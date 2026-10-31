"""Document model for LINTO."""

from __future__ import annotations
import copy
import logging
import math
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
from .geometry import (
    Point,
    BoundingBox,
    AffineTransform,
    PathSegment,
    QuadraticBezierSegment,
    CubicBezierSegment,
    ArcSegment,
    compute_segments_bounds,
)

logger = logging.getLogger("linto.core.document")


PAPER_PRESETS: Dict[str, Tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A0": (841.0, 1189.0),
    "Letter": (215.9, 279.4),
}

DEFAULT_EXP_MARGINS: Dict[str, float] = {
    "left": 5.0,
    "right": 5.0,
    "top": 25.0,     # Vorderkante Vorschub
    "bottom": 5.0,   # Hinterkante Vorschub
}

DEVICE_PROFILES: Dict[str, Dict[str, Any]] = {
    "mutoh_xp500": {
        "name": "Mutoh XP-500 (Rollenplotter)",
        "type": "roller",
        "feed_margin_mm": DEFAULT_EXP_MARGINS["top"],
        "trailing_margin_mm": DEFAULT_EXP_MARGINS["bottom"],
        "side_margin_mm": DEFAULT_EXP_MARGINS["left"],
    },
    "flatbed_sym": {
        "name": "Flachbettplotter (Symmetrisch 5 mm)",
        "type": "flatbed",
        "margin_mm": 5.0,
    },
    "flatbed_borderless": {
        "name": "Flachbettplotter (Randlos 0 mm)",
        "type": "flatbed",
        "margin_mm": 0.0,
    },
    "custom": {
        "name": "Benutzerdefiniert (Custom)",
        "type": "custom",
    },
}


