"""
Color Temperature Effect Plugin - Warm/Cool Color Adjustment
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class TemperatureEffect(PluginBase):
    """
    Color Temperature Effect - Passt Farbtemperatur an (warm/kalt).
    """
    
    METADATA = {
        'id': 'temperature',
        'name': 'Color Temperature',
        'description': 'Passt Farbtemperatur an (warm = orange, kalt = blau)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Color/Tone'
    }
    
    PARAMETERS = [
        {
            'name': 'temperature',
            'label': 'Temperatur',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -100.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Farbtemperatur (<0 = kalt/blau, 0 = neutral, >0 = warm/orange)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Temperatur-Wert."""
        self.temperature = float(config.get('temperature', 0.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Farbtemperatur-Anpassung auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Temperatur-angepasstes Frame
        """
        if abs(self.temperature) < 1.0:
            return frame
        
        # Normalisiere Temperatur auf 0.0-1.0 Range
        temp_factor = self.temperature / 100.0
        
        # Konvertiere zu Float für Berechnungen
        result = frame.astype(np.float32)
        
        if temp_factor > 0:
            # Warm: Erhöhe Rot/Gelb, reduziere Blau
            # BGR Format: [B, G, R]
            result[:, :, 0] = result[:, :, 0] * (1.0 - temp_factor * 0.3)  # Blau reduzieren
            result[:, :, 1] = result[:, :, 1] * (1.0 + temp_factor * 0.1)  # Grün leicht erhöhen
            result[:, :, 2] = result[:, :, 2] * (1.0 + temp_factor * 0.3)  # Rot erhöhen
        else:
            # Kalt: Erhöhe Blau, reduziere Rot/Gelb
            temp_factor = abs(temp_factor)
            result[:, :, 0] = result[:, :, 0] * (1.0 + temp_factor * 0.3)  # Blau erhöhen
            result[:, :, 1] = result[:, :, 1] * (1.0 - temp_factor * 0.1)  # Grün leicht reduzieren
            result[:, :, 2] = result[:, :, 2] * (1.0 - temp_factor * 0.3)  # Rot reduzieren
        
        # Clip auf 0-255
        result = np.clip(result, 0, 255)
        
        return result.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'temperature':
            self.temperature = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'temperature': self.temperature
        }
