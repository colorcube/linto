# 7. Concepts, Algorithms & Architecture (Deep Dive)

This chapter provides a detailed technical insight into the mathematical and machine-level mechanics of LINTO: how the slicer operates, how algorithms like 2-Opt TSP and Ramer-Douglas-Peucker work, how coordinates are transformed, and how the multi-plotter architecture is structured.

---

## 1. Why Standard Printer Drivers or Inkscape Aren't Enough

Inkjet and laser printers rasterize documents into a grid of microscopic ink dots. Pen plotters, by contrast, are **kinematic vector machines**: they drive a physical pen (fineliner, ballpoint, technical pen, or brush) with stepper motors across paper or film.

This introduces fundamental challenges that standard printing systems cannot handle:

1. **Path Sequencing & Air Travel Distance:**
   In SVG or CAD files, paths are stored in order of creation or grouping. If streamed directly to a plotter, the toolhead jumps back and forth across the sheet thousands of times. The result is excessive plot times, unnecessary mechanical wear, and ink bleeding from repeated pen touchdowns.
2. **Physical Pen Tip Wear & Speed:**
   Every pen-down event puts stress on the nib and ink feed. Continuous strokes must be maintained without constant lifting and dropping.
3. **Buffer Overflows & Serial Stalls:**
   Vintage plotters use serial RS-232 connections and small hardware buffers (often only 1 KB to 64 KB). Sending a multi-megabyte plot file at full wire speed crashes the controller or drops vectors.
4. **Coordinate Transformation & Asymmetric Margins:**
   Standard vector formats use an origin at the top-left (0, 0), with positive coordinates running right and down. Plotters often use **Center-Origin** (0,0 in the middle of the sheet) or **Bottom-Left** (0,0 at the bottom-left corner) in proprietary plotter steps (e.g. 40 units/mm). Grit-roller plotters also require wider margins along the leading feed edge for pinch rollers.

---

## 2. The Plotter Slicer: Pipeline Architecture

LINTO acts as a **slicer** for pen plotters, translating vector geometries through a multi-stage pipeline into optimized machine paths:

```
[ SVG / Vector Input ]
        │
        ▼
1. Import & Color Clustering (Map to 1–8 physical pens)
        │
        ▼
2. Segment Merge & Reversal (Join open ends & optimize draw direction)
        │
        ▼
3. RDP Simplification (Douglas-Peucker to filter redundant vertices)
        │
        ▼
4. 2-Opt Path Optimization (Minimize rapid pen-up air moves)
        │
        ▼
5. Coordinate Transformation (Sheet mm -> Plotter Units with margin offsets)
        │
        ▼
[ Live Streaming via RTS/CTS Handshake or HP-GL Export ]
```

### Optimization Stages:

* **Color Clustering:** Graphical elements with distinct RGB stroke colors are automatically grouped onto the active pen channels (1 through 8). Paths sharing a pen are batched to keep tool swaps to an absolute minimum.
* **Line Merging:** When two endpoints meet within a configurable tolerance (e.g. 0.1 mm), LINTO joins them into a continuous polyline. The pen stays down on the paper instead of lifting.
* **Path Reversal:** Polylines can be drawn in either direction. The pipeline reverses paths when the end of a stroke is closer to the start of the next stroke than its beginning.
* **RDP Simplification (Ramer-Douglas-Peucker):** CAD tools and freehand vector curves often generate thousands of collinear micro-vertices. The RDP algorithm prunes redundant nodes without altering visual contours, preventing stepper motor jitter.
* **2-Opt Path Optimization (Traveling Salesperson Problem):** A heuristic permutation algorithm rearranges path ordering to minimize total rapid travel distance (`Pen Up`), often reducing air travel by **40% to 70%**.

---

## 3. Coordinate Systems & Origins

In LINTO, you always work in intuitive **sheet coordinates**:
* Unit: Millimeters (mm).
* Origin: Top-left corner of the paper sheet.
* X-axis extends to the right, Y-axis extends downwards.

For hardware output, LINTO converts these coordinates into the target machine's native coordinate space:

### Center-Origin vs. Bottom-Left

```
     Bottom-Left (e.g. Roland, Generic HP-GL)        Center-Origin (e.g. Mutoh XP-500)
    ┌───────────────────────────┐               ┌───────────────────────────┐
    │                           │               │             ▲ +Y          │
    │                           │               │             │             │
    │                           │               │       -X ───┼───► +X      │
    │                           │               │           (0,0)           │
    │(0,0)                      │               │             │             │
    └───────────────────────────┘               └───────────────────────────┘
```

