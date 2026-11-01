"""The version number must match in the package and in all packaging files."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import linto

ROOT = Path(__file__).resolve().parent.parent
VERSION = linto.__version__


def test_rpm_spec_version():
    spec = (ROOT / "packaging" / "rpm" / "linto.spec").read_text(encoding="utf-8")
    assert re.search(rf"^Version:\s*{re.escape(VERSION)}$", spec, re.M)
    first_changelog = spec.split("%changelog", 1)[1].strip().splitlines()[0]
    assert first_changelog.endswith(f"- {VERSION}-1"), first_changelog


def test_debian_changelog_version():
    first = (ROOT / "packaging" / "debian" / "changelog").read_text(encoding="utf-8").splitlines()[0]
    assert first.startswith(f"linto ({VERSION}-"), first


def test_metainfo_latest_release():
    root = ET.parse(linto.RESOURCES_DIR / "desktop" / "de.colorcube.linto.metainfo.xml").getroot()
    latest = root.find("releases/release")
    assert latest is not None and latest.get("version") == VERSION
