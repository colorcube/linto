Hier sind 10 priorisierte User Stories für **LINTO**, formuliert nach dem Standardformat *(Als … möchte ich … damit …)* inklusive konkreter Akzeptanzkriterien.

---

### Epic 1: Canvas & Layout (Säule 2)

#### US-01: Maßhaltige Arbeitsfläche, Papiermaße & Randanzeige

* **Als** Plotter-Anwender
* **möchte ich** das Papierformat manuell frei einstellen oder per Knopfdruck vom Gerät einlesen können,
* **damit** ich den physisch nutzbaren Zeichenbereich maßhaltig vor Augen habe (unabhängig davon, ob der Plotter Sensoren besitzt).
* **Akzeptanzkriterien:**
* Dropdown für Standard-Formate (DIN A4–A0, Letter) sowie Eingabefelder für beliebige Maße in mm ($W \times H$).
* Schaltfläche *„Papiergröße vom Gerät holen“* (ruft `OH;` ab und passt das Canvas an).
* Das Canvas zeigt das Blatt und eine gestrichelte Begrenzungslinie für den unplottbaren Rand (Hard-Clip).
* Zeichnungen dürfen aus dem Papier herausragen: Überstehende Pfade werden deutlich optisch markiert (z. B. rot schraffiert), im Pre-Flight gewarnt und beim Plotten wahlweise per Software sauber am Rand beschnitten oder unbeschnitten ausgegeben.



#### US-02: Schnellausrichtung, prozentuale Platzierung & Skalierung

* **Als** Zeichner und Konstrukteur
* **möchte ich** ein Motiv zentrieren, prozentual ausrichten, auf Originalmaße (1:1) zurücksetzen oder passgenau skalieren,
* **damit** sowohl künstlerische Grafiken als auch maßstabsgetreue technische Zeichnungen ohne Rechnerei exakt auf das Papier passen.
* **Akzeptanzkriterien:**
* **Schnellausrichtung:** Schaltflächen für *Horizontal zentrieren*, *Vertikal zentrieren* sowie Eingabe relativer Prozent-Positionen (z. B. $50\%, 50\%$ = mittig).
* **Originalgröße (1:1):** Ein Klick setzt das Motiv exakt auf die in der SVG-Datei hinterlegten Millimetermaße zurück (für CAD- und Architekturpläne).
* **Einpassen (Fit to Page):** Skaliert das Motiv proportional auf das Blatt, mit konfigurierbarem Rand wahlweise in mm (z. B. $20\text{ mm}$) oder in Prozent (z. B. $5\%$).
* **Skalier-Werkzeuge:** Schaltflächen für relatives Skalieren ($\pm x\,\%$) sowie numerische Eingabefelder für Ziel-Breite/Höhe in mm (mit Koppelung des Seitenverhältnisses).



---

### Epic 2: Vektoreditor & Stiftmanagement (Säule 1)

#### US-03: Stift-Management & WYSIWYG-Darstellung

* **Als** Anwender mit einem Mehrstift-Plotter
* **möchte ich** Stiften individuelle Farben und reale Strichstärken (in mm) sowie Plotter-Parameter zuweisen,
* **damit** ich am Bildschirm eine maßhaltige Vorschau erhalte (WYSIWYG) und Linienverläufe nicht zu Tintentümpeln verschmieren.
* **Akzeptanzkriterien:**
* Ein Stift-Panel listet Stift 1 bis 8 mit: UI-Anzeigefarbe, physischer Strichstärke (`width_mm`), Geschwindigkeit (`VS`) und Anpressdruck (`FS`).
* Das Canvas rendert Pfade mit der echten Strichbreite in mm.
* Ausgewählte Pfade oder Gruppen können per Klick oder Tastenkürzel (`1`–`8`) direkt einem anderen Stift zugewiesen werden.
* Stifte können ein-/ausgeblendet oder vom Plot ausgeschlossen werden.



#### US-04: SVG-Import, Farbreduktion & flexibles Remapping

* **Als** Benutzer
* **möchte ich** externe SVG-Dateien importieren, deren Farben/Ebenen automatisch auf maximal 8 Stifte verteilt werden und das Mapping jederzeit nachträglich anpassen können,
* **damit** ich mehrfarbige Grafiken auch mit weniger Stiften (oder monochrom mit nur einem Stift) plotten kann, ohne die Quelldatei neu zu bearbeiten.
* **Akzeptanzkriterien:**
* SVG-Import erkennt Inkscape-Ebenen (`inkscape:groupmode="layer"`) und distinkte Konturfarben (`stroke`), Füllungen werden ignoriert.
* Bei mehr als 8 Farben fasst ein automatischer Clustering-Algorithmus (Farbreduktion) ähnliche Farbtöne zusammen.
* Das Mapping kann jederzeit im Stift-Panel geändert werden (z. B. „Alle Farben auf Stift 1 zusammenfassen“ oder Stift 3 $\to$ Stift 1 umleiten).
* Gruppierte SVG-Elemente bleiben auf dem Canvas als zusammenhängende Gruppe verschiebbar.