@dataclass
class Page:
    """Paper dimensions, device profile and margins in millimeters."""
    preset: str = "A3"
    width_mm: float = 297.0
    height_mm: float = 420.0
    orientation: str = "landscape"  # "landscape" or "portrait"
    device_profile: str = "mutoh_xp500"
    feed_edge: str = "top"  # "top", "bottom", "left", "right"
    margin_profile: str = "exp"
    margin_left_mm: float = 5.0
    margin_right_mm: float = 5.0
    margin_top_mm: float = 25.0
    margin_bottom_mm: float = 5.0

    def __post_init__(self):
        self.apply_preset(self.preset, self.orientation)

    def apply_device_profile(
        self,
        profile_key: str,
        feed_edge: Optional[str] = None,
        margin_profile: str = "",
    ):
        """Configure margins according to plotter hardware characteristics (from YAML profile)."""
        self.device_profile = profile_key
        if feed_edge is not None:
            self.feed_edge = feed_edge
        if margin_profile:
            self.margin_profile = margin_profile

        if profile_key == "flatbed_sym":
            self.margin_left_mm = 5.0
            self.margin_right_mm = 5.0
            self.margin_top_mm = 5.0
            self.margin_bottom_mm = 5.0
            return
        if profile_key == "flatbed_borderless":
            self.margin_left_mm = 0.0
            self.margin_right_mm = 0.0
            self.margin_top_mm = 0.0
            self.margin_bottom_mm = 0.0
            return
        if profile_key == "custom":
            return

        # Load from YAML device profile (Single Source of Truth)
        from ..device.profile import load_profile, get_default_profile
        try:
            dev_prof = load_profile(profile_key)
        except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
            logger.warning("Device profile '%s' could not be loaded (%s); falling back to default.", profile_key, exc)
            dev_prof = get_default_profile()

        eff_margin_profile = margin_profile or self.margin_profile
        lead_m, trail_m, side_l, side_r = dev_prof.get_margins(eff_margin_profile)
        if self.feed_edge == "bottom":
            self.margin_bottom_mm = lead_m
            self.margin_top_mm = trail_m
            self.margin_left_mm = side_l
            self.margin_right_mm = side_r
        elif self.feed_edge == "left":
            self.margin_left_mm = lead_m
            self.margin_right_mm = trail_m
            self.margin_top_mm = side_l
            self.margin_bottom_mm = side_r
        elif self.feed_edge == "right":
            self.margin_right_mm = lead_m
            self.margin_left_mm = trail_m
            self.margin_top_mm = side_l
            self.margin_bottom_mm = side_r
        else:  # "top" (default)
            self.margin_top_mm = lead_m
            self.margin_bottom_mm = trail_m
            self.margin_left_mm = side_l
            self.margin_right_mm = side_r

    def apply_preset(self, preset: str, orientation: Optional[str] = None):
        if orientation is not None:
            self.orientation = orientation
        self.preset = preset
        if preset in PAPER_PRESETS:
            w, h = PAPER_PRESETS[preset]
            if self.orientation == "landscape":
                self.width_mm = max(w, h)
                self.height_mm = min(w, h)
            else:
                self.width_mm = min(w, h)
                self.height_mm = max(w, h)
        if self.device_profile != "custom":
            self.apply_device_profile(self.device_profile, self.feed_edge, self.margin_profile)

    def set_custom_size(self, width_mm: float, height_mm: float):
        self.preset = "Custom"
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.orientation = "landscape" if width_mm >= height_mm else "portrait"

    @property
    def plottable_box(self) -> BoundingBox:
        """Plottable bounding box inside sheet margins."""
        return BoundingBox(
            min_x=self.margin_left_mm,
            min_y=self.margin_top_mm,
            max_x=max(self.margin_left_mm, self.width_mm - self.margin_right_mm),
            max_y=max(self.margin_top_mm, self.height_mm - self.margin_bottom_mm),
        )

    @property
    def sheet_box(self) -> BoundingBox:
        """Physical sheet bounding box (0, 0) to (W, H)."""
        return BoundingBox(0.0, 0.0, self.width_mm, self.height_mm)

    def is_bounds_outside_plottable(self, bounds: BoundingBox, tol_mm: float = 0.5) -> bool:
        """Return True if any edge of bounds exceeds plottable_box by more than tol_mm."""
        pb = self.plottable_box
        return (
            bounds.min_x < pb.min_x - tol_mm
            or bounds.min_y < pb.min_y - tol_mm
            or bounds.max_x > pb.max_x + tol_mm
            or bounds.max_y > pb.max_y + tol_mm
        )

    def apply_probe_result(self, result: Any, tolerance_mm: float = 15.0) -> bool:
        """Update the sheet from a hardware ProbeResult (what the plotter reports wins).

        The plotter reports only the hard-clip window. The sheet is estimated as
        hard-clip + current margins. If that matches a preset (in either orientation)
        within `tolerance_mm`, the preset is used with the detected orientation;
        otherwise a custom size is set.
        """
        if not getattr(result, "success", False):
            return False
        hard_clip_mm = getattr(result, "hard_clip_mm", None)
        if hard_clip_mm:
            clip_w, clip_h = hard_clip_mm
            sheet_w = clip_w + self.margin_left_mm + self.margin_right_mm
            sheet_h = clip_h + self.margin_top_mm + self.margin_bottom_mm
            orientation = "landscape" if sheet_w >= sheet_h else "portrait"
            best: Optional[Tuple[str, float]] = None
            for name, (pw, ph) in PAPER_PRESETS.items():
                long_side, short_side = max(pw, ph), min(pw, ph)
                exp_w, exp_h = (long_side, short_side) if orientation == "landscape" else (short_side, long_side)
                err = max(abs(sheet_w - exp_w), abs(sheet_h - exp_h))
                if err <= tolerance_mm and (best is None or err < best[1]):
                    best = (name, err)
            if best is not None:
                self.apply_preset(best[0], orientation)
            else:
                self.set_custom_size(sheet_w, sheet_h)
            return True
        detected_format = getattr(result, "detected_format", "")
        if detected_format and detected_format in PAPER_PRESETS:
            self.apply_preset(detected_format, self.orientation)
            return True
        return False


@dataclass
class LogicalPen:
    """Logical pen definition (pen slot 1..8)."""
    pen_id: int
    name: str
    color_hex: str
    width_mm: float = 0.35
    speed_cm_s: float = 20.0
    force_g: float = 20.0
    mapped_to: Optional[int] = None  # Non-destructive remapping to another pen
    enabled: bool = True

    @property
    def effective_pen_id(self) -> int:
        """Pen id after dynamic remapping."""
        return self.mapped_to if self.mapped_to is not None else self.pen_id


