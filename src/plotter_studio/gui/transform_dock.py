"""Transform, scaling and placement dock widget in compact Inkscape tool style."""

from __future__ import annotations
import copy
import math
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QDoubleSpinBox, QPushButton, QToolButton,
    QRadioButton, QButtonGroup, QLabel, QFrame,
    QGroupBox, QScrollArea
)
from ..core.document import Document, ImportItem
from ..core.geometry import AffineTransform, Point, BoundingBox
from .commands import TransformItemCommand
from .icons import get_icon


class TransformDockWidget(QDockWidget):
    """
    Compact, tool-oriented dock widget for scaling, rotating and placing objects.
    Inkscape-like layout with direct mm inputs, aspect ratio lock, and quick tool buttons.
    """
    item_transformed = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__("Skalieren & Platzieren", parent)
        self.setObjectName("TransformDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.doc = doc
        self.active_item: Optional[ImportItem] = None
        self.undo_stack: Optional[QUndoStack] = None
        self._updating_fields = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        scroll.setWidget(self.container)
        self.setWidget(scroll)

        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(6, 6, 6, 6)
        self.main_layout.setSpacing(8)

        # 1. Header / Object Info
        header_box = QHBoxLayout()
        header_box.setSpacing(4)
        self.lbl_item_icon = QLabel()
        self.lbl_item_name = QLabel("Kein Objekt ausgewählt")
        self.lbl_item_name.setStyleSheet("font-weight: bold; color: #374151;")
        self.lbl_locked_badge = QLabel()
        self.lbl_locked_badge.setStyleSheet("color: #b91c1c; font-size: 11px; font-weight: bold;")
        self.lbl_locked_badge.setVisible(False)

        header_box.addWidget(self.lbl_item_icon)
        header_box.addWidget(self.lbl_item_name)
        header_box.addStretch()
        header_box.addWidget(self.lbl_locked_badge)
        self.main_layout.addLayout(header_box)

        # 2. Gruppe "Transformation" (Numerische Maße, Position und Skalierung)
        self.grp_transform = QGroupBox("Transformation")
        t_layout = QVBoxLayout(self.grp_transform)
        t_layout.setContentsMargins(8, 8, 8, 8)
        t_layout.setSpacing(6)

        # Position Section (X / Y with Reference Mode)
        pos_header = QHBoxLayout()
        lbl_pos = QLabel("Position:")
        lbl_pos.setStyleSheet("font-weight: 600; color: #4b5563;")
        pos_header.addWidget(lbl_pos)
        pos_header.addStretch()

        self.rb_ref_page = QRadioButton("Blatt")
        self.rb_ref_clip = QRadioButton("Plottbereich")
        self.rb_ref_page.setChecked(True)
        self.ref_group = QButtonGroup(self)
        self.ref_group.addButton(self.rb_ref_page)
        self.ref_group.addButton(self.rb_ref_clip)
        self.rb_ref_page.toggled.connect(self.refresh_item_fields)
        pos_header.addWidget(self.rb_ref_page)
        pos_header.addWidget(self.rb_ref_clip)
        t_layout.addLayout(pos_header)

        pos_grid = QGridLayout()
        pos_grid.setContentsMargins(0, 0, 0, 0)
        pos_grid.setSpacing(4)

        pos_grid.addWidget(QLabel("X:"), 0, 0)
        self.spin_pos_x = QDoubleSpinBox()
        self.spin_pos_x.setRange(-2000.0, 5000.0)
        self.spin_pos_x.setDecimals(1)
        self.spin_pos_x.setSuffix(" mm")
        self.spin_pos_x.valueChanged.connect(self._on_pos_mm_changed)
        pos_grid.addWidget(self.spin_pos_x, 0, 1)

        pos_grid.addWidget(QLabel("Y:"), 0, 2)
        self.spin_pos_y = QDoubleSpinBox()
        self.spin_pos_y.setRange(-2000.0, 5000.0)
        self.spin_pos_y.setDecimals(1)
        self.spin_pos_y.setSuffix(" mm")
        self.spin_pos_y.valueChanged.connect(self._on_pos_mm_changed)
        pos_grid.addWidget(self.spin_pos_y, 0, 3)

        t_layout.addLayout(pos_grid)

        # Dimensions Section (Width / Chain / Height)
        dim_header = QHBoxLayout()
        lbl_dim = QLabel("Abmessungen:")
        lbl_dim.setStyleSheet("font-weight: 600; color: #4b5563;")
        dim_header.addWidget(lbl_dim)
        dim_header.addStretch()
        t_layout.addLayout(dim_header)

        dim_grid = QGridLayout()
        dim_grid.setContentsMargins(0, 0, 0, 0)
        dim_grid.setSpacing(4)

        dim_grid.addWidget(QLabel("B:"), 0, 0)
        self.spin_obj_w = QDoubleSpinBox()
        self.spin_obj_w.setRange(1.0, 5000.0)
        self.spin_obj_w.setDecimals(1)
        self.spin_obj_w.setSuffix(" mm")
        self.spin_obj_w.valueChanged.connect(self._on_obj_w_changed)
        dim_grid.addWidget(self.spin_obj_w, 0, 1)

        # Proportional chain toggle button
        self.btn_chain = QToolButton(self)
        self.btn_chain.setCheckable(True)
        self.btn_chain.setChecked(True)
        self.btn_chain.setToolTip("Seitenverhältnis sperren")
        self._update_chain_icon()
        self.btn_chain.toggled.connect(self._on_chain_toggled)
        dim_grid.addWidget(self.btn_chain, 0, 2)

        dim_grid.addWidget(QLabel("H:"), 0, 3)
        self.spin_obj_h = QDoubleSpinBox()
        self.spin_obj_h.setRange(1.0, 5000.0)
        self.spin_obj_h.setDecimals(1)
        self.spin_obj_h.setSuffix(" mm")
        self.spin_obj_h.valueChanged.connect(self._on_obj_h_changed)
        dim_grid.addWidget(self.spin_obj_h, 0, 4)

        t_layout.addLayout(dim_grid)

        # Scale Percentage
        scale_box = QHBoxLayout()
        scale_box.setSpacing(4)
        lbl_scale = QLabel("Skalierung:")
        lbl_scale.setStyleSheet("font-weight: 600; color: #4b5563;")
        scale_box.addWidget(lbl_scale)

        self.spin_obj_scale = QDoubleSpinBox()
        self.spin_obj_scale.setRange(1.0, 5000.0)
        self.spin_obj_scale.setDecimals(1)
        self.spin_obj_scale.setSingleStep(5.0)
        self.spin_obj_scale.setSuffix(" %")
        self.spin_obj_scale.setValue(100.0)
        self.spin_obj_scale.valueChanged.connect(self._on_scale_spin_changed)
        scale_box.addWidget(self.spin_obj_scale)

        self.btn_scale_down = QPushButton("-10%")
        self.btn_scale_down.setFixedWidth(44)
        self.btn_scale_down.setToolTip("Um 10% verkleinern")
        self.btn_scale_down.clicked.connect(lambda: self.scale_relative(0.9))
        scale_box.addWidget(self.btn_scale_down)

        self.btn_scale_up = QPushButton("+10%")
        self.btn_scale_up.setFixedWidth(44)
        self.btn_scale_up.setToolTip("Um 10% vergrößern")
        self.btn_scale_up.clicked.connect(lambda: self.scale_relative(1.1))
        scale_box.addWidget(self.btn_scale_up)

        t_layout.addLayout(scale_box)
        self.main_layout.addWidget(self.grp_transform)

        # 3. Gruppe "Rotation"
        self.grp_rotation = QGroupBox("Rotation")
        r_layout = QHBoxLayout(self.grp_rotation)
        r_layout.setContentsMargins(8, 8, 8, 8)
        r_layout.setSpacing(6)

        self.btn_rotate_ccw = QPushButton("-90°")
        self.btn_rotate_ccw.setIcon(get_icon("rotate-ccw", size=16))
        self.btn_rotate_ccw.setToolTip("90° gegen Uhrzeigersinn drehen (Strg+Umschalt+R)")
        self.btn_rotate_ccw.clicked.connect(lambda: self.rotate_selected(-90.0))

        self.btn_rotate_cw = QPushButton("+90°")
        self.btn_rotate_cw.setIcon(get_icon("rotate-cw", size=16))
        self.btn_rotate_cw.setToolTip("90° im Uhrzeigersinn drehen (Strg+R)")
        self.btn_rotate_cw.clicked.connect(lambda: self.rotate_selected(90.0))

        r_layout.addWidget(self.btn_rotate_ccw)
        r_layout.addWidget(self.btn_rotate_cw)
        self.main_layout.addWidget(self.grp_rotation)

        # 4. Gruppe "Platzieren"
        self.grp_placement = QGroupBox("Platzieren")
        p_layout = QHBoxLayout(self.grp_placement)
        p_layout.setContentsMargins(8, 8, 8, 8)
        p_layout.setSpacing(6)

        self.btn_center_h = QPushButton("Horiz. Mittig")
        self.btn_center_h.setIcon(get_icon("align-h-center", size=16))
        self.btn_center_h.setToolTip("Horizontal auf Blatt / Plottbereich mittig ausrichten")
        self.btn_center_h.clicked.connect(self.align_center_h)

        self.btn_center_v = QPushButton("Vert. Mittig")
        self.btn_center_v.setIcon(get_icon("align-v-center", size=16))
        self.btn_center_v.setToolTip("Vertikal auf Blatt / Plottbereich mittig ausrichten")
        self.btn_center_v.clicked.connect(self.align_center_v)

        self.btn_center_both = QPushButton("Zentrieren")
        self.btn_center_both.setIcon(get_icon("align-center", size=16))
        self.btn_center_both.setToolTip("Auf Blatt / Plottbereich mittig zentrieren (beide Achsen)")
        self.btn_center_both.clicked.connect(self.align_center_both)

        p_layout.addWidget(self.btn_center_h)
        p_layout.addWidget(self.btn_center_v)
        p_layout.addWidget(self.btn_center_both)
        self.main_layout.addWidget(self.grp_placement)

        # 5. Gruppe "Skalieren"
        self.grp_scaling = QGroupBox("Skalieren")
        s_layout = QVBoxLayout(self.grp_scaling)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        margin_layout = QHBoxLayout()
        margin_layout.setSpacing(6)
        lbl_margin = QLabel("Rand beim Einpassen:")
        lbl_margin.setStyleSheet("color: #4b5563;")
        lbl_margin.setToolTip("Sicherheitsabstand / Mindestabstand zum Blattrand bzw. Plottbereich beim Einpassen")

        self.spin_fit_margin = QDoubleSpinBox()
        self.spin_fit_margin.setRange(0.0, 500.0)
        self.spin_fit_margin.setDecimals(1)
        self.spin_fit_margin.setValue(15.0)
        self.spin_fit_margin.setSuffix(" mm")
        self.spin_fit_margin.setMinimumWidth(100)
        self.spin_fit_margin.setToolTip("Sicherheitsabstand / Mindestabstand zum Blattrand bzw. Plottbereich beim Einpassen")

        margin_layout.addWidget(lbl_margin)
        margin_layout.addWidget(self.spin_fit_margin)
        s_layout.addLayout(margin_layout)

        scale_btn_layout = QHBoxLayout()
        scale_btn_layout.setSpacing(6)

        self.btn_fit = QPushButton("Einpassen")
        self.btn_fit.setIcon(get_icon("fit-page", size=16))
        self.btn_fit.setToolTip("Proportional auf Blatt/Plottbereich einpassen unter Beachtung des Randabstands")
        self.btn_fit.clicked.connect(lambda: self.fit_to_page())

        self.btn_original_size = QPushButton("1:1 Originalgröße")
        self.btn_original_size.setIcon(get_icon("original-size", size=16))
        self.btn_original_size.setToolTip("Auf Originalgröße (1:1 aus Quelldatei) zurücksetzen")
        self.btn_original_size.clicked.connect(self.reset_to_original_size)

        scale_btn_layout.addWidget(self.btn_fit)
        scale_btn_layout.addWidget(self.btn_original_size)
        s_layout.addLayout(scale_btn_layout)

        self.main_layout.addWidget(self.grp_scaling)
        self.main_layout.addStretch()

        self._set_item_controls_enabled(False)

    @property
    def rot_group(self):
        """Backward compatibility alias for rotation controls."""
        return self.grp_rotation

    def _update_chain_icon(self):
        if self.btn_chain.isChecked():
            self.btn_chain.setIcon(get_icon("chain", size=16))
            self.btn_chain.setToolTip("Seitenverhältnis gesperrt (klicken zum Lösen)")
        else:
            self.btn_chain.setIcon(get_icon("chain-broken", size=16))
            self.btn_chain.setToolTip("Seitenverhältnis frei (klicken zum Sperren)")

    def _on_chain_toggled(self, checked: bool):
        self._update_chain_icon()

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def _set_item_controls_enabled(self, enabled: bool):
        self.grp_transform.setEnabled(enabled)
        self.grp_rotation.setEnabled(enabled)
        self.grp_placement.setEnabled(enabled)
        self.grp_scaling.setEnabled(enabled)

        self.rb_ref_page.setEnabled(enabled)
        self.rb_ref_clip.setEnabled(enabled)
        self.spin_pos_x.setEnabled(enabled)
        self.spin_pos_y.setEnabled(enabled)
        self.spin_obj_w.setEnabled(enabled)
        self.spin_obj_h.setEnabled(enabled)
        self.btn_chain.setEnabled(enabled)
        self.spin_obj_scale.setEnabled(enabled)
        self.btn_scale_down.setEnabled(enabled)
        self.btn_scale_up.setEnabled(enabled)
        self.btn_rotate_ccw.setEnabled(enabled)
        self.btn_rotate_cw.setEnabled(enabled)
        self.btn_center_h.setEnabled(enabled)
        self.btn_center_v.setEnabled(enabled)
        self.btn_center_both.setEnabled(enabled)
        self.btn_fit.setEnabled(enabled)
        self.spin_fit_margin.setEnabled(enabled)
        self.btn_original_size.setEnabled(enabled)

    def set_active_item(self, item: Optional[ImportItem]):
        self.active_item = item
        if item is None:
            self.lbl_item_name.setText("Kein Objekt ausgewählt")
            self.lbl_locked_badge.setVisible(False)
            self._set_item_controls_enabled(False)
        else:
            self.lbl_item_name.setText(item.name)
            if item.locked:
                self.lbl_locked_badge.setText("🔒 Gesperrt")
                self.lbl_locked_badge.setVisible(True)
                self._set_item_controls_enabled(False)
            else:
                self.lbl_locked_badge.setVisible(False)
                self._set_item_controls_enabled(True)
            self.refresh_item_fields()

    def refresh_item_fields(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        if self._updating_fields:
            return

        self._updating_fields = True
        try:
            cb = self.active_item.current_bounds
            if not cb:
                return

            sx = math.hypot(self.active_item.transform.a, self.active_item.transform.b)
            scale_pct = sx * 100.0

            self.spin_obj_w.setValue(cb.width)
            self.spin_obj_h.setValue(cb.height)
            self.spin_obj_scale.setValue(scale_pct)

            tb = self._get_target_box()
            self.spin_pos_x.setValue(cb.min_x - tb.min_x)
            self.spin_pos_y.setValue(cb.min_y - tb.min_y)
        finally:
            self._updating_fields = False

    def _get_target_box(self) -> BoundingBox:
        if self.rb_ref_clip.isChecked():
            return self.doc.page.plottable_box
        return self.doc.page.sheet_box

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

    def rotate_selected(self, angle_degrees: float):
        """Rotate active item around its current visual center."""
        if not self.active_item or not self.active_item.original_bounds:
            return
        cb = self.active_item.current_bounds
        if cb is None:
            return

        cx, cy = cb.center.x, cb.center.y
        old_t = copy.deepcopy(self.active_item.transform)
        rot_t = AffineTransform.rotation(angle_degrees, cx, cy)
        new_t = rot_t.multiply(old_t)

        dir_str = "im Uhrzeigersinn" if angle_degrees > 0 else "gegen den Uhrzeigersinn"
        self._apply_item_transform(old_t, new_t, f"Objekt drehen ({int(abs(angle_degrees))}° {dir_str})")

    def _apply_scene_scale(self, factor_x: float, factor_y: float):
        """Scale active item around its center in scene coordinates, preserving rotation."""
        if not self.active_item or not self.active_item.original_bounds:
            return
        cb = self.active_item.current_bounds
        if cb is None:
            return

        cx, cy = cb.center.x, cb.center.y
        old_t = copy.deepcopy(self.active_item.transform)

        t1 = AffineTransform.translation(-cx, -cy)
        s = AffineTransform(factor_x, 0.0, 0.0, factor_y, 0.0, 0.0)
        t2 = AffineTransform.translation(cx, cy)
        s_scene = t2.multiply(s.multiply(t1))

        new_t = s_scene.multiply(old_t)
        self._apply_item_transform(old_t, new_t, "Objekt skalieren")

    def _on_obj_w_changed(self, new_w: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        cb = self.active_item.current_bounds
        if cb is None or cb.width <= 0:
            return
        factor_x = new_w / cb.width
        factor_y = factor_x if self.btn_chain.isChecked() else 1.0
        self._apply_scene_scale(factor_x, factor_y)

    def _on_obj_h_changed(self, new_h: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        cb = self.active_item.current_bounds
        if cb is None or cb.height <= 0:
            return
        factor_y = new_h / cb.height
        factor_x = factor_y if self.btn_chain.isChecked() else 1.0
        self._apply_scene_scale(factor_x, factor_y)

    def _on_scale_spin_changed(self, pct: float):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        target_scale = max(0.01, pct / 100.0)
        cur_scale = math.hypot(self.active_item.transform.a, self.active_item.transform.b)
        if cur_scale <= 1e-6:
            return
        factor = target_scale / cur_scale
        self._apply_scene_scale(factor, factor)

    def scale_relative(self, factor: float):
        self._apply_scene_scale(factor, factor)

    def reset_to_original_size(self):
        """Reset scale to 1.0 (true 1:1 original mm size from source file), preserving rotation."""
        if not self.active_item:
            return
        cur_scale = math.hypot(self.active_item.transform.a, self.active_item.transform.b)
        if cur_scale <= 1e-6:
            return
        factor = 1.0 / cur_scale
        self._apply_scene_scale(factor, factor)

    def fit_to_page(self, margin_mm: Optional[float] = None):
        if not self.active_item or not self.active_item.original_bounds:
            return
        if margin_mm is None:
            margin_mm = self.spin_fit_margin.value()

        tb = self._get_target_box()
        cb = self.active_item.current_bounds
        if cb is None or cb.width <= 0 or cb.height <= 0:
            return

        avail_w = max(10.0, tb.width - 2 * margin_mm)
        avail_h = max(10.0, tb.height - 2 * margin_mm)

        scale_factor = min(avail_w / cb.width, avail_h / cb.height)
        cx, cy = cb.center.x, cb.center.y
        old_t = copy.deepcopy(self.active_item.transform)

        t1 = AffineTransform.translation(-cx, -cy)
        s = AffineTransform(scale_factor, 0.0, 0.0, scale_factor, 0.0, 0.0)
        t2 = AffineTransform.translation(tb.center.x, tb.center.y)
        fit_t = t2.multiply(s.multiply(t1))

        new_t = fit_t.multiply(old_t)
        self._apply_item_transform(old_t, new_t, "Auf Blatt einpassen")

    # --- Position and Alignment ---
    def _on_pos_mm_changed(self):
        if self._updating_fields or not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        cb = self.active_item.current_bounds
        if cb is None:
            return

        target_left = tb.min_x + self.spin_pos_x.value()
        target_top = tb.min_y + self.spin_pos_y.value()
        dx = target_left - cb.min_x
        dy = target_top - cb.min_y

        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx += dx
        new_t.ty += dy

        self._apply_item_transform(old_t, new_t, "Position ändern (mm)")

    def align_center_h(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        cb = self.active_item.current_bounds
        if cb is None:
            return
        dx = tb.center.x - cb.center.x
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx += dx
        self._apply_item_transform(old_t, new_t, "Horizontal zentrieren")

    def align_center_v(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        cb = self.active_item.current_bounds
        if cb is None:
            return
        dy = tb.center.y - cb.center.y
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.ty += dy
        self._apply_item_transform(old_t, new_t, "Vertikal zentrieren")

    def align_center_both(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        tb = self._get_target_box()
        cb = self.active_item.current_bounds
        if cb is None:
            return
        dx = tb.center.x - cb.center.x
        dy = tb.center.y - cb.center.y
        old_t = copy.deepcopy(self.active_item.transform)
        new_t = copy.deepcopy(old_t)
        new_t.tx += dx
        new_t.ty += dy
        self._apply_item_transform(old_t, new_t, "Mittig zentrieren")
