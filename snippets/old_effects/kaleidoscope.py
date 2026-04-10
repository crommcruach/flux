"""
Kaleidoscope Effect Plugin
Erstellt Spiegel-Segmente um einen Mittelpunkt für Kaleidoskop-Effekt.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator

class KaleidoscopeEffect(PluginBase):
    """Kaleidoscope - Mirror segments around center."""
    
    METADATA = {
        'id': 'kaleidoscope',
        'name': 'Kaleidoscope',
        'description': 'Mirror segments around center with rotation',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Simple 3D & Kaleidoscope'
    }
    
    PARAMETERS = [
        {
            'name': 'segments',
            'label': 'Segments',
            'type': ParameterType.INT,
            'default': 6,
            'min': 2,
            'max': 20,
            'description': 'Number of mirror segments'
        },
        {
            'name': 'rotation',
            'label': 'Rotation',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 360,
            'step': 5,
            'description': 'Rotation angle (degrees)'
        },
        {
            'name': 'center_x',
            'label': 'Center X',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Horizontal center position (0-1)'
        },
        {
            'name': 'center_y',
            'label': 'Center Y',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Vertical center position (0-1)'
        },
        {
            'name': 'zoom',
            'label': 'Zoom',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 3.0,
            'step': 0.1,
            'description': 'Zoom level'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.segments = int(config.get('segments', 6))
        self.rotation = int(config.get('rotation', 0))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
        self.zoom = float(config.get('zoom', 1.0))
        self.gpu = get_gpu_accelerator(config)
        self._map_x = None
        self._umat_x = None
        self._map_h = -1
        self._map_w = -1

    def _compute_maps(self, h, w):
        """Recompute kaleidoscope coordinate maps. Called once per parameter/size change."""
        center_x_px = self.center_x * w
        center_y_px = self.center_y * h
        angle_per_segment = 360.0 / self.segments
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        x = x - center_x_px
        y = y - center_y_px
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        theta_deg = np.degrees(theta) + self.rotation
        theta_deg = theta_deg % 360
        segment_angle = theta_deg % angle_per_segment
        segment_idx = (theta_deg / angle_per_segment).astype(int)
        mirror = segment_idx % 2 == 1
        segment_angle = np.where(mirror, angle_per_segment - segment_angle, segment_angle)
        theta_new = np.radians(segment_angle)
        r = r / self.zoom
        self._map_x = (r * np.cos(theta_new) + center_x_px).astype(np.float32)
        self._map_y = (r * np.sin(theta_new) + center_y_px).astype(np.float32)
        self._map_h = h
        self._map_w = w

    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Kaleidoscope."""
        h, w = frame.shape[:2]
        if self._map_x is None or self._map_h != h or self._map_w != w:
            self._compute_maps(h, w)
        return cv2.remap(frame, self._map_x, self._map_y,
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        self._map_x = None  # Invalidate coordinate maps
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'segments':
            self.segments = int(value)
            return True
        elif name == 'rotation':
            self.rotation = int(value)
            return True
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        elif name == 'zoom':
            self.zoom = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'segments': self.segments,
            'rotation': self.rotation,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'zoom': self.zoom
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
