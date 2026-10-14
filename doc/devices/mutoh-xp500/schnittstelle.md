# Mutoh XP-500 – Schnittstelle

Quellen: 📘 Handbuch Kap. 3 (S. 3-1…3-11), Appendix-4; 📏 eigene Messungen am Gerät; 🔧 MutohPlot.

## Übersicht

- Zwei Ports. RS-232C ist Standard; RS-422A (DB15), GP-IB und Centronics sind optional.
- Centronics ist **nur Empfang** (keine Abfragen wie `OH`/`OF` möglich), Kabel max. 2 m. Für Plotter Studio daher **ungeeignet**.
- Der Plotter ist **DTE** (sendet auf Pin 2, empfängt auf Pin 3), d. h. zum PC braucht es ein **Nullmodem**-Kabel.
- Port-Nummer und **Befehlsmodus** werden pro Port eingestellt (S. 3-11). Details stehen in Kapitel 7, das noch fehlt.

## RS-232C-Pinbelegung (DB25, Buchse am Plotter) 📘

| Pin | Signal | Richtung (aus Sicht Plotter) |
|---|---|---|
| 1 | FG (Schutzerde) | – |
| 2 | TXD | → aus |
| 3 | RXD | ← ein |
| 4 | RTS | → aus |
| 5 | CTS | ← ein |
| 6 | DSR | ← ein |
| 7 | SG (Signalmasse) | – |
| 8 | CD | ← ein |
| 15 | ST | ← ein |
| 17 | RT | ← ein |
| 18 | DTR | → aus (alternativ) |
| 20 | DTR | → aus (Standard) |
| übrige | nicht belegt | |

## Kabel

**25 ↔ 25 (Abb. 3.3) 📘:** 1–1, 2↔3 gekreuzt, RTS 4 → CD 8 (beidseitig gekreuzt), CTS 5 + DSR 6 auf jeder Seite gebrückt und vom DTR 20 der Gegenseite gespeist, 7–7.

**9 (PC) → 25 (Plotter) (Abb. 3.2):** aus der Zeichnung gelesen, ⚠️ **unsicher**:

| PC (DB9) | | Plotter (DB25) |
|---|---|---|
| 2 RXD | ← | 2 TXD |
| 3 TXD | → | 3 RXD |
| 4 DTR | → | 5 CTS + 6 DSR |
| 5 SG | – | 7 SG |
| 6 DSR + 8 CTS | ← | 20 DTR |
| 7 RTS | → | 8 CD |
| 1 CD | ← | 4 RTS |

**Wesentlich für den Handshake:** Der Plotter meldet „bereit/Puffer nicht voll“ über **DTR (Pin 20)**, und das landet am **CTS des PCs**. Deshalb funktioniert bei dir `stty … crtscts`.

## Parameter (Tabelle 3.5) 📘 und deine Einstellung 📏

| Parameter | Mögliche Werte | Deine Einstellung |
|---|---|---|
| Baudrate | Ext, 300, 400 (sic, vermutlich 600), 1200, 2400, 9600, 19200 | **19200** |
| Datenbits | 7, 8 | **8** |
| Parität | keine, gerade, ungerade | **keine** |
| Stoppbits | 1, 2 | **1** |
| Handshake (Software) | Off, ENQ/ACK, Xon-Xoff | **Aus** („Protokoll“) |
| DTR Control | Always On, Always Off, 18-pin, 20-pin | **20** (Pin 20 = Busy/Ready) |
| CTS Control | On, Off | **An** (Plotter beachtet sein CTS-Eingangssignal) |
| RTS Control | Always On, Always Off, Control | „RTS“ (vermutlich *Control*) |

- Es gibt **fünf vorprogrammierte Kombinationen USER1…USER5** (Kapitel 7 „User Parameter“). → Bitte notieren, welcher USER-Satz aktiv ist.
- 19200 Baud ist das Maximum. „Ext“ = externer Takt, nicht relevant.
- GP-IB: Adresse 0–30, Listen-only an/aus. Centronics: keine Parameter.

> [!NOTE]
> Die KI-Zusammenfassung nennt für den XP-511 „9600 Baud, gerade Parität, XON/XOFF“. Das ist **kein Werksstandard** aus dem Handbuch, sondern bestenfalls eine fremde Konfiguration. Maßgeblich ist deine funktionierende Einstellung oben.

## Linux-Setup 📏

```sh
stty -F /dev/ttyUSB0 19200 cs8 -parenb -cstopb crtscts -ixon -ixoff raw -echo
cat datei.hpgl > /dev/ttyUSB0
```

- Funktioniert an deinem Gerät (beobachtet mit `/dev/ttyS5` und `/dev/ttyUSB0`).
- Daten per Pipe an `tio` zu schicken schlägt fehl. Plotter Studio schreibt deshalb direkt auf das TTY (pyserial, `rtscts=True`).
- Für ein stabiles Gerät: udev-Symlink oder `/dev/serial/by-id/…` verwenden (Port noch nachzuliefern, Q-14).
- 🔧 MutohPlot: PL2303-Adapter mit Kernel-`IXON` können hängen. Bei XON/XOFF daher im Userspace auswerten. Mit RTS/CTS (dein Setup) tritt das nicht auf.
- ⚠️ USB-Seriell-Adapter puffern selbst (oft 256 B–4 KB FIFO + Kernelpuffer). Der Fortschritt „gesendet“ ist deshalb nicht „beim Plotter angekommen“ und erst recht nicht „gezeichnet“. Für Fortschritt und Abbruch: `ESC.B` abfragen bzw. `tcdrain()`, siehe [escape-sequenzen.md](escape-sequenzen.md).

## Durchsatz

8N1 bei 19200 Baud = 10 Bit pro Zeichen → **max. 1920 Zeichen/s**.

| Kodierung | Beispiel | Zeichen/Vektor | Vektoren/s |
|---|---|---|---|
| Jeder Punkt als eigener Befehl | `PA-12345,-6789;` | ~16 | ~120 |
| Koordinatenkette nach `PD` | `-12345,-6789,` | ~13 | ~150 |
| Relativ (`PR`), kurze Deltas | `12,-5,` | ~6 | ~320 |
| Relativ, Einheit 0,1 mm | `3,-1,` | ~5 | ~380 |

Beispiel: Eine Kurve aus 0,5-mm-Segmenten mit absoluten Ketten ergibt ≈ 150 × 0,5 = **75 mm/s**, weit unter den 900 mm/s der Mechanik. **Bei dichter generativer Grafik ist die serielle Leitung der Engpass.** Der 1-MB-Puffer überbrückt das nur, wenn die Mechanik langsamer zeichnet als die Daten nachkommen.

Konsequenzen für den Emitter (→ [konzept.md](../../konzept.md) §5/§7):
1. Koordinatenketten statt einzelner `PA`-Befehle (Standard).
2. Option **relative Koordinaten** (`PR`) mit periodischem absolutem Wiederaufsetzen (gegen Rundungsdrift: Deltas aus gerundeten Absolutwerten bilden, dann driftet nichts).
3. Linienvereinfachung mit Toleranz < halbe Strichbreite (vpype `linesimplify`).
4. Bögen/Kreise optional als `AA`/`CI` ausgeben, wenn die Quelle echte Kreise enthält (Profiloption, zunächst aus).
5. Unnötige Ziffern vermeiden: ganzzahlige Units, keine Leerzeichen, kein `;` innerhalb von Ketten.
