# 🎯 ArtNet Output Routing - Backend Implementation Plan

**Date:** 2026-02-11  
**Status:** Planning Phase  
**Context:** Canvas Editor now saves shapes to session state, need to implement ArtNet output routing

---

## 📋 Executive Summary

The **Canvas Editor** now auto-saves shapes (parameters only) to `session_state.editor.shapes[]`. We need to implement the **ArtNet Output Routing** system that:

1. **Loads shapes from session state** (editor.shapes[])
2. **Calculates LED coordinates** from shape parameters (same logic as editor)
3. **Creates ArtNet Objects** with full coordinate arrays
4. **Manages ArtNet Outputs** (network targets with universe assignments)
5. **Routes objects to outputs** (many-to-many mapping)
6. **Renders video frames to LED coordinates** using OutputManager/SliceManager pattern

### Frontend Integration Strategy

**Reuse existing `output-settings.html`** with dual-mode support:
- **Mode Switcher:** Toggle between "Video Output" and "ArtNet Output" at top
- **Left Panel:** Outputs (ArtNet endpoints), Canvas (ArtNet resolution), Tools (reserved)
- **Right Panel:** Objects (LED properties, white detection, color correction)
- **Center Canvas:** LED coordinate preview with realtime pixel sampling

This approach maintains UI consistency and reuses proven patterns from video routing.

---

## 🏗️ Current Architecture Status

### ✅ What We Already Have

#### 1. **Editor Shape Storage**
- **Location:** `session_state.editor.shapes[]`
- **Content:** Shape parameters (type, position, size, rotation, rows/cols, etc.)
- **Saved by:** `frontend/js/editor.js` auto-save system
- **Format:** Compact JSON (8-15 properties per shape)

**Example:**
```json
{
  "editor": {
    "shapes": [
      {
        "id": "shape-1",
        "type": "matrix",
        "x": 500,
        "y": 400,
        "size": 200,
        "rows": 8,
        "cols": 10,
        "pattern": "zigzag-left",
        "pointCount": 80,
        "rotation": 0,
        "scaleX": 1,
        "scaleY": 1,
        "color": "cyan"
      }
    ],
    "canvas": {
      "width": 1920,
      "height": 1080
    }
  }
}
```

#### 2. **Output Routing Infrastructure**
- **OutputManager:** `src/modules/outputs/output_manager.py` (manages video outputs + slices)
- **SliceManager:** `src/modules/outputs/slice_manager.py` (canvas regions with transforms)
- **Session State Integration:** `save_output_state()`, `get_output_state()` methods exist
- **API Endpoints:** `/api/outputs/state` (GET/POST) implemented

#### 3. **ArtNet Infrastructure**
- **ArtNetManager:** `src/modules/artnet_manager.py` (sends DMX data to network)
- **Delta Encoding:** Implemented with threshold and full-frame intervals
- **RGB Channel Mapping:** Supports RGB, GRB, BGR, etc.
- **Multi-Universe Support:** Auto-calculates universe boundaries

#### 4. **Points Calculation**
- **Frontend Logic:** `frontend/js/editor.js` has `getShapePoints()`, `getMatrixPoints()`, etc.
- **Backend Logic:** Need to implement Python equivalents for LED coordinate generation

### ❌ What We Need to Implement

#### 1. **ArtNet Objects System**
- **Data Model:** `ArtNetObject` class with LED coordinates
- **Calculation Engine:** Generate LED coordinates from shape parameters
- **LED Type Support:** RGB, RGBW, RGBAW, RGBWW, RGBCW, RGBCWW
- **White Channel Logic:** Detection modes (luminance, average, minimum)
- **Channel Order:** Flexible mapping (RGB, GRB, RGBW, GRBW, etc.)
- **Universe Assignment:** Auto-calculate universe ranges based on LED count + type
- **Master-Slave Linking:** Synchronize colors across objects

#### 2. **ArtNet Outputs System**
- **Data Model:** `ArtNetOutput` class (network target + configuration)
- **Properties:** IP, subnet, start universe, FPS, delay
- **Color Correction:** Per-output brightness/contrast/RGB adjustment
- **Object Assignment:** Many objects → one output, many-to-many routing
- **Delta Encoding:** Per-output delta settings

#### 3. **Session State Integration**
- **Storage Location:** `session_state.artnet_routing`
- **Structure:** Separate from editor (objects + outputs + assignments)
- **Auto-Save:** Similar to output-settings (debounced, async)
- **Restore:** Load on page reload

#### 4. **REST API Endpoints**
- **Objects:** CRUD operations for ArtNet objects
- **Outputs:** CRUD operations for ArtNet outputs
- **Assignments:** Assign/remove objects from outputs
- **Rendering:** Frame rendering pipeline (video → LED coordinates)

---

## 🔧 Data Models

### 1. ArtNet Object

**Purpose:** Represents LED fixture with spatial positioning and rendering properties.

**Data Model:**

```python
# src/modules/artnet_routing/artnet_object.py

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import json

@dataclass
class ArtNetPoint:
    """Single LED pixel coordinate"""
    id: int           # Sequential ID (1, 2, 3, ...)
    x: float          # X coordinate on canvas
    y: float          # Y coordinate on canvas

@dataclass
class ArtNetObject:
    """LED fixture with calculated coordinates"""
    
    # Identity
    id: str                          # UUID (e.g., "obj-123")
    name: str                        # Display name (e.g., "Matrix Left")
    source_shape_id: str             # Reference to editor.shapes[n].id
    
    # Geometry (calculated from shape parameters)
    type: str                        # 'matrix', 'circle', 'line', 'star', etc.
    points: List[ArtNetPoint]        # Calculated LED coordinates
    
    # LED Configuration
    led_type: str = 'RGB'            # 'RGB', 'RGBW', 'RGBAW', 'RGBWW', 'RGBCW', 'RGBCWW'
    channels_per_pixel: int = 3      # Auto-calculated: RGB=3, RGBW=4, RGBAW=5, RGBCWW=6
    channel_order: str = 'RGB'       # Channel mapping: 'RGB', 'GRB', 'RGBW', 'GRBW', etc.
    
    # Network Assignment (auto-calculated)
    universe_start: int = 1          # Starting ArtNet universe
    universe_end: int = 1            # Ending ArtNet universe
    
    # White Channel Configuration (for RGBW+)
    white_detection_enabled: bool = True
    white_detection_mode: str = 'luminance'  # 'average', 'minimum', 'luminance'
    white_threshold: int = 200               # 0-255
    white_behavior: str = 'hybrid'           # 'replace', 'additive', 'hybrid'
    color_temperature: int = 4500            # 2700-6500K (for RGBWW/RGBCW)
    
    # Color Correction (per-object)
    brightness: int = 0              # -255 to 255
    contrast: int = 0                # -255 to 255
    red: int = 0                     # -255 to 255
    green: int = 0                   # -255 to 255
    blue: int = 0                    # -255 to 255
    
    # Timing
    delay: int = 0                   # Delay in milliseconds
    
    # Layer Routing
    input_layer: str = 'player'      # 'player', 'layer1', ..., 'layer10'
    
    # Master-Slave Linking
    master_id: Optional[str] = None  # ID of master object (if this is slave)
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'sourceShapeId': self.source_shape_id,
            'type': self.type,
            'points': [{'id': p.id, 'x': p.x, 'y': p.y} for p in self.points],
            'ledType': self.led_type,
            'channelsPerPixel': self.channels_per_pixel,
            'channelOrder': self.channel_order,
            'universeStart': self.universe_start,
            'universeEnd': self.universe_end,
            'whiteDetectionEnabled': self.white_detection_enabled,
            'whiteDetectionMode': self.white_detection_mode,
            'whiteThreshold': self.white_threshold,
            'whiteBehavior': self.white_behavior,
            'colorTemperature': self.color_temperature,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'delay': self.delay,
            'inputLayer': self.input_layer,
            'masterId': self.master_id
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetObject':
        """Deserialize from JSON"""
        points = [ArtNetPoint(**p) for p in data['points']]
        return ArtNetObject(
            id=data['id'],
            name=data['name'],
            source_shape_id=data['sourceShapeId'],
            type=data['type'],
            points=points,
            led_type=data.get('ledType', 'RGB'),
            channels_per_pixel=data.get('channelsPerPixel', 3),
            channel_order=data.get('channelOrder', 'RGB'),
            universe_start=data.get('universeStart', 1),
            universe_end=data.get('universeEnd', 1),
            white_detection_enabled=data.get('whiteDetectionEnabled', True),
            white_detection_mode=data.get('whiteDetectionMode', 'luminance'),
            white_threshold=data.get('whiteThreshold', 200),
            white_behavior=data.get('whiteBehavior', 'hybrid'),
            color_temperature=data.get('colorTemperature', 4500),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            delay=data.get('delay', 0),
            input_layer=data.get('inputLayer', 'player'),
            master_id=data.get('masterId')
        )
    
    def get_max_pixels_per_universe(self) -> int:
        """Calculate maximum pixels per universe based on LED type"""
        return 510 // self.channels_per_pixel
    
    def calculate_universe_range(self) -> Tuple[int, int]:
        """Calculate universe range needed for this object"""
        total_channels = len(self.points) * self.channels_per_pixel
        universes_needed = (total_channels + 509) // 510  # Ceiling division
        return (self.universe_start, self.universe_start + universes_needed - 1)
```

