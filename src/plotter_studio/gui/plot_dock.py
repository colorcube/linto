"""Dock widget for Plot Mode: Pipeline parameters, pre-flight statistics, pen filters,
device connection & live plot control, and exports.
"""

from __future__ import annotations

import threading
from typing import Optional, Set

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
    QScrollArea, QFileDialog, QMessageBox, QFrame, QComboBox, QProgressBar
)
from ..core.document import Document
from ..pipeline.compiler import PipelineConfig, PlotJob, compile_document_to_plot_job
from ..device import (
    get_default_profile,
    HPGLEmitter,
    list_serial_ports,
    probe_plotter,
    SerialStreamer,
    StreamerState,
    ProbeResult,
)


class StreamerSignalBridge(QObject):
    """Bridge for cross-thread communication from background worker to Qt main thread."""
    progress = Signal(int, int, float, int, float)  # step_idx, total_cmds, pct, pen, drawn_m
    status = Signal(str, str)                       # state_name, message
    finished = Signal(bool, str)                    # success, message
    probe_done = Signal(object)                     # ProbeResult


class PlotDockWidget(QDockWidget):
    """
    Dock widget providing pipeline controls, pre-flight inspection statistics,
    pen visibility filters, device streaming controls, and export actions.
    """
    config_changed = Signal()
    toggle_travels = Signal(bool)
    toggle_nodes = Signal(bool)
    pen_filter_changed = Signal(object)  # Set[int] or None
    export_hpgl_requested = Signal()
    export_svg_requested = Signal()
    stream_step_changed = Signal(int)

    def __init__(self, doc: Document, parent=None):
        super().__init__("Plot-Vorschau & Ausgabe", parent)
        self.doc = doc
        self.job: Optional[PlotJob] = None
        self._pen_checkboxes: dict[int, QCheckBox] = {}
        self._pipeline_dirty = False

        self._bridge = StreamerSignalBridge()
        self._bridge.progress.connect(self._on_stream_progress)
        self._bridge.status.connect(self._on_stream_status)
        self._bridge.finished.connect(self._on_stream_finished)
        self._bridge.probe_done.connect(self._on_probe_done)

        self._streamer: Optional[SerialStreamer] = None
        self._probe_thread: Optional[threading.Thread] = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()
        self.refresh_ports()

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

        # Connect parameter modifications to dirty tracking
        self.spin_flatten.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_merge.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_simplify.valueChanged.connect(self._on_pipeline_param_changed)
        self.chk_sort.toggled.connect(self._on_pipeline_param_changed)
        self.chk_clip.toggled.connect(self._on_pipeline_param_changed)

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

        # 4. Device Connection & Live Plot Control
        grp_device = QGroupBox("🖨️ Plotter-Verbindung & Ausgabe", container)
        vbox_device = QVBoxLayout(grp_device)
        vbox_device.setSpacing(8)

        grid_conn = QGridLayout()
        grid_conn.setSpacing(4)
        grid_conn.addWidget(QLabel("Port / Ziel:"), 0, 0)

        self.combo_port = QComboBox()
        self.combo_port.setEditable(True)
        self.combo_port.setToolTip("Serielle Schnittstelle (z.B. /dev/ttyUSB0, COM3) oder TCP (tcp://127.0.0.1:9999)")
        grid_conn.addWidget(self.combo_port, 0, 1)

        self.btn_refresh_ports = QPushButton("🔄")
        self.btn_refresh_ports.setFixedWidth(32)
        self.btn_refresh_ports.setToolTip("Schnittstellenliste neu einlesen")
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)
        grid_conn.addWidget(self.btn_refresh_ports, 0, 2)

        grid_conn.addWidget(QLabel("Ränder (Clip):"), 1, 0)
        self.combo_margins = QComboBox()
        self.combo_margins.addItem("EXP (Erweitert: 25 / 5 / 5 / 5 mm)", "exp")
        self.combo_margins.addItem("NORM (Normal: 25 / 10 / 10 / 10 mm)", "norm")
        self.combo_margins.addItem("TYPE1 (38 / 10 / 10 / 10 mm)", "type1")
        self.combo_margins.addItem("TYPE3 (38 / 5 / 5 / 5 mm)", "type3")
        grid_conn.addWidget(self.combo_margins, 1, 1, 1, 2)

        grid_conn.addWidget(QLabel("Drehung:"), 2, 0)
        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem("0° (Standard)", 0)
        self.combo_rotation.addItem("90° (Quer/Vorschub)", 90)
        self.combo_rotation.addItem("180°", 180)
        self.combo_rotation.addItem("270°", 270)
        grid_conn.addWidget(self.combo_rotation, 2, 1, 1, 2)

        hbox_axes = QHBoxLayout()
        hbox_axes.setSpacing(6)
        self.chk_swap_xy = QCheckBox("X↔Y")
        self.chk_swap_xy.setToolTip("Achsentausch: X- und Y-Achsen vertauschen (z.B. Rollenvorschub ↔ Wagen)")
        self.chk_invert_x = QCheckBox("X inv.")
        self.chk_invert_x.setToolTip("X-Achse spiegeln")
        self.chk_invert_y = QCheckBox("Y inv.")
        self.chk_invert_y.setToolTip("Y-Achse spiegeln")
        hbox_axes.addWidget(self.chk_swap_xy)
        hbox_axes.addWidget(self.chk_invert_x)
        hbox_axes.addWidget(self.chk_invert_y)
        grid_conn.addLayout(hbox_axes, 3, 0, 1, 3)

        vbox_device.addLayout(grid_conn)

        self.btn_probe = QPushButton("🔍 Plotter prüfen (Inquiry)")
        self.btn_probe.clicked.connect(self.start_probe)
        vbox_device.addWidget(self.btn_probe)

        self.lbl_probe_status = QLabel("Kein Plotter geprüft")
        self.lbl_probe_status.setWordWrap(True)
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px;
            background-color: #f5f5f5;
            color: #616161;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            font-size: 11px;
        """)
        vbox_device.addWidget(self.lbl_probe_status)

        hbox_ctrl = QHBoxLayout()
        hbox_ctrl.setSpacing(6)

        self.btn_start_plot = QPushButton("🚀 Plot senden")
        self.btn_start_plot.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 6px;")
        self.btn_start_plot.setEnabled(False)
        self.btn_start_plot.clicked.connect(self.start_plot)
        hbox_ctrl.addWidget(self.btn_start_plot)

        self.btn_pause_plot = QPushButton("⏸ Pause")
        self.btn_pause_plot.setEnabled(False)
        self.btn_pause_plot.clicked.connect(self.toggle_pause)
        hbox_ctrl.addWidget(self.btn_pause_plot)

        self.btn_abort_plot = QPushButton("⏹ Abbrechen")
        self.btn_abort_plot.setEnabled(False)
        self.btn_abort_plot.setStyleSheet("color: #c62828;")
        self.btn_abort_plot.clicked.connect(self.abort_plot)
        hbox_ctrl.addWidget(self.btn_abort_plot)

        vbox_device.addLayout(hbox_ctrl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        vbox_device.addWidget(self.progress_bar)

        self.lbl_stream_status = QLabel("Bereit")
        self.lbl_stream_status.setStyleSheet("color: #555; font-size: 11px;")
        self.lbl_stream_status.setWordWrap(True)
        vbox_device.addWidget(self.lbl_stream_status)

        layout.addWidget(grp_device)

        # 5. Export & Actions
        grp_export = QGroupBox("💾 Datei-Export", container)
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

    def refresh_ports(self):
        """Scan available serial ports, virtual plotter symlinks, and TCP."""
        current = self.combo_port.currentText().strip()
        self.combo_port.clear()
        ports = list_serial_ports()
        for p in ports:
            self.combo_port.addItem(p)

        if current:
            idx = self.combo_port.findText(current)
            if idx >= 0:
                self.combo_port.setCurrentIndex(idx)
            else:
                self.combo_port.setEditText(current)
        elif ports:
            self.combo_port.setCurrentIndex(0)

    def start_probe(self):
        """Inquire connected plotter (OI/OF/OH) in background thread."""
        port = self.combo_port.currentText().strip()
        if not port:
            self.lbl_probe_status.setText("⚠️ Kein Port ausgewählt")
            return

        self.btn_probe.setEnabled(False)
        self.lbl_probe_status.setText(f"Prüfe {port}...")
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px;
            background-color: #fff9c4;
            color: #f57f17;
            border: 1px solid #fff59d;
            border-radius: 4px;
            font-size: 11px;
        """)

        def _probe_worker():
            res = probe_plotter(port, timeout=1.5)
            self._bridge.probe_done.emit(res)

        self._probe_thread = threading.Thread(target=_probe_worker, daemon=True, name="PlotterProbeThread")
        self._probe_thread.start()

    def _on_probe_done(self, result: ProbeResult):
        self.btn_probe.setEnabled(True)
        if result.success:
            clip_info = ""
            if result.hard_clip_mm:
                clip_info = f" • Hard-Clip: {result.hard_clip_mm[0]:.0f}×{result.hard_clip_mm[1]:.0f} mm"
            pin_info = ""
            if result.cts is not None:
                pin_info = " • CTS: Bereit" if result.cts else " • ⚠️ CTS: Low"
            self.lbl_probe_status.setText(
                f"✓ {result.model} ({result.detected_format}, {result.units_per_mm:.0f} U/mm){clip_info}{pin_info}"
            )
            self.lbl_probe_status.setStyleSheet("""
                padding: 6px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
                border-radius: 4px;
                font-size: 11px;
            """)
        else:
            self.lbl_probe_status.setText(f"⚠️ {result.error_message}")
            self.lbl_probe_status.setStyleSheet("""
                padding: 6px;
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #ffcdd2;
                border-radius: 4px;
                font-size: 11px;
            """)

    def _on_pipeline_param_changed(self, *args):
        """Called when any pipeline optimization parameter is modified by the user."""
        self._pipeline_dirty = True
        self.btn_recompute.setText("⚠️ Pipeline neu berechnen (geändert)")
        self.btn_recompute.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                background-color: #fff3e0;
                color: #e65100;
                border: 1px solid #ffb74d;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #ffe0b2;
            }
        """)
        self.lbl_warnings.setText("⚠️ Einstellungen geändert – Vorschau noch nicht aktualisiert!")
        self.lbl_warnings.setStyleSheet("""
            padding: 6px;
            background-color: #fff3e0;
            color: #e65100;
            border: 1px solid #ffb74d;
            border-radius: 4px;
            font-size: 11px;
        """)

    def is_pipeline_dirty(self) -> bool:
        """Return True if pipeline parameters have been modified without recomputing."""
        return self._pipeline_dirty

    def get_emitter_options(self) -> dict[str, Any]:
        """Return user-configured axis transformation parameters."""
        return {
            "rotation_deg": int(self.combo_rotation.currentData() or 0),
            "swap_xy": self.chk_swap_xy.isChecked(),
            "invert_x": self.chk_invert_x.isChecked(),
            "invert_y": self.chk_invert_y.isChecked(),
        }

    def start_plot(self):
        """Start streaming HP-GL commands to the selected plotter port."""
        if self._pipeline_dirty:
            self.config_changed.emit()

        if not self.job or not self.job.steps:
            QMessageBox.warning(self, "Plot-Ausgabe", "Es sind keine Vektoren für die Ausgabe vorhanden.")
            return

        port = self.combo_port.currentText().strip()
        if not port:
            QMessageBox.warning(self, "Plot-Ausgabe", "Bitte wählen Sie eine Schnittstelle oder Adresse aus.")
            return

        margin_key = self.combo_margins.currentData() or "exp"
        profile = get_default_profile()
        emitter = HPGLEmitter(
            profile,
            margin_profile=margin_key,
            **self.get_emitter_options(),
        )
        commands = emitter.emit_commands(self.job, self.doc)

        if not commands:
            QMessageBox.warning(self, "Plot-Ausgabe", "Keine HP-GL Befehle generiert.")
            return

        self._streamer = SerialStreamer(
            on_progress=lambda s, t, pct, p, d: self._bridge.progress.emit(s, t, pct, p, d),
            on_status=lambda state, msg: self._bridge.status.emit(state.value, msg),
            on_finished=lambda success, msg: self._bridge.finished.emit(success, msg),
        )

        self.btn_start_plot.setEnabled(False)
        self.btn_pause_plot.setEnabled(True)
        self.btn_pause_plot.setText("⏸ Pause")
        self.btn_abort_plot.setEnabled(True)
        self.combo_port.setEnabled(False)
        self.combo_margins.setEnabled(False)
        self.combo_rotation.setEnabled(False)
        self.chk_swap_xy.setEnabled(False)
        self.chk_invert_x.setEnabled(False)
        self.chk_invert_y.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_stream_status.setText("Starte Übertragung...")

        baud = profile.connection.baudrate
        started = self._streamer.start_stream(port, commands, baudrate=baud)
        if not started:
            self._on_stream_finished(False, "Streamer konnte nicht gestartet werden.")

    def toggle_pause(self):
        """Toggle pause/resume during streaming."""
        if not self._streamer:
            return
        if self._streamer.state == StreamerState.PAUSED:
            self._streamer.resume()
            self.btn_pause_plot.setText("⏸ Pause")
        elif self._streamer.state == StreamerState.STREAMING:
            self._streamer.pause()
            self.btn_pause_plot.setText("▶️ Fortsetzen")

    def abort_plot(self):
        """Abort active plot and lift pen immediately."""
        if not self._streamer:
            return
        self.btn_pause_plot.setEnabled(False)
        self.btn_abort_plot.setEnabled(False)
        self.lbl_stream_status.setText("Abbruch eingeleitet (ESC.K & Pen-Up)...")
        self._streamer.abort()

    def _on_stream_progress(self, step_idx: int, total_cmds: int, pct: float, pen: int, drawn_m: float):
        self.progress_bar.setValue(int(round(pct)))
        self.lbl_stream_status.setText(
            f"Befehl {step_idx}/{total_cmds} ({pct:.1f}%) • Stift {pen} • {drawn_m:.2f} m"
        )
        self.stream_step_changed.emit(step_idx)

    def _on_stream_status(self, state_str: str, msg: str):
        self.lbl_stream_status.setText(msg)

    def _on_stream_finished(self, success: bool, msg: str):
        self.btn_start_plot.setEnabled(bool(self.job and self.job.steps))
        self.btn_pause_plot.setEnabled(False)
        self.btn_pause_plot.setText("⏸ Pause")
        self.btn_abort_plot.setEnabled(False)
        self.combo_port.setEnabled(True)
        self.combo_margins.setEnabled(True)
        self.combo_rotation.setEnabled(True)
        self.chk_swap_xy.setEnabled(True)
        self.chk_invert_x.setEnabled(True)
        self.chk_invert_y.setEnabled(True)

        if success:
            self.progress_bar.setValue(100)
            self.lbl_stream_status.setText(f"✓ {msg}")
            if self.job:
                self.stream_step_changed.emit(len(self.job.steps))
        else:
            self.lbl_stream_status.setText(f"⚠️ {msg}")

    def closeEvent(self, event):
        if self._streamer and self._streamer.is_active():
            self._streamer.abort()
        super().closeEvent(event)

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
        self._pipeline_dirty = False
        self.btn_recompute.setText("🔄 Pipeline neu berechnen")
        self.btn_recompute.setStyleSheet("")

        if not (self._streamer and self._streamer.is_active()):
            self.btn_start_plot.setEnabled(bool(job and job.steps))

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
