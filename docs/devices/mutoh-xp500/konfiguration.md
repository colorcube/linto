# Mutoh XP-500 – Bedienfeld-Konfiguration (Kapitel 7)

Quelle: 📘 *MUTOH XP-500 Series User Guide*, Kapitel 7 „Configuring the Plotter“, Seiten 7-1…7-31 (`configure-001…031.png`).

---

## 1. Übersicht & Menühierarchie

Die Konfiguration erfolgt im Ruhezustand (`STANDBY`) über das Bedienfeld (LCD 16 Zeichen × 4 Zeilen, Funktionstasten F1–F4, Menü-Tasten ▲/▼, ENTER, EXIT, CE).

```text
STANDBY 1
├── F1: RESET
├── F2: USER ─────► Auswahl des aktiven Parametersatzes: User 1 bis User 4
├── F3: CLEAR
└── F4: SETUP
    ├── F1: Online ───► Schnittstellen-Parameter je Port (Port 1 / Port 2)
    │                  Baud, Data, Parity, Stop Bit, Protocol, DTR Pin, CTS Control, RTS Pin
    │                  Vordefiniert: Default 1…5 oder User Def
    ├── F2: Spec ─────► Umgebungsparameter (Environment Settings)
    │                  Hard Clip, Sort, Buzzer, Smoothing, Buffer Size, Next Mode
    ├── F3: Command ──► Befehlsmodus & Emulation
    │                  MH-GL (Emulation, Program Step, VS/AS/FS, IN Command)
    └── F4: Option ───► Optionen (Zusatzkarten)

STANDBY 5
├── F1: WIDE-L ───► Wide-Line-Modus (Dicke je Stift 0.20…1.00 mm für MH-GL/2)
└── F3: TIME OUT ─► Schnittstellen-Umschaltzeit (Off, 10s, 30s, 1m, 3m, 5m, 10m, 30m)
```

Einstellungen werden im EEPROM gespeichert und bleiben auch beim Ausschalten erhalten (`Page 7-23`).

---

## 2. Parameter im Detail

### 2.1 Online-Parameter (Schnittstelle, S. 7-4…7-12)

Der Plotter besitzt zwei Schnittstellen-Steckplätze (Port 1, Port 2), die modular bestückt sein können (RS232, RS422, GP-IB, Centronics). Der aktive Port wird automatisch erkannt, sobald Daten anliegen.

#### Vordefinierte Profile für RS-232C / RS-422A (Tabelle 7.1, S. 7-7)

| Parameter | Default 1 | Default 2 | Default 3 | Default 4 | Default 5 | User Def (einstellbar) |
|---|---|---|---|---|---|---|
| **Baud Rate** | 9600 | 9600 | 9600 | 9600 | 9600 | 19200, 9600, 4800, 2400, 1200, 600, 300, Ext |
| **Data Bits** | 7 | 8 | 7 | 8 | 8 | 7, 8 |
| **Parity** | Even | None | Even | None | Even | None, Odd, Even |
| **Stop Bit** | 1 | 1 | 1 | 1 | 2 | 1, 2 |
| **Protocol** | Off | Off | Xon | Xon | Off | Off, Xon-Xoff, ACK/ENQ |
| **DTR Pin** | 20 | 20 | On | On | 20 | On-Off, 20, 18 |
| **CTS Control** | Off | Off | Off | Off | Off | **Off, On** |
| **RTS Pin** | On | On | On | On | On | On, Off, RTS |

> [!NOTE]
> Deine funktionierende Einstellung (`19200, 8, None, 1, Protocol Off, DTR 20, CTS Control On, RTS Pin RTS`) entspricht exakt einem **`User Def`**-Satz! In den Werkseinstellungen (Default 1–5) ist CTS Control immer *Off* und die Baudrate 9600.

---

### 2.2 Spec / Environment Settings (Umgebung, S. 7-14…7-18)

| Parameter | Werte | Bedeutung |
|---|---|---|
| **Hard Clip** | **Norm, Exp, Type 1, Type 3** | Bestimmt die physikalischen Ränder (siehe Abbildung 7.3 unten) |
| **Sort** | **Off, Pen, All** | **Firmware-Vektorsortierung:**<br>• `Off`: Zeichnet strikt in der Reihenfolge, wie empfangen.<br>• `Pen`: Sortiert nach Stiftnummer zur Minimierung von Stiftwechseln.<br>• `All`: Sortiert nach Stiftnummer **und** optimiert die Kopf-Leerwege! |
| **Buzzer** | Off, Error, Key, All | Signalton-Verhalten |
| **Smoothing** | **Off, 5°, 10°, 15°, 20°, 25°, 30°** | **Kurvenglättung:** Wenn der Winkel zwischen zwei Linien kleiner als der Schwellenwert ist, behält der Kopf hohes Tempo bei und rundet die Ecke sanft aus. Bei größerem Winkel bremst er ab und zieht eine scharfe Ecke. |
| **Buffer Size** | **Norm, Small** | **Empfangspuffergröße:**<br>• `Norm`: **1 MByte** (1.000.000 Bytes)<br>• `Small`: **1 KByte** (1.000 Bytes) |
| **Next Mode** | REMOTE, LOCAL | Status nach Papierinitialisierung oder Reset |

---

### 2.3 Hard-Clip-Fenster & Ränder (Abbildung 7.3, S. 7-15)

```text
                  A (oben / Vorschubrichtung)
              ▲ ┌─────────────────────────┐
              │ │         • P1            │
              │ │   ┌─► Y                 │
Direction of  │ │   │                     │
media         │ │ C │ X             D     │
movement      │ │   ▼                     │
              │ │                   • P2  │
              │ └─────────────────────────┘
                  B (unten / Hinterkante)
```