### 2. ArtNet Output

**Purpose:** Network target with routing configuration.

**Data Model:**

```python
# src/modules/artnet_routing/artnet_output.py

@dataclass
class ArtNetOutput:
    """ArtNet network output target"""
    
    # Identity
    id: str                    # UUID (e.g., "out-456")
    name: str                  # Display name (e.g., "Main LED Wall")
    
    # Network Configuration
    target_ip: str             # Target IP address (e.g., "192.168.1.10")
    subnet: str                # Subnet mask (e.g., "255.255.255.0")
    start_universe: int        # Starting universe for this output
    
    # Protocol Settings
    fps: int = 30              # Frames per second
    delay: int = 0             # Delay in milliseconds
    active: bool = True        # Enable/disable output
    
    # Color Correction (applied to ALL objects on this output)
    brightness: int = 0        # -255 to 255
    contrast: int = 0          # -255 to 255
    red: int = 0               # -255 to 255
    green: int = 0             # -255 to 255
    blue: int = 0              # -255 to 255
    
    # Delta Encoding
    delta_enabled: bool = False
    delta_threshold: int = 8   # 0-255
    full_frame_interval: int = 30  # Frames
    
    # Object Assignments
    assigned_objects: List[str] = field(default_factory=list)  # List of object IDs
    
    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'targetIP': self.target_ip,
            'subnet': self.subnet,
            'startUniverse': self.start_universe,
            'fps': self.fps,
            'delay': self.delay,
            'active': self.active,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'deltaEnabled': self.delta_enabled,
            'deltaThreshold': self.delta_threshold,
            'fullFrameInterval': self.full_frame_interval,
            'assignedObjects': self.assigned_objects
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetOutput':
        return ArtNetOutput(
            id=data['id'],
            name=data['name'],
            target_ip=data['targetIP'],
            subnet=data['subnet'],
            start_universe=data['startUniverse'],
            fps=data.get('fps', 30),
            delay=data.get('delay', 0),
            active=data.get('active', True),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            delta_enabled=data.get('deltaEnabled', False),
            delta_threshold=data.get('deltaThreshold', 8),
            full_frame_interval=data.get('fullFrameInterval', 30),
            assigned_objects=data.get('assignedObjects', [])
        )
```

---

## 🎨 Point Generation Engine

**Purpose:** Convert editor shapes to LED coordinates (Python port of editor.js logic).

**Implementation:**

