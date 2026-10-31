"""Tests for i18n localization and fallback mechanism."""

import ast
import glob
import json
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QLabel

from linto.gui.i18n import PlotterTranslator, setup_i18n, get_translations_dir


def test_translator_fallback_to_source_text(qapp):
    """When a string is missing in translation dict, it falls back to source text."""
    setup_i18n(qapp, language_override="en")
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
    setup_i18n(qapp, language_override="de")


def test_translator_context_override(qapp):
    """Context-specific translation overrides global translation."""
    setup_i18n(qapp, language_override="en")
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
    setup_i18n(qapp, language_override="de")


def test_setup_i18n_english_fallback(qapp):
    """Setting up i18n with 'en' installs no translation and uses source text."""
    app_trans, qt_trans = setup_i18n(qapp, language_override="en")
    assert app_trans.active_language == "en"

    lbl = QLabel()
    assert lbl.tr("Open Project...") == "Open Project..."
    setup_i18n(qapp, language_override="de")


def test_setup_i18n_german_translation(qapp):
    """Setting up i18n with 'de' loads de.json and translates registered strings."""
    app_trans, qt_trans = setup_i18n(qapp, language_override="de")
    assert app_trans.active_language == "de"

    lbl = QLabel()
    assert lbl.tr("&File") == "&Datei"
    assert lbl.tr("&New Project") == "&Neues Projekt"
    assert lbl.tr("&Open Project...") == "Projekt &öffnen..."
    assert lbl.tr("Center on Sheet") == "Mittig ausrichten"

    # Docks & Dialogs translations
    assert lbl.tr("Objects & Layers") == "Objekte & Ebenen"
    assert lbl.tr("Position & Dimensions") == "Position & Maße"
    assert lbl.tr("Printable Area") == "Plottbarer Bereich"
    assert lbl.tr("No object selected") == "Kein Objekt ausgewählt"
    assert lbl.tr("Pens") == "Stifte"
    assert lbl.tr("Pipeline Optimization") == "Pipeline-Optimierung"
    assert lbl.tr("Pre-Flight Inspection") == "Pre-Flight-Inspektion"
    assert lbl.tr("Plotter Control") == "Plotter-Steuerung"
    assert lbl.tr("File Export") == "Datei-Export"
    assert lbl.tr("Page Setup & Paper Format") == "Seiteneinrichtung & Papierformat"
    assert lbl.tr("Configure Plotter Devices") == "Plotter-Geräte konfigurieren"
    assert lbl.tr("Apply Pen Preset") == "Stift-Preset anwenden"

    # Toolbar icon hover tooltips
    assert lbl.tr("Layout Mode (Ctrl+L)") == "Layout-Modus (Strg+L)"
    assert lbl.tr("Output / Plot Mode (Ctrl+P)") == "Ausgabe- / Plot-Modus (Strg+P)"
    assert lbl.tr("Open project or vector file (Ctrl+O)") == "Projekt oder Vektordatei öffnen (Strg+O)"
    assert lbl.tr("Save project (Ctrl+S)") == "Projekt speichern (Strg+S)"
    assert lbl.tr("Undo (Ctrl+Z)") == "Rückgängig (Strg+Z)"
    assert lbl.tr("Redo (Ctrl+Y)") == "Wiederholen (Strg+Y)"
    assert lbl.tr("Fit sheet to window (Ctrl+0)") == "Blatt im Fenster einpassen (Strg+0)"
    assert lbl.tr("Center on sheet or printable area") == "Mittig auf Blatt oder plottbarem Bereich ausrichten"
    assert lbl.tr("Configure plotter devices...") == "Plotter-Geräte konfigurieren..."

    # Transformation Dock Flip tooltips and buttons
    assert lbl.tr("Flip Horiz.") == "Horiz. spiegeln"
    assert lbl.tr("Flip Vert.") == "Vert. spiegeln"
    assert lbl.tr("Mirror selected object horizontally") == "Auswahl horizontal spiegeln"
    assert lbl.tr("Mirror selected object vertically") == "Auswahl vertikal spiegeln"

    # Standard dialog buttons (e.g. Unsaved Changes dialog)
    assert QCoreApplication.translate("QPlatformTheme", "Save") == "Speichern"
    assert QCoreApplication.translate("QPlatformTheme", "Discard") == "Verwerfen"
    assert QCoreApplication.translate("QPlatformTheme", "Cancel") == "Abbrechen"
    assert QCoreApplication.translate("QPlatformTheme", "&Save") == "&Speichern"
    assert QCoreApplication.translate("QPlatformTheme", "&Discard") == "&Verwerfen"
    assert QCoreApplication.translate("QPlatformTheme", "&Cancel") == "&Abbrechen"


def test_translator_accelerator_handling(qapp):
    """PlotterTranslator matches keys gracefully regardless of accelerator '&' differences."""
    setup_i18n(qapp, language_override="en")
    translator = PlotterTranslator(qapp)
    translator.load_dict({
        "&Save": "&Speichern",
        "Discard": "Verwerfen",
    }, lang="de")
    qapp.installTranslator(translator)

    lbl = QLabel()
    # Exact matches
    assert lbl.tr("&Save") == "&Speichern"
    assert lbl.tr("Discard") == "Verwerfen"

    # Stripping '&' from source_text finds key without '&'
    assert lbl.tr("&Discard") == "Verwerfen"

    qapp.removeTranslator(translator)
    setup_i18n(qapp, language_override="de")


def test_all_gui_tr_keys_translated_in_de_json():
    """Every literal string passed to tr()/_tr() in gui/*.py must exist in de.json."""
    de_path = get_translations_dir() / "de.json"
    de = json.loads(de_path.read_text(encoding="utf-8"))
    all_de_keys = set(de.keys())

    gui_glob = str(de_path.parent.parent.parent / "src" / "linto" / "gui" / "*.py")
    missing = []
    for path in sorted(glob.glob(gui_glob)):
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = None
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("tr", "translate"):
                    func_name = node.func.attr
                elif isinstance(node.func, ast.Name) and node.func.id in ("tr", "_tr"):
                    func_name = node.func.id
                if func_name and node.args:
                    arg_idx = 1 if func_name == "translate" and len(node.args) >= 2 else 0
                    arg = node.args[arg_idx]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value not in all_de_keys:
                            missing.append((path, node.lineno, arg.value))

    assert missing == [], f"Missing keys in de.json: {missing}"


