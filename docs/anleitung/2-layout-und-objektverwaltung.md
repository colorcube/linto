# 2. Layout-Modus & Objektverwaltung

Der **Layout-Modus** ist die kreative Schaltzentrale von Plotter Studio. Hier arrangieren, skalieren und drehen Sie Ihre Vektorgrafiken auf dem gewählten Papierformat, weisen Stifte und Farben zu und prüfen die Abstände zu den Randbereichen des Plotters.

![Übersicht des Layout-Modus](../images/ui_overview_layout.png)

---

## 1. Aufbau der Benutzeroberfläche

Die Arbeitsumgebung ist übersichtlich in funktionale Bereiche unterteilt:

1. **Haupt-Canvas (Mitte):**
   * Zeigt das gewählte Papierblatt maßstabsgetreu in Millimetern an.
   * Ein **roter, gestrichelter Innenrahmen** markiert den physisch plottbaren Bereich (das sogenannte *Hard-Clip-Fenster*). Liegen Vektoren außerhalb dieses Rahmens, warnt Plotter Studio vor möglichem Beschnitt.
   * **Lineale (oben und links):** Zeigen präzise Millimeterangaben. Der Nullpunkt (0, 0) liegt an der oberen linken Ecke des Papiers.
   * **Maus-Navigation:**
     * **Mausrad:** Zoomt stufenlos hinein und heraus (zentriert auf den Mauszeiger).
     * **Mittlere Maustaste gedrückt halten:** Verschiebt den Bildausschnitt (Pan).
     * **Linke Maustaste:** Selektiert Objekte und ermöglicht direktes Verschieben per Drag & Drop.

2. **Werkzeug- & Geräteleiste (oben):**
   * Modus-Umschaltung zwischen **Layout-Modus** und **Ausgabe-Modus** (Plot-Vorschau).
   * Datei-Aktionen: **Öffnen** (`Strg+O`), **Speichern** (`Strg+S`), **Importieren** (`Strg+I`).
   * Ansichtssteuerung: **Blatt im Fenster einpassen** (`Strg+0`), **Hineinzoomen** (`+`), **Herauszoomen** (`-`).
   * Bearbeitung & Anordnung: Rückgängig (`Strg+Z`), Wiederholen (`Strg+Y`), Duplizieren (`Strg+D`), Löschen (`Entf`), Drehen (90° links/rechts), Mittig ausrichten, Auf Auswahl zoomen, 1:1 Originalgröße.
   * Schnelltaste für die **Seiteneinrichtung** (zeigt das aktive Format, z. B. `DIN A3 Quer`).
   * Schnellauswahl des aktiven Plotters (z. B. *Mutoh XP-500 (Seriell)*) und Schnelltaste für **Geräte-Einstellungen**.

3. **Rechte Werkzeug-Docks:**
   * **Dock "Objekte & Ebenen":** Baumansicht aller geladenen Dokumente, Gruppen und Pfade.
   * **Dock "Transformation":** Numerische Steuerung für Position (Bezug Blatt/Plottbereich), Drehung, Ausrichtung und Skalierung (Zoom, Original, Einpassen).
   * **Dock "Stifte & Farben":** Verwaltung der Stiftpalette und Zuordnung der Zeichenwerkzeuge.
   *(Tipp: Wenn Docks als Tabs gruppiert sind, dient der Tab-Reiter direkt als platzsparende Titelleiste.)*

---

## 2. Blatt- & Seiteneinrichtung

Vor dem Platzieren von Grafiken sollten Sie das gewünschte Blattformat und Randprofil festlegen. Klicken Sie in der Werkzeugleiste auf **[ Seiteneinrichtung... ]**.

![Dialog Seiteneinrichtung](../images/dialog_page_setup.png)

