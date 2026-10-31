"""CLI entrypoint for running linto."""

import sys
from .gui.app import run_gui


def main():
    sys.exit(run_gui())


if __name__ == "__main__":
    main()
