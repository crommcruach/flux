"""
Rainbow Wave Generator Plugin - Horizontal rainbow wave effect
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class RainbowWaveGenerator(PluginBase):
    """
    Rainbow Wave Generator - Horizontale Regenbogen-Welle.
    
    Erzeugt eine sich bewegende Regenbogen-Welle.
    """
    
    METADATA = {
        'id': 'rainbow_wave',
        'name': 'Rainbow Wave',
        'description': 'Horizontale Regenbogen-Welle',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }
    
    PARAMETERS = [
        {
            'name': 'speed',
            'label': 'Speed',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Wave movement speed'
        },
        {
            'name': 'wave_length',
            'label': 'Wave Length',
            'type': ParameterType.FLOAT,
            'default': 60.0,
            'min': 10.0,
            'max': 200.0,
            'step': 1.0,
            'description': 'Length of rainbow wave in pixels'
        },
        {
            'name': 'vertical',
            'label': 'Vertical',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Vertical orientation (instead of horizontal)'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.speed = config.get('speed', 2.0)
        self.wave_length = config.get('wave_length', 60.0)
        self.vertical = config.get('vertical', False)
        self.duration = config.get('duration', 10)
        self.time = 0.0
    
    def _hsv_to_rgb_vectorized(self, h, s, v):
        """Schnelle HSV zu RGB Konvertierung (vektorisiert)."""
        i = (h * 6.0).astype(int)
        f = (h * 6.0) - i
        
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        
        i = i % 6
        
        r = np.choose(i, [v, q, p, p, t, v])
        g = np.choose(i, [t, v, v, q, p, p])
        b = np.choose(i, [p, p, t, v, v, q])
        
        return r, g, b
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Rainbow Wave Frame.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height', 'time' enthalten
            
        Returns:
            Generated frame
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        # Update internal time if not provided
        if 'time' not in kwargs:
            self.time += 1.0 / 30.0
            time = self.time
        
        # Berechne Hue-Offset basierend auf Zeit
        offset = (time * self.speed) % 1.0
        
        if self.vertical:
            # Vertical rainbow wave
            coords = np.arange(height, dtype=np.float32)
            hue = (coords / self.wave_length + offset) % 1.0
            r, g, b = self._hsv_to_rgb_vectorized(hue, 1.0, 1.0)
            frame_col = np.stack([r * 255, g * 255, b * 255], axis=-1).astype(np.uint8)
            frame = np.tile(frame_col[:, np.newaxis, :], (1, width, 1))
        else:
            # Horizontal rainbow wave
            coords = np.arange(width, dtype=np.float32)
            hue = (coords / self.wave_length + offset) % 1.0
            r, g, b = self._hsv_to_rgb_vectorized(hue, 1.0, 1.0)
            frame_row = np.stack([r * 255, g * 255, b * 255], axis=-1).astype(np.uint8)
            frame = np.tile(frame_row, (height, 1, 1))
        
        return frame
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'speed':
            self.speed = float(value)
            return True
        elif name == 'wave_length':
            self.wave_length = float(value)
            return True
        elif name == 'vertical':
            self.vertical = bool(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'speed': self.speed,
            'wave_length': self.wave_length,
            'vertical': self.vertical
        }
