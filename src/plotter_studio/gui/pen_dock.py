"""Pen management dock widget with WYSIWYG colors, stroke widths, presets and dynamic remapping."""

from __future__ import annotations
import os
import copy
from typing import Optional, List, Dict, Any
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
    PenPreset, BUILTIN_PRESETS, get_builtin_presets,
    save_preset_json, load_preset_json, remap_document_to_preset
)
from .commands import ApplyPresetCommand, PenRemapCommand


class PenPresetDialog(QDialog):
    """Dialog prompting the user how existing drawing paths should be mapped to the new preset."""
    def __init__(self, preset_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stift-Preset anwenden")
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        lbl = QLabel(f"<b>Preset anwenden:</b> {preset_name}<br><br>Wie sollen vorhandene Objekte angepasst werden?")
        layout.addWidget(lbl)

        self.rb_slot = QRadioButton("Stifteigenschaften übernehmen (Slot 1..8 beibehalten)")
        self.rb_slot.setToolTip("Stift 1 bleibt Stift 1; übernimmt die neue Farbe, Minenbreite und Geschwindigkeit des Presets.")
        self.rb_slot.setChecked(True)

        self.rb_delta_e = QRadioButton("Farben automatisch neu zuweisen (Delta E)")
        self.rb_delta_e.setToolTip("Berechnet für alle Pfade den farblich ähnlichsten aktiven Stift im neuen Set.")

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.rb_slot)
        self.btn_group.addButton(self.rb_delta_e)

        layout.addWidget(self.rb_slot)
        layout.addWidget(self.rb_delta_e)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        button_box.button(QDialogButtonBox.Ok).setText("Preset anwenden")
        button_box.button(QDialogButtonBox.Cancel).setText("Abbrechen")
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
    - Dynamic remapping (merging pens / monochrome)
    - Stift Presets (Fineliner, Posca, Isograph, Ballpoint, Custom)
    - Quick assignment to selected canvas objects
    """
    pen_changed = Signal()
    assign_selection_to_pen = Signal(int)

    def __init__(self, doc: Document, parent=None):
        super().__init__("Stifte", parent)
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
        preset_group = QGroupBox("Stift-Presets (Sets)")
        p_layout = QVBoxLayout(preset_group)

        row_p = QHBoxLayout()
        self.combo_presets = QComboBox()
        row_p.addWidget(self.combo_presets, stretch=1)

        self.btn_apply_preset = QPushButton("Anwenden")
        self.btn_apply_preset.clicked.connect(self._on_apply_preset_clicked)
        row_p.addWidget(self.btn_apply_preset)

        p_layout.addLayout(row_p)

        row_p2 = QHBoxLayout()
        self.btn_save_preset = QPushButton("Als Preset speichern...")
        self.btn_save_preset.clicked.connect(self._on_save_preset_clicked)
        self.btn_load_preset = QPushButton("Aus Datei laden...")
        self.btn_load_preset.clicked.connect(self._on_load_preset_clicked)
        row_p2.addWidget(self.btn_save_preset)
        row_p2.addWidget(self.btn_load_preset)
        p_layout.addLayout(row_p2)

        self.layout.addWidget(preset_group)

        # --- Section 2: Quick Actions ---
        qa_group = QGroupBox("Schnell-Aktionen")
        qa_layout = QHBoxLayout(qa_group)
        self.btn_monochrome = QPushButton("Alle auf Stift 1 (Monochrom)")
        self.btn_monochrome.clicked.connect(self._on_monochrome_clicked)
        self.btn_reset_remap = QPushButton("1:1 Wiederherstellen")
        self.btn_reset_remap.clicked.connect(self._on_reset_remap_clicked)
        qa_layout.addWidget(self.btn_monochrome)
        qa_layout.addWidget(self.btn_reset_remap)
        self.layout.addWidget(qa_group)

        # --- Section 3: Table of Pens ---
        self.table = QTableWidget(len(self.doc.pens), 5)
        self.table.setHorizontalHeaderLabels(["Stift", "Farbe", "Breite", "Zuweisung", "Aktiv"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)

        self.layout.addWidget(self.table)

        # --- Section 4: Quick assignment buttons for selected items ---
        assign_group = QGroupBox("Ausgewähltes Objekt zuweisen an:")
        assign_layout = QHBoxLayout(assign_group)
        assign_layout.setSpacing(4)
        for pen_id in range(1, 9):
            btn = QPushButton(str(pen_id))
            btn.setFixedWidth(28)
            btn.setToolTip(f"Ausgewähltes Objekt Stift {pen_id} zuweisen")
            btn.clicked.connect(lambda checked=False, pid=pen_id: self.assign_selection_to_pen.emit(pid))
            assign_layout.addWidget(btn)
        self.layout.addWidget(assign_group)

        self._populate_presets()
        self.refresh_table()

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def _get_user_presets_dir(self) -> str:
        d = os.environ.get("PLOTTER_STUDIO_CONFIG_DIR")
        if not d:
            d = os.path.expanduser("~/.config/plotter-studio/pens")
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        return d

    def _populate_presets(self):
        self.combo_presets.clear()
        # Built-in presets
        for p in get_builtin_presets():
            self.combo_presets.addItem(f"★ {p.name}", p)

        # Custom presets from config dir
        pdir = self._get_user_presets_dir()
        if os.path.exists(pdir):
            for fname in sorted(os.listdir(pdir)):
                if fname.endswith(".json"):
                    fpath = os.path.join(pdir, fname)
                    try:
                        preset = load_preset_json(fpath)
                        self.combo_presets.addItem(f"📁 {preset.name}", preset)
                    except Exception:
                        pass

    def refresh_table(self):
        self.table.blockSignals(True)
        for row, pen in enumerate(self.doc.pens):
            # Col 0: Pen ID & Name
            item_name = QTableWidgetItem(f"SP{pen.pen_id}")
            item_name.setTextAlignment(Qt.AlignCenter)
            item_name.setFlags(Qt.ItemIsEnabled)
            self.table.setItem(row, 0, item_name)

            # Col 1: Color swatch button
            btn_col = QPushButton()
            btn_col.setFixedSize(26, 20)
            btn_col.setStyleSheet(f"background-color: {pen.color_hex}; border: 1px solid #555; border-radius: 3px;")
            btn_col.clicked.connect(lambda checked=False, p=pen: self._choose_color(p))
            self.table.setCellWidget(row, 1, btn_col)

            # Col 2: Width spinbox (mm)
            spin_w = QDoubleSpinBox()
            spin_w.setRange(0.05, 5.0)
            spin_w.setSingleStep(0.05)
            spin_w.setDecimals(2)
            spin_w.setValue(pen.width_mm)
            spin_w.setSuffix(" mm")
            spin_w.valueChanged.connect(lambda val, p=pen: self._update_pen_width(p, val))
            self.table.setCellWidget(row, 2, spin_w)

            # Col 3: Remap combobox
            combo_remap = QComboBox()
            combo_remap.addItem(f"-> SP{pen.pen_id} (Standard)", None)
            for target_id in range(1, 9):
                if target_id != pen.pen_id:
                    combo_remap.addItem(f"-> auf SP{target_id} umleiten", target_id)
            if pen.mapped_to is not None:
                idx = combo_remap.findData(pen.mapped_to)
                if idx >= 0:
                    combo_remap.setCurrentIndex(idx)
            combo_remap.currentIndexChanged.connect(lambda idx, cb=combo_remap, p=pen: self._update_remap(p, cb.currentData()))
            self.table.setCellWidget(row, 3, combo_remap)

            # Col 4: Enabled checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            chk_item.setCheckState(Qt.Checked if pen.enabled else Qt.Unchecked)
            self.table.setItem(row, 4, chk_item)

        self.table.itemChanged.connect(self._on_table_item_changed)
        self.table.blockSignals(False)

    def _choose_color(self, pen: LogicalPen):
        col = QColorDialog.getColor(QColor(pen.color_hex), self, f"Farbe für Stift {pen.pen_id} wählen")
        if col.isValid():
            pen.color_hex = col.name()
            self.refresh_table()
            self.pen_changed.emit()

    def _update_pen_width(self, pen: LogicalPen, val: float):
        pen.width_mm = val
        self.pen_changed.emit()

    def _update_remap(self, pen: LogicalPen, target_id: Optional[int]):
        pen.mapped_to = target_id
        self.pen_changed.emit()

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if item.column() == 4:
            row = item.row()
            if 0 <= row < len(self.doc.pens):
                self.doc.pens[row].enabled = (item.checkState() == Qt.Checked)
                self.pen_changed.emit()

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
                text=f"Preset '{preset.name}' anwenden",
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
        name, ok = QInputDialog.getText(self, "Stift-Preset speichern", "Name des Presets:")
        if not ok or not name.strip():
            return
        clean_name = name.strip()
        safe_fname = "".join(c for c in clean_name if c.isalnum() or c in " -_").strip()
        fpath = os.path.join(self._get_user_presets_dir(), f"{safe_fname}.json")

        preset = PenPreset(
            name=clean_name,
            description="Benutzerdefiniertes Stift-Set",
            pens=copy.deepcopy(self.doc.pens),
        )
        try:
            save_preset_json(preset, fpath)
            self._populate_presets()
            idx = self.combo_presets.findText(f"📁 {clean_name}")
            if idx >= 0:
                self.combo_presets.setCurrentIndex(idx)
            QMessageBox.information(self, "Preset gespeichert", f"Preset '{clean_name}' wurde gespeichert.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Speichern", f"Konnte Preset nicht speichern:\n{e}")

    def _on_load_preset_clicked(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Stift-Preset aus JSON laden", "", "JSON Dateien (*.json);;Alle Dateien (*)"
        )
        if fpath:
            try:
                preset = load_preset_json(fpath)
                self._apply_preset_with_dialog(preset, always_ask_strategy=True)
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Laden", f"Konnte Preset-Datei nicht laden:\n{e}")

    def _on_monochrome_clicked(self):
        old_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        self.doc.remap_all_to_pen(1)
        new_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        if self.undo_stack:
            cmd = PenRemapCommand(self.doc, old_mappings, new_mappings, self._on_preset_cmd_updated, text="Alle auf Stift 1 (Monochrom)")
            self.undo_stack.push(cmd)
        else:
            self._on_preset_cmd_updated()

    def _on_reset_remap_clicked(self):
        old_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        self.doc.reset_remapping()
        new_mappings = [(p.pen_id, p.mapped_to) for p in self.doc.pens]
        if self.undo_stack:
            cmd = PenRemapCommand(self.doc, old_mappings, new_mappings, self._on_preset_cmd_updated, text="1:1 Zuweisung wiederherstellen")
            self.undo_stack.push(cmd)
        else:
            self._on_preset_cmd_updated()
