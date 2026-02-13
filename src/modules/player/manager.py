"""
Player Manager - Central player container (Single Source of Truth)
"""
import time
from ..core.logger import get_logger, debug_playback

logger = get_logger(__name__)


class PlayerManager:
    """
    Central container for dual-player management.
    
    Manages two independent players:
    - Video Player: For video preview display (no Art-Net output)
    - Art-Net Player: For Art-Net output (no video preview)
    
    Each player has:
    - Own frame source
    - Own playlist
    - Own effect chain
    - Independent playback state
    
    UNIFIED ACCESS: Use get_player(player_id) for consistent access
    """
    
    def __init__(self, player=None, artnet_player=None, socketio=None):
        """
        Initialize PlayerManager with dual players.
        
        Args:
            player: Video player instance (preview)
            artnet_player: Art-Net player instance (output)
            socketio: SocketIO instance for WebSocket events (optional)
        """
        # Main player reference
        self._player = player
        
        # OUTPUT PLAYERS (Active Playlist - control physical output)
        self.video_player = player  # Player for video preview (no Art-Net)
        self.artnet_player = artnet_player  # Player for Art-Net output (no preview)
        
        # PREVIEW PLAYERS (Viewed Playlist - UI only, no output)
        # Lazy-initialized when viewing non-active playlist
        self.video_preview_player = None
        self.artnet_preview_player = None
        self._preview_players_created = False
        self._preview_last_used = 0  # Timestamp for cleanup
        
        # TAKEOVER PREVIEW MODE
        # Pauses active playlist and plays preview on main output players
        self._takeover_mode_active = False
        self._takeover_saved_state = {}  # Stores active playlist state
        
        # Unified player registry with IDs
        self.players = {
            'video': self.video_player,
            'artnet': self.artnet_player,
            'video_preview': None,  # Will be set when created
            'artnet_preview': None  # Will be set when created
        }
        
        # Master/Slave Synchronization
        self.master_playlist = None  # 'video' or 'artnet' or None
        
        # Sequencer (audio-driven master control)
        self.sequencer = None  # AudioSequencer instance
        self.sequencer_mode_active = False  # Sequencer mode: ON = sequencer is MASTER, OFF = normal
        
        # WebSocket support
        self.socketio = socketio
        
        # Initialize slave cache for all players
        self._update_all_slave_caches()
        
        logger.debug(f"PlayerManager initialized (video_player: {player is not None}, artnet_player: {artnet_player is not None})")
    
    @property
    def player(self):
        """Get main player instance (shortcut to video_player)."""
        return self._player or self.video_player
    
    @player.setter
    def player(self, new_player):
        """Set main player instance (updates video_player)."""
        old_player = self._player
        self._player = new_player
        self.video_player = new_player
        
        if old_player and old_player != new_player:
            logger.debug(f"Player switched: {type(old_player).__name__} → {type(new_player).__name__}")
        elif new_player:
            logger.debug(f"Player set: {type(new_player).__name__}")
    
    def set_player(self, new_player):
        """
        Set new player instance (explicit method for clarity).
        
        Args:
            new_player: New player instance
        """
        self.player = new_player
        
        # Update slave cache for new player
        if new_player:
            self._update_all_slave_caches()
    
    def get_player(self):
        """
        Get current player instance (explicit method for clarity).
        
        Returns:
            Player instance or None
        """
        return self._player
    
    def has_player(self):
        """
        Check if player is set.
        
        Returns:
            bool: True if player exists
        """
        return self._player is not None
    
    # Dual-Player Methods
    def set_artnet_player(self, new_player):
        """Set Art-Net player instance."""
        old_player = self.artnet_player
        self.artnet_player = new_player
        self.players['artnet'] = new_player
        
        # Update slave cache for new player
        if new_player:
            self._update_all_slave_caches()
        
        if old_player and old_player != new_player:
            logger.debug(f"Art-Net player switched: {type(old_player).__name__} → {type(new_player).__name__}")
        elif new_player:
            logger.debug(f"Art-Net player set: {type(new_player).__name__}")
    
    def get_video_player(self):
        """Get video player instance."""
        return self.video_player
    
    def get_artnet_player(self):
        """Get Art-Net player instance."""
        return self.artnet_player
    
    # UNIFIED ACCESS METHOD
    def get_player(self, player_id: str):
        """
        Get player by ID (unified access method).
        
        Args:
            player_id: Player identifier ('video', 'artnet', 'video_preview', 'artnet_preview')
        
        Returns:
            Player instance or None if not found
        """
        if player_id not in self.players:
            logger.warning(f"Invalid player_id: {player_id}. Valid IDs: {list(self.players.keys())}")
            return None
        
        player = self.players.get(player_id)
        if player is None:
            logger.warning(f"Player '{player_id}' is not initialized")
        
        return player
    
    def get_all_player_ids(self):
        """
        Get list of all available player IDs.
        
        Returns:
            List of player IDs
        """
        return list(self.players.keys())
    
    def has_artnet_player(self):
        """Check if Art-Net player is set."""
        return self.artnet_player is not None
    
    # Preview Player Management (Dual-Player Architecture)
    def create_preview_players(self):
        """
        Create preview player instances on-demand.
        Preview players run viewed (non-active) playlists without affecting output.
        
        Returns:
            bool: True if created or already exist, False on error
        """
        if self._preview_players_created:
            # Update last used timestamp
            self._preview_last_used = time.time()
            return True
        
        try:
            from .player_core import Player
            from .sources import VideoSource
            
            # Create video preview player (clone video player config)
            if self.video_player:
                logger.info("Creating video preview player...")
                
                # Clone config but disable display output for preview
                preview_config = self.video_player.config.copy() if self.video_player.config else {}
                if 'outputs' in preview_config and 'definitions' in preview_config['outputs']:
                    # Filter out display outputs from definitions
                    preview_config['outputs'] = preview_config['outputs'].copy()
                    preview_config['outputs']['definitions'] = [
                        output for output in preview_config['outputs']['definitions']
                        if output.get('type') != 'display'
                    ]
                    # Also update routing to exclude display outputs
                    if 'default_routing' in preview_config['outputs']:
                        preview_config['outputs']['default_routing'] = {
                            k: [v for v in route_list if not any(
                                d.get('id') == v and d.get('type') == 'display'
                                for d in preview_config.get('outputs', {}).get('definitions', [])
                            )]
                            for k, route_list in preview_config['outputs']['default_routing'].items()
                        }
                
                self.video_preview_player = Player(
                    frame_source=VideoSource(
                        video_path=None,
                        canvas_width=self.video_player.canvas_width,
                        canvas_height=self.video_player.canvas_height,
                        config=preview_config
                    ),
                    points_json_path=self.video_player.points_json_path,
                    target_ip=self.video_player.target_ip,
                    start_universe=self.video_player.start_universe,
                    fps_limit=15,  # Lower FPS for preview (optimization)
                    config=preview_config,
                    enable_artnet=False,  # NO OUTPUT - preview only
                    player_name="VideoPreview",
                    clip_registry=self.video_player.clip_registry
                )
                self.players['video_preview'] = self.video_preview_player
                logger.info("✅ Video preview player created (display output disabled)")
            
            # Create artnet preview player (clone artnet player config)
            if self.artnet_player:
                logger.info("Creating Art-Net preview player...")
                
                # Clone config but disable display output for preview
                preview_config = self.artnet_player.config.copy() if self.artnet_player.config else {}
                if 'outputs' in preview_config and 'definitions' in preview_config['outputs']:
                    # Filter out display outputs from definitions
                    preview_config['outputs'] = preview_config['outputs'].copy()
                    preview_config['outputs']['definitions'] = [
                        output for output in preview_config['outputs']['definitions']
                        if output.get('type') != 'display'
                    ]
                    # Also update routing to exclude display outputs
                    if 'default_routing' in preview_config['outputs']:
                        preview_config['outputs']['default_routing'] = {
                            k: [v for v in route_list if not any(
                                d.get('id') == v and d.get('type') == 'display'
                                for d in preview_config.get('outputs', {}).get('definitions', [])
                            )]
                            for k, route_list in preview_config['outputs']['default_routing'].items()
                        }
                
                self.artnet_preview_player = Player(
                    frame_source=VideoSource(
                        video_path=None,
                        canvas_width=self.artnet_player.canvas_width,
                        canvas_height=self.artnet_player.canvas_height,
                        config=preview_config
                    ),
                    points_json_path=self.artnet_player.points_json_path,
                    target_ip=self.artnet_player.target_ip,
                    start_universe=self.artnet_player.start_universe,
                    fps_limit=15,  # Lower FPS for preview (optimization)
                    config=preview_config,
                    enable_artnet=False,  # NO OUTPUT - preview only
                    player_name="ArtNetPreview",
                    clip_registry=self.artnet_player.clip_registry
                )
                self.players['artnet_preview'] = self.artnet_preview_player
                logger.info("✅ Art-Net preview player created (display output disabled)")
            
            self._preview_players_created = True
            self._preview_last_used = time.time()
            logger.info("🎭 Preview players initialized (isolated from output)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create preview players: {e}", exc_info=True)
            return False
    
    def destroy_preview_players(self):
        """
        Clean up preview players to free resources.
        Called when switching back to active playlist or after timeout.
        """
        if not self._preview_players_created:
            return
        
        try:
            if self.video_preview_player:
                logger.info("Destroying video preview player...")
                if self.video_preview_player.is_running:
                    self.video_preview_player.stop()
                self.video_preview_player = None
                self.players['video_preview'] = None
            
            if self.artnet_preview_player:
                logger.info("Destroying Art-Net preview player...")
                if self.artnet_preview_player.is_running:
                    self.artnet_preview_player.stop()
                self.artnet_preview_player = None
                self.players['artnet_preview'] = None
            
            self._preview_players_created = False
            logger.info("🗑️ Preview players destroyed")
            
        except Exception as e:
            logger.error(f"Error destroying preview players: {e}", exc_info=True)
    
    def has_preview_players(self):
        """Check if preview players are created."""
        return self._preview_players_created
    
    def get_preview_player(self, player_id: str):
        """
        Get preview player by ID.
        
        Args:
            player_id: 'video' or 'artnet' (automatically adds '_preview' suffix)
        
        Returns:
            Preview player instance or None
        """
        preview_id = f"{player_id}_preview"
        return self.players.get(preview_id)
    
    def check_preview_timeout(self, timeout_seconds: int = 300):
        """
        Check if preview players should be destroyed due to inactivity.
        
        Args:
            timeout_seconds: Timeout in seconds (default: 5 minutes)
        
        Returns:
            bool: True if players were destroyed
        """
        if not self._preview_players_created:
            return False
        
        inactive_time = time.time() - self._preview_last_used
        if inactive_time > timeout_seconds:
            logger.info(f"Preview players inactive for {inactive_time:.0f}s - destroying")
            self.destroy_preview_players()
            return True
        
        return False
    
    # Takeover Preview Mode (Pause active playlist, use output players for preview)
    def start_takeover_preview(self, playlist_id: str, player_id: str = None):
        """
        Start takeover preview mode: Pause active playlist and load preview playlist into output players.
        This lets you preview on the actual output (Art-Net) without running separate players.
        
        Args:
            playlist_id: ID of playlist to preview
            player_id: Specific player to takeover ('video' or 'artnet'), or None for both
        
        Returns:
            dict: Status with success, saved state info
        """
        if self._takeover_mode_active:
            return {
                "success": False,
                "error": "Takeover preview already active",
                "mode": "takeover_active"
            }
        
        try:
            # Stop any isolated preview players first (they conflict with takeover mode)
            if self._preview_players_created:
                logger.info("🛑 Stopping isolated preview players for takeover mode")
                self.destroy_preview_players()
            
            from .api_playlists import get_playlist_system
            playlist_system = get_playlist_system()
            
            if not playlist_system:
                return {"success": False, "error": "Playlist system not available"}
            
            # Get active and preview playlists
            active_playlist = playlist_system.get_active_playlist()
            preview_playlist = playlist_system.get_playlist(playlist_id)
            
            if not active_playlist:
                return {"success": False, "error": "No active playlist"}
            
            if not preview_playlist:
                return {"success": False, "error": f"Preview playlist {playlist_id} not found"}
            
            # Determine which players to takeover
            players_to_takeover = []
            if player_id:
                players_to_takeover = [player_id]
            else:
                players_to_takeover = ['video', 'artnet']
            
            # Save current state for each player
            self._takeover_saved_state = {
                'active_playlist_id': active_playlist.id,
                'preview_playlist_id': playlist_id,
                'players': {}
            }
            
            for pid in players_to_takeover:
                player = self.get_player(pid)
                if not player:
                    continue
                
                # Save current player state
                self._takeover_saved_state['players'][pid] = {
                    'is_playing': player.is_playing,
                    'is_paused': player.is_paused,
                    'current_clip_index': player.current_clip_index,
                    'playlist': player.playlist.copy() if hasattr(player, 'playlist') and player.playlist else [],
                    'playlist_ids': player.playlist_ids.copy() if hasattr(player, 'playlist_ids') and player.playlist_ids else [],
                    'autoplay': player.autoplay if hasattr(player, 'autoplay') else False,
                    'loop_playlist': player.loop_playlist if hasattr(player, 'loop_playlist') else False,
                    'current_position': player.source.get_current_frame() if hasattr(player, 'source') and hasattr(player.source, 'get_current_frame') else 0
                }
                
                # Pause active playback
                if player.is_playing:
                    player.pause()
                    logger.info(f"⏸️ Paused {pid} player for takeover preview")
            
            self._takeover_mode_active = True
            logger.info(f"🎬 Takeover preview mode activated: {preview_playlist.name}")
            
            return {
                "success": True,
                "mode": "takeover_started",
                "active_playlist": active_playlist.name,
                "preview_playlist": preview_playlist.name,
                "players_paused": players_to_takeover,
                "saved_state": True
            }
            
        except Exception as e:
            logger.error(f"Failed to start takeover preview: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def stop_takeover_preview(self):
        """
        Stop takeover preview mode and restore active playlist state.
        
        Returns:
            dict: Status with success, restored state info
        """
        if not self._takeover_mode_active:
            return {
                "success": False,
                "error": "No takeover preview active",
                "mode": "not_active"
            }
        
        try:
            from .api_playlists import get_playlist_system
            playlist_system = get_playlist_system()
            
            if not playlist_system:
                return {"success": False, "error": "Playlist system not available"}
            
            # Get active playlist
            active_playlist_id = self._takeover_saved_state.get('active_playlist_id')
            active_playlist = playlist_system.get_playlist(active_playlist_id)
            
            if not active_playlist:
                logger.warning(f"Active playlist {active_playlist_id} not found, cannot restore")
                self._takeover_mode_active = False
                self._takeover_saved_state = {}
                return {"success": False, "error": "Active playlist not found"}
            
            # Restore each player
            restored_players = []
            for pid, saved_state in self._takeover_saved_state.get('players', {}).items():
                player = self.get_player(pid)
                if not player:
                    continue
                
                # Stop current playback
                if player.is_playing:
                    player.stop()
                
                # Restore playlist
                player.playlist = saved_state['playlist']
                player.playlist_ids = saved_state['playlist_ids']
                player.autoplay = saved_state['autoplay']
                player.loop_playlist = saved_state['loop_playlist']
                
                # Restore clip position
                if saved_state['current_clip_index'] >= 0 and saved_state['current_clip_index'] < len(player.playlist):
                    player.load_clip_by_index(saved_state['current_clip_index'], notify_manager=False)
                
                # Restore playback state
                if saved_state['is_playing'] and not saved_state['is_paused']:
                    player.play()
                    logger.info(f"▶️ Resumed {pid} player after takeover preview")
                elif saved_state['is_paused']:
                    player.pause()
                    logger.info(f"⏸️ Restored paused state for {pid} player")
                
                restored_players.append(pid)
            
            self._takeover_mode_active = False
            prev_playlist_name = self._takeover_saved_state.get('preview_playlist_id', 'unknown')
            self._takeover_saved_state = {}
            
            logger.info(f"🎬 Takeover preview mode stopped, active playlist restored")
            
            return {
                "success": True,
                "mode": "takeover_stopped",
                "active_playlist": active_playlist.name,
                "players_restored": restored_players
            }
            
        except Exception as e:
            logger.error(f"Failed to stop takeover preview: {e}", exc_info=True)
            self._takeover_mode_active = False
            self._takeover_saved_state = {}
            return {"success": False, "error": str(e)}
    
    def is_takeover_preview_active(self):
        """Check if takeover preview mode is active."""
        return self._takeover_mode_active
    
    def get_takeover_preview_state(self):
        """Get current takeover preview state info."""
        if not self._takeover_mode_active:
            return None
        return {
            "active": True,
            "active_playlist_id": self._takeover_saved_state.get('active_playlist_id'),
            "preview_playlist_id": self._takeover_saved_state.get('preview_playlist_id'),
            "players_taken": list(self._takeover_saved_state.get('players', {}).keys())
        }
    
    # Master/Slave Synchronization Methods
    
    def set_master_playlist(self, player_id: str = None) -> bool:
        """
        Sets a playlist as Master, all others become Slaves.
        
        Args:
            player_id: 'video' or 'artnet' or None (deactivates Master mode)
        
        Returns:
            True if successful, False if invalid player_id
        """
        if player_id not in ['video', 'artnet', None]:
            logger.warning(f"Invalid player_id for master: {player_id}")
            return False
        
        old_master = self.master_playlist
        self.master_playlist = player_id
        
        # Update all players' slave cache when master changes
        self._update_all_slave_caches()
        
        # DEBUG: Log stack trace to find who's calling this
        import traceback
        logger.info(f"👑 Master playlist: {old_master} → {player_id}")
        if old_master != player_id:  # Only log stack on actual change
            logger.info(f"📞 set_master_playlist called from:\n{''.join(traceback.format_stack()[:-1])}")
        
        # Emit WebSocket event for master/slave state change
        if self.socketio and old_master != player_id:
            try:
                self.socketio.emit('master_slave_changed', {
                    'master_playlist': player_id,
                    'timestamp': time.time()
                }, namespace='/player')
                logger.info(f"📡 WebSocket: master_slave_changed emitted (master={player_id})")
            except Exception as e:
                logger.error(f"❌ Error emitting master_slave_changed WebSocket event: {e}")
        
        # Initial Sync: When Master is activated, ALL playlists jump to index 0 and start from frame 0
        if player_id is not None:
            # Reset ALL players to index 0, frame 0 (master AND slaves)
            for pid in self.get_all_player_ids():
                player = self.get_player(pid)
                if player and len(player.playlist) > 0:
                    was_playing = player.is_playing
                    logger.info(f"Master mode activated - resetting {pid} to index 0, frame 0 (was at index {player.current_clip_index})")
                    
                    # Force to index 0 (notify_manager=False to avoid triggering sync events)
                    player.load_clip_by_index(0, notify_manager=False)
                    
                    # Explicitly reset source to frame 0 (ensure clean start)
                    if hasattr(player, 'source') and player.source:
                        player.source.reset()
                        player.source.current_frame = 0
                    
                    # Restart playback if it was playing
                    if was_playing and not player.is_playing:
                        player.start()
                    
                    logger.debug(f"✅ {pid} reset to clip 0, frame 0, playing={player.is_playing}")
        
        return True
    
    def get_master_playlist(self) -> str:
        """
        Get current master playlist ID.
        
        Returns:
            'video', 'artnet', or None
        """
        return self.master_playlist
    
    def is_master(self, player_id: str) -> bool:
        """
        Check if player is currently master.
        
        Args:
            player_id: Player identifier
        
        Returns:
            True if player is master
        """
        return self.master_playlist == player_id
    
    def sync_slaves_to_master(self):
        """
        Synchronizes all Slave playlists to Master clip index.
        Called when Master is activated or Master changes clip.
        """
        if not self.master_playlist:
            logger.debug("No master playlist set, skipping sync")
            return
        
        master_player = self.get_player(self.master_playlist)
        if not master_player:
            logger.warning(f"Master player '{self.master_playlist}' not found")
            return
        
        master_clip_index = master_player.get_current_clip_index()
        
        logger.debug(f"🔄 Syncing slaves to master index {master_clip_index}")
        
        # Synchronize all Slaves
        for player_id in self.get_all_player_ids():
            if player_id == self.master_playlist:
                continue
            
            slave_player = self.get_player(player_id)
            if slave_player:
                self._sync_slave_to_index(slave_player, master_clip_index)
    
    def _sync_slave_to_index(self, slave_player, clip_index: int):
        """
        Synchronizes single Slave to clip index.
        
        Edge-Cases:
        - Slave has fewer clips than index → Slave is stopped (black screen)
        - Clip-index invalid → No action
        - Slave has empty playlist → No action
        
        Args:
            slave_player: Slave player instance
            clip_index: Target clip index
        """
        playlist = slave_player.playlist
        if not playlist or len(playlist) == 0:
            logger.debug(f"Slave {slave_player.player_name} has empty playlist, skipping sync")
            return
        
        # If Slave doesn't have enough clips → Stop playback and show black screen
        if clip_index >= len(playlist):
            slave_player.stop()
            
            # Create black frame
            import numpy as np
            black_frame_rgb = np.zeros((slave_player.canvas_height, slave_player.canvas_width, 3), dtype=np.uint8)
            
            # Clear Art-Net output via routing_bridge (if enabled)
            if hasattr(slave_player, 'routing_bridge') and slave_player.routing_bridge and slave_player.enable_artnet:
                try:
                    slave_player.routing_bridge.process_frame(black_frame_rgb)
                except Exception as e:
                    logger.error(f"Failed to send black frame via routing_bridge: {e}")
            
            # Clear preview frame (expects BGR for MJPEG stream)
            import cv2
            black_frame_bgr = cv2.cvtColor(black_frame_rgb, cv2.COLOR_RGB2BGR)
            slave_player.last_video_frame = black_frame_bgr
            slave_player.last_frame = None
            
            # Mark as auto-stopped so it can be restarted when master returns to valid range
            slave_player._auto_stopped_by_master = True
            logger.info(f"⏹️ Slave {slave_player.player_name} stopped (index {clip_index} out of range, has {len(playlist)} clips) - black screen")
            return
        
        # Check if slave was previously auto-stopped by master (out of range)
        was_auto_stopped = getattr(slave_player, '_auto_stopped_by_master', False)
        
        # Load clip at index (this will restart playback if player was playing)
        success = slave_player.load_clip_by_index(clip_index, notify_manager=False)
        
        if success:
            # If slave was auto-stopped and now has valid clip, restart playback
            if was_auto_stopped and not slave_player.is_playing:
                logger.info(f"🔄 Slave {slave_player.player_name} was auto-stopped, restarting playback at index {clip_index}")
                slave_player.start()
                slave_player._auto_stopped_by_master = False  # Clear flag
            
            logger.debug(f"🔄 Slave {slave_player.player_name} synced to index {clip_index}")
            
            # Emit WebSocket event for slave clip change (for active border update)
            if self.socketio:
                try:
                    self.socketio.emit('playlist.changed', {
                        'player_id': slave_player.player_id,
                        'current_index': clip_index
                    }, namespace='/player')
                except Exception as e:
                    logger.error(f"❌ Error emitting slave playlist.changed WebSocket event: {e}")
        else:
            logger.warning(f"Failed to sync slave {slave_player.player_name} to index {clip_index}")
    
    def on_clip_changed(self, player_id: str, clip_index: int):
        """
        Event-Handler: Called when clip changes in any player.
        If player is Master → Synchronize all Slaves.
        
        Args:
            player_id: ID of player that changed clip
            clip_index: New clip index
        """
        # In sequencer mode, ignore normal master/slave sync (sequencer controls everything)
        if self.sequencer_mode_active:
            logger.debug(f"⏭️ Ignoring on_clip_changed in sequencer mode (player={player_id}, index={clip_index})")
            return
        
        # Emit WebSocket event for playlist change
        if self.socketio:
            try:
                self.socketio.emit('playlist.changed', {
                    'player_id': player_id,
                    'current_index': clip_index
                }, namespace='/player')
                logger.debug(f"📡 WebSocket: playlist.changed emitted for {player_id} index={clip_index}")
            except Exception as e:
                logger.error(f"❌ Error emitting playlist.changed WebSocket event: {e}")
        
        if player_id != self.master_playlist:
            return  # Not Master, no sync action
        
        logger.debug(f"👑 Master {player_id} clip changed to index {clip_index}")
        
        # Synchronize all Slaves
        for slave_id in self.get_all_player_ids():
            if slave_id == self.master_playlist:
                continue
            
            slave_player = self.get_player(slave_id)
            if slave_player:
                self._sync_slave_to_index(slave_player, clip_index)
    
    # ========== SEQUENCER INTEGRATION ==========
    
    def init_sequencer(self):
        """Initialize audio sequencer (called during startup)"""
        try:
            from .audio_sequencer import AudioSequencer
            self.sequencer = AudioSequencer(player_manager=self)
            
            # Set up callbacks for UI updates
            self.sequencer.on_slot_change = self._on_sequencer_slot_change
            self.sequencer.on_position_update = self._on_sequencer_position_update
            
            logger.info("🎵 AudioSequencer initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize sequencer: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def set_sequencer_mode(self, enabled: bool):
        """Enable/disable sequencer mode
        
        When enabled:
        - Sequencer becomes MASTER timeline controller
        - All playlists become SLAVES following slot boundaries
        - Master/slave via Transport is disabled
        
        When disabled:
        - Normal Master/Slave operation via Transport
        - Sequencer is inactive
        
        Args:
            enabled: True to enable sequencer mode, False to disable
        """
        self.sequencer_mode_active = enabled
        
        # Update all players' slave cache when sequencer mode changes
        self._update_all_slave_caches()
        
        if enabled:
            # Clear master playlist - sequencer controls all
            old_master = self.master_playlist
            self.master_playlist = None
            logger.info(f"🎵 SEQUENCER MODE ON: Sequencer is MASTER, all playlists are SLAVES (previous master: {old_master})")
        else:
            logger.info("🎵 SEQUENCER MODE OFF: Normal master/slave operation")
            # Note: master_playlist will be set by user via transport position controls
        
        # Broadcast mode change via WebSocket
        if self.socketio:
            try:
                self.socketio.emit('sequencer_mode_changed', {
                    'enabled': enabled,
                    'master_playlist': self.master_playlist
                }, namespace='/player')
            except Exception as e:
                logger.error(f"❌ Error emitting sequencer_mode_changed: {e}")
    
    def sequencer_advance_slaves(self, slot_index: int, force_reload: bool = False):
        """Advance all players to the clip matching the sequencer slot.
        
        Called when sequencer slot boundary is crossed.
        Sequencer is MASTER, all playlists are SLAVES.
        Slot index maps directly to clip index (slot 0 → clip 0, slot 1 → clip 1, etc.)
        
        Args:
            slot_index: Current slot index (0, 1, 2, ...) - maps to clip index
            force_reload: If True, reload clips even if already at correct index
        """
        logger.debug(f"🎯 Sequencer slot {slot_index}: Loading clip index in all playlists")
        
        if not self.sequencer_mode_active:
            logger.warning("⚠️ Sequencer mode not active, skipping slave advance")
            return
        
        # Load clip at slot_index in ALL playlists (they are all slaves to sequencer)
        for player_id, player in self.players.items():
            if player and player.playlist_manager.playlist and len(player.playlist_manager.playlist) > 0:
                playlist_length = len(player.playlist_manager.playlist)
                
                # Check if slot index exceeds playlist length → stop player and show black screen
                if slot_index >= playlist_length:
                    player.stop()
                    
                    # Create black frame
                    import numpy as np
                    black_frame_rgb = np.zeros((player.canvas_height, player.canvas_width, 3), dtype=np.uint8)
                    
                    # Clear Art-Net output via routing_bridge (if enabled)
                    if hasattr(player, 'routing_bridge') and player.routing_bridge and player.enable_artnet:
                        try:
                            player.routing_bridge.process_frame(black_frame_rgb)
                        except Exception as e:
                            logger.error(f"Failed to send black frame via routing_bridge: {e}")
                    
                    # Clear preview frame
                    import cv2
                    black_frame_bgr = cv2.cvtColor(black_frame_rgb, cv2.COLOR_RGB2BGR)
                    player.last_video_frame = black_frame_bgr
                    player.last_frame = None
                    
                    logger.info(f"⏹️ Sequencer slot {slot_index}: {player_id} stopped (only has {playlist_length} clips) - black screen")
                    continue
                
                current_index = getattr(player, 'current_clip_index', -1)
                target_index = slot_index
                
                if target_index != current_index or force_reload:
                    logger.info(f"🔄 Sequencer: Loading {player_id} clip {target_index}")
                    
                    # Load clip at target index
                    success = player.load_clip_by_index(target_index, notify_manager=False)
                    
                    if not success:
                        logger.warning(f"❌ Failed to load {player_id} clip {target_index}")
                        continue
                    
                    # Emit playlist.changed for frontend UI update
                    if self.socketio:
                        self.socketio.emit('playlist.changed', {
                            'player_id': player_id,
                            'current_index': target_index
                        }, namespace='/player')
                    
                    if not player.is_playing:
                        player.start()
                else:
                    # Still emit playlist.changed even when skipping reload
                    if self.socketio:
                        self.socketio.emit('playlist.changed', {
                            'player_id': player_id,
                            'current_index': target_index
                        }, namespace='/player')
        
        # Broadcast to frontend via WebSocket
        if self.socketio:
            try:
                self.socketio.emit('sequencer_slot_advance', {
                    'slot_index': slot_index,
                    'timestamp': time.time()
                }, namespace='/player')
            except Exception as e:
                logger.error(f"❌ Error emitting sequencer_slot_advance: {e}")
    
    def _on_sequencer_slot_change(self, slot_index: int):
        """Callback: Sequencer slot changed
        
        Args:
            slot_index: New slot index
        """
        logger.debug(f"🎵 Sequencer slot change callback: slot {slot_index}")
        # Additional logic can be added here if needed
    
    def _update_all_slave_caches(self):
        """Update slave detection cache in all players when state changes"""
        for player_id, player in self.players.items():
            if player:
                is_slave = (self.sequencer_mode_active or
                           (self.master_playlist is not None and 
                            not self.is_master(player_id)))
                player._is_slave_cached = is_slave
                logger.debug(f"Updated slave cache for {player_id}: {is_slave}")
            else:
                logger.debug(f"Skipping slave cache update for {player_id}: player is None")
    
    def _on_sequencer_position_update(self, position: float, slot_index: int):
        """Callback: Sequencer position updated (100ms updates)
        
        Throttled to ~5/sec for WebSocket performance.
        
        Args:
            position: Current position in seconds
            slot_index: Current slot index or None
        """
        # Throttle WebSocket updates to 200ms (5/sec) for performance
        if not hasattr(self, '_last_position_update'):
            self._last_position_update = 0
        
        current_time = time.time()
        if current_time - self._last_position_update < 0.2:  # 200ms throttle
            return
        
        self._last_position_update = current_time
        
        # Broadcast position update via WebSocket
        if self.socketio:
            try:
                self.socketio.emit('sequencer_position', {
                    'position': position,
                    'slot_index': slot_index
                }, namespace='/player')
            except Exception as e:
                # Don't spam logs on WebSocket errors
                pass
    
    def update_sequences(self, dt: float):
        """
        Update all dynamic parameter sequences
        
        Should be called from the render loop with delta time.
        
        Args:
            dt: Delta time in seconds since last update
        """
        if hasattr(self, 'sequence_manager') and self.sequence_manager:
            try:
                self.sequence_manager.update_all(dt, self)
            except Exception as e:
                logger.error(f"Error updating sequences: {e}", exc_info=True)
