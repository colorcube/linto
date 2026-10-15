"""Dock widget for Plot Mode: Pipeline parameters, pre-flight statistics, pen filters and exports."""

from __future__ import annotations
from typing import Optional, Set
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
    QScrollArea, QFileDialog, QMessageBox, QFrame
)
from ..core.document import Document
from ..pipeline.compiler import PipelineConfig, PlotJob, compile_document_to_plot_job


class PlotDockWidget(QDockWidget):
    """
    Dock widget providing pipeline controls, pre-flight inspection statistics,
    pen visibility filters, and export actions.
    """
    config_changed = Signal()
    toggle_travels = Signal(bool)
    toggle_nodes = Signal(bool)
    pen_filter_changed = Signal(object)  # Set[int] or None
    export_hpgl_requested = Signal()
    export_svg_requested = Signal()

    def __init__(self, doc: Document, parent=None):
        super().__init__("Plot-Vorschau & Ausgabe", parent)
        self.doc = doc
        self.job: Optional[PlotJob] = None
        self._pen_checkboxes: dict[int, QCheckBox] = {}

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()

    def _init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget(scroll)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # 1. Pipeline Settings
        grp_pipeline = QGroupBox("⚙️ Pipeline-Optimierung", container)
        grid_pipe = QGridLayout(grp_pipeline)
        grid_pipe.setSpacing(6)

        grid_pipe.addWidget(QLabel("Kurvenglättung:"), 0, 0)
        self.spin_flatten = QDoubleSpinBox()
        self.spin_flatten.setRange(0.01, 2.0)
        self.spin_flatten.setValue(0.05)
        self.spin_flatten.setSingleStep(0.01)
        self.spin_flatten.setSuffix(" mm")
        grid_pipe.addWidget(self.spin_flatten, 0, 1)

        grid_pipe.addWidget(QLabel("Endpunkte verbinden:"), 1, 0)
        self.spin_merge = QDoubleSpinBox()
        self.spin_merge.setRange(0.0, 5.0)
        self.spin_merge.setValue(0.10)
        self.spin_merge.setSingleStep(0.05)
        self.spin_merge.setSuffix(" mm")
        grid_pipe.addWidget(self.spin_merge, 1, 1)

        grid_pipe.addWidget(QLabel("Vereinfachen:"), 2, 0)
        self.spin_simplify = QDoubleSpinBox()
        self.spin_simplify.setRange(0.0, 2.0)
        self.spin_simplify.setValue(0.02)
        self.spin_simplify.setSingleStep(0.01)
        self.spin_simplify.setSuffix(" mm")
        grid_pipe.addWidget(self.spin_simplify, 2, 1)

        self.chk_sort = QCheckBox("Leerwege optimieren (Sortierung)")
        self.chk_sort.setChecked(True)
        grid_pipe.addWidget(self.chk_sort, 3, 0, 1, 2)

        self.chk_clip = QCheckBox("Am plottbaren Bereich beschneiden (Clip)")
        self.chk_clip.setChecked(False)
        grid_pipe.addWidget(self.chk_clip, 4, 0, 1, 2)

        self.chk_show_travels = QCheckBox("Leerfahrten (Pen-Up) anzeigen")
        self.chk_show_travels.setChecked(True)
        self.chk_show_travels.toggled.connect(self.toggle_travels.emit)
        grid_pipe.addWidget(self.chk_show_travels, 5, 0, 1, 2)

        self.chk_show_nodes = QCheckBox("Stützpunkte (Koordinaten) anzeigen")
        self.chk_show_nodes.setChecked(False)
        self.chk_show_nodes.toggled.connect(self.toggle_nodes.emit)
        grid_pipe.addWidget(self.chk_show_nodes, 6, 0, 1, 2)

        self.btn_recompute = QPushButton("🔄 Pipeline neu berechnen")
        self.btn_recompute.clicked.connect(self.config_changed.emit)
        grid_pipe.addWidget(self.btn_recompute, 7, 0, 1, 2)

        layout.addWidget(grp_pipeline)

        # 2. Pre-Flight Inspection Statistics
        grp_stats = QGroupBox("📊 Pre-Flight-Inspektion", container)
        vbox_stats = QVBoxLayout(grp_stats)
        vbox_stats.setSpacing(6)

        grid_stat_values = QGridLayout()
        grid_stat_values.setSpacing(4)

        grid_stat_values.addWidget(QLabel("✏️ Zeichenweg:"), 0, 0)
        self.lbl_draw = QLabel("0.00 m")
        self.lbl_draw.setStyleSheet("font-weight: bold;")
        grid_stat_values.addWidget(self.lbl_draw, 0, 1)

        grid_stat_values.addWidget(QLabel("✈️ Leerweg:"), 1, 0)
        self.lbl_travel = QLabel("0.00 m")
        self.lbl_travel.setStyleSheet("font-weight: bold; color: #00838f;")
        grid_stat_values.addWidget(self.lbl_travel, 1, 1)

        grid_stat_values.addWidget(QLabel("⚡ Ersparnis:"), 2, 0)
        self.lbl_savings = QLabel("0 %")
        grid_stat_values.addWidget(self.lbl_savings, 2, 1)

        grid_stat_values.addWidget(QLabel("🔄 Stiftwechsel:"), 3, 0)
        self.lbl_pen_changes = QLabel("0")
        grid_stat_values.addWidget(self.lbl_pen_changes, 3, 1)

        grid_stat_values.addWidget(QLabel("⏱️ Geschätzte Zeit:"), 4, 0)
        self.lbl_duration = QLabel("00m 00s")
        self.lbl_duration.setStyleSheet("font-weight: bold; color: #2e7d32; font-size: 13px;")
        grid_stat_values.addWidget(self.lbl_duration, 4, 1)

        grid_stat_values.addWidget(QLabel("📍 Stützpunkte:"), 5, 0)
        self.lbl_points = QLabel("0")
        grid_stat_values.addWidget(self.lbl_points, 5, 1)

        vbox_stats.addLayout(grid_stat_values)

        # Warning / Info box
        self.lbl_warnings = QLabel("✓ Alle Pfade im plottbaren Bereich")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet("""
            padding: 6px;
            background-color: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #c8e6c9;
            border-radius: 4px;
            font-size: 11px;
        """)
        vbox_stats.addWidget(self.lbl_warnings)

        layout.addWidget(grp_stats)

        # 3. Pen Visibility Filters
        self.grp_pens = QGroupBox("🎨 Stift-Filter", container)
        self.vbox_pens = QVBoxLayout(self.grp_pens)
        layout.addWidget(self.grp_pens)

        # 4. Export & Actions
        grp_export = QGroupBox("💾 Ausgabe & Export", container)
        vbox_export = QVBoxLayout(grp_export)
        vbox_export.setSpacing(6)

        self.btn_export_hpgl = QPushButton("📄 Plotdatei (.hpgl) exportieren...")
        self.btn_export_hpgl.clicked.connect(self.export_hpgl_requested.emit)
        vbox_export.addWidget(self.btn_export_hpgl)

        self.btn_export_svg = QPushButton("🎨 Plot-Vektoren (.svg) exportieren...")
        self.btn_export_svg.clicked.connect(self.export_svg_requested.emit)
        vbox_export.addWidget(self.btn_export_svg)

        layout.addWidget(grp_export)

        layout.addStretch()
        scroll.setWidget(container)
        self.setWidget(scroll)

    def get_pipeline_config(self) -> PipelineConfig:
        return PipelineConfig(
            flatten_tolerance_mm=self.spin_flatten.value(),
            merge_tolerance_mm=self.spin_merge.value(),
            simplify_tolerance_mm=self.spin_simplify.value(),
            sort_paths=self.chk_sort.isChecked(),
            clip_to_plottable=self.chk_clip.isChecked(),
        )

    def set_job(self, job: Optional[PlotJob]):
        self.job = job
        if not job:
            self.lbl_draw.setText("0.00 m")
            self.lbl_travel.setText("0.00 m")
            self.lbl_savings.setText("0 %")
            self.lbl_pen_changes.setText("0")
            self.lbl_duration.setText("00m 00s")
            self.lbl_points.setText("0")
            self.lbl_warnings.setText("Keine Pfade vorhanden")
            self.lbl_warnings.setStyleSheet("padding: 4px; color: #777;")
            return

        draw_m = job.total_draw_mm / 1000.0
        travel_m = job.total_travel_mm / 1000.0
        self.lbl_draw.setText(f"{draw_m:.2f} m")
        self.lbl_travel.setText(f"{travel_m:.2f} m")
        self.lbl_savings.setText(f"{job.travel_savings_pct:.1f} % durch Sortierung")
        self.lbl_pen_changes.setText(str(job.pen_changes))
        self.lbl_duration.setText(job.formatted_duration)
        self.lbl_points.setText(f"{job.total_points:,}".replace(",", "."))

        # Warnings display
        if job.warnings:
            msg = "\n".join(job.warnings)
            self.lbl_warnings.setText(f"⚠️ {msg}")
            self.lbl_warnings.setStyleSheet("""
                padding: 6px;
                background-color: #fff3e0;
                color: #e65100;
                border: 1px solid #ffe0b2;
                border-radius: 4px;
                font-size: 11px;
            """)
        else:
            self.lbl_warnings.setText("✓ Alle Pfade im plottbaren Bereich")
            self.lbl_warnings.setStyleSheet("""
                padding: 6px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
                border-radius: 4px;
                font-size: 11px;
            """)

        self._update_pen_filters(job)

    def _update_pen_filters(self, job: PlotJob):
        # Clear existing
        while self.vbox_pens.count():
            item = self.vbox_pens.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._pen_checkboxes.clear()

        if not job.layers:
            lbl = QLabel("Keine Stifte verwendet")
            lbl.setStyleSheet("color: #888; font-size: 11px;")
            self.vbox_pens.addWidget(lbl)
            return

        for pen_id, layer in sorted(job.layers.items()):
            color = layer.pen.color_hex
            name = layer.pen.name
            line_count = len(layer.lines)
            draw_m = layer.draw_distance_mm / 1000.0

            chk = QCheckBox(f"{name} ({line_count} Pfade, {draw_m:.2f} m)")
            chk.setChecked(True)
            chk.setStyleSheet(f"""
                QCheckBox {{
                    font-size: 11px;
                }}
                QCheckBox::indicator:checked {{
                    background-color: {color};
                    border: 1px solid #444;
                }}
            """)
            chk.toggled.connect(self._on_pen_filter_toggled)
            self._pen_checkboxes[pen_id] = chk
            self.vbox_pens.addWidget(chk)

    def _on_pen_filter_toggled(self):
        active_pens: Set[int] = set()
        all_checked = True
        for pen_id, chk in self._pen_checkboxes.items():
            if chk.isChecked():
                active_pens.add(pen_id)
            else:
                all_checked = False

        if all_checked:
            self.pen_filter_changed.emit(None)  # None = show all
        else:
            self.pen_filter_changed.emit(active_pens)
