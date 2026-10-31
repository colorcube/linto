# Analyse: MutohPlot (gefundenes Projekt)

Stand: 2026-10-13 · Quelle: [github.com/oliver321/MutohPlot](https://github.com/oliver321/MutohPlot), v0.1.0 vom 2026-09-07, Autor „Oliver F.“, **MIT-Lizenz**.

## 1. Was MutohPlot ist

Ein Python-Werkzeug (CLI + lokale Weboberfläche), das HP-GL und SVG für **genau unseren Plotter (Mutoh XP-500)** umrechnet und seriell überträgt. Entwickelt Juli–September 2026, offenbar stark agentengestützt (Branches `agent/…`). Etwa 5 900 Zeilen Code, über 200 Tests. Die einzige Abhängigkeit ist `pyserial`. Betrieben wird es auf einem Raspberry Pi am Plotter.

| Bereich | Umfang |
|---|---|
| Import | SVG (eigener Parser: line, polyline, polygon, rect, circle, ellipse, path inkl. Bögen, Transformationen), HP-GL (Parser: `IN DF SP PA PR PU PD AA AR CI EA RA LB SI DI DR SL CP`) |
| Layout | Einpassen in den sicheren Bereich, Drehung 0/90/180/270 und automatisch, A3–A0 hoch/quer |
| Optimierung | Diskretisierung nach Qualitätsprofil (0,02–0,2 mm), doppelte Segmente entfernen (richtungsunabhängig), Nearest-Neighbour mit räumlichem Index |
| Gerät | XP-500-Achsabbildung, **Hard-Clip-Fenster aus dem Handbuch**, Kalibrierassistent (4 Ränder messen → Profil), `OF`/`OH`-Abfrage |
| Übertragung | 19200 8N1, **XON/XOFF im Userspace** (PL2303-Workaround), Puffer-Profile `large`/`small`, Stop/Go/Abbruch, Warteschlange, Verlauf |
| Stifte | 8 Plätze mit Name, Typ (Tusche, Faser, Bleistift, Kugelschreiber), Breite, Farbe; Zuordnung SVG-Farbe bzw. Ebene „Pen 4“ → Stift |
| UI | Web (stdlib `http.server`), Seiten Plotten / Hardware / Kalibrierung / Stifte |

## 2. Neue Gerätefakten (aus MutohPlot bzw. dem dort zitierten Handbuch)

| Fakt | Quelle | Bedeutung für uns |
|---|---|---|
| **Hard-Clip-Fenster** am Panel: `Norm` (oben 35 / unten 15 / links 15 / rechts 15 mm), `Exp` (25/5/5/5), `Type 1` (25/5/11/11), `Type 3` (25/10/10/10), Toleranz ±1 mm. „Oben“ = Vorderkante in Vorschubrichtung. | Handbuch, Abb. 7.3 (laut `docs/hard-clip.md`) | Erklärt die asymmetrischen Ränder. Das Profil braucht `window` als Einstellung plus Kalibrierkorrektur. |
| Ursprung = Hard-Clip-Mitte → Versatz zur Blattmitte = (oben − unten)/2, bei Norm/Exp/Type 1 **10 mm** in Vorschubrichtung | `transform/hard_clip.py` | bestätigt unsere Messung und konzept.md §4 |
| Achsen: erste Koordinate (X) = Vorschub, „nach unten“ auf dem Blatt; zweite (Y) = quer, „nach rechts“. `X = y_papier − H/2`, `Y = x_papier − W/2` (Achstausch, keine Spiegelung) | `transform/coordinate.py`, hardwaregetestet | Kandidat für unsere `insert_matrix`, mit dem Orientierungsplot bestätigen |
| **Empfangspuffer am Panel wählbar: 1 MB oder 1000 Zeichen** | `docs/a3-serial-hardware-test.md` | Mit 1000 Zeichen reagieren Pause und Abbruch fast sofort und der Fortschritt stimmt auf ±1000 Byte, ganz ohne `ESC.B`. **Sehr wertvoll.** |
| Abbruch bei vollem Puffer: am Gerät auf `LOCAL` schalten, dann `RESET` | README | Workaround, falls `ESC.K` fehlt |
| PL2303-Adapter: Kernel-IXON kann einen gestoppten 256-Byte-Sendepuffer „hängen lassen“ → XON/XOFF selbst behandeln | `serial_io.py` | Strategie `xonxoff_userspace` vorsehen. Du nutzt RTS/CTS, das umgeht das Problem. |
| ⚠️ Einheit: MutohPlot schreibt mit **0,01 mm/Unit**, bei dir liefert `OF;` aber **40** (= 0,025 mm) | `devices/mutoh_xp500.py` vs. deine Notizen | Der XP-500 hat vermutlich einen umschaltbaren Befehlsmodus/Auflösung (MH-GL vs. HP-GL-Emulation). **Die Einheit muss aus `OF;` gelesen und darf nicht fest codiert werden.** |
| Geschwindigkeit `VS` noch nicht hardwaregetestet, `ESC.`-Befehle werden nicht verwendet | `docs/configuration.md`, Code | bleibt AP0 |

## 3. Bewertung im Hinblick auf LINTO

**Stärken**
- Hardwaregetestet am XP-500: Achsen, Fenster, Kalibrierung, Übertragung.
- Guter HP-GL-Parser (Bögen, Kreise, Labels, Füllrechtecke), passt genau zu unserem AP4 „HPGL-Import“.
- Durchdachter Kalibrierablauf (4 Ränder messen → reale Blattmaße + Mittelpunktkorrektur), das entspricht unserem AP0/AP2.
- MIT-Lizenz: Code darf in ein GPLv3-Projekt übernommen werden (MIT-Hinweis beibehalten).

**Schwächen (für unsere Ziele)**
- **Datenmodell:** flache `list[Polyline]` aus `list[Point]`-Dataclasses (reines Python). Kein Objektbaum, keine Transformationen pro Objekt, langsam bei 10⁵–10⁶ Punkten.
- **Kopplung:** Die Geschäftslogik steckt teilweise in `cli.py` (941 Zeilen). Die Weboberfläche ruft CLI-Funktionen über ein künstliches `argparse.Namespace` auf. Eine saubere Bibliotheks-API gibt es nicht.
- **Layout-Semantik:** Grundsätzlich „einpassen + zentrieren“. Freies Platzieren mehrerer Objekte ist nicht vorgesehen.
- **Fokus:** Raspberry-Pi-Webdienst mit A3 als Standard, ein anderes Bedienkonzept als ein Desktop-Layout-Editor.
- Einheit fest auf 0,01 mm (siehe oben). Ohne Anpassung passt sie wahrscheinlich nicht zu deinem Gerät.

## 4. Optionen

| Option | Beschreibung | Pro | Contra |
|---|---|---|---|
| **A** Als Abhängigkeit nutzen | `pip install mutohplot`, LINTO ruft Konvertierung/Übertragung auf | schneller Start | keine saubere API, Datenmodell passt nicht, Abhängigkeit von fremden Zielen |
| **B** Forken & ausbauen | MutohPlot um eine Qt-Oberfläche und ein Objektmodell erweitern | alles Vorhandene sofort da | großer Umbau des Kerns nötig, Fork driftet ab |
| **C** Eigenständig, gezielt übernehmen | LINTO nach konzept.md bauen, einzelne Module/Wissen aus MutohPlot portieren (mit MIT-Hinweis) | sauberes Modell, bewährtes Gerätewissen, unabhängig | etwas mehr Arbeit als A |
| **D** MutohPlot als Backend | LINTO nur als Layout-Editor, der fertige HPGL an MutohPlots Web-API/Queue übergibt | minimaler Aufwand für M1 | zwei Programme, Doppelarbeit bei Fit/Rotation, Positionierung kollidiert mit „Einpassen“ |

### Empfehlung: **C**, ergänzt um eine Übergangslösung
1. **Sofort:** MutohPlot lokal installieren und als **Werkzeug zum Plotten verwenden**, solange LINTO entsteht. Es dient außerdem als **Referenz/Testorakel**: Gleiche SVG → HPGL vergleichen.
2. **In LINTO übernehmen bzw. portieren:**

| MutohPlot | Ziel in LINTO | Anpassung |
|---|---|---|
| `hpgl/tokenizer.py`, `hpgl/parser.py`, `hpgl/stroke_font.py` | AP4 HPGL-Import | Ausgabe auf numpy-Polylinien umstellen |
| `hard_clip.py`, `transform/hard_clip.py` (Fenstertabelle, Mittelpunktkorrektur) | AP2 Geräteprofil/Abbildung | in Profil-YAML überführen |
| `calibration.py`, `calibration_profiles.py` (4-Rand-Kalibrierung, Zeichnung) | AP2 Kalibrierplots | Ablauf übernehmen |
| `serial_io.py` (Userspace-XON/XOFF, `OF`/`OH`-Abfrage) | AP3 Transport | als Strategie `xonxoff_userspace` neben `rtscts` |
| `optimize/paths.py` (Dedupe richtungsunabhängig) | AP4 Pipeline | Duplikate erkennen und entfernen |
| Stifttypen/-breiten aus `web_profiles.py`, `config/Standard.toml` | Werkzeugbibliothek | Felder übernehmen |
| Tests (`test_parser`, `test_hard_clip*`, `test_calibration*`) | Testfälle | als Referenzfälle |

3. **Nicht übernehmen:** SVG-Reader (lieber `svgelements`: CSS, `use`, vollständiger), Weboberfläche, Datenmodell, CLI-Struktur.
4. **Optional:** Kontakt zu Oliver F. aufnehmen, wenn sinnvoll / Bugs gefunden werden, um Erfahrungen auszutauschen.

## 5. Auswirkung auf Geometrie & vpype (D-15)

MutohPlot zeigt, dass ein Eigenbau der Linien-Ebene mit reinen Python-Listen funktioniert, aber nicht skaliert. Eine reine Python-Liste ist zu langsam, aber ein schweres Framework wie `vpype` bringt zu viele unerwünschte CLI-Abhängigkeiten mit. Die Entscheidung (D-15) lautet daher: **Schlanker numpy/scipy-Kern.** `vpype` dient als wertvolle **Ideen- und Algorithmen-Ressource** (z. B. Referenz für Heuristiken beim Linemerge und 2-Opt), wird aber nicht als Abhängigkeit installiert.
