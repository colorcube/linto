"""Tests for AP7 Object & Layer Management and UI redesign."""

import math
import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsItem

from linto.core.document import Document, ImportItem, VectorPath
from linto.core.geometry import AffineTransform, BoundingBox
from linto.pipeline.compiler import compile_document_to_plot_job
from linto.gui.main_window import MainWindow
from linto.gui.icons import get_icon


def _create_sample_item(name: str, x: float, y: float, w: float = 40.0, h: float = 20.0) -> ImportItem:
    pts = np.array([
        [x, y],
        [x + w, y],
        [x + w, y + h],
        [x, y + h],
        [x, y],
    ], dtype=np.float64)
    path = VectorPath(points=pts, pen_id=1, closed=True)
    return ImportItem(name=name, paths=[path])


def test_document_item_operations():
    doc = Document()
    it1 = _create_sample_item("Ebene 1", 10, 10)
    it2 = _create_sample_item("Ebene 2", 20, 20)
    it3 = _create_sample_item("Ebene 3", 30, 30)

    doc.items.extend([it1, it2, it3])
    assert [i.name for i in doc.items] == ["Ebene 1", "Ebene 2", "Ebene 3"]

    # Move up (towards top layer)
    assert doc.move_item_up(it1.item_id) is True
    assert [i.name for i in doc.items] == ["Ebene 2", "Ebene 1", "Ebene 3"]

    # Move down
    assert doc.move_item_down(it1.item_id) is True
    assert [i.name for i in doc.items] == ["Ebene 1", "Ebene 2", "Ebene 3"]

    # Boundary conditions
    assert doc.move_item_down(it1.item_id) is False
    assert doc.move_item_up(it3.item_id) is False

    # Duplicate
    dup = doc.duplicate_item(it1, offset_mm=10.0)
    assert len(doc.items) == 4
    assert dup.name == "Ebene 1 (Kopie)"
    assert dup.transform.tx == it1.transform.tx + 10.0
    assert dup.transform.ty == it1.transform.ty + 10.0


def test_compiler_respects_visibility():
    doc = Document()
    it1 = _create_sample_item("Sichtbar", 10, 10)
    it2 = _create_sample_item("Unsichtbar", 20, 20)
    it2.visible = False

    doc.items.extend([it1, it2])
    job = compile_document_to_plot_job(doc)
    assert 1 in job.layers
    # Only it1 paths (5 points) should be included in layer 1
    assert job.layers[1].point_count == len(it1.paths[0].points)


def test_object_dock_ui_and_synchronization(qapp):
    doc = Document()
    it1 = _create_sample_item("Objekt A", 10, 10)
    it2 = _create_sample_item("Objekt B", 30, 30)
    doc.items.extend([it1, it2])

    win = MainWindow(doc)
    win.show()

    dock = win.object_dock
    assert dock is not None
    assert dock.windowTitle() == "Objekte & Ebenen"

    # Tree should contain 2 items, displayed in reverse order (top layer Objekt B first)
    assert dock.tree.topLevelItemCount() == 2
    top_node = dock.tree.topLevelItem(0)
    bottom_node = dock.tree.topLevelItem(1)
    assert top_node.data(0, Qt.UserRole) == it2.item_id
    assert bottom_node.data(0, Qt.UserRole) == it1.item_id

    # Test Visibility toggle via column 0 click
    assert it2.visible is True
    dock._on_item_clicked(top_node, 0)
    assert it2.visible is False
    # Canvas item should now be hidden
    g_item2 = win.canvas._item_map[it2.item_id]
    assert not g_item2.isVisible()

    # Toggle back on
    dock._on_item_clicked(top_node, 0)
    assert it2.visible is True
    assert g_item2.isVisible()

    # Test Lock toggle via column 1 click
    assert it2.locked is False
    dock._on_item_clicked(top_node, 1)
    assert it2.locked is True
    assert not (g_item2.flags() & QGraphicsItem.ItemIsMovable)

    # Test selection sync: selecting canvas item selects tree item
    win.canvas._scene.clearSelection()
    g_item1 = win.canvas._item_map[it1.item_id]
    g_item1.setSelected(True)
    win.canvas.selection_changed_signal.emit()

    assert dock.get_selected_item_id() == it1.item_id

    # Test duplicate via dock button
    initial_count = len(doc.items)
    dock.duplicate_selected()
    assert len(doc.items) == initial_count + 1
    assert doc.items[-1].name == "Objekt A (Kopie)"
    assert doc.items[-1].item_id in win.canvas._item_map

    # Test delete via dock button
    del_id = doc.items[-1].item_id
    dock.delete_selected()
    assert doc.find_item(del_id) is None

    # Test move up/down
    # Select it1 (at index 0 in doc.items)
    for i in range(dock.tree.topLevelItemCount()):
        n = dock.tree.topLevelItem(i)
        if n.data(0, Qt.UserRole) == it1.item_id:
            dock.tree.setCurrentItem(n)
            n.setSelected(True)
            break

    dock.move_selected_up()
    assert doc.items[1].item_id == it1.item_id

    dock.move_selected_down()
    assert doc.items[0].item_id == it1.item_id

    win.close()


