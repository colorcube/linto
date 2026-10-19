# 4. Hardware-Setup, Kalibrierung & Diagnose

Hier erfährst du, wie du deinen Stiftplotter physikalisch mit dem Computer verbindest, die Schnittstellenparameter am Gerät und im Dialog *Geräte-Einstellungen* konfigurierst, die Verbindung mit dem integrierten Diagnosetool testest und den offiziellen Kalibrierplot durchführst.

---

## 1. Physischer Anschluss & Verkabelung

Klassische Plotter nutzen serielle RS-232-Schnittstellen (meist 25-polige DB-25-Buchsen oder 9-polige DB-9-Buchsen). Moderne Computer verfügen in der Regel über keine nativen COM-Ports mehr, weshalb ein USB-zu-Seriell-Adapter verwendet wird.

### Empfohlene USB-Seriell-Adapter
* **Chipsatz:** Verwende Adapter mit Original-Chipsätzen von **FTDI** (z.B. FT232R, FT2232) oder **Silicon Labs** (CP2102).
* **Vorsicht:** Billige Nachbauten ohne echten RTS/CTS-Hardware-Handshake führen bei größeren Vektordaten unweigerlich zu Pufferüberläufen und Datenverlust.

### Nullmodem-Verkabelung mit echtem Hardware-Handshake
Für eine zuverlässige Kommunikation ist ein vollbeschaltetes Nullmodem-Kabel (Cross-Over) zwingend erforderlich:

| Signal | PC-Seite (DB-9 Buchse) | Plotter-Seite (DB-25 Stecker) | Plotter-Seite (DB-9 Stecker) | Beschreibung |
|---|---|---|---|---|
| **RxD** (Empfang) | Pin 2 | Pin 2 (TxD) | Pin 3 (TxD) | Empfangsdatenleitung |
| **TxD** (Senden) | Pin 3 | Pin 3 (RxD) | Pin 2 (RxD) | Sendedatenleitung |
| **GND** (Masse) | Pin 5 | Pin 7 (GND) | Pin 5 (GND) | Signalmasse |
| **RTS** (Request to Send) | Pin 7 | Pin 5 (CTS) | Pin 8 (CTS) | PC signalisiert Empfangsbereitschaft |
| **CTS** (Clear to Send) | Pin 8 | Pin 4 (RTS) | Pin 7 (RTS) | **Plotter steuert Datenfluss (Handshake)** |
| **DTR** (Data Terminal Ready)| Pin 4 | Pin 6 (DSR) | Pin 6 (DSR) | Betriebsbereitschaft |
| **DSR** (Data Set Ready) | Pin 6 | Pin 20 (DTR) | Pin 4 (DTR) | Betriebsbereitschaft |

> **Wichtig:** Eine einfache 3-Draht-Verbindung (nur TxD, RxD, GND) ohne RTS/CTS funktioniert bei Stiftplottern nicht sicher, da der Plotter bei komplexen Kurvenfahrten den PC anhalten können muss.

### Alternative: TCP / Ethernet Device Server
Statt eines USB-Kabels kannst du auch Serial-to-Ethernet-Boxen (z.B. Moxa NPort, USR-TCP232) oder einen Raspberry Pi mit `socat` verwenden. Plotter Studio unterstützt TCP-Sockets nativ über die Portangabe `tcp://<IP-Adresse>:<Port>` (z.B. `tcp://192.168.1.150:4001`).

---

## 2. Bedienfeld- und Panel-Setup (Beispiel Mutoh XP-500)

Stelle am Bedienfeld oder den DIP-Schaltern des Plotters folgende Parameter ein:

* **Emulation:** HP-7585B oder MH-GL.
* **Baudrate:** `19200` Baud (oder `9600` Baud bei langen Kabelwegen).
* **Datenformat:** `8` Datenbits, `keine` Parität (None), `1` Stoppbit (**8N1**).
* **Handshake / Flow Control:** **Hardware (RTS/CTS)**. *XON/XOFF muss deaktiviert sein*.
* **Randmodus (Margin Profile):** **EXP** (Expanded).
* **Papiereinzug:** Nach dem Einlegen des Papiers liest der optische Sensor die Ränder automatisch ein.

---

## 3. Dialog „Geräte-Einstellungen“

Öffne über die obere Werkzeugleiste oder das Menü **Geräte → Einstellungen...** den Konfigurationsdialog, um deinen Plotter in Plotter Studio einzurichten:

![Dialog Geräte-Einstellungen](images/dialog_device_settings.png)

* **Plotter-Liste:** Zeigt alle angelegten Gerätekonfigurationen an.
* **[ Neues Gerät ]:** Legt eine neue Gerätekonfiguration an.
* **Einstellungen pro Gerät:**
  * **Anzeigename:** Frei wählbarer Name (z.B. `Mutoh XP-500 Studio` oder `Roland DXY-1150 Flachbett`).
  * **Geräteprofil:** Auswahl des Hardware-Grundmodells aus den über 25 mitgelieferten Profilen (z.B. `mutoh_xp500`, `roland_dxy`, `hpgl_generic`).
  * **Schnittstelle & Baudrate:** Serieller Port (z.B. `/dev/ttyUSB0`) oder Netzwerkadresse (`tcp://127.0.0.1:9999`) sowie Baudrate, Parität und Flusssteuerung.
  * **Randprofil:** Gewünschtes Standard-Margin-Profil des Geräts.

