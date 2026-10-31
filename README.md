# LINTO

> **The modular slicer, layout editor, and streaming controller for physical vector pen plotters.**

LINTO prepares vector graphics for real pen plotters: it optimizes pen paths to cut down pen-up travel, simulates the drawing process interactively on screen, and streams commands reliably with hardware flow control directly to your machine.

> **Project status: early alpha (v0.1.0).** Developed and tested on Linux with a Mutoh XP-500 (HP-GL / HP 7585B emulation). The other device profiles are untested on real hardware — feedback and bug reports are very welcome.

---

## Visual Tour

### Layout Mode: Arrange, scale, and map vector artwork to pens
![LINTO Layout Mode](docs/manual/en/images/ui_overview_layout.png)

### Output Mode: Path optimization, pen-up travel visualization & simulation
![LINTO Plot Mode with Simulation](docs/manual/en/images/ui_overview_plot.png)

---

## What is LINTO?

If you draw with a **physical pen plotter** (from vintage workhorses like the Mutoh XP-500, HP 7585B, or Roland DXY to modern DIY drawing robots) and create your artwork in **Inkscape, Illustrator, CAD, or generative Python/Processing scripts**, LINTO is the bridge to your hardware:

* **True Millimeter Layout:** Position artwork on standard paper sizes (DIN A4 to A0) or custom sheets. See real hardware margin constraints (such as asymmetric roller feed margins) or probe physical sheet boundaries directly from plotter optical sensors (`OH;`).
* **Slicer Pipeline & 2-Opt TSP:** Much like a 3D-printing slicer, LINTO merges collinear line segments, simplifies redundant nodes, and reorders vectors using a **2-Opt Traveling Salesperson Problem (TSP)** heuristic. Depending on the artwork, this can cut pen-up air travel considerably.
* **Interactive Simulation Scrubber:** Before dropping ink on expensive paper, scrub forward and backward through the entire plot timeline. Inspect pen-down strokes, travel paths (`Pen Up`), and touchdown nodes.
* **Safe Live Streaming:** Streams commands over RS-232 serial or TCP with strict **RTS/CTS hardware flow control** to prevent plotter buffer overflows. Supports pause, resume, and immediate abort (`ESC.K`, `PU;`, `SP0;`) that parks the pen safely in the carousel.

### What LINTO is Not
* **Not an inkjet printer driver:** Large-format photo printers (e.g. HP DesignJet, Epson SureColor) are raster printers. LINTO exclusively drives mechanical vector machines moving physical pens.
* **Not a vinyl cutting suite:** Focused strictly on pen plotting. Drag-knife offset compensation is on the roadmap.
* **Not an illustration tool:** You continue designing in your favorite software (Inkscape, Blender, code). LINTO handles the preparation, slicing, and machine execution.

---

## Core Features

* **Vector Import:** Opens SVG (`.svg`) and HP-GL (`.hpgl`, `.plt`) files via drag & drop or file dialog.
* **Pen Palette & Color Clustering:** Automatically clusters stroke colors to 8 logical pens using perceptual Delta-E in CIE-Lab color space. Configurable pen speed (`VS` in cm/s) and force (`FS` in grams).
* **Precise Transformation:** Numerical positioning (sheet or plottable area reference), proportional scaling with zoom presets, 1:1 original size, margin-aware fitting, free rotation, and flipping.
* **Layers & Z-Order:** Reorder drawing sequence via drag & drop, lock layers against accidental edits, or toggle visibility.
* **Multi-Plotter Support:** Modular YAML profiles (`src/linto/resources/devices/*.yaml`). Ships with 26 profiles: Mutoh XP-500, Generic Flatbed, and **24 profiles adapted from InkCut** (Roland, Graphtec, Summa, US Cutter, etc.). Only the Mutoh XP-500 has been verified on real hardware so far.
* **Hardware Diagnostics & Emulator:** Standalone terminal probing tool (`tools/xp500_probe.py`), calibration pattern (`src/linto/resources/calibration_plot_a3.svg`), and a complete software emulator (`VirtualPlotter`) for instant headless testing without hardware.

---

## Installation

**Requirements:** Python 3.11 or newer, Linux (macOS and Windows may work but are untested). For live plotting: a plotter speaking HP-GL connected via RS-232 (USB serial adapter) or TCP.

```bash
python3 -m venv ~/.venvs/linto
source ~/.venvs/linto/bin/activate
pip install git+https://github.com/colorcube/linto.git

linto
```

