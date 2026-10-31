# 5. Anbindung weiterer Plottermodelle & Geräteprofile

LINTO beschränkt sich nicht auf den Mutoh XP-500. Jedes unterstützte Plottermodell wird über eine deklarative YAML-Profildatei im Verzeichnis `resources/devices/` beschrieben. Beim Programmstart liest LINTO (`list_available_profiles()` in `src/linto/device/profile.py`) alle `*.yaml`-Dateien in diesem Ordner automatisch ein und stellt sie im Dialog **[Geräte-Einstellungen](4-hardware-setup-und-test.md#3-dialog-gerate-einstellungen)** zur Auswahl bereit.

---

## 1. Eigene Geräteprofile anlegen (`resources/devices/*.yaml`)

Um ein weiteres Plottermodell einzubinden, legst du einfach eine neue Datei `resources/devices/<name>.yaml` an. Sobald die Datei dort gespeichert ist, steht das Modell sofort in LINTO zur Verfügung.

### Beispiel 1: Flachbettplotter (`roland_dxy.yaml`, Ursprung unten links)

```yaml
model_id: "roland_dxy"
name: "Roland DXY-1300 Flachbett"
manufacturer: "Roland DG"
emulation: "HP-GL / RD-GL"
protocol: "hpgl"
origin: "bottom_left"          # Flachbettplotter: Ursprung unten links
units_per_mm: 40.0             # Auflösung: 0,025 mm pro Schritt
max_pens: 8                    # 8-Stift-Wechsler
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

### Beispiel 2: Rollenplotter mit allen Optionen (`mutoh_xp500.yaml`, Ursprung zentriert)

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

## 2. Referenz aller YAML-Felder

### 2.1 Identifikation & Protokoll

| Feld | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `model_id` | `string` | Dateiname ohne `.yaml` | Eindeutige interne Kennung des Plottermodells (z. B. `"mutoh_xp500"`, `"hpgl_generic"`). |
| `name` | `string` | `"Unknown Plotter"` | Anzeigename des Modells in der Geräteauswahl. |
| `manufacturer` | `string` | `"Unknown"` | Herstellername (z. B. `"Mutoh"`, `"Roland"`, `"Graphtec"`). |
| `emulation` | `string` | `"HP-7585B"` | Emulationskennung (zur Information und zum Abgleich mit der `OI;`-Antwort). |
| `protocol` | `string` | `"hpgl"` | Befehlssprache des Plotters (aktuell `"hpgl"`). |

### 2.2 Koordinatensystem & intrinsisches Achsen-Mapping

LINTO arbeitet im Layout-Modus mit Blattkoordinaten in Millimetern (Ursprung oben links, `+X` nach rechts, `+Y` nach unten). Der HP-GL-Emitter rechnet diese Koordinaten zunächst in das zentrierte bzw. eckenbasierte kartesische Blattkoordinatensystem (`+X` rechts, `+Y` oben) um und wendet darauf das **intrinsische Hardware-Achsen-Mapping** des Geräteprofils an:

| Feld | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `origin` | `string` | `"center"` | `"center"`: Ursprung `(0,0)` liegt in der Mitte des plottbaren Hard-Clip-Fensters (z. B. Mutoh XP-500, Großformat-Rollenplotter).<br>`"bottom_left"`: Ursprung `(0,0)` liegt unten links (z. B. klassische Flachbettplotter). |
| `units_per_mm` | `float` | `40.0` | Plotter-Schritte pro Millimeter (`40.0` entspricht `0,025 mm/Unit`, `100.0` entspricht `0,01 mm/Unit`). Wird bei einer Hardware-Abfrage (`OF;`) automatisch aktualisiert. |
| `rotation_deg` | `int` | `0` | Intrinsische Grunddrehung der Hardware-Achsen gegen den Uhrzeigersinn (`0`, `90`, `180`, `270`). |
| `invert_x` | `bool` | `false` | Spiegelt die X-Achse vor dem Achsentausch. |
| `invert_y` | `bool` | `false` | Spiegelt die Y-Achse vor dem Achsentausch. |
| `swap_xy` | `bool` | `false` | Vertauscht X- und Y-Achse nach Rotation/Spiegelung. Beim Mutoh XP-500 (`swap_xy: true, invert_y: true`) ist die Plotter-X-Achse die Papier-Vorschubrichtung (nach unten positiv) und die Plotter-Y-Achse die Wagenbewegung (nach rechts positiv). |

> [!NOTE]
> Die im Dialog *Geräte-Einstellungen* und im *Plot-Dock* einstellbaren Achsen-Optionen sind **Benutzer-Korrekturen**, die zusätzlich zum intrinsischen Mapping des Geräteprofils angewendet werden (Standard: keine Korrektur).

### 2.3 Stifte, Stifterkennung & Kinematik (Plotzeit-Schätzung)

| Feld | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `max_pens` | `int` | `8` | Maximale Anzahl der Stifte im Magazin/Karussell. |
| `auto_pen_force` | `bool` | `false` | **`true`**, wenn der Plotter über eine automatische Stifterkennung mit automatischer Andruckregelung verfügt (wie der Mutoh XP-500 über codierte Stifthalter für Tusche, Bleistift, Kugelschreiber etc.).<br>• Ist `auto_pen_force: true`, bleibt die Option **»Manuellen Stiftandruck (FS) senden«** im Plot-Dock standardmäßig **deaktiviert**, damit die Hardware den Andruck automatisch wählt (kann bei Bedarf im Plot-Dock aktiviert werden).<br>• Ist `auto_pen_force: false`, ist die Option im Plot-Dock standardmäßig **aktiviert**, sodass die im Stifte-Dock hinterlegten `FS`-Werte gesendet werden. |
| `force_unit` | `string` | `"grams"` | Einheit für den `FS`-Befehl:<br>• `"grams"`: Direkte Übergabe der Grammzahl (z. B. `FS30;` für 30 g beim Mutoh XP-500).<br>• `"hp_level"`: Umrechnung der Grammzahl auf HP-Stufen `1..8` (`FS1;` bis `FS8;`). |
| `decimal_speed` | `bool` | `true` | Wenn `true`, erlaubt `VS` Nachkommastellen (z. B. `VS12.5;`), andernfalls wird auf ganze `cm/s` gerundet. |
| `max_speed_mm_s` | `float` | `900.0` | Maximale Zeichengeschwindigkeit entlang einer Achse in `mm/s` (Obergrenze für die Plotzeit-Schätzung). Beim Mutoh XP-500: `900 mm/s` (`1272 mm/s` diagonal). |
| `travel_speed_mm_s` | `float` | `900.0` | Eilgang-Geschwindigkeit bei angehobenem Stift (`PU`) in `mm/s` für die Plotzeit-Schätzung und den Echtzeit-Emulator. |
| `pen_change_time_s` | `float` | `2.5` | Mechanische Dauer eines physischen Stiftwechsels (`SPn;`) am Karussell in Sekunden für die Plotzeit-Schätzung. |
| `pen_actuation_time_s` | `float` | `0.04` | Dauer eines einzelnen Pen-Down/Pen-Up-Hubzyklus in Sekunden. |

### 2.4 Serielle Schnittstelle (`connection`)

Definiert die Vorgabewerte beim Anlegen oder Auswählen des Geräteprofils im Dialog *Geräte-Einstellungen*:

| Feld | Typ | Standardwert | Beschreibung |
|---|---|---|---|
| `baudrate` | `int` | `19200` | Standard-Baudrate (z. B. `9600`, `19200`). |
| `bytesize` | `int` | `8` | Anzahl der Datenbits (`7` oder `8`). |
| `parity` | `string` | `"N"` | Parität: `"N"` (Keine), `"E"` (Gerade / Even), `"O"` (Ungerade / Odd). |
| `stopbits` | `int` | `1` | Anzahl der Stoppbits (`1` oder `2`). |
| `flow_control` | `string` | `"rtscts"` | Flusssteuerung: `"rtscts"` (Hardware-Handshake RTS/CTS), `"xonxoff"` (Software-Handshake XON/XOFF) oder `"none"`. Alternativ werden auch die booleschen Felder `rtscts: true/false` und `xonxoff: true/false` ausgewertet. |

### 2.5 Randprofile (`margins_mm` & `default_margin_profile`)

Unter `margins_mm` können ein oder mehrere benannte Randprofile hinterlegt werden. Jedes Profil gibt die nicht beplottbaren Ränder (für Andruckrollen und Greifer) in Millimetern an:

* `top`: Rand an der Papiereinzugskante (Vorderkante / Leading Edge)
* `bottom`: Rand an der Hinterkante (Trailing Edge)
* `left`: Linker Seitenrand (Andruckrolle links)
* `right`: Rechter Seitenrand (Andruckrolle rechts)
* `default_margin_profile`: Schlüssel des standardmäßig ausgewählten Randprofils (z. B. `"exp"` oder `"default"`).

---

## 3. Geräte-Import aus Inkcut (`tools/import_inkcut_devices.py`)

LINTO liefert ein Import-Werkzeug mit, mit dem du alle HP-GL-Gerätetreiber aus einer Inkcut-Installation (`manifest.enaml`) direkt in gebrauchsfertige LINTO-Profile konvertieren kannst:

```bash
# Geräte aus Inkcut einlesen und auflisten:
python3 tools/import_inkcut_devices.py --list-only

# Profile nach resources/devices/ konvertieren:
python3 tools/import_inkcut_devices.py
```

LINTO bringt bereits über 25 vorinstallierte Profile für Modelle von Roland (Stika SV-8/12/15, CAMM-1), Graphtec (CE5000), US Cutter (Refine MH-721/1351), Secabo, Summa, Sekonic und weitere mit.

> [!NOTE]
> **Hinweis zu Schneideplottern (Cutter):** Viele dieser aus Inkcut übernommenen Modelle sind Schneideplotter. Sie funktionieren in LINTO hervorragend mit einem Stifteinsatz als Zeichenplotter. Das Schneiden von Folien mit Messerklingen wird noch nicht unterstützt, da die dafür notwendige Schleppmesser-Offset-Kompensation noch fehlt.
