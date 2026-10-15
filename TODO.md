# TODO

Stand: 2026-10-14. Konzeptphase, noch kein Code.

## Am Plotter (nach dem Urlaub)

Details und Ergebnistabelle: [docs/devices/mutoh-xp500/testplan.md](docs/devices/mutoh-xp500/testplan.md) · Anleitung: [docs/devices/mutoh-xp500/einrichtung.md](docs/devices/mutoh-xp500/einrichtung.md)

- [ ] Q-14 Port: `ls -l /dev/serial/by-id/`, `lsusb`
- [ ] Q-16 Panel gemäß [einrichtung.md](docs/devices/mutoh-xp500/einrichtung.md) einstellen (USER1, Buffer Small, Sort Off, 0.025 mm, Hard Clip Exp)
- [ ] Q-18 Puffer auf 1000 Zeichen (Panel) oder per `ESC.@` begrenzen?
- [ ] Q-13 Randplot: Widersprüche der Notiztabelle, fehlende ~3,5 mm in X
- [ ] Abfragen: `ESC.A/B/E/L/O`, `OS`, `OE`, `OT` (Bedeutung von `1,1`), `OO`
- [ ] Testplots: Orientierung, Rand, Maßstab, `VS/FS/AS` pro Stift, `CV`, Durchsatz `PA` vs. `PR`, Abbruch mit `ESC.K`, Stiftsortierung, `WD`
- [ ] MutohPlot-Gegenprobe mit `--device-unit 0.025`
- [ ] Typenschild/Firmware notieren

## Handbuch

- [x] Kapitel 7 (Setup-/User-Parameter, Abb. 7.3) eingearbeitet in [docs/devices/mutoh-xp500/konfiguration.md](docs/devices/mutoh-xp500/konfiguration.md)
- [ ] Ggf. Beschreibung von `ESC.@`, `ESC.O`/`OS`-Bits, `CV`, `AP`, `GP` (falls es einen Befehlsteil mit Details gibt)

## Entscheidungen

- [x] Q-17 MutohPlot: Option C bestätigt, eigenständiges Projekt, Übernahme sinnvoller Module mit MIT-Hinweis (D-14)
- [x] Q-05 vpype: nicht als Abhängigkeit, dient als Ideen- und Algorithmen-Ressource (D-15)
- [x] User Stories überarbeitet (`docs/project/user-stories.md`)

## Später / Ideen

- Ideenspeicher: [docs/project/konzept.md §9](docs/project/konzept.md)
