"""Tests for Plotter Studio project SVG export and loading."""

import os
import tempfile
import numpy as np
import pytest
from pathlib import Path

from plotter_studio.core.document import Document, Page, LogicalPen, ImportItem, VectorPath
from plotter_studio.core.geometry import AffineTransform, Point
from plotter_studio.core.svg_export import export_document_to_svg, load_document_from_svg, is_project_file
from plotter_studio.core.svg_import import load_svg, _clean_duplicate_attributes


def test_duplicate_attributes_healing():
    """Verify that duplicate attributes (e.g. duplicate xmlns:ps) are healed."""
    raw = (
        '<svg xmlns:ps="https://plotter-studio.org/schema/v1" '
        'xmlns="http://www.w3.org/2000/svg" '
        'xmlns:ps="https://plotter-studio.org/schema/v1" width="100mm" height="100mm">'
        '<rect x="10" y="10" width="80" height="80" stroke="#000000"/>'
        '</svg>'
    )
    cleaned = _clean_duplicate_attributes(raw)
    assert cleaned.count('xmlns:ps=') == 1

    # Should load cleanly through load_svg
    item = load_svg(raw)
    assert len(item.paths) >= 1


def test_affine_transform_inverse():
    """Verify affine transform inverse accuracy and singular handling."""
    # Identity inverse
    ident = AffineTransform.identity()
    inv_ident = ident.inverse()
    assert inv_ident.a == 1.0 and inv_ident.d == 1.0

    # Composite transform: translate, rotate 45 deg, scale 2.0
    t = AffineTransform.rotation(45.0, 10.0, 20.0).multiply(
        AffineTransform.scale(2.0, 1.5)
    ).multiply(AffineTransform.translation(50.0, -30.0))

    inv_t = t.inverse()

    pts = np.array([[0.0, 0.0], [10.0, 20.0], [-50.0, 120.0], [420.0, 297.0]])
    transformed = t.transform_coords(pts)
    restored = inv_t.transform_coords(transformed)
    assert np.allclose(pts, restored, atol=1e-8)

    # Singular matrix (det == 0) falls back to identity safely
    singular = AffineTransform(0.0, 0.0, 0.0, 0.0, 10.0, 20.0)
    assert singular.inverse() == AffineTransform.identity()