```python
# src/modules/artnet_routing/point_generator.py

import math
from typing import List, Tuple
from .artnet_object import ArtNetPoint

class PointGenerator:
    """Generate LED coordinates from shape parameters"""
    
    @staticmethod
    def generate_points(shape: dict) -> List[ArtNetPoint]:
        """
        Generate LED points from editor shape parameters
        
        Args:
            shape: Dictionary from editor.shapes[] (session state)
        
        Returns:
            List of ArtNetPoint with calculated coordinates
        """
        shape_type = shape['type']
        
        if shape_type == 'matrix':
            return PointGenerator._generate_matrix(shape)
        elif shape_type == 'circle':
            return PointGenerator._generate_circle(shape)
        elif shape_type == 'line':
            return PointGenerator._generate_line(shape)
        elif shape_type == 'star':
            return PointGenerator._generate_star(shape)
        elif shape_type == 'polygon':
            return PointGenerator._generate_polygon(shape)
        elif shape_type == 'freehand':
            return PointGenerator._generate_freehand(shape)
        elif shape_type == 'arc':
            return PointGenerator._generate_arc(shape)
        else:
            raise ValueError(f"Unknown shape type: {shape_type}")
    
    @staticmethod
    def _generate_matrix(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for matrix (grid) shape"""
        rows = shape.get('rows', 4)
        cols = shape.get('cols', 4)
        pattern = shape.get('pattern', 'zigzag-left')
        size = shape.get('size', 100)
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = shape.get('rotation', 0)
        scale_x = shape.get('scaleX', 1)
        scale_y = shape.get('scaleY', 1)
        row_spacing = shape.get('rowSpacing', 1.0)
        col_spacing = shape.get('colSpacing', 1.0)
        
        points = []
        point_id = 1
        
        # Calculate spacing
        x_spacing = (size * scale_x * col_spacing) / (cols - 1) if cols > 1 else 0
        y_spacing = (size * scale_y * row_spacing) / (rows - 1) if rows > 1 else 0
        
        # Generate grid based on pattern
        for row in range(rows):
            for col in range(cols):
                # Determine column order based on pattern
                if pattern == 'zigzag-left' and row % 2 == 1:
                    actual_col = cols - 1 - col  # Reverse even rows
                elif pattern == 'zigzag-right' and row % 2 == 0:
                    actual_col = cols - 1 - col  # Reverse odd rows
                else:
                    actual_col = col
                
                # Local coordinates (relative to center)
                local_x = (actual_col - (cols - 1) / 2) * x_spacing
                local_y = (row - (rows - 1) / 2) * y_spacing
                
                # Apply rotation
                if rotation != 0:
                    rad = math.radians(rotation)
                    cos_r = math.cos(rad)
                    sin_r = math.sin(rad)
                    rotated_x = local_x * cos_r - local_y * sin_r
                    rotated_y = local_x * sin_r + local_y * cos_r
                    local_x = rotated_x
                    local_y = rotated_y
                
                # World coordinates
                world_x = x_center + local_x
                world_y = y_center + local_y
                
                points.append(ArtNetPoint(id=point_id, x=world_x, y=world_y))
                point_id += 1
        
        return points
    
    @staticmethod
    def _generate_circle(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for circle shape"""
        point_count = shape.get('pointCount', 60)
        size = shape.get('size', 100)
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = shape.get('rotation', 0)
        scale_x = shape.get('scaleX', 1)
        scale_y = shape.get('scaleY', 1)
        
        points = []
        radius_x = size / 2 * scale_x
        radius_y = size / 2 * scale_y
        
        for i in range(point_count):
            angle = (2 * math.pi * i / point_count) + math.radians(rotation)
            local_x = radius_x * math.cos(angle)
            local_y = radius_y * math.sin(angle)
            
            world_x = x_center + local_x
            world_y = y_center + local_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_line(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for line shape"""
        point_count = shape.get('pointCount', 50)
        size = shape.get('size', 100)
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = shape.get('rotation', 0)
        scale_x = shape.get('scaleX', 1)
        
        points = []
        length = size * scale_x
        
        for i in range(point_count):
            t = i / (point_count - 1) if point_count > 1 else 0
            local_x = (t - 0.5) * length
            local_y = 0
            
            # Apply rotation
            if rotation != 0:
                rad = math.radians(rotation)
                cos_r = math.cos(rad)
                sin_r = math.sin(rad)
                rotated_x = local_x * cos_r - local_y * sin_r
                rotated_y = local_x * sin_r + local_y * cos_r
                local_x = rotated_x
                local_y = rotated_y
            
            world_x = x_center + local_x
            world_y = y_center + local_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    @staticmethod
    def _generate_star(shape: dict) -> List[ArtNetPoint]:
        """Generate LED points for star shape"""
        spikes = shape.get('spikes', 5)
        point_count = shape.get('pointCount', 50)
        size = shape.get('size', 100)
        x_center = shape.get('x', 0)
        y_center = shape.get('y', 0)
        rotation = shape.get('rotation', 0)
        scale_x = shape.get('scaleX', 1)
        scale_y = shape.get('scaleY', 1)
        inner_ratio = shape.get('innerRatio', 0.5)
        
        points = []
        outer_radius_x = size / 2 * scale_x
        outer_radius_y = size / 2 * scale_y
        inner_radius_x = outer_radius_x * inner_ratio
        inner_radius_y = outer_radius_y * inner_ratio
        
        angle_step = 2 * math.pi / (spikes * 2)
        
        for i in range(point_count):
            t = i / point_count
            angle_index = t * spikes * 2
            progress_in_segment = angle_index % 1
            segment_index = int(angle_index)
            
            is_outer = segment_index % 2 == 0
            
            if is_outer:
                radius_x = outer_radius_x
                radius_y = outer_radius_y
            else:
                radius_x = inner_radius_x
                radius_y = inner_radius_y
            
            angle = (segment_index * angle_step) + math.radians(rotation) - math.pi / 2
            
            local_x = radius_x * math.cos(angle)
            local_y = radius_y * math.sin(angle)
            
            world_x = x_center + local_x
            world_y = y_center + local_y
            
            points.append(ArtNetPoint(id=i + 1, x=world_x, y=world_y))
        
        return points
    
    # TODO: Implement _generate_polygon, _generate_freehand, _generate_arc
```

---

## 🔌 ArtNet Routing Manager

**Purpose:** Central manager for objects, outputs, and rendering pipeline.

**Implementation:**

```python
# src/modules/artnet_routing/artnet_routing_manager.py

from typing import Dict, List, Optional
from .artnet_object import ArtNetObject
from .artnet_output import ArtNetOutput
from .point_generator import PointGenerator
from ..logger import get_logger

logger = get_logger(__name__)

class ArtNetRoutingManager:
    """Manages ArtNet objects, outputs, and routing assignments"""
    
    def __init__(self, session_state_manager):
        self.session = session_state_manager
        self.objects: Dict[str, ArtNetObject] = {}
        self.outputs: Dict[str, ArtNetOutput] = {}
        
    def sync_from_editor_shapes(self) -> List[ArtNetObject]:
        """
        Load shapes from session_state.editor.shapes and generate ArtNet objects
        
        Returns:
            List of newly created/updated ArtNet objects
        """
        editor_state = self.session._state.get('editor', {})
        shapes = editor_state.get('shapes', [])
        
        if not shapes:
            logger.info("No editor shapes found in session state")
            return []
        
        created_objects = []
        
        for shape in shapes:
            shape_id = shape['id']
            
            # Check if object already exists
            existing_obj = self._find_object_by_shape_id(shape_id)
            
            if existing_obj:
                # Update existing object
                obj = self._update_object_from_shape(existing_obj, shape)
            else:
                # Create new object
                obj = self._create_object_from_shape(shape)
                self.objects[obj.id] = obj
            
            created_objects.append(obj)
        
        logger.info(f"✅ Synced {len(created_objects)} objects from editor shapes")
        return created_objects
    
    def _find_object_by_shape_id(self, shape_id: str) -> Optional[ArtNetObject]:
        """Find ArtNet object by source shape ID"""
        for obj in self.objects.values():
            if obj.source_shape_id == shape_id:
                return obj
        return None
    
    def _create_object_from_shape(self, shape: dict) -> ArtNetObject:
        """Create new ArtNet object from editor shape"""
        import uuid
        
        # Generate LED coordinates
        points = PointGenerator.generate_points(shape)
        
        # Create object
        obj_id = f"obj-{uuid.uuid4().hex[:8]}"
        obj = ArtNetObject(
            id=obj_id,
            name=shape.get('name', f"Object {obj_id}"),
            source_shape_id=shape['id'],
            type=shape['type'],
            points=points,
            led_type='RGB',  # Default, can be changed by user
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        # Calculate universe range
        obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.debug(f"Created object {obj_id}: {len(points)} points, universes {obj.universe_start}-{obj.universe_end}")
        
        return obj
    
    def _update_object_from_shape(self, obj: ArtNetObject, shape: dict) -> ArtNetObject:
        """Update existing ArtNet object from modified editor shape"""
        # Regenerate LED coordinates
        obj.points = PointGenerator.generate_points(shape)
        obj.name = shape.get('name', obj.name)
        obj.type = shape['type']
        
        # Recalculate universe range
        obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.debug(f"Updated object {obj.id}: {len(obj.points)} points")
        
        return obj
    
    def get_state(self) -> dict:
        """Get complete routing state for session persistence"""
        return {
            'objects': {obj_id: obj.to_dict() for obj_id, obj in self.objects.items()},
            'outputs': {out_id: out.to_dict() for out_id, out in self.outputs.items()}
        }
    
    def set_state(self, state: dict):
        """Restore routing state from session"""
        # Restore objects
        self.objects = {}
        for obj_id, obj_data in state.get('objects', {}).items():
            self.objects[obj_id] = ArtNetObject.from_dict(obj_data)
        
        # Restore outputs
        self.outputs = {}
        for out_id, out_data in state.get('outputs', {}).items():
            self.outputs[out_id] = ArtNetOutput.from_dict(out_data)
        
        logger.info(f"✅ Restored state: {len(self.objects)} objects, {len(self.outputs)} outputs")
    
    # CRUD Operations for Objects
    
    def create_object(self, obj: ArtNetObject):
        """Add new ArtNet object"""
        self.objects[obj.id] = obj
        logger.info(f"Created object {obj.id}")
    
    def update_object(self, obj_id: str, updates: dict):
        """Update ArtNet object properties"""
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        
        obj = self.objects[obj_id]
        
        # Update properties
        for key, value in updates.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        
        # Recalculate universe range if LED config changed
        if any(k in updates for k in ['led_type', 'channels_per_pixel', 'points']):
            obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.info(f"Updated object {obj_id}")
    
    def delete_object(self, obj_id: str):
        """Delete ArtNet object"""
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        
        # Remove from all outputs
        for output in self.outputs.values():
            if obj_id in output.assigned_objects:
                output.assigned_objects.remove(obj_id)
        
        del self.objects[obj_id]
        logger.info(f"Deleted object {obj_id}")
    
    # CRUD Operations for Outputs
    
    def create_output(self, output: ArtNetOutput):
        """Add new ArtNet output"""
        self.outputs[output.id] = output
        logger.info(f"Created output {output.id}")
    
    def update_output(self, out_id: str, updates: dict):
        """Update ArtNet output properties"""
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        
        # Update properties
        for key, value in updates.items():
            if hasattr(output, key):
                setattr(output, key, value)
        
        logger.info(f"Updated output {out_id}")
    
    def delete_output(self, out_id: str):
        """Delete ArtNet output"""
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        del self.outputs[out_id]
        logger.info(f"Deleted output {out_id}")
    
    # Assignment Operations
    
    def assign_object_to_output(self, obj_id: str, out_id: str):
        """Assign ArtNet object to output"""
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        if obj_id not in output.assigned_objects:
            output.assigned_objects.append(obj_id)
            logger.info(f"Assigned object {obj_id} to output {out_id}")
    
    def remove_object_from_output(self, obj_id: str, out_id: str):
        """Remove ArtNet object from output"""
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        if obj_id in output.assigned_objects:
            output.assigned_objects.remove(obj_id)
            logger.info(f"Removed object {obj_id} from output {out_id}")
```

