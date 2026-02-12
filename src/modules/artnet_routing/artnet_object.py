"""
ArtNet Object Data Models

Contains data models for LED fixtures and coordinate points:
- ArtNetPoint: Single LED coordinate (x, y)
- ArtNetObject: LED fixture with full configuration
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math


@dataclass
class ArtNetPoint:
    """Single LED pixel coordinate"""
    id: int           # Sequential LED ID (1-based)
    x: float          # X coordinate on canvas
    y: float          # Y coordinate on canvas
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'x': self.x,
            'y': self.y
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetPoint':
        """Deserialize from JSON"""
        return ArtNetPoint(
            id=data['id'],
            x=data['x'],
            y=data['y']
        )


@dataclass
class ArtNetObject:
    """LED fixture with calculated coordinates"""
    
    # Identity
    id: str                      # UUID (e.g., "obj-123abc")
    name: str                    # Display name
    source_shape_id: str         # Editor shape ID (reference)
    type: str                    # Shape type (matrix, circle, line, star, etc.)
    
    # LED Coordinates
    points: List[ArtNetPoint] = field(default_factory=list)
    
    # LED Type Configuration
    led_type: str = 'RGB'        # RGB, RGBW, RGBAW, RGBWW, RGBCW, RGBCWW
    channels_per_pixel: int = 3  # 3-6 depending on LED type
    channel_order: str = 'RGB'   # Channel mapping (RGB, GRB, BGR, RGBW, etc.)
    
    # Universe Assignment
    universe_start: int = 1      # Starting universe
    universe_end: int = 1        # Ending universe (auto-calculated)
    
    # White Channel Configuration (for RGBW+ LEDs)
    white_detection: bool = False           # Enable white channel detection
    white_mode: str = 'luminance'           # luminance, average, minimum
    white_threshold: int = 200              # Threshold for white detection (0-255)
    white_behavior: str = 'hybrid'          # replace, additive, hybrid
    color_temp: int = 4500                  # Color temperature (K) for RGBWW/RGBCW
    
    # Color Correction
    brightness: int = 0          # -255 to 255
    contrast: int = 0            # -255 to 255
    red: int = 0                 # -255 to 255
    green: int = 0               # -255 to 255
    blue: int = 0                # -255 to 255
    
    # Timing
    delay: int = 0               # Delay in milliseconds
    
    # Layer Routing
    input_layer: str = 'player'  # 'player', 'layer1', ..., 'layer10'
    
    # Master-Slave Linking
    master_id: Optional[str] = None  # ID of master object (if this is slave)
    
    # Transform Properties (for frontend manipulation)
    rotation: float = 0.0         # Rotation in degrees
    scale_x: float = 1.0         # Scale X factor
    scale_y: float = 1.0         # Scale Y factor
    visible: bool = True          # Canvas visibility
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'sourceShapeId': self.source_shape_id,
            'type': self.type,
            'points': [p.to_dict() for p in self.points],
            'ledType': self.led_type,
            'channelsPerPixel': self.channels_per_pixel,
            'channelOrder': self.channel_order,
            'universeStart': self.universe_start,
            'universeEnd': self.universe_end,
            'whiteDetection': self.white_detection,
            'whiteMode': self.white_mode,
            'whiteThreshold': self.white_threshold,
            'whiteBehavior': self.white_behavior,
            'colorTemp': self.color_temp,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'delay': self.delay,
            'inputLayer': self.input_layer,
            'masterId': self.master_id,
            'rotation': self.rotation,
            'scaleX': self.scale_x,
            'scaleY': self.scale_y,
            'visible': self.visible
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetObject':
        """Deserialize from JSON"""
        return ArtNetObject(
            id=data['id'],
            name=data['name'],
            source_shape_id=data['sourceShapeId'],
            type=data['type'],
            points=[ArtNetPoint.from_dict(p) for p in data.get('points', [])],
            led_type=data.get('ledType', 'RGB'),
            channels_per_pixel=data.get('channelsPerPixel', 3),
            channel_order=data.get('channelOrder', 'RGB'),
            universe_start=data.get('universeStart', 1),
            universe_end=data.get('universeEnd', 1),
            white_detection=data.get('whiteDetection', False),
            white_mode=data.get('whiteMode', 'luminance'),
            white_threshold=data.get('whiteThreshold', 200),
            white_behavior=data.get('whiteBehavior', 'hybrid'),
            color_temp=data.get('colorTemp', 4500),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            delay=data.get('delay', 0),
            input_layer=data.get('inputLayer', 'player'),
            master_id=data.get('masterId'),
            rotation=data.get('rotation', 0.0),
            scale_x=data.get('scaleX', 1.0),
            scale_y=data.get('scaleY', 1.0),
            visible=data.get('visible', True)
        )
    
    def get_max_pixels_per_universe(self) -> int:
        """
        Calculate maximum pixels per universe based on LED type.
        
        ArtNet universes have 512 channels, but only 510 are usable for RGB data.
        
        Returns:
            Maximum number of pixels that fit in one universe
        """
        return 510 // self.channels_per_pixel
    
    def calculate_universe_range(self) -> Tuple[int, int]:
        """
        Calculate universe range needed for this object.
        
        Returns:
            Tuple of (start_universe, end_universe)
        """
        pixel_count = len(self.points)
        max_pixels_per_universe = self.get_max_pixels_per_universe()
        
        universes_needed = math.ceil(pixel_count / max_pixels_per_universe)
        
        return (self.universe_start, self.universe_start + universes_needed - 1)
