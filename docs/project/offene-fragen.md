# Offene Fragen & Entscheidungen

Stand: 2026-10-13 (Runde 4). Antworten bitte direkt hier eintragen oder im Chat geben.

## Offene Fragen

| ID | Frage | Vorschlag / Default |
|---|---|---|
| Q-05 | **vpype als Bibliothek?** Entscheidung: **Nein / Nicht nötig.** Eigener schlanker Geometriekern mit `numpy`/`scipy` ist sauberer, schneller und ohne Ballast. | D-15 |
| Q-13 | **Notiztabelle:** A3/A2 „portrait“ widersprüchlich; X-Rand ~3,5 mm kleiner als laut Handbuch | Randplot in AP0 |
| Q-14 | **Port:** `ls -l /dev/serial/by-id/` und `lsusb` | nachliefern, wenn am Plotter |
| Q-16 | **Panel-Einstellungen:** USER-Satz, Hard-Clip-Fenster, Empfangspuffer, Befehlsmodus und **Zeicheneinheit** (laut Handbuch 0,1…0,01 mm einstellbar; bei dir 0,025, bei MutohPlot 0,01) | nachliefern, wenn am Plotter, siehe [testplan.md](../devices/mutoh-xp500/testplan.md) |

## Beantwortet

| ID | Antwort |
|---|---|
| Q-01 | Nur für dich, aber als Open-Source-taugliches Projekt. |
| Q-02 | Mutoh XP-500, **Einzelblätter**, Handbuch vorhanden (Papier + PDF-Scan, nicht durchsuchbar). |
| Q-03 | **GPLv3** ok. |
| Q-04 | 19200 8N1, CTS-Handshake, `stty … crtscts` + `cat` funktioniert. Siehe [devices/mutoh-xp500/schnittstelle.md](../devices/mutoh-xp500/schnittstelle.md). |
| Q-06 | Gestrichen: Keine Integration generativer Kunst nötig. Externe Skripte exportieren Standard-SVG. |
| Q-07 | Erweiterungen in den Ideenspeicher (konzept.md §9). |
| Q-08 | „Ja und nein“: SVG ok, aber die Anzeige wird eventuell zum einfachen Editor ausgebaut. → SVG + Namespace mit **versioniertem Schema**, das Modell ist führend (konzept.md §3.4). |
| Q-09 | Plotter hängt am Arbeitsplatzrechner. → plotd mit HTTP nur auf `127.0.0.1`. |
| Q-10 | Phase 1: Importieren & Anordnen. Phase 2: Objekte selektieren, verändern, löschen. Mehr später. |
| Q-11 | Viele verschiedene Stifte (Tusche, Bleistift …), **max. 8 pro Plot**. → Werkzeugbibliothek + Geschwindigkeit pro Stift + Stifttest-Plot in Phase 1. |
| Q-12 | Handbuch Kapitel 7 transkribiert in [devices/mutoh-xp500/konfiguration.md](../devices/mutoh-xp500/konfiguration.md). |
| Q-15 | Phase-1-Umfang bestätigt. |
| Q-17 | Plotter Studio ist eigenständig. Code-Übernahmen aus MutohPlot nach Bedarf mit MIT-Hinweis. Oliver F. wird informiert, wenn sinnvoll / Bugs gefunden. |
| Q-18 | Puffergröße am Panel auf `Small` (1000 Zeichen) stellen. |

## Entscheidungen

| ID | Entscheidung | Begründung |
|---|---|---|
| D-01 | Kern ohne Qt (numpy/Python), Qt nur in der GUI | Headless, Tests (Review B2) |
| D-02 | Stift ist Attribut, Objektbaum unabhängig | mehrfarbige Gruppen (Review B1) |
| D-03 | Nur Software-Koordinatentransformation, kein IP/SC | eine Testmatrix (Review B3) |
| D-04 | Plot-Dienst als eigener Prozess mit persistenten Jobs (Phase 1: inline) | lange Jobs, Resume (Review B4) |
| D-05 | Logische Stifte → Werkzeuge → Slots (Phase 1: Stift n = Slot n), max. 8 | Q-11 |
| D-06 | Flusskontrolle RTS/CTS (Default) oder XON/XOFF im Userspace. Schnelle Pause/Abbruch über 1000-Zeichen-Plotterpuffer, `ESC.B` optional | verifiziert / MutohPlot |
| D-07 | Reihenfolge: Hardware → CLI → GUI Phase 1 → GUI Phase 2 → Ideen | Nutzen früh (Review B7) |
| D-08 | Lizenz GPLv3, GUI mit PySide6 | Q-03 |
| D-09 | Nur Einzelblätter A4–A0 | Q-02 |
| D-10 | Ursprung = Hard-Clip-Mitte. Ränder aus Panel-Fenster + 4-Rand-Kalibrierung, `OH` vor jedem Job, **Einheit aus `OF`** | Messungen + MutohPlot |
| D-11 | Keine Integration generativer Kunst. Externe Skripte exportieren Standard-SVG | Q-06 |
| D-12 | plotd-API: HTTP/WebSocket auf `127.0.0.1` | Q-09 |
| D-13 | Projektdatei: SVG + `ps:`-Namespace, versioniert, Modell führend | Q-08 |
| D-14 | MutohPlot: keine Abhängigkeit. Module portieren (MIT-Hinweis), als Übergangswerkzeug und Referenz nutzen (vorbehaltlich Q-17) | [analyse-mutohplot.md](analyse-mutohplot.md) |
| D-15 | Kein vpype als Abhängigkeit: Schlanker, eigener Geometriekern mit `numpy`/`scipy` (Bézier, Merge, KD-Tree Sortierung) ist wartungsärmer und schneller | Q-05 |
