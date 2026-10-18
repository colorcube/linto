"""Shared pytest fixtures."""

import os
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QMessageBox


@pytest.fixture(scope="session")
def qapp(tmp_path_factory):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    settings_dir = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_dir))
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
        from plotter_studio.gui.i18n import setup_i18n
        setup_i18n(app, language_override="de")
    return app


@pytest.fixture(autouse=True)
def _isolate_qt_dialogs_and_settings(monkeypatch):
    """Prevent modal QMessageBox.question hangs during tests."""
    def _default_question(_parent, _title, _text, buttons=QMessageBox.StandardButton.Yes, default_btn=QMessageBox.StandardButton.NoButton):
        if buttons & QMessageBox.StandardButton.Discard:
            return QMessageBox.StandardButton.Discard
        return QMessageBox.StandardButton.Yes

    def _default_ok(*_args, **_kwargs):
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "question", _default_question)
    monkeypatch.setattr(QMessageBox, "critical", _default_ok)
    monkeypatch.setattr(QMessageBox, "warning", _default_ok)
    monkeypatch.setattr(QMessageBox, "information", _default_ok)
    monkeypatch.setattr(QMessageBox, "about", lambda *_a, **_kw: None)

