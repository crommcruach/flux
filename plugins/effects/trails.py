"""
Trails Effect Plugin - Ghost-Trails with frame blending
"""
import cv2
import numpy as np
from collections import deque
from plugins import PluginBase, PluginType, ParameterType


class TrailsEffect(PluginBase):
    """
    Trails Effect - Erstellt Ghost-Trails durch Frame-Blending mit Historie.
    """
    
    METADATA = {
        'id': 'trails',
        'name': 'Trails',
        'description': 'Ghost-Trails Effekt durch Frame-Blending',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'length',
            'label': 'Trail Length',
            'type': ParameterType.INT,
            'default': 5,
            'min': 2,
            'max': 30,
            'step': 1,
            'description': 'Anzahl der Frames für Trail-Historie'
        },
        {
            'name': 'decay',
            'label': 'Decay',
            'type': ParameterType.FLOAT,
            'default': 0.7,
            'min': 0.1,
            'max': 0.99,
            'step': 0.05,
            'description': 'Decay-Faktor für ältere Frames (höher = länger sichtbar)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Trail-Parametern."""
        self.length = int(config.get('length', 5))
        self.decay = config.get('decay', 0.7)
        self.frame_history = deque(maxlen=self.length)
    
    def process_frame(self, frame, **kwargs):
        """
        Erstellt Ghost-Trails durch Blending mit Frame-Historie.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Trails
        """
        # Add current frame to history
        self.frame_history.append(frame.copy())
        
        if len(self.frame_history) < 2:
            return frame  # Not enough history yet
        
        # OPTIMIZED: Pre-convert all frames to float32 (avoid conversion in loop)
        result = np.zeros_like(frame, dtype=np.float32)
        total_weight = 0.0
        
        # Pre-convert current frame
        frames_float = [f.astype(np.float32) for f in self.frame_history]
        
        # Blend from oldest to newest
        for i, hist_frame in enumerate(frames_float):
            # Calculate weight (exponential decay)
            weight = self.decay ** (len(frames_float) - i - 1)
            result += hist_frame * weight
            total_weight += weight
        
        # Normalize by total weight
        result /= total_weight
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'length':
            new_length = int(value)
            if new_length != self.length:
                self.length = new_length
                # Recreate deque with new maxlen
                old_frames = list(self.frame_history)
                self.frame_history = deque(old_frames, maxlen=self.length)
            return True
        elif name == 'decay':
            self.decay = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'length': self.length,
            'decay': self.decay
        }
    
    def cleanup(self):
        """Cleanup frame history."""
        self.frame_history.clear()
