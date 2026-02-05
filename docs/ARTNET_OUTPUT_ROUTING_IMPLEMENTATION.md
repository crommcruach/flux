# 🎯 ArtNet Output Routing - Backend Implementation Plan

**Date:** February 4, 2026  
**Status:** Planning Phase  
**Frontend Prototype:** `snippets/artnet-output/artnet-output-prototype.html`

---

## 📋 Executive Summary

This document outlines the complete backend implementation required to support the ArtNet output routing system. The frontend prototype is complete with all UI features. This plan focuses on the Python backend architecture to handle:

- **ArtNet objects** (LED fixtures with spatial positioning and color correction)
- **ArtNet outputs** (network targets with universe/subnet configuration)
- **Object-to-output assignments** (routing pixel data from player to physical fixtures)
- **Master-slave object linking** (color synchronization between fixtures)
- **Per-object and per-output color correction** (brightness, contrast, RGB adjustment)
- **Layer input routing** (assigning objects to player layers 0-10)
- **RGB format mapping** (supporting different LED strip wiring: RGB, GRB, BGR, etc.)

---

## 🎨 Frontend Prototype Features (Implemented)

### ✅ Object Management
- Canvas-based visual editor with zoom/pan
- Object positioning with drag-and-drop
- Object transformation: move, scale, rotate
- Multi-select with Ctrl+click for group operations
- Point flip/reverse for LED direction control
- Object types: matrix, circle, line, star (expandable)
- Collapsible object list UI (default collapsed)

### ✅ Object Properties (Per Object)
- **Spatial:** Points array with x,y coordinates
- **Network:** Universe start/end assignment (auto-calculated based on LED type)
- **LED Type Configuration:**
  - **LED Type Selector:** RGB, RGBW, RGBAW, RGBWW, RGBCW, RGBCWW
  - **Channels Per Pixel:** Auto-calculated (RGB=3, RGBW=4, RGBAW=5, RGBCWW=6)
  - **Max Pixels/Universe:** Auto-displayed (RGB=170, RGBW=127, RGBAW=102, RGBCWW=85)
  - **Channel Order:** Flexible mapping (RGB, GRB, RGBW, GRBW, WRGB, etc.)
- **White Channel Configuration (for RGBW+):**
  - **Enable White Detection:** Toggle automatic white detection
  - **Detection Mode:** Average, Minimum, Luminance (ITU-R BT.709)
  - **White Threshold:** 0-255 slider (default 200) - minimum RGB for white detection
  - **White Behavior:** Replace (reduce RGB), Additive (keep RGB), Hybrid (50/50)
  - **Color Temperature:** 2700K-6500K slider (for multi-white LEDs)
  - **Channel Assignment:** Select which physical channel is warm/cool/amber white
- **Timing:** Delay in milliseconds
- **Color Correction:** 
  - Brightness (-255 to 255, default 0)
  - Contrast (-255 to 255, default 0)
  - Red (-255 to 255, default 0)
  - Green (-255 to 255, default 0)
  - Blue (-255 to 255, default 0)
- **Input Layer:** player (Layer 0), layer1-layer10
- **Linking:** Master-slave relationships (same type and point count required)

### ✅ Output Configuration (Per Output)
- **Network:** Target IP, Subnet mask, Start universe
- **Protocol:** FPS (frames per second)
- **Timing:** Delay in milliseconds
- **Color Correction:** Brightness, Contrast, Red, Green, Blue (-255 to 255)
- **Delta Encoding:** Toggle + settings modal (threshold, full frame interval)
- **Object Assignment:** Multiple objects per output
- **Status:** Active/Inactive toggle

### ✅ Visualization & Preview
- Color preview mode (samples pixel colors from background)
- Test pattern generation (color bars, gradient, checkerboard)
- Resolution selector (1024×768 to 3840×2160, custom)
- Master-slave link visualization (colored lines, M/S labels)
- Transform handles for canvas manipulation

### ✅ Delta Encoding UI (Per Output)
- **Toggle Button:** Enable/disable delta encoding in output properties
- **Settings Modal:** Opens when clicking "Delta Settings" button
  - **Threshold Slider:** 0-20 (default 8) - Minimum RGB change to transmit
  - **Full Frame Interval:** 1-120 frames (default 30) - Send full frame every N frames
  - **Description:** "Delta encoding sends only changed pixels, reducing network traffic by up to 80%"
  - **Statistics (Runtime):** 
    - Changed pixels: XX%
    - Data reduction: XX%
    - Network savings: XX KB/s

---

## 💡 LED Type System Explained

### Supported LED Types

| LED Type | Channels | Description | Max Pixels/Universe | Use Case |
|----------|----------|-------------|---------------------|----------|
| **RGB** | 3 | Standard RGB LEDs | 170 (510÷3) | Basic color lighting, video mapping |
| **RGBW** | 4 | RGB + White | 127 (508÷4) | Better whites, architectural lighting |
| **RGBAW** | 5 | RGB + Amber + White | 102 (510÷5) | Warm whites, stage lighting, film |
| **RGBWW** | 5 | RGB + Warm + Cool White | 102 (510÷5) | Tunable white temperature |
| **RGBCW** | 5 | RGB + Cool + Warm White | 102 (510÷5) | Same as RGBWW, different order |
| **RGBCWW** | 6 | RGB + Cool + Warm + White | 85 (510÷6) | Maximum white control |

### Universe Calculation

**DMX512 Standard:**
- 512 channels per universe
- 510 usable channels (2 used by ArtNet header)

**Auto-Calculation Formula:**
```
Max Pixels = floor(510 / channels_per_pixel)
Universes Needed = ceil(total_pixels * channels_per_pixel / 510)
```

**Examples:**
```
100 RGB LEDs:
  - Channels: 100 × 3 = 300 channels
  - Universes: 1 (fits in 510)
  
200 RGBW LEDs:
  - Channels: 200 × 4 = 800 channels  
  - Universes: 2 (first 127 in universe 1, remaining 73 in universe 2)
  
150 RGBAW LEDs:
  - Channels: 150 × 5 = 750 channels
  - Universes: 2 (first 102 in universe 1, remaining 48 in universe 2)
```

### White Channel Detection Modes

#### 1. **Minimum Mode** (Recommended for RGBW)
```python
white = min(R, G, B)
# Example: RGB(200, 180, 190) → W=180
# Extracts the "common" color component
```

**Best for:** Simple RGBW strips where you want maximum white extraction.

#### 2. **Average Mode**
```python
white = (R + G + B) / 3
# Example: RGB(200, 180, 190) → W=190
```

**Best for:** Balanced white detection, good for amber+white LEDs.

#### 3. **Luminance Mode** (ITU-R BT.709)
```python
white = 0.2126 × R + 0.7152 × G + 0.0722 × B
# Example: RGB(200, 180, 190) → W=185
# Perceptually accurate luminance
```

**Best for:** Professional installations where perceived brightness matters.

### White Channel Behaviors

#### 1. **Replace Mode**
- Reduces RGB by white amount
- Adds white channel value
- **Effect:** Purer colors, more efficient (less power)
- **Example:** `RGB(200, 200, 200) → RGBW(0, 0, 0, 200)`

```python
white = min(R, G, B)
new_R = R - white
new_G = G - white  
new_B = B - white
W = white
```

#### 2. **Additive Mode**
- Keeps RGB unchanged
- Adds white on top
- **Effect:** Brighter output, more saturated
- **Example:** `RGB(200, 200, 200) → RGBW(200, 200, 200, 200)`

```python
white = min(R, G, B)
new_R = R
new_G = G
new_B = B
W = white
```

#### 3. **Hybrid Mode** (Recommended)
- 50% replace, 50% keep
- Balanced approach
- **Effect:** Good color accuracy with brightness boost
- **Example:** `RGB(200, 200, 200) → RGBW(100, 100, 100, 200)`

```python
white = min(R, G, B)
reduce = white / 2
new_R = R - reduce
new_G = G - reduce
new_B = B - reduce
W = white
```

### White Threshold

