"""
Generator Plugins - Procedural frame generation
"""
from .plasma import PlasmaGenerator
from .rainbow_wave import RainbowWaveGenerator
from .pulse import PulseGenerator
from .fire import FireGenerator
from .matrix_rain import MatrixRainGenerator
from .rtsp_stream import RTSPStreamGenerator

__all__ = [
    'PlasmaGenerator',
    'RainbowWaveGenerator', 
    'PulseGenerator',
    'FireGenerator',
    'MatrixRainGenerator',
    'RTSPStreamGenerator'
]
