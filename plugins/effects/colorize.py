"""
Colorize Effect Plugin - Colorize image while preserving luminance
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ColorizeEffect(PluginBase):
    """
    Colorize Effect - Färbt das Bild ein, behält aber die Luminanz bei.
    """
    
    METADATA = {
        'id': 'colorize',
        'name': 'Colorize',
        'description': 'Färbt das Bild ein (behält Luminanz bei)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'hue',
            'label': 'Hue',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 180.0,
            'step': 1.0,
            'description': 'Ziel-Farbton (0-180 in OpenCV)'
        },
        {
            'name': 'saturation',
            'label': 'Saturation',
            'type': ParameterType.FLOAT,
            'default': 255.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Sättigung (0 = Graustufen, 255 = voll gesättigt)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Hue/Saturation-Werten."""
        self.hue = config.get('hue', 0.0)
        self.saturation = config.get('saturation', 255.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Färbt das Bild ein, behält Luminanz bei.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Colorisiertes Frame
        """
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Replace Hue and Saturation, keep Value (Luminance)
        hsv[:, :, 0] = int(self.hue)  # Set hue
        hsv[:, :, 1] = int(self.saturation)  # Set saturation
        # hsv[:, :, 2] stays unchanged (keeps luminance)
        
        # Convert back to BGR
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'hue':
            self.hue = float(value)
        elif name == 'saturation':
            self.saturation = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'hue': self.hue,
            'saturation': self.saturation
        }