def test_project_export_and_load_roundtrip():
    """Verify full document save and restore cycle via SVG."""
    page = Page(preset="A3", orientation="landscape")
    page.margin_left_mm = 8.0
    page.margin_right_mm = 8.0
    page.margin_top_mm = 20.0
    page.margin_bottom_mm = 6.0

    pens = [
        LogicalPen(1, "Pen 1 Black", "#111111", width_mm=0.35, speed_cm_s=15.0, force_g=18.0),
        LogicalPen(2, "Pen 2 Red", "#ee0000", width_mm=0.50, speed_cm_s=25.0, force_g=22.0, mapped_to=1),
    ]

    item1 = ImportItem(
        name="BoxItem",
        paths=[
            VectorPath(points=np.array([[0.0, 0.0], [50.0, 0.0], [50.0, 50.0], [0.0, 50.0], [0.0, 0.0]]), pen_id=1, closed=True)
        ],
        transform=AffineTransform.translation(30.0, 40.0),
        source_path="/path/to/box.svg",
    )

    item2 = ImportItem(
        name="LineItem",
        paths=[
            VectorPath(points=np.array([[10.0, 10.0], [80.0, 80.0]]), pen_id=2, closed=False)
        ],
        transform=AffineTransform.rotation(30.0, 10.0, 10.0),
        source_path=None,
    )

    doc = Document(page=page, pens=pens, items=[item1, item2])

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        tmp_path = f.name

    try:
        export_document_to_svg(doc, tmp_path)

        # Check raw XML: exactly one xmlns:ps
        raw_xml = Path(tmp_path).read_text(encoding="utf-8")
        assert raw_xml.count("xmlns:ps=") == 1
        assert is_project_file(tmp_path) is True

        # Reconstruct
        loaded_doc = load_document_from_svg(tmp_path)

        # Page checks
        assert loaded_doc.page.preset == "A3"
        assert loaded_doc.page.orientation == "landscape"
        assert loaded_doc.page.margin_left_mm == 8.0
        assert loaded_doc.page.margin_right_mm == 8.0
        assert loaded_doc.page.margin_top_mm == 20.0
        assert loaded_doc.page.margin_bottom_mm == 6.0

        # Pens checks
        assert len(loaded_doc.pens) == 2
        p1, p2 = loaded_doc.pens[0], loaded_doc.pens[1]
        assert p1.pen_id == 1 and p1.name == "Pen 1 Black" and p1.color_hex == "#111111"
        assert p2.pen_id == 2 and p2.mapped_to == 1 and p2.speed_cm_s == 25.0

        # Items checks
        assert len(loaded_doc.items) == 2
        it1 = loaded_doc.items[0]
        assert it1.name == "BoxItem"
        assert it1.source_path == "/path/to/box.svg"
        assert len(it1.paths) == 1
        assert it1.paths[0].pen_id == 1
        assert it1.paths[0].closed is True
        # Check that transformed bounds match
        orig_cb = item1.current_bounds
        load_cb = it1.current_bounds
        assert orig_cb is not None and load_cb is not None
        assert np.isclose(orig_cb.min_x, load_cb.min_x, atol=0.01)
        assert np.isclose(orig_cb.min_y, load_cb.min_y, atol=0.01)
        assert np.isclose(orig_cb.width, load_cb.width, atol=0.01)
        assert np.isclose(orig_cb.height, load_cb.height, atol=0.01)

        it2 = loaded_doc.items[1]
        assert it2.name == "LineItem"
        assert len(it2.paths) == 1
        assert it2.paths[0].pen_id == 2
        assert it2.paths[0].closed is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_load_existing_user_projekt():
    """Verify that tmp/projekt.svg loads correctly with its 3 items."""
    proj_path = "tmp/projekt.svg"
    if not os.path.exists(proj_path):
        pytest.skip("tmp/projekt.svg not found")

    assert is_project_file(proj_path) is True
    doc = load_document_from_svg(proj_path)
    assert len(doc.items) == 3
    names = [it.name for it in doc.items]
    assert "calibration_grid" in names
    assert "TEST_10cm" in names
    assert "calibration_plot_a3" in names
    assert doc.page.preset == "A3"
    assert len(doc.pens) == 8


def test_load_standard_svg_as_project():
    """Verify that a standard SVG (non-project) loads cleanly into a new Document."""
    svg_path = "examples/TEST_10cm.svg"
    if not os.path.exists(svg_path):
        pytest.skip("examples/TEST_10cm.svg not found")

    assert is_project_file(svg_path) is False
    doc = load_document_from_svg(svg_path)
    assert len(doc.items) == 1
    assert len(doc.items[0].paths) > 0
    assert doc.items[0].name == "TEST_10cm"
    assert doc.page.preset == "Custom"
    assert doc.page.width_mm == 100.0
    assert doc.page.height_mm == 100.0

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        tmp_out = f.name
    try:
        export_document_to_svg(doc, tmp_out)
        assert is_project_file(tmp_out) is True
        reloaded = load_document_from_svg(tmp_out)
        assert reloaded.page.preset == "Custom"
        assert reloaded.page.width_mm == 100.0
        assert reloaded.page.height_mm == 100.0
        assert len(reloaded.items) == 1
    finally:
        if os.path.exists(tmp_out):
            os.remove(tmp_out)


