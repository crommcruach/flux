# Transport/Timeline Redesign: Implementation Plan

## 📋 Overview
Redesign transport system to be **fast, reliable, and persistent** by:
1. Separating transport state from effect system
2. Storing trim settings in clip registry
3. Using WebSocket for real-time position updates
4. Optimizing frame seeking with cache and keyframe index

---

## Phase 1: Clip Registry Trim Integration (2-3 hours)

### 1.1 Enhance Clip Registry (30 min)
**File**: `src/modules/clip_registry.py`

**Add methods:**
```python
def get_trim(self, clip_id: str) -> Dict:
    """Get trim settings for clip."""
    
def set_trim(self, clip_id: str, in_point: int, out_point: int, speed: float = 1.0):
    """Save trim settings to clip."""
    
def get_transport_state(self, clip_id: str) -> Dict:
    """Get full transport state (trim + playback settings)."""
    
def set_transport_state(self, clip_id: str, state: Dict):
    """Save full transport state."""
```

**Extend clip data structure:**
```python
self.clips[clip_id] = {
    # ... existing fields ...
    'trim': {
        'in_point': 0,
        'out_point': None,  # None = end of video
        'speed': 1.0,
        'reverse': False,
        'mode': 'repeat',
        'loop_count': 0
    }
}
```

### 1.2 Modify Transport Effect to Use Registry (1 hour)
**File**: `plugins/effects/transport.py`

**Changes:**
- Accept `clip_registry` and `clip_id` in kwargs
- Load trim from registry on initialization
- Save trim updates back to registry
- Remove trim from effect parameters (read-only display)

**Key modifications:**
```python
def _initialize_state(self, frame_source):
    # 1. Get clip_id from kwargs
    # 2. Load trim from clip_registry.get_trim(clip_id)
    # 3. Apply trim settings
    # 4. If no trim exists, initialize to full range and save
    
def update_parameter(self, name, value):
    # When transport_position changes:
    # 1. Update internal state
    # 2. Save to clip_registry.set_trim()
```

### 1.3 Pass Clip Registry to Transport (30 min)
**Files**: 
- `src/modules/player_core.py` (effect initialization)
- `src/modules/player.py` (kwargs passing)

**Changes:**
- Pass `clip_registry` and `clip_id` in effect kwargs
- Ensure available in `_apply_effect_chain()`

### 1.4 API Endpoints for Trim (30 min)
**File**: `src/modules/api_effects.py` or new `api_transport.py`

**Add routes:**
```python
@app.route('/api/clips/<clip_id>/trim', methods=['GET'])
def get_clip_trim(clip_id):
    """Get trim settings for specific clip."""
    
@app.route('/api/clips/<clip_id>/trim', methods=['POST'])
def set_clip_trim(clip_id):
    """Update trim settings for specific clip."""
```

**Benefits:**
- Direct trim access without going through effect system
- Faster updates (no effect chain refresh)
- Can update trim even when clip not loaded

### 1.5 Testing (30 min)
- Load clip → verify trim loads from registry
- Change trim → verify saves to registry
- Reload same clip → verify trim persists
- Test with multiple instances of same video

---

## Phase 2: Transport State Controller (3-4 hours)

### 2.1 Create TransportController Class (2 hours)
**New file**: `src/modules/transport_controller.py`

**Class structure:**
```python
class TransportController:
    """
    Direct frame control - bypasses effect system.
    Manages playback independently of effects.
    """
    
    def __init__(self, frame_source, clip_registry, clip_id):
        self.source = frame_source
        self.clip_registry = clip_registry
        self.clip_id = clip_id
        
        # Load state from registry
        trim = clip_registry.get_trim(clip_id)
        self.in_point = trim['in_point']
        self.out_point = trim['out_point']
        self.speed = trim['speed']
        self.mode = trim['mode']
        
        # Runtime state
        self.position = self.in_point
        self._virtual_position = float(self.in_point)
        self.playing = False
        
    def play(self):
        """Start playback."""
        
    def pause(self):
        """Pause playback."""
        
    def seek(self, frame: int):
        """Instant seek to frame."""
        
    def set_trim(self, in_point: int, out_point: int):
        """Update trim points."""
        
    def advance_frame(self) -> int:
        """Calculate next frame based on speed/mode."""
        
    def get_state(self) -> Dict:
        """Get current state for API/WebSocket."""
```

