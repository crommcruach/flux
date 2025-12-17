# Audio-Driven Sequencer Implementation Plan

## Overview
Implementation plan for Phase 1 (Backend Audio) and Phase 3 (Master Integration) of the Audio-Driven Sequencer.

**Status:** UI completed (WaveSurfer.js integrated in player.html)  
**Next:** Backend audio engine + Master playlist integration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (DONE)                           │
│  - WaveSurfer.js waveform visualization                     │
│  - Split management (click to add, right-click to remove)   │
│  - Slot display with clip mapping                           │
│  - Playback controls (play/pause/stop)                      │
└─────────────────────────────┬───────────────────────────────┘
                              │ REST API + WebSocket
┌─────────────────────────────▼───────────────────────────────┐
│                    Backend (TO IMPLEMENT)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ AudioSequencer (main controller)                       │ │
│  │  - Load audio file                                     │ │
│  │  - Playback control (play/pause/stop/seek)            │ │
│  │  - Timeline management (splits → slots)               │ │
│  │  - Current position tracking (50ms monitoring)        │ │
│  │  - Trigger slot changes → Master playlist             │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ AudioTimeline (data model)                            │ │
│  │  - Splits: [0.0, 2.5, 4.0, 7.2, ...]                 │ │
│  │  - Slots: [{start:0.0, end:2.5, clip_idx:0}, ...]    │ │
│  │  - Clip mapping: {0: "video/intro.mp4", ...}         │ │
│  │  - Export/import JSON                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ AudioEngine (miniaudio wrapper)                       │ │
│  │  - Load audio file (MP3, WAV, OGG, FLAC)             │ │
│  │  - Play/pause/stop/seek                               │ │
│  │  - Get current position                               │ │
│  │  - Get duration                                       │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│              Sequencer Mode: Master/Slave System            │
│  - SEQUENCER MODE OFF: Normal playlist operation            │
│    • Master playlist controls slaves via Transport          │
│  - SEQUENCER MODE ON: Sequencer becomes master controller   │
│    • AudioSequencer drives timeline (MASTER)                │
│    • All playlists become SLAVES following sequencer        │
│    • Slot boundaries trigger playlist clip advances         │
│    • Each slot duration = time until next clip              │
│  - On slot boundary: advance all slave playlists to next    │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Backend Audio (3-4h)

### 1.1 File Structure

```
src/modules/
├── audio_sequencer.py       # Main controller (NEW)
├── audio_timeline.py         # Timeline/slot data model (NEW)
├── audio_engine.py           # miniaudio wrapper (NEW)
└── player_manager.py         # Update to integrate sequencer (MODIFY)

data/
└── sequencer/                # Sequencer data storage (NEW)
    ├── timeline.json         # Current timeline state
    └── audio/                # Uploaded audio files
        └── track_*.mp3
```

### 1.2 AudioEngine (src/modules/audio_engine.py)

**Purpose:** Thin wrapper around miniaudio for audio playback

**Dependencies:** `pip install miniaudio`

**Implementation:**

```python
import miniaudio
import threading
from pathlib import Path

class AudioEngine:
    """Manages audio file playback using miniaudio"""
    
    def __init__(self):
        self.device = miniaudio.PlaybackDevice()
        self.decoder = None
        self.current_position = 0.0  # seconds
        self.duration = 0.0
        self.is_playing = False
        self.is_loaded = False
        self._lock = threading.Lock()
        self._stream = None
        
    def load(self, file_path: str) -> dict:
        """Load audio file and return metadata"""
        try:
            self.decoder = miniaudio.decode_file(file_path)
            self.duration = self.decoder.num_frames / self.decoder.sample_rate
            self.is_loaded = True
            self.current_position = 0.0
            
            return {
                'duration': self.duration,
                'sample_rate': self.decoder.sample_rate,
                'channels': self.decoder.nchannels,
                'format': self.decoder.sample_format
            }
        except Exception as e:
            raise Exception(f"Failed to load audio: {e}")
    
    def play(self):
        """Start/resume playback"""
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        with self._lock:
            if not self.is_playing:
                self.is_playing = True
                self._start_stream()
    
    def pause(self):
        """Pause playback"""
        with self._lock:
            self.is_playing = False
            if self._stream:
                self._stream.stop()
    
    def stop(self):
        """Stop playback and reset position"""
        with self._lock:
            self.is_playing = False
            self.current_position = 0.0
            if self._stream:
                self._stream.stop()
                self._stream = None
    
    def seek(self, position: float):
        """Seek to position in seconds"""
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        position = max(0.0, min(position, self.duration))
        with self._lock:
            self.current_position = position
            # Reload decoder at new position
            if self.is_playing:
                self._restart_stream()
    
    def get_position(self) -> float:
        """Get current playback position in seconds"""
        with self._lock:
            return self.current_position
    
    def get_duration(self) -> float:
        """Get total duration in seconds"""
        return self.duration
    
    def _start_stream(self):
        """Internal: Start audio stream"""
        # Implementation uses miniaudio stream callback
        # Updates self.current_position in audio thread
        pass
    
    def _restart_stream(self):
        """Internal: Restart stream after seek"""
        if self._stream:
            self._stream.stop()
        self._start_stream()
```

**Key Points:**
- Thread-safe position tracking
- Support for MP3, WAV, OGG, FLAC via miniaudio
- Simple API: load → play/pause/stop/seek
- Returns duration for timeline creation

---

### 1.3 AudioTimeline (src/modules/audio_timeline.py)

**Purpose:** Manage splits, slots, and clip mappings

**Implementation:**

