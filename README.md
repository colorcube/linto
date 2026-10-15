# Plotter Studio

> **Die modulare Steuer-, Layout- und Slicer-Software für klassische und moderne Vektor-Stiftplotter.**

Plotter Studio bereitet Vektorgrafiken für echte Stiftplotter auf, optimiert Fahrwege, simuliert den Zeichenvorgang interaktiv am Bildschirm und sendet die Daten sicher und ohne Pufferüberlauf an das Gerät.

---

## Ein Blick in das Programm

### Layout-Modus: Grafiken anordnen, skalieren und Stiften zuweisen
![Plotter Studio Layout Modus](docs/images/ui_overview_layout.png)

### Ausgabe-Modus: Pfadoptimierung, Leerfahrten-Visualisierung & Simulation
![Plotter Studio Ausgabe Modus mit Simulation](docs/images/ui_overview_plot.png)

---

## Was ist Plotter Studio – und kann ich es brauchen?

### Wofür ist Plotter Studio gedacht?
Wenn Sie mit einem **physischen Stiftplotter** zeichnen (egal ob Oldtimer wie Mutoh XP-500, HP 7585B, Roland DXY oder moderne Pen Plotter) und Ihre Grafiken aus Programmen wie **Inkscape, Illustrator, CAD oder generativen Python/Processing-Skripten** stammen, ist Plotter Studio das fehlende Bindeglied:
* Sie können Grafiken direkt auf Standard-Papierformaten (DIN A4 bis DIN A0) oder freien Abmessungen platzieren, numerisch skalieren, zentrieren und drehen.
* Sie sehen genau, wie viel Rand der Plotter für den Vorschub benötigt (asymmetrische Rollenränder) oder können das eingespannte Papier per Knopfdruck direkt vom Plotter abfragen.
* Die Software arbeitet wie ein **Slicer** beim 3D-Druck: Sie verbindet aneinanderliegende Linien, glättet überflüssige Stützpunkte und sortiert alle Vektoren mit einem **2-Opt-Algorithmus (TSP)** so um, dass die Stift-Leerfahrten in der Luft um **40 % bis 70 %** sinken.
* Bevor ein einziger Tropfen Tinte auf das Papier gelangt, können Sie den gesamten Plot mit einer **Zeitleiste (Scrubber)** sekundengenau vor- und zurückspulen.
* Das Senden erfolgt im Hintergrund über serielle Schnittstellen oder Netzwerk mit echtem **Hardware-Handshake (RTS/CTS)**, sodass der Speicher des Plotters nie überläuft und der Stift bei einem Abbruch sofort sicher abgehoben und geparkt wird.

### Was ist Plotter Studio gar nicht?
* **Kein Druckertreiber für Tintenstrahl-Großformatdrucker:** Großformatdrucker (z.B. HP DesignJet, Canon imagePROGRAF oder Epson SureColor) werden in der Praxis oft fälschlicherweise als „Plotter“ bezeichnet. Dabei handelt es sich jedoch um Pixel-Rasterdrucker mit Tintenpatronen. Plotter Studio steuert ausschließlich echte **mechanische Stiftplotter** an, die echte Schreibstifte über Papier führen.
* **Kein Zeichenprogramm:** Plotter Studio ersetzt weder Inkscape noch Adobe Illustrator oder CAD-Software. Sie zeichnen und entwerfen weiterhin in Ihrer gewohnten Software. Plotter Studio ist die nachgeschaltete Werkbank zum Vorbereiten, Prüfen und Ausführen des Plots.

### Was kann die Software heute schon?
* **Vektor-Import:** Schneller Import von SVG-Vektordateien per Drag & Drop oder Dateidialog.
* **Automatisches Farb-Clustering:** Grafikelemente werden anhand ihrer Strichfarbe automatisch auf die Stifte 1 bis 8 gruppiert.
* **Layout & Transformation:** Numerische Positionierung, Skalierung mit Proportions-Sperre, 50%/100%/200%-Schnelltasten, Einpassen auf das Papier, Zentrieren, Drehen und Spiegeln.
* **Objekt- & Ebenenverwaltung:** Z-Order (Zeichenreihenfolge per Drag & Drop ändern), Sichtbarkeit umschalten und Bearbeitung sperren.
* **Slicer-Pipeline & 2-Opt Pfadoptimierung:** Drastische Verkürzung der Plotzeiten durch Verbinden von Linienenden und Eliminierung unnötiger Eilgangswege.
* **Interaktive Simulation:** Zeitstrahl-Scrubber mit Play/Pause, 1x–10x Geschwindigkeit, türkisfarbener Visualisierung aller Leerfahrten (`Pen Up`) und Aufsetzpunkte.
* **Pre-Flight-Statistiken:** Exakte Berechnung von Zeichenweg, Leerweg, Ersparnis, Stiftwechseln und geschätzter Plotdauer.
* **Stift-Filterung:** Gezieltes Aktivieren einzelner Stifte (z.B. für manuelle Stiftwechsel oder Testdurchläufe).
* **Sicheres Live-Streaming:** Übertragung via RS-232 (USB-Adapter) oder TCP mit RTS/CTS-Handshake, Pause/Fortsetzen, Live-Werkzeugkopf im Canvas und Notfallabbruch (`ESC.K`, `PU;`, `SP0;`).
* **Multi-Plotter-Unterstützung:** Modular über lesbare YAML-Profile (`resources/devices/*.yaml`) für Rollen- und Flachbettplotter (Center-Origin & Bottom-Left).
* **Hardware-Diagnose & Kalibrierung:** Eigenständiges Terminal-Diagnosetool (`tools/xp500_probe.py`) und offizielles Kalibriermuster (`resources/calibration_plot_a3.svg`).
* **Integrierter Software-Emulator:** Vollwertiger virtueller Plotter (`VirtualPlotter`) zum sofortigen Testen ohne Hardware.

