# Py_artnet - TODO Liste

> **Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)**

## 🚀 Geplante Features (nach Komplexität & Priorität)

Die Features sind in 6 Prioritätsstufen organisiert basierend auf **Implementierungs-Komplexität** und **Business-Value**:
- **P1**: Quick Wins (niedriger Aufwand, hoher Nutzen)
- **P2**: Mittlere Komplexität, hoher Nutzen
- **P3**: Mittlere Komplexität, mittlerer Nutzen
- **P4**: Hohe Komplexität, hoher Nutzen
- **P5**: Niedrige Priorität / Maintenance
- **P6**: Optional / Langfristig

---

## 🔥 PRIORITÄT 1 - Quick Wins (~43-66h)
**Niedriger Aufwand, hoher Nutzen - sofort umsetzbar**

### 1.0 🎨 Unified Playlist System - Player/Playlist Generalisierung (~7-10h) 🆕

**Ziel:** 100% generalisiertes Player-System - neue Player durch `playerConfigs` hinzufügen, ohne Code-Änderungen.

**Aktueller Stand:** ~60% generalisiert (Backend 99%, Frontend 60%)

- [x] **Phase 1: Legacy Variables migrieren (2h):** ✅ COMPLETED
  - `videoFiles/artnetFiles` → `playerConfigs[playerId].files`
  - `currentVideoFile/currentArtnetFile` → `playerConfigs[playerId].currentFile`
  - `videoAutoplay/artnetAutoplay` → `playerConfigs[playerId].autoplay`
  - `videoLoop/artnetLoop` → `playerConfigs[playerId].loop`
  - ~15 Funktionen betroffen (loadVideoFile, loadArtnetFile, etc.)

- [x] **Phase 2: Load-Funktionen generalisieren (2-3h):** ✅ COMPLETED
  - `loadVideoFile()` + `loadArtnetFile()` → `loadFile(playerId, file)`
  - `window.loadVideoFile` + `window.loadArtnetFile` → `window.loadFile`
  - Entfernt ~100 Zeilen Code-Duplikation

- [x] **Phase 3: Player Wrappers entfernen (2h):** ✅ COMPLETED
  - `toggleVideoPlay()`, `nextVideoClip()` etc. → `togglePlay(playerId)`, `nextClip(playerId)`
  - Window-Wrapper durch direkte generische Calls ersetzen

- [x] **Phase 4: Backend-Hotfix (15min):** ✅ COMPLETED
  - `default_effects.py` Zeilen 115-118: Hardcoded player_type checks entfernen
  - Verwende `player.player_type` statt `isinstance()` checks

- [x] **Phase 5: Testing & Bugfixes:** ✅ COMPLETED
  - Fixed orphaned function call references
  - Exposed player control functions to window object
  - Fixed async/await syntax in drop handlers
  - Implemented transport loop detection for autoplay
  - Fixed Art-Net autoplay race conditions
  - All bugs resolved, both players fully functional

- [x] **Phase 6: v2.3.7 Legacy Code Cleanup (~6-8h):** ✅ COMPLETED (2025-12-05)
  - ✅ Removed deprecated trim/reverse functions from player.js (~300 lines)
  - ✅ Deleted 4 deprecated backend modules (~500 lines): api_clip_trim.py, api_artnet_effects_deprecated.py, api_effects_deprecated.py, api_videos_deprecated.py
  - ✅ Removed deprecated ClipRegistry methods: set_clip_trim(), set_clip_reverse(), get_clip_playback_info()
  - ✅ Removed trim/reverse logic from VideoSource (in_point, out_point, reverse properties)
  - ✅ Removed ScriptSource class completely (~100 lines) and all references from 9 modules
  - ✅ Migrated ScriptSource → GeneratorSource with deprecation warnings
  - ✅ Removed legacy API fallbacks from playerConfigs
  - ✅ Removed deprecated layer management functions: updateLayerStackVisibility(), selectLayer()
  - ✅ Fixed all syntax errors introduced during cleanup (4 errors)
  - **Total Impact:** ~1000 lines of dead code removed, Transport Effect Plugin now single source of truth

- [x] **Phase 7: WebRTC → WebSocket Migration (~4h):** ✅ COMPLETED (2025-12-08)
  - ✅ Created WebSocket streaming backend (`src/modules/api_websocket.py`)
  - ✅ Created WebSocket streaming frontend (`frontend/js/websocket-preview.js`)
  - ✅ Removed WebRTC backend modules (api_webrtc.py, webrtc_track.py)
  - ✅ Removed WebRTC frontend (webrtc-preview.js)
  - ✅ Updated player.js and player.html for WebSocket
  - ✅ Migrated config.json from webrtc → websocket section
  - ✅ Added Socket.IO integration (Flask-SocketIO + Socket.IO client)
  - ✅ Implemented aspect-ratio-preserving canvas rendering
  - ✅ Performance optimizations: frame identity tracking, 1ms polling, fast JPEG encoding
  - ✅ Fixed disconnect handler and thread joining issues
  - **Result:** Latency reduced from ~1s to <100ms, simplified LAN-only architecture

**Vorteile:**
- Neue Player in 5min hinzufügen (nur `playerConfigs` Entry)
- -200 Zeilen Code (keine Duplikation)
- Konsistentes Verhalten über alle Player
- Wartbarkeit massiv verbessert
- Cleaner codebase ohne deprecated legacy code (~1000 lines removed)

**Siehe:** [UNIFIED_PLAYLISTS.md](docs/UNIFIED_PLAYLISTS.md) für Details

---

### 1.1 🔄 Master/Slave Duration Sync (~3-4h) 🆕

**Ziel:** Slave clips automatically loop to match master clip duration for synchronized timing.

**Concept:** When slave syncs to a clip, calculate required `loop_count` based on master's clip duration.

- [ ] **Config Option (30min):**
  - Add `master_slave.sync_slave_duration: false` to config.json
  - Add `master_slave.duration_match_tolerance: 0.5` (seconds) for rounding
  - Document config options in CONFIG_SCHEMA.md

- [ ] **Duration Calculation Method (1h):**
  - Add `_get_clip_duration(player)` to PlayerManager
  - Calculate duration from source.total_frames / source.fps
  - Handle edge cases: generators (return None), missing metadata
  - Add `_get_transport_effect(player)` helper method

- [ ] **Sync Logic Implementation (1-2h):**
  - Enhance `_sync_slave_to_index()` in player_manager.py
  - Calculate required loops: `math.ceil(master_duration / slave_duration)`
  - Apply to slave's transport.loop_count
  - Add detailed logging: "🔄 Slave duration sync: 5.0s × 6 = 30.0s (master: 30.0s)"

- [ ] **Edge Case Handling (30min):**
  - Slave longer than master: Use loop_count=1, log warning
  - Generator clips: Skip duration sync, use manual loop_count
  - Missing duration data: Fallback to existing behavior
  - Zero/negative durations: Validation checks

- [ ] **Testing & Validation (30min):**
  - Test: 30s master + 5s slave = 6 loops
  - Test: 10s master + 15s slave = 1 loop (slave plays full)
  - Test: Master with generators
  - Test: Config enabled/disabled behavior

**Example Usage:**
```json
{
    "master_slave": {
        "sync_slave_duration": true
    }
}
```

**Result:**
```
Master: 30s clip, loop_count=1 → plays once, advances
Slave:  5s clip, loop_count=6 (auto) → loops 6 times, syncs with master
```

**Siehe:** [TRANSPORT_MASTER_SLAVE_ANALYSIS.md](docs/TRANSPORT_MASTER_SLAVE_ANALYSIS.md) Option 1

---

### 1.2 🎨 Generator Duration Support (~3-4h) ✅ COMPLETED (2025-12-08)

**Ziel:** Give generator clips a defined duration for proper loop_count and master/slave synchronization.

**Concept:** Add `duration` parameter to GeneratorSource for calculating total_frames and enabling duration-based timing.

- [x] **GeneratorSource Enhancement (2h):** ✅ COMPLETED
  - Added `duration` parameter (seconds, default 0=infinite)
  - Uses existing `fps` from FrameSource (default 30)
  - Calculates `total_frames = duration * fps` when duration > 0
  - Modified `get_next_frame()` to loop frames: `virtual_frame % total_frames`
  - Added `is_duration_defined()` method for duration sync compatibility
  - Updates `is_infinite` flag based on duration (0=infinite, >0=finite)

- [x] **Plugin System Updates (1h):** ✅ COMPLETED
  - PLUGIN_TEMPLATE.md already included duration parameter example
  - Duration auto-handled by GeneratorSource parameter system
  - Validation built-in via parameter min/max (0-600s in template)
  - All existing generators can add duration parameter to PARAMETERS array

