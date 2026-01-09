# 🚀 Output Routing & Slicing System - Comprehensive Implementation Guide

## 📋 Overview

This guide implements the output routing system in **isolated modules** to ensure existing functionality (especially Art-Net player) remains untouched.

### **Architecture Summary:**
```
New Modules (won't affect existing code):
├── src/modules/outputs/          # New directory
│   ├── __init__.py
│   ├── output_base.py            # Base classes
│   ├── output_manager.py         # Output coordination
│   ├── slice_manager.py          # Slice definitions
│   ├── compositor.py             # Multi-layer compositing
│   └── plugins/                  # Output plugins
│       ├── __init__.py
│       ├── display_output.py     # Display windows
│       ├── recording_output.py   # Video recording
│       └── ndi_output.py         # NDI streaming (future)
├── src/modules/api_outputs.py    # New API routes
└── frontend/
    ├── slice-editor.html         # New page
    ├── js/slice-editor.js        # New JS module
    └── css/slice-editor.css      # New styles

Modified Files (minimal changes):
├── src/modules/player_core.py    # Add output_manager integration
├── src/modules/rest_api.py       # Register API routes
├── config.json                   # Add output_routing section
└── frontend/menu-bar.html        # Add slice editor link
```

### **Design Principles:**
- ✅ **Isolated modules** - No changes to existing Art-Net code
- ✅ **Video player only** - Art-Net player keeps current behavior
- ✅ **Backward compatible** - Works without configuration
- ✅ **Plugin architecture** - Easy to add new output types
- ✅ **Thread-safe** - Separate threads per output
- ✅ **FPS independent** - Each output polls at its own rate

---

## 📦 Phase 1: Core Infrastructure (3-4 hours)

### **Step 1.1: Create Directory Structure**

```bash
# Create new directories
mkdir src/modules/outputs
mkdir src/modules/outputs/plugins
```

### **Step 1.2: Create Base Classes**

**File: `src/modules/outputs/__init__.py`**
```python
"""
Output Routing System
Provides flexible output routing with slicing and compositing for video player
"""

from .output_base import OutputPluginBase
from .output_manager import OutputManager
from .slice_manager import SliceManager, SliceDefinition
from .compositor import OutputCompositor, CompositorLayer

__all__ = [
    'OutputPluginBase',
    'OutputManager',
    'SliceManager',
    'SliceDefinition',
    'OutputCompositor',
    'CompositorLayer'
]
```

**File: `src/modules/outputs/output_base.py`**
```python
"""
Base class for all output plugins
"""
import threading
import queue
import time
import numpy as np
from abc import ABC, abstractmethod
from ..logger import get_logger

logger = get_logger(__name__)


class OutputPluginBase(ABC):
    """Base class for all output plugins (Display, NDI, Recording, etc.)"""
    
    def __init__(self, output_id: str, config: dict):
        self.output_id = output_id
        self.config = config
        self.enabled = config.get('enabled', True)
        self.target_fps = config.get('fps', 30)
        self.thread = None
        self.running = False
        self.frame_queue = queue.Queue(maxsize=2)  # Small buffer to prevent lag
        self.stats = {
            'frames_sent': 0,
            'frames_dropped': 0,
            'last_frame_time': 0
        }
        
        logger.info(f"Output plugin '{output_id}' initialized (FPS: {self.target_fps}, enabled: {self.enabled})")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize output hardware/connection
        Returns True on success, False on failure
        """
        pass
    
    @abstractmethod
    def send_frame(self, frame: np.ndarray, timestamp: float):
        """
        Send frame to output (called in output thread)
        
        Args:
            frame: RGB numpy array (height, width, 3)
            timestamp: Frame timestamp
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup resources when output is stopped"""
        pass
    
    def start_thread(self):
        """Start output thread with FPS polling"""
        if self.thread and self.thread.is_alive():
            logger.warning(f"Output '{self.output_id}' thread already running")
            return
        
        self.running = True
        self.thread = threading.Thread(
            target=self._output_loop,
            name=f"Output-{self.output_id}",
            daemon=True
        )
        self.thread.start()
        logger.info(f"Output '{self.output_id}' thread started")
    
    def stop_thread(self):
        """Stop output thread"""
        if not self.running:
            return
        
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info(f"Output '{self.output_id}' thread stopped")
    
    def _output_loop(self):
        """Main output loop - polls at target FPS"""
        frame_delay = 1.0 / self.target_fps
        
        logger.debug(f"Output loop started for '{self.output_id}' (FPS: {self.target_fps})")
        
        while self.running:
            try:
                # Non-blocking get with timeout
                frame, timestamp = self.frame_queue.get(timeout=frame_delay)
                
                # Send frame to output
                self.send_frame(frame, timestamp)
                
                # Update stats
                self.stats['frames_sent'] += 1
                self.stats['last_frame_time'] = time.time()
                
            except queue.Empty:
                # No new frame available, continue polling
                continue
            except Exception as e:
                logger.error(f"Error in output loop for '{self.output_id}': {e}", exc_info=True)
                time.sleep(0.1)  # Prevent tight loop on error
        
        logger.debug(f"Output loop stopped for '{self.output_id}'")
    
    def push_frame(self, frame: np.ndarray, timestamp: float) -> bool:
        """
        Push frame to output queue (non-blocking)
        
        Returns:
            True if frame was queued, False if dropped
        """
        try:
            self.frame_queue.put_nowait((frame, timestamp))
            return True
        except queue.Full:
            self.stats['frames_dropped'] += 1
            logger.debug(f"Output '{self.output_id}' dropped frame (queue full)")
            return False
    
    def get_stats(self) -> dict:
        """Get output statistics"""
        return {
            'output_id': self.output_id,
            'enabled': self.enabled,
            'fps': self.target_fps,
            'frames_sent': self.stats['frames_sent'],
            'frames_dropped': self.stats['frames_dropped'],
            'last_frame_time': self.stats['last_frame_time']
        }
```