### Was kann Plotter Studio (noch) nicht bzw. was steht auf der Roadmap?
* **HP-GL/PLT-Import:** Das Einlesen bestehender HP-GL-Plotdateien ist für eine spätere Version geplant; aktuell dient SVG als universelles Quellformat, während HP-GL das optimierte Ausgabe- und Exportformat ist.
* **Direkter DXF-Import:** CAD-Dateien im DXF-Format müssen aktuell vor dem Import in Inkscape, QCAD oder LibreCAD als SVG gespeichert werden.
* **Schleppmesser-Kompensation (Drag-Knife Offset):** Für Schneideplotter (Vinyl-Cutter) ist eine Offset-Kompensation für drehbare Klingen wie in InkCut geplant; derzeit liegt der Fokus auf Stiftplottern.
* **Import von InkCut-Gerätedefinitionen:** Plotter Studio nutzt eigene, transparente YAML-Geräteprofile, die sich einfach für beliebige Fabrikate erstellen lassen.
* **G-Code-Plotter (Marlin / Grbl):** Die direkte Erzeugung von CNC-G-Code für 3D-Drucker oder Fräsen mit Stifthalter befindet sich in Planung; aktuell wird der Industriestandard HP-GL / MH-GL ausgegeben.

---

## Quickstart: In 5 Schritten zum ersten Plot

Sie müssen nicht warten, bis Ihre serielle Verkabelung steht: Mit dem integrierten Software-Emulator können Sie Plotter Studio sofort ausprobieren.

```
[ 1. Plotter verbinden ] -> [ 2. Blatt einrichten ] -> [ 3. SVG platzieren ] -> [ 4. Simulieren ] -> [ 5. Plotten ]
```

