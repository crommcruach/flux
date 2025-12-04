"""
Radial Blur Effect Plugin - Blur from Center Point
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class RadialBlurEffect(PluginBase):
    """
    Radial Blur Effect - Erzeugt radialen Blur von einem Zentrum aus.
    """
    
    METADATA = {
        'id': 'radial_blur',
        'name': 'Radial Blur',
        'description': 'Radialer Blur von einem Zentrum aus (Motion/Zoom Blur)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur & Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 5.0,
            'min': 0.0,
            'max': 20.0,
            'description': 'Blur-Stärke (Anzahl der Iterationen)'
        },
        {
            'name': 'center_x',
            'label': 'Zentrum X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'X-Position des Zentrums (0 = links, 1 = rechts)'
        },
        {
            'name': 'center_y',
            'label': 'Zentrum Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Y-Position des Zentrums (0 = oben, 1 = unten)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Radial Blur Parametern."""
        self.strength = float(config.get('strength', 5.0))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Radial Blur auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Radial Blur
        """
        if self.strength <= 0:
            return frame
        
        h, w = frame.shape[:2]
        center_x_px = int(self.center_x * w)
        center_y_px = int(self.center_y * h)
        
        # Anzahl der Blur-Iterationen
        iterations = int(self.strength)
        if iterations < 1:
            return frame
        
        # Akkumulator für gemittelte Frames
        result = np.zeros_like(frame, dtype=np.float32)
        
        # Radial Blur durch wiederholtes Zoom und Mittelung
        for i in range(iterations):
            # Zoom-Faktor (von 1.0 bis 1 + strength/100)
            scale = 1.0 + (i / iterations) * (self.strength / 100.0)
            
            # Transformation Matrix für Zoom
            M = cv2.getRotationMatrix2D((center_x_px, center_y_px), 0, scale)
            
            # Transformiere Frame
            zoomed = cv2.warpAffine(frame, M, (w, h), 
                                    flags=cv2.INTER_LINEAR,
                                    borderMode=cv2.BORDER_REFLECT)
            
            # Akkumuliere
            result += zoomed.astype(np.float32)
        
        # Mittelwert bilden
        result = result / iterations
        
        return result.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
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
