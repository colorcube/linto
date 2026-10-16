"""Tests for Mutoh XP-500 Plotter Emulator."""

import os
import socket
import tempfile
import time
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from plotter_studio.emulator import (
    VirtualPlotter,
    PtyServer,
    TcpServer,
    BytePacer,
    export_plotter_svg,
)


def test_inquiry_commands():
    """Verify all HP-GL and Escape inquiry responses."""
    responses: list[bytes] = []

    plotter = VirtualPlotter(
        paper="A3",
        margin_profile="EXP",
        buffer_size=1000,
        resolution_mm=0.025,
        on_response=lambda resp: responses.append(resp),
    )

    # 1. Device identification
    plotter.receive_bytes(b"OI;")
    assert responses.pop(0) == b"7585B\r"

    # 2. Units per mm (40, 40 for 0.025 mm)
    plotter.receive_bytes(b"OF;")
    assert responses.pop(0) == b"40,40\r"

    # 3. Stocker type & pen
    plotter.receive_bytes(b"OT;")
    assert responses.pop(0) == b"1,1\r"

    # 4. Status byte
    plotter.receive_bytes(b"OS;")
    assert responses.pop(0) == b"16\r"

    # 5. Error code
    plotter.receive_bytes(b"OE;")
    assert responses.pop(0) == b"0\r"

    # 6. Hard-clip window for A3 with EXP margins (410 x 267 mm)
    # 410 * 40 / 2 = 8200, 267 * 40 / 2 = 5340
    plotter.receive_bytes(b"OH;")
    assert responses.pop(0) == b"-8200,-5340,8200,5340\r"

    # 7. Escape sequence ESC.A (identification)
    plotter.receive_bytes(b"\x1b.A")
    assert responses.pop(0) == b"7585B\r"

    # 8. Escape sequence ESC.L (buffer capacity)
    plotter.receive_bytes(b"\x1b.L")
    assert responses.pop(0) == b"1000\r"

    # 9. Escape sequence ESC.B (free buffer)
    plotter.receive_bytes(b"\x1b.B")
    resp_b = responses.pop(0)
    assert resp_b.endswith(b"\r")
    assert int(resp_b[:-1]) > 0


def test_drawing_and_metrics():
    """Verify drawing commands, polyline recording, and distance calculation."""
    plotter = VirtualPlotter(
        paper="A3",
        resolution_mm=0.025,  # 40 units/mm
    )

    # Draw a 25 mm x 25 mm square (1000 x 1000 units) with pen 1
    # Perimeter should be 100 mm
    hpgl_data = (
        b"IN; "
        b"SP1; "
        b"VS30; "
        b"PU 0,0; "
        b"PD 1000,0, 1000,1000, 0,1000, 0,0; "
        b"PU; "
        b"SP0;"
    )
    plotter.receive_bytes(hpgl_data)

    assert plotter.stats.commands_executed > 5
    assert plotter.stats.pen_changes == 2  # SP1, SP0
    assert plotter.stats.pen_down_count == 1
    assert plotter.stats.pen_up_count >= 1

    # Distance check: 1000 units = 25 mm. 4 segments * 25 mm = 100 mm
    assert pytest.approx(plotter.stats.drawn_distance_mm, rel=1e-2) == 100.0

    # Polylines recorded: 1 polyline with pen 1 and 5 points
    assert len(plotter.recorded_polylines) == 1
    poly = plotter.recorded_polylines[0]
    assert poly.pen == 1
    assert len(poly.points) == 5
    # First point: (0, 0)
    assert pytest.approx(poly.points[0][0]) == 0.0
    assert pytest.approx(poly.points[0][1]) == 0.0
    # Second point: (25.0, 0.0)
    assert pytest.approx(poly.points[1][0]) == 25.0
    assert pytest.approx(poly.points[1][1]) == 0.0


def test_relative_motion():
    """Verify relative motion (PR) command."""
    plotter = VirtualPlotter(
        paper="A3",
        resolution_mm=0.025,
    )

    # Move to (400, 400) absolute (10 mm, 10 mm), then PR 400,0 (10 mm in X)
    plotter.receive_bytes(b"IN; SP2; PU 400,400; PD; PR 400,0; PU;")

    assert len(plotter.recorded_polylines) == 1
    poly = plotter.recorded_polylines[0]
    assert poly.pen == 2
    assert len(poly.points) == 2
    assert pytest.approx(poly.points[0][0]) == 10.0
    assert pytest.approx(poly.points[0][1]) == 10.0
    assert pytest.approx(poly.points[1][0]) == 20.0
    assert pytest.approx(poly.points[1][1]) == 10.0
    assert pytest.approx(plotter.stats.drawn_distance_mm, rel=1e-2) == 10.0


