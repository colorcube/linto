# Plotter Studio

> **Moderne Steuer- und Layout-Software (Slicer) für Vektor-Stiftplotter unter Linux und Windows.**

Plotter Studio schließt die Lücke zwischen modernen Vektorgrafiken (SVG, CAD, generative Kunst) und der physikalischen Mechanik klassischer und moderner Stiftplotter. Es fungiert als **intelligenter Slicer**: Es optimiert Pfadgeometrien, minimiert Stift-Leerfahrten drastisch (2-Opt TSP), verhindert Pufferüberläufe durch echten RTS/CTS-Hardware-Handshake und bietet eine intuitive Benutzeroberfläche mit Live-Simulation.

---

## 📸 Screenshots

### 1. Layout-Modus (Objektplatzierung, Skalierung & Randinspektion)
![Plotter Studio Layout Modus](docs/images/ui_overview_layout.png)

### 2. Ausgabe-Modus (Simulation, Eilgang-Vorschau & Pre-Flight-Statistiken)
![Plotter Studio Ausgabe Modus mit Simulation](docs/images/ui_overview_plot.png)

---

## ✨ Hauptfunktionen

* **Intelligente Slicer-Pipeline:**
  * **Linienzusammenfassung (Merge):** Aneinanderliegende Linienenden werden automatisch zu durchgehenden Polylinien verbunden.
  * **Richtungsumkehr (Reverse):** Intelligente Umkehrung von Pfadrichtungen zur Vermeidung von Rückwegen.
  * **RDP-Vereinfachung:** Glättung redundanter Mikrostützpunkte (Douglas-Peucker) verhindert Motorstottern.
  * **2-Opt TSP Pfadoptimierung:** Ordnet Werkzeugwege mathematisch optimal an und spart **40 % bis 70 % aller Stift-Leerfahrten** ein.
* **Layout & Grafikwerkzeuge:**
  * Zoombarer Vektor-Canvas mit Millimeter-Linealen, Fadenkreuz und Hard-Clip-Grenzen.
  * **Seiteneinrichtung:** DIN A4 bis DIN A0 sowie benutzerdefinierte Maße, Hoch-/Querformat, Randprofile (EXP, NORM etc.) und Live-Hard-Clip-Erkennung (`OH;`).
  * **Transformation:** Numerische Positionierung, Skalierung mit Proportions-Sperre (🔗), Schnelltasten (50 %, 100 %, 200 %, Auf Blatt einpassen, Zentrieren), Drehen und Spiegeln.
  * **Objekt- & Ebenen-Dock:** Z-Order Steuerung, Sichtbarkeit (Auge), Bearbeitungssperre (Schloss), Duplizieren und Löschen.
  * **Stiftpalette:** Bis zu 8 Werkzeuge mit automatischem Farb-Clustering beim SVG-Import.
* **Simulation & Pre-Flight:**
  * Interaktive Simulationsleiste (Scrubber) mit Play/Pause und variabler Geschwindigkeit (1x bis 10x).
  * Klare Farbcodierung im Canvas: Tatsächliche Stiftlinien, türkis gestrichelte Leerfahrten (`Pen Up`) und Aufsetzpunkte.
  * Exakte Statistiken: Zeichenstrecke, Eilgangsstrecke, prozentuale Ersparnis, Stiftwechsel und geschätzte Plotdauer.
  * **Stift-Filter:** Gezieltes Aktivieren einzelner Stifte für manuelle Stiftwechsel oder Testplots.
* **Robuste Geräteanbindung:**
  * Live-Streaming über serielle Schnittstelle (RS-232 / USB-Seriell) oder TCP-Netzwerk.
  * Strikte Flusssteuerung über **RTS/CTS-Hardware-Handshake** verhindert Pufferüberläufe.
  * Notfall-Rückzug bei Abbruch (`ESC.K`, `PU;`, `SP0;`) schützt Papier und Stiftspitze.
  * Live-Synchronisation: Virtueller Werkzeugkopf-Cursor wandert im Canvas mit dem echten Plotterkopf mit.
  * Export nach Standard-HP-GL (`.hpgl`) und nach Stiften gruppiertem Plot-SVG (`.svg`).
