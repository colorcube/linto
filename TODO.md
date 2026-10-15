# TODO & Status

Stand: 2026-10-15 · **Software-Meilensteine M1, M2 & M3 vollständig abgeschlossen (AP1–AP7, 66/66 Tests bestanden).**  
Nächster Schritt: **AP0 Hardware-Verifikation am realen Mutoh XP-500 Plotter**.

---

## 1. Software-Status (Erledigt)

- [x] **AP1 – Geometrie & Core:** Polylinien (`VectorPath`), BoundingBox, AffineTransform, Bézier-Glättung, RDP, Endpunkt-Merge, KD-Tree 2-Opt Wegeoptimierung.
- [x] **AP2 – Device & Emitter:** YAML-Geräteprofil (`mutoh_xp500.yaml`), HP-GL-Emitter (`IN`, `SP`, `VS`, `FS`, `PU`, `PD`), Center-Origin Koordinatentransformation, Ränderprofile (EXP, NORM, TYPE1, TYPE3).
- [x] **AP3 – Streaming & Emulator:** Serielles Streaming mit RTS/CTS-Handshake, TCP-Sockets, Hintergrund-Streamer mit Pause/Resume und sofortigem Not-Abbruch (`ESC.K`), vollständiger Software-Emulator mit Virtual Plotter (PTY und TCP) und SVG-Aufzeichnung.
- [x] **AP4 – Pipeline, Slicer & Export:** Pre-Flight-Statistiken (Zeichenweg, Leerweg, Stiftwechsel, Dauer, Hardclip-Prüfung), HP-GL- und SVG-Export.
- [x] **AP5 – GUI Layout-Modus:** Canvas mit Zoom/Pan, mm-Linealen, WYSIWYG-Strichbreiten, Seiteneinrichtungsdialog (`PageSetupDialog`), Stift-Palette (8 Stifte, Geschwindigkeit, Anpressdruck).
- [x] **AP6 – GUI Ausgabe-Modus:** Modus `Ausgabe` mit Pre-Flight-Inspektion, Leerfahrten-Anzeige, Scrubber-Simulation, Hardware-Inquiry (`probe_plotter`), Live-Plottersteuerung.
- [x] **AP7 – GUI Detail-Bearbeitung & Layout-Feinschliff:**
  - Dock `Objekte & Ebenen` (Z-Order, Sichtbarkeit, Sperren, Duplizieren, Inline-Rename).
  - Modernes, rahmenloses `SectionGroup`-Design (13px Header + 1px Trennlinie) für Transform- und Ausgabe-Dock.
  - Dynamische Feldbreiten über `QFontMetrics` (automatische Skalierung bei beliebigen Schriftgrößen).
  - Globaler `DeviceManager` mit persistentem Speicher (`~/.config/plotter-studio/devices.yaml`) und Toolbar-Integration.
- [x] **Hardware-Test-Vorbereitung:**
  - Diagnosetool: `tools/xp500_probe.py` (vollständige Registerabfrage `OI`, `OF`, `OH`, `OS`, `ESC.L`, `ESC.B` via Terminal).
  - Kalibrier- & Testplots: `resources/calibration_plot_a4.svg` / `.hpgl` und `resources/calibration_plot_a3.svg` / `.hpgl` (Orientierungspfeile +X/+Y, 400 mm Messstrecke für Maßstabsprüfung, 4-Rand-Rahmen, Stifte 1–8 Matrix, Rundlauf-Kreise).
  - Generator-Skript: `tools/generate_calibration_plot.py`.

---

## 2. Am Plotter (Hardware-Termin vor Ort)

Details und Ergebnistabelle: [docs/devices/mutoh-xp500/testplan.md](docs/devices/mutoh-xp500/testplan.md) · Anleitung: [docs/devices/mutoh-xp500/einrichtung.md](docs/devices/mutoh-xp500/einrichtung.md)

