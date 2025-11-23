"""
Posterize Effect Plugin - Color reduction using bit-shift
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class PosterizeEffect(PluginBase):
    """
    Posterize Effect - Reduziert Farbanzahl durch Bit-Shift.
    """
    
    METADATA = {
        'id': 'posterize',
        'name': 'Posterize',
        'description': 'Reduziert Farbanzahl (Poster-Effekt)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'levels',
            'label': 'Levels',
            'type': ParameterType.FLOAT,
            'default': 8.0,
            'min': 2.0,
            'max': 256.0,
            'step': 1.0,
            'description': 'Anzahl der Farbstufen pro Kanal (weniger = stärker posterisiert)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Levels-Wert."""
        self.levels = config.get('levels', 8.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Reduziert Farbanzahl durch Quantisierung.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Posterisiertes Frame
        """
        if self.levels >= 256:
            return frame  # No posterization
        
        # Calculate step size
        levels = max(2, int(self.levels))
        step = 255.0 / (levels - 1)
        
        # Quantize colors
        result = np.floor(frame.astype(np.float32) / step) * step
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'levels':
            self.levels = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'levels': self.levels}
