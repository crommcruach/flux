"""
Sharpen Effect Plugin - Image Sharpening Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SharpenEffect(PluginBase):
    """
    Sharpen Effect - Schärft das Bild durch Verstärkung von Kanten.
    """
    
    METADATA = {
        'id': 'sharpen',
        'name': 'Sharpen',
        'description': 'Schärft das Bild durch Kantenbetonung',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Enhance'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 5.0,
            'step': 0.1,
            'description': 'Schärfungs-Intensität (0 = Original, höher = schärfer)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Sharpen-Stärke."""
        self.strength = float(config.get('strength', 1.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Sharpen-Filter auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Geschärftes Frame
        """
        if self.strength <= 0.0:
            return frame
        
        # Unsharp Mask Technik: Original - Gaussian Blur = Kanten
        # Original + (Original - Blur) * strength = Geschärftes Bild
        
        # Berechne Blur mit kleinem Kernel
        blurred = cv2.GaussianBlur(frame, (0, 0), 3)
        
        # Berechne geschärftes Bild
        sharpened = cv2.addWeighted(frame, 1.0 + self.strength, blurred, -self.strength, 0)
        
        return sharpened
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'strength':
            self.strength = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'strength': self.strength
        }
