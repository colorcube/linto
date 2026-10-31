# Analyse: InkCut (Plotter-Treiber, Protokolle & Filter)

Stand: 2026-10-15 · Analyse des InkCut-Codebestands ([github.com/inkcut/inkcut](https://github.com/inkcut/inkcut)).
Dient als Referenz für Geräteprofile, Protokolle (DMPL, CAMM-GL, GPGL, G-Code) und Schleppmesser-Algorithmen in LINTO.


---

### Die 4 interessantesten Funde in InkCut

#### 1. Fertige Geräte-Bibliothek (`device/drivers/manifest.enaml`)
InkCut bringt ein Verzeichnis erprobter Plotter-Modelle mit Bettabmessungen, Protokollen und gerätespezifischen Besonderheiten mit:
* **Roland:** PNC-900, PNC-950, PNC-1000, CAMM-1 (CM-24, CX-24), Stika SV-8 / SV-12 / SV-15 (`swap_xy = True`)
* **Graphtec:** CE5000-60, FC8000-130
* **Silhouette:** Cameo 4, Portrait (inkl. spezifischer Skalierungsfaktoren `5.64` und Achsenspiegelung)
* **Summa:** D120R, T600
* **US Cutter / Creation / SeikiTech:** Refine MH-721, MH-1351, LaserPoint, PCut CT-630
* **Mimaki, Secabo, Ioline, Redsail**

> **Nutzen für uns:** Wir können diese Daten direkt in deklarative YAML-Geräteprofile (`resources/devices/*.yaml`) für LINTO übernehmen.

---

#### 2. Emitter für alternative Plotter-Sprachen (`device/protocols/`)
LINTO spricht aktuell HP-GL. InkCut zeigt auf jeweils ca. 30–60 Zeilen Python die exakten Kommandos für alternative Protokolle:
* **DMPL (`dmpl.py`):** Houston Instrument DMPL (für Summa, Houston, US Cutter; Modi 1–4 und 6 wie `;:HAEC1`, `EC` Stiftwahl, `BP` Stiftkraft).
* **Roland CAMM-GL (`camm.py`):** `^IN;`, `D{x},{y};`, `M{x},{y};`.
* **Graphtec GPGL (`gpgl.py`):** `  H`, `D{x},{y}`, `M{x},{y}`, `!{v}`, `FX{f},1`.
* **G-Code (`gcode.py`):** Für 3D-Drucker oder Fräsen mit Stifthalter (`G0`/`G1`, Werkzeughub über Z-Achse oder Servo/M3).

> **Nutzen für uns:** Wenn wir unseren Emitter modular gestalten (`core/emitter/`), können wir diese Dialekte sehr einfach als Plug-ins ergänzen.

---

#### 3. Schneideplotter-Filter (`device/filters/`)
Falls mit LINTO auch Schneideplotter (Vinylfolie) betrieben werden sollen:
* **Blade Offset (`blade_offset.py`):** Ein Schleppmesser (Drag Knife) dreht sich passiv im Halter. Die Klingenspitze läuft dem Drehpunkt um ca. 0.25 mm hinterher. Ohne Schleppmesser-Kompensation werden spitze Ecken rund gezogen. Der Filter berechnet Anstellwinkel und Ausgleichsbögen in den Ecken.
* **Overcut (`overcut.py`):** Verlängert geschlossene Pfade um 0.5–1 mm über den Startpunkt hinaus, damit sich geschnittene Folien ("Entgittern") sauber lösen, ohne dass Ecken hängen bleiben.
* **Min Line (`min_line.py`):** Filtert Sub-Millimeter-Zittern/Rauschen heraus.

---

#### 4. Transports & Buffer-Handling (`device/transports/` & `device/plugin.py`)
* **Spooler / CUPS (`transports/printer/`):** Neuere Schneideplotter (z. B. Silhouette Cameo, Brother, neuere Graphtec) melden sich als USB-Drucker an. InkCut kann Jobs über das OS-Drucksystem/Spooler abschicken.
* **Software-Throttling:** InkCut berechnet die Bewegungsdistanz \(d\) und verzögert das Senden (`delay = d / rate`), falls Plotter über billige USB-Seriell-Adapter angeschlossen sind, die Hardware-Handshakes (CTS/RTS) ignorieren und deren Puffer sonst überlaufen würden.

---

### Was LINTO schon jetzt besser macht
1. **Moderne Geometrie:** InkCut arbeitet komplett auf `QPainterPath` / `QPolygon` von Qt, eng verwoben mit Enaml und Twisted. LINTO arbeitet auf reinem NumPy (`(N, 2)` float64 in Millimetern) – das ist um Größenordnungen schneller, thread-sicher und headless testbar.
2. **Pfadoptimierung (TSP):** InkCut macht nur ein einfaches Greedy über einen KD-Tree. Unser **Greedy + 2-Opt** (inklusive Richtungs-Umkehr offener Pfade) erzielt deutlich kürzere Eilgangwege (50–80% Ersparnis).
3. **Simulation:** Unsere Plot-Simulation mit Stiftbreiten, Vor- und Nachlauf-Ghosting, Knotenpunkten und interaktivem Scrubber ist wesentlich detaillierter.
