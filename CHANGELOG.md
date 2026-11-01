# Changelog

All notable changes to LINTO are listed here. Versions follow [Semantic Versioning](https://semver.org/).

## 0.1.1 – unreleased

- rpm (Fedora) and deb (Debian) packages, built and attached to each GitHub release
- Status messages during plotting are shown in the UI language (they were always German before)
- Own device profiles in `~/.config/linto/devices/`; a profile with the same file name replaces the bundled one
- Device Settings: button that opens the folder for own device profiles
- Application ID `de.colorcube.linto` for the menu entry and icon; `linto --install-desktop` removes the old `linto.desktop` entry
- Works with svgelements 1.7 (as shipped by Debian 13)

## 0.1.0 – 2026-11-01

First public alpha, licensed under the GPL-3.0-or-later. Developed and tested on Linux with a Mutoh XP-500; all other device profiles are untested on real hardware.

- Layout in real millimeters on DIN A4–A0 or custom sheets with the plotter's hard-clip margins; sheet size query from the plotter (`OH;`)
- Slicer pipeline: curve flattening, merging of connected segments, simplification and travel optimization (2-Opt)
- Simulation of the whole plot including pen-up travel, with a pre-flight summary of drawing distance, travel and estimated time
- Automatic mapping of stroke colors to up to 8 pens; speed (`VS`) and force (`FS`) per pen
- Streaming over RS-232 or TCP with hardware flow control (RTS/CTS), pause, resume and safe abort
- 26 device profiles: Mutoh XP-500, a generic HP-GL profile and 24 profiles adapted from InkCut
- Built-in plotter emulator (`python3 -m linto.emulator --tcp 9999`)
- User interface and manual in English and German
