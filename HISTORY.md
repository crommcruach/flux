# Py_artnet - Version History

## v2.4 - Transport Enhancements & Generator Improvements (2025-12-08)

### v2.4.0 - Transport Plugin for Generators & Duration Defaults (2025-12-08)
- ✓ **Transport Plugin for Generators** - Unified playback control across all source types
  - Removed frontend blocking checks in player.js (lines 2813-2816, 2877-2883)
  - Removed backend generator skip check in transport.py (lines 370-376)
  - Generators now show transport effect in UI with full functionality
  - Transport speed, reverse, trim, playback modes now work with generators
  - Result: Unified playback architecture for videos AND generators
- ✓ **Generator Duration Defaults Changed** - No infinite generation, practical defaults
  - Default duration: 30 seconds (changed from 10s)
  - Min duration: 1 second (no infinite generation)
  - Max duration: 60 seconds
  - Updated generators: checkerboard, fire, plasma, pulse, rainbow_wave, matrix_rain, static_picture
  - GeneratorSource backend defaults to 30s instead of 0s (infinite)
  - Live sources (webcam, screencapture, livestream) remain continuous (no duration limit)
- ✓ **Transport Loop Count Feature** - Precise loop control for timing
  - Added `loop_count` parameter (0=infinite, 1+=exact loops)
  - Added `random_frame_count` parameter for random mode timing
  - Internal loop iteration tracking (`_current_loop_iteration`)
  - Signals completion after N loops for playlist autoplay
  - Works with all playback modes (bounce, random)
  - Enables precise master/slave timing control
- ✓ **Transport Playback Mode Cleanup** - Simplified modes
  - Removed `repeat` and `play_once` modes
  - Kept `bounce` and `random` modes
  - Default changed to `bounce` (more interesting than repeat)
  - loop_count parameter replaces play_once functionality
- ✓ **Timeline Slider Fix** - Correct display for short clips
  - Fixed max range calculation for clips <1 second
  - Added fallback: `total_frames = max(out_point, 100)` when total_frames is None
  - Ensures slider handles display correctly even for 20-frame clips
- ✓ **WebSocket Resource Leak Fixes** - Improved stability
  - Added URL cleanup: `pendingUrls` Set tracks and revokes all blob URLs
  - Image object reuse: Single `frameImage` reused instead of creating new each frame
  - Connection debouncing: `isConnecting` flag prevents connection spam
  - Idempotent disconnect: Safe to call multiple times, handles KeyError race conditions
  - Stale stream cleanup: Periodic cleanup of dead threads
  - Connection limits: `max_concurrent_streams` config (default 10)
  - Enhanced ping settings: Faster dead connection detection
- ✓ **Generator Playback Control Removal** - Simplified architecture
  - Removed speed, reverse, playback_mode from GeneratorSource
  - Removed all playback mode logic from get_next_frame()
  - Simplified to time-based frame tracking: `virtual_frame % total_frames`
  - Transport plugin now handles all playback control for generators
  - Removed legacy playback UI from frontend (speed/reverse/mode sliders)
  - ~150 lines of code removed from backend and frontend
- ✓ **Seamless Generator Looping** - Frame wrapping works correctly
- ✓ **Master/Slave Playlist Synchronization** - Multi-output synchronized playback
  - Master/Slave toggle UI in playlist headers (👑 master indicator)
  - Only one playlist can be master (toggle switches others to slave)
  - Event-based synchronization: Master emits `clip_changed`, slaves react
  - Initial sync: All slaves jump to master clip index when master activated
  - Edge case handling: Slaves with fewer clips stop (black screen), master deactivation makes slaves autonomous
  - Backend: `PlayerManager` with master/slave state management
  - API: `set_master_playlist()`, `sync_slaves_to_master()`, `on_clip_changed()` observer pattern
  - REST endpoints: `POST /api/player/{id}/set_master`, `GET /api/player/sync_status`
  - Frontend: Master toggle button, visual feedback (green/gold master, grey slave)
  - Real-time status updates via `pollSyncStatus()`
  - Independent transitions: Slaves use their own transition settings
  - Result: Synchronized shows across multiple outputs (Video + Art-Net) with independent clip content but synchronized timing
  - Uses modulo arithmetic: `virtual_frame % total_frames`
  - Time calculation: `time = virtual_frame / fps`
  - No visual glitches when looping back to frame 0
  - Works with transport speed/reverse/trim
- ✓ **Master/Slave Auto-Loop Behavior** - Slaves automatically hold at current clip
  - Slave detection: Checks if player_manager.master_playlist is set and player is not master
  - When clip ends (frame=None): Slaves loop current clip (seek to 0) instead of advancing
  - Waits for master sync event to advance to next clip
  - Master advances independently via autoplay + transport loop_count
  - Prevents slaves from advancing out of sync with master
  - Debug logging: "🔄 Slave mode: Looping current clip"
- ✓ **Documentation Added** - Architecture and analysis docs
  - Created PLAYER_EXECUTION_FLOW.md - Complete system flow documentation
  - Created TRANSPORT_MASTER_SLAVE_ANALYSIS.md - Master/slave timing analysis
  - Documents WebSocket latency, frame processing times, sync mechanisms
  - Includes loop_count feature details and use cases

