"""Dock widget for Plot Mode: Pipeline parameters, pre-flight statistics, pen filters,
device connection & live plot control, and exports.
"""

from __future__ import annotations

import threading
from typing import Optional, Set

from PySide6.QtCore import Qt, Signal, QObject, QEvent, QSize
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QDoubleSpinBox, QCheckBox, QPushButton,
    QScrollArea, QFileDialog, QMessageBox, QFrame, QComboBox, QProgressBar,
    QStyle
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
    DeviceManager,
    ConfiguredDevice,
)
from .icons import get_icon
from .transform_dock import SectionGroup


class StreamerSignalBridge(QObject):
    """Bridge for cross-thread communication from background worker to Qt main thread."""
    progress = Signal(int, int, float, int, float)  # step_idx, total_cmds, pct, pen, drawn_m
    status = Signal(str, str)                       # state_name, message
    finished = Signal(bool, str)                    # success, message
    probe_done = Signal(object)                     # ProbeResult


class DockScrollArea(QScrollArea):
    """QScrollArea for dock widgets that dynamically computes required content width."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def minimumSizeHint(self) -> QSize:
        w = self.widget()
        if w:
            sb_w = self.style().pixelMetric(QStyle.PM_ScrollBarExtent)
            return QSize(w.minimumSizeHint().width() + sb_w + 4, 100)
        return super().minimumSizeHint()

    def sizeHint(self) -> QSize:
        w = self.widget()
        if w:
            sb_w = self.style().pixelMetric(QStyle.PM_ScrollBarExtent)
            return QSize(max(w.sizeHint().width() + sb_w + 4, 380), 750)
        return super().sizeHint()


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
        super().__init__("Ausgabe", parent)
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
        self.device_manager: Optional[DeviceManager] = None

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self._init_ui()
        self.refresh_ports()

    def minimum_content_width(self) -> int:
        """Calculate the required width to display all dock content without horizontal clipping."""
        if hasattr(self, "_container"):
            self._container.ensurePolished()
            hint_w = self._container.sizeHint().width()
            sb_w = self.style().pixelMetric(QStyle.PM_ScrollBarExtent)
            return max(hint_w + sb_w + 10, 380)
        return 380

    def sizeHint(self) -> QSize:
        return QSize(self.minimum_content_width(), 750)

    def minimumSizeHint(self) -> QSize:
        return QSize(self.minimum_content_width(), 100)

    def update_minimum_width(self, _=None):
        """Update minimum width based on dynamic content and adjust parent dock area if needed."""
        if not hasattr(self, "_container"):
            return
        self._container.adjustSize()
        req_w = self.minimum_content_width()
        self.setMinimumWidth(req_w)
        parent_win = self.window()
        if parent_win and hasattr(parent_win, "resizeDocks"):
            if self.width() < req_w:
                parent_win.resizeDocks([self], [req_w], Qt.Horizontal)

    def showEvent(self, event):
        super().showEvent(event)
        self.update_minimum_width()

    def _init_ui(self):
        self._scroll = DockScrollArea(self)
        self._container = QWidget(self._scroll)
        layout = QVBoxLayout(self._container)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(6)

        # 1. Pipeline Settings (Einklappbar, per Klick erweiterbar)
        self.grp_pipeline = SectionGroup("Pipeline-Optimierung", self._container, collapsible=True, collapsed=False)
        grid_pipe = QGridLayout()
        grid_pipe.setContentsMargins(0, 0, 0, 0)
        grid_pipe.setHorizontalSpacing(8)
        grid_pipe.setVerticalSpacing(4)
        grid_pipe.setColumnStretch(0, 0)
        grid_pipe.setColumnStretch(1, 0)
        grid_pipe.setColumnStretch(2, 1)

        lbl_flat = QLabel("Kurvenglättung:")
        lbl_flat.setStyleSheet("font-weight: 500; color: #374151;")
        self.spin_flatten = QDoubleSpinBox()
        self.spin_flatten.setAlignment(Qt.AlignLeft)
        self.spin_flatten.setRange(0.01, 2.0)
        self.spin_flatten.setValue(0.05)
        self.spin_flatten.setSingleStep(0.01)
        self.spin_flatten.setSuffix(" mm")
        grid_pipe.addWidget(lbl_flat, 0, 0)
        grid_pipe.addWidget(self.spin_flatten, 0, 1)

        lbl_merge = QLabel("Endpunkte verbinden:")
        lbl_merge.setStyleSheet("font-weight: 500; color: #374151;")
        self.spin_merge = QDoubleSpinBox()
        self.spin_merge.setAlignment(Qt.AlignLeft)
        self.spin_merge.setRange(0.0, 5.0)
        self.spin_merge.setValue(0.10)
        self.spin_merge.setSingleStep(0.05)
        self.spin_merge.setSuffix(" mm")
        grid_pipe.addWidget(lbl_merge, 1, 0)
        grid_pipe.addWidget(self.spin_merge, 1, 1)

        lbl_simp = QLabel("Vereinfachen:")
        lbl_simp.setStyleSheet("font-weight: 500; color: #374151;")
        self.spin_simplify = QDoubleSpinBox()
        self.spin_simplify.setAlignment(Qt.AlignLeft)
        self.spin_simplify.setRange(0.0, 2.0)
        self.spin_simplify.setValue(0.02)
        self.spin_simplify.setSingleStep(0.01)
        self.spin_simplify.setSuffix(" mm")
        grid_pipe.addWidget(lbl_simp, 2, 0)
        grid_pipe.addWidget(self.spin_simplify, 2, 1)

        self.grp_pipeline.addLayout(grid_pipe)

        # Checkboxen untereinander
        self.chk_sort = QCheckBox("Leerwege optimieren (Sortierung)")
        self.chk_sort.setToolTip("Leerwege optimieren (TSP 2-Opt Sortierung)")
        self.chk_sort.setChecked(True)
        self.grp_pipeline.addWidget(self.chk_sort)

        self.chk_clip = QCheckBox("Am Plottbereich beschneiden")
        self.chk_clip.setToolTip("Pfade am hardware- oder seitenspezifischen Plottbereich beschneiden (Clip)")
        self.chk_clip.setChecked(False)
        self.grp_pipeline.addWidget(self.chk_clip)

        self.chk_show_travels = QCheckBox("Leerfahrten anzeigen")
        self.chk_show_travels.setToolTip("Leerfahrten (Pen-Up-Bewegungen) auf der Zeichenfläche anzeigen")
        self.chk_show_travels.setChecked(True)
        self.chk_show_travels.toggled.connect(self.toggle_travels.emit)
        self.grp_pipeline.addWidget(self.chk_show_travels)

        self.chk_show_nodes = QCheckBox("Stützpunkte anzeigen")
        self.chk_show_nodes.setToolTip("Stützpunkte (Koordinatenknoten) auf der Zeichenfläche anzeigen")
        self.chk_show_nodes.setChecked(False)
        self.chk_show_nodes.toggled.connect(self.toggle_nodes.emit)
        self.grp_pipeline.addWidget(self.chk_show_nodes)

        self.btn_recompute = QPushButton("Pipeline neu berechnen")
        self.btn_recompute.clicked.connect(self.config_changed.emit)
        self.grp_pipeline.addWidget(self.btn_recompute)

        # Parameter-Änderungen verbinden
        self.spin_flatten.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_merge.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_simplify.valueChanged.connect(self._on_pipeline_param_changed)
        self.chk_sort.toggled.connect(self._on_pipeline_param_changed)
        self.chk_clip.toggled.connect(self._on_pipeline_param_changed)

        layout.addWidget(self.grp_pipeline)

        # 2. Pre-Flight Inspection Statistics (sauber untereinander)
        self.grp_stats = SectionGroup("Pre-Flight-Inspektion", self._container, collapsible=True, collapsed=False)
        grid_stat_values = QGridLayout()
        grid_stat_values.setContentsMargins(0, 0, 0, 0)
        grid_stat_values.setSpacing(4)
        grid_stat_values.setColumnStretch(1, 1)

        def _add_stat_row(row: int, icon_name: str, label_text: str, val_widget: QLabel):
            icon_lbl = QLabel()
            icon_lbl.setPixmap(get_icon(icon_name, size=16).pixmap(16, 16))
            icon_lbl.setFixedSize(18, 18)
            icon_lbl.setAlignment(Qt.AlignCenter)
            grid_stat_values.addWidget(icon_lbl, row, 0)

            title_lbl = QLabel(label_text)
            title_lbl.setStyleSheet("color: #374151;")
            grid_stat_values.addWidget(title_lbl, row, 1)

            val_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid_stat_values.addWidget(val_widget, row, 2)

        self.lbl_draw = QLabel("0.00 m")
        self.lbl_draw.setStyleSheet("font-weight: bold;")
        _add_stat_row(0, "pencil", "Zeichenweg:", self.lbl_draw)

        self.lbl_travel = QLabel("0.00 m")
        self.lbl_travel.setStyleSheet("font-weight: bold; color: #00838f;")
        _add_stat_row(1, "travel", "Leerweg:", self.lbl_travel)

        self.lbl_savings = QLabel("0 %")
        _add_stat_row(2, "percent", "Ersparnis:", self.lbl_savings)

        self.lbl_pen_changes = QLabel("0")
        _add_stat_row(3, "refresh", "Stiftwechsel:", self.lbl_pen_changes)

        self.lbl_duration = QLabel("00m 00s")
        self.lbl_duration.setStyleSheet("font-weight: bold; color: #2e7d32;")
        _add_stat_row(4, "clock", "Geschätzte Zeit:", self.lbl_duration)

        self.lbl_points = QLabel("0")
        _add_stat_row(5, "node", "Stützpunkte:", self.lbl_points)

        self.grp_stats.addLayout(grid_stat_values)

        # Warning / Info box
        self.lbl_warnings = QLabel("✓ Alle Pfade im plottbaren Bereich")
        self.lbl_warnings.setWordWrap(True)
        self.lbl_warnings.setStyleSheet("""
            padding: 6px 8px;
            background-color: #f0fdf4;
            color: #166534;
            border: 1px solid #bbf7d0;
            border-radius: 4px;
        """)
        self.grp_stats.addWidget(self.lbl_warnings)
        layout.addWidget(self.grp_stats)

        # 3. Pen Visibility Filters
        self.grp_pens = SectionGroup("Stifte", self._container, collapsible=True, collapsed=True)
        self.vbox_pens = QVBoxLayout()
        self.vbox_pens.setContentsMargins(0, 0, 0, 0)
        self.vbox_pens.setSpacing(2)

        lbl_pens_placeholder = QLabel("Wird nach Pipeline-Berechnung angezeigt")
        lbl_pens_placeholder.setStyleSheet("color: #94a3b8; font-style: italic; padding: 2px 0;")
        self.vbox_pens.addWidget(lbl_pens_placeholder)
        self.grp_pens.addLayout(self.vbox_pens)
        layout.addWidget(self.grp_pens)

        # 4. Device Connection & Live Plot Control
        self.grp_device = SectionGroup("Plotter-Steuerung", self._container, collapsible=True, collapsed=False)

        # Active Device Info Display
        self.lbl_active_device_info = QLabel("Kein Gerät ausgewählt<br><span style='color: #64748b;'>In oberer Leiste wählen</span>")
        self.lbl_active_device_info.setWordWrap(True)
        self.lbl_active_device_info.setStyleSheet("""
            padding: 6px 8px;
            background-color: #f8fafc;
            color: #334155;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        """)
        self.grp_device.addWidget(self.lbl_active_device_info)

        # Hidden controls to maintain compatibility with headless tests & internal state
        self.combo_port = QComboBox(self)
        self.combo_port.setEditable(True)
        self.combo_port.setVisible(False)

        self.btn_refresh_ports = QPushButton(self)
        self.btn_refresh_ports.setIcon(get_icon("refresh", size=16))
        self.btn_refresh_ports.setVisible(False)
        self.btn_refresh_ports.clicked.connect(self.refresh_ports)

        from ..device.profile import get_margin_profile_items
        self.combo_margins = QComboBox(self)
        for label, key in get_margin_profile_items():
            self.combo_margins.addItem(label, key)
        self.combo_margins.setVisible(False)

        # Drehung und Achsen in zwei kompakten Zeilen
        hbox_rot = QHBoxLayout()
        hbox_rot.setContentsMargins(0, 0, 0, 0)
        hbox_rot.setSpacing(6)

        lbl_rot = QLabel("Drehung:")
        lbl_rot.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_rot.addWidget(lbl_rot)

        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem("0° (Standard)", 0)
        self.combo_rotation.addItem("90° (Quer/Vorschub)", 90)
        self.combo_rotation.addItem("180°", 180)
        self.combo_rotation.addItem("270°", 270)
        hbox_rot.addWidget(self.combo_rotation)
        hbox_rot.addStretch()
        self.grp_device.addLayout(hbox_rot)

        hbox_axes = QHBoxLayout()
        hbox_axes.setContentsMargins(0, 0, 0, 0)
        hbox_axes.setSpacing(8)

        lbl_axes = QLabel("Achsen:")
        lbl_axes.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_axes.addWidget(lbl_axes)

        self.chk_swap_xy = QCheckBox("X↔Y")
        self.chk_swap_xy.setToolTip("Achsentausch: X- und Y-Achsen vertauschen (z.B. Rollenvorschub ↔ Wagen)")
        self.chk_invert_x = QCheckBox("X inv.")
        self.chk_invert_x.setToolTip("X-Achse spiegeln")
        self.chk_invert_y = QCheckBox("Y inv.")
        self.chk_invert_y.setToolTip("Y-Achse spiegeln")
        hbox_axes.addWidget(self.chk_swap_xy)
        hbox_axes.addWidget(self.chk_invert_x)
        hbox_axes.addWidget(self.chk_invert_y)
        hbox_axes.addStretch()
        self.grp_device.addLayout(hbox_axes)

        self.btn_probe = QPushButton("Plotter prüfen (Inquiry)")
        self.btn_probe.setIcon(get_icon("search", size=15))
        self.btn_probe.clicked.connect(self.start_probe)
        self.grp_device.addWidget(self.btn_probe)

        self.lbl_probe_status = QLabel("Kein Plotter geprüft")
        self.lbl_probe_status.setWordWrap(True)
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px 8px;
            background-color: #f8fafc;
            color: #64748b;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        """)
        self.grp_device.addWidget(self.lbl_probe_status)

        self.chk_pause_pen_change = QCheckBox("Bei Stiftwechsel automatisch pausieren")
        self.chk_pause_pen_change.setToolTip(
            "Pausiert den Plot automatisch vor jedem Stiftwechsel (SPn;),\n"
            "z.B. für manuelle Stiftwechsel oder Spezialstifte"
        )
        self.grp_device.addWidget(self.chk_pause_pen_change)

        self.btn_start_plot = QPushButton("Plot senden")
        self.btn_start_plot.setIcon(get_icon("play", size=16))
        self.btn_start_plot.setStyleSheet("font-weight: 600; padding: 5px;")
        self.btn_start_plot.setEnabled(False)
        self.btn_start_plot.clicked.connect(self.start_plot)
        self.grp_device.addWidget(self.btn_start_plot)

        hbox_ctrl = QHBoxLayout()
        hbox_ctrl.setContentsMargins(0, 0, 0, 0)
        hbox_ctrl.setSpacing(6)

        self.btn_pause_plot = QPushButton("Pause")
        self.btn_pause_plot.setIcon(get_icon("pause", size=15))
        self.btn_pause_plot.setEnabled(False)
        self.btn_pause_plot.clicked.connect(self.toggle_pause)
        hbox_ctrl.addWidget(self.btn_pause_plot)

        self.btn_abort_plot = QPushButton("Abbrechen")
        self.btn_abort_plot.setIcon(get_icon("stop", size=15))
        self.btn_abort_plot.setEnabled(False)
        self.btn_abort_plot.setStyleSheet("color: #b91c1c;")
        self.btn_abort_plot.clicked.connect(self.abort_plot)
        hbox_ctrl.addWidget(self.btn_abort_plot)

        self.grp_device.addLayout(hbox_ctrl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(14)
        self.grp_device.addWidget(self.progress_bar)

        self.lbl_stream_status = QLabel("Bereit")
        self.lbl_stream_status.setStyleSheet("color: #64748b;")
        self.lbl_stream_status.setWordWrap(True)
        self.grp_device.addWidget(self.lbl_stream_status)

        layout.addWidget(self.grp_device)

        # 5. Export & Actions (Side-by-side)
        self.grp_export = SectionGroup("Datei-Export", self._container, collapsible=True, collapsed=False)
        hbox_export = QHBoxLayout()
        hbox_export.setContentsMargins(0, 0, 0, 0)
        hbox_export.setSpacing(6)

        self.btn_export_hpgl = QPushButton("HP-GL (.hpgl)")
        self.btn_export_hpgl.setIcon(get_icon("save", size=15))
        self.btn_export_hpgl.setToolTip("Berechnete HP-GL Plotbefehle als Datei speichern")
        self.btn_export_hpgl.clicked.connect(self.export_hpgl_requested.emit)
        hbox_export.addWidget(self.btn_export_hpgl)

        self.btn_export_svg = QPushButton("Vektoren (.svg)")
        self.btn_export_svg.setIcon(get_icon("save", size=15))
        self.btn_export_svg.setToolTip("Optimierte Plot-Vektoren als SVG exportieren")
        self.btn_export_svg.clicked.connect(self.export_svg_requested.emit)
        hbox_export.addWidget(self.btn_export_svg)

        self.grp_export.addLayout(hbox_export)
        layout.addWidget(self.grp_export)

        layout.addStretch()
        self._scroll.setWidget(self._container)
        self.setWidget(self._scroll)

        # Connect collapsible section toggles to minimum width updates
        for grp in [self.grp_pipeline, self.grp_stats, self.grp_pens, self.grp_device, self.grp_export]:
            grp.toggled_collapse.connect(self.update_minimum_width)

        self._update_font_metrics_sizes()
        self.update_minimum_width()

    def _update_font_metrics_sizes(self):
        """Berechnet Eingabefeldbreiten dynamisch anhand der Schriftart."""
        fm = self.fontMetrics()
        spin_w = fm.horizontalAdvance("0.00 mm") + fm.height() + 24
        for s in (self.spin_flatten, self.spin_merge, self.spin_simplify):
            s.setFixedWidth(spin_w)

    def changeEvent(self, event: QEvent):
        """Reagiert auf System- und Anwendungs-Schriftänderungen zur Laufzeit."""
        if event.type() == QEvent.FontChange:
            self._update_font_metrics_sizes()
        super().changeEvent(event)

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

    def set_device_manager(self, manager: DeviceManager):
        self.device_manager = manager
        dev = manager.get_active_device()
        if dev:
            self.apply_configured_device(dev)

    def apply_configured_device(self, dev: ConfiguredDevice):
        idx = self.combo_port.findText(dev.port)
        if idx >= 0:
            self.combo_port.setCurrentIndex(idx)
        else:
            self.combo_port.setEditText(dev.port)

        m_idx = self.combo_margins.findData(dev.margin_profile)
        if m_idx >= 0:
            self.combo_margins.setCurrentIndex(m_idx)

        r_idx = self.combo_rotation.findData(dev.rotation)
        if r_idx >= 0:
            self.combo_rotation.setCurrentIndex(r_idx)

        self.chk_swap_xy.setChecked(dev.swap_xy)
        self.chk_invert_x.setChecked(dev.invert_x)
        self.chk_invert_y.setChecked(dev.invert_y)

        flow_names = {
            "rtscts": "RTS/CTS",
            "dsrdtr": "DTR/DSR",
            "xonxoff": "XON/XOFF",
            "none": "Keine",
        }
        flow_str = flow_names.get(getattr(dev, "flow_control", "rtscts"), "RTS/CTS")
        baud_info = f" ({dev.baudrate} Baud, {flow_str})" if not dev.port.startswith("tcp://") else f" ({flow_str})"
        self.lbl_active_device_info.setText(
            f"Gerät: <b>{dev.name}</b><br>"
            f"Schnittstelle: <code>{dev.port}</code>{baud_info}"
        )

    def start_probe(self):
        """Inquire connected plotter (OI/OF/OH) in background thread."""
        port = self.combo_port.currentText().strip()
        baud = 19200
        if self.device_manager:
            dev = self.device_manager.get_active_device()
            if dev:
                if not port:
                    port = dev.port
                baud = dev.baudrate
        if not port:
            self.lbl_probe_status.setText("Kein Port ausgewählt")
            return

        self.btn_probe.setEnabled(False)
        self.lbl_probe_status.setText(f"Prüfe {port} mit {baud} Baud...")
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px 8px;
            background-color: #fff9c4;
            color: #f57f17;
            border: 1px solid #fff59d;
            border-radius: 4px;
        """)

        def _probe_worker():
            res = probe_plotter(port, baudrate=baud)
            self._bridge.probe_done.emit(res)

        self._probe_thread = threading.Thread(target=_probe_worker, daemon=True, name="PlotterProbeThread")
        self._probe_thread.start()

    def _on_probe_done(self, result: ProbeResult):
        self.btn_probe.setEnabled(True)
        if result.success:
            clip_info = ""
            if result.hard_clip_mm:
                clip_info = f" • Hard-Clip: {result.hard_clip_mm[0]:.0f}×{result.hard_clip_mm[1]:.0f} mm"
            pin_parts = []
            if result.cts is not None:
                pin_parts.append("CTS: Bereit" if result.cts else "⚠️ CTS: Low")
            if result.dsr is not None:
                pin_parts.append("DSR: Bereit" if result.dsr else "⚠️ DSR: Low")
            pin_info = f" • {' / '.join(pin_parts)}" if pin_parts else ""
            self.lbl_probe_status.setText(
                f"✓ {result.model} ({result.detected_format}, {result.units_per_mm:.0f} U/mm){clip_info}{pin_info}"
            )
            self.lbl_probe_status.setStyleSheet("""
                padding: 6px 8px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
                border-radius: 4px;
            """)
        else:
            self.lbl_probe_status.setText(f"⚠️ {result.error_message}")
            self.lbl_probe_status.setStyleSheet("""
                padding: 6px 8px;
                background-color: #ffebee;
                color: #c62828;
                border: 1px solid #ffcdd2;
                border-radius: 4px;
            """)

    def _on_pipeline_param_changed(self, *args):
        """Called when any pipeline optimization parameter is modified by the user."""
        self._pipeline_dirty = True
        self.btn_recompute.setText("Pipeline neu berechnen (geändert)")
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
            padding: 6px 8px;
            background-color: #fff3e0;
            color: #e65100;
            border: 1px solid #ffb74d;
            border-radius: 4px;
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
        margin_key = self.combo_margins.currentData() or "exp"
        profile = get_default_profile()
        baud = profile.connection.baudrate
        flow_ctrl = getattr(profile.connection, "flow_control", "rtscts")

        if self.device_manager:
            dev = self.device_manager.get_active_device()
            if dev:
                if not port:
                    port = dev.port
                profile = dev.get_profile()
                baud = dev.baudrate
                flow_ctrl = getattr(dev, "flow_control", flow_ctrl)

        if not port:
            QMessageBox.warning(self, "Plot-Ausgabe", "Bitte wählen Sie eine Schnittstelle oder Adresse aus.")
            return

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

        started = self._streamer.start_stream(
            port,
            commands,
            baudrate=baud,
            flow_control=flow_ctrl,
            pause_on_pen_change=self.chk_pause_pen_change.isChecked(),
        )
        if not started:
            self._on_stream_finished(False, "Streamer konnte nicht gestartet werden.")

    def toggle_pause(self):
        """Toggle pause/resume during streaming."""
        if not self._streamer:
            return
        if self._streamer.is_user_paused():
            self._streamer.resume()
            self.btn_pause_plot.setText("⏸ Pause")
        elif self._streamer.is_active():
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
        if self._streamer and self._streamer.is_user_paused():
            self.btn_pause_plot.setText("▶️ Fortsetzen")
        elif state_str == "STREAMING":
            self.btn_pause_plot.setText("⏸ Pause")

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
        self.btn_recompute.setText("Pipeline neu berechnen")
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
            self.lbl_warnings.setStyleSheet("padding: 6px 8px; color: #64748b;")
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
                padding: 6px 8px;
                background-color: #fff3e0;
                color: #e65100;
                border: 1px solid #ffe0b2;
                border-radius: 4px;
            """)
        else:
            self.lbl_warnings.setText("✓ Alle Pfade im plottbaren Bereich")
            self.lbl_warnings.setStyleSheet("""
                padding: 6px 8px;
                background-color: #e8f5e9;
                color: #2e7d32;
                border: 1px solid #c8e6c9;
                border-radius: 4px;
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
            lbl.setStyleSheet("color: #94a3b8; font-style: italic; padding: 2px 0;")
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
                QCheckBox::indicator:checked {{
                    background-color: {color};
                    border: 1px solid #444;
                }}
            """)
            chk.toggled.connect(self._on_pen_filter_toggled)
            self._pen_checkboxes[pen_id] = chk
            self.vbox_pens.addWidget(chk)

        self.update_minimum_width()

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