- [x] **UI Integration (30min):** ✅ COMPLETED
  - Generator parameter UI already supports INT parameters with triple-slider
  - Duration shows as slider when added to generator's PARAMETERS
  - Range customizable via param min/max (e.g., 0-300s)
  - Value displayed automatically by existing parameter system

- [x] **Master/Slave Compatibility (30min):** ✅ COMPLETED
  - `is_duration_defined()` method ready for TODO 1.1 integration
  - When `_get_clip_duration()` is implemented in TODO 1.1, it will check this method
  - Generators with duration > 0 can be master clips
  - Duration sync (1.1) will work seamlessly with generators

**Implementation Details:**
```python
# src/modules/frame_source.py - GeneratorSource.__init__()
self.duration = parameters.get('duration', 0)  # 0 = infinite, >0 = seconds
self.is_infinite = (self.duration == 0)
if self.duration > 0:
    self.total_frames = int(self.duration * self.fps)
else:
    self.total_frames = 0  # 0 = infinite

# src/modules/frame_source.py - GeneratorSource.get_next_frame()
if self.total_frames > 0:
    virtual_frame = virtual_frame % self.total_frames  # Loop frames

# src/modules/frame_source.py - GeneratorSource.is_duration_defined()
def is_duration_defined(self):
    return self.duration > 0
```

**Usage in Generator Plugins:**
```python
# Add to PARAMETERS array
{
    'name': 'duration',
    'label': 'Duration (seconds)',
    'type': ParameterType.INT,
    'default': 0,  # 0 = infinite
    'min': 0,
    'max': 600,
    'description': 'Playback duration (0 = infinite, >0 = loop after N seconds)'
}
```

**Edge Cases:**
- duration=0: Infinite generator (default behavior)
- duration>0: Loops after total_frames reached
- Master/slave: Generators with duration can be master or calculate slave loops
- UI: Duration parameter automatically gets slider in generator parameter panel

**Benefits:**
- ✅ Generators work in master/slave duration sync (TODO 1.1)
- ✅ Predictable loop timing for playlist automation
- ✅ Frame-accurate synchronization with video clips
- ✅ Transport effect loop_count works with generators
- ✅ No changes needed to existing generators (duration optional)

**Siehe:** [TRANSPORT_MASTER_SLAVE_ANALYSIS.md](docs/TRANSPORT_MASTER_SLAVE_ANALYSIS.md) Option 3

---

### 1.3 🎛️ Dynamic Playlists via config.json (~8-12h) 🆕

**Ziel:** Neue Playlists (Audio, DMX, OSC, MIDI, etc.) über config.json hinzufügen, ohne Code zu ändern.

- [ ] **Config Schema Definition (2h):**
  - Definiere `playlists` Array in config.json
  - Schema pro Playlist: `{id, name, type, icon, apiBase, features}`
  - Beispiel-Types: video, artnet, audio, dmx, osc, midi
  - Features-Flags: autoplay, loop, transitions, preview, effects

- [ ] **Backend Dynamic Registration (2-3h):**
  - PlayerManager liest `playlists` aus config.json
  - Dynamisches Registrieren von Playern: `for playlist in config['playlists']: register_player(playlist['id'])`
  - Player-Type-Factory: Je nach type verschiedene Player-Klassen instantiieren
  - API-Routes automatisch für alle konfigurierten Player verfügbar

- [ ] **Frontend Dynamic playerConfigs (2-3h):**
  - Neuer API-Endpoint: `GET /api/player/configs` → Gibt alle Player-Configs zurück
  - Frontend: Fetch playerConfigs from API statt hardcoded
  - playerConfigs dynamisch aus API-Response generieren
  - Backward-compatibility: Fallback auf hardcoded configs wenn API fehlt

- [ ] **Dynamic UI Generation (2-3h):**
  - HTML-Template für Player-Section (Mustache/Handlebars oder JS Template Literals)
  - JavaScript generiert player-sections basierend auf playerConfigs
  - Icon-Mapping: video=📹, artnet=💡, audio=🔊, dmx=🎚️, osc=🎛️, midi=🎹
  - Container-IDs dynamisch: `${playerId}Playlist`, `${playerId}Preview`, etc.

- [ ] **Auto-Initialize (1h):**
  - Loop über alle playerConfigs: `for (let playerId in playerConfigs) { await loadPlaylist(playerId); }`
  - Event-Listeners automatisch für alle Player registrieren
  - Drop-Zones für alle Player generieren

**Config-Beispiel (config.json):**
```json
{
  "playlists": [
    {
      "id": "video",
      "name": "Video",
      "type": "video",
      "icon": "📹",
      "apiBase": "/api/player/video",
      "features": {
        "autoplay": true,
        "loop": true,
        "transitions": true,
        "preview": true,
        "effects": true
      }
    },
    {
      "id": "artnet",
      "name": "Art-Net",
      "type": "artnet",
      "icon": "💡",
      "apiBase": "/api/player/artnet",
      "features": {
        "autoplay": true,
        "loop": true,
        "transitions": true,
        "preview": true,
        "effects": true
      }
    },
    {
      "id": "audio",
      "name": "Audio",
      "type": "audio",
      "icon": "🔊",
      "apiBase": "/api/player/audio",
      "features": {
        "autoplay": true,
        "loop": true,
        "transitions": false,
        "preview": false,
        "effects": true
      }
    }
  ]
}
```

**Vorteile:**
- Neue Player in 5min hinzufügen (nur config.json Entry, kein Code!)
- Skalierbar auf beliebig viele Player (Audio, DMX, OSC, MIDI, etc.)
- Konsistente API für alle Player-Typen
- Frontend/Backend vollständig entkoppelt

---

### 1.2 🎯 Playlist Master/Slave Synchronization (~8-14h) 🚧 IN PROGRESS

**⚠️ KNOWN ISSUE:** Generator clips in playlists with autoplay+loop+master/slave mode not working correctly. Need deeper investigation of generator handling in autoplay loop and slave synchronization context.

- [x] **Master/Slave Toggle UI (2h):** ✅ COMPLETED
  - Toggle-Button in Playlist-Header (Video & Art-Net)
  - Master-Indicator (👑 Icon) für aktive Master-Playlist
  - Nur eine Playlist kann Master sein (Toggle schaltet andere aus)
  - Visuelles Feedback: Master (grün/golden), Slave (grau/normal)
  - CSS Styling mit Switch-Animation

- [x] **Synchronization Engine (4-6h):** ✅ COMPLETED
  - Event-System: Master emittiert `clip_changed` Events mit Clip-Index
  - Slave-Listener: Reagiert auf Master-Events und wechselt zum gleichen Clip-Index
  - Initial Sync: Wenn Master aktiviert → Alle Slaves springen zu Master-Clip-Index
  - Transition-Preservation: Slaves verwenden ihre eigenen Transition-Settings
  - Edge-Case Handling:
    - Slave hat weniger Clips als Master → Slave stopped (black screen)
    - Master deaktiviert → Slaves werden autonom
    - Playlist leer → Keine Sync-Aktion

- [x] **Backend Implementation (3-4h):** ✅ COMPLETED
  - `PlayerManager`: Master/Slave State Management
  - `set_master_playlist(player_id)` → Setzt Master, alle anderen zu Slaves
  - `sync_slaves_to_master()` → Synchronisiert alle Slaves zum Master-Clip
  - Event-Dispatcher für Clip-Wechsel (Observer Pattern via `on_clip_changed()`)
  - `current_clip_index` tracking in Player
  - `load_clip_by_index()` for direct index-based clip loading

- [x] **REST API (1-2h):** ✅ COMPLETED
  - POST `/api/player/{player_id}/set_master` → Aktiviert Master-Mode
  - GET `/api/player/sync_status` → Gibt Master/Slave Status zurück
  - Unified API: Master-State in Player-Status integrieren (`is_master`, `master_playlist`, `current_clip_index`)

- [x] **Frontend Integration (2h):** ✅ COMPLETED
  - Master-Toggle-Button in Playlist-Controls (neben Autoplay/Loop)
  - Master/Slave Status-Anzeige (Icon + Farbe)
  - API-Calls für Toggle-Actions
  - Visual Feedback bei Sync-Aktionen (grüner Rahmen auf aktiven Clip)
  - `updateMasterUI()` für visuelles Feedback
  - `pollSyncStatus()` für real-time Updates

**Funktionsweise:**
```
MASTER (Video Playlist):     [Clip1] [Clip2] [Clip3] [Clip4] ← Master aktiviert
                                                      ↓ Clip 4 aktiv
SLAVE (Art-Net Playlist):    [Clip1] [Clip2] [Clip3] [Clip4] → Springt zu Clip 4
                                                      ↑ Sync!

Master → Clip 5:             [Clip5] wird geladen
Slave:                       → Wechselt auch zu Clip 5 (sofort, mit eigener Transition)
```

