# Performance Monitoring System

## Overview

The Performance Monitoring System provides real-time profiling of the entire rendering pipeline, tracking processing times for each stage to identify bottlenecks.

## Complete Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                         RENDERING PIPELINE                          │
└─────────────────────────────────────────────────────────────────────┘

1. Source Decode (source_decode)
   ├─ FFmpeg codec decoding (H.264/H.265: 10-30ms, HAP: 1-3ms)
   ├─ VideoSource.get_next_frame()
   ├─ GeneratorSource.get_next_frame()
   └─ Frame buffer management
   
2. Clip Effects (clip_effects)
   ├─ Layer-specific effects
   ├─ Effect plugin processing
   ├─ Transport effect (frame position)
   └─ Per-clip parameter modulation
   
3. Layer Composition (layer_composition)
   ├─ Multi-layer blending
   ├─ Alpha compositing
   ├─ Blend mode application (add, multiply, screen, etc.)
   └─ Layer opacity/masking
   
4. Player Effects (player_effects)
   ├─ Player-level effect chain (video/artnet)
   ├─ Global effects (blur, color grading, etc.)
   ├─ Video vs ArtNet separate processing
   └─ Effect parameter sequences
   
5. Audio Sequences (audio_sequences) *
   ├─ BPM detection
   ├─ Beat detection
   ├─ Audio-driven parameter modulation
   └─ Sequence manager updates
   
6. Transitions (transitions)
   ├─ Crossfade between clips
   ├─ Transition plugins (fade, wipe, etc.)
   ├─ Transition easing curves
   └─ Previous frame compositing
   
7. Background Composite (background_composite) *
   ├─ Background image overlay
   ├─ Background blending
   └─ Canvas compositing
   
8. Output Routing (output_routing)
   ├─ ArtNet pixel mapping
   ├─ Universe distribution
   ├─ DMX channel assignment
   └─ Output buffering
   
9. Frame Delivery (frame_delivery) *
    ├─ Preview stream encoding
    ├─ Display window updates
    ├─ ArtNet packet transmission
    └─ Frame timing sync

* Stages not yet fully instrumented (future enhancement)

NOTE: The "clip_load" stage was removed and split into granular stages
      (source_decode, clip_effects, layer_composition) for accurate
      bottleneck identification. Profiling now happens inside LayerManager.
```

## Architecture

### Profiler Module

**Location**: `src/modules/performance/profiler.py`

**Key Components**:
- `PerformanceProfiler`: Main profiler class
- `StageMetrics`: Data class for stage metrics
- `get_profiler(player_name)`: Get/create profiler instance
- `get_all_profilers()`: Get all registered profilers

**Features**:
- Thread-safe circular buffers (default: 100 samples)
- Context manager API for easy instrumentation
- Automatic frame time tracking
- Per-player profiling (Video Player, ArtNet Player)
- Enable/disable without code changes

### Player Integration

**Location**: `src/modules/player/core.py`

**Instrumentation Points**:
```python
# Clip Load + Layer Compositing
with self.profiler.profile_stage('clip_load'):
    frame, source_delay = self.layer_manager.composite_layers(...)

# Transitions
with self.profiler.profile_stage('transitions'):
    frame = self.transition_manager.apply(frame, self.player_name)

# Player Effects
with self.profiler.profile_stage('player_effects'):
    frame = self.effect_processor.apply_effects(...)

# Output Routing
with self.profiler.profile_stage('output_routing'):
    self.routing_bridge.process_frame(frame_for_artnet)

