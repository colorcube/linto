"""Tests for the Linux desktop integration (menu entry + icon) and CLI options."""

import subprocess
import sys

from linto import RESOURCES_DIR
from linto import desktop


def test_icon_is_packaged():
    icon = RESOURCES_DIR / "icons" / "linto.svg"
    assert icon.is_file()
    assert "<svg" in icon.read_text(encoding="utf-8")


def test_install_and_uninstall_desktop_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(desktop, "_refresh_caches", lambda: None)

    written = desktop.install_desktop_entry()
    entry = tmp_path / "applications" / "de.colorcube.linto.desktop"
    icon = tmp_path / "icons" / "hicolor" / "scalable" / "apps" / "de.colorcube.linto.svg"
    assert set(written) == {entry, icon}
    assert icon.read_bytes() == desktop.ICON_SOURCE.read_bytes()

    text = entry.read_text(encoding="utf-8")
    assert "Name=LINTO" in text
    assert "Icon=de.colorcube.linto" in text
    exec_line = next(line for line in text.splitlines() if line.startswith("Exec="))
    assert exec_line.endswith(" %f")

    removed = desktop.uninstall_desktop_entry()
    assert set(removed) == {entry, icon}
    assert not entry.exists() and not icon.exists()
    assert desktop.uninstall_desktop_entry() == []


def test_cli_version():
    out = subprocess.run(
        [sys.executable, "-m", "linto", "--version"], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().startswith("linto ")


def test_install_removes_legacy_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(desktop, "_refresh_caches", lambda: None)
    legacy = tmp_path / "applications" / "linto.desktop"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("[Desktop Entry]\n", encoding="utf-8")

    desktop.install_desktop_entry()
    assert not legacy.exists()
