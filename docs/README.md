# Plotter Studio – Dokumentation

Willkommen in der Dokumentation von Plotter Studio. Die Dokumentation ist in drei Hauptbereiche gegliedert:

---

## 1. [Benutzerhandbuch & Anleitungen](anleitung/README.md) (`docs/anleitung/`)
Praktische Dokumentation für Anwender:
* **Workflow:** Laden von SVG-Dateien, Skalieren und Platzieren auf dem Blatt.
* **Plot-Modus:** Vektoroptimierung, Stift-Simulation mit Scrubber, Pre-Flight-Prüfung.
* **Tipps für Vektordateien:** Vorbereitung von SVGs aus CAD, Inkscape oder eigenen Skripten.

---

## 2. [Gerätedokumentation](devices/mutoh-xp500/README.md) (`docs/devices/`)
Hardware-Dokumentation, Spezifikationen und Schnittstellenbeschreibungen:
* **[Mutoh XP-500](devices/mutoh-xp500/README.md):**
  * [Einrichtung & Schnellstart](devices/mutoh-xp500/einrichtung.md) (Bedienfeld, RS-232, Papier & Rollen)
  * [Bedienfeld-Konfiguration](devices/mutoh-xp500/konfiguration.md) (Handbuch Kapitel 7 transkribiert)
  * [Technische Spezifikationen](devices/mutoh-xp500/spezifikationen.md)
  * [RS-232C-Schnittstelle & Handshake](devices/mutoh-xp500/schnittstelle.md)
  * [Einheiten, Ursprung & Koordinaten](devices/mutoh-xp500/einheiten-und-koordinaten.md)
  * [MH-GL-Befehlssatz](devices/mutoh-xp500/mhgl-befehle.md) & [Escape-Sequenzen](devices/mutoh-xp500/escape-sequenzen.md)
  * [Software-Emulator (`virtual_plotter`)](devices/mutoh-xp500/emulator.md) (PTY/TCP-Simulation & Firmware-Inquiries)
  * [Hardware-Testplan](devices/mutoh-xp500/testplan.md)

---

## 3. [Projekt- & Konzeptdokumente](project/konzept.md) (`docs/project/`)
Architektur, Systementwurf und Projektorganisation:
* **[Konzept v2.2](project/konzept.md):** Architektur, Datenmodell, Koordinatensysteme, Pipeline, Streaming-Dienst `plotd`, Stiftmodelle.
* **[Arbeitspakete & Meilensteine](project/arbeitspakete.md):** Phasen M0 bis M3, Aufwände und Abhängigkeiten.
* **[Offene Fragen & Entscheidungen](project/offene-fragen.md):** Laufendes Protokoll technischer Entscheidungen (D-01…D-15).
* **[User Stories](project/user-stories.md):** Anwendungsfälle US-01 bis US-10.
* **[Analyse MutohPlot](project/analyse-mutohplot.md):** Untersuchung des Referenzprojekts für den Mutoh XP-500.
* **[Analyse InkCut](project/analyse-inkcut.md):** Untersuchung von Treibern, Protokollen (DMPL, CAMM-GL, G-Code) und Schleppmesser-Filtern.
* **[Projekt-TODO](../TODO.md):** Offene Punkte für Tests am Gerät.
