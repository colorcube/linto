"""Canvas viewport and scene with paper representation and out-of-bounds warning."""

from __future__ import annotations
import copy
from typing import Optional, List, Dict
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QWheelEvent,
    QMouseEvent, QDragEnterEvent, QDropEvent, QTransform
)
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from ..core.document import Document, ImportItem
from .items import GraphicsImportItem


class PlotterCanvas(QGraphicsView):
    """
    Interactive 2D Viewport with millimeter coordinates.
    1.0 scene unit = 1.0 millimeter.
    """
    mouse_moved_mm = Signal(float, float)
    zoom_changed = Signal(float)
    file_dropped = Signal(str)
    selection_changed_signal = Signal()
    item_drag_finished = Signal(object, object, object)  # (item, old_transform, new_transform)

    def __init__(self, doc: Document, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Rendering options
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setRenderHint(QPainter.SmoothPixmapTransform, True)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

        # Pan state
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._space_pressed = False

        self._item_map: Dict[str, GraphicsImportItem] = {}

        self.update_scene_rect()
        self.rebuild_items()

        # Connect scene selection change
        self._scene.selectionChanged.connect(self.selection_changed_signal.emit)

    def update_scene_rect(self):
        """Update paper boundaries and scene size."""
        w = self.doc.page.width_mm
        h = self.doc.page.height_mm
        # Give generous margin around the paper for panning and margins
        pad = max(100.0, max(w, h) * 0.2)
        self._scene.setSceneRect(-pad, -pad, w + 2 * pad, h + 2 * pad)
        self.viewport().update()

    def rebuild_items(self):
        """Synchronize QGraphicsItems with Document items."""
        # Clear existing
        for g_item in self._item_map.values():
            if g_item.scene():
                self._scene.removeItem(g_item)
        self._item_map.clear()

        # Add items from doc
        for item in self.doc.items:
            g_item = GraphicsImportItem(item, self.doc)
            self._scene.addItem(g_item)
            self._item_map[item.item_id] = g_item

        self.viewport().update()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        painter.save()

        # Canvas workspace background (light gray)
        painter.fillRect(rect, QColor("#e8e8e8"))

        w = self.doc.page.width_mm
        h = self.doc.page.height_mm
        paper_rect = QRectF(0.0, 0.0, w, h)

        # Drop shadow for paper
        shadow_rect = QRectF(3.0, 3.0, w, h)
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 35))

        # Paper sheet (pure white)
        painter.fillRect(paper_rect, QColor("#ffffff"))
        painter.setPen(QPen(QColor("#b0b0b0"), 0.5))
        painter.drawRect(paper_rect)

        # Plottable area (Hard-Clip rectangle inside margins)
        pb = self.doc.page.plottable_box
        plottable_rect = QRectF(pb.min_x, pb.min_y, pb.width, pb.height)

        # Subtle paper margin shading (showing the non-plottable border)
        margin_brush = QBrush(QColor(245, 245, 248))
        if pb.min_y > 0:
            painter.fillRect(QRectF(0, 0, w, pb.min_y), margin_brush)
        if h > pb.max_y:
            painter.fillRect(QRectF(0, pb.max_y, w, h - pb.max_y), margin_brush)
        if pb.min_x > 0 and pb.height > 0:
            painter.fillRect(QRectF(0, pb.min_y, pb.min_x, pb.height), margin_brush)
        if w > pb.max_x and pb.height > 0:
            painter.fillRect(QRectF(pb.max_x, pb.min_y, w - pb.max_x, pb.height), margin_brush)

        pen_hardclip = QPen(QColor("#2196f3"), 0.4, Qt.DashLine)
        painter.setPen(pen_hardclip)
        painter.drawRect(plottable_rect)

        painter.restore()

    def wheelEvent(self, event: QWheelEvent):
        """Zoom smoothly towards mouse cursor."""
        factor = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        current_scale = self.transform().m11()
        new_scale = current_scale * factor

        # Clamp zoom between 5% and 5000%
        if 0.05 <= new_scale <= 50.0:
            self.scale(factor, factor)
            self.zoom_changed.emit(new_scale)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = True
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space_pressed = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_pressed):
            self._is_panning = True
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        elif event.button() == Qt.LeftButton:
            sp = self.mapToScene(event.pos())
            item_at = self.scene().itemAt(sp, QTransform())
            cur = item_at
            while cur and not isinstance(cur, GraphicsImportItem):
                cur = cur.parentItem()
            if isinstance(cur, GraphicsImportItem):
                self._drag_item = cur.item
                self._drag_old_transform = copy.deepcopy(cur.item.transform)
            else:
                self._drag_item = None
                self._drag_old_transform = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        # Update ruler and status coordinates
        sp = self.mapToScene(event.pos())
        self.mouse_moved_mm.emit(sp.x(), sp.y())

        if self._is_panning:
            dx = event.position().x() - self._pan_start_x
            dy = event.position().y() - self._pan_start_y
            self._pan_start_x = event.position().x()
            self._pan_start_y = event.position().y()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - dx))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - dy))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self._is_panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_pressed else Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        if hasattr(self, "_drag_item") and self._drag_item is not None and self._drag_old_transform is not None:
            if (self._drag_item.transform.tx != self._drag_old_transform.tx or
                self._drag_item.transform.ty != self._drag_old_transform.ty):
                self.item_drag_finished.emit(
                    self._drag_item, self._drag_old_transform, copy.deepcopy(self._drag_item.transform)
                )
            self._drag_item = None
            self._drag_old_transform = None
        self.selection_changed_signal.emit()

    def zoom_to_fit(self):
        """Fit entire paper sheet in viewport."""
        w = self.doc.page.width_mm
        h = self.doc.page.height_mm
        rect = QRectF(-15, -15, w + 30, h + 30)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self.zoom_changed.emit(self.transform().m11())

    def get_selected_import_items(self) -> List[ImportItem]:
        selected = []
        for g_item in self._scene.selectedItems():
            if isinstance(g_item, GraphicsImportItem):
                selected.append(g_item.item)
        return selected

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".svg", ".hpgl", ".plt")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            fpath = url.toLocalFile()
            if fpath.lower().endswith((".svg", ".hpgl", ".plt")):
                self.file_dropped.emit(fpath)
                event.acceptProposedAction()
                return
        event.ignore()
