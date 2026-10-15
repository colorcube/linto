import os
import time
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication
from plotter_studio.core.document import Document
from plotter_studio.gui.main_window import MainWindow
from plotter_studio.gui.canvas import CanvasMode
from plotter_studio.device import ProbeResult
from plotter_studio.emulator import VirtualPlotter, PtyServer


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

    # Initially in Layout mode: layout docks visible, plot dock hidden
    assert win.canvas._mode == CanvasMode.LAYOUT
    assert win.simulation_bar.isHidden()
    assert win.plot_dock.isHidden()
    assert win.paper_dock.isVisible()

    # 1. Switch to Plot mode: layout docks hidden, plot dock visible
    win.switch_to_plot_mode()
    assert win.canvas._mode == CanvasMode.PLOT
    assert not win.simulation_bar.isHidden()
    assert win.plot_dock.isVisible()
    assert win.paper_dock.isHidden()
    assert win.transform_dock.isHidden()
    assert win.pen_dock.isHidden()

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
    assert win.plot_dock.isHidden()
    assert win.paper_dock.isVisible()
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


def test_plot_dock_device_controls(qapp, tmp_path):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    win = MainWindow(doc)
    win.show()

    svg_content = """<svg width="60mm" height="40mm" viewBox="0 0 60 40" xmlns="http://www.w3.org/2000/svg">
      <line x1="10" y1="10" x2="50" y2="30" stroke="#000000"/>
    </svg>"""
    test_svg = str(tmp_path / "test_line.svg")
    with open(test_svg, "w", encoding="utf-8") as f:
        f.write(svg_content)
    win.import_svg_file(test_svg)
    win.switch_to_plot_mode()

    dock = win.plot_dock
    assert dock.isVisible()
    assert dock.combo_port.count() > 0

    # Test margins combobox
    assert dock.combo_margins.count() >= 4
    dock.combo_margins.setCurrentIndex(1)  # norm
    assert dock.combo_margins.currentData() == "norm"
    dock.combo_margins.setCurrentIndex(0)  # exp
    assert dock.combo_margins.currentData() == "exp"

    # Test probe handling
    mock_res = ProbeResult(
        port="tcp://127.0.0.1:9999",
        success=True,
        model="Mutoh XP-500",
        units_per_mm=40.0,
        detected_format="A3",
        hard_clip_mm=(390.0, 287.0),
    )
    dock._on_probe_done(mock_res)
    assert "Mutoh XP-500" in dock.lbl_probe_status.text()
    assert "A3" in dock.lbl_probe_status.text()

    # Test probe failure
    fail_res = ProbeResult(
        port="/dev/nonexistent",
        success=False,
        error_message="Gerät nicht gefunden",
    )
    dock._on_probe_done(fail_res)
    assert "⚠️ Gerät nicht gefunden" in dock.lbl_probe_status.text()

    # Test live streaming with VirtualPlotter over PtyServer
    plotter = VirtualPlotter(paper="A4", margin_profile="EXP")
    symlink = tmp_path / "gui_test_port"
    server = PtyServer(plotter, symlink_path=symlink)
    port_path = server.start()

    try:
        dock.combo_port.setEditText(port_path)
        assert dock.btn_start_plot.isEnabled()
        assert not dock.btn_pause_plot.isEnabled()
        assert not dock.btn_abort_plot.isEnabled()

        # Start streaming
        dock.start_plot()
        assert not dock.btn_start_plot.isEnabled()
        assert dock.btn_pause_plot.isEnabled()
        assert dock.btn_abort_plot.isEnabled()

        # Wait for completion (process Qt events)
        start_t = time.time()
        while dock._streamer and dock._streamer.is_active() and (time.time() - start_t < 3.0):
            qapp.processEvents()
            time.sleep(0.02)

        # Allow final Qt signals to propagate
        for _ in range(15):
            qapp.processEvents()
            time.sleep(0.01)

        assert dock.progress_bar.value() == 100
        assert "✓" in dock.lbl_stream_status.text()
        assert dock.btn_start_plot.isEnabled()
        assert not dock.btn_pause_plot.isEnabled()
        assert not dock.btn_abort_plot.isEnabled()

    finally:
        server.stop()
        win.close()
        win.cleanup()


def test_plot_dock_pipeline_dirty_and_nodes(qapp, tmp_path):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # 1. Test setting show_nodes before plot mode
    win.plot_dock.chk_show_nodes.setChecked(True)
    assert win.canvas._show_nodes is True

    svg_content = """<svg width="40mm" height="40mm" viewBox="0 0 40 40">
      <polyline points="5,5 20,35 35,5" stroke="#000" />
    </svg>"""
    test_svg = str(tmp_path / "nodes_dirty.svg")
    with open(test_svg, "w", encoding="utf-8") as f:
        f.write(svg_content)
    win.import_svg_file(test_svg)
    win.switch_to_plot_mode()

    # Node visibility should have carried over to plot preview item
    preview = win.canvas._plot_preview_item
    assert preview is not None
    assert preview.show_nodes is True
    assert not win.plot_dock.is_pipeline_dirty()

    # 2. Modify a pipeline setting -> should mark pipeline dirty
    dock = win.plot_dock
    dock.spin_simplify.setValue(0.15)
    assert dock.is_pipeline_dirty() is True
    assert "geändert" in dock.btn_recompute.text()

    # Recompute clears dirty flag
    dock.btn_recompute.click()
    assert dock.is_pipeline_dirty() is False
    assert "geändert" not in dock.btn_recompute.text()

    # Modify another setting (clip) -> dirty again
    dock.chk_clip.setChecked(True)
    assert dock.is_pipeline_dirty() is True

    # 3. Auto-recompute on export
    hpgl_out = str(tmp_path / "dirty_export.hpgl")
    from PySide6.QtWidgets import QFileDialog
    orig_save = QFileDialog.getSaveFileName
    QFileDialog.getSaveFileName = lambda *args, **kwargs: (hpgl_out, "HP-GL (*.hpgl)")
    try:
        win.export_hpgl_dialog()
        # Export should have auto-recompiled and cleared dirty flag
        assert dock.is_pipeline_dirty() is False
    finally:
        QFileDialog.getSaveFileName = orig_save

    win.close()
    win.cleanup()


