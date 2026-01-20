# MIDI Control Implementation Guide

## Overview

This document outlines the implementation plan for MIDI control in Flux with **two complementary approaches**:

1. **Primary: Web MIDI API** (Browser-based, no installation required)
2. **Backup: Direct USB MIDI** (Server-side, for compatibility and reliability)

### Key Features

**MIDI Profile Storage:**
- Stored separately in `config/midi_profiles.json` (not session_state.json)
- Reusable across different sessions/projects
- Sharable between projects (studio setup, live setup, backup controller)
- Independent from clip/session data

**Global vs Local Mapping:**
- **Local**: `CC#14 → video.effect.0.brightness` (specific effect only)
- **Global**: `CC#14 → *.brightness` (all brightness parameters everywhere)
- Pattern matching: `video.layer.*.opacity`, `*.effect.*.blur`
- Use cases: Master faders, group controls, synchronized parameters

## Architecture Options

### Option 1: Web MIDI API (Browser-based)

```
┌─────────────────┐
│ MIDI Controller │
└────────┬────────┘
         │ USB/Bluetooth
         ↓
┌─────────────────┐
│   Browser       │
│ (Web MIDI API)  │
└────────┬────────┘
         │ WebSocket
         ↓
┌─────────────────┐
│ Flask Backend   │
│   (SocketIO)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Parameters    │
│ (Effects, etc.) │
└─────────────────┘
```

### Option 2: Direct USB MIDI (Server-side)

```
┌─────────────────┐
│ MIDI Controller │
└────────┬────────┘
         │ USB (Direct to Server)
         ↓
┌─────────────────┐
│   Server        │
│ (python-rtmidi) │
│   MIDI Thread   │
└────────┬────────┘
         │ Direct
         ↓
┌─────────────────┐
│   Parameters    │
│ (Effects, etc.) │
└─────────────────┘
```

## Comparison: Web MIDI vs Direct USB

| Feature | Web MIDI API | Direct USB MIDI |
|---------|--------------|-----------------|
| **Installation** | None | Python package (`python-rtmidi`) |
| **Browser Required** | Chrome/Edge/Opera | Any browser |
| **Location** | MIDI device on any machine | MIDI device on server only |
| **Latency** | 5-15ms (WebSocket) | <1ms (direct) |
| **Setup** | Click & grant permission | Configure Python backend |
| **Hot-swap** | Automatic | Requires restart |
| **Remote Control** | ✅ Yes | ❌ No |
| **Firefox/Safari** | ❌ No | ✅ Yes |
| **Reliability** | Network-dependent | Hardware-direct |
| **Use Case** | Remote VJ, web-first | Server console, backup |

## Why Web MIDI API?

### ✅ Advantages:
- **No additional software required** - Built into Chrome, Edge, Opera
- **Remote control** - MIDI controller can be on different machine than server
- **Browser-based device selection** - User-friendly UI
- **Real-time performance** - Low latency via existing WebSocket infrastructure
- **Cross-platform** - Works on Windows, macOS, Linux
- **No drivers needed** - Browser handles MIDI device communication

### ❌ Browser Compatibility:
| Browser | Support | Notes |
|---------|---------|-------|
| Chrome/Chromium | ✅ Full | Best support since 2015 |
| Edge (Chromium) | ✅ Full | Same as Chrome |
| Opera | ✅ Full | Chromium-based |
| Firefox | ❌ None | No Web MIDI API support |
| Safari | ⚠️ Partial | Requires flag `Develop > Experimental Features > Web MIDI API` |

### Alternative: Python MIDI (Not Recommended)
Using `python-rtmidi` or `mido` would require:
- ❌ MIDI controller physically connected to server
- ❌ Additional Python dependencies
- ❌ Platform-specific drivers
- ❌ No remote control capability
- ❌ More complex setup

## Implementation Plan

### Phase 0: Parameter Discovery System (3-4h)

Before implementing MIDI control, we need a system to discover and track all controllable parameters.

#### 0.1 Parameter Registry (`src/modules/parameter_registry.py`)

