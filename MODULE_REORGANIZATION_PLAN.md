# 🗂️ Module Reorganization Plan - Clear Hierarchy

**Generated:** February 13, 2026  
**Goal:** Transform flat module structure into logical, maintainable hierarchy  
**Estimated Time:** 6-10 hours (with testing)

---

## 🎯 **DESIGN PRINCIPLES**

1. **Group by Domain** - Related functionality together
2. **Clear Naming** - Module name = what it does
3. **Shallow Hierarchy** - Max 2-3 levels deep
4. **Single Responsibility** - Each module has one clear purpose
5. **Import Simplicity** - Easy to find and import

---

## 📊 **CURRENT STATE** (Problems)

```
src/modules/
├── api_artnet_effects.py          # API prefix = 20+ files
├── api_benchmark.py
├── api_bpm.py
├── api_clip_layers.py
├── api_config.py
├── api_console.py
├── api_converter.py
├── api_debug.py
├── api_effects.py
├── api_files.py
├── api_layers.py
├── api_logs.py
├── api_outputs.py
├── api_player_unified.py
├── api_playlists.py
├── api_plugins.py
├── api_points.py
├── api_projects.py
├── api_routes.py
├── api_sequences.py
├── api_session.py
├── api_transitions.py
├── api_webrtc.py
├── artnet_manager.py              # Old Art-Net system
├── artnet_routing/                # New Art-Net system (9 modules)
├── audio_engine.py
├── audio_sequencer.py
├── audio_timeline.py
├── cli_handler.py
├── clip_registry.py
├── command_executor.py
├── config_schema.py
├── constants.py
├── default_effects.py
├── dmx_controller.py
├── frame_source.py
├── layer.py
├── logger.py
├── outputs/                       # Video outputs (2 modules)
├── player/                        # Player subsystem (4 modules)
├── player_core.py                 # Why both player/ and player_core.py?
├── player_lock.py
├── player_manager.py
├── playlist_manager.py
├── plugin_manager.py
├── points_loader.py
├── replay_manager.py
├── rest_api.py
├── routes.py
├── sequences/                     # Sequence system (6 modules)
├── session/                       # Session system (exists!)
├── session_state.py               # Why both session/ and session_state.py?
├── thumbnail_generator.py
├── uid_registry.py
├── utils.py
├── validator.py
├── video_converter.py
├── webrtc_track.py
└── ... (60+ total files)
```

**Problems:**
- ❌ 20+ `api_*.py` files - should be grouped
- ❌ Duplicate patterns: `player/` + `player_core.py`, `session/` + `session_state.py`
- ❌ Inconsistent naming: Some folders, some not
- ❌ Mixed concerns: Utils, constants scattered
- ❌ Flat namespace pollution

---

## ✨ **PROPOSED STRUCTURE** (Solution)

