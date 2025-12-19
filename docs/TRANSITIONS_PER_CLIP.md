# Per-Clip Transitions - Implementation Guide

## Overview

This document describes the implementation of **per-clip transition overrides** using the existing transition plugin system. Clips can specify custom transitions that override the playlist default by using a simple effect plugin.

## Core Concept

**Transition Flow:**
```
Clip 1 → [Playlist Default Transition] → Clip 2 → [Custom Zoom Transition] → Clip 3 → [Playlist Default] → Clip 4
         (fade, 1.0s)                    (zoom, 2.0s from plugin)         (fade, 1.0s)
```

**Key Principle:** A transition effect applied to a clip controls the **incoming transition TO that clip**.

- Clip 2 has no transition effect → uses playlist default when transitioning FROM clip 1
- Clip 3 has "zoom" transition effect → uses zoom transition when transitioning FROM clip 2
- Clip 4 has no transition effect → uses playlist default when transitioning FROM clip 3

## Architecture

### Plugin Separation

**Transition Plugins** (`plugins/transitions/`):
- Actual transition implementations (fade, wipe, zoom, dissolve, etc.)
- Handle frame blending between previous and current frame
- Already exist and are fully functional

**Transition Effect Plugin** (`plugins/effects/transition.py`):
- **Only job**: Select which transition plugin to use for this clip
- Lists available transitions from `plugins/transitions/` directory
- Stores selection (plugin name, duration, easing)
- Does NOT implement transition logic itself

### Timing & Override Logic

**When to Check:**
```python
# Player loads new clip
def load_file(self, path, clip_id):
    # 1. BEFORE loading new clip, check if it has transition effect
    clip = self.get_clip_by_id(clip_id)
    transition_effect = self._find_transition_effect(clip)
    
    # 2. If found, override TransitionManager config
    if transition_effect:
        custom_config = extract_config_from_effect(transition_effect)
        self.transition_manager.apply_config(custom_config)
    else:
        # 3. No override - revert to playlist default
        self.transition_manager.apply_config(self.playlist_default_transition)
    
    # 4. Load clip (transition happens automatically via TransitionManager)
    self._load_clip_impl(path)
```

**Challenge Solved:** Check happens during clip load, BEFORE the transition starts. This ensures the correct transition config is active when TransitionManager captures the previous frame.

## How It Works

### Step-by-Step Flow

**1. Playlist Default (No Override):**
```
Player: Load Clip 2
  ├─ Check Clip 2 for transition effect: None found
  ├─ Use playlist default: {plugin: 'fade', duration: 1.0s}
  ├─ TransitionManager: Blend with fade
  └─ Clip 2 plays
```

**2. Custom Transition (Override):**
```
Player: Load Clip 3
  ├─ Check Clip 3 for transition effect: Found!
  │   └─ Parameters: {plugin: 'zoom', duration: 2.0s, easing: 'ease_out'}
  ├─ Override TransitionManager config with custom settings
  ├─ TransitionManager: Blend with zoom plugin
  └─ Clip 3 plays
```

**3. Return to Default:**
```
Player: Load Clip 4
  ├─ Check Clip 4 for transition effect: None found
  ├─ Restore playlist default: {plugin: 'fade', duration: 1.0s}
  ├─ TransitionManager: Blend with fade
  └─ Clip 4 plays
```

### Effect Plugin Responsibilities

**What the effect plugin DOES:**
1. Scan `plugins/transitions/` directory for available plugins
2. Build dropdown list of transition options
3. Store user selection (plugin name, duration, easing)
4. Return config when requested

