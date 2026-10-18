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
    assert profile.swap_xy is True
    assert profile.invert_y is True
    emitter = HPGLEmitter(profile, margin_profile="exp")

    doc = Document()
    doc.page.width = 420.0
    doc.page.height = 297.0

    # 1 line with pen 1 from (210, 158.5) [center] to (235, 158.5) [+25mm in sheet X = +1000 units in plotter Y (carriage)]
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
    # At (235, 158.5) -> dx_sheet = +25mm -> plotter (X=feed=0, Y=carriage=+1000)
    assert "PD0,1000;" in hpgl_str
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

    # 0. Mutoh XP-500 default (swap_xy=True, invert_y=True -> X=feed down, Y=carriage right)
    e_xp500 = HPGLEmitter(profile, margin_profile="exp")
    assert e_xp500.to_plotter_units(210.0, 158.5, 420.0, 297.0) == (0, 0)
    # +25mm right on sheet -> (0, +1000)
    assert e_xp500.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, 1000)
    # 10mm higher on sheet (y=148.5) -> -400 in X (feed down)
    assert e_xp500.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (-400, 0)
    # Plottable corners for A3 EXP (left=5, right=415, top=25, bottom=292) map to X: ±5340, Y: ±8200
    assert e_xp500.to_plotter_units(5.0, 25.0, 420.0, 297.0) == (-5340, -8200)
    assert e_xp500.to_plotter_units(415.0, 292.0, 420.0, 297.0) == (5340, 8200)

    # 1. Unswapped Cartesian (0 deg, no invert, no swap)
    e_std = HPGLEmitter(profile, margin_profile="exp", swap_xy=False, invert_x=False, invert_y=False)
    assert e_std.to_plotter_units(210.0, 158.5, 420.0, 297.0) == (0, 0)
    assert e_std.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (1000, 0)
    assert e_std.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (0, 400)

    # 2. Invert X
    e_inv_x = HPGLEmitter(profile, margin_profile="exp", swap_xy=False, invert_x=True, invert_y=False)
    assert e_inv_x.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (-1000, 0)

    # 3. Invert Y
    e_inv_y = HPGLEmitter(profile, margin_profile="exp", swap_xy=False, invert_x=False, invert_y=True)
    assert e_inv_y.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (0, -400)

    # 4. Swap XY only
    e_swap = HPGLEmitter(profile, margin_profile="exp", swap_xy=True, invert_x=False, invert_y=False)
    assert e_swap.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, 1000)
    assert e_swap.to_plotter_units(210.0, 148.5, 420.0, 297.0) == (400, 0)

    # 5. Rotation 90° (CCW in Cartesian: (1, 0) -> (0, 1))
    e_rot90 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=90, swap_xy=False, invert_x=False, invert_y=False)
    assert e_rot90.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (0, 1000)

    # 6. Rotation 180°
    e_rot180 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=180, swap_xy=False, invert_x=False, invert_y=False)
    assert e_rot180.to_plotter_units(235.0, 158.5, 420.0, 297.0) == (-1000, 0)

    # 7. Rotation 270°
    e_rot270 = HPGLEmitter(profile, margin_profile="exp", rotation_deg=270, swap_xy=False, invert_x=False, invert_y=False)
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


def test_streamer_pause_on_pen_change(monkeypatch):
    """Verify automatic pause before SPn; pen change and resume."""
    import serial
    from plotter_studio.device.emitter import EmittedCommand
    from plotter_studio.device.streamer import StreamerState

    written_chunks = []
    flushed = [False]

    class MockSerial:
        def __init__(self, *args, **kwargs):
            pass

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def write(self, data: bytes):
            written_chunks.append(data.decode("ascii"))

        def flush(self):
            flushed[0] = True

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", MockSerial)

    cmds = [
        EmittedCommand(hpgl="IN;\r\n", step_index=0, pen=0, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="SP1;VS15;FS20;\r\n", step_index=0, pen=1, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="PD100,100;\r\n", step_index=1, pen=1, is_draw=True, dist_mm=10.0),
        EmittedCommand(hpgl="SP2;VS15;FS20;\r\n", step_index=1, pen=2, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="PD200,200;\r\n", step_index=2, pen=2, is_draw=True, dist_mm=10.0),
        EmittedCommand(hpgl="PU;SP0;\r\n", step_index=2, pen=0, is_draw=False, dist_mm=0.0),
    ]

    statuses = []
    finished = [False, False]
    streamer = SerialStreamer(
        on_status=lambda st, msg: statuses.append((st, msg)),
        on_finished=lambda ok, msg: finished.__setitem__(0, True) or finished.__setitem__(1, ok),
        end_settle_delay_s=0.01,
    )

    streamer.start_stream("/dev/ttyUSB0", cmds, pause_on_pen_change=True, end_settle_delay_s=0.01)

    # Wait until streamer pauses at SP2
    start_t = time.time()
    while not streamer.is_user_paused() and (time.time() - start_t < 2.0):
        time.sleep(0.01)

    assert streamer.is_user_paused() is True
    assert streamer.state == StreamerState.PAUSED
    # SP1 and PD100,100 should have been sent, but SP2 not yet
    assert any("SP1;" in c for c in written_chunks)
    assert not any("SP2;" in c for c in written_chunks)

    # Resume and wait for completion
    streamer.resume()
    start_t = time.time()
    while not finished[0] and (time.time() - start_t < 2.0):
        time.sleep(0.01)

    assert finished == [True, True]
    assert any("SP2;" in c for c in written_chunks)
    assert flushed[0] is True


