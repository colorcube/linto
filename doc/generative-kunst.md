# Generative Kunst – Integrationskonzept

Stand: 2026-10-13 · Teil von [konzept.md](konzept.md) · Status: **Idee, zurückgestellt** (D-11)

> [!NOTE]
> Bisherige Erfahrung: JavaScript (p5.js) und Processing. Beide können SVG exportieren (Processing: `beginRecord(SVG, …)`, p5.js: `p5.js-svg`). Am wichtigsten ist daher **Stufe 0 (Datei-Brücke)**. Sie braucht im Kern nur neu ladbare Importe, und die sind im Konzept bereits vorgesehen. Die Stufen 2 und 3 (Python-SDK) sind spätere Optionen. Denkbar wäre auch ein kleines JS-Hilfsmodul, das Linien direkt an plotd schickt.

## Ziel
Generative Arbeiten (Code → Linien) sollen sich ohne Umwege auf dem XP-500 plotten lassen. Dazu gehören schnelles Iterieren, reproduzierbare Ergebnisse (Seed + Parameter) und eine sinnvolle Nutzung des A0-Formats.
Grundsatz: **Externe Werkzeuge bleiben erlaubt.** Plotter Studio soll sie *aufnehmen*, nicht ersetzen.

## Vier Integrationsstufen

| Stufe | Name | Sprache | Wie | Aufwand |
|---|---|---|---|---|
| 0 | **Datei-Brücke** | beliebig (Processing, p5.js, Python, Rust …) | Skript schreibt SVG/HPGL → *verlinkter Import* mit Auto-Reload bei Dateiänderung. Position, Skalierung und Stiftzuordnung bleiben erhalten. | S |
| 1 | **CLI & Python-API** | beliebig / Python | `plotter-studio plot out.svg --profile xp570 --page A0 --fit 20mm`, in Python: `ps.plot(lines, page="A0")` → Job an `plotd`. Kein GUI nötig. | S (fällt aus AP3/AP4 ab) |
| 2 | **Generator-Objekte** | Python | Sketch-Datei mit deklarierten Parametern → Objekt im Dokument, Parameter-Panel, Live-Neuberechnung, Seed-Verwaltung, Variationsbogen | M–L |
| 3 | **Modifikatoren** | eingebaut / Plugin | Nicht-destruktive Filter auf beliebigen Objekten: Schraffur, Noise-Verzerrung, Occlusion, Array/Wiederholung, Clip | M–L |

Empfehlung: **Stufe 0 + 1 früh** (fast gratis, sobald Import und plotd existieren), **Stufe 2 als eigener Meilenstein**, Stufe 3 schrittweise.

## Stufe 2 im Detail: Generator-SDK

### Sketch-API (Entwurf)

```python
# sketches/waves.py
from plotter_studio.gen import Sketch, Param

class Waves(Sketch):
    # Parameter → automatisch Slider/Felder im Panel
    lines     = Param(80, min=10, max=400, step=1)
    amplitude = Param(12.0, min=0, max=50, unit="mm")
    freq      = Param(3.0, min=0.1, max=20)
    two_pens  = Param(True)

    def draw(self, g):            # g: Zeichenkontext in mm, Bereich = Generator-Rahmen
        w, h = g.width, g.height
        for i in range(self.lines):
            y0 = h * i / self.lines
            xs = g.linspace(0, w, 600)
            ys = y0 + self.amplitude * g.noise(xs * 0.01, i * 0.1) \
                 * g.sin(xs / w * self.freq * g.tau)
            g.pen(2 if (self.two_pens and i % 2) else 1)
            g.polyline(xs, ys)
```

Der Kontext `g` stellt bereit:
- `polyline`, `line`, `rect`, `circle`, `arc`, `bezier`, `text` (Hershey), `pen(n)`,
- `rng` (seeded numpy-Generator), `noise` (Simplex/Perlin, seeded),
- Transform-Stack (`push`, `translate`, `rotate`, `scale`),
- Shapely-Brücke (`g.geometry(shp)`) sowie Helfer `hatch(polygon, angle, spacing)`, `occlude()`, `clip()`.

### Ausführung
- **Runner im Subprozess** (`python -m plotter_studio.gen.run sketch.py --params … --seed …`). Er gibt Polylinien binär zurück (npz über stdout).
  Das hält die GUI auch bei Endlosschleifen und Abstürzen bedienbar, mit Timeout und Abbruch-Button.
- **Live-Reload:** Dateiüberwachung (inotify/`watchfiles`) → bei Speichern neu rechnen. Tracebacks erscheinen im Panel.
- **Cache:** Schlüssel = (Hash Skript, Parameter, Seed, Rahmengröße). Die Ausgabe wird im Projekt gespeichert, damit das Projekt auch ohne Skript öffnet.
- **Einfrieren:** Generator → statische Pfade (Snapshot), z. B. um anschließend von Hand nachzubearbeiten.

### Reproduzierbarkeit & Editionen
- Jeder Generator speichert Skript-Hash, Parameter und Seed. Das **Plot-Log** hält fest, welche Variante wann mit welchen Stiften geplottet wurde.
- Optional: Seed/Parameter als kleine Hershey-Signatur in eine Blattecke plotten.

### Variationsbogen (A0 ausnutzen)
Raster aus *n × m* Zellen, jede Zelle zeigt denselben Generator mit Seed `s+i` oder einer Parameter-Interpolation (z. B. `amplitude` von 0 → 50 über die Spalten). Taugt als Kontaktbogen zum Auswählen oder als eigenständiges Werk.

### vsketch-Kompatibilität (optional)
[vsketch](https://github.com/abey79/vsketch) ist das etablierte Python-Framework für Plotter-Kunst und baut auf vpype auf. Wenn Plotter Studio vpype als Polylinien-Ebene nutzt (⟨Q-05⟩), kann ein Adapter vsketch-Sketches direkt als Generator-Objekt laden: Parameter aus `vsk.Param` übernehmen, `draw(vsk)` ausführen, das vpype-Document übernehmen. So wären vorhandene vsketch-Arbeiten und Beispiele sofort nutzbar.

## Stufe 3: Modifikatoren (Stapel pro Objekt)

```
Objekt "Kreisfeld"
 ├─ Generator: circles.py (seed 7)
 ├─ Modifikator: Occlusion (vorne verdeckt hinten)
 ├─ Modifikator: Noise-Verzerrung (Amplitude 1.5 mm)
 └─ Modifikator: Clip auf Blattrand
```
Jeder Modifikator ist eine Funktion `Lines → Lines` mit Parametern und lässt sich daher dieselbe Infrastruktur wie Pipeline-Schritte teilen. Eigene Modifikatoren können später als Plugins (Python-Entry-Points) hinzukommen.

## Plot-spezifische Hinweise für generative Arbeiten
- **Datenvolumen:** 9600 Baud ≈ 3,4 MB/h. Der Pre-Flight zeigt Übertragungsdauer vs. Plotdauer, Simplify ist dafür das Hauptwerkzeug.
- **Tusche & Papier:** sehr dichte Linien weichen Papier auf. Optional „Dichtewarnung“ (Strichlänge pro cm²) als Heatmap.
- **Reihenfolge:** Bei Nass-in-Nass-Problemen nicht streng nach Nähe sortieren, sondern „räumlich verteilt“ bzw. mit Trocknungspause pro Stift.
