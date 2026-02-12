"""
ArtNet Output Routing Module

Manages ArtNet objects (LED fixtures), outputs (network targets), 
and routing assignments for the Py_artnet video player.

Core Components:
- ArtNetPoint: Single LED coordinate (x, y)
- ArtNetObject: LED fixture with spatial positioning and rendering properties
- ArtNetOutput: Network target with routing configuration
- PointGenerator: Convert editor shapes to LED coordinates
- ArtNetRoutingManager: Central manager for objects, outputs, and rendering (Phase 3)
"""

from .artnet_object import ArtNetPoint, ArtNetObject
from .artnet_output import ArtNetOutput
from .point_generator import PointGenerator
from .artnet_routing_manager import ArtNetRoutingManager

__all__ = [
    'ArtNetPoint',
    'ArtNetObject',
    'ArtNetOutput',
    'PointGenerator',
    'ArtNetRoutingManager',
]
