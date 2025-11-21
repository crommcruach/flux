# Flux Script Generator

Dieser Ordner enthält Python-Scripts die als prozedurale Video-Quellen verwendet werden können.

## Script-Format

Jedes Script muss eine `generate_frame()` Funktion implementieren:

```python
import numpy as np

def generate_frame(frame_number, width, height, time, fps, canvas=None):
    """
    Generiert ein einzelnes Frame.
    
    Args:
        frame_number (int): Aktuelle Frame-Nummer (startet bei 0)
        width (int): Canvas-Breite in Pixeln
        height (int): Canvas-Höhe in Pixeln
        time (float): Verstrichene Zeit in Sekunden seit Start
        fps (int): Frames pro Sekunde
        canvas (numpy.ndarray): Wiederverwendbares Canvas (optional, für Performance)
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array (dtype=uint8)
        ODER
        list: Liste von (x, y, r, g, b) Tupeln für Point-Mapping
              ⚠️ Bei Point-Listen MUSS auch auf canvas gezeichnet werden!
    """
    # Nutze Canvas wenn vorhanden (schneller als neu erstellen)
    if canvas is None:
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Option 1: Direkt auf Canvas zeichnen
    canvas[10:20, 10:20] = [255, 0, 0]  # Rotes Quadrat
    return canvas
    
    # Option 2: Point-Liste (für LED-Mapping)
    rgb_values = []
    for x in range(width):
        for y in range(height):
            rgb_values.append((x, y, 255, 0, 0))
    
    # WICHTIG: Auch auf Canvas zeichnen für Preview!
    if canvas is not None:
        for x, y, r, g, b in rgb_values:
            # Zeichne 10x10 Block pro Point
            canvas[y*10:(y+1)*10, x*10:(x+1)*10] = [r, g, b]
    
    return rgb_values
```

## ⚠️ Wichtig: Canvas vs. Point-Liste

**Canvas-basiert (Standard):**
- Zeichne direkt auf das Canvas-Array
- Schneller für Full-Frame-Effekte
- Return: `numpy.ndarray`

**Point-basiert (für Mapping):**
- Return: Liste von `(x, y, r, g, b)` Tupeln
- **MUSS auch auf Canvas zeichnen**, sonst schwarze Preview!
- Siehe `fire.py`, `heartbeat.py`, `matrix_rain.py` für Beispiele

## Optionale Metadata

Scripts können Metadata definieren:

```python
METADATA = {
    "name": "Mein Effekt",
    "author": "Dein Name",
    "description": "Beschreibung des Effekts",
    "fps": 30,
    "parameters": {
        "speed": {"default": 1.0, "min": 0.1, "max": 10.0}
    }
}
```

## Verwendung

### CLI
```bash
# Liste alle Scripts
list scripts

# Lade ein Script
load script:rainbow_wave.py

# Starte Wiedergabe
start
```

### Beispiele

- **rainbow_wave.py** - Horizontale Regenbogen-Welle
- **plasma.py** - Klassischer Plasma-Effekt
- **pulse.py** - Einfache pulsierende Farben

## Tipps

### Performance
- **Nutze canvas-Parameter**: Nicht jedes Frame neu erstellen!
- Verwende NumPy für schnelle Array-Operationen
- Vermeide Python-Schleifen wo möglich (nutze Broadcasting)
- `canvas.fill(0)` ist schneller als `np.zeros()`

### Canvas-Zeichnung (Point-Listen)
Wenn dein Script Point-Listen zurückgibt:
```python
# Zeichne 10x10 Blöcke für jeden Point
for x, y, r, g, b in rgb_values:
    x_start = x * 10
    y_start = y * 10
    x_end = min(x_start + 10, width)
    y_end = min(y_start + 10, height)
    canvas[y_start:y_end, x_start:x_end] = [r, g, b]
```

### Animation
- Nutze `time` für zeitbasierte Animation (FPS-unabhängig)
- Nutze `frame_number` für frame-genaue Sequenzen
- `np.sin(time)` für periodische Bewegungen

### Kreative Ideen
- Mathematische Muster (Sinus, Perlin Noise)
- Zelluläre Automaten (Game of Life)
- Fraktale (Mandelbrot, Julia)
- Partikel-Systeme mit globalem State
- Audio-Reaktive Effekte
- Partikel-Systeme
- L-Systems
- Metaballs

### NumPy Tricks

```python
# Effiziente Grid-Generierung
x = np.linspace(0, width, width)
y = np.linspace(0, height, height)
X, Y = np.meshgrid(x, y)

# Distanz vom Zentrum
dist = np.sqrt((X - width/2)**2 + (Y - height/2)**2)

# Winkel
angle = np.arctan2(Y - height/2, X - width/2)
```

## Dependencies

Scripts haben Zugriff auf:
- `numpy`
- `colorsys` (für HSV ↔ RGB)
- `math`
- Alle anderen Python Standard-Bibliotheken

Für externe Bibliotheken (z.B. Perlin Noise), füge sie zu `requirements.txt` hinzu.
