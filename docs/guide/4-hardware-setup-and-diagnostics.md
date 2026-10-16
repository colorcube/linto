# 4. Hardware Setup, Calibration & Diagnostics

Here you will learn how to physically connect your pen plotter to your computer, configure serial interface parameters and control panel settings, test communication using the built-in diagnostic probe tool, run the calibration plot, and add custom plotter models.

---

## 1. Physical Connection & Cabling

Classic plotters utilize RS-232 serial interfaces (typically 25-pin DB-25 or 9-pin DB-9 connectors). Modern computers usually lack native COM ports, requiring a USB-to-serial adapter.

### Recommended USB-to-Serial Adapters
* **Chipset:** Use adapters with genuine **FTDI** (e.g. FT232R, FT2232) or **Silicon Labs** (CP2102) chipsets.
* **Caution:** Inexpensive clone adapters lacking proper hardware RTS/CTS flow control will cause buffer overruns and data loss on larger vector drawings.

### Null-Modem Cabling with Genuine Hardware Handshake
Reliable communication strictly requires a full-handshake null-modem (crossover) cable:

| Signal | PC Side (DB-9 Female) | Plotter Side (DB-25 Male) | Plotter Side (DB-9 Male) | Description |
|---|---|---|---|---|
| **RxD** (Receive) | Pin 2 | Pin 2 (TxD) | Pin 3 (TxD) | Receive data line |
| **TxD** (Transmit) | Pin 3 | Pin 3 (RxD) | Pin 2 (RxD) | Transmit data line |
| **GND** (Ground) | Pin 5 | Pin 7 (GND) | Pin 5 (GND) | Signal ground |
| **RTS** (Request to Send) | Pin 7 | Pin 5 (CTS) | Pin 8 (CTS) | PC indicates readiness |
| **CTS** (Clear to Send) | Pin 8 | Pin 4 (RTS) | Pin 7 (RTS) | **Plotter throttles data flow (Handshake)** |
| **DTR** (Data Terminal Ready)| Pin 4 | Pin 6 (DSR) | Pin 6 (DSR) | Operational readiness |
| **DSR** (Data Set Ready) | Pin 6 | Pin 20 (DTR) | Pin 4 (DTR) | Operational readiness |

> **Important:** A simple 3-wire connection (only TxD, RxD, GND) without RTS/CTS is unreliable on pen plotters because the plotter must be able to pause the computer during complex mechanical movements.

### Alternative: TCP / Ethernet Device Servers
Instead of a direct USB cable, you can use serial-to-Ethernet converters (e.g. Moxa NPort, USR-TCP232) or a Raspberry Pi running `socat`. Plotter Studio natively supports TCP network sockets via `tcp://<IP-Address>:<Port>` (e.g. `tcp://192.168.1.150:4001`).

---

## 2. Control Panel & DIP Switch Setup (Mutoh XP-500 Example)

Configure the following settings on your plotter's front control panel or DIP switches:

* **Emulation:** HP-7585B or MH-GL.
* **Baud Rate:** `19200` baud (or `9600` baud for very long cables).
* **Data Format:** `8` data bits, `None` parity, `1` stop bit (**8N1**).
* **Handshake / Flow Control:** **Hardware (RTS/CTS)**. *XON/XOFF must be disabled*.
* **Margin Profile:** **EXP** (Expanded).
* **Paper Loading:** After loading the paper, the optical sensor detects sheet edges automatically.

---

## 3. Hardware Diagnostics with `tools/xp500_probe.py`

Plotter Studio includes a standalone terminal diagnostic tool to verify the serial lines and inspect raw responses at the byte level:

```bash
# Probing via USB-Serial:
python3 tools/xp500_probe.py /dev/ttyUSB0

# Probing with custom baud rate and detailed ESC sequences:
python3 tools/xp500_probe.py /dev/ttyUSB0 --baudrate 19200 --esc

# Probing via network / TCP server:
python3 tools/xp500_probe.py tcp://127.0.0.1:9999
```

### Typical Output on a Successful Connection:
```
============================================================
Plotter Studio - Hardware Diagnostic Probe
Target: /dev/ttyUSB0 (19200 baud, 8N1, RTS/CTS)
============================================================
[1/4] Checking Hardware Control Lines (RS-232)...
  CTS line : True  (Plotter is ready to accept data)
  DSR line : True  (Plotter hardware present)

[2/4] Querying Plotter Identification...
  Command 'OI;' -> Response: '7585B' (HP-7585B emulation active)

[3/4] Querying Resolution & Scaling Factors...
  Command 'OF;' -> Response: '40,40' (40 Plotter-Units per mm = 0.025 mm/step)

[4/4] Querying Plottable Window (Hard-Clip)...
  Command 'OH;' -> Response: '-8200,-5340,8200,5340'
  Calculated printable area: 410.0 mm x 267.0 mm (Matches DIN A3)

Result: Plotter is ONLINE, RESPONSIVE and READY FOR PLOTTING!
```

