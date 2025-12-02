"""
Noise Effect Plugin - Add Random Noise
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class NoiseEffect(PluginBase):
    """
    Noise Effect - Fügt zufälliges Rauschen zum Bild hinzu.
    """
    
    METADATA = {
        'id': 'noise',
        'name': 'Noise',
        'description': 'Fügt zufälliges Rauschen zum Bild hinzu (Gaussian oder Salt & Pepper)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'intensity',
            'label': 'Intensität',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Rausch-Intensität (0 = kein Rauschen, 1 = maximales Rauschen)'
        },
        {
            'name': 'type',
            'label': 'Typ',
            'type': ParameterType.SELECT,
            'default': 'gaussian',
            'options': ['gaussian', 'salt_pepper'],
            'description': 'Rausch-Typ (Gaussian = gleichmäßig, Salt & Pepper = schwarze/weiße Punkte)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Noise-Parametern."""
        self.intensity = float(config.get('intensity', 0.1))
        self.noise_type = str(config.get('type', 'gaussian'))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Rauschen auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verrauschtes Frame
        """
        if self.intensity <= 0.0:
            return frame
        
        if self.noise_type == 'gaussian':
            # Gaussian Noise
            noise = np.random.normal(0, self.intensity * 50, frame.shape).astype(np.float32)
            noisy = frame.astype(np.float32) + noise
            noisy = np.clip(noisy, 0, 255)
            return noisy.astype(np.uint8)
        
        elif self.noise_type == 'salt_pepper':
            # Salt & Pepper Noise
            noisy = frame.copy()
            
            # Salt (weiße Pixel)
            num_salt = int(self.intensity * 0.5 * frame.size * 0.01)
            coords = [np.random.randint(0, i, num_salt) for i in frame.shape[:2]]
            noisy[coords[0], coords[1], :] = 255
            
            # Pepper (schwarze Pixel)
            num_pepper = int(self.intensity * 0.5 * frame.size * 0.01)
            coords = [np.random.randint(0, i, num_pepper) for i in frame.shape[:2]]
            noisy[coords[0], coords[1], :] = 0
            
            return noisy
        
        return frame
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'intensity':
            self.intensity = float(value)
            return True
        elif name == 'type':
            self.noise_type = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'intensity': self.intensity,
            'type': self.noise_type
        }
