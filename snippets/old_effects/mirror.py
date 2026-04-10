"""
Mirror Effect Plugin - Mirror/Kaleidoscope Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class MirrorEffect(PluginBase):
    """
    Mirror Effect - Spiegelt Bildhälften für symmetrischen Effekt.
    """
    
    METADATA = {
        'id': 'mirror',
        'name': 'Mirror',
        'description': 'Spiegelt Bildhälften für symmetrischen Kaleidoskop-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'mode',
            'label': 'Modus',
            'type': ParameterType.SELECT,
            'default': 'left_to_right',
            'options': ['left_to_right', 'right_to_left', 'top_to_bottom', 'bottom_to_top', 'quad'],
            'description': 'Mirror-Modus (left/right = horizontal, top/bottom = vertikal, quad = 4-fach Spiegel)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Mirror-Modus."""
        self.mode = str(config.get('mode', 'left_to_right'))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Mirror-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Gespiegeltes Frame
        """
        h, w = frame.shape[:2]
        
        if self.mode == 'left_to_right':
            # Linke Hälfte nach rechts spiegeln
            left_half = frame[:, :w//2]
            mirrored = cv2.flip(left_half, 1)
            result = np.hstack([left_half, mirrored])
            
        elif self.mode == 'right_to_left':
            # Rechte Hälfte nach links spiegeln
            right_half = frame[:, w//2:]
            mirrored = cv2.flip(right_half, 1)
            result = np.hstack([mirrored, right_half])
            
        elif self.mode == 'top_to_bottom':
            # Obere Hälfte nach unten spiegeln
            top_half = frame[:h//2, :]
            mirrored = cv2.flip(top_half, 0)
            result = np.vstack([top_half, mirrored])
            
        elif self.mode == 'bottom_to_top':
            # Untere Hälfte nach oben spiegeln
            bottom_half = frame[h//2:, :]
            mirrored = cv2.flip(bottom_half, 0)
            result = np.vstack([mirrored, bottom_half])
            
        elif self.mode == 'quad':
            # 4-fach Spiegel (Kaleidoskop)
            quarter = frame[:h//2, :w//2]
            top_left = quarter
            top_right = cv2.flip(quarter, 1)
            bottom_left = cv2.flip(quarter, 0)
            bottom_right = cv2.flip(quarter, -1)
            
            top_row = np.hstack([top_left, top_right])
            bottom_row = np.hstack([bottom_left, bottom_right])
            result = np.vstack([top_row, bottom_row])
        else:
            return frame
        
        # Resize auf Original-Größe falls nötig
        if result.shape[:2] != (h, w):
            result = cv2.resize(result, (w, h))
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'mode':
            self.mode = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'mode': self.mode
        }
