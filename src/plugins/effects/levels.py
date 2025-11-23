"""
Levels Effect Plugin - Input/Output levels adjustment
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class LevelsEffect(PluginBase):
    """
    Levels Effect - Input/Output Levels-Anpassung.
    """
    
    METADATA = {
        'id': 'levels',
        'name': 'Levels',
        'description': 'Input/Output Levels-Anpassung',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'input_min',
            'label': 'Input Min',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Input-Minimum (Schwarzpunkt)'
        },
        {
            'name': 'input_max',
            'label': 'Input Max',
            'type': ParameterType.FLOAT,
            'default': 255.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Input-Maximum (Weißpunkt)'
        },
        {
            'name': 'output_min',
            'label': 'Output Min',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Output-Minimum'
        },
        {
            'name': 'output_max',
            'label': 'Output Max',
            'type': ParameterType.FLOAT,
            'default': 255.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Output-Maximum'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Levels-Werten."""
        self.input_min = config.get('input_min', 0.0)
        self.input_max = config.get('input_max', 255.0)
        self.output_min = config.get('output_min', 0.0)
        self.output_max = config.get('output_max', 255.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Levels-Anpassung auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit angepassten Levels
        """
        # Check if levels are at defaults
        if (self.input_min == 0.0 and self.input_max == 255.0 and
            self.output_min == 0.0 and self.output_max == 255.0):
            return frame
        
        # Avoid division by zero
        input_range = max(self.input_max - self.input_min, 1.0)
        
        # Convert to float for calculations
        result = frame.astype(np.float32)
        
        # Map input range to 0-255
        result = (result - self.input_min) * (255.0 / input_range)
        result = np.clip(result, 0, 255)
        
        # Map to output range
        output_range = self.output_max - self.output_min
        result = (result / 255.0) * output_range + self.output_min
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'input_min':
            self.input_min = float(value)
        elif name == 'input_max':
            self.input_max = float(value)
        elif name == 'output_min':
            self.output_min = float(value)
        elif name == 'output_max':
            self.output_max = float(value)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'input_min': self.input_min,
            'input_max': self.input_max,
            'output_min': self.output_min,
            'output_max': self.output_max
        }
