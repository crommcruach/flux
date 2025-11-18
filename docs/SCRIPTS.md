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

### Minimales Beispiel

Erstelle `scripts/mein_script.py`:

```python
import numpy as np

METADATA = {
    'name': 'Mein Script',
    'description': 'Beschreibung',
    'parameters': {}
}

def generate_frame(frame_number, width, height, time, fps):
    """Generiert einen Frame als NumPy RGB-Array."""
    
    # Erstelle leeres Frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # ... füge hier deine Grafik-Logik ein ...
    
    return frame
```

### Vollständiges Beispiel (Farbverlauf)

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

def generate_frame(frame_number, width, height, time, fps):
    """Horizontaler Regenbogen-Verlauf."""
    
    # Erstelle leeres Frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Zeit-basierte Hue-Rotation
    hue_offset = (time * 0.1) % 1.0
    
    # Für jede Spalte
    for x in range(width):
        # Berechne Hue basierend auf Position und Zeit
        hue = (x / width + hue_offset) % 1.0
        
        # Konvertiere HSV zu RGB
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        
        # Setze alle Pixel in dieser Spalte
        frame[:, x] = [int(r*255), int(g*255), int(b*255)]
    
    return frame
```

## API-Spezifikation

### generate_frame()

```python
def generate_frame(frame_number, width, height, time, fps):
    """
    Generiert einen einzelnen Frame.
    
    Args:
        frame_number (int): Frame-Index (0, 1, 2, ...)
        width (int): Canvas-Breite in Pixel
        height (int): Canvas-Höhe in Pixel
        time (float): Zeit in Sekunden seit Start
        fps (int): Ziel-FPS
    
    Returns:
        np.ndarray: RGB-Array mit shape (height, width, 3), dtype=uint8
                    Werte: 0-255 für jeden Kanal (R, G, B)
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

### Frame Shape falsch
```python
# ❌ Falsch: (width, height, 3)
frame = np.zeros((width, height, 3))

# ✓ Richtig: (height, width, 3)
frame = np.zeros((height, width, 3))
```

### Dtype vergessen
```python
# ❌ Falsch: float64 (default)
frame = np.zeros((height, width, 3))

# ✓ Richtig: uint8 (0-255)
frame = np.zeros((height, width, 3), dtype=np.uint8)
```

### RGB statt BGR
```python
# ✓ Richtig: RGB-Reihenfolge
# OpenCV nutzt BGR, aber wir verwenden RGB!
frame[:, :] = [255, 0, 0]  # Rot
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
