# Py_artnet - TODO Liste

> **Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.4)**

## 🚀 Roadmap Overview

**Current Status (v2.4.0 - December 2025):**
- ✅ Unified API & Plugin System
- ✅ Multi-layer compositing with blend modes  
- ✅ Master/Slave playlist synchronization
- ✅ Transport plugin for all sources (video + generators)
- ✅ WebSocket preview streaming (<100ms latency)
- ✅ Generator duration defaults (30s)
- ✅ HAP codec support & universal video converter
- ✅ Transition system with fade effects
- ✅ 18 effect plugins (color, time, motion, blur, blending)

**Priority Levels:**
- 🔥 **P1 - Critical** (28-40h): Core features for professional VJ workflow
- ⚡ **P2 - High Value** (32-46h): Features that unlock major use cases
- 🎯 **P3 - Enhancement** (30-42h): Quality of life & polish
- 🔬 **P4 - Advanced** (60-90h): Complex features for specialized setups

---

## 🔥 P1 - CRITICAL FEATURES (~6-10h)

### 1.1 🎹 MIDI Control (~6-10h) 🔥

**Why Critical:** External hardware control is essential for live performance. Enables physical faders, buttons, and pad controllers.

**Features:**
- [ ] **MIDI Device Support (3-4h)**
  - python-rtmidi integration
  - Device discovery & selection UI
  - MIDI message parsing (Note On/Off, CC, Program Change)
  
- [ ] **MIDI Learn System (2-3h)**
  - Click parameter → next MIDI input binds
  - Persistent mapping storage (config.json)
  - Visual feedback when mapped
  
- [ ] **Advanced Mapping (1-2h)**
  - Curve types: Linear, Exponential, Logarithmic
  - Range mapping: MIDI 0-127 → Parameter min-max
  - Multi-controller support (multiple devices simultaneously)
  
- [ ] **Feedback System (1h, optional)**
  - Send LED status back to controller
  - Motorized fader sync

**API Endpoints:**
- `GET /api/midi/devices` - List available MIDI devices
- `POST /api/midi/learn` - Enable learn mode for parameter
- `GET /api/midi/mappings` - Get all mappings
- `DELETE /api/midi/mappings/{id}` - Remove mapping

**Dependencies:** python-rtmidi (`pip install python-rtmidi`)

---

## ⚡ P2 - HIGH VALUE FEATURES (~90-137h)

### 2.1 🖥️ Multi-Network Adapter Support (~4-6h) ⚡

**Why High Priority:** Visual file browsing and batch operations dramatically speed up workflow.

**Implementation:**
- [ ] **Thumbnail Generation (3-4h)**
  - Videos: First frame via FFmpeg
  - Images: Resized preview via Pillow
  - Cache system: `data/thumbnails/`
  - Lazy loading: Generate on-demand
  
- [ ] **UI Integration (2-3h)**
  - Toggle: Enable/Disable thumbnails
  - List view: 50x50px thumbnails
  - Hover popup: 200x200px preview
  - Loading spinner during generation
  
- [ ] **Multi-Select Modal (3-5h)** ✨ NEW
  - Checkbox selection mode (Ctrl+Click, Shift+Click for range)
  - Select all / Deselect all buttons
  - Selected count indicator (e.g., "12 files selected")
  - Batch actions toolbar:
    - **Add to Playlist** - Add all selected clips sequentially
    - **Add as Layers** - Stack selected clips as layers on current clip
    - **Add to Slot** - Add to specific playlist slot (if slots implemented)
    - **Generate Thumbnails** - Batch thumbnail generation
    - **Delete** - Batch file deletion (with confirmation)
  - Visual feedback: Selected items highlighted with border/background
  - Keyboard shortcuts: Ctrl+A (select all), Escape (cancel selection)
  - Drag & drop multiple selected files
  
- [ ] **Performance (1-2h)**
  - Thumbnail size: 100x100px JPEG (85% quality)
  - Max generation time: 500ms per file
  - Batch generation API endpoint
  - Cache cleanup: Delete old thumbnails after 30 days

**API:**
- `POST /api/files/thumbnails/generate` - Batch generate
- `GET /api/files/thumbnails/{path}` - Get thumbnail
- `POST /api/player/{id}/clips/batch` - Add multiple clips at once
- `POST /api/player/{id}/clips/{clip_id}/layers/batch` - Add multiple layers

**Use Cases:**
- Add 10 video clips to playlist in one action
- Create multi-layer composition from multiple files
- Batch thumbnail generation for large video libraries
- Quickly build complex layer stacks (e.g., base + 5 overlays)

---

## ⚡ P2 - HIGH VALUE FEATURES (~32-46h)

### 2.1 🖥️ Multi-Network Adapter Support (~4-6h) ⚡

**Why High Value:** Separates control traffic from Art-Net output, essential for large installations.

**Features:**
- [ ] **Network Interface Discovery (1-2h)**
  - List all available network adapters
  - Show IP, subnet, status
  
- [ ] **Routing Configuration (2-3h)**
  - API binding: Select adapter for REST API
  - Art-Net routing: Assign universes to specific adapters
  - Multi-Art-Net: Multiple Art-Net networks in parallel
  
- [ ] **Failover (1h, optional)**
  - Automatic switch to backup adapter
  - Health monitoring

**Config Example:**
```json
{
  "network": {
    "api": {"bind_address": "192.168.1.10", "port": 5000},
    "artnet": {
      "adapters": [
        {"interface": "10.0.0.50", "universes": [1,2,3,4,5]},
        {"interface": "10.0.1.50", "universes": [6,7,8,9,10]}
      ]
    }
  }
}
```

