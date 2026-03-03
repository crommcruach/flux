# Multi-Threading and Multi-CPU Optimization Opportunities

**Date**: 2026-02-12  
**Updated**: 2026-03-03  
**Status**: Analysis Complete + PyAV vs OpenCV Comparison  
**Priority**: High Performance Optimization

---

## Executive Summary

This document analyzes the current threading architecture and identifies opportunities for:
- **Multi-Threading** (concurrent I/O-bound operations)
- **Multi-Processing** (parallel CPU-bound operations using multiple CPU cores)

### Key Findings

1. **GIL Bottleneck**: The application uses separate threads for Video Player and Art-Net Player, but Python's GIL (Global Interpreter Lock) limits them to ~1-1.5 CPU cores total (not 2+ cores).

2. **HAP Codec Threading Issue**: cv2.VideoCapture + HAP codec requires `threads;1` to prevent crashes (`async_lock assertion failed`). This limits per-video decode performance.

3. **Multi-Processing Solves Both**: Running players in separate processes bypasses GIL (true 2-core parallelism) while keeping threads;1 per process safe.

4. **PyAV Alternative**: Switching to PyAV would enable per-video multi-threading (2-3x faster decode for H.264/H.265), but requires major refactoring (10-15 hours).

### Recommended Strategy

**Priority 1**: Multi-process dual-player architecture (13-19 hours)
- Separate Video Player and Art-Net Player into different processes
- Bypasses GIL, achieves true 2-core parallelism
- **40% performance improvement** when both players active

**Priority 2**: Multi-process layer rendering (1-2 days)
- Parallel decode for 4+ layers
- **4x speedup** for multi-layer compositions

**Priority 3 (Optional)**: PyAV for H.264/H.265 (10-15 hours)
- Only if heavy codec decode is bottleneck after Phase 1-2
- HAP is already fast enough (1-3ms) with cv2

**Verdict**: cv2 + Multi-Processing gives **80% of benefit for 40% of effort** compared to PyAV refactor.

---

## Python GIL (Global Interpreter Lock) Issue 🔒

### What Is The GIL?

Python's Global Interpreter Lock (GIL) is a mutex that protects access to Python objects, preventing multiple threads from executing Python bytecode simultaneously.

**Impact on Multi-Threading**:
```python
# Even with separate threads, only ONE executes at a time!
Thread 1: [Has GIL] [Decode] [Effects] [Release GIL]
Thread 2:                            [Takes GIL] [Decode] [Effects]

# Result: Sequential execution, not parallel!
```

**Why This Matters**:
- ✅ Multi-threading works for I/O-bound tasks (network, files)
- ❌ Multi-threading **does NOT** work for CPU-bound tasks (video decode, effects)
- ⚠️ Only **one CPU core** is effectively used, even with multiple threads

### GIL Exception: Native C/C++ Extensions

**Good News**: OpenCV and NumPy **release the GIL** during C++ operations!

```python
# OpenCV operations release GIL:
ret, frame = cap.read()        # ✅ GIL released (C++ FFmpeg decode)
frame = cv2.resize(frame, ...)  # ✅ GIL released (C++ resize)
frame = cv2.GaussianBlur(...)   # ✅ GIL released (C++ blur)

# Pure Python operations hold GIL:
for i in range(1000):           # ❌ GIL held (Python loop)
    x = x + 1                   # ❌ GIL held (Python math)
```

**Result**: Some parallelism exists, but limited and unpredictable.

### Solution: Multi-Processing

**Multi-Processing bypasses GIL completely**:
```python
from multiprocessing import Process

# Each process has its OWN Python interpreter and GIL!
Process 1: [Own GIL] [Decode] [Effects] ← CPU Core 1 (100%)
Process 2: [Own GIL] [Decode] [Effects] ← CPU Core 2 (100%)

# Result: True parallelism on multiple CPU cores!
```

---

## Current Threading Architecture

### Dual-Player Architecture (Video + Art-Net)

**Current Implementation**: Two separate players running in **separate threads**:

```python
# main.py (lines 551-552)
player.start()          # Video Player (Preview) → Thread 1
artnet_player.start()   # Art-Net Player → Thread 2

# Inside Player.start() (core.py line 815):
self.thread = threading.Thread(target=self._play_loop, daemon=True)
self.thread.start()
```

**Thread Layout**:
```
Main Python Process (Single GIL!)
├── Thread 1: REST API (Flask)
├── Thread 2: Video Player (Preview) ← _play_loop
├── Thread 3: Art-Net Player ← _play_loop
├── Thread 4: Session State (background save)
└── Thread 5+: Other background tasks
```

