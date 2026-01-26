# Multi-Playlist System - Complete Implementation Plan

**Date:** January 23, 2026  
**Status:** Planning Phase  
**Author:** Architecture Document

---

## Executive Summary

This document outlines a complete, well-thought-out implementation plan for the multi-playlist system with per-playlist sequencer timelines and modes. This replaces the previous iterative approach that led to confusion and bugs.

---

## Core Requirements

### 1. Playlist Concepts

**ACTIVE Playlist:**
- The playlist that controls actual playback
- Its settings are applied to physical players (video, artnet, sequencer)
- Only ONE playlist can be active at a time
- When you activate a playlist, playback switches to it

**VIEWED Playlist:**
- The playlist you're currently looking at/editing in the GUI
- Can be different from the active playlist
- Allows you to edit a playlist while another one is playing
- Changes are saved to the viewed playlist only

**Example Workflow:**
```
1. Default playlist is ACTIVE (playing)
2. User creates "Test" playlist
3. User clicks "Test" tab → Test becomes VIEWED (Default still active/playing)
4. User edits Test (adds clips, enables sequencer, etc.)
5. All changes save to Test playlist only
6. Default continues playing unchanged
7. User right-clicks Test → "Activate" → Test becomes ACTIVE (applies to players)
```

### 2. Per-Playlist Settings

Each playlist stores:
- **Player clips:** Separate clip lists for video/artnet/sequencer players
- **Player settings:** autoplay, loop, index for each player
- **Sequencer timeline:** Complete timeline with splits, audio file, clip mappings
- **Sequencer mode:** ON (master) or OFF (normal master/slave)
- **Master/slave config:** Which player is master when sequencer OFF

### 3. Key Behaviors

**Viewing a Playlist (left-click tab):**
- GUI updates to show that playlist's content
- Sequencer toggle shows that playlist's saved sequencer mode
- Player lists show that playlist's clips
- Active playlist continues playing in background

**Activating a Playlist (right-click → Activate):**
- Stops applying changes to old active playlist
- Applies new playlist's settings to all physical players
- Loads sequencer timeline from new playlist
- Applies sequencer mode from new playlist
- Switches master/slave configuration
- New playlist becomes both ACTIVE and VIEWED

**Adding a Clip:**
- Clip is added to VIEWED playlist only
- If viewed == active: physical players update immediately
- If viewed != active: clip saved for later, no immediate playback change

**Enabling Sequencer Mode:**
- Sequencer mode saved to VIEWED playlist only
- If viewed == active: physical sequencer mode changes immediately
- If viewed != active: mode saved for later, no immediate change

**Saving Changes:**
- All changes (clips, settings, timeline, mode) save to VIEWED playlist
- Active playlist auto-saves when it changes (clip added, mode toggled, etc.)
- Inactive playlists save when edited

### 4. Session State Layout Example

The session state JSON will look like this:

