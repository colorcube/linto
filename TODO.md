# Plotter Studio – Todo & Roadmap

Zentrale Aufgabenliste für die Weiterentwicklung von Plotter Studio. Detaillierte Spezifikationen und Hintergründe finden sich in [docs/project/arbeitspakete.md](docs/project/arbeitspakete.md) und [docs/project/konzept.md](docs/project/konzept.md).

---

## 1. Packaging & Distribution (AP8 / M4)

Ziel: Plotter Studio als eigenständiges, klickbares Einzelprogramm (ohne Notwendigkeit einer manuellen Python-Installation) für Linux und Windows bereitstellen.

- [ ] **Ressourcenpfad anpassen:** In [src/plotter_studio/device/profile.py](src/plotter_studio/device/profile.py) `sys._MEIPASS` unterstützen, damit `resources/devices/*.yaml` im gepackten Zustand gefunden werden.
- [ ] **PyInstaller Spezifikation:** `plotter-studio.spec` mit allen notwendigen Qt-Plugins, Binärabhängigkeiten (Shapely, NumPy, SciPy) und YAML-Gerätedefinitionen erstellen.
- [ ] **Linux AppImage:** Build-Skript für ein Linux-AppImage bereitstellen (umgeht `glibc`-Inkompatibilitäten zwischen verschiedenen Linux-Distributionen).
- [ ] **Windows Executable:** Build-Test für `plotter-studio.exe`.
- [ ] **CI/CD Automation:** GitHub Actions Workflow (`.github/workflows/release.yml`) für automatische Multi-Plattform-Builds bei neuen Git-Tags.

---

## 2. Hardware-Inbetriebnahme & Kalibrierung (AP0 / M0)

Tests direkt am physischen Mutoh XP-500 Plotter mit [tools/xp500_probe.py](tools/xp500_probe.py) und Nullmodemkabel.

- [ ] **Panel-Einstellungen verifizieren:** Hard-Clip-Fenster (`EXP`), Puffergröße (`Small` = 1000 Zeichen), Handshake (`RTS/CTS`), Schrittauflösung (`0.025 mm`).
- [ ] **Hardware-Inquiry prüfen:** Rückmeldungen von `OI;`, `OF;` und `OH;` gegen die Software-Parser abgleichen.
- [ ] **Kalibrierungs-Plot:** [resources/calibration_plot_a3.svg](resources/calibration_plot_a3.svg) auf DIN A3 zeichnen und Randmaße mit dem Stahllineal gegen das Profil abgleichen.
- [ ] **Puffer- und Abbruchverhalten:** Wirksamkeit von `ESC.K` (Puffer leeren) bei Live-Abbrüchen verifizieren.

---

## 3. Format- und Treiber-Roadmap

- [ ] **HP-GL/PLT-Import:** Bestehende HP-GL-Dateien als Vektorpfade in den Layout-Canvas einlesen.
- [ ] **Schneideplotter-Unterstützung (Vinyl Cutter):** Klingen-Offset-Kompensation (Drag-Knife) implementieren, um Schnittecken bei Schleppmessern sauber auszufahren.
- [ ] **DXF-Import:** Direkter Import von 2D-CAD-Dateien (unter Nutzung von `ezdxf`).
- [ ] **G-Code-Treiber:** Emitter für DIY-Stiftplotter und Fräsen/3D-Drucker mit Marlin- oder Grbl-Firmware.

---

## 4. Erweiterte Gestaltungswerkzeuge

- [ ] **Schraffur (Hatching):** Automatisches Füllen geschlossener Vektorflächen mit Stift-Linienmustern.
- [ ] **Hershey-Text:** Parametrische Single-Line-Schriften für technische Beschriftungen, Passkreuze und Stiftnotizen.
