"""
Oil Paint Effect Plugin - Artistic Oil Painting Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class OilPaintEffect(PluginBase):
    """
    Oil Paint Effect - Simuliert Ölmalerei-Stil.
    """
    
    METADATA = {
        'id': 'oil_paint',
        'name': 'Oil Paint',
        'description': 'Simuliert Ölmalerei-Effekt mit konfigurierbarer Pinselgröße',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Artistic'
    }
    
    PARAMETERS = [
        {
            'name': 'size',
            'label': 'Pinselgröße',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 10,
            'step': 1,
            'description': 'Größe des Ölmalerei-Pinsels (höher = gröber)'
        },
        {
            'name': 'dynRatio',
            'label': 'Dynamik',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 3,
            'step': 1,
            'description': 'Dynamik-Verhältnis (höher = glatter)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Oil-Paint-Parametern."""
        self.size = int(config.get('size', 5))
        self.dynRatio = int(config.get('dynRatio', 1))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Oil-Paint-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Ölgemälde-artiges Frame
        """
        try:
            # OpenCV's xphoto module für Oil Paint (falls verfügbar)
            if hasattr(cv2, 'xphoto'):
                painted = cv2.xphoto.oilPainting(frame, self.size, self.dynRatio)
                return painted
        except:
            pass
        
        # Fallback: Median Blur + Bilateral für ähnlichen Effekt
        # (Oil Paint benötigt opencv-contrib-python)
        # Median Blur ist viel schneller als bilateralFilter
        kernel_size = self.size * 2 + 1  # Muss ungerade sein
        painted = cv2.medianBlur(frame, kernel_size)
        
        # Optional: leichter Bilateral für Glättung (nur bei kleiner Pinselgröße)
        if self.size <= 3:
            painted = cv2.bilateralFilter(painted, d=5, sigmaColor=50, sigmaSpace=50)
        
        return painted
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'size':
            self.size = int(value)
            return True
        elif name == 'dynRatio':
            self.dynRatio = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'size': self.size,
            'dynRatio': self.dynRatio
        }