```json
{
  "version": "1.0",
  "timestamp": "2026-01-23T14:30:00",
  "multi_playlist_system": {
    "active_playlist_id": "bd4f63fb-408b-48b8-890c-b029170894c7",
    "viewed_playlist_id": "bd4f63fb-408b-48b8-890c-b029170894c7",
    "playlists": [
      {
        "id": "bd4f63fb-408b-48b8-890c-b029170894c7",
        "name": "Default",
        "type": "standard",
        "created_at": "2026-01-23T14:00:00",
        "sequencer_mode": false,
        "master_player": "video",
        "players": {
          "video": {
            "clips": [
              "video/clip1.mp4",
              "video/clip2.mp4"
            ],
            "clip_ids": [
              "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
              "b2c3d4e5-f6a7-8901-bcde-f12345678901"
            ],
            "clip_params": {},
            "index": 0,
            "autoplay": true,
            "loop": true,
            "is_playing": true,
            "settings": {}
          },
          "artnet": {
            "clips": [
              "generator:rainbow"
            ],
            "clip_ids": [
              "c3d4e5f6-a7b8-9012-cdef-123456789012"
            ],
            "clip_params": {
              "rainbow": {"speed": 0.5, "brightness": 1.0}
            },
            "index": 0,
            "autoplay": true,
            "loop": true,
            "is_playing": true,
            "settings": {}
          },
          "sequencer": {
            "clips": [],
            "clip_ids": [],
            "clip_params": {},
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {
              "timeline": null
            }
          }
        }
      },
      {
        "id": "93294b95-a7fa-4ef3-b13c-67afd648a0b9",
        "name": "Test",
        "type": "standard",
        "created_at": "2026-01-23T14:15:00",
        "sequencer_mode": true,
        "master_player": "video",
        "players": {
          "video": {
            "clips": [
              "video/test_clip.mp4"
            ],
            "clip_ids": [
              "d4e5f6a7-b8c9-0123-def0-123456789abc"
            ],
            "clip_params": {},
            "index": 0,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {}
          },
          "artnet": {
            "clips": [],
            "clip_ids": [],
            "clip_params": {},
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {}
          },
          "sequencer": {
            "clips": [],
            "clip_ids": [],
            "clip_params": {},
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {
              "timeline": {
                "audio_file": "audio/test_song.mp3",
                "duration": 180.5,
                "splits": [
                  {"time": 0.0, "id": 0},
                  {"time": 30.5, "id": 1},
                  {"time": 60.0, "id": 2},
                  {"time": 90.5, "id": 3}
                ],
                "clip_mapping": {
                  "0": {
                    "video": "d4e5f6a7-b8c9-0123-def0-123456789abc",
                    "artnet": null
                  },
                  "1": {
                    "video": "d4e5f6a7-b8c9-0123-def0-123456789abc",
                    "artnet": null
                  },
                  "2": {
                    "video": null,
                    "artnet": null
                  }
                }
              }
            }
          }
        }
      },
      {
        "id": "f1234567-89ab-cdef-0123-456789abcdef",
        "name": "Live Show",
        "type": "live",
        "created_at": "2026-01-23T14:20:00",
        "sequencer_mode": true,
        "master_player": "sequencer",
        "players": {
          "video": {
            "clips": [
              "video/intro.mp4",
              "video/verse1.mp4",
              "video/chorus.mp4",
              "video/verse2.mp4",
              "video/outro.mp4"
            ],
            "clip_ids": [
              "e5f6a7b8-c9d0-1234-ef01-23456789abcd",
              "f6a7b8c9-d0e1-2345-f012-3456789abcde",
              "a7b8c9d0-e1f2-3456-0123-456789abcdef",
              "b8c9d0e1-f2a3-4567-1234-56789abcdef0",
              "c9d0e1f2-a3b4-5678-2345-6789abcdef01"
            ],
            "clip_params": {},
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {}
          },
          "artnet": {
            "clips": [
              "generator:strobe",
              "generator:rainbow",
              "generator:pulse"
            ],
            "clip_ids": [
              "d0e1f2a3-b4c5-6789-3456-789abcdef012",
              "e1f2a3b4-c5d6-789a-4567-89abcdef0123",
              "f2a3b4c5-d6e7-89ab-5678-9abcdef01234"
            ],
            "clip_params": {
              "strobe": {"frequency": 10.0, "brightness": 1.0},
              "rainbow": {"speed": 1.0, "brightness": 0.8},
              "pulse": {"speed": 0.3, "color": [255, 0, 0]}
            },
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {}
          },
          "sequencer": {
            "clips": [],
            "clip_ids": [],
            "clip_params": {},
            "index": -1,
            "autoplay": false,
            "loop": false,
            "is_playing": false,
            "settings": {
              "timeline": {
                "audio_file": "audio/live_song.mp3",
                "duration": 240.0,
                "splits": [
                  {"time": 0.0, "id": 0},
                  {"time": 8.0, "id": 1},
                  {"time": 32.0, "id": 2},
                  {"time": 64.0, "id": 3},
                  {"time": 96.0, "id": 4},
                  {"time": 128.0, "id": 5},
                  {"time": 160.0, "id": 6},
                  {"time": 192.0, "id": 7},
                  {"time": 224.0, "id": 8}
                ],
                "clip_mapping": {
                  "0": {
                    "video": "e5f6a7b8-c9d0-1234-ef01-23456789abcd",
                    "artnet": null
                  },
                  "1": {
                    "video": "f6a7b8c9-d0e1-2345-f012-3456789abcde",
                    "artnet": "d0e1f2a3-b4c5-6789-3456-789abcdef012"
                  },
                  "2": {
                    "video": "a7b8c9d0-e1f2-3456-0123-456789abcdef",
                    "artnet": "e1f2a3b4-c5d6-789a-4567-89abcdef0123"
                  },
                  "3": {
                    "video": "f6a7b8c9-d0e1-2345-f012-3456789abcde",
                    "artnet": "e1f2a3b4-c5d6-789a-4567-89abcdef0123"
                  },
                  "4": {
                    "video": "b8c9d0e1-f2a3-4567-1234-56789abcdef0",
                    "artnet": "f2a3b4c5-d6e7-89ab-5678-9abcdef01234"
                  },
                  "5": {
                    "video": "a7b8c9d0-e1f2-3456-0123-456789abcdef",
                    "artnet": "e1f2a3b4-c5d6-789a-4567-89abcdef0123"
                  },
                  "6": {
                    "video": "f6a7b8c9-d0e1-2345-f012-3456789abcde",
                    "artnet": "d0e1f2a3-b4c5-6789-3456-789abcdef012"
                  },
                  "7": {
                    "video": "c9d0e1f2-a3b4-5678-2345-6789abcdef01",
                    "artnet": null
                  }
                }
              }
            }
          }
        }
      }
    ]
  },
  "clip_registry": {
    "clips": {
      "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
        "clip_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "player_id": "video",
        "absolute_path": "C:/Users/.../video/clip1.mp4",
        "relative_path": "video/clip1.mp4",
        "filename": "clip1.mp4",
        "metadata": {},
        "created_at": "2026-01-23T14:00:00",
        "effects": []
      }
    }
  }
}
```

