# Flux - Architektur & Verbesserungsvorschläge

## ✨ Aktuelle Architektur v2.0 (November 2025)

### 🏗️ Unified Player Architecture mit UUID-basiertem Clip-Management

**Implementiert:** 2025-11-26

#### Kernsystem

```
src/modules/
├── Core Player System
│   ├── player.py              # Unified Player (beide Instanzen: Video + Art-Net)
│   ├── player_manager.py      # Container für beide Player-Instanzen
│   ├── clip_registry.py       # UUID-basiertes Clip-Management (NEU)
│   ├── frame_source.py        # VideoSource + ScriptSource Interfaces
│   └── artnet_manager.py      # Art-Net Output
│
├── Unified API (NEU v2.0)
│   ├── api_player_unified.py  # /api/player/{player_id}/... Endpoints
│   │   ├── Clip Management: load, current
│   │   ├── Effect Management: add, remove, update, clear
│   │   └── Playback Control: play, pause, stop
│   └── Legacy APIs (für Backward Compatibility)
│       ├── api_videos.py      # Video Player spezifische Endpoints
│       └── api_artnet_playback.py  # Art-Net Player spezifische Endpoints
│
├── Effect System
│   ├── plugin_manager.py      # Plugin-Loading & Registry
│   └── plugins/effects/       # Effect-Plugins (blur, pixelate, etc.)
│
└── REST API
    ├── rest_api.py            # Main Flask Server
    ├── api_routes.py          # General Routes
    ├── api_config.py          # Config Management
    └── ...
```

#### Dual-Player Architektur

**Video Player (Preview):**
- `player_id = "video"`
- `enable_artnet = False`
- Nur für Browser-Preview
- Keine Art-Net Ausgabe

**Art-Net Player (Output):**
- `player_id = "artnet"`
- `enable_artnet = True`
- Art-Net Output zu LEDs
- Separates Video-Processing

**Vorteile:**
- ✅ Beide Player können unterschiedliche Videos abspielen
- ✅ Unabhängige Clip-Effekte pro Player
- ✅ Keine gegenseitige Beeinflussung
- ✅ Preview ohne Art-Net Output möglich

#### ClipRegistry System

**Konzept:**
```python
ClipRegistry = {
    "clip_id": {
        "player_id": "video",  # Welcher Player hat den Clip geladen
        "absolute_path": "/full/path/video.mp4",
        "relative_path": "video.mp4",
        "metadata": {},
        "effects": [  # Clip-spezifische Effekte
            {
                "plugin_id": "blur",
                "metadata": {...},
                "parameters": {"radius": 5}
            }
        ]
    }
}
```

**Features:**
- UUID-basierte Clip-Identifikation (keine Pfad-Kollisionen)
- Clip → Player Mapping (ein Clip pro Player)
- Effekt-Speicherung pro Clip (persistent während Clip geladen ist)
- Singleton Pattern für globalen Zugriff

**API-Flow:**
1. Frontend: `POST /api/player/video/clip/load` → Backend registriert Clip, gibt UUID zurück
2. Frontend: `POST /api/player/video/clip/{uuid}/effects/add` → Effekt wird im Registry gespeichert
3. Player: Lädt Effekte aus `clip_registry.get_clip_effects(current_clip_id)` bei jedem Frame
4. Parameter-Updates werden live in Registry aktualisiert → Player liest bei jedem Frame neu

#### Lazy Initialization

**Problem:** Beide Player öffnen dieselbe Video-Datei → FFmpeg `async_lock assertion failed`

**Lösung:** VideoSource wird erst beim ersten `play()` initialisiert
```python
class Player:
    def __init__(self, frame_source, ...):
        self.source = frame_source
        self.source_initialized = False  # NICHT sofort initialisieren
    
    def start(self):
        if not self.source_initialized:
            self.source.initialize()  # Erst jetzt FFmpeg öffnen
            self.source_initialized = True
```

---

## Architektur (Nach Refactoring 2024)

### Module-Struktur