**Vorteile:**
- Synchrone Shows mit mehreren Outputs (Video + Art-Net)
- Verschiedene Clips auf verschiedenen Ausgängen, aber synchroner Ablauf
- Master/Slave kann jederzeit gewechselt werden
- Jede Playlist behält ihre eigenen Effekte/Transitions

---

### 1.2 🔌 Plugin-System erweitern (~8-12h) ✅ COMPLETED (2025-12-07)

- [x] **Layer-Effekte über Clip FX Tab (8-12h):** ✅ COMPLETED
  - ✅ API-Endpoints für Layer-Effekte (Unified API: `/api/player/{player_id}/clip/{clip_id}/effects`)
  - ✅ Layer-Selection-Logik: Layer-as-Clips Architecture (jedes Layer hat eigene clip_id)
  - ✅ Clip FX Tab: Zeigt Layer-Effekte wenn Layer ausgewählt (via selectedLayerClipId)
  - ✅ API-Calls automatisch korrekt geroutet (targetClipId = selectedLayerClipId || selectedClipId)
  - ✅ Drag & Drop von Effekten funktioniert für Clip UND Layer
  - ✅ Backend: apply_layer_effects() vollständig integriert, Layer.effects Array populiert
  - ✅ Live-Effekt-Instanzen: API gibt live Parameter von aktiven Layer-Instanzen zurück
  - ✅ Unabhängige Layer-Effekte: Jedes Layer hat eigene Effekt-Instanzen (z.B. Transport, Transform)
  - ✅ Parameter-Updates: Direkte Updates auf live Layer-Effekt-Instanzen (nicht Registry)
  - ✅ Transport-Plugin: Timeline-Erkennung funktioniert pro Layer, Trim-Points persistieren
  - ✅ Opacity-Persistence: Layer-Opacity bleibt erhalten über Transport-Loops
  - **Key Fixes:**
    - API findet aktive Layer by clip_id und updated live Effekt-Instanzen
    - Transport prioritisiert layer.source über player.source für unabhängige Kontrolle
    - Keine unnötigen Layer-Reloads mehr (nur bei Clip-Wechsel, nicht bei Parameter-Updates)
    - Timeline auto-adjusts nur bei Default-Werten [0,100], respektiert User-Trim-Points

---

### 1.3 ⚡ WebSocket Command Channel - Zeitkritische Commands (~6-8h) 🔥 🚧 IN PROGRESS

**Problem:** Polling-Intervalle (250-3000ms) verursachen Latenz bei zeitkritischen Operationen.

**Lösung:** Hybrid-Ansatz - REST für Daten-Operations, WebSocket für Commands & Live-Updates.

#### Endpoints nach Mehrwert (absteigend):

**🔥 TIER 1 - Maximaler Mehrwert (Command Latency: ~50ms → ~2-5ms)**

- [ ] **Effect Parameter Updates (Live-Controls):**
  - `PUT /api/player/{id}/effects/{index}/parameter` → `ws://effect.param.update`
  - Aktuell: 500ms Polling für Live-Parameter (Brightness, Hue, etc.)
  - Mit WS: Instant bidirektionales Feedback (<5ms)
  - **Mehrwert: 100x schneller, 10x weniger Server-Load**

- [ ] **Layer Opacity/Blend Mode Updates:**
  - `PATCH /api/player/{id}/layers/{layer_id}` → `ws://layer.update`
  - Aktuell: HTTP Request pro Slider-Change (50-200ms Latency)
  - Mit WS: Real-time slider sync (<5ms)
  - **Mehrwert: Smooth UI, keine Lag-Spikes**

- [ ] **Transport Controls (Play/Pause/Stop/Next/Prev):**
  - `POST /api/player/{id}/play|pause|stop|next|previous` → `ws://player.command`
  - Aktuell: 20-100ms HTTP Round-Trip
  - Mit WS: <5ms Command Execution
  - **Mehrwert: Instant Response, MIDI/OSC-ready**

**🟡 TIER 2 - Hoher Mehrwert (Status Polling: 2000ms → Event-driven)**

- [ ] **Player Status Broadcast:**
  - `GET /api/player/{id}/status` → `ws://player.status` (Push statt Poll)
  - Aktuell: 2s Polling-Intervall (status_broadcast_interval)
  - Mit WS: Event-driven Updates bei Änderungen
  - **Mehrwert: 90% weniger Requests, instant UI-Updates**

- [ ] **Effect Chain Updates:**
  - `GET /api/player/{id}/effects` → `ws://effects.changed`
  - Aktuell: 2s Polling für Effect-List-Refresh
  - Mit WS: Nur bei Add/Remove/Reorder Events
  - **Mehrwert: 95% weniger Traffic**

- [ ] **Clip Progress Updates:**
  - `GET /api/player/{id}/status` (current_frame) → `ws://clip.progress`
  - Aktuell: 2s Polling für Trim-Slider-Sync
  - Mit WS: Real-time Progress (10-30 FPS)
  - **Mehrwert: Smooth Progress-Bars**

**🟢 TIER 3 - Mittlerer Mehrwert (Optimierung statt Latenz)**

- [ ] **Playlist Updates:**
  - `GET /api/player/{id}/playlist` → `ws://playlist.changed`
  - Aktuell: 500ms Polling bei Autoplay (nur aktiv wenn autoplay enabled)
  - Mit WS: Event bei Clip-Wechsel
  - **Mehrwert: 80% weniger Requests bei Autoplay**

- [ ] **Console/Log Streaming:**
  - `GET /api/logs` → `ws://logs.stream`
  - Aktuell: 3s Polling + throttled fetch
  - Mit WS: Real-time Log-Streaming
  - **Mehrwert: Live-Debugging, keine Polling-Delay**

**❌ NICHT WebSocket (bleiben REST):**
- File Operations (Upload, Convert, List) - zu große Payloads
- Configuration Changes - selten, keine Latenz-Kritik
- Playlist Save/Load - Daten-Operations, kein Live-Update
- Plugin/Generator Discovery - Einmalig beim Laden

#### Implementation Plan:

1. **Backend WebSocket Server (2h):**
   - Flask-SocketIO bereits vorhanden (rest_api.py:285)
   - Neue Namespaces: `/player`, `/effects`, `/layers`
   - Event-Emitter in Player-Klasse integrieren

2. **Frontend WebSocket Client (2h):**
   - `common.js` Socket.IO Connection erweitern
   - Event-Listener für Commands (Tier 1)
   - Auto-Reconnect & Fallback zu REST

3. **Hybrid Routing Layer (1h):**
   - `isSocketConnected()` Check vor Command
   - Fallback: WS failed → REST Request
   - Progressive Enhancement

4. **Testing & Rollout (1-2h):**
   - Latency Benchmarks (vorher/nachher)
   - Concurrent User Tests
   - Graceful Degradation Tests

**Expected Results:**
- Command Latency: 50-100ms → 2-5ms (**20-50x schneller**)
- Server Load: -85% bei Status/Effect-Requests
- UI Responsiveness: Instant Feedback für alle Controls
- Production-Ready: MIDI/OSC Controller Support möglich

---

### 1.4 🎬 Playlist-Sequenzer (~8-12h)

- [ ] **Show-Editor UI (4h):**
  - Liste von Clips mit Drag & Drop
  - Clip-Properties: Video/Script, Duration, Transition, Brightness

- [ ] **Persistence (2h):**
  - Save/Load Show-Dateien (JSON `.fluxshow`)
  - Show-Library (Liste aller Shows)

- [ ] **Playback Engine (4h):**
  - Sequential Playback mit Transitions
  - Cue-System (Next Cue, Jump to Cue N)
  - Loop-Mode

- [ ] **REST API (2h):**
  - GET/POST/PUT/DELETE `/api/sequencer/shows`
  - POST `/api/sequencer/play`, `/api/sequencer/stop`
  - POST `/api/sequencer/cue/<index>`

**JSON-Format Beispiel:**
```json
{
  "name": "Halloween Show 2025",
  "clips": [
    {"type": "video", "source": "kanal_1/intro.mp4", "duration": 15, "transition": "fade", "brightness": 1.0},
    {"type": "script", "source": "plasma", "duration": 30, "transition": "cut"}
  ],
  "loop": true
}
```

---

### 1.5 🎛️ Dynamische Parameter Sequenzen (~6-10h) 🆕

- [ ] **Automatisierte Parameter-Modulation über verschiedene Sequenz-Typen:**
  - **Grundidee:** Parameter können zeitbasierte Sequenzen abspielen statt statischer Werte
  - **UI-Konzept:**
    ```
    ⚙️ Parameter [Blur Strength: 5.0] |--▼----|-------▼--|
     └ Sequenz-Modus: [Dropdown ▼]
          ⊙ Manual (statisch)
          ⊙ Audio Reactive
          ⊙ Timeline
          ⊙ Envelope
          ⊙ LFO (Low-Frequency Oscillator)
    ```

