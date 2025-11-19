# Flux

Video-to-Art-Net DMX Control System mit Web-Interface und Multi-Kanal Unterstützung.

## Features

### Video & Content
- 🎥 **Video Playback** - OpenCV mit Hardware-Beschleunigung (NVDEC/QSV/VAAPI)
- 🎞️ **GIF Support** - Animated GIFs mit Transparenz und Frame-Timing
- 🎨 **Script Generator** - Prozedurale Grafiken via Python (Shader-ähnlich)
- 💾 **RGB Cache** - msgpack-basiertes Caching für schnelle Wiedergabe
- 🔄 **4-Kanal Video System** - Bis zu 1020 Videos (255 pro Kanal)

### Art-Net & DMX
- 🌐 **Art-Net Output** - Multi-Universe Support mit automatischer Grenzlogik
- 🎨 **RGB Channel Mapping** - Konfigurierbare Kanal-Reihenfolge pro Universum (RGB, GRB, BGR, etc.)
- 🏛️ **DMX Input Control** - 9-Kanal Steuerung (Ch1-5: Control, Ch6-9: Video Slots)

### Web Interface
- 📡 **REST API** - Flask-basierte API mit WebSocket, CORS Support
- 🖥️ **Bootstrap GUI** - Canvas Editor + Control Panel + Config Manager
- 🌙 **Dark Mode** - Vollständiges Theme-System mit LocalStorage
- 🛎️ **Toast-Benachrichtigungen** - Theme-aware Notifications
- 🔍 **Canvas-Zoom & Scrollbars** - Zoom per Maus & Buttons, automatische Scrollbalken

### Konfiguration & Verwaltung
- ⚙️ **Dynamic Config UI** - Web-basierte config.json Verwaltung
- 🎨 **Multi-JSON Support** - Flexible Punkte-Konfigurationen mit Validierung
- 💾 **Server-Projektverwaltung** - Projekte speichern/laden/löschen im Backend, Download & Modal-UI
- ⚡ **Performance** - NumPy-optimierte RGB-Extraktion, Hardware-Decoding

## Installation

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Optional: Python Environment konfigurieren
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

## Schnellstart

```bash
# Hauptanwendung starten
python src/main.py

# REST API starten (im CLI)
> api start

# Web-Interfaces öffnen
# http://localhost:5000 - Canvas Editor (Bootstrap GUI)
# http://localhost:5000/controls - Control Panel
```

## CLI Befehle

### Playback
- `start` - Video-Wiedergabe starten
- `stop` - Video stoppen
- `pause` / `resume` - Pausieren/Fortsetzen
- `restart` - Video neu starten

### Video-Verwaltung
- `load <pfad>` - Video laden
- `list` - Alle Videos anzeigen
- `switch <name>` - Video wechseln

### Punkte-Verwaltung
- `points list` - Alle JSON-Dateien auflisten
- `points validate [name]` - JSON validieren
- `points switch <name>` - Punkte-Liste wechseln
- `points reload` - Aktuelle Liste neu laden

### Script Generator
- `scripts list` - Alle verfügbaren Scripts anzeigen
- `script:<name>` - Script laden und starten (z.B. `script:rainbow_wave`)
- `load script:<name>` - Alternatives Format zum Laden

### Einstellungen
- `brightness <0-100>` - Helligkeit setzen
- `speed <faktor>` - Geschwindigkeit (0.1-3.0)
- `fps <wert>` - FPS-Limit setzen
- `loop <anzahl>` - Loop-Limit (0 = endlos)

### Art-Net
- `blackout` - Alle DMX-Kanäle auf 0
- `test <farbe>` - Testmuster (red/green/blue/white/gradient)
- `ip <adresse>` - Art-Net Ziel-IP setzen
- `universe <nummer>` - Start-Universum setzen

### REST API
- `api start [port]` - Server starten (Standard: 5000)
- `api stop` - Server stoppen

### Info
- `status` - Aktueller Status
- `info` - Detaillierte Informationen
- `stats` - Live-Statistiken

## REST API Endpoints

### Playback
- `POST /api/play` - Video starten
- `POST /api/stop` - Video stoppen
- `POST /api/pause` - Pausieren
- `POST /api/resume` - Fortsetzen
- `POST /api/restart` - Neu starten

### Settings
- `POST /api/brightness` - Body: `{"value": 0-100}`
- `POST /api/speed` - Body: `{"value": 0.1-3.0}`
- `POST /api/fps` - Body: `{"value": 30}`
- `POST /api/loop` - Body: `{"value": 0}`

