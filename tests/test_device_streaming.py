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
    # Hard clip w = 420 - 10 = 410. center_x = 5 + 205 = 210
    # Hard clip h = 297 - 30 = 267. center_y = 25 + 133.5 = 158.5
    cx, cy = profile.calculate_center_mm(420.0, 297.0, "exp")
    assert pytest.approx(cx) == 210.0
    assert pytest.approx(cy) == 158.5


def test_hpgl_emitter():
    profile = get_default_profile()
    emitter = HPGLEmitter(profile, margin_profile="exp")

    doc = Document()
    doc.page.width = 420.0
    doc.page.height = 297.0

    # 1 line with pen 1 from (210, 158.5) [center] to (235, 158.5) [+25mm]
    path = VectorPath(
        points=np.array([[210.0, 158.5], [235.0, 158.5]]),
        pen_id=1,
    )
    doc.items.append(ImportItem(name="TestItem", paths=[path]))

    job = compile_document_to_plot_job(doc)
    commands = emitter.emit_commands(job, doc)
    assert len(commands) >= 4  # IN, SP1, PU, PD, PU;SP0
    hpgl_str = "".join(c.hpgl for c in commands)

    assert "IN;" in hpgl_str
    assert "SP1;" in hpgl_str
    # At center (210, 158.5), plotter units should be (0, 0)
    assert "PU0,0;" in hpgl_str
    # At (235, 158.5) -> dx = +25mm * 40 = 1000 units in X
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
            # 410 x 267 mm
            assert pytest.approx(result.hard_clip_mm[0], rel=1e-2) == 410.0
            assert pytest.approx(result.hard_clip_mm[1], rel=1e-2) == 267.0
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


def test_axis_transformations():
    profile = get_default_profile()
    # Center for A3 EXP is (210.0, 158.5)
    # Point at center (210.0, 158.5) -> (0, 0)
    # Point at +25mm X: (235.0, 158.5) -> dx=+25mm -> 1000 units
    # Point at -10mm Y: (210.0, 148.5) -> y_mm is 10mm higher on sheet -> dy_c = +10mm (upwards) -> 400 units

    # 1. Standard (0 deg, no invert, no swap)
    e_std = HPGLEmitter(profile, margin_profile="exp")
    assert e_std.to_plotter_units(210.0, 158.5, 420.0, 297.0) == (0, 0)
    assert e_std.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (1000, 0)
    assert e_std.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (0, 400)

    # 2. Invert X
    e_inv_x = HPGLEmitter(profile, margin_profile="exp", invert_x=True)
    assert e_inv_x.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (-1000, 0)

    # 3. Invert Y
    e_inv_y = HPGLEmitter(profile, margin_profile="exp", invert_y=True)
    assert e_inv_y.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (0, -400)

    # 4. Swap XY
    e_swap = HPGLEmitter(profile, margin_profile="exp", swap_xy=True)
    assert e_swap.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, 1000)
    assert e_swap.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (400, 0)

    # 5. Rotation 90° (CCW in Cartesian: (1, 0) -> (0, 1))
    e_rot90 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=90)
    assert e_rot90.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, 1000)

    # 6. Rotation 180°
    e_rot180 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=180)
    assert e_rot180.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (-1000, 0)

    # 7. Rotation 270°
    e_rot270 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=270)
    assert e_rot270.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, -1000)


def test_userspace_xon_xoff():
    plotter = VirtualPlotter(paper="A3")

    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "streamer_xoff_port"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        profile = get_default_profile()
        emitter = HPGLEmitter(profile)
        doc = Document()
        doc.page.width = 420.0
        doc.page.height = 297.0

        # Create multiple lines
        paths = [
            VectorPath(points=np.array([[100.0 + i * 5, 100.0], [120.0 + i * 5, 120.0]]), pen_id=1)
            for i in range(8)
        ]
        doc.items.append(ImportItem(name="TestLines", paths=paths))
        job = compile_document_to_plot_job(doc)
        cmds = emitter.emit_commands(job, doc)

        finished_box = [False, False]
        streamer = SerialStreamer(
            on_finished=lambda success, msg: finished_box.__setitem__(0, True) or finished_box.__setitem__(1, success),
        )

        streamer.start_stream(port_path, cmds, inter_command_delay_s=0.03, xonxoff_userspace=True)
        time.sleep(0.04)

        # Plotter sends XOFF (0x13) to pause
        server._enqueue_response(b"\x13")
        time.sleep(0.1)

        # Streamer should be paused by XOFF
        assert streamer._xoff_paused is True
        assert streamer.is_active()
        assert finished_box[0] is False

        # Now plotter sends XON (0x11) to resume
        server._enqueue_response(b"\x11")
        time.sleep(0.05)

        # Wait for completion
        start_t = time.time()
        while not finished_box[0] and (time.time() - start_t < 3.0):
            time.sleep(0.05)

        assert finished_box[0] is True
        assert finished_box[1] is True
        server.stop()