def test_abort_and_reset():
    """Verify ESC.K (abort) and ESC.R (reset)."""
    plotter = VirtualPlotter()
    plotter.receive_bytes(b"SP1; PD 100,100;")
    assert plotter.pen_down is True
    assert plotter.active_pen == 1

    # Abort
    plotter.receive_bytes(b"\x1b.K")
    assert plotter.pen_down is False

    # Reset
    plotter.receive_bytes(b"\x1b.R")
    assert plotter.active_pen == 0
    assert plotter.pen_down is False
    assert plotter.pos_units == (0, 0)


def test_svg_export(tmp_path: Path):
    """Verify SVG export of drawn polylines."""
    plotter = VirtualPlotter(paper="A4", resolution_mm=0.025)
    plotter.receive_bytes(b"SP1; PU 0,0; PD 500,500; PU; SP3; PU 100,100; PD 200,200; PU;")

    out_file = tmp_path / "test_plot.svg"
    export_plotter_svg(plotter, out_file)

    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "<svg" in content
    assert "class=\"plot-path\"" in content
    # XML parse validation
    tree = ET.fromstring(content)
    assert tree.tag.endswith("svg")


def test_pty_server_e2e():
    """Verify full end-to-end communication over Linux PTY."""
    plotter = VirtualPlotter(paper="A3", resolution_mm=0.025)

    with tempfile.TemporaryDirectory() as tmpdir:
        symlink = Path(tmpdir) / "virtual_plotter_link"
        server = PtyServer(plotter, symlink_path=symlink)
        port_path = server.start()

        assert symlink.is_symlink()
        assert Path(port_path).exists()

        try:
            # Open slave device directly as raw binary file
            with open(port_path, "r+b", buffering=0) as f:
                # Send inquiry
                f.write(b"OI;\r")
                time.sleep(0.05)
                reply = f.read(100)
                assert b"7585B\r" in reply

                # Send resolution inquiry
                f.write(b"OF;\r")
                time.sleep(0.05)
                reply = f.read(100)
                assert b"40,40\r" in reply

                # Send buffer inquiry
                f.write(b"\x1b.B")
                time.sleep(0.05)
                reply = f.read(100)
                assert b"\r" in reply

                # Send drawing vector
                f.write(b"IN; SP1; PU 0,0; PD 1000,0; PU; SP0;\r")
                time.sleep(0.1)

            assert plotter.stats.drawn_distance_mm > 0
            assert plotter.stats.pen_changes >= 2
        finally:
            server.stop()

        assert not symlink.exists()


def test_tcp_server_e2e():
    """Verify communication over TCP socket."""
    plotter = VirtualPlotter(paper="A3")
    server = TcpServer(plotter, host="127.0.0.1", port=19876)
    server.start()

    try:
        time.sleep(0.05)
        with socket.create_connection(("127.0.0.1", 19876), timeout=1.0) as sock:
            sock.sendall(b"OI;")
            time.sleep(0.05)
            data = sock.recv(1024)
            assert b"7585B\r" in data
    finally:
        server.stop()


def test_byte_pacer():
    """Verify BytePacer math and timing calculations for various baud rates."""
    # 300 baud: 30 bytes/s -> 1 byte = 33.33ms, 3 bytes = 100ms
    pacer_300 = BytePacer(300)
    assert pacer_300.is_throttled is True
    assert pacer_300.bytes_per_sec == 30.0
    assert pacer_300.chunk_size == 3
    assert abs(pacer_300.delay_for_bytes(30) - 1.0) < 1e-6
    assert abs(pacer_300.delay_for_bytes(3) - 0.1) < 1e-6

    # 9600 baud: 960 bytes/s
    pacer_9600 = BytePacer(9600)
    assert pacer_9600.is_throttled is True
    assert pacer_9600.bytes_per_sec == 960.0
    assert abs(pacer_9600.delay_for_bytes(960) - 1.0) < 1e-6

    # 19200 baud
    pacer_19200 = BytePacer(19200)
    assert pacer_19200.is_throttled is True
    assert pacer_19200.bytes_per_sec == 1920.0

    # Unthrottled (None or 0)
    pacer_none = BytePacer(None)
    assert pacer_none.is_throttled is False
    assert pacer_none.delay_for_bytes(100) == 0.0
    assert pacer_none.chunk_size == 4096

    pacer_zero = BytePacer(0)
    assert pacer_zero.is_throttled is False
    assert pacer_zero.delay_for_bytes(100) == 0.0

    # Verify actual pacing sleep duration for a small byte count
    t0 = time.perf_counter()
    pacer_300.pace(3)  # 3 bytes at 300 baud = 100 ms
    elapsed = time.perf_counter() - t0
    assert 0.08 <= elapsed <= 0.20