```
src/modules/
├── api/                          # 🌐 REST API Layer
│   ├── __init__.py
│   ├── app.py                    # Flask app + main routes (was: rest_api.py)
│   ├── middleware.py             # CORS, error handlers
│   │
│   ├── player/                   # Player-related endpoints
│   │   ├── __init__.py
│   │   ├── playback.py           # Play/pause/stop (was: api_player_unified.py)
│   │   ├── clips.py              # Clip management (was: api_clip_layers.py)
│   │   ├── layers.py             # Layer operations (was: api_layers.py)
│   │   ├── effects.py            # Effect management (was: api_effects.py)
│   │   ├── transitions.py        # Transition config (was: api_transitions.py)
│   │   └── playlists.py          # Playlist CRUD (was: api_playlists.py)
│   │
│   ├── content/                  # Content management endpoints
│   │   ├── __init__.py
│   │   ├── files.py              # File browser (was: api_files.py)
│   │   ├── converter.py          # Video converter (was: api_converter.py)
│   │   ├── plugins.py            # Plugin management (was: api_plugins.py)
│   │   └── projects.py           # Project save/load (was: api_projects.py)
│   │
│   ├── output/                   # Output-related endpoints
│   │   ├── __init__.py
│   │   ├── artnet.py             # Art-Net config (was: api_routes.py artnet section)
│   │   ├── routing.py            # Output routing (was: api_outputs.py)
│   │   └── points.py             # Points management (was: api_points.py)
│   │
│   ├── system/                   # System/config endpoints
│   │   ├── __init__.py
│   │   ├── config.py             # Config management (was: api_config.py)
│   │   ├── session.py            # Session state (was: api_session.py)
│   │   ├── debug.py              # Debug endpoints (was: api_debug.py)
│   │   ├── logs.py               # Log viewing (was: api_logs.py)
│   │   ├── console.py            # Console output (was: api_console.py)
│   │   └── benchmark.py          # Performance tests (was: api_benchmark.py)
│   │
│   └── audio/                    # Audio-related endpoints
│       ├── __init__.py
│       ├── bpm.py                # BPM detection (was: api_bpm.py)
│       ├── sequences.py          # Sequences (was: api_sequences.py)
│       └── webrtc.py             # WebRTC streaming (was: api_webrtc.py)
│
├── artnet/                       # 🎨 Art-Net Output System
│   ├── __init__.py
│   ├── manager.py                # DEPRECATED: Old system (was: artnet_manager.py)
│   │
│   ├── routing/                  # New routing-based system
│   │   ├── __init__.py
│   │   ├── manager.py            # Main routing manager
│   │   ├── bridge.py             # Player integration
│   │   ├── objects.py            # ArtNet objects (was: artnet_object.py)
│   │   ├── outputs.py            # ArtNet outputs (was: artnet_output.py)
│   │   ├── sender.py             # Network sender (was: artnet_sender.py)
│   │   ├── pixel_sampler.py      # Canvas sampling
│   │   ├── point_generator.py    # Point distribution
│   │   ├── color_correction.py   # Color transforms
│   │   ├── rgb_mapper.py         # Channel mapping (was: rgb_format_mapper.py)
│   │   └── output_manager.py     # Output management
│   │
│   └── dmx/                      # DMX Input Control
│       ├── __init__.py
│       └── controller.py         # DMX listener (was: dmx_controller.py)
│
├── player/                       # 🎬 Video Player System
│   ├── __init__.py
│   ├── core.py                   # Main Player class (was: player_core.py)
│   ├── manager.py                # PlayerManager (was: player_manager.py)
│   ├── lock.py                   # Thread locking (was: player_lock.py)
│   │
│   ├── sources/                  # Frame sources
│   │   ├── __init__.py
│   │   ├── base.py               # Base classes (from frame_source.py)
│   │   ├── video.py              # VideoSource
│   │   ├── generator.py          # GeneratorSource
│   │   └── dummy.py              # DummySource
│   │
│   ├── layers/                   # Layer system
│   │   ├── __init__.py
│   │   ├── layer.py              # Layer class (was: layer.py)
│   │   └── manager.py            # LayerManager (from player/layer_manager.py)
│   │
│   ├── effects/                  # Effect system
│   │   ├── __init__.py
│   │   ├── defaults.py           # Default effects (was: default_effects.py)
│   │   └── registry.py           # Effect registry
│   │
│   ├── clips/                    # Clip management
│   │   ├── __init__.py
│   │   ├── registry.py           # ClipRegistry (was: clip_registry.py)
│   │   └── uid_registry.py       # UID management (was: uid_registry.py)
│   │
│   ├── playlists/                # Playlist system
│   │   ├── __init__.py
│   │   ├── manager.py            # Multi-playlist (was: playlist_manager.py)
│   │   └── player_playlist.py    # Per-player (from player/playlist_manager.py)
│   │
│   ├── transitions/              # Transition system
│   │   ├── __init__.py
│   │   └── manager.py            # TransitionManager (from player/transition_manager.py)
│   │
│   ├── recording/                # Recording system
│   │   ├── __init__.py
│   │   ├── manager.py            # RecordingManager (from player/recording_manager.py)
│   │   └── replay.py             # ReplayManager (was: replay_manager.py)
│   │
│   └── outputs/                  # Video output system
│       ├── __init__.py
│       ├── manager.py            # OutputManager (from outputs/output_manager.py)
│       ├── display.py            # Window outputs (from outputs/display_output.py)
│       └── slices.py             # SliceManager (from outputs/slice_manager.py)
│
├── session/                      # 💾 Session & State Management
│   ├── __init__.py
│   ├── state.py                  # SessionStateManager (was: session_state.py)
│   ├── save.py                   # Save operations (extract from session/)
│   ├── load.py                   # Load operations (extract from session/)
│   ├── restore.py                # Restore snapshots (extract from session/)
│   └── validator.py              # State validation (was: validator.py)
│
├── audio/                        # 🎵 Audio Processing
│   ├── __init__.py
│   ├── engine.py                 # Audio engine (was: audio_engine.py)
│   ├── sequencer.py              # Audio sequencer (was: audio_sequencer.py)
│   ├── timeline.py               # Timeline (was: audio_timeline.py)
│   │
│   └── sequences/                # Parameter sequences
│       ├── __init__.py
│       ├── manager.py            # SequenceManager (from sequences/sequence_manager.py)
│       ├── base.py               # BaseSequence (from sequences/base_sequence.py)
│       ├── analyzer.py           # AudioAnalyzer (from sequences/audio_analyzer.py)
│       ├── audio.py              # AudioSequence (from sequences/audio_sequence.py)
│       ├── lfo.py                # LFOSequence (from sequences/lfo_sequence.py)
│       ├── bpm.py                # BPMSequence (from sequences/bpm_sequence.py)
│       └── timeline.py           # TimelineSequence (from sequences/timeline_sequence.py)
│
├── content/                      # 📁 Content Management
│   ├── __init__.py
│   ├── points.py                 # Points loader (was: points_loader.py)
│   ├── thumbnails.py             # Thumbnail gen (was: thumbnail_generator.py)
│   ├── converter.py              # Video converter (was: video_converter.py)
│   └── webrtc_track.py           # WebRTC tracks (was: webrtc_track.py)
│
├── plugins/                      # 🔌 Plugin System
│   ├── __init__.py
│   └── manager.py                # PluginManager (was: plugin_manager.py)
│
├── cli/                          # 💻 Command Line Interface
│   ├── __init__.py
│   ├── handler.py                # CLI handler (was: cli_handler.py)
│   └── commands.py               # Command executor (was: command_executor.py)
│
├── core/                         # 🔧 Core Utilities
│   ├── __init__.py
│   ├── constants.py              # Global constants (was: constants.py)
│   ├── logger.py                 # Logging system (was: logger.py)
│   ├── config.py                 # Config schema (was: config_schema.py)
│   └── utils.py                  # Utilities (was: utils.py)
│
└── __init__.py                   # Module exports
```

