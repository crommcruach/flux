"""
Effect Plugins — GPU-shader effects only.

Active effects (all use WGSL shaders via get_shader()/get_uniforms()):
  - TransformEffect      — position, scale, rotation (transform.wgsl)
  - BrightnessContrastEffect — brightness/contrast (brightness_contrast.wgsl)
  - ColorizeEffect       — hue/saturation colorize (colorize.wgsl)
  - HueRotateEffect      — hue rotation (hue_rotate.wgsl)
  - BlendModeEffect      — 14-mode color blend (blend_mode.wgsl)

Special exception (CPU, required by core playback engine):
  - TransportEffect      — frame position, speed, trim, loop control
"""
from .transform import TransformEffect
from .brightness_contrast import BrightnessContrastEffect
from .colorize import ColorizeEffect
from .hue_rotate import HueRotateEffect
from .blend_mode import BlendModeEffect
from .transport import TransportEffect

__all__ = [
    'TransformEffect',
    'BrightnessContrastEffect',
    'ColorizeEffect',
    'HueRotateEffect',
    'BlendModeEffect',
    'TransportEffect',
]
