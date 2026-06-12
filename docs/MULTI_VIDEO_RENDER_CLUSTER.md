# Multi-Video Render Cluster - Complete Feature Guide

> Complete implementation guide for distributed rendering with command replication, time synchronization, and file distribution

**Status:** Planning  
**Priority:** P4 (Advanced Feature)  
**Estimated Time:** 40-60h total  
**Dependencies:** None (standalone feature)

---

## 📋 Executive Overview

The Multi-Video Render Cluster enables **enterprise-scale synchronized video playback** across dozens of outputs using multiple PCs. Each node renders locally from the same commands, eliminating frame streaming overhead and enabling unlimited scaling.

### Core Concept

**Command Replication, Not Frame Streaming**

```
Traditional Approach (❌):
Master renders frame → Compress → Network → Decompress → Display
= High latency, limited scaling, massive bandwidth

Our Approach (✅):
Master sends command → All nodes render same frame locally
= Near-zero latency, infinite scaling, minimal bandwidth
```

### Key Features

✅ **Zero Frame Streaming** - Commands only, not video data  
✅ **Perfect Synchronization** - ±1ms with timestamp-based rendering  
✅ **Infinite Scaling** - 2 to 100+ nodes, same performance  
✅ **Deterministic Rendering** - Same commands = identical output  
✅ **Automatic File Distribution** - HTTP-based with hash validation  
✅ **Effects/Transitions Sync** - All nodes execute identical pipelines  
✅ **Master/Slave Architecture** - One control node, many render nodes  

---

## 🏗️ System Architecture

