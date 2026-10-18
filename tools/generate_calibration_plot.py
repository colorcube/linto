#!/usr/bin/env python3
"""Generates calibration and test plot SVGs for Mutoh XP-500 verification (AP0 / testplan.md).

Outputs:
- resources/calibration_plot_a4.svg (DIN A4 Quer: 297 x 210 mm)
- resources/calibration_plot_a3.svg (DIN A3 Quer: 420 x 297 mm)

Features included (matching testplan.md requirements):
1. Orientation: Arrows for +X (Feed) and +Y (Carriage), plus TOP/Leading Edge indicator.
2. Scale accuracy: High-precision measurement segments with tick marks (400 mm for A3, 250 mm for A4).
3. Border calibration: Outer frame matching plottable area for 4-edge margin measurement.
4. Multi-pen test matrix: Distinct patterns for pens 1 through 8 with standard colors.
5. Concentric circles: 360-segment circular test for CV mode, backlash and axis orthogonality.
"""

from pathlib import Path


def generate_svg(format_name: str, width_mm: float, height_mm: float) -> str:
    """Generate SVG content for a given paper format."""
    # Colors for pens 1..8
    pen_colors = [
        "#1a1a1a",  # Pen 1: Black
        "#d32f2f",  # Pen 2: Red
        "#1976d2",  # Pen 3: Blue
        "#388e3c",  # Pen 4: Green
        "#f57c00",  # Pen 5: Orange
        "#7b1fa2",  # Pen 6: Magenta
        "#0097a7",  # Pen 7: Cyan
        "#c09000",  # Pen 8: Yellow/Gold (darkened slightly for visibility on white)
    ]

    # Plottable margins: Mutoh XP-500 EXP mode: Top 25mm (feed edge), others 5mm
    margin_top = 25.0
    margin_bottom = 5.0
    margin_left = 5.0
    margin_right = 5.0

    plot_x = margin_left
    plot_y = margin_top
    plot_w = width_mm - margin_left - margin_right
    plot_h = height_mm - margin_top - margin_bottom

    cx = width_mm / 2.0
    cy = (margin_top + (height_mm - margin_bottom)) / 2.0

    is_a3 = width_mm >= 400.0
    plot_right = plot_x + plot_w
    plot_bottom = plot_y + plot_h

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">')
    lines.append('  <style>')
    lines.append('    text { font-family: "DejaVu Sans", "Helvetica", "Arial", sans-serif; font-size: 3.2px; fill: #1a1a1a; }')
    lines.append('    .title { font-size: 4.5px; font-weight: bold; }')
    lines.append('    .section-title { font-size: 3.5px; font-weight: bold; }')
    lines.append('    .edge-label { font-size: 2.8px; font-weight: bold; fill: #d32f2f; }')
    lines.append('    .axis-label { font-size: 3.4px; font-weight: bold; }')
    lines.append('  </style>')

    # 1. Hard-Clip / Plottable Area Frame (Pen 1)
    lines.append('  <!-- Plottable Boundary (EXP: Top 25mm, Bottom 5mm, Left/Right 5mm) -->')
    lines.append(f'  <rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" fill="none" stroke="{pen_colors[0]}" stroke-width="0.35"/>')
    lines.append('  <!-- Inner border (2mm offset) -->')
    lines.append(f'  <rect x="{plot_x + 2}" y="{plot_y + 2}" width="{plot_w - 4}" height="{plot_h - 4}" fill="none" stroke="{pen_colors[0]}" stroke-width="0.25"/>')

    # Edge annotations (placed cleanly inside the inner border so everything stays within plottable bounds)
    lines.append(f'  <text x="{cx}" y="{plot_y + 5.5}" text-anchor="middle" class="edge-label">▲ VORSCHUB-KANTE / LEADING EDGE (SOLL-ABSTAND OBEN: 25.0 mm) ▲</text>')
    lines.append(f'  <text x="{cx}" y="{plot_bottom - 3.5}" text-anchor="middle" class="edge-label">▼ HINTERKANTE / TRAILING EDGE (SOLL-ABSTAND UNTEN: 5.0 mm) ▼</text>')
    lines.append(f'  <text x="{plot_x + 5.5}" y="{cy}" text-anchor="middle" transform="rotate(-90 {plot_x + 5.5} {cy})" class="edge-label">▲ LINKS (SOLL: 5.0 mm) ▲</text>')
    lines.append(f'  <text x="{plot_right - 5.5}" y="{cy}" text-anchor="middle" transform="rotate(90 {plot_right - 5.5} {cy})" class="edge-label">▲ RECHTS (SOLL: 5.0 mm) ▲</text>')

    # 2. Title & Header Block (Top-Left)
    header_x = plot_x + 14.0
    title_y = plot_y + 15.0 if is_a3 else plot_y + 13.5
    sub_y = title_y + 5.5
    lines.append(f'  <text x="{header_x}" y="{title_y}" class="title">MUTOH XP-500 KALIBRIER- &amp; TESTPLOT ({format_name} QUER)</text>')
    lines.append(f'  <text x="{header_x}" y="{sub_y}">Plotter Studio Hardware-Verifikation · AP0 Testplan · Maße in Millimeter</text>')

    # 3. Orientation arrows (+X and +Y) directly below Header
    arrow_ox = header_x + 2.0
    arrow_oy = sub_y + 8.5 if is_a3 else sub_y + 7.0
    arrow_len = 22.0 if is_a3 else 18.0

    lines.append('  <!-- Orientation Coordinate System -->')
    lines.append(f'  <g stroke="{pen_colors[1]}" stroke-width="0.5" fill="none">')
    # +X arrow (to right: feed)
    lines.append(f'    <line x1="{arrow_ox}" y1="{arrow_oy}" x2="{arrow_ox + arrow_len}" y2="{arrow_oy}"/>')
    lines.append(f'    <polyline points="{arrow_ox + arrow_len - 3},{arrow_oy - 2} {arrow_ox + arrow_len},{arrow_oy} {arrow_ox + arrow_len - 3},{arrow_oy + 2}"/>')
    # +Y arrow (downwards: carriage)
    lines.append(f'    <line x1="{arrow_ox}" y1="{arrow_oy}" x2="{arrow_ox}" y2="{arrow_oy + arrow_len}"/>')
    lines.append(f'    <polyline points="{arrow_ox - 2},{arrow_oy + arrow_len - 3} {arrow_ox},{arrow_oy + arrow_len} {arrow_ox + 2},{arrow_oy + arrow_len - 3}"/>')
    lines.append('  </g>')
    lines.append(f'  <text x="{arrow_ox + arrow_len + 3}" y="{arrow_oy + 1.2}" class="axis-label" fill="{pen_colors[1]}">+X (Vorschub / Rollenvorschub)</text>')
    lines.append(f'  <text x="{arrow_ox + 4}" y="{arrow_oy + arrow_len - 1.0}" class="axis-label" fill="{pen_colors[1]}">+Y (Wagen / Stiftachse)</text>')

    # 4. Middle Diagnostic Band: Concentric Circles (Left) & Pen 1..8 Matrix (Center-Right)
    if is_a3:
        section_header_y = 104.0
        circle_x = 90.0
        circle_y = 156.0
        radii = [10.0, 20.0, 30.0, 40.0]
        cross_half = 45.0
        matrix_x = 190.0
        matrix_y = 116.0
        matrix_row_step = 11.5
        matrix_line_len = 40.0
    else:
        section_header_y = 83.0
        circle_x = 62.0
        circle_y = 121.0
        radii = [10.0, 20.0, 30.0]
        cross_half = 34.0
        matrix_x = 128.0
        matrix_y = 92.0
        matrix_row_step = 9.0
        matrix_line_len = 30.0

    circle_left = circle_x - cross_half
    max_r = radii[-1]
    radii_str = ", ".join(str(int(r)) for r in radii)

    # 4a. Concentric Circles & Square-in-Circle (Orthogonality, CV mode, Backlash)
    lines.append('  <!-- Concentric circles for backlash & CV mode -->')
    lines.append(f'  <text x="{circle_left}" y="{section_header_y}" class="section-title">Kreisbogen &amp; Umkehrspiel (R={radii_str} mm):</text>')
    # Outer reference square around largest circle
    lines.append(f'  <rect x="{circle_x - max_r}" y="{circle_y - max_r}" width="{max_r * 2}" height="{max_r * 2}" fill="none" stroke="{pen_colors[0]}" stroke-width="0.25"/>')
    for i, r in enumerate(radii):
        col = pen_colors[(i + 2) % 8]
        lines.append(f'  <circle cx="{circle_x}" cy="{circle_y}" r="{r}" fill="none" stroke="{col}" stroke-width="0.35"/>')
    # Crosshair
    lines.append(f'  <line x1="{circle_x - cross_half}" y1="{circle_y}" x2="{circle_x + cross_half}" y2="{circle_y}" stroke="{pen_colors[2]}" stroke-width="0.25"/>')
    lines.append(f'  <line x1="{circle_x}" y1="{circle_y - cross_half}" x2="{circle_x}" y2="{circle_y + cross_half}" stroke="{pen_colors[2]}" stroke-width="0.25"/>')
    lines.append(f'  <text x="{circle_left}" y="{circle_y + cross_half + 6.0}">Rundlauf, Quadrantübergänge &amp; CV-Modus</text>')

    # 4b. Pen Matrix 1..8 (Multi-pen test)
    lines.append('  <!-- Pen 1..8 Verification Matrix -->')
    lines.append(f'  <text x="{matrix_x}" y="{section_header_y}" class="section-title">Stifte 1–8 Testmuster (SP1…SP8):</text>')

    for pen_idx in range(1, 9):
        col = pen_colors[pen_idx - 1]
        row_y = matrix_y + (pen_idx - 1) * matrix_row_step
        zig_x = matrix_x + matrix_line_len + 3.0
        box_x = zig_x + 15.0
        lbl_x = box_x + 9.0
        lines.append(f'  <!-- Pen {pen_idx} -->')
        lines.append(f'  <g stroke="{col}" stroke-width="0.35">')
        lines.append(f'    <line x1="{matrix_x}" y1="{row_y}" x2="{matrix_x + matrix_line_len}" y2="{row_y}"/>')
        lines.append(f'    <polyline points="{zig_x},{row_y - 2} {zig_x + 4},{row_y + 2} {zig_x + 8},{row_y - 2} {zig_x + 12},{row_y + 2}"/>')
        lines.append(f'    <rect x="{box_x}" y="{row_y - 2.5}" width="5" height="5" fill="none"/>')
        lines.append('  </g>')
        lines.append(f'  <text x="{lbl_x}" y="{row_y + 1.2}">SP{pen_idx} ({col})</text>')

    # 5. Precision Scale Ruler in Y-Axis (Right Column, clear of bottom X-ruler)
    meas_y_len = 200.0 if is_a3 else 120.0
    meas_y_ox = plot_right - 34.0 if is_a3 else plot_right - 30.0
    meas_y_oy = 44.0 if is_a3 else 42.0

    lines.append('  <!-- Precision Scale Ruler (Y-Axis) -->')
    lines.append(f'  <text x="{meas_y_ox}" y="{meas_y_oy - 5.0}" text-anchor="middle" class="section-title">Y: {meas_y_len:.0f} mm</text>')
    lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
    lines.append(f'    <line x1="{meas_y_ox}" y1="{meas_y_oy}" x2="{meas_y_ox}" y2="{meas_y_oy + meas_y_len}"/>')
    y_ticks = [0.0, 50.0, 100.0, 150.0, 200.0] if is_a3 else [0.0, 40.0, 80.0, 120.0]
    for cur in y_ticks:
        ty = meas_y_oy + cur
        tw = 4.0
        lines.append(f'    <line x1="{meas_y_ox - tw}" y1="{ty}" x2="{meas_y_ox + tw}" y2="{ty}"/>')
        lines.append('  </g>')
        lines.append(f'  <text x="{meas_y_ox + 6.0}" y="{ty + 1.2}">{int(cur)} mm</text>')
        lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
    lines.append('  </g>')

    # 6. Precision Scale Ruler in X-Axis (Lower Band, unobstructed across full width)
    meas_len = 400.0 if is_a3 else 250.0
    meas_ox = (width_mm - meas_len) / 2.0
    meas_oy = plot_bottom - 23.0 if is_a3 else plot_bottom - 20.0

    lines.append('  <!-- Precision Scale Ruler (X-Axis) -->')
    lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
    lines.append(f'    <line x1="{meas_ox}" y1="{meas_oy}" x2="{meas_ox + meas_len}" y2="{meas_oy}"/>')
    step = 50.0
    cur = 0.0
    while cur <= meas_len + 0.01:
        tx = meas_ox + cur
        th = 4.0 if int(cur) % 100 == 0 else 2.5
        if cur <= 0.01:
            t_anchor = "start"
        elif cur >= meas_len - 0.01:
            t_anchor = "end"
        else:
            t_anchor = "middle"
        lines.append(f'    <line x1="{tx}" y1="{meas_oy - th}" x2="{tx}" y2="{meas_oy + th}"/>')
        lines.append('  </g>')
        lines.append(f'  <text x="{tx}" y="{meas_oy - 5.0}" text-anchor="{t_anchor}">{int(cur)} mm</text>')
        lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
        cur += step
    lines.append('  </g>')
    lines.append(f'  <text x="{cx}" y="{meas_oy + 8.5}" text-anchor="middle" class="section-title">MASSTABSPRÜFUNG X: EXAKT {meas_len:.1f} mm (MIT STAHLMASSSTAB MESSEN)</text>')

    lines.append('</svg>\n')
    return '\n'.join(lines)


