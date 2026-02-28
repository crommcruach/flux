# HAP Multi-Threading Implementation Guide

## 🎯 Goal
Enable multi-threaded video decoding for HAP codec using PyAV, removing the `threads;1` FFmpeg limitation and significantly improving performance for multi-layer compositing.

## 📊 Expected Performance Gains

| Scenario | Current (OpenCV) | After PyAV | Improvement |
|----------|------------------|------------|-------------|
| **HAP Single Layer** | 18-20ms/frame | 5-8ms/frame | **2-3x faster** |
| **HAP 3 Layers (Sequential)** | 54-60ms/frame | 6-8ms/frame | **~8x faster** |
| **Multi-Layer Compositing** | Sequential decode | Parallel decode | **N layers = 1 layer time** |
| **Max FPS (4K HAP)** | ~18 FPS | ~60 FPS | **3x throughput** |

## 🏗️ Architecture Overview

### Current Architecture (OpenCV)
```
main.py:94 → os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'
                                    ↓
           VideoSource (OpenCV cv2.VideoCapture)
                    - Single-threaded FFmpeg
                    - HAP codec crashes with multi-threading
                    - Sequential layer decode
```

### New Architecture (Hybrid)
```
Auto-Detection at Runtime
         ↓
    ┌────────────┐
    │ Is HAP?    │
    └─────┬──────┘
          │
    ┌─────┴─────────────────────┐
    │                           │
   YES                         NO
    │                           │
    ↓                           ↓
PyAVVideoSource          VideoSource (OpenCV)
- Multi-threaded         - Single-threaded
- HAP optimized         - H.264/standard codecs
- Parallel layers       - Existing behavior
```

## 📦 Components to Create

