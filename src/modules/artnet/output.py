"""
ArtNet Output Data Model

Network target configuration for ArtNet routing:
- IP address and subnet
- Universe configuration
- FPS and timing
- Color correction (applied to all assigned objects)
- Delta encoding settings
- Object assignments (many-to-many)
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ArtNetOutput:
    """ArtNet network output target"""
    
    # Identity
    id: str                    # UUID (e.g., "out-456")
    name: str                  # Display name (e.g., "Main LED Wall")
    
    # Network Configuration
    target_ip: str             # Target IP address (e.g., "192.168.1.10")
    subnet: str                # Subnet mask (e.g., "255.255.255.0")
    start_universe: int        # Starting universe for this output
    
    # Protocol Settings
    fps: int = 30              # Frames per second
    delay: int = 0             # Delay in milliseconds
    active: bool = True        # Enable/disable output
    
    # Color Correction (applied to ALL objects on this output)
    brightness: int = 0        # -255 to 255
    contrast: int = 0          # -255 to 255
    red: int = 0               # -255 to 255
    green: int = 0             # -255 to 255
    blue: int = 0              # -255 to 255
    
    # Delta Encoding
    delta_enabled: bool = False
    delta_threshold: int = 8   # 0-255
    full_frame_interval: int = 30  # Frames
    
    # Object Assignments
    assigned_objects: List[str] = field(default_factory=list)  # List of object IDs
    
    def to_dict(self) -> dict:
        """Serialize to JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'targetIP': self.target_ip,
            'subnet': self.subnet,
            'startUniverse': self.start_universe,
            'fps': self.fps,
            'delay': self.delay,
            'active': self.active,
            'brightness': self.brightness,
            'contrast': self.contrast,
            'red': self.red,
            'green': self.green,
            'blue': self.blue,
            'deltaEnabled': self.delta_enabled,
            'deltaThreshold': self.delta_threshold,
            'fullFrameInterval': self.full_frame_interval,
            'assignedObjects': self.assigned_objects
        }
    
    @staticmethod
    def from_dict(data: dict) -> 'ArtNetOutput':
        """Deserialize from JSON"""
        return ArtNetOutput(
            id=data['id'],
            name=data['name'],
            target_ip=data['targetIP'],
            subnet=data['subnet'],
            start_universe=data['startUniverse'],
            fps=data.get('fps', 30),
            delay=data.get('delay', 0),
            active=data.get('active', True),
            brightness=data.get('brightness', 0),
            contrast=data.get('contrast', 0),
            red=data.get('red', 0),
            green=data.get('green', 0),
            blue=data.get('blue', 0),
            delta_enabled=data.get('deltaEnabled', False),
            delta_threshold=data.get('deltaThreshold', 8),
            full_frame_interval=data.get('fullFrameInterval', 30),
            assigned_objects=data.get('assignedObjects', [])
        )
