"""Transform, scaling and placement dock widget in compact Inkscape tool style."""

from __future__ import annotations
import copy
import math
from typing import Optional
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QDoubleSpinBox, QPushButton, QToolButton,
    QRadioButton, QButtonGroup, QLabel, QFrame,
    QGroupBox, QScrollArea
)
from ..core.document import Document, ImportItem
from ..core.geometry import AffineTransform, BoundingBox
from ..core.layout_ops import (
    get_combined_bounds,
    compute_rotation_transforms,
    compute_scene_scale_transforms,
    compute_reset_scale_transforms,
    compute_fit_to_box_transforms,
    compute_position_transforms,
    compute_align_center_transforms,
)
from .commands import (
    TransformItemCommand,
    CMD_ID_POS,
    CMD_ID_SIZE,
    CMD_ID_SCALE,
    CMD_ID_ROT,
)
from .icons import get_icon


class SectionGroup(QGroupBox):
    """Clean group container with a header label and horizontal line instead of a box border."""

    toggled_collapse = Signal(bool)

    def __init__(self, title: str, parent=None, collapsible: bool = False, collapsed: bool = False):
        super().__init__("", parent)
        self._section_title = title
        self._collapsible = collapsible
        self._collapsed = False
        self.setStyleSheet("QGroupBox { border: none; margin: 0; padding: 0; background: transparent; }")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 4, 0, 2)
        main_layout.setSpacing(4)

        # Header with prominent title and visible dividing line
        header_vbox = QVBoxLayout()
        header_vbox.setContentsMargins(0, 2, 0, 2)
        header_vbox.setSpacing(3)

        header_hbox = QHBoxLayout()
        header_hbox.setContentsMargins(0, 0, 0, 0)
        header_hbox.setSpacing(6)

        if collapsible:
            self.btn_toggle = QToolButton(self)
            self.btn_toggle.setIcon(get_icon("chevron-down" if not collapsed else "chevron-right", size=12))
            self.btn_toggle.setFixedSize(16, 16)
            self.btn_toggle.setStyleSheet("QToolButton { border: none; background: transparent; }")
            self.btn_toggle.clicked.connect(self.toggle_collapsed)
            header_hbox.addWidget(self.btn_toggle)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(
            "QLabel { font-weight: bold; color: #1e293b; font-size: 13px; } "
            "QLabel:disabled { color: #94a3b8; }"
        )
        if collapsible:
            self.lbl_title.setCursor(Qt.PointingHandCursor)
            self.lbl_title.mousePressEvent = lambda e: self.toggle_collapsed()
        header_hbox.addWidget(self.lbl_title)
        header_hbox.addStretch()
        header_vbox.addLayout(header_hbox)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #cbd5e1; border: none;")
        header_vbox.addWidget(line)

        main_layout.addLayout(header_vbox)

        self._body_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self._body_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 2)
        self.content_layout.setSpacing(6)
        main_layout.addWidget(self._body_widget)

        if collapsed:
            self.set_collapsed(True)

    def addWidget(self, widget: QWidget, *args):
        self.content_layout.addWidget(widget, *args)

    def addLayout(self, layout, *args):
        self.content_layout.addLayout(layout, *args)

    def title(self) -> str:
        return self._section_title

    def setTitle(self, title: str):
        self._section_title = title
        self.lbl_title.setText(title)

    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool):
        self._collapsed = collapsed
        self._body_widget.setVisible(not collapsed)
        if self._collapsible and hasattr(self, 'btn_toggle'):
            icon_name = "chevron-right" if collapsed else "chevron-down"
            self.btn_toggle.setIcon(get_icon(icon_name, size=12))
        self.toggled_collapse.emit(collapsed)