def test_streamer_flow_control_options():
    """Verify SerialStreamer handles flow_control parameter properly."""
    plotter = VirtualPlotter(paper="A3")
    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "streamer_fc_port"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        profile = get_default_profile()
        emitter = HPGLEmitter(profile)
        doc = Document()
        path = VectorPath(points=np.array([[100.0, 100.0], [110.0, 110.0]]), pen_id=1)
        doc.items.append(ImportItem(name="Line", paths=[path]))
        cmds = emitter.emit_commands(compile_document_to_plot_job(doc), doc)

        for fc in ["rtscts", "dsrdtr", "xonxoff", "none"]:
            finished_box = [False, False]
            streamer = SerialStreamer(
                on_finished=lambda success, msg: finished_box.__setitem__(0, True) or finished_box.__setitem__(1, success),
            )
            started = streamer.start_stream(port_path, cmds, flow_control=fc)
            assert started is True
            start_t = time.time()
            while not finished_box[0] and (time.time() - start_t < 2.0):
                time.sleep(0.02)
            assert finished_box[0] is True
            assert finished_box[1] is True

        server.stop()


def test_emitter_step_index_sync_with_job_steps():
    """Verify that HPGLEmitter increments global_step_idx for PU commands to match job.steps."""
    profile = get_default_profile()
    emitter = HPGLEmitter(profile, points_per_cmd=16)

    doc = Document()
    doc.page.width = 420.0
    doc.page.height = 297.0

    # 3 polylines:
    # Line 1: 3 vertices (2 draw segments)
    # Line 2: 2 vertices (1 draw segment)
    # Line 3: 4 vertices (3 draw segments)
    paths = [
        VectorPath(points=np.array([[50.0, 50.0], [60.0, 50.0], [70.0, 60.0]]), pen_id=1),
        VectorPath(points=np.array([[100.0, 100.0], [120.0, 100.0]]), pen_id=1),
        VectorPath(points=np.array([[150.0, 150.0], [160.0, 150.0], [170.0, 160.0], [180.0, 160.0]]), pen_id=1),
    ]
    doc.items.append(ImportItem(name="Paths", paths=paths))

    job = compile_document_to_plot_job(doc, PipelineConfig(sort_paths=False))
    # In job.steps:
    # Line 1: 1 TRAVEL + 2 DRAW = 3 steps (indices 0, 1, 2)
    # Line 2: 1 TRAVEL + 1 DRAW = 2 steps (indices 3, 4)
    # Line 3: 1 TRAVEL + 3 DRAW = 4 steps (indices 5, 6, 7, 8)
    # Total job.steps = 9
    assert len(job.steps) == 9
    travel_steps = [s for s in job.steps if s.action == "TRAVEL"]
    draw_steps = [s for s in job.steps if s.action == "DRAW"]
    assert len(travel_steps) == 3
    assert len(draw_steps) == 6

    cmds = emitter.emit_commands(job, doc)
    # Filter to motion commands (PU / PD)
    pu_cmds = [c for c in cmds if c.hpgl.startswith("PU") and not c.hpgl.startswith("PU;")]
    pd_cmds = [c for c in cmds if c.hpgl.startswith("PD")]

    assert len(pu_cmds) == 3
    assert len(pd_cmds) == 3

    # Check step indices:
    # PU 1 -> step 0 (TRAVEL)
    # PD 1 -> step 1 (DRAW steps 1 and 2)
    # PU 2 -> step 3 (TRAVEL step 3, NOT 2!)
    # PD 2 -> step 4 (DRAW step 4)
    # PU 3 -> step 5 (TRAVEL step 5, NOT 3!)
    # PD 3 -> step 6 (DRAW steps 6, 7, 8)
    assert pu_cmds[0].step_index == 0
    assert pd_cmds[0].step_index == 1
    assert pu_cmds[1].step_index == 3
    assert pd_cmds[1].step_index == 4
    assert pu_cmds[2].step_index == 5
    assert pd_cmds[2].step_index == 6

    # End command should reflect total step count
    end_cmd = cmds[-1]
    assert "PU;SP0;" in end_cmd.hpgl
    assert end_cmd.step_index == len(job.steps)


def test_serial_streamer_write_timeout(monkeypatch):
    """Verify write_timeout is accepted and passed to serial.Serial."""
    import serial
    recorded_kwargs = {}

    class MockSerial:
        def __init__(self, *args, **kwargs):
            recorded_kwargs.update(kwargs)
            self.is_open = False

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", MockSerial)

    streamer = SerialStreamer(write_timeout=4.2)
    assert streamer.write_timeout == 4.2

    # Verify write_timeout passed through to Serial
    streamer._run_stream(
        port="/dev/ttyUSB0",
        commands=[],
        baudrate=19200,
        write_timeout=4.2,
    )
    assert recorded_kwargs.get("write_timeout") == 4.2

