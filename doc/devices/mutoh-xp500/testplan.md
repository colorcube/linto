# Mutoh XP-500 – Testplan am Gerät (AP0)

Checkliste für den nächsten Termin am Plotter. Ergebnisse bitte direkt hier eintragen.
Gesammelte Gesamtliste aller offenen Punkte: [TODO.md](../../../TODO.md).

## 1. Ablesen (ohne Plot)

- [ ] Typenschild: Modell (XP-510 / XP-511 / …), Firmware-Version (Einschaltmeldung)
- [ ] Port: `ls -l /dev/serial/by-id/` und `lsusb` (Q-14)
- [ ] Panel: aktiver **USER-Parametersatz** (USER1…5) und dessen Werte (Baud, Handshake, DTR/CTS/RTS Control)
- [ ] Panel: **Befehlsmodus** (MH-GL / HP-GL / …?) und **Zeicheneinheit** (Setup → Befehl (MH-GL) → Zeicheneinheit)
- [ ] Panel: **Hard-Clip-Fenster** (Norm / Exp / Type 1 / Type 3 / gibt es Type 2?)
- [ ] Panel: **Empfangspuffer** (1 MB / 1000 Zeichen) (Q-16, Q-18)
- [ ] Panel: Stift-Einstellungen (Geschwindigkeit/Andruck pro Stift? automatischer Andruck?), Vektorsortierung, Kurvenglättung
- [ ] Wenn möglich: Kapitel 7 des Handbuchs (Setup-/User-Parameter, Abb. 7.3) scannen

## 2. Abfragen (Terminal, `tio --local-echo`)

| Befehl | Erwartung | Ergebnis |
|---|---|---|
| `ESC.A` | Identifikation | |
| `ESC.L` | Puffergröße (≈ 1 MB oder 1000) | |
| `ESC.B` | freier Platz (= `ESC.L` bei leerem Puffer) | |
| `ESC.O` | Statuszahl, z. B. mit/ohne Blatt, in LOCAL | |
| `ESC.E` | 0 | |
| `OS;` | Statusbyte | |
| `OE;` | 0 | |
| `OT;` | mit allen Stiften / ohne Stift / Stift 3 entnommen → Bedeutung von `1,1` | |
| `OO;` | Optionen | |
| `OA;` | Position + Stiftstatus | |
| `OF;` | 40,40; danach Zeicheneinheit am Panel ändern → neuer Wert? (zurückstellen!) | |

## 3. Testplots

- [ ] **Orientierung:** Pfeil +X, Pfeil +Y, Text „OBEN“ an der Blattoberkante → Achsmatrix/Vorzeichen bestätigen
- [ ] **Randplot:** Rechteck exakt auf den Hard-Clip (`OH`) + Lineal/Messung der Abstände zu allen vier Blattkanten → $m_{x-}, m_{x+}, m_{y\pm}$, Fenstertyp, fehlende 3,5 mm in X (Q-13)
- [ ] **Maßstab:** 400 mm-Strecke in X und Y messen → Streckengenauigkeit (Spec: ±0,1 % bzw. ±0,25 mm)
- [ ] **Stiftparameter:** `VS v,pen` / `FS f,pen` / `AS a,pen`. Wirkt der Stiftparameter? Bleibt der Wert über `SP`-Wechsel und `IN` erhalten?
- [ ] **`CV`:** Kreis aus 360 kurzen Segmenten mit `CV0` vs. `CV1` → Laufruhe und Zeit
- [ ] **Durchsatz:** dieselbe dichte Kurve absolut (`PA`) vs. relativ (`PR`) → Zeit messen (siehe [schnittstelle.md](schnittstelle.md#durchsatz))
- [ ] **Abbruch:** großen Plot starten, nach 10 s `ESC.K` → stoppt er? Wie schnell bei 1 MB vs. 1000 Zeichen? Mit `ESC.@1000;…:` als Software-Limit?
- [ ] **Stiftsortierung:** Datei mit SP2 → SP1 → SP2 → wird in dieser Reihenfolge gezeichnet?
- [ ] **`WD`:** Text auf das LCD schreiben (Stiftwechsel-Hinweis) → funktioniert? Terminator?
- [ ] **Gegenprobe MutohPlot** mit `--device-unit 0.025` (Q-17)