# Mark frame complete
self.profiler.record_frame_complete()
```

### REST API Endpoints

**Location**: `src/modules/api/system/performance.py`

**Endpoints**:

#### GET /api/performance/metrics
Get comprehensive performance metrics for all players.

**Response**:
```json
{
  "success": true,
  "metrics": {
    "Video Player (Preview)": {
      "player": "Video Player (Preview)",
      "enabled": true,
      "timestamp": "2026-02-26T...",
      "uptime_seconds": 123.4,
      "total_frames": 3000,
      "fps": 30.5,
      "total_frame_time": {
        "avg_ms": 8.5,
        "min_ms": 5.2,
        "max_ms": 15.3,
        "target_fps": 60,
        "target_frame_time_ms": 16.67,
        "performance_ratio": 1.96
      },
      "stages": [
        {
          "name": "clip_load",
          "avg_ms": 3.2,
          "min_ms": 2.1,
          "max_ms": 8.5,
          "last_ms": 3.1,
          "samples": 100,
          "percentage": 37.6
        },
        ...
      ]
    },
    "Art-Net Player": { ... }
  },
  "players": ["Video Player (Preview)", "Art-Net Player"]
}
```

#### POST /api/performance/reset
Reset performance metrics.

**Request**:
```json
{
  "player": "Video Player (Preview)"  // Optional, reset all if omitted
}
```

**Response**:
```json
{
  "success": true,
  "message": "Reset metrics for Video Player (Preview)"
}
```

#### POST /api/performance/toggle
Enable/disable performance profiling.

**Request**:
```json
{
  "enabled": true,
  "player": "Video Player (Preview)"  // Optional
}
```

**Response**:
```json
{
  "success": true,
  "enabled": true,
  "player": "Video Player (Preview)"
}
```

### Web Interface

**Location**: `frontend/performance.html`

**URL**: `http://localhost:5000/performance`

**Features**:
- Real-time performance dashboard (1 second refresh)
- Separate cards for each player (Video/ArtNet)
- Pipeline stage visualization with bar graphs
- Frame time summary with color-coded status:
  - 🟢 Green: Performance good (< target frame time)
  - 🟠 Orange: Performance warning (> 80% of target)
  - 🔴 Red: Performance critical (> target frame time)
- Stage-by-stage breakdown:
  - Average time (ms)
  - Min/Max times
  - Percentage of total frame time
  - Visual bar graph
- Live statistics:
  - Current FPS
  - Total frames processed
  - Uptime
  - Performance ratio
- Controls:
  - Auto-refresh toggle (pause/resume)
  - Manual refresh
  - Reset metrics
  - Return to home

## Configuration

### Enable/Disable Profiling

Performance profiling can be configured globally in `config.json`:

```json
{
  "performance": {
    "profiling_enabled": true,
    ...
  }
}
```

**Settings**:
- `profiling_enabled: true` - Enable performance profiling (default)
- `profiling_enabled: false` - Disable profiling for zero overhead

**When to Disable**:
- ✅ **Production Deployments**: Set to `false` for zero overhead
- ✅ **Live Performances**: Disable to maximize performance
- ✅ **Final Installations**: No monitoring needed after optimization
- ❌ **Development**: Keep enabled to identify bottlenecks
- ❌ **Testing**: Keep enabled to catch performance regressions
- ❌ **Optimization**: Keep enabled to measure improvements

### Runtime Control

**Dynamic Toggle** (via API):
```bash
# Disable profiling at runtime
curl -X POST http://localhost:5000/api/performance/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Enable profiling at runtime
curl -X POST http://localhost:5000/api/performance/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

**Per-Player Control** (optional):
```bash
# Disable only Video Player profiling
curl -X POST http://localhost:5000/api/performance/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false, "player": "Video Player (Preview)"}'
```

### Configuration Loading

Profiling is configured during application startup in [main.py](../src/main.py):

```python
# Configure performance profiling (before players are created)
from modules.performance import set_profiling_enabled
profiling_enabled = config.get('performance', {}).get('profiling_enabled', True)
set_profiling_enabled(profiling_enabled)
logger.debug(f"Performance profiling: {'enabled' if profiling_enabled else 'disabled (zero overhead)'}")
```

**Important**: Configuration is applied **before** players are created, ensuring consistent behavior from startup.

## Usage

### Access Performance Monitor

1. Start Flux application
2. Open browser to `http://localhost:5000/performance`
3. View real-time metrics for both players

### Identify Bottlenecks

**Look for**:
1. **High percentage stages** (> 30% of frame time)
   - These are consuming most processing time
   - Prime candidates for optimization

