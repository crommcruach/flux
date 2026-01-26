# Multi-Playlist System Implementation Plan

## 📋 Overview

Implementation of a multi-playlist system allowing users to work with multiple independent playlists simultaneously. Primary use cases:
- **Live Mixing Playlist**: Quick access, manual navigation, live performance
- **Sequence Playlist**: Automated sequences, timed transitions, pre-programmed shows

**No backwards compatibility required** - Clean slate implementation.

### Key Concept: Active vs. Viewed Playlist

**CRITICAL DISTINCTION**:
- **Active Playlist** = Which playlist is controlling playback (runs in background, repeats/loops)
- **Viewed Playlist** = Which playlist the GUI is displaying for editing

**These are SEPARATE!** User can:
1. Have Playlist A actively playing in the background (with autoplay/loop)
2. Edit Playlist B in the GUI (add/remove/reorder clips)
3. Right-click Playlist B → "Activate" to make it the active playlist

**Example Workflow**:
- Active: "Show Sequence" (playing video 3/10, autoplay ON, looping)
- Viewed: "Live Mixing" (user editing, adding new clips)
- Background: Show Sequence continues playing and looping
- GUI: Shows Live Mixing clips for editing
- User activates Live Mixing → Show Sequence stops, Live Mixing starts playing

---

## 🎯 Goals

1. **Multiple Independent Playlists**: Each player (video/artnet) can have multiple named playlists
2. **Playlist Types**: Support different playlist modes (Live, Sequence, Standard)
3. **Quick Switching**: Instant switching between playlists without disrupting playback
4. **Per-Playlist Settings**: Each playlist has its own autoplay, loop, and transition settings
5. **Playlist Cycling**: Automatically switch to next playlist when current ends (chain playlists)
6. **Unified UI**: Tab-based interface for playlist management
7. **Persistent Storage**: Save/load multi-playlist configurations

---

## 🏗️ Architecture

### Current State (Single Playlist per Player)

```
PlayerManager
├── video_player
│   ├── playlist: []           # Single playlist
│   ├── playlist_index: -1
│   ├── autoplay: True
│   └── loop_playlist: False
└── artnet_player
    ├── playlist: []
    ├── playlist_index: -1
    ├── autoplay: True
    └── loop_playlist: False
```

### New Structure (Multi-Playlist System)

**Playlist-First Architecture**: Playlists contain complete configurations for all players

```
MultiPlaylistSystem
├── active_playlist_id: "playlist_001"    # Which playlist controls playback
├── viewed_playlist_id: "playlist_002"    # Which playlist GUI is showing/editing
├── playlists: {
│   "playlist_001": {                 # Playlist 1 (Live Mixing) - ACTIVE (playing)
│   │   id: "playlist_001",
│   │   name: "Live Mixing",
│   │   type: "live",
│   │   created_at: timestamp,
│   │   modified_at: timestamp,
│   │   players: {
│   │       video: {
│   │           clips: [],
│   │           clip_ids: [],
│   │           index: -1,
│   │           autoplay: False,
│   │           loop: False,
│   │           settings: {}
│   │       },
│   │       artnet: {
│   │           clips: [],
│   │           clip_ids: [],
│   │           index: -1,
│   │           autoplay: False,
│   │           loop: False,
│   │           settings: {}
│   │       },
│   │       sequencer: {
│   │           clips: [],
│   │           clip_ids: [],
│   │           index: -1,
│   │           autoplay: False,
│   │           loop: False,
│   │           settings: {}
│   │       }
│   │   }
│   },
│   "playlist_002": {                 # Playlist 2 (Show Sequence)
│   │   id: "playlist_002",
│   │   name: "Show Sequence",
│   │   type: "sequence",
│   │   created_at: timestamp,
│   │   modified_at: timestamp,
│   │   players: {
│   │       video: {
│   │           clips: [...],
│   │           clip_ids: [...],
│   │           index: 0,
│   │           autoplay: True,
│   │           loop: True,
│   │           settings: {bpm: 120}
│   │       },
│   │       artnet: {...},
│   │       sequencer: {...}
│   │   }
│   }
│}
└── PlayerManager (receives current playlist state)

---

## 📊 Data Structures

### Player State (within Playlist)

```python
@dataclass
class PlayerState:
    """State of a single player within a playlist."""
    
    # Clips
    clips: List[str] = field(default_factory=list)  # Paths or generator:id
    clip_ids: List[str] = field(default_factory=list)  # UUIDs
    clip_params: Dict[str, Any] = field(default_factory=dict)  # generator_id -> params
    
    # Playback state
    index: int = -1
    autoplay: bool = False
    loop: bool = False
    
    # Player-specific settings
    settings: Dict[str, Any] = field(default_factory=dict)
    # Examples: bpm, transition settings, sequencer timeline data, etc.
    # For sequencer player: settings['timeline'] contains:
    #   - audio_file: str (path to audio file)
    #   - duration: float (audio duration in seconds)
    #   - splits: List[float] (timeline split points)
    #   - clip_mapping: Dict[int, str] (slot index -> clip name)
    # This ensures each playlist has its own independent sequencer timeline!
    
    def get_current_clip(self) -> Optional[str]:
        """Get current clip path."""
        if 0 <= self.index < len(self.clips):
            return self.clips[self.index]
        return None
    
    def get_current_clip_id(self) -> Optional[str]:
        """Get current clip UUID."""
        if 0 <= self.index < len(self.clip_ids):
            return self.clip_ids[self.index]
        return None

@dataclass
class Playlist:
    """Complete playlist containing all player states."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Playlist"
    type: str = "standard"  # "live", "sequence", "standard"
    
    # Player states (video, artnet, sequencer)
    players: Dict[str, PlayerState] = field(default_factory=dict)
    
    # Master/Slave synchronization settings (per playlist)
    master_player: Optional[str] = None  # 'video', 'artnet', 'sequencer', or None
    # When master_player is set:
    # - Master controls clip index for all slaves
    # - Slaves automatically follow master's clip changes
    # - Each player keeps its own effects/transitions
    # - Uses existing master/slave implementation (no changes to current behavior)
    
    # Sequencer Mode (per playlist)
    sequencer_mode: bool = False  # Whether audio sequencer controls this playlist
    # When True: Sequencer is master, all players are slaves
    # When False: Use master_player setting (normal master/slave)
    # IMPORTANT: Sequencer timeline data is stored in players['sequencer'].settings['timeline']
    # This allows each playlist to have its own independent sequencer timeline!
    
    # Playlist Cycling/Chaining
    next_playlist_id: Optional[str] = None  # Playlist to activate when this one ends
    # When next_playlist_id is set:
    # - When all players finish (autoplay reaches end)
    # - System automatically activates next_playlist_id
    # - Allows chaining playlists for automated shows
    # - Set to None to stop at end (default behavior)
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Initialize default player states if not present."""
        for player_id in ['video', 'artnet', 'sequencer']:
            if player_id not in self.players:
                self.players[player_id] = PlayerState()
    
    def get_player_state(self, player_id: str) -> Optional[PlayerState]:
        """Get state for specific player."""
        return self.players.get(player_id)
