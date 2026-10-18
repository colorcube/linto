"""Tests for DeviceManager and DeviceSettingsDialog."""

import pytest
from pathlib import Path
from plotter_studio.device.manager import DeviceManager, ConfiguredDevice
from plotter_studio.gui.device_dialog import DeviceSettingsDialog


def test_device_manager_defaults_and_persistence(tmp_path):
    config_file = tmp_path / "devices.yaml"
    mgr = DeviceManager(config_path=config_file)

    # Initial defaults should exist and be saved
    devices = mgr.list_devices()
    assert len(devices) >= 2
    assert mgr.active_device_id in [d.id for d in devices]
    assert config_file.is_file()

    # Active device lookup
    active = mgr.get_active_device()
    assert active is not None
    assert active.id == mgr.active_device_id

    # Switch active device
    other_id = [d.id for d in devices if d.id != active.id][0]
    mgr.set_active_device(other_id)
    assert mgr.active_device_id == other_id
    assert mgr.get_active_device().id == other_id

    # Add new device
    new_dev = ConfiguredDevice(
        id="test_custom_plotter",
        name="Mein Custom Plotter",
        model_id="mutoh_xp500",
        port="/dev/ttyUSB1",
        baudrate=9600,
        flow_control="none",
        margin_profile="norm",
        rotation=90,
        swap_xy=True,
    )
    mgr.add_device(new_dev)
    assert len(mgr.list_devices()) == len(devices) + 1
    assert mgr.get_device("test_custom_plotter") is not None

    # Reload in new manager instance from same file
    mgr2 = DeviceManager(config_path=config_file)
    assert len(mgr2.list_devices()) == len(devices) + 1
    loaded_dev = mgr2.get_device("test_custom_plotter")
    assert loaded_dev is not None
    assert loaded_dev.name == "Mein Custom Plotter"
    assert loaded_dev.baudrate == 9600
    assert loaded_dev.flow_control == "none"
    assert loaded_dev.swap_xy is True

    # Update device
    new_dev.name = "Umbenannter Plotter"
    new_dev.flow_control = "xonxoff"
    mgr2.update_device(new_dev)
    assert mgr2.get_device("test_custom_plotter").name == "Umbenannter Plotter"
    assert mgr2.get_device("test_custom_plotter").flow_control == "xonxoff"

    # Delete device
    mgr2.delete_device("test_custom_plotter")
    assert mgr2.get_device("test_custom_plotter") is None


def test_device_dialog_headless(qapp, tmp_path):
    config_file = tmp_path / "devices.yaml"
    mgr = DeviceManager(config_path=config_file)

    dlg = DeviceSettingsDialog(mgr)
    assert dlg.windowTitle() == "Plotter-Geräte konfigurieren"
    assert dlg.list_devices.count() == len(mgr.list_devices())

    # Switch selection in dialog
    dlg.list_devices.setCurrentRow(0)
    assert dlg.txt_name.text() != ""

    # Test adding new device via dialog button
    initial_count = dlg.list_devices.count()
    dlg._on_add_device()
    assert dlg.list_devices.count() == initial_count + 1

    # Test save button label, baudrate and flow_control
    assert dlg.btn_save_item.text() == "Speichern"
    dlg.txt_name.setText("Geänderter Name")
    assert "300" in [dlg.combo_baud.itemText(i) for i in range(dlg.combo_baud.count())]
    dlg.combo_baud.setCurrentText("300")

    flow_keys = [dlg.combo_flow.itemData(i) for i in range(dlg.combo_flow.count())]
    assert "rtscts" in flow_keys
    assert "dsrdtr" not in flow_keys
    assert "xonxoff" in flow_keys
    assert "none" in flow_keys

    dlg.combo_flow.setCurrentIndex(dlg.combo_flow.findData("xonxoff"))
    dlg.combo_bytesize.setCurrentIndex(dlg.combo_bytesize.findData(7))
    dlg.combo_parity.setCurrentIndex(dlg.combo_parity.findData("E"))
    dlg.combo_stopbits.setCurrentIndex(dlg.combo_stopbits.findData(1))
    dlg._on_save_current_device()
    assert "Geänderter Name" in dlg.list_devices.currentItem().text()
    saved_dev = mgr.get_device(dlg._current_device.id)
    assert saved_dev.baudrate == 300
    assert saved_dev.flow_control == "xonxoff"
    assert saved_dev.bytesize == 7
    assert saved_dev.parity == "E"
    assert saved_dev.stopbits == 1
    assert saved_dev.framing_label == "7E1"

    # Test connection test error handling (background thread, non-blocking)
    dlg.combo_port.setEditText("/dev/nonexistent_test_port")
    dlg._on_test_device()
    if dlg._probe_thread is not None:
        dlg._probe_thread.join(timeout=2.0)
    qapp.processEvents()
    assert "Fehlgeschlagen:" in dlg.lbl_test_result.text()

    dlg.close()


