"""
Timeline Sequence

Keyframe-based timeline animation with interpolation.
"""

import bisect
import random
import logging
from typing import Dict, Any, List, Tuple
from .base_sequence import BaseSequence

logger = logging.getLogger(__name__)


class TimelineSequence(BaseSequence):
    """Keyframe-based timeline animation"""
    
    INTERPOLATIONS = ['linear', 'ease_in', 'ease_out', 'ease_in_out', 'step']
    LOOP_MODES = ['once', 'loop', 'ping_pong', 'random']
    
    PLAYBACK_STATES = ['pause', 'forward', 'backward']
    
    def __init__(self, sequence_id: str, target_parameter: str, keyframes: List[Tuple[float, float]] = None,
                 interpolation: str = 'linear', loop_mode: str = 'once', duration: float = 10.0, 
                 playback_state: str = 'pause', speed: float = 1.0):
        """
        Initialize timeline sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            keyframes: List of (time, value) tuples
            interpolation: Interpolation type ('linear', 'ease_in', 'ease_out', 'ease_in_out', 'step')
            loop_mode: Loop mode ('once', 'loop', 'ping_pong')
            duration: Total timeline duration in seconds
            playback_state: Playback state ('pause', 'forward', 'backward')
            speed: Speed multiplier (1.0 = normal, 2.0 = 2x faster, 0.5 = half speed)
        """
        super().__init__(sequence_id, 'timeline', target_parameter)
        
        self.keyframes = keyframes or []
        self.interpolation = interpolation
        self.loop_mode = loop_mode
        self.duration = duration
        self.playback_state = playback_state if playback_state in self.PLAYBACK_STATES else 'pause'
        self.speed = max(0.1, min(10.0, speed))  # Clamp between 0.1x and 10x
        
        self._time = 0.0
        self._direction = 1  # 1 = forward, -1 = backward (for ping_pong or backward playback)
        self._current_keyframe_index = 0  # For random mode
        
        # Sort keyframes by time
        self.keyframes.sort(key=lambda k: k[0])
        
        if interpolation not in self.INTERPOLATIONS:
            logger.warning(f"Unknown interpolation: {interpolation}, defaulting to 'linear'")
            self.interpolation = 'linear'
        
        if loop_mode not in self.LOOP_MODES:
            logger.warning(f"Unknown loop mode: {loop_mode}, defaulting to 'once'")
            self.loop_mode = 'once'
    
    def update(self, dt: float):
        """
        Update timeline time
        
        Args:
            dt: Delta time in seconds
        """
        # Don't update if paused
        if self.playback_state == 'pause':
            return
        
        # Determine direction based on playback state
        if self.playback_state == 'forward':
            direction = 1
        elif self.playback_state == 'backward':
            direction = -1
        else:
            direction = self._direction  # Use ping_pong direction
        
        # Calculate time increment as fraction of duration (0-1 range)
        # This makes the timeline scale with duration automatically
        # Apply speed multiplier: higher speed = faster playback
        time_increment = (dt / self.duration) * direction * self.speed
        
        # Update normalized time (0-1)
        normalized_time = self._time / self.duration if self.duration > 0 else 0
        normalized_time += time_increment
        
        # Handle loop modes with normalized time
        if self.loop_mode == 'once':
            if self.playback_state == 'forward':
                normalized_time = min(normalized_time, 1.0)
            elif self.playback_state == 'backward':
                normalized_time = max(normalized_time, 0.0)
        
        elif self.loop_mode == 'loop':
            if normalized_time >= 1.0:
                normalized_time = normalized_time % 1.0
            elif normalized_time < 0:
                normalized_time = 1.0 + (normalized_time % 1.0)
        
        elif self.loop_mode == 'ping_pong':
            if normalized_time >= 1.0:
                normalized_time = 1.0
                self._direction = -1
            elif normalized_time <= 0:
                normalized_time = 0
                self._direction = 1
        
        elif self.loop_mode == 'random':
            # Jump randomly to ANY keyframe when reaching current keyframe
            if not self.keyframes or len(self.keyframes) < 2:
                # Convert back to absolute time
                self._time = normalized_time * self.duration
                return
            
            # Check if we've reached the current target keyframe
            current_kf_time = self.keyframes[self._current_keyframe_index][0]
            
            # Check if we've passed the keyframe (depends on direction)
            if (self.playback_state == 'forward' and self._time >= current_kf_time) or \
               (self.playback_state == 'backward' and self._time <= current_kf_time):
                
                # Pick ANY random keyframe
                new_index = random.randint(0, len(self.keyframes) - 1)
                
                # Avoid staying on same keyframe if possible
                if len(self.keyframes) > 1:
                    while new_index == self._current_keyframe_index:
                        new_index = random.randint(0, len(self.keyframes) - 1)
                
                self._current_keyframe_index = new_index
                
                # Jump to new keyframe time
                self._time = self.keyframes[self._current_keyframe_index][0]
                return
        
        # Convert normalized time back to absolute time
        self._time = normalized_time * self.duration
    
    def get_value(self) -> float:
        """Interpolate value at current time"""
        if not self.keyframes:
            return 0.0
        
        # Find surrounding keyframes
        times = [k[0] for k in self.keyframes]
        idx = bisect.bisect_left(times, self._time)
        
        # Before first keyframe
        if idx == 0:
            return self.keyframes[0][1]
        
        # After last keyframe
        if idx >= len(self.keyframes):
            return self.keyframes[-1][1]
        
        # Between keyframes
        k1_time, k1_value = self.keyframes[idx - 1]
        k2_time, k2_value = self.keyframes[idx]
        
        # Normalize time (0-1 between keyframes)
        if k2_time == k1_time:
            return k1_value
        
        t = (self._time - k1_time) / (k2_time - k1_time)
        
        # Apply interpolation
        if self.interpolation == 'linear':
            t_interp = t
        
        elif self.interpolation == 'ease_in':
            t_interp = t * t
        
        elif self.interpolation == 'ease_out':
            t_interp = 1 - (1 - t) * (1 - t)
        
        elif self.interpolation == 'ease_in_out':
            # Smoothstep
            t_interp = 3 * t * t - 2 * t * t * t
        
        elif self.interpolation == 'step':
            # Hold value until next keyframe
            t_interp = 0
        
        else:
            t_interp = t
        
        # Interpolate value
        return k1_value + (k2_value - k1_value) * t_interp
    
    def add_keyframe(self, time: float, value: float):
        """
        Add keyframe and resort
        
        Args:
            time: Time in seconds
            value: Value at this time
        """
        self.keyframes.append((time, value))
        self.keyframes.sort(key=lambda k: k[0])
        logger.debug(f"Added keyframe: t={time}, v={value}")
    
    def remove_keyframe(self, index: int) -> bool:
        """
        Remove keyframe by index
        
        Args:
            index: Index of keyframe to remove
            
        Returns:
            True if removed, False if invalid index
        """
        if 0 <= index < len(self.keyframes):
            removed = self.keyframes.pop(index)
            logger.debug(f"Removed keyframe: {removed}")
            return True
        return False
    
    def reset(self):
        """Reset timeline to beginning"""
        self._time = 0.0
        self._direction = 1
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'keyframes': self.keyframes,
            'interpolation': self.interpolation,
            'loop_mode': self.loop_mode,
            'duration': self.duration,
            'playback_state': self.playback_state,
            'speed': self.speed,
            'enabled': self.enabled
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'TimelineSequence':
        """Create from dictionary"""
        return cls(
            sequence_id=data.get('id'),
            target_parameter=data.get('target_parameter'),
            keyframes=data.get('keyframes', []),
            interpolation=data.get('interpolation', 'linear'),
            loop_mode=data.get('loop_mode', 'once'),
            duration=data.get('duration', 10.0),
            playback_state=data.get('playback_state', 'pause'),
            speed=data.get('speed', 1.0)
        )
