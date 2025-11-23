"""
Stop Motion Effect Plugin - Frame-Hold with frequency
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class StopMotionEffect(PluginBase):
    """
    Stop Motion Effect - Hält Frames für konfigurierbare Dauer (Stop-Motion-Look).
    """
    
    METADATA = {
        'id': 'stop_motion',
        'name': 'Stop Motion',
        'description': 'Frame-Hold Effekt für Stop-Motion-Look',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'hold_frames',
            'label': 'Hold Frames',
            'type': ParameterType.INT,
            'default': 3,
            'min': 2,
            'max': 30,
            'step': 1,
            'description': 'Anzahl Frames, für die ein Frame gehalten wird'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Hold-Frames."""
        self.hold_frames = int(config.get('hold_frames', 3))
        self.current_hold_frame = None
        self.frame_counter = 0
    
    def process_frame(self, frame, **kwargs):
        """
        Hält Frames für konfigurierbare Dauer.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Optional frame_number
            
        Returns:
            Gehaltenes Frame (Stop-Motion-Effekt)
        """
        # Check if we should capture a new frame
        if self.frame_counter % self.hold_frames == 0:
            self.current_hold_frame = frame.copy()
        
        self.frame_counter += 1
        
        # Return held frame (or current if none held yet)
        return self.current_hold_frame if self.current_hold_frame is not None else frame
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'hold_frames':
            self.hold_frames = max(1, int(value))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'hold_frames': self.hold_frames}
    
    def cleanup(self):
        """Cleanup held frame."""
        self.current_hold_frame = None
