# MIDI Profiles & Global Mapping

## Overview

This document details two advanced MIDI features:

1. **MIDI Profiles** - Reusable mapping configurations stored separately from sessions
2. **Global Mapping** - Pattern-based parameter mapping (control multiple parameters with one fader)

## 1. MIDI Profile System

### Architecture

```
config/
└── midi_profiles.json          # All MIDI profiles stored here
    ├── active_profile: "Studio Setup"
    └── profiles: [
        {
          name: "Studio Setup",
          description: "Main studio controller",
          mappings: {...}
        },
        {
          name: "Live Show",
          description: "Backup controller for live",
          mappings: {...}
        }
    ]
```

**Separated from `session_state.json`:**
- ✅ MIDI controller setup is hardware-specific, not content-specific
- ✅ Use same MIDI mappings across different video projects
- ✅ Share profiles between machines (copy file)
- ✅ Version control friendly (separate file)
- ✅ Switch profiles based on controller (studio vs live vs backup)

### File Format: `config/midi_profiles.json`

```json
{
  "active_profile": "Studio Setup",
  "profiles": [
    {
      "name": "Studio Setup",
      "description": "Main BCF2000 controller",
      "created": "2026-01-20T10:30:00",
      "modified": "2026-01-20T15:45:00",
      "mappings": {
        "cc:1": {
          "type": "cc",
          "number": 1,
          "path": "*.brightness",
          "min": 0,
          "max": 100,
          "mode": "global",
          "name": "Master Brightness"
        },
        "cc:14": {
          "type": "cc",
          "number": 14,
          "path": "video.effect.0.blur",
          "min": 0,
          "max": 50,
          "mode": "local",
          "name": "Blur Effect"
        }
      }
    },
    {
      "name": "Live Show",
      "description": "Backup Korg controller",
      "created": "2026-01-18T09:00:00",
      "modified": "2026-01-19T22:30:00",
      "mappings": {
        "cc:7": {
          "type": "cc",
          "number": 7,
          "path": "video.global.speed",
          "min": 0.5,
          "max": 2.0,
          "mode": "local",
          "name": "Playback Speed"
        }
      }
    }
  ]
}
```

### Profile Management API

