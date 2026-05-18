"""
Auto Mask Effect Plugin - Key out (near-)black backgrounds by luminance threshold.
"""
import os
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'auto_mask.wgsl')


class AutoMaskEffect(PluginBase):
    """
    Auto Mask Effect - Makes dark/black pixels transparent based on a luminance threshold.
    """

    _shader_src: str | None = None

    METADATA = {
        'id': 'auto_mask',
        'name': 'Auto Mask',
        'description': 'Keyt schwarze/dunkle Hintergründe per Luminanz-Schwellwert aus (Alpha = 0)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }

    PARAMETERS = [
        {
            'name': 'threshold',
            'label': 'Threshold',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Luminanz-Schwellwert – Pixel mit Helligkeit <= Schwellwert werden transparent (0 = nur reines Schwarz, 1 = alles)'
        },
        {
            'name': 'invert',
            'label': 'Invert',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Maske invertieren – helle Pixel werden transparent, dunkle bleiben sichtbar'
        }
    ]

    def initialize(self, config):
        self.threshold = float(config.get('threshold', 0.1))
        self.invert = bool(config.get('invert', False))

    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via GLSL shader. This stub is never called on live frames."""
        return frame

    # ── GPU shader interface ────────────────────────────────────────────
    def get_shader(self):
        if AutoMaskEffect._shader_src is None:
            with open(_SHADER_PATH) as f:
                AutoMaskEffect._shader_src = f.read()
        return AutoMaskEffect._shader_src

    def get_uniforms(self, **kwargs):
        return {
            'threshold': float(self.threshold),
            'invert': 1.0 if self.invert else 0.0,
        }

    def is_noop(self):
        # noop only if threshold is 0 and not inverted (nothing gets masked)
        return self.threshold <= 0.0 and not self.invert

    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'threshold':
            self.threshold = max(0.0, min(1.0, float(value)))
            return True
        elif name == 'invert':
            self.invert = bool(value)
            return True
        return False

    def get_parameters(self):
        return {
            'threshold': self.threshold,
            'invert': self.invert,
        }
