# MIDI Implementation Guide

## Overview

MIDI in Flux is split into **two independent subsystems** that serve different purposes:

| Subsystem | Purpose | Approach |
|-----------|---------|----------|
| **MIDI Parameter Control** | Map MIDI knobs/faders to effect/layer params | Web MIDI API (browser-based) |
| **MIDI Clock** | Sync playback tempo with external devices/DAWs | Server-side Python (mido + rtmidi) |

These subsystems share REST endpoints under `/api/midi/` and use the existing **SocketIO** instance for real-time updates.

---

## Architecture

```
MIDI Controller (USB)
    │
    ├──────────────────────────────────────────────────────────┐
    │                                                          │
    │ (for parameter control)          (for clock sync)        │
    ▼                                  ▼                       │
Browser                         Server (Python)                │
Web MIDI API                    mido + python-rtmidi           │
    │                                  │                       │
    │ WebSocket (SocketIO)             │ REST + SocketIO       │
    ▼                                  ▼                       │
┌──────────────────────────────────────────────────────────┐   │
│              Flask Backend (src/modules/api_midi.py)     │   │
│                                                          │   │
│  /api/midi/mappings       (CRUD - param control)         │   │
│  /api/midi/profiles       (CRUD - profile management)    │   │
│  /api/midi/devices        (clock: list MIDI devices)     │   │
│  /api/midi/clock/connect  (clock: connect input/output)  │   │
│  /api/midi/clock/status   (clock: current BPM, beat)     │   │
│  SocketIO: midi_clock_update  (20 Hz clock broadcast)    │   │
└──────────────────────────────────────────────────────────┘   │
```

---

## Part 1: MIDI Parameter Control

### 1.1 Approach: Visual MIDI Frames (not Parameter Registry)

**Decision:** Parameter control uses the **Visual Frame** approach — not a backend Parameter Registry.

Why Visual Frames win:

| | Parameter Registry | Visual Frames |
|---|---|---|
| Lines of code | ~1550 | ~150 |
| Sync issues | Backend ↔ Frontend | Single source (DOM) |
| Adding a param | Update 5+ places | Wrap control in a div |
| Dynamic updates | Rescan on changes | Auto-discovered via DOM |

**The key insight:** If a parameter is visible as a UI control, wrap it in a `.midi-param-frame` div. The DOM is the parameter registry.

### 1.2 How It Works

1. All controllable UI elements are wrapped in `.midi-param-frame` divs with `data-param-*` attributes.
2. A toggle button activates **MIDI Learn Mode** (Ctrl+M).
3. In MIDI Learn Mode, frames are highlighted — click one to arm it.
4. Move a MIDI CC on the controller → mapping is saved.
5. The backend stores mappings per profile in `config/midi_profiles.json`.
6. On MIDI input, the backend broadcasts via SocketIO and the frontend updates the matching control.

### 1.3 Dependencies

No additional packages needed — uses the browser built-in Web MIDI API.

```
Supported browsers: Chrome, Edge, Opera
Not supported: Firefox, Safari (no Web MIDI API)
```

### 1.4 HTML: Wrapping Parameters in MIDI Frames

```html
<!-- Before: Plain slider -->
<div class="mb-3">
    <label>Brightness</label>
    <input type="range" id="brightness" min="0" max="100" value="75">
</div>

<!-- After: MIDI-mappable frame -->
<div class="midi-param-frame"
     data-param-path="video.effect.0.brightness"
     data-param-name="Brightness"
     data-param-min="0"
     data-param-max="100">

    <div class="midi-param-control">
        <label>Brightness</label>
        <input type="range" id="brightness" min="0" max="100" value="75">
    </div>

    <div class="midi-param-indicator" style="display: none;">
        <span class="midi-code">Click to map</span>
        <button class="midi-remove-btn" style="display: none;">x</button>
    </div>
</div>
```

#### Parameter Path Naming Convention

Format: `{player}.{category}.{index}.{parameter}`

| Path | Description |
|------|-------------|
| `video.global.speed` | Video playback speed |
| `video.global.opacity` | Video master opacity |
| `video.effect.0.brightness` | First effect brightness |
| `video.effect.1.threshold` | Second effect threshold |
| `video.layer.0.opacity` | Layer 0 opacity |
| `video.layer.0.effect.0.blur` | Layer 0, effect 0, blur param |
| `video.generator.speed` | Generator speed |
| `artnet.effect.0.intensity` | Art-Net effect intensity |
| `sequencer.bpm` | Sequencer BPM |
| `audio.gain` | Audio analyzer gain |

### 1.5 CSS: MIDI Learn Mode Styles

**File:** `frontend/css/midi-display.css`

