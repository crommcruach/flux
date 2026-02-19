"""
ArtNet Output Routing Module

Manages ArtNet objects (LED fixtures), outputs (network targets), 
and routing assignments for the Py_artnet video player.

Core Components:
- ArtNetPoint: Single LED coordinate (x, y)
- ArtNetObject: LED fixture with spatial positioning and rendering properties
- ArtNetOutput: Network target with routing configuration
- PointGenerator: Convert editor shapes to LED coordinates
- ArtNetRoutingManager: Central manager for objects, outputs, and assignments

Rendering Pipeline (NEW):
- ColorCorrector: Apply brightness, contrast, and RGB adjustments
- PixelSampler: Sample video frames at object coordinates
- RGBFormatMapper: Handle LED channel orders (RGB, GRB, RGBW, etc.)
- OutputManager: Complete frame rendering and DMX generation
- ArtNetSender: Network transmission via stupidArtnet per output
- RoutingBridge: Main integration point with player
"""

from .object import ArtNetPoint, ArtNetObject
from .output import ArtNetOutput
from .point_generator import PointGenerator
from .routing_manager import ArtNetRoutingManager
from .color_correction import ColorCorrector
from .pixel_sampler import PixelSampler
from .rgb_format_mapper import RGBFormatMapper
from .output_manager import OutputManager
from .sender import ArtNetSender
from .routing_bridge import RoutingBridge

__all__ = [
    'ArtNetPoint',
    'ArtNetObject',
    'ArtNetOutput',
    'PointGenerator',
    'ArtNetRoutingManager',
    'ColorCorrector',
    'PixelSampler',
    'RGBFormatMapper',
    'OutputManager',
    'ArtNetSender',
    'RoutingBridge',
]