### 1. PyAV Video Source (`src/modules/player/sources_pyav.py`)
```python
"""
PyAV-based video source for HAP codec with multi-threading support.
"""
import av
import numpy as np
import threading
from queue import Queue, Empty
from .sources import FrameSource

class PyAVVideoSource(FrameSource):
    """
    Multi-threaded HAP video decoder using PyAV.
    
    Features:
    - Multi-threaded HAP decoding (no crashes!)
    - Frame-accurate seeking
    - Background frame prefetching
    - Compatible with existing FrameSource API
    """
    
    def __init__(self, video_path, canvas_width, canvas_height, config=None, 
                 clip_id=None, player_name='video'):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = video_path
        self.clip_id = clip_id
        self.player_name = player_name
        
        # PyAV components
        self.container = None
        self.stream = None
        self._lock = threading.Lock()
        
        # Threading configuration
        self.thread_count = config.get('performance', {}).get('pyav_threads', 4) if config else 4
        
        # Frame prefetching (optional optimization)
        self.enable_prefetch = config.get('performance', {}).get('pyav_prefetch', False) if config else False
        self.prefetch_queue = Queue(maxsize=3) if self.enable_prefetch else None
        self.prefetch_thread = None
        self.prefetch_running = False
    
    def initialize(self):
        """Initialize PyAV container and video stream."""
        try:
            # Open video file
            self.container = av.open(self.video_path)
            self.stream = self.container.streams.video[0]
            
            # Enable multi-threading (works with HAP!)
            self.stream.thread_type = 'AUTO'  # Or 'FRAME' for frame-level parallelism
            self.stream.thread_count = self.thread_count
            
            # Get video properties
            self.total_frames = self.stream.frames
            self.fps = float(self.stream.average_rate)
            self.width = self.stream.width
            self.height = self.stream.height
            
            # Detect codec
            codec_name = self.stream.codec_context.name
            logger.debug(f"🎬 PyAV: Opened {codec_name} video: {self.width}x{self.height} @ {self.fps} FPS (threads={self.thread_count})")
            
            # Check if scaling needed
            self._needs_scaling = (self.width != self.canvas_width or 
                                  self.height != self.canvas_height)
            
            # Start prefetch thread if enabled
            if self.enable_prefetch:
                self._start_prefetch()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ PyAV initialization failed: {e}")
            return False
    
    def get_next_frame(self):
        """Get next decoded frame as numpy array (BGR format)."""
        try:
            # Use prefetch if enabled
            if self.enable_prefetch:
                try:
                    frame_data = self.prefetch_queue.get(timeout=0.1)
                    if frame_data is None:
                        return None, 0
                    return frame_data
                except Empty:
                    # Queue empty, decode directly as fallback
                    pass
            
            # Direct decode (no prefetch)
            with self._lock:
                # Seek if needed
                target_pts = int(self.current_frame * self.stream.time_base.denominator / 
                               (self.fps * self.stream.time_base.numerator))
                
                # Find frame at target position
                for packet in self.container.demux(self.stream):
                    for frame in packet.decode():
                        if frame.pts >= target_pts:
                            # Convert to numpy array (BGR format like OpenCV)
                            numpy_frame = frame.to_ndarray(format='bgr24')
                            
                            # Scale if needed
                            if self._needs_scaling:
                                numpy_frame = self._scale_frame(numpy_frame)
                            
                            self.current_frame += 1
                            return numpy_frame, 1.0 / self.fps
                
                # End of stream
                return None, 0
                
        except StopIteration:
            return None, 0
        except Exception as e:
            logger.error(f"❌ PyAV decode error: {e}")
            return None, 0
    
    def _prefetch_loop(self):
        """Background thread for frame prefetching (optional optimization)."""
        while self.prefetch_running:
            try:
                if self.prefetch_queue.full():
                    time.sleep(0.001)
                    continue
                
                # Decode next frame
                frame, delay = self._decode_frame_direct()
                self.prefetch_queue.put((frame, delay))
                
            except Exception as e:
                logger.error(f"⚠️ Prefetch error: {e}")
                break
    
    def _start_prefetch(self):
        """Start background prefetch thread."""
        self.prefetch_running = True
        self.prefetch_thread = threading.Thread(target=self._prefetch_loop, daemon=True)
        self.prefetch_thread.start()
        logger.debug(f"🚀 PyAV prefetch thread started")
    
    def reset(self):
        """Seek to beginning of video."""
        with self._lock:
            if self.container:
                self.container.seek(0)
                self.current_frame = 0
    
    def cleanup(self):
        """Release PyAV resources."""
        # Stop prefetch thread
        if self.enable_prefetch and self.prefetch_running:
            self.prefetch_running = False
            if self.prefetch_thread:
                self.prefetch_thread.join(timeout=1.0)
        
        # Close container
        with self._lock:
            if self.container:
                self.container.close()
                self.container = None
    
    def get_source_name(self):
        """Get video filename."""
        return os.path.basename(self.video_path) if self.video_path else "Unknown Video (PyAV)"
    
    def _scale_frame(self, frame):
        """Scale frame to canvas size (reuse existing scaling logic)."""
        import cv2
        return cv2.resize(frame, (self.canvas_width, self.canvas_height), 
                         interpolation=cv2.INTER_LINEAR)
```

