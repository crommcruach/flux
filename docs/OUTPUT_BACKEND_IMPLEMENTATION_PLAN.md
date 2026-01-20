# 🎯 Output Backend Implementation Plan

## 📊 Current State Analysis

### ✅ What We Already Have:

1. **Frontend (Complete)**
   - ✅ [output-settings.html](../frontend/output-settings.html) - Slice editor UI (2546 lines)
   - ✅ [output-settings.css](../frontend/css/output-settings.css) - Styling (543 lines)
   - ✅ [output-settings.js](../frontend/js/output-settings.js) - Slice management logic
   - ✅ Features: Rectangle/Polygon/Circle slices, masks, soft edges, multi-screen assignment
   - ✅ Export/Import JSON for slice configurations

2. **Documentation (Complete)**
   - ✅ [OUTPUT_ROUTING_IMPLEMENTATION.md](OUTPUT_ROUTING_IMPLEMENTATION.md) - Comprehensive guide (1169 lines)
   - ✅ 5-phase implementation strategy with code examples
   - ✅ Architecture diagrams and API specifications

3. **Player Infrastructure**
   - ✅ [player_core.py](../src/modules/player_core.py) - Unified player with frame pipeline (1706 lines)
   - ✅ Frame sources: VideoSource, GeneratorSource
   - ✅ Effect processing pipeline (video/artnet chains)
   - ✅ Layer system with compositing
   - ✅ Canvas dimensions (self.canvas_width, self.canvas_height)
   - ✅ Frame output ready (`processed_frame` as numpy array)

4. **Configuration System**
   - ✅ [config.json](../config.json) - Structured config with validation
   - ✅ Video section with resolution settings
   - ✅ Art-Net section with universe configs
   - ✅ Effects chains (video/artnet/clips)

5. **Related Systems**
   - ✅ Screen capture plugin ([screencapture.py](../plugins/generators/screencapture.py)) using MSS library
   - ✅ Art-Net output infrastructure (DMX output working)
   - ✅ Plugin architecture for generators/effects/transitions
   - ✅ REST API framework with WebSocket support
   - ✅ Points loader for LED mapping

### ❌ What We DON'T Have:

1. **Backend Modules** (Phase 1 - COMPLETED ✅)
   - ✅ `src/modules/outputs/` directory
   - ✅ Output manager system
   - ✅ Slice manager (backend slice processing)
   - ✅ Display output plugins
   - ✅ Video output routing

2. **API Endpoints** (Phase 2 - COMPLETED ✅)
   - ✅ `/api/outputs/*` - Output management endpoints
   - ✅ `/api/slices/*` - Slice CRUD endpoints
   - ✅ `/api/monitors` - Available display detection

3. **Player Integration** (Phase 3 - COMPLETED ✅)
   - ✅ Output manager initialization in player_core.py
   - ✅ Frame distribution to multiple outputs
   - ✅ Slice extraction and routing
   - ✅ Session state integration

4. **Configuration** (Phase 3 - COMPLETED ✅)
   - ✅ `output_routing` section in config.json
   - ✅ Output definitions with source routing
   - ✅ Slice definitions

5. **Monitor Detection** (Phase 1 - COMPLETED ✅)
   - ✅ Monitor enumeration (screeninfo added to requirements.txt)
   - ✅ Display position/resolution detection

6. **Professional Video Routing** (NOT IMPLEMENTED - Future Enhancement)
   - ❌ No NDI output support (ndi-python not in requirements.txt)
   - ❌ No Spout output support (SpoutGL not in requirements.txt)
   - ❌ No network video streaming
   - ❌ No GPU texture sharing

7. **Session State Integration** (Phase 3 - COMPLETED ✅)
   - ✅ Session state system exists ([session_state.py](../src/modules/session_state.py))
   - ✅ Session state saved to [session_state.json](../session_state.json)
   - ✅ Output settings included in session state
   - ✅ Slice definitions persisted across sessions

---

## � Clip & Layer Routing Feature

### Overview

In addition to slicing the canvas, the output system supports routing individual **clips** and **layers** to different screens. This enables powerful VJ workflows:

- **Multi-screen VJ setups**: Send different layers to different projectors
- **Clip preview**: Dedicated screen showing current clip (before layer compositing)
- **Background isolation**: Output only background layer to LED wall
- **Effect separation**: Overlay effects on one screen, clean output on another

### Source Types

Each output can display content from three different sources:

1. **`canvas`** - Full composited canvas (all layers combined)
   - Default behavior
   - Shows final output with all effects and layers
   - Can be sliced (e.g., left half to screen 1, right half to screen 2)

2. **`clip:<clip_id>`** - Individual clip (before layer compositing)
   - `clip:current` - Currently active clip
   - `clip:<uuid>` - Specific clip by UUID
   - Useful for preview monitors
   - Shows raw clip without layer effects

3. **`layer:<index>`** - Explicit single layer output (ISOLATED)
   - `layer:0` - Background layer ONLY (isolated from other layers)
   - `layer:1` - Overlay layer 1 ONLY (isolated)
   - `layer:2` - Overlay layer 2 ONLY (isolated)
   - `layer:N` - Any layer N ONLY (isolated)
   - **Each layer outputs independently** - no compositing with other layers
   - **Perfect for parallel processing** - send different layers to different screens
   - **Layers can be sliced** - apply slices to individual layers
   - **Use case**: Separate control over each visual element

4. **`layer:<index>:inclusive`** - Hierarchical layer composite (NEW)
   - `layer:3:inclusive` - Outputs layers 0-3 composited with blend modes
   - `layer:5:inclusive` - Outputs layers 0-5 composited with blend modes
   - Respects layer blend modes (add, multiply, screen, etc.)
   - Allows outputting partial layer stacks
   - Perfect for complex multi-output setups

### Configuration Examples

**Example 1: Hierarchical layer output** (NEW)
```json
{
  "outputs": {
    "main_screen": {
      "source": "canvas",
      "slice": "full",
      "monitor_index": 0,
      "_comment": "Full canvas with all layers"
    },
    "led_wall": {
      "source": "layer:3:inclusive",
      "slice": "full",
      "monitor_index": 1,
      "_comment": "Layers 0-3 composited (background + 3 overlays)"
    },
    "single_effect": {
      "source": "layer:4",
      "slice": "full",
      "monitor_index": 2,
      "_comment": "Only layer 4 (single layer, no compositing)"
    }
  }
}3
```

**Example 2: Explicit layer separation** (Multi-layer VJ setup)
```json
{
  "outputs": {
    "main_screen": {
      "source": "canvas",
      "slice": "full",
      "monitor_index": 0,
      "_comment": "Full composite (all layers together)"
    },
    "background_wall": {
      "source": "layer:0",
      "slice": "full",
      "monitor_index": 1,
      "_comment": "EXPLICIT: Background layer ONLY (isolated)"
    },
    "overlay_projector": {
      "source": "layer:1",
      "slice": "full",
      "monitor_index": 2,
      "_comment": "EXPLICIT: Overlay layer 1 ONLY (isolated)"
    },
    "effects_screen": {
      "source": "layer:2",
      "slice": "full",
      "monitor_index": 3,
      "_comment": "EXPLICIT: Effects layer 2 ONLY (isolated)"
    }
  }
}
```

**Example 2: Clip preview + sliced output**
```json
{
  "outputs": {
    "preview_monitor": {
      "source": "clip:current",
      "slice": "full",
      "monitor_index": 0,
      "resolution": [640, 360]
    },
    "left_projector": {
      "source": "canvas",
      "slice": "left_half",
      "monitor_index": 1
    },
    "right_projector": {
      "source": "canvas",
      "slice": "right_half",
      "monitor_index": 2
    }
  }
}
```

