"""Interactive QGraphicsItem representing an ImportItem on the canvas."""

from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from PySide6.QtCore import Qt, QRectF, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QPolygonF, QTransform
from PySide6.QtWidgets import QGraphicsItem, QGraphicsSceneMouseEvent

if TYPE_CHECKING:
    from ..core.document import Document, ImportItem, VectorPath


class GraphicsImportItem(QGraphicsItem):
    """
    QGraphicsItem rendering an ImportItem with true millimeter coordinates and WYSIWYG pens.
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

        # Synchronize scale and position from item model
        self.sync_from_transform()

    def boundingRect(self) -> QRectF:
        if self.item.original_bounds is None:
            return QRectF()
        b = self.item.original_bounds
        scale_x = abs(self.item.transform.a) if abs(self.item.transform.a) > 1e-6 else 1.0
        scale_y = abs(self.item.transform.d) if abs(self.item.transform.d) > 1e-6 else 1.0
        # 3.0 mm scene padding for stroke thickness and selection handles
        pad_x = 3.0 / scale_x
        pad_y = 3.0 / scale_y
        return QRectF(b.min_x - pad_x, b.min_y - pad_y, b.width + 2 * pad_x, b.height + 2 * pad_y)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)

        pens_dict = {p.pen_id: p for p in self.doc.pens}
        scale = max(0.0001, (abs(self.item.transform.a) + abs(self.item.transform.d)) / 2.0)

        # Draw paths
        for path in self.item.paths:
            # Check remapped effective pen
            orig_pen = pens_dict.get(path.pen_id)
            if orig_pen is None or not orig_pen.enabled:
                continue

            eff_pen_id = orig_pen.effective_pen_id
            pen = pens_dict.get(eff_pen_id, orig_pen)

            qcolor = QColor(pen.color_hex)
            # Physical stroke width in scene mm: divide by scale so Qt painter draws exact mm width on paper
            eff_width = pen.width_mm / scale
            qpen = QPen(qcolor, eff_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(qpen)
            painter.setBrush(Qt.NoBrush)

            if len(path.points) >= 2:
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

                # Corner handles
                h_brush = QBrush(QColor("#ffffff"))
                h_pen = QPen(sel_color, 1.0 / scale)
                painter.setBrush(h_brush)
                painter.setPen(h_pen)
                h_size = 2.5 / scale
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