def test_project_curve_preservation_roundtrip():
    """Verify that exporting and reloading a project preserves native C and Q Bézier curves."""
    from plotter_studio.core.geometry import CubicBezierSegment, QuadraticBezierSegment

    svg_curves = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10 50 C 20 10, 80 10, 90 50" stroke="#000000" fill="none"/>
      <path d="M 10 80 Q 50 20, 90 80" stroke="#d32f2f" fill="none"/>
    </svg>"""
    item = load_svg(svg_curves, name="CurvesItem")
    item.transform = AffineTransform.translation(15.0, 25.0).multiply(AffineTransform.scale(1.5))

    doc = Document()
    doc.items.append(item)

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        tmp_path = f.name

    try:
        export_document_to_svg(doc, tmp_path)
        raw_xml = Path(tmp_path).read_text(encoding="utf-8")
        # Exported SVG must contain native C and Q commands, not flattened L chains
        assert " C " in raw_xml
        assert " Q " in raw_xml

        reloaded = load_document_from_svg(tmp_path)
        assert len(reloaded.items) == 1
        r_item = reloaded.items[0]
        assert len(r_item.paths) == 2
        assert isinstance(r_item.paths[0].segments[0], CubicBezierSegment)
        assert isinstance(r_item.paths[1].segments[0], QuadraticBezierSegment)

        # Verify restored local control points match original before transform
        orig_c = item.paths[0].segments[0]
        rest_c = r_item.paths[0].segments[0]
        assert np.allclose(orig_c.start, rest_c.start, atol=1e-3)
        assert np.allclose(orig_c.control1, rest_c.control1, atol=1e-3)
        assert np.allclose(orig_c.control2, rest_c.control2, atol=1e-3)
        assert np.allclose(orig_c.end, rest_c.end, atol=1e-3)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_project_metadata_persistence_and_plot_job_svg_export(tmp_path):
    """Verify device_profile, feed_edge, item.visible, item.locked persistence and export_plot_job_to_svg."""
    from plotter_studio.core.svg_export import export_plot_job_to_svg
    from plotter_studio.pipeline.compiler import compile_document_to_plot_job

    doc = Document()
    doc.page.apply_device_profile("mutoh_xp500", "bottom")
    it1 = ImportItem(
        name="VisibleLocked",
        paths=[VectorPath(points=np.array([[10.0, 10.0], [50.0, 50.0]]), pen_id=1)],
        visible=True,
        locked=True,
    )
    it2 = ImportItem(
        name="HiddenUnlocked",
        paths=[VectorPath(points=np.array([[20.0, 20.0], [60.0, 60.0]]), pen_id=2)],
        visible=False,
        locked=False,
    )
    doc.items.extend([it1, it2])

    proj_file = str(tmp_path / "meta_test.svg")
    export_document_to_svg(doc, proj_file)
    reloaded = load_document_from_svg(proj_file)

    assert reloaded.page.device_profile == "mutoh_xp500"
    assert reloaded.page.feed_edge == "bottom"
    assert len(reloaded.items) == 2
    assert reloaded.items[0].visible is True
    assert reloaded.items[0].locked is True
    assert reloaded.items[1].visible is False
    assert reloaded.items[1].locked is False

    # Test export_plot_job_to_svg
    job = compile_document_to_plot_job(doc)
    plot_svg_file = str(tmp_path / "plot_job.svg")
    export_plot_job_to_svg(job, doc.page, plot_svg_file)
    assert os.path.exists(plot_svg_file)
    svg_text = Path(plot_svg_file).read_text(encoding="utf-8")
    assert "pen_1_" in svg_text
    assert "<path" in svg_text


def test_main_window_dirty_state_and_direct_save(qapp, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from plotter_studio.gui.main_window import MainWindow
    from plotter_studio.gui.commands import AddItemCommand

    doc = Document()
    win = MainWindow(doc)

    assert win.undo_stack.isClean()
    assert "*" not in win.windowTitle()

    it = ImportItem(
        name="TestPath",
        paths=[VectorPath(points=np.array([[10.0, 10.0], [40.0, 40.0]]), pen_id=1)],
    )
    win.undo_stack.push(AddItemCommand(doc, it, win._on_item_structure_changed))
    assert not win.undo_stack.isClean()
    assert "*" in win.windowTitle()

    # If user cancels unsaved prompt, new_document should abort and keep items
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **kw: QMessageBox.StandardButton.Cancel)
    win.new_document()
    assert len(doc.items) == 1

    # Direct save via save_project when current_project_path is set
    save_path = str(tmp_path / "direct_save.svg")
    win.current_project_path = save_path
    assert win.save_project() is True
    assert os.path.exists(save_path)
    assert win.undo_stack.isClean()
    assert "*" not in win.windowTitle()
    assert "direct_save.svg" in win.windowTitle()
    win.close()




