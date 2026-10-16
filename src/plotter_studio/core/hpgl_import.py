"""HP-GL / PLT Import parser converting HP-GL commands into millimeter VectorPaths.

Source / Origin Notice:
-----------------------
The HP-GL tokenizer (`HPGLTokenizer`, `Command`), 5x7 stroke font (`GLYPHS`, `glyph_rows`),
and state machine / geometry parser (`HPGLParser`, `PlotState`, `HPGLPolyline`) are adapted
from the sibling project **MutohPlot**:
  - `MutohPlot/src/mutohplot/hpgl/tokens.py`
  - `MutohPlot/src/mutohplot/hpgl/tokenizer.py`
  - `MutohPlot/src/mutohplot/hpgl/stroke_font.py`
  - `MutohPlot/src/mutohplot/hpgl/parser.py`

Adapted for Plotter Studio's `ImportItem` / `VectorPath` document model (millimeter space,
top-left canvas origin with +Y pointing downwards).
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
from typing import Dict, List, Optional, Tuple
import numpy as np

from .document import ImportItem, VectorPath
from .geometry import LineSegment, PathSegment


# ---------------------------------------------------------------------------
# 1. Tokens & Tokenizer (adapted from MutohPlot: mutohplot/hpgl/tokens.py & tokenizer.py)
# ---------------------------------------------------------------------------

_FLOAT_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

NUMERIC_COMMANDS = {
    "PA",
    "PR",
    "PU",
    "PD",
    "SP",
    "VS",
    "FS",
    "AS",
    "RO",
    "AA",
    "AR",
    "CI",
    "EA",
    "RA",
    "SI",
    "SL",
    "DI",
    "DR",
    "CP",
    "IP",
    "SC",
    "IW",
    "LT",
    "PT",
}


@dataclass(slots=True)
class Command:
    """Single tokenized HP-GL instruction."""

    name: str
    payload: str

    def numeric_args(self) -> List[float]:
        return [float(match.group(0)) for match in _FLOAT_RE.finditer(self.payload)]


class HPGLTokenizer:
    """Streaming-friendly tokenizer for classic HP-GL files (from MutohPlot)."""

    def tokenize(self, data: str) -> List[Command]:
        commands: List[Command] = []
        index = 0
        length = len(data)
        while index < length:
            while index < length and data[index] in " \t\r\n;":
                index += 1
            if index >= length:
                break
            # Skip ESC device-control sequences (e.g. ESC.Y, ESC.@, ESC.I...)
            if data[index] == "\x1b":
                index += 1
                while index < length and data[index] not in "\r\n;:" and not data[index].isalpha():
                    index += 1
                if index < length and not data[index - 1].isalpha():
                    index += 1
                continue
            if index + 1 >= length or not (data[index].isalpha() and data[index + 1].isalpha()):
                index += 1
                continue
            name = data[index : index + 2].upper()
            index += 2
            if name == "LB":
                start = index
                while index < length and data[index] not in ("\x03", ";"):
                    index += 1
                payload = data[start:index]
                if index < length and data[index] in ("\x03", ";"):
                    index += 1
                commands.append(Command(name=name, payload=payload))
                continue
            start = index
            while index < length:
                char = data[index]
                if char == ";":
                    break
                if (
                    index + 1 < length
                    and data[index].isalpha()
                    and data[index + 1].isalpha()
                    and (name not in NUMERIC_COMMANDS or self._looks_like_command_boundary(data, start, index))
                ):
                    break
                index += 1
            payload = data[start:index].strip()
            if index < length and data[index] == ";":
                index += 1
            commands.append(Command(name=name, payload=payload))
        return commands

    @staticmethod
    def _looks_like_command_boundary(data: str, start: int, index: int) -> bool:
        if index == start:
            return True
        prev = data[index - 1]
        if prev in "eE":
            return False
        return prev.isdigit() or prev in " \t\r\n,."


# ---------------------------------------------------------------------------
# 2. Built-in 5x7 Stroke Font for HP-GL LB labels (from MutohPlot: mutohplot/hpgl/stroke_font.py)
# ---------------------------------------------------------------------------

GLYPHS: Dict[str, Tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "#": ("01010", "11111", "01010", "01010", "11111", "01010", "00000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "%": ("11001", "11010", "00100", "01000", "10110", "00110", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "'": ("00100", "00100", "00000", "00000", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "*": ("00100", "10101", "01110", "11111", "01110", "10101", "00100"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    ",": ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "00100", "00000"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    ":": ("00000", "00100", "00000", "00000", "00100", "00000", "00000"),
    ";": ("00000", "00100", "00000", "00000", "00100", "00100", "01000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "?": ("01110", "10001", "00010", "00100", "00100", "00000", "00100"),
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00001", "00001", "00001", "00001", "10001", "10001", "01110"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10001", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "\\": ("10000", "01000", "00100", "00010", "00001", "00000", "00000"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
}


def glyph_rows(character: str) -> Tuple[str, ...]:
    """Return 5x7 bitmap rows for an ASCII character."""
    if character in GLYPHS:
        return GLYPHS[character]
    upper = character.upper()
    return GLYPHS.get(upper, GLYPHS["?"])


# ---------------------------------------------------------------------------
# 3. HP-GL Parser (adapted from MutohPlot: mutohplot/hpgl/parser.py)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HPGLPolyline:
    """Intermediate polyline in HP-GL coordinate space (millimeters, +Y up)."""

    points: List[Tuple[float, float]]
    pen: int = 1

    @property
    def is_closed(self) -> bool:
        if len(self.points) < 3:
            return False
        p0 = self.points[0]
        p1 = self.points[-1]
        return math.hypot(p1[0] - p0[0], p1[1] - p0[1]) <= 1e-4


@dataclass(slots=True)
class PlotState:
    """Internal state machine for HP-GL interpretation."""

    x_mm: float = 0.0
    y_mm: float = 0.0
    pen_down: bool = False
    relative_mode: bool = False
    pen: int = 1
    char_width_mm: float = 2.85
    char_height_mm: float = 3.75
    char_slant: float = 0.0
    text_dir_x: float = 1.0
    text_dir_y: float = 0.0


class HPGLParser:
    """Convert classic HP-GL commands into millimeter polylines (from MutohPlot)."""

    def __init__(self, source_unit_mm: float = 0.025) -> None:
        self.source_unit_mm = source_unit_mm
        self.tokenizer = HPGLTokenizer()

    def parse(self, text: str) -> List[HPGLPolyline]:
        state = PlotState()
        polylines: List[HPGLPolyline] = []
        current_points: List[Tuple[float, float]] = []

        def flush_current() -> None:
            nonlocal current_points
            if len(current_points) >= 2:
                polylines.append(HPGLPolyline(points=list(current_points), pen=max(1, min(8, state.pen))))
            current_points = []

        for command in self.tokenizer.tokenize(text):
            name = command.name
            args = command.numeric_args()

            if name in {"IN", "DF"}:
                flush_current()
                state = PlotState(pen=state.pen if name == "DF" else 1)
                continue

            if name == "SP":
                flush_current()
                if args:
                    raw_pen = int(round(args[0]))
                    if raw_pen > 0:
                        state.pen = max(1, min(8, raw_pen))
                continue

            if name == "PA":
                state.relative_mode = False
                self._apply_motion(args, state, current_points, relative=False)
                continue

            if name == "PR":
                state.relative_mode = True
                self._apply_motion(args, state, current_points, relative=True)
                continue

            if name == "PU":
                flush_current()
                state.pen_down = False
                self._apply_motion(args, state, current_points, relative=state.relative_mode)
                continue

            if name == "PD":
                if not state.pen_down:
                    flush_current()
                    state.pen_down = True
                    current_points = [(state.x_mm, state.y_mm)]
                self._apply_motion(args, state, current_points, relative=state.relative_mode)
                continue

            if name in {"AA", "AR"} and len(args) >= 3:
                center_x = args[0] * self.source_unit_mm
                center_y = args[1] * self.source_unit_mm
                if name == "AR":
                    center_x += state.x_mm
                    center_y += state.y_mm
                sweep_deg = args[2]
                chord_deg = abs(args[3]) if len(args) >= 4 else 5.0
                arc_points = self._approximate_arc(
                    start=(state.x_mm, state.y_mm),
                    center=(center_x, center_y),
                    sweep_deg=sweep_deg,
                    chord_deg=max(chord_deg, 1.0),
                )
                if state.pen_down:
                    if not current_points:
                        current_points = [(state.x_mm, state.y_mm)]
                    current_points.extend(arc_points[1:])
                state.x_mm, state.y_mm = arc_points[-1]
                continue

            if name == "CI" and args:
                flush_current()
                radius_mm = abs(args[0]) * self.source_unit_mm
                chord_deg = abs(args[1]) if len(args) >= 2 else 5.0
                circle = self._approximate_circle(
                    (state.x_mm, state.y_mm), radius_mm, max(chord_deg, 1.0)
                )
                polylines.append(HPGLPolyline(points=circle, pen=max(1, min(8, state.pen))))
                continue

            if name in {"EA", "RA"} and len(args) >= 2:
                flush_current()
                corner_x = args[0] * self.source_unit_mm
                corner_y = args[1] * self.source_unit_mm
                rect = [
                    (state.x_mm, state.y_mm),
                    (corner_x, state.y_mm),
                    (corner_x, corner_y),
                    (state.x_mm, corner_y),
                    (state.x_mm, state.y_mm),
                ]
                polylines.append(HPGLPolyline(points=rect, pen=max(1, min(8, state.pen))))
                if name == "RA":
                    polylines.extend(
                        self._hatch_rectangle(
                            state.x_mm, state.y_mm, corner_x, corner_y, max(1, min(8, state.pen))
                        )
                    )
                continue

            if name == "SI" and len(args) >= 2:
                # SI specifies character width and height in centimeters
                state.char_width_mm = max(abs(args[0]) * 10.0, 0.5)
                state.char_height_mm = max(abs(args[1]) * 10.0, 0.5)
                continue

            if name == "SL":
                state.char_slant = args[0] if args else 0.0
                continue

            if name in {"DI", "DR"}:
                if len(args) >= 2 and (args[0] != 0 or args[1] != 0):
                    norm = math.hypot(args[0], args[1])
                    state.text_dir_x = args[0] / norm
                    state.text_dir_y = args[1] / norm
                else:
                    state.text_dir_x = 1.0
                    state.text_dir_y = 0.0
                continue

            if name == "CP":
                spaces = args[0] if len(args) >= 1 else 0.0
                lines = args[1] if len(args) >= 2 else 0.0
                advance = spaces * state.char_width_mm * 1.4
                line_shift = lines * state.char_height_mm * 1.6
                normal_x = -state.text_dir_y
                normal_y = state.text_dir_x
                state.x_mm += state.text_dir_x * advance + normal_x * line_shift
                state.y_mm += state.text_dir_y * advance + normal_y * line_shift
                continue

            if name == "LB":
                flush_current()
                polylines.extend(self._emit_label(command.payload, state))
                continue

        flush_current()
        return polylines

    def _apply_motion(
        self,
        args: List[float],
        state: PlotState,
        current_points: List[Tuple[float, float]],
        *,
        relative: bool,
    ) -> None:
        if len(args) < 2:
            return
        if state.pen_down and not current_points:
            current_points.append((state.x_mm, state.y_mm))
        for index in range(0, len(args) - 1, 2):
            dx = args[index] * self.source_unit_mm
            dy = args[index + 1] * self.source_unit_mm
            if relative:
                state.x_mm += dx
                state.y_mm += dy
            else:
                state.x_mm = dx
                state.y_mm = dy
            if state.pen_down:
                current_points.append((state.x_mm, state.y_mm))

    @staticmethod
    def _approximate_arc(
        *,
        start: Tuple[float, float],
        center: Tuple[float, float],
        sweep_deg: float,
        chord_deg: float,
    ) -> List[Tuple[float, float]]:
        radius = math.hypot(start[0] - center[0], start[1] - center[1])
        if radius == 0.0:
            return [start]
        start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
        steps = max(1, int(math.ceil(abs(sweep_deg) / chord_deg)))
        points = [start]
        for step in range(1, steps + 1):
            angle = start_angle + math.radians((sweep_deg * step) / steps)
            points.append(
                (center[0] + math.cos(angle) * radius, center[1] + math.sin(angle) * radius)
            )
        return points

    @staticmethod
    def _approximate_circle(
        center: Tuple[float, float],
        radius_mm: float,
        chord_deg: float,
    ) -> List[Tuple[float, float]]:
        steps = max(8, int(math.ceil(360.0 / chord_deg)))
        points: List[Tuple[float, float]] = []
        for step in range(steps + 1):
            angle = math.radians((360.0 * step) / steps)
            points.append(
                (
                    center[0] + math.cos(angle) * radius_mm,
                    center[1] + math.sin(angle) * radius_mm,
                )
            )
        return points

    @staticmethod
    def _hatch_rectangle(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        pen: int,
    ) -> List[HPGLPolyline]:
        min_x, max_x = sorted((x0, x1))
        min_y, max_y = sorted((y0, y1))
        step = 0.6
        current_y = min_y + step
        lines: List[HPGLPolyline] = []
        reverse = False
        while current_y < max_y:
            pts = (
                [(max_x, current_y), (min_x, current_y)]
                if reverse
                else [(min_x, current_y), (max_x, current_y)]
            )
            lines.append(HPGLPolyline(points=pts, pen=pen))
            reverse = not reverse
            current_y += step
        return lines

    def _emit_label(self, text: str, state: PlotState) -> List[HPGLPolyline]:
        polylines: List[HPGLPolyline] = []
        origin_x = state.x_mm
        origin_y = state.y_mm
        line_index = 0
        col_index = 0
        cell_width = state.char_width_mm / 4.0
        cell_height = state.char_height_mm / 6.0
        normal_x = -state.text_dir_y
        normal_y = state.text_dir_x

        for char in text:
            if char == "\r":
                col_index = 0
                continue
            if char == "\n":
                line_index -= 1
                col_index = 0
                continue
            rows = glyph_rows(char)
            char_base_x = (
                origin_x
                + state.text_dir_x * (col_index * state.char_width_mm * 1.35)
                + normal_x * (line_index * state.char_height_mm * 1.6)
            )
            char_base_y = (
                origin_y
                + state.text_dir_y * (col_index * state.char_width_mm * 1.35)
                + normal_y * (line_index * state.char_height_mm * 1.6)
            )

            # Horizontal runs
            for row_idx, row in enumerate(rows):
                start_col: Optional[int] = None
                for col_idx, bit in enumerate(row + "0"):
                    if bit == "1" and start_col is None:
                        start_col = col_idx
                    elif bit == "0" and start_col is not None:
                        end_col = col_idx - 1
                        if end_col > start_col:
                            p0 = self._glyph_point(
                                char_base_x,
                                char_base_y,
                                start_col,
                                row_idx,
                                cell_width,
                                cell_height,
                                state,
                            )
                            p1 = self._glyph_point(
                                char_base_x,
                                char_base_y,
                                end_col,
                                row_idx,
                                cell_width,
                                cell_height,
                                state,
                            )
                            polylines.append(HPGLPolyline(points=[p0, p1], pen=max(1, min(8, state.pen))))
                        start_col = None

            # Vertical runs
            for col_idx in range(5):
                start_row: Optional[int] = None
                for row_idx in range(8):
                    bit = rows[row_idx][col_idx] if row_idx < 7 else "0"
                    if bit == "1" and start_row is None:
                        start_row = row_idx
                    elif bit == "0" and start_row is not None:
                        end_row = row_idx - 1
                        if end_row > start_row:
                            p0 = self._glyph_point(
                                char_base_x,
                                char_base_y,
                                col_idx,
                                start_row,
                                cell_width,
                                cell_height,
                                state,
                            )
                            p1 = self._glyph_point(
                                char_base_x,
                                char_base_y,
                                col_idx,
                                end_row,
                                cell_width,
                                cell_height,
                                state,
                            )
                            polylines.append(HPGLPolyline(points=[p0, p1], pen=max(1, min(8, state.pen))))
                        start_row = None

            # Single isolated dots (e.g. period, colon, exclamation dot)
            for row_idx, row in enumerate(rows):
                for col_idx, bit in enumerate(row):
                    if bit != "1":
                        continue
                    has_h_neighbor = (col_idx > 0 and row[col_idx - 1] == "1") or (
                        col_idx < 4 and row[col_idx + 1] == "1"
                    )
                    has_v_neighbor = (row_idx > 0 and rows[row_idx - 1][col_idx] == "1") or (
                        row_idx < 6 and rows[row_idx + 1][col_idx] == "1"
                    )
                    if not has_h_neighbor and not has_v_neighbor:
                        p0 = self._glyph_point(
                            char_base_x,
                            char_base_y,
                            col_idx,
                            row_idx,
                            cell_width,
                            cell_height,
                            state,
                        )
                        p1 = (p0[0] + cell_width * 0.25, p0[1] + cell_height * 0.25)
                        polylines.append(HPGLPolyline(points=[p0, p1], pen=max(1, min(8, state.pen))))

            col_index += 1

        state.x_mm = origin_x + state.text_dir_x * (col_index * state.char_width_mm * 1.35)
        state.y_mm = origin_y + state.text_dir_y * (col_index * state.char_height_mm * 1.35)
        return polylines

    @staticmethod
    def _glyph_point(
        base_x: float,
        base_y: float,
        col_idx: int,
        row_idx: int,
        cell_width: float,
        cell_height: float,
        state: PlotState,
    ) -> Tuple[float, float]:
        local_y = (6 - row_idx) * cell_height
        local_x = col_idx * cell_width + local_y * state.char_slant
        normal_x = -state.text_dir_y
        normal_y = state.text_dir_x
        x = base_x + state.text_dir_x * local_x + normal_x * local_y
        y = base_y + state.text_dir_y * local_x + normal_y * local_y
        return (x, y)


# ---------------------------------------------------------------------------
# 4. Plotter Studio Import Integration
# ---------------------------------------------------------------------------


def is_hpgl_file(filepath: str) -> bool:
    """Return True if filepath has an .hpgl or .plt extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return ext in (".hpgl", ".plt")