### Einstellungsoptionen im Dialog:
* **Standard-Formate:** Schnellauswahl aus DIN A4, A3, A2, A1 und A0.
* **Benutzerdefiniert:** Freie Eingabe von Breite und Höhe in Millimetern (z.B. für Sonderformate oder Zuschnitte von der Papierrolle).
* **Ausrichtung:** Umschaltung zwischen **Hochformat (Portrait)** und **Querformat (Landscape)**.
* **Randprofil (Margin Profile):**
  * *EXP (Expanded):* Minimale Ränder für maximale Zeichenfläche (Standard beim Mutoh XP-500: 25 mm Einzug, 5 mm an den anderen drei Seiten).
  * *NORM (Normal):* Größere Sicherheitsabstände (35 mm / 15 mm).
  * *TYPE1 / TYPE3:* Spezialprofile für Rollenpapier.
  * *default / minimal:* Symmetrische Ränder für Flachbettplotter und Schneideplotter.
* **Plotter abfragen (Live-Hard-Clip):**
  Ist ein Plotter per RS-232 oder Netzwerk verbunden, fragt dieser Button über den HP-GL-Befehl `OH;` die exakten Grenzen des aktuell eingespannten Papiers direkt von den optischen Sensoren der Hardware ab. Format und Maße werden automatisch übernommen.

---

## 3. Vektorgrafiken importieren

Plotter Studio unterstützt zwei direkt importierbare Vektorformate:
* **SVG (`.svg`):** Das empfohlene Hauptformat für Vektorgrafiken aus Inkscape, eigenen Skripten (Python, Processing, p5.js), Blender, Adobe Illustrator, Affinity Designer oder CAD-Exporten. Mathematische Kurven (Bézier-Kurven, Kreisbögen) bleiben beim Import verlustfrei erhalten und werden erst bei der Plot-Aufbereitung nach eingestellter Toleranz linearisiert.
* **HP-GL (`.hpgl`, `.plt`):** Direkter Import bestehender Plotter-Dateien (inklusive Stiftwahl `SP1`–`SP8`, Kreisen `CI`, Bögen `AA`/`AR`, Rechtecken `EA`/`RA` sowie `LB`-Textbeschriftungen über den integrierten 5×7-Vektorzeichensatz).

### Import-Möglichkeiten:
1. **Drag & Drop:** Ziehen Sie eine oder mehrere `.svg`-, `.hpgl`- oder `.plt`-Dateien direkt aus dem Dateimanager in das Canvas-Fenster.
2. **Datei öffnen (`Strg+O`):** Öffnet ein bestehendes Plotter-Studio-Projekt oder eine Vektordatei direkt als neues Dokument. Entsprechen die Abmessungen einer SVG-Datei keinem Standard-DIN-Format (z. B. 10×10 cm), wird das Blattformat automatisch als passendes benutzerdefiniertes Format eingerichtet.
3. **Importieren (`Strg+I`):** Lädt weitere Vektorgrafiken als zusätzliche Objekte in das bereits geöffnete Layout hinzu.

### Automatisches Farb-Clustering (SVG) & Stiftübernahme (HP-GL)
* **SVG:** Beim Import analysiert Plotter Studio alle Strichfarben (`stroke`) in der Datei und ordnet sie über einen wahrnehmungsgerechten Farbabstands-Algorithmus (Delta-E im CIE-Lab-Farbraum) automatisch den 8 Stiften der Palette zu.
* **HP-GL / PLT:** Die in der Plotdatei enthaltenen `SP1;`–`SP8;`-Befehle werden direkt den Stiften 1–8 in Plotter Studio zugewiesen.

---

## 4. Dock "Objekte & Ebenen" (Z-Order)

Das Dock **Objekte & Ebenen** listet alle geladenen Zeichnungselemente hierarchisch auf.

![Dock Objekte und Ebenen](../images/dock_objects_layers.png)

### Funktionen und Bedienelemente:
* **Sichtbarkeit (Auge-Symbol):** Schaltet ein Objekt oder eine Ebene unsichtbar. Unsichtbare Objekte werden weder im Canvas gerendert noch an den Plotter gesendet.
* **Sperren (Schloss-Symbol):** Schützt das Objekt vor versehentlichem Verschieben, Transformieren oder Löschen im Canvas.
* **Z-Reihenfolge (Zeichenabfolge):**
  * Objekte, die in der Liste weiter oben stehen, werden im Canvas über den darunter liegenden Objekten dargestellt.
  * Über die Schaltflächen **[ Nach oben ]** und **[ Nach unten ]** können Sie die Reihenfolge ändern.
  * *Praxistipp:* Bestimmen Sie so, welche Objekte zuerst oder zuletzt gezeichnet werden.
