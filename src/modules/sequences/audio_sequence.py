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
    
    def __init__(self, sequence_id: str, target_parameter: str, audio_analyzer,
                 feature: str = 'rms', min_value: float = 0.0, max_value: float = 1.0,
                 smoothing: float = 0.1, invert: bool = False,
                 band: str = 'bass', direction: str = 'rise_from_min', attack_release: float = 0.5):
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
            band: Frequency band ('bass', 'mid', 'treble')
            direction: Playback direction ('rise_from_min', 'rise_from_max', 'beat_forward', 'beat_backward')
            attack_release: Attack/release time (0.0-1.0)
        """
        super().__init__(sequence_id, 'audio', target_parameter)
        
        self.audio_analyzer = audio_analyzer
        self.feature = feature
        self.min_value = min_value
        self.max_value = max_value
        self.smoothing = smoothing
        self.invert = invert
        self.band = band
        self.direction = direction
        self.attack_release = attack_release
        
        self._current_value = min_value
        
        if feature not in self.FEATURES:
            logger.warning(f"Unknown audio feature: {feature}, defaulting to 'rms'")
            self.feature = 'rms'
    
    def update(self, dt: float):
        """
        Update sequence value from audio features
        
        Args:
            dt: Delta time in seconds
        """
        if not self.audio_analyzer or not self.audio_analyzer.is_running():
            return
        
        # Get audio features
        features = self.audio_analyzer.get_features()
        
        # Get band value (bass, mid, treble)
        band_value = features.get(self.band, 0.0)
        
        # Log audio feature detection
        if band_value > 0.01:  # Only log if significant
            logger.info(f"🎤 Audio detected: {self.band}={band_value:.3f} (beat={features.get('beat', False)})")
        
        audio_value = features.get(self.feature, band_value)
        
        # Handle beat feature (boolean -> float)
        if self.feature == 'beat':
            audio_value = 1.0 if audio_value else 0.0
        
        # Invert if requested
        if self.invert:
            audio_value = 1.0 - audio_value
        
        # Map to parameter range
        target_value = self.min_value + (audio_value * (self.max_value - self.min_value))
        
        # Smooth transition (exponential smoothing)
        if self.smoothing > 0:
            # Calculate alpha based on dt (time-based smoothing)
            alpha = 1.0 - np.exp(-dt / max(self.smoothing, 0.001))
            self._current_value += (target_value - self._current_value) * alpha
        else:
            self._current_value = target_value
    
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
            'direction': self.direction,
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
            direction=data.get('direction', 'rise_from_min'),
            attack_release=data.get('attack_release', 0.5)
        )