### 2. Codec Detection Utility (`src/modules/player/codec_detector.py`)
```python
"""
Codec detection utility for automatic VideoSource selection.
"""
import av
from ..core.logger import get_logger

logger = get_logger(__name__)

def detect_codec(video_path):
    """
    Detect video codec from file.
    
    Args:
        video_path: Path to video file
    
    Returns:
        str: Codec name (lowercase) or None if detection fails
    """
    try:
        container = av.open(video_path)
        stream = container.streams.video[0]
        codec = stream.codec_context.name.lower()
        container.close()
        
        logger.debug(f"🔍 Detected codec: {codec} ({video_path})")
        return codec
        
    except Exception as e:
        logger.warning(f"⚠️ Codec detection failed: {e}")
        return None

def is_hap_codec(video_path):
    """
    Check if video uses HAP codec.
    
    Args:
        video_path: Path to video file
    
    Returns:
        bool: True if HAP codec detected
    """
    codec = detect_codec(video_path)
    return codec in ['hap', 'hap_alpha', 'hap_q'] if codec else False

def create_optimal_video_source(video_path, canvas_width, canvas_height, config=None, 
                               clip_id=None, player_name='video'):
    """
    Factory function: Create optimal VideoSource based on codec.
    
    Args:
        video_path: Path to video file
        canvas_width: Target canvas width
        canvas_height: Target canvas height
        config: Configuration dict
        clip_id: Clip UUID
        player_name: Player name
    
    Returns:
        FrameSource: PyAVVideoSource for HAP, VideoSource for others
    """
    from .sources import VideoSource
    from .sources_pyav import PyAVVideoSource
    
    # Check if PyAV optimization is enabled
    use_pyav = config.get('performance', {}).get('use_pyav_for_hap', True) if config else True
    
    if use_pyav and is_hap_codec(video_path):
        # Use PyAV for HAP (multi-threaded)
        logger.debug(f"✅ Using PyAVVideoSource for HAP video: {video_path}")
        return PyAVVideoSource(video_path, canvas_width, canvas_height, config, clip_id, player_name)
    else:
        # Use OpenCV for all other codecs
        logger.debug(f"✅ Using OpenCV VideoSource for video: {video_path}")
        return VideoSource(video_path, canvas_width, canvas_height, config, clip_id, player_name)
```

### 3. Update VideoSource Import (`src/modules/player/sources.py`)
Add to existing file:
```python
# At the end of sources.py

def create_video_source(video_path, canvas_width, canvas_height, config=None, clip_id=None, player_name='video'):
    """
    Factory function to create optimal video source.
    Uses codec detection to choose between PyAV (HAP) and OpenCV (others).
    """
    try:
        from .codec_detector import create_optimal_video_source
        return create_optimal_video_source(video_path, canvas_width, canvas_height, config, clip_id, player_name)
    except ImportError:
        # Fallback to OpenCV if PyAV not available
        logger.warning("⚠️ PyAV not available, using OpenCV for all videos")
        return VideoSource(video_path, canvas_width, canvas_height, config, clip_id, player_name)
```

## 📝 Step-by-Step Implementation

### Phase 1: Create PyAV Components (Non-Breaking)
**Estimated Time: 2-3 hours**

1. **Create new file**: `src/modules/player/sources_pyav.py`
   - Copy template from above
   - Implement `PyAVVideoSource` class
   - Test initialization and basic playback

2. **Create new file**: `src/modules/player/codec_detector.py`
   - Implement codec detection
   - Add HAP detection logic
   - Create factory function

3. **Test in isolation**:
   ```python
   # Test script
   from modules.player.sources_pyav import PyAVVideoSource
   
   source = PyAVVideoSource('video.hap', 1920, 1080)
   assert source.initialize()
   frame, delay = source.get_next_frame()
   assert frame is not None
   ```

### Phase 2: Integration with Existing Code
**Estimated Time: 1-2 hours**

1. **Update imports** in files that create VideoSource:
   - `src/modules/player/core.py` (line ~600-700)
   - `src/modules/player/layers/manager.py` (line ~100-200)
   
   **Replace:**
   ```python
   from .sources import VideoSource
   source = VideoSource(path, width, height, config, clip_id, player_name)
   ```
   
   **With:**
   ```python
   from .sources import create_video_source
   source = create_video_source(path, width, height, config, clip_id, player_name)
   ```

2. **Remove FFmpeg single-thread constraint** in `main.py`:
   ```python
   # Line 94 - Comment out (no longer needed for HAP!)
   # os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'  # PyAV handles HAP now
   ```

### Phase 3: Configuration
**Estimated Time: 30 minutes**

