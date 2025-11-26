"""
Pulse Generator Plugin - Pulsing solid color effect
"""
import numpy as np
import math
from plugins import PluginBase, PluginType, ParameterType


class PulseGenerator(PluginBase):
    """
    Pulse Generator - Pulsierende Vollfarbe.
    
    Einfaches pulsierendes Farbfeld mit konfigurierbarer Frequenz.
    """
    
    METADATA = {
        'id': 'pulse',
        'name': 'Pulse',
        'description': 'Pulsierende Vollfarbe mit Farbrotation',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }
    
    PARAMETERS = [
        {
            'name': 'frequency',
            'label': 'Pulse Frequency',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Pulse frequency in Hz'
        },
        {
            'name': 'min_brightness',
            'label': 'Min Brightness',
            'type': ParameterType.FLOAT,
            'default': 0.3,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Minimum brightness (0-1)'
        },
        {
            'name': 'max_brightness',
            'label': 'Max Brightness',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Maximum brightness (0-1)'
        },
        {
            'name': 'hue_rotation',
            'label': 'Hue Rotation Speed',
            'type': ParameterType.FLOAT,
            'default': 0.2,
            'min': 0.0,
            'max': 2.0,
            'step': 0.05,
            'description': 'Color rotation speed'
        },
        {
            'name': 'saturation',
            'label': 'Saturation',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Color saturation (0-1)'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 5,
            'max': 600,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.frequency = config.get('frequency', 2.0)
        self.min_brightness = config.get('min_brightness', 0.3)
        self.max_brightness = config.get('max_brightness', 1.0)
        self.hue_rotation = config.get('hue_rotation', 0.2)
        self.saturation = config.get('saturation', 1.0)
        self.duration = config.get('duration', 30)
        self.time = 0.0
    
    def _hsv_to_rgb(self, h, s, v):
        """Konvertiert HSV zu RGB."""
        import colorsys
        return colorsys.hsv_to_rgb(h, s, v)
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Pulse Frame.
        
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
        
        # Berechne pulsierende Helligkeit
        brightness_range = self.max_brightness - self.min_brightness
        brightness = self.min_brightness + brightness_range * (0.5 + 0.5 * math.sin(time * self.frequency * 2 * math.pi))
        
        # Rotiere durch Farben
        hue = (time * self.hue_rotation) % 1.0
        
        # Konvertiere zu RGB
        r, g, b = self._hsv_to_rgb(hue, self.saturation, brightness)
        
        # Erstelle Frame mit einzelner Farbe
        frame = np.full((height, width, 3), 
                        [int(r * 255), int(g * 255), int(b * 255)], 
                        dtype=np.uint8)
        
        return frame
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'frequency':
            self.frequency = float(value)
            return True
        elif name == 'min_brightness':
            self.min_brightness = float(value)
            return True
        elif name == 'max_brightness':
            self.max_brightness = float(value)
            return True
        elif name == 'hue_rotation':
            self.hue_rotation = float(value)
            return True
        elif name == 'saturation':
            self.saturation = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'frequency': self.frequency,
            'min_brightness': self.min_brightness,
            'max_brightness': self.max_brightness,
            'hue_rotation': self.hue_rotation,
            'saturation': self.saturation
        }
