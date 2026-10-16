"""Tests for i18n localization and fallback mechanism."""

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication, QLabel

from plotter_studio.gui.i18n import PlotterTranslator, setup_i18n


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_translator_fallback_to_source_text(qapp):
    """When a string is missing in translation dict, it falls back to source text."""
    translator = PlotterTranslator(qapp)
    translator.load_dict({"&File": "&Datei"}, lang="de")
    qapp.installTranslator(translator)

    lbl = QLabel()
    # Found in dict
    assert lbl.tr("&File") == "&Datei"
    # Not found in dict -> falls back to original English string
    assert lbl.tr("&Edit") == "&Edit"
    assert lbl.tr("Nonexistent String") == "Nonexistent String"

    qapp.removeTranslator(translator)


def test_translator_context_override(qapp):
    """Context-specific translation overrides global translation."""
    translator = PlotterTranslator(qapp)
    translator.load_dict({
        "Close": "Schließen",
        "MainWindow": {
            "Close": "Beenden",
        }
    }, lang="de")
    qapp.installTranslator(translator)

    # In MainWindow context
    assert QCoreApplication.translate("MainWindow", "Close") == "Beenden"
    # In another context -> falls back to global "Schließen"
    assert QCoreApplication.translate("OtherContext", "Close") == "Schließen"

    qapp.removeTranslator(translator)


def test_setup_i18n_english_fallback(qapp):
    """Setting up i18n with 'en' installs no translation and uses source text."""
    app_trans, qt_trans = setup_i18n(qapp, language_override="en")
    assert app_trans.active_language == "en"

    lbl = QLabel()
    assert lbl.tr("Open Project...") == "Open Project..."


def test_setup_i18n_german_translation(qapp):
    """Setting up i18n with 'de' loads de.json and translates registered strings."""
    app_trans, qt_trans = setup_i18n(qapp, language_override="de")
    assert app_trans.active_language == "de"

    lbl = QLabel()
    assert lbl.tr("&File") == "&Datei"
    assert lbl.tr("&New Project") == "&Neues Projekt"
    assert lbl.tr("&Open Project...") == "Projekt &öffnen..."
    assert lbl.tr("Center on Sheet") == "Mittig ausrichten"

