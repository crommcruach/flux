# Transport Duration Mode - Implementation Plan

## Overview

Add a **Duration Mode** parameter to the Transport Effect plugin that allows users to control when multi-layer clips should advance based on layer duration completion.

## Current Behavior

### Sequencer Mode (Slave Playlists)
- All layers loop **independently and infinitely**
- Layer 0 (10sec) loops continuously
- Layer 1 (5sec) loops 2x during one Layer 0 cycle
- Layer 2 (3sec) loops 3.33x during one Layer 0 cycle
- Advances only when **sequencer slot changes** (external trigger)

### Normal Playlist Mode (Non-Slave)
- Layer 0 controls clip duration
- When Layer 0 completes (based on transport loop_count), clip advances
- Slave layers loop independently

## Proposed Feature

Add a **`duration_mode`** dropdown parameter to Transport Effect with the following options:

| Mode | Behavior | Example (L0=10s, L1=5s, L2=3s) |
|------|----------|-------------------------------|
| `"layer_0"` | Advance when Layer 0 completes | Advance after 10 seconds |
| `"shortest"` | Advance when shortest layer completes | Advance after 3 seconds (Layer 2) |
| `"longest"` | Advance when longest layer completes | Advance after 10 seconds (Layer 0) |
| `"layer_1"` | Advance when Layer 1 completes | Advance after 5 seconds |
| `"layer_2"` | Advance when Layer 2 completes | Advance after 3 seconds |
| `"layer_N"` | Advance when Layer N completes | Advance after N's duration |
| `"manual"` | Never auto-advance (infinite loop) | Current infinite loop behavior |

**Default:** `"layer_0"` (maintains backward compatibility)

## Use Cases

### 1. Short Background Loops
- **Layer 0:** 30-second main visual
- **Layer 1:** 3-second animated texture overlay
- **Mode:** `"layer_0"` → Texture loops 10x while main visual plays once

### 2. Quick Transitions
- **Layer 0:** 10-second slow fade
- **Layer 1:** 2-second flash effect
- **Mode:** `"shortest"` → Advance after flash completes (2 sec)

### 3. Synchronized Multi-Layer
- **Layer 0:** 5-second visual
- **Layer 1:** 5-second overlay
- **Mode:** `"longest"` or `"layer_0"` → Both complete together

### 4. Sequencer Slot Duration Control
- Use Transport Effect's `duration_mode` to control when sequencer should advance
- Set `"shortest"` for rapid-fire progression
- Set `"longest"` for full composition playthrough

## Implementation Details

### 1. Transport Effect Plugin (`plugins/effects/transport.py`)

#### Add New Parameter

```python
# In PLUGIN_CONFIG
{
    "parameters": [
        # ... existing parameters ...
        {
            "name": "duration_mode",
            "label": "Duration Mode",
            "type": "dropdown",
            "default": "layer_0",
            "options": [
                {"value": "layer_0", "label": "Layer 0 (Master)"},
                {"value": "shortest", "label": "Shortest Layer"},
                {"value": "longest", "label": "Longest Layer"},
                {"value": "layer_1", "label": "Layer 1"},
                {"value": "layer_2", "label": "Layer 2"},
                {"value": "layer_3", "label": "Layer 3"},
                {"value": "manual", "label": "Manual (Infinite)"}
            ],
            "description": "Determines when clip should advance based on layer durations"
        }
    ]
}
```

#### Add Duration Tracking

