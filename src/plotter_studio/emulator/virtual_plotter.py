"""Virtual Mutoh XP-500 Plotter (HP-7585B Emulation).

Simulates the firmware state machine, inquiries (OI, OF, OH, OT, OS, OE, ESC.B, etc.),
drawing commands (IN, SP, VS, FS, AS, PU, PD, PA, PR), buffer capacity and flow control.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class PaperFormat(str, Enum):
    A4_LANDSCAPE = "A4"
    A3_LANDSCAPE = "A3"
    A2_LANDSCAPE = "A2"
    A1_LANDSCAPE = "A1"
    A0_LANDSCAPE = "A0"
    CUSTOM = "CUSTOM"


# Sheet dimensions in mm (width, height)
PAPER_SIZES: dict[str, tuple[float, float]] = {
    "A4": (297.0, 210.0),
    "A3": (420.0, 297.0),
    "A2": (594.0, 420.0),
    "A1": (841.0, 594.0),
    "A0": (1189.0, 841.0),
}

# Margins according to Mutoh manual Fig. 7.3: (top, bottom, left, right) in mm
# Note: "top" is leading edge in feed (X) direction
MARGIN_PROFILES = {
    "EXP": (25.0, 5.0, 5.0, 5.0),
    "NORM": (35.0, 15.0, 15.0, 15.0),
    "TYPE1": (25.0, 5.0, 11.0, 11.0),
    "TYPE3": (25.0, 10.0, 10.0, 10.0),
}


@dataclass
class RecordedPolyline:
    pen: int
    points: list[tuple[float, float]]  # (x, y) in mm


@dataclass
class EmulatorStats:
    bytes_received: int = 0
    bytes_sent: int = 0
    commands_executed: int = 0
    drawn_distance_mm: float = 0.0
    travel_distance_mm: float = 0.0
    pen_changes: int = 0
    pen_up_count: int = 0
    pen_down_count: int = 0


class VirtualPlotter:
    """Firmware simulator for Mutoh XP-500 in HP-7585B emulation mode."""

    def __init__(
        self,
        paper: str = "A3",
        custom_size_mm: Optional[tuple[float, float]] = None,
        margin_profile: str = "EXP",
        buffer_size: int = 1000,
        resolution_mm: float = 0.025,
        default_speed_cm_s: float = 40.0,
        realtime: bool = False,
        speedup: float = 1.0,
        baudrate: Optional[int] = None,
        on_response: Optional[Callable[[bytes], None]] = None,
        on_event: Optional[Callable[[str, dict], None]] = None,
    ):
        """
        Args:
            paper: Paper format name ("A4", "A3", "A2", "A1", "A0", "CUSTOM")
            custom_size_mm: (width, height) in mm if paper == "CUSTOM"
            margin_profile: "EXP", "NORM", "TYPE1", or "TYPE3"
            buffer_size: Input buffer capacity in bytes (e.g. 1000 or 1048576)
            resolution_mm: Unit size in mm (0.025 => 40 units/mm; 0.010 => 100 units/mm)
            default_speed_cm_s: Default pen speed in cm/s
            realtime: If True, simulates mechanical delay according to pen speed
            speedup: Acceleration factor for realtime simulation (e.g. 10.0 = 10x faster)
            baudrate: Simulated serial baud rate (e.g. 300, 1200, 9600, 19200; None for unthrottled)
            on_response: Callback invoked whenever the plotter sends response bytes to the host
        """
        self.paper = paper.upper()
        if self.paper == "CUSTOM" and custom_size_mm:
            self.sheet_width_mm, self.sheet_height_mm = custom_size_mm
        else:
            self.sheet_width_mm, self.sheet_height_mm = PAPER_SIZES.get(self.paper, (420.0, 297.0))

        self.margin_profile = margin_profile.upper()
        self.margins_mm = MARGIN_PROFILES.get(self.margin_profile, (25.0, 5.0, 5.0, 5.0))
        self.buffer_size = buffer_size
        self.resolution_mm = resolution_mm
        self.units_per_mm = 1.0 / resolution_mm
        self.default_speed_cm_s = default_speed_cm_s
        self.realtime = realtime
        self.speedup = max(0.1, speedup)
        self.baudrate = int(baudrate) if (baudrate is not None and int(baudrate) > 0) else None
        self.on_response = on_response
        self.on_event = on_event

        # Lock for thread-safe state access
        self._lock = threading.RLock()

        # Hard-clip area calculation (Center-Origin)
        # X: sheet_width - (m_top + m_bottom), Y: sheet_height - (m_left + m_right)
        top_m, bottom_m, left_m, right_m = self.margins_mm
        self.plottable_width_mm = max(10.0, self.sheet_width_mm - (top_m + bottom_m))
        self.plottable_height_mm = max(10.0, self.sheet_height_mm - (left_m + right_m))

        self.hard_clip_xmin_units = int(- (self.plottable_width_mm * self.units_per_mm) / 2.0)
        self.hard_clip_xmax_units = int((self.plottable_width_mm * self.units_per_mm) / 2.0)
        self.hard_clip_ymin_units = int(- (self.plottable_height_mm * self.units_per_mm) / 2.0)
        self.hard_clip_ymax_units = int((self.plottable_height_mm * self.units_per_mm) / 2.0)

        # Plotter state
        self.active_pen: int = 0
        self.pen_down: bool = False
        self.pos_units: tuple[int, int] = (0, 0)
        self.pen_speed: dict[int, float] = {p: default_speed_cm_s for p in range(1, 9)}
        self.pen_force: dict[int, int] = {p: 4 for p in range(1, 9)}
        self.pen_accel: dict[int, float] = {p: 4.0 for p in range(1, 9)}

        self.status_byte: int = 16  # Ready / Normal
        self.error_code: int = 0
        self.lcd_message: str = ""

        # Buffer tracking
        self.buffer_used: int = 0

        # Recorded drawing
        self.recorded_polylines: list[RecordedPolyline] = []
        self._current_polyline: list[tuple[float, float]] = []
        self.stats = EmulatorStats()

        # Incoming byte buffer
        self._rx_accumulator = bytearray()

    @property
    def free_buffer(self) -> int:
        with self._lock:
            return max(0, self.buffer_size - self.buffer_used)

    @property
    def pos_mm(self) -> tuple[float, float]:
        with self._lock:
            return (self.pos_units[0] / self.units_per_mm, self.pos_units[1] / self.units_per_mm)

    def reset(self) -> None:
        """Reset the plotter to power-on state (ESC.R / IN)."""
        with self._lock:
            self._flush_current_polyline()
            self.active_pen = 0
            self.pen_down = False
            self.pos_units = (0, 0)
            self.buffer_used = 0
            self.status_byte = 16
            self.error_code = 0
            self.lcd_message = ""

    def abort(self) -> None:
        """Abort current plot immediately (ESC.K)."""
        with self._lock:
            self._flush_current_polyline()
            self.pen_down = False
            self.buffer_used = 0
            self._rx_accumulator.clear()
            if self.on_event:
                self.on_event("abort", {})

    def receive_bytes(self, data: bytes) -> None:
        """Push incoming raw bytes into the plotter input."""
        with self._lock:
            self.stats.bytes_received += len(data)
            self.buffer_used = min(self.buffer_size, self.buffer_used + len(data))
            self._rx_accumulator.extend(data)
            self._process_rx_buffer()

    def _send_response(self, text: str, inquiry_cmd: str = "") -> None:
        """Send response string to host terminated with CR."""
        resp = (text + "\r").encode("ascii")
        self.stats.bytes_sent += len(resp)
        if self.on_response:
            self.on_response(resp)
        if self.on_event and inquiry_cmd:
            self.on_event("inquiry", {"cmd": inquiry_cmd, "response": text})

    def _flush_current_polyline(self) -> None:
        if self._current_polyline and len(self._current_polyline) >= 2:
            poly = RecordedPolyline(pen=self.active_pen, points=list(self._current_polyline))
            self.recorded_polylines.append(poly)
            if self.on_event:
                dist = sum(
                    math.hypot(poly.points[i + 1][0] - poly.points[i][0], poly.points[i + 1][1] - poly.points[i][1])
                    for i in range(len(poly.points) - 1)
                )
                self.on_event("polyline_drawn", {
                    "pen": self.active_pen,
                    "points": len(poly.points),
                    "dist_mm": dist,
                    "total_polylines": len(self.recorded_polylines),
                })
        self._current_polyline.clear()

    def _process_rx_buffer(self) -> None:
        """Parse commands from incoming accumulator."""
        while self._rx_accumulator:
            # Check for Escape sequences: \x1b.[A-Z@](...):?
            if self._rx_accumulator[0] == 0x1B:
                if len(self._rx_accumulator) < 2:
                    break  # Wait for more bytes
                if self._rx_accumulator[1] == ord("."):
                    if len(self._rx_accumulator) < 3:
                        break
                    cmd_char = chr(self._rx_accumulator[2])
                    # Check if command has parameter ending in ':'
                    if cmd_char in ("@", "H", "I", "M", "N", "P", "Q", "S", "T"):
                        # Needs closing ':'
                        colon_pos = self._rx_accumulator.find(b":", 3)
                        if colon_pos == -1:
                            break  # Incomplete
                        params = self._rx_accumulator[3:colon_pos].decode("ascii", errors="replace")
                        del self._rx_accumulator[:colon_pos + 1]
                        self._execute_escape_cmd(cmd_char, params)
                        continue
                    else:
                        # 3-byte escape command e.g. ESC.B, ESC.K, ESC.R, ESC.L, ESC.O, ESC.E, ESC.A
                        del self._rx_accumulator[:3]
                        self._execute_escape_cmd(cmd_char, "")
                        continue
                else:
                    # Lone ESC or unknown escape sequence -> discard ESC byte
                    del self._rx_accumulator[0]
                    continue

            # Skip leading whitespace or semicolons
            b = self._rx_accumulator[0]
            if b in (ord(" "), ord("\r"), ord("\n"), ord("\t"), ord(";")):
                del self._rx_accumulator[0]
                if self.buffer_used > 0:
                    self.buffer_used -= 1
                continue

            # Look for command end: ';' or newline
            match = re.search(rb"[;\r\n]", self._rx_accumulator)
            if not match:
                # If accumulator is getting large without terminator, check if next 2 chars are letters
                if len(self._rx_accumulator) >= 4 and chr(self._rx_accumulator[0]).isalpha() and chr(self._rx_accumulator[1]).isalpha():
                    # Might be concatenated without semicolons, wait or check
                    pass
                break  # Incomplete command

            end_idx = match.start()
            cmd_bytes = self._rx_accumulator[:end_idx]
            # Remove command and terminator
            consumed = end_idx + 1
            del self._rx_accumulator[:consumed]
            self.buffer_used = max(0, self.buffer_used - consumed)

            cmd_str = cmd_bytes.decode("ascii", errors="replace").strip()
            if cmd_str:
                self._execute_hpgl_cmd(cmd_str)

    def _execute_escape_cmd(self, cmd: str, params: str) -> None:
        self.stats.commands_executed += 1
        cmd = cmd.upper()

        if cmd == "B":
            # Buffer inquiry: returns free buffer capacity in bytes + CR
            self._send_response(str(self.free_buffer))
        elif cmd == "L":
            # Buffer capacity inquiry
            self._send_response(str(self.buffer_size))
        elif cmd == "A":
            # Plotter identification
            self._send_response("7585B")
        elif cmd == "E":
            # Extended error
            self._send_response(str(self.error_code))
        elif cmd == "O":
            # Extended status
            self._send_response(str(self.status_byte))
        elif cmd == "K":
            # Abort graphics
            self.abort()
        elif cmd == "R":
            # Reset communications
            self.reset()
        elif cmd == "@":
            # Set buffer size if numeric parameter given
            parts = params.split(";")
            if parts and parts[0].isdigit():
                new_size = int(parts[0])
                if new_size > 0:
                    self.buffer_size = new_size
                    self.buffer_used = min(self.buffer_used, self.buffer_size)

    def _execute_hpgl_cmd(self, cmd_str: str) -> None:
        self.stats.commands_executed += 1
        opcode = cmd_str[:2].upper()
        args_str = cmd_str[2:].strip()

        # Inquiries
        if opcode == "OI":
            self._send_response("7585B", inquiry_cmd="OI")
        elif opcode == "OF":
            u = int(round(self.units_per_mm))
            self._send_response(f"{u},{u}", inquiry_cmd="OF")
        elif opcode == "OH":
            self._send_response(
                f"{self.hard_clip_xmin_units},{self.hard_clip_ymin_units},"
                f"{self.hard_clip_xmax_units},{self.hard_clip_ymax_units}",
                inquiry_cmd="OH",
            )
        elif opcode == "OT":
            # Stocker type 1, pen loaded
            self._send_response("1,1", inquiry_cmd="OT")
        elif opcode == "OS":
            self._send_response(str(self.status_byte), inquiry_cmd="OS")
        elif opcode == "OE":
            self._send_response(str(self.error_code), inquiry_cmd="OE")
            self.error_code = 0
        elif opcode in ("OA", "OC"):
            # Position & pen status (0 = up, 1 = down)
            p_state = 1 if self.pen_down else 0
            self._send_response(f"{self.pos_units[0]},{self.pos_units[1]},{p_state}", inquiry_cmd=opcode)

        # Control commands
        elif opcode == "IN":
            self.reset()
            if self.on_event:
                self.on_event("init", {})
        elif opcode == "SP":
            p = int(args_str) if args_str.isdigit() else 0
            if p != self.active_pen:
                old_p = self.active_pen
                self._flush_current_polyline()
                self.active_pen = p
                self.stats.pen_changes += 1
                if self.on_event:
                    self.on_event("pen_change", {"pen": p, "old_pen": old_p})
                if p == 0 and len(self.recorded_polylines) > 0:
                    if self.on_event:
                        self.on_event("job_finished", {
                            "polylines": len(self.recorded_polylines),
                            "draw_m": self.stats.drawn_distance_mm / 1000.0,
                            "travel_m": self.stats.travel_distance_mm / 1000.0,
                        })
                if self.realtime:
                    time.sleep(1.2 / self.speedup)
        elif opcode == "VS":
            # VS v[,pen]
            parts = [s.strip() for s in args_str.split(",") if s.strip()]
            if parts:
                v = float(parts[0])
                if len(parts) > 1 and parts[1].isdigit():
                    self.pen_speed[int(parts[1])] = v
                else:
                    for p in self.pen_speed:
                        self.pen_speed[p] = v
                if self.on_event:
                    self.on_event("speed_change", {"speed_cm_s": v})
        elif opcode == "FS":
            parts = [s.strip() for s in args_str.split(",") if s.strip()]
            if parts:
                f = int(parts[0])
                if len(parts) > 1 and parts[1].isdigit():
                    self.pen_force[int(parts[1])] = f
                else:
                    for p in self.pen_force:
                        self.pen_force[p] = f
        elif opcode == "AS":
            parts = [s.strip() for s in args_str.split(",") if s.strip()]
            if parts:
                a = float(parts[0])
                if len(parts) > 1 and parts[1].isdigit():
                    self.pen_accel[int(parts[1])] = a
                else:
                    for p in self.pen_accel:
                        self.pen_accel[p] = a
        elif opcode == "PU":
            self._handle_pen_state(down=False, args_str=args_str, relative=False)
        elif opcode == "PD":
            self._handle_pen_state(down=True, args_str=args_str, relative=False)
        elif opcode == "PA":
            self._handle_move(args_str=args_str, relative=False)
        elif opcode == "PR":
            self._handle_move(args_str=args_str, relative=True)
        elif opcode == "WD":
            # Text display
            self.lcd_message = args_str

    def _handle_pen_state(self, down: bool, args_str: str, relative: bool) -> None:
        if self.pen_down != down:
            if not down:
                # Pen lifted -> complete current line
                self._flush_current_polyline()
                self.stats.pen_up_count += 1
            else:
                self.stats.pen_down_count += 1
                # Start new polyline with current position
                self._current_polyline = [self.pos_mm]
            self.pen_down = down
            if self.realtime:
                time.sleep(0.04 / self.speedup)

        if args_str:
            self._handle_move(args_str=args_str, relative=relative)

    def _handle_move(self, args_str: str, relative: bool) -> None:
        if not args_str:
            return

        # Parse comma- or space-separated numbers
        raw_tokens = re.split(r"[, \t]+", args_str.strip())
        coords = []
        for t in raw_tokens:
            if t:
                try:
                    coords.append(int(round(float(t))))
                except ValueError:
                    pass

        # Coordinates come in pairs: x1, y1, x2, y2...
        for i in range(0, len(coords) - 1, 2):
            val_x, val_y = coords[i], coords[i + 1]
            if relative:
                target_x = self.pos_units[0] + val_x
                target_y = self.pos_units[1] + val_y
            else:
                target_x = val_x
                target_y = val_y

            # Calculate physical distance moved
            dx_units = target_x - self.pos_units[0]
            dy_units = target_y - self.pos_units[1]
            dist_units = math.hypot(dx_units, dy_units)
            dist_mm = dist_units / self.units_per_mm

            self.pos_units = (target_x, target_y)
            pos_mm = self.pos_mm

            if self.pen_down and self.active_pen > 0:
                self.stats.drawn_distance_mm += dist_mm
                if not self._current_polyline:
                    self._current_polyline.append(pos_mm)
                else:
                    self._current_polyline.append(pos_mm)
            else:
                self.stats.travel_distance_mm += dist_mm

            if self.realtime and dist_mm > 0:
                speed = self.pen_speed.get(self.active_pen, self.default_speed_cm_s) * 10.0  # mm/s
                move_sec = dist_mm / max(10.0, speed)
                time.sleep(move_sec / self.speedup)

