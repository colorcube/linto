# Plotter Studio

> **Language / Sprache:** [English](README.md) | [Deutsch](README.de.md)

> **The modular slicer, layout editor, and streaming controller for physical vector pen plotters.**

Plotter Studio prepares vector graphics for real pen plotters: it optimizes pen paths (saving 40% to 70% of pen-up travel time), simulates the drawing process interactively on screen, and streams commands reliably with hardware flow control directly to your machine.

---

## Visual Tour

### Layout Mode: Arrange, scale, and map vector artwork to pens
![Plotter Studio Layout Mode](docs/images/ui_overview_layout.png)

### Output Mode: Path optimization, pen-up travel visualization & simulation
![Plotter Studio Plot Mode with Simulation](docs/images/ui_overview_plot.png)

---

## What is Plotter Studio?

If you draw with a **physical pen plotter** (from vintage workhorses like the Mutoh XP-500, HP 7585B, or Roland DXY to modern DIY drawing robots) and create your artwork in **Inkscape, Illustrator, CAD, or generative Python/Processing scripts**, Plotter Studio is the bridge to your hardware:

* **True Millimeter Layout:** Position artwork on standard paper sizes (DIN A4 to A0) or custom sheets. See real hardware margin constraints (such as asymmetric roller feed margins) or probe physical sheet boundaries directly from plotter optical sensors (`OH;`).
* **Slicer Pipeline & 2-Opt TSP:** Much like a 3D-printing slicer, Plotter Studio merges collinear line segments, simplifies redundant nodes, and reorders vectors using a **2-Opt Traveling Salesperson Problem (TSP)** heuristic. This typically cuts pen-up air travel by **40% to 70%**.
* **Interactive Simulation Scrubber:** Before dropping ink on expensive paper, scrub forward and backward through the entire plot timeline. Inspect pen-down strokes, travel paths (`Pen Up`), and touchdown nodes.
* **Safe Live Streaming:** Streams commands over RS-232 serial or TCP with strict **RTS/CTS hardware flow control** to prevent plotter buffer overflows. Supports pause, resume, and immediate abort (`ESC.K`, `PU;`, `SP0;`) that parks the pen safely in the carousel.

### What Plotter Studio is Not
* **Not an inkjet printer driver:** Großformat photo printers (e.g. HP DesignJet, Epson SureColor) are raster printers. Plotter Studio exclusively drives mechanical vector machines moving physical pens.
* **Not a vinyl cutting suite:** Focused strictly on pen plotting. Drag-knife offset compensation is on the roadmap.
* **Not an illustration tool:** You continue designing in your favorite software (Inkscape, Blender, code). Plotter Studio handles the preparation, slicing, and machine execution.

---

## Core Features

* **Vector Import:** Opens SVG (`.svg`) and HP-GL (`.hpgl`, `.plt`) files via drag & drop or file dialog.
* **Pen Palette & Color Clustering:** Automatically clusters stroke colors to 8 logical pens using perceptual Delta-E in CIE-Lab color space. Configurable pen speed (`VS` in cm/s) and force (`FS` in grams).
* **Precise Transformation:** Numerical positioning (sheet or plottable area reference), proportional scaling with zoom presets, 1:1 original size, margin-aware fitting, free rotation, and flipping.
* **Layers & Z-Order:** Reorder drawing sequence via drag & drop, lock layers against accidental edits, or toggle visibility.
* **Multi-Plotter Support:** Modular YAML profiles (`resources/devices/*.yaml`). Ships with 26 profiles: Mutoh XP-500, Generic Flatbed, and **24 profiles adapted from InkCut** (Roland, Graphtec, Summa, US Cutter, Silhouette, etc.).
* **Hardware Diagnostics & Emulator:** Standalone terminal probing tool (`tools/xp500_probe.py`), calibration pattern (`resources/calibration_plot_a3.svg`), and a complete software emulator (`VirtualPlotter`) for instant headless testing without hardware.

---

## Quickstart: First Plot in 5 Steps

You don't need hardware connected to try Plotter Studio—the built-in emulator lets you explore immediately:

```
[ 1. Connect ] -> [ 2. Page Setup ] -> [ 3. Import Vector ] -> [ 4. Simulate ] -> [ 5. Plot ]
```

1. **Connect plotter or launch emulator:**
   * *With hardware:* Connect your plotter via RS-232 null-modem cable (see [Chapter 4: Hardware Setup](docs/anleitung/4-hardware-setup-und-test.md)).
   * *Without hardware:* Launch the emulator in a terminal with `python3 -m plotter_studio.emulator --tcp 9999` and select `Mutoh XP-500 Simulator (TCP)` in the top toolbar.
2. **Configure sheet and margin profile:**
   * Click **[ Page Setup... ]**, choose your format (e.g. `DIN A3 Landscape`) and margin profile (e.g. `EXP`). Click **[ Query Plotter ]** to read sensor boundaries automatically.
3. **Import and place vector artwork:**
   * Drag and drop an `.svg` or `.hpgl` file into the window.
   * Use **[ Fit to Sheet ]** or **[ Center ]** in the *Transform* dock.
4. **Simulate the plot:**
   * Switch to the **Output** tab at the top.
   * Scrub the simulation slider or press Play to review pen travel and sequence before drawing.
5. **Plot or export:**
   * Click **[ Send Plot ]** for live streaming, or export an optimized file via **[ Export Plot File (.hpgl)... ]**.

---

## Documentation

Comprehensive documentation is available in the [`docs/guide/`](docs/guide/README.md) directory:

* **[1. Quickstart & Workflow](docs/guide/1-quickstart-and-workflow.md):** Step-by-step guide with hardware or emulator.
* **[2. Layout Mode & Object Management](docs/guide/2-layout-and-objects.md):** Canvas navigation, rulers, page setup, Z-order, and pen docks.
* **[3. Output Mode, Simulation & Streaming](docs/guide/3-output-simulation-export.md):** Pipeline tuning, pre-flight stats, simulation scrubber, and serial streaming.
* **[4. Hardware Setup, Calibration & Diagnostics](docs/guide/4-hardware-setup-and-diagnostics.md):** RS-232 null-modem pinout (RTS/CTS), FTDI adapters, diagnostic probe, and calibration sheet.
* **[5. Vector Formats, Sources & Workflows](docs/guide/5-vector-formats-and-workflows.md):** Custom SVG scripts (mm units, pen color codes), Inkscape, Blender, HP-GL, and DXF.
* **[6. Technical Concepts & Architecture](docs/guide/6-concepts-and-architecture.md):** Deep-dive into slicer math, 2-Opt TSP, coordinate transformations, and streaming.
* **[7. Recommended Resources, Tools & Community](docs/guide/7-resources-tools-and-community.md):** Curated tools (vpype, vsketch, ln, Turtletoy), single-line Hershey fonts, and communities.
* **[Mutoh XP-500 Device Reference](docs/devices/mutoh-xp500/README.md):** Manual transcription, MH-GL command set, escape sequences, and DIP registers.

---

## Developer Setup

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Launch Plotter Studio
plotter-studio

# Run test suite (107 tests)
pytest
```

---

## Related Projects & Credits

* **[InkCut](https://github.com/codelv/inkcut) (GPL-3.0-or-later):** 24 device profiles (Roland, Graphtec, Summa, US Cutter) adapted via `tools/import_inkcut_devices.py`, and inspiration for device abstraction.
* **[vpype](https://github.com/abey79/vpype) (Antoine Beyeler, GPL-3.0-or-later):** Conceptual inspiration for the modular slicer pipeline and path optimization heuristics.
* **[MutohPlot](https://github.com/oliver321/MutohPlot) (Oliver F., MIT License):** Valuable reference for Mutoh XP-500 hard-clip margins, HP-GL tokenizer, and 5×7 stroke font.

---

## License

Licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [LICENSE.txt](LICENSE.txt).

---

## Built with AI Collaboration

This project was built through pair-programming between a human developer and autonomous AI coding agents.
