"""Simulation playback and scrubber bar widget for the Plot Mode."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QSlider, QLabel, QComboBox
)
from ..pipeline.compiler import PlotJob
from .icons import get_icon


class PlotSimulationBar(QWidget):
    """
    Bottom simulation bar providing playback controls, speed selection,
    and a scrubber slider for interactive plot simulation.
    """
    step_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.job: Optional[PlotJob] = None
        self.total_steps = 0
        self.current_step = 0
        self.is_playing = False

        self._timer = QTimer(self)
        self._timer.setInterval(40)  # 25 fps
        self._timer.timeout.connect(self._on_timer_tick)

        self._speed_multiplier = 1

        self._init_ui()

    def _init_ui(self):
        self.setFixedHeight(48)
        self.setStyleSheet("""
            PlotSimulationBar {
                background-color: #2b2b2b;
                border-top: 1px solid #444;
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #3c3f41;
                border: 1px solid #555;
                color: #f0f0f0;
                border-radius: 3px;
                padding: 4px 10px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #4c5052;
            }
            QPushButton:pressed {
                background-color: #2d2f30;
            }
            QComboBox {
                background-color: #3c3f41;
                border: 1px solid #555;
                color: #f0f0f0;
                padding: 2px 6px;
                border-radius: 3px;
            }
            QLabel {
                color: #cccccc;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #555;
                height: 6px;
                background: #1e1e1e;
                margin: 2px 0;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #2196f3;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #777;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(10)

        # Rewind button
        self.btn_rewind = QPushButton()
        self.btn_rewind.setIcon(get_icon("skip-back", size=16, color="#f0f0f0"))
        self.btn_rewind.setToolTip(self.tr("Jump to start"))
        self.btn_rewind.setFixedWidth(32)
        self.btn_rewind.clicked.connect(self.rewind)
        layout.addWidget(self.btn_rewind)

        # Play/Pause button
        self.btn_play = QPushButton(self.tr("Play"))
        self.btn_play.setIcon(get_icon("play", size=16, color="#f0f0f0"))
        self.btn_play.setFixedWidth(100)
        self.btn_play.clicked.connect(self.toggle_play)
        layout.addWidget(self.btn_play)

        # Forward button
        self.btn_forward = QPushButton()
        self.btn_forward.setIcon(get_icon("skip-forward", size=16, color="#f0f0f0"))
        self.btn_forward.setToolTip(self.tr("Jump to end"))
        self.btn_forward.setFixedWidth(32)
        self.btn_forward.clicked.connect(self.jump_to_end)
        layout.addWidget(self.btn_forward)

        # Speed selector
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["1x", "2x", "5x", "10x", "25x"])
        self.combo_speed.setCurrentIndex(2)  # Default 5x
        self._speed_multiplier = 5
        self.combo_speed.currentIndexChanged.connect(self._on_speed_changed)
        layout.addWidget(self.combo_speed)

        # Scrubber slider
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(100)
        self.slider.valueChanged.connect(self._on_slider_value_changed)
        layout.addWidget(self.slider, 1)

        # Step and progress label
        self.lbl_progress = QLabel(
            self.tr("Step: %1 / %2 (%3 %)").replace("%1", "0").replace("%2", "0").replace("%3", "100")
        )
        self.lbl_progress.setMinimumWidth(160)
        layout.addWidget(self.lbl_progress)

        # Active pen label
        self.lbl_pen = QLabel(self.tr("Pen: -"))
        self.lbl_pen.setMinimumWidth(120)
        layout.addWidget(self.lbl_pen)

    def set_job(self, job: Optional[PlotJob]):
        self.job = job
        self.pause()
        if job and job.steps:
            self.total_steps = len(job.steps)
            self.slider.setRange(0, self.total_steps)
            self.slider.setValue(self.total_steps)
            self.current_step = self.total_steps
        else:
            self.total_steps = 0
            self.slider.setRange(0, 0)
            self.slider.setValue(0)
            self.current_step = 0
        self._update_labels()

    def set_step(self, step: int):
        """Externally set active simulation step (e.g. during live device streaming)."""
        self.pause()
        clamped = max(0, min(self.total_steps, step))
        self.slider.blockSignals(True)
        self.slider.setValue(clamped)
        self.slider.blockSignals(False)
        self.current_step = clamped
        self._update_labels()

    def rewind(self):
        self.pause()
        self.slider.setValue(0)

    def jump_to_end(self):
        self.pause()
        self.slider.setValue(self.total_steps)

    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        if self.total_steps == 0:
            return
        if self.current_step >= self.total_steps:
            self.slider.setValue(0)
        self.is_playing = True
        self.btn_play.setIcon(get_icon("pause", size=16, color="#f0f0f0"))
        self.btn_play.setText(self.tr("Pause"))
        self._timer.start()

    def pause(self):
        self.is_playing = False
        self.btn_play.setIcon(get_icon("play", size=16, color="#f0f0f0"))
        self.btn_play.setText(self.tr("Play"))
        self._timer.stop()

    def _on_speed_changed(self, index: int):
        speeds = [1, 2, 5, 10, 25]
        self._speed_multiplier = speeds[index] if index < len(speeds) else 1

    def _on_timer_tick(self):
        if not self.job or self.total_steps == 0:
            self.pause()
            return

        increment = max(1, int(self._speed_multiplier * (self.total_steps / 250.0)))
        next_step = self.current_step + increment

        if next_step >= self.total_steps:
            self.slider.setValue(self.total_steps)
            self.pause()
        else:
            self.slider.setValue(next_step)

    def _on_slider_value_changed(self, val: int):
        self.current_step = val
        self._update_labels()
        self.step_changed.emit(val)

    def _update_labels(self):
        if self.total_steps > 0:
            pct = int((self.current_step / float(self.total_steps)) * 100.0)
            self.lbl_progress.setText(
                self.tr("Step: %1 / %2 (%3 %)")
                .replace("%1", str(self.current_step))
                .replace("%2", str(self.total_steps))
                .replace("%3", str(pct))
            )
        else:
            self.lbl_progress.setText(self.tr("No paths available"))

        if self.job and self.current_step > 0 and self.current_step <= len(self.job.steps):
            active_step = self.job.steps[self.current_step - 1]
            layer = self.job.layers.get(active_step.pen_id)
            pen_name = layer.pen.name if layer else self.tr("Pen %1").replace("%1", str(active_step.pen_id))
            action_desc = self.tr("Draw") if active_step.action == "DRAW" else self.tr("Travel")
            self.lbl_pen.setText(f"{pen_name} ({action_desc})")
        else:
            self.lbl_pen.setText(self.tr("Pen: -"))
