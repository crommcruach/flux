# Dynamic Parameter Sequences - Implementation Plan

**Priority:** 🔥 P1 - Critical  
**Estimated Time:** 6-10 hours  
**Status:** Planning Phase  
**Last Updated:** December 23, 2025

---

## 📋 Overview

Dynamic Parameter Sequences enable automated, real-time modulation of any effect or source parameter. This creates evolving, dynamic visuals without manual control and is essential for music-reactive shows.

**Key Features:**
- 🎵 **Audio Reactive** - Bind parameters to audio features (Bass, RMS, Peak, etc.)
- 🌊 **LFO** - Low Frequency Oscillator with multiple waveforms
- 📈 **Timeline Keyframes** - Time-based parameter animation with curves
- 📊 **ADSR Envelope** - Attack/Decay/Sustain/Release modulation

---

## 🎯 Goals

1. **Universal Parameter Control** - Any numeric parameter can be sequenced
2. **Backend Audio Analysis** - Headless operation without browser dependency
3. **Real-time Performance** - <5ms latency for audio-reactive modulation
4. **Multiple Simultaneous Sequences** - Stack multiple modulators per parameter
5. **Easy Integration** - Minimal changes to existing effect/source code

---

## 🏗️ Architecture

### Module Structure

```
src/modules/sequences/
├── __init__.py
├── sequence_manager.py      # Main coordinator
├── base_sequence.py          # Abstract base class
├── audio_analyzer.py         # Backend audio input & FFT analysis
├── audio_sequence.py         # Audio-reactive sequence
├── lfo_sequence.py           # LFO oscillator
├── timeline_sequence.py      # Keyframe timeline
└── envelope_sequence.py      # ADSR envelope
```

### Core Components

#### 1. SequenceManager
- Central registry for all sequences
- Manages sequence lifecycle (create, update, delete)
- Applies modulation to parameters each frame
- REST API endpoint handler

#### 2. AudioAnalyzer (Backend Service)
- **Runs in separate thread** (critical for headless operation)
- Audio input via `sounddevice` (microphone or system loopback)
- Real-time FFT analysis (Bass/Mid/Treble frequency bands)
- BPM detection & beat tracking (optional: librosa)
- Onset detection for beat triggers
- Exposes audio features via thread-safe properties
- WebSocket broadcast for UI visualization

#### 3. Sequence Types (All inherit from BaseSequence)
- **AudioSequence** - Reads from AudioAnalyzer features
- **LFOSequence** - Generates waveforms (Sine, Square, Sawtooth, etc.)
- **TimelineSequence** - Interpolates keyframes
- **EnvelopeSequence** - ADSR state machine

---

## 📐 Design Decisions

### ✅ Backend Audio Analysis (NOT Frontend)

**Reason:** Headless operation + reliability

```
❌ WRONG: Browser-based audio analysis
- Requires browser tab open
- Unreliable for headless servers
- Cannot access system audio easily

✅ CORRECT: Backend audio thread
- Works without browser
- Direct system audio access (WASAPI Loopback)
- Consistent performance
- Similar to AudioSequencer architecture
```

### ✅ Thread-Safe Feature Cache

AudioAnalyzer updates features in audio thread, SequenceManager reads from main render thread:

```python
class AudioAnalyzer:
    def __init__(self):
        self._features = {
            'rms': 0.0,
            'peak': 0.0,
            'bass': 0.0,  # 20-250 Hz
            'mid': 0.0,   # 250-4000 Hz
            'treble': 0.0, # 4000-20000 Hz
            'bpm': 0.0,
            'beat': False  # Onset detection
        }
        self._lock = threading.Lock()
    
    def get_features(self):
        with self._lock:
            return self._features.copy()
```

### ✅ Parameter Target System

Sequences target parameters using dot notation:

```
player.video.clip.effects[0].brightness  # Effect parameter
player.video.clip.transform.scale        # Transform parameter
player.artnet.clip.color_r               # Source parameter
```

---

## 🔨 Implementation Phases

### Phase 1: Core Architecture (2-3h)

