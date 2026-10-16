# Plotter Studio – Todo & Roadmap

Zentrale Aufgabenliste für die Weiterentwicklung von Plotter Studio. Detaillierte Spezifikationen und Hintergründe finden sich in [docs/project/arbeitspakete.md](docs/project/arbeitspakete.md) und [docs/project/konzept.md](docs/project/konzept.md).

---

## 1. Code-Bereinigung, GUI & UX (Ergebnisse aus Projekt-Review)

### 1.1 Altlasten & Code-Duplikate abbauen
- [x] **Veraltete Docks löschen:** `src/plotter_studio/gui/paper_dock.py` (wurde durch `PageSetupDialog` ersetzt) und `src/plotter_studio/gui/layout_dock.py` samt Referenzen in `main_window.py` entfernen.
- [x] **Single Source of Truth für Randprofile:** Die vierfach duplizierten Mutoh-Randprofile (`resources/devices/mutoh_xp500.yaml`, `core/document.py`, `emulator/virtual_plotter.py`, `gui/plot_dock.py` & `gui/device_dialog.py`) zusammenführen und ausschließlich aus den YAML-Geräteprofilen laden (behebt auch abweichende Zahlenwerte für `NORM`/`TYPE1`/`TYPE3`).
- [x] **Drag-&-Drop-Handler zusammenführen:** Identische `dragEnterEvent`/`dragMoveEvent`/`dropEvent`-Methoden in `gui/main_window.py` und `gui/canvas.py` konsolidieren und Mehrfach-Datei-Drops (aktuell vorzeitiges `return` nach der ersten Datei) ermöglichen.
- [x] **Punkt-Strecken-Distanz vereinheitlichen:** Identische Vektor-Projektion in `pipeline/flatten.py` und `pipeline/simplify.py` in eine gemeinsame Hilfsfunktion auslagern.
- [x] **Preset-Logik im Stift-Dock zusammenführen:** Duplizierte Preset-Anwendung in `gui/pen_dock.py` (`_on_apply_preset_clicked` und `_on_load_preset_clicked`) in eine gemeinsame Methode extrahieren.

### 1.2 GUI-Bugs & Bedienungskonsistenz
- [x] **`PenDockWidget` Signal-Bug beheben:** `self.table.itemChanged.connect(self._on_table_item_changed)` in `gui/pen_dock.py` aus `refresh_table()` in `_setup_ui()` verschieben, damit das Signal nicht bei jedem Refresh mehrfach registriert wird.
- [x] **Stift-Geschwindigkeit (`VS`) und Anpressdruck (`FS`) in der GUI:** Spalten für Geschwindigkeit (`cm/s`) und Kraft (`g`) im `PenDockWidget` ergänzen (`LogicalPen` und `HPGLEmitter` unterstützen sie bereits).
- [x] **Undo/Redo-Lücken (`QUndoStack`) schließen:**
  - Löschen über das Papierkorb-Icon im `ObjectDockWidget` über `DeleteItemsCommand` leiten (wie bei der `Entf`-Taste).
  - Duplizieren, Z-Order (Hoch/Runter), Umbenennen, Sperren und Ausblenden im `ObjectDockWidget` sowie manuelle Stiftänderungen im `PenDockWidget` als `QUndoCommand` kapseln.
- [x] **Objekt-Umbenennen im `ObjectDockWidget` reparieren:** Beim Editieren des Namens per Doppelklick nicht das Anzeige-Suffix ` ({path_count} Pfade)` in `doc_item.name` zurückschreiben (z. B. über `Qt.ItemDataRole.EditRole` oder eigene Spalte).
- [x] **Gesperrte Objekte (`item.locked`) schützen:** In allen Transformations-Methoden (`center_on_sheet`, `fit_to_sheet`, `rotate_90_cw/ccw`, `reset_scale_1_1`) und in `delete_selected_items` prüfen, ob `item.locked` gesetzt ist.
- [x] **Multi-Selektion & freie Rotation im `TransformDockWidget`:**
  - Mehrfachauswahl (`selected`) bei Transformationen (Zentrieren, Drehen, Skalieren) gemeinsam transformieren statt nur `selected[0]`.
  - Numerisches Eingabefeld (Spinbox) für freie Rotationswinkel (`0,0°`–`360,0°`) ergänzen (`AffineTransform.rotation()` unterstützt dies bereits).
- [x] **`PageSetupDialog`-Details:**
  - Einfaches `&` in `QGroupBox("Papierformat && Ausrichtung")` und `QGroupBox("Ränder && Vorschubkante")` maskieren (verhindert Unterstrich-Darstellung `_Ausrichtung`).
  - Statusleiste (`self.lbl_sheet_status`) in `MainWindow._on_page_changed_from_dialog()` aktualisieren.
  - Asymmetrische Ränder (z. B. 25 mm Vorschubkante vs. 5 mm Rest) im Dialog nicht versehentlich symmetrisch überschreiben; beim Abfragen der Plotter-Größe (`OH;`) berücksichtigen, dass der Plotter den Hard-Clip-Bereich und nicht die Außenmaße des Bogens meldet.

