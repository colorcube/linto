# Plotter Studio – Benutzerhandbuch

Willkommen im offiziellen Benutzerhandbuch von **Plotter Studio**. Dieses Handbuch führt Sie von den ersten Schritten und dem typischen Arbeitsablauf über die Detailbedienung aller Werkzeuge bis hin zum Anschluss, der Kalibrierung und den mathematischen Hintergründen.

---

## Schnellübersicht: Ist Plotter Studio das Richtige für mich?

### Was ist Plotter Studio?
Plotter Studio ist ein spezialisierter **Slicer und Arbeitsbereich für Vektor-Stiftplotter**. Es schließt die Lücke zwischen Vektor-Grafikprogrammen (wie Inkscape, Illustrator, CAD oder generativer Kunst aus Python/Processing) und der physischen Mechanik von Zeichenmaschinen.

### Was ist es gar nicht?
* **Kein Druckertreiber für Tintenstrahl-Großformatdrucker:** Großformatige Fotodrucker (z.B. HP DesignJet, Epson SureColor, Canon imagePROGRAF) werden in Büros umgangssprachlich oft als „Plotter“ bezeichnet, sind aber Pixel-Rasterdrucker. Plotter Studio steuert ausschließlich echte **Vektor-Stiftplotter** an, die physische Stifte über Papier bewegen.
* **Kein Vektor-Zeichenprogramm:** Plotter Studio ersetzt weder Inkscape noch Adobe Illustrator. Sie erstellen Ihre Kunstwerke, CAD-Pläne oder Algorithmen in Ihrem gewohnten Werkzeug und exportieren sie als Standard-SVG oder HP-GL. Plotter Studio übernimmt dann das Layouten, Skalieren, Pfadoptimieren und Plotten.

### Was kann Plotter Studio heute schon?
* SVG- und HP-GL-Vektordateien laden, platzieren, numerisch skalieren (50%, 100%, 200%, Proportions-Sperre), drehen und auf dem Papier zentrieren.
* Randprofile für Rollen- und Flachbettplotter (z.B. EXP, NORM mit asymmetrischem Vorschubrand) und optische Papiererkennung (`OH;`).
* Automatisches Farb-Clustering auf bis zu 8 Stifte.
* Multi-Objektverwaltung mit Z-Order (Zeichenabfolge), Sichtbarkeit und Bearbeitungssperre.
* Intelligente Slicer-Pipeline: Pfade verbinden (Merge), Richtung optimieren (Reverse), Mikrostützpunkte glätten (Douglas-Peucker) und 2-Opt TSP Pfadoptimierung (40–70 % weniger Stift-Leerfahrten).
* Interaktive Simulation mit Zeitleiste (Scrubber), variabler Geschwindigkeit und Visualisierung aller Leerfahrten (`Pen Up`).
* Pre-Flight-Inspektion mit genauen Werten für Zeichenstrecke, Leerweg und geschätzter Laufzeit.
* Stift-Filterung zum selektiven Plotten einzelner Farben (z.B. für manuelle Stiftwechsel).
* Live-Streaming über RS-232 oder TCP mit striktem **RTS/CTS-Hardware-Handshake** (kein Pufferüberlauf).
* Sicherer Notfallabbruch (`ESC.K`, `PU;`, `SP0;`) schützt Papier und Stiftspitze.
* Offene Multi-Plotter-Architektur (Center-Origin & Bottom-Left) über YAML-Profile.
* Hardware-Diagnosetool (`tools/xp500_probe.py`), Kalibriermuster (`resources/calibration_plot_a3.svg`) und integrierter Software-Emulator (`VirtualPlotter`).