```
src/modules/
├── Core Player
│   ├── video_player.py       # Video-Wiedergabe (945 Zeilen → verbessert)
│   ├── script_player.py      # Script-Wiedergabe (320 Zeilen → verbessert)
│   └── artnet_manager.py     # Art-Net Output (240 Zeilen)
│
├── Shared Components (NEU)
│   ├── points_loader.py      # Points-JSON Parser (120 Zeilen)
│   ├── cache_manager.py      # RGB Cache Manager (200 Zeilen)
│   └── script_generator.py   # Script Loader (85 Zeilen)
│
├── REST API
│   ├── rest_api.py           # Main API Server (360 Zeilen)
│   ├── api_routes.py         # Playback/Settings Routes
│   ├── api_videos.py         # Video Management
│   ├── api_points.py         # Points Management
│   ├── api_projects.py       # Project Management
│   ├── api_console.py        # Console Log
│   ├── api_config.py         # Config Management (NEU)
│   └── cache_commands.py     # Cache Commands
│
├── Input/Output
│   └── dmx_controller.py     # DMX Input (240 Zeilen)
│
└── Utilities
    ├── cli_handler.py        # CLI Commands
    ├── validator.py          # JSON Validation
    ├── logger.py             # Logging System
    ├── constants.py          # Constants
    └── utils.py              # Helper Functions
```

## Durchgeführtes Refactoring

### 1. ✅ PointsLoader-Modul erstellt

**Problem:** VideoPlayer und ScriptPlayer hatten identischen Code (90+ Zeilen) zum Laden von Points-JSON.

**Lösung:** 
- Neues Modul `points_loader.py`
- Statische Methode `PointsLoader.load_points()`
- Unterstützt Validierung und Universe-Mapping
- Code-Reduktion: ~180 Zeilen eliminiert

**Vorteile:**
- Single Source of Truth
- Einfachere Wartung
- Konsistente Fehlerbehandlung

### 2. ✅ CacheManager-Modul erstellt

**Problem:** Cache-Logik war fest in VideoPlayer verdrahtet (150+ Zeilen).

**Lösung:**
- Neues Modul `cache_manager.py`
- Klasse `CacheManager` mit klarer API
- Methoden: `load_cache()`, `save_cache()`, `clear_cache()`, `get_cache_stats()`
- Unterstützt msgpack-basiertes Caching

**Vorteile:**
- Cache-Logik wiederverwendbar
- VideoPlayer deutlich schlanker
- Cache-Statistiken zentral verfügbar
- Einfacher zu testen

### 3. ✅ API-Module aufgeräumt

**Problem:** `rest_api_backup.py` war veraltet und nicht verwendet.

**Lösung:**
- Backup-Datei gelöscht
- Module-Exports aktualisiert
- Neue Module (PointsLoader, CacheManager) exportiert

## Architektur-Verbesserungen

### ✅ Umgesetzte Verbesserungen

1. **Modulare Code-Organisation**
   - Gemeinsamer Code in wiederverwendbare Module extrahiert
   - Klare Verantwortlichkeiten pro Modul
   - Reduzierte Code-Duplikation

2. **Separation of Concerns**
   - Points-Loading separiert
   - Cache-Management separiert
   - API-Routen in eigene Module aufgeteilt

3. **Verbesserte Wartbarkeit**
   - Kleinere, fokussierte Module
   - Einfachere Unit-Tests möglich
   - Bessere Code-Lesbarkeit

## Vorschläge für zukünftige Verbesserungen

### 1. PlayerBase Abstraktion (Optional)

**Idee:** Gemeinsame Basis-Klasse für VideoPlayer und ScriptPlayer

```python
# src/modules/player_base.py
class PlayerBase:
    """Gemeinsame Basis für Video- und Script-Player."""
    
    def __init__(self, points_json_path, target_ip, start_universe, config):
        # Gemeinsame Initialisierung
        self._load_points(points_json_path)
        self._init_artnet(target_ip, start_universe)
        self._init_controls()
    
    def _load_points(self, points_json_path):
        """Lädt Points-Konfiguration."""
        points_data = PointsLoader.load_points(points_json_path)
        self.point_coords = points_data['point_coords']
        # ...
    
    def _init_artnet(self, target_ip, start_universe):
        """Initialisiert Art-Net Manager."""
        self.artnet_manager = ArtNetManager(...)
    
    # Gemeinsame Methoden: play(), stop(), pause(), etc.
```

