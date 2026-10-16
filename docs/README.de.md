# Plotter Studio – Dokumentation

> **Sprache / Language:** [Deutsch](README.de.md) | [English](README.md)

Willkommen in der Dokumentation von Plotter Studio. Die Dokumentation ist in drei Hauptbereiche gegliedert:

---

## 1. [Benutzerhandbuch & Anleitungen](anleitung/README.md) (`docs/anleitung/`)
Praktische Dokumentation und Benutzerhandbuch für Anwender:
* **[1. Schnellstart & Typischer Workflow](anleitung/1-schnellstart-und-workflow.md):** Einstieg mit physischer Hardware oder dem integrierten Software-Emulator; der 5-Schritte-Workflow von SVG bis Plot.
* **[2. Layout-Modus & Objektverwaltung](anleitung/2-layout-und-objektverwaltung.md):** Import von SVG & HP-GL, Seiteneinrichtung mit Hard-Clip-Abfrage (`OH;`), Transformation (50%, 100%, 200%, Proportions-Sperre, Einpassen, Zentrieren), Z-Order Ebenenverwaltung und Stiftzuordnung.
* **[3. Ausgabe-Modus, Simulation & Export](anleitung/3-ausgabe-simulation-export.md):** Pipeline-Tuning (Merge, Reverse, RDP, 2-Opt), Pre-Flight-Statistiken, interaktive Scrubber-Simulation mit Leerfahrten-Visualisierung, Stiftfilterung, serielles Streaming und HP-GL/SVG-Export.
* **[4. Hardware-Setup, Kalibrierung & Diagnose](anleitung/4-hardware-setup-und-test.md):** RS-232 Verkabelung mit Hardware-Handshake (RTS/CTS), Bedienfeld-Setup, Hardware-Diagnosetool `xp500_probe.py`, der offizielle Kalibrierplot (`resources/calibration_plot_a3.svg`) und Einbindung weiterer Plottermodelle.
* **[5. Leitfaden: Vektorformate, Quellen & Workflows](anleitung/5-vektorformate-und-workflows.md):** Best Practices für eigene SVG-Skripte, Inkscape als Universal-Konverter, Blender (3D zu 2D SVG), HP-GL und DXF.
* **[6. Hintergrund: Konzepte, Algorithmen & Architektur (Deep-Dive)](anleitung/6-konzepte-und-architektur.md):** Slicer-Architektur, mathematische Grundlagen der 2-Opt TSP Pfadoptimierung, Koordinatensysteme (Center-Origin vs. Bottom-Left), asymmetrische Rollenränder und Multi-Plotter-Treiberdesign.
* **[7. Empfohlene Ressourcen, Tools & Community-Sammlungen](anleitung/7-ressourcen-tools-und-community.md):** Kuratierte Sammlung spezialisierter Software (vpype, vsketch, ln, Turtletoy), Hershey-Einlinienschriften und Community-Hubs (Awesome Plotters, Drawingbots, Reddit).

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
* **[Todo & Roadmap](project/TODO.md):** Zentrale Aufgabenliste für Weiterentwicklung, Packaging und Hardware-Tests.
* **[Konzept v2.3](project/konzept.md):** Architektur, Datenmodell, Koordinatensysteme, Pipeline, Streaming und Stiftmodelle.
* **[User Stories](project/user-stories.md):** Anwendungsfälle US-01 bis US-10.
* **[Analyse MutohPlot](project/analyse-mutohplot.md):** Untersuchung des Referenzprojekts für den Mutoh XP-500.
* **[Analyse InkCut](project/analyse-inkcut.md):** Untersuchung von Treibern, Protokollen (DMPL, CAMM-GL, G-Code) und Schleppmesser-Filtern.