> [!NOTE]
> Wie du weitere Plottermodelle einbindest, eigene YAML-Geräteprofile erstellst oder Profile aus Inkcut importierst, erfährst du in **[Kapitel 5: Anbindung weiterer Plottermodelle & Geräteprofile](5-plottermodelle-und-geraeteprofile.md)**.

---

## 4. Hardware-Diagnose mit `tools/xp500_probe.py`

Plotter Studio liefert ein eigenständiges Terminal-Diagnosewerkzeug mit, mit dem du die Schnittstelle und alle Rückmeldungen auf Bit- und Byte-Ebene prüfen kannst:

```bash
# Aufruf über USB-Seriell:
python3 tools/xp500_probe.py /dev/ttyUSB0

# Aufruf mit Baudrate und detaillierten ESC-Sequenzen:
python3 tools/xp500_probe.py /dev/ttyUSB0 --baudrate 19200 --esc

# Aufruf über Netzwerk / TCP-Server:
python3 tools/xp500_probe.py tcp://127.0.0.1:9999
```

### Typische Ausgabe bei fehlerfreier Verbindung:
```
============================================================
Plotter Studio - Hardware Diagnostic Probe
Target: /dev/ttyUSB0 (19200 baud, 8N1, RTS/CTS)
============================================================
[1/4] Checking Hardware Control Lines (RS-232)...
  CTS line : True  (Plotter is ready to accept data)
  DSR line : True  (Plotter hardware present)

[2/4] Querying Plotter Identification...
  Command 'OI;' -> Response: '7585B' (HP-7585B emulation active)

[3/4] Querying Resolution & Scaling Factors...
  Command 'OF;' -> Response: '40,40' (40 Plotter-Units per mm = 0.025 mm/step)

[4/4] Querying Plottable Window (Hard-Clip)...
  Command 'OH;' -> Response: '-8200,-5340,8200,5340'
  Calculated printable area: 410.0 mm x 267.0 mm (Matches DIN A3)

Result: Plotter is ONLINE, RESPONSIVE and READY FOR PLOTTING!
```

Erscheint hier ein Timeout, überprüfe die Leitungen CTS/RTS und die Baudrate am Plotterbedienfeld.

---

## 5. Der Kalibrierplot (Genauigkeit, Ränder, Stifte & Backlash)

Im Verzeichnis `resources/` liegen vorbereitete Kalibriermuster für DIN A4 und DIN A3 bereit:
* `resources/calibration_plot_a3.svg` / `.hpgl`
* `resources/calibration_plot_a4.svg` / `.hpgl`

![Kalibrierplot Struktur](images/ui_overview_plot.png)

### Aufbau und Prüfkriterien des Testmusters:

1. **Orientierungs-Pfeile (+X / +Y) & Kantenmarkierung:**
   * An der Einzugskante ist der Pfeil `+Y` und der Schriftzug `TOP / LEADING EDGE` aufgedruckt.
   * *Prüfung:* Wurde die Schrift kopfstehend oder gespiegelt gezeichnet? Falls ja, muss im Geräteprofil `invert_x`, `invert_y` oder `rotation_deg` angepasst werden.
2. **Präzisions-Messstrecke (400 mm bei A3 / 200 mm bei A4):**
   * Eine lange durchgezogene Messlinie mit präzisen Endstrichen.
   * *Prüfung:* Miss die gezeichnete Linie mit einem hochwertigen **Stahllineal** nach.
   * Ist die Linie z.B. exakt 400,0 mm lang, arbeitet die Schrittmotorübersetzung perfekt mit 40,0 Units/mm. Bei Abweichungen kann der Faktor im Geräteprofil (`units_per_mm`) feinjustiert werden.
3. **Äußerer Begrenzungsrahmen (Hard-Clip Check):**
   * Zeichnet ein Rechteck genau an den äußersten plottbaren Grenzen des Papiers.
   * *Prüfung:* Werden alle 4 Kanten sauber gezeichnet, ohne dass der Stift auf die Gummiwalzen läuft oder der Kopf an mechanische Begrenzer schlägt?
4. **8-Stifte-Matrix:**
   * 8 beschriftete Testboxen mit Farbstreifen.
   * *Prüfung:* Funktioniert das automatische Ein- und Auswechseln aller Stifte aus dem Karussell fehlerfrei? Schließen die Stiftkappen dicht?
5. **Konzentrische Kreise & Quadrat-in-Kreis (Umkehrspiel / Backlash):**
   * Feine konzentrische Kreise und ein exakt zentriertes Quadrat.
   * *Prüfung:*
     * Treffen die Anfangs- und Endpunkte der Kreislinien exakt aufeinander?
     * Sind Kreise kreisrund oder leicht eiförmig/elliptisch?
     * Ein Versatz an den Quadranten deutet auf mechanisches Spiel (Backlash) im Riemenantrieb oder den Andruckrollen hin.
