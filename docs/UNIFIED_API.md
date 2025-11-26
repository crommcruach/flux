# Unified Player API v2.0

## 🎯 Konzept

Die neue Unified API bietet eine konsistente, UUID-basierte Schnittstelle für Clip-Management und Effekte über beide Player-Instanzen (Video Preview und Art-Net Output).

## 🏗️ Architektur

### Dual-Player System

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   Video Player          │         │   Art-Net Player        │
│   (player_id="video")   │         │   (player_id="artnet")  │
├─────────────────────────┤         ├─────────────────────────┤
│ enable_artnet = False   │         │ enable_artnet = True    │
│ Preview only            │         │ LED Output              │
│                         │         │                         │
│ current_clip_id:        │         │ current_clip_id:        │
│ "abc-123-..."           │         │ "def-456-..."           │
└─────────────────────────┘         └─────────────────────────┘
           │                                   │
           └───────────────┬───────────────────┘
                           │
                ┌──────────▼──────────┐
                │   ClipRegistry      │
                │   (Singleton)       │
                ├─────────────────────┤
                │ clip_id → {         │
                │   player_id,        │
                │   path,             │
                │   effects: [...]    │
                │ }                   │
                └─────────────────────┘
```

### ClipRegistry

**Zentrale Clip-Verwaltung mit UUID-basierter Identifikation:**

```python
{
    "da6eebb1-e2f0-4c0e-bbf5-25727e579bbb": {
        "player_id": "video",
        "absolute_path": "C:/Videos/myvideo.mp4",
        "relative_path": "myvideo.mp4",
        "metadata": {},
        "effects": [
            {
                "plugin_id": "blur",
                "metadata": {...},
                "parameters": {"radius": 5},
                "instance": <PluginInstance>  # Lazy-loaded
            }
        ]
    }
}
```

## 📡 API Endpoints

### URL-Struktur

```
/api/player/{player_id}/clip/{clip_id}/{action}
```

- `player_id`: `"video"` oder `"artnet"`
- `clip_id`: UUID (z.B. `"da6eebb1-e2f0-4c0e-bbf5-25727e579bbb"`)
- `action`: `effects/add`, `effects/clear`, `play`, etc.

### Clip Loading

```http
POST /api/player/video/clip/load
Content-Type: application/json

{
  "video_path": "myvideo.mp4"
}
```

**Response:**
```json
{
  "success": true,
  "clip_id": "da6eebb1-e2f0-4c0e-bbf5-25727e579bbb",
  "player_id": "video",
  "relative_path": "myvideo.mp4"
}
```

### Effect Management

#### Add Effect
```http
POST /api/player/video/clip/{clip_id}/effects/add
Content-Type: application/json

{
  "plugin_id": "blur"
}
```

#### Update Parameter
```http
PUT /api/player/video/clip/{clip_id}/effects/0/parameter
Content-Type: application/json

{
  "name": "radius",
  "value": 10
}
```

#### List Effects
```http
GET /api/player/video/clip/{clip_id}/effects
```

**Response:**
```json
{
  "success": true,
  "clip_id": "da6eebb1-e2f0-4c0e-bbf5-25727e579bbb",
  "effects": [
    {
      "plugin_id": "blur",
      "metadata": {...},
      "parameters": {"radius": 10}
    }
  ]
}
```

#### Remove Effect
```http
DELETE /api/player/video/clip/{clip_id}/effects/0
```

#### Clear All Effects
```http
POST /api/player/video/clip/{clip_id}/effects/clear
```

### Playback Control

```http
POST /api/player/video/play
POST /api/player/video/pause
POST /api/player/video/stop
```

## 🔄 Frontend Integration

### State Management

```javascript
// State-Variablen
let selectedClipId = null;           // UUID vom Server
let selectedClipPath = null;         // Nur für Display
let selectedClipPlayerType = null;   // "video" oder "artnet"

// Video laden
const response = await fetch('/api/player/video/clip/load', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({video_path: 'myvideo.mp4'})
});
const data = await response.json();
selectedClipId = data.clip_id;
selectedClipPath = data.relative_path;
selectedClipPlayerType = 'video';
```

### Effect Operations

```javascript
// Effekt hinzufügen
await fetch(`/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/add`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({plugin_id: 'blur'})
});

// Parameter aktualisieren
await fetch(`/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/0/parameter`, {
    method: 'PUT',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: 'radius', value: 10})
});

