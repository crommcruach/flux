"""
Fade Transition Plugin - Smooth crossfade between two frames
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class FadeTransition(PluginBase):
    """
    Fade Transition - Smooth crossfade between two frames.
    """
    
    METADATA = {
        'id': 'fade',
        'name': 'Fade',
        'description': 'Smooth crossfade transition between frames',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.TRANSITION,
        'category': 'Transitions'
    }
    
    PARAMETERS = [
        {
            'name': 'duration',
            'label': 'Duration',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Transition duration in seconds'
        },
        {
            'name': 'easing',
            'label': 'Easing',
            'type': ParameterType.SELECT,
            'default': 'linear',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Transition-Parametern."""
        self.duration = config.get('duration', 1.0)
        self.easing = config.get('easing', 'linear')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        """
        Mischt zwei Frames mit Fade-Transition.
        
        Args:
            frame_a: Frame A (Start-Frame, NumPy Array, BGR)
            frame_b: Frame B (End-Frame, NumPy Array, BGR)
            progress: Übergangs-Fortschritt (0.0 = nur A, 1.0 = nur B)
            
        Returns:
            Gemischtes Frame (NumPy Array, BGR)
        """
        # Ensure frames have same dimensions
        if frame_a.shape != frame_b.shape:
            # Resize frame_b to match frame_a
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        # Apply easing function to progress
        eased_progress = self._apply_easing(progress)
        
        # Clamp progress to [0.0, 1.0]
        eased_progress = np.clip(eased_progress, 0.0, 1.0)
        
        # Linear blend: result = frame_a * (1 - progress) + frame_b * progress
        result = cv2.addWeighted(
            frame_a, 1.0 - eased_progress,
            frame_b, eased_progress,
            0
        )
        
        return result
    
    def _apply_easing(self, progress: float) -> float:
        """
        Wendet Easing-Funktion auf Progress an.
        
        Args:
            progress: Linear progress (0.0 - 1.0)
            
        Returns:
            Eased progress (0.0 - 1.0)
        """
        if self.easing == 'linear':
            return progress
        elif self.easing == 'ease_in':
            # Quadratic ease-in: progress^2
            return progress * progress
        elif self.easing == 'ease_out':
            # Quadratic ease-out: 1 - (1 - progress)^2
            return 1.0 - (1.0 - progress) ** 2
        elif self.easing == 'ease_in_out':
            # Cubic ease-in-out
            if progress < 0.5:
                return 4.0 * progress ** 3
            else:
                return 1.0 - ((-2.0 * progress + 2.0) ** 3) / 2.0
        else:
            # Fallback to linear
            return progress
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'duration':
            self.duration = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'duration': self.duration,
            'easing': self.easing
        }
    
    def cleanup(self):
        """Cleanup resources."""
        pass
