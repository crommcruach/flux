# Dual Player Architecture - Output + Preview System

## Problem Statement
Current limitation: Single player instance per type (video/artnet) cannot simultaneously:
- Run ACTIVE playlist (for Art-Net output)
- Preview VIEWED playlist (different from active, for UI exploration)

## Proposed Architecture

### Four Player Instances

```
┌─────────────────────────────────────────────────────┐
│                PlayerManager                         │
├─────────────────────────────────────────────────────┤
│                                                       │
│  OUTPUT PLAYERS (Active Playlist)                    │
│  ├─ video_player         → Canvas/Preview Stream     │
│  └─ artnet_player        → Art-Net/DMX Output        │
│                                                       │
│  PREVIEW PLAYERS (Viewed Playlist, if different)     │
│  ├─ video_preview_player → Preview Canvas           │
│  └─ artnet_preview_player→ Preview Visualization     │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Player Initialization

```python
class PlayerManager:
    def __init__(self, player=None, artnet_player=None, socketio=None):
        # OUTPUT PLAYERS (always running, control physical output)
        self.video_player = player              # enable_artnet=False
        self.artnet_player = artnet_player      # enable_artnet=True
        
        # PREVIEW PLAYERS (on-demand, UI only)
        self.video_preview_player = None        # enable_artnet=False
        self.artnet_preview_player = None       # enable_artnet=False
        
        self.players = {
            'video': self.video_player,
            'artnet': self.artnet_player,
            'video_preview': self.video_preview_player,
            'artnet_preview': self.artnet_preview_player
        }
```

### Player Usage Matrix

| Player Instance          | Art-Net | Purpose                    | Playlist Source      |
|--------------------------|---------|----------------------------|----------------------|
| video_player             | ❌      | Video canvas output        | Active playlist      |
| artnet_player            | ✅      | DMX/Art-Net output         | Active playlist      |
| video_preview_player     | ❌      | Preview canvas             | Viewed playlist      |
| artnet_preview_player    | ❌      | Preview visualization      | Viewed playlist      |

## Implementation Plan

### Phase 1: PlayerManager Enhancement

**File**: `src/modules/player_manager.py`

```python
def create_preview_players(self):
    """Create preview player instances on-demand."""
    if self.video_preview_player is None:
        # Clone video player configuration
        self.video_preview_player = Player(
            frame_source=VideoSource(None),  # Empty source
            points_json_path=self.video_player.points_json_path,
            target_ip=self.video_player.target_ip,
            start_universe=self.video_player.start_universe,
            fps_limit=self.video_player.fps_limit,
            config=self.video_player.config,
            enable_artnet=False,  # NO OUTPUT
            player_name="VideoPreview",
            clip_registry=self.video_player.clip_registry
        )
    
    if self.artnet_preview_player is None:
        # Clone artnet player configuration
        self.artnet_preview_player = Player(
            frame_source=VideoSource(None),
            points_json_path=self.artnet_player.points_json_path,
            target_ip=self.artnet_player.target_ip,
            start_universe=self.artnet_player.start_universe,
            fps_limit=self.artnet_player.fps_limit,
            config=self.artnet_player.config,
            enable_artnet=False,  # NO OUTPUT
            player_name="ArtNetPreview",
            clip_registry=self.artnet_player.clip_registry
        )
    
    # Update player registry
    self.players['video_preview'] = self.video_preview_player
    self.players['artnet_preview'] = self.artnet_preview_player

def destroy_preview_players(self):
    """Clean up preview players when not needed."""
    if self.video_preview_player:
        self.video_preview_player.stop()
        self.video_preview_player = None
    if self.artnet_preview_player:
        self.artnet_preview_player.stop()
        self.artnet_preview_player = None
```

### Phase 2: Playlist System Integration

**File**: `src/modules/playlist_manager.py`

```python
def apply_playlist_to_preview(self, playlist_id: str, player_manager):
    """
    Load playlist into PREVIEW players (not output players).
    Used when viewing non-active playlist.
    """
    playlist = self.playlists.get(playlist_id)
    if not playlist:
        return False
    
    # Create preview players if needed
    player_manager.create_preview_players()
    
    # Get player states
    video_state = playlist.get_player_state('video')
    artnet_state = playlist.get_player_state('artnet')
    
    # Apply to PREVIEW players
    if video_state:
        preview_player = player_manager.video_preview_player
        preview_player.playlist = video_state.clips.copy()
        preview_player.playlist_ids = video_state.clip_ids.copy()
        preview_player.autoplay = video_state.autoplay
        preview_player.loop_playlist = video_state.loop
        preview_player.load_clip_by_index(0)  # Load first clip
    
    if artnet_state:
        preview_player = player_manager.artnet_preview_player
        preview_player.playlist = artnet_state.clips.copy()
        preview_player.playlist_ids = artnet_state.clip_ids.copy()
        preview_player.autoplay = artnet_state.autoplay
        preview_player.loop_playlist = artnet_state.loop
        preview_player.load_clip_by_index(0)
    
    return True
