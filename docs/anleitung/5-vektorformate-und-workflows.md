# 5. Leitfaden: Vektorformate, Quellen & Workflows

Ein Stiftplotter zeichnet keine Pixelbilder, sondern fährt mathematische Vektorpfade mit physischen Stiften ab. Je nachdem, womit du deine Grafiken entwirfst – ob per eigenem Code (Python, Processing), in 3D-Programmen wie Blender, in Grafik-Editoren wie Inkscape oder in CAD-Systemen –, gibt es bewährte Wege, um optimale Daten für Plotter Studio zu erzeugen.

---

## 1. Eigene Skripte (SVG selbst generieren)

Für generative Kunst (Plotter Art) aus eigenen Python-, JavaScript- oder Processing-Skripten ist **SVG** das ideale Ausgabeformat. Wenn du beim Erzeugen der SVG-Datei vier einfache Regeln beachtest, werden Maße und Stifte beim Import sofort 1:1 erkannt:

1. **Maßeinheit Millimeter (`mm`) und `viewBox` synchron halten:**
   Setze `width` und `height` explizit in `mm` und verwende dieselben Zahlenwerte in der `viewBox`. Dann entspricht `1.0` im Koordinatensystem deines Skripts exakt **1 Millimeter** auf dem Papier:
   ```xml
   <svg xmlns="http://www.w3.org/2000/svg"
        width="420mm" height="297mm"
        viewBox="0 0 420 297">
     <!-- 1 Einheit = 1 mm auf einem DIN A3 Querformat-Blatt -->
   </svg>
   ```
   *(Ohne Einheit interpretiert der SVG-Standard Zahlenwerte als Pixel bei 96 DPI, also `1 px ≈ 0,2646 mm`.)*

2. **Stiftzuweisung über die Strichfarbe (`stroke`):**
   Plotter Studio ordnet Pfade anhand ihrer `stroke`-Farbe den Stiften 1–8 zu. Wenn du in deinem Skript direkt die 8 Standard-Hex-Farben verwendest, landet jeder Pfad garantiert und deterministisch auf dem gewünschten Stift:
   
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

   ```xml
   <!-- Landet automatisch auf Stift 1 (Schwarz) -->
   <path d="M 10,10 L 100,10 L 100,100 Z" fill="none" stroke="#000000" stroke-width="0.35" />

   <!-- Landet automatisch auf Stift 2 (Rot) -->
   <circle cx="55" cy="55" r="30" fill="none" stroke="#d32f2f" stroke-width="0.35" />
   ```
   Verwendest du abweichende Farben, gruppiert das Farb-Clustering bis zu 8 vorkommende Farbtöne automatisch auf die nächstliegenden Stifte.

3. **Immer `fill="none"` setzen:**
   Ein Stiftplotter kennt keine Flächenfüllung, sondern nur Konturlinien. Setze im Skript `fill="none"`, damit du schon im Browser oder Bildbetrachter exakt das siehst, was der Stift später zeichnet.

4. **Unterstützte SVG-Elemente:**
   Du kannst `<path>`, `<line>`, `<polyline>`, `<polygon>`, `<rect>`, `<circle>`, `<ellipse>`, `<text>` (inkl. `<tspan>`) sowie verschachtelte `<g transform="...">`-Gruppen beliebig kombinieren. Kurven (`C`, `Q`, `A`) werden verlustfrei eingelesen.
   * **SVG-`<text>`-Import (Automatische Einlinien-Ersatzschrift):** Nicht in Pfade umgewandelte `<text>`-Elemente werden beim Import automatisch durch eine integrierte **Hershey-Simplex-Einlinienschrift** (inkl. deutscher Umlaute, `ß` und gängiger Akzentzeichen) unter Beachtung von `font-size`, `text-anchor` (`start`, `middle`, `end`) und `dx`/`dy`-Versatz ersetzt. Plotter Studio gibt dabei bewusst weiterhin einen Hinweis in der Statusleiste und in der Pre-Flight-Inspektion aus, dass `<text>` durch eine einfache Linienschrift ersetzt wurde (wer die exakten Umrisskonturen einer bestimmten TrueType-Schrift plotten möchte, wandelt den Text zuvor im Grafikprogramm in Pfade um).

---

## 2. Inkscape als universeller Vor-Konverter

**Inkscape** ist das „Schweizer Taschenmesser" für die Plotter-Vorbereitung. Nahezu jedes Fremdformat lässt sich in Inkscape öffnen, prüfen und als sauberes SVG speichern:

* **Vektor- & Druckformate:** `.pdf`, `.eps`, `.ps` (wichtig: beim PDF-Import werden eingebettete Schriften oft als Doppellinien-Umrisse geladen), Adobe Illustrator (`.ai`), CorelDRAW (`.cdr`), Visio (`.vsd`/`.vsdx`), `.wmf`/`.emf`.
* **CAD-Formate:** `.dxf` (AutoCAD R12/R14/2000+) und `.hpgl`/`.plt`.
* **Echte Einlinienschriften (Hershey Text):**
  Normale Computerschriften (TrueType/OpenType) bestehen aus geschlossenen Außenkonturen (ein „I" wird als schmales Rechteck doppelt umfahren). Während Plotter Studio direkte SVG-`<text>`-Elemente automatisch durch seine eingebaute **Hershey-Simplex**-Einlinienschrift ersetzt, bringt Inkscape unter `Erweiterungen → Text → Hershey Text` noch weitere **Single-Line-Schriftstile** (z. B. Script, Serif, Gothic) mit – oder erlaubt über `Pfad → Objekt in Pfad umwandeln` das gezielte Plotten von Umriss-Schriften.
* **Rasterbilder (`.png`, `.jpg`) vektorisieren:**
  Über `Pfad → Bitmap nachzeichnen` bietet Inkscape den Modus **Mittellinien-Vektorisierung (Centerline Tracing / Autotrace)**. Anders als die normale Konturerkennung (die um jede schwarze Linie zwei Ränder legt) erzeugt das Centerline-Tracing eine einzelne Mittellinie für den Stift.

---

## 3. Blender (3D-Szenen als 2D-SVG ausgeben)

Blender eignet sich hervorragend für algorithmische 3D-Geometrie, Architektur-Drahtmodelle und Kamera-Perspektiven mit automatischer Verdeckungsberechnung (*Hidden Line Removal* – verdeckte Kanten auf der Rückseite von Objekten werden sauber weggelassen). Es gibt zwei direkt eingebaute Wege in Blender:

1. **Freestyle SVG Exporter (Mitgeliefertes Add-on):**
   * Unter `Edit → Preferences → Add-ons` nach **Freestyle SVG Exporter** suchen und aktivieren.
   * In den *Render Properties* **Freestyle** und **Freestyle SVG Export** einschalten.
   * Beim Rendern (`F12`) schreibt Blender eine fertige `.svg`-Datei mit allen sichtbaren Kanten aus Kamerasicht.
2. **Grease Pencil + Line Art Modifier (Ab Blender 3.x / 4.x, besonders schnell):**
   * `Add → Grease Pencil → Scene Line Art` zur Szene hinzufügen (berechnet Konturen, Silhouetten und Schnittkanten in Echtzeit im Viewport).
   * Anschließend über `File → Export → Grease Pencil as SVG (.svg)` direkt als Vektorgrafik für Plotter Studio exportieren.

---

## 4. HP-GL (`.hpgl` / `.plt`)

**HP-GL** (*Hewlett-Packard Graphics Language*) ist kein Entwurfsformat, sondern eine historische Maschinensteuerungssprache (`PU` = Stift hoch, `PD` = Stift runter, `SP` = Stiftwahl) mit einer festen Schrittauflösung von `1 Einheit = 0,025 mm`.

* **Direktimport in Plotter Studio:**
  Du kannst bestehende `.hpgl`- und `.plt`-Dateien direkt über `Datei → Importieren` (`Strg+I`), `Datei → Projekt öffnen` (`Strg+O`) oder per Drag & Drop laden.
* **Unterstützte Befehle beim Import:**
  Neben absoluten/relativen Fahrbefehlen (`PA`, `PR`, `PU`, `PD`) und Stiftwechseln (`SP1`–`SP8`) unterstützt der aus dem Schwesterprojekt *MutohPlot* übernommene Parser auch geometrische Primitive (`CI` Kreise, `AA`/`AR` Kreisbögen, `EA`/`RA` Rechtecke) sowie **`LB`-Textbeschriftungen** (inkl. Zeichengröße `SI`, Richtung `DI`/`DR`, Neigung `SL` und Versatz `CP`) über einen integrierten 5×7-Vektorzeichensatz.
* **Hinweis zu Genauigkeit & externen Konvertern:**
  Da HP-GL-Dateien bereits für ein Zielgerät gerastert sind, sind Kurven darin in kurze Geradensegmente aufgelöst. Falls du alte HP-GL-Dateien außerhalb von Plotter Studio nach SVG umwandeln möchtest, eignen sich dafür u. a. **Inkscape**, **`vpype`** (mit `vpype-hpgl`) oder das klassische Linux-Kommandozeilentool **`hp2xx`** (`hp2xx -m svg datei.hpgl -f datei.svg`).

---

## 5. DXF (CAD-Zeichnungen)

**DXF** (*Drawing Exchange Format*) ist der universelle 2D-Austauschstandard im CAD-, Architektur- und CNC-/Lasercutter-Bereich (AutoCAD, FreeCAD, QCAD, LibreCAD, Rhino, Fusion 360).

* **Besonderheiten beim Stiftplotten:**
  CAD-Zeichnungen nutzen häufig *Ebenen (Layer)* oder ACI-Farbnummern zur Unterscheidung von Körperkanten, Bemaßungen und Hilfslinien und enthalten oft unverbundene Einzellinien oder Bemaßungsblöcke.
* **Empfohlener Workflow:**
  Exportiere die Zeichnung direkt aus dem CAD-Programm als **SVG** (z. B. in QCAD oder FreeCAD TechDraw) oder öffne die `.dxf`-Datei kurz in **Inkscape** (Skalierungsfaktor beim Import auf `1.0` für Millimeter belassen) und speichere sie als `.svg` für Plotter Studio.

---

> [!TIP]
> Weiterführende Werkzeuge (z. B. `vpype`, `vsketch`, `ln`), Single-Line-Schriften sowie die zentralen Community-Hubs (**Awesome Plotters**, Drawingbots.net, Reddit) findest du in **[Kapitel 7: Empfohlene Ressourcen, Tools & Community-Sammlungen](7-ressourcen-tools-und-community.md)**.

