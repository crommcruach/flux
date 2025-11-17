# Flux

Video-to-Art-Net DMX Control System mit Web-Interface und Multi-Kanal Unterstützung.

## Features

- 🎥 **Video Playback** - OpenCV mit Hardware-Beschleunigung (NVDEC/QSV/VAAPI)
- 🎞️ **GIF Support** - Animated GIFs mit Transparenz und Frame-Timing
- 🌐 **Art-Net Output** - Multi-Universe Support mit automatischer Grenzlogik
- 🎛️ **DMX Input Control** - 9-Kanal Steuerung (Ch1-5: Control, Ch6-9: Video Slots)
- 📡 **REST API** - Flask-basierte API mit CORS Support
- 🖥️ **Web Interfaces** - Bootstrap GUI Editor + Control Panel
- 🎨 **Multi-JSON Support** - Flexible Punkte-Konfigurationen mit Validierung
- 🔄 **4-Kanal Video System** - Bis zu 1020 Videos (255 pro Kanal)
- 🌙 **Dark Mode** - Vollständiges Theme-System mit LocalStorage
- ⚡ **Performance** - Numpy-optimierte RGB-Extraktion, Hardware-Decoding, RGB-Cache

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

### Einstellungen
- `brightness <0-100>` - Helligkeit setzen
- `speed <faktor>` - Geschwindigkeit (0.1-3.0)
- `fps <wert>` - FPS-Limit setzen
- `loop <anzahl>` - Loop-Limit (0 = endlos)

### Art-Net
- `blackout` - Alle DMX-Kanäle auf 0
- `test <farbe>` - Testmuster (red/green/blue/white)

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

### Art-Net
- `POST /api/blackout` - Blackout aktivieren
- `POST /api/test` - Body: `{"color": "red"}`

### Info
- `GET /api/status` - Aktueller Status
- `GET /api/info` - Detaillierte Informationen
- `GET /api/stats` - Live-Statistiken
- `GET /api/points` - Punkte-Listen

### Recording
- `POST /api/record/start` - Aufzeichnung starten
- `POST /api/record/stop` - Aufzeichnung stoppen

## Projektstruktur

```
Py_artnet/
├── src/
│   ├── main.py                    # Haupteinstiegspunkt
│   ├── modules/
│   │   ├── video_player.py        # Video-Playback Engine
│   │   ├── dmx_controller.py      # DMX Input Handler
│   │   ├── rest_api.py            # Flask REST API
│   │   ├── validator.py           # JSON Schema Validierung
│   │   └── utils.py               # CLI Hilfsfunktionen
│   └── static/                    # Web-Interface Assets
│       ├── index.html             # Bootstrap Canvas Editor
│       ├── controls.html          # Control Panel
│       ├── styles.css             # Gemeinsame Styles
│       ├── gui-editor.js          # Editor Logic
│       └── bootstrap-icons/       # Icon Library
├── video/
│   ├── kanal_1/                   # Video-Slots 0-254
│   ├── kanal_2/                   # Video-Slots 255-509
│   ├── kanal_3/                   # Video-Slots 510-764
│   ├── kanal_4/                   # Video-Slots 765-1019
│   └── testbild.mp4              # Test Pattern
├── data/                          # JSON Punkte-Konfigurationen
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
    "dmx_listen_port": 6454
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

## GIF Support

Das System unterstützt animated GIFs mit folgenden Features:
- **Transparenz-Handling**: Alpha-Channel wird gegen konfigurierbaren Hintergrund gerendert
- **Variable Frame-Timing**: Original GIF-Frame-Delays werden respektiert
- **RGB-Cache**: GIFs werden wie Videos gecacht für schnellere Wiedergabe
- **Konfiguration**:
  - `gif_transparency_bg`: RGB-Werte für Transparenz-Hintergrund (Standard: [0,0,0])
  - `gif_respect_frame_timing`: Variable Frame-Delays aktivieren (Standard: true)

## Hardware-Beschleunigung

Automatische Erkennung und Nutzung von:
- **NVDEC** (NVIDIA)
- **QSV** (Intel Quick Sync)
- **VAAPI** (Linux)
- **MMAL** (Raspberry Pi)

Status wird beim Start in der Konsole ausgegeben
