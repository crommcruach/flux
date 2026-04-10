"""
Slide Wipe Transition Plugin - Clips slide in from different directions
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class SlideWipeUpTransition(PluginBase):
    """Slide Wipe Up - Frame B slides in from bottom"""
    
    METADATA = {
        'id': 'slide_wipe_up',
        'name': 'Slide Wipe Up',
        'description': 'Frame B slides in from bottom',
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
            'default': 'ease_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 1.0)
        self.easing = config.get('easing', 'ease_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        offset = int(h * (1.0 - progress))
        
        result = frame_a.copy()
        if offset < h:
            result[offset:, :] = frame_b[:(h - offset), :]
        
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
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'easing': self.easing}
    
    def cleanup(self):
        pass


class SlideWipeDownTransition(PluginBase):
    """Slide Wipe Down - Frame B slides in from top"""
    
    METADATA = {
        'id': 'slide_wipe_down',
        'name': 'Slide Wipe Down',
        'description': 'Frame B slides in from top',
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
            'default': 'ease_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 1.0)
        self.easing = config.get('easing', 'ease_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        offset = int(h * progress)
        
        result = frame_a.copy()
        if offset > 0:
            result[:offset, :] = frame_b[(h - offset):, :]
        
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
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'easing': self.easing}
    
    def cleanup(self):
        pass


class SlideWipeLeftTransition(PluginBase):
    """Slide Wipe Left - Frame B slides in from right"""
    
    METADATA = {
        'id': 'slide_wipe_left',
        'name': 'Slide Wipe Left',
        'description': 'Frame B slides in from right',
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
            'default': 'ease_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 1.0)
        self.easing = config.get('easing', 'ease_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        offset = int(w * (1.0 - progress))
        
        result = frame_a.copy()
        if offset < w:
            result[:, offset:] = frame_b[:, :(w - offset)]
        
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
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'easing': self.easing}
    
    def cleanup(self):
        pass


class SlideWipeRightTransition(PluginBase):
    """Slide Wipe Right - Frame B slides in from left"""
    
    METADATA = {
        'id': 'slide_wipe_right',
        'name': 'Slide Wipe Right',
        'description': 'Frame B slides in from left',
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
            'default': 'ease_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 1.0)
        self.easing = config.get('easing', 'ease_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        offset = int(w * progress)
        
        result = frame_a.copy()
        if offset > 0:
            result[:, :offset] = frame_b[:, (w - offset):]
        
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