* **Verwaltung:**
  * **Doppelklick auf Namen:** Benennt das Objekt direkt um.
  * **[ Duplizieren ] (`Strg+D`):** Erstellt eine leicht versetzte Kopie des ausgewählten Objekts.
  * **[ Löschen ] (`Entf`):** Entfernt das Objekt aus dem Dokument (vollständig über `Strg+Z` rückgängig machbar).

---

## 5. Dock "Transformation"

Das Dock **Transformation** erlaubt die millimetergenaue Positionierung, Drehung, Ausrichtung und Skalierung eines oder mehrerer ausgewählter Objekte. Wenn Docks als Reiter (Tabs) gruppiert sind, wird die interne Titelleiste automatisch ausgeblendet und der Tab-Reiter dient als platzsparende Beschriftung.

![Dock Transformation](../images/dock_transformation.png)

### 1. Gruppe "Position":
* **Bezug:** Auswahl zwischen **Blatt** (gesamtes Papierformat) und **Plottbereich** (physisches Hard-Clip-Fenster des Plotters). Alle Koordinaten und Ausrichtungen orientieren sich an diesem gewählten Rahmen.
* **X / Y (mm):** Exakte Position der oberen linken Ecke des ausgewählten Objekts.
* **B / H (mm):** Exakte Breite und Höhe des Objekts in Millimetern.
* **Proportions-Sperre (Schloss-Symbol):**
  * *Aktiviert (geschlossen):* Änderungen an Breite oder Höhe passen die jeweils andere Achse proportional an.
  * *Deaktiviert (geöffnet):* Erlaubt unproportionales Skalieren / Verzerren.

### 2. Gruppe "Rotation":
* **[ -90° ] / [ +90° ]:** Schnelle Drehung der Auswahl um 90 Grad gegen den bzw. im Uhrzeigersinn.
* **Freier Winkel (`°`) & [ Drehen ]:** Dreht alle ausgewählten Objekte um einen beliebigen Winkel (`-360,0°` bis `+360,0°`).

### 3. Gruppe "Platzieren":
* **[ Horiz. Mittig ]:** Zentriert die Auswahl horizontal auf dem gewählten Bezugsrahmen (Blatt oder Plottbereich).
* **[ Vert. Mittig ]:** Zentriert die Auswahl vertikal auf dem gewählten Bezugsrahmen.
* **[ Zentrieren ] (Fadenkreuz):** Setzt die Auswahl exakt in die geometrische Mitte des Bezugsrahmens.

### 4. Gruppe "Skalierung":
* **Zoom (%):** Stufenlose numerische Skalierung in Prozent (100,0 % = Originalgröße).
* **[ + ] / [ - ]:** Schnelles Vergrößern bzw. Verkleinern in 10 %-Schritten (+10 % / -10 %).
* **[ Original ]:** Setzt die Abmessungen des Objekts sofort auf die 1:1 Originalgröße (100 %) der Quelldatei zurück.
* **[ Einpassen ]:** Skaliert die Auswahl proportional so groß wie möglich in den gewählten Bezugsrahmen (Blatt oder Plottbereich).
* **Rand (mm):** Einstellbarer Sicherheitsabstand beim Einpassen, um automatisch Randabstände zu wahren.

---

## 6. Stiftpalette & Farbzuweisung

Im Dock **Stifte & Farben** verwalten Sie die 8 logischen Stiftkanäle des Plotters (inklusive Strichstärke, Zeichengeschwindigkeit `VS` in `cm/s` und Anpressdruck `FS` in `g`):

| Stift | Standardfarbe | Hex-Code | Empfohlene Verwendung |
|---|---|---|---|
| **Stift 1** | Schwarz | `#000000` | Hauptkonturen, Beschriftung |
| **Stift 2** | Rot | `#d32f2f` | Hervorhebungen, Bemaßung |
| **Stift 3** | Blau | `#1976d2` | Hilfslinien, Schraffuren |
| **Stift 4** | Grün | `#388e3c` | Sekundäre Geometrie |
| **Stift 5** | Orange | `#f57c00` | Flächenschraffur |
| **Stift 6** | Magenta | `#7b1fa2` | Feine Details |
| **Stift 7** | Cyan | `#0097a7` | Entwürfe |
| **Stift 8** | Gelb | `#fbc02d` | Marker / Akzente |