If a timeout occurs, check your CTS/RTS wiring and baud rate on the plotter control panel.

---

## 4. The Calibration Plot (Accuracy, Margins, Pens & Backlash)

Pre-compiled calibration patterns for DIN A4 and DIN A3 are located in `resources/`:
* `resources/calibration_plot_a3.svg` / `.hpgl`
* `resources/calibration_plot_a4.svg` / `.hpgl`

![Calibration Plot](../images/ui_overview_plot.png)

### Calibration Features & Verification Criteria:

1. **Orientation Arrows (+X / +Y) & Edge Markers:**
   * An arrow marked `+Y` and text `TOP / LEADING EDGE` is drawn at the feed edge.
   * *Check:* Was the text drawn upside-down or mirrored? If so, adjust `invert_x`, `invert_y`, or `rotation_deg` in the device profile.
2. **Precision Measurement Line (400 mm for A3 / 200 mm for A4):**
   * A continuous measurement line with precise end ticks.
   * *Check:* Measure the drawn line with a quality **steel ruler**.
   * If the line measures exactly 400.0 mm, stepper resolution is calibrated at 40.0 units/mm. Any variance can be fine-tuned via `units_per_mm` in the profile.
3. **Outer Hard-Clip Border:**
   * Traces a rectangle along the plotter's maximum printable limits.
   * *Check:* Are all 4 borders drawn cleanly without the pen running over pinch rollers or the carriage hitting mechanical limits?
4. **8-Pen Matrix:**
   * 8 labeled test boxes with colored hatch fills.
   * *Check:* Does the pen carousel change each pen smoothly? Do pen caps seal tightly?
5. **Concentric Circles & Square-in-Circle (Backlash Check):**
   * Concentric circles enclosing a centered square.
   * *Check:*
     * Do circle start and endpoints align perfectly?
     * Are circles round or egg-shaped/elliptical?
     * Quadrant shifts indicate mechanical backlash in drive belts or pinch wheels.

---

## 5. Adding Custom Plotter Models

Plotter Studio is not restricted to the Mutoh XP-500. You can add any HP-GL compatible plotter to the configuration.

### Device Settings Dialog

Open **Device -> Settings...** from the menu or top toolbar:

![Device Settings Dialog](../images/dialog_device_settings.png)

* **Plotter List:** Displays all configured devices.
* **[ New Device ]:** Adds a new profile.
* **Per-Device Settings:**
  * **Display Name:** e.g. `Roland DXY-1150 Flatbed`.
  * **Device Profile:** Base hardware model (e.g. `mutoh_xp500` or `hpgl_generic`).
  * **Port & Baud Rate:** Serial port or network address.
  * **Margin Profile:** Default margin configuration.

### Creating Custom YAML Device Profiles
Device profiles are stored under `resources/devices/<name>.yaml`. You can create new profiles directly:

```yaml
model_id: "roland_dxy"
name: "Roland DXY-1300 Flatbed"
manufacturer: "Roland DG"
emulation: "HP-GL / RD-GL"
protocol: "hpgl"
origin: "bottom_left"          # Flatbed: origin bottom-left
units_per_mm: 40.0             # Resolution: 0.025 mm per step
max_pens: 8                    # 8-pen carousel
swap_xy: false
invert_x: false
invert_y: false
rotation_deg: 0

connection:
  baudrate: 9600
  bytesize: 8
  parity: "N"
  stopbits: 1
  rtscts: true
  xonxoff: false

margins_mm:
  default:
    top: 8.0
    bottom: 8.0
    left: 8.0
    right: 8.0

default_margin_profile: "default"
```

Once saved to `resources/devices/`, the new profile immediately becomes available in Plotter Studio's UI.

### Importing Device Drivers from InkCut

Plotter Studio includes a converter script to import HP-GL device drivers directly from an InkCut installation (`manifest.enaml`):

```bash
# List devices detected from InkCut:
python3 tools/import_inkcut_devices.py --list-only

# Convert and export profiles to resources/devices/:
python3 tools/import_inkcut_devices.py
```

Plotter Studio includes over 25 pre-installed profiles for Roland (Stika SV-8/12/15, CAMM-1), Graphtec (CE5000), US Cutter (Refine MH-721/1351), Secabo, Summa, Sekonic, and others.

> **Note on Vinyl Cutters:** Many imported models are vinyl cutters. They work well in Plotter Studio when fitted with a pen holder. Blade cutting of adhesive vinyl is not yet supported due to missing drag-knife offset compensation.