---

## 📡 REST API Endpoints

**Implementation:**

```python
# src/modules/api/api_artnet_routing.py

from flask import Blueprint, jsonify, request
from ..artnet_routing.artnet_routing_manager import ArtNetRoutingManager
from ..artnet_routing.artnet_object import ArtNetObject
from ..artnet_routing.artnet_output import ArtNetOutput
from ..logger import get_logger

logger = get_logger(__name__)

def register_artnet_routing_routes(app, routing_manager: ArtNetRoutingManager):
    """Register ArtNet routing API endpoints"""
    
    # ==================== SYNC ====================
    
    @app.route('/api/artnet/routing/sync', methods=['POST'])
    def sync_from_editor():
        """Sync ArtNet objects from editor shapes"""
        try:
            objects = routing_manager.sync_from_editor_shapes()
            return jsonify({
                'success': True,
                'objects': [obj.to_dict() for obj in objects],
                'count': len(objects)
            })
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== OBJECTS ====================
    
    @app.route('/api/artnet/routing/objects', methods=['GET'])
    def get_objects():
        """Get all ArtNet objects"""
        try:
            objects = [obj.to_dict() for obj in routing_manager.objects.values()]
            return jsonify({'success': True, 'objects': objects})
        except Exception as e:
            logger.error(f"Get objects error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['GET'])
    def get_object(obj_id):
        """Get single ArtNet object"""
        try:
            if obj_id not in routing_manager.objects:
                return jsonify({'success': False, 'error': 'Object not found'}), 404
            
            obj = routing_manager.objects[obj_id]
            return jsonify({'success': True, 'object': obj.to_dict()})
        except Exception as e:
            logger.error(f"Get object error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects', methods=['POST'])
    def create_object():
        """Create new ArtNet object"""
        try:
            data = request.get_json()
            obj = ArtNetObject.from_dict(data)
            routing_manager.create_object(obj)
            return jsonify({'success': True, 'object': obj.to_dict()})
        except Exception as e:
            logger.error(f"Create object error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['PUT'])
    def update_object(obj_id):
        """Update ArtNet object"""
        try:
            data = request.get_json()
            routing_manager.update_object(obj_id, data)
            obj = routing_manager.objects[obj_id]
            return jsonify({'success': True, 'object': obj.to_dict()})
        except Exception as e:
            logger.error(f"Update object error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['DELETE'])
    def delete_object(obj_id):
        """Delete ArtNet object"""
        try:
            routing_manager.delete_object(obj_id)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Delete object error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== OUTPUTS ====================
    
    @app.route('/api/artnet/routing/outputs', methods=['GET'])
    def get_outputs():
        """Get all ArtNet outputs"""
        try:
            outputs = [out.to_dict() for out in routing_manager.outputs.values()]
            return jsonify({'success': True, 'outputs': outputs})
        except Exception as e:
            logger.error(f"Get outputs error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['GET'])
    def get_output(out_id):
        """Get single ArtNet output"""
        try:
            if out_id not in routing_manager.outputs:
                return jsonify({'success': False, 'error': 'Output not found'}), 404
            
            output = routing_manager.outputs[out_id]
            return jsonify({'success': True, 'output': output.to_dict()})
        except Exception as e:
            logger.error(f"Get output error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs', methods=['POST'])
    def create_output():
        """Create new ArtNet output"""
        try:
            data = request.get_json()
            output = ArtNetOutput.from_dict(data)
            routing_manager.create_output(output)
            return jsonify({'success': True, 'output': output.to_dict()})
        except Exception as e:
            logger.error(f"Create output error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['PUT'])
    def update_output(out_id):
        """Update ArtNet output"""
        try:
            data = request.get_json()
            routing_manager.update_output(out_id, data)
            output = routing_manager.outputs[out_id]
            return jsonify({'success': True, 'output': output.to_dict()})
        except Exception as e:
            logger.error(f"Update output error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['DELETE'])
    def delete_output(out_id):
        """Delete ArtNet output"""
        try:
            routing_manager.delete_output(out_id)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Delete output error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== ASSIGNMENTS ====================
    
    @app.route('/api/artnet/routing/assign', methods=['POST'])
    def assign_object():
        """Assign object to output"""
        try:
            data = request.get_json()
            obj_id = data['objectId']
            out_id = data['outputId']
            
            routing_manager.assign_object_to_output(obj_id, out_id)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Assign error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/unassign', methods=['POST'])
    def unassign_object():
        """Remove object from output"""
        try:
            data = request.get_json()
            obj_id = data['objectId']
            out_id = data['outputId']
            
            routing_manager.remove_object_from_output(obj_id, out_id)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Unassign error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== STATE ====================
    
    @app.route('/api/artnet/routing/state', methods=['GET'])
    def get_routing_state():
        """Get complete routing state"""
        try:
            state = routing_manager.get_state()
            return jsonify({'success': True, 'state': state})
        except Exception as e:
            logger.error(f"Get state error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/state', methods=['POST'])
    def set_routing_state():
        """Set complete routing state"""
        try:
            data = request.get_json()
            routing_manager.set_state(data.get('state', {}))
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Set state error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
```