### Was kann Plotter Studio (noch) nicht bzw. was ist geplant?
* **Direkter DXF-Import:** Aktuell müssen CAD-Zeichnungen im DXF-Format vorab z.B. in Inkscape oder QCAD als SVG exportiert werden.
* **Schleppmesser-Kompensation (Drag-Knife Offset):** Für reine Schneideplotter (Vinyl-Cutter) ist eine Offset-Korrektur für drehbare Messerklingen wie in InkCut geplant, aktuell liegt der Fokus auf Stiftplottern.
* **Direkter Import von InkCut-Gerätedefinitionen:** Profile werden derzeit über die eigene, transparente YAML-Struktur (`resources/devices/*.yaml`) gepflegt.
* **G-Code-Plotter (Marlin / Grbl):** Die direkte Generierung von CNC-G-Code für 3D-Drucker mit Stifthalter befindet sich in der Konzeption; aktuell werden Plotter mit HP-GL / MH-GL angesteuert.

---

## Inhaltsverzeichnis

1. **[1. Schnellstart & Typischer Workflow](1-schnellstart-und-workflow.md)**
   * Mit oder ohne Hardware? (Nutzung des virtuellen Emulators)
   * Der 5-Schritte-Workflow von SVG bis zum fertigen Plot.
2. **[2. Layout-Modus & Objektverwaltung](2-layout-und-objektverwaltung.md)**
   * Benutzeroberfläche, Canvas, Millimeter-Lineale und Hard-Clip-Grenzen.
   * Seiteneinrichtung (DIN A4–A0, Randprofile EXP/NORM, optische Hard-Clip-Abfrage `OH;`).
   * Vektor-Import & automatisches Farb-Clustering.
   * Docks: *Objekte & Ebenen* (Z-Order, Sichtbarkeit, Sperren), *Transformation* (Proportions-Sperre, Schnelltasten, Drehen, Spiegeln) und *Stifte*.
3. **[3. Ausgabe-Modus, Simulation & Export](3-ausgabe-simulation-export.md)**
   * Die Optimierungs-Pipeline (Merge, Reverse, RDP, 2-Opt Pfadoptimierung).
   * Pre-Flight-Statistiken (Zeichenweg, Eilgang-Ersparnis, Stiftwechsel, Dauer).
   * Die Simulation mit dem Scrubber (Zeitleiste, 1x–10x, Leerwege-Darstellung).
   * Selektives Plotten (Stift-Filter) für manuelle Stiftwechsel oder Testläufe.
   * Live-Streaming, Pause und sicherer Notfallabbruch (`ESC.K`, `PU;`, `SP0;`).
   * Datei-Export nach HP-GL (`.hpgl`) und Plot-SVG (`.svg`).
4. **[4. Hardware-Setup, Kalibrierung & Diagnose](4-hardware-setup-und-test.md)**
   * RS-232 Verkabelung mit Nullmodem und zwingendem Hardware-Handshake (RTS/CTS), FTDI-Adapter und TCP.
   * Bedienfeld-Setup (19200 Baud, 8N1, Emulation HP-7585B, Rand EXP).
   * Hardware-Diagnosetool `tools/xp500_probe.py` (CTS, DSR, `OI`, `OF`, `OH`, `OE`, `OS`, ESC-Sequenzen).
   * Der offizielle Kalibrierplot (`resources/calibration_plot_a3.svg`): Nachmessen mit dem Stahllineal, Backlash-Prüfung, Randabstände und 8-Stift-Matrix.
   * Beliebige weitere Plotter einbinden (Geräte-Dialog und eigene YAML-Profile).
5. **[5. Hintergrund: Konzepte, Algorithmen & Architektur (Deep-Dive)](5-konzepte-und-architektur.md)**
   * Ausführliche mathematische und technische Hintergründe für Entwickler und Power-User.
   * Details zu 2-Opt TSP, Ramer-Douglas-Peucker, Koordinatentransformationen und der Streaming-Architektur.

---

## Weiterführende Gerätedokumentation
* **[Mutoh XP-500 Gerätedokumentation](../devices/mutoh-xp500/README.md):** Umfassende Transkription des Original-Handbuchs, MH-GL-Befehlssatz, Escape-Sequenzen und Register.
