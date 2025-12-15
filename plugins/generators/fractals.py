"""
Fractals Generator Plugin - Simple 2D fractals
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class FractalsGenerator(PluginBase):
    """Fractals Generator - Sierpinski triangle, hex, square fractals."""
    
    METADATA = {
        'id': 'fractals',
        'name': 'Fractals',
        'description': 'Simple 2D fractals (Sierpinski triangle, hex, square)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'fractal_type',
            'label': 'Fractal Type',
            'type': ParameterType.SELECT,
            'default': 'triangle',
            'options': ['triangle', 'square', 'hex'],
            'description': 'Type of fractal pattern'
        },
        {
            'name': 'depth',
            'label': 'Depth',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 8,
            'step': 1,
            'description': 'Fractal recursion depth'
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
        self.fractal_type = config.get('fractal_type', 'triangle')
        self.depth = int(config.get('depth', 5))
        self.color_r = int(config.get('color_r', 255))
        self.color_g = int(config.get('color_g', 255))
        self.color_b = int(config.get('color_b', 255))
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
        self.time = 0.0
    
    def _draw_sierpinski_triangle(self, frame, p1, p2, p3, depth):
        """Draw Sierpinski triangle recursively."""
        if depth == 0:
            pts = np.array([p1, p2, p3], np.int32)
            color = (self.color_b, self.color_g, self.color_r)
            cv2.fillPoly(frame, [pts], color)
        else:
            # Calculate midpoints
            m1 = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            m2 = ((p2[0] + p3[0]) // 2, (p2[1] + p3[1]) // 2)
            m3 = ((p3[0] + p1[0]) // 2, (p3[1] + p1[1]) // 2)
            
            # Recursively draw three smaller triangles
            self._draw_sierpinski_triangle(frame, p1, m1, m3, depth - 1)
            self._draw_sierpinski_triangle(frame, m1, p2, m2, depth - 1)
            self._draw_sierpinski_triangle(frame, m3, m2, p3, depth - 1)
    
    def _draw_sierpinski_square(self, frame, x, y, size, depth):
        """Draw Sierpinski carpet (square fractal) recursively."""
        if depth == 0 or size < 1:
            color = (self.color_b, self.color_g, self.color_r)
            cv2.rectangle(frame, (x, y), (x + size, y + size), color, -1)
        else:
            new_size = size // 3
            for i in range(3):
                for j in range(3):
                    # Skip center square (that's what makes it Sierpinski)
                    if i == 1 and j == 1:
                        continue
                    new_x = x + i * new_size
                    new_y = y + j * new_size
                    self._draw_sierpinski_square(frame, new_x, new_y, new_size, depth - 1)
    
    def _draw_hex_fractal(self, frame, cx, cy, radius, depth):
        """Draw hexagonal fractal recursively."""
        if depth == 0 or radius < 2:
            # Draw hexagon
            pts = []
            for i in range(6):
                angle = np.pi / 3 * i
                x = int(cx + radius * np.cos(angle))
                y = int(cy + radius * np.sin(angle))
                pts.append([x, y])
            pts = np.array(pts, np.int32)
            color = (self.color_b, self.color_g, self.color_r)
            cv2.fillPoly(frame, [pts], color)
        else:
            new_radius = radius // 3
            # Center hex
            self._draw_hex_fractal(frame, cx, cy, new_radius, depth - 1)
            # Six surrounding hexes
            for i in range(6):
                angle = np.pi / 3 * i
                new_cx = int(cx + radius * 2/3 * np.cos(angle))
                new_cy = int(cy + radius * 2/3 * np.sin(angle))
                self._draw_hex_fractal(frame, new_cx, new_cy, new_radius, depth - 1)
    
    def process_frame(self, frame, **kwargs):
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        self.time = time
        
        # Create black canvas
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw fractal based on type
        if self.fractal_type == 'triangle':
            # Sierpinski triangle
            margin = min(width, height) // 10
            p1 = (width // 2, margin)
            p2 = (margin, height - margin)
            p3 = (width - margin, height - margin)
            self._draw_sierpinski_triangle(frame, p1, p2, p3, self.depth)
        
        elif self.fractal_type == 'square':
            # Sierpinski carpet
            size = min(width, height) - 4
            x = (width - size) // 2
            y = (height - size) // 2
            self._draw_sierpinski_square(frame, x, y, size, self.depth)
        
        elif self.fractal_type == 'hex':
            # Hexagonal fractal
            cx = width // 2
            cy = height // 2
            radius = min(width, height) // 2 - 5
            self._draw_hex_fractal(frame, cx, cy, radius, self.depth)
        
        return frame
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'fractal_type':
            if value in ['triangle', 'square', 'hex']:
                self.fractal_type = value
                return True
        elif name == 'depth':
            self.depth = max(1, min(8, int(value)))
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
            'fractal_type': self.fractal_type,
            'depth': self.depth,
            'color_r': self.color_r,
            'color_g': self.color_g,
            'color_b': self.color_b,
            'duration': self.duration
        }
    
    def cleanup(self):
        pass
