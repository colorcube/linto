"""Main Application Window for Plotter Studio."""

from __future__ import annotations
import os
import math
from typing import Optional, Any
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QAction, QKeySequence, QUndoStack, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QToolBar,
    QStatusBar, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QSizePolicy, QComboBox, QToolButton, QMenu
)
from ..core.document import Document, ImportItem
from ..core.geometry import AffineTransform
from ..core.hpgl_import import is_hpgl_file
from ..core.svg_export import (
    export_document_to_svg,
    export_plot_job_to_svg,
    load_document_from_svg,
    is_project_file,
    import_file_to_item,
)
from ..pipeline.compiler import compile_document_to_plot_job
from .canvas import PlotterCanvas, CanvasMode, extract_droppable_files
from .rulers import RulerWidget, RULER_BREADTH
from .pen_dock import PenDockWidget
from .transform_dock import TransformDockWidget
from .plot_dock import PlotDockWidget
from .object_dock import ObjectDockWidget
from .simulation_bar import PlotSimulationBar
from .icons import get_icon
from ..device import build_emitter, DeviceManager
from .device_dialog import DeviceSettingsDialog
from .page_dialog import PageSetupDialog
from .commands import (
    TransformItemCommand, AssignPenCommand,
    AddItemCommand, DeleteItemsCommand, PageConfigCommand,
    ModifyItemPropertiesCommand,
)


