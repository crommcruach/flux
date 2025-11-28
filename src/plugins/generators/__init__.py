"""
Generator Plugins - Procedural frame generation
"""
from .plasma import PlasmaGenerator
from .rainbow_wave import RainbowWaveGenerator
from .pulse import PulseGenerator
from .fire import FireGenerator
from .matrix_rain import MatrixRainGenerator
from .checkerboard import CheckerboardGenerator
from .webcam import WebcamGenerator
from .livestream import LiveStreamGenerator
from .screencapture import ScreencaptureGenerator
from .static_picture import StaticPictureGenerator

__all__ = [
    'PlasmaGenerator',
    'RainbowWaveGenerator', 
    'PulseGenerator',
    'FireGenerator',
    'MatrixRainGenerator',
    'CheckerboardGenerator',
    'WebcamGenerator',
    'LiveStreamGenerator',
    'ScreencaptureGenerator',
    'StaticPictureGenerator'
]