**Key Points:**
- `active_playlist_id`: Which playlist is currently controlling playback
- `viewed_playlist_id`: Which playlist the GUI is showing
- Each playlist has complete state for all 3 players (video, artnet, sequencer)
- Sequencer timeline stored in `players.sequencer.settings.timeline`
- Sequencer mode stored per-playlist in `sequencer_mode`
- Clip UUIDs used everywhere for clip identification
- Generator parameters stored in `clip_params`

---

## Technical Architecture

### Phase 1: Core Data Structures

#### File: `src/modules/multi_playlist_system.py`

**PlayerState Class:**
```python
class PlayerState:
    """State for a single player within a playlist"""
    def __init__(self):
        self.clips = []           # List of clip paths/generator IDs
        self.clip_ids = []        # List of UUIDs matching clips
        self.clip_params = {}     # Generator parameters
        self.index = -1           # Current playlist index
        self.autoplay = False     # Autoplay enabled
        self.loop = False         # Loop playlist
        self.is_playing = False   # Playing state
        self.settings = {}        # Additional settings (sequencer timeline, etc.)
```

**Playlist Class:**
```python
class Playlist:
    """A complete playlist with all player states"""
    def __init__(self, name, type='standard'):
        self.id = str(uuid.uuid4())
        self.name = name
        self.type = type  # 'standard', 'live', 'sequence'
        self.created_at = datetime.now()
        
        # Player states
        self.players = {
            'video': PlayerState(),
            'artnet': PlayerState(),
            'sequencer': PlayerState()
        }
        
        # Configuration
        self.sequencer_mode = False  # True = sequencer is master
        self.master_player = 'video'  # Master when sequencer_mode=False
    
    def get_player_state(self, player_id):
        return self.players.get(player_id)
```

**MultiPlaylistSystem Class:**
```python
class MultiPlaylistSystem:
    """Manages multiple playlists and switching between them"""
    def __init__(self, player_manager, session_state, websocket_manager):
        self.player_manager = player_manager
        self.session_state = session_state
        self.websocket_manager = websocket_manager
        
        self.playlists = {}  # {playlist_id: Playlist}
        self.active_playlist_id = None   # Currently controlling playback
        self.viewed_playlist_id = None   # Currently shown in GUI
    
    def create_playlist(self, name, type='standard') -> Playlist
    def delete_playlist(self, playlist_id) -> bool
    def rename_playlist(self, playlist_id, new_name) -> bool
    
    def activate_playlist(self, playlist_id) -> bool
    def set_viewed_playlist(self, playlist_id) -> bool
    
    def get_active_playlist() -> Playlist
    def get_viewed_playlist() -> Playlist
    
    def apply_playlist(self, playlist_id) -> None
    def capture_active_playlist_state() -> None
    
    def serialize_all() -> dict
    def load_from_dict(data) -> bool
```

