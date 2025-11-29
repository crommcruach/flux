# Multi-Layer Support - Architektur-Analyse

## Datum: 2025-11-29

## Aktuelle Architektur (Single Source)

### Player Structure
```python
class Player:
    def __init__(self, frame_source, ...):
        self.source = frame_source  # SINGLE source (VideoSource, ScriptSource, GeneratorSource)
        self.video_effect_chain = []  # Effects für Video-Preview
        self.artnet_effect_chain = []  # Effects für Art-Net Output
        self.current_clip_id = None  # UUID of currently loaded clip
```

### Playback Flow
```
1. get_next_frame() von self.source
2. Apply brightness/hue auf komplettes Frame
3. Apply video_effect_chain (für Preview)
4. Apply artnet_effect_chain (für Art-Net Output)
5. Extract pixels für DMX
6. Send via ArtNet
```

### API: Clip Loading
```python
POST /api/player/<player_id>/clip/load
Body: {
    "type": "video",
    "path": "video1.mp4"
    # ODER
    "type": "generator", 
    "generator_id": "plasma"
}
```

**Limitation**: Nur **1 Clip pro Player** zur Zeit!

---

## Problemstellung für Multi-Layer

### Ziel
Mehrere Clips gleichzeitig abspielen und compositen:
- Layer 1: Video "background.mp4" (Normal blend, 100% opacity)
- Layer 2: Generator "plasma" (Multiply blend, 50% opacity)
- Layer 3: Video "overlay.mp4" (Screen blend, 75% opacity)

### Herausforderungen

#### 1. **Player Architecture**
- **Current**: `self.source` - single source
- **Needed**: `self.layers = []` - multiple sources

#### 2. **API Design**
- **Current**: `/api/player/{id}/clip/load` - replaces current clip
- **Needed**: Layer management endpoints:
  - `POST /api/player/{id}/layers/add` - Add layer to stack
  - `DELETE /api/player/{id}/layers/{layer_id}` - Remove layer
  - `PUT /api/player/{id}/layers/reorder` - Change layer order
  - `PATCH /api/player/{id}/layers/{layer_id}` - Update blend/opacity

#### 3. **Frame Processing**
- **Current**: Single frame pipeline
  ```python
  frame = self.source.get_next_frame()
  frame = apply_effects(frame, 'video')
  frame = apply_effects(frame, 'artnet')
  ```

- **Needed**: Multi-layer compositing
  ```python
  # Layer 0 (bottom)
  base_frame = layers[0].source.get_next_frame()
  base_frame = apply_layer_effects(base_frame, layers[0])
  
  # Composite additional layers
  for layer in layers[1:]:
      overlay_frame = layer.source.get_next_frame()
      overlay_frame = apply_layer_effects(overlay_frame, layer)
      
      # Use blend effect
      blend_plugin = BlendEffect()
      blend_plugin.initialize({
          'blend_mode': layer.blend_mode,
          'opacity': layer.opacity
      })
      base_frame = blend_plugin.process_frame(base_frame, overlay=overlay_frame)
  
  # Final global effects
  base_frame = apply_effects(base_frame, 'video')
  base_frame = apply_effects(base_frame, 'artnet')
  ```

#### 4. **Clip Registry**
- **Current**: 1 clip per player tracked by `current_clip_id`
- **Needed**: Multiple clips tracked per layer
  ```python
  player.layer_clips = [
      "uuid-1",  # Layer 0 clip
      "uuid-2",  # Layer 1 clip
      "uuid-3"   # Layer 2 clip
  ]
  ```

#### 5. **Effect Management**
- **Current**: Effects pro Player (global) oder pro Clip
- **Needed**: Effects pro Layer
  ```python
  layers[0].effects = [BlurEffect(), TransformEffect()]
  layers[1].effects = [OpacityEffect()]
  ```

#### 6. **Session State**
- **Current**: Saves player.source, player.current_clip_id
- **Needed**: Save entire layer stack
  ```json
  {
    "player_id": "video",
    "layers": [
      {
        "layer_id": 0,
        "clip_id": "uuid-1",
        "blend_mode": "normal",
        "opacity": 100.0,
        "effects": [...]
      },
      {
        "layer_id": 1,
        "clip_id": "uuid-2",
        "blend_mode": "multiply",
        "opacity": 50.0,
        "effects": [...]
      }
    ]
  }
  ```

---

## Proposed Architecture Changes

### 1. Layer Data Structure

