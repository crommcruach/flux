"""
Rotate Effect Plugin - Image Rotation Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class RotateEffect(PluginBase):
    """
    Rotate Effect - Rotiert das Bild um einen Winkel.
    """
    
    METADATA = {
        'id': 'rotate',
        'name': 'Rotate',
        'description': 'Rotiert das Bild um einen konfigurierbaren Winkel',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'angle',
            'label': 'Winkel (°)',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -180.0,
            'max': 180.0,
            'step': 5.0,
            'description': 'Rotationswinkel in Grad (negativ = gegen Uhrzeigersinn)'
        },
        {
            'name': 'center_x',
            'label': 'Zentrum X (%)',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Horizontale Position des Rotationszentrums (0-100%)'
        },
        {
            'name': 'center_y',
            'label': 'Zentrum Y (%)',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Vertikale Position des Rotationszentrums (0-100%)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Rotations-Parametern."""
        self.angle = float(config.get('angle', 0.0))
        self.center_x = float(config.get('center_x', 50.0))
        self.center_y = float(config.get('center_y', 50.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Rotation auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Rotiertes Frame
        """
        if abs(self.angle) < 0.1:
            return frame
        
        h, w = frame.shape[:2]
        
        # Berechne Rotationszentrum in Pixeln
        cx = int(w * self.center_x / 100.0)
        cy = int(h * self.center_y / 100.0)
        
        # Erstelle Rotations-Matrix
        M = cv2.getRotationMatrix2D((cx, cy), self.angle, 1.0)
        
        # Rotiere Bild
        rotated = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR)
        
        return rotated
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'angle':
            self.angle = float(value)
            return True
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'angle': self.angle,
            'center_x': self.center_x,
            'center_y': self.center_y
        }
