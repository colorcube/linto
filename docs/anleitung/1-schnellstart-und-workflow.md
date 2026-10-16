# 1. Schnellstart & Typischer Workflow

Dieser Leitfaden führt Sie Schritt für Schritt von einer vorhandenen Vektordatei (SVG) bis zur fertigen Stiftzeichnung auf Papier.

> **Tipp: Sie können Plotter Studio sofort ohne echte Hardware ausprobieren!**  
> Plotter Studio enthält einen integrierten virtuellen Software-Plotter (`VirtualPlotter`), der die serielle Schnittstelle und Firmware-Befehle vollständig über das lokale Netzwerk emuliert.

---

## Einstieg: Mit oder ohne Hardware?

### Variante A: Mit angeschlossenem Plotter
1. Verbinden Sie Ihren Plotter per seriellem Nullmodemkabel (RS-232 mit RTS/CTS) oder USB-Seriell-Adapter mit dem PC.
2. Schalten Sie den Plotter ein und spannen Sie ein Blatt Papier ein.
3. Wählen Sie oben Ihr Gerätemodell aus (über 25 Profile für Mutoh, Roland, Graphtec, US Cutter, Secabo etc. sind bereits hinterlegt).
4. Ausführliche Details zur Verkabelung finden Sie in [Kapitel 4: Hardware-Setup & Diagnose](4-hardware-setup-und-test.md).

### Variante B: Schneller Test mit dem Software-Simulator
Wenn Sie noch keine Hardware aufgebaut haben:
1. Öffnen Sie ein Terminal und starten Sie den integrierten Emulator (z. B. mit realistischer Zeichenzeit-Simulation):
   ```bash
   python3 -m plotter_studio.emulator --tcp 9999 --realtime
   ```
2. Wählen Sie in der oberen Leiste von Plotter Studio als Gerät **Mutoh XP-500 Simulator (TCP)** aus.
3. **Flusssteuerung (Handshake):** Da virtuelle Pseudoterminals (PTY) und TCP-Sockets keine physikalischen Hardware-Pins (RTS/CTS) besitzen, verwendet der Emulator **Software-Handshake (`XON / XOFF`)**. Das Profil *Mutoh XP-500 Simulator (TCP)* ist bereits ab Werk darauf eingestellt. Falls Sie ein eigenes Profil für den Emulator anlegen (z. B. für `./virtual_plotter`), stellen Sie unter *Plotter-Geräte konfigurieren* die Flusssteuerung stets auf **Software (XON / XOFF)**.

---

## Der 5-Schritte-Workflow

```
[ 1. Blatt wählen ] -> [ 2. SVG importieren & skalieren ] -> [ 3. Stifte prüfen ] -> [ 4. Simulieren ] -> [ 5. Plotten ]
```

---

### Schritt 1: Blattgröße & Randprofil festlegen

Klicken Sie in der oberen Leiste auf **[ Seiteneinrichtung... ]**:

1. **Format wählen:** Wählen Sie z.B. **DIN A3** und **Querformat (Landscape)**.
2. **Randprofil:** Belassen Sie die Voreinstellung auf **EXP** (Expanded – maximale Zeichenfläche).
3. **Live-Abfrage (optional):** Ist ein physischer Plotter verbunden, klicken Sie auf **[ Plotter abfragen ]**. Plotter Studio fragt über den Befehl `OH;` die exakten Abmessungen des eingespannten Papiers direkt von den optischen Sensoren der Hardware ab.
4. Bestätigen Sie mit **OK**. Das Canvas zeigt nun das Papierblatt mit dem rot gestrichelten *Hard-Clip-Rahmen* an.