```

### 🎵 Sequencer Timeline Storage (CRITICAL)

**Problem We're Solving:**
Previously, sequencer timeline data (audio file, splits, clip mappings) was stored globally, causing conflicts when switching between playlists with different sequencer configurations.

**Solution:**
Store sequencer timeline data **per-playlist** in `playlist.players['sequencer'].settings['timeline']`

**Structure:**
```python
playlist.players['sequencer'].settings = {
    'timeline': {
        'audio_file': 'audio/show_music.mp3',  # Path to audio file
        'duration': 180.5,                      # Audio duration (seconds)
        'splits': [5.2, 12.8, 25.3, ...],      # Split points (seconds)
        'clip_mapping': {                       # Slot index -> clip name
            0: 'video/intro.mp4',
            1: 'video/main.mp4',
            2: 'video/outro.mp4'
        }
    }
}
```

**Benefits:**
- ✅ Each playlist has independent sequencer timeline
- ✅ Switching playlists switches audio timeline automatically
- ✅ No global state conflicts
- ✅ Multiple sequencer playlists work independently
- ✅ Save/load preserves per-playlist timelines

**Implementation Requirements:**
1. **Save timeline to viewed playlist** when user modifies splits/mappings
2. **Load timeline from active playlist** when activating a playlist
3. **Clear global timeline** and load from playlist on startup
4. **Persist timeline** in session_state.json as part of playlist data

### Playlist Types

1. **Standard**: Default behavior, manual or auto navigation
   - `autoplay`: True/False
   - `loop`: True/False
   
2. **Live**: Optimized for live mixing
   - `autoplay`: False (manual control)
   - `loop`: False
   - Quick access buttons
   - Hotkey support
   
3. **Sequence**: Timed automated sequences
   - `autoplay`: True
   - `loop`: True/False
   - BPM sync
   - Transition timing
   - Sequence markers

### MultiPlaylistSystem

```python
class MultiPlaylistSystem:
    """Global playlist system containing all playlists and players."""
    
    def __init__(self, player_manager):
        self.playlists: Dict[str, Playlist] = {}
        self.active_playlist_id: Optional[str] = None
        self.player_manager = player_manager  # Reference to PlayerManager
        
    def create_playlist(self, name: str, type: str = "standard") -> Playlist:
        """Create new playlist with default player states."""
        playlist = Playlist(name=name, type=type)
        self.playlists[playlist.id] = playlist
        
        # Set as active if first playlist
        if self.active_playlist_id is None:
            self.active_playlist_id = playlist.id
            self.apply_playlist(playlist.id)
            
        return playlist
    
    def get_active_playlist(self) -> Optional[Playlist]:
        """Get currently active playlist."""
        if self.active_playlist_id:
            return self.playlists.get(self.active_playlist_id)
        return None
    
    def switch_playlist(self, playlist_id: str) -> bool:
        """
        Switch active playlist (playback control).
        This applies playlist state to all players and changes what's playing.
        Emits WebSocket event to update all connected clients.
        """
        if playlist_id in self.playlists:
            # Save current state before switching
            self.save_current_state()
            
            self.active_playlist_id = playlist_id
            self.apply_playlist(playlist_id)
            
            # Also update viewed playlist to match active
            self.viewed_playlist_id = playlist_id
            
            # Emit WebSocket event to all clients
            if hasattr(self, 'websocket_manager'):
                playlist = self.playlists[playlist_id]
                self.websocket_manager.broadcast({
                    'event': 'playlist_activated',
                    'playlist_id': playlist_id,
                    'playlist_name': playlist.name,
                    'playlist_type': playlist.type
                })
            
            return True
        return False
    
    def set_viewed_playlist(self, playlist_id: str) -> bool:
        """
        Change which playlist the GUI is displaying/editing.
        Does NOT affect playback - active playlist continues playing.
        """
        if playlist_id in self.playlists:
            self.viewed_playlist_id = playlist_id
            logger.info(f"GUI now viewing/editing playlist: {self.playlists[playlist_id].name}")
            return True
        return False
    
    def get_viewed_playlist(self) -> Optional[Playlist]:
        """Get the playlist currently displayed in GUI."""
        if self.viewed_playlist_id:
            return self.playlists.get(self.viewed_playlist_id)
        return None
    
    def apply_playlist(self, playlist_id: str):
        """
        Apply playlist state to all players.
        This loads clips, settings, playback state, and master/slave configuration.
        
        IMPORTANT: Does NOT stop currently playing clips - they continue seamlessly.
        The new playlist's autoplay/loop settings take effect immediately for future decisions.
        """
        playlist = self.playlists.get(playlist_id)
        if not playlist:
            return
        
        # Apply to each player (current playback continues)
        for player_id in ['video', 'artnet', 'sequencer']:
            player = self.player_manager.get_player(player_id)
            if player:
                player_state = playlist.get_player_state(player_id)
                if player_state:
                    # Apply state to player (settings take effect immediately)
                    player.playlist = player_state.clips
                    player.playlist_ids = player_state.clip_ids
                    player.playlist_index = player_state.index
                    player.autoplay = player_state.autoplay
                    player.loop_playlist = player_state.loop
                    player.playlist_params = player_state.clip_params
                    
                    logger.info(f"Applied playlist '{playlist.name}' to {player_id}: "
                               f"{len(player_state.clips)} clips, autoplay={player_state.autoplay}, loop={player_state.loop}")
        
        # Apply master/slave configuration for this playlist
        if hasattr(self.player_manager, 'set_master_playlist'):
            self.player_manager.set_master_playlist(playlist.master_player)
            logger.info(f"Applied master/slave config: master={playlist.master_player}")
    
    def save_current_state(self, auto_save_to_disk=True):
        """
        Save current player states back to ACTIVE playlist.
        Only the active playlist's state is updated from players.
        Viewed (non-active) playlists are NOT updated automatically.
        
        Args:
            auto_save_to_disk: If True, immediately persist to session_state.json
        """
        if not self.active_playlist_id:
            return
        
        playlist = self.get_active_playlist()
        if not playlist:
            return
        
        # Save state from each player
        for player_id in ['video', 'artnet', 'sequencer']:
            player = self.player_manager.get_player(player_id)
            if player:
                player_state = playlist.get_player_state(player_id)
                if player_state:
                    # Save player state to playlist
                    player_state.clips = player.playlist.copy()
                    player_state.clip_ids = player.playlist_ids.copy()
                    player_state.index = player.playlist_index
                    player_state.autoplay = player.autoplay
                    player_state.loop = player.loop_playlist
                    player_state.is_playing = player.is_playing  # Capture playback state
                    if hasattr(player, 'playlist_params'):
                        player_state.clip_params = player.playlist_params.copy()
        
        # Save master/slave configuration
        if hasattr(self.player_manager, 'get_master_playlist'):
            playlist.master_player = self.player_manager.get_master_playlist()
            logger.debug(f"Saved master/slave config: master={playlist.master_player}")
        
        playlist.modified_at = time.time()
        
        # Auto-save to disk immediately
        if auto_save_to_disk and hasattr(self, 'session_state_manager'):
            self.session_state_manager.save()
            logger.debug(f"Auto-saved playlist state to disk")
    
    def remove_playlist(self, playlist_id: str) -> bool:
        """Remove playlist (must have at least one remaining)."""
        if len(self.playlists) <= 1:
            return False
            
        if playlist_id in self.playlists:
            # Handle chain references: if any playlist chains to this one,
            # update it to chain to this playlist's next_playlist_id instead
            deleted_playlist = self.playlists[playlist_id]
            for pl in self.playlists.values():
                if pl.next_playlist_id == playlist_id:
                    pl.next_playlist_id = deleted_playlist.next_playlist_id  # Skip to next
            
            del self.playlists[playlist_id]
            
            # Switch active if removed
            if self.active_playlist_id == playlist_id:
                new_id = next(iter(self.playlists.keys()))
                self.switch_playlist(new_id)
            
            # Update viewed if removed
            if self.viewed_playlist_id == playlist_id:
                self.viewed_playlist_id = self.active_playlist_id
            
            return True
        return False
    
    def get_playlist(self, playlist_id: str) -> Optional[Playlist]:
        """Get playlist by ID."""
        return self.playlists.get(playlist_id)
    
    def list_playlists(self) -> List[Playlist]:
        """List all playlists."""
        return list(self.playlists.values())
```

---

## 🔧 Backend Implementation

### Step 1: Create Multi-Playlist System

**File:** `src/modules/multi_playlist_system.py`

**Tasks:**
- Implement `PlayerState` dataclass (state per player within playlist)
- Implement `Playlist` dataclass (contains all player states)
- Implement `MultiPlaylistSystem` class (global playlist manager)
- Add playlist CRUD operations (create, read, update, delete)
- Add playlist switching logic with state save/load
- Add `apply_playlist()` to push state to all players
- Add `save_current_state()` to capture state from all players
- Add serialization/deserialization for persistence

### Step 2: Integrate with PlayerManager

**Files:**
- `src/modules/player/player_manager.py`
- `src/main.py`

**Changes:**
- Create global `MultiPlaylistSystem` instance
- Pass `player_manager` reference to system
- Players keep their existing properties (no changes needed)
- `MultiPlaylistSystem` reads/writes player properties directly
- On playlist switch, system updates all player states

**Example Integration:**
```python
# In main.py or initialization
from modules.multi_playlist_system import MultiPlaylistSystem

# Create global playlist system
playlist_system = MultiPlaylistSystem(player_manager)

# Create default playlist
default_playlist = playlist_system.create_playlist("Default", "standard")
```

**No player class changes needed** - players work as before, system manages their state.

### Step 3: Update API Endpoints

**File:** `src/modules/api_player_unified.py`

**New Endpoints:**

```python
# Global Playlist Management (not per-player)
POST   /api/playlists/create
POST   /api/playlists/activate          # Change active playlist (playback control)
POST   /api/playlists/view              # Change viewed playlist (GUI only)
GET    /api/playlists/list
GET    /api/playlists/<playlist_id>
PUT    /api/playlists/<playlist_id>
DELETE /api/playlists/<playlist_id>
POST   /api/playlists/<playlist_id>/rename
POST   /api/playlists/<playlist_id>/duplicate

# Playlist Content (for specific player within playlist)
POST   /api/playlists/<playlist_id>/player/<player_id>/clips/set
POST   /api/playlists/<playlist_id>/player/<player_id>/clips/add
DELETE /api/playlists/<playlist_id>/player/<player_id>/clips/<clip_id>
POST   /api/playlists/<playlist_id>/player/<player_id>/clips/reorder

# Playlist Settings (per player within playlist)
GET    /api/playlists/<playlist_id>/player/<player_id>/settings
PUT    /api/playlists/<playlist_id>/player/<player_id>/settings

# Master/Slave Configuration (per playlist)
GET    /api/playlists/<playlist_id>/master
PUT    /api/playlists/<playlist_id>/master
POST   /api/playlists/<playlist_id>/master/set
```

**Modified Endpoints:**

```python
# These now operate on the ACTIVE playlist's player state
POST /api/player/<player_id>/playlist/set       # Active playlist's player state
POST /api/player/<player_id>/next               # Active playlist's player state
POST /api/player/<player_id>/previous           # Active playlist's player state

