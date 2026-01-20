# 3D DMX Visualizer Prototype

Real-time 3D visualization of DMX lighting fixtures using Three.js and WebGL.

## Features

### Phase 1: Core (Implemented)
- ✅ Three.js scene with camera controls
- ✅ Stage floor with grid
- ✅ Multiple camera views (3D, Top, Front, Side)
- ✅ Orbit controls for navigation

### Phase 2: Fixture Models (Implemented)
- ✅ Moving Head fixtures (pan/tilt)
- ✅ LED PAR fixtures
- ✅ Strobe fixtures
- ✅ LED Strip fixtures (50 pixels)
- ✅ Display/Screen fixtures
- ✅ Light beams with transparency
- ✅ Shadows and lighting

### Phase 3: DMX Mapping (Implemented)
- ✅ DMX channel to 3D parameter mapping
- ✅ Pan/Tilt rotation (0-255 → degrees)
- ✅ Dimmer control (0-255 → intensity)
- ✅ RGB color control
- ✅ Test controls for manual DMX input

### Phase 4: Real-time Updates (Partially Implemented)
- ✅ Animation loop at 60fps
- ✅ Performance statistics (FPS, draw calls)
- ✅ Demo animations (rainbow chase, circular movement)
- 🔜 WebSocket connection to backend (code ready, needs backend)

### Phase 5: Visual Effects (Basic Implementation)
- ✅ Light beams (cone geometry)
- ✅ Spotlight rendering
- ✅ Color mixing
- 🔜 Bloom/glow post-processing
- 🔜 Volumetric lighting

## File Structure

```
snippets/dmx-visualizer/
├── index.html          # Main HTML page with UI
├── style.css           # Styling and layout
├── visualizer.js       # Core 3D engine (DMXVisualizer class)
├── fixtures.js         # Fixture library and DMX manager
├── demo.js             # Demo animations and WebSocket
└── README.md           # This file
```

## Usage

### Open the Visualizer

1. Open `index.html` in a modern web browser
2. The visualizer will automatically load with demo fixtures

### Controls

**Camera Navigation:**
- Left mouse: Rotate camera
- Right mouse: Pan camera
- Mouse wheel: Zoom in/out
- Buttons: Quick camera presets

**Stage Settings:**
- Adjust stage width and depth
- Update button refreshes the stage

**Add Fixtures:**
- Select fixture type from dropdown
- Click "Add Fixture" to place randomly
- Fixtures: Moving Head, LED PAR, Strobe, LED Strip, Display

**Test Controls:**
- Pan/Tilt sliders (0-255)
- Dimmer slider (0-255)
- Color picker (RGB)
- Controls affect the first fixture

**Visualization Options:**
- Show/Hide grid
- Show/Hide light beams
- Show/Hide labels (TODO)

**Fixture Selection:**
- Click on any fixture to select it
- Info panel shows fixture details

### Demo Animations

The demo automatically starts with:
- 4 moving heads (corners)
- 2 LED PARs (sides)
- 1 LED strip (back)
- 1 display screen (front)

Animations include:
- Moving heads: Circular pan/tilt movement + color cycle
- LED PARs: Pulsing dimmer + color cycle
- LED Strip: Rainbow chase effect

## Integration with Backend

### WebSocket Connection

The visualizer can connect to the backend DMX output stream:

```javascript
// In demo.js
connectDMXWebSocket(); // Uncomment to enable

// WebSocket URL: ws://localhost:5000/dmx-output
// Data format: { universe: 1, channels: [0-512] }
```

### Backend Implementation Needed

Add to `src/api/dmx_routes.py`:

```python
from flask_socketio import emit, Namespace

class DMXOutputNamespace(Namespace):
    def on_connect(self):
        print('Client connected to DMX output stream')
    
    def on_disconnect(self):
        print('Client disconnected from DMX output stream')

# Register namespace
socketio.on_namespace(DMXOutputNamespace('/dmx-output'))

# Emit DMX data whenever Art-Net is updated
def broadcast_dmx_data(universe, channels):
    socketio.emit('dmx_data', {
        'universe': universe,
        'channels': list(channels)
    }, namespace='/dmx-output')
```

## Performance

**Current Stats (8 fixtures):**
- FPS: 60
- Draw Calls: ~20
- Memory: ~50MB

**Optimization Tips:**
- Disable beams for >50 fixtures
- Reduce shadow map resolution
- Use LOD for distant fixtures
- Limit update rate to 30fps

## Next Steps

### Phase 6: UI Integration (3-4h)
- [ ] Embed in `frontend/dmx.html`
- [ ] Sync with DMX patcher
- [ ] Load patched fixtures automatically
- [ ] DMX value inspector on hover

### Phase 7: Performance (1-2h)
- [ ] Frustum culling
- [ ] LOD system
- [ ] WebGL instancing for LED strips
- [ ] Frame rate limiter

### Advanced Features (Optional)
- [ ] Haze/fog effects
- [ ] Stage model import (GLTF)
- [ ] Multiple venues
- [ ] Light spill & shadows
- [ ] Projection mapping preview

## Dependencies

All dependencies loaded from CDN:
- Three.js r160
- OrbitControls
- EffectComposer (for future post-processing)

No build step required - just open in browser!

## Browser Requirements

- Modern browser with WebGL 2.0 support
- Chrome 56+, Firefox 51+, Safari 15+, Edge 79+
- Recommended: Chrome for best performance

## Credits

- Three.js: https://threejs.org/
- Open Fixture Library: https://open-fixture-library.org/
- Inspired by QLC+ Web Access

## License

Part of Py_artnet project
