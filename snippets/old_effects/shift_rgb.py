"""
Shift RGB Effect Plugin - Chromatic Aberration Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ShiftRGBEffect(PluginBase):
    """
    Shift RGB Effect - RGB-Kanal-Verschiebung für chromatische Aberration.
    """
    
    METADATA = {
        'id': 'shift_rgb',
        'name': 'Shift RGB',
        'description': 'RGB-Kanal-Verschiebung für chromatische Aberration',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Glitch & Noise'
    }
    
    PARAMETERS = [
        {
            'name': 'red_x',
            'label': 'Rot X',
            'type': ParameterType.INT,
            'default': 5,
            'min': -50,
            'max': 50,
            'description': 'Horizontale Verschiebung des Rot-Kanals in Pixeln'
        },
        {
            'name': 'red_y',
            'label': 'Rot Y',
            'type': ParameterType.INT,
            'default': 0,
            'min': -50,
            'max': 50,
            'description': 'Vertikale Verschiebung des Rot-Kanals in Pixeln'
        },
        {
            'name': 'green_x',
            'label': 'Grün X',
            'type': ParameterType.INT,
            'default': 0,
            'min': -50,
            'max': 50,
            'description': 'Horizontale Verschiebung des Grün-Kanals in Pixeln'
        },
        {
            'name': 'green_y',
            'label': 'Grün Y',
            'type': ParameterType.INT,
            'default': 0,
            'min': -50,
            'max': 50,
            'description': 'Vertikale Verschiebung des Grün-Kanals in Pixeln'
        },
        {
            'name': 'blue_x',
            'label': 'Blau X',
            'type': ParameterType.INT,
            'default': -5,
            'min': -50,
            'max': 50,
            'description': 'Horizontale Verschiebung des Blau-Kanals in Pixeln'
        },
        {
            'name': 'blue_y',
            'label': 'Blau Y',
            'type': ParameterType.INT,
            'default': 0,
            'min': -50,
            'max': 50,
            'description': 'Vertikale Verschiebung des Blau-Kanals in Pixeln'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Shift RGB Parametern."""
        self.red_x = int(config.get('red_x', 5))
        self.red_y = int(config.get('red_y', 0))
        self.green_x = int(config.get('green_x', 0))
        self.green_y = int(config.get('green_y', 0))
        self.blue_x = int(config.get('blue_x', -5))
        self.blue_y = int(config.get('blue_y', 0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet RGB Shift auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit verschobenen RGB-Kanälen
        """
        h, w = frame.shape[:2]
        
        # Splitte in BGR-Kanäle
        b, g, r = cv2.split(frame)
        
        # Erstelle Verschiebungs-Matrizen
        # Translation Matrix: [[1, 0, tx], [0, 1, ty]]
        
        # Rot-Kanal verschieben
        if self.red_x != 0 or self.red_y != 0:
            M_r = np.float32([[1, 0, self.red_x], [0, 1, self.red_y]])
            r = cv2.warpAffine(r, M_r, (w, h), borderMode=cv2.BORDER_WRAP)
        
        # Grün-Kanal verschieben
        if self.green_x != 0 or self.green_y != 0:
            M_g = np.float32([[1, 0, self.green_x], [0, 1, self.green_y]])
            g = cv2.warpAffine(g, M_g, (w, h), borderMode=cv2.BORDER_WRAP)
        
        # Blau-Kanal verschieben
        if self.blue_x != 0 or self.blue_y != 0:
            M_b = np.float32([[1, 0, self.blue_x], [0, 1, self.blue_y]])
            b = cv2.warpAffine(b, M_b, (w, h), borderMode=cv2.BORDER_WRAP)
        
        # Merge zurück zu BGR
        result = cv2.merge([b, g, r])
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'red_x':
            self.red_x = int(value)
            return True
        elif name == 'red_y':
            self.red_y = int(value)
            return True
        elif name == 'green_x':
            self.green_x = int(value)
            return True
        elif name == 'green_y':
            self.green_y = int(value)
            return True
        elif name == 'blue_x':
            self.blue_x = int(value)
            return True
        elif name == 'blue_y':
            self.blue_y = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'red_x': self.red_x,
            'red_y': self.red_y,
            'green_x': self.green_x,
            'green_y': self.green_y,
            'blue_x': self.blue_x,
            'blue_y': self.blue_y
        }
