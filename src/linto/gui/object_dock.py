"""Object and Layer management dock widget."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QUndoStack
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem, QToolButton, QHeaderView,
    QAbstractItemView, QStyledItemDelegate, QLineEdit
)
from .icons import get_icon
from .commands import (
    AddItemCommand,
    DeleteItemsCommand,
    ModifyItemPropertiesCommand,
    MoveItemZOrderCommand,
)

if TYPE_CHECKING:
    from ..core.document import Document, ImportItem
    from .canvas import PlotterCanvas


_RAW_NAME_ROLE = Qt.UserRole
_SUFFIX_ROLE = Qt.UserRole + 1


class _ObjectNameDelegate(QStyledItemDelegate):
    """Delegate that edits the raw object name (without path count suffix)."""

    def setEditorData(self, editor, index):
        raw_name = index.data(_RAW_NAME_ROLE)
        if isinstance(editor, QLineEdit) and raw_name is not None:
            editor.setText(str(raw_name))
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QLineEdit):
            model.setData(index, editor.text(), Qt.EditRole)
        else:
            super().setModelData(editor, model, index)


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
        super().__init__(self.tr("Objects & Layers"), parent)
        self.doc = doc
        self.canvas = canvas
        self.undo_stack: Optional[QUndoStack] = None
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
        self.tree.setHeaderLabels(["", "", self.tr("Object")])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.tree.setItemDelegateForColumn(2, _ObjectNameDelegate(self.tree))
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
        h_item.setToolTip(0, self.tr("Toggle visibility"))
        h_item.setIcon(1, get_icon("lock", size=14))
        h_item.setToolTip(1, self.tr("Toggle lock"))

        layout.addWidget(self.tree)

        # Action Toolbar at bottom
        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(0, 0, 0, 0)
        btn_bar.setSpacing(2)

        self.btn_import = QToolButton(self)
        self.btn_import.setIcon(get_icon("import", size=18))
        self.btn_import.setToolTip(self.tr("Import file (SVG, HP-GL)"))
        self.btn_import.setAutoRaise(True)

        self.btn_dup = QToolButton(self)
        self.btn_dup.setIcon(get_icon("duplicate", size=18))
        self.btn_dup.setToolTip(self.tr("Duplicate selected object (Ctrl+D)"))
        self.btn_dup.setAutoRaise(True)

        self.btn_del = QToolButton(self)
        self.btn_del.setIcon(get_icon("delete", size=18))
        self.btn_del.setToolTip(self.tr("Delete selected object (Del)"))
        self.btn_del.setAutoRaise(True)

        self.btn_up = QToolButton(self)
        self.btn_up.setIcon(get_icon("arrow-up", size=18))
        self.btn_up.setToolTip(self.tr("Move layer up (Bring Forward)"))
        self.btn_up.setAutoRaise(True)

        self.btn_down = QToolButton(self)
        self.btn_down.setIcon(get_icon("arrow-down", size=18))
        self.btn_down.setToolTip(self.tr("Move layer down (Send Backward)"))
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
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemSelectionChanged.connect(self._on_tree_selection_changed)

        # Connect Action Buttons
        self.btn_dup.clicked.connect(self.duplicate_selected)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_up.clicked.connect(self.move_selected_up)
        self.btn_down.clicked.connect(self.move_selected_down)

        # Initial populate
        self.refresh()

    def set_undo_stack(self, stack: QUndoStack):
        self.undo_stack = stack

    def get_selected_item_ids(self) -> list[str]:
        items = self.tree.selectedItems()
        return [it.data(0, Qt.UserRole) for it in items if it.data(0, Qt.UserRole)]

    def get_selected_item_id(self) -> Optional[str]:
        ids = self.get_selected_item_ids()
        return ids[0] if ids else None

    def _get_selected_doc_items(self) -> list[ImportItem]:
        """Return currently selected ImportItems in document order (syncing canvas and tree)."""
        sel_ids = set(self.get_selected_item_ids())
        canvas_sel = self.canvas.get_selected_import_items()
        if canvas_sel:
            sel_ids.update(it.item_id for it in canvas_sel)
        return [it for it in self.doc.items if it.item_id in sel_ids]

    def _populate_tree_node(self, node: QTreeWidgetItem, item: ImportItem):
        node.setData(0, Qt.UserRole, item.item_id)

        # Col 0: Visibility
        vis_icon = get_icon("eye" if item.visible else "eye-off", size=16)
        node.setIcon(0, vis_icon)
        node.setToolTip(0, self.tr("Toggle visibility") if item.visible else self.tr("Hidden (click to show)"))

        # Col 1: Lock
        lock_icon = get_icon("lock" if item.locked else "lock-open", size=16)
        node.setIcon(1, lock_icon)
        node.setToolTip(1, self.tr("Locked (click to unlock)") if item.locked else self.tr("Unlocked (click to lock)"))

        # Col 2: Name + Path count
        path_count = len(item.paths)
        suffix = self.tr("(1 path)") if path_count == 1 else self.tr("(%1 paths)").replace("%1", str(path_count))
        label = f"{item.name} {suffix}"
        node.setText(2, label)
        node.setData(2, _RAW_NAME_ROLE, item.name)
        node.setData(2, _SUFFIX_ROLE, suffix)
        node.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable)

    def refresh(self):
        """Rebuild or update tree items based on document items (ordered reverse so top layer is at top)."""
        if self._updating:
            return
        self._updating = True
        self.tree.blockSignals(True)

        current_sel_ids = set(self.get_selected_item_ids())
        rev_items = list(reversed(self.doc.items))
        existing_ids = [
            self.tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self.tree.topLevelItemCount())
        ]
        target_ids = [item.item_id for item in rev_items]

        if existing_ids == target_ids:
            for i, item in enumerate(rev_items):
                node = self.tree.topLevelItem(i)
                self._populate_tree_node(node, item)
                if item.item_id in current_sel_ids:
                    node.setSelected(True)
                    if len(current_sel_ids) == 1:
                        self.tree.setCurrentItem(node)
        else:
            self.tree.clear()
            for item in rev_items:
                node = QTreeWidgetItem(self.tree)
                self._populate_tree_node(node, item)
                if item.item_id in current_sel_ids:
                    node.setSelected(True)
                    if len(current_sel_ids) == 1:
                        self.tree.setCurrentItem(node)

        self._update_button_states()
        self.tree.blockSignals(False)
        self._updating = False

    def sync_from_canvas_selection(self):
        """Update selected rows in tree when canvas selection changes."""
        if self._updating or getattr(self.canvas, "_mode", None) == "plot":
            return
        self._updating = True
        self.tree.blockSignals(True)

        sel_ids = {
            g_item.item.item_id
            for g_item in self.canvas._item_map.values()
            if g_item.isSelected()
        }

        self.tree.clearSelection()
        first_selected = None
        for i in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(i)
            item_id = node.data(0, Qt.UserRole)
            if item_id in sel_ids:
                node.setSelected(True)
                if first_selected is None:
                    first_selected = node
        if first_selected is not None and len(sel_ids) == 1:
            self.tree.setCurrentItem(first_selected)

        self._update_button_states()
        self.tree.blockSignals(False)
        self._updating = False

    def _update_button_states(self):
        selected_items = [
            self.doc.find_item(iid) for iid in self.get_selected_item_ids()
        ]
        selected_items = [it for it in selected_items if it is not None]
        has_sel = len(selected_items) > 0
        has_unlocked = any(not it.locked for it in selected_items)
        self.btn_dup.setEnabled(has_sel)
        self.btn_del.setEnabled(has_unlocked)

        if len(selected_items) != 1 or len(self.doc.items) <= 1:
            self.btn_up.setEnabled(False)
            self.btn_down.setEnabled(False)
        else:
            item_id = selected_items[0].item_id
            idx = next((i for i, it in enumerate(self.doc.items) if it.item_id == item_id), -1)
            # Up means towards top layer (len - 1)
            self.btn_up.setEnabled(idx < len(self.doc.items) - 1)
            # Down means towards bottom layer (0)
            self.btn_down.setEnabled(idx > 0)

    def _on_prop_cmd_updated(self, item_id: str):
        g_item = self.canvas._item_map.get(item_id)
        if g_item:
            g_item.sync_from_transform()
        self.refresh()
        self.document_modified.emit()

    def _on_item_clicked(self, node: QTreeWidgetItem, column: int):
        item_id = node.data(0, Qt.UserRole)
        item = self.doc.find_item(item_id)
        if not item:
            return

        if column == 0:
            old_vis = item.visible
            new_vis = not old_vis
            if self.undo_stack:
                action_txt = (
                    self.tr("Show '%1'").replace("%1", item.name)
                    if new_vis
                    else self.tr("Hide '%1'").replace("%1", item.name)
                )
                cmd = ModifyItemPropertiesCommand(
                    item,
                    {"visible": old_vis},
                    {"visible": new_vis},
                    lambda iid=item_id: self._on_prop_cmd_updated(iid),
                    text=action_txt,
                )
                self.undo_stack.push(cmd)
            else:
                item.visible = new_vis
                self._on_prop_cmd_updated(item_id)
        elif column == 1:
            old_lock = item.locked
            new_lock = not old_lock
            if self.undo_stack:
                action_txt = (
                    self.tr("Lock '%1'").replace("%1", item.name)
                    if new_lock
                    else self.tr("Unlock '%1'").replace("%1", item.name)
                )
                cmd = ModifyItemPropertiesCommand(
                    item,
                    {"locked": old_lock},
                    {"locked": new_lock},
                    lambda iid=item_id: self._on_prop_cmd_updated(iid),
                    text=action_txt,
                )
                self.undo_stack.push(cmd)
            else:
                item.locked = new_lock
                self._on_prop_cmd_updated(item_id)

    def _on_item_double_clicked(self, node: QTreeWidgetItem, column: int):
        if column == 2:
            raw_name = node.data(2, _RAW_NAME_ROLE)
            if raw_name:
                self.tree.blockSignals(True)
                node.setText(2, str(raw_name))
                self.tree.blockSignals(False)

    def _on_item_changed(self, node: QTreeWidgetItem, column: int):
        if column == 2 and not self._updating:
            item_id = node.data(0, Qt.UserRole)
            item = self.doc.find_item(item_id)
            if item:
                raw_text = node.text(2).strip()
                suffix = str(node.data(2, _SUFFIX_ROLE) or "")
                if suffix and raw_text.endswith(suffix):
                    clean_name = raw_text[:-len(suffix)].strip()
                else:
                    clean_name = raw_text
                if clean_name and clean_name != item.name:
                    old_name = item.name
                    if self.undo_stack:
                        cmd = ModifyItemPropertiesCommand(
                            item,
                            {"name": old_name},
                            {"name": clean_name},
                            lambda iid=item_id: self._on_prop_cmd_updated(iid),
                            text=self.tr("Rename object to '%1'").replace("%1", clean_name),
                        )
                        self.undo_stack.push(cmd)
                        return
                    item.name = clean_name
                self.refresh()
                self.document_modified.emit()

    def _on_tree_selection_changed(self):
        if self._updating:
            return
        self._updating = True
        sel_ids = set(self.get_selected_item_ids())

        self.canvas.blockSignals(True)
        self.canvas._scene.blockSignals(True)

        for it_id, g_item in self.canvas._item_map.items():
            g_item.setSelected(it_id in sel_ids)

        self.canvas._scene.blockSignals(False)
        self.canvas.blockSignals(False)

        self._update_button_states()
        self._updating = False
        self.canvas.selection_changed_signal.emit()

    def _on_structure_cmd_updated(self, select_ids: Optional[str | list[str]] = None):
        self.canvas.rebuild_items()
        self.refresh()
        self.canvas._scene.clearSelection()
        if isinstance(select_ids, str):
            target_ids = [select_ids]
        elif isinstance(select_ids, list):
            target_ids = select_ids
        else:
            target_ids = []
        for tid in target_ids:
            if tid and tid in self.canvas._item_map:
                self.canvas._item_map[tid].setSelected(True)
        self.sync_from_canvas_selection()
        self.document_modified.emit()

    def duplicate_selected(self):
        targets = self._get_selected_doc_items()
        if not targets:
            return
        new_items = [self.doc.duplicate_item(it, offset_mm=10.0) for it in targets]
        new_ids = [ni.item_id for ni in new_items]
        if self.undo_stack:
            # Remove first so AddItemCommand.redo() appends cleanly
            for ni in new_items:
                self.doc.remove_item(ni.item_id)
            if len(new_items) == 1:
                ni = new_items[0]
                cmd = AddItemCommand(
                    self.doc,
                    ni,
                    lambda nid=ni.item_id: self._on_structure_cmd_updated(nid),
                    text=self.tr("Duplicate '%1'").replace("%1", targets[0].name),
                )
                self.undo_stack.push(cmd)
            else:
                macro_text = self.tr("Duplicate %1 objects").replace("%1", str(len(new_items)))
                self.undo_stack.beginMacro(macro_text)
                try:
                    for it, ni in zip(targets, new_items):
                        cmd = AddItemCommand(
                            self.doc,
                            ni,
                            lambda nids=new_ids: self._on_structure_cmd_updated(nids),
                            text=self.tr("Duplicate '%1'").replace("%1", it.name),
                        )
                        self.undo_stack.push(cmd)
                finally:
                    self.undo_stack.endMacro()
        else:
            self._on_structure_cmd_updated(new_ids)

    def delete_selected(self):
        targets = [it for it in self._get_selected_doc_items() if not it.locked]
        if not targets:
            return
        if self.undo_stack:
            text = (
                self.tr("Delete '%1'").replace("%1", targets[0].name)
                if len(targets) == 1
                else self.tr("Delete %1 objects").replace("%1", str(len(targets)))
            )
            cmd = DeleteItemsCommand(
                self.doc,
                targets,
                lambda: self._on_structure_cmd_updated(None),
                text=text,
            )
            self.undo_stack.push(cmd)
        else:
            for it in targets:
                self.doc.remove_item(it.item_id)
            self._on_structure_cmd_updated(None)

    def move_selected_up(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        idx = next((i for i, it in enumerate(self.doc.items) if it.item_id == item_id), -1)
        if idx < 0 or idx >= len(self.doc.items) - 1:
            return
        if self.undo_stack:
            cmd = MoveItemZOrderCommand(
                self.doc,
                item_id,
                "up",
                lambda iid=item_id: self._on_structure_cmd_updated(iid),
                text=self.tr("Move layer up"),
            )
            self.undo_stack.push(cmd)
        elif self.doc.move_item_up(item_id):
            self._on_structure_cmd_updated(item_id)

    def move_selected_down(self):
        item_id = self.get_selected_item_id()
        if not item_id:
            return
        idx = next((i for i, it in enumerate(self.doc.items) if it.item_id == item_id), -1)
        if idx <= 0:
            return
        if self.undo_stack:
            cmd = MoveItemZOrderCommand(
                self.doc,
                item_id,
                "down",
                lambda iid=item_id: self._on_structure_cmd_updated(iid),
                text=self.tr("Move layer down"),
            )
            self.undo_stack.push(cmd)
        elif self.doc.move_item_down(item_id):
            self._on_structure_cmd_updated(item_id)