# Automatically saves to active playlist when modified
```

**Endpoint Details:**

#### Create Playlist
```python
@app.route('/api/playlists/create', methods=['POST'])
def create_playlist():
    """Create new global playlist with all player states."""
    data = request.get_json()
    name = data.get('name', 'New Playlist')
    type = data.get('type', 'standard')
    
    # Access global playlist system
    playlist_system = get_playlist_system()
    
    playlist = playlist_system.create_playlist(name, type)
    
    return jsonify({
        "success": True,
        "playlist": {
            "id": playlist.id,
            "name": playlist.name,
            "type": playlist.type,
            "players": list(playlist.players.keys())
        }
    })
```

#### Switch Playlist
```python
@app.route('/api/playlists/activate', methods=['POST'])
def activate_playlist():
    """
    Activate playlist (change which playlist controls playback).
    This applies the playlist state to ALL players at once.
    The active playlist runs in the background and controls playback.
    """
    data = request.get_json()
    playlist_id = data.get('playlist_id')
    
    playlist_system = get_playlist_system()
    
    # Save current state before switching
    playlist_system.save_current_state()
    
    # Switch and apply new playlist
    success = playlist_system.switch_playlist(playlist_id)
    
    if success:
        active = playlist_system.get_active_playlist()
        
        return jsonify({
            "success": True,
            "active_playlist": {
                "id": active.id,
                "name": active.name,
                "type": active.type,
                "players": {
                    player_id: {
                        "clips": len(state.clips),
                        "index": state.index,
                        "autoplay": state.autoplay,
                        "loop": state.loop
                    }
                    for player_id, state in active.players.items()
                }
            }
        })
    else:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
```

#### View Playlist (GUI Display)
```python
@app.route('/api/playlists/view', methods=['POST'])
def view_playlist():
    """
    Set which playlist the GUI is displaying/editing.
    Does NOT affect playback - active playlist continues in background.
    This allows user to edit one playlist while another is playing.
    """
    data = request.get_json()
    playlist_id = data.get('playlist_id')
    
    playlist_system = get_playlist_system()
    success = playlist_system.set_viewed_playlist(playlist_id)
    
    if success:
        viewed = playlist_system.get_viewed_playlist()
        active_id = playlist_system.active_playlist_id
        
        return jsonify({
            "success": True,
            "viewed_playlist": {
                "id": viewed.id,
                "name": viewed.name,
                "type": viewed.type,
                "is_active": viewed.id == active_id,
                "players": {
                    player_id: {
                        "clips": state.clips,
                        "clip_ids": state.clip_ids,
                        "index": state.index,
                        "autoplay": state.autoplay,
                        "loop": state.loop
                    }
                    for player_id, state in viewed.players.items()
                }
            },
            "active_playlist_id": active_id
        })
    else:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
```

#### List Playlists
```python
@app.route('/api/playlists/list', methods=['GET'])
def list_playlists():
    """Get all global playlists."""
    playlist_system = get_playlist_system()
    
    playlists = playlist_system.list_playlists()
    active_id = playlist_system.active_playlist_id
    viewed_id = playlist_system.viewed_playlist_id
    
    return jsonify({
        "success": True,
        "active_playlist_id": active_id,
        "viewed_playlist_id": viewed_id,
        "playlists": [
            {
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "is_active": p.id == active_id,
                "master_player": p.master_player,  # Master/slave config
                "players": {
                    player_id: {
                        "clips": len(state.clips),
                        "index": state.index
                    }
                    for player_id, state in p.players.items()
                },
                "created_at": p.created_at,
                "modified_at": p.modified_at
            }
            for p in playlists
        ]
    })
```

#### Set Master Player for Playlist
```python
@app.route('/api/playlists/<playlist_id>/master/set', methods=['POST'])
def set_playlist_master(playlist_id):
    """
    Set master player for a specific playlist.
    Each playlist has its own master/slave configuration.
    """
    data = request.get_json()
    master_player = data.get('master_player')  # 'video', 'artnet', 'sequencer', or None
    
    playlist_system = get_playlist_system()
    playlist = playlist_system.get_playlist(playlist_id)
    
    if not playlist:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
    
    # Validate master_player value
    valid_masters = ['video', 'artnet', 'sequencer', None]
    if master_player not in valid_masters:
        return jsonify({
            "success": False,
            "error": f"Invalid master_player. Must be one of: {valid_masters}"
        }), 400
    
    # Update playlist's master configuration
    playlist.master_player = master_player
    playlist.modified_at = time.time()
    
    # If this is the active playlist, apply the master/slave config immediately
    if playlist_id == playlist_system.active_playlist_id:
        if hasattr(player_manager, 'set_master_playlist'):
            player_manager.set_master_playlist(master_player)
    
    return jsonify({
        "success": True,
        "playlist_id": playlist_id,
        "master_player": master_player
    })

@app.route('/api/playlists/<playlist_id>/master', methods=['GET'])
def get_playlist_master(playlist_id):
    """Get master player for specific playlist."""
    playlist_system = get_playlist_system()
    playlist = playlist_system.get_playlist(playlist_id)
    
    if not playlist:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
    
    return jsonify({
        "success": True,
        "playlist_id": playlist_id,
        "master_player": playlist.master_player
    })
```

### Step 4: Sequencer Timeline Per-Playlist Integration

**CRITICAL IMPLEMENTATION**: Sequencer timeline must be stored per-playlist to avoid conflicts.

**Files to Modify:**
- `src/modules/api_sequencer.py` - Save/load timeline from playlist
- `src/modules/multi_playlist_system.py` - Apply timeline when switching playlists

**Implementation Steps:**

#### 4.1: Save Timeline to Viewed Playlist (api_sequencer.py)

Whenever timeline is modified (upload audio, add split, remove split, set clip mapping), save to viewed playlist:

```python
# After any timeline modification:
try:
    from .api_playlists import get_playlist_system
    playlist_system = get_playlist_system()
    if playlist_system:
        viewed_playlist = playlist_system.get_viewed_playlist()
        if viewed_playlist:
            sequencer_state = viewed_playlist.players.get('sequencer')
            if sequencer_state:
                # Save timeline data to playlist
                sequencer_state.settings['timeline'] = player_manager.sequencer.timeline.to_dict()
                playlist_system._auto_save()
                logger.info(f"💾 Saved timeline to playlist '{viewed_playlist.name}'")
except Exception as e:
    logger.error(f"Could not save timeline to playlist: {e}", exc_info=True)
```

**Apply this pattern after:**
- Audio file upload/load
- Add split
- Remove split
- Set clip mapping

#### 4.2: Load Timeline from Active Playlist (multi_playlist_system.py)

When activating a playlist, load its sequencer timeline:

```python
def apply_playlist(self, playlist_id: str):
    """Apply playlist state to all players."""
    playlist = self.playlists.get(playlist_id)
    if not playlist:
        return
    
    # ... apply clips to each player ...
    
    # Apply sequencer timeline from playlist
    if hasattr(self.player_manager, 'sequencer') and self.player_manager.sequencer:
        sequencer_state = playlist.players.get('sequencer')
        if sequencer_state and sequencer_state.settings.get('timeline'):
            # Load timeline from playlist settings
            timeline_data = sequencer_state.settings['timeline']
            self.player_manager.sequencer.timeline.from_dict(timeline_data)
            logger.info(f"✅ Loaded sequencer timeline from playlist '{playlist.name}': "
                       f"{len(timeline_data.get('splits', []))} splits")
        else:
            # Clear timeline if playlist has no timeline data
            self.player_manager.sequencer.timeline.clear_splits()
            logger.info(f"🗑️ Cleared sequencer timeline (playlist '{playlist.name}' has no timeline)")
        
        # Apply sequencer mode
        if hasattr(self.player_manager, 'set_sequencer_mode'):
            self.player_manager.set_sequencer_mode(playlist.sequencer_mode)
            logger.info(f"Applied sequencer mode: {playlist.sequencer_mode}")