```python
from typing import List, Dict, Optional
import json
from pathlib import Path

class AudioTimeline:
    """Manages timeline splits and slot-to-clip mappings"""
    
    def __init__(self):
        self.audio_file: Optional[str] = None
        self.duration: float = 0.0
        self.splits: List[float] = []  # [2.5, 4.0, 7.2, ...]
        self.clip_mapping: Dict[int, str] = {}  # {0: "video/intro.mp4", ...}
        
    def load_audio(self, file_path: str, duration: float):
        """Initialize timeline with audio file"""
        self.audio_file = file_path
        self.duration = duration
        self.splits = []
        self.clip_mapping = {}
    
    def add_split(self, time: float) -> bool:
        """Add split point, return True if added"""
        if time <= 0.0 or time >= self.duration:
            return False
        
        # Don't add if too close to existing split (0.5s threshold)
        for split in self.splits:
            if abs(split - time) < 0.5:
                return False
        
        self.splits.append(time)
        self.splits.sort()
        return True
    
    def remove_split(self, time: float, threshold: float = 0.1) -> bool:
        """Remove split near given time"""
        for i, split in enumerate(self.splits):
            if abs(split - time) < threshold:
                self.splits.pop(i)
                return True
        return False
    
    def get_slots(self) -> List[Dict]:
        """Convert splits to slot list"""
        if not self.splits:
            return []
        
        points = [0.0] + self.splits + [self.duration]
        slots = []
        
        for i in range(len(points) - 1):
            slots.append({
                'index': i,
                'start': points[i],
                'end': points[i + 1],
                'duration': points[i + 1] - points[i],
                'clip_name': self.clip_mapping.get(i, f"Clip {i}")
            })
        
        return slots
    
    def get_current_slot(self, position: float) -> Optional[int]:
        """Get slot index at given position"""
        slots = self.get_slots()
        for slot in slots:
            if slot['start'] <= position < slot['end']:
                return slot['index']
        return None
    
    def set_clip_mapping(self, slot_index: int, clip_name: str):
        """Map slot to clip name"""
        self.clip_mapping[slot_index] = clip_name
    
    def to_dict(self) -> dict:
        """Export timeline to dict"""
        return {
            'audio_file': self.audio_file,
            'duration': self.duration,
            'splits': self.splits,
            'clip_mapping': self.clip_mapping,
            'slots': self.get_slots()
        }
    
    def from_dict(self, data: dict):
        """Import timeline from dict"""
        self.audio_file = data.get('audio_file')
        self.duration = data.get('duration', 0.0)
        self.splits = data.get('splits', [])
        self.clip_mapping = data.get('clip_mapping', {})
        # Convert string keys back to int
        self.clip_mapping = {int(k): v for k, v in self.clip_mapping.items()}
    
    def save(self, file_path: str):
        """Save timeline to JSON"""
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    def load(self, file_path: str):
        """Load timeline from JSON"""
        with open(file_path, 'r') as f:
            data = json.load(f)
            self.from_dict(data)
```

**Key Points:**
- Converts splits → slots automatically
- Handles clip mapping per slot
- Export/import JSON for persistence
- Validates split constraints (min distance, boundaries)

---

### 1.4 AudioSequencer (src/modules/audio_sequencer.py)

**Purpose:** Main controller that ties everything together

**Implementation:**

```python
import threading
import time
from typing import Optional, Callable
from .audio_engine import AudioEngine
from .audio_timeline import AudioTimeline

class AudioSequencer:
    """Main audio sequencer controller"""
    
    def __init__(self, player_manager):
        self.engine = AudioEngine()
        self.timeline = AudioTimeline()
        self.player_manager = player_manager
        
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_active = False
        self.current_slot_index: Optional[int] = None
        
        # Callbacks
        self.on_slot_change: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
    
    def load_audio(self, file_path: str) -> dict:
        """Load audio file and initialize timeline"""
        metadata = self.engine.load(file_path)
        self.timeline.load_audio(file_path, metadata['duration'])
        return {
            'duration': metadata['duration'],
            'sample_rate': metadata['sample_rate'],
            'audio_file': file_path
        }
    
    def play(self):
        """Start playback and monitoring"""
        self.engine.play()
        if not self.monitor_active:
            self._start_monitoring()
    
    def pause(self):
        """Pause playback"""
        self.engine.pause()
    
    def stop(self):
        """Stop playback and reset"""
        self.engine.stop()
        self._stop_monitoring()
        self.current_slot_index = None
    
    def seek(self, position: float):
        """Seek to position"""
        self.engine.seek(position)
    
    def get_position(self) -> float:
        """Get current position"""
        return self.engine.get_position()
    
    def add_split(self, time: float) -> bool:
        """Add split point to timeline"""
        return self.timeline.add_split(time)
    
    def remove_split(self, time: float) -> bool:
        """Remove split point"""
        return self.timeline.remove_split(time)
    
    def get_timeline_data(self) -> dict:
        """Get full timeline data"""
        return self.timeline.to_dict()
    
    def set_clip_mapping(self, slot_index: int, clip_name: str):
        """Map slot to clip"""
        self.timeline.set_clip_mapping(slot_index, clip_name)
    
    def _start_monitoring(self):
        """Start monitoring thread (50ms interval)"""
        self.monitor_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _stop_monitoring(self):
        """Stop monitoring thread"""
        self.monitor_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def _monitor_loop(self):
        """Monitoring loop - checks position every 50ms"""
        while self.monitor_active:
            try:
                position = self.engine.get_position()
                
                # Check for slot change
                current_slot = self.timeline.get_current_slot(position)
                if current_slot != self.current_slot_index:
                    self._handle_slot_change(current_slot)
                    self.current_slot_index = current_slot
                
                # Notify position update
                if self.on_position_update:
                    self.on_position_update(position, current_slot)
                
            except Exception as e:
                print(f"Monitor loop error: {e}")
            
            time.sleep(0.05)  # 50ms interval
    
    def _handle_slot_change(self, new_slot_index: Optional[int]):
        """Handle slot boundary crossing
        
        When sequencer mode is ON:
        - Sequencer is the MASTER timeline controller
        - All playlists are SLAVES following slot boundaries
        - Each slot advance triggers next clip in all slave playlists
        """
        if new_slot_index is None:
            return
        
        # Advance all slave playlists to next clip
        if self.player_manager:
            try:
                # Sequencer mode: advance ALL playlists (slaves) by one clip
                self.player_manager.sequencer_advance_slaves(new_slot_index)
            except Exception as e:
                print(f"Failed to advance slaves: {e}")
        
        # Call callback
        if self.on_slot_change:
            self.on_slot_change(new_slot_index)
```

**Key Points:**
- 50ms monitoring loop for responsive slot detection
- Integrates AudioEngine + AudioTimeline
- Triggers Master playlist changes on slot boundaries
- Thread-safe with daemon threads
- Callback system for UI updates

---

## Phase 3: Master Integration (3-4h)

### 3.1 PlayerManager Updates (src/modules/player_manager.py)

**Add sequencer integration:**

