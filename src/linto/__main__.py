"""CLI entrypoint for running linto."""

import argparse
import sys

from . import __version__


def main():
    parser = argparse.ArgumentParser(
        prog="linto",
        description="LINTO – slicer, layout editor and streaming controller for pen plotters.",
    )
    parser.add_argument("file", nargs="?", help="SVG, HP-GL or LINTO project file to open")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--install-desktop",
        action="store_true",
        help="add LINTO to the application menu of the current user (Linux)",
    )
    group.add_argument(
        "--uninstall-desktop",
        action="store_true",
        help="remove the application menu entry again",
    )
    # Qt consumes its own options (e.g. -platform); keep unknown ones for QApplication.
    args, qt_args = parser.parse_known_args()

    if args.install_desktop or args.uninstall_desktop:
        from .desktop import install_desktop_entry, uninstall_desktop_entry

        if args.install_desktop:
            for path in install_desktop_entry():
                print(f"Installed: {path}")
        else:
            removed = uninstall_desktop_entry()
            for path in removed:
                print(f"Removed: {path}")
            if not removed:
                print("Nothing to remove.")
        return

    from .gui.app import run_gui

    sys.exit(run_gui(qt_args=[sys.argv[0], *qt_args], open_file=args.file))


if __name__ == "__main__":
    main()
