"""
Pixelate Effect Plugin - LoRez Pixel Art Look
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class PixelateEffect(PluginBase):
    """
    Pixelate Effect - Erzeugt Pixelation/LoRez Effekt.
    """
    
    METADATA = {
        'id': 'pixelate',
        'name': 'Pixelate',
        'description': 'Pixelation/LoRez Effekt für Retro-Look',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur & Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'block_size',
            'label': 'Blockgröße',
            'type': ParameterType.INT,
            'default': 10,
            'min': 2,
            'max': 100,
            'description': 'Größe der Pixelblöcke in Pixeln'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Pixelate Parametern."""
        self.block_size = int(config.get('block_size', 10))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Pixelate auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Pixelated Frame
        """
        if self.block_size < 2:
            return frame
        
        h, w = frame.shape[:2]
        
        # Downscale zu niedrigerer Auflösung
        small_w = max(1, w // self.block_size)
        small_h = max(1, h // self.block_size)
        
        # Resize down (Nearest Neighbor für harte Kanten)
        small = cv2.resize(frame, (small_w, small_h), 
                          interpolation=cv2.INTER_NEAREST)
        
        # Resize back up (Nearest Neighbor für Blockeffekt)
        pixelated = cv2.resize(small, (w, h), 
                              interpolation=cv2.INTER_NEAREST)
        
        return pixelated
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'block_size':
            self.block_size = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'block_size': self.block_size
        }