// Effekt entfernen
await fetch(`/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/0`, {
    method: 'DELETE'
});
```

## ⚡ Performance

### Lazy Initialization

VideoSource wird erst beim ersten `play()` initialisiert, nicht im Constructor:

```python
class Player:
    def __init__(self, frame_source, ...):
        self.source = frame_source
        self.source_initialized = False  # Nicht sofort öffnen!
    
    def start(self):
        if not self.source_initialized:
            self.source.initialize()  # Jetzt FFmpeg öffnen
            self.source_initialized = True
```

**Vorteil:** Verhindert FFmpeg `async_lock assertion failed` wenn beide Player dieselbe Datei laden.

### Effect Processing

Effekte werden bei jedem Frame aus dem ClipRegistry geladen:

```python
def _process_frame(self, frame):
    if self.clip_registry and self.current_clip_id:
        clip_effects = self.clip_registry.get_clip_effects(self.current_clip_id)
        
        for effect_data in clip_effects:
            # Lazy instance creation
            if 'instance' not in effect_data:
                effect_data['instance'] = create_plugin_instance(...)
            
            # Update parameters (live parameter changes!)
            plugin = effect_data['instance']
            for param, value in effect_data['parameters'].items():
                setattr(plugin, param, value)
            
            # Process frame
            frame = plugin.process_frame(frame)
    
    return frame
```

**Vorteil:** Parameter-Updates via API werden sofort ohne Neustart angewendet.

## 🔍 Debugging

### Logging

```python
logger.info(f"✅ [{player_id}] Loaded clip: {filename} (clip_id={clip_id})")
logger.debug(f"[{player_name}] Applying {len(clip_effects)} clip effects for clip_id={clip_id}")
logger.debug(f"🔧 Clip effect parameter updated: {clip_id}[{index}].{param_name} = {param_value}")
```

### Verify Clip Loading

```bash
# Check if clip is registered
curl http://localhost:5000/api/player/video/clip/current

# Check clip effects
curl http://localhost:5000/api/player/video/clip/{clip_id}/effects
```

## 🚀 Migration von Legacy API

### Alte API (Deprecated)
```javascript
// Path-basiert, separate Endpoints
POST /api/video/load
POST /api/artnet/playback/load
POST /api/effects/add_clip_effect  // Body: {clip_path, plugin_id}
```

### Neue API (v2.0)
```javascript
// UUID-basiert, unified Endpoints
POST /api/player/video/clip/load
POST /api/player/artnet/clip/load
POST /api/player/{player_id}/clip/{clip_id}/effects/add  // Body: {plugin_id}
```

## ✅ Vorteile

1. **Keine Pfad-Kollisionen:** UUIDs statt Pfade
2. **Unabhängige Player:** Beide Player können verschiedene Clips mit verschiedenen Effekten
3. **Konsistente API:** Gleiche URL-Struktur für beide Player
4. **Live Parameter-Updates:** Änderungen sofort ohne Restart
5. **Saubere Architektur:** ClipRegistry als Single Source of Truth
6. **Einfaches Debugging:** Klare Zuordnung Clip-ID → Player → Effekte

## 📝 Beispiel-Workflow

```bash
# 1. Video in Video-Player laden
curl -X POST http://localhost:5000/api/player/video/clip/load \
  -H "Content-Type: application/json" \
  -d '{"video_path": "myvideo.mp4"}'
# → clip_id: "abc-123-..."

# 2. Video in Art-Net-Player laden (DASSELBE Video!)
curl -X POST http://localhost:5000/api/player/artnet/clip/load \
  -H "Content-Type: application/json" \
  -d '{"video_path": "myvideo.mp4"}'
# → clip_id: "def-456-..." (UNTERSCHIEDLICHE UUID!)

# 3. Blur nur zu Video-Player hinzufügen
curl -X POST http://localhost:5000/api/player/video/clip/abc-123-.../effects/add \
  -H "Content-Type: application/json" \
  -d '{"plugin_id": "blur"}'

# 4. Pixelate nur zu Art-Net-Player hinzufügen
curl -X POST http://localhost:5000/api/player/artnet/clip/def-456-.../effects/add \
  -H "Content-Type: application/json" \
  -d '{"plugin_id": "pixelate"}'

# Ergebnis: Beide Player spielen dasselbe Video mit VERSCHIEDENEN Effekten!
```