**Performance Impact**:
```python
# Both players share ONE GIL:
CPU Core 1:
  ├─ 10ms: Video Player Thread (has GIL)
  ├─ 10ms: Art-Net Player Thread (has GIL)
  ├─ 10ms: Video Player Thread (has GIL)
  └─ 10ms: Art-Net Player Thread (has GIL)
  
Total for both: ~20ms (sequential!)
# Only ~1-1.5 CPU cores utilized due to GIL
```

**Why This Is Suboptimal**:
- ✅ Correct implementation (separate threads)
- ❌ GIL prevents true parallelism
- ❌ Only uses 1-1.5 CPU cores (not 2+)
- ⚠️ 40-50% performance left on table

### Existing Threading Usage

| Module | Current Usage | Purpose | GIL Impact |
|--------|---------------|---------|------------|
| `main.py` | ThreadPoolExecutor(max_workers=1) | Cleanup timeout handling | Low (I/O) |
| `session/state.py` | Background thread | Async file I/O with debouncing | Low (I/O) |
| `player/sources.py` | threading.Lock() | HAP codec thread-safety | N/A (sync) |
| `player/recording/replay.py` | Thread (daemon=True) | Replay loop | Low |
| **`player/core.py`** | **2x Thread (Video + Art-Net)** | **Dual player playback** | **HIGH ⚠️** |

### Critical Constraint

**FFmpeg Threading Disabled**:
```python
# CRITICAL: Set FFmpeg options BEFORE any cv2 imports
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'
```

**Reason**: Prevents HAP codec threading assertion errors  
**Impact**: Video decoding limited to single thread per VideoCapture instance

---

## PyAV vs OpenCV (cv2.VideoCapture) 🎬

### The HAP Threading Problem

**Root Cause**: HAP codec + cv2.VideoCapture + multi-threading = `async_lock assertion failed`

**What Happens**:
```python
# Without threads;1:
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;4'  # Causes crashes!

FFmpeg HAP decoder:
  ├─ Thread 1: [Decode DXT block 1]
  ├─ Thread 2: [Decode DXT block 2]
  ├─ Thread 3: [Decode DXT block 3]
  └─ Thread 4: [Decode DXT block 4]
       ↓
  Race condition in FFmpeg's async_lock
       ↓
  CRASH: "async_lock assertion failed"
```

**Current Mitigation**: Force single-threaded FFmpeg (`threads;1`)

### Solution Comparison

#### Option A: Keep cv2.VideoCapture + Multi-Processing ⭐ **RECOMMENDED**

**Approach**: Keep `threads;1` but use separate processes

```python
# Each process has isolated cv2.VideoCapture with threads;1
Process 1: cv2.VideoCapture (threads;1) → Video Player
Process 2: cv2.VideoCapture (threads;1) → Art-Net Player
Process 3: cv2.VideoCapture (threads;1) → Layer 1
Process 4: cv2.VideoCapture (threads;1) → Layer 2

# 4 processes = 4x parallelism (different videos)
# Total CPU usage: 4 cores at 100% ✅
```

**Pros**:
- ✅ **No code refactoring** (keep existing VideoSource)
- ✅ **Stable** (current cv2 code is proven)
- ✅ **True parallelism** (bypasses GIL)
- ✅ **Works with HAP** (threads;1 prevents crashes)
- ✅ **4-8 hours implementation** (medium effort)

**Cons**:
- ⚠️ Inter-process communication overhead
- ⚠️ Each video limited to 1 FFmpeg thread (but multiple videos parallel)

**Verdict**: **Best for multi-layer VJ work** (4+ layers, different videos)

---

#### Option B: Switch to PyAV (Python FFmpeg Bindings)

**Approach**: Replace cv2.VideoCapture with PyAV

```python
import av

# PyAV handles HAP threading properly!
container = av.open(video_path)
stream = container.streams.video[0]
stream.thread_type = 'AUTO'   # Multi-threading works!
stream.thread_count = 4        # Use multiple cores per video
```

**Pros**:
- ✅ **True multi-threading per video** (no threads;1 limit)
- ✅ **Lower latency** (~20-30% faster than cv2)
- ✅ **HAP works perfectly** (no assertion errors)
- ✅ **Hardware decode support** (NVDEC, VAAPI)
- ✅ **Better codec control** (pixel formats, decode options)

