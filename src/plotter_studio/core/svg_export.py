"""SVG Export serializer and project document loader."""

from __future__ import annotations
import copy
import os
from pathlib import Path
from typing import Optional, List, Tuple
import uuid
import xml.etree.ElementTree as ET
import numpy as np
import svgelements

from .document import Document, LogicalPen, ImportItem, VectorPath, Page, DEFAULT_PENS
from .geometry import (
    AffineTransform,
    LineSegment,
    QuadraticBezierSegment,
    CubicBezierSegment,
    ArcSegment,
)
from .svg_import import (
    segment_to_points,
    extract_subpath_segments,
    _clean_duplicate_attributes,
    load_svg,
)


NS_PS = "https://plotter-studio.org/schema/v1"
NS_SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("ps", NS_PS)


def export_document_to_svg(doc: Document, output_path: str):
    """Save document to an SVG file with embedded ps: metadata."""
    w_mm = doc.page.width_mm
    h_mm = doc.page.height_mm

    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
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
        "device_profile": doc.page.device_profile,
        "feed_edge": doc.page.feed_edge,
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
            f"{{{NS_PS}}}visible": str(item.visible).lower(),
            f"{{{NS_PS}}}locked": str(item.locked).lower(),
        })
        if item.source_path:
            g_item.set(f"{{{NS_PS}}}source", item.source_path)

        for p_idx, path in enumerate(item.paths):
            pen = pens_dict.get(path.pen_id)
            color = pen.color_hex if pen else "#000000"
            stroke_width = pen.width_mm if pen else 0.35

            d_parts: List[str] = []
            if path.segments:
                t_segs = [s.transformed(item.transform) for s in path.segments]
                first = t_segs[0].start
                d_parts.append(f"M {first[0]:.4f},{first[1]:.4f}")
                for seg in t_segs:
                    if isinstance(seg, LineSegment):
                        d_parts.append(f"L {seg.end[0]:.4f},{seg.end[1]:.4f}")
                    elif isinstance(seg, QuadraticBezierSegment):
                        d_parts.append(
                            f"Q {seg.control[0]:.4f},{seg.control[1]:.4f} {seg.end[0]:.4f},{seg.end[1]:.4f}"
                        )
                    elif isinstance(seg, CubicBezierSegment):
                        d_parts.append(
                            f"C {seg.control1[0]:.4f},{seg.control1[1]:.4f} "
                            f"{seg.control2[0]:.4f},{seg.control2[1]:.4f} "
                            f"{seg.end[0]:.4f},{seg.end[1]:.4f}"
                        )
                    elif isinstance(seg, ArcSegment):
                        if seg.cubics:
                            for c in seg.cubics:
                                d_parts.append(
                                    f"C {c.control1[0]:.4f},{c.control1[1]:.4f} "
                                    f"{c.control2[0]:.4f},{c.control2[1]:.4f} "
                                    f"{c.end[0]:.4f},{c.end[1]:.4f}"
                                )
                        else:
                            d_parts.append(f"L {seg.end[0]:.4f},{seg.end[1]:.4f}")
                if path.closed:
                    d_parts.append("Z")
            else:
                if len(path.points) < 2:
                    continue
                pts_transformed = item.transform.transform_coords(path.points)
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


def is_project_file(filepath_or_data: str) -> bool:
    """Check if an SVG file or XML string contains Plotter Studio project metadata."""
    try:
        if os.path.exists(filepath_or_data):
            with open(filepath_or_data, "r", encoding="utf-8", errors="replace") as f:
                header = f.read(4096)
            return NS_PS in header or "<ps:project" in header
        return NS_PS in filepath_or_data or "<ps:project" in filepath_or_data
    except Exception:
        return False


