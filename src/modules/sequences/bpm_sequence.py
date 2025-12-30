"""
BPM Sequence

Beat-synchronized keyframe animation that jumps to keyframes on each beat.
"""

import random
import logging
from typing import Dict, Any, List, Tuple, Optional
from .base_sequence import BaseSequence

logger = logging.getLogger(__name__)


class BPMSequence(BaseSequence):
    """Beat-synchronized keyframe animation"""
    
    BEAT_DIVISIONS = [1, 4, 8, 16, 32]  # Number of keyframes/beats
    
    def __init__(self, sequence_id: str, target_parameter: str, audio_analyzer,
                 beat_division: int = 8, keyframes: List[float] = None,
                 clip_duration: float = 10.0, playback_state: str = 'forward',
                 loop_mode: str = 'loop', speed: float = 1.0):
        """
        Initialize BPM sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            audio_analyzer: Reference to AudioAnalyzer for BPM data
            beat_division: Number of beats/keyframes (1, 4, 8, 16, or 32)
            keyframes: List of values (one per beat)
            clip_duration: Total clip duration in seconds
            playback_state: 'forward', 'backward', or 'pause'
            loop_mode: 'once', 'loop', or 'ping_pong'
            speed: Speed multiplier (0.1 to 10.0)
        """
        super().__init__(sequence_id, 'bpm', target_parameter)
        
        self.audio_analyzer = audio_analyzer
        self.beat_division = beat_division if beat_division in self.BEAT_DIVISIONS else 8
        self.clip_duration = clip_duration
        self.playback_state = playback_state
        self.loop_mode = loop_mode
        self.speed = max(0.1, min(10.0, speed))
        
        # Initialize keyframes (one value per beat)
        if keyframes and len(keyframes) == beat_division:
            self.keyframes = keyframes
        else:
            # Default: linear ramp from 0 to 1
            self.keyframes = [i / (beat_division - 1) for i in range(beat_division)]
        
        # Current state
        self._current_beat_index = 0
        self._last_beat_count = 0
        self._current_value = self.keyframes[0] if self.keyframes else 0.0
        self._beat_accumulator = 0.0  # For speed multiplier
        self._direction = 1  # 1 for forward, -1 for backward (ping_pong)
        
        logger.info(f"Created BPM sequence: {beat_division} beats, {playback_state}, {loop_mode}, {speed}x")
    
    def update(self, dt: float):
        """
        Update beat index based on BPM
        
        Args:
            dt: Delta time in seconds (not used, we sync to beats)
        """
        if not self.audio_analyzer:
            return
        
        # Get BPM status
        bpm_status = self.audio_analyzer.get_bpm_status()
        
        if not bpm_status.get('enabled', False):
            return
        
        current_beat_count = bpm_status.get('beat_count', 0)
        
        # Check if a new beat occurred
        if current_beat_count != self._last_beat_count:
            self._on_beat()
            self._last_beat_count = current_beat_count
    
    def _on_beat(self):
        """Handle beat event - advance beat index based on playback state"""
        if not self.keyframes:
            return
        
        # Pause: don't advance
        if self.playback_state == 'pause':
            return
        
        # Apply speed: accumulate beat count
        self._beat_accumulator += self.speed
        
        # Only advance if accumulated at least 1 beat
        if self._beat_accumulator < 1.0:
            return
        
        # Advance by integer number of beats
        beats_to_advance = int(self._beat_accumulator)
        self._beat_accumulator -= beats_to_advance
        
        # Determine direction
        if self.playback_state == 'backward':
            step = -beats_to_advance * self._direction
        else:  # forward
            step = beats_to_advance * self._direction
        
        # Calculate new index
        new_index = self._current_beat_index + step
        
        # Apply loop mode
        if self.loop_mode == 'once':
            # Stop at boundaries
            if new_index < 0:
                new_index = 0
            elif new_index >= len(self.keyframes):
                new_index = len(self.keyframes) - 1
                
        elif self.loop_mode == 'loop':
            # Wrap around
            new_index = new_index % len(self.keyframes)
            
        elif self.loop_mode == 'ping_pong':
            # Bounce at boundaries
            max_index = len(self.keyframes) - 1
            
            while new_index < 0 or new_index > max_index:
                if new_index < 0:
                    new_index = -new_index
                    self._direction *= -1
                elif new_index > max_index:
                    new_index = 2 * max_index - new_index
                    self._direction *= -1
        
        self._current_beat_index = new_index
        
        # Update value immediately
        self._current_value = self.keyframes[self._current_beat_index]
        
        logger.debug(f"Beat! Index: {self._current_beat_index}, Value: {self._current_value:.3f}, Direction: {self._direction}")
    
    def get_value(self) -> float:
        """Get current keyframe value"""
        return self._current_value
    
    def set_keyframe(self, index: int, value: float):
        """
        Set keyframe value
        
        Args:
            index: Keyframe index (0 to beat_division-1)
            value: Value to set (0.0 to 1.0)
        """
        if 0 <= index < len(self.keyframes):
            self.keyframes[index] = max(0.0, min(1.0, value))
            logger.debug(f"Set keyframe {index}: {value:.3f}")
        else:
            logger.warning(f"Invalid keyframe index: {index} (max: {len(self.keyframes) - 1})")
    
    def set_beat_division(self, beat_division: int):
        """
        Change beat division and resize keyframes
        
        Args:
            beat_division: New beat division (1, 4, 8, 16, or 32)
        """
        if beat_division not in self.BEAT_DIVISIONS:
            logger.warning(f"Invalid beat division: {beat_division}, keeping {self.beat_division}")
            return
        
        # Interpolate existing keyframes to new count
        old_keyframes = self.keyframes
        new_keyframes = []
        
        for i in range(beat_division):
            # Map new index to old index range
            old_index_float = (i / (beat_division - 1)) * (len(old_keyframes) - 1) if beat_division > 1 else 0
            old_index = int(old_index_float)
            
            if old_index >= len(old_keyframes) - 1:
                new_keyframes.append(old_keyframes[-1])
            else:
                # Linear interpolation
                t = old_index_float - old_index
                value = old_keyframes[old_index] * (1 - t) + old_keyframes[old_index + 1] * t
                new_keyframes.append(value)
        
        self.beat_division = beat_division
        self.keyframes = new_keyframes
        self._current_beat_index = 0
        
        logger.info(f"Beat division changed to {beat_division}, keyframes resized")
    
    def set_playback_state(self, state: str):
        """Set playback state (forward, backward, pause)"""
        if state in ['forward', 'backward', 'pause']:
            self.playback_state = state
            logger.info(f"Playback state: {state}")
        else:
            logger.warning(f"Invalid playback state: {state}")
    
    def set_loop_mode(self, mode: str):
        """Set loop mode (once, loop, ping_pong)"""
        if mode in ['once', 'loop', 'ping_pong']:
            self.loop_mode = mode
            self._direction = 1  # Reset direction on mode change
            logger.info(f"Loop mode: {mode}")
        else:
            logger.warning(f"Invalid loop mode: {mode}")
    
    def set_speed(self, speed: float):
        """Set speed multiplier (0.1 to 10.0)"""
        self.speed = max(0.1, min(10.0, speed))
        logger.info(f"Speed: {self.speed}x")
    
    def reset(self):
        """Reset to first keyframe"""
        self._current_beat_index = 0
        self._last_beat_count = 0
        self._beat_accumulator = 0.0
        self._direction = 1
        if self.keyframes:
            self._current_value = self.keyframes[0]
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'beat_division': self.beat_division,
            'keyframes': self.keyframes,
            'clip_duration': self.clip_duration,
            'playback_state': self.playback_state,
            'loop_mode': self.loop_mode,
            'speed': self.speed,
            'enabled': self.enabled
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any], audio_analyzer) -> 'BPMSequence':
        """
        Create from dictionary
        
        Args:
            data: Serialized data
            audio_analyzer: Reference to AudioAnalyzer instance
        """
        sequence = cls(
            sequence_id=data.get('id'),
            target_parameter=data.get('target_parameter'),
            audio_analyzer=audio_analyzer,
            beat_division=data.get('beat_division', 8),
            keyframes=data.get('keyframes'),
            clip_duration=data.get('clip_duration', 10.0),
            playback_state=data.get('playback_state', 'forward'),
            loop_mode=data.get('loop_mode', 'loop'),
            speed=data.get('speed', 1.0)
        )
        sequence.enabled = data.get('enabled', True)
        return sequence
