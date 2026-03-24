"""
GPU pipeline — ModernGL/GLSL layer compositor.

Public API used by LayerManager:
    from ...gpu import get_context, get_texture_pool, get_renderer, load_shader, BLEND_MODES
"""
from .context import get_context, destroy_context
from .texture_pool import get_texture_pool
from .renderer import get_renderer, load_shader
from .frame import GPUFrame

# Blend mode name → integer index used in blend.frag
BLEND_MODES: dict[str, int] = {
    'normal':   0,
    'add':      1,
    'subtract': 2,
    'multiply': 3,
    'screen':   4,
    'overlay':  5,
    'mask':     6,
}

__all__ = [
    'get_context',
    'destroy_context',
    'get_texture_pool',
    'get_renderer',
    'load_shader',
    'GPUFrame',
    'BLEND_MODES',
]
