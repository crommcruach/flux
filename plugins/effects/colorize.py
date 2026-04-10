"""
Colorize Effect Plugin - Colorize image while preserving luminance
"""
import os
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'colorize.wgsl')


class ColorizeEffect(PluginBase):
    """
    Colorize Effect - Färbt das Bild ein, behält aber die Luminanz bei.
    """

    _shader_src: str | None = None

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

    def _hex_to_opencv_hsva(self, hex_color):
        """Konvertiert Hex-Farbe (#rrggbb oder #rrggbbaa) zu OpenCV H (0-180), S (0-255), V (0-255) und Alpha (0-255)."""
        hex_color = str(hex_color).lstrip('#')
        alpha = 255
        if len(hex_color) == 8:
            try:
                alpha = int(hex_color[6:8], 16)
            except ValueError:
                alpha = 255
            hex_color = hex_color[:6]
        if len(hex_color) != 6:
            return 0, 255, 255, 255
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            pixel = np.array([[[b, g, r]]], dtype=np.uint8)  # BGR for OpenCV
            hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)
            return int(hsv[0, 0, 0]), int(hsv[0, 0, 1]), int(hsv[0, 0, 2]), alpha
        except Exception:
            return 0, 255, 255, 255

    def initialize(self, config):
        """Initialisiert Plugin mit einer Hex-Farbe."""
        self.color = config.get('color', '#ff0000')
        self.invert = bool(config.get('invert', False))
        self.hue, self.saturation, self.brightness, self.alpha = self._hex_to_opencv_hsva(self.color)
    
    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via GLSL shader. This stub is never called on live frames."""
        return frame

    # ── GPU shader interface ────────────────────────────────────────────
    def get_shader(self):
        if ColorizeEffect._shader_src is None:
            with open(_SHADER_PATH) as f:
                ColorizeEffect._shader_src = f.read()
        return ColorizeEffect._shader_src

    def get_uniforms(self, **kwargs):
        # OpenCV hue: 0-180 → normalized 0-1;  OpenCV sat/val/alpha: 0-255 → 0-1
        return {
            'hue': self.hue / 180.0,
            'saturation': self.saturation / 255.0,
            'brightness': self.brightness / 255.0,
            'alpha': self.alpha / 255.0,
            'invert': 1 if self.invert else 0,
        }

    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'color':
            self.color = str(value)
            self.hue, self.saturation, self.brightness, self.alpha = self._hex_to_opencv_hsva(self.color)
        elif name == 'invert':
            self.invert = bool(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'color': self.color,
            'invert': self.invert
        }