* **Multi-Plotter-Architektur:**
  * Nicht an ein einzelnes Fabrikat gebunden! Modular aufgebaut über deklarative YAML-Geräteprofile (`resources/devices/*.yaml`).
  * Unterstützt Center-Origin (z.B. **Mutoh XP-500**, HP-7585B) und Bottom-Left-Systeme (z.B. **Roland DXY**, HP 7475A, generische Flachbettplotter).
  * Konfigurierbare Randmodi für Rollen- und Flachbettmechaniken.
* **Integrierter Software-Emulator:**
  * Vollwertiger virtueller Plotter (`VirtualPlotter`) mit PTY- und TCP-Server zum Entwickeln, Testen und Simulieren ohne echte Hardware.

---

## 🚀 Schnellstart

### 1. Installation

```bash
# Repository klonen
git clone https://github.com/Diverse/plotter-studio.git
cd plotter-studio

# Virtuelle Umgebung erstellen und aktivieren
python3 -m venv .venv
source .venv/bin/activate

# Abhängigkeiten installieren (im Entwicklungsmodus)
pip install -e ".[dev]"
```

### 2. Plotter Studio starten

```bash
# Direkt als Modul ausführen:
python3 -m plotter_studio.gui

# Oder über das installierte Konsolenskript:
plotter-studio
```

### 3. Testen mit dem integrierten Software-Emulator

Sie benötigen keinen physischen Plotter, um alle Funktionen zu testen:

```bash
# In einem separaten Terminal den Emulator auf Port 9999 starten:
python3 -m plotter_studio.emulator --tcp 9999

# In Plotter Studio oben "Mutoh XP-500 Simulator (TCP)" auswählen
# und mit [ 🔍 Plotter prüfen (Inquiry) ] die Verbindung testen!
```

---

## 📖 Ausführliche Dokumentation

Plotter Studio verfügt über ein umfassendes Benutzerhandbuch und detaillierte Hardware-Spezifikationen:

* **[Benutzerhandbuch & Anleitungen (docs/anleitung/)](docs/anleitung/README.md):**
  1. **[Konzepte & Architektur](docs/anleitung/1-konzepte-und-architektur.md):** Warum Slicer statt Druckertreiber? 2-Opt TSP, Koordinatensysteme und Multi-Plotter-Design.
  2. **[Layout-Modus & Objektverwaltung](docs/anleitung/2-layout-und-objektverwaltung.md):** GUI-Überblick, Import, Transformation, Ebenen & Stifte.
  3. **[Ausgabe-Modus, Simulation & Export](docs/anleitung/3-ausgabe-simulation-export.md):** Pipeline-Tuning, Pre-Flight, Scrubber-Simulation und Live-Streaming.
  4. **[Hardware-Setup, Kalibrierung & Diagnose](docs/anleitung/4-hardware-setup-und-test.md):** RS-232 Verkabelung, Panel-Einstellungen, Diagnosetool `xp500_probe.py` und der offizielle Kalibrierplot (`resources/calibration_plot_a3.svg`).
* **[Mutoh XP-500 Gerätedokumentation](docs/devices/mutoh-xp500/README.md):** Vollständige Referenz zu MH-GL-Befehlen, Escape-Sequenzen und Hardware-Registern.
* **[Architektur & Meilensteine](docs/project/konzept.md):** Konzept und technischer Hintergrund.

---

## 🛠️ Hardware-Werkzeuge

* **Diagnose-Probe:**
  ```bash
  python3 tools/xp500_probe.py /dev/ttyUSB0 --baudrate 19200
  ```
* **Kalibriermuster generieren:**
  ```bash
  python3 tools/generate_calibration_plot.py
  ```

---

## 🧪 Tests ausführen

Das gesamte System ist durch automatisierte Komponententests abgesichert:

```bash
.venv/bin/pytest
```

---

## 📄 Lizenz

Dieses Projekt ist unter der **GNU General Public License v3.0 or later (GPL-3.0-or-later)** lizenziert.
