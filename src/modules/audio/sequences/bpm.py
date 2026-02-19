"""
BPM Sequence

Beat-synchronized continuous animation that interpolates from min to max over N beats.
Duration = beat_division / (BPM / 60) seconds
"""

import time
import logging
from typing import Dict, Any, Optional
from .base import BaseSequence

logger = logging.getLogger(__name__)


class BPMSequence(BaseSequence):
    """Beat-synchronized continuous animation over N beats"""
    
    # Number of beats for animation duration (fractional and whole numbers)
    BEAT_DIVISIONS = [0.0625, 0.125, 0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128]
    
    def __init__(self, sequence_id: str, target_parameter: str, audio_analyzer,
                 beat_division: int = 8, clip_duration: float = 10.0,
                 playback_state: str = 'forward', loop_mode: str = 'loop',
                 speed: float = 1.0, min_value: float = 0.0, max_value: float = 100.0):
        """
        Initialize BPM sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            audio_analyzer: Reference to AudioAnalyzer for BPM data
            beat_division: Number of beats for full animation (0.0625=1/16, 0.125=1/8, 0.25=1/4, 0.5=1/2, 1, 4, 8, 16, 32, 64, 128)
            clip_duration: Total clip duration in seconds
            playback_state: 'forward', 'backward', or 'pause'
            loop_mode: 'once', 'loop', or 'ping_pong'
            speed: Speed multiplier (0.1 to 10.0)
            min_value: Minimum parameter value (e.g., 0 for scale)
            max_value: Maximum parameter value (e.g., 500 for scale)
        """
        super().__init__(sequence_id, 'bpm', target_parameter)
        
        self.audio_analyzer = audio_analyzer
        self.beat_division = beat_division if beat_division in self.BEAT_DIVISIONS else 8
        self.clip_duration = clip_duration
        self.playback_state = playback_state
        self.loop_mode = loop_mode
        self.speed = max(0.1, min(10.0, speed))
        self.min_value = min_value
        self.max_value = max_value
        
        # Animation state
        self._start_beat_count = None  # Beat count when animation started
        self._progress = 0.0  # Current progress (0.0 to 1.0)
        self._direction = 1  # 1 for forward, -1 for backward (ping_pong)
        self._last_beat_count = 0
        self._animation_active = False
        
        logger.info(f"Created BPM sequence: {beat_division} beats, {playback_state}, {loop_mode}, {speed}x, range: {min_value}-{max_value}")
    
    def update(self, dt: float):
        """
        Update animation progress based on beat counting
        
        Args:
            dt: Delta time in seconds (not used, we sync to beats)
        """
        # Add debug logging counter
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        
        if not self.audio_analyzer:
            if self._debug_counter % 60 == 1:
                logger.warning(f"🚫 BPM sequence {self.id}: No audio analyzer!")
            return
        
        # Pause: don't update
        if self.playback_state == 'pause':
            if self._debug_counter % 60 == 1:
                logger.info(f"⏸️ BPM sequence {self.id}: Paused")
            return
        
        # Get BPM status
        bpm_status = self.audio_analyzer.get_bpm_status()
        
        if not bpm_status.get('enabled', False):
            if self._debug_counter % 60 == 1:
                logger.info(f"🚫 BPM sequence {self.id}: BPM not enabled")
            return
        
        current_beat_count = bpm_status.get('beat_count', 0)
        
        # Log BPM status every 60 frames
        if self._debug_counter % 60 == 1:
            logger.debug(f"🥁 BPM sequence {self.id}: beat_count={current_beat_count}, last={self._last_beat_count}, active={self._animation_active}, progress={self._progress:.3f}")
        
        # Start animation on first beat or when beat count changes
        if current_beat_count != self._last_beat_count:
            if not self._animation_active:
                self._start_beat_count = current_beat_count
                self._animation_active = True
                logger.info(f"🎬 BPM animation started at beat {current_beat_count}")
            self._last_beat_count = current_beat_count
        
        # If animation not started yet, return min value
        if not self._animation_active or self._start_beat_count is None:
            self._progress = 0.0 if self._direction > 0 else 1.0
            if self._debug_counter % 60 == 1:
                logger.info(f"⏳ BPM sequence {self.id}: Waiting for first beat...")
            return
        
        # Calculate progress based on beat counting (always in sync!)
        # Example: beat_division=8, speed=1.0, current_beat=5, start_beat=1 → 4 beats elapsed
        #          progress = (4 * 1.0) / 8 = 0.5 (50% through animation)
        beats_elapsed = (current_beat_count - self._start_beat_count) * self.speed
        raw_progress = beats_elapsed / self.beat_division if self.beat_division > 0 else 0.0
        
        # Log progress every 60 frames
        if self._debug_counter % 60 == 1:
            logger.debug(f"📊 BPM progress: beats_elapsed={beats_elapsed:.2f}, raw_progress={raw_progress:.3f}, beat_division={self.beat_division}")
        
        # Apply loop mode
        if self.loop_mode == 'once':
            # Clamp to 0-1
            self._progress = max(0.0, min(1.0, raw_progress))
            if raw_progress >= 1.0:
                self._animation_active = False  # Stop animation
                
        elif self.loop_mode == 'loop':
            # Wrap around
            self._progress = raw_progress % 1.0
            # Restart beat count on loop
            if raw_progress >= 1.0 and int(raw_progress) != int(raw_progress - self.speed):
                self._start_beat_count = current_beat_count
            
        elif self.loop_mode == 'ping_pong':
            # Bounce between 0 and 1
            cycle = raw_progress % 2.0
            if cycle < 1.0:
                self._progress = cycle
                self._direction = 1
            else:
                self._progress = 2.0 - cycle
                self._direction = -1
        
        # Apply forward/backward direction
        if self.playback_state == 'backward':
            self._progress = 1.0 - self._progress
    
    def get_value(self) -> float:
        """Get current interpolated value scaled to parameter range"""
        # Interpolate from min to max based on progress
        value = self.min_value + self._progress * (self.max_value - self.min_value)
        
        # Debug log value every 60 calls
        if not hasattr(self, '_get_value_counter'):
            self._get_value_counter = 0
        self._get_value_counter += 1
        
        if self._get_value_counter % 60 == 1:
            logger.debug(f"📈 BPM get_value(): progress={self._progress:.3f}, min={self.min_value}, max={self.max_value}, value={value:.2f}")
        
        return value
    
    def set_beat_division(self, beat_division: float):
        """
        Change beat division (animation duration in beats)
        
        Args:
            beat_division: New beat division (0.0625, 0.125, 0.25, 0.5, 1, 4, 8, 16, 32, 64, 128)
        """
        if beat_division not in self.BEAT_DIVISIONS:
            logger.warning(f"Invalid beat division: {beat_division}, keeping {self.beat_division}")
            return
        
        self.beat_division = beat_division
        logger.info(f"Beat division changed to {beat_division} beats")
    
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
        """Reset animation to start"""
        self._start_beat_count = None
        self._progress = 0.0
        self._direction = 1
        self._last_beat_count = 0
        self._animation_active = False
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'beat_division': self.beat_division,
            'clip_duration': self.clip_duration,
            'playback_state': self.playback_state,
            'loop_mode': self.loop_mode,
            'speed': self.speed,
            'min_value': self.min_value,
            'max_value': self.max_value,
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
            clip_duration=data.get('clip_duration', 10.0),
            playback_state=data.get('playback_state', 'forward'),
            loop_mode=data.get('loop_mode', 'loop'),
            speed=data.get('speed', 1.0),
            min_value=data.get('min_value', 0.0),
            max_value=data.get('max_value', 100.0)
        )
        sequence.enabled = data.get('enabled', True)
        return sequence
