import os
import pytest
from PySide6.QtWidgets import QApplication
from plotter_studio.core.document import Document
from plotter_studio.core.svg_import import load_svg
from plotter_studio.core.svg_export import export_document_to_svg
from plotter_studio.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


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
    win.layout_dock.set_active_item(item)
    win.layout_dock.align_center_both()
    b = item.current_bounds
    assert b is not None
    page_center = doc.page.sheet_box.center
    assert abs(b.center.x - page_center.x) < 1.0
    assert abs(b.center.y - page_center.y) < 1.0

    # Fit to page: verify model and graphical item BOTH scale
    win.layout_dock.fit_to_page(margin_mm=20.0)
    b_fit = item.current_bounds
    assert b_fit is not None
    assert b_fit.height > 200.0

    fit_rect = g_item.sceneBoundingRect()
    assert fit_rect.height() > 200.0
    assert abs(fit_rect.height() - b_fit.height - 6.0) < 1.0

    # Test scale relative (-10%)
    h_before = fit_rect.height()
    win.layout_dock.scale_relative(0.9)
    rect_scaled = g_item.sceneBoundingRect()
    assert rect_scaled.height() < h_before

    # Test direct width edit via dock spinbox
    win.layout_dock._on_obj_w_changed(150.0)
    w_edited = item.current_bounds.width
    assert abs(w_edited - 150.0) < 0.5
    assert abs(g_item.sceneBoundingRect().width() - 156.0) < 1.0

    # Test 1:1 reset
    win.layout_dock.reset_to_original_size()
    assert abs(item.transform.a - 1.0) < 1e-4
    assert abs(g_item.sceneBoundingRect().height() - 66.0) < 1.0

    # Export project
    export_path = str(tmp_path / "project.svg")
    export_document_to_svg(doc, export_path)
    assert os.path.exists(export_path)
    assert os.path.getsize(export_path) > 100

    win.close()
