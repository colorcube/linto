"""Application entrypoint for launching LINTO GUI."""

from __future__ import annotations
import sys
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .. import RESOURCES_DIR
from .i18n import setup_i18n
from .main_window import MainWindow


def run_gui(qt_args: list[str] | None = None, open_file: str | None = None):
    """Launch the LINTO Qt application, optionally opening a file on startup."""
    app = QApplication(qt_args if qt_args is not None else sys.argv)
    app.setApplicationName("LINTO")
    app.setOrganizationName("linto")
    # Matches linto.desktop, so Wayland compositors and task bars show the right icon.
    app.setDesktopFileName("de.colorcube.linto")
    app.setWindowIcon(QIcon(str(RESOURCES_DIR / "icons" / "linto.svg")))

    # Initialize internationalization (detects system locale, defaults/falls back to English)
    translators = setup_i18n(app)
    app._translators = translators

    window = MainWindow()
    app.aboutToQuit.connect(window.cleanup)
    window.show()
    if open_file:
        window.load_project_file(open_file)

    ret = app.exec()
    window.cleanup()
    return ret