Prevents activating white channel for colors that aren't "white enough":

```python
if white >= threshold:
    # Use white channel
else:
    # Pure RGB mode, no white
```

**Examples:**
- Threshold = 200: Only RGB(200+, 200+, 200+) triggers white
- Threshold = 100: RGB(100+, 100+, 100+) triggers white
- Threshold = 0: Always uses white channel (not recommended)

**Recommended Values:**
- **RGBW:** 200 (only bright whites)
- **RGBAW:** 150 (more sensitive for warm whites)
- **RGBWW/RGBCWW:** 180 (balanced)

### Color Temperature Mapping (Multi-White LEDs)

For RGBWW/RGBCW/RGBCWW LEDs with separate warm and cool white channels:

```python
# Color temperature range: 2700K (warm) to 6500K (cool)
temp_normalized = (color_temp - 2700) / (6500 - 2700)

warm_white = white_value × (1 - temp_normalized)
cool_white = white_value × temp_normalized
```

**Examples:**
- 2700K: 100% warm, 0% cool → `RGBWW(R, G, B, 255, 0)`
- 4500K: 50% warm, 50% cool → `RGBWW(R, G, B, 128, 128)`
- 6500K: 0% warm, 100% cool → `RGBWW(R, G, B, 0, 255)`

### Channel Order Examples

**RGB (3 channels):**
- `RGB`: Red-Green-Blue (standard)
- `GRB`: Green-Red-Blue (WS2812B LEDs)
- `BGR`: Blue-Green-Red (some Chinese strips)

**RGBW (4 channels):**
- `RGBW`: Red-Green-Blue-White (standard)
- `GRBW`: Green-Red-Blue-White (WS2812B RGBW)
- `WRGB`: White-Red-Green-Blue (some 4-channel strips)

**RGBAW (5 channels):**
- `RGBAW`: Red-Green-Blue-Amber-White
- `RGBWA`: Red-Green-Blue-White-Amber

**RGBWW (5 channels):**
- `RGBWW`: Red-Green-Blue-WarmWhite-CoolWhite
- `RGBCW`: Red-Green-Blue-CoolWhite-WarmWhite

**RGBCWW (6 channels):**
- `RGBCWW`: Red-Green-Blue-CoolWhite-WarmWhite-White

---

## 🏗️ Backend Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Player Core (Existing)                    │
│  - Video playback / Generators                               │
│  - Layer system (0-10 layers)                                │
│  - Effect processing pipeline                                │
│  - Frame output (numpy array)                                │
└──────────────────┬──────────────────────────────────────────┘
                   │ processed_frame (numpy array)
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              ArtNet Output Manager (NEW)                     │
│  - Object registry                                           │
│  - Output registry                                           │
│  - Color correction processor                                │
│  - Master-slave resolver                                     │
│  - Pixel sampling & mapping                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │ DMX data per output
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              ArtNet Sender (Enhanced)                        │
│  - UDP socket per output                                     │
│  - Universe packetization (512 channels/universe)            │
│  - Subnet handling                                           │
│  - FPS throttling                                            │
│  - Delay buffer                                              │
└─────────────────────────────────────────────────────────────┘
                   │ UDP packets
                   ▼
         Network (ArtNet Protocol)
```

---

## 📦 Module Structure

### New Modules to Create

```
src/modules/artnet_routing/
├── __init__.py
├── artnet_object.py          # ArtNet object data model
├── artnet_output.py          # ArtNet output data model
├── output_manager.py         # Main output routing logic
├── color_correction.py       # Color correction algorithms
├── pixel_sampler.py          # Canvas pixel sampling
├── master_slave_resolver.py  # Link relationship resolver
├── rgb_format_mapper.py      # RGB channel order mapping
└── artnet_sender.py          # Enhanced ArtNet UDP sender
```

### Integration Points

```
src/modules/
├── player_core.py            # MODIFY: Add ArtNet output manager
├── session_state.py          # MODIFY: Add ArtNet config persistence
├── api_artnet.py             # NEW: REST API endpoints
└── config_schema.py          # MODIFY: Add ArtNet config schema
```

---

## 🔧 Data Models

### 1. ArtNet Object Model

```python
# artnet_object.py

@dataclass
class ArtNetPoint:
    """Single LED point in 2D space"""
    id: int                    # Sequential ID (1, 2, 3, ...)
    x: float                   # X coordinate on canvas
    y: float                   # Y coordinate on canvas
    color: Optional[Tuple[int, int, int]] = None  # RGB color (0-255)

@dataclass
class ArtNetObject:
    """LED fixture/object with spatial positioning"""
    id: str                    # UUID
    name: str                  # Display name
    type: str                  # 'matrix', 'circle', 'line', 'star', etc.
    points: List[ArtNetPoint]  # Array of LED points
    
    # Network assignment
    universe_start: int        # Starting ArtNet universe (1-32768)
    universe_end: int          # Ending universe (calculated from point count and LED type)
    
    # LED Type Configuration
    led_type: str = 'RGB'      # 'RGB', 'RGBW', 'RGBAW', 'RGBWW', 'RGBCWW'
    channels_per_pixel: int = 3  # Auto-calculated: RGB=3, RGBW=4, RGBAW=5, etc.
    channel_order: str = 'RGB'   # Channel mapping: 'RGB', 'RGBW', 'GRBW', 'RGBWWCW', etc.
    
    # White Channel Configuration
    white_detection_enabled: bool = True     # Enable automatic white detection
    white_detection_mode: str = 'luminance'  # 'average', 'minimum', 'luminance'
    white_threshold: int = 200               # RGB threshold for white detection (0-255)
    white_channel_behavior: str = 'hybrid'   # 'additive', 'replace', 'hybrid'
    
    # Multi-White Channel Configuration (for RGBAW, RGBWW, RGBCWW)
    warm_white_channel: int = 3    # Channel index for warm white (0-based)
    cool_white_channel: int = 4    # Channel index for cool white (0-based, -1 if unused)
    amber_channel: int = -1        # Channel index for amber (0-based, -1 if unused)
    color_temperature: int = 3200  # Color temperature in Kelvin (2700-6500)
    
    # Timing
    delay: int = 0             # Delay in milliseconds
    
    # Color correction
    brightness: int = 0        # -255 to 255
    contrast: int = 0          # -255 to 255
    red: int = 0               # -255 to 255
    green: int = 0             # -255 to 255
    blue: int = 0              # -255 to 255
    
    # Layer routing
    input_layer: str = 'player'  # 'player', 'layer1', 'layer2', ... 'layer10'
    
    # Master-slave linking
    master_id: Optional[str] = None  # ID of master object (if slave)
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'points': [{'id': p.id, 'x': p.x, 'y': p.y} for p in self.points],
            'universeStart': self.universe_start,
            'universeEnd': self.universe_end,
            'ledType': self.led_type,
            'channelsPerPixel': self.channels_per_pixel,
            'channelOrder': self.channel_order,
            'whiteDetectionEnabled': self.white_detection_enabled,
            'whiteDetectionMode': self.white_detection_mode,
            'whiteThreshold': self.white_threshold,
            'whiteChannelBehavior': self.white_channel_behavior,
            'warmWhiteChannel': self.warm_white_channel,
            'coolWhiteChannel': self.cool_white_channel,
            'amberChannel': self.amber_channel,
            'colorTemperature': self.color_temperature,
            'delay': self.delay,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'input': self.input_layer,
            'masterId': self.master_id
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetObject':
        """Deserialize from JSON"""
        points = [
            ArtNetPoint(id=p['id'], x=p['x'], y=p['y'])
            for p in data['points']
        ]
        
        # Auto-calculate channels_per_pixel from led_type if not provided
        led_type = data.get('ledType', 'RGB')
        channels_per_pixel = data.get('channelsPerPixel', _calculate_channels_per_pixel(led_type))
        
        return ArtNetObject(
            id=data['id'],
            name=data['name'],
            type=data['type'],
            points=points,
            universe_start=data['universeStart'],
            universe_end=data['universeEnd'],
            led_type=led_type,
            channels_per_pixel=channels_per_pixel,
            channel_order=data.get('channelOrder', led_type),
            white_detection_enabled=data.get('whiteDetectionEnabled', True),
            white_detection_mode=data.get('whiteDetectionMode', 'luminance'),
            white_threshold=data.get('whiteThreshold', 200),
            white_channel_behavior=data.get('whiteChannelBehavior', 'hybrid'),
            warm_white_channel=data.get('warmWhiteChannel', 3),
            cool_white_channel=data.get('coolWhiteChannel', -1),
            amber_channel=data.get('amberChannel', -1),
            color_temperature=data.get('colorTemperature', 3200),
            delay=data.get('delay', 0),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            input_layer=data.get('input', 'player'),
            master_id=data.get('masterId')
        )