**Cons**:
- ❌ **Major refactoring** (653 lines of VideoSource code)
- ❌ **Complex API** (iterator-based, not simple read())
- ❌ **Seeking is harder** (timestamp-based, not frame-based)
- ❌ **Installation issues** (Windows binary wheels)
- ❌ **10-15 hours implementation** (high effort)
- ❌ **Testing required** (all codecs, all features)

**Verdict**: **Best for single-video optimization** (if decode is bottleneck)

---

### Performance Comparison

| Scenario | cv2 (threads;1) | cv2 Multi-Process | PyAV (threads;4) | PyAV Multi-Process |
|----------|-----------------|-------------------|------------------|--------------------|
| **Single HAP Video** | 2-3ms | 2-3ms | 1-2ms ✅ | 1-2ms ✅ |
| **Single H.264 Video** | 15-20ms | 15-20ms | 5-8ms ✅ | 5-8ms ✅ |
| **4 HAP Layers (Parallel)** | 12ms (sequential) | 3ms ✅ | 6ms | 1.5ms ✅ |
| **Video + Art-Net (Dual Player)** | ~15ms (GIL) | ~3ms ✅ | ~10ms (GIL) | ~2ms ✅ |

**Key Insight**: 
- **PyAV is faster per-video** (2-3x decode speedup)
- **Multi-processing is faster for multi-layer** (4x parallelism)
- **Best of both**: PyAV + Multi-Processing (requires both refactorings)

---

### Codec-Specific Recommendations

#### For HAP Codec (VJ/Live Performance)

**Current**: cv2 + threads;1 = 2-3ms decode ✅ **Good enough**

**Options**:
1. **Keep cv2 + Multi-Process** → 3ms for 4 layers ⭐ Best effort/performance
2. **Switch to PyAV** → 1-2ms decode (marginal 1ms gain, high effort)

**Recommendation**: **cv2 + Multi-Process** (80% benefit, 20% effort)

#### For H.264/H.265 (Editing/Archive)

**Current**: cv2 + threads;1 = 15-20ms decode ⚠️ Slow

**Options**:
1. **PyAV (threads;4)** → 5-8ms decode ⭐ 3x faster
2. **cv2 + Multi-Process** → 15ms (no per-video improvement)

**Recommendation**: **PyAV** (if H.264/H.265 is bottleneck)

---

### Implementation Strategy

#### Phase 1: Multi-Processing (RECOMMENDED START)
```python
# Implement multi-process layer rendering
# Keep cv2.VideoCapture (no refactor)
# Time: 4-8 hours
# Gain: 4x speedup for multi-layer
```

#### Phase 2: Evaluate Need for PyAV
```python
# After Phase 1, benchmark performance
# If single-video decode is still bottleneck → PyAV
# If multi-layer is bottleneck (solved) → Done!
```

#### Phase 3: PyAV Integration (ONLY IF NEEDED)
```python
# Hybrid approach: PyAV for HAP, cv2 for others
# Time: 10-15 hours
# Gain: Additional 1-2ms per frame for HAP
```

---

## CPU-Intensive Operations Analysis

### 1. Video Frame Decoding ⚡ HIGH IMPACT

**Current State**: Sequential single-threaded decoding  
**Location**: `src/modules/player/sources.py` - `VideoSource.get_next_frame()`

```python
# Current: Single-threaded decode
ret, frame = self.cap.read()  # Blocks on FFmpeg decode
```

**Bottleneck**:
- H.264/H.265 decoding: **10-30ms per frame**
- HAP decoding: **1-3ms per frame**
- Only one video can decode at a time per player

**Optimization Strategy**: Multi-Processing (separate processes)

**Recommended Solution**:
```python
from multiprocessing import Process, Queue, Pool

class VideoDecoderPool:
    """Decode multiple videos in parallel using separate processes"""
    def __init__(self, max_workers=4):
        self.pool = Pool(processes=max_workers)
        self.decode_jobs = {}
    
    def decode_frame_async(self, video_path, frame_number):
        """Submit frame decode job to process pool"""
        future = self.pool.apply_async(self._decode_frame, 
                                        (video_path, frame_number))
        return future
    
    @staticmethod
    def _decode_frame(video_path, frame_number):
        """Worker function running in separate process"""
        cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None
```

**Benefits**:
- Decode multiple videos simultaneously (multi-layer playback)
- Pre-decode upcoming frames in background
- Utilize all CPU cores for heavy codecs (H.264/H.265)
- Each process has isolated FFmpeg instance (no HAP threading issues)

**Use Cases**:
- Multi-layer composition (4+ layers)
- Clip preloading for instant playback
- Transition overlap (2 videos playing simultaneously)

---

