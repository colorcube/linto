"""Shared pytest fixtures."""

import os
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        from plotter_studio.gui.i18n import setup_i18n
        setup_i18n(app, language_override="de")
    return app
