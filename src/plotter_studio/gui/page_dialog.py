"""Page and paper setup dialog."""

from __future__ import annotations
import threading
from typing import Optional, Dict, Any
from PySide6.QtCore import Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QLabel, QMessageBox, QDialogButtonBox
)
from ..core.document import Document, PAPER_PRESETS
from ..device import probe_plotter, DeviceManager, ConfiguredDevice
from .commands import PageConfigCommand
from .icons import get_icon


class PageSetupDialog(QDialog):
    """
    Modal dialog for configuring:
    - Paper format preset (DIN A4..A0, Letter, Custom)
    - Sheet orientation (Landscape, Portrait)
    - Custom dimensions (Width x Height mm)
    - Roller plotter feed edge (Top, Bottom, Left, Right)
    - Margins (X, Y mm)
    - Plotter hardware bounds query ('Papiergröße vom Plotter abfragen')
    
    Does NOT contain duplicate device selection — uses active device globally.
    """
    page_changed = Signal()
    _probe_finished = Signal(str, object)

    def __init__(self, doc: Document, device_manager: Optional[DeviceManager] = None, undo_stack: Optional[QUndoStack] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Page Setup & Paper Format"))
        self.setWindowIcon(get_icon("page"))
        self.setMinimumWidth(440)

        self.doc = doc
        self.device_manager = device_manager
        self.undo_stack = undo_stack
        self._probe_thread: Optional[threading.Thread] = None
        self._probe_finished.connect(self._handle_probe_result)

        # Store initial state for canceling
        self._initial_state = {
            "preset": self.doc.page.preset,
            "width_mm": self.doc.page.width_mm,
            "height_mm": self.doc.page.height_mm,
            "orientation": self.doc.page.orientation,
            "margin_left_mm": self.doc.page.margin_left_mm,
            "margin_right_mm": self.doc.page.margin_right_mm,
            "margin_top_mm": self.doc.page.margin_top_mm,
            "margin_bottom_mm": self.doc.page.margin_bottom_mm,
            "device_profile": self.doc.page.device_profile,
            "feed_edge": self.doc.page.feed_edge,
            "margin_profile": self.doc.page.margin_profile,
        }

        self._active_dev: Optional[ConfiguredDevice] = (
            self.device_manager.get_active_device() if self.device_manager else None
        )

        self._init_ui()
        self._sync_from_page()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        # Active Device Info Header
        dev_name = self._active_dev.name if self._active_dev else self.tr("Default Plotter")
        dev_port = self._active_dev.port if self._active_dev else "/dev/ttyUSB0"
        info_text = self.tr("Active device: <b>%1</b> (%2)").replace("%1", dev_name).replace("%2", dev_port)
        self.lbl_device_info = QLabel(info_text)
        self.lbl_device_info.setStyleSheet("""
            padding: 8px 10px;
            background-color: #f3f4f6;
            border: 1px solid #e5e7eb;
            border-radius: 6px;
            color: #374151;
            font-size: 12px;
        """)
        main_layout.addWidget(self.lbl_device_info)

        # --- Group: Paper Format & Orientation ---
        grp_format = QGroupBox(self.tr("Paper Format && Orientation"))
        f_layout = QFormLayout(grp_format)
        f_layout.setSpacing(8)

        # Presets
        self.combo_preset = QComboBox()
        for p_name in PAPER_PRESETS.keys():
            self.combo_preset.addItem(f"DIN {p_name}" if p_name.startswith("A") else p_name, p_name)
        self.combo_preset.addItem(self.tr("Custom"), "Custom")
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        f_layout.addRow(self.tr("Format:"), self.combo_preset)

        # Orientation
        self.combo_orient = QComboBox()
        self.combo_orient.addItem(self.tr("Landscape"), "landscape")
        self.combo_orient.addItem(self.tr("Portrait"), "portrait")
        self.combo_orient.currentIndexChanged.connect(self._on_orient_changed)
        f_layout.addRow(self.tr("Orientation:"), self.combo_orient)

        # Dimensions
        dim_layout = QHBoxLayout()
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(20.0, 5000.0)
        self.spin_width.setDecimals(1)
        self.spin_width.setSuffix(" mm")
        self.spin_width.setKeyboardTracking(False)
        self.spin_width.setValue(self.doc.page.width_mm)
        self.spin_width.valueChanged.connect(self._on_custom_dim_changed)

        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(20.0, 5000.0)
        self.spin_height.setDecimals(1)
        self.spin_height.setSuffix(" mm")
        self.spin_height.setKeyboardTracking(False)
        self.spin_height.setValue(self.doc.page.height_mm)
        self.spin_height.valueChanged.connect(self._on_custom_dim_changed)

        dim_layout.addWidget(self.spin_width)
        dim_layout.addWidget(QLabel("×"))
        dim_layout.addWidget(self.spin_height)
        f_layout.addRow(self.tr("Dimensions:"), dim_layout)

        main_layout.addWidget(grp_format)

        # --- Group: Margins & Feed ---
        grp_margins = QGroupBox(self.tr("Margins && Feed Edge"))
        m_layout = QFormLayout(grp_margins)
        m_layout.setSpacing(8)

        # Feed edge (only relevant for roller plotters like mutoh_xp500)
        self.combo_feed = QComboBox()
        self.combo_feed.addItem(self.tr("Feed: Top (Default)"), "top")
        self.combo_feed.addItem(self.tr("Feed: Bottom"), "bottom")
        self.combo_feed.addItem(self.tr("Feed: Left"), "left")
        self.combo_feed.addItem(self.tr("Feed: Right"), "right")
        self.combo_feed.currentIndexChanged.connect(self._on_feed_edge_changed)
        m_layout.addRow(self.tr("Feed edge:"), self.combo_feed)

        # Margins (4 individual edges to preserve asymmetric margins)
        margin_h_layout = QHBoxLayout()
        self.spin_margin_left = QDoubleSpinBox()
        self.spin_margin_left.setRange(0.0, 100.0)
        self.spin_margin_left.setDecimals(1)
        self.spin_margin_left.setSuffix(" mm")
        self.spin_margin_left.setKeyboardTracking(False)
        self.spin_margin_left.setValue(self.doc.page.margin_left_mm)
        self.spin_margin_left.valueChanged.connect(self._on_margins_changed)

        self.spin_margin_right = QDoubleSpinBox()
        self.spin_margin_right.setRange(0.0, 100.0)
        self.spin_margin_right.setDecimals(1)
        self.spin_margin_right.setSuffix(" mm")
        self.spin_margin_right.setKeyboardTracking(False)
        self.spin_margin_right.setValue(self.doc.page.margin_right_mm)
        self.spin_margin_right.valueChanged.connect(self._on_margins_changed)

        margin_h_layout.addWidget(QLabel(self.tr("Left:")))
        margin_h_layout.addWidget(self.spin_margin_left)
        margin_h_layout.addWidget(QLabel(self.tr("Right:")))
        margin_h_layout.addWidget(self.spin_margin_right)
        m_layout.addRow(self.tr("Margins X:"), margin_h_layout)

        margin_v_layout = QHBoxLayout()
        self.spin_margin_top = QDoubleSpinBox()
        self.spin_margin_top.setRange(0.0, 100.0)
        self.spin_margin_top.setDecimals(1)
        self.spin_margin_top.setSuffix(" mm")
        self.spin_margin_top.setKeyboardTracking(False)
        self.spin_margin_top.setValue(self.doc.page.margin_top_mm)
        self.spin_margin_top.valueChanged.connect(self._on_margins_changed)

        self.spin_margin_bottom = QDoubleSpinBox()
        self.spin_margin_bottom.setRange(0.0, 100.0)
        self.spin_margin_bottom.setDecimals(1)
        self.spin_margin_bottom.setSuffix(" mm")
        self.spin_margin_bottom.setKeyboardTracking(False)
        self.spin_margin_bottom.setValue(self.doc.page.margin_bottom_mm)
        self.spin_margin_bottom.valueChanged.connect(self._on_margins_changed)

        margin_v_layout.addWidget(QLabel(self.tr("Top:")))
        margin_v_layout.addWidget(self.spin_margin_top)
        margin_v_layout.addWidget(QLabel(self.tr("Bottom:")))
        margin_v_layout.addWidget(self.spin_margin_bottom)
        m_layout.addRow(self.tr("Margins Y:"), margin_v_layout)

        # Backwards-compatible aliases
        self.spin_margin_x = self.spin_margin_left
        self.spin_margin_y = self.spin_margin_top

        main_layout.addWidget(grp_margins)

        # Hardware Probe Button
        self.btn_fetch_device = QPushButton(self.tr("Query paper size from plotter"))
        self.btn_fetch_device.setIcon(get_icon("search", size=16))
        self.btn_fetch_device.setToolTip(self.tr("Queries paper and pinch roller bounds via OH; from active plotter"))
        self.btn_fetch_device.clicked.connect(self._on_fetch_device_size)
        main_layout.addWidget(self.btn_fetch_device)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _sync_from_page(self):
        self.spin_width.blockSignals(True)
        self.spin_height.blockSignals(True)
        self.spin_margin_left.blockSignals(True)
        self.spin_margin_right.blockSignals(True)
        self.spin_margin_top.blockSignals(True)
        self.spin_margin_bottom.blockSignals(True)
        self.combo_preset.blockSignals(True)
        self.combo_orient.blockSignals(True)
        self.combo_feed.blockSignals(True)

        try:
            self.spin_width.setValue(self.doc.page.width_mm)
            self.spin_height.setValue(self.doc.page.height_mm)
            self.spin_margin_left.setValue(self.doc.page.margin_left_mm)
            self.spin_margin_right.setValue(self.doc.page.margin_right_mm)
            self.spin_margin_top.setValue(self.doc.page.margin_top_mm)
            self.spin_margin_bottom.setValue(self.doc.page.margin_bottom_mm)

            preset_idx = self.combo_preset.findData(self.doc.page.preset)
            if preset_idx >= 0:
                self.combo_preset.setCurrentIndex(preset_idx)

            orient_idx = self.combo_orient.findData(self.doc.page.orientation)
            if orient_idx >= 0:
                self.combo_orient.setCurrentIndex(orient_idx)

            feed_idx = self.combo_feed.findData(self.doc.page.feed_edge)
            if feed_idx >= 0:
                self.combo_feed.setCurrentIndex(feed_idx)

            is_roller = self.doc.page.device_profile == "mutoh_xp500"
            self.combo_feed.setEnabled(is_roller)
        finally:
            self.spin_width.blockSignals(False)
            self.spin_height.blockSignals(False)
            self.spin_margin_left.blockSignals(False)
            self.spin_margin_right.blockSignals(False)
            self.spin_margin_top.blockSignals(False)
            self.spin_margin_bottom.blockSignals(False)
            self.combo_preset.blockSignals(False)
            self.combo_orient.blockSignals(False)
            self.combo_feed.blockSignals(False)

    def _on_preset_changed(self):
        preset = self.combo_preset.currentData()
        if preset != "Custom":
            self.doc.page.apply_preset(preset, self.combo_orient.currentData())
        self._sync_from_page()

    def _on_orient_changed(self):
        orient = self.combo_orient.currentData()
        preset = self.combo_preset.currentData()
        if preset != "Custom":
            self.doc.page.apply_preset(preset, orient)
        else:
            w, h = self.doc.page.width_mm, self.doc.page.height_mm
            if (orient == "landscape" and w < h) or (orient == "portrait" and w > h):
                self.doc.page.width_mm, self.doc.page.height_mm = h, w
        self._sync_from_page()

    def _on_feed_edge_changed(self):
        edge = self.combo_feed.currentData()
        self.doc.page.apply_device_profile(self.doc.page.device_profile, edge)
        self._sync_from_page()

    def _on_custom_dim_changed(self):
        self.combo_preset.blockSignals(True)
        self.combo_preset.setCurrentIndex(self.combo_preset.findData("Custom"))
        self.combo_preset.blockSignals(False)
        self.doc.page.set_custom_size(self.spin_width.value(), self.spin_height.value())

    def _on_margins_changed(self):
        new_l = self.spin_margin_left.value()
        new_r = self.spin_margin_right.value()
        new_t = self.spin_margin_top.value()
        new_b = self.spin_margin_bottom.value()
        if (
            abs(new_l - self.doc.page.margin_left_mm) < 1e-4
            and abs(new_r - self.doc.page.margin_right_mm) < 1e-4
            and abs(new_t - self.doc.page.margin_top_mm) < 1e-4
            and abs(new_b - self.doc.page.margin_bottom_mm) < 1e-4
        ):
            return
        self.doc.page.device_profile = "custom"
        self.doc.page.margin_left_mm = new_l
        self.doc.page.margin_right_mm = new_r
        self.doc.page.margin_top_mm = new_t
        self.doc.page.margin_bottom_mm = new_b
        self._sync_from_page()

    def _on_fetch_device_size(self):
        target = self._active_dev.port if self._active_dev else "/dev/ttyUSB0"
        baud = self._active_dev.baudrate if self._active_dev else 19200
        bytesize = 8
        parity = "N"
        stopbits = 1
        axes_swapped = True
        if self._active_dev:
            prof = self._active_dev.get_profile()
            bytesize = int(getattr(self._active_dev, "bytesize", None) or prof.connection.bytesize)
            parity = str(getattr(self._active_dev, "parity", None) or prof.connection.parity).upper()
            stopbits = int(getattr(self._active_dev, "stopbits", None) or prof.connection.stopbits)
            axes_swapped = prof.axes_swapped
        self.btn_fetch_device.setEnabled(False)
        self.btn_fetch_device.setText(self.tr("Querying '%1'...").replace("%1", target))

        def _worker():
            res = probe_plotter(
                target,
                baudrate=baud,
                timeout=0.6,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                axes_swapped=axes_swapped,
            )
            self._probe_finished.emit(target, res)

        self._probe_thread = threading.Thread(target=_worker, daemon=True, name="PageSetupProbeThread")
        self._probe_thread.start()

    def _handle_probe_result(self, target: str, res):
        self.btn_fetch_device.setEnabled(True)
        self.btn_fetch_device.setText(self.tr("Query paper size from plotter"))

        if res.success:
            if res.units_per_mm and res.units_per_mm > 0 and self._active_dev:
                self._active_dev.probed_units_per_mm = res.units_per_mm
            self.doc.page.apply_probe_result(res)
            self._sync_from_page()
            msg = (
                self.tr("Plotter at '%1' reports:\nModel: %2\nFormat: %3 (%4 × %5 mm)")
                .replace("%1", target)
                .replace("%2", str(res.model or ""))
                .replace("%3", str(res.detected_format or ""))
                .replace("%4", f"{self.doc.page.width_mm:.1f}")
                .replace("%5", f"{self.doc.page.height_mm:.1f}")
            )
            QMessageBox.information(
                self,
                self.tr("Paper Size Detected"),
                msg
            )
        else:
            err_detail = res.error_message or self.tr("No response from device")
            msg = self.tr("Could not query paper size from '%1':\n%2").replace("%1", target).replace("%2", err_detail)
            QMessageBox.warning(
                self,
                self.tr("Device Query Failed"),
                msg
            )

    def accept(self):
        new_state = {
            "preset": self.doc.page.preset,
            "width_mm": self.doc.page.width_mm,
            "height_mm": self.doc.page.height_mm,
            "orientation": self.doc.page.orientation,
            "margin_left_mm": self.doc.page.margin_left_mm,
            "margin_right_mm": self.doc.page.margin_right_mm,
            "margin_top_mm": self.doc.page.margin_top_mm,
            "margin_bottom_mm": self.doc.page.margin_bottom_mm,
            "device_profile": self.doc.page.device_profile,
            "feed_edge": self.doc.page.feed_edge,
            "margin_profile": self.doc.page.margin_profile,
        }
        # If changed and undo stack exists, push command
        if self.undo_stack and new_state != self._initial_state:
            # Revert page to initial state first, then push command so redo applies it
            self._apply_dict(self._initial_state)
            cmd = PageConfigCommand(
                self.doc.page, self._initial_state, new_state, self._on_undo_redo, text=self.tr("Change page setup")
            )
            self.undo_stack.push(cmd)
        else:
            self.page_changed.emit()

        super().accept()

    def reject(self):
        # Restore initial state
        self._apply_dict(self._initial_state)
        super().reject()

    def _apply_dict(self, state: Dict[str, Any]):
        p = self.doc.page
        p.preset = state.get("preset", p.preset)
        p.width_mm = state.get("width_mm", p.width_mm)
        p.height_mm = state.get("height_mm", p.height_mm)
        p.orientation = state.get("orientation", p.orientation)
        p.device_profile = state.get("device_profile", p.device_profile)
        p.feed_edge = state.get("feed_edge", p.feed_edge)
        p.margin_profile = state.get("margin_profile", p.margin_profile)
        p.margin_left_mm = state.get("margin_left_mm", p.margin_left_mm)
        p.margin_right_mm = state.get("margin_right_mm", p.margin_right_mm)
        p.margin_top_mm = state.get("margin_top_mm", p.margin_top_mm)
        p.margin_bottom_mm = state.get("margin_bottom_mm", p.margin_bottom_mm)

    def _on_undo_redo(self):
        self._sync_from_page()
        self.page_changed.emit()
