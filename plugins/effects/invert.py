"""
Invert RGB Effect Plugin - Channel-wise RGB inversion
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class InvertEffect(PluginBase):
    """
    Invert RGB Effect - Invertiert RGB-Kanäle (255 - pixel_value).
    """
    
    METADATA = {
        'id': 'invert',
        'name': 'Invert RGB',
        'description': 'Invertiert RGB-Kanäle (Negativ-Effekt)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'amount',
            'label': 'Amount',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Stärke der Invertierung (0 = original, 1 = voll invertiert)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Invert-Amount."""
        self.amount = config.get('amount', 1.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Invertiert RGB-Kanäle.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Invertiertes Frame
        """
        if self.amount < 0.01:
            return frame  # No inversion
        
        # Invert: 255 - pixel_value
        inverted = 255 - frame
        
        # Blend with original based on amount
        if self.amount < 0.99:
            result = cv2.addWeighted(frame, 1.0 - self.amount, inverted, self.amount, 0)
            return result
        else:
            return inverted
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'amount':
            self.amount = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'amount': self.amount}
