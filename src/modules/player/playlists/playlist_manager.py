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
from ...core.logger import get_logger

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
        self.transition_config: Dict = {     # Transition configuration
            'enabled': False,
            'effect': 'fade',
            'duration': 1.0,
            'easing': 'ease_in_out'
        }
    
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
            'global_effects': self.global_effects.copy(),
            'transition_config': self.transition_config.copy()
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
        state.transition_config = data.get('transition_config', {
            'enabled': False,
            'effect': 'fade',
            'duration': 1.0,
            'easing': 'ease_in_out'
        }).copy()
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
    
    def __init__(self, player_manager, session_state, websocket_manager, config=None):
        self.player_manager = player_manager
        self.session_state = session_state
        self.websocket_manager = websocket_manager
        self.config = config  # Store config for default effects
        
        self.playlists: Dict[str, Playlist] = {}  # {playlist_id: Playlist}
        self.active_playlist_id: Optional[str] = None   # Currently controlling playback
        self.viewed_playlist_id: Optional[str] = None   # Currently shown in GUI
        
        logger.info("Multi-Playlist System initialized")
    
    # ========================================
    # PLAYLIST CRUD
    # ========================================
    
    def create_playlist(self, name: str, playlist_type: str = 'standard') -> Playlist:
        """Create a new playlist with default effects applied"""
        playlist = Playlist(name, playlist_type)
        
        # Apply default effects from config to new playlist
        if self.config:
            effects_config = self.config.get('effects', {})
            logger.info(f"[CREATE DEBUG] Effects config: video={len(effects_config.get('video', []))}, artnet={len(effects_config.get('artnet', []))}")
            
            # Apply video default effects
            video_defaults = effects_config.get('video', [])
            if video_defaults:
                playlist.players['video'].global_effects = self._serialize_default_effects(video_defaults)
                logger.info(f"  ✅ Applied {len(video_defaults)} default effects to video player")
            
            # Apply artnet default effects
            artnet_defaults = effects_config.get('artnet', [])
            if artnet_defaults:
                playlist.players['artnet'].global_effects = self._serialize_default_effects(artnet_defaults)
                logger.info(f"  ✅ Applied {len(artnet_defaults)} default effects to artnet player")
        else:
            logger.warning(f"[CREATE DEBUG] No config available for default effects")
        
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
    
    def _serialize_default_effects(self, effects_config: List[Dict]) -> List[Dict]:
        """
        Serialize default effects from config format to storage format.
        Config format: [{'plugin_id': 'transform', 'params': {...}}, ...]
        Storage format: [{'index': 0, 'plugin_id': 'transform', 'parameters': {...}, ...}, ...]
        """
        serialized = []
        for idx, effect_cfg in enumerate(effects_config):
            plugin_id = effect_cfg.get('plugin_id')
            params = effect_cfg.get('params', {})
            
            # Create a minimal effect representation (will be fully initialized when applied)
            serialized.append({
                'index': idx,
                'plugin_id': plugin_id,
                'parameters': params.copy(),
                'enabled': True,
                'config': params.copy()
            })
        
        return serialized
    
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
                    
                    # Apply transition config to player
                    if hasattr(player, 'transition_config') and player_state.transition_config:
                        player.transition_config = player_state.transition_config.copy()
                    
                    # Apply clip parameters (includes per-clip effects)
                    if hasattr(player, 'playlist_params'):
                        player.playlist_params = player_state.clip_params.copy()
                        logger.info(f"[RESTORE DEBUG] {player_id} - Restored clip params for {len(player_state.clip_params)} clips")
                        for clip_id, params in player_state.clip_params.items():
                            if 'effects' in params:
                                logger.info(f"[RESTORE DEBUG] {player_id} - Clip {clip_id[:8]}... has {len(params['effects'])} effects")
                                # Log first effect's parameters for debugging
                                if params['effects']:
                                    first_effect = params['effects'][0]
                                    logger.info(f"[RESTORE DEBUG] {player_id} -   Effect: {first_effect.get('plugin_id', 'unknown')}")
                                    if 'parameters' in first_effect:
                                        for param_name, param_value in list(first_effect['parameters'].items())[:5]:
                                            logger.info(f"[RESTORE DEBUG] {player_id} -     {param_name} = {param_value}")
                            else:
                                logger.info(f"[RESTORE DEBUG] {player_id} - Clip {clip_id[:8]}... has no effects key in params")
                    
                    # Apply global effects to player
                    if hasattr(player, 'effect_processor') and player.effect_processor:
                        chain_type = 'artnet' if player_id == 'artnet' else 'video'
                        try:
                            # Clear existing chain
                            player.effect_processor.clear_chain(chain_type=chain_type)
                            logger.info(f"[RESTORE DEBUG] {player_id} - Cleared effect chain")
                            
                            # Restore effects from playlist
                            restored_count = 0
                            for idx, effect_data in enumerate(player_state.global_effects):
                                plugin_id = effect_data.get('plugin_id') or effect_data.get('id')
                                enabled = effect_data.get('enabled', True)  # Check if effect is enabled
                                
                                logger.info(f"[RESTORE DEBUG] {player_id} - Effect {idx}: plugin_id={plugin_id}, enabled={enabled}")
                                logger.info(f"[RESTORE DEBUG] {player_id} - Effect data keys: {list(effect_data.keys())}")
                                
                                # Skip disabled effects
                                if not enabled:
                                    logger.info(f"[RESTORE DEBUG] {player_id} - Skipping disabled effect '{plugin_id}'")
                                    continue
                                
                                config = effect_data.get('config', {})
                                
                                # Extract parameter values from parameters dict if present
                                if 'parameters' in effect_data:
                                    config = effect_data['parameters']
                                    logger.info(f"[RESTORE DEBUG] {player_id} - Using parameters: {list(config.keys())}")
                                    # Log actual parameter values for debugging
                                    for param_name, param_value in list(config.items())[:5]:  # Log first 5 params
                                        logger.info(f"[RESTORE DEBUG] {player_id} -   {param_name} = {param_value}")
                                
                                success, msg = player.add_effect_to_chain(plugin_id, config, chain_type=chain_type)
                                if success:
                                    restored_count += 1
                                    logger.info(f"[RESTORE DEBUG] {player_id} - ✅ Restored effect '{plugin_id}'")
                                else:
                                    logger.warning(f"[RESTORE DEBUG] {player_id} - ❌ Failed to restore effect '{plugin_id}': {msg}")
                            
                            logger.info(f"[RESTORE DEBUG] {player_id} - Restored {restored_count}/{len(player_state.global_effects)} enabled global effects")
                        except Exception as e:
                            logger.error(f"[RESTORE DEBUG] {player_id} - Error applying effects: {e}", exc_info=True)
                    
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
        
        # Capture state from each player - only video and artnet, sequencer handled separately
        for player_id in ['video', 'artnet']:
            player = self.player_manager.get_player(player_id)
            if player:
                player_state = active_playlist.get_player_state(player_id)
                if player_state:
                    # Save player state to playlist
                    player_state.clips = list(player.playlist) if hasattr(player, 'playlist') and player.playlist else []
                    player_state.clip_ids = list(player.playlist_ids) if hasattr(player, 'playlist_ids') and player.playlist_ids else []
                    player_state.index = player.playlist_index if hasattr(player, 'playlist_index') else -1
                    player_state.autoplay = player.autoplay if hasattr(player, 'autoplay') else False
                    player_state.loop = player.loop_playlist if hasattr(player, 'loop_playlist') else False
                    player_state.is_playing = player.is_playing if hasattr(player, 'is_playing') else False
                    
                    # Capture transition config from player
                    if hasattr(player, 'transition_config'):
                        player_state.transition_config = player.transition_config.copy()
                    
                    # Capture global effects from player
                    if hasattr(player, 'effect_processor'):
                        chain_type = 'artnet' if player_id == 'artnet' else 'video'
                        try:
                            player_state.global_effects = player.get_effect_chain(chain_type=chain_type)
                        except Exception as e:
                            logger.error(f"{player_id} - Error capturing effects: {e}")
                            player_state.global_effects = []
                    
                    # Extract per-clip effects from clip_registry (has CURRENT values, not stale)
                    from .clips.registry import get_clip_registry
                    clip_registry = get_clip_registry()
                    
                    if not clip_registry:
                        player_state.clip_params = {}
                    else:
                        player_state.clip_params = {}
                        
                        # Start with any generator parameters from playlist_params
                        if hasattr(player, 'playlist_params'):
                            for clip_id, params in player.playlist_params.items():
                                if 'parameters' in params:  # Generator parameters
                                    player_state.clip_params[clip_id] = {'parameters': params['parameters']}
                        
                        # Extract LIVE per-clip effects from active player layers
                        # This captures the ACTUAL running parameter values!
                        clip_count = 0
                        for clip_id in player_state.clip_ids:
                            # Find the active layer with this clip_id
                            active_layer = None
                            if hasattr(player, 'layers') and player.layers:
                                for layer in player.layers:
                                    if hasattr(layer, 'clip_id') and layer.clip_id == clip_id:
                                        active_layer = layer
                                        break
                            
                            if active_layer and hasattr(active_layer, 'effects') and active_layer.effects:
                                # Found the live layer - extract LIVE parameters from effect instances
                                if clip_id not in player_state.clip_params:
                                    player_state.clip_params[clip_id] = {}
                                
                                effects_list = []
                                for effect_config in active_layer.effects:
                                    live_instance = effect_config.get('instance')
                                    plugin_id = effect_config.get('id')
                                    
                                    if live_instance and hasattr(live_instance, 'get_parameters'):
                                        # Get LIVE parameter values
                                        live_params = live_instance.get_parameters()
                                        
                                        # Get metadata from registry
                                        registry_effect = None
                                        if clip_id in clip_registry.clips:
                                            for reg_eff in clip_registry.clips[clip_id].get('effects', []):
                                                if reg_eff.get('plugin_id') == plugin_id:
                                                    registry_effect = reg_eff
                                                    break
                                        
                                        # Build effect dict with LIVE parameters
                                        effect_dict = {
                                            'plugin_id': plugin_id,
                                            'parameters': live_params  # LIVE VALUES
                                        }
                                        
                                        # Copy metadata if available
                                        if registry_effect and 'metadata' in registry_effect:
                                            effect_dict['metadata'] = registry_effect['metadata']
                                        
                                        effects_list.append(effect_dict)
                                
                                player_state.clip_params[clip_id]['effects'] = effects_list
                                clip_count += 1
                            else:
                                # No active layer found - fallback to registry
                                if clip_id in clip_registry.clips:
                                    clip_data = clip_registry.clips[clip_id]
                                    if 'effects' in clip_data and clip_data['effects']:
                                        if clip_id not in player_state.clip_params:
                                            player_state.clip_params[clip_id] = {}
                                        player_state.clip_params[clip_id]['effects'] = clip_data['effects']
                                        clip_count += 1
                        
                        if clip_count > 0:
                            logger.info(f"Captured live state: {player_id} player ({clip_count} clips)")
        
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
        # Serialize all playlists
        
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
            
            # CRITICAL FIX: Re-populate clip_params from clip_registry
            # Saved files may have empty clip_params, but clip_registry has the effects
            try:
                from .clips.registry import get_clip_registry
                clip_registry = get_clip_registry()
                
                if not clip_registry:
                    logger.warning("⚠️ clip_registry not available, cannot re-populate clip_params")
                else:
                    config = self.player_manager.audio_analyzer.config if hasattr(self.player_manager, 'audio_analyzer') else {}
                    video_dir = config.get('paths', {}).get('video_dir', 'video')
                    
                    for playlist in self.playlists.values():
                        for player_id, player_state in playlist.players.items():
                            # Register all clips and extract effects
                            for idx, clip_path in enumerate(player_state.clips):
                                clip_id = player_state.clip_ids[idx] if idx < len(player_state.clip_ids) else None
                                
                                if not clip_id:
                                    continue
                                
                                # Register clip if not already in registry
                                if clip_id not in clip_registry.clips:
                                    try:
                                        # Determine relative path
                                        if clip_path.startswith('generator:'):
                                            relative_path = clip_path
                                            metadata = {'type': 'generator', 'generator_id': clip_path.replace('generator:', '')}
                                        else:
                                            try:
                                                import os
                                                relative_path = os.path.relpath(clip_path, video_dir)
                                            except:
                                                relative_path = clip_path
                                            metadata = {'type': 'video'}
                                        
                                        # Register with known clip_id
                                        registered_id = clip_registry.register_clip(
                                            player_id,
                                            clip_path,
                                            relative_path,
                                            metadata
                                        )
                                        
                                        # Ensure registry uses our clip_id
                                        if registered_id != clip_id:
                                            clip_registry.clips[clip_id] = clip_registry.clips[registered_id]
                                            clip_registry.clips[clip_id]['clip_id'] = clip_id
                                            del clip_registry.clips[registered_id]
                                        
                                        pass  # Clip registered
                                    except Exception as e:
                                        logger.warning(f"Failed to register clip: {e}")
                                
                                # Now extract effects from registry
                                if clip_id in clip_registry.clips:
                                    clip_data = clip_registry.clips[clip_id]
                                    if 'effects' in clip_data and clip_data['effects']:
                                        if clip_id not in player_state.clip_params:
                                            player_state.clip_params[clip_id] = {}
                                        player_state.clip_params[clip_id]['effects'] = clip_data['effects']
                                        pass  # Effects extracted from registry
                    
                    logger.info(f"✅ Re-populated clip_params from clip_registry for {len(self.playlists)} playlists")
            except Exception as e:
                logger.warning(f"⚠️ Failed to re-populate clip_params from registry: {e}", exc_info=True)
            
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
                from .clips.registry import get_clip_registry
                clip_registry = get_clip_registry()
                
                self.session_state.save_async(
                    self.player_manager,
                    clip_registry,
                    force=True
                )
            except Exception as e:
                logger.warning(f"Auto-save failed: {e}")
