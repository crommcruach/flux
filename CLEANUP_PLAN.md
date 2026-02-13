# 🧹 CLEANUP PLAN - Py_artnet Refactoring Roadmap

**Generated:** February 13, 2026  
**Status:** Ready for execution  
**Estimated Total Time:** 20-30 hours

---

## 🚨 **CRITICAL ISSUES FIXED**

✅ **JavaScript Syntax Error** - [output-settings.js:5813](frontend/js/output-settings.js#L5813)  
   - **Fixed:** Missing `/**` comment opening
   - **Status:** RESOLVED

---

## 📊 **PROBLEM SUMMARY**

### 1. **Dual Art-Net Implementations** (BIGGEST ISSUE)
You have **TWO parallel Art-Net systems**:

| System | Location | Purpose | Status |
|--------|----------|---------|--------|
| **Legacy** | `artnet_manager.py` (445 lines) | Old points-based system | ⚠️ **IN USE** |
| **New** | `artnet_routing/` (9 modules) | Modern pixel sampling system | ✅ **ACTIVE** |

**Problem:**  
- Both systems running simultaneously  
- Confusion about which to use  
- Duplicate functionality
- Old system still referenced in main.py

### 2. **Obsolete Configuration** (config.json)
Documentation says these are obsolete, but **they're still in use**:

```json
// ❌ MARKED FOR REMOVAL in ARTNET_OUTPUT_ROUTING_IMPLEMENTATION.md
"channels": { ... },           // ENTIRE SECTION - not used by new system
"cache": { ... },              // ENTIRE SECTION - not used by new system  
"artnet": {
  "target_ip": "127.0.0.1",    // → Should be per-output
  "start_universe": 0,         // → Should be per-output
  "fps": 30,                   // → Should be per-output
  "bit_depth": 8,              // → Hardcoded to 8 (standard RGB)
  "delta_encoding": { ... },   // → Not needed (marked "optimization not needed")
  "universe_configs": { ... }  // → Should be per-object RGB format
}
```

**Keep Only:**
```json
"artnet": {
  "broadcast": true,           // Global setting
  "dmx_listen_ip": "0.0.0.0",  // DMX INPUT (separate feature)
  "dmx_listen_port": 6454      // DMX INPUT (separate feature)
}
```

### 3. **Massive Files**
- [output-settings.js](frontend/js/output-settings.js): **6,272 lines** ⚠️  
- Combines: DMX monitor, slice editor, canvas renderer, routing manager
- Should be split into 5+ modules

### 4. **Deprecated Code Still Present**
```python
# Session State
session_state.py:143 - save_players_state() is DEPRECATED
session_state.py:217 - "LEGACY: Old player state save code removed (200+ lines)"
session_state.py:266 - "Sequences (if stored at root level - legacy)"

# Player Core  
player_core.py:65 - "_legacy_source" wrapper for backward compatibility
player_core.py:369 - "script_name (deprecated - use generator_id)"

# CLI/Command System
cli_handler.py:197 - Script system deprecated
command_executor.py:489 - Script system deprecated
dmx_controller.py:222 - "Script loading deprecated"
```

---

## 🎯 **CLEANUP ROADMAP**

### **PHASE 1: Art-Net Consolidation** (8-12h) 🔥 **CRITICAL**

#### 1.1 Audit Art-Net Usage (2h)
**Goal:** Understand what actually uses each system

**Tasks:**
- [ ] Grep for `artnet_manager` usage across codebase
- [ ] Grep for `artnet_routing` usage across codebase  
- [ ] Document which features depend on old system
- [ ] Identify migration path for each feature

**Commands:**
```powershell
# Find artnet_manager usage
rg "artnet_manager" --type py

# Find artnet_routing usage  
rg "artnet_routing" --type py

# Find ArtNetManager instantiation
rg "ArtNetManager\(" --type py
```

#### 1.2 Feature Migration Plan (2-3h)
Create migration checklist for each feature:

**Old System Features:**
- [ ] Test patterns (blackout, colors, gradient)
- [ ] Delta-encoding
- [ ] Universe channel mapping (RGB/GRB/BGR)
- [ ] Replay mode priority
- [ ] DMX monitor last_frame
- [ ] Stats tracking (packets, bytes)

**New System Features:**  
- [ ] Pixel sampling from canvas
- [ ] Multi-output routing
- [ ] Per-object RGB format
- [ ] Color correction per output
- [ ] Master/slave object linking

**Decision:** Can old features be ported to new system or deprecated?

#### 1.3 Deprecation Strategy (1-2h)
**Option A: Full Migration** (Recommended)
- Move test patterns to new system
- Deprecate old `artnet_manager.py`
- Update all references to use `artnet_routing/`

**Option B: Coexistence** (Not recommended)
- Keep both systems
- Document clear separation
- Risk of continued confusion

**Create:** `docs/ARTNET_MIGRATION_PLAN.md`

#### 1.4 Execute Migration (3-5h)
- [ ] Port missing features to new system
- [ ] Update `main.py` initialization
- [ ] Update API routes
- [ ] Update CLI commands
- [ ] Add deprecation warnings to old system
- [ ] Update documentation

---

### **PHASE 2: Configuration Cleanup** (3-4h) ⚠️ **HIGH**

#### 2.1 Create Backup (5min)
```powershell
Copy-Item config.json config.json.backup
```

#### 2.2 Update config.json (30min)
**Remove:**
```json
"channels": { ... },     // DELETE ENTIRE SECTION
"cache": { ... },        // DELETE ENTIRE SECTION
"artnet": {
  "target_ip": ...,      // DELETE
  "start_universe": ..., // DELETE  
  "fps": ...,            // DELETE
  "dmx_control_universe": ..., // DELETE
  "even_packet": ...,    // DELETE
  "bit_depth": ...,      // DELETE
  "delta_encoding": { ... },   // DELETE
  "universe_configs": { ... }  // DELETE
}
```

**Keep:**
```json
"artnet": {
  "broadcast": true,
  "dmx_listen_ip": "0.0.0.0",
  "dmx_listen_port": 6454
}
```

#### 2.3 Update Config Schema (1h)
**File:** `src/modules/config_schema.py`
- [ ] Remove obsolete fields from schema
- [ ] Add deprecation warnings for old fields
- [ ] Update validation logic

#### 2.4 Update Initialization Code (1-2h)
**File:** `src/main.py`
- [ ] Remove references to deleted config keys
- [ ] Move settings to session_state.json (per-output)
- [ ] Test startup with new config

#### 2.5 Update Documentation (30min)
- [ ] Update [CONFIG_SCHEMA.md](docs/CONFIG_SCHEMA.md)
- [ ] Update [README.md](README.md) configuration section
- [ ] Add migration notes to CHANGELOG

---

### **PHASE 3: Split output-settings.js** (6-8h) 📝 **MAINTAINABILITY**

**Current:** 6,272 lines in one file  
**Target:** 5-7 focused modules

#### 3.1 Analysis & Planning (1h)
Read file, identify logical boundaries:
```javascript
// Sections identified:
- DMX Monitor (lines ~5700-5900, ~200 lines)
- Slice Editor (lines ~2000-3500, ~1500 lines)  
- Canvas Renderer (lines ~3500-4500, ~1000 lines)
- Routing Manager (lines ~1000-2000, ~1000 lines)
- Point Generator (lines ~500-1000, ~500 lines)
- UI State Management (scattered, ~500 lines)
- API Integration (scattered, ~800 lines)
```

#### 3.2 Create New Module Structure (2h)
```
frontend/js/output-settings/
├── index.js              // Main entry point, app initialization
├── dmx-monitor.js        // DMX visualization (200 lines)
├── slice-editor.js       // Slice creation/editing (1500 lines)
├── canvas-renderer.js    // Canvas drawing logic (1000 lines)
├── routing-manager.js    // Output routing logic (1000 lines)
├── point-generator.js    // Dot distribution (500 lines)
├── ui-state.js           // State management (500 lines)
└── api-client.js         // Backend API calls (800 lines)
```

#### 3.3 Extract Modules One-by-One (3-4h)
**Order:** Start with most isolated, work to most coupled

1. **dmx-monitor.js** (30min)
   ```javascript
   export class DmxMonitor {
     constructor(socketio) { ... }
     open() { ... }
     close() { ... }
     updateFromData(data) { ... }
   }
   ```

2. **point-generator.js** (45min)
   ```javascript
   export class PointGenerator {
     generateMatrix(config) { ... }
     generateCircle(config) { ... }
     generateLine(config) { ... }
     // ... other shapes
   }
   ```

3. **api-client.js** (30min)
   ```javascript
   export class OutputRoutingAPI {
     async getObjects() { ... }
     async createObject(data) { ... }
     // ... other API calls
   }
   ```

4. **canvas-renderer.js** (1h)
   ```javascript
   export class CanvasRenderer {
     constructor(canvas) { ... }
     render(objects, outputs) { ... }
     drawObject(obj) { ... }
     // ... rendering methods
   }
   ```

5. **slice-editor.js** (1h)
   ```javascript
   export class SliceEditor {
     constructor(renderer, api) { ... }
     // ... editing logic
   }
   ```

6. **routing-manager.js & ui-state.js** (1h)

#### 3.4 Update HTML & Integration (30min)
**File:** `frontend/output-settings.html`
```html
<script type="module">
  import { initOutputSettings } from './js/output-settings/index.js';
  initOutputSettings();
</script>
```

#### 3.5 Testing (30min)
- [ ] Load output-settings page
- [ ] Test DMX monitor
- [ ] Test slice creation
- [ ] Test object routing
- [ ] Check browser console for errors

---

### **PHASE 4: Remove Deprecated Code** (3-4h) 🗑️ **DEBT REDUCTION**

#### 4.1 Session State Cleanup (1h)
**File:** `src/modules/session_state.py`

```python
# REMOVE (line 143):
def save_players_state(self, ...):
    """DEPRECATED - use save_async instead"""
    # DELETE THIS FUNCTION

# REMOVE (line 217):
# LEGACY: Old player state save code removed (200+ lines)
# DELETE COMMENT BLOCK

# REMOVE (lines 266, 337, 373):
# Delete all "LEGACY" comments and dead code paths
```

#### 4.2 Player Core Cleanup (1h)
**File:** `src/modules/player_core.py`

```python
# REMOVE (line 66):
self._legacy_source = frame_source  # DELETE
# Update all references to use layer system instead

# REMOVE (line 369):
@property
def script_name(self):
    """Script-Name (deprecated - use generator_id instead)."""
    # DELETE THIS PROPERTY

# REMOVE all "Legacy behavior" code paths (lines 701, 1245, 1368, 1871-1887)
```

#### 4.3 Script System Removal (30min)
**Files:** `cli_handler.py`, `command_executor.py`, `dmx_controller.py`

Search & destroy:
```python
# DELETE all mentions of:
- "Script system deprecated"
- ScriptGenerator import attempts
- Script-related CLI commands
```

#### 4.4 Frontend Cleanup (30min-1h)
**Already done** (v2.3.7 - HISTORY.md):
- ✅ Trim/reverse functions removed (~300 lines)
- ✅ trimSliderInstance variable removed

**Additional cleanup needed:**
- [ ] Search for "deprecated" comments in JS files
- [ ] Remove old API endpoint references
- [ ] Clean up unused imports

#### 4.5 Documentation Update (30min)
- [ ] Update [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [ ] Remove deprecated API endpoints from [API.md](docs/API.md)
- [ ] Update feature list in [README.md](README.md)

---

### **PHASE 5: Manager Consolidation** (Optional, 6-8h) 🔬 **ADVANCED**

**Current State:** 22+ Manager/Controller classes

#### 5.1 Audit Manager Responsibilities (2h)
Create responsibility matrix:

| Manager | Responsibility | Dependencies | Merge Candidate? |
|---------|----------------|--------------|------------------|
| ArtNetManager | Old Art-Net output | stupidArtnet | → ArtNetSender |
| OutputManager | Video outputs | cv2, screeninfo | Keep |
| PlayerManager | Player lifecycle | Player objects | Keep |
| SessionStateManager | State persistence | json | Keep |
| SequenceManager | Parameter sequences | AudioAnalyzer | Keep |
| ReplayManager | Replay recording | ArtNetManager | Review |
| TransitionManager | Clip transitions | Player | Keep |
| RecordingManager | Frame recording | Player | Keep |
| LayerManager | Layer compositing | Player | Keep |
| PlaylistManager | Playlist operations | Player | Keep |
| ... | ... | ... | ... |

#### 5.2 Identify Merge Opportunities (1-2h)
**Questions:**
- Can ArtNetManager be fully replaced by ArtNetSender?
- Should ReplayManager be part of RecordingManager?
- Are there managers that are just thin wrappers?

#### 5.3 Refactor Plan (2-3h)
- [ ] Document merge strategy
- [ ] Update integration points
- [ ] Write migration tests

#### 5.4 Execute Merges (2-3h)
- One manager at a time
- Test thoroughly between merges

---

## 📋 **EXECUTION CHECKLIST**

### Before Starting
- [ ] Create feature branch: `git checkout -b refactor/cleanup-2026`
- [ ] Run full test suite: `pytest tests/`
- [ ] Backup config.json
- [ ] Commit current state

### Phase Order (Recommended)
```
1. ✅ Fix syntax error (DONE)
2. 🔥 Phase 1: Art-Net Consolidation (8-12h)
3. ⚠️  Phase 2: Configuration Cleanup (3-4h)
4. 🗑️ Phase 4: Remove Deprecated Code (3-4h)
5. 📝 Phase 3: Split output-settings.js (6-8h)
6. 🔬 Phase 5: Manager Consolidation (Optional, 6-8h)
```

**Total:** 20-30 hours (without Phase 5)

### After Each Phase
- [ ] Run tests
- [ ] Test in browser (frontend changes)
- [ ] Commit changes: `git commit -m "refactor(phase-N): description"`
- [ ] Update this checklist

### Final Steps
- [ ] Full integration test
- [ ] Update CHANGELOG.md
- [ ] Merge to main: `git merge refactor/cleanup-2026`
- [ ] Archive old branches

---

## 🚀 **QUICK START GUIDE**

### If you only have 2 hours:
**Do Phase 4 (Remove Deprecated Code)** - Immediate debt reduction, low risk.

### If you have 4 hours: **Do Phase 2 (Config Cleanup)** - Removes confusion about obsolete settings.

### If you have 8 hours:
**Do Phase 1 (Art-Net Consolidation)** - Biggest ROI, solves core architectural issue.

### If you have a full day:
**Do Phases 1, 2, 4** - Tackles the three biggest issues.

---

## 📖 **RELATED DOCUMENTATION**

Existing refactoring plans (good news - you've already documented some of this!):
- [ARTNET_OUTPUT_ROUTING_IMPLEMENTATION.md](docs/ARTNET_OUTPUT_ROUTING_IMPLEMENTATION.md) - New Art-Net system design
- [SESSION_STATE_REFACTORING.md](docs/SESSION_STATE_REFACTORING.md) - Session state cleanup plan
- [UNIFIED_PLAYLISTS.md](docs/UNIFIED_PLAYLISTS.md) - Playlist unification (partially done)
- [agent.md](agent.md) - Development guidelines (excellent!)

---

## ❓ **DECISION POINTS**

These need your input before executing:

### 1. Art-Net Systems (Phase 1)
**Question:** Fully migrate to new system or keep both?  
**Recommendation:** Full migration (eliminate confusion)  
**Your call:** □ Migrate  □ Coexist  □ Keep old only

### 2. Config Cleanup (Phase 2)
**Question:** Delete obsolete settings now or deprecate gradually?  
**Recommendation:** Delete (they're documented as obsolete since v2.4)  
**Your call:** □ Delete now  □ Deprecate first  □ Keep for compatibility

### 3. output-settings.js Split (Phase 3)
**Question:** Create new directory or keep flat?  
**Recommendation:** New directory `frontend/js/output-settings/`  
**Your call:** □ New directory  □ Flat structure  □ Skip for now

### 4. Manager Consolidation (Phase 5)
**Question:** Worth the effort or leave as-is?  
**Recommendation:** Lower priority, only if clear wins identified  
**Your call:** □ Do it  □ Skip  □ Defer to v2.5

---

## 📞 **NEXT STEPS**

**Ready to start?** Tell me:
1. Which phase should we tackle first?
2. Any of the decision points above need discussion?
3. Do you want me to start with a specific file/feature?

**Recommended:** Start with **Phase 1.1 (Art-Net Audit)** - let's understand the full picture before making changes.
