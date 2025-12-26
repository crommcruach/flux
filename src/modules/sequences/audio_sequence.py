"""
Audio Reactive Sequence

Binds parameter to audio features (RMS, Peak, Bass, Mid, Treble, BPM).
"""

import logging
import numpy as np
from typing import Dict, Any
from .base_sequence import BaseSequence

logger = logging.getLogger(__name__)


class AudioSequence(BaseSequence):
    """Audio-reactive parameter modulation"""
    
    FEATURES = ['rms', 'peak', 'bass', 'mid', 'treble', 'bpm', 'beat']
    MODES = ['rise-from-min', 'rise-from-max', 'beat-forward', 'beat-backward', 
             'raise', 'lower', 'attack_release', 'inverted_attack_release']  # Include legacy modes
    
    def __init__(self, sequence_id: str, target_parameter: str, audio_analyzer,
                 feature: str = 'rms', min_value: float = 0.0, max_value: float = 1.0,
                 smoothing: float = 0.1, invert: bool = False,
                 band: str = 'bass', mode: str = 'rise-from-min', attack_release: float = 0.5):
        """
        Initialize audio sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            audio_analyzer: AudioAnalyzer instance
            feature: Audio feature to bind ('rms', 'peak', 'bass', 'mid', 'treble', 'bpm', 'beat')
            min_value: Minimum parameter value
            max_value: Maximum parameter value
            smoothing: Smoothing factor (0-1, lower = smoother)
            invert: Invert audio value (1 - value)
            mode: Modulation mode:
                - 'rise-from-min': Start at rangeMin, rise on beat, fall back to rangeMin
                - 'rise-from-max': Start at rangeMax, fall on beat, rise back to rangeMax
                - 'beat-forward': Add to current, wrap at rangeMax
                - 'beat-backward': Subtract from current, wrap at rangeMin
            attack_release: Attack/release speed (0.0-1.0, higher = faster)
        """
        super().__init__(sequence_id, 'audio', target_parameter)
        
        self.audio_analyzer = audio_analyzer
        self.feature = feature
        self.min_value = min_value
        self.max_value = max_value
        self.smoothing = smoothing
        self.invert = invert
        self.band = band
        self.mode = mode if mode in self.MODES else 'rise-from-min'
        self.attack_release = attack_release
        self._envelope_value = 0.0  # Envelope state for attack_release modes
        self._last_applied_value = None  # Track last applied value to avoid marginal updates
        
        # Log configuration for debugging
        logger.info(f"🎵 AudioSequence created: mode={self.mode}, band={self.band}, range={self.min_value}-{self.max_value}, attack_release={self.attack_release}")
        
        # Initialize at appropriate starting value based on mode
        if self.mode == 'rise-from-max':
            self._current_value = self.max_value
        elif self.mode in ['beat-forward', 'beat-backward']:
            self._current_value = self.min_value  # Start at min for accumulator modes
        else:
            self._current_value = self.min_value
        
        if feature not in self.FEATURES:
            logger.warning(f"Unknown audio feature: {feature}, defaulting to 'rms'")
            self.feature = 'rms'
    
    def update(self, dt: float):
        """
        Update sequence value from audio features
        
        Args:
            dt: Delta time in seconds
        """
        if not self.audio_analyzer:
            if not hasattr(self, '_no_analyzer_logged'):
                logger.warning(f"⚠️ No audio_analyzer for sequence {self.id}")
                self._no_analyzer_logged = True
            return
            
        if not self.audio_analyzer.is_running():
            if not hasattr(self, '_not_running_logged'):
                logger.info(f"⏸️ Audio analyzer not running for sequence {self.id}")
                self._not_running_logged = True
            return
        
        # Reset log flags when running
        if hasattr(self, '_not_running_logged'):
            delattr(self, '_not_running_logged')
        if hasattr(self, '_no_analyzer_logged'):
            delattr(self, '_no_analyzer_logged')
        
        # Get audio features
        features = self.audio_analyzer.get_features()
        
        # Get band value (bass, mid, treble)
        band_value = features.get(self.band, 0.0)
        
        # Log audio feature detection (throttled)
        if not hasattr(self, '_log_counter'):
            self._log_counter = 0
        self._log_counter += 1
        
        if band_value > 0.01 and self._log_counter % 30 == 0:  # Log every 30 frames if audio detected
            logger.info(f"🎤 Audio detected: {self.band}={band_value:.3f} (beat={features.get('beat', False)})")
        
        audio_value = features.get(self.feature, band_value)
        
        # Handle beat feature (boolean -> float)
        if self.feature == 'beat':
            audio_value = 1.0 if audio_value else 0.0
        
        # Invert if requested
        if self.invert:
            audio_value = 1.0 - audio_value
        
        # Get beat detection for logging and beat modes
        beat_detected = features.get('beat', False)
        
        # Log mode and values for debugging (only when significant activity)
        if beat_detected or audio_value > 0.3:  # Only log when there's significant activity
            logger.info(f"🔊 Mode: {self.mode} | Audio: {audio_value:.2f} | Beat: {beat_detected} | Band[{self.band}]: {band_value:.2f}")
        
        # Apply modulation mode
        if self.mode == 'rise-from-min':
            # Start at rangeMin, rise to calculated value on audio, fall back to rangeMin
            if audio_value > 0.01:  # Audio detected → attack (rise)
                attack_speed = self.attack_release * 10.0
                self._envelope_value += audio_value * attack_speed * dt
                self._envelope_value = min(1.0, self._envelope_value)
            else:  # No audio → release (decay back to min)
                release_speed = self.attack_release * 5.0
                self._envelope_value -= release_speed * dt
                self._envelope_value = max(0.0, self._envelope_value)
            
            target_value = self.min_value + (self._envelope_value * (self.max_value - self.min_value))
            
        elif self.mode == 'rise-from-max':
            # Start at rangeMax, fall to calculated value on audio, rise back to rangeMax
            if audio_value > 0.01:  # Audio detected → attack (drop)
                attack_speed = self.attack_release * 10.0
                self._envelope_value += audio_value * attack_speed * dt
                self._envelope_value = min(1.0, self._envelope_value)
            else:  # No audio → release (rise back to max)
                release_speed = self.attack_release * 5.0
                self._envelope_value -= release_speed * dt
                self._envelope_value = max(0.0, self._envelope_value)
            
            target_value = self.max_value - (self._envelope_value * (self.max_value - self.min_value))
            
        elif self.mode == 'beat-forward':
            # Add band value to current on BEAT, wrap at rangeMax
            if beat_detected:
                # Use the band energy level as increment (scaled by range)
                increment = band_value * (self.max_value - self.min_value)
                self._current_value += increment
                # Wrap around at max
                if self._current_value > self.max_value:
                    self._current_value = self.min_value + (self._current_value - self.max_value)
                logger.info(f"🥁 BEAT forward: +{increment:.1f} -> {self._current_value:.1f}")
            target_value = self._current_value
            
        elif self.mode == 'beat-backward':
            # Subtract band value from current on BEAT, wrap at rangeMin
            if beat_detected:
                # Use the band energy level as decrement (scaled by range)
                decrement = band_value * (self.max_value - self.min_value)
                self._current_value -= decrement
                # Wrap around at min
                if self._current_value < self.min_value:
                    self._current_value = self.max_value - (self.min_value - self._current_value)
                logger.info(f"🥁 BEAT backward: -{decrement:.1f} -> {self._current_value:.1f}")
            target_value = self._current_value
        
        else:
            # Fallback to rise-from-min mode
            if audio_value > 0.01:
                attack_speed = self.attack_release * 10.0
                self._envelope_value += audio_value * attack_speed * dt
                self._envelope_value = min(1.0, self._envelope_value)
            else:
                release_speed = self.attack_release * 5.0
                self._envelope_value -= release_speed * dt
                self._envelope_value = max(0.0, self._envelope_value)
            target_value = self.min_value + (self._envelope_value * (self.max_value - self.min_value))
        
        # Smooth transition (only for beat-forward/backward, envelope modes have built-in smoothing)
        if self.mode in ['beat-forward', 'beat-backward']:
            # No smoothing for beat modes - use direct value
            self._current_value = target_value
        elif self.smoothing > 0:
            # Calculate alpha based on dt (time-based smoothing)
            alpha = 1.0 - np.exp(-dt / max(self.smoothing, 0.001))
            self._current_value += (target_value - self._current_value) * alpha
        else:
            self._current_value = target_value
        
        # CRITICAL: Clamp value to range to prevent going outside slider bounds
        self._current_value = max(self.min_value, min(self.max_value, self._current_value))
        
        # Log current value every 30 frames for debugging
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter += 1
        if self._debug_counter % 30 == 1:
            uid_parts = self.target_parameter.split('_')
            param_name = uid_parts[3] if len(uid_parts) > 3 else 'param'
            clip_id = uid_parts[2] if len(uid_parts) > 2 and uid_parts[1] == 'clip' else 'unknown'
            logger.debug(f"🎚️ [{self.mode}] Clip:{clip_id[:8]}... {param_name} = {self._current_value:.2f}, target={target_value:.2f}, audio={band_value:.3f} (range: {self.min_value}-{self.max_value})")
        
        # Only update if change is significant (> 1.0) to avoid marginal updates
        if self._last_applied_value is not None:
            value_change = abs(self._current_value - self._last_applied_value)
            if value_change < 1.0:
                # Skip update - change too small
                return
        
        # Update the last applied value
        self._last_applied_value = self._current_value
        
        # Log value updates (throttled to avoid spam)
        if not hasattr(self, '_value_log_counter'):
            self._value_log_counter = 0
        self._value_log_counter += 1
        
        # Log every 30 frames (~1 second at 30fps) or on significant changes
        if hasattr(self, '_last_logged_value'):
            value_change = abs(self._current_value - self._last_logged_value)
            should_log = (self._value_log_counter % 30 == 0) or (value_change > (self.max_value - self.min_value) * 0.1)
        else:
            should_log = True
        
        if should_log:
            logger.info(f"🎚️ [{self.name}] {self.target_parameter.split('_')[3] if '_' in self.target_parameter else 'param'} = {self._current_value:.2f} (range: {self.min_value:.1f}-{self.max_value:.1f}, {self.band}={band_value:.3f})")
            self._last_logged_value = self._current_value
    
    def get_value(self) -> float:
        """Get current modulated value"""
        return self._current_value
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'feature': self.feature,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'smoothing': self.smoothing,
            'invert': self.invert,
            'band': self.band,
            'mode': self.mode,
            'attack_release': self.attack_release,
            'enabled': self.enabled
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any], audio_analyzer) -> 'AudioSequence':
        """
        Create from dictionary
        
        Args:
            data: Serialized data
            audio_analyzer: AudioAnalyzer instance
            
        Returns:
            AudioSequence instance
        """
        return cls(
            sequence_id=data.get('id'),
            target_parameter=data.get('target_parameter'),
            audio_analyzer=audio_analyzer,
            feature=data.get('feature', 'rms'),
            min_value=data.get('min_value', 0.0),
            max_value=data.get('max_value', 1.0),
            smoothing=data.get('smoothing', 0.1),
            invert=data.get('invert', False),
            band=data.get('band', 'bass'),
            mode=data.get('mode', data.get('direction', 'raise')),  # Backward compatible
            attack_release=data.get('attack_release', 0.5)
        )