**Benefits:**
- Unified playback control: Transport plugin works with videos AND generators
- Practical defaults: No infinite generation, 30s duration makes sense
- Precise timing: loop_count enables exact loop control
- Better stability: WebSocket resource leaks fixed
- Cleaner code: Removed duplicate playback control logic (~150 lines)
- Frame-perfect looping: Seamless transitions for generators

**Performance Improvements:**
- WebSocket latency: <100ms (was ~1s with WebRTC)
- Timeline slider: Works correctly for any clip length
- Generator looping: No frame skips or visual glitches
- Memory usage: Reduced blob URL leaks, connection limits enforced

**Generator Duration Support (v2.4.0):**
- ✓ Backend duration parameter in all generator plugins (checkerboard, fire, plasma, pulse, rainbow_wave, matrix_rain, static_picture)
- ✓ Default: 30s, Min: 1s, Max: 60s (practical for shows)
- ✓ GeneratorSource calculates `total_frames = fps * duration`
- ✓ Frame wrapping via modulo: `frame_index = virtual_frame % total_frames`
- ✓ Seamless looping without visual artifacts
- ✓ Transport plugin recognizes generator duration (via `source.total_frames`)
- ✓ Timeline slider shows generator duration (0-100%)
- ✓ Trim points work with generators (in/out_point in frames)
- ✓ Loop count: 0=infinite, 1+=defined number of loops
- ✓ Speed/reverse control via Transport (generators have no own speed anymore)
- ✓ Duration slider in generator settings (1s - 60s)
- ✓ Display of current duration in seconds
- ✓ Duration reset button (back to 30s)
- ✓ Live preview on duration change (generator re-initialized)
- Result: Practical show planning with defined-length generators, seamless looping, transport control works with generators, combinable with videos

**Plugin System Extensions (v2.3.x - completed 2025-12-07):**
- ✓ Layer effects via Clip FX Tab with unified API (`/api/player/{player_id}/clip/{clip_id}/effects`)
- ✓ Layer-as-Clips Architecture: Each layer has own clip_id
- ✓ Clip FX Tab shows layer effects when layer selected (via selectedLayerClipId)
- ✓ API calls automatically routed (targetClipId = selectedLayerClipId || selectedClipId)
- ✓ Drag & drop effects work for clips AND layers
- ✓ Backend: apply_layer_effects() fully integrated, Layer.effects array populated
- ✓ Live effect instances: API returns live parameters from active layer instances
- ✓ Independent layer effects: Each layer has own effect instances (Transport, Transform, etc.)
- ✓ Parameter updates: Direct updates on live layer effect instances (not registry)
- ✓ Transport plugin: Timeline detection works per layer, trim points persist
- ✓ Opacity persistence: Layer opacity maintained across transport loops
- Key fixes: API finds active layers by clip_id, transport prioritizes layer.source, no unnecessary layer reloads, timeline auto-adjusts only for default values [0,100]

---

## v2.3 - Unified API & Plugin System (2025-11-26 - 2025-12-05)

### v2.3.7 - Legacy Code Cleanup & ScriptSource Removal (2025-12-05)
- ✓ **Deprecated Trim/Reverse Functions Removed** - Transport Effect Plugin is now standard
  - Frontend cleanup: Removed ~300 lines of deprecated code from player.js
  - Functions removed: loadTrimSettings(), reloadClipSettings(), toggleTrimSection(), setupTrimRangeSliders(), updateTrimPointsFromSlider(), toggleReverse(), resetTrim()
  - Commented HTML removed: Old trim controls UI section (~30 lines)
  - trimSliderInstance variable removed
- ✓ **Deprecated Backend Modules Deleted** - 4 files removed, ~500 lines eliminated
  - api_artnet_effects_deprecated.py (163 lines) - replaced by unified player API
  - api_effects_deprecated.py (204 lines) - replaced by unified player API
  - api_clip_trim.py (244 lines) - replaced by Transport Effect Plugin
  - api_videos_deprecated.py - deprecated video API
  - rest_api.py: Removed imports and registration calls
- ✓ **Deprecated ClipRegistry Methods Removed** - Trim/reverse functionality consolidated
  - set_clip_trim() method removed (~25 lines)
  - set_clip_reverse() method removed (~20 lines)
  - get_clip_playback_info() method removed (~25 lines)
  - All trim/reverse logic now handled by Transport Effect Plugin
- ✓ **VideoSource Trim/Reverse Code Removed** - frame_source.py cleanup
  - Removed deprecated trim/reverse properties (in_point, out_point, reverse)
  - Removed ClipRegistry loading logic from __init__ (~25 lines)
  - Removed trim boundary checking from get_next_frame() (~20 lines)
  - Removed reload_trim_settings() method (~25 lines)
  - Simplified reset() method (removed trim logic)
- ✓ **Legacy API Fallbacks Removed** - Cleaner playerConfigs
  - legacyApi object removed from playerConfigs (video player)
  - play/pause/stop functions simplified (no more fallback endpoints)
  - Legacy sync comments removed (3 occurrences)
  - "MIGRATION: Convert old float IDs" comment simplified
  - "Transition State (legacy)" comment removed
