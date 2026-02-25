"""
Transition Manager - Handles smooth transitions between clips
"""
import time
import numpy as np
from ...core.logger import get_logger, debug_playback

logger = get_logger(__name__)


class TransitionManager:
    """Manages transitions between video clips."""
    
    def __init__(self):
        """Initialize TransitionManager."""
        self.config = {
            "enabled": False,
            "effect": "fade",
            "duration": 1.0,
            "easing": "ease_in_out",
            "plugin": None
        }
        self.buffer = None  # Buffer für letztes Frame
        self.active = False
        self.start_time = 0
        self.frames = 0
        
    def configure(self, enabled=None, effect=None, duration=None, easing=None, plugin=None):
        """
        Configure transition settings.
        
        Args:
            enabled: Enable/disable transitions
            effect: Transition effect name
            duration: Transition duration in seconds
            easing: Easing function name
            plugin: Transition plugin instance
        """
        if enabled is not None:
            self.config["enabled"] = enabled
        if effect is not None:
            self.config["effect"] = effect
        if duration is not None:
            self.config["duration"] = duration
        if easing is not None:
            self.config["easing"] = easing
        if plugin is not None:
            self.config["plugin"] = plugin
            
    def start(self, player_name=""):
        """
        Start a new transition.
        
        Args:
            player_name: Name for logging
            
        Returns:
            bool: True if transition started, False if no buffer available
        """
        if not self.config.get("enabled") or self.buffer is None:
            return False
            
        self.active = True
        self.start_time = time.time()
        self.frames = 0
        debug_playback(logger, f"⚡ [{player_name}] Transition started: {self.config['effect']}")
        return True
    
    def apply(self, new_frame, player_name=""):
        """
        Apply transition to new frame.
        
        Args:
            new_frame: New frame to transition to
            player_name: Name for logging
            
        Returns:
            np.ndarray: Blended frame or original if transition not active
        """
        if not self.active or self.buffer is None:
            return new_frame
            
        elapsed = time.time() - self.start_time
        duration = self.config.get("duration", 1.0)
        
        if elapsed < duration:
            # Calculate progress (0.0 to 1.0)
            progress = min(1.0, elapsed / duration)
            
            # Apply transition using plugin
            transition_plugin = self.config.get("plugin")
            if transition_plugin:
                try:
                    blended_frame = transition_plugin.blend_frames(
                        self.buffer,
                        new_frame,
                        progress
                    )
                    self.frames += 1
                    return blended_frame
                except Exception as e:
                    logger.error(f"❌ [{player_name}] Transition error: {e}")
                    self.active = False
                    return new_frame
        else:
            # Transition complete
            self.active = False
            debug_playback(logger, f"✅ [{player_name}] Transition complete ({self.frames} frames)")
            
        return new_frame
    
    def store_frame(self, frame):
        """
        Store frame for next transition.
        
        Args:
            frame: Frame to store as transition buffer
        """
        if self.config.get("enabled"):
            self.buffer = frame.copy()
            
    def clear(self):
        """Clear transition state."""
        self.buffer = None
        self.active = False
        self.start_time = 0
        self.frames = 0