```python
class PlayerManager:
    def __init__(self):
        # ... existing code ...
        self.sequencer = None  # AudioSequencer instance
        self.sequencer_mode_active = False  # Track sequencer master mode
    
    def init_sequencer(self):
        """Initialize audio sequencer"""
        from .audio_sequencer import AudioSequencer
        self.sequencer = AudioSequencer(self)
        
        # Set up callbacks
        self.sequencer.on_slot_change = self._on_sequencer_slot_change
        self.sequencer.on_position_update = self._on_sequencer_position_update
    
    def set_sequencer_mode(self, enabled: bool):
        """Enable/disable sequencer mode
        
        When enabled:
        - Sequencer becomes MASTER timeline controller
        - All playlists become SLAVES following slot boundaries
        
        When disabled:
        - Normal Master/Slave operation via Transport
        """
        self.sequencer_mode_active = enabled
        
        # Broadcast mode change
        if self.socketio:
            self.socketio.emit('sequencer_mode_changed', {
                'enabled': enabled
            })
    
    def _on_sequencer_slot_change(self, slot_index: int):
        """Handle sequencer slot change"""
        # Sequencer mode drives slave playlists
        pass
    
    def _on_sequencer_position_update(self, position: float, slot_index: Optional[int]):
        """Broadcast position update to frontend"""
        if self.socketio:
            self.socketio.emit('sequencer_position', {
                'position': position,
                'slot_index': slot_index
            })
    
    def sequencer_advance_slaves(self, slot_index: int):
        """Advance all slave playlists to next clip
        
        Called when sequencer slot boundary is crossed.
        Sequencer is MASTER, all playlists are SLAVES.
        Each slot duration determines when to advance.
        
        Args:
            slot_index: Current slot index (0, 1, 2, ...)
        """
        if not self.sequencer_mode_active:
            return
        
        # Advance ALL playlists (they are all slaves to sequencer)
        for player_id, player in self.players.items():
            if player.playlist and len(player.playlist) > 0:
                # Advance to next clip in playlist
                next_index = (player.current_clip_index + 1) % len(player.playlist)
                player.current_clip_index = next_index
                player.play()
        
        # Broadcast to frontend
        if self.socketio:
            self.socketio.emit('sequencer_slot_advance', {
                'slot_index': slot_index,
                'timestamp': time.time()
            })
```

### 3.2 API Endpoints (src/main.py)

**Add sequencer REST API:**

```python
# Sequencer endpoints
@app.route('/api/sequencer/mode', methods=['POST'])
def sequencer_set_mode():
    """Enable/disable sequencer mode
    
    When enabled: Sequencer = MASTER, all playlists = SLAVES
    When disabled: Normal Master/Slave via Transport
    """
    data = request.json
    enabled = data.get('enabled', False)
    player_manager.set_sequencer_mode(enabled)
    return jsonify({'success': True, 'mode': 'master' if enabled else 'disabled'})

@app.route('/api/sequencer/upload', methods=['POST'])
def sequencer_upload_audio():
    """Upload audio file for sequencer
    
    Handles drag-and-drop file upload to backend.
    Saves to data/sequencer/audio/ directory.
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate audio file extension
        allowed_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        if not file.filename.lower().endswith(allowed_extensions):
            return jsonify({'error': 'Invalid file type. Allowed: MP3, WAV, OGG, FLAC, M4A, AAC'}), 400
        
        # Create sequencer audio directory
        from pathlib import Path
        audio_dir = Path('data/sequencer/audio')
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename
        import re
        safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
        
        # Save file
        file_path = audio_dir / safe_filename
        file.save(str(file_path))
        
        # Load into sequencer immediately
        metadata = player_manager.sequencer.load_audio(str(file_path))
        
        return jsonify({
            'success': True,
            'path': str(file_path),
            'filename': safe_filename,
            'metadata': metadata
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/sequencer/browse-audio', methods=['GET'])
def sequencer_browse_audio():
    """List available audio files in data/sequencer/audio/ and video/ folders
    
    Returns JSON with audio files for modal file browser.
    """
    try:
        from pathlib import Path
        import os
        
        audio_extensions = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')
        files = []
        
        # Scan data/sequencer/audio/
        sequencer_audio_dir = Path('data/sequencer/audio')
        if sequencer_audio_dir.exists():
            for file_path in sequencer_audio_dir.glob('*'):
                if file_path.suffix.lower() in audio_extensions:
                    files.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'folder': 'Sequencer Audio'
                    })
        
        # Scan video/ folder for music
        video_dir = Path('video')
        if video_dir.exists():
            for file_path in video_dir.rglob('*'):
                if file_path.suffix.lower() in audio_extensions:
                    rel_path = file_path.relative_to(video_dir)
                    files.append({
                        'filename': file_path.name,
                        'path': str(file_path),
                        'size': file_path.stat().st_size,
                        'folder': f'Video/{rel_path.parent}' if rel_path.parent != Path('.') else 'Video'
                    })
        
        return jsonify({
            'success': True,
            'files': sorted(files, key=lambda x: x['filename'])
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sequencer/load', methods=['POST'])
def sequencer_load_audio():
    """Load audio file into sequencer
    
    Expects file_path from server (not local path).
    Used by modal file browser.
    """
    data = request.json
    file_path = data.get('file_path')
    
    try:
        metadata = player_manager.sequencer.load_audio(file_path)
        return jsonify({'success': True, 'metadata': metadata})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/sequencer/audio/<path:file_path>', methods=['GET'])
def sequencer_serve_audio(file_path):
    """Serve audio file to frontend
    
    Allows WaveSurfer.js to load audio from server after upload.
    """
    from flask import send_file
    from pathlib import Path
    
    try:
        # Construct full path (security: only allow from data/sequencer/audio or video/)
        if file_path.startswith('data/sequencer/audio/'):
            full_path = Path(file_path)
        elif file_path.startswith('video/'):
            full_path = Path(file_path)
        else:
            return jsonify({'error': 'Invalid path'}), 403
        
        if not full_path.exists():
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            str(full_path),
            mimetype='audio/mpeg',  # Will auto-detect based on extension
            as_attachment=False
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sequencer/play', methods=['POST'])
def sequencer_play():
    """Start sequencer playback"""
    player_manager.sequencer.play()
    return jsonify({'success': True})

@app.route('/api/sequencer/pause', methods=['POST'])
def sequencer_pause():
    """Pause sequencer playback"""
    player_manager.sequencer.pause()
    return jsonify({'success': True})

@app.route('/api/sequencer/stop', methods=['POST'])
def sequencer_stop():
    """Stop sequencer playback"""
    player_manager.sequencer.stop()
    return jsonify({'success': True})

@app.route('/api/sequencer/seek', methods=['POST'])
def sequencer_seek():
    """Seek to position"""
    data = request.json
    position = data.get('position', 0.0)
    player_manager.sequencer.seek(position)
    return jsonify({'success': True})

@app.route('/api/sequencer/split/add', methods=['POST'])
def sequencer_add_split():
    """Add split point"""
    data = request.json
    time = data.get('time')
    success = player_manager.sequencer.add_split(time)
    return jsonify({'success': success})

@app.route('/api/sequencer/split/remove', methods=['POST'])
def sequencer_remove_split():
    """Remove split point"""
    data = request.json
    time = data.get('time')
    success = player_manager.sequencer.remove_split(time)
    return jsonify({'success': success})

@app.route('/api/sequencer/timeline', methods=['GET'])
def sequencer_get_timeline():
    """Get timeline data"""
    timeline = player_manager.sequencer.get_timeline_data()
    return jsonify(timeline)

@app.route('/api/sequencer/clip-mapping', methods=['POST'])
def sequencer_set_clip_mapping():
    """Map slot to clip"""
    data = request.json
    slot_index = data.get('slot_index')
    clip_name = data.get('clip_name')
    player_manager.sequencer.set_clip_mapping(slot_index, clip_name)
    return jsonify({'success': True})

@app.route('/api/sequencer/save', methods=['POST'])
def sequencer_save_timeline():
    """Save timeline to file"""
    data = request.json
    file_path = data.get('file_path', 'data/sequencer/timeline.json')
    player_manager.sequencer.timeline.save(file_path)
    return jsonify({'success': True})

@app.route('/api/sequencer/load-timeline', methods=['POST'])
def sequencer_load_timeline():
    """Load timeline from file"""
    data = request.json
    file_path = data.get('file_path', 'data/sequencer/timeline.json')
    player_manager.sequencer.timeline.load(file_path)
    return jsonify({'success': True, 'timeline': player_manager.sequencer.get_timeline_data()})
```

