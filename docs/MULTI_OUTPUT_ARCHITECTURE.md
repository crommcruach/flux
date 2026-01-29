# Multi-Output Player Architecture

## Overview

**Status:** ✅ Foundation implemented (rudimentary output routing)  
**Next Step:** Complete redesign for N-output parameter-based system  
**Complexity:** High  
**Estimated Time:** 74-112 hours  
**Priority:** P5 - Architecture Redesign

---

## Storage Strategy

### Config.json (Persistent)
**Output Definitions** - Hardware/infrastructure configuration that rarely changes:
```json
{
  "outputs": [
    {
      "id": "main_screen",
      "type": "video",
      "enabled": true,
      "device": "HDMI-1",
      "resolution": {"width": 1920, "height": 1080},
      "fps": 60
    },
    {
      "id": "preview",
      "type": "preview",
      "resolution": {"width": 640, "height": 360},
      "fps": 30
    }
  ],
  "routing": {
    "_comment": "Default routing - used on startup",
    "playlist_video": ["main_screen", "preview"],
    "playlist_artnet": ["led_matrix"]
  }
}
```

### Session State (Runtime)
**Active Routing** - Current session routing (can differ from config defaults):
```json
{
  "output_routing": {
    "playlist_video": ["main_screen"],
    "playlist_artnet": ["led_matrix", "preview_artnet"]
  },
  "output_states": {
    "main_screen": {"active": true, "last_frame_time": 1234567890},
    "preview": {"active": false}
  }
}
```

**Rationale:**
- **Config** = "What outputs exist" (persistent, survives restart)
- **Session** = "Which outputs are currently active and their routing" (runtime, reset on restart)
- User can change routing during session without modifying config
- Next startup uses config defaults, not last session state

---

## Implementation Philosophy

**Direct N-Output Implementation** - Since we don't need backwards compatibility, we'll implement the full N-output system from the start. This means:

- Preview is just another output (no special case)
- Per-playlist outputs are native from day one
- Output management via dedicated UI (`output-settings.html`)
- Clean architecture without technical debt

**Why not start simple?** Implementing "preview + single output" first would require the same foundation (Output base class, OutputManager) but force us to refactor when adding multiple outputs. Going straight to N-outputs is actually simpler.

---

## Problem Statement

**Current Limitations:**
```python
# Current: Hardcoded single players
video_player = VideoPlayer(config)     # One video output
artnet_player = ArtNetPlayer(config)   # One Art-Net output
preview = ???                           # No dedicated preview player
```

Current single-player architecture (video_player, artnet_player) limits scalability. We need a flexible system where multiple outputs can be controlled independently and routed to different screens/devices.

---

## Proposed Architecture

```python
# Future: N outputs with flexible routing
output_manager = OutputManager([
    Output(id="main_screen", type="video", device="HDMI-1", resolution=(1920,1080)),
    Output(id="preview", type="video", device="virtual", resolution=(640,360)),
    Output(id="artnet_1", type="artnet", target_ip="10.0.0.50", universes=[0-10]),
    Output(id="artnet_2", type="artnet", target_ip="10.0.1.50", universes=[11-20]),
    Output(id="sdi_out", type="video", device="BlackmagicSDI", resolution=(1920,1080)),
])
```

---

## Implementation Plan

### 1. Output Manager Core (~20-30h)

**Features:**
- [ ] **Output Base Class (4-6h)**
  ```python
  class Output:
      def __init__(self, id, type, config):
          self.id = id
          self.type = type  # "video", "artnet", "ndi", "sdi"
          self.config = config
          self.active = False
          self.resolution = config.get('resolution')
          self.fps = config.get('fps', 30)
      
      def render_frame(self, frame_data):
          raise NotImplementedError
      
      def start(self):
          pass
      
      def stop(self):
          pass
  ```

- [ ] **Output Types (8-12h)**
  - VideoOutput: Screen/monitor rendering
  - ArtNetOutput: DMX/LED matrix
  - PreviewOutput: Lightweight preview
  - NDIOutput: Network Device Interface
  - SDIOutput: Professional video interface
  - VirtualOutput: Memory buffer (testing/recording)

- [ ] **Output Manager (6-8h)**
  - Register/unregister outputs
  - Route playlists to specific outputs
  - Broadcast frame to multiple outputs
  - Per-output frame processing
  - Resource management (GPU contexts, etc.)

