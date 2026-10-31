import pytest
import os
import tempfile
import numpy as np
from linto.core.document import Document, ImportItem, VectorPath, LogicalPen
from linto.core.geometry import Point
from linto.core.pen_presets import (
    PenPreset,
    get_builtin_presets,
    save_preset_json,
    load_preset_json,
    remap_document_to_preset,
)


def test_builtin_presets_exist():
    presets = get_builtin_presets()
    assert len(presets) >= 5
    names = [p.name for p in presets]
    assert any("Fineliner (8 Farben)" in n for n in names)
    assert any("Fineliner (4 Farben Basic)" in n for n in names)
    assert any("Monochrom" in n for n in names)
    assert any("Posca" in n for n in names)
    assert any("Kugelschreiber" in n for n in names)
    assert any("Tusche" in n for n in names)


def test_preset_serialization_roundtrip():
    preset = PenPreset(
        name="Custom Test Set",
        description="Testing preset export and import",
        pens=[
            LogicalPen(pen_id=1, name="Custom Black", color_hex="#111111", width_mm=0.4, speed_cm_s=15.0, force_g=30.0, enabled=True),
            LogicalPen(pen_id=2, name="Custom Red", color_hex="#ff0000", width_mm=0.5, speed_cm_s=25.0, force_g=20.0, enabled=False),
        ]
    )
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        save_preset_json(preset, tmp_path)
        loaded = load_preset_json(tmp_path)
        assert loaded.name == preset.name
        assert loaded.description == preset.description
        assert len(loaded.pens) == 2
        assert loaded.pens[0].name == "Custom Black"
        assert loaded.pens[0].width_mm == 0.4
        assert loaded.pens[0].force_g == 30.0
        assert loaded.pens[1].enabled is False
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_remap_document_to_preset_slot_strategy():
    doc = Document()
    # Add an item with paths assigned to pens 1, 2, and 5
    item = ImportItem(
        name="test.svg",
        paths=[
            VectorPath(points=np.array([[0.0, 0.0], [10.0, 10.0]]), pen_id=1),
            VectorPath(points=np.array([[10.0, 10.0], [20.0, 20.0]]), pen_id=2),
            VectorPath(points=np.array([[20.0, 20.0], [30.0, 30.0]]), pen_id=5),
        ]
    )
    doc.items.append(item)

    # 4-pen preset: pens 1..4 enabled, 5..8 disabled
    four_pen = next(p for p in get_builtin_presets() if "4 Farben" in p.name)
    old_pens, old_assignments = remap_document_to_preset(doc, four_pen, strategy="slot")

    assert len(old_pens) == 8
    assert len(old_assignments) == 3
    # Pen 1 and 2 should remain 1 and 2
    assert item.paths[0].pen_id == 1
    assert item.paths[1].pen_id == 2
    # Pen 5 was disabled in the 4-pen preset, so it should fall back to pen 1
    assert item.paths[2].pen_id == 1


def test_remap_document_to_preset_delta_e_strategy():
    doc = Document()
    # Create an item with a bright red path and a dark path
    item = ImportItem(
        name="colors.svg",
        paths=[
            VectorPath(points=np.array([[0.0, 0.0], [10.0, 0.0]]), pen_id=1),  # Default doc pen 1 is black (#1a1a1a)
            VectorPath(points=np.array([[0.0, 10.0], [10.0, 10.0]]), pen_id=2), # Default doc pen 2 is red (#d32f2f)
        ]
    )
    doc.items.append(item)

    # Apply 4-color basic preset (1: Black, 2: Cyan, 3: Magenta, 4: Yellow)
    four_pen = next(p for p in get_builtin_presets() if "4 Farben" in p.name)
    remap_document_to_preset(doc, four_pen, strategy="delta_e")

    # Black (pen 1) should remain matched to black (pen 1)
    assert item.paths[0].pen_id == 1
    # Red (#d32f2f) is perceptually closest to Magenta (#e6007e) in this palette
    assert item.paths[1].pen_id == 3
