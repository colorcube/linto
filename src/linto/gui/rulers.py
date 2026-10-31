"""Millimeter rulers for LINTO canvas."""

from __future__ import annotations
import math
from typing import Optional
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget, QGraphicsView


RULER_BREADTH = 24  # Width of vertical ruler or height of horizontal ruler in pixels


class RulerWidget(QWidget):
    """
    Ruler widget displaying millimeter coordinates with adaptive tick spacing.
    """
    HORIZONTAL = 0
    VERTICAL = 1

    def __init__(self, orientation: int, view: QGraphicsView, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.orientation = orientation
        self.view = view
        self.cursor_pos_mm: Optional[float] = None
        self.setFont(QFont("Monospace", 8))

        if self.orientation == self.HORIZONTAL:
            self.setFixedHeight(RULER_BREADTH)
        else:
            self.setFixedWidth(RULER_BREADTH)

    def set_cursor_pos(self, val_mm: Optional[float]):
        self.cursor_pos_mm = val_mm
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        # Background
        painter.fillRect(self.rect(), QColor("#f0f0f0"))

        # Border line
        pen_border = QPen(QColor("#cccccc"), 1)
        painter.setPen(pen_border)
        if self.orientation == self.HORIZONTAL:
            painter.drawLine(0, RULER_BREADTH - 1, self.width(), RULER_BREADTH - 1)
        else:
            painter.drawLine(RULER_BREADTH - 1, 0, RULER_BREADTH - 1, self.height())

        # Determine visible scene range
        if not self.view.scene():
            return

        viewport = self.view.viewport()
        top_left_scene = self.view.mapToScene(0, 0)
        bot_right_scene = self.view.mapToScene(viewport.width(), viewport.height())

        if self.orientation == self.HORIZONTAL:
            start_mm = top_left_scene.x()
            end_mm = bot_right_scene.x()
        else:
            start_mm = top_left_scene.y()
            end_mm = bot_right_scene.y()

        span_mm = abs(end_mm - start_mm)
        if span_mm <= 0:
            return

        # Adaptive tick step (1, 2, 5, 10, 20, 50, 100 mm)
        view_len = self.width() if self.orientation == self.HORIZONTAL else self.height()
        px_per_mm = view_len / span_mm

        if px_per_mm > 5.0:
            major_step = 10.0
            mid_step = 5.0
            minor_step = 1.0
        elif px_per_mm > 1.5:
            major_step = 20.0
            mid_step = 10.0
            minor_step = 5.0
        elif px_per_mm > 0.5:
            major_step = 50.0
            mid_step = 25.0
            minor_step = 10.0
        else:
            major_step = 100.0
            mid_step = 50.0
            minor_step = 20.0

        # Draw ticks
        first_tick = math.floor(min(start_mm, end_mm) / minor_step) * minor_step
        last_tick = math.ceil(max(start_mm, end_mm) / minor_step) * minor_step

        pen_minor = QPen(QColor("#bbbbbb"), 1)
        pen_major = QPen(QColor("#666666"), 1)
        pen_text = QColor("#333333")

        t = first_tick
        while t <= last_tick:
            # Map mm to pixel in this widget
            if self.orientation == self.HORIZONTAL:
                p_scene = QPointF(t, 0)
                p_view = self.view.mapFromScene(p_scene)
                pos = p_view.x()
            else:
                p_scene = QPointF(0, t)
                p_view = self.view.mapFromScene(p_scene)
                pos = p_view.y()

            is_major = abs(t % major_step) < 1e-4
            is_mid = abs(t % mid_step) < 1e-4

            if is_major:
                painter.setPen(pen_major)
                tick_len = RULER_BREADTH * 0.5
            elif is_mid:
                painter.setPen(pen_minor)
                tick_len = RULER_BREADTH * 0.35
            else:
                painter.setPen(pen_minor)
                tick_len = RULER_BREADTH * 0.2

            if self.orientation == self.HORIZONTAL:
                painter.drawLine(pos, RULER_BREADTH - tick_len, pos, RULER_BREADTH - 1)
                if is_major:
                    painter.setPen(pen_text)
                    txt = f"{int(round(t))}"
                    painter.drawText(pos + 2, 12, txt)
            else:
                painter.drawLine(RULER_BREADTH - tick_len, pos, RULER_BREADTH - 1, pos)
                if is_major:
                    painter.setPen(pen_text)
                    txt = f"{int(round(t))}"
                    painter.save()
                    painter.translate(12, pos - 2)
                    painter.rotate(-90)
                    painter.drawText(0, 0, txt)
                    painter.restore()

            t += minor_step

        # Cursor indicator
        if self.cursor_pos_mm is not None:
            if self.orientation == self.HORIZONTAL:
                p_scene = QPointF(self.cursor_pos_mm, 0)
                cur_px = self.view.mapFromScene(p_scene).x()
                painter.setPen(QPen(QColor("#e51400"), 1))
                painter.drawLine(cur_px, 0, cur_px, RULER_BREADTH)
            else:
                p_scene = QPointF(0, self.cursor_pos_mm)
                cur_px = self.view.mapFromScene(p_scene).y()
                painter.setPen(QPen(QColor("#e51400"), 1))
                painter.drawLine(0, cur_px, RULER_BREADTH, cur_px)
