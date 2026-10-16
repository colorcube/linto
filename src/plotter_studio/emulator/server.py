"""PTY and TCP server for Virtual Plotter.

Provides a virtual serial port (/dev/pts/X or symlink) or TCP socket that
applications (plotd, pyserial, InkCut, MutohPlot) can connect to.
"""

from __future__ import annotations

import logging
import os
import pty
import select
import socket
import termios
import threading
import time
from pathlib import Path
from typing import Optional

from .virtual_plotter import VirtualPlotter

logger = logging.getLogger("plotter_studio.emulator")


class BytePacer:
    """Calculates transmission pacing delays for serial baud rates (8N1).

    8N1 framing: 1 start bit + 8 data bits + 1 stop bit = 10 bits per character.
    Examples:
    - 300 baud: 30 bytes/s -> ~33.3 ms per byte
    - 1200 baud: 120 bytes/s -> ~8.3 ms per byte
    - 9600 baud: 960 bytes/s -> ~1.04 ms per byte
    - 19200 baud: 1920 bytes/s -> ~0.52 ms per byte
    """

    def __init__(self, baudrate: Optional[int] = None):
        self.baudrate = int(baudrate) if (baudrate is not None and int(baudrate) > 0) else None

    @property
    def is_throttled(self) -> bool:
        return self.baudrate is not None and self.baudrate > 0

    @property
    def bytes_per_sec(self) -> float:
        if not self.is_throttled or not self.baudrate:
            return float("inf")
        return self.baudrate / 10.0

    @property
    def chunk_size(self) -> int:
        """Target chunk size to balance realistic pacing with system call overhead (~20-100 ms)."""
        if not self.is_throttled or not self.baudrate:
            return 4096
        # At 300 baud: 30 bytes/s -> chunk of 1 to 3 bytes (33-100 ms)
        # At 19200 baud: 1920 bytes/s -> chunk of 96-128 bytes
        return max(1, min(128, int(self.baudrate / 100)))

    def delay_for_bytes(self, byte_count: int) -> float:
        """Return delay in seconds for given number of bytes at configured baud rate."""
        if not self.is_throttled or not self.baudrate or byte_count <= 0:
            return 0.0
        return (byte_count * 10.0) / self.baudrate

    def pace(self, byte_count: int) -> None:
        """Sleep for the duration required to transmit byte_count bytes."""
        d = self.delay_for_bytes(byte_count)
        if d > 0.0:
            time.sleep(d)