```python
"""
Parameter Registry - Discovers and tracks all controllable parameters
Provides unified parameter paths for MIDI mapping
"""
from typing import Dict, List, Any, Optional
from ..logger import get_logger

logger = get_logger(__name__)


class Parameter:
    """Single controllable parameter"""
    
    def __init__(self, path: str, name: str, value_type: str, 
                 min_value: float, max_value: float, current_value: float,
                 category: str, description: str = ""):
        self.path = path  # Unique path: 'video.effect.0.brightness'
        self.name = name  # Display name: 'Brightness'
        self.value_type = value_type  # 'float', 'int', 'bool', 'enum'
        self.min_value = min_value
        self.max_value = max_value
        self.current_value = current_value
        self.category = category  # 'effect', 'generator', 'layer', 'global'
        self.description = description
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'path': self.path,
            'name': self.name,
            'type': self.value_type,
            'min': self.min_value,
            'max': self.max_value,
            'value': self.current_value,
            'category': self.category,
            'description': self.description
        }


class ParameterRegistry:
    """Registry of all controllable parameters in the system"""
    
    def __init__(self, player_manager, plugin_manager):
        self.player_manager = player_manager
        self.plugin_manager = plugin_manager
        self.parameters: Dict[str, Parameter] = {}
        self.update_callbacks = []  # Callbacks when parameters change
    
    def scan_all_parameters(self) -> Dict[str, Parameter]:
        """
        Scan entire system for controllable parameters
        Called on startup and when structure changes (effect added, etc.)
        """
        self.parameters.clear()
        
        # Scan both players (video + artnet)
        for player_id in ['video', 'artnet']:
            player = self.player_manager.get_player(player_id)
            if not player:
                continue
            
            # Global player parameters
            self._scan_player_global(player, player_id)
            
            # Effect chain parameters
            self._scan_effect_chain(player, player_id)
            
            # Layer parameters (if multi-layer enabled)
            self._scan_layers(player, player_id)
            
            # Generator parameters (if current clip is generator)
            self._scan_generator(player, player_id)
        
        # Sequencer parameters (BPM, position, etc.)
        self._scan_sequencer()
        
        # Audio analyzer parameters
        self._scan_audio_analyzer()
        
        logger.info(f"🔍 Parameter scan complete: {len(self.parameters)} parameters found")
        
        # Notify callbacks about parameter structure change
        self._notify_callbacks('structure_changed')
        
        return self.parameters
    
    def _scan_player_global(self, player, player_id: str):
        """Scan global player parameters"""
        base_path = f"{player_id}.global"
        
        # Playback speed
        self.parameters[f"{base_path}.speed"] = Parameter(
            path=f"{base_path}.speed",
            name="Playback Speed",
            value_type="float",
            min_value=0.1,
            max_value=4.0,
            current_value=getattr(player, 'playback_speed', 1.0),
            category="global",
            description="Video playback speed"
        )
        
        # Opacity
        self.parameters[f"{base_path}.opacity"] = Parameter(
            path=f"{base_path}.opacity",
            name="Master Opacity",
            value_type="float",
            min_value=0.0,
            max_value=100.0,
            current_value=100.0,
            category="global"
        )
    
    def _scan_effect_chain(self, player, player_id: str):
        """Scan effect chain parameters"""
        effect_chain = getattr(player, 'video_effect_chain', None) or \
                      getattr(player, 'artnet_effect_chain', None)
        
        if not effect_chain:
            return
        
        for idx, effect_dict in enumerate(effect_chain):
            effect_id = effect_dict.get('id')
            effect_instance = effect_dict.get('instance')
            
            if not effect_instance or not effect_id:
                continue
            
            # Get effect metadata from plugin
            plugin = self.plugin_manager.get_effect(effect_id)
            if not plugin:
                continue
            
            base_path = f"{player_id}.effect.{idx}"
            
            # Get parameters from plugin metadata
            for param in plugin.get('parameters', []):
                param_name = param['name']
                param_path = f"{base_path}.{param_name}"
                
                # Get current value from effect config
                current_value = effect_dict.get('config', {}).get(param_name, param.get('default', 0))
                
                self.parameters[param_path] = Parameter(
                    path=param_path,
                    name=param.get('label', param_name),
                    value_type=param.get('type', 'float'),
                    min_value=param.get('min', 0),
                    max_value=param.get('max', 100),
                    current_value=current_value,
                    category="effect",
                    description=f"{plugin['name']} - {param.get('label', param_name)}"
                )
    
    def _scan_layers(self, player, player_id: str):
        """Scan layer parameters (multi-layer system)"""
        if not hasattr(player, 'layer_manager') or not player.layer_manager:
            return
        
        for layer_idx, layer in enumerate(player.layer_manager.layers):
            base_path = f"{player_id}.layer.{layer_idx}"
            
            # Layer opacity
            self.parameters[f"{base_path}.opacity"] = Parameter(
                path=f"{base_path}.opacity",
                name=f"Layer {layer_idx} Opacity",
                value_type="float",
                min_value=0.0,
                max_value=100.0,
                current_value=layer.opacity,
                category="layer"
            )
            
            # Layer enabled
            self.parameters[f"{base_path}.enabled"] = Parameter(
                path=f"{base_path}.enabled",
                name=f"Layer {layer_idx} Enabled",
                value_type="bool",
                min_value=0,
                max_value=1,
                current_value=1 if layer.enabled else 0,
                category="layer"
            )
            
            # Layer effects (if any)
            for effect_idx, effect in enumerate(layer.effects):
                effect_id = effect.get('id')
                plugin = self.plugin_manager.get_effect(effect_id)
                if not plugin:
                    continue
                
                effect_base_path = f"{base_path}.effect.{effect_idx}"
                
                for param in plugin.get('parameters', []):
                    param_name = param['name']
                    param_path = f"{effect_base_path}.{param_name}"
                    current_value = effect.get('config', {}).get(param_name, param.get('default', 0))
                    
                    self.parameters[param_path] = Parameter(
                        path=param_path,
                        name=f"L{layer_idx} {plugin['name']} {param.get('label', param_name)}",
                        value_type=param.get('type', 'float'),
                        min_value=param.get('min', 0),
                        max_value=param.get('max', 100),
                        current_value=current_value,
                        category="layer_effect"
                    )
    
    def _scan_generator(self, player, player_id: str):
        """Scan generator parameters (if current source is generator)"""
        if not hasattr(player, 'source'):
            return
        
        from ..frame_source import GeneratorSource
        
        if not isinstance(player.source, GeneratorSource):
            return
        
        generator_id = player.source.generator_id
        plugin = self.plugin_manager.get_generator(generator_id)
        if not plugin:
            return
        
        base_path = f"{player_id}.generator"
        
        for param in plugin.get('parameters', []):
            param_name = param['name']
            param_path = f"{base_path}.{param_name}"
            current_value = player.source.parameters.get(param_name, param.get('default', 0))
            
            self.parameters[param_path] = Parameter(
                path=param_path,
                name=param.get('label', param_name),
                value_type=param.get('type', 'float'),
                min_value=param.get('min', 0),
                max_value=param.get('max', 100),
                current_value=current_value,
                category="generator",
                description=f"{plugin['name']} - {param.get('label', param_name)}"
            )
    
    def _scan_sequencer(self):
        """Scan sequencer parameters"""
        if not hasattr(self.player_manager, 'sequencer') or not self.player_manager.sequencer:
            return
        
        base_path = "sequencer"
        
        # BPM
        self.parameters[f"{base_path}.bpm"] = Parameter(
            path=f"{base_path}.bpm",
            name="Sequencer BPM",
            value_type="float",
            min_value=20.0,
            max_value=300.0,
            current_value=120.0,
            category="sequencer"
        )
    
    def _scan_audio_analyzer(self):
        """Scan audio analyzer parameters"""
        if not hasattr(self.player_manager, 'audio_analyzer'):
            return
        
        base_path = "audio"
        
        # Gain
        self.parameters[f"{base_path}.gain"] = Parameter(
            path=f"{base_path}.gain",
            name="Audio Gain",
            value_type="float",
            min_value=0.0,
            max_value=10.0,
            current_value=1.0,
            category="audio"
        )
    
    def get_parameter(self, path: str) -> Optional[Parameter]:
        """Get parameter by path"""
        return self.parameters.get(path)
    
    def get_all_parameters(self) -> Dict[str, Parameter]:
        """Get all parameters"""
        return self.parameters
    
    def get_parameters_by_category(self, category: str) -> Dict[str, Parameter]:
        """Get parameters filtered by category"""
        return {
            path: param 
            for path, param in self.parameters.items() 
            if param.category == category
        }
    
    def update_parameter_value(self, path: str, value: float) -> bool:
        """
        Update parameter value via player manager
        Returns True if successful
        """
        param = self.parameters.get(path)
        if not param:
            logger.warning(f"Parameter not found: {path}")
            return False
        
        # Parse path and update via appropriate method
        parts = path.split('.')
        player_id = parts[0]  # 'video', 'artnet', 'sequencer', 'audio'
        
        try:
            if player_id in ['video', 'artnet']:
                player = self.player_manager.get_player(player_id)
                if not player:
                    return False
                
                if parts[1] == 'effect':
                    # Effect parameter: video.effect.0.brightness
                    effect_index = int(parts[2])
                    param_name = parts[3]
                    player.set_effect_parameter(effect_index, param_name, value)
                    
                elif parts[1] == 'layer':
                    # Layer parameter: video.layer.0.opacity
                    layer_index = int(parts[2])
                    if parts[3] == 'opacity':
                        player.layer_manager.layers[layer_index].opacity = value
                    elif parts[3] == 'enabled':
                        player.layer_manager.layers[layer_index].enabled = bool(value)
                    elif parts[3] == 'effect':
                        # Layer effect: video.layer.0.effect.1.brightness
                        effect_index = int(parts[4])
                        param_name = parts[5]
                        layer = player.layer_manager.layers[layer_index]
                        if effect_index < len(layer.effects):
                            effect = layer.effects[effect_index]
                            effect['config'][param_name] = value
                            # Reinitialize effect if needed
                            if effect.get('instance'):
                                effect['instance'].set_parameter(param_name, value)
                
                elif parts[1] == 'generator':
                    # Generator parameter: video.generator.speed
                    param_name = parts[2]
                    if hasattr(player, 'source') and hasattr(player.source, 'parameters'):
                        player.source.parameters[param_name] = value
                        player.source.set_parameter(param_name, value)
                
                elif parts[1] == 'global':
                    # Global parameter: video.global.speed
                    if parts[2] == 'speed':
                        player.playback_speed = value
            
            elif player_id == 'sequencer':
                if parts[1] == 'bpm':
                    if hasattr(self.player_manager, 'sequencer'):
                        self.player_manager.sequencer.set_bpm(value)
            
            elif player_id == 'audio':
                if parts[1] == 'gain':
                    if hasattr(self.player_manager, 'audio_analyzer'):
                        self.player_manager.audio_analyzer.set_gain(value)
            
            # Update cached value
            param.current_value = value
            
            # Notify callbacks
            self._notify_callbacks('value_changed', path, value)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update parameter {path}: {e}")
            return False
    
    def register_callback(self, callback):
        """Register callback for parameter changes"""
        self.update_callbacks.append(callback)
    
    def _notify_callbacks(self, event_type: str, *args):
        """Notify all callbacks of parameter change"""
        for callback in self.update_callbacks:
            try:
                callback(event_type, *args)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    def export_parameter_list(self) -> List[Dict[str, Any]]:
        """Export all parameters as list (for UI/API)"""
        return [param.to_dict() for param in self.parameters.values()]
```

#### 0.2 Dynamic Parameter Tracking

The parameter registry automatically rescans when:
1. **Effect added/removed** → Rescan effect chain
2. **Layer added/removed** → Rescan layers
3. **Generator loaded** → Rescan generator parameters
4. **Clip changed** → Rescan all (different effects per clip)

**Hook into existing events:**

```python
# In player_core.py - when adding effect
def add_effect(self, effect_id, config=None):
    # ... existing code ...
    
    # Trigger parameter rescan
    if hasattr(self.player_manager, 'parameter_registry'):
        self.player_manager.parameter_registry.scan_all_parameters()

# In layer_manager.py - when adding layer
def add_layer(self, source, blend_mode='normal', opacity=100.0):
    # ... existing code ...
    
    # Trigger parameter rescan
    if hasattr(self.player, 'player_manager') and \
       hasattr(self.player.player_manager, 'parameter_registry'):
        self.player.player_manager.parameter_registry.scan_all_parameters()
```

#### 0.3 API Endpoints for Parameter Discovery

