"""
Fire Generator Plugin - Realistic fire effect with flickering flames
"""
import numpy as np
import math
import random
from plugins import PluginBase, PluginType, ParameterType


class FireGenerator(PluginBase):
    """
    Fire Generator - Realistischer Feuer-Effekt.
    
    Flackernde Flammen in Gelb/Orange/Rot die von unten nach oben züngeln.
    """
    
    METADATA = {
        'id': 'fire',
        'name': 'Fire',
        'description': 'Realistisches Feuer mit flackernden Flammen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }
    
    PARAMETERS = [
        {
            'name': 'intensity',
            'label': 'Fire Intensity',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Overall fire intensity'
        },
        {
            'name': 'turbulence',
            'label': 'Turbulence',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 3.0,
            'step': 0.1,
            'description': 'Flame flicker amount'
        },
        {
            'name': 'speed',
            'label': 'Animation Speed',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Animation speed multiplier'
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
        self.intensity = config.get('intensity', 1.0)
        self.turbulence = config.get('turbulence', 1.0)
        self.speed = config.get('speed', 1.0)
        self.detail = config.get('detail', 10)
        self.duration = config.get('duration', 10)
        self.time = 0.0
        self.noise_offset = 0.0
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Fire Frame.
        
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
        
        # Update noise
        self.noise_offset += 0.05 * self.speed
        t = time * self.speed
        
        # Create canvas
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Generate points grid
        step = self.detail
        for y in range(0, height, step):
            for x in range(0, width, step):
                # Normalize positions
                norm_y = y / height
                norm_x = x / width
                
                # Base intensity: hotter at bottom
                base_intensity = (1.0 - norm_y ** 0.7) * self.intensity
                
                # Turbulence with multiple frequencies
                turb = (
                    math.sin(norm_x * 8 + t * 2) * 0.3 +
                    math.sin(norm_x * 15 + t * 3 + self.noise_offset) * 0.2 +
                    math.sin(norm_x * 20 - t * 4) * 0.15
                ) * self.turbulence
                
                # Vertical flame tongues
                flame_wave = math.sin(norm_x * 10 + t * 1.5) * (1 - norm_y) * 0.4
                
                # Random sparkle
                sparkle = random.random() * 0.1 if random.random() > 0.95 else 0
                
                # Combine all effects
                intensity = base_intensity + turb + flame_wave + sparkle
                intensity = max(0, min(1.0, intensity))
                
                # Fire color gradient
                if intensity > 0.8:
                    # Very hot: almost white/bright yellow
                    r, g, b = 255, int(255 * (0.8 + intensity * 0.2)), int(200 * (intensity - 0.8) * 5)
                elif intensity > 0.6:
                    # Hot: bright yellow-orange
                    r, g, b = 255, int(200 + (intensity - 0.6) * 275), int(50 * (intensity - 0.6))
                elif intensity > 0.4:
                    # Medium: orange
                    r, g, b = 255, int(100 + (intensity - 0.4) * 500), 0
                elif intensity > 0.2:
                    # Cool: dark orange/red
                    r, g, b = int(180 + (intensity - 0.2) * 375), int((intensity - 0.2) * 500), 0
                elif intensity > 0.05:
                    # Very cool: dark red/embers
                    r, g, b = int(intensity * 900), int(intensity * 200), 0
                else:
                    # Black/no fire
                    r, g, b = int(intensity * 500), 0, 0
                
                # Clamp values
                r = max(0, min(255, r))
                g = max(0, min(255, g))
                b = max(0, min(255, b))
                
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
        
        if name == 'intensity':
            self.intensity = float(value)
            return True
        elif name == 'turbulence':
            self.turbulence = float(value)
            return True
        elif name == 'speed':
            self.speed = float(value)
            return True
        elif name == 'detail':
            self.detail = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'intensity': self.intensity,
            'turbulence': self.turbulence,
            'speed': self.speed,
            'detail': self.detail
        }
