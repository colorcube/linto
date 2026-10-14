"""Color clustering and palette matching for mapping SVG stroke colors to pens."""

from __future__ import annotations
import math
from typing import List, Tuple, Dict


def hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """Convert hex string (e.g. '#ff0000', 'rgb(255,0,0)', or 'red') to (R, G, B) 0..255."""
    s = hex_str.strip().lstrip("#")
    if len(s) == 3:
        s = "".join([c * 2 for c in s])
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    return (0, 0, 0)


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_to_xyz(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    """Convert sRGB to CIE XYZ."""
    def pivot(c: float) -> float:
        c = c / 255.0
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92

    r, g, b = [pivot(v) for v in rgb]
    x = r * 0.4124 + g * 0.3576 + b * 0.1805
    y = r * 0.2126 + g * 0.7152 + b * 0.0722
    z = r * 0.0193 + g * 0.1192 + b * 0.9505
    return (x, y, z)


def xyz_to_lab(xyz: Tuple[float, float, float]) -> Tuple[float, float, float]:
    """Convert CIE XYZ to CIE L*a*b* (D65 standard illuminant)."""
    # D65 reference white
    xn, yn, zn = 0.95047, 1.00000, 1.08883
    x, y, z = xyz[0] / xn, xyz[1] / yn, xyz[2] / zn

    def pivot(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 0.008856 else (7.787 * t) + (16.0 / 116.0)

    fx, fy, fz = pivot(x), pivot(y), pivot(z)
    L = (116.0 * fy) - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return (L, a, b)


def rgb_to_lab(rgb: Tuple[int, int, int]) -> Tuple[float, float, float]:
    return xyz_to_lab(rgb_to_xyz(rgb))


def rgb_hex_to_lab(hex_str: str) -> Tuple[float, float, float]:
    """Direct conversion from hex string to CIE L*a*b*."""
    return rgb_to_lab(hex_to_rgb(hex_str))


def delta_e(lab1: Tuple[float, float, float], lab2: Tuple[float, float, float]) -> float:
    """CIE76 Euclidean distance in Lab color space (perceptual difference)."""
    return math.hypot(lab1[0] - lab2[0], lab1[1] - lab2[1], lab1[2] - lab2[2])


color_delta_e = delta_e


def cluster_colors_to_pens(
    colors: List[str],
    pen_palette: List[Tuple[int, str]],  # List of (pen_id, hex_color)
    max_pens: int = 8,
) -> Dict[str, int]:
    """
    Map a list of arbitrary hex colors to pen_ids (1..8).
    Returns dict mapping hex_color -> pen_id.
    """
    distinct_colors = list(dict.fromkeys(colors))  # Preserve order, unique
    if not distinct_colors:
        return {}

    palette_labs = [
        (pen_id, rgb_to_lab(hex_to_rgb(hex_col)))
        for pen_id, hex_col in pen_palette[:max_pens]
    ]

    mapping: Dict[str, int] = {}

    # If colors <= available pens, assign sequentially or match to closest
    if len(distinct_colors) <= len(palette_labs):
        # 1:1 mapping: each distinct color gets a unique pen
        for idx, col in enumerate(distinct_colors):
            mapping[col] = palette_labs[idx][0]
    else:
        # More colors than pens: find closest palette pen via Delta E in Lab space
        for col in distinct_colors:
            col_lab = rgb_to_lab(hex_to_rgb(col))
            best_pen = palette_labs[0][0]
            min_dist = float("inf")
            for pen_id, p_lab in palette_labs:
                dist = delta_e(col_lab, p_lab)
                if dist < min_dist:
                    min_dist = dist
                    best_pen = pen_id
            mapping[col] = best_pen

    return mapping