def test_xp500_golden_oh_measurements():
    """Golden test verifying HPGLEmitter and probe_plotter against real Mutoh XP-500 OH; measurements."""
    profile = get_default_profile()
    emitter = HPGLEmitter(profile, margin_profile="exp")

    # A3 landscape (420 x 297 mm), EXP margins: top=25, bottom=5, left=5, right=5
    # Plottable box: x in [5, 415] (width 410 mm), y in [25, 292] (height 267 mm)
    # Measured OH on XP-500 for A3 landscape: -5399,-8209,5399,8209 (X=feed ±270mm, Y=carriage ±410.5mm)
    # Theoretical EXP in 40 units/mm: X in [-5340, 5340], Y in [-8200, 8200]
    px_tl, py_tl = emitter.to_plotter_units(5.0, 25.0, 420.0, 297.0)
    px_tr, py_tr = emitter.to_plotter_units(415.0, 25.0, 420.0, 297.0)
    px_bl, py_bl = emitter.to_plotter_units(5.0, 292.0, 420.0, 297.0)
    px_br, py_br = emitter.to_plotter_units(415.0, 292.0, 420.0, 297.0)

    assert (px_tl, py_tl) == (-5340, -8200)
    assert (px_tr, py_tr) == (-5340, 8200)
    assert (px_bl, py_bl) == (5340, -8200)
    assert (px_br, py_br) == (5340, 8200)

    # Dynamic units_per_mm (e.g. OF; = 100,100 -> 0.01 mm step)
    emitter_100 = HPGLEmitter(profile, margin_profile="exp", units_per_mm=100.0)
    assert emitter_100.to_plotter_units(415.0, 292.0, 420.0, 297.0) == (13350, 20500)


