"""SVG recorder for Virtual Plotter paths.

Converts recorded polylines from VirtualPlotter into a true-to-scale SVG document.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .virtual_plotter import VirtualPlotter

# Default pen colors for pens 1..8
PEN_PALETTE = {
    1: "#000000",  # Black
    2: "#d32f2f",  # Red
    3: "#1976d2",  # Blue
    4: "#388e3c",  # Green
    5: "#f57c00",  # Orange
    6: "#7b1fa2",  # Purple
    7: "#0097a7",  # Cyan
    8: "#c2185b",  # Magenta
}


def export_plotter_svg(plotter: VirtualPlotter, target_path: str | Path) -> None:
    """Export the recorded lines of the VirtualPlotter as a stand-alone SVG file."""
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    w = plotter.sheet_width_mm
    h = plotter.sheet_height_mm

    top_m, bottom_m, left_m, right_m = plotter.margins_mm
    hard_clip_w = plotter.plottable_width_mm
    hard_clip_h = plotter.plottable_height_mm

    # Center of hard-clip window in sheet coordinates
    center_x = left_m + (hard_clip_w / 2.0)
    center_y = top_m + (hard_clip_h / 2.0)

    # Flush any currently open polyline
    plotter._flush_current_polyline()

    svg_parts: list[str] = [
        f'<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{w}mm" height="{h}mm" viewBox="0 0 {w:.2f} {h:.2f}">',
        f'  <defs>',
        f'    <style>',
        f'      .sheet-border {{ fill: #ffffff; stroke: #cccccc; stroke-width: 0.5; }}',
        f'      .hard-clip {{ fill: none; stroke: #e0e0e0; stroke-width: 0.5; stroke-dasharray: 4,4; }}',
        f'      .plot-path {{ fill: none; stroke-linecap: round; stroke-linejoin: round; }}',
        f'    </style>',
        f'  </defs>',
        f'  <!-- Sheet boundary -->',
        f'  <rect class="sheet-border" x="0" y="0" width="{w:.2f}" height="{h:.2f}" />',
        f'  <!-- Hard-clip area (margins: top={top_m}, bottom={bottom_m}, left={left_m}, right={right_m} mm) -->',
        f'  <rect class="hard-clip" x="{left_m:.2f}" y="{top_m:.2f}" width="{hard_clip_w:.2f}" height="{hard_clip_h:.2f}" />',
    ]

    # Draw recorded polylines
    for poly in plotter.recorded_polylines:
        if not poly.points:
            continue
        color = PEN_PALETTE.get(poly.pen, "#444444")
        # Map center-origin (px, py) to sheet coords:
        # In Mutoh XP-500 coordinates: +X is feed down (+Y in SVG), +Y is carriage right (+X in SVG)
        pts_str = " ".join(
            f"{center_x + py:.3f},{center_y + px:.3f}"
            for px, py in poly.points
        )
        svg_parts.append(
            f'  <polyline class="plot-path" stroke="{color}" stroke-width="0.35" points="{pts_str}" />'
        )

    svg_parts.append('</svg>\n')

    path.write_text("\n".join(svg_parts), encoding="utf-8")

