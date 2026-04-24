"""
Generator Plugins - Procedural frame generation
"""
from .plasma import PlasmaGenerator
from .rainbow_wave import RainbowWaveGenerator
from .pulse import PulseGenerator
from .fire import FireGenerator
from .checkerboard import CheckerboardGenerator
from .lines import LinesGenerator
from .circles import CirclesGenerator
from .triangles import TrianglesGenerator
from .oscillator import OscillatorGenerator
from .noise import NoiseGenerator

__all__ = [
    'PlasmaGenerator',
    'RainbowWaveGenerator',
    'PulseGenerator',
    'FireGenerator',
    'CheckerboardGenerator',
    'LinesGenerator',
    'CirclesGenerator',
    'TrianglesGenerator',
    'OscillatorGenerator',
    'NoiseGenerator',
]
