# Arbeitspakete & Meilensteine

Stand: 2026-10-14 (v2.2) · Basis: [konzept.md](konzept.md) v2.2
Aufwand: S ≈ 1–3 Abende, M ≈ 1–2 Wochenenden, L ≈ mehrere Wochenenden.

## Meilensteine

| Meilenstein | Inhalt | Nutzen |
|---|---|---|
| **M0 – Hardware verstanden** | AP0 | vollständig verifiziertes Geräteprofil |
| **M1 – CLI-Plot** | AP1–AP4 | SVG → Blatt plotten ohne GUI, mit Blatterkennung, Optimierung, Fortschritt, Abbruch, Resume |
| **M2 – GUI Phase 1** | AP5–AP6 | Importieren & Anordnen, Stifte, Pre-Flight-Vorschau, Gerätesteuerung |
| **M3 – GUI Phase 2** | AP7 | Objekte innerhalb von Importen selektieren, verändern, löschen |
| später | Ideenspeicher (konzept.md §10) | generative Kunst, Text, Schraffur … |

```mermaid
flowchart LR
  AP0 --> AP2
  AP1 --> AP2
  AP1 --> AP4
  AP2 --> AP3
  AP4 --> AP3
  AP3 --> AP5
  AP4 --> AP5
  AP5 --> AP6
  AP6 --> AP7
```

---

## AP0 – Hardware-Spike Mutoh XP-500 (S) ⚠️ zuerst
Bereits bekannt (siehe [devices/mutoh-xp500/](devices/mutoh-xp500/README.md)): Schnittstelle, Handshake, `OI`=7585B, `OF`, `OH`-Werte, Ursprung, Achsen, Randsummen. Aus MutohPlot außerdem: Hard-Clip-Fenster, Puffer-Einstellung 1 MB/1000 Zeichen, Achsabbildung, Abbruch über LOCAL/RESET.

Noch offen. Zuerst Panel und Handbuch, dann mit Skript `tools/xp500_probe.py` (pyserial) prüfen:
0. **Panel-Einstellungen notieren:** Hard-Clip-Fenster (Norm/Exp/Type 1/Type 3), Empfangspuffer (1 MB/1000 Zeichen), Befehlsmodus/Auflösung (warum `OF` = 40 statt 100 wie bei MutohPlot?), Vektorsortierung.
   **Querprüfung:** MutohPlot lokal installieren und einen Kalibrierplot damit ausgeben. Einheit beachten, ggf. `--device-unit 0.025`.
1. **Puffer:** `ESC.L` (Puffergröße), `ESC.B` (freier Puffer), Antwort-Terminator (`ESC.M`). Verhalten mit 1000-Zeichen-Puffer und RTS/CTS.
2. **Abbruch:** verwirft `ESC.K` den Puffer? Wie verhält sich die Pause-Taste?
3. **Sync:** Antwortet `OA;` erst, wenn die vorherigen Befehle ausgeführt sind?
4. **Befehle:** `VS v,pen`, `FS`, `AS`, `CI`, `PR`, maximale Punkte pro `PD`. Bedeutung von `OT;`.
5. **Firmware-Vektorsortierung**: an/aus und Wirkung.
6. **Orientierungsplot:** Pfeile „+X/+Y“, Beschriftung der Ecken, Blatt-Oberkante markieren → `insert_matrix` (Kandidat aus MutohPlot bestätigen).
7. **Randplot (4-Rand-Kalibrierung wie MutohPlot):** Rechteck exakt auf dem Hard-Clip plotten, Abstände zu allen vier Blattkanten messen (A4, A3, A2, je beide Lagen) → Ränder je Kante, Abgleich mit Fenstertabelle. Klärt auch die Tabellen-Widersprüche.
8. **Maßhaltigkeit:** Rahmen 1000 × 700 mm auf A0 (bzw. 500 × 350 auf A2) + Kreuze, mit Stahlmaß messen → `scale_x/y`.
9. **Bewegungsmessung:** Linien 1/10/100/500 mm, Zeiten messen, Stiftwechsel stoppen → `motion`.

**Ergebnis:** `resources/devices/mutoh_xp500.yaml` (alle `?` aufgelöst) + Abschnitt „Verifizierte Fakten“ ergänzt.

> [!TIP]
> Bis Plotter Studio plotten kann, lässt sich **MutohPlot als Übergangswerkzeug** nutzen (`mutohplot web` lokal).

## Übernahmen aus MutohPlot (MIT, Hinweis beibehalten)
| AP | Modul | Zweck |
|---|---|---|
| AP2 | `hard_clip.py`, `transform/hard_clip.py`, `calibration*.py` | Fenstertabelle, Mittelpunktkorrektur, Kalibrierzeichnung und -profil |
| AP3 | `serial_io.py` | Userspace-XON/XOFF, `OF`/`OH`-Abfrage |
| AP4 | `hpgl/tokenizer.py`, `hpgl/parser.py`, `hpgl/stroke_font.py` | HP-GL-Import |
| AP4 | `optimize/paths.py` (Dedupe) | Duplikate erkennen und entfernen |
| alle | passende Tests | Referenzfälle |