**File: `src/modules/outputs/slice_manager.py`**
```python
"""
Slice Manager - Handles frame slicing definitions and operations
"""
import numpy as np
import cv2
from ..logger import get_logger

logger = get_logger(__name__)


class SliceDefinition:
    """Defines a rectangular slice region"""
    
    def __init__(self, slice_id: str, x: int, y: int, width: int, height: int, description: str = ""):
        self.slice_id = slice_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.description = description
    
    def to_dict(self) -> dict:
        return {
            'slice_id': self.slice_id,
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            slice_id=data.get('slice_id', ''),
            x=data.get('x', 0),
            y=data.get('y', 0),
            width=data.get('width', 1920),
            height=data.get('height', 1080),
            description=data.get('description', '')
        )


class SliceManager:
    """Manages frame slicing definitions and operations"""
    
    def __init__(self, config: dict, canvas_width: int, canvas_height: int):
        self.config = config
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.slices = {}  # slice_id -> SliceDefinition
        
        self._load_slices()
        
        logger.info(f"SliceManager initialized: {len(self.slices)} slices, canvas {canvas_width}x{canvas_height}")
    
    def _load_slices(self):
        """Load slice definitions from config"""
        slice_defs = self.config.get('slices', {}).get('definitions', {})
        
        # Always have a 'full' slice
        if 'full' not in slice_defs:
            slice_defs['full'] = {
                'x': 0,
                'y': 0,
                'width': self.canvas_width,
                'height': self.canvas_height,
                'description': 'Full frame'
            }
        
        for slice_id, slice_config in slice_defs.items():
            self.slices[slice_id] = SliceDefinition(
                slice_id=slice_id,
                x=slice_config.get('x', 0),
                y=slice_config.get('y', 0),
                width=slice_config.get('width', self.canvas_width),
                height=slice_config.get('height', self.canvas_height),
                description=slice_config.get('description', '')
            )
        
        logger.debug(f"Loaded {len(self.slices)} slice definitions")
    
    def get_slice(self, slice_id: str, frame: np.ndarray) -> np.ndarray:
        """
        Extract slice region from frame
        
        Args:
            slice_id: ID of slice to extract
            frame: Source frame (RGB numpy array)
            
        Returns:
            Sliced frame (copy)
        """
        if slice_id not in self.slices:
            logger.warning(f"Slice '{slice_id}' not found, using full frame")
            return frame.copy()
        
        slice_def = self.slices[slice_id]
        
        # Validate bounds
        x = max(0, min(slice_def.x, frame.shape[1]))
        y = max(0, min(slice_def.y, frame.shape[0]))
        x2 = max(0, min(x + slice_def.width, frame.shape[1]))
        y2 = max(0, min(y + slice_def.height, frame.shape[0]))
        
        # Extract slice
        sliced_frame = frame[y:y2, x:x2].copy()
        
        return sliced_frame
    
    def add_slice(self, slice_id: str, x: int, y: int, width: int, height: int, description: str = ""):
        """Add slice definition dynamically"""
        self.slices[slice_id] = SliceDefinition(slice_id, x, y, width, height, description)
        logger.info(f"Added slice '{slice_id}': {x},{y} {width}x{height}")
    
    def remove_slice(self, slice_id: str):
        """Remove slice definition"""
        if slice_id in self.slices and slice_id != 'full':
            del self.slices[slice_id]
            logger.info(f"Removed slice '{slice_id}'")
    
    def get_all_slices(self) -> dict:
        """Get all slice definitions"""
        return {sid: s.to_dict() for sid, s in self.slices.items()}
    
    def get_slice_preview(self, frame: np.ndarray) -> np.ndarray:
        """
        Generate preview showing all slice boundaries
        
        Args:
            frame: Source frame
            
        Returns:
            Frame with slice boundaries drawn
        """
        preview = frame.copy()
        
        for slice_id, slice_def in self.slices.items():
            if slice_id == 'full':
                continue
            
            # Draw rectangle for each slice
            color = (0, 255, 0)  # Green
            cv2.rectangle(
                preview,
                (slice_def.x, slice_def.y),
                (slice_def.x + slice_def.width, slice_def.y + slice_def.height),
                color,
                2
            )
            
            # Draw label
            cv2.putText(
                preview,
                slice_id,
                (slice_def.x + 10, slice_def.y + 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2
            )
        
        return preview
```