Durch Rechtsklick auf ein Objekt im Canvas oder Auswahl im Stifte-Dock kann jedem Objekt jederzeit eine andere Stiftnummer zugewiesen werden.

---

## 7. Leitfaden: Vektorformate, Quellen & Workflows

Ein Stiftplotter zeichnet keine Pixelbilder, sondern fährt mathematische Vektorpfade mit physischen Stiften ab. Je nachdem, womit Sie Ihre Grafiken entwerfen – ob per eigenem Code (Python, Processing), in 3D-Programmen wie Blender, in Grafik-Editoren wie Inkscape oder in CAD-Systemen –, gibt es bewährte Wege, um optimale Daten für Plotter Studio zu erzeugen.

### 7.1 Eigene Skripte (SVG selbst generieren)

Für generative Kunst (Plotter Art) aus eigenen Python-, JavaScript- oder Processing-Skripten ist **SVG** das ideale Ausgabeformat. Wenn Sie beim Erzeugen der SVG-Datei vier einfache Regeln beachten, werden Maße und Stifte beim Import sofort 1:1 erkannt:

1. **Maßeinheit Millimeter (`mm`) und `viewBox` synchron halten:**
   Setzen Sie `width` und `height` explizit in `mm` und verwenden Sie dieselben Zahlenwerte in der `viewBox`. Dann entspricht `1.0` im Koordinatensystem Ihres Skripts exakt **1 Millimeter** auf dem Papier:
   ```xml
   <svg xmlns="http://www.w3.org/2000/svg"
        width="420mm" height="297mm"
        viewBox="0 0 420 297">
     <!-- 1 Einheit = 1 mm auf einem DIN A3 Querformat-Blatt -->
   </svg>
   ```
   *(Ohne Einheit interpretiert der SVG-Standard Zahlenwerte als Pixel bei 96 DPI, also `1 px ≈ 0,2646 mm`.)*

