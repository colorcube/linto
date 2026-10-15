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
    assert loaded_dev.swap_xy is True

    # Update device
    new_dev.name = "Umbenannter Plotter"
    mgr2.update_device(new_dev)
    assert mgr2.get_device("test_custom_plotter").name == "Umbenannter Plotter"

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

    # Test save button label and action
    assert dlg.btn_save_item.text() == "Speichern"
    dlg.txt_name.setText("Geänderter Name")
    dlg._on_save_current_device()
    assert "Geänderter Name" in dlg.list_devices.currentItem().text()

    # Test connection test error handling (fast timeout, non-blocking)
    dlg.combo_port.setEditText("/dev/nonexistent_test_port")
    dlg._on_test_device()
    assert "Fehlgeschlagen:" in dlg.lbl_test_result.text()

    dlg.close()