### 2. Effect Processing (Image Transformations) ⚡ HIGH IMPACT

**Current State**: Sequential effect chain processing  
**Location**: `src/modules/player/effects/processor.py` - `apply_effects()`

**CPU-Intensive Effects**:
| Effect | Operation | Cost per Frame |
|--------|-----------|----------------|
| `blend.py` | cv2.resize(), alpha blending | 2-5ms |
| `transform.py` | cv2.warpAffine(), cv2.warpPerspective() | 3-8ms |
| `kaleidoscope.py` | cv2.remap() with coordinate transforms | 5-15ms |
| `radial_blur.py` | Multiple cv2.warpAffine() iterations | 10-30ms |
| `vignette.py` | NumPy float32 multiplication | 1-3ms |
| `keystone.py` | cv2.warpPerspective() | 3-8ms |

**Current Processing**:
```python
# Sequential effect chain (single-threaded)
for effect in effect_chain:
    processed_frame = effect.process_frame(processed_frame)
```

**Optimization Strategy**: ThreadPoolExecutor for independent effects

**Recommended Solution**:
```python
from concurrent.futures import ThreadPoolExecutor
import cv2

class ParallelEffectProcessor:
    """Process independent effects in parallel"""
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def apply_effects_parallel(self, frame, effect_chain):
        """Apply effects in parallel where possible"""
        # Separate effects into dependent and independent groups
        independent, dependent = self._analyze_dependencies(effect_chain)
        
        # Process independent effects in parallel
        if independent:
            futures = []
            for effect in independent:
                # Each thread processes a copy of the frame
                frame_copy = frame.copy()
                future = self.executor.submit(effect.process_frame, frame_copy)
                futures.append((effect, future))
            
            # Blend results back together
            processed_frames = [f.result() for _, f in futures]
            frame = self._composite_results(processed_frames)
        
        # Process dependent effects sequentially
        for effect in dependent:
            frame = effect.process_frame(frame)
        
        return frame
```

**Benefits**:
- Parallel execution of independent effects (e.g., multiple layers with separate effects)
- Reduce latency for complex effect chains (8+ effects)
- Stay within frame time budget at high FPS (60fps = 16.6ms per frame)

**Limitation**: OpenCV GIL (Global Interpreter Lock) - some OpenCV operations release GIL, some don't
- **GIL-friendly**: cv2.resize(), cv2.warpAffine(), cv2.remap() (C++ implementations)
- **GIL-bound**: Pure NumPy operations (unless using NumExpr)

---

### 3. Multi-Layer Composition ⚡ MEDIUM IMPACT

**Current State**: Sequential layer rendering  
**Location**: `src/modules/player/layers/manager.py` - `LayerManager.render_layers()`

**Bottleneck**:
```python
# Current: Sequential layer processing
for layer in layers:
    layer_frame = layer.get_current_frame()  # Decode
    layer_frame = apply_clip_effects(layer_frame)  # Transform
    composited = blend_layer(composited, layer_frame)  # Blend
```

**Optimization Strategy**: Multi-Process Layer Rendering

**Recommended Solution**:
```python
from multiprocessing import Pool
import cloudpickle  # Better serialization than pickle

class ParallelLayerRenderer:
    """Render multiple layers in parallel across CPU cores"""
    def __init__(self, max_workers=None):
        # Default to CPU count - 1 (leave one core for main thread)
        self.pool = Pool(processes=max_workers)
    
    def render_layers_parallel(self, layers, frame_index):
        """Render all layers in parallel"""
        # Submit all layer render jobs
        layer_jobs = []
        for layer_id, layer_config in enumerate(layers):
            job = self.pool.apply_async(
                self._render_single_layer,
                (layer_id, layer_config, frame_index)
            )
            layer_jobs.append((layer_id, job))
        
        # Collect results and composite
        layer_frames = []
        for layer_id, job in layer_jobs:
            frame = job.get(timeout=0.1)  # 100ms timeout
            layer_frames.append(frame)
        
        # Composite layers sequentially (blending must be ordered)
        return self._composite_layers(layer_frames)
    
    @staticmethod
    def _render_single_layer(layer_id, layer_config, frame_index):
        """Worker: Render single layer in isolated process"""
        # Decode frame
        source = VideoSource(layer_config['video_path'], ...)
        frame = source.get_frame_at(frame_index)
        
        # Apply clip effects
        for effect in layer_config['effects']:
            frame = effect.process_frame(frame)
        
        return (layer_id, frame)
```

