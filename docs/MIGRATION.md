# Migration Guide: Legacy API → Unified API v2.0

## Breaking Changes in v2.3.0

### Player-Code

#### Entfernt
```python
# DEPRECATED - Nicht mehr verfügbar
player.effect_chain
player.clip_effects
player.add_effect(plugin_id)
player.remove_effect(index)
player.clear_effects()
```

#### Ersetzt durch
```python
# Player-Level Effects (für alle Videos)
player.add_effect_to_chain(plugin_id, config, chain_type='video')
player.remove_effect_from_chain(index, chain_type='video')

# Clip-Level Effects (über API/ClipRegistry)
clip_registry.add_effect_to_clip(clip_id, effect_data)
clip_registry.get_clip_effects(clip_id)
```

### API-Endpoints

#### Video Player - Alte API
```http
POST /api/video/load
Request: {"video": "myvideo.mp4"}

POST /api/effects/add_clip_effect
Request: {"clip_path": "myvideo.mp4", "plugin_id": "blur"}

GET /api/effects/get_clip_effects
Request: {"clip_path": "myvideo.mp4"}
```

#### Video Player - Neue API (v2.0)
```http
POST /api/player/video/clip/load
Request: {"video_path": "myvideo.mp4"}
Response: {"clip_id": "abc-123-..."}

POST /api/player/video/clip/abc-123-.../effects/add
Request: {"plugin_id": "blur"}

GET /api/player/video/clip/abc-123-.../effects
Response: {"effects": [...]}
```

#### Art-Net Player - Alte API
```http
POST /api/artnet/playback/load
Request: {"video_path": "myvideo.mp4"}

POST /api/artnet/playback/effects/add
Request: {"clip_path": "myvideo.mp4", "plugin_id": "blur"}
```

#### Art-Net Player - Neue API (v2.0)
```http
POST /api/player/artnet/clip/load
Request: {"video_path": "myvideo.mp4"}
Response: {"clip_id": "def-456-..."}

POST /api/player/artnet/clip/def-456-.../effects/add
Request: {"plugin_id": "blur"}
```

### Frontend-Code

#### Alte Implementation
```javascript
// State: Path-basiert
let selectedClip = null;  // "myvideo.mp4"
let selectedClipPlayerType = 'video';

// Video laden
const response = await fetch('/api/video/load', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({video: 'myvideo.mp4'})
});
selectedClip = 'myvideo.mp4';

// Effekt hinzufügen
await fetch('/api/effects/add_clip_effect', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        clip_path: selectedClip,
        plugin_id: 'blur'
    })
});

// Effekte laden
const effects = await fetch('/api/effects/get_clip_effects', {
    method: 'GET',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({clip_path: selectedClip})
});
```

#### Neue Implementation (v2.0)
```javascript
// State: UUID-basiert
let selectedClipId = null;           // "abc-123-..."
let selectedClipPath = null;         // "myvideo.mp4" (nur für Display)
let selectedClipPlayerType = 'video';

// Video laden
const response = await fetch('/api/player/video/clip/load', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({video_path: 'myvideo.mp4'})
});
const data = await response.json();
selectedClipId = data.clip_id;       // UUID vom Server!
selectedClipPath = data.relative_path;

// Effekt hinzufügen
await fetch(`/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/add`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({plugin_id: 'blur'})
});

// Effekte laden
const effects = await fetch(
    `/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects`
);
```

## Vorteile der neuen API

### 1. Keine Pfad-Kollisionen
**Problem (Alt):** Beide Player laden `myvideo.mp4` → Effekte werden verwechselt

**Lösung (Neu):** Beide Player erhalten unterschiedliche UUIDs für denselben Pfad
```
Video Player:  clip_id = "abc-123-..."  (myvideo.mp4)
Art-Net Player: clip_id = "def-456-..."  (myvideo.mp4)
→ Effekte werden getrennt gespeichert!
```

### 2. Konsistente URL-Struktur
**Alt:** Verschiedene Endpoint-Muster für Video/Art-Net
```
/api/video/load
/api/artnet/playback/load
/api/effects/add_clip_effect
```

**Neu:** Einheitliches Schema
```
/api/player/{player_id}/clip/{clip_id}/{action}
```

### 3. RESTful Design
**Alt:** Mischung aus POST/GET mit Bodys
```http
GET /api/effects/get_clip_effects
Body: {"clip_path": "..."}  ← GET mit Body ist unüblich
```

