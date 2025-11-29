# Blend Effect Plugin - Layer Compositing Foundation

## Overview

The Blend Effect plugin provides the foundation for layer-based compositing in Flux. It implements 6 industry-standard blend modes to composite multiple video/generator layers into a final output frame.

## Features

### Blend Modes

1. **Normal** - Standard alpha blending (overlay replaces base)
2. **Multiply** - Darkens by multiplying colors (base × overlay)
3. **Screen** - Lightens using inverse multiply: `1 - (1-base) × (1-overlay)`
4. **Add** - Linear dodge, adds colors with clipping: `min(base + overlay, 1.0)`
5. **Subtract** - Subtracts overlay from base: `max(base - overlay, 0.0)`
6. **Overlay** - Combines multiply (dark) and screen (light) modes:
   - If base < 0.5: `2 × base × overlay`
   - If base ≥ 0.5: `1 - 2 × (1-base) × (1-overlay)`

### Parameters

- **blend_mode** (SELECT): Choose from 6 blend modes
- **opacity** (FLOAT): Layer opacity 0-100% (controls blend strength)

## Mathematical Verification

All blend modes have been mathematically verified:

```
Multiply: 0.5 × 0.5 = 0.25 (50% gray → 25% gray)
Screen:   1 - 0.5 × 0.5 = 0.75 (50% gray → 75% gray)
Add:      0.5 + 0.5 = 1.0 (clamped to 255)
Overlay Dark:  2 × 0.25 × 0.5 = 0.25
Overlay Light: 1 - 2 × 0.25 × 0.5 = 0.75
```

## Usage

### As Effect Plugin

```python
from plugins.effects.blend import BlendEffect

# Initialize
blend = BlendEffect()
blend.initialize({'blend_mode': 'multiply', 'opacity': 75.0})

# Apply to frames
result = blend.process_frame(base_frame, overlay=overlay_frame)
```

### In Layer Compositing

The blend effect will be used in the upcoming layer system:

```python
# Proposed Player Layer Structure
self.layers = [
    {
        "source": VideoSource("video1.mp4"),
        "effects": [],
        "blend_mode": "normal",
        "opacity": 100.0
    },
    {
        "source": GeneratorSource("plasma"),
        "effects": [BlurEffect(), TransformEffect()],
        "blend_mode": "multiply",
        "opacity": 50.0
    }
]
```

## Technical Details

### Performance

- **Float32 Precision**: All calculations use float32 to avoid uint8 overflow
- **Auto-Resize**: Automatically resizes overlay to match base frame dimensions
- **Efficient Blending**: Uses NumPy vectorized operations and cv2.addWeighted()
- **Memory Efficient**: In-place operations where possible

### Frame Processing Flow

1. Check if overlay exists (if not, only apply opacity)
2. Resize overlay to match base dimensions
3. Convert both frames to float32 normalized [0-1]
4. Apply selected blend mode algorithm
5. Apply opacity with cv2.addWeighted() for performance
6. Clip to [0-1] range and convert back to uint8

### Blend Mode Algorithms

All blend modes operate on normalized float32 values [0-1]:

```python
# Normal (Alpha Blend)
blended = overlay

# Multiply (Darkens)
blended = base * overlay

# Screen (Lightens)
blended = 1.0 - (1.0 - base) * (1.0 - overlay)

# Add (Linear Dodge)
blended = np.minimum(base + overlay, 1.0)

# Subtract
blended = np.maximum(base - overlay, 0.0)

# Overlay (Conditional)
mask = base < 0.5
multiply = 2.0 * base * overlay
screen = 1.0 - 2.0 * (1.0 - base) * (1.0 - overlay)
blended = np.where(mask, multiply, screen)
```

## Testing

Comprehensive test suite validates:
- ✓ All 6 blend modes with known inputs
- ✓ Opacity parameter (50% blend = 127 gray)
- ✓ Mathematical correctness of each mode
- ✓ Parameter updates at runtime
- ✓ Automatic frame resizing
- ✓ Edge cases (0%, 100% opacity, same colors)

Run tests:
```bash
cd tests
python test_blend_effect.py
```

## Integration with Layer System

The blend effect is designed as the foundation for the upcoming layer-based compositing architecture:

### Architecture Overview

Instead of the complex slot-based system (40-54h estimate), we use a simpler layer array:

```python
# Current Player (single source)
self.source = VideoSource(...)

# Proposed Player (multi-layer)
self.layers = [
    {"source": ..., "effects": [], "blend_mode": "normal", "opacity": 1.0},
    {"source": ..., "effects": [], "blend_mode": "multiply", "opacity": 0.5}
]
```

### Benefits

- **Simpler Architecture**: ~8h implementation vs 40-54h for slots
- **Backward Compatible**: 1 layer = current single-source behavior
- **Reuses Existing Systems**: Effect chains, transitions, playback logic
- **Industry Standard**: Blend modes familiar from Photoshop/After Effects

### Compositing Flow

1. Fetch frame from first layer (base)
2. Apply layer's effects
3. For each additional layer:
   - Fetch frame
   - Apply layer's effects
   - Use BlendEffect with layer's blend_mode + opacity
4. Apply global effects (if any)
5. Output to DMX/ArtNet

## Next Steps

1. **Modify Player for Layers** (~2h)
   - Add `self.layers = []` array
   - Implement layer management methods
   - Modify `_play_loop()` for sequential compositing

2. **Create Layer Management API** (~1h)
   - POST `/api/player/{id}/layers/add`
   - DELETE `/api/player/{id}/layers/{layer_id}`
   - PUT `/api/player/{id}/layers/reorder`
   - GET `/api/player/{id}/layers/list`

3. **Layer UI Component** (~3h)
   - Layer stack visualization
   - Drag & drop reordering
   - Blend mode dropdown per layer
   - Opacity slider per layer

4. **Test & Document** (~2h)

**Total Estimated Time**: ~8h for complete layer system

## References

- Blend modes reference: https://en.wikipedia.org/wiki/Blend_modes
- Photoshop blend modes: https://helpx.adobe.com/photoshop/using/blending-modes.html
- OpenCV documentation: https://docs.opencv.org/

## Version History

- **1.0.0** (2025-01-29) - Initial release
  - 6 blend modes: Normal, Multiply, Screen, Add, Subtract, Overlay
  - Opacity parameter with cv2.addWeighted optimization
  - Automatic frame resizing
  - Comprehensive test suite
