"""Dialog for managing plotter devices, connections, and hardware testing."""

from __future__ import annotations

import copy
import uuid
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox,
    QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox,
    QDialogButtonBox
)

from ..device.manager import DeviceManager, ConfiguredDevice
from ..device.probe import list_serial_ports, probe_plotter
from .icons import get_icon


class DeviceSettingsDialog(QDialog):
    """Configuration dialog for plotter devices."""

    def __init__(self, device_manager: DeviceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Plotter-Geräte konfigurieren")
        self.setMinimumSize(680, 480)
        self.manager = device_manager
        self._current_device: Optional[ConfiguredDevice] = None

        self._init_ui()
        self._load_devices_list()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Content horizontal layout: left (device list) + right (editor)
        content_layout = QHBoxLayout()

        # Left column: Device list & actions
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("<b>Eingerichtete Geräte:</b>"))

        self.list_devices = QListWidget()
        self.list_devices.currentItemChanged.connect(self._on_device_selected)
        left_layout.addWidget(self.list_devices)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Hinzufügen")
        self.btn_add.setIcon(get_icon("plus"))
        self.btn_add.clicked.connect(self._on_add_device)

        self.btn_delete = QPushButton("Löschen")
        self.btn_delete.setIcon(get_icon("delete"))
        self.btn_delete.clicked.connect(self._on_delete_device)

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        left_layout.addLayout(btn_row)

        content_layout.addLayout(left_layout, 1)

        # Right column: Editor fields
        self.grp_editor = QGroupBox("Geräteeinstellungen")
        e_layout = QVBoxLayout(self.grp_editor)

        form = QFormLayout()

        self.txt_name = QLineEdit()
        form.addRow("Bezeichnung:", self.txt_name)

        self.combo_model = QComboBox()
        self.combo_model.addItem("Mutoh XP-500", "mutoh_xp500")
        form.addRow("Modellprofil:", self.combo_model)

        port_row = QHBoxLayout()
        self.combo_port = QComboBox()
        self.combo_port.setEditable(True)
        self.combo_port.setToolTip("Serieller Port (z.B. /dev/ttyUSB0) oder TCP (tcp://127.0.0.1:9999)")
        self.btn_refresh_ports = QPushButton()
        self.btn_refresh_ports.setIcon(get_icon("refresh"))
        self.btn_refresh_ports.setToolTip("Ports aktualisieren")
        self.btn_refresh_ports.setFixedWidth(32)
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)

        port_row.addWidget(self.combo_port)
        port_row.addWidget(self.btn_refresh_ports)
        form.addRow("Schnittstelle:", port_row)

        self.combo_baud = QComboBox()
        for b in [9600, 19200, 38400, 57600, 115200]:
            self.combo_baud.addItem(str(b), b)
        self.combo_baud.setCurrentText("19200")
        form.addRow("Baudrate:", self.combo_baud)

        self.combo_margins = QComboBox()
        self.combo_margins.addItem("EXP (Erweitert: 25 / 5 / 5 / 5 mm)", "exp")
        self.combo_margins.addItem("NORM (Normal: 25 / 10 / 10 / 10 mm)", "norm")
        self.combo_margins.addItem("TYPE1 (38 / 10 / 10 / 10 mm)", "type1")
        self.combo_margins.addItem("TYPE3 (38 / 5 / 5 / 5 mm)", "type3")
        form.addRow("Randfenster:", self.combo_margins)

        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem("0° (Standard)", 0)
        self.combo_rotation.addItem("90° (Vorschubachse)", 90)
        self.combo_rotation.addItem("180°", 180)
        self.combo_rotation.addItem("270°", 270)
        form.addRow("Gerätedrehung:", self.combo_rotation)

        axes_layout = QHBoxLayout()
        self.chk_swap_xy = QCheckBox("X↔Y tauschen")
        self.chk_invert_x = QCheckBox("X spiegeln")
        self.chk_invert_y = QCheckBox("Y spiegeln")
        axes_layout.addWidget(self.chk_swap_xy)
        axes_layout.addWidget(self.chk_invert_x)
        axes_layout.addWidget(self.chk_invert_y)
        form.addRow("Achsen:", axes_layout)

        e_layout.addLayout(form)

        # Test / Probe button & status
        test_group = QGroupBox("Verbindungstest")
        t_layout = QVBoxLayout(test_group)
        self.btn_test = QPushButton("Plotter prüfen (Inquiry)")
        self.btn_test.setIcon(get_icon("search"))
        self.btn_test.clicked.connect(self._on_test_device)
        t_layout.addWidget(self.btn_test)

        self.lbl_test_result = QLabel("Noch nicht getestet")
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setStyleSheet("padding: 4px; background: #f3f4f6; border-radius: 4px; font-size: 11px;")
        t_layout.addWidget(self.lbl_test_result)
        e_layout.addWidget(test_group)

        # Save changes button
        self.btn_save_item = QPushButton("Speichern")
        self.btn_save_item.setIcon(get_icon("save", size=16))
        self.btn_save_item.setToolTip("Geräteeinstellungen speichern")
        self.btn_save_item.clicked.connect(self._on_save_current_device)
        e_layout.addWidget(self.btn_save_item)
        e_layout.addStretch()

        content_layout.addWidget(self.grp_editor, 2)
        main_layout.addLayout(content_layout)

        # Bottom buttons (Close) at the bottom right
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.accept)
        main_layout.addWidget(buttons)

    def _refresh_ports(self):
        cur_text = self.combo_port.currentText()
        self.combo_port.clear()
        ports = list_serial_ports()
        for p in ports:
            self.combo_port.addItem(p)
        if not ports:
            self.combo_port.addItem("/dev/ttyUSB0")
            self.combo_port.addItem("tcp://127.0.0.1:9999")
        if cur_text:
            self.combo_port.setCurrentText(cur_text)

    def _load_devices_list(self, select_id: Optional[str] = None):
        self.list_devices.clear()
        self._refresh_ports()
        target_row = 0
        for i, dev in enumerate(self.manager.devices):
            item = QListWidgetItem(dev.name)
            item.setData(Qt.UserRole, dev.id)
            if dev.id == self.manager.active_device_id:
                item.setText(f"{dev.name} (Aktiv)")
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            self.list_devices.addItem(item)
            if select_id is not None and dev.id == select_id:
                target_row = i

        if self.list_devices.count() > 0:
            self.list_devices.setCurrentRow(target_row)

    def _on_device_selected(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        if not current:
            self.grp_editor.setEnabled(False)
            return

        self.grp_editor.setEnabled(True)
        dev_id = current.data(Qt.UserRole)
        for d in self.manager.devices:
            if d.id == dev_id:
                self._current_device = copy.deepcopy(d)
                self._populate_fields(d)
                break

    def _populate_fields(self, dev: ConfiguredDevice):
        self.txt_name.setText(dev.name)
        idx_model = self.combo_model.findData(dev.model_id)
        if idx_model >= 0:
            self.combo_model.setCurrentIndex(idx_model)
        self.combo_port.setCurrentText(dev.port)
        self.combo_baud.setCurrentText(str(dev.baudrate))
        idx_margin = self.combo_margins.findData(dev.margin_profile)
        if idx_margin >= 0:
            self.combo_margins.setCurrentIndex(idx_margin)
        idx_rot = self.combo_rotation.findData(dev.rotation)
        if idx_rot >= 0:
            self.combo_rotation.setCurrentIndex(idx_rot)
        self.chk_swap_xy.setChecked(dev.swap_xy)
        self.chk_invert_x.setChecked(dev.invert_x)
        self.chk_invert_y.setChecked(dev.invert_y)
        self.lbl_test_result.setText("Noch nicht getestet")

    def _on_add_device(self):
        new_id = f"device_{uuid.uuid4().hex[:6]}"
        new_dev = ConfiguredDevice(
            id=new_id,
            name="Neuer Plotter",
            model_id="mutoh_xp500",
            port=self.combo_port.currentText() or "/dev/ttyUSB0",
            baudrate=19200,
            margin_profile="exp",
        )
        self.manager.add_device(new_dev)
        self._load_devices_list(select_id=new_id)

    def _on_delete_device(self):
        if not self._current_device:
            return
        if len(self.manager.devices) <= 1:
            QMessageBox.warning(self, "Löschen nicht möglich", "Mindestens ein Gerät muss eingerichtet bleiben.")
            return

        reply = QMessageBox.question(
            self,
            "Gerät löschen",
            f"Möchtest du das Gerät '{self._current_device.name}' wirklich löschen?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.manager.delete_device(self._current_device.id)
            self._load_devices_list()

    def _on_save_current_device(self):
        if not self._current_device:
            return

        self._current_device.name = self.txt_name.text().strip() or "Plotter"
        self._current_device.model_id = self.combo_model.currentData()
        self._current_device.port = self.combo_port.currentText().strip()
        self._current_device.baudrate = int(self.combo_baud.currentText())
        self._current_device.margin_profile = self.combo_margins.currentData()
        self._current_device.rotation = int(self.combo_rotation.currentData())
        self._current_device.swap_xy = self.chk_swap_xy.isChecked()
        self._current_device.invert_x = self.chk_invert_x.isChecked()
        self._current_device.invert_y = self.chk_invert_y.isChecked()

        saved_id = self._current_device.id
        self.manager.update_device(self._current_device)
        self._load_devices_list(select_id=saved_id)
        self.btn_save_item.setText("✓ Gespeichert")
        QTimer.singleShot(1500, lambda: self.btn_save_item.setText("Speichern"))

    def _on_test_device(self):
        port = self.combo_port.currentText().strip()
        if not port:
            self.lbl_test_result.setText("Keine Schnittstelle ausgewählt")
            return
        baudrate = int(self.combo_baud.currentText())
        self.btn_test.setEnabled(False)
        self.lbl_test_result.setText(f"Prüfe {port}...")
        self.lbl_test_result.setStyleSheet("padding: 4px; background: #fff9c4; color: #f57f17; border-radius: 4px; font-size: 11px;")
        self.lbl_test_result.repaint()

        res = probe_plotter(port, baudrate=baudrate, timeout=0.6)
        self.btn_test.setEnabled(True)

        if res.success:
            dim_str = (
                f"{res.hard_clip_mm[0]:.0f} × {res.hard_clip_mm[1]:.0f} mm ({res.detected_format})"
                if res.hard_clip_mm
                else "Kein Bogen gemessen"
            )
            pin_info = " • CTS: Bereit" if res.cts else " • CTS: Low"
            self.lbl_test_result.setStyleSheet("padding: 4px; background: #e8f5e9; color: #2e7d32; border-radius: 4px; font-size: 11px;")
            self.lbl_test_result.setText(
                f"✓ <b>Erfolgreich!</b><br/>"
                f"Modell: {res.model or 'Unbekannt'}<br/>"
                f"Auflösung: {res.units_per_mm:.0f} U/mm{pin_info}<br/>"
                f"Bogen: {dim_str}"
            )
        else:
            self.lbl_test_result.setStyleSheet("padding: 4px; background: #ffebee; color: #c62828; border-radius: 4px; font-size: 11px;")
            self.lbl_test_result.setText(f"Fehlgeschlagen: {res.error_message or 'Keine Antwort vom Plotter (Timeout)'}")