---

## 📋 **MIGRATION CHECKLIST**

### **Phase 0: Preparation** (30min)
- [ ] Create feature branch: `git checkout -b refactor/module-reorganization`
- [ ] Run full test suite to establish baseline
- [ ] Commit current state
- [ ] Create backup: `Copy-Item -Recurse src src.backup`

### **Phase 1: API Reorganization** (2-3h)
Consolidate 23 `api_*.py` files into structured hierarchy.

**Steps:**
1. Create directory structure:
   ```powershell
   New-Item -ItemType Directory -Path "src/modules/api/player"
   New-Item -ItemType Directory -Path "src/modules/api/content"
   New-Item -ItemType Directory -Path "src/modules/api/output"
   New-Item -ItemType Directory -Path "src/modules/api/system"
   New-Item -ItemType Directory -Path "src/modules/api/audio"
   ```

2. Move and rename files:
   ```powershell
   # Player endpoints
   Move-Item "src/modules/api_player_unified.py" "src/modules/api/player/playback.py"
   Move-Item "src/modules/api_clip_layers.py" "src/modules/api/player/clips.py"
   Move-Item "src/modules/api_layers.py" "src/modules/api/player/layers.py"
   Move-Item "src/modules/api_effects.py" "src/modules/api/player/effects.py"
   Move-Item "src/modules/api_transitions.py" "src/modules/api/player/transitions.py"
   Move-Item "src/modules/api_playlists.py" "src/modules/api/player/playlists.py"
   
   # Content endpoints
   Move-Item "src/modules/api_files.py" "src/modules/api/content/files.py"
   Move-Item "src/modules/api_converter.py" "src/modules/api/content/converter.py"
   Move-Item "src/modules/api_plugins.py" "src/modules/api/content/plugins.py"
   Move-Item "src/modules/api_projects.py" "src/modules/api/content/projects.py"
   
   # Output endpoints
   Move-Item "src/modules/api_outputs.py" "src/modules/api/output/routing.py"
   Move-Item "src/modules/api_points.py" "src/modules/api/output/points.py"
   
   # System endpoints
   Move-Item "src/modules/api_config.py" "src/modules/api/system/config.py"
   Move-Item "src/modules/api_session.py" "src/modules/api/system/session.py"
   Move-Item "src/modules/api_debug.py" "src/modules/api/system/debug.py"
   Move-Item "src/modules/api_logs.py" "src/modules/api/system/logs.py"
   Move-Item "src/modules/api_console.py" "src/modules/api/system/console.py"
   Move-Item "src/modules/api_benchmark.py" "src/modules/api/system/benchmark.py"
   
   # Audio endpoints
   Move-Item "src/modules/api_bpm.py" "src/modules/api/audio/bpm.py"
   Move-Item "src/modules/api_sequences.py" "src/modules/api/audio/sequences.py"
   Move-Item "src/modules/api_webrtc.py" "src/modules/api/audio/webrtc.py"
   
   # Main API files
   Move-Item "src/modules/rest_api.py" "src/modules/api/app.py"
   Move-Item "src/modules/routes.py" "src/modules/api/routes.py"  # Temporary, merge later
   ```

