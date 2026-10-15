"""Automated tests for Undo/Redo commands and QUndoStack integration."""

import os
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QUndoStack
from plotter_studio.core.document import Document, ImportItem, VectorPath, LogicalPen
from plotter_studio.core.geometry import AffineTransform, Point, BoundingBox
from plotter_studio.gui.commands import (
    TransformItemCommand, AssignPenCommand, AddItemCommand,
    DeleteItemsCommand, PageConfigCommand, PenRemapCommand, ApplyPresetCommand
)
import numpy as np




def test_transform_undo_redo(qapp):
    stack = QUndoStack()
    doc = Document()
    pts = np.array([[0.0, 0.0], [50.0, 50.0]])
    item = ImportItem(name="TestItem", paths=[VectorPath(points=pts)])
    doc.items.append(item)

    old_t = AffineTransform(1.0, 0.0, 0.0, 1.0, 10.0, 10.0)
    new_t = AffineTransform(2.0, 0.0, 0.0, 2.0, 40.0, 50.0)
    item.transform = old_t

    updated = [False]
    def on_upd():
        updated[0] = True

    cmd = TransformItemCommand(item, old_t, new_t, on_upd, text="Skalieren")
    stack.push(cmd)

    assert item.transform.a == 2.0
    assert item.transform.tx == 40.0
    assert updated[0] is True

    # Undo
    updated[0] = False
    stack.undo()
    assert item.transform.a == 1.0
    assert item.transform.tx == 10.0
    assert updated[0] is True

    # Redo
    updated[0] = False
    stack.redo()
    assert item.transform.a == 2.0
    assert item.transform.tx == 40.0
    assert updated[0] is True


def test_assign_pen_undo_redo(qapp):
    stack = QUndoStack()
    pts1 = np.array([[0.0, 0.0], [10.0, 10.0]])
    pts2 = np.array([[10.0, 10.0], [20.0, 20.0]])
    item = ImportItem(name="Test", paths=[VectorPath(points=pts1, pen_id=2), VectorPath(points=pts2, pen_id=3)])

    updated = [False]
    cmd = AssignPenCommand([item], new_pen_id=1, on_updated=lambda: updated.__setitem__(0, True))
    stack.push(cmd)

    assert item.paths[0].pen_id == 1
    assert item.paths[1].pen_id == 1

    stack.undo()
    assert item.paths[0].pen_id == 2
    assert item.paths[1].pen_id == 3

    stack.redo()
    assert item.paths[0].pen_id == 1
    assert item.paths[1].pen_id == 1


def test_add_delete_item_undo_redo(qapp):
    stack = QUndoStack()
    doc = Document()
    item = ImportItem(name="Square", paths=[VectorPath(points=np.array([[0, 0], [10, 0], [10, 10], [0, 10]]))])

    # Test AddItemCommand
    cmd_add = AddItemCommand(doc, item, on_updated=lambda: None)
    stack.push(cmd_add)
    assert len(doc.items) == 1
    assert doc.items[0].name == "Square"

    stack.undo()
    assert len(doc.items) == 0

    stack.redo()
    assert len(doc.items) == 1

    # Test DeleteItemsCommand
    cmd_del = DeleteItemsCommand(doc, [item], on_updated=lambda: None)
    stack.push(cmd_del)
    assert len(doc.items) == 0

    stack.undo()
    assert len(doc.items) == 1
    assert doc.items[0].name == "Square"

    stack.redo()
    assert len(doc.items) == 0


def test_page_config_undo_redo(qapp):
    stack = QUndoStack()
    doc = Document()
    doc.page.apply_preset("A4", "portrait")

    old_state = {
        "preset": "A4",
        "width_mm": 210.0,
        "height_mm": 297.0,
        "orientation": "portrait",
    }
    new_state = {
        "preset": "A2",
        "width_mm": 594.0,
        "height_mm": 420.0,
        "orientation": "landscape",
    }

    cmd = PageConfigCommand(doc.page, old_state, new_state, on_updated=lambda: None)
    stack.push(cmd)
    assert doc.page.width_mm == 594.0
    assert doc.page.orientation == "landscape"

    stack.undo()
    assert doc.page.width_mm == 210.0
    assert doc.page.orientation == "portrait"

    stack.redo()
    assert doc.page.width_mm == 594.0
    assert doc.page.orientation == "landscape"
