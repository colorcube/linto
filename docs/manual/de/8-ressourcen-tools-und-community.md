# 8. Empfohlene Ressourcen, Tools & Community-Sammlungen

Für kreatives Arbeiten, generative Kunst, algorithmisches Design und den praktischen Erfahrungsaustausch mit Stiftplottern gibt es eine lebendige, weltweite Open-Source- und Maker-Community. Hier findest du die wichtigsten Anlaufstellen, kuratierte Sammlungen, Software-Werkzeuge und Foren.

---

## 1. Zentrale Sammlungen & Community-Hubs

* **[Awesome Plotters (GitHub)](https://github.com/beardicus/awesome-plotters):**
  *Die* zentrale, kuratierte Linksammlung auf GitHub für computergesteuerte Zeichenmaschinen, Plotter-Art, Software, Firmware, mathematische Bibliotheken und Hardware-Projekte. Ein idealer Startpunkt für Recherchen zu allen Aspekten rund um Stiftplotter.
* **[Drawingbots.net](https://drawingbots.net/):**
  Der zentrale internationale Community-Hub für Plotter-Künstler und Zeichenroboter-Bauer. Bietet Software- und Hardware-Verzeichnisse, Tutorials, Interviews und einen sehr aktiven **Discord-Server** zum Erfahrungsaustausch über Stifte, Papiere, Tinten und Mechanik.
* **[Reddit r/PlotterArt](https://www.reddit.com/r/PlotterArt/):**
  Eine sehr aktive Reddit-Community mit täglichen Inspirationen, Vorstellungen eigener Plotter-Arbeiten, Praxistests verschiedener Stiftarten (Fineliner, Gelschreiber, Tusche, Marker) und Papiersorten sowie Hilfestellungen bei mechanischen und softwareseitigen Problemen.

---

## 2. Spezialisierte Vektor-Werkzeuge für Plotter

* **[Inkcut](https://github.com/inkcut/inkcut):**
  Eine etablierte Open-Source-Alternative zu LINTO zur Ansteuerung von 2D-Plottern und Schneideplottern (Vinyl-Cuttern). Unterstützt insbesondere das Folienschneiden inklusive Schleppmesser-Offset-Kompensation (*Blade Offset* / *Overcut*), Entgitterungslinien (*Weeding*) sowie eine direkte Inkscape-Integration. Viele der Geräteprofile in LINTO stammen ursprünglich aus Inkcut.
* **[vpype](https://github.com/abey79/vpype):**
  Das Standard-Kommandozeilenwerkzeug für Vektorkunst auf Stiftplottern. Unterstützt automatisches Erzeugen von Schraffuren (*Hatching*) zur Füllung von Flächen mit Linienmustern, Skalieren, Filtern, Kurvenglättung und Transformationen von SVG-Dateien.
* **[vsketch](https://github.com/abey79/vsketch):**
  Ein auf *vpype* und Python aufbauendes Entwicklungs-Framework, das speziell für generative Plotter-Kunst geschaffen wurde. Bietet einen interaktiven Viewer, Live-Reload beim Coden und automatischen SVG-Export.
* **[Turtletoy](https://turtletoy.net/):**
  Eine faszinierende Online-Plattform für generative Vektorkunst direkt im Browser. Skripte werden mit einer an Python-Turtle angelehnten API geschrieben und können direkt als saubere, optimierte SVG-Dateien für LINTO heruntergeladen werden.
* **[ln (3D Line Art Engine)](https://github.com/fogleman/ln):**
  Eine blitzschnelle 3D-zu-Vektor-Engine in Go (auch als Python-Bindings verfügbar), die 3D-Modelle (`.obj`, `.stl`) und mathematische Funktionen in 2D-Vektorzeichnungen umrechnet und verdeckte Linien (*Hidden Line Removal*) verlässlich handhabt.