3. Create `__init__.py` files:
   ```python
   # src/modules/api/__init__.py
   """REST API Layer - All HTTP endpoints"""
   from .app import RestAPI
   
   # src/modules/api/player/__init__.py
   """Player control endpoints"""
   
   # ... etc for each subdirectory
   ```

4. Update imports in moved files:
   ```python
   # OLD: from modules.logger import get_logger
   # NEW: from modules.core.logger import get_logger
   
   # OLD: from modules.player_manager import PlayerManager
   # NEW: from modules.player.manager import PlayerManager
   ```

5. Update main.py imports:
   ```python
   # OLD: from modules import RestAPI
   # NEW: from modules.api import RestAPI
   ```

6. Test: Start server, test all API endpoints

### **Phase 2: Art-Net Consolidation** (1-2h)
Organize Art-Net into clear hierarchy.

**Steps:**
1. Create structure:
   ```powershell
   New-Item -ItemType Directory -Path "src/modules/artnet"
   New-Item -ItemType Directory -Path "src/modules/artnet/routing"
   New-Item -ItemType Directory -Path "src/modules/artnet/dmx"
   ```

2. Move files:
   ```powershell
   Move-Item "src/modules/artnet_manager.py" "src/modules/artnet/manager.py"
   Move-Item "src/modules/artnet_routing/*" "src/modules/artnet/routing/"
   Move-Item "src/modules/dmx_controller.py" "src/modules/artnet/dmx/controller.py"
   ```

3. Update imports throughout codebase

4. Test: Art-Net output, DMX input

### **Phase 3: Player Reorganization** (2-3h)
Consolidate player subsystems.

**Steps:**
1. Create clean structure (player/ already exists, enhance it)
2. Move scattered player files into player/
3. Organize by subsystem (sources, layers, clips, etc.)
4. Update all imports
5. Test: Video playback, layers, effects

### **Phase 4: Session & Core Utilities** (1-2h)
Clean up session management and core utils.

**Steps:**
1. Enhance session/ directory
2. Create core/ for shared utilities
3. Move logger, config, constants, utils
4. Update all imports
5. Test: Session save/load

### **Phase 5: Remaining Modules** (1h)
Audio, content, plugins, CLI.

**Steps:**
1. Create audio/, content/, plugins/, cli/ directories
2. Move respective files
3. Update imports
4. Test each subsystem

---

## 🔄 **IMPORT PATH CHANGES**

### Before:
```python
from modules import RestAPI, PlayerManager, DMXController
from modules.logger import get_logger
from modules.artnet_manager import ArtNetManager
from modules.player_core import Player
from modules.clip_registry import get_clip_registry
from modules.session_state import SessionStateManager
```

### After:
```python
from modules.api import RestAPI
from modules.player import PlayerManager, Player
from modules.artnet.dmx import DMXController
from modules.artnet import ArtNetManager  # or artnet.routing.manager
from modules.core import get_logger
from modules.player.clips import get_clip_registry
from modules.session import SessionStateManager
```

