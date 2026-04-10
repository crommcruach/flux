"""
Blend Mode Effect Plugin
Blends frames with colors or layers using various blend modes.
GPU-native: uses blend_mode.wgsl shader via the wgpu pipeline.
"""
import os
from ..plugin_base import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'blend_mode.wgsl'
)

# Integer IDs for the 'mode' uniform — must match if-else order in blend_mode.wgsl
BLEND_MODE_IDS: dict = {
    'normal':     0,
    'multiply':   1,
    'screen':     2,
    'overlay':    3,
    'add':        4,
    'subtract':   5,
    'darken':     6,
    'lighten':    7,
    'color_dodge': 8,
    'color_burn': 9,
    'hard_light': 10,
    'soft_light': 11,
    'difference': 12,
    'exclusion':  13,
}


class BlendModeEffect(PluginBase):
    """
    Blend Mode effect that supports various blend modes for compositing.
    Can blend with a solid color or with another layer.
    """
    
    METADATA = {
        'id': 'blend_mode',
        'name': 'Blend Mode',
        'description': 'Blend frames with colors using various blend modes (Multiply, Screen, Overlay, etc.)',
        'author': 'Flux Art-Net System',
        'version': '1.0.0',
        'type': PluginType.EFFECT
    }
    
    PARAMETERS = [
        {
            'name': 'mode',
            'type': ParameterType.SELECT,
            'default': 'normal',
            'options': [
                'normal',
                'multiply',
                'screen', 
                'overlay',
                'add',
                'subtract',
                'darken',
                'lighten',
                'color_dodge',
                'color_burn',
                'hard_light',
                'soft_light',
                'difference',
                'exclusion'
            ],
            'description': 'Blend mode to use',
            'min': None,
            'max': None
        },
        {
            'name': 'color_r',
            'type': ParameterType.RANGE,
            'default': 255,
            'min': 0,
            'max': 255,
            'description': 'Blend color - Red channel (0-255)',
            'options': None
        },
        {
            'name': 'color_g',
            'type': ParameterType.RANGE,
            'default': 255,
            'min': 0,
            'max': 255,
            'description': 'Blend color - Green channel (0-255)',
            'options': None
        },
        {
            'name': 'color_b',
            'type': ParameterType.RANGE,
            'default': 255,
            'min': 0,
            'max': 255,
            'description': 'Blend color - Blue channel (0-255)',
            'options': None
        },
        {
            'name': 'opacity',
            'type': ParameterType.RANGE,
            'default': 100.0,
            'min': 0.0,
            'max': 100.0,
            'description': 'Blend opacity (0-100%)',
            'options': None
        },
        {
            'name': 'mix',
            'type': ParameterType.RANGE,
            'default': 100.0,
            'min': 0.0,
            'max': 100.0,
            'description': 'Mix amount - blend between original and effect (0-100%)',
            'options': None
        }
    ]

    def process_frame(self, frame, **kwargs):
        """GPU-native — rendered via GLSL shader. This stub is never called on live frames."""
        return frame

    # ── GPU shader interface ─────────────────────────────────────────────────

    def get_shader(self):
        with open(_SHADER_PATH, encoding='utf-8') as f:
            return f.read()

    def get_uniforms(self, **kwargs):
        return {
            'color': [
                self.parameters.get('color_r', 255) / 255.0,
                self.parameters.get('color_g', 255) / 255.0,
                self.parameters.get('color_b', 255) / 255.0,
            ],
            'opacity':    float(self.parameters.get('opacity', 100.0)) / 100.0,
            'mix_amount': float(self.parameters.get('mix', 100.0)) / 100.0,
            'mode':       BLEND_MODE_IDS.get(self.parameters.get('mode', 'normal'), 0),
        }
    
    def initialize(self, config: dict = None):
        """Initialize the plugin with default parameters"""
        # Set defaults from PARAMETERS
        self.parameters = {}
        for param in self.PARAMETERS:
            self.parameters[param['name']] = config.get(param['name'], param['default']) if config else param['default']
    
    def get_parameters(self) -> dict:
        """Get current parameters"""
        return self.parameters.copy()
    
    def update_parameter(self, name: str, value) -> bool:
        """Update a single parameter"""
        if name in [p['name'] for p in self.PARAMETERS]:
            self.parameters[name] = value
            return True
        return False