```css
.midi-param-frame {
    position: relative;
    padding: 8px;
    border-radius: 6px;
    border: 2px solid transparent;
    transition: all 0.3s ease;
}

body.midi-learn-mode .midi-param-frame {
    border: 2px solid rgba(255, 193, 7, 0.3);
    background: rgba(255, 193, 7, 0.05);
    cursor: pointer;
}

body.midi-learn-mode .midi-param-frame:hover {
    border-color: rgba(255, 193, 7, 0.6);
    background: rgba(255, 193, 7, 0.1);
}

body.midi-learn-mode .midi-param-frame.has-mapping {
    border-color: rgba(40, 167, 69, 0.5);
    background: rgba(40, 167, 69, 0.05);
}

.midi-param-frame.learning {
    border-color: #ffc107;
    background: rgba(255, 193, 7, 0.2);
    animation: framePulse 1s infinite;
}

@keyframes framePulse {
    0%, 100% { border-color: rgba(255, 193, 7, 0.8); box-shadow: 0 0 10px rgba(255, 193, 7, 0.3); }
    50%       { border-color: rgba(255, 193, 7, 1);   box-shadow: 0 0 20px rgba(255, 193, 7, 0.6); }
}

.midi-param-indicator {
    display: none;
    font-size: 0.75rem;
    margin-top: 4px;
    color: #ffc107;
}

body.midi-learn-mode .midi-param-indicator {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.midi-param-frame.has-mapping .midi-param-indicator { color: #28a745; }

.midi-code { font-family: "Courier New", monospace; font-weight: bold; }

.midi-remove-btn {
    background: #dc3545;
    border: none;
    color: white;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    font-size: 14px;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    display: none;
}

.midi-param-frame.has-mapping .midi-remove-btn { display: block; }

#midiLearnToggle { transition: all 0.3s ease; }

#midiLearnToggle:not(.active) { background: transparent; border-color: #ffc107; color: #ffc107; }

#midiLearnToggle.active {
    background: #ffc107;
    border-color: #ffc107;
    color: #000;
    box-shadow: 0 0 20px rgba(255, 193, 7, 0.5);
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(255, 193, 7, 0.5); }
    50%       { box-shadow: 0 0 30px rgba(255, 193, 7, 0.8); }
}

/* Beat indicator dots (MIDI clock display) */
.beat-dot {
    width: 14px; height: 14px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    transition: all 0.1s ease;
}

.beat-dot.beat-active {
    background: #2196f3;
    box-shadow: 0 0 12px rgba(33, 150, 243, 0.8);
    transform: scale(1.2);
}
```

### 1.6 JavaScript: VisualMIDILearnManager

**File:** `frontend/js/midi-learn.js`

