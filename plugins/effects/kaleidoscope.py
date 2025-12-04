"""
Kaleidoscope Effect Plugin
Erstellt Spiegel-Segmente um einen Mittelpunkt für Kaleidoskop-Effekt.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

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
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Kaleidoscope."""
        h, w = frame.shape[:2]
        
        # Center-Position in Pixeln
        center_x_px = self.center_x * w
        center_y_px = self.center_y * h
        
        # Erstelle Output-Frame
        result = np.zeros_like(frame)
        
        # Winkel pro Segment
        angle_per_segment = 360.0 / self.segments
        
        # Erstelle Koordinaten-Grid
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        
        # Verschiebe Koordinaten zum Zentrum
        x = x - center_x_px
        y = y - center_y_px
        
        # Konvertiere zu Polar-Koordinaten
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        
        # Konvertiere zu Grad und addiere Rotation
        theta_deg = np.degrees(theta) + self.rotation
        
        # Normalisiere auf 0-360
        theta_deg = theta_deg % 360
        
        # Mappe jeden Winkel auf das erste Segment durch Spiegelung
        segment_angle = theta_deg % angle_per_segment
        
        # Spiegle jeden zweiten Segment-Abschnitt für Kaleidoskop-Effekt
        segment_idx = (theta_deg / angle_per_segment).astype(int)
        mirror = segment_idx % 2 == 1
        segment_angle = np.where(mirror, angle_per_segment - segment_angle, segment_angle)
        
        # Konvertiere zurück zu Radianten
        theta_new = np.radians(segment_angle)
        
        # Wende Zoom an
        r = r / self.zoom
        
        # Konvertiere zurück zu Kartesischen Koordinaten
        x_new = r * np.cos(theta_new) + center_x_px
        y_new = r * np.sin(theta_new) + center_y_px
        
        # Mappe Koordinaten
        map_x = x_new.astype(np.float32)
        map_y = y_new.astype(np.float32)
        
        # Remap Frame
        result = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
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