**Example 4: Layer + slice combination**
```json
{
  "outputs": {
    "led_strip_left": {
      "source": "layer:0",
      "slice": "left_strip",
      "monitor_index": 1
    },
    "led_strip_right": {
      "source": "layer:1",
      "slice": "right_strip",
      "monitor_index": 1
    }
  }
}
```

### Implementation Details

**Output Manager receives:**
- `composite_frame` - Full canvas (all layers composited)
- `layer_manager` - Reference to layer system
- `current_clip_id` - Active clip UUID

**Frame extraction logic:**
```python
def get_frame_for_output(self, output_config):
    """Get frame based on output source configuration"""
    source = output_config.get('source', 'canvas')
    
    if source == 'canvas':
        # Full composited canvas
        frame = self.composite_frame
    
    elif source.startswith('clip:'):
        clip_id = source.split(':')[1]
        if clip_id == 'current':
            # Get current active clip
            frame = self.layer_manager.get_current_clip_frame()
        else:
            # Get specific clip by UUID
            frame = self.layer_manager.get_clip_frame(clip_id)
    
    elif source.startswith('layer:'):
        # Parse layer specification
        parts = source.split(':')
        layer_index = int(parts[1])
        include_sub_layers = len(parts) > 2 and parts[2] == 'inclusive'
        
        if include_sub_layers:
            # Composite layers 0 through layer_index with blend modes
            # This creates a hierarchical output (e.g., layer:3:inclusive = layers 0+1+2+3)
            frame = self.layer_manager.composite_layers_through(layer_index)
        else:
            # Get specific layer only (no compositing)
            frame = self.layer_manager.get_layer_frame(layer_index)
    
    else:
        # Fallback to canvas
        frame = self.composite_frame
    
    # Apply slice if configured
    slice_id = output_config.get('slice', 'full')
    if slice_id != 'full':
        frame = self.slice_manager.get_slice(slice_id, frame)
    
    return frame
```

**Layer Manager method (to be added):**
```python
def composite_layers_through(self, max_layer_index: int) -> np.ndarray:
    """
    Composite layers 0 through max_layer_index with their blend modes.
    
    Args:
        max_layer_index: Maximum layer index to include (inclusive)
        
    RHierarchical Layer Output** (NEW):
   - Main screen: Full canvas (all layers)
   - LED wall: Layers 0-3 composited (background + 3 effects)
   - Side projector: Layer 4 only (single effect layer)
   - **Benefit**: Output different layer combinations without duplicating content

2. **Complex VJ Performance** (NEW):
   - Screen 1: Layers 0-2 (background + two effects) → `layer:2:inclusive`
   - Screen 2: Layers 0-4 (background + four effects) → `layer:4:inclusive`
   - Screen 3: Layer 5 only (isolated effect) → `layer:5`
   - **Benefit**: Progressive layer buildup across multiple screens

3. **VJ Performance**: 
   - Background video on LED wall (layer:0 → monitor 1)
   - Live camera feed on projector (layer:1 → monitor 2)
   - Composited mix on main screen (canvas → monitor 0)

4. **Theater Setup**:
   - Actor background on rear projection (layer:0, sliced)
   - Foreground effects on LED strips (layer:1, multiple slices)
   - Full stage output on control monitor (canvas)

5. **Club Installation**:
   - Ceiling LEDs (layer:0, circular slice)
   - Wall panels (layer:1, multiple rectangular slices)
   - DJ monitor (clip:current preview)

6. **Corporate Events**:
   - Main presentation screen (canvas, centered slice)
   - Side screens with logo overlays (layer:2)
   - Confidence monitor with notes (clip:current)

7. **Multi-Output Layer Stack** (NEW):
   - Output A: Layers 0-1 (base + overlay 1) → `layer:1:inclusive`
   - Output B: Layers 0-2 (base + overlays 1-2) → `layer:2:inclusive`
   - Output C: Layers 0-3 (base + overlays 1-3) → `layer:3:inclusive`
   - Output D: Layer 4 only (special effect) → `layer:4`
   - **Benefit**: Create progressive reveals or different complexity levels per screen

8. **NDI Network Streaming** (NEW):
   - Main output to projector (display → monitor 0)
   - Live stream to broadcast (NDI → "Flux Broadcast")
   - Monitoring feed to control room (NDI → "Flux Monitor")
   - **Benefit**: Send video over network to remote locations, OBS, vMix, etc.

9. **Spout GPU Sharing** (NEW):
   - Background layer to Resolume (Spout → "Flux BG")
   - Overlay effects to TouchDesigner (Spout → "Flux FX")
   - Full canvas to recording software (Spout → "Flux Record")
   - **Benefit**: Zero-copy GPU sharing with other creative applications

10. **Hybrid Output Setup** (NEW):
   - Physical projector (display → monitor 0, full canvas)
   - Network stream (NDI → "Flux Stream", canvas)
   - GPU share to VJ software (Spout → "Flux Mix", layer:0)
   - Preview monitor (display → monitor 1, clip:current)
   - **Benefit**: Mix all output types for complex production workflows

11. **Explicit Layer Isolation** (NEW):
   - LED Wall: Layer 0 ONLY (background video) → `layer:0`
   - Front Projector: Layer 1 ONLY (foreground effects) → `layer:1`
   - Side Screens: Layer 2 ONLY (text overlays) → `layer:2`
   - Ceiling LEDs: Layer 3 ONLY (ambient effects) → `layer:3`
   - Main Screen: All layers composited → `canvas`
   - **Benefit**: Independent control over each visual element, no interference between layers
        layer_frame = layer.get_frame()
        blend_mode = layer.blend_mode
        opacity = layer.opacity / 100.0
        
        # Apply blend mode
        result = self._apply_blend_mode(result, layer_frame, blend_mode, opacity)
    
    return result
```

### API Endpoints

**Set output source (single layer):**
```bash
curl -X PUT http://localhost:5000/api/outputs/video/display_main/source \
  -H "Content-Type: application/json" \
  -d '{"source": "layer:4"}'
```

**Set output source (hierarchical - include sub-layers):**
```bash
curl -X PUT http://localhost:5000/api/outputs/video/led_wall/source \
  -H "Content-Type: application/json" \
  -d '{"source": "layer:3:inclusive"}'
```

**Set output slice:**
```bash
curl -X PUT http://localhost:5000/api/outputs/video/display_main/slice \
  -H "Content-Type: application/json" \
  -d '{"slice_id": "left_half"}'
```

**Get output configuration:**
```bash
curl http://localhost:5000/api/outputs/video
```

### Use Cases

1. **VJ Performance**: 
   - Background video on LED wall (layer:0 → monitor 1)
   - Live camera feed on projector (layer:1 → monitor 2)
   - Composited mix on main screen (canvas → monitor 0)

2. **Theater Setup**:
   - Actor background on rear projection (layer:0, sliced)
   - Foreground effects on LED strips (layer:1, multiple slices)
   - Full stage output on control monitor (canvas)

3. **Club Installation**:
   - Ceiling LEDs (layer:0, circular slice)
   - Wall panels (layer:1, multiple rectangular slices)
   - DJ monitor (clip:current preview)

4. **Corporate Events**:
   - Main presentation screen (canvas, centered slice)
   - Side screens with logo overlays (layer:2)
   - Confidence monitor with notes (clip:current)

---

## �🏗️ Implementation Plan

### Phase 1: Core Backend Infrastructure (4-6 hours)

**Goal**: Create the foundational output routing system without touching player_core.py

#### Step 1.1: Create Module Structure (15 min)
```bash
mkdir src/modules/outputs
mkdir src/modules/outputs/plugins
```

**Files to create:**
- `src/modules/outputs/__init__.py`
- `src/modules/outputs/output_base.py`
- `src/modules/outputs/output_manager.py`
- `src/modules/outputs/slice_manager.py`
- `src/modules/outputs/plugins/__init__.py`

#### Step 1.2: Implement Output Base Classes (1-2 hours)