- [ ] **Configuration Schema (2-4h)**
  ```json
  {
    "outputs": [
      {
        "id": "main_screen",
        "type": "video",
        "enabled": true,
        "device": "HDMI-1",
        "resolution": {"width": 1920, "height": 1080},
        "fps": 60,
        "vsync": true
      },
      {
        "id": "preview",
        "type": "preview",
        "enabled": true,
        "resolution": {"width": 640, "height": 360},
        "fps": 30,
        "parent_output": "main_screen"
      },
      {
        "id": "led_matrix",
        "type": "artnet",
        "enabled": true,
        "target_ip": "10.0.0.50",
        "universes": [0, 1, 2, 3, 4, 5],
        "points_file": "data/punkte_export.json"
      }
    ],
    "routing": {
      "playlist_video": ["main_screen", "preview"],
      "playlist_artnet": ["led_matrix"],
      "generator_overlay": ["main_screen"]
    }
  }
  ```

---

### 2. Playlist-to-Output Routing (~15-20h)

**Features:**
- [ ] **Dynamic Routing (6-8h)**
  - Map any playlist to any output(s)
  - One-to-many: Single playlist → multiple outputs
  - Many-to-one: Multiple playlists → single output (compositing)
  - Route changes without restart

- [ ] **Output Chains (4-6h)**
  - Pipeline: Playlist → Effects → Output 1, Output 2, ...
  - Per-output effects: Different effects per output
  - Output groups: Control multiple outputs as one

- [ ] **UI Integration (5-6h)**
  - **Output Settings Page** (`output-settings.html`):
    - Manage all outputs (add/edit/delete)
    - Configure output properties (resolution, FPS, device)
    - Visual routing matrix (drag playlist to outputs)
    - Live output preview thumbnails
    - Output status indicators (active/inactive)
  - **Playlist Integration**:
    - Output selector dropdown on each playlist
    - Quick routing toggles
    - Current routing indicators

**Example Use Cases:**
```
Use Case 1: Main + Preview
├─ Playlist Video → Main Screen (1920x1080)
└─ Playlist Video → Preview Panel (640x360)

Use Case 2: Multi-LED Setup
├─ Playlist ArtNet → LED Matrix 1 (10.0.0.50)
├─ Playlist ArtNet → LED Matrix 2 (10.0.1.50)
└─ Playlist ArtNet → LED Matrix 3 (10.0.2.50)

Use Case 3: Complex Routing
├─ Playlist 1 → Main Screen + NDI Stream
├─ Playlist 2 → Preview + SDI Output
└─ Generator → Overlay on Main Screen
```

---

### 3. Preview System Integration (~12-16h)

**Features:**
- [ ] **Dedicated Preview Output (4-6h)**
  - PreviewOutput class (lightweight)
  - Lower resolution, capped FPS
  - No DMX/Art-Net output
  - Independent from main players

- [ ] **Non-Active Playlist Preview (6-8h)**
  - Preview clips from non-active playlists
  - Floating preview panel (see [NON_ACTIVE_PLAYLIST_PREVIEW.md](NON_ACTIVE_PLAYLIST_PREVIEW.md))
  - Frame streaming via WebSocket
  - Auto-cleanup after inactivity

- [ ] **Multi-Preview Support (2-4h)**
  - Preview multiple clips simultaneously
  - Picture-in-picture layouts
  - Grid view (4/9/16 previews)

---

### 4. Multi-Screen Support (~16-24h)

**Features:**
- [ ] **Screen Discovery (4-6h)**
  - Detect connected monitors/displays
  - Screen enumeration API
  - Resolution and refresh rate detection
  - Primary/secondary screen identification

- [ ] **Window Management (6-10h)**
  - Fullscreen on specific monitor
  - Borderless window mode
  - Per-screen vsync control
  - Screen switching without restart

- [ ] **GPU Context Management (4-6h)**
  - Multi-GPU support
  - Shared OpenGL contexts
  - Resource allocation per screen
  - Performance optimization

- [ ] **UI Controls (2-4h)**
  - Screen selector in settings
  - "Move to Screen X" button
  - Display topology visualization

---

### 5. Advanced Output Types (~16-20h)