def test_abort_during_xoff_on_last_command(monkeypatch):
    """Verify aborting while XOFF-paused on the final command reports abort (False), never success (0.4)."""
    import serial
    from plotter_studio.device.emitter import EmittedCommand

    written = []
    output_flushed = [False]

    class MockXoffSerial:
        def __init__(self, *args, **kwargs):
            self.in_waiting = 1
            self._sent_xoff = False
            self.rtscts = False

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            output_flushed[0] = True

        def read(self, n=1):
            if not self._sent_xoff:
                self._sent_xoff = True
                self.in_waiting = 0
                return b"\x13"  # XOFF
            return b""

        def write(self, data: bytes):
            written.append(data)
            return len(data)

        def flush(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", MockXoffSerial)

    # Single command = last command in loop
    cmds = [EmittedCommand(hpgl="PD100,100;\r\n", step_index=0, pen=1, is_draw=True, dist_mm=5.0)]
    finished_res = [None, ""]
    streamer = SerialStreamer(
        on_finished=lambda ok, msg: finished_res.__setitem__(0, ok) or finished_res.__setitem__(1, msg),
    )

    streamer.start_stream("/dev/ttyUSB0", cmds, flow_control="xonxoff", sync_with_oa=False)

    # Wait until XOFF pause triggers
    start_t = time.time()
    while not streamer._xoff_paused and (time.time() - start_t < 1.0):
        time.sleep(0.01)
    assert streamer._xoff_paused is True

    # Abort while waiting for XON on the last command
    streamer.abort()

    start_t = time.time()
    while finished_res[0] is None and (time.time() - start_t < 1.0):
        time.sleep(0.01)

    assert finished_res[0] is False
    assert "abgebrochen" in finished_res[1].lower()
    assert output_flushed[0] is True
    assert any(b"\x1b.K" in chunk for chunk in written)


def test_cts_stall_and_serial_framing(monkeypatch):
    """Verify CTS stall retries without killing the job (0.2, 0.3) and 7E1 framing is passed (0.9)."""
    import serial
    from plotter_studio.device.emitter import EmittedCommand

    recorded_kwargs = {}
    written = []
    cts_flag = [False]  # Start with CTS low (buffer full)

    class MockCtsSerial:
        def __init__(self, *args, **kwargs):
            recorded_kwargs.update(kwargs)
            self.rtscts = kwargs.get("rtscts", False)
            self.in_waiting = 0

        @property
        def cts(self):
            return cts_flag[0]

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        def write(self, data: bytes):
            written.append(data)
            return len(data)

        def read(self, n=1):
            return b"0,0,0\r"

        def flush(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(serial, "Serial", MockCtsSerial)

    cmds = [EmittedCommand(hpgl="PD100,100;\r\n", step_index=0, pen=1, is_draw=True, dist_mm=5.0)]
    statuses = []
    finished = [None]
    streamer = SerialStreamer(
        on_status=lambda st, msg: statuses.append((st, msg)),
        on_finished=lambda ok, msg: finished.__setitem__(0, ok),
        end_settle_delay_s=0.0,
    )

    streamer.start_stream(
        "/dev/ttyUSB0",
        cmds,
        flow_control="rtscts",
        bytesize=7,
        parity="E",
        stopbits=2,
        sync_with_oa=True,
    )

    # Wait until streamer enters PAUSED due to CTS low
    start_t = time.time()
    while not any(st == StreamerState.PAUSED for st, _ in statuses) and (time.time() - start_t < 1.0):
        time.sleep(0.01)
    assert any("CTS low" in msg for _, msg in statuses)

    # Release CTS -> job should resume and finish cleanly with OA; sync
    cts_flag[0] = True
    start_t = time.time()
    while finished[0] is None and (time.time() - start_t < 1.0):
        time.sleep(0.01)

    assert finished[0] is True
    assert recorded_kwargs["bytesize"] == serial.SEVENBITS
    assert recorded_kwargs["parity"] == serial.PARITY_EVEN
    assert recorded_kwargs["stopbits"] == serial.STOPBITS_TWO
    assert any(b"OA;\r" in chunk for chunk in written)


def test_fake_transport_partial_writes_and_build_emitter():
    """Verify pluggable Transport with partial writes, DeviceConnectionConfig sync, and build_emitter priority."""
    from plotter_studio.device import (
        Transport,
        build_emitter,
        DeviceConnectionConfig,
        ConfiguredDevice,
    )
    from plotter_studio.device.emitter import EmittedCommand

    # 1. DeviceConnectionConfig single source of truth
    cfg_xon = DeviceConnectionConfig(xonxoff=True)
    assert cfg_xon.flow_control == "xonxoff"
    assert cfg_xon.xonxoff is True
    assert cfg_xon.rtscts is False

    cfg_fc = DeviceConnectionConfig(flow_control="dsrdtr")
    assert cfg_fc.dsrdtr is True
    assert cfg_fc.rtscts is False

    # 2. build_emitter priority order: Document -> ConfiguredDevice -> explicit overrides
    doc = Document()
    doc.page.feed_edge = "bottom"
    doc.page.margin_profile = "norm"
    dev = ConfiguredDevice(
        id="dev1",
        name="Custom XP-500",
        model_id="mutoh_xp500",
        margin_profile="type1",
        rotation=90,
        swap_xy=False,
        probed_units_per_mm=100.0,
    )
    em = build_emitter(
        document=doc,
        device=dev,
        margin_profile="exp",
        overrides={"rotation_deg": 180},
    )
    assert em.feed_edge == "bottom"
    assert em.margin_profile == "exp"
    assert em.units_per_mm == 100.0
    assert em.rotation_deg == 180
    assert em.swap_xy is False

    # 3. Pluggable Transport simulating partial writes (3 bytes at a time)
    class PartialWriteFakeTransport(Transport):
        def __init__(self):
            self.opened = False
            self.closed = False
            self.sent = bytearray()

        def open(self) -> None:
            self.opened = True

        def write(self, data: bytes) -> int:
            chunk = data[:3]
            self.sent.extend(chunk)
            return len(chunk)

        def read_available(self) -> bytes:
            return b""

        def read_some(self, max_bytes: int = 128, timeout_s: float = 0.05) -> bytes:
            return b"0,0,0\r"

        def close(self) -> None:
            self.closed = True

    fake_t = PartialWriteFakeTransport()
    cmds = [
        EmittedCommand(hpgl="IN;\r\n", step_index=0, pen=0, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="SP1;PD100,200;\r\n", step_index=1, pen=1, is_draw=True, dist_mm=10.0),
    ]
    done = [None]
    streamer = SerialStreamer(
        on_finished=lambda ok, msg: done.__setitem__(0, ok),
        end_settle_delay_s=0.0,
        transport=fake_t,
    )
    assert streamer.start_stream("fake://plotter", cmds, sync_with_oa=True) is True
    start_t = time.time()
    while done[0] is None and (time.time() - start_t < 1.0):
        time.sleep(0.01)

    assert done[0] is True
    assert fake_t.opened is True
    assert fake_t.closed is True
    assert b"IN;\r\nSP1;PD100,200;\r\nOA;\r" == bytes(fake_t.sent)


def test_resume_from_step_and_trace_log_and_emitter_capabilities():
    """Verify SerialStreamer resume from step N, trace log recording, and HPGLEmitter IW/VS/FS capabilities."""
    from plotter_studio.device import Transport
    from plotter_studio.device.emitter import EmittedCommand

    class RecordingTransport(Transport):
        def __init__(self):
            self.sent = bytearray()

        def open(self) -> None:
            pass

        def write(self, data: bytes) -> int:
            self.sent.extend(data)
            return len(data)

        def read_available(self) -> bytes:
            return b""

        def read_some(self, max_bytes: int = 128, timeout_s: float = 0.05) -> bytes:
            return b"0,0,0\r"

        def close(self) -> None:
            pass

    rec = RecordingTransport()
    cmds = [
        EmittedCommand(hpgl="IN;\r\n", step_index=0, pen=0, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="SP1;VS15;FS20;\r\n", step_index=0, pen=1, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="PU100,200;\r\n", step_index=0, pen=1, is_draw=False, dist_mm=0.0),
        EmittedCommand(hpgl="PD300,400;\r\n", step_index=1, pen=1, is_draw=True, dist_mm=10.0),
        EmittedCommand(hpgl="PD500,600;\r\n", step_index=2, pen=1, is_draw=True, dist_mm=10.0),
        EmittedCommand(hpgl="PU;SP0;\r\n", step_index=3, pen=0, is_draw=False, dist_mm=0.0),
    ]
    done = [None]
    streamer = SerialStreamer(
        on_finished=lambda ok, msg: done.__setitem__(0, ok),
        end_settle_delay_s=0.0,
        transport=rec,
    )
    # Resume from step 2: should emit IN;, SP1;VS15;FS20;, PU300,400; (end of skipped step 1), then PD500,600; and PU;SP0;
    assert streamer.start_stream("fake://plotter", cmds, sync_with_oa=False, start_step_index=2) is True
    start_t = time.time()
    while done[0] is None and (time.time() - start_t < 1.0):
        time.sleep(0.01)

    assert done[0] is True
    sent_str = rec.sent.decode("ascii")
    assert "IN;\r\n" in sent_str
    assert "SP1;VS15;FS20;\r\n" in sent_str
    assert "PD300,400;\r\n" not in sent_str
    assert "PU300,400;\r\nPD500,600;\r\n" in sent_str
    assert len(streamer.get_trace_log()) >= 4

    # Verify HPGLEmitter decimal VS, hp_level FS, handshake init, and IW clip
    import numpy as np
    from plotter_studio.pipeline.compiler import PlotJob, PlotLayer

    prof = get_default_profile()
    prof.force_unit = "hp_level"
    prof.decimal_speed = True
    doc = Document()
    doc.pens[0].speed_cm_s = 12.5
    doc.pens[0].force_g = 100  # 100 / 25 -> FS4
    job = PlotJob()
    job.layers[1] = PlotLayer(pen_id=1, pen=doc.pens[0], lines=[np.array([[10.0, 30.0], [20.0, 40.0]])])

    em = HPGLEmitter(prof, include_handshake_init=True, include_iw_clip=True)
    out = em.emit_string(job, doc)
    assert out.startswith("\x1b.R\r\x1b.(\rIN;IW")
    assert "SP1;VS12.5;FS4;" in out




