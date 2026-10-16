# 1. Quickstart & Typical Workflow

This guide takes you step by step from an existing vector file (SVG) to a finished pen drawing on paper.

> **Tip: You can try Plotter Studio right away without physical hardware!**  
> Plotter Studio includes a built-in virtual software plotter (`VirtualPlotter`) that fully emulates the serial interface and firmware commands over your local network.

---

## Getting Started: With or Without Hardware?

### Option A: With a Connected Plotter
1. Connect your plotter to your PC using a serial null-modem cable (RS-232 with RTS/CTS) or a quality USB-to-serial adapter.
2. Power on the plotter and load a sheet of paper.
3. Select your plotter model from the top toolbar (over 25 device profiles for Mutoh, Roland, Graphtec, US Cutter, Secabo, etc. are included).
4. See [Chapter 4: Hardware Setup & Diagnostics](4-hardware-setup-and-diagnostics.md) for detailed cabling information.

### Option B: Quick Test with the Software Simulator
If you do not have hardware set up yet:
1. Open a terminal and start the built-in emulator (e.g. with realistic drawing-time simulation):
   ```bash
   python3 -m plotter_studio.emulator --tcp 9999 --realtime
   ```
2. In the top toolbar of Plotter Studio, select **Mutoh XP-500 Simulator (TCP)** as your active device.
3. **Flow Control (Handshake):** Because virtual pseudoterminals (PTY) and TCP sockets lack physical hardware handshake pins (RTS/CTS), the emulator uses **software handshaking (`XON / XOFF`)**. The *Mutoh XP-500 Simulator (TCP)* profile comes preconfigured for this out of the box. If you create a custom profile for the emulator, always set flow control to **Software (XON / XOFF)**.

---

## The 5-Step Workflow

```
[ 1. Set Sheet ] -> [ 2. Import & Scale SVG ] -> [ 3. Check Pens ] -> [ 4. Simulate ] -> [ 5. Plot ]
```

---

### Step 1: Set Sheet Size & Margin Profile

Click **[ Page Setup... ]** in the top toolbar:

1. **Select Format:** For example, choose **DIN A3** and **Landscape**.
2. **Margin Profile:** Keep the default **EXP** (Expanded – maximum printable area).
3. **Live Query (optional):** If a physical plotter is connected, click **[ Query Plotter ]**. Plotter Studio uses the `OH;` command to query the exact sheet dimensions directly from the machine's optical sensors.
4. Click **OK**. The canvas now displays the sheet with the red dashed *hard-clip boundary*.

*(Details: [Chapter 2: Layout & Object Management](2-layout-and-objects.md#2-sheet--page-setup))*

---

### Step 2: Import & Align Vector Graphics

1. Drag and drop any `.svg` or `.hpgl` file directly from your file manager onto the canvas (or press `Ctrl+O` / `Ctrl+I`).
2. The artwork is loaded. During import, Plotter Studio analyzes all stroke colors and assigns them automatically to pens 1 through 8.
3. Open the **Transform** dock on the right:
   * In the *Placement* group, click **[ Center ]** (crosshair icon) to center the artwork on the sheet.
   * In the *Scale* group, click **[ Fit to Sheet ]** to enlarge the artwork to fit the printable area (you can set the desired margin in millimeters right next to it).
   * Use the **[ + ]** and **[ - ]** buttons (10% increments), the **Zoom** input field, or **[ Original ]** (1:1) to quickly adjust the size.
   * The lock icon ensures the aspect ratio stays proportional during scaling.

*(Details: [Chapter 2: Transform & Object Management](2-layout-and-objects.md#5-transform-dock))*

---

### Step 3: Check Pens & Colors

1. Check the bottom pen toolbar or the **Pens & Colors** dock to see which colors have been assigned to which tools (Pens 1 to 8).
2. If you want to draw a path with a different pen:
   * Select the object on the canvas or in the **Objects & Layers** dock.
   * Assign the desired pen number via right-click context menu or through the pen dock.

*(Details: [Chapter 2: Pen Palette](2-layout-and-objects.md#6-pen-palette--color-assignment))*

---

### Step 4: Switch to Output Mode & Simulate

Click the **Output / Plot** tab at the top:

1. **Read Pre-Flight Statistics:**
   * In the **Output** dock, you can immediately inspect:
     * Exact distance drawn on paper (`Pen Down`).
     * Air distance traveled between paths (`Pen Up`).
     * Time and travel distance saved by the automatic **2-Opt path optimization** (typically **40% to 70%**).
2. **Simulation with the Scrubber:**
   * Find the simulation bar below the canvas.
   * Click **[ Play ]** or drag the **slider**:
     * Cyan dashed lines show all rapid travel moves in the air.
     * Yellow dots indicate every point where the pen is lowered or lifted.
     * The crosshair cursor traces the sheet exactly as the physical plotter toolhead will.
3. **Selective Plotting (optional):**
   * If you have only a single pen holder or want to plot layer by layer, simply uncheck the pens you wish to skip in the current run.

*(Details: [Chapter 3: Output Mode, Simulation & Export](3-output-simulation-export.md))*

---

### Step 5: Send Plot to Device or Export File

1. **Verify Hardware:**
   * In the *Output* dock, click **[ Probe Plotter (Inquiry) ]**.
   * On success, a green status banner appears:  
     `7585B (A3, 40 U/mm) • Hard-Clip: 390x287 mm`.
2. **Start Plotting:**
   * Click **[ Send Plot ]**.
   * Streaming runs in the background. The progress bar and toolhead cursor on the canvas show the live progress in real time.
   * **[ Pause ]:** Pauses transmission (e.g. to inspect ink flow).
   * **[ Cancel ]:** Triggers an emergency stop: the plotter immediately halts, lifts the pen (`PU;`), and parks it safely in the carousel (`SP0;`).
3. **File Export (Alternative):**
   * Click **[ Export Plot File (.hpgl)... ]** if you want to save the optimized machine file for execution at a later time.

*(Details: [Chapter 3: Live Plotting & Export](3-output-simulation-export.md#5-live-plotting-on-hardware))*

---

## Next Steps

* Layout and drawing tools in detail:  
  -> **[Chapter 2: Layout Mode & Object Management](2-layout-and-objects.md)**
* Optimization settings and simulation:  
  -> **[Chapter 3: Output Mode, Simulation & Export](3-output-simulation-export.md)**
* RS-232 cabling, hardware diagnostics, and calibration:  
  -> **[Chapter 4: Hardware Setup, Calibration & Diagnostics](4-hardware-setup-and-diagnostics.md)**
* Vector formats, custom scripts, Inkscape, Blender, and CAD:  
  -> **[Chapter 5: Vector Formats, Sources & Workflows](5-vector-formats-and-workflows.md)**
* Mathematical background, slicer algorithms, and multi-plotter drivers:  
  -> **[Chapter 6: Concepts, Algorithms & Architecture (Deep Dive)](6-concepts-and-architecture.md)**
* Curated tools, single-line fonts, and community collections:  
  -> **[Chapter 7: Recommended Resources, Tools & Community](7-resources-tools-and-community.md)**