def load_document_from_svg(filepath_or_data: str) -> Document:
    """Load an SVG file and reconstruct the full Document model.

    Supports both Plotter Studio project SVGs (with embedded page/pen/item metadata)
    and standard SVGs (which are loaded as an ImportItem on a matching or default page).
    """
    if not is_project_file(filepath_or_data):
        item = load_svg(filepath_or_data)
        page = Page()
        try:
            if os.path.exists(filepath_or_data):
                svg_obj = svgelements.SVG.parse(filepath_or_data)
            else:
                import io
                svg_obj = svgelements.SVG.parse(io.StringIO(filepath_or_data))
            w_mm = None
            h_mm = None
            if svg_obj.width and svg_obj.height:
                w_mm = float(svg_obj.width) * (25.4 / 96.0)
                h_mm = float(svg_obj.height) * (25.4 / 96.0)
            elif getattr(svg_obj, "viewbox", None):
                vb = svg_obj.viewbox
                if vb.width and vb.height:
                    w_mm = float(vb.width) * (25.4 / 96.0)
                    h_mm = float(vb.height) * (25.4 / 96.0)

            if w_mm and h_mm:
                formats = {
                    "A4": (210, 297),
                    "A3": (297, 420),
                    "A2": (420, 594),
                    "A1": (594, 841),
                    "A0": (841, 1189),
                }
                detected_preset = None
                detected_orient = "portrait"
                for name, (dim1, dim2) in formats.items():
                    if abs(w_mm - dim1) < 5 and abs(h_mm - dim2) < 5:
                        detected_preset = name
                        detected_orient = "portrait"
                        break
                    elif abs(w_mm - dim2) < 5 and abs(h_mm - dim1) < 5:
                        detected_preset = name
                        detected_orient = "landscape"
                        break
                if detected_preset:
                    page.apply_preset(detected_preset, detected_orient)
                elif w_mm > 0.0 and h_mm > 0.0:
                    page.set_custom_size(round(w_mm, 2), round(h_mm, 2))
            elif item.current_bounds:
                b = item.current_bounds
                w = round(max(50.0, b.max_x + 10.0), 2)
                h = round(max(50.0, b.max_y + 10.0), 2)
                page.set_custom_size(w, h)
        except Exception:
            pass

        return Document(page=page, pens=copy.deepcopy(DEFAULT_PENS), items=[item] if item.paths else [])

    if os.path.exists(filepath_or_data):
        raw = Path(filepath_or_data).read_text(encoding="utf-8", errors="replace")
    else:
        raw = filepath_or_data

    cleaned = _clean_duplicate_attributes(raw)
    root = ET.fromstring(cleaned)

    # 1. Page settings
    ps_proj = root.find(f".//{{{NS_PS}}}project")
    page = Page()
    if ps_proj is not None:
        ps_page = ps_proj.find(f"{{{NS_PS}}}page")
        if ps_page is not None:
            preset = ps_page.get("preset", "A3")
            orientation = ps_page.get("orientation", "landscape")
            page.apply_preset(preset, orientation)
            if "device_profile" in ps_page.attrib:
                page.device_profile = ps_page.attrib["device_profile"]
            if "feed_edge" in ps_page.attrib:
                page.feed_edge = ps_page.attrib["feed_edge"]
            if "width_mm" in ps_page.attrib:
                page.width_mm = float(ps_page.attrib["width_mm"])
            if "height_mm" in ps_page.attrib:
                page.height_mm = float(ps_page.attrib["height_mm"])
            if "margin_left" in ps_page.attrib:
                page.margin_left_mm = float(ps_page.attrib["margin_left"])
            if "margin_right" in ps_page.attrib:
                page.margin_right_mm = float(ps_page.attrib["margin_right"])
            if "margin_top" in ps_page.attrib:
                page.margin_top_mm = float(ps_page.attrib["margin_top"])
            if "margin_bottom" in ps_page.attrib:
                page.margin_bottom_mm = float(ps_page.attrib["margin_bottom"])

    # 2. Pens
    pens: List[LogicalPen] = []
    if ps_proj is not None:
        ps_pens = ps_proj.find(f"{{{NS_PS}}}pens")
        if ps_pens is not None:
            for p_elem in ps_pens.findall(f"{{{NS_PS}}}pen"):
                pid = int(p_elem.get("id", 1))
                name = p_elem.get("name", f"Stift {pid}")
                col = p_elem.get("color", "#000000")
                w = float(p_elem.get("width_mm", 0.35))
                spd = float(p_elem.get("speed", 20.0))
                frc = float(p_elem.get("force", 20.0))
                en = p_elem.get("enabled", "true").lower() == "true"
                m = p_elem.get("mapped_to")
                mapped_to = int(m) if m is not None else None
                pens.append(LogicalPen(
                    pen_id=pid,
                    name=name,
                    color_hex=col,
                    width_mm=w,
                    speed_cm_s=spd,
                    force_g=frc,
                    enabled=en,
                    mapped_to=mapped_to,
                ))
    if not pens:
        pens = copy.deepcopy(DEFAULT_PENS)

    # 3. Items
    items: List[ImportItem] = []
    g_elements = root.findall(f".//{{{NS_SVG}}}g") + root.findall(".//g")
    seen_g = set()
    unique_g = []
    for g in g_elements:
        if id(g) not in seen_g:
            seen_g.add(id(g))
            unique_g.append(g)

    for g in unique_g:
        ps_name = g.attrib.get(f"{{{NS_PS}}}name")
        item_id_attr = g.attrib.get("id", "")
        if not ps_name and not item_id_attr.startswith("item_"):
            continue

        name = ps_name or (item_id_attr[5:] if item_id_attr.startswith("item_") else "Import")
        source = g.attrib.get(f"{{{NS_PS}}}source")
        visible = g.attrib.get(f"{{{NS_PS}}}visible", "true").lower() == "true"
        locked = g.attrib.get(f"{{{NS_PS}}}locked", "false").lower() == "true"
        t_str = g.attrib.get(f"{{{NS_PS}}}transform")
        if t_str:
            try:
                vals = [float(x) for x in t_str.split(",")]
                transform = AffineTransform(*vals)
            except Exception:
                transform = AffineTransform.identity()
        else:
            transform = AffineTransform.identity()

        inv_t = transform.inverse()

        item_paths: List[VectorPath] = []
        path_elements = g.findall(f"{{{NS_SVG}}}path") + g.findall("path")
        seen_p = set()
        unique_paths = []
        for p_elem in path_elements:
            if id(p_elem) not in seen_p:
                seen_p.add(id(p_elem))
                unique_paths.append(p_elem)

        for path_elem in unique_paths:
            pen_id_str = path_elem.attrib.get(f"{{{NS_PS}}}pen", "1")
            try:
                pen_id = int(pen_id_str)
            except ValueError:
                pen_id = 1

            d = path_elem.attrib.get("d", "")
            if not d:
                continue

            p = svgelements.Path(d)
            for segs, is_closed in extract_subpath_segments(p, scale_mm=1.0):
                local_segs = [s.transformed(inv_t) for s in segs]
                item_paths.append(VectorPath(pen_id=pen_id, closed=is_closed, segments=local_segs))

        if item_paths:
            raw_id = item_id_attr[5:] if item_id_attr.startswith("item_") else str(uuid.uuid4())
            item = ImportItem(
                name=name,
                paths=item_paths,
                transform=transform,
                source_path=source,
                item_id=raw_id,
                visible=visible,
                locked=locked,
            )
            items.append(item)

    if not items:
        fallback_item = load_svg(filepath_or_data)
        if fallback_item.paths:
            items.append(fallback_item)

    return Document(page=page, pens=pens, items=items)


def export_plot_job_to_svg(job, page: Page, output_path: str):
    """Export compiled plot job polylines into a clean SVG file grouped by pen."""
    w_mm = page.width_mm
    h_mm = page.height_mm
    root = ET.Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg",
        "width": f"{w_mm:.2f}mm",
        "height": f"{h_mm:.2f}mm",
        "viewBox": f"0 0 {w_mm:.2f} {h_mm:.2f}",
        "version": "1.1",
    })

    for pen_id, layer in sorted(job.layers.items()):
        g_layer = ET.SubElement(root, "g", {
            "id": f"pen_{pen_id}_{layer.pen.name.replace(' ', '_')}",
            "stroke": layer.pen.color_hex,
            "stroke-width": f"{layer.pen.width_mm:.2f}",
            "fill": "none",
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        })
        for poly in layer.lines:
            if len(poly) < 2:
                continue
            d_parts = [f"M {poly[0, 0]:.3f},{poly[0, 1]:.3f}"]
            for pt in poly[1:]:
                d_parts.append(f"L {pt[0]:.3f},{pt[1]:.3f}")
            ET.SubElement(g_layer, "path", {"d": " ".join(d_parts)})

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)

