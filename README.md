# Flux

Video-to-Art-Net DMX Control System mit Web-Interface und Multi-Kanal Unterstützung.

## Features

### Video & Content
- 🎥 **Video Playback** - OpenCV mit Hardware-Beschleunigung (NVDEC/QSV/VAAPI)
-  **Script Generator** - Prozedurale Grafiken via Python (Shader-ähnlich)
- 🎬 **Multi-Layer Compositing** - Clip-based Layer-Stack mit Blend Modes (Normal, Multiply, Screen, Overlay, Add, Subtract)
- 🎨 **Layer Effects** - Individuelle Effect-Chains pro Layer
- 📊 **Layer Opacity** - 0-100% Transparenz-Kontrolle pro Layer
- 🎞️ **Video Converter** - FFmpeg-basierter Konverter mit HAP Codec Support (DXT1, DXT5, BC7), H.264, Batch-Verarbeitung, Loop-Optimierung

### Art-Net & DMX
- 🌐 **Art-Net Output** - Multi-Universe Support mit automatischer Grenzlogik
- 🎨 **RGB Channel Mapping** - Konfigurierbare Kanal-Reihenfolge pro Universum (RGB, GRB, BGR, etc.)
- 📊 **Delta-Encoding** - Intelligente Differenz-Übertragung (50-90% Netzwerk-Reduktion)
- 🏛️ **DMX Input Control** - 9-Kanal Steuerung (Ch1-5: Control, Ch6-9: Video Slots)

### Web Interface
- 📡 **REST API** - Flask-basierte API mit WebSocket, CORS Support
- 🖥️ **Bootstrap GUI** - Canvas Editor + Control Panel + Config Manager + Video Converter
- 🌙 **Dark Mode** - Vollständiges Theme-System mit LocalStorage
- 🛎️ **Toast-Benachrichtigungen** - Theme-aware Notifications
- 🔍 **Canvas-Zoom & Scrollbars** - Zoom per Maus & Buttons, automatische Scrollbalken

### Konfiguration & Verwaltung
- ⚙️ **Dynamic Config UI** - Web-basierte config.json Verwaltung
- 🎨 **Multi-JSON Support** - Flexible Punkte-Konfigurationen mit Validierung
- 💾 **Server-Projektverwaltung** - Projekte speichern/laden/löschen im Backend, Download & Modal-UI
- 📊 **CLI Debug-Modus** - Konfigurierbares Console-Logging (WARNING, INFO, DEBUG)

### Performance (v2.2 Optimierungen)
- ⚡ **NumPy-Vektorisierung** - 10-50x schnellere Stream-Loops (40-60% CPU-Reduktion)
- 💾 **Zero-Copy Frames** - Redundante Frame-Kopien entfernt (15-20% CPU-Reduktion)
- 🎨 **Hardware Channel-Reorder** - NumPy fancy indexing statt Loops (5-10% CPU-Reduktion)
- 📊 **Delta-Encoding** - Nur geänderte Pixel übertragen (50-90% Netzwerk-Reduktion)
- 🛡️ **Memory-Safe Recording** - Deque-basiert, verhindert 195MB Memory-Leak
- 🎯 **Event-Sync** - Sofortige Pause/Resume ohne Polling-Delay
- 🔒 **Lock-Free Stats** - Atomic Counters (2-5% CPU-Reduktion)
- 🏛️ **Gradient Cache** - Pattern-Caching spart 1-3ms pro Generation

### Architektur (v2.3 - Unified API & Dual-Player)
- 🏗️ **Unified API** - Konsistente REST-Endpoints mit UUID-basierten Clips
- 👥 **Dual-Player System** - Video Player (Preview) + Art-Net Player (Output) unabhängig
- 🎯 **ClipRegistry** - Zentrale UUID-basierte Clip-Verwaltung mit Effekt-Speicherung
- 🔄 **Frame Source Pattern** - Austauschbare Frame-Quellen (Video, Script, Stream)
- 🔌 **Hot Source Switching** - Wechsel zwischen Videos/Scripts ohne Player-Neustart
- 🧩 **Extensible** - Einfaches Hinzufügen neuer Source-Typen (ImageSequence, LiveStream, etc.)
- ♻️ **Code Reduction** - 90% weniger Duplikation, deprecated Code entfernt
- ⚡ **Lazy Initialization** - VideoSource erst beim Play laden (verhindert FFmpeg-Konflikte)