**Files to Create:**
- `src/modules/sequences/__init__.py`
- `src/modules/sequences/base_sequence.py`
- `src/modules/sequences/sequence_manager.py`

**Tasks:**
- [ ] BaseSequence abstract class
  - Properties: `id`, `name`, `type`, `target_parameter`, `enabled`
  - Methods: `update(dt)`, `get_value()`, `serialize()`, `deserialize()`
  
- [ ] SequenceManager class
  - Registry: `Dict[str, BaseSequence]`
  - Methods: `create()`, `delete()`, `update_all(dt)`, `apply_modulation()`
  - Parameter resolution: Parse dot notation to actual object property
  
- [ ] Integration with PlayerManager
  - Call `sequence_manager.update_all(dt)` each frame
  - Apply modulated values before rendering

**API Endpoints:**
```
POST   /api/sequences                    # Create sequence
GET    /api/sequences                    # List all sequences
GET    /api/sequences/{id}               # Get sequence details
PUT    /api/sequences/{id}               # Update sequence
DELETE /api/sequences/{id}               # Delete sequence
POST   /api/sequences/{id}/toggle        # Enable/disable
```

---

### Phase 2: Audio Reactive (2-3h)

**Files to Create:**
- `src/modules/sequences/audio_analyzer.py`
- `src/modules/sequences/audio_sequence.py`

#### 2.1 AudioAnalyzer Implementation

```python
import sounddevice as sd
import numpy as np
import threading
from collections import deque

class AudioAnalyzer:
    """Backend audio analysis service (runs in separate thread)"""
    
    def __init__(self, device=None, sample_rate=44100, block_size=2048):
        self.device = device  # None = default input
        self.sample_rate = sample_rate
        self.block_size = block_size
        
        # Feature cache (thread-safe)
        self._features = {
            'rms': 0.0,
            'peak': 0.0,
            'bass': 0.0,
            'mid': 0.0,
            'treble': 0.0,
            'bpm': 0.0,
            'beat': False
        }
        self._lock = threading.Lock()
        
        # Audio buffer for BPM detection
        self._audio_buffer = deque(maxlen=sample_rate * 4)  # 4 seconds
        
        # FFT setup
        self._window = np.hanning(block_size)
        
        # Stream
        self._stream = None
        self._running = False
    
    def start(self):
        """Start audio capture"""
        if self._running:
            return
        
        self._stream = sd.InputStream(
            device=self.device,
            channels=1,
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            callback=self._audio_callback
        )
        self._stream.start()
        self._running = True
    
    def stop(self):
        """Stop audio capture"""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False
    
    def _audio_callback(self, indata, frames, time, status):
        """Audio thread callback (do NOT block!)"""
        if status:
            print(f"Audio status: {status}")
        
        audio = indata[:, 0]  # Mono
        
        # Add to buffer for BPM detection
        self._audio_buffer.extend(audio)
        
        # Calculate RMS (Root Mean Square)
        rms = np.sqrt(np.mean(audio**2))
        
        # Calculate Peak
        peak = np.max(np.abs(audio))
        
        # FFT Analysis
        windowed = audio * self._window
        fft = np.fft.rfft(windowed)
        magnitude = np.abs(fft)
        freqs = np.fft.rfftfreq(self.block_size, 1/self.sample_rate)
        
        # Frequency bands
        bass = np.mean(magnitude[(freqs >= 20) & (freqs < 250)])
        mid = np.mean(magnitude[(freqs >= 250) & (freqs < 4000)])
        treble = np.mean(magnitude[(freqs >= 4000) & (freqs < 20000)])
        
        # Normalize to 0-1 range (adjust scaling as needed)
        bass_norm = np.clip(bass / 100, 0, 1)
        mid_norm = np.clip(mid / 50, 0, 1)
        treble_norm = np.clip(treble / 20, 0, 1)
        
        # Beat detection (simple onset)
        beat = peak > 0.5  # Threshold-based (improve with proper onset detection)
        
        # Update features (thread-safe)
        with self._lock:
            self._features['rms'] = float(rms)
            self._features['peak'] = float(peak)
            self._features['bass'] = float(bass_norm)
            self._features['mid'] = float(mid_norm)
            self._features['treble'] = float(treble_norm)
            self._features['beat'] = beat
    
    def get_features(self):
        """Get current audio features (thread-safe)"""
        with self._lock:
            return self._features.copy()
    
    def list_devices(self):
        """List available audio input devices"""
        return sd.query_devices()
```