### **Step 1.3: Create Output Manager**

**File: `src/modules/outputs/output_manager.py`**
```python
"""
Output Manager - Coordinates output routing and frame distribution
"""
import threading
import time
import numpy as np
from ..logger import get_logger

logger = get_logger(__name__)


class OutputManager:
    """Manages output routing for a player"""
    
    def __init__(self, player_name: str, canvas_width: int, canvas_height: int, config: dict = None):
        self.player_name = player_name
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.config = config or {}
        self.outputs = {}  # output_id -> OutputPluginBase
        self.latest_frame = None
        self.latest_timestamp = 0
        self.frame_lock = threading.Lock()
        
        # Slice Manager
        from .slice_manager import SliceManager
        self.slice_manager = SliceManager(self.config, canvas_width, canvas_height)
        
        logger.info(f"OutputManager initialized for '{player_name}' ({canvas_width}x{canvas_height})")
    
    def register_output(self, output_id: str, output_plugin):
        """
        Register an output plugin
        
        Args:
            output_id: Unique identifier for output
            output_plugin: OutputPluginBase instance
        """
        self.outputs[output_id] = output_plugin
        
        if output_plugin.enabled:
            if output_plugin.initialize():
                output_plugin.start_thread()
                logger.info(f"[{self.player_name}] Output '{output_id}' registered and started")
            else:
                logger.error(f"[{self.player_name}] Output '{output_id}' failed to initialize")
                output_plugin.enabled = False
        else:
            logger.info(f"[{self.player_name}] Output '{output_id}' registered (disabled)")
    
    def unregister_output(self, output_id: str):
        """Unregister and stop an output"""
        if output_id in self.outputs:
            output = self.outputs[output_id]
            output.stop_thread()
            output.cleanup()
            del self.outputs[output_id]
            logger.info(f"[{self.player_name}] Output '{output_id}' unregistered")
    
    def update_frame(self, frame: np.ndarray):
        """
        Called by player when new frame is available
        Distributes frame (or slices) to all outputs
        
        Args:
            frame: Source frame (RGB numpy array)
        """
        with self.frame_lock:
            self.latest_frame = frame.copy()
            self.latest_timestamp = time.time()
        
        # Push frames to all outputs
        for output_id, output in self.outputs.items():
            if not output.enabled:
                continue
            
            try:
                # Get slice for this output
                slice_id = output.config.get('slice', 'full')
                sliced_frame = self.slice_manager.get_slice(slice_id, frame)
                
                # Push to output queue
                output.push_frame(sliced_frame, self.latest_timestamp)
                
            except Exception as e:
                logger.error(f"[{self.player_name}] Error processing output '{output_id}': {e}")
    
    def enable_output(self, output_id: str):
        """Enable an output dynamically"""
        if output_id in self.outputs:
            output = self.outputs[output_id]
            output.enabled = True
            if output.initialize():
                output.start_thread()
                logger.info(f"[{self.player_name}] Output '{output_id}' enabled")
            else:
                logger.error(f"[{self.player_name}] Failed to enable output '{output_id}'")
                output.enabled = False
    
    def disable_output(self, output_id: str):
        """Disable an output dynamically"""
        if output_id in self.outputs:
            output = self.outputs[output_id]
            output.enabled = False
            output.stop_thread()
            logger.info(f"[{self.player_name}] Output '{output_id}' disabled")
    
    def get_output_stats(self) -> dict:
        """Get statistics for all outputs"""
        stats = {}
        for output_id, output in self.outputs.items():
            stats[output_id] = output.get_stats()
        return stats
    
    def cleanup(self):
        """Stop and cleanup all outputs"""
        logger.info(f"[{self.player_name}] Cleaning up OutputManager...")
        for output_id in list(self.outputs.keys()):
            self.unregister_output(output_id)
```

