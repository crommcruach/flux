"""
Multi-Playlist System - Core implementation

Manages multiple independent playlists with per-playlist sequencer timelines and modes.
Separates ACTIVE playlist (controls playback) from VIEWED playlist (shown in GUI).
"""

import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from .logger import get_logger

logger = get_logger(__name__)


class PlayerState:
    """State for a single player within a playlist"""
    
    def __init__(self):
        self.clips: List[str] = []           # List of clip paths/generator IDs
        self.clip_ids: List[str] = []        # List of UUIDs matching clips
        self.clip_params: Dict = {}          # Generator parameters {generator_id: params}
        self.index: int = -1                 # Current playlist index
        self.autoplay: bool = True           # Autoplay enabled
        self.loop: bool = True               # Loop playlist
        self.is_playing: bool = False        # Playing state
        self.global_effects: List = []       # Global effects for this player
    
    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            'clips': self.clips.copy(),
            'clip_ids': self.clip_ids.copy(),
            'clip_params': self.clip_params.copy(),
            'index': self.index,
            'autoplay': self.autoplay,
            'loop': self.loop,
            'is_playing': self.is_playing,
            'global_effects': self.global_effects.copy()
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'PlayerState':
        """Deserialize from dictionary"""
        state = PlayerState()
        state.clips = data.get('clips', []).copy()
        state.clip_ids = data.get('clip_ids', []).copy()
        state.clip_params = data.get('clip_params', {}).copy()
        state.index = data.get('index', -1)
        state.autoplay = data.get('autoplay', False)
        state.loop = data.get('loop', False)
        state.is_playing = data.get('is_playing', False)
        state.global_effects = data.get('global_effects', []).copy()
        return state


class Playlist:
    """A complete playlist with all player states"""
    
    def __init__(self, name: str, playlist_type: str = 'standard'):
        self.id: str = str(uuid.uuid4())
        self.name: str = name
        self.type: str = playlist_type  # 'standard', 'live', 'sequence'
        self.created_at: datetime = datetime.now()
        
        # Player states
        self.players: Dict[str, PlayerState] = {
            'video': PlayerState(),
            'artnet': PlayerState()
        }
        
        # Sequencer state (separate from players)
        self.sequencer: Dict = {
            'mode_active': False,
            'timeline': {
                'audio_file': None,
                'duration': 0.0,
                'splits': [],
                'clip_mapping': {},
                'slots': []
            }
        }
        
        # Configuration
        self.master_player: str = None    # Master player for this playlist (None = off)
    
    def get_player_state(self, player_id: str) -> Optional[PlayerState]:
        """Get player state by ID"""
        return self.players.get(player_id)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'created_at': self.created_at.isoformat(),
            'master_player': self.master_player,
            'video': self.players['video'].to_dict(),
            'artnet': self.players['artnet'].to_dict(),
            'sequencer': self.sequencer.copy()
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'Playlist':
        """Deserialize from dictionary"""
        playlist = Playlist(data['name'], data.get('type', 'standard'))
        playlist.id = data['id']
        playlist.created_at = datetime.fromisoformat(data['created_at'])
        playlist.master_player = data.get('master_player', None)
        
        # Restore player states
        playlist.players['video'] = PlayerState.from_dict(data.get('video', {}))
        playlist.players['artnet'] = PlayerState.from_dict(data.get('artnet', {}))
        
        # Restore sequencer state
        playlist.sequencer = data.get('sequencer', {
            'mode_active': False,
            'timeline': {
                'audio_file': None,
                'duration': 0.0,
                'splits': [],
                'clip_mapping': {},
                'slots': []
            }
        })
        
        return playlist


