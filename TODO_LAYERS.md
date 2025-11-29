# Multi-Layer System - Implementation TODO

**Status**: Ready for Implementation  
**Erstellt**: 2025-11-29  
**Geschätzte Zeit**: ~12h

---

## Multi-Layer System - Finale Spezifikation

### Kern-Konzept

**Layer-Stack mit Master-Slave Synchronisation:**
```python
player.layers = [
    Layer(0, VideoSource("bg.mp4"), "normal", 100),      # MASTER
    Layer(1, GeneratorSource("plasma"), "multiply", 50), # SLAVE
    Layer(2, VideoSource("fx.mp4"), "screen", 75)        # SLAVE
]
```

---

## 1. Layer-Synchronisation

### Master (Layer 0):
- Bestimmt Gesamt-Länge und Timing
- Steuert FPS für alle Layers
- Autoplay/Playlist funktioniert normal
- Transitions werden hier angewendet
- Bei Ende: Nächstes Video oder Stop

### Slaves (Layer 1-N):
- Laufen parallel zu Layer 0
- **Automatischer Loop** wenn eigenes Ende erreicht
- **Sequential Frame-Fetching** mit Master-Takt:
  - Alle Sources werden mit Master-FPS abgefragt (get_next_frame())
  - 60 FPS Slave bei 30 FPS Master: Überspringt jeden 2. Frame intern
  - 30 FPS Slave bei 60 FPS Master: Hält Frames doppelt
  - Generatoren: Rendern mit Master-FPS
- Keine eigenen Playlists

**Hinweis**: Phase 1 nutzt simple get_next_frame() Abfrage. Für perfekte Sync bei unterschiedlichen FPS könnte später zeit-basiertes Sampling implementiert werden.

### Beispiel:
```
Layer 0: video.mp4 (10s)      [============]
Layer 1: overlay.mp4 (2s)     [==][==][==][==][==]  ← 5x Loop
Layer 2: plasma (infinite)    [============]         ← Läuft 10s
```

---

## 2. Frame Processing Pipeline

```python
while is_running:
    # 1. Master-Frame
    base = layers[0].source.get_next_frame()
    if base is None:
        → Autoplay oder Stop
    base = apply_layer_effects(layers[0], base)
    
    # 2. Slaves compositen
    for layer in layers[1:]:
        overlay = layer.source.get_next_frame()
        if overlay is None:
            layer.source.reset()  # Auto-Loop!
            overlay = layer.source.get_next_frame()
        
        overlay = apply_layer_effects(layer, overlay)
        
        # Blend
        blend = BlendEffect(layer.blend_mode, layer.opacity)
        base = blend.process_frame(base, overlay)
    
    # 3. Global Effects
    base = apply_brightness_hue(base)
    base = apply_effects(base, 'video')
    base = apply_effects(base, 'artnet')
    
    # 4. DMX Output
    ...
```

---

## 3. API Endpoints

```python
# Layer Management
POST   /api/player/{id}/layers/add
{
    "type": "video",              # oder "generator"
    "path": "overlay.mp4",        # oder generator_id
    "blend_mode": "multiply",     # normal, multiply, screen, add, subtract, overlay
    "opacity": 75.0,              # 0-100
    "parameters": {}              # für Generators
}
→ Returns: {"layer_id": 1}

DELETE /api/player/{id}/layers/{layer_id}

GET    /api/player/{id}/layers
→ Returns: [
    {
        "layer_id": 0,
        "clip_id": "uuid",
        "type": "video",
        "path": "bg.mp4",
        "blend_mode": "normal",
        "opacity": 100.0,
        "enabled": true,
        "effects": [...]
    },
    ...
]

PATCH  /api/player/{id}/layers/{layer_id}
{
    "blend_mode": "screen",
    "opacity": 50.0,
    "enabled": false
}

PUT    /api/player/{id}/layers/reorder
{
    "order": [0, 2, 1]  # Layer IDs in neuer Reihenfolge
}

# Layer Clip Loading
POST   /api/player/{id}/layers/{layer_id}/clip/load
{
    "type": "generator",
    "generator_id": "plasma",
    "parameters": {"speed": 2.0}
}

# Layer Effects
POST   /api/player/{id}/layers/{layer_id}/effects/add
DELETE /api/player/{id}/layers/{layer_id}/effects/{index}
PATCH  /api/player/{id}/layers/{layer_id}/effects/{index}/parameter
```

---

## 4. Backward Compatibility

### Alte API funktioniert weiter:
```python
# ALT (funktioniert)
POST /api/player/video/clip/load
→ Lädt in Layer 0

# NEU (explizit)
POST /api/player/video/layers/0/clip/load
```

### Player Properties:
```python
# Backward compat via @property
@property
def source(self):
    return self.layers[0].source if self.layers else None

@property
def current_clip_id(self):
    return self.layers[0].clip_id if self.layers else None
```

---

## 5. Session State & Snapshots

