"""
Oscillator Generator Plugin - Generates waveform visualizations
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class OscillatorGenerator(PluginBase):
    """Oscillator Generator - Sine, square, sawtooth, triangle waveforms."""
    
    METADATA = {
        'id': 'oscillator',
        'name': 'Oscillator',
        'description': 'Waveform generator (sine, square, sawtooth, triangle)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'waveform',
            'label': 'Waveform',
            'type': ParameterType.SELECT,
            'default': 'sine',
            'options': ['sine', 'square', 'sawtooth', 'triangle'],
            'description': 'Waveform type'
        },
        {
            'name': 'frequency',
            'label': 'Frequency',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Wave frequency'
        },
        {
            'name': 'amplitude',
            'label': 'Amplitude',
            'type': ParameterType.FLOAT,
            'default': 0.8,
            'min': 0.1,
            'max': 1.0,
            'step': 0.1,
            'description': 'Wave amplitude (0.1-1.0)'
        },
        {
            'name': 'line_count',
            'label': 'Line Count',
            'type': ParameterType.INT,
            'default': 3,
            'min': 1,
            'max': 10,
            'step': 1,
            'description': 'Number of waveform lines'
        },
        {
            'name': 'line_width',
            'label': 'Line Width',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 10,
            'step': 1,
            'description': 'Line thickness'
        },
        {
            'name': 'animated',
            'label': 'Animated',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Animate waveform over time'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.STRING,
            'default': '10',
            'description': 'Playback duration in seconds (1-60)'
        }
    ]
    
    def initialize(self, config):
        self.waveform = config.get('waveform', 'sine')
        self.frequency = float(config.get('frequency', 1.0))
        self.amplitude = float(config.get('amplitude', 0.8))
        self.line_count = int(config.get('line_count', 3))
        self.line_width = int(config.get('line_width', 2))
        self.animated = bool(config.get('animated', True))
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
        self.time = 0.0
    
    def _generate_waveform(self, x, phase=0.0):
        """Generate waveform values based on type."""
        x = x * self.frequency + phase
        
        if self.waveform == 'sine':
            return np.sin(x * 2 * np.pi)
        elif self.waveform == 'square':
            return np.sign(np.sin(x * 2 * np.pi))
        elif self.waveform == 'sawtooth':
            return 2 * (x % 1.0) - 1
        elif self.waveform == 'triangle':
            return 2 * np.abs(2 * (x % 1.0) - 1) - 1
        return np.zeros_like(x)
    
    def process_frame(self, frame, **kwargs):
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        self.time = time
        
        # Create black canvas
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Generate waveform
        x = np.linspace(0, 1, width)
        
        # Draw multiple lines
        for line_idx in range(self.line_count):
            # Calculate vertical position for this line
            line_y = int((line_idx + 0.5) * height / self.line_count)
            
            # Phase shift for animation
            phase = time * self.frequency if self.animated else 0.0
            phase += line_idx * 0.2  # Offset each line slightly
            
            # Generate waveform
            wave = self._generate_waveform(x, phase)
            
            # Scale and offset wave
            y_offset = int(self.amplitude * height / (2 * self.line_count))
            y_values = line_y + (wave * y_offset).astype(int)
            y_values = np.clip(y_values, 0, height - 1)
            
            # Color gradient based on line index
            hue = (line_idx / max(1, self.line_count - 1)) * 180
            color_hsv = np.uint8([[[hue, 255, 255]]])
            color_bgr = cv2.cvtColor(color_hsv, cv2.COLOR_HSV2BGR)[0, 0]
            color = tuple(map(int, color_bgr))
            
            # Draw waveform
            for i in range(width - 1):
                pt1 = (i, y_values[i])
                pt2 = (i + 1, y_values[i + 1])
                cv2.line(frame, pt1, pt2, color, self.line_width)
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'waveform':
            if value in ['sine', 'square', 'sawtooth', 'triangle']:
                self.waveform = value
                return True
        elif name == 'frequency':
            self.frequency = max(0.1, min(10.0, float(value)))
            return True
        elif name == 'amplitude':
            self.amplitude = max(0.1, min(1.0, float(value)))
            return True
        elif name == 'line_count':
            self.line_count = max(1, min(10, int(value)))
            return True
        elif name == 'line_width':
            self.line_width = max(1, min(10, int(value)))
            return True
        elif name == 'animated':
            self.animated = bool(value)
            return True
        elif name == 'duration':
            try:
                self.duration = max(1, min(60, float(value)))
            except (ValueError, TypeError):
                self.duration = 10
            return True
        return False
    
    def get_parameters(self):
        return {
            'waveform': self.waveform,
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'line_count': self.line_count,
            'line_width': self.line_width,
            'animated': self.animated,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
