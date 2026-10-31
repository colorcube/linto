"""Desktop integration for Linux: menu entry (.desktop file) and application icon.

Installs into the user's XDG data directory (``~/.local/share`` by default), so no
root privileges are needed. Works for pip, pipx and editable installs alike.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import RESOURCES_DIR

APP_ID = "linto"
ICON_SOURCE = RESOURCES_DIR / "icons" / "linto.svg"

DESKTOP_TEMPLATE = """[Desktop Entry]
Type=Application
Name=LINTO
GenericName=Pen Plotter Studio
GenericName[de]=Stiftplotter-Studio
Comment=Prepare, simulate and plot vector graphics on pen plotters
Comment[de]=Vektorgrafiken für Stiftplotter vorbereiten, simulieren und plotten
Exec={exec} %f
Icon={icon}
Terminal=false
Categories=Graphics;2DGraphics;VectorGraphics;Engineering;
MimeType=image/svg+xml;application/vnd.hp-hpgl;
Keywords=plotter;pen plotter;HP-GL;HPGL;SVG;
StartupWMClass={app_id}
"""


def _data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def desktop_file_path() -> Path:
    return _data_home() / "applications" / f"{APP_ID}.desktop"


def icon_path() -> Path:
    return _data_home() / "icons" / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"


def _exec_command() -> str:
    """Command line that starts LINTO from the current installation."""
    launcher = shutil.which(APP_ID)
    if launcher:
        return shlex.quote(str(Path(launcher).resolve()))
    return f"{shlex.quote(sys.executable)} -m {APP_ID}"


def _refresh_caches() -> None:
    """Refresh desktop/icon caches if the tools exist; failures are harmless."""
    for cmd in (
        ["update-desktop-database", str(desktop_file_path().parent)],
        ["gtk-update-icon-cache", "-q", "-t", str(_data_home() / "icons" / "hicolor")],
    ):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install_desktop_entry() -> list[Path]:
    """Install the .desktop file and icon for the current user. Returns the written paths."""
    icon = icon_path()
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ICON_SOURCE, icon)

    desktop = desktop_file_path()
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text(
        DESKTOP_TEMPLATE.format(exec=_exec_command(), icon=APP_ID, app_id=APP_ID),
        encoding="utf-8",
    )
    _refresh_caches()
    return [desktop, icon]


def uninstall_desktop_entry() -> list[Path]:
    """Remove the .desktop file and icon. Returns the paths that were removed."""
    removed = []
    for path in (desktop_file_path(), icon_path()):
        if path.is_file():
            path.unlink()
            removed.append(path)
    _refresh_caches()
    return removed
