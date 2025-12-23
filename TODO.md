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

## 🔥 P1 - CRITICAL FEATURES (~28-40h)

### 1.1 🎵 Audio-Driven Sequencer (~12-16h) 🔥 TOP PRIORITY

**Why Critical:** Music-synced visual shows are core VJ functionality. Without this, users must manually trigger clips.

**Concept:**
```
Audio Waveform Timeline
├─ User clicks waveform → create split point
├─ Time Slots (segments between splits)
│  └─ Slot 0: 0.0-2.5s  → Clip 0
│  └─ Slot 1: 2.5-4.0s  → Clip 1
│  └─ Slot 2: 4.0-7.2s  → Clip 2
├─ Backend audio playback (miniaudio)
└─ Drives Master playlist → Slaves follow
```

**Implementation:**
- [ ] **Phase 1: Backend Audio (3-4h)**
  - `AudioTimeline` class: load audio, extract waveform, manage splits
  - `AudioSequencer`: miniaudio playback, 50ms monitoring loop
  - REST API: `/api/sequencer/*` (load, play, pause, stop, split management)
  
- [ ] **Phase 2: Frontend Waveform (4-5h)**
  - WaveSurfer.js v7+ integration (RegionsPlugin, TimelinePlugin)
  - Click to add splits, right-click to remove
  - Slot visualization with clip mapping
  - Playback controls & current slot highlighting
  
- [ ] **Phase 3: Master Integration (3-4h)**
  - Audio position triggers `master_advance_to_clip(slot_index)`
  - Transport `loop_count` controls loops within slots
  - Slot boundary detection with 50ms precision
  
- [ ] **Phase 4: UI Polish (2-3h)**
  - Visual feedback, beat markers (optional)
  - Export/import timeline JSON
  - Info display: current time, slot, BPM

**Key Decisions:**
- ✅ Backend audio playback (miniaudio) - runs headless
- ✅ WaveSurfer.js - battle-tested waveform library
- ✅ 50ms monitoring loop - responsive without CPU overhead

**Dependencies:** miniaudio (`pip install miniaudio`)

---

### 1.2 🎹 MIDI Control (~6-10h) 🔥

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

### 1.3 🎛️ Dynamic Parameter Sequences (~6-10h) 🔥

**Why Critical:** Automated parameter modulation creates dynamic, evolving visuals without manual control.

**Architecture Decision:** ⚠️ **Audio detection MUST run in backend** (not frontend) for headless operation and reliability.

**Sequence Types:**
- [ ] **Audio Reactive (2-3h)**
  - **Backend audio analysis:** sounddevice + numpy FFT (runs without browser)
  - **Audio source selection:** Configurable in config.json (microphone, line-in, system audio/speaker loopback)
  - Bind parameter to audio feature (RMS, Peak, Bass, Mid, Treble, BPM)
  - Range mapping: Audio level (0-1) → Parameter range
  - Smoothing: Attack/Release for smooth transitions
  - Real-time analysis in monitoring thread (similar to AudioSequencer)
  
- [ ] **LFO - Low Frequency Oscillator (2-3h)**
  - Waveforms: Sine, Triangle, Square, Sawtooth, Random
  - Frequency (Hz) & Amplitude control
  - Phase offset for multi-LFO sync
  
- [ ] **Timeline Keyframes (2-3h)**
  - Time → Value pairs with interpolation
  - Linear, Bezier, Step curves
  - Loop modes: Once, Loop, Ping-Pong
  
- [ ] **ADSR Envelope (1-2h, optional)**
  - Attack, Decay, Sustain, Release phases
  - Trigger modes: On-Load, On-Beat, Manual

**UI Components:**
- Sequence button (⚙️) next to each parameter
- Modal editor with type selector
- Live preview showing modulated value
- Visual waveform/curve display

**Use Cases:**
- Blur pulsing with bass
- Color cycling with LFO
- Brightness envelope on beat drops
- Timeline-based color shifts for precise timing

---

### 1.4 🔍 File Browser Thumbnails & Multi-Select (~8-14h) 🎯

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

### 2.1 🎵 Audio-Reactive Effects (~10-14h) ⚡

**Why High Value:** Real-time audio analysis enables reactive visuals that respond to music dynamics.

**Architecture:** ⚠️ **Backend audio analysis** (headless, no frontend dependency)

**Features:**
- [ ] **Backend Audio Input (4h)**
  - Microphone input via sounddevice (backend thread)
  - System audio capture (WASAPI Loopback on Windows)
  - Device selection API + UI
  - Runs independently of browser
  
- [ ] **Backend Audio Analysis Engine (3-4h)**
  - Real-time FFT in backend thread: Bass/Mid/Treble frequency bands
  - BPM detection & tempo tracking (librosa or custom)
  - Onset detection (beat triggers)
  - RMS/Peak level calculation
  - Analysis results cached and exposed via API
  
