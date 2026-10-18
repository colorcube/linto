"""SVG Import parser converting vector graphics into millimeter VectorPaths."""

from __future__ import annotations
import io
import math
import os
import re
from pathlib import Path
from typing import List, Tuple, Optional
import svgelements
from .geometry import (
    PathSegment,
    LineSegment,
    QuadraticBezierSegment,
    CubicBezierSegment,
    ArcSegment,
)
from .document import VectorPath, ImportItem, DEFAULT_PENS
from .color_cluster import cluster_colors_to_pens, rgb_to_hex


# Conversion factor: 1 px at 96 DPI = 25.4 / 96.0 mm ≈ 0.26458333 mm
PX_TO_MM = 25.4 / 96.0


def _clean_duplicate_attributes(svg_text: str) -> str:
    """Remove duplicate XML attributes on the same tag (e.g. duplicate xmlns declarations)."""
    def dedupe_tag(match):
        tag_content = match.group(0)
        seen = set()
        out = []
        tag_name_match = re.match(r"^<([a-zA-Z0-9_\-:]+)", tag_content)
        if not tag_name_match:
            return tag_content
        out.append("<" + tag_name_match.group(1))
        rest = tag_content[len(tag_name_match.group(0)):]

        attr_regex = re.compile(r"([a-zA-Z0-9_\-:]+)\s*=\s*(\"[^\"]*\"|'[^']*')")
        for m in attr_regex.finditer(rest):
            attr_name = m.group(1)
            attr_val = m.group(2)
            if attr_name not in seen:
                seen.add(attr_name)
                out.append(f" {attr_name}={attr_val}")
        if tag_content.rstrip().endswith("/>"):
            out.append(" />")
        elif tag_content.rstrip().endswith(">"):
            out.append(">")
        return "".join(out)

    return re.sub(r"<[a-zA-Z0-9_\-:]+[^>]*>", dedupe_tag, svg_text)


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


def svg_segment_to_model(
    seg: svgelements.PathSegment,
    scale_mm: float = 1.0,
) -> Optional[PathSegment]:
    """Convert an svgelements PathSegment into a lossless millimeter PathSegment primitive."""
    if isinstance(seg, svgelements.Line):
        if seg.start is None or seg.end is None:
            return None
        p0 = (float(seg.start.x) * scale_mm, float(seg.start.y) * scale_mm)
        p1 = (float(seg.end.x) * scale_mm, float(seg.end.y) * scale_mm)
        if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 1e-9:
            return None
        return LineSegment(start=p0, end=p1)
    elif isinstance(seg, svgelements.QuadraticBezier):
        if seg.start is None or seg.control is None or seg.end is None:
            return None
        return QuadraticBezierSegment(
            start=(float(seg.start.x) * scale_mm, float(seg.start.y) * scale_mm),
            control=(float(seg.control.x) * scale_mm, float(seg.control.y) * scale_mm),
            end=(float(seg.end.x) * scale_mm, float(seg.end.y) * scale_mm),
        )
    elif isinstance(seg, svgelements.CubicBezier):
        if seg.start is None or seg.control1 is None or seg.control2 is None or seg.end is None:
            return None
        return CubicBezierSegment(
            start=(float(seg.start.x) * scale_mm, float(seg.start.y) * scale_mm),
            control1=(float(seg.control1.x) * scale_mm, float(seg.control1.y) * scale_mm),
            control2=(float(seg.control2.x) * scale_mm, float(seg.control2.y) * scale_mm),
            end=(float(seg.end.x) * scale_mm, float(seg.end.y) * scale_mm),
        )
    elif isinstance(seg, svgelements.Arc):
        if seg.start is None or seg.end is None:
            return None
        cubics = tuple(
            CubicBezierSegment(
                start=(float(c.start.x) * scale_mm, float(c.start.y) * scale_mm),
                control1=(float(c.control1.x) * scale_mm, float(c.control1.y) * scale_mm),
                control2=(float(c.control2.x) * scale_mm, float(c.control2.y) * scale_mm),
                end=(float(c.end.x) * scale_mm, float(c.end.y) * scale_mm),
            )
            for c in seg.as_cubic_curves()
        )
        cx = float(seg.center.x) * scale_mm if getattr(seg, "center", None) is not None else 0.0
        cy = float(seg.center.y) * scale_mm if getattr(seg, "center", None) is not None else 0.0
        rx = float(seg.rx or 0.0) * scale_mm
        ry = float(seg.ry or 0.0) * scale_mm
        rot_rad = float(seg.get_rotation()) if hasattr(seg, "get_rotation") else 0.0
        start_t = float(seg.get_start_t()) if hasattr(seg, "get_start_t") else 0.0
        sweep_rad = float(seg.sweep or 0.0)
        return ArcSegment(
            start=(float(seg.start.x) * scale_mm, float(seg.start.y) * scale_mm),
            end=(float(seg.end.x) * scale_mm, float(seg.end.y) * scale_mm),
            center=(cx, cy),
            rx=rx,
            ry=ry,
            rotation_rad=rot_rad,
            start_angle_rad=start_t,
            sweep_angle_rad=sweep_rad,
            large_arc=abs(sweep_rad) > math.pi,
            sweep=sweep_rad > 0.0,
            cubics=cubics,
        )
    elif isinstance(seg, svgelements.Close):
        if seg.start is not None and seg.end is not None:
            p0 = (float(seg.start.x) * scale_mm, float(seg.start.y) * scale_mm)
            p1 = (float(seg.end.x) * scale_mm, float(seg.end.y) * scale_mm)
            if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > 1e-6:
                return LineSegment(start=p0, end=p1)
        return None
    return None


