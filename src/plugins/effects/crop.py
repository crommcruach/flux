"""
Crop Effect Plugin - Crop/Cut Image
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class CropEffect(PluginBase):
    """
    Crop Effect - Schneidet Bild zu (mit oder ohne Skalierung zurück).
    """
    
    METADATA = {
        'id': 'crop',
        'name': 'Crop',
        'description': 'Schneidet das Bild zu einer Region zurecht',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'left',
            'label': 'Links (%)',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Beschnitt von links (0-100%)'
        },
        {
            'name': 'top',
            'label': 'Oben (%)',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Beschnitt von oben (0-100%)'
        },
        {
            'name': 'right',
            'label': 'Rechts (%)',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Beschnitt von rechts (0-100%)'
        },
        {
            'name': 'bottom',
            'label': 'Unten (%)',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Beschnitt von unten (0-100%)'
        },
        {
            'name': 'scale_back',
            'label': 'Zurückskalieren',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Skaliere zugeschnittenes Bild zurück auf Originalgröße'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Crop-Parametern."""
        self.left = float(config.get('left', 0.0))
        self.top = float(config.get('top', 0.0))
        self.right = float(config.get('right', 0.0))
        self.bottom = float(config.get('bottom', 0.0))
        self.scale_back = bool(config.get('scale_back', True))
    
    def process_frame(self, frame, **kwargs):
        """
        Schneidet Frame zu.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Zugeschnittenes (und optional skaliertes) Frame
        """
        h, w = frame.shape[:2]
        
        # Berechne Crop-Region in Pixeln
        crop_left = int(w * self.left / 100.0)
        crop_top = int(h * self.top / 100.0)
        crop_right = int(w * self.right / 100.0)
        crop_bottom = int(h * self.bottom / 100.0)
        
        # Validiere Crop-Region
        x1 = max(0, crop_left)
        y1 = max(0, crop_top)
        x2 = min(w, w - crop_right)
        y2 = min(h, h - crop_bottom)
        
        if x2 <= x1 or y2 <= y1:
            return frame  # Invalide Crop-Region
        
        # Schneide zu
        cropped = frame[y1:y2, x1:x2]
        
        # Optional: Skaliere zurück auf Originalgröße
        if self.scale_back:
            cropped = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        
        return cropped
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'left':
            self.left = float(value)
            return True
        elif name == 'top':
            self.top = float(value)
            return True
        elif name == 'right':
            self.right = float(value)
            return True
        elif name == 'bottom':
            self.bottom = float(value)
            return True
        elif name == 'scale_back':
            self.scale_back = bool(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'left': self.left,
            'top': self.top,
            'right': self.right,
            'bottom': self.bottom,
            'scale_back': self.scale_back
        }