```python
@app.route('/api/parameters', methods=['GET'])
def get_all_parameters():
    """Get all controllable parameters"""
    try:
        if parameter_registry:
            parameters = parameter_registry.export_parameter_list()
            return jsonify({
                'success': True,
                'parameters': parameters,
                'count': len(parameters)
            })
        return jsonify({'success': False, 'error': 'Parameter registry not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/parameters/category/<category>', methods=['GET'])
def get_parameters_by_category(category):
    """Get parameters filtered by category"""
    try:
        if parameter_registry:
            params = parameter_registry.get_parameters_by_category(category)
            return jsonify({
                'success': True,
                'parameters': [p.to_dict() for p in params.values()],
                'category': category
            })
        return jsonify({'success': False, 'error': 'Parameter registry not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/parameters/rescan', methods=['POST'])
def rescan_parameters():
    """Trigger parameter rescan"""
    try:
        if parameter_registry:
            parameters = parameter_registry.scan_all_parameters()
            return jsonify({
                'success': True,
                'count': len(parameters)
            })
        return jsonify({'success': False, 'error': 'Parameter registry not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@socketio.on('parameter_value_changed')
def handle_parameter_value_change(data):
    """Handle parameter value change from frontend"""
    try:
        path = data.get('path')
        value = data.get('value')
        
        if parameter_registry:
            success = parameter_registry.update_parameter_value(path, value)
            if success:
                # Broadcast to all clients
                socketio.emit('parameter_updated', {'path': path, 'value': value})
    except Exception as e:
        logger.error(f"Parameter update failed: {e}")
```

#### 0.4 Frontend Parameter Browser

```javascript
class ParameterBrowser {
    constructor() {
        this.parameters = [];
        this.filteredParameters = [];
        this.selectedCategory = 'all';
    }
    
    async loadParameters() {
        const response = await fetch('/api/parameters');
        const data = await response.json();
        if (data.success) {
            this.parameters = data.parameters;
            this.updateUI();
        }
    }
    
    filterByCategory(category) {
        this.selectedCategory = category;
        if (category === 'all') {
            this.filteredParameters = this.parameters;
        } else {
            this.filteredParameters = this.parameters.filter(
                p => p.category === category
            );
        }
        this.updateUI();
    }
    
    updateUI() {
        const container = document.getElementById('parameterList');
        container.innerHTML = '';
        
        this.filteredParameters.forEach(param => {
            const row = document.createElement('div');
            row.className = 'parameter-row';
            row.innerHTML = `
                <div class="param-name">${param.name}</div>
                <div class="param-path">${param.path}</div>
                <div class="param-value">${param.value.toFixed(2)}</div>
                <div class="param-range">${param.min} - ${param.max}</div>
                <button onclick="startMIDILearn('${param.path}')" 
                        class="btn btn-sm btn-warning">
                    🎹 Learn
                </button>
            `;
            container.appendChild(row);
        });
    }
}

// Global instance
window.parameterBrowser = new ParameterBrowser();
```

### Phase 1A: Core MIDI Infrastructure - Web MIDI API (4-6h)

#### 1.1 Frontend MIDI Module (`frontend/js/midi-manager.js`)

```javascript
class MIDIManager {
    constructor() {
        this.midiAccess = null;
        this.selectedDevice = null;
        this.inputs = [];
        this.outputs = [];
        this.mappings = new Map(); // CC/note -> parameter path
        this.learnMode = false;
        this.learnCallback = null;
    }
    
    async initialize() {
        if (!navigator.requestMIDIAccess) {
            throw new Error('Web MIDI API not supported');
        }
        
        this.midiAccess = await navigator.requestMIDIAccess();
        this.updateDeviceList();
        
        // Listen for device changes (plug/unplug)
        this.midiAccess.onstatechange = () => this.updateDeviceList();
    }
    
    updateDeviceList() {
        this.inputs = Array.from(this.midiAccess.inputs.values());
        this.outputs = Array.from(this.midiAccess.outputs.values());
    }
    
    connectDevice(deviceId) {
        const input = this.midiAccess.inputs.get(deviceId);
        if (input) {
            input.onmidimessage = (msg) => this.handleMIDIMessage(msg);
            this.selectedDevice = input;
        }
    }
    
    handleMIDIMessage(message) {
        const [status, data1, data2] = message.data;
        const messageType = status & 0xF0;
        const channel = status & 0x0F;
        
        // MIDI Learn mode
        if (this.learnMode && this.learnCallback) {
            this.learnCallback({ type: messageType, channel, data1, data2 });
            return;
        }
        
        // Control Change (CC)
        if (messageType === 0xB0) {
            const ccNumber = data1;
            const value = data2; // 0-127
            this.handleCC(ccNumber, value);
        }
        
        // Note On/Off
        else if (messageType === 0x90 || messageType === 0x80) {
            const note = data1;
            const velocity = data2;
            const isNoteOn = messageType === 0x90 && velocity > 0;
            this.handleNote(note, velocity, isNoteOn);
        }
    }
    
    handleCC(ccNumber, value) {
        const mapping = this.mappings.get(`cc:${ccNumber}`);
        if (mapping) {
            // Send via WebSocket
            socket.emit('midi_parameter_update', {
                path: mapping.path,
                value: this.scaleValue(value, mapping.min, mapping.max)
            });
        }
    }
    
    scaleValue(midiValue, min, max) {
        // Scale MIDI 0-127 to parameter range
        return min + (midiValue / 127) * (max - min);
    }
    
    startLearn(parameterPath, callback) {
        this.learnMode = true;
        this.learnCallback = (midiData) => {
            // Create mapping
            const key = `cc:${midiData.data1}`;
            this.mappings.set(key, {
                path: parameterPath,
                min: 0,
                max: 100
            });
            
            // Save to backend
            this.saveMappings();
            
            callback(midiData);
            this.stopLearn();
        };
    }
    
    stopLearn() {
        this.learnMode = false;
        this.learnCallback = null;
    }
    
    async loadMappings() {
        const response = await fetch('/api/midi/mappings');
        const data = await response.json();
        if (data.success) {
            this.mappings = new Map(Object.entries(data.mappings));
        }
    }
    
    async saveMappings() {
        await fetch('/api/midi/mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                mappings: Object.fromEntries(this.mappings)
            })
        });
    }
}

// Global instance
window.midiManager = new MIDIManager();
```

#### 1.2 Backend MIDI Handler (`src/modules/midi_manager.py`)

