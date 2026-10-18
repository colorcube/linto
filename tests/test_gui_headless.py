import os
import pytest
from PySide6.QtWidgets import QApplication
from plotter_studio.core.document import Document
from plotter_studio.core.svg_import import load_svg
from plotter_studio.core.svg_export import export_document_to_svg
from plotter_studio.gui.main_window import MainWindow




def test_main_window_headless(qapp, tmp_path):
    doc = Document()
    doc.page.apply_preset("A3", "landscape")
    win = MainWindow(doc)
    win.show()

    # Create and import a test SVG
    svg_content = """<svg width="100mm" height="80mm" viewBox="0 0 100 80" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="40" r="30" stroke="#d32f2f" fill="none"/>
    </svg>"""
    test_svg_path = str(tmp_path / "test.svg")
    with open(test_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    win.import_svg_file(test_svg_path)
    assert len(doc.items) == 1

    item = doc.items[0]
    g_item = win.canvas._item_map[item.item_id]

    # Verify initial scale 1.0 and graphical item scene size
    init_rect = g_item.sceneBoundingRect()
    assert abs(init_rect.width() - 66.0) < 1.0  # 60mm diameter circle + 2*3mm padding
    assert abs(init_rect.height() - 66.0) < 1.0

    # Check item centered
    win.transform_dock.set_active_item(item)
    win.transform_dock.align_center_both()
    b = item.current_bounds
    assert b is not None
    page_center = doc.page.sheet_box.center
    assert abs(b.center.x - page_center.x) < 1.0
    assert abs(b.center.y - page_center.y) < 1.0

    # Fit to page: verify model and graphical item BOTH scale
    win.transform_dock.fit_to_page(margin_mm=20.0)
    b_fit = item.current_bounds
    assert b_fit is not None
    assert b_fit.height > 200.0

    fit_rect = g_item.sceneBoundingRect()
    assert fit_rect.height() > 200.0
    assert abs(fit_rect.height() - b_fit.height - 6.0) < 1.0

    # Fit to plottable area explicitly
    win.transform_dock.fit_to_plottable(margin_mm=10.0)
    b_plot = item.current_bounds
    assert b_plot is not None
    pb = doc.page.plottable_box
    assert abs(b_plot.center.x - pb.center.x) < 1.0
    assert abs(b_plot.center.y - pb.center.y) < 1.0

    # Fit to sheet explicitly
    win.transform_dock.fit_to_sheet(margin_mm=15.0)
    b_sheet = item.current_bounds
    assert b_sheet is not None
    sb = doc.page.sheet_box
    assert abs(b_sheet.center.x - sb.center.x) < 1.0
    assert abs(b_sheet.center.y - sb.center.y) < 1.0

    # Test scale relative (-10%)
    h_before = fit_rect.height()
    win.transform_dock.scale_relative(0.9)
    rect_scaled = g_item.sceneBoundingRect()
    assert rect_scaled.height() < h_before

    # Test direct width edit via dock spinbox
    win.transform_dock._on_obj_w_changed(150.0)
    w_edited = item.current_bounds.width
    assert abs(w_edited - 150.0) < 0.5
    assert abs(g_item.sceneBoundingRect().width() - 156.0) < 1.0

    # Test 1:1 reset
    win.transform_dock.reset_to_original_size()
    assert abs(item.transform.a - 1.0) < 1e-4
    assert abs(g_item.sceneBoundingRect().height() - 66.0) < 1.0

    # Export project
    export_path = str(tmp_path / "project.svg")
    export_document_to_svg(doc, export_path)
    assert os.path.exists(export_path)
    win.close()


def test_docks_and_page_setup_dialog(qapp):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Verify dock instances and titles
    assert win.object_dock is not None
    assert win.transform_dock is not None
    assert win.pen_dock is not None
    assert win.object_dock.windowTitle() == "Objekte & Ebenen"
    assert win.transform_dock.windowTitle() == "Transformation"
    assert win.pen_dock.windowTitle() == "Stifte"

    # Verify group titles in TransformDock
    assert win.transform_dock.grp_transform.title() == "Position"
    assert win.transform_dock.grp_rotation.title() == "Rotation"
    assert win.transform_dock.grp_placement.title() == "Platzieren"
    assert win.transform_dock.grp_scaling.title() == "Skalierung"
    assert win.transform_dock.btn_fit_plottable.text() == "Auf plottbaren Bereich einpassen"
    assert not win.transform_dock.btn_fit_plottable.icon().isNull()
    assert win.transform_dock.btn_fit_sheet.text() == "Auf Blatt einpassen"
    assert not win.transform_dock.btn_fit_sheet.icon().isNull()
    assert win.transform_dock.btn_fit is win.transform_dock.btn_fit_sheet
    assert win.transform_dock.btn_scale_up.text() == "+"
    assert win.transform_dock.btn_scale_down.text() == "-"
    assert win.transform_dock.btn_original_size.text() == "Original"
    assert not win.transform_dock.btn_center_h.icon().isNull()
    assert not win.transform_dock.btn_center_v.icon().isNull()
    assert not win.transform_dock.btn_center_both.icon().isNull()
    assert win.transform_dock.spin_fit_margin.minimumWidth() >= 75

    # Verify that Transform and Pen docks are tabified and title bars hidden
    tabified_with_transform = win.tabifiedDockWidgets(win.transform_dock)
    assert win.pen_dock in tabified_with_transform
    win._update_dock_title_bars()
    assert getattr(win.transform_dock.titleBarWidget(), "_is_dummy_title_bar", False) is True
    assert getattr(win.pen_dock.titleBarWidget(), "_is_dummy_title_bar", False) is True
    # Standalone object dock has native title bar
    assert win.object_dock.titleBarWidget() is None

    # Verify toolbar paper setup button & status bar
    assert "DIN A3" in win.btn_page_setup.text()
    assert "DIN A3" in win.lbl_paper_status.text()

    # Test PageSetupDialog interaction
    from plotter_studio.gui.page_dialog import PageSetupDialog
    dlg = PageSetupDialog(doc, win.device_manager, win.undo_stack, parent=win)
    dlg.page_changed.connect(win._on_page_changed)
    dlg.combo_preset.setCurrentIndex(dlg.combo_preset.findData("A4"))
    dlg.accept()

    assert doc.page.preset == "A4"
    assert "DIN A4" in win.btn_page_setup.text()
    assert "DIN A4" in win.lbl_paper_status.text()

    # Verify tab switching (raise)
    win.transform_dock.raise_()
    assert win.transform_dock.isVisible()

    win.pen_dock.raise_()
    assert win.pen_dock.isVisible()

    win.close()


def test_interactive_corner_handle_scaling(qapp, tmp_path):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Create and import a test SVG
    svg_content = """<svg width="50mm" height="50mm" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="50" height="50" stroke="#000" fill="none"/>
    </svg>"""
    test_svg_path = str(tmp_path / "square.svg")
    with open(test_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    win.import_svg_file(test_svg_path)
    item = doc.items[0]
    g_item = win.canvas._item_map[item.item_id]

    g_item.setSelected(True)
    ob = item.original_bounds
    assert ob is not None

    # Verify handle detection at corners
    from PySide6.QtCore import QPointF
    assert g_item._handle_at(QPointF(ob.min_x, ob.min_y)) == "tl"
    assert g_item._handle_at(QPointF(ob.max_x, ob.min_y)) == "tr"
    assert g_item._handle_at(QPointF(ob.min_x, ob.max_y)) == "bl"
    assert g_item._handle_at(QPointF(ob.max_x, ob.max_y)) == "br"
    assert g_item._handle_at(QPointF(ob.center.x, ob.center.y)) is None

    # Verify cursors
    from PySide6.QtCore import Qt
    assert g_item._cursor_for_handle("tl") == Qt.SizeFDiagCursor
    assert g_item._cursor_for_handle("br") == Qt.SizeFDiagCursor
    assert g_item._cursor_for_handle("tr") == Qt.SizeBDiagCursor
    assert g_item._cursor_for_handle("bl") == Qt.SizeBDiagCursor

    # Simulate mouse press on bottom-right handle
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent
    from PySide6.QtCore import QEvent
    press_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMousePress)
    press_event.setButton(Qt.LeftButton)
    press_event.setPos(QPointF(ob.max_x, ob.max_y))
    press_event.setScenePos(g_item.mapToScene(QPointF(ob.max_x, ob.max_y)))
    g_item.mousePressEvent(press_event)
    assert g_item._resizing_handle == "br"

    # Simulate drag to double size (from 50mm to 100mm)
    move_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseMove)
    current_scene_br = g_item.mapToScene(QPointF(ob.max_x, ob.max_y))
    move_event.setScenePos(current_scene_br + QPointF(50.0, 50.0))
    g_item.mouseMoveEvent(move_event)

    # Scale should be approximately 2.0
    assert abs(item.transform.a - 2.0) < 0.1
    assert abs(item.transform.d - 2.0) < 0.1
    assert abs(item.current_bounds.width - 100.0) < 5.0

    # Simulate mouse release
    release_event = QGraphicsSceneMouseEvent(QEvent.GraphicsSceneMouseRelease)
    release_event.setButton(Qt.LeftButton)
    g_item.mouseReleaseEvent(release_event)
    assert g_item._resizing_handle is None

    win.close()