#### 2.2 AudioSequence Implementation

```python
from .base_sequence import BaseSequence

class AudioSequence(BaseSequence):
    """Audio-reactive parameter modulation"""
    
    def __init__(self, sequence_id, target_parameter, audio_analyzer, 
                 feature='rms', min_value=0.0, max_value=1.0, 
                 smoothing=0.1, invert=False):
        super().__init__(sequence_id, 'audio', target_parameter)
        
        self.audio_analyzer = audio_analyzer
        self.feature = feature  # 'rms', 'peak', 'bass', 'mid', 'treble', 'beat'
        self.min_value = min_value
        self.max_value = max_value
        self.smoothing = smoothing  # Attack/Release (0-1, lower = smoother)
        self.invert = invert
        
        self._current_value = 0.0
    
    def update(self, dt):
        """Update sequence value"""
        features = self.audio_analyzer.get_features()
        audio_value = features.get(self.feature, 0.0)
        
        # Map to parameter range
        if self.invert:
            audio_value = 1.0 - audio_value
        
        target_value = self.min_value + (audio_value * (self.max_value - self.min_value))
        
        # Smooth transition (exponential smoothing)
        if self.smoothing > 0:
            alpha = 1.0 - np.exp(-dt / self.smoothing)
            self._current_value += (target_value - self._current_value) * alpha
        else:
            self._current_value = target_value
    
    def get_value(self):
        """Get current modulated value"""
        return self._current_value
    
    def serialize(self):
        """Export to JSON"""
        return {
            'id': self.id,
            'type': self.type,
            'target_parameter': self.target_parameter,
            'feature': self.feature,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'smoothing': self.smoothing,
            'invert': self.invert,
            'enabled': self.enabled
        }
```

**Tasks:**
- [ ] AudioAnalyzer: Device selection, start/stop, FFT analysis
- [ ] AudioSequence: Feature binding, range mapping, smoothing
- [ ] API: Audio device list, analyzer control
- [ ] WebSocket: Broadcast audio features for UI visualization (optional)

**API Endpoints:**
```
GET  /api/audio/devices              # List audio input devices
POST /api/audio/start                # Start audio analyzer
POST /api/audio/stop                 # Stop audio analyzer
GET  /api/audio/features             # Get current audio features
```

---

### Phase 3: LFO Oscillator (1-2h)

**Files to Create:**
- `src/modules/sequences/lfo_sequence.py`

```python
import math
import numpy as np
from .base_sequence import BaseSequence

class LFOSequence(BaseSequence):
    """Low Frequency Oscillator"""
    
    WAVEFORMS = ['sine', 'square', 'triangle', 'sawtooth', 'random']
    
    def __init__(self, sequence_id, target_parameter, waveform='sine',
                 frequency=1.0, amplitude=1.0, offset=0.0, phase=0.0,
                 min_value=0.0, max_value=1.0):
        super().__init__(sequence_id, 'lfo', target_parameter)
        
        self.waveform = waveform
        self.frequency = frequency  # Hz
        self.amplitude = amplitude
        self.offset = offset
        self.phase = phase  # 0-1 (0 = 0°, 0.5 = 180°, 1 = 360°)
        self.min_value = min_value
        self.max_value = max_value
        
        self._time = 0.0
        self._last_random = 0.0
    
    def update(self, dt):
        """Update oscillator time"""
        self._time += dt
    
    def get_value(self):
        """Calculate current oscillator value"""
        # Calculate phase-adjusted time
        t = (self._time * self.frequency + self.phase) % 1.0
        
        # Generate waveform
        if self.waveform == 'sine':
            wave = math.sin(t * 2 * math.pi)
        
        elif self.waveform == 'square':
            wave = 1.0 if t < 0.5 else -1.0
        
        elif self.waveform == 'triangle':
            wave = 1.0 - 4.0 * abs(t - 0.5)
        
        elif self.waveform == 'sawtooth':
            wave = 2.0 * t - 1.0
        
        elif self.waveform == 'random':
            # Stepped random (changes at frequency rate)
            if int(self._time * self.frequency) != int((self._time - 0.001) * self.frequency):
                self._last_random = np.random.uniform(-1, 1)
            wave = self._last_random
        
        else:
            wave = 0.0
        
        # Apply amplitude and offset
        value = wave * self.amplitude + self.offset
        
        # Map to parameter range
        normalized = (value + 1.0) / 2.0  # -1..1 → 0..1
        return self.min_value + (normalized * (self.max_value - self.min_value))
    
    def serialize(self):
        return {
            'id': self.id,
            'type': self.type,
            'target_parameter': self.target_parameter,
            'waveform': self.waveform,
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'offset': self.offset,
            'phase': self.phase,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'enabled': self.enabled
        }
```