def main():
    res_dir = Path(__file__).resolve().parent.parent / "resources"
    res_dir.mkdir(exist_ok=True)

    # 1. DIN A4 Landscape (297 x 210 mm)
    a4_svg = generate_svg("DIN A4", 297.0, 210.0)
    a4_path = res_dir / "calibration_plot_a4.svg"
    a4_path.write_text(a4_svg, encoding="utf-8")
    print(f"✓ Generiert: {a4_path} ({len(a4_svg)} Bytes)")

    # 2. DIN A3 Landscape (420 x 297 mm)
    a3_svg = generate_svg("DIN A3", 420.0, 297.0)
    a3_path = res_dir / "calibration_plot_a3.svg"
    a3_path.write_text(a3_svg, encoding="utf-8")
    print(f"✓ Generiert: {a3_path} ({len(a3_svg)} Bytes)")

    # 3. Export matching HP-GL files
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        from plotter_studio.core.svg_import import load_svg
        from plotter_studio.core.document import Document
        from plotter_studio.pipeline.compiler import compile_document_to_plot_job
        from plotter_studio.device import get_default_profile, HPGLEmitter

        profile = get_default_profile()
        emitter = HPGLEmitter(profile, margin_profile="exp")

        for name, p_path, preset in [("A4", a4_path, "A4"), ("A3", a3_path, "A3")]:
            item = load_svg(str(p_path))
            doc = Document()
            doc.page.apply_preset(preset, orientation="landscape")
            doc.items.append(item)
            job = compile_document_to_plot_job(doc)
            hpgl_str = emitter.emit_string(job, doc)
            hpgl_path = res_dir / f"calibration_plot_{name.lower()}.hpgl"
            hpgl_path.write_text(hpgl_str, encoding="ascii")
            print(f"✓ Generiert: {hpgl_path} ({len(hpgl_str)} Bytes, {len(job.steps)} Schritte)")
    except Exception as e:
        print(f"Hinweis: HP-GL Export übersprungen ({e})")


if __name__ == "__main__":
    main()