---

## Session State Storage

### Where Sequencer Data is Stored

**1. Session State File: `session_state.json`** (Auto-saved on every change)

```json
{
  "last_updated": "2025-12-17T10:30:45.123456",
  "players": {
    "video": { ... },
    "artnet": { ... }
  },
  "sequencer": {
    "mode_active": false,
    "audio_file": "data/sequencer/audio/track_123.mp3",
    "timeline": {
      "duration": 180.5,
      "splits": [2.5, 4.0, 7.2, 12.0],
      "clip_mapping": {
        "0": "video/intro.mp4",
        "1": "video/main.mp4",
        "2": "video/outro.mp4"
      }
    },
    "last_position": 5.3
  }
}
```

---

## Implementation Checklist

### Phase 1: Backend Audio (3-4h)

- [ ] **Install dependencies (5 min)**
  - `pip install miniaudio`
  
- [ ] **Create AudioEngine (1-1.5h)**
  - Implement load/play/pause/stop/seek
  - Thread-safe position tracking
  - Test with MP3, WAV files
  
- [ ] **Create AudioTimeline (1h)**
  - Split management (add/remove/validate)
  - Slot generation
  - Clip mapping
  - JSON export/import
  
- [ ] **Create AudioSequencer (1-1.5h)**
  - Wire AudioEngine + AudioTimeline
  - Implement monitoring loop (50ms)
  - Add callbacks for slot changes
  - Test slot detection accuracy

### Phase 3: Master Integration (3-4h)

- [ ] **Update PlayerManager (1h)**
  - Add sequencer initialization
  - Implement `sequencer_advance_slaves()`
  - Implement `set_sequencer_mode(enabled)`
  - Wire slot change callbacks
  - Test Master/Slave sync
  
- [ ] **Update SessionStateManager (30min)**
  - Modify `save()` to include sequencer state in session_state.json
  - Modify `restore()` to reload sequencer timeline on restart
  - Save: audio_file, splits, clip_mapping, mode_active, last_position
  - Restore: Load audio, restore splits, restore clip mappings, restore mode

- [ ] **Update Playlist Save/Load (30min)**
  - Modify `/api/playlist/save` to include sequencer state in JSON
  - Modify `/api/playlist/load` to restore sequencer from saved data
  - Save: audio_file, timeline (splits, clip_mapping), mode_active
  - Restore: Load audio, restore splits/mappings, restore mode
  
- [ ] **Update Snapshot Save/Restore (30min)**
  - Modify snapshot creation to include sequencer state
  - Modify snapshot restore to reload sequencer settings
  - Same data as playlist: audio_file, timeline, mode_active
  
- [ ] **Add REST API endpoints (1-1.5h)**
  - Sequencer mode: `/api/sequencer/mode` (enable/disable master mode)
  - Upload audio: `/api/sequencer/upload` (drag-and-drop file upload)
  - Browse audio: `/api/sequencer/browse-audio` (list server audio files)
  - Load audio: `/api/sequencer/load` (load from server path)
  - Playback: `/api/sequencer/{play,pause,stop,seek}`
  - Splits: `/api/sequencer/split/{add,remove}`
  - Timeline: `/api/sequencer/timeline`
  - Clip mapping: `/api/sequencer/clip-mapping`
  
- [ ] **Add WebSocket events (0.5h)**
  - Broadcast position updates
  - Broadcast slot changes
  
- [ ] **Frontend Integration (1-1.5h)**
  - Wire `toggleSequencerMode()` in player.html:
    - Call `/api/sequencer/mode` with enabled=true/false
    - Show/hide waveform section
    - Update button text: "Sequencer: MASTER" / "Sequencer Mode"
  - Update `waveform-analyzer.js`:
    - **Drag-and-drop**: Upload file via `/api/sequencer/upload` FormData
    - **Browse button**: Open modal, fetch files via `/api/sequencer/browse-audio`
    - **Modal**: Display files in table/grid, click to load via `/api/sequencer/load`
    - Call `/api/sequencer/{play,pause,stop}` on button clicks
    - Call `/api/sequencer/split/add` on waveform click
    - Call `/api/sequencer/split/remove` on region right-click
    - Listen to WebSocket for position updates and slot advances
  - Create file browser modal component:
    - Bootstrap modal with file list/grid
    - Filter by folder (Sequencer Audio / Video)
    - Display filename, size, folder
    - Click to load, double-click to load and close
  - Test end-to-end workflow

---

## Testing Plan

### Unit Tests
```python
# tests/test_audio_timeline.py
def test_add_split():
    timeline = AudioTimeline()
    timeline.load_audio("test.mp3", 10.0)
    assert timeline.add_split(5.0) == True
    assert len(timeline.splits) == 1
    assert timeline.add_split(5.1) == False  # Too close

def test_get_slots():
    timeline = AudioTimeline()
    timeline.load_audio("test.mp3", 10.0)
    timeline.add_split(3.0)
    timeline.add_split(7.0)
    slots = timeline.get_slots()
    assert len(slots) == 3
    assert slots[0] == {'index': 0, 'start': 0.0, 'end': 3.0, ...}
```

### Integration Tests
```python
# tests/test_audio_sequencer.py
def test_slot_detection():
    sequencer = AudioSequencer(None)
    sequencer.load_audio("test.mp3")
    sequencer.add_split(2.5)
    sequencer.engine.seek(2.6)
    # Verify current_slot_index changes
```