**`output_base.py`**: Abstract base class for all output plugins
- Features:
  - Thread-safe frame queue
  - FPS throttling
  - Enable/disable state
  - Statistics tracking (frames sent/dropped)
  - Abstract methods: `initialize()`, `send_frame()`, `cleanup()`

**`slice_manager.py`**: Slice definition and extraction
- Features:
  - `SliceDefinition` class (x, y, width, height, rotation, soft_edge)
  - `extract_slice()` - Extract rectangular region from frame
  - `apply_mask()` - Apply mask to slice
  - `apply_soft_edge()` - Blur edges of slice
  - `apply_rotation()` - Rotate slice
  - Shape support: Rectangle, Polygon, Circle
  - Coordinate transformations
  - **get_state()** / **set_state()** methods for persistence (NEW)

**`output_manager.py`**: Coordinates all outputs
- Features:
  - Register/unregister output plugins
  - `update_frame()` - Distribute frame to all outputs
  - Slice assignment per output
  - **Clip/Layer routing per output** (NEW)
  - Thread-safe frame distribution
  - Output statistics aggregation
  - Source selection: 'canvas' (full composite), 'clip:<clip_id>', 'layer:<layer_id>'
  - **Session state integration** - Save/load output configuration (NEW)
  - **get_state()** / **set_state()** methods for persistence

#### Step 1.3: Implement Display Output Plugin (2-3 hours)

**`plugins/display_output.py`**: OpenCV window output
- Features:
  - Create fullscreen/windowed displays
  - Multi-monitor support
  - Window positioning (X, Y, monitor index)
  - Resolution scaling
  - Keyboard shortcuts (ESC to close, F to toggle fullscreen)

**Dependencies needed:**
```bash
# Add to requirements.txt:
screeninfo>=0.8.0  # Monitor detection
NDIlib-python>=1.0.0  # NDI output (optional)
SpoutGL>=0.2.0  # Spout output (optional, Windows only)
```

**Monitor Detection Utility:**
```python
# src/modules/outputs/monitor_utils.py
from screeninfo import get_monitors

def get_available_monitors():
    """Returns list of available monitors with positions and resolutions"""
    return [
        {
            'index': i,
            'name': f'Monitor {i+1}',
            'x': m.x,
            'y': m.y,
            'width': m.width,
            'height': m.height,
            'is_primary': m.is_primary if hasattr(m, 'is_primary') else (i == 0)
        }
        for i, m in enumerate(get_monitors())
    ]
```

#### Step 1.4: Implement NDI Output Plugin (2-3 hours)

**`plugins/ndi_output.py`**: NDI network video output
- Features:
  - Send video over IP network
  - NDI source naming
  - Automatic discovery by NDI receivers
  - Low-latency streaming
  - Multiple simultaneous NDI sources
  - Resolution and framerate configuration
  - NDI groups support

**Implementation:**
```python
import NDIlib as ndi
import numpy as np
from ..output_base import OutputBase
import logging

logger = logging.getLogger(__name__)

class NDIOutput(OutputBase):
    """
    NDI network video output
    Sends video over IP to NDI receivers
    """
    
    def __init__(self, output_id: str, config: dict):
        super().__init__(output_id, config)
        self.ndi_sender = None
        self.ndi_name = config.get('ndi_name', f'Flux_{output_id}')
        self.ndi_groups = config.get('ndi_groups', '')
        
    def initialize(self) -> bool:
        """Initialize NDI sender"""
        try:
            if not ndi.initialize():
                logger.error("NDI initialization failed")
                return False
            
            # Create NDI sender
            send_settings = ndi.SendCreate()
            send_settings.ndi_name = self.ndi_name
            send_settings.groups = self.ndi_groups
            
            self.ndi_sender = ndi.send_create(send_settings)
            
            if self.ndi_sender is None:
                logger.error(f"Failed to create NDI sender: {self.ndi_name}")
                return False
            
            logger.info(f"✅ NDI output '{self.ndi_name}' initialized")
            return True
            
        except Exception as e:
            logger.error(f"NDI initialization error: {e}")
            return False
    
    def send_frame(self, frame: np.ndarray) -> bool:
        """Send frame via NDI"""
        if self.ndi_sender is None:
            return False
        
        try:
            # Convert BGR to RGBA (NDI uses RGBA)
            frame_rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
            
            # Create NDI video frame
            video_frame = ndi.VideoFrameV2()
            video_frame.data = frame_rgba
            video_frame.FourCC = ndi.FOURCC_VIDEO_TYPE_RGBA
            
            # Send frame
            ndi.send_send_video_v2(self.ndi_sender, video_frame)
            
            self.frames_sent += 1
            return True
            
        except Exception as e:
            logger.error(f"NDI send error: {e}")
            self.frames_dropped += 1
            return False
    
    def cleanup(self):
        """Cleanup NDI resources"""
        if self.ndi_sender:
            ndi.send_destroy(self.ndi_sender)
            self.ndi_sender = None
        ndi.destroy()
        logger.info(f"NDI output '{self.ndi_name}' cleaned up")
```

#### Step 1.5: Implement Spout Output Plugin (2-3 hours)

**`plugins/spout_output.py`**: Spout GPU texture sharing (Windows)
- Features:
  - GPU-based texture sharing (zero-copy)
  - Share with other applications (Resolume, TouchDesigner, etc.)
  - Low CPU overhead
  - Multiple Spout senders
  - Automatic sender naming
  - Windows only

**Implementation:**
```python
import SpoutGL
import numpy as np
from ..output_base import OutputBase
import logging
import platform

logger = logging.getLogger(__name__)

class SpoutOutput(OutputBase):
    """
    Spout GPU texture sharing output (Windows only)
    Shares frames with other applications via GPU
    """
    
    def __init__(self, output_id: str, config: dict):
        super().__init__(output_id, config)
        self.spout_sender = None
        self.spout_name = config.get('spout_name', f'Flux_{output_id}')
        self.width = config.get('resolution', [1920, 1080])[0]
        self.height = config.get('resolution', [1920, 1080])[1]
        
    def initialize(self) -> bool:
        """Initialize Spout sender"""
        # Check if Windows
        if platform.system() != 'Windows':
            logger.error("Spout is only available on Windows")
            return False
        
        try:
            # Create Spout sender
            self.spout_sender = SpoutGL.SpoutSender()
            self.spout_sender.setSenderName(self.spout_name)
            
            # Initialize with resolution
            success = self.spout_sender.createSender(
                self.spout_name,
                self.width,
                self.height
            )
            
            if not success:
                logger.error(f"Failed to create Spout sender: {self.spout_name}")
                return False
            
            logger.info(f"✅ Spout output '{self.spout_name}' initialized ({self.width}x{self.height})")
            return True
            
        except Exception as e:
            logger.error(f"Spout initialization error: {e}")
            return False
    
    def send_frame(self, frame: np.ndarray) -> bool:
        """Send frame via Spout"""
        if self.spout_sender is None:
            return False
        
        try:
            # Resize if needed
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))
            
            # Convert BGR to RGB (Spout uses RGB)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Send frame (GPU texture sharing)
            self.spout_sender.sendImage(frame_rgb)
            
            self.frames_sent += 1
            return True
            
        except Exception as e:
            logger.error(f"Spout send error: {e}")
            self.frames_dropped += 1
            return False
    
    def cleanup(self):
        """Cleanup Spout resources"""
        if self.spout_sender:
            self.spout_sender.releaseSender()
            self.spout_sender = None
        logger.info(f"Spout output '{self.spout_name}' cleaned up")
```

---

### Phase 2: API Endpoints (2-3 hours)

**Goal**: Create REST API for frontend communication

#### Step 2.1: Create Output API Module (1-2 hours)

**`src/modules/api_outputs.py`**: Output and slice management API

**Endpoints to implement:**