Or from a local checkout (see [Developer Setup](#developer-setup) for an editable install):

```bash
git clone https://github.com/colorcube/linto.git
cd linto
python3 -m venv .venv
.venv/bin/pip install .
.venv/bin/linto
```

On Linux, your user needs access to the serial port: membership in the `dialout` group (Debian, Ubuntu, Fedora, openSUSE) or `uucp` (Arch, Manjaro), e.g. `sudo usermod -aG dialout $USER`, then log in again. See the [hardware setup guide](docs/manual/en/4-hardware-setup-and-diagnostics.md) for details.

---

## Quickstart: First Plot in 5 Steps

You don't need hardware connected to try LINTO—the built-in emulator lets you explore immediately:

```
[ 1. Connect ] -> [ 2. Page Setup ] -> [ 3. Import Vector ] -> [ 4. Simulate ] -> [ 5. Plot ]
```

1. **Connect plotter or launch emulator:**
   * *With hardware:* Connect your plotter via RS-232 null-modem cable.
   * *Without hardware:* Launch the emulator in a second terminal with `python3 -m linto.emulator --tcp 9999` and select `Mutoh XP-500 Simulator (TCP)` in the top toolbar.
2. **Configure sheet and margin profile:**
   * Click **[ Page Setup... ]**, choose your format (e.g. `DIN A3 Landscape`) and margin profile (e.g. `EXP`). Click **[ Query Plotter ]** to read sensor boundaries automatically.
3. **Import and place vector artwork:**
   * Drag and drop an `.svg` or `.hpgl` file into the window — sample files are in [`examples/`](examples/).
   * Use **[ Fit to Sheet ]** or **[ Center ]** in the *Transform* dock.
4. **Simulate the plot:**
   * Switch to the **Output** tab at the top.
   * Scrub the simulation slider or press Play to review pen travel and sequence before drawing.
5. **Plot or export:**
   * Click **[ Send Plot ]** for live streaming, or export an optimized file via **[ Export Plot File (.hpgl)... ]**.

---

## Documentation

Online manual: **[English](https://colorcube.github.io/linto/manual/)** | **[Deutsch](https://colorcube.github.io/linto/handbuch/)**

* **English:** [Documentation Overview](docs/README.md) | [User Manual (`docs/manual/en/`)](docs/manual/en/README.md)
* **Deutsch:** [Dokumentations-Übersicht](docs/README.de.md) | [Benutzerhandbuch (`docs/manual/de/`)](docs/manual/de/README.md)


### Building & Previewing the HTML Manuals (Zensical)

The Markdown sources in `docs/manual/` are built into two standalone, offline-capable HTML manuals (German and English) using **[Zensical](https://zensical.org/)**. Pressing `F1` (or *Help → User Guide*) inside LINTO automatically opens the offline HTML manual matching the active UI language:

```bash
# Build both offline HTML manuals (outputs to site/manual/ and site/handbuch/):
zensical build --clean
zensical build --clean -f zensical.de.toml

# Local live preview server – English manual (http://localhost:8000/):
zensical serve

# Local live preview server – German manual (http://localhost:8000/):
zensical serve -f zensical.de.toml
```

---

## Developer Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Launch LINTO
linto

# Run test suite (headless, no display or hardware needed)
QT_QPA_PLATFORM=offscreen pytest
```

### Project Layout

| Path | Contents |
|---|---|
| `src/linto/core/` | Document model, geometry, SVG/HP-GL import, SVG export, fonts |
| `src/linto/pipeline/` | Slicer pipeline: clipping, merging, simplification, path sorting, HP-GL compiler |
| `src/linto/device/` | Device profiles, serial/TCP transport, streaming with flow control, plotter probing |
| `src/linto/emulator/` | Software plotter emulator (PTY or TCP) for testing without hardware |
| `src/linto/gui/` | PySide6 user interface |
| `src/linto/resources/` | Device profiles (YAML), translations, calibration plots |
| `tools/` | Helper scripts (calibration plot generator, InkCut profile importer, XP-500 probe) |
| `docs/` | User manuals (EN/DE) and device documentation |

---

## Contributing

Bug reports, device test reports and pull requests are welcome. When reporting a problem with a plotter, please include the plotter model, connection type (serial adapter / TCP), the device profile used, and if possible the exported `.hpgl` file. Testing one of the InkCut-derived profiles on real hardware is especially helpful.

Please run the test suite before submitting a pull request.

---

## Related Projects & Credits

* **[InkCut](https://github.com/inkcut/inkcut) (GPL-3.0-or-later):** 24 device profiles (Roland, Graphtec, Summa, US Cutter) adapted via `tools/import_inkcut_devices.py`, and inspiration for device abstraction.
* **[vpype](https://github.com/abey79/vpype) (Antoine Beyeler, GPL-3.0-or-later):** Conceptual inspiration for the modular slicer pipeline and path optimization heuristics.
* **[MutohPlot](https://github.com/oliver321/MutohPlot) (Oliver F., MIT License):** The HP-GL tokenizer, parser and 5×7 `LB` label stroke font in `core/hpgl_import.py` are adapted from MutohPlot (MIT license notice in the file header). Also a valuable reference for Mutoh XP-500 hard-clip margins and SVG `<text>` diagnostic warnings.
* **Hershey Vector Fonts (A. V. Hershey, 1967, Public Domain):** Basis for the integrated **Hershey Simplex** single-line vector font used to render SVG `<text>` elements directly for pen plotters.

---

## License

Copyright © 2026 René Fritz.

Licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [LICENSE](LICENSE).

Portions adapted from MutohPlot are licensed under the MIT License; see the header of `src/linto/core/hpgl_import.py`.

---

## Built with AI Collaboration

This project was built through pair-programming between a human developer and autonomous AI coding agents.