---

## 📊 Session State Integration

**Structure:**

```json
{
  "editor": {
    "shapes": [...],
    "canvas": {"width": 1920, "height": 1080}
  },
  "artnet_routing": {
    "objects": {
      "obj-123": {
        "id": "obj-123",
        "name": "Matrix Left",
        "sourceShapeId": "shape-1",
        "type": "matrix",
        "points": [{}, {}, ...],
        "ledType": "RGB",
        "universeStart": 1,
        "universeEnd": 2
      }
    },
    "outputs": {
      "out-456": {
        "id": "out-456",
        "name": "Main LED Wall",
        "targetIP": "192.168.1.10",
        "startUniverse": 1,
        "assignedObjects": ["obj-123", "obj-789"]
      }
    }
  }
}
```

**Modifications to `session_state.py`:**

```python
# In _build_state_dict() method, add:

# ArtNet routing (updated via routing_manager)
if hasattr(player_manager, 'artnet_routing_manager'):
    routing_state = player_manager.artnet_routing_manager.get_state()
    state['artnet_routing'] = routing_state

# During restore, add:

# Restore ArtNet routing
if 'artnet_routing' in state and hasattr(player_manager, 'artnet_routing_manager'):
    player_manager.artnet_routing_manager.set_state(state['artnet_routing'])
```

---

## 🎨 Frontend Architecture (Dual-Mode Output Settings)

### Overview

Reuse existing `frontend/output-settings.html` with a **mode switcher** for Video/ArtNet routing.

### Mode Switcher (Top of Left Panel)

```html
<div class="mode-switcher" style="padding: 1rem; border-bottom: 1px solid var(--border-color);">
  <div class="btn-group" role="group" style="width: 100%;">
    <button id="videoModeBtn" class="btn btn-primary active" onclick="switchMode('video')">
      Video Output
    </button>
    <button id="artnetModeBtn" class="btn btn-secondary" onclick="switchMode('artnet')">
      ArtNet Output
    </button>
  </div>
</div>
```

### UI Layout Comparison

| Section | Video Mode | ArtNet Mode |
|---------|-----------|-------------|
| **Left Panel - Outputs** | Video outputs (monitors) | ArtNet endpoints (IP, universe, FPS) |
| **Left Panel - Canvas** | Video canvas resolution | ArtNet input resolution (from editor) |
| **Left Panel - Tools** | Slice drawing tools | Reserved (future use) |
| **Right Panel** | Slice properties (geometry, transforms) | Object properties (LED type, white detection, color correction) |
| **Center Canvas** | Video preview with slices | ArtNet preview with LED coordinates |

### ArtNet Mode - Left Panel

#### Outputs Section
```javascript
// Display ArtNet endpoints instead of monitors
{
  id: 'out-456',
  name: 'Main LED Wall',
  targetIP: '192.168.1.10',
  startUniverse: 1,
  fps: 30,
  delay: 0,
  active: true,
  assignedObjects: ['obj-123', 'obj-789']
}
```

**UI Elements:**
- Name input
- IP address input
- Start universe input
- FPS slider (1-60)
- Delay input (milliseconds)
- Active toggle
- Assigned objects count badge
- Edit/Delete buttons

#### Canvas Section
- **Display:** ArtNet input resolution (from `session_state.editor.canvas`)
- **Format:** "1920 × 1080" (read-only)
- **Purpose:** Show the coordinate space where LED objects are mapped
- **Note:** Matches editor canvas resolution

#### Tools Section
- **Current:** Empty (reserved for future features)
- **Potential Future Use:**
  - Universe calculator
  - White balance presets
  - Test pattern generator
  - Object grouping tools

### ArtNet Mode - Right Panel

#### Object List
```javascript
// Display ArtNet objects (synced from editor shapes)
{
  id: 'obj-123',
  name: 'Matrix Left',
  sourceShapeId: 'shape-1',
  type: 'matrix',
  pointCount: 80,
  ledType: 'RGB',
  universeStart: 1,
  universeEnd: 2
}
```

#### Object Properties Panel (when object selected)
```html
<div class="object-properties">
  <!-- Basic Info -->
  <h3>Matrix Left</h3>
  <p>80 LEDs • Universes 1-2</p>
  
  <!-- LED Configuration -->
  <div class="form-group">
    <label>LED Type</label>
    <select id="ledType">
      <option value="RGB">RGB (3 channels)</option>
      <option value="RGBW">RGBW (4 channels)</option>
      <option value="RGBAW">RGBAW (5 channels)</option>
      <option value="RGBWW">RGBWW (5 channels)</option>
      <option value="RGBCW">RGBCW (5 channels)</option>
      <option value="RGBCWW">RGBCWW (6 channels)</option>
    </select>
  </div>
  
  <div class="form-group">
    <label>Channel Order</label>
    <select id="channelOrder">
      <option value="RGB">RGB</option>
      <option value="GRB">GRB</option>
      <option value="BGR">BGR</option>
      <!-- Dynamic options based on LED type -->
    </select>
  </div>
  
  <!-- White Channel (if RGBW+) -->
  <div class="white-channel-section">
    <div class="form-check">
      <input type="checkbox" id="whiteDetection" checked>
      <label>White Detection</label>
    </div>
    
    <div class="form-group">
      <label>Detection Mode</label>
      <select id="whiteMode">
        <option value="luminance">Luminance (ITU-R BT.709)</option>
        <option value="minimum">Minimum (Best for RGBW)</option>
        <option value="average">Average</option>
      </select>
    </div>
    
    <div class="form-group">
      <label>White Threshold</label>
      <input type="range" id="whiteThreshold" min="0" max="255" value="200">
      <span>200</span>
    </div>
    
    <div class="form-group">
      <label>White Behavior</label>
      <select id="whiteBehavior">
        <option value="hybrid">Hybrid (Recommended)</option>
        <option value="replace">Replace RGB</option>
        <option value="additive">Additive</option>
      </select>
    </div>
    
    <!-- For RGBWW/RGBCW -->
    <div class="form-group">
      <label>Color Temperature</label>
      <input type="range" id="colorTemp" min="2700" max="6500" value="4500">
      <span>4500K</span>
    </div>
  </div>
  
  <!-- Color Correction -->
  <div class="color-correction">
    <label>Brightness</label>
    <input type="range" min="-255" max="255" value="0">
    
    <label>Contrast</label>
    <input type="range" min="-255" max="255" value="0">
    
    <label>Red</label>
    <input type="range" min="-255" max="255" value="0">
    
    <label>Green</label>
    <input type="range" min="-255" max="255" value="0">
    
    <label>Blue</label>
    <input type="range" min="-255" max="255" value="0">
  </div>
  
  <!-- Timing -->
  <div class="form-group">
    <label>Delay (ms)</label>
    <input type="number" id="delay" value="0" min="0">
  </div>
  
  <!-- Layer Routing -->
  <div class="form-group">
    <label>Input Layer</label>
    <select id="inputLayer">
      <option value="player">Player (Layer 0)</option>
      <option value="layer1">Layer 1</option>
      <option value="layer2">Layer 2</option>
      <!-- ... up to Layer 10 -->
    </select>
  </div>
  
  <!-- Master-Slave Linking -->
  <div class="form-group">
    <label>Link to Master</label>
    <select id="masterId">
      <option value="">None (Independent)</option>
      <option value="obj-456">Matrix Right</option>
      <!-- List of other objects with same point count -->
    </select>
  </div>
  
  <!-- Output Assignment -->
  <div class="form-group">
    <label>Assigned to Outputs</label>
    <div class="assigned-outputs">
      <span class="badge">Main LED Wall</span>
      <span class="badge">Backup Output</span>
    </div>
    <button class="btn btn-sm" onclick="showAssignModal()">Assign...</button>
  </div>
</div>
```

