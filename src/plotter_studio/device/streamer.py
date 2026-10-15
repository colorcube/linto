"""Serial and TCP plot streaming worker.

Handles thread-safe transmission of HP-GL instructions to the plotter with
flow control, progress tracking, pause/resume and immediate abort.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from enum import Enum
from typing import Callable, Optional

import serial

from .emitter import EmittedCommand

logger = logging.getLogger("plotter_studio.device.streamer")


XON = 0x11
XOFF = 0x13


class StreamerState(str, Enum):
    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    STREAMING = "STREAMING"
    PAUSED = "PAUSED"
    ABORTING = "ABORTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class SerialStreamer:
    """Background worker that streams HP-GL commands to a serial or TCP port."""

    def __init__(
        self,
        on_progress: Optional[Callable[[int, int, float, int, float], None]] = None,
        on_status: Optional[Callable[[StreamerState, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None,
    ):
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finished = on_finished

        self.state = StreamerState.IDLE
        self._thread: Optional[threading.Thread] = None

        self._pause_event = threading.Event()
        self._pause_event.set()  # Unpaused by default
        self._abort_requested = False
        self._xoff_paused = False

        self._serial: Optional[serial.Serial] = None
        self._socket: Optional[socket.socket] = None

        self._lock = threading.Lock()

    def is_active(self) -> bool:
        return self.state in (StreamerState.CONNECTING, StreamerState.STREAMING, StreamerState.PAUSED)

    def start_stream(
        self,
        port: str,
        commands: list[EmittedCommand],
        baudrate: int = 19200,
        inter_command_delay_s: float = 0.0,
        xonxoff_userspace: bool = True,
        rtscts: bool = True,
    ) -> bool:
        """Start streaming commands in a background thread."""
        with self._lock:
            if self.is_active():
                return False

            self.state = StreamerState.CONNECTING
            self._abort_requested = False
            self._xoff_paused = False
            self._pause_event.set()

            self._thread = threading.Thread(
                target=self._run_stream,
                args=(port, commands, baudrate, inter_command_delay_s, xonxoff_userspace, rtscts),
                daemon=True,
                name="PlotStreamWorker",
            )
            self._thread.start()
            return True

    def pause(self) -> None:
        """Pause the current plot transmission."""
        with self._lock:
            if self.state == StreamerState.STREAMING:
                self.state = StreamerState.PAUSED
                self._pause_event.clear()
                self._emit_status(StreamerState.PAUSED, "Plot pausiert")

    def resume(self) -> None:
        """Resume transmission from pause."""
        with self._lock:
            if self.state == StreamerState.PAUSED:
                self.state = StreamerState.STREAMING
                self._pause_event.set()
                self._emit_status(StreamerState.STREAMING, "Plot fortgesetzt")

    def abort(self) -> None:
        """Immediately abort current plot job and lift pen."""
        with self._lock:
            if not self.is_active():
                return
            self.state = StreamerState.ABORTING
            self._abort_requested = True
            self._pause_event.set()  # Wake up if paused

    def _emit_status(self, state: StreamerState, msg: str) -> None:
        self.state = state
        if self.on_status:
            self.on_status(state, msg)

    def _send_raw(self, data: bytes) -> None:
        if self._socket:
            self._socket.sendall(data)
        elif self._serial:
            self._serial.write(data)

    def _check_and_wait_xoff(self) -> None:
        """Process incoming bytes for XON / XOFF flow control."""
        if not self._serial:
            return

        while not self._abort_requested:
            try:
                available = self._serial.in_waiting
                if available > 0:
                    raw = self._serial.read(available)
                    for b in raw:
                        if b == XOFF:
                            logger.debug("Plotter sent XOFF (0x13) - pausing send")
                            self._xoff_paused = True
                        elif b == XON:
                            logger.debug("Plotter sent XON (0x11) - resuming send")
                            self._xoff_paused = False
            except Exception as e:
                logger.warning(f"Error checking flow control: {e}")
                break

            if not self._xoff_paused:
                break
            time.sleep(0.02)

    def _run_stream(
        self,
        port: str,
        commands: list[EmittedCommand],
        baudrate: int,
        inter_command_delay_s: float = 0.0,
        xonxoff_userspace: bool = True,
        rtscts: bool = True,
    ) -> None:
        port_clean = port.strip()
        total_commands = len(commands)
        drawn_total_mm = 0.0

        self._emit_status(StreamerState.CONNECTING, f"Verbinde mit {port_clean}...")

        try:
            if port_clean.startswith("tcp://"):
                host_port = port_clean[6:].split(":")
                host = host_port[0]
                tcp_port = int(host_port[1]) if len(host_port) > 1 else 9999
                self._socket = socket.create_connection((host, tcp_port), timeout=3.0)
                self._socket.settimeout(2.0)
            else:
                self._serial = serial.Serial(
                    port=port_clean,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    rtscts=rtscts,
                    xonxoff=False,
                    timeout=0.1 if xonxoff_userspace else 2.0,
                )
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

            self._emit_status(StreamerState.STREAMING, "Sende Plotdaten...")

            for i, cmd in enumerate(commands):
                # Check for abort
                if self._abort_requested:
                    self._emit_status(StreamerState.ABORTING, "Sende Abbruch-Befehl...")
                    try:
                        self._send_raw(b"\x1b.K\rPU;SP0;\r\n")
                    except Exception:
                        pass
                    self._close_connection()
                    self._emit_status(StreamerState.IDLE, "Plot abgebrochen")
                    if self.on_finished:
                        self.on_finished(False, "Plot durch Benutzer abgebrochen")
                    return

                # Wait if paused
                self._pause_event.wait()

                # Flow control check (userspace XON/XOFF)
                if xonxoff_userspace:
                    self._check_and_wait_xoff()
                    if self._abort_requested:
                        continue

                if inter_command_delay_s > 0.0:
                    time.sleep(inter_command_delay_s)

                # Send command bytes
                self._send_raw(cmd.hpgl.encode("ascii", errors="replace"))

                if cmd.is_draw:
                    drawn_total_mm += cmd.dist_mm

                # Emit progress
                pct = ((i + 1) / total_commands) * 100.0 if total_commands > 0 else 100.0
                if self.on_progress:
                    self.on_progress(cmd.step_index, total_commands, pct, cmd.pen, drawn_total_mm / 1000.0)

            # Successfully completed
            self._close_connection()
            self._emit_status(StreamerState.COMPLETED, "Plot erfolgreich abgeschlossen")
            if self.on_finished:
                self.on_finished(True, "Plot erfolgreich abgeschlossen")

        except Exception as e:
            logger.error(f"Streamer exception: {e}")
            self._close_connection()
            self._emit_status(StreamerState.ERROR, f"Übertragungsfehler: {e}")
            if self.on_finished:
                self.on_finished(False, f"Fehler: {e}")

    def _close_connection(self) -> None:
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