### Complete Data Flow Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. FILE SELECTION (Frontend)                                        │
│    - Drag-and-drop: Upload to /api/sequencer/upload                │
│    - Browse button: Open modal → /api/sequencer/browse-audio       │
│                     → Select file → /api/sequencer/load            │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 2. BACKEND LOADS AUDIO (AudioEngine)                                │
│    - Load file via miniaudio                                        │
│    - Extract metadata: duration, sample_rate, channels             │
│    - Initialize AudioTimeline with duration                         │
│    - Return metadata to frontend                                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 3. FRONTEND VISUALIZES (WaveSurfer.js)                             │
│    - Fetch audio: GET /api/sequencer/audio/<path>                  │
│    - WaveSurfer.load(audioUrl) → display waveform                  │
│    - Enable user interaction (click to split)                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 4. USER CREATES SPLITS (Frontend → Backend)                        │
│    - User clicks waveform at time T                                │
│    - Frontend: POST /api/sequencer/split/add { time: T }          │
│    - Backend: AudioTimeline.add_split(T)                           │
│    - Backend: Validates (min distance, boundaries)                 │
│    - Backend: Sorts splits array                                   │
│    - Backend: Recalculates slots from splits                       │
│    - Backend: Returns success                                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 5. FRONTEND FETCHES SLOTS (Backend → Frontend)                     │
│    - Frontend: GET /api/sequencer/timeline                         │
│    - Backend: Returns AudioTimeline.to_dict()                      │
│      {                                                              │
│        splits: [2.5, 4.0, 7.2],                                    │
│        slots: [                                                     │
│          {index: 0, start: 0.0, end: 2.5, duration: 2.5},         │
│          {index: 1, start: 2.5, end: 4.0, duration: 1.5},         │
│          {index: 2, start: 4.0, end: 7.2, duration: 3.2}          │
│        ]                                                            │
│      }                                                              │
│    - Frontend: Renders slot divs with times                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│ 6. PLAYBACK & MONITORING (50ms loop)                               │
│    - Backend: AudioSequencer monitors position                     │
│    - Backend: Detects slot boundary crossing                       │
│    - Backend: Calls player_manager.sequencer_advance_slaves()     │
│    - Backend: WebSocket → 'sequencer_position' event              │
│    - Frontend: Updates UI highlighting                             │
└─────────────────────────────────────────────────────────────────────┘
```

### Manual Testing Workflow
1. **Drag-and-drop upload**: Drag MP3 file to preview area, verify upload and load
2. **Browse button**: Click Browse, verify modal shows server audio files
3. **Modal selection**: Click file in modal, verify it loads
4. **Waveform loads**: Verify WaveSurfer displays audio waveform
5. **Click waveform**: Add split at 3.5s → verify POST /api/sequencer/split/add
6. **Fetch slots**: Verify GET /api/sequencer/timeline returns slot data
7. **Slots display**: Verify slot divs show start/end/duration times
8. Click Play
9. Verify position updates in real-time (WebSocket)
10. Verify slot highlighting changes as playback progresses
11. **Sequencer Mode ON**: Verify all playlists advance on slot boundaries
12. Test pause/resume
13. Test seek
14. **Remove split**: Right-click region → verify POST /api/sequencer/split/remove
15. Save/load timeline

---

## Error Handling

### Audio Loading Errors
```python
try:
    metadata = sequencer.load_audio(file_path)
except FileNotFoundError:
    return jsonify({'error': 'Audio file not found'}), 404
except Exception as e:
    return jsonify({'error': f'Failed to load audio: {e}'}), 400
```

### Playback Errors
- Graceful handling if audio device not available
- Fallback to software decoding if hardware fails
- User notification via WebSocket

### Synchronization Edge Cases
- Handle Master playlist empty
- Handle clip not found in playlist
- Handle rapid slot changes (< 50ms)

---

## Performance Considerations

### Monitoring Loop
- 50ms interval = 20 updates/sec (responsive)
- Minimal CPU overhead (<1%)
- Daemon thread auto-cleans on exit

### Audio Decoding
- miniaudio handles decoding efficiently
- Supports streaming (no full load to RAM)
- Low latency (<10ms)

### Slot Detection
- O(n) complexity where n = number of slots
- Typically n < 50, so negligible
- Could optimize with binary search if needed

---

## Frontend Implementation Details

### Drag-and-Drop Upload (waveform-analyzer.js)

```javascript
// Update existing drag-and-drop handlers
const previewArea = document.getElementById('preview-area-waveform');

previewArea.addEventListener('drop', async (e) => {
    e.preventDefault();
    previewArea.classList.remove('drag-over');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        const file = files[0];
        
        // Validate audio file
        const validExtensions = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'];
        const extension = file.name.split('.').pop().toLowerCase();
        if (!validExtensions.includes(extension)) {
            alert('Invalid file type. Please upload MP3, WAV, OGG, FLAC, M4A, or AAC.');
            return;
        }
        
        // Upload file to backend
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/sequencer/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log('Audio uploaded:', result.metadata);
                // WaveSurfer will auto-load from backend
                await loadAudioFromServer(result.path);
            } else {
                alert('Upload failed: ' + result.error);
            }
        } catch (error) {
            console.error('Upload error:', error);
            alert('Failed to upload audio file');
        }
    }
});

async function loadAudioFromServer(serverPath) {
    // Load audio via backend sequencer
    // Backend will serve audio via sequencer endpoint
    const audioUrl = `/api/sequencer/audio/${encodeURIComponent(serverPath)}`;
    await wavesurfer.load(audioUrl);
    
    // After loading, fetch initial timeline (may have saved splits)
    await fetchAndRenderTimeline();
}
```

### Split Management (waveform-analyzer.js)

```javascript
// CRITICAL: Push splits to backend immediately when created

// User clicks waveform to add split
wavesurfer.on('interaction', async (time) => {
    // Add split to backend
    await addSplitToBackend(time);
});

async function addSplitToBackend(time) {
    try {
        const response = await fetch('/api/sequencer/split/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time: time })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`Split added at ${time}s`);
            
            // Fetch updated timeline with recalculated slots
            await fetchAndRenderTimeline();
        } else {
            console.warn('Split not added (too close to existing split or boundary)');
        }
    } catch (error) {
        console.error('Error adding split:', error);
    }
}

// User right-clicks region to remove split
wavesurfer.on('region-clicked', async (region, event) => {
    if (event.button === 2) {  // Right-click
        event.preventDefault();
        
        // Remove split from backend
        await removeSplitFromBackend(region.start);
    }
});

async function removeSplitFromBackend(time) {
    try {
        const response = await fetch('/api/sequencer/split/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time: time })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`Split removed at ${time}s`);
            
            // Fetch updated timeline with recalculated slots
            await fetchAndRenderTimeline();
        } else {
            console.warn('Split not found');
        }
    } catch (error) {
        console.error('Error removing split:', error);
    }
}

// Fetch timeline data and render slots
async function fetchAndRenderTimeline() {
    try {
        const response = await fetch('/api/sequencer/timeline');
        const timeline = await response.json();
        
        if (timeline.splits) {
            // Update WaveSurfer regions to match backend splits
            updateWaveSurferRegions(timeline.splits);
            
            // Render slots with start/end/duration
            renderSlots(timeline.slots);
            
            console.log('Timeline updated:', timeline);
        }
    } catch (error) {
        console.error('Error fetching timeline:', error);
    }
}

function updateWaveSurferRegions(splits) {
    // Clear existing regions
    wavesurfer.clearRegions();
    
    // Add regions from backend splits
    // (regions are visual markers on waveform)
    splits.forEach((splitTime, index) => {
        wavesurfer.addRegion({
            start: splitTime,
            end: splitTime + 0.1,  // Thin marker
            color: 'rgba(255, 0, 0, 0.3)',
            drag: false,
            resize: false
        });
    });
}

