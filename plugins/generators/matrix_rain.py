"""
Matrix Rain Generator Plugin - Falling green characters effect like in The Matrix
"""
import numpy as np
import random
from plugins import PluginBase, PluginType, ParameterType


class MatrixRainGenerator(PluginBase):
    """
    Matrix Rain Generator - Grüner Matrix-Regen.
    
    Vertikale Streifen mit fallenden Zeichen wie im Film Matrix.
    """
    
    METADATA = {
        'id': 'matrix_rain',
        'name': 'Matrix Rain',
        'description': 'Grüner Matrix-Regen mit fallenden Zeichen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }
    
    PARAMETERS = [
        {
            'name': 'num_strips',
            'label': 'Number of Strips',
            'type': ParameterType.INT,
            'default': 20,
            'min': 5,
            'max': 50,
            'step': 1,
            'description': 'Number of falling strips'
        },
        {
            'name': 'min_speed',
            'label': 'Min Speed',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.5,
            'max': 10.0,
            'step': 0.5,
            'description': 'Minimum fall speed'
        },
        {
            'name': 'max_speed',
            'label': 'Max Speed',
            'type': ParameterType.FLOAT,
            'default': 8.0,
            'min': 0.5,
            'max': 20.0,
            'step': 0.5,
            'description': 'Maximum fall speed'
        },
        {
            'name': 'detail',
            'label': 'Detail Level',
            'type': ParameterType.INT,
            'default': 10,
            'min': 5,
            'max': 20,
            'step': 1,
            'description': 'Rendering detail (lower = blockier, faster)'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 60,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.num_strips = config.get('num_strips', 20)
        self.min_speed = config.get('min_speed', 2.0)
        self.max_speed = config.get('max_speed', 8.0)
        self.detail = config.get('detail', 10)
        self.duration = config.get('duration', 10)
        self.time = 0.0
        self.rain_strips = {}
        self.initialized = False
        self.last_width = 0
        self.last_height = 0
    
    def _init_rain_strips(self, width, height):
        """Initialisiert die Regen-Streifen."""
        self.rain_strips.clear()
        
        for i in range(self.num_strips):
            self.rain_strips[i] = {
                'x': random.uniform(0, width),
                'y': random.uniform(-height * 0.5, 0),
                'speed': random.uniform(self.min_speed, self.max_speed),
                'length': random.uniform(20, 60),
                'brightness': random.uniform(0.6, 1.0)
            }
        
        self.initialized = True
        self.last_width = width
        self.last_height = height
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Matrix Rain Frame.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height', 'time' enthalten
            
        Returns:
            Generated frame
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        # Update internal time if not provided
        if 'time' not in kwargs:
            self.time += 1.0 / 30.0
            time = self.time
        
        # Initialize or reinitialize if dimensions changed
        if not self.initialized or width != self.last_width or height != self.last_height:
            self._init_rain_strips(width, height)
        
        # Update strip positions
        for strip in self.rain_strips.values():
            strip['y'] += strip['speed']
            
            # Reset if completely through
            if strip['y'] > height + strip['length']:
                strip['y'] = -strip['length']
                strip['x'] = random.uniform(0, width)
                strip['speed'] = random.uniform(self.min_speed, self.max_speed)
                strip['length'] = random.uniform(20, 60)
                strip['brightness'] = random.uniform(0.6, 1.0)
        
        # Create canvas
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Generate points grid
        step = self.detail
        for y in range(0, height, step):
            for x in range(0, width, step):
                # Find closest strip
                closest_strip = None
                min_distance = float('inf')
                
                for strip in self.rain_strips.values():
                    dx = abs(x - strip['x'])
                    dy = y - strip['y']
                    
                    # Check if point is in strip
                    if dx < 15 and 0 <= dy <= strip['length']:
                        distance = dx + abs(dy)
                        if distance < min_distance:
                            min_distance = distance
                            closest_strip = (strip, dy)
                
                if closest_strip:
                    strip, dy = closest_strip
                    
                    # Brightness based on position in strip
                    position_factor = 1.0 - (dy / strip['length'])
                    
                    # Horizontal distance dampening
                    dx = abs(x - strip['x'])
                    distance_factor = max(0, 1.0 - dx / 15)
                    
                    # Total intensity
                    intensity = position_factor * distance_factor * strip['brightness']
                    
                    # Head highlight (first 10% extra bright)
                    if dy < strip['length'] * 0.1:
                        head_boost = (1 - dy / (strip['length'] * 0.1)) * 0.5
                        intensity = min(1.0, intensity + head_boost)
                    
                    # Matrix green color
                    if intensity > 0.8:
                        # Very bright: almost white with green tint
                        r = int(200 * intensity)
                        g = 255
                        b = int(200 * intensity)
                    elif intensity > 0.5:
                        # Bright: bright green
                        r = int(100 * intensity)
                        g = int(255 * intensity)
                        b = int(100 * intensity)
                    else:
                        # Dark: dark green
                        r = 0
                        g = int(200 * intensity)
                        b = 0
                    
                    # Occasional flicker for "digital glitch" effect
                    if random.random() > 0.97:
                        r = int(r * 0.5)
                        g = int(g * 0.5)
                        b = int(b * 0.5)
                else:
                    # Black background with occasional faint glow
                    if random.random() > 0.98:
                        r, g, b = 0, random.randint(0, 30), 0
                    else:
                        r, g, b = 0, 0, 0
                
                # Draw block around point
                x_start = max(0, x - step//2)
                x_end = min(width, x + step//2)
                y_start = max(0, y - step//2)
                y_end = min(height, y + step//2)
                
                canvas[y_start:y_end, x_start:x_end] = [r, g, b]
        
        return canvas
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'num_strips':
            self.num_strips = int(value)
            self.initialized = False  # Force reinit
            return True
        elif name == 'min_speed':
            self.min_speed = float(value)
            return True
        elif name == 'max_speed':
            self.max_speed = float(value)
            return True
        elif name == 'detail':
            self.detail = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'num_strips': self.num_strips,
            'min_speed': self.min_speed,
            'max_speed': self.max_speed,
            'detail': self.detail
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        self.rain_strips.clear()
        self.initialized = False