class TransformDockWidget(QDockWidget):
    """
    Compact, tool-oriented dock widget for scaling, rotating and placing objects.
    Inkscape-like layout with direct mm inputs, aspect ratio lock, and quick tool buttons.
    """
    item_transformed = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__(self.tr("Transform"), parent)
        self.setObjectName("TransformDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.doc = doc
        self.active_item: Optional[ImportItem] = None
        self.selected_items: list[ImportItem] = []
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
        self.lbl_item_name = QLabel(self.tr("No object selected"))
        self.lbl_item_name.setStyleSheet("font-weight: bold; color: #374151;")
        self.lbl_locked_badge = QLabel()
        self.lbl_locked_badge.setStyleSheet("color: #b91c1c; font-size: 11px; font-weight: bold;")
        self.lbl_locked_badge.setVisible(False)

        header_box.addWidget(self.lbl_item_icon)
        header_box.addWidget(self.lbl_item_name)
        header_box.addStretch()
        header_box.addWidget(self.lbl_locked_badge)
        self.main_layout.addLayout(header_box)

        # 2. Group "Position"
        self.grp_transform = SectionGroup(self.tr("Position"))
        self.grp_position = self.grp_transform

        # Position Section (X / Y with Reference Mode)
        pos_header = QHBoxLayout()
        pos_header.setSpacing(6)
        lbl_pos = QLabel(self.tr("Reference:"))
        lbl_pos.setStyleSheet("font-weight: 500; color: #4b5563;")
        pos_header.addWidget(lbl_pos)

        self.rb_ref_page = QRadioButton(self.tr("Sheet"))
        self.rb_ref_clip = QRadioButton(self.tr("Printable Area"))
        self.rb_ref_page.setChecked(True)
        self.ref_group = QButtonGroup(self)
        self.ref_group.addButton(self.rb_ref_page)
        self.ref_group.addButton(self.rb_ref_clip)
        self.rb_ref_page.toggled.connect(self.refresh_item_fields)
        pos_header.addWidget(self.rb_ref_page)
        pos_header.addWidget(self.rb_ref_clip)
        pos_header.addStretch()
        self.grp_transform.addLayout(pos_header)

        # Position & Dimensionen (X / Y und W / 🔒 / H) in einem dynamischen Grid
        grid_pos_dim = QGridLayout()
        grid_pos_dim.setContentsMargins(0, 0, 0, 0)
        grid_pos_dim.setSpacing(6)

        lbl_x = QLabel(self.tr("X:"))
        lbl_x.setStyleSheet("font-weight: 500; color: #4b5563;")
        self.spin_pos_x = QDoubleSpinBox()
        self.spin_pos_x.setAlignment(Qt.AlignLeft)
        self.spin_pos_x.setRange(-2000.0, 5000.0)
        self.spin_pos_x.setDecimals(1)
        self.spin_pos_x.setSuffix(" mm")
        self.spin_pos_x.setKeyboardTracking(False)
        self.spin_pos_x.valueChanged.connect(self._on_pos_mm_changed)

        lbl_y = QLabel(self.tr("Y:"))
        lbl_y.setStyleSheet("font-weight: 500; color: #4b5563;")
        self.spin_pos_y = QDoubleSpinBox()
        self.spin_pos_y.setAlignment(Qt.AlignLeft)
        self.spin_pos_y.setRange(-2000.0, 5000.0)
        self.spin_pos_y.setDecimals(1)
        self.spin_pos_y.setSuffix(" mm")
        self.spin_pos_y.setKeyboardTracking(False)
        self.spin_pos_y.valueChanged.connect(self._on_pos_mm_changed)

        lbl_w = QLabel(self.tr("W:"))
        lbl_w.setStyleSheet("font-weight: 500; color: #4b5563;")
        self.spin_obj_w = QDoubleSpinBox()
        self.spin_obj_w.setAlignment(Qt.AlignLeft)
        self.spin_obj_w.setRange(1.0, 5000.0)
        self.spin_obj_w.setDecimals(1)
        self.spin_obj_w.setSuffix(" mm")
        self.spin_obj_w.setKeyboardTracking(False)
        self.spin_obj_w.valueChanged.connect(self._on_obj_w_changed)

        # Proportional padlock toggle button (Inkscape style)
        self.btn_chain = QToolButton(self)
        self.btn_chain.setCheckable(True)
        self.btn_chain.setChecked(True)
        self._update_chain_icon()
        self.btn_chain.toggled.connect(self._on_chain_toggled)

        lbl_h = QLabel(self.tr("H:"))
        lbl_h.setStyleSheet("font-weight: 500; color: #4b5563;")
        self.spin_obj_h = QDoubleSpinBox()
        self.spin_obj_h.setAlignment(Qt.AlignLeft)
        self.spin_obj_h.setRange(1.0, 5000.0)
        self.spin_obj_h.setDecimals(1)
        self.spin_obj_h.setSuffix(" mm")
        self.spin_obj_h.setKeyboardTracking(False)
        self.spin_obj_h.valueChanged.connect(self._on_obj_h_changed)

        grid_pos_dim.addWidget(lbl_x, 0, 0)
        grid_pos_dim.addWidget(self.spin_pos_x, 0, 1)
        grid_pos_dim.addWidget(lbl_y, 0, 3)
        grid_pos_dim.addWidget(self.spin_pos_y, 0, 4)

        grid_pos_dim.addWidget(lbl_w, 1, 0)
        grid_pos_dim.addWidget(self.spin_obj_w, 1, 1)
        grid_pos_dim.addWidget(self.btn_chain, 1, 2, alignment=Qt.AlignCenter)
        grid_pos_dim.addWidget(lbl_h, 1, 3)
        grid_pos_dim.addWidget(self.spin_obj_h, 1, 4)

        grid_pos_dim.setColumnStretch(5, 1)
        self.grp_transform.addLayout(grid_pos_dim)
        self.main_layout.addWidget(self.grp_transform)

        # 3. Group "Rotation"
        self.grp_rotation = SectionGroup(self.tr("Rotation"))
        r_layout = QHBoxLayout()
        r_layout.setSpacing(6)

        lbl_angle = QLabel(self.tr("Angle:"))
        lbl_angle.setStyleSheet("font-weight: 500; color: #4b5563;")
        r_layout.addWidget(lbl_angle)

        self.spin_rot_angle = QDoubleSpinBox()
        self.spin_rot_angle.setAlignment(Qt.AlignLeft)
        self.spin_rot_angle.setRange(-360.0, 360.0)
        self.spin_rot_angle.setDecimals(1)
        self.spin_rot_angle.setSingleStep(5.0)
        self.spin_rot_angle.setSuffix(" °")
        self.spin_rot_angle.setKeyboardTracking(False)
        self.spin_rot_angle.setToolTip(self.tr("Rotation angle in degrees"))
        self.spin_rot_angle.valueChanged.connect(self._on_rot_angle_spin_changed)
        r_layout.addWidget(self.spin_rot_angle)

        self.btn_rotate_ccw = QPushButton("-90°")
        self.btn_rotate_ccw.setIcon(get_icon("rotate-ccw", size=16))
        self.btn_rotate_ccw.setToolTip(self.tr("Rotate 90° CCW (Ctrl+Shift+R)"))
        self.btn_rotate_ccw.clicked.connect(lambda: self.rotate_selected(-90.0))

        self.btn_rotate_cw = QPushButton("+90°")
        self.btn_rotate_cw.setIcon(get_icon("rotate-cw", size=16))
        self.btn_rotate_cw.setToolTip(self.tr("Rotate 90° CW (Ctrl+R)"))
        self.btn_rotate_cw.clicked.connect(lambda: self.rotate_selected(90.0))

        r_layout.addWidget(self.btn_rotate_ccw)
        r_layout.addWidget(self.btn_rotate_cw)
        self.grp_rotation.addLayout(r_layout)

        flip_layout = QHBoxLayout()
        flip_layout.setSpacing(6)
        self.btn_flip_h = QPushButton(self.tr("Flip Horiz."))
        self.btn_flip_h.setToolTip(self.tr("Mirror selected object horizontally"))
        self.btn_flip_h.clicked.connect(self.flip_horizontal)
        self.btn_flip_v = QPushButton(self.tr("Flip Vert."))
        self.btn_flip_v.setToolTip(self.tr("Mirror selected object vertically"))
        self.btn_flip_v.clicked.connect(self.flip_vertical)
        flip_layout.addWidget(self.btn_flip_h)
        flip_layout.addWidget(self.btn_flip_v)
        flip_layout.addStretch()
        self.grp_rotation.addLayout(flip_layout)

        self.main_layout.addWidget(self.grp_rotation)

        # 4. Group "Placement"
        self.grp_placement = SectionGroup(self.tr("Placement"))
        p_layout = QHBoxLayout()
        p_layout.setSpacing(6)

        self.btn_center_h = QPushButton(self.tr("Center Horiz."))
        self.btn_center_h.setIcon(get_icon("align-h-center", size=16))
        self.btn_center_h.setToolTip(self.tr("Center horizontally relative to reference frame"))
        self.btn_center_h.clicked.connect(self.align_center_h)

        self.btn_center_v = QPushButton(self.tr("Center Vert."))
        self.btn_center_v.setIcon(get_icon("align-v-center", size=16))
        self.btn_center_v.setToolTip(self.tr("Center vertically relative to reference frame"))
        self.btn_center_v.clicked.connect(self.align_center_v)

        self.btn_center_both = QPushButton(self.tr("Center"))
        self.btn_center_both.setIcon(get_icon("align-center", size=16))
        self.btn_center_both.setToolTip(self.tr("Center on sheet or printable area (both axes)"))
        self.btn_center_both.clicked.connect(self.align_center_both)

        p_layout.addWidget(self.btn_center_h)
        p_layout.addWidget(self.btn_center_v)
        p_layout.addWidget(self.btn_center_both)
        self.grp_placement.addLayout(p_layout)
        self.main_layout.addWidget(self.grp_placement)

        # 5. Group "Scale"
        self.grp_scaling = SectionGroup(self.tr("Scale"))

        # Row 1: Fit to Printable Area
        fit_plottable_row = QHBoxLayout()
        fit_plottable_row.setContentsMargins(0, 0, 0, 0)
        fit_plottable_row.setSpacing(6)

        self.btn_fit_plottable = QPushButton(self.tr("Fit to Printable Area"))
        self.btn_fit_plottable.setIcon(get_icon("fit-plottable", size=16))
        self.btn_fit_plottable.setToolTip(self.tr("Fit proportionally to printable area"))
        self.btn_fit_plottable.clicked.connect(lambda: self.fit_to_plottable())
        fit_plottable_row.addWidget(self.btn_fit_plottable)
        fit_plottable_row.addStretch()
        self.grp_scaling.addLayout(fit_plottable_row)

        # Row 2: Fit to Sheet & Margin
        fit_sheet_row = QHBoxLayout()
        fit_sheet_row.setContentsMargins(0, 0, 0, 0)
        fit_sheet_row.setSpacing(6)

        self.btn_fit_sheet = QPushButton(self.tr("Fit to Sheet"))
        self.btn_fit_sheet.setIcon(get_icon("fit-page", size=16))
        self.btn_fit_sheet.setToolTip(self.tr("Fit proportionally to sheet with margin"))
        self.btn_fit_sheet.clicked.connect(lambda: self.fit_to_sheet())
        self.btn_fit = self.btn_fit_sheet  # Backward compatibility alias
        fit_sheet_row.addWidget(self.btn_fit_sheet)

        lbl_margin = QLabel(self.tr("Margin:"))
        lbl_margin.setStyleSheet("font-weight: 500; color: #4b5563;")
        lbl_margin.setToolTip(self.tr("Safety margin to sheet edges when fitting"))
        fit_sheet_row.addWidget(lbl_margin)

        self.spin_fit_margin = QDoubleSpinBox()
        self.spin_fit_margin.setAlignment(Qt.AlignLeft)
        self.spin_fit_margin.setRange(0.0, 500.0)
        self.spin_fit_margin.setDecimals(1)
        self.spin_fit_margin.setValue(15.0)
        self.spin_fit_margin.setSuffix(" mm")
        self.spin_fit_margin.setKeyboardTracking(False)
        self.spin_fit_margin.setToolTip(self.tr("Safety margin to sheet edges when fitting in mm"))
        fit_sheet_row.addWidget(self.spin_fit_margin)

        fit_sheet_row.addStretch()
        self.grp_scaling.addLayout(fit_sheet_row)

        # Row 3: Zoom
        zoom_row = QHBoxLayout()
        zoom_row.setContentsMargins(0, 0, 0, 0)
        zoom_row.setSpacing(6)

        lbl_zoom = QLabel(self.tr("Zoom:"))
        lbl_zoom.setStyleSheet("font-weight: 500; color: #4b5563;")
        zoom_row.addWidget(lbl_zoom)

        self.spin_obj_scale = QDoubleSpinBox()
        self.spin_obj_scale.setAlignment(Qt.AlignLeft)
        self.spin_obj_scale.setRange(1.0, 5000.0)
        self.spin_obj_scale.setDecimals(1)
        self.spin_obj_scale.setSingleStep(5.0)
        self.spin_obj_scale.setSuffix(" %")
        self.spin_obj_scale.setValue(100.0)
        self.spin_obj_scale.setKeyboardTracking(False)
        self.spin_obj_scale.valueChanged.connect(self._on_scale_spin_changed)
        zoom_row.addWidget(self.spin_obj_scale)

        self.btn_scale_up = QPushButton("+")
        self.btn_scale_up.setFixedWidth(28)
        self.btn_scale_up.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_scale_up.setToolTip(self.tr("Enlarge by 10%"))
        self.btn_scale_up.clicked.connect(lambda: self.scale_relative(1.1))
        zoom_row.addWidget(self.btn_scale_up)

        self.btn_scale_down = QPushButton("-")
        self.btn_scale_down.setFixedWidth(28)
        self.btn_scale_down.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.btn_scale_down.setToolTip(self.tr("Shrink by 10%"))
        self.btn_scale_down.clicked.connect(lambda: self.scale_relative(0.9))
        zoom_row.addWidget(self.btn_scale_down)

        self.btn_original_size = QPushButton(self.tr("Original"))
        self.btn_original_size.setIcon(get_icon("original-size", size=14))
        self.btn_original_size.setToolTip(self.tr("Reset to original size (100% / 1:1)"))
        self.btn_original_size.clicked.connect(self.reset_to_original_size)
        zoom_row.addWidget(self.btn_original_size)

        zoom_row.addStretch()
        self.grp_scaling.addLayout(zoom_row)

        self.main_layout.addWidget(self.grp_scaling)
        self.main_layout.addStretch()

        self._update_font_metrics_sizes()
        self._set_item_controls_enabled(False)

    def _update_font_metrics_sizes(self):
        """Passt Eingabefeld- und Button-Größen dynamisch an die aktuelle Schriftart an."""
        fm = self.fontMetrics()
        spin_mm_w = fm.horizontalAdvance("-8888.8 mm") + fm.height() + 24
        spin_pct_w = fm.horizontalAdvance("0000.0 %") + fm.height() + 20
        margin_w = fm.horizontalAdvance("000.0 mm") + fm.height() + 20

        spin_h = self.spin_obj_w.sizeHint().height()
        lock_size = max(24, spin_h)
        icon_size = max(16, int(lock_size * 0.6))

        for s in (self.spin_pos_x, self.spin_pos_y, self.spin_obj_w, self.spin_obj_h):
            s.setFixedWidth(spin_mm_w)
        self.spin_obj_scale.setFixedWidth(spin_pct_w)
        self.spin_fit_margin.setFixedWidth(margin_w)
        self.spin_rot_angle.setFixedWidth(margin_w)
        self.btn_chain.setFixedSize(lock_size, lock_size)
        self.btn_chain.setIconSize(QSize(icon_size, icon_size))

    def changeEvent(self, event: QEvent):
        """Reagiert auf System- und Anwendungs-Schriftänderungen zur Laufzeit."""
        if event.type() == QEvent.FontChange:
            self._update_font_metrics_sizes()
        super().changeEvent(event)

    @property
    def rot_group(self):
        """Backward compatibility alias for rotation controls."""
        return self.grp_rotation

    def _update_chain_icon(self):
        if self.btn_chain.isChecked():
            self.btn_chain.setIcon(get_icon("lock", size=16))
            self.btn_chain.setToolTip(self.tr("Aspect ratio locked (click to unlock)"))
        else:
            self.btn_chain.setIcon(get_icon("lock-open", size=16))
            self.btn_chain.setToolTip(self.tr("Aspect ratio unlocked (click to lock)"))

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
        self.spin_rot_angle.setEnabled(enabled)
        self.btn_rotate_ccw.setEnabled(enabled)
        self.btn_rotate_cw.setEnabled(enabled)
        self.btn_flip_h.setEnabled(enabled)
        self.btn_flip_v.setEnabled(enabled)
        self.btn_center_h.setEnabled(enabled)
        self.btn_center_v.setEnabled(enabled)
        self.btn_center_both.setEnabled(enabled)
        self.btn_fit_plottable.setEnabled(enabled)
        self.btn_fit_sheet.setEnabled(enabled)
        self.btn_fit.setEnabled(enabled)
        self.spin_fit_margin.setEnabled(enabled)
        self.btn_original_size.setEnabled(enabled)

    def _get_unlocked_items(self) -> list[ImportItem]:
        items = self.selected_items if self.selected_items else ([self.active_item] if self.active_item else [])
        return [it for it in items if it is not None and not it.locked and it.original_bounds is not None]

    def _get_selection_bounds(self, items: Optional[list[ImportItem]] = None) -> Optional[BoundingBox]:
        targets = items if items is not None else self._get_unlocked_items()
        return get_combined_bounds(targets)

    def set_selected_items(self, items: list[ImportItem]):
        self.selected_items = list(items)
        self.active_item = items[0] if items else None
        if not items:
            self.lbl_item_name.setText(self.tr("No object selected"))
            self.lbl_locked_badge.setVisible(False)
            self._set_item_controls_enabled(False)
            return

        if len(items) == 1:
            self.lbl_item_name.setText(items[0].name)
        else:
            self.lbl_item_name.setText(self.tr("%1 objects selected").replace("%1", str(len(items))))

        unlocked = self._get_unlocked_items()
        if not unlocked:
            self.lbl_locked_badge.setText(self.tr("🔒 Locked"))
            self.lbl_locked_badge.setVisible(True)
            self._set_item_controls_enabled(False)
        else:
            if len(unlocked) < len(items):
                self.lbl_locked_badge.setText(self.tr("🔒 %1 locked").replace("%1", str(len(items) - len(unlocked))))
                self.lbl_locked_badge.setVisible(True)
            else:
                self.lbl_locked_badge.setVisible(False)
            self._set_item_controls_enabled(True)
        self.refresh_item_fields()

    def set_active_item(self, item: Optional[ImportItem]):
        self.set_selected_items([item] if item is not None else [])

    def refresh_item_fields(self):
        if not self.active_item or not self.active_item.original_bounds:
            return
        if self._updating_fields:
            return

        self._updating_fields = True
        try:
            targets = self.selected_items if len(self.selected_items) > 1 else [self.active_item]
            cb = self._get_selection_bounds(targets)
            if not cb:
                return

            self.spin_obj_w.setValue(cb.width)
            self.spin_obj_h.setValue(cb.height)
            self.spin_obj_scale.setValue(self.active_item.scale_percent)
            self.spin_rot_angle.setValue(self.active_item.rotation_degrees)

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
    def _apply_multi_transforms(
        self,
        changes: list[tuple[ImportItem, AffineTransform, AffineTransform]],
        text: str,
        command_id: int = -1,
    ):
        if not changes:
            return
        if len(changes) == 1:
            it, old_t, new_t = changes[0]
            if self.undo_stack:
                cmd = TransformItemCommand(
                    it, old_t, new_t, self._on_transform_applied, text=text, command_id=command_id
                )
                self.undo_stack.push(cmd)
            else:
                it.transform = copy.deepcopy(new_t)
                self._on_transform_applied()
            return

        if self.undo_stack:
            self.undo_stack.beginMacro(text)
            try:
                for it, old_t, new_t in changes:
                    cmd = TransformItemCommand(it, old_t, new_t, self._on_transform_applied, text=text)
                    self.undo_stack.push(cmd)
            finally:
                self.undo_stack.endMacro()
        else:
            for it, _, new_t in changes:
                it.transform = copy.deepcopy(new_t)
            self._on_transform_applied()

    def _on_transform_applied(self):
        self.refresh_item_fields()
        self.item_transformed.emit()

    def _on_rot_angle_spin_changed(self, target_angle_deg: float):
        if self._updating_fields:
            return
        unlocked = self._get_unlocked_items()
        if not unlocked or not self.active_item:
            return
        delta = target_angle_deg - self.active_item.rotation_degrees
        if abs(delta) < 1e-4:
            return
        self.rotate_selected(delta, command_id=CMD_ID_ROT)

    def rotate_selected(self, angle_degrees: float, command_id: int = -1):
        """Rotate unlocked selected item(s) around their visual center."""
        changes = compute_rotation_transforms(self._get_unlocked_items(), angle_degrees)
        if not changes:
            return
        dir_str = self.tr("CW") if angle_degrees > 0 else self.tr("CCW")
        text = self.tr("Rotate object (%1° %2)").replace("%1", f"{angle_degrees:.1f}").replace("%2", dir_str)
        self._apply_multi_transforms(changes, text, command_id=command_id)

    def flip_horizontal(self):
        """Mirror unlocked selected item(s) horizontally around their visual center."""
        self._apply_scene_scale(-1.0, 1.0, text=self.tr("Flip object horizontally"))

    def flip_vertical(self):
        """Mirror unlocked selected item(s) vertically around their visual center."""
        self._apply_scene_scale(1.0, -1.0, text=self.tr("Flip object vertically"))

    def _apply_scene_scale(
        self,
        factor_x: float,
        factor_y: float,
        text: Optional[str] = None,
        command_id: int = -1,
    ):
        """Scale unlocked selected item(s) around center in scene coordinates, preserving rotation."""
        changes = compute_scene_scale_transforms(self._get_unlocked_items(), factor_x, factor_y)
        self._apply_multi_transforms(
            changes, text or self.tr("Scale object"), command_id=command_id
        )

    def _on_obj_w_changed(self, new_w: float):
        if self._updating_fields:
            return
        unlocked = self._get_unlocked_items()
        cb = self._get_selection_bounds(unlocked)
        if cb is None or cb.width <= 0:
            return
        factor_x = new_w / cb.width
        factor_y = factor_x if self.btn_chain.isChecked() else 1.0
        self._apply_scene_scale(factor_x, factor_y, command_id=CMD_ID_SIZE)

    def _on_obj_h_changed(self, new_h: float):
        if self._updating_fields:
            return
        unlocked = self._get_unlocked_items()
        cb = self._get_selection_bounds(unlocked)
        if cb is None or cb.height <= 0:
            return
        factor_y = new_h / cb.height
        factor_x = factor_y if self.btn_chain.isChecked() else 1.0
        self._apply_scene_scale(factor_x, factor_y, command_id=CMD_ID_SIZE)

    def _on_scale_spin_changed(self, pct: float):
        if self._updating_fields or not self.active_item or self.active_item.locked or not self.active_item.original_bounds:
            return
        target_scale = max(0.01, pct / 100.0)
        cur_scale = math.hypot(self.active_item.transform.a, self.active_item.transform.b)
        if cur_scale <= 1e-6:
            return
        factor = target_scale / cur_scale
        self._apply_scene_scale(factor, factor, command_id=CMD_ID_SCALE)

    def scale_relative(self, factor: float):
        self._apply_scene_scale(factor, factor)

    def reset_to_original_size(self):
        """Reset scale to 1.0 (true 1:1 original mm size from source file), preserving rotation."""
        changes = compute_reset_scale_transforms(self._get_unlocked_items())
        self._apply_multi_transforms(changes, self.tr("Original size (1:1)"))

    def fit_to_box(self, target_box: BoundingBox, action_name: str, margin_mm: float = 0.0):
        changes = compute_fit_to_box_transforms(self._get_unlocked_items(), target_box, margin_mm)
        self._apply_multi_transforms(changes, action_name)

    def fit_to_plottable(self, margin_mm: float = 0.0):
        self.fit_to_box(self.doc.page.plottable_box, self.tr("Fit to Printable Area"), margin_mm)

    def fit_to_sheet(self, margin_mm: Optional[float] = None):
        if margin_mm is None:
            margin_mm = self.spin_fit_margin.value()
        self.fit_to_box(self.doc.page.sheet_box, self.tr("Fit to Sheet"), margin_mm)

    def fit_to_page(self, margin_mm: Optional[float] = None):
        """Backward compatibility alias for fit_to_sheet."""
        self.fit_to_sheet(margin_mm)

    # --- Position and Alignment ---
    def _on_pos_mm_changed(self):
        if self._updating_fields:
            return
        changes = compute_position_transforms(
            self._get_unlocked_items(),
            self._get_target_box(),
            self.spin_pos_x.value(),
            self.spin_pos_y.value(),
        )
        self._apply_multi_transforms(
            changes, self.tr("Change position (mm)"), command_id=CMD_ID_POS
        )

    def align_center_h(self):
        changes = compute_align_center_transforms(
            self._get_unlocked_items(), self._get_target_box(), horizontal=True, vertical=False
        )
        self._apply_multi_transforms(changes, self.tr("Center horizontally"))

    def align_center_v(self):
        changes = compute_align_center_transforms(
            self._get_unlocked_items(), self._get_target_box(), horizontal=False, vertical=True
        )
        self._apply_multi_transforms(changes, self.tr("Center vertically"))

    def align_center_both(self):
        changes = compute_align_center_transforms(
            self._get_unlocked_items(), self._get_target_box(), horizontal=True, vertical=True
        )
        self._apply_multi_transforms(changes, self.tr("Center on sheet"))

