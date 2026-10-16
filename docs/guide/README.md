# Plotter Studio – User Guide

Welcome to the official user guide for **Plotter Studio**. This guide covers everything from getting started and typical workflows to detailed tool usage, hardware setup, calibration, and mathematical background.

---

## Overview: Is Plotter Studio Right for You?

### What is Plotter Studio?
Plotter Studio is a specialized **slicer and workspace for vector pen plotters**. It bridges the gap between vector graphics software (such as Inkscape, Illustrator, CAD, or generative art code from Python/Processing) and the physical mechanics of drawing machines.

### What is it not?
* **Not a large-format inkjet printer driver:** Large-format office printers (e.g. HP DesignJet, Epson SureColor, Canon imagePROGRAF) are colloquially called "plotters", but they are raster-based pixel printers. Plotter Studio exclusively controls true **vector pen plotters** that move physical pens across paper.
* **Not cutting plotter software (vinyl cutters):** Plotter Studio is designed for **pen plotters**. Pure vinyl cutters with drag-knife blades are not yet supported because drag-knife offset compensation is still under development (though many vinyl cutters can be used as pen plotters with a pen holder).
* **Not a vector drawing application:** Plotter Studio does not replace Inkscape or Illustrator. You create your artwork, CAD plans, or algorithms in your preferred tool and export them as standard SVG. Plotter Studio handles sheet layout, scaling, path optimization, and plotting.

### What can Plotter Studio do today?
* Load, place, numerically scale (50%, 100%, 200%, aspect ratio lock), rotate (90° steps or free angles), and center SVG and HP-GL/PLT files on the sheet.
* Support margin profiles for grit-roller and flatbed plotters (e.g., EXP, NORM with asymmetric leading edge) and query paper dimensions via `OH;`.
* Automatic color clustering onto up to 8 pens (SVG) or direct assignment of pen numbers `SP1`–`SP8` and `LB` text labels (HP-GL).
* Multi-object management with Z-order (draw sequence), visibility, and editing locks.
* Smart slicer pipeline: path merging, direction optimization (reversing), micro-vertex simplification (Ramer-Douglas-Peucker), and 2-Opt TSP path optimization (40–70% fewer pen-up travel moves).
* Interactive simulation with timeline scrubber, variable playback speed (1x–10x), and pen-up travel move visualization.
* Pre-flight inspection with exact draw distance, air distance, and estimated runtime.
* Pen filtering to selectively plot individual colors (ideal for manual pen swaps).
* Live streaming over RS-232 or TCP with strict **RTS/CTS hardware handshaking** (preventing buffer overflows) and optional auto-pause on pen changes.
* Safe emergency abort (`ESC.K`, `PU;`, `SP0;`) protecting paper and pen tips.
* Open multi-plotter architecture (Center-Origin & Bottom-Left) via YAML profiles with 26 built-in models: including Mutoh XP-500, Generic Flatbed, and **24 device profiles imported from InkCut** (Roland, Graphtec, US Cutter, Summa, Sekonic, etc.) plus the converter tool `tools/import_inkcut_devices.py`.
* Hardware diagnostic tool (`tools/xp500_probe.py`), calibration patterns (`resources/calibration_plot_a3.svg`), and built-in software emulator (`VirtualPlotter`).

### What is not yet supported or planned?
* **Vinyl cutter drag-knife offset compensation:** Blade cutting is not yet supported; current focus is on pen plotting.
* **Direct DXF import:** Currently, CAD drawings in DXF format should be converted to SVG (e.g. via Inkscape or QCAD) first.
* **G-Code plotters (Marlin / Grbl):** Generating CNC G-code for 3D printers with pen mounts is planned; current drivers target HP-GL / MH-GL machines.

---

## Table of Contents

1. **[1. Quickstart & Typical Workflow](1-quickstart-and-workflow.md)**
   * Getting started with or without hardware (using the virtual emulator)
   * The 5-step workflow from SVG to finished plot
2. **[2. Layout Mode & Object Management](2-layout-and-objects.md)**
   * User interface, canvas, millimeter rulers, and hard-clip limits
   * Page setup (DIN A4–A0, margin profiles EXP/NORM, optical paper query `OH;`)
   * Vector import (SVG & HP-GL/PLT) & automatic color clustering
   * Docks: *Objects & Layers* (Z-order, visibility, locks), *Transform* (aspect lock, presets, rotate, free angle), and *Pens*
3. **[3. Output Mode, Simulation & Export](3-output-simulation-export.md)**
   * Optimization pipeline (Merge, Reverse, RDP, 2-Opt TSP path optimization)
   * Pre-flight statistics (draw distance, travel savings, pen swaps, runtime)
   * Simulation with the scrubber (timeline, 1x–10x speed, pen-up visualization)
   * Selective plotting (pen filter) for manual pen swaps or dry runs
   * Live streaming, pause, and safe emergency abort (`ESC.K`, `PU;`, `SP0;`)
   * File export to HP-GL (`.hpgl`) and Plot SVG (`.svg`)
4. **[4. Hardware Setup, Calibration & Diagnostics](4-hardware-setup-and-diagnostics.md)**
   * RS-232 null-modem cabling with hardware handshaking (RTS/CTS), FTDI adapters, and TCP
   * Control panel setup (19200 baud, 8N1, HP-7585B emulation, EXP margins)
   * Hardware probe tool `tools/xp500_probe.py` (CTS, DSR, `OI`, `OF`, `OH`, `OE`, `OS`, ESC sequences)
   * Official calibration plot (`resources/calibration_plot_a3.svg`): measuring with a steel ruler, backlash check, margin verification, and 8-pen matrix
   * Adding custom plotters (device dialog and custom YAML profiles)
5. **[5. Vector Formats, Sources & Workflows](5-vector-formats-and-workflows.md)**
   * Custom scripts (generating SVGs, `mm` units, 8 standard pen colors)
   * Inkscape as universal converter, Hershey single-line fonts & centerline tracing
   * Blender (3D scenes to 2D SVG using Freestyle & Grease Pencil Line Art)
   * HP-GL (`.hpgl` / `.plt`) direct import & external converters (`vpype`, `hp2xx`)
   * DXF (CAD drawings and layer considerations)
6. **[6. Concepts, Algorithms & Architecture (Deep Dive)](6-concepts-and-architecture.md)**
   * Technical and mathematical foundations for developers and power users
   * Details on 2-Opt TSP, Ramer-Douglas-Peucker, coordinate transforms, and streaming architecture
7. **[7. Recommended Resources, Tools & Community](7-resources-tools-and-community.md)**
   * Curated collections & community hubs: Awesome Plotters, Drawingbots.net & Discord, Reddit r/PlotterArt
   * Specialized vector tools: vpype, vsketch, Turtletoy, ln (3D Line Art)
   * Single-line fonts (Single-Stroke / Hershey Fonts)
