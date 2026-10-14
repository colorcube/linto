"""SVG Export serializer saving Plotter Studio project documents."""

from __future__ import annotations
import xml.etree.ElementTree as ET
from typing import Optional
from .document import Document, LogicalPen, ImportItem, VectorPath


NS_PS = "https://plotter-studio.org/schema/v1"
ET.register_namespace("ps", NS_PS)


def export_document_to_svg(doc: Document, output_path: str):
    """Save document to an SVG file with embedded ps: metadata."""
    w_mm = doc.page.width_mm
    h_mm = doc.page.height_mm

    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "xmlns:ps": NS_PS,
        "width": f"{w_mm:.2f}mm",
        "height": f"{h_mm:.2f}mm",
        "viewBox": f"0 0 {w_mm:.2f} {h_mm:.2f}",
        "version": "1.1",
    })

    # Metadata tag for Plotter Studio settings
    metadata = ET.SubElement(root, "metadata")
    ps_project = ET.SubElement(metadata, f"{{{NS_PS}}}project", {"version": "1.0"})

    # Page settings
    ET.SubElement(ps_project, f"{{{NS_PS}}}page", {
        "preset": doc.page.preset,
        "width_mm": f"{doc.page.width_mm:.2f}",
        "height_mm": f"{doc.page.height_mm:.2f}",
        "orientation": doc.page.orientation,
        "margin_left": f"{doc.page.margin_left_mm:.2f}",
        "margin_right": f"{doc.page.margin_right_mm:.2f}",
        "margin_top": f"{doc.page.margin_top_mm:.2f}",
        "margin_bottom": f"{doc.page.margin_bottom_mm:.2f}",
    })

    # Pens
    ps_pens = ET.SubElement(ps_project, f"{{{NS_PS}}}pens")
    for pen in doc.pens:
        attrs = {
            "id": str(pen.pen_id),
            "name": pen.name,
            "color": pen.color_hex,
            "width_mm": f"{pen.width_mm:.2f}",
            "speed": f"{pen.speed_cm_s:.1f}",
            "force": f"{pen.force_g:.1f}",
            "enabled": str(pen.enabled).lower(),
        }
        if pen.mapped_to is not None:
            attrs["mapped_to"] = str(pen.mapped_to)
        ET.SubElement(ps_pens, f"{{{NS_PS}}}pen", attrs)

    # Render graphics elements into SVG body
    pens_dict = {p.pen_id: p for p in doc.pens}

    for item in doc.items:
        g_item = ET.SubElement(root, "g", {
            "id": f"item_{item.item_id[:8]}",
            f"{{{NS_PS}}}name": item.name,
            f"{{{NS_PS}}}transform": f"{item.transform.a},{item.transform.b},{item.transform.c},{item.transform.d},{item.transform.tx},{item.transform.ty}",
        })
        if item.source_path:
            g_item.set(f"{{{NS_PS}}}source", item.source_path)

        for p_idx, path in enumerate(item.paths):
            if len(path.points) < 2:
                continue

            pen = pens_dict.get(path.pen_id)
            color = pen.color_hex if pen else "#000000"
            stroke_width = pen.width_mm if pen else 0.35

            # Apply item transform to points for standard SVG viewers
            pts_transformed = item.transform.transform_coords(path.points)

            # Build d string
            d_parts = [f"M {pts_transformed[0, 0]:.3f},{pts_transformed[0, 1]:.3f}"]
            for i in range(1, len(pts_transformed)):
                d_parts.append(f"L {pts_transformed[i, 0]:.3f},{pts_transformed[i, 1]:.3f}")
            if path.closed:
                d_parts.append("Z")

            ET.SubElement(g_item, "path", {
                "d": " ".join(d_parts),
                "fill": "none",
                "stroke": color,
                "stroke-width": f"{stroke_width:.2f}",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
                f"{{{NS_PS}}}pen": str(path.pen_id),
            })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