#### List All Profiles
```python
@app.route('/api/midi/profiles', methods=['GET'])
def get_midi_profiles():
    """Get list of all MIDI profiles"""
    try:
        if not midi_manager:
            return jsonify({'success': False, 'error': 'MIDI manager not available'})
        
        profiles = midi_manager.get_profile_list()
        
        return jsonify({
            'success': True,
            'profiles': profiles,
            'active': midi_manager.active_profile_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### Create Profile
```python
@app.route('/api/midi/profiles', methods=['POST'])
def create_midi_profile():
    """Create new MIDI profile"""
    try:
        data = request.json
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({'success': False, 'error': 'Name required'})
        
        if midi_manager.profiles.get(name):
            return jsonify({'success': False, 'error': 'Profile already exists'})
        
        profile = midi_manager.create_profile(name, description)
        
        return jsonify({
            'success': True,
            'profile': {
                'name': profile.name,
                'description': profile.description
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### Switch Profile
```python
@app.route('/api/midi/profiles/switch', methods=['POST'])
def switch_midi_profile():
    """Switch to different MIDI profile"""
    try:
        data = request.json
        name = data.get('name')
        
        if not name:
            return jsonify({'success': False, 'error': 'Name required'})
        
        success = midi_manager.switch_profile(name)
        
        if success:
            # Broadcast to all clients
            socketio.emit('midi_profile_changed', {'profile': name})
            
            return jsonify({'success': True, 'active_profile': name})
        else:
            return jsonify({'success': False, 'error': 'Profile not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### Delete Profile
```python
@app.route('/api/midi/profiles/<name>', methods=['DELETE'])
def delete_midi_profile(name):
    """Delete MIDI profile"""
    try:
        success = midi_manager.delete_profile(name)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Cannot delete Default or profile not found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### Duplicate Profile
```python
@app.route('/api/midi/profiles/duplicate', methods=['POST'])
def duplicate_midi_profile():
    """Duplicate existing profile"""
    try:
        data = request.json
        source = data.get('source')
        new_name = data.get('name')
        
        if not source or not new_name:
            return jsonify({'success': False, 'error': 'Source and name required'})
        
        new_profile = midi_manager.duplicate_profile(source, new_name)
        
        if new_profile:
            return jsonify({
                'success': True,
                'profile': {
                    'name': new_profile.name,
                    'description': new_profile.description
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Duplication failed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

#### Export/Import Profile
```python
@app.route('/api/midi/profiles/<name>/export', methods=['GET'])
def export_midi_profile(name):
    """Export profile as JSON file"""
    try:
        profile = midi_manager.profiles.get(name)
        if not profile:
            return jsonify({'success': False, 'error': 'Profile not found'})
        
        # Return as downloadable JSON
        from flask import make_response
        response = make_response(json.dumps(profile.to_dict(), indent=2))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename={name}.midi_profile.json'
        return response
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/midi/profiles/import', methods=['POST'])
def import_midi_profile():
    """Import profile from JSON file"""
    try:
        data = request.json
        
        profile = MIDIProfile.from_dict(data)
        
        # Check if name already exists
        if profile.name in midi_manager.profiles:
            profile.name = f"{profile.name} (imported)"
        
        midi_manager.profiles[profile.name] = profile
        midi_manager.save_profiles()
        
        return jsonify({
            'success': True,
            'profile': {
                'name': profile.name,
                'description': profile.description
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
```

### Frontend Profile Manager UI

```html
<!-- Add to player.html -->
<div class="modal fade" id="midiProfilesModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content bg-dark text-light">
            <div class="modal-header border-secondary">
                <h5 class="modal-title">🎹 MIDI Profiles</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Active Profile -->
                <div class="mb-3">
                    <label class="form-label">Active Profile</label>
                    <select class="form-select bg-dark text-light border-secondary" 
                            id="activeProfileSelect" onchange="switchMidiProfile()">
                    </select>
                </div>
                
                <!-- Profile List -->
                <div class="mb-3">
                    <label class="form-label">Available Profiles</label>
                    <div id="profileList" class="list-group">
                        <!-- Profiles loaded here -->
                    </div>
                </div>
                
                <!-- Actions -->
                <div class="d-flex gap-2">
                    <button class="btn btn-success" onclick="createNewProfile()">
                        ➕ New Profile
                    </button>
                    <button class="btn btn-info" onclick="duplicateActiveProfile()">
                        📋 Duplicate
                    </button>
                    <button class="btn btn-primary" onclick="exportActiveProfile()">
                        💾 Export
                    </button>
                    <button class="btn btn-warning" onclick="importProfile()">
                        📂 Import
                    </button>
                </div>
            </div>
        </div>
    </div>
</div>
```

```javascript
// Add to player.js

class MIDIProfileManager {
    constructor() {
        this.profiles = [];
        this.activeProfile = null;
    }
    
    async loadProfiles() {
        const response = await fetch('/api/midi/profiles');
        const data = await response.json();
        
        if (data.success) {
            this.profiles = data.profiles;
            this.activeProfile = data.active;
            this.updateUI();
        }
    }
    
    async switchProfile(name) {
        const response = await fetch('/api/midi/profiles/switch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name})
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`Switched to profile: ${name}`, 'success');
            this.loadProfiles();
        }
    }
    
    async createProfile(name, description) {
        const response = await fetch('/api/midi/profiles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, description})
        });
        
        const data = await response.json();
        if (data.success) {
            showToast('Profile created', 'success');
            this.loadProfiles();
        }
        return data.success;
    }
    
    async deleteProfile(name) {
        if (!confirm(`Delete profile "${name}"?`)) return;
        
        const response = await fetch(`/api/midi/profiles/${name}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        if (data.success) {
            showToast('Profile deleted', 'success');
            this.loadProfiles();
        }
    }
    
    async duplicateProfile(sourceName) {
        const newName = prompt(`Enter name for duplicated profile:`, `${sourceName} Copy`);
        if (!newName) return;
        
        const response = await fetch('/api/midi/profiles/duplicate', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({source: sourceName, name: newName})
        });
        
        const data = await response.json();
        if (data.success) {
            showToast('Profile duplicated', 'success');
            this.loadProfiles();
        }
    }
    
    async exportProfile(name) {
        window.open(`/api/midi/profiles/${name}/export`, '_blank');
    }
    
    async importProfile(fileInput) {
        const file = fileInput.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        reader.onload = async (e) => {
            try {
                const profileData = JSON.parse(e.target.result);
                
                const response = await fetch('/api/midi/profiles/import', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(profileData)
                });
                
                const data = await response.json();
                if (data.success) {
                    showToast('Profile imported', 'success');
                    this.loadProfiles();
                }
            } catch (err) {
                showToast('Import failed: ' + err.message, 'error');
            }
        };
        reader.readAsText(file);
    }
    
    updateUI() {
        // Update profile select dropdown
        const select = document.getElementById('activeProfileSelect');
        select.innerHTML = '';
        
        this.profiles.forEach(profile => {
            const option = document.createElement('option');
            option.value = profile.name;
            option.textContent = `${profile.name} (${profile.mapping_count} mappings)`;
            option.selected = profile.is_active;
            select.appendChild(option);
        });
        
        // Update profile list
        const list = document.getElementById('profileList');
        list.innerHTML = '';
        
        this.profiles.forEach(profile => {
            const item = document.createElement('div');
            item.className = 'list-group-item bg-secondary text-light d-flex align-items-center';
            
            const badge = profile.is_active ? 
                '<span class="badge bg-success me-2">ACTIVE</span>' : '';
            
            item.innerHTML = `
                ${badge}
                <div class="flex-grow-1">
                    <strong>${profile.name}</strong>
                    <br><small class="text-muted">${profile.description}</small>
                    <br><small>${profile.mapping_count} mappings</small>
                </div>
                <div class="btn-group">
                    <button class="btn btn-sm btn-primary" 
                            onclick="midiProfileManager.exportProfile('${profile.name}')">
                        💾
                    </button>
                    ${profile.name !== 'Default' ? `
                        <button class="btn btn-sm btn-danger" 
                                onclick="midiProfileManager.deleteProfile('${profile.name}')">
                            🗑️
                        </button>
                    ` : ''}
                </div>
            `;
            
            list.appendChild(item);
        });
    }
}

// Global instance
window.midiProfileManager = new MIDIProfileManager();
```

## 2. Global vs Local Parameter Mapping

### Concept

**Local Mapping** (Traditional):
- One MIDI control → One specific parameter
- Example: `CC#14 → video.effect.0.brightness`

**Global Mapping** (Pattern-based):
- One MIDI control → Multiple parameters matching pattern
- Example: `CC#14 → *.brightness` (all brightness parameters)

### Pattern Syntax

| Pattern | Matches | Example Parameters |
|---------|---------|-------------------|
| `*.brightness` | All brightness parameters | `video.effect.0.brightness`<br>`video.effect.1.brightness`<br>`artnet.effect.0.brightness` |
| `video.effect.*.blur` | All blur parameters in video effects | `video.effect.0.blur`<br>`video.effect.1.blur`<br>`video.effect.2.blur` |
| `video.layer.*.opacity` | All layer opacities | `video.layer.0.opacity`<br>`video.layer.1.opacity`<br>`video.layer.2.opacity` |
| `*.effect.*.intensity` | All effect intensities everywhere | `video.effect.0.intensity`<br>`video.layer.0.effect.0.intensity`<br>`artnet.effect.1.intensity` |
| `video.effect.0.brightness` | Specific parameter only (local) | `video.effect.0.brightness` |

### Use Cases

#### Master Brightness Control
```json
{
  "cc:1": {
    "type": "cc",
    "number": 1,
    "path": "*.brightness",
    "mode": "global",
    "name": "Master Brightness",
    "min": 0,
    "max": 100
  }
}
```
**Result:** One fader controls brightness of ALL effects (video + art-net + layers)

#### Layer Opacity Master
```json
{
  "cc:7": {
    "type": "cc",
    "number": 7,
    "path": "video.layer.*.opacity",
    "mode": "global",
    "name": "All Layers Opacity",
    "min": 0,
    "max": 100
  }
}
```
**Result:** Fade all layers in/out together

#### Effect Type Control
```json
{
  "cc:14": {
    "type": "cc",
    "number": 14,
    "path": "*.effect.*.blur",
    "mode": "global",
    "name": "All Blur Effects",
    "min": 0,
    "max": 50
  }
}
```
**Result:** Control all blur effects with one knob

### MIDI Learn with Global Mapping

```javascript
async function startMIDILearn(parameterPath, parameterName) {
    // Show modal with mode selection
    const mode = await showMappingModeDialog(parameterName);
    // Returns: 'local' or 'global'
    
    let finalPath = parameterPath;
    
    if (mode === 'global') {
        // Convert specific path to pattern
        // video.effect.0.brightness → *.brightness
        // OR video.effect.0.brightness → video.effect.*.brightness
        
        const pattern = await showPatternDialog(parameterPath);
        finalPath = pattern;
    }
    
    // Start MIDI Learn
    midiLearnManager.startLearn(finalPath, parameterName, mode);
}

function showPatternDialog(parameterPath) {
    // Show dialog with pattern options
    const parts = parameterPath.split('.');
    const paramName = parts[parts.length - 1];
    
    return new Promise((resolve) => {
        const modal = createModal('Select Global Pattern', `
            <div>
                <label>Pattern for "${paramName}":</label>
                <select id="patternSelect" class="form-select mb-2">
                    <option value="*.${paramName}">
                        All ${paramName} (everywhere)
                    </option>
                    <option value="video.effect.*.${paramName}">
                        All ${paramName} in video effects
                    </option>
                    <option value="video.layer.*.${paramName}">
                        All ${paramName} in layers
                    </option>
                    <option value="*.effect.*.${paramName}">
                        All ${paramName} in all effects
                    </option>
                    <option value="${parameterPath}">
                        Custom: ${parameterPath}
                    </option>
                </select>
                <button class="btn btn-primary" onclick="confirmPattern()">Confirm</button>
            </div>
        `);
        
        window.confirmPattern = () => {
            const pattern = document.getElementById('patternSelect').value;
            modal.hide();
            resolve(pattern);
        };
        
        modal.show();
    });
}
```

### Backend: Pattern Matching Logic

Already implemented in updated `MIDIMapping` class:

```python
def matches_path(self, path: str) -> bool:
    """Check if parameter path matches this mapping (supports wildcards)"""
    if self.mapping_mode == 'local':
        return path == self.parameter_path
    
    # Global pattern matching
    pattern = self.parameter_path
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
        param = parameter_registry.get_parameter(self.parameter_path)
        return [self.parameter_path] if param else []
    
    # Global: Find all matching paths
    matching = []
    for path in parameter_registry.parameters.keys():
        if self.matches_path(path):
            matching.append(path)
    
    return matching
```

### Visual Feedback for Global Mappings

```javascript
function displayMappings(mappings) {
    const container = document.getElementById('midiMappingList');
    container.innerHTML = '';
    
    mappings.forEach(mapping => {
        const row = document.createElement('div');
        row.className = 'mapping-row';
        
        const modeIcon = mapping.is_global ? '🌐' : '📍';
        const modeClass = mapping.is_global ? 'text-warning' : 'text-info';
        
        let pathDisplay = mapping.path;
        if (mapping.is_global && mapping.matching_count) {
            pathDisplay += ` <span class="badge bg-success">${mapping.matching_count} params</span>`;
        }
        
        row.innerHTML = `
            <span class="${modeClass}" title="${mapping.mode}">${modeIcon}</span>
            <strong class="me-2">${mapping.midi}</strong>
            <span class="font-monospace flex-grow-1">${pathDisplay}</span>
            <span class="me-2">${mapping.name}</span>
            <button onclick="editMapping('${mapping.midi}')" class="btn btn-sm btn-primary">✏️</button>
            <button onclick="removeMapping('${mapping.midi}')" class="btn btn-sm btn-danger">🗑️</button>
        `;
        
        container.appendChild(row);
    });
}
```

## Summary

### MIDI Profiles
✅ Stored in `config/midi_profiles.json` (separate from sessions)  
✅ Multiple profiles (Studio, Live, Backup)  
✅ Switch profiles on-the-fly  
✅ Export/Import for sharing  
✅ Duplicate profiles for quick setup  

### Global Mapping
✅ Pattern-based: `*.brightness`, `video.layer.*.opacity`  
✅ Control multiple parameters with one fader  
✅ Master controls (brightness, opacity, intensity)  
✅ Type-specific controls (all blur, all color)  
✅ Visual feedback showing match count  

**Implementation Time:**
- Profile system: +2h
- Global mapping: +2h
- Total: +4h on top of base MIDI implementation