```python
"""
MIDI Manager - Handles MIDI mappings and parameter updates
"""
from typing import Dict, Any, Optional
from ..logger import get_logger

logger = get_logger(__name__)


class MIDIMapping:
    """Single MIDI CC/Note to Parameter mapping with global/local support"""
    
    def __init__(self, midi_type: str, midi_number: int, parameter_path: str, 
                 min_value: float = 0, max_value: float = 100, 
                 mapping_mode: str = 'local', name: str = ''):
        self.midi_type = midi_type  # 'cc' or 'note'
        self.midi_number = midi_number  # CC number or note number
        self.parameter_path = parameter_path  # 'video.effect.0.brightness' or '*.brightness'
        self.min_value = min_value
        self.max_value = max_value
        self.mapping_mode = mapping_mode  # 'local' or 'global'
        self.name = name  # User-friendly name: "Master Brightness", "Layer Opacity"
        self.valid = True  # For validation tracking
    
    def is_global(self) -> bool:
        """Check if this is a global pattern mapping"""
        return self.mapping_mode == 'global' or '*' in self.parameter_path
    
    def matches_path(self, path: str) -> bool:
        """Check if parameter path matches this mapping (supports wildcards)"""
        if self.mapping_mode == 'local':
            return path == self.parameter_path
        
        # Global pattern matching
        pattern = self.parameter_path
        
        # Simple wildcard matching
        pattern_parts = pattern.split('.')
        path_parts = path.split('.')
        
        if len(pattern_parts) != len(path_parts):
            return False
        
        for pattern_part, path_part in zip(pattern_parts, path_parts):
            if pattern_part == '*':
                continue  # Wildcard matches anything
            if pattern_part != path_part:
                return False
        
        return True
    
    def get_matching_paths(self, parameter_registry) -> List[str]:
        """Get all parameter paths that match this mapping"""
        if self.mapping_mode == 'local':
            # Check if single path exists
            param = parameter_registry.get_parameter(self.parameter_path)
            return [self.parameter_path] if param else []
        
        # Global: Find all matching paths
        matching = []
        for path in parameter_registry.parameters.keys():
            if self.matches_path(path):
                matching.append(path)
        
        return matching
    
    def scale_value(self, midi_value: int) -> float:
        """Scale MIDI value (0-127) to parameter range"""
        normalized = midi_value / 127.0
        return self.min_value + normalized * (self.max_value - self.min_value)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': self.midi_type,
            'number': self.midi_number,
            'path': self.parameter_path,
            'min': self.min_value,
            'max': self.max_value,
            'mode': self.mapping_mode,
            'name': self.name,
            'is_global': self.is_global()
        }


class MIDIProfile:
    """MIDI profile - collection of mappings that can be saved/loaded"""
    
    def __init__(self, name: str, description: str = ''):
        self.name = name
        self.description = description
        self.mappings: Dict[str, MIDIMapping] = {}
        self.created = datetime.now().isoformat()
        self.modified = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'created': self.created,
            'modified': self.modified,
            'mappings': {
                key: mapping.to_dict() 
                for key, mapping in self.mappings.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MIDIProfile':
        profile = cls(data['name'], data.get('description', ''))
        profile.created = data.get('created', datetime.now().isoformat())
        profile.modified = data.get('modified', datetime.now().isoformat())
        
        for key, mapping_data in data.get('mappings', {}).items():
            profile.mappings[key] = MIDIMapping(
                midi_type=mapping_data['type'],
                midi_number=mapping_data['number'],
                parameter_path=mapping_data['path'],
                min_value=mapping_data.get('min', 0),
                max_value=mapping_data.get('max', 100),
                mapping_mode=mapping_data.get('mode', 'local'),
                name=mapping_data.get('name', '')
            )
        
        return profile


class MIDIManager:
    """Manages MIDI profiles, mappings and parameter updates"""
    
    def __init__(self, player_manager, parameter_registry):
        self.player_manager = player_manager
        self.parameter_registry = parameter_registry
        self.profiles: Dict[str, MIDIProfile] = {}
        self.active_profile_name: Optional[str] = None
        self.learn_mode = False
        self.learn_callback = None
        
        # Load profiles from file
        self.profiles_file = 'config/midi_profiles.json'
        self.load_profiles()
    
    @property
    def active_profile(self) -> Optional[MIDIProfile]:
        """Get currently active profile"""
        return self.profiles.get(self.active_profile_name) if self.active_profile_name else None
    
    @property
    def mappings(self) -> Dict[str, MIDIMapping]:
        """Get mappings from active profile"""
        return self.active_profile.mappings if self.active_profile else {}
    
    def load_profiles(self):
        """Load MIDI profiles from config/midi_profiles.json"""
        try:
            if not os.path.exists(self.profiles_file):
                # Create default profile
                self.create_profile('Default', 'Default MIDI profile')
                self.active_profile_name = 'Default'
                self.save_profiles()
                logger.info("📁 Created default MIDI profile")
                return
            
            with open(self.profiles_file, 'r') as f:
                data = json.load(f)
            
            # Load profiles
            for profile_data in data.get('profiles', []):
                profile = MIDIProfile.from_dict(profile_data)
                self.profiles[profile.name] = profile
            
            # Set active profile
            self.active_profile_name = data.get('active_profile', 'Default')
            
            logger.info(f"📁 Loaded {len(self.profiles)} MIDI profiles, active: {self.active_profile_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load MIDI profiles: {e}")
            # Create default profile as fallback
            self.create_profile('Default', 'Default MIDI profile')
            self.active_profile_name = 'Default'
    
    def save_profiles(self):
        """Save MIDI profiles to config/midi_profiles.json"""
        try:
            os.makedirs(os.path.dirname(self.profiles_file), exist_ok=True)
            
            data = {
                'active_profile': self.active_profile_name,
                'profiles': [
                    profile.to_dict() 
                    for profile in self.profiles.values()
                ]
            }
            
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"💾 Saved {len(self.profiles)} MIDI profiles")
            
        except Exception as e:
            logger.error(f"❌ Failed to save MIDI profiles: {e}")
    
    def create_profile(self, name: str, description: str = '') -> MIDIProfile:
        """Create new MIDI profile"""
        profile = MIDIProfile(name, description)
        self.profiles[name] = profile
        self.save_profiles()
        logger.info(f"📝 Created MIDI profile: {name}")
        return profile
    
    def delete_profile(self, name: str) -> bool:
        """Delete MIDI profile"""
        if name == 'Default':
            logger.warning("Cannot delete Default profile")
            return False
        
        if name in self.profiles:
            del self.profiles[name]
            if self.active_profile_name == name:
                self.active_profile_name = 'Default'
            self.save_profiles()
            logger.info(f"🗑️ Deleted MIDI profile: {name}")
            return True
        return False
    
    def switch_profile(self, name: str) -> bool:
        """Switch to different MIDI profile"""
        if name not in self.profiles:
            logger.warning(f"Profile not found: {name}")
            return False
        
        self.active_profile_name = name
        self.save_profiles()
        logger.info(f"🔄 Switched to MIDI profile: {name}")
        return True
    
    def duplicate_profile(self, source_name: str, new_name: str) -> Optional[MIDIProfile]:
        """Duplicate existing profile with new name"""
        if source_name not in self.profiles:
            logger.warning(f"Source profile not found: {source_name}")
            return None
        
        if new_name in self.profiles:
            logger.warning(f"Profile already exists: {new_name}")
            return None
        
        source = self.profiles[source_name]
        new_profile = MIDIProfile(new_name, f"Copy of {source.description}")
        
        # Copy all mappings
        for key, mapping in source.mappings.items():
            new_profile.mappings[key] = MIDIMapping(
                mapping.midi_type,
                mapping.midi_number,
                mapping.parameter_path,
                mapping.min_value,
                mapping.max_value,
                mapping.mapping_mode,
                mapping.name
            )
        
        self.profiles[new_name] = new_profile
        self.save_profiles()
        logger.info(f"📋 Duplicated profile {source_name} → {new_name}")
        return new_profile
    
    def add_mapping(self, midi_type: str, midi_number: int, parameter_path: str,
                   min_value: float = 0, max_value: float = 100, 
                   mapping_mode: str = 'local', name: str = ''):
        """Add or update a MIDI mapping in active profile"""
        if not self.active_profile:
            logger.warning("No active profile")
            return False
        
        key = f"{midi_type}:{midi_number}"
        self.active_profile.mappings[key] = MIDIMapping(
            midi_type, midi_number, parameter_path, min_value, max_value, 
            mapping_mode, name
        )
        self.active_profile.modified = datetime.now().isoformat()
        self.save_profiles()
        
        mode_str = '🌐 GLOBAL' if mapping_mode == 'global' else '📍 LOCAL'
        logger.info(f"🎹 {mode_str} Mapped {key} → {parameter_path}")
        return True
    
    def remove_mapping(self, midi_type: str, midi_number: int):
        """Remove a MIDI mapping from active profile"""
        if not self.active_profile:
            return False
        
        key = f"{midi_type}:{midi_number}"
        if key in self.active_profile.mappings:
            del self.active_profile.mappings[key]
            self.active_profile.modified = datetime.now().isoformat()
            self.save_profiles()
            logger.info(f"🗑️ Removed mapping {key}")
            return True
        return False
    
    def handle_midi_message(self, midi_type: str, midi_number: int, value: int,
                           parameter_registry) -> bool:
        """
        Handle incoming MIDI message and update parameter(s)
        Supports both local and global mappings
        """
        key = f"{midi_type}:{midi_number}"
        mapping = self.mappings.get(key)
        
        if not mapping:
            return False
        
        # Check if mapping is marked invalid
        if not getattr(mapping, 'valid', True):
            logger.warning(f"Skipping invalid mapping: {key}")
            return False
        
        # Scale MIDI value to parameter range
        param_value = mapping.scale_value(value)
        
        # Get matching parameter paths
        matching_paths = mapping.get_matching_paths(parameter_registry)
        
        if not matching_paths:
            logger.warning(f"No parameters match mapping: {key} → {mapping.parameter_path}")
            mapping.valid = False
            return False
        
        # Update all matching parameters
        success_count = 0
        for path in matching_paths:
            if parameter_registry.update_parameter_value(path, param_value):
                success_count += 1
        
        if success_count > 0:
            if mapping.is_global():
                logger.debug(f"🎹 {key} ({value}) → {success_count} parameters = {param_value:.2f}")
            else:
                logger.debug(f"🎹 {key} ({value}) → {mapping.parameter_path} = {param_value:.2f}")
        
        return success_count > 0
    
    def validate_all_mappings(self, parameter_registry) -> Dict[str, Any]:
        """
        Validate all MIDI mappings against current parameter registry
        Returns validation report
        """
        valid_mappings = []
        invalid_mappings = []
        
        for key, mapping in self.mappings.items():
            matching_paths = mapping.get_matching_paths(parameter_registry)
            
            if matching_paths:
                valid_mappings.append({
                    'midi': key,
                    'path': mapping.parameter_path,
                    'name': mapping.name,
                    'mode': mapping.mapping_mode,
                    'matching_count': len(matching_paths),
                    'matching_paths': matching_paths[:5]  # First 5 for display
                })
                mapping.valid = True
            else:
                invalid_mappings.append({
                    'midi': key,
                    'path': mapping.parameter_path,
                    'name': mapping.name,
                    'reason': 'No matching parameters found'
                })
                mapping.valid = False
        
        return {
            'valid_count': len(valid_mappings),
            'invalid_count': len(invalid_mappings),
            'valid': valid_mappings,
            'invalid': invalid_mappings
        }
    
    def get_profile_list(self) -> List[Dict[str, Any]]:
        """Get list of all profiles with metadata"""
        return [
            {
                'name': profile.name,
                'description': profile.description,
                'mapping_count': len(profile.mappings),
                'created': profile.created,
                'modified': profile.modified,
                'is_active': profile.name == self.active_profile_name
            }
            for profile in self.profiles.values()
        ]
                    parameter_path=data['path'],
                    min_value=data.get('min', 0),
                    max_value=data.get('max', 100)
                )
            logger.info(f"🎹 Loaded {len(self.mappings)} MIDI mappings")
    
    def save_mappings(self):
        """Save MIDI mappings to session state"""
        if self.session_state:
            mappings_data = {
                key: mapping.to_dict() 
                for key, mapping in self.mappings.items()
            }
            self.session_state._state['midi_mappings'] = mappings_data
            logger.info(f"💾 Saved {len(self.mappings)} MIDI mappings")
    
    def add_mapping(self, midi_type: str, midi_number: int, parameter_path: str,
                   min_value: float = 0, max_value: float = 100):
        """Add or update a MIDI mapping"""
        key = f"{midi_type}:{midi_number}"
        self.mappings[key] = MIDIMapping(
            midi_type, midi_number, parameter_path, min_value, max_value
        )
        self.save_mappings()
        logger.info(f"🎹 Mapped {key} → {parameter_path}")
    
    def remove_mapping(self, midi_type: str, midi_number: int):
        """Remove a MIDI mapping"""
        key = f"{midi_type}:{midi_number}"
        if key in self.mappings:
            del self.mappings[key]
            self.save_mappings()
            logger.info(f"🗑️ Removed mapping {key}")
    
    def handle_midi_message(self, midi_type: str, midi_number: int, value: int):
        """Handle incoming MIDI message and update parameter"""
        key = f"{midi_type}:{midi_number}"
        mapping = self.mappings.get(key)
        
        if not mapping:
            logger.debug(f"No mapping for {key}")
            return False
        
        # Scale MIDI value to parameter range
        param_value = mapping.scale_value(value)
        
        # Update parameter via player manager
        success = self.update_parameter(mapping.parameter_path, param_value)
        
        if success:
            logger.debug(f"🎹 MIDI {key} ({value}) → {mapping.parameter_path} = {param_value:.2f}")
        
        return success
    
    def update_parameter(self, parameter_path: str, value: float) -> bool:
        """Update parameter via player manager"""
        # Parse parameter path: 'video.effect.0.param.brightness'
        parts = parameter_path.split('.')
        
        if len(parts) < 2:
            logger.warning(f"Invalid parameter path: {parameter_path}")
            return False
        
        player_id = parts[0]  # 'video' or 'artnet'
        
        try:
            if parts[1] == 'effect':
                # Effect parameter: video.effect.0.param.brightness
                effect_index = int(parts[2])
                param_name = parts[4]
                
                player = self.player_manager.get_player(player_id)
                if player:
                    player.set_effect_parameter(effect_index, param_name, value)
                    return True
            
            elif parts[1] == 'generator':
                # Generator parameter: video.generator.param.speed
                param_name = parts[3]
                
                player = self.player_manager.get_player(player_id)
                if player and hasattr(player, 'set_generator_parameter'):
                    player.set_generator_parameter(param_name, value)
                    return True
            
        except Exception as e:
            logger.error(f"Failed to update parameter {parameter_path}: {e}")
        
        return False
    
    def get_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Get all mappings as dict"""
        return {key: mapping.to_dict() for key, mapping in self.mappings.items()}
```