```python
class Layer:
    """Represents a single compositing layer."""
    def __init__(self, layer_id, source, blend_mode='normal', opacity=100.0):
        self.layer_id = layer_id  # Unique ID within player
        self.source = source  # VideoSource/GeneratorSource/ScriptSource
        self.effects = []  # Layer-specific effects
        self.blend_mode = blend_mode  # 'normal', 'multiply', 'screen', etc.
        self.opacity = opacity  # 0-100%
        self.clip_id = None  # UUID from ClipRegistry
        self.enabled = True  # Layer visibility toggle
```

### 2. Modified Player Class

```python
class Player:
    def __init__(self, ...):
        # NEW: Layer system
        self.layers = []  # List of Layer objects
        self.layer_counter = 0  # For generating layer IDs
        
        # DEPRECATED but keep for backward compatibility
        self.source = None  # Maps to layers[0].source if available
        self.current_clip_id = None  # Maps to layers[0].clip_id
        
        # Keep existing
        self.video_effect_chain = []  # GLOBAL effects after compositing
        self.artnet_effect_chain = []  # GLOBAL effects after compositing
```

**Backward Compatibility**:
```python
@property
def source(self):
    """Returns first layer's source for backward compatibility."""
    return self.layers[0].source if self.layers else None

@source.setter
def source(self, value):
    """Sets first layer's source for backward compatibility."""
    if not self.layers:
        self.add_layer(value)
    else:
        self.layers[0].source = value
```

### 3. New API Endpoints

```python
# Layer Management
POST   /api/player/{id}/layers/add          # Add new layer
DELETE /api/player/{id}/layers/{layer_id}  # Remove layer
GET    /api/player/{id}/layers              # List all layers
PATCH  /api/player/{id}/layers/{layer_id}  # Update layer config
PUT    /api/player/{id}/layers/reorder     # Reorder layers

# Layer Clip Loading
POST   /api/player/{id}/layers/{layer_id}/clip/load

# Layer Effects
POST   /api/player/{id}/layers/{layer_id}/effects/add
DELETE /api/player/{id}/layers/{layer_id}/effects/{index}
PATCH  /api/player/{id}/layers/{layer_id}/effects/{index}/parameter
```

### 4. Modified _play_loop()

```python
def _play_loop(self):
    while self.is_running:
        if not self.layers:
            # No layers - idle
            time.sleep(0.1)
            continue
        
        # STEP 1: Fetch first layer (base)
        base_layer = self.layers[0]
        if not base_layer.enabled:
            # Base layer disabled - black frame
            base_frame = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        else:
            base_frame, _ = base_layer.source.get_next_frame()
            if base_frame is None:
                # Handle end of base layer (autoplay, loop, etc.)
                continue
            
            # Apply layer-specific effects
            for effect in base_layer.effects:
                base_frame = effect['instance'].process_frame(base_frame)
        
        # STEP 2: Composite additional layers
        for layer in self.layers[1:]:
            if not layer.enabled:
                continue
            
            overlay_frame, _ = layer.source.get_next_frame()
            if overlay_frame is None:
                # Handle layer end (loop or disable)
                layer.source.reset()
                continue
            
            # Apply layer-specific effects
            for effect in layer.effects:
                overlay_frame = effect['instance'].process_frame(overlay_frame)
            
            # Blend with base using BlendEffect
            blend_plugin = self.get_blend_plugin(layer.blend_mode, layer.opacity)
            base_frame = blend_plugin.process_frame(base_frame, overlay=overlay_frame)
        
        # STEP 3: Apply global brightness/hue
        base_frame = self.apply_brightness_hue(base_frame)
        
        # STEP 4: Apply global effect chains
        frame_for_video = self.apply_effects(base_frame, 'video')
        frame_for_artnet = self.apply_effects(base_frame, 'artnet')
        
        # STEP 5: Extract pixels and send
        # ... existing DMX extraction code ...
```

### 5. Layer Management Methods