### Phase 2: Backend Integration

#### Changes to `src/main.py`

**After PlayerManager initialization:**
```python
# Initialize multi-playlist system
from .modules.multi_playlist_system import MultiPlaylistSystem
from .modules.api_playlists import register_playlist_routes, set_playlist_system

playlist_system = MultiPlaylistSystem(player_manager, session_state, None)
set_playlist_system(playlist_system)
player_manager.playlist_system = playlist_system

# Create default playlist if none exist
if len(playlist_system.playlists) == 0:
    default_playlist = playlist_system.create_playlist("Default", "standard")
    playlist_system.activate_playlist(default_playlist.id)

# Register API routes
register_playlist_routes(rest_api.app, player_manager, rest_api.socketio)

# Connect websocket after socketio is ready
player_manager.playlist_system.websocket_manager = rest_api.socketio
```

#### Changes to `src/modules/session_state.py`

**In `_build_state_dict()` method:**
```python
# Save multi-playlist system
if hasattr(player_manager, 'playlist_system') and player_manager.playlist_system:
    # Capture current active playlist state before saving
    player_manager.playlist_system.capture_active_playlist_state()
    state['multi_playlist_system'] = player_manager.playlist_system.serialize_all()
```

**In `restore()` method:**
```python
# Restore multi-playlist system
multi_playlist_data = state.get('multi_playlist_system')
if multi_playlist_data and hasattr(player_manager, 'playlist_system'):
    success = player_manager.playlist_system.load_from_dict(multi_playlist_data)
    if success:
        logger.info(f"Restored {len(multi_playlist_data.get('playlists', []))} playlists")
```

#### File: `src/modules/api_playlists.py`

**API Endpoints:**

```python
# Playlist CRUD
POST   /api/playlists/create         # Create new playlist
DELETE /api/playlists/<id>           # Delete playlist
PUT    /api/playlists/<id>/rename    # Rename playlist
GET    /api/playlists/list           # List all playlists

# Playlist control
POST   /api/playlists/activate       # Activate playlist (apply to players)
POST   /api/playlists/view           # View playlist (GUI only)
GET    /api/playlists/<id>           # Get playlist details

# State management
POST   /api/playlists/save-state     # Manually save current state to viewed playlist
```

**Critical Logic - View Playlist Response:**

```python
@app.route('/api/playlists/view', methods=['POST'])
def view_playlist():
    """Set which playlist the GUI is displaying/editing"""
    playlist_id = request.json.get('playlist_id')
    playlist_system.set_viewed_playlist(playlist_id)
    
    viewed = playlist_system.get_viewed_playlist()
    active_id = playlist_system.active_playlist_id
    is_active = viewed.id == active_id
    
    if is_active:
        # Get LIVE data from physical players
        players_data = {
            'video': {
                'clips': list(video_player.playlist),
                'sequencer_mode': player_manager.sequencer_mode_active,
                # ... other live state
            }
        }
    else:
        # Get SAVED data from playlist object
        players_data = {
            'video': {
                'clips': viewed.players['video'].clips,
                'sequencer_mode': viewed.sequencer_mode,  # From playlist!
                # ... other saved state
            }
        }
    
    return jsonify({
        'viewed_playlist': {
            'id': viewed.id,
            'name': viewed.name,
            'is_active': is_active,
            'sequencer_mode': viewed.sequencer_mode,  # Always from playlist
            'players': players_data
        }
    })
```

**Critical Logic - Activate Playlist:**

```python
def activate_playlist(playlist_id):
    """Activate playlist (apply to physical players)"""
    # 1. Capture current active playlist state
    if active_playlist_id:
        capture_active_playlist_state()
    
    # 2. Apply new playlist
    playlist = playlists[playlist_id]
    
    # Apply player clips and settings
    for player_id in ['video', 'artnet', 'sequencer']:
        player = player_manager.get_player(player_id)
        player_state = playlist.get_player_state(player_id)
        
        player.playlist = player_state.clips.copy()
        player.playlist_ids = player_state.clip_ids.copy()
        player.playlist_index = player_state.index
        player.autoplay = player_state.autoplay
        player.loop_playlist = player_state.loop
    
    # Apply sequencer timeline
    if playlist.players['sequencer'].settings.get('timeline'):
        timeline_data = playlist.players['sequencer'].settings['timeline']
        player_manager.sequencer.timeline.from_dict(timeline_data)
    else:
        player_manager.sequencer.timeline.clear_splits()
    
    # Apply sequencer mode
    player_manager.set_sequencer_mode(playlist.sequencer_mode)
    
    # Apply master/slave config
    player_manager.set_master_playlist(playlist.master_player)
    
    # 3. Update state
    self.active_playlist_id = playlist_id
    self.viewed_playlist_id = playlist_id
    
    # 4. Save and broadcast
    self._auto_save()
    emit_websocket('playlist_activated', {...})
```