```javascript
class VisualMIDILearnManager {
    constructor() {
        this.learnModeActive = false;
        this.activeLearnFrame = null;
        this.frames = new Map(); // param_path -> frame element
        this.midiAccess = null;
        this._init();
    }

    async _init() {
        this.scanParameterFrames();
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'm') { e.preventDefault(); this.toggleLearnMode(); }
        });
        socket.on('parameter_structure_changed', () => this.scanParameterFrames());

        if (navigator.requestMIDIAccess) {
            try {
                this.midiAccess = await navigator.requestMIDIAccess();
                this._listenMIDIInputs();
                this.midiAccess.onstatechange = () => this._listenMIDIInputs();
            } catch (e) {
                console.error('Web MIDI access denied:', e);
            }
        } else {
            console.warn('Web MIDI API not supported (use Chrome/Edge).');
        }
    }

    _listenMIDIInputs() {
        for (const input of this.midiAccess.inputs.values()) {
            input.onmidimessage = (e) => this._onMIDIMessage(e);
        }
    }

    _onMIDIMessage(event) {
        const [status, number, value] = event.data;
        if ((status & 0xF0) !== 0xB0) return; // Only CC messages
        const type = 'cc';

        if (this.learnModeActive && this.activeLearnFrame) {
            this._completeLearning(this.activeLearnFrame, type, number);
        } else {
            socket.emit('midi_input', { type, number, value });
        }
    }

    scanParameterFrames() {
        const frames = document.querySelectorAll('.midi-param-frame');
        this.frames.clear();
        frames.forEach(frame => {
            const path = frame.dataset.paramPath;
            this.frames.set(path, frame);
            frame.addEventListener('click', () => {
                if (this.learnModeActive) this.startLearnForFrame(frame);
            });
            const removeBtn = frame.querySelector('.midi-remove-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this._removeMappingForFrame(frame);
                });
            }
        });
        console.log('MIDI: registered ' + this.frames.size + ' parameter frames');
    }

    toggleLearnMode() {
        this.learnModeActive = !this.learnModeActive;
        document.getElementById('midiLearnToggle')?.classList.toggle('active', this.learnModeActive);
        document.body.classList.toggle('midi-learn-mode', this.learnModeActive);

        if (this.learnModeActive) {
            this._refreshFrameStates();
            showToast('MIDI Learn Mode Active - Click a parameter to map', 'info');
        } else {
            if (this.activeLearnFrame) this._cancelLearn();
            showToast('MIDI Learn Mode Off', 'info');
        }
        this._updateMappingCount();
    }

    async startLearnForFrame(frame) {
        if (this.activeLearnFrame) this._cancelLearn();
        const path = frame.dataset.paramPath;
        const existing = await this._getMappingForPath(path);
        if (existing && !confirm('Already mapped to ' + existing.midi + '. Remap?')) return;

        this.activeLearnFrame = frame;
        frame.classList.add('learning');
        frame.querySelector('.midi-code').textContent = 'Move MIDI control...';
    }

    async _completeLearning(frame, type, number) {
        const path = frame.dataset.paramPath;
        const name = frame.dataset.paramName;
        const min  = parseFloat(frame.dataset.paramMin ?? 0);
        const max  = parseFloat(frame.dataset.paramMax ?? 100);

        frame.classList.remove('learning');
        this.activeLearnFrame = null;

        const isGlobal = confirm('"' + name + '" — map as GLOBAL (all matching params)?\nOK=Global  Cancel=Local');
        const mode = isGlobal ? 'global' : 'local';

        let finalPath = path;
        if (mode === 'global') {
            finalPath = await this._showPatternDialog(path);
            if (!finalPath) return;
        }

        const res = await fetch('/api/midi/mappings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                midi_type: type, midi_number: number,
                parameter_path: finalPath, min_value: min,
                max_value: max, mapping_mode: mode, name
            })
        });
        const data = await res.json();

        if (data.success) {
            this._setFrameMapping(frame, type.toUpperCase() + '#' + number, mode);
            showToast('Mapped ' + type.toUpperCase() + '#' + number + ' to ' + name, 'success');
        } else {
            showToast('Mapping failed: ' + data.error, 'error');
        }
        this._updateMappingCount();
    }

    _cancelLearn() {
        if (!this.activeLearnFrame) return;
        this.activeLearnFrame.classList.remove('learning');
        this.activeLearnFrame.querySelector('.midi-code').textContent = 'Click to map';
        this.activeLearnFrame = null;
    }

    _setFrameMapping(frame, midiCode, mode) {
        frame.classList.add('has-mapping');
        const icon = mode === 'global' ? '[G]' : '[L]';
        frame.querySelector('.midi-code').textContent = icon + ' ' + midiCode;
    }

    async _removeMappingForFrame(frame) {
        const mapping = await this._getMappingForPath(frame.dataset.paramPath);
        if (!mapping || !confirm('Remove ' + mapping.midi + ' from ' + frame.dataset.paramName + '?')) return;
        const [type, number] = mapping.midi.split(':');
        const res = await fetch('/api/midi/mappings/' + type + '/' + number, { method: 'DELETE' });
        if ((await res.json()).success) {
            frame.classList.remove('has-mapping');
            frame.querySelector('.midi-code').textContent = 'Click to map';
            this._updateMappingCount();
        }
    }

    async _refreshFrameStates() {
        const data = await (await fetch('/api/midi/mappings')).json();
        if (!data.success) return;
        this.frames.forEach(f => f.classList.remove('has-mapping'));
        data.mappings.forEach(m => {
            const frame = this.frames.get(m.path);
            if (frame) this._setFrameMapping(frame, m.type.toUpperCase() + '#' + m.number, m.mode);
        });
    }

    async _getMappingForPath(path) {
        const data = await (await fetch('/api/midi/mappings')).json();
        return data.success ? data.mappings.find(m => m.path === path) : null;
    }

    async _updateMappingCount() {
        const data = await (await fetch('/api/midi/mappings')).json();
        const badge = document.getElementById('midiMappingCount');
        if (!badge) return;
        const count = data.success ? data.mappings.length : 0;
        badge.textContent = count + ' mappings';
        badge.style.display = count > 0 ? 'inline-block' : 'none';
    }

    _showPatternDialog(paramPath) {
        const parts = paramPath.split('.');
        const paramName = parts[parts.length - 1];
        const options = [
            '*.' + paramName,
            'video.effect.*.' + paramName,
            'video.layer.*.' + paramName,
            '*.effect.*.' + paramName,
            paramPath
        ];
        const choice = prompt(
            'Select global pattern:\n' +
            options.map((o, i) => (i + 1) + '. ' + o).join('\n') +
            '\n\nEnter number:', '1'
        );
        const idx = parseInt(choice) - 1;
        return Promise.resolve(options[idx] ?? null);
    }
}

// Apply MIDI values from backend broadcast
socket.on('midi_apply', ({ type, number, value, path, mode, min, max }) => {
    window.midiLearnManager?.frames.forEach((frame, framePath) => {
        if (matchesMidiPattern(framePath, path)) {
            const fMin = parseFloat(frame.dataset.paramMin ?? min ?? 0);
            const fMax = parseFloat(frame.dataset.paramMax ?? max ?? 100);
            const scaled = fMin + (value / 127) * (fMax - fMin);
            const input = frame.querySelector('input, select');
            if (input) { input.value = scaled; input.dispatchEvent(new Event('input')); }
        }
    });
});

function matchesMidiPattern(path, pattern) {
    const pp = pattern.split('.');
    const lp = path.split('.');
    if (pp.length !== lp.length) return false;
    return pp.every((p, i) => p === '*' || p === lp[i]);
}

window.midiLearnManager = new VisualMIDILearnManager();
```

### 1.7 MIDI Learn Toggle (Playlist Bar)

Add to `player.html`:

```html
<button id="midiLearnToggle"
        class="btn btn-outline-warning"
        onclick="midiLearnManager.toggleLearnMode()"
        title="MIDI Learn Mode (Ctrl+M)">
    MIDI
</button>
<span class="badge bg-info" id="midiMappingCount" style="display: none;">0 mappings</span>
```

---

## Part 2: MIDI Profiles

### 2.1 Storage

MIDI profiles are stored separately from sessions because they are hardware-specific.

**File:** `config/midi_profiles.json`

```json
{
  "active_profile": "Studio Setup",
  "profiles": [
    {
      "name": "Studio Setup",
      "description": "Main BCF2000 controller",
      "mappings": {
        "cc:1":  { "type": "cc", "number": 1,  "path": "*.brightness",         "min": 0, "max": 100, "mode": "global", "name": "Master Brightness" },
        "cc:14": { "type": "cc", "number": 14, "path": "video.effect.0.blur",  "min": 0, "max": 50,  "mode": "local",  "name": "Blur Effect" }
      }
    },
    {
      "name": "Live Show",
      "description": "Backup Korg controller",
      "mappings": {}
    }
  ]
}
```

Why separate from `session_state.json`:
- Same hardware setup is reused across different projects
- Shareable between machines (copy one file)
- Switch profiles on-the-fly without affecting session data

