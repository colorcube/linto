"""Pen management dock widget with WYSIWYG colors, stroke widths, presets and dynamic remapping."""

from __future__ import annotations
import copy
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QDoubleSpinBox, QColorDialog, QLabel, QGroupBox, QHeaderView,
    QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
    QInputDialog, QMessageBox, QFileDialog
)
from ..core.document import Document, LogicalPen
from ..core.pen_presets import (
    PenPreset,
    get_builtin_presets,
    get_user_presets_dir,
    list_user_presets,
    save_user_preset,
    load_preset_json,
    remap_document_to_preset,
)
from .commands import ApplyPresetCommand, PenRemapCommand, ModifyPenPropertyCommand


class PenPresetDialog(QDialog):
    """Dialog prompting the user how existing drawing paths should be mapped to the new preset."""
    def __init__(self, preset_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Apply Pen Preset"))
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        prompt_text = self.tr("<b>Apply preset:</b> %1<br><br>How should existing drawing objects be adjusted?").replace("%1", preset_name)
        lbl = QLabel(prompt_text)
        layout.addWidget(lbl)

        self.rb_slot = QRadioButton(self.tr("Keep pen slots 1..8 (adopt preset properties)"))
        self.rb_slot.setToolTip(self.tr("Pen 1 stays Pen 1; adopts the new color, stroke width, and speed of the preset."))
        self.rb_slot.setChecked(True)

        self.rb_delta_e = QRadioButton(self.tr("Automatically reassign colors (Delta E)"))
        self.rb_delta_e.setToolTip(self.tr("Finds the closest color match in the new set for all paths."))

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_slot)
        self.btn_group.addButton(self.rb_delta_e)

        layout.addWidget(self.rb_slot)
        layout.addWidget(self.rb_delta_e)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.button(QDialogButtonBox.Ok).setText(self.tr("Apply Preset"))
        button_box.button(QDialogButtonBox.Cancel).setText(self.tr("Cancel"))
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    @property
    def selected_strategy(self) -> str:
        return "delta_e" if self.rb_delta_e.isChecked() else "slot"


