"""
LFO Sequence

Low Frequency Oscillator for parameter modulation.
"""

import math
import numpy as np
import logging
from typing import Dict, Any
from .base import BaseSequence

logger = logging.getLogger(__name__)


class LFOSequence(BaseSequence):
    """Low Frequency Oscillator"""
    
    WAVEFORMS = ['sine', 'square', 'triangle', 'sawtooth', 'random']
    
    def __init__(self, sequence_id: str, target_parameter: str, waveform: str = 'sine',
                 frequency: float = 1.0, amplitude: float = 1.0, offset: float = 0.0,
                 phase: float = 0.0, min_value: float = 0.0, max_value: float = 1.0):
        """
        Initialize LFO sequence
        
        Args:
            sequence_id: Unique ID
            target_parameter: Target parameter path
            waveform: Waveform type ('sine', 'square', 'triangle', 'sawtooth', 'random')
            frequency: Frequency in Hz
            amplitude: Amplitude (0-1)
            offset: DC offset (-1 to 1)
            phase: Phase offset (0-1, where 1 = 360°)
            min_value: Minimum output value
            max_value: Maximum output value
        """
        super().__init__(sequence_id, 'lfo', target_parameter)
        
        self.waveform = waveform
        self.frequency = frequency
        self.amplitude = amplitude
        self.offset = offset
        self.phase = phase
        self.min_value = min_value
        self.max_value = max_value
        
        self._time = 0.0
        self._last_random = 0.0
        self._last_step_time = 0.0
        
        if waveform not in self.WAVEFORMS:
            logger.warning(f"Unknown waveform: {waveform}, defaulting to 'sine'")
            self.waveform = 'sine'
    
    def update(self, dt: float):
        """
        Update oscillator time
        
        Args:
            dt: Delta time in seconds
        """
        self._time += dt
    
    def get_value(self) -> float:
        """Calculate current oscillator value"""
        # Calculate phase-adjusted time (0-1 normalized)
        t = (self._time * self.frequency + self.phase) % 1.0
        
        # Generate waveform
        if self.waveform == 'sine':
            wave = math.sin(t * 2 * math.pi)
        
        elif self.waveform == 'square':
            wave = 1.0 if t < 0.5 else -1.0
        
        elif self.waveform == 'triangle':
            # Triangle: -1 to 1 and back
            wave = 1.0 - 4.0 * abs(t - 0.5)
        
        elif self.waveform == 'sawtooth':
            # Sawtooth: ramp from -1 to 1
            wave = 2.0 * t - 1.0
        
        elif self.waveform == 'random':
            # Stepped random (changes at frequency rate)
            current_step = int(self._time * self.frequency)
            last_step = int((self._time - 0.001) * self.frequency)
            
            if current_step != last_step:
                self._last_random = np.random.uniform(-1, 1)
            
            wave = self._last_random
        
        else:
            wave = 0.0
        
        # Apply amplitude and offset
        value = wave * self.amplitude + self.offset
        
        # Map from -1..1 to 0..1
        normalized = (value + 1.0) / 2.0
        
        # Map to parameter range
        return self.min_value + (normalized * (self.max_value - self.min_value))
    
    def reset(self):
        """Reset oscillator time"""
        self._time = 0.0
        self._last_random = 0.0
    
    def serialize(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            'id': self.id,
            'type': self.type,
            'name': self.name,
            'target_parameter': self.target_parameter,
            'waveform': self.waveform,
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'offset': self.offset,
            'phase': self.phase,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'enabled': self.enabled
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'LFOSequence':
        """Create from dictionary"""
        return cls(
            sequence_id=data.get('id'),
            target_parameter=data.get('target_parameter'),
            waveform=data.get('waveform', 'sine'),
            frequency=data.get('frequency', 1.0),
            amplitude=data.get('amplitude', 1.0),
            offset=data.get('offset', 0.0),
            phase=data.get('phase', 0.0),
            min_value=data.get('min_value', 0.0),
            max_value=data.get('max_value', 1.0)
        )
