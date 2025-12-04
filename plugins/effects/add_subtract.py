"""
AddSubtract Effect Plugin - Add/Subtract RGB values
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class AddSubtractEffect(PluginBase):
    """
    AddSubtract Effect - Addiert oder subtrahiert Werte von RGB-Kanälen.
    """
    
    METADATA = {
        'id': 'add_subtract',
        'name': 'Add/Subtract RGB',
        'description': 'Addiert oder subtrahiert Werte von RGB-Kanälen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'red',
            'label': 'Red',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -255.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Wert für Rot-Kanal addieren/subtrahieren'
        },
        {
            'name': 'green',
            'label': 'Green',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -255.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Wert für Grün-Kanal addieren/subtrahieren'
        },
        {
            'name': 'blue',
            'label': 'Blue',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -255.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Wert für Blau-Kanal addieren/subtrahieren'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit RGB-Werten."""
        self.red = config.get('red', 0.0)
        self.green = config.get('green', 0.0)
        self.blue = config.get('blue', 0.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Addiert/Subtrahiert Werte von RGB-Kanälen.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Modifiziertes Frame
        """
        # BGR-Format: Blue, Green, Red
        result = frame.astype(np.float32)
        result[:, :, 0] += self.blue  # Blue channel
        result[:, :, 1] += self.green  # Green channel
        result[:, :, 2] += self.red  # Red channel
        
        # Clamp to valid range [0, 255]
        result = np.clip(result, 0, 255).astype(np.uint8)
        return result
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'red':
            self.red = float(value)
            return True
        elif name == 'green':
            self.green = float(value)
            return True
        elif name == 'blue':
            self.blue = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'red': self.red,
            'green': self.green,
            'blue': self.blue
        }