- ✓ **ScriptSource Completely Removed** - ~200 lines legacy code eliminated
  - frame_source.py: ScriptSource class removed (~100 lines)
  - api_routes.py: /api/load_script endpoint → generator placeholder
  - rest_api.py: ScriptSource import & isinstance checks removed
  - rest_api.py: Console command 'script:' removed
  - cli_handler.py: _handle_load_script() → deprecation warning
  - dmx_controller.py: ScriptSource loading → warning log
  - command_executor.py: _handle_script_load() → deprecation warning
  - player.py: ScriptSource import removed, .py file layer creation removed
  - __init__.py: ScriptSource → GeneratorSource in exports
  - layer.py: ScriptSource removed from docstring
- ✓ **Deprecated Function Cleanup** - Old layer management functions removed
  - updateLayerStackVisibility() removed - replaced by clip-based layers
  - selectLayer() removed - replaced by clip-based layers
  - "TODO: Extract to separate function" comment removed
- ✓ **Total Impact** - Massive codebase cleanup
  - ~1000 lines of dead code removed
  - 4 deprecated files deleted
  - ~20 deprecated functions/methods eliminated
  - No errors introduced - all changes validated
  - Transport Effect Plugin is now the single source of truth for trim/reverse/speed control
  - GeneratorSource with generator plugins replaces all ScriptSource usage

### v2.3.6 - Triple-Handle Slider UI System (2025-12-04)
- ✓ **Triple-Handle Slider Component** - Universal Numeric Parameter Control
  - Reusable JavaScript class (triple-slider.js ~200 lines)
  - 3 draggable handles: Min range (▼), Max range (▼), Value (|)
  - Features: Auto-clamping, step snapping, range restrictions, callbacks
  - Dark mode styling (triple-slider.css ~80 lines)
  - Bootstrap 5 variable integration
  - Global registry: window.tripleSliders for instance management
  - Public API: initTripleSlider(), getTripleSlider(), setValue(), getValue(), setRange(), getRange()
- ✓ **Comprehensive Test Suite** - 6 Test Scenarios
  - Test page: triple-slider-test.html (~400 lines)
  - Scenarios: Float, Integer, Small Range, Value-Only, Effect Parameters, Performance Test
  - Validation checklist: Drag, clamp, step snap, API methods, callbacks
  - User approved: "looks good go on"
- ✓ **Full Application Integration** - Replaced All Standard Range Sliders
  - HTML templates: Added CSS + JS includes (player, effects, artnet, index)
  - effects.js: FLOAT/INT rendering replaced with triple-slider (line 248-268)
  - player.js: Parameter rendering replaced with triple-slider (2 locations)
    - Location 1: renderParameterControl() FLOAT/INT case (line 3002-3030)
    - Location 2: Generator parameters (line 993-1011)
  - Right-click reset: resetParameterToDefaultTriple() helper functions
  - Automatic initialization via setTimeout() after DOM update
  - Seamless integration: All effect and player parameters now use triple-slider
- ✓ **Range Persistence System** - Min/Max Range Saved with Parameters
  - Frontend: updateParameter() sends rangeMin/rangeMax alongside value
  - Backend: Parameters stored as {_value, _rangeMin, _rangeMax} object
  - Plugin loading: _extract_parameter_values() extracts actual values
  - Session state: Range metadata persisted across page reloads
  - Snapshot support: Range restrictions saved in project files
  - Restore behavior: Sliders initialize with saved range values
  - onRangeChange callback: Automatically saves when user adjusts range handles
- ✓ **Documentation** - Complete Integration Guide
  - TRIPLE_SLIDER_INTEGRATION.md (~250 lines)
  - TRIPLE_SLIDER_COMPLETED.md - Implementation completion report
  - Step-by-step integration plan with code snippets
  - API documentation with usage examples
  - Estimated integration time: ~2-3h (completed)

### v2.3.5 - HAP Codec & Universal Video Converter (2025-12-02)
- ✓ **HAP Codec Decoder** - Hardware-beschleunigtes Video-Decoding
  - HAP Varianten: HAP (DXT1), HAP Alpha (DXT5), HAP Q (BC7)
  - FFmpeg Integration: libavcodec HAP Support
  - Automatische HAP-Format-Erkennung
  - Fallback auf Standard-Codecs
  - Performance-Messung
- ✓ **Universal Video Converter** - FFmpeg-basierte Batch-Konvertierung
  - Input-Formate: AVI, MP4, MOV, GIF, PNG-Sequences
  - Output-Profile: HAP (Performance), H.264 (Hardware-Encoding), H.264 NVENC (GPU)
  - Batch-Processing: Ganze Ordner konvertieren mit glob patterns (recursive)
  - Resize Modes: none, fit, fill, stretch, auto
  - Loop-Optimierung: Nahtlose Loops mit FFmpeg fade filters
  - Separate HTML-Page: Eigenständige Converter-UI (converter.html)
  - FFmpeg-Wrapper mit Progress-Tracking
  - REST API Endpoints: status, formats, info, convert, batch, upload, canvas-size
  - Web-UI mit separater HTML-Page und Dark Mode