#### Changes to `src/modules/api_sequencer.py`

**CRITICAL: Save timeline changes to VIEWED playlist**

After every timeline modification (upload audio, add split, remove split, change clip mapping):

```python
def after_timeline_change():
    """Save timeline to viewed playlist after any change"""
    try:
        playlist_system = get_playlist_system()
        if playlist_system:
            viewed = playlist_system.get_viewed_playlist()
            if viewed:
                # Save timeline to viewed playlist
                sequencer_state = viewed.players['sequencer']
                sequencer_state.settings['timeline'] = player_manager.sequencer.timeline.to_dict()
                playlist_system._auto_save()
    except Exception as e:
        logger.error(f"Failed to save timeline to playlist: {e}")
```

**Call this after:**
1. Audio upload (`/api/sequencer/upload`)
2. Audio load (`/api/sequencer/load`)
3. Split add (`/api/sequencer/split/add`)
4. Split remove (`/api/sequencer/split/remove`)
5. Clip mapping (`/api/sequencer/split/<id>/mapping`)

**CRITICAL: Sequencer mode toggle**

```python
@app.route('/api/sequencer/mode', methods=['POST'])
def set_sequencer_mode():
    """Enable/disable sequencer mode"""
    enabled = request.json.get('enabled', False)
    
    playlist_system = get_playlist_system()
    if playlist_system:
        viewed = playlist_system.get_viewed_playlist()
        
        # ALWAYS save to viewed playlist
        viewed.sequencer_mode = enabled
        
        # Only apply to physical players if viewed == active
        if viewed.id == playlist_system.active_playlist_id:
            player_manager.set_sequencer_mode(enabled)
        
        playlist_system._auto_save()
    else:
        # Fallback: no playlist system
        player_manager.set_sequencer_mode(enabled)
    
    return jsonify({'success': True, 'enabled': enabled})
```

**CRITICAL: Sequencer status**

```python
@app.route('/api/sequencer/status', methods=['GET'])
def sequencer_get_status():
    """Get sequencer status for VIEWED playlist"""
    
    # Get sequencer mode from VIEWED playlist (not physical player!)
    mode_active = False
    playlist_system = get_playlist_system()
    if playlist_system:
        viewed = playlist_system.get_viewed_playlist()
        if viewed:
            mode_active = viewed.sequencer_mode  # From playlist, not player!
    
    # Get physical timeline/audio data
    return jsonify({
        'mode_active': mode_active,  # From viewed playlist!
        'has_audio': engine.is_loaded,
        'audio_file': audio_file,
        'splits': timeline.splits,
        'clip_mapping': clip_mapping
    })
```

#### Changes to `src/modules/api_player_unified.py`

**CRITICAL: Clip loading saves to VIEWED playlist**

After loading a clip (video or generator):

```python
def after_clip_load(player_id, clip_id):
    """Save clip to viewed playlist after loading"""
    try:
        playlist_system = get_playlist_system()
        if playlist_system:
            viewed = playlist_system.get_viewed_playlist()
            if viewed:
                player = player_manager.get_player(player_id)
                player_state = viewed.players[player_id]
                
                # Save complete player state to viewed playlist
                player_state.clips = list(player.playlist)
                player_state.clip_ids = list(player.playlist_ids)
                player_state.index = player.playlist_index
                player_state.current_clip_id = clip_id
                
                playlist_system._auto_save()
                logger.info(f"💾 Saved clip to viewed playlist '{viewed.name}'")
    except Exception as e:
        logger.warning(f"Failed to save clip to playlist: {e}")
```

### Phase 3: Frontend Integration

#### File: `frontend/js/components/playlist-tabs.js`

