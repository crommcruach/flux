# Script Generator - Kurzanleitung

## Übersicht

Das Script Generator System ermöglicht es, Python-Scripts als prozedurale Videoquellen zu verwenden. Scripts generieren Frames in Echtzeit und laufen endlos - perfekt für generative Kunst, Visualisierungen und Live-Grafiken.

## Schnellstart

### 1. Scripts auflisten

**CLI:**
```bash
> scripts list
```

**API:**
```bash
GET http://localhost:5000/api/scripts
```

### 2. Script laden und starten

**CLI:**
```bash
> script:rainbow_wave
```

**API:**
```bash
POST http://localhost:5000/api/load_script
Body: {"script": "rainbow_wave"}
```

### 3. Steuerung

Alle Standard-Befehle funktionieren mit Scripts:
- `brightness 50` - Helligkeit anpassen
- `speed 2.0` - Geschwindigkeit ändern
- `stop` - Script stoppen
- `start` - Script starten

## Eigenes Script erstellen

### ⚠️ WICHTIG: Canvas vs. Points

Es gibt **zwei Methoden** um Pixel zu zeichnen:

#### Methode 1: Canvas zeichnen (Standard)
Das Script schreibt direkt auf das Canvas-Array:

```python
import numpy as np

METADATA = {
    'name': 'Mein Script',
    'description': 'Beschreibung',
    'parameters': {}
}

def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """Generiert Frame durch direktes Zeichnen auf Canvas."""
    
    # Erstelle Canvas falls nicht vorhanden
    if canvas is None:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Zeichne direkt auf Canvas
    canvas[10:20, 10:20] = [255, 0, 0]  # Rotes Quadrat
    
    return canvas
```

#### Methode 2: Point-Liste (für Mapping)
Das Script gibt eine Liste von (x, y, r, g, b) Tupeln zurück:

```python
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """Generiert Frame als Point-Liste für LED-Mapping."""
    
    rgb_values = []
    
    # Für jeden Punkt RGB-Wert berechnen
    for y in range(height):
        for x in range(width):
            # Berechne Farbe basierend auf Position/Zeit
            r = int((x / width) * 255)
            g = int((y / height) * 255) 
            b = int((time * 50) % 255)
            
            rgb_values.append((x, y, r, g, b))
    
    # WICHTIG: Schreibe Points auf Canvas für Preview
    if canvas is not None:
        for x, y, r, g, b in rgb_values:
            # Zeichne 10x10 Block für jeden Point
            x_start = x * 10
            y_start = y * 10
            x_end = min(x_start + 10, width)
            y_end = min(y_start + 10, height)
            canvas[y_start:y_end, x_start:x_end] = [r, g, b]
    
    return rgb_values
```

**Regel:** Wenn dein Script `rgb_values` zurückgibt, **muss** es auch auf Canvas zeichnen, sonst ist die Preview schwarz!

### Vollständiges Beispiel 1: Canvas-basiert (Farbverlauf)

```python
import numpy as np
import colorsys

METADATA = {
    'name': 'Color Gradient',
    'description': 'Horizontaler Farbverlauf mit Hue-Rotation',
    'parameters': {
        'speed': 1.0
    }
}

def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """Horizontaler Regenbogen-Verlauf."""
    
    # Erstelle Canvas falls nicht vorhanden
    if canvas is None:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Zeit-basierte Hue-Rotation
    hue_offset = (time * 0.1) % 1.0
    
    # Für jede Spalte
    for x in range(width):
        # Berechne Hue basierend auf Position und Zeit
        hue = (x / width + hue_offset) % 1.0
        
        # Konvertiere HSV zu RGB
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        
        # Setze alle Pixel in dieser Spalte
        canvas[:, x] = [int(r*255), int(g*255), int(b*255)]
    
    return canvas
```

### Vollständiges Beispiel 2: Point-basiert (Matrix Rain)

```python
import numpy as np
import random

METADATA = {
    'name': 'Matrix Rain',
    'description': 'Matrix-artiger Regen-Effekt',
    'parameters': {
        'speed': 1.0
    }
}

# Globaler State für Spalten-Positionen
COLUMNS = []

def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """Matrix-Regen mit fallenden grünen Pixeln."""
    
    global COLUMNS
    
    # Initialisiere Spalten beim ersten Frame
    if not COLUMNS:
        COLUMNS = [{'y': random.randint(-height, 0), 'speed': random.uniform(0.5, 2.0)} 
                   for _ in range(width)]
    
    rgb_values = []
    
    # Update und zeichne jede Spalte
    for x in range(width):
        col = COLUMNS[x]
        
        # Bewege Spalte nach unten
        col['y'] += col['speed']
        
        # Reset wenn unten angekommen
        if col['y'] > height:
            col['y'] = random.randint(-20, 0)
            col['speed'] = random.uniform(0.5, 2.0)
        
        # Zeichne Pixel an aktueller Position
        y = int(col['y'])
        if 0 <= y < height:
            rgb_values.append((x, y, 0, 255, 0))  # Grün
    
    # WICHTIG: Zeichne auf Canvas für Preview!
    if canvas is not None:
        canvas.fill(0)  # Lösche altes Frame
        for x, y, r, g, b in rgb_values:
            # Zeichne 10x10 Block pro Point
            x_start = x * 10
            y_start = y * 10
            x_end = min(x_start + 10, width)
            y_end = min(y_start + 10, height)
            canvas[y_start:y_end, x_start:x_end] = [r, g, b]
    
    return rgb_values
```

## API-Spezifikation

### generate_frame()

