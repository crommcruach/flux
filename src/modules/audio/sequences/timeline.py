"""
Timeline Sequence

Simple time-based animation that interpolates from min to max over a duration.
"""

import random
import logging
from typing import Dict, Any
from .base_sequence import BaseSequence

logger = logging.getLogger(__name__)


class TimelineSequence(BaseSequence):
    """Time-based animation from min to max over duration"""
    
    LOOP_MODES = ['once', 'loop', 'ping_pong', 'random']
    PLAYBACK_STATES = ['pause', 'forward', 'backward']
    
    def __init__(self, sequence_id: str, target_parameter: str,
                 loop_mode: str = 'once', duration: float = 5.0, 
                 playback_state: str = 'pause', speed: float = 1.0,
                 min_value: float = 0.0, max_value: float = 100.0):
        """
        Initialize timeline sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            loop_mode: Loop mode ('once', 'loop', 'ping_pong', 'random')
            duration: Total animation duration in seconds
            playback_state: Playback state ('pause', 'forward', 'backward')
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x faster, 0.5 = half speed)
            min_value: Minimum parameter value
            max_value: Maximum parameter value
        """
        super().__init__(sequence_id, 'timeline', target_parameter)
        
        self.loop_mode = loop_mode if loop_mode in self.LOOP_MODES else 'once'
        self.duration = duration
        self.playback_state = playback_state if playback_state in self.PLAYBACK_STATES else 'pause'
        self.speed = max(0.1, min(10.0, speed))  # Clamp between 0.1x and 10x
        self.min_value = min_value
        self.max_value = max_value
        
        self._time = 0.0
        self._progress = 0.0  # 0.0 to 1.0
        self._direction = 1  # 1 = forward, -1 = backward (for ping_pong)
        self._random_jump_interval = 0.15  # Jump every 0.15 seconds in random mode
        self._time_since_last_jump = 0.0
        self._current_random_value = min_value  # Current random value for random mode
        
        logger.debug(f"Created Timeline sequence: {duration}s, {playback_state}, {loop_mode}, {speed}x, range: {min_value}-{max_value}")
    
    def update(self, dt: float):
        """
        Update timeline progress
        
        Args:
            dt: Delta time in seconds
        """
        # Don't update if paused
        if self.playback_state == 'pause':
            return
        
        # Determine direction based on loop mode and playback state
        # For ping_pong, always use internal direction
        if self.loop_mode == 'ping_pong':
            direction = self._direction
        elif self.playback_state == 'forward':
            direction = 1
        elif self.playback_state == 'backward':
            direction = -1
        else:
            direction = self._direction
        
        # Handle random mode differently - jump at intervals
        if self.loop_mode == 'random':
            self._time_since_last_jump += dt
            
            # Check if it's time for a new random jump
            if self._time_since_last_jump >= self._random_jump_interval:
                # Pick random value between min and max
                self._current_random_value = random.uniform(self.min_value, self.max_value)
                self._time_since_last_jump = 0.0
                logger.debug(f"Random jump to value: {self._current_random_value:.2f}")
            
            # Don't update time/progress in random mode
            return
        
        # Calculate time increment (apply speed multiplier)
        time_increment = dt * direction * self.speed
        
        # Update time
        self._time += time_increment
        
        # Calculate normalized progress (0-1)
        normalized_progress = self._time / self.duration if self.duration > 0 else 0
        
        # Handle loop modes
        if self.loop_mode == 'once':
            if self.playback_state == 'forward':
                self._progress = min(normalized_progress, 1.0)
            elif self.playback_state == 'backward':
                self._progress = max(normalized_progress, 0.0)
        
        elif self.loop_mode == 'loop':
            if normalized_progress >= 1.0:
                self._time = 0.0
                self._progress = 0.0
            elif normalized_progress < 0:
                self._time = self.duration
                self._progress = 1.0
            else:
                self._progress = normalized_progress
        
        elif self.loop_mode == 'ping_pong':
            if normalized_progress >= 1.0:
                # Reflect back from 1.0
                over = normalized_progress - 1.0
                self._time = self.duration - (over * self.duration)
                self._progress = 1.0 - over
                self._direction = -1
            elif normalized_progress <= 0:
                # Reflect back from 0.0
                under = -normalized_progress
                self._time = under * self.duration
                self._progress = under
                self._direction = 1
            else:
                self._progress = normalized_progress
            
            # Clamp to valid range
            self._progress = max(0.0, min(1.0, self._progress))
    
    def get_value(self) -> float:
        """Get interpolated value at current progress"""
        # Random mode returns the current random value
        if self.loop_mode == 'random':
            return self._current_random_value
        
        # Linear interpolation from min to max
        return self.min_value + (self.max_value - self.min_value) * self._progress
    
    def reset(self):
        """Reset timeline to beginning"""
        self._time = 0.0
        self._progress = 0.0
        self._direction = 1
        self._time_since_last_jump = 0.0
        self._current_random_value = self.min_value
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'loop_mode': self.loop_mode,
            'duration': self.duration,
            'playback_state': self.playback_state,
            'speed': self.speed,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'enabled': self.enabled
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'TimelineSequence':
        """Create from dictionary"""
        return cls(
            sequence_id=data.get('id'),
            target_parameter=data.get('target_parameter'),
            loop_mode=data.get('loop_mode', 'once'),
            duration=data.get('duration', 5.0),
            playback_state=data.get('playback_state', 'pause'),
            speed=data.get('speed', 1.0),
            min_value=data.get('min_value', 0.0),
            max_value=data.get('max_value', 100.0)
        )