### **✅ Verification Step 1:**
```bash
# Test imports
cd src
python -c "from modules.outputs import OutputManager, SliceManager; print('✅ Core modules imported successfully')"
```

---

## 📦 Phase 2: Display Output Plugin (2-3 hours)

### **Step 2.1: Create Display Output Plugin**

**File: `src/modules/outputs/plugins/__init__.py`**
```python
"""
Output Plugins
"""

from .display_output import DisplayOutputPlugin

__all__ = ['DisplayOutputPlugin']
```

**File: `src/modules/outputs/plugins/display_output.py`**
```python
"""
Display Output Plugin - Renders frames to display windows
"""
import cv2
import numpy as np
from ..output_base import OutputPluginBase
from ...logger import get_logger

logger = get_logger(__name__)

# Check if screeninfo is available
try:
    from screeninfo import get_monitors
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False
    logger.warning("screeninfo not available, multi-monitor support limited")


class DisplayOutputPlugin(OutputPluginBase):
    """Display output plugin - creates OpenCV windows on monitors"""
    
    def __init__(self, output_id: str, config: dict):
        super().__init__(output_id, config)
        
        self.monitor_index = config.get('monitor_index', 0)
        self.fullscreen = config.get('fullscreen', True)
        self.resolution = tuple(config.get('resolution', [1920, 1080]))
        self.window_title = config.get('window_title', f'Flux Display - {output_id}')
        self.window_created = False
        
        logger.info(f"DisplayOutput '{output_id}': monitor={self.monitor_index}, "
                   f"fullscreen={self.fullscreen}, resolution={self.resolution}")
    
    def initialize(self) -> bool:
        """Create display window"""
        try:
            # Create window
            cv2.namedWindow(self.window_title, cv2.WINDOW_NORMAL)
            
            if self.fullscreen:
                # Fullscreen mode
                cv2.setWindowProperty(self.window_title, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                
                # Position on target monitor if screeninfo available
                if SCREENINFO_AVAILABLE:
                    monitors = get_monitors()
                    if self.monitor_index < len(monitors):
                        monitor = monitors[self.monitor_index]
                        cv2.moveWindow(self.window_title, monitor.x, monitor.y)
                        logger.info(f"Window positioned on monitor {self.monitor_index} at {monitor.x},{monitor.y}")
                    else:
                        logger.warning(f"Monitor {self.monitor_index} not found, using primary")
            else:
                # Windowed mode
                cv2.resizeWindow(self.window_title, *self.resolution)
                
                # Position with offset if multi-monitor
                if SCREENINFO_AVAILABLE and self.monitor_index > 0:
                    monitors = get_monitors()
                    if self.monitor_index < len(monitors):
                        monitor = monitors[self.monitor_index]
                        cv2.moveWindow(self.window_title, monitor.x + 100, monitor.y + 100)
            
            self.window_created = True
            logger.info(f"Display window '{self.window_title}' created successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create display window: {e}", exc_info=True)
            return False
    
    def send_frame(self, frame: np.ndarray, timestamp: float):
        """Display frame in window"""
        if not self.window_created:
            return
        
        try:
            # Resize if needed
            if frame.shape[:2][::-1] != self.resolution:
                frame = cv2.resize(frame, self.resolution, interpolation=cv2.INTER_LINEAR)
            
            # Convert RGB to BGR for OpenCV
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            # Display
            cv2.imshow(self.window_title, frame_bgr)
            cv2.waitKey(1)  # Required for OpenCV to process events
            
        except Exception as e:
            logger.error(f"Error displaying frame: {e}")
            self.window_created = False
    
    def cleanup(self):
        """Close display window"""
        if self.window_created:
            try:
                cv2.destroyWindow(self.window_title)
                logger.info(f"Display window '{self.window_title}' closed")
            except:
                pass
            self.window_created = False
```

