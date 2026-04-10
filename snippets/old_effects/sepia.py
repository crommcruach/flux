"""
Sepia Effect Plugin - Vintage Sepia Tone Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SepiaEffect(PluginBase):
    """
    Sepia Effect - Erzeugt einen Vintage-Sepia-Ton (braun-orange).
    """
    
    METADATA = {
        'id': 'sepia',
        'name': 'Sepia Tone',
        'description': 'Vintage Sepia-Effekt (braun-orange Ton)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Color/Tone'
    }
    
    PARAMETERS = [
        {
            'name': 'intensity',
            'label': 'Intensität',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Sepia-Intensität (0 = Original, 1 = voller Sepia-Ton)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Sepia-Intensität."""
        self.intensity = float(config.get('intensity', 1.0))
        
        # Standard Sepia-Matrix (klassische Formel)
        self.sepia_matrix = np.array([
            [0.393, 0.769, 0.189],  # Blue channel
            [0.349, 0.686, 0.168],  # Green channel
            [0.272, 0.534, 0.131]   # Red channel
        ], dtype=np.float32)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Sepia-Ton auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Sepia-gefärbtes Frame
        """
        if self.intensity <= 0.0:
            return frame
        
        # Konvertiere zu Float für Berechnungen
        frame_float = frame.astype(np.float32)
        
        # Wende Sepia-Matrix an (Matrix-Multiplikation mit jedem Pixel)
        # OpenCV verwendet BGR, daher invertieren wir die Matrix-Reihenfolge
        sepia = cv2.transform(frame_float, self.sepia_matrix)
        
        # Clip auf 0-255
        sepia = np.clip(sepia, 0, 255)
        
        # Mische Original mit Sepia basierend auf Intensität
        if self.intensity < 1.0:
            sepia = frame_float * (1.0 - self.intensity) + sepia * self.intensity
        
        return sepia.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'intensity':
            self.intensity = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'intensity': self.intensity
        }