### ArtNet Mode - Center Canvas

#### Canvas Rendering
- **Background:** ArtNet input resolution canvas
- **Objects:** LED coordinates rendered as dots
- **Colors:** Object color coding (matching editor)
- **Selection:** Click to select object (updates right panel)
- **Preview Mode:** Sample actual video pixels at LED coordinates
- **Universe Boundaries:** Optional overlay showing universe ranges

#### Preview Modes
1. **Shape View:** Show object outlines (like editor)
2. **LED View:** Show individual LED dots
3. **Preview View:** Show actual colors from video input
4. **Universe View:** Color-code by universe assignment

### Mode Switching Logic

```javascript
// Mode state
let currentMode = 'video'; // 'video' or 'artnet'

async function switchMode(mode) {
  if (mode === currentMode) return;
  
  currentMode = mode;
  
  // Update UI
  document.getElementById('videoModeBtn').classList.toggle('active', mode === 'video');
  document.getElementById('artnetModeBtn').classList.toggle('active', mode === 'artnet');
  
  if (mode === 'artnet') {
    // Switch to ArtNet mode
    
    // 1. Sync objects from editor shapes
    await fetch('/api/artnet/routing/sync', { method: 'POST' });
    
    // 2. Load ArtNet outputs
    const outputsRes = await fetch('/api/artnet/routing/outputs');
    const outputsData = await outputsRes.json();
    artnetOutputs = outputsData.outputs;
    
    // 3. Load ArtNet objects
    const objectsRes = await fetch('/api/artnet/routing/objects');
    const objectsData = await objectsRes.json();
    artnetObjects = objectsData.objects;
    
    // 4. Update UI
    renderArtNetOutputs();
    renderArtNetObjects();
    renderArtNetCanvas();
    
    // 5. Setup ArtNet-specific event listeners
    setupArtNetContextMenu();
    
  } else {
    // Switch to Video mode
    
    // 1. Load video outputs
    await loadVideoOutputs();
    
    // 2. Load slices
    await loadSlices();
    
    // 3. Update UI
    renderVideoOutputs();
    renderSlices();
    renderVideoCanvas();
    
    // 4. Remove ArtNet event listeners
    removeArtNetContextMenu();
  }
}
```

### DMX Monitor Integration (Debugging)

#### Context Menu Implementation

```javascript
// ArtNet context menu setup
let contextMenu = null;

function setupArtNetContextMenu() {
  const canvas = document.getElementById('canvas');
  
  // Remove any existing context menu handler
  canvas.oncontextmenu = (e) => {
    e.preventDefault();
    
    // Only show in ArtNet mode
    if (currentMode !== 'artnet') return;
    
    // Remove existing menu if any
    if (contextMenu) {
      contextMenu.remove();
    }
    
    // Create context menu
    contextMenu = document.createElement('div');
    contextMenu.className = 'context-menu';
    contextMenu.style.cssText = `
      position: fixed;
      left: ${e.clientX}px;
      top: ${e.clientY}px;
      background: var(--panel-bg);
      border: 1px solid var(--border-color);
      border-radius: 4px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.3);
      z-index: 10000;
      min-width: 180px;
      padding: 4px 0;
    `;
    
    // Add menu items
    const menuItems = [
      {
        label: '🔍 Preview Output',
        action: () => openDMXMonitor()
      },
      {
        label: '📊 Universe Statistics',
        action: () => showUniverseStats()
      },
      {
        label: '🎨 Test Pattern',
        action: () => sendTestPattern()
      }
    ];
    
    menuItems.forEach(item => {
      const menuItem = document.createElement('div');
      menuItem.className = 'context-menu-item';
      menuItem.textContent = item.label;
      menuItem.style.cssText = `
        padding: 8px 16px;
        cursor: pointer;
        transition: background 0.2s;
      `;
      menuItem.onmouseover = () => {
        menuItem.style.background = 'var(--hover-bg)';
      };
      menuItem.onmouseout = () => {
        menuItem.style.background = 'transparent';
      };
      menuItem.onclick = () => {
        item.action();
        contextMenu.remove();
        contextMenu = null;
      };
      contextMenu.appendChild(menuItem);
    });
    
    document.body.appendChild(contextMenu);
    
    return false;
  };
  
  // Close context menu on click elsewhere
  document.addEventListener('click', closeContextMenu);
}

function closeContextMenu() {
  if (contextMenu) {
    contextMenu.remove();
    contextMenu = null;
  }
}

function removeArtNetContextMenu() {
  const canvas = document.getElementById('canvas');
  canvas.oncontextmenu = null;
  closeContextMenu();
  document.removeEventListener('click', closeContextMenu);
}
```

#### DMX Monitor Modal

```javascript
// DMX Monitor Modal (reuses artnet.html DMX grid UI)
function openDMXMonitor() {
  // Create modal backdrop
  const backdrop = document.createElement('div');
  backdrop.id = 'dmxMonitorBackdrop';
  backdrop.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.7);
    z-index: 9999;
    display: flex;
    align-items: center;
    justify-content: center;
  `;
  
  // Create modal container
  const modal = document.createElement('div');
  modal.id = 'dmxMonitorModal';
  modal.style.cssText = `
    background: var(--panel-bg);
    border-radius: 8px;
    width: 90%;
    max-width: 1200px;
    height: 80%;
    max-height: 800px;
    display: flex;
    flex-direction: column;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
  `;
  
  // Modal header
  const header = document.createElement('div');
  header.style.cssText = `
    padding: 1rem 1.5rem;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    justify-content: space-between;
    align-items: center;
  `;
  header.innerHTML = `
    <div>
      <h3 style="margin: 0; font-size: 1.2rem;">DMX Monitor - ArtNet Output Preview</h3>
      <p style="margin: 0.25rem 0 0 0; font-size: 0.85rem; opacity: 0.7;">
        Real-time DMX channel monitoring
      </p>
    </div>
    <div style="display: flex; gap: 1rem; align-items: center;">
      <label style="font-size: 0.9rem;">Universe:</label>
      <select id="dmxUniverseSelector" class="form-select" style="width: 120px;">
        <!-- Populated dynamically -->
      </select>
      <button class="btn btn-secondary" onclick="closeDMXMonitor()">Close</button>
    </div>
  `;
  
  // Modal body (DMX grid container)
  const body = document.createElement('div');
  body.style.cssText = `
    flex: 1;
    overflow: auto;
    padding: 1rem;
  `;
  body.innerHTML = `
    <div id="dmxGridContainer" style="
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(50px, 1fr));
      gap: 4px;
      max-width: 100%;
    ">
      <!-- DMX channels will be populated here -->
    </div>
    
    <div style="margin-top: 1rem; padding: 1rem; background: var(--info-bg); border-radius: 4px;">
      <h4 style="margin: 0 0 0.5rem 0;">Channel Value Legend</h4>
      <div style="display: flex; gap: 1rem; font-size: 0.85rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <div style="width: 20px; height: 20px; background: #1a1a1a; border: 1px solid #333;"></div>
          <span>0 (Off)</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <div style="width: 20px; height: 20px; background: #ff0000; border: 1px solid #333;"></div>
          <span>255 (Full)</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <div style="width: 20px; height: 20px; background: #666; border: 1px solid #333;"></div>
          <span>1-254 (Partial)</span>
        </div>
      </div>
    </div>
  `;
  
  modal.appendChild(header);
  modal.appendChild(body);
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);
  
  // Close on backdrop click
  backdrop.onclick = (e) => {
    if (e.target === backdrop) {
      closeDMXMonitor();
    }
  };
  
  // Initialize DMX monitor
  initDMXMonitor();
}

