# Mutoh XP-500 – Einheiten und Koordinaten

## Zeicheneinheit

| Quelle | Aussage |
|---|---|
| 📘 Appendix-2 | Software-Auflösung **0,1 / 0,05 / 0,025 / 0,0125 / 0,01 mm** pro Schritt |
| 📘 Appendix (Inquiry) | `OF` = „output 1-mm length in plotter unit“ |
| 🇯🇵 FAQ | Zeichnung halb/doppelt so groß ⇒ Einheit von Plotter und Treiber passen nicht. Einstellung: **Setup → Befehl (MH-GL) → Zeicheneinheit**. Im HP-GL-Modus fest 0,025 mm |
| 📏 M | `OF;` → `40,40` ⇒ **0,025 mm** an deinem Gerät |
| 🔧 MP | MutohPlot schreibt mit **0,01 mm** (also `OF` = 100 an jenem Gerät) |

| Einheit | Units/mm (`OF`) | Max. Koordinate A0 (±594,5 mm) |
|---|---|---|
| 0,1 mm | 10 | ±5945 |
| 0,05 mm | 20 | ±11 890 |
| **0,025 mm** | **40** | **±23 780** |
| 0,0125 mm | 80 | ±47 560 |
| 0,01 mm | 100 | ±59 450 |

**Regeln für Plotter Studio**
1. `units_per_mm` wird **beim Verbinden per `OF;` gelesen** und nie fest angenommen. Ein Profilwert dient nur als Vorgabe ohne Rückkanal (z. B. beim Export als Datei).
2. HP-GL-Dateien, die *exportiert* werden, bekommen die Einheit in den Metadaten bzw. im Dateinamen-Kommentar, damit sie nicht auf einem anders eingestellten Gerät skaliert herauskommen.
3. Empfehlung: **0,025 mm beibehalten.** Das ist HP-kompatibel (Dateien von Fremdtools passen) und liegt weit unter jeder Strichbreite. 0,1 mm würde ca. 20 % Bandbreite sparen, kann aber bei flachen Kurven mit feinen Stiften sichtbare Treppen erzeugen.
4. ⚠️ Ungeklärt: Akzeptiert die Firmware bei 0,01 mm Koordinaten > 32 767? (HP-7585B-Grenzen) → nur relevant, falls jemand die Einheit umstellt.

## Ursprung und Achsen 📏

- `(0,0)` = **Mitte des Hard-Clip-Bereichs**, nicht die Blattmitte.
- **X = Papiervorschub** (das Papier bewegt sich), **Y = Stiftwagen**.
- „Die Oberkante des Papiers liegt links“ (Blick von vorn).
- Der Hard-Clip hängt davon ab, wie das Blatt eingelegt ist (Andruckrollen bestimmen die Breite) → **`OH;` nach jedem Blattwechsel neu abfragen.**
- 🔧 MP (hardwaregetestet): `X = y_papier − H/2 (+ Fensterkorrektur)`, `Y = x_papier − W/2` → Kandidat für `insert_matrix [[0,1],[1,0]]` im Profil. Vorzeichen per Orientierungsplot bestätigen ([testplan.md](testplan.md)).
- MH-GL kennt `RO n` (Drehung 0/90/…). In der Handbuchtabelle steht „69°“, ein offensichtlicher Druckfehler für 90°. Plotter Studio dreht selbst und sendet kein `RO`.

## Hard-Clip-Fenster 📘

Ränder in mm (Appendix-2; 🔧 MP: Abb. 7.3, ±1 mm):

| Fenster | X (Vorschub) | Y (Wagen) | Σ X | Σ Y |
|---|---|---|---|---|
| Normal | 35 / 15 | 15 / 15 | 50 | 30 |
| Expanded | 25 / 5 | 5 / 5 | 30 | 10 |
| Type 1 | 25 / 5 | 11 / 11 | 30 | 22 |
| Type 3 | 25 / 10 | 10 / 10 | 35 | 20 |

## Randanalyse

Aus deinen `OH`-Werten 📏 (Units/40 = mm, Blattmaß minus plottbares Maß):

| Format | Notiz | Rohwerte `OH;` | X plottbar | Y plottbar | Σ Rand X | Σ Rand Y |
|---|---|---|---|---|---|---|
| A4 | landscape | `-3670,-5460,3670,5460` | 183,5 mm | 273,0 mm | 26,5 mm | 24,0 mm ⚠️ |
| A3 | landscape | `-5399,-8209,5399,8209` | 270,0 mm | 410,5 mm | 27,0 mm | 9,5 mm |
| A3 | portrait | `-7878,-5775,7878,5775` | 393,9 mm | 288,8 mm | 26,1 mm | 8,3 mm |
| A2 | landscape | `-11353,-8179,11353,8179` | 567,7 mm | 409,0 mm | 26,3 mm | 11,0 mm |
| A2 | portrait | `-7851,-11693,7851,11693` | 392,6 mm | 584,7 mm | 27,4 mm | 9,3 mm |

Abgleich mit dem Handbuch:
- **Y ≈ 8–11 mm** passt zu **Expanded** (10 mm ± 1 mm pro Seite). A4 mit 24 mm: Die Rollen standen vermutlich nicht an den Blattkanten.
- **X ≈ 26–27 mm**, laut Expanded wären es **30 mm**. Es fehlen sehr konstant ~3,5 mm. Mögliche Ursachen:
  - Die Blattkantenerkennung hat einen Versatz (Sensor erkennt die Kante später/früher).
  - Die Blätter sind nicht exakt DIN-maßhaltig (unwahrscheinlich bei 3,5 mm).
  - Ein anderes Fenster bzw. ein Fenster, das nicht in der Tabelle steht („Type 2“?).
- ⚠️ Widersprüche in der Notiztabelle (Q-13): Bei „A2 portrait“ sind width/height vertauscht, und „A3 portrait“ hat die lange Seite in X, „A2 portrait“ die kurze.

→ Die Aufteilung vorn/hinten ($m_{x-}$, $m_{x+}$) und der tatsächliche Fenstertyp werden per Randplot bestimmt ([testplan.md](testplan.md)).

## Blattlage aus dem Hard-Clip

$$x_{\text{Blatt}} \in [-h_x - m_{x-},\; h_x + m_{x+}], \qquad y_{\text{Blatt}} \in [-h_y - m_{y-},\; h_y + m_{y+}]$$

$h_x, h_y$ = halbe Hard-Clip-Maße in mm. $m_{x\pm}$ kommen aus dem Profil (Fenster laut Handbuch + Kalibrierkorrektur). $m_{y\pm}$ werden symmetrisch angenommen: $(\text{Blatt}_y - 2h_y)/2$.

Nebeneffekt: Format und Einlage lassen sich aus `OH` **automatisch erkennen**, indem man mit Formattabelle + Fensterrändern vergleicht und den nächsten Treffer innerhalb einer Toleranz wählt. Details: [konzept.md §4](../../konzept.md).