DEFAULT_PENS: List[LogicalPen] = [
    LogicalPen(1, "Stift 1 (Schwarz)", "#1a1a1a", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(2, "Stift 2 (Rot)", "#d32f2f", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(3, "Stift 3 (Blau)", "#1976d2", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(4, "Stift 4 (Grün)", "#388e3c", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(5, "Stift 5 (Orange)", "#f57c00", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(6, "Stift 6 (Magenta)", "#7b1fa2", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(7, "Stift 7 (Cyan)", "#0097a7", width_mm=0.35, speed_cm_s=20.0),
    LogicalPen(8, "Stift 8 (Gelb)", "#fbc02d", width_mm=0.50, speed_cm_s=15.0),
]


class VectorPath:
    """
    A vector path in millimeters, storing either exact mathematical curve segments
    (`segments`) or a discrete polyline (`points`).
    When constructed with `segments`, curves remain unflattened in the model and are
    only linearized on demand (e.g. during pipeline compilation).
    """
    def __init__(
        self,
        points: Optional[np.ndarray] = None,
        pen_id: int = 1,
        closed: bool = False,
        segments: Optional[List[PathSegment]] = None,
    ):
        self.pen_id: int = pen_id
        self.closed: bool = closed
        self.segments: List[PathSegment] = list(segments) if segments else []
        self._points: Optional[np.ndarray] = (
            np.asarray(points, dtype=np.float64) if points is not None else None
        )

    @property
    def has_curves(self) -> bool:
        """Return True if this path contains Bézier or Arc segments."""
        return any(
            isinstance(s, (QuadraticBezierSegment, CubicBezierSegment, ArcSegment))
            for s in self.segments
        )

    @property
    def points(self) -> np.ndarray:
        """Return polyline points (lazily flattened at default 0.05 mm if segments are stored)."""
        if self._points is not None:
            return self._points
        if self.segments:
            from ..pipeline.flatten import flatten_path_segments
            self._points = flatten_path_segments(self.segments, tolerance=0.05)
            return self._points
        return np.empty((0, 2), dtype=np.float64)

    @points.setter
    def points(self, value: Optional[np.ndarray]):
        self._points = np.asarray(value, dtype=np.float64) if value is not None else None

    def to_polyline(
        self,
        tolerance_mm: float = 0.05,
        transform: Optional[AffineTransform] = None,
    ) -> np.ndarray:
        """
        Convert path to an (N, 2) polyline in millimeters.
        If native segments are present, applies `transform` to the curve primitives first
        and flattens with `tolerance_mm`.
        """
        if self.segments:
            from ..pipeline.flatten import flatten_path_segments
            return flatten_path_segments(self.segments, tolerance=tolerance_mm, transform=transform)
        if self._points is None or len(self._points) == 0:
            return np.empty((0, 2), dtype=np.float64)
        if transform is not None:
            return transform.transform_coords(self._points)
        return self._points

    def transformed(self, transform: AffineTransform) -> VectorPath:
        if self.segments:
            new_segs = [s.transformed(transform) for s in self.segments]
            return VectorPath(pen_id=self.pen_id, closed=self.closed, segments=new_segs)
        new_pts = transform.transform_coords(self.points)
        return VectorPath(points=new_pts, pen_id=self.pen_id, closed=self.closed)

    @property
    def bounds(self) -> Optional[BoundingBox]:
        if self.segments:
            return compute_segments_bounds(self.segments)
        pts = self.points
        if len(pts) == 0:
            return None
        min_x = float(np.min(pts[:, 0]))
        min_y = float(np.min(pts[:, 1]))
        max_x = float(np.max(pts[:, 0]))
        max_y = float(np.max(pts[:, 1]))
        return BoundingBox(min_x, min_y, max_x, max_y)


@dataclass
class ImportItem:
    """An imported graphic (SVG, HP-GL) placed on the canvas."""
    name: str
    paths: List[VectorPath] = field(default_factory=list)
    transform: AffineTransform = field(default_factory=AffineTransform.identity)
    source_path: Optional[str] = None
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    original_bounds: Optional[BoundingBox] = None  # Bounds before item transform
    visible: bool = True
    locked: bool = False
    ignored_text_count: int = 0

    def __post_init__(self):
        if self.original_bounds is None:
            self.recalculate_original_bounds()

    def recalculate_original_bounds(self):
        box: Optional[BoundingBox] = None
        for p in self.paths:
            pb = p.bounds
            if pb is not None:
                box = pb if box is None else box.expanded_to(pb)
        self.original_bounds = box

    @property
    def current_bounds(self) -> Optional[BoundingBox]:
        """Transformed tight bounding box."""
        if self.original_bounds is None:
            return None
        t = self.transform
        # Fast path for axis-aligned transforms (no rotation/shear) or empty paths
        if (abs(t.b) <= 1e-12 and abs(t.c) <= 1e-12) or not self.paths:
            pts = [
                Point(self.original_bounds.min_x, self.original_bounds.min_y),
                Point(self.original_bounds.max_x, self.original_bounds.min_y),
                Point(self.original_bounds.max_x, self.original_bounds.max_y),
                Point(self.original_bounds.min_x, self.original_bounds.max_y),
            ]
            t_pts = t.transform_points(pts)
            return BoundingBox.from_points(t_pts)

        cache_key = (
            t.a, t.b, t.c, t.d, t.tx, t.ty,
            len(self.paths),
            self.original_bounds.min_x,
            self.original_bounds.min_y,
            self.original_bounds.max_x,
            self.original_bounds.max_y,
        )
        if getattr(self, "_cached_bounds_key", None) == cache_key:
            return getattr(self, "_cached_bounds", None)

        box: Optional[BoundingBox] = None
        for p in self.paths:
            if p.segments:
                pb = compute_segments_bounds([s.transformed(t) for s in p.segments])
            else:
                pts_arr = p.points
                if len(pts_arr) == 0:
                    pb = None
                else:
                    t_arr = t.transform_coords(pts_arr)
                    pb = BoundingBox(
                        float(np.min(t_arr[:, 0])),
                        float(np.min(t_arr[:, 1])),
                        float(np.max(t_arr[:, 0])),
                        float(np.max(t_arr[:, 1])),
                    )
            if pb is not None:
                box = pb if box is None else box.expanded_to(pb)

        self._cached_bounds_key = cache_key
        self._cached_bounds = box
        return box

    @property
    def scale_percent(self) -> float:
        """Return current X scale factor in percent."""
        return math.hypot(self.transform.a, self.transform.b) * 100.0

    @property
    def rotation_degrees(self) -> float:
        """Return current rotation angle in degrees."""
        return math.degrees(math.atan2(self.transform.b, self.transform.a))

    def set_pen_for_all(self, pen_id: int):
        """Set all paths in this item to a specific pen."""
        for p in self.paths:
            p.pen_id = pen_id


@dataclass
class Document:
    """LINTO root document."""
    page: Page = field(default_factory=Page)
    pens: List[LogicalPen] = field(default_factory=lambda: [LogicalPen(**vars(p)) for p in DEFAULT_PENS])
    items: List[ImportItem] = field(default_factory=list)

    def get_pen(self, pen_id: int) -> Optional[LogicalPen]:
        for p in self.pens:
            if p.pen_id == pen_id:
                return p
        return None

    def remap_all_to_pen(self, target_pen_id: int):
        """Monochrome plot: all pens mapped to one."""
        for p in self.pens:
            p.mapped_to = target_pen_id

    def reset_remapping(self):
        """Restore 1:1 pen mapping."""
        for p in self.pens:
            p.mapped_to = None

    def find_item(self, item_id: str) -> Optional[ImportItem]:
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None

    def remove_item(self, item_id: str) -> bool:
        for idx, item in enumerate(self.items):
            if item.item_id == item_id:
                del self.items[idx]
                return True
        return False

    def duplicate_item(self, item: ImportItem, offset_mm: float = 10.0) -> ImportItem:
        """Create a duplicate of an item offset by (offset_mm, offset_mm) and append to document."""
        new_paths = []
        for p in item.paths:
            new_paths.append(VectorPath(
                points=np.copy(p._points) if p._points is not None else None,
                pen_id=p.pen_id,
                closed=p.closed,
                segments=list(p.segments) if p.segments else None,
            ))
        new_transform = copy.deepcopy(item.transform)
        new_transform.tx += offset_mm
        new_transform.ty += offset_mm

        new_name = f"{item.name} (Kopie)"
        new_item = ImportItem(
            name=new_name,
            paths=new_paths,
            transform=new_transform,
            source_path=item.source_path,
            visible=item.visible,
            locked=False,
        )
        self.items.append(new_item)
        return new_item

    def move_item_up(self, item_id: str) -> bool:
        """Move item one step up in z-order (drawn later / on top)."""
        for i, it in enumerate(self.items):
            if it.item_id == item_id:
                if i < len(self.items) - 1:
                    self.items[i], self.items[i + 1] = self.items[i + 1], self.items[i]
                    return True
                return False
        return False

    def move_item_down(self, item_id: str) -> bool:
        """Move item one step down in z-order (drawn earlier / below)."""
        for i, it in enumerate(self.items):
            if it.item_id == item_id:
                if i > 0:
                    self.items[i], self.items[i - 1] = self.items[i - 1], self.items[i]
                    return True
                return False
        return False
