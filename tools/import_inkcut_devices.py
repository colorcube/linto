#!/usr/bin/env python3
"""
Import HP-GL device profiles from InkCut's drivers manifest.enaml into LINTO.

Usage:
    python3 tools/import_inkcut_devices.py --source /path/to/inkcut/inkcut/device/drivers/manifest.enaml [--output src/linto/resources/devices]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
import yaml


def parse_dimension_mm(val: str | None) -> float | None:
    """Parse dimension strings like '60cm', '12in', '46.8cm' into mm."""
    if not val:
        return None
    val = val.strip("'\" ")
    try:
        if val.endswith("cm"):
            return round(float(val[:-2]) * 10.0, 1)
        elif val.endswith("in"):
            return round(float(val[:-2]) * 25.4, 1)
        elif val.endswith("mm"):
            return round(float(val[:-2]), 1)
        return round(float(val), 1)
    except ValueError:
        return None


def extract_hpgl_drivers(manifest_path: Path) -> list[dict]:
    """Parse manifest.enaml and extract all DeviceDriver blocks with 'hpgl' protocol."""
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    content = manifest_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    raw_drivers: list[dict] = []
    curr: dict | None = None

    for line in lines:
        if "DeviceDriver:" in line:
            if curr:
                raw_drivers.append(curr)
            curr = {}
        elif curr is not None:
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "=" in stripped:
                parts = stripped.split("=", 1)
                k = parts[0].strip()
                v = parts[1].strip()
                curr[k] = v
            elif "swap_xy" in stripped:
                curr["swap_xy"] = True

    if curr:
        raw_drivers.append(curr)

    # Filter for HP-GL protocol
    hpgl_drivers = []
    for d in raw_drivers:
        proto_str = d.get("protocols", "")
        if "hpgl" in proto_str:
            hpgl_drivers.append(d)

    return hpgl_drivers


def convert_driver_to_profile(driver: dict) -> dict:
    """Convert an InkCut driver dictionary into a LINTO DeviceProfile dict."""
    m = driver.get("manufacturer", "Generic").strip("'\" ")
    mod = driver.get("model", "Plotter").strip("'\" ")
    w = parse_dimension_mm(driver.get("width"))
    l = parse_dimension_mm(driver.get("length"))
    swap_xy = bool(driver.get("swap_xy", False))

    slug = f"{m.lower()}_{mod.lower()}"
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")

    profile = {
        "model_id": slug,
        "name": f"{m} {mod}",
        "manufacturer": m,
        "emulation": "HP-GL",
        "protocol": "hpgl",
        "origin": "bottom_left",
        "units_per_mm": 40.0,
        "max_pens": 1,
        "swap_xy": swap_xy,
        "invert_x": False,
        "invert_y": False,
        "rotation_deg": 0,
        "connection": {
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            "rtscts": True,
            "xonxoff": False,
        },
        "margins_mm": {
            "default": {
                "top": 10.0,
                "bottom": 10.0,
                "left": 10.0,
                "right": 10.0,
            },
            "minimal": {
                "top": 5.0,
                "bottom": 5.0,
                "left": 5.0,
                "right": 5.0,
            },
        },
        "default_margin_profile": "default",
    }

    if w:
        profile["max_width_mm"] = w
    if l:
        profile["max_length_mm"] = l

    return profile


def main():
    parser = argparse.ArgumentParser(description="Import InkCut HP-GL drivers into LINTO")
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to inkcut/device/drivers/manifest.enaml in a checkout of https://github.com/inkcut/inkcut",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "src" / "linto" / "resources" / "devices",
        help="Target directory for generated YAML profiles",
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="Only list the detected HP-GL devices without writing files",
    )

    args = parser.parse_args()

    if not args.source.is_file():
        print(f"Error: InkCut manifest not found at {args.source}", file=sys.stderr)
        sys.exit(1)

    drivers = extract_hpgl_drivers(args.source)
    print(f"Found {len(drivers)} HP-GL devices in InkCut manifest:")
    for d in drivers:
        m = d.get("manufacturer", "").strip("'\" ")
        mod = d.get("model", "").strip("'\" ")
        w = d.get("width", "n/a").strip("'\" ")
        swap = "swap_xy=True" if d.get("swap_xy") else ""
        print(f"  - {m} {mod} (Breite: {w} {swap})")

    if args.list_only:
        return

    args.output.mkdir(parents=True, exist_ok=True)
    count = 0
    for d in drivers:
        profile = convert_driver_to_profile(d)
        target_file = args.output / f"{profile['model_id']}.yaml"
        # Write formatted YAML
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile, f, sort_keys=False)
        count += 1

    print(f"\nSuccessfully generated {count} device profile YAMLs in {args.output}")


if __name__ == "__main__":
    main()