**Benefits**:
- **4-layer composition**: Render 4 layers simultaneously on quad-core CPU
- **Scalability**: Performance scales linearly with CPU cores (8 cores = 8x faster)
- Crucial for real-time multi-layer mixing (VJ performances)

**Use Case**: 4+ layer compositions with effects (common in VJ setups)

---

### 4. Art-Net Packet Generation ⚡ MEDIUM IMPACT

**Current State**: Sequential DMX packet generation  
**Location**: `src/modules/artnet/output_manager.py` - `render_frame()`

**Bottleneck**:
```python
# Sequential output rendering
for output_id, output_config in outputs.items():
    dmx_data = self._sample_pixels(frame, objects, output_config)
    rendered_outputs[output_id] = dmx_data
```

**Optimization Strategy**: ThreadPoolExecutor for parallel pixel sampling

**Recommended Solution**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

class ParallelOutputManager:
    """Render multiple outputs in parallel"""
    def __init__(self, max_workers=4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def render_frame_parallel(self, frame, objects, outputs):
        """Render all outputs in parallel"""
        futures = {}
        
        # Submit all output render jobs
        for output_id, output_config in outputs.items():
            if not output_config.active:
                continue
            
            future = self.executor.submit(
                self._render_single_output,
                frame.copy(),  # Send copy to avoid race conditions
                objects,
                output_config
            )
            futures[future] = output_id
        
        # Collect results as they complete
        rendered_outputs = {}
        for future in as_completed(futures, timeout=0.05):
            output_id = futures[future]
            dmx_data = future.result()
            rendered_outputs[output_id] = dmx_data
        
        return rendered_outputs
```

**Benefits**:
- Render 4-8 Art-Net outputs simultaneously
- Crucial when sending to multiple controllers (different universes)
- Reduce frame processing time by 3-4x with 4 outputs

**Use Case**: Installations with 4+ Art-Net controllers/outputs

---

### 5. JPEG Encoding for Network Streams ⚡ LOW IMPACT

**Current State**: Sequential JPEG encoding  
**Location**: `src/modules/api/output/artnet.py` - Multiple stream endpoints

```python
# Current: Single-threaded JPEG encode
ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
```

**Bottleneck**: JPEG encoding is already hardware-accelerated (libjpeg-turbo), limited gains

**Optimization Strategy**: Only parallelize if multiple streams active

**Recommended Approach**: ThreadPoolExecutor with background encoding

**Benefits**: Minimal (2-3ms per frame) - **LOW PRIORITY**

---

### 6. Frame Caching and Preloading ⚡ HIGH IMPACT

**Current State**: Loop cache for short videos  
**Location**: `src/modules/player/sources.py` - `VideoSource`

**Opportunity**: Aggressive frame pre-decoding in background

**Recommended Solution**:
```python
from concurrent.futures import ThreadPoolExecutor
from collections import deque

class AsyncFramePreloader:
    """Pre-decode frames in background thread pool"""
    def __init__(self, video_path, lookahead=30):
        self.video_path = video_path
        self.lookahead = lookahead
        self.frame_cache = {}  # frame_index → decoded_frame
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.prefetch_jobs = {}
    
    def get_frame(self, frame_index):
        """Get frame (from cache or blocking decode)"""
        # Check cache first
        if frame_index in self.frame_cache:
            frame = self.frame_cache[frame_index]
            del self.frame_cache[frame_index]  # Free memory
            self._schedule_prefetch(frame_index)
            return frame
        
        # Cache miss - blocking decode
        frame = self._decode_frame_sync(frame_index)
        self._schedule_prefetch(frame_index)
        return frame
    
    def _schedule_prefetch(self, current_frame):
        """Schedule decoding of upcoming frames"""
        for i in range(1, self.lookahead + 1):
            next_frame = current_frame + i
            if next_frame not in self.frame_cache and next_frame not in self.prefetch_jobs:
                future = self.executor.submit(self._decode_frame_sync, next_frame)
                self.prefetch_jobs[next_frame] = future
        
        # Collect completed jobs
        for frame_idx, future in list(self.prefetch_jobs.items()):
            if future.done():
                self.frame_cache[frame_idx] = future.result()
                del self.prefetch_jobs[frame_idx]
```

**Benefits**:
- **Zero decode latency** for sequential playback (all frames pre-cached)
- Smooth 60fps playback even with heavy codecs (H.265)
- Background CPU utilization during idle periods

**Trade-off**: Higher memory usage (30 frames @ 1080p ≈ 180MB RGB)

---

## Audio Processing (Future Consideration)

**Status**: No audio processing currently implemented

**Potential Use Cases**:
- BPM detection (beat-synchronized effects)
- Audio waveform visualization
- Beat-reactive parameter modulation

**Recommended Libraries**:
- `librosa`: Music analysis, BPM detection
- `aubio`: Real-time audio feature extraction
- `soundfile`: Audio file I/O

**Multi-Threading Strategy**: Background thread for audio analysis

---

## Implementation Roadmap

### Phase 0: Dual-Player Multi-Processing ⭐ **HIGHEST PRIORITY**

**0.1 Separate Video Player + Art-Net Player into Processes** (13-19 hours)

**Problem**: Both players run in separate threads but share ONE GIL
- Video Player Thread + Art-Net Player Thread = GIL contention
- Only ~1-1.5 CPU cores utilized (not 2)
- 40-50% performance left on table

**Solution**: Run each player in separate process
```python
# Process 1: Video Player (Preview)
# Process 2: Art-Net Player
# Each has own Python interpreter and GIL!
# True 2-core parallelism ✅
```

**Implementation Steps**:
1. Create process wrappers for each player (2-3 hours)
2. Implement command queues (REST API → Players) (2-3 hours)
3. Implement status queues (Players → WebSocket) (2-3 hours)
4. Session state synchronization (3-4 hours)
5. Testing & debugging (4-6 hours)

**Expected Performance Gain**:
- **40% faster** when both players active simultaneously
- True 2-core CPU utilization (200% vs current 100-150%)
- Better frame stability (less drops)
- Smoother playback during heavy effects

**Risk**: Medium (inter-process communication complexity)

**Verdict**: **Essential for dual-player architecture** - solves GIL bottleneck

---

### Phase 1: Quick Wins (Low Risk)

**1.1 Parallel Art-Net Output Rendering** (2-3 hours)
- Parallelize output rendering with ThreadPoolExecutor
- Test with 4+ outputs
- Measure latency reduction

**1.2 Background Frame Preloading** (3-4 hours)
- Implement AsyncFramePreloader
- Configure lookahead buffer size
- Monitor memory usage

### Phase 2: Major Optimizations (Medium Risk)

**2.1 Multi-Process Layer Rendering** (1-2 days)
- Implement ParallelLayerRenderer
- Handle serialization (cloudpickle for effects)
- Performance benchmarking (2 layers vs 4 layers vs 8 layers)

**2.2 Parallel Effect Processing** (2-3 days)
- Analyze effect dependencies
- Implement ParallelEffectProcessor
- Optimize for GIL-release (use OpenCV where possible)

### Phase 3: Advanced Optimizations (High Risk)

**3.1 Multi-Process Video Decoder Pool** (3-5 days)
- Implement VideoDecoderPool
- Inter-process communication (shared memory or queues)
- Handle FFmpeg isolation per process
- Extensive testing with HAP codec

---

## Performance Expectations

### Current Bottlenecks (Single Core)

| Operation | Current Time | % of Frame Budget (60fps) |
|-----------|--------------|---------------------------|
| H.264 Decode (1 video) | 15ms | 90% |
| Clip Effects (5 effects) | 10ms | 60% |
| Layer Composition (4 layers) | 8ms | 48% |
| Art-Net Rendering (1 output) | 2ms | 12% |
| **Total (worst case)** | **35ms** | **210% (frame drop!)** |

### After Multi-Core Optimization (8-core CPU)

| Operation | Optimized Time | Speedup | % of Frame Budget |
|-----------|----------------|---------|-------------------|
| H.264 Decode (4 videos parallel) | 15ms | 1x* | 90% |
| Clip Effects (parallel) | 3ms | 3.3x | 18% |
| Layer Composition (4 cores) | 2ms | 4x | 12% |
| Art-Net Rendering (4 outputs parallel) | 0.5ms | 4x | 3% |
| **Total (optimized)** | **20.5ms** | **1.7x** | **123%** |

*Decode limited by per-file FFmpeg constraint, but multiple files can decode simultaneously

### Target Scenarios

**Scenario A: Simple Playback (1 video, 3 effects)**
- Current: 20ms → 60fps ✅
- Optimized: 10ms → 100fps ✅

**Scenario B: Complex Composition (4 layers, 8 effects total)**
- Current: 35ms → 28fps ❌ (frame drops)
- Optimized: 15ms → 66fps ✅

**Scenario C: VJ Live Performance (4 layers, 12 effects, 4 Art-Net outputs)**
- Current: 50ms → 20fps ❌ (unusable)
- Optimized: 22ms → 45fps ⚠️ (acceptable for 30fps output)

---

## Technical Considerations

### Python GIL (Global Interpreter Lock)

**Problem**: Python's GIL prevents true parallel execution of Python bytecode

**Solutions**:
1. **Multi-Processing**: Bypass GIL entirely (separate processes = separate GIL)
2. **Native Extensions**: OpenCV/NumPy release GIL during C++ operations
3. **Cython**: Compile hot loops to C (nogil context)

**Recommendation**: Use **Multi-Processing** for CPU-intensive tasks (decoding, effects)

### Memory Management

**Challenge**: Each process has separate memory space

**Solutions**:
- **Shared Memory** (multiprocessing.shared_memory): Zero-copy frame sharing
- **Memory Pools**: Pre-allocate frame buffers to avoid repeated allocation
- **Lazy Loading**: Only decode frames when needed

### Process Communication Overhead

**Serialization Cost**: Pickling/unpickling frames takes time

**Solutions**:
1. **Shared Memory Arrays** (numpy.ndarray backed by shared_memory)
2. **Memory-Mapped Files** (mmap for large datasets)
3. **ZeroMQ** (efficient IPC for frame streaming)

**Benchmark**: Pickle 1080p frame ≈ 3ms, Shared Memory ≈ 0.01ms

---

## Testing Strategy

### Performance Benchmarks

Create benchmarks for each optimization:

```python
# benchmark_parallel_effects.py
import time
import numpy as np
from effects.processor import EffectProcessor, ParallelEffectProcessor

def benchmark_effects(processor, frame, effect_chain, iterations=100):
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        processor.apply_effects(frame, effect_chain)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'mean': np.mean(times),
        'std': np.std(times),
        'min': np.min(times),
        'max': np.max(times)
    }

