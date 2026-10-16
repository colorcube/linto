# 5. Vector Formats, Sources & Workflows

A pen plotter does not render pixel grids—it drives mathematical vector paths using physical pens. Whether you create artwork with code (Python, Processing), 3D applications like Blender, vector editors like Inkscape, or CAD systems, here are the best practices for generating clean data for Plotter Studio.

---

## 1. Custom Scripts (Generating Clean SVGs)

For generative art (Plotter Art) created via Python, JavaScript, or Processing, **SVG** is the ideal format. Following four simple guidelines ensures that your dimensions and pen assignments import 1:1 without manual tweaking:

1. **Keep Millimeters (`mm`) and `viewBox` in Sync:**
   Set `width` and `height` explicitly in `mm` and reuse the exact numbers in the `viewBox`. Then `1.0` in your script's coordinate space corresponds to exactly **1 millimeter** on paper:
   ```xml
   <svg xmlns="http://www.w3.org/2000/svg"
        width="420mm" height="297mm"
        viewBox="0 0 420 297">
     <!-- 1 unit = 1 mm on a DIN A3 landscape sheet -->
   </svg>
   ```
   *(Without explicit units, SVG defaults to pixels at 96 DPI, where `1 px ≈ 0.2646 mm`.)*

2. **Pen Mapping via Stroke Color (`stroke`):**
   Plotter Studio maps paths to pens 1–8 based on their `stroke` hex color. If your script uses the 8 default hex colors, every path will land reliably on the intended pen:
   
   | Pen | Default Color | Hex Code | Recommended Use |
   |---|---|---|---|
   | **Pen 1** | Black | `#000000` | Outlines, text labels |
   | **Pen 2** | Red | `#d32f2f` | Highlights, dimensions |
   | **Pen 3** | Blue | `#1976d2` | Guidelines, hatching |
   | **Pen 4** | Green | `#388e3c` | Secondary geometry |
   | **Pen 5** | Orange | `#f57c00` | Fill shading |
   | **Pen 6** | Magenta | `#7b1fa2` | Fine accents |
   | **Pen 7** | Cyan | `#0097a7` | Draft paths |
   | **Pen 8** | Yellow | `#fbc02d` | Markers, highlights |

   ```xml
   <!-- Lands automatically on Pen 1 (Black) -->
   <path d="M 10,10 L 100,10 L 100,100 Z" fill="none" stroke="#000000" stroke-width="0.35" />

   <!-- Lands automatically on Pen 2 (Red) -->
   <circle cx="55" cy="55" r="30" fill="none" stroke="#d32f2f" stroke-width="0.35" />
   ```
   If custom colors are used, automatic color clustering maps up to 8 distinct hues to the nearest available pen.

3. **Always Set `fill="none"`:**
   Pen plotters only draw stroke lines, not solid fills. Setting `fill="none"` ensures that what you see in your web browser or SVG preview matches what the pen will physically draw.

4. **Supported SVG Elements:**
   You can freely mix `<path>`, `<line>`, `<polyline>`, `<polygon>`, `<rect>`, `<circle>`, `<ellipse>`, and nested `<g transform="...">` groups. Curves (`C`, `Q`, `A`) are parsed losslessly.

---

## 2. Inkscape as a Universal Pre-Converter

**Inkscape** is the "Swiss Army knife" for plotter preparation. Virtually any third-party vector format can be inspected, cleaned, and exported as SVG:

* **Vector & Print Formats:** `.pdf`, `.eps`, `.ps` (note: PDF text fonts often import as double-line outlines), Adobe Illustrator (`.ai`), CorelDRAW (`.cdr`), Visio (`.vsd`/`.vsdx`), `.wmf`/`.emf`.
* **CAD Formats:** `.dxf` (AutoCAD R12/R14/2000+) and `.hpgl`/`.plt`.
* **Single-Line Fonts (Hershey Text):**
  Standard fonts (TrueType/OpenType) consist of closed outline contours (e.g. an "I" is drawn as a narrow rectangle). Inkscape provides true **single-line fonts** for plotters under `Extensions → Text → Hershey Text`.
* **Bitmap Vectorization (Centerline Tracing):**
  Via `Path → Trace Bitmap`, Inkscape offers **Centerline Tracing (Autotrace)**. Unlike outline tracing (which traces both sides of a black line), centerline tracing creates a single clean centerline for the pen.

---

## 3. Blender (Exporting 3D Scenes as 2D SVG)

Blender is well-suited for 3D generative art, architectural wireframes, and perspective line drawings with automatic **Hidden Line Removal** (hidden edges on the back side of meshes are cleanly omitted):

1. **Freestyle SVG Exporter (Built-in Add-on):**
   * Enable the **Freestyle SVG Exporter** under `Edit → Preferences → Add-ons`.
   * Check **Freestyle** and **Freestyle SVG Export** in *Render Properties*.
   * Press `F12` to render: Blender writes a clean `.svg` file containing all visible camera edges.
2. **Grease Pencil + Line Art Modifier (Blender 3.x / 4.x, fast):**
   * Add `Grease Pencil → Scene Line Art` to the scene (calculates silhouettes, creases, and intersections in real time).
   * Export directly via `File → Export → Grease Pencil as SVG (.svg)`.

---

## 4. HP-GL (`.hpgl` / `.plt`)

**HP-GL** (*Hewlett-Packard Graphics Language*) is an industry-standard machine control language (`PU` = Pen Up, `PD` = Pen Down, `SP` = Select Pen) with a fixed coordinate step of `1 unit = 0.025 mm`.

* **Direct Import in Plotter Studio:**
  Load existing `.hpgl` and `.plt` files directly via `File → Import` (`Ctrl+I`), `File → Open Project` (`Ctrl+O`), or drag-and-drop.
* **Supported Commands:**
  In addition to absolute/relative moves (`PA`, `PR`, `PU`, `PD`) and pen changes (`SP1`–`SP8`), the parser supports geometric primitives (`CI` circles, `AA`/`AR` arcs, `EA`/`RA` rectangles) and **`LB` text labels** (including sizing `SI`, direction `DI`/`DR`, slant `SL`, and character plot `CP`) via an integrated 5×7 vector font.
* **Accuracy & External Converters:**
  Curves in HP-GL files are broken into short linear segments. If you need to convert old HP-GL files outside Plotter Studio, tools like **Inkscape**, **`vpype`** (with `vpype-hpgl`), or the classic CLI utility **`hp2xx`** (`hp2xx -m svg input.hpgl -f output.svg`) work well.

---

## 5. DXF (CAD Drawings)

**DXF** (*Drawing Exchange Format*) is the standard 2D exchange format in CAD, architecture, and CNC/laser cutting (AutoCAD, FreeCAD, QCAD, LibreCAD, Rhino, Fusion 360).

* **Plotter Considerations:**
  CAD drawings often organize geometry across layers or ACI color numbers and may contain disconnected line fragments or dimension blocks.
* **Recommended Workflow:**
  Export drawings directly as **SVG** from your CAD software (e.g. in QCAD or FreeCAD TechDraw) or open the `.dxf` in **Inkscape** (keep scaling factor at `1.0` for millimeters) and save as `.svg` for Plotter Studio.

---

> [!TIP]
> For advanced toolchains (e.g. `vpype`, `vsketch`, `ln`), single-line fonts, and community hubs (**Awesome Plotters**, Drawingbots.net, Reddit), see **[Chapter 7: Recommended Resources, Tools & Community](7-resources-tools-and-community.md)**.