**Tasks:**
- [ ] LFOSequence: All waveforms, frequency control
- [ ] Phase offset for multi-LFO sync
- [ ] API integration

---

### Phase 4: Timeline Keyframes (2-3h)

**Files to Create:**
- `src/modules/sequences/timeline_sequence.py`

```python
from .base_sequence import BaseSequence
import bisect

class TimelineSequence(BaseSequence):
    """Keyframe-based timeline animation"""
    
    INTERPOLATIONS = ['linear', 'ease_in', 'ease_out', 'ease_in_out', 'step']
    LOOP_MODES = ['once', 'loop', 'ping_pong']
    
    def __init__(self, sequence_id, target_parameter, keyframes=None,
                 interpolation='linear', loop_mode='once', duration=10.0):
        super().__init__(sequence_id, 'timeline', target_parameter)
        
        self.keyframes = keyframes or []  # [(time, value), ...]
        self.interpolation = interpolation
        self.loop_mode = loop_mode
        self.duration = duration
        
        self._time = 0.0
        self._direction = 1  # 1 = forward, -1 = backward (for ping_pong)
        
        # Sort keyframes by time
        self.keyframes.sort(key=lambda k: k[0])
    
    def update(self, dt):
        """Update timeline time"""
        self._time += dt * self._direction
        
        # Handle loop modes
        if self.loop_mode == 'once':
            self._time = min(self._time, self.duration)
        
        elif self.loop_mode == 'loop':
            if self._time >= self.duration:
                self._time = self._time % self.duration
        
        elif self.loop_mode == 'ping_pong':
            if self._time >= self.duration:
                self._time = self.duration
                self._direction = -1
            elif self._time <= 0:
                self._time = 0
                self._direction = 1
    
    def get_value(self):
        """Interpolate value at current time"""
        if not self.keyframes:
            return 0.0
        
        # Find surrounding keyframes
        times = [k[0] for k in self.keyframes]
        idx = bisect.bisect_left(times, self._time)
        
        # Before first keyframe
        if idx == 0:
            return self.keyframes[0][1]
        
        # After last keyframe
        if idx >= len(self.keyframes):
            return self.keyframes[-1][1]
        
        # Between keyframes
        k1_time, k1_value = self.keyframes[idx - 1]
        k2_time, k2_value = self.keyframes[idx]
        
        # Normalize time (0-1 between keyframes)
        t = (self._time - k1_time) / (k2_time - k1_time)
        
        # Apply interpolation
        if self.interpolation == 'linear':
            t_interp = t
        
        elif self.interpolation == 'ease_in':
            t_interp = t * t
        
        elif self.interpolation == 'ease_out':
            t_interp = 1 - (1 - t) * (1 - t)
        
        elif self.interpolation == 'ease_in_out':
            t_interp = 3*t*t - 2*t*t*t  # Smoothstep
        
        elif self.interpolation == 'step':
            t_interp = 0  # Hold value until next keyframe
        
        else:
            t_interp = t
        
        # Interpolate value
        return k1_value + (k2_value - k1_value) * t_interp
    
    def add_keyframe(self, time, value):
        """Add keyframe and resort"""
        self.keyframes.append((time, value))
        self.keyframes.sort(key=lambda k: k[0])
    
    def remove_keyframe(self, index):
        """Remove keyframe by index"""
        if 0 <= index < len(self.keyframes):
            del self.keyframes[index]
    
    def serialize(self):
        return {
            'id': self.id,
            'type': self.type,
            'target_parameter': self.target_parameter,
            'keyframes': self.keyframes,
            'interpolation': self.interpolation,
            'loop_mode': self.loop_mode,
            'duration': self.duration,
            'enabled': self.enabled
        }
```

