"""
Circles Effect Plugin
Mappt das Bild auf konzentrische Kreise für Circular Warp-Effekt.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class CirclesEffect(PluginBase):
    """Circles - Concentric circle mapping with zoom and rotation."""
    
    METADATA = {
        'id': 'circles',
        'name': 'Circles',
        'description': 'Concentric circle mapping with zoom and rotation',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Simple 3D & Kaleidoscope'
    }
    
    PARAMETERS = [
        {
            'name': 'frequency',
            'label': 'Frequency',
            'type': ParameterType.FLOAT,
            'default': 5.0,
            'min': 0.1,
            'max': 20.0,
            'step': 0.1,
            'description': 'Number of circular waves'
        },
        {
            'name': 'amplitude',
            'label': 'Amplitude',
            'type': ParameterType.FLOAT,
            'default': 0.2,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Wave displacement strength'
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
            'max': 5.0,
            'step': 0.1,
            'description': 'Zoom level'
        },
        {
            'name': 'mode',
            'label': 'Mode',
            'type': ParameterType.SELECT,
            'default': 'radial_warp',
            'options': ['radial_warp', 'circular_repeat', 'spiral'],
            'description': 'Circle mapping mode'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.frequency = float(config.get('frequency', 5.0))
        self.amplitude = float(config.get('amplitude', 0.2))
        self.rotation = int(config.get('rotation', 0))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
        self.zoom = float(config.get('zoom', 1.0))
        self.mode = str(config.get('mode', 'radial_warp'))
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Circles."""
        h, w = frame.shape[:2]
        
        # Center-Position in Pixeln
        center_x_px = self.center_x * w
        center_y_px = self.center_y * h
        
        # Erstelle Koordinaten-Grid
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        
        # Verschiebe zum Zentrum
        x = x - center_x_px
        y = y - center_y_px
        
        # Konvertiere zu Polar-Koordinaten
        r = np.sqrt(x**2 + y**2)
        theta = np.arctan2(y, x)
        
        # Normalisiere Radius
        max_radius = np.sqrt((w/2)**2 + (h/2)**2)
        r_norm = r / max_radius
        
        if self.mode == 'radial_warp':
            # Radiale Wellendistorsion
            wave = np.sin(r_norm * self.frequency * 2 * np.pi)
            r_new = r + wave * self.amplitude * max_radius
            theta_new = theta + np.radians(self.rotation)
            
        elif self.mode == 'circular_repeat':
            # Wiederhole Bild in konzentrischen Kreisen
            r_new = (r_norm * self.frequency) % 1.0 * max_radius / self.zoom
            theta_new = theta + np.radians(self.rotation)
            
        else:  # spiral
            # Spiralförmige Verzerrung
            spiral_offset = r_norm * self.frequency * 2 * np.pi
            theta_new = theta + spiral_offset + np.radians(self.rotation)
            r_new = r / self.zoom
        
        # Konvertiere zurück zu Kartesischen Koordinaten
        x_new = r_new * np.cos(theta_new) + center_x_px
        y_new = r_new * np.sin(theta_new) + center_y_px
        
        # Mappe Koordinaten
        map_x = x_new.astype(np.float32)
        map_y = y_new.astype(np.float32)
        
        # Remap Frame
        result = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'frequency':
            self.frequency = float(value)
            return True
        elif name == 'amplitude':
            self.amplitude = float(value)
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
        elif name == 'mode':
            self.mode = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'frequency': self.frequency,
            'amplitude': self.amplitude,
            'rotation': self.rotation,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'zoom': self.zoom,
            'mode': self.mode
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