**Vorteile:**
- Noch weniger Code-Duplikation
- Einheitliche Player-Schnittstelle
- Einfacher neue Player-Typen hinzuzufügen

**Nachteile:**
- Mehr Abstraktion (kann Komplexität erhöhen)
- Erfordert größeres Refactoring

**Empfehlung:** Erst umsetzen wenn 3+ Player-Typen existieren

### 2. Filter-Pipeline System

**Idee:** Modulares Filter-System für Video/Script-Frames

```python
# src/modules/filters/
├── filter_base.py         # BaseFilter Klasse
├── brightness_filter.py   # Helligkeit
├── hue_rotation_filter.py # Farbverschiebung
├── blur_filter.py         # Weichzeichnung
└── invert_filter.py       # Farbinvertierung

# Verwendung:
player.add_filter(BrightnessFilter(0.8))
player.add_filter(HueRotationFilter(45))
```

**Vorteile:**
- Flexible Effekt-Ketten
- Wiederverwendbare Filter
- Einfach erweiterbar

**Implementierung:**
```python
class FilterBase:
    def apply(self, frame: np.ndarray) -> np.ndarray:
        raise NotImplementedError

class BrightnessFilter(FilterBase):
    def __init__(self, factor: float):
        self.factor = factor
    
    def apply(self, frame):
        return (frame * self.factor).clip(0, 255).astype(np.uint8)
```

### 3. Plugin-System für Scripts

**Idee:** Hot-Reloading und Parameterisierung von Scripts

```python
# scripts/plugin_base.py
class ScriptPlugin:
    """Base class for procedural scripts."""
    
    # Parameter-Definition
    PARAMETERS = {
        'speed': {'type': 'float', 'default': 1.0, 'min': 0.1, 'max': 5.0},
        'color': {'type': 'color', 'default': '#FF0000'}
    }
    
    def __init__(self):
        self.params = self._init_params()
    
    def set_parameter(self, name, value):
        """Ändere Parameter zur Laufzeit."""
        self.params[name] = value
    
    def generate_frame(self, frame_number, width, height, time, fps):
        raise NotImplementedError
```

**Vorteile:**
- Parameter zur Laufzeit änderbar
- UI kann automatisch generiert werden
- Script-Presets speicherbar

### 4. Echtzeit-Performance-Monitoring

**Idee:** Detailliertes Performance-Tracking

```python
# src/modules/performance_monitor.py
class PerformanceMonitor:
    """Überwacht Performance-Metriken."""
    
    def track_frame_time(self, duration):
        """Trackt Frame-Generierungszeit."""
        
    def track_artnet_send(self, duration):
        """Trackt Art-Net Sendezeit."""
    
    def get_metrics(self):
        return {
            'avg_frame_time_ms': ...,
            'avg_fps': ...,
            'dropped_frames': ...,
            'memory_usage_mb': ...
        }
```

**Nutzen:**
- Performance-Probleme identifizieren
- Optimierungen validieren
- Debug-Informationen

### 5. Verbesserte Error-Handling

**Idee:** Einheitliches Exception-Handling

```python
# src/modules/exceptions.py
class FluxException(Exception):
    """Base exception for Flux."""
    pass

class VideoLoadError(FluxException):
    """Fehler beim Laden von Videos."""
    pass

class PointsLoadError(FluxException):
    """Fehler beim Laden von Points-JSON."""
    pass

class ArtNetError(FluxException):
    """Fehler bei Art-Net Kommunikation."""
    pass
```

**Vorteile:**
- Bessere Fehlerdiagnose
- Spezifische Fehlerbehandlung
- Cleaner Code

### 6. Datenbank für Projekte (Optional)

**Idee:** SQLite statt JSON für Projekte

```python
# src/modules/database.py
class ProjectDatabase:
    """Verwaltet Projekte in SQLite."""
    
    def save_project(self, name, points_data, metadata):
        """Speichert Projekt in DB."""
    
    def load_project(self, name):
        """Lädt Projekt aus DB."""
    
    def search_projects(self, query):
        """Sucht Projekte nach Name/Tags."""
```

