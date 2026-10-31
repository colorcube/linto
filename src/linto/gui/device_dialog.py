"""Dialog for managing plotter devices, connections, and hardware testing."""

from __future__ import annotations

import copy
import threading
import uuid
import weakref
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QComboBox, QCheckBox,
    QPushButton, QListWidget, QListWidgetItem, QGroupBox, QMessageBox,
    QDialogButtonBox
)

from ..device.manager import DeviceManager, ConfiguredDevice
from ..device.profile import list_available_profiles, load_profile, get_default_profile
from ..device.probe import list_serial_ports, probe_plotter
from .i18n import localize

AXIS_CORRECTION_TIP = (
    "Additional correction on top of the device profile's built-in axis mapping.\n"
    "Leave off normally; only use it if an orientation test plot comes out rotated or mirrored."
)
from .icons import get_icon


class DeviceSettingsDialog(QDialog):
    """Configuration dialog for plotter devices."""
    _probe_finished = Signal(object)

    def __init__(self, device_manager: DeviceManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Configure Plotter Devices"))
        self.setMinimumSize(680, 560)
        self.manager = device_manager
        self._current_device: Optional[ConfiguredDevice] = None
        self._probe_thread: Optional[threading.Thread] = None
        self._probe_lock = threading.Lock()
        self._closed_event = threading.Event()
        self._probe_finished.connect(self._handle_test_result)

        self._init_ui()
        self._load_devices_list()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Content horizontal layout: left (device list) + right (editor)
        content_layout = QHBoxLayout()

        # Left column: Device list & actions
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel(self.tr("<b>Configured Devices:</b>")))

        self.list_devices = QListWidget()
        self.list_devices.currentItemChanged.connect(self._on_device_selected)
        left_layout.addWidget(self.list_devices)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton(self.tr("Add"))
        self.btn_add.setIcon(get_icon("plus"))
        self.btn_add.clicked.connect(self._on_add_device)

        self.btn_delete = QPushButton(self.tr("Delete"))
        self.btn_delete.setIcon(get_icon("delete"))
        self.btn_delete.clicked.connect(self._on_delete_device)

        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_delete)
        left_layout.addLayout(btn_row)

        content_layout.addLayout(left_layout, 1)

        # Right column: Editor fields
        self.grp_editor = QGroupBox(self.tr("Device Settings"))
        e_layout = QVBoxLayout(self.grp_editor)

        form = QFormLayout()

        self.txt_name = QLineEdit()
        form.addRow(self.tr("Name:"), self.txt_name)

        self.combo_model = QComboBox()
        avail_profiles = list_available_profiles()
        for p in avail_profiles:
            self.combo_model.addItem(f"{p.name} ({p.manufacturer})", p.model_id)
        if not avail_profiles:
            self.combo_model.addItem("Mutoh XP-500", "mutoh_xp500")
        self.combo_model.currentIndexChanged.connect(self._on_model_profile_changed)
        form.addRow(self.tr("Model Profile:"), self.combo_model)

        port_row = QHBoxLayout()
        self.combo_port = QComboBox()
        self.combo_port.setEditable(True)
        self.combo_port.setToolTip(self.tr("Serial port (e.g. /dev/ttyUSB0) or TCP (tcp://127.0.0.1:9999)"))
        self.btn_refresh_ports = QPushButton()
        self.btn_refresh_ports.setIcon(get_icon("refresh"))
        self.btn_refresh_ports.setToolTip(self.tr("Refresh ports"))
        self.btn_refresh_ports.setFixedWidth(32)
        self.btn_refresh_ports.clicked.connect(self._refresh_ports)

        port_row.addWidget(self.combo_port)
        port_row.addWidget(self.btn_refresh_ports)
        form.addRow(self.tr("Port / Address:"), port_row)

        self.combo_baud = QComboBox()
        for b in [300, 600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
            self.combo_baud.addItem(str(b), b)
        self.combo_baud.setEditable(True)
        self.combo_baud.setCurrentText("19200")
        form.addRow(self.tr("Baud Rate:"), self.combo_baud)

        framing_row = QHBoxLayout()
        self.combo_bytesize = QComboBox()
        self.combo_bytesize.addItem(self.tr("8 Data Bits"), 8)
        self.combo_bytesize.addItem(self.tr("7 Data Bits"), 7)
        self.combo_bytesize.setToolTip(self.tr("Serial data bits (default from device profile, e.g. 8 or 7)"))

        self.combo_parity = QComboBox()
        self.combo_parity.addItem(self.tr("None (N)"), "N")
        self.combo_parity.addItem(self.tr("Even (E)"), "E")
        self.combo_parity.addItem(self.tr("Odd (O)"), "O")
        self.combo_parity.setToolTip(self.tr("Serial parity check (None, Even, Odd)"))

        self.combo_stopbits = QComboBox()
        self.combo_stopbits.addItem(self.tr("1 Stop Bit"), 1)
        self.combo_stopbits.addItem(self.tr("2 Stop Bits"), 2)
        self.combo_stopbits.setToolTip(self.tr("Serial stop bits (1 or 2)"))

        framing_row.addWidget(self.combo_bytesize)
        framing_row.addWidget(self.combo_parity)
        framing_row.addWidget(self.combo_stopbits)
        form.addRow(self.tr("Data Format:"), framing_row)

        self.combo_flow = QComboBox()
        self.combo_flow.addItem(self.tr("Hardware (RTS / CTS)"), "rtscts")
        self.combo_flow.addItem(self.tr("Software (XON / XOFF)"), "xonxoff")
        self.combo_flow.addItem(self.tr("None"), "none")
        self.combo_flow.setToolTip(
            self.tr(
                "Flow control (Handshake):\n"
                "• RTS/CTS: Standard for 7/8-wire RS-232 cables (Mutoh DTR pin 20 wired to PC CTS)\n"
                "• XON/XOFF: Software handshake (3-wire cables & TCP simulator)\n"
                "• None: No handshake"
            )
        )
        form.addRow(self.tr("Flow Control:"), self.combo_flow)

        from ..device.profile import get_margin_profile_items
        self.combo_margins = QComboBox()
        for label, key in get_margin_profile_items():
            self.combo_margins.addItem(label, key)
        form.addRow(self.tr("Margin Profile:"), self.combo_margins)

        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem(self.tr("0° (no correction)"), 0)
        self.combo_rotation.addItem("90°", 90)
        self.combo_rotation.addItem("180°", 180)
        self.combo_rotation.addItem("270°", 270)
        self.combo_rotation.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        form.addRow(self.tr("Rotation correction:"), self.combo_rotation)

        axes_layout = QHBoxLayout()
        self.chk_swap_xy = QCheckBox(self.tr("Swap X↔Y"))
        self.chk_invert_x = QCheckBox(self.tr("Mirror X"))
        self.chk_invert_y = QCheckBox(self.tr("Mirror Y"))
        axes_layout.addWidget(self.chk_swap_xy)
        axes_layout.addWidget(self.chk_invert_x)
        axes_layout.addWidget(self.chk_invert_y)
        for chk in (self.chk_swap_xy, self.chk_invert_x, self.chk_invert_y):
            chk.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        form.addRow(self.tr("Axis correction:"), axes_layout)

        e_layout.addLayout(form)

        # Test / Probe button & status
        test_group = QGroupBox(self.tr("Connection Test"))
        t_layout = QVBoxLayout(test_group)
        self.btn_test = QPushButton(self.tr("Probe Plotter (Inquiry)"))
        self.btn_test.setIcon(get_icon("search"))
        self.btn_test.clicked.connect(self._on_test_device)
        t_layout.addWidget(self.btn_test)

        self.lbl_test_result = QLabel(self.tr("Not tested yet"))
        self.lbl_test_result.setWordWrap(True)
        self.lbl_test_result.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.lbl_test_result.setMinimumHeight(88)
        self.lbl_test_result.setStyleSheet("padding: 6px 8px; background: #f3f4f6; border-radius: 4px; font-size: 11px;")
        t_layout.addWidget(self.lbl_test_result)
        e_layout.addWidget(test_group)

        # Save changes button
        self.btn_save_item = QPushButton(self.tr("Save"))
        self.btn_save_item.setIcon(get_icon("save", size=16))
        self.btn_save_item.setToolTip(self.tr("Save device settings"))
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
                item.setText(f"{dev.name} (" + self.tr("Active") + ")")
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
        self.combo_model.blockSignals(True)
        idx_model = self.combo_model.findData(dev.model_id)
        if idx_model >= 0:
            self.combo_model.setCurrentIndex(idx_model)
        self.combo_model.blockSignals(False)
        self.combo_port.setCurrentText(dev.port)
        self.combo_baud.setCurrentText(str(dev.baudrate))
        idx_bs = self.combo_bytesize.findData(int(getattr(dev, "bytesize", 8) or 8))
        self.combo_bytesize.setCurrentIndex(idx_bs if idx_bs >= 0 else 0)
        idx_par = self.combo_parity.findData(str(getattr(dev, "parity", "N") or "N").upper())
        self.combo_parity.setCurrentIndex(idx_par if idx_par >= 0 else 0)
        idx_sb = self.combo_stopbits.findData(int(getattr(dev, "stopbits", 1) or 1))
        self.combo_stopbits.setCurrentIndex(idx_sb if idx_sb >= 0 else 0)
        flow = getattr(dev, "flow_control", "rtscts")
        idx_flow = self.combo_flow.findData(flow)
        if idx_flow >= 0:
            self.combo_flow.setCurrentIndex(idx_flow)
        else:
            self.combo_flow.setCurrentIndex(0)
        idx_margin = self.combo_margins.findData(dev.margin_profile)
        if idx_margin >= 0:
            self.combo_margins.setCurrentIndex(idx_margin)
        idx_rot = self.combo_rotation.findData(dev.rotation)
        if idx_rot >= 0:
            self.combo_rotation.setCurrentIndex(idx_rot)
        self.chk_swap_xy.setChecked(dev.swap_xy)
        self.chk_invert_x.setChecked(dev.invert_x)
        self.chk_invert_y.setChecked(dev.invert_y)
        self.lbl_test_result.setText(self.tr("Not tested yet"))
        self.lbl_test_result.setStyleSheet("padding: 6px 8px; background: #f3f4f6; border-radius: 4px; font-size: 11px;")

    def _on_model_profile_changed(self):
        """Apply default serial connection parameters from the newly selected DeviceProfile."""
        model_id = self.combo_model.currentData() or "mutoh_xp500"
        try:
            prof = load_profile(model_id)
        except Exception:
            return
        self.combo_baud.setCurrentText(str(prof.connection.baudrate))
        idx_bs = self.combo_bytesize.findData(int(prof.connection.bytesize))
        if idx_bs >= 0:
            self.combo_bytesize.setCurrentIndex(idx_bs)
        idx_par = self.combo_parity.findData(str(prof.connection.parity).upper())
        if idx_par >= 0:
            self.combo_parity.setCurrentIndex(idx_par)
        idx_sb = self.combo_stopbits.findData(int(prof.connection.stopbits))
        if idx_sb >= 0:
            self.combo_stopbits.setCurrentIndex(idx_sb)
        idx_flow = self.combo_flow.findData(prof.connection.flow_control)
        if idx_flow >= 0:
            self.combo_flow.setCurrentIndex(idx_flow)
        idx_margin = self.combo_margins.findData(prof.default_margin_profile)
        if idx_margin >= 0:
            self.combo_margins.setCurrentIndex(idx_margin)

    def _on_add_device(self):
        new_id = f"device_{uuid.uuid4().hex[:6]}"
        model_id = self.combo_model.currentData() or "mutoh_xp500"
        try:
            prof = load_profile(model_id)
        except Exception:
            prof = get_default_profile()
        port = self.combo_port.currentText() or prof.connection.default_port
        default_flow = (
            "xonxoff"
            if (port.startswith("tcp://") or "virtual_plotter" in port)
            else (prof.connection.flow_control if prof.connection.flow_control != "dsrdtr" else "rtscts")
        )
        new_dev = ConfiguredDevice(
            id=new_id,
            name=self.tr("New Plotter"),
            model_id=model_id,
            port=port,
            baudrate=int(prof.connection.baudrate),
            bytesize=int(prof.connection.bytesize),
            parity=str(prof.connection.parity).upper(),
            stopbits=int(prof.connection.stopbits),
            flow_control=default_flow,
            margin_profile=prof.default_margin_profile or "exp",
        )
        self.manager.add_device(new_dev)
        self._load_devices_list(select_id=new_id)

    def _on_delete_device(self):
        if not self._current_device:
            return
        if len(self.manager.devices) <= 1:
            QMessageBox.warning(self, self.tr("Cannot Delete"), self.tr("At least one device must remain configured."))
            return

        del_msg = self.tr("Do you really want to delete device '%1'?").replace("%1", self._current_device.name)
        reply = QMessageBox.question(
            self,
            self.tr("Delete Device"),
            del_msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.manager.delete_device(self._current_device.id)
            self._load_devices_list()

    def _on_save_current_device(self):
        if not self._current_device:
            return

        new_model_id = self.combo_model.currentData()
        if new_model_id and new_model_id != self._current_device.model_id:
            self._current_device.send_pen_force = None
        self._current_device.name = self.txt_name.text().strip() or "Plotter"
        self._current_device.model_id = new_model_id
        self._current_device.port = self.combo_port.currentText().strip()
        try:
            self._current_device.baudrate = int(self.combo_baud.currentText().strip())
        except ValueError:
            self._current_device.baudrate = 19200
        self._current_device.bytesize = int(self.combo_bytesize.currentData() or 8)
        self._current_device.parity = str(self.combo_parity.currentData() or "N").upper()
        self._current_device.stopbits = int(self.combo_stopbits.currentData() or 1)
        self._current_device.flow_control = self.combo_flow.currentData() or "rtscts"
        self._current_device.margin_profile = self.combo_margins.currentData()
        self._current_device.rotation = int(self.combo_rotation.currentData())
        self._current_device.swap_xy = self.chk_swap_xy.isChecked()
        self._current_device.invert_x = self.chk_invert_x.isChecked()
        self._current_device.invert_y = self.chk_invert_y.isChecked()

        saved_id = self._current_device.id
        self.manager.update_device(self._current_device)
        self._load_devices_list(select_id=saved_id)
        self.btn_save_item.setText(self.tr("✓ Saved"))
        weak_self = weakref.ref(self)

        def _reset_save_label():
            dlg = weak_self()
            if dlg is not None and not dlg._closed_event.is_set():
                dlg.btn_save_item.setText(dlg.tr("Save"))

        QTimer.singleShot(1500, _reset_save_label)

    def _on_test_device(self):
        if self._probe_thread is not None and self._probe_thread.is_alive():
            return
        port = self.combo_port.currentText().strip()
        if not port:
            self.lbl_test_result.setText(self.tr("No port selected"))
            return
        try:
            baudrate = int(self.combo_baud.currentText().strip())
        except ValueError:
            baudrate = 19200
        bytesize = int(self.combo_bytesize.currentData() or 8)
        parity = str(self.combo_parity.currentData() or "N").upper()
        stopbits = int(self.combo_stopbits.currentData() or 1)
        try:
            prof = load_profile(self.combo_model.currentData() or "mutoh_xp500")
        except Exception:
            prof = self._current_device.get_profile() if self._current_device else get_default_profile()
        axes_swapped = prof.axes_swapped
        self.btn_test.setEnabled(False)
        self.lbl_test_result.setText(self.tr("Probing %1 at %2 baud...").replace("%1", port).replace("%2", str(baudrate)))
        self.lbl_test_result.setStyleSheet("padding: 6px 8px; background: #fff9c4; color: #f57f17; border-radius: 4px; font-size: 11px;")

        weak_self = weakref.ref(self)
        lock = self._probe_lock
        closed_event = self._closed_event

        def _worker():
            res = probe_plotter(
                port,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                axes_swapped=axes_swapped,
            )
            with lock:
                if closed_event.is_set():
                    return
                dlg = weak_self()
                if dlg is not None:
                    try:
                        dlg._probe_finished.emit(res)
                    except RuntimeError:
                        pass
                    finally:
                        del dlg

        self._probe_thread = threading.Thread(target=_worker, daemon=True, name="DeviceSettingsProbeThread")
        self._probe_thread.start()

    def _mark_closed(self):
        with self._probe_lock:
            self._closed_event.set()
            try:
                self._probe_finished.disconnect(self._handle_test_result)
            except (RuntimeError, TypeError):
                pass

    def done(self, result: int):
        self._mark_closed()
        super().done(result)

    def closeEvent(self, event):
        self._mark_closed()
        super().closeEvent(event)

    def _handle_test_result(self, res):
        if self._closed_event.is_set():
            return
        self.btn_test.setEnabled(True)

        if res.success:
            if res.units_per_mm and res.units_per_mm > 0 and self._current_device:
                self._current_device.probed_units_per_mm = res.units_per_mm
            dim_str = (
                f"{res.hard_clip_mm[0]:.0f} × {res.hard_clip_mm[1]:.0f} mm ({res.detected_format})"
                if res.hard_clip_mm
                else self.tr("No sheet measured")
            )
            pin_parts = []
            if res.cts is not None:
                pin_parts.append(f"CTS: {self.tr('High (Ready)') if res.cts else 'Low'}")
            if res.dsr is not None:
                pin_parts.append(f"DSR: {self.tr('High (Ready)') if res.dsr else 'Low'}")
            pin_info = f"<br>Pins: {' • '.join(pin_parts)}" if pin_parts else ""
            self.lbl_test_result.setStyleSheet("padding: 6px 8px; background: #e8f5e9; color: #2e7d32; border-radius: 4px; font-size: 11px;")
            self.lbl_test_result.setText(
                self.tr("✓ <b>Success!</b><br/>Model: %1<br/>Resolution: %2 U/mm%3<br/>Sheet: %4")
                .replace("%1", str(res.model or self.tr("Unknown")))
                .replace("%2", f"{res.units_per_mm:.0f}")
                .replace("%3", pin_info)
                .replace("%4", dim_str)
            )
        else:
            pin_parts = []
            if res.cts is not None:
                pin_parts.append(f"CTS: {self.tr('High (Ready)') if res.cts else 'Low'}")
            if res.dsr is not None:
                pin_parts.append(f"DSR: {self.tr('High (Ready)') if res.dsr else 'Low'}")
            pin_hint = f"<br>Pins: {' • '.join(pin_parts)}" if pin_parts else ""
            self.lbl_test_result.setStyleSheet("padding: 6px 8px; background: #ffebee; color: #c62828; border-radius: 4px; font-size: 11px;")
            err_msg = localize(res.error_message) if res.error_message else self.tr("No response from plotter (timeout)")
            self.lbl_test_result.setText(
                self.tr("Failed: %1%2").replace("%1", err_msg).replace("%2", pin_hint)
            )