2. **Red/orange stages**
   - Stages taking longer than expected
   - May cause dropped frames

3. **Max time spikes**
   - Occasional slowdowns
   - May indicate resource contention or GC pauses

4. **Total frame time > 16.67ms**
   - Performance ratio < 1.0
   - Cannot maintain 60 FPS
   - Frames will be dropped

### Performance Investigation Workflow

```
1. Open Performance Monitor
   ↓
2. Start playback with typical content
   ↓
3. Let it run for ~30 seconds (gather samples)
   ↓
4. Identify slowest stages (highest percentage)
   ↓
5. Check stage max times for spikes
   ↓
6. Adjust effects/settings to reduce load
   ↓
7. Reset metrics and re-test
   ↓
8. Compare before/after performance
```

## Performance Targets

**Target Frame Times** (60 FPS):
- **Total Frame Time**: < 16.67 ms
- **Clip Load**: < 3 ms (18%)
- **Effects**: < 5 ms (30%)
- **Output Routing**: < 2 ms (12%)
- **Transitions**: < 1 ms (6%)
- **Buffer**: ~5 ms (30%) for overhead

**Critical Thresholds**:
- ⚠️ Warning: > 13.3 ms (80% of target)
- 🚨 Critical: > 16.67 ms (dropped frames)

## Future Enhancements

### Planned Improvements

1. **More Granular Profiling**
   - Individual effect plugin timing
   - Per-layer composition breakdown
   - Codec decode times
   - DMX packet transmission times

2. **Historical Data**
   - Trend graphs (time series)
   - Performance over time
   - Identify degradation patterns
   - Export metrics to CSV/JSON

3. **Alerts & Notifications**
   - WebSocket push notifications
   - Configurable thresholds
   - Performance degradation detection
   - Bottleneck warnings

4. **Comparative Analysis**
   - Compare different effect configurations
   - A/B testing framework
   - Regression detection
   - Performance snapshots

5. **Advanced Visualization**
   - Flame graphs
   - Call stack profiling
   - Memory usage tracking
   - GPU utilization (if available)

6. **Integration**
   - Export to external monitoring (Prometheus, Grafana)
   - Performance logging to file
   - CI/CD performance regression tests

## Technical Notes

### Thread Safety
- All profiler operations are thread-safe
- Uses `threading.RLock()` for synchronization
- Circular buffers (`deque`) for memory efficiency
- Per-thread timer stack for nested profiling

### Performance Overhead
- **Enabled**: ~1-2 μs per stage (context manager + timing)
- **Disabled**: Near-zero overhead (fast path - just `yield`, no timing code)
- Minimal memory footprint (circular buffers)
- Can be disabled dynamically (no overhead when disabled)
- **Production Recommendation**: Disable via `config.json` for zero overhead

### Memory Usage
- 100 samples per stage × 10 stages = 1000 floats
- ~8 KB per player
- Total: ~16 KB for both players
- Circular buffers prevent memory growth

### Accuracy
- Uses `time.perf_counter()` for high-resolution timing
- Microsecond precision
- Includes all overhead in stage (realistic measurement)
- Averages over 100 samples for stability

## Troubleshooting

### Performance monitor shows no data
- **Cause**: Players not started
- **Solution**: Start playback on at least one player

### Metrics not updating
- **Cause**: Auto-refresh paused
- **Solution**: Click "Resume" button

### Very high frame times (> 50ms)
- **Cause**: Heavy effects, high resolution, or slow hardware
- **Solution**: 
  - Reduce canvas resolution
  - Disable expensive effects
  - Lower video quality/FPS
  - Use lighter codecs (HAP vs H.264)

### Inconsistent timing
- **Cause**: Background processes, thermal throttling
- **Solution**: 
  - Close unnecessary applications
  - Check system temperature
  - Ensure adequate cooling

## See Also

- [agent.md](../agent.md) - Project guidelines and architecture
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [EFFECT_PIPELINE.md](EFFECT_PIPELINE.md) - Effect processing details
- [LAYER_EFFECTS_PLAN.md](LAYER_EFFECTS_PLAN.md) - Layer system architecture