def test_drag_and_drop_import_and_initial_zoom(qapp, tmp_path):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Verify initial zoom flag is set by showEvent
    assert getattr(win, "_initial_zoom_done", False) is True

    # Create two test SVG files to test multi-file drop
    svg_content = """<svg width="40mm" height="40mm" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="40" height="40" stroke="#ff0000" fill="none"/>
    </svg>"""
    test_svg_path1 = str(tmp_path / "drop_test_1.svg")
    test_svg_path2 = str(tmp_path / "drop_test_2.svg")
    for p in (test_svg_path1, test_svg_path2):
        with open(p, "w", encoding="utf-8") as f:
            f.write(svg_content)

    # Simulate DropEvent with QMimeData containing two URLs
    from PySide6.QtCore import QMimeData, QUrl, QPointF, Qt
    from PySide6.QtGui import QDropEvent
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(test_svg_path1), QUrl.fromLocalFile(test_svg_path2)])

    drop_event = QDropEvent(
        QPointF(200.0, 200.0),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    win.dropEvent(drop_event)

    # Document should now contain both dropped items
    assert len(doc.items) == 2
    assert "drop_test_1" in doc.items[0].name
    assert "drop_test_2" in doc.items[1].name

    win.close()


def test_menu_exit_clean_shutdown(qapp, tmp_path):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Import an item and select it
    svg_content = """<svg width="40mm" height="40mm" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <circle cx="20" cy="20" r="15" stroke="#1976d2" fill="none"/>
    </svg>"""
    test_svg_path = str(tmp_path / "exit_test.svg")
    with open(test_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    win.import_svg_file(test_svg_path)

    # Verify that triggering act_exit closes window and cleans up without crash
    win.act_exit.trigger()
    assert not win.isVisible()


def test_rotation_ui_and_undo(qapp, tmp_path):
    import math
    import numpy as np
    from plotter_studio.pipeline.compiler import compile_document_to_plot_job

    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Create a non-square rectangle (60mm x 30mm)
    svg_content = """<svg width="60mm" height="30mm" viewBox="0 0 60 30" xmlns="http://www.w3.org/2000/svg">
      <rect x="0" y="0" width="60" height="30" stroke="#000" fill="none"/>
    </svg>"""
    test_svg_path = str(tmp_path / "rect.svg")
    with open(test_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    win.import_svg_file(test_svg_path)
    assert len(doc.items) == 1
    item = doc.items[0]
    g_item = win.canvas._item_map[item.item_id]
    g_item.setSelected(True)
    win._on_selection_changed()

    b0 = item.current_bounds
    assert b0 is not None
    assert math.isclose(b0.width, 60.0, abs_tol=0.5)
    assert math.isclose(b0.height, 30.0, abs_tol=0.5)
    orig_center_x, orig_center_y = b0.center.x, b0.center.y

    # Verify dock rotation controls exist and are enabled
    assert win.transform_dock.rot_group.isEnabled()
    assert win.transform_dock.btn_rotate_cw is not None
    assert win.transform_dock.btn_rotate_ccw is not None

    # Rotate +90° clockwise via dock button
    win.transform_dock.btn_rotate_cw.click()

    b1 = item.current_bounds
    assert b1 is not None
    # Width and height should be swapped
    assert math.isclose(b1.width, 30.0, abs_tol=0.5)
    assert math.isclose(b1.height, 60.0, abs_tol=0.5)
    # Center should remain invariant
    assert math.isclose(b1.center.x, orig_center_x, abs_tol=1e-4)
    assert math.isclose(b1.center.y, orig_center_y, abs_tol=1e-4)

    # Dock fields should display updated dimensions and 100% scale
    assert math.isclose(win.transform_dock.spin_obj_w.value(), 30.0, abs_tol=0.5)
    assert math.isclose(win.transform_dock.spin_obj_h.value(), 60.0, abs_tol=0.5)
    assert math.isclose(win.transform_dock.spin_obj_scale.value(), 100.0, abs_tol=0.1)

    # Test Undo
    win.act_undo.trigger()
    b_undo = item.current_bounds
    assert math.isclose(b_undo.width, 60.0, abs_tol=0.5)
    assert math.isclose(b_undo.height, 30.0, abs_tol=0.5)

    # Test Redo
    win.act_redo.trigger()
    b_redo = item.current_bounds
    assert math.isclose(b_redo.width, 30.0, abs_tol=0.5)
    assert math.isclose(b_redo.height, 60.0, abs_tol=0.5)

    # Rotate -90° counter-clockwise via menu action
    win.act_rotate_ccw.trigger()
    b2 = item.current_bounds
    assert math.isclose(b2.width, 60.0, abs_tol=0.5)
    assert math.isclose(b2.height, 30.0, abs_tol=0.5)

    # Test pipeline compiler with rotated item
    win.transform_dock.btn_rotate_cw.click()
    job = compile_document_to_plot_job(doc)
    assert len(job.layers) > 0
    layer = next(iter(job.layers.values()))
    # All points in compiled layer must fall within b1
    pts = np.vstack(layer.lines)
    assert np.min(pts[:, 0]) >= b1.min_x - 0.1
    assert np.max(pts[:, 0]) <= b1.max_x + 0.1
    assert np.min(pts[:, 1]) >= b1.min_y - 0.1
    assert np.max(pts[:, 1]) <= b1.max_y + 0.1

    win.close()


def test_main_window_open_project(qapp, tmp_path):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    assert win.act_open_project is not None
    assert win.act_open_project.text() == "Projekt &öffnen..."

    # Check loading tmp/projekt.svg
    if os.path.exists("tmp/projekt.svg"):
        win.load_project_file("tmp/projekt.svg")
        assert len(win.doc.items) == 3
        assert win.doc.page.preset == "A3"
        assert len(win.doc.pens) == 8
        assert "3 Objekt(e)" in win.lbl_info.text()
        assert len(win.canvas._item_map) == 3
        assert win.object_dock.tree.topLevelItemCount() == 3

    # Check opening standard SVG via load_project_file
    if os.path.exists("examples/TEST_10cm.svg"):
        win.load_project_file("examples/TEST_10cm.svg")
        assert len(win.doc.items) == 1
        assert "Pfade" in win.lbl_info.text()
        assert win.canvas._item_map is not None
        assert win.object_dock.tree.topLevelItemCount() == 1
        assert win.doc.page.preset == "Custom"
        assert win.doc.page.width_mm == 100.0
        assert win.doc.page.height_mm == 100.0

    win.close()


def test_graphics_item_paints_native_curves_and_duplicates(qapp):
    """Verify GraphicsImportItem.paint renders Q, C, and Arc segments via QPainterPath and duplicate_item preserves segments."""
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QStyleOptionGraphicsItem

    svg_curves = """<svg width="100mm" height="100mm" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <path d="M 10 20 L 40 20 Q 60 5, 80 20 C 95 35, 95 65, 80 80 Z" stroke="#000000" fill="none"/>
      <circle cx="50" cy="50" r="25" stroke="#d32f2f" fill="none"/>
    </svg>"""
    doc = Document()
    item = load_svg(svg_curves, name="Curves")
    doc.items.append(item)

    dup = doc.duplicate_item(item, offset_mm=15.0)
    assert len(dup.paths) == len(item.paths)
    assert dup.paths[0].has_curves is True
    assert dup.paths[1].has_curves is True

    win = MainWindow(doc)
    win.canvas.rebuild_items()
    g_item = win.canvas._item_map[item.item_id]

    img = QImage(200, 200, QImage.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPainter(img)
    opt = QStyleOptionGraphicsItem()
    g_item.paint(painter, opt, None)
    painter.end()
    win.close()

