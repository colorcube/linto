# Mutoh XP-500 – Device-Control-Befehle (Escape-Sequenzen)

Quelle: 📘 Handbuch Appendix-11…12 (`esc-001…002.png`). Alle Befehle beginnen mit `ESC` (0x1B) + `.`. Sie werden **vor** dem MH-GL-Parser ausgewertet, wirken also auch, wenn der Puffer voll ist (sofern der Handshake das Senden erlaubt; siehe unten).

Status: alle 📘, noch **nicht am Gerät getestet**.

## Plotterverwaltung

| Befehl | Parameter | Funktion | Nutzung in `plotd` |
|---|---|---|---|
| `ESC.A` | – | Identifikation ausgeben | ○ Verbindungstest |
| **`ESC.B`** | – | **Freier Platz im logischen Eingangspuffer** | ● Fortschritt, Pufferstrategie `+poll` |
| **`ESC.E`** | – | **Erweiterter Fehler** (I/O-Fehler) | ● Diagnose |
| `ESC.J` | – | Abort device control (laufende Ausgabe abbrechen) | ○ |
| **`ESC.K`** | – | **Abort graphics: MH-GL-Auswertung abbrechen, Puffer verwerfen** | ● **Abbruch** |
| **`ESC.L`** | – | **Puffergröße, wenn leer** | ● beim Verbinden: Puffergröße (1 MB vs. 1000 Zeichen) erkennen |
| **`ESC.O`** | – | **Erweiterter Status** (z. B. Local, Blatt fehlt, Puffer leer) | ● Zustandsautomat |
| `ESC.Q n:` | `n` | Monitormodus | ○ Debug |
| **`ESC.R`** | – | **Kommunikation auf Einschaltzustand zurücksetzen** | ● beim Verbinden |
| `ESC.S n:` | `n` | Konfigurierbare Speichergröße ausgeben | ○ |
| `ESC.T` | `phys I/O;polygon;dl char;0;vector buf;pen sort buf:` | **Speicher aufteilen**, u. a. **Vektorpuffer** und **Stift-Sortierpuffer** | ○ siehe unten |
| `ESC.U` | – | Flush-Modus beenden | ○ |
| `ESC.Y` / `ESC.(` | – | Plotter EIN (Daten werden interpretiert) | ● |
| `ESC.Z` / `ESC.)` | – | Plotter AUS (Daten werden ignoriert) | ○ |
| `ESC.@` | `logical I/O buffer size;I/O conditions:` | Logische Puffergröße + I/O-Bedingungen setzen | ○ **Pufferlimit per Software** statt Panel |

## Handshake

| Befehl | Parameter | Funktion |
|---|---|---|
| `ESC.H` | `blocksize;enq char;ack string:` | ENQ/ACK-Handshake konfigurieren |
| `ESC.I` | `xoff threshold;(omitted);xon trigger:` | XON/XOFF- bzw. ENQ/ACK-Parameter |
| `ESC.M` | `turnaround delay;output trigger;echo terminator;output initiator:` | Antwortformat (Terminator, Verzögerung) |
| `ESC.N` | `interchar delay;handshake param:` | Zeichenverzögerung |
| `ESC.P` | `handshake:` | Einen der drei Standard-Handshakes wählen |

Für dein Setup (Hardware-Handshake über DTR→CTS) wird davon nichts benötigt. `ESC.M` kann relevant sein, falls Antworten ein unerwartetes Abschlusszeichen haben (Standard: CR).

## Konsequenzen für `plotd` (→ [konzept.md §6](../../konzept.md))

1. **Verbindungsaufbau:** `ESC.R` → `ESC.L` (Puffergröße) → `IN;` → `OI;` `OF;` `OH;` `OT;`.
2. **Puffergrenze per Software:** `ESC.@1000;…:` könnte den logischen Puffer auf ~1000 Zeichen begrenzen, **ohne am Panel umzustellen** (Q-18). Dann reagieren Pause und Abbruch schnell, während andere Programme (InkCut, `cat`) nach einem `ESC.R`/Neustart weiter den vollen Puffer nutzen. → testen.
3. **Fortschritt:** `ESC.B` liefert den freien Platz. Gesendete Bytes − (Puffergröße − frei) = vom Plotter *ausgewertete* Bytes. Das ist genauer als „gesendet“, weil der USB-Adapter puffert. Mit `OA;` als Sync-Punkt erhält man „wirklich gezeichnet bis hier“.
4. **Abbruch:** Host-Sendepuffer leeren (`tcflush(TCOFLUSH)`), dann `ESC.K`, dann `PU;SP0;`. Fallback ohne Wirkung: Hinweis „am Gerät LOCAL → RESET“ (🔧 MP).
5. ⚠️ **Hardware-Handshake und ESC:** Wenn der Plotter per DTR „voll“ meldet, sendet der Host (bei `crtscts`) **auch kein `ESC.K`**. Mit 1-MB-Puffer kann ein Abbruch deshalb erst nach langer Zeit greifen. Das ist ein weiterer Grund für eine kleine logische Puffergrenze (Punkt 2) bzw. für die Strategie `+poll` (Host sendet nur so viel, wie laut `ESC.B` frei ist, und der Hardware-Handshake bleibt nur Sicherheitsnetz).
6. **Stiftsortierung in Firmware:** `ESC.T` hat einen *pen sort buffer*. Wenn die Firmware Vektoren nach Stift umsortiert, kann sie die von Plotter Studio optimierte Reihenfolge verändern (und z. B. Bleistift-vor-Tusche-Reihenfolgen kaputt machen). → Testen, ob sie aktiv ist, und ggf. mit Puffergröße 0 abschalten.
