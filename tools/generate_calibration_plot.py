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

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_mm} {height_mm}">')
    lines.append('  <style>')
    lines.append('    text { font-family: "DejaVu Sans", "Helvetica", "Arial", sans-serif; font-size: 3.5px; fill: #1a1a1a; }')
    lines.append('    .title { font-size: 5px; font-weight: bold; }')
    lines.append('    .edge-label { font-size: 3.2px; font-weight: bold; fill: #d32f2f; }')
    lines.append('    .axis-label { font-size: 4px; font-weight: bold; }')
    lines.append('  </style>')

    # 1. Sheet outline (dashed grey)
    lines.append(f'  <!-- Sheet border (physical paper: {width_mm} x {height_mm} mm) -->')
    lines.append(f'  <rect x="0" y="0" width="{width_mm}" height="{height_mm}" fill="none" stroke="#cbd5e1" stroke-width="0.2" stroke-dasharray="2,2"/>')

    # 2. Hard-Clip / Plottable Area Frame (Pen 1)
    lines.append('  <!-- Plottable Boundary (EXP: Top 25mm, Bottom 5mm, Left/Right 5mm) -->')
    lines.append(f'  <rect x="{plot_x}" y="{plot_y}" width="{plot_w}" height="{plot_h}" fill="none" stroke="{pen_colors[0]}" stroke-width="0.35"/>')
    lines.append(f'  <!-- Inner border (2mm offset) -->')
    lines.append(f'  <rect x="{plot_x + 2}" y="{plot_y + 2}" width="{plot_w - 4}" height="{plot_h - 4}" fill="none" stroke="{pen_colors[0]}" stroke-width="0.25"/>')

    # Edge annotations
    lines.append(f'  <text x="{cx}" y="{plot_y - 2}" text-anchor="middle" class="edge-label">▲ VORSCHUB-KANTE (TOP / LEADING EDGE: SOLL-ABSTAND 25.0 mm) ▲</text>')
    lines.append(f'  <text x="{cx}" y="{height_mm - 1.5}" text-anchor="middle" class="edge-label">▼ HINTERKANTE (BOTTOM: SOLL-ABSTAND 5.0 mm) ▼</text>')
    lines.append(f'  <text x="2" y="{cy}" text-anchor="middle" transform="rotate(-90 2 {cy})" class="edge-label">◄ LINKS (SOLL 5.0 mm)</text>')
    lines.append(f'  <text x="{width_mm - 1.5}" y="{cy}" text-anchor="middle" transform="rotate(90 {width_mm - 1.5} {cy})" class="edge-label">RECHTS (SOLL 5.0 mm) ►</text>')

    # Title
    lines.append(f'  <text x="{plot_x + 6}" y="{plot_y + 10}" class="title">MUTOH XP-500 KALIBRIER- &amp; TESTPLOT ({format_name} QUER)</text>')
    lines.append(f'  <text x="{plot_x + 6}" y="{plot_y + 15}">Plotter Studio Hardware-Verifikation · AP0 Testplan · Maße in Millimeter</text>')

    # 3. Orientation arrows (+X and +Y)
    arrow_ox = plot_x + 15
    arrow_oy = plot_y + 35
    arrow_len = 25.0

    lines.append('  <!-- Orientation Coordinate System -->')
    lines.append(f'  <g stroke="{pen_colors[1]}" stroke-width="0.5" fill="none">')
    # +X arrow (to right: feed)
    lines.append(f'    <line x1="{arrow_ox}" y1="{arrow_oy}" x2="{arrow_ox + arrow_len}" y2="{arrow_oy}"/>')
    lines.append(f'    <polyline points="{arrow_ox + arrow_len - 3},{arrow_oy - 2} {arrow_ox + arrow_len},{arrow_oy} {arrow_ox + arrow_len - 3},{arrow_oy + 2}"/>')
    # +Y arrow (downwards: carriage)
    lines.append(f'    <line x1="{arrow_ox}" y1="{arrow_oy}" x2="{arrow_ox}" y2="{arrow_oy + arrow_len}"/>')
    lines.append(f'    <polyline points="{arrow_ox - 2},{arrow_oy + arrow_len - 3} {arrow_ox},{arrow_oy + arrow_len} {arrow_ox + 2},{arrow_oy + arrow_len - 3}"/>')
    lines.append('  </g>')
    lines.append(f'  <text x="{arrow_ox + arrow_len + 2}" y="{arrow_oy + 1.2}" class="axis-label" fill="{pen_colors[1]}">+X (Vorschub / Rollenvorschub)</text>')
    lines.append(f'  <text x="{arrow_ox - 1}" y="{arrow_oy + arrow_len + 5}" class="axis-label" fill="{pen_colors[1]}">+Y (Wagen / Stiftachse)</text>')

    # 4. Precision scale measuring segment
    meas_len = 400.0 if width_mm >= 400 else 250.0
    meas_ox = (width_mm - meas_len) / 2.0
    meas_oy = cy - 10.0

    lines.append('  <!-- Precision Scale Ruler (X-Axis) -->')
    lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
    lines.append(f'    <line x1="{meas_ox}" y1="{meas_oy}" x2="{meas_ox + meas_len}" y2="{meas_oy}"/>')
    # Tick marks every 50 mm
    step = 50.0
    cur = 0.0
    while cur <= meas_len + 0.01:
        tx = meas_ox + cur
        th = 4.0 if int(cur) % 100 == 0 else 2.5
        lines.append(f'    <line x1="{tx}" y1="{meas_oy - th}" x2="{tx}" y2="{meas_oy + th}"/>')
        lines.append(f'  </g>')
        lines.append(f'  <text x="{tx}" y="{meas_oy - 5}" text-anchor="middle">{int(cur)} mm</text>')
        lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
        cur += step
    lines.append('  </g>')
    lines.append(f'  <text x="{cx}" y="{meas_oy + 8}" text-anchor="middle" font-weight="bold">MASSTABSPRÜFUNG: EXAKT {meas_len:.1f} mm (MIT STAHLMASSSTAB MESSEN)</text>')

    # Precision scale measuring segment in Y-Axis
    meas_y_len = 200.0 if height_mm >= 250 else 140.0
    meas_y_ox = width_mm - plot_x - 30.0
    meas_y_oy = (height_mm - meas_y_len) / 2.0 + 10.0

    lines.append('  <!-- Precision Scale Ruler (Y-Axis) -->')
    lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
    lines.append(f'    <line x1="{meas_y_ox}" y1="{meas_y_oy}" x2="{meas_y_ox}" y2="{meas_y_oy + meas_y_len}"/>')
    cur = 0.0
    while cur <= meas_y_len + 0.01:
        ty = meas_y_oy + cur
        tw = 4.0 if int(cur) % 50 == 0 else 2.5
        lines.append(f'    <line x1="{meas_y_ox - tw}" y1="{ty}" x2="{meas_y_ox + tw}" y2="{ty}"/>')
        lines.append(f'  </g>')
        lines.append(f'  <text x="{meas_y_ox + 6}" y="{ty + 1.2}">{int(cur)}</text>')
        lines.append(f'  <g stroke="{pen_colors[0]}" stroke-width="0.35">')
        cur += 50.0
    lines.append('  </g>')
    lines.append(f'  <text x="{meas_y_ox}" y="{meas_y_oy + meas_y_len + 6}" text-anchor="middle">Y: {meas_y_len:.0f} mm</text>')

    # 5. Concentric Circles (Orthogonality, CV mode, Backlash)
    circle_x = plot_x + 40
    circle_y = plot_y + 85
    lines.append('  <!-- Concentric circles for backlash & CV mode -->')
    radii = [10.0, 20.0, 30.0]
    for i, r in enumerate(radii):
        col = pen_colors[(i + 2) % 8]
        lines.append(f'  <circle cx="{circle_x}" cy="{circle_y}" r="{r}" fill="none" stroke="{col}" stroke-width="0.35"/>')
    # Crosshair
    lines.append(f'  <line x1="{circle_x - 35}" y1="{circle_y}" x2="{circle_x + 35}" y2="{circle_y}" stroke="{pen_colors[2]}" stroke-width="0.25"/>')
    lines.append(f'  <line x1="{circle_x}" y1="{circle_y - 35}" x2="{circle_x}" y2="{circle_y + 35}" stroke="{pen_colors[2]}" stroke-width="0.25"/>')
    lines.append(f'  <text x="{circle_x}" y="{circle_y + 40}" text-anchor="middle">Kreisbogen / CV-Test (R=10, 20, 30 mm)</text>')

    # 6. Pen Matrix 1..8 (Multi-pen test)
    matrix_x = plot_x + 100 if width_mm >= 400 else plot_x + 75
    matrix_y = plot_y + 75
    lines.append('  <!-- Pen 1..8 Verification Matrix -->')
    lines.append(f'  <text x="{matrix_x}" y="{matrix_y - 4}" font-weight="bold">Stifte 1–8 Testmuster (SP1…SP8):</text>')

    for pen_idx in range(1, 9):
        col = pen_colors[pen_idx - 1]
        row_y = matrix_y + (pen_idx - 1) * 9.0
        lines.append(f'  <!-- Pen {pen_idx} -->')
        lines.append(f'  <g stroke="{col}" stroke-width="0.35">')
        # Test line pattern (solid, stepped, hatched)
        lines.append(f'    <line x1="{matrix_x}" y1="{row_y}" x2="{matrix_x + 30}" y2="{row_y}"/>')
        lines.append(f'    <polyline points="{matrix_x + 32},{row_y - 2} {matrix_x + 36},{row_y + 2} {matrix_x + 40},{row_y - 2} {matrix_x + 44},{row_y + 2}"/>')
        lines.append(f'    <rect x="{matrix_x + 47}" y="{row_y - 2.5}" width="5" height="5" fill="none"/>')
        lines.append('  </g>')
        lines.append(f'  <text x="{matrix_x + 56}" y="{row_y + 1.2}">SP{pen_idx} ({col})</text>')

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