#### 1.3 SocketIO Event Handler (`src/modules/rest_api.py`)

```python
# Add to RestAPI class

@socketio.on('midi_parameter_update')
def handle_midi_parameter_update(data):
    """Handle MIDI parameter update from browser"""
    try:
        midi_type = data.get('type', 'cc')
        midi_number = data.get('number')
        value = data.get('value')
        
        if midi_manager:
            midi_manager.handle_midi_message(midi_type, midi_number, value)
            
    except Exception as e:
        logger.error(f"MIDI parameter update failed: {e}")

@app.route('/api/midi/mappings', methods=['GET'])
def get_midi_mappings():
    """Get all MIDI mappings"""
    try:
        if midi_manager:
            mappings = midi_manager.get_all_mappings()
            return jsonify({'success': True, 'mappings': mappings})
        return jsonify({'success': False, 'error': 'MIDI manager not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/mappings', methods=['POST'])
def save_midi_mappings():
    """Save MIDI mappings"""
    try:
        data = request.get_json()
        mappings = data.get('mappings', {})
        
        if midi_manager:
            # Clear existing mappings
            midi_manager.mappings.clear()
            
            # Add new mappings
            for key, mapping_data in mappings.items():
                midi_manager.add_mapping(
                    midi_type=mapping_data['type'],
                    midi_number=mapping_data['number'],
                    parameter_path=mapping_data['path'],
                    min_value=mapping_data.get('min', 0),
                    max_value=mapping_data.get('max', 100)
                )
            
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'error': 'MIDI manager not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/learn', methods=['POST'])
def midi_learn():
    """Start MIDI learn for parameter"""
    try:
        data = request.get_json()
        parameter_path = data.get('parameter_path')
        
        # Store learn request
        socketio.emit('midi_learn_started', {'path': parameter_path})
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

### Phase 1B: Direct USB MIDI Backend (3-4h)

#### 1.4 Python MIDI Backend (`src/modules/midi_input.py`)

```python
"""
Direct USB MIDI Input Handler
Runs in separate thread, provides backup when Web MIDI not available
"""
import threading
import time
from typing import Optional, Callable
from ..logger import get_logger

try:
    import rtmidi
    RTMIDI_AVAILABLE = True
except ImportError:
    RTMIDI_AVAILABLE = False

logger = get_logger(__name__)