```python
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """
    Generiert einen einzelnen Frame.
    
    Args:
        frame_number (int): Frame-Index (0, 1, 2, ...)
        width (int): Canvas-Breite in Pixel
        height (int): Canvas-Höhe in Pixel
        time (float): Zeit in Sekunden seit Start
        fps (int): Ziel-FPS
        canvas (np.ndarray): Wiederverwendbares Canvas-Array (height, width, 3)
                             Optional, aber sollte genutzt werden für Performance
    
    Returns:
        np.ndarray: RGB-Array mit shape (height, width, 3), dtype=uint8
                    Werte: 0-255 für jeden Kanal (R, G, B)
        ODER
        list: Liste von (x, y, r, g, b) Tupeln für Point-Mapping
              ⚠️ WICHTIG: Wenn Point-Liste, MUSS auch auf canvas gezeichnet werden!
    """
```

### METADATA

```python
METADATA = {
    'name': str,           # Anzeigename (erforderlich)
    'description': str,    # Kurzbeschreibung (erforderlich)
    'parameters': dict     # Konfigurierbare Parameter (optional)
}
```

## Beispiele

Das System enthält 3 fertige Beispiele:

### rainbow_wave.py
Horizontale Regenbogen-Welle mit HSV-Farbrotation
- Nutzt `colorsys` für HSV→RGB
- Zeit-basierte Animation
- Konfigurierbare Geschwindigkeit

### plasma.py
Klassischer Plasma-Effekt mit überlagerten Sinus-Wellen
- 4 Sinus-Wellen mit verschiedenen Frequenzen
- Zeitbasierte Hue-Verschiebung
- Mathematisch generierte Muster

### pulse.py
Einfache pulsierende Farbfläche
- Sinus-basierte Helligkeits-Modulation
- Hue-Rotation
- Minimalistisches Design

## Tipps & Tricks

### Performance
- NumPy-Operationen sind schneller als Python-Loops
- Nutze Broadcasting statt Schleifen
- Cache berechnete Werte wenn möglich

### Animationen
- Nutze `time` für glatte Animationen (unabhängig von FPS)
- Nutze `frame_number` für frame-genaue Sequenzen
- `np.sin()`, `np.cos()` für periodische Bewegungen

### Farben
- `colorsys.hsv_to_rgb()` für Regenbogen-Effekte
- HSV ist intuitiver für Farbanimationen
- Hue: 0-1 (Farbton), Saturation: 0-1 (Sättigung), Value: 0-1 (Helligkeit)

### Debugging
- Fehler werden in der Console ausgegeben mit Traceback
- Test-Frames mit kleiner Auflösung (100x100)
- `print()` Ausgaben erscheinen in der Console

## Erweiterte Techniken

### Noise & Zufall
```python
import random
random.seed(42)  # Reproduzierbarer Zufall
value = random.random()
```

### Mathematische Muster
```python
import math
x_pos = width/2 + math.cos(time) * 100
y_pos = height/2 + math.sin(time) * 100
```

### Partikel-Systeme
```python
# Speichere State in METADATA oder globaler Variable
PARTICLES = []

def generate_frame(...):
    global PARTICLES
    # Update Partikel
    # Render Partikel
```

### Externe Daten
```python
# JSON lesen
import json
with open('data.json') as f:
    data = json.load(f)

# API abfragen (nur bei Bedarf, nicht jeden Frame!)
import requests
response = requests.get('http://...')
```

## Häufige Fehler

### 1. Point-Liste ohne Canvas-Zeichnung
```python
# ❌ Falsch: Point-Liste zurückgeben, aber nicht auf Canvas zeichnen
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    rgb_values = [(x, y, 255, 0, 0) for x, y in points]
    return rgb_values  # Preview bleibt schwarz!

# ✓ Richtig: Immer auch auf Canvas zeichnen
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    rgb_values = [(x, y, 255, 0, 0) for x, y in points]
    
    if canvas is not None:
        for x, y, r, g, b in rgb_values:
            x_start = x * 10
            y_start = y * 10
            canvas[y_start:y_start+10, x_start:x_start+10] = [r, g, b]
    
    return rgb_values  # Preview funktioniert!
```

### 2. Frame Shape falsch
```python
# ❌ Falsch: (width, height, 3)
frame = np.zeros((width, height, 3))

# ✓ Richtig: (height, width, 3)
frame = np.zeros((height, width, 3))
```

### 3. Dtype vergessen
```python
# ❌ Falsch: float64 (default)
canvas = np.zeros((height, width, 3))

# ✓ Richtig: uint8 (0-255)
canvas = np.zeros((height, width, 3), dtype=np.uint8)
```

### 4. Canvas-Parameter ignoriert
```python
# ❌ Falsch: Immer neues Array erstellen
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    frame = np.zeros((height, width, 3), dtype=np.uint8)  # Langsam!
    return frame

# ✓ Richtig: Canvas wiederverwenden
def generate_frame(frame_number, width, height, time, fps, canvas=None):
    if canvas is None:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas.fill(0)  # Schneller als neu erstellen
    return canvas
```

### 5. RGB statt BGR
```python
# ✓ Richtig: RGB-Reihenfolge
# OpenCV nutzt BGR, aber wir verwenden RGB!
canvas[:, :] = [255, 0, 0]  # Rot
```

## Weitere Informationen

- Vollständige Dokumentation: `scripts/README.md`
- API-Referenz: `docs/API.md`
- Beispiel-Scripts: `scripts/*.py`

## Support

Bei Fragen oder Problemen:
1. Prüfe die Console-Ausgabe auf Fehler
2. Validiere Frame-Shape und dtype
3. Teste mit minimaler Auflösung
4. Siehe Beispiel-Scripts für funktionierende Patterns
