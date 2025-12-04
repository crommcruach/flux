"""
Tint Effect Plugin - Tint image with base color
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class TintEffect(PluginBase):
    """
    Tint Effect - Färbt das Bild mit einer Basisfarbe ein.
    """
    
    METADATA = {
        'id': 'tint',
        'name': 'Tint',
        'description': 'Färbt das Bild mit einer Basisfarbe ein',
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
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Rot-Anteil (0.0 - 1.0)'
        },
        {
            'name': 'green',
            'label': 'Green',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Grün-Anteil (0.0 - 1.0)'
        },
        {
            'name': 'blue',
            'label': 'Blue',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Blau-Anteil (0.0 - 1.0)'
        },
        {
            'name': 'amount',
            'label': 'Amount',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Stärke des Tint-Effekts'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Tint-Farbe."""
        self.red = config.get('red', 1.0)
        self.green = config.get('green', 1.0)
        self.blue = config.get('blue', 1.0)
        self.amount = config.get('amount', 0.5)
    
    def process_frame(self, frame, **kwargs):
        """
        Färbt das Bild mit einer Basisfarbe ein.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Getintetes Frame
        """
        if self.amount < 0.01:
            return frame  # No tint
        
        # Create tint multiplier (BGR format)
        tint = np.array([self.blue, self.green, self.red], dtype=np.float32)
        
        # Apply tint
        tinted = frame.astype(np.float32) * tint
        tinted = np.clip(tinted, 0, 255).astype(np.uint8)
        
        # Blend with original based on amount
        if self.amount < 0.99:
            result = cv2.addWeighted(frame, 1.0 - self.amount, tinted, self.amount, 0)
            return result
        else:
            return tinted
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'red':
            self.red = float(value)
        elif name == 'green':
            self.green = float(value)
        elif name == 'blue':
            self.blue = float(value)
        elif name == 'amount':
            self.amount = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'amount': self.amount
        }
