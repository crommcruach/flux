"""
Wipe Transition Plugins - Linear, Radial, and Round wipes
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class LinearWipeTransition(PluginBase):
    """Linear Wipe - Straight line wipe with angle control"""
    
    METADATA = {
        'id': 'linear_wipe',
        'name': 'Linear Wipe',
        'description': 'Straight line wipe with angle control',
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
            'name': 'angle',
            'label': 'Angle',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 360.0,
            'step': 15.0,
            'description': 'Wipe angle in degrees (0=left to right)'
        },
        {
            'name': 'feather',
            'label': 'Feather',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 200.0,
            'step': 10.0,
            'description': 'Edge softness in pixels'
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
        self.duration = config.get('duration', 1.0)
        self.angle = config.get('angle', 0.0)
        self.feather = config.get('feather', 50.0)
        self.easing = config.get('easing', 'linear')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        
        # Create coordinate grids
        y, x = np.mgrid[0:h, 0:w]
        
        # Convert angle to radians
        angle_rad = np.deg2rad(self.angle)
        
        # Calculate projection along wipe direction
        # Rotate coordinates
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # Project onto wipe axis
        projection = (x - w / 2) * cos_a + (y - h / 2) * sin_a
        
        # Normalize to 0-1 range
        max_dist = np.sqrt((w / 2) ** 2 + (h / 2) ** 2)
        projection = (projection + max_dist) / (2 * max_dist)
        
        # Calculate wipe position
        wipe_pos = progress
        
        # Create gradient mask with feathering
        if self.feather > 0:
            feather_norm = self.feather / max_dist
            mask = (projection - wipe_pos) / feather_norm + 0.5
            mask = np.clip(mask, 0.0, 1.0)
        else:
            mask = (projection >= wipe_pos).astype(np.float32)
        
        # Expand mask to 3 channels
        mask = np.stack([mask] * 3, axis=-1)
        
        # Blend frames using mask
        result = frame_a * (1.0 - mask) + frame_b * mask
        result = result.astype(np.uint8)
        
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
        elif name == 'angle':
            self.angle = float(value)
            return True
        elif name == 'feather':
            self.feather = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'angle': self.angle, 'feather': self.feather, 'easing': self.easing}
    
    def cleanup(self):
        pass


class RadialWipeTransition(PluginBase):
    """Radial Wipe - Clock-style wipe from center"""
    
    METADATA = {
        'id': 'radial_wipe',
        'name': 'Radial Wipe',
        'description': 'Clock-style radial wipe',
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
            'name': 'start_angle',
            'label': 'Start Angle',
            'type': ParameterType.FLOAT,
            'default': 90.0,
            'min': 0.0,
            'max': 360.0,
            'step': 15.0,
            'description': 'Starting angle in degrees (0=right, 90=top)'
        },
        {
            'name': 'clockwise',
            'label': 'Clockwise',
            'type': ParameterType.BOOL,
            'default': True,
            'description': 'Rotation direction'
        },
        {
            'name': 'feather',
            'label': 'Feather',
            'type': ParameterType.FLOAT,
            'default': 20.0,
            'min': 0.0,
            'max': 100.0,
            'step': 5.0,
            'description': 'Edge softness'
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
        self.duration = config.get('duration', 1.0)
        self.start_angle = config.get('start_angle', 90.0)
        self.clockwise = config.get('clockwise', True)
        self.feather = config.get('feather', 20.0)
        self.easing = config.get('easing', 'linear')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        h, w = frame_a.shape[:2]
        
        # Create coordinate grids centered at image center
        y, x = np.mgrid[0:h, 0:w]
        y = y - h / 2
        x = x - w / 2
        
        # Calculate angles (0 to 2*pi)
        angles = np.arctan2(y, x)
        
        # Convert to 0-360 degrees
        angles = np.rad2deg(angles)
        angles = (angles + 360) % 360
        
        # Adjust for start angle
        angles = (angles - self.start_angle + 360) % 360
        
        # Calculate sweep angle
        if self.clockwise:
            sweep = progress * 360
            mask = angles <= sweep
        else:
            sweep = progress * 360
            mask = angles >= (360 - sweep)
        
        # Apply feathering
        if self.feather > 0:
            feather_range = self.feather
            if self.clockwise:
                dist = angles - sweep
                dist = np.where(dist < 0, dist + 360, dist)
            else:
                target = 360 - sweep
                dist = angles - target
                dist = np.where(dist > 180, dist - 360, dist)
                dist = -dist
            
            mask = 1.0 - np.clip(dist / feather_range, 0.0, 1.0)
        else:
            mask = mask.astype(np.float32)
        
        # Expand mask to 3 channels
        mask = np.stack([mask] * 3, axis=-1)
        
        # Blend frames
        result = frame_a * (1.0 - mask) + frame_b * mask
        result = result.astype(np.uint8)
        
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
        elif name == 'start_angle':
            self.start_angle = float(value)
            return True
        elif name == 'clockwise':
            self.clockwise = bool(value)
            return True
        elif name == 'feather':
            self.feather = float(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'start_angle': self.start_angle, 'clockwise': self.clockwise, 'feather': self.feather, 'easing': self.easing}
    
    def cleanup(self):
        pass


class RoundWipeTransition(PluginBase):
    """Round Wipe - Circular wipe expanding from center"""
    
    METADATA = {
        'id': 'round_wipe',
        'name': 'Round Wipe',
        'description': 'Circular wipe expanding from center',
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
            'name': 'center_x',
            'label': 'Center X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Horizontal center position (0=left, 1=right)'
        },
        {
            'name': 'center_y',
            'label': 'Center Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Vertical center position (0=top, 1=bottom)'
        },
        {
            'name': 'feather',
            'label': 'Feather',
            'type': ParameterType.FLOAT,
            'default': 50.0,
            'min': 0.0,
            'max': 200.0,
            'step': 10.0,
            'description': 'Edge softness in pixels'
        },
        {
            'name': 'reverse',
            'label': 'Reverse',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Reverse direction (shrink instead of expand)'
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
        self.center_x = config.get('center_x', 0.5)
        self.center_y = config.get('center_y', 0.5)
        self.feather = config.get('feather', 50.0)
        self.reverse = config.get('reverse', False)
        self.easing = config.get('easing', 'ease_in_out')
    
    def blend_frames(self, frame_a: np.ndarray, frame_b: np.ndarray, progress: float) -> np.ndarray:
        if frame_a.shape != frame_b.shape:
            frame_b = cv2.resize(frame_b, (frame_a.shape[1], frame_a.shape[0]))
        
        progress = self._apply_easing(progress)
        progress = np.clip(progress, 0.0, 1.0)
        
        if self.reverse:
            progress = 1.0 - progress
        
        h, w = frame_a.shape[:2]
        
        # Calculate center position
        cx = int(w * self.center_x)
        cy = int(h * self.center_y)
        
        # Create coordinate grids
        y, x = np.mgrid[0:h, 0:w]
        
        # Calculate distance from center
        distances = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        
        # Calculate maximum distance to cover entire frame
        max_dist = np.sqrt(max(cx, w - cx) ** 2 + max(cy, h - cy) ** 2)
        
        # Calculate current radius
        radius = progress * max_dist
        
        # Create mask with feathering
        if self.feather > 0:
            mask = 1.0 - np.clip((distances - radius) / self.feather, 0.0, 1.0)
        else:
            mask = (distances <= radius).astype(np.float32)
        
        # Expand mask to 3 channels
        mask = np.stack([mask] * 3, axis=-1)
        
        # Blend frames
        if self.reverse:
            result = frame_b * (1.0 - mask) + frame_a * mask
        else:
            result = frame_a * (1.0 - mask) + frame_b * mask
        
        result = result.astype(np.uint8)
        
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
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        elif name == 'feather':
            self.feather = float(value)
            return True
        elif name == 'reverse':
            self.reverse = bool(value)
            return True
        elif name == 'easing':
            if value in ['linear', 'ease_in', 'ease_out', 'ease_in_out']:
                self.easing = value
                return True
        return False
    
    def get_parameters(self):
        return {'duration': self.duration, 'center_x': self.center_x, 'center_y': self.center_y, 'feather': self.feather, 'reverse': self.reverse, 'easing': self.easing}
    
    def cleanup(self):
        pass
