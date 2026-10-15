# 5. Hintergrund: Konzepte, Algorithmen & Architektur (Deep-Dive)

Dieses Kapitel bietet einen detaillierten technischen Einblick in die mathematischen und maschinennahen Hintergründe von Plotter Studio: Wie der Slicer intern arbeitet, wie Algorithmen wie 2-Opt TSP und RDP funktionieren, wie Koordinaten mathematisch transformiert werden und wie die Multi-Plotter-Architektur aufgebaut ist.

---

## 1. Warum reicht ein normaler Druckertreiber oder Inkscape nicht?

Beim Drucken auf Tintenstrahl- oder Laserdruckern wird ein Dokument in ein Raster aus mikroskopischen Farbpunkten aufgelöst. Stiftplotter hingegen sind **kinematische Vektormaschinen**: Sie führen einen physikalischen Stift (Fineliner, Kugelschreiber, Tuschestift, Pinsel) mit Motoren über Papier oder Folie.

Daraus ergeben sich fundamentale Herausforderungen, die herkömmliche Drucksysteme nicht bewältigen können:

1. **Pfad-Reihenfolge & Stift-Leerfahrten (Travel Distance):**
   In SVG- oder CAD-Dateien liegen Pfade oft in Entstehungs- oder Gruppierungsreihenfolge vor. Würde man diese direkt an den Plotter senden, springt der Schreibkopf tausende Male unkoordiniert quer über das gesamte Papier hin und her. Das Resultat sind extreme Plotzeiten, unnötiger mechanischer Verschleiß und verwaschene Linien durch Tropfenbildung beim Aufsetzen.
2. **Physikalische Stiftabnutzung & Geschwindigkeit:**
   Jedes Absenken des Stifts (`Pen Down`) belastet die Feder und Spitze. Linien müssen kontinuierlich durchgezogen werden, ohne ständig auf- und abzusetzen.
3. **Pufferüberläufe & serielle Verbindungsabbrüche:**
   Klassische Plotter besitzen typischerweise serielle Schnittstellen (RS-232) und kleine Hardware-Puffer (oft nur 1 KB bis 64 KB). Sendet man eine mehrere Megabyte große HP-GL-Datei ungebremst an den Anschluss, stürzt der Plotter ab oder verschluckt Segmente.
4. **Koordinatentransformation & asymmetrische Ränder:**
   Vektorgrafiken beginnen oben links (0, 0) mit positiven Werten nach rechts und unten. Plotter arbeiten jedoch häufig mit **Center-Origin** (0,0 in der Blattmitte) oder **Bottom-Left** (0,0 unten links) in proprietären Plotter-Schritten (z.B. 40 Einheiten/mm). Rollenplotter benötigen an der Vorschubkante mehr Rand für die Andruckrollen als an den Seiten.

---

## 2. Der Plotter-Slicer: Funktionsweise der Pipeline

Plotter Studio fungiert für Stiftplotter ähnlich wie ein **Slicer** in der 3D-Druckwelt: Es nimmt eine Vektorgeometrie entgegen und übersetzt sie über eine mehrstufige Pipeline in optimierte Fahrbefehle für die Hardware.

```
[ SVG / Vektordatei ]
        │
        ▼
1. Import & Farbclustering (Zuordnung auf 1–8 physikalische Stifte)
        │
        ▼
2. Segment-Merge & Reversal (Pfade verbinden & Richtung optimieren)
        │
        ▼
3. RDP-Vereinfachung (Douglas-Peucker zur Glättung überflüssiger Knoten)
        │
        ▼
4. 2-Opt Pfadoptimierung (Minimierung der Stift-Leerfahrten)
        │
        ▼
5. Koordinatentransformation (Blatt-mm ➔ Plotter-Units mit Randversatz)
        │
        ▼
[ Live-Streaming mit RTS/CTS-Handshake oder HP-GL-Export ]
```

### Die Optimierungsstufen im Detail:

* **Farb-Clustering:** Grafikelemente mit unterschiedlichen RGB-Farben werden automatisch auf die verfügbaren Stiftkanäle (z.B. Stift 1 bis 8) gruppiert. Innerhalb eines Stifts werden alle Pfade zusammengefasst, um Werkzeugwechsel auf das absolute Minimum zu reduzieren.
* **Linienzusammenfassung (Merge):** Berühren sich zwei Linienenden innerhalb einer einstellbaren Toleranz (z.B. 0,1 mm), verbindet Plotter Studio diese zu einer zusammenhängenden Polylinie. Der Stift bleibt auf dem Papier, statt angehoben und neu aufgesetzt zu werden.
* **Pfade umkehren (Reversal):** Polylinien können in beiden Richtungen gezeichnet werden. Die Pipeline kehrt Liniensegmente bei Bedarf automatisch um, wenn das Linienende näher am nächsten Pfad liegt.
* **RDP-Vereinfachung (Ramer-Douglas-Peucker):** CAD-Programme und Freihand-Vektoren erzeugen oft Tausende mikroskopische Stützpunkte auf geraden Linien. Der RDP-Algorithmus filtert redundante Punkte heraus, ohne die visuelle Kontur zu verändern. Das verhindert Stottern der Schrittmotoren.
* **2-Opt Pfadoptimierung (Traveling Salesperson Problem):** Ein heuristischer Optimierungsalgorithmus ordnet die Reihenfolge aller Vektoren so an, dass die Gesamtstrecke der Eilgang-Leerfahrten (`Pen Up`) drastisch minimiert wird (oft um **40 % bis 70 %**).

---

## 3. Koordinatensysteme und Nullpunkte

In Plotter Studio arbeiten Sie immer mit intuitiven **Blattkoordinaten**:
* Einheit: Millimeter (mm).
* Nullpunkt: Oben links an der Papierkante.
* X-Achse nach rechts, Y-Achse nach unten.

Für die Ausgabe rechnet Plotter Studio die Geometrie in die nativen Koordinaten des Zielgeräts um:

### Center-Origin vs. Bottom-Left

```
     Bottom-Left (z.B. Roland, HP-GL Generic)        Center-Origin (z.B. Mutoh XP-500)
    ┌───────────────────────────┐               ┌───────────────────────────┐
    │                           │               │             ▲ +Y          │
    │                           │               │             │             │
    │                           │               │       -X ───┼───► +X      │
    │                           │               │           (0,0)           │
    │(0,0)                      │               │             │             │
    └───────────────────────────┘               └───────────────────────────┘
```

1. **Center-Origin (Mittelpunkt-Ursprung):**
   Geräte wie der **Mutoh XP-500** (und viele Großformatplotter) setzen (0,0) exakt in das Zentrum des nutzbaren Hard-Clip-Fensters. Koordinaten können positiv und negativ sein.
2. **Bottom-Left (Unten-Links-Ursprung):**
   Klassische Tisch- und Flachbettplotter (wie Roland DXY oder HP 7475A) haben ihren Ursprung in der unteren linken Ecke mit ausschließlich positiven Koordinaten.

### Randprofile & Asymmetrische Ränder
Rollenplotter benötigen an der vorderen Blattkante einen Sicherheitsabstand für den Greifmechanismus und die Andruckrollen. Beim Mutoh XP-500 sind folgende Randprofile hinterlegt:

| Randprofil | Einzug (Vorderkante) | Hinterkante | Links | Rechts | Einsatzzweck |
|---|---|---|---|---|---|
| **EXP** (Expanded) | 25,0 mm | 5,0 mm | 5,0 mm | 5,0 mm | Maximaler Zeichenbereich (Standard) |
| **NORM** (Normal) | 35,0 mm | 15,0 mm | 15,0 mm | 15,0 mm | Große Sicherheitsränder |
| **TYPE1** | 25,0 mm | 5,0 mm | 11,0 mm | 11,0 mm | Rollenpapier mit Seitenrand |
| **TYPE3** | 25,0 mm | 10,0 mm | 10,0 mm | 10,0 mm | Alternative für Endlospapier |

Plotter Studio visualisiert diese Ränder im Canvas als gepunktete Linie und warnt vor Beschnitt.

---

## 4. Hardware-Schnittstelle & Streaming-Sicherheit

Die Kommunikation mit physischen Plottern erfolgt über serielle RS-232-Schnittstellen (bzw. USB-Seriell-Adapter) oder TCP-Netzwerk-Sockets.