```python
class TransportEffect(PluginBase):
    def __init__(self, config=None):
        super().__init__(config)
        # ... existing init ...
        self.duration_mode = config.get('duration_mode', 'layer_0')
        self.target_duration = None  # Set by player
        self._elapsed_time = 0.0  # Track elapsed time since clip start
        self._last_update_time = None
    
    def set_target_duration(self, layer_durations: List[float]):
        """Called by player to set target duration based on mode
        
        Args:
            layer_durations: List of layer durations in seconds [L0, L1, L2, ...]
        """
        if not layer_durations:
            self.target_duration = None
            return
        
        if self.duration_mode == 'manual':
            self.target_duration = None  # Infinite
        elif self.duration_mode == 'shortest':
            self.target_duration = min(layer_durations)
        elif self.duration_mode == 'longest':
            self.target_duration = max(layer_durations)
        elif self.duration_mode.startswith('layer_'):
            layer_idx = int(self.duration_mode.split('_')[1])
            if layer_idx < len(layer_durations):
                self.target_duration = layer_durations[layer_idx]
            else:
                logger.warning(f"Layer {layer_idx} doesn't exist, using Layer 0")
                self.target_duration = layer_durations[0]
        else:
            self.target_duration = layer_durations[0]  # Default to Layer 0
        
        logger.info(f"🎯 Transport duration_mode={self.duration_mode}, target={self.target_duration}s")
    
    def update_elapsed_time(self, dt: float):
        """Update elapsed time (called by player each frame)"""
        if self.target_duration is not None and self.playback_state != 'pause':
            self._elapsed_time += dt
            
            # Check if target duration reached
            if self._elapsed_time >= self.target_duration:
                self.loop_completed = True
                logger.debug(f"⏱️ Target duration reached: {self._elapsed_time:.2f}s >= {self.target_duration:.2f}s")
    
    def reset(self):
        """Reset transport state (called on clip load/loop)"""
        # ... existing reset logic ...
        self._elapsed_time = 0.0
        self._last_update_time = None
```

### 2. Player Core (`src/modules/player/core.py`)

#### Calculate Layer Durations

```python
def _get_layer_durations(self) -> List[float]:
    """Get duration in seconds for each layer
    
    Returns:
        List of durations [L0, L1, L2, ...] in seconds
    """
    durations = []
    
    if not self.layers:
        return durations
    
    for layer in self.layers:
        if not layer.source:
            durations.append(0.0)
            continue
        
        # Video source: total_frames / fps
        if hasattr(layer.source, 'total_frames') and hasattr(layer.source, 'fps'):
            if layer.source.fps > 0:
                duration = layer.source.total_frames / layer.source.fps
            else:
                duration = 0.0
        # Generator: infinite (use a large value or 0)
        elif hasattr(layer.source, 'generator_name'):
            duration = 0.0  # Generators have no inherent duration
        else:
            duration = 0.0
        
        durations.append(duration)
    
    return durations
```

#### Initialize Transport Duration Mode

```python
def load_clip_layers(self, clip_id, clip_registry, video_dir):
    """Load layers for a clip from registry"""
    # ... existing layer loading logic ...
    
    # After layers are loaded, set transport duration mode
    if self.layers:
        layer_durations = self._get_layer_durations()
        
        # Find transport effect on Layer 0 and set target duration
        for effect in self.layers[0].effects:
            if effect.get('id') == 'transport' and effect.get('instance'):
                transport = effect['instance']
                transport.set_target_duration(layer_durations)
                break
```

#### Update Transport Elapsed Time

```python
def _play_loop(self):
    """Main playback loop"""
    # ... existing frame timing logic ...
    
    while self.is_running and self.is_playing:
        loop_start = time.time()
        
        # ... existing frame fetching logic ...
        
        # Update transport elapsed time (for duration_mode tracking)
        if self.layers:
            for effect in self.layers[0].effects:
                if effect.get('id') == 'transport' and effect.get('instance'):
                    transport = effect['instance']
                    if hasattr(transport, 'update_elapsed_time'):
                        transport.update_elapsed_time(frame_time)
                    break
        
        # ... rest of playback logic ...
```

### 3. Frontend UI

#### Effect Editor (`frontend/js/effects.js`)

```javascript
// Add duration_mode dropdown to transport effect UI
// This is handled automatically by parameter type="dropdown"
// No additional code needed - dropdown will appear in effect editor
```

#### Layer Duration Display (Optional Enhancement)