- ✓ **Converter UI Implementation** - Standalone Video Converter Page
  - File Browser Integration (FilesTab component mit tree/list view)
  - Drag & Drop Zone (from file browser + from file system)
  - Local File Upload (browse button + drag & drop support)
  - Dual-Mode Selection: Browser Mode (drag & drop) vs Pattern Mode (glob)
  - Multi-file Sequential Conversion mit progress tracking
  - Canvas Size Integration (loads from config.json, fallback 60x300)
  - Output Directory Selection
  - Format Selection Cards (HAP, HAP Alpha, HAP Q, H.264, H.264 NVENC)
  - Conversion Options (Resize Mode, Optimize Loop, Target Size)
  - Progress Bar & Queue Display
  - Results Summary (success/failed counts, compression ratio)
  - Consistent Styling (matches app design with CSS variables)
  - Search Filter für File Browser (works in both tree and list view)
  - Auto-expand folders when searching in tree view

### v2.3.4 - Effect Library Expansion (2025-12-02)
- ✓ **60+ neue Effect-Plugins implementiert** - Massive Erweiterung der Effect-Bibliothek
- ✓ **Geometrie & Transform (6 Effekte):**
  - Flip (Horizontal/Vertical/Both Spiegelung)
  - Mirror (5 Modi: left-to-right, right-to-left, top-to-bottom, bottom-to-top, quad)
  - Slide (Endlose X/Y Verschiebung mit Wrap-Around)
  - Keystone (Perspektivische Trapez-Verzerrung, horizontal/vertikal)
  - Fish Eye (Sphärische Linsenverzerrung, -2.0 bis +2.0)
  - Twist (Spiralförmige Drehung mit konfigurierbarem Radius)
- ✓ **Blur & Distortion (4 Effekte):**
  - Radial Blur (Motion/Zoom Blur von Zentrum aus)
  - Pixelate (LoRez Retro-Look mit konfigurierbarer Blockgröße)
  - Displace (Verschiebung basierend auf Helligkeits-Map)
  - Wave Warp (Sinusförmige Wellenverzerrung horizontal/vertikal)
- ✓ **Glitch & Noise (4 Effekte):**
  - Shift Glitch (Digitale Zeilenverschiebung mit konfigurierbarer Intensität)
  - Distortion (Barrel/Pincushion Linsenverzerrung)
  - Static (TV-Static/Schnee-Rauschen, schwarz/weiß oder farbig)
  - Shift RGB (RGB-Kanal-Verschiebung für chromatische Aberration)
- ✓ **Edge & Detection (2 Effekte):**
  - Edge Detection (Sobel/Canny/Laplacian mit mehreren Farbmodi)
  - Auto Mask (Automatische Maskierung durch Helligkeit/Farbbereich/Kanten)
- ✓ **Composite & Mask (4 Effekte):**
  - Chroma Key (Green/Blue screen removal mit Spill Suppression)
  - Keystone Mask (Perspektivische Maskierung mit 4-Punkt-Kontrolle)
  - Vignette (Rand-Abdunklung/-Aufhellung mit Circular/Rectangular Shape)
  - Drop Shadow (Schatten mit Offset, Blur, Opacity und Detection Modes)
- ✓ **Simple 3D & Kaleidoscope (4 Effekte):**
  - Kaleidoscope (Mirror segments mit Rotation und Zoom)
  - Tile (Grid-Repeat mit Mirror-Modi und Offset)
  - Circles (Concentric circle mapping mit 3 Modi: radial_warp, circular_repeat, spiral)
  - Bendoscope (Kaleidoskop + Circular Bending + Twist für psychedelische Effekte)
- ✓ **Leicht implementierbare Zusatz-Effekte (15 Effekte):**
  - Sharpen (Unsharp Mask mit konfigurierbarer Stärke)
  - Emboss (3D-Relief-Effekt mit 4 Hauptrichtungen)
  - Sepia (Vintage-Ton mit Intensitäts-Parameter)
  - Gamma Correction (Lookup-Table-basiert, schnell)
  - Color Temperature (Warm/Kalt-Anpassung)
  - Channel Mixer (9 Parameter für vollständige RGB-Kontrolle)
  - Noise (Gaussian & Salt/Pepper)
  - Solarize (Invertierung über Schwellwert)
  - Duotone (Zwei-Farben-Mapping für Schatten/Highlights)
  - Oil Paint (Ölmalerei-Simulation mit Pinselgröße)
  - Mosaic (Pixelation/Blockierung)
  - Zoom (Zoom In/Out mit Zentrum-Kontrolle)
  - Rotate (Rotation mit Zentrum-Kontrolle)
  - Border (3 Modi: Solid, Replicate, Reflect)
  - Crop (Prozentuale Zuschnitt mit Scale-Back-Option)
- ✓ **NumPy String Type Bugfix** - COLOR Parameter handling korrigiert für np.str_ types

### v2.3.3 - Clip Trimming & ion.rangeSlider UI (2025-12-01)
- ✓ **Clip Trimming System** - In/Out Points pro Clip mit Non-Destructive Editing
  - **ClipRegistry Integration:** Metadata für in_point, out_point, reverse, total_frames
  - **REST API:** POST `/api/clips/<clip_id>/trim`, `/api/clips/<clip_id>/reverse`, `/api/clips/<clip_id>/reset-trim`, `/api/clips/<clip_id>/reload`
  - **VideoSource Frame-Range-Check:** current_frame initialisiert auf in_point statt 0
  - **Reverse Playback:** Frame-Counter rückwärts, Loop zurück zu out_point
  - **Live-Apply:** reload_trim_settings() für aktive Wiedergabe