**Tasks:**
- [ ] TimelineSequence: Keyframe interpolation, loop modes
- [ ] Keyframe CRUD operations
- [ ] UI: Timeline editor with draggable keyframes

---

### Phase 5: ADSR Envelope (1-2h, Optional)

**Files to Create:**
- `src/modules/sequences/envelope_sequence.py`

```python
from .base_sequence import BaseSequence

class EnvelopeSequence(BaseSequence):
    """ADSR Envelope (Attack, Decay, Sustain, Release)"""
    
    TRIGGER_MODES = ['on_load', 'on_beat', 'manual']
    
    def __init__(self, sequence_id, target_parameter,
                 attack=0.1, decay=0.2, sustain=0.7, release=0.3,
                 min_value=0.0, max_value=1.0, trigger_mode='manual'):
        super().__init__(sequence_id, 'envelope', target_parameter)
        
        self.attack = attack      # Time to reach peak (seconds)
        self.decay = decay        # Time to reach sustain level
        self.sustain = sustain    # Sustain level (0-1)
        self.release = release    # Time to reach 0 after release
        self.min_value = min_value
        self.max_value = max_value
        self.trigger_mode = trigger_mode
        
        self._state = 'idle'  # 'idle', 'attack', 'decay', 'sustain', 'release'
        self._time = 0.0
        self._value = 0.0
    
    def trigger(self):
        """Start envelope (Attack phase)"""
        self._state = 'attack'
        self._time = 0.0
    
    def release_trigger(self):
        """Start Release phase"""
        if self._state != 'idle':
            self._state = 'release'
            self._time = 0.0
    
    def update(self, dt):
        """Update envelope state"""
        if self._state == 'idle':
            self._value = 0.0
            return
        
        self._time += dt
        
        if self._state == 'attack':
            # Ramp up to 1.0
            if self._time >= self.attack:
                self._value = 1.0
                self._state = 'decay'
                self._time = 0.0
            else:
                self._value = self._time / self.attack
        
        elif self._state == 'decay':
            # Ramp down to sustain level
            if self._time >= self.decay:
                self._value = self.sustain
                self._state = 'sustain'
                self._time = 0.0
            else:
                progress = self._time / self.decay
                self._value = 1.0 - (1.0 - self.sustain) * progress
        
        elif self._state == 'sustain':
            # Hold sustain level
            self._value = self.sustain
        
        elif self._state == 'release':
            # Ramp down to 0
            if self._time >= self.release:
                self._value = 0.0
                self._state = 'idle'
                self._time = 0.0
            else:
                start_value = self._value  # Value when release started
                progress = self._time / self.release
                self._value = start_value * (1.0 - progress)
    
    def get_value(self):
        """Get current envelope value"""
        return self.min_value + (self._value * (self.max_value - self.min_value))
    
    def serialize(self):
        return {
            'id': self.id,
            'type': self.type,
            'target_parameter': self.target_parameter,
            'attack': self.attack,
            'decay': self.decay,
            'sustain': self.sustain,
            'release': self.release,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'trigger_mode': self.trigger_mode,
            'enabled': self.enabled
        }
```

**Tasks:**
- [ ] EnvelopeSequence: ADSR state machine
- [ ] Trigger API endpoint
- [ ] UI: ADSR curve visualization

---

### Phase 6: Frontend UI (2-3h)

**UI Components:**

