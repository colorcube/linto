import os
import pytest
from PySide6.QtWidgets import QApplication
from plotter_studio.core.document import Document
from plotter_studio.gui.main_window import MainWindow
from plotter_studio.gui.canvas import CanvasMode


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_plot_mode_switching_and_simulation(qapp, tmp_path):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    win = MainWindow(doc)
    win.show()

    # Create and import a test SVG
    svg_content = """<svg width="100mm" height="80mm" viewBox="0 0 100 80" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="10" width="80" height="60" stroke="#000000" fill="none"/>
      <circle cx="50" cy="40" r="25" stroke="#d32f2f" fill="none"/>
    </svg>"""
    test_svg_path = str(tmp_path / "test_plot.svg")
    with open(test_svg_path, "w", encoding="utf-8") as f:
        f.write(svg_content)

    win.import_svg_file(test_svg_path)
    assert len(doc.items) == 1

    # Initially in Layout mode
    assert win.canvas._mode == CanvasMode.LAYOUT
    assert win.simulation_bar.isHidden()

    # 1. Switch to Plot mode
    win.switch_to_plot_mode()
    assert win.canvas._mode == CanvasMode.PLOT
    assert not win.simulation_bar.isHidden()
    assert win.plot_dock.isVisible()

    # Check that layout items are hidden and preview item is active
    item = doc.items[0]
    g_item = win.canvas._item_map[item.item_id]
    assert not g_item.isVisible()

    preview_item = win.canvas._plot_preview_item
    assert preview_item is not None
    assert preview_item.isVisible()
    assert preview_item.job is not None
    assert len(preview_item.job.steps) > 0

    # 2. Check pre-flight statistics in plot dock
    draw_text = win.plot_dock.lbl_draw.text()
    assert "m" in draw_text
    assert float(draw_text.replace(" m", "")) > 0.0

    travel_text = win.plot_dock.lbl_travel.text()
    assert "m" in travel_text

    duration_text = win.plot_dock.lbl_duration.text()
    assert "s" in duration_text

    assert "✓ Alle Pfade im plottbaren Bereich" in win.plot_dock.lbl_warnings.text()

    # 3. Verify circle and rect are composed of individual segments (not single whole objects)
    draw_steps = [s for s in preview_item.job.steps if s.action == "DRAW"]
    assert len(draw_steps) > 10
    for s in draw_steps:
        assert len(s.points) == 2  # 1 segment per step

    # 4. Test simulation scrubber
    total_steps = len(preview_item.job.steps)
    half_step = total_steps // 2
    win.simulation_bar.slider.setValue(half_step)
    assert preview_item.current_step == half_step

    # 5. Test travel toggle
    win.plot_dock.chk_show_travels.setChecked(False)
    assert not preview_item.show_travels
    win.plot_dock.chk_show_travels.setChecked(True)
    assert preview_item.show_travels

    # 6. Test coordinate node points toggle
    assert not preview_item.show_nodes
    win.plot_dock.chk_show_nodes.setChecked(True)
    assert preview_item.show_nodes
    assert win.act_show_nodes.isChecked()

    # Paint test with nodes enabled (full view and scrubbing)
    from PySide6.QtGui import QPainter, QImage
    img = QImage(400, 300, QImage.Format_ARGB32)
    painter = QPainter(img)
    preview_item.set_simulation_step(total_steps)
    preview_item.paint(painter, None)
    preview_item.set_simulation_step(half_step)
    preview_item.paint(painter, None)
    painter.end()

    win.plot_dock.chk_show_nodes.setChecked(False)
    assert not preview_item.show_nodes
    assert not win.act_show_nodes.isChecked()

    # 7. Test simulation play/pause
    win.simulation_bar.play()
    assert win.simulation_bar.is_playing
    win.simulation_bar.pause()
    assert not win.simulation_bar.is_playing

    # 6. Switch back to Layout mode
    win.switch_to_layout_mode()
    assert win.canvas._mode == CanvasMode.LAYOUT
    assert win.simulation_bar.isHidden()
    assert g_item.isVisible()
    assert not preview_item.isVisible()

    # 7. Clean teardown
    win.close()
    win.cleanup()


def test_plot_mode_exports(qapp, tmp_path, monkeypatch):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    win = MainWindow(doc)
    win.show()

    svg_content = """<svg width="50mm" height="50mm" viewBox="0 0 50 50" xmlns="http://www.w3.org/2000/svg">
      <line x1="5" y1="5" x2="45" y2="45" stroke="#000000"/>
    </svg>"""
    test_svg = str(tmp_path / "simple.svg")
    with open(test_svg, "w", encoding="utf-8") as f:
        f.write(svg_content)
    win.import_svg_file(test_svg)
    win.switch_to_plot_mode()

    # Test HP-GL export
    hpgl_out = str(tmp_path / "out.hpgl")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (hpgl_out, "HP-GL (*.hpgl)")
    )
    win.export_hpgl_dialog()
    assert os.path.exists(hpgl_out)
    with open(hpgl_out, "r", encoding="ascii") as f:
        content = f.read()
    assert "IN;" in content
    assert "SP1;" in content
    assert "PU" in content
    assert "PD" in content
    assert "SP0;" in content

    # Test Plot-SVG export
    svg_out = str(tmp_path / "out.svg")
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (svg_out, "SVG (*.svg)")
    )
    win.export_plot_svg_dialog()
    assert os.path.exists(svg_out)
    with open(svg_out, "r", encoding="utf-8") as f:
        svg_text = f.read()
    assert "<svg" in svg_text
    assert "<path" in svg_text

    win.close()
    win.cleanup()