- ✓ **Ion.RangeSlider Integration** - Professional UI Component für Trim Points
  - **Double Range Slider:** Zwei Handles für in_point/out_point mit Grid Display
  - **jQuery & ion.rangeSlider 2.3.1** via CDN
  - **Collapsible Section:** Toggle-Arrow wie Effects-System
  - **Right-Click Reset:** Context-Menu setzt Slider auf volle Clip-Range zurück
  - **Dark Theme Styling:** Custom CSS für ion.rangeSlider
- ✓ **Backend as Source of Truth:** Frontend nutzt backend-generierte clip_id statt eigene UUID
  - **Bug Fix:** controls.js verwendet `data.clip_id` statt `crypto.randomUUID()`
  - **Konsistente Clip-ID:** UUID über gesamten Lifecycle (Playlist → Playback → Loops)

### v2.3.2 - Multi-Layer Compositing System (2025-11-28)
- ✓ **Clip-Based Layer Architecture** - Layer-Stack pro Clip (Layer 0 = Base)
- ✓ **BlendEffect Plugin** - 6 Blend Modes: Normal, Multiply, Screen, Overlay, Add, Subtract
- ✓ **Layer CRUD API** - `/api/clips/{clip_id}/layers/*` Endpoints
- ✓ **Frontend Layer Panel** - Drag & Drop, Blend Mode/Opacity Controls
- ✓ **Thread-Safe Layer Loading** - Auto-Reload bei Clip-Wechsel
- ✓ **Session State Persistence** - Layer-Stack in Snapshots/Projects

### v2.3.1 - UI/UX Improvements (2025-11-28)
- ✓ **Universal Search Filter Component** - Debounced Search mit Live-Resultat-Zähler
  - Implementiert für: Effects, Sources, Files Tabs
  - Komponenten: `search-filter.html`, `search-filter-loader.js`
  - Dokumentation: `docs/SEARCH_FILTER.md`
- ✓ **Multi-Video-Source Support** - `video_sources` Array in config.json
  - UNC-Pfade (Netzwerkfreigaben) unterstützt
  - File Browser zeigt alle Quellen als Root-Ordner
  - API: `get_file_tree()` und `get_all_videos()` erweitert
  - Dokumentation: `docs/VIDEO_SOURCES.md`, `docs/CONFIG_SCHEMA.md`
- ✓ **Default Effect Chains** - Auto-Apply via config.json
  - `effects.video`: Effect Chain beim Video-Player-Start
  - `effects.artnet`: Effect Chain beim Art-Net-Player-Start
  - `effects.clips`: Per-Clip Default-Effekte (UUID oder Pfad-basiert)
  - DefaultEffectsManager mit vollständiger Validierung
  - Dokumentation: `docs/DEFAULT_EFFECTS.md`

### Unified API Architecture mit UUID-basiertem Clip-Management
- ✓ **ClipRegistry System** - UUID-basierte Clip-Identifikation (Singleton-Pattern)
- ✓ **Vereinheitlichte API** - `/api/player/{player_id}/clip/{clip_id}/...` Endpoints
- ✓ **Dual-Player-Architektur** - Video Player (Preview) + Art-Net Player (Output)
- ✓ **Unabhängige Clip-Effekte** - Jeder Player verwaltet eigene Effekt-Chains
- ✓ **PlayerManager** - `get_player(player_id)` für einheitlichen Zugriff
- ✓ **Frontend Migration** - controls.js nutzt UUID-basierte Endpoints
- ✓ **Lazy VideoSource-Initialisierung** - Verhindert FFmpeg-Konflikte beim Multi-Instance-Zugriff
- ✓ **Clip-basierte Effekte** - Player lädt Effekte aus ClipRegistry statt lokaler Liste

### Plugin-System (vollständig implementiert)
- ✓ **PluginBase** - Standardisiertes Interface mit METADATA + PARAMETERS
- ✓ **PluginManager** - Auto-Discovery, Lazy Loading, Error-Isolation
- ✓ **Parameter-System** - 5 Typen (float, int, bool, select, color) mit Validation
- ✓ **Runtime-Updates** - Parameter während Playback änderbar
- ✓ **Plugin-API** - `/api/plugins/*` Endpoints für CRUD-Operationen
- ✓ **18 Effect-Plugins implementiert:**
  - **Farb-Manipulation (11):** add_subtract, brightness_contrast, colorize, tint, hue_rotate, invert, saturation, exposure, levels, posterize, threshold
  - **Time & Motion (5):** trails, stop_motion, delay_rgb, freeze, strobe
  - **Blur (1):** blur (Gaussian/Box)
  - **Blending (1):** blend_mode (14 Modi: Normal, Multiply, Screen, Overlay, Add, Subtract, Darken, Lighten, Color Dodge, Color Burn, Hard Light, Soft Light, Difference, Exclusion)