- [ ] **Sequenz-Typen (6-8h):**
  
  - **Audio Reactive (2h):**
    - Bind Parameter an Audio-Feature (RMS, Peak, Bass, Mid, Treble, BPM)
    - Range-Mapping: Audio-Level (0-1) → Parameter-Range (min-max)
    - Smoothing-Filter: Attack/Release für sanfte Übergänge
    - Threshold: Nur triggern wenn Audio über Schwellwert
    - UI: Spektrum-Visualisierung + Live-Wert-Anzeige
  
  - **Timeline (2h):**
    - Keyframe-basierte Timeline (Zeit → Wert Paare)
    - Linear/Bezier/Step Interpolation zwischen Keyframes
    - Loop-Modes: Once, Loop, Ping-Pong
    - Sync mit Clip-Time oder Global-Time
    - UI: Mini-Timeline-Editor mit Keyframe-Punkten
  
  - **Envelope (1-2h):**
    - ADSR (Attack, Decay, Sustain, Release) Envelope
    - Trigger-Modes: On-Load, On-Beat, Manual
    - Duration & Curve-Shape pro Phase
    - UI: Visual ADSR-Curve mit Drag-Handles
  
  - **LFO (1-2h):**
    - Waveforms: Sine, Triangle, Square, Sawtooth, Random
    - Frequency (Hz) & Amplitude Control
    - Phase-Offset für mehrere LFOs sync
    - UI: Live-Waveform-Preview

- [ ] **Backend Implementation (2-3h):**
  - `ParameterSequencer` Klasse mit Sequenz-Engine
  - `SequencePlayer` pro Parameter-Binding
  - Integration in Effect-Pipeline (Parameter-Update-Loop)
  - Persistence: Sequenz-Config in Effect-Metadata
  - API: CRUD für Parameter-Sequenzen

- [ ] **REST API (1h):**
  - POST `/api/effects/{effect_id}/params/{param_name}/sequence` → Bind Sequenz
  - GET `/api/effects/{effect_id}/params/{param_name}/sequence` → Get Sequenz-Config
  - DELETE `/api/effects/{effect_id}/params/{param_name}/sequence` → Unbind (zurück zu Manual)
  - PUT `/api/effects/{effect_id}/params/{param_name}/sequence` → Update Sequenz-Settings

- [ ] **Frontend UI (2-3h):**
  - Sequenz-Button neben jedem Parameter (⚙️ Icon)
  - Modal/Sidebar für Sequenz-Editor
  - Type-Selector (Dropdown: Manual/Audio/Timeline/Envelope/LFO)
  - Type-spezifische Controls (Range-Mapper, Timeline-Editor, ADSR-Curve)
  - Live-Preview: Zeigt aktuellen modulierten Wert in Echtzeit
  - Visual Feedback: Parameter-Name wird farbig wenn Sequenz aktiv

**Use-Cases:**
- Audio-reactive Blur/Brightness (pulst mit Musik)
- Timeline-basierte Color-Shifts für exakte Timing-Kontrolle
- ADSR-Envelope für Impact-Effekte (z.B. Flash bei Beat)
- LFO für organische Bewegungen (z.B. wabernde Transforms)

**Config-Beispiel:**
```json
{
  "effect_id": "blur_01",
  "parameter_sequences": {
    "strength": {
      "type": "audio_reactive",
      "audio_feature": "bass",
      "range": {"min": 0.0, "max": 10.0},
      "smoothing": {"attack": 0.1, "release": 0.3}
    },
    "brightness": {
      "type": "lfo",
      "waveform": "sine",
      "frequency": 0.5,
      "amplitude": 0.3,
      "offset": 0.7
    }
  }
}
```

**Vorteile:**
- Lebendige, dynamische Effekte statt statischer Parameter
- Musik-synchrone Visuals ohne manuelle Automation
- Wiederverwendbare Sequenz-Presets
- Echtzeit-Modulation ohne Performance-Impact

---

### 1.6 🎹 MIDI-over-Ethernet Support (~6-10h)

- [ ] **MIDI Control via Ethernet (minimale Latenz) (6-10h):**
  - **Grundidee:** MIDI-Signale über Ethernet statt USB für <5ms Latenz
  - **WebSocket-MIDI (empfohlen):**
    - Web-MIDI API (Browser nativ)
    - Bidirektional (Server → Client Feedback)
    - <5ms Latenz (LAN), <20ms (WiFi)
  - **RTP-MIDI (optional):**
    - Standard-Protokoll (Apple MIDI-Network)
    - UDP-basiert (noch niedriger Latenz)
  - **Features:**
    - MIDI-Learn: Click auf Parameter → nächster MIDI-Input wird gemappt
    - Multi-Controller: Mehrere MIDI-Geräte gleichzeitig
    - Feedback: LED-Status zurück an Controller
    - Curve-Mapping: Linear, Exponential, Logarithmic
  - **Implementierung:**
    - Phase 1: WebSocket-MIDI-Handler (~2h)
    - Phase 2: MIDI-Mapping-Engine (~2h)
    - Phase 3: MIDI-Learn UI (~2h)
    - Phase 4: Client-Library (Browser) (~1h)
    - Phase 5: Feedback-System (~1h)
    - Phase 6: RTP-MIDI Support (optional) (~2h)

---

## ⚡ PRIORITÄT 2 - Mittel-Komplex, Hoch-Wert (~48-72h)
**Mittlerer bis hoher Aufwand, hoher Performance-Gewinn & Skalierbarkeit**

### 2.1 ⚡ WebSocket Command Channel (~4-6h) 🔥 PRIORITY

- [ ] **Zeitkritische Commands über WebSocket (Hybrid-Ansatz):**
  - **Problem mit REST:** 10-50ms Latenz pro Request
  - **WebSocket-Vorteile:** 2-5ms Latenz (LAN), Persistent Connection
  - **Architektur-Entscheidung:**
    - ✅ **WebSocket für Commands** (sofortiger Mehrwert)
    - ⏸️ **WebRTC für Video** später optional (nur bei CPU-Problemen)
  - **Zeitkritische Commands:**
    - Playback: play, pause, stop, seek
    - Parameter: brightness, speed, effect_param
    - Blackout: sofortiger Blackout-Toggle
  - **Features:**
    - Auto-Reconnect bei Verbindungsabbruch
    - Event-basiert (einfach erweiterbar)
    - Broadcast an alle Clients (Multi-User)
    - Command-Queue mit Priority-System
    - Batch-Commands
    - MessagePack Support (optional)
  - **Implementierung:**
    - Phase 1: Flask-SocketIO Integration (~1h)
    - Phase 2: WebSocket Command Handler (~2h)
    - Phase 3: Command-Queue & Priority (~1h)
    - Phase 4: Client-Library (JavaScript) (~1h)
    - Phase 5: MessagePack Support (optional) (~1h)
  - **Latenz-Verbesserung:**
    - REST: 10-50ms → WebSocket: 2-5ms (LAN)
    - Responsiveness-Gewinn: 5-25x schneller

**Code-Beispiel:**
```javascript
// Vorher (REST): 15-50ms Latenz
await fetch('/api/player/video/play', {method: 'POST'});

// Nachher (WebSocket): 2-5ms Latenz
socket.emit('player.play', {player_id: 'video'});
socket.on('player.status', (data) => console.log(data));
```

---

### 2.2 🖥️ Multi-Video Render Cluster (~40-60h)

- [ ] **Synchronisierte Multi-Server-Architektur für skalierbare Video-Ausgabe:**
  - **Grundidee:** Mehrere Render-Nodes (PCs/Server) für parallele Video-Displays
  - **Architektur Pattern:** Master-Slave Cluster mit WebSocket Command Sync
  
- [ ] **Core Features:**
  - **Cluster Manager (8-12h):**
    - Node Discovery (mDNS/Broadcast)
    - Health Checks & Auto-Failover
    - Leader Election (Raft-ähnlich)
    - Cluster Status Dashboard
  
  - **Command Sync Engine (10-15h):**
    - WebSocket Command Broadcast (Master → Slaves)
    - Timestamp-ordered Render Queue
    - Command Deduplication & Validation
    - Retry Logic & Acknowledgments
  
  - **State Replication (8-12h):**
    - Full State Snapshot (on Node Join)
    - Delta Updates (incremental sync)
    - MVCC (Multi-Version Concurrency Control)
    - Conflict Resolution
  
  - **Render Synchronization (8-12h):**
    - NTP Time Sync Integration (±1ms accuracy)
    - Frame Target Calculation (`target_time = base_time + frame_index * frame_duration`)
    - VSync Lock Mode (GPU waits on VSync for <1ms jitter)
    - Drift Monitoring & Correction
  
  - **Monitoring & Debugging (6-9h):**
    - Cluster Dashboard (Node Status, Network Lag, Frame Drift)
    - Performance Metrics (FPS per Node, Sync Jitter)
    - Command History & Replay
    - Network Topology Visualization

