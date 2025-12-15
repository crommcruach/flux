"""
RGB Split Transition Plugin - Separates RGB channels during transition
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class RGBSplitTransition(PluginBase):
    """RGB Split Transition - Separates color channels with horizontal offset"""
    
    METADATA = {
        'id': 'rgb_split',
        'name': 'RGB Split',
        'description': 'RGB channel separation with glitch effect',
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
            'name': 'intensity',
            'label': 'Intensity',
            'type': ParameterType.FLOAT,
            'default': 30.0,
            'min': 5.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Maximum channel separation in pixels'
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
        self.duration = config.get('duration', 1.0)
        self.intensity = config.get('intensity', 30.0)
        self.easing = config.get('easing', 'ease_in_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress_eased = self._apply_easing(progress)
        progress_eased = np.clip(progress_eased, 0.0, 1.0)
        
        # Calculate split amount (peaks at 0.5 progress)
        split_progress = 1.0 - abs(2.0 * progress - 1.0)
        split_amount = int(self.intensity * split_progress)
        
        # Blend frames
        blended = cv2.addWeighted(
            frame_a, 1.0 - progress_eased,
            frame_b, progress_eased,
            0
        )
        
        # Split RGB channels
        h, w = blended.shape[:2]
        result = np.zeros_like(blended)
        
        b, g, r = cv2.split(blended)
        
        # Shift red channel right
        if split_amount > 0:
            result[:, split_amount:, 2] = r[:, :(w - split_amount)]
            result[:, :split_amount, 2] = r[:, :split_amount]
        else:
            result[:, :, 2] = r
        
        # Green channel stays centered
        result[:, :, 1] = g
        
        # Shift blue channel left
        if split_amount > 0:
            result[:, :(w - split_amount), 0] = b[:, split_amount:]
            result[:, (w - split_amount):, 0] = b[:, (w - split_amount):]
        else:
            result[:, :, 0] = b
        
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
        elif name == 'intensity':
            self.intensity = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'intensity': self.intensity, 'easing': self.easing}
    
    def cleanup(self):
        pass