function closeDMXMonitor() {
  const backdrop = document.getElementById('dmxMonitorBackdrop');
  if (backdrop) {
    backdrop.remove();
  }
  
  // Stop polling DMX data
  if (window.dmxMonitorInterval) {
    clearInterval(window.dmxMonitorInterval);
    window.dmxMonitorInterval = null;
  }
}

async function initDMXMonitor() {
  // Populate universe selector based on assigned objects
  const universeSelector = document.getElementById('dmxUniverseSelector');
  
  // Get all universes from current objects
  const universes = new Set();
  artnetObjects.forEach(obj => {
    for (let u = obj.universeStart; u <= obj.universeEnd; u++) {
      universes.add(u);
    }
  });
  
  // Add options
  Array.from(universes).sort((a, b) => a - b).forEach(u => {
    const option = document.createElement('option');
    option.value = u;
    option.textContent = `Universe ${u}`;
    universeSelector.appendChild(option);
  });
  
  // Set default to first universe
  if (universes.size > 0) {
    universeSelector.value = Array.from(universes)[0];
  }
  
  // Load initial DMX data
  await updateDMXGrid();
  
  // Setup auto-refresh (every 100ms for smooth updates)
  window.dmxMonitorInterval = setInterval(updateDMXGrid, 100);
  
  // Update on universe change
  universeSelector.onchange = updateDMXGrid;
}

async function updateDMXGrid() {
  const universeSelector = document.getElementById('dmxUniverseSelector');
  if (!universeSelector) return;
  
  const universe = parseInt(universeSelector.value);
  
  try {
    // Fetch DMX data from backend
    const response = await fetch(`/api/artnet/dmx/${universe}`);
    const data = await response.json();
    
    if (!data.success) {
      console.error('Failed to fetch DMX data:', data.error);
      return;
    }
    
    const channels = data.channels; // Array of 512 channel values (0-255)
    
    // Render grid
    const gridContainer = document.getElementById('dmxGridContainer');
    if (!gridContainer) return;
    
    // Clear existing grid
    gridContainer.innerHTML = '';
    
    // Create channel cells (512 channels)
    for (let i = 0; i < 512; i++) {
      const value = channels[i] || 0;
      
      // Calculate color based on value
      let bgColor;
      if (value === 0) {
        bgColor = '#1a1a1a'; // Black for off
      } else if (value === 255) {
        bgColor = '#ff0000'; // Red for full
      } else {
        const intensity = Math.floor((value / 255) * 100);
        bgColor = `hsl(0, 0%, ${intensity}%)`; // Gray scale for partial
      }
      
      const cell = document.createElement('div');
      cell.style.cssText = `
        background: ${bgColor};
        border: 1px solid var(--border-color);
        border-radius: 2px;
        padding: 4px;
        text-align: center;
        font-size: 0.7rem;
        min-height: 50px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        cursor: help;
      `;
      
      cell.innerHTML = `
        <div style="font-weight: bold; color: ${value > 128 ? '#000' : '#fff'};">
          ${i + 1}
        </div>
        <div style="font-size: 0.65rem; color: ${value > 128 ? '#333' : '#999'};">
          ${value}
        </div>
      `;
      
      cell.title = `Channel ${i + 1}: ${value}`;
      
      gridContainer.appendChild(cell);
    }
    
  } catch (error) {
    console.error('DMX monitor update error:', error);
  }
}

// Additional debug functions
function showUniverseStats() {
  // Calculate universe statistics
  const stats = {};
  
  artnetObjects.forEach(obj => {
    const range = `${obj.universeStart}-${obj.universeEnd}`;
    if (!stats[range]) {
      stats[range] = {
        objects: [],
        channels: 0,
        universes: obj.universeEnd - obj.universeStart + 1
      };
    }
    stats[range].objects.push(obj.name);
    stats[range].channels += obj.points.length * obj.channelsPerPixel;
  });
  
  console.table(stats);
  alert('Universe statistics logged to console');
}

function sendTestPattern() {
  // Send test pattern to selected objects
  const confirmed = confirm('Send test pattern to all assigned objects?');
  if (confirmed) {
    fetch('/api/artnet/test-pattern', { method: 'POST' })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          alert('Test pattern sent!');
        }
      });
  }
}
```

#### Backend API for DMX Monitor

```python
# Add to api_artnet_routing.py