---

### 2.3 🖥️ Output Routing System (~6-10h) ⚡

**Why High Value:** Enables flexible output to HDMI displays, virtual outputs (OBS, vMix), and multiple screens simultaneously.

**Features:**
- [ ] **Output Targets (3-4h)**
  - HDMI/DisplayPort output selection
  - Virtual output (named pipes, shared memory)
  - Virtual camera device (OBS Virtual Camera compatible)
  - Multiple simultaneous outputs
  
- [ ] **Output Configuration (2-3h)**
  - Per-player output routing
  - Resolution & refresh rate per output
  - Fullscreen/windowed modes
  - Output preview in UI
  
- [ ] **Virtual Output Integrations (2-3h)**
  - OBS Studio integration (Browser Source)
  - vMix NDI output
  - Spout/Syphon (Windows/Mac)
  - Virtual webcam driver

**Config Example:**
```json
{
  "outputs": [
    {"id": "hdmi_1", "type": "display", "screen": 1, "fullscreen": true},
    {"id": "obs", "type": "virtual", "method": "shared_memory", "resolution": "1920x1080"},
    {"id": "spout", "type": "spout", "name": "PyArtnet_Out"}
  ]
}
```

**Dependencies:** pyvirtualcam (virtual camera), SpoutGL (Windows Spout)

---

### 2.3 🔮 ShaderToy Source (~8-12h) ⚡

**Why High Value:** Unlimited procedural graphics via GLSL shaders.

**Features:**
- [ ] **ModernGL Integration (4-6h)**
  - OpenGL context management
  - GLSL shader compilation
  - Texture binding & uniforms
  
- [ ] **ShaderToy Compatibility (2-3h)**
  - iTime, iResolution, iMouse uniforms
  - Texture channels (iChannel0-3)
  - Multi-pass rendering
  
- [ ] **Shader Library (2-3h)**
  - Load shaders from files
  - Built-in shader collection
  - UI: Shader selector with preview

**Dependencies:** moderngl, PyOpenGL

---

### 2.4 📹 Enhanced Live Sources (~8-12h) ⚡

**Why High Value:** Professional live input with better control and metadata.

**Features:**
- [ ] **Camera Source Improvements (3-4h)**
  - Device enumeration with friendly names
  - Resolution/FPS selection
  - Auto-reconnect on device disconnect
  - Multiple camera instances
  - Camera settings UI (brightness, contrast, etc.)
  
- [ ] **Screen Capture Enhancements (2-3h)**
  - Multi-monitor selection
  - Window-specific capture (by title/process)
  - Region capture (x, y, width, height)
  - Cursor toggle
  - FPS limiter for performance
  
- [ ] **YouTube Source Improvements (3-4h)**
  - Duration detection via yt-dlp metadata
  - Thumbnail extraction
  - Quality selection (360p, 720p, 1080p)
  - Transport support (trim, speed, reverse)
  - Playlist URL support (auto-load videos)
  - Live stream support

**API Updates:**
- `GET /api/sources/cameras` - List camera devices
- `GET /api/sources/youtube/info?url=...` - Get video metadata
- `GET /api/sources/screens` - List screens/windows

**Dependencies:** yt-dlp (YouTube metadata)

---

### 2.5 📡 SPOUT/NDI Input Plugin (~6-10h) ⚡

**Why High Value:** Professional video routing from other applications (Resolume, TouchDesigner, vMix, etc.).

**Features:**
- [ ] **SPOUT Input (Windows) (3-4h)**
  - List available SPOUT senders
  - Receive SPOUT texture stream
  - Auto-reconnect on sender restart
  - Multiple SPOUT inputs simultaneously
  
- [ ] **NDI Input (Cross-platform) (3-4h)**
  - NDI source discovery
  - Receive NDI video stream
  - Audio support (optional)
  - Low-latency mode
  
- [ ] **UI Integration (1-2h)**
  - Source selector dropdown
  - Connection status indicator
  - Refresh button for source list

**Config Example:**
```json
{
  "source_type": "spout",
  "spout_sender": "Resolume_Output",
  "fps": 30
}
```

**Dependencies:** SpoutGL (SPOUT), ndi-python (NDI)

---

### 2.6 🎭 DMX Lighting Control System (~48-70h) ⚡ 💡 **USP FEATURE**

**Why High Value:** Unified video + lighting control in one system. Competes with Resolume Arena ($699) at a fraction of the cost.

**Output Method:** Art-Net (existing infrastructure) → DMX via hardware converters

**Architecture:**
```
DMX Sequence Engine
├─ Fixture Library (moving heads, LED pars, scanners, strobes)
├─ Fixture Patching (DMX address, universe assignment)
├─ Scene/Sequence Editor (timeline-based cues)
└─ Art-Net Output (reuse existing ArtNetPlayer)
```

**Fixture Library:** ✨ **Open Fixture Library (OFL)** - https://open-fixture-library.org/
- 1500+ professional fixture definitions (Martin, Chauvet, ADJ, Elation, Robe, etc.)
- REST API for search & download
- MIT License - free commercial use
- Constantly updated by community

