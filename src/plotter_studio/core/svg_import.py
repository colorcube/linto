"""SVG Import parser converting vector graphics into millimeter VectorPaths."""

from __future__ import annotations
import os
import math
from typing import List, Tuple, Dict, Optional
import numpy as np
import svgelements
from .geometry import Point, BoundingBox, AffineTransform
from .document import VectorPath, ImportItem, DEFAULT_PENS
from .color_cluster import cluster_colors_to_pens, rgb_to_hex
from ..pipeline.flatten import flatten_cubic_bezier, flatten_quadratic_bezier


# Conversion factor: 1 px at 96 DPI = 25.4 / 96.0 mm ≈ 0.26458333 mm
PX_TO_MM = 25.4 / 96.0


def extract_stroke_color(element: svgelements.SVGElement) -> str:
    """Extract stroke color as #rrggbb hex string."""
    col = getattr(element, "stroke", None)
    if col is not None and col != "none" and col.value is not None:
        if isinstance(col, svgelements.Color):
            return rgb_to_hex(col.red, col.green, col.blue)
    fill = getattr(element, "fill", None)
    if fill is not None and fill != "none" and fill.value is not None:
        if isinstance(fill, svgelements.Color):
            return rgb_to_hex(fill.red, fill.green, fill.blue)
    return "#1a1a1a"


def segment_to_points(
    seg: svgelements.PathSegment,
    scale_mm: float,
    tolerance_mm: float = 0.05,
) -> List[Tuple[float, float]]:
    """Convert an svgelements path segment into a list of (x, y) coordinates in mm."""
    if isinstance(seg, svgelements.Line):
        return [
            (seg.start.x * scale_mm, seg.start.y * scale_mm),
            (seg.end.x * scale_mm, seg.end.y * scale_mm),
        ]
    elif isinstance(seg, svgelements.CubicBezier):
        p0 = (seg.start.x * scale_mm, seg.start.y * scale_mm)
        p1 = (seg.control1.x * scale_mm, seg.control1.y * scale_mm)
        p2 = (seg.control2.x * scale_mm, seg.control2.y * scale_mm)
        p3 = (seg.end.x * scale_mm, seg.end.y * scale_mm)
        return flatten_cubic_bezier(p0, p1, p2, p3, tolerance=tolerance_mm)
    elif isinstance(seg, svgelements.QuadraticBezier):
        p0 = (seg.start.x * scale_mm, seg.start.y * scale_mm)
        p1 = (seg.control1.x * scale_mm, seg.control1.y * scale_mm)
        p2 = (seg.end.x * scale_mm, seg.end.y * scale_mm)
        return flatten_quadratic_bezier(p0, p1, p2, tolerance=tolerance_mm)
    elif isinstance(seg, svgelements.Arc):
        # Sample arc based on chordal error e: step = 2 * acos(1 - e / R)
        rx = getattr(seg, "rx", None)
        ry = getattr(seg, "ry", None)
        r_approx = max(float(rx or 10.0), float(ry or 10.0)) * scale_mm
        cos_val = max(-1.0, min(1.0, 1.0 - (tolerance_mm / max(1.0, r_approx))))
        step_angle = max(math.radians(2.0), min(math.radians(30.0), 2.0 * math.acos(cos_val)))
        
        # Estimate sweep angle from length
        arc_len_mm = seg.length() * scale_mm
        sweep_est = arc_len_mm / max(0.1, r_approx)
        num_steps = max(4, min(360, int(math.ceil(sweep_est / step_angle))))
        
        pts: List[Tuple[float, float]] = []
        for i in range(num_steps + 1):
            t = i / float(num_steps)
            pt = seg.point(t)
            pts.append((pt.x * scale_mm, pt.y * scale_mm))
        return pts
    elif isinstance(seg, svgelements.Close):
        if seg.start and seg.end:
            return [
                (seg.start.x * scale_mm, seg.start.y * scale_mm),
                (seg.end.x * scale_mm, seg.end.y * scale_mm),
            ]
        return []
    return []


def load_svg(
    filepath_or_data: str,
    tolerance_mm: float = 0.05,
    name: Optional[str] = None,
    pen_palette: Optional[List[Tuple[int, str]]] = None,
) -> ImportItem:
    """
    Load an SVG file and convert into an ImportItem with VectorPaths in millimeters.
    """
    if os.path.exists(filepath_or_data):
        item_name = name or os.path.splitext(os.path.basename(filepath_or_data))[0]
        source_path = filepath_or_data
        svg = svgelements.SVG.parse(filepath_or_data)
    else:
        item_name = name or "Import"
        source_path = None
        import io
        svg = svgelements.SVG.parse(io.StringIO(filepath_or_data))

    # Determine scale to millimeters
    # Default: svgelements coordinates are in pixels at 96 DPI
    scale_mm = PX_TO_MM

    # Collect raw paths and their stroke colors
    raw_subpaths: List[Tuple[List[Tuple[float, float]], str, bool]] = []
    found_colors: List[str] = []

    for elem in svg.elements():
        if isinstance(elem, (svgelements.Path, svgelements.Shape)):
            # Convert shapes (circle, rect, line, etc.) to Path
            p = svgelements.Path(elem) if not isinstance(elem, svgelements.Path) else elem
            color = extract_stroke_color(elem)
            found_colors.append(color)

            current_points: List[Tuple[float, float]] = []
            is_closed = False

            for seg in p:
                if isinstance(seg, svgelements.Move):
                    if len(current_points) >= 2:
                        raw_subpaths.append((current_points, color, is_closed))
                    current_points = [(seg.end.x * scale_mm, seg.end.y * scale_mm)]
                    is_closed = False
                elif isinstance(seg, svgelements.Close):
                    if len(current_points) >= 2:
                        pts = segment_to_points(seg, scale_mm, tolerance_mm)
                        if pts:
                            current_points.append(pts[-1])
                        is_closed = True
                        raw_subpaths.append((current_points, color, is_closed))
                        current_points = []
                else:
                    pts = segment_to_points(seg, scale_mm, tolerance_mm)
                    if pts:
                        if not current_points:
                            current_points.extend(pts)
                        else:
                            # Avoid duplicate start point
                            current_points.extend(pts[1:])

            if len(current_points) >= 2:
                raw_subpaths.append((current_points, color, is_closed))

    # Cluster colors to pens
    if pen_palette is None:
        pen_palette = [(p.pen_id, p.color_hex) for p in DEFAULT_PENS]

    color_to_pen = cluster_colors_to_pens(found_colors, pen_palette, max_pens=8)

    # Build VectorPaths
    vector_paths: List[VectorPath] = []
    for pts, col, closed in raw_subpaths:
        pen_id = color_to_pen.get(col, 1)
        arr = np.array(pts, dtype=np.float64)
        vector_paths.append(VectorPath(points=arr, pen_id=pen_id, closed=closed))

    item = ImportItem(
        name=item_name,
        paths=vector_paths,
        source_path=source_path,
    )
    return item