# Helper function
def _calculate_channels_per_pixel(led_type: str) -> int:
    """Auto-calculate channels per pixel based on LED type"""
    channel_map = {
        'RGB': 3,
        'RGBW': 4,
        'RGBAW': 5,
        'RGBWW': 5,
        'RGBCW': 5,
        'RGBCWW': 6,
        'RGBAWWCW': 7
    }
    return channel_map.get(led_type, 3)
```

### 2. ArtNet Output Model

```python
# artnet_output.py

@dataclass
class ArtNetOutput:
    """ArtNet network output target"""
    id: str                    # UUID
    name: str                  # Display name
    target_ip: str             # Target IP address
    subnet: str                # Subnet mask (e.g., '255.255.255.0')
    start_universe: int        # Starting universe for this output
    fps: int = 30              # Frames per second
    delay: int = 0             # Delay in milliseconds
    
    # Color correction (applied to all objects on this output)
    brightness: int = 0        # -255 to 255
    contrast: int = 0          # -255 to 255
    red: int = 0               # -255 to 255
    green: int = 0             # -255 to 255
    blue: int = 0              # -255 to 255
    
    # Delta encoding optimization
    delta_encoding_enabled: bool = True       # Enable delta encoding (send only changed pixels)
    delta_threshold: int = 8                   # Threshold for 8-bit change detection (0-20)
    delta_full_frame_interval: int = 30        # Send full frame every N frames
    
    # Object assignments
    assigned_objects: List[str] = field(default_factory=list)  # Object IDs
    
    # Status
    active: bool = False       # Enable/disable output
    
    # Runtime state (not serialized)
    _last_frame_time: float = 0.0
    _delay_buffer: deque = field(default_factory=lambda: deque(maxlen=60))
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'targetIP': self.target_ip,
            'subnet': self.subnet,
            'startUniverse': self.start_universe,
            'fps': self.fps,
            'delay': self.delay,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'deltaEncodingEnabled': self.delta_encoding_enabled,
            'deltaThreshold': self.delta_threshold,
            'deltaFullFrameInterval': self.delta_full_frame_interval,
            'assignedObjects': self.assigned_objects,
            'active': self.active
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetOutput':
        """Deserialize from JSON"""
        return ArtNetOutput(
            id=data['id'],
            name=data['name'],
            target_ip=data['targetIP'],
            subnet=data.get('subnet', '255.255.255.0'),
            start_universe=data['startUniverse'],
            fps=data.get('fps', 30),
            delay=data.get('delay', 0),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            delta_encoding_enabled=data.get('deltaEncodingEnabled', True),
            delta_threshold=data.get('deltaThreshold', 8),
            delta_full_frame_interval=data.get('deltaFullFrameInterval', 30),
            assigned_objects=data.get('assignedObjects', []),
            active=data.get('active', False)
        )
```

---

## 🎨 Core Processing Pipeline

### Output Manager Class

```python
# output_manager.py

class ArtNetOutputManager:
    """
    Main output routing manager.
    
    Responsibilities:
    - Manage ArtNet objects and outputs registry
    - Sample pixels from player frame based on object points
    - Apply color correction (per-object and per-output)
    - Resolve master-slave links
    - Map RGB formats
    - Apply delays
    - Generate DMX data and send to ArtNet outputs
    """
    
    def __init__(self, canvas_width: int, canvas_height: int):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        
        # Registries
        self.objects: Dict[str, ArtNetObject] = {}
        self.outputs: Dict[str, ArtNetOutput] = {}
        
        # Components
        self.pixel_sampler = PixelSampler()
        self.color_corrector = ColorCorrector()
        self.master_slave_resolver = MasterSlaveResolver()
        self.rgb_mapper = RGBFormatMapper()
        self.artnet_sender = ArtNetSender()
        
        # Layer frame cache (for input layer routing)
        self.layer_frames: Dict[str, np.ndarray] = {}
    
    def register_object(self, obj: ArtNetObject):
        """Add or update an object in registry"""
        self.objects[obj.id] = obj
    
    def register_output(self, output: ArtNetOutput):
        """Add or update an output in registry"""
        self.outputs[output.id] = output
    
    def update_layer_frames(self, layer_frames: Dict[str, np.ndarray]):
        """
        Update cached layer frames from player.
        
        Args:
            layer_frames: {
                'player': composite_frame,  # Layer 0 (background)
                'layer1': layer1_frame,
                'layer2': layer2_frame,
                ...
                'layer10': layer10_frame
            }
        """
        self.layer_frames = layer_frames
    
    def process_frame(self, frame: np.ndarray, layer_frames: Dict[str, np.ndarray]):
        """
        Main processing pipeline. Called once per frame from player.
        
        Args:
            frame: Composite frame from player (numpy array, RGB)
            layer_frames: Individual layer frames for input routing
        """
        self.update_layer_frames(layer_frames)
        
        # Process each active output
        for output in self.outputs.values():
            if not output.active:
                continue
            
            # Check FPS throttling
            if not self._should_send_frame(output):
                continue
            
            # Build DMX data for this output
            dmx_data = self._build_dmx_data(output, frame)
            
            # Apply delay buffer
            if output.delay > 0:
                dmx_data = self._apply_delay(output, dmx_data)
            
            # Send to ArtNet
            self.artnet_sender.send(
                target_ip=output.target_ip,
                start_universe=output.start_universe,
                dmx_data=dmx_data,
                subnet=output.subnet
            )
    
    def _build_dmx_data(self, output: ArtNetOutput, frame: np.ndarray) -> bytes:
        """
        Build DMX data for all objects assigned to this output.
        
        Returns:
            bytes: DMX channel data (3 bytes per pixel: R, G, B)
        """
        dmx_channels = []
        
        for obj_id in output.assigned_objects:
            obj = self.objects.get(obj_id)
            if not obj:
                continue
            
            # Get source frame based on object's input layer
            source_frame = self.layer_frames.get(obj.input_layer, frame)
            
            # Resolve master-slave links
            if obj.master_id:
                # Slave object: inherit colors from master
                master_obj = self.objects.get(obj.master_id)
                if master_obj:
                    pixel_colors = self.master_slave_resolver.resolve_colors(
                        slave_obj=obj,
                        master_obj=master_obj,
                        master_frame=source_frame
                    )
                else:
                    # Master not found, sample normally
                    pixel_colors = self._sample_object_pixels(obj, source_frame)
            else:
                # Master object or independent: sample pixels
                pixel_colors = self._sample_object_pixels(obj, source_frame)
            
            # Apply per-object color correction
            pixel_colors = self.color_corrector.apply(
                pixels=pixel_colors,
                brightness=obj.brightness,
                contrast=obj.contrast,
                red=obj.red,
                green=obj.green,
                blue=obj.blue
            )
            
            # Apply per-output color correction
            pixel_colors = self.color_corrector.apply(
                pixels=pixel_colors,
                brightness=output.brightness,
                contrast=output.contrast,
                red=output.red,
                green=output.green,
                blue=output.blue
            )
            
            # Map RGB format
            pixel_colors = self.rgb_mapper.map_format(
                pixels=pixel_colors,
                format=obj.rgb_format
            )
            
            # Flatten to DMX channel data
            for r, g, b in pixel_colors:
                dmx_channels.extend([r, g, b])
        
        return bytes(dmx_channels)
    
    def _sample_object_pixels(self, obj: ArtNetObject, frame: np.ndarray) -> List[Tuple[int, int, int]]:
        """Sample pixel colors for all points in object"""
        colors = []
        for point in obj.points:
            # Normalize coordinates to frame dimensions
            x = int((point.x / self.canvas_width) * frame.shape[1])
            y = int((point.y / self.canvas_height) * frame.shape[0])
            
            # Clamp to frame bounds
            x = max(0, min(x, frame.shape[1] - 1))
            y = max(0, min(y, frame.shape[0] - 1))
            
            # Sample pixel (assuming RGB format from player)
            r, g, b = frame[y, x]
            colors.append((int(r), int(g), int(b)))
        
        return colors
    
    def _should_send_frame(self, output: ArtNetOutput) -> bool:
        """Check if enough time has passed based on FPS"""
        current_time = time.time()
        frame_interval = 1.0 / output.fps
        
        if current_time - output._last_frame_time >= frame_interval:
            output._last_frame_time = current_time
            return True
        return False
    
    def _apply_delay(self, output: ArtNetOutput, dmx_data: bytes) -> bytes:
        """Apply delay buffer to output"""
        # Add current frame to buffer
        output._delay_buffer.append(dmx_data)
        
        # Calculate frames to delay
        delay_frames = int((output.delay / 1000.0) * output.fps)
        
        # Return delayed frame if buffer is full
        if len(output._delay_buffer) > delay_frames:
            return output._delay_buffer[0]
        else:
            # Buffer not full yet, return black
            return bytes([0] * len(dmx_data))