*(Ausführliche Details: [Kapitel 2: Layout & Seiteneinrichtung](2-layout-und-objektverwaltung.md#2-blatt--seiteneinrichtung))*

---

### Schritt 2: Vektorgrafik importieren und ausrichten

1. Ziehen Sie eine beliebige `.svg`-Datei per **Drag & Drop** aus Ihrem Dateimanager direkt in das Canvas (oder drücken Sie `Strg+O`).
2. Das Dokument wird geladen. Beim Import analysiert Plotter Studio alle Strichfarben und teilt sie automatisch den Stiften 1 bis 8 zu.
3. Wechseln Sie in das rechte Dock **Transformation**:
   * Klicken Sie auf **[ Auf Blatt einpassen ]**, um die Grafik maximal vergrößert auf dem Blatt zu platzieren.
   * Oder klicken Sie auf **[ Auf Blatt zentrieren ]**, um das Motiv exakt in der Mitte auszurichten.
   * Mit den Schnelltasten **[ 50 % ]**, **[ 100 % ]** und **[ 200 % ]** oder den numerischen Feldern können Sie die Größe millimetergenau anpassen.
   * Das aktivierte Schloss-Symbol sorgt dafür, dass das Seitenverhältnis beim Skalieren proportional erhalten bleibt.

*(Ausführliche Details: [Kapitel 2: Transformation & Objektverwaltung](2-layout-und-objektverwaltung.md#5-dock-transformation))*

---

### Schritt 3: Stifte kontrollieren

1. Überprüfen Sie in der unteren Stiftleiste oder im Dock **Stifte & Farben**, welche Farben welchen Werkzeugen (Stift 1 bis 8) zugewiesen wurden.
2. Möchten Sie einen Pfad mit einem anderen Stift zeichnen:
   * Wählen Sie das Objekt im Canvas oder im Dock **Objekte & Ebenen** aus.
   * Weisen Sie ihm per Rechtsklick oder über das Stift-Dock die gewünschte Stiftnummer zu.

*(Ausführliche Details: [Kapitel 2: Stiftpalette](2-layout-und-objektverwaltung.md#6-stiftpalette--farbzuweisung))*

---

### Schritt 4: In den Ausgabe-Modus wechseln & simulieren

Klicken Sie oben auf den Reiter **Ausgabe / Plotten**:

1. **Pre-Flight-Statistiken ablesen:**
   * Im Dock **Ausgabe** sehen Sie sofort:
     * Wie viele Meter der Stift tatsächlich auf dem Papier zeichnet (`Pen Down`).
     * Wie viele Meter Leerfahrten in der Luft (`Pen Up`) zurückgelegt werden.
     * Wie viel Zeit und Leerweg durch die automatische **2-Opt-Pfadoptimierung** eingespart wurden (meist **40 % bis 70 %**).
2. **Simulation mit dem Scrubber:**
   * Unter dem Canvas befindet sich die Simulationsleiste.
   * Klicken Sie auf **[ Play ]** oder ziehen Sie den **Schieberegler**:
     * Türkis/Cyan gestrichelte Linien zeigen alle Eilgang-Fahrten in der Luft.
     * Gelbe Markierungen zeigen jeden Punkt, an dem der Stift aufgesetzt oder angehoben wird.
     * Das Fadenkreuz (Toolhead-Cursor) wandert genau so über das Blatt, wie es der echte Plotterkopf tun wird.
3. **Selektives Plotten (optional):**
   * Besitzen Sie nur einen Stifthalter oder möchten Sie schichtweise plotten? Deaktivieren Sie in der Stiftliste einfach die Häkchen bei den Stiften, die im aktuellen Durchgang nicht gezeichnet werden sollen.

*(Ausführliche Details: [Kapitel 3: Ausgabe-Modus & Simulation](3-ausgabe-simulation-export.md))*

---

### Schritt 5: Plot an das Gerät senden oder exportieren

1. **Hardware prüfen:**
   * Klicken Sie im Dock *Ausgabe* auf **[ Plotter prüfen (Inquiry) ]**.
   * Nach erfolgreicher Antwort leuchtet das Banner grün auf:  
     `7585B (A3, 40 U/mm) • Hard-Clip: 390x287 mm`.
2. **Plot starten:**
   * Klicken Sie auf **[ Plot senden ]**.
   * Die Übertragung startet im Hintergrund. Der Fortschrittsbalken und der Toolhead-Cursor im Canvas zeigen den aktuellen Status in Echtzeit an.
   * **[ Pause ]:** Hält die Übertragung an (z.B. um Tinte zu prüfen).
   * **[ Abbrechen ]:** Löst den Notfall-Rückzug aus: Der Plotter stoppt sofort, hebt den Stift an (`PU;`) und parkt ihn sicher im Halter (`SP0;`).
3. **Datei-Export (Alternative):**
   * Klicken Sie auf **[ Plotdatei (.hpgl) exportieren... ]**, wenn Sie die fertige, optimierte Maschinendatei für eine spätere Ausführung speichern möchten.

*(Ausführliche Details: [Kapitel 3: Live-Plotten & Export](3-ausgabe-simulation-export.md#5-live-plotten-auf-der-hardware))*

---

## Nächste Schritte

* Ausführliche Erklärungen zu allen Layout- und Zeichenwerkzeugen:  
  -> **[Kapitel 2: Layout-Modus & Objektverwaltung](2-layout-und-objektverwaltung.md)**
* Alle Einstellungen zur Pfadoptimierung und Scrubber-Simulation:  
  -> **[Kapitel 3: Ausgabe-Modus, Simulation & Export](3-ausgabe-simulation-export.md)**
* RS-232 Verkabelung, Hardware-Diagnosetool und der Kalibrierplot:  
  -> **[Kapitel 4: Hardware-Setup, Kalibrierung & Diagnose](4-hardware-setup-und-test.md)**
* Mathematische Hintergründe, Slicer-Algorithmen und Multi-Plotter-Treiber:  
  -> **[Kapitel 5: Hintergrund: Konzepte, Algorithmen & Architektur (Deep-Dive)](5-konzepte-und-architektur.md)**
