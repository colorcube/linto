# Gerätesteuerung & Plotten

Plotter Studio verbindet sich direkt mit echten Stiftplottern (wie dem **Mutoh XP-500**) sowie Software-Emulatoren über serielle Schnittstellen (RS-232, USB-Seriell-Adapter) oder TCP-Netzwerkverbindungen.

---

## 1. Geräteprofil & Koordinatensystem

### Mutoh XP-500 Spezifikationen
* **Befehlssatz:** HP-GL (HP-7585B Emulation)
* **Auflösung:** 40 Einheiten pro mm (Plotter-Schritt = 0,025 mm)
* **Schnittstellenparameter:** 19200 Baud, 8 Datenbits, keine Parität, 1 Stoppbit (8N1)
* **Flusssteuerung:** Hardware-Handshake (RTS/CTS)
* **Koordinaten-Ursprung:** **Center-Origin (0,0 in der Mitte des Hard-Clip-Fensters)**

### Randprofile (Clip-Fenster)
Der Mutoh XP-500 besitzt je nach DIP-Schalter- bzw. Menüeinstellung am Bedienfeld vier vordefinierte Randmodi. Da Rollenplotter an der Vorderkante einen Einzugsbereich für die Andruckrollen benötigen, ist der Rand asymmetrisch:

| Randprofil | Vorderkante (Einzug) | Hinterkante | Links | Rechts | Einsatzzweck |
|---|---|---|---|---|---|
| **EXP** (Expanded) | 25 mm | 5 mm | 5 mm | 5 mm | Maximal nutzbare Zeichenfläche (Standard) |
| **NORM** (Normal) | 25 mm | 10 mm | 10 mm | 10 mm | Standardränder |
| **TYPE1** | 38 mm | 10 mm | 10 mm | 10 mm | Großer Vorschubrand für Rollenpapier |
| **TYPE3** | 38 mm | 5 mm | 5 mm | 5 mm | Großer Vorschubrand mit schmalen Seitenrändern |

Plotter Studio berechnet die Transformation von Blattkoordinaten (mm, Ursprung oben links) in Plotter-Units (Center-Origin) automatisch basierend auf dem gewählten Randprofil.

---

## 2. Anschlüsse & Plattform-Unterstützung

Plotter Studio ist plattformunabhängig und unterstützt Linux und Windows gleichermaßen über dieselbe Schnittstellenlogik:

### Schnittstellentypen
* **Linux (Seriell):** `/dev/ttyUSB0`, `/dev/ttyS0` etc.
* **Linux (Virtueller Emulator):** `./virtual_plotter` (wird automatisch als Symlink erkannt)
* **Windows (Seriell):** `COM1`, `COM3`, `COM4` etc.
* **TCP / Netzwerk:** `tcp://127.0.0.1:9999` (für den integrierten Software-Emulator im Netzwerkmodus)

Über den **Aktualisieren-Knopf (🔄)** neben der Anschlussauswahl werden alle aktuell am System verfügbaren Ports sowie aktive virtuelle Plotter neu eingelesen.

---

## 3. Plotter-Inquiry (Hardware-Prüfung)

Vor dem Plotten kann die Verbindung und das eingelegte Blatt mit einem Klick auf **[ 🔍 Plotter prüfen (Inquiry) ]** getestet werden.

### Ausgeführte Befehle
Plotter Studio sendet eine Diagnoseabfrage an das Gerät:
1. `OI;` (Output Identification): Fragt das Modell ab (z.B. `7585B`).
2. `OF;` (Output Factors): Fragt die Maßeinheiten ab (z.B. `40,40` = 40 Units/mm).
3. `OH;` (Output Hard-Clip): Fragt die Grenzen des plottbaren Bereichs ab (z.B. `-7800,-5740,7800,5740`).

### Automatische Blatterkennung
Aus der `OH`-Antwort berechnet Plotter Studio die exakte Breite und Höhe der physikalisch plottbaren Fläche in Millimetern und leitet daraus das eingelegte Blattformat ab (DIN A4, A3, A2, A1, A0).

Das Ergebnis wird direkt im Dock angezeigt:
* **Erfolg:** `✓ 7585B (A3, 40 U/mm) • Hard-Clip: 390×287 mm` (grünes Banner)
* **Keine Antwort:** `⚠️ Keine Antwort vom Plotter (Timeout)` (rotes Banner)

---

## 4. Live-Plotten & Steuerung

Im Bereich **🖨️ Plotter-Verbindung & Ausgabe** stehen folgende Bedienelemente zur Verfügung:

### [ 🚀 Plot senden ]
* Übersetzt den aktuellen, optimierten Plot-Auftrag mit dem `HPGLEmitter` in HP-GL-Befehlsketten (`IN`, `SP`, `VS`, `FS`, `PU`, `PD`).
* Startet die Übertragung im Hintergrund (`SerialStreamer`), sodass die Benutzeroberfläche vollständig reaktionsfähig bleibt.
* Der Fortschrittsbalken visualisiert den Übertragungsfortschritt von 0 bis 100 %.
* Im Canvas läuft der **Toolhead-Cursor (Fadenkreuz und Stiftposition)** in Echtzeit mit den tatsächlich gesendeten Befehlen synchron mit.

### [ ⏸ Pause ] / [ ▶️ Fortsetzen ]
* Pausiert die Übertragung von Befehlen an den seriellen Puffer.
* Ein Klick auf **▶️ Fortsetzen** setzt den Plot genau an der unterbrochenen Stelle fort.

### [ ⏹ Abbrechen ]
* Bricht den laufenden Plot sofort sicher ab.
* Sendet die Fluchtsequenz `\x1b.K` (Clear Buffer), hebt den Stift an (`PU;`) und legt ihn in die Halterung zurück (`SP0;`), um Beschädigungen von Papier und Stiftspitze zu verhindern.

---

## 5. Datei-Export

Alternativ zur direkten seriellen Ausgabe können optimierte Daten exportiert werden:
* **[ 📄 Plotdatei (.hpgl) exportieren... ]**: Erzeugt eine fertige HP-GL/PLT-Datei mit korrekten Center-Origin-Koordinaten, Stiftwechseln und Geschwindigkeitsparametern.
* **[ 🎨 Plot-Vektoren (.svg) exportieren... ]**: Erzeugt eine saubere SVG-Datei, in der Pfade nach Stiften und Strichfarben gruppiert sind.
