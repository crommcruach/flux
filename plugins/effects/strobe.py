"""
Strobe Effect Plugin - Alternating blank frames
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class StrobeEffect(PluginBase):
    """
    Strobe Effect - Alterniert zwischen sichtbaren und schwarzen Frames.
    """
    
    METADATA = {
        'id': 'strobe',
        'name': 'Strobe',
        'description': 'Strobe-Licht-Effekt mit alternierenden Frames',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'frequency',
            'label': 'Frequency',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 30,
            'step': 1,
            'description': 'Strobe-Frequenz (alle N Frames ein Flash)'
        },
        {
            'name': 'duration',
            'label': 'Flash Duration',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 10,
            'step': 1,
            'description': 'Dauer des Flashes in Frames'
        },
        {
            'name': 'intensity',
            'label': 'Intensity',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Intensität des Strobes (0 = aus, 1 = volle Helligkeit)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Strobe-Parametern."""
        self.frequency = int(config.get('frequency', 2))
        self.duration = int(config.get('duration', 1))
        self.intensity = config.get('intensity', 1.0)
        self.frame_counter = 0
    
    def process_frame(self, frame, **kwargs):
        """
        Erstellt Strobe-Effekt durch alternierende Frames.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Strobe-Effekt
        """
        # Calculate position in strobe cycle
        cycle_position = self.frame_counter % self.frequency
        
        # Check if we're in flash duration
        if cycle_position < self.duration:
            # Show frame with intensity
            if self.intensity < 0.99:
                result = (frame.astype(np.float32) * self.intensity).astype(np.uint8)
            else:
                result = frame
        else:
            # Black frame
            result = np.zeros_like(frame)
        
        self.frame_counter += 1
        return result
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'frequency':
            self.frequency = max(1, int(value))
            return True
        elif name == 'duration':
            self.duration = max(1, int(value))
            return True
        elif name == 'intensity':
            self.intensity = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'frequency': self.frequency,
            'duration': self.duration,
            'intensity': self.intensity
        }
