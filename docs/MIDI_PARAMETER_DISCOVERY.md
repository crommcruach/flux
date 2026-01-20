# MIDI Parameter Discovery & Dynamic Mapping

## Overview

This document explains how to handle **dynamic parameters** in the MIDI control system - parameters that can be added/removed at runtime (effects, layers, generators).

## The Challenge

Unlike traditional MIDI controllers with fixed parameters, Flux has:
- **Dynamic effect chains** - users can add/remove effects
- **Multi-layer system** - layers can be added/removed
- **Plugin system** - different effects have different parameters
- **Generator switching** - parameters change when switching video to generator
- **Clip-specific effects** - each clip can have different effect chains

**Problem:** If user maps `CC#14 → Effect 0 Brightness`, then removes that effect, what happens?

## The Solution: Parameter Registry

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Parameter Registry                        │
│  - Scans entire system for controllable parameters          │
│  - Assigns unique paths: "video.effect.0.brightness"       │
│  - Tracks parameter metadata (min/max/type)                 │
│  - Updates on structure changes (effect added/removed)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├─ Scan Triggers:
                            │  • Startup
                            │  • Effect added/removed
                            │  • Layer added/removed
                            │  • Clip changed
                            │  • Generator loaded
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                     MIDI Manager                             │
│  - Stores mappings: "CC#14 → video.effect.0.brightness"    │
│  - Validates mappings before applying                       │
│  - Marks invalid mappings (parameter doesn't exist)         │
│  - Provides cleanup tools                                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├─ On MIDI Input:
                            │  1. Check mapping exists
                            │  2. Validate parameter exists
                            │  3. Apply value if valid
                            │  4. Mark invalid if missing
                            │
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Frontend Parameter Browser                  │
│  - Lists all available parameters                           │
│  - Filtered by category (effect/layer/global)              │
│  - Shows current values                                     │
│  - Provides "🎹 Learn" buttons                             │
│  - Highlights invalid mappings                              │
└─────────────────────────────────────────────────────────────┘
```

## Parameter Path Naming Convention

### Format: `{player}.{category}.{index}.{parameter}`

**Examples:**

| Parameter Path | Description |
|----------------|-------------|
| `video.global.speed` | Video player playback speed |
| `video.global.opacity` | Video player master opacity |
| `video.effect.0.brightness` | First effect's brightness parameter |
| `video.effect.1.threshold` | Second effect's threshold parameter |
| `video.layer.0.opacity` | First layer's opacity |
| `video.layer.0.effect.0.blur` | First layer's first effect's blur param |
| `video.generator.speed` | Generator speed parameter |
| `artnet.effect.0.intensity` | Art-Net effect intensity |
| `sequencer.bpm` | Sequencer BPM |
| `audio.gain` | Audio analyzer gain |

### Why This Works

✅ **Unique** - Each parameter has a unique path  
✅ **Persistent** - Paths are saved as strings (not object references)  
✅ **Validatable** - Can check if path still exists  
✅ **Human-readable** - Easy to understand what parameter it controls  
✅ **Hierarchical** - Shows structure (player → effect → parameter)

## Complete Workflow

### 1. Initial Setup (Startup)

```python
# In main.py
parameter_registry = ParameterRegistry(player_manager, plugin_manager)
midi_manager = MIDIManager(session_state, parameter_registry)

# Initial scan
parameter_registry.scan_all_parameters()
# Result: 247 parameters found (example)
```

### 2. User Opens MIDI Learn UI

```javascript
// User clicks "MIDI Settings" button
parameterBrowser.loadParameters();
// GET /api/parameters
// Returns: [{path: 'video.effect.0.brightness', name: 'Brightness', ...}, ...]
```

### 3. User Creates MIDI Mapping

**User Action:**
1. Finds "Brightness" parameter in list
2. Clicks "🎹 Learn" button
3. Moves fader on MIDI controller (sends CC#14 value 87)
4. Mapping created and saved

**Backend Storage:**
```json
{
  "cc:14": {
    "midi_type": "cc",
    "midi_number": 14,
    "parameter_path": "video.effect.0.brightness",
    "min_value": 0,
    "max_value": 100,
    "valid": true
  }
}
```

### 4. MIDI Control Active

**MIDI Input:** CC#14 = 64 (half-way)

**Processing:**
```python
# 1. Find mapping
mapping = midi_manager.mappings.get('cc:14')
# Result: video.effect.0.brightness

# 2. Validate parameter exists
param = parameter_registry.get_parameter('video.effect.0.brightness')
if not param:
    mapping.valid = False  # Mark invalid
    return False

# 3. Scale value
scaled = param.min_value + (64/127) * (param.max_value - param.min_value)
# Result: 0 + (0.504 * 100) = 50.4

# 4. Apply
parameter_registry.update_parameter_value('video.effect.0.brightness', 50.4)
# Updates effect instance, marks value changed
```

### 5. User Removes Effect

**User Action:** Right-clicks effect → Delete

**What Happens:**
```python
# In player_core.py
def remove_effect(self, index):
    del self.video_effect_chain[index]
    
    # Trigger rescan
    if hasattr(self.player_manager, 'parameter_registry'):
        self.player_manager.parameter_registry.scan_all_parameters()
        # Emits: parameter_structure_changed event
```

**Frontend Reacts:**
```javascript
socket.on('parameter_structure_changed', async () => {
    // Auto-validate MIDI mappings
    const report = await midiLearnManager.validateAllMappings();
    // GET /api/midi/mappings/validate
    
    if (report.invalid_count > 0) {
        // Show warning: "CC#14 → video.effect.0.brightness is invalid"
        midiLearnManager.showInvalidMappingsWarning(report.invalid);
    }
});
```

### 6. Next MIDI Input (After Effect Removed)

**MIDI Input:** CC#14 = 100

**Processing:**
```python
# 1. Find mapping
mapping = midi_manager.mappings.get('cc:14')
# Still exists: video.effect.0.brightness

# 2. Validate parameter
param = parameter_registry.get_parameter('video.effect.0.brightness')
# Result: None (effect was removed)

# 3. Mark invalid
logger.warning("Parameter no longer exists: video.effect.0.brightness")
mapping.valid = False

# 4. Skip update
return False
```

**Result:** MIDI input is safely ignored, mapping marked invalid for cleanup later.

## API Reference

### Get All Parameters
```
GET /api/parameters
Response: {
  "success": true,
  "parameters": [
    {
      "path": "video.effect.0.brightness",
      "name": "Brightness",
      "type": "float",
      "min": 0,
      "max": 100,
      "value": 50.0,
      "category": "effect",
      "description": "Blur - Brightness"
    },
    ...
  ],
  "count": 247
}
```

### Get Parameters by Category
```
GET /api/parameters/category/effect
Response: {
  "success": true,
  "parameters": [...],  // Only effect parameters
  "category": "effect"
}
```

### Rescan Parameters
```
POST /api/parameters/rescan
Response: {
  "success": true,
  "count": 251  // New count after rescan
}
```

### Validate MIDI Mappings
```
POST /api/midi/mappings/validate
Response: {
  "success": true,
  "report": {
    "valid_count": 12,
    "invalid_count": 2,
    "valid": [
      {"midi": "cc:1", "path": "video.global.speed", "name": "Playback Speed", ...},
      ...
    ],
    "invalid": [
      {"midi": "cc:14", "path": "video.effect.0.brightness", "reason": "Parameter not found"},
      ...
    ]
  }
}
```

### Remove Invalid Mappings
```
POST /api/midi/mappings/remove_invalid
Response: {
  "success": true,
  "removed_count": 2,
  "removed": ["cc:14", "cc:15"]
}
```

## Parameter Categories

### Global Parameters
- Always available
- Survive structure changes
- Examples: playback speed, master opacity, BPM

**Paths:**
- `video.global.speed`
- `video.global.opacity`
- `artnet.global.dimmer`
- `sequencer.bpm`
- `audio.gain`

### Effect Parameters
- Dynamic (effects can be added/removed)
- Index-based (effect.0, effect.1, ...)
- Plugin-defined parameters

**When to Rescan:**
- Effect added
- Effect removed
- Effect reordered
- Clip changed (different effect chain per clip)

**Paths:**
- `video.effect.{index}.{parameter}`
- `artnet.effect.{index}.{parameter}`

### Layer Parameters
- Dynamic (layers can be added/removed)
- Include layer properties + layer effects

**When to Rescan:**
- Layer added
- Layer removed
- Layer effect added/removed

**Paths:**
- `video.layer.{index}.opacity`
- `video.layer.{index}.enabled`
- `video.layer.{index}.effect.{index}.{parameter}`

### Generator Parameters
- Dynamic (change when switching to generator)
- Generator-type-specific parameters

**When to Rescan:**
- Video switched to generator
- Generator type changed

**Paths:**
- `video.generator.{parameter}`
- `artnet.generator.{parameter}`

## Best Practices

### 1. Always Use Parameter Paths
❌ **Bad:** Store reference to effect object
```python
mapping = {'effect': effect_instance, 'param': 'brightness'}
# Breaks when effect removed
```

✅ **Good:** Store string path
```python
mapping = {'path': 'video.effect.0.brightness'}
# Validates on each use
```

### 2. Validate Before Applying
❌ **Bad:** Assume parameter exists
```python
effect.brightness = value  # Crash if effect removed
```

✅ **Good:** Validate first
```python
param = parameter_registry.get_parameter(path)
if param:
    parameter_registry.update_parameter_value(path, value)
```

### 3. Rescan on Structure Changes
❌ **Bad:** Never update parameter list
```python
def add_effect(self, effect):
    self.effects.append(effect)
    # MIDI Learn UI shows outdated parameters
```

✅ **Good:** Trigger rescan
```python
def add_effect(self, effect):
    self.effects.append(effect)
    if parameter_registry:
        parameter_registry.scan_all_parameters()
        socketio.emit('parameter_structure_changed')
```

### 4. Provide Cleanup Tools
✅ Show invalid mappings in UI
✅ Allow bulk removal of invalid mappings
✅ Auto-validate on parameter changes
✅ Visual indicators (✓/✗) for mapping validity

### 5. Graceful Degradation
When parameter doesn't exist:
- ✅ Log warning (not error)
- ✅ Mark mapping invalid
- ✅ Continue processing other MIDI inputs
- ✅ Don't crash

## Performance Considerations

### Rescan Triggers
**Expensive:** Full parameter scan (100-500ms)

**When to trigger:**
- ✅ Effect added/removed (infrequent)
- ✅ Layer added/removed (infrequent)
- ✅ Clip changed (occasional)
- ❌ Every frame (NO!)
- ❌ Every MIDI input (NO!)

### Caching
```python
# Cache parameter registry results
self.parameters = {}  # Dict lookup: O(1)

# Don't rescan on every MIDI input
def handle_midi_message(self, ...):
    # Use cached parameters
    param = self.parameters.get(path)  # Fast!
```

### Validation Strategy
```python
# Option 1: Validate on every MIDI input (SAFE, ~5µs)
param = parameter_registry.get_parameter(path)
if param:
    apply_value()

# Option 2: Mark invalid once, skip later (FAST, 0µs)
if not mapping.valid:
    return  # Skip immediately
```

**Recommendation:** Use Option 1 (validate on every input) - 5µs is negligible, ensures correctness.

## Testing Checklist

### Dynamic Parameter Tests

- [ ] **Effect Added:** Parameter appears in list, MIDI Learn works
- [ ] **Effect Removed:** Mapping becomes invalid, MIDI input skipped
- [ ] **Effect Reordered:** Mappings update to new indices
- [ ] **Layer Added:** Layer parameters appear
- [ ] **Layer Removed:** Layer mappings invalid
- [ ] **Clip Changed:** New effect chain parameters loaded
- [ ] **Generator Loaded:** Generator parameters replace video parameters
- [ ] **Invalid Mapping Cleanup:** Remove invalid mappings works
- [ ] **Validation Warning:** UI shows warning when mappings invalid
- [ ] **Rescan Button:** Manual rescan updates parameter list
- [ ] **Parameter Value Display:** Shows current values in real-time
- [ ] **MIDI Learn with Dynamic:** Can map to newly added parameters
- [ ] **Mapping Persistence:** Mappings survive server restart
- [ ] **Validation on Startup:** Invalid mappings detected on load

### Performance Tests

- [ ] **Rescan Time:** <500ms for typical configuration
- [ ] **MIDI Input Latency:** <10ms including validation
- [ ] **Memory Usage:** Parameter registry <10MB
- [ ] **Concurrent Updates:** Multiple MIDI inputs don't block

## Summary

**Key Points:**
1. ✅ **Parameter paths** (strings) instead of object references
2. ✅ **Automatic rescanning** when structure changes
3. ✅ **Runtime validation** of MIDI mappings
4. ✅ **Graceful handling** of invalid mappings
5. ✅ **Visual feedback** for mapping validity
6. ✅ **Cleanup tools** for invalid mappings

**Result:** Robust MIDI control system that handles dynamic parameters elegantly, doesn't crash when structure changes, and provides clear feedback to users.
