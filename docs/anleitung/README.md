# Plotter Studio – Benutzerhandbuch & Anleitungen

Dieses Verzeichnis enthält Anleitungen und Dokumentation für Anwender von Plotter Studio.

---

## Inhaltsübersicht

1. **Schnellstart & Workflow** *(in Vorbereitung)*
   - SVG-Dateien per Drag & Drop oder Dateidialog öffnen
   - Blattgröße und Ausrichtung wählen (DIN A4–A0 oder freie Formate)
   - Objekte auf dem Blatt platzieren, verschieben und skalieren
   - Stifte und Farben zuweisen
2. **Plot-Modus & Vorschau** *(in Vorbereitung)*
   - Vektoroptimierung (Linien zusammenfassen, Vereinfachung, 2-Opt-Wegoptimierung)
   - Simulation der Stiftbewegungen mit dem Scrubber
   - Stiftbreiten, Leerfahrten und Knotenpunkte prüfen
   - Pre-Flight-Statistiken (Zeichenweg, Eilgang-Ersparnis, Stiftwechsel, Dauer)
3. **[Geräteanbindung & Plotten](geraetesteuerung-und-plotten.md)**
   - Serielle Verbindung (RS-232, Baudrate, Hardware-Handshake RTS/CTS)
   - Plotter-Prüfung und automatische Blatterkennung (`OI;OF;OH;`)
   - Plot starten, pausieren und abbrechen mit Notfall-Rückzug (`ESC.K`, `PU;SP0;`)
   - HP-GL- und Plot-SVG-Export
4. **Vorbereitung von Vektordateien** *(in Vorbereitung)*
   - Exportieren sauberer SVGs aus Inkscape, Illustrator oder CAD
   - Skripte (Python, Processing etc.): Einfach als Standard-SVG exportieren – Plotter Studio übernimmt Optimierung und Stiftzuordnung
