"""
Fish Eye Effect Plugin - Spherical Distortion
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class FisheyeEffect(PluginBase):
    """
    Fish Eye Effect - Sphärische Linsenverzerrung (Fischaugen-Effekt).
    """
    
    METADATA = {
        'id': 'fisheye',
        'name': 'Fish Eye',
        'description': 'Sphärische Linsenverzerrung für Fischaugen- oder Kugel-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Verzerrungsstärke (>0 = Fisheye, <0 = Barrel-Invert, 0 = keine Verzerrung)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Fisheye-Stärke."""
        self.strength = float(config.get('strength', 0.5))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Fisheye-Verzerrung auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verzerrtes Frame
        """
        if abs(self.strength) < 0.01:
            return frame
        
        h, w = frame.shape[:2]
        
        # Zentrum des Bildes
        cx = w / 2.0
        cy = h / 2.0
        
        # Erstelle Mesh-Grid (VIEL schneller als For-Schleife!)
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        
        # Distanz vom Zentrum (normalisiert)
        dx = (x - cx) / cx
        dy = (y - cy) / cy
        r = np.sqrt(dx**2 + dy**2)
        
        # Fisheye-Transformation (vektorisiert)
        # Verhindere Division durch 0
        r_safe = np.where(r > 0, r, 1)
        
        # Theta = atan(r * strength)
        theta = np.arctan(r_safe * self.strength)
        r_new = np.where(r > 0, theta / self.strength, 0)
        
        # Neue Koordinaten
        factor = np.where(r > 0, r_new / r_safe, 1)
        map_x = (cx + dx * cx * factor).astype(np.float32)
        map_y = (cy + dy * cy * factor).astype(np.float32)
        
        # Wende Remap an
        distorted = cv2.remap(frame, map_x, map_y, 
                             interpolation=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0))
        
        return distorted
    
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