### **Step 2.2: Add Dependency**

Add to `requirements.txt`:
```
screeninfo>=0.8.1
```

Install:
```bash
pip install screeninfo
```

### **✅ Verification Step 2:**
```bash
# Test display output (creates test window)
python -c "
from modules.outputs.plugins import DisplayOutputPlugin
import numpy as np
import time

output = DisplayOutputPlugin('test', {
    'enabled': True,
    'fps': 30,
    'fullscreen': False,
    'resolution': [800, 600]
})

if output.initialize():
    print('✅ Display window created')
    # Show test pattern for 3 seconds
    test_frame = np.random.randint(0, 255, (600, 800, 3), dtype=np.uint8)
    for i in range(90):
        output.send_frame(test_frame, time.time())
        time.sleep(1/30)
    output.cleanup()
    print('✅ Display output test passed')
else:
    print('❌ Failed to create window')
"
```

---

## 📦 Phase 3: Player Integration (2-3 hours)

### **Step 3.1: Modify Player Core (Minimal Changes)**

**File: `src/modules/player_core.py`**

**Change 1:** Add imports at the top:
```python
# ADD after existing imports (around line 10-20)
from .outputs import OutputManager
```

**Change 2:** In `Player.__init__()`, add output manager initialization:

Find this section (around line 145-150):
```python
        # Art-Net Manager wird extern gesetzt
        self.artnet_manager = None
```

ADD this section right after:
```python
        # Output Manager (NEW - for video player only, Art-Net player keeps existing behavior)
        self.output_manager = None
        if not enable_artnet and 'output_routing' in self.config:
            # Only initialize output manager for video player (preview only)
            self.output_manager = OutputManager(
                player_name=self.player_name,
                canvas_width=self.canvas_width,
                canvas_height=self.canvas_height,
                config=self.config
            )
            logger.info(f"[{self.player_name}] OutputManager initialized")
```

**Change 3:** In `Player._play_loop()`, add output frame distribution:

Find this section (around line 1200-1250), after effects are applied:
```python
                # Transition anwenden
                if self.transition_manager:
                    frame = self.transition_manager.apply(frame, self.player_name)
```

ADD this section right after:
```python
                # Send to output manager (video player only)
                if self.output_manager:
                    self.output_manager.update_frame(frame)
```

**Change 4:** In `Player.stop()`, add cleanup:

Find this section (around line 850):
```python
        # Cleanup
        if self.source:
            self.source.cleanup()
```

ADD this section right after:
```python
        # Cleanup output manager
        if self.output_manager:
            self.output_manager.cleanup()
            logger.debug(f"[{self.player_name}] OutputManager cleaned up")
```

### **✅ Verification Step 3:**
```bash
# Check syntax
python -m py_compile src/modules/player_core.py
echo "✅ player_core.py syntax OK"
```

---

## 📦 Phase 4: Configuration (30 min)

### **Step 4.1: Update config.json**

**File: `config.json`**

Add this section after the `"video"` section:

```json
{
  "video": {
    ...existing video config...
  },
  
  "output_routing": {
    "video_player": {
      "outputs": {
        "display_main": {
          "type": "display",
          "enabled": false,
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
          "slice": "full",
          "monitor_index": 1,
          "fullscreen": true,
          "resolution": [1920, 1080],
          "fps": 30,
          "window_title": "Flux Secondary Display"
        }
      }
    }
  },
  
  "slices": {
    "definitions": {
      "full": {
        "x": 0,
        "y": 0,
        "width": 1920,
        "height": 1080,
        "description": "Full frame"
      },
      "left_half": {
        "x": 0,
        "y": 0,
        "width": 960,
        "height": 1080,
        "description": "Left half"
      },
      "right_half": {
        "x": 960,
        "y": 0,
        "width": 960,
        "height": 1080,
        "description": "Right half"
      }
    },
    "presets": {
      "dual_horizontal": ["left_half", "right_half"],
      "single": ["full"]
    }
  }
}
```

---

## 📦 Phase 5: API Endpoints (2 hours)

### **Step 5.1: Create Outputs API**

