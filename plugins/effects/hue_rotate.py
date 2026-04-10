"""
Hue Rotate Effect Plugin - Hue shift on HSV color space
"""
import os
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'hue_rotate.wgsl')


class HueRotateEffect(PluginBase):
    """
    Hue Rotate Effect - Verschiebt den Farbton (Hue) auf HSV-Basis.
    """

    _shader_src: str | None = None

    METADATA = {
        'id': 'hue_rotate',
        'name': 'Hue Rotate',
        'description': 'Verschiebt den Farbton (Hue) auf HSV-Basis',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'hue_shift',
            'label': 'Hue Shift',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -180.0,
            'max': 180.0,
            'step': 1.0,
            'description': 'Farbton-Verschiebung in Grad (-180 bis +180)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Hue-Shift."""
        self.hue_shift = config.get('hue_shift', 0.0)
    
    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via GLSL shader. This stub is never called on live frames."""
        return frame
    
    # ── GPU shader interface ────────────────────────────────────────────
    def get_shader(self):
        if HueRotateEffect._shader_src is None:
            with open(_SHADER_PATH) as f:
                HueRotateEffect._shader_src = f.read()
        return HueRotateEffect._shader_src

    def get_uniforms(self, **kwargs):
        return {'hue_shift': float(self.hue_shift)}

    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']

        if name == 'hue_shift':
            self.hue_shift = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'hue_shift': self.hue_shift}
