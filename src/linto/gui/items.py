"""Interactive QGraphicsItem representing an ImportItem on the canvas."""

from __future__ import annotations
import copy
import math
from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor, QBrush, QPolygonF, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent, QGraphicsSceneHoverEvent
from ..core.geometry import (
    Point,
    LineSegment,
    QuadraticBezierSegment,
    CubicBezierSegment,
    ArcSegment,
)

if TYPE_CHECKING:
    from ..core.document import Document, ImportItem


class GraphicsImportItem(QGraphicsItem):
    """
    QGraphicsItem rendering an ImportItem with true millimeter coordinates,
    WYSIWYG pens, selection bounds, and interactive corner handles for proportional scaling.
    """
    def __init__(self, item: ImportItem, doc: Document, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.item = item
        self.doc = doc

        self.setFlags(
            QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        # Handle resize state
        self._resizing_handle: Optional[str] = None
        self._resize_start_transform: Optional[Any] = None

        # Synchronize scale and position from item model
        self.sync_from_transform()

    def boundingRect(self) -> QRectF:
        if not self.item.visible or self.item.original_bounds is None:
            return QRectF()
        b = self.item.original_bounds
        scale_x = math.hypot(self.item.transform.a, self.item.transform.b)
        scale_y = math.hypot(self.item.transform.c, self.item.transform.d)
        scale_x = scale_x if scale_x > 1e-6 else 1.0
        scale_y = scale_y if scale_y > 1e-6 else 1.0
        # 3.0 mm scene padding for stroke thickness and selection handles
        pad_x = 3.0 / scale_x
        pad_y = 3.0 / scale_y
        return QRectF(b.min_x - pad_x, b.min_y - pad_y, b.width + 2 * pad_x, b.height + 2 * pad_y)

    def _handle_at(self, local_pos: QPointF) -> Optional[str]:
        """Returns handle identifier ('tl', 'tr', 'bl', 'br') if local_pos is near a corner."""
        if not self.isSelected() or self.item.locked or not self.item.visible or self.item.original_bounds is None:
            return None
        b = self.item.original_bounds
        scale = max(0.0001, (math.hypot(self.item.transform.a, self.item.transform.b) + math.hypot(self.item.transform.c, self.item.transform.d)) / 2.0)
        # 3.0 mm hit radius in scene mm
        hit_radius = 3.0 / scale
        corners = {
            "tl": QPointF(b.min_x, b.min_y),
            "tr": QPointF(b.max_x, b.min_y),
            "bl": QPointF(b.min_x, b.max_y),
            "br": QPointF(b.max_x, b.max_y),
        }
        for name, c in corners.items():
            if abs(local_pos.x() - c.x()) <= hit_radius and abs(local_pos.y() - c.y()) <= hit_radius:
                return name
        return None

    def _cursor_for_handle(self, handle: str) -> Qt.CursorShape:
        if self.item.original_bounds is None:
            return Qt.ArrowCursor
        ob = self.item.original_bounds
        loc_corners = {
            "tl": Point(ob.min_x, ob.min_y),
            "tr": Point(ob.max_x, ob.min_y),
            "bl": Point(ob.min_x, ob.max_y),
            "br": Point(ob.max_x, ob.max_y),
        }
        loc_pt = loc_corners.get(handle)
        if loc_pt is None:
            return Qt.ArrowCursor
        cb = self.item.current_bounds
        if cb is None:
            return Qt.ArrowCursor
        sc_pt = self.item.transform.transform_point(loc_pt)
        vx = sc_pt.x - cb.center.x
        vy = sc_pt.y - cb.center.y
        if vx * vy > 0:
            return Qt.SizeFDiagCursor
        else:
            return Qt.SizeBDiagCursor

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent):
        if self.isSelected():
            handle = self._handle_at(event.pos())
            if handle:
                self.setCursor(self._cursor_for_handle(handle))
            else:
                self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.setCursor(Qt.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.LeftButton and self.isSelected():
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing_handle = handle
                self._resize_start_transform = copy.deepcopy(self.item.transform)
                event.accept()
                return
        self._resizing_handle = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing_handle and self._resize_start_transform and self.item.original_bounds:
            ob = self.item.original_bounds
            t0 = self._resize_start_transform

            # Check if user holds Alt for center-based proportional scaling
            scale_from_center = bool(event.modifiers() & Qt.AltModifier)

            if scale_from_center:
                loc_anchor = Point(ob.center.x, ob.center.y)
            else:
                corners = {
                    "tl": (Point(ob.min_x, ob.min_y), Point(ob.max_x, ob.max_y)),  # (handle, opposite anchor)
                    "tr": (Point(ob.max_x, ob.min_y), Point(ob.min_x, ob.max_y)),
                    "bl": (Point(ob.min_x, ob.max_y), Point(ob.max_x, ob.min_y)),
                    "br": (Point(ob.max_x, ob.max_y), Point(ob.min_x, ob.min_y)),
                }
                _, loc_anchor = corners[self._resizing_handle]

            handle_corners = {
                "tl": Point(ob.min_x, ob.min_y),
                "tr": Point(ob.max_x, ob.min_y),
                "bl": Point(ob.min_x, ob.max_y),
                "br": Point(ob.max_x, ob.max_y),
            }
            loc_handle = handle_corners[self._resizing_handle]

            anc_scene = t0.transform_point(loc_anchor)
            h_start_scene = t0.transform_point(loc_handle)

            v0_x = h_start_scene.x - anc_scene.x
            v0_y = h_start_scene.y - anc_scene.y
            denom = v0_x * v0_x + v0_y * v0_y

            if denom > 1e-6:
                cur_scene = event.scenePos()
                v_x = cur_scene.x() - anc_scene.x
                v_y = cur_scene.y() - anc_scene.y

                # Proportional ratio via projection onto diagonal
                r = (v_x * v0_x + v_y * v0_y) / denom
                scale0 = math.hypot(t0.a, t0.b)
                min_r = 0.01 / max(1e-4, scale0)
                r = max(min_r, r)

                new_a = t0.a * r
                new_b = t0.b * r
                new_c = t0.c * r
                new_d = t0.d * r
                new_tx = anc_scene.x - (new_a * loc_anchor.x + new_c * loc_anchor.y)
                new_ty = anc_scene.y - (new_b * loc_anchor.x + new_d * loc_anchor.y)

                self.item.transform.a = new_a
                self.item.transform.b = new_b
                self.item.transform.c = new_c
                self.item.transform.d = new_d
                self.item.transform.tx = new_tx
                self.item.transform.ty = new_ty

                self.sync_from_transform()

                # Notify canvas of live update so status bar and transform dock stay in sync
                scene = self.scene()
                if scene:
                    for view in scene.views():
                        if hasattr(view, "item_transformed_live"):
                            view.item_transformed_live.emit()

            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing_handle:
            self._resizing_handle = None
            self._resize_start_transform = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def paint(self, painter: QPainter, option, widget=None):
        if not self.item.visible:
            return
        painter.setRenderHint(QPainter.Antialiasing, True)

        pens_dict = {p.pen_id: p for p in self.doc.pens}
        scale = max(0.0001, (math.hypot(self.item.transform.a, self.item.transform.b) + math.hypot(self.item.transform.c, self.item.transform.d)) / 2.0)

        # Draw paths
        for path in self.item.paths:
            orig_pen = pens_dict.get(path.pen_id)
            if orig_pen is None or not orig_pen.enabled:
                continue

            eff_pen_id = orig_pen.effective_pen_id
            pen = pens_dict.get(eff_pen_id, orig_pen)

            qcolor = QColor(pen.color_hex)
            eff_width = pen.width_mm / scale
            qpen = QPen(qcolor, eff_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(qpen)
            painter.setBrush(Qt.NoBrush)

            if path.segments:
                qpath = QPainterPath()
                first_start = path.segments[0].start
                qpath.moveTo(first_start[0], first_start[1])
                for seg in path.segments:
                    if isinstance(seg, LineSegment):
                        qpath.lineTo(seg.end[0], seg.end[1])
                    elif isinstance(seg, QuadraticBezierSegment):
                        qpath.quadTo(
                            seg.control[0], seg.control[1],
                            seg.end[0], seg.end[1],
                        )
                    elif isinstance(seg, CubicBezierSegment):
                        qpath.cubicTo(
                            seg.control1[0], seg.control1[1],
                            seg.control2[0], seg.control2[1],
                            seg.end[0], seg.end[1],
                        )
                    elif isinstance(seg, ArcSegment):
                        if seg.cubics:
                            for c in seg.cubics:
                                qpath.cubicTo(
                                    c.control1[0], c.control1[1],
                                    c.control2[0], c.control2[1],
                                    c.end[0], c.end[1],
                                )
                        else:
                            qpath.lineTo(seg.end[0], seg.end[1])
                if path.closed:
                    qpath.closeSubpath()
                painter.drawPath(qpath)
            elif len(path.points) >= 2:
                poly = QPolygonF([QPointF(float(pt[0]), float(pt[1])) for pt in path.points])
                if path.closed:
                    painter.drawPolygon(poly)
                else:
                    painter.drawPolyline(poly)

        # Selection rectangle and handles or Out-of-bounds warning
        b = self.item.original_bounds
        if b is not None:
            pb = self.doc.page.plottable_box
            cb = self.item.current_bounds
            is_oob = (cb is not None and not pb.contains_box(cb))

            if self.isSelected():
                sel_color = QColor("#e65100") if is_oob else QColor("#0078d4")
                sel_pen = QPen(sel_color, 1.0 / scale, Qt.DashLine)
                painter.setPen(sel_pen)
                painter.setBrush(Qt.NoBrush)
                rect = QRectF(b.min_x, b.min_y, b.width, b.height)
                painter.drawRect(rect)

                # Corner handles (white square with selection color border)
                h_brush = QBrush(QColor("#ffffff"))
                h_pen = QPen(sel_color, 1.2 / scale)
                painter.setBrush(h_brush)
                painter.setPen(h_pen)
                h_size = 3.0 / scale
                for corner in [
                    rect.topLeft(), rect.topRight(),
                    rect.bottomLeft(), rect.bottomRight()
                ]:
                    painter.drawRect(QRectF(corner.x() - h_size / 2, corner.y() - h_size / 2, h_size, h_size))
            elif is_oob:
                # Subtle dotted warning box when not selected but out of bounds
                warn_pen = QPen(QColor(230, 81, 0, 160), 0.8 / scale, Qt.DotLine)
                painter.setPen(warn_pen)
                painter.setBrush(Qt.NoBrush)
                rect = QRectF(b.min_x, b.min_y, b.width, b.height)
                painter.drawRect(rect)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            new_pos: QPointF = value
            # Sync position back to item transform
            self.item.transform.tx = new_pos.x()
            self.item.transform.ty = new_pos.y()
        return super().itemChange(change, value)

    def sync_from_transform(self):
        """Update QGraphicsItem position and scale transform from model."""
        self.prepareGeometryChange()
        self.setVisible(self.item.visible)
        self.setFlag(QGraphicsItem.ItemIsMovable, not self.item.locked)
        self.setPos(self.item.transform.tx, self.item.transform.ty)
        self.setTransform(
            QTransform(
                self.item.transform.a,
                self.item.transform.b,
                self.item.transform.c,
                self.item.transform.d,
                0.0,
                0.0,
            )
        )
        self.update()