- [ ] **Technical Details:**
  - **Sync Mechanism:**
    ```python
    # Master broadcasts command:
    {
      "type": "render.frame",
      "timestamp": 1733404800.500,  # NTP-synchronized time
      "frame_index": 1234,
      "player_state": {...},
      "effect_params": {...},
      "vsync_lock": true  # GPU waits on VSync
    }
    # Slaves execute at exact timestamp
    ```
  
  - **Latency Budget:**
    - WebSocket Broadcast: 2-10ms (LAN)
    - NTP Sync Accuracy: ±1ms
    - VSync Jitter: <1ms (hardware-accelerated)
    - **Total System Jitter: <11ms** (acceptable for live shows)
  
  - **Video Output Scaling:**
    - Modern GPU: 4-8 HDMI/DP outputs per card
    - 4 Render Nodes × 4 Outputs = **16 synchronized displays**
    - 10 Render Nodes × 8 Outputs = **80 synchronized displays**
  
  - **Advantages over Art-Net Clustering:**
    - ✅ VSync hardware sync (<1ms jitter vs Art-Net 44Hz limitations)
    - ✅ Zero network overhead for frame data (each node renders locally)
    - ✅ Higher resolution (4K per display vs 512 DMX channels)
    - ✅ Simpler implementation (GPU driver handles sync)

- [ ] **Use Cases:**
  - Massive video walls (16-64+ synchronized displays)
  - Multi-projector mapping with edge blending
  - Immersive environments (360° projections, domes)
  - Mixed output (video displays + Art-Net LED strips hybrid)
  - Corporate installations (distributed campus displays)

- [ ] **Configuration Example:**
  ```json
  {
    "cluster": {
      "mode": "master",  // or "slave"
      "master_address": "192.168.1.100:5001",
      "node_id": "render_node_1",
      "sync": {
        "ntp_server": "pool.ntp.org",
        "vsync_lock": true,
        "max_drift_ms": 5
      },
      "outputs": [
        {"id": "HDMI-1", "resolution": "1920x1080", "position": [0, 0]},
        {"id": "HDMI-2", "resolution": "1920x1080", "position": [1920, 0]},
        {"id": "DP-1", "resolution": "3840x2160", "position": [3840, 0]}
      ]
    }
  }
  ```

- [ ] **Implementation Phases:**
  - Phase 1: Cluster Manager & Node Discovery (8-12h)
  - Phase 2: Command Sync Engine (10-15h)
  - Phase 3: State Replication (8-12h)
  - Phase 4: Render Sync & NTP Integration (8-12h)
  - Phase 5: Monitoring Dashboard (6-9h)

**Rationale:** Strategisch wichtig für große Installationen. Video-Clustering ist BESSER als Art-Net-Clustering aufgrund Hardware-Sync, null Netzwerk-Overhead für Frames, und höhere Auflösung. Kommt nach P1 (Basis-Features) und P2 (Master/Slave für einzelne Instanz).

---

### 2.3 🌐 Multi-Network-Adapter Support (~4-6h)

- [ ] **Separate Netzwerk-Interfaces:**
  - **Grundidee:** Control-Traffic (API) getrennt von Art-Net-Output
  - **Features:**
    - API-Binding auf spezifisches Interface
    - Art-Net-Routing: Universes auf verschiedenen Adaptern
    - Multi-Art-Net: Mehrere Art-Net-Netzwerke parallel
    - Failover: Automatischer Switch auf Backup-Adapter
  - **Use-Cases:**
    - Adapter 1: Management (192.168.1.x)
    - Adapter 2: Art-Net Output 1 (10.0.0.x)
    - Adapter 3: Art-Net Output 2 (10.0.1.x)
  - **Implementierung:**
    - Phase 1: Network-Interface-Discovery (~1h)
    - Phase 2: API-Binding-Config (~1h)
    - Phase 3: Art-Net Multi-Adapter-Routing (~2h)
    - Phase 4: UI (Network-Adapter-Auswahl) (~1h)

**Config-Beispiel:**
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

## 🔧 PRIORITÄT 3 - Mittel-Komplex, Mittel-Wert (~39-57h)
**Mittlerer Aufwand, mittlere Business-Priorität**

### 3.1 🎥 WebRTC Video Preview ✅ COMPLETED (~8h)

- [x] **Hardware-beschleunigtes Video-Streaming:** ✅ COMPLETED (2025-12-08)
  - **Performance Improvement:**
    - CPU Usage: 40-60% → 5-10% (**10x reduction**)
    - Bandwidth: 2-5 Mbps → 0.2-1 Mbps (**5x reduction**)
    - Latency: 100-200ms → <100ms (**2x faster**)
  - **Implemented Features:**
    - ✅ Hardware-accelerated H.264 encoding (GPU via aiortc)
    - ✅ Multi-Quality: Low (360p, 15fps), Medium (720p, 20fps), High (1080p, 30fps)
    - ✅ Adaptive FPS control (10-30 FPS)
    - ✅ Connection limit: Max 5 concurrent preview clients
    - ✅ Automatic MJPEG fallback on WebRTC failure
    - ✅ UI controls: Quality selector + mode toggle
    - ✅ Real-time stats display (FPS + bandwidth)
    - ✅ WebRTC signaling API (/api/webrtc/offer, /api/webrtc/close, /api/webrtc/stats)
    - ✅ Full documentation (docs/WEBRTC_PREVIEW.md)
  - **Backend Implementation:**
    - `src/modules/webrtc_track.py`: PlayerVideoTrack class
    - `src/modules/api_webrtc.py`: WebRTC signaling endpoints
    - Integration with rest_api.py
  - **Frontend Implementation:**
    - `frontend/js/webrtc-preview.js`: WebRTCPreview class
    - Integration in player.js + player.html
    - Quality selector dropdown
    - Mode toggle button (WebRTC ↔ MJPEG)
    - Live stats display
  - **Testing:**
    - Verify WebRTC connection establishes
    - Test quality switching (requires reconnection)
    - Test automatic MJPEG fallback
    - Monitor CPU/bandwidth improvements

---

### 3.2 🎵 Audio-Reactive Support (~10-14h)

- [ ] **Audio-Input (4h):**
  - Microphone-Input (pyaudio/sounddevice)
  - System-Audio-Capture (WASAPI Loopback)
  
- [ ] **Audio-Analyse (3h):**
  - FFT (Bass/Mid/Treble Frequenz-Bänder)
  - BPM-Detection (tempo tracking)
  - Onset-Detection (Beat-Trigger)
  
- [ ] **Reaktive Parameter (3h):**
  - Brightness ← RMS/Peak-Level
  - Speed ← BPM
  - Color ← Frequenz-Mapping
  - Effect-Intensity ← Audio-Level
  
- [ ] **UI & API (2h):**
  - Audio-Device-Auswahl
  - Live-Spektrum-Anzeige
  - Parameter-Mapping-Editor

---

---

## 🚀 PRIORITÄT 4 - Hoch-Komplex, Hoch-Wert (~48-76h)
**Hoher Aufwand, strategisch wichtig**

### 4.1 🔮 Neue Frame Sources (~12-20h)

- [ ] **ShaderToy Source (8-12h):**
  - ModernGL/PyOpenGL Integration
  - GLSL Shader Support (Shadertoy-kompatibel)
  - Uniform Variables (iTime, iResolution, iMouse)

- [x] **LiveStream Source (2-5h):** ✅ COMPLETED
  - RTSP/HTTP/HLS/RTMP Stream Support
  - FFmpeg Integration via OpenCV
  - YouTube URL Support (yt-dlp)

---

### 4.2 🎥 Projection Mapping Support (~16-24h)