#### US-05: Single-Line-Schriften (Hershey Fonts)

* **Als** Plotter-Nutzer
* **möchte ich** Text eingeben können, der als echte Einzellinien-Schrift gerendert wird,
* **damit** der Plotter Buchstaben als saubere Striche zeichnet statt als doppelt umrandete Konturen normaler TTF-Schriften.
* **Akzeptanzkriterien:**
* Textwerkzeug mit Auswahl klassischer Hershey-Fonts (z. B. Sans-Serif, Script).
* Schriftgröße in Millimetern einstellbar.
* Der Text wird direkt als editierbare Vektorkette auf dem aktiven Stift-Layer platziert.



---

### Epic 3: Geometrie & Pfadoptimierung (Plot-Engine)

#### US-06: Kontrollierte Bézier-Diskretisierung (Flattening)

* **Als** Anwender
* **möchte ich** die Sehnen-Toleranz für die Umwandlung von Kurven in Geraden über einen Regler justieren können,
* **damit** Kurven auf dem Plotter glatt aussehen, ohne den internen Puffer mit Millionen unnötiger Punkte zu überlasten.
* **Akzeptanzkriterien:**
* Einstellbare Toleranz (Default: $0,05\text{ mm}$, Bereich: $0,01$ bis $0,5\text{ mm}$).
* Live-Vorschau der resultierenden Liniensegmente und Punktanzahl im Pre-Flight-Dialog.



#### US-07: Wegoptimierung und bidirektionale Richtungsumkehr

* **Als** Plotter-Operator
* **möchte ich**, dass die Software unzusammenhängende Pfade sortiert und ungerichtete Linien bei Bedarf umdreht,
* **damit** Leerfahrten mit angehobenem Stift minimiert werden und der Plot signifikant schneller fertig ist.
* **Akzeptanzkriterien:**
* Der Optimierer minimiert die Distanz zwischen aufeinanderfolgenden Pfaden (Greedy / TSP-Ansatz).
* Pfade werden von $A \to B$ oder $B \to A$ gezeichnet, je nachdem, was näher am aktuellen Stiftort liegt.
* Anzeige der eingesparten Leerweg-Strecke (z. B. „Leerweg reduziert um 38 %“).



---

### Epic 4: Hardware, Pre-Flight & Kommunikation (Säule 3)

#### US-08: Pre-Flight-Vorschau mit Leerfahrten und Zeitschätzung

* **Als** Benutzer
* **möchte ich** vor dem Senden an das Gerät eine exakte Plot-Vorschau inklusive aller Stifthübe sehen,
* **damit** ich Fehler erkenne, bevor teures Papier oder feine Tuschestifte beschädigt werden.
* **Akzeptanzkriterien:**
* Visuelle Darstellung: Gezeichnete Linien in Layer-Farbe, Leerfahrten (`PU`) als rote gestrichelte Linien.
* Statistische Auswertung: Gezeichnete Gesamtlänge (m), Leerweg (m), Anzahl Stiftwechsel und geschätzte Gesamtdauer.



#### US-09: Asynchrone Bogenvermessung (`OH;`) und beliebige Formate

* **Als** Besitzer eines Mutoh XP-500 (oder ähnlichen Plotters)
* **möchte ich** das physisch eingelegte Papier (Standard-DIN oder beliebiges Format, begrenzt durch die manuell gesetzten Andruckrollen) über das Gerät abtasten lassen,
* **damit** das Canvas exakt auf die real gemessenen Blattmaße und den geräteeigenen Nullpunkt angepasst wird.
* **Akzeptanzkriterien:**
* Button „Bogen am Gerät vermessen“ löst das Senden von `OH;` aus.
* Nicht-blockierender Vorgang: Die UI bleibt bedienbar, zeigt einen Lade-Status und bricht nach einem konfigurierbaren Timeout (z. B. 10 s) sauber ab, falls keine Antwort kommt.
* Bei erfolgreicher Rückmeldung passen sich Canvas-Größe und plottbarer Arbeitsbereich automatisch an (auch bei krummen / benutzerdefinierten Blattmaßen).



#### US-10: Stabiles serielles Streaming mit Hardware-Handshake

* **Als** Anwender
* **möchte ich** den Plot-Befehlsstrom über RS-232 / USB-Serial sicher an den Plotter senden können,
* **damit** bei Geräten mit kleinem 1-KB-Puffer kein Pufferüberlauf und keine Fehlzeichnungen entstehen.
* **Akzeptanzkriterien:**
* Übertragung läuft in einem separaten Hintergrund-Thread (`QThread`).
* Daten werden in gedrosselten Chunks (64–128 Bytes) unter Berücksichtigung von Hardware-Flow-Control (CTS/RTS) gesendet.
* Die UI bietet Bedienelemente für: *Pause*, *Fortsetzen* und *Not-Aus / Abbrechen* (sendet sofort `PU; SP0;`).
* Live-Fortschrittsbalken mit Angabe der verbleibenden Zeit.