### Multi-Layer Compositing System (v2.3.2)
- ✓ **Clip-Based Layer Architecture** - Jeder Clip hat eigenen Layer-Stack (Layer 0 = Base)
- ✓ **Layer Class** - `layer.py` mit blend_mode, opacity, effects, clip_id
- ✓ **Player Layer Management** - add_layer(), remove_layer(), reorder_layers(), load_clip_layers()
- ✓ **Multi-Layer Compositing Loop** - Sequential frame-fetching, auto-loop overlays
- ✓ **Clip-Based Layer API** - `/api/clips/{clip_id}/layers/*` REST Endpoints
- ✓ **ClipRegistry Layer Storage** - Per-clip layers array mit persistence
- ✓ **Session State Integration** - Layer-Stack in Snapshots/Projects gespeichert
- ✓ **Frontend Layer Panel** - Drag & drop, blend mode/opacity controls, add/remove layers
- ✓ **BlendEffect Plugin** - 6 blend modes (normal, multiply, screen, overlay, add, subtract)
- ✓ **Per-Layer Effects** - Effekte vor Compositing angewendet
- ✓ **Backward Compatibility** - Alte Sessions automatisch konvertiert
- ✓ **Thread-Safe Loading** - Auto-reload bei Clip-Wechsel

### Transition Plugin System (v2.3.1)
- ✓ **PluginType.TRANSITION** - `blend_frames(frame_a, frame_b, progress)` Methode
- ✓ **Fade Transition Plugin** - Easing-Funktionen: linear, ease_in, ease_out, ease_in_out
- ✓ **Player Integration** - Transition-Buffering mit apply_transition() bei Clip-Wechsel
- ✓ **REST API** - `/api/transitions/list`, `/api/player/{player_id}/transition/config`, `/api/player/{player_id}/transition/status`
- ✓ **Reusable UI Component** - `components/transition-menu.html`
  - Enable/Disable Toggle mit Settings-Panel
  - Effect-Dropdown dynamisch geladen von API
  - Duration-Slider: 0.1-5.0s, 0.1s Steps, Live-Value-Display
  - Easing-Function Selector: 4 Modi
  - Integration in Video & Art-Net Player-UI
- ✓ **Dokumentation** - `docs/TRANSITION_SYSTEM.md`, `docs/TRANSITION_FRONTEND_INTEGRATION.md`, `docs/TRANSITION_QUICKSTART.md`

### Code Cleanup & Deprecation
- ✓ **Legacy Player gelöscht** - video_player.py (868 Zeilen) und script_player.py (~620 Zeilen)
- ✓ **~1500 Zeilen toter Code eliminiert**
- ✓ **Unified Player** - Nur noch eine Player-Klasse mit austauschbaren FrameSource Implementierungen
- ✓ **Deprecated Properties entfernt** - `self.effect_chain`, `self.clip_effects`
- ✓ **Backward-Compatibility-Code entfernt** - Alle Legacy-Funktionen gelöscht
- ✓ **Test-Dateien organisiert** - Verschoben nach `tests/` Ordner
- ✓ **__init__.py bereinigt** - Deprecated exports entfernt, ClipRegistry hinzugefügt
- ✓ **Static Content bereinigt** - Backup-Dateien gelöscht (~36 KB)

### Dokumentation
- ✓ **CHANGELOG.md** - v2.3.0 Release Notes
- ✓ **TODO.md aktualisiert** - Erledigtes markiert, neue Struktur
- ✓ **ARCHITECTURE.md** - Unified API Dokumentation
- ✓ **docs/UNIFIED_API.md** - API-Referenz mit allen Endpoints
- ✓ **docs/MIGRATION.md** - Migration Guide von alten APIs
- ✓ **docs/MULTI_LAYER_ARCHITECTURE.md** - Layer-System Architektur
- ✓ **docs/BLEND_EFFECT.md** - BlendEffect Plugin Dokumentation
- ✓ **TODO_LAYERS.md** - Multi-Layer Implementation Tracking

### Vorteile
- **Keine Pfad-basierten Kollisionen** - UUID-basierte Identifikation
- **Saubere Trennung** - Video-Preview vs. Art-Net-Output
- **Einfachere API** - Konsistente RESTful Endpoints
- **Unabhängige Player** - Verschiedene Videos mit verschiedenen Effekten gleichzeitig
- **Erweiterbar** - Plugin-System für neue Effekte ohne Core-Changes
- **Testbar** - Jedes Plugin isoliert testbar
- **Flexible Compositing** - Clip-basierte Layer-Stacks mit individuellen Effekten

---

## v2.2 - Performance-Optimierungen (2025-11-23)

### Performance-Features
- ✓ **NumPy-Vektorisierung Stream-Loops** - 40-60% CPU-Reduktion
- ✓ **Redundante Frame-Copies entfernt** - 15-20% CPU-Reduktion  
- ✓ **NumPy Channel-Reordering** - 5-10% CPU-Reduktion
- ✓ **Gradient-Pattern Cache** - 1-3ms pro Generation gespart
- ✓ **Memory Leak Prevention** - Deque-basierte Recording (verhindert 195MB nach 1h)
- ✓ **Event-basierte Synchronisation** - Sofortige Pause/Resume
- ✓ **Lock-free Stats** - Atomic Counters, 2-5% CPU-Reduktion

