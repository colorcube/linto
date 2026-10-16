# Mutoh XP-500 – Software-Emulator (`virtual_plotter`)

Der Software-Emulator simuliert das Verhalten eines Mutoh XP-500 Plotters (HP-7585B Emulation) unter Linux.
Er stellt eine virtuelle serielle Schnittstelle (Linux-PTY oder TCP-Socket) bereit, mit der sich Plotter Studio, `plotd`, `pyserial`, aber auch externe Tools (wie MutohPlot oder InkCut) verbinden können – exakt so, als wäre ein physischer USB-Seriell-Adapter angeschlossen.

---

## 1. Schnellstart

### Emulator im Terminal starten
```bash
python -m plotter_studio.emulator
```

Ausgabe:
```text
================================================================
 🖋️  Mutoh XP-500 Plotter Emulator (HP-7585B Simulation)
================================================================
 Format:           A3 (420 x 297 mm)
 Ränder (Profil):  EXP (390.0 x 287.0 mm Hard-Clip)
 Auflösung:        0.025 mm/Unit (40 Units/mm)
 Puffer:           SMALL (1,000 Bytes)
 Verbindung:       /path/to/plotter-studio/virtual_plotter
 Mechanik:         Sofortige Abarbeitung (Fast-Mode)
================================================================
Warte auf Befehle... (Drücke Strg+C zum Beenden)
```

Der Emulator legt standardmäßig einen Symlink `./virtual_plotter` an, der auf das zugewiesene Pseudoterminal (z. B. `/dev/pts/3`) zeigt.

### Testen per Terminal
In einem zweiten Terminal kann direkt mit dem virtuellen Plotter kommuniziert werden:
```bash
# Befehlsabfrage senden (z. B. Stiftplotter-Identifikation)
echo -ne "OI;\r" > ./virtual_plotter
head -n 1 < ./virtual_plotter
# Antwort: 7585B
```

### Langsame Schnittstelle simulieren (z. B. 300 Baud)
Um serielle Übertragungen historisch authentisch oder für Time-out- und Puffer-Stresstests zu verlangsamen:
```bash
# 300 Baud (~30 Bytes/Sekunde bei 8N1) über TCP
python -m plotter_studio.emulator --tcp 9999 --baudrate 300 --realtime

# 1200 Baud über virtuelles PTY
python -m plotter_studio.emulator --baudrate 1200
```

---

## 2. CLI-Optionen

| Option | Werte / Standard | Beschreibung |
|---|---|---|
| `--paper` | `A4`, `A3`, `A2`, `A1`, `A0` (Default: `A3`) | Simuliertes Papierformat |
| `--margin` | `EXP`, `NORM`, `TYPE1`, `TYPE3` (Default: `EXP`) | Hard-Clip-Randprofil laut Handbuch Abb. 7.3 |
| `--buffer` | `small`, `large` (Default: `small`) | Eingangspuffer: `small` (1000 Zeichen, Panel-Einstellung) oder `large` (1 MB) |
| `--unit` | `0.025`, `0.010` (Default: `0.025`) | Auflösung in mm pro Einheit (`OF;` meldet 40 bzw. 100) |
| `--symlink` | Pfad (Default: `./virtual_plotter`) | Pfad für den Symlink auf das PTY-Device |
| `--tcp` | Port (z. B. `9999`) | Startet TCP-Server statt Linux-PTY |
| `--realtime` | Flag (Default: aus) | Simuliert echte mechanische Verfahr- und Stiftwechselzeiten |
| `--speedup` | Zahl (Default: `5.0`) | Beschleunigungsfaktor für die Echtzeit-Simulation |
| `--baudrate` | Zahl (z. B. `300`, `1200`, `9600`, `19200`) | Drosselt serielle Übertragung exakt nach Baudrate (8N1, z. B. 30 Bytes/s bei 300 Baud) |
| `--svg-output` | Pfad (Default: `./emulator_output.svg`) | Speichert beim Beenden (Strg+C) alle gezeichneten Vektoren als SVG |

---

## 3. Unterstützte Befehle

### Abfragen (Inquiries)
* `OI;` / `ESC.A` → `7585B\r` (Plotter-Identifikation HP-7585B)
* `OF;` → `40,40\r` (Auflösung in Units/mm, bei `--unit 0.025`) bzw. `100,100\r`
* `OH;` → `xmin,ymin,xmax,ymax\r` (Hard-Clip-Grenzen in Center-Origin-Koordinaten)
* `OT;` → `1,1\r` (8-fach Karussell eingesetzt, Stift geladen)
* `OS;` / `ESC.O` → `16\r` (Status normal)
* `OE;` / `ESC.E` → `0\r` (Fehlerspeicher)
* `OA;` / `OC;` → `x,y,pen_state\r` (aktuelle Koordinaten & Stiftstatus `0`=oben, `1`=unten)
* `ESC.B` → freie Pufferkapazität in Bytes (z. B. `1000\r`)
* `ESC.L` → Gesamtpuffergröße in Bytes (z. B. `1000\r` oder `1048576\r`)

### Vektor- und Steuerbefehle
* `IN;` / `ESC.R` → Initialisierung / Reset auf Einschaltzustand
* `ESC.K` → Abort (sofortiger Abbruch: leert Puffer, hebt Stift `PU`)
* `SP n;` → Stiftwechsel (0 = kein Stift / ablegen, 1..8 = Stift 1..8)
* `VS v[,pen];` → Stiftgeschwindigkeit in cm/s
* `FS f[,pen];` → Stiftandruck (1..8)
* `AS a[,pen];` → Beschleunigung (1..4 G)
* `PU [x,y...];` → Stift heben (+ optional verfahren)
* `PD [x,y...];` → Stift senken (+ optional zeichnen)
* `PA x,y[,x2,y2...];` → Absolute Koordinaten (auch Koordinatenketten)
* `PR dx,dy[,dx2,dy2...];` → Relative Koordinaten

---

## 4. Nutzung in automatisierten Tests

Der Emulator ist modular aufgebaut und kann in Pytest-Fixtures direkt im selben Prozess verwendet werden:

```python
from plotter_studio.emulator import VirtualPlotter, PtyServer

plotter = VirtualPlotter(paper="A3", buffer_size=1000)
server = PtyServer(plotter, symlink_path="/tmp/my_plotter")
port = server.start()

# Verbindung via pyserial oder Datei-Handle
# ... Tests ausführen ...

server.stop()
```
