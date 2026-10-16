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


def test_pen_dock_columns_and_undo_without_duplicate_signals(qapp):
    from plotter_studio.gui.pen_dock import PenDockWidget
    from PySide6.QtCore import Qt
    doc = Document()
    stack = QUndoStack()
    dock = PenDockWidget(doc)
    dock.set_undo_stack(stack)

    # Call refresh_table multiple times to ensure itemChanged is not connected multiple times
    dock.refresh_table()
    dock.refresh_table()
    dock.refresh_table()

    orig_speed = doc.pens[0].speed_cm_s
    orig_force = doc.pens[0].force_g

    assert dock.table.columnCount() == 7
    # Edit speed (column 3) and force (column 4) of pen 1 (row 0) via cellWidget spinboxes
    dock.table.cellWidget(0, 3).setValue(25.0)
    assert doc.pens[0].speed_cm_s == pytest.approx(25.0)
    assert stack.count() == 1

    dock.table.cellWidget(0, 4).setValue(45.0)
    assert doc.pens[0].force_g == pytest.approx(45.0)
    assert stack.count() == 2

    # Toggle enabled checkbox (column 6) to verify itemChanged only fires once
    dock.table.item(0, 6).setCheckState(Qt.Unchecked)
    assert doc.pens[0].enabled is False
    assert stack.count() == 3

    stack.undo()
    assert doc.pens[0].enabled is True
    stack.undo()
    assert doc.pens[0].force_g == pytest.approx(orig_force)
    stack.undo()
    assert doc.pens[0].speed_cm_s == pytest.approx(orig_speed)


def test_object_dock_undo_rename_and_lock_protection(qapp):
    from plotter_studio.gui.main_window import MainWindow
    from PySide6.QtCore import Qt

    doc = Document()
    pts = np.array([[10.0, 10.0], [50.0, 10.0], [50.0, 40.0], [10.0, 10.0]])
    it1 = ImportItem(name="Stern", paths=[VectorPath(points=pts, pen_id=1, closed=True)])
    it2 = ImportItem(name="Kreis", paths=[VectorPath(points=pts.copy(), pen_id=2, closed=True)])
    doc.items.extend([it1, it2])

    win = MainWindow(doc)
    dock = win.object_dock
    stack = win.undo_stack

    # Rename via tree item with suffix stripping
    top_node = dock.tree.topLevelItem(0)  # it2 ("Kreis (1 Pfad)")
    dock._on_item_double_clicked(top_node, 2)
    assert top_node.text(2) == "Kreis"
    top_node.setText(2, "Kreis Neu (1 Pfad)")
    assert it2.name == "Kreis Neu"
    assert stack.count() == 1

    stack.undo()
    assert it2.name == "Kreis"
    stack.redo()
    assert it2.name == "Kreis Neu"

    # Lock it2 via column 1 click
    dock._on_item_clicked(dock.tree.topLevelItem(0), 1)
    assert it2.locked is True

    # Locked item should be protected against delete, rotate, and transform_dock actions
    win.canvas._item_map[it2.item_id].setSelected(True)
    win.canvas.selection_changed_signal.emit()
    old_tx = it2.transform.tx
    win.transform_dock.align_center_both()
    assert it2.transform.tx == pytest.approx(old_tx)
    win.rotate_selected_items(45.0)
    assert it2.transform.a == pytest.approx(1.0)
    win.delete_selected_items()
    assert doc.find_item(it2.item_id) is not None

    # Unlock via undo
    stack.undo()
    assert it2.locked is False

    # Test free rotation angle and multi-selection in TransformDockWidget
    win.transform_dock.set_selected_items([it1, it2])
    win.transform_dock.spin_rot_angle.setValue(30.0)
    assert it1.transform.a == pytest.approx(np.cos(np.radians(30.0)))
    assert it2.transform.a == pytest.approx(np.cos(np.radians(30.0)))

    stack.undo()
    assert it1.transform.a == pytest.approx(1.0)
    assert it2.transform.a == pytest.approx(1.0)
    win.close()

