# Plotter Studio – Documentation

> **Language / Sprache:** [English](README.md) | [Deutsch](README.de.md)

Welcome to the Plotter Studio documentation. The documentation is organized into three main areas:

---

## 1. [User Guide & Manual](guide/README.md) (`docs/guide/`)
Practical user documentation and workflow guides:
* **[1. Quickstart & Typical Workflow](guide/1-quickstart-and-workflow.md):** Getting started with physical hardware or the built-in software emulator; the 5-step workflow from SVG to finished plot.
* **[2. Layout Mode & Object Management](guide/2-layout-and-objects.md):** Importing SVG & HP-GL, page setup with hard-clip query (`OH;`), transformations (50%, 100%, 200%, aspect ratio lock, fit to sheet, center), Z-order management, and pen assignment.
* **[3. Output Mode, Simulation & Export](guide/3-output-simulation-export.md):** Pipeline tuning (Merge, Reverse, RDP, 2-Opt), pre-flight statistics, interactive timeline simulation with air-travel visualization, pen filtering, serial streaming, and HP-GL/SVG export.
* **[4. Hardware Setup, Calibration & Diagnostics](guide/4-hardware-setup-and-diagnostics.md):** RS-232 cabling with hardware handshaking (RTS/CTS), control panel configuration, hardware diagnostic tool `xp500_probe.py`, the official calibration plot (`resources/calibration_plot_a3.svg`), and integrating custom plotter models.
* **[5. Vector Formats, Sources & Workflows](guide/5-vector-formats-and-workflows.md):** Best practices for custom SVG scripts, Inkscape as universal converter, Blender (3D scenes to 2D SVG), HP-GL, and DXF.
* **[6. Concepts, Algorithms & Architecture (Deep Dive)](guide/6-concepts-and-architecture.md):** Slicer architecture, mathematical foundations of 2-Opt TSP path optimization, coordinate systems (Center-Origin vs. Bottom-Left), asymmetric roll margins, and multi-plotter driver design.
* **[7. Recommended Resources, Tools & Community](guide/7-resources-tools-and-community.md):** Curated collection of specialized software (vpype, vsketch, ln, Turtletoy), Hershey single-line fonts, and community hubs (Awesome Plotters, Drawingbots, Reddit).

---

## 2. [Device Documentation](devices/mutoh-xp500/README.md) (`docs/devices/`)
Hardware documentation, technical specifications, and protocol references:
* **[Mutoh XP-500](devices/mutoh-xp500/README.md):**
  * [Setup & Quickstart](devices/mutoh-xp500/einrichtung.md) (Control panel, RS-232, paper & rollers)
  * [Control Panel Configuration](devices/mutoh-xp500/konfiguration.md) (Transcribed from manual chapter 7)
  * [Technical Specifications](devices/mutoh-xp500/spezifikationen.md)
  * [RS-232C Interface & Handshake](devices/mutoh-xp500/schnittstelle.md)
  * [Units, Origin & Coordinates](devices/mutoh-xp500/einheiten-und-koordinaten.md)
  * [MH-GL Command Set](devices/mutoh-xp500/mhgl-befehle.md) & [Escape Sequences](devices/mutoh-xp500/escape-sequenzen.md)
  * [Software Emulator (`virtual_plotter`)](devices/mutoh-xp500/emulator.md) (PTY/TCP simulation & firmware inquiries)
  * [Hardware Test Plan](devices/mutoh-xp500/testplan.md)

---

## 3. [Project & Concept Documents](project/konzept.md) (`docs/project/`)
Architecture, system specifications, and development roadmap (German):
* **[Todo & Roadmap](project/TODO.md):** Central task backlog for upcoming features, packaging, and hardware tests.
* **[Concept v2.3](project/konzept.md):** Architecture, data model, coordinate systems, pipeline, streaming, and pen models.
* **[User Stories](project/user-stories.md):** User stories US-01 through US-10.
* **[MutohPlot Analysis](project/analyse-mutohplot.md):** Analysis of the Mutoh XP-500 reference project.
* **[InkCut Analysis](project/analyse-inkcut.md):** Analysis of drivers, protocols (DMPL, CAMM-GL, G-Code), and drag-knife filters.
