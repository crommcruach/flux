"""
Blur Effect Plugin - Gaussian Blur Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class BlurEffect(PluginBase):
    """
    Gaussian Blur Effect - Verwischt das Bild mit konfigurierbarer Stärke.
    """
    
    METADATA = {
        'id': 'blur',
        'name': 'Gaussian Blur',
        'description': 'Verwischt das Bild mit Gaussian Blur',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur/Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Blur Stärke',
            'type': ParameterType.FLOAT,
            'default': 5.0,
            'min': 0.0,
            'max': 20.0,
            'step': 0.5,
            'description': 'Stärke des Blur-Effekts (höher = stärker verwischt)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Blur-Stärke."""
        self.strength = config.get('strength', 5.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Gaussian Blur auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Geblurrtes Frame
        """
        if self.strength == 0:
            return frame  # No blur
        
        # Kernel Size muss ungerade sein
        kernel_size = int(self.strength) * 2 + 1
        kernel_size = max(1, kernel_size)  # Mindestens 1
        
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
    
    def update_parameter(self, name, value):
        """Aktualisiert Blur-Stärke."""
        if name == 'strength':
            self.strength = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Blur-Stärke zurück."""
        return {'strength': self.strength}
