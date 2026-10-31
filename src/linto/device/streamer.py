"""Serial and TCP plot streaming worker with pluggable Transport abstraction.

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

logger = logging.getLogger("linto.device.streamer")


XON = 0x11
XOFF = 0x13

_PARITY_MAP = {
    "N": serial.PARITY_NONE,
    "NONE": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "EVEN": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
    "ODD": serial.PARITY_ODD,
}


def parse_tcp_address(port: str, default_port: int = 9999) -> tuple[str, int]:
    """Parse a 'tcp://host[:port]' string into (host, tcp_port)."""
    raw = port.strip()
    if raw.startswith("tcp://"):
        raw = raw[6:]
    host_port = raw.split(":")
    host = host_port[0] or "127.0.0.1"
    tcp_port = int(host_port[1]) if len(host_port) > 1 and host_port[1] else default_port
    return host, tcp_port


def resolve_serial_framing(
    bytesize: int = 8,
    parity: str = "N",
    stopbits: float = 1,
) -> tuple[int, str, float]:
    """Convert numeric/string framing parameters to pyserial constants."""
    ser_parity = _PARITY_MAP.get(str(parity).upper(), serial.PARITY_NONE)
    ser_bytesize = serial.SEVENBITS if int(bytesize) == 7 else serial.EIGHTBITS
    ser_stopbits = serial.STOPBITS_TWO if float(stopbits) == 2 else serial.STOPBITS_ONE
    return ser_bytesize, ser_parity, ser_stopbits


class Transport:
    """Abstract byte transport interface for serial, TCP, or fake test connections."""

    def open(self) -> None:
        raise NotImplementedError

    def write(self, data: bytes) -> int:
        raise NotImplementedError

    def read_available(self) -> bytes:
        raise NotImplementedError

    def read_some(self, max_bytes: int = 128, timeout_s: float = 0.05) -> bytes:
        return self.read_available()

    def reset_input(self) -> None:
        pass

    def discard_output(self) -> None:
        pass

    def drain(self) -> None:
        pass

    def close(self) -> None:
        pass

    def is_cts_low(self) -> bool:
        return False

    def disable_hardware_flow_control(self) -> None:
        pass

    def can_sync_oa(self) -> bool:
        return True


class SerialTransport(Transport):
    """pyserial-backed Transport."""

    def __init__(
        self,
        port: str,
        baudrate: int = 19200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: float = 1,
        rtscts: bool = True,
        dsrdtr: bool = False,
        timeout: float = 0.2,
        write_timeout: float = 5.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.bytesize, self.parity, self.stopbits = resolve_serial_framing(bytesize, parity, stopbits)
        self.rtscts = rtscts
        self.dsrdtr = dsrdtr
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.ser: Optional[serial.Serial] = None

    def open(self) -> None:
        kwargs = dict(
            port=self.port,
            baudrate=self.baudrate,
            bytesize=self.bytesize,
            parity=self.parity,
            stopbits=self.stopbits,
            rtscts=self.rtscts,
            dsrdtr=self.dsrdtr,
            xonxoff=False,
            timeout=self.timeout,
            write_timeout=self.write_timeout,
        )
        try:
            self.ser = serial.Serial(**kwargs, exclusive=True)
        except (TypeError, ValueError):
            self.ser = serial.Serial(**kwargs)
        except (serial.SerialException, OSError) as exc:
            # Some virtual PTYs do not support TIOCEXCL (exclusive=True); retry without exclusive if errno is ENOTTY/EINVAL
            err_str = str(exc).lower()
            if "exclusive" in err_str or "inappropriate ioctl" in err_str or getattr(exc, "errno", None) in (22, 25):
                self.ser = serial.Serial(**kwargs)
            else:
                raise
        self.reset_input()
        self.discard_output()

    def write(self, data: bytes) -> int:
        if not self.ser:
            return 0
        n = self.ser.write(data)
        return len(data) if n is None else int(n)

    def read_available(self) -> bytes:
        if not self.ser:
            return b""
        available = getattr(self.ser, "in_waiting", 0)
        if available and available > 0:
            return self.ser.read(available)
        return b""

    def read_some(self, max_bytes: int = 128, timeout_s: float = 0.05) -> bytes:
        if not self.ser or not hasattr(self.ser, "read"):
            return b""
        waiting = getattr(self.ser, "in_waiting", 0)
        chunk = self.ser.read(waiting if waiting and waiting > 0 else 1)
        if not chunk and timeout_s > 0:
            time.sleep(min(timeout_s, 0.02))
        return chunk or b""

    def can_sync_oa(self) -> bool:
        return bool(self.ser and hasattr(self.ser, "read"))

    def reset_input(self) -> None:
        if self.ser and hasattr(self.ser, "reset_input_buffer"):
            try:
                self.ser.reset_input_buffer()
            except Exception:
                pass

    def discard_output(self) -> None:
        if self.ser and hasattr(self.ser, "reset_output_buffer"):
            try:
                self.ser.reset_output_buffer()
            except Exception:
                pass
        if self.ser and hasattr(self.ser, "cancel_write"):
            try:
                self.ser.cancel_write()
            except Exception:
                pass

    def drain(self) -> None:
        if self.ser and hasattr(self.ser, "flush"):
            try:
                self.ser.flush()
            except Exception:
                pass

    def close(self) -> None:
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def is_cts_low(self) -> bool:
        if self.ser and getattr(self.ser, "rtscts", False):
            try:
                return getattr(self.ser, "cts", True) is False
            except Exception:
                return False
        return False

    def disable_hardware_flow_control(self) -> None:
        if self.ser and getattr(self.ser, "rtscts", False):
            try:
                self.ser.rtscts = False
            except Exception:
                pass


class TcpTransport(Transport):
    """TCP socket-backed Transport."""

    def __init__(self, port: str, connect_timeout: float = 3.0, write_timeout: float = 2.0):
        self.host, self.tcp_port = parse_tcp_address(port)
        self.connect_timeout = connect_timeout
        self.write_timeout = write_timeout
        self.sock: Optional[socket.socket] = None

    def open(self) -> None:
        self.sock = socket.create_connection((self.host, self.tcp_port), timeout=self.connect_timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(self.write_timeout)

    def write(self, data: bytes) -> int:
        if not self.sock:
            return 0
        n = self.sock.send(data)
        if n <= 0:
            raise ConnectionError("TCP-Verbindung geschlossen")
        return n

    def read_available(self) -> bytes:
        if not self.sock:
            return b""
        r, _, _ = select.select([self.sock], [], [], 0)
        if r:
            return self.sock.recv(4096)
        return b""

    def read_some(self, max_bytes: int = 256, timeout_s: float = 0.05) -> bytes:
        if not self.sock:
            return b""
        r, _, _ = select.select([self.sock], [], [], timeout_s)
        if r:
            return self.sock.recv(max_bytes)
        return b""

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class StreamerState(str, Enum):
    IDLE = "IDLE"
    CONNECTING = "CONNECTING"
    STREAMING = "STREAMING"
    PAUSED = "PAUSED"
    ABORTING = "ABORTING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class SerialStreamer:
    """Background worker that streams HP-GL commands to a serial, TCP, or custom Transport."""

    def __init__(
        self,
        on_progress: Optional[Callable[[int, int, float, int, float], None]] = None,
        on_status: Optional[Callable[[StreamerState, str], None]] = None,
        on_finished: Optional[Callable[[bool, str], None]] = None,
        on_trace: Optional[Callable[[str, bytes], None]] = None,
        write_timeout: float = 5.0,
        end_settle_delay_s: float = 0.05,
        transport: Optional[Transport] = None,
        max_trace_entries: int = 2000,
    ):
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finished = on_finished
        self.on_trace = on_trace
        self.write_timeout = write_timeout
        self.end_settle_delay_s = end_settle_delay_s
        self._injected_transport = transport
        self.max_trace_entries = max(100, max_trace_entries)

        self._lock = threading.RLock()
        self._state = StreamerState.IDLE
        self._thread: Optional[threading.Thread] = None

        self._pause_event = threading.Event()
        self._pause_event.set()  # Unpaused by default
        self._abort_requested = False
        self._xoff_paused = False

        self._transport: Optional[Transport] = None
        self._serial: Optional[serial.Serial] = None
        self._socket: Optional[socket.socket] = None
        self._trace_log: list[str] = []
        self.last_completed_step_index: int = 0

    def _record_trace(self, direction: str, data: bytes) -> None:
        if not data:
            return
        text_repr = data.decode("ascii", errors="replace").replace("\r", "\\r").replace("\n", "\\n").replace("\x1b", "<ESC>")
        ts = time.strftime("%H:%M:%S")
        entry = f"[{ts}] {direction}: {text_repr}"
        with self._lock:
            self._trace_log.append(entry)
            if len(self._trace_log) > self.max_trace_entries:
                del self._trace_log[: len(self._trace_log) - self.max_trace_entries]
            cb = self.on_trace
        if cb:
            try:
                cb(direction, data)
            except Exception:
                pass

    def get_trace_log(self) -> list[str]:
        with self._lock:
            return list(self._trace_log)

    def clear_trace_log(self) -> None:
        with self._lock:
            self._trace_log.clear()

    @property
    def state(self) -> StreamerState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, value: StreamerState) -> None:
        with self._lock:
            self._state = value

    def is_active(self) -> bool:
        with self._lock:
            return self._state in (
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
        transport: Optional[Transport] = None,
        start_step_index: int = 0,
    ) -> bool:
        """Start streaming commands in a background thread."""
        with self._lock:
            if self.is_active():
                return False

            self._state = StreamerState.CONNECTING
            self._abort_requested = False
            self._xoff_paused = False
            self._pause_event.set()
            self.last_completed_step_index = max(0, int(start_step_index))

            eff_write_timeout = self.write_timeout if write_timeout is None else write_timeout
            eff_settle_delay = self.end_settle_delay_s if end_settle_delay_s is None else end_settle_delay_s
            eff_transport = transport or self._injected_transport

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
                    eff_transport,
                    max(0, int(start_step_index)),
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
        should_emit = False
        with self._lock:
            if self.is_active() and not self.is_user_paused():
                self._state = StreamerState.PAUSED
                self._pause_event.clear()
                should_emit = True
        if should_emit:
            self._emit_status(StreamerState.PAUSED, "Plot pausiert")

    def resume(self) -> None:
        """Resume transmission from manual user pause."""
        new_state: Optional[StreamerState] = None
        msg = ""
        with self._lock:
            if self.is_user_paused():
                self._pause_event.set()
                new_state = StreamerState.PAUSED if self._xoff_paused else StreamerState.STREAMING
                self._state = new_state
                msg = "Plotter-Puffer voll (XOFF) – warte auf Plotter..." if self._xoff_paused else "Plot fortgesetzt"
        if new_state is not None:
            self._emit_status(new_state, msg)

    def abort(self, wait: bool = False, timeout: float = 1.0) -> None:
        """Immediately abort current plot job, flush host buffer, and lift pen."""
        thread_to_join: Optional[threading.Thread] = None
        with self._lock:
            if not self.is_active():
                return
            self._state = StreamerState.ABORTING
            self._abort_requested = True
            self._pause_event.set()  # Wake up if paused
            if self._transport:
                self._transport.discard_output()
            if wait and self._thread and self._thread is not threading.current_thread():
                thread_to_join = self._thread
        if thread_to_join is not None and thread_to_join.is_alive():
            thread_to_join.join(timeout=max(0.0, float(timeout)))

    def _emit_status(self, state: StreamerState, msg: str) -> None:
        with self._lock:
            self._state = state
            cb = self.on_status
        if cb:
            cb(state, msg)

    def _send_raw(self, data: bytes) -> bool:
        """Send raw bytes via active Transport, retrying cleanly if CTS or write timeout blocks.

        Returns True if all bytes were sent, False if aborted during transmission.
        """
        if not self._transport:
            return True

        view = memoryview(data)
        sent = 0
        stall_notified = False
        timeout_exc = (getattr(serial, "SerialTimeoutException", TimeoutError), socket.timeout, TimeoutError)

        while sent < len(view):
            if self._abort_requested:
                return False

            if self._transport.is_cts_low():
                if not stall_notified:
                    stall_notified = True
                    self._emit_status(
                        StreamerState.PAUSED,
                        "Plotter-Puffer voll (CTS low) – warte auf Plotter...",
                    )
                time.sleep(0.05)
                continue

            try:
                chunk_bytes = bytes(view[sent:])
                n = self._transport.write(chunk_bytes)
                if n > 0:
                    self._record_trace("TX", chunk_bytes[:n])
                sent += n
                if stall_notified and not self.is_user_paused():
                    stall_notified = False
                    self._emit_status(StreamerState.STREAMING, "Sende Plotdaten...")
            except timeout_exc:
                if self._abort_requested:
                    return False
                if not stall_notified:
                    stall_notified = True
                    self._emit_status(
                        StreamerState.PAUSED,
                        "Plotter-Puffer voll (Write-Timeout) – warte auf Plotter...",
                    )
                time.sleep(0.05)
                continue
        return True

    def _sync_plotter_ready(self, timeout_s: float = 2.0) -> bool:
        """Send OA; inquiry and wait for plotter response to ensure buffer is drained up to this point."""
        if self._abort_requested or not self._transport or not self._transport.can_sync_oa():
            return False

        try:
            self._transport.reset_input()
            if not self._send_raw(b"OA;\r"):
                return False
            self._transport.drain()
            deadline = time.monotonic() + timeout_s
            buf = bytearray()
            while time.monotonic() < deadline and not self._abort_requested:
                chunk = self._transport.read_some(128, timeout_s=0.05)
                if chunk:
                    self._record_trace("RX", chunk)
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
            if self._transport:
                self._transport.discard_output()
                self._transport.disable_hardware_flow_control()
                try:
                    abort_bytes = b"\x1b.K\rPU;SP0;\r\n"
                    self._transport.write(abort_bytes)
                    self._record_trace("TX", abort_bytes)
                    self._transport.drain()
                except Exception:
                    pass
        except Exception:
            pass
        self._close_connection()
        self._emit_status(StreamerState.IDLE, "Plot abgebrochen")
        if self.on_finished:
            self.on_finished(False, "Plot durch Benutzer abgebrochen")

    def _check_and_wait_xoff(self) -> None:
        """Process incoming bytes for XON / XOFF flow control."""
        if not self._transport:
            return

        while not self._abort_requested:
            try:
                raw = self._transport.read_available()
                if raw:
                    self._record_trace("RX", raw)
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

    @staticmethod
    def _extract_last_coord_pair(hpgl_cmd: str) -> Optional[str]:
        """Extract the last 'x,y' coordinate pair from a PU or PD command string."""
        s = hpgl_cmd.strip()
        if not (s.startswith("PU") or s.startswith("PD")):
            return None
        body = s[2:].rstrip(";").strip()
        if not body:
            return None
        parts = [p.strip() for p in body.split(",") if p.strip()]
        if len(parts) >= 2 and len(parts) % 2 == 0:
            return f"{parts[-2]},{parts[-1]}"
        return None

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
        transport: Optional[Transport] = None,
        start_step_index: int = 0,
    ) -> None:
        port_clean = port.strip()
        total_commands = len(commands)
        drawn_total_mm = 0.0

        fc = (flow_control or "rtscts").lower()
        effective_rtscts = (fc == "rtscts") if rtscts is None else bool(rtscts)
        effective_dsrdtr = (fc == "dsrdtr") if dsrdtr is None else bool(dsrdtr)
        effective_xonxoff = (fc == "xonxoff") if xonxoff_userspace is None else bool(xonxoff_userspace)

        self._emit_status(StreamerState.CONNECTING, f"Verbinde mit {port_clean}...")

        try:
            if transport is not None:
                self._transport = transport
                self._transport.open()
            elif port_clean.startswith("tcp://"):
                if fc != "none" and xonxoff_userspace is not False:
                    effective_xonxoff = True
                tcp_t = TcpTransport(port_clean, connect_timeout=3.0, write_timeout=2.0)
                tcp_t.open()
                self._transport = tcp_t
                self._socket = tcp_t.sock
            else:
                ser_t = SerialTransport(
                    port=port_clean,
                    baudrate=baudrate,
                    bytesize=bytesize,
                    parity=parity,
                    stopbits=stopbits,
                    rtscts=effective_rtscts,
                    dsrdtr=effective_dsrdtr,
                    timeout=0.1 if effective_xonxoff else 0.2,
                    write_timeout=write_timeout,
                )
                ser_t.open()
                self._transport = ser_t
                self._serial = ser_t.ser

            self._emit_status(StreamerState.STREAMING, "Sende Plotdaten...")
            active_pen: Optional[int] = None
            resumed_from_skip = False
            pending_pen_cmd: Optional[EmittedCommand] = None
            last_skipped_coord: Optional[str] = None

            for i, cmd in enumerate(commands):
                hpgl_stripped = cmd.hpgl.lstrip()
                is_init_cmd = (i == 0) and (hpgl_stripped.startswith("IN") or hpgl_stripped.startswith("\x1b"))
                is_pen_select = hpgl_stripped.startswith("SP") and not hpgl_stripped.startswith("SP0") and cmd.pen > 0

                # Handle resume from start_step_index > 0
                if start_step_index > 0 and not resumed_from_skip:
                    if is_init_cmd:
                        # Always send initialization command
                        if not self._send_raw(cmd.hpgl.encode("ascii", errors="replace")):
                            self._execute_abort_sequence()
                            return
                        continue
                    if cmd.step_index < start_step_index:
                        if is_pen_select:
                            pending_pen_cmd = cmd
                            active_pen = cmd.pen
                        else:
                            coord = self._extract_last_coord_pair(hpgl_stripped)
                            if coord:
                                last_skipped_coord = coord
                            if cmd.is_draw:
                                drawn_total_mm += cmd.dist_mm
                        continue
                    else:
                        resumed_from_skip = True
                        if pending_pen_cmd is not None and not is_pen_select:
                            if not self._send_raw(pending_pen_cmd.hpgl.encode("ascii", errors="replace")):
                                self._execute_abort_sequence()
                                return
                            pending_pen_cmd = None
                        if hpgl_stripped.startswith("PD") and last_skipped_coord:
                            if not self._send_raw(f"PU{last_skipped_coord};\r\n".encode("ascii")):
                                self._execute_abort_sequence()
                                return

                # Automatic pause before pen change (SPn; where n > 0 after first pen)
                if is_pen_select:
                    if pause_on_pen_change and active_pen is not None and cmd.pen != active_pen:
                        if sync_with_oa:
                            self._sync_plotter_ready(timeout_s=5.0)
                        should_pause_pen = False
                        with self._lock:
                            if not self._abort_requested:
                                self._state = StreamerState.PAUSED
                                self._pause_event.clear()
                                should_pause_pen = True
                        if should_pause_pen:
                            self._emit_status(
                                StreamerState.PAUSED,
                                f"Stiftwechsel auf SP{cmd.pen} – Bitte Stift wechseln und Fortsetzen klicken",
                            )
                    active_pen = cmd.pen

                self._pause_event.wait()

                if self._abort_requested:
                    self._execute_abort_sequence()
                    return

                if effective_xonxoff:
                    self._check_and_wait_xoff()
                    if self._abort_requested:
                        self._execute_abort_sequence()
                        return

                if inter_command_delay_s > 0.0:
                    time.sleep(inter_command_delay_s)

                sent_ok = self._send_raw(cmd.hpgl.encode("ascii", errors="replace"))
                if not sent_ok or self._abort_requested:
                    self._execute_abort_sequence()
                    return

                if cmd.is_draw:
                    drawn_total_mm += cmd.dist_mm
                self.last_completed_step_index = cmd.step_index

                pct = ((i + 1) / total_commands) * 100.0 if total_commands > 0 else 100.0
                if self.on_progress:
                    self.on_progress(cmd.step_index, total_commands, pct, cmd.pen, drawn_total_mm / 1000.0)

            if self._transport:
                self._transport.drain()
            if sync_with_oa and total_commands > 0 and not self._abort_requested:
                self._sync_plotter_ready(timeout_s=2.0)
            if end_settle_delay_s > 0.0 and not self._abort_requested:
                time.sleep(end_settle_delay_s)

            if self._abort_requested:
                self._execute_abort_sequence()
                return

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
        if self._transport:
            self._transport.close()
            self._transport = None
        self._serial = None
        self._socket = None
