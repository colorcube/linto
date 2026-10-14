# Mutoh XP-500 – Technische Daten

Quelle: 📘 Handbuch Appendix-2…4 (`specifications-001…003.png`), sofern nicht anders markiert.

## Mechanik und Zeichnen

| Merkmal | Wert | Bedeutung für Plotter Studio |
|---|---|---|
| Max. Zeichengeschwindigkeit | **1272 mm/s** diagonal, **900 mm/s** entlang einer Achse | Obergrenze für `VS` im Profil. Für Tusche/Bleistift ist praktisch deutlich weniger sinnvoll (Werkzeugbibliothek) |
| Max. Beschleunigung | **4,2 G** diagonal, **3 G** pro Achse | `AS` (Beschleunigung, pro Stift) existiert, siehe [mhgl-befehle.md](mhgl-befehle.md) |
| Mechanische Auflösung | 0,005 mm/Schritt | Feiner als jede Software-Einheit |
| **Software-Auflösung** | **0,1 / 0,05 / 0,025 / 0,0125 / 0,01 mm/Schritt** | = die einstellbare MH-GL-„Zeicheneinheit“. `OF;` meldet Units/mm (40 ⇔ 0,025 mm). Siehe [einheiten-und-koordinaten.md](einheiten-und-koordinaten.md) |
| Antrieb XY | DC-Motoren, Software-Servo | – |
| Wiederholgenauigkeit | ±0,1 mm | Mehrfachdurchgänge (gleiche Linie zweimal) liegen innerhalb ±0,1 mm |
| Streckengenauigkeit | ±0,1 % der Strecke oder ±0,25 mm (der größere Wert), auf doppelt mattierter Polyesterfolie (#300) | Auf A0 (1189 mm) bis ±1,2 mm → Kalibrierung „Skalierung pro Achse“ kann sinnvoll sein (Idee) |
| Stift auf/ab | Tauchspule, Software-Servo, **80 Zyklen/s** (je 1× auf + 1× ab) | Pen-up-Kosten im Optimierer sind klein, aber nicht null |
| **Andruck** | **15–450 g**, manuell oder automatisch | `FS` (pro Stift) → Werkzeugbibliothek |
| Stifttypen | Tuschefüller, Einweg-Tusche, Keramikspitze, Faserstift (flüssig / ölbasiert), Kugelschreiber (wasser-/ölbasiert), **Bleistift 0,2 / 0,3 / 0,4 / 0,5 / 0,7 mm** (0,7 mm benötigt Minen B oder härter) | Grundlage für Werkzeug-Presets |
| Stiftmagazin (Stocker) | **bis 8 Stifte/Bleistifte** | passt zu „max. 8 Stifte pro Plot“ |
| Medien | Transparentpapier (Tracing bond), Hochglanzpapier, Polyesterfolie, Normalpapier | – |
| Bedienfeld | LCD 16 Zeichen × 4 Zeilen, 8 LEDs, 22 Tasten | – |
| Standard-Befehlsmodus | **MH-GL (HP-GL)** | siehe [mhgl-befehle.md](mhgl-befehle.md) |

## Hard-Clip-Bereich (Ränder in mm)

| Fenster | X (Vorschubrichtung) | Y (Wagenrichtung) | Summe X | Summe Y |
|---|---|---|---|---|
| Normal | 35, 15 | 15, 15 | 50 | 30 |
| Expanded | 25, 5 | 5, 5 | 30 | 10 |
| Type 1 | 25, 5 | 11, 11 | 30 | 22 |
| Type 3 | 25, 10 | 10, 10 | 35 | 20 |

- Die X-Ränder sind **asymmetrisch** (25 bzw. 35 mm an einer Kante, wahrscheinlich der Vorderkante). Welche Kante welche ist, ist noch offen.
- **„Type 2“ fehlt** in der Tabelle (Druckfehler oder z. B. ein Rollenmodus?) → Kapitel 7 prüfen.
- MutohPlot gibt zusätzlich ±1 mm Toleranz an (🔧 MP, Handbuch Abb. 7.3).
- Abgleich mit deinen Messungen: [einheiten-und-koordinaten.md](einheiten-und-koordinaten.md#randanalyse).

## Elektrik, Umgebung, Maße

| Merkmal | Wert |
|---|---|
| Leistungsaufnahme | 120 VA |
| Netzspannung | 110–120 V AC / 220–240 V AC, 50/60 Hz |
| Betrieb | 5–40 °C, 35–75 % rF (nicht kondensierend) |
| Empfohlen | 16–32 °C, 50–65 % rF |
| Max. Änderungsrate | 2 °C/h, 5 % rF/h |
| Lagerung | 0–50 °C, 10–90 % rF |

| Maß | XP-510 | XP-511 |
|---|---|---|
| Höhe | 1279 mm | 1279 mm |
| Breite | 1446 mm | 1159 mm |
| Tiefe | 604 mm | 604 mm |
| Gewicht gesamt | 55 kg | 46 kg |
| Paket Plotter / Ständer | 45 kg / 20 kg | 34 kg / 17 kg |

> [!NOTE]
> Die Modellnummern sind im Scan handschriftlich überschrieben (an der dritten Stelle steht eine „1“ oder „2“). Das breitere Modell ist vermutlich die A0-Variante. Welches Modell du hast, steht auf dem Typenschild.

## Optionen

Centronics-, GP-IB- und RS-422A-Schnittstelle (optional). RS-232C ist optional, gehört aber zur Standardausstattung. Rollenhalter (optional).

## Schnittstelle (Kurzfassung)

RS-232C, 300–19200 Baud + EXT, ASCII, asynchron, vollduplex, 7/8 Datenbits, 1/2 Stoppbits, Parität gerade/ungerade/keine. **Empfangspuffer 1 MB** (laut MutohPlot am Panel auch auf 1000 Zeichen umstellbar). Details: [schnittstelle.md](schnittstelle.md).
