# Plotter Studio – Benutzerhandbuch & Anleitungen

Willkommen im offiziellen Benutzerhandbuch von **Plotter Studio**. Diese Anleitung erklärt die grundlegenden Konzepte, die Arbeit mit der grafischen Benutzeroberfläche, die Vektoroptimierung sowie den Anschluss und die Kalibrierung moderner und klassischer Stiftplotter.

---

## Inhaltsverzeichnis

### 1. [Konzepte & Architektur](1-konzepte-und-architektur.md)
* **Warum reicht ein normaler Druckertreiber nicht?** (Kinematik von Stiftplottern, Pfadreihenfolge, Puffergrenzen).
* **Der Plotter-Slicer:** Von Vektordateien zu optimierten Maschinenfahrwegen.
* **Koordinatensysteme & Nullpunkte:** Blattkoordinaten, Center-Origin vs. Bottom-Left, asymmetrische Ränder bei Rollenplottern.
* **Flusssteuerung & Sicherheit:** Serielles Streaming mit echtem RTS/CTS-Hardware-Handshake und Notfallabbruch.
* **Multi-Plotter-Architektur:** Deklarative YAML-Geräteprofile, `DeviceManager` und herstellerunabhängige Erweiterbarkeit.

### 2. [Layout-Modus & Objektverwaltung](2-layout-und-objektverwaltung.md)
* **Aufbau der Benutzeroberfläche:** Canvas, Millimeter-Lineale, Menüleiste und Docks.
* **Blatt- & Seiteneinrichtung:** DIN A4 bis DIN A0, Quer-/Hochformat, Randprofile und optische Hard-Clip-Abfrage (`OH;`).
* **Vektorgrafiken importieren:** SVG- und HP-GL-Dateien per Drag & Drop öffnen, automatisches Farb-Clustering.
* **Dock "Objekte & Ebenen":** Sichtbarkeit, Bearbeitungssperre, Z-Reihenfolge (Zeichenabfolge), Duplizieren und Löschen.
* **Dock "Transformation":** Millimetergenaue Positionierung, proportionales Skalieren mit Schloss-Schalter, Schnelltasten (50 %, 100 %, 200 %, Auf Blatt einpassen), Drehen und Spiegeln.
* **Stiftpalette & Farbzuweisung:** 8 Stiftkanäle, Strichbreiten und Zuweisung zu Pfadgruppen.

### 3. [Ausgabe-Modus, Simulation & Export](3-ausgabe-simulation-export.md)
* **Die Optimierungs-Pipeline (Tuning):** Linien zusammenfassen (Merge), Pfade umkehren (Reverse), RDP-Vereinfachung (Douglas-Peucker), 2-Opt Pfadoptimierung (Traveling Salesperson).
* **Pre-Flight-Statistiken:** Gezeichneter Weg (`Pen Down`), Eilgang-Leerfahrten (`Pen Up`), prozentuale Zeitersparnis und Stiftwechsel.
* **Simulation mit dem Scrubber:** Zeitstrahl zum interaktiven Abspielen, Vor- und Zurückspulen der Stiftbewegungen mit Geschwindigkeitsregelung (1x–10x).
* **Selektives Plotten (Stift-Filter):** Gezieltes Deaktivieren einzelner Farben für manuelle Stiftwechsel oder Testplots.
* **Live-Plotten:** Serielles Streaming im Hintergrund, Toolhead-Live-Cursor im Canvas, Pause/Fortsetzen und Notfallabbruch (`ESC.K`, `PU;`, `SP0;`).
* **Datei-Export:** Standardkonforme HP-GL-Plotdateien (`.hpgl`) und nach Stiften gruppierte Vektorgrafiken (`.svg`).

### 4. [Hardware-Setup, Kalibrierung & Diagnose](4-hardware-setup-und-test.md)
* **Physischer Anschluss & Verkabelung:** RS-232, 9-polige/25-polige Nullmodemkabel mit voller RTS/CTS-Beschaltung, USB-Seriell-Adapter (FTDI) und TCP-Netzwerk-Server.
* **Bedienfeld-Setup:** Baudrate (19200), Parität (8N1), Emulation (HP-7585B) und Randprofil (EXP).
* **Hardware-Diagnose:** Das CLI-Diagnosewerkzeug `tools/xp500_probe.py` zur Überprüfung aller Statusbits und Firmware-Abfragen.
* **Der Kalibrierplot:** Nutzen der mitgelieferten DIN A3/A4 Testmuster (`resources/calibration_plot_a3.svg`), Messung mit dem Stahllineal, Prüfung der 8 Stifte, Ränder und mechanischem Umkehrspiel (Backlash).
* **Weitere Plotter anbinden:** Einrichten neuer Geräte über den Dialog *Geräte-Einstellungen* oder über neue YAML-Dateien in `resources/devices/`.

---

## Weiterführende technische Dokumentation
* **[Gerätedokumentation Mutoh XP-500](../devices/mutoh-xp500/README.md):** Ausführliche technische Transkription des Handbuchs, MH-GL-Befehle, Escape-Sequenzen und Register.
* **[Architektur- und Konzeptdokumente](../project/konzept.md):** Datenmodelle, Pipeline-Design und Streaming-Architektur.