**Key features:**
- Minimal overhead (no parameter serialization)
- Direct frame control
- Automatic registry sync
- Event emission for UI updates

### 2.2 Integrate Controller into Player (1 hour)
**File**: `src/modules/player_core.py`

**Changes:**
```python
class PlayerCore:
    def __init__(self, ...):
        self.transport = None  # TransportController instance
        
    def load_clip(self, clip_id, ...):
        # After source initialization:
        self.transport = TransportController(
            self.source, 
            self.clip_registry, 
            clip_id
        )
        
    def _render_frame(self):
        # Before rendering:
        if self.transport and self.is_playing:
            current_frame = self.transport.advance_frame()
            # Frame already set in source by controller
```

**Benefits:**
- Transport runs ONCE per frame (not per effect)
- Direct access: `player.transport.seek(100)`
- No effect chain overhead for playback

### 2.3 Keep Transport Effect as UI Adapter (30 min)
**File**: `plugins/effects/transport.py`

**Modify to be "thin wrapper":**
```python
class TransportEffect:
    """UI adapter for TransportController."""
    
    def apply(self, frame, **kwargs):
        # 1. Get player.transport
        # 2. Read state from controller
        # 3. Return frame unchanged (no processing)
        # 4. Update parameters for UI display
        
    def update_parameter(self, name, value):
        # 1. Forward to player.transport.set_X()
        # 2. Update display parameters
```

**Benefits:**
- Keeps existing UI working
- No frontend changes needed
- Transport effect becomes pure UI/config

### 2.4 Testing (30 min)
- Verify playback with controller
- Test seek performance (should be instant)
- Test trim updates through effect UI
- Verify registry sync

---

## Phase 3: WebSocket Position Updates (2 hours)

### 3.1 Add Transport WebSocket Messages (1 hour)
**File**: `src/modules/websocket_handler.py` or WebSocket implementation

**New message types:**
```python
# Server → Client
{
    "type": "transport_update",
    "player_id": "video",
    "position": 150,
    "in_point": 0,
    "out_point": 300,
    "playing": true,
    "speed": 1.0
}

# Client → Server
{
    "type": "transport_seek",
    "player_id": "video",
    "position": 150
}

{
    "type": "transport_set_trim",
    "player_id": "video",
    "in_point": 10,
    "out_point": 290
}
```

**Implementation:**
- Add WebSocket emit in `TransportController.advance_frame()`
- Throttle to max 10 updates/sec (reduce network traffic)
- Add WebSocket handlers for seek/trim commands

### 3.2 Frontend WebSocket Integration (45 min)
**File**: `frontend/js/player.js`

**Changes:**
```javascript
// Listen for transport updates
ws.on('transport_update', (data) => {
    updateTransportUI(data);
    updateTimelineSlider(data.position, data.in_point, data.out_point);
});

// Send seek commands
function seekTo(frame) {
    ws.send({
        type: 'transport_seek',
        player_id: currentPlayer,
        position: frame
    });
}
```

**Remove polling:**
- Delete `setInterval` for position updates
- Pure event-driven updates
- Instant UI response

### 3.3 Testing (15 min)
- Verify position updates in real-time
- Test scrubbing responsiveness
- Monitor network traffic (should be minimal)

---

## Phase 4: Frame Seeking Optimization (3-4 hours)

### 4.1 Build Keyframe Index (2 hours)
**File**: `src/modules/frame_source.py`

**Add to VideoSource:**
```python
class VideoSource:
    def __init__(self, ...):
        self._keyframe_index = []  # List of seekable frames
        self._build_keyframe_index()
        
    def _build_keyframe_index(self):
        """Build index of keyframes for fast seeking."""
        # Sample every Nth frame or use codec keyframes
        # Store in self._keyframe_index
        
    def seek_fast(self, target_frame: int):
        """Fast seek using keyframe index."""
        # 1. Find nearest keyframe <= target
        # 2. Seek to keyframe
        # 3. Read forward to exact frame
        # 4. Cache path for next seek
```

**Optimization strategies:**
- Build index on clip load (background thread)
- Cache last N frames in LRU cache
- Use codec keyframes if available (H.264, VP9)

### 4.2 Frame Cache with LRU (1 hour)
**File**: `src/modules/frame_source.py`

