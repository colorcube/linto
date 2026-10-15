"""Object and Layer management dock widget."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QToolButton, QHeaderView,
    QAbstractItemView
)
from .icons import get_icon

if TYPE_CHECKING:
    from ..core.document import Document, ImportItem
    from .canvas import PlotterCanvas


class ObjectDockWidget(QDockWidget):
    """
    Dock widget providing layer & object management:
    - Z-order list (top layer at top of tree)
    - Visibility toggle (eye icon)
    - Lock toggle (lock icon)
    - Inline renaming
    - Toolbar: Import, Duplicate (Ctrl+D), Delete (Del), Move Up/Down
    - Bi-directional selection sync with canvas
    """
    document_modified = Signal()

    def __init__(self, doc: Document, canvas: PlotterCanvas, parent: Optional[QWidget] = None):
        super().__init__("Objekte & Ebenen", parent)
        self.doc = doc
        self.canvas = canvas
        self._updating = False

        self.setObjectName("ObjectDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Tree Widget for Objects/Layers
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["", "", "Objekt"])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.setStyleSheet("QTreeWidget { outline: none; } QTreeWidget::item { outline: none; }")

        header = self.tree.header()
        header.setMinimumSectionSize(24)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.resizeSection(0, 24)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.resizeSection(1, 24)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setStretchLastSection(True)

        h_item = self.tree.headerItem()
        h_item.setIcon(0, get_icon("eye", size=14))
        h_item.setToolTip(0, "Sichtbarkeit umschalten")
        h_item.setIcon(1, get_icon("lock", size=14))
        h_item.setToolTip(1, "Sperren umschalten")

        layout.addWidget(self.tree)

        # Action Toolbar at bottom
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(2)

        self.btn_import = QToolButton(self)
        self.btn_import.setIcon(get_icon("import", size=18))
        self.btn_import.setToolTip("Datei importieren (SVG, HP-GL)")
        self.btn_import.setAutoRaise(True)

        self.btn_dup = QToolButton(self)
        self.btn_dup.setIcon(get_icon("duplicate", size=18))
        self.btn_dup.setToolTip("Ausgewähltes Objekt duplizieren (Strg+D)")
        self.btn_dup.setAutoRaise(True)

        self.btn_del = QToolButton(self)
        self.btn_del.setIcon(get_icon("delete", size=18))
        self.btn_del.setToolTip("Ausgewähltes Objekt entfernen (Entf)")
        self.btn_del.setAutoRaise(True)

        self.btn_up = QToolButton(self)
        self.btn_up.setIcon(get_icon("arrow-up", size=18))
        self.btn_up.setToolTip("Ebene nach oben verschieben (Vordergrund)")
        self.btn_up.setAutoRaise(True)

        self.btn_down = QToolButton(self)
        self.btn_down.setIcon(get_icon("arrow-down", size=18))
        self.btn_down.setToolTip("Ebene nach unten verschieben (Hintergrund)")
        self.btn_down.setAutoRaise(True)

        btn_bar.addWidget(self.btn_import)
        btn_bar.addWidget(self.btn_dup)
        btn_bar.addWidget(self.btn_del)
        btn_bar.addStretch()
        btn_bar.addWidget(self.btn_up)
        btn_bar.addWidget(self.btn_down)

        layout.addLayout(btn_bar)
        self.setWidget(container)

        # Connect Tree Events
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        # Connect Action Buttons
        self.btn_dup.clicked.connect(self.duplicate_selected)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_up.clicked.connect(self.move_selected_up)
        self.btn_down.clicked.connect(self.move_selected_down)

        # Initial populate
        self.refresh()

    def get_selected_item_id(self) -> Optional[str]:
        items = self.tree.selectedItems()
        if not items:
            return None
        return items[0].data(0, Qt.UserRole)

    def refresh(self):
        """Rebuild tree items based on document items (ordered reverse so top layer is at top)."""
        if self._updating:
            return
        self._updating = True
        self.tree.blockSignals(True)

        current_sel_id = self.get_selected_item_id()
        self.tree.clear()

        # Display items in reverse order: doc.items[-1] is top layer
        for item in reversed(self.doc.items):
            node = QTreeWidgetItem(self.tree)
            node.setData(0, Qt.UserRole, item.item_id)

            # Col 0: Visibility
            vis_icon = get_icon("eye" if item.visible else "eye-off", size=16)
            node.setIcon(0, vis_icon)
            node.setToolTip(0, "Sichtbarkeit umschalten" if item.visible else "Ausgeblendet (klicken zum Einblenden)")

            # Col 1: Lock
            lock_icon = get_icon("lock" if item.locked else "lock-open", size=16)
            node.setIcon(1, lock_icon)
            node.setToolTip(1, "Gesperrt (klicken zum Entsperren)" if item.locked else "Entsperrt (klicken zum Sperren)")

            # Col 2: Name + Path count
            path_count = len(item.paths)
            label = f"{item.name} ({path_count} Pfade)" if path_count != 1 else f"{item.name} (1 Pfad)"
            node.setText(2, label)
            node.setData(2, Qt.UserRole, item.name)  # Raw name for renaming
            node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)

            if item.item_id == current_sel_id:
                node.setSelected(True)
                self.tree.setCurrentItem(node)

        self._update_button_states()
        self.tree.blockSignals(False)
        self._updating = False

    def sync_from_canvas_selection(self):
        """Update selected row in tree when canvas selection changes."""
        if self._updating:
            return
        self._updating = True
        self.tree.blockSignals(True)

        sel_ids = {
            g_item.item.item_id
            for g_item in self.canvas._item_map.values()
            if g_item.isSelected()
        }

        self.tree.clearSelection()
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            item_id = node.data(0, Qt.UserRole)
            if item_id in sel_ids:
                node.setSelected(True)
                self.tree.setCurrentItem(node)
                break

        self._update_button_states()
        self.tree.blockSignals(False)
        self._updating = False

    def _update_button_states(self):
        item_id = self.get_selected_item_id()
        has_sel = item_id is not None
        self.btn_dup.setEnabled(has_sel)
        self.btn_del.setEnabled(has_sel)

        if not has_sel or len(self.doc.items) <= 1:
            self.btn_up.setEnabled(False)
            self.btn_down.setEnabled(False)
        else:
            # In doc.items order:
            idx = next((i for i, it in enumerate(self.doc.items) if it.item_id == item_id), -1)
            # Up means towards top layer (len - 1)
            self.btn_up.setEnabled(idx < len(self.doc.items) - 1)
            # Down means towards bottom layer (0)
            self.btn_down.setEnabled(idx > 0)

    def _on_item_clicked(self, node: QTreeWidgetItem, column: int):
        item_id = node.data(0, Qt.UserRole)
        item = self.doc.find_item(item_id)
        if not item:
            return

        if column == 0:
            # Toggle visibility
            item.visible = not item.visible
            node.setIcon(0, get_icon("eye" if item.visible else "eye-off", size=16))
            g_item = self.canvas._item_map.get(item_id)
            if g_item:
                g_item.sync_from_transform()
            self.document_modified.emit()
        elif column == 1:
            # Toggle lock
            item.locked = not item.locked
            node.setIcon(1, get_icon("lock" if item.locked else "lock-open", size=16))
            g_item = self.canvas._item_map.get(item_id)
            if g_item:
                g_item.sync_from_transform()
            self.document_modified.emit()

    def _on_item_changed(self, node: QTreeWidgetItem, column: int):
        if column == 2 and not self._updating:
            item_id = node.data(0, Qt.UserRole)
            item = self.doc.find_item(item_id)
            if item:
                new_text = node.text(2).strip()
                # If user entered something, update item name
                if new_text:
                    item.name = new_text
                self.refresh()
                self.document_modified.emit()

    def _on_tree_selection_changed(self):
        if self._updating:
            return
        self._updating = True
        item_id = self.get_selected_item_id()

        self.canvas.blockSignals(True)
        self.canvas._scene.blockSignals(True)

        for it_id, g_item in self.canvas._item_map.items():
            g_item.setSelected(it_id == item_id)

        self.canvas._scene.blockSignals(False)
        self.canvas.blockSignals(False)

        self._update_button_states()
        self._updating = False
        self.canvas.selection_changed_signal.emit()

    def duplicate_selected(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        item = self.doc.find_item(item_id)
        if not item:
            return
        new_item = self.doc.duplicate_item(item, offset_mm=10.0)
        self.canvas.rebuild_items()
        self.refresh()
        # Select the duplicated item
        g_item = self.canvas._item_map.get(new_item.item_id)
        if g_item:
            self.canvas._scene.clearSelection()
            g_item.setSelected(True)
        self.sync_from_canvas_selection()
        self.document_modified.emit()

    def delete_selected(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        self.doc.remove_item(item_id)
        self.canvas.rebuild_items()
        self.refresh()
        self.document_modified.emit()

    def move_selected_up(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        if self.doc.move_item_up(item_id):
            self.canvas.rebuild_items()
            g_item = self.canvas._item_map.get(item_id)
            if g_item:
                self.canvas._scene.clearSelection()
                g_item.setSelected(True)
            self.refresh()
            self.sync_from_canvas_selection()
            self.document_modified.emit()

    def move_selected_down(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        if self.doc.move_item_down(item_id):
            self.canvas.rebuild_items()
            g_item = self.canvas._item_map.get(item_id)
            if g_item:
                self.canvas._scene.clearSelection()
                g_item.setSelected(True)
            self.refresh()
            self.sync_from_canvas_selection()
            self.document_modified.emit()
