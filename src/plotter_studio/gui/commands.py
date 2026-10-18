"""Undo/Redo command classes based on QUndoCommand."""

from __future__ import annotations
import copy
from typing import List, Tuple, Optional, Callable, Dict, Any
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QUndoCommand
from ..core.geometry import AffineTransform
from ..core.document import Document, ImportItem, VectorPath, LogicalPen, Page

CMD_ID_POS = 1001
CMD_ID_SIZE = 1002
CMD_ID_SCALE = 1003
CMD_ID_ROT = 1004


def _tr(text: str) -> str:
    return QCoreApplication.translate("Commands", text)


class TransformItemCommand(QUndoCommand):
    """Undoable command for moving, scaling or aligning an ImportItem."""
    def __init__(
        self,
        item: ImportItem,
        old_transform: AffineTransform,
        new_transform: AffineTransform,
        on_updated: Callable[[], None],
        text: Optional[str] = None,
        command_id: int = -1,
    ):
        super().__init__(text or _tr("Transform object"))
        self.item = item
        self.old_transform = copy.deepcopy(old_transform)
        self.new_transform = copy.deepcopy(new_transform)
        self.on_updated = on_updated
        self._cmd_id = command_id

    def id(self) -> int:
        return self._cmd_id

    def undo(self):
        self.item.transform = copy.deepcopy(self.old_transform)
        self.on_updated()

    def redo(self):
        self.item.transform = copy.deepcopy(self.new_transform)
        self.on_updated()

    def mergeWith(self, other: QUndoCommand) -> bool:
        if not isinstance(other, TransformItemCommand):
            return False
        if other.id() != self.id() or self.id() == -1:
            return False
        if other.item != self.item:
            return False
        self.new_transform = copy.deepcopy(other.new_transform)
        return True


