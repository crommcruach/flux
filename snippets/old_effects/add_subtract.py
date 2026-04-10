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
        # Use _get_param_value() from PluginBase to handle range metadata
        self.red = self._get_param_value('red', 0.0)
        self.green = self._get_param_value('green', 0.0)
        self.blue = self._get_param_value('blue', 0.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Addiert/Subtrahiert Werte von RGB-Kanälen.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Modifiziertes Frame
        """
        # Throttled logging every 120 frames
        if not hasattr(self, '_process_counter'):
            self._process_counter = 0
        self._process_counter += 1
        if self._process_counter % 120 == 1:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"🎨 [AddSubtract {id(self)}] R={self.red}, G={self.green}, B={self.blue}")
            logger.info(f"🖼️  [AddSubtract] Input frame shape={frame.shape}, mean={frame.mean():.1f}")
        
        # RGB-Format: Red, Green, Blue
        result = frame.astype(np.float32)
        result[:, :, 0] += self.red  # Red channel
        result[:, :, 1] += self.green  # Green channel
        result[:, :, 2] += self.blue  # Blue channel
        
        # Clamp to valid range [0, 255]
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        if self._process_counter % 120 == 1:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ [AddSubtract] Output frame mean={result.mean():.1f}, changed={(frame.mean() - result.mean()):.1f}")
        
        return result
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
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
