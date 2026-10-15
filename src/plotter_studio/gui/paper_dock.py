"""Paper and device management dock widget."""

from __future__ import annotations
from typing import Optional, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QDoubleSpinBox, QPushButton,
    QGroupBox, QLabel
)
from ..core.document import Document, PAPER_PRESETS, DEVICE_PROFILES
from .commands import PageConfigCommand


class PaperDockWidget(QDockWidget):
    """
    Dock widget managing:
    - Paper format presets (DIN A4..A0, Letter, Custom)
    - Sheet orientation (Landscape, Portrait)
    - Device profiles (Mutoh XP-500 roller vs Flatbed symmetric vs Custom)
    - Feed edge for roller plotters (Top, Bottom, Left, Right)
    - Dimensions in mm (Width x Height)
    - Margins in mm (X, Y)
    - Hardware paper query ('Papiergröße vom Gerät holen')
    """
    page_changed = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__("Papier & Gerät", parent)
        self.setObjectName("PaperDockWidget")
        self.doc = doc
        self.undo_stack: Optional[QUndoStack] = None

        self.container = QWidget(self)
        self.setWidget(self.container)
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(10)

        # --- Section: Paper Format & Orientation ---
        fmt_group = QGroupBox("Papierformat")
        f_layout = QFormLayout(fmt_group)

        # Paper Presets
        self.combo_preset = QComboBox()
        for p_name in PAPER_PRESETS.keys():
            self.combo_preset.addItem(f"DIN {p_name}" if p_name.startswith("A") else p_name, p_name)
        self.combo_preset.addItem("Benutzerdefiniert (Custom)", "Custom")
        self.combo_preset.setCurrentIndex(1)  # Default A3
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        f_layout.addRow("Format:", self.combo_preset)

        # Orientation
        self.combo_orient = QComboBox()
        self.combo_orient.addItem("Querformat (Landscape)", "landscape")
        self.combo_orient.addItem("Hochformat (Portrait)", "portrait")
        self.combo_orient.currentIndexChanged.connect(self._on_orient_changed)
        f_layout.addRow("Lage:", self.combo_orient)

        # Custom dimensions
        dim_layout = QHBoxLayout()
        self.spin_width = QDoubleSpinBox()
        self.spin_width.setRange(50.0, 3000.0)
        self.spin_width.setDecimals(1)
        self.spin_width.setSuffix(" mm")
        self.spin_width.setValue(self.doc.page.width_mm)
        self.spin_width.valueChanged.connect(self._on_custom_dim_changed)

        self.spin_height = QDoubleSpinBox()
        self.spin_height.setRange(50.0, 3000.0)
        self.spin_height.setDecimals(1)
        self.spin_height.setSuffix(" mm")
        self.spin_height.setValue(self.doc.page.height_mm)
        self.spin_height.valueChanged.connect(self._on_custom_dim_changed)

        dim_layout.addWidget(self.spin_width)
        dim_layout.addWidget(QLabel("x"))
        dim_layout.addWidget(self.spin_height)
        f_layout.addRow("Maße:", dim_layout)

        self.main_layout.addWidget(fmt_group)

        # --- Section: Plotter & Ränder ---
        dev_group = QGroupBox("Gerät & Ränder")
        d_layout = QFormLayout(dev_group)

        # Device Profile
        self.combo_device = QComboBox()
        for prof_key, prof_info in DEVICE_PROFILES.items():
            self.combo_device.addItem(prof_info["name"], prof_key)
        self.combo_device.currentIndexChanged.connect(self._on_device_profile_changed)
        d_layout.addRow("Gerätetyp:", self.combo_device)

        # Feed edge for roller plotters
        self.combo_feed = QComboBox()
        self.combo_feed.addItem("Vorschub: Oben (Standard)", "top")
        self.combo_feed.addItem("Vorschub: Unten", "bottom")
        self.combo_feed.addItem("Vorschub: Links", "left")
        self.combo_feed.addItem("Vorschub: Rechts", "right")
        self.combo_feed.currentIndexChanged.connect(self._on_feed_edge_changed)
        d_layout.addRow("Vorschubkante:", self.combo_feed)

        # Margins
        margin_layout = QHBoxLayout()
        self.spin_margin_x = QDoubleSpinBox()
        self.spin_margin_x.setRange(0.0, 100.0)
        self.spin_margin_x.setDecimals(1)
        self.spin_margin_x.setSuffix(" mm")
        self.spin_margin_x.setValue(self.doc.page.margin_left_mm)
        self.spin_margin_x.valueChanged.connect(self._on_margins_changed)

        self.spin_margin_y = QDoubleSpinBox()
        self.spin_margin_y.setRange(0.0, 100.0)
        self.spin_margin_y.setDecimals(1)
        self.spin_margin_y.setSuffix(" mm")
        self.spin_margin_y.setValue(self.doc.page.margin_top_mm)
        self.spin_margin_y.valueChanged.connect(self._on_margins_changed)

        margin_layout.addWidget(QLabel("X:"))
        margin_layout.addWidget(self.spin_margin_x)
        margin_layout.addWidget(QLabel("Y:"))
        margin_layout.addWidget(self.spin_margin_y)
        d_layout.addRow("Ränder:", margin_layout)

        # Fetch paper size button
        self.btn_fetch_device = QPushButton("Papiergröße vom Gerät holen")
        self.btn_fetch_device.setToolTip("Fragt OH; vom Plotter ab und passt das Format an die Andruckrollen an")
        self.btn_fetch_device.clicked.connect(self._on_fetch_device_size)
        d_layout.addRow(self.btn_fetch_device)

        self.main_layout.addWidget(dev_group)
        self.main_layout.addStretch()

        self.refresh_page_fields()

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def refresh_page_fields(self):
        self.spin_width.blockSignals(True)
        self.spin_height.blockSignals(True)
        self.spin_margin_x.blockSignals(True)
        self.spin_margin_y.blockSignals(True)
        self.combo_preset.blockSignals(True)
        self.combo_orient.blockSignals(True)
        self.combo_device.blockSignals(True)
        self.combo_feed.blockSignals(True)

        try:
            self.spin_width.setValue(self.doc.page.width_mm)
            self.spin_height.setValue(self.doc.page.height_mm)
            self.spin_margin_x.setValue(self.doc.page.margin_left_mm)
            self.spin_margin_y.setValue(self.doc.page.margin_top_mm)

            preset_idx = self.combo_preset.findData(self.doc.page.preset)
            if preset_idx >= 0:
                self.combo_preset.setCurrentIndex(preset_idx)

            orient_idx = self.combo_orient.findData(self.doc.page.orientation)
            if orient_idx >= 0:
                self.combo_orient.setCurrentIndex(orient_idx)

            dev_idx = self.combo_device.findData(self.doc.page.device_profile)
            if dev_idx >= 0:
                self.combo_device.setCurrentIndex(dev_idx)

            feed_idx = self.combo_feed.findData(self.doc.page.feed_edge)
            if feed_idx >= 0:
                self.combo_feed.setCurrentIndex(feed_idx)

            self.combo_feed.setEnabled(self.doc.page.device_profile == "mutoh_xp500")
        finally:
            self.spin_width.blockSignals(False)
            self.spin_height.blockSignals(False)
            self.spin_margin_x.blockSignals(False)
            self.spin_margin_y.blockSignals(False)
            self.combo_preset.blockSignals(False)
            self.combo_orient.blockSignals(False)
            self.combo_device.blockSignals(False)
            self.combo_feed.blockSignals(False)

    # --- Page / Device Configuration ---
    def _apply_page_state(self, new_state: Dict[str, Any], text: str = "Papierformat ändern"):
        old_state = {
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
        if self.undo_stack:
            cmd = PageConfigCommand(
                self.doc.page, old_state, new_state, self._on_page_cmd_updated, text=text
            )
            self.undo_stack.push(cmd)
        else:
            self._apply_dict_to_page(new_state)
            self._on_page_cmd_updated()

    def _apply_dict_to_page(self, state: Dict[str, Any]):
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

    def _on_page_cmd_updated(self):
        self.refresh_page_fields()
        self.page_changed.emit()

    def _on_preset_changed(self):
        preset = self.combo_preset.currentData()
        if preset != "Custom":
            self.doc.page.apply_preset(preset, self.combo_orient.currentData())
        self._on_page_cmd_updated()

    def _on_orient_changed(self):
        orient = self.combo_orient.currentData()
        preset = self.combo_preset.currentData()
        if preset != "Custom":
            self.doc.page.apply_preset(preset, orient)
        else:
            w, h = self.doc.page.width_mm, self.doc.page.height_mm
            if (orient == "landscape" and w < h) or (orient == "portrait" and w > h):
                self.doc.page.width_mm, self.doc.page.height_mm = h, w
        self._on_page_cmd_updated()

    def _on_device_profile_changed(self):
        prof_key = self.combo_device.currentData()
        self.doc.page.apply_device_profile(prof_key, self.combo_feed.currentData())
        self._on_page_cmd_updated()

    def _on_feed_edge_changed(self):
        edge = self.combo_feed.currentData()
        self.doc.page.apply_device_profile(self.doc.page.device_profile, edge)
        self._on_page_cmd_updated()

    def _on_custom_dim_changed(self):
        self.combo_preset.blockSignals(True)
        self.combo_preset.setCurrentIndex(self.combo_preset.findData("Custom"))
        self.combo_preset.blockSignals(False)
        self.doc.page.set_custom_size(self.spin_width.value(), self.spin_height.value())
        self.page_changed.emit()

    def _on_margins_changed(self):
        self.doc.page.device_profile = "custom"
        self.doc.page.margin_left_mm = self.spin_margin_x.value()
        self.doc.page.margin_right_mm = self.spin_margin_x.value()
        self.doc.page.margin_top_mm = self.spin_margin_y.value()
        self.doc.page.margin_bottom_mm = self.spin_margin_y.value()
        self.refresh_page_fields()
        self.page_changed.emit()

    def _on_fetch_device_size(self):
        """Simulate or query OH; bounds from connected plotter."""
        self.combo_preset.setCurrentIndex(self.combo_preset.findData("A2"))
        self.combo_orient.setCurrentIndex(self.combo_orient.findData("landscape"))
        self.doc.page.apply_device_profile("mutoh_xp500", "top")
        self._on_page_cmd_updated()