### 2.2 Profile REST API

```
GET    /api/midi/profiles              list all
POST   /api/midi/profiles              create
POST   /api/midi/profiles/switch       activate
POST   /api/midi/profiles/duplicate    duplicate
GET    /api/midi/profiles/<name>/export  download as JSON
POST   /api/midi/profiles/import       upload JSON
DELETE /api/midi/profiles/<name>       delete
```

### 2.3 Profile Manager UI (JavaScript)

```javascript
class MIDIProfileManager {
    async loadProfiles() {
        const data = await (await fetch('/api/midi/profiles')).json();
        if (data.success) { this.profiles = data.profiles; this._updateUI(); }
    }

    async switchProfile(name) {
        await fetch('/api/midi/profiles/switch', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name })
        });
        showToast('Switched to: ' + name, 'success');
        this.loadProfiles();
    }

    async createProfile(name, description) {
        await fetch('/api/midi/profiles', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, description })
        });
        this.loadProfiles();
    }

    async duplicateProfile(source) {
        const newName = prompt('Name for duplicated profile:', source + ' Copy');
        if (!newName) return;
        await fetch('/api/midi/profiles/duplicate', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ source, name: newName })
        });
        this.loadProfiles();
    }

    exportProfile(name) { window.open('/api/midi/profiles/' + name + '/export', '_blank'); }

    async importProfile(file) {
        const profileData = JSON.parse(await file.text());
        await fetch('/api/midi/profiles/import', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(profileData)
        });
        this.loadProfiles();
    }
}

window.midiProfileManager = new MIDIProfileManager();
```

---

## Part 3: Global vs Local Mapping

### 3.1 Concept

| Mode | Example | Effect |
|------|---------|--------|
| **Local** | `CC#14 -> video.effect.0.brightness` | One fader, one parameter |
| **Global** | `CC#1 -> *.brightness` | One fader, all brightness params |

### 3.2 Pattern Syntax

| Pattern | Matches |
|---------|---------|
| `*.brightness` | All brightness parameters anywhere |
| `video.effect.*.blur` | All blur params in video effects |
| `video.layer.*.opacity` | All layer opacities |
| `*.effect.*.intensity` | All effect intensities everywhere |

### 3.3 Backend Pattern Matching

```python
def matches_pattern(path: str, pattern: str) -> bool:
    pp = pattern.split('.')
    lp = path.split('.')
    if len(pp) != len(lp):
        return False
    return all(p == '*' or p == l for p, l in zip(pp, lp))
```

### 3.4 Common Global Mapping Examples

```json
{
  "cc:1":  { "path": "*.brightness",         "mode": "global", "name": "Master Brightness" },
  "cc:7":  { "path": "video.layer.*.opacity", "mode": "global", "name": "All Layers Opacity" },
  "cc:14": { "path": "*.effect.*.blur",       "mode": "global", "name": "All Blur Effects" }
}
```

---

## Part 4: Backend — `src/modules/api_midi.py`

### 4.1 Mappings + Profiles CRUD