- [ ] **Parameter Binding System (3h)**
  - Backend applies modulation to effect parameters
  - Brightness ← RMS/Peak level
  - Speed ← BPM
  - Color ← Frequency mapping
  - Effect intensity ← Audio level
  - WebSocket broadcasts analysis data for UI visualization
  
- [ ] **UI & Visualization (2-3h)**
  - Live spectrum display (receives data via WebSocket)
  - Parameter mapping editor
  - Sensitivity controls
  - Device selection dropdown

**Implementation:**
```python
# Backend: src/modules/audio_analyzer.py
class AudioAnalyzer:
    def __init__(self):
        self.device = sounddevice.InputStream(callback=self._audio_callback)
        self.fft_buffer = []
        self.current_features = {
            'rms': 0.0,
            'bass': 0.0,
            'mid': 0.0,
            'treble': 0.0,
            'bpm': 0.0
        }
    
    def _audio_callback(self, indata, frames, time, status):
        # FFT analysis in audio thread
        # Update self.current_features
        pass
    
    def get_features(self):
        return self.current_features
```

**Dependencies:** sounddevice, numpy, librosa (optional for BPM)

---

### 2.2 🖥️ Multi-Network Adapter Support (~4-6h) ⚡

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

### 2.4 🎬 Playlist Slots with Compositing (~12-16h) ⚡

**Why High Value:** Professional show structure with stacked alternatives and live compositing.

**Concept:** "Card Deck" UI
```
Slot 1: [Intro Variations] 🎴
  ├─ Clip A (base)          blend: normal    opacity: 100%
  ├─ Clip B (overlay)       blend: multiply  opacity: 50%
  └─ Clip C (generator)     blend: screen    opacity: 70%
  → All play simultaneously, composited in real-time

Slot 2: [Drop Section] → Transition (fade 1.5s) → Slot 3
```

**Implementation:**
- [ ] **Slot Manager (3-4h)**
  - Slot data structure with multi-clip support
  - Trigger modes: Manual, Auto, Random, MIDI
  - Transition between slots
  
- [ ] **Layer Compositor (3-4h)**
  - Real-time compositing within slot
  - Blend modes per clip
  - Opacity per clip
  - Layer order via drag & drop
  
- [ ] **UI Components (4-5h)**
  - Card deck view (collapsed/expanded)
  - Slot controls (play, name, duration)
  - Clip stacking with visual feedback
  - Transition settings
  
- [ ] **API Integration (2-3h)**
  - REST endpoints: Slot CRUD, clip management
  - Trigger API for external control

---

### 2.4 🔮 ShaderToy Source (~8-12h) ⚡

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

### 2.6 📹 Enhanced Live Sources (~8-12h) ⚡

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

### 2.7 📡 SPOUT/NDI Input Plugin (~6-10h) ⚡

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

## 🎯 P3 - ENHANCEMENT FEATURES (~30-42h)

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

### 3.1.5 🎨 New Generator Plugins (~10-14h) 🎯

**Why Enhancement:** Expand procedural graphics library with geometric and noise-based patterns.

**Geometric Generators (4-6h):**
- [ ] **Lines Generator (1h)**
  - Horizontal/Vertical/Diagonal lines
  - Line width, spacing, angle
  - Color per line or gradient
  
- [ ] **Circles Generator (1-2h)**
  - Concentric circles or grid pattern
  - Circle size, spacing, fill/stroke
  - Animated pulsing/rotation
  
- [ ] **Static Color Generator (0.5h)**
  - Single solid color output
  - RGB color picker
  - Useful for testing/backgrounds

**Math/Noise Generators (4-6h):**
- [ ] **Sine Wave Generator (1h)**
  - 2D sine wave patterns
  - Frequency, amplitude, phase controls
  - Horizontal/vertical/radial modes
  
- [ ] **Noise Generator (2-3h)**
  - Perlin/Simplex noise
  - Fractal noise (multiple octaves)
  - Animated noise scrolling
  - Scale, octaves, persistence controls
  
- [ ] **Fractals Generator (2-3h)**
  - Sierpiński Triangle
  - Sierpiński Carpet (Quadrat)
  - Hexagonal fractals
  - Koch snowflake
  - Recursion depth control
  - Color schemes

**Implementation Notes:**
- All generators use existing GeneratorSource base class
- 30s default duration (configurable 1-60s)
- Real-time parameter updates
- Compatible with Transport plugin

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

### 3.2.5 ❄️ New Effect Plugins (~8-12h) 🎯

**Why Enhancement:** Creative visual effects for unique looks.

**Visual Effects (5-7h):**
- [ ] **Snow Effect (2-3h)**
  - Falling snowflake particles
  - Parameters: density, speed, size variation
  - Wind direction (horizontal drift)
  - Accumulation effect (optional)
  - Depth layers (parallax)
  
- [ ] **ASCII Art Effect (3-4h)**
  - Convert video to ASCII characters
  - Character set: full/limited/custom
  - Font size and color
  - Invert option (black/white)
  - Edge detection mode (Sobel filter)
  - Preview with monospace font rendering

