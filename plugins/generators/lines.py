"""
Lines Generator Plugin - Horizontal lines pattern
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class LinesGenerator(PluginBase):
    """Lines Generator - Horizontal lines pattern."""
    
    METADATA = {
        'id': 'lines',
        'name': 'Lines',
        'description': 'Horizontal lines pattern',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'line_count',
            'label': 'Line Count',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 100,
            'step': 1,
            'description': 'Number of horizontal lines'
        },
        {
            'name': 'line_width',
            'label': 'Line Width',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 20,
            'step': 1,
            'description': 'Width of each line in pixels'
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
        self.line_count = int(config.get('line_count', 10))
        self.line_width = int(config.get('line_width', 2))
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
        
        # Calculate spacing
        if self.line_count > 1:
            spacing = height / self.line_count
        else:
            spacing = height
        
        # Draw horizontal lines
        color = (self.color_b, self.color_g, self.color_r)  # BGR format
        for i in range(self.line_count):
            y = int(i * spacing + spacing / 2)
            y_start = max(0, y - self.line_width // 2)
            y_end = min(height, y + self.line_width // 2)
            frame[y_start:y_end, :] = color
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'line_count':
            self.line_count = max(1, min(100, int(value)))
            return True
        elif name == 'line_width':
            self.line_width = max(1, min(20, int(value)))
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
            'line_count': self.line_count,
            'line_width': self.line_width,
            'color_r': self.color_r,
            'color_g': self.color_g,
            'color_b': self.color_b,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