```

### Color Correction Processor

```python
# color_correction.py

class ColorCorrector:
    """Apply brightness, contrast, and RGB adjustments"""
    
    @staticmethod
    def apply(
        pixels: List[Tuple[int, int, int]],
        brightness: int = 0,
        contrast: int = 0,
        red: int = 0,
        green: int = 0,
        blue: int = 0
    ) -> List[Tuple[int, int, int]]:
        """
        Apply color correction to pixel array.
        
        Args:
            pixels: List of (R, G, B) tuples (0-255)
            brightness: -255 to 255 (additive)
            contrast: -255 to 255 (multiplicative around 128)
            red: -255 to 255 (additive to red channel)
            green: -255 to 255 (additive to green channel)
            blue: -255 to 255 (additive to blue channel)
        
        Returns:
            Corrected pixel list
        """
        corrected = []
        
        # Convert contrast to factor (0.0 to 2.0, center at 1.0)
        contrast_factor = (contrast + 255) / 255.0
        
        for r, g, b in pixels:
            # Apply brightness (additive)
            r = r + brightness
            g = g + brightness
            b = b + brightness
            
            # Apply contrast (multiplicative around midpoint 128)
            r = 128 + (r - 128) * contrast_factor
            g = 128 + (g - 128) * contrast_factor
            b = 128 + (b - 128) * contrast_factor
            
            # Apply RGB adjustments (additive per channel)
            r = r + red
            g = g + green
            b = b + blue
            
            # Clamp to 0-255
            r = max(0, min(255, int(r)))
            g = max(0, min(255, int(g)))
            b = max(0, min(255, int(b)))
            
            corrected.append((r, g, b))
        
        return corrected
```

### Master-Slave Resolver

```python
# master_slave_resolver.py

class MasterSlaveResolver:
    """Resolve master-slave color relationships"""
    
    @staticmethod
    def resolve_colors(
        slave_obj: ArtNetObject,
        master_obj: ArtNetObject,
        master_frame: np.ndarray
    ) -> List[Tuple[int, int, int]]:
        """
        Slave object inherits colors from master's corresponding points.
        
        Logic:
        - If same point count: 1:1 mapping
        - If different point count: interpolate/scale indices
        
        Args:
            slave_obj: Slave object (receives colors)
            master_obj: Master object (provides colors)
            master_frame: Frame to sample master colors from
        
        Returns:
            Color list for slave object
        """
        slave_count = len(slave_obj.points)
        master_count = len(master_obj.points)
        
        # Sample master colors (if not already cached)
        master_colors = []
        for point in master_obj.points:
            # Sample from frame (implement proper sampling)
            x = int(point.x)
            y = int(point.y)
            # Clamp and sample
            x = max(0, min(x, master_frame.shape[1] - 1))
            y = max(0, min(y, master_frame.shape[0] - 1))
            r, g, b = master_frame[y, x]
            master_colors.append((int(r), int(g), int(b)))
        
        # Map to slave points
        slave_colors = []
        for i in range(slave_count):
            if slave_count == master_count:
                # 1:1 mapping
                slave_colors.append(master_colors[i])
            else:
                # Scale index
                master_idx = int((i / slave_count) * master_count)
                master_idx = min(master_idx, master_count - 1)
                slave_colors.append(master_colors[master_idx])
        
        return slave_colors
```

### White Channel Processor

```python
# white_channel_processor.py

class WhiteChannelProcessor:
    """
    Process RGB colors and add white channel data for RGBW/RGBAW/RGBCWW LEDs.
    
    Handles:
    - White detection from RGB values
    - White channel calculation modes
    - Multi-white channel support (warm/cool/amber)
    - Color temperature mapping
    """
    
    @staticmethod
    def process_rgbw(
        rgb_colors: List[Tuple[int, int, int]],
        led_type: str,
        white_detection_enabled: bool,
        white_detection_mode: str,
        white_threshold: int,
        white_channel_behavior: str,
        color_temperature: int = 3200
    ) -> List[Tuple[int, ...]]:
        """
        Convert RGB colors to RGBW/RGBAW/etc. with white channel.
        
        Args:
            rgb_colors: List of (R, G, B) tuples
            led_type: 'RGB', 'RGBW', 'RGBAW', 'RGBWW', 'RGBCWW'
            white_detection_enabled: Enable automatic white detection
            white_detection_mode: 'average', 'minimum', 'luminance'
            white_threshold: Minimum RGB value to consider as white (0-255)
            white_channel_behavior: 'additive', 'replace', 'hybrid'
            color_temperature: Color temp in Kelvin (2700-6500)
        
        Returns:
            List of tuples with white channel(s) added
        """
        if led_type == 'RGB':
            return rgb_colors  # No white channel
        
        result = []
        
        for r, g, b in rgb_colors:
            if not white_detection_enabled:
                # No white detection: return RGB + 0 for white channels
                white_channels = WhiteChannelProcessor._get_zero_white_channels(led_type)
                result.append((r, g, b) + white_channels)
                continue
            
            # Detect white amount
            white_value = WhiteChannelProcessor._detect_white(
                r, g, b, 
                mode=white_detection_mode,
                threshold=white_threshold
            )
            
            if white_value == 0:
                # No white detected
                white_channels = WhiteChannelProcessor._get_zero_white_channels(led_type)
                result.append((r, g, b) + white_channels)
                continue
            
            # Apply white channel behavior
            if white_channel_behavior == 'replace':
                # Replace RGB with white (reduces RGB, adds white)
                new_r = max(0, r - white_value)
                new_g = max(0, g - white_value)
                new_b = max(0, b - white_value)
                white_channels = WhiteChannelProcessor._calculate_white_channels(
                    white_value, led_type, color_temperature
                )
                result.append((new_r, new_g, new_b) + white_channels)
            
            elif white_channel_behavior == 'additive':
                # Keep RGB, add white on top
                white_channels = WhiteChannelProcessor._calculate_white_channels(
                    white_value, led_type, color_temperature
                )
                result.append((r, g, b) + white_channels)
            
            elif white_channel_behavior == 'hybrid':
                # 50% replace, 50% additive (balanced)
                reduce_amount = white_value // 2
                new_r = max(0, r - reduce_amount)
                new_g = max(0, g - reduce_amount)
                new_b = max(0, b - reduce_amount)
                white_channels = WhiteChannelProcessor._calculate_white_channels(
                    white_value, led_type, color_temperature
                )
                result.append((new_r, new_g, new_b) + white_channels)
        
        return result
    
    @staticmethod
    def _detect_white(r: int, g: int, b: int, mode: str, threshold: int) -> int:
        """
        Detect white amount from RGB values.
        
        Returns:
            White value (0-255), 0 if below threshold
        """
        if mode == 'minimum':
            # Minimum of RGB channels
            white = min(r, g, b)
        
        elif mode == 'average':
            # Average of RGB channels
            white = (r + g + b) // 3
        
        elif mode == 'luminance':
            # Perceived luminance (ITU-R BT.709)
            white = int(0.2126 * r + 0.7152 * g + 0.0722 * b)
        
        else:
            white = min(r, g, b)  # Default to minimum
        
        # Apply threshold
        return white if white >= threshold else 0
    
    @staticmethod
    def _calculate_white_channels(
        white_value: int,
        led_type: str,
        color_temperature: int
    ) -> Tuple[int, ...]:
        """
        Calculate white channel values based on LED type and color temperature.
        
        Returns:
            Tuple of white channel values
        """
        if led_type == 'RGBW':
            # Single white channel
            return (white_value,)
        
        elif led_type == 'RGBAW':
            # RGB + Amber + White
            # Split white_value between amber and white based on color temp
            if color_temperature <= 3000:
                # Warm: More amber, less white
                amber = int(white_value * 0.7)
                white = int(white_value * 0.3)
            else:
                # Cool: Less amber, more white
                amber = int(white_value * 0.3)
                white = int(white_value * 0.7)
            return (amber, white)
        
        elif led_type in ['RGBWW', 'RGBCW']:
            # RGB + Warm White + Cool White
            # Split based on color temperature
            # 2700K = 100% warm, 6500K = 100% cool
            temp_range = 6500 - 2700
            temp_normalized = (color_temperature - 2700) / temp_range
            temp_normalized = max(0, min(1, temp_normalized))
            
            warm_white = int(white_value * (1 - temp_normalized))
            cool_white = int(white_value * temp_normalized)
            return (warm_white, cool_white)
        
        elif led_type == 'RGBCWW':
            # RGB + Cool White + Warm White (same as RGBWW but different order)
            temp_range = 6500 - 2700
            temp_normalized = (color_temperature - 2700) / temp_range
            temp_normalized = max(0, min(1, temp_normalized))
            
            cool_white = int(white_value * temp_normalized)
            warm_white = int(white_value * (1 - temp_normalized))
            return (cool_white, warm_white)
        
        else:
            # Unknown type, return single white
            return (white_value,)
    
    @staticmethod
    def _get_zero_white_channels(led_type: str) -> Tuple[int, ...]:
        """Return tuple of zeros for white channels"""
        channel_counts = {
            'RGB': 0,
            'RGBW': 1,
            'RGBAW': 2,
            'RGBWW': 2,
            'RGBCW': 2,
            'RGBCWW': 3
        }
        count = channel_counts.get(led_type, 0)
        return tuple([0] * count)
