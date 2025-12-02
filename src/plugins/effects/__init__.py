"""
Effect Plugins - Bildverarbeitung
"""
from .blend import BlendEffect
from .blur import BlurEffect
from .opacity import OpacityEffect
from .transform import TransformEffect
from .sharpen import SharpenEffect
from .emboss import EmbossEffect
from .sepia import SepiaEffect
from .gamma import GammaEffect
from .temperature import TemperatureEffect
from .channel_mixer import ChannelMixerEffect
from .noise import NoiseEffect
from .solarize import SolarizeEffect
from .duotone import DuotoneEffect
from .oil_paint import OilPaintEffect
from .mosaic import MosaicEffect
from .zoom import ZoomEffect
from .rotate import RotateEffect
from .border import BorderEffect
from .crop import CropEffect
from .flip import FlipEffect
from .mirror import MirrorEffect
from .slide import SlideEffect
from .keystone import KeystoneEffect
from .fisheye import FisheyeEffect
from .twist import TwistEffect
from .radial_blur import RadialBlurEffect
from .pixelate import PixelateEffect
from .displace import DisplaceEffect
from .wave_warp import WaveWarpEffect
from .shift_glitch import ShiftGlitchEffect
from .distortion import DistortionEffect
from .static import StaticEffect
from .shift_rgb import ShiftRGBEffect
from .edge_detection import EdgeDetectionEffect
from .auto_mask import AutoMaskEffect
from .chroma_key import ChromaKeyEffect
from .keystone_mask import KeystoneMaskEffect
from .vignette import VignetteEffect
from .drop_shadow import DropShadowEffect
from .kaleidoscope import KaleidoscopeEffect
from .tile import TileEffect
from .circles import CirclesEffect
from .bendoscope import BendoscopeEffect

__all__ = [
    'BlendEffect', 
    'BlurEffect', 
    'OpacityEffect', 
    'TransformEffect',
    'SharpenEffect',
    'EmbossEffect',
    'SepiaEffect',
    'GammaEffect',
    'TemperatureEffect',
    'ChannelMixerEffect',
    'NoiseEffect',
    'SolarizeEffect',
    'DuotoneEffect',
    'OilPaintEffect',
    'MosaicEffect',
    'ZoomEffect',
    'RotateEffect',
    'BorderEffect',
    'CropEffect',
    'FlipEffect',
    'MirrorEffect',
    'SlideEffect',
    'KeystoneEffect',
    'FisheyeEffect',
    'TwistEffect',
    'RadialBlurEffect',
    'PixelateEffect',
    'DisplaceEffect',
    'WaveWarpEffect',
    'ShiftGlitchEffect',
    'DistortionEffect',
    'StaticEffect',
    'ShiftRGBEffect',
    'EdgeDetectionEffect',
    'AutoMaskEffect',
    'ChromaKeyEffect',
    'KeystoneMaskEffect',
    'VignetteEffect',
    'DropShadowEffect',
    'KaleidoscopeEffect',
    'TileEffect',
    'CirclesEffect',
    'BendoscopeEffect'
]
