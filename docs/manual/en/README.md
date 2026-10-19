# Plotter Studio

Plotter Studio is a specialized **slicer and workspace for vector pen plotters**. It bridges the gap between vector graphics software (such as Inkscape, Illustrator, CAD, or generative art code from Python/Processing) and the physical mechanics of drawing machines.

In other words: Plotter Studio lets you bring your drawings to paper at the exact right size using a pen plotter.

Plotter Studio was developed and tested on **Linux**, but should also run on **macOS** and **Windows** (untested).

![Plotter Studio – User Interface](images/ui_overview_layout.png)

> [!NOTE]
> Currently, only HP-GL plotters are supported. However, support for controlling other plotters can be integrated, as the internal data format is not tied to HP-GL.

---

## What can Plotter Studio do?
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

## What is not yet supported or planned?
* **Vinyl cutter drag-knife offset compensation:** Blade cutting is not yet supported; current focus is on pen plotting.
* **Direct DXF import:** Currently, CAD drawings in DXF format should be converted to SVG (e.g. via Inkscape or QCAD) first.
* **G-Code plotters (Marlin / Grbl):** Supporting G-code-based plotters or 3D printers with pen mounts is on the to-do list; currently, only HP-GL / MH-GL plotters are supported.

## What is it not?
* **Not a large-format inkjet printer driver:** Large-format office printers (e.g. HP DesignJet, Epson SureColor, Canon imagePROGRAF) are colloquially called "plotters", but they are raster-based pixel printers. Plotter Studio exclusively controls true **vector pen plotters** that move physical pens across paper.
* **Not cutting plotter software (vinyl cutters):** Plotter Studio is designed for **pen plotters**. Pure vinyl cutters with drag-knife blades are not yet supported because drag-knife offset compensation is missing (though many vinyl cutters can be used as pen plotters with a pen holder).
* **Not a vector drawing application:** Plotter Studio does not replace Inkscape or Illustrator. You create your artwork, CAD plans, or algorithms in your preferred tool and export them as standard SVG. Plotter Studio handles sheet layout, scaling, path optimization, and plotting.