```

### Universe Calculator

```python
# universe_calculator.py

class UniverseCalculator:
    """Calculate universe spans and channel allocations"""
    
    DMX_CHANNELS_PER_UNIVERSE = 512
    DMX_USABLE_CHANNELS = 510  # 512 - 2 (ArtNet header uses 2 channels)
    
    @staticmethod
    def calculate_universe_span(
        num_pixels: int,
        channels_per_pixel: int,
        start_universe: int
    ) -> Tuple[int, int, int]:
        """
        Calculate universe span for an object.
        
        Args:
            num_pixels: Number of LED pixels
            channels_per_pixel: Channels per pixel (3 for RGB, 4 for RGBW, etc.)
            start_universe: Starting universe number
        
        Returns:
            Tuple of (end_universe, pixels_per_universe, total_channels)
        """
        # Calculate max pixels per universe
        pixels_per_universe = UniverseCalculator.DMX_USABLE_CHANNELS // channels_per_pixel
        
        # Calculate total channels needed
        total_channels = num_pixels * channels_per_pixel
        
        # Calculate number of universes needed
        universes_needed = (total_channels + UniverseCalculator.DMX_USABLE_CHANNELS - 1) // UniverseCalculator.DMX_USABLE_CHANNELS
        
        # Calculate end universe
        end_universe = start_universe + universes_needed - 1
        
        return (end_universe, pixels_per_universe, total_channels)
    
    @staticmethod
    def get_max_pixels_per_universe(channels_per_pixel: int) -> int:
        """
        Get maximum pixels that fit in one universe.
        
        Examples:
            RGB (3 channels): 510 / 3 = 170 pixels
            RGBW (4 channels): 510 / 4 = 127 pixels (127 * 4 = 508)
            RGBAW (5 channels): 510 / 5 = 102 pixels (102 * 5 = 510)
            RGBWW (5 channels): 510 / 5 = 102 pixels
            RGBCWW (6 channels): 510 / 6 = 85 pixels (85 * 6 = 510)
        """
        return UniverseCalculator.DMX_USABLE_CHANNELS // channels_per_pixel
    
    @staticmethod
    def calculate_channel_map(
        num_pixels: int,
        channels_per_pixel: int,
        start_universe: int
    ) -> List[Dict]:
        """
        Create detailed channel mapping for each pixel.
        
        Returns:
            List of dicts with pixel-to-universe-channel mapping:
            [
                {
                    'pixel_id': 0,
                    'universe': 1,
                    'start_channel': 1,
                    'end_channel': 3,
                    'channels': [1, 2, 3]
                },
                ...
            ]
        """
        pixels_per_universe = UniverseCalculator.get_max_pixels_per_universe(channels_per_pixel)
        channel_map = []
        
        for pixel_id in range(num_pixels):
            # Calculate which universe this pixel belongs to
            universe_offset = pixel_id // pixels_per_universe
            universe = start_universe + universe_offset
            
            # Calculate channel within universe
            pixel_in_universe = pixel_id % pixels_per_universe
            start_channel = pixel_in_universe * channels_per_pixel + 1  # DMX channels are 1-indexed
            end_channel = start_channel + channels_per_pixel - 1
            
            channel_map.append({
                'pixel_id': pixel_id,
                'universe': universe,
                'start_channel': start_channel,
                'end_channel': end_channel,
                'channels': list(range(start_channel, end_channel + 1))
            })
        
        return channel_map
```

### RGB Format Mapper

```python
# channel_order_mapper.py

