"""
Colorize Effect Plugin - Colorize image while preserving luminance
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ColorizeEffect(PluginBase):
    """
    Colorize Effect - Färbt das Bild ein, behält aber die Luminanz bei.
    """
    
    METADATA = {
        'id': 'colorize',
        'name': 'Colorize',
        'description': 'Färbt das Bild ein (behält Luminanz bei)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'color',
            'label': 'Color',
            'type': ParameterType.COLOR,
            'default': '#ff0000',
            'description': 'Zielfarbe (Hue + Saturation werden aus Hex-Farbe extrahiert)'
        },
        {
            'name': 'invert',
            'label': 'Invert Colors',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Farben invertieren (nach dem Colorize-Schritt)'
        }
    ]

    def _hex_to_opencv_hs(self, hex_color):
        """Konvertiert Hex-Farbe (#rrggbb oder #rrggbbaa) zu OpenCV HSV H (0-180) und S (0-255)."""
        hex_color = str(hex_color).lstrip('#')
        # Strip optional alpha byte (#rrggbbaa -> #rrggbb)
        if len(hex_color) == 8:
            hex_color = hex_color[:6]
        if len(hex_color) != 6:
            return 0, 255
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            pixel = np.array([[[b, g, r]]], dtype=np.uint8)  # BGR for OpenCV
            hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
            return int(hsv[0, 0, 0]), int(hsv[0, 0, 1])
        except Exception:
            return 0, 255

    def initialize(self, config):
        """Initialisiert Plugin mit einer Hex-Farbe."""
        self.color = config.get('color', '#ff0000')
        self.invert = bool(config.get('invert', False))
        self.hue, self.saturation = self._hex_to_opencv_hs(self.color)
    
    def process_frame(self, frame, **kwargs):
        """
        Färbt das Bild ein, behält Luminanz bei.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Colorisiertes Frame
        """
        # Convert to HSV
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Replace Hue and Saturation (derived from color), keep Value (Luminance)
        hsv[:, :, 0] = self.hue
        hsv[:, :, 1] = self.saturation
        
        # Invert only the V (brightness) channel so dark→bright and bright→dark
        # while the chosen hue stays intact
        if self.invert:
            hsv[:, :, 2] = 255 - hsv[:, :, 2]
        
        # Convert back to BGR
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'color':
            self.color = str(value)
            self.hue, self.saturation = self._hex_to_opencv_hs(self.color)
        elif name == 'invert':
            self.invert = bool(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'color': self.color,
            'invert': self.invert
        }
