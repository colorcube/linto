"""LINTO - Modular Slicer & Studio for Pen Plotters under Linux."""

__version__ = "0.1.0"

import os
from pathlib import Path

#: Bundled data files (device profiles, translations, calibration plots), shipped as package data.
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"


def user_config_dir() -> Path:
    """Per-user configuration directory (``$XDG_CONFIG_HOME/linto``, default ``~/.config/linto``)."""
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "linto"