function renderSlots(slots) {
    const slotsContainer = document.getElementById('slots-container-waveform');
    slotsContainer.innerHTML = '';
    
    slots.forEach((slot, index) => {
        // Slot div
        const slotDiv = document.createElement('div');
        slotDiv.className = 'slot-item';
        slotDiv.dataset.slotIndex = slot.index;
        
        slotDiv.innerHTML = `
            <div class="slot-header">
                <span class="slot-number">${slot.index + 1}</span>
                <span class="slot-time">${formatTime(slot.start)} - ${formatTime(slot.end)}</span>
            </div>
            <div class="slot-duration">${formatTime(slot.duration)}</div>
            <div class="slot-clip">${slot.clip_name}</div>
        `;
        
        slotsContainer.appendChild(slotDiv);
        
        // Add invisible spacer between slots
        if (index < slots.length - 1) {
            const spacer = document.createElement('div');
            spacer.className = 'slot-spacer';
            slotsContainer.appendChild(spacer);
        }
    });
}
```

### File Browser Modal (player.html)

```html
<!-- Audio File Browser Modal -->
<div class="modal fade" id="sequencerFileBrowserModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content bg-dark text-light">
            <div class="modal-header border-secondary">
                <h5 class="modal-title">Select Audio File</h5>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Search/Filter -->
                <div class="mb-3">
                    <input type="text" class="form-control bg-dark text-light border-secondary" 
                           id="sequencerFileSearch" placeholder="Search files...">
                </div>
                
                <!-- File List -->
                <div class="table-responsive" style="max-height: 400px; overflow-y: auto;">
                    <table class="table table-dark table-hover">
                        <thead class="sticky-top bg-dark">
                            <tr>
                                <th>Filename</th>
                                <th>Folder</th>
                                <th>Size</th>
                            </tr>
                        </thead>
                        <tbody id="sequencerFileList">
                            <!-- Populated via JS -->
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
```

### Modal JavaScript (waveform-analyzer.js)

```javascript
// Browse button handler
document.getElementById('browse-btn-waveform').addEventListener('click', async () => {
    await openFileBrowserModal();
});

async function openFileBrowserModal() {
    try {
        const response = await fetch('/api/sequencer/browse-audio');
        const result = await response.json();
        
        if (result.success) {
            renderFileList(result.files);
            const modal = new bootstrap.Modal(document.getElementById('sequencerFileBrowserModal'));
            modal.show();
        } else {
            alert('Failed to load audio files: ' + result.error);
        }
    } catch (error) {
        console.error('Error loading file list:', error);
    }
}

function renderFileList(files) {
    const tbody = document.getElementById('sequencerFileList');
    tbody.innerHTML = '';
    
    files.forEach(file => {
        const row = document.createElement('tr');
        row.style.cursor = 'pointer';
        row.innerHTML = `
            <td>${file.filename}</td>
            <td><small class="text-muted">${file.folder}</small></td>
            <td><small class="text-muted">${formatBytes(file.size)}</small></td>
        `;
        
        row.addEventListener('click', () => selectAudioFile(file.path));
        tbody.appendChild(row);
    });
}