**Neu:** Korrekte REST-Semantik
```http
GET /api/player/video/clip/abc-123-.../effects
# Keine Body bei GET
```

### 4. Klare Zuständigkeiten
**Alt:** `clip_path` in jedem Request mitschicken
```javascript
// Bei jedem API-Call
{clip_path: selectedClip, plugin_id: 'blur'}
```

**Neu:** Clip-ID in URL, nur relevante Daten im Body
```javascript
// URL enthält Kontext
PUT /api/player/video/clip/{clip_id}/effects/0/parameter
Body: {name: 'radius', value: 10}
```

## Automatische Migration

### Backend Compatibility Layer (Optional)

Falls alte API-Calls noch unterstützt werden sollen:

```python
# api_legacy_wrapper.py (zu erstellen)

@app.route('/api/video/load', methods=['POST'])
def legacy_video_load():
    """Wrapper für alte Video-Load API."""
    data = request.get_json()
    video_path = data.get('video')
    
    # Redirect zu neuer API
    return redirect(
        url_for('load_clip', player_id='video'),
        code=307  # Temporary Redirect mit POST
    )
```

### Frontend Feature Detection

```javascript
// Check if new API is available
async function detectAPI() {
    try {
        const response = await fetch('/api/player/video/clip/current');
        return response.ok ? 'v2' : 'v1';
    } catch {
        return 'v1';
    }
}

// Use appropriate API
const apiVersion = await detectAPI();
if (apiVersion === 'v2') {
    // Use new unified API
} else {
    // Fallback to legacy API
}
```

## Checkliste Migration

- [ ] **Backend aktualisiert** (bereits in v2.3.0)
  - [x] ClipRegistry erstellt
  - [x] api_player_unified.py implementiert
  - [x] Player erhält clip_registry
  - [x] Deprecated Code entfernt

- [ ] **Frontend aktualisiert**
  - [x] State-Variablen: `selectedClipId` statt `selectedClip`
  - [x] API-Calls auf neue Endpoints umgestellt
  - [x] Video-Load speichert clip_id
  - [x] Effekt-Calls verwenden clip_id in URL
  - [ ] Testen: Video laden, Effekte hinzufügen, Parameter ändern

- [ ] **Dokumentation**
  - [x] API.md aktualisiert
  - [x] ARCHITECTURE.md aktualisiert
  - [x] CHANGELOG.md aktualisiert
  - [x] UNIFIED_API.md erstellt
  - [x] MIGRATION.md erstellt (diese Datei)

- [ ] **Testing**
  - [x] Backend-Tests: test_unified_api.py (20/20 passed)
  - [ ] Frontend-Tests: Browser-Testing mit beiden Playern
  - [ ] Integration-Tests: Video laden, Effekte, Parameter-Updates

## Troubleshooting

### Clip-Effekte werden nicht angewendet

**Symptom:** Effekte im Frontend sichtbar, aber Video unverändert

**Ursache:** Player lädt nicht aus ClipRegistry

**Lösung:** Checke ob:
1. `player.clip_registry` gesetzt ist (Constructor)
2. `player.current_clip_id` gesetzt wird beim Load
3. Player liest aus `clip_registry.get_clip_effects(current_clip_id)`

### FFmpeg async_lock Fehler

**Symptom:** `assertion "!pthread_mutex_lock(mutex)" failed`

**Ursache:** Beide Player öffnen dieselbe Datei gleichzeitig

**Lösung:** Lazy Initialization aktiviert (bereits in v2.3.0)
```python
# player.py
self.source_initialized = False  # Im Constructor

# Erst beim play() öffnen
if not self.source_initialized:
    self.source.initialize()
```

### Alte API-Calls schlagen fehl

**Symptom:** 404 Not Found für `/api/video/load`

**Ursache:** Alte Endpoints existieren noch (für Backward Compatibility)

**Lösung:** 
1. Frontend auf neue API migrieren (empfohlen)
2. Oder: Compatibility Layer erstellen (siehe oben)

## Support

Bei Fragen zur Migration:
1. Check `docs/UNIFIED_API.md` für API-Details
2. Check `docs/ARCHITECTURE.md` für System-Architektur
3. Check `tests/test_unified_api.py` für Beispiele