**Vorteile:**
- Schnellere Suche
- Metadaten (Tags, Datum, Autor)
- Versionierung möglich

**Nachteile:**
- Mehr Dependencies
- Komplexere Setup

**Empfehlung:** Erst ab 50+ Projekten sinnvoll

### 7. Testing-Infrastruktur

**Idee:** Unit-Tests für kritische Module

```
tests/
├── test_points_loader.py
├── test_cache_manager.py
├── test_script_generator.py
├── test_artnet_manager.py
└── test_video_player.py
```

**Priorität:** Hoch - verhindert Regressionen

### 8. Configuration Schema

**Idee:** JSON-Schema für config.json Validierung

```python
# src/modules/config_schema.py
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["artnet", "video", "paths"],
    "properties": {
        "artnet": {
            "type": "object",
            "required": ["target_ip", "start_universe"],
            "properties": {
                "target_ip": {"type": "string", "pattern": "^\\d+\\.\\d+\\.\\d+\\.\\d+$"},
                "start_universe": {"type": "integer", "minimum": 0, "maximum": 32767}
            }
        }
    }
}
```

**Vorteile:**
- Validierung beim Laden
- Auto-Completion in IDEs
- Dokumentation der Config-Struktur

## Best Practices

### Code-Organisation

1. **Ein Modul = Eine Verantwortlichkeit**
   - PointsLoader: Nur Points-Loading
   - CacheManager: Nur Cache-Verwaltung
   - VideoPlayer: Nur Video-Wiedergabe

2. **Dependency Injection**
   - Module erhalten Dependencies als Parameter
   - Beispiel: `VideoPlayer(cache_manager=cache_mgr)`
   - Erleichtert Testing und Flexibilität

3. **Type Hints verwenden**
   ```python
   def load_points(self, path: str) -> Dict[str, Any]:
       ...
   ```

4. **Logging statt Print**
   ```python
   # Gut
   logger.info("Cache geladen")
   
   # Vermeiden
   print("Cache geladen")
   ```

### Performance

1. **NumPy nutzen statt Python-Loops**
   ```python
   # Gut
   frame = np.zeros((height, width, 3), dtype=np.uint8)
   
   # Vermeiden
   frame = [[[0, 0, 0] for _ in range(width)] for _ in range(height)]
   ```

2. **Cache wo sinnvoll**
   - RGB-Daten (✓ umgesetzt)
   - Berechnete Koordinaten
   - Kompilierte Regex

3. **Profiling nutzen**
   ```python
   import cProfile
   cProfile.run('player.play()')
   ```

### API-Design

1. **RESTful Endpoints**
   - GET für Abfragen
   - POST für Änderungen
   - DELETE für Löschungen

2. **Konsistente Responses**
   ```json
   {
     "status": "success|error",
     "data": {...},
     "message": "Optional message"
   }
   ```

3. **Versionierung**
   - `/api/v1/videos`
   - Ermöglicht Breaking Changes

## Zusammenfassung

### ✅ Umgesetzte Verbesserungen
- PointsLoader-Modul (Code-Reduktion: 180 Zeilen)
- CacheManager-Modul (Code-Reduktion: 150 Zeilen)
- Aufgeräumte Module-Struktur
- Verbesserte Wartbarkeit

### 📋 Empfohlene nächste Schritte

**Kurzfristig (1-2 Wochen):**
1. ✅ Testing-Infrastruktur aufbauen
2. ✅ Config-Schema implementieren
3. ✅ Error-Handling verbessern

**Mittelfristig (1-2 Monate):**
4. Filter-Pipeline System
5. Script-Plugin-System
6. Performance-Monitoring

**Langfristig (bei Bedarf):**
7. PlayerBase Abstraktion
8. Datenbank für Projekte
9. API-Versionierung

### Metriken

**Code-Qualität (vorher → nachher):**
- VideoPlayer: 973 → ~820 Zeilen (-15%)
- ScriptPlayer: 348 → ~270 Zeilen (-22%)
- Code-Duplikation: ~180 Zeilen eliminiert
- Neue Module: +2 (PointsLoader, CacheManager)

**Wartbarkeit:**
- Klare Separation of Concerns
- Wiederverwendbare Komponenten
- Einfacher zu testen