```javascript
// In layer info panel, show layer durations
function displayLayerDurations(clipId) {
    const clip = getClipById(clipId);
    if (!clip || !clip.layers) return;
    
    const durationsHtml = clip.layers.map((layer, idx) => {
        const duration = calculateLayerDuration(layer);
        return `<div>Layer ${idx}: ${duration.toFixed(2)}s</div>`;
    }).join('');
    
    document.getElementById('layerDurations').innerHTML = durationsHtml;
}

function calculateLayerDuration(layer) {
    if (layer.type === 'video') {
        // duration_seconds from backend
        return layer.duration_seconds || 0;
    } else if (layer.type === 'generator') {
        return Infinity; // Generators are infinite
    }
    return 0;
}
```

## API Changes

### Clip Registry Schema

**No changes needed** - layer durations are calculated on-the-fly from existing source properties.

### Transport Effect Config

```json
{
  "id": "transport",
  "parameters": {
    "speed": 1.0,
    "direction": "forward",
    "playback_mode": "repeat",
    "loop_count": 0,
    "duration_mode": "layer_0"  // NEW
  }
}
```

## Edge Cases & Handling

### 1. Generator Layers (Infinite Duration)
- **Problem:** Generators have no inherent duration
- **Solution:** Treat as `duration = 0.0`, exclude from shortest/longest calculations
- If all layers are generators, fall back to `loop_count` behavior

### 2. Mixed Video + Generator Layers
```
Layer 0: 10s video
Layer 1: Infinite generator
```
- `"shortest"` → 10s (ignores generator)
- `"longest"` → 10s (ignores generator)
- `"layer_0"` → 10s
- `"layer_1"` → Infinite (manual mode)

### 3. Transport Speed Affects Duration
- **Layer 0:** 10s video, speed=2.0 → effective duration = 5s
- **Solution:** Calculate effective duration: `base_duration / abs(speed)`
- Apply speed correction in `set_target_duration()`

### 4. Transport Direction = Backward
- Duration remains the same
- Advance trigger occurs at same point (end of reverse playback)

### 5. Sequencer Mode Interaction
- **Sequencer Mode ON:** Transport still controls clip looping internally
- **Duration Mode = "manual":** Clips loop infinitely until sequencer advances
- **Duration Mode = "shortest":** Clips could auto-advance before sequencer slot ends (potential conflict)
- **Recommendation:** When in sequencer mode, transport duration_mode should be "manual" or managed carefully

### 6. Non-Existent Layer Selected
```
Layer 0: 10s
Layer 1: 5s
duration_mode: "layer_2"  // Doesn't exist!
```
- **Solution:** Fall back to Layer 0 with warning log

### 7. Zero-Duration Layers
- If layer has 0 duration (empty video, error), treat as infinite
- Log warning and exclude from shortest/longest calculations

## Migration & Backward Compatibility

### Default Behavior
- **Default:** `duration_mode = "layer_0"`
- **Existing clips:** No transport duration_mode set → defaults to Layer 0
- **Behavior:** Identical to current implementation ✅

### Existing Playlists
- No migration needed
- Transport effects without `duration_mode` parameter use Layer 0 default
- Users can opt-in by editing transport effect and selecting mode

## Performance Considerations

### Minimal Overhead
- Layer duration calculation: **Once per clip load** (~0.1ms)
- Elapsed time update: **Once per frame** (~0.001ms)
- No impact on frame processing pipeline