**Much clearer!** Each import tells you the domain.

---

## 🎯 **BENEFITS**

### Developer Experience
- ✅ **Find files faster** - Know exactly where to look
- ✅ **Understand structure** - Clear domains and responsibilities
- ✅ **Easier onboarding** - New devs understand layout immediately
- ✅ **Better IDE support** - Autocomplete works better with hierarchy

### Maintenance
- ✅ **Reduce cognitive load** - Less overwhelming than 60 flat files
- ✅ **Clear boundaries** - Separation of concerns enforced by structure
- ✅ **Easier refactoring** - Move entire domains without breaking others
- ✅ **Better testing** - Test by domain (all API tests, all player tests, etc.)

### Code Quality
- ✅ **Prevent god modules** - Hard to have 1000-line files when organized
- ✅ **Encourage modularity** - Natural to split when in subdirectories
- ✅ **Explicit dependencies** - Import paths show coupling
- ✅ **Namespace clarity** - No more `api_` prefix pollution

---

## ⚠️ **RISKS & MITIGATION**

### Risk 1: Breaking All Imports
**Mitigation:**
- Use search-replace for common patterns
- Test after each phase, not at the end
- Keep old structure side-by-side initially (can rollback)

### Risk 2: Circular Dependencies Exposed
**Mitigation:**
- This is actually GOOD - exposes bad coupling
- Fix circular imports as you find them
- Use dependency injection where needed

### Risk 3: Time-Consuming
**Mitigation:**
- Can do incrementally (one phase at a time)
- Each phase is independently valuable
- Can stop and resume anytime

---

## 🚀 **EXECUTION STRATEGY**

### Option A: Big Bang (6-10h continuous)
- Do all phases in one session
- Fastest but highest risk
- Best if you can test thoroughly at end

### Option B: Incremental (2h per phase, spread over days)
- One phase per day
- Lower risk, can test between phases
- Easier to fit into schedule

### Option C: Hybrid (Recommended)
- Phase 1 (API) first - biggest win (2-3h)
- Test thoroughly
- Then do Phases 2-4 together (4-5h)
- Phase 5 last if time permits (1h)

---

## ✅ **TESTING CHECKLIST**

After each phase:
- [ ] Application starts without import errors
- [ ] API endpoints respond (test in browser/Postman)
- [ ] Video player works (play/pause/stop)
- [ ] Art-Net output works (test pattern)
- [ ] Session save/load works
- [ ] No Python errors in logs
- [ ] Frontend still connects to backend
- [ ] Run pytest if you have tests

---

## 📖 **ADDITIONAL BENEFITS**

### Future Features
With this structure, adding features is clearer:
- New API endpoint? → Know exactly where: `api/player/` or `api/output/`
- New Art-Net feature? → Goes in `artnet/routing/`
- New player feature? → Clear subsystem: `player/layers/` or `player/clips/`

### Documentation
Can generate docs per domain:
- `docs/api/` - API documentation
- `docs/player/` - Player system docs
- `docs/artnet/` - Art-Net system docs

### Team Development
Multiple devs can work without conflicts:
- Dev A: Working on `api/player/`
- Dev B: Working on `artnet/routing/`
- No file collisions!

---

## 🤔 **QUESTIONS FOR YOU**

Before we start, confirm:

1. **Naming preferences:**
   - `api/` vs `web/` vs `http/`?
   - `artnet/` vs `art_net/` vs `output/artnet/`?
   - `player/` vs `video/` vs `playback/`?

2. **Migration strategy:**
   - Big bang or incremental?
   - Which phase should we start with?

3. **Testing:**
   - Do you have automated tests?
   - How do you currently test the application?

4. **Backward compatibility:**
   - Need to support old import paths temporarily?
   - Or clean break is OK?

---

## 🎬 **READY TO START?**

**Recommended First Step:** Phase 1 (API Reorganization)
- Biggest immediate impact
- Reduces 23 files to organized structure
- Easiest to test (just API endpoints)
- 2-3 hours well spent

**Should I:**
1. Generate the PowerShell script to do Phase 1 moves?
2. Start with import updates in main.py?
3. Create all `__init__.py` files first?
4. Something else?

Let me know and we'll execute together! 🚀
