# Non-Active Playlist Preview Implementation Guide

## Overview
This guide outlines how to implement preview functionality for non-active playlists without interrupting the currently playing (active) playlist.

**Status**: 🟡 Planning Phase  
**Complexity**: High  
**Estimated Time**: 2-3 days  
**Priority**: Low (workaround available)

---

## Current Architecture

### Singleton Players
```python
# src/modules/player_manager.py
class PlayerManager:
    def __init__(self):
        self.video_player = VideoPlayer(...)  # Single instance
        self.artnet_player = ArtNetPlayer(...)  # Single instance
        self.active_playlist = None
```

**Problem**: Only the active playlist can control these singleton players.

### Playlist Binding
- Active playlist → Controls physical output
- Viewed playlist → UI display only, no preview capability

---

## Proposed Architecture

### 1. Preview Player System

#### A. Create PreviewPlayer Class
**File**: `src/modules/preview_player.py`

```python
class PreviewPlayer:
    """
    Lightweight player for previewing clips from non-active playlists.
    Does NOT output to DMX/Art-Net, only renders to preview canvas.
    """
    
    def __init__(self, width=640, height=360):
        """Initialize with lower resolution for performance"""
        self.width = width
        self.height = height
        self.is_active = False
        self.current_clip = None
        self.video_source = None
        self.preview_frame_buffer = None
        
    def load_clip(self, clip_path, start_time=0):
        """Load a clip for preview"""
        pass
        
    def play(self):
        """Start preview playback"""
        pass
        
    def pause(self):
        """Pause preview"""
        pass
        
    def stop(self):
        """Stop and cleanup resources"""
        pass
        
    def get_preview_frame(self):
        """Return current frame as base64 for frontend"""
        pass
        
    def cleanup(self):
        """Release video decoder and resources"""
        pass
```

**Key Features**:
- Independent from main players
- Lower resolution (640x360 or 854x480) for performance
- No DMX/Art-Net output
- Lazy initialization (created only when needed)
- Auto-cleanup after inactivity

---

#### B. Update PlayerManager
**File**: `src/modules/player_manager.py`

```python
class PlayerManager:
    def __init__(self):
        # Main players (existing)
        self.video_player = VideoPlayer(...)
        self.artnet_player = ArtNetPlayer(...)
        
        # Preview system (new)
        self.preview_player = None  # Lazy init
        self.preview_active = False
        self.preview_playlist_id = None
        
    def get_preview_player(self):
        """Get or create preview player"""
        if self.preview_player is None:
            self.preview_player = PreviewPlayer(width=640, height=360)
        return self.preview_player
        
    def cleanup_preview_player(self):
        """Dispose preview player when not needed"""
        if self.preview_player:
            self.preview_player.cleanup()
            self.preview_player = None
            self.preview_active = False
```

---

### 2. API Endpoints

#### A. New Preview Routes
**File**: `src/modules/api_player_unified.py`

