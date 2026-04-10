"""
Player Manager - Central player container (Single Source of Truth)
"""
import time
import os
import json
from ..core.logger import get_logger, debug_playback
from . import sequencer_integration as _seq

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
            from .core import Player
            from .sources import VideoSource
            
            # Load global config for preview_fps_limit setting
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config.json")
            preview_fps = None  # Default: use source FPS
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    global_config = json.load(f)
                    preview_fps = global_config.get('video', {}).get('preview_fps_limit')
                    if preview_fps is not None:
                        logger.debug(f"Preview FPS limit from config: {preview_fps}")
            except Exception as e:
                logger.warning(f"Could not load preview_fps_limit from config: {e}")
            
            # Create video preview player (clone video player config)
            if self.video_player:
                logger.debug("Creating video preview player...")
                
                # Clone config for preview player
                preview_config = self.video_player.config.copy() if self.video_player.config else {}
                
                self.video_preview_player = Player(
                    frame_source=VideoSource(
                        video_path=None,
                        canvas_width=self.video_player.canvas_width,
                        canvas_height=self.video_player.canvas_height,
                        config=preview_config
                    ),
                    target_ip=self.video_player.target_ip,
                    start_universe=self.video_player.start_universe,
                    fps_limit=preview_fps,  # Use config value (null = use source FPS)
                    config=preview_config,
                    enable_artnet=False,  # NO OUTPUT - preview only
                    player_name="VideoPreview",
                    clip_registry=self.video_player.clip_registry,
                    canvas_width=self.video_player.canvas_width,
                    canvas_height=self.video_player.canvas_height
                )
                self.players['video_preview'] = self.video_preview_player
                logger.debug("✅ Video preview player created (display output disabled)")
            
            # Create artnet preview player (clone artnet player config)
            if self.artnet_player:
                logger.debug("Creating Art-Net preview player...")
                
                # Clone config for preview player
                preview_config = self.artnet_player.config.copy() if self.artnet_player.config else {}
                
                self.artnet_preview_player = Player(
                    frame_source=VideoSource(
                        video_path=None,
                        canvas_width=self.artnet_player.canvas_width,
                        canvas_height=self.artnet_player.canvas_height,
                        config=preview_config
                    ),
                    target_ip=self.artnet_player.target_ip,
                    start_universe=self.artnet_player.start_universe,
                    fps_limit=preview_fps,  # Use config value (null = use source FPS)
                    config=preview_config,
                    enable_artnet=False,  # NO OUTPUT - preview only
                    player_name="ArtNetPreview",
                    clip_registry=self.artnet_player.clip_registry,
                    canvas_width=self.artnet_player.canvas_width,
                    canvas_height=self.artnet_player.canvas_height
                )
                self.players['artnet_preview'] = self.artnet_preview_player
                logger.debug("✅ Art-Net preview player created (display output disabled)")
            
            self._preview_players_created = True
            self._preview_last_used = time.time()
            logger.debug("🎭 Preview players initialized (isolated from output)")
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
                logger.debug("Destroying video preview player...")
                if self.video_preview_player.is_running:
                    self.video_preview_player.stop()
                self.video_preview_player = None
                self.players['video_preview'] = None
            
            if self.artnet_preview_player:
                logger.debug("Destroying Art-Net preview player...")
                if self.artnet_preview_player.is_running:
                    self.artnet_preview_player.stop()
                self.artnet_preview_player = None
                self.players['artnet_preview'] = None
            
            self._preview_players_created = False
            logger.debug("🗑️ Preview players destroyed")
            
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
            logger.debug(f"Preview players inactive for {inactive_time:.0f}s - destroying")
            self.destroy_preview_players()
            return True
        
        return False
    
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
        logger.debug(f"👑 Master playlist: {old_master} → {player_id}")
        if old_master != player_id:  # Only log stack on actual change
            logger.debug(f"📞 set_master_playlist called from:\n{''.join(traceback.format_stack()[:-1])}")
        
        # Emit WebSocket event for master/slave state change
        if self.socketio and old_master != player_id:
            try:
                self.socketio.emit('master_slave_changed', {
                    'master_playlist': player_id,
                    'timestamp': time.time()
                }, namespace='/player')
                logger.debug(f"📡 WebSocket: master_slave_changed emitted (master={player_id})")
            except Exception as e:
                logger.error(f"❌ Error emitting master_slave_changed WebSocket event: {e}")
        
        # Initial Sync: When Master is activated, ALL playlists jump to index 0 and start from frame 0
        if player_id is not None:
            # Reset ALL players to index 0, frame 0 (master AND slaves)
            for pid in self.get_all_player_ids():
                player = self.get_player(pid)
                if player and len(player.playlist) > 0:
                    was_playing = player.is_playing
                    logger.debug(f"Master mode activated - resetting {pid} to index 0, frame 0 (was at index {player.current_clip_index})")
                    
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
            logger.debug(f"⏹️ Slave {slave_player.player_name} stopped (index {clip_index} out of range, has {len(playlist)} clips) - black screen")
            return
        
        # Check if slave was previously auto-stopped by master (out of range)
        was_auto_stopped = getattr(slave_player, '_auto_stopped_by_master', False)
        
        # Load clip at index (this will restart playback if player was playing)
        success = slave_player.load_clip_by_index(clip_index, notify_manager=False)
        
        if success:
            # If slave was auto-stopped and now has valid clip, restart playback
            if was_auto_stopped and not slave_player.is_playing:
                logger.debug(f"🔄 Slave {slave_player.player_name} was auto-stopped, restarting playback at index {clip_index}")
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
    # Heavy logic lives in sequencer_integration.py; thin delegates here.

    def init_sequencer(self):
        """Initialize AudioSequencer.  See sequencer_integration.py."""
        _seq.init_sequencer(self)
    
    def set_sequencer_mode(self, enabled: bool):
        """Enable/disable sequencer mode.  See sequencer_integration.py."""
        _seq.set_sequencer_mode(self, enabled)
    
    def sequencer_advance_slaves(self, slot_index: int, force_reload: bool = False):
        """Advance all players to clip *slot_index*.  See sequencer_integration.py."""
        _seq.sequencer_advance_slaves(self, slot_index, force_reload)
    
    def _on_sequencer_slot_change(self, slot_index: int):
        """Kept for backward compat — wired by sequencer_integration.init_sequencer."""
        _seq._on_slot_change(self, slot_index)

    def _update_all_slave_caches(self):
        """Refresh slave-detection cache in all players.  See sequencer_integration.py."""
        _seq.update_all_slave_caches(self)

    def _on_sequencer_position_update(self, position: float, slot_index: int):
        """Throttled position-update callback.  See sequencer_integration.py."""
        _seq._on_position_update(self, position, slot_index)
    
    def update_sequences(self, dt: float):
        """Tick dynamic parameter sequences (render loop).  See sequencer_integration.py."""
        _seq.update_sequences(self, dt)
