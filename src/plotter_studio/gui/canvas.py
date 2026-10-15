"""Canvas viewport and scene with paper representation and out-of-bounds warning."""

from __future__ import annotations
import copy
from typing import Optional, List, Dict, Set
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (
    QPainter, QPen, QColor, QBrush, QWheelEvent,
    QMouseEvent, QDragEnterEvent, QDropEvent, QDragMoveEvent, QTransform
)
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from ..core.document import Document, ImportItem
from ..pipeline.compiler import PlotJob
from .items import GraphicsImportItem
from .plot_items import GraphicsPlotPreviewItem


class CanvasMode:
    LAYOUT = "layout"
    PLOT = "plot"


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
    item_transformed_live = Signal()

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
        self.viewport().setAcceptDrops(True)
        self.setMouseTracking(True)

        # Pan state
        self._is_panning = False
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._space_pressed = False

        self._item_map: Dict[str, GraphicsImportItem] = {}
        self._mode: str = CanvasMode.LAYOUT
        self._plot_preview_item: Optional[GraphicsPlotPreviewItem] = None
        self._show_nodes: bool = False
        self._show_travels: bool = True

        self.update_scene_rect()
        self.rebuild_items()

        # Connect scene selection change
        self._scene.selectionChanged.connect(self.selection_changed_signal.emit)

    def cleanup(self):
        """Mute signals and clear items before teardown to avoid PySide6 shutdown warnings/assertions."""
        if getattr(self, "_is_cleaned_up", False):
            return
        self._is_cleaned_up = True
        if hasattr(self, "_scene") and self._scene is not None:
            self._scene.blockSignals(True)
            self._item_map.clear()
            self._plot_preview_item = None
            self._scene.clear()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)

    def _get_paper_rect(self) -> QRectF:
        return QRectF(0.0, 0.0, self.doc.page.width_mm, self.doc.page.height_mm)

    def update_scene_rect(self):
        """Update paper boundaries and scene size."""
        w = self.doc.page.width_mm
        h = self.doc.page.height_mm
        # Give generous margin around the paper for panning and margins
        pad = max(100.0, max(w, h) * 0.2)
        self._scene.setSceneRect(-pad, -pad, w + 2 * pad, h + 2 * pad)
        if self._plot_preview_item is not None:
            self._plot_preview_item.page_rect = self._get_paper_rect()
            self._plot_preview_item.update()
        self.viewport().update()

    def set_mode(self, mode: str):
        """Switch canvas between CanvasMode.LAYOUT and CanvasMode.PLOT."""
        self._mode = mode
        if mode == CanvasMode.PLOT:
            # Hide interactive layout items
            for g_item in self._item_map.values():
                g_item.setVisible(False)
            if self._plot_preview_item is None:
                self._plot_preview_item = GraphicsPlotPreviewItem(
                    page_rect=self._get_paper_rect(),
                    show_nodes=self._show_nodes,
                    show_travels=self._show_travels,
                )
                self._scene.addItem(self._plot_preview_item)
            self._plot_preview_item.setVisible(True)
            self._scene.clearSelection()
        else:
            # Show interactive layout items
            if self._plot_preview_item is not None:
                self._plot_preview_item.setVisible(False)
            for g_item in self._item_map.values():
                g_item.setVisible(True)
        self.viewport().update()

    def set_plot_job(self, job: Optional[PlotJob]):
        """Supply compiled PlotJob to preview item."""
        if self._plot_preview_item is None:
            self._plot_preview_item = GraphicsPlotPreviewItem(
                job,
                page_rect=self._get_paper_rect(),
                show_nodes=self._show_nodes,
                show_travels=self._show_travels,
            )
            self._scene.addItem(self._plot_preview_item)
            if self._mode != CanvasMode.PLOT:
                self._plot_preview_item.setVisible(False)
        else:
            self._plot_preview_item.set_job(job, page_rect=self._get_paper_rect())
        self.viewport().update()

    def set_simulation_step(self, step: int):
        """Set active step for simulation rendering."""
        if self._plot_preview_item is not None:
            self._plot_preview_item.set_simulation_step(step)
            self.viewport().update()

    def set_show_travels(self, show: bool):
        """Toggle display of dashed pen-up travel lines."""
        self._show_travels = show
        if self._plot_preview_item is not None:
            self._plot_preview_item.set_show_travels(show)
            self.viewport().update()

    def set_show_nodes(self, show: bool):
        """Toggle display of coordinate vertices (nodes)."""
        self._show_nodes = show
        if self._plot_preview_item is not None:
            self._plot_preview_item.set_show_nodes(show)
            self.viewport().update()

    def set_visible_pens(self, pens: Optional[Set[int]]):
        """Filter paths by pen IDs (None means all)."""
        if self._plot_preview_item is not None:
            self._plot_preview_item.set_visible_pens(pens)
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
            if self._mode == CanvasMode.PLOT:
                g_item.setVisible(False)
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
            old_t = self._drag_old_transform
            cur_t = self._drag_item.transform
            if (old_t.tx != cur_t.tx or old_t.ty != cur_t.ty or
                abs(old_t.a - cur_t.a) > 1e-5 or abs(old_t.d - cur_t.d) > 1e-5):
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

    def dragMoveEvent(self, event: QDragMoveEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".svg", ".hpgl", ".plt")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                if fpath.lower().endswith((".svg", ".hpgl", ".plt")):
                    self.file_dropped.emit(fpath)
                    event.acceptProposedAction()
                    return
        event.ignore()
