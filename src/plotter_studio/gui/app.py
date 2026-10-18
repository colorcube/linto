"""Application entrypoint for launching Plotter Studio GUI."""

from __future__ import annotations
import sys
from PySide6.QtWidgets import QApplication
from .i18n import setup_i18n
from .main_window import MainWindow


def run_gui():
    """Launch the Plotter Studio Qt application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Plotter Studio")
    app.setOrganizationName("PlotterStudio")

    # Initialize internationalization (detects system locale, defaults/falls back to English)
    translators = setup_i18n(app)
    app._translators = translators

    window = MainWindow()
    app.aboutToQuit.connect(window.cleanup)
    window.show()

    ret = app.exec()
    window.cleanup()
    return ret