**Features:**
- [ ] **Phase 1: Fixture Library & Patching (6-10h)** ⬇️ *Reduced time - using OFL!*
  - **OFL Integration (2-3h)**:
    - Search fixtures via OFL API: `GET https://open-fixture-library.org/api/v1/fixtures`
    - Download fixture definitions: `GET /api/v1/fixtures/{manufacturer}/{fixture-key}`
    - Local cache in `data/dmx_fixtures/` (avoid repeated downloads)
    - Convert OFL JSON → internal format
    - Fixture browser UI with search (similar to file browser)
  - **Fixture Patching UI (4-7h)**:
    - Search & add fixtures from OFL catalog
    - Assign DMX address (1-512)
    - Assign Universe (1-32768)
    - Select fixture mode (different channel counts)
    - Multi-fixture patching (auto-increment addresses)
    - Fixture groups (all moving heads, all PARs)
    - **Patch Grid View** - Visual grid showing all patched fixtures with addresses
    - **2D Stage Layout** - Position fixtures on stage plan (top-down view):
      - Drag fixtures to physical positions
      - Stage dimensions (width × depth in meters)
      - Export/import stage layouts
      - Visual reference for programming
    - **LED Strip Integration** ✨ NEW (2-3h):
      - Import existing LED strip configurations from Art-Net player
      - Create "LED Strip" fixture type (custom fixture profile)
      - Map LED strip universe/channels to DMX control
      - Position LED strips on 3D stage layout
      - Treat strips as addressable pixel fixtures
      - Control via DMX sequences/FX engines
      - Unified control: Video effects + DMX control
  - **Movement Limits (2-3h)**:
    - Per-fixture pan/tilt limits (prevent fixture collisions)
    - Per-channel range limits (e.g., gobo wheel: only slots 1-5)
    - Safety zones (avoid audience, rigging, walls)
    - Invert pan/tilt per fixture
  - Storage: `data/dmx_patched_fixtures.json` (user's patched fixtures)
  
- [ ] **Phase 2: Scene Editor with Steps & FX (10-14h)**
  - **Static Scenes**:
    - Set fixture parameters (pan: 127, tilt: 200, color: red, dimmer: 255)
    - Save as named scene ("Intro Look", "Drop Red", "Chase Blue")
    - Recall scene via UI or API
  - **Multi-Step Scenes** ✨ NEW:
    - Scene with multiple steps (Step 1 → Step 2 → Step 3)
    - Per-step timing (hold duration, fade time)
    - Step triggers: Auto-advance, manual, beat-synced
    - Loop steps or run once
  - **Scene FX Layers** ✨ NEW:
    - Apply FX engine to scene parameters
    - FX override static values (e.g., static red + color chase FX)
    - Multiple FX per scene (dimmer chase + color cycle)
  - Scene list UI (similar to playlist UI)
  - Quick scene recall buttons
  - Scene fading (crossfade duration)
  
- [ ] **Phase 3: FX Engines (12-18h)** ✨ NEW
  - **Colour FX Engine (2-3h)**:
    - RGB/CMY color cycling
    - Rainbow effect
    - Color bounce (2 colors alternating)
    - Color fade (smooth transitions)
    - Speed control (BPM-synced or free-running)
  
  - **Chaser FX Engine (2-3h)**:
    - Step sequencer for any parameter
    - Define s5eps with values & timing
    - Direction: Forward, Backward, Bounce, Random
    - Apply to: Dimmer, Shutter, Color wheel, Gobo wheel
    - Beat-synced or time-based
  
  - **Movement FX Engine (2-3h)**:
    - Pan/Tilt patterns: Circle, Figure-8, Square, Triangle, Random
    - Size control (degrees of movement)
    - Speed & direction
    - Offset per fixture (staggered movements)
    - Shape presets library
  
  - **Value FX Engine (1-2h)**:
    - Sine wave oscillation for any channel
    - Square wave (on/off pulsing)
    - Sawtooth (ramp up/down)
    - Random stepped values
    - Min/max range, frequency
  
  - **Curve FX Engine (2-3h)**:
    - Custom envelope curves (ADSR-style)
    - Draw curve in UI (timeline with handles)
    - Apply to any parameter
    - Loop or one-shot
    - Use cases: Dimmer fade curves, color transitions
  
  - **Mapping FX (2-3h)** ✨ ADVANCED:
    - **Value Mapping**: Map input range → output range
      - Audio level (0-1) → Dimmer (50-255)
      - BPM (60-180) → Speed (10-100)
    - **Colour Mapping**: Map external data to colors
      - Frequency bands → RGB values
      - Temperature data → Color temperature
      - Custom lookup tables
    - Bind external sources: Audio, MIDI, OSC, API
  
  - **FX Stack System**:
    - Apply multiple FX to same fixture/channel
    - Priority system (which FX wins on conflicts)
    - FX groups (apply to fixture group)
    - Enable/disable FX layers
  
- [ ] **Phase 4: DMX Sequence Timeline (12-16h)**
  - Timeline editor (new page: `dmx.html`):
    - Time-based keyframe editor
    - Per-fixture parameter tracks
    - Interpolation types (linear, step, ease)
    - Loop modes (once, loop, ping-pong)
  - Movement presets:
    - Circle (pan/tilt)
    - Figure-8
    - Sweep (left-right, up-down)
    - Bounce
    - Random
  - Color chase presets:
    - RGB cycle
    - Rainbow
    - Strobe patterns
  - BPM-synced movements (beat-aligned keyframes)
  - Export/import sequences (JSON)
  
- [ ] **Phase 4: DMX Effect Plugin (4-6h)**
  - New plugin: `plugins/effects/dmx_sequence.py`
  - Parameters:
    - `sequence_id`: Select DMX sequence
    - `intensity`: Master dimmer (0-100%)
    - `speed`: Playback speed multiplier (0.1-10x)
    - `trigger_mode`: 
      - `continuous` - Always playing
      - `on_beat` - Advance on BPM beat
      - `on_clip_start` - Trigger when clip starts
      - `manual` - API/MIDI triggered
  - Apply to video player (lighting follows video)
  - Multiple DMX effects per player (layer sequences)
  
- [ ] **Phase 6: Integration & Sync (4-6h)**
  - Master/Slave DMX sync:
    - DMX sequences follow video master playlist
    - Sync points: Clip boundaries, beats, timeline markers
  - Audio-reactive DMX:
    - Dimmer follows audio RMS
    - Color follows frequency bands
    - Strobe on beat detection
  - MIDI triggering:
    - Recall scenes via MIDI Note On
    - Control dimmer via MIDI CC
    - Sequence playback control

**API Endpoints:**
```python
# Fixtures
GET    /api/dmx/fixtures          # List all patched fixtures
POST   /api/dmx/fixtures          # Add fixture
PUT    /api/dmx/fixtures/{id}     # Update fixture
DELETE /api/dmx/fixtures/{id}     # Remove fixture

# Scenes
GET    /api/dmx/scenes            # List all scenes
POST   /api/dmx/scenes            # Create scene
PUT    /api/dmx/scenes/{id}       # Update scene
DELETE /api/dmx/scenes/{id}       # Delete scene
POST   /api/dmx/scenes/{id}/recall # Recall scene

# Sequences
GET    /api/dmx/sequences         # List all sequences
POST   /api/dmx/sequences         # Create sequence
PUT    /api/dmx/sequences/{id}    # Update sequence
DELETE /api/dmx/sequences/{id}    # Delete sequence
POST   /api/dmx/sequences/{id}/play   # Play sequence
POST   /api/dmx/sequences/{id}/stop   # Stop sequence

# Output (reuse existing Art-Net infrastructure)
GET    /api/dmx/output/status     # DMX output status
POST   /api/dmx/output/blackout   # Emergency blackout
```

**UI Components:**
- `frontend/dmx.html` - Main DMX control page:
  - **Fixture Patcher** (left panel):
    - Fixture library browser (OFL search)
    - Patch grid view (universe/address grid)
    - 2D stage layout editor (drag fixtures on stage plan)
    - Movement limits editor
  - **Scene Manager** (center top):
    - Scene list with recall buttons
    - Step editor (multi-step scenes)
    - FX layer assignment
  - **FX Engine Panel** (center right):
    - FX type selector (Colour/Chaser/Move/Value/Curve/Mapping)
    - FX parameter controls
    - FX preview visualization
    - Apply to fixtures/groups
  - **Timeline Editor** (center bottom):
    - Keyframe-based sequence programming
    - Per-fixture parameter tracks
  - **Live Output View** (right panel):
    - Real-time DMX values (0-255)
    - 2D visualization (fixtures highlight on stage)
    - Active FX indicators
- Fixture selector in effect parameters
- Scene recall buttons in player UI
- DMX output indicator in status bar

**Data Structures:**
```json
// Patched fixture (user's installation)
{
  "id": "mh_001",
  "name": "Moving Head 1",
  "fixture_type": "dmx_fixture",  // or "led_strip"
  "ofl_manufacturer": "chauvet",
  "ofl_fixture_key": "intimidator-spot-360",
  "mode": "14-Channel",  // Selected mode from OFL definition
  "universe": 1,
  "address": 1,
  "channels": {
    // Auto-generated from OFL definition + address offset
    "pan": 1,
    "pan_fine": 2,
    "tilt": 3,
    "tilt_fine": 4,
    "color_wheel": 5,
    "gobo_wheel": 6,
    "gobo_rotation": 7,
    "prism": 8,
    "focus": 9,
    "dimmer": 10,
    "shutter": 11,
    "control": 12,
    "movement_speed": 13,
    "dimmer_mode": 14
  },
  "_ofl_cache": {
    // Cached OFL definition for offline use
    "capabilities": {...},
    "physical": {...}
  }
}

// LED Strip as DMX Fixture ✨ NEW
{
  "id": "strip_001",
  "name": "LED Strip Front Wall",
  "fixture_type": "led_strip",
  "universe": 2,
  "address": 1,
  "pixel_count": 150,
  "pixel_spacing": 0.05,  // meters between pixels
  "layout": "linear",  // or "matrix", "arc", "custom"
  "position": {"x": 0, "y": 2.5, "z": 0},  // 3D position
  "orientation": {"rotation": 0, "tilt": 0},
  "channels": {
    // 3 channels per pixel (RGB)
    "pixels": [
      {"r": 1, "g": 2, "b": 3},    // Pixel 0
      {"r": 4, "g": 5, "b": 6},    // Pixel 1
      // ... 150 pixels = 450 channels
    ]
  },
  "control_mode": "dmx",  // or "video" (from Art-Net player)
  "linked_artnet_object": "strip_front_wall"  // Reference to existing Art-Net config
}

// DMX Sequence
{
  "id": "seq_intro",
  "name": "Intro Lights",
  "duration": 30.0,
  "keyframes": [
    {
      "time": 0.0,
      "fixture_id": "mh_001",
      "values": {"pan": 127, "tilt": 127, "dimmer": 0}
    },
    {
      "time": 2.0,
      "fixture_id": "mh_001",
      "values": {"pan": 127, "tilt": 127, "dimmer": 255}
    },
    {
      "time": 5.0,
      "fixture_id": "mh_001",
      "values": {"pan": 200, "tilt": 100, "dimmer": 255}
    }
  ],
  "loop_mode": "loop"
}
```
 + FX engines, much lower cost
- ✅ **vs GrandMA onPC** (free): Similar FX engines, easier to use, integrated with video
- ✅ **vs MadMapper** ($399): More affordable, unified system with FX
- ✅ **vs QLC+** (free): Better video integration, modern UI, professional FX engines
- ✅ **vs Chamsys MagicQ** (free): Comparable FX engines, simpler workflow
- New `DMXSequenceEngine` class for sequence playback
- DMX values (0-255) map directly to Art-Net pixel values
- Each DMX universe = separate Art-Net universe
- 512 channels per universe (standard DMX limit)

**Use Cases:**
- VJ with lighting control: Video + lights synchronized
- Theater productions: Pre-programmed lighting cues
- Clubs/bars: Music-reactive lighting
- Live events: MIDI-controlled lighting scenes
- Corporate events: Professional A/V control
- **LED Strip Shows**: Video effects + DMX control on same strips
- **Unified Installation**: Video walls + moving heads + LED strips - all synchronized

**Competitive Analysis:**
- ✅ **vs Resolume Arena** ($699): Similar features, much lower cost
- ✅ **vs GrandMA onPC** (free): Easier to use, integrated with video
- ✅ **vs MadMapper** ($399): More affordable, unified system
- ✅ **vs QLC+** (free): Better video integration, modern UI

**USP:** "All-in-one VJ + Lighting control - Video, LED strips, DMX fixtures, all synchronized"

**Integration Benefits:** ✨
- **Unified Control**: Switch between video effects and DMX control on LED strips
- **Hybrid Shows**: Video content on strips + moving head effects simultaneously
- **Single Interface**: Manage everything from one system
- **3D Preview**: See LED strips + fixtures together in visualizer
- **Cross-Control**: Apply DMX FX to LED strips, video effects to traditional fixtures

**Dependencies:** 
- None for core functionality (uses existing Art-Net infrastructure)
- `requests` - For OFL API calls (already in requirements)
- **Open Fixture Library API** - https://open-fixture-library.org/ (free, no auth required)

**Implementation Notes:**
- OFL API is free, no authentication needed
- Cache fixtures locally to work offline
- Fallback: Include 10-20 most common fixtures in `data/dmx_fixtures/builtin/`
- OFL format conversion: Map OFL capabilities to simple DMX channel values (0-255)

---

### 2.7 🎭 3D DMX Visualizer (~10-17h) ⚡ 💡 **GAME CHANGER**

**Why High Value:** Real-time 3D visualization is a **massive differentiator**. Most lighting consoles require expensive add-ons ($600-$2000+) or separate software.

**Output Method:** HTML5/WebGL in browser (Three.js)

**Open Source Leverage:** 🎁
- **QLC+ Web Access** (Apache 2.0): Three.js setup, fixture rendering patterns
- **Open Fixture Library** (MIT): GLTF 3D models for fixtures
- **Proven code** from production lighting software

**Features:**
- [ ] **Phase 1: Three.js Core (1-2h)**
  - Scene, camera, renderer setup
  - Stage floor (grid with dimensions)
  - OrbitControls (pan, zoom, rotate)
  - Camera presets (top, front, side, isometric)
  
- [ ] **Phase 2: 3D Fixture Models (1-2h)** ⬇️ *Reduced - using OFL GLTF models!*
  - Load GLTF models from OFL (when available)
  - Fallback: Procedural models (inspired by QLC+):
    - Moving head: Cone beam with pivot
    - LED PAR: Cylindrical beam
    - Scanner: Mirror rotation
    - Strobe: Flash effect
    - Generic: Simple cylinder
  - **LED Strip Visualization** ✨ NEW:
    - Linear array of small spheres/cubes (one per pixel)
    - Real-time RGB color per pixel
    - Positions based on LED strip layout
    - Support for 2D matrices (grids)
    - Show actual video content on strips
  - **Display/Screen Models** ✨ NEW:
    - 3D plane objects (TVs, projector screens, LED walls)
    - Configurable size (width × height in meters)
    - Position and rotation in 3D space
    - Real-time video texture mapping
    - Multiple displays per venue
  
- [ ] **Phase 3: DMX → 3D Mapping (2-3h)**
  - Map DMX channels to 3D properties:
    - Pan/Tilt → 3D rotation (accounting for movement limits)
    - Dimmer → Beam opacity/intensity
    - RGB/CMY → Beam color
    - Gobo → Texture projection
    - Shutter → Beam on/off
    - Prism → Beam splitting
  - Use OFL fixture definitions for channel mapping
  - Calculate beam angles from fixture specs
  
- [ ] **Phase 4: Real-time Updates (1-2h)**
  - WebSocket connection to backend DMX output
  - Receive Art-Net universe data (512ch × N universes)
  - **Video stream connection** ✨ NEW:
    - Connect to video player WebSocket preview
    - Receive video frames as base64/blob
    - Update display textures in real-time
    - 10-30 fps preview (adjustable quality)
  - Update 3D scene at 30-60 fps
  - Interpolation for smooth movements
  - Only update changed fixtures (performance)
  
- [ ] **Phase 5: Visual Effects (2-3h)**
  - Light beams (volumetric lighting)
  - Bloom/glow post-processing
  - Color mixing visualization
  - Beam shapes (spot, wash, beam angle)
  - Gobo projection onto surfaces
  
- [ **Display management** ✨ NEW:
    - Add/remove displays (screens, projectors)
    - Link display to video player output
    - Adjust size, position, rotation
    - Toggle video preview on/off (performance)
  - ] **Phase 6: UI Integration (2-3h)**
  - New page: `frontend/dmx-visualizer.html`
  - Embedded view in `dmx.html` (side panel)
  - View toggles: 3D perspective, top-down, front, side
  - Show/hide fixtures
  - Stage dimensions editor
  - Fixture selection (click to highlight)
  - DMX value inspector (hover fixture)
  
- [ ] **Phase 7: Performance Optimization (1-2h)**
  - **Video texture optimization**:
    - Reduce preview resolution for performance
    - Pause video updates when display not visible
    - Compressed frame streaming
  - LOD (Level of Detail) for distant fixtures
  - Frustum culling (only render visible)
  - Update only moving fixtures
  - WebGL optimization (batching, instancing)
  - Frame rate limiter (30/60 fps toggle)

**Advanced Features (Optional +8-12h):**
- [ ] **Haze/Fog Effects (2-3h)**
  - Volumetric fog rendering
  - Beam visibility in fog
  - Adjustable fog density
  
- [ ] **Stage Import (2-3h)**
  - Import 3D models (OBJ, GLTF)
  - Custom stage designs
  - Truss structures
  - Audience areas
  
- [ ] **Multiple Venues (1-2h)**
  - Save/load venue configurations
- [ ] **Projection Mapping Preview (2-3h)** ✨ NEW
  - Import 3D building models
  - Project video onto surfaces
  - Preview projection mapping setup
  - Adjust keystone/warping in 3D view

  - Preset venues (club, theater, outdoor)
  - Copy fixtures between venues
  
- [ ] **Light Spill & Shadows (3-4h)**
  - Calculate light hitting floor/walls
POST   /api/dmx/visualizer/display  # Add display/screen to scene
PUT    /api/dmx/visualizer/display/{id} # Update display properties
DELETE /api/dmx/visualizer/display/{id} # Remove display

# Real-time data (WebSocket)
ws://localhost:5000/dmx-output      # DMX universe stream
ws://localhost:5000/video-preview   # Video frame stream for displays

**API Endpoints:**
```python
# Visualizer
GET    /api/dmx/visualizer/scene    # Get current 3D scene state
POST   /api/dmx/visualizer/venue    # Save venue configuration
GET    /api/dmx/visualizer/venue/{id} # Load venue

# Real-time data (WebSocket)
ws://localhost:5000/dmx-output      # DMX universe stream
```

**Technology Stack:**
- **Three.js** (r160+) - WebGL 3D engine (MIT License)
- **OrbitControls** - Camera navigation
- **EffectComposer** - Post-processing effects
- **GLTFLoader** - Load OFL 3D models
- **WebSocket** - Real-time DMX data

**Data Integration:**
```javascript
// Use patched fixtures from Phase 1
fixtures.forEach(fixture => {
    // 1. Load OFL 3D model (if available)
    if (fixture._ofl_cache.physical?.model3d) {
        loadGLTF(fixture._ofl_cache.physical.model3d);
    }
    

// NEW: Add displays with live video ✨
displays.forEach(display => {
    // 1. Create 3D plane (screen)
    const geometry = new THREE.PlaneGeometry(display.width, display.height);
    const material = new THREE.MeshBasicMaterial();
    const screen = new THREE.Mesh(geometry, material);
    
    // 2. Position screen
    screen.position.set(display.x, display.y, display.z);
    screen.rotation.set(display.rotX, display.rotY, display.rotZ);
    
    // 3. Video texture (real-time)
  **Display management panel** ✨ NEW:
  - Add screen/projector/LED wall
  - Link to video player
  - Adjust size, position, rotation
  - Video quality settings (resolution, fps)
- Stage grid toggle
- Beam visibility toggle
- Performance stats (FPS, fixture count, video streams
    // 4. Connect to player WebSocket
    connectVideoPreview(display.player_id, videoElement); + video preview
- ✅ **vs Capture** ($600-$2000): Free, integrated, modern UI + real-time video
- ✅ **vs WYSIWYG** ($2000+): Free, real-time, easier to use + video visualization
- ✅ **vs MagicQ Visualizer** (free): Better integration, modern WebGL + video output preview
- ✅ **vs Resolume Arena** ($699): Integrated lighting + video in one view

**USP Enhancement:** "All-in-one VJ + Lighting + 3D Visualizer - See your entire show in real-time! Video content, LED strips, and lighting - all in one 3D view
        fixture.stage_position.y
    );
    
    // 3. Update from DMX data
    updateFixtureFromDMX(fixture, dmxUniverseData);
});
```

**UI Components:**
- Main 3D viewport (fullscreen capable)
- Camera controls (orbit, pan, zoom)
- View presets (Top, Front, Side, 3D)
- Fixture selection (click to inspect DMX values)
- Stage grid toggle
- Beam visibility toggle
- Performance stats (FPS, fixture count)

**Competitive Advantage:**
- ✅ **vs MA3D** (GrandMA, $$$): Free, browser-based, no installation
- ✅ **vs Capture** ($600-$2000): Free, integrated, modern UI
- ✅ **vs WYSIWYG** ($2000+): Free, real-time, easier to use
- ✅ **vs MagicQ Visualizer** (free): Better integration, modern WebGL

**USP Enhancement:** "All-in-one VJ + Lighting + 3D Visualizer - See your entire show in real-time!"

**Dependencies:**
- Three.js (CDN: https://cdn.jsdelivr.net/npm/three@0.160.0/)
- GLTFLoader (for OFL 3D models)
- No backend dependencies (pure frontend)

**Open Source Credits:**
- QLC+ (Apache 2.0) - Inspiration for fixture rendering
- Open Fixture Library (MIT) - GLTF 3D models & fixture data
- **Video preview**: Use existing WebSocket streaming (already implemented!)
- Performance: 50+ fixtures + 4 video displays @ 60fps achievable
- Mobile support: Scale down effects, 30fps, reduce fixtures, disable video
- **Display types supported**: TV screens, projectors, LED walls, video walls
- **Use cases**: Pre-viz entire club/theater show before installation!
**Implementation Notes:**
- Start with OFL GLTF models (saves 4-6h of modeling)
- Borrow rendering patterns from QLC+ Web Access
- WebSocket reuses existing infrastructure
- Performance: 50+ fixtures @ 60fps achievable
- Mobile support: Scale down effects, 30fps, reduce fixtures

---

## 🎯 P3 - ENHANCEMENT FEATURES (~34-50h)

### 3.1 🎥 Video Wall Slicing (~8-12h) 🎯

**Why Enhancement:** Enables large-scale LED walls and multi-display setups.

**Features:**
- [ ] **Slice Configuration (3-4h)**
  - Define slice regions (x, y, width, height)
  - Grid-based slicing (e.g., 3x2 = 6 displays)
  - Custom slice areas for irregular layouts
  
- [ ] **Slice Transform Effect (2-3h)**
  - New effect plugin: `slice_transform`
  - Apply to player or layer level
  - Parameters: slice_id, offset, dimensions
  
- [ ] **Visual Slice Mapper (3-4h)**
  - HTML page: `slice-mapper.html`
  - Drag & drop grid editor
  - Live preview of all slices
  - Export/import configurations

**Config Example:**
```json
{
  "video_wall": {
    "slices": [
      {
        "id": "top_left",
        "source_rect": {"x": 0, "y": 0, "width": 60, "height": 150},
        "target": "strip_1",
        "universes": [1, 2]
      }
    ]
  }
}
```

---

### 3.2 🎨 GUI Optimizations (~12-18h) 🎯

**Why Enhancement:** Better UX and productivity improvements.

**Features:**
- [ ] **Art-Net Preview Expansion (4-6h)**
  - Live LED object visualization
  - Real-time color display (10-30 FPS)
  - Object list with universe info
  - Click pixel → show RGB value
  
- [ ] **Drag & Drop Layout Editor (4-6h)**
  - GridStack.js integration
  - Freely move & resize panels
  - LocalStorage persistence
  - Preset layouts: Standard, Video-Focus, Compact
  
- [ ] **Effect Presets (2-3h)**
  - Save/load effect parameter sets
  - Preset library per effect
  - Quick apply from dropdown
  
- [ ] **Search & Filter Improvements (2-3h)**
  - Fuzzy search for effects
  - Filter by category/tag
  - Recent/favorites lists

---

### 3.3 🎛️ Dynamic Playlists via Config (~8-12h) 🎯

**Why Enhancement:** Adds new player types without code changes.

**Features:**
- [ ] **Config Schema (2-3h)**
  - Define `playlists` array in config.json
  - Schema: {id, name, type, icon, apiBase, features}
  - Types: video, artnet, audio, dmx, osc, midi
  
- [ ] **Backend Dynamic Registration (2-3h)**
  - PlayerManager reads config.json playlists
  - Auto-register players
  - API routes dynamically generated
  
- [ ] **Frontend Dynamic UI (3-4h)**
  - Fetch player configs from API
  - Generate UI from configs
  - Dynamic icons and controls
  
- [ ] **Auto-Initialize (1-2h)**
  - Loop over configs and initialize
  - Register event listeners
  - Setup drop zones

**Config Example:**
```json
{
  "playlists": [
    {
      "id": "video",
      "name": "Video",
      "type": "video",
      "icon": "📹",
      "apiBase": "/api/player/video",
      "features": {"autoplay": true, "loop": true, "transitions": true}
    }
  ]
}
```

---

### 3.4 🧪 Testing & Documentation (~6-8h) 🎯

- [ ] **Unit Tests (3-4h)**
  - Player tests
  - FrameSource tests
  - API endpoint tests
  
- [ ] **Integration Tests (2-3h)**
  - Master/slave sync tests
  - Effect pipeline tests
  - Transition tests
  
- [ ] **Documentation (1-2h)**
  - API documentation updates
  - User guide for new features
  - Video tutorials (optional)

---

## 🔬 P4 - ADVANCED FEATURES (~60-90h)

### 4.1 🖥️ Multi-Video Render Cluster (~40-60h) 🔬

**Why Advanced:** Enterprise-scale installations with dozens of synchronized outputs.

**Architecture:**
- Master-Slave cluster with WebSocket command sync
- NTP time synchronization (±1ms accuracy)
- VSync hardware lock (<1ms jitter)
- Zero network overhead (each node renders locally)

**Features:**
- [ ] **Cluster Manager (8-12h)**
  - Node discovery (mDNS/Broadcast)
  - Health checks & auto-failover
  - Leader election
  - Status dashboard
  
- [ ] **Command Sync Engine (10-15h)**
  - WebSocket command broadcast
  - Timestamp-ordered render queue
  - Deduplication & validation
  - Retry logic
  
- [ ] **State Replication (8-12h)**
  - Full state snapshot on node join
  - Delta updates (incremental sync)
  - MVCC conflict resolution
  
- [ ] **Render Synchronization (8-12h)**
  - NTP integration
  - Frame target calculation
  - VSync lock mode
  - Drift monitoring & correction
  
- [ ] **Monitoring Dashboard (6-9h)**
  - Cluster status visualization
  - Performance metrics (FPS, sync jitter)
  - Command history & replay
  - Network topology graph

**Use Cases:**
- 16-80+ synchronized displays
- Multi-projector mapping with edge blending
- Immersive 360° environments
- Corporate campus installations

---

### 4.2 🎥 Projection Mapping (~16-24h) 🔬

**Why Advanced:** Professional installations require precise geometric correction.

**Features:**
- [ ] **Corner-Pin & Mesh Warp (3-4h)**
  - 4-point perspective correction
  - Grid-based mesh warping
  - Auto-alignment via marker detection
  
- [ ] **Edge Blending (3-4h)**
  - Soft-edge overlap between projectors
  - Brightness & color matching
  - Configurable feather width
  
- [ ] **Multi-Projector Setup (2-3h)**
  - Define overlap regions
  - Content routing per projector
  - Sync modes for stacked projectors
  
- [ ] **Projection Zones (3-4h)**
  - Multiple zones per projector
  - Different content per zone
  - Layer support with compositing
  - Alpha masks for zone boundaries
  
- [ ] **UI: Mapping Editor (4-6h)**
  - `projection-mapper.h110-162h | DMX lighting control (with FX engines)
  - Live preview with warping
  - Test pattern generator
  - Export/import60-382s

**Use Cases:**
- Building facade mapping
- Theater & stage projections
- Museum installations
- Immersive 360° projections

---

## 📊 Summary by Priority

| Priority | Total Hours | Focus | ROI |
|----------|-------------|-------|-----|
| **P1 - Critical** | 6-10h | MIDI control | High |
| **P2 - High Value** | 90-137h | DMX lighting (FX + 3D visualizer), output routing, SPOUT/NDI, enhanced sources, multi-network, shaders | Very High |
| **P3 - Enhancement** | 34-50h | Video slicing, GUI polish, dynamic config, testing | Medium |
| **P4 - Advanced** | 60-90h | Render cluster, projection mapping | Low (specialized) |
| **TOTAL** | **190-287h** | | |

---

## 🎯 Recommended Implementation Order

### Phase 1: Professional Control (P1) - 6-10h 🔥
1. **MIDI Control** (6-10h) ← START HERE
   - Hardware control for live performance
   - Essential for professional VJs
   - MIDI Learn system for rapid setup

**Outcome:** External hardware control unlocked

---

### Phase 2: Power Features (P2) - 90-137h ⚡
1. **DMX Lighting Control System** (48-70h) ← 💡 **MAJOR USP** - Pro lighting with FX engines!
2. **3D DMX Visualizer** (10-17h) ← 🎭 **GAME CHANGER** - Real-time 3D visualization!
3. **Output Routing System** (6-10h) - HDMI, Virtual outputs, SPOUT
4. **Enhanced Live Sources** (8-12h) - Better Camera, Screen Capture, YouTube
5. **SPOUT/NDI Input Plugin** (6-10h) - Pro video routing
6. **Multi-Network Adapter** (4-6h) - Separate control/output networks
7. **ShaderToy Source** (8-12h) - GLSL procedural graphics

**Outcome:** Professional feature set with lighting control, flexible I/O, and procedural graphics

---

### Phase 3: Polish & Scale (P3) - 34-50h 🎯
1. **Video Wall Slicing** (8-12h) - Large LED wall support
2. **GUI Optimizations** (12-18h) - Better UX, Art-Net preview, layouts
3. **Dynamic Playlists** (8-12h) - Config-driven player types
4. **Testing & Docs** (6-8h) - Quality assurance

**Outcome:** Production-polished with improved UX and scalability

---

### Phase 4: Enterprise (P4) - 60-90h 🔬
1. **Multi-Video Render Cluster** (40-60h)
2. **Projection Mapping** (16-24h)

**Outcome:** Enterprise-grade installations and complex setups

---

## 📝 Notes

**Completed in v2.4.0:**
- ✅ Unified playlist system (Video + Art-Net)
- ✅ Master/Slave synchronization
- ✅ Transport plugin for generators
- ✅ WebSocket preview streaming
- ✅ Generator duration defaults
- ✅ Multi-layer compositing
- ✅ HAP codec support
- ✅ Transition system

**Dependencies to Install:**
- `pip install python-rtmidi` - MIDI control
- `pip install moderngl` - ShaderToy source
- `pip install yt-dlp` - YouTube metadata extraction
- `pip install pyvirtualcam` - Virtual camera output
- `pip install SpoutGL` - SPOUT input/output (Windows)
- `pip install ndi-python` - NDI input/output (cross-platform)

**Breaking Changes:**
- None planned for P1-P3
- P4 features are additive (optional)

**Completed Features (v2.4.0):**
- ✅ Dynamic Parameter Sequences (Audio, LFO, Timeline, BPM)
- ✅ Audio-reactive modulation with backend analysis
- ✅ BPM detection and beat synchronization

---

*Last Updated: December 30, 2025*
