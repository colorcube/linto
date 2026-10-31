# Mutoh XP-500 – Einrichtung & Schnellstart für LINTO

Stand: 2026-10-14 · Praxis-Leitfaden für die Inbetriebnahme am Linux-Rechner

Dieses Dokument fasst die konkreten Schritte zusammen, um den **Mutoh XP-500** am Bedienfeld und unter Linux optimal für den Betrieb mit **LINTO** (oder MutohPlot) zu konfigurieren.

---

## 1. Verkabelung & Linux-Setup

### Verkabelung
* **USB-RS232-Adapter:** Vorzugsweise FTDI- oder Prolific/CH340-Chipsatz mit vollständiger Signalbelegung (mindestens TXD, RXD, GND, RTS, CTS, DTR).
* **Nullmodem-/Crossover-Kabel:**
  * TXD (2) $\leftrightarrow$ RXD (3)
  * RXD (3) $\leftrightarrow$ TXD (2)
  * GND (7) $\leftrightarrow$ GND (7)
  * RTS (4) $\leftrightarrow$ CTS (5)
  * CTS (5) $\leftrightarrow$ RTS (4)
  * DTR (20) $\leftrightarrow$ DSR/DCD (6/8)

### Linux-Rechner
1. **Benutzergruppe:** Sicherstellen, dass dein Linux-Benutzer auf serielle Ports zugreifen darf:
   ```bash
   sudo usermod -aG dialout $USER   # Auf Debian/Ubuntu
   # bzw. sudo usermod -aG uucp $USER  # Auf Arch/openSUSE
   ```
2. **Geräte-ID ermitteln (persistent):**
   ```bash
   ls -l /dev/serial/by-id/
   ```
   *Beispiel:* `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A1234567-if00-port0`  
   *Vorteil:* Dieser Pfad ändert sich im Gegensatz zu `/dev/ttyUSB0` auch bei Umstecken oder Neustart nie.

---

## 2. Bedienfeld-Setup am Plotter (Schritt für Schritt)

Die Einstellungen werden am LCD-Bedienfeld vorgenommen und im gewählten Benutzersatz (**USER1** bis **USER5**) batteriegepuffert dauerhaft gespeichert.

Drücke am Bedienfeld `MENU` und wähle **`SETUP`**:

### A. Benutzersatz wählen
* `SETUP` $\to$ `User` $\to$ **`USER1`** wählen.

### B. Schnittstelle (`SETUP → Interface`)
| Parameter | Wert | Bedeutung |
|---|---|---|
| **Baud Rate** | **`19200`** | Maximale Datenrate der seriellen Schnittstelle |
| **Data Bit** | **`8`** | 8 Datenbits |
| **Parity** | **`None`** | Keine Paritätsprüfung |
| **Stop Bit** | **`1`** | 1 Stoppbit |
| **Handshake** | **`Off`** | Software-XON/XOFF am Plotter aus |
| **CTS Control** | **`On`** | Hardware-Flusskontrolle über CTS aktiv (wichtig!) |
| **DTR** | **`Pin 20`** | DTR-Signal auf Pin 20 |

### C. Befehlssatz & Auflösung (`SETUP → Command`)
| Parameter | Wert | Bedeutung |
|---|---|---|
| **Command Mode** | **`MH-GL`** (oder `HP-GL`) | HP-7585B Emulation |
| **Program Step** | **`0.025 mm`** | Auflösung 40 Schritte/mm (Default). *Spart ca. 25 % serielle Zeichen im Vergleich zu 0,010 mm bei identischer mechanischer Linienqualität.* |
| **Circle Resolution** | **`Fine`** | Glatte Kreis- und Bogeninterpolation |

> [!NOTE]
> Wenn `Program Step` auf `0.025 mm` steht, antwortet der Plotter auf `OF;` mit `40,40`. Steht er auf `0.010 mm`, antwortet er mit `100,100`. LINTO erkennt dies automatisch.