### Schritt 1: Rechner & Anschluss (ohne Plot)
- [ ] Port ermitteln: `ls -l /dev/serial/by-id/` und `lsusb` (Q-14).
- [ ] Typenschild und Firmware-Version (Einschaltmeldung) notieren.
- [ ] Panel gemäß [einrichtung.md](docs/devices/mutoh-xp500/einrichtung.md) einstellen (Q-16, Q-18):
  - Parametersatz: `USER1`
  - Empfangspuffer: `Small` (1000 Zeichen)
  - Vektorsortierung: `Off` (wird durch Plotter Studio optimiert)
  - Zeicheneinheit: `0.025 mm` (entspricht 40 Units/mm)
  - Hard-Clip-Fenster: `Exp`

### Schritt 2: Hardware-Inquiry ausführen
- [ ] Terminal-Diagnose starten:
  ```bash
  ./tools/xp500_probe.py /dev/ttyUSB0
  ```
  Prüfen:
  - CTS / DSR Leitungsstatus
  - `OI;` (7585B)
  - `OF;` (40,40)
  - `OH;` (Hard-Clip Grenzen in Units und mm)
  - `ESC.L` & `ESC.B` (Puffergröße: 1000 Bytes)
  - `OS;`, `OE;`, `OT;`

### Schritt 3: Kalibrier- & Testplots (auf Papier)
- [ ] **Orientierungsplot:** Pfeile $+X$ / $+Y$ und Text „OBEN“ an der Blattoberkante ausgeben → Achsmatrix und Vorzeichen bestätigen (`resources/calibration_plot_a3.svg` oder `.hpgl`).
- [ ] **Randplot (4-Rand-Kalibrierung):** Rechteck exakt auf den Hard-Clip (`OH`) plotten, Abstände zu allen vier Blattkanten mit Stahlmaßstab messen ($m_{x-}, m_{x+}, m_{y-}, m_{y+}$) → Klärt Q-13.
- [ ] **Maßstab:** 400 mm-Messstrecke in X und Y mit Stahlmaßstab nachmessen (Soll: $scale_x = 1.0$, $scale_y = 1.0$).
- [ ] **Stiftparameter:** `VS v,pen` (Geschwindigkeit) und `FS f,pen` (Anpressdruck) pro Stift 1–8 prüfen.
- [ ] **Abbruch-Test:** Plot starten und Not-Stopp via `ESC.K` (Schaltfläche *Abbrechen* in GUI) testen → Sofortiger Halt ohne Puffer-Nachlauf.
- [ ] **Gegenprobe mit MutohPlot** (`--device-unit 0.025`).

---

## 3. Handbuch & Dokumentation

- [x] Kapitel 7 (Setup-/User-Parameter, Abb. 7.3) eingearbeitet in [docs/devices/mutoh-xp500/konfiguration.md](docs/devices/mutoh-xp500/konfiguration.md)
- [ ] Ggf. Beschreibung von `ESC.@`, `ESC.O`/`OS`-Bits, `CV`, `AP`, `GP` anhand der Testergebnisse ergänzen.

---

## 4. Entscheidungen (Erledigt)

- [x] **Q-17 / D-14:** Plotter Studio ist eigenständiges Projekt mit Übernahme sinnvoller Module aus MutohPlot (MIT-Hinweis).
- [x] **Q-05 / D-15:** Eigener, schlanker Geometriekern mit `numpy`/`scipy` statt vpype.
- [x] **D-01 bis D-13:** Sämtliche Architektur- und Datenmodellentscheidungen bestätigt und umgesetzt.

---

## 5. Später / Nächste Software-Features (Ideenspeicher)

Details siehe [docs/project/konzept.md §9](docs/project/konzept.md#L479):

- [ ] **Hershey-Text / Single-Line Fonts:** Parametrische Vektorschriften für Beschriftungen, Randnotizen und Signaturblöcke.
- [ ] **Schraffur (Hatching):** Automatisches Füllen von SVG-Flächen mit parallelen, kreuzenden oder wellenförmigen Schraffurlinien.
- [ ] **DXF-Import:** Technischer CAD-Import (`ezdxf`).
- [ ] **Stipple / TSP-Art:** Rastergrafik-Konvertierung in Stipple-Punkte oder kontinuierliche Linien.
- [ ] **Rollenmedien / Banner-Modus:** Endlospapier-Plots ohne Begrenzung der Vorschublänge.
