"""
Shift Glitch Effect Plugin - Digital Glitch with Line Shifting
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ShiftGlitchEffect(PluginBase):
    """
    Shift Glitch Effect - Digitaler Glitch-Effekt mit horizontalen Zeilenverschiebungen.
    """
    
    METADATA = {
        'id': 'shift_glitch',
        'name': 'Shift Glitch',
        'description': 'Digitaler Glitch-Effekt mit zufälligen Zeilenverschiebungen',
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
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Glitch-Intensität (0 = kein Glitch, 1 = maximaler Glitch)'
        },
        {
            'name': 'shift_amount',
            'label': 'Verschiebung',
            'type': ParameterType.INT,
            'default': 50,
            'min': 0,
            'max': 200,
            'description': 'Maximale horizontale Verschiebung in Pixeln'
        },
        {
            'name': 'block_size',
            'label': 'Blockgröße',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 50,
            'description': 'Höhe der verschobenen Blöcke in Pixeln'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Shift Glitch Parametern."""
        self.intensity = float(config.get('intensity', 0.5))
        self.shift_amount = int(config.get('shift_amount', 50))
        self.block_size = int(config.get('block_size', 5))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Shift Glitch auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Shift Glitch Effekt
        """
        if self.intensity <= 0:
            return frame
        
        h, w = frame.shape[:2]
        result = frame.copy()
        
        # Anzahl der Glitch-Blöcke basierend auf Intensität
        num_blocks = int((h / self.block_size) * self.intensity)
        
        if num_blocks == 0:
            return frame
        
        # Zufällige Y-Positionen für Glitch-Blöcke
        glitch_positions = np.random.randint(0, h - self.block_size, size=num_blocks)
        
        for y_pos in glitch_positions:
            # Zufällige horizontale Verschiebung
            shift = np.random.randint(-self.shift_amount, self.shift_amount + 1)
            
            if shift == 0:
                continue
            
            # Extrahiere Block
            y_end = min(y_pos + self.block_size, h)
            block = result[y_pos:y_end, :].copy()
            
            # Verschiebe Block horizontal mit Wrap-Around
            if shift > 0:
                result[y_pos:y_end, shift:] = block[:, :w-shift]
                result[y_pos:y_end, :shift] = block[:, w-shift:]
            else:
                shift = abs(shift)
                result[y_pos:y_end, :w-shift] = block[:, shift:]
                result[y_pos:y_end, w-shift:] = block[:, :shift]
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'intensity':
            self.intensity = float(value)
            return True
        elif name == 'shift_amount':
            self.shift_amount = int(value)
            return True
        elif name == 'block_size':
            self.block_size = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'intensity': self.intensity,
            'shift_amount': self.shift_amount,
            'block_size': self.block_size
        }
