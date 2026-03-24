"""
Bendoscope Effect Plugin
Kombiniert Kaleidoskop mit kreisförmiger Biegung für psychedelische Effekte.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType
from src.modules.gpu.accelerator import get_gpu_accelerator

class BendoscopeEffect(PluginBase):
    """Bendoscope - Circular kaleidoscope with bending distortion."""
    
    METADATA = {
        'id': 'bendoscope',
        'name': 'Bendoscope',
        'description': 'Circular kaleidoscope with bending distortion',
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
            'name': 'bend_strength',
            'label': 'Bend Strength',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Circular bending intensity'
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
        },
        {
            'name': 'twist',
            'label': 'Twist',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -5.0,
            'max': 5.0,
            'step': 0.1,
            'description': 'Radial twist amount'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.segments = int(config.get('segments', 6))
        self.bend_strength = float(config.get('bend_strength', 0.5))
        self.rotation = int(config.get('rotation', 0))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
        self.zoom = float(config.get('zoom', 1.0))
        self.twist = float(config.get('twist', 0.0))
        self.gpu = get_gpu_accelerator(config)
        self._map_x = None
        self._umat_x = None
        self._map_h = -1
        self._map_w = -1

    def _compute_maps(self, h, w):
        """Recompute bendoscope coordinate maps. Called once per parameter/size change."""
        center_x_px = self.center_x * w
        center_y_px = self.center_y * h
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        x = x - center_x_px
        y = y - center_y_px
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        max_radius = np.sqrt((w / 2)**2 + (h / 2)**2)
        r_norm = r / max_radius
        r_bent = r * (1 + self.bend_strength * r_norm**2) if self.bend_strength != 0 else r
        theta_twisted = theta + (self.twist * r_norm * np.pi)
        angle_per_segment = 360.0 / self.segments
        theta_deg = np.degrees(theta_twisted) + self.rotation
        theta_deg = theta_deg % 360
        segment_angle = theta_deg % angle_per_segment
        segment_idx = (theta_deg / angle_per_segment).astype(int)
        mirror = segment_idx % 2 == 1
        segment_angle = np.where(mirror, angle_per_segment - segment_angle, segment_angle)
        theta_final = np.radians(segment_angle)
        r_final = r_bent / self.zoom
        self._map_x = (r_final * np.cos(theta_final) + center_x_px).astype(np.float32)
        self._map_y = (r_final * np.sin(theta_final) + center_y_px).astype(np.float32)
        self._map_h = h
        self._map_w = w
        if self.gpu.enabled:
            self._umat_x = cv2.UMat(self._map_x)
            self._umat_y = cv2.UMat(self._map_y)

    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Bendoscope."""
        h, w = frame.shape[:2]
        if self._map_x is None or self._map_h != h or self._map_w != w:
            self._compute_maps(h, w)
        if self.gpu.enabled:
            result = cv2.remap(cv2.UMat(frame), self._umat_x, self._umat_y,
                               cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            return result.get()
        return cv2.remap(frame, self._map_x, self._map_y,
                         cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        self._map_x = None  # Invalidate coordinate maps
        if name == 'segments':
            self.segments = int(value)
            return True
        elif name == 'bend_strength':
            self.bend_strength = float(value)
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
        elif name == 'twist':
            self.twist = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'segments': self.segments,
            'bend_strength': self.bend_strength,
            'rotation': self.rotation,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'zoom': self.zoom,
            'twist': self.twist
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