```

**Benefits:**
- ✅ Each playlist has independent sequencer timeline
- ✅ Switching playlists = switching timelines automatically
- ✅ No global state conflicts
- ✅ Multiple sequencer playlists work perfectly

### Step 5: Update Session State Persistence

**File:** `src/modules/session_state.py`

**Changes:**
- **Auto-save immediately** on any playlist change (add/remove clip, rename, settings change)
- Save all playlists (not just active one)
- Load and restore all playlists with active playlist ID
- **No migration** - old single-playlist format is not supported

**OLD format (DEPRECATED, will NOT be loaded):**
```json
"video_player": {
    "playlist": [...],
    "playlist_ids": [...],
    "autoplay": true,
    "loop": false
}
```

**NEW format (global playlists):**
```json
"multi_playlist_system": {
    "active_playlist_id": "playlist_001",
    "viewed_playlist_id": "playlist_001",
    "playlists": {
        "playlist_001": {
            "id": "playlist_001",
            "name": "Live Mixing",
            "type": "live",
            "created_at": timestamp,
            "modified_at": timestamp,
            "players": {
                "video": {
                    "clips": [...],
                    "clip_ids": [...],
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                },
                "artnet": {
                    "clips": [...],
                    "clip_ids": [...],
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                },
                "sequencer": {
                    "clips": [],
                    "clip_ids": [],
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                }
            }
        },
        "playlist_002": {
            "id": "playlist_002",
            "name": "Show Sequence",
            "type": "sequence",
            "created_at": timestamp,
            "modified_at": timestamp,
            "sequencer_mode": true,
            "players": {
                "video": {...},
                "artnet": {...},
                "sequencer": {
                    "clips": [],
                    "clip_ids": [],
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {
                        "timeline": {
                            "audio_file": "audio/show_music.mp3",
                            "duration": 180.5,
                            "splits": [5.2, 12.8, 25.3, 48.7],
                            "clip_mapping": {
                                "0": "video/intro.mp4",
                                "1": "video/main.mp4"
                            }
                        }
                    }
                }
            }
        }
    }
}
```

**IMPORTANT**: Note how playlist_002 has sequencer timeline data in `players.sequencer.settings.timeline` - this is the key to per-playlist independence!

---

## 🎨 Frontend Implementation

### Step 1: Playlist Tabs Component

**File:** `frontend/js/components/playlist-tabs.js`

**Features:**
- Tab bar showing all playlists
- Active playlist highlighted
- Click tab to switch
- Right-click context menu (rename, duplicate, delete)
- Add (+) button for new playlist
- Drag-to-reorder tabs

**HTML Structure:**
```html
<!-- Middle section: BPM | Playlist Tabs | Audio Sequencer (50px height) -->
<div class="middle-section" style="display: flex; height: 50px; align-items: center; gap: 10px;">
    <!-- BPM Section (left) -->
    <div class="bpm-section" style="min-width: 100px;">
        <label>BPM: <span id="bpmValue">120</span></label>
    </div>
    
    <!-- Playlist Tabs (center) -->
    <div class="playlist-tabs-container" style="flex: 1; height: 50px; overflow-x: auto; overflow-y: hidden;">
        <div class="playlist-tabs" id="playlistTabs" style="display: flex; height: 100%; align-items: center;">
            <!-- Tabs generated here -->
            <!-- Active tab has .active class + ● indicator -->
        </div>
        <button class="playlist-add-btn" id="addPlaylistBtn" title="Add Playlist" style="height: 40px;">
            <i class="fas fa-plus"></i>
        </button>
    </div>
    
    <!-- Audio Sequencer Section (right) -->
    <div class="audio-sequencer-section" style="min-width: 120px;">
        <button id="audioSequencerBtn">Audio Seq</button>
    </div>
</div>

<!-- Context menu -->
<div class="context-menu" id="playlistContextMenu" style="display: none;">
    <div class="context-menu-item" data-action="activate">✓ Activate</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" data-action="rename">Rename</div>
    <div class="context-menu-item" data-action="duplicate">Duplicate</div>
    <div class="context-menu-item" data-action="settings">Settings</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" data-action="delete">Delete</div>
</div>
```

**JavaScript Class:**
```javascript
class PlaylistTabs {
    constructor() {
        this.playlists = [];
        this.activePlaylistId = null;
        this.onSwitch = null;  // Callback when playlist switches
        
        this.init();
    }
    
    async init() {
        await this.load();
        this.render();
        this.attachEvents();
    }
    
    async load() {
        const response = await fetch('/api/playlists/list');
        const data = await response.json();
        
        if (data.success) {
            this.playlists = data.playlists;
            this.activePlaylistId = data.active_playlist_id;
        }
    }
    
    render() {
        const container = document.getElementById('playlistTabs');
        container.innerHTML = '';
        
        this.playlists.forEach(playlist => {
            const tab = document.createElement('div');
            tab.className = 'playlist-tab';
            
            // Mark active playlist
            if (playlist.id === this.activePlaylistId) {
                tab.classList.add('active');
                tab.title = `${playlist.name} (Active)`;
            } else {
                tab.title = `${playlist.name} (Right-click to activate)`;
            }
            
            // Type indicator
            const typeIcon = this.getTypeIcon(playlist.type);
            
            tab.innerHTML = `
                <span class="playlist-type-icon">${typeIcon}</span>
                <span class="playlist-name">${playlist.name}</span>
                ${playlist.id === this.activePlaylistId ? '<span class="active-indicator">●</span>' : ''}
            `;
            
            tab.dataset.playlistId = playlist.id;
            container.appendChild(tab);
        });
    }
    
    getTypeIcon(type) {
        const icons = {
            'live': '<i class="fas fa-microphone"></i>',
            'sequence': '<i class="fas fa-list-ol"></i>',
            'standard': '<i class="fas fa-play"></i>'
        };
        return icons[type] || icons.standard;
    }
    
    attachEvents() {
        // Left-click: View/edit playlist (GUI only, no playback change)
        // Right-click: Context menu with "Activate" option (changes playback)
        document.querySelectorAll('.playlist-tab').forEach(tab => {
            // Left-click: View this playlist in GUI (changes viewed_playlist_id)
            tab.addEventListener('click', async (e) => {
                const playlistId = tab.dataset.playlistId;
                await this.viewPlaylist(playlistId);  // View/edit in GUI
            });
            
            // Right-click opens context menu with "Activate" option
            tab.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showContextMenu(e, tab.dataset.playlistId);
            });
        });
        
        // Add button
        document.getElementById('addPlaylistBtn').addEventListener('click', () => {
            this.createPlaylist();
        });
        
        // Hide context menu on outside click
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
    }
    
    async viewPlaylist(playlistId) {
        // View/edit playlist in GUI (does NOT change playback)
        const response = await fetch('/api/playlists/view', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ playlist_id: playlistId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            this.viewedPlaylistId = playlistId;
            this.render();
            
            // Update GUI to show this playlist's clips
            if (this.onView) {
                this.onView(playlistId);
            }
        }
    }
    
    async activatePlaylist(playlistId) {
        // Activate playlist (changes playback control)
        const response = await fetch('/api/playlists/activate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ playlist_id: playlistId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            this.activePlaylistId = playlistId;
            this.viewedPlaylistId = playlistId;  // Also view it
            this.render();
            
            // Trigger callback (updates ALL player displays)
            if (this.onActivate) {
                this.onActivate(playlistId);
            }
        }
    }
    
    async createPlaylist() {
        const name = prompt('Playlist name:');
        if (!name) return;
        
        const type = this.selectPlaylistType();
        
        const response = await fetch('/api/playlists/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, type })
        });
        
        const data = await response.json();
        
        if (data.success) {
            await this.load();
            this.render();
        }
    }
    
    selectPlaylistType() {
        // Show modal to select type
        // For now, return 'standard'
        return 'standard';
    }
    
    showContextMenu(event, playlistId) {
        this.contextMenuPlaylistId = playlistId;
        const menu = document.getElementById('playlistContextMenu');
        
        // Show/hide "Activate" option based on whether it's already active
        const activateItem = menu.querySelector('[data-action="activate"]');
        if (activateItem) {
            if (playlistId === this.activePlaylistId) {
                activateItem.style.display = 'none';
            } else {
                activateItem.style.display = 'block';
            }
        }
        
        menu.style.display = 'block';
        menu.style.left = event.clientX + 'px';
        menu.style.top = event.clientY + 'px';
    }
    
    hideContextMenu() {
        const menu = document.getElementById('playlistContextMenu');
        menu.style.display = 'none';
    }
    
    async handleContextMenuAction(action) {
        this.hideContextMenu();
        
        const playlistId = this.contextMenuPlaylistId;
        if (!playlistId) return;
        
        switch (action) {
            case 'activate':
                await this.activatePlaylist(playlistId);  // Activate via context menu
                break;
            case 'rename':
                await this.renamePlaylist(playlistId);
                break;
            case 'duplicate':
                await this.duplicatePlaylist(playlistId);
                break;
            case 'settings':
                await this.showPlaylistSettings(playlistId);
                break;
            case 'delete':
                await this.removePlaylist(playlistId);
                break;
        }
    }
}
```

### Step 2: Update Playlist UI

**File:** `frontend/artnet.html` / `frontend/editor.html`

**Changes:**
- Add playlist tabs at top of playlist section
- Update playlist rendering to show active playlist only
- Add playlist type indicators
- Show playlist-specific settings

**HTML:**
```html
<!-- Middle Section: BPM | Playlist Tabs | Audio Sequencer (50px height) -->
<div class="middle-section" style="display: flex; height: 50px; align-items: center; gap: 10px;">
    <!-- BPM Section -->
    <div class="bpm-section" style="min-width: 100px;">
        <label>BPM: <span id="bpmValue">120</span></label>
    </div>
    
    <!-- Global Playlist Tabs (center) -->
    <div class="global-playlist-tabs-container" style="flex: 1; height: 50px; overflow-x: auto; overflow-y: hidden;">
        <div class="playlist-tabs" id="globalPlaylistTabs" style="display: flex; height: 100%; align-items: center;"></div>
        <button class="playlist-add-btn" id="addPlaylistBtn" style="height: 40px;">+</button>
    </div>
    
    <!-- Audio Sequencer Section -->
    <div class="audio-sequencer-section" style="min-width: 120px;">
        <button id="audioSequencerBtn">Audio Seq</button>
    </div>
</div>

<!-- Video Player Section -->

<!-- Video Player Section -->
<div class="playlist-section">
    <h3>Video Player</h3>
    
    <!-- Video clips from active playlist -->
    <div id="videoPlaylist" class="playlist-container">
        <!-- Clips from active_playlist.players.video -->
    </div>
    
    <!-- Video-specific controls -->
    <div class="playlist-controls">
        <label>
            <input type="checkbox" id="videoAutoplay"> Autoplay
        </label>
        <label>
            <input type="checkbox" id="videoLoop"> Loop
        </label>
    </div>