def segment_to_points(
    seg: svgelements.PathSegment,
    scale_mm: float,
    tolerance_mm: float = 0.05,
) -> List[Tuple[float, float]]:
    """Convert an svgelements path segment into a list of (x, y) coordinates in mm."""
    model_seg = svg_segment_to_model(seg, scale_mm=scale_mm)
    if model_seg is None:
        return []
    from ..pipeline.flatten import flatten_segment
    return flatten_segment(model_seg, tolerance=tolerance_mm)


def extract_subpath_segments(
    p: svgelements.Path,
    scale_mm: float = 1.0,
) -> List[Tuple[List[PathSegment], bool]]:
    """Extract subpaths from an svgelements.Path as lists of unflattened PathSegments."""
    subpaths: List[Tuple[List[PathSegment], bool]] = []
    current_segments: List[PathSegment] = []
    is_closed = False

    for seg in p:
        if isinstance(seg, svgelements.Move):
            if current_segments:
                subpaths.append((current_segments, is_closed))
            current_segments = []
            is_closed = False
        elif isinstance(seg, svgelements.Close):
            close_seg = svg_segment_to_model(seg, scale_mm=scale_mm)
            if close_seg is not None:
                current_segments.append(close_seg)
            if current_segments:
                is_closed = True
                subpaths.append((current_segments, is_closed))
                current_segments = []
                is_closed = False
        else:
            model_seg = svg_segment_to_model(seg, scale_mm=scale_mm)
            if model_seg is not None:
                current_segments.append(model_seg)

    if current_segments:
        subpaths.append((current_segments, is_closed))

    return subpaths


def parse_svg_tolerant(filepath_or_data: str) -> svgelements.SVG:
    """Parse an SVG file path or XML string via svgelements, healing duplicate XML attributes on retry."""
    is_file = os.path.exists(filepath_or_data)
    try:
        if is_file:
            return svgelements.SVG.parse(filepath_or_data)
        return svgelements.SVG.parse(io.StringIO(filepath_or_data))
    except Exception as e:
        if "duplicate attribute" in str(e).lower():
            raw = (
                Path(filepath_or_data).read_text(encoding="utf-8", errors="replace")
                if is_file
                else filepath_or_data
            )
            cleaned = _clean_duplicate_attributes(raw)
            return svgelements.SVG.parse(io.StringIO(cleaned))
        raise


def load_svg(
    filepath_or_data: str,
    tolerance_mm: float = 0.05,
    name: Optional[str] = None,
    pen_palette: Optional[List[Tuple[int, str]]] = None,
) -> ImportItem:
    """
    Load an SVG file and convert into an ImportItem with exact VectorPath curve segments
    in millimeters (no premature curve flattening on import).
    """
    if os.path.exists(filepath_or_data):
        item_name = name or os.path.splitext(os.path.basename(filepath_or_data))[0]
        source_path = filepath_or_data
    else:
        item_name = name or "Import"
        source_path = None
    svg = parse_svg_tolerant(filepath_or_data)

    # Determine scale to millimeters
    # Default: svgelements coordinates are in pixels at 96 DPI
    scale_mm = PX_TO_MM

    # Collect raw paths as native geometric segments and their stroke colors
    raw_subpaths: List[Tuple[List[PathSegment], str, bool]] = []
    found_colors: List[str] = []

    for elem in svg.elements():
        if isinstance(elem, (svgelements.Path, svgelements.Shape)):
            # Convert shapes (circle, rect, line, etc.) to Path
            p = svgelements.Path(elem) if not isinstance(elem, svgelements.Path) else elem
            color = extract_stroke_color(elem)
            found_colors.append(color)

            for segs, is_closed in extract_subpath_segments(p, scale_mm=scale_mm):
                raw_subpaths.append((segs, color, is_closed))

    # Cluster colors to pens
    if pen_palette is None:
        pen_palette = [(p.pen_id, p.color_hex) for p in DEFAULT_PENS]

    color_to_pen = cluster_colors_to_pens(found_colors, pen_palette, max_pens=8)

    # Build VectorPaths with exact curve segments
    vector_paths: List[VectorPath] = []
    for segs, col, closed in raw_subpaths:
        pen_id = color_to_pen.get(col, 1)
        vector_paths.append(VectorPath(pen_id=pen_id, closed=closed, segments=segs))

    item = ImportItem(
        name=item_name,
        paths=vector_paths,
        source_path=source_path,
    )
    return item

