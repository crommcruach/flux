"""
Snow Effect Plugin - Adds falling snowflakes overlay
"""
import numpy as np
import cv2
import time
from plugins import PluginBase, PluginType, ParameterType


class SnowEffect(PluginBase):
    """
    Snow Effect - Adds animated falling snowflakes to frames.
    
    Generates particles that fall downward with optional wind drift.
    Customizable count, size, speed, and opacity.
    """
    
    METADATA = {
        'id': 'snow',
        'name': 'Falling Snow',
        'description': 'Add falling snowflakes overlay to frames',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Overlay'
    }
    
    PARAMETERS = [
        {
            'name': 'count',
            'label': 'Snowflake Count',
            'type': ParameterType.INT,
            'default': 100,
            'min': 10,
            'max': 1000,
            'step': 10,
            'description': 'Number of snowflakes'
        },
        {
            'name': 'speed',
            'label': 'Fall Speed',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.5,
            'max': 10.0,
            'step': 0.5,
            'description': 'Vertical fall speed (pixels per frame)'
        },
        {
            'name': 'wind',
            'label': 'Wind Drift',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': -5.0,
            'max': 5.0,
            'step': 0.1,
            'description': 'Horizontal wind drift (negative = left, positive = right)'
        },
        {
            'name': 'min_size',
            'label': 'Min Size',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 10,
            'step': 1,
            'description': 'Minimum snowflake size in pixels'
        },
        {
            'name': 'max_size',
            'label': 'Max Size',
            'type': ParameterType.INT,
            'default': 6,
            'min': 2,
            'max': 20,
            'step': 1,
            'description': 'Maximum snowflake size in pixels'
        },
        {
            'name': 'opacity',
            'label': 'Opacity',
            'type': ParameterType.FLOAT,
            'default': 0.8,
            'min': 0.1,
            'max': 1.0,
            'step': 0.1,
            'description': 'Snowflake opacity (0.0 = transparent, 1.0 = opaque)'
        },
        {
            'name': 'turbulence',
            'label': 'Turbulence',
            'type': ParameterType.FLOAT,
            'default': 0.3,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Random horizontal wobble intensity'
        },
        {
            'name': 'blur',
            'label': 'Motion Blur',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 5,
            'step': 1,
            'description': 'Motion blur amount (0 = none)'
        }
    ]
    
    def initialize(self, config):
        """Initialize snow effect with parameters."""
        self.count = config.get('count', 100)
        self.speed = config.get('speed', 2.0)
        self.wind = config.get('wind', 0.5)
        self.min_size = config.get('min_size', 2)
        self.max_size = config.get('max_size', 6)
        self.opacity = config.get('opacity', 0.8)
        self.turbulence = config.get('turbulence', 0.3)
        self.blur = config.get('blur', 0)
        
        # Initialize snowflake particles
        self.snowflakes = []
        self.frame_width = 0
        self.frame_height = 0
        self.last_update = time.time()
    
    def _init_snowflakes(self, width, height):
        """Initialize or reinitialize snowflake positions."""
        self.frame_width = width
        self.frame_height = height
        self.snowflakes = []
        
        for _ in range(self.count):
            snowflake = {
                'x': np.random.uniform(0, width),
                'y': np.random.uniform(-height, height),  # Spread vertically
                'size': np.random.uniform(self.min_size, self.max_size),
                'speed': np.random.uniform(self.speed * 0.7, self.speed * 1.3),
                'wind_offset': np.random.uniform(-self.turbulence, self.turbulence),
                'opacity': np.random.uniform(self.opacity * 0.5, self.opacity)
            }
            self.snowflakes.append(snowflake)
    
    def _update_snowflakes(self):
        """Update snowflake positions."""
        for flake in self.snowflakes:
            # Vertical movement
            flake['y'] += flake['speed']
            
            # Horizontal movement (wind + turbulence)
            wobble = np.random.uniform(-self.turbulence, self.turbulence)
            flake['x'] += self.wind + wobble
            
            # Wrap around horizontally
            if flake['x'] < 0:
                flake['x'] += self.frame_width
            elif flake['x'] > self.frame_width:
                flake['x'] -= self.frame_width
            
            # Reset at bottom
            if flake['y'] > self.frame_height:
                flake['y'] = -10
                flake['x'] = np.random.uniform(0, self.frame_width)
                flake['size'] = np.random.uniform(self.min_size, self.max_size)
                flake['speed'] = np.random.uniform(self.speed * 0.7, self.speed * 1.3)
                flake['opacity'] = np.random.uniform(self.opacity * 0.5, self.opacity)
    
    def process_frame(self, frame, **kwargs):
        """
        Add falling snow effect to frame.
        
        Args:
            frame: Input frame (RGB)
            
        Returns:
            Frame with snow overlay
        """
        height, width = frame.shape[:2]
        
        # Initialize snowflakes on first frame or if dimensions changed
        if len(self.snowflakes) != self.count or self.frame_width != width or self.frame_height != height:
            self._init_snowflakes(width, height)
        
        # Update snowflake positions
        self._update_snowflakes()
        
        # Create overlay
        overlay = frame.copy()
        
        # Draw each snowflake
        for flake in self.snowflakes:
            x = int(flake['x'])
            y = int(flake['y'])
            size = int(flake['size'])
            alpha = flake['opacity']
            
            # Skip if out of bounds
            if y < 0 or y >= height or x < 0 or x >= width:
                continue
            
            # Draw snowflake (white circle)
            if self.blur > 0:
                # Create small temporary canvas for blurred snowflake
                temp = np.zeros((size * 4, size * 4, 3), dtype=np.uint8)
                center = (size * 2, size * 2)
                cv2.circle(temp, center, size, (255, 255, 255), -1)
                temp = cv2.GaussianBlur(temp, (self.blur * 2 + 1, self.blur * 2 + 1), 0)
                
                # Blend onto overlay
                y1 = max(0, y - size * 2)
                y2 = min(height, y + size * 2)
                x1 = max(0, x - size * 2)
                x2 = min(width, x + size * 2)
                
                temp_y1 = size * 2 - (y - y1)
                temp_y2 = temp_y1 + (y2 - y1)
                temp_x1 = size * 2 - (x - x1)
                temp_x2 = temp_x1 + (x2 - x1)
                
                if temp_y2 > temp_y1 and temp_x2 > temp_x1:
                    region = overlay[y1:y2, x1:x2]
                    temp_crop = temp[temp_y1:temp_y2, temp_x1:temp_x2]
                    mask = (temp_crop > 0).any(axis=2)
                    region[mask] = cv2.addWeighted(region[mask], 1 - alpha, temp_crop[mask], alpha, 0)
            else:
                # Simple circle without blur
                color = (255, 255, 255)
                thickness = -1  # Filled
                
                # Create mask and blend
                mask = np.zeros((height, width), dtype=np.uint8)
                cv2.circle(mask, (x, y), size, 255, thickness)
                
                overlay = np.where(mask[:, :, None] > 0, 
                                   cv2.addWeighted(overlay, 1 - alpha, 
                                                   np.full_like(overlay, color), alpha, 0),
                                   overlay).astype(np.uint8)
        
        return overlay
    
    def get_parameters(self):
        """Return current parameter values."""
        return {
            'count': self.count,
            'speed': self.speed,
            'wind': self.wind,
            'min_size': self.min_size,
            'max_size': self.max_size,
            'opacity': self.opacity,
            'turbulence': self.turbulence,
            'blur': self.blur
        }
    
    def update_parameter(self, name, value):
        """Update a parameter value."""
        if name == 'count':
            self.count = max(10, min(1000, int(value)))
            # Reinitialize snowflakes with new count
            if self.frame_width > 0:
                self._init_snowflakes(self.frame_width, self.frame_height)
        elif name == 'speed':
            self.speed = max(0.5, min(10.0, float(value)))
        elif name == 'wind':
            self.wind = max(-5.0, min(5.0, float(value)))
        elif name == 'min_size':
            self.min_size = max(1, min(10, int(value)))
        elif name == 'max_size':
            self.max_size = max(2, min(20, int(value)))
        elif name == 'opacity':
            self.opacity = max(0.1, min(1.0, float(value)))
        elif name == 'turbulence':
            self.turbulence = max(0.0, min(2.0, float(value)))
        elif name == 'blur':
            self.blur = max(0, min(5, int(value)))
    
    def cleanup(self):
        """Cleanup resources."""
        self.snowflakes.clear()