```python
# Monitor Detection
@app.route('/api/monitors', methods=['GET'])
def get_monitors():
    """Get available display monitors"""
    # Returns: [{'index': 0, 'name': 'Monitor 1', 'width': 1920, 'height': 1080, ...}]

# Output Management
@app.route('/api/outputs/<player>', methods=['GET'])
def get_outputs(player):
    """Get all outputs for player (video/artnet)"""
    # Returns: {'outputs': {...}, 'enabled_outputs': [...]}

@app.route('/api/outputs/<player>/<output_id>/enable', methods=['POST'])
def enable_output(player, output_id):
    """Enable specific output"""

@app.route('/api/outputs/<player>/<output_id>/disable', methods=['POST'])
def disable_output(player, output_id):
    """Disable specific output"""

@app.route('/api/outputs/<player>/<output_id>/source', methods=['PUT'])
def set_output_source(player, output_id):
    """Set output source (canvas/clip/layer)"""
    # Body: {'source': 'canvas'} or {'source': 'clip', 'clip_id': 'uuid'} or {'source': 'layer', 'layer_index': 0}

@app.route('/api/outputs/<player>/<output_id>/slice', methods=['PUT'])
def set_output_slice(player, output_id):
    """Set slice for output"""
    # Body: {'slice_id': 'custom_slice_1'}

# Slice Management
@app.route('/api/slices', methods=['GET'])
def get_slices():
    """Get all slice definitions"""
    # Returns: {'slices': {...}, 'canvas': {'width': 1920, 'height': 1080}}

@app.route('/api/slices', methods=['POST'])
def create_slice():
    """Create new slice definition"""
    # Body: {slice_id, x, y, width, height, rotation, shape, ...}

@app.route('/api/slices/<slice_id>', methods=['PUT'])
def update_slice(slice_id):
    """Update slice definition"""

@app.route('/api/slices/<slice_id>', methods=['DELETE'])
def delete_slice(slice_id):
    """Delete slice definition"""

@app.route('/api/slices/import', methods=['POST'])
def import_slices():
    """Import slices from JSON (from frontend export)"""
    # Body: JSON from output-settings.js export

@app.route('/api/slices/export', methods=['GET'])
def export_slices():
    """Export slices to JSON"""
Session State Integration (NEW)
@app.route('/api/outputs/state', methods=['GET'])
def get_output_state():
    """Get complete output state (for session save)"""
    # Returns: {'outputs': {...}, 'slices': {...}, 'enabled_outputs': [...]}

@app.route('/api/outputs/state', methods=['POST'])
def set_output_state():
    """Restore complete output state (for session load)"""
    # Body: {'outputs': {...}, 'slices': {...}, 'enabled_outputs': [...]}

# 
# Preview/Debug
@app.route('/api/outputs/<player>/preview/<output_id>', methods=['GET'])
def get_output_preview(player, output_id):
    """Get preview image of specific output (base64 JPEG)"""
```

#### Step 2.2: Register API Routes (30 min)

**Modify `src/modules/rest_api.py`**:
```python
# Add import
from .api_outputs import register_output_routes

# In create_app() or setup_routes():
register_output_routes(app, player_manager)
```

---

### Phase 3: Player Integration (2-3 hours)

**Goal**: Integrate output manager into video player without breaking Art-Net player

#### Step 3.1: Modify Player Core (1-2 hours)

**`src/modules/player_core.py`** - Changes:

1. **Import output manager** (top of file):
```python
# ADD after existing imports
try:
    from .outputs import OutputManager
    OUTPUTS_AVAILABLE = True
except ImportError:
    OUTPUTS_AVAILABLE = False
    OutputManager = None
```

2. **Initialize output manager** (in `__init__` method, around line 100-150):
```python
# FIND this section (around line 147):
# Art-Net Manager wird extern gesetzt
self.artnet_manager = None

# ADD AFTER:
# Output Manager (NEW - video player only, optional feature)
self.output_manager = None
if OUTPUTS_AVAILABLE and not enable_artnet:
    # Only initialize for video player if configured
    output_config = self.config.get('output_routing', {}).get('video_player', {})
    if output_config.get('enabled', False):
        try:
            self.output_manager = OutputManager(
                player_name=self.player_name,
                canvas_width=self.canvas_width,
                canvas_height=self.canvas_height,
                config=output_config
            )
            logger.info(f"✅ Output Manager initialized for {self.player_name}")
        except Exception as e:
            logger.warning(f"Output Manager initialization failed: {e}")
```

3. **Distribute frames to outputs** (in frame processing, around line 900-1000):
```python
# FIND where processed frame is ready (after effect processing)
# Usually around where artnet_manager.send_frame() is called

# ADD AFTER effect processing:
# Distribute frame to output routing system (if enabled)
if self.output_manager:
    try:
        # Pass both composite frame and layer manager for individual layer access
        self.output_manager.update_frame(
            composite_frame=processed_frame,
            layer_manager=self.layer_manager if hasattr(self, 'layer_manager') else None,
            current_clip_id=self.current_clip_id if hasattr(self, 'current_clip_id') else None
        )
    except Exception as e:
        logger.error(f"Output manager frame update failed: {e}")
```
# FIND where processed frame is ready (after effect processing)
# Usually arounIntegrate with Session State (1 hour)

**`src/modules/session_state.py`** - Add output settings to session schema:

```python
# ADD to SessionState class:

def save_output_state(self, player_name: str, output_state: dict):
    """Save output routing state to session"""
    if 'outputs' not in self.state:
        self.state['outputs'] = {}
    
    self.state['outputs'][player_name] = {
        'outputs': output_state.get('outputs', {}),
        'slices': output_state.get('slices', {}),
        'enabled_outputs': output_state.get('enabled_outputs', []),
        'timestamp': time.time()
    }
    self.save()

def get_output_state(self, player_name: str) -> dict:
    """Load output routing state from session"""
    if 'outputs' not in self.state:
        return {}
    return self.state['outputs'].get(player_name, {})

def clear_output_state(self, player_name: str):
    """Clear output state for specific player"""
    if 'outputs' in self.state and player_name in self.state['outputs']:
        del self.state['outputs'][player_name]
        self.save()
```

**`src/modules/outputs/output_manager.py`** - Add state methods:

```python
# ADD to OutputManager class:

def get_state(self) -> dict:
    """
    Get complete output state for session persistence
    
    Returns:
        dict: {
            'outputs': {output_id: {config}},
            'slices': {slice_id: {definition}},
            'enabled_outputs': [output_id, ...]
        }
    """
    return {
        'outputs': {
            output_id: {
                'type': output.config.get('type'),
                'source': output.config.get('source', 'canvas'),
                'slice': output.config.get('slice', 'full'),
                'monitor_index': output.config.get('monitor_index', 0),
                'resolution': output.config.get('resolution', [1920, 1080]),
                'fps': output.config.get('fps', 30),
                'fullscreen': output.config.get('fullscreen', True),
                'window_title': output.config.get('window_title', ''),
                'enabled': output.enabled
            }
            for output_id, output in self.outputs.items()
        },
        'slices': self.slice_manager.get_state(),
        'enabled_outputs': [
            output_id for output_id, output in self.outputs.items() 
            if output.enabled
        ]
    }

def set_state(self, state: dict):
    """
    Restore output state from session
    
    Args:
        state: Dict from get_state()
    """
    # Restore slices
    if 'slices' in state:
        self.slice_manager.set_state(state['slices'])
    
    # Update output configurations
    if 'outputs' in state:
        for output_id, output_config in state['outputs'].items():
            if output_id in self.outputs:
                output = self.outputs[output_id]
                # Update configuration
                output.config.update(output_config)
                
                # Handle enable/disable
                if output_config.get('enabled', False) and not output.enabled:
                    self.enable_output(output_id)
                elif not output_config.get('enabled', False) and output.enabled:
                    self.disable_output(output_id)
    
    logger.info(f"[{self.player_name}] Output state restored from session")
```

