"""
Duotone Effect Plugin - Two-Color Tone Mapping
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class DuotoneEffect(PluginBase):
    """
    Duotone Effect - Mappt Bild auf zwei Farben (Schatten und Highlights).
    """
    
    METADATA = {
        'id': 'duotone',
        'name': 'Duotone',
        'description': 'Mappt Bild auf zwei Farben (Schatten-Farbe und Highlight-Farbe)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Artistic'
    }
    
    PARAMETERS = [
        {
            'name': 'shadow_color',
            'label': 'Schatten-Farbe',
            'type': ParameterType.COLOR,
            'default': '#000080',
            'description': 'Farbe für dunkle Bereiche (RGB Hex)'
        },
        {
            'name': 'highlight_color',
            'label': 'Highlight-Farbe',
            'type': ParameterType.COLOR,
            'default': '#FFD700',
            'description': 'Farbe für helle Bereiche (RGB Hex)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Duotone-Farben."""
        self.shadow_color = str(config.get('shadow_color', '#000080'))
        self.highlight_color = str(config.get('highlight_color', '#FFD700'))
        self._parse_colors()
    
    def _parse_colors(self):
        """Konvertiert Hex-Farben zu BGR."""
        # Shadow color
        shadow_hex = self.shadow_color.lstrip('#')
        shadow_rgb = tuple(int(shadow_hex[i:i+2], 16) for i in (0, 2, 4))
        self.shadow_bgr = np.array([shadow_rgb[2], shadow_rgb[1], shadow_rgb[0]], dtype=np.float32)
        
        # Highlight color
        highlight_hex = self.highlight_color.lstrip('#')
        highlight_rgb = tuple(int(highlight_hex[i:i+2], 16) for i in (0, 2, 4))
        self.highlight_bgr = np.array([highlight_rgb[2], highlight_rgb[1], highlight_rgb[0]], dtype=np.float32)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Duotone-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Duotone-gefärbtes Frame
        """
        # Konvertiere zu Graustufen
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Normalisiere auf 0.0-1.0
        gray_norm = gray.astype(np.float32) / 255.0
        
        # Erstelle leeres BGR-Bild
        result = np.zeros(frame.shape, dtype=np.float32)
        
        # Interpoliere zwischen Shadow- und Highlight-Farbe basierend auf Helligkeit
        for i in range(3):  # B, G, R channels
            result[:, :, i] = self.shadow_bgr[i] * (1.0 - gray_norm) + self.highlight_bgr[i] * gray_norm
        
        return result.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'shadow_color':
            self.shadow_color = str(value)
            self._parse_colors()
            return True
        elif name == 'highlight_color':
            self.highlight_color = str(value)
            self._parse_colors()
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'shadow_color': self.shadow_color,
            'highlight_color': self.highlight_color
        }