**Oscillator Effects (3-5h):**
- [ ] **Oscillator Effect Plugin (3-5h)**
  - Modulate parameters with waveforms
  - Waveform types:
    - Sine (smooth oscillation)
    - Square (on/off switching)
    - Sawtooth (ramp up/down)
    - Triangle (linear up/down)
    - Random (stepped noise)
  - Parameters:
    - Frequency (Hz): 0.01-10Hz
    - Amplitude (range): 0-100%
    - Phase offset: 0-360°
    - Target parameter selection
  - Use cases:
    - Pulsing brightness
    - Color cycling
    - Transform wobble
    - Speed modulation

**Implementation:**
- Snow: Particle system with physics
- ASCII: Pillow for text rendering, numpy for luminance
- Oscillator: Time-based waveform calculation, applied to parameter values

**Dependencies:** numpy (ASCII edge detection)

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
  - `projection-mapper.html` page
  - Live preview with warping
  - Test pattern generator
  - Export/import setups

**Use Cases:**
- Building facade mapping
- Theater & stage projections
- Museum installations
- Immersive 360° projections

---

## 📊 Summary by Priority

| Priority | Total Hours | Focus | ROI |
|----------|-------------|-------|-----|
| **P1 - Critical** | 30-44h | Audio sequencer, MIDI, parameter sequences, thumbnails + multi-select | Very High |
| **P2 - High Value** | 62-92h | Audio reactive, output routing, SPOUT/NDI, enhanced sources, multi-network, slots, shaders | High |
| **P3 - Enhancement** | 60-86h | Video slicing, new generators (Lines, Circles, Noise, Fractals), new effects (Snow, ASCII, Oscillator), GUI polish, dynamic config | Medium |
| **P4 - Advanced** | 60-90h | Render cluster, projection mapping | Low (specialized) |
| **TOTAL** | **212-312h** | | |

---

## 🎯 Recommended Implementation Order

### Phase 1: Core Workflow (P1) - 30-44h 🔥
1. **Audio-Driven Sequencer** (12-16h) ← START HERE
   - Enables music-synced shows
   - Foundation for audio-reactive features
   
2. **MIDI Control** (6-10h)
   - Hardware control for live performance
   - Essential for professional VJs
   
3. **Dynamic Parameter Sequences** (6-10h)
   - Automated modulation
   - Creates evolving visuals
   
4. **File Browser Thumbnails & Multi-Select** (8-14h)
   - Visual browsing + batch operations
   - Multi-select: Add multiple clips/layers at once
   - Dramatically speeds up workflow

**Outcome:** Production-ready VJ system with audio sync and hardware control

---

### Phase 2: Power Features (P2) - 62-92h ⚡
1. **Audio-Reactive Effects** (10-14h)
2. **Output Routing System** (6-10h) ← NEW: HDMI, Virtual, SPOUT
3. **Enhanced Live Sources** (8-12h) ← NEW: Better Camera, Screen Capture, YouTube
4. **SPOUT/NDI Input Plugin** (6-10h) ← NEW: Pro video routing
5. **Multi-Network Adapter** (4-6h)
6. **Playlist Slots with Compositing** (12-16h)
7. **ShaderToy Source** (8-12h)

**Outcome:** Professional feature set with reactive visuals, flexible I/O, and procedural graphics

---

### Phase 3: Polish & Scale (P3) - 60-86h 🎯
1. **Video Wall Slicing** (8-12h)
2. **New Generator Plugins** (10-14h) ← NEW: Lines, Circles, Sine, Noise, Fractals
3. **New Effect Plugins** (8-12h) ← NEW: Snow, ASCII, Oscillator
4. **GUI Optimizations** (12-18h)
5. **Dynamic Playlists** (8-12h)
6. **Testing & Docs** (6-8h)

**Outcome:** Production-polished with expanded creative toolkit and improved UX

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
- `pip install miniaudio` - Audio sequencer
- `pip install python-rtmidi` - MIDI control
- `pip install sounddevice numpy` - Audio reactive
- `pip install moderngl` - ShaderToy source
- `pip install Pillow` - Thumbnail generation & ASCII effect
- `pip install yt-dlp` - YouTube metadata extraction
- `pip install pyvirtualcam` - Virtual camera output
- `pip install SpoutGL` - SPOUT input/output (Windows)
- `pip install ndi-python` - NDI input/output (cross-platform)

**Breaking Changes:**
- None planned for P1-P3
- P4 features are additive (optional)

**New Features Summary (December 10, 2025):**
- ✨ Output Routing: HDMI, Virtual outputs, SPOUT/NDI
- ✨ Enhanced Sources: Improved Camera, Screen Capture, YouTube with duration
- ✨ SPOUT/NDI Input: Professional video routing from external apps
- ✨ New Generators: Lines, Circles, Static Color, Sine Wave, Noise (Fractal), Fractals (Sierpiński, etc.)
- ✨ New Effects: Snow particle system, ASCII art conversion, Oscillator modulation

---

*Last Updated: December 10, 2025*
