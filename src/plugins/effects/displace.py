"""
Displace Effect Plugin - Displacement Map Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class DisplaceEffect(PluginBase):
    """
    Displace Effect - Verschiebt Pixel basierend auf Helligkeits-Map.
    """
    
    METADATA = {
        'id': 'displace',
        'name': 'Displace',
        'description': 'Verschiebt Pixel basierend auf Helligkeitsverteilung',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur & Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'strength_x',
            'label': 'Stärke X',
            'type': ParameterType.FLOAT,
            'default': 10.0,
            'min': -50.0,
            'max': 50.0,
            'description': 'Horizontale Displacement-Stärke in Pixeln'
        },
        {
            'name': 'strength_y',
            'label': 'Stärke Y',
            'type': ParameterType.FLOAT,
            'default': 10.0,
            'min': -50.0,
            'max': 50.0,
            'description': 'Vertikale Displacement-Stärke in Pixeln'
        },
        {
            'name': 'scale',
            'label': 'Skalierung',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'description': 'Skalierung der Displacement-Map (größer = weniger Detail)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Displace Parametern."""
        self.strength_x = float(config.get('strength_x', 10.0))
        self.strength_y = float(config.get('strength_y', 10.0))
        self.scale = float(config.get('scale', 1.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Displacement auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Displaced Frame
        """
        if self.strength_x == 0 and self.strength_y == 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Erzeuge Displacement-Map aus Grauwert-Bild
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Optional: Skaliere Displacement-Map für gröbere/feinere Effekte
        if self.scale != 1.0:
            scale_w = max(1, int(w / self.scale))
            scale_h = max(1, int(h / self.scale))
            gray = cv2.resize(gray, (scale_w, scale_h), 
                            interpolation=cv2.INTER_LINEAR)
            gray = cv2.resize(gray, (w, h), 
                            interpolation=cv2.INTER_LINEAR)
        
        # Normalisiere zu [-1, 1] Bereich
        disp_map = (gray.astype(np.float32) / 127.5) - 1.0
        
        # Erstelle Verschiebungs-Koordinaten mit np.meshgrid (optimiert)
        y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
        
        # Wende Displacement an
        x_displaced = x_coords + (disp_map * self.strength_x).astype(np.float32)
        y_displaced = y_coords + (disp_map * self.strength_y).astype(np.float32)
        
        # Begrenze auf gültige Koordinaten
        x_displaced = np.clip(x_displaced, 0, w - 1)
        y_displaced = np.clip(y_displaced, 0, h - 1)
        
        # Remap mit cv2.remap (sehr schnell)
        displaced = cv2.remap(frame, 
                             x_displaced.astype(np.float32), 
                             y_displaced.astype(np.float32),
                             interpolation=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT)
        
        return displaced
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'strength_x':
            self.strength_x = float(value)
            return True
        elif name == 'strength_y':
            self.strength_y = float(value)
            return True
        elif name == 'scale':
            self.scale = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'strength_x': self.strength_x,
            'strength_y': self.strength_y,
            'scale': self.scale
        }