### Erweitertes Format:
```json
{
  "players": {
    "video": {
      "layers": [
        {
          "layer_id": 0,
          "clip_id": "uuid-1",
          "type": "video",
          "path": "bg.mp4",
          "blend_mode": "normal",
          "opacity": 100.0,
          "enabled": true,
          "effects": [
            {"plugin_id": "blur", "parameters": {"amount": 5}}
          ]
        },
        {
          "layer_id": 1,
          "clip_id": "uuid-2",
          "type": "generator",
          "generator_id": "plasma",
          "parameters": {"speed": 2.0},
          "blend_mode": "multiply",
          "opacity": 50.0,
          "enabled": true,
          "effects": []
        }
      ],
      "playlist": [...],           // Layer 0 Playlist für Autoplay
      "current_index": 0,
      "autoplay": true,
      "loop": true,
      "global_effects": [...]
    }
  }
}
```

### Features:
- **Save**: Speichert kompletten Layer-Stack
- **Snapshots**: Funktionieren automatisch (kompletter State)
- **Migration**: Alte Sessions automatisch konvertiert (playlist → layer 0)

---

## 6. Data Structures

### Layer Class:
```python
class Layer:
    layer_id: int              # Unique ID
    source: FrameSource        # Video/Generator/Script
    effects: list              # Layer-specific effects [{instance, config}]
    blend_mode: str            # 'normal', 'multiply', 'screen', 'add', 'subtract', 'overlay'
    opacity: float             # 0-100%
    clip_id: str               # UUID from ClipRegistry
    enabled: bool              # Visibility toggle
    last_frame: ndarray        # Cache für Compositing
```

### Player Additions:
```python
class Player:
    # NEU
    self.layers = []           # List of Layer objects
    self.layer_counter = 0     # For generating layer IDs
    
    # ALT (backward compat via @property)
    self.source               # → layers[0].source
    self.current_clip_id      # → layers[0].clip_id
    
    # BEHALTEN
    self.video_effect_chain = []   # Global effects
    self.artnet_effect_chain = []  # Global effects
    self.playlist = []             # Layer 0 playlist
    self.autoplay = True
    self.loop_playlist = True
```

---

## 7. Implementation Plan

### Phase 1: Core (~4h)
- [x] BlendEffect Plugin (FERTIG!)
- [ ] Layer class (`src/modules/layer.py`)
  - [ ] `__init__(layer_id, source, blend_mode, opacity)`
  - [ ] Properties: `layer_id`, `source`, `effects`, `blend_mode`, `opacity`, `clip_id`, `enabled`, `last_frame`
  
- [ ] Player: layers array + management methods
  - [ ] Add `self.layers = []`
  - [ ] Add `self.layer_counter = 0`
  - [ ] Method: `add_layer(source, clip_id, blend_mode, opacity) → layer_id`
  - [ ] Method: `remove_layer(layer_id) → bool`
  - [ ] Method: `get_layer(layer_id) → Layer`
  - [ ] Method: `reorder_layers(new_order: list)`
  - [ ] Method: `update_layer_config(layer_id, blend_mode, opacity, enabled)`
  - [ ] Method: `apply_layer_effects(layer, frame) → frame`
  - [ ] Method: `get_blend_plugin(blend_mode, opacity) → BlendEffect`
  - [ ] Property: `source` (backward compat)
  - [ ] Property: `current_clip_id` (backward compat)
  
- [ ] Modified `_play_loop()` mit Master-Slave
  - [ ] Check if layers exist
  - [ ] Fetch master frame (Layer 0)
  - [ ] Handle master end (autoplay/stop)
  - [ ] Apply master layer effects
  - [ ] Loop through slave layers
  - [ ] Auto-reset slave sources on end
  - [ ] Apply slave layer effects
  - [ ] Composite with BlendEffect
  - [ ] Apply global effects
  - [ ] DMX extraction & output

### Phase 2: API (~3h)
- [ ] Layer management endpoints (`src/modules/api_layers.py`)
  - [ ] `POST /api/player/{id}/layers/add`
  - [ ] `DELETE /api/player/{id}/layers/{layer_id}`
  - [ ] `GET /api/player/{id}/layers`
  - [ ] `PATCH /api/player/{id}/layers/{layer_id}`
  - [ ] `PUT /api/player/{id}/layers/reorder`
  
- [ ] Layer clip loading
  - [ ] `POST /api/player/{id}/layers/{layer_id}/clip/load`
  
- [ ] Layer effect management
  - [ ] `POST /api/player/{id}/layers/{layer_id}/effects/add`
  - [ ] `DELETE /api/player/{id}/layers/{layer_id}/effects/{index}`
  - [ ] `PATCH /api/player/{id}/layers/{layer_id}/effects/{index}/parameter`
  - [ ] `POST /api/player/{id}/layers/{layer_id}/effects/clear`
  
- [ ] Backward compat wrapper
  - [ ] Test: `POST /api/player/{id}/clip/load` → loads to layer 0
  - [ ] Test: All existing API endpoints still work

### Phase 3: Session State (~1h)
- [ ] Extend `session_state.py`
  - [ ] Save layer stack in `save()`
  - [ ] Load layer stack in restore
  - [ ] Migration function for old sessions (playlist → layer 0)
  
- [ ] Test migration
  - [ ] Load old session → converts to layer 0
  - [ ] Save new session → includes layers
  - [ ] Snapshot/restore works with layers

