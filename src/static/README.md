# Static Files Structure

## Verzeichnisstruktur

```
static/
├── js/                      # JavaScript Module
│   ├── constants.js        # Konstanten und Konfiguration
│   ├── state.js           # Globaler Zustand
│   ├── utils.js           # Hilfsfunktionen
│   ├── stroke-font.js     # Vektorbasierte Schriftarten
│   ├── shapes.js          # Shape-Generator (geplant)
│   ├── renderer.js        # Canvas-Rendering (geplant)
│   ├── handlers.js        # Event-Handler (geplant)
│   └── ui.js              # UI-Updates (geplant)
├── bootstrap-icons/        # Bootstrap Icon-Bibliothek
├── controls.html          # Video-Steuerung Interface
├── controls.js            # Video-Steuerung Logik
├── editor.js              # Haupt-Editor (zu refaktorisieren)
├── index.html             # Hauptseite
├── styles.css             # CSS-Styles
├── favicon.svg            # Favicon
└── logo.svg               # Logo

## Module

### constants.js
Zentrale Konstanten:
- `MIN_SCALE`, `MAX_SCALE` - Skalierungsgrenzen
- `HANDLE` - Handler-Konfiguration
- `COLORS` - Farbpalette
- `TOOLTIP` - Tooltip-Konfiguration
- `POINT` - Punkt-Rendering-Konfiguration

### state.js
Globaler Zustand und State-Management:
- Shape-Verwaltung (`shapes`, `selectedShape`, `selectedShapes`)
- Gruppierung (`groups`, `groupCounter`)
- Drag-Zustand (`dragMode`, `offsetX`, `offsetY`, etc.)
- Rendering-Zustand (`needsRedraw`, `hoveredPoint`, etc.)
- Icon-Images
- State-Setter-Funktionen
- `loadIcons()` - Lädt alle Icon-Images

### utils.js
Hilfsfunktionen:
- `markForRedraw()` - Markiert Canvas für Neuzeichnung
- `localToWorld()` - Transformiert lokale zu Weltkoordinaten
- `worldToLocal()` - Transformiert Welt- zu lokalen Koordinaten
- `worldLenBetweenLocal()` - Berechnet Weltdistanz zwischen lokalen Punkten
- `distributeAlongEdges()` - Verteilt Punkte gleichmäßig entlang Kanten

### stroke-font.js
Vektorbasierte Buchstaben-Definitionen:
- `STROKE_FONT` - Objekt mit Buchstaben A-Z, 0-9, Sonderzeichen
- `LETTER_WIDTHS` - Breiten der Buchstaben
- `DEFAULT_LETTER_SPACING` - Standard-Buchstabenabstand

## Migration Status

✅ Erstellt:
- `constants.js` - Vollständig
- `state.js` - Vollständig
- `utils.js` - Vollständig
- `stroke-font.js` - Vorhanden

🔄 In Arbeit:
- Refaktorisierung von `editor.js` in weitere Module

## Nächste Schritte

1. Extrahiere Shape-Generatoren in `shapes.js`
2. Extrahiere Rendering-Logik in `renderer.js`
3. Extrahiere Event-Handler in `handlers.js`
4. Extrahiere UI-Update-Logik in `ui.js`
5. Aktualisiere `index.html` für ES6-Module
6. Erstelle `main.js` als Einstiegspunkt