class ChannelOrderMapper:
    """
    Map pixel colors to different channel orders, including white channels.
    Replaces and extends the old RGBFormatMapper.
    """
    
    # Extended format maps for RGB + White channels
    FORMAT_MAPS = {
        # 3-channel (RGB)
        'RGB': [0, 1, 2],
        'RBG': [0, 2, 1],
        'GRB': [1, 0, 2],
        'GBR': [1, 2, 0],
        'BRG': [2, 0, 1],
        'BGR': [2, 1, 0],
        
        # 4-channel (RGBW)
        'RGBW': [0, 1, 2, 3],
        'RBGW': [0, 2, 1, 3],
        'GRBW': [1, 0, 2, 3],
        'GBRW': [1, 2, 0, 3],
        'BRGW': [2, 0, 1, 3],
        'BGRW': [2, 1, 0, 3],
        'WRGB': [3, 0, 1, 2],
        'WGBR': [3, 1, 2, 0],
        
        # 5-channel (RGBAW - Amber, White)
        'RGBAW': [0, 1, 2, 3, 4],
        'RGBWA': [0, 1, 2, 4, 3],
        'GRBAW': [1, 0, 2, 3, 4],
        
        # 5-channel (RGBWW - Warm White, Cool White)
        'RGBWW': [0, 1, 2, 3, 4],      # RGB + WarmWhite + CoolWhite
        'RGBCW': [0, 1, 2, 4, 3],       # RGB + CoolWhite + WarmWhite
        'GRBWW': [1, 0, 2, 3, 4],
        
        # 6-channel (RGBCWW - Cool White, Warm White)
        'RGBCWW': [0, 1, 2, 3, 4, 5],
        'RGBWWC': [0, 1, 2, 4, 5, 3],
    }
    
    @staticmethod
    def map_channels(
        pixels: List[Tuple[int, ...]],
        channel_order: str
    ) -> List[Tuple[int, ...]]:
        """
        Remap channels based on channel order string.
        
        Args:
            pixels: List of color tuples (can be 3, 4, 5, or 6 channels)
            channel_order: Channel order string (e.g., 'RGBW', 'GRBW', 'RGBCWW')
        
        Returns:
            Remapped pixel list
        
        Example:
            Input: [(255, 0, 0, 128)] with order 'GRBW'
            Output: [(0, 255, 0, 128)]  # G and R swapped
        """
        if channel_order not in ChannelOrderMapper.FORMAT_MAPS:
            # Unknown format, return unchanged
            return pixels
        
        mapping = ChannelOrderMapper.FORMAT_MAPS[channel_order]
        remapped = []
        
        for pixel in pixels:
            # Validate pixel has correct number of channels
            if len(pixel) != len(mapping):
                # Mismatch, skip remapping
                remapped.append(pixel)
                continue
            
            # Remap channels
            remapped_pixel = tuple(pixel[i] for i in mapping)
            remapped.append(remapped_pixel)
        
        return remapped
    
    @staticmethod
    def get_supported_orders_for_type(led_type: str) -> List[str]:
        """
        Get list of supported channel orders for a given LED type.
        
        Args:
            led_type: 'RGB', 'RGBW', 'RGBAW', 'RGBWW', 'RGBCWW'
        
        Returns:
            List of valid channel order strings
        """
        type_to_channels = {
            'RGB': 3,
            'RGBW': 4,
            'RGBAW': 5,
            'RGBWW': 5,
            'RGBCW': 5,
            'RGBCWW': 6
        }
        
        expected_channels = type_to_channels.get(led_type, 3)
        
        # Filter formats by channel count
        return [
            fmt for fmt, mapping in ChannelOrderMapper.FORMAT_MAPS.items()
            if len(mapping) == expected_channels
        ]
```

---

## 🔌 REST API Endpoints

### Object Management

```python
# api_artnet.py

from fastapi import APIRouter, HTTPException
from typing import List

router = APIRouter(prefix="/api/artnet")

# ==================== OBJECTS ====================

@router.get("/objects")
async def get_objects() -> List[dict]:
    """Get all ArtNet objects"""
    return [obj.to_dict() for obj in output_manager.objects.values()]

