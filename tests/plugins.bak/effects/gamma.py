"""
Gamma Correction Effect Plugin - Non-linear Brightness Adjustment
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class GammaEffect(PluginBase):
    """
    Gamma Correction Effect - Nicht-lineare Helligkeitsanpassung.
    """
    
    METADATA = {
        'id': 'gamma',
        'name': 'Gamma Correction',
        'description': 'Nicht-lineare Helligkeitsanpassung (Gamma-Korrektur)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Color/Tone'
    }
    
    PARAMETERS = [
        {
            'name': 'gamma',
            'label': 'Gamma',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 3.0,
            'step': 0.05,
            'description': 'Gamma-Wert (<1 = heller, 1 = neutral, >1 = dunkler)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Gamma-Wert."""
        self.gamma = float(config.get('gamma', 1.0))
        self._build_lookup_table()
    
    def _build_lookup_table(self):
        """Erstellt Lookup-Table für schnelle Gamma-Korrektur."""
        # Erstelle LUT für 0-255 Werte
        # gamma < 1 = heller, gamma > 1 = dunkler
        self.lut = np.array([((i / 255.0) ** self.gamma) * 255 
                            for i in range(256)], dtype=np.uint8)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Gamma-Korrektur auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Gamma-korrigiertes Frame
        """
        if abs(self.gamma - 1.0) < 0.01:
            return frame
        
        # Wende Lookup-Table an (sehr schnell)
        corrected = cv2.LUT(frame, self.lut)
        
        return corrected
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'gamma':
            self.gamma = float(value)
            self._build_lookup_table()
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'gamma': self.gamma
        }
