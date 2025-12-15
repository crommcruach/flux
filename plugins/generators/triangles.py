"""
Triangles Generator Plugin - Triangular pattern like checkerboard
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class TrianglesGenerator(PluginBase):
    """Triangles Generator - Triangular pattern (▼▲▼▲)."""
    
    METADATA = {
        'id': 'triangles',
        'name': 'Triangles',
        'description': 'Triangular pattern like checkerboard',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'columns',
            'label': 'Columns',
            'type': ParameterType.INT,
            'default': 8,
            'min': 1,
            'max': 64,
            'step': 1,
            'description': 'Number of columns'
        },
        {
            'name': 'rows',
            'label': 'Rows',
            'type': ParameterType.INT,
            'default': 8,
            'min': 1,
            'max': 64,
            'step': 1,
            'description': 'Number of rows'
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
        self.columns = int(config.get('columns', 8))
        self.rows = int(config.get('rows', 8))
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
        
        # Calculate cell dimensions
        cell_width = width / self.columns
        cell_height = height / self.rows
        
        # Draw triangular pattern
        for row in range(int(self.rows)):
            for col in range(int(self.columns)):
                # Alternate triangle direction like checkerboard
                flip_up = (row + col) % 2 == 0
                
                # Calculate cell boundaries
                x_start = int(col * cell_width)
                x_end = int((col + 1) * cell_width)
                y_start = int(row * cell_height)
                y_end = int((row + 1) * cell_height)
                
                # Define triangle points
                if flip_up:
                    # Triangle pointing up: ▲
                    pts = np.array([
                        [x_start, y_end],           # Bottom left
                        [x_end, y_end],             # Bottom right
                        [(x_start + x_end) // 2, y_start]  # Top center
                    ], np.int32)
                else:
                    # Triangle pointing down: ▼
                    pts = np.array([
                        [x_start, y_start],         # Top left
                        [x_end, y_start],           # Top right
                        [(x_start + x_end) // 2, y_end]    # Bottom center
                    ], np.int32)
                
                # Fill triangle with white
                cv2.fillPoly(frame, [pts], (255, 255, 255))
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'columns':
            self.columns = max(1, min(64, int(value)))
            return True
        elif name == 'rows':
            self.rows = max(1, min(64, int(value)))
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
            'columns': self.columns,
            'rows': self.rows,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
