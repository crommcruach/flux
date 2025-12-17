"""
Player Manager - Central player container (Single Source of Truth)
"""
import time
from .logger import get_logger, debug_playback

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
        
        # Dual-player system
        self.video_player = player  # Player for video preview (no Art-Net)
        self.artnet_player = artnet_player  # Player for Art-Net output (no preview)
        
        # Unified player registry with IDs
        self.players = {
            'video': self.video_player,
            'artnet': self.artnet_player
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
            player_id: Player identifier ('video' or 'artnet')
        
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
        
        # Initial Sync: When Master is activated, jump to index 0 and sync all players
        if player_id is not None:
            master_player = self.get_player(player_id)
            if master_player and len(master_player.playlist) > 0:
                was_playing = master_player.is_playing
                logger.info(f"Master {player_id} activated - jumping to index 0 (was at index {master_player.current_clip_index})")
                
                # Force master to index 0 (notify_manager=False to avoid double-sync)
                master_player.load_clip_by_index(0, notify_manager=False)
                
                # Restart playback if it was playing
                if was_playing and not master_player.is_playing:
                    master_player.start()
                
                # Now sync all slaves to master at index 0
                logger.info(f"Syncing all slaves to master {player_id} at index 0")
                self.sync_slaves_to_master()
        
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
        
        # If Slave doesn't have enough clips → Stop playback
        if clip_index >= len(playlist):
            slave_player.stop()
            logger.info(f"⏹️ Slave {slave_player.player_name} stopped (index {clip_index} out of range, has {len(playlist)} clips)")
            return
        
        # Load clip at index (this will restart playback if player was playing)
        success = slave_player.load_clip_by_index(clip_index, notify_manager=False)
        
        if success:
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
                current_index = getattr(player, 'current_clip_index', -1)
                
                # Map slot index to clip index (with wrapping if slot exceeds playlist length)
                target_index = slot_index % len(player.playlist_manager.playlist)
                
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