- [ ] **Projection Mapping System (16-24h):**
  - **Grundidee:** Video-Content auf reale Objekte projizieren mit Warp & Blend
  - **Projektor-Kalibrierung:**
    - Corner-Pin: 4-Punkt-Perspektiven-Korrektur
    - Mesh-Warping: Grid-basierte Verzerrung (z.B. für gekrümmte Flächen)
    - Auto-Alignment: Marker-Detection für automatische Kalibrierung
    - Multi-Projektor-Setup: Overlap-Bereiche definieren
  - **Edge-Blending:**
    - Soft-Edge-Overlap: Sanfter Übergang zwischen Projektoren
    - Brightness-Matching: Angleichung der Helligkeit in Overlap-Bereichen
    - Color-Matching: Farbkalibrierung zwischen Projektoren
    - Feather-Width: Konfigurierbare Blending-Zone (0-20% Overlap)
  - **Projection Zones:**
    - Zone-Definition: Mehrere Projektions-Bereiche pro Projektor
    - Content-Mapping: Verschiedene Videos pro Zone
    - Layer-Support: Mehrere Layer pro Zone mit Compositing
    - Mask-Support: Alpha-Masken für Zone-Grenzen
  - **Beamer-Stacking:**
    - Brightness-Boost: Mehrere Projektoren auf gleiche Fläche
    - HDR-Simulation: Stacking für höheren Kontrast
    - Sync-Modes: Frame-Lock zwischen gestackten Projektoren
    - Alignment-Tools: Pixel-genaue Ausrichtung
  - **Visualisierung & Setup:**
    - Separate HTML-Page: `projection-mapper.html`
    - Live-Preview mit Warping
    - Test-Pattern-Generator (Grid, Circles, Checkerboard)
    - Export/Import von Projection-Setups
  - **Implementierung:**
    - Phase 1: Corner-Pin & Mesh-Warp Engine (~3h)
    - Phase 2: Edge-Blending Algorithm (~3h)
    - Phase 3: Multi-Projektor-Routing (~2h)
    - Phase 4: Beamer-Stacking Support (~2h)
    - Phase 5: Projection Zone Management (~3h)
    - Phase 6: UI (Mapping-Editor, Test-Patterns) (~4h)
    - Phase 7: API-Endpoints (Setup CRUD) (~2h)

**Use-Cases:**
- Gebäude-Projektionen (Facade-Mapping)
- Theater & Bühnen-Projektionen
- Event-Installationen mit Multi-Projektor-Setups
- Museum-Installationen (Objekt-Projektionen)
- Immersive Environments (360° Projektionen)

**Config-Beispiel:**
```json
{
  "projection_mapping": {
    "projectors": [
      {
        "id": "proj_left",
        "output": "strip_1",
        "corner_pin": [[0,0], [1920,0], [1920,1080], [0,1080]],
        "mesh_warp": "grid_5x5_curved.json",
        "brightness": 1.0,
        "zones": [
          {
            "id": "zone_left_wall",
            "content_rect": {"x": 0, "y": 0, "width": 1920, "height": 1080},
            "mask": "wall_mask.png"
          }
        ]
      },
      {
        "id": "proj_right",
        "output": "strip_2",
        "corner_pin": [[0,0], [1920,0], [1920,1080], [0,1080]],
        "edge_blend": {
          "enabled": true,
          "overlap_left": {"width": 200, "feather": 0.5},
          "brightness_match": 0.95
        }
      },
      {
        "id": "proj_center_stacked",
        "output": "strip_3",
        "stacking": {
          "enabled": true,
          "stack_with": "proj_center_base",
          "sync_mode": "frame_lock",
          "brightness_boost": 1.8
        }
      }
    ]
  }
}
```

---

### 4.3 🎥 Multi-Video-Routing per Art-Net-Objekt (~20-28h)

- [ ] **Grundidee:** Mehrere Videos gleichzeitig, jedes LED-Objekt bekommt eigenes Video/Generator
- [ ] **Architektur:**
  - Mehrere Player-Instanzen parallel (Video1, Video2, Video3)
  - LED-Objekte definieren (Name, Universe-Range, Pixel-Count)
  - Routing-Config: `{"object": "strip_1", "video_player_id": "video_1"}`
  
- [ ] **Kartendeck-UI mit Slot-Compositing:**
  - **Slot-Struktur (Kartendeck-Metapher):**
    - Slot = Playlist-Position mit gestapelten Clip-Alternativen (wie Kartendeck 🎴)
    - Minimiert: Zeigt Icon + Anzahl (`[3 Clips] 🎴`)
    - Ausklappen: Zeigt alle Clips im Stack mit Compositing-Settings
  
  - **Compositing innerhalb eines Slots:**
    - Alle Clips im Slot laufen parallel (Layer-Stack)
    - Werden automatisch übereinander komponiert
    - Jeder Clip hat eigene Effect-Chain
    - Blend Mode pro Clip (Normal, Multiply, Screen, Overlay, Add, Subtract)
    - Opacity pro Clip (0-100%)
    - Layer-Reihenfolge via Drag & Drop änderbar
  
  - **Sequential zwischen Slots:**
    - Slot 1 → Slot 2 → Slot 3 (mit Transitions)
    - Transition-Effekte zwischen Slots (Fade, Wipe, Dissolve, etc.)
    - Auto-Next oder manueller Trigger (Button/Keyboard/MIDI)
    - Loop-Mode für Slot-Sequenz
  
  - **Trigger-Modi pro Slot:**
    - **Manual:** Button-Click oder Keyboard (Nummerntaste)
    - **Auto:** Nach Duration automatisch zum nächsten Slot
    - **Random:** Zufälliger Slot aus Sequenz
    - **MIDI:** MIDI-Note triggert spezifischen Slot
  
  - **Pro Clip im Slot:**
    - Eigene Effect-Chain
    - Blend Mode & Opacity (für Compositing)
    - Weight für Random-Auswahl (bei mehreren Clips)
    - Auto-Loop oder Play-Once
  
  - **Pro Slot:**
    - Name/Label (z.B. "Intro Varianten", "Drop", "Outro")
    - Duration (für Auto-Mode)
    - Transition zum nächsten Slot (Type + Duration)
    - Output-Routing (LED-Objekt-Zuweisung)
    - Enable/Disable Toggle

- [ ] **Implementierung:**
  - Phase 1: LED-Objekt-Definition & Config (~2h)
  - Phase 2: Slot-Manager (Slot-Sequenz, Trigger-System) (~3h)
  - Phase 3: Layer-Compositor für Slot-Compositing (Blend Modes, Opacity) (~3h)
  - Phase 4: Transition-System zwischen Slots (~2h)
  - Phase 5: Routing-System & Frame-Collection (~2h)
  - Phase 6: API-Endpoints (Slot CRUD, Clip Management, Trigger) (~3h)
  - Phase 7: UI (Kartendeck-View, Ausklapp-Mechanik, Compositing-Controls) (~5h)

**JSON-Config Beispiel:**
```json
{
  "led_objects": [
    {"name": "strip_left", "universes": [1,2], "pixels": 200},
    {"name": "strip_right", "universes": [3,4], "pixels": 200},
    {"name": "panel_center", "universes": [5,6], "pixels": 256}
  ],
  "slots": [
    {
      "slot_id": 1,
      "name": "Intro Varianten",
      "duration": 30,
      "clips": [
        {
          "path": "intro_v1.mp4",
          "effects": [{"plugin_id": "blur", "params": {"strength": 2.0}}],
          "blend_mode": "normal",
          "opacity": 100,
          "layer_order": 0
        },
        {
          "path": "generator:plasma",
          "effects": [],
          "blend_mode": "multiply",
          "opacity": 50,
          "layer_order": 1
        }
      ],
      "transition_to_next": {"type": "fade", "duration": 1.5},
      "output_routing": {"led_object": "strip_left"}
    },
    {
      "slot_id": 2,
      "name": "Drop Section",
      "duration": 60,
      "clips": [
        {"path": "drop_bg.mp4", "blend_mode": "normal", "opacity": 100},
        {"path": "generator:fire", "blend_mode": "screen", "opacity": 70},
        {"path": "overlay.mp4", "blend_mode": "add", "opacity": 40}
      ],
      "transition_to_next": {"type": "wipe_left", "duration": 0.5},
      "output_routing": {"led_object": "strip_left"}
    }
  ]
}
```

---

### 4.4 🖥️ Video Wall Slicing Support (~8-12h)

- [ ] **Multi-Display Video Slicing (8-12h):**
  - **Grundidee:** Ein Video auf mehrere Displays/LED-Matrizen aufteilen
  - **Slice Configuration:**
    - Definition von Slice-Bereichen (x, y, width, height)
    - Zuweisung von Slices zu LED-Objekten/Displays
    - Grid-basierte Slice-Definition (z.B. 3x2 Grid = 6 Displays)
    - Custom Slice-Bereiche für unregelmäßige Layouts
  - **Slice Transform Plugin:**
    - Neuer Effect-Plugin-Typ: `slice_transform`
    - Parameter: `slice_id`, `x_offset`, `y_offset`, `width`, `height`
    - Anwendbar auf Player-Level oder Layer-Level
    - Unterstützt Multi-Layer-Compositing (jeder Layer kann gesliced werden)
  - **Slice Routing:**
    - Mapping: Slice → LED-Objekt/Universe-Range
    - Multi-Player-Support: Verschiedene Slices an verschiedene Player
    - Overlap-Detection: Warnung bei überlappenden Slices
  - **Slice Map Visualisierung:**
    - Separate HTML-Page: `slice-mapper.html`
    - Visual Grid-Editor mit Drag & Drop
    - Live-Preview aller Slices
    - Export/Import von Slice-Konfigurationen
  - **Implementierung:**
    - Phase 1: Slice Configuration Schema (~1h)
    - Phase 2: Slice Transform Plugin (~2h)
    - Phase 3: Slice Routing Engine (~2h)
    - Phase 4: API-Endpoints (Slice CRUD) (~1h)
    - Phase 5: Slice Map Visualisierung (~3h)
    - Phase 6: Live-Preview Integration (~1h)

