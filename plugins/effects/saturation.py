"""
Saturation Effect Plugin - Desaturation to grayscale
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SaturationEffect(PluginBase):
    """
    Saturation Effect - Entsättigung zu Graustufen.
    """
    
    METADATA = {
        'id': 'saturation',
        'name': 'Saturation',
        'description': 'Entsättigung zu Graustufen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'saturation',
            'label': 'Saturation',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Sättigung (0 = Graustufen, 1 = original, 2 = übersättigt)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Saturation-Wert."""
        self.saturation = config.get('saturation', 1.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Ändert die Sättigung des Frames.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit angepasster Sättigung
        """
        if abs(self.saturation - 1.0) < 0.01:
            return frame  # No change
        
        # OPTIMIZED: Convert to HSV (cvtColor returns uint8, no need for astype)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Adjust saturation (in-place with integer math)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.float32) * self.saturation, 0, 255).astype(np.uint8)
        
        # Convert back to BGR
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'saturation':
            self.saturation = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'saturation': self.saturation}