## Installation

```bash
# Abhängigkeiten installieren
pip install -r requirements.txt

# Optional: Python Environment konfigurieren
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```

**Hinweis:** Ab Version 2.4 benötigt Flux **keine MSVC Build Tools** mehr für Windows!  
Audio-Playback nutzt jetzt PyAV + sounddevice (bereits in dependencies enthalten).

## Schnellstart

```bash
# Hauptanwendung starten
python src/main.py

# REST API starten (im CLI)
> api start

# Web-Interfaces öffnen
# http://localhost:5000 - Canvas Editor (Bootstrap GUI)
# http://localhost:5000/controls - Control Panel
# http://localhost:5000/converter - Video Converter
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

### Generator Plugins (replaces legacy Script Generator)
- See [PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) for generator plugin development
- Legacy script commands (`script:`, `load script:`) now show deprecation warnings
- Use generator plugins instead for procedural content generation

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
- `delta [on|off]` - Delta-Encoding umschalten
- `delta status` - Delta-Encoding Status anzeigen
- `delta threshold <n>` - Änderungs-Schwellwert setzen
- `delta interval <n>` - Full-Frame Sync-Intervall setzen

### System & Debugging
- `debug [on|off]` - CLI Debug-Modus (Console-Logging Level)
- `debug verbose` - Verbose-Modus (alle Meldungen inkl. DEBUG)
- `debug status` - Aktuelles Log-Level anzeigen
- `status` - Player-Status
- `info` - Detaillierte Informationen
- `stats` - Live-Statistiken

### REST API
- `api start [port]` - Server starten (Standard: 5000)
- `api stop` - Server stoppen

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

### Layer Management (Compositing)
- `GET /api/clips/{clip_id}/layers` - Alle Layers eines Clips (inkl. Layer 0)
- `POST /api/clips/{clip_id}/layers/add` - Layer hinzufügen - Body: `{"source_type": "video", "source_path": "overlay.mp4", "blend_mode": "screen", "opacity": 70.0}`
- `PATCH /api/clips/{clip_id}/layers/{layer_id}` - Layer aktualisieren - Body: `{"opacity": 50.0, "blend_mode": "multiply"}`
- `DELETE /api/clips/{clip_id}/layers/{layer_id}` - Layer entfernen
- `PUT /api/clips/{clip_id}/layers/reorder` - Layer-Reihenfolge ändern - Body: `{"layer_order": [1, 3, 2]}`

**Blend Modes:** `normal`, `multiply`, `screen`, `overlay`, `add`, `subtract`

**Compositing-Reihenfolge:** Layer 0 (Base) → Layer 1 → Layer 2 → ... (bottom to top)

### Generator Plugins (legacy script endpoints deprecated)
- `GET /api/scripts` - Liste aller Scripts (deprecated, use generator plugins)
- `POST /api/load_generator` - Load generator plugin (replaces /api/load_script)
- See [PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) for generator plugin API

### Art-Net
- `POST /api/blackout` - Blackout aktivieren
- `POST /api/test` - Body: `{"color": "red"}`
- `GET /api/local_ips` - Verfügbare lokale IPs
- `POST /api/ip` - Body: `{"ip": "192.168.1.11"}`
- `GET /api/artnet/info` - Art-Net Status inkl. Delta-Encoding
- `POST /api/artnet/delta-encoding` - Body: `{"enabled": true, "threshold": 8, "full_frame_interval": 30}`

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

### Video Converter
- `GET /api/converter/status` - FFmpeg-Verfügbarkeit prüfen
- `GET /api/converter/formats` - Verfügbare Output-Formate (HAP, HAP Alpha, HAP Q, H.264, H.264 NVENC)
- `POST /api/converter/info` - Video-Metadaten abrufen (ffprobe)
- `POST /api/converter/convert` - Einzelne Datei konvertieren
- `POST /api/converter/batch` - Batch-Konvertierung mit Glob-Pattern
- `GET /api/converter/canvas-size` - Canvas-Größe aus config.json laden

## Projektstruktur

```
Py_artnet/
├── src/
│   ├── main.py                    # Haupteinstiegspunkt
│   ├── modules/
│   │   ├── player.py              # Unified Media Player with Layer Support
│   │   ├── frame_source.py        # Frame Source Abstraction (VideoSource, GeneratorSource)
│   │   ├── clip_registry.py       # UUID-based Clip Management with Layers
│   │   ├── api_clip_layers.py     # Layer Management API
│   │   ├── video_converter.py     # FFmpeg Video Converter (HAP, H.264)
│   │   ├── api_converter.py       # Converter REST API
│   │   ├── script_generator.py    # Script Loader & Manager
│   │   ├── points_loader.py       # Points-JSON Parser
│   │   ├── cache_manager.py       # RGB Cache Manager
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
│       ├── config.html            # Dynamic Config Manager
│       ├── converter.html         # Video Converter UI
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
    "extensions": [".mp4", ".avi", ".mov", ".mkv", ".wmv"],
    "max_per_channel": 255,
    "default_fps": null,
    "default_brightness": 100,
    "default_speed": 1.0
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

