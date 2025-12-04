"""
Mosaic Effect Plugin - Pixelated Mosaic Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class MosaicEffect(PluginBase):
    """
    Mosaic Effect - Erzeugt Mosaik/Pixelation-Effekt.
    """
    
    METADATA = {
        'id': 'mosaic',
        'name': 'Mosaic',
        'description': 'Pixelation/Mosaik-Effekt mit konfigurierbarer Blockgröße',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'block_size',
            'label': 'Blockgröße',
            'type': ParameterType.INT,
            'default': 10,
            'min': 2,
            'max': 50,
            'step': 2,
            'description': 'Größe der Mosaik-Blöcke in Pixeln'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Block-Größe."""
        self.block_size = int(config.get('block_size', 10))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Mosaik-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Mosaikiertes Frame
        """
        if self.block_size <= 1:
            return frame
        
        h, w = frame.shape[:2]
        
        # Berechne neue Dimensionen (reduziert)
        small_h = max(1, h // self.block_size)
        small_w = max(1, w // self.block_size)
        
        # Verkleinere Bild
        small = cv2.resize(frame, (small_w, small_h), interpolation=cv2.INTER_LINEAR)
        
        # Vergrößere zurück mit Nearest Neighbor für Pixelation-Effekt
        mosaic = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        
        return mosaic
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'block_size':
            self.block_size = max(2, int(value))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'block_size': self.block_size
        }