**File: `src/modules/api_outputs.py`**
```python
"""
Output Routing API Endpoints
"""
from flask import jsonify, request
from .logger import get_logger

logger = get_logger(__name__)


def register_output_routes(app, player_manager):
    """Register output routing API routes"""
    
    @app.route('/api/outputs/<player_id>', methods=['GET'])
    def get_outputs(player_id):
        """Get all outputs for a player"""
        try:
            player = player_manager.get_player(player_id)
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            stats = player.output_manager.get_output_stats()
            
            return jsonify({
                'success': True,
                'outputs': stats
            })
        except Exception as e:
            logger.error(f"Error getting outputs: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/outputs/<player_id>/<output_id>/enable', methods=['POST'])
    def enable_output(player_id, output_id):
        """Enable an output"""
        try:
            player = player_manager.get_player(player_id)
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            player.output_manager.enable_output(output_id)
            
            return jsonify({'success': True, 'message': f'Output {output_id} enabled'})
        except Exception as e:
            logger.error(f"Error enabling output: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/outputs/<player_id>/<output_id>/disable', methods=['POST'])
    def disable_output(player_id, output_id):
        """Disable an output"""
        try:
            player = player_manager.get_player(player_id)
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            player.output_manager.disable_output(output_id)
            
            return jsonify({'success': True, 'message': f'Output {output_id} disabled'})
        except Exception as e:
            logger.error(f"Error disabling output: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/slices', methods=['GET'])
    def get_slices():
        """Get all slice definitions"""
        try:
            player = player_manager.get_player('video')
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            slices = player.output_manager.slice_manager.get_all_slices()
            
            return jsonify({
                'success': True,
                'slices': slices,
                'canvas': {
                    'width': player.output_manager.canvas_width,
                    'height': player.output_manager.canvas_height
                }
            })
        except Exception as e:
            logger.error(f"Error getting slices: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/slices', methods=['POST'])
    def add_slice():
        """Add new slice definition"""
        try:
            data = request.get_json()
            player = player_manager.get_player('video')
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            slice_id = data.get('slice_id')
            x = data.get('x', 0)
            y = data.get('y', 0)
            width = data.get('width', 1920)
            height = data.get('height', 1080)
            description = data.get('description', '')
            
            player.output_manager.slice_manager.add_slice(slice_id, x, y, width, height, description)
            
            return jsonify({
                'success': True,
                'message': f'Slice {slice_id} added'
            })
        except Exception as e:
            logger.error(f"Error adding slice: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/slices/<slice_id>', methods=['DELETE'])
    def delete_slice(slice_id):
        """Delete slice definition"""
        try:
            player = player_manager.get_player('video')
            if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                return jsonify({'success': False, 'error': 'Output manager not available'}), 404
            
            player.output_manager.slice_manager.remove_slice(slice_id)
            
            return jsonify({
                'success': True,
                'message': f'Slice {slice_id} deleted'
            })
        except Exception as e:
            logger.error(f"Error deleting slice: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info("Output routing API routes registered")
```

### **Step 5.2: Register API Routes**

**File: `src/modules/rest_api.py`**

Find the section where routes are registered (around line 50-80):

```python
        # Find this section:
        from .api_transitions import register_transition_routes
        register_transition_routes(app, self.player_manager)
```

ADD this line right after:
```python
        from .api_outputs import register_output_routes
        register_output_routes(app, self.player_manager)
```

### **✅ Verification Step 5:**
```bash
# Test API endpoints (after starting server)
curl http://localhost:5000/api/slices
# Should return slice definitions

curl http://localhost:5000/api/outputs/video
# Should return output stats
```

---

## 📦 Phase 6: Load Outputs on Startup (1-2 hours)

### **Step 6.1: Create Output Loader**

Add to `src/modules/outputs/output_manager.py`:

```python
    def load_outputs_from_config(self):
        """Load and register outputs from config"""
        player_config = self.config.get('output_routing', {}).get('video_player', {})
        outputs_config = player_config.get('outputs', {})
        
        if not outputs_config:
            logger.info(f"[{self.player_name}] No outputs configured")
            return
        
        for output_id, output_config in outputs_config.items():
            output_type = output_config.get('type', 'display')
            
            try:
                if output_type == 'display':
                    from .plugins import DisplayOutputPlugin
                    output = DisplayOutputPlugin(output_id, output_config)
                    self.register_output(output_id, output)
                else:
                    logger.warning(f"[{self.player_name}] Unknown output type '{output_type}' for '{output_id}'")
                    
            except Exception as e:
                logger.error(f"[{self.player_name}] Failed to load output '{output_id}': {e}", exc_info=True)
        
        logger.info(f"[{self.player_name}] Loaded {len(self.outputs)} outputs from config")
```

