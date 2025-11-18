# Flux Script Generator

Dieser Ordner enthält Python-Scripts die als prozedurale Video-Quellen verwendet werden können.

## Script-Format

Jedes Script muss eine `generate_frame()` Funktion implementieren:

```python
import numpy as np

def generate_frame(frame_number, width, height, time, fps=30):
    """
    Generiert ein einzelnes Frame.
    
    Args:
        frame_number (int): Aktuelle Frame-Nummer (startet bei 0)
        width (int): Canvas-Breite in Pixeln
        height (int): Canvas-Höhe in Pixeln
        time (float): Verstrichene Zeit in Sekunden seit Start
        fps (int): Frames pro Sekunde
    
    Returns:
        numpy.ndarray: Frame als (height, width, 3) RGB Array (dtype=uint8)
    """
    # Erstelle Frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Deine Logik hier...
    
    return frame
```

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
- Verwende NumPy für schnelle Array-Operationen
- Vermeide Python-Schleifen wo möglich
- Nutze vectorization für Pixel-Operationen

### Kreative Ideen
- Mathematische Muster (Sinus, Perlin Noise)
- Zelluläre Automaten (Game of Life)
- Fraktale (Mandelbrot, Julia)
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