**Add caching:**
```python
from functools import lru_cache

class VideoSource:
    def __init__(self, ...):
        self._frame_cache = {}  # frame_num → np.array
        self._cache_size = 30   # Keep 30 frames (1 sec @ 30fps)
        
    def get_frame(self, frame_num: int):
        """Get frame with caching."""
        if frame_num in self._frame_cache:
            return self._frame_cache[frame_num]
            
        frame = self._read_frame(frame_num)
        self._add_to_cache(frame_num, frame)
        return frame
```

**Benefits:**
- Scrubbing back/forth is instant (cache hit)
- Preview generation uses cache
- Minimal memory overhead (30 frames ≈ 50MB)

### 4.3 Async Frame Preloading (1 hour)
**File**: `src/modules/frame_source.py`

**Add preloader:**
```python
import threading

class VideoSource:
    def start_preload(self, frame_num: int, direction: int = 1):
        """Preload frames in background."""
        def preload_worker():
            for i in range(frame_num, frame_num + 10):
                self.get_frame(i)  # Will cache
                
        threading.Thread(target=preload_worker, daemon=True).start()
```

**Usage:**
- Preload next 10 frames during playback
- Eliminates frame read stutter
- Start on play/seek

### 4.4 Testing (30 min)
- Test seek performance (should be <50ms)
- Test scrubbing (should be smooth)
- Monitor memory usage
- Test with large videos (>1000 frames)

---

## Phase 5: Performance Monitoring & Optimization (2 hours)

### 5.1 Add Performance Metrics (1 hour)
**File**: `src/modules/transport_controller.py`

**Add timing:**
```python
class TransportController:
    def __init__(self, ...):
        self._metrics = {
            'seek_times': [],
            'frame_advance_times': [],
            'cache_hits': 0,
            'cache_misses': 0
        }
        
    def get_performance_stats(self) -> Dict:
        """Get performance metrics."""
```

**Add API endpoint:**
```python
@app.route('/api/transport/performance', methods=['GET'])
def transport_performance():
    """Get transport performance metrics."""
```

### 5.2 Frontend Performance Display (30 min)
**File**: `frontend/js/player.js`

**Add debug panel:**
```javascript
// Show in console or debug overlay
function showTransportMetrics() {
    fetch('/api/transport/performance')
        .then(r => r.json())
        .then(data => console.table(data));
}
```

### 5.3 Optimization Tuning (30 min)
- Adjust cache size based on metrics
- Tune preload distance
- Optimize WebSocket throttling
- Profile frame read times

---

## Phase 6: Migration & Compatibility (1 hour)

### 6.1 Backward Compatibility (30 min)
**Ensure old transport effect still works:**
- Keep effect-based transport as fallback
- Frontend detects new API and uses it
- Projects with old transport configs load correctly

### 6.2 Migration Script (30 min)
**File**: `scripts/migrate_transport_to_registry.py`

**Purpose:**
- Scan existing project files
- Extract trim settings from effect parameters
- Save to clip registry
- Update project files

---

## 📊 Expected Results

### Performance Improvements:
- **Seek time**: 500ms → **<50ms** (10x faster)
- **Trim update**: 200ms → **<10ms** (20x faster)
- **Position updates**: 250ms polling → **real-time** WebSocket
- **Frame advance**: 2-5ms → **<1ms** (direct control)

### User Experience:
- ✅ Instant scrubbing (no lag)
- ✅ Smooth timeline updates
- ✅ Trim persists across sessions
- ✅ Multiple instances of same video have independent trim
- ✅ Real-time position display (no polling delay)

### Code Quality:
- ✅ Separation of concerns (state vs UI)
- ✅ Easier to test (isolated controller)
- ✅ Better performance monitoring
- ✅ Cleaner architecture

---

## 🗓️ Timeline Estimate

| Phase | Duration | Priority |
|-------|----------|----------|
| **Phase 1**: Registry Integration | 2-3 hours | **HIGH** |
| **Phase 2**: Transport Controller | 3-4 hours | **HIGH** |
| **Phase 3**: WebSocket Updates | 2 hours | **MEDIUM** |
| **Phase 4**: Seek Optimization | 3-4 hours | **MEDIUM** |
| **Phase 5**: Performance Monitoring | 2 hours | **LOW** |
| **Phase 6**: Migration | 1 hour | **LOW** |
| **Total** | **13-16 hours** | |

---

## 🚀 Recommended Implementation Order

### Week 1: Core Infrastructure
1. **Phase 1** (Registry) - Foundation for persistence
2. **Phase 2** (Controller) - Core performance improvement