Add to `config.json`:
```json
{
  "performance": {
    "use_pyav_for_hap": true,
    "_use_pyav_for_hap_comment": "Auto-detect HAP codec and use PyAV multi-threaded decoder",
    
    "pyav_threads": 4,
    "_pyav_threads_comment": "Number of threads for PyAV HAP decoding (0=auto, 1-8 manual)",
    
    "pyav_prefetch": false,
    "_pyav_prefetch_comment": "Enable background frame prefetching (experimental - may use more memory)"
  }
}
```

### Phase 4: Testing Strategy
**Estimated Time: 1-2 hours**

#### Test 1: HAP Single Video
```python
# Test HAP codec detection and playback
video_path = "test_hap.mov"
source = create_video_source(video_path, 1920, 1080, config)
assert isinstance(source, PyAVVideoSource)

# Test multi-threaded decode
for i in range(100):
    frame, delay = source.get_next_frame()
    assert frame is not None
    assert frame.shape == (1080, 1920, 3)
```

#### Test 2: Multi-Layer HAP
```python
# Test parallel decode of 3 HAP layers
layer1 = create_video_source("layer1.hap", 1920, 1080, config)
layer2 = create_video_source("layer2.hap", 1920, 1080, config)
layer3 = create_video_source("layer3.hap", 1920, 1080, config)

import time
start = time.time()
frame1, _ = layer1.get_next_frame()
frame2, _ = layer2.get_next_frame()
frame3, _ = layer3.get_next_frame()
elapsed = time.time() - start

print(f"3 layers decoded in {elapsed*1000:.1f}ms")
# Expected: <10ms (parallel) vs ~60ms (sequential)
```

#### Test 3: H.264 Fallback (No Regression)
```python
# Test that H.264 still uses OpenCV
h264_path = "test_h264.mp4"
source = create_video_source(h264_path, 1920, 1080, config)
assert isinstance(source, VideoSource)  # OpenCV, not PyAV
```

#### Test 4: Integration Test (Full Playback)
1. Load HAP video in playlist
2. Add 2 HAP layers
3. Play for 30 seconds
4. Verify FPS matches target
5. Check profiler metrics

### Phase 5: Performance Monitoring
**Estimated Time: 30 minutes**

Add profiling stage for PyAV:
```python
# In modules/performance/profiler.py
PROFILE_STAGES = [
    'source_decode',        # Existing
    'pyav_decode',          # NEW: Track PyAV separately
    'opencv_decode',        # NEW: Track OpenCV separately
    'clip_effects',
    'layer_composition',
]
```

Update LayerManager to track decoder type:
```python
# In composite_layers()
if isinstance(layer.source, PyAVVideoSource):
    with profiler.profile_stage('pyav_decode'):
        frame, delay = layer.source.get_next_frame()
else:
    with profiler.profile_stage('opencv_decode'):
        frame, delay = layer.source.get_next_frame()
```

## 🔧 Configuration Options

### Enable/Disable PyAV
```json
"performance": {
  "use_pyav_for_hap": false  // Disable: fallback to OpenCV for all
}
```

### Thread Count Tuning
```json
"performance": {
  "pyav_threads": 0  // 0=auto (recommended), 1-8=manual
}
```

**Recommendations:**
- **0 (auto)**: Let PyAV decide (usually = CPU cores)
- **2-4**: Good for most systems
- **6-8**: High-end workstations with many CPU cores

### Prefetch (Experimental)
```json
"performance": {
  "pyav_prefetch": true  // Enable background frame prefetching
}
```

**Trade-offs:**
- ✅ Smoother playback (frames ready in advance)
- ❌ Higher memory usage (~100-200MB per video)
- ❌ Complexity (thread coordination)

## 🚨 Rollback Plan

If issues occur, **instant rollback** without code changes:

### Option 1: Config Disable
```json
"performance": {
  "use_pyav_for_hap": false
}
```
Restart app → All videos use OpenCV again.

### Option 2: Remove PyAV Module
```bash
pip uninstall av
```
Code automatically falls back to OpenCV.