**What the effect plugin DOES NOT do:**
- ❌ Implement transition logic (that's in `plugins/transitions/`)
- ❌ Process frames (returns frame unchanged)
- ❌ Manage timing (TransitionManager handles that)
- ❌ Handle blending (transition plugins do that)

## Implementation

### Effect Plugin Structure

**File:** `plugins/effects/transition.py`

The effect plugin is a **configuration selector**, not a transition implementation:

```python
"""
Transition Effect Plugin
Allows clips to override playlist default transition.
This plugin ONLY selects which transition to use - actual transitions
are implemented in plugins/transitions/ directory.
"""

from plugins.plugin_base import EffectPlugin
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class TransitionEffect(EffectPlugin):
    """Clip-level transition selector."""
    
    def __init__(self):
        super().__init__()
        self.name = "Transition"
        self.description = "Override playlist transition for this clip"
        self.author = "Flux"
        self.version = "1.0.0"
        
        # Discover available transitions
        self.available_transitions = self._discover_transitions()
        
        # Parameters
        self.parameters = {
            'plugin': {
                'type': 'select',
                'label': 'Transition Plugin',
                'default': self._get_default_transition(),
                'options': self._build_options()
            },
            'duration': {
                'type': 'float',
                'label': 'Duration (seconds)',
                'default': 1.0,
                'min': 0.1,
                'max': 5.0,
                'step': 0.1
            },
            'easing': {
                'type': 'select',
                'label': 'Easing',
                'default': 'ease_in_out',
                'options': [
                    {'value': 'linear', 'label': 'Linear'},
                    {'value': 'ease_in', 'label': 'Ease In'},
                    {'value': 'ease_out', 'label': 'Ease Out'},
                    {'value': 'ease_in_out', 'label': 'Ease In/Out'}
                ]
            }
        }
    
    def _discover_transitions(self):
        """Scan plugins/transitions/ for available transitions."""
        transitions = {}
        transitions_dir = Path('plugins/transitions')
        
        if not transitions_dir.exists():
            logger.warning("Transitions directory not found")
            return {'none': 'No Transition'}
        
        for file in transitions_dir.glob('*.py'):
            if file.name.startswith('__'):
                continue
            
            plugin_name = file.stem
            # Convert filename to label
            label = ' '.join(w.capitalize() for w in plugin_name.replace('_transition', '').split('_'))
            transitions[plugin_name] = label
        
        transitions['none'] = 'No Transition'
        logger.info(f"Discovered {len(transitions)-1} transition plugins")
        return transitions
    
    def _get_default_transition(self):
        """Get default transition plugin."""
        if 'fade' in self.available_transitions:
            return 'fade'
        elif len(self.available_transitions) > 1:
            return list(self.available_transitions.keys())[0]
        return 'none'
    
    def _build_options(self):
        """Build options for dropdown."""
        return [
            {'value': k, 'label': v}
            for k, v in self.available_transitions.items()
        ]
    
    def process(self, frame, parameters, frame_count, fps):
        """
        This effect doesn't process frames.
        It only stores configuration that the player reads.
        """
        return frame
    
    def get_config(self, parameters):
        """
        Extract transition config from effect parameters.
        Called by player when loading clip.
        
        Returns:
            dict: {plugin: str, duration: float, easing: str}
                  or None if transition disabled
        """
        plugin = parameters.get('plugin', 'fade')
        
        if plugin == 'none':
            return None  # No transition
        
        return {
            'plugin': plugin,
            'duration': parameters.get('duration', 1.0),
            'easing': parameters.get('easing', 'ease_in_out')
        }
```

### Player Integration

**File:** `src/modules/player/player_base.py` (or video/artnet player)

```python
"""
Transition Effect Plugin
Allows clips to override playlist default transition settings.
"""

from plugins.plugin_base import EffectPlugin
import logging

logger = logging.getLogger(__name__)

class TransitionEffect(EffectPlugin):
    """Clip-level transition override effect."""
    
    def __init__(self):
        super().__init__()
        self.name = "Transition"
        self.description = "Override playlist transition for this clip"
        self.author = "Flux"
        self.version = "1.0.0"
        
        # Load available transitions from plugins/transitions/
        self.available_transitions = self._load_available_transitions()
        
        # Define parameters
        self.parameters = {
            'plugin': {
                'type': 'select',
                'label': 'Transition Plugin',
                'default': 'fade' if 'fade' in self.available_transitions else list(self.available_transitions.keys())[0] if self.available_transitions else 'none',
                'options': self._build_transition_options()
            },
            'duration': {
                'type': 'float',
                'label': 'Duration (seconds)',
                'default': 1.0,
                'min': 0.1,
                'max': 5.0,
                'step': 0.1
            },
            'easing': {
                'type': 'select',
                'label': 'Easing',
                'default': 'ease_in_out',
                'options': [
                    {'value': 'linear', 'label': 'Linear'},
       3 Update Player Clip Loading

**File:** `src/modules/player/player_base.py` or `src/modules/api_player_unified.py`

Modify clip load to check for transition effect:

```python
def load_file(self, path, clip_id=None):
    """Load clip and apply transition effect if present."""
    
    # Find clip in playlist
    clip = self.get_clip_by_id(clip_id) if clip_id else None
    
    # Check if clip has transition effect
    if clip and hasattr(clip, 'effects'):
        transition_effect = self._find_transition_effect(clip.effects)
        
        if transition_effect:
            # Clip has custom transition - apply it
            effect_params = transition_effect.get('parameters', {})
            plugin = effect_params.get('plugin', 'fade')
            transition_config = {
                'enabled': plugin != 'none',
                'plugin': plugin if plugin != 'none' else None,
                'duration': effect_params.get('duration', 1.0),
                'easing': effect_params.get('easing', 'ease_in_out')
            }
            
            if hasattr(self, 'transition_manager'):
                self.transition_manager.apply_clip_config(transition_config, self.name)
                logger.info(f"🎬 Applied clip transition: {transition_config['effect']}")
    
    # Load the clip
    success = self._load_file_impl(path, clip_id)
    return success

def _find_transition_effect(self, effects):
    """Find transition effect in clip's effect list."""
    for effect in effects:
        if effect.get('name', '').lower() == 'transition':
            return effect
    return Nonestr, duration: float, easing: str}
    
    Returns:
        dict: Effective configuration to use
    """
    # Check if clip has custom transition
    if clip_transition and isinstance(clip_transition, dict):
        # Clip has custom config - use it
        logger.debug(f"Using clip transition: {clip_transition.get('effect', 'unknown')}")
        return clip_transition
    
    # Fall back to playlist default
    logger.debug(f"Using playlist default transition: {self.config.get('effect', 'unknown')}")
    return self.config

def apply_clip_config(self, clip_transition=None, player_name=""):
    """
    Apply clip-specific or playlist default transition config.
    
    Args:
        clip_transition: Optional clip transition override
        player_name: Player name for logging
    """
    effective_config = self.get_effective_config(clip_transition)
    
    # Update current config for this clip
    self.configure(
        enabled=effective_config.get('enabled', False),
        plugin=effective_config.get('plugin'),  # Plugin name from plugins/transitions/
        duration=effective_config.get('duration', 1.0),
        easing=effective_config.get('easing', 'ease_in_out')
    )
    
    logger.info(f"🎬 [{player_name}] Transition config applied: "
                f"plugin={effective_config.get('plugin')}, "
                f"duration={effective_config.get('duration')}s, "
                f"source={'clip' if clip_transition else 'playlist'}")
```

#### 1.2 Update Player Clip Loading

**File:** `src/modules/api_player_unified.py` (or wherever `/api/player/{id}/clip/load` is)

Modify clip load endpoint to accept transition config:

```python
@app.route('/api/player/<player_id>/clip/load', methods=['POST'])
def load_clip(player_id):
    data = request.get_json() or {}
    path = data.get('path')
    clip_id = data.get('clip_id')
    clip_transition = data.get('transition')  # NEW: Optional clip transition
    
    # ... existing validation ...
    
    player = player_manager.get_player(player_id)
    
    # Apply clip transition config before loading
    if hasattr(player, 'transition_manager'):
        player.transition_manager.apply_clip_config(clip_transition, player_id)
    
    # Load clip
    success = player.load_file(path, clip_id)
    
    # ... rest of endpoint ...
```

#### 1.3 Update Session State Handling

**File:** `src/modules/session_state.py`

Ensure `transition` field is preserved:

```python
def save(self, player_manager, clip_registry, force=False):
    # ... existing code ...
    
    for player_id in ['video', 'artnet']:
        player = player_manager.get_player(player_id)
        playlist_data = []
        
        for clip in player.playlist:
            clip_data = {
                'id': clip.id,
                'path': clip.path,
                'type': clip.type,
                'effects': clip.effects,
                'parameters': clip.parameters,
                'transition': clip.transition  # NEW: Save clip transition
            }
            playlist_data.append(clip_data)
        
        # ... rest of save logic ...
```

### Phase 2: API Endpoints

Add new REST endpoints for managing clip transitions:

**File:** `src/modules/api_transitions.py` (or new file `api_clip_transitions.py`)

```python
@app.route('/api/player/<player_id>/clip/<clip_id>/transition', methods=['GET'])
def get_clip_transition(player_id, clip_id):
    """Get transition config for specific clip."""
    try:
        player = player_manager.get_player(player_id)
        clip = player.get_clip_by_id(clip_id)
        Frontend Integration

**No API changes needed!** The existing effect system handles everything. id: crypto.randomUUID(),
    path: filePath,
    name: fileName,
    type: 'video',
    effects: [],
    parameters: {},
    transition: null  // NEW: Default to playlist transition
};
```

#### 3.2 Modify loadFile Function

**File:** `frontend/js/player.js` (around line 2272)

Pass clip transition to backend:

```javascript
window.loadFile = async function(playerId, filePath, clipId = null, addToPlaylist = false) {
    const config = playerConfigs[playerId];
    if (!config) {
        console.error(`❌ Unknown player: ${playerId}`);
        return;
    }
    
    // Find clip in playlist to get transition config
    const fileItem = config.files.find(f => f.id === clipId);
    const clipTransition = fileItem?.transition || null;
    
    try {
        debug.log(`📂 Loading file for ${config.name}: ${filePath}`);
        
        // Call backend API with clip transition
        const response = await fetch(`${API_BASE}${config.apiBase}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: filePath,
                clip_id: clipId,
                transition: clipTransition  // NEW: Send clip transition
            })
        });
        
        // ... rest of function ...
    }
};
```

#### 3.3 Add Clip Transition UI

**File:** `frontend/js/player.js` (in ClipFX section rendering)

Add transition controls to ClipFX tab:

```javascript
function renderClipTransitionSection() {
    if (!selectedClipId || !selectedClipPlayerType) {
        return '';
    }
    
    const config = playerConfigs[selectedClipPlayerType];
    const clip = config.files.find(f => f.id === selectedClipId);
    
    if (!clip) return '';
    
    const hasCustomTransition = clip.transition !== null;
    const transition = clip.transition || {
        enabled: true,
        effect: 'fade',
        duration: 1.0,
        easing: 'ease_in_out'
    };
    
    return `
        <div Usage

**Using transition effects is exactly like using any other effect:**

#### 3.1 Add Transition Effect to Clip

1. Select clip in playlist
2. Open ClipFX tab
3. Click "➕ Add Effect"
4. Select "Transition" from effect list
5. Configure parameters:
   - **Transition Plugin**: Select from available plugins in `plugins/transitions/` (fade, wipe, dissolve, etc.)
   - **Duration**: 0.1 - 5.0 seconds
   - **Easing**: linear, ease_in, ease_out, ease_in_out

#### 3.2 Effect Behavior

- **No effect added** → Uses playlist default transition
- **Effect added with plugin selected** → Uses clip-specific transition with selected plugin
- **Effect added with plugin = "none"** → No transition for this clip
- **Effect removed** → Reverts to playlist default

#### 3.3 Visual Indicator

Clips with transition effect will show in effects list:
```
📋 Clip Effects
  ⚡ Transition (wipe_transition, 2.0s)
  🎨 Color Adjustment
  ✨ Glow
1. **Visual Indicators**
   - Badge on clip thumbnail showing custom transition
   - Different color for clips with overrides

2. **Bulk Operations**
   - Set same transition for multiple clips
   - Copy/paste transition between clips

3. **Transition Preview**
   - Preview transition between two clips
   - Scrub through transition timeline

4. **Templates**
   - Save transition presets
   - Apply preset to clip

## References

- Current transition system: `src/modules/player/transition_manager.py`
- Playlist data structure: `src/modules/session_state.py`
- Transition UI: `frontend/components/transition-menu.html`
- API docs: `docs/TRANSITION_SYSTEM.md`
 (⚡ button)
4. Play through all clips - should all fade
5. Select clip 2 in playlist
6. Open ClipFX tab
7. Click "➕ Add Effect" → Select "Transition"
8. Set plugin to "wipe_transition", duration 2.0s
9. Play clip 1 → clip 2: should use wipe transition over 2s ✅
10. Play clip 2 → clip 3: should fade over 1s (default) ✅
11. Save project, reload page
12. Load saved project
13. Verify clip 2 still has transition effect in effects list
14. Play through - verify transitions match
15. Remove transition effect from clip 2
16. Play again - should use playlist default fadetransition effect → use playlist default
- Existing behavior fully preserved
- Effect system already handles serialization

### Implementation Steps

1. **Create Effect Plugin** (`plugins/effects/transition.py`)
   - Define parameters (effect, duration, easing)
   - Implement `get_transition_config()` method

2. **Update Player Load Logic**
   - Check for transition effect when loading clip
   - Extract config and apply to TransitionManager
   - No API changes needed

3. **Test**
   - Add transition effect to clips via existing UI
   - Verify effect parameters save/load correctly
   - Confirm transitions work as expected