### Optimization
- Cache layer durations on clip load (don't recalculate every frame)
- Only update elapsed time if `duration_mode != "manual"`

## Testing Plan

### Unit Tests

```python
# test_transport_duration_mode.py

def test_shortest_mode():
    """Test shortest layer completion triggers advance"""
    # Create clip: L0=10s, L1=5s, L2=3s
    # Set duration_mode="shortest"
    # Expect: Advance after 3s
    
def test_longest_mode():
    """Test longest layer completion triggers advance"""
    # Create clip: L0=10s, L1=5s, L2=3s
    # Set duration_mode="longest"
    # Expect: Advance after 10s
    
def test_specific_layer_mode():
    """Test specific layer selection"""
    # Create clip: L0=10s, L1=5s
    # Set duration_mode="layer_1"
    # Expect: Advance after 5s

def test_manual_mode():
    """Test manual mode never auto-advances"""
    # Set duration_mode="manual"
    # Play for 100s
    # Expect: Still on same clip

def test_generator_ignored():
    """Test generators excluded from calculations"""
    # L0=10s video, L1=generator
    # Set duration_mode="shortest"
    # Expect: Advance after 10s (not infinite)

def test_nonexistent_layer_fallback():
    """Test fallback when selected layer doesn't exist"""
    # L0=10s, L1=5s (no L2)
    # Set duration_mode="layer_2"
    # Expect: Warning + fallback to L0 (10s)
```

### Integration Tests

1. **Sequencer Mode:** Verify transport duration mode doesn't conflict with sequencer control
2. **Master/Slave Playlists:** Test shortest/longest mode in slave playlists
3. **UI:** Verify dropdown appears and saves correctly
4. **Speed Interaction:** Test duration adjustment with transport speed

## Implementation Phases

### Phase 1: Backend Core ✅
- [ ] Add `duration_mode` parameter to transport.py
- [ ] Implement `set_target_duration()` method
- [ ] Add elapsed time tracking
- [ ] Calculate layer durations in player core
- [ ] Initialize transport on clip load

### Phase 2: Integration ✅
- [ ] Hook elapsed time updates into playback loop
- [ ] Test shortest/longest/specific layer modes
- [ ] Handle edge cases (generators, missing layers)

### Phase 3: Frontend ✅
- [ ] Dropdown appears automatically (no code needed)
- [ ] Test parameter save/load
- [ ] (Optional) Add layer duration display in UI

### Phase 4: Testing & Polish ✅
- [ ] Write unit tests
- [ ] Integration testing
- [ ] Documentation updates
- [ ] Release notes

## User Documentation

### Quick Start

**To control when multi-layer clips advance:**

1. Select a clip with multiple layers
2. Add/Edit Transport Effect on Layer 0
3. Set **Duration Mode**:
   - **Layer 0:** Advance when main layer finishes (default)
   - **Shortest:** Advance when shortest layer finishes
   - **Longest:** Advance when longest layer finishes
   - **Layer 1/2/3:** Advance when specific layer finishes
   - **Manual:** Never auto-advance (infinite loop)

### Example Workflow

**Creating a 3-second slideshow with animated texture:**

```
Clip Setup:
- Layer 0: Static image (converted to 3s video)
- Layer 1: 0.5s particle burst (loops 6x)

Transport Settings:
- speed: 1.0
- playback_mode: repeat
- loop_count: 1
- duration_mode: "layer_0"

Result: Particles loop 6 times while image shows for 3s, then advance
```

## Future Enhancements

### 1. BPM-Sync Duration Mode
- `"bpm_sync"` → Advance on beat boundaries
- Requires integration with BPM detection

### 2. Custom Duration
- `"custom"` → User specifies exact duration in seconds
- Add `custom_duration` parameter

### 3. Timeline Markers
- Allow setting advance markers in timeline
- `"first_marker"` / `"last_marker"` modes

### 4. Layer Group Modes
- `"group_A"` → Advance when all layers in group A complete
- Complex multi-group compositions

## References

- [TRANSPORT_MASTER_SLAVE_ANALYSIS.md](TRANSPORT_MASTER_SLAVE_ANALYSIS.md) - Transport loop count implementation
- [LAYER_EFFECTS_PLAN.md](LAYER_EFFECTS_PLAN.md) - Multi-layer architecture
- [plugins/effects/transport.py](../plugins/effects/transport.py) - Transport Effect implementation
- [src/modules/player/core.py](../src/modules/player/core.py) - Player playback loop

---

**Status:** 📋 **Planning Phase** - Ready for implementation
**Priority:** Medium
**Complexity:** Medium
**Estimated Effort:** 4-6 hours
