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

## Video Converter

Der integrierte Video Converter unterstützt HAP Codec und verschiedene Optimierungen für LED-Mapping.

### Voraussetzungen

FFmpeg muss installiert sein:

```powershell
# Windows (via winget)
winget install --id=Gyan.FFmpeg -e

# Nach Installation: Terminal neu starten
# Status prüfen:
ffmpeg -version
```

### Via Web Interface

1. Öffne `http://localhost:5000/converter`
2. Wähle Output-Format:
   - **HAP** - DXT1 Kompression (beste Performance)
   - **HAP Alpha** - DXT5 mit Transparenz
   - **HAP Q** - BC7 höchste Qualität
   - **H.264** - Standard MP4 (CPU)
   - **H.264 NVENC** - NVIDIA GPU-Encoding
3. Eingabemuster:
   - Einzelne Datei: `testbild.mp4`
   - Ordner: `video/kanal_1/*.mp4`
   - Rekursiv: `video/**/*.mp4`
4. Output-Ordner: `video/converted`
5. Optionen:
   - **Resize Mode**: fit, fill, stretch, auto
   - **Target Size**: Canvas-Größe (z.B. 60x300)
   - **Loop Optimization**: Fade In/Out für nahtlose Loops
6. Klicke "Convert Videos"

### Via REST API

**Einzelne Datei konvertieren:**
```bash
curl -X POST http://localhost:5000/api/converter/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "testbild.mp4",
    "output_format": "HAP",
    "output_dir": "video/converted",
    "resize_mode": "fit",
    "target_size": [60, 300],
    "loop_optimization": true
  }'
```

**Batch-Konvertierung:**
```bash
curl -X POST http://localhost:5000/api/converter/batch \
  -H "Content-Type: application/json" \
  -d '{
    "input_pattern": "video/**/*.mp4",
    "output_format": "HAP",
    "output_dir": "video/converted",
    "resize_mode": "fit",
    "target_size": [60, 300]
  }'
```

**Video-Info abrufen:**
```bash
curl -X POST http://localhost:5000/api/converter/info \
  -H "Content-Type: application/json" \
  -d '{"video_path": "testbild.mp4"}'
```

### Output-Formate

| Format | Codec | Beschreibung | Use Case |
|--------|-------|--------------|----------|
| **HAP** | DXT1 | Schnellste Wiedergabe | LED-Mapping, Echtzeit |
| **HAP Alpha** | DXT5 | Mit Transparenz | Overlays, Compositing |
| **HAP Q** | BC7 | Höchste Qualität | Hochauflösende LEDs |
| **H.264** | libx264 | Standard MP4 | Kompatibilität |
| **H.264 NVENC** | h264_nvenc | GPU-Encoding | Schnelle Konvertierung |

### Resize Modes

- **none**: Keine Größenänderung
- **fit**: Einpassen mit Letterbox (behält Seitenverhältnis)
- **fill**: Füllen mit Crop (behält Seitenverhältnis)
- **stretch**: Strecken auf Zielgröße (verzerrt)
- **auto**: Verwendet Canvas-Größe aus config.json

### Loop-Optimierung

Aktiviert Fade In/Out für nahtlose Video-Loops:
- **Fade Duration**: 0.5 Sekunden
- **Effect**: Schwarzer Ein-/Ausblende am Anfang und Ende
- **Use Case**: Videos die endlos wiederholt werden

### Beispiele

**Alle Videos in HAP konvertieren:**
```bash
# Via API
curl -X POST http://localhost:5000/api/converter/batch \
  -H "Content-Type: application/json" \
  -d '{
    "input_pattern": "video/**/*.mp4",
    "output_format": "HAP",
    "output_dir": "video/hap_optimized",
    "resize_mode": "auto",
    "loop_optimization": true
  }'
```

**Einzelnes Video mit Custom-Größe:**
```bash
curl -X POST http://localhost:5000/api/converter/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "myvideo.mp4",
    "output_format": "HAP",
    "output_dir": "output",
    "resize_mode": "fit",
    "target_size": [120, 600]
  }'
```

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

## Art-Net Optimierung

### Delta-Encoding

Delta-Encoding reduziert Netzwerktraffic um 50-90% bei statischen oder langsamen Szenen, indem nur geänderte Pixel übertragen werden.

**Via CLI:**
```bash
> delta status                # Aktuellen Status anzeigen
> delta on                    # Delta-Encoding aktivieren
> delta off                   # Delta-Encoding deaktivieren
> delta threshold 10          # Schwellwert setzen (höher = weniger Updates)
> delta interval 30           # Full-Frame alle 30 Frames senden
```

**Via REST API:**
```bash
# Status abrufen
curl http://localhost:5000/api/artnet/info

# Delta-Encoding aktivieren
curl -X POST http://localhost:5000/api/artnet/delta-encoding \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Schwellwert ändern
curl -X POST http://localhost:5000/api/artnet/delta-encoding \
  -H "Content-Type: application/json" \
  -d '{"threshold": 15, "full_frame_interval": 60}'
```

**Via config.json:**
```json
{
  "artnet_config": {
    "bit_depth": 8,
    "delta_encoding": {
      "enabled": true,
      "threshold": 8,
      "threshold_16bit": 2048,
      "full_frame_interval": 30
    }
  }
}
```

**Konfiguration:**
- `enabled`: Delta-Encoding ein/aus
- `threshold`: Minimale Farbänderung für Update (0-255 bei 8-bit)
- `threshold_16bit`: Schwellwert für 16-bit LEDs (0-65535)
- `full_frame_interval`: Anzahl Frames zwischen Full-Frame-Sync (verhindert Packet Loss Artefakte)

**Empfohlene Einstellungen:**
- Statische Szenen (Testbilder): `threshold: 5-10`, `interval: 60`
- Langsame Videos: `threshold: 8-15`, `interval: 30`
- Schnelle Videos: `threshold: 20-30`, `interval: 15`

**A/B Testing:**
```bash
> delta off                   # Baseline messen
> stats                       # Netzwerktraffic notieren
> delta on                    # Delta-Encoding aktivieren
> stats                       # Traffic Reduktion vergleichen
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

## CLI Debug-Modus

### Console-Logging steuern

Das Console-Logging kann zwischen verschiedenen Detailstufen umgeschaltet werden:

**Via CLI:**
```bash
> debug                       # Status anzeigen
> debug off                   # Nur Warnings & Errors (Standard)
> debug on                    # INFO, WARNING, ERROR anzeigen
> debug verbose               # Alle Meldungen (DEBUG, INFO, WARNING, ERROR)
```

**Via config.json (persistent):**
```json
{
  "app": {
    "console_log_level": "WARNING"
  }
}
```

Verfügbare Levels:
- `"DEBUG"` - Alle Meldungen (sehr detailliert)
- `"INFO"` - Informationen + Warnungen + Fehler
- `"WARNING"` - Nur Warnungen und Fehler (Standard)
- `"ERROR"` - Nur Fehler
- `"CRITICAL"` - Nur kritische Fehler

**Hinweis:** Die Log-Datei (`logs/flux_*.log`) enthält immer alle Meldungen unabhängig vom Console-Level.

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
