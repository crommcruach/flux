"""
Static Effect Plugin - TV Static Noise
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class StaticEffect(PluginBase):
    """
    Static Effect - TV-Static/Schnee-Rauschen.
    """
    
    METADATA = {
        'id': 'static',
        'name': 'Static',
        'description': 'TV-Static/Schnee-Rauschen-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Glitch & Noise'
    }
    
    PARAMETERS = [
        {
            'name': 'intensity',
            'label': 'Intensität',
            'type': ParameterType.FLOAT,
            'default': 0.3,
            'min': 0.0,
            'max': 1.0,
            'description': 'Static-Intensität (0 = kein Static, 1 = nur Static)'
        },
        {
            'name': 'size',
            'label': 'Größe',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 10,
            'description': 'Größe der Static-Pixel (1 = fein, 10 = grob)'
        },
        {
            'name': 'colored',
            'label': 'Farbig',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['no', 'yes'],
            'description': 'Schwarz/Weiß oder farbiges Static'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Static Parametern."""
        self.intensity = float(config.get('intensity', 0.3))
        self.size = int(config.get('size', 1))
        self.colored = str(config.get('colored', 'no'))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Static auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Static-Rauschen
        """
        if self.intensity <= 0:
            return frame
        
        h, w = frame.shape[:2]
        
        # Größe des Static-Grids
        static_h = max(1, h // self.size)
        static_w = max(1, w // self.size)
        
        if self.colored == 'yes':
            # Farbiges Static (RGB)
            static = np.random.randint(0, 256, (static_h, static_w, 3), dtype=np.uint8)
        else:
            # Schwarz/Weiß Static
            static_gray = np.random.randint(0, 256, (static_h, static_w), dtype=np.uint8)
            static = cv2.cvtColor(static_gray, cv2.COLOR_GRAY2BGR)
        
        # Skaliere Static auf Frame-Größe
        if self.size > 1:
            static = cv2.resize(static, (w, h), interpolation=cv2.INTER_NEAREST)
        
        # Blende Static über Original-Frame
        result = cv2.addWeighted(frame, 1.0 - self.intensity, 
                                static, self.intensity, 0)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'intensity':
            self.intensity = float(value)
            return True
        elif name == 'size':
            self.size = int(value)
            return True
        elif name == 'colored':
            self.colored = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'intensity': self.intensity,
            'size': self.size,
            'colored': self.colored
        }
