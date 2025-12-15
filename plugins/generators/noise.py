"""
Noise Generator Plugin - Various noise patterns
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class NoiseGenerator(PluginBase):
    """Noise Generator - White noise, Perlin-like noise patterns."""
    
    METADATA = {
        'id': 'noise',
        'name': 'Noise',
        'description': 'Noise pattern generator',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'noise_type',
            'label': 'Noise Type',
            'type': ParameterType.SELECT,
            'default': 'white',
            'options': ['white', 'smooth', 'colored'],
            'description': 'Type of noise pattern'
        },
        {
            'name': 'scale',
            'label': 'Scale',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Noise scale/frequency'
        },
        {
            'name': 'animated',
            'label': 'Animated',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Animate noise over time'
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
        self.noise_type = config.get('noise_type', 'white')
        self.scale = float(config.get('scale', 1.0))
        self.animated = bool(config.get('animated', True))
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
        self.time = 0.0
        self.noise_seed = 0
    
    def _generate_white_noise(self, height, width):
        """Generate white noise."""
        return np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
    
    def _generate_smooth_noise(self, height, width, scale):
        """Generate smooth noise using downsampling."""
        # Generate small noise
        small_h = max(2, int(height / (scale * 10)))
        small_w = max(2, int(width / (scale * 10)))
        small_noise = np.random.randint(0, 256, (small_h, small_w, 3), dtype=np.uint8)
        
        # Upscale with interpolation
        smooth = cv2.resize(small_noise, (width, height), interpolation=cv2.INTER_LINEAR)
        return smooth
    
    def _generate_colored_noise(self, height, width, time_offset):
        """Generate colored noise with shifting hues."""
        # Create noise pattern
        noise = np.random.rand(height, width)
        
        # Convert to HSV color space
        hue = ((noise * 180) + time_offset * 50) % 180
        saturation = np.ones((height, width)) * 255
        value = (noise * 255).astype(np.uint8)
        
        hsv = np.stack([hue.astype(np.uint8), saturation.astype(np.uint8), value], axis=-1)
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return bgr
    
    def process_frame(self, frame, **kwargs):
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        self.time = time
        
        # Update random seed for animation
        if self.animated:
            self.noise_seed = int(time * 30)  # 30 fps equivalent
            np.random.seed(self.noise_seed)
        
        # Generate noise based on type
        if self.noise_type == 'white':
            frame = self._generate_white_noise(height, width)
        elif self.noise_type == 'smooth':
            frame = self._generate_smooth_noise(height, width, self.scale)
        elif self.noise_type == 'colored':
            frame = self._generate_colored_noise(height, width, time if self.animated else 0)
        else:
            frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'noise_type':
            if value in ['white', 'smooth', 'colored']:
                self.noise_type = value
                return True
        elif name == 'scale':
            self.scale = max(0.1, min(10.0, float(value)))
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
            'noise_type': self.noise_type,
            'scale': self.scale,
            'animated': self.animated,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