class MultiPlaylistSystem:
    """Manages multiple playlists and switching between them"""
    
    def __init__(self, player_manager, session_state, websocket_manager):
        self.player_manager = player_manager
        self.session_state = session_state
        self.websocket_manager = websocket_manager
        
        self.playlists: Dict[str, Playlist] = {}  # {playlist_id: Playlist}
        self.active_playlist_id: Optional[str] = None   # Currently controlling playback
        self.viewed_playlist_id: Optional[str] = None   # Currently shown in GUI
        
        logger.info("Multi-Playlist System initialized")
    
    # ========================================
    # PLAYLIST CRUD
    # ========================================
    
    def create_playlist(self, name: str, playlist_type: str = 'standard') -> Playlist:
        """Create a new playlist"""
        playlist = Playlist(name, playlist_type)
        self.playlists[playlist.id] = playlist
        
        # Set as viewed if it's the first playlist
        if len(self.playlists) == 1:
            self.viewed_playlist_id = playlist.id
        
        logger.info(f"Created playlist: {name} (id={playlist.id}, type={playlist_type})")
        self._auto_save()
        
        return playlist
    
    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist"""
        if playlist_id not in self.playlists:
            logger.warning(f"Cannot delete playlist: {playlist_id} not found")
            return False
        
        # Don't allow deleting the active playlist
        if playlist_id == self.active_playlist_id:
            logger.warning(f"Cannot delete active playlist: {playlist_id}")
            return False
        
        # Don't allow deleting the last playlist
        if len(self.playlists) <= 1:
            logger.warning("Cannot delete the last playlist")
            return False
        
        playlist = self.playlists[playlist_id]
        del self.playlists[playlist_id]
        
        # Update viewed playlist if we deleted it
        if self.viewed_playlist_id == playlist_id:
            # Switch to active playlist or first available
            self.viewed_playlist_id = self.active_playlist_id or next(iter(self.playlists.keys()))
        
        logger.info(f"Deleted playlist: {playlist.name} (id={playlist_id})")
        self._auto_save()
        
        return True
    
    def rename_playlist(self, playlist_id: str, new_name: str) -> bool:
        """Rename a playlist"""
        if playlist_id not in self.playlists:
            logger.warning(f"Cannot rename playlist: {playlist_id} not found")
            return False
        
        old_name = self.playlists[playlist_id].name
        self.playlists[playlist_id].name = new_name
        
        logger.info(f"Renamed playlist: {old_name} → {new_name}")
        self._auto_save()
        
        return True
    
    def get_playlist(self, playlist_id: str) -> Optional[Playlist]:
        """Get a playlist by ID"""
        return self.playlists.get(playlist_id)
    
    def list_playlists(self) -> List[Playlist]:
        """Get all playlists"""
        return list(self.playlists.values())
    
    # ========================================
    # PLAYLIST CONTROL
    # ========================================
    
    def activate_playlist(self, playlist_id: str) -> bool:
        """
        Activate playlist (apply to physical players).
        This makes the playlist control actual playback.
        """
        if playlist_id not in self.playlists:
            logger.error(f"Cannot activate playlist: {playlist_id} not found")
            return False
        
        # Capture current active playlist state before switching
        if self.active_playlist_id and self.active_playlist_id in self.playlists:
            self.capture_active_playlist_state()
        
        old_playlist_id = self.active_playlist_id
        self.active_playlist_id = playlist_id
        self.apply_playlist(playlist_id)
        
        # Also update viewed playlist to match active
        self.viewed_playlist_id = playlist_id
        
        playlist = self.playlists[playlist_id]
        logger.info(f"Activated playlist: {playlist.name} (id={playlist_id})")
        
        # Emit WebSocket event to all clients
        if self.websocket_manager:
            try:
                self.websocket_manager.emit('playlist_activated', {
                    'playlist_id': playlist_id,
                    'playlist_name': playlist.name,
                    'playlist_type': playlist.type,
                    'old_playlist_id': old_playlist_id
                })
            except Exception as e:
                logger.error(f"Failed to broadcast playlist activation: {e}")
        
        # Auto-save
        self._auto_save()
        
        return True
    
    def set_viewed_playlist(self, playlist_id: str) -> bool:
        """
        Set which playlist the GUI is displaying/editing.
        Does NOT affect playback - active playlist continues in background.
        """
        if playlist_id not in self.playlists:
            logger.error(f"Cannot view playlist: {playlist_id} not found")
            return False
        
        self.viewed_playlist_id = playlist_id
        playlist = self.playlists[playlist_id]
        
        logger.info(f"Viewing playlist: {playlist.name} (id={playlist_id})")
        
        return True
    
    def get_active_playlist(self) -> Optional[Playlist]:
        """Get the currently active playlist"""
        if self.active_playlist_id:
            return self.playlists.get(self.active_playlist_id)
        return None
    
    def get_viewed_playlist(self) -> Optional[Playlist]:
        """Get the currently viewed playlist"""
        if self.viewed_playlist_id:
            return self.playlists.get(self.viewed_playlist_id)
        return None
    
    # ========================================
    # PLAYLIST APPLICATION
    # ========================================
    
    def apply_playlist(self, playlist_id: str) -> None:
        """
        Apply playlist state to all players.
        This loads clips, settings, playback state, and master/slave configuration.
        
        IMPORTANT: Does NOT stop currently playing clips - they continue seamlessly.
        The new playlist's autoplay/loop settings take effect immediately for future decisions.
        
        Args:
            playlist_id: ID of playlist to apply
        """
        playlist = self.playlists.get(playlist_id)
        if not playlist:
            logger.error(f"Cannot apply playlist: {playlist_id} not found")
            return
        
        # Apply to each player (current playback continues) - only video and artnet, sequencer handled separately
        for player_id in ['video', 'artnet']:
            player = self.player_manager.get_player(player_id)
            if player:
                player_state = playlist.get_player_state(player_id)
                if player_state:
                    # Apply state to player (settings take effect immediately)
                    player.playlist = player_state.clips.copy()
                    player.playlist_ids = player_state.clip_ids.copy()
                    player.playlist_index = player_state.index
                    player.autoplay = player_state.autoplay
                    player.loop_playlist = player_state.loop
                    
                    if hasattr(player, 'playlist_params'):
                        player.playlist_params = player_state.clip_params.copy()
                    
                    logger.debug(f"Applied playlist '{playlist.name}' to {player_id}: "
                               f"{len(player_state.clips)} clips, autoplay={player_state.autoplay}, "
                               f"loop={player_state.loop}, index={player_state.index}")
        
        # Apply sequencer mode and timeline
        if self.player_manager.sequencer:
            # Get sequencer state from playlist
            sequencer_data = playlist.sequencer
            
            # Load timeline from playlist
            if sequencer_data.get('timeline'):
                timeline_data = sequencer_data['timeline']
                self.player_manager.sequencer.timeline.from_dict(timeline_data)
                logger.info(f"✅ Loaded sequencer timeline from playlist '{playlist.name}': "
                           f"{len(timeline_data.get('splits', []))} splits, "
                           f"audio: {timeline_data.get('audio_file', 'None')}")
            else:
                # Clear timeline if playlist has no timeline data
                self.player_manager.sequencer.timeline.clear_splits()
                logger.info(f"🗑️ Cleared sequencer timeline (playlist '{playlist.name}' has no timeline)")
        
        # Apply sequencer mode for this playlist
        if hasattr(self.player_manager, 'set_sequencer_mode'):
            mode_active = playlist.sequencer.get('mode_active', False)
            self.player_manager.set_sequencer_mode(mode_active)
            logger.debug(f"Applied sequencer mode: {mode_active}")
        
        # Apply master/slave configuration for this playlist
        if hasattr(self.player_manager, 'set_master_playlist'):
            self.player_manager.set_master_playlist(playlist.master_player)
            logger.debug(f"Applied master/slave config: master={playlist.master_player}")
    
    def capture_active_playlist_state(self) -> None:
        """
        Capture current state from physical players and save to active playlist.
        Called before switching to a different playlist.
        """
        if not self.active_playlist_id or self.active_playlist_id not in self.playlists:
            return
        
        active_playlist = self.playlists[self.active_playlist_id]
        
        logger.info(f"[CAPTURE DEBUG] Capturing state for active playlist: {active_playlist.name} (id={self.active_playlist_id})")
        
        # Capture state from each player - only video and artnet, sequencer handled separately
        for player_id in ['video', 'artnet']:
            player = self.player_manager.get_player(player_id)
            if player:
                player_state = active_playlist.get_player_state(player_id)
                if player_state:
                    # Save player state to playlist
                    old_clips = player_state.clips.copy()
                    player_state.clips = list(player.playlist) if hasattr(player, 'playlist') and player.playlist else []
                    player_state.clip_ids = list(player.playlist_ids) if hasattr(player, 'playlist_ids') and player.playlist_ids else []
                    
                    logger.info(f"[CAPTURE DEBUG] {player_id} - Old clips: {old_clips}, New clips: {player_state.clips}")
                    
                    player_state.index = player.playlist_index if hasattr(player, 'playlist_index') else -1
                    player_state.autoplay = player.autoplay if hasattr(player, 'autoplay') else False
                    player_state.loop = player.loop_playlist if hasattr(player, 'loop_playlist') else False
                    player_state.is_playing = player.is_playing if hasattr(player, 'is_playing') else False
                    
                    if hasattr(player, 'playlist_params'):
                        player_state.clip_params = player.playlist_params.copy()
        
        # Capture sequencer timeline and mode
        if hasattr(self.player_manager, 'sequencer') and self.player_manager.sequencer:
            # Save timeline to playlist
            active_playlist.sequencer['timeline'] = self.player_manager.sequencer.timeline.to_dict()
            
            # Save sequencer mode
            if hasattr(self.player_manager, 'sequencer_mode_active'):
                active_playlist.sequencer['mode_active'] = self.player_manager.sequencer_mode_active
        
        logger.debug(f"Captured state from active playlist: {active_playlist.name}")
    
    # ========================================
    # SERIALIZATION
    # ========================================
    
    def serialize_all(self) -> dict:
        """Serialize all playlists to dictionary"""
        logger.info(f"[SERIALIZE DEBUG] Serializing {len(self.playlists)} playlists")
        for pid, pl in self.playlists.items():
            logger.info(f"[SERIALIZE DEBUG] Playlist: {pl.name} (id={pid}), video clips: {pl.players['video'].clips}")
        
        return {
            'active_playlist_id': self.active_playlist_id,
            'viewed_playlist_id': self.viewed_playlist_id,
            'items': {
                playlist_id: playlist.to_dict()
                for playlist_id, playlist in self.playlists.items()
            }
        }
    
    def load_from_dict(self, data: dict) -> bool:
        """Load all playlists from dictionary"""
        try:
            self.playlists.clear()
            
            # Restore all playlists from 'items' dict
            items_data = data.get('items', {})
            for playlist_id, playlist_data in items_data.items():
                playlist = Playlist.from_dict(playlist_data)
                self.playlists[playlist.id] = playlist
            
            # Fallback: support old 'playlists' array format for migration
            if not items_data and 'playlists' in data:
                logger.info("Migrating from old 'playlists' array format to new 'items' dict format")
                playlists_data = data.get('playlists', [])
                for playlist_data in playlists_data:
                    playlist = Playlist.from_dict(playlist_data)
                    self.playlists[playlist.id] = playlist
            
            # Restore active and viewed IDs
            self.active_playlist_id = data.get('active_playlist_id')
            self.viewed_playlist_id = data.get('viewed_playlist_id')
            
            # Apply active playlist to players
            if self.active_playlist_id and self.active_playlist_id in self.playlists:
                self.apply_playlist(self.active_playlist_id)
            
            logger.info(f"Loaded {len(self.playlists)} playlists from session state")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load playlists from dict: {e}", exc_info=True)
            return False
    
    # ========================================
    # AUTO-SAVE
    # ========================================
    
    def _auto_save(self):
        """Trigger auto-save of session state"""
        if self.session_state:
            try:
                # Import here to avoid circular dependency
                from .clip_registry import get_clip_registry
                clip_registry = get_clip_registry()
                
                self.session_state.save_async(
                    self.player_manager,
                    clip_registry,
                    force=True
                )
            except Exception as e:
                logger.warning(f"Auto-save failed: {e}")