@app.route('/api/artnet/dmx/<int:universe>', methods=['GET'])
def get_dmx_data(universe):
    """Get current DMX channel values for a universe (for DMX monitor)"""
    try:
        # Get ArtNet player
        artnet_player = player_manager.get_player('artnet')
        if not artnet_player or not hasattr(artnet_player, 'artnet_manager'):
            return jsonify({'success': False, 'error': 'ArtNet not available'}), 404
        
        artnet_mgr = artnet_player.artnet_manager
        
        # Get last frame data
        if not artnet_mgr.last_frame:
            # Return zeros if no frame data
            return jsonify({
                'success': True,
                'universe': universe,
                'channels': [0] * 512
            })
        
        # Extract 512 channels for this universe
        universe_offset = (universe - artnet_mgr.start_universe) * 510
        frame_data = artnet_mgr.last_frame
        
        channels = []
        for i in range(512):
            channel_index = universe_offset + i
            if channel_index < len(frame_data):
                channels.append(int(frame_data[channel_index]))
            else:
                channels.append(0)
        
        return jsonify({
            'success': True,
            'universe': universe,
            'channels': channels
        })
        
    except Exception as e:
        logger.error(f"DMX data error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

### Data Flow

```
User opens output-settings.html
        ↓
Default: Video Mode
        ↓
User clicks "ArtNet Output" button
        ↓
POST /api/artnet/routing/sync  (generate objects from editor shapes)
        ↓
GET /api/artnet/routing/objects (fetch generated objects)
        ↓
GET /api/artnet/routing/outputs (fetch ArtNet endpoints)
        ↓
Render ArtNet UI (outputs list, objects list, canvas)
        ↓
User edits object properties
        ↓
PUT /api/artnet/routing/objects/{id}
        ↓
Auto-save to session state (debounced, like video mode)
```

### Session State Structure

```json
{
  "video_routing": {
    "outputs": {...},
    "slices": {...}
  },
  "artnet_routing": {
    "objects": {...},
    "outputs": {...}
  }
}
```

**Key Points:**
- Both routing systems coexist in session state
- Switching modes doesn't lose data
- Each mode has independent output/object management
- Canvas shows appropriate preview for current mode

---

## 🚀 Implementation Phases

### Phase 1: Core Data Models (1-2 hours)
- [ ] Create `src/modules/artnet_routing/` folder
- [ ] Implement `artnet_object.py` (ArtNetObject, ArtNetPoint)
- [ ] Implement `artnet_output.py` (ArtNetOutput)
- [ ] Add tests for serialization/deserialization

### Phase 2: Point Generation (2-3 hours)
- [ ] Implement `point_generator.py` (PointGenerator)
- [ ] Port matrix generation from editor.js
- [ ] Port circle generation
- [ ] Port line generation
- [ ] Port star generation
- [ ] Add tests for coordinate accuracy

### Phase 3: Routing Manager (2-3 hours)
- [ ] Implement `artnet_routing_manager.py` (ArtNetRoutingManager)
- [ ] Add object CRUD operations
- [ ] Add output CRUD operations
- [ ] Add assignment operations
- [ ] Implement `sync_from_editor_shapes()`

### Phase 4: REST API (1-2 hours)
- [ ] Create `src/modules/api/api_artnet_routing.py`
- [ ] Implement object endpoints (/objects)
- [ ] Implement output endpoints (/outputs)
- [ ] Implement assignment endpoints (/assign, /unassign)
- [ ] Implement state endpoints (/state)

### Phase 5: Session State Integration (1 hour)
- [ ] Modify `session_state.py` to include artnet_routing
- [ ] Add routing_manager to player_manager initialization
- [ ] Test save/restore cycle

### Phase 6: Frontend Integration (3-4 hours)
- [ ] Adapt `frontend/output-settings.html` to support dual mode (Video/ArtNet)
- [ ] Add mode switcher at top of left panel (toggle between Video/ArtNet)
- [ ] **Left Panel (ArtNet mode):**
  - [ ] Outputs section: Show ArtNet endpoints (IP, universe, FPS, delay)
  - [ ] Canvas section: Display ArtNet input resolution (from editor canvas)
  - [ ] Tools section: Reserved for future use
- [ ] **Right Panel (ArtNet mode):**
  - [ ] Show ArtNet objects (generated from editor shapes via sync)
  - [ ] Display object properties: LED type, channel order, white detection, color correction
  - [ ] Object assignment to outputs
- [ ] **Center Canvas (ArtNet mode):**
  - [ ] Show ArtNet input in realtime (similar to video routing)
  - [ ] Display shapes/objects with LED coordinates
  - [ ] Preview mode with actual pixel sampling
  - [ ] Right-click context menu with "Preview Output" option
- [ ] **DMX Monitor Integration (Debugging):**
  - [ ] Implement context menu on canvas right-click
  - [ ] Add "Preview Output" menu option
  - [ ] Create DMX monitor modal (reuse artnet.html monitor UI)
  - [ ] Show DMX channel grid with universe selector
  - [ ] Display real-time channel values (0-255) with color coding
  - [ ] Update monitor when selecting different objects/outputs
- [ ] Call `/api/artnet/routing/sync` on mode switch to generate objects
- [ ] Save/restore ArtNet routing state via session state

---

## ✅ Testing Checklist

### Backend Tests
- [ ] Editor shapes saved to session state
- [ ] Sync API creates ArtNet objects from shapes
- [ ] Point generation matches editor.js output
- [ ] Universe calculations correct for RGB/RGBW/RGBAW
- [ ] Object-to-output assignments persist
- [ ] Session save includes artnet_routing
- [ ] Session restore rebuilds objects/outputs
- [ ] Objects update when editor shapes change
- [ ] Master-slave linking works
- [ ] Delta encoding per-output functional

### Frontend Tests
- [ ] Mode switcher toggles between Video/ArtNet modes
- [ ] ArtNet mode syncs objects from editor on first load
- [ ] Left panel shows ArtNet outputs (IP, universe, FPS)
- [ ] Left panel shows ArtNet input resolution
- [ ] Right panel shows object list with properties
- [ ] Selecting object updates right panel
- [ ] LED type changes update channels per pixel
- [ ] White detection UI shows/hides based on LED type
- [ ] Channel order options adapt to LED type
- [ ] Color correction sliders update object
- [ ] Object assignment to outputs works
- [ ] Canvas shows LED coordinates (dots)
- [ ] Canvas preview samples actual video pixels
- [ ] Universe boundaries overlay works
- [ ] Auto-save triggers on property changes
- [ ] Switching modes preserves data
- [ ] Video mode still works (no regression)
- [ ] ArtNet mode persists across page reload

### DMX Monitor Tests
- [ ] Right-click on canvas shows context menu
- [ ] Context menu only appears in ArtNet mode
- [ ] "Preview Output" opens DMX monitor modal
- [ ] DMX monitor shows 512 channels in grid
- [ ] Universe selector populated with assigned universes
- [ ] Channel values update in real-time (100ms refresh)
- [ ] Channel colors reflect intensity (black=0, red=255, gray=partial)
- [ ] Universe switching updates displayed channels
- [ ] Modal closes on backdrop click
- [ ] Modal closes on Close button
- [ ] Polling stops when modal closes
- [ ] Test pattern button sends data to ArtNet
- [ ] Universe statistics shows correct channel counts
- [ ] DMX monitor works during video playback

---

## 📚 Next Steps

1. **Review this plan** with team/user
2. **Create Phase 1** data models
3. **Port point generation** from editor.js to Python
4. **Implement routing manager** with sync logic
5. **Add REST API** endpoints
6. **Integrate with session state** for persistence
7. **Build frontend UI** (adapt prototype)
8. **Test end-to-end** workflow

---

## 🔗 Related Documents

- [ARTNET_OUTPUT_ROUTING_IMPLEMENTATION.md](./ARTNET_OUTPUT_ROUTING_IMPLEMENTATION.md) - Original detailed spec
- [CANVAS_EDITOR_SESSION_STATE_PLAN.md](./CANVAS_EDITOR_SESSION_STATE_PLAN.md) - Editor integration
- [LEGACY_DOTS_EXPORT_LOGIC.md](./LEGACY_DOTS_EXPORT_LOGIC.md) - Old point export system (deprecated)
- Frontend prototype: `snippets/artnet-output/artnet-output-prototype.html` (reference only, using output-settings.html instead)

---

## 💡 Implementation Benefits

### Reusing output-settings.html

✅ **UI Consistency:** Users familiar with video routing understand ArtNet routing instantly  
✅ **Code Reuse:** Leverages existing OutputManager/SliceManager patterns  
✅ **Rapid Development:** ~30% less code than building separate UI  
✅ **Unified Workflow:** Single page for all output routing (video + ArtNet)  
✅ **Session State Integration:** Already implemented, just extend for ArtNet  
✅ **Canvas Framework:** Drawing, panning, zooming already working  
✅ **Auto-Save Infrastructure:** Debouncing, error handling, status indicators ready  

### Architecture Advantages

- **Separation of Concerns:** Video routing and ArtNet routing coexist independently
- **Progressive Enhancement:** Video mode unaffected, no regressions
- **Data Integrity:** Both routing configs saved in session state
- **Scalability:** Easy to add third routing mode (e.g., DMX fixtures) in future
- **Performance:** Shared canvas renderer, no duplicate rendering logic

---

**Status:** ⏳ Awaiting approval to begin implementation
