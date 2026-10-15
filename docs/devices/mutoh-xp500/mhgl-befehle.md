# Mutoh XP-500 – MH-GL-Befehle

Quelle: 📘 Handbuch Appendix-5…10 (`mhgl-001…006.png`), Parameter wie dort angegeben. `(…)` = optional, `[…]` = optional laut Handbuch-Notation.

MH-GL ist Mutohs HP-GL-kompatible Sprache. Das Gerät meldet sich mit `OI;` → `7585B` (HP-7585B-Emulation, **HP-GL, nicht HP-GL/2**). Fehlermeldungen am Panel haben laut 🇯🇵 FAQ die Form „Befehlsfehler MHxx“.

**Relevanz für Plotter Studio:** ● wird verwendet · ○ optional/später · – nicht vorgesehen
**Status:** 📘 = nur Handbuch · ✅ = an deinem Gerät getestet

## Linien

| Befehl | Parameter | Funktion | Rel. | Status |
|---|---|---|---|---|
| `PA` | `x,y(,…)` | Absolut fahren | ● | ✅ |
| `PR` | `x,y(,…)` | Relativ fahren | ○ (Bandbreite) | 📘 |
| `PD` | `(x,y,…)` | Stift ab | ● | ✅ |
| `PU` | `(x,y,…)` | Stift auf | ● | ✅ |
| `SP` | `pen` | Stift wählen (0 = ablegen) | ● | ✅ |

## Kreise, Rechtecke, Polygone

| Befehl | Parameter | Funktion | Rel. |
|---|---|---|---|
| `AA` | `x,y,angle(,chord tol)` | Bogen, absolutes Zentrum | ○ |
| `AR` | `x,y,angle(,chord tol)` | Bogen, relatives Zentrum | ○ |
| `CI` | `radius(,chord tol)` | Kreis | ○ |
| `EA` / `ER` | `x,y` | Rechteck absolut/relativ (Umriss) | – |
| `RA` / `RR` | `x,y` | Rechteck gefüllt | – |
| `EW` / `WG` | `radius,start,sweep(,chord)` | Kreissegment Umriss/gefüllt | – |
| `PM` | `n` | Polygonmodus | – |
| `EP` / `FP` | – | Polygon umranden/füllen | – |

## Sonstige Polygon- und Achsbefehle

| Befehl | Parameter | Funktion | Rel. |
|---|---|---|---|
| `SM` | `char` | Symbolmodus | – |
| `XT` / `YT` | – | Achsenmarkierung | – |

## Zeichen/Text

| Befehl | Parameter | Funktion |
|---|---|---|
| `LB` | `(ccc) term` | Text ausgeben (Abschluss mit Terminator, nicht `;`) |
| `BL` | `(ccc) term` | Text in Puffer |
| `DT` | `term` | Terminator für `LB`, `BL`, `WD` |
| `CA` / `CS` / `SA` / `SS` | `set` | Zeichensatz alternativ/standard |
| `DS` | `slot,set` | Zeichensatz einem Slot zuweisen |
| `IV` | `slot(,left)` | Zeichensatz aufrufen |
| `CC` | `chord angle` | Sehnenwinkel für Zeichen |
| `CM` | `switch(,fallback)` | Zeichenmodus |
| `CP` | `space,line` | Cursor versetzen |
| `DI` / `DR` | `run,rise` | Schreibrichtung absolut/relativ |
| `DL` / `UC` | … | Benutzerzeichen |
| `DV` | `n` | Vertikale Schreibrichtung |
| `ES` | `space(,line)` | Zusatzabstand |
| `KB` / `KL` | `JIS` | Kanji |
| `LO` | `pos` | Textausrichtung |
| `OL` | – | Textlänge abfragen |
| `PB` | – | Puffer ausgeben |
| `SI` / `SR` | `width,height` | Zeichengröße absolut/relativ |
| `SL` | `tangent` | Neigung |

Rel.: – Plotter Studio rendert Text selbst zu Linien (Hershey/Single-Line-Fonts), damit Vorschau = Plot. `LB` wäre höchstens für Beschriftungen im Testplot interessant (○).

## Zeichnen

| Befehl | Parameter | Funktion | Rel. |
|---|---|---|---|
| `LT` | `n(,p)` sowie `LT -7,1\|2\|3,dt1,ut(,dt2)` | Linientyp, benutzerdefinierte Strichelung | – (selbst erzeugen) |
| `UF` | `gap1(,…gap20)` | Benutzerdefinierte Füllung | – |
| `FT` | `type(,spacing(,angle))` | Fülltyp | – |
| `PT` | `thickness` | Stiftdicke (für Füllungen) | – |
| `CT` | `n` | Sehnentoleranz-Modus | – |
| `TL` | `tp(,tn)` | Tick-Länge | – |

