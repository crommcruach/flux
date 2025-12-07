"""
Player Manager - Central player container (Single Source of Truth)
"""
from .logger import get_logger

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
    
    def __init__(self, player=None, artnet_player=None):
        """
        Initialize PlayerManager with dual players.
        
        Args:
            player: Video player instance (preview)
            artnet_player: Art-Net player instance (output)
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
        
        # DEBUG: Log stack trace to find who's calling this
        import traceback
        logger.info(f"👑 Master playlist: {old_master} → {player_id}")
        if old_master != player_id:  # Only log stack on actual change
            logger.info(f"📞 set_master_playlist called from:\n{''.join(traceback.format_stack()[:-1])}")
        
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
            logger.info(f"🔄 Slave {slave_player.player_name} synced to index {clip_index} (current_clip_index={slave_player.current_clip_index}, playlist_index={slave_player.playlist_index})")
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