### Art-Net Delta-Encoding
- ✓ **LED Bit-Tiefe Unterstützung** - 8-bit und 16-bit Modi
- ✓ **Basic Delta-Encoding** - Threshold-basierte Differenz-Erkennung
- ✓ **Full-Frame Sync** - Periodische komplette Updates (alle N Frames)
- ✓ **Runtime Controls** - CLI/API-Befehle für delta on/off/status/threshold/interval

### Weitere Features
- ✓ **CLI Debug-Modus** - Konfigurierbares Console-Logging (config.json: console_log_level)
- ✓ **Art-Net Reaktivierung Bugfix** - `is_active` wird in start() korrekt gesetzt

### Messergebnisse
- **Gesamt-Performance-Gewinn:** ~55-75% CPU-Reduktion, 50-90% Netzwerk-Reduktion (statische Szenen)
- **Delta-Encoding (300 LEDs, 8-bit, 30 FPS):**
  - Statisches Testbild: 87% Netzwerk-Reduktion (1.2 Mbps → 0.15 Mbps)
  - Langsames Video: 50% Netzwerk-Reduktion (1.2 Mbps → 0.6 Mbps)
  - Schnelles Video: 25% Netzwerk-Reduktion (1.2 Mbps → 0.9 Mbps)
  - CPU-Overhead: 0-5% (NumPy-optimiert)
  - Memory: ~6 MB für last_sent_frame Buffer

### Dokumentation
- ✓ docs/DELTA_ENCODING.md - Vollständige technische Dokumentation
- ✓ docs/PERFORMANCE.md - Performance-Metriken und Benchmarks
- ✓ docs/USAGE.md - Art-Net Optimierung Sektion
- ✓ CHANGELOG.md - Version 2.2.0 Release Notes

---

## v2.1 - Architecture Refactoring (2025-11-22)

### PlayerManager Refactoring
- **Problem:** DMXController wurde als Player-Container missbraucht
  - Verletzt Single Responsibility Principle
  - Namens-Verwirrung: Module nutzten `dmx_controller` nur für `player`-Zugriff
  - Zirkuläre Abhängigkeiten und Code-Duplikation

- **Lösung:** PlayerManager-Klasse eingeführt
  - Zentraler Player-Container (Single Source of Truth)
  - DMXController bleibt rein für DMX-Input zuständig
  - Betrifft: main.py, cli_handler.py, rest_api.py, api_videos.py, api_points.py, api_routes.py, command_executor.py

- **Vorteile:**
  - Klare Verantwortlichkeit und Modulgrenzen
  - Einfacherer Player-Wechsel (nur `player_manager.set_player()`)
  - Reduziert Coupling zwischen Modulen
  - Bessere Testbarkeit

- **Implementierung:**
  - `PlayerManager` Klasse mit `player` Property und `set_player()` Methode
  - DMXController nutzt PlayerManager statt direktem Player
  - Backward Compatibility: DMXController.player Property delegiert zu PlayerManager
  - Alle API-Routen aktualisiert (playback, settings, artnet, info, recording, scripts, videos, points)
  - RestAPI und CLIHandler nutzen PlayerManager
  - CommandExecutor nutzt player_provider Lambda für PlayerManager-Zugriff

### Bugfixes
- ✓ Restart-Funktion repariert: Startet Video jetzt immer neu vom ersten Frame (egal ob pausiert/gestoppt)
- ✓ Preview & Fullscreen Stream funktionieren wieder
- ✓ Traffic-Messung funktioniert
- ✓ Cache-System-Reste entfernt (cache_loaded AttributeError behoben)

---

## v2.0 - Unified Player Architecture (2025-11-20)

### Architektur-Refactoring
- ✓ Frame Source Abstraction (FrameSource base class)
- ✓ VideoSource Implementation (OpenCV-basiert, GIF-Support)
- ✓ ScriptSource Implementation (ScriptGenerator-Integration)
- ✓ Unified Player mit source switching
- ✓ Alle API-Routen aktualisiert (video/script loading)
- ✓ CLI Handler Migration (video/script/points)
- ✓ DMX Controller Integration
- ✓ Backward Compatibility (alte VideoPlayer/ScriptPlayer als deprecated)
- ✓ Stop/Start/Restart Playback-Fixes
- ✓ 90% Code-Duplikation eliminiert (~1300 → 850 Zeilen + neue Architektur)

---

## v1.x - Initial Implementation

### Core Features
- ✓ CLI-Steuerung implementiert
- ✓ DMX-Input über Art-Net (Universum 100)
- ✓ DMX-Test-App erstellt
- ✓ Video-Player mit Art-Net Output
- ✓ Numpy-Optimierung für RGB-Extraktion
- ✓ 8-Universen-Grenze Logik
- ✓ Brightness/Speed/Loop Steuerung
- ✓ Pause/Resume Funktionalität
- ✓ Blackout Funktion
- ✓ Code-Refactoring (Module-Struktur)
- ✓ Konfigurationsdatei (config.json)

### Video-System
- ✓ Video-Slot System (4 Kanäle, 1020 Videos, DMX Ch6-9)
- ✓ Hardware-Beschleunigung aktiviert mit Status-Ausgabe
- ✓ Kanal-Ordner System (kanal_1 bis kanal_4)
- ✓ RGB-Aufzeichnung
- ✓ Canvas-Größe Skalierung