```python
# ========================================
# PREVIEW PLAYER (Non-Active Playlists)
# ========================================

@app.route('/api/preview/load', methods=['POST'])
def preview_load_clip():
    """
    Load a clip into preview player (doesn't affect active playlist)
    
    POST body:
    {
        "playlist_id": "video" or "artnet",
        "clip_index": 0,
        "start_time": 0  (optional)
    }
    """
    try:
        data = request.get_json()
        playlist_id = data.get('playlist_id')
        clip_index = data.get('clip_index', 0)
        start_time = data.get('start_time', 0)
        
        # Check if this playlist is active
        active_id = get_active_playlist_id()
        if playlist_id == active_id:
            return jsonify({
                'success': False,
                'error': 'Cannot preview active playlist. Use regular preview instead.'
            }), 400
        
        # Get clip from non-active playlist
        playlist = get_playlist(playlist_id)
        if clip_index >= len(playlist.clips):
            return jsonify({'success': False, 'error': 'Invalid clip index'}), 400
            
        clip = playlist.clips[clip_index]
        
        # Load into preview player
        preview_player = player_manager.get_preview_player()
        preview_player.load_clip(clip.path, start_time)
        player_manager.preview_active = True
        player_manager.preview_playlist_id = playlist_id
        
        return jsonify({
            'success': True,
            'clip': {
                'name': clip.name,
                'duration': clip.duration,
                'path': clip.path
            }
        })
        
    except Exception as e:
        logger.error(f"Preview load error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preview/play', methods=['POST'])
def preview_play():
    """Start preview playback"""
    try:
        preview_player = player_manager.get_preview_player()
        preview_player.play()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preview/pause', methods=['POST'])
def preview_pause():
    """Pause preview playback"""
    try:
        preview_player = player_manager.get_preview_player()
        preview_player.pause()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preview/stop', methods=['POST'])
def preview_stop():
    """Stop preview and cleanup"""
    try:
        player_manager.cleanup_preview_player()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preview/frame', methods=['GET'])
def preview_get_frame():
    """Get current preview frame (base64 encoded)"""
    try:
        if not player_manager.preview_active:
            return jsonify({'success': False, 'error': 'Preview not active'}), 404
            
        preview_player = player_manager.get_preview_player()
        frame_base64 = preview_player.get_preview_frame()
        
        return jsonify({
            'success': True,
            'frame': frame_base64,
            'timestamp': preview_player.current_time
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

---

### 3. Frontend Changes

#### A. Add Preview Panel Component
**File**: `frontend/css/preview-panel.css` (new)

```css
.preview-panel {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 400px;
    height: 280px;
    background: #1a1a1a;
    border: 2px solid #667eea;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    z-index: 9999;
    display: none;
}

.preview-panel.active {
    display: block;
}

.preview-panel-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 8px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-radius: 6px 6px 0 0;
}

.preview-panel-canvas {
    width: 100%;
    height: calc(100% - 80px);
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
}

.preview-panel-canvas img {
    max-width: 100%;
    max-height: 100%;
}

.preview-panel-controls {
    padding: 8px;
    display: flex;
    gap: 8px;
    background: #2a2a2a;
    border-radius: 0 0 6px 6px;
}

.preview-panel-badge {
    background: #ff6b6b;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: bold;
}
```

#### B. Preview Panel JavaScript
**File**: `frontend/js/preview-panel.js` (new)

```javascript
class PreviewPanel {
    constructor() {
        this.isActive = false;
        this.updateInterval = null;
        this.currentPlaylistId = null;
        this.currentClipIndex = null;
        
        this.initPanel();
    }
    
    initPanel() {
        // Create preview panel HTML
        const panel = document.createElement('div');
        panel.id = 'previewPanel';
        panel.className = 'preview-panel';
        panel.innerHTML = `
            <div class="preview-panel-header">
                <span>
                    <strong>Preview Mode</strong>
                    <span class="preview-panel-badge">NON-ACTIVE</span>
                </span>
                <button class="btn btn-sm btn-danger" onclick="previewPanel.close()">✕</button>
            </div>
            <div class="preview-panel-canvas">
                <img id="previewFrameImg" src="" alt="Preview">
            </div>
            <div class="preview-panel-controls">
                <button class="btn btn-sm btn-success" onclick="previewPanel.play()">▶️</button>
                <button class="btn btn-sm btn-warning" onclick="previewPanel.pause()">⏸️</button>
                <button class="btn btn-sm btn-danger" onclick="previewPanel.stop()">⏹️</button>
                <span id="previewTime" class="ms-auto">0:00</span>
            </div>
        `;
        document.body.appendChild(panel);
    }
    