2. **Stiftzuweisung über die Strichfarbe (`stroke`):**
   Plotter Studio ordnet Pfade anhand ihrer `stroke`-Farbe den Stiften 1–8 zu. Wenn Sie in Ihrem Skript direkt die 8 Standard-Hex-Farben aus der Tabelle in [Abschnitt 6](#6-stiftpalette--farbzuweisung) verwenden (`#000000`, `#d32f2f`, `#1976d2`, `#388e3c`, `#f57c00`, `#7b1fa2`, `#0097a7`, `#fbc02d`), landet jeder Pfad garantiert und deterministisch auf dem gewünschten Stift:
   ```xml
   <!-- Landet automatisch auf Stift 1 (Schwarz) -->
   <path d="M 10,10 L 100,10 L 100,100 Z" fill="none" stroke="#000000" stroke-width="0.35" />

   <!-- Landet automatisch auf Stift 2 (Rot) -->
   <circle cx="55" cy="55" r="30" fill="none" stroke="#d32f2f" stroke-width="0.35" />
   ```
   Verwenden Sie abweichende Farben, gruppiert das Farb-Clustering bis zu 8 vorkommende Farbtöne automatisch auf die nächstliegenden Stifte.

3. **Immer `fill="none"` setzen:**
   Ein Stiftplotter kennt keine Flächenfüllung, sondern nur Konturlinien. Setzen Sie im Skript `fill="none"`, damit Sie schon im Browser oder Bildbetrachter exakt das sehen, was der Stift später zeichnet.

4. **Unterstützte SVG-Elemente:**
   Sie können `<path>`, `<line>`, `<polyline>`, `<polygon>`, `<rect>`, `<circle>` und `<ellipse>` sowie verschachtelte `<g transform="...">`-Gruppen beliebig kombinieren. Kurven (`C`, `Q`, `A`) werden verlustfrei eingelesen.

---

### 7.2 Inkscape als universeller Vor-Konverter

**Inkscape** ist das „Schweizer Taschenmesser" für die Plotter-Vorbereitung. Nahezu jedes Fremdformat lässt sich in Inkscape öffnen, prüfen und als sauberes SVG speichern:

* **Vektor- & Druckformate:** `.pdf`, `.eps`, `.ps` (wichtig: beim PDF-Import werden eingebettete Schriften oft als Doppellinien-Umrisse geladen), Adobe Illustrator (`.ai`), CorelDRAW (`.cdr`), Visio (`.vsd`/`.vsdx`), `.wmf`/`.emf`.
* **CAD-Formate:** `.dxf` (AutoCAD R12/R14/2000+) und `.hpgl`/`.plt`.
* **Echte Einlinienschriften (Hershey Text):**
  Normale Computerschriften (TrueType/OpenType) bestehen aus geschlossenen Außenkonturen (ein „I" wird als schmales Rechteck doppelt umfahren). Inkscape bringt unter `Erweiterungen → Text → Hershey Text` echte **Single-Line-Schriften** für Stiftplotter mit, die als einfache Mittellinie gezeichnet werden.
* **Rasterbilder (`.png`, `.jpg`) vektorisieren:**
  Über `Pfad → Bitmap nachzeichnen` bietet Inkscape den Modus **Mittellinien-Vektorisierung (Centerline Tracing / Autotrace)**. Anders als die normale Konturerkennung (die um jede schwarze Linie zwei Ränder legt) erzeugt das Centerline-Tracing eine einzelne Mittellinie für den Stift.

---

### 7.3 Blender (3D-Szenen als 2D-SVG ausgeben)

Blender eignet sich hervorragend für algorithmische 3D-Geometrie, Architektur-Drahtmodelle und Kamera-Perspektiven mit automatischer Verdeckungsberechnung (*Hidden Line Removal* – verdeckte Kanten auf der Rückseite von Objekten werden sauber weggelassen). Es gibt zwei direkt eingebaute Wege in Blender:

1. **Freestyle SVG Exporter (Mitgeliefertes Add-on):**
   * Unter `Edit → Preferences → Add-ons` nach **Freestyle SVG Exporter** suchen und aktivieren.
   * In den *Render Properties* **Freestyle** und **Freestyle SVG Export** einschalten.
   * Beim Rendern (`F12`) schreibt Blender eine fertige `.svg`-Datei mit allen sichtbaren Kanten aus Kamerasicht.
2. **Grease Pencil + Line Art Modifier (Ab Blender 3.x / 4.x, besonders schnell):**
   * `Add → Grease Pencil → Scene Line Art` zur Szene hinzufügen (berechnet Konturen, Silhouetten und Schnittkanten in Echtzeit im Viewport).
   * Anschließend über `File → Export → Grease Pencil as SVG (.svg)` direkt als Vektorgrafik für Plotter Studio exportieren.

---

### 7.4 HP-GL (`.hpgl` / `.plt`)

**HP-GL** (*Hewlett-Packard Graphics Language*) ist kein Entwurfsformat, sondern eine historische Maschinensteuerungssprache (`PU` = Stift hoch, `PD` = Stift runter, `SP` = Stiftwahl) mit einer festen Schrittauflösung von `1 Einheit = 0,025 mm`.

* **Direktimport in Plotter Studio:**
  Sie können bestehende `.hpgl`- und `.plt`-Dateien direkt über `Datei → Importieren` (`Strg+I`), `Datei → Projekt öffnen` (`Strg+O`) oder per Drag & Drop laden.
* **Unterstützte Befehle beim Import:**
  Neben absoluten/relativen Fahrbefehlen (`PA`, `PR`, `PU`, `PD`) und Stiftwechseln (`SP1`–`SP8`) unterstützt der aus dem Schwesterprojekt *MutohPlot* übernommene Parser auch geometrische Primitive (`CI` Kreise, `AA`/`AR` Kreisbögen, `EA`/`RA` Rechtecke) sowie **`LB`-Textbeschriftungen** (inkl. Zeichengröße `SI`, Richtung `DI`/`DR`, Neigung `SL` und Versatz `CP`) über einen integrierten 5×7-Vektorzeichensatz.
* **Hinweis zu Genauigkeit & externen Konvertern:**
  Da HP-GL-Dateien bereits für ein Zielgerät gerastert sind, sind Kurven darin in kurze Geradensegmente aufgelöst. Falls Sie alte HP-GL-Dateien außerhalb von Plotter Studio nach SVG umwandeln möchten, eignen sich dafür u. a. **Inkscape**, **`vpype`** (mit `vpype-hpgl`) oder das klassische Linux-Kommandozeilentool **`hp2xx`** (`hp2xx -m svg datei.hpgl -f datei.svg`).

---

### 7.5 DXF (CAD-Zeichnungen)

**DXF** (*Drawing Exchange Format*) ist der universelle 2D-Austauschstandard im CAD-, Architektur- und CNC-/Lasercutter-Bereich (AutoCAD, FreeCAD, QCAD, LibreCAD, Rhino, Fusion 360).

* **Besonderheiten beim Stiftplotten:**
  CAD-Zeichnungen nutzen häufig *Ebenen (Layer)* oder ACI-Farbnummern zur Unterscheidung von Körperkanten, Bemaßungen und Hilfslinien und enthalten oft unverbundene Einzellinien oder Bemaßungsblöcke.
* **Empfohlener Workflow:**
  Exportieren Sie die Zeichnung direkt aus dem CAD-Programm als **SVG** (z. B. in QCAD oder FreeCAD TechDraw) oder öffnen Sie die `.dxf`-Datei kurz in **Inkscape** (Skalierungsfaktor beim Import auf `1.0` für Millimeter belassen) und speichern Sie sie als `.svg` für Plotter Studio.

---

### 7.6 Empfohlene Ressourcen, Tools & Community-Sammlungen

Für kreatives Arbeiten, generative Kunst und den Austausch mit anderen Plotter-Enthusiasten gibt es eine lebendige Open-Source- und Maker-Community. Folgende Anlaufstellen sind besonders empfehlenswert:

* **[Awesome Plotters](https://github.com/beardicus/awesome-plotters):**
  *Die* zentrale, kuratierte Linksammlung auf GitHub für computergesteuerte Zeichenmaschinen, Plotter-Art, Software, Firmware, mathematische Bibliotheken und Hardware-Projekte. Ein idealer Startpunkt für Recherchen.
* **[Drawingbots.net](https://drawingbots.net/):**
  Der zentrale internationale Community-Hub für Plotter-Künstler und Zeichenroboter-Bauer. Bietet Software- und Hardware-Verzeichnisse, Tutorials, Interviews und einen sehr aktiven **Discord-Server** zum Erfahrungsaustausch über Stifte, Papiere und Mechanik.
* **[vpype](https://github.com/abey79/vpype) & [vsketch](https://github.com/abey79/vsketch):**
  * *vpype:* Das „Schweizer Taschenmesser" auf der Kommandozeile für Plotter-Vektoren (automatisches Erzeugen von Schraffuren (*Hatching*), Skalieren, Filtern und Transformieren von SVG-Dateien).
  * *vsketch:* Ein auf *vpype* und Python aufbauendes Entwicklungs-Framework, das speziell für generative Plotter-Kunst mit bequemer Vorschau und automatischem SVG-Export geschaffen wurde.
* **[Turtletoy](https://turtletoy.net/):**
  Eine faszinierende Online-Plattform für generative Kunst im Browser. Skripte werden mit einer an Python-Turtle angelehnten API geschrieben und können direkt als saubere, optimierte SVG-Dateien für den Plotter heruntergeladen werden.
* **[ln (3D Line Art Engine)](https://github.com/fogleman/ln):**
  Eine blitzschnelle 3D-zu-Vektor-Engine in Go (auch als Python-Bindings verfügbar), die 3D-Modelle (`.obj`, `.stl`) und mathematische Funktionen in 2D-Vektorzeichnungen umrechnet und verdeckte Linien (*Hidden Line Removal*) meisterhaft handhabt.
* **[Reddit r/PlotterArt](https://www.reddit.com/r/PlotterArt/):**
  Eine sehr aktive Reddit-Community mit Inspirationen, Praxistests verschiedener Stiftarten (Fineliner, Gelschreiber, Tusche, Marker) und Papiersorten sowie Hilfestellungen bei kniffligen Plotter-Problemen.


