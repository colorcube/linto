"""Pen presets management, loading, saving and intelligent remapping."""

from __future__ import annotations
import copy
import os
import json
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
from .document import DEFAULT_PENS, Document, LogicalPen, VectorPath
from .color_cluster import rgb_hex_to_lab, find_closest_pen_id


@dataclass
class PenPreset:
    """A configured set of logical pens with physical attributes."""
    name: str
    description: str
    pens: List[LogicalPen]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "pens": [
                {
                    "pen_id": p.pen_id,
                    "name": p.name,
                    "color_hex": p.color_hex,
                    "width_mm": p.width_mm,
                    "speed_cm_s": p.speed_cm_s,
                    "force_g": p.force_g,
                    "enabled": p.enabled,
                    "mapped_to": p.mapped_to,
                }
                for p in self.pens
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PenPreset:
        pens = []
        for pd in data.get("pens", []):
            pens.append(
                LogicalPen(
                    pen_id=pd["pen_id"],
                    name=pd.get("name", f"Stift {pd['pen_id']}"),
                    color_hex=pd.get("color_hex", "#000000"),
                    width_mm=float(pd.get("width_mm", 0.35)),
                    speed_cm_s=float(pd.get("speed_cm_s", 20.0)),
                    force_g=float(pd.get("force_g", 20.0)),
                    enabled=bool(pd.get("enabled", True)),
                    mapped_to=pd.get("mapped_to"),
                )
            )
        return cls(
            name=data.get("name", "Unbenanntes Preset"),
            description=data.get("description", ""),
            pens=pens,
        )


BUILTIN_PRESETS: List[PenPreset] = [
    PenPreset(
        name="Fineliner (8 Farben)",
        description="Standard 0.35 mm Fineliner (Schwarz, Rot, Blau, Grün, Orange, Magenta, Cyan, Gelb)",
        pens=[copy.deepcopy(p) for p in DEFAULT_PENS],
    ),
    PenPreset(
        name="Fineliner (4 Farben Basic)",
        description="4-Farben Fineliner Set (Schwarz, Cyan, Magenta, Gelb)",
        pens=[
            LogicalPen(1, "Stift 1 (Schwarz)", "#1a1a1a", width_mm=0.35, speed_cm_s=20.0, enabled=True),
            LogicalPen(2, "Stift 2 (Cyan)", "#00a0dc", width_mm=0.35, speed_cm_s=20.0, enabled=True),
            LogicalPen(3, "Stift 3 (Magenta)", "#e6007e", width_mm=0.35, speed_cm_s=20.0, enabled=True),
            LogicalPen(4, "Stift 4 (Gelb)", "#fff100", width_mm=0.35, speed_cm_s=20.0, enabled=True),
            LogicalPen(5, "Stift 5", "#9e9e9e", width_mm=0.35, enabled=False),
            LogicalPen(6, "Stift 6", "#9e9e9e", width_mm=0.35, enabled=False),
            LogicalPen(7, "Stift 7", "#9e9e9e", width_mm=0.35, enabled=False),
            LogicalPen(8, "Stift 8", "#9e9e9e", width_mm=0.35, enabled=False),
        ],
    ),
    PenPreset(
        name="Monochrom (Nur 1 Stift)",
        description="Einfarbiger technischer Plot mit einem einzelnen Stift",
        pens=[
            LogicalPen(1, "Stift 1 (Schwarz)", "#1a1a1a", width_mm=0.35, speed_cm_s=25.0, enabled=True),
            LogicalPen(2, "Stift 2", "#888888", enabled=False),
            LogicalPen(3, "Stift 3", "#888888", enabled=False),
            LogicalPen(4, "Stift 4", "#888888", enabled=False),
            LogicalPen(5, "Stift 5", "#888888", enabled=False),
            LogicalPen(6, "Stift 6", "#888888", enabled=False),
            LogicalPen(7, "Stift 7", "#888888", enabled=False),
            LogicalPen(8, "Stift 8", "#888888", enabled=False),
        ],
    ),
    PenPreset(
        name="Posca Acrylmarker (4 Farben)",
        description="Deckende Acryl-Farbmarker (0.7 mm, langsame Geschwindigkeit für satten Fluss)",
        pens=[
            LogicalPen(1, "Stift 1 (Schwarz)", "#111111", width_mm=0.70, speed_cm_s=10.0, force_g=25.0, enabled=True),
            LogicalPen(2, "Stift 2 (Weiß)", "#f8f8f8", width_mm=0.70, speed_cm_s=10.0, force_g=25.0, enabled=True),
            LogicalPen(3, "Stift 3 (Gold/Ocker)", "#d4af37", width_mm=0.70, speed_cm_s=10.0, force_g=25.0, enabled=True),
            LogicalPen(4, "Stift 4 (Karminrot)", "#d32f2f", width_mm=0.70, speed_cm_s=10.0, force_g=25.0, enabled=True),
            LogicalPen(5, "Stift 5", "#9e9e9e", width_mm=0.70, enabled=False),
            LogicalPen(6, "Stift 6", "#9e9e9e", width_mm=0.70, enabled=False),
            LogicalPen(7, "Stift 7", "#9e9e9e", width_mm=0.70, enabled=False),
            LogicalPen(8, "Stift 8", "#9e9e9e", width_mm=0.70, enabled=False),
        ],
    ),
    PenPreset(
        name="Kugelschreiber (Ballpoint)",
        description="Kugelschreiber-Set (0.5 mm, hohe Geschwindigkeit, hoher Anpressdruck)",
        pens=[
            LogicalPen(1, "Stift 1 (Blau)", "#0d47a1", width_mm=0.50, speed_cm_s=35.0, force_g=50.0, enabled=True),
            LogicalPen(2, "Stift 2 (Schwarz)", "#212121", width_mm=0.50, speed_cm_s=35.0, force_g=50.0, enabled=True),
            LogicalPen(3, "Stift 3 (Rot)", "#b71c1c", width_mm=0.50, speed_cm_s=35.0, force_g=50.0, enabled=True),
            LogicalPen(4, "Stift 4 (Grün)", "#1b5e20", width_mm=0.50, speed_cm_s=35.0, force_g=50.0, enabled=True),
            LogicalPen(5, "Stift 5", "#888888", enabled=False),
            LogicalPen(6, "Stift 6", "#888888", enabled=False),
            LogicalPen(7, "Stift 7", "#888888", enabled=False),
            LogicalPen(8, "Stift 8", "#888888", enabled=False),
        ],
    ),
    PenPreset(
        name="Tusche / Isograph (DIN 15 Strichstärken)",
        description="Technische Tuschezeichner nach Norm (0.25, 0.35, 0.50, 0.70 mm, schwarz)",
        pens=[
            LogicalPen(1, "Stift 1 (0.25 mm Fein)", "#0a0a0a", width_mm=0.25, speed_cm_s=12.0, force_g=15.0, enabled=True),
            LogicalPen(2, "Stift 2 (0.35 mm Mittel)", "#0a0a0a", width_mm=0.35, speed_cm_s=12.0, force_g=15.0, enabled=True),
            LogicalPen(3, "Stift 3 (0.50 mm Breit)", "#0a0a0a", width_mm=0.50, speed_cm_s=12.0, force_g=15.0, enabled=True),
            LogicalPen(4, "Stift 4 (0.70 mm Extra)", "#0a0a0a", width_mm=0.70, speed_cm_s=10.0, force_g=15.0, enabled=True),
            LogicalPen(5, "Stift 5", "#888888", enabled=False),
            LogicalPen(6, "Stift 6", "#888888", enabled=False),
            LogicalPen(7, "Stift 7", "#888888", enabled=False),
            LogicalPen(8, "Stift 8", "#888888", enabled=False),
        ],
    ),
]


def get_builtin_presets() -> List[PenPreset]:
    return list(BUILTIN_PRESETS)


def get_user_presets_dir() -> str:
    """Return user presets directory path, creating it if possible."""
    d = os.environ.get("PLOTTER_STUDIO_CONFIG_DIR")
    if not d:
        d = os.path.expanduser("~/.config/plotter-studio/pens")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def list_user_presets() -> List[PenPreset]:
    """Load and return all user PenPresets from the user presets directory."""
    presets: List[PenPreset] = []
    pdir = get_user_presets_dir()
    if os.path.exists(pdir):
        for fname in sorted(os.listdir(pdir)):
            if fname.endswith(".json"):
                fpath = os.path.join(pdir, fname)
                try:
                    presets.append(load_preset_json(fpath))
                except (OSError, ValueError, KeyError, TypeError):
                    pass
    return presets


def save_user_preset(preset: PenPreset) -> str:
    """Save a PenPreset to the user presets directory and return the saved file path."""
    safe_fname = "".join(c for c in preset.name if c.isalnum() or c in " -_").strip() or "preset"
    fpath = os.path.join(get_user_presets_dir(), f"{safe_fname}.json")
    save_preset_json(preset, fpath)
    return fpath


def save_preset_json(preset: PenPreset, filepath: str):
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(preset.to_dict(), f, indent=2, ensure_ascii=False)


def load_preset_json(filepath: str) -> PenPreset:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PenPreset.from_dict(data)


def remap_document_to_preset(
    doc: Document,
    preset: PenPreset,
    strategy: str = "slot"
) -> Tuple[List[LogicalPen], List[Tuple[VectorPath, int]]]:
    """
    Applies a PenPreset to Document.
    Returns (old_pens, old_path_assignments) for undo support.

    strategy:
      - 'slot': Stift 1 bleibt Stift 1; übernimmt neue Farben/Minen.
        Pfade auf deaktivierten Stiften werden auf den ersten aktiven Stift umgeleitet.
      - 'delta_e': Berechnet für alle Pfade den farblich ähnlichsten aktiven Stift im neuen Set.
    """
    old_pens = copy.deepcopy(doc.pens)
    old_assignments: List[Tuple[VectorPath, int]] = []
    for item in doc.items:
        for p in item.paths:
            old_assignments.append((p, p.pen_id))

    # 1. Update doc.pens from preset (1..8)
    preset_dict = {p.pen_id: p for p in preset.pens}
    for i in range(1, 9):
        target_pen = doc.get_pen(i)
        if target_pen:
            src = preset_dict.get(i)
            if src:
                target_pen.name = src.name
                target_pen.color_hex = src.color_hex
                target_pen.width_mm = src.width_mm
                target_pen.speed_cm_s = src.speed_cm_s
                target_pen.force_g = src.force_g
                target_pen.enabled = src.enabled
                target_pen.mapped_to = src.mapped_to
            else:
                target_pen.enabled = False

    enabled_pens = [p for p in doc.pens if p.enabled]
    fallback_pen_id = enabled_pens[0].pen_id if enabled_pens else 1

    # 2. Update path assignments according to strategy
    if strategy == "slot":
        enabled_ids = {p.pen_id for p in enabled_pens}
        for item in doc.items:
            for p in item.paths:
                if p.pen_id not in enabled_ids:
                    p.pen_id = fallback_pen_id
    elif strategy == "delta_e":
        pen_palette = [(p.pen_id, rgb_hex_to_lab(p.color_hex)) for p in enabled_pens]
        old_pen_dict = {p.pen_id: p for p in old_pens}

        for item in doc.items:
            for path in item.paths:
                old_p = old_pen_dict.get(path.pen_id)
                old_color = old_p.color_hex if old_p else "#000000"
                path.pen_id = find_closest_pen_id(old_color, pen_palette, fallback_pen_id=fallback_pen_id)

    return old_pens, old_assignments