**Component Features:**
- Display tabs for all playlists
- Visual indicators: active (green border), viewed (highlighted)
- Left-click: VIEW playlist (edit without affecting playback)
- Right-click: Context menu with Activate, Rename, Delete
- Create new playlist button

**Critical: Click Handlers**

```javascript
// Left-click: VIEW only (no playback change)
async viewPlaylist(playlistId) {
    const response = await fetch('/api/playlists/view', {
        method: 'POST',
        body: JSON.stringify({ playlist_id: playlistId })
    });
    
    const data = await response.json();
    
    // Update GUI to show this playlist
    this.onView(playlistId, data.viewed_playlist);
}

// Right-click → Activate: ACTIVATE (change playback)
async activatePlaylist(playlistId) {
    const response = await fetch('/api/playlists/activate', {
        method: 'POST',
        body: JSON.stringify({ playlist_id: playlistId })
    });
    
    const data = await response.json();
    
    // Update ALL player displays
    this.onActivate(playlistId, data.active_playlist);
}
```

**Critical: onView Callback (in player.html)**

```javascript
playlistTabs.onView = async (playlistId, playlistData) => {
    // Update sequencer toggle to show VIEWED playlist's mode
    const sequencerBtn = document.getElementById('sequencerModeBtn');
    window.sequencerModeActive = playlistData.sequencer_mode;  // From viewed playlist!
    
    if (playlistData.sequencer_mode) {
        sequencerBtn.classList.add('btn-success');
        sequencerBtn.textContent = '🎵 Sequencer: MASTER';
        // Show waveform if this is the active playlist
        if (playlistData.is_active) {
            document.querySelector('.waveform-analyzer-section').style.display = 'grid';
        }
    } else {
        sequencerBtn.classList.remove('btn-success');
        sequencerBtn.textContent = '🎵 Sequencer Mode';
        // Hide waveform if this is NOT the active playlist
        if (!playlistData.is_active) {
            document.querySelector('.waveform-analyzer-section').style.display = 'none';
        }
    }
    
    // Update player lists
    updateVideoPlaylist(playlistData.players.video);
    updateArtnetPlaylist(playlistData.players.artnet);
};
```

#### Changes to `frontend/player.html`

**Add playlist tabs component:**

```html
<head>
    <link rel="stylesheet" href="css/playlist-tabs.css">
</head>

<body>
    <!-- Position between BPM widget and audio analyzer -->
    <div class="middle-section-center">
        <div id="playlistTabs"></div>
    </div>
    
    <script src="js/components/playlist-tabs.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', async () => {
            const playlistTabs = new PlaylistTabsManager('playlistTabs');
            await playlistTabs.init();
            
            playlistTabs.onActivate = async (playlistId, playlist) => {
                // Full refresh when activating
                await refreshAllPlayers();
            };
            
            playlistTabs.onView = async (playlistId, playlist) => {
                // Update GUI to show viewed playlist
                updateSequencerToggle(playlist.sequencer_mode, playlist.is_active);
                updatePlayerLists(playlist.players);
            };
        });
    </script>
</body>
```

---

## Critical Issues & Solutions

### Issue 1: Clips appear in both playlists

**Root Cause:** When loading a clip, it's saved to the physical player's state, but we're not explicitly saving it to the viewed playlist.

**Solution:** In `api_player_unified.py`, after loading a clip, explicitly save the player's complete state (playlist, playlist_ids, index) to the viewed playlist's player state.

### Issue 2: Sequencer mode shows same state for all playlists

**Root Cause:** The `/api/sequencer/status` endpoint returns `player_manager.sequencer_mode_active` (physical player state) instead of the viewed playlist's saved mode.

**Solution:** Change `/api/sequencer/status` to return `viewed_playlist.sequencer_mode` instead of the physical player's state.

### Issue 3: Sequencer mode applies to wrong playlist

**Root Cause:** When toggling sequencer mode, it's applied to the physical player immediately, even if you're viewing a different playlist than the active one.

**Solution:** In `/api/sequencer/mode` endpoint:
1. ALWAYS save mode to viewed playlist
2. Only apply to physical player if `viewed.id == active.id`
3. If viewing inactive playlist, just save for later

### Issue 4: Timeline not isolated per playlist

**Root Cause:** Timeline changes modify the physical sequencer but don't save to the viewed playlist.