## Generator Plugins (v2.3.7+)

> **⚠️ DEPRECATED:** Legacy Script Generator (ScriptSource) has been replaced by the Generator Plugin system in v2.3.7.
> 
> Old script loading commands (`script:`, `load script:`, `/api/load_script`) now return deprecation warnings.
> 
> **Migration:** Use generator plugins instead. See [PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) for details.

Prozedural content generation is now handled by generator plugins, which provide:
- **Plugin Architecture**: Standardized plugin system with metadata, parameters, and lifecycle hooks
- **Effect Chaining**: Generators can be combined with effect plugins for complex visuals
- **Dynamic Loading**: Hot-swap generators at runtime
- **Parameter Control**: Real-time parameter adjustment via API
- **Better Integration**: Full support for unified player API and effect pipeline

### Migration from Scripts to Generators

**Old (Deprecated):**
```bash
> scripts list              # DEPRECATED
> script:rainbow_wave       # DEPRECATED
POST /api/load_script       # DEPRECATED
```

**New (Generator Plugins):**
```bash
GET  /api/plugins/generators                    # List all generator plugins
POST /api/player/video/load_generator          # Load generator plugin
POST /api/player/video/effects/params          # Adjust generator parameters
```

### Creating Generator Plugins

Generator plugins follow the standardized plugin architecture. Create a new plugin in `src/plugins/generators/`:

```python
from plugins.plugin_base import PluginBase, PluginMetadata, PluginParameter
import numpy as np

class MyGeneratorPlugin(PluginBase):
    def __init__(self):
        super().__init__(
            metadata=PluginMetadata(
                name="My Generator",
                category="generator",
                description="Generates procedural content",
                version="1.0.0"
            ),
            parameters=[
                PluginParameter("speed", float, 1.0, 0.1, 5.0)
            ]
        )
    
    def process_frame(self, frame_data, frame_number, **kwargs):
        height, width = self.height, self.width
        output = np.zeros((height, width, 3), dtype=np.uint8)
        # ... generate graphics ...
        return output
```

See [PLUGIN_SYSTEM.md](docs/PLUGIN_SYSTEM.md) and [NEW_PLUGINS.md](docs/NEW_PLUGINS.md) for detailed documentation.

## Hardware-Beschleunigung

Automatische Erkennung und Nutzung von:
- **NVDEC** (NVIDIA)
- **QSV** (Intel Quick Sync)
- **VAAPI** (Linux)
- **MMAL** (Raspberry Pi)

Status wird beim Start in der Konsole ausgegeben
