"""Main Application Window for Plotter Studio."""

from __future__ import annotations
import os
import copy
import math
from typing import Optional
from PySide6.QtCore import Qt, QPointF, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon, QUndoStack, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QGridLayout, QToolBar,
    QStatusBar, QLabel, QFileDialog, QMessageBox, QTabWidget,
    QSizePolicy, QComboBox, QToolButton
)
from ..core.document import Document, ImportItem
from ..core.geometry import AffineTransform
from ..core.svg_import import load_svg
from ..core.svg_export import export_document_to_svg, load_document_from_svg, is_project_file
from ..pipeline.compiler import (
    PipelineConfig, PlotJob, compile_document_to_plot_job
)
from .canvas import PlotterCanvas, CanvasMode
from .rulers import RulerWidget, RULER_BREADTH
from .pen_dock import PenDockWidget
from .paper_dock import PaperDockWidget
from .transform_dock import TransformDockWidget
from .layout_dock import LayoutDockWidget
from .plot_dock import PlotDockWidget
from .object_dock import ObjectDockWidget
from .simulation_bar import PlotSimulationBar
from .icons import get_icon
from ..device import get_default_profile, HPGLEmitter, DeviceManager, ConfiguredDevice
from .device_dialog import DeviceSettingsDialog
from .page_dialog import PageSetupDialog
from .commands import (
    TransformItemCommand, AssignPenCommand,
    AddItemCommand, DeleteItemsCommand
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

        self.setWindowTitle("Plotter Studio")
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
        self.addDockWidget(Qt.RightDockWidgetArea, self.object_dock)

        # Panel 2: Skalieren & Platzieren (Bottom Right)
        self.transform_dock = TransformDockWidget(self.doc, self)
        self.transform_dock.set_undo_stack(self.undo_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.transform_dock)
        self.layout_dock = self.transform_dock  # compatibility alias

        # Split vertical: Object Dock on top, Transform Dock below
        self.splitDockWidget(self.object_dock, self.transform_dock, Qt.Vertical)

        # Panel 3: Stifte (Tabified with Transform Dock)
        self.pen_dock = PenDockWidget(self.doc, self)
        self.pen_dock.set_undo_stack(self.undo_stack)
        self.addDockWidget(Qt.RightDockWidgetArea, self.pen_dock)
        self.tabifyDockWidget(self.transform_dock, self.pen_dock)

        # Paper settings dock kept for compatibility if needed, but hidden by default
        self.paper_dock = PaperDockWidget(self.doc, self)
        self.paper_dock.set_undo_stack(self.undo_stack)
        self.paper_dock.set_device_manager(self.device_manager)
        self.addDockWidget(Qt.RightDockWidgetArea, self.paper_dock)
        self.tabifyDockWidget(self.pen_dock, self.paper_dock)
        self.paper_dock.hide()

        self.transform_dock.raise_()

        # Panel 4: Plot-Vorschau & Ausgabe
        self.plot_dock = PlotDockWidget(self.doc, self)
        self.plot_dock.set_device_manager(self.device_manager)
        self.addDockWidget(Qt.RightDockWidgetArea, self.plot_dock)

        # In initial Layout mode, Plot dock is hidden
        self.plot_dock.hide()

    def _setup_actions_and_menus(self):
        menu_bar = self.menuBar()

        # --- File Menu ---
        menu_file = menu_bar.addMenu("&Datei")

        self.act_new = QAction("&Neu", self)
        self.act_new.setIcon(get_icon("plus"))
        self.act_new.setShortcut(QKeySequence.New)
        self.act_new.triggered.connect(self.new_document)
        menu_file.addAction(self.act_new)

        self.act_open_project = QAction("Projekt &öffnen...", self)
        self.act_open_project.setIcon(get_icon("open"))
        self.act_open_project.setShortcut(QKeySequence.Open)
        self.act_open_project.setToolTip("Projekt oder SVG-Datei öffnen (Strg+O)")
        self.act_open_project.triggered.connect(self.open_project_dialog)
        menu_file.addAction(self.act_open_project)

        self.act_save_as = QAction("Projekt &speichern unter...", self)
        self.act_save_as.setIcon(get_icon("save"))
        self.act_save_as.setShortcut(QKeySequence.SaveAs)
        self.act_save_as.setToolTip("Projekt als SVG speichern (Strg+Umschalt+S)")
        self.act_save_as.triggered.connect(self.save_project_dialog)
        menu_file.addAction(self.act_save_as)

        menu_file.addSeparator()

        self.act_import_svg = QAction("&Importieren...", self)
        self.act_import_svg.setIcon(get_icon("import"))
        self.act_import_svg.setShortcut(QKeySequence("Ctrl+I"))
        self.act_import_svg.setToolTip("SVG- oder Plotdatei importieren (Strg+I)")
        self.act_import_svg.triggered.connect(self.import_svg_dialog)
        menu_file.addAction(self.act_import_svg)

        menu_file.addSeparator()

        self.act_page_setup = QAction("&Seiteneinrichtung...", self)
        self.act_page_setup.setIcon(get_icon("page"))
        self.act_page_setup.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self.act_page_setup.setToolTip("Seiteneinrichtung & Papierformat bearbeiten (Strg+Umschalt+P)")
        self.act_page_setup.triggered.connect(self.open_page_setup_dialog)
        menu_file.addAction(self.act_page_setup)

        menu_file.addSeparator()

        self.act_exit = QAction("&Beenden", self)
        self.act_exit.setShortcut(QKeySequence.Quit)
        self.act_exit.triggered.connect(self.close)
        menu_file.addAction(self.act_exit)

        # --- Edit Menu ---
        menu_edit = menu_bar.addMenu("&Bearbeiten")

        self.act_undo = self.undo_stack.createUndoAction(self, "&Rückgängig")
        self.act_undo.setIcon(get_icon("undo"))
        self.act_undo.setShortcut(QKeySequence.Undo)
        menu_edit.addAction(self.act_undo)

        self.act_redo = self.undo_stack.createRedoAction(self, "&Wiederholen")
        self.act_redo.setIcon(get_icon("redo"))
        self.act_redo.setShortcut(QKeySequence.Redo)
        menu_edit.addAction(self.act_redo)

        menu_edit.addSeparator()

        self.act_duplicate = QAction("&Duplizieren", self)
        self.act_duplicate.setIcon(get_icon("duplicate"))
        self.act_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.act_duplicate.setToolTip("Ausgewähltes Objekt duplizieren (Strg+D)")
        self.act_duplicate.triggered.connect(self.duplicate_selected_items)
        menu_edit.addAction(self.act_duplicate)

        self.act_delete = QAction("&Löschen", self)
        self.act_delete.setIcon(get_icon("delete"))
        self.act_delete.setShortcut(QKeySequence.Delete)
        self.act_delete.setToolTip("Ausgewählte Objekte löschen (Entf)")
        self.act_delete.triggered.connect(self.delete_selected_items)
        menu_edit.addAction(self.act_delete)

        menu_edit.addSeparator()

        self.act_rotate_ccw = QAction("90° gegen Uhrzeigersinn (-90°)", self)
        self.act_rotate_ccw.setIcon(get_icon("rotate-ccw"))
        self.act_rotate_ccw.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.act_rotate_ccw.setToolTip("Auswahl 90° gegen den Uhrzeigersinn drehen (Strg+Umschalt+R)")
        self.act_rotate_ccw.triggered.connect(lambda: self.rotate_selected_items(-90.0))
        menu_edit.addAction(self.act_rotate_ccw)

        self.act_rotate_cw = QAction("90° im Uhrzeigersinn (+90°)", self)
        self.act_rotate_cw.setIcon(get_icon("rotate-cw"))
        self.act_rotate_cw.setShortcut(QKeySequence("Ctrl+R"))
        self.act_rotate_cw.setToolTip("Auswahl 90° im Uhrzeigersinn drehen (Strg+R)")
        self.act_rotate_cw.triggered.connect(lambda: self.rotate_selected_items(90.0))
        menu_edit.addAction(self.act_rotate_cw)

        menu_edit.addSeparator()

        # Assign pen 1..8 shortcuts
        for pen_id in range(1, 9):
            act = QAction(f"Auswahl Stift {pen_id} zuweisen", self)
            act.setShortcut(QKeySequence(str(pen_id)))
            act.triggered.connect(lambda checked=False, pid=pen_id: self.assign_selection_to_pen(pid))
            menu_edit.addAction(act)

        # --- View Menu ---
        menu_view = menu_bar.addMenu("&Ansicht")

        # Mode switching group
        self.mode_group = QActionGroup(self)
        self.mode_group.setExclusive(True)

        self.act_mode_layout = QAction("Layout", self)
        self.act_mode_layout.setIcon(get_icon("mode-layout"))
        self.act_mode_layout.setCheckable(True)
        self.act_mode_layout.setChecked(True)
        self.act_mode_layout.setShortcut(QKeySequence("Ctrl+L"))
        self.act_mode_layout.triggered.connect(self.switch_to_layout_mode)
        self.mode_group.addAction(self.act_mode_layout)
        menu_view.addAction(self.act_mode_layout)

        self.act_mode_plot = QAction("Ausgabe", self)
        self.act_mode_plot.setIcon(get_icon("mode-plot"))
        self.act_mode_plot.setCheckable(True)
        self.act_mode_plot.setShortcut(QKeySequence("Ctrl+P"))
        self.act_mode_plot.triggered.connect(self.switch_to_plot_mode)
        self.mode_group.addAction(self.act_mode_plot)
        menu_view.addAction(self.act_mode_plot)

        menu_view.addSeparator()

        self.act_zoom_fit = QAction("Blatt im Fenster einpassen", self)
        self.act_zoom_fit.setIcon(get_icon("zoom-fit"))
        self.act_zoom_fit.setShortcut(QKeySequence("Ctrl+0"))
        self.act_zoom_fit.setToolTip("Blatt im Fenster einpassen (Strg+0)")
        self.act_zoom_fit.triggered.connect(self.canvas.zoom_to_fit)
        menu_view.addAction(self.act_zoom_fit)

        self.act_zoom_in = QAction("Vergrößern", self)
        self.act_zoom_in.setIcon(get_icon("zoom-in"))
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.setToolTip("Vergrößern (Strg++)")
        self.act_zoom_in.triggered.connect(lambda checked=False: self.canvas.zoom_in())
        menu_view.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("Verkleinern", self)
        self.act_zoom_out.setIcon(get_icon("zoom-out"))
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.setToolTip("Verkleinern (Strg+-)")
        self.act_zoom_out.triggered.connect(lambda checked=False: self.canvas.zoom_out())
        menu_view.addAction(self.act_zoom_out)

        # Docks toggle & Display options
        menu_view.addSeparator()
        self.act_show_nodes = QAction("Stützpunkte (Koordinaten) anzeigen", self)
        self.act_show_nodes.setCheckable(True)
        self.act_show_nodes.setChecked(False)
        self.act_show_nodes.toggled.connect(self.plot_dock.chk_show_nodes.setChecked)
        menu_view.addAction(self.act_show_nodes)

        menu_view.addSeparator()
        menu_view.addAction(self.object_dock.toggleViewAction())
        menu_view.addAction(self.transform_dock.toggleViewAction())
        menu_view.addAction(self.paper_dock.toggleViewAction())
        menu_view.addAction(self.pen_dock.toggleViewAction())
        menu_view.addAction(self.plot_dock.toggleViewAction())

        # --- Help Menu ---
        menu_help = menu_bar.addMenu("&Hilfe")
        act_about = QAction("Über &Plotter Studio", self)
        act_about.triggered.connect(self.show_about)
        menu_help.addAction(act_about)

    def _setup_toolbar(self):
        toolbar = QToolBar("Haupt-Werkzeugleiste", self)
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
        toolbar.addAction(self.act_save_as)
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

        btn_center = toolbar.addAction("Mittig ausrichten")
        btn_center.setIcon(get_icon("align-center"))
        btn_center.setToolTip("Mittig auf Blatt/Plottbereich ausrichten")
        btn_center.triggered.connect(self.transform_dock.align_center_both)

        btn_fit = toolbar.addAction("Auf Blatt einpassen")
        btn_fit.setIcon(get_icon("fit-page"))
        btn_fit.setToolTip("Auf Blatt einpassen")
        btn_fit.triggered.connect(self.transform_dock.fit_to_page)

        btn_orig = toolbar.addAction("1:1 Originalgröße")
        btn_orig.setIcon(get_icon("original-size"))
        btn_orig.setToolTip("1:1 Originalgröße (aus Quelldatei)")
        btn_orig.triggered.connect(self.transform_dock.reset_to_original_size)

        # Spacer to push paper setup & device settings to the right
        spacer = QWidget(toolbar)
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Paper Setup Button in toolbar showing current format
        self.btn_page_setup = QToolButton(toolbar)
        self.btn_page_setup.setIcon(get_icon("page", size=18))
        self.btn_page_setup.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_page_setup.setToolTip("Papierformat & Seiteneinrichtung bearbeiten...")
        self.btn_page_setup.clicked.connect(self.open_page_setup_dialog)
        toolbar.addWidget(self.btn_page_setup)

        toolbar.addSeparator()

        lbl_device = QLabel(" Gerät: ", toolbar)
        lbl_device.setStyleSheet("color: #4b5563;")
        toolbar.addWidget(lbl_device)

        self.combo_active_device = QComboBox(toolbar)
        self.combo_active_device.setMinimumWidth(220)
        self.combo_active_device.setToolTip("Aktives Plotter-Gerät für Abfragen und Plottausgabe")
        self.combo_active_device.currentIndexChanged.connect(self._on_active_device_changed)
        toolbar.addWidget(self.combo_active_device)

        self.btn_device_settings = QToolButton(toolbar)
        self.btn_device_settings.setIcon(get_icon("settings", size=18))
        self.btn_device_settings.setToolTip("Geräte verwalten und konfigurieren...")
        self.btn_device_settings.clicked.connect(self.open_device_settings_dialog)
        toolbar.addWidget(self.btn_device_settings)

        self._refresh_device_selector()
        self._update_paper_display()

    def _setup_status_bar(self):
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.lbl_coord = QLabel("X: 0.0 mm | Y: 0.0 mm")
        self.lbl_zoom = QLabel("Zoom: 100 %")
        self.lbl_info = QLabel("Bereit")
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
        self.canvas.item_drag_finished.connect(self._on_item_drag_finished)

        # Pen dock
        self.pen_dock.pen_changed.connect(self._on_pens_changed)
        self.pen_dock.assign_selection_to_pen.connect(self.assign_selection_to_pen)

        # Paper dock
        self.paper_dock.page_changed.connect(self._on_page_changed)

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

        # Object dock
        self.object_dock.btn_import.clicked.connect(self.import_svg_dialog)
        self.object_dock.document_modified.connect(self._on_document_modified)
        self.canvas.selection_changed_signal.connect(self.object_dock.sync_from_canvas_selection)

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

    def _on_active_device_changed(self):
        dev_id = self.combo_active_device.currentData()
        if not dev_id:
            return
        self.device_manager.set_active_device(dev_id)
        dev = self.device_manager.get_active_device()
        if dev:
            self.paper_dock.apply_configured_device(dev)
            self.plot_dock.apply_configured_device(dev)

    def open_device_settings_dialog(self):
        dlg = DeviceSettingsDialog(self.device_manager, parent=self)
        if dlg.exec():
            self._refresh_device_selector()
            dev = self.device_manager.get_active_device()
            if dev:
                self.paper_dock.apply_configured_device(dev)
                self.plot_dock.apply_configured_device(dev)

    def open_page_setup_dialog(self):
        dlg = PageSetupDialog(self.doc, self.device_manager, self.undo_stack, parent=self)
        dlg.page_changed.connect(self._on_page_changed)
        if dlg.exec():
            self._on_page_changed()

    def _update_paper_display(self):
        p = self.doc.page
        if p.preset != "Custom":
            fmt_str = f"DIN {p.preset}" if p.preset.startswith("A") else p.preset
            orient_str = "Quer" if p.orientation == "landscape" else "Hoch"
            summary = f"{fmt_str} {orient_str} ({p.width_mm:.0f} × {p.height_mm:.0f} mm)"
        else:
            summary = f"Custom ({p.width_mm:.0f} × {p.height_mm:.0f} mm)"
        if hasattr(self, "btn_page_setup"):
            self.btn_page_setup.setText(summary)
            self.btn_page_setup.setToolTip(f"Seiteneinrichtung: {summary} (Klicken zum Bearbeiten)")
        if hasattr(self, "lbl_paper_status"):
            self.lbl_paper_status.setText(f"Blatt: {summary}")

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
        scale_diff = abs(math.hypot(old_t.a, old_t.b) - math.hypot(new_t.a, new_t.b))
        action_name = "skalieren" if scale_diff > 1e-4 else "verschieben"
        cmd = TransformItemCommand(
            item, old_t, new_t, self._on_item_transformed, text=f"{item.name} {action_name}"
        )
        self.undo_stack.push(cmd)

    def rotate_selected_items(self, angle_degrees: float):
        """Rotate all currently selected items by angle_degrees."""
        selected = self.canvas.get_selected_import_items()
        if not selected:
            return
        if len(selected) == 1:
            self.transform_dock.rotate_selected(angle_degrees)
        else:
            dir_str = "im Uhrzeigersinn" if angle_degrees > 0 else "gegen den Uhrzeigersinn"
            self.undo_stack.beginMacro(f"Objekte drehen ({int(abs(angle_degrees))}° {dir_str})")
            try:
                for it in selected:
                    cb = it.current_bounds
                    if cb:
                        cx, cy = cb.center.x, cb.center.y
                        old_t = copy.deepcopy(it.transform)
                        rot_t = AffineTransform.rotation(angle_degrees, cx, cy)
                        new_t = rot_t.multiply(old_t)
                        cmd = TransformItemCommand(
                            it, old_t, new_t, self._on_item_transformed, text=f"{it.name} drehen"
                        )
                        self.undo_stack.push(cmd)
            finally:
                self.undo_stack.endMacro()

    def _on_selection_changed(self):
        selected = self.canvas.get_selected_import_items()
        if selected:
            item = selected[0]
            self.transform_dock.set_active_item(item)
            b = item.current_bounds
            if b:
                pb = self.doc.page.plottable_box
                is_oob = not pb.contains_box(b)
                scale_pct = math.hypot(item.transform.a, item.transform.b) * 100.0
                warn_text = " — ⚠️ Außerhalb des Plottbereichs!" if is_oob else ""
                self.lbl_info.setText(
                    f"Ausgewählt: {item.name} ({b.width:.1f} x {b.height:.1f} mm, Skalierung: {scale_pct:.0f}%){warn_text}"
                )
        else:
            self.transform_dock.set_active_item(None)
            self.lbl_info.setText(f"{len(self.doc.items)} Objekt(e) auf dem Blatt")

    def new_document(self):
        self.doc.items.clear()
        self.undo_stack.clear()
        self.canvas.rebuild_items()
        self.object_dock.refresh()
        self.pen_dock.refresh_table()
        self.paper_dock.refresh_page_fields()
        self.transform_dock.set_active_item(None)
        self._update_paper_display()
        self.lbl_info.setText("Neues Dokument erstellt")

    def open_project_dialog(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "Projekt oder SVG öffnen", "", "SVG-Dateien (*.svg);;Alle Dateien (*)"
        )
        if fpath:
            self.load_project_file(fpath)

    def load_project_file(self, fpath: str):
        try:
            is_proj = is_project_file(fpath)
            loaded_doc = load_document_from_svg(fpath)
            self.doc.page = loaded_doc.page
            self.doc.pens = loaded_doc.pens
            self.doc.items = loaded_doc.items
            self.undo_stack.clear()
            self._update_paper_display()
            self.transform_dock.refresh_item_fields()
            self.canvas.update_scene_rect()
            self.canvas.rebuild_items()
            self.canvas.zoom_to_fit()
            self.object_dock.refresh()
            self.pen_dock.refresh_table()
            self.paper_dock.refresh_page_fields()
            self.transform_dock.set_active_item(None)
            self._on_selection_changed()
            if self.canvas._mode == CanvasMode.PLOT:
                self.recompile_plot_job()

            if is_proj:
                self.lbl_info.setText(f"Projekt geladen: {os.path.basename(fpath)} ({len(self.doc.items)} Objekt(e))")
            else:
                num_paths = sum(len(it.paths) for it in self.doc.items)
                self.lbl_info.setText(f"SVG geladen: {os.path.basename(fpath)} ({num_paths} Pfade)")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Öffnen der Datei", f"Konnte Datei nicht laden:\n{e}")

    def import_svg_dialog(self):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "SVG-Grafik importieren", "", "SVG Dateien (*.svg);;Alle Dateien (*)"
        )
        if fpath:
            self.import_svg_file(fpath)

    def import_svg_file(self, fpath: str):
        try:
            if is_project_file(fpath):
                resp = QMessageBox.question(
                    self,
                    "Projektdatei erkannt",
                    f"Die Datei »{os.path.basename(fpath)}« ist ein vollständiges Plotter-Studio-Projekt.\n\n"
                    "Möchten Sie das Projekt vollständig öffnen (Ja) oder als einzelnes Objekt in das aktuelle Blatt importieren (Nein)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes,
                )
                if resp == QMessageBox.StandardButton.Cancel:
                    return
                if resp == QMessageBox.StandardButton.Yes:
                    self.load_project_file(fpath)
                    return

            pen_palette = [(p.pen_id, p.color_hex) for p in self.doc.pens]
            item = load_svg(fpath, pen_palette=pen_palette)

            # Center item on page upon import
            pb = self.doc.page.plottable_box
            if item.original_bounds:
                ob = item.original_bounds
                tx = pb.min_x + (pb.width - ob.width) / 2.0 - ob.min_x
                ty = pb.min_y + (pb.height - ob.height) / 2.0 - ob.min_y
                item.transform.tx = tx
                item.transform.ty = ty

            cmd = AddItemCommand(
                self.doc, item, self._on_item_structure_changed, text=f"Import {os.path.basename(fpath)}"
            )
            self.undo_stack.push(cmd)
            self.lbl_info.setText(f"Importiert: {os.path.basename(fpath)}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Import", f"Konnte Datei nicht importieren:\n{e}")

    def save_project_dialog(self):
        fpath, _ = QFileDialog.getSaveFileName(
            self, "Projekt speichern unter", "projekt.svg", "SVG Projektdatei (*.svg)"
        )
        if fpath:
            try:
                export_document_to_svg(self.doc, fpath)
                self.lbl_info.setText(f"Gespeichert unter: {os.path.basename(fpath)}")
            except Exception as e:
                QMessageBox.critical(self, "Fehler beim Speichern", f"Fehler beim Speichern:\n{e}")

    def delete_selected_items(self):
        selected = self.canvas.get_selected_import_items()
        if not selected:
            return
        cmd = DeleteItemsCommand(
            self.doc, selected, self._on_item_structure_changed, text="Auswahl löschen"
        )
        self.undo_stack.push(cmd)

    def _on_item_structure_changed(self):
        self.canvas.rebuild_items()
        self.object_dock.refresh()
        if self.doc.items and self.doc.items[-1].item_id in self.canvas._item_map:
            self.canvas._item_map[self.doc.items[-1].item_id].setSelected(True)
        self._on_selection_changed()

    def assign_selection_to_pen(self, pen_id: int):
        selected = self.canvas.get_selected_import_items()
        if not selected:
            return
        cmd = AssignPenCommand(
            selected, pen_id, self._on_pens_changed, text=f"Auswahl Stift {pen_id} zuweisen"
        )
        self.undo_stack.push(cmd)
        self.lbl_info.setText(f"Objekt(e) Stift {pen_id} zugewiesen")

    def show_about(self):
        QMessageBox.about(
            self,
            "Über Plotter Studio",
            "<b>Plotter Studio</b> v0.1.0<br>"
            "Modularer Slicer & Layout-Studio für Stiftplotter unter Linux.<br><br>"
            "Lizenz: GPLv3"
        )

    def showEvent(self, event):
        super().showEvent(event)
        if not getattr(self, "_initial_zoom_done", False):
            self._initial_zoom_done = True
            from PySide6.QtCore import QTimer
            self.canvas.zoom_to_fit()
            QTimer.singleShot(50, self.canvas.zoom_to_fit)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".svg", ".hpgl", ".plt")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith((".svg", ".hpgl", ".plt")):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                fpath = url.toLocalFile()
                if fpath.lower().endswith((".svg", ".hpgl", ".plt")):
                    self.import_svg_file(fpath)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def switch_to_plot_mode(self):
        """Switch view and controls into Plot/Slice mode."""
        self.act_mode_plot.setChecked(True)
        self.recompile_plot_job()
        self.canvas.set_mode(CanvasMode.PLOT)

        # Hide layout docks
        self.object_dock.hide()
        self.paper_dock.hide()
        self.transform_dock.hide()
        self.pen_dock.hide()

        # Show plot dock and controls
        self.simulation_bar.show()
        self.plot_dock.show()
        self.plot_dock.raise_()
        self.lbl_info.setText("Ausgabe aktiv")

    def switch_to_layout_mode(self):
        """Switch view and controls back into Layout mode."""
        self.act_mode_layout.setChecked(True)
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
        self.object_dock.refresh()
        self.transform_dock.refresh_item_fields()
        self.lbl_info.setText("Layout aktiv")

    def recompile_plot_job(self):
        """Compile document paths through pipeline and update preview, scrubber and stats."""
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
            QMessageBox.information(self, "Export nicht möglich", "Keine Pfade zum Exportieren vorhanden.")
            return

        fpath, _ = QFileDialog.getSaveFileName(
            self, "Plotdatei exportieren", "job.hpgl", "HP-GL Plotdatei (*.hpgl *.plt);;Alle Dateien (*)"
        )
        if not fpath:
            return

        margin_key = "exp"
        emitter_opts = {}
        if hasattr(self, "plot_dock"):
            if hasattr(self.plot_dock, "combo_margins"):
                margin_key = self.plot_dock.combo_margins.currentData() or "exp"
            if hasattr(self.plot_dock, "get_emitter_options"):
                emitter_opts = self.plot_dock.get_emitter_options()
        profile = get_default_profile()
        emitter = HPGLEmitter(profile, margin_profile=margin_key, **emitter_opts)
        hpgl_content = emitter.emit_string(self._current_job, self.doc)

        try:
            with open(fpath, "w", encoding="ascii") as f:
                f.write(hpgl_content)
            self.lbl_info.setText(f"HP-GL exportiert: {os.path.basename(fpath)}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Export", f"HP-GL-Export fehlgeschlagen:\n{e}")

    def export_plot_svg_dialog(self):
        """Export compiled polylines into a clean SVG file grouped by pen."""
        if (
            not hasattr(self, "_current_job")
            or not self._current_job
            or (hasattr(self, "plot_dock") and self.plot_dock.is_pipeline_dirty())
        ):
            self.recompile_plot_job()
        if not self._current_job or not self._current_job.layers:
            QMessageBox.information(self, "Export nicht möglich", "Keine Pfade zum Exportieren vorhanden.")
            return

        fpath, _ = QFileDialog.getSaveFileName(
            self, "Plot-Vektoren exportieren", "plot_output.svg", "SVG Vektordatei (*.svg);;Alle Dateien (*)"
        )
        if not fpath:
            return

        import xml.etree.ElementTree as ET
        w_mm = self.doc.page.width_mm
        h_mm = self.doc.page.height_mm
        root = ET.Element("svg", {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{w_mm:.2f}mm",
            "height": f"{h_mm:.2f}mm",
            "viewBox": f"0 0 {w_mm:.2f} {h_mm:.2f}",
            "version": "1.1",
        })

        for pen_id, layer in sorted(self._current_job.layers.items()):
            g_layer = ET.SubElement(root, "g", {
                "id": f"pen_{pen_id}_{layer.pen.name.replace(' ', '_')}",
                "stroke": layer.pen.color_hex,
                "stroke-width": f"{layer.pen.width_mm:.2f}",
                "fill": "none",
                "stroke-linecap": "round",
                "stroke-linejoin": "round",
            })
            for poly in layer.lines:
                if len(poly) < 2:
                    continue
                d_parts = [f"M {poly[0, 0]:.3f},{poly[0, 1]:.3f}"]
                for pt in poly[1:]:
                    d_parts.append(f"L {pt[0]:.3f},{pt[1]:.3f}")
                ET.SubElement(g_layer, "path", {"d": " ".join(d_parts)})

        try:
            tree = ET.ElementTree(root)
            ET.indent(tree, space="  ")
            tree.write(fpath, encoding="utf-8", xml_declaration=True)
            self.lbl_info.setText(f"Plot-SVG exportiert: {os.path.basename(fpath)}")
        except Exception as e:
            QMessageBox.critical(self, "Fehler beim Export", f"SVG-Export fehlgeschlagen:\n{e}")

    def cleanup(self):
        """Clean up canvas and docks to ensure safe, warning-free Qt teardown."""
        if hasattr(self, "simulation_bar") and self.simulation_bar:
            self.simulation_bar.pause()
        if hasattr(self, "plot_dock") and self.plot_dock:
            if getattr(self.plot_dock, "_streamer", None) and self.plot_dock._streamer.is_active():
                self.plot_dock._streamer.abort()
        if hasattr(self, "canvas") and self.canvas:
            self.canvas.cleanup()

    def closeEvent(self, event):
        self.cleanup()
        super().closeEvent(event)
