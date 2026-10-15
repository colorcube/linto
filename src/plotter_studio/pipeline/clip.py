"""Polyline box clipping (Cohen-Sutherland algorithm)."""

from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np

# Cohen-Sutherland outcode bit flags
INSIDE = 0  # 0000
LEFT   = 1  # 0001
RIGHT  = 2  # 0010
BOTTOM = 4  # 0100
TOP    = 8  # 1000


def _compute_outcode(x: float, y: float, xmin: float, ymin: float, xmax: float, ymax: float) -> int:
    code = INSIDE
    if x < xmin:
        code |= LEFT
    elif x > xmax:
        code |= RIGHT
    if y < ymin:
        code |= BOTTOM
    elif y > ymax:
        code |= TOP
    return code


def clip_segment(
    x0: float, y0: float, x1: float, y1: float,
    xmin: float, ymin: float, xmax: float, ymax: float,
) -> Optional[Tuple[float, float, float, float]]:
    """Clip a 2D line segment (x0, y0)-(x1, y1) against [xmin, ymin, xmax, ymax]."""
    outcode0 = _compute_outcode(x0, y0, xmin, ymin, xmax, ymax)
    outcode1 = _compute_outcode(x1, y1, xmin, ymin, xmax, ymax)

    accept = False

    while True:
        if (outcode0 | outcode1) == 0:
            # Bitwise OR is 0: both points inside
            accept = True
            break
        elif (outcode0 & outcode1) != 0:
            # Bitwise AND is not 0: both points in the same outside region
            break
        else:
            # At least one point is outside
            outcode_out = outcode0 if outcode0 != 0 else outcode1

            if outcode_out & TOP:
                x = x0 + (x1 - x0) * (ymax - y0) / (y1 - y0)
                y = ymax
            elif outcode_out & BOTTOM:
                x = x0 + (x1 - x0) * (ymin - y0) / (y1 - y0)
                y = ymin
            elif outcode_out & RIGHT:
                y = y0 + (y1 - y0) * (xmax - x0) / (x1 - x0)
                x = xmax
            elif outcode_out & LEFT:
                y = y0 + (y1 - y0) * (xmin - x0) / (x1 - x0)
                x = xmin
            else:
                x, y = x0, y0

            if outcode_out == outcode0:
                x0, y0 = x, y
                outcode0 = _compute_outcode(x0, y0, xmin, ymin, xmax, ymax)
            else:
                x1, y1 = x, y
                outcode1 = _compute_outcode(x1, y1, xmin, ymin, xmax, ymax)

    if accept:
        return (x0, y0, x1, y1)
    return None


def clip_polyline_to_box(
    points: np.ndarray,
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> List[np.ndarray]:
    """
    Clip an (N, 2) polyline against [xmin, ymin, xmax, ymax].
    May return zero, one, or multiple polylines if lines leave and re-enter the box.
    """
    if len(points) < 2:
        return []

    result: List[np.ndarray] = []
    current_line: List[Tuple[float, float]] = []

    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        clipped = clip_segment(p0[0], p0[1], p1[0], p1[1], xmin, ymin, xmax, ymax)

        if clipped is not None:
            cx0, cy0, cx1, cy1 = clipped
            if not current_line:
                current_line = [(cx0, cy0), (cx1, cy1)]
            else:
                last_pt = current_line[-1]
                # Check if this segment connects to the previous one
                if abs(last_pt[0] - cx0) < 1e-4 and abs(last_pt[1] - cy0) < 1e-4:
                    current_line.append((cx1, cy1))
                else:
                    if len(current_line) >= 2:
                        result.append(np.array(current_line, dtype=np.float64))
                    current_line = [(cx0, cy0), (cx1, cy1)]
        else:
            if len(current_line) >= 2:
                result.append(np.array(current_line, dtype=np.float64))
            current_line = []

    if len(current_line) >= 2:
        result.append(np.array(current_line, dtype=np.float64))

    return result


def clip_polylines_to_box(
    lines: List[np.ndarray],
    xmin: float,
    ymin: float,
    xmax: float,
    ymax: float,
) -> List[np.ndarray]:
    """Clip a list of polylines against a bounding box."""
    clipped_list: List[np.ndarray] = []
    for line in lines:
        for sub_line in clip_polyline_to_box(line, xmin, ymin, xmax, ymax):
            if len(sub_line) >= 2:
                clipped_list.append(sub_line)
    return clipped_list
