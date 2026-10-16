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

    # 6. Hard-clip window for A3 with EXP margins (390 x 287 mm)
    # 390 * 40 / 2 = 7800, 287 * 40 / 2 = 5740
    plotter.receive_bytes(b"OH;")
    assert responses.pop(0) == b"-7800,-5740,7800,5740\r"

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
    """Verify that TcpServer throttles incoming data according to baudrate."""
    plotter = VirtualPlotter(paper="A3", baudrate=2400)
    server = TcpServer(plotter, host="127.0.0.1", port=19877)
    server.start()

    try:
        time.sleep(0.05)
        # 2400 baud = 240 bytes/s -> 48 bytes takes ~0.20 s
        payload = b"IN; SP1; PU 0,0; PD 100,100; PU; SP0;\r"  # 37 bytes
        with socket.create_connection(("127.0.0.1", 19877), timeout=2.0) as sock:
            t0 = time.perf_counter()
            sock.sendall(payload)
            # Wait for plotter to process incoming data
            deadline = time.time() + 2.0
            while plotter.stats.bytes_received < len(payload) and time.time() < deadline:
                time.sleep(0.02)
            elapsed = time.perf_counter() - t0

            # 37 bytes at 2400 baud (240 bytes/s) takes ~0.154 s
            assert plotter.stats.bytes_received == len(payload)
            assert elapsed >= 0.10
    finally:
        server.stop()

