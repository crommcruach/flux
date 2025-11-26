# New Plugins - Usage Examples

## Added Plugins

### 1. Opacity Effect Plugin
**File:** `src/plugins/effects/opacity.py`  
**Plugin ID:** `opacity`

Controls video transparency/opacity from 0% (fully transparent/black) to 100% (fully visible).

**Parameters:**
- `opacity` (0-100%) - Default: 100.0

### 2. Transform Effect Plugin
**File:** `src/plugins/effects/transform.py`  
**Plugin ID:** `transform`

2D/3D transformations with position, scale, and rotation.

**Parameters:**
- `position_x` (-2000 to +2000 px) - Default: 0.0
- `position_y` (-2000 to +2000 px) - Default: 0.0
- `scale_xy` (0-500%) - Symmetric scaling - Default: 100.0
- `scale_x` (0-500%) - Horizontal scaling - Default: 100.0
- `scale_y` (0-500%) - Vertical scaling - Default: 100.0
- `rotation_x` (0-360°) - 3D rotation around X-axis - Default: 0.0
- `rotation_y` (0-360°) - 3D rotation around Y-axis - Default: 0.0
- `rotation_z` (0-360°) - 2D rotation (clockwise) - Default: 0.0

## REST API Examples

### Add Opacity Effect (50% transparency)
```bash
curl -X POST http://localhost:5000/api/effects/video/add \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": "opacity",
    "config": {
      "opacity": 50.0
    }
  }'
```

### Add Transform Effect (scale and rotate)
```bash
curl -X POST http://localhost:5000/api/effects/video/add \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": "transform",
    "config": {
      "position_x": 100.0,
      "position_y": 50.0,
      "scale_xy": 120.0,
      "rotation_y": 25.0
    }
  }'
```

### Update Effect Parameter
```bash
# Update opacity to 75%
curl -X PUT http://localhost:5000/api/effects/video/0/parameter \
  -H "Content-Type: application/json" \
  -d '{
    "param_name": "opacity",
    "value": 75.0
  }'

# Update transform rotation
curl -X PUT http://localhost:5000/api/effects/video/0/parameter \
  -H "Content-Type: application/json" \
  -d '{
    "param_name": "rotation_x",
    "value": 45.0
  }'
```

### Get Current Effect Chain
```bash
curl http://localhost:5000/api/effects/video
```

### Remove Effect from Chain
```bash
curl -X DELETE http://localhost:5000/api/effects/video/0
```

### Clear All Effects
```bash
curl -X DELETE http://localhost:5000/api/effects/video
```

## Combined Usage Example

Create a cinematic effect with both plugins:

```bash
# 1. Add Transform for 3D perspective
curl -X POST http://localhost:5000/api/effects/video/add \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": "transform",
    "config": {
      "position_x": 0.0,
      "position_y": -50.0,
      "scale_xy": 110.0,
      "rotation_x": 15.0,
      "rotation_y": 10.0
    }
  }'

# 2. Add Opacity for fade effect
curl -X POST http://localhost:5000/api/effects/video/add \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": "opacity",
    "config": {
      "opacity": 85.0
    }
  }'
```

## Effect Chains

Effects can be applied to two separate chains:
- **video** - Preview/Video output only
- **artnet** - Art-Net DMX output only

Add effect to Art-Net chain:
```bash
curl -X POST http://localhost:5000/api/effects/artnet/add \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_id": "opacity",
    "config": {
      "opacity": 80.0
    }
  }'
```

## Python Integration Example

```python
from modules.plugin_manager import get_plugin_manager

# Load plugin manager
pm = get_plugin_manager()

# Create opacity effect instance
opacity_effect = pm.load_plugin('opacity', config={'opacity': 50.0})

# Apply to frame
import numpy as np
test_frame = np.ones((200, 200, 3), dtype=np.uint8) * 255  # White frame
result = opacity_effect.process_frame(test_frame)

# Update parameter
opacity_effect.update_parameter('opacity', 75.0)
result = opacity_effect.process_frame(test_frame)

# Create transform effect instance
transform_effect = pm.load_plugin('transform', config={
    'position_x': 50.0,
    'scale_xy': 150.0,
    'rotation_y': 30.0
})

# Apply to frame
result = transform_effect.process_frame(test_frame)
```

## Notes

- Both plugins automatically register on startup via PluginManager discovery
- Effects are applied in chain order (first added = first applied)
- Transform applies transformations in order: Scale → 2D Rotation (Z) → 3D Rotation (X, Y) → Position
- Transform maintains frame dimensions (crops/pads as needed)
- Opacity uses float precision for smooth gradients
- All parameters support runtime updates without reloading