```python
def add_layer(self, source, clip_id=None, blend_mode='normal', opacity=100.0):
    """Add new layer to stack."""
    layer_id = self.layer_counter
    self.layer_counter += 1
    
    layer = Layer(layer_id, source, blend_mode, opacity)
    layer.clip_id = clip_id
    self.layers.append(layer)
    
    logger.info(f"✅ Layer {layer_id} added: {source.get_source_name()}")
    return layer_id

def remove_layer(self, layer_id):
    """Remove layer from stack."""
    for i, layer in enumerate(self.layers):
        if layer.layer_id == layer_id:
            layer.source.cleanup()
            del self.layers[i]
            logger.info(f"🗑️ Layer {layer_id} removed")
            return True
    return False

def reorder_layers(self, new_order):
    """Reorder layers (new_order = [layer_id, ...])."""
    layer_map = {layer.layer_id: layer for layer in self.layers}
    self.layers = [layer_map[lid] for lid in new_order if lid in layer_map]
    logger.info(f"🔄 Layers reordered: {new_order}")

def get_layer(self, layer_id):
    """Get layer by ID."""
    for layer in self.layers:
        if layer.layer_id == layer_id:
            return layer
    return None

def update_layer_config(self, layer_id, blend_mode=None, opacity=None, enabled=None):
    """Update layer configuration."""
    layer = self.get_layer(layer_id)
    if not layer:
        return False
    
    if blend_mode is not None:
        layer.blend_mode = blend_mode
    if opacity is not None:
        layer.opacity = opacity
    if enabled is not None:
        layer.enabled = enabled
    
    logger.debug(f"🔧 Layer {layer_id} updated")
    return True
```

---

## Migration Strategy

### Phase 1: Internal Changes (No API Breaking)
1. Add `self.layers = []` to Player
2. Implement Layer class
3. Modify `_play_loop()` to support layers
4. Keep `self.source` as backward compatibility property

### Phase 2: API Extensions (Additive)
1. Add layer management endpoints
2. Keep existing `/api/player/{id}/clip/load` working (adds to layer 0)
3. Test with single layer (should behave like before)

### Phase 3: Frontend Integration
1. Update UI to show layer stack
2. Add layer controls (add, remove, reorder)
3. Add blend mode selector per layer
4. Add opacity slider per layer

### Phase 4: Session State Migration
1. Update session state format to save layers
2. Add migration code for old sessions (convert source → layer 0)

---

## Implementation Estimate

### Backend (~6-8h)
- [ ] Layer class implementation (~1h)
- [ ] Player modifications (layers array, methods) (~2h)
- [ ] Modify `_play_loop()` for compositing (~2h)
- [ ] API endpoints for layer management (~2h)
- [ ] Session state migration (~1h)

### Frontend (~4-5h)
- [ ] Layer stack UI component (~2h)
- [ ] Drag & drop reordering (~1h)
- [ ] Blend mode/opacity controls (~1h)
- [ ] API integration (~1h)

### Testing & Documentation (~2h)
- [ ] Test single layer (backward compat) (~30min)
- [ ] Test multi-layer compositing (~30min)
- [ ] Test blend modes (~30min)
- [ ] Documentation (~30min)

**Total: ~12-15h**

---

## Decision Points

### ⚠️ Critical Questions Before Implementation

1. **Layer Synchronization**
   - How to handle layers with different FPS?
   - How to handle layers with different durations?
   - **Proposal**: Each layer loops independently

2. **Layer Autoplay**
   - Should layers have individual playlists?
   - **Proposal**: NO - too complex. Layers are manually managed.

3. **Effect Scope**
   - Per-layer effects vs global effects?
   - **Proposal**: BOTH - layer.effects[] + player.video/artnet_effect_chain[]

4. **Transition System**
   - How do transitions work with layers?
   - **Proposal**: Transitions only on layer 0 (base layer)

5. **Backward Compatibility**
   - Must existing API still work?
   - **Proposal**: YES - map old API to layer 0 operations

---

## Recommendation

### ✅ Proceed with Implementation
- Architecture is sound and elegant
- Backward compatibility achievable via properties
- Estimated effort reasonable (~12-15h)
- Uses existing BlendEffect plugin
- No major blockers identified

### 🔴 Blockers to Resolve First
1. **Layer Sync Strategy**: Decide on independent loop vs synchronized playback
2. **API Compatibility**: Verify all existing endpoints still work with layer 0 mapping
3. **Session Migration**: Plan migration path for existing sessions

### 📋 Next Steps
1. Create Layer class in `src/modules/layer.py`
2. Add layer management methods to Player
3. Modify `_play_loop()` for compositing
4. Create API endpoints in new file `src/modules/api_layers.py`
5. Update session state schema

---

## Open Questions for User

1. **Layer Playback**:
   - Sollen alle Layers synchron laufen (gleiche FPS)?
   - Oder jeder Layer mit eigener FPS/Loop?

2. **Layer Playlists**:
   - Soll jeder Layer eine eigene Playlist haben?
   - Oder nur manuelles Layer-Management?

3. **Transition Scope**:
   - Transitions nur auf Layer 0?
   - Oder pro Layer konfigurierbar?

4. **Performance**:
   - Limit für maximale Layer-Anzahl? (z.B. 5 Layers)
   - GPU-Beschleunigung für Blending geplant?