def test_tcp_server_baudrate_pacing():
    """Verify that TcpServer paces inquiry responses according to baudrate."""
    plotter = VirtualPlotter(paper="A3")
    server = TcpServer(plotter, host="127.0.0.1", port=19877, baudrate=300)
    server.start()

    try:
        time.sleep(0.05)
        # At 300 baud (30 bytes/s), 6 bytes ("7585B\r") takes ~0.20 s
        with socket.create_connection(("127.0.0.1", 19877), timeout=2.0) as sock:
            t0 = time.perf_counter()
            sock.sendall(b"OI;")
            resp = b""
            while not resp.endswith(b"\r"):
                chunk = sock.recv(1024)
                if not chunk:
                    break
                resp += chunk
            elapsed = time.perf_counter() - t0

            assert resp == b"7585B\r"
            assert elapsed >= 0.08
    finally:
        server.stop()


def test_flow_control_buffer_watermarks():
    """Verify that VirtualPlotter sends XOFF at high-water mark and XON at low-water mark."""
    responses: list[bytes] = []
    plotter = VirtualPlotter(
        paper="A3",
        buffer_size=100,
        realtime=True,
        speedup=20.0,
        on_response=lambda resp: responses.append(resp),
    )
    try:
        # Feed enough bytes to cross 80-byte high water mark
        chunk = b"PU 0,0;\n" * 12  # 84 bytes
        plotter.receive_bytes(chunk)
        # Should have sent XOFF (0x13)
        assert b"\x13" in responses

        # Wait for realtime thread to drain below 40-byte low water mark
        deadline = time.time() + 2.0
        while b"\x11" not in responses and time.time() < deadline:
            time.sleep(0.02)
        assert b"\x11" in responses
    finally:
        plotter.stop()


def test_tcp_streamer_flow_control():
    """Verify SerialStreamer streaming over TCP respects emulator XON/XOFF flow control."""
    from plotter_studio.device.emitter import EmittedCommand
    from plotter_studio.device.streamer import SerialStreamer

    plotter = VirtualPlotter(paper="A3", buffer_size=100, realtime=True, speedup=50.0)
    server = TcpServer(plotter, host="127.0.0.1", port=19878)
    server.start()

    try:
        time.sleep(0.05)
        cmds = [
            EmittedCommand(hpgl=f"PD {i * 10},{i * 10};\n", step_index=i, pen=1, is_draw=True, dist_mm=5.0)
            for i in range(20)
        ]

        finished_box = [False, False]
        streamer = SerialStreamer(
            on_finished=lambda success, msg: finished_box.__setitem__(0, True) or finished_box.__setitem__(1, success),
        )
        streamer.start_stream("tcp://127.0.0.1:19878", cmds, xonxoff_userspace=True)

        deadline = time.time() + 3.0
        while not finished_box[0] and time.time() < deadline:
            time.sleep(0.05)

        assert finished_box[0] is True
        assert finished_box[1] is True
        assert plotter.stats.commands_executed >= 20
    finally:
        server.stop()


def test_tcp_streamer_large_buffer_backpressure():
    """Verify SerialStreamer over TCP triggers genuine XOFF/XON backpressure on a 1000-byte buffer."""
    from plotter_studio.device.emitter import EmittedCommand
    from plotter_studio.device.streamer import SerialStreamer, StreamerState

    events: list[tuple[str, dict]] = []
    plotter = VirtualPlotter(
        paper="A3",
        buffer_size=1000,
        realtime=True,
        speedup=50.0,
        flow_control=True,
        on_event=lambda ev, d: events.append((ev, d)),
    )
    server = TcpServer(plotter, host="127.0.0.1", port=19879)
    server.start()

    try:
        time.sleep(0.05)
        cmds = [
            EmittedCommand(hpgl=f"PA {i * 10},{i * 10};\n", step_index=i, pen=1, is_draw=True, dist_mm=5.0)
            for i in range(160)  # ~1.9 KB, well exceeding 1000 bytes
        ]

        statuses: list[StreamerState] = []
        finished_box = [False, False]
        streamer = SerialStreamer(
            on_status=lambda st, msg: statuses.append(st),
            on_finished=lambda success, msg: finished_box.__setitem__(0, True) or finished_box.__setitem__(1, success),
        )
        streamer.start_stream("tcp://127.0.0.1:19879", cmds, flow_control="xonxoff")

        deadline = time.time() + 5.0
        while not finished_box[0] and time.time() < deadline:
            time.sleep(0.05)

        assert finished_box[0] is True
        assert finished_box[1] is True
        # Verify that streamer was paused due to XOFF
        assert StreamerState.PAUSED in statuses
        # Verify that plotter fired flow_control events (XOFF and XON)
        fc_events = [ev for ev, d in events if ev == "flow_control"]
        assert len(fc_events) >= 2
    finally:
        server.stop()


