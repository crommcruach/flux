"""
Circles Generator Plugin - Draw circles pattern
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class CirclesGenerator(PluginBase):
    """Circles Generator - Draw circles pattern."""
    
    METADATA = {
        'id': 'circles',
        'name': 'Circles',
        'description': 'Draw circles pattern',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'circle_count',
            'label': 'Circle Count',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 50,
            'step': 1,
            'description': 'Number of circles'
        },
        {
            'name': 'radius',
            'label': 'Radius',
            'type': ParameterType.INT,
            'default': 20,
            'min': 5,
            'max': 100,
            'step': 1,
            'description': 'Circle radius in pixels'
        },
        {
            'name': 'thickness',
            'label': 'Thickness',
            'type': ParameterType.INT,
            'default': 2,
            'min': -1,
            'max': 20,
            'step': 1,
            'description': 'Line thickness (-1 for filled)'
        },
        {
            'name': 'color_r',
            'label': 'Red',
            'type': ParameterType.INT,
            'default': 255,
            'min': 0,
            'max': 255,
            'step': 1,
            'description': 'Red color component'
        },
        {
            'name': 'color_g',
            'label': 'Green',
            'type': ParameterType.INT,
            'default': 255,
            'min': 0,
            'max': 255,
            'step': 1,
            'description': 'Green color component'
        },
        {
            'name': 'color_b',
            'label': 'Blue',
            'type': ParameterType.INT,
            'default': 255,
            'min': 0,
            'max': 255,
            'step': 1,
            'description': 'Blue color component'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.STRING,
            'default': '10',
            'description': 'Playback duration in seconds (1-60)'
        }
    ]
    
    def initialize(self, config):
        self.circle_count = int(config.get('circle_count', 5))
        self.radius = int(config.get('radius', 20))
        self.thickness = int(config.get('thickness', 2))
        self.color_r = int(config.get('color_r', 255))
        self.color_g = int(config.get('color_g', 255))
        self.color_b = int(config.get('color_b', 255))
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
        self.time = 0.0
    
    def process_frame(self, frame, **kwargs):
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        self.time = time
        
        # Create black canvas
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw circles
        color = (self.color_b, self.color_g, self.color_r)  # BGR format
        
        # Calculate grid layout
        cols = int(np.ceil(np.sqrt(self.circle_count)))
        rows = int(np.ceil(self.circle_count / cols))
        
        cell_width = width / cols
        cell_height = height / rows
        
        circle_idx = 0
        for row in range(rows):
            for col in range(cols):
                if circle_idx >= self.circle_count:
                    break
                
                # Calculate center position
                cx = int((col + 0.5) * cell_width)
                cy = int((row + 0.5) * cell_height)
                
                # Draw circle
                cv2.circle(frame, (cx, cy), self.radius, color, self.thickness)
                circle_idx += 1
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'circle_count':
            self.circle_count = max(1, min(50, int(value)))
            return True
        elif name == 'radius':
            self.radius = max(5, min(100, int(value)))
            return True
        elif name == 'thickness':
            self.thickness = max(-1, min(20, int(value)))
            return True
        elif name == 'color_r':
            self.color_r = max(0, min(255, int(value)))
            return True
        elif name == 'color_g':
            self.color_g = max(0, min(255, int(value)))
            return True
        elif name == 'color_b':
            self.color_b = max(0, min(255, int(value)))
            return True
        elif name == 'duration':
            try:
                self.duration = max(1, min(60, float(value)))
            except (ValueError, TypeError):
                self.duration = 10
            return True
        return False
    
    def get_parameters(self):
        return {
            'circle_count': self.circle_count,
            'radius': self.radius,
            'thickness': self.thickness,
            'color_r': self.color_r,
            'color_g': self.color_g,
            'color_b': self.color_b,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