def test_device_manager_pure_python_signals_without_qobject(tmp_path):
    from PySide6.QtCore import QObject
    config_file = tmp_path / "devices_pure.yaml"
    mgr = DeviceManager(config_path=config_file)
    assert not isinstance(mgr, QObject)

    changed_events = []
    updated_events = []
    mgr.device_changed.connect(lambda dev: changed_events.append(dev.id))
    mgr.devices_updated.connect(lambda: updated_events.append(True))

    devices = mgr.list_devices()
    other_id = [d.id for d in devices if d.id != mgr.active_device_id][0]
    mgr.set_active_device(other_id)
    assert changed_events == [other_id]

    new_dev = ConfiguredDevice(id="dev_sig", name="Signal Test")
    mgr.add_device(new_dev)
    assert len(updated_events) == 1



OLD_DEVICES_YAML = """active_device_id: mutoh_xp500_usb
devices:
- id: mutoh_xp500_usb
  name: Mutoh XP-500 (Seriell)
  model_id: mutoh_xp500
  port: /dev/ttyUSB0
  baudrate: 19200
  flow_control: dsrdtr
  margin_profile: exp
  rotation: 0
  swap_xy: false
  invert_x: false
  invert_y: false
- id: interim
  name: Interim build
  model_id: mutoh_xp500
  port: tcp://127.0.0.1:9999
  baudrate: 19200
  flow_control: xonxoff
  margin_profile: exp
  rotation: 0
  swap_xy: true
  invert_x: false
  invert_y: true
  some_future_key: 42
"""


def test_old_devices_yaml_migrates_to_axis_corrections(tmp_path):
    """Old configs (absolute axis values) must not override the XP-500 profile mapping."""
    from plotter_studio.core.document import Document
    from plotter_studio.device import build_emitter

    config_file = tmp_path / "devices.yaml"
    config_file.write_text(OLD_DEVICES_YAML, encoding="utf-8")
    mgr = DeviceManager(config_path=config_file)

    usb = mgr.get_device("mutoh_xp500_usb")
    interim = mgr.get_device("interim")
    assert usb.flow_control == "rtscts"  # dsrdtr does nothing on Linux
    for dev in (usb, interim):
        assert (dev.rotation, dev.swap_xy, dev.invert_x, dev.invert_y) == (0, False, False, False)
        assert dev.axis_schema == 2

    # Full chain DeviceManager -> build_emitter: A3 landscape EXP corners
    # X = feed (sheet down), Y = carriage (sheet right); measured OH ~ +-5399 / +-8209
    doc = Document()
    for dev in (usb, interim):
        em = build_emitter(document=doc, device=dev)
        pb = doc.page.plottable_box
        assert em.to_plotter_units(pb.min_x, pb.min_y, 420.0, 297.0, center_mm=(pb.center.x, pb.center.y)) == (-5340, -8200)
        assert em.to_plotter_units(pb.max_x, pb.max_y, 420.0, 297.0, center_mm=(pb.center.x, pb.center.y)) == (5340, 8200)

    # Migration is persisted
    assert "axis_schema: 2" in config_file.read_text(encoding="utf-8")


def test_new_device_defaults_have_no_axis_correction():
    dev = ConfiguredDevice(id="x", name="HP 7475", model_id="hpgl_generic")
    assert (dev.rotation, dev.swap_xy, dev.invert_x, dev.invert_y) == (0, False, False, False)
