"""
Solarize Effect Plugin - Invert Colors Above Threshold
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SolarizeEffect(PluginBase):
    """
    Solarize Effect - Invertiert Farben oberhalb eines Schwellwerts.
    """
    
    METADATA = {
        'id': 'solarize',
        'name': 'Solarize',
        'description': 'Invertiert Farben oberhalb eines Schwellwerts (Foto-Überbelichtung-Effekt)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Artistic'
    }
    
    PARAMETERS = [
        {
            'name': 'threshold',
            'label': 'Schwellwert',
            'type': ParameterType.INT,
            'default': 128,
            'min': 0,
            'max': 255,
            'step': 5,
            'description': 'Helligkeits-Schwellwert (Werte darüber werden invertiert)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Threshold."""
        self.threshold = int(config.get('threshold', 128))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Solarize-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Solarisiertes Frame
        """
        # Erstelle Maske für Pixel über Threshold
        mask = frame > self.threshold
        
        # Invertiere nur die Pixel über Threshold
        result = frame.copy()
        result[mask] = 255 - result[mask]
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'threshold':
            self.threshold = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'threshold': self.threshold
        }
