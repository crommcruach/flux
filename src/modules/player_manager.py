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
    """
    
    def __init__(self, player=None, artnet_player=None):
        """
        Initialize PlayerManager with dual players.
        
        Args:
            player: Main video player (for backward compatibility, becomes video_player)
            artnet_player: Art-Net player instance (optional)
        """
        # Main player (legacy, maps to video_player for backward compatibility)
        self._player = player
        
        # Dual-player system
        self.video_player = player  # Player for video preview (no Art-Net)
        self.artnet_player = artnet_player  # Player for Art-Net output (no preview)
        
        logger.debug(f"PlayerManager initialized (video_player: {player is not None}, artnet_player: {artnet_player is not None})")
    
    @property
    def player(self):
        """Get main player instance (legacy, maps to video_player)."""
        return self._player or self.video_player
    
    @player.setter
    def player(self, new_player):
        """Set main player instance (legacy, updates video_player)."""
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
    
    def has_artnet_player(self):
        """Check if Art-Net player is set."""
        return self.artnet_player is not None