### Phase 4: Frontend (~4h)
- [ ] Layer stack UI component
  - [ ] Create `layer-stack.html` component
  - [ ] List all layers with drag handles
  - [ ] Show blend mode + opacity per layer
  - [ ] Show clip thumbnail/name
  
- [ ] Drag & drop reorder
  - [ ] Implement sortable.js or similar
  - [ ] Call `/api/player/{id}/layers/reorder` on drop
  
- [ ] Blend/opacity controls
  - [ ] Blend mode dropdown (6 modes)
  - [ ] Opacity slider (0-100%)
  - [ ] Enabled/disabled toggle
  - [ ] Update via PATCH endpoint
  
- [ ] Add/remove buttons
  - [ ] "Add Layer" button → file/generator picker
  - [ ] Delete button per layer (except layer 0)
  - [ ] Confirmation dialog

---

## 8. Blend Modes (via BlendEffect Plugin)

✅ **Bereits implementiert und getestet:**

- **normal** - Standard overlay
- **multiply** - Darkens (base × overlay) 
- **screen** - Lightens (inverse multiply)
- **add** - Linear dodge (additive)
- **subtract** - Subtractive  
- **overlay** - Conditional multiply/screen

**Dateien:**
- `src/plugins/effects/blend.py` (188 lines)
- `tests/test_blend_effect.py` (279 lines)
- `docs/BLEND_EFFECT.md` (dokumentation)

**Status**: ✅ ALL TESTS PASSED

---

## 9. Testing Checklist

### Backend Tests:
- [ ] Layer creation/deletion
- [ ] Layer reordering
- [ ] Master-slave synchronisation
- [ ] Auto-loop on slave end
- [ ] Blend modes work correctly
- [ ] Layer effects applied
- [ ] Global effects still work
- [ ] Backward compat (old API)
- [ ] Session save/load
- [ ] Snapshot restore
- [ ] Migration old sessions

### Frontend Tests:
- [ ] Layer stack renders
- [ ] Drag & drop reorder
- [ ] Blend mode change updates
- [ ] Opacity slider updates
- [ ] Add layer works
- [ ] Delete layer works
- [ ] Layer enable/disable toggle
- [ ] Layer effects UI
- [ ] Session restore loads layers

### Integration Tests:
- [ ] Single layer = old behavior
- [ ] 2 layers composite correctly
- [ ] 3+ layers composite correctly
- [ ] Different FPS sources (z.B. 60 FPS Slave auf 30 FPS Master)
  - [ ] Verify: Slave läuft nicht doppelt so schnell
  - [ ] Verify: Frame-Skipping funktioniert
- [ ] Generator + Video layers
- [ ] Layer with effects + blend
- [ ] Autoplay with layers
- [ ] Transitions on layer 0

---

## 10. Entscheidungen Getroffen ✅

1. ✅ Layer 0 = Master-Timecode
2. ✅ Slaves loopen automatisch (kein HOLD/FADE)
3. ✅ Sequential Frame-Fetching mit Master-FPS (Phase 1)
   - Alle Sources werden mit get_next_frame() im Master-Takt abgefragt
   - Frame-Skipping bei schnelleren Sources
   - Frame-Hold bei langsameren Sources
   - (Optional später: Zeit-basiertes Sampling für perfekte Sync)
4. ✅ Blend modes via BlendEffect Plugin
5. ✅ API backward compatible (alte Endpoints → Layer 0)
6. ✅ Session State speichert Layer-Stack
7. ✅ Snapshots funktionieren automatisch
8. ✅ Alte Sessions werden migriert

---

## 11. Beispiel-Szenarien

### Szenario 1: Background + Generator
```
Layer 0: video.mp4 (10s)     [============]
Layer 1: plasma (infinite)   [============] ← rendered für 10s
→ Ergebnis: 10s Video mit Plasma-Overlay
```

### Szenario 2: Video + kurzes Overlay
```
Layer 0: background.mp4 (10s) [============]
Layer 1: logo.mp4 (2s)        [==][==][==][==][==] ← 5x Loop
→ Ergebnis: Logo wiederholt sich während Background läuft
```

### Szenario 3: Dreifach-Composite
```
Layer 0: base.mp4 (20s, normal, 100%)
Layer 1: texture.mp4 (5s, multiply, 50%)    ← loopt 4x
Layer 2: light.mp4 (10s, screen, 75%)       ← loopt 2x
→ Ergebnis: Komplexer Multi-Layer Effekt
```

---

## 12. Offene Punkte: KEINE ✅

Alle Entscheidungen getroffen - Bereit für Implementierung!

---

## 13. Referenz-Dokumente

- `docs/BLEND_EFFECT.md` - Blend Effect Plugin Dokumentation
- `docs/MULTI_LAYER_ARCHITECTURE.md` - Ausführliche Architektur-Analyse
- `src/plugins/effects/blend.py` - BlendEffect Implementation
- `tests/test_blend_effect.py` - BlendEffect Tests

---

## Start Implementation

**Ready**: 2025-11-29  
**Estimated Time**: 12h  
**Status**: GO! 🚀