    async open(playlistId, clipIndex) {
        try {
            // Load clip into preview player
            const response = await fetch('/api/preview/load', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    playlist_id: playlistId,
                    clip_index: clipIndex,
                    start_time: 0
                })
            });
            
            const data = await response.json();
            if (!data.success) {
                showToast('❌ ' + data.error, 'error');
                return;
            }
            
            this.currentPlaylistId = playlistId;
            this.currentClipIndex = clipIndex;
            this.isActive = true;
            
            document.getElementById('previewPanel').classList.add('active');
            
            // Start frame updates
            this.startFrameUpdates();
            
        } catch (error) {
            console.error('Preview open error:', error);
            showToast('❌ Failed to open preview', 'error');
        }
    }
    
    startFrameUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        this.updateInterval = setInterval(async () => {
            try {
                const response = await fetch('/api/preview/frame');
                const data = await response.json();
                
                if (data.success && data.frame) {
                    document.getElementById('previewFrameImg').src = 
                        `data:image/jpeg;base64,${data.frame}`;
                    document.getElementById('previewTime').textContent = 
                        this.formatTime(data.timestamp);
                }
            } catch (error) {
                console.error('Frame update error:', error);
            }
        }, 33); // ~30fps
    }
    
    async play() {
        await fetch('/api/preview/play', {method: 'POST'});
    }
    
    async pause() {
        await fetch('/api/preview/pause', {method: 'POST'});
    }
    
    async stop() {
        await fetch('/api/preview/stop', {method: 'POST'});
        this.close();
    }
    
    close() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
        
        this.isActive = false;
        document.getElementById('previewPanel').classList.remove('active');
        
        // Cleanup backend
        fetch('/api/preview/stop', {method: 'POST'});
    }
    
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
}

// Initialize global instance
const previewPanel = new PreviewPanel();
window.previewPanel = previewPanel;
```

#### C. Update Playlist UI
**File**: `frontend/js/player.js`

Add preview button to non-active playlist items:

```javascript
function renderPlaylistItem(clip, index, playlistId) {
    const isActive = (playlistId === getActivePlaylistId());
    
    // ... existing code ...
    
    // Add preview button for non-active playlists
    if (!isActive) {
        const previewBtn = document.createElement('button');
        previewBtn.className = 'btn btn-sm btn-info';
        previewBtn.innerHTML = '👁️ Preview';
        previewBtn.title = 'Preview this clip (opens in preview panel)';
        previewBtn.onclick = () => {
            previewPanel.open(playlistId, index);
        };
        itemElement.appendChild(previewBtn);
    }
    
    // ... rest of code ...
}
```

---

### 4. Resource Management

#### A. Auto-Cleanup Strategy

```python
# src/modules/preview_player.py

import threading
import time

class PreviewPlayer:
    def __init__(self, width=640, height=360):
        # ... existing init ...
        self.last_activity = time.time()
        self.inactivity_timeout = 300  # 5 minutes
        self.cleanup_thread = None
        
    def start_inactivity_timer(self):
        """Start background thread to cleanup after inactivity"""
        if self.cleanup_thread is None:
            self.cleanup_thread = threading.Thread(
                target=self._inactivity_monitor, 
                daemon=True
            )
            self.cleanup_thread.start()
    
    def _inactivity_monitor(self):
        """Monitor inactivity and auto-cleanup"""
        while True:
            time.sleep(30)  # Check every 30s
            
            if time.time() - self.last_activity > self.inactivity_timeout:
                logger.info("Preview player inactive, cleaning up...")
                self.cleanup()
                break
    
    def touch_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()
