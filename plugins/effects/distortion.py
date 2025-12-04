"""
Distortion Effect Plugin - Lens Distortion Effects
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class DistortionEffect(PluginBase):
    """
    Distortion Effect - Linsen-Verzerrungseffekte (Barrel/Pincushion).
    """
    
    METADATA = {
        'id': 'distortion',
        'name': 'Distortion',
        'description': 'Linsen-Verzerrung (Barrel/Pincushion Distortion)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Glitch & Noise'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Verzerrungsstärke (negativ = Barrel, positiv = Pincushion)'
        },
        {
            'name': 'center_x',
            'label': 'Zentrum X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'X-Position des Verzerrungszentrums (0 = links, 1 = rechts)'
        },
        {
            'name': 'center_y',
            'label': 'Zentrum Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Y-Position des Verzerrungszentrums (0 = oben, 1 = unten)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Distortion Parametern."""
        self.strength = float(config.get('strength', 0.0))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Distortion auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verzerrtes Frame
        """
        if self.strength == 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Zentrum in Pixel-Koordinaten
        cx = self.center_x * w
        cy = self.center_y * h
        
        # Erstelle Koordinaten-Grids
        y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
        
        # Berechne Distanz vom Zentrum (normalisiert)
        dx = (x_coords - cx) / w
        dy = (y_coords - cy) / h
        r = np.sqrt(dx**2 + dy**2)
        
        # Barrel/Pincushion Distortion Formula
        # r' = r * (1 + k*r^2)
        # k < 0: Barrel (Fisheye-like)
        # k > 0: Pincushion
        k = self.strength
        r_distorted = r * (1 + k * r**2)
        
        # Berechne neue Koordinaten
        # Vermeide Division durch Null
        r_safe = np.where(r < 0.001, 0.001, r)
        scale = r_distorted / r_safe
        
        x_new = cx + dx * w * scale
        y_new = cy + dy * h * scale
        
        # Begrenze auf gültige Koordinaten
        x_new = np.clip(x_new, 0, w - 1).astype(np.float32)
        y_new = np.clip(y_new, 0, h - 1).astype(np.float32)
        
        # Remap
        distorted = cv2.remap(frame, 
                             x_new, 
                             y_new,
                             interpolation=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT)
        
        return distorted
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'strength':
            self.strength = float(value)
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
            'strength': self.strength,
            'center_x': self.center_x,
            'center_y': self.center_y
        }