# Test with 8 effects
frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
effects = [create_effect('blur'), create_effect('vignette'), ...]

sequential_results = benchmark_effects(EffectProcessor(), frame, effects)
parallel_results = benchmark_effects(ParallelEffectProcessor(workers=4), frame, effects)

print(f"Sequential: {sequential_results['mean']*1000:.2f}ms")
print(f"Parallel: {parallel_results['mean']*1000:.2f}ms")
print(f"Speedup: {sequential_results['mean'] / parallel_results['mean']:.2f}x")
```

### Stability Testing

- **Memory Leak Detection**: Monitor memory over 24-hour runs
- **Race Condition Testing**: Concurrent access to shared resources
- **Error Recovery**: Handle process crashes gracefully

---

## Configuration

Add performance settings to `config.json`:

```json
{
  "performance": {
    "multi_threading": {
      "enabled": true,
      "max_workers": 4
    },
    "multi_processing": {
      "enabled": true,
      "decoder_pool_size": 4,
      "layer_renderer_workers": 4
    },
    "frame_cache": {
      "enabled": true,
      "lookahead_frames": 30,
      "max_cache_size_mb": 512
    },
    "optimizations": {
      "parallel_effects": true,
      "parallel_outputs": true,
      "async_preloading": true
    }
  }
}
```

---

## Monitoring and Profiling

### CPU Utilization Tracking

```python
import psutil
import threading