def load_hpgl(
    filepath_or_data: str,
    name: Optional[str] = None,
    source_unit_mm: float = 0.025,
) -> ImportItem:
    """Load an HP-GL file (.hpgl / .plt) or raw HP-GL string into a Plotter Studio ImportItem.

    Coordinate System Conversion:
    - Classic HP-GL uses a mathematical Cartesian coordinate system (+X right, +Y up),
      and plotter files may use either bottom-left (0, 0) or center-origin (negative/positive)
      coordinates.
    - Plotter Studio's canvas/SVG coordinate system uses top-left (0, 0) with +X right and +Y down.
    - We invert the Y-axis (`y_canvas = -y_hpgl`) so geometry and `LB` text labels appear upright,
      and shift the imported item's minimum bounding corner to (0, 0) in local item space.
    """
    if os.path.exists(filepath_or_data):
        item_name = name or os.path.splitext(os.path.basename(filepath_or_data))[0]
        source_path: Optional[str] = filepath_or_data
        raw_text = Path(filepath_or_data).read_text(encoding="utf-8", errors="replace")
    else:
        item_name = name or "HPGL-Import"
        source_path = None
        raw_text = filepath_or_data

    parser = HPGLParser(source_unit_mm=source_unit_mm)
    polylines = parser.parse(raw_text)

    if not polylines:
        return ImportItem(name=item_name, paths=[], source_path=source_path)

    # Flip Y-axis (+Y up in HP-GL -> +Y down in Canvas/SVG) and find bounding box minimum
    flipped_polylines: List[Tuple[List[Tuple[float, float]], int, bool]] = []
    min_x = float("inf")
    min_y = float("inf")

    for poly in polylines:
        if len(poly.points) < 2:
            continue
        pts_flipped = [(pt[0], -pt[1]) for pt in poly.points]
        for x, y in pts_flipped:
            if x < min_x:
                min_x = x
            if y < min_y:
                min_y = y
        flipped_polylines.append((pts_flipped, poly.pen, poly.is_closed))

    if not flipped_polylines:
        return ImportItem(name=item_name, paths=[], source_path=source_path)

    # Normalize local coordinates so the item's top-left corner starts at (0.0, 0.0)
    vector_paths: List[VectorPath] = []
    for pts_flipped, pen_id, is_closed in flipped_polylines:
        norm_pts = [(x - min_x, y - min_y) for x, y in pts_flipped]
        segs: List[PathSegment] = []
        for i in range(len(norm_pts) - 1):
            p0 = norm_pts[i]
            p1 = norm_pts[i + 1]
            if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1e-9:
                segs.append(LineSegment(start=p0, end=p1))
        if not segs:
            continue
        pts_array = np.asarray(norm_pts, dtype=np.float64)
        vector_paths.append(
            VectorPath(
                points=pts_array,
                pen_id=max(1, min(8, pen_id)),
                closed=is_closed,
                segments=segs,
            )
        )

    return ImportItem(
        name=item_name,
        paths=vector_paths,
        source_path=source_path,
    )
