# Video RGB Analyzer - Beispiele

## Grundlegende Verwendung

### 1. Video analysieren und RGB-Daten extrahieren

```python
from src.video_analyzer import analyze_video

# Video analysieren und als komprimierte .rgbz Datei speichern
result = analyze_video(
    video_path='mein_video.mp4',
    output_path='video_daten',
    compression_level=6  # 1-9, höher = mehr Kompression
)

print(f"Gespeichert: {result['output_file']}")
print(f"Größe: {result['file_size_mb']:.2f} MB")
```

### 2. RGB-Daten laden

```python
from src.video_analyzer import load_rgb_data

# Lade gespeicherte Daten
data = load_rgb_data('video_daten.rgbz')

# Zugriff auf Metadaten
print(f"Frames: {data['metadata']['frame_count']}")
print(f"Auflösung: {data['metadata']['width']}x{data['metadata']['height']}")
print(f"FPS: {data['metadata']['fps']}")
```

### 3. RGB-Werte einzelner Pixel abrufen

```python
from src.video_analyzer import get_pixel_rgb

# RGB-Werte eines bestimmten Pixels
r, g, b = get_pixel_rgb(
    data=data,
    frame_idx=0,  # Erster Frame
    x=100,
    y=50
)

print(f"RGB: ({r}, {g}, {b})")
```

## Erweiterte Verwendung

### Alle Pixel eines Frames durchlaufen

```python
data = load_rgb_data('video_daten.rgbz')

# Direkter Zugriff auf Frame-Array
frame_0 = data['frames'][0]  # Shape: (height, width, 3)

# Durchlaufe alle Pixel
for y in range(data['metadata']['height']):
    for x in range(data['metadata']['width']):
        r, g, b = frame_0[y, x]
        # Verarbeite RGB-Werte...
```

### Mit VideoAnalyzer-Klasse arbeiten

```python
from src.video_analyzer import VideoAnalyzer

# Erstelle Analyzer-Objekt
analyzer = VideoAnalyzer('mein_video.mp4')

# Zugriff auf Video-Eigenschaften
print(f"FPS: {analyzer.fps}")
print(f"Frames: {analyzer.frame_count}")
print(f"Größe: {analyzer.width}x{analyzer.height}")

# Extrahiere Daten
result = analyzer.extract_rgb_data('output', compression_level=9)
```

## Dateiformat

Die Funktion erstellt zwei Dateien:

1. **`.rgbz`** - Komprimierte RGB-Daten (gzip + pickle)
   - Enthält numpy array mit allen Frames
   - Format: `(frame_count, height, width, 3)` mit dtype=uint8

2. **`.json`** - Metadaten (lesbar)
   - Video-Pfad, Auflösung, Frame-Count, FPS

## Installation

```bash
pip install -r requirements.txt
```

Benötigte Pakete:
- opencv-python
- numpy