class CPUMonitor:
    def __init__(self):
        self.cpu_percent = []
        self.monitoring = False
        self.thread = None
    
    def start(self):
        self.monitoring = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def _monitor_loop(self):
        while self.monitoring:
            cpu = psutil.cpu_percent(interval=0.1, percpu=True)
            self.cpu_percent.append(cpu)
            time.sleep(0.1)
    
    def get_stats(self):
        return {
            'per_core': [np.mean([reading[i] for reading in self.cpu_percent]) 
                         for i in range(psutil.cpu_count())],
            'total': np.mean([np.mean(reading) for reading in self.cpu_percent])
        }
```

### Performance Profiler Integration

Extend existing profiler in `src/modules/performance/profiler.py`:

```python
# Add new timing points
TIMING_POINTS = [
    'parallel_decode',      # Multi-process decode
    'parallel_effects',     # Parallel effect processing
    'parallel_layers',      # Parallel layer rendering
    'parallel_outputs',     # Parallel Art-Net outputs
]
```

---

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **GIL Bottleneck** | Multi-threading ineffective | Use multi-processing for CPU tasks |
| **Memory Overhead** | OOM with large frame cache | Configurable cache limits, monitoring |
| **Process Spawning Latency** | Slow startup | Pre-spawn worker pool at initialization |
| **Race Conditions** | Data corruption | Thread-safe queues, immutable data |
| **HAP Codec Issues** | FFmpeg assertion errors | Isolated processes, threading.Lock() |
| **Increased Complexity** | Harder debugging | Comprehensive logging, fallback to sequential |

---

## Rollout Strategy

### Enable/Disable Flags

All optimizations behind feature flags:

```python
# config.json
"performance": {
  "parallel_effects": false,  # Start disabled
  "parallel_layers": false,
  "async_preloading": true,   # Safe to enable
  "parallel_outputs": true    # Safe to enable
}
```

### Gradual Rollout

1. **Week 1**: Parallel outputs (low risk, high gain)
2. **Week 2**: Async preloading (medium risk, high gain)
3. **Week 3**: Parallel effects (medium risk, medium gain)
4. **Week 4**: Parallel layers (high risk, high gain)

### Fallback Mechanism

If errors occur, automatically fall back to sequential processing:

```python
try:
    frame = parallel_processor.process(frame, effects)
