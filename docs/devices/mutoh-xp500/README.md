# Mutoh XP-500 – Gerätedokumentation

Gesammelte, geprüfte Informationen zum Mutoh XP-500 (DIN-A0-Stiftplotter, MH-GL / HP-GL), aufbereitet für Plotter Studio (Geräteprofil, Treiber, `plotd`).

## Inhalt

| Datei | Inhalt |
|---|---|
| [einrichtung.md](einrichtung.md) | **Schnellstart & Einrichtung:** Schritt-für-Schritt-Anleitung für Bedienfeld, Linux/Kabel, Papier/Rollen und PC-Test |
| [konfiguration.md](konfiguration.md) | **Bedienfeld-Menü (Kapitel 7):** Menühierarchie, Online-Parameter (Tabelle 7.1), Environment (Hard Clip Fig 7.3, Sort, Smoothing, Buffer Size), Command (Emulation, Program Step, VS/AS/FS) |
| [spezifikationen.md](spezifikationen.md) | Technische Daten (Geschwindigkeit, Auflösung, Andruck, Stifte, Hard-Clip, Umgebung, Maße) |
| [schnittstelle.md](schnittstelle.md) | RS-232C: Pinbelegung, Kabel, Parameter, Handshake, Linux-Setup, Durchsatz |
| [einheiten-und-koordinaten.md](einheiten-und-koordinaten.md) | Zeicheneinheit (konfigurierbar!), Ursprung, Achsen, Hard-Clip-Fenster, Randmessungen |
| [mhgl-befehle.md](mhgl-befehle.md) | Vollständige MH-GL-Befehlstabelle aus dem Handbuch + Relevanz für Plotter Studio |
| [escape-sequenzen.md](escape-sequenzen.md) | Device-Control-Befehle (`ESC.x`) für Puffer, Status, Abbruch, Handshake |
| [emulator.md](emulator.md) | **Software-Emulator (`virtual_plotter`):** PTY/TCP-Simulation von Firmware, Puffer und HP-7585B-Befehlen |
| [testplan.md](testplan.md) | Was am Gerät noch geprüft werden muss (Checkliste für AP0) |

## Quellen

| Kürzel | Quelle | Verlässlichkeit |
|---|---|---|
| 📘 **HB** | *MUTOH XP-500 Series User Guide* (XP-510/XP-511), PDF-Scan, auch unter `https://www.synthmind.com/xp-510-511_ug_en.pdf`. Extrahierte Seiten: [`tmp/mutoh-xp500-manual/`](../../../tmp/mutoh-xp500-manual/) | hoch (Herstellerangabe) |
| 📏 **M** | Eigene Messungen am Gerät (siehe [einheiten-und-koordinaten.md](einheiten-und-koordinaten.md)) | hoch (am Referenzgerät) |
| 🔧 **MP** | MutohPlot (Oliver F., MIT), an einem XP-500 hardwaregetestet: [analyse-mutohplot.md](../../project/analyse-mutohplot.md) | mittel–hoch (anderes Gerät, andere Einstellungen) |
| 🇯🇵 **FAQ** | Japanische Mutoh-FAQ (Hinweis per Chat) | mittel |
| ❓ **KI** | KI-Zusammenfassung [`tmp/mhgl-interpolated-information.md`](../../../tmp/mhgl-interpolated-information.md) | **ignoriert** (überholt/unzuverlässig) |

Extrahierte Handbuchseiten:

| Datei | Handbuch |
|---|---|
| `configure-001…031.png` | Kapitel 7 „Configuring the Plotter“, S. 7-1…7-31 (vollständig ausgewertet) |
| `interface-001…011.png` | Kapitel 3 „Connecting the Plotter“, S. 3-1…3-11 |
| `specifications-001…003.png` | Appendix-2…4 (General / Interface Specifications) |
| `mhgl-001…006.png` | Appendix-5…10 (MH-GL-Befehlstabelle) |
| `esc-001…002.png` | Appendix-11…12 (Device-Control-Befehle) |

## Die wichtigsten Erkenntnisse für Plotter Studio

1. **Die Zeicheneinheit ist einstellbar:** 0,1 / 0,05 / 0,025 / 0,0125 / 0,01 mm (📘 „Software Resolution“). Deshalb liefert dein `OF;` den Wert 40, während MutohPlot mit 0,01 mm arbeitet. → **Einheit immer per `OF;` lesen**, nie fest annehmen.
2. **Die serielle Leitung ist der Flaschenhals:** Bei 19200 Baud kommen maximal ca. 1900 Zeichen/s an. Bei dichten Kurven begrenzt das die Zeichengeschwindigkeit stärker als die Mechanik (900 mm/s). → Kompakte Kodierung (Koordinatenketten, `PR`, ggf. gröbere Einheit), siehe [schnittstelle.md](schnittstelle.md#durchsatz).
3. **Device-Control ist vorhanden:** `ESC.B` (freier Puffer), `ESC.L`, `ESC.K` (Abbruch), `ESC.E`/`ESC.O` (Status) stehen im Handbuch → Grundlage für die Puffer-, Fortschritts- und Abbruchstrategie in `plotd`.
4. **Pro-Stift-Parameter in Firmware:** `VS v,pen`, `FS force,pen`, `AS acc,pen` → Werkzeugbibliothek kann direkt auf Gerätebefehle abgebildet werden. Andruck 15–450 g.
5. **Hard-Clip-Fenster** sind Herstellerangaben (Norm/Exp/Type 1/Type 3). Deine `OH`-Messungen passen in Y zu `Exp`, in X fehlen ca. 3,5 mm → am Gerät klären.