```python
"""
MIDI API — Mappings, Profiles, Clock
Uses existing SocketIO instance (no separate WebSocket library).
"""
from flask import Blueprint, jsonify, request
import json, copy, logging
from pathlib import Path

logger = logging.getLogger(__name__)
midi_bp = Blueprint('midi', __name__)

PROFILES_FILE = Path('config/midi_profiles.json')

def _load_profiles():
    if PROFILES_FILE.exists():
        return json.loads(PROFILES_FILE.read_text())
    return {'active_profile': 'Default', 'profiles': [{'name': 'Default', 'description': '', 'mappings': {}}]}

def _save_profiles(data):
    PROFILES_FILE.parent.mkdir(exist_ok=True)
    PROFILES_FILE.write_text(json.dumps(data, indent=2))

def _active_mappings():
    data = _load_profiles()
    active = data.get('active_profile', 'Default')
    for p in data.get('profiles', []):
        if p['name'] == active:
            return p.get('mappings', {})
    return {}

def _save_active_mappings(mappings):
    data = _load_profiles()
    active = data.get('active_profile', 'Default')
    for p in data.get('profiles', []):
        if p['name'] == active:
            p['mappings'] = mappings
    _save_profiles(data)

# Mappings

@midi_bp.route('/api/midi/mappings', methods=['GET'])
def get_mappings():
    mappings = _active_mappings()
    result = [{'midi': k, 'type': v['type'], 'number': v['number'],
               'path': v['path'], 'mode': v.get('mode', 'local'), 'name': v.get('name', '')}
              for k, v in mappings.items()]
    return jsonify({'success': True, 'mappings': result})

@midi_bp.route('/api/midi/mappings', methods=['POST'])
def add_mapping():
    d = request.get_json() or {}
    midi_type   = d.get('midi_type', 'cc')
    midi_number = d.get('midi_number')
    path        = d.get('parameter_path')
    if midi_number is None or not path:
        return jsonify({'success': False, 'error': 'midi_number and parameter_path required'}), 400
    key = f"{midi_type}:{midi_number}"
    mappings = _active_mappings()
    mappings[key] = {
        'type': midi_type, 'number': midi_number, 'path': path,
        'min': d.get('min_value', 0), 'max': d.get('max_value', 100),
        'mode': d.get('mapping_mode', 'local'), 'name': d.get('name', path)
    }
    _save_active_mappings(mappings)
    return jsonify({'success': True})

@midi_bp.route('/api/midi/mappings/<midi_type>/<int:midi_number>', methods=['DELETE'])
def delete_mapping(midi_type, midi_number):
    key = f"{midi_type}:{midi_number}"
    mappings = _active_mappings()
    if key not in mappings:
        return jsonify({'success': False, 'error': 'Mapping not found'}), 404
    del mappings[key]
    _save_active_mappings(mappings)
    return jsonify({'success': True})

# Profiles

@midi_bp.route('/api/midi/profiles', methods=['GET'])
def get_profiles():
    data   = _load_profiles()
    active = data.get('active_profile')
    result = [{'name': p['name'], 'description': p.get('description', ''),
               'mapping_count': len(p.get('mappings', {})), 'is_active': p['name'] == active}
              for p in data.get('profiles', [])]
    return jsonify({'success': True, 'profiles': result, 'active': active})

@midi_bp.route('/api/midi/profiles', methods=['POST'])
def create_profile():
    d = request.get_json() or {}
    name = d.get('name')
    if not name:
        return jsonify({'success': False, 'error': 'name required'}), 400
    data = _load_profiles()
    if any(p['name'] == name for p in data['profiles']):
        return jsonify({'success': False, 'error': 'Profile already exists'}), 409
    data['profiles'].append({'name': name, 'description': d.get('description', ''), 'mappings': {}})
    _save_profiles(data)
    return jsonify({'success': True})

@midi_bp.route('/api/midi/profiles/switch', methods=['POST'])
def switch_profile():
    name = (request.get_json() or {}).get('name')
    data = _load_profiles()
    if not any(p['name'] == name for p in data['profiles']):
        return jsonify({'success': False, 'error': 'Profile not found'}), 404
    data['active_profile'] = name
    _save_profiles(data)
    return jsonify({'success': True, 'active_profile': name})

@midi_bp.route('/api/midi/profiles/duplicate', methods=['POST'])
def duplicate_profile():
    d = request.get_json() or {}
    source, new_name = d.get('source'), d.get('name')
    data = _load_profiles()
    src = next((p for p in data['profiles'] if p['name'] == source), None)
    if not src:
        return jsonify({'success': False, 'error': 'Source not found'}), 404
    new_profile = copy.deepcopy(src)
    new_profile['name'] = new_name
    data['profiles'].append(new_profile)
    _save_profiles(data)
    return jsonify({'success': True})

@midi_bp.route('/api/midi/profiles/<name>/export', methods=['GET'])
def export_profile(name):
    data    = _load_profiles()
    profile = next((p for p in data['profiles'] if p['name'] == name), None)
    if not profile:
        return jsonify({'success': False, 'error': 'Not found'}), 404
    from flask import make_response
    r = make_response(json.dumps(profile, indent=2))
    r.headers['Content-Type'] = 'application/json'
    r.headers['Content-Disposition'] = f'attachment; filename={name}.midi_profile.json'
    return r

@midi_bp.route('/api/midi/profiles/import', methods=['POST'])
def import_profile():
    profile = request.get_json()
    if not profile or 'name' not in profile:
        return jsonify({'success': False, 'error': 'Invalid profile data'}), 400
    data = _load_profiles()
    if any(p['name'] == profile['name'] for p in data['profiles']):
        profile['name'] += ' (imported)'
    data['profiles'].append(profile)
    _save_profiles(data)
    return jsonify({'success': True, 'profile': profile['name']})

@midi_bp.route('/api/midi/profiles/<name>', methods=['DELETE'])
def delete_profile(name):
    if name == 'Default':
        return jsonify({'success': False, 'error': 'Cannot delete Default profile'}), 400
    data = _load_profiles()
    data['profiles'] = [p for p in data['profiles'] if p['name'] != name]
    if data.get('active_profile') == name:
        data['active_profile'] = 'Default'
    _save_profiles(data)
    return jsonify({'success': True})
```

### 4.2 SocketIO: MIDI Input Handler

```python
# In src/modules/rest_api.py (register on existing socketio instance)
from .api_midi import _active_mappings, matches_pattern

@socketio.on('midi_input')
def handle_midi_input(data):
    """Browser sends raw MIDI CC; backend resolves mapping and broadcasts midi_apply."""
    midi_type   = data.get('type', 'cc')
    midi_number = data.get('number')
    value       = data.get('value', 0)

    key     = f"{midi_type}:{midi_number}"
    mapping = _active_mappings().get(key)
    if not mapping:
        return

    socketio.emit('midi_apply', {
        'type':   midi_type,
        'number': midi_number,
        'value':  value,
        'path':   mapping['path'],
        'mode':   mapping.get('mode', 'local'),
        'min':    mapping.get('min', 0),
        'max':    mapping.get('max', 100)
    })
```

---

## Part 5: MIDI Clock (Server-side)

### 5.1 Protocol Reference

| Message | Byte | Description |
|---------|------|-------------|
| Timing Clock  | 0xF8 | 24 times per quarter note (24 PPQN) |
| Start         | 0xFA | Start playback from beginning |
| Continue      | 0xFB | Continue from current position |
| Stop          | 0xFC | Stop playback |
| Active Sensing| 0xFE | Keepalive (optional) |

```
BPM = 60 / (avg_clock_interval_seconds * 24)
Clock Interval (ms) = 60000 / (BPM * 24)
Example: 120 BPM -> 20.833ms between clock ticks
```

### 5.2 Dependencies

```txt
# requirements.txt
mido>=1.3.0
python-rtmidi>=1.5.0
```

### 5.3 MIDIClockManager

**File:** `src/modules/midi_clock.py`

