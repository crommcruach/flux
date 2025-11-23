"""
Exposure Effect Plugin - Exposure curve using LUT
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ExposureEffect(PluginBase):
    """
    Exposure Effect - Exposure-Kurve mit Lookup Table (LUT).
    """
    
    METADATA = {
        'id': 'exposure',
        'name': 'Exposure',
        'description': 'Exposure-Anpassung mit Lookup Table',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'exposure',
            'label': 'Exposure',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -3.0,
            'max': 3.0,
            'step': 0.1,
            'description': 'Exposure-Wert (-3 = sehr dunkel, +3 = sehr hell)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Exposure-Wert."""
        self.exposure = config.get('exposure', 0.0)
        self._update_lut()
    
    def _update_lut(self):
        """Erstellt Lookup Table basierend auf Exposure-Wert."""
        # Exposure formula: output = input * 2^exposure
        multiplier = 2.0 ** self.exposure
        self.lut = np.clip(np.arange(256) * multiplier, 0, 255).astype(np.uint8)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Exposure-Kurve auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit angepasster Exposure
        """
        if abs(self.exposure) < 0.01:
            return frame  # No exposure change
        
        return cv2.LUT(frame, self.lut)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'exposure':
            self.exposure = float(value)
            self._update_lut()
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'exposure': self.exposure}
