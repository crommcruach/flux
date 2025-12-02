"""
Slide Effect Plugin - Shift Image Position
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SlideEffect(PluginBase):
    """
    Slide Effect - Verschiebt das Bild horizontal oder vertikal mit Wrap-Around.
    """
    
    METADATA = {
        'id': 'slide',
        'name': 'Slide',
        'description': 'Verschiebt das Bild mit Wrap-Around (endlose Verschiebung)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'x_offset',
            'label': 'X-Verschiebung',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -100.0,
            'max': 100.0,
            'step': 1.0,
            'description': 'Horizontale Verschiebung in % der Bildbreite (-100 bis +100)'
        },
        {
            'name': 'y_offset',
            'label': 'Y-Verschiebung',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -100.0,
            'max': 100.0,
            'step': 1.0,
            'description': 'Vertikale Verschiebung in % der Bildhöhe (-100 bis +100)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Slide-Parametern."""
        self.x_offset = float(config.get('x_offset', 0.0))
        self.y_offset = float(config.get('y_offset', 0.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Slide-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verschobenes Frame mit Wrap-Around
        """
        if abs(self.x_offset) < 0.1 and abs(self.y_offset) < 0.1:
            return frame
        
        h, w = frame.shape[:2]
        
        # Berechne Pixel-Verschiebung aus Prozent
        shift_x = int(w * self.x_offset / 100.0)
        shift_y = int(h * self.y_offset / 100.0)
        
        # Wrap-Around mit numpy roll
        shifted = np.roll(frame, shift_x, axis=1)  # Horizontal shift
        shifted = np.roll(shifted, shift_y, axis=0)  # Vertical shift
        
        return shifted
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'x_offset':
            self.x_offset = float(value)
            return True
        elif name == 'y_offset':
            self.y_offset = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'x_offset': self.x_offset,
            'y_offset': self.y_offset
        }