**`src/modules/outputs/slice_manager.py`** - Add state methods:

```python
# ADD to SliceManager class:

def get_state(self) -> dict:
    """Get all slice definitions for session persistence"""
    return {
        slice_id: {
            'x': slice_def.x,
            'y': slice_def.y,
            'width': slice_def.width,
            'height': slice_def.height,
            'rotation': slice_def.rotation,
            'shape': slice_def.shape,
            'soft_edge': slice_def.soft_edge,
            'mask': slice_def.mask,
            'description': slice_def.description,
            'points': slice_def.points if hasattr(slice_def, 'points') else None
        }
        for slice_id, slice_def in self.slices.items()
    }

def set_state(self, slices_dict: dict):
    """Restore slice definitions from session"""
    self.slices.clear()
    for slice_id, slice_data in slices_dict.items():
        self.add_slice(
            slice_id=slice_id,
            x=slice_data.get('x', 0),
            y=slice_data.get('y', 0),
            width=slice_data.get('width', self.canvas_width),
            height=slice_data.get('height', self.canvas_height),
            rotation=slice_data.get('rotation', 0),
            shape=slice_data.get('shape', 'rectangle'),
            soft_edge=slice_data.get('soft_edge'),
            mask=slice_data.get('mask'),
            description=slice_data.get('description', ''),
            points=slice_data.get('points')
        )
    logger.info(f"Restored {len(self.slices)} slices from session")
```

**`src/modules/player_core.py`** - Auto-save/restore on session operations:

```python
# MODIFY Player class to save/restore output state

# In Player.__init__() after output manager initialization:
if self.output_manager:
    # Restore output state from session
    from .session_state import session_state
    saved_state = session_state.get_output_state(self.player_name)
    if saved_state:
        try:
            self.output_manager.set_state(saved_state)
            logger.info(f"Output state restored for {self.player_name}")
        except Exception as e:
            logger.warning(f"Failed to restore output state: {e}")

# ADD method to save output state:
def save_output_state(self):
    """Save current output state to session"""
    if self.output_manager:
        from .session_state import session_state
        state = self.output_manager.get_state()
        session_state.save_output_state(self.player_name, state)
        logger.debug(f"Output state saved for {self.player_name}")

# CALL save_output_state() at key points:
# - When output configuration changes
# - On graceful shutdown
# - Before snapshots
```

**`src/modules/api_outputs.py`** - Add session state endpoints:

```python
@app.route('/api/outputs/state', methods=['GET'])
def get_output_state():
    """Get complete output state for session save"""
    try:
        player = player_manager.get_player('video')
        if not player or not player.output_manager:
            return jsonify({'success': False, 'error': 'Output manager not available'}), 404
        
        state = player.output_manager.get_state()
        
        return jsonify({
            'success': True,
            'state': state
        })
    except Exception as e:
        logger.error(f"Get output state error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/outputs/state', methods=['POST'])
def set_output_state():
    """Restore complete output state from session"""
    try:
        data = request.get_json()
        player = player_manager.get_player('video')
        if not player or not player.output_manager:
            return jsonify({'success': False, 'error': 'Output manager not available'}), 404
        
        state = data.get('state', {})
        player.output_manager.set_state(state)
        
        # Also save to session file
        from ..session_state import session_state
        session_state.save_output_state(player.player_name, state)
        
        return jsonify({
            'success': True,
            'message': 'Output state restored'
        })
    except Exception as e:
        logger.error(f"Set output state error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Step 3.3: d where artnet_manager.send_frame() is called

# ADD AFTER effect processing:
# Distribute frame to output routing system (if enabled)
if self.output_manager:
    try:
        self.output_manager.update_frame(processed_frame)
    except Exception as e:
        logger.error(f"Output manager frame update failed: {e}")
```

#### Step 3.2: Update Configuration Schema (30 min)

**`config.json`** - Add new section:
```json
{
  "output_roource": "canvas",
          "_source_options": "canvas | clip:<uuid> | layer:<index>",
          "slice": "full",
          "monitor_index": 0,
          "fullscreen": true,
          "resolution": [1920, 1080],
          "fps": 30,
          "window_title": "Flux Main Display"
        },
        "display_secondary": {
          "type": "display",
          "enabled": false,
          "source": "layer:0",
          "_source_comment": "Output only layer 0 (background layer)",
          "slice": "custom_slice_1",
          "monitor_index": 1,
          "fullscreen": true,
          "resolution": [1920, 1080],
          "fps": 30,
          "window_title": "Flux Secondary Display"
        },
        "display_clip_preview": {
          "type": "display",
          "enabled": false,
          "source": "clip:current",
          "_source_comment": "Output current active clip (before layer compositing)",
          "slice": "full",
          "monitor_index": 2,
          "fullscreen": false,
          "resolution": [640, 360],
          "fps": 30,
          "window_title": "Clip Preview"
        },
        "ndi_main": {
          "type": "ndi",
          "enabled": false,
          "source": "canvas",
          "_source_comment": "Send full canvas via NDI",
          "slice": "full",
          "ndi_name": "Flux Main Output",
          "ndi_groups": "VJ",
          "resolution": [1920, 1080],
          "fps": 30,
          "_description": "NDI network output - discoverable by other NDI applications"
        },
        "ndi_layer_preview": {
          "type": "ndi",
          "enabled": false,
          "source": "layer:1",
          "_source_comment": "Send layer 1 via NDI for monitoring",
          "slice": "full",
          "ndi_name": "Flux Layer 1",
          "ndi_groups": "VJ",
          "resolution": [1920, 1080],
          "fps": 30
        },
        "spout_main": {
          "type": "spout",
          "enabled": false,
          "source": "canvas",
          "_source_comment": "Share full canvas via Spout (Windows only)",
          "slice": "full",
          "spout_name": "Flux Main",
          "resolution": [1920, 1080],
          "fps": 60,
          "_description": "Spout GPU sharing - zero-copy to Resolume/TouchDesigner"
        },
        "spout_background": {
          "type": "spout",
          "enabled": false,
          "source": "layer:0",
          "_source_comment": "Share background layer via Spout",
          "slice": "full",
          "spout_name": "Flux Background",
          "resolution": [1920, 1080],
          "fps": 60
        },
        "display_secondary": {
          "type": "display",
          "enabled": false,
          "slice": "custom_slice_1",
          "monitor_index": 1,
          "fullscreen": true,
          "resolution": [1920, 1080],
          "fps": 30,
          "window_title": "Flux Secondary Display"
        }
      },
      "slices": {
        "_comment": "Slice definitions loaded from /api/slices/import",
        "full": {
          "id": "full",
          "x": 0,
          "y": 0,
          "width": 1920,
          "height": 1080,
          "rotation": 0,
          "shape": "rectangle",
          "description": "Full canvas"
        }
      }
    }
  }
}
```

**`src/modules/config_schema.py`** - Add validation schema:
```python
# Add to CONFIG_SCHEMA dict: + add clip/layer routing UI
"output_routing": {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "video_player": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "outputs": {"type": "object"},
                "slices": {"type": "object"}
            }
        }
    }
}
```

---

### Phase 4: Frontend Integration (2-3 hours)

**Goal**: Connect existing output-settings.html to backend API

#### Step 4.1: Update Output Settings JS (1-2 hours)

**`frontend/js/output-settings.js`** - Add API integration:

```javascript
// Add at top of file:
const API_BASE = 'http://localhost:5000';

// ========================================
// API INTEGRATION (NEW)
// ========================================

/**
 * Load available monitors from backend
 */
async function loadMonitors() {
    try {
        const response = await fetch(`${API_BASE}/api/monitors`);
        const data = await response.json();
        
        if (data.success) {
            // Update screens list with real monitors
            const monitorNames = data.monitors.map(m => m.name);
            app.screens = monitorNames;
            app.updateScreenButtons();
            showToast(`Loaded ${data.monitors.length} monitors`);
        }
    } catch (e) {
        console.error('Failed to load monitors:', e);
        showToast('Failed to load monitors', 'error');
    }
}

/**
 * Save slices to backend
 */
async function saveSlicesToBackend() {
    try {
        const exportData = app.exportToJSON();
        const response = await fetch(`${API_BASE}/api/slices/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                slices: exportData.slices,
                canvas: exportData.canvas
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showToast('✅ Slices saved to backend');
        } else {
            showToast(`❌ Save failed: ${data.error}`, 'error');
        }
    } catch (e) {
        console.error('Failed to save slices:', e);
        showToast('Failed to save slices', 'error');
    }
}

/**
 * Load slices from backend
 */
async function loadSlicesFromBackend() {
    try {
        const response = await fetch(`${API_BASE}/api/slices`);
        const data = await response.json();
        
        if (data.success) {
            app.importFromJSON({
                slices: data.slices,
                canvas: data.canvas
            });
            showToast(`✅ Loaded ${Object.keys(data.slices).length} slices`);
        }
    } catch (e) {
        console.error('Failed to load slices:', e);
        showToast('Failed to load slices', 'error');
    }
}

/**
 * Enable/disable output
 */
async function toggleOutput(outputId, enabled) {
    try {
        const endpoint = enabled ? 'enable' : 'disable';
        const response = await fetch(
            `${API_BASE}/api/outputs/video/${outputId}/${endpoint}`,
            { method: 'POST' }
        );
        
        const data = await response.json();
        if (data.success) {
            showToast(`Output ${outputId} ${enabled ? 'enabled' : 'disabled'}`);
        }
    } catch (e) {
        console.error('Failed to toggle output:', e);
    }
}
Output Management UI (1 hour)

**New file: `frontend/output-manager.html`** - Output routing UI:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Output Manager - Flux</title>
    <link rel="stylesheet" href="libs/bootstrap/css/bootstrap.min.css">
    <link rel="stylesheet" href="css/styles.css">
</head>
<body>
    <div id="menuBarContainer"></div>
    
    <div class="container mt-4">
        <h1>🖥️ Output Manager</h1>
        <p class="text-muted">Route clips, layers, and slices to different screens</p>
        
        <!-- Available Monitors -->
        <div class="card mb-3">
            <div class="card-header">
                <h5>Available Monitors</h5>
            </div>
            <div class="card-body" id="monitorsContainer">
                Loading monitors...
            </div>
        </div>
        
        <!-- Output Routing -->
        <div class="card">
            <div class="card-header">
                <h5>Output Configuration</h5>
                <button class="btn btn-sm btn-success" onclick="addOutput()">+ Add Output</button>
            </div>
            <div class="card-body">
                <table class="table table-dark table-striped">
                    <thead>
                        <tr>
                            <th>Output ID</th>
                            <th>Monitor</th>
                            <th>Source</th>
                            <th>Slice</th>
                            <th>Resolution</th>
                            <th>FPS</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="outputsTableBody">
                        <!-- Populated by JS -->
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Layer Assignment -->
        <div class="card mt-3">
            <div class="card-header">
                <h5>Layer → Output Assignment</h5>
            </div>
            <div class="card-body">
                <p class="text-muted">Assign individual layers to specific outputs</p>
                <div id="layerAssignmentContainer">
                    <!-- Populated by JS -->
                </div>
            </div>
        </div>
    </div>
    
    <script src="js/menu-loader.js"></script>
    <script src="js/output-manager.js"></script>
</body>
</html>
```

**New file: `frontend/js/output-manager.js`** - Output management logic:
```javascript
const API_BASE = 'http://localhost:5000';
let monitors = [];
let outputs = {};

async function loadMonitors() {
    try {
        const response = await fetch(`${API_BASE}/api/monitors`);
        const data = await response.json();
        
        if (data.success) {
            monitors = data.monitors;
            displayMonitors();
        }
    } catch (e) {
        console.error('Failed to load monitors:', e);
    }
}

function displayMonitors() {
    const container = document.getElementById('monitorsContainer');
    container.innerHTML = monitors.map(m => `
        <div class="d-inline-block m-2 p-3 border rounded">
            <strong>${m.name}</strong><br>
            ${m.width}x${m.height}<br>
            Position: ${m.x}, ${m.y}<br>
            ${m.is_primary ? '<span class="badge bg-primary">Primary</span>' : ''}
        </div>
    `).join('');
}

async function loadOutputs() {
    try {
        const response = await fetch(`${API_BASE}/api/outputs/video`);
        const data = await response.json();
        
        if (data.success) {
            outputs = data.outputs;
            displayOutputs();
        }
    } catch (e) {
        console.error('Failed to load outputs:', e);
    } (All Layers)</option>
                    <option value="clip:current" ${cfg.source === 'clip:current' ? 'selected' : ''}>Current Clip</option>
                    <optgroup label="Single Layer">
                        ${Array.from({length: 10}, (_, i) => `
                            <option value="layer:${i}" ${cfg.source === `layer:${i}` ? 'selected' : ''}>Layer ${i} only</option>
                        `).join('')}
                    </optgroup>
                    <optgroup label="Hierarchical (Include Sub-Layers)">
                        ${Array.from({length: 10}, (_, i) => `
                            <option value="layer:${i}:inclusive" ${cfg.source === `layer:${i}:inclusive` ? 'selected' : ''}>Layers 0-${i} composite</option>
                        `).join('')}
                    </optgroup>ementById('outputsTableBody');
    tbody.innerHTML = Object.entries(outputs).map(([id, cfg]) => `
        <tr>
            <td><code>${id}</code></td>
            <td>
                <select class="form-select form-select-sm" onchange="updateOutput('${id}', 'monitor_index', this.value)">
                    ${monitors.map((m, i) => `
                        <option value="${i}" ${cfg.monitor_index === i ? 'selected' : ''}>
                            ${m.name}
                        </option>
                    `).join('')}
                </select>
            </td>
            <td>
                <select class="form-select form-select-sm" onchange="updateOutputSource('${id}', this.value)">
                    <option value="canvas" ${cfg.source === 'canvas' ? 'selected' : ''}>Full Canvas</option>
                    <option value="clip:current" ${cfg.source === 'clip:current' ? 'selected' : ''}>Current Clip</option>
                    ${Array.from({length: 10}, (_, i) => `
                        <option value="layer:${i}" ${cfg.source === `layer:${i}` ? 'selected' : ''}>Layer ${i}</option>
                    `).join('')}
                </select>
            </td>
            <td>
                <select class="form-select form-select-sm" onchange="updateOutput('${id}', 'slice', this.value)">
                    <option value="full">Full</option>
                    <!-- Load from slices API -->
                </select>
            </td>
            <td>${cfg.resolution.join('x')}</td>
            <td>${cfg.fps}</td>
            <td>
                ${cfg.enabled ? '<span class="badge bg-success">Enabled</span>' : '<span class="badge bg-secondary">Disabled</span>'}
            </td>
            <td>
                <button class="btn btn-sm btn-${cfg.enabled ? 'warning' : 'success'}" 
                        onclick="toggleOutput('${id}', ${!cfg.enabled})">
                    ${cfg.enabled ? 'Disable' : 'Enable'}
                </button>
            </td>
        </tr>
    `).join('');
}

async function updateOutputSource(outputId, source) {
    try {
        const response = await fetch(`${API_BASE}/api/outputs/video/${outputId}/source`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source })
        });
        
        const data = await response.json();
        if (data.success) {
            console.log(`Output ${outputId} source updated to ${source}`);
        }
    } catch (e) {
        console.error('Failed to update output source:', e);
    }
}