### Art-Net Features
- ✓ Art-Net Code Separation (artnet_manager.py Modul)
- ✓ Test-Pattern mit Gradient
- ✓ Automatischer Art-Net Start
- ✓ RGB-Kanal-Reihenfolge pro Universum (Channel Mapping)
- ✓ Unterstützt alle 6 Permutationen (RGB, GRB, BGR, RBG, GBR, BRG)
- ✓ universe_configs in config.json
- ✓ _reorder_channels() Methode in ArtNetManager
- ✓ CLI-Befehle: artnet map/show mit Range-Syntax
- ✓ Testmuster berücksichtigen Channel Mapping

### Points Management
- ✓ Multi-JSON Punkte-Verwaltung (list/validate/switch/reload)
- ✓ JSON Schema Validierung mit jsonschema
- ✓ Points Switch/Reload via REST API
- ✓ /api/points/switch mit Validierung
- ✓ /api/points/reload für aktuelles File
- ✓ Auto-restart bei laufendem Video

### Flask REST API
- ✓ Flask REST API komplett implementiert
- ✓ Alle Playback Endpoints (play/stop/pause/resume/restart)
- ✓ Settings Endpoints (brightness/speed/fps/loop)
- ✓ Art-Net Endpoints (blackout/test)
- ✓ Video Management (list/load)
- ✓ Points Management (list/switch/reload/validate/current)
- ✓ Status & Info & Stats Endpoints
- ✓ Recording Endpoints (start/stop)
- ✓ Console Endpoints (log/command/clear)
- ✓ CORS Support aktiviert

### API Modularisierung
- ✓ api_routes.py (Playback, Settings, Art-Net)
- ✓ api_points.py (Points Management)
- ✓ api_videos.py (Video Management)
- ✓ api_console.py (Console & Commands)

### Web-Interface
- ✓ Bootstrap GUI (index.html) - Canvas Editor
- ✓ Control Panel (controls.html) - Playback Steuerung
- ✓ Dark Mode mit LocalStorage
- ✓ Externe CSS-Datei (styles.css)
- ✓ Externe JS-Dateien (editor.js, controls.js)
- ✓ Navigation zwischen GUIs
- ✓ Console Component in separates JS-Modul ausgelagert
- ✓ Responsive Design für Mobile optimiert
- ✓ LocalStorage für Settings Persistence (Brightness, Speed)
- ✓ Canvas-Zoom & Scrollbars (Zoom per Maus & Buttons, automatische Scrollbalken)
- ✓ Toast-Benachrichtigungen (statt alert, Theme-aware)
- ✓ Server-Projektverwaltung (CRUD, Download, Modal-UI)

### WebSocket Support
- ✓ Flask-SocketIO Integration
- ✓ Status Broadcasting (alle 2s)
- ✓ Console Live-Updates
- ✓ Fallback auf REST Polling
- ✓ Werkzeug "write() before start_response" Bug gefixt (manage_session=False + disconnect error handling)

### Script Generator (Procedural Graphics)
- ✓ ScriptGenerator Klasse (list/load/generate)
- ✓ ScriptPlayer Klasse (kompatibel mit VideoPlayer API)
- ✓ Python Script API: generate_frame(frame_number, width, height, time, fps)
- ✓ 10 Beispiel-Shaders (rainbow_wave, plasma, pulse, matrix_rain, fire, heartbeat, falling_blocks, line_*)
- ✓ METADATA-System für Script-Infos
- ✓ CLI-Befehle: scripts list, script:<name>
- ✓ REST API Endpoints: GET /api/scripts, POST /api/load_script
- ✓ Vollständige Dokumentation (scripts/README.md)
- ✓ Error Handling mit Traceback
- ✓ Lazy Module Loading (__init__.py __getattr__)

### Command Execution
- ✓ CommandExecutor Klasse für gemeinsame Command-Handler Logik
- ✓ CLIHandler nutzt CommandExecutor.execute()
- ✓ API Console nutzt gemeinsamen Command-Handler
- ✓ Code-Deduplizierung zwischen CLI und Web Console
- ✓ Einheitliche CommandResult-Struktur

### Konfiguration
- ✓ API Host/Port/Secret Key in config.json
- ✓ Art-Net FPS/Even Packet/Broadcast
- ✓ Video Delays (shutdown/frame_wait/recording_stop)
- ✓ Console Log Buffer Size
- ✓ Status Broadcast Interval
- ✓ Frontend Polling Interval
- ✓ Frontend-Config API Endpoint (/api/config/frontend)

### Dokumentation & Testing
- ✓ docs/API.md (500+ Zeilen, alle Endpoints)
- ✓ WebSocket Events dokumentiert
- ✓ Dokumentation in README und API.md
- ✓ tests/test_main.py (4 Test-Klassen)
- ✓ Validator, ArtNetManager, Cache, Error Tests

### Projekt-Infrastruktur
- ✓ RGB Cache Infrastruktur (cache/ Ordner, CLI-Befehle)
- ✓ requirements-lock.txt erstellt (27 Packages mit exakten Versionen)
- ✓ .gitignore Patterns
