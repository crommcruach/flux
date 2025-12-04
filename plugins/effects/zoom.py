"""
Zoom Effect Plugin - Zoom In/Out Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ZoomEffect(PluginBase):
    """
    Zoom Effect - Zoomt das Bild rein oder raus.
    """
    
    METADATA = {
        'id': 'zoom',
        'name': 'Zoom',
        'description': 'Zoomt das Bild ein oder aus vom Zentrum',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'zoom',
            'label': 'Zoom-Faktor',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Zoom-Faktor (<1 = raus, 1 = original, >1 = rein)'
        },
        {
            'name': 'center_x',
            'label': 'Zentrum X (%)',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Horizontale Position des Zoom-Zentrums (0-100%)'
        },
        {
            'name': 'center_y',
            'label': 'Zentrum Y (%)',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Vertikale Position des Zoom-Zentrums (0-100%)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Zoom-Parametern."""
        self.zoom = float(config.get('zoom', 1.0))
        self.center_x = float(config.get('center_x', 50.0))
        self.center_y = float(config.get('center_y', 50.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Zoom-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Gezoomtes Frame
        """
        if abs(self.zoom - 1.0) < 0.01:
            return frame
        
        h, w = frame.shape[:2]
        
        # Berechne Zoom-Zentrum in Pixeln
        cx = int(w * self.center_x / 100.0)
        cy = int(h * self.center_y / 100.0)
        
        # Erstelle Transformations-Matrix für Zoom um Zentrum
        # 1. Verschiebe Zentrum zum Ursprung
        # 2. Skaliere
        # 3. Verschiebe zurück
        
        M = cv2.getRotationMatrix2D((cx, cy), 0, self.zoom)
        
        zoomed = cv2.warpAffine(frame, M, (w, h), flags=cv2.INTER_LINEAR)
        
        return zoomed
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'zoom':
            self.zoom = float(value)
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
            'zoom': self.zoom,
            'center_x': self.center_x,
            'center_y': self.center_y
        }