```python
"""
MIDI Clock Manager
Server-side clock input/output for tempo synchronization.
"""
import mido
import time
import threading
import logging
from collections import deque

logger = logging.getLogger(__name__)


class MIDIClockManager:
    CLOCK    = 0xF8
    START    = 0xFA
    CONTINUE = 0xFB
    STOP     = 0xFC
    PPQN     = 24

    def __init__(self):
        self.input_port         = None
        self.input_device_name  = None
        self.input_thread       = None
        self.is_receiving       = False

        self.output_port        = None
        self.output_device_name = None
        self.output_thread      = None
        self.is_sending         = False

        self.bpm            = 0.0
        self.is_playing     = False
        self.beat_position  = 0.0      # 0.0-4.0 (quarter notes)
        self.clock_times    = deque(maxlen=24)
        self.last_clock_time = 0
        self.clock_count    = 0

        self.output_bpm     = 120.0
        self.output_running = False

        self.on_start_callback = None
        self.on_stop_callback  = None
        self.on_beat_callback  = None

    def get_input_devices(self):
        try:
            return mido.get_input_names()
        except Exception as e:
            logger.error(f"MIDI input devices error: {e}")
            return []

    def get_output_devices(self):
        try:
            return mido.get_output_names()
        except Exception as e:
            logger.error(f"MIDI output devices error: {e}")
            return []

    def connect_input(self, device_name=None):
        try:
            if self.is_receiving:
                self.disconnect_input()
            if device_name is None:
                devices = self.get_input_devices()
                if not devices:
                    raise RuntimeError("No MIDI input devices found")
                device_name = devices[0]
            self.input_port        = mido.open_input(device_name)
            self.input_device_name = device_name
            self.is_receiving      = True
            self.input_thread      = threading.Thread(target=self._input_loop, daemon=True)
            self.input_thread.start()
            logger.info(f"MIDI input connected: {device_name}")
            return True
        except Exception as e:
            logger.error(f"MIDI connect input: {e}")
            return False

    def disconnect_input(self):
        self.is_receiving = False
        if self.input_thread:
            self.input_thread.join(timeout=2)
        if self.input_port:
            self.input_port.close()
            self.input_port = None

    def _input_loop(self):
        try:
            for msg in self.input_port:
                if not self.is_receiving:
                    break
                if   msg.type == 'clock':    self._handle_clock()
                elif msg.type == 'start':    self._handle_start()
                elif msg.type == 'continue': self._handle_continue()
                elif msg.type == 'stop':     self._handle_stop()
        except Exception as e:
            logger.error(f"MIDI input loop: {e}")

    def _handle_clock(self):
        now = time.time()
        if self.last_clock_time > 0:
            self.clock_times.append(now - self.last_clock_time)
        self.last_clock_time = now
        self.clock_count += 1
        if len(self.clock_times) >= 24:
            avg = sum(self.clock_times) / len(self.clock_times)
            if avg > 0:
                self.bpm = 60.0 / (avg * 24)
        self.beat_position = (self.clock_count % 96) / 24.0
        if self.clock_count % 24 == 0 and self.on_beat_callback:
            self.on_beat_callback(int(self.beat_position))

    def _handle_start(self):
        self.is_playing    = True
        self.clock_count   = 0
        self.beat_position = 0.0
        if self.on_start_callback:
            self.on_start_callback()

    def _handle_continue(self):
        self.is_playing = True
        if self.on_start_callback:
            self.on_start_callback()

    def _handle_stop(self):
        self.is_playing = False
        if self.on_stop_callback:
            self.on_stop_callback()

    def connect_output(self, device_name=None, bpm=120.0):
        try:
            if self.is_sending:
                self.disconnect_output()
            if device_name is None:
                devices = self.get_output_devices()
                if not devices:
                    raise RuntimeError("No MIDI output devices found")
                device_name = devices[0]
            self.output_port        = mido.open_output(device_name)
            self.output_device_name = device_name
            self.output_bpm         = bpm
            self.is_sending         = True
            self.output_thread      = threading.Thread(target=self._output_loop, daemon=True)
            self.output_thread.start()
            logger.info(f"MIDI output connected: {device_name} @ {bpm} BPM")
            return True
        except Exception as e:
            logger.error(f"MIDI connect output: {e}")
            return False

    def disconnect_output(self):
        self.is_sending     = False
        self.output_running = False
        if self.output_thread:
            self.output_thread.join(timeout=2)
        if self.output_port:
            try:
                self.output_port.send(mido.Message.from_bytes([self.STOP]))
            except Exception:
                pass
            self.output_port.close()
            self.output_port = None

    def _output_loop(self):
        while self.is_sending:
            if self.output_running:
                interval = 60.0 / (self.output_bpm * self.PPQN)
                self.output_port.send(mido.Message.from_bytes([self.CLOCK]))
                time.sleep(interval)
            else:
                time.sleep(0.01)

    def send_start(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.START]))
            self.output_running = True

    def send_continue(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.CONTINUE]))
            self.output_running = True

    def send_stop(self):
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.STOP]))
            self.output_running = False

    def set_output_bpm(self, bpm):
        self.output_bpm = max(20.0, min(300.0, float(bpm)))

    def get_status(self):
        return {
            'input':  {
                'connected':    self.is_receiving,
                'device':       self.input_device_name,
                'bpm':          round(self.bpm, 1),
                'playing':      self.is_playing,
                'beat_position': round(self.beat_position, 2)
            },
            'output': {
                'connected': self.is_sending,
                'device':    self.output_device_name,
                'bpm':       self.output_bpm,
                'running':   self.output_running
            }
        }


_instance = None

def get_midi_clock_manager() -> MIDIClockManager:
    global _instance
    if _instance is None:
        _instance = MIDIClockManager()
    return _instance
```