### Video Management
- `GET /api/videos` - Liste aller Videos
- `POST /api/video/load` - Body: `{"path": "video.mp4"}`

### Script Generator
- `GET /api/scripts` - Liste aller Scripts
- `POST /api/load_script` - Body: `{"script": "rainbow_wave"}`
- `GET /api/script/info/<name>` - Script-Metadaten

### Art-Net
- `POST /api/blackout` - Blackout aktivieren
- `POST /api/test` - Body: `{"color": "red"}`
- `GET /api/local_ips` - Verfügbare lokale IPs
- `POST /api/ip` - Body: `{"ip": "192.168.1.11"}`

### Configuration
- `GET /api/config` - Aktuelle Konfiguration
- `POST /api/config` - Konfiguration speichern (mit automatischer Validierung & Backup)
- `POST /api/config/validate` - Konfiguration validieren (ohne speichern)
- `POST /api/config/restore` - Von Backup wiederherstellen
- `GET /api/config/schema` - JSON-Schema abrufen
- `GET /api/config/default` - Standard-Konfiguration generieren

### Info
- `GET /api/status` - Aktueller Status
- `GET /api/info` - Detaillierte Informationen
- `GET /api/stats` - Live-Statistiken
- `GET /api/points` - Punkte-Listen

### Recording
- `POST /api/record/start` - Aufzeichnung starten
- `POST /api/record/stop` - Aufzeichnung stoppen

### Cache Management
- `POST /api/cache/clear` - Cache leeren
- `GET /api/cache/stats` - Cache-Statistiken

## Projektstruktur

```
Py_artnet/
├── src/
│   ├── main.py                    # Haupteinstiegspunkt
│   ├── modules/
│   │   ├── video_player.py        # Video-Playback Engine
│   │   ├── script_player.py       # Script-Playback Engine
│   │   ├── script_generator.py    # Script Loader & Manager
│   │   ├── points_loader.py       # Points-JSON Parser (NEU)
│   │   ├── cache_manager.py       # RGB Cache Manager (NEU)
│   │   ├── artnet_manager.py      # Art-Net Output Handler
│   │   ├── dmx_controller.py      # DMX Input Handler
│   │   ├── rest_api.py            # Flask REST API
│   │   ├── api_*.py               # API Route Modules
│   │   ├── cli_handler.py         # CLI Command Handler
│   │   ├── validator.py           # JSON Schema Validierung
│   │   ├── logger.py              # Logging System
│   │   └── utils.py               # CLI Hilfsfunktionen
│   └── static/                    # Web-Interface Assets
│       ├── index.html             # Bootstrap Canvas Editor
│       ├── controls.html          # Control Panel
│       ├── config.html            # Dynamic Config Manager (NEU)
│       ├── styles.css             # Gemeinsame Styles
│       ├── editor.js              # Editor Logic
│       ├── controls.js            # Control Panel Logic
│       └── bootstrap-icons/       # Icon Library
├── scripts/                       # Prozedurale Shader-Scripts (NEU)
│   ├── rainbow_wave.py
│   ├── plasma.py
│   ├── pulse.py
│   └── line_*.py                  # Line-based Scripts
├── video/
│   ├── kanal_1/                   # Video-Slots 0-254
│   ├── kanal_2/                   # Video-Slots 255-509
│   ├── kanal_3/                   # Video-Slots 510-764
│   ├── kanal_4/                   # Video-Slots 765-1019
│   └── testbild.mp4              # Test Pattern
├── data/                          # JSON Punkte-Konfigurationen
├── cache/                         # RGB Cache Dateien (.msgpack)
├── PROJECTS/                      # Gespeicherte Projekte
├── docs/                          # Erweiterte Dokumentation
│   ├── API.md                     # API Reference
│   ├── SCRIPTS.md                 # Script Generator Docs
│   ├── USAGE.md                   # Usage Examples
│   └── LOGGING.md                 # Logging Configuration
├── config.json                    # Zentrale Konfiguration
├── requirements.txt               # Python Dependencies
└── TODO.md                        # Feature Roadmap
```

## Konfiguration (config.json)

```json
{
  "artnet": {
    "target_ip": "127.0.0.1",
    "start_universe": 1,
    "dmx_control_universe": 100,
    "dmx_listen_ip": "0.0.0.0",
    "dmx_listen_port": 6454,
    "universe_configs": {
      "default": "RGB",
      "0": "GRB",
      "1": "BGR"
    }
  },
  "video": {
    "extensions": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".gif"],
    "max_per_channel": 255,
    "default_fps": null,
    "default_brightness": 100,
    "default_speed": 1.0,
    "gif_transparency_bg": [0, 0, 0],
    "gif_respect_frame_timing": true
  },
  "paths": {
    "video_dir": "video",
    "data_dir": "data",
    "points_json": "video_rgb_data.json"
  },
  "channels": {
    "max_per_universe": 510,
    "channels_per_point": 3
  }
}
```

