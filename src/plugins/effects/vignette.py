"""
Vignette Effect Plugin
Dunkelt oder erhellt die Ränder des Bildes ab.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class VignetteEffect(PluginBase):
    """Vignette - Dunkelt/Erhellt Bildränder."""
    
    METADATA = {
        'id': 'vignette',
        'name': 'Vignette',
        'description': 'Darken or brighten edges with smooth falloff',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Strength',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': -1.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Vignette intensity (negative = brighten edges)'
        },
        {
            'name': 'radius',
            'label': 'Radius',
            'type': ParameterType.FLOAT,
            'default': 0.8,
            'min': 0.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Size of unaffected center area'
        },
        {
            'name': 'softness',
            'label': 'Softness',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.1,
            'max': 2.0,
            'step': 0.1,
            'description': 'Falloff smoothness'
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
            'name': 'shape',
            'label': 'Shape',
            'type': ParameterType.SELECT,
            'default': 'circular',
            'options': ['circular', 'rectangular'],
            'description': 'Vignette shape'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.strength = float(config.get('strength', 0.5))
        self.radius = float(config.get('radius', 0.8))
        self.softness = float(config.get('softness', 0.5))
        self.center_x = float(config.get('center_x', 0.5))
        self.center_y = float(config.get('center_y', 0.5))
        self.shape = str(config.get('shape', 'circular'))
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Vignette."""
        h, w = frame.shape[:2]
        
        # Erstelle Koordinaten-Grid
        y, x = np.ogrid[:h, :w]
        
        # Center-Position in Pixeln
        center_x_px = self.center_x * w
        center_y_px = self.center_y * h
        
        if self.shape == 'circular':
            # Normalisiere zu Aspekt-Ratio-korrigiertem Kreis
            aspect = w / h
            x_norm = (x - center_x_px) / w
            y_norm = (y - center_y_px) / h * aspect
            
            # Berechne Distanz vom Zentrum
            distance = np.sqrt(x_norm**2 + y_norm**2)
            
        else:  # rectangular
            # Manhattan-Distanz für rechteckige Form
            x_norm = np.abs(x - center_x_px) / (w / 2)
            y_norm = np.abs(y - center_y_px) / (h / 2)
            distance = np.maximum(x_norm, y_norm)
        
        # Berechne Vignette-Maske mit Falloff
        # radius = wo Vignette startet, softness = wie schnell sie abfällt
        mask = (distance - self.radius) / self.softness
        mask = np.clip(mask, 0, 1)
        
        # Smooth Falloff mit Cosinus-Kurve
        mask = (1 - np.cos(mask * np.pi)) / 2
        
        # Strength bestimmt Intensität (negativ = aufhellen)
        if self.strength >= 0:
            # Dunkeln: Multipliziere mit (1 - strength * mask)
            multiplier = 1 - (self.strength * mask)
        else:
            # Aufhellen: Addiere Helligkeit
            multiplier = 1 + (abs(self.strength) * mask)
        
        # Erweitere Maske zu 3 Channels
        multiplier = np.stack([multiplier, multiplier, multiplier], axis=2)
        
        # Wende Vignette an
        result = frame.astype(float) * multiplier
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'strength':
            self.strength = float(value)
            return True
        elif name == 'radius':
            self.radius = float(value)
            return True
        elif name == 'softness':
            self.softness = float(value)
            return True
        elif name == 'center_x':
            self.center_x = float(value)
            return True
        elif name == 'center_y':
            self.center_y = float(value)
            return True
        elif name == 'shape':
            self.shape = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'strength': self.strength,
            'radius': self.radius,
            'softness': self.softness,
            'center_x': self.center_x,
            'center_y': self.center_y,
            'shape': self.shape
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