*Achsen laut Abbildung 7.3:*
- **X** zeigt nach unten (entgegen der Papierauswurf-Richtung).
- **Y** zeigt nach rechts (Wagenrichtung).
- P1 und P2 liegen standardmäßig **15 mm** innerhalb des Hard-Clip-Bereichs.

#### Randmaße in mm (Tabelle Fig. 7.3)

| Fenster | A (Vorderkante) | B (Hinterkante) | C (links / Rollen) | D (rechts / Rollen) | Summe X | Summe Y |
|---|---|---|---|---|---|---|
| **Norm** | 35 ± 1 | 15 ± 1 | 15 ± 1 | 15 ± 1 | 50 mm | 30 mm |
| **Exp** | 25 ± 1 | 5 ± 1 | 5 ± 1 | 5 ± 1 | 30 mm | 10 mm |
| **Type 1** | 25 ± 1 | 5 ± 1 | 11 ± 1 | 11 ± 1 | 30 mm | 22 mm |
| **Type 3** | 25 ± 1 | 10 ± 1 | 10 ± 1 | 10 ± 1 | 35 mm | 20 mm |

> [!IMPORTANT]
> **Beliebige Blattgrößen & Rollenpositionierung:**
> Die Seitenränder **C** und **D** werden durch die **manuell verschiebbaren Andruckrollen** definiert. Der Plotter tastet die Rollen und die Papierkanten optisch/mechanisch ab. Dadurch ist **jedes beliebige Papierformat** nutzbar!
> Bei `Exp` beträgt der Rand zu den Andruckrollen links und rechts lediglich 5 mm.

---

### 2.4 Command Mode / MH-GL (S. 7-19…7-22)

Unter `SETUP → Command → MH-GL` befinden sich die wesentlichen Spracheinstellungen:

| Parameter | Werte | Bedeutung für Software |
|---|---|---|
| **Emulation** | **Off, F-900, HP759X, HP758X, MH-GL2** | Emulationsmodus. Bei dir steht er auf `HP758X` (weshalb `OI;` mit `7585B` antwortet!). |
| **Program Step** | **0.025mm, 0.010mm** | **Die Zeicheneinheit!**<br>• `0.025mm`: 40 Units/mm (`OF;` meldet `40,40`). Klassischer HP-GL-Standard.<br>• `0.010mm`: 100 Units/mm (`OF;` meldet `100,100`). Das erklärt, warum MutohPlot mit 0,01 mm rechnete! |
| **VS, AS, FS** | **Good, Void** | • `Good`: Host-Befehle für Speed (`VS`), Beschleunigung (`AS`) und Andruck (`FS`) werden akzeptiert.<br>• `Void`: Werden ignoriert (Bedienfeldwerte bleiben starr). |
| **IN Command** | **Norm, Limit** | Verhalten beim `IN;`-Initialisierungsbefehl (setzt Fenster zurück oder behält Grenzen). |

---

### 2.5 User Parameter (S. 7-23…7-25)

Es können bis zu 4 Benutzer-Profile (**User 1 bis User 4**) gespeichert werden. Im Standby-Bildschirm lässt sich mit der Taste `USER` und `1…4` sekundenschnell zwischen verschiedenen Vorkonfigurationen (z. B. User 1 = LINTO 19200 8N1 CTS 0.025mm Buffer Small; User 2 = Altes CAD-System 9600 XON) wechseln.

---

### 2.6 Wide Line & Time Out (S. 7-26…7-31)

- **Wide Line:** Strichstärkenverarbeitung für MH-GL/2 (Dicken von 0,20 bis 1,00 mm pro Stift zuweisbar). Für LINTO in Phase 1 irrelevant, da wir Pfade selbst mit Stiftbreiten und Füllmustern zerlegen.
- **Time Out:** Wenn zwei Rechner an Port 1 und Port 2 hängen, schaltet der Plotter nach einer Inaktivität von z. B. 30 Sekunden wieder frei für den anderen Port.

---

## 3. Zentrale Erkenntnisse & Konsequenzen für LINTO

1. **Rätsel um MutohPlot gelöst (`Program Step`):**
   Das Handbuch belegt schwarz auf weiß: `0.025mm` vs. `0.010mm` ist ein Menüpunkt am Panel! LINTO muss sich nie auf einen festen Wert verlassen, sondern fragt bei Verbindungsaufbau `OF;` ab und skaliert dynamisch.
2. **Buffer Size (`Norm` vs. `Small`):**
   Am Panel kann direkt `Buffer Size: Small` (1 KByte / 1000 Zeichen) gewählt werden. Damit ist das Pufferproblem bei Pause/Abbruch ohne Firmware-Tricks hardwareseitig gelöst.
3. **Firmware-Sortierung (`Sort: Off` zwingend):**
   Wenn `Sort` am Panel auf `Pen` oder `All` steht, ignoriert der Plotter unsere im Slicer optimierte Strichreihenfolge und Leerweg-Planung! **Empfehlung:** Am Plotter für LINTO immer `Sort: Off` wählen.
4. **Befehlsakzeptanz (`VS, AS, FS: Good`):**
   Muss auf `Good` stehen, damit unsere Werkzeugbibliothek Geschwindigkeit und Andruck pro Stift steuern kann.
5. **Freie Formate / Rollenposition:**
   Da die Andruckrollen manuell auf die Papierbreite eingestellt werden, unterstützt der Slicer beliebige freie Formate („Custom Sheet Size“). Der gemeldete `OH`-Bereich ist autoritativ für die plottbare Fläche.