**Use-Cases:**
- LED-Matrix-Wände (z.B. 6x 60x300 Pixel = 180x300 Video Wall)
- Multi-Display-Setups (3x2 Monitore als eine große Fläche)

**Config-Beispiel:**
```json
{
  "video_wall": {
    "slices": [
      {
        "id": "slice_top_left",
        "source_rect": {"x": 0, "y": 0, "width": 60, "height": 150},
        "target": "strip_1",
        "universes": [1, 2]
      },
      {
        "id": "slice_top_right",
        "source_rect": {"x": 60, "y": 0, "width": 60, "height": 150},
        "target": "strip_2",
        "universes": [3, 4]
      },
      {
        "id": "slice_bottom_left",
        "source_rect": {"x": 0, "y": 150, "width": 60, "height": 150},
        "target": "strip_3",
        "universes": [5, 6]
      },
      {
        "id": "slice_bottom_right",
        "source_rect": {"x": 60, "y": 150, "width": 60, "height": 150},
        "target": "strip_4",
        "universes": [7, 8]
      }
    ]
  }
}
```

---

## 🎨 PRIORITÄT 5 - Niedrig-Komplex, Niedrig-Priorität (~14-20h)
**Maintenance, Polishing, Nice-to-have**

### 5.1 🔌 Plugin-System (Optional) (~2-3h)

- [ ] **Preset System für Effect Parameters (2-3h):**
  - Effect-Preset-Speicherung (Name + Parameter-Werte)
  - Preset-Library pro Effect-Plugin
  - UI: Save/Load/Delete Presets im Effect-Panel
  - API: `/api/effects/<effect_id>/presets` CRUD
  - Dokumentation: `docs/EFFECT_PRESETS.md`

---

### 5.2 🎨 GUI-Optimierungen (~12-18h)

- [ ] **Art-Net Preview Expansion (4-6h):**
  - **Realtime LED Object Visualization:**
    - Live-View aller LED-Objekte mit aktuellen Farben
    - 2D-Representation: LED-Strip/Matrix als Pixel-Reihe
    - Farbcodierung: RGB-Werte als colored boxes
    - Auto-Update: 10-30 FPS live refresh
  - **Object-List View:**
    - Universe-Info pro Objekt (Universe 1-4, etc.)
    - Pixel-Count & Status (Online/Offline)
    - DMX-Address-Range anzeigen
  - **Features:**
    - Toggle zwischen Compact-View (Icons) und Expanded-View (Full Colors)
    - Click auf Objekt → Highlight in Preview
    - Color-Picker: Click auf Pixel → zeigt RGB-Wert
    - Performance-Mode: Reduced FPS bei niedriger CPU
  - **Implementierung:**
    - Phase 1: WebSocket für Live-DMX-Data (~2h)
    - Phase 2: Canvas-Renderer für LED-Objects (~2h)
    - Phase 3: UI-Controls & Toggle (~1h)
    - Phase 4: Performance-Optimierung (~1h)

- [ ] **Drag & Drop Layout-Editor:**
  - GridStack.js Integration
  - Panels frei verschieben & resizen
  - LocalStorage-Persistierung
  - Preset-Layouts: "Standard", "Video-Focus", "Compact"

---

### 5.3 🧪 Testing & Verification

- [ ] **Milkdrop via Screencapture testen:**
  - Screencapture-Generator mit Milkdrop/projectM-Fenster
  - Region-Capture für optimale Performance
  - Alternative: Window-Capture API

- [x] **Multi-Layer System Testing (~2-4h):** ✅ COMPLETED (2025-12-02)
  - ✅ Run `tests/test_api_layers.py` to verify all tests pass
  - ✅ Test live multi-layer playback with different FPS sources
    - ✅ Verify: Overlay läuft nicht doppelt so schnell bei höherer FPS
    - ✅ Verify: Frame-Skipping funktioniert bei niedrigerer FPS
  - ✅ Verify snapshot restore with layers
  - ✅ Test generator + video layer combinations
  - ✅ Test layer with effects + blend modes
  - ✅ Test autoplay with multi-layer clips
  - ✅ Test transitions on layer 0 with overlays active

### 5.4 🛠️ Weitere Verbesserungen

- [ ] **File Browser Thumbnails (~6-10h):**
  - **Thumbnail Generation:**
    - Video: Erstes Frame als Thumbnail (FFmpeg -ss 0 -vframes 1)
    - Image: Resized Preview (Pillow/OpenCV)
    - Cache-System: Thumbnails in `data/thumbnails/` speichern
    - Lazy-Loading: Thumbnails on-demand generieren
  - **UI Features:**
    - Toggle-Button: Enable/Disable Thumbnail-Anzeige
    - List-View: Thumbnail neben Dateinamen (50x50px)
    - Tree-View: Thumbnail neben File-Icon (40x40px)
    - Hover-Popup: Größeres Preview (200x200px) bei Mouse-Hover
    - Loading-State: Spinner während Thumbnail-Generation
  - **Performance:**
    - Thumbnail-Size: 100x100px (JPEG, 85% Qualität)
    - Max. Generation-Time: 500ms pro Video
    - Batch-Generation: API-Endpoint `/api/files/thumbnails/generate`
    - Cache-Cleanup: Alte Thumbnails nach 30 Tagen löschen
  - **Implementation:**
    - Phase 1: Thumbnail-Generator (FFmpeg + Pillow) (~2h)
    - Phase 2: Cache-System & API (~2h)
    - Phase 3: FilesTab UI Integration (~2h)
    - Phase 4: Toggle & Settings (~1h)

- [ ] **Vollständige Player/Playlist-Generalisierung (~8-12h):**
  - Hardcodierte Playlist-Arrays entfernen (`videoFiles`, `artnetFiles`)
  - Hardcodierte Current-Item-IDs zu `playerConfigs[playerId].currentItemId` migrieren
  - Spezifische Lade-Funktionen (`loadVideoFile`, `loadArtnetFile`) durch generische Funktion mit `playerId` Parameter ersetzen
  - HTML/UI dynamisch aus `playerConfigs` generieren (Player-Container, Buttons)
  - Legacy-onclick-Handler (`window.playVideo`, etc.) entfernen und durch generische Event-Handler ersetzen
  - **Ziel:** Neuer Player nur durch Hinzufügen in `playerConfigs` möglich, ohne Code-Änderungen

- [x] **Playlist Playback Refactoring (~4-6h):** ✅ COMPLETED
  - ✅ Überarbeitung Loop/Autoplay/Play-Funktionen
  - ✅ Clip-Add-Handling vereinheitlichen
  - ✅ Auto-Start beim ersten Clip konsistent implementieren
  - ✅ State-Management zwischen Frontend/Backend synchronisieren
  - **Note:** Implemented with session_state.py persistence, autoplay/loop toggles, and consistent clip handling

- [x] **player.js Performance-Optimierung (~6-10h):** ✅ COMPLETED - Already Optimized
  - ✅ **Event-Handler-Leak behoben:** Event-Delegation implementiert (Lines 1689-1936)
    - Memory-Leak behoben durch Event-Delegation Pattern
    - 4 Event-Listener pro Container (statt 15-20 pro Item)
    - Handler Cleanup on Re-Render implementiert
    - **Einsparung: 40-60% Memory**
  - ✅ **Generator-Map für O(1) Lookups:** Map-basierte Lookups implementiert (Lines 21-23, 381, 436)
    - effectsMap und generatorsMap nutzen Map.get() statt Array.find()
    - Alle Hot-Paths verwenden Map-Lookups (Lines 507, 896, 996, 1013)
    - Nur 1x Array.find() Fallback (Line 1718, defensive coding, <1% impact)
    - **Einsparung: 5-10% CPU**
  - ✅ **Unified Update-Loop:** Intelligenter koordinierter Update-Loop (Lines 190-227)
    - Single setInterval (250ms) mit koordinierten Sub-Intervallen
    - Conditional Updates: nur bei Autoplay/Clip-Selection aktiv
    - 3 separate Timer zu 1 koordiniertem Loop kombiniert
    - **Einsparung: 10-15% CPU**
  - ✅ **DOM-Query-Caching:** Minimal querySelector usage
    - Nur 1x querySelectorAll() in dragend (Line 1781, nur bei Drag-Operations)
    - Event-Delegation verhindert wiederholte Queries
    - **Impact: <1% (drag operations sind selten)**
  - ✅ **Bereits implementiert:**
    - Fast-poll für Live-Parameter (500ms updateClipEffectLiveParameters) ohne Re-Rendering
    - Separate Update-Intervalle für Video/Art-Net/Clip-Effects
    - Conditional Updates (nur wenn nötig)
  - **Gesamt-Ergebnis:** ~50-75% CPU/Memory Reduction achieved
  - **Dokumentation:** `PERFORMANCE_ANALYSIS_PLAYER.md` (detaillierte Analyse)
  - **Fazit:** ✅ Keine weitere Optimierung notwendig, Performance-Budget erfüllt