#### 1. Sequence Button (Next to Parameters)
```html
<!-- Add ⚙️ button next to each parameter -->
<input type="range" id="param-brightness" />
<button class="btn btn-sm" onclick="openSequenceEditor('brightness')">⚙️</button>
```

#### 2. Sequence Editor Modal
```html
<div class="modal" id="sequenceEditorModal">
  <div class="modal-header">
    <h5>Parameter Sequence: <span id="seq-param-name"></span></h5>
  </div>
  <div class="modal-body">
    <!-- Type Selector -->
    <select id="seq-type">
      <option value="audio">Audio Reactive</option>
      <option value="lfo">LFO</option>
      <option value="timeline">Timeline Keyframes</option>
      <option value="envelope">ADSR Envelope</option>
    </select>
    
    <!-- Type-specific controls (dynamic) -->
    <div id="seq-controls"></div>
    
    <!-- Live Preview -->
    <div class="preview">
      <canvas id="seq-preview"></canvas>
      <span>Current Value: <span id="seq-value">0.00</span></span>
    </div>
  </div>
  <div class="modal-footer">
    <button class="btn btn-primary" onclick="saveSequence()">Save</button>
    <button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
  </div>
</div>
```

#### 3. Audio Reactive Controls
```html
<div id="audio-controls">
  <label>Audio Feature:</label>
  <select id="audio-feature">
    <option value="rms">RMS Level</option>
    <option value="peak">Peak</option>
    <option value="bass">Bass (20-250Hz)</option>
    <option value="mid">Mid (250-4000Hz)</option>
    <option value="treble">Treble (4000-20000Hz)</option>
  </select>
  
  <label>Min Value: <input type="number" id="audio-min" value="0" /></label>
  <label>Max Value: <input type="number" id="audio-max" value="100" /></label>
  <label>Smoothing: <input type="range" id="audio-smooth" min="0" max="1" step="0.01" value="0.1" /></label>
  <label><input type="checkbox" id="audio-invert" /> Invert</label>
  
  <!-- Live Spectrum -->
  <canvas id="audio-spectrum" width="400" height="100"></canvas>
</div>
```

#### 4. LFO Controls
```html
<div id="lfo-controls">
  <label>Waveform:</label>
  <select id="lfo-wave">
    <option value="sine">Sine</option>
    <option value="square">Square</option>
    <option value="triangle">Triangle</option>
    <option value="sawtooth">Sawtooth</option>
    <option value="random">Random</option>
  </select>
  
  <label>Frequency: <input type="number" id="lfo-freq" value="1.0" step="0.1" /> Hz</label>
  <label>Amplitude: <input type="range" id="lfo-amp" min="0" max="1" step="0.01" value="1" /></label>
  <label>Phase: <input type="range" id="lfo-phase" min="0" max="1" step="0.01" value="0" /></label>
  
  <!-- Waveform Preview -->
  <canvas id="lfo-preview" width="400" height="100"></canvas>
</div>
```

**Tasks:**
- [ ] Modal component with type selector
- [ ] Type-specific control panels
- [ ] Live preview canvas
- [ ] WebSocket subscription for audio features
- [ ] Save/load/delete sequence

---

## 🔌 API Reference

### Sequence Management

```
POST   /api/sequences
Body: {
  "type": "audio|lfo|timeline|envelope",
  "target_parameter": "player.video.clip.effects[0].brightness",
  "config": { ... type-specific config ... }
}

GET    /api/sequences
Response: [
  {
    "id": "seq_001",
    "type": "audio",
    "target_parameter": "player.video.clip.effects[0].brightness",
    "enabled": true,
    "config": { ... }
  }
]

PUT    /api/sequences/{id}
Body: { "config": { ... } }

DELETE /api/sequences/{id}

POST   /api/sequences/{id}/toggle
```

### Audio Analyzer

```
GET    /api/audio/devices
Response: [
  {"index": 0, "name": "Microphone", "channels": 1},
  {"index": 1, "name": "System Audio", "channels": 2}
]

POST   /api/audio/start
Body: {"device": 0}

POST   /api/audio/stop

GET    /api/audio/features
Response: {
  "rms": 0.45,
  "peak": 0.78,
  "bass": 0.62,
  "mid": 0.34,
  "treble": 0.21,
  "bpm": 120.0,
  "beat": false
}
```