class PtyServer:
    """Provides a virtual serial port using a Linux pseudoterminal (PTY)."""

    def __init__(
        self,
        plotter: VirtualPlotter,
        symlink_path: Optional[str | Path] = None,
        baudrate: Optional[int] = None,
    ):
        self.plotter = plotter
        self.symlink_path = Path(symlink_path).resolve() if symlink_path else None
        self.baudrate = baudrate if baudrate is not None else getattr(plotter, "baudrate", None)
        self.pacer = BytePacer(self.baudrate)

        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.slave_path: str = ""

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._out_queue: list[bytes] = []
        self._queue_lock = threading.Lock()

        # Connect plotter responses to our outgoing queue
        self.plotter.on_response = self._enqueue_response

    def _enqueue_response(self, data: bytes) -> None:
        with self._queue_lock:
            if data in (b"\x13", b"\x11") and self.master_fd is not None:
                try:
                    os.write(self.master_fd, data)
                    return
                except OSError:
                    pass
            self._out_queue.append(data)

    def start(self) -> str:
        """Start the PTY server and return the slave device path."""
        if self._running:
            return self.slave_path

        self.master_fd, self.slave_fd = pty.openpty()
        self.slave_path = os.ttyname(self.slave_fd)

        # Configure slave PTY in raw mode (no echo, no translation)
        self._set_raw_mode(self.slave_fd)

        # Make master non-blocking
        os.set_blocking(self.master_fd, False)

        # Create symlink if requested
        if self.symlink_path:
            try:
                if self.symlink_path.is_symlink() or self.symlink_path.exists():
                    self.symlink_path.unlink()
                self.symlink_path.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(self.slave_path, self.symlink_path)
                logger.info(f"Created symlink: {self.symlink_path} -> {self.slave_path}")
            except Exception as e:
                logger.warning(f"Could not create symlink {self.symlink_path}: {e}")

        self._running = True
        self._thread = threading.Thread(target=self._io_loop, daemon=True, name="PtyEmulatorLoop")
        self._thread.start()

        return str(self.symlink_path) if self.symlink_path else self.slave_path

    def _set_raw_mode(self, fd: int) -> None:
        attrs = termios.tcgetattr(fd)
        # Input modes: no break, no CR to NL, no parity, no strip, no flow control translation
        attrs[0] = attrs[0] & ~(termios.IGNBRK | termios.BRKINT | termios.PARMRK |
                                termios.ISTRIP | termios.INLCR | termios.IGNCR |
                                termios.ICRNL | termios.IXON | termios.IXOFF)
        # Output modes: no post-processing
        attrs[1] = attrs[1] & ~termios.OPOST
        # Local modes: no echo, no canonical (line-by-line), no extended input, no signals (SIGINT, etc.)
        attrs[3] = attrs[3] & ~(termios.ECHO | termios.ECHONL | termios.ICANON |
                                termios.ISIG | termios.IEXTEN)
        # Control modes: 8-bit, enable receiver
        attrs[2] = (attrs[2] & ~(termios.CSIZE | termios.PARENB)) | termios.CS8 | termios.CREAD

        termios.tcsetattr(fd, termios.TCSANOW, attrs)

    def _io_loop(self) -> None:
        assert self.master_fd is not None

        while self._running:
            try:
                # Write any queued responses first (paced according to baudrate)
                with self._queue_lock:
                    pending = list(self._out_queue)
                    self._out_queue.clear()

                for chunk in pending:
                    offset = 0
                    while offset < len(chunk) and self._running:
                        piece = chunk[offset : offset + self.pacer.chunk_size]
                        try:
                            os.write(self.master_fd, piece)
                        except (BlockingIOError, OSError):
                            pass
                        self.pacer.pace(len(piece))
                        offset += len(piece)

                # Wait for incoming data with timeout
                timeout = 0.01 if self.pacer.is_throttled else 0.02
                r, _, _ = select.select([self.master_fd], [], [], timeout)
                if r and self._running:
                    try:
                        data = os.read(self.master_fd, 1024)
                        if data:
                            self.plotter.receive_bytes(data)
                    except (BlockingIOError, OSError):
                        pass
            except Exception as e:
                if self._running:
                    logger.debug(f"PtyServer read loop exception: {e}")
                break

    def stop(self) -> None:
        """Stop PTY loop and close all file descriptors."""
        self._running = False
        self.plotter.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        if self.slave_fd is not None:
            try:
                os.close(self.slave_fd)
            except OSError:
                pass
            self.slave_fd = None

        if self.symlink_path and (self.symlink_path.is_symlink() or self.symlink_path.exists()):
            try:
                self.symlink_path.unlink()
            except OSError:
                pass


class TcpServer:
    """Provides a virtual serial-over-TCP port."""

    def __init__(
        self,
        plotter: VirtualPlotter,
        host: str = "127.0.0.1",
        port: int = 9999,
        baudrate: Optional[int] = None,
    ):
        self.plotter = plotter
        self.host = host
        self.port = port
        self.baudrate = baudrate if baudrate is not None else getattr(plotter, "baudrate", None)
        self.pacer = BytePacer(self.baudrate)
        self._server_sock: Optional[socket.socket] = None
        self._client_sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._queue_lock = threading.Lock()

        self.plotter.on_response = self._send_tcp_response

    def _send_tcp_response(self, data: bytes) -> None:
        with self._queue_lock:
            if self._client_sock:
                try:
                    if data in (b"\x13", b"\x11"):
                        self._client_sock.sendall(data)
                        return
                    offset = 0
                    while offset < len(data) and self._running:
                        piece = data[offset : offset + self.pacer.chunk_size]
                        self._client_sock.sendall(piece)
                        self.pacer.pace(len(piece))
                        offset += len(piece)
                except OSError:
                    self._client_sock = None

    def start(self) -> str:
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(1)
        self._server_sock.settimeout(0.2)

        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True, name="TcpEmulatorLoop")
        self._thread.start()
        return f"tcp://{self.host}:{self.port}"

    def _accept_loop(self) -> None:
        assert self._server_sock is not None
        while self._running:
            try:
                client, addr = self._server_sock.accept()
                self._client_sock = client
                self._client_sock.settimeout(0.1)
                logger.info(f"TCP client connected from {addr}")

                while self._running and self._client_sock:
                    try:
                        data = self._client_sock.recv(1024)
                        if not data:
                            break
                        self.plotter.receive_bytes(data)
                    except socket.timeout:
                        continue
                    except OSError:
                        break

                if self._client_sock:
                    try:
                        self._client_sock.close()
                    except OSError:
                        pass
                    self._client_sock = None
            except socket.timeout:
                continue
            except OSError:
                break

    def stop(self) -> None:
        self._running = False
        self.plotter.stop()
        if self._client_sock:
            try:
                self._client_sock.close()
            except OSError:
                pass
            self._client_sock = None

        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

