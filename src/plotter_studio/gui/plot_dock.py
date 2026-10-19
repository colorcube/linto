"""Dock widget for Plot Mode: Pipeline parameters, pre-flight statistics, pen filters,
device connection & live plot control, and exports.
"""

from __future__ import annotations

import threading
from typing import Optional, Set, Any

from PySide6.QtCore import Qt, Signal, QObject, QEvent, QSize, QTimer
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox, QPushButton,
    QScrollArea, QMessageBox, QFrame, QComboBox, QProgressBar,
    QStyle, QDialog, QPlainTextEdit
)
from ..core.document import Document
from ..pipeline.compiler import PipelineConfig, PlotJob
from ..device import (
    get_default_profile,
    build_emitter,
    list_serial_ports,
    probe_plotter,
    SerialStreamer,
    ProbeResult,
    DeviceManager,
    ConfiguredDevice,
)
from .icons import get_icon
from .transform_dock import SectionGroup
from .device_dialog import AXIS_CORRECTION_TIP


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
    stream_active_changed = Signal(bool)

    def __init__(self, doc: Document, parent=None):
        super().__init__(self.tr("Output"), parent)
        self.doc = doc
        self.job: Optional[PlotJob] = None
        self._pen_checkboxes: dict[int, QCheckBox] = {}
        self._pipeline_dirty = False
        self._updating_device = False

        self._recompute_timer = QTimer(self)
        self._recompute_timer.setSingleShot(True)
        self._recompute_timer.setInterval(400)
        self._recompute_timer.timeout.connect(self._on_recompute_timer)

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

    def is_streaming(self) -> bool:
        """Return True while a plot job is actively streaming or paused on the hardware."""
        return bool(self._streamer and self._streamer.is_active())

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

        # 1. Pipeline Settings (Collapsible)
        self.grp_pipeline = SectionGroup(self.tr("Pipeline Optimization"), self._container, collapsible=True, collapsed=False)
        grid_pipe = QGridLayout()
        grid_pipe.setContentsMargins(0, 0, 0, 0)
        grid_pipe.setHorizontalSpacing(8)
        grid_pipe.setVerticalSpacing(4)
        grid_pipe.setColumnStretch(0, 0)
        grid_pipe.setColumnStretch(1, 0)
        grid_pipe.setColumnStretch(2, 0)
        grid_pipe.setColumnStretch(3, 1)

        def _make_info_badge(tip: str) -> QLabel:
            lbl = QLabel()
            lbl.setPixmap(get_icon("info", color="#6b7280", size=14).pixmap(14, 14))
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.setToolTip(tip)
            lbl.setFixedSize(16, 16)
            lbl.setAlignment(Qt.AlignCenter)
            return lbl

        tip_flatten = self.tr(
            "<b>Curve Flattening (Bézier & Arcs)</b><br>"
            "Subdivides curved paths into straight line segments for the plotter.<br><br>"
            "• <b>Tolerance (mm):</b> Maximum chordal distance between true curve and segment.<br>"
            "• <b>Smaller (e.g. 0.02 mm):</b> Smoother curves, more vertices & commands.<br>"
            "• <b>Larger (e.g. 0.10 mm):</b> Faster plotting, but curves may appear faceted.<br>"
            "• <i>Default: 0.05 mm (seamless curve rendering below pen width).</i>"
        )
        tip_merge = self.tr(
            "<b>Connect Endpoints (Line Merge)</b><br>"
            "Merges adjacent line segments automatically into continuous paths.<br><br>"
            "• <b>Tolerance (mm):</b> Maximum distance between endpoints to join.<br>"
            "• <b>Benefit:</b> Greatly reduces pen-up/down actuations (PU/PD), saves time and pen tips.<br>"
            "• <b>Too large (e.g. > 0.5 mm):</b> Nearby lines or hatchings may merge accidentally.<br>"
            "• <i>Default: 0.10 mm (bridges microscopic SVG/CAD export gaps).</i>"
        )
        tip_simplify = self.tr(
            "<b>Simplify Paths (Ramer-Douglas-Peucker)</b><br>"
            "Removes redundant vertices from nearly straight lines.<br><br>"
            "• <b>Tolerance (mm):</b> Maximum allowed geometric deviation (epsilon).<br>"
            "• <b>Benefit:</b> Drastically reduces file size and prevents plotter jitter on dense paths.<br>"
            "• <b>Too large (e.g. > 0.08 mm):</b> Sharp corners and fine details may round off.<br>"
            "• <b>0.00 mm:</b> Disables simplification (removes only collinear points).<br>"
            "• <i>Default: 0.02 mm (lossless point reduction).</i>"
        )

        lbl_flat = QLabel(self.tr("Curve flattening:"))
        lbl_flat.setStyleSheet("font-weight: 500; color: #374151;")
        lbl_flat.setToolTip(tip_flatten)
        self.spin_flatten = QDoubleSpinBox()
        self.spin_flatten.setKeyboardTracking(False)
        self.spin_flatten.setAlignment(Qt.AlignLeft)
        self.spin_flatten.setRange(0.01, 2.0)
        self.spin_flatten.setValue(0.05)
        self.spin_flatten.setSingleStep(0.01)
        self.spin_flatten.setSuffix(" mm")
        self.spin_flatten.setToolTip(tip_flatten)
        self.btn_info_flatten = _make_info_badge(tip_flatten)
        grid_pipe.addWidget(lbl_flat, 0, 0)
        grid_pipe.addWidget(self.spin_flatten, 0, 1)
        grid_pipe.addWidget(self.btn_info_flatten, 0, 2)

        lbl_merge = QLabel(self.tr("Connect endpoints:"))
        lbl_merge.setStyleSheet("font-weight: 500; color: #374151;")
        lbl_merge.setToolTip(tip_merge)
        self.spin_merge = QDoubleSpinBox()
        self.spin_merge.setKeyboardTracking(False)
        self.spin_merge.setAlignment(Qt.AlignLeft)
        self.spin_merge.setRange(0.0, 5.0)
        self.spin_merge.setValue(0.10)
        self.spin_merge.setSingleStep(0.05)
        self.spin_merge.setSuffix(" mm")
        self.spin_merge.setToolTip(tip_merge)
        self.btn_info_merge = _make_info_badge(tip_merge)
        grid_pipe.addWidget(lbl_merge, 1, 0)
        grid_pipe.addWidget(self.spin_merge, 1, 1)
        grid_pipe.addWidget(self.btn_info_merge, 1, 2)

        lbl_simp = QLabel(self.tr("Simplify:"))
        lbl_simp.setStyleSheet("font-weight: 500; color: #374151;")
        lbl_simp.setToolTip(tip_simplify)
        self.spin_simplify = QDoubleSpinBox()
        self.spin_simplify.setKeyboardTracking(False)
        self.spin_simplify.setAlignment(Qt.AlignLeft)
        self.spin_simplify.setRange(0.0, 2.0)
        self.spin_simplify.setValue(0.02)
        self.spin_simplify.setSingleStep(0.01)
        self.spin_simplify.setSuffix(" mm")
        self.spin_simplify.setToolTip(tip_simplify)
        self.btn_info_simplify = _make_info_badge(tip_simplify)
        grid_pipe.addWidget(lbl_simp, 2, 0)
        grid_pipe.addWidget(self.spin_simplify, 2, 1)
        grid_pipe.addWidget(self.btn_info_simplify, 2, 2)

        self.grp_pipeline.addLayout(grid_pipe)

        # Checkboxes
        self.chk_sort = QCheckBox(self.tr("Optimize travel moves (Sort)"))
        self.chk_sort.setToolTip(self.tr("Optimize travel moves (TSP 2-Opt sorting)"))
        self.chk_sort.setChecked(True)
        self.grp_pipeline.addWidget(self.chk_sort)

        self.chk_dedup = QCheckBox(self.tr("Remove overlapping segments"))
        self.chk_dedup.setToolTip(self.tr("Remove duplicate or overlapping line segments within the same pen layer"))
        self.chk_dedup.setChecked(True)
        self.grp_pipeline.addWidget(self.chk_dedup)

        self.chk_clip = QCheckBox(self.tr("Clip to printable area"))
        self.chk_clip.setToolTip(self.tr("Clip paths to hardware or page-specific printable area"))
        self.chk_clip.setChecked(False)
        self.grp_pipeline.addWidget(self.chk_clip)

        hbox_pen_order = QHBoxLayout()
        hbox_pen_order.setContentsMargins(0, 0, 0, 0)
        hbox_pen_order.setSpacing(6)
        lbl_pen_order = QLabel(self.tr("Pen order:"))
        lbl_pen_order.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_pen_order.addWidget(lbl_pen_order)
        self.combo_pen_order = QComboBox()
        self.combo_pen_order.addItem(self.tr("By Pen Number (1–8)"), "id")
        self.combo_pen_order.addItem(self.tr("Lightest Colors First"), "luminance")
        self.combo_pen_order.setToolTip(self.tr("Order in which pens are plotted (plotting light colors first prevents dark ink smudging)"))
        hbox_pen_order.addWidget(self.combo_pen_order, 1)
        self.grp_pipeline.addLayout(hbox_pen_order)

        self.chk_show_travels = QCheckBox(self.tr("Show rapid moves"))
        self.chk_show_travels.setToolTip(self.tr("Show pen-up travel moves on canvas"))
        self.chk_show_travels.setChecked(True)
        self.chk_show_travels.toggled.connect(self.toggle_travels.emit)
        self.grp_pipeline.addWidget(self.chk_show_travels)

        self.chk_show_nodes = QCheckBox(self.tr("Show vertices"))
        self.chk_show_nodes.setToolTip(self.tr("Show coordinate vertices on canvas"))
        self.chk_show_nodes.setChecked(False)
        self.chk_show_nodes.toggled.connect(self.toggle_nodes.emit)
        self.grp_pipeline.addWidget(self.chk_show_nodes)

        self.btn_recompute = QPushButton(self.tr("Recompute Pipeline"))
        self.btn_recompute.clicked.connect(self.config_changed.emit)
        self.grp_pipeline.addWidget(self.btn_recompute)

        # Parameter change connections
        self.spin_flatten.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_merge.valueChanged.connect(self._on_pipeline_param_changed)
        self.spin_simplify.valueChanged.connect(self._on_pipeline_param_changed)
        self.chk_sort.toggled.connect(self._on_pipeline_param_changed)
        self.chk_dedup.toggled.connect(self._on_pipeline_param_changed)
        self.chk_clip.toggled.connect(self._on_pipeline_param_changed)
        self.combo_pen_order.currentIndexChanged.connect(self._on_pipeline_param_changed)

        layout.addWidget(self.grp_pipeline)

        # 2. Pre-Flight Inspection Statistics
        self.grp_stats = SectionGroup(self.tr("Pre-Flight Inspection"), self._container, collapsible=True, collapsed=False)
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
        _add_stat_row(0, "pencil", self.tr("Draw distance:"), self.lbl_draw)

        self.lbl_travel = QLabel("0.00 m")
        self.lbl_travel.setStyleSheet("font-weight: bold; color: #00838f;")
        _add_stat_row(1, "travel", self.tr("Air travel:"), self.lbl_travel)

        self.lbl_savings = QLabel("0 %")
        _add_stat_row(2, "percent", self.tr("Savings:"), self.lbl_savings)

        self.lbl_pen_changes = QLabel("0")
        _add_stat_row(3, "refresh", self.tr("Pen changes:"), self.lbl_pen_changes)

        self.lbl_duration = QLabel("00m 00s")
        self.lbl_duration.setStyleSheet("font-weight: bold; color: #2e7d32;")
        _add_stat_row(4, "clock", self.tr("Estimated time:"), self.lbl_duration)

        self.lbl_points = QLabel("0")
        _add_stat_row(5, "node", self.tr("Vertices:"), self.lbl_points)

        self.grp_stats.addLayout(grid_stat_values)

        # Warning / Info box
        self.lbl_warnings = QLabel(self.tr("✓ All paths within printable area"))
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
        self.grp_pens = SectionGroup(self.tr("Pens"), self._container, collapsible=True, collapsed=True)
        self.vbox_pens = QVBoxLayout()
        self.vbox_pens.setContentsMargins(0, 0, 0, 0)
        self.vbox_pens.setSpacing(2)

        lbl_pens_placeholder = QLabel(self.tr("Displayed after pipeline computation"))
        lbl_pens_placeholder.setStyleSheet("color: #94a3b8; font-style: italic; padding: 2px 0;")
        self.vbox_pens.addWidget(lbl_pens_placeholder)
        self.grp_pens.addLayout(self.vbox_pens)
        layout.addWidget(self.grp_pens)

        # 4. Device Connection & Live Plot Control
        self.grp_device = SectionGroup(self.tr("Plotter Control"), self._container, collapsible=True, collapsed=False)

        # Active Device Info Display
        self.lbl_active_device_info = QLabel(self.tr("No device selected<br><span style='color: #64748b;'>Select in top toolbar</span>"))
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

        lbl_rot = QLabel(self.tr("Rotation correction:"))
        lbl_rot.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_rot.addWidget(lbl_rot)

        self.combo_rotation = QComboBox()
        self.combo_rotation.addItem(self.tr("0° (no correction)"), 0)
        self.combo_rotation.addItem("90°", 90)
        self.combo_rotation.addItem("180°", 180)
        self.combo_rotation.addItem("270°", 270)
        self.combo_rotation.currentIndexChanged.connect(self._on_emitter_option_changed)
        hbox_rot.addWidget(self.combo_rotation)
        hbox_rot.addStretch()
        self.grp_device.addLayout(hbox_rot)

        hbox_axes = QHBoxLayout()
        hbox_axes.setContentsMargins(0, 0, 0, 0)
        hbox_axes.setSpacing(8)

        lbl_axes = QLabel(self.tr("Axis correction:"))
        lbl_axes.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        lbl_axes.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_axes.addWidget(lbl_axes)

        self.chk_swap_xy = QCheckBox("X↔Y")
        self.chk_swap_xy.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        self.chk_swap_xy.toggled.connect(self._on_emitter_option_changed)
        self.chk_invert_x = QCheckBox("X inv.")
        self.chk_invert_x.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        self.chk_invert_x.toggled.connect(self._on_emitter_option_changed)
        self.chk_invert_y = QCheckBox("Y inv.")
        self.chk_invert_y.setToolTip(self.tr(AXIS_CORRECTION_TIP))
        self.chk_invert_y.toggled.connect(self._on_emitter_option_changed)
        hbox_axes.addWidget(self.chk_swap_xy)
        hbox_axes.addWidget(self.chk_invert_x)
        hbox_axes.addWidget(self.chk_invert_y)
        hbox_axes.addStretch()
        self.grp_device.addLayout(hbox_axes)

        self.btn_probe = QPushButton(self.tr("Probe Plotter (Inquiry)"))
        self.btn_probe.setIcon(get_icon("search", size=15))
        self.btn_probe.clicked.connect(self.start_probe)
        self.grp_device.addWidget(self.btn_probe)

        self.lbl_probe_status = QLabel(self.tr("No plotter probed"))
        self.lbl_probe_status.setWordWrap(True)
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px 8px;
            background-color: #f8fafc;
            color: #64748b;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        """)
        self.grp_device.addWidget(self.lbl_probe_status)

        self.chk_pause_pen_change = QCheckBox(self.tr("Auto-pause on pen change"))
        self.chk_pause_pen_change.setToolTip(
            self.tr("Pauses the plot automatically before each pen change (SPn;),\ne.g. for manual pen swaps or specialty pens")
        )
        self.grp_device.addWidget(self.chk_pause_pen_change)

        hbox_resume = QHBoxLayout()
        hbox_resume.setContentsMargins(0, 0, 0, 0)
        hbox_resume.setSpacing(6)
        lbl_resume = QLabel(self.tr("Start from step:"))
        lbl_resume.setStyleSheet("font-weight: 500; color: #374151;")
        hbox_resume.addWidget(lbl_resume)
        self.spin_start_step = QSpinBox()
        self.spin_start_step.setKeyboardTracking(False)
        self.spin_start_step.setRange(0, 999999)
        self.spin_start_step.setValue(0)
        self.spin_start_step.setToolTip(
            self.tr("Resume plot from step N (0 = start from beginning; automatically set to last step after abort)")
        )
        hbox_resume.addWidget(self.spin_start_step)
        hbox_resume.addStretch()
        self.grp_device.addLayout(hbox_resume)

        self.btn_start_plot = QPushButton(self.tr("Send Plot"))
        self.btn_start_plot.setIcon(get_icon("play", size=16))
        self.btn_start_plot.setStyleSheet("font-weight: 600; padding: 5px;")
        self.btn_start_plot.setEnabled(False)
        self.btn_start_plot.clicked.connect(self.start_plot)
        self.grp_device.addWidget(self.btn_start_plot)

        hbox_ctrl = QHBoxLayout()
        hbox_ctrl.setContentsMargins(0, 0, 0, 0)
        hbox_ctrl.setSpacing(6)

        self.btn_pause_plot = QPushButton(self.tr("Pause"))
        self.btn_pause_plot.setIcon(get_icon("pause", size=15))
        self.btn_pause_plot.setEnabled(False)
        self.btn_pause_plot.clicked.connect(self.toggle_pause)
        hbox_ctrl.addWidget(self.btn_pause_plot)

        self.btn_abort_plot = QPushButton(self.tr("Cancel"))
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

        self.lbl_stream_status = QLabel(self.tr("Ready"))
        self.lbl_stream_status.setStyleSheet("color: #64748b;")
        self.lbl_stream_status.setWordWrap(True)
        self.grp_device.addWidget(self.lbl_stream_status)

        self.btn_diag_log = QPushButton(self.tr("Diagnostic Log..."))
        self.btn_diag_log.setToolTip(self.tr("Show transmitted and received HP-GL bytes for hardware diagnostics"))
        self.btn_diag_log.clicked.connect(self.show_diagnostic_log)
        self.grp_device.addWidget(self.btn_diag_log)

        layout.addWidget(self.grp_device)

        # 5. Export & Actions (Side-by-side)
        self.grp_export = SectionGroup(self.tr("File Export"), self._container, collapsible=True, collapsed=False)
        hbox_export = QHBoxLayout()
        hbox_export.setContentsMargins(0, 0, 0, 0)
        hbox_export.setSpacing(6)

        self.btn_export_hpgl = QPushButton("HP-GL (.hpgl)")
        self.btn_export_hpgl.setIcon(get_icon("save", size=15))
        self.btn_export_hpgl.setToolTip(self.tr("Save computed HP-GL plot commands to file"))
        self.btn_export_hpgl.clicked.connect(self.export_hpgl_requested.emit)
        hbox_export.addWidget(self.btn_export_hpgl)

        self.btn_export_svg = QPushButton("SVG (.svg)")
        self.btn_export_svg.setIcon(get_icon("save", size=15))
        self.btn_export_svg.setToolTip(self.tr("Export optimized plot vectors as SVG"))
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
        self._updating_device = True
        try:
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
        finally:
            self._updating_device = False

        flow_names = {
            "rtscts": "RTS/CTS",
            "dsrdtr": "DTR/DSR",
            "xonxoff": "XON/XOFF",
            "none": self.tr("None"),
        }
        flow_str = flow_names.get(getattr(dev, "flow_control", "rtscts"), "RTS/CTS")
        framing_str = getattr(dev, "framing_label", "8N1")
        baud_info = f" ({dev.baudrate} Baud, {framing_str}, {flow_str})" if not dev.port.startswith("tcp://") else f" ({flow_str})"
        dev_info_html = self.tr("Device: <b>%1</b><br>Port: <code>%2</code>%3").replace("%1", dev.name).replace("%2", dev.port).replace("%3", baud_info)
        self.lbl_active_device_info.setText(dev_info_html)

    def _on_emitter_option_changed(self, *args):
        """Sync rotation and axis inversion/swap controls back to the active ConfiguredDevice."""
        if self._updating_device or not self.device_manager:
            return
        dev = self.device_manager.get_active_device()
        if dev:
            dev.rotation = int(self.combo_rotation.currentData() or 0)
            dev.swap_xy = self.chk_swap_xy.isChecked()
            dev.invert_x = self.chk_invert_x.isChecked()
            dev.invert_y = self.chk_invert_y.isChecked()

    def start_probe(self):
        """Inquire connected plotter (OI/OF/OH) in background thread."""
        if self.is_streaming() or (self._probe_thread is not None and self._probe_thread.is_alive()):
            return
        port = self.combo_port.currentText().strip()
        baud = 19200
        bytesize = 8
        parity = "N"
        stopbits = 1
        axes_swapped = get_default_profile().axes_swapped
        if self.device_manager:
            dev = self.device_manager.get_active_device()
            if dev:
                if not port:
                    port = dev.port
                baud = dev.baudrate
                prof = dev.get_profile()
                bytesize = int(getattr(dev, "bytesize", None) or prof.connection.bytesize)
                parity = str(getattr(dev, "parity", None) or prof.connection.parity).upper()
                stopbits = int(getattr(dev, "stopbits", None) or prof.connection.stopbits)
                axes_swapped = prof.axes_swapped
        if not port:
            self.lbl_probe_status.setText(self.tr("No port selected"))
            return

        self.btn_probe.setEnabled(False)
        self.btn_start_plot.setEnabled(False)
        self.lbl_probe_status.setText(self.tr("Probing %1 at %2 baud...").replace("%1", port).replace("%2", str(baud)))
        self.lbl_probe_status.setStyleSheet("""
            padding: 6px 8px;
            background-color: #fff9c4;
            color: #f57f17;
            border: 1px solid #fff59d;
            border-radius: 4px;
        """)

        def _probe_worker():
            res = probe_plotter(
                port,
                baudrate=baud,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                axes_swapped=axes_swapped,
            )
            self._bridge.probe_done.emit(res)

        self._probe_thread = threading.Thread(target=_probe_worker, daemon=True, name="PlotterProbeThread")
        self._probe_thread.start()

    def _on_probe_done(self, result: ProbeResult):
        if not self.is_streaming():
            self.btn_probe.setEnabled(True)
            self.btn_start_plot.setEnabled(bool(self.job and self.job.steps))
        if result.success:
            if result.units_per_mm and result.units_per_mm > 0 and self.device_manager:
                dev = self.device_manager.get_active_device()
                if dev:
                    dev.probed_units_per_mm = result.units_per_mm
            clip_info = ""
            if result.hard_clip_mm:
                clip_info = f" • Hard-Clip: {result.hard_clip_mm[0]:.0f}×{result.hard_clip_mm[1]:.0f} mm"
            pin_parts = []
            if result.cts is not None:
                pin_parts.append(self.tr("CTS: Ready") if result.cts else self.tr("⚠️ CTS: Low"))
            if result.dsr is not None:
                pin_parts.append(self.tr("DSR: Ready") if result.dsr else self.tr("⚠️ DSR: Low"))
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
        self.btn_recompute.setText(self.tr("Recompute Pipeline (Modified)"))
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
        self.lbl_warnings.setText(self.tr("⚠️ Settings changed – preview not updated yet!"))
        self.lbl_warnings.setStyleSheet("""
            padding: 6px 8px;
            background-color: #fff3e0;
            color: #e65100;
            border: 1px solid #ffb74d;
            border-radius: 4px;
        """)
        if not self.is_streaming():
            self._recompute_timer.start(400)

    def _on_recompute_timer(self):
        """Automatically trigger pipeline recomputation after debounce delay."""
        if self._pipeline_dirty and not self.is_streaming():
            self.config_changed.emit()

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

    def format_issues(self, job) -> list[str]:
        """Translate structured pipeline issues into user-facing text."""
        lines: list[str] = []
        issues = getattr(job, "issues", None)
        if issues is None:
            return list(getattr(job, "warnings", []) or [])
        for issue in issues:
            p = issue.params
            if issue.code == "out_of_bounds":
                lines.append(
                    self.tr("Drawing extends %1 mm beyond the printable area.")
                    .replace("%1", f"{p.get('overhang_mm', 0.0):.1f}")
                )
            elif issue.code == "text_replaced":
                lines.append(
                    self.tr("%1 SVG text element(s) replaced by single-line font (convert text to paths before import to keep the original font).")
                    .replace("%1", str(int(p.get("count", 0))))
                )
            elif issue.code == "disabled_pen_paths":
                lines.append(
                    self.tr("%1 path(s) use disabled pens and will not be plotted.")
                    .replace("%1", str(int(p.get("count", 0))))
                )
        return lines

    def _confirm_start_plot(self, port: str, dev_name: str) -> bool:
        """Show a pre-flight confirmation summary before streaming to hardware."""
        page = self.doc.page
        fmt_str = f"DIN {page.preset}" if page.preset != "Custom" and page.preset.startswith("A") else page.preset
        paper_info = f"{fmt_str} ({page.width_mm:.0f} × {page.height_mm:.0f} mm)"
        pen_list = ", ".join(
            f"SP{pid} ({layer.pen.name})"
            for pid, layer in self.job.layers.items()
        ) if self.job and self.job.layers else "-"
        duration_str = self.job.formatted_duration if self.job else "00m 00s"
        warn_lines = self.format_issues(self.job) if self.job else []
        if self.job and getattr(self.job, "has_out_of_bounds", False) and not self.chk_clip.isChecked():
            warn_lines.append(
                self.tr("Paths extend beyond printable margins while 'Clip to printable area' is disabled!")
            )
        start_step = self.spin_start_step.value()
        if start_step > 0:
            warn_lines.append(self.tr("Resuming plot from step %1").replace("%1", str(start_step)))

        warn_block = ("\n\n⚠️ " + "\n⚠️ ".join(warn_lines)) if warn_lines else ""

        msg = (
            self.tr(
                "Ready to send plot to hardware?\n\n"
                "• Device: %1 (%2)\n"
                "• Paper: %3\n"
                "• Pens required: %4\n"
                "• Estimated time: %5%6"
            )
            .replace("%1", dev_name)
            .replace("%2", port)
            .replace("%3", paper_info)
            .replace("%4", pen_list)
            .replace("%5", duration_str)
            .replace("%6", warn_block)
        )
        resp = QMessageBox.question(
            self,
            self.tr("Confirm Plot Start"),
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        return resp == QMessageBox.StandardButton.Yes

    def start_plot(self):
        """Start streaming HP-GL commands to the selected plotter port."""
        if self.is_streaming():
            return
        if self._probe_thread is not None and self._probe_thread.is_alive():
            self._probe_thread.join(timeout=1.5)

        if self._pipeline_dirty:
            self._recompute_timer.stop()
            self.config_changed.emit()

        if not self.job or not self.job.steps:
            QMessageBox.warning(self, self.tr("Plot Output"), self.tr("No vectors available for output."))
            return

        port = self.combo_port.currentText().strip()
        margin_key = self.combo_margins.currentData() or "exp"
        profile = get_default_profile()
        baud = profile.connection.baudrate
        flow_ctrl = getattr(profile.connection, "flow_control", "rtscts")
        dev_name = profile.name
        dev = self.device_manager.get_active_device() if self.device_manager else None

        if dev:
            dev_name = dev.name
            if not port:
                port = dev.port
            profile = dev.get_profile()
            baud = dev.baudrate
            flow_ctrl = getattr(dev, "flow_control", flow_ctrl)

        if not port:
            QMessageBox.warning(self, self.tr("Plot Output"), self.tr("Please select an interface or address."))
            return

        if not self._confirm_start_plot(port, dev_name):
            return

        emitter = build_emitter(
            document=self.doc,
            device=dev,
            margin_profile=margin_key,
            overrides=self.get_emitter_options(),
        )
        commands = emitter.emit_commands(self.job, self.doc)

        if not commands:
            QMessageBox.warning(self, self.tr("Plot Output"), self.tr("No HP-GL commands generated."))
            return

        self._streamer = SerialStreamer(
            on_progress=lambda s, t, pct, p, d: self._bridge.progress.emit(s, t, pct, p, d),
            on_status=lambda state, msg: self._bridge.status.emit(state.value, msg),
            on_finished=lambda success, msg: self._bridge.finished.emit(success, msg),
        )

        self.btn_start_plot.setEnabled(False)
        self.btn_pause_plot.setEnabled(True)
        self.btn_pause_plot.setText(self.tr("⏸ Pause"))
        self.btn_abort_plot.setEnabled(True)
        self.btn_probe.setEnabled(False)
        self.chk_pause_pen_change.setEnabled(False)
        self.spin_start_step.setEnabled(False)
        self.grp_pipeline.setEnabled(False)
        self.combo_port.setEnabled(False)
        self.combo_margins.setEnabled(False)
        self.combo_rotation.setEnabled(False)
        self.chk_swap_xy.setEnabled(False)
        self.chk_invert_x.setEnabled(False)
        self.chk_invert_y.setEnabled(False)
        self.progress_bar.setValue(0)
        self.lbl_stream_status.setText(self.tr("Starting transmission..."))
        self.stream_active_changed.emit(True)

        started = self._streamer.start_stream(
            port,
            commands,
            baudrate=baud,
            flow_control=flow_ctrl,
            pause_on_pen_change=self.chk_pause_pen_change.isChecked(),
            bytesize=int(getattr(dev, "bytesize", None) or profile.connection.bytesize) if dev else profile.connection.bytesize,
            parity=str(getattr(dev, "parity", None) or profile.connection.parity).upper() if dev else profile.connection.parity,
            stopbits=int(getattr(dev, "stopbits", None) or profile.connection.stopbits) if dev else profile.connection.stopbits,
            start_step_index=self.spin_start_step.value(),
        )
        if not started:
            self._on_stream_finished(False, self.tr("Could not start streamer."))

    def toggle_pause(self):
        """Toggle pause/resume during streaming."""
        if not self._streamer:
            return
        if self._streamer.is_user_paused():
            self._streamer.resume()
            self.btn_pause_plot.setText(self.tr("⏸ Pause"))
        elif self._streamer.is_active():
            self._streamer.pause()
            self.btn_pause_plot.setText(self.tr("▶️ Resume"))

    def abort_plot(self, checked: bool = False, *, wait: bool = False, timeout: float = 1.0):
        """Abort active plot and lift pen immediately."""
        if not self._streamer:
            return
        self.btn_pause_plot.setEnabled(False)
        self.btn_abort_plot.setEnabled(False)
        self.lbl_stream_status.setText(self.tr("Abort initiated (ESC.K & Pen-Up)..."))
        try:
            self._streamer.abort(wait=wait, timeout=timeout)
        except TypeError:
            self._streamer.abort()

    def _on_stream_progress(self, step_idx: int, total_cmds: int, pct: float, pen: int, drawn_m: float):
        self.progress_bar.setValue(int(round(pct)))
        status_msg = (
            self.tr("Command %1/%2 (%3%) • Pen %4 • %5 m")
            .replace("%1", str(step_idx))
            .replace("%2", str(total_cmds))
            .replace("%3", f"{pct:.1f}")
            .replace("%4", str(pen))
            .replace("%5", f"{drawn_m:.2f}")
        )
        self.lbl_stream_status.setText(status_msg)
        self.stream_step_changed.emit(step_idx)

    def _on_stream_status(self, state_str: str, msg: str):
        self.lbl_stream_status.setText(msg)
        if self._streamer and self._streamer.is_user_paused():
            self.btn_pause_plot.setText(self.tr("▶️ Resume"))
        elif state_str == "STREAMING":
            self.btn_pause_plot.setText(self.tr("⏸ Pause"))

    def _on_stream_finished(self, success: bool, msg: str):
        self.btn_start_plot.setEnabled(bool(self.job and self.job.steps))
        self.btn_pause_plot.setEnabled(False)
        self.btn_pause_plot.setText(self.tr("⏸ Pause"))
        self.btn_abort_plot.setEnabled(False)
        self.btn_probe.setEnabled(True)
        self.chk_pause_pen_change.setEnabled(True)
        self.spin_start_step.setEnabled(True)
        self.grp_pipeline.setEnabled(True)
        self.combo_port.setEnabled(True)
        self.combo_margins.setEnabled(True)
        self.combo_rotation.setEnabled(True)
        self.chk_swap_xy.setEnabled(True)
        self.chk_invert_x.setEnabled(True)
        self.chk_invert_y.setEnabled(True)
        self.stream_active_changed.emit(False)

        if success:
            self.progress_bar.setValue(100)
            self.spin_start_step.setValue(0)
            self.lbl_stream_status.setText(f"✓ {msg}")
            if self.job:
                self.stream_step_changed.emit(len(self.job.steps))
        else:
            last_step = getattr(self._streamer, "last_completed_step_index", 0) if self._streamer else 0
            if last_step > 0:
                self.spin_start_step.setValue(last_step)
            self.lbl_stream_status.setText(f"⚠️ {msg}")

    def show_diagnostic_log(self):
        """Open a modal dialog displaying the recorded HP-GL TX/RX trace log."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("HP-GL Diagnostic Log (TX/RX)"))
        dlg.resize(620, 420)
        vbox = QVBoxLayout(dlg)
        txt = QPlainTextEdit(dlg)
        txt.setReadOnly(True)
        entries = self._streamer.get_trace_log() if self._streamer else []
        txt.setPlainText("\n".join(entries) if entries else self.tr("No transmission log entries recorded yet."))
        vbox.addWidget(txt)

        hbox_btn = QHBoxLayout()
        btn_clear = QPushButton(self.tr("Clear Log"), dlg)

        def _clear():
            if self._streamer:
                self._streamer.clear_trace_log()
            txt.setPlainText(self.tr("No transmission log entries recorded yet."))

        btn_clear.clicked.connect(_clear)
        hbox_btn.addWidget(btn_clear)
        hbox_btn.addStretch()
        btn_close = QPushButton(self.tr("Close"), dlg)
        btn_close.clicked.connect(dlg.accept)
        hbox_btn.addWidget(btn_close)
        vbox.addLayout(hbox_btn)
        dlg.exec()

    def closeEvent(self, event):
        if self._streamer and self._streamer.is_active():
            self._streamer.abort(wait=True, timeout=1.0)
        super().closeEvent(event)

    def get_pipeline_config(self) -> PipelineConfig:
        prof = get_default_profile()
        baud: Optional[int] = prof.connection.baudrate
        bytesize = int(prof.connection.bytesize)
        parity = str(prof.connection.parity).upper()
        stopbits = int(prof.connection.stopbits)
        dev = self.device_manager.get_active_device() if self.device_manager else None
        if dev:
            prof = dev.get_profile()
            baud = int(dev.baudrate) if dev.baudrate and dev.baudrate > 0 else prof.connection.baudrate
            bytesize = int(getattr(dev, "bytesize", None) or prof.connection.bytesize)
            parity = str(getattr(dev, "parity", None) or prof.connection.parity).upper()
            stopbits = int(getattr(dev, "stopbits", None) or prof.connection.stopbits)
        bits_per_byte = 1 + bytesize + (0 if parity == "N" else 1) + stopbits
        return PipelineConfig(
            flatten_tolerance_mm=self.spin_flatten.value(),
            merge_tolerance_mm=self.spin_merge.value(),
            simplify_tolerance_mm=self.spin_simplify.value(),
            deduplicate_segments=self.chk_dedup.isChecked(),
            pen_order=str(self.combo_pen_order.currentData() or "id"),
            sort_paths=self.chk_sort.isChecked(),
            clip_to_plottable=self.chk_clip.isChecked(),
            max_speed_mm_s=prof.max_speed_mm_s,
            travel_speed_mm_s=prof.travel_speed_mm_s,
            pen_change_time_s=prof.pen_change_time_s,
            pen_actuation_time_s=prof.pen_actuation_time_s,
            baudrate=baud,
            bits_per_byte=bits_per_byte,
        )

    def set_job(self, job: Optional[PlotJob]):
        if self.is_streaming():
            return
        self._recompute_timer.stop()
        self.job = job
        self._pipeline_dirty = False
        self.btn_recompute.setText(self.tr("Recompute Pipeline"))
        self.btn_recompute.setStyleSheet("")
        max_step = max(0, len(job.steps)) if (job and job.steps) else 0
        self.spin_start_step.setRange(0, max_step)
        self.spin_start_step.setValue(0)

        if not (self._streamer and self._streamer.is_active()):
            self.btn_start_plot.setEnabled(bool(job and job.steps))

        if not job:
            self.lbl_draw.setText("0.00 m")
            self.lbl_travel.setText("0.00 m")
            self.lbl_savings.setText("0 %")
            self.lbl_pen_changes.setText("0")
            self.lbl_duration.setText("00m 00s")
            self.lbl_points.setText("0")
            self.lbl_warnings.setText(self.tr("No paths available"))
            self.lbl_warnings.setStyleSheet("padding: 6px 8px; color: #64748b;")
            return

        draw_m = job.total_draw_mm / 1000.0
        travel_m = job.total_travel_mm / 1000.0
        self.lbl_draw.setText(f"{draw_m:.2f} m")
        self.lbl_travel.setText(f"{travel_m:.2f} m")
        self.lbl_savings.setText(self.tr("%1 % by sorting").replace("%1", f"{job.travel_savings_pct:.1f}"))
        self.lbl_pen_changes.setText(str(job.pen_changes))
        self.lbl_duration.setText(job.formatted_duration)
        self.lbl_points.setText(f"{job.total_points:,}".replace(",", "."))

        # Warnings display
        issue_lines = self.format_issues(job)
        if issue_lines:
            msg = "\n".join(issue_lines)
            self.lbl_warnings.setText(f"⚠️ {msg}")
            self.lbl_warnings.setStyleSheet("""
                padding: 6px 8px;
                background-color: #fff3e0;
                color: #e65100;
                border: 1px solid #ffe0b2;
                border-radius: 4px;
            """)
        else:
            self.lbl_warnings.setText(self.tr("✓ All paths within printable area"))
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
            lbl = QLabel(self.tr("No pens used"))
            lbl.setStyleSheet("color: #94a3b8; font-style: italic; padding: 2px 0;")
            self.vbox_pens.addWidget(lbl)
            return

        for pen_id, layer in sorted(job.layers.items()):
            color = layer.pen.color_hex
            name = layer.pen.name
            line_count = len(layer.lines)
            draw_m = layer.draw_distance_mm / 1000.0

            path_str = self.tr("(1 path, %1 m)").replace("%1", f"{draw_m:.2f}") if line_count == 1 else self.tr("(%1 paths, %2 m)").replace("%1", str(line_count)).replace("%2", f"{draw_m:.2f}")
            chk = QCheckBox(f"{name} {path_str}")
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