## DMX Kanal-Mapping

- **Kanal 1**: Play/Stop (0=Stop, 128+=Play)
- **Kanal 2**: Brightness (0-255)
- **Kanal 3**: Speed (0-255, 128=1.0x)
- **Kanal 4**: Pause/Resume (0=Resume, 128+=Pause)
- **Kanal 5**: Blackout (128+=Blackout)
- **Kanal 6**: Video-Kanal Auswahl (0-63=K1, 64-127=K2, 128-191=K3, 192-255=K4)
- **Kanal 7-9**: Video-Slot Auswahl (0-255 pro Kanal)

## RGB-Kanal-Reihenfolge (Channel Mapping)

Pro Art-Net Universum kann die Farb-Kanal-Reihenfolge konfiguriert werden. Dies ist nötig wenn LEDs nicht die Standard-RGB Reihenfolge verwenden.

### Unterstützte Formate
- **RGB** - Standard (z.B. WS2812B) 
- **GRB** - Häufig bei WS2811
- **BGR** - Manche China-LEDs
- **RBG**, **GBR**, **BRG** - Weitere Permutationen

### Konfiguration
```json
"universe_configs": {
  "default": "RGB",     // Standard für alle nicht spezifizierten Universen
  "0": "GRB",          // Universum 0 verwendet GRB
  "1": "BGR",          // Universum 1 verwendet BGR
  "5": "RBG"           // Universum 5 verwendet RBG
}
```

**Hinweise:**
- Die Umordnung erfolgt automatisch bei der Ausgabe
- Testmuster berücksichtigen die konfigurierte Reihenfolge
- Bei fehlender Konfiguration wird "RGB" verwendet

## GIF Support

Das System unterstützt animated GIFs mit folgenden Features:
- **Transparenz-Handling**: Alpha-Channel wird gegen konfigurierbaren Hintergrund gerendert
- **Variable Frame-Timing**: Original GIF-Frame-Delays werden respektiert
- **RGB-Cache**: GIFs werden wie Videos gecacht für schnellere Wiedergabe
- **Konfiguration**:
  - `gif_transparency_bg`: RGB-Werte für Transparenz-Hintergrund (Standard: [0,0,0])
  - `gif_respect_frame_timing`: Variable Frame-Delays aktivieren (Standard: true)

## Prozedural generierte Grafiken (Scripts)

Neben Video-Dateien können auch Python-Scripts als Videoquellen verwendet werden. Diese generieren Frames prozedural in Echtzeit und laufen endlos.

### Features
- **Infinite Content**: Scripts laufen ohne Wiederholung
- **Python-basiert**: Volle Flexibilität mit NumPy, Math, etc.
- **Hot-Loading**: Scripts können zur Laufzeit gewechselt werden
- **Standard-Controls**: Brightness, Speed, etc. funktionieren mit Scripts

### Verwendung

**CLI:**
```bash
> scripts list              # Alle verfügbaren Scripts anzeigen
> script:rainbow_wave       # Script laden und starten
> script:plasma             # Anderes Script laden
```

**API:**
```bash
GET  /api/scripts           # Liste aller Scripts
POST /api/load_script       # Body: {"script": "rainbow_wave"}
```

### Eigene Scripts erstellen

Scripts liegen im `scripts/` Ordner und müssen folgende Struktur haben:

```python
import numpy as np

METADATA = {
    'name': 'My Script',
    'description': 'Does something cool',
    'parameters': {
        'speed': 1.0
    }
}

def generate_frame(frame_number, width, height, time, fps):
    """
    Generiert einen Frame als NumPy-Array.
    
    Args:
        frame_number: Frame-Index (0, 1, 2, ...)
        width: Canvas-Breite
        height: Canvas-Höhe
        time: Zeit in Sekunden seit Start
        fps: Ziel-FPS
    
    Returns:
        np.array: RGB-Array mit shape (height, width, 3), dtype=uint8
    """
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # ... generiere Grafik ...
    return frame
```

Siehe `scripts/README.md` für detaillierte Dokumentation und Beispiele.

## Hardware-Beschleunigung

Automatische Erkennung und Nutzung von:
- **NVDEC** (NVIDIA)
- **QSV** (Intel Quick Sync)
- **VAAPI** (Linux)
- **MMAL** (Raspberry Pi)

Status wird beim Start in der Konsole ausgegeben
