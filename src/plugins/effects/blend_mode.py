"""
Blend Mode Effect Plugin
Blends frames with colors or layers using various blend modes.
"""
import numpy as np
from ..plugin_base import PluginBase, PluginType, ParameterType


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
    
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Apply blend mode effect to the frame.
        
        Args:
            frame: Input frame (numpy array)
            
        Returns:
            Processed frame with blend mode applied
        """
        mode = self.parameters.get('mode', 'normal')
        color_r = int(self.parameters.get('color_r', 255))
        color_g = int(self.parameters.get('color_g', 255))
        color_b = int(self.parameters.get('color_b', 255))
        opacity = float(self.parameters.get('opacity', 100.0)) / 100.0
        mix = float(self.parameters.get('mix', 100.0)) / 100.0
        
        # Create blend color layer (same size as frame)
        blend_layer = np.full_like(frame, [color_b, color_g, color_r], dtype=np.uint8)
        
        # Convert to float for blending (0-1 range)
        base = frame.astype(np.float32) / 255.0
        blend = blend_layer.astype(np.float32) / 255.0
        
        # Apply blend mode
        if mode == 'normal':
            result = blend
        elif mode == 'multiply':
            result = base * blend
        elif mode == 'screen':
            result = 1.0 - (1.0 - base) * (1.0 - blend)
        elif mode == 'overlay':
            result = self._overlay_blend(base, blend)
        elif mode == 'add':
            result = np.clip(base + blend, 0.0, 1.0)
        elif mode == 'subtract':
            result = np.clip(base - blend, 0.0, 1.0)
        elif mode == 'darken':
            result = np.minimum(base, blend)
        elif mode == 'lighten':
            result = np.maximum(base, blend)
        elif mode == 'color_dodge':
            result = self._color_dodge(base, blend)
        elif mode == 'color_burn':
            result = self._color_burn(base, blend)
        elif mode == 'hard_light':
            result = self._hard_light(base, blend)
        elif mode == 'soft_light':
            result = self._soft_light(base, blend)
        elif mode == 'difference':
            result = np.abs(base - blend)
        elif mode == 'exclusion':
            result = base + blend - 2.0 * base * blend
        else:
            result = base
        
        # Apply opacity
        result = base * (1.0 - opacity) + result * opacity
        
        # Apply mix (blend between original and effect)
        result = base * (1.0 - mix) + result * mix
        
        # Convert back to uint8
        result = np.clip(result * 255.0, 0, 255).astype(np.uint8)
        
        return result
    
    def _overlay_blend(self, base: np.ndarray, blend: np.ndarray) -> np.ndarray:
        """Overlay blend mode"""
        result = np.where(
            base < 0.5,
            2.0 * base * blend,
            1.0 - 2.0 * (1.0 - base) * (1.0 - blend)
        )
        return result
    
    def _color_dodge(self, base: np.ndarray, blend: np.ndarray) -> np.ndarray:
        """Color dodge blend mode"""
        result = np.where(
            blend >= 1.0,
            1.0,
            np.clip(base / (1.0 - blend + 1e-10), 0.0, 1.0)
        )
        return result
    
    def _color_burn(self, base: np.ndarray, blend: np.ndarray) -> np.ndarray:
        """Color burn blend mode"""
        result = np.where(
            blend <= 0.0,
            0.0,
            np.clip(1.0 - (1.0 - base) / (blend + 1e-10), 0.0, 1.0)
        )
        return result
    
    def _hard_light(self, base: np.ndarray, blend: np.ndarray) -> np.ndarray:
        """Hard light blend mode"""
        result = np.where(
            blend < 0.5,
            2.0 * base * blend,
            1.0 - 2.0 * (1.0 - base) * (1.0 - blend)
        )
        return result
    
    def _soft_light(self, base: np.ndarray, blend: np.ndarray) -> np.ndarray:
        """Soft light blend mode (Pegtop formula)"""
        result = (1.0 - 2.0 * blend) * base * base + 2.0 * blend * base
        return np.clip(result, 0.0, 1.0)
    
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