class PenDockWidget(QDockWidget):
    """
    Dock widget managing pens 1 to 8:
    - Display color picker
    - Physical stroke width in mm
    - Pen speed (cm/s) and force (g)
    - Dynamic remapping (merging pens / monochrome)
    - Stift Presets (Fineliner, Posca, Isograph, Ballpoint, Custom)
    - Quick assignment to selected canvas objects
    """
    pen_changed = Signal()
    assign_selection_to_pen = Signal(int)

    def __init__(self, doc: Document, parent=None):
        super().__init__(self.tr("Pens"), parent)
        self.setObjectName("PenDockWidget")
        self.doc = doc
        self.undo_stack: Optional[QUndoStack] = None
        self.user_presets: List[PenPreset] = []

        self.container = QWidget(self)
        self.setWidget(self.container)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        # --- Section 1: Presets ---
        preset_group = QGroupBox(self.tr("Pen Presets (Sets)"))
        p_layout = QVBoxLayout(preset_group)

        row_p = QHBoxLayout()
        self.combo_presets = QComboBox()
        row_p.addWidget(self.combo_presets, stretch=1)

        self.btn_apply_preset = QPushButton(self.tr("Apply"))
        self.btn_apply_preset.clicked.connect(self._on_apply_preset_clicked)
        row_p.addWidget(self.btn_apply_preset)

        p_layout.addLayout(row_p)

        row_p2 = QHBoxLayout()
        self.btn_save_preset = QPushButton(self.tr("Save as Preset..."))
        self.btn_save_preset.clicked.connect(self._on_save_preset_clicked)
        self.btn_load_preset = QPushButton(self.tr("Load from File..."))
        self.btn_load_preset.clicked.connect(self._on_load_preset_clicked)
        row_p2.addWidget(self.btn_save_preset)
        row_p2.addWidget(self.btn_load_preset)
        p_layout.addLayout(row_p2)

        self.layout.addWidget(preset_group)

        # --- Section 2: Quick Actions ---
        qa_group = QGroupBox(self.tr("Quick Actions"))
        qa_layout = QHBoxLayout(qa_group)
        self.btn_monochrome = QPushButton(self.tr("All to Pen 1 (Monochrome)"))
        self.btn_monochrome.clicked.connect(self._on_monochrome_clicked)
        self.btn_reset_remap = QPushButton(self.tr("Reset 1:1 Mapping"))
        self.btn_reset_remap.clicked.connect(self._on_reset_remap_clicked)
        qa_layout.addWidget(self.btn_monochrome)
        qa_layout.addWidget(self.btn_reset_remap)
        self.layout.addWidget(qa_group)

        # --- Section 3: Table of Pens ---
        self.table = QTableWidget(len(self.doc.pens), 7)
        self.table.setHorizontalHeaderLabels([
            self.tr("Pen"),
            self.tr("Color"),
            self.tr("Width"),
            self.tr("Speed"),
            self.tr("Force"),
            self.tr("Mapping"),
            self.tr("Active")
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.itemChanged.connect(self._on_table_item_changed)

        self.layout.addWidget(self.table)

        # --- Section 4: Quick assignment buttons for selected items ---
        assign_group = QGroupBox(self.tr("Assign selected object to:"))
        assign_layout = QHBoxLayout(assign_group)
        assign_layout.setSpacing(4)
        for pen_id in range(1, 9):
            btn = QPushButton(str(pen_id))
            btn.setFixedWidth(28)
            btn.setToolTip(self.tr("Assign selected object to Pen %1").replace("%1", str(pen_id)))
            btn.clicked.connect(lambda checked=False, pid=pen_id: self.assign_selection_to_pen.emit(pid))
            assign_layout.addWidget(btn)
        self.layout.addWidget(assign_group)

        self._populate_presets()
        self.refresh_table()

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def _get_user_presets_dir(self) -> str:
        return get_user_presets_dir()

    def _populate_presets(self):
        self.combo_presets.clear()
        for p in get_builtin_presets():
            self.combo_presets.addItem(f"★ {p.name}", p)
        for preset in list_user_presets():
            self.combo_presets.addItem(f"📁 {preset.name}", preset)

    def refresh_table(self):
        self.table.blockSignals(True)
        for row, pen in enumerate(self.doc.pens):
            # Col 0: Pen ID & Name
            item_name = self.table.item(row, 0)
            if item_name is None:
                item_name = QTableWidgetItem(f"SP{pen.pen_id}")
                item_name.setTextAlignment(Qt.AlignCenter)
                item_name.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(row, 0, item_name)
            else:
                item_name.setText(f"SP{pen.pen_id}")

            # Col 1: Color swatch button
            btn_col = self.table.cellWidget(row, 1)
            if btn_col is None:
                btn_col = QPushButton()
                btn_col.setFixedSize(26, 20)
                btn_col.clicked.connect(lambda checked=False, pid=pen.pen_id: self._choose_color(self.doc.get_pen(pid)))
                self.table.setCellWidget(row, 1, btn_col)
            btn_col.setStyleSheet(f"background-color: {pen.color_hex}; border: 1px solid #555; border-radius: 3px;")

            # Col 2: Width spinbox (mm)
            spin_w = self.table.cellWidget(row, 2)
            if spin_w is None:
                spin_w = QDoubleSpinBox()
                spin_w.setRange(0.05, 5.0)
                spin_w.setSingleStep(0.05)
                spin_w.setDecimals(2)
                spin_w.setSuffix(" mm")
                spin_w.setKeyboardTracking(False)
                spin_w.valueChanged.connect(lambda val, pid=pen.pen_id: self._update_pen_width(self.doc.get_pen(pid), val))
                self.table.setCellWidget(row, 2, spin_w)
            spin_w.blockSignals(True)
            spin_w.setValue(pen.width_mm)
            spin_w.blockSignals(False)

            # Col 3: Speed spinbox (cm/s)
            spin_speed = self.table.cellWidget(row, 3)
            if spin_speed is None:
                spin_speed = QDoubleSpinBox()
                spin_speed.setRange(1.0, 100.0)
                spin_speed.setSingleStep(5.0)
                spin_speed.setDecimals(0)
                spin_speed.setSuffix(" cm/s")
                spin_speed.setKeyboardTracking(False)
                spin_speed.setToolTip(self.tr("Drawing speed (VS in cm/s)"))
                spin_speed.valueChanged.connect(lambda val, pid=pen.pen_id: self._update_pen_speed(self.doc.get_pen(pid), val))
                self.table.setCellWidget(row, 3, spin_speed)
            spin_speed.blockSignals(True)
            spin_speed.setValue(pen.speed_cm_s)
            spin_speed.blockSignals(False)

            # Col 4: Force spinbox (g)
            spin_force = self.table.cellWidget(row, 4)
            if spin_force is None:
                spin_force = QDoubleSpinBox()
                spin_force.setRange(1.0, 500.0)
                spin_force.setSingleStep(5.0)
                spin_force.setDecimals(0)
                spin_force.setSuffix(" g")
                spin_force.setKeyboardTracking(False)
                spin_force.setToolTip(self.tr("Pen force (FS / grams)"))
                spin_force.valueChanged.connect(lambda val, pid=pen.pen_id: self._update_pen_force(self.doc.get_pen(pid), val))
                self.table.setCellWidget(row, 4, spin_force)
            spin_force.blockSignals(True)
            spin_force.setValue(pen.force_g)
            spin_force.blockSignals(False)

            # Col 5: Remap combobox
            combo_remap = self.table.cellWidget(row, 5)
            if combo_remap is None:
                combo_remap = QComboBox()
                combo_remap.addItem(f"-> SP{pen.pen_id} " + self.tr("(Default)"), None)
                for target_id in range(1, 9):
                    if target_id != pen.pen_id:
                        combo_remap.addItem(self.tr("-> remap to SP%1").replace("%1", str(target_id)), target_id)
                combo_remap.currentIndexChanged.connect(lambda idx, cb=combo_remap, pid=pen.pen_id: self._update_remap(self.doc.get_pen(pid), cb.currentData()))
                self.table.setCellWidget(row, 5, combo_remap)
            combo_remap.blockSignals(True)
            if pen.mapped_to is not None:
                idx = combo_remap.findData(pen.mapped_to)
                if idx >= 0:
                    combo_remap.setCurrentIndex(idx)
            else:
                combo_remap.setCurrentIndex(0)
            combo_remap.blockSignals(False)

            # Col 6: Enabled checkbox
            chk_item = self.table.item(row, 6)
            if chk_item is None:
                chk_item = QTableWidgetItem()
                chk_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                self.table.setItem(row, 6, chk_item)
            chk_item.setCheckState(Qt.Checked if pen.enabled else Qt.Unchecked)

        self.table.blockSignals(False)

    def _push_pen_change(self, pen: LogicalPen, attr_name: str, old_val: Any, new_val: Any, text: str):
        if old_val == new_val:
            return
        if self.undo_stack:
            cmd = ModifyPenPropertyCommand(
                self.doc, pen.pen_id, attr_name, old_val, new_val, self._on_preset_cmd_updated, text=text
            )
            self.undo_stack.push(cmd)
        else:
            setattr(pen, attr_name, new_val)
            self.refresh_table()
            self.pen_changed.emit()

    def _choose_color(self, pen: LogicalPen):
        col = QColorDialog.getColor(QColor(pen.color_hex), self, self.tr("Select color for Pen %1").replace("%1", str(pen.pen_id)))
        if col.isValid():
            self._push_pen_change(
                pen, "color_hex", pen.color_hex, col.name(), self.tr("Change color of Pen %1").replace("%1", str(pen.pen_id))
            )

    def _update_pen_width(self, pen: LogicalPen, val: float):
        if abs(pen.width_mm - val) < 1e-6:
            return
        self._push_pen_change(pen, "width_mm", pen.width_mm, val, self.tr("Change width of SP%1").replace("%1", str(pen.pen_id)))

    def _update_pen_speed(self, pen: LogicalPen, val: float):
        if abs(pen.speed_cm_s - val) < 1e-6:
            return
        self._push_pen_change(pen, "speed_cm_s", pen.speed_cm_s, val, self.tr("Change speed of SP%1").replace("%1", str(pen.pen_id)))

    def _update_pen_force(self, pen: LogicalPen, val: float):
        if abs(pen.force_g - val) < 1e-6:
            return
        self._push_pen_change(pen, "force_g", pen.force_g, val, self.tr("Change force of SP%1").replace("%1", str(pen.pen_id)))

    def _update_remap(self, pen: LogicalPen, target_id: Optional[int]):
        self._push_pen_change(
            pen, "mapped_to", pen.mapped_to, target_id, self.tr("Change mapping of SP%1").replace("%1", str(pen.pen_id))
        )

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 6:
            row = item.row()
            if 0 <= row < len(self.doc.pens):
                pen = self.doc.pens[row]
                new_enabled = (item.checkState() == Qt.Checked)
                self._push_pen_change(
                    pen, "enabled", pen.enabled, new_enabled, self.tr("Enable/disable Pen %1").replace("%1", str(pen.pen_id))
                )

    def _apply_preset_with_dialog(self, preset: PenPreset, always_ask_strategy: bool = False):
        strategy = "slot"
        if always_ask_strategy or len(self.doc.items) > 0:
            dlg = PenPresetDialog(preset.name, self)
            if dlg.exec() != QDialog.Accepted:
                return
            strategy = dlg.selected_strategy

        old_pens = copy.deepcopy(self.doc.pens)
        old_assignments = [(p, p.pen_id) for it in self.doc.items for p in it.paths]

        remap_document_to_preset(self.doc, preset, strategy=strategy)

        if self.undo_stack:
            cmd = ApplyPresetCommand(
                self.doc,
                old_pens,
                self.doc.pens,
                old_assignments,
                self._on_preset_cmd_updated,
                text=self.tr("Apply preset '%1'").replace("%1", preset.name),
            )
            self.undo_stack.push(cmd)
        else:
            self._on_preset_cmd_updated()

    def _on_apply_preset_clicked(self):
        preset: Optional[PenPreset] = self.combo_presets.currentData()
        if not preset:
            return
        self._apply_preset_with_dialog(preset, always_ask_strategy=False)

    def _on_preset_cmd_updated(self):
        self.refresh_table()
        self.pen_changed.emit()

    def _on_save_preset_clicked(self):
        name, ok = QInputDialog.getText(self, self.tr("Save Pen Preset"), self.tr("Preset name:"))
        if not ok or not name.strip():
            return
        clean_name = name.strip()

        preset = PenPreset(
            name=clean_name,
            description=self.tr("Custom pen set"),
            pens=copy.deepcopy(self.doc.pens),
        )
        try:
            save_user_preset(preset)
            self._populate_presets()
            idx = self.combo_presets.findText(f"📁 {clean_name}")
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)
            QMessageBox.information(self, self.tr("Preset Saved"), self.tr("Preset '%1' has been saved.").replace("%1", clean_name))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Save Error"), self.tr("Failed to save preset:\n%1").replace("%1", str(e)))

    def _on_load_preset_clicked(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, self.tr("Load Pen Preset from JSON"), "", self.tr("JSON Files (*.json);;All Files (*)")
        )
        if fpath:
            try:
                preset = load_preset_json(fpath)
                self._apply_preset_with_dialog(preset, always_ask_strategy=True)
            except Exception as e:
                QMessageBox.critical(self, self.tr("Load Error"), self.tr("Failed to load preset file:\n%1").replace("%1", str(e)))

    def _on_monochrome_clicked(self):
        old_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        self.doc.remap_all_to_pen(1)
        new_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        if self.undo_stack:
            cmd = PenRemapCommand(self.doc, old_mappings, new_mappings, self._on_preset_cmd_updated, text=self.tr("All to Pen 1 (Monochrome)"))
            self.undo_stack.push(cmd)
        else:
            self._on_preset_cmd_updated()

    def _on_reset_remap_clicked(self):
        old_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        self.doc.reset_remapping()
        new_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        if self.undo_stack:
            cmd = PenRemapCommand(self.doc, old_mappings, new_mappings, self._on_preset_cmd_updated, text=self.tr("Reset 1:1 Mapping"))
            self.undo_stack.push(cmd)
        else:
            self._on_preset_cmd_updated()