- [x] **Projekt-Struktur Refactoring (~2-3h):** ✅ COMPLETED (2025-12-04)
  - ✅ `src/plugins/` → `plugins/` (nach Root verschoben)
  - ✅ `src/static/` → `frontend/` (nach Root verschoben + umbenannt)
  - **Vorteile:**
    - Klare Trennung: Backend (`src/`) vs Frontend (`frontend/`) vs Plugins (`plugins/`)
    - Bessere Übersicht: Plugins sind Top-Level (wie Config)
    - Standard-Konvention: Viele Projekte nutzen `frontend/` statt `static/`
  - **Durchgeführte Änderungen:**
    - Plugin-Verzeichnis: `plugin_manager.py` nutzt jetzt `plugins/`
    - Flask static_folder: `rest_api.py` zeigt auf `../frontend`
    - Test-Imports: `test_blend_*.py` nutzen `from plugins.effects`
    - Alle Plugin-Dateien nutzen bereits `from plugins import` (keine Änderung nötig)

- [ ] Unit Tests erweitern (Player, FrameSource, API)
- [ ] API-Authentifizierung (Basic Auth/Token)
- [ ] PyInstaller EXE Build Setup
- [ ] Environment Variable Support für config.json
- [ ] JSON Schema Validation für config.json
- [ ] Hot-Reload (config.json watcher)
- [ ] Dockerfile erstellen

---

## 🔬 PRIORITÄT 6 - Optional / Langfristig (~64-86h)
**Zukünftige Features mit hohem Aufwand**

### 6.1 ⏱️ Script-basierter Sequenzer (Optional, ~4-6h)

- **Power-User Feature:** Python-DSL für Show-Definition
- **Features:** CLI-Befehl, Script-Loader, Volle Python-Kontrolle
- **Empfehlung:** Nice-to-have, niedrige Priorität

---

### 6.2 📈 Timeline-Sequenzer (Optional, ~60-80h)

- Upgrade von Playlist-Sequenzer zu visueller Timeline
- Features: Clip-Trimming, Scrubbing, Multi-Track, Audio-Sync
- **Nur bei komplexeren Anforderungen**

---

## 📊 Zusammenfassung nach Priorität

| Priorität | Aufwand | Nutzen | Summe Stunden |
|-----------|---------|--------|---------------|
| **P1** | Niedrig | Hoch | ~45-69h (+7-10h Unified +2-3h Presets +6-8h WS) |
| **P2** | Mittel-Hoch | Sehr Hoch | ~48-72h (+40-60h Multi-Video Cluster) |
| **P3** | Mittel | Mittel | ~16-31h |
| **P4** | Hoch | Hoch | ~48-76h |
| **P5** | Niedrig | Niedrig | ~12-18h (Presets → P1 verschoben) |
| **P6** | Sehr Hoch | Mittel | ~64-86h |
| **GESAMT** | | | **~233-352h** (+40-60h Multi-Video Cluster)

---

## 🎯 Empfohlene Umsetzungs-Reihenfolge

### Phase 1: Foundation & Performance (P1) - ~45-69h 🔥 PRIORITY
1. **Unified Playlist System (7-10h)** ← Zuerst! (Basis für alles weitere, -200 Zeilen Code)
2. Master/Slave Playlist Sync (8-14h)
3. Plugin-System erweitern - Layer-Effekte (8-12h)
4. Preset System für Effect Parameters (2-3h)
5. **WebSocket Command Channel (6-8h)** ← Performance-Boost! (20-50x schnellere Commands)
6. Playlist-Sequenzer (8-12h)
7. MIDI-over-Ethernet Support (6-10h)

**Ziel:** Saubere Code-Basis → Vollständige Show-Control → Production-ready Performance

**Warum diese Reihenfolge?**
- **Unified Playlist zuerst:** Bereinigt Code-Basis, macht alle weiteren Features einfacher
- **Master/Slave danach:** Baut auf sauberem Playlist-System auf
- **Layer-Effekte + Presets:** Vervollständigt Plugin-System vor Performance-Optimierung
- **WebSocket am Ende:** Optimiert dann das bereits funktionierende System (85% weniger Server-Load)

---

### Phase 2: Multi-Network (P2) - ~8-12h
1. Multi-Network-Adapter Support

**Ziel:** Multi-Universe Art-Net auf verschiedenen Netzwerk-Interfaces

---

### Phase 3: Content (P3) - ~16-31h
1. Audio-Reactive Support
2. WebRTC Video Preview (optional - nur bei CPU-Problemen)

**Ziel:** Audio-Reactive Effects & Optional Video-Streaming-Optimierung

---

### Phase 4: Advanced (P4) - ~24-40h
1. Multi-Video-Routing mit Kartendeck-UI
2. Neue Frame Sources (ShaderToy, LiveStream)

**Ziel:** Multi-Output-Setups & Advanced Content-Sources

---

### Phase 5+: Polish & Future (P5+P6) - ~78-107h
1. GUI-Optimierungen
2. Maintenance & Tests
3. Optional: Timeline-Sequenzer

**Ziel:** Production-Polishing & Langzeit-Features

---

## 📚 Status (Stand: 2025-12-02)

### ✅ Fertiggestellt (v2.3)
- **Unified API Architecture** mit UUID-basiertem Clip-Management
- **Dual-Player-System** (Video Preview + Art-Net Output)
- **Plugin-System** vollständig implementiert (PluginBase, PluginManager, API)
- **18 Effect-Plugins:** 11 Farb-Manipulation, 5 Time & Motion, 1 Blur, 1 Blending
- **ClipRegistry** mit UUID-basierter Clip-Identifikation
- **Code-Cleanup** (~1500 Zeilen deprecated Code entfernt)
- **Universal Search Filter** für Effects, Sources, Files (v2.3.1)
- **Multi-Video-Source Support** via `video_sources` config (v2.3.1)
- **Default Effect Chains** via config.json (Player & Clip-Level) (v2.3.1)
- **Transition Plugin System** mit Fade Transition & Reusable UI Component (v2.3.1)
- **Multi-Layer Compositing System** (v2.3.2):
  - Clip-based layers (per playlist item)
  - Layer 0 = base clip (immutable)
  - Overlay layers with blend modes (Normal, Multiply, Screen, Overlay, Add, Subtract)
  - Per-layer opacity control (0-100%)
  - Layer CRUD API (`/api/clips/{clip_id}/layers`)
  - Drag-drop layer management in UI
  - Thread-safe layer loading with auto-reload
  - Session state persistence for layers
- **Clip Trimming System** (v2.3.3):
  - In/Out Points pro Clip mit Non-Destructive Editing
  - Reverse Playback Support
  - Ion.RangeSlider UI mit Collapsible Section
  - Right-Click Reset to Full Range
  - Backend as Source of Truth für Clip IDs
  - Live-Apply bei aktiver Wiedergabe
- **HAP Codec & Universal Video Converter** (v2.3.5):
  - FFmpeg-based video converter mit HAP codec support
  - Multiple output formats: HAP, HAP Alpha, HAP Q, H.264, H.264 NVENC
  - Batch processing mit glob patterns (recursive support)
  - Resize modes: none, fit, fill, stretch, auto
  - Loop optimization mit fade in/out
  - Standalone converter.html page mit dark mode
  - File browser integration (FilesTab component)
  - Drag & drop from file browser and file system
  - Local file upload support
  - Dual-mode selection: Browser Mode vs Pattern Mode
  - Multi-file sequential conversion mit progress tracking
  - Smart path resolution (workspace root + video/ directory)
  - Search filter for file browser (tree + list view)
  - Auto-expand folders when searching

---

*Siehe [HISTORY.md](HISTORY.md) für abgeschlossene Features (v1.x - v2.3)*
