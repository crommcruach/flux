"""
Camera Lens Blur Transition Plugin - Simulates camera focus change
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class CameraLensBlurTransition(PluginBase):
    """Camera Lens Blur - Simulates focus rack between frames"""
    
    METADATA = {
        'id': 'camera_lens_blur',
        'name': 'Camera Lens Blur',
        'description': 'Simulates camera focus change with blur',
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
            'default': 1.5,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Transition duration in seconds'
        },
        {
            'name': 'blur_amount',
            'label': 'Blur Amount',
            'type': ParameterType.FLOAT,
            'default': 25.0,
            'min': 5.0,
            'max': 51.0,
            'step': 2.0,
            'description': 'Maximum blur kernel size (odd numbers only)'
        },
        {
            'name': 'easing',
            'label': 'Easing',
            'type': ParameterType.SELECT,
            'default': 'ease_in_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 1.5)
        self.blur_amount = config.get('blur_amount', 25.0)
        self.easing = config.get('easing', 'ease_in_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress_eased = self._apply_easing(progress)
        progress_eased = np.clip(progress_eased, 0.0, 1.0)
        
        # Calculate blur intensity (peaks at 0.5 progress)
        blur_intensity = 1.0 - abs(2.0 * progress_eased - 1.0)
        kernel_size = int(self.blur_amount * blur_intensity)
        
        # Ensure kernel size is odd and at least 1
        kernel_size = max(1, kernel_size)
        if kernel_size % 2 == 0:
            kernel_size += 1
        
        # Apply blur based on progress
        if progress_eased < 0.5:
            # First half: blur frame_a
            if kernel_size > 1:
                blurred_a = cv2.GaussianBlur(frame_a, (kernel_size, kernel_size), 0)
            else:
                blurred_a = frame_a
            
            # Crossfade from frame_a to blurred midpoint
            local_progress = progress_eased * 2.0
            result = cv2.addWeighted(
                frame_a, 1.0 - local_progress,
                blurred_a, local_progress,
                0
            )
        else:
            # Second half: blur frame_b and transition
            if kernel_size > 1:
                blurred_b = cv2.GaussianBlur(frame_b, (kernel_size, kernel_size), 0)
            else:
                blurred_b = frame_b
            
            # Crossfade from blurred midpoint to frame_b
            local_progress = (progress_eased - 0.5) * 2.0
            
            # At midpoint, fully crossfade between frames
            if progress_eased <= 0.5:
                result = blurred_b
            else:
                result = cv2.addWeighted(
                    blurred_b, 1.0 - local_progress,
                    frame_b, local_progress,
                    0
                )
        
        # Always blend with opposite frame based on overall progress
        result = cv2.addWeighted(
            frame_a, 1.0 - progress_eased,
            frame_b, progress_eased,
            0
        )
        
        # Apply blur to result
        if kernel_size > 1:
            result = cv2.GaussianBlur(result, (kernel_size, kernel_size), 0)
        
        return result
    
    def _apply_easing(self, progress: float) -> float:
        if self.easing == 'linear':
            return progress
        elif self.easing == 'ease_in':
            return progress * progress
        elif self.easing == 'ease_out':
            return 1.0 - (1.0 - progress) ** 2
        elif self.easing == 'ease_in_out':
            if progress < 0.5:
                return 2.0 * progress * progress
            else:
                return 1.0 - 2.0 * (1.0 - progress) ** 2
        return progress
    
    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'duration':
            self.duration = float(value)
            return True
        elif name == 'blur_amount':
            self.blur_amount = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'blur_amount': self.blur_amount, 'easing': self.easing}
    
    def cleanup(self):
        pass
