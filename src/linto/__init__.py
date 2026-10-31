"""LINTO - Modular Slicer & Studio for Pen Plotters under Linux."""

__version__ = "0.1.0"

from pathlib import Path

#: Bundled data files (device profiles, translations, calibration plots), shipped as package data.
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