async function toggleOutput(outputId, enabled) {
    try {
        const endpoint = enabled ? 'enable' : 'disable';
        const response = await fetch(`${API_BASE}/api/outputs/video/${outputId}/${endpoint}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        if (data.success) {
            await loadOutputs(); // Refresh
        }
    } catch (e) {
        console.error('Failed to toggle output:', e);
    }
}

// Session state auto-save (debounced)
let saveStateTimeout = null;
function scheduleStateSave() {
    if (saveStateTimeout) clearTimeout(saveStateTimeout);
    saveStateTimeout = setTimeout(saveOutputState, 1000); // Save 1s after last change
}

async function saveOutputState() {
    try {
        const response = await fetch(`${API_BASE}/api/outputs/state`);
        const data = await response.json();
        
        if (data.success) {
            // State is already saved on backend
            console.log('Output state saved to session');
        }
    } catch (e) {
        console.error('Failed to save output state:', e);
    }
}

// Call scheduleStateSave() after any output change
// Example: after updateOutputSource(), toggleOutput(), etc.

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    await loadMonitors();
    await loadOutputs();
    
    // Auto-save state every 5 seconds
    setInterval(saveOutputState, 5000);
});
```

**Add route in `src/modules/routes.py`**:
```python
@app.route('/output-manager')
def output_manager_page():
    return send_from_directory(app.static_folder, 'output-manager.html')
```

**Add to menu-bar.html**:
```html
<a href="/output-manager" title="Output Manager">🖥️</a>
```

#### Step 4.3: Add Backend Sync UI to Slice Editor
// Add buttons to UI for API actions
// (Can be added in panel-section for "Backend Sync")
```

#### Step 4.2: Add Backend Sync UI (30 min)

**`frontend/output-settings.html`** - Add sync section:
```html
<!-- Add in right panel, after export section -->
<div class="panel-section">
    <h2>🔄 Backend Sync</h2>
    <div class="panel-section-content">
        <button onclick="loadMonitors()" class="primary" style="width: 100%; margin-bottom: 8px;">
            🖥️ Load Monitors
        </button>
        <button onclick="saveSlicesToBackend()" class="primary" style="width: 100%; margin-bottom: 8px;">
            💾 Save to Backend
        </button>
        <button onclick="loadSlicesFromBackend()" style="width: 100%; margin-bottom: 8px;">
            📥 Load from Backend
        </button>
        <div id="backendStatus" style="font-size: 11px; color: #888; margin-top: 8px;">
            Backend: <span id="backendStatusText">Not connected</span>
        </div>
    </div>
</div>
```

---

### Phase 5: Real-time Preview System (3-4 hours)

**Goal**: Add live preview of slices and transformations

#### Step 5.1: Preview API Endpoint (1-2 hours)

**Add to `src/modules/api_outputs.py`**:

```pytImplement `/api/outputs/state` (GET/POST) for session persistence
- [ ] hon
@app.route('/api/outputs/preview/<player>/<output_id>', methods=['GET'])
def get_output_preview(player, output_id):
    """Get current frame for specific output as JPEG"""
    try:
        player_obj = player_manager.get_player(player)
        if not player_obj or not player_obj.output_manager:
            return jsonify({'success': False, 'error': 'Player not available'}), 404
      Create `output-manager.html` (new page for output routing)
- [ ] Create `output-manager.js` (clip/layer → screen routing)
- [ ] Add route `/output-manager` to routes.py
- [ ] Add API calls to `output-settings.js`
- [ ] Implement `loadMonitors()`
- [ ] Implement `saveSlicesToBackend()`
- [ ] Implement `loadSlicesFromBackend()`
- [ ] Add backend sync UI to `output-settings.html`
- [ ] **Add session state integration** (save/restore output state)
- [ ] Add `get_state()` / `set_state()` to OutputManager
- [ ] Add `get_state()` / `set_state()` to SliceManager
- [ ] Modify `session_state.py` to include output settings
- [ ] Auto-restore output state on player startup
- [ ] Add `output_routing` section to `config.json`
- [ ] Update `config_schema.py`
- [ ] Test with video player (output manager should initialize and restore stat
        if frame is None:
            return jsonify({'success': False, 'error': 'No frame available'}), 404
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': f'data:image/jpeg;base64,{image_base64}',
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Preview error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/outputs/preview/<player>/slice/<slice_id>', methods=['GET'])
def get_slice_preview(player, slice_id):
    """Get preview of specific slice from current frame"""
    try:
        player_obj = player_manager.get_player(player)
        if not player_obj:
            return jsonify({'success': False, 'error': 'Player not available'}), 404
        
        # Get current frame
        with player_obj.frame_lock if hasattr(player_obj, 'frame_lock') else nullcontext():
            frame = player_obj.latest_frame if hasattr(player_obj, 'latest_frame') else None
        
        if frame is None:
            return jsonify({'success': False, 'error': 'No frame available'}), 404
        
        # Extract slice
        if player_obj.output_manager:
            sliced_frame = player_obj.output_manager.slice_manager.get_slice(slice_id, frame)
        else:
            sliced_frame = frame
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', sliced_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        image_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': f'data:image/jpeg;base64,{image_base64}',
            'slice_id': slice_id,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.error(f"Slice preview error: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
```

#### Step 5.2: Frontend Live Preview (2 hours)

**Add to `frontend/js/output-settings.js`**:

- ✅ **Session state persistence** - Output settings saved/restored on reload/snapshot
- ✅ **Auto-save** - Changes automatically saved to session (2s debounce)
- ✅ **Snapshot support** - Output configuration included in project snapshots
```javascript
// Live preview system
let previewInterval = null;
let previewEnabled = false;

/**
 * Start live preview updates
 */
function startLivePreview() {
    if (previewInterval) return;
    
    previewEnabled = true;
    previewInterval = setInterval(updateLivePreviews, 100); // 10 FPS
    showToast('Live preview started');
}

/**
- ✅ **Hierarchical layer output** - Output layers 0-N composited with blend modes

### Full Feature Set:
- ✅ All slice shapes (rectangle, polygon, circle)
- ✅ Multi-monitor support with detection
- ✅ Soft edges and masks
- ✅ Live preview system
- ✅ Complete API coverage
- ✅ Frontend backend sync
- ✅ **Output Manager UI** - Visual routing of clips/layers/slices to screens
- ✅ **Explicit layer routing** - Output ANY layer (0-N) to ANY screen in isolation
- ✅ **Per-layer isolation** - Layer 0 → Screen A, Layer 1 → Screen B, no interference
- ✅ **Clip preview output** - Dedicated window showing current clip before compositing
- ✅ **Hierarchical compositing** - "Include sub-layers" mode for progressive layer builds
- ✅ **Blend mode support** - Hierarchical outputs respect layer blend modes (add, multiply, etc.)
- ✅ **Flexible routing** - Mix single layers, layer stacks, and canvas across outputs
- ✅ **NDI output** - Network video streaming to NDI receivers (OBS, vMix, etc.)
- ✅ **Spout output** - GPU texture sharing with Resolume, TouchDesigner, etc. (Windows)
- ✅ **Hybrid outputs** - Combine displays, NDI, and Spout in one setuppp.selectedSlice.id;
        const response = await fetch(
            `${API_BASE}/api/outputs/preview/video/slice/${sliceId}`
        );
        const data = await response.json();
        
        if (data.success) {
            // Update preview image in modal or canvas overlay
            updatePreviewImage(data.image);
        }
    } catch (e) {
        console.error('Preview update failed:', e);
    }
}

/**
 * Show slice preview in overlay
 */
function updatePreviewImage(imageData) {
    // Create or update preview overlay
    let overlay = document.getElementById('previewOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'previewOverlay';
        overlay.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            width: 320px;
            height: 180px;
            border: 2px solid #4CAF50;
            border-radius: 8px;
            overflow: hidden;
            background: #000;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.5);
        `;
        document.body.

4. **Session State Tests** (30 min)
   - Create slice configuration
   - Configure output routing
   - Save session (should auto-save)
   - Restart application
   - Verify slices restored
   - Verify output routing restored
   - Test snapshot creation
   - Test snapshot restoration
   - Verify outputs match snapshotappendChild(overlay);
    }
    
    overlay.innerHTML = `<img src="${imageData}" style="width: 100%; height: 100%; object-fit: contain;">`;
}
```

---

### Phase 6: Testing & Validation (2-3 hours)

#### Test Plan:

1. **Module Tests** (1 hour)
   - Test slice extraction (rectangle, polygon, circle)
   - Test rotation and soft edge
   - Test mask application
   - Test monitor detection

2. **API Tests** (1 hour)
   - Test all endpoints with curl/Postman
   - Test slice CRUD operations
   - Test output enable/disable
   - Test preview endpoints

# Test session state save
curl http://localhost:5000/api/outputs/state

# Test session state restore
curl -X POST http://localhost:5000/api/outputs/state \
  -H "Content-Type: application/json" \
  -d @saved_output_state.json

3. **Integration Tests** (1 hour)
   - Load video in video player
   - Create slices in frontend
   - Save to backend
   - Enable display output
   - Verify output windows appear
   - Test multi-monitor output
   - Test live preview

#### Test Script:
```bash
# Test monitor detection
curl http://localhost:5000/api/monitors

# Test slice creation
curl -X POST http://localhost:5000/api/slices \
  -H "Content-Type: application/json" \
  -d '{
    "slice_id": "test_slice",
    "x": 0,
    "y": 0,
    "width": 960,
    "height": 1080,
    "shape": "rectangle"
  }'

# Test output enable
curl -X POST http://localhost:5000/api/outputs/video/display_main/enable

# Test preview
curl http://localhost:5000/api/outputs/preview/video/slice/test_slice
```

---

## 📋 Implementation Checklist

### Phase 1: Core Backend (8-12 hours)
- [ ] Create `src/modules/outputs/` directory structure
- [ ] Implement `output_base.py` (base class)
- [ ] Implement `slice_manager.py` (slice extraction)
- [ ] Implement `output_manager.py` (frame distribution)
- [ ] Implement `plugins/display_output.py` (OpenCV windows)
- [ ] Implement `plugins/ndi_output.py` (NDI network streaming)
- [ ] Implement `plugins/spout_output.py` (Spout GPU sharing, Windows)
- [ ] Add `screeninfo`, `NDIlib-python`, `SpoutGL` to requirements.txt
- [ ] Test slice extraction manually
- [ ] Test NDI output with NDI receiver
- [ ] Test Spout output with Resolume/TouchDesigner

### Phase 2: API Endpoints (2-3 hours)
- [ ] Create `src/modules/api_outputs.py`
- [ ] Implement `/api/monitors` endpoi
- [ ] **Session state persistence tests** (save → reload → verify)
- [ ] **Snapshot tests** (create snapshot → restore → verify outputs)
- [ ] **Auto-save tests** (modify slice → wait 2s → verify saved)nt
- [ ] Implement `/api/outputs/*` endpoints
- [ ] Implement `/api/slices/*` endpoints
- [ ] Register routes in `rest_api.py`
- [ ] Test all endpoints with curl

### 5. **Session State Persistence**
- Auto-save after every change (debounced)
- Restore on application startup
- Include in snapshots
- Graceful degradation if session file missing

### Phase 3: Player Integration (2-3 hours)
- [ ] Add output manager initialization to `player_core.py`
- [ ] Add frame distribution call
- [ ] Add `output_routing` section to `config.json`
- [ ] Update `config_schema.py`
- [ ] Test with video player (output manager should initialize)

### Phase 4: Frontend Integration (2-3 hours)
- [ ] Add API calls to `output-settings.js`
- [ ] Implement `loadMonitors()`
- [ ] Implement `saveSlicesToBackend()`
- [ ] Implement `loadSlicesFromBackend()`
- [ ] Add backend sync UI to `output-settings.html`
- [ ] Test full workflow (create slice → save → enable output)

### Phase 5: Real-time Preview (3-4 hours)
- [ ] Implement preview API endpoints
- [ ] Add live preview system to frontend
- [ ] Add preview overlay UI
- [ ] Test live preview with video playback

### Phase 6: Testing (2-3 hours)
- [ ] Unit tests for slice extraction
- [ ] API endpoint tests
- [ ] Integration tests (full workflow)
- [ ] Multi-monitor testing
- [ ] Performance testing (FPS impact)

---

## ⚠️ Safety Measures

### 1. **No Breaking Changes**
- Art-Net player completely untouched
- Output manager only initialized for video player
- Optional feature (disabled by default in config)
- Graceful fallback if imports fail

### 2. **Error Handling**
- Try-except around all output operations
- Failed outputs don't crash player
- Comprehensive logging

### 3. **Performance**
- Separate threads per output (no player blocking)
- Frame queues with drop-oldest strategy
- FPS throttling per output
- Optional feature (can be disabled)

### 4. **Backward Compatibility**
- Works without configuration
- Existing projects unaffected
- Frontend works standalone (localStorage)

---

## 🎯 Next Steps (Immediate Actions)

### Start with Phase 1 (Today):
1. **Create directory structure** (5 min)
2. **Implement `output_base.py`** (30-45 min)
3. **Implement `slice_manager.py`** (1-2 hours)
4. **Test slice extraction manually** (30 min)

### Continue with Phase 2 (Next):
5. **Implement API endpoints** (2-3 hours)
6. **Test with curl** (30 min)

### Priority Order:
```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
└─Core─┘  └─API──┘  └Player┘  └──UI──┘  └Preview┘  └Tests┘
```

---

## 📊 Estimated Time Breakdown

| Phase | Description | Time | Priority |
|-------|-------------|------|----------|
| 1 | Core Backend (+ NDI/Spout) | 8-12h | 🔴 Critical |
| 2 | API Endpoints | 2-3h | 🔴 Critical |
| 3 | Player Integration | 2-3h | 🔴 Critical |
| 4 | Frontend Integration | 2-3h | 🟡 High |
| 5 | Real-time Preview | 3-4h | 🟢 Nice-to-have |
| 6 | Testing | 3-4h | 🟡 High |
| **Total** | | **20-29h** | |

---

## 🚀 Success Criteria

### Minimum Viable Product (MVP):
- ✅ Slice extraction working (rectangle only)
- ✅ Display output plugin (single monitor)
- ✅ API endpoints for slice CRUD
- ✅ Frontend can save/load slices
- ✅ Video player outputs to display window

### Full Feature Set:
- ✅ All slice shapes (rectangle, polygon, circle)
- ✅ Multi-monitor support with detection
- ✅ Soft edges and masks
- ✅ Live preview system
- ✅ Complete API coverage
- ✅ Frontend backend sync
- ✅ **Output Manager UI** - Visual routing of clips/layers/slices to screens
- ✅ **Explicit layer routing** - Output ANY layer (0-N) to ANY screen in isolation
- ✅ **Per-layer isolation** - Layer 0 → Screen A, Layer 1 → Screen B, no interference
- ✅ **Clip preview output** - Dedicated window showing current clip before compositing
- ✅ **Hierarchical compositing** - "Include sub-layers" mode for progressive layer builds
- ✅ **Blend mode support** - Hierarchical outputs respect layer blend modes (add, multiply, etc.)
- ✅ **Flexible routing** - Mix single layers, layer stacks, and canvas across outputs
- ✅ **NDI output** - Network video streaming to NDI receivers (OBS, vMix, etc.)
- ✅ **Spout output** - GPU texture sharing with Resolume, TouchDesigner, etc. (Windows)
- ✅ **Hybrid outputs** - Combine displays, NDI, and Spout in one setup

---

**Last Updated:** 2026-01-12  
**Status:** Ready to implement  
**Next Action:** Create Phase 1 directory structure and start with `output_base.py`