async function selectAudioFile(filePath) {
    try {
        const response = await fetch('/api/sequencer/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: filePath })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('Audio loaded:', result.metadata);
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('sequencerFileBrowserModal'));
            modal.hide();
            
            // Load into WaveSurfer
            await loadAudioFromServer(filePath);
        } else {
            alert('Failed to load audio: ' + result.error);
        }
    } catch (error) {
        console.error('Error loading audio:', error);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Search filter
document.getElementById('sequencerFileSearch').addEventListener('input', (e) => {
    const searchTerm = e.target.value.toLowerCase();
    const rows = document.querySelectorAll('#sequencerFileList tr');
    
    rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(searchTerm) ? '' : 'none';
    });
});
```

---

## Next Steps After Phase 1 & 3

1. **Phase 4: UI Polish (2-3h)**
   - Beat markers (optional)
   - Export/import timeline UI
   - Visual feedback improvements
   - BPM detection display
   
2. **Extended Features**
   - Loop slots (repeat slot N times before advancing)
   - Slot transitions (fade between slots)
   - MIDI triggering (jump to slot on MIDI note)
   - Timeline zoom/pan for long tracks

---

## File Summary

**New Files:**
- `src/modules/audio_engine.py` (~150 lines)
- `src/modules/audio_timeline.py` (~120 lines)
- `src/modules/audio_sequencer.py` (~150 lines)

**Modified Files:**
- `src/modules/player_manager.py` (+80 lines: sequencer init, mode toggle, slave advance)
- `src/modules/session_state.py` (+40 lines: save/restore sequencer state)
- `src/modules/api_player_unified.py` (+60 lines: playlist save/load with sequencer)
- `src/modules/api_session.py` (+40 lines: snapshot save/restore with sequencer)
- `src/main.py` (+180 lines API endpoints: mode, upload, browse, load, playback, splits, timeline, clip-mapping, save, load-timeline)
- `frontend/js/waveform-analyzer.js` (+180 lines: API integration, drag-and-drop upload, modal file browser, split management)
- `frontend/player.html` (+80 lines: file browser modal HTML)
- `frontend/css/player.css` (+40 lines: modal styling)

**Total:** ~1120 lines of new code

---

## Timeline Estimate

| Task | Time | Dependencies |
|------|------|--------------|
| AudioEngine implementation | 1-1.5h | miniaudio install |
| AudioTimeline implementation | 1h | - |
| SessionStateManager integration | 30min | AudioSequencer |
| Playlist save/load integration | 30min | AudioSequencer |
| Snapshot save/restore integration | 30min | AudioSequencer |
| REST API endpoints | 1-1.5h | All backend |
| Frontend API wiring | 1-1.5h | REST API |
| Testing & debugging | 1-2h | All |
| **TOTAL** | **9-12| 1-1.5h | REST API |
| Testing & debugging | 1-2h | All |
| **TOTAL** | **7.5-10h** | |

**Recommended:** Split into 2 sessions:
1. **Session 1 (3-4h):** Backend audio (AudioEngine, AudioTimeline, AudioSequencer)
2. **Session 2 (4-6h):** Integration (PlayerManager, API, Frontend, Testing)

**2. Standalone Timeline File: `data/sequencer/timeline.json`** (Manual save/load)

```json
{
  "audio_file": "data/sequencer/audio/track_123.mp3",
  "duration": 180.5,
  "splits": [2.5, 4.0, 7.2, 12.0],
  "clip_mapping": {
    "0": "video/intro.mp4",
    "1": "video/main.mp4",
    "2": "video/outro.mp4"
  },
  "slots": [
    {
      "index": 0,
      "start": 0.0,
      "end": 2.5,
      "duration": 2.5,
      "clip_name": "video/intro.mp4"
    },
    {
      "index": 1,
      "start": 2.5,
      "end": 4.0,
      "duration": 1.5,
      "clip_name": "video/main.mp4"
    },
    {
      "index": 2,
      "start": 4.0,
      "end": 7.2,
      "duration": 3.2,
      "clip_name": "video/outro.mp4"
    }
  ]
}
```

### Playlist Save/Load Integration (api_player_unified.py)

**IMPORTANT:** Sequencer settings must be saved with playlists so users can restore complete show setups.

**Modified `/api/playlist/save` endpoint:**

```python
@app.route('/api/playlist/save', methods=['POST'])
def save_playlist():
    """Save both playlists + Sequencer settings."""
    try:
        import json
        data = request.get_json()
        
        name = data.get('name')
        video_playlist = data.get('video_playlist', [])
        artnet_playlist = data.get('artnet_playlist', [])
        
        if not name:
            return jsonify({"success": False, "message": "Name required"}), 400
        
        # Get sequencer state
        sequencer_state = None
        if player_manager.sequencer:
            sequencer_state = {
                "mode_active": player_manager.sequencer_mode_active,
                "audio_file": player_manager.sequencer.timeline.audio_file,
                "timeline": player_manager.sequencer.timeline.to_dict()
                # to_dict() includes: duration, splits, clip_mapping
            }
        
        # Save combined playlist as JSON
        playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
        os.makedirs(playlists_dir, exist_ok=True)
        
        playlist_path = os.path.join(playlists_dir, f'{name}.json')
        with open(playlist_path, 'w', encoding='utf-8') as f:
            json.dump({
                'video_playlist': video_playlist,
                'artnet_playlist': artnet_playlist,
                'sequencer': sequencer_state,  # Include sequencer settings
                'created': datetime.now().isoformat()
            }, f, indent=2)
        
        logger.info(f"💾 Playlists saved: {name} (Video: {len(video_playlist)}, Art-Net: {len(artnet_playlist)}, Sequencer: {'Yes' if sequencer_state else 'No'})")
        return jsonify({
            "success": True,
            "message": f"Playlists '{name}' saved",
            "video_count": len(video_playlist),
            "artnet_count": len(artnet_playlist),
            "has_sequencer": sequencer_state is not None
        })
    except Exception as e:
        logger.error(f"Error saving playlists: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
```

**Modified `/api/playlist/load` endpoint:**

```python
@app.route('/api/playlist/load/<name>', methods=['GET'])
def load_playlist(name):
    """Load saved playlist + Sequencer settings."""
    try:
        import json
        
        playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
        playlist_path = os.path.join(playlists_dir, f'{name}.json')
        
        if not os.path.exists(playlist_path):
            return jsonify({"success": False, "message": f"Playlist '{name}' not found"}), 404
        
        with open(playlist_path, 'r', encoding='utf-8') as f:
            playlist_data = json.load(f)
        
        # Restore sequencer if included
        sequencer_data = playlist_data.get('sequencer')
        if sequencer_data and player_manager.sequencer:
            # Restore audio file
            audio_file = sequencer_data.get('audio_file')
            if audio_file and os.path.exists(audio_file):
                player_manager.sequencer.load_audio(audio_file)
                
                # Restore timeline (splits, clip_mapping)
                timeline_data = sequencer_data.get('timeline', {})
                player_manager.sequencer.timeline.from_dict(timeline_data)
                
                # Restore sequencer mode
                mode_active = sequencer_data.get('mode_active', False)
                player_manager.set_sequencer_mode(mode_active)
                
                logger.info(f"🎵 Sequencer restored from playlist: audio={audio_file}, splits={len(timeline_data.get('splits', []))}")
        
        logger.info(f"📂 Playlist loaded: {name}")
        return jsonify({
            "success": True,
            "name": name,
            "video_playlist": playlist_data.get('video_playlist', []),
            "artnet_playlist": playlist_data.get('artnet_playlist', []),
            "sequencer": sequencer_data,  # Send sequencer data to frontend
            "created": playlist_data.get('created'),
        })
    except Exception as e:
        logger.error(f"Error loading playlist: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
```

**Frontend Integration (player.js):**

```javascript
// Modify savePlaylists() to include sequencer state
window.savePlaylists = async function() {
    const name = prompt('Playlist Name:', `playlist_${new Date().toISOString().slice(0, 10)}`);
    if (!name) return;
    
    try {
        // Get sequencer state from frontend
        const sequencerState = window.waveformAnalyzer ? {
            mode_active: window.sequencerModeActive || false,
            audio_file: window.currentSequencerAudioFile || null,
            timeline: window.currentSequencerTimeline || null
        } : null;
        
        const response = await fetch(`${API_BASE}/api/playlist/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                video_playlist: videoFiles,
                artnet_playlist: artnetFiles,
                sequencer: sequencerState  // Include sequencer
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`Playlists "${name}" saved (Video: ${data.video_count}, Art-Net: ${data.artnet_count}, Sequencer: ${data.has_sequencer ? 'Yes' : 'No'})`, 'success');
        } else {
            showToast(data.message || 'Save failed', 'error');
        }
    } catch (error) {
        console.error('❌ Error saving playlists:', error);
        showToast('Error saving playlists', 'error');
    }
};

// Modify loadPlaylists() to restore sequencer state
window.loadPlaylists = async function() {
    // ... existing modal code ...
    
    // When user selects a playlist:
    const response = await fetch(`${API_BASE}/api/playlist/load/${playlistName}`);
    const data = await response.json();
    
    if (data.success) {
        // Load playlists (existing code)
        videoFiles = data.video_playlist;
        artnetFiles = data.artnet_playlist;
        
        // Restore sequencer if included
        if (data.sequencer && window.waveformAnalyzer) {
            const seq = data.sequencer;
            
            // Load audio file into WaveSurfer
            if (seq.audio_file) {
                await window.waveformAnalyzer.loadAudioFromServer(seq.audio_file);
            }
            
            // Restore timeline (splits will be rendered)
            if (seq.timeline) {
                window.currentSequencerTimeline = seq.timeline;
                await window.waveformAnalyzer.fetchAndRenderTimeline();
            }
            
            // Restore sequencer mode
            if (seq.mode_active) {
                await toggleSequencerMode(); // Enable master mode
            }
            
            console.log('🎵 Sequencer restored from playlist');
        }
        
        showToast(`Playlist "${playlistName}" loaded`, 'success');
    }
};
```

---

### Snapshot Integration (api_session.py)

**Snapshots automatically include sequencer state** because they copy `session_state.json`.

**No additional changes needed** - just ensure `SessionStateManager.save()` includes sequencer data.

**Modified `/api/session/snapshot` endpoint** (for clarity):

```python
@app.route('/api/session/snapshot', methods=['POST'])
def create_snapshot():
    """Create a snapshot of current session state (includes sequencer)."""
    try:
        data = request.get_json() or {}
        
        # Generate filename with timestamp: YYYYMMDD_HHMMSS_snap.json
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_snap.json"
        
        snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
        
        # Force save current state (includes sequencer if active)
        session_state_manager.save(
            player_manager=app.flux_player_manager,
            clip_registry=app.flux_clip_registry,
            force=True
        )
        
        # Copy session_state.json to snapshots directory
        session_state_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), '..', 'session_state.json'
        )
        
        if not os.path.exists(session_state_path):
            return jsonify({
                "success": False,
                "error": "No session state found to snapshot"
            }), 404
        
        shutil.copy2(session_state_path, snapshot_path)
        
        # Get file info
        file_size = os.path.getsize(snapshot_path)
        
        logger.info(f"📸 Snapshot created: {filename} ({file_size} bytes)")
        
        return jsonify({
            "success": True,
            "message": f"Snapshot '{filename}' created",
            "filename": filename,
            "size": file_size
        })
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**Modified `/api/session/snapshot/restore` endpoint:**

```python
@app.route('/api/session/snapshot/restore', methods=['POST'])
def restore_snapshot():
    """Restore a snapshot including sequencer state."""
    try:
        data = request.get_json()
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"success": False, "error": "No filename provided"}), 400
        
        snapshot_path = os.path.join(SNAPSHOTS_DIR, filename)
        
        if not os.path.exists(snapshot_path):
            return jsonify({"success": False, "error": f"Snapshot '{filename}' not found"}), 404
        
        # Copy snapshot to session_state.json
        session_state_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), '..', 'session_state.json'
        )
        
        shutil.copy2(snapshot_path, session_state_path)
        
        # Reload session state (includes sequencer)
        session_state_manager._state = session_state_manager._load_or_create()
        session_state_manager.restore(
            player_manager=app.flux_player_manager,
            clip_registry=app.flux_clip_registry,
            config=app.flux_config
        )
        
        logger.info(f"🔄 Snapshot restored: {filename} (sequencer included)")
        
        return jsonify({
            "success": True,
            "message": f"Snapshot '{filename}' restored. Reload page to apply.",
            "filename": filename,
            "requires_reload": True
        })
        
    except Exception as e:
        logger.error(f"Error restoring snapshot: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

### Session State Integration (session_state.py)

**Modifications to SessionStateManager:**

```python
def save(self, player_manager, clip_registry, force: bool = False) -> bool:
    """Save player + sequencer state"""
    # ... existing player save code ...
    
    # Add sequencer state
    if player_manager.sequencer:
        state["sequencer"] = {
            "mode_active": player_manager.sequencer_mode_active,
            "audio_file": player_manager.sequencer.timeline.audio_file,
            "timeline": player_manager.sequencer.timeline.to_dict(),
            "last_position": player_manager.sequencer.get_position()
        }
    
    # ... write to session_state.json ...

def restore(self, player_manager, clip_registry, config) -> bool:
    """Restore player + sequencer state"""
    # ... existing player restore code ...
    
    # Restore sequencer state
    sequencer_state = state.get('sequencer')
    if sequencer_state and player_manager.sequencer:
        mode_active = sequencer_state.get('mode_active', False)
        audio_file = sequencer_state.get('audio_file')
        timeline_data = sequencer_state.get('timeline', {})
        last_position = sequencer_state.get('last_position', 0.0)
        
        # Restore audio file
        if audio_file and os.path.exists(audio_file):
            player_manager.sequencer.load_audio(audio_file)
            
            # Restore timeline (splits + clip mapping)
            player_manager.sequencer.timeline.from_dict(timeline_data)
            
            # Restore sequencer mode
            player_manager.set_sequencer_mode(mode_active)
            
            # Restore playback position (optional)
            if last_position > 0:
                player_manager.sequencer.seek(last_position)
    
    # ... rest of restore code ...
```

### Directory Structure

```
project_root/
├── session_state.json              # Auto-saved (sequencer state included)
├── data/
│   └── sequencer/
│       ├── timeline.json           # Manual save/load (current timeline)
│       └── audio/                  # Uploaded audio files
│           ├── track_001.mp3
│           ├── track_002.wav
│           └── ...
├── projects/                       # Named project saves (optional)
│   ├── project1_20251217.json     # Could include sequencer timeline
│   └── ...
```

### Auto-Save Behavior

**When session_state.json is updated:**
- Every playlist change (add/remove clip)
- Every split add/remove
- Sequencer mode toggle
- Clip mapping changes
- Every 500ms minimum (debounced)

**On application restart:**
- Loads session_state.json automatically
- Restores sequencer audio file
- Restores timeline splits
- Restores clip mappings
- Restores sequencer mode state
- Resumes at last playback position (optional)

---

## Workflow Summary: Frontend ↔ Backend Data Flow

### ✅ Complete Bidirectional Communication

**Frontend → Backend (User Actions):**
1. **Upload File**: `FormData` → `POST /api/sequencer/upload` → saves to disk, loads into AudioEngine
2. **Browse Files**: Click Browse → `GET /api/sequencer/browse-audio` → displays modal
3. **Select File**: Click file in modal → `POST /api/sequencer/load` → loads into AudioEngine
4. **Add Split**: Click waveform → `POST /api/sequencer/split/add {time: T}` → AudioTimeline stores split
5. **Remove Split**: Right-click region → `POST /api/sequencer/split/remove {time: T}` → AudioTimeline removes split

**Backend → Frontend (Data Flow):**
1. **Audio Metadata**: Upload/Load → returns `{duration, sample_rate, channels}`
2. **Audio Stream**: WaveSurfer → `GET /api/sequencer/audio/<path>` → plays audio
3. **Timeline Data**: After split change → `GET /api/sequencer/timeline` → returns:
   ```json
   {
     "splits": [2.5, 4.0, 7.2],
     "slots": [
       {"index": 0, "start": 0.0, "end": 2.5, "duration": 2.5},
       {"index": 1, "start": 2.5, "end": 4.0, "duration": 1.5},
       {"index": 2, "start": 4.0, "end": 7.2, "duration": 3.2}
     ]
   }
   ```
4. **Position Updates**: During playback → WebSocket `sequencer_position` → `{position, slot_index}`
5. **Slot Changes**: Slot boundary crossed → WebSocket `sequencer_slot_advance` → `{slot_index, timestamp}`

**Key Design Principle:**
- Backend is **source of truth** for timeline data (splits, slots, durations)
- Frontend **never** calculates slot boundaries - always fetches from `/api/sequencer/timeline`
- Immediate sync: Every user action (add/remove split) triggers backend update + frontend refresh

---

*Implementation Plan Created: December 17, 2025*
*Last Updated: December 17, 2025 - Added complete workflow documentation*
