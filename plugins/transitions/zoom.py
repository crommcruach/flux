"""
Zoom Transition Plugins - Punch zoom in and out effects
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class PunchZoomInTransition(PluginBase):
    """Punch Zoom In - Zooms into frame B with impact"""
    
    METADATA = {
        'id': 'punch_zoom_in',
        'name': 'Punch Zoom In',
        'description': 'Zooms into next frame with impact',
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
            'default': 0.8,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Transition duration in seconds'
        },
        {
            'name': 'zoom_amount',
            'label': 'Zoom Amount',
            'type': ParameterType.FLOAT,
            'default': 1.5,
            'min': 1.1,
            'max': 3.0,
            'step': 0.1,
            'description': 'Maximum zoom scale'
        },
        {
            'name': 'center_x',
            'label': 'Center X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Horizontal zoom center (0=left, 1=right)'
        },
        {
            'name': 'center_y',
            'label': 'Center Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Vertical zoom center (0=top, 1=bottom)'
        },
        {
            'name': 'easing',
            'label': 'Easing',
            'type': ParameterType.SELECT,
            'default': 'ease_in',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing function for transition'
        }
    ]
    
    def initialize(self, config):
        self.duration = config.get('duration', 0.8)
        self.zoom_amount = config.get('zoom_amount', 1.5)
        self.center_x = config.get('center_x', 0.5)
        self.center_y = config.get('center_y', 0.5)
        self.easing = config.get('easing', 'ease_in')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        
        # Calculate zoom scale (starts small, zooms to normal)
        scale = 1.0 / (1.0 + (self.zoom_amount - 1.0) * (1.0 - progress))
        
        # Calculate center point
        cx = int(w * self.center_x)
        cy = int(h * self.center_y)
        
        # Calculate zoomed dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize frame_b
        if new_w > 0 and new_h > 0:
            zoomed = cv2.resize(frame_b, (new_w, new_h))
            
            # Calculate crop/paste coordinates
            start_x = max(0, cx - new_w // 2)
            start_y = max(0, cy - new_h // 2)
            end_x = min(w, start_x + new_w)
            end_y = min(h, start_y + new_h)
            
            # Calculate source coordinates
            src_start_x = max(0, new_w // 2 - cx)
            src_start_y = max(0, new_h // 2 - cy)
            src_end_x = src_start_x + (end_x - start_x)
            src_end_y = src_start_y + (end_y - start_y)
            
            # Create result starting with frame_a
            result = frame_a.copy()
            
            # Paste zoomed frame_b
            if src_end_x > src_start_x and src_end_y > src_start_y:
                result[start_y:end_y, start_x:end_x] = zoomed[src_start_y:src_end_y, src_start_x:src_end_x]
            
            # Blend based on progress
            result = cv2.addWeighted(
                frame_a, 1.0 - progress,
                result, progress,
                0
            )
        else:
            result = frame_a
        
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
        elif name == 'zoom_amount':
            self.zoom_amount = float(value)
            return True
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'zoom_amount': self.zoom_amount, 'center_x': self.center_x, 'center_y': self.center_y, 'easing': self.easing}
    
    def cleanup(self):
        pass


class PunchZoomOutTransition(PluginBase):
    """Punch Zoom Out - Zooms out from frame A with impact"""
    
    METADATA = {
        'id': 'punch_zoom_out',
        'name': 'Punch Zoom Out',
        'description': 'Zooms out from current frame with impact',
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
            'default': 0.8,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Transition duration in seconds'
        },
        {
            'name': 'zoom_amount',
            'label': 'Zoom Amount',
            'type': ParameterType.FLOAT,
            'default': 1.5,
            'min': 1.1,
            'max': 3.0,
            'step': 0.1,
            'description': 'Maximum zoom scale'
        },
        {
            'name': 'center_x',
            'label': 'Center X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Horizontal zoom center (0=left, 1=right)'
        },
        {
            'name': 'center_y',
            'label': 'Center Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Vertical zoom center (0=top, 1=bottom)'
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
        self.duration = config.get('duration', 0.8)
        self.zoom_amount = config.get('zoom_amount', 1.5)
        self.center_x = config.get('center_x', 0.5)
        self.center_y = config.get('center_y', 0.5)
        self.easing = config.get('easing', 'ease_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        
        # Calculate zoom scale (starts normal, zooms out)
        scale = 1.0 + (self.zoom_amount - 1.0) * progress
        
        # Calculate center point
        cx = int(w * self.center_x)
        cy = int(h * self.center_y)
        
        # Calculate zoomed dimensions
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize frame_a
        if new_w > 0 and new_h > 0:
            zoomed = cv2.resize(frame_a, (new_w, new_h))
            
            # Calculate crop coordinates centered on zoom point
            crop_start_x = max(0, (new_w - w) // 2 + (cx - w // 2))
            crop_start_y = max(0, (new_h - h) // 2 + (cy - h // 2))
            crop_end_x = min(new_w, crop_start_x + w)
            crop_end_y = min(new_h, crop_start_y + h)
            
            # Crop zoomed frame
            cropped = zoomed[crop_start_y:crop_end_y, crop_start_x:crop_end_x]
            
            # If cropped size doesn't match, resize
            if cropped.shape[0] != h or cropped.shape[1] != w:
                cropped = cv2.resize(cropped, (w, h))
            
            # Blend with frame_b based on progress
            result = cv2.addWeighted(
                cropped, 1.0 - progress,
                frame_b, progress,
                0
            )
        else:
            result = frame_b
        
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
        elif name == 'zoom_amount':
            self.zoom_amount = float(value)
            return True
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'zoom_amount': self.zoom_amount, 'center_x': self.center_x, 'center_y': self.center_y, 'easing': self.easing}
    
    def cleanup(self):
        pass