```

#### B. Memory Limits

```python
# Limit preview player resources
MAX_PREVIEW_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB
PREVIEW_RESOLUTION = (640, 360)  # Lower than main player
PREVIEW_FPS_LIMIT = 30  # Cap frame rate
```

---

### 5. Implementation Steps

#### Phase 1: Backend Foundation
1. ✅ Create `PreviewPlayer` class
2. ✅ Add preview routes to API
3. ✅ Update `PlayerManager` with preview support
4. ✅ Add resource management and cleanup
5. ✅ Test preview player independently

#### Phase 2: Frontend Integration
1. ✅ Create preview panel CSS
2. ✅ Create `PreviewPanel` JavaScript class
3. ✅ Add preview buttons to non-active playlists
4. ✅ Implement frame streaming (WebSocket or polling)
5. ✅ Add keyboard shortcuts (P for preview)

#### Phase 3: Polish & Edge Cases
1. ✅ Handle preview during playlist switching
2. ✅ Add preview to artnet playlist (if applicable)
3. ✅ Implement drag-to-resize preview panel
4. ✅ Add "picture-in-picture" mode option
5. ✅ Error handling and recovery
6. ✅ Performance optimization

#### Phase 4: Testing
1. ✅ Test preview while active playlist is playing
2. ✅ Test resource cleanup after inactivity
3. ✅ Test multiple clip previews in sequence
4. ✅ Test edge cases (file missing, corrupted, etc.)
5. ✅ Performance benchmarks

---

### 6. Potential Challenges

#### Challenge 1: Video Decoder Limits
**Problem**: Some systems limit concurrent video decoders
**Solution**: 
- Use software decoder for preview (lower quality, more CPU)
- Limit preview resolution to reduce resource usage
- Queue preview requests if decoder unavailable

#### Challenge 2: Frame Rate Performance
**Problem**: Updating preview at 30fps may impact main player
**Solution**:
- Lower preview frame rate (15-20fps acceptable)
- Use WebSocket for efficient frame streaming
- Skip frames if backend is busy

#### Challenge 3: Art-Net Preview
**Problem**: Can't output DMX from preview player
**Solution**:
- Show simulated LED output (render pixels as image)
- Use the points file to map pixels to visual representation
- Optional: Add "virtual LED matrix" visualization

---

### 7. Alternative Approaches

#### Option A: Thumbnail-Based Preview
Instead of live playback, generate thumbnail strips:
- Faster and lighter
- Good for quick browsing
- No resource conflicts
- **Downside**: Not real playback preview

#### Option B: Pause Main Player
- Pause active playlist
- Switch to preview mode
- Resume after preview
- **Downside**: Interrupts performance

#### Option C: Dual Monitor Setup
- Main output on monitor 1
- Preview output on monitor 2
- Both run simultaneously
- **Downside**: Requires specific hardware setup

---

### 8. Testing Checklist

- [ ] Preview non-active video playlist while artnet is active
- [ ] Preview non-active artnet playlist while video is active
- [ ] Preview auto-stops after inactivity
- [ ] Preview player releases resources properly
- [ ] Main player unaffected by preview operations
- [ ] Preview panel is draggable and resizable
- [ ] Multiple sequential previews work correctly
- [ ] Preview handles missing/corrupted files gracefully
- [ ] Preview works with different video codecs
- [ ] Performance acceptable on lower-end hardware

---

### 9. Future Enhancements

1. **Preview Scrubbing** - Seek through clip in preview
2. **Preview Effects** - Show effects in preview player
3. **Multi-Clip Preview** - Preview transitions between clips
4. **Preview Recording** - Record preview output
5. **Remote Preview** - Stream preview to mobile device
6. **Preview Overlay** - Show preview as overlay on main canvas

---

### 10. Configuration

Add to `config.json`:

```json
{
  "preview": {
    "enabled": true,
    "resolution": {
      "width": 640,
      "height": 360
    },
    "fps_limit": 30,
    "inactivity_timeout": 300,
    "max_buffer_size_mb": 10,
    "auto_cleanup": true,
    "panel_position": "bottom-right",
    "allow_artnet_preview": true
  }
}
```

---

## Conclusion

This implementation provides a complete preview system for non-active playlists without disrupting the main playback. The architecture is:
- **Independent**: Preview player is separate from main players
- **Efficient**: Lower resolution, lazy initialization, auto-cleanup
- **Safe**: Cannot interfere with active playlist
- **User-friendly**: Floating panel with intuitive controls

**Estimated Implementation Time**: 16-24 hours  
**Recommended Priority**: Medium (nice-to-have, not critical)

---

## Related Documentation
- [MULTI_PLAYLIST_SYSTEM.md](MULTI_PLAYLIST_SYSTEM.md)
- [PLAYER_EXECUTION_FLOW.md](PLAYER_EXECUTION_FLOW.md)
- [PERFORMANCE.md](PERFORMANCE.md)