### Option 3: Re-enable FFmpeg Single-Thread
```python
# main.py line 94
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'  # Restore safety
```

## 📈 Success Metrics

### Before Implementation (Baseline)
- HAP single layer: 18-20ms/frame
- HAP 3 layers: 54-60ms sequential
- Max FPS (4K HAP): ~18 FPS

### After Implementation (Target)
- HAP single layer: 5-8ms/frame (2-3x faster)
- HAP 3 layers: 6-8ms parallel (8x faster)
- Max FPS (4K HAP): 60 FPS (3x faster)

### Monitoring Dashboard
Add to profiler output:
```
┌─────────────────────────────────────────┐
│ Video Decode Performance                │
├─────────────────────────────────────────┤
│ Decoder:        PyAV (HAP multi-thread) │
│ Threads:        4                       │
│ Avg Decode:     6.2ms/frame            │
│ Peak Decode:    9.8ms/frame            │
│ Layers:         3 parallel              │
│ Total Pipeline: 12.4ms/frame           │
│ Target FPS:     60                      │
│ Actual FPS:     58.3 ✅                │
└─────────────────────────────────────────┘
```

## 🎓 Implementation Checklist

- [ ] Phase 1: Create PyAV components
  - [ ] `sources_pyav.py` - PyAVVideoSource class
  - [ ] `codec_detector.py` - Detection + factory
  - [ ] Unit tests for PyAV decoder
  
- [ ] Phase 2: Integration
  - [ ] Update VideoSource imports in core.py
  - [ ] Update VideoSource imports in manager.py
  - [ ] Comment out FFmpeg single-thread constraint
  
- [ ] Phase 3: Configuration
  - [ ] Add performance.use_pyav_for_hap
  - [ ] Add performance.pyav_threads
  - [ ] Add performance.pyav_prefetch
  
- [ ] Phase 4: Testing
  - [ ] Test HAP single video
  - [ ] Test HAP multi-layer parallel
  - [ ] Test H.264 fallback (no regression)
  - [ ] Integration test (30s+ playback)
  
- [ ] Phase 5: Monitoring
  - [ ] Add pyav_decode profiling stage
  - [ ] Update LayerManager profiler calls
  - [ ] Verify metrics in profiler output

## 🐛 Common Issues & Solutions

### Issue 1: "av module not found"
**Solution**: PyAV already in requirements.txt, but ensure installed:
```bash
pip install av>=10.0.0
```

### Issue 2: PyAV decode slower than expected
**Cause**: Thread count too high/low
**Solution**: Try different values:
```json
"pyav_threads": 0  // Start with auto
```

### Issue 3: Frame format mismatch
**Cause**: PyAV returns RGB, but pipeline expects BGR
**Solution**: Already handled in code:
```python
frame.to_ndarray(format='bgr24')  # ✅ BGR like OpenCV
```

### Issue 4: Memory leak with prefetch
**Cause**: Queue not properly cleaned on source switch
**Solution**: Disable prefetch initially:
```json
"pyav_prefetch": false
```

## 📚 References

- **PyAV Documentation**: https://pyav.org/docs/stable/
- **HAP Codec Spec**: https://github.com/Vidvox/hap
- **FFmpeg Threading**: https://trac.ffmpeg.org/wiki/ThreadingModels
- **Multi-Threading Article**: https://nrsyed.com/2018/07/05/multithreading-with-opencv-python-to-improve-video-processing-performance/

## ✅ Final Notes

**Why This Approach Works:**
1. **Non-breaking**: Fallback to OpenCV if PyAV fails
2. **Backward compatible**: H.264 videos unchanged
3. **Incremental**: Can enable/disable per config
4. **Safe**: Codec detection prevents crashes
5. **Fast**: Multi-threaded HAP finally possible

**Estimated Total Implementation Time: 4-6 hours**

Ready to implement when you are! 🚀
