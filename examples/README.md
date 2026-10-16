# Plotter Studio – Beispieldateien (`examples/`)

Dieses Verzeichnis enthält Beispielgrafiken im **SVG**- und **HP-GL**-Format zum Testen des Layouts, der Stiftzuweisung und der Plotterausgabe.

---

## 🚀 Klassische HP-GL Plotter-Demos

Die folgenden Dateien sind historische Klassiker aus der Ära der Stiftplotter und CAD-Pioniere:

### 1. `space-columbia.hpgl` (Space Shuttle Columbia)
* **Herkunft:** Die legendäre original CAD-Musterzeichnung `COLUMBIA.DWG` aus den frühen AutoCAD-Versionen (1980er Jahre).
* **Besonderheit:** **Mehrfarbige Stift-Demonstration** über 6 verschiedene Stiftnummern (`SP1` bis `SP6`).
* **Inhalt:** Perspektivische Draufsicht des Space Shuttle Orbiters mit Hitzekacheln, Triebwerken und Frachtraum sowie dem klassischen Schriftzug *„The AutoCAD DRAWING COLUMBIA“*.
* **Statistik:** 597 Pfade, 2.723 Punkte, 6 Stiftebenen.

### 2. `space-shuttle-launch.hpgl` (Space Shuttle Start)
* **Inhalt:** Das Space Shuttle beim Senkrechtstart mit Außentank, Feststoffraketen und dynamischen Rauch- und Abgaswolken.
* **Statistik:** 226 Pfade, 4.481 Punkte.

### 3. `imperial-walker.hpgl` (Star Wars AT-AT Walker)
* **Inhalt:** Detaillierte technische Strichzeichnung des imperialen Kampfläufers All Terrain Armored Transport (AT-AT) aus *Star Wars: Das Imperium schlägt zurück*.
* **Statistik:** 464 Pfade, 4.195 Punkte.

### 4. `death-star.hpgl` (Star Wars Todesstern & TIE-Fighter)
* **Inhalt:** Der Todesstern mit Superlaser-Schüssel im Weltraum, umgeben von einem Geschwader anfliegender TIE-Fighter und Sternenfeldern.
* **Statistik:** 333 Pfade, 4.243 Punkte.

---

## 🎨 SVG-Vektorgrafiken

* **`color_mandala.svg`:** Mehrfarbiges geometrisches Mandala zur Demonstration von Stiftfarben und Layer-Splitting.
* **`calibration_grid.svg`:** Geometrisches Testgitter zur Überprüfung von Linienparallelität und rechten Winkeln.
* **`TEST_10cm.svg`:** 100 × 100 mm Quadrat zur messtechnischen Überprüfung der Skalierungsgenauigkeit mit dem Stahllineal.

---

## 💡 Verwendung in Plotter Studio

1. Klicken Sie auf **Datei → Importieren...** (`Strg+I`) oder ziehen Sie eine der Dateien einfach per **Drag & Drop** in das Anwendungsfenster.
2. Im Dock **Transformation** können Sie die Motive mit `[ Blatt zentrieren ]` oder `[ Einpassen ]` mit einem Klick auf Ihr gewähltes Papierformat (z. B. DIN A4 oder DIN A3) skalieren und ausrichten.
3. Wechseln Sie in den **Plot-Modus** (`Strg+P`), um die Zeichnung in der Live-Simulation abzufahren oder direkt an den Plotter zu senden.