1. **Center-Origin:**
   Machines like the **Mutoh XP-500** (and many large-format drafting plotters) place (0, 0) at the exact center of the hard-clip printable area. Coordinates are both positive and negative.
2. **Bottom-Left:**
   Flatbed and desktop plotters (like Roland DXY or HP 7475A) place (0, 0) at the lower-left corner with strictly positive coordinates.

### Margin Profiles & Asymmetric Roll Margins
Grit-roller plotters need extra clearance along the leading edge for the paper sensor and pinch rollers. On the Mutoh XP-500, the margin profiles include:

| Profile | Feed Edge (Leading) | Trailing Edge | Left | Right | Intended Use |
|---|---|---|---|---|---|
| **EXP** (Expanded) | 25.0 mm | 5.0 mm | 5.0 mm | 5.0 mm | Maximum drawing area (Default) |
| **NORM** (Normal) | 35.0 mm | 15.0 mm | 15.0 mm | 15.0 mm | Generous safety borders |
| **TYPE1** | 25.0 mm | 5.0 mm | 11.0 mm | 11.0 mm | Roll paper with side margins |
| **TYPE3** | 25.0 mm | 10.0 mm | 10.0 mm | 10.0 mm | Alternative for continuous rolls |

LINTO renders these margins on the canvas as a dotted outline and warns you of any clipping.

---

## 4. Hardware Interface & Streaming Safety

Communication with physical plotters uses RS-232 serial interfaces (or USB-to-serial adapters) or TCP network sockets.

### Flow Control
LINTO relies on strict **hardware handshaking (RTS/CTS)**:
* The plotter toggles its CTS line (Clear to Send) to indicate when internal buffer space is available.
* The `SerialStreamer` thread waits atomically on CTS before transmitting chunks of data, preventing buffer overflows and corrupted drawings.

### Emergency Stop & Safe Abort
When a plot is canceled from the user interface:
1. LINTO transmits `\x1b.K` (Clear Device Buffer) to flush the plotter's hardware buffer.
2. The pen is immediately raised (`PU;`).
3. The pen is safely parked into the carousel (`SP0;`) to prevent nib drying and paper damage.

---

## 5. Multi-Plotter Architecture

LINTO is modular by design. While the **Mutoh XP-500** serves as the reference large-format plotter, the architecture supports any HP-GL machine.

### Declarative Device Profiles (`resources/devices/*.yaml`)
Every device is defined by a concise YAML specification:

```yaml
model_id: "hpgl_generic"
name: "Generic HP-GL Plotter (Flatbed)"
manufacturer: "Generic / HP"
emulation: "HP-GL"
protocol: "hpgl"
origin: "bottom_left"         # "center" or "bottom_left"
units_per_mm: 40.0            # 40 units/mm = 0.025 mm step
max_pens: 8                   # Carousel pen count
swap_xy: false                # Swap axes if needed
invert_x: false               # Invert X axis
invert_y: false               # Invert Y axis
rotation_deg: 0               # Rotation (0, 90, 180, 270)

connection:
  baudrate: 9600
  bytesize: 8
  parity: "N"
  stopbits: 1
  rtscts: true
  xonxoff: false

margins_mm:
  default:
    top: 10.0
    bottom: 10.0
    left: 10.0
    right: 10.0
```

### The `DeviceManager`
* Maintains configured plotters in `~/.config/linto/devices.yaml`.
* Enables 1-click switching between plotters in the UI (e.g. from Mutoh XP-500 roller to Roland DXY flatbed or software simulator).
* Canvas rulers, margins, and emitters adapt dynamically to the selected device profile.

---

## 6. Related Projects, Inspiration & Credits

* **InkCut (GPL-3.0-or-later):** 24 HP-GL device profiles (Roland, Graphtec, US Cutter, Summa, Sekonic, etc.) were imported and adapted (`tools/import_inkcut_devices.py`). Also served as reference for device driver abstraction.
* **vpype (Antoine Beyeler, GPL-3.0-or-later):** Conceptual inspiration for the modular slicer pipeline (line merging, RDP smoothing, and 2-Opt TSP path optimization).
* **MutohPlot (Oliver F., MIT License):** Reference for Mutoh XP-500 specifics (hard-clip window, EXP/NORM margins, axis mapping, and HP-GL parsing).