</div>

<!-- Art-Net Player Section -->
<div class="playlist-section">
    <h3>Art-Net Player</h3>
    
    <!-- Art-Net clips from active playlist -->
    <div id="artnetPlaylist" class="playlist-container">
        <!-- Clips from active_playlist.players.artnet -->
    </div>
    
    <!-- Art-Net-specific controls -->
    <div class="playlist-controls">
        <label>
            <input type="checkbox" id="artnetAutoplay"> Autoplay
        </label>
        <label>
            <input type="checkbox" id="artnetLoop"> Loop
        </label
</div>
```

### Step 3: Update Player.js

**File:** `frontend/js/player.js`

**Changes:**
- Initialize PlaylistTabs component
- Handle playlist switching
- Update status updates to include active playlist info
- Update playlist loading to work with multi-playlist API

```javascript
// Initialize playlist tabs
const videoPlaylistTabs = new PlaylistTabs('video');
videoPlaylistTabs.onSwitch = async (playlistId) => {
    // Reload playlist content
    await updatePlaylist('video');
};

const artnetPlaylistTabs = new PlaylistTabs('artnet');
artnetPlaylistTabs.onSwitch = async (playlistId) => {
    await updatePlaylist('artnet');
};

// Modified updatePlaylist to use active playlist
async function updatePlaylist(playerId) {
    const response = await fetch(`/api/player/${playerId}/playlists/list`);
    const data = await response.json();
    
    if (data.success) {
        const activePlaylist = data.playlists.find(p => p.is_active);
     active_playlist_id": "playlist_001",
    "playlists": {
        "playlist_001": {
            "id": "playlist_001",
            "name": "Live Mixing",
            "type": "live",
            "created_at": 1735689600.0,
            "modified_at": 1735689600.0,
            "players": {
                "video": {
                    "clips": ["video1.mp4", "video2.mp4"],
                    "clip_ids": ["uuid1", "uuid2"],
                    "clip_params": {},
                    "index": 0,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                },
                "artnet": {
                    "clips": ["artnet1.json", "artnet2.json"],
                    "clip_ids": ["uuid3", "uuid4"],
                    "clip_params": {},
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                },
                "sequencer": {
                    "clips": [],
                    "clip_ids": [],
                    "clip_params": {},
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
                    "settings": {}
                }
            },
            "master_player": null
        },
        "playlist_002": {
            "id": "playlist_002",
            "name": "Show Sequence",
            "type": "sequence",
            "created_at": 1735689600.0,
            "modified_at": 1735689600.0,
            "players": {
                "video": {
                    "clips": ["video3.mp4", "video4.mp4"],
                    "clip_ids": ["uuid5", "uuid6"],
                    "clip_params": {},
                    "index": 0,
                    "autoplay": true,
                    "loop": true,
                    "settings": {"bpm": 120}
                },
                "artnet": {
                    "clips": ["artnet3.json"],
                    "clip_ids": ["uuid7"],
                    "clip_params": {},
                    "index": 0,
                    "autoplay": true,
                    "loop": true,
                    "settings": {"bpm": 120}
                },
                "sequencer": {
                    "clips": [],
                    "clip_ids": [],
                    "clip_params": {},
                    "index": -1,
                    "autoplay": false,
                    "loop": false,
            global multi-playlist configuration."""
    data = request.get_json()
    filename = data.get('filename', f'multi_playlist_{datetime.now().strftime("%Y-%m-%d")}.json')
    
    playlist_system = get_playlist_system()
    
    # Save current state first
    playlist_system.save_current_state()
    
    # Build config
    config = {
        "version": "2.0",
        "format": "multi_playlist",
        "created_at": time.time(),
        "modified_at": time.time(),
        "active_playlist_id": playlist_system.active_playlist_id,
        "playlists": {}
    }
    
    # Serialize all playlists
    for playlist_id, playlist in playlist_system.playlists.items():
        config["playlists"][playlist_id] = {
            "id": playlist.id,
            "name": playlist.name,
            "type": playlist.type,
            "created_at": playlist.created_at,
            "modified_at": playlist.modified_at,
            "master_player": playlist.master_player,  # Master/slave config
            "players": {
                player_id: {
                    "clips": state.clips,
                    "clip_ids": state.clip_ids,
                    "clip_params": state.clip_params,
                    "index": state.index,
                    "autoplay": state.autoplay,
                    "loop": state.loop,
                    "settings": state.settings
                }
                for player_id, state in playlist.players.items()
            }
        }
    
    # Save to file
    filepath = os.path.join(playlists_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True, "filename": filename})

@app.route('/api/playlists/load-multi', methods=['POST'])
def load_multi_playlist():
    """Load global multi-playlist configuration."""
    data = request.get_json()
    filename = data.get('filename')
    
    filepath = os.path.join(playlists_dir, filename)
    
    with open(filepath, 'r') as f:
        config = json.load(f)
    
    playlist_system = get_playlist_system()
    
    # Clear existing playlists
    playlist_system.playlists.clear()
    
    # Load all playlists
    for playlist_id, playlist_data in config["playlists"].items():
        playlist = Playlist(
            id=playlist_data["id"],
            name=playlist_data["name"],
            type=playlist_data["type"],
            created_at=playlist_data["created_at"],
            modified_at=playlist_data["modified_at"],
            master_player=playlist_data.get("master_player")  # Load master/slave config
        )
        
        # Load player states
        for player_id, state_data in playlist_data["players"].items():
            playlist.players[player_id] = PlayerState(
                clips=state_data["clips"],
                clip_ids=state_data["clip_ids"],
                clip_params=state_data.get("clip_params", {}),
                index=state_data["index"],
                autoplay=state_data["autoplay"],
                loop=state_data["loop"],
                settings=state_data.get("settings", {})
            )
        
        playlist_system.playlists[playlist.id] = playlist
    
    # Set and apply active playlist (including master/slave config)
    active_id = config.get("active_playlist_id")
    if active_id:
        playlist_system.switch_playlist(active_id)
                ]
            }
    
    # Save to file
    filepath = os.path.join(playlists_dir, filename)
    with open(filepath, 'w') as f:
        json.dump(config, f, indent=2)
    
    return jsonify({"success": True, "filename": filename})

@app.route('/api/playlists/load-multi', methods=['POST'])
def load_multi_playlist():
    """Load multi-playlist configuration."""
    data = request.get_json()
    filename = data.get('filename')
    
    filepath = os.path.join(playlists_dir, filename)
    
    with open(filepath, 'r') as f:
        config = json.load(f)
    
    # Restore playlists for each player
    for player_id, player_data in config["players"].items():
        player = player_manager.get_player(player_id)
        if player:
            # Clear existing playlists
            player.multi_playlist_manager.playlists.clear()
            
            # Load playlists
            for playlist_data in player_data["playlists"]:
                playlist = Playlist.from_dict(playlist_data)
                player.multi_playlist_manager.playlists[playlist.id] = playlist
            
            # Set active playlist
            player.multi_playlist_manager.active_playlist_id = player_data["active_playlist_id"]
    
    return jsonify({"success": True})
```

---

## 🎬 Use Cases

### Use Case 1: Live Mixing Setup

**Scenario:** DJ wants quick access to video clips for live mixing

**Workflow:**
1. Create "Live Mix" playlist (type: live)
2. Add favorite clips for quick access
3. Disable autoplay, disable loop
4. Switch between clips manually during performance
5. Create second "Backup" playlist for redundancy

**Benefits:**
- Quick switching between prepared clips
- Manual control over playback
- Multiple playlists for different sets

### Use Case 2: Automated SequALL players (video, artnet, sequencer) in each scene
3. Switch playlists between scenes - **all players update together**
4. Each playlist has coordinated settings across all players

**Benefits:**
- Complete scene configuration (video + lighting + sequences)
- All players switch together synchronously
- Quick scene changes with one click
- No manual coordination needednable loop
4. Configure BPM sync and transitions
5. Create "Intermission" playlist for breaks
6. Switch playlists as needed

**Benefits:**
- Automated playback
- Timed transitions
- Easy switching between show segments

### Use Case 3: Multi-Scene Performance

**Scenario:** Theater production with different scenes

**Workflow:**
1. Create playlist for each scene ("Scene 1", "Scene 2", etc.)
2. Load appropriate clips for each scene
3. Switch playlists between scenes
4. Each playlist has custom settings (loop, autoplay)

**Benefits:**
- Organized by scene
- Scene-specific settings
- Quick scene changes

### Use Case 4: Automated Playlist Cycling

**Scenario:** Unattended exhibition with multiple playlist sequences

**Workflow:**
1. Create "Intro" playlist (3 clips, autoplay ON, loop OFF)
2. Set `next_playlist_id` → "Main Loop"
3. Create "Main Loop" playlist (20 clips, autoplay ON, loop ON)
4. Set `next_playlist_id` → "Main Loop" (cycles back to itself)
5. Alternative: Chain multiple playlists (Intro → Part1 → Part2 → Part3 → Intro)

**Behavior:**
- System starts with "Intro" playlist
- When Intro finishes all 3 clips → automatically switches to "Main Loop"
- Main Loop plays 20 clips, then loops infinitely
- No manual intervention needed

**Benefits:**
- Fully automated show sequences
- Different intro/outro vs main content
- Can create complex multi-act shows
- Perfect for exhibitions, museums, retail displays

**Advanced Chaining:**
```
Playlist Chain:
"Welcome" → "Tutorial" → "Demo" → "Main Show" → "Outro" → "Welcome" (cycle repeats)

Each playlist:
- Has its own clips, effects, settings
- Automatically advances to next when done
- Can loop internally (loop=True) or advance once (loop=False)
```

---

## 🚀 Implementation Steps

### Phase 1: Backend Foundation (Days 1-2)
- [ ] Create `Playlist` dataclass
- [ ] Create `MultiPlaylistManager` class
- [ ] Add unit tests for manager
- [ ] Integrate with player classes
- [ ] Add backwards compatibility properties

### Phase 2: API Endpoints (Days 3-4)
- [ ] Implement playlist CRUD endpoints
- [ ] Implement playlist switching endpoint
- [ ] Implement clip management endpoints
- [ ] Update existing endpoints for backwards compatibility
- [ ] Test all endpoints with Postman/curl

### Phase 3: Frontend UI (Days 5-7)
- [ ] Create PlaylistTabs component
- [ ] Add tab bar to artnet.html
- [ ] Add tab bar to editor.html
- [ ] Implement context menu
- [ ] Add playlist creation dialog
- [ ] Style playlist tabs (CSS)

### Phase 4: Integration (Days 8-9)
- [ ] Update player.js for multi-playlist
- [ ] Update playlist rendering
- [ ] Update status updates
- [ ] Test switching between playlists
- [ ] Test clip playback in different playlists

### Phase 5: Persistence (Days 10-11)
- [ ] Update session_state.py for multi-playlist
- [ ] Implement save/load multi-playlist
- [ ] Update snapshot format
- [ ] Test save/load functionality
- [ ] Migrate old playlists (if desired)

### Phase 6: Testing & Polish (Days 12-14)────────┐
│ Global Playlists                                                 │
├─────────────────────────────────────────────────────────────────┤
│ [🎤 Live Mix] [📋 Show Sequence] [▶️ Standard] [+]              │  ← Global Tabs
│ Current: Live Mix                                                │
├─────────────────────────────────────────────────────────────────┤
│ Video Player                                                     │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                │
│ │ video1.mp4  │ │ video2.mp4  │ │ video3.mp4  │                │  ← Video clips
│ │ [▶️]        │ │ [ ]         │ │ [ ]         │                │     from active
│ └─────────────┘ └─────────────┘ └─────────────┘                │     playlist
│ [☑ Autoplay] [☐ Loop]                                           │
├─────────────────────────────────────────────────────────────────┤
│ Art-Net Player                                                   │
│ ┌─────────────┐ ┌─────────────┐                                 │
│ │ artnet1.json│ │ artnet2.json│                                 │  ← Art-Net clips
│ │ [▶️]        │ │ [ ]         │                                 │     from active
│ └─────────────┘ └─────────────┘                              - updates ALL players at once
- **Memory**: Keep all playlists in memory for fast switching
- **Persistence**: Auto-save current state before switching playlists
- **UI feedback**: Show loading state during switch, update all player displays
- **Hotkeys**: Add keyboard shortcuts for playlist switching (1-9)
- **Drag-drop**: Support drag-drop clips between playlists and between players
- **Templates**: Save playlist as template for reuse (complete multi-player configuration)
- **Import/Export**: Individual playlist import/export
- **Synchronized switching**: All players update atomically when switching playlists
1. **Session state format**: New multi-playlist format
2. **API endpoints**: Some endpoints changed (playlist/set still works on active)
3. **Player properties**: `playlist`, `playlist_index` now proxies to active playlist
4. **Saved playlists**: Old single-playlist format won't load automatically

---

## 🎨 UI Mockup

```
┌─────────────────────────────────────────────────────────┐
│ Video Player                                             │
├─────────────────────────────────────────────────────────┤
│ [🎤 Live Mix] [📋 Show Sequence] [▶️ Standard] [+]      │  ← Playlist Tabs
├─────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐        │
│ │ video1.mp4  │ │ video2.mp4  │ │ video3.mp4  │        │  ← Active Playlist
│ │ [▶️]        │ │ [ ]         │ │ [ ]         │        │     Clips
│ └─────────────┘ └─────────────┘ └─────────────┘        │
│                                                          │
│ [☑ Autoplay] [☐ Loop]          Type: Live Mixing       │  ← Playlist Settings
└─────────────────────────────────────────────────────────┘
```

---

## 🎯 Active vs. Viewed Playlist Explained

### The Two-Layer System

This architecture separates **playback control** from **GUI editing**:

```
┌─────────────────────────────────────────────────────────┐
│ LAYER 1: PLAYBACK (Background)                          │
│ Active Playlist: "Show Sequence"                        │
│ - Video player running clip 3/10                        │
│ - Autoplay: ON, Loop: ON                                │
│ - Playing continuously in background                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ LAYER 2: GUI (Foreground)                               │
│ Viewed Playlist: "Live Mixing"                          │
│ - Showing clips for editing                             │
│ - User adding/removing/reordering                       │
│ - Does NOT affect active playlist playback              │
└─────────────────────────────────────────────────────────┘
```

### User Workflows

**Workflow 1: Prepare next playlist while current plays**
1. Active: "Show Sequence" → autoplay=ON, loop=ON, playing video 5/10
2. User clicks "Live Mixing" tab → GUI shows Live Mixing clips
3. User adds 3 new videos to Live Mixing playlist
4. Show Sequence continues playing in background (unaffected)
5. User right-clicks "Live Mixing" → "Activate"
6. Show Sequence stops, Live Mixing becomes active and starts playing

**Workflow 2: Quick switching during live show**
1. Active: "Intro" playlist → playing
2. User right-clicks "Main Show" → "Activate"
3. Intro stops, Main Show immediately takes over
4. All players switch to Main Show's clips and settings
5. Viewed playlist updates to match active (Main Show)

**Workflow 3: Edit background content**
1. Active: "Loop Background" → autoplay=ON, loop=ON, playing continuously
2. User clicks "Next Set" tab → views/edits Next Set playlist
3. Loop Background keeps looping in background
4. User prepares Next Set playlist
5. When ready: right-click "Next Set" → "Activate"

### API Methods

```python
# View a playlist (GUI editing) - doesn't affect playback
playlist_system.set_viewed_playlist("playlist_002")

# Activate a playlist (change playback) - applies to players
playlist_system.switch_playlist("playlist_002")

# These are SEPARATE operations!
```

### Frontend Behavior

**Tab Indicators:**
- **Green dot (●)**: Active playlist (playing in background)
- **Blue highlight**: Viewed playlist (displayed in GUI)
- Can be same or different!

**Tab Interactions:**
- **Left-click tab**: View/edit this playlist (GUI only)
- **Right-click → "Activate"**: Make this playlist active (playback control)

**Example Tab Display:**
```
[● Show Seq] [Live Mix] [Outro]
   Active      Viewed    Inactive
```
In this state:
- Show Seq: Playing in background (green dot)
- Live Mix: Displayed in GUI for editing (blue highlight)
- Outro: Neither active nor viewed

---

## 🎥 Preview & Output Behavior

### Simple Rule: Preview = Viewed Playlist, Output = Active Playlist

**Preview screens are ALWAYS tied to the VIEWED playlist** (regardless of active/inactive status).  
**DMX/Art-Net output is ALWAYS from the ACTIVE playlist** (background, continuous).

These are completely separate systems, so no conflicts!

#### Preview System (GUI)
**Always shows VIEWED playlist:**
- Video preview canvas displays clips from viewed playlist
- Clip thumbnails from viewed playlist
- Generator previews from viewed playlist
- User can scrub/preview any clip in viewed playlist
- Click any clip → preview loads that clip (no Art-Net output)

**Works the same whether viewed playlist is active or inactive:**
- Viewing active playlist → preview shows what's playing + outputting
- Viewing inactive playlist → preview shows that playlist's clips (safe preview, no output)

#### Output System (DMX/Art-Net)
**Always outputs from ACTIVE playlist:**
- Art-Net DMX packets stream from active playlist's current clip
- Fixtures display content from active playlist
- Autoplay/loop from active playlist control progression
- Runs continuously in background
- Completely independent of what's being previewed in GUI

### Example Scenarios

**Scenario 1: Normal operation (active = viewed)**
```
Active:  "Main Show" (playing clip 5/20)
Viewed:  "Main Show" (same)

Preview: Shows "Main Show" clips, preview canvas displays clip 5
Output:  Art-Net outputs clip 5 to fixtures
Result:  Preview and output are synchronized (normal mode)
```

**Scenario 2: Edit different playlist while show runs**
```
Active:  "Main Show" (playing clip 5/20, looping)
Viewed:  "Encore" (editing, adding clips)

Preview: Shows "Encore" clips, user clicks clip 3 → preview shows clip 3
Output:  Art-Net continues outputting "Main Show" clip 5 (unaffected)
Result:  User edits Encore safely, Main Show keeps running on fixtures
```

**Scenario 3: Preview next playlist before activating**
```
Active:  "Loop Background" (looping 3 clips continuously)
Viewed:  "Next Scene" (want to check before going live)

Preview: Shows "Next Scene" clips, user previews each one
Output:  Art-Net outputs "Loop Background" (continuous loop)
Result:  User verifies Next Scene looks good, then activates it
         When activated: Art-Net switches to Next Scene
```

**Scenario 4: Prepare playlist from scratch**
```
Active:  "Live Show" (playing, autoplay ON)
Viewed:  "New Playlist" (empty, being built)

Preview: Shows empty "New Playlist", user adds clips, previews each
Output:  Art-Net continues with "Live Show" (uninterrupted)
Result:  Complete new playlist built while show runs
```

### Technical Implementation

**Preview Updates (Frontend):**
```javascript
// When user views a playlist (active or inactive)
function onPlaylistViewed(viewedPlaylist) {
    // Update GUI to show viewed playlist
    renderPlaylist(viewedPlaylist.players.video.clips);
    renderPlaylist(viewedPlaylist.players.artnet.clips);
    
    // Preview canvas shows viewed playlist content
    updateCanvasPreview(viewedPlaylist);
    
    // Active playlist continues running independently
}

// When user clicks a clip in viewed playlist
async function previewClip(clipId) {
    // Load clip to preview canvas (no Art-Net output)
    await loadClipPreview(clipId, viewedPlaylistId);
    
    // Active playlist's Art-Net output unchanged
}
```

**Output Control (Backend):**
```python
# Player's _play_loop() always uses active playlist settings
def _play_loop(self):
    # Get clips from active playlist
    active_playlist = playlist_system.get_active_playlist()
    
    # Art-Net output from active playlist's current clip
    frame = self.get_current_frame()
    self.artnet_manager.send_frame(frame)
    
    # Autoplay/loop from active playlist
    if active_playlist.players[self.player_id].autoplay:
        self.advance_to_next_clip()
```

### UI Indicators

**Clear status display:**
```
┌────────────────────────────────────────────┐
│ 🔴 ACTIVE: "Main Show" (clip 5/20)        │  ← What's outputting to Art-Net
│ 👁️ VIEWING: "Encore" (editing)             │  ← What's shown in preview
└────────────────────────────────────────────┘
```

**Tab display:**
```
[● Main Show] [Encore] [Outro]
   ↑ Active    ↑ Viewed  ↑ Inactive
   (DMX out)   (Preview) (Stored)
```

### Key Benefits

✅ **Independent systems** - Preview and output never conflict  
✅ **Safe editing** - Edit any playlist without disrupting output  
✅ **Preview inactive playlists** - Check content before activating  
✅ **Continuous output** - Art-Net never interrupted during editing  
✅ **Flexible workflow** - Preview and prepare multiple playlists in advance  
✅ **Clear separation** - Always know what's live vs. what's being edited

---

## 🔄 Playlist Cycling (Auto-Chaining)

### Feature: Automatic Playlist Advancement

Playlists can automatically switch to another playlist when they finish, enabling complex automated show sequences without manual intervention.

### Configuration

Each playlist has an optional `next_playlist_id` field:
```python
@dataclass
class Playlist:
    # ... other fields ...
    next_playlist_id: Optional[str] = None  # Playlist to activate when this ends
```

### How It Works

**Detection of Playlist End:**
- Player reaches last clip in playlist **with autoplay=True**
- `autoplay=True` AND `loop=False` AND no more clips to play
- **Manual navigation past last clip does NOT trigger cycling**
- Player signals "playlist complete" event

**Auto-Switch Logic:**
```python
# In player's _play_loop() when reaching end:
if self.playlist_index >= len(self.playlist) - 1:
    if not self.loop_playlist and self.autoplay:  # ONLY if autoplay is enabled
        # Check if playlist has next_playlist_id
        active_playlist = playlist_system.get_active_playlist()
        if active_playlist.next_playlist_id:
            # Auto-switch to next playlist
            playlist_system.switch_playlist(active_playlist.next_playlist_id)
            logger.info(f"🔄 Auto-switching to playlist: {active_playlist.next_playlist_id}")
        else:
            # No next playlist - stop
            break
```

### Example Configurations

**1. Linear Chain (Intro → Main → Outro → Stop)**
```python
Intro:  next_playlist_id = "main_show"
Main:   next_playlist_id = "outro"
Outro:  next_playlist_id = None  # Stops here
```

**2. Infinite Loop (Intro → Main → Back to Intro)**
```python
Intro:  next_playlist_id = "main_loop"
Main:   next_playlist_id = "intro"  # Cycles back
```

**3. Multi-Act Show**
```python
Act1:   next_playlist_id = "intermission_1"
Int1:   next_playlist_id = "act_2"
Act2:   next_playlist_id = "intermission_2"
Int2:   next_playlist_id = "act_3"
Act3:   next_playlist_id = "finale"
Finale: next_playlist_id = "act_1"  # Full cycle
```

**4. Exhibition Loop (Short Intro, Long Main)**
```python
Intro:  autoplay=True, loop=False, next_playlist_id = "main_content"
Main:   autoplay=True, loop=True, next_playlist_id = None
# Plays intro once, then loops main content forever
```

### API Endpoints

```python
# Set next playlist for cycling
@app.route('/api/playlists/<playlist_id>/chain', methods=['POST'])
def set_playlist_chain(playlist_id):
    """
    Configure playlist cycling/chaining.
    Set next_playlist_id to auto-switch when current playlist ends.
    """
    data = request.get_json()
    next_playlist_id = data.get('next_playlist_id')  # Can be None to disable
    
    playlist_system = get_playlist_system()
    playlist = playlist_system.get_playlist(playlist_id)
    
    if not playlist:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
    
    # Validate next_playlist_id exists
    if next_playlist_id and next_playlist_id not in playlist_system.playlists:
        return jsonify({"success": False, "error": "Next playlist not found"}), 404
    
    # Detect circular references (optional safety check)
    if next_playlist_id == playlist_id:
        return jsonify({"success": False, "error": "Cannot chain to self (use loop=True instead)"}), 400
    
    playlist.next_playlist_id = next_playlist_id
    playlist.modified_at = time.time()
    
    return jsonify({
        "success": True,
        "playlist_id": playlist_id,
        "next_playlist_id": next_playlist_id
    })

# Get playlist chain info
@app.route('/api/playlists/<playlist_id>/chain', methods=['GET'])
def get_playlist_chain(playlist_id):
    """Get next_playlist_id for a playlist."""
    playlist_system = get_playlist_system()
    playlist = playlist_system.get_playlist(playlist_id)
    
    if not playlist:
        return jsonify({"success": False, "error": "Playlist not found"}), 404
    
    return jsonify({
        "success": True,
        "playlist_id": playlist_id,
        "next_playlist_id": playlist.next_playlist_id
    })
```

### Frontend UI

**Context Menu Addition:**
```javascript
contextMenu.innerHTML = `
    <div class="context-menu-item" data-action="activate">▶️ Activate (Make Active)</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" data-action="chain">🔗 Set Next Playlist...</div>
    <div class="context-menu-item" data-action="rename">✏️ Rename</div>
    <div class="context-menu-item" data-action="duplicate">📋 Duplicate</div>
    <div class="context-menu-separator"></div>
    <div class="context-menu-item" data-action="delete">🗑️ Delete</div>
`;
```

**Chain Configuration Dialog:**
```javascript
async function setPlaylistChain(playlistId) {
    // Show dialog with dropdown of all playlists
    const playlists = await fetchPlaylists();
    const nextId = await showChainDialog(playlists, playlistId);
    
    if (nextId !== undefined) {
        await fetch(`/api/playlists/${playlistId}/chain`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ next_playlist_id: nextId })
        });
    }
}
```

**Visual Chain Indicator:**
```
[Intro] → [Main Show] → [Outro]
   ↓____________________↑
   (cycles back)
```

### Use Cases

**Museum Exhibition:**
- "Welcome" (1 min) → "Main Content" (10 min, loops) → repeat
- Intro plays once per cycle, main content loops within itself

**Retail Store:**
- "Morning" (8am-12pm) → "Afternoon" (12pm-5pm) → "Evening" (5pm-8pm)
- Time-based but can also use manual/automatic playlist advancement

**Theater Performance:**
- Act 1 → Intermission graphics → Act 2 → Intermission → Act 3 → Finale
- Fully automated multi-hour performance

**Trade Show Booth:**
- "Attract" (eye-catching loop) → "Demo" (detailed product) → "Attract" (repeat)
- Automatically cycles to draw attention

### Safety Features

1. **Circular Reference Detection**: Prevent playlist → self (use loop=True instead)
2. **Missing Playlist Fallback**: If next_playlist_id doesn't exist, stop instead of crash
3. **Manual Override**: User can always manually activate any playlist to break the cycle
4. **UI Warning**: Show warning if chain creates infinite loop without user confirmation

### Implementation Notes

**Detection Point:**
In `player_core.py` `_play_loop()` method:
```python
if next_item_path is None:
    # End of playlist reached
    # Check for playlist chaining
    if self.player_manager and hasattr(self.player_manager, 'playlist_system'):
        active = self.player_manager.playlist_system.get_active_playlist()
        if active and active.next_playlist_id:
            # Auto-switch to next playlist
            self.player_manager.playlist_system.switch_playlist(active.next_playlist_id)
            continue  # Continue playback with new playlist
    break  # No chaining, stop playback
```

---

## ⚠️ Critical: Autoplay & Playback State Management

### Important: Only Active Playlist Controls Playback

**The viewed playlist is for GUI editing only** - it does NOT affect playback at all!

- Active Playlist: Controls player behavior (autoplay, loop, clips)
- Viewed Playlist: GUI display only (user can edit freely)

When user edits a non-active playlist:
- Changes are saved to that playlist's state
- Active playlist continues playing with its own settings
- No interference between active and viewed playlists

### Problem

**Each playlist stores `autoplay` and `loop` settings separately**, but only the **ACTIVE playlist's settings should control playback**. The issue:

1. **Playlist A** is active with `autoplay=True, loop=True` and video is playing
2. User **switches to Playlist B** which has `autoplay=False, loop=False`  
3. **What should happen**: Current clip keeps playing, but when it ends, use Playlist B's `autoplay=False` (don't advance)
4. **Critical**: Inactive playlists must NOT interfere with active playlist's playback behavior

### Root Cause

- When `apply_playlist()` runs, it sets `player.autoplay = player_state.autoplay`
- The player's `_play_loop()` thread reads `self.playlist_manager.autoplay` to decide what to do when clip ends
- **This already works correctly!** The new playlist's autoplay setting takes effect immediately
- **The actual issue**: We need to ensure only the active playlist's settings are applied

### Solution: Track Playback State Per Playlist

Each playlist must remember whether each player was **actively playing** so we can restore the correct state when switching back:

```python
@dataclass
class PlayerState:
    # ... existing fields ...
    is_playing: bool = False  # NEW: Whether player is actively playing in THIS playlist
```

**Workflow:**
1. **Before switching playlists**: `save_current_state()` captures `player.is_playing` state
2. **When switching**: `apply_playlist()` applies new clips, autoplay, loop settings **WITHOUT stopping players**
3. **Current clip continues playing**: Uses the NEW playlist's autoplay/loop settings going forward
4. **Settings take effect immediately**: When current clip ends, the active playlist's autoplay determines behavior

### Updated apply_playlist() Logic

```python
def apply_playlist(self, playlist_id: str):
    """
    Apply playlist state to all players.
    IMPORTANT: Does NOT stop currently playing clips - they continue playing.
    The new playlist's autoplay/loop settings take effect immediately.
    """
    playlist = self.playlists.get(playlist_id)
    if not playlist:
        return
    
    # Apply to each player (current playback continues)
    for player_id in ['video', 'artnet', 'sequencer']:
        player = self.player_manager.get_player(player_id)
        if player:
            player_state = playlist.get_player_state(player_id)
            if player_state:
                # Apply clips and settings immediately
                player.playlist = player_state.clips
                player.playlist_ids = player_state.clip_ids
                player.playlist_index = player_state.index
                player.autoplay = player_state.autoplay  # Takes effect immediately
                player.loop_playlist = player_state.loop  # Takes effect immediately
                player.playlist_params = player_state.clip_params
                
                logger.info(f"Applied playlist '{playlist.name}' to {player_id}: "
                           f"{len(player_state.clips)} clips, autoplay={player_state.autoplay}, "
                           f"loop={player_state.loop}")
    
    # Apply master/slave configuration
    if hasattr(self.player_manager, 'set_master_playlist'):
        self.player_manager.set_master_playlist(playlist.master_player)
```

### Why This Matters

**Key Insight**: The player's `_play_loop()` checks `self.playlist_manager.autoplay` **every time a clip ends**. When we call `player.autoplay = player_state.autoplay`, that setting takes effect immediately for the next decision.

**Example Scenarios:**

1. **Playlist A (autoplay=True, playing) → Playlist B (autoplay=False)**
   - Current clip continues playing
   - When it ends, checks `player.autoplay` → now `False`
   - Stops instead of advancing to next clip ✅

2. **Playlist B (autoplay=False, stopped) → Playlist A (autoplay=True)**
   - No clips playing, so nothing happens immediately
   - Settings are ready: if user plays a clip, autoplay=True will work ✅

3. **Switching back and forth**
   - Each playlist's `is_playing` state is preserved
   - Can restore which players were playing in each playlist
   - Active playlist's settings always control behavior ✅

**Critical Rule**: Only the ACTIVE playlist's autoplay/loop settings affect playback. Inactive playlists are just stored state.

### Implementation Checklist

- [x] Add `is_playing: bool` field to `PlayerState` dataclass
- [ ] Update `save_current_state()` to capture `player.is_playing` and auto-save to disk
- [ ] Ensure `apply_playlist()` does NOT stop players (just applies settings)
- [ ] Update JSON format examples to include `is_playing` field
- [ ] Add WebSocket event emission on playlist activation
- [ ] Implement left-click = view, right-click menu = activate behavior
- [ ] Remove `/api/playlists/switch` endpoint (use `/activate` and `/view`)
- [ ] Handle chain deletion (skip to next playlist in sequence)
- [ ] Test scenario: Playlist A (autoplay=True, playing clip 1) → Playlist B (autoplay=False) → Verify clip 1 finishes but doesn't advance
- [ ] Test scenario: Playlist A (playing video 2/5) → switch → switch back to A → Verify state preserved
- [ ] Test scenario: Inactive playlist with autoplay=True should NOT affect active playlist playback
- [ ] Test scenario: Cycling only triggers on autoplay (not manual navigation)

---

## 📝 Notes

- **Playlist switching**: Should be instant (no loading delay)
- **Memory**: Keep all playlists in memory for fast switching (no artificial limits)
- **Persistence**: Auto-save immediately on any playlist change (clips, settings, rename, etc.)
- **UI feedback**: Show loading state during switch
- **Hotkeys**: Add keyboard shortcuts for playlist switching (1-9)
- **Drag-drop**: Support drag-drop clips between playlists
- **Templates**: Save playlist as template for reuse
- **Import/Export**: Individual playlist import/export
- **Tab clicks**: Left-click views/edits playlist (GUI), right-click menu activates (playback)
- **WebSocket**: Emit events on playlist activation to update all connected clients
- **Chain deletion**: Automatically update chains to skip deleted playlist
- **No migration**: Old single-playlist format NOT supported (clean break)

---

## 🔮 Future Enhancements

1. **Playlist Cycling (PRIORITY)**: Automatic playlist chaining
   - Each playlist can specify `next_playlist_id` to auto-advance
   - When playlist ends (autoplay reaches last clip), switch to next playlist
   - Create show sequences: Intro → Main → Outro → loop back
   - UI: Visual chain indicator showing playlist flow
   - Cycle modes: Once, Repeat, Stop

2. **Playlist Groups**: Folder structure for playlists
3. **Playlist Templates**: Save/load playlist templates
4. **Playlist Sync**: Sync playlists between players
5. **Playlist Merge**: Merge multiple playlists
6. **Smart Playlists**: Auto-populate based on rules
7. **Playlist Scheduling**: Time-based playlist switching
- [ ] Verify `apply_playlist()` does NOT stop players (just applies settings)
- [ ] Update JSON format examples to include `is_playing` field
- [ ] Test scenario: Playlist A (autoplay=True, playing clip 1) → Playlist B (autoplay=False) → Verify clip 1 finishes but doesn't advance
- [ ] Test scenario: Playlist A (playing video 2/5) → switch → switch back to A → Verify state preserved
- [ ] Test scenario: Inactive playlist with autoplay=True should NOT affect active playlist playback
## ✅ Success Criteria

- [ ] Can create unlimited playlists per player
- [ ] Can switch between playlists instantly
- [ ] Each playlist has independent settings
- [ ] UI shows all playlists clearly
- [ ] Playlists persist across restarts (auto-save)
- [ ] No performance degradation with many playlists
- [ ] Clear visual indication of active vs. viewed playlist
- [ ] Easy playlist management (rename, delete, duplicate)
- [ ] Left-click tab = view/edit, right-click menu = activate
- [ ] WebSocket events update all clients on playlist changes
- [ ] Chain deletion automatically handled

---

## ✅ Design Decisions Summary

**Finalized Behaviors:**

1. **Session state saving:** Auto-save immediately on any playlist change
2. **Master/Slave:** Uses existing implementation, no changes needed
3. **Playlist cycling:** Only triggers on autoplay reaching end (not manual navigation)
4. **Migration:** No backwards compatibility - old format NOT supported (clean break)
5. **Tab interaction:** Left-click = view/edit (GUI), Right-click menu = activate (playback)
6. **API design:** Simplified - `/activate` for playback, `/view` for GUI, removed `/switch`
7. **Chain deletion:** Auto-update chains to skip deleted playlist
8. **Resource limits:** No limits - user manages memory/CPU/GPU
9. **WebSocket:** Emit events on playlist activation for multi-client sync
10. **Playlist IDs:** UUID for uniqueness, `name` field for human readability

---

## 📚 References

- [UNIFIED_PLAYLISTS.md](UNIFIED_PLAYLISTS.md) - Unified player system
- [SETLIST_PLAYLISTS.md](SETLIST_PLAYLISTS.md) - Setlist architecture (similar concept)
- [PLAYER_EXECUTION_FLOW.md](PLAYER_EXECUTION_FLOW.md) - Player execution flow
- `src/modules/player/playlist_manager.py` - Current single playlist implementation
