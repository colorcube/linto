"""Serial and TCP plot streaming worker.

Handles thread-safe transmission of HP-GL instructions to the plotter with
flow control, progress tracking, pause/resume and immediate abort.
"""

from __future__ import annotations

import logging
import select
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
        write_timeout: float = 5.0,
        end_settle_delay_s: float = 0.05,
    ):
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finished = on_finished
        self.write_timeout = write_timeout
        self.end_settle_delay_s = end_settle_delay_s

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
        return self.state in (
            StreamerState.CONNECTING,
            StreamerState.STREAMING,
            StreamerState.PAUSED,
            StreamerState.ABORTING,
        )

    def start_stream(
        self,
        port: str,
        commands: list[EmittedCommand],
        baudrate: int = 19200,
        inter_command_delay_s: float = 0.0,
        flow_control: str = "rtscts",
        xonxoff_userspace: Optional[bool] = None,
        rtscts: Optional[bool] = None,
        dsrdtr: Optional[bool] = None,
        write_timeout: Optional[float] = None,
        pause_on_pen_change: bool = False,
        end_settle_delay_s: Optional[float] = None,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
        sync_with_oa: bool = True,
    ) -> bool:
        """Start streaming commands in a background thread."""
        with self._lock:
            if self.is_active():
                return False

            self.state = StreamerState.CONNECTING
            self._abort_requested = False
            self._xoff_paused = False
            self._pause_event.set()

            eff_write_timeout = self.write_timeout if write_timeout is None else write_timeout
            eff_settle_delay = self.end_settle_delay_s if end_settle_delay_s is None else end_settle_delay_s

            self._thread = threading.Thread(
                target=self._run_stream,
                args=(
                    port,
                    commands,
                    baudrate,
                    inter_command_delay_s,
                    flow_control,
                    xonxoff_userspace,
                    rtscts,
                    dsrdtr,
                    eff_write_timeout,
                    pause_on_pen_change,
                    eff_settle_delay,
                    bytesize,
                    parity,
                    stopbits,
                    sync_with_oa,
                ),
                daemon=True,
                name="PlotStreamWorker",
            )
            self._thread.start()
            return True

    def is_user_paused(self) -> bool:
        return not self._pause_event.is_set()

    def pause(self) -> None:
        """Pause the current plot transmission (manual user pause)."""
        with self._lock:
            if self.is_active() and not self.is_user_paused():
                self.state = StreamerState.PAUSED
                self._pause_event.clear()
                self._emit_status(StreamerState.PAUSED, "Plot pausiert")

    def resume(self) -> None:
        """Resume transmission from manual user pause."""
        with self._lock:
            if self.is_user_paused():
                self._pause_event.set()
                new_state = StreamerState.PAUSED if self._xoff_paused else StreamerState.STREAMING
                msg = "Plotter-Puffer voll (XOFF) – warte auf Plotter..." if self._xoff_paused else "Plot fortgesetzt"
                self._emit_status(new_state, msg)

    def abort(self) -> None:
        """Immediately abort current plot job, flush host buffer, and lift pen."""
        with self._lock:
            if not self.is_active():
                return
            self.state = StreamerState.ABORTING
            self._abort_requested = True
            self._pause_event.set()  # Wake up if paused
            if self._serial and hasattr(self._serial, "reset_output_buffer"):
                try:
                    self._serial.reset_output_buffer()
                except Exception:
                    pass
            if self._serial and hasattr(self._serial, "cancel_write"):
                try:
                    self._serial.cancel_write()
                except Exception:
                    pass

    def _emit_status(self, state: StreamerState, msg: str) -> None:
        self.state = state
        if self.on_status:
            self.on_status(state, msg)

    def _send_raw(self, data: bytes) -> bool:
        """Send raw bytes, retrying cleanly if hardware CTS blocks longer than write_timeout.

        Returns True if all bytes were sent, False if aborted during transmission.
        """
        if self._socket:
            view = memoryview(data)
            sent = 0
            while sent < len(view):
                if self._abort_requested:
                    return False
                try:
                    n = self._socket.send(view[sent:])
                    if n <= 0:
                        raise ConnectionError("TCP-Verbindung geschlossen")
                    sent += n
                except socket.timeout:
                    if self._abort_requested:
                        return False
                    continue
            return True

        if self._serial:
            view = memoryview(data)
            sent = 0
            cts_stall_notified = False
            while sent < len(view):
                if self._abort_requested:
                    return False

                # Check CTS before writing if hardware handshake is active and cts property is readable
                if getattr(self._serial, "rtscts", False):
                    try:
                        cts_state = getattr(self._serial, "cts", True)
                    except Exception:
                        cts_state = True
                    if cts_state is False:
                        if not cts_stall_notified:
                            cts_stall_notified = True
                            self._emit_status(
                                StreamerState.PAUSED,
                                "Plotter-Puffer voll (CTS low) – warte auf Plotter...",
                            )
                        time.sleep(0.05)
                        continue

                try:
                    n = self._serial.write(bytes(view[sent:]))
                    if n is None:
                        n = len(view) - sent
                    sent += n
                    if cts_stall_notified and not self.is_user_paused():
                        cts_stall_notified = False
                        self._emit_status(StreamerState.STREAMING, "Sende Plotdaten...")
                except getattr(serial, "SerialTimeoutException", TimeoutError):
                    if self._abort_requested:
                        return False
                    if not cts_stall_notified:
                        cts_stall_notified = True
                        self._emit_status(
                            StreamerState.PAUSED,
                            "Plotter-Puffer voll (Write-Timeout) – warte auf Plotter...",
                        )
                    time.sleep(0.05)
                    continue
            return True

        return True

    def _sync_plotter_ready(self, timeout_s: float = 2.0) -> bool:
        """Send OA; inquiry and wait for plotter response to ensure buffer is drained up to this point.

        Because the plotter executes OA; in-order from its command buffer, receiving the
        'x,y,p\\r' reply guarantees all preceding drawing motions have completed mechanically.
        """
        if self._abort_requested:
            return False

        try:
            if self._serial and hasattr(self._serial, "read"):
                if hasattr(self._serial, "reset_input_buffer"):
                    self._serial.reset_input_buffer()
                if not self._send_raw(b"OA;\r"):
                    return False
                if hasattr(self._serial, "flush"):
                    self._serial.flush()
                deadline = time.monotonic() + timeout_s
                buf = bytearray()
                while time.monotonic() < deadline and not self._abort_requested:
                    waiting = getattr(self._serial, "in_waiting", 0)
                    chunk = self._serial.read(waiting if waiting and waiting > 0 else 1)
                    if chunk:
                        buf.extend(chunk)
                        if b"\r" in buf or b"\n" in buf:
                            return True
                    else:
                        time.sleep(0.02)
                return False

            if self._socket:
                if not self._send_raw(b"OA;\r"):
                    return False
                deadline = time.monotonic() + timeout_s
                buf = bytearray()
                while time.monotonic() < deadline and not self._abort_requested:
                    r, _, _ = select.select([self._socket], [], [], 0.05)
                    if r:
                        chunk = self._socket.recv(256)
                        if not chunk:
                            break
                        buf.extend(chunk)
                        if b"\r" in buf or b"\n" in buf:
                            return True
                return False
        except Exception as e:
            logger.debug(f"OA; sync skipped or timed out: {e}")
        return False

    def _execute_abort_sequence(self) -> None:
        """Flush host output buffer, send ESC.K and lift/park pen immediately."""
        self._emit_status(StreamerState.ABORTING, "Sende Abbruch-Befehl...")
        try:
            if self._serial:
                if hasattr(self._serial, "reset_output_buffer"):
                    try:
                        self._serial.reset_output_buffer()
                    except Exception:
                        pass
                # Temporarily disable rtscts stall if CTS is low so ESC.K goes out immediately
                orig_rtscts = getattr(self._serial, "rtscts", False)
                try:
                    if orig_rtscts:
                        self._serial.rtscts = False
                except Exception:
                    pass
                try:
                    self._serial.write(b"\x1b.K\rPU;SP0;\r\n")
                    if hasattr(self._serial, "flush"):
                        self._serial.flush()
                except Exception:
                    pass
            elif self._socket:
                try:
                    self._socket.sendall(b"\x1b.K\rPU;SP0;\r\n")
                except Exception:
                    pass
        except Exception:
            pass
        self._close_connection()
        self._emit_status(StreamerState.IDLE, "Plot abgebrochen")
        if self.on_finished:
            self.on_finished(False, "Plot durch Benutzer abgebrochen")

    def _check_and_wait_xoff(self) -> None:
        """Process incoming bytes for XON / XOFF flow control (Serial or TCP)."""
        if not self._serial and not self._socket:
            return

        while not self._abort_requested:
            try:
                raw = b""
                if self._serial:
                    available = getattr(self._serial, "in_waiting", 0)
                    if available and available > 0:
                        raw = self._serial.read(available)
                elif self._socket:
                    r, _, _ = select.select([self._socket], [], [], 0)
                    if r:
                        raw = self._socket.recv(4096)

                if raw:
                    for b in raw:
                        if b == XOFF:
                            logger.info("Plotter sent XOFF (0x13) - pausing send")
                            self._xoff_paused = True
                            self._emit_status(StreamerState.PAUSED, "Plotter-Puffer voll (XOFF) – warte auf Plotter...")
                        elif b == XON:
                            logger.info("Plotter sent XON (0x11) - resuming send")
                            self._xoff_paused = False
                            self._emit_status(StreamerState.STREAMING, "Sende Plotdaten (XON)...")
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
        flow_control: str = "rtscts",
        xonxoff_userspace: Optional[bool] = None,
        rtscts: Optional[bool] = None,
        dsrdtr: Optional[bool] = None,
        write_timeout: float = 5.0,
        pause_on_pen_change: bool = False,
        end_settle_delay_s: float = 0.05,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
        sync_with_oa: bool = False,
    ) -> None:
        port_clean = port.strip()
        total_commands = len(commands)
        drawn_total_mm = 0.0

        fc = (flow_control or "rtscts").lower()
        effective_rtscts = (fc == "rtscts") if rtscts is None else bool(rtscts)
        effective_dsrdtr = (fc == "dsrdtr") if dsrdtr is None else bool(dsrdtr)
        effective_xonxoff = (fc == "xonxoff") if xonxoff_userspace is None else bool(xonxoff_userspace)

        parity_map = {
            "N": serial.PARITY_NONE,
            "NONE": serial.PARITY_NONE,
            "E": serial.PARITY_EVEN,
            "EVEN": serial.PARITY_EVEN,
            "O": serial.PARITY_ODD,
            "ODD": serial.PARITY_ODD,
        }
        ser_parity = parity_map.get(str(parity).upper(), serial.PARITY_NONE)
        ser_bytesize = serial.SEVENBITS if int(bytesize) == 7 else serial.EIGHTBITS
        ser_stopbits = serial.STOPBITS_TWO if float(stopbits) == 2 else serial.STOPBITS_ONE

        self._emit_status(StreamerState.CONNECTING, f"Verbinde mit {port_clean}...")

        try:
            if port_clean.startswith("tcp://"):
                if fc != "none" and xonxoff_userspace is not False:
                    effective_xonxoff = True
                host_port = port_clean[6:].split(":")
                host = host_port[0]
                tcp_port = int(host_port[1]) if len(host_port) > 1 else 9999
                self._socket = socket.create_connection((host, tcp_port), timeout=3.0)
                self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self._socket.settimeout(2.0)
            else:
                self._serial = serial.Serial(
                    port=port_clean,
                    baudrate=baudrate,
                    bytesize=ser_bytesize,
                    parity=ser_parity,
                    stopbits=ser_stopbits,
                    rtscts=effective_rtscts,
                    dsrdtr=effective_dsrdtr,
                    xonxoff=False,
                    timeout=0.1 if effective_xonxoff else 0.2,
                    write_timeout=write_timeout,
                )
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

            self._emit_status(StreamerState.STREAMING, "Sende Plotdaten...")
            active_pen: Optional[int] = None

            for i, cmd in enumerate(commands):
                # Automatic pause before pen change (SPn; where n > 0 after first pen)
                hpgl_stripped = cmd.hpgl.lstrip()
                is_pen_select = hpgl_stripped.startswith("SP") and not hpgl_stripped.startswith("SP0") and cmd.pen > 0
                if is_pen_select:
                    if pause_on_pen_change and active_pen is not None and cmd.pen != active_pen:
                        # Synchronize with plotter buffer via OA; before prompting user to swap pens
                        if sync_with_oa:
                            self._sync_plotter_ready(timeout_s=5.0)
                        with self._lock:
                            if not self._abort_requested:
                                self.state = StreamerState.PAUSED
                                self._pause_event.clear()
                                self._emit_status(
                                    StreamerState.PAUSED,
                                    f"Stiftwechsel auf SP{cmd.pen} – Bitte Stift wechseln und Fortsetzen klicken",
                                )
                    active_pen = cmd.pen

                # Wait if paused (manual or pen-change pause)
                self._pause_event.wait()

                # Check for abort (before or after pause)
                if self._abort_requested:
                    self._execute_abort_sequence()
                    return

                # Flow control check (userspace XON/XOFF)
                if effective_xonxoff:
                    self._check_and_wait_xoff()
                    if self._abort_requested:
                        self._execute_abort_sequence()
                        return

                if inter_command_delay_s > 0.0:
                    time.sleep(inter_command_delay_s)

                # Send command bytes
                sent_ok = self._send_raw(cmd.hpgl.encode("ascii", errors="replace"))
                if not sent_ok or self._abort_requested:
                    self._execute_abort_sequence()
                    return

                if cmd.is_draw:
                    drawn_total_mm += cmd.dist_mm

                # Emit progress
                pct = ((i + 1) / total_commands) * 100.0 if total_commands > 0 else 100.0
                if self.on_progress:
                    self.on_progress(cmd.step_index, total_commands, pct, cmd.pen, drawn_total_mm / 1000.0)

            # Allow plotter to finish mechanical SP0; pen parking before closing serial port
            if self._serial and hasattr(self._serial, "flush"):
                try:
                    self._serial.flush()
                except Exception:
                    pass
            if sync_with_oa and total_commands > 0 and not self._abort_requested:
                self._sync_plotter_ready(timeout_s=2.0)
            if end_settle_delay_s > 0.0 and not self._abort_requested:
                time.sleep(end_settle_delay_s)

            if self._abort_requested:
                self._execute_abort_sequence()
                return

            # Successfully completed
            self._close_connection()
            self._emit_status(StreamerState.COMPLETED, "Plot erfolgreich abgeschlossen")
            if self.on_finished:
                self.on_finished(True, "Plot erfolgreich abgeschlossen")

        except Exception as e:
            if self._abort_requested:
                self._execute_abort_sequence()
                return
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

