import pytest
from plotter_studio.core.document import Document
from plotter_studio.device import DeviceManager, ConfiguredDevice, ProbeResult
from plotter_studio.gui.page_dialog import PageSetupDialog
from PySide6.QtGui import QUndoStack


def test_page_setup_dialog_preset_and_orientation(qapp):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    stack = QUndoStack()
    mgr = DeviceManager()

    dlg = PageSetupDialog(doc, device_manager=mgr, undo_stack=stack)
    assert dlg.combo_preset.currentData() == "A4"
    assert dlg.combo_orient.currentData() == "landscape"
    assert dlg.spin_width.value() == 297.0
    assert dlg.spin_height.value() == 210.0

    # Switch to A3 Portrait
    dlg.combo_preset.setCurrentIndex(dlg.combo_preset.findData("A3"))
    dlg.combo_orient.setCurrentIndex(dlg.combo_orient.findData("portrait"))
    assert dlg.spin_width.value() == 297.0
    assert dlg.spin_height.value() == 420.0

    # Accept dialog
    dlg.accept()
    assert doc.page.preset == "A3"
    assert doc.page.orientation == "portrait"
    assert stack.count() == 1

    # Test undo
    stack.undo()
    assert doc.page.preset == "A4"
    assert doc.page.orientation == "landscape"

    # Test redo
    stack.redo()
    assert doc.page.preset == "A3"
    assert doc.page.orientation == "portrait"


def test_page_setup_dialog_custom_dimensions(qapp):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    dlg = PageSetupDialog(doc)

    # Edit width
    dlg.spin_width.setValue(500.0)
    dlg.spin_height.setValue(350.0)
    assert dlg.combo_preset.currentData() == "Custom"

    dlg.accept()
    assert doc.page.preset == "Custom"
    assert doc.page.width_mm == 500.0
    assert doc.page.height_mm == 350.0


def test_page_setup_dialog_roller_feed_edge(qapp):
    doc = Document()
    doc.page.device_profile = "mutoh_xp500"
    dlg = PageSetupDialog(doc)
    assert dlg.combo_feed.isEnabled()

    # Change feed edge to left
    dlg.combo_feed.setCurrentIndex(dlg.combo_feed.findData("left"))
    assert doc.page.margin_left_mm == 25.0
    assert doc.page.margin_top_mm == 5.0

    # Change feed edge to bottom
    dlg.combo_feed.setCurrentIndex(dlg.combo_feed.findData("bottom"))
    assert doc.page.margin_bottom_mm == 25.0
    assert doc.page.margin_left_mm == 5.0


def test_page_setup_dialog_cancel_restores_state(qapp):
    doc = Document()
    doc.page.apply_preset("A4", "landscape")
    orig_w = doc.page.width_mm
    orig_h = doc.page.height_mm

    dlg = PageSetupDialog(doc)
    dlg.combo_preset.setCurrentIndex(dlg.combo_preset.findData("A0"))
    dlg.reject()

    assert doc.page.preset == "A4"
    assert doc.page.width_mm == orig_w
    assert doc.page.height_mm == orig_h


def test_page_setup_dialog_asymmetric_margins_and_probe_clip(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: QMessageBox.StandardButton.Ok)

    doc = Document()
    doc.page.apply_device_profile("mutoh_xp500", "top")
    assert doc.page.margin_top_mm == 25.0
    assert doc.page.margin_bottom_mm == 5.0
    assert doc.page.margin_left_mm == 5.0
    assert doc.page.margin_right_mm == 5.0

    dlg = PageSetupDialog(doc)
    assert dlg.spin_margin_top.value() == 25.0
    assert dlg.spin_margin_bottom.value() == 5.0
    assert dlg.spin_margin_left.value() == 5.0
    assert dlg.spin_margin_right.value() == 5.0

    # Changing only left margin preserves right/top/bottom margins
    dlg.spin_margin_left.setValue(12.0)
    assert doc.page.margin_left_mm == 12.0
    assert doc.page.margin_right_mm == 5.0
    assert doc.page.margin_top_mm == 25.0
    assert doc.page.margin_bottom_mm == 5.0

    # Test OH; probe result with custom hard_clip_mm adds margins to form outer sheet size
    res = ProbeResult(
        port="virtual://mutoh",
        success=True,
        model="XP-500",
        hard_clip_mm=(400.0, 250.0),
        detected_format=None,
    )
    dlg._handle_probe_result("virtual://mutoh", res)
    assert doc.page.preset == "Custom"
    assert doc.page.width_mm == pytest.approx(400.0 + 12.0 + 5.0)
    assert doc.page.height_mm == pytest.approx(250.0 + 25.0 + 5.0)

    # Test OH; probe result with A3 Portrait (297 x 420 mm outer sheet -> clip 287 x 390 mm with margins 5/5/25/5)
    doc.page.apply_device_profile("mutoh_xp500", "top")
    res_a3_portrait = ProbeResult(
        port="virtual://mutoh",
        success=True,
        model="XP-500",
        hard_clip_mm=(287.0, 390.0),
        detected_format="A3",
    )
    doc.page.apply_probe_result(res_a3_portrait)
    assert doc.page.preset == "A3"
    assert doc.page.orientation == "portrait"
    assert doc.page.width_mm == pytest.approx(297.0)
    assert doc.page.height_mm == pytest.approx(420.0)