```

### Phase 3: API Endpoints

**File**: `src/modules/api_playlists.py`

```python
@app.route('/api/playlists/<playlist_id>/preview-clip', methods=['POST'])
def preview_clip_endpoint(playlist_id):
    """Load clip for preview (uses preview players if not active)."""
    data = request.get_json()
    player_id = data.get('player_id')  # 'video' or 'artnet'
    clip_index = data.get('clip_index')
    
    is_active = playlist_id == playlist_system.active_playlist_id
    
    if is_active:
        # Active playlist: Use main output players
        player = player_manager.get_player(player_id)
        player.load_clip_by_index(clip_index)
        return jsonify({"success": True, "mode": "output"})
    else:
        # Non-active: Use preview players
        player_manager.create_preview_players()
        preview_player_id = f"{player_id}_preview"
        preview_player = player_manager.get_player(preview_player_id)
        
        # Load playlist into preview player
        playlist_system.apply_playlist_to_preview(playlist_id, player_manager)
        
        # Load specific clip
        preview_player.load_clip_by_index(clip_index)
        
        return jsonify({
            "success": True,
            "mode": "preview_live",
            "note": "Preview player running independently"
        })
```

### Phase 4: Streaming Endpoints

**File**: `src/modules/api_outputs.py`

Add new preview stream endpoints:

```python
@app.route('/api/outputs/video/stream/preview_live')
def video_preview_stream():
    """MJPEG stream from video preview player."""
    player_manager.create_preview_players()
    preview_player = player_manager.video_preview_player
    return Response(
        generate_preview_stream(preview_player),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/outputs/artnet/stream/preview_live')
def artnet_preview_stream():
    """MJPEG stream from artnet preview player."""
    player_manager.create_preview_players()
    preview_player = player_manager.artnet_preview_player
    return Response(
        generate_preview_stream(preview_player),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
```

### Phase 5: Frontend Updates

**File**: `frontend/js/player.js`

```javascript
// Update preview image sources based on active/viewed state
function updatePreviewSources() {
    const isActive = viewedPlaylistId === activePlaylistId;
    
    const videoPreviewImg = document.getElementById('videoPreviewImg');
    const artnetPreviewImg = document.getElementById('artnetPreviewImg');
    
    if (isActive) {
        // Show main output streams
        videoPreviewImg.src = `${API_BASE}/api/outputs/video/stream/preview_virtual`;
        artnetPreviewImg.src = `${API_BASE}/api/outputs/artnet/stream/preview_virtual`;
    } else {
        // Show preview player streams
        videoPreviewImg.src = `${API_BASE}/api/outputs/video/stream/preview_live`;
        artnetPreviewImg.src = `${API_BASE}/api/outputs/artnet/stream/preview_live`;
    }
}
```

## Performance Considerations

### Resource Usage
- **4 Players Running**: ~2x memory usage
- **Preview players idle when not viewing**: Minimal CPU impact
- **Destroy preview players**: When switching back to active playlist

### Optimization Strategies

1. **Lazy Initialization**: Create preview players only when needed
2. **Automatic Cleanup**: Destroy preview players after 5 minutes of inactivity
3. **Reduced FPS**: Run preview players at lower FPS (15 instead of 30)
4. **Shared Resources**: Share points/config between output and preview players

```python
# Reduced FPS for preview
self.video_preview_player = Player(
    fps_limit=15,  # Lower FPS for preview
    enable_artnet=False,
    player_name="VideoPreview"
)
```

## Migration Path

### Step 1: Add Preview Players (Non-Breaking)
- Add preview player instances to PlayerManager
- Keep existing single-player behavior as default

### Step 2: Update API Endpoints
- Detect active vs viewed playlist
- Route to appropriate player instance

### Step 3: Update Frontend
- Switch preview image sources based on playlist state
- Add loading indicators for preview players

### Step 4: Testing
- Test memory usage with 4 players
- Verify Art-Net output unaffected by preview
- Test autoplay behavior in preview mode

### Step 5: Cleanup Old Code
- Remove static thumbnail fallback code
- Remove "preview_isolated" mode
- Streamline preview logic

## Benefits

✅ **True Live Preview**: See actual playlist behavior (autoplay, transitions)  
✅ **Perfect Isolation**: Active playlist never affected by preview  
✅ **Professional Workflow**: Explore playlists safely during shows  
✅ **Test Autoplay**: Preview autoplay behavior before activation  
✅ **Simultaneous Playback**: Output and preview run independently  

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| High memory usage | Performance degradation | Lazy init, auto-cleanup after 5 min |
| CPU overhead | Frame drops | Lower FPS for preview (15 fps) |
| Complex state management | Bugs | Clear player ID naming, extensive testing |
| Art-Net interference | Output corruption | Preview players have `enable_artnet=False` |

## Alternative Approaches

### Option 1: Single Preview Player (Lighter)
- Only create video_preview_player
- Art-Net preview uses static visualization
- Reduces memory by 50%

### Option 2: Shared Player with Mode Flag
- Single player with `preview_mode` flag
- Toggle between output and preview
- Less memory, but requires context switching

### Option 3: Virtual Players (Future)
- Lightweight player instances without full rendering
- Only compute state, not frames
- Requires significant refactoring

## Recommendation

**Implement Full Dual-Player System** (4 players) because:
1. Clean separation of concerns
2. No risk of output interference
3. True preview functionality
4. Memory usage acceptable for modern systems (~500MB total)
5. Easier to debug and maintain

## Timeline Estimate

- Phase 1 (PlayerManager): 2-3 hours
- Phase 2 (Playlist Integration): 2 hours
- Phase 3 (API Endpoints): 1-2 hours
- Phase 4 (Streaming): 1 hour
- Phase 5 (Frontend): 2-3 hours
- Testing & Debugging: 3-4 hours

**Total**: ~12-15 hours of development
