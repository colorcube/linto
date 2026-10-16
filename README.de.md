# Plotter Studio

> **Sprache / Language:** [Deutsch](README.de.md) | [English](README.md)

> **Der modulare Slicer, Layout-Editor und Streaming-Controller für Stiftplotter unter Linux.**

Plotter Studio bereitet deine Vektorgrafiken für echte Stiftplotter auf: Es optimiert Fahrwege (40–70 % weniger Leerfahrten), simuliert den Zeichenvorgang interaktiv am Bildschirm und streamt die Daten mit Hardware-Handshake zuverlässig an das Gerät.

---

## Blick in die App

### Layout-Modus: Grafiken arrangieren, skalieren und Stiften zuweisen
![Plotter Studio Layout Modus](docs/images/ui_overview_layout.png)

### Ausgabe-Modus: Pfadoptimierung, Leerwege-Visualisierung & Simulation
![Plotter Studio Ausgabe Modus mit Simulation](docs/images/ui_overview_plot.png)

---

## Was ist Plotter Studio?

Wenn du mit einem **physischen Stiftplotter** zeichnest (egal ob Klassiker wie Mutoh XP-500, HP 7585B, Roland DXY oder moderne Stiftmaschinen) und deine Grafiken aus **Inkscape, Illustrator, CAD oder generativen Python/Processing-Skripten** stammen, ist Plotter Studio das Bindeglied zur Hardware:

* **Echtes Millimeter-Layout:** Platziere deine Grafiken auf DIN-Formaten (A4 bis A0) oder freien Bogenmaßen. Du siehst exakt die physischen Ränder (z. B. asymmetrische Vorschubränder bei Rollenplottern) oder fragst das eingespannte Papier per Knopfdruck direkt vom Plotter ab (`OH;`).
* **Slicer-Pipeline & 2-Opt TSP:** Wie ein Slicer im 3D-Druck verbindet Plotter Studio benachbarte Linien, glättet Mikrostützpunkte und optimiert die Stiftreihenfolge mit einem **2-Opt-Algorithmus (Traveling Salesperson Problem)**. Das spart typischerweise **40 % bis 70 %** der zeitraubenden Leerfahrten in der Luft ein.
* **Interaktive Simulation:** Bevor der Stift das Papier berührt, kannst du den gesamten Plot mit einer Zeitleiste (Scrubber) vor- und zurückspulen – inklusive Anzeige aller Stifthübe (`Pen Up`).
* **Sicheres Live-Streaming:** Serieller Versand mit striktem **RTS/CTS-Hardware-Handshake** (kein Pufferüberlauf). Pausieren, Fortsetzen und sofortiger Notfallabbruch (`ESC.K`, `PU;`, `SP0;`) parken den Stift sicher im Karussell.

### Was Plotter Studio nicht ist
* **Kein Druckertreiber für Tintenstrahl-Großformatdrucker:** Plotter Studio steuert ausschließlich echte mechanische Stiftplotter an, keine Raster-Tintenstrahldrucker.
* **Keine Schneideplotter-Software:** Der Fokus liegt auf Stiftplottern. Schneidemesser (Drag-Knife Offset) stehen auf der Roadmap.
* **Kein Zeichenprogramm:** Du entwirfst weiter in Inkscape, Illustrator oder deinem Code. Plotter Studio übernimmt das Aufbereiten und Plotten.

---

## Kern-Features im Überblick

* **Vektor-Import:** SVG- und HP-GL/PLT-Dateien per Drag & Drop oder Dateidialog öffnen.
* **Stiftpalette & Farb-Clustering:** Automatische Zuordnung von Strichfarben auf die 8 Stifte via Delta-E (Lab-Farbraum). Einstellbare Zeichengeschwindigkeit (`VS`) und Anpressdruck (`FS`).
* **Präzise Transformation:** Numerische Positionierung (Bezug: Blatt oder Plottbereich), proportionale Skalierung, 1:1-Originalgröße, Einpassen mit Rand, freie Drehung und Spiegelung.
* **Objekte & Ebenen (Z-Order):** Zeichenreihenfolge ändern, Objekte sperren oder ausblenden.
* **Multi-Plotter-Unterstützung:** 26 vorinstallierte YAML-Profile (Mutoh XP-500, Generic Flatbed sowie **24 Profile aus InkCut** wie Roland, Graphtec, Summa, US Cutter).
* **Hardware-Diagnose & Emulator:** Eingebautes Terminal-Diagnosetool (`tools/xp500_probe.py`), Kalibriermuster (`resources/calibration_plot_a3.svg`) und vollwertiger Software-Emulator (`VirtualPlotter`) zum Testen ohne Hardware.

---

## Quickstart: In 5 Schritten zum ersten Plot

Du brauchst keine Hardware, um sofort loszulegen – der eingebaute Emulator simuliert einen echten Plotter:

```
[ 1. Verbinden ] -> [ 2. Blatt wählen ] -> [ 3. Vektor laden ] -> [ 4. Simulieren ] -> [ 5. Plotten ]
```

1. **Plotter verbinden oder Simulator starten:**
   * *Mit Hardware:* Plotter per RS-232-Nullmodemkabel anschließen (siehe [Kapitel 4: Hardware-Setup](docs/anleitung/4-hardware-setup-und-test.md)).
   * *Ohne Hardware:* Simulator im Terminal mit `python3 -m plotter_studio.emulator --tcp 9999` starten und oben `Mutoh XP-500 Simulator (TCP)` auswählen.
2. **Blattgröße und Randprofil wählen:**
   * Klicke auf **[ Seiteneinrichtung... ]**, wähle z. B. `DIN A3 Quer` und Randprofil `EXP`. Mit **[ Plotter abfragen ]** liest du die Maße direkt von den optischen Sensoren ab.
3. **Zeichnung importieren und platzieren:**
   * Ziehe eine `.svg`- oder `.hpgl`-Datei per Drag & Drop ins Fenster.
   * Nutze im Dock *Transformation* **[ Einpassen ]** oder **[ Zentrieren ]**.
4. **Plot simulieren:**
   * Wechsle oben auf den Reiter **Ausgabe**.
   * Ziehe am Zeitleisten-Schieberegler oder drücke Play, um Leerwege und Zeichenreihenfolge vorab zu prüfen.
5. **Plotten oder exportieren:**
   * Klicke auf **[ Plot senden ]** für die Live-Ausgabe oder exportiere die optimierte Datei über **[ Plotdatei (.hpgl) exportieren... ]**.

---

## Dokumentation

Das ausführliche Handbuch findest du im Ordner [`docs/anleitung/`](docs/anleitung/README.md):

* **[1. Schnellstart & Typischer Workflow](docs/anleitung/1-schnellstart-und-workflow.md):** Schritt-für-Schritt-Einstieg mit Hardware oder Emulator.
* **[2. Layout-Modus & Objektverwaltung](docs/anleitung/2-layout-und-objektverwaltung.md):** Canvas, Werkzeuge, Seiteneinrichtung, Z-Order, Skalierung & Stifte.
* **[3. Ausgabe-Modus, Simulation & Export](docs/anleitung/3-ausgabe-simulation-export.md):** Pipeline-Tuning, Pre-Flight-Statistiken, Scrubber-Simulation & Streaming.
* **[4. Hardware-Setup, Kalibrierung & Diagnose](docs/anleitung/4-hardware-setup-und-test.md):** Nullmodem-Verkabelung (RTS/CTS), FTDI-Adapter, Diagnosetool und Kalibrierplot.
* **[5. Leitfaden: Vektorformate, Quellen & Workflows](docs/anleitung/5-vektorformate-und-workflows.md):** Eigene SVG-Skripte (`mm`-Einheiten, Stiftfarben), Inkscape, Blender, HP-GL und DXF.
* **[6. Hintergrund: Konzepte, Algorithmen & Architektur](docs/anleitung/6-konzepte-und-architektur.md):** Deep-Dive in Slicer-Mathematik, 2-Opt TSP, Koordinatentransformationen und Streaming.
* **[7. Empfohlene Ressourcen, Tools & Community](docs/anleitung/7-ressourcen-tools-und-community.md):** Kuratierte Tools (vpype, vsketch, ln, Turtletoy), Hershey-Fonts und Community-Hubs.
* **[Mutoh XP-500 Gerätedokumentation](docs/devices/mutoh-xp500/README.md):** Handbuch-Transkription, MH-GL-Befehlssatz, Escape-Sequenzen und Register.

---

## Installation für Entwickler

```bash
# Virtuelle Umgebung anlegen und aktivieren
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Plotter Studio starten
plotter-studio

# Testsuite ausführen (107 Tests)
pytest
```

---

## Verwandte Projekte & Dank

* **[InkCut](https://github.com/codelv/inkcut) (GPL-3.0-or-later):** 24 Geräteprofile (u. a. Roland, Graphtec, Summa, US Cutter) wurden übernommen und aufbereitet (`tools/import_inkcut_devices.py`).
* **[vpype](https://github.com/abey79/vpype) (Antoine Beyeler, GPL-3.0-or-later):** Konzeptionelle Inspiration für die modulare Slicer-Pipeline.
* **[MutohPlot](https://github.com/oliver321/MutohPlot) (Oliver F., MIT-Lizenz):** Wertvolle Referenz für die Mutoh XP-500 Hard-Clip-Tabellen, HP-GL-Tokenizer und den 5×7-Vektorfont.

---

## Lizenz

Lizenziert unter der **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. Siehe [LICENSE.txt](LICENSE.txt).

---

## Entstehungsprozess mit KI-Nutzung

Dieses Projekt entstand in einem kollaborativen Pair-Programming-Prozess zwischen einem menschlichen Entwickler und autonomen KI-Agenten.