class MainWindow(QMainWindow):
    """
    Main Window integrating Canvas, Rulers, Object Dock, Transform Dock, Pen Dock and Plot Dock.
    """
    def __init__(self, doc: Optional[Document] = None, parent=None):
        super().__init__(parent)
        self.doc = doc or Document()
        self.undo_stack = QUndoStack(self)
        self.device_manager = DeviceManager()
        self._settings = QSettings("PlotterStudio", "PlotterStudio")
        self.current_project_path: Optional[str] = None
        self.undo_stack.cleanChanged.connect(self._update_window_title)

        self._update_window_title()
        self.resize(1280, 850)
        self.setAcceptDrops(True)

        # Central canvas with rulers
        self._setup_central_canvas()

        # Docks
        self._setup_docks()

        # Menus & Toolbar
        self._setup_actions_and_menus()
        self._setup_toolbar()
        self._setup_status_bar()

        # Connect signals
        self._connect_signals()

        # Restore persisted window geometry if available
        self._restore_window_settings()

        # Initial view
        self.canvas.zoom_to_fit()

    def _setup_central_canvas(self):
        container = QWidget(self)
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.canvas = PlotterCanvas(self.doc, container)
        self.ruler_h = RulerWidget(RulerWidget.HORIZONTAL, self.canvas, container)
        self.ruler_v = RulerWidget(RulerWidget.VERTICAL, self.canvas, container)

        # Corner box
        corner = QWidget(container)
        corner.setFixedSize(RULER_BREADTH, RULER_BREADTH)
        corner.setStyleSheet("background-color: #e0e0e0; border-right: 1px solid #ccc; border-bottom: 1px solid #ccc;")

        grid.addWidget(corner, 0, 0)
        grid.addWidget(self.ruler_h, 0, 1)
        grid.addWidget(self.ruler_v, 1, 0)
        grid.addWidget(self.canvas, 1, 1)

        # Simulation bar below canvas (visible only in Plot mode)
        self.simulation_bar = PlotSimulationBar(container)
        self.simulation_bar.hide()
        grid.addWidget(self.simulation_bar, 2, 0, 1, 2)

        self.setCentralWidget(container)

    def _setup_docks(self):
        # Enable docking options for intuitive tabbed dragging and animation
        self.setDockOptions(
            QMainWindow.DockOption.AnimatedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
            | QMainWindow.DockOption.GroupedDragging
        )
        self.setTabPosition(Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)

        # Panel 1: Objekte & Ebenen (Top Right)
        self.object_dock = ObjectDockWidget(self.doc, self.canvas, self)
        self.object_dock.set_undo_stack(self.undo_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.object_dock)

        # Panel 2: Skalieren & Platzieren (Bottom Right)
        self.transform_dock = TransformDockWidget(self.doc, self)
        self.transform_dock.set_undo_stack(self.undo_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.transform_dock)

        # Split vertical: Object Dock on top, Transform Dock below
        self.splitDockWidget(self.object_dock, self.transform_dock, Qt.Vertical)

        # Panel 3: Stifte (Tabified with Transform Dock)
        self.pen_dock = PenDockWidget(self.doc, self)
        self.pen_dock.set_undo_stack(self.undo_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.pen_dock)
        self.tabifyDockWidget(self.transform_dock, self.pen_dock)

        self.transform_dock.raise_()

        # Panel 4: Plot-Vorschau & Ausgabe
        self.plot_dock = PlotDockWidget(self.doc, self)
        self.plot_dock.set_device_manager(self.device_manager)
        self.addDockWidget(Qt.RightDockWidgetArea, self.plot_dock)

        # In initial Layout mode, Plot dock is hidden
        self.plot_dock.hide()

        # Connect dock signals to hide duplicate title bars when tabbed
        self._all_docks = [
            self.object_dock,
            self.transform_dock,
            self.pen_dock,
            self.plot_dock,
        ]
        for dock in self._all_docks:
            dock.topLevelChanged.connect(lambda _: self._schedule_dock_title_update())
            dock.dockLocationChanged.connect(lambda _: self._schedule_dock_title_update())
            dock.visibilityChanged.connect(lambda _: self._schedule_dock_title_update())

        self._update_dock_title_bars()

    def _format_action_tooltip(self, action: QAction, base_tooltip: str) -> str:
        """Append native shortcut text to tooltip if not already present."""
        if "(" in base_tooltip and ")" in base_tooltip:
            return base_tooltip
        sc = action.shortcut().toString(QKeySequence.NativeText)
        if sc:
            return f"{base_tooltip} ({sc})"
        return base_tooltip

    def _setup_actions_and_menus(self):
        menu_bar = self.menuBar()

        # --- File Menu ---
        menu_file = menu_bar.addMenu(self.tr("&File"))

        self.act_new = QAction(self.tr("&New Project"), self)
        self.act_new.setIcon(get_icon("plus"))
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.setToolTip(self._format_action_tooltip(self.act_new, self.tr("Create new project")))
        self.act_new.triggered.connect(self.new_document)
        menu_file.addAction(self.act_new)

        self.act_open_project = QAction(self.tr("&Open Project..."), self)
        self.act_open_project.setIcon(get_icon("open"))
        self.act_open_project.setShortcut(QKeySequence.Open)
        self.act_open_project.setToolTip(self._format_action_tooltip(self.act_open_project, self.tr("Open project or vector file (Ctrl+O)")))
        self.act_open_project.triggered.connect(self.open_project_dialog)
        menu_file.addAction(self.act_open_project)

        self.act_save = QAction(self.tr("&Save Project"), self)
        self.act_save.setIcon(get_icon("save"))
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.setToolTip(self._format_action_tooltip(self.act_save, self.tr("Save project (Ctrl+S)")))
        self.act_save.triggered.connect(self.save_project)
        menu_file.addAction(self.act_save)

        self.act_save_as = QAction(self.tr("Save Project &As..."), self)
        self.act_save_as.setIcon(get_icon("save"))
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.setToolTip(self._format_action_tooltip(self.act_save_as, self.tr("Save project as SVG (Ctrl+Shift+S)")))
        self.act_save_as.triggered.connect(self.save_project_dialog)
        menu_file.addAction(self.act_save_as)

        menu_file.addSeparator()

        self.act_import_svg = QAction(self.tr("&Import..."), self)
        self.act_import_svg.setIcon(get_icon("import"))
        self.act_import_svg.setShortcut(QKeySequence("Ctrl+I"))
        self.act_import_svg.setToolTip(self._format_action_tooltip(self.act_import_svg, self.tr("Import SVG or plot file (Ctrl+I)")))
        self.act_import_svg.triggered.connect(self.import_svg_dialog)
        menu_file.addAction(self.act_import_svg)

        menu_file.addSeparator()

        self.act_page_setup = QAction(self.tr("&Page Setup..."), self)
        self.act_page_setup.setIcon(get_icon("page"))
        self.act_page_setup.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_page_setup.setToolTip(self._format_action_tooltip(self.act_page_setup, self.tr("Edit page setup & paper format (Ctrl+Shift+P)")))
        self.act_page_setup.triggered.connect(self.open_page_setup_dialog)
        menu_file.addAction(self.act_page_setup)

        menu_file.addSeparator()

        self.act_exit = QAction(self.tr("E&xit"), self)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

        # --- Edit Menu ---
        menu_edit = menu_bar.addMenu(self.tr("&Edit"))

        self.act_undo = self.undo_stack.createUndoAction(self, self.tr("&Undo"))
        self.act_undo.setIcon(get_icon("undo"))
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.setToolTip(self._format_action_tooltip(self.act_undo, self.tr("Undo (Ctrl+Z)")))
        menu_edit.addAction(self.act_undo)

        self.act_redo = self.undo_stack.createRedoAction(self, self.tr("&Redo"))
        self.act_redo.setIcon(get_icon("redo"))
        self.act_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.act_redo.setToolTip(self._format_action_tooltip(self.act_redo, self.tr("Redo (Ctrl+Y)")))
        menu_edit.addAction(self.act_redo)

        menu_edit.addSeparator()

        self.act_select_all = QAction(self.tr("Select &All"), self)
        self.act_select_all.setShortcut(QKeySequence.SelectAll)
        self.act_select_all.setToolTip(self._format_action_tooltip(self.act_select_all, self.tr("Select all objects on sheet (Ctrl+A)")))
        self.act_select_all.triggered.connect(self.canvas.select_all_items)
        menu_edit.addAction(self.act_select_all)

        self.act_deselect_all = QAction(self.tr("Deselect All"), self)
        self.act_deselect_all.setShortcut(QKeySequence("Esc"))
        self.act_deselect_all.setToolTip(self.tr("Deselect all objects (Esc)"))
        self.act_deselect_all.triggered.connect(self.canvas.clear_selection)
        menu_edit.addAction(self.act_deselect_all)

        menu_edit.addSeparator()

        self.act_duplicate = QAction(self.tr("&Duplicate"), self)
        self.act_duplicate.setIcon(get_icon("duplicate"))
        self.act_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.act_duplicate.setToolTip(self._format_action_tooltip(self.act_duplicate, self.tr("Duplicate selected object (Ctrl+D)")))
        self.act_duplicate.triggered.connect(self.duplicate_selected_items)
        menu_edit.addAction(self.act_duplicate)

        self.act_delete = QAction(self.tr("&Delete"), self)
        self.act_delete.setIcon(get_icon("delete"))
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.setToolTip(self._format_action_tooltip(self.act_delete, self.tr("Delete selected objects (Del)")))
        self.act_delete.triggered.connect(self.delete_selected_items)
        menu_edit.addAction(self.act_delete)

        menu_edit.addSeparator()

        self.act_rotate_ccw = QAction(self.tr("Rotate 90° CCW (-90°)"), self)
        self.act_rotate_ccw.setIcon(get_icon("rotate-ccw"))
        self.act_rotate_ccw.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.act_rotate_ccw.setToolTip(self._format_action_tooltip(self.act_rotate_ccw, self.tr("Rotate selection 90° counter-clockwise (Ctrl+Shift+R)")))
        self.act_rotate_ccw.triggered.connect(lambda: self.rotate_selected_items(-90.0))
        menu_edit.addAction(self.act_rotate_ccw)

        self.act_rotate_cw = QAction(self.tr("Rotate 90° CW (+90°)"), self)
        self.act_rotate_cw.setIcon(get_icon("rotate-cw"))
        self.act_rotate_cw.setShortcut(QKeySequence("Ctrl+R"))
        self.act_rotate_cw.setToolTip(self._format_action_tooltip(self.act_rotate_cw, self.tr("Rotate selection 90° clockwise (Ctrl+R)")))
        self.act_rotate_cw.triggered.connect(lambda: self.rotate_selected_items(90.0))
        menu_edit.addAction(self.act_rotate_cw)

        self.act_flip_h = QAction(self.tr("Flip Horizontal"), self)
        self.act_flip_h.setToolTip(self.tr("Flip selection horizontally"))
        self.act_flip_h.triggered.connect(lambda: self.flip_selected_items(horizontal=True))
        menu_edit.addAction(self.act_flip_h)

        self.act_flip_v = QAction(self.tr("Flip Vertical"), self)
        self.act_flip_v.setToolTip(self.tr("Flip selection vertically"))
        self.act_flip_v.triggered.connect(lambda: self.flip_selected_items(horizontal=False))
        menu_edit.addAction(self.act_flip_v)

        menu_edit.addSeparator()

        # Assign pen 1..8 shortcuts
        self._pen_actions: list[QAction] = []
        for pen_id in range(1, 9):
            act = QAction(self.tr("Assign to Pen %1").replace("%1", str(pen_id)), self)
            act.setShortcut(QKeySequence(str(pen_id)))
            act.triggered.connect(lambda checked=False, pid=pen_id: self.assign_selection_to_pen(pid))
            menu_edit.addAction(act)
            self._pen_actions.append(act)

        # --- View Menu ---
        menu_view = menu_bar.addMenu(self.tr("&View"))

        # Mode switching group
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)

        self.act_mode_layout = QAction(self.tr("Layout"), self)
        self.act_mode_layout.setIcon(get_icon("mode-layout"))
        self.act_mode_layout.setCheckable(True)
        self.act_mode_layout.setChecked(True)
        self.act_mode_layout.setShortcut(QKeySequence("Ctrl+L"))
        self.act_mode_layout.setToolTip(self._format_action_tooltip(self.act_mode_layout, self.tr("Layout Mode (Ctrl+L)")))
        self.act_mode_layout.triggered.connect(self.switch_to_layout_mode)
        self.mode_group.addAction(self.act_mode_layout)
        menu_view.addAction(self.act_mode_layout)

        self.act_mode_plot = QAction(self.tr("Output"), self)
        self.act_mode_plot.setIcon(get_icon("mode-plot"))
        self.act_mode_plot.setCheckable(True)
        self.act_mode_plot.setShortcut(QKeySequence("Ctrl+P"))
        self.act_mode_plot.setToolTip(self._format_action_tooltip(self.act_mode_plot, self.tr("Output / Plot Mode (Ctrl+P)")))
        self.act_mode_plot.triggered.connect(self.switch_to_plot_mode)
        self.mode_group.addAction(self.act_mode_plot)
        menu_view.addAction(self.act_mode_plot)

        menu_view.addSeparator()

        self.act_zoom_fit = QAction(self.tr("Fit Sheet to Window"), self)
        self.act_zoom_fit.setIcon(get_icon("zoom-fit"))
        self.act_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.act_zoom_fit.setToolTip(self._format_action_tooltip(self.act_zoom_fit, self.tr("Fit sheet to window (Ctrl+0)")))
        self.act_zoom_fit.triggered.connect(self.canvas.zoom_to_fit)
        menu_view.addAction(self.act_zoom_fit)

        self.act_zoom_selection = QAction(self.tr("Zoom to Selection"), self)
        self.act_zoom_selection.setIcon(get_icon("zoom-in"))
        self.act_zoom_selection.setShortcut(QKeySequence("Ctrl+Shift+0"))
        self.act_zoom_selection.setToolTip(self._format_action_tooltip(self.act_zoom_selection, self.tr("Zoom to selected objects (Ctrl+Shift+0)")))
        self.act_zoom_selection.triggered.connect(self.canvas.zoom_to_selection)
        menu_view.addAction(self.act_zoom_selection)

        self.act_zoom_in = QAction(self.tr("Zoom In"), self)
        self.act_zoom_in.setIcon(get_icon("zoom-in"))
        self.act_zoom_in.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl++"), QKeySequence("Ctrl+="), QKeySequence("+"), QKeySequence("=")])
        self.act_zoom_in.setToolTip(self._format_action_tooltip(self.act_zoom_in, self.tr("Zoom In (Ctrl++)")))
        self.act_zoom_in.triggered.connect(lambda checked=False: self.canvas.zoom_in())
        menu_view.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction(self.tr("Zoom Out"), self)
        self.act_zoom_out.setIcon(get_icon("zoom-out"))
        self.act_zoom_out.setShortcuts([QKeySequence.ZoomOut, QKeySequence("Ctrl+-"), QKeySequence("-")])
        self.act_zoom_out.setToolTip(self._format_action_tooltip(self.act_zoom_out, self.tr("Zoom Out (Ctrl+-)")))
        self.act_zoom_out.triggered.connect(lambda checked=False: self.canvas.zoom_out())
        menu_view.addAction(self.act_zoom_out)

        # Docks toggle & Display options
        menu_view.addSeparator()
        self.act_show_nodes = QAction(self.tr("Show Vertices (Nodes)"), self)
        self.act_show_nodes.setCheckable(True)
        self.act_show_nodes.setChecked(False)
        self.act_show_nodes.toggled.connect(self.plot_dock.chk_show_nodes.setChecked)
        menu_view.addAction(self.act_show_nodes)

        menu_view.addSeparator()
        menu_view.addAction(self.object_dock.toggleViewAction())
        menu_view.addAction(self.transform_dock.toggleViewAction())
        menu_view.addAction(self.pen_dock.toggleViewAction())
        menu_view.addAction(self.plot_dock.toggleViewAction())

        # --- Help Menu ---
        menu_help = menu_bar.addMenu(self.tr("&Help"))
        act_about = QAction(self.tr("&About Plotter Studio"), self)
        act_about.triggered.connect(self.show_about)
        menu_help.addAction(act_about)

    def _setup_toolbar(self):
        toolbar = QToolBar(self.tr("Main Toolbar"), self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        self.toolbar = toolbar

        # Mode switches with text beside icon
        toolbar.addAction(self.act_mode_layout)
        toolbar.addAction(self.act_mode_plot)

        btn_layout = toolbar.widgetForAction(self.act_mode_layout)
        if btn_layout:
            btn_layout.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn_plot = toolbar.widgetForAction(self.act_mode_plot)
        if btn_plot:
            btn_plot.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        toolbar.addSeparator()

        toolbar.addAction(self.act_open_project)
        toolbar.addAction(self.act_save)
        toolbar.addAction(self.act_import_svg)
        toolbar.addSeparator()

        # Zoom controls (fit to window, zoom in, zoom out) before Undo/Redo
        toolbar.addAction(self.act_zoom_fit)
        toolbar.addAction(self.act_zoom_in)
        toolbar.addAction(self.act_zoom_out)
        toolbar.addSeparator()

        toolbar.addAction(self.act_undo)
        toolbar.addAction(self.act_redo)
        toolbar.addSeparator()

        toolbar.addAction(self.act_duplicate)
        toolbar.addAction(self.act_delete)
        toolbar.addSeparator()

        toolbar.addAction(self.act_rotate_ccw)
        toolbar.addAction(self.act_rotate_cw)
        toolbar.addSeparator()

        btn_center = toolbar.addAction(self.tr("Center on Sheet"))
        btn_center.setIcon(get_icon("align-center"))
        btn_center.setToolTip(self.tr("Center on sheet or printable area"))
        btn_center.triggered.connect(self.transform_dock.align_center_both)
        self.act_align_center = btn_center

        btn_fit = toolbar.addAction(self.tr("Fit to Sheet"))
        btn_fit.setIcon(get_icon("fit-page"))
        btn_fit.setToolTip(self.tr("Fit artwork to sheet"))
        btn_fit.triggered.connect(self.transform_dock.fit_to_page)
        self.act_fit_sheet = btn_fit

        btn_orig = toolbar.addAction(self.tr("Original Size (1:1)"))
        btn_orig.setIcon(get_icon("original-size"))
        btn_orig.setToolTip(self.tr("Reset to 1:1 original size"))
        btn_orig.triggered.connect(self.transform_dock.reset_to_original_size)
        self.act_orig_size = btn_orig

        self._layout_editing_actions = [
            self.act_duplicate,
            self.act_delete,
            self.act_rotate_ccw,
            self.act_rotate_cw,
            self.act_flip_h,
            self.act_flip_v,
            self.act_align_center,
            self.act_fit_sheet,
            self.act_orig_size,
            *self._pen_actions,
        ]

        # Spacer to push paper setup & device settings to the right
        spacer = QWidget(toolbar)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Paper Setup Button in toolbar showing current format
        self.btn_page_setup = QToolButton(toolbar)
        self.btn_page_setup.setIcon(get_icon("page", size=18))
        self.btn_page_setup.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_page_setup.setToolTip(self.tr("Edit page setup and margins..."))
        self.btn_page_setup.clicked.connect(self.open_page_setup_dialog)
        toolbar.addWidget(self.btn_page_setup)

        toolbar.addSeparator()

        lbl_device = QLabel(self.tr(" Device: "), toolbar)
        lbl_device.setStyleSheet("color: #4b5563;")
        toolbar.addWidget(lbl_device)

        self.combo_active_device = QComboBox(toolbar)
        self.combo_active_device.setMinimumWidth(220)
        self.combo_active_device.setToolTip(self.tr("Active plotter device for inquiry and plotting"))
        self.combo_active_device.currentIndexChanged.connect(self._on_active_device_changed)
        toolbar.addWidget(self.combo_active_device)

        self.btn_device_settings = QToolButton(toolbar)
        self.btn_device_settings.setIcon(get_icon("settings", size=18))
        self.btn_device_settings.setToolTip(self.tr("Configure plotter devices..."))
        self.btn_device_settings.clicked.connect(self.open_device_settings_dialog)
        toolbar.addWidget(self.btn_device_settings)

        self._refresh_device_selector()
        self._update_paper_display()

    def _setup_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_coord = QLabel("X: 0.0 mm | Y: 0.0 mm")
        self.lbl_zoom = QLabel("Zoom: 100 %")
        self.lbl_info = QLabel(self.tr("Ready"))
        self.lbl_paper_status = QLabel("DIN A3 (420 × 297 mm)")
        self.lbl_paper_status.setStyleSheet("color: #4b5563; font-size: 11px; padding: 0 4px;")

        self.status_bar.addWidget(self.lbl_info, 1)
        self.status_bar.addPermanentWidget(self.lbl_paper_status)
        self.status_bar.addPermanentWidget(self.lbl_coord)
        self.status_bar.addPermanentWidget(self.lbl_zoom)

    def _connect_signals(self):
        # Canvas mouse coordinates to rulers & status
        self.canvas.mouse_moved_mm.connect(self._on_mouse_moved)
        self.canvas.zoom_changed.connect(self._on_zoom_changed)
        self.canvas.file_dropped.connect(self.import_svg_file)
        self.canvas.selection_changed_signal.connect(self._on_selection_changed)
        self.canvas.items_drag_finished.connect(self._on_items_drag_finished)
        self.canvas.context_menu_requested.connect(self._show_canvas_context_menu)

        # Pen dock
        self.pen_dock.pen_changed.connect(self._on_pens_changed)
        self.pen_dock.assign_selection_to_pen.connect(self.assign_selection_to_pen)

        # Transform dock
        self.transform_dock.item_transformed.connect(self._on_item_transformed)
        self.canvas.item_transformed_live.connect(self._on_item_transformed_live)

        # Simulation bar
        self.simulation_bar.step_changed.connect(self.canvas.set_simulation_step)

        # Plot dock
        self.plot_dock.config_changed.connect(self.recompile_plot_job)
        self.plot_dock.toggle_travels.connect(self.canvas.set_show_travels)
        self.plot_dock.toggle_nodes.connect(self.canvas.set_show_nodes)
        self.plot_dock.toggle_nodes.connect(self.act_show_nodes.setChecked)
        self.plot_dock.pen_filter_changed.connect(self.canvas.set_visible_pens)
        self.plot_dock.export_hpgl_requested.connect(self.export_hpgl_dialog)
        self.plot_dock.export_svg_requested.connect(self.export_plot_svg_dialog)
        self.plot_dock.stream_step_changed.connect(self.canvas.set_simulation_step)
        self.plot_dock.stream_step_changed.connect(self.simulation_bar.set_step)
        self.plot_dock.stream_active_changed.connect(self._on_stream_active_changed)

        # Object dock
        self.object_dock.btn_import.clicked.connect(self.import_svg_dialog)
        self.object_dock.document_modified.connect(self._on_document_modified)
        self.canvas.selection_changed_signal.connect(self.object_dock.sync_from_canvas_selection)

    def is_plot_active(self) -> bool:
        """Return True when a hardware plot stream is currently running or paused."""
        return bool(hasattr(self, "plot_dock") and self.plot_dock and self.plot_dock.is_streaming())

    def _on_stream_active_changed(self, active: bool):
        """Lock/unlock editing, file, and mode controls while a plot is actively streaming."""
        self.setAcceptDrops(not active)
        self.act_new.setEnabled(not active)
        self.act_open_project.setEnabled(not active)
        self.act_import_svg.setEnabled(not active)
        self.act_page_setup.setEnabled(not active)
        self.act_mode_layout.setEnabled(not active)
        self.btn_page_setup.setEnabled(not active)
        self.combo_active_device.setEnabled(not active)
        self.btn_device_settings.setEnabled(not active)
        self.object_dock.setEnabled(not active)
        self.transform_dock.setEnabled(not active)
        self.pen_dock.setEnabled(not active)
        self.simulation_bar.setEnabled(not active)
        if active:
            self.act_undo.setEnabled(False)
            self.act_redo.setEnabled(False)
            for act in self._layout_editing_actions:
                act.setEnabled(False)
            self.lbl_info.setText(self.tr("Plot in progress..."))
        else:
            self.act_undo.setEnabled(self.undo_stack.canUndo())
            self.act_redo.setEnabled(self.undo_stack.canRedo())
            in_layout = (self.canvas._mode == CanvasMode.LAYOUT)
            for act in self._layout_editing_actions:
                act.setEnabled(in_layout)
            if not in_layout and self.plot_dock.is_pipeline_dirty():
                self.recompile_plot_job()
            self.lbl_info.setText(self.tr("Output active") if not in_layout else self.tr("Layout active"))

    def _refresh_device_selector(self):
        self.combo_active_device.blockSignals(True)
        self.combo_active_device.clear()
        active_id = self.device_manager.active_device_id
        active_idx = 0
        devices = self.device_manager.list_devices()
        for i, dev in enumerate(devices):
            label = f"{dev.name} ({dev.port})"
            self.combo_active_device.addItem(label, dev.id)
            if dev.id == active_id:
                active_idx = i
        if self.combo_active_device.count() > 0:
            self.combo_active_device.setCurrentIndex(active_idx)
        self.combo_active_device.blockSignals(False)

    def _capture_page_margin_state(self) -> dict[str, Any]:
        p = self.doc.page
        return {
            "margin_left_mm": p.margin_left_mm,
            "margin_right_mm": p.margin_right_mm,
            "margin_top_mm": p.margin_top_mm,
            "margin_bottom_mm": p.margin_bottom_mm,
            "device_profile": p.device_profile,
            "margin_profile": p.margin_profile,
        }

    def _apply_active_device_to_page_and_plot_dock(self, dev: ConfiguredDevice, record_undo: bool = False):
        if self.doc.page.device_profile != "custom" and dev.model_id:
            old_state = self._capture_page_margin_state()
            self.doc.page.apply_device_profile(
                dev.model_id, self.doc.page.feed_edge, dev.margin_profile
            )
            new_state = self._capture_page_margin_state()
            if record_undo and old_state != new_state:
                cmd = PageConfigCommand(
                    self.doc.page,
                    old_state,
                    new_state,
                    self._on_page_changed,
                    text=self.tr("Apply device profile '%1'").replace("%1", dev.name),
                )
                self.undo_stack.push(cmd)
            else:
                self._on_page_changed()
        self.plot_dock.apply_configured_device(dev)
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def _on_active_device_changed(self):
        dev_id = self.combo_active_device.currentData()
        if not dev_id:
            return
        self.device_manager.set_active_device(dev_id)
        dev = self.device_manager.get_active_device()
        if dev:
            self._apply_active_device_to_page_and_plot_dock(dev, record_undo=True)

    def open_device_settings_dialog(self):
        dlg = DeviceSettingsDialog(self.device_manager, parent=self)
        if dlg.exec():
            self._refresh_device_selector()
            dev = self.device_manager.get_active_device()
            if dev:
                self._apply_active_device_to_page_and_plot_dock(dev, record_undo=True)

    def open_page_setup_dialog(self):
        dlg = PageSetupDialog(self.doc, self.device_manager, self.undo_stack, parent=self)
        dlg.page_changed.connect(self._on_page_changed)
        if dlg.exec():
            self._on_page_changed()

    def _update_paper_display(self):
        p = self.doc.page
        if p.preset != "Custom":
            fmt_str = f"DIN {p.preset}" if p.preset.startswith("A") else p.preset
            orient_str = self.tr("Landscape (short)") if p.orientation == "landscape" else self.tr("Portrait (short)")
            summary = f"{fmt_str} {orient_str} ({p.width_mm:.0f} × {p.height_mm:.0f} mm)"
        else:
            summary = f"Custom ({p.width_mm:.0f} × {p.height_mm:.0f} mm)"
        if hasattr(self, "btn_page_setup"):
            self.btn_page_setup.setText(summary)
            self.btn_page_setup.setToolTip(
                self.tr("Page setup: %1 (Click to edit)").replace("%1", summary)
            )
        if hasattr(self, "lbl_paper_status"):
            self.lbl_paper_status.setText(self.tr("Sheet: %1").replace("%1", summary))

    def _on_document_modified(self):
        self.canvas.viewport().update()
        self._on_selection_changed()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def duplicate_selected_items(self):
        self.object_dock.duplicate_selected()

    def _on_mouse_moved(self, x_mm: float, y_mm: float):
        self.ruler_h.set_cursor_pos(x_mm)
        self.ruler_v.set_cursor_pos(y_mm)
        self.lbl_coord.setText(f"X: {x_mm:.1f} mm | Y: {y_mm:.1f} mm")

    def _on_zoom_changed(self, zoom: float):
        self.lbl_zoom.setText(f"Zoom: {int(zoom * 100)} %")
        self.ruler_h.update()
        self.ruler_v.update()

    def _on_page_changed(self):
        self._update_paper_display()
        self.transform_dock.refresh_item_fields()
        self.canvas.update_scene_rect()
        self.canvas.zoom_to_fit()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def _on_pens_changed(self):
        self.canvas.viewport().update()
        self._on_selection_changed()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def _on_item_transformed(self):
        for g_item in self.canvas._item_map.values():
            g_item.sync_from_transform()
        self.canvas.viewport().update()
        self._on_selection_changed()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def _on_item_transformed_live(self):
        self._on_selection_changed()

    def _on_item_drag_finished(self, item: ImportItem, old_t: AffineTransform, new_t: AffineTransform):
        self._on_items_drag_finished([(item, old_t, new_t)])

    def _on_items_drag_finished(self, changes: list[tuple[ImportItem, AffineTransform, AffineTransform]]):
        if not changes:
            return
        if len(changes) == 1:
            item, old_t, new_t = changes[0]
            scale_diff = abs(math.hypot(old_t.a, old_t.b) - math.hypot(new_t.a, new_t.b))
            if scale_diff > 1e-4:
                text = self.tr("Scale %1").replace("%1", item.name)
            else:
                text = self.tr("Move %1").replace("%1", item.name)
            cmd = TransformItemCommand(
                item, old_t, new_t, self._on_item_transformed, text=text
            )
            self.undo_stack.push(cmd)
        else:
            macro_text = self.tr("Move %1 objects").replace("%1", str(len(changes)))
            self.undo_stack.beginMacro(macro_text)
            for item, old_t, new_t in changes:
                cmd = TransformItemCommand(
                    item, old_t, new_t, self._on_item_transformed, text=macro_text
                )
                self.undo_stack.push(cmd)
            self.undo_stack.endMacro()

    def rotate_selected_items(self, angle_degrees: float):
        """Rotate all currently selected unlocked items by angle_degrees."""
        selected = [it for it in self.canvas.get_selected_import_items() if not it.locked]
        if not selected:
            return
        self.transform_dock.set_selected_items(selected)
        self.transform_dock.rotate_selected(angle_degrees)

    def flip_selected_items(self, horizontal: bool = True):
        """Flip all currently selected unlocked items horizontally or vertically."""
        selected = [it for it in self.canvas.get_selected_import_items() if not it.locked]
        if not selected:
            return
        self.transform_dock.set_selected_items(selected)
        if horizontal:
            self.transform_dock.flip_horizontal()
        else:
            self.transform_dock.flip_vertical()

    def _on_selection_changed(self):
        selected = self.canvas.get_selected_import_items()
        if selected:
            item = selected[0]
            self.transform_dock.set_selected_items(selected)
            b = item.current_bounds
            if b:
                is_oob = self.doc.page.is_bounds_outside_plottable(b)
                warn_text = self.tr(" — ⚠️ Outside printable area!") if is_oob else ""
                if len(selected) == 1:
                    self.lbl_info.setText(
                        self.tr("Selected: %1 (%2 x %3 mm, Scale: %4%)%5")
                        .replace("%1", item.name)
                        .replace("%2", f"{b.width:.1f}")
                        .replace("%3", f"{b.height:.1f}")
                        .replace("%4", f"{item.scale_percent:.0f}")
                        .replace("%5", warn_text)
                    )
                else:
                    self.lbl_info.setText(self.tr("%1 objects selected").replace("%1", str(len(selected))))
        else:
            self.transform_dock.set_selected_items([])
            self.lbl_info.setText(self.tr("%1 object(s) on sheet").replace("%1", str(len(self.doc.items))))

    def _update_window_title(self, is_clean: Optional[bool] = None):
        try:
            if is_clean is None:
                is_clean = self.undo_stack.isClean()
            dirty_suffix = " *" if not is_clean else ""
            if self.current_project_path:
                self.setWindowTitle(f"Plotter Studio — {os.path.basename(self.current_project_path)}{dirty_suffix}")
            else:
                self.setWindowTitle(f"Plotter Studio{dirty_suffix}")
        except RuntimeError:
            pass

    def _get_last_dir(self) -> str:
        if hasattr(self, "_settings") and self._settings is not None:
            val = self._settings.value("paths/last_dir", "")
            if isinstance(val, str) and val and os.path.isdir(val):
                return val
        return ""

    def _set_last_dir(self, filepath: str):
        if not filepath or not hasattr(self, "_settings") or self._settings is None:
            return
        parent = os.path.dirname(os.path.abspath(filepath))
        if os.path.isdir(parent):
            self._settings.setValue("paths/last_dir", parent)

    def _restore_window_settings(self):
        if not hasattr(self, "_settings") or self._settings is None:
            return
        geom = self._settings.value("window/geometry")
        if geom:
            try:
                self.restoreGeometry(geom)
            except Exception:
                pass

    def _save_window_settings(self):
        if not hasattr(self, "_settings") or self._settings is None:
            return
        try:
            self._settings.setValue("window/geometry", self.saveGeometry())
        except Exception:
            pass

    def _confirm_abort_active_plot(self) -> bool:
        """Ask user before aborting an active plot when closing the window."""
        if not self.is_plot_active():
            return True

        resp = QMessageBox.question(
            self,
            self.tr("Plot in Progress"),
            self.tr(
                "A plot is currently running.\n\n"
                "Do you want to abort the plot and lift the pen before closing?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.plot_dock.abort_plot(wait=True, timeout=1.0)
            return True
        return False

    def _confirm_discard_unsaved_changes(self) -> bool:
        """Ask user whether to save or discard unsaved changes. Returns True to proceed."""
        if self.undo_stack.isClean():
            return True

        resp = QMessageBox.question(
            self,
            self.tr("Unsaved Changes"),
            self.tr(
                "The current document contains unsaved changes.\n\n"
                "Do you want to save your changes before continuing?"
            ),
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if resp == QMessageBox.StandardButton.Save:
            return self.save_project()
        if resp == QMessageBox.StandardButton.Discard:
            return True
        return False

    def new_document(self):
        if self.is_plot_active():
            return
        if not self._confirm_discard_unsaved_changes():
            return
        fresh_doc = Document()
        self.doc.items.clear()
        self.doc.page = fresh_doc.page
        self.doc.pens = fresh_doc.pens
        dev = self.device_manager.get_active_device() if hasattr(self, "device_manager") and self.device_manager else None
        if dev and dev.model_id:
            self.doc.page.apply_device_profile(
                dev.model_id, self.doc.page.feed_edge, dev.margin_profile
            )
        self.current_project_path = None
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._update_window_title()
        self.canvas.update_scene_rect()
        self.canvas.rebuild_items()
        self.canvas.zoom_to_fit()
        self.object_dock.refresh()
        self.pen_dock.refresh_table()
        self.transform_dock.set_active_item(None)
        self._update_paper_display()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()
        self.lbl_info.setText(self.tr("New document created"))

    def open_project_dialog(self):
        if self.is_plot_active():
            return
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open Project or Vector File"),
            self._get_last_dir(),
            self.tr("Vector Files (*.svg *.hpgl *.plt);;SVG Files (*.svg);;HP-GL Plot Files (*.hpgl *.plt);;All Files (*)"),
        )
        if fpath:
            self.load_project_file(fpath)

    def load_project_file(self, fpath: str):
        if self.is_plot_active():
            return
        if not self._confirm_discard_unsaved_changes():
            return
        try:
            self._set_last_dir(fpath)
            is_proj = is_project_file(fpath)
            loaded_doc = load_document_from_svg(fpath)
            self.doc.page = loaded_doc.page
            self.doc.pens = loaded_doc.pens
            self.doc.items = loaded_doc.items
            self.current_project_path = fpath if is_proj else None
            self.undo_stack.clear()
            self.undo_stack.setClean()
            self._update_window_title()
            self._update_paper_display()
            self.transform_dock.refresh_item_fields()
            self.canvas.update_scene_rect()
            self.canvas.rebuild_items()
            self.canvas.zoom_to_fit()
            self.object_dock.refresh()
            self.pen_dock.refresh_table()
            self.transform_dock.set_active_item(None)
            self._on_selection_changed()
            if self.canvas._mode == CanvasMode.PLOT:
                self.recompile_plot_job()

            if is_proj:
                self.lbl_info.setText(
                    self.tr("Project loaded: %1 (%2 object(s))")
                    .replace("%1", os.path.basename(fpath))
                    .replace("%2", str(len(self.doc.items)))
                )
            else:
                num_paths = sum(len(it.paths) for it in self.doc.items)
                fmt_label = "HP-GL" if is_hpgl_file(fpath) else "SVG"
                self.lbl_info.setText(
                    self.tr("%1 loaded: %2 (%3 paths)")
                    .replace("%1", fmt_label)
                    .replace("%2", os.path.basename(fpath))
                    .replace("%3", str(num_paths))
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Error Opening File"),
                self.tr("Could not load file:\n%1").replace("%1", str(e)),
            )

    def import_svg_dialog(self):
        if self.is_plot_active():
            return
        fpath, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Import Vector Artwork"),
            self._get_last_dir(),
            self.tr("Vector Files (*.svg *.hpgl *.plt);;SVG Files (*.svg);;HP-GL Plot Files (*.hpgl *.plt);;All Files (*)"),
        )
        if fpath:
            self.import_svg_file(fpath)

    def import_svg_file(self, fpath: str):
        if self.is_plot_active():
            return
        try:
            self._set_last_dir(fpath)
            if not is_hpgl_file(fpath) and is_project_file(fpath):
                resp = QMessageBox.question(
                    self,
                    self.tr("Project File Detected"),
                    self.tr(
                        "The file '%1' is a complete Plotter Studio project.\n\n"
                        "Do you want to open the full project (Yes) or import it as a single object onto the current sheet (No)?"
                    ).replace("%1", os.path.basename(fpath)),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if resp == QMessageBox.StandardButton.Cancel:
                    return
                if resp == QMessageBox.StandardButton.Yes:
                    self.load_project_file(fpath)
                    return

            item = import_file_to_item(fpath, self.doc.pens, target_box=self.doc.page.plottable_box)

            cmd = AddItemCommand(
                self.doc,
                item,
                lambda: self._on_item_structure_changed(select_id=item.item_id),
                text=self.tr("Import %1").replace("%1", os.path.basename(fpath)),
            )
            self.undo_stack.push(cmd)
            if getattr(item, "ignored_text_count", 0) > 0:
                self.lbl_info.setText(
                    self.tr("Imported: %1 (⚠️ %2 <text> element(s) replaced by single-line font – convert text to paths for original font)")
                    .replace("%1", os.path.basename(fpath))
                    .replace("%2", str(item.ignored_text_count))
                )
            else:
                self.lbl_info.setText(self.tr("Imported: %1").replace("%1", os.path.basename(fpath)))
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Import Error"),
                self.tr("Could not import file:\n%1").replace("%1", str(e)),
            )

    def _show_canvas_context_menu(self, global_pos):
        """Show context menu for right-click on canvas in Layout mode."""
        if self.is_plot_active():
            return
        menu = QMenu(self)
        selected = self.canvas.get_selected_import_items()
        unlocked = [it for it in selected if not it.locked]

        if selected:
            pen_menu = menu.addMenu(self.tr("Assign to Pen"))
            pen_menu.setEnabled(bool(unlocked))
            for p in self.doc.pens:
                act_p = pen_menu.addAction(f"SP{p.pen_id} — {p.name}")
                act_p.triggered.connect(lambda checked=False, pid=p.pen_id: self.assign_selection_to_pen(pid))

            menu.addSeparator()
            menu.addAction(self.act_rotate_ccw)
            menu.addAction(self.act_rotate_cw)
            menu.addAction(self.act_flip_h)
            menu.addAction(self.act_flip_v)
            menu.addSeparator()
            menu.addAction(self.act_duplicate)

            all_locked = all(it.locked for it in selected)
            act_lock = menu.addAction(self.tr("Unlock") if all_locked else self.tr("Lock"))

            def _toggle_lock():
                target_lock = not all_locked
                action_text = self.tr("Lock") if target_lock else self.tr("Unlock")
                if len(selected) > 1:
                    self.undo_stack.beginMacro(action_text)
                for it in selected:
                    cmd = ModifyItemPropertiesCommand(
                        it,
                        {"locked": it.locked},
                        {"locked": target_lock},
                        self._on_item_structure_changed,
                        text=action_text,
                    )
                    self.undo_stack.push(cmd)
                if len(selected) > 1:
                    self.undo_stack.endMacro()

            act_lock.triggered.connect(_toggle_lock)
            menu.addAction(self.act_delete)
            menu.addSeparator()
            menu.addAction(self.act_zoom_selection)
        else:
            menu.addAction(self.act_import_svg)
            menu.addAction(self.act_select_all)
            menu.addSeparator()

        menu.addAction(self.act_zoom_fit)
        menu.exec(global_pos)

    def _save_project_to_path(self, fpath: str) -> bool:
        try:
            export_document_to_svg(self.doc, fpath)
            self.current_project_path = fpath
            self._set_last_dir(fpath)
            self.undo_stack.setClean()
            self._update_window_title()
            self.lbl_info.setText(self.tr("Saved to: %1").replace("%1", os.path.basename(fpath)))
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Save Error"),
                self.tr("Error saving file:\n%1").replace("%1", str(e)),
            )
            return False

    def save_project(self) -> bool:
        """Save project directly to current_project_path or open Save As dialog."""
        if self.current_project_path:
            return self._save_project_to_path(self.current_project_path)
        return self.save_project_dialog()

    def save_project_dialog(self) -> bool:
        last_dir = self._get_last_dir()
        default_path = self.current_project_path or (os.path.join(last_dir, "projekt.svg") if last_dir else "projekt.svg")
        fpath, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Project As"),
            default_path,
            self.tr("SVG Project File (*.svg)"),
        )
        if fpath:
            return self._save_project_to_path(fpath)
        return False

    def delete_selected_items(self):
        selected = [it for it in self.canvas.get_selected_import_items() if not it.locked]
        if not selected and hasattr(self, "object_dock"):
            selected = [it for it in self.object_dock._get_selected_doc_items() if not it.locked]
        if not selected:
            return
        cmd = DeleteItemsCommand(
            self.doc,
            selected,
            self._on_item_structure_changed,
            text=self.tr("Delete selection"),
        )
        self.undo_stack.push(cmd)

    def _on_item_structure_changed(self, select_id: Optional[str] = None):
        self.canvas.rebuild_items()
        if select_id and select_id in self.canvas._item_map:
            self.canvas._item_map[select_id].setSelected(True)
        self.object_dock.refresh()
        self.object_dock.sync_from_canvas_selection()
        self._on_selection_changed()
        if self.canvas._mode == CanvasMode.PLOT:
            self.recompile_plot_job()

    def assign_selection_to_pen(self, pen_id: int):
        selected = [it for it in self.canvas.get_selected_import_items() if not it.locked]
        if not selected:
            return
        cmd = AssignPenCommand(
            selected,
            pen_id,
            self._on_pens_changed,
            text=self.tr("Assign selection to Pen %1").replace("%1", str(pen_id)),
        )
        self.undo_stack.push(cmd)
        self.lbl_info.setText(self.tr("Object(s) assigned to Pen %1").replace("%1", str(pen_id)))

    def show_about(self):
        QMessageBox.about(
            self,
            self.tr("About Plotter Studio"),
            self.tr(
                "<b>Plotter Studio</b> v0.1.0<br>"
                "Modular Slicer & Layout Studio for Pen Plotters on Linux.<br><br>"
                "License: GPLv3"
            ),
        )

    def showEvent(self, event):
        super().showEvent(event)
        self._schedule_dock_title_update()
        if not getattr(self, "_initial_zoom_done", False):
            self._initial_zoom_done = True
            self.canvas.zoom_to_fit()
            QTimer.singleShot(50, self.canvas.zoom_to_fit)

    def _schedule_dock_title_update(self):
        QTimer.singleShot(0, self._update_dock_title_bars)

    def _update_dock_title_bars(self):
        """Hide redundant dock title bars when docks are tabbed together."""
        all_docks = getattr(self, "_all_docks", None)
        if not all_docks:
            all_docks = [
                getattr(self, "object_dock", None),
                getattr(self, "transform_dock", None),
                getattr(self, "pen_dock", None),
                getattr(self, "plot_dock", None),
            ]
            all_docks = [d for d in all_docks if d is not None]

        for dock in all_docks:
            is_tabbed = False
            if not dock.isFloating() and not dock.isHidden():
                siblings = [
                    d for d in self.tabifiedDockWidgets(dock)
                    if not d.isHidden() and not d.isFloating()
                ]
                is_tabbed = len(siblings) > 0

            if is_tabbed:
                cur_tb = dock.titleBarWidget()
                if cur_tb is None or getattr(cur_tb, "_is_dummy_title_bar", False) is False:
                    dummy = QWidget()
                    dummy._is_dummy_title_bar = True
                    dummy.setFixedHeight(0)
                    dock.setTitleBarWidget(dummy)
            else:
                cur_tb = dock.titleBarWidget()
                if cur_tb is not None and getattr(cur_tb, "_is_dummy_title_bar", False) is True:
                    dock.setTitleBarWidget(None)

    def dragEnterEvent(self, event):
        if not self.is_plot_active() and extract_droppable_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self.is_plot_active() and extract_droppable_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if self.is_plot_active():
            event.ignore()
            return
        files = extract_droppable_files(event.mimeData())
        if files:
            for fpath in files:
                self.import_svg_file(fpath)
            event.acceptProposedAction()
        else:
            event.ignore()

    def switch_to_plot_mode(self):
        """Switch view and controls into Plot/Slice mode."""
        self.act_mode_plot.setChecked(True)
        for act in getattr(self, "_layout_editing_actions", []):
            act.setEnabled(False)
        self.recompile_plot_job()
        self.canvas.set_mode(CanvasMode.PLOT)

        # Hide layout docks
        self.object_dock.hide()
        self.transform_dock.hide()
        self.pen_dock.hide()

        # Show plot dock and controls
        self.simulation_bar.show()
        self.plot_dock.show()
        self.plot_dock.raise_()
        target_w = max(self.plot_dock.minimum_content_width(), self.plot_dock.width(), 380)
        self.resizeDocks([self.plot_dock], [target_w], Qt.Horizontal)
        self._schedule_dock_title_update()
        self.lbl_info.setText(self.tr("Output active"))

    def switch_to_layout_mode(self):
        """Switch view and controls back into Layout mode."""
        if self.is_plot_active():
            self.act_mode_plot.setChecked(True)
            return
        self.act_mode_layout.setChecked(True)
        for act in getattr(self, "_layout_editing_actions", []):
            act.setEnabled(True)
        self.simulation_bar.pause()
        self.simulation_bar.hide()
        self.canvas.set_mode(CanvasMode.LAYOUT)

        # Hide plot dock
        self.plot_dock.hide()

        # Restore layout docks
        self.object_dock.show()
        self.transform_dock.show()
        self.pen_dock.show()
        self.transform_dock.raise_()
        target_w = max(self.transform_dock.minimumSizeHint().width(), self.transform_dock.width(), 380)
        self.resizeDocks([self.transform_dock], [target_w], Qt.Horizontal)
        self._schedule_dock_title_update()
        self.object_dock.refresh()
        self.transform_dock.refresh_item_fields()
        self.lbl_info.setText(self.tr("Layout active"))

    def recompile_plot_job(self):
        """Compile document paths through pipeline and update preview, scrubber and stats."""
        if self.is_plot_active():
            return
        cfg = self.plot_dock.get_pipeline_config()
        self._current_job = compile_document_to_plot_job(self.doc, cfg)
        self.canvas.set_plot_job(self._current_job)
        self.simulation_bar.set_job(self._current_job)
        self.plot_dock.set_job(self._current_job)

    def export_hpgl_dialog(self):
        """Export compiled plot job to an HP-GL / PLT file."""
        if (
            not hasattr(self, "_current_job")
            or not self._current_job
            or (hasattr(self, "plot_dock") and self.plot_dock.is_pipeline_dirty())
        ):
            self.recompile_plot_job()
        if not self._current_job or not self._current_job.layers:
            QMessageBox.information(
                self,
                self.tr("Export Not Possible"),
                self.tr("No paths available for export."),
            )
            return

        last_dir = self._get_last_dir()
        default_hpgl = os.path.join(last_dir, "job.hpgl") if last_dir else "job.hpgl"
        fpath, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Plot File"),
            default_hpgl,
            self.tr("HP-GL Plot File (*.hpgl *.plt);;All Files (*)"),
        )
        if not fpath:
            return
        self._set_last_dir(fpath)

        dev = self.device_manager.get_active_device() if hasattr(self, "device_manager") and self.device_manager else None
        margin_key: Optional[str] = None
        emitter_opts: dict[str, Any] = {}

        if hasattr(self, "plot_dock") and self.plot_dock:
            if hasattr(self.plot_dock, "combo_margins") and self.plot_dock.combo_margins.currentData():
                margin_key = self.plot_dock.combo_margins.currentData()
            if hasattr(self.plot_dock, "get_emitter_options"):
                emitter_opts.update(self.plot_dock.get_emitter_options())

        emitter = build_emitter(
            document=self.doc,
            device=dev,
            margin_profile=margin_key,
            overrides=emitter_opts,
        )
        hpgl_content = emitter.emit_string(self._current_job, self.doc)

        try:
            with open(fpath, "w", encoding="ascii") as f:
                f.write(hpgl_content)
            self.lbl_info.setText(self.tr("HP-GL exported: %1").replace("%1", os.path.basename(fpath)))
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Export Error"),
                self.tr("HP-GL export failed:\n%1").replace("%1", str(e)),
            )

    def export_plot_svg_dialog(self):
        """Export compiled polylines into a clean SVG file grouped by pen."""
        if (
            not hasattr(self, "_current_job")
            or not self._current_job
            or (hasattr(self, "plot_dock") and self.plot_dock.is_pipeline_dirty())
        ):
            self.recompile_plot_job()
        if not self._current_job or not self._current_job.layers:
            QMessageBox.information(
                self,
                self.tr("Export Not Possible"),
                self.tr("No paths available for export."),
            )
            return

        last_dir = self._get_last_dir()
        default_svg = os.path.join(last_dir, "plot_output.svg") if last_dir else "plot_output.svg"
        fpath, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export Plot Vectors"),
            default_svg,
            self.tr("SVG Vector File (*.svg);;All Files (*)"),
        )
        if not fpath:
            return
        self._set_last_dir(fpath)

        try:
            export_plot_job_to_svg(self._current_job, self.doc.page, fpath)
            self.lbl_info.setText(self.tr("Plot SVG exported: %1").replace("%1", os.path.basename(fpath)))
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Export Error"),
                self.tr("SVG export failed:\n%1").replace("%1", str(e)),
            )

    def cleanup(self):
        """Clean up canvas and docks to ensure safe, warning-free Qt teardown."""
        if hasattr(self, "simulation_bar") and self.simulation_bar:
            self.simulation_bar.pause()
        if hasattr(self, "plot_dock") and self.plot_dock:
            if getattr(self.plot_dock, "_streamer", None) and self.plot_dock._streamer.is_active():
                try:
                    self.plot_dock._streamer.abort(wait=True, timeout=1.0)
                except TypeError:
                    self.plot_dock._streamer.abort()
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.cleanup()

    def closeEvent(self, event):
        if not self._confirm_abort_active_plot():
            event.ignore()
            return
        if not self._confirm_discard_unsaved_changes():
            event.ignore()
            return
        self._save_window_settings()
        self.cleanup()
        super().closeEvent(event)