1. **Plotter verbinden oder Simulator starten:**
   * *Mit Hardware:* Schließen Sie den Plotter per RS-232-Nullmodemkabel an.  
     -> Siehe **[Kapitel 4: Hardware-Setup & Verkabelung](docs/anleitung/4-hardware-setup-und-test.md)**
   * *Ohne Hardware (Simulator):* Starten Sie den Simulator im Terminal mit `python3 -m plotter_studio.emulator --tcp 9999` und wählen Sie in Plotter Studio oben `Mutoh XP-500 Simulator (TCP)` aus.  
     -> Siehe **[Kapitel 1: Schnellstart mit Emulator](docs/anleitung/1-schnellstart-und-workflow.md#variante-b-schneller-test-mit-dem-software-simulator)**
2. **Blattgröße und Randprofil wählen:**
   * Klicken Sie auf **[ Seiteneinrichtung... ]**, wählen Sie z.B. DIN A3 Querformat und das Randprofil `EXP`. Ist ein Plotter verbunden, liest **[ Plotter abfragen ]** das Papierformat automatisch aus.  
     -> Siehe **[Kapitel 2: Blatt- & Seiteneinrichtung](docs/anleitung/2-layout-und-objektverwaltung.md#2-blatt--seiteneinrichtung)**
3. **Zeichnung importieren und ausrichten:**
   * Ziehen Sie eine beliebige `.svg`-Datei per Drag & Drop in das Fenster.
   * Nutzen Sie im Dock *Transformation* die Schnelltasten **[ Auf Blatt einpassen ]** oder **[ Auf Blatt zentrieren ]**.  
     -> Siehe **[Kapitel 2: Transformation & Objektverwaltung](docs/anleitung/2-layout-und-objektverwaltung.md#5-dock-transformation)**
4. **Plot simulieren und Fahrwege prüfen:**
   * Wechseln Sie oben in den Reiter **Ausgabe**.
   * Ziehen Sie den Schieberegler der Simulationsleiste oder klicken Sie auf Play: Überprüfen Sie den Toolhead-Cursor und die türkis gestrichelten Leerfahrten.  
     -> Siehe **[Kapitel 3: Ausgabe-Modus & Simulation](docs/anleitung/3-ausgabe-simulation-export.md#3-die-simulation-mit-dem-scrubber)**
5. **Plotten oder exportieren:**
   * Klicken Sie auf **[ Plot senden ]** für die direkte Ausgabe oder auf **[ Plotdatei (.hpgl) exportieren... ]**, um eine fertige HP-GL-Datei zu speichern.  
     -> Siehe **[Kapitel 3: Live-Plotten auf der Hardware](docs/anleitung/3-ausgabe-simulation-export.md#5-live-plotten-auf-der-hardware)**

---

## Vollständige Dokumentation

Das Handbuch ist in praxisorientierte Kapitel unterteilt:

* **[Benutzerhandbuch Übersicht (docs/anleitung/)](docs/anleitung/README.md)**
  * **[1. Schnellstart & Typischer Workflow](docs/anleitung/1-schnellstart-und-workflow.md):** Schritt-für-Schritt-Anleitung von SVG bis Stiftbewegung.
  * **[2. Layout-Modus & Objektverwaltung](docs/anleitung/2-layout-und-objektverwaltung.md):** Canvas, Werkzeuge, Seiteneinrichtung, Z-Order, Skalierung & Stifte.
  * **[3. Ausgabe-Modus, Simulation & Export](docs/anleitung/3-ausgabe-simulation-export.md):** Pipeline-Tuning, Pre-Flight-Statistiken, Scrubber-Simulation, Stift-Filterung & Live-Streaming.
  * **[4. Hardware-Setup, Kalibrierung & Diagnose](docs/anleitung/4-hardware-setup-und-test.md):** Nullmodem-Pinbelegung (RS-232 mit RTS/CTS), USB-Adapter, Hardware-Diagnosetool `xp500_probe.py`, der offizielle Kalibrierplot (`resources/calibration_plot_a3.svg`) und Anbindung weiterer Plotter.
  * **[5. Hintergrund: Konzepte, Algorithmen & Architektur (Deep-Dive)](docs/anleitung/5-konzepte-und-architektur.md):** Detaillierter Einblick in Slicer-Mathematik, 2-Opt TSP, Koordinatentransformationen und Streaming.
* **[Gerätedokumentation Mutoh XP-500](docs/devices/mutoh-xp500/README.md):** Befehlssatz MH-GL, Escape-Sequenzen, DIP-Schalter und Register.

---

## Schnellstart für Entwickler

```bash
# Virtuelle Umgebung und Installation
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Plotter Studio starten
plotter-studio

# Automatische Tests ausführen (66 Tests)
pytest
```


---

## Verwandte Projekte, Inspiration

Plotter Studio steht auf den Schultern bewährter Open-Source-Projekte aus der Plotter- und Maker-Community:

* **vpype (Antoine Beyeler, GPL-3.0-or-later):**  
  Das bekannte Kommandozeilenwerkzeug für generative Plotterkunst war die zentrale konzeptionelle Inspiration für die Trennung unserer Slicer-Pipeline in modulare Stufen: Linienzusammenfassung (*Merge*), Pfadumkehr (*Reverse*), Linienvereinfachung (*Ramer-Douglas-Peucker*) und insbesondere die 2-Opt-Pfadoptimierung (Traveling Salesperson Problem) zur Reduktion von Eilgang-Leerfahrten. Plotter Studio überträgt diese Konzepte in eine interaktive Desktop-GUI mit Live-Vorschau und Streaming.
* **MutohPlot (Oliver F., MIT-Lizenz):**  
  Diente bei der Entstehung von Plotter Studio als wertvolles Referenzprojekt und Testorakel für die Eigenheiten des Referenzplotters Mutoh XP-500. Die Dokumentation von MutohPlot half entscheidend beim Verständnis der Hardware-Randprofile (Normal, Expanded, Type 1/3), des Hard-Clip-Fensters und der Achsenorientierung. Es wurde **kein Code direkt übernommen**: Plotter Studio verwendet ein eigenständiges, hierarchisches Dokumenten- und Grafikmodell auf NumPy-Basis sowie eine native Hardware-Handshake-Übertragung.
* **InkCut (GPL-3.0-or-later):**  
  Ein etabliertes Open-Source-Programm für Schneideplotter. InkCut diente als architektonische Referenz für die geräteunabhängige Treiberabstraktion, alternative Plottersprachen (DMPL, CAMM-GL) und Filter für Schleppmesser. Auch hier wurde **kein Code übernommen**; die Implementierung in Plotter Studio ist eigenständig aufgebaut.

---

## Lizenz

Dieses Projekt ist unter der **GNU General Public License v3.0 or later (GPL-3.0-or-later)** lizenziert. Der vollständige Lizenztext befindet sich in der Datei [LICENSE.txt](LICENSE.txt).


## Entstehungsprozess mit KI Nutzung

Dieses Projekt entstand in einem kollaborativen Pair-Programming-Prozess zwischen einem menschlichen Entwickler und autonomen KI-Agenten.