### Cluster Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                        MASTER NODE                               │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Full UI & Control                                          │ │
│  │  - Playlist management                                      │ │
│  │  - Effect editor                                            │ │
│  │  - Timeline controls                                        │ │
│  │  - File browser                                             │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Command Broadcast Engine                                   │ │
│  │  - WebSocket server (/cluster/*)                           │ │
│  │  - Command queue & deduplication                           │ │
│  │  - State snapshot generator                                │ │
│  │  - Master clock broadcast (100ms heartbeat)                │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  File Server (HTTP)                                        │ │
│  │  - Serve video files                                       │ │
│  │  - Generate file manifests                                 │ │
│  │  - Compute SHA256 hashes                                   │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  Optional: Local Rendering                                 │ │
│  │  - Master can also render assigned outputs                 │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       │ WebSocket Commands
                       │ + HTTP File Transfer
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  SLAVE #1    │ │  SLAVE #2    │ │  SLAVE #3    │
│              │ │              │ │              │
│ Outputs:     │ │ Outputs:     │ │ Outputs:     │
│ - HDMI1      │ │ - HDMI1      │ │ - HDMI1      │
│ - HDMI2      │ │ - HDMI2      │ │ - HDMI2      │
│              │ │              │ │              │
│ Cache:       │ │ Cache:       │ │ Cache:       │
│ 15 files     │ │ 22 files     │ │ 18 files     │
│ 8.2 GB       │ │ 12.1 GB      │ │ 9.7 GB       │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Node Roles

| Role | Description | UI | Rendering | Command Source |
|------|-------------|-----|-----------|----------------|
| **Master** | Control node with full UI | Full web interface | Optional | Generates commands |
| **Slave** | Render-only node | Minimal status page | Required | Receives commands |

---

## 🔄 Command Replication System

### Command Flow

```
User Action on Master                WebSocket Broadcast           Slave Execution
──────────────────────              ────────────────────          ─────────────────

1. Load Clip
   ├─ Select video file            → load_clip command           → Fetch from cache
   └─ Generate command                {clip_id, file_path}          or HTTP download
                                                                    Load into memory

2. Apply Effect
   ├─ Add color_correction         → apply_effect command        → Execute same effect
   └─ Params: brightness=1.5          {effect, params}              with same params
                                      timestamp: 123456.789         Identical result

3. Start Playback
   ├─ Click Play                    → play command                → Sync to timestamp
   └─ BPM: 128, time: 0s              {timestamp, bpm}              Start rendering

4. Transition
   ├─ Fade to next clip            → start_transition command    → Execute fade
   └─ Duration: 2s                    {type: fade, duration: 2}     at same timestamp
                                                                    Synchronized output
```

### Command Types

```python
# Clip management
{
    "type": "load_clip",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "clip": {
        "id": "clip_001",
        "file_path": "videos/concert.mp4",
        "sha256": "abc123def456789...",  # Included so slave skips separate hash request
        "duration": 180.5,
        "fps": 30
    }
}

# Effect application
{
    "type": "apply_effect",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "clip_id": "clip_001",
    "layer_index": 0,
    "effect": {
        "id": "eff_001",
        "type": "color_correction",
        "params": {
            "brightness": 1.5,
            "contrast": 1.2,
            "saturation": 0.9
        }
    }
}

# Playback control
{
    "type": "play",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "playback_start_master_time": 1234567890.123,  # Master time at which position 0 was reached
    "start_time": 0.0,                             # Position in clip at playback start
    "bpm": 128,
    "master_clock": 1234567890.123
    # Slave computes current position as: master_time_now - playback_start_master_time + start_time
    # This avoids stale position from snapshot network delay
}

# Transition
{
    "type": "start_transition",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "from_clip": "clip_001",
    "to_clip": "clip_002",
    "transition": {
        "type": "fade",
        "duration": 2.0,
        "curve": "ease_in_out"
    }
}

# Blend mode
{
    "type": "set_layer_blend",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "clip_id": "clip_001",
    "layer_index": 1,
    "blend_mode": "screen",
    "opacity": 0.75
}

# Master clock heartbeat
{
    "type": "heartbeat",
    "master_clock": 1234567890.123,
    "bpm": 128,
    "beat_count": 512
}
```

### Deterministic Rendering

**Critical Principle:** Same commands → Same output

All nodes run **identical code** and execute **identical operations**:

```python
# Master executes
frame = apply_effect(frame, effect_type="blur", params={"radius": 10})

# Slave executes (identical)
frame = apply_effect(frame, effect_type="blur", params={"radius": 10})

# Result: Pixel-perfect identical frames
```

**Requirements:**
- ✅ All nodes same software version
- ✅ All nodes same effect plugins
- ✅ All nodes same generator plugins
- ✅ Identical frame processing pipeline
- ✅ Deterministic random number seeding (for random effects)

---

## ⏱️ Time Synchronization

### Option A: Master Clock Broadcast (Fallback)

Master broadcasts its clock every 100ms, slaves synchronize to it.

```python
# Master: Broadcast heartbeat
@app.socketio.on_interval(0.1)  # 100ms = 10Hz
def broadcast_heartbeat():
    socketio.emit('cluster/heartbeat', {
        'master_clock': time.time(),
        'bpm': current_bpm,
        'beat_count': beat_counter
    }, namespace='/cluster')

# Slave: Sync to master clock
def on_heartbeat(data):
    master_time = data['master_clock']
    local_time = time.time()
    
    # Calculate offset
    clock_offset = master_time - local_time
    
    # Apply smoothing (exponential moving average)
    global smoothed_offset
    smoothed_offset = 0.9 * smoothed_offset + 0.1 * clock_offset
    
    # Adjusted local time
    def get_master_time():
        return time.time() + smoothed_offset
```

**Pros:**
- ✅ Simple implementation
- ✅ No external dependencies
- ✅ Works on any network
- ✅ Automatic drift correction

**Cons:**
- ❌ Network jitter affects accuracy (±10-50ms)
- ❌ Not suitable for frame-accurate sync (<16ms)

**Best for:** Environments where NTP setup is not possible

---

### Option B: NTP Time Synchronization (Recommended)

Use Network Time Protocol for ±1ms precision.

```bash
# Setup NTP on all nodes (Linux)
sudo apt-get install ntp
sudo systemctl enable ntp
sudo systemctl start ntp

# Point to master as NTP server
# /etc/ntp.conf on slaves
server 192.168.1.100 iburst prefer

# Windows: Use built-in time sync
w32tm /config /manualpeerlist:192.168.1.100 /syncfromflags:manual /update
net stop w32time && net start w32time
```

**Pros:**
- ✅ ±1ms accuracy
- ✅ Hardware clock sync
- ✅ Industry standard
- ✅ Handles network delays

**Cons:**
- ❌ Requires network configuration
- ❌ Additional setup complexity
- ❌ Firewall rules (UDP 123)

**Best for:** All installations — default choice for reliable sync

---

### Frame Synchronization Algorithm

Regardless of time source, frame sync uses timestamp-based rendering:

```python
class ClusterRenderer:
    def __init__(self):
        self.clock_offset = 0.0  # From master clock sync
        
    def get_current_master_time(self):
        """Get synchronized time"""
        if USE_NTP:
            return time.time()  # NTP-synced clock
        else:
            return time.time() + self.clock_offset  # Master clock offset
    
    def render_frame_at_timestamp(self, target_timestamp):
        """
        Render frame for specific timestamp
        
        All nodes render the same timestamp → identical frame
        """
        # Calculate video position
        video_time = target_timestamp - self.playback_start_time
        
        # Get frame at exact position
        frame = self.video_source.get_frame_at_time(video_time)
        
        # Apply effects (all nodes execute same effects)
        for effect in self.active_effects:
            frame = effect.process(frame, video_time)
        
        # Apply transition if active
        if self.transition_active:
            progress = (target_timestamp - self.transition_start) / self.transition_duration
            frame = self.blend_transition(frame, progress)
        
        return frame
    
    def render_loop(self):
        """Main render loop with accurate frame timing (Windows-safe)"""
        next_frame_time = time.perf_counter()
        frame_interval = 1.0 / self.fps

        while self.playing:
            # What time should we render for?
            target_timestamp = self.get_current_master_time()

            # Render frame for that timestamp
            frame = self.render_frame_at_timestamp(target_timestamp)

            # Display
            self.output_manager.send_frame(frame, self.output_ids)

            # Precise frame timing: accumulate instead of sleep(1/fps)
            # Avoids Windows timer resolution drift (~15ms)
            next_frame_time += frame_interval
            sleep_time = next_frame_time - time.perf_counter()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                # Frame took too long — skip ahead to stay on schedule
                next_frame_time = time.perf_counter()
```

**Key Points:**
- All nodes render **the same timestamp**
- Video position calculated from timestamp, not frame count
- Effects/transitions execute at exact timestamps
- Result: Pixel-perfect synchronization

---

## 📦 State Replication

### Initial Sync: Full Snapshot

When slave connects, it receives complete state:

```python
# Master: Generate state snapshot
def get_state_snapshot():
    now = time.time()
    return {
        "version": "2.4.0",
        "snapshot_time": now,  # Slave uses this to compensate for network delay
        "playlists": {
            "video": {
                "clips": [...],  # All clips with effects and sha256 hashes
                "current_clip": "clip_001",
                # Send anchor point instead of raw position:
                "playback_start_master_time": now - 45.2,  # master_time when pos=0
                "current_position": 45.2  # for display only, not for seek
            },
            "artnet": {
                "objects": [...],
                "active": True
            }
        },
        "config": {...},
        "bpm": 128,
        "master_clock": now
    }

# Slave: Compute accurate position on connect
def load_state(snapshot):
    network_delay = time.time() - snapshot['snapshot_time']  # Estimate one-way delay
    adjusted_start = snapshot['playlists']['video']['playback_start_master_time']
    # Current position = (now - delay_adjustment) - playback_start
    # Slave render loop handles this automatically via get_current_master_time()
```

### Incremental Updates: Delta Sync

After initial sync, only send changes:

```python
# Master: Track state changes
state_version = 0

def update_playlist(change):
    global state_version
    state_version += 1
    
    # Broadcast delta
    socketio.emit('cluster/state_delta', {
        'version': state_version,
        'change_type': 'playlist_update',
        'data': change
    }, namespace='/cluster')

# Slave: Apply delta
def on_state_delta(delta):
    if delta['version'] == expected_version + 1:
        apply_change(delta)
        expected_version += 1
    else:
        # Out of sync - request full snapshot
        request_snapshot()
```

---

## 🎨 Effects, Transitions & Blends Synchronization

### How It Works

**Effects/transitions/blends are commands, not rendered frames**

```python
# Master applies effect
add_effect(clip_id="clip_001", effect_type="blur", params={"radius": 10})

# Master broadcasts command
→ {"type": "apply_effect", "clip_id": "clip_001", "effect_type": "blur", ...}

# Slave receives command and applies SAME effect
→ All nodes execute: frame = blur(frame, radius=10)

# Result: Identical processing on all nodes
```

### Why This Works

All nodes have:
- ✅ Same codebase (same `blur()` implementation)
- ✅ Same effect plugins (same algorithms)
- ✅ Same parameters (from command)
- ✅ Same input frame (from same video file)
- ✅ **Result: Identical output frame**

### Multi-Layer Blending

```python
# Command replication handles layers automatically
{
    "type": "add_layer",
    "clip_id": "clip_001",
    "layer": {
        "source": "videos/overlay.mp4",
        "blend_mode": "screen",
        "opacity": 0.75,
        "effects": [
            {"type": "color_correction", "params": {...}},
            {"type": "blur", "params": {...}}
        ]
    }
}

# All nodes execute:
base_frame = render_clip("clip_001")
overlay_frame = render_clip("videos/overlay.mp4")
overlay_frame = apply_effects(overlay_frame)  # Same effects
result = blend(base_frame, overlay_frame, mode="screen", opacity=0.75)
```

### Transition Synchronization

```python
# Master starts transition at specific timestamp
{
    "type": "start_transition",
    "timestamp": 1234567890.500,  # Exact start time
    "transition": {
        "type": "fade",
        "duration": 2.0
    }
}

# All nodes calculate transition progress from timestamp
current_time = get_master_time()
progress = (current_time - 1234567890.500) / 2.0  # Same calculation
alpha = ease_in_out(progress)  # Same easing function
result = lerp(frame_a, frame_b, alpha)  # Identical blend
```

**Critical:** Timestamp-based transitions ensure all nodes are at the same progress point.

---

## 📁 File Distribution System

### Overview

The cluster file distribution system enables automatic video file sharing between master and slave nodes without manual copying. The master acts as an HTTP file server, while slaves fetch files on-demand and cache them locally with hash-based integrity verification.

### Key Features

✅ **Zero Manual Copying** - Files automatically distributed to slaves  
✅ **Hash-Based Validation** - SHA256 checksums ensure file integrity  
✅ **Local Caching** - Fast playback after initial fetch  
✅ **Cache Warming** - Pre-fetch playlist files before playback  
✅ **Status Indicators** - Frontend shows cache readiness per file  
✅ **Bandwidth Efficient** - Only fetch missing/changed files  

---

## 🏗️ Architecture

```
Master Node                          Slave Node
┌─────────────────┐                 ┌─────────────────┐
│  Video Files    │                 │  Cache Manager  │
│  /videos/*.mp4  │                 │  /tmp/cache/    │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         │  HTTP File Server                 │
         │  /api/cluster/files/*             │
         │                                   │
         │  /api/cluster/files/manifest      │
         │  (file list + hashes)             │
         │                                   │
         └───────────────────────────────────┘
                   WebSocket
            Command: load_clip()
            → Slave fetches file
            → Validates hash
            → Caches locally
            → Ready to play
```

### Data Flow

1. **Master broadcasts command:** `load_clip("videos/concert.mp4")`
2. **Slave receives command:**
   - Checks local cache: `/tmp/cluster_cache/abc123def.mp4`
   - Computes hash if file exists
   - Fetches from master if missing/hash mismatch
3. **Master serves file:** HTTP streaming with range support
4. **Slave validates:** SHA256 checksum verification
5. **Slave caches:** Store with hash-based filename
6. **Slave reports:** Cache status to master via WebSocket

---

## 🗄️ Hash-Based Cache System

### Why Hash-Based?

❌ **Filename-based:** File renames break cache  
❌ **Size-based:** Corrupted files same size  
❌ **Timestamp-based:** Clock drift, unreliable  
✅ **Hash-based:** Guaranteed integrity, content-addressable

### Cache File Naming

```python
# Original file: videos/concert_2026.mp4
# SHA256: abc123def456...
# Cached as: /tmp/cluster_cache/abc123def456.mp4

# Metadata file: /tmp/cluster_cache/abc123def456.json
{
    "original_path": "videos/concert_2026.mp4",
    "sha256": "abc123def456789...",
    "size": 524288000,
    "cached_at": "2026-01-16T10:30:00Z",
    "last_accessed": "2026-01-16T14:22:15Z",
    "master_url": "http://192.168.1.100:5000"
}
```

### Cache Directory Structure

```
/tmp/cluster_cache/
├── abc123def456.mp4          # Cached video file
├── abc123def456.json         # Metadata
├── def789abc123.mp4          # Another cached file
├── def789abc123.json         # Metadata
├── manifest.json             # Cache index
└── .lock                     # Cache operation lock
```

---

## 📡 API Endpoints

### Master Node - File Server

#### 1. Get File Manifest (File List + Hashes)

```python
GET /api/cluster/files/manifest

Response:
{
    "files": [
        {
            "path": "videos/concert_2026.mp4",
            "sha256": "abc123def456789...",
            "size": 524288000,
            "modified": "2026-01-10T08:00:00Z"
        },
        {
            "path": "videos/intro.mp4",
            "sha256": "def789abc123456...",
            "size": 102400000,
            "modified": "2026-01-12T14:30:00Z"
        }
    ],
    "total_size": 626688000,
    "count": 2
}
```

#### 2. Download File

```python
GET /api/cluster/files/<path:filepath>
Headers:
    Range: bytes=0-1023  # Optional - for resume support

Response:
    Content-Type: video/mp4
    Content-Length: 524288000
    Accept-Ranges: bytes
    X-File-SHA256: abc123def456789...
    
    [Binary file data]
```

#### 3. Get File Hash

```python
GET /api/cluster/files/hash/<path:filepath>

Response:
{
    "path": "videos/concert_2026.mp4",
    "sha256": "abc123def456789...",
    "size": 524288000
}
```

### Slave Node - Cache Management

#### 1. Get Cache Status

```python
GET /api/cluster/cache/status

Response:
{
    "cache_dir": "/tmp/cluster_cache",
    "total_size": 1073741824,  # 1GB
    "used_size": 626688000,
    "file_count": 2,
    "files": [
        {
            "original_path": "videos/concert_2026.mp4",
            "sha256": "abc123def456789...",
            "size": 524288000,
            "cached": true,
            "last_accessed": "2026-01-16T14:22:15Z"
        }
    ]
}
```

#### 2. Warm Cache (Pre-fetch Files)

```python
POST /api/cluster/cache/warm
{
    "files": [
        "videos/concert_2026.mp4",
        "videos/intro.mp4"
    ]
}

Response:
{
    "status": "warming",
    "job_id": "warm_job_123",
    "files_queued": 2
}
```

#### 3. Get Warming Status

```python
GET /api/cluster/cache/warm/status/<job_id>

Response:
{
    "job_id": "warm_job_123",
    "status": "in_progress",  # or "completed", "failed"
    "progress": {
        "total_files": 2,
        "completed_files": 1,
        "current_file": "videos/intro.mp4",
        "current_progress": 0.45,  # 45% of current file
        "total_progress": 0.72     # 72% overall
    },
    "files": [
        {
            "path": "videos/concert_2026.mp4",
            "status": "completed",
            "cached": true
        },
        {
            "path": "videos/intro.mp4",
            "status": "downloading",
            "cached": false,
            "progress": 0.45
        }
    ]
}
```

#### 4. Clear Cache

```python
POST /api/cluster/cache/clear
{
    "max_age_days": 30,  # Optional - clear files older than X days
    "force": false       # Optional - clear all files
}

Response:
{
    "cleared_files": 5,
    "freed_space": 2147483648  # bytes
}
```

---

## 🔧 Backend Implementation

### 1. Master File Server

**File:** `src/modules/cluster/file_server.py`

```python
import os
import hashlib
import threading
from flask import send_file, jsonify

class ClusterFileServer:
    """HTTP file server for master node"""
    
    def __init__(self, media_root):
        self.media_root = os.path.abspath(media_root)
        self._file_hashes = {}  # Cache computed hashes
        self._hash_lock = threading.Lock()  # Thread-safe hash cache

    def _safe_path(self, filepath):
        """Resolve path and reject traversal attempts"""
        safe = os.path.normpath(os.path.join(self.media_root, filepath))
        if not safe.startswith(self.media_root + os.sep) and safe != self.media_root:
            return None
        return safe
        
    def compute_file_hash(self, filepath):
        """Compute SHA256 hash of file (thread-safe, cached)"""
        with self._hash_lock:
            if filepath in self._file_hashes:
                return self._file_hashes[filepath]

        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):  # 64KB chunks for speed
                sha256.update(chunk)

        file_hash = sha256.hexdigest()
        with self._hash_lock:
            self._file_hashes[filepath] = file_hash
        return file_hash
    
    def get_manifest(self):
        """Generate file manifest with hashes"""
        files = []
        total_size = 0
        
        for root, dirs, filenames in os.walk(self.media_root):
            for filename in filenames:
                if filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    filepath = os.path.join(root, filename)
                    rel_path = os.path.relpath(filepath, self.media_root)
                    file_size = os.path.getsize(filepath)
                    file_hash = self.compute_file_hash(filepath)
                    
                    files.append({
                        'path': rel_path.replace('\\', '/'),
                        'sha256': file_hash,
                        'size': file_size,
                        'modified': os.path.getmtime(filepath)
                    })
                    total_size += file_size
        
        return {
            'files': files,
            'total_size': total_size,
            'count': len(files)
        }
    
    def serve_file(self, filepath):
        """Serve file with range support"""
        full_path = self._safe_path(filepath)
        if not full_path:
            return {'error': 'Invalid path'}, 403

        if not os.path.exists(full_path):
            return {'error': 'File not found'}, 404

        # Detect MIME type from extension
        ext = os.path.splitext(full_path)[1].lower()
        mime_map = {'.mp4': 'video/mp4', '.mov': 'video/quicktime',
                    '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska'}
        mimetype = mime_map.get(ext, 'application/octet-stream')

        file_hash = self.compute_file_hash(full_path)

        response = send_file(
            full_path,
            mimetype=mimetype,
            conditional=True,  # Enable range requests
            as_attachment=False
        )
        response.headers['X-File-SHA256'] = file_hash
        response.headers['Accept-Ranges'] = 'bytes'

        return response

# Flask routes
@app.route('/api/cluster/files/manifest', methods=['GET'])
def get_file_manifest():
    manifest = file_server.get_manifest()
    return jsonify(manifest)

@app.route('/api/cluster/files/<path:filepath>', methods=['GET'])
def serve_cluster_file(filepath):
    return file_server.serve_file(filepath)

@app.route('/api/cluster/files/hash/<path:filepath>', methods=['GET'])
def get_file_hash(filepath):
    full_path = file_server._safe_path(filepath)
    if not full_path:
        return {'error': 'Invalid path'}, 403
    if not os.path.exists(full_path):
        return {'error': 'File not found'}, 404

    return jsonify({
        'path': filepath,
        'sha256': file_server.compute_file_hash(full_path),
        'size': os.path.getsize(full_path)
    })
```

### 2. Slave Cache Manager

**File:** `src/modules/cluster/cache_manager.py`

```python
import os
import json
import hashlib
import threading
import requests
from pathlib import Path
from datetime import datetime

class ClusterCacheManager:
    """Manages local file cache on slave nodes"""
    
    def __init__(self, master_url, cache_dir):
        self.master_url = master_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.manifest_file = self.cache_dir / 'manifest.json'
        self._load_manifest()
        
        # Cache warming state
        self.warming_jobs = {}
        self.warming_lock = threading.Lock()
        
    def _load_manifest(self):
        """Load cache manifest from disk"""
        if self.manifest_file.exists():
            with open(self.manifest_file, 'r') as f:
                self.manifest = json.load(f)
        else:
            self.manifest = {'files': {}}
    
    def _save_manifest(self):
        """Save cache manifest to disk"""
        with open(self.manifest_file, 'w') as f:
            json.dump(self.manifest, f, indent=2)
    
    def _compute_hash(self, filepath):
        """Compute SHA256 hash of file"""
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _fetch_file_hash(self, filepath):
        """Get file hash from master"""
        url = f"{self.master_url}/api/cluster/files/hash/{filepath}"
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()['sha256']
        return None
    
    def get_file(self, filepath, expected_hash=None):
        """
        Get file from cache or fetch from master
        
        Args:
            filepath: Relative file path (e.g., "videos/concert.mp4")
            expected_hash: SHA256 hash (from load_clip command — avoids extra HTTP round-trip)
            
        Returns:
            Absolute path to cached file
        """
        # Get expected hash from master only if not provided by command
        if not expected_hash:
            expected_hash = self._fetch_file_hash(filepath)
            if not expected_hash:
                raise FileNotFoundError(f"File not found on master: {filepath}")

        # Preserve original file extension
        ext = os.path.splitext(filepath)[1] or '.mp4'
        cached_path = self.cache_dir / f"{expected_hash}{ext}"
        metadata_path = self.cache_dir / f"{expected_hash}.json"
        
        if cached_path.exists():
            # Validate hash
            actual_hash = self._compute_hash(cached_path)
            if actual_hash == expected_hash:
                # Update last accessed time
                self._update_metadata(metadata_path, filepath)
                return str(cached_path)
            else:
                # Hash mismatch - delete corrupted file
                cached_path.unlink()
                if metadata_path.exists():
                    metadata_path.unlink()
        
        # Fetch from master
        return self._fetch_and_cache(filepath, expected_hash)
    
    def _fetch_and_cache(self, filepath, expected_hash):
        """Download file from master with resume support"""
        url = f"{self.master_url}/api/cluster/files/{filepath}"
        ext = os.path.splitext(filepath)[1] or '.mp4'
        cached_path = self.cache_dir / f"{expected_hash}{ext}"
        metadata_path = self.cache_dir / f"{expected_hash}.json"
        tmp_path = self.cache_dir / f"{expected_hash}.tmp"

        # Resume support: check how much we already have
        resume_offset = tmp_path.stat().st_size if tmp_path.exists() else 0
        headers = {'Range': f'bytes={resume_offset}-'} if resume_offset else {}

        response = requests.get(url, stream=True, headers=headers)
        if response.status_code not in (200, 206):
            raise FileNotFoundError(f"Failed to fetch file: {filepath}")

        total_size = int(response.headers.get('Content-Length', 0)) + resume_offset

        # Append or create
        mode = 'ab' if resume_offset else 'wb'
        with open(tmp_path, mode) as f:
            for chunk in response.iter_content(chunk_size=65536):
                f.write(chunk)

        # Validate hash
        actual_hash = self._compute_hash(tmp_path)
        if actual_hash != expected_hash:
            tmp_path.unlink()
            raise ValueError(f"Hash mismatch for {filepath}: expected {expected_hash}, got {actual_hash}")

        # Atomic rename to final path
        tmp_path.rename(cached_path)
        
        # Save metadata
        metadata = {
            'original_path': filepath,
            'sha256': expected_hash,
            'size': total_size,
            'cached_at': datetime.utcnow().isoformat() + 'Z',
            'last_accessed': datetime.utcnow().isoformat() + 'Z',
            'master_url': self.master_url
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update manifest
        self.manifest['files'][filepath] = {
            'hash': expected_hash,
            'cached_path': str(cached_path)
        }
        self._save_manifest()
        
        return str(cached_path)
    
    def _update_metadata(self, metadata_path, filepath):
        """Update last accessed time in metadata"""
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            metadata['last_accessed'] = datetime.utcnow().isoformat() + 'Z'
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def warm_cache(self, filepaths, job_id=None):
        """
        Pre-fetch multiple files in background
        
        Args:
            filepaths: List of file paths to fetch
            job_id: Optional job ID for tracking
            
        Returns:
            Job ID for status tracking
        """
        if not job_id:
            job_id = f"warm_{datetime.utcnow().timestamp()}"
        
        job_state = {
            'status': 'starting',
            'total_files': len(filepaths),
            'completed_files': 0,
            'files': {fp: {'status': 'pending', 'cached': False} for fp in filepaths}
        }
        
        with self.warming_lock:
            self.warming_jobs[job_id] = job_state
        
        # Start background thread
        thread = threading.Thread(
            target=self._warm_cache_worker,
            args=(job_id, filepaths)
        )
        thread.daemon = True
        thread.start()
        
        return job_id
    
    def _warm_cache_worker(self, job_id, filepaths):
        """Background worker for cache warming — parallel downloads"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        job_state = self.warming_jobs[job_id]
        job_state['status'] = 'in_progress'

        def fetch_one(filepath):
            job_state['files'][filepath]['status'] = 'fetching'
            try:
                self.get_file(filepath)
                job_state['files'][filepath]['status'] = 'completed'
                job_state['files'][filepath]['cached'] = True
                with self.warming_lock:
                    job_state['completed_files'] += 1
            except Exception as e:
                job_state['files'][filepath]['status'] = 'failed'
                job_state['files'][filepath]['error'] = str(e)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(fetch_one, fp): fp for fp in filepaths}
            for future in as_completed(futures):
                future.result()  # propagate exceptions to log

        job_state['status'] = 'completed'
        job_state['completed_at'] = datetime.utcnow().isoformat() + 'Z'

        # Evict old completed jobs (keep last 20)
        with self.warming_lock:
            completed = [(jid, js) for jid, js in self.warming_jobs.items()
                         if js['status'] == 'completed']
            completed.sort(key=lambda x: x[1].get('completed_at', ''), reverse=True)
            for evict_id, _ in completed[20:]:
                del self.warming_jobs[evict_id]
    
    def get_warming_status(self, job_id):
        """Get status of cache warming job"""
        if job_id not in self.warming_jobs:
            return None
        
        job_state = self.warming_jobs[job_id]
        
        # Calculate progress
        total = job_state['total_files']
        completed = job_state['completed_files']
        total_progress = completed / total if total > 0 else 0
        
        return {
            'job_id': job_id,
            'status': job_state['status'],
            'progress': {
                'total_files': total,
                'completed_files': completed,
                'total_progress': total_progress
            },
            'files': [
                {'path': fp, **info}
                for fp, info in job_state['files'].items()
            ]
        }
    
    def get_cache_status(self):
        """Get overall cache status"""
        files = []
        total_size = 0
        
        for filepath, info in self.manifest['files'].items():
            cached_path = Path(info['cached_path'])
            if cached_path.exists():
                size = cached_path.stat().st_size
                total_size += size
                
                metadata_path = cached_path.with_suffix('.json')
                metadata = {}
                if metadata_path.exists():
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                
                files.append({
                    'original_path': filepath,
                    'sha256': info['hash'],
                    'size': size,
                    'cached': True,
                    'last_accessed': metadata.get('last_accessed')
                })
        
        return {
            'cache_dir': str(self.cache_dir),
            'total_size': total_size,
            'file_count': len(files),
            'files': files
        }
    
    def clear_cache(self, max_age_days=None, force=False):
        """Clear old or all cached files"""
        cleared = 0
        freed_space = 0
        
        if force:
            # Clear everything
            for file in self.cache_dir.glob('*'):
                if file.is_file():
                    freed_space += file.stat().st_size
                    file.unlink()
                    cleared += 1
            
            self.manifest = {'files': {}}
            self._save_manifest()
            
        elif max_age_days:
            # Clear files older than max_age_days
            cutoff = datetime.utcnow().timestamp() - (max_age_days * 86400)
            
            for metadata_file in self.cache_dir.glob('*.json'):
                if metadata_file.name == 'manifest.json':
                    continue
                
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                last_accessed = datetime.fromisoformat(
                    metadata['last_accessed'].replace('Z', '+00:00')
                ).timestamp()
                
                if last_accessed < cutoff:
                    # Delete cache file
                    cache_file = metadata_file.with_suffix('.mp4')
                    if cache_file.exists():
                        freed_space += cache_file.stat().st_size
                        cache_file.unlink()
                        cleared += 1
                    
                    metadata_file.unlink()
                    
                    # Remove from manifest
                    original_path = metadata['original_path']
                    if original_path in self.manifest['files']:
                        del self.manifest['files'][original_path]
            
            self._save_manifest()
        
        return {
            'cleared_files': cleared,
            'freed_space': freed_space
        }

# Flask routes
@app.route('/api/cluster/cache/status', methods=['GET'])
def get_cache_status():
    return jsonify(cache_manager.get_cache_status())

@app.route('/api/cluster/cache/warm', methods=['POST'])
def warm_cache():
    data = request.json
    files = data.get('files', [])
    job_id = cache_manager.warm_cache(files)
    return jsonify({'status': 'warming', 'job_id': job_id, 'files_queued': len(files)})

@app.route('/api/cluster/cache/warm/status/<job_id>', methods=['GET'])
def get_warming_status(job_id):
    status = cache_manager.get_warming_status(job_id)
    if not status:
        return {'error': 'Job not found'}, 404
    return jsonify(status)

@app.route('/api/cluster/cache/clear', methods=['POST'])
def clear_cache():
    data = request.json
    result = cache_manager.clear_cache(
        max_age_days=data.get('max_age_days'),
        force=data.get('force', False)
    )
    return jsonify(result)
```

---

## 🎨 Frontend Integration

### 1. Cache Status Indicator

**Location:** Playlist UI, File Browser

```html
<!-- In playlist clip item -->
<div class="clip-item">
    <span class="clip-name">concert_2026.mp4</span>
    
    <!-- Cache status badge -->
    <span class="cache-status" data-filepath="videos/concert_2026.mp4">
        <i class="bi bi-cloud-download"></i>
        <span class="status-text">Checking...</span>
    </span>
</div>
```

```css
.cache-status {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.85em;
}

.cache-status.cached {
    background: #d4edda;
    color: #155724;
}

.cache-status.downloading {
    background: #fff3cd;
    color: #856404;
}

.cache-status.not-cached {
    background: #f8d7da;
    color: #721c24;
}
```

```javascript
// Update cache status indicators
async function updateCacheStatus() {
    if (!window.clusterMode || window.clusterMode !== 'slave') {
        return; // Only on slave nodes
    }
    
    const response = await fetch('/api/cluster/cache/status');
    const cacheStatus = await response.json();
    
    // Create lookup map
    const cachedFiles = {};
    cacheStatus.files.forEach(file => {
        cachedFiles[file.original_path] = file;
    });
    
    // Update all status indicators
    document.querySelectorAll('.cache-status').forEach(indicator => {
        const filepath = indicator.dataset.filepath;
        const fileInfo = cachedFiles[filepath];
        
        if (fileInfo && fileInfo.cached) {
            indicator.className = 'cache-status cached';
            indicator.querySelector('.status-text').textContent = 'Cached';
            indicator.querySelector('i').className = 'bi bi-check-circle-fill';
        } else {
            indicator.className = 'cache-status not-cached';
            indicator.querySelector('.status-text').textContent = 'Not Cached';
            indicator.querySelector('i').className = 'bi bi-cloud-download';
        }
    });
}

// Check cache status periodically
setInterval(updateCacheStatus, 5000);
```

### 2. Cache Warming UI

**Location:** Playlist actions, Cluster settings

```html
<!-- Cache warming button in playlist -->
<button class="btn btn-sm btn-warning" onclick="warmPlaylistCache()">
    <i class="bi bi-download"></i> Pre-fetch Files
</button>

<!-- Cache warming modal -->
<div class="modal" id="cacheWarmingModal">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5>Cache Warming Progress</h5>
            </div>
            <div class="modal-body">
                <div class="progress mb-3">
                    <div class="progress-bar" id="warmProgress" style="width: 0%">0%</div>
                </div>
                
                <div id="warmFileList">
                    <!-- File list with status -->
                </div>
            </div>
        </div>
    </div>
</div>
```

```javascript
// Warm cache for current playlist
async function warmPlaylistCache() {
    const playlist = app.playlists.video;
    const files = playlist.clips.map(clip => clip.file_path);
    
    // Start warming
    const response = await fetch('/api/cluster/cache/warm', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({files})
    });
    
    const result = await response.json();
    const jobId = result.job_id;
    
    // Show modal
    $('#cacheWarmingModal').modal('show');
    
    // Poll for progress
    const progressInterval = setInterval(async () => {
        const statusResponse = await fetch(`/api/cluster/cache/warm/status/${jobId}`);
        const status = await statusResponse.json();
        
        // Update progress bar
        const progress = Math.round(status.progress.total_progress * 100);
        document.getElementById('warmProgress').style.width = `${progress}%`;
        document.getElementById('warmProgress').textContent = `${progress}%`;
        
        // Update file list
        const fileListHtml = status.files.map(file => `
            <div class="warm-file-item">
                <span class="file-name">${file.path}</span>
                <span class="file-status status-${file.status}">
                    ${getStatusIcon(file.status)} ${file.status}
                </span>
            </div>
        `).join('');
        document.getElementById('warmFileList').innerHTML = fileListHtml;
        
        // Stop when complete
        if (status.status === 'completed') {
            clearInterval(progressInterval);
            setTimeout(() => {
                $('#cacheWarmingModal').modal('hide');
                updateCacheStatus(); // Refresh cache indicators
            }, 2000);
        }
    }, 1000);
}

function getStatusIcon(status) {
    const icons = {
        'pending': '<i class="bi bi-clock"></i>',
        'fetching': '<i class="bi bi-download"></i>',
        'completed': '<i class="bi bi-check-circle-fill text-success"></i>',
        'failed': '<i class="bi bi-x-circle-fill text-danger"></i>'
    };
    return icons[status] || '';
}
```

### 3. Cluster Settings Panel

```html
<div class="card mt-3">
    <div class="card-header">
        <h6>Cluster Cache Settings</h6>
    </div>
    <div class="card-body">
        <div class="mb-3">
            <label>Cache Directory</label>
            <input type="text" class="form-control" value="/tmp/cluster_cache" disabled>
        </div>
        
        <div class="mb-3">
            <label>Cache Size</label>
            <div class="d-flex align-items-center gap-2">
                <div class="flex-grow-1">
                    <div class="progress">
                        <div class="progress-bar" id="cacheUsageBar" style="width: 45%">45%</div>
                    </div>
                </div>
                <span id="cacheUsageText">600 MB / 1.3 GB</span>
            </div>
        </div>
        
        <div class="d-flex gap-2">
            <button class="btn btn-warning" onclick="warmAllCache()">
                <i class="bi bi-download"></i> Pre-fetch All
            </button>
            <button class="btn btn-danger" onclick="clearOldCache()">
                <i class="bi bi-trash"></i> Clear Old (30d+)
            </button>
            <button class="btn btn-outline-danger" onclick="clearAllCache()">
                <i class="bi bi-trash3"></i> Clear All
            </button>
        </div>
    </div>
</div>
```

---

## 🚀 Implementation Steps

### Phase 1: Backend Foundation (4-6h)

1. **Create `ClusterFileServer` class** (2-3h)
   - Implement file manifest generation
   - Add SHA256 hash computation
   - Setup HTTP file serving with range support
   - Add Flask routes

2. **Create `ClusterCacheManager` class** (2-3h)
   - Implement hash-based cache storage
   - Add file fetching with validation
   - Create metadata management
   - Add Flask routes

### Phase 2: Cache Warming (3-4h)

3. **Implement cache warming system** (2-3h)
   - Background worker threads
   - Progress tracking
   - Job status API

4. **Add cache management** (1h)
   - Clear old files
   - Cache size monitoring
   - Manual cache clearing

### Phase 3: Frontend Integration (3-5h)

5. **Add cache status indicators** (1-2h)
   - Status badges in playlist
   - Real-time status updates
   - Visual feedback

6. **Create cache warming UI** (2-3h)
   - Progress modal
   - File-by-file status
   - Bulk operations

### Phase 4: Integration & Testing (2-3h)

7. **Integrate with cluster system** (1-2h)
   - Connect to ClusterManager
   - Update VideoFrameSource to use cache
   - WebSocket status updates

8. **Testing & optimization** (1h)
   - Test hash validation
   - Test cache warming
   - Performance optimization

---

## 📝 Configuration

### Master Node Config

```json
{
    "cluster": {
        "mode": "master",
        "file_server": {
            "enabled": true,
            "media_root": "C:\\Videos",
            "compute_hashes_on_startup": false,
            "hash_cache_file": "data/cluster_file_hashes.json"
        }
    }
}
```

### Slave Node Config

```json
{
    "cluster": {
        "mode": "slave",
        "master_url": "http://192.168.1.100:5000",
        "cache": {
            "enabled": true,
            "cache_dir": "/tmp/cluster_cache",
            "max_size_gb": 50,
            "auto_warm_on_connect": true,
            "auto_clear_old_days": 30
        }
    }
}
```

---

## 🧪 Testing Scenarios

1. **Basic fetch:** Load clip on slave → file fetches and caches
2. **Hash validation:** Corrupt cached file → re-fetches from master
3. **Cache hit:** Load same clip again → uses cache (no network)
4. **Cache warming:** Pre-fetch playlist → all files cached before play
5. **Network failure:** Master offline → uses cached files
6. **Hash mismatch:** File changed on master → slave re-fetches
7. **Large file:** 4GB video → resume support, progress tracking
8. **Cache clearing:** Old files → auto-cleanup after 30 days

---

## 📊 Performance Metrics

### Expected Performance

- **Hash computation:** ~200-500 MB/s (SSD)
- **Network transfer:** Limited by bandwidth (100 Mbps = ~12 MB/s)
- **Cache lookup:** <1ms (filesystem)
- **Hash validation:** ~200-500 MB/s (for cached files)

### Bandwidth Requirements

| Scenario | Files | Avg Size | Total | Transfer Time (100 Mbps) |
|----------|-------|----------|-------|--------------------------|
| Small show | 10 clips | 500 MB | 5 GB | ~7 minutes |
| Medium show | 50 clips | 500 MB | 25 GB | ~35 minutes |
| Large show | 200 clips | 500 MB | 100 GB | ~2.3 hours |

**Recommendation:** Pre-fetch files before show (cache warming)

---

## 🔐 Security Considerations

1. **Hash validation prevents:**
   - Corrupted file playback
   - Man-in-the-middle tampering
   - Accidental file corruption

2. **Access control:**
   - Master file server should be on private network
   - Optional: Add authentication to cluster API
   - Optional: HTTPS for file transfers

3. **Cache isolation:**
   - Each slave has independent cache
   - No shared state between slaves
   - Cache directory permissions (read/write for app only)

---

## 🎯 Future Enhancements

- [ ] **P2P file sharing** - Slaves share cached files with each other
- [ ] **Chunked downloads** - Resume large file transfers
- [ ] **Compression** - Gzip/Brotli for faster transfers
- [ ] **Prefetch prediction** - ML-based pre-fetching
- [ ] **Delta sync** - Only transfer changed video segments
- [ ] **Multi-master** - Multiple file servers for redundancy
- [ ] **CDN integration** - Use CDN for file distribution

---

## 📚 Related Documentation

- [TRANSPORT_MASTER_SLAVE_ANALYSIS.md](TRANSPORT_MASTER_SLAVE_ANALYSIS.md) - Cluster architecture
- [PLAYLIST_MASTER_SLAVE.md](PLAYLIST_MASTER_SLAVE.md) - Playlist synchronization
- [PERFORMANCE.md](PERFORMANCE.md) - Performance optimization

---

## 🤔 Architecture Design Decisions

### Decision Matrix

The following key decisions have been finalized:

| Decision | Option A | Option B | **DECISION** ✅ | Rationale |
|----------|----------|----------|----------------|-----------|
| **Time Sync** | Master Clock Broadcast | NTP Protocol | **Both (NTP default)** | NTP preferred for accuracy, Master Clock fallback when NTP unavailable |
| **File Access** | HTTP File Server | Shared Storage (NFS/SMB) | **HTTP Primary** | HTTP always works, shared storage optional for performance |
| **Slave UI** | Headless (API only) | Minimal Status Page | **Status Page** | Useful for monitoring, cache status, sync metrics |
| **Failover** | Continue on disconnect | Pause on disconnect | **Nuanced (see below)** | Different behavior based on what fails |
| **Output Assignment** | Static in config | Dynamic via master | **Dynamic via master** | Slaves report outputs, master selects like local HDMI |
| **Version Check** | Enforce same version | Allow version mismatch | **Enforce** | Guarantees deterministic rendering |

### Time Synchronization Decision ✅ DECIDED

**Implementation:** Both NTP and Master Clock, switchable

**NTP Protocol (Default):**
- ✅ Pros: ±1ms accuracy, hardware clock sync, industry standard
- ❌ Cons: Requires NTP setup (firewall UDP 123, NTP server config)
- 🎯 Use case: All installations — best synchronization
- 🔧 Config: `"time_sync": "ntp"` (default)

**Master Clock Broadcast (Fallback):**
- ✅ Pros: Zero setup, works immediately, no dependencies
- ❌ Cons: ±10-50ms accuracy (network jitter)
- 🎯 Use case: Quick testing or environments where NTP is unavailable
- 🔧 Config: `"time_sync": "master_clock"`

**Configuration Example:**
```json
{
    "cluster": {
        "time_sync": {
            "method": "ntp",           // or "master_clock" as fallback
            "ntp_server": "192.168.1.100",  // Master acts as NTP server
            "heartbeat_interval": 0.1  // 100ms heartbeat (both modes)
        }
    }
}
```

**Implementation:**
- NTP: Default — master acts as NTP server, slaves sync to it (±1ms)
- Master Clock: Fallback — broadcast every 100ms if NTP unavailable
- UI: Toggle in cluster settings to switch modes
- Runtime switching: Possible without restart
- Auto-fallback: If NTP sync fails, automatically fall back to Master Clock

### File Distribution Decision ✅ DECIDED

**Implementation:** HTTP primary, shared storage optional for performance

**Architecture:**
1. **HTTP from master** - Always works, no infrastructure needed (primary)
2. **Cache Locally** - Store with hash-based naming, reuse on next load
3. **Optional: Shared Storage** - If configured, skip download entirely (fast path)

**File Manager:**
```python
class HybridFileManager:
    def get_file(self, filepath):
        # 1. Check local cache first (fastest)
        cached_path = self.cache.get(filepath)
        if cached_path and os.path.exists(cached_path):
            return cached_path  # Cache hit - no network needed
        
        # 2. Optional: Try shared storage paths (zero download)
        for shared_path in self.shared_paths:
            full_path = os.path.join(shared_path, filepath)
            if os.path.exists(full_path):
                return full_path  # Fast path - already on disk
        
        # 3. Fetch from master HTTP (primary transfer method)
        return self.fetch_from_master_http(filepath)
```

**Configuration Example:**
```json
{
    "cluster": {
        "file_sources": [
            {"type": "http", "cache_dir": "/tmp/cluster_cache"},   // Primary (always)
            {"type": "shared", "path": "/mnt/shared/videos"}       // Optional performance boost
        ]
    }
}
```

**Benefits:**
- ✅ Zero infrastructure required (HTTP works everywhere out of the box)
- ✅ Works on any network without extra setup
- ✅ Local cache avoids re-downloading files already fetched
- ✅ Shared storage optional: add later for large installs without code changes
- ✅ Consistent behavior across all environments

### Slave UI Decision ✅ DECIDED

**Implementation:** Minimal status page at `http://slave:5000/status`

**Status Page Features:**
- ✅ Connection status (Connected/Disconnected/Standby)
- ✅ Master URL and sync metrics
- ✅ Cache status (files cached, total size, warming progress)
- ✅ Assigned outputs (HDMI1, HDMI2, NDI, etc.)
- ✅ Performance metrics (FPS, latency, network)
- ✅ Error log (last 50 errors)
- ✅ Configuration display (read-only)

**Benefits:**
- Easy troubleshooting during setup
- Monitor cache warming progress
- Verify sync accuracy
- Check output assignments
- Debug connection issues

**Resource Overhead:** ~10 MB RAM (negligible)

**Optional Headless Mode:**
```bash
python main.py --slave --master http://192.168.1.100:5000 --headless
```
Disables web UI completely for embedded systems.

### Failover Strategy Decision ✅ DECIDED

**Implementation:** Nuanced behavior based on failure type

#### Scenario 1: Master Fails
**Behavior:** All slaves stop immediately and show black screen

```python
# Slave detects master disconnection
def on_master_disconnect():
    self.stop_playback()
    self.show_black_screen()
    self.status = "master_offline"
    self.start_reconnect_attempts()
    log.warning("Master disconnected - stopping playback")
```

**Rationale:**
- Without master, no commands → cannot stay synchronized
- Black screen is clear failure indicator
- All slaves in same state (no confusion)
- Safe failure mode (better than desync chaos)

#### Scenario 2: One or More Slaves Fail
**Behavior:** Master and other slaves continue normally

```python
# Master detects slave disconnection
def on_slave_disconnect(slave_id):
    self.slave_status[slave_id] = "offline"
    self.ui_show_warning(f"Slave {slave_id} offline")
    # Other slaves unaffected - keep playing
    log.warning(f"Slave {slave_id} disconnected - continuing with other slaves")
```

**Rationale:**
- Master is still operational → can continue
- Other slaves still synchronized → show goes on
- Failed slave outputs go dark (venue-specific issue)
- Master UI shows warning (operator awareness)

#### Scenario 3: Individual Slave Loses Connection
**Behavior:** Slave enters standby mode with blank screen

```python
# Slave connection lost
def on_connection_lost():
    self.playback_state = "standby"
    self.show_blank_screen()
    self.status_led = "yellow"  # Warning state
    
    # Start retry loop
    while not self.connected:
        try:
            self.reconnect_to_master()
            time.sleep(5)  # Retry every 5 seconds
        except:
            log.info("Reconnection attempt failed, retrying...")
    
    # On successful reconnect
    def on_reconnect():
        self.request_state_snapshot()  # Get current state
        self.resume_playback()
        self.status_led = "green"
        log.info("Reconnected to master - resuming playback")
```

**Visual Indicators:**
- **Blank screen:** No video output (not black bars, truly blank)
- **Status LED:** Yellow/amber during standby
- **Status page:** Shows "Standby - Reconnecting..."

#### Future Enhancement: Autonomous Playback Mode (Phase 2)

**Concept:** Slave continues playing from cache if it has full playlist

```json
{
    "cluster": {
        "autonomous_mode": {
            "enabled": false,  // Disabled by default (Phase 1)
            "require_ntp": true,  // Only work if NTP is synced
            "max_duration": 300  // Max 5 minutes autonomous
        }
    }
}
```

**Behavior (when enabled):**
1. Slave detects master disconnect
2. Checks if entire current clip is cached
3. Checks if NTP time sync is active
4. If both true → continues playing from cache using NTP time
5. If clip ends or cache incomplete → blank screen
6. If master reconnects → resync and continue

**Use Case:** Brief network glitches during live show

**Implementation Notes:**
- Phase 2 feature (not MVP)
- Requires NTP time sync (not master clock)
- Must have full clip cached (not partial)
- Configurable timeout (max autonomous duration)
- Clear warning in UI when slave is autonomous

**Safety Considerations:**
- Default: Disabled (fail-safe to blank screen)
- Requires explicit configuration
- Only for short durations (<5 minutes)
- Master UI shows warning when slave is autonomous
- No multi-clip playback (only current clip)

### Summary Table

| Failure Type | Master | Slaves | Blank Screen | Reconnect |
|--------------|--------|--------|--------------|-----------|
| **Master fails** | Offline | All stop | ✅ All | Master restarts |
| **Slave fails** | Continues | Others continue | ❌ Only failed slave | Slave restarts |
| **Connection lost** | Continues | Other continues | ✅ Disconnected slave | Auto-retry (5s) |
| **Autonomous mode** (Phase 2) | Offline | Continue if cached + NTP | ❌ Keeps playing | Auto-resync |

### Output Assignment Decision ✅ DECIDED

**Implementation:** Dynamic discovery and selection via master UI

#### Concept: Slaves Report Available Outputs

Each slave announces its available outputs to master on connection:

```python
# Slave: Discover and report outputs
def report_available_outputs():
    outputs = []
    
    # Physical outputs
    for screen in enumerate_screens():
        outputs.append({
            "id": f"HDMI{screen.index}",
            "type": "display",
            "resolution": f"{screen.width}x{screen.height}",
            "refresh_rate": screen.refresh_rate
        })
    
    # Virtual outputs
    if has_ndi():
        outputs.append({
            "id": "NDI1",
            "type": "ndi",
            "name": "PyArtnet_NDI"
        })
    
    if has_spout():
        outputs.append({
            "id": "SPOUT1",
            "type": "spout",
            "name": "PyArtnet_Spout"
        })
    
    # Report to master
    socketio.emit('cluster/slave_register', {
        'slave_id': self.slave_id,
        'hostname': socket.gethostname(),
        'outputs': outputs,
        'capabilities': {
            'max_resolution': '3840x2160',
            'fps': [30, 60],
            'codecs': ['h264', 'h265', 'hap']
        }
    }, namespace='/cluster')
```

#### Master UI: Output Routing

Master UI shows all outputs (local + remote) in output routing:

```
Output Routing
═══════════════════════════════════════════════════

Source: Video Player (clip_001)
 ↓
Select Output(s):

┌─────────────────────────────────────────────────┐
│ Local Outputs                                   │
├─────────────────────────────────────────────────┤
│ ☐ HDMI1 (local)       1920x1080 @ 60Hz         │
│ ☐ HDMI2 (local)       3840x2160 @ 30Hz         │
│ ☐ NDI1 (local)        Network output            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Slave: render-pc-1 (192.168.1.101)             │
├─────────────────────────────────────────────────┤
│ ☑ HDMI1 (slave1)      1920x1080 @ 60Hz         │
│ ☑ HDMI2 (slave1)      1920x1080 @ 60Hz         │
│ ☐ NDI1 (slave1)       Network output            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Slave: render-pc-2 (192.168.1.102)             │
├─────────────────────────────────────────────────┤
│ ☑ HDMI1 (slave2)      3840x2160 @ 30Hz         │
│ ☐ HDMI2 (slave2)      1920x1080 @ 60Hz         │
│ ☐ SPOUT1 (slave2)     Windows Spout             │
└─────────────────────────────────────────────────┘

[Apply Configuration]  [Test All Outputs]
```

#### Data Structure

```json
{
    "outputs": {
        "video_player": {
            "local": ["HDMI1"],
            "remote": [
                {"slave_id": "slave1", "output_id": "HDMI1"},
                {"slave_id": "slave1", "output_id": "HDMI2"},
                {"slave_id": "slave2", "output_id": "HDMI1"}
            ]
        }
    }
}
```

#### Command Flow

```python
# User selects outputs in master UI
# Master sends assignment command
{
    "type": "assign_outputs",
    "timestamp": 1234567890.123,
    "player_id": "video",
    "outputs": ["HDMI1", "HDMI2"]  # Slave-specific output IDs
}

# Slave receives command
def on_assign_outputs(data):
    self.active_outputs = data['outputs']
    self.output_manager.configure_outputs(self.active_outputs)
    log.info(f"Assigned outputs: {self.active_outputs}")
```

#### Benefits

✅ **Unified Interface** - All outputs (local + remote) in one place  
✅ **Auto Discovery** - No manual configuration of slave outputs  
✅ **Dynamic Reconfiguration** - Change output assignments live  
✅ **Hardware Awareness** - Master knows each slave's capabilities  
✅ **Multi-Protocol** - HDMI, NDI, SPOUT, virtual outputs all supported  
✅ **Validation** - Master can warn about incompatible assignments (e.g., 4K to 1080p output)  

#### Implementation Notes

- Slaves send output list on connect (and on hardware change)
- Master stores in `cluster_topology.json`
- UI uses dropdown/checkboxes to select outputs
- Output IDs are unique per slave: `slave1:HDMI1`, `slave2:HDMI1`
- Master tracks which outputs are active for status display
- Test pattern can be sent to verify all outputs work

### Master Discovery

Slaves locate the master via **explicit URL + config persistence**:

1. **First run:** provide `--master-url http://192.168.1.100:5000` (or `cluster set slave http://...` at runtime). The URL is saved to `config.json` under `cluster.master_url`.
2. **Subsequent runs:** `--master-url` is optional — the saved URL is used automatically. No flag needed after first setup.
3. **Override any time:** pass `--master-url` again to point to a different master (new value is saved).
4. **Stale URL:** if the master IP changes, update via `cluster set slave ws://new-ip:5000` or edit `config.json` directly.

```json
// config.json — persisted cluster settings
{
  "cluster": {
    "mode": "slave",            // "master" | "slave" | "standalone"
    "master_url": "http://192.168.1.100:5000",
    "slave_id": "FrontScreens",
    "last_connected": "2026-06-09T10:00:00Z"
  }
}
```

> **Why not mDNS/auto-discovery?** Auto-discovery is fragile in live venues (VLANs, firewalls, multiple instances on the same LAN). Explicit URL is predictable and works across subnets without extra dependencies.

---

### CLI Interface Design

**Simplified Commands (with dynamic output discovery):**

```bash
# Master mode (default)
python main.py

# Master with local rendering (also acts as render node)
python main.py --master --render-local HDMI1,HDMI2

# Slave mode — first run (URL saved to config.json automatically)
python main.py --slave --master-url http://192.168.1.100:5000

# Slave mode — subsequent runs (URL loaded from config.json, no flag needed)
python main.py --slave

# Slave with custom cache (first run)
python main.py --slave --master-url http://192.168.1.100:5000 \
               --cache-dir /mnt/fast-ssd/cache \
               --cache-size 100

# Slave with shared storage (optional performance boost)
python main.py --slave --master-url http://192.168.1.100:5000 \
               --shared-storage /mnt/shared/videos

# Headless slave (no status page)
python main.py --slave --master-url http://192.168.1.100:5000 --headless

# Slave with custom hostname
python main.py --slave --master-url http://192.168.1.100:5000 \
               --hostname "FrontProjectors"
```

**Key Changes from Earlier Design:**
- ❌ No `--outputs` CLI flag (outputs assigned dynamically from master UI)
- ✅ Slave auto-discovers and reports all available outputs
- ✅ Master UI selects which outputs are active per slave
- ✅ More flexible: Change output assignments without restarting slaves

**Argument Specification:**

```python
import argparse

parser = argparse.ArgumentParser(description='Py_artnet Multi-Video Render Cluster')

# Cluster mode
mode_group = parser.add_mutually_exclusive_group()
mode_group.add_argument('--master', action='store_true',
                        help='Run as master node (default)')
mode_group.add_argument('--slave', action='store_true',
                        help='Run as slave node (requires --master-url)')

parser.add_argument('--master-url', type=str, metavar='URL',
                    help='Master node HTTP base URL (e.g., http://192.168.1.100:5000). '
                         'Saved to config.json on first use; optional on subsequent runs.')

# Master options
parser.add_argument('--render-local', type=str, metavar='OUTPUTS',
                    help='Master also renders these local outputs (comma-separated)')

# Slave identification
parser.add_argument('--hostname', type=str,
                    help='Custom hostname for slave identification (default: system hostname)')
parser.add_argument('--slave-id', type=str,
                    help='Custom slave ID (default: auto-generated from hostname)')

# File distribution
parser.add_argument('--shared-storage', type=str, action='append', metavar='PATH',
                    help='Shared storage path (can specify multiple, checked in order)')
parser.add_argument('--cache-dir', type=str, default='/tmp/cluster_cache',
                    help='Cache directory for HTTP-downloaded files')
parser.add_argument('--cache-size', type=int, default=50,
                    help='Max cache size in GB')

# Time synchronization
parser.add_argument('--time-sync', choices=['ntp', 'master_clock'], default='ntp',
                    help='Time synchronization method (default: ntp)')
parser.add_argument('--ntp-server', type=str,
                    help='NTP server address (for --time-sync=ntp)')

# UI mode
parser.add_argument('--headless', action='store_true',
                    help='Run without web UI (slave only)')

# Network binding
parser.add_argument('--host', type=str, default='0.0.0.0',
                    help='Bind address for web server')
parser.add_argument('--port', type=int, default=5000,
                    help='Web server port')

# Autonomous mode (Phase 2)
parser.add_argument('--autonomous', action='store_true',
                    help='Enable autonomous playback mode (requires NTP and cache)')
parser.add_argument('--autonomous-timeout', type=int, default=300,
                    help='Max duration for autonomous playback (seconds)')
```

**Runtime CLI Commands (while app is running):**

The cluster mode can also be switched at runtime without restarting, via the existing CLI command interface:

```
# Switch to master mode at runtime
cluster set master

# Switch to slave mode at runtime (master-url required if not already set)
cluster set slave http://192.168.1.100:5000

# Switch to slave using last-saved or auto-discovered master URL
cluster set slave

# Show current cluster status
cluster status

# Reconnect to master (useful after network interruption)
cluster reconnect

# Disconnect from cluster (standalone mode)
cluster disconnect
```

> **Note:** Switching mode at runtime stops all active rendering. On `cluster set slave` the node immediately attempts to connect and sync state from the master.

**Example Configurations:**

```bash
# ── Scenario: Small club with 2 slaves ──────────────────────────────────────

# Master
python main.py --master

# Slave 1 (front screens) — first run: URL saved to config.json
python main.py --slave --master-url http://192.168.1.100:5000 --hostname "FrontScreens"

# Slave 2 (side walls) — first run
python main.py --slave --master-url http://192.168.1.100:5000 --hostname "SideWalls"

# After first run, slaves restart without --master-url:
python main.py --slave --hostname "FrontScreens"
python main.py --slave --hostname "SideWalls"

# Then assign HDMI1+HDMI2 to each slave from master UI

# ── Scenario: Large venue with shared NAS ───────────────────────────────────

# Master
python main.py --master

# Slaves — HTTP primary, NAS skips download if file already present
python main.py --slave --master-url http://192.168.1.100:5000 \
               --cache-dir /tmp/cache \
               --shared-storage /mnt/nas/videos

# ── Time sync options ───────────────────────────────────────────────────────

# Default: NTP (all nodes configured to same NTP source externally)
python main.py --master
python main.py --slave  # --master-url loaded from config.json

# Fallback: Master clock broadcast (no NTP source available)
python main.py --master --time-sync master_clock
python main.py --slave --time-sync master_clock
```

---

## 🚦 Implementation Roadmap

### Phase 1: Core Cluster (16-24h)

**Goal:** Basic master/slave with command replication

1. **CLI & Initialization (2-3h)**
   - Argument parsing
   - Master/slave mode detection
   - WebSocket server/client setup
   - Output assignment from CLI

2. **Command Broadcast Engine (4-6h)**
   - Command serialization
   - WebSocket broadcast to slaves
   - Command queue & deduplication
   - Error handling & retries

3. **State Replication (3-4h)**
   - Full snapshot on connect
   - Delta updates
   - Version tracking
   - Conflict resolution

4. **NTP Time Sync (2-3h)**
   - Configure all nodes to use the same NTP source (e.g. `pool.ntp.org`, `time.windows.com`, or a local master-hosted NTP server)
   - Heartbeat fallback if NTP unavailable
   - Drift monitoring

5. **Timestamp-Based Rendering (3-4h)**
   - Calculate frame from timestamp
   - Synchronize playback start
   - Handle effects at timestamps
   - Transition timing

6. **Minimal Slave UI (2-3h)**
   - Status page (`/status`)
   - Cache status display
   - Sync metrics
   - Error log

### Phase 2: File Distribution (12-18h)

See [File Distribution System](#-file-distribution-system) section for details.

7. **Master File Server (4-6h)**
   - HTTP file serving
   - SHA256 hash computation
   - File manifest generation
   - Range request support

8. **Slave Cache Manager (4-6h)**
   - Hash-based cache storage
   - File fetching & validation
   - Metadata management
   - Cache warming

9. **Frontend Integration (3-5h)**
   - Cache status indicators
   - Warming progress UI
   - Cluster dashboard

10. **Testing & Optimization (1-2h)**
    - Multi-node testing
    - Performance tuning
    - Error recovery

### Phase 3: Advanced Features (12-18h)

11. **NTP Time Sync (2-3h)**
    - Optional NTP mode
    - Configuration UI
    - Accuracy monitoring

12. **Dynamic Output Assignment (3-4h)**
    - Master UI for slave management
    - Drag-and-drop output assignment
    - Save assignments to master

13. **Health Monitoring (2-3h)**
    - Node discovery (mDNS)
    - Heartbeat monitoring
    - Performance metrics
    - Network topology graph

14. **Failover & Resilience (3-4h)**
    - Auto-reconnect logic
    - Continue-on-disconnect mode
    - Leader election (Phase 3)

15. **Cluster Dashboard (2-3h)**
    - Master UI: Slave list
    - Real-time status
    - FPS, latency, cache metrics
    - Command history

---

## 🧪 Testing Strategy

### Test Scenarios

| Test | Description | Expected Result | Pass Criteria |
|------|-------------|-----------------|---------------|
| **Basic Sync** | 2 slaves play same video | Both outputs identical | Visual inspection |
| **Effect Sync** | Apply blur effect on master | Both slaves show blur | Pixel-perfect match |
| **Transition Sync** | Fade between clips | Smooth synchronized fade | ±1 frame tolerance |
| **Cache Hit** | Play cached video | Instant playback | No network traffic |
| **Cache Miss** | Play new video | Auto-download then play | Progress indicator shows |
| **Hash Validation** | Corrupt cached file | Re-download from master | File replaced |
| **Network Failure** | Disconnect master | Slaves pause (or continue) | Config-dependent |
| **Clock Drift** | Long playback (1 hour) | No visible desync | <100ms drift |
| **Multi-Layer** | Base + 2 overlay layers | All slaves identical | Blend modes match |
| **High Load** | 10 slaves, 4K video | Smooth playback | >25 FPS all nodes |

### Performance Benchmarks

**Target Metrics:**

| Metric | Target | Excellent | Acceptable |
|--------|--------|-----------|------------|
| **Sync Accuracy** | ±10ms | ±5ms | ±50ms |
| **Command Latency** | <20ms | <10ms | <100ms |
| **Cache Download** | 50 MB/s | 100 MB/s | 10 MB/s |
| **CPU Overhead** | <5% | <2% | <10% |
| **Memory Overhead** | <100 MB | <50 MB | <500 MB |
| **Network Bandwidth** | <1 Mbps | <500 Kbps | <5 Mbps |

---

## 📊 Use Cases & ROI

### Typical Installations

**Small Club (2-4 outputs)**
- 1 Master PC (with UI)
- 1-2 Slave PCs (2 outputs each)
- Local network (1 Gbps)
- Total cost: 3 PCs (~$3000)
- vs. 4× standalone systems: $12,000+ saved

**Medium Venue (8-16 outputs)**
- 1 Master PC
- 4-8 Slave PCs (2 outputs each)
- Managed switch (1 Gbps)
- Total cost: 9 PCs + switch (~$10,000)
- vs. 16× standalone: $48,000+ saved

**Large Installation (50+ outputs)**
- 1 Master PC
- 25+ Slave PCs
- 10 Gbps backbone
- Total cost: ~$30,000
- vs. 50× standalone: $150,000+ saved
- **Enterprise-grade synchronization** not possible with standalone systems

### Competitive Analysis

| Feature | Py_artnet Cluster | Resolume Arena | Dataton Watchout | d3 Technologies |
|---------|-------------------|----------------|------------------|-----------------|
| **Price** | Free (open source) | $699/seat | $3000+/seat | $10,000+/seat |
| **Max Outputs** | Unlimited | 16 (per seat) | 64+ | 128+ |
| **Sync Method** | Command replication | Timecode/MIDI | Hardware lock | Genlock/Timecode |
| **File Distribution** | HTTP + cache | Manual/shared | Manual/shared | Manual/shared |
| **Setup Time** | 10 minutes | 30 minutes | Hours | Days |
| **Licensing** | Free | Per-node | Per-node | Per-node |
| **3D Visualizer** | Planned (P2) | - | ✓ | ✓ |
| **DMX Control** | Planned (P2) | ✓ | - | ✓ |

**Unique Advantages:**
- ✅ Zero frame streaming (lowest latency)
- ✅ Infinite scaling (command replication)
- ✅ Automatic file distribution
- ✅ Free & open source
- ✅ Simple setup (one command)

---

## 🎯 Success Criteria

### MVP (Minimum Viable Product)

A successful MVP must demonstrate:

✅ **Master/Slave Communication**
- [x] Slave connects to master via WebSocket
- [x] Master broadcasts commands
- [x] Slave receives and executes commands

✅ **Basic Synchronization**
- [x] Play same video on 2+ slaves
- [x] Visual sync within ±50ms (tolerable)
- [x] No frame streaming (commands only)

✅ **File Distribution**
- [x] Slave fetches file from master HTTP
- [x] File cached locally with hash validation
- [x] Second playback uses cache (no network)

✅ **Effect/Transition Sync**
- [x] Apply effect on master → slaves match
- [x] Transition on master → slaves synchronized

✅ **Basic Monitoring**
- [x] Slave status page shows connection state
- [x] Cache status visible
- [x] Error logs accessible

### Production Ready

For production use, additionally required:

✅ **Advanced Sync**
- [ ] Clock drift <10ms over 1 hour
- [ ] Optional NTP mode for ±1ms accuracy
- [ ] Automatic clock correction

✅ **Resilience**
- [ ] Auto-reconnect on network failure
- [ ] Graceful degradation (continue or pause)
- [ ] Error recovery without restart

✅ **Management UI**
- [ ] Master dashboard showing all slaves
- [ ] Drag-and-drop output assignment
- [ ] Cache warming from UI
- [ ] Performance metrics

✅ **Documentation**
- [ ] Setup guide (step-by-step)
- [ ] Network configuration examples
- [ ] Troubleshooting guide
- [ ] Video tutorials

---

*Last Updated: January 16, 2026*