### 5.4 Clock REST API + SocketIO Broadcast

Add to `src/modules/api_midi.py`:

```python
from .midi_clock import get_midi_clock_manager
import threading, time as _time

# MIDI Clock REST endpoints

@midi_bp.route('/api/midi/devices', methods=['GET'])
def get_midi_devices():
    mgr = get_midi_clock_manager()
    return jsonify({'success': True,
                    'input_devices':  mgr.get_input_devices(),
                    'output_devices': mgr.get_output_devices()})

@midi_bp.route('/api/midi/clock/connect-input', methods=['POST'])
def clock_connect_input():
    d  = request.get_json() or {}
    ok = get_midi_clock_manager().connect_input(d.get('device'))
    return jsonify({'success': ok, 'device': get_midi_clock_manager().input_device_name})

@midi_bp.route('/api/midi/clock/disconnect-input', methods=['POST'])
def clock_disconnect_input():
    get_midi_clock_manager().disconnect_input()
    return jsonify({'success': True})

@midi_bp.route('/api/midi/clock/connect-output', methods=['POST'])
def clock_connect_output():
    d  = request.get_json() or {}
    ok = get_midi_clock_manager().connect_output(d.get('device'), d.get('bpm', 120.0))
    return jsonify({'success': ok, 'device': get_midi_clock_manager().output_device_name})

@midi_bp.route('/api/midi/clock/disconnect-output', methods=['POST'])
def clock_disconnect_output():
    get_midi_clock_manager().disconnect_output()
    return jsonify({'success': True})

@midi_bp.route('/api/midi/clock/start',    methods=['POST'])
def clock_send_start():    get_midi_clock_manager().send_start();    return jsonify({'success': True})

@midi_bp.route('/api/midi/clock/continue', methods=['POST'])
def clock_send_continue(): get_midi_clock_manager().send_continue(); return jsonify({'success': True})

@midi_bp.route('/api/midi/clock/stop',     methods=['POST'])
def clock_send_stop():     get_midi_clock_manager().send_stop();     return jsonify({'success': True})

@midi_bp.route('/api/midi/clock/set-bpm', methods=['POST'])
def clock_set_bpm():
    d = request.get_json() or {}
    get_midi_clock_manager().set_output_bpm(d.get('bpm', 120.0))
    return jsonify({'success': True, 'bpm': get_midi_clock_manager().output_bpm})

@midi_bp.route('/api/midi/clock/status', methods=['GET'])
def clock_status():
    return jsonify({'success': True, 'status': get_midi_clock_manager().get_status()})


def _start_clock_broadcast(socketio_instance):
    """Push MIDI clock status at 20 Hz via SocketIO."""
    def _loop():
        while True:
            try:
                socketio_instance.emit('midi_clock_update', get_midi_clock_manager().get_status())
            except Exception:
                pass
            _time.sleep(0.05)
    threading.Thread(target=_loop, daemon=True).start()


def init_midi_api(app, socketio_instance):
    app.register_blueprint(midi_bp)
    _start_clock_broadcast(socketio_instance)
    logger.info("MIDI API initialized")
```

**Call from `main.py`:**

```python
from src.modules.api_midi import init_midi_api
init_midi_api(app, rest_api.socketio)
```

### 5.5 Frontend Clock Display

**File:** `frontend/components/midi-clock.html`