### D. Gerätespezifikationen (`SETUP → Spec`)
| Parameter | Wert | Warum dieser Wert für LINTO kritisch ist |
|---|---|---|
| **Buffer Size** | **`Small`** (1000 Zeichen) | **Extrem wichtig:** Bei `Small` reagiert der Plotter bei Pause/Abbruch am PC innerhalb von Bruchteilen einer Sekunde. Bei `Norm` (1 MB) würde er minutenlang weiterplotten! |
| **Sort** | **`Off`** | **Extrem wichtig:** Verhindert, dass die interne Firmware die optimierte Reihenfolge von LINTO (2-Opt / Traveling Salesperson) durcheinanderbringt. |
| **Hard Clip** | **`Exp`** (Expanded) | Nutzt die maximale Papierfläche mit minimalen Rändern (nur 5 mm an den Rollen). |
| **Pen Setup** | **`VS, AS, FS: Good`** | Gestattet der Software, Geschwindigkeit (`VS`), Anpressdruck (`FS`) und Beschleunigung (`AS`) pro Stift zu steuern. |

---

## 3. Papier einlegen & Rollenmechanik

Der Mutoh XP-500 besitzt optische Sensoren und verschiebbare Andruckrollen (**Pinch Rollers**). Dadurch kann **jedes beliebige Papierformat** (DIN A4 bis DIN A0 sowie beliebige Sonder- und Bannermaße) verwendet werden:

1. **Hebel anheben:** Andruckrollen-Hebel (rechts) nach oben legen, um die Rollen zu entlasten.
2. **Papier einschieben:** Blatt von vorne oder hinten zwischen Walze und Rollen einschieben, an der Anlegekante ausrichten.
3. **Rollen positionieren:** Die beiden äußeren Andruckrollen manuell genau an die linke und rechte Papierkante schieben (sie müssen auf den gerasterten grit wheels aufliegen).
4. **Hebel absenken:** Andruckhebel nach unten drücken.
5. **Initialisierung:** Der Plotter fährt das Papier vor und zurück, tastet mit den optischen Sensoren die Kanten ab und ermittelt die tatsächliche Blattgröße.

### Ränder bei `Hard Clip: Exp`
* **Vorderkante:** $25\,\text{mm}$ (Sicherheitsabstand zum Auswurf)
* **Hinterkante:** $5\,\text{mm}$
* **Linke/Rechte Kante (an den Rollen):** je $5\,\text{mm}$
* *Gesamtrand:* $X = 30\,\text{mm}$, $Y = 10\,\text{mm}$.

---

## 4. Stifte bestücken
* Das 8-fach-Stiftkarussell nimmt Faser-, Tusche- oder Kugelschreiber auf.
* Stifte ohne Schutzkappe in die Plätze 1–8 einsetzen und arretieren.
* In LINTO können den Plätzen 1–8 die passenden Farben und Parameter zugeordnet werden.

---

## 5. Verbindungstest vom PC (Terminal / Python)

Sobald der Plotter eingeschaltet, initialisiert und mit dem Linux-Rechner verbunden ist, kann die Kommunikation in wenigen Sekunden getestet werden:

```bash
python3 -c "
import serial, time

port = '/dev/ttyUSB0'  # oder /dev/serial/by-id/...
with serial.Serial(port, 19200, bytesize=8, parity='N', stopbits=1, rtscts=True, timeout=2) as s:
    time.sleep(0.5)
    s.reset_input_buffer()
    
    # Gerätekennung, Zeicheneinheit und abgetastete Blattgrenzen abfragen
    s.write(b'IN;OI;OF;OH;')
    antwort = s.read(200).decode('ascii', errors='replace')
    print('Antwort vom Plotter:\n', antwort)
"
```

### Erwartete Antwort:
```text
7585B
40,40
-15840,-11200,15840,11200   (Beispielwerte für A2 je nach Einlage)
```

* `7585B`: Der Plotter meldet sich korrekt als HP-7585B.
* `40,40`: Schrittweite $0,025\,\text{mm}$ (bei 0,010 mm stünde hier `100,100`).
* Koordinaten: Die Grenzen $X_{\min}, Y_{\min}, X_{\max}, Y_{\max}$ in Plotter-Einheiten um den zentrierten Nullpunkt `(0,0)`.

Damit ist das Gerät zu 100 % einsatzbereit für LINTO!
