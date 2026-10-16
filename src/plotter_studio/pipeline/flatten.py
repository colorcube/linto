"""Bézier and arc curve flattening with chordal tolerance in millimeters."""

from __future__ import annotations
import math
from typing import List, Tuple, Sequence, Optional
import numpy as np
from ..core.geometry import (
    AffineTransform,
    PathSegment,
    LineSegment,
    QuadraticBezierSegment,
    CubicBezierSegment,
    ArcSegment,
    point_segment_distance as point_line_distance,
)


def flatten_cubic_bezier(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    p3: Tuple[float, float],
    tolerance: float = 0.05,
    max_depth: int = 12,
) -> List[Tuple[float, float]]:
    """
    Adaptive subdivision of a cubic Bézier curve using de Casteljau's algorithm.
    Returns list of points from p0 to p3.
    """
    points: List[Tuple[float, float]] = [p0]

    def subdivide(
        x0: float, y0: float,
        x1: float, y1: float,
        x2: float, y2: float,
        x3: float, y3: float,
        depth: int,
    ):
        d1 = point_line_distance(x1, y1, x0, y0, x3, y3)
        d2 = point_line_distance(x2, y2, x0, y0, x3, y3)
        if (d1 <= tolerance and d2 <= tolerance) or depth >= max_depth:
            points.append((x3, y3))
            return

        # de Casteljau split at t=0.5
        x01 = (x0 + x1) * 0.5
        y01 = (y0 + y1) * 0.5
        x12 = (x1 + x2) * 0.5
        y12 = (y1 + y2) * 0.5
        x23 = (x2 + x3) * 0.5
        y23 = (y2 + y3) * 0.5

        x012 = (x01 + x12) * 0.5
        y012 = (y01 + y12) * 0.5
        x123 = (x12 + x23) * 0.5
        y123 = (y12 + y23) * 0.5

        x0123 = (x012 + x123) * 0.5
        y0123 = (y012 + y123) * 0.5

        subdivide(x0, y0, x01, y01, x012, y012, x0123, y0123, depth + 1)
        subdivide(x0123, y0123, x123, y123, x23, y23, x3, y3, depth + 1)

    subdivide(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], 0)
    return points


def flatten_quadratic_bezier(
    p0: Tuple[float, float],
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    tolerance: float = 0.05,
    max_depth: int = 12,
) -> List[Tuple[float, float]]:
    """Adaptive subdivision of a quadratic Bézier curve."""
    points: List[Tuple[float, float]] = [p0]

    def subdivide(
        x0: float, y0: float,
        x1: float, y1: float,
        x2: float, y2: float,
        depth: int,
    ):
        d = point_line_distance(x1, y1, x0, y0, x2, y2)
        if d <= tolerance or depth >= max_depth:
            points.append((x2, y2))
            return

        x01 = (x0 + x1) * 0.5
        y01 = (y0 + y1) * 0.5
        x12 = (x1 + x2) * 0.5
        y12 = (y1 + y2) * 0.5
        x012 = (x01 + x12) * 0.5
        y012 = (y01 + y12) * 0.5

        subdivide(x0, y0, x01, y01, x012, y012, depth + 1)
        subdivide(x012, y012, x12, y12, x2, y2, depth + 1)

    subdivide(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], 0)
    return points


def flatten_arc(
    cx: float, cy: float, rx: float, ry: float,
    start_angle_rad: float, sweep_angle_rad: float,
    tolerance: float = 0.05,
    rotation_rad: float = 0.0,
) -> List[Tuple[float, float]]:
    """Flatten an elliptical or circular arc into points with chord tolerance."""
    r_max = max(rx, ry)
    if r_max < 1e-6:
        return [(cx, cy)]

    # Maximum angular step based on chordal error: e = R * (1 - cos(theta / 2))
    # cos(theta / 2) = 1 - e / R
    cos_half_theta = max(-1.0, min(1.0, 1.0 - (max(1e-5, tolerance) / max(1e-3, r_max))))
    theta_step = 2.0 * math.acos(cos_half_theta)
    theta_step = max(math.radians(1.0), min(math.radians(30.0), theta_step))

    num_steps = max(4, int(math.ceil(abs(sweep_angle_rad) / theta_step)))
    actual_step = sweep_angle_rad / num_steps
    cos_phi = math.cos(rotation_rad)
    sin_phi = math.sin(rotation_rad)

    points: List[Tuple[float, float]] = []
    for i in range(num_steps + 1):
        a = start_angle_rad + i * actual_step
        ex = rx * math.cos(a)
        ey = ry * math.sin(a)
        px = cx + ex * cos_phi - ey * sin_phi
        py = cy + ex * sin_phi + ey * cos_phi
        points.append((px, py))

    return points


def flatten_segment(seg: PathSegment, tolerance: float = 0.05) -> List[Tuple[float, float]]:
    """Flatten a single geometric PathSegment into (x, y) points in millimeters."""
    tol = max(1e-4, tolerance)
    if isinstance(seg, LineSegment):
        return [seg.start, seg.end]
    elif isinstance(seg, QuadraticBezierSegment):
        return flatten_quadratic_bezier(seg.start, seg.control, seg.end, tolerance=tol)
    elif isinstance(seg, CubicBezierSegment):
        return flatten_cubic_bezier(seg.start, seg.control1, seg.control2, seg.end, tolerance=tol)
    elif isinstance(seg, ArcSegment):
        if seg.rx > 1e-6 and seg.ry > 1e-6 and abs(seg.sweep_angle_rad) > 1e-6:
            pts = flatten_arc(
                seg.center[0],
                seg.center[1],
                seg.rx,
                seg.ry,
                seg.start_angle_rad,
                seg.sweep_angle_rad,
                tolerance=tol,
                rotation_rad=seg.rotation_rad,
            )
            pts[0] = seg.start
            pts[-1] = seg.end
            return pts
        elif seg.cubics:
            out: List[Tuple[float, float]] = []
            for c in seg.cubics:
                c_pts = flatten_cubic_bezier(c.start, c.control1, c.control2, c.end, tolerance=tol)
                if not out:
                    out.extend(c_pts)
                else:
                    out.extend(c_pts[1:])
            return out
        return [seg.start, seg.end]
    return []


def flatten_path_segments(
    segments: Sequence[PathSegment],
    tolerance: float = 0.05,
    transform: Optional[AffineTransform] = None,
) -> np.ndarray:
    """
    Transform and flatten a sequence of PathSegments into an (N, 2) polyline array.
    Applying the transform to the mathematical curve primitives before subdivision
    ensures chordal accuracy at any scale factor.
    """
    if not segments:
        return np.empty((0, 2), dtype=np.float64)

    pts: List[Tuple[float, float]] = []
    for seg in segments:
        t_seg = seg.transformed(transform) if transform is not None else seg
        seg_pts = flatten_segment(t_seg, tolerance=tolerance)
        if not seg_pts:
            continue
        if not pts:
            pts.extend(seg_pts)
        else:
            pts.extend(seg_pts[1:])

    if not pts:
        return np.empty((0, 2), dtype=np.float64)
    return np.array(pts, dtype=np.float64)

