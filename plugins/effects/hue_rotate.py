"""
Hue Rotate Effect Plugin - Hue shift on HSV color space
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class HueRotateEffect(PluginBase):
    """
    Hue Rotate Effect - Verschiebt den Farbton (Hue) auf HSV-Basis.
    """
    
    METADATA = {
        'id': 'hue_rotate',
        'name': 'Hue Rotate',
        'description': 'Verschiebt den Farbton (Hue) auf HSV-Basis',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'hue_shift',
            'label': 'Hue Shift',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -180.0,
            'max': 180.0,
            'step': 1.0,
            'description': 'Farbton-Verschiebung in Grad (-180 bis +180)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Hue-Shift."""
        self.hue_shift = config.get('hue_shift', 0.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Verschiebt den Hue-Wert auf HSV-Basis.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit verschobenem Hue
        """
        if abs(self.hue_shift) < 0.1:
            return frame  # No shift, return original
        
        # Convert BGR to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        
        # Shift hue (OpenCV uses 0-180 range for hue)
        # Convert our -180 to +180 range to 0-180 OpenCV range
        hsv[:, :, 0] = (hsv[:, :, 0] + self.hue_shift / 2.0) % 180
        
        # Convert back to uint8 and BGR
        hsv = hsv.astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'hue_shift':
            self.hue_shift = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'hue_shift': self.hue_shift}
