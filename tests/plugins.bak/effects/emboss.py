"""
Emboss Effect Plugin - 3D Relief Effect
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class EmbossEffect(PluginBase):
    """
    Emboss Effect - Erzeugt einen 3D-Relief-Effekt.
    """
    
    METADATA = {
        'id': 'emboss',
        'name': 'Emboss',
        'description': 'Erzeugt einen 3D-Relief/Prägung-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Artistic'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 3.0,
            'step': 0.1,
            'description': 'Emboss-Intensität (0 = kein Effekt, höher = stärker)'
        },
        {
            'name': 'angle',
            'label': 'Winkel',
            'type': ParameterType.FLOAT,
            'default': 45.0,
            'min': 0.0,
            'max': 360.0,
            'step': 15.0,
            'description': 'Lichtwinkel für den Relief-Effekt (0-360°)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Emboss-Parametern."""
        self.strength = float(config.get('strength', 1.0))
        self.angle = float(config.get('angle', 45.0))
        self._update_kernel()
    
    def _update_kernel(self):
        """Erstellt Emboss-Kernel basierend auf Winkel."""
        # Konvertiere Winkel zu Radians
        rad = np.radians(self.angle)
        
        # Basis-Emboss-Kernel (45° Standard)
        # [-2 -1  0]
        # [-1  1  1]
        # [ 0  1  2]
        
        # Rotiere Kernel basierend auf Winkel
        cos_a = np.cos(rad)
        sin_a = np.sin(rad)
        
        # Vereinfachter Emboss-Kernel mit 4 Hauptrichtungen
        angle_norm = self.angle % 360
        
        if angle_norm < 45 or angle_norm >= 315:
            # Rechts
            self.kernel = np.array([[-1, 0, 1],
                                   [-2, 0, 2],
                                   [-1, 0, 1]], dtype=np.float32)
        elif angle_norm < 135:
            # Oben
            self.kernel = np.array([[-1, -2, -1],
                                   [ 0,  0,  0],
                                   [ 1,  2,  1]], dtype=np.float32)
        elif angle_norm < 225:
            # Links
            self.kernel = np.array([[ 1,  0, -1],
                                   [ 2,  0, -2],
                                   [ 1,  0, -1]], dtype=np.float32)
        else:
            # Unten
            self.kernel = np.array([[ 1,  2,  1],
                                   [ 0,  0,  0],
                                   [-1, -2, -1]], dtype=np.float32)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Emboss-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Embossed Frame
        """
        if self.strength <= 0.0:
            return frame
        
        # Konvertiere zu Graustufen für Emboss-Berechnung
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Wende Emboss-Kernel an (skaliert mit Stärke)
        embossed = cv2.filter2D(gray, cv2.CV_32F, self.kernel)
        
        # Normalisiere und skaliere mit Stärke
        embossed = embossed * self.strength
        embossed = embossed + 128  # Offset für Grau als Basis
        embossed = np.clip(embossed, 0, 255).astype(np.uint8)
        
        # Konvertiere zurück zu BGR (Graustufen-Emboss)
        embossed_bgr = cv2.cvtColor(embossed, cv2.COLOR_GRAY2BGR)
        
        return embossed_bgr
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'strength':
            self.strength = float(value)
            return True
        elif name == 'angle':
            self.angle = float(value)
            self._update_kernel()
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'strength': self.strength,
            'angle': self.angle
        }