def test_toolbar_clean_style_and_device_selector(qapp):
    doc = Document()
    win = MainWindow(doc)
    win.show()

    # Verify mode switches have text, other toolbar actions are icon-only
    assert win.act_mode_layout.text() == "Layout"
    assert win.act_mode_plot.text() == "Ausgabe"

    # Verify device selector combo and settings button in toolbar
    assert win.combo_active_device is not None
    assert win.combo_active_device.count() >= 2
    assert win.btn_device_settings is not None

    # Switching device updates paper dock and plot dock
    devs = win.device_manager.list_devices()
    win.combo_active_device.setCurrentIndex(1)
    selected_dev = devs[1]
    assert win.device_manager.active_device_id == selected_dev.id

    win.close()


def test_multi_selection_duplicate_delete_and_drag_undo(qapp):
    """Verify multi-selection in ObjectDock, multi-duplicate/delete, drag undo, spinbox merging, and flipping."""
    import numpy as np
    from linto.core.geometry import AffineTransform

    doc = Document()
    pts = np.array([[10.0, 10.0], [40.0, 10.0], [40.0, 30.0], [10.0, 10.0]])
    it1 = ImportItem(name="Obj1", paths=[VectorPath(points=pts.copy(), pen_id=1, closed=True)])
    it2 = ImportItem(name="Obj2", paths=[VectorPath(points=pts.copy(), pen_id=2, closed=True)])
    it3 = ImportItem(name="Obj3", paths=[VectorPath(points=pts.copy(), pen_id=3, closed=True)])
    doc.items.extend([it1, it2, it3])

    win = MainWindow(doc)
    win.show()

    # 1. Verify spinboxes have keyboardTracking disabled
    assert win.transform_dock.spin_pos_x.keyboardTracking() is False
    assert win.transform_dock.spin_obj_w.keyboardTracking() is False
    assert win.plot_dock.spin_flatten.keyboardTracking() is False

    # 2. Select both it1 and it2 on canvas -> ObjectDock syncs multi-selection
    win.canvas._item_map[it1.item_id].setSelected(True)
    win.canvas._item_map[it2.item_id].setSelected(True)
    win.canvas.selection_changed_signal.emit()
    assert set(win.object_dock.get_selected_item_ids()) == {it1.item_id, it2.item_id}

    # 3. Duplicate both selected items in one macro
    win.duplicate_selected_items()
    assert len(doc.items) == 5
    win.undo_stack.undo()
    assert len(doc.items) == 3

    # 4. Delete it1 -> selection should NOT jump to doc.items[-1] (it3)
    win.canvas._scene.clearSelection()
    win.canvas._item_map[it1.item_id].setSelected(True)
    win.canvas.selection_changed_signal.emit()
    win.delete_selected_items()
    assert len(doc.items) == 2
    assert win.canvas.get_selected_import_items() == []
    win.undo_stack.undo()
    assert len(doc.items) == 3

    # 5. Multi-item drag undo via items_drag_finished
    old_t1 = AffineTransform(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    new_t1 = AffineTransform(1.0, 0.0, 0.0, 1.0, 25.0, 15.0)
    old_t2 = AffineTransform(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    new_t2 = AffineTransform(1.0, 0.0, 0.0, 1.0, 25.0, 15.0)
    it1.transform = new_t1
    it2.transform = new_t2
    win.canvas.items_drag_finished.emit([(it1, old_t1, new_t1), (it2, old_t2, new_t2)])
    assert it1.transform.tx == pytest.approx(25.0)
    assert it2.transform.tx == pytest.approx(25.0)

    # Single undo reverts both items
    win.undo_stack.undo()
    assert it1.transform.tx == pytest.approx(0.0)
    assert it2.transform.tx == pytest.approx(0.0)

    # 6. Consecutive spinbox position changes on same item merge into 1 undo command
    win.undo_stack.clear()
    win.transform_dock.set_selected_items([it1])
    win.transform_dock.spin_pos_x.setValue(30.0)
    win.transform_dock.spin_pos_x.setValue(45.0)
    assert win.undo_stack.count() == 1

    # 7. Flip horizontal & vertical
    win.canvas._item_map[it1.item_id].setSelected(True)
    a_before = it1.transform.a
    d_before = it1.transform.d
    win.flip_selected_items(horizontal=True)
    assert it1.transform.a == pytest.approx(-a_before)
    win.flip_selected_items(horizontal=False)
    assert it1.transform.d == pytest.approx(-d_before)

    # 8. Zoom to selection
    win.act_zoom_selection.trigger()
    assert win.canvas.transform().m11() > 0.0

    win.close()

