"""Tests for device profiles, HP-GL emitter, probing, and serial streaming."""

import tempfile
import time
from pathlib import Path
import pytest
import numpy as np

from plotter_studio.core.document import Document, ImportItem, VectorPath
from plotter_studio.device import (
    load_profile,
    get_default_profile,
    HPGLEmitter,
    list_serial_ports,
    probe_plotter,
    SerialStreamer,
    StreamerState,
)
from plotter_studio.emulator import VirtualPlotter, PtyServer, TcpServer
from plotter_studio.pipeline.compiler import compile_document_to_plot_job, PipelineConfig


def test_device_profile():
    profile = get_default_profile()
    assert profile.model_id == "mutoh_xp500"
    assert profile.units_per_mm == 40.0
    assert profile.connection.baudrate == 19200
    assert profile.connection.rtscts is True

    # Test margins
    m_exp = profile.get_margins("exp")
    assert m_exp == (25.0, 5.0, 5.0, 5.0)

    # Test center calculation for A3 (420 x 297 mm)
    # Hard clip w = 420 - 30 = 390. center_x = 5 + 195 = 200
    # Hard clip h = 297 - 10 = 287. center_y = 25 + 143.5 = 168.5
    cx, cy = profile.calculate_center_mm(420.0, 297.0, "exp")
    assert pytest.approx(cx) == 200.0
    assert pytest.approx(cy) == 168.5


def test_hpgl_emitter():
    profile = get_default_profile()
    emitter = HPGLEmitter(profile, margin_profile="exp")

    doc = Document()
    doc.page.width = 420.0
    doc.page.height = 297.0

    # 1 line with pen 1 from (200, 168.5) [center] to (225, 168.5) [+25mm]
    path = VectorPath(
        points=np.array([[200.0, 168.5], [225.0, 168.5]]),
        pen_id=1,
    )
    doc.items.append(ImportItem(name="TestItem", paths=[path]))

    job = compile_document_to_plot_job(doc)
    commands = emitter.emit_commands(job, doc)
    assert len(commands) >= 4  # IN, SP1, PU, PD, PU;SP0
    hpgl_str = "".join(c.hpgl for c in commands)

    assert "IN;" in hpgl_str
    assert "SP1;" in hpgl_str
    # At center (200, 168.5), plotter units should be (0, 0)
    assert "PU0,0;" in hpgl_str
    # At (225, 168.5) -> dx = +25mm * 40 = 1000 units in X
    assert "PD1000,0;" in hpgl_str
    assert "PU;SP0;" in hpgl_str


def test_device_probing():
    plotter = VirtualPlotter(paper="A3", margin_profile="EXP", resolution_mm=0.025)

    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "test_port"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        try:
            result = probe_plotter(port_path, timeout=1.0)
            assert result.success is True
            assert "7585B" in result.model
            assert result.units_per_mm == 40.0
            assert result.detected_format == "A3"
            assert result.hard_clip_mm is not None
            # 390 x 287 mm
            assert pytest.approx(result.hard_clip_mm[0], rel=1e-2) == 390.0
            assert pytest.approx(result.hard_clip_mm[1], rel=1e-2) == 287.0
        finally:
            server.stop()


def test_serial_streamer_e2e():
    plotter = VirtualPlotter(paper="A3", margin_profile="EXP", resolution_mm=0.025)

    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "streamer_port"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        profile = get_default_profile()
        emitter = HPGLEmitter(profile, margin_profile="exp")

        doc = Document()
        doc.page.width = 420.0
        doc.page.height = 297.0

        # Draw a 50mm square in pen 1
        poly = np.array([
            [175.0, 143.5],
            [225.0, 143.5],
            [225.0, 193.5],
            [175.0, 193.5],
            [175.0, 143.5],
        ])
        path = VectorPath(points=poly, pen_id=1)
        doc.items.append(ImportItem(name="Square", paths=[path]))

        job = compile_document_to_plot_job(doc)
        cmds = emitter.emit_commands(job, doc)

        progress_history = []
        finished_event = [False, False, ""]

        streamer = SerialStreamer(
            on_progress=lambda s, t, pct, pen, d: progress_history.append((pct, d)),
            on_finished=lambda success, msg: finished_event.__setitem__(0, True) or finished_event.__setitem__(1, success) or finished_event.__setitem__(2, msg),
        )

        started = streamer.start_stream(port_path, cmds)
        assert started is True

        # Wait for completion
        start_t = time.time()
        while not finished_event[0] and (time.time() - start_t < 3.0):
            time.sleep(0.05)

        assert finished_event[0] is True
        assert finished_event[1] is True  # Success
        assert len(progress_history) > 0
        assert progress_history[-1][0] == 100.0

        # Verify virtual plotter received all lines
        time.sleep(0.05)
        server.stop()

        assert len(plotter.recorded_polylines) == 1
        assert pytest.approx(plotter.stats.drawn_distance_mm, rel=1e-2) == 200.0


def test_streamer_abort():
    plotter = VirtualPlotter(paper="A3", realtime=True, speedup=0.5)

    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "streamer_abort_port"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        profile = get_default_profile()
        emitter = HPGLEmitter(profile)
        doc = Document()
        doc.page.width = 420.0
        doc.page.height = 297.0

        # Create items with different pens
        paths = []
        for p in range(1, 4):
            paths.append(
                VectorPath(
                    points=np.array([[100.0, 100.0 + p * 10], [200.0, 100.0 + p * 10]]),
                    pen_id=p,
                )
            )
        doc.items.append(ImportItem(name="MultiPen", paths=paths))

        job = compile_document_to_plot_job(doc)
        cmds = emitter.emit_commands(job, doc)

        finished_box = [False, False]
        streamer = SerialStreamer(
            on_finished=lambda success, msg: finished_box.__setitem__(0, True) or finished_box.__setitem__(1, success),
        )

        streamer.start_stream(port_path, cmds, inter_command_delay_s=0.04)
        time.sleep(0.05)
        assert streamer.is_active()

        # Abort
        streamer.abort()

        start_t = time.time()
        while not finished_box[0] and (time.time() - start_t < 2.0):
            time.sleep(0.05)

        assert finished_box[0] is True
        assert finished_box[1] is False  # Aborted
        server.stop()