class AssignPenCommand(QUndoCommand):
    """Undoable command for assigning paths to a specific pen slot."""
    def __init__(
        self,
        items: List[ImportItem],
        new_pen_id: int,
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Assign pen"))
        self.items = items
        self.new_pen_id = new_pen_id
        self.on_updated = on_updated
        # Store original pen ids for every path in the affected items
        self.original_assignments: List[Tuple[VectorPath, int]] = []
        for it in self.items:
            for p in it.paths:
                self.original_assignments.append((p, p.pen_id))

    def undo(self):
        for path, orig_id in self.original_assignments:
            path.pen_id = orig_id
        self.on_updated()

    def redo(self):
        for it in self.items:
            it.set_pen_for_all(self.new_pen_id)
        self.on_updated()


class AddItemCommand(QUndoCommand):
    """Undoable command for adding an ImportItem to the document."""
    def __init__(
        self,
        doc: Document,
        item: ImportItem,
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Import object"))
        self.doc = doc
        self.item = item
        self.on_updated = on_updated

    def undo(self):
        self.doc.remove_item(self.item.item_id)
        self.on_updated()

    def redo(self):
        if self.doc.find_item(self.item.item_id) is None:
            self.doc.items.append(self.item)
        self.on_updated()


class DeleteItemsCommand(QUndoCommand):
    """Undoable command for removing items from the document."""
    def __init__(
        self,
        doc: Document,
        items: List[ImportItem],
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Delete object(s)"))
        self.doc = doc
        self.items_with_indices: List[Tuple[int, ImportItem]] = []
        for it in items:
            for idx, existing in enumerate(self.doc.items):
                if existing.item_id == it.item_id:
                    self.items_with_indices.append((idx, it))
                    break
        self.on_updated = on_updated

    def undo(self):
        # Re-insert items at their original indices (sorted by index)
        for idx, it in sorted(self.items_with_indices, key=lambda x: x[0]):
            if self.doc.find_item(it.item_id) is None:
                self.doc.items.insert(min(idx, len(self.doc.items)), it)
        self.on_updated()

    def redo(self):
        for _, it in self.items_with_indices:
            self.doc.remove_item(it.item_id)
        self.on_updated()


class PageConfigCommand(QUndoCommand):
    """Undoable command for changing paper format, orientation or margins."""
    def __init__(
        self,
        page: Page,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Change paper format"))
        self.page = page
        self.old_state = copy.deepcopy(old_state)
        self.new_state = copy.deepcopy(new_state)
        self.on_updated = on_updated

    def _apply_state(self, state: Dict[str, Any]):
        self.page.preset = state.get("preset", self.page.preset)
        self.page.width_mm = state.get("width_mm", self.page.width_mm)
        self.page.height_mm = state.get("height_mm", self.page.height_mm)
        self.page.orientation = state.get("orientation", self.page.orientation)
        self.page.device_profile = state.get("device_profile", self.page.device_profile)
        self.page.feed_edge = state.get("feed_edge", self.page.feed_edge)
        self.page.margin_left_mm = state.get("margin_left_mm", self.page.margin_left_mm)
        self.page.margin_right_mm = state.get("margin_right_mm", self.page.margin_right_mm)
        self.page.margin_top_mm = state.get("margin_top_mm", self.page.margin_top_mm)
        self.page.margin_bottom_mm = state.get("margin_bottom_mm", self.page.margin_bottom_mm)

    def undo(self):
        self._apply_state(self.old_state)
        self.on_updated()

    def redo(self):
        self._apply_state(self.new_state)
        self.on_updated()


class PenRemapCommand(QUndoCommand):
    """Undoable command for remapping pens or applying monochrome."""
    def __init__(
        self,
        doc: Document,
        old_mappings: List[Tuple[int, Optional[int]]],
        new_mappings: List[Tuple[int, Optional[int]]],
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Change pen remapping"))
        self.doc = doc
        self.old_mappings = old_mappings
        self.new_mappings = new_mappings
        self.on_updated = on_updated

    def undo(self):
        for pid, mapped in self.old_mappings:
            p = self.doc.get_pen(pid)
            if p:
                p.mapped_to = mapped
        self.on_updated()

    def redo(self):
        for pid, mapped in self.new_mappings:
            p = self.doc.get_pen(pid)
            if p:
                p.mapped_to = mapped
        self.on_updated()


class ApplyPresetCommand(QUndoCommand):
    """Undoable command for switching pen presets with remapping."""
    def __init__(
        self,
        doc: Document,
        old_pens: List[LogicalPen],
        new_pens: List[LogicalPen],
        old_assignments: List[Tuple[VectorPath, int]],
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Apply pen preset"))
        self.doc = doc
        self.old_pens = copy.deepcopy(old_pens)
        self.new_pens = copy.deepcopy(new_pens)
        self.old_assignments = list(old_assignments)
        self.new_assignments = [(p, p.pen_id) for it in doc.items for p in it.paths]
        self.on_updated = on_updated

    def undo(self):
        self.doc.pens = copy.deepcopy(self.old_pens)
        for path, pid in self.old_assignments:
            path.pen_id = pid
        self.on_updated()

    def redo(self):
        self.doc.pens = copy.deepcopy(self.new_pens)
        for path, pid in self.new_assignments:
            path.pen_id = pid
        self.on_updated()


class ModifyItemPropertiesCommand(QUndoCommand):
    """Undoable command for changing name, visibility or lock state of an ImportItem."""
    def __init__(
        self,
        item: ImportItem,
        old_props: Dict[str, Any],
        new_props: Dict[str, Any],
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Change object property"))
        self.item = item
        self.old_props = copy.deepcopy(old_props)
        self.new_props = copy.deepcopy(new_props)
        self.on_updated = on_updated

    def _apply(self, props: Dict[str, Any]):
        for k, v in props.items():
            setattr(self.item, k, v)

    def undo(self):
        self._apply(self.old_props)
        self.on_updated()

    def redo(self):
        self._apply(self.new_props)
        self.on_updated()


class MoveItemZOrderCommand(QUndoCommand):
    """Undoable command for moving an ImportItem up or down in document z-order."""
    def __init__(
        self,
        doc: Document,
        item_id: str,
        direction: str,
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Change layer order"))
        self.doc = doc
        self.item_id = item_id
        self.direction = direction  # "up" or "down"
        self.on_updated = on_updated

    def undo(self):
        if self.direction == "up":
            self.doc.move_item_down(self.item_id)
        else:
            self.doc.move_item_up(self.item_id)
        self.on_updated()

    def redo(self):
        if self.direction == "up":
            self.doc.move_item_up(self.item_id)
        else:
            self.doc.move_item_down(self.item_id)
        self.on_updated()


class ModifyPenPropertyCommand(QUndoCommand):
    """Undoable command for modifying a property of a LogicalPen (color, width, speed, force, mapped_to, enabled)."""
    def __init__(
        self,
        doc: Document,
        pen_id: int,
        attr_name: str,
        old_value: Any,
        new_value: Any,
        on_updated: Callable[[], None],
        text: Optional[str] = None,
    ):
        super().__init__(text or _tr("Modify pen"))
        self.doc = doc
        self.pen_id = pen_id
        self.attr_name = attr_name
        self.old_value = old_value
        self.new_value = new_value
        self.on_updated = on_updated

    def undo(self):
        p = self.doc.get_pen(self.pen_id)
        if p is not None:
            setattr(p, self.attr_name, self.old_value)
        self.on_updated()

    def redo(self):
        p = self.doc.get_pen(self.pen_id)
        if p is not None:
            setattr(p, self.attr_name, self.new_value)
        self.on_updated()