### **Step 6.2: Call Loader in Player Init**

**File: `src/modules/player_core.py`**

Update the output manager initialization:

```python
        # Output Manager (NEW - for video player only)
        self.output_manager = None
        if not enable_artnet and 'output_routing' in self.config:
            self.output_manager = OutputManager(
                player_name=self.player_name,
                canvas_width=self.canvas_width,
                canvas_height=self.canvas_height,
                config=self.config
            )
            # Load outputs from config
            self.output_manager.load_outputs_from_config()
            logger.info(f"[{self.player_name}] OutputManager initialized with {len(self.output_manager.outputs)} outputs")
```

---

## 📦 Phase 7: Frontend - Slice Editor (3-4 hours)

**Status:** Not yet implemented. Will include:
- `frontend/slice-editor.html` - Visual slice editor page
- `frontend/js/slice-editor.js` - SVG-based slice manipulation
- `frontend/css/slice-editor.css` - Styling
- Live video preview background (using `/api/preview/video/stream`)
- Drag-and-drop slice creation
- Preset templates (dual, triple, quad, video wall)
- Export/import slice configurations

---

## 📦 Phase 8: Compositor System (Future)

**Status:** Not yet implemented. Will enable:
- Multiple slices per output
- Layer compositing with transforms (position, rotation, scale, opacity)
- Projection mapping (quad warping)
- Picture-in-picture effects
- Bezel compensation for video walls

**File structure:**
- `src/modules/outputs/compositor.py`
- Enhanced output config with layer definitions

---

## 🧪 Testing Checklist

### **Phase 1-5 Testing:**
```bash
# 1. Test imports
python -c "from modules.outputs import OutputManager; print('✅ Imports OK')"

# 2. Test display output
# (Creates window for 3 seconds)
python test_scripts/test_display_output.py

# 3. Start server and test API
curl http://localhost:5000/api/slices
curl http://localhost:5000/api/outputs/video

# 4. Enable display output via API
curl -X POST http://localhost:5000/api/outputs/video/display_main/enable

# 5. Play video and verify output window appears
# Load video in player, output should show automatically
```

### **Integration Testing:**
1. Start server with updated config
2. Load video in video player
3. Enable display output via config or API
4. Verify output window shows video content
5. Test slice assignment (left_half, right_half)
6. Verify each output shows correct slice
7. Test dynamic enable/disable of outputs

---

## 🚨 Troubleshooting

### **Issue: Output manager not initialized**
**Cause:** Config missing `output_routing` section or Art-Net player selected
**Solution:** Check config.json has `output_routing` section, verify video player (not Art-Net)

### **Issue: Display window not appearing**
**Cause:** OpenCV not installed or monitor_index invalid
**Solution:** 
```bash
pip install opencv-python screeninfo
```
Check monitor count, adjust monitor_index in config

### **Issue: Frames not being sent to outputs**
**Cause:** Output disabled or initialization failed
**Solution:** Check logs for initialization errors, verify output enabled in config

### **Issue: Import errors for outputs module**
**Cause:** Module structure incorrect
**Solution:** Verify all `__init__.py` files exist with correct imports

---

## 📝 Future Enhancements

### **Additional Output Plugins:**
- **NDI Output** - Network Device Interface streaming
- **Recording Output** - Save to MP4/MOV files
- **Virtual Camera** - OBS Virtual Camera compatible
- **Spout/Syphon** - Texture sharing (Windows/Mac)
- **HTTP Stream** - MJPEG/HLS streaming
- **Custom Script** - User-defined Python output handlers

### **Advanced Features:**
- Real-time output performance monitoring
- Output failover (backup outputs)
- Output synchronization (frame-accurate multi-output)
- Hardware acceleration (GPU-based scaling)
- Network output (remote displays over network)

---

## 📚 References

- Output Routing Architecture Design
- Slice Editor UI Mockups
- Multi-Layer Compositor Design
- Projection Mapping Implementation Guide

---

**Last Updated:** 2026-01-08
**Version:** 1.0
**Status:** Phases 1-5 Complete, Frontend Pending
