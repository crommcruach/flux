"""
Player Manager - Central player container (Single Source of Truth)
"""
from .logger import get_logger

logger = get_logger(__name__)


class PlayerManager:
    """
    Central container for player management.
    
    This class serves as a Single Source of Truth for player access,
    eliminating the architectural issue where DMXController was misused
    as a player container.
    
    Benefits:
    - Clear separation of concerns
    - Single Responsibility Principle
    - Reduced coupling between modules
    - Better testability
    - Easier player switching
    """
    
    def __init__(self, player=None):
        """
        Initialize PlayerManager.
        
        Args:
            player: Initial player instance (optional)
        """
        self._player = player
        logger.debug("PlayerManager initialized")
    
    @property
    def player(self):
        """Get current player instance."""
        return self._player
    
    @player.setter
    def player(self, new_player):
        """Set player instance."""
        old_player = self._player
        self._player = new_player
        
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
