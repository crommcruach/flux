"""
Keystone Effect Plugin - Perspective Correction
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class KeystoneEffect(PluginBase):
    """
    Keystone Effect - Perspektivische Verzerrung/Korrektur (Trapez-Effekt).
    """
    
    METADATA = {
        'id': 'keystone',
        'name': 'Keystone',
        'description': 'Perspektivische Verzerrung für Trapez/Keystone-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'horizontal',
            'label': 'Horizontal',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -50.0,
            'max': 50.0,
            'step': 1.0,
            'description': 'Horizontale Keystone-Korrektur (-50 bis +50, 0 = keine Verzerrung)'
        },
        {
            'name': 'vertical',
            'label': 'Vertikal',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -50.0,
            'max': 50.0,
            'step': 1.0,
            'description': 'Vertikale Keystone-Korrektur (-50 bis +50, 0 = keine Verzerrung)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Keystone-Parametern."""
        self.horizontal = float(config.get('horizontal', 0.0))
        self.vertical = float(config.get('vertical', 0.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Keystone-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Perspektivisch verzerrtes Frame
        """
        if abs(self.horizontal) < 0.1 and abs(self.vertical) < 0.1:
            return frame
        
        h, w = frame.shape[:2]
        
        # Berechne Verschiebung in Pixeln
        h_shift = int(w * self.horizontal / 100.0)
        v_shift = int(h * self.vertical / 100.0)
        
        # Original-Eckpunkte
        src_points = np.float32([
            [0, 0],           # Top-left
            [w, 0],           # Top-right
            [w, h],           # Bottom-right
            [0, h]            # Bottom-left
        ])
        
        # Ziel-Eckpunkte (Trapez-Form)
        dst_points = np.float32([
            [0 - h_shift, 0 - v_shift],           # Top-left
            [w + h_shift, 0 + v_shift],           # Top-right
            [w + h_shift, h - v_shift],           # Bottom-right
            [0 - h_shift, h + v_shift]            # Bottom-left
        ])
        
        # Berechne Perspektiv-Matrix
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        
        # Wende Perspektiv-Transformation an
        warped = cv2.warpPerspective(frame, matrix, (w, h), 
                                     flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(0, 0, 0))
        
        return warped
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'horizontal':
            self.horizontal = float(value)
            return True
        elif name == 'vertical':
            self.vertical = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'horizontal': self.horizontal,
            'vertical': self.vertical
        }