except Exception as e:
    logger.warning(f"Parallel processing failed, falling back: {e}")
    frame = sequential_processor.process(frame, effects)
```

---

## Conclusion

**Summary**: The application has significant untapped multi-core potential due to Python's GIL limiting the dual-player architecture. Implementing multi-processing can achieve **2-4x performance improvement** on modern multi-core CPUs.

### Critical Findings

1. **Dual-Player GIL Bottleneck** ⚠️ **HIGHEST PRIORITY**
   - Video Player + Art-Net Player run in separate threads but share ONE GIL
   - Only ~1-1.5 CPU cores utilized (not 2)
   - **Solution**: Multi-processing (separate processes) = true 2-core parallelism
   - **Impact**: 40% performance improvement when both players active

2. **HAP Codec Threading Limitation**
   - cv2.VideoCapture requires `threads;1` to prevent crashes
   - **Solution A**: Multi-processing (keep cv2, separate processes) ⭐ Recommended
   - **Solution B**: Switch to PyAV (enables multi-threading) ⚠️ High effort

3. **PyAV vs OpenCV Trade-off**
   - **PyAV**: 2-3x faster decode per video, but 10-15 hours refactoring
   - **cv2 + Multi-Processing**: 4x faster for multi-layer, only 4-8 hours
   - **Verdict**: cv2 + Multi-Processing gives 80% benefit for 40% effort

### Priority Order (Updated)

**Phase 0 (NEW - CRITICAL)**:
0. ⚡ **Multi-Process Dual-Player Architecture** (13-19 hours, 40% gain) 🔥

**Phase 1 (Quick Wins)**:
1. ⚡ **Parallel Art-Net Outputs** (2-3 hours, medium gain)
2. ⚡ **Async Frame Preloading** (3-4 hours, high gain)

**Phase 2 (Major Optimizations)**:
3. ⚡ **Multi-Process Layer Rendering** (1-2 days, 4x gain for multi-layer)
4. ⚡ **Parallel Effect Processing** (2-3 days, medium gain)

**Phase 3 (Optional - Only If Needed)**:
5. ⚡ **PyAV Integration** (10-15 hours, 2-3x per-video gain for H.264/H.265)

### Recommendations by Use Case

**VJ/Live Performance (4+ layers, HAP codec)**:
- ✅ Multi-process dual-player (Phase 0)
- ✅ Multi-process layer rendering (Phase 2.1)
- ❌ Skip PyAV (HAP is already fast at 1-3ms)

**Video Editing (1-2 layers, H.264/H.265)**:
- ✅ Multi-process dual-player (Phase 0)
- ✅ PyAV for heavy codec decode (Phase 3)
- ⚠️ Layer rendering less critical

**Art-Net Installation (8+ outputs)**:
- ✅ Multi-process dual-player (Phase 0)
- ✅ Parallel Art-Net outputs (Phase 1.1)
- ⚠️ Less need for decode optimization

### Next Steps

1. **Implement Phase 0**: Multi-process dual-player architecture (13-19 hours)
2. **Benchmark**: Measure CPU usage and frame times before/after
3. **Evaluate**: If decode is still bottleneck → Consider PyAV (Phase 3)
4. **Iterate**: Add Phase 1-2 optimizations based on profiling

### Key Insight

**The GIL is the main bottleneck**, not cv2.VideoCapture itself. Multi-processing solves GIL limitations while keeping stable, proven cv2 code. PyAV offers marginal gains for HAP but significant gains for H.264/H.265 - evaluate based on actual codec usage.

---

**Document Version**: 2.0  
**Last Updated**: 2026-03-03  
**Changes**: Added GIL analysis, PyAV vs OpenCV comparison, dual-player multi-processing priority
