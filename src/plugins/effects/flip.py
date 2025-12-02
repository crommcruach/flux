"""
Flip Effect Plugin - Flip Image Horizontally or Vertically
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class FlipEffect(PluginBase):
    """
    Flip Effect - Spiegelt das Bild horizontal oder vertikal.
    """
    
    METADATA = {
        'id': 'flip',
        'name': 'Flip',
        'description': 'Spiegelt das Bild horizontal oder vertikal',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'direction',
            'label': 'Richtung',
            'type': ParameterType.SELECT,
            'default': 'horizontal',
            'options': ['horizontal', 'vertical', 'both'],
            'description': 'Flip-Richtung (horizontal = links/rechts, vertical = oben/unten, both = beides)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Flip-Richtung."""
        self.direction = str(config.get('direction', 'horizontal'))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Flip auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Gespiegeltes Frame
        """
        if self.direction == 'horizontal':
            # Flip horizontal (links/rechts)
            flipped = cv2.flip(frame, 1)
        elif self.direction == 'vertical':
            # Flip vertical (oben/unten)
            flipped = cv2.flip(frame, 0)
        elif self.direction == 'both':
            # Flip both (horizontal + vertical = 180° rotation)
            flipped = cv2.flip(frame, -1)
        else:
            return frame
        
        return flipped
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'direction':
            self.direction = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'direction': self.direction
        }