**Solution:** After every timeline operation, save the complete timeline to `viewed_playlist.players['sequencer'].settings['timeline']`.

### Issue 5: No way to distinguish active vs viewed

**Root Cause:** Frontend doesn't clearly show which playlist is active vs which is being edited.

**Solution:**
- Active playlist: Green border, icon indicator
- Viewed playlist: Highlighted background
- Both can be same or different
- Status text: "Viewing: Test | Playing: Default"

---

## Implementation Order

### Step 1: Core Backend (No Frontend Yet)
1. Create `multi_playlist_system.py` with all classes
2. Create `api_playlists.py` with all routes
3. Test with curl/Postman - verify create, view, activate work

### Step 2: Integration into Main App
1. Modify `main.py` to initialize playlist system
2. Modify `session_state.py` to save/load playlists
3. Test: Create playlist, restart server, playlists persist

### Step 3: Sequencer Integration
1. Modify `api_sequencer.py` to save timeline to viewed playlist
2. Modify sequencer mode toggle to respect active vs viewed
3. Modify sequencer status to return viewed playlist's mode
4. Test: Create playlist, enable sequencer, switch playlists, modes are separate

### Step 4: Clip Loading Integration
1. Modify `api_player_unified.py` to save clips to viewed playlist
2. Test: Add clip to Test playlist, switch to Default, Test clip not in Default

### Step 5: Frontend Component
1. Create `playlist-tabs.js` component
2. Create `playlist-tabs.css` styles
3. Test standalone: `test-playlist-tabs.html`

### Step 6: Frontend Integration
1. Add component to `player.html`
2. Wire up callbacks (onView, onActivate)
3. Update sequencer toggle to show viewed playlist's mode
4. Update player lists to show viewed playlist's clips

### Step 7: End-to-End Testing
1. Test: Create, view, activate workflow
2. Test: Edit inactive playlist while another plays
3. Test: Sequencer mode per-playlist
4. Test: Clips per-playlist
5. Test: Session persistence

---

## Testing Strategy

### Unit Tests
- `tests/test_multi_playlist_system.py`: Test all MultiPlaylistSystem methods
- `test_quick_architecture.py`: Offline test of playlist independence

### Integration Tests
- `test_integration_multi_playlist.py`: Test with running server
- Test create → view → edit → activate workflow

### Manual Test Cases

**Test Case 1: Basic Workflow**
1. Server starts with Default playlist active
2. Add video clip to Default
3. Create "Test" playlist (should be empty)
4. Click Test tab (view it)
5. Add different video clip to Test
6. Switch back to Default tab
7. **Verify:** Default has only first clip, Test has only second clip

**Test Case 2: Sequencer Mode Isolation**
1. Default playlist active, sequencer OFF
2. Create Test playlist, click to view it
3. Enable sequencer mode on Test (toggle button)
4. **Verify:** Toggle shows ON for Test
5. Switch back to Default tab
6. **Verify:** Toggle shows OFF for Default
7. **Verify:** Physical sequencer is still OFF (Default is active)

**Test Case 3: Edit Inactive Playlist**
1. Default playlist active and playing a video
2. Create Test playlist, view it
3. Add clips to Test, enable sequencer, upload audio, add splits
4. **Verify:** Default continues playing unchanged
5. Right-click Test → Activate
6. **Verify:** Test's settings now apply to players

**Test Case 4: Session Persistence**
1. Create 3 playlists with different settings
2. Restart server
3. **Verify:** All 3 playlists restored with correct settings

---

## Success Criteria

- [ ] Can create multiple playlists
- [ ] Can view one playlist while another is active (playing)
- [ ] Clips added to viewed playlist don't appear in other playlists
- [ ] Sequencer mode toggle shows viewed playlist's mode
- [ ] Sequencer timeline is separate per playlist
- [ ] Activating a playlist applies all its settings to physical players
- [ ] Active playlist continues playing while editing inactive playlist
- [ ] Session state persists all playlists correctly
- [ ] Frontend clearly shows active vs viewed playlist
- [ ] No confusion about which playlist is being edited

---

## Notes

- This is a complete rewrite plan, not an incremental change
- Follow the implementation order exactly
- Test each step before moving to next
- Don't skip integration testing
- Keep active vs viewed distinction clear at all times
