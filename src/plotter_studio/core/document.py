"""Document model for Plotter Studio."""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Sequence
import numpy as np
from .geometry import Point, BoundingBox, AffineTransform


PAPER_PRESETS: Dict[str, Tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A3": (297.0, 420.0),
    "A2": (420.0, 594.0),
    "A1": (594.0, 841.0),
    "A0": (841.0, 1189.0),
    "Letter": (215.9, 279.4),
}

DEVICE_PROFILES: Dict[str, Dict[str, Any]] = {
    "mutoh_xp500": {
        "name": "Mutoh XP-500 (Rollenplotter)",
        "type": "roller",
        "feed_margin_mm": 25.0,
        "trailing_margin_mm": 5.0,
        "side_margin_mm": 5.0,
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

DEFAULT_EXP_MARGINS = {
    "left": 5.0,
    "right": 5.0,
    "top": 25.0,     # Vorderkante Vorschub
    "bottom": 5.0,   # Hinterkante Vorschub
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
    margin_left_mm: float = 5.0
    margin_right_mm: float = 5.0
    margin_top_mm: float = 25.0
    margin_bottom_mm: float = 5.0

    def __post_init__(self):
        self.apply_preset(self.preset, self.orientation)

    def apply_device_profile(self, profile_key: str, feed_edge: Optional[str] = None):
        """Configure margins according to plotter hardware characteristics."""
        self.device_profile = profile_key
        if feed_edge is not None:
            self.feed_edge = feed_edge

        if profile_key == "mutoh_xp500":
            # 25mm on leading feed edge, 5mm on all other edges
            self.margin_left_mm = 5.0
            self.margin_right_mm = 5.0
            self.margin_top_mm = 5.0
            self.margin_bottom_mm = 5.0
            if self.feed_edge == "top":
                self.margin_top_mm = 25.0
            elif self.feed_edge == "bottom":
                self.margin_bottom_mm = 25.0
            elif self.feed_edge == "left":
                self.margin_left_mm = 25.0
            elif self.feed_edge == "right":
                self.margin_right_mm = 25.0
        elif profile_key == "flatbed_sym":
            self.margin_left_mm = 5.0
            self.margin_right_mm = 5.0
            self.margin_top_mm = 5.0
            self.margin_bottom_mm = 5.0
        elif profile_key == "flatbed_borderless":
            self.margin_left_mm = 0.0
            self.margin_right_mm = 0.0
            self.margin_top_mm = 0.0
            self.margin_bottom_mm = 0.0

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
            self.apply_device_profile(self.device_profile, self.feed_edge)

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


@dataclass
class VectorPath:
    """A vector path as a sequence of (x, y) points in millimeters."""
    points: np.ndarray  # Shape (N, 2), float64
    pen_id: int = 1
    closed: bool = False

    def transformed(self, transform: AffineTransform) -> VectorPath:
        new_pts = transform.transform_coords(self.points)
        return VectorPath(points=new_pts, pen_id=self.pen_id, closed=self.closed)

    @property
    def bounds(self) -> Optional[BoundingBox]:
        if len(self.points) == 0:
            return None
        min_x = float(np.min(self.points[:, 0]))
        min_y = float(np.min(self.points[:, 1]))
        max_x = float(np.max(self.points[:, 0]))
        max_y = float(np.max(self.points[:, 1]))
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
        """Transformed bounding box."""
        if self.original_bounds is None:
            return None
        pts = [
            Point(self.original_bounds.min_x, self.original_bounds.min_y),
            Point(self.original_bounds.max_x, self.original_bounds.min_y),
            Point(self.original_bounds.max_x, self.original_bounds.max_y),
            Point(self.original_bounds.min_x, self.original_bounds.max_y),
        ]
        t_pts = self.transform.transform_points(pts)
        return BoundingBox.from_points(t_pts)

    def set_pen_for_all(self, pen_id: int):
        """Set all paths in this item to a specific pen."""
        for p in self.paths:
            p.pen_id = pen_id


@dataclass
class Document:
    """Plotter Studio root document."""
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