## Plottersteuerung

| Befehl | Parameter | Funktion | Rel. | Status |
|---|---|---|---|---|
| `IN` | – bzw. `IN-1` | Initialisieren (`IN-1` = Variante, Bedeutung klären) | ● | ✅ |
| `DF` | – | Defaults | ○ | 📘 |
| `VS` | `velocity(,pen)` | **Geschwindigkeit, pro Stift** | ● | 📘 |
| `FS` | `force(,pen)` | **Andruck, pro Stift** | ● | 📘 |
| `AS` | `acceleration(,pen)` | **Beschleunigung, pro Stift** | ○ | 📘 |
| `CV` | `n(,delay)` | **Kurvenglättung** (Firmware fährt Polylinien flüssiger) | ○ (testen!) | 📘 |
| `AP` | `n` | Automatische Stiftfunktionen (z. B. Stift abdecken, Auto-Pickup) | ○ | 📘 |
| `GP` | `group[,pen(,num pens(,length))]` | Stiftgruppe (vermutlich Stiftwechsel nach Strecke) | ○ | 📘 |
| `SG` | `group` | Stiftgruppe wählen | ○ | 📘 |
| `GM` | `polygon buf[,dl char buf(,0,d1(,d2))]` | Speicheraufteilung | – | 📘 |
| `NR` | – | Plotter auf „Local“ (pausiert) | ○ (Pause/Blattwechsel) | 📘 |

## Koordinaten

| Befehl | Parameter | Funktion | Rel. | Status |
|---|---|---|---|---|
| `IP` | `P1x,P1y(,P2x,P2y)` | Referenzpunkte | – (wir rechnen in Units) | ✅ (Notizen) |
| `SC` | `Xmin,Xmax,Ymin,Ymax[,type(,left,bottom)]` oder `Xmin,Xfactor,Ymin,Yfactor,type` | Benutzerskalierung | – | ✅ (Notizen) |
| `IW` | `x1,y1,x2,y2` | Clip-Fenster | ○ (Sicherheitsnetz: auf Blattgrenze setzen) | 📘 |
| `RO` | `n` | Drehung (Handbuch: „69°“ = Druckfehler für 90°) | – | 📘 |
| `OH` | – | Hard-Clip abfragen | ● | ✅ |
| `OP` | – | P1/P2 abfragen | ○ | 📘 |
| `OW` | – | Fenster abfragen | ○ | 📘 |
| `DC` / `DP` / `OD` | – | Digitalisieren | – | 📘 |

## Tastatur/Panel

| Befehl | Parameter | Funktion | Rel. |
|---|---|---|---|
| `WD` | `(ccc) term` | **Text aufs LCD schreiben** | ○ (z. B. „Stift 3: Tusche 0,3 einsetzen“) |
| `KY` | `key(,function)` | Funktionstasten F1–F4 belegen | ○ (z. B. Taste = „weiter“) |
| `GC` | `count` | Zähler | – |
| `OG` / `OK` | – | Zähler/Taste abfragen | ○ (zusammen mit `KY`) |

## Abfragen

| Befehl | Funktion | Rel. | Status / Antwort 📏 |
|---|---|---|---|
| `OI` | Identifikation | ● | ✅ `7585B` |
| `OF` | Units pro mm | ● | ✅ `40,40` |
| `OT` | „Stocker type and whether pen installed“ | ● | ✅ `1,1` (Typ 1, Stift eingesetzt? → [testplan.md](testplan.md)) |
| `OA` | Aktuelle Position | ● (Sync/Fortschritt) | gesendet, Antwort nicht notiert |
| `OS` | Statusbyte | ● | 📘 |
| `OE` | Fehlercode | ● | 📘 |
| `OC` | Position + Stiftstatus | ○ | 📘 |
| `OO` | Optionen | ○ | 📘 |
| `IM` | `E-mask[,S-mask(,P-mask)]` Fehlermasken | ○ | 📘 |

## Minimaler Befehlssatz für Plotter Studio (Dialekt `mhgl-7585b`)

```text
Verbindungsaufbau:  ESC.R  IN;  OI;  OF;  OH;  OT;
Pro Stift:          SPn;  VSv;  FSf;   (AS optional)
Zeichnen:           PU x,y;  PD x,y,x,y,…;   (PR optional)
Synchronisieren:    OA;   (Antwort abwarten = alles davor ausgeführt)
Ende:               PU;  SP0;
```

`VS`/`FS` werden mit Stiftparameter gesendet (`VS v,pen`), wenn die Firmware das sauber umsetzt (Test), sonst nach jedem `SP` ohne Stiftparameter.