## AP1 – Core: Polylinien & Geometrie (M)
- **Schlanker numpy/scipy-Kern (Entscheidung D-15):** Eigener Polylinien-Datentyp (`ndarray`). Algorithmen (Bézier-Diskretisierung, Endpunkt-Merge, KD-Tree 2-Opt) orientieren sich an den Konzepten von vpype/MutohPlot als Ideen- und Algorithmen-Ressource, jedoch ohne externe Monster-Abhängigkeiten.
- Polylinien-Datentyp (numpy), Stift-Zuordnung.
- Adaptive Bézier-/Bogen-Diskretisierung mit Sehnentoleranz.
- Affine Transformationen, Bounding Boxes, Statistik (Längen, Leerweg).
- Unit-Tests (pytest + hypothesis).

**Abnahme:** Kreis r = 100 mm bei 0,05 mm Toleranz → max. Abweichung ≤ 0,05 mm, minimale Punktzahl.

## AP2 – Device: Profil, Abbildung, Blatterkennung, HPGL-Emitter (M)
- YAML-Profil + Validierung (pydantic).
- Abbildung Papier-mm → Units nach konzept.md §4 (Hard-Clip-Mitte, Ränder, Einlage-Matrix, Maßstab).
- Blatterkennung aus `OH` (Format + Lage), Warnung bei Abweichung.
- Emitter (7585B): `PA`/`PR`, Punktlisten, Stiftwechsel, `VS`, Init/End.
- Kalibrier- und Testplots als eingebaute Jobs (Orientierung, Ränder, Rahmen, Stifttest).

**Abnahme:** Golden-File-Tests. Ein auf A3 zentriert geplottetes Rechteck sitzt auf ±1 mm mittig, unabhängig von der Rollenposition.

## AP3 – plotd: Streaming, Jobs, CLI (M–L)
- Serieller Transport (pyserial, `rtscts`, by-id, Reconnect), Strategien `handshake` / `handshake+poll` / `sync`.
- Job-Format (hpgl + index + state), Zustandsautomat, Pause/Abbruch/Resume ab Checkpoint, Stiftwechsel-Prompt.
- CLI `plotter-studio plot|status|pause|abort|resume|jobs|probe`. In Phase 1 inline, die Dienst-API ⟨Q-09⟩ folgt vor AP6.
- **Virtueller Plotter** (pty, simuliert 7585B inkl. Puffer, `OH`, `ESC.B`, rendert PNG) für Tests ohne Papier.

**Abnahme:** 30-minütiger Testjob ohne Fehlzeichnung. Abbruch stoppt innerhalb von ≤ 5 s (falls `ESC.K`/Polling verfügbar). Resume nach Abziehen des USB-Steckers funktioniert.

## AP4 – Pipeline, Optimierer, Import, Schätzer (M)
- SVG-Import (svgelements): Strichfarbe/Ebene → Stift, Füllungen ignorieren (Warnung), Gruppen erhalten. Auto-Farbreduktion (Clustering auf $\le 8$ Stifte).
- HPGL/PLT-Import (vorhandene Dateien ansehen, umplatzieren, senden).
- Pipeline: Clip, Merge, Simplify, Dedupe, Sort (Greedy + 2-Opt, Umkehr, Startpunkt-Rotation), Pen-Order.
- Zeitschätzer, Pre-Flight-Report.
- CLI: `plotter-studio plot file.svg --page A3 --center --margin 20mm [--preview out.png] [--monochrome / --pens 1,2]`.

**Abnahme = M1:** Ein Inkscape-SVG wird per CLI auf das eingelegte Blatt zentriert, optimiert und mit Fortschrittsanzeige geplottet.

## AP5 – GUI Phase 1: Layout-Modus (L)
- Hauptfenster (PySide6), Canvas (Blatt, plottbarer Bereich, Lineale, Zoom/Pan, WYSIWYG-Strichbreite in mm, Überstands-Warnung).
- Dokumentmodell, Undo/Redo, Projektdatei ⟨Q-08⟩.
- Papiermaße: Presets, freie mm-Maße, Knopf „Papiergröße vom Gerät holen“ (`OH;`).
- Import (Dialog mit Mapping-Vorschau, Drag & Drop), Import-Objekte verschieben/skalieren/drehen/löschen, numerische Eingabe.
- Platzierungswerkzeuge: Zentrieren, prozentuale Ausrichtung ($50\%, 50\%$), 1:1 Originalgröße (für CAD/Schaltpläne), Einpassen mit Rand (mm oder %), Skalieren um $x\%$ oder auf Zielmaße in mm.
- Stift-Panel mit dynamischem Remapping (Farben zusammenführen, Monochrom-Knopf, Stiftzuweisung per Selektion/Tastatur `1`–`8`).

## AP6 – GUI Phase 1: Plot-Modus & Gerätesteuerung (M–L)
- Kompilierte Vorschau mit Leerfahrten, Scrubber, Stift-Filter.
- Pipeline-Optionen mit Live-Statistik (Worker-Thread).
- Gerätepanel als plotd-Client: Verbinden, Blatt erkennen, Start/Pause/Abbruch/Resume, Fortschritt im Canvas.

**Abnahme = M2.**

## AP7 – GUI Phase 2: Objekte bearbeiten (M)
- Objekt-Panel (Baum), Gruppe „betreten“, Unterauswahl, Transformieren, Stift zuweisen, Löschen.

**Abnahme = M3.**
