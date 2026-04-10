"""
Brightness/Contrast Effect Plugin - Basic brightness and contrast control
"""
import os
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'brightness_contrast.wgsl')


class BrightnessContrastEffect(PluginBase):
    """
    Brightness/Contrast Effect - Helligkeit und Kontrast anpassen.
    """

    _shader_src: str | None = None

    METADATA = {
        'id': 'brightness_contrast',
        'name': 'Brightness/Contrast',
        'description': 'Helligkeit und Kontrast anpassen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'brightness',
            'label': 'Brightness',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -100.0,
            'max': 100.0,
            'step': 1.0,
            'description': 'Helligkeit (-100 = dunkel, +100 = hell)'
        },
        {
            'name': 'contrast',
            'label': 'Contrast',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 3.0,
            'step': 0.1,
            'description': 'Kontrast (1.0 = original, >1.0 = mehr Kontrast)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Brightness/Contrast-Werten."""
        self.brightness = config.get('brightness', 0.0)
        self.contrast = config.get('contrast', 1.0)
    
    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via GLSL shader. This stub is never called on live frames."""
        return frame
    
    # ── GPU shader interface ────────────────────────────────────────────
    def get_shader(self):
        if BrightnessContrastEffect._shader_src is None:
            with open(_SHADER_PATH) as f:
                BrightnessContrastEffect._shader_src = f.read()
        return BrightnessContrastEffect._shader_src

    def get_uniforms(self, **kwargs):
        return {
            'brightness': self.brightness / 100.0,
            'contrast': float(self.contrast),
        }

    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'brightness':
            self.brightness = float(value)
        elif name == 'contrast':
            self.contrast = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'brightness': self.brightness,
            'contrast': self.contrast
        }