**Features:**
- [ ] **NDI Output (6-8h)**
  - Network Device Interface support
  - Low-latency video streaming
  - NDI discovery and registration
  - Audio + video synchronization

- [ ] **SDI Output (4-6h)**
  - Blackmagic DeckLink support
  - Professional broadcast output
  - Genlock synchronization
  - Timecode embedding

- [ ] **Virtual Output (2-3h)**
  - Memory buffer output
  - Recording/capture support
  - Testing and debugging

- [ ] **Syphon/Spout (4-5h)**
  - macOS Syphon server
  - Windows Spout server
  - Share output with other apps

---

### 6. Testing & Validation (~6-10h)

**Test Matrix:**
- [ ] Single output (baseline)
- [ ] Dual output (main + preview)
- [ ] Triple output (video + artnet + preview)
- [ ] Output switching (runtime changes)
- [ ] Resource cleanup (output destruction)
- [ ] Performance benchmarks
- [ ] Error recovery (output failure)
- [ ] Config validation

**Performance Targets:**
- Single output: <2ms frame time
- Dual output: <4ms frame time
- Triple output: <6ms frame time
- Output switch: <100ms
- Memory overhead: <50MB per output

---

## API Design

### Output Management
```python
GET    /api/outputs                    # List all outputs
POST   /api/outputs                    # Create new output
PUT    /api/outputs/{id}               # Update output config
DELETE /api/outputs/{id}               # Remove output
POST   /api/outputs/{id}/start         # Start output
POST   /api/outputs/{id}/stop          # Stop output

GET    /api/outputs/types              # List available output types
GET    /api/outputs/devices            # List available devices
```

### Routing Management
```python
GET    /api/routing                    # Get current routing config
POST   /api/routing/playlist/{id}      # Set playlist output routing
DELETE /api/routing/playlist/{id}      # Clear playlist routing

POST   /api/routing/link               # Link playlist to output(s)
    {
        "playlist_id": "video",
        "output_ids": ["main_screen", "preview"]
    }
```

---

## File Structure

```
src/
├── modules/
│   ├── output_manager.py          # Output manager core
│   ├── outputs/
│   │   ├── base.py                # Output base class
│   │   ├── video_output.py        # Video/screen output
│   │   ├── artnet_output.py       # Art-Net/DMX output
│   │   ├── preview_output.py      # Preview output
│   │   ├── ndi_output.py          # NDI output
│   │   ├── sdi_output.py          # SDI output
│   │   └── virtual_output.py      # Virtual/buffer output
│   └── routing.py                 # Routing logic

frontend/
├── output-settings.html           # Output management UI
├── js/
│   └── output-settings.js         # Output management logic
└── css/
    └── output-settings.css        # Output UI styling
```

---

## Benefits

### Flexibility
- Add/remove outputs dynamically
- Route any playlist to any output
- Multiple outputs simultaneously

### Scalability
- Support N outputs (limited only by hardware)
- Independent resolution/fps per output
- Distributed rendering possible

### Integration
- **Preview is just another output** - No special handling needed
- Per-playlist preview outputs (view multiple playlists simultaneously)
- NDI/SDI for professional workflows
- Virtual outputs for streaming/recording

### Maintainability
- Clean separation of concerns
- Easy to add new output types
- Unified API for all outputs

---

## Related Documentation
- [NON_ACTIVE_PLAYLIST_PREVIEW.md](NON_ACTIVE_PLAYLIST_PREVIEW.md) - Preview system architecture
- [OUTPUT_BACKEND_IMPLEMENTATION_PLAN.md](OUTPUT_BACKEND_IMPLEMENTATION_PLAN.md) - Output abstraction details
- [MULTI_VIDEO_RENDER_CLUSTER.md](MULTI_VIDEO_RENDER_CLUSTER.md) - Distributed rendering
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization

---

## Timeline

**Phase 1-2: Core + Routing** (35-50h)
- Months 1-2: Foundation

**Phase 3-4: Preview + Multi-Screen** (28-40h)
- Month 3: User-facing features

**Phase 5-6: Advanced + Testing** (22-30h)
- Month 4: Polish and validation

**Total: 85-120 hours** (estimated 3-4 months part-time)

---

*Last Updated: January 29, 2026*
