# 5. Adding Plotter Models & Device Profiles

LINTO is not restricted to the Mutoh XP-500. Every supported plotter model is defined by a declarative YAML profile located in `src/linto/resources/devices/`. At startup, LINTO (`list_available_profiles()` in `src/linto/device/profile.py`) automatically loads all `*.yaml` files in that directory and makes them available in the **[Device Settings Dialog](4-hardware-setup-and-diagnostics.md#3-device-settings-dialog)**.

---

## 1. Creating Custom YAML Device Profiles (`src/linto/resources/devices/*.yaml`)

To add a new plotter model, simply create a new file `src/linto/resources/devices/<name>.yaml`. As soon as the file is saved, the model becomes available in LINTO.

### Example 1: Flatbed Plotter (`roland_dxy.yaml`, Bottom-Left Origin)

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

### Example 2: Grit-Roller Plotter with Full Options (`mutoh_xp500.yaml`, Center Origin)

```yaml
model_id: "mutoh_xp500"
name: "Mutoh XP-500"
manufacturer: "Mutoh"
emulation: "HP-7585B"
protocol: "hpgl"
origin: "center"
units_per_mm: 40.0
max_pens: 8
max_speed_mm_s: 900.0
travel_speed_mm_s: 900.0
pen_change_time_s: 2.5
pen_actuation_time_s: 0.04
auto_pen_force: true
force_unit: "grams"
decimal_speed: true
swap_xy: true
invert_x: false
invert_y: true
rotation_deg: 0

connection:
  baudrate: 19200
  bytesize: 8
  parity: "N"
  stopbits: 1
  rtscts: true
  xonxoff: false

margins_mm:
  exp:
    top: 25.0
    bottom: 5.0
    left: 5.0
    right: 5.0
  norm:
    top: 35.0
    bottom: 15.0
    left: 15.0
    right: 15.0
  type1:
    top: 25.0
    bottom: 5.0
    left: 11.0
    right: 11.0
  type3:
    top: 25.0
    bottom: 10.0
    left: 10.0
    right: 10.0

default_margin_profile: "exp"
```

---

## 2. Complete Reference of All YAML Fields

### 2.1 Identification & Protocol

| Field | Type | Default | Description |
|---|---|---|---|
| `model_id` | `string` | Filename without `.yaml` | Unique internal identifier for the plotter model (e.g. `"mutoh_xp500"`, `"hpgl_generic"`). |
| `name` | `string` | `"Unknown Plotter"` | Display name shown in the device selector. |
| `manufacturer` | `string` | `"Unknown"` | Manufacturer name (e.g. `"Mutoh"`, `"Roland"`, `"Graphtec"`). |
| `emulation` | `string` | `"HP-7585B"` | Emulation identifier (informational and matched against `OI;` responses). |
| `protocol` | `string` | `"hpgl"` | Command language of the plotter (currently `"hpgl"`). |

### 2.2 Coordinate System & Intrinsic Axis Mapping

In Layout Mode, LINTO works with sheet coordinates in millimeters (origin at top-left, `+X` right, `+Y` down). The HP-GL emitter first converts these coordinates into the centered or corner-based Cartesian sheet coordinate system (`+X` right, `+Y` up) and then applies the device profile's **intrinsic hardware axis mapping**:

| Field | Type | Default | Description |
|---|---|---|---|
| `origin` | `string` | `"center"` | `"center"`: Origin `(0,0)` is at the center of the plottable hard-clip window (e.g. Mutoh XP-500, large-format grit-roller plotters).<br>`"bottom_left"`: Origin `(0,0)` is at the bottom-left corner (e.g. classic flatbed plotters). |
| `units_per_mm` | `float` | `40.0` | Plotter steps per millimeter (`40.0` equals `0.025 mm/unit`, `100.0` equals `0.01 mm/unit`). Automatically updated when querying the hardware (`OF;`). |
| `rotation_deg` | `int` | `0` | Intrinsic base rotation of hardware axes counter-clockwise (`0`, `90`, `180`, `270`). |
| `invert_x` | `bool` | `false` | Mirrors the X axis before axis swapping. |
| `invert_y` | `bool` | `false` | Mirrors the Y axis before axis swapping. |
| `swap_xy` | `bool` | `false` | Swaps X and Y axes after rotation/mirroring. On the Mutoh XP-500 (`swap_xy: true, invert_y: true`), the plotter X axis is the paper feed direction (positive downward) and the plotter Y axis is carriage movement (positive rightward). |

> [!NOTE]
> The axis options available in the *Device Settings* dialog and *Plot Dock* are **user overrides** applied on top of the device profile's intrinsic mapping (default: no override).

### 2.3 Pens, Pen Sensing & Kinematics (Plot Time Estimation)

| Field | Type | Default | Description |
|---|---|---|---|
| `max_pens` | `int` | `8` | Maximum number of pens in the magazine/carousel. |
| `auto_pen_force` | `bool` | `false` | **`true`** if the plotter features automatic pen type detection and automatic force regulation (such as the Mutoh XP-500 using coded pen holders for technical pens, pencils, ballpoints, etc.).<br>• When `auto_pen_force: true`, the **“Send manual pen force (FS)”** option in the Plot Dock is **unchecked by default** so hardware regulates pressure automatically (can be enabled manually if desired).<br>• When `auto_pen_force: false`, the option in the Plot Dock is **checked by default**, sending the `FS` values configured in the Pens Dock. |
| `force_unit` | `string` | `"grams"` | Unit for the `FS` command:<br>• `"grams"`: Direct gram value (e.g. `FS30;` for 30 g on Mutoh XP-500).<br>• `"hp_level"`: Maps gram values to HP force levels `1..8` (`FS1;` through `FS8;`). |
| `decimal_speed` | `bool` | `true` | When `true`, allows decimal values in `VS` commands (e.g. `VS12.5;`); otherwise rounds to integer `cm/s`. |
| `max_speed_mm_s` | `float` | `900.0` | Maximum drawing speed along a single axis in `mm/s` (upper bound for plot time estimation). On Mutoh XP-500: `900 mm/s` (`1272 mm/s` diagonal). |
| `travel_speed_mm_s` | `float` | `900.0` | Rapid travel speed with pen raised (`PU`) in `mm/s` used for plot time estimation and the real-time emulator. |
| `pen_change_time_s` | `float` | `2.5` | Mechanical duration of a physical pen swap (`SPn;`) at the carousel in seconds for plot time estimation. |
| `pen_actuation_time_s` | `float` | `0.04` | Duration of a single pen-down/pen-up actuation cycle in seconds. |

### 2.4 Serial Interface (`connection`)

Defines the default serial parameters when creating or selecting the device profile in the *Device Settings* dialog:

| Field | Type | Default | Description |
|---|---|---|---|
| `baudrate` | `int` | `19200` | Default baud rate (e.g. `9600`, `19200`). |
| `bytesize` | `int` | `8` | Number of data bits (`7` or `8`). |
| `parity` | `string` | `"N"` | Parity: `"N"` (None), `"E"` (Even), `"O"` (Odd). |
| `stopbits` | `int` | `1` | Number of stop bits (`1` or `2`). |
| `flow_control` | `string` | `"rtscts"` | Flow control: `"rtscts"` (hardware RTS/CTS handshake), `"xonxoff"` (software XON/XOFF handshake), or `"none"`. Alternatively, boolean fields `rtscts: true/false` and `xonxoff: true/false` are also supported. |

### 2.5 Margin Profiles (`margins_mm` & `default_margin_profile`)

One or more named margin profiles can be defined under `margins_mm`. Each profile specifies the unplottable margins (for pinch rollers and grippers) in millimeters:

* `top`: Margin at the paper feed edge (leading edge)
* `bottom`: Margin at the trailing edge
* `left`: Left side margin (left pinch roller)
* `right`: Right side margin (right pinch roller)
* `default_margin_profile`: Key of the margin profile selected by default (e.g. `"exp"` or `"default"`).

---

## 3. Importing Device Drivers from Inkcut (`tools/import_inkcut_devices.py`)

LINTO includes a converter script to import HP-GL device drivers directly from an Inkcut installation (`manifest.enaml`):

```bash
# List devices detected from Inkcut:
python3 tools/import_inkcut_devices.py --list-only

# Convert and export profiles to src/linto/resources/devices/:
python3 tools/import_inkcut_devices.py
```

LINTO includes over 25 pre-installed profiles for Roland (Stika SV-8/12/15, CAMM-1), Graphtec (CE5000), US Cutter (Refine MH-721/1351), Secabo, Summa, Sekonic, and others.

> [!NOTE]
> **Note on Vinyl Cutters:** Many imported models are vinyl cutters. They work well in LINTO when fitted with a pen holder. Blade cutting of adhesive vinyl is not yet supported due to missing drag-knife offset compensation.