class DirectMIDIInput:
    """Direct USB MIDI input handler using python-rtmidi"""
    
    def __init__(self, midi_manager, enabled=False):
        self.midi_manager = midi_manager
        self.enabled = enabled
        self.midi_in = None
        self.selected_port = None
        self.running = False
        self.thread = None
        
        if not RTMIDI_AVAILABLE:
            logger.warning("⚠️ python-rtmidi not installed. Direct USB MIDI disabled.")
            logger.info("   Install with: pip install python-rtmidi")
            return
        
        if self.enabled:
            self.initialize()
    
    def initialize(self):
        """Initialize MIDI input"""
        if not RTMIDI_AVAILABLE:
            return False
        
        try:
            self.midi_in = rtmidi.MidiIn()
            logger.info("🎹 Direct MIDI input initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize MIDI input: {e}")
            return False
    
    def get_available_ports(self):
        """Get list of available MIDI input ports"""
        if not self.midi_in:
            return []
        
        try:
            ports = self.midi_in.get_ports()
            logger.info(f"🎹 Available MIDI ports: {ports}")
            return ports
        except Exception as e:
            logger.error(f"❌ Failed to get MIDI ports: {e}")
            return []
    
    def open_port(self, port_index: int = 0, port_name: Optional[str] = None):
        """Open MIDI input port"""
        if not self.midi_in:
            return False
        
        try:
            # Close existing port if open
            if self.midi_in.is_port_open():
                self.midi_in.close_port()
            
            # Open by index or name
            if port_name:
                ports = self.get_available_ports()
                if port_name in ports:
                    port_index = ports.index(port_name)
                else:
                    logger.error(f"❌ Port '{port_name}' not found")
                    return False
            
            self.midi_in.open_port(port_index)
            self.selected_port = port_index
            
            # Set callback
            self.midi_in.set_callback(self._midi_callback)
            
            port_name = self.get_available_ports()[port_index]
            logger.info(f"✅ Opened MIDI port {port_index}: {port_name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to open MIDI port {port_index}: {e}")
            return False
    
    def _midi_callback(self, event, data=None):
        """Callback for MIDI messages (runs in MIDI thread)"""
        message, deltatime = event
        
        if len(message) < 2:
            return
        
        status = message[0]
        data1 = message[1]
        data2 = message[2] if len(message) > 2 else 0
        
        message_type = status & 0xF0
        channel = status & 0x0F
        
        # Control Change (CC)
        if message_type == 0xB0:
            cc_number = data1
            value = data2
            logger.debug(f"🎹 CC {cc_number} = {value}")
            self.midi_manager.handle_midi_message('cc', cc_number, value)
        
        # Note On/Off
        elif message_type == 0x90 or message_type == 0x80:
            note = data1
            velocity = data2
            is_note_on = message_type == 0x90 and velocity > 0
            logger.debug(f"🎹 Note {note} {'ON' if is_note_on else 'OFF'} (vel={velocity})")
            
            # Treat note as toggle (0/127)
            value = 127 if is_note_on else 0
            self.midi_manager.handle_midi_message('note', note, value)
    
    def start_monitoring(self):
        """Start MIDI monitoring thread (alternative to callback)"""
        if not self.midi_in or not self.midi_in.is_port_open():
            logger.error("❌ No MIDI port open")
            return False
        
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("🎹 MIDI monitoring started")
        return True
    
    def _monitor_loop(self):
        """Monitor MIDI input in separate thread"""
        while self.running:
            try:
                message = self.midi_in.get_message()
                if message:
                    midi_message, deltatime = message
                    self._process_message(midi_message)
                time.sleep(0.001)  # 1ms polling
            except Exception as e:
                logger.error(f"❌ MIDI monitoring error: {e}")
                time.sleep(0.1)
    
    def _process_message(self, message):
        """Process MIDI message"""
        if len(message) < 2:
            return
        
        status = message[0]
        data1 = message[1]
        data2 = message[2] if len(message) > 2 else 0
        
        message_type = status & 0xF0
        
        if message_type == 0xB0:  # CC
            self.midi_manager.handle_midi_message('cc', data1, data2)
        elif message_type == 0x90 or message_type == 0x80:  # Note
            velocity = data2 if message_type == 0x90 else 0
            value = 127 if velocity > 0 else 0
            self.midi_manager.handle_midi_message('note', data1, value)
    
    def stop_monitoring(self):
        """Stop MIDI monitoring"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("🎹 MIDI monitoring stopped")
    
    def close(self):
        """Close MIDI port and cleanup"""
        self.stop_monitoring()
        
        if self.midi_in and self.midi_in.is_port_open():
            self.midi_in.close_port()
            logger.info("🎹 MIDI port closed")
        
        del self.midi_in
        self.midi_in = None
```

#### 1.5 Configuration (`config.json`)

Add MIDI configuration section:

```json
{
  "midi": {
    "enabled": true,
    "web_midi": {
      "enabled": true,
      "comment": "Browser-based MIDI via Web MIDI API (primary)"
    },
    "direct_usb": {
      "enabled": false,
      "auto_connect": true,
      "port_name": null,
      "port_index": 0,
      "comment": "Direct USB MIDI on server (backup/compatibility)"
    }
  }
}
```

#### 1.6 Integration in `main.py`

```python
# Initialize MIDI Manager
midi_manager = None
direct_midi_input = None

if config.get('midi', {}).get('enabled', True):
    from modules.midi_manager import MIDIManager
    from modules.midi_input import DirectMIDIInput
    
    midi_manager = MIDIManager(player_manager, session_state_instance)
    logger.info("🎹 MIDI Manager initialized")
    
    # Direct USB MIDI (if enabled)
    direct_config = config.get('midi', {}).get('direct_usb', {})
    if direct_config.get('enabled', False):
        direct_midi_input = DirectMIDIInput(
            midi_manager, 
            enabled=True
        )
        
        # Auto-connect to first available port
        if direct_config.get('auto_connect', True):
            ports = direct_midi_input.get_available_ports()
            if ports:
                port_name = direct_config.get('port_name')
                port_index = direct_config.get('port_index', 0)
                
                if direct_midi_input.open_port(port_index, port_name):
                    logger.info(f"✅ Auto-connected to MIDI port: {ports[port_index]}")
            else:
                logger.warning("⚠️ No MIDI ports available for auto-connect")
    
    # Set MIDI manager in REST API for WebSocket events
    rest_api.midi_manager = midi_manager
    rest_api.direct_midi_input = direct_midi_input
```

#### 1.7 Backend API Endpoints for Direct MIDI

Add to `src/modules/api_routes.py`:

```python
@app.route('/api/midi/ports', methods=['GET'])
def get_midi_ports():
    """Get available direct USB MIDI ports"""
    try:
        if direct_midi_input:
            ports = direct_midi_input.get_available_ports()
            return jsonify({
                'success': True,
                'ports': ports,
                'selected': direct_midi_input.selected_port,
                'available': True
            })
        return jsonify({
            'success': True,
            'ports': [],
            'available': False,
            'message': 'Direct MIDI not enabled or python-rtmidi not installed'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/ports/<int:port_index>', methods=['POST'])
def connect_midi_port(port_index):
    """Connect to direct USB MIDI port"""
    try:
        if direct_midi_input:
            if direct_midi_input.open_port(port_index):
                return jsonify({'success': True, 'port': port_index})
            return jsonify({'success': False, 'error': 'Failed to open port'})
        return jsonify({'success': False, 'error': 'Direct MIDI not available'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/status', methods=['GET'])
def get_midi_status():
    """Get MIDI system status"""
    try:
        web_midi_enabled = config.get('midi', {}).get('web_midi', {}).get('enabled', True)
        direct_midi_enabled = config.get('midi', {}).get('direct_usb', {}).get('enabled', False)
        
        status = {
            'web_midi': {
                'enabled': web_midi_enabled,
                'supported': 'Requires Chrome/Edge/Opera'
            },
            'direct_usb': {
                'enabled': direct_midi_enabled,
                'available': direct_midi_input is not None,
                'connected': direct_midi_input and direct_midi_input.midi_in and direct_midi_input.midi_in.is_port_open() if direct_midi_input else False,
                'port': direct_midi_input.selected_port if direct_midi_input else None
            },
            'mappings_count': len(midi_manager.mappings) if midi_manager else 0
        }
        
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

### Phase 2: MIDI Learn UI (2-3h)

#### 2.1 Dynamic Parameter Handling in MIDI Learn

**Challenge:** Effects/layers/generators can be added/removed at runtime, making MIDI mappings invalid.

**Solution:** Use parameter paths (strings) instead of object references + validation system.

**Example Scenario:**
1. User maps `CC#14 → video.effect.0.brightness` (Blur effect brightness)
2. User removes Blur effect
3. Parameter path `video.effect.0.brightness` no longer exists
4. MIDI mapping should either:
   - Gracefully fail (log warning, skip update)
   - Auto-remap to new effect at index 0 (if user enables this)
   - Show "Invalid Mappings" warning in UI

**Backend Validation:**

```python
# Add to MIDIManager class in midi_manager.py

def validate_all_mappings(self, parameter_registry) -> Dict[str, Any]:
    """
    Validate all MIDI mappings against current parameter registry
    Returns validation report
    """
    valid_mappings = []
    invalid_mappings = []
    
    for key, mapping in self.mappings.items():
        param_path = mapping.parameter_path
        param = parameter_registry.get_parameter(param_path)
        
        if param:
            valid_mappings.append({
                'midi': key,
                'path': param_path,
                'name': param.name,
                'current_value': param.current_value
            })
            mapping.valid = True
        else:
            invalid_mappings.append({
                'midi': key,
                'path': param_path,
                'reason': 'Parameter not found (effect/layer removed?)'
            })
            mapping.valid = False
    
    return {
        'valid_count': len(valid_mappings),
        'invalid_count': len(invalid_mappings),
        'valid': valid_mappings,
        'invalid': invalid_mappings
    }

def handle_midi_message(self, midi_type: str, midi_number: int, value: int, 
                       parameter_registry) -> bool:
    """
    Handle incoming MIDI message with validation
    """
    key = f"{midi_type}:{midi_number}"
    mapping = self.mappings.get(key)
    
    if not mapping:
        return False
    
    # Check if mapping is marked invalid
    if not getattr(mapping, 'valid', True):
        logger.warning(f"Skipping invalid MIDI mapping: {key} → {mapping.parameter_path}")
        return False
    
    # Verify parameter still exists (real-time validation)
    param = parameter_registry.get_parameter(mapping.parameter_path)
    if not param:
        logger.warning(f"Parameter no longer exists: {mapping.parameter_path}")
        mapping.valid = False  # Mark as invalid
        return False
    
    # Scale and apply
    param_value = mapping.scale_value(value)
    success = parameter_registry.update_parameter_value(mapping.parameter_path, param_value)
    
    if success:
        logger.debug(f"🎹 {key} ({value}) → {mapping.parameter_path} = {param_value:.2f}")
    
    return success
```

**Frontend Validation UI:**

```javascript
// Add to player.js

class MIDILearnManager {
    constructor(midiManager) {
        this.midiManager = midiManager;
        this.learnMode = false;
        this.learnTargetPath = null;
        this.learnCallback = null;
    }
    
    async startLearn(parameterPath, parameterName) {
        // Verify parameter exists
        const param = await this.getParameter(parameterPath);
        if (!param) {
            showToast('Parameter not found! Try rescanning.', 'error');
            return;
        }
        
        this.learnMode = true;
        this.learnTargetPath = parameterPath;
        
        // Show learn modal
        const modal = new bootstrap.Modal(document.getElementById('midiLearnModal'));
        document.getElementById('learnParameterName').textContent = parameterName;
        document.getElementById('learnParameterPath').textContent = parameterPath;
        modal.show();
        
        // Listen for MIDI input
        this.learnCallback = (midiData) => {
            this.completeLearn(midiData, param);
        };
        
        this.midiManager.setLearnMode(true, this.learnCallback);
    }
    
    async completeLearn(midiData, param) {
        const mapping = {
            midi_type: 'cc',  // or 'note'
            midi_number: midiData.cc || midiData.note,
            parameter_path: this.learnTargetPath,
            min_value: param.min,
            max_value: param.max
        };
        
        // Send to backend
        const response = await fetch('/api/midi/mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(mapping)
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`Mapped CC${midiData.cc} to ${param.name}`, 'success');
            this.cancelLearn();
            this.refreshMappingList();
        }
    }
    
    cancelLearn() {
        this.learnMode = false;
        this.learnTargetPath = null;
        this.midiManager.setLearnMode(false, null);
        
        const modal = bootstrap.Modal.getInstance(document.getElementById('midiLearnModal'));
        if (modal) modal.hide();
    }
    
    async validateAllMappings() {
        const response = await fetch('/api/midi/mappings/validate', {method: 'POST'});
        const data = await response.json();
        
        if (data.success && data.report.invalid_count > 0) {
            this.showInvalidMappingsWarning(data.report.invalid);
        }
        
        return data.report;
    }
    
    showInvalidMappingsWarning(invalidMappings) {
        const list = invalidMappings.map(m => 
            `<li><code>${m.midi}</code> → <code>${m.path}</code><br>
             <small class="text-muted">${m.reason}</small></li>`
        ).join('');
        
        const html = `
            <div class="alert alert-warning">
                <h6>⚠️ Invalid MIDI Mappings Detected</h6>
                <p>The following MIDI mappings point to parameters that no longer exist:</p>
                <ul>${list}</ul>
                <button onclick="midiLearnManager.removeInvalidMappings()" class="btn btn-sm btn-danger">
                    Remove All Invalid
                </button>
            </div>
        `;
        
        document.getElementById('midiValidationWarning').innerHTML = html;
    }
    
    async removeInvalidMappings() {
        const response = await fetch('/api/midi/mappings/remove_invalid', {method: 'POST'});
        const data = await response.json();
        
        if (data.success) {
            showToast(`Removed ${data.removed_count} invalid mappings`, 'success');
            this.refreshMappingList();
            document.getElementById('midiValidationWarning').innerHTML = '';
        }
    }
    
    async getParameter(path) {
        const response = await fetch(`/api/parameters?path=${encodeURIComponent(path)}`);
        const data = await response.json();
        return data.success ? data.parameter : null;
    }
    
    async refreshMappingList() {
        const response = await fetch('/api/midi/mappings');
        const data = await response.json();
        
        if (data.success) {
            this.displayMappings(data.mappings);
        }
    }
    
    displayMappings(mappings) {
        const container = document.getElementById('midiMappingList');
        container.innerHTML = '';
        
        mappings.forEach(mapping => {
            const row = document.createElement('div');
            row.className = 'mapping-row d-flex align-items-center mb-2 p-2 bg-secondary rounded';
            
            const validClass = mapping.valid ? 'text-success' : 'text-danger';
            const validIcon = mapping.valid ? '✓' : '✗';
            
            row.innerHTML = `
                <span class="${validClass} me-2">${validIcon}</span>
                <strong class="me-2">${mapping.midi}</strong>
                <span class="flex-grow-1 font-monospace">${mapping.path}</span>
                <span class="badge bg-info me-2">${mapping.min} - ${mapping.max}</span>
                <button onclick="midiLearnManager.removeMapping('${mapping.midi}')" 
                        class="btn btn-sm btn-danger">
                    🗑️
                </button>
            `;
            
            container.appendChild(row);
        });
    }
}

// Initialize
window.midiLearnManager = new MIDILearnManager(window.midiManager);

// Auto-validate on parameter structure change
socket.on('parameter_structure_changed', async () => {
    console.log('🔄 Parameter structure changed, validating MIDI mappings...');
    await midiLearnManager.validateAllMappings();
});
```

**Backend API Endpoints:**

```python
@app.route('/api/midi/mappings/validate', methods=['POST'])
def validate_midi_mappings():
    """Validate all MIDI mappings"""
    try:
        if not midi_manager or not parameter_registry:
            return jsonify({'success': False, 'error': 'MIDI or parameter registry not available'})
        
        report = midi_manager.validate_all_mappings(parameter_registry)
        
        return jsonify({
            'success': True,
            'report': report
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/mappings/remove_invalid', methods=['POST'])
def remove_invalid_mappings():
    """Remove all invalid MIDI mappings"""
    try:
        if not midi_manager:
            return jsonify({'success': False, 'error': 'MIDI manager not available'})
        
        removed = []
        for key, mapping in list(midi_manager.mappings.items()):
            if not getattr(mapping, 'valid', True):
                del midi_manager.mappings[key]
                removed.append(key)
        
        if removed:
            midi_manager.save_mappings()
        
        return jsonify({
            'success': True,
            'removed_count': len(removed),
            'removed': removed
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### 2.2 MIDI Settings Modal (Add to `player.html`)

```html
<!-- MIDI Settings Modal -->
<div class="modal fade" id="midiSettingsModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content bg-dark text-light">
            <div class="modal-header border-secondary">
                <h5 class="modal-title">🎹 MIDI Control</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Mode Selection -->
                <div class="mb-3">
                    <label class="form-label">MIDI Mode</label>
                    <select class="form-select bg-dark text-light border-secondary" id="midiModeSelect" onchange="midiModeChanged()">
                        <option value="web">Web MIDI (Browser-based)</option>
                        <option value="direct">Direct USB (Server-based)</option>
                    </select>
                    <small class="text-muted">Web MIDI = remote control, Direct USB = server console</small>
                </div>
                
                <!-- Web MIDI Device Selection -->
                <div class="mb-3" id="webMidiSection">
                    <label class="form-label">Web MIDI Device</label>
                    <select class="form-select bg-dark text-light border-secondary" id="midiDeviceSelect">
                        <option value="">No device selected</option>
                    </select>
                    <button class="btn btn-sm btn-outline-primary mt-2" onclick="midiRefreshDevices()">
                        🔄 Refresh Devices
                    </button>
                </div>
                
                <!-- Direct USB MIDI Port Selection -->
                <div class="mb-3" id="directMidiSection" style="display: none;">
                    <label class="form-label">Direct USB MIDI Port</label>
                    <select class="form-select bg-dark text-light border-secondary" id="directMidiPortSelect">
                        <option value="">No port selected</option>
                    </select>
                    <button class="btn btn-sm btn-outline-primary mt-2" onclick="refreshDirectMidiPorts()">
                        🔄 Refresh Ports
                    </button>
                    <button class="btn btn-sm btn-success mt-2" onclick="connectDirectMidiPort()">
                        🔌 Connect
                    </button>
                </div>
                
                <!-- Device Selection -->
                <div class="mb-3">
                    <label class="form-label">MIDI Device</label>
                    <select class="form-select bg-dark text-light border-secondary" id="midiDeviceSelect">
                        <option value="">No device selected</option>
                    </select>
                    <button class="btn btn-sm btn-outline-primary mt-2" onclick="midiRefreshDevices()">
                        🔄 Refresh Devices
                    </button>
                </div>
                
                <!-- MIDI Mappings Table -->
                <div class="mb-3">
                    <label class="form-label">Mappings</label>
                    <table class="table table-dark table-sm">
                        <thead>
                            <tr>
                                <th>MIDI</th>
                                <th>Parameter</th>
                                <th>Range</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody id="midiMappingsTable">
                            <tr><td colspan="4" class="text-center text-muted">No mappings yet</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <!-- Status -->
                <div id="midiStatus" class="alert alert-info" style="display: none;"></div>
            </div>
            <div class="modal-footer border-secondary">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
            </div>
        </div>
    </div>
</div>
```

#### 2.2 Parameter MIDI Learn Button

Add to effect parameter controls:

```html
<button class="btn btn-sm btn-outline-warning" 
        onclick="startMIDILearn('video.effect.0.param.brightness')"
        title="MIDI Learn">
    🎹
</button>
```

### Phase 3: Session State Integration (1h)

Update `src/modules/session_state.py` to persist MIDI mappings:

```python
def _build_state_dict(self, player_manager, clip_registry) -> Dict[str, Any]:
    # ... existing code ...
    
    # MIDI mappings
    if hasattr(player_manager, 'midi_manager') and player_manager.midi_manager:
        state["midi_mappings"] = player_manager.midi_manager.get_all_mappings()
        logger.debug(f"🎹 MIDI mappings saved: {len(state['midi_mappings'])} mappings")
    
    return state
```

## Usage Workflow

### Mode 1: Web MIDI (Remote Control)

#### 1. Connect MIDI Controller
1. Plug MIDI controller into **your local machine** (not server)
2. Open player page in Chrome/Edge
3. Click "🎹 MIDI" button in toolbar
4. Select "Web MIDI (Browser-based)" mode
5. Select device from dropdown
6. Browser requests MIDI permission (one-time)
7. Controller is now active - works from anywhere on network

#### 2. Map Parameters (MIDI Learn)
1. Click 🎹 button next to any parameter slider
2. Status shows "Waiting for MIDI input..."
3. Move fader/knob on MIDI controller
4. Mapping created automatically
5. Test by moving controller - parameter updates

### Mode 2: Direct USB (Server Console)

#### 1. Connect MIDI Controller
1. Plug MIDI controller into **server machine** via USB
2. Open player page (any browser)
3. Click "🎹 MIDI" button in toolbar
4. Select "Direct USB (Server-based)" mode
5. Click "🔄 Refresh Ports" to detect devices
6. Select port from dropdown
7. Click "🔌 Connect"
8. Controller is now active - only works when plugged into server

#### 2. Map Parameters
Same MIDI Learn workflow as Web MIDI - mappings work for both modes

### Automatic Fallback

The system automatically uses the best available method:
1. **Web MIDI detected** → Uses browser-based control (preferred)
2. **Web MIDI unavailable** → Falls back to Direct USB (if configured)
3. **Both available** → User can choose in settings

## Installation

### Web MIDI API (No Installation)
- ✅ Built into Chrome/Edge/Opera
- ✅ Works out of the box
- ✅ No dependencies

### Direct USB MIDI (Optional Backup)

#### Install python-rtmidi:

**Windows:**
```bash
pip install python-rtmidi
```

**macOS:**
```bash
brew install rtmidi
pip install python-rtmidi
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install libasound2-dev libjack-dev
pip install python-rtmidi
```

**Linux (Arch):**
```bash
sudo pacman -S rtmidi
pip install python-rtmidi
```

#### Enable in config.json:

```json
{
  "midi": {
    "enabled": true,
    "direct_usb": {
      "enabled": true,
      "auto_connect": true,
      "port_index": 0
    }
  }
}
```

#### Verify Installation:

```bash
python -c "import rtmidi; print('✅ python-rtmidi available')"
```

## Use Cases

### Scenario 1: Remote VJ (Web MIDI Recommended)
**Setup:** VJ operates from laptop, server runs on different machine/rack  
**MIDI Controller:** On VJ laptop  
**Mode:** Web MIDI API  
**Benefits:** Full remote control, no cables to server, works from anywhere on network

### Scenario 2: Server Console (Direct USB Recommended)
**Setup:** Server has keyboard/mouse/display, operated directly  
**MIDI Controller:** Plugged into server  
**Mode:** Direct USB  
**Benefits:** Zero latency, no network dependency, works without browser support

### Scenario 3: Hybrid Setup (Both Enabled)
**Setup:** Primary control via Web MIDI, backup Direct USB on server  
**MIDI Controllers:** Both laptop and server  
**Mode:** Both active  
**Benefits:** Flexibility - switch between remote and local control

### Scenario 4: Firefox/Safari Users (Direct USB Required)
**Setup:** Browser doesn't support Web MIDI API  
**MIDI Controller:** Plugged into server  
**Mode:** Direct USB (only option)  
**Benefits:** MIDI control still works despite browser limitations

## Performance Considerations

### Web MIDI:
- **Latency**: ~5-15ms (network + WebSocket)
- **Throughput**: 30-60 messages/sec recommended
- **Network**: Requires stable connection
- **CPU**: Minimal (browser handles MIDI)

### Direct USB:
- **Latency**: <1ms (hardware direct)
- **Throughput**: Unlimited (hardware dependent)
- **Network**: Independent
- **CPU**: Minimal (separate thread)

### Best Practices:
- **Throttle updates**: Limit to 30-60 parameter updates/sec
- **Queue messages**: Don't block on parameter updates
- **Use separate thread**: Direct USB should run in daemon thread
- **Graceful degradation**: Fall back to Direct USB if Web MIDI fails

## Future Enhancements

### Phase 4: Advanced Features (Optional)
- **MIDI Feedback**: Send parameter values back to controller (LED rings, motorized faders)
- **Preset switching**: Map MIDI program change to effect presets
- **Note velocity mapping**: Use velocity as parameter value
- **MIDI Clock sync**: Sync BPM to external MIDI clock
- **Multi-page mappings**: Bank switching for more than 127 parameters
- **Learning curves**: Different curve types (linear, S-curve, exponential)

## Testing Checklist

### Web MIDI:
- [ ] MIDI device detection and selection (browser)
- [ ] MIDI Learn workflow (click → move controller → map)
- [ ] Parameter updates via MIDI
- [ ] Multiple mappings (different CCs)
- [ ] Browser permission handling
- [ ] Device hot-swap (plug/unplug during operation)
- [ ] WebSocket reconnection (network interruption)
- [ ] Chrome/Edge/Opera compatibility

### Direct USB:
- [ ] MIDI port detection (python-rtmidi)
- [ ] Port connection/disconnection
- [ ] MIDI Learn workflow (same as Web MIDI)
- [ ] Parameter updates via MIDI
- [ ] Thread safety (separate MIDI thread)
- [ ] Auto-connect on startup
- [ ] Graceful error handling (no device connected)
- [ ] Windows/macOS/Linux compatibility

### Both Modes:
- [ ] Session state persistence (mappings survive restart)
- [ ] Mode switching (Web → Direct, Direct → Web)
- [ ] Concurrent operation (both active simultaneously)
- [ ] Mapping sharing (same mappings work for both modes)
- [ ] Status reporting (which mode active, which device connected)

## Security Considerations

- Web MIDI API requires **HTTPS** in production (localhost works with HTTP)
- User must **explicitly grant permission** for MIDI access
- No access to other system MIDI applications
- MIDI data only sent to your backend via WebSocket

## Browser Fallback

For Firefox/Safari users without Web MIDI support:

```javascript
if (!navigator.requestMIDIAccess) {
    showToast('MIDI not supported. Please use Chrome, Edge, or Opera.', 'warning');
}
```

## Example Configuration

```json
{
  "midi_mappings": {
    "cc:1": {
      "type": "cc",
      "number": 1,
      "path": "video.effect.0.param.brightness",
      "min": 0,
      "max": 100
    },
    "cc:2": {
      "type": "cc",
      "number": 2,
      "path": "video.effect.0.param.contrast",
      "min": -50,
      "max": 50
    },
    "note:60": {
      "type": "note",
      "number": 60,
      "path": "video.play_pause",
      "min": 0,
      "max": 1
    }
  }
}
```

## Documentation References

- [Web MIDI API Specification](https://www.w3.org/TR/webmidi/)
- [MDN Web MIDI API](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API)
- [Can I Use Web MIDI](https://caniuse.com/midi)

## Summary

This dual-mode implementation provides:

### Web MIDI API (Primary):
- ✅ **Zero installation** MIDI control via browser
- ✅ **Remote control** capability (VJ on laptop, server in rack)
- ✅ **MIDI Learn** for easy mapping
- ✅ **Session persistence** of mappings
- ✅ **Real-time updates** via existing WebSocket
- ✅ **Professional workflow** for VJ performances

### Direct USB MIDI (Backup):
- ✅ **Ultra-low latency** (<1ms hardware direct)
- ✅ **Browser-independent** (works in Firefox, Safari)
- ✅ **Network-independent** (no WebSocket required)
- ✅ **Reliable** hardware connection
- ✅ **Server console** control option
- ✅ **Auto-connect** on startup

### Combined Benefits:
- ✅ **Best of both worlds** - choose mode per use case
- ✅ **Automatic fallback** - Direct USB when Web MIDI unavailable
- ✅ **Unified mappings** - same parameter mappings work for both
- ✅ **Flexible deployment** - remote or local control
- ✅ **Maximum compatibility** - supports all browsers and setups

**Total implementation time:** ~12-16 hours for complete dual-mode MIDI system.

**Dependencies:**
- Web MIDI: None (built into browser)
- Direct USB: `python-rtmidi` (optional, 5MB install)