@router.get("/objects/{object_id}")
async def get_object(object_id: str) -> dict:
    """Get single ArtNet object by ID"""
    obj = output_manager.objects.get(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    return obj.to_dict()

@router.post("/objects")
async def create_object(data: dict) -> dict:
    """Create new ArtNet object"""
    obj = ArtNetObject.from_dict(data)
    output_manager.register_object(obj)
    session_state.save_artnet_config(output_manager)
    return obj.to_dict()

@router.put("/objects/{object_id}")
async def update_object(object_id: str, data: dict) -> dict:
    """Update existing ArtNet object"""
    if object_id not in output_manager.objects:
        raise HTTPException(status_code=404, detail="Object not found")
    
    obj = ArtNetObject.from_dict(data)
    output_manager.register_object(obj)
    session_state.save_artnet_config(output_manager)
    return obj.to_dict()

@router.delete("/objects/{object_id}")
async def delete_object(object_id: str):
    """Delete ArtNet object"""
    if object_id not in output_manager.objects:
        raise HTTPException(status_code=404, detail="Object not found")
    
    del output_manager.objects[object_id]
    session_state.save_artnet_config(output_manager)
    return {"status": "deleted"}

@router.put("/objects/{object_id}/points")
async def update_object_points(object_id: str, points: List[dict]) -> dict:
    """Update object points (for canvas manipulation)"""
    obj = output_manager.objects.get(object_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Object not found")
    
    obj.points = [ArtNetPoint(**p) for p in points]
    session_state.save_artnet_config(output_manager)
    return obj.to_dict()

# ==================== OUTPUTS ====================

@router.get("/outputs")
async def get_outputs() -> List[dict]:
    """Get all ArtNet outputs"""
    return [out.to_dict() for out in output_manager.outputs.values()]

@router.get("/outputs/{output_id}")
async def get_output(output_id: str) -> dict:
    """Get single ArtNet output by ID"""
    output = output_manager.outputs.get(output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")
    return output.to_dict()

@router.post("/outputs")
async def create_output(data: dict) -> dict:
    """Create new ArtNet output"""
    output = ArtNetOutput.from_dict(data)
    output_manager.register_output(output)
    session_state.save_artnet_config(output_manager)
    return output.to_dict()

@router.put("/outputs/{output_id}")
async def update_output(output_id: str, data: dict) -> dict:
    """Update existing ArtNet output"""
    if output_id not in output_manager.outputs:
        raise HTTPException(status_code=404, detail="Output not found")
    
    output = ArtNetOutput.from_dict(data)
    output_manager.register_output(output)
    session_state.save_artnet_config(output_manager)
    return output.to_dict()

@router.delete("/outputs/{output_id}")
async def delete_output(output_id: str):
    """Delete ArtNet output"""
    if output_id not in output_manager.outputs:
        raise HTTPException(status_code=404, detail="Output not found")
    
    del output_manager.outputs[output_id]
    session_state.save_artnet_config(output_manager)
    return {"status": "deleted"}

@router.post("/outputs/{output_id}/test")
async def test_output(output_id: str):
    """Send test pattern to output"""
    output = output_manager.outputs.get(output_id)
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")
    
    # Send rainbow test pattern
    test_data = generate_test_pattern(output)
    output_manager.artnet_sender.send(
        target_ip=output.target_ip,
        start_universe=output.start_universe,
        dmx_data=test_data,
        subnet=output.subnet
    )
    return {"status": "test_sent"}

# ==================== CONFIGURATION ====================

@router.get("/config")
async def get_config() -> dict:
    """Get complete ArtNet configuration"""
    return {
        'objects': [obj.to_dict() for obj in output_manager.objects.values()],
        'outputs': [out.to_dict() for out in output_manager.outputs.values()]
    }

@router.post("/config/import")
async def import_config(data: dict):
    """Import complete ArtNet configuration"""
    # Clear existing
    output_manager.objects.clear()
    output_manager.outputs.clear()
    
    # Load objects
    for obj_data in data.get('objects', []):
        obj = ArtNetObject.from_dict(obj_data)
        output_manager.register_object(obj)
    
    # Load outputs
    for out_data in data.get('outputs', []):
        output = ArtNetOutput.from_dict(out_data)
        output_manager.register_output(output)
    
    session_state.save_artnet_config(output_manager)
    return {"status": "imported"}

@router.post("/config/export")
async def export_config() -> dict:
    """Export complete ArtNet configuration"""
    return {
        'objects': [obj.to_dict() for obj in output_manager.objects.values()],
        'outputs': [out.to_dict() for out in output_manager.outputs.values()]
    }
```

---

## 🔄 Player Integration

### Modify player_core.py

```python
# player_core.py

class PlayerCore:
    def __init__(self, ...):
        # ... existing initialization ...
        
        # Initialize ArtNet output manager
        self.artnet_output_manager = ArtNetOutputManager(
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height
        )
        
        # Load ArtNet config from session state
        self._load_artnet_config()
    
    def _load_artnet_config(self):
        """Load ArtNet objects and outputs from session state"""
        config = session_state.get_artnet_config()
        
        for obj_data in config.get('objects', []):
            obj = ArtNetObject.from_dict(obj_data)
            self.artnet_output_manager.register_object(obj)
        
        for out_data in config.get('outputs', []):
            output = ArtNetOutput.from_dict(out_data)
            self.artnet_output_manager.register_output(output)
    
    def update(self, dt):
        """Main update loop - called every frame"""
        # ... existing frame processing ...
        
        # Get processed frame
        processed_frame = self.get_output_frame()
        
        # Get individual layer frames for input routing
        layer_frames = {
            'player': processed_frame,  # Composite (all layers)
            'layer1': self.layer_manager.get_layer_frame(1) if self.layer_manager else None,
            'layer2': self.layer_manager.get_layer_frame(2) if self.layer_manager else None,
            # ... up to layer10
        }
        
        # Filter out None values
        layer_frames = {k: v for k, v in layer_frames.items() if v is not None}
        
        # Send to ArtNet outputs
        self.artnet_output_manager.process_frame(
            frame=processed_frame,
            layer_frames=layer_frames
        )
```

---

## 💾 Session State Integration

### Modify session_state.py

```python
# session_state.py

class SessionState:
    def __init__(self):
        # ... existing fields ...
        self.artnet_config = {
            'objects': [],
            'outputs': []
        }
    
    def save_artnet_config(self, output_manager: ArtNetOutputManager):
        """Save ArtNet configuration to session state"""
        self.artnet_config = {
            'objects': [obj.to_dict() for obj in output_manager.objects.values()],
            'outputs': [out.to_dict() for out in output_manager.outputs.values()]
        }
        self.save()
    
    def get_artnet_config(self) -> dict:
        """Get ArtNet configuration from session state"""
        return self.artnet_config
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        data = super().to_dict()
        data['artnet_config'] = self.artnet_config
        return data
    
    @staticmethod
    def from_dict(data: dict) -> 'SessionState':
        """Deserialize from JSON"""
        state = SessionState()
        # ... existing deserialization ...
        state.artnet_config = data.get('artnet_config', {'objects': [], 'outputs': []})
        return state
```

---

## 📋 Implementation Phases

### Phase 1: Data Models & Basic Infrastructure (Week 1)
**Deliverables:**
- ✅ Create `artnet_routing/` module structure
- ✅ Implement `ArtNetObject` and `ArtNetOutput` data models
- ✅ Implement basic `ArtNetOutputManager` skeleton
- ✅ Add session state integration
- ✅ Create API endpoints for CRUD operations

**Testing:**
- Can create/read/update/delete objects via API
- Can create/read/update/delete outputs via API
- Configuration persists across restarts
- Frontend can connect to backend APIs

### Phase 2: Pixel Sampling & Basic Routing (Week 2)
**Deliverables:**
- ✅ Implement `PixelSampler` for coordinate-based sampling
- ✅ Implement basic `_build_dmx_data()` method
- ✅ Integrate with player_core.py
- ✅ Test single object → single output routing

**Testing:**
- Player frame pixels correctly sampled at object points
- DMX data generated correctly (3 bytes per pixel)
- Test with single LED strip (e.g., 50 LEDs)
- Visual verification: moving patterns in player should reflect on LEDs

### Phase 3: Color Correction (Week 3)
**Deliverables:**
- ✅ Implement `ColorCorrector` class
- ✅ Add per-object color correction pipeline
- ✅ Add per-output color correction pipeline
- ✅ Test brightness, contrast, RGB adjustments

**Testing:**
- Brightness slider changes LED brightness
- Contrast adjustment works correctly
- RGB channel adjustments (red +50, green -50, etc.)
- Verify per-object corrections don't affect other objects
- Verify per-output corrections apply to all assigned objects

### Phase 4: RGB Format Mapping (Week 3)
**Deliverables:**
- ✅ Implement `RGBFormatMapper` class
- ✅ Test all 6 format permutations (RGB, RBG, GRB, GBR, BRG, BGR)

**Testing:**
- Test each format with known color (e.g., pure red)
- Verify LED strips light up correctly based on wiring
- Test mixed formats (Object 1: RGB, Object 2: GRB)

### Phase 5: Master-Slave Linking (Week 4)
**Deliverables:**
- ✅ Implement `MasterSlaveResolver` class
- ✅ Add link validation (same type, same point count)
- ✅ Implement color inheritance logic
- ✅ Handle edge cases (missing master, circular links)

**Testing:**
- Two identical objects (50 LEDs each)
- Link Object B as slave to Object A
- Verify Object B shows same colors as Object A
- Test with different point counts (interpolation)
- Test multiple slaves to one master

### Phase 6: Layer Input Routing (Week 4)
**Deliverables:**
- ✅ Modify player to provide layer frames
- ✅ Implement layer frame caching in output manager
- ✅ Add input layer selection per object
- ✅ Test routing different objects to different layers

**Testing:**
- Object 1 assigned to Player (Layer 0)
- Object 2 assigned to Layer 1
- Verify Object 2 shows only Layer 1 content
- Test with layer effects enabled
- Test with 10 layers active

### Phase 7: Timing & Performance (Week 5)
**Deliverables:**
- ✅ Implement FPS throttling per output
- ✅ Implement delay buffer system
- ✅ Optimize pixel sampling performance
- ✅ Add performance monitoring

**Testing:**
- Set Output 1 to 30 FPS, Output 2 to 60 FPS
- Verify frame rates are correct
- Test delay buffer (50ms, 100ms, 500ms)
- Measure CPU usage with 10 outputs active
- Optimize to <5% CPU per output

### Phase 8: Frontend Integration (Week 6)
**Deliverables:**
- ✅ Replace prototype mock data with real API calls
- ✅ Implement WebSocket for real-time color preview
- ✅ Add error handling and user feedback
- ✅ Test all frontend features with live backend

**Testing:**
- Create object in frontend → appears in backend
- Move object on canvas → positions update in backend
- Change color correction → LEDs update in real-time
- Delete output → stops sending ArtNet packets
- Import/export configuration works

---

## 🧪 Testing Strategy

### Unit Tests
```python
# tests/test_color_corrector.py
def test_brightness_adjustment():
    corrector = ColorCorrector()
    pixels = [(128, 128, 128)]
    result = corrector.apply(pixels, brightness=50)
    assert result == [(178, 178, 178)]

def test_rgb_format_mapping():
    mapper = RGBFormatMapper()
    pixels = [(255, 0, 0)]  # Red
    result = mapper.map_format(pixels, format='GRB')
    assert result == [(0, 255, 0)]  # Green position gets red value
```

### Integration Tests
```python
# tests/test_artnet_integration.py
def test_full_pipeline():
    # Setup
    manager = ArtNetOutputManager(1920, 1080)
    obj = create_test_object(num_points=50)
    output = create_test_output()
    manager.register_object(obj)
    manager.register_output(output)
    
    # Generate test frame
    frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    frame[:, :] = [255, 0, 0]  # Red
    
    # Process
    manager.process_frame(frame, {'player': frame})
    
    # Verify DMX data sent
    assert len(manager.artnet_sender.sent_packets) > 0
    assert manager.artnet_sender.sent_packets[0]['target_ip'] == output.target_ip
```

### Performance Tests
```python
# tests/test_performance.py
def test_10_outputs_performance():
    """Verify <5% CPU with 10 active outputs"""
    manager = setup_10_outputs()
    
    start = time.time()
    for _ in range(100):  # 100 frames
        manager.process_frame(test_frame, layer_frames)
    
    elapsed = time.time() - start
    fps = 100 / elapsed
    assert fps >= 30  # Should maintain 30 FPS minimum
```

---

## 📊 Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| CPU Usage | <5% per output | At 30 FPS with 500 LEDs |
| Frame Processing Time | <10ms | Total pipeline time |
| Memory Usage | <100MB | For 10 outputs with 1000 LEDs each |
| Network Latency | <2ms | ArtNet packet send time |
| FPS Stability | ±2 FPS | Maintain target FPS consistently |

---

## 🚀 Deployment Checklist

### Backend
- [ ] All modules implemented and tested
- [ ] API endpoints functional
- [ ] Session state persistence working
- [ ] Player integration complete
- [ ] Performance targets met

### Frontend
- [ ] Mock data replaced with API calls
- [ ] Real-time updates working
- [ ] Error handling implemented
- [ ] User documentation complete

### Testing
- [ ] Unit tests passing (>90% coverage)
- [ ] Integration tests passing
- [ ] Performance tests passing
- [ ] Manual QA completed

### Documentation
- [ ] API documentation complete
- [ ] Backend architecture documented
- [ ] User manual updated
- [ ] Troubleshooting guide created

---

## ⚠️ Configuration Migration

### Obsolete config.json Settings

The following sections in `config.json` become **obsolete** when the new ArtNet output routing system is implemented. All settings move to per-object and per-output configuration in `session_state.json`:

#### 1. `channels` Section - **REMOVE ENTIRELY**
```json
// OBSOLETE - Remove this entire section
"channels": {
  "channels_per_point": 3,      // ❌ Now per-object (always 3 for RGB)
  "max_per_universe": 510        // ❌ Fixed DMX standard (not configurable)
}
```

**Migration:**
- `channels_per_point`: Always 3 (RGB), defined in code
- `max_per_universe`: Fixed at 510 (DMX512 standard minus 2 header bytes)

#### 2. `artnet` Section - **REMOVE MOST SETTINGS**
```json
// OBSOLETE - Most of these settings move to per-output configuration
"artnet": {
  "target_ip": "127.0.0.1",           // ❌ → per-output `targetIP`
  "start_universe": 0,                // ❌ → per-output `startUniverse`
  "fps": 30,                          // ❌ → per-output `fps`
  "broadcast": true,                  // ⚠️  Keep (global broadcast mode)
  "dmx_control_universe": 100,        // ❌ Legacy, unused
  "dmx_listen_ip": "0.0.0.0",        // ⚠️  Keep (DMX input feature, separate)
  "dmx_listen_port": 6454,           // ⚠️  Keep (DMX input feature, separate)
  "even_packet": true,                // ❌ Legacy, unused
  "bit_depth": 8,                     // ❌ Always 8-bit (standard)
  "delta_encoding": { ... },          // ❌ Remove (optimization not needed)
  "universe_configs": {               // ❌ → per-object `rgbFormat`
    "0": "GRB",
    "default": "RGB"
  }
}
```

**What to Keep (Optional):**
```json
"artnet": {
  "broadcast": true,           // Global: Use broadcast vs unicast
  "dmx_listen_ip": "0.0.0.0", // DMX input (separate feature)
  "dmx_listen_port": 6454      // DMX input (separate feature)
}
```

**Migration:**
- `target_ip` → ArtNetOutput.target_ip (per output)
- `start_universe` → ArtNetOutput.start_universe (per output)
- `fps` → ArtNetOutput.fps (per output, default 30)
- `universe_configs["0"]` → ArtNetObject.rgb_format (per object)
- `bit_depth`: Hardcoded to 8 (standard RGB)
- `delta_encoding`: Remove (not needed with efficient sampling)

#### 3. `cache` Section - **REMOVE ENTIRELY**
```json
// OBSOLETE - Remove this entire section
"cache": {
  "compression": "msgpack",   // ❌ Not used by ArtNet routing
  "enabled": true,            // ❌ Not used by ArtNet routing
  "max_size_mb": 1024         // ❌ Not used by ArtNet routing
}
```

**Reason:** Cache was designed for old points-based system. New system samples pixels directly from player frame (no caching needed).

### New Configuration Structure

#### config.json (Minimal Global Settings)
```json
{
  "artnet": {
    "broadcast": true,           // Optional: Use broadcast mode
    "dmx_listen_ip": "0.0.0.0", // Optional: DMX input feature
    "dmx_listen_port": 6454      // Optional: DMX input feature
  }
}
```

#### session_state.json (Per-Output and Per-Object Config)
```json
{
  "artnet_config": {
    "objects": [
      {
        "id": "obj-1",
        "name": "LED Strip 1",
        "type": "line",
        "points": [...],
        "universeStart": 1,
        "universeEnd": 2,
        "delay": 0,
        "brightness": 0,
        "contrast": 0,
        "red": 0,
        "green": 0,
        "blue": 0,
        "rgbFormat": "GRB",        // Per-object RGB format
        "input": "player",
        "masterId": null
      }
    ],
    "outputs": [
      {
        "id": "output-1",
        "name": "Main Output",
        "targetIP": "192.168.1.10",  // Per-output IP
        "subnet": "255.255.255.0",
        "startUniverse": 1,           // Per-output universe
        "fps": 30,                    // Per-output FPS
        "delay": 0,
        "brightness": 0,
        "contrast": 0,
        "red": 0,
        "green": 0,
        "blue": 0,
        "assignedObjects": ["obj-1"],
        "active": true
      }
    ]
  }
}
```

### Migration Script

```python
# scripts/migrate_artnet_config.py

def migrate_config():
    """Migrate old config.json artnet settings to new session_state.json"""
    
    # Load old config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # Create default output from old settings
    old_artnet = config.get('artnet', {})
    old_channels = config.get('channels', {})
    
    default_output = {
        'id': 'output-legacy',
        'name': 'Legacy Output',
        'targetIP': old_artnet.get('target_ip', '127.0.0.1'),
        'subnet': '255.255.255.0',
        'startUniverse': old_artnet.get('start_universe', 0),
        'fps': old_artnet.get('fps', 30),
        'delay': 0,
        'brightness': 0,
        'contrast': 0,
        'red': 0,
        'green': 0,
        'blue': 0,
        'assignedObjects': [],
        'active': True
    }
    
    # Get default RGB format from universe_configs
    universe_configs = old_artnet.get('universe_configs', {})
    default_rgb_format = universe_configs.get('default', 'RGB')
    
    print("Migration complete!")
    print(f"Default output created: {default_output['targetIP']}")
    print(f"Default RGB format: {default_rgb_format}")
    print("\nOBSOLETE SETTINGS - Remove from config.json:")
    print("  - channels (entire section)")
    print("  - cache (entire section)")
    print("  - artnet.target_ip")
    print("  - artnet.start_universe")
    print("  - artnet.fps")
    print("  - artnet.universe_configs")
    print("  - artnet.bit_depth")
    print("  - artnet.delta_encoding")
    print("  - artnet.dmx_control_universe")
    print("  - artnet.even_packet")
```

### Recommended Clean config.json

```json
{
  "api": { ... },
  "app": { ... },
  "artnet": {
    "broadcast": true,
    "dmx_listen_ip": "0.0.0.0",
    "dmx_listen_port": 6454,
    "_comment": "DMX input feature (separate from ArtNet output routing)"
  },
  "effects": { ... },
  "frontend": { ... },
  "websocket": { ... },
  "performance": { ... },
  "paths": { ... },
  "video": { ... },
  "outputs": { ... }
}
```

**Note:** Remove these sections entirely:
- ❌ `channels`
- ❌ `cache`
- ❌ Most of `artnet` (keep only DMX input settings)

---

## 🔮 Future Enhancements

### v2.0 Features
- **3D Object Positioning**: Add Z-axis for depth mapping
- **Object Groups**: Bulk operations on multiple objects
- **Animation Curves**: Per-object animation paths
- **Advanced Linking**: Many-to-many master-slave relationships
- **Fixture Profiles**: Pre-defined object templates (moving heads, PAR cans)
- **DMX Input**: Control objects via external DMX controllers
- **MIDI Mapping**: Map MIDI controls to color correction parameters
- **Artpoll Discovery**: Auto-discover ArtNet devices on network

### v3.0 Features
- **Timeline Sequencing**: Record and playback object property changes
- **DMX 512 Support**: Beyond ArtNet (sACN, DMX512 USB)
- **Pixel Mapping Plugins**: Custom sampling algorithms
- **GPU Acceleration**: CUDA/OpenCL for massive LED counts (10,000+)
- **Distributed Rendering**: Multi-PC ArtNet clusters

---

## 📚 References

- **ArtNet Protocol Spec**: https://art-net.org.uk/
- **DMX512 Standard**: https://www.rdmprotocol.org/
- **LED Strip Wiring**: https://learn.adafruit.com/led-strip-guide
- **Color Correction Theory**: https://docs.opencv.org/4.x/d3/dc1/tutorial_basic_linear_transform.html

---

**Document Version:** 1.0  
**Last Updated:** February 4, 2026  
**Status:** Planning Phase - Ready for Implementation
