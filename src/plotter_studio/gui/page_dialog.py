"""Page and paper setup dialog."""

from __future__ import annotations
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QLabel, QMessageBox, QDialogButtonBox
)
from ..core.document import Document, PAPER_PRESETS, DEVICE_PROFILES
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

    def __init__(self, doc: Document, device_manager: Optional[DeviceManager] = None, undo_stack: Optional[QUndoStack] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seiteneinrichtung & Papierformat")
        self.setWindowIcon(get_icon("page"))
        self.setMinimumWidth(440)

        self.doc = doc
        self.device_manager = device_manager
        self.undo_stack = undo_stack

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
        dev_name = self._active_dev.name if self._active_dev else "Standard-Plotter"
        dev_port = self._active_dev.port if self._active_dev else "/dev/ttyUSB0"
        self.lbl_device_info = QLabel(f"Aktives Gerät: <b>{dev_name}</b> ({dev_port})")
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
        grp_format = QGroupBox("Papierformat && Ausrichtung")
        f_layout = QFormLayout(grp_format)
        f_layout.setSpacing(8)

        # Presets
        self.combo_preset = QComboBox()
        for p_name in PAPER_PRESETS.keys():
            self.combo_preset.addItem(f"DIN {p_name}" if p_name.startswith("A") else p_name, p_name)
        self.combo_preset.addItem("Benutzerdefiniert (Custom)", "Custom")
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        f_layout.addRow("Format:", self.combo_preset)

        # Orientation
        self.combo_orient = QComboBox()
        self.combo_orient.addItem("Querformat (Landscape)", "landscape")
        self.combo_orient.addItem("Hochformat (Portrait)", "portrait")
        self.combo_orient.currentIndexChanged.connect(self._on_orient_changed)
        f_layout.addRow("Ausrichtung:", self.combo_orient)

        # Dimensions
        dim_layout = QHBoxLayout()
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(20.0, 5000.0)
        self.spin_width.setDecimals(1)
        self.spin_width.setSuffix(" mm")
        self.spin_width.setValue(self.doc.page.width_mm)
        self.spin_width.valueChanged.connect(self._on_custom_dim_changed)

        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(20.0, 5000.0)
        self.spin_height.setDecimals(1)
        self.spin_height.setSuffix(" mm")
        self.spin_height.setValue(self.doc.page.height_mm)
        self.spin_height.valueChanged.connect(self._on_custom_dim_changed)

        dim_layout.addWidget(self.spin_width)
        dim_layout.addWidget(QLabel("×"))
        dim_layout.addWidget(self.spin_height)
        f_layout.addRow("Abmessungen:", dim_layout)

        main_layout.addWidget(grp_format)

        # --- Group: Ränder & Vorschub ---
        grp_margins = QGroupBox("Ränder && Vorschubkante")
        m_layout = QFormLayout(grp_margins)
        m_layout.setSpacing(8)

        # Feed edge (only relevant for roller plotters like mutoh_xp500)
        self.combo_feed = QComboBox()
        self.combo_feed.addItem("Vorschub: Oben (Standard)", "top")
        self.combo_feed.addItem("Vorschub: Unten", "bottom")
        self.combo_feed.addItem("Vorschub: Links", "left")
        self.combo_feed.addItem("Vorschub: Rechts", "right")
        self.combo_feed.currentIndexChanged.connect(self._on_feed_edge_changed)
        m_layout.addRow("Vorschubkante:", self.combo_feed)

        # Margins (4 individual edges to preserve asymmetric margins)
        margin_h_layout = QHBoxLayout()
        self.spin_margin_left = QDoubleSpinBox()
        self.spin_margin_left.setRange(0.0, 100.0)
        self.spin_margin_left.setDecimals(1)
        self.spin_margin_left.setSuffix(" mm")
        self.spin_margin_left.setValue(self.doc.page.margin_left_mm)
        self.spin_margin_left.valueChanged.connect(self._on_margins_changed)

        self.spin_margin_right = QDoubleSpinBox()
        self.spin_margin_right.setRange(0.0, 100.0)
        self.spin_margin_right.setDecimals(1)
        self.spin_margin_right.setSuffix(" mm")
        self.spin_margin_right.setValue(self.doc.page.margin_right_mm)
        self.spin_margin_right.valueChanged.connect(self._on_margins_changed)

        margin_h_layout.addWidget(QLabel("Links:"))
        margin_h_layout.addWidget(self.spin_margin_left)
        margin_h_layout.addWidget(QLabel("Rechts:"))
        margin_h_layout.addWidget(self.spin_margin_right)
        m_layout.addRow("Ränder X:", margin_h_layout)

        margin_v_layout = QHBoxLayout()
        self.spin_margin_top = QDoubleSpinBox()
        self.spin_margin_top.setRange(0.0, 100.0)
        self.spin_margin_top.setDecimals(1)
        self.spin_margin_top.setSuffix(" mm")
        self.spin_margin_top.setValue(self.doc.page.margin_top_mm)
        self.spin_margin_top.valueChanged.connect(self._on_margins_changed)

        self.spin_margin_bottom = QDoubleSpinBox()
        self.spin_margin_bottom.setRange(0.0, 100.0)
        self.spin_margin_bottom.setDecimals(1)
        self.spin_margin_bottom.setSuffix(" mm")
        self.spin_margin_bottom.setValue(self.doc.page.margin_bottom_mm)
        self.spin_margin_bottom.valueChanged.connect(self._on_margins_changed)

        margin_v_layout.addWidget(QLabel("Oben:"))
        margin_v_layout.addWidget(self.spin_margin_top)
        margin_v_layout.addWidget(QLabel("Unten:"))
        margin_v_layout.addWidget(self.spin_margin_bottom)
        m_layout.addRow("Ränder Y:", margin_v_layout)

        # Backwards-compatible aliases
        self.spin_margin_x = self.spin_margin_left
        self.spin_margin_y = self.spin_margin_top

        main_layout.addWidget(grp_margins)

        # Hardware Probe Button (unter beiden Boxen)
        self.btn_fetch_device = QPushButton("Papiergröße vom Plotter abfragen")
        self.btn_fetch_device.setIcon(get_icon("search", size=16))
        self.btn_fetch_device.setToolTip("Liest die Papier- und Andruckrollen-Grenzen via OH; vom aktiven Plotter aus")
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
        self.doc.page.device_profile = "custom"
        self.doc.page.margin_left_mm = self.spin_margin_left.value()
        self.doc.page.margin_right_mm = self.spin_margin_right.value()
        self.doc.page.margin_top_mm = self.spin_margin_top.value()
        self.doc.page.margin_bottom_mm = self.spin_margin_bottom.value()
        self._sync_from_page()

    def _on_fetch_device_size(self):
        target = self._active_dev.port if self._active_dev else "/dev/ttyUSB0"
        self.btn_fetch_device.setEnabled(False)
        self.btn_fetch_device.setText(f"Frage '{target}' ab...")
        self.btn_fetch_device.repaint()

        res = probe_plotter(target, timeout=0.6)
        self._handle_probe_result(target, res)

    def _handle_probe_result(self, target: str, res):
        self.btn_fetch_device.setEnabled(True)
        self.btn_fetch_device.setText("Papiergröße vom Plotter abfragen")

        if res.success:
            if res.detected_format and res.detected_format in PAPER_PRESETS:
                self.combo_preset.setCurrentIndex(self.combo_preset.findData(res.detected_format))
                self.combo_orient.setCurrentIndex(self.combo_orient.findData("landscape"))
                self.doc.page.apply_preset(res.detected_format, "landscape")
            elif res.hard_clip_mm:
                w, h = res.hard_clip_mm
                sheet_w = w + self.doc.page.margin_left_mm + self.doc.page.margin_right_mm
                sheet_h = h + self.doc.page.margin_top_mm + self.doc.page.margin_bottom_mm
                self.doc.page.set_custom_size(sheet_w, sheet_h)
            self._sync_from_page()
            QMessageBox.information(
                self,
                "Papiergröße erkannt",
                f"Plotter an '{target}' meldet:\nModell: {res.model}\nFormat: {res.detected_format} ({self.doc.page.width_mm:.1f} × {self.doc.page.height_mm:.1f} mm)"
            )
        else:
            QMessageBox.warning(
                self,
                "Geräteabfrage fehlgeschlagen",
                f"Konnte Papiergröße von '{target}' nicht abfragen:\n{res.error_message or 'Keine Antwort vom Gerät'}"
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
        }
        # If changed and undo stack exists, push command
        if self.undo_stack and new_state != self._initial_state:
            # Revert page to initial state first, then push command so redo applies it
            self._apply_dict(self._initial_state)
            cmd = PageConfigCommand(
                self.doc.page, self._initial_state, new_state, self._on_undo_redo, text="Seiteneinrichtung ändern"
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
        p.margin_left_mm = state.get("margin_left_mm", p.margin_left_mm)
        p.margin_right_mm = state.get("margin_right_mm", p.margin_right_mm)
        p.margin_top_mm = state.get("margin_top_mm", p.margin_top_mm)
        p.margin_bottom_mm = state.get("margin_bottom_mm", p.margin_bottom_mm)

    def _on_undo_redo(self):
        self._sync_from_page()
        self.page_changed.emit()
