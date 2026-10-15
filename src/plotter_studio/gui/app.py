"""Application entrypoint for launching Plotter Studio GUI."""

from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from .main_window import MainWindow


def run_gui():
    """Launch the Plotter Studio Qt application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Plotter Studio")
    app.setOrganizationName("PlotterStudio")

    window = MainWindow()
    app.aboutToQuit.connect(window.cleanup)
    window.show()

    ret = app.exec()
    window.cleanup()
    return ret