### Flusssteuerung (Flow-Control)
Plotter Studio nutzt striktes **RTS/CTS-Hardware-Handshaking**:
* Der Plotter signalisiert über die CTS-Leitung (Clear To Send), ob sein interner Puffer Daten aufnehmen kann.
* Plotter Studio wartet im `SerialStreamer`-Thread atomar auf CTS, bevor weitere Byte-Chunks gesendet werden. Dadurch sind Pufferüberläufe und Datenverlust ausgeschlossen.

### Notaus- und Schutzmechanismen
Wird ein Plot über die Benutzeroberfläche abgebrochen:
1. Sendet Plotter Studio sofort die Abbruchsequenz `\x1b.K` (Clear Device Buffer) an den Plotter.
2. Der Schreibstift wird unmittelbar angehoben (`PU;`).
3. Der Stift wird im Parkkarussell abgelegt (`SP0;`), um ein Austrocknen der Spitze oder Beschädigungen des Papiers zu verhindern.

---

## 5. Multi-Plotter-Architektur: Offen für jedes Gerät

Plotter Studio wurde von Grund auf modular entwickelt. Auch wenn der **Mutoh XP-500** als Referenz-Großformatplotter dient, ist die Software **nicht auf ein einziges Fabrikat beschränkt**.

### Deklarative Geräteprofile (`resources/devices/*.yaml`)
Jedes Gerät wird durch eine einfache, lesbare YAML-Datei definiert:

```yaml
model_id: "hpgl_generic"
name: "Generic HP-GL Plotter (Flatbed)"
manufacturer: "Generic / HP"
emulation: "HP-GL"
protocol: "hpgl"
origin: "bottom_left"         # "center" oder "bottom_left"
units_per_mm: 40.0            # 40 Units/mm = 0,025 mm Schrittweite
max_pens: 8                   # Anzahl Stifte im Wechlser
swap_xy: false                # Achsentausch bei Bedarf
invert_x: false               # X-Achse spiegeln
invert_y: false               # Y-Achse spiegeln
rotation_deg: 0               # Grundrotation (0, 90, 180, 270)

connection:
  baudrate: 9600
  bytesize: 8
  parity: "N"
  stopbits: 1
  rtscts: true
  xonxoff: false

margins_mm:
  default:
    top: 10.0
    bottom: 10.0
    left: 10.0
    right: 10.0
```

### Der `DeviceManager`
* Verwaltet eine Liste aller konfigurierten Plotter in `~/.config/plotter-studio/devices.yaml`.
* Ermöglicht es, in der Benutzeroberfläche mit einem Klick zwischen verschiedenen Plottern umzuschalten (z.B. vom Mutoh XP-500 Rollenplotter zu einem Roland DXY Flachbettplotter oder einem virtuellen Emulator).
* Alle Docks, Lineale, Randbereiche und Emitter passen sich sofort dynamisch an das gewählte Gerät an.

---

## 6. Verwandte Projekte, Inspiration & Danksagung

Plotter Studio baut auf den Erfahrungen und Erkenntnissen bewährter Open-Source-Projekte auf:

* **vpype (Antoine Beyeler, GPL-3.0-or-later):**  
  Die modulare Architektur der Slicer-Pipeline (Segmentverschmelzung, Umkehrung, Douglas-Peucker-Glättung und die 2-Opt TSP-Optimierung zur Minimierung von Leerfahrten) wurde maßgeblich durch *vpype* inspiriert. Plotter Studio implementiert diese Prinzipien auf Basis von reinem NumPy und integriert sie in eine interaktive Desktop-Oberfläche mit Echtzeit-Feedback und direkter Hardware-Ausgabe.
* **MutohPlot (Oliver F., MIT-Lizenz):**  
  Diente bei der Entstehung von Plotter Studio als Referenzprojekt und Testorakel für die Eigenheiten des Mutoh XP-500. Insbesondere die Hardware-Randprofile (Normal, Expanded, Type 1/3) und die Handshake-Eigenheiten wurden anhand von MutohPlot verifiziert. Es wurde **kein Code direkt übernommen**: Plotter Studio verwendet ein eigenes objektorientiertes Dokumentenmodell und eine native RTS/CTS-Flusssteuerung.
* **InkCut (GPL-3.0-or-later):**  
  Diente als architektonische Inspiration für die Entkopplung von Geräteprofilen und Transportmechanismen sowie für künftige Schleppmesser-Filter. Auch hier wurde **kein Code übernommen**; Plotter Studio setzt auf eine eigenständige Qt6- und NumPy-Architektur.