### Week 2: Real-time & Optimization  
3. **Phase 3** (WebSocket) - Real-time updates
4. **Phase 4** (Seeking) - Smooth scrubbing

### Week 3: Polish
5. **Phase 5** (Monitoring) - Performance validation
6. **Phase 6** (Migration) - Production readiness

---

## ⚠️ Risks & Mitigation

| Risk | Mitigation |
|------|-----------|
| Breaking existing projects | Keep old transport effect working, add migration |
| WebSocket overhead | Throttle updates, use binary format if needed |
| Frame cache memory usage | LRU eviction, configurable size, monitor usage |
| Keyframe index build time | Background thread, progress indicator, cache index |
| Seeking accuracy with codecs | Test with various formats, fallback to sequential |

---

## 🎯 Success Criteria

- [ ] Trim settings persist after player reload
- [ ] Seek completes in <50ms
- [ ] UI updates without polling
- [ ] Smooth scrubbing (no visible lag)
- [ ] Multiple instances work independently
- [ ] Memory usage <100MB for cache
- [ ] All existing projects still load

---

## 📚 Architecture Changes

### Current Architecture:
```
Frontend → API → Player → Effect Chain → Transport Effect
                                           ↓
                                    Frame Calculation
```

**Problems:**
- Transport runs on every frame render
- Parameter updates go through full chain
- No persistence mechanism
- Polling for position updates

### New Architecture:
```
Frontend → WebSocket ←→ TransportController ←→ Clip Registry
              ↓              ↓                      ↓
           Real-time    Direct Frame           Persistence
           Updates      Control                Storage

Player → TransportController.advance_frame()
          ↓
      Frame Source (with cache + index)
          ↓
      Effect Chain (no transport)
```

**Benefits:**
- Transport runs once per frame (not per effect)
- Direct state access (no serialization)
- Automatic persistence
- Real-time UI sync

---

## 🔧 Technical Details

### Clip Registry Data Structure:
```python
{
    'clip_id': 'uuid-123',
    'path': 'video.mp4',
    'trim': {
        'in_point': 0,
        'out_point': 300,
        'speed': 1.0,
        'reverse': False,
        'mode': 'repeat',
        'loop_count': 0
    },
    'effects': [...],
    'layers': [...]
}
```

### TransportController State:
```python
{
    'position': 150,
    'in_point': 0,
    'out_point': 300,
    'speed': 1.0,
    'playing': True,
    'mode': 'repeat',
    '_virtual_position': 150.5,
    '_loop_iteration': 2
}
```

### WebSocket Protocol:
```javascript
// Position update (throttled to 10/sec)
ws.send({
    type: 'transport_update',
    player_id: 'video',
    position: 150,
    in_point: 0,
    out_point: 300,
    playing: true
});

// Seek command (instant)
ws.send({
    type: 'transport_seek',
    player_id: 'video',
    position: 200
});
```

### Frame Cache Strategy:
```python
# LRU cache with 30 frame capacity
cache = {
    145: np.array(...),  # Previous frames
    146: np.array(...),
    147: np.array(...),
    # ... current frame
    150: np.array(...),  # Current
    # ... preloaded frames
    151: np.array(...),
    152: np.array(...)
}
```

---

## 📝 Notes

### Why Separate Controller from Effect?
1. **Performance**: Transport logic runs once per frame, not per effect
2. **Clarity**: Separation of playback control vs visual effects
3. **Flexibility**: Direct API access for advanced features
4. **Persistence**: Natural integration with clip registry

### Why Keep Transport Effect?
1. **UI Compatibility**: Existing frontend expects effect parameters
2. **Migration**: Smooth transition for existing projects
3. **Flexibility**: Users can still configure via effect if needed
4. **Gradual Rollout**: Test new system while maintaining old one

### Why WebSocket for Position?
1. **Real-time**: Instant updates without polling
2. **Efficient**: Single connection for all updates
3. **Bidirectional**: Commands (seek) and updates (position)
4. **Scalable**: Already used for other real-time features

---

## 🔗 Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [PLUGIN_SYSTEM.md](./PLUGIN_SYSTEM.md) - Effect plugin details
- [API.md](./API.md) - REST API endpoints
- [PERFORMANCE.md](./PERFORMANCE.md) - Performance optimization guide

---

**Status**: Planning Phase  
**Last Updated**: December 14, 2025  
**Next Step**: Begin Phase 1 - Clip Registry Integration
