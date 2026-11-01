"""Desktop integration for Linux: menu entry (.desktop file) and application icon.

Used for pip/pipx installs (``linto --install-desktop``); distribution packages install the
same files system-wide. Installs into the user's XDG data directory (``~/.local/share`` by
default), so no root privileges are needed.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import RESOURCES_DIR

APP_ID = "de.colorcube.linto"
DESKTOP_SOURCE = RESOURCES_DIR / "desktop" / f"{APP_ID}.desktop"
ICON_SOURCE = RESOURCES_DIR / "icons" / "linto.svg"

# File names used by LINTO before the reverse-DNS application ID; removed on (un)install.
_LEGACY_NAMES = ("linto.desktop", "linto.svg")


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def desktop_file_path() -> Path:
    return _data_home() / "applications" / f"{APP_ID}.desktop"


def icon_path() -> Path:
    return _data_home() / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"


def _legacy_paths() -> list[Path]:
    return [
        _data_home() / "applications" / _LEGACY_NAMES[0],
        _data_home() / "icons" / "hicolor" / "scalable" / "apps" / _LEGACY_NAMES[1],
    ]


def _exec_command() -> str:
    """Command line that starts LINTO from the current installation."""
    launcher = shutil.which("linto")
    if launcher:
        return shlex.quote(str(Path(launcher).resolve()))
    return f"{shlex.quote(sys.executable)} -m linto"


def desktop_entry_text() -> str:
    """The bundled desktop entry, with Exec pointing to this installation."""
    lines = []
    for line in DESKTOP_SOURCE.read_text(encoding="utf-8").splitlines():
        if line.startswith("Exec="):
            line = f"Exec={_exec_command()} %f"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _refresh_caches() -> None:
    """Refresh desktop/icon caches if the tools exist; failures are harmless."""
    for cmd in (
        ["update-desktop-database", str(desktop_file_path().parent)],
        ["gtk-update-icon-cache", "-q", "-t", str(_data_home() / "icons" / "hicolor")],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _remove_legacy() -> list[Path]:
    removed = []
    for path in _legacy_paths():
        if path.is_file():
            path.unlink()
            removed.append(path)
    return removed


def install_desktop_entry() -> list[Path]:
    """Install the .desktop file and icon for the current user. Returns the written paths."""
    _remove_legacy()
    icon = icon_path()
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_SOURCE, icon)

    desktop = desktop_file_path()
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(desktop_entry_text(), encoding="utf-8")
    _refresh_caches()
    return [desktop, icon]


def uninstall_desktop_entry() -> list[Path]:
    """Remove the .desktop file and icon. Returns the paths that were removed."""
    removed = []
    for path in (desktop_file_path(), icon_path()):
        if path.is_file():
            path.unlink()
            removed.append(path)
    removed += _remove_legacy()
    _refresh_caches()
    return removed