### Envelope Triggers

```
POST   /api/sequences/{id}/trigger       # Start envelope
POST   /api/sequences/{id}/release       # Release envelope
```

---

## 🧪 Testing Plan

### Unit Tests
- [ ] BaseSequence serialization
- [ ] AudioSequence feature mapping & smoothing
- [ ] LFOSequence waveform generation
- [ ] TimelineSequence interpolation
- [ ] EnvelopeSequence state transitions

### Integration Tests
- [ ] SequenceManager parameter resolution
- [ ] AudioAnalyzer thread safety
- [ ] Multiple sequences on same parameter (stacking)
- [ ] Sequence enable/disable

### Performance Tests
- [ ] 100 simultaneous sequences < 5ms latency
- [ ] Audio analysis CPU usage < 5%
- [ ] Memory leak checks (long-running)

---

## 🎯 Use Cases

### 1. Bass-Reactive Brightness
```json
{
  "type": "audio",
  "target_parameter": "player.video.clip.effects[0].brightness",
  "config": {
    "feature": "bass",
    "min_value": 50,
    "max_value": 150,
    "smoothing": 0.05
  }
}
```

### 2. Color Cycling with LFO
```json
{
  "type": "lfo",
  "target_parameter": "player.video.clip.effects[1].hue_shift",
  "config": {
    "waveform": "sine",
    "frequency": 0.5,
    "min_value": 0,
    "max_value": 360
  }
}
```

### 3. Timed Fade Out
```json
{
  "type": "timeline",
  "target_parameter": "player.video.clip.opacity",
  "config": {
    "keyframes": [
      [0, 100],
      [8, 100],
      [10, 0]
    ],
    "interpolation": "ease_out",
    "loop_mode": "once"
  }
}
```

### 4. Beat-Triggered Flash
```json
{
  "type": "envelope",
  "target_parameter": "player.video.clip.effects[0].brightness",
  "config": {
    "attack": 0.01,
    "decay": 0.05,
    "sustain": 0.3,
    "release": 0.2,
    "trigger_mode": "on_beat"
  }
}
```

---

## 📦 Dependencies

**Required:**
```bash
pip install sounddevice numpy
```

**Optional (for advanced features):**
```bash
pip install librosa  # BPM detection & onset analysis
```

**System Requirements:**
- Python 3.8+
- Audio input device (microphone or virtual loopback)

---

## 🚀 Future Enhancements

### Phase 2 Extensions (Post-MVP)
- [ ] **Macro Sequences** - Control multiple parameters with one sequence
- [ ] **Sequence Presets** - Save/load common configurations
- [ ] **MIDI-Triggered Envelopes** - External hardware triggers
- [ ] **Expression Parser** - Custom math formulas (e.g., `sin(time * 2) * bass`)
- [ ] **Sequence Recording** - Record manual parameter changes as timeline
- [ ] **Advanced BPM** - Phase-locked loop, beat quantization
- [ ] **Multi-Band Audio** - 8-10 frequency bands for finer control

---

## 📊 Success Metrics

- ✅ **Performance:** <5ms sequence update latency
- ✅ **Capacity:** Support 100+ simultaneous sequences
- ✅ **Audio Latency:** <50ms input-to-visual latency
- ✅ **CPU Usage:** Audio analysis <5% on modern CPU
- ✅ **Reliability:** Headless operation without browser
- ✅ **Usability:** <3 clicks to bind parameter to audio

---

## 🔗 Related Documentation

- [PLUGIN_SYSTEM.md](PLUGIN_SYSTEM.md) - Effect plugin integration
- [UNIFIED_API.md](UNIFIED_API.md) - API architecture
- [SEQUENCER_IMPLEMENTATION_PLAN.md](SEQUENCER_IMPLEMENTATION_PLAN.md) - Audio timeline sequencer

---

*Last Updated: December 23, 2025*
