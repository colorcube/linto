"""Layout, paper management and transformation dock widget."""

from __future__ import annotations
import copy
from typing import Optional, List, Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QComboBox, QDoubleSpinBox, QPushButton,
    QRadioButton, QButtonGroup, QGroupBox, QLabel, QCheckBox
)
from ..core.document import Document, PAPER_PRESETS, DEVICE_PROFILES, ImportItem
from ..core.geometry import AffineTransform, Point, BoundingBox
from .commands import TransformItemCommand, PageConfigCommand


class LayoutDockWidget(QDockWidget):
    """
    Dock widget managing:
    - Paper format (presets, custom mm, orientation, margins)
    - Device profiles (Mutoh XP-500 roller vs Flatbed symmetric vs Custom)
    - Object sizing & scaling (mm, percent, lock aspect ratio, fit to page, 1:1)
    - Object placement (center, percent, absolute mm coordinates)
    """
    page_changed = Signal()
    item_transformed = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__("Layout & Papier", parent)
        self.doc = doc
        self.active_item: Optional[ImportItem] = None
        self.undo_stack: Optional[QUndoStack] = None
        self._updating_fields = False

        self.container = QWidget(self)
        self.setWidget(self.container)
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.main_layout.setSpacing(10)

        # --- Section 1: Paper Format & Device Profile ---
        paper_group = QGroupBox("Papierformat & Plotter-Ränder")
        p_layout = QFormLayout(paper_group)

        # Paper Presets
        self.combo_preset = QComboBox()
        for p_name in PAPER_PRESETS.keys():
            self.combo_preset.addItem(f"DIN {p_name}" if p_name.startswith("A") else p_name, p_name)
        self.combo_preset.addItem("Benutzerdefiniert (Custom)", "Custom")
        self.combo_preset.setCurrentIndex(1)  # Default A3
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        p_layout.addRow("Format:", self.combo_preset)

        # Orientation
        self.combo_orient = QComboBox()
        self.combo_orient.addItem("Querformat (Landscape)", "landscape")
        self.combo_orient.addItem("Hochformat (Portrait)", "portrait")
        self.combo_orient.currentIndexChanged.connect(self._on_orient_changed)
        p_layout.addRow("Lage:", self.combo_orient)

        # Device Profile
        self.combo_device = QComboBox()
        for prof_key, prof_info in DEVICE_PROFILES.items():
            self.combo_device.addItem(prof_info["name"], prof_key)
        self.combo_device.currentIndexChanged.connect(self._on_device_profile_changed)
        p_layout.addRow("Gerätetyp:", self.combo_device)

        # Feed edge for roller plotters
        self.combo_feed = QComboBox()
        self.combo_feed.addItem("Vorschub: Oben (Standard)", "top")
        self.combo_feed.addItem("Vorschub: Unten", "bottom")
        self.combo_feed.addItem("Vorschub: Links", "left")
        self.combo_feed.addItem("Vorschub: Rechts", "right")
        self.combo_feed.currentIndexChanged.connect(self._on_feed_edge_changed)
        p_layout.addRow("Vorschubkante:", self.combo_feed)

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
        p_layout.addRow("Maße:", dim_layout)

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
        p_layout.addRow("Ränder:", margin_layout)

        # Fetch paper size button
        self.btn_fetch_device = QPushButton("Papiergröße vom Gerät holen")
        self.btn_fetch_device.setToolTip("Fragt OH; vom Plotter ab und passt das Canvas an die Andruckrollen an")
        self.btn_fetch_device.clicked.connect(self._on_fetch_device_size)
        p_layout.addRow(self.btn_fetch_device)

        self.main_layout.addWidget(paper_group)

        # --- Section 2: Size & Scaling (Größe & Skalierung) ---
        self.scale_group = QGroupBox("Größe & Skalierung")
        s_layout = QVBoxLayout(self.scale_group)

        self.lbl_item_name = QLabel("Kein Objekt ausgewählt")
        self.lbl_item_name.setStyleSheet("font-weight: bold; color: #555;")
        s_layout.addWidget(self.lbl_item_name)

        # Dimensions mm
        dim_form = QFormLayout()
        mm_row = QHBoxLayout()
        self.spin_obj_w = QDoubleSpinBox()
        self.spin_obj_w.setRange(1.0, 5000.0)
        self.spin_obj_w.setDecimals(1)
        self.spin_obj_w.setSuffix(" mm")
        self.spin_obj_w.valueChanged.connect(self._on_obj_w_changed)

        self.spin_obj_h = QDoubleSpinBox()
        self.spin_obj_h.setRange(1.0, 5000.0)
        self.spin_obj_h.setDecimals(1)
        self.spin_obj_h.setSuffix(" mm")
        self.spin_obj_h.valueChanged.connect(self._on_obj_h_changed)

        mm_row.addWidget(self.spin_obj_w)
        mm_row.addWidget(QLabel("x"))
        mm_row.addWidget(self.spin_obj_h)
        dim_form.addRow("Größe (mm):", mm_row)

        # Lock aspect ratio
        self.chk_keep_aspect = QCheckBox("Seitenverhältnis beibehalten")
        self.chk_keep_aspect.setChecked(True)
        dim_form.addRow("", self.chk_keep_aspect)

        # Scale percentage
        pct_row = QHBoxLayout()
        self.spin_obj_scale = QDoubleSpinBox()
        self.spin_obj_scale.setRange(1.0, 5000.0)
        self.spin_obj_scale.setDecimals(1)
        self.spin_obj_scale.setSingleStep(5.0)
        self.spin_obj_scale.setSuffix(" %")
        self.spin_obj_scale.setValue(100.0)
        self.spin_obj_scale.valueChanged.connect(self._on_scale_spin_changed)

        self.btn_scale_down = QPushButton("-10 %")
        self.btn_scale_down.clicked.connect(lambda: self.scale_relative(0.9))
        self.btn_scale_up = QPushButton("+10 %")
        self.btn_scale_up.clicked.connect(lambda: self.scale_relative(1.1))

        pct_row.addWidget(self.spin_obj_scale)
        pct_row.addWidget(self.btn_scale_down)
        pct_row.addWidget(self.btn_scale_up)
        dim_form.addRow("Skalierung:", pct_row)
        s_layout.addLayout(dim_form)

        # Quick action buttons: 1:1 and Fit to page with margin
        quick_scale_row = QHBoxLayout()
        self.btn_original_size = QPushButton("1:1 Originalgröße")
        self.btn_original_size.setToolTip("Setzt Skalierung auf exakte 100% (mm-Maße aus Quelldatei)")
        self.btn_original_size.clicked.connect(self.reset_to_original_size)

        self.btn_fit = QPushButton("Auf Blatt einpassen")
        self.btn_fit.setToolTip("Skaliert das Objekt proportional auf Blatt/Plottbereich")
        self.btn_fit.clicked.connect(lambda: self.fit_to_page())

        quick_scale_row.addWidget(self.btn_original_size)
        quick_scale_row.addWidget(self.btn_fit)
        s_layout.addLayout(quick_scale_row)

        # Margin input for fitting
        fit_margin_layout = QHBoxLayout()
        fit_margin_layout.addWidget(QLabel("Rand bei Einpassen:"))
        self.spin_fit_margin = QDoubleSpinBox()
        self.spin_fit_margin.setRange(0.0, 100.0)
        self.spin_fit_margin.setDecimals(1)
        self.spin_fit_margin.setValue(15.0)
        self.spin_fit_margin.setSuffix(" mm")
        fit_margin_layout.addWidget(self.spin_fit_margin)
        s_layout.addLayout(fit_margin_layout)

        self.main_layout.addWidget(self.scale_group)

        # --- Section 3: Alignment & Placement ---
        self.align_group = QGroupBox("Objekt-Platzierung")
        a_layout = QVBoxLayout(self.align_group)

        # Reference mode
        ref_layout = QHBoxLayout()
        self.rb_ref_page = QRadioButton("Bezug Blatt")
        self.rb_ref_clip = QRadioButton("Bezug Plottbereich")
        self.rb_ref_page.setChecked(True)
        self.ref_group = QButtonGroup(self)
        self.ref_group.addButton(self.rb_ref_page)
        self.ref_group.addButton(self.rb_ref_clip)
        self.rb_ref_page.toggled.connect(self.refresh_item_fields)
        ref_layout.addWidget(self.rb_ref_page)
        ref_layout.addWidget(self.rb_ref_clip)
        a_layout.addLayout(ref_layout)

        # Position inputs (mm and %)
        pos_form = QFormLayout()
        pos_mm_row = QHBoxLayout()
        self.spin_pos_x = QDoubleSpinBox()
        self.spin_pos_x.setRange(-2000.0, 5000.0)
        self.spin_pos_x.setDecimals(1)
        self.spin_pos_x.setSuffix(" mm")
        self.spin_pos_x.valueChanged.connect(self._on_pos_mm_changed)

        self.spin_pos_y = QDoubleSpinBox()
        self.spin_pos_y.setRange(-2000.0, 5000.0)
        self.spin_pos_y.setDecimals(1)
        self.spin_pos_y.setSuffix(" mm")
        self.spin_pos_y.valueChanged.connect(self._on_pos_mm_changed)

        pos_mm_row.addWidget(QLabel("X:"))
        pos_mm_row.addWidget(self.spin_pos_x)
        pos_mm_row.addWidget(QLabel("Y:"))
        pos_mm_row.addWidget(self.spin_pos_y)
        pos_form.addRow("Position (mm):", pos_mm_row)

        pos_pct_row = QHBoxLayout()
        self.spin_pos_pct_x = QDoubleSpinBox()
        self.spin_pos_pct_x.setRange(0.0, 100.0)
        self.spin_pos_pct_x.setDecimals(1)
        self.spin_pos_pct_x.setSuffix(" %")
        self.spin_pos_pct_x.valueChanged.connect(self._on_pos_pct_changed)

        self.spin_pos_pct_y = QDoubleSpinBox()
        self.spin_pos_pct_y.setRange(0.0, 100.0)
        self.spin_pos_pct_y.setDecimals(1)
        self.spin_pos_pct_y.setSuffix(" %")
        self.spin_pos_pct_y.valueChanged.connect(self._on_pos_pct_changed)

        pos_pct_row.addWidget(QLabel("X:"))
        pos_pct_row.addWidget(self.spin_pos_pct_x)
        pos_pct_row.addWidget(QLabel("Y:"))
        pos_pct_row.addWidget(self.spin_pos_pct_y)
        pos_form.addRow("Ausrichtung (%):", pos_pct_row)
        a_layout.addLayout(pos_form)

        # Alignment buttons
        btn_row1 = QHBoxLayout()
        self.btn_center_h = QPushButton("Horizontal")
        self.btn_center_h.clicked.connect(self.align_center_h)
        self.btn_center_v = QPushButton("Vertikal")
        self.btn_center_v.clicked.connect(self.align_center_v)
        self.btn_center_both = QPushButton("Mittig (Beide)")
        self.btn_center_both.clicked.connect(self.align_center_both)
        btn_row1.addWidget(self.btn_center_h)
        btn_row1.addWidget(self.btn_center_v)
        btn_row1.addWidget(self.btn_center_both)
        a_layout.addLayout(btn_row1)

        self.main_layout.addWidget(self.align_group)
        self.main_layout.addStretch()

        self._set_item_controls_enabled(False)

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def _set_item_controls_enabled(self, enabled: bool):
        self.scale_group.setEnabled(enabled)
        self.align_group.setEnabled(enabled)

    def set_active_item(self, item: Optional[ImportItem]):
        self.active_item = item
        if item is None:
            self.lbl_item_name.setText("Kein Objekt ausgewählt")
            self._set_item_controls_enabled(False)
        else:
            self.lbl_item_name.setText(f"Objekt: {item.name}")
            self._set_item_controls_enabled(True)
            self.refresh_item_fields()

    def refresh_item_fields(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        if self._updating_fields:
            return

        self._updating_fields = True
        try:
            ob = self.active_item.original_bounds
            sx = abs(self.active_item.transform.a)
            sy = abs(self.active_item.transform.d)
            current_w = ob.width * sx
            current_h = ob.height * sy
            scale_pct = sx * 100.0

            self.spin_obj_w.setValue(current_w)
            self.spin_obj_h.setValue(current_h)
            self.spin_obj_scale.setValue(scale_pct)

            cb = self.active_item.current_bounds
            tb = self._get_target_box()
            if cb:
                self.spin_pos_x.setValue(cb.min_x - tb.min_x)
                self.spin_pos_y.setValue(cb.min_y - tb.min_y)

                slack_w = tb.width - cb.width
                slack_h = tb.height - cb.height
                pct_x = ((cb.min_x - tb.min_x) / slack_w * 100.0) if abs(slack_w) > 1e-4 else 50.0
                pct_y = ((cb.min_y - tb.min_y) / slack_h * 100.0) if abs(slack_h) > 1e-4 else 50.0
                self.spin_pos_pct_x.setValue(max(0.0, min(100.0, pct_x)))
                self.spin_pos_pct_y.setValue(max(0.0, min(100.0, pct_y)))
        finally:
            self._updating_fields = False

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

    def _get_target_box(self) -> BoundingBox:
        if self.rb_ref_clip.isChecked():
            return self.doc.page.plottable_box
        return self.doc.page.sheet_box

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
        self.refresh_item_fields()

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
        self.refresh_item_fields()

    def _on_margins_changed(self):
        self.doc.page.device_profile = "custom"
        self.doc.page.margin_left_mm = self.spin_margin_x.value()
        self.doc.page.margin_right_mm = self.spin_margin_x.value()
        self.doc.page.margin_top_mm = self.spin_margin_y.value()
        self.doc.page.margin_bottom_mm = self.spin_margin_y.value()
        self.refresh_page_fields()
        self.page_changed.emit()
        self.refresh_item_fields()

    def _on_fetch_device_size(self):
        """Simulate or query OH; bounds from connected plotter."""
        self.combo_preset.setCurrentIndex(self.combo_preset.findData("A2"))
        self.combo_orient.setCurrentIndex(self.combo_orient.findData("landscape"))
        self.doc.page.apply_device_profile("mutoh_xp500", "top")
        self._on_page_cmd_updated()

    # --- Item Sizing & Transformation ---
    def _apply_item_transform(self, old_t: AffineTransform, new_t: AffineTransform, text: str):
        if not self.active_item:
            return
        if self.undo_stack:
            cmd = TransformItemCommand(
                self.active_item, old_t, new_t, self._on_transform_applied, text=text
            )
            self.undo_stack.push(cmd)
        else:
            self.active_item.transform = copy.deepcopy(new_t)
            self._on_transform_applied()

    def _on_transform_applied(self):
        self.refresh_item_fields()
        self.item_transformed.emit()

    def _apply_scale(self, new_scale_x: float, new_scale_y: float):
        if not self.active_item or not self.active_item.original_bounds:
            return
        ob = self.active_item.original_bounds
        cb = self.active_item.current_bounds
        if cb is None:
            return

        cx, cy = cb.center.x, cb.center.y
        loc_cx, loc_cy = ob.center.x, ob.center.y

        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.a = new_scale_x
        new_t.d = new_scale_y
        new_t.tx = cx - new_scale_x * loc_cx
        new_t.ty = cy - new_scale_y * loc_cy

        self._apply_item_transform(old_t, new_t, "Objekt skalieren")

    def _on_obj_w_changed(self, new_w: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        ob = self.active_item.original_bounds
        if ob.width <= 0:
            return
        scale_x = new_w / ob.width
        scale_y = scale_x if self.chk_keep_aspect.isChecked() else self.active_item.transform.d
        self._apply_scale(scale_x, scale_y)

    def _on_obj_h_changed(self, new_h: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        ob = self.active_item.original_bounds
        if ob.height <= 0:
            return
        scale_y = new_h / ob.height
        scale_x = scale_y if self.chk_keep_aspect.isChecked() else self.active_item.transform.a
        self._apply_scale(scale_x, scale_y)

    def _on_scale_spin_changed(self, pct: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        scale = max(0.01, pct / 100.0)
        self._apply_scale(scale, scale)

    def scale_relative(self, factor: float):
        if not self.active_item or not self.active_item.original_bounds:
            return
        new_sx = self.active_item.transform.a * factor
        new_sy = self.active_item.transform.d * factor
        self._apply_scale(new_sx, new_sy)

    def reset_to_original_size(self):
        """Reset scale to 1.0 (true 1:1 original mm size from source file)."""
        if not self.active_item:
            return
        self._apply_scale(1.0, 1.0)

    def fit_to_page(self, margin_mm: Optional[float] = None):
        if not self.active_item or not self.active_item.original_bounds:
            return
        if margin_mm is None:
            margin_mm = self.spin_fit_margin.value()

        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        avail_w = max(10.0, tb.width - 2 * margin_mm)
        avail_h = max(10.0, tb.height - 2 * margin_mm)
        if ob.width <= 0 or ob.height <= 0:
            return

        scale = min(avail_w / ob.width, avail_h / ob.height)
        loc_cx, loc_cy = ob.center.x, ob.center.y

        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.a = scale
        new_t.d = scale
        new_t.tx = tb.center.x - scale * loc_cx
        new_t.ty = tb.center.y - scale * loc_cy

        self._apply_item_transform(old_t, new_t, "Auf Blatt einpassen")

    # --- Position and Alignment ---
    def _on_pos_mm_changed(self):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        sx = self.active_item.transform.a
        sy = self.active_item.transform.d

        target_left = tb.min_x + self.spin_pos_x.value()
        target_top = tb.min_y + self.spin_pos_y.value()

        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx = target_left - sx * ob.min_x
        new_t.ty = target_top - sy * ob.min_y

        self._apply_item_transform(old_t, new_t, "Position ändern (mm)")

    def _on_pos_pct_changed(self):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        sx = self.active_item.transform.a
        sy = self.active_item.transform.d

        item_w = ob.width * sx
        item_h = ob.height * sy
        slack_w = tb.width - item_w
        slack_h = tb.height - item_h

        pct_x = self.spin_pos_pct_x.value() / 100.0
        pct_y = self.spin_pos_pct_y.value() / 100.0

        target_left = tb.min_x + pct_x * slack_w
        target_top = tb.min_y + pct_y * slack_h

        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx = target_left - sx * ob.min_x
        new_t.ty = target_top - sy * ob.min_y

        self._apply_item_transform(old_t, new_t, "Position ändern (%)")

    def align_center_h(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx = tb.center.x - old_t.a * ob.center.x
        self._apply_item_transform(old_t, new_t, "Horizontal zentrieren")

    def align_center_v(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.ty = tb.center.y - old_t.d * ob.center.y
        self._apply_item_transform(old_t, new_t, "Vertikal zentrieren")

    def align_center_both(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        ob = self.active_item.original_bounds
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx = tb.center.x - old_t.a * ob.center.x
        new_t.ty = tb.center.y - old_t.d * ob.center.y
        self._apply_item_transform(old_t, new_t, "Mittig zentrieren")