### 1.3 Architektur, Projekt-Persistenz & Workflow-Sicherheit
- [x] **Dirty-State & direktes Speichern (`Strg+S`):** Vor `Neu`, `Projekt öffnen` und beim Schließen des Fensters (`closeEvent`) über `undo_stack.isClean()` vor ungespeicherten Änderungen warnen; direktes `Speichern` (`Strg+S`) auf den aktuellen Dateipfad ergänzen.
- [x] **Projekt-Metadaten in `core/svg_export.py` vervollständigen:** `page.device_profile`, `page.feed_edge`, `item.visible` und `item.locked` im `plotter:`-Namespace mit abspeichern und beim Laden wiederherstellen; fehlenden `Any`-Import in `core/document.py` ergänzen.
- [x] **`DeviceManager` von Qt entkoppeln:** `PySide6.QtCore.QObject` in `device/manager.py` durch reine Python-Callbacks ersetzen, damit `plotter_studio.device` auch headless ohne installiertes Qt nutzbar ist.
- [x] **Plot-SVG-Export in `core/svg_export.py` auslagern:** String-Aufbau aus `MainWindow.export_plot_svg_dialog()` in eine testbare Funktion in `core/svg_export.py` verschieben.
- [x] **Nicht-blockierendes Hardware-Probing in Dialogen:** `probe_plotter()` in `PageSetupDialog` und `DeviceSettingsDialog` wie im `PlotDockWidget` in einen Hintergrund-Thread auslagern.
- [x] **Manueller Stiftwechsel / Pause bei Stiftwechsel:** Option im `SerialStreamer`, vor `SPn;`-Wechseln automatisch zu pausieren (wichtig für 1-Stift-Plotter und Spezialstifte außerhalb des 8er-Karussells).
- [x] **Ausschwingzeit nach `SP0;` am Job-Ende:** Kurze Wartezeit in `SerialStreamer._run_stream()` vor dem Schließen des seriellen Ports, damit der Plotter den Stift mechanisch ins Karussell ablegen kann, bevor DTR/RTS abfällt.

---

## 2. Packaging & Distribution (AP8 / M4)

Ziel: Plotter Studio als eigenständiges, klickbares Einzelprogramm (ohne Notwendigkeit einer manuellen Python-Installation) für Linux und Windows bereitstellen.

- [ ] **Ressourcenpfad anpassen:** In [src/plotter_studio/device/profile.py](src/plotter_studio/device/profile.py) `sys._MEIPASS` unterstützen, damit `resources/devices/*.yaml` im gepackten Zustand gefunden werden.
- [ ] **PyInstaller Spezifikation:** `plotter-studio.spec` mit allen notwendigen Qt-Plugins, Binärabhängigkeiten (NumPy) und YAML-Gerätedefinitionen erstellen.
- [ ] **Linux AppImage:** Build-Skript für ein Linux-AppImage bereitstellen (umgeht `glibc`-Inkompatibilitäten zwischen verschiedenen Linux-Distributionen).
- [ ] **Windows Executable:** Build-Test für `plotter-studio.exe`.
- [ ] **CI/CD Automation:** GitHub Actions Workflow (`.github/workflows/release.yml`) für automatische Multi-Plattform-Builds bei neuen Git-Tags.

---

## 3. Hardware-Inbetriebnahme & Kalibrierung (AP0 / M0)

Tests direkt am physischen Mutoh XP-500 Plotter mit [tools/xp500_probe.py](tools/xp500_probe.py) und Nullmodemkabel.

- [ ] **Panel-Einstellungen verifizieren:** Hard-Clip-Fenster (`EXP`), Puffergröße (`Small` = 1000 Zeichen), Handshake (`RTS/CTS`), Schrittauflösung (`0.025 mm`).
- [ ] **Hardware-Inquiry prüfen:** Rückmeldungen von `OI;`, `OF;` und `OH;` gegen die Software-Parser abgleichen.
- [ ] **Kalibrierungs-Plot:** [resources/calibration_plot_a3.svg](resources/calibration_plot_a3.svg) auf DIN A3 zeichnen und Randmaße mit dem Stahllineal gegen das Profil abgleichen.
- [ ] **Puffer- und Abbruchverhalten:** Wirksamkeit von `ESC.K` (Puffer leeren) bei Live-Abbrüchen verifizieren.

---

## 4. Format- und Treiber-Roadmap

- [x] **HP-GL/PLT-Import (optional):** Bestehende `.hpgl`/`.plt`-Dateien als Vektorpfade in den Layout-Canvas einlesen (inkl. `LB`-Text, Kreisen `CI`, Bögen `AA`/`AR`, Rechtecken `EA`/`RA` und Stiftzuweisung `SP1`–`SP8`, übernommen aus `MutohPlot` in `src/plotter_studio/core/hpgl_import.py`).
- [ ] **Schneideplotter-Unterstützung (Vinyl Cutter):** Klingen-Offset-Kompensation (Drag-Knife) implementieren, um Schnittecken bei Schleppmessern sauber auszufahren.
- [ ] **DXF-Import:** Direkter Import von 2D-CAD-Dateien (unter Nutzung von `ezdxf`).
- [ ] **G-Code-Treiber:** Emitter für DIY-Stiftplotter und Fräsen/3D-Drucker mit Marlin- oder Grbl-Firmware.

---

## 5. Erweiterte Gestaltungswerkzeuge

- [ ] **Schraffur (Hatching):** Automatisches Füllen geschlossener Vektorflächen mit Stift-Linienmustern.
- [ ] **Hershey-Text:** Parametrische Single-Line-Schriften für technische Beschriftungen, Passkreuze und Stiftnotizen (inkl. `stroke_font.py` aus `MutohPlot` als mögliche Vorlage).