```html
<div class="midi-clock-container p-3">
    <!-- Input -->
    <div class="midi-section mb-3">
        <div class="d-flex justify-content-between mb-2">
            <strong>Clock In</strong>
            <span id="clockInStatus" class="badge bg-secondary">Disconnected</span>
        </div>
        <div class="d-flex gap-2 mb-2">
            <select id="clockInputDevice" class="form-select form-select-sm flex-grow-1"></select>
            <button class="btn btn-sm btn-primary" onclick="midiClock.connectInput()">Connect</button>
        </div>
        <div class="d-flex gap-3 mb-2">
            <span>BPM: <strong id="clockInBPM">--</strong></span>
            <span>Beat: <strong id="clockInBeat">--</strong></span>
        </div>
        <div class="d-flex gap-2">
            <div class="beat-dot" id="beat-0"></div>
            <div class="beat-dot" id="beat-1"></div>
            <div class="beat-dot" id="beat-2"></div>
            <div class="beat-dot" id="beat-3"></div>
        </div>
    </div>

    <!-- Output -->
    <div class="midi-section">
        <div class="d-flex justify-content-between mb-2">
            <strong>Clock Out</strong>
            <span id="clockOutStatus" class="badge bg-secondary">Disconnected</span>
        </div>
        <div class="d-flex gap-2 mb-2">
            <select id="clockOutputDevice" class="form-select form-select-sm flex-grow-1"></select>
            <button class="btn btn-sm btn-primary" onclick="midiClock.connectOutput()">Connect</button>
        </div>
        <div class="mb-2">
            <label class="small">BPM: <strong id="clockOutBPMValue">120</strong></label>
            <input type="range" class="form-range" id="clockOutBPM"
                   min="20" max="300" value="120"
                   oninput="midiClock.setBPM(this.value)">
        </div>
        <div class="d-flex gap-2">
            <button class="btn btn-sm btn-success" onclick="midiClock.start()">Start</button>
            <button class="btn btn-sm btn-warning" onclick="midiClock.continue()">Continue</button>
            <button class="btn btn-sm btn-danger"  onclick="midiClock.stop()">Stop</button>
        </div>
    </div>
</div>

<script>
const midiClock = {
    async init() {
        const data = await (await fetch('/api/midi/devices')).json();
        if (data.success) {
            this._fill('clockInputDevice',  data.input_devices);
            this._fill('clockOutputDevice', data.output_devices);
        }
        socket.on('midi_clock_update', (s) => this._update(s));
    },
    _fill(id, devices) {
        const sel = document.getElementById(id);
        sel.innerHTML = '<option value="">Select device...</option>';
        devices.forEach(d => {
            const o = document.createElement('option');
            o.value = o.textContent = d;
            sel.appendChild(o);
        });
    },
    async connectInput() {
        const device = document.getElementById('clockInputDevice').value;
        if (!device) return;
        await fetch('/api/midi/clock/connect-input', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ device })
        });
    },
    async connectOutput() {
        const device = document.getElementById('clockOutputDevice').value;
        const bpm    = parseFloat(document.getElementById('clockOutBPM').value);
        if (!device) return;
        await fetch('/api/midi/clock/connect-output', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ device, bpm })
        });
    },
    async setBPM(bpm) {
        document.getElementById('clockOutBPMValue').textContent = bpm;
        await fetch('/api/midi/clock/set-bpm', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ bpm: parseFloat(bpm) })
        });
    },
    async start()    { await fetch('/api/midi/clock/start',    { method: 'POST' }); },
    async continue() { await fetch('/api/midi/clock/continue', { method: 'POST' }); },
    async stop()     { await fetch('/api/midi/clock/stop',     { method: 'POST' }); },
    _update(s) {
        document.getElementById('clockInStatus').textContent =
            s.input.connected ? 'Connected: ' + s.input.device : 'Disconnected';
        document.getElementById('clockInStatus').className =
            'badge ' + (s.input.connected ? 'bg-success' : 'bg-secondary');
        document.getElementById('clockInBPM').textContent  = s.input.bpm  || '--';
        document.getElementById('clockInBeat').textContent = s.input.beat_position || '--';

        const beat = Math.floor(s.input.beat_position) % 4;
        for (let i = 0; i < 4; i++)
            document.getElementById('beat-' + i).classList.toggle('beat-active', i === beat && s.input.playing);

        const running = s.output.running;
        document.getElementById('clockOutStatus').textContent =
            s.output.connected ? s.output.device + (running ? ' (Running)' : '') : 'Disconnected';
        document.getElementById('clockOutStatus').className =
            'badge ' + (running ? 'bg-primary' : s.output.connected ? 'bg-success' : 'bg-secondary');
    }
};
document.addEventListener('DOMContentLoaded', () => midiClock.init());
</script>
```

### 5.6 Integration Examples

```python
# Sync sequencer to MIDI clock
from src.modules.midi_clock import get_midi_clock_manager

midi = get_midi_clock_manager()
midi.on_start_callback = sequencer.play
midi.on_stop_callback  = sequencer.pause
```

```python
# Beat-synced GLSL effect — pass beat phase as uniform
class StrobeEffect(EffectPlugin):
    def get_uniforms(self, parameters, frame_count, fps):
        midi = get_midi_clock_manager()
        return {
            'u_beat_phase': midi.beat_position % 1.0,
            'u_playing':    float(midi.is_playing)
        }
```

```javascript
// Sync MIDI output BPM from detected audio BPM
async function onBPMDetected(bpm) {
    await fetch('/api/midi/clock/set-bpm', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ bpm })
    });
}
```

---

## File Reference

| File | Purpose |
|------|---------|
| `src/modules/midi_clock.py` | MIDI Clock Manager (server-side mido/rtmidi) |
| `src/modules/api_midi.py` | All REST + SocketIO handlers |
| `frontend/js/midi-learn.js` | VisualMIDILearnManager (Web MIDI API) |
| `frontend/components/midi-clock.html` | Clock display component |
| `frontend/css/midi-display.css` | MIDI Learn + Clock styles |
| `config/midi_profiles.json` | MIDI mappings/profiles (auto-created) |

---

## Performance

| Component | CPU | Latency |
|-----------|-----|---------|
| MIDI Clock input (rtmidi) | <1% | <5ms |
| MIDI Clock output | ~1-2% | <1ms jitter |
| SocketIO clock broadcast (20 Hz) | <0.5% | 50ms (UI only) |
| Web MIDI API -> SocketIO -> apply | <1% | 5-15ms |

---

## Troubleshooting

**No MIDI devices found:**
- Verify device connected, drivers installed
- Test: `python -c "import mido; print(mido.get_input_names())"`
- Restart the application

**Clock drift / jitter:**
- Close other MIDI applications on the same device
- Use a dedicated USB port (not a hub)

**Web MIDI API not working:**
- Must use Chrome, Edge, or Opera (Firefox/Safari not supported)
- Browser shows permission prompt on first use

**MIDI Learn not detecting input:**
- Check browser console for Web MIDI permission errors
- Confirm controller sends CC messages (not just SysEx/Note)

---

## Future Enhancements

- Note triggers — MIDI notes trigger clip playback / scene switching
- Program Change — switch MIDI profiles or scenes
- MIDI Thru — pass-through to daisy-chained devices
- Ableton Link — network tempo sync
- MTC (MIDI Time Code) — frame-accurate sync
- Multiple simultaneous input devices
