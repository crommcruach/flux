"""
Fish Eye Effect Plugin - Spherical Distortion
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator


class FisheyeEffect(PluginBase):
    """
    Fish Eye Effect - Sphärische Linsenverzerrung (Fischaugen-Effekt).
    """
    
    METADATA = {
        'id': 'fisheye',
        'name': 'Fish Eye',
        'description': 'Sphärische Linsenverzerrung für Fischaugen- oder Kugel-Effekt',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Verzerrungsstärke (>0 = Fisheye, <0 = Barrel-Invert, 0 = keine Verzerrung)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Fisheye-Stärke."""
        self.strength = float(config.get('strength', 0.5))
        self.gpu = get_gpu_accelerator(config)
        self._map_x = None  # Cached maps (None = recompute needed)
        self._umat_x = None  # GPU UMat maps (uploaded once, reused every frame)
        self._map_h = -1
        self._map_w = -1

    def _compute_maps(self, h, w):
        """Recompute fisheye coordinate maps. Called once per parameter/size change."""
        cx = w / 2.0
        cy = h / 2.0
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        dx = (x - cx) / cx
        dy = (y - cy) / cy
        r = np.sqrt(dx**2 + dy**2)
        r_safe = np.where(r > 0, r, 1)
        theta = np.arctan(r_safe * self.strength)
        r_new = np.where(r > 0, theta / self.strength, 0)
        factor = np.where(r > 0, r_new / r_safe, 1)
        self._map_x = (cx + dx * cx * factor).astype(np.float32)
        self._map_y = (cy + dy * cy * factor).astype(np.float32)
        self._map_h = h
        self._map_w = w
        if self.gpu.enabled:
            self._umat_x = cv2.UMat(self._map_x)
            self._umat_y = cv2.UMat(self._map_y)

    def process_frame(self, frame, **kwargs):
        """
        Wendet Fisheye-Verzerrung auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verzerrtes Frame
        """
        if abs(self.strength) < 0.01:
            return frame
        
        h, w = frame.shape[:2]
        if self._map_x is None or self._map_h != h or self._map_w != w:
            self._compute_maps(h, w)
        if self.gpu.enabled:
            result = cv2.remap(cv2.UMat(frame), self._umat_x, self._umat_y,
                               cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=(0, 0, 0))
            return result.get()
        return cv2.remap(frame, self._map_x, self._map_y,
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(0, 0, 0))
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        self._map_x = None  # Invalidate coordinate maps
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']

        if name == 'strength':
            self.strength = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'strength': self.strength
        }
