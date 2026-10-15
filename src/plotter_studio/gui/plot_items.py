"""QGraphicsItem for rendering compiled PlotJob paths, travel lines and toolhead simulation."""

from __future__ import annotations
from typing import Optional, Set
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPolygonF
from PySide6.QtWidgets import QGraphicsItem
import numpy as np

from ..pipeline.compiler import PlotJob, PlotStep


class GraphicsPlotPreviewItem(QGraphicsItem):
    """
    Renders compiled PlotJob:
    - Drawn lines in true pen colors and physical widths (mm)
    - Dashed travel lines (pen-up movements)
    - Ghosted future lines during simulation scrubbing
    - Live toolhead indicator
    """
    def __init__(
        self,
        job: Optional[PlotJob] = None,
        page_rect: Optional[QRectF] = None,
        show_nodes: bool = False,
        show_travels: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.job = job
        self.page_rect = page_rect or QRectF(0, 0, 420, 297)
        self.current_step = 0 if job else 0
        if job:
            self.current_step = len(job.steps)
        self.show_travels = show_travels
        self.show_nodes = show_nodes
        self.visible_pens: Optional[Set[int]] = None  # None means all visible

        # Prevent selection/movement
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)

    def set_job(self, job: Optional[PlotJob], page_rect: Optional[QRectF] = None):
        self.prepareGeometryChange()
        self.job = job
        if page_rect is not None:
            self.page_rect = page_rect
        self.current_step = len(job.steps) if job else 0
        self.update()

    def set_simulation_step(self, step: int):
        if not self.job:
            return
        total = len(self.job.steps)
        clamped = max(0, min(total, step))
        if clamped != self.current_step:
            self.current_step = clamped
            self.update()

    def set_show_travels(self, show: bool):
        if self.show_travels != show:
            self.show_travels = show
            self.update()

    def set_show_nodes(self, show: bool):
        if self.show_nodes != show:
            self.show_nodes = show
            self.update()

    def set_visible_pens(self, pens: Optional[Set[int]]):
        self.visible_pens = pens
        self.update()

    def boundingRect(self) -> QRectF:
        pad = 20.0
        return self.page_rect.adjusted(-pad, -pad, pad, pad)

    def paint(self, painter: QPainter, option, widget=None):
        if not self.job or not self.job.steps:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        total_steps = len(self.job.steps)
        is_scrubbing = (self.current_step < total_steps)

        # 1. Ghosted future draw lines (when scrubbing)
        if is_scrubbing:
            for s_idx in range(self.current_step, total_steps):
                step = self.job.steps[s_idx]
                if step.action != "DRAW":
                    continue
                if self.visible_pens is not None and step.pen_id not in self.visible_pens:
                    continue

                layer = self.job.layers.get(step.pen_id)
                pen_color = QColor(layer.pen.color_hex if layer else "#444444")
                pen_color.setAlpha(35)  # Faint ghosting
                width = layer.pen.width_mm if layer else 0.35

                qpen = QPen(pen_color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(qpen)

                pts = step.points
                p0 = QPointF(float(pts[0, 0]), float(pts[0, 1]))
                p1 = QPointF(float(pts[1, 0]), float(pts[1, 1]))
                painter.drawLine(p0, p1)

                if self.show_nodes:
                    view_scale = abs(painter.transform().m11())
                    if view_scale < 1e-4:
                        view_scale = 1.0
                    dot_r = max(0.4, 2.2 / view_scale)
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(pen_color))
                    painter.drawEllipse(p1, dot_r, dot_r)

        # 2. Travel lines up to current_step
        if self.show_travels:
            travel_pen = QPen(QColor(0, 150, 166, 160), 0.25, Qt.DashLine, Qt.RoundCap)
            painter.setPen(travel_pen)
            for s_idx in range(self.current_step):
                step = self.job.steps[s_idx]
                if step.action == "TRAVEL":
                    if self.visible_pens is not None and step.pen_id not in self.visible_pens:
                        continue
                    p0 = step.points[0]
                    p1 = step.points[1]
                    painter.drawLine(QPointF(float(p0[0]), float(p0[1])), QPointF(float(p1[0]), float(p1[1])))

        # 3. Active drawn lines up to current_step
        last_tool_pos: Optional[QPointF] = None
        last_pen_color: QColor = QColor("#000000")

        # Collect points for node drawing if enabled
        nodes_to_draw: list[tuple[QPointF, QColor, float]] = []

        for s_idx in range(self.current_step):
            step = self.job.steps[s_idx]
            if self.visible_pens is not None and step.pen_id not in self.visible_pens:
                continue

            layer = self.job.layers.get(step.pen_id)
            color_hex = layer.pen.color_hex if layer else "#000000"
            width_mm = layer.pen.width_mm if layer else 0.35
            draw_color = QColor(color_hex)
            last_pen_color = draw_color

            if step.action == "DRAW":
                qpen = QPen(draw_color, width_mm, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
                painter.setPen(qpen)

                pts = step.points
                p0 = QPointF(float(pts[0, 0]), float(pts[0, 1]))
                p1 = QPointF(float(pts[1, 0]), float(pts[1, 1]))
                painter.drawLine(p0, p1)
                last_tool_pos = p1

                if self.show_nodes:
                    if s_idx == 0 or self.job.steps[s_idx - 1].action == "TRAVEL":
                        nodes_to_draw.append((p0, draw_color))
                    nodes_to_draw.append((p1, draw_color))

            elif step.action == "TRAVEL":
                if len(step.points) > 1:
                    last_tool_pos = QPointF(float(step.points[1, 0]), float(step.points[1, 1]))

        # 4. Draw coordinate nodes (clean, solid points)
        if self.show_nodes and nodes_to_draw:
            view_scale = abs(painter.transform().m11())
            if view_scale < 1e-4:
                view_scale = 1.0
            dot_r = max(0.4, 2.6 / view_scale)

            painter.setPen(Qt.NoPen)
            for pt, color in nodes_to_draw:
                painter.setBrush(QBrush(color))
                painter.drawEllipse(pt, dot_r, dot_r)

        # 5. Toolhead indicator at current position
        if last_tool_pos is not None:
            # Concentric crosshair/circle indicator
            painter.setBrush(QBrush(last_pen_color))
            painter.setPen(QPen(QColor(255, 255, 255), 0.5))
            painter.drawEllipse(last_tool_pos, 1.8, 1.8)

            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(33, 150, 243, 200), 0.4, Qt.DotLine))
            painter.drawEllipse(last_tool_pos, 4.0, 4.0)

            # Hairlines
            painter.setPen(QPen(QColor(33, 150, 243, 150), 0.3))
            painter.drawLine(
                QPointF(last_tool_pos.x() - 5.0, last_tool_pos.y()),
                QPointF(last_tool_pos.x() + 5.0, last_tool_pos.y()),
            )
            painter.drawLine(
                QPointF(last_tool_pos.x(), last_tool_pos.y() - 5.0),
                QPointF(last_tool_pos.x(), last_tool_pos.y() + 5.0),
            )

        painter.restore()
