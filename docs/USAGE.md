# Flux - Usage Guide

## Grundlegende Verwendung

### 1. Anwendung starten

```bash
# Standard-Start
python src/main.py

# Mit spezifischer Konfiguration
python src/main.py --config custom_config.json
```

### 2. Video abspielen

**Via CLI:**
```bash
> load video/testbild.mp4    # Video laden
> start                       # Wiedergabe starten
> brightness 75               # Helligkeit auf 75% setzen
> speed 1.5                   # Geschwindigkeit auf 1.5x setzen
```

**Via Web Interface:**
1. Browser öffnen: `http://localhost:5000/controls`
2. Video aus Liste auswählen
3. Play-Button klicken
4. Slider für Brightness/Speed nutzen

### 3. Prozedurale Scripts nutzen

**Via CLI:**
```bash
> scripts list                # Verfügbare Scripts anzeigen
> script:rainbow_wave         # Script laden und starten
> brightness 80               # Helligkeit anpassen (funktioniert auch für Scripts)
```

**Via API:**
```bash
curl -X POST http://localhost:5000/api/load_script \
  -H "Content-Type: application/json" \
  -d '{"script": "rainbow_wave"}'
```

## Points-Konfiguration

### Points-Datei wechseln

```bash
> points list                 # Alle verfügbaren Points-Dateien anzeigen
> points switch my_config     # Andere Konfiguration laden
> points validate             # Aktuelle Konfiguration validieren
```

### Eigene Points-Datei erstellen

```json
{
  "canvas": {
    "width": 1920,
    "height": 1080
  },
  "objects": [
    {
      "id": "strip-1",
      "points": [
        {"x": 100, "y": 200},
        {"x": 101, "y": 200},
        {"x": 102, "y": 200}
      ]
    }
  ]
}
```

Speichere die Datei in `data/` und lade sie mit `points switch <name>`.

## Script Generator

### Eigenes Script erstellen

1. Erstelle Datei in `scripts/my_script.py`:

```python
import numpy as np

METADATA = {
    'name': 'My Script',
    'description': 'Beschreibung des Scripts',
    'parameters': {
        'speed': 1.0
    }
}

def generate_frame(frame_number, width, height, time, fps):
    """
    Generiert einen einzelnen Frame.
    
    Args:
        frame_number: Frame-Index (0, 1, 2, ...)
        width: Canvas-Breite in Pixeln
        height: Canvas-Höhe in Pixeln
        time: Zeit in Sekunden seit Start (float)
        fps: Ziel-FPS (float)
    
    Returns:
        np.array: RGB-Frame, shape (height, width, 3), dtype=uint8
    """
    # Erstelle leeren schwarzen Frame
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Beispiel: Rotes Quadrat das sich bewegt
    x = int((time * 100) % width)
    y = height // 2
    frame[y-10:y+10, x-10:x+10] = [255, 0, 0]  # Rot
    
    return frame
```

2. Script laden:
```bash
> script:my_script
```

Siehe `scripts/README.md` für weitere Beispiele.

## Konfiguration verwalten

### Via Web Interface

1. Öffne `http://localhost:5000/config`
2. Ändere Werte in den Formularen
3. Klicke "Save Configuration"
4. System erstellt automatisch Backup

### Via config.json

```json
{
  "artnet": {
    "target_ip": "192.168.1.11",
    "start_universe": 0,
    "universe_configs": {
      "default": "RGB",
      "0": "GRB"
    }
  },
  "video": {
    "default_fps": 30,
    "default_brightness": 100
  }
}
```

## Cache Management

### Cache nutzen

Der RGB-Cache beschleunigt die Wiedergabe:

```bash
# Cache-Statistiken anzeigen
curl http://localhost:5000/api/cache/stats

# Cache leeren
curl -X POST http://localhost:5000/api/cache/clear
```

### Cache-Konfiguration

```json
{
  "cache": {
    "enabled": true,
    "max_size_mb": 1000
  }
}
```

## DMX Control

### DMX-Kanal Mapping

Sende DMX-Befehle auf Universum 100 (konfigurierbar):

- **Kanal 1**: Play/Stop (0-127=Stop, 128-255=Play)
- **Kanal 2**: Brightness (0-255)
- **Kanal 3**: Speed (0-255, 128=1.0x)
- **Kanal 4**: Pause/Resume (0-127=Resume, 128-255=Pause)
- **Kanal 5**: Blackout (0-127=Normal, 128-255=Blackout)
- **Kanal 6-9**: Video-Slot Auswahl

### Video-Slots

```bash
# Videos in Ordner organisieren:
video/kanal_1/video001.mp4    # Slot 0
video/kanal_1/video002.mp4    # Slot 1
video/kanal_2/video001.mp4    # Slot 255
```

DMX-Kanäle 6-9 wählen Video automatisch aus.

## Projekte verwalten

### Projekt speichern

1. Öffne Canvas Editor: `http://localhost:5000`
2. Erstelle Points-Konfiguration
3. Klicke "Save Project"
4. Projekt wird in `PROJECTS/` gespeichert

### Projekt laden

```bash
> project load Test_20251117_150828
```

Oder via Web Interface: Projects-Dropdown → Load

## Installation

```bash
# Dependencies installieren
pip install -r requirements.txt

# Optional: Virtual Environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

Benötigte Pakete:
- opencv-python
- numpy
