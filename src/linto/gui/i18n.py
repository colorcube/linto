"""Internationalization (i18n) support for LINTO.

Provides QTranslator-based localization with automatic system locale detection
and fallback to English.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


def get_translations_dir() -> Path:
    """Return the absolute path to the resources/translations directory."""
    from .. import RESOURCES_DIR

    return RESOURCES_DIR / "translations"


class PlotterTranslator(QTranslator):
    """Custom QTranslator that translates strings from dictionaries or JSON files.

    If a string is not found in the dictionary, translate() returns an empty string
    which tells Qt to fall back to the original source text (English).
    """

    def __init__(self, parent: Optional[QApplication] = None) -> None:
        super().__init__(parent)
        self._context_messages: dict[tuple[str, str], str] = {}
        self._global_messages: dict[str, str] = {}
        self._active_language: str = "en"

    @property
    def active_language(self) -> str:
        return self._active_language

    def load_dict(self, messages: dict, lang: str = "de") -> None:
        """Load translations from a dictionary.

        Can contain flat key-values:
            {"&File": "&Datei", "&Open...": "&Öffnen..."}
        or nested context dictionaries:
            {"MainWindow": {"&File": "&Datei"}, "Canvas": {...}}
        """
        self._active_language = lang
        for key, val in messages.items():
            if isinstance(val, dict):
                context = key
                for src, trans in val.items():
                    if isinstance(trans, str):
                        self._context_messages[(context, src)] = trans
                        if src not in self._global_messages:
                            self._global_messages[src] = trans
            elif isinstance(val, str):
                self._global_messages[key] = val

    def load_json(self, path: Path | str, lang: str = "de") -> bool:
        """Load translations from a JSON file."""
        file_path = Path(path)
        if not file_path.is_file():
            return False
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            self.load_dict(data, lang=lang)
            logger.info("Loaded translations for '%s' from %s", lang, file_path)
            return True
        except Exception as e:
            logger.error("Failed to load translation file %s: %s", file_path, e)
            return False

    def translate(
        self,
        context: str,
        source_text: str,
        disambiguation: Optional[str] = None,
        n: int = -1,
    ) -> str:
        """Qt translation hook called on self.tr() and QCoreApplication.translate()."""
        # 1. Exact match with context
        match = self._context_messages.get((context, source_text))
        if match:
            return match

        # 2. Global match across contexts
        match = self._global_messages.get(source_text)
        if match:
            return match

        # 3. If source_text has accelerator '&', try matching without it as fallback
        if "&" in source_text:
            clean = source_text.replace("&", "")
            match = self._global_messages.get(clean)
            if match:
                return match

        # 4. Fallback to original source text
        return source_text


def setup_i18n(
    app: QApplication,
    language_override: Optional[str] = None,
) -> Tuple[PlotterTranslator, Optional[QTranslator]]:
    """Configure and install application and Qt system translators.

    Args:
        app: The active QApplication instance.
        language_override: Optional explicit language code (e.g. 'de', 'en').
                           If None, detects the system UI language.

    Returns:
        A tuple of (app_translator, qt_base_translator).
    """
    if language_override:
        lang = language_override.strip().lower()
    else:
        # Detect system language (e.g. 'de_DE' -> 'de')
        sys_locale = QLocale.system().name()
        lang = sys_locale.split("_")[0].lower() if sys_locale else "en"

    logger.debug("Configuring i18n for language: '%s'", lang)

    app_translator = PlotterTranslator(app)
    qt_translator: Optional[QTranslator] = None

    # If language is English, source strings are already English -> no translator needed
    if lang == "en":
        logger.debug("Language is English, using native source strings.")
        return app_translator, None

    # 1. Try to load application translations from resources/translations/<lang>.json
    trans_dir = get_translations_dir()
    json_path = trans_dir / f"{lang}.json"

    if json_path.is_file():
        app_translator.load_json(json_path, lang=lang)
        app.installTranslator(app_translator)
    else:
        # Check for compiled .qm file if available
        qm_path = trans_dir / f"linto_{lang}.qm"
        if qm_path.is_file():
            loaded = app_translator.load(str(qm_path))
            if loaded:
                app.installTranslator(app_translator)
                logger.info("Loaded .qm translations from %s", qm_path)

    # 2. Load Qt's built-in translations (OK, Cancel, Yes, No, file dialog buttons)
    qt_translations_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    qt_candidate = QTranslator(app)
    if qt_candidate.load(f"qtbase_{lang}", qt_translations_path):
        app.installTranslator(qt_candidate)
        qt_translator = qt_candidate
        logger.debug("Loaded Qt base translations for '%s' from %s", lang, qt_translations_path)

    return app_translator, qt_translator
