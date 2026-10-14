"""Pen management dock widget with WYSIWYG colors, stroke widths and dynamic remapping."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QDoubleSpinBox, QColorDialog, QLabel, QGroupBox, QHeaderView
)
from ..core.document import Document, LogicalPen


class PenDockWidget(QDockWidget):
    """
    Dock widget managing pens 1 to 8:
    - Display color picker
    - Physical stroke width in mm
    - Dynamic remapping (merging pens / monochrome)
    - Quick assignment to selected canvas objects
    """
    pen_changed = Signal()
    assign_selection_to_pen = Signal(int)

    def __init__(self, doc: Document, parent=None):
        super().__init__("Stifte & Werkzeuge", parent)
        self.doc = doc

        self.container = QWidget(self)
        self.setWidget(self.container)
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(8)

        # Quick Actions
        qa_group = QGroupBox("Schnell-Aktionen")
        qa_layout = QHBoxLayout(qa_group)
        self.btn_monochrome = QPushButton("Alle auf Stift 1 (Monochrom)")
        self.btn_monochrome.clicked.connect(self._on_monochrome_clicked)
        self.btn_reset_remap = QPushButton("1:1 Wiederherstellen")
        self.btn_reset_remap.clicked.connect(self._on_reset_remap_clicked)
        qa_layout.addWidget(self.btn_monochrome)
        qa_layout.addWidget(self.btn_reset_remap)
        self.layout.addWidget(qa_group)

        # Table of pens
        self.table = QTableWidget(len(self.doc.pens), 5)
        self.table.setHorizontalHeaderLabels(["Stift", "Farbe", "Breite (mm)", "Zuweisung", "Plotten"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.NoSelection)

        self.layout.addWidget(self.table)

        # Quick assignment buttons for selected items
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

        self.refresh_table()

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
            # Set current index
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

    def _on_monochrome_clicked(self):
        self.doc.remap_all_to_pen(1)
        self.refresh_table()
        self.pen_changed.emit()

    def _on_reset_remap_clicked(self):
        self.doc.reset_remapping()
        self.refresh_table()
        self.pen_changed.emit()
