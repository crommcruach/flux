"""
Threshold Effect Plugin - 2-color image using threshold
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ThresholdEffect(PluginBase):
    """
    Threshold Effect - Erstellt 2-Farben-Bild mit Schwellenwert.
    """
    
    METADATA = {
        'id': 'threshold',
        'name': 'Threshold',
        'description': 'Erstellt 2-Farben-Bild mit Schwellenwert',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'threshold',
            'label': 'Threshold',
            'type': ParameterType.FLOAT,
            'default': 127.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Schwellenwert (Pixel < Threshold = Schwarz, >= Threshold = Weiß)'
        },
        {
            'name': 'mode',
            'label': 'Mode',
            'type': ParameterType.SELECT,
            'default': 'binary',
            'options': ['binary', 'binary_inv', 'adaptive'],
            'description': 'Threshold-Modus'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Threshold-Wert."""
        self.threshold = config.get('threshold', 127.0)
        self.mode = config.get('mode', 'binary')
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Threshold auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Thresholded Frame
        """
        # Convert to grayscale first
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        if self.mode == 'binary':
            _, thresholded = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        elif self.mode == 'binary_inv':
            _, thresholded = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY_INV)
        elif self.mode == 'adaptive':
            thresholded = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
        else:
            _, thresholded = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        
        # Convert back to BGR (grayscale as color)
        return cv2.cvtColor(thresholded, cv2.COLOR_GRAY2BGR)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'threshold':
            self.threshold = float(value)
        elif name == 'mode':
            self.mode = str(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'threshold': self.threshold,
            'mode': self.mode
        }
