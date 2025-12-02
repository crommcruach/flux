"""
Twist Effect Plugin - Swirl/Twirl Distortion
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class TwistEffect(PluginBase):
    """
    Twist Effect - Dreht das Bild spiralförmig um das Zentrum (Swirl/Twirl).
    """
    
    METADATA = {
        'id': 'twist',
        'name': 'Twist',
        'description': 'Spiralförmige Drehung um das Zentrum (Swirl/Twirl-Effekt)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Transform'
    }
    
    PARAMETERS = [
        {
            'name': 'angle',
            'label': 'Winkel',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -360.0,
            'max': 360.0,
            'step': 5.0,
            'description': 'Twist-Winkel in Grad (+ = im Uhrzeigersinn, - = gegen Uhrzeigersinn)'
        },
        {
            'name': 'radius',
            'label': 'Radius',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 10.0,
            'max': 200.0,
            'step': 5.0,
            'description': 'Effekt-Radius in % (Bereich der Verzerrung vom Zentrum)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Twist-Parametern."""
        self.angle = float(config.get('angle', 0.0))
        self.radius = float(config.get('radius', 100.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Twist-Effekt auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Verdrehtes Frame
        """
        if abs(self.angle) < 0.1:
            return frame
        
        h, w = frame.shape[:2]
        
        # Zentrum des Bildes
        cx = w / 2.0
        cy = h / 2.0
        
        # Maximaler Radius (für Normalisierung)
        max_radius = min(w, h) / 2.0 * (self.radius / 100.0)
        
        # Winkel in Radians
        twist_angle = np.radians(self.angle)
        
        # Erstelle Mesh-Grid (VIEL schneller als For-Schleife!)
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        
        # Distanz vom Zentrum
        dx = x - cx
        dy = y - cy
        distance = np.sqrt(dx**2 + dy**2)
        
        # Berechne Twist-Faktor (stärker im Zentrum)
        factor = np.where(distance < max_radius, 
                         1.0 - (distance / max_radius),
                         0)
        rotation = twist_angle * factor
        
        # Rotiere um Zentrum (vektorisiert)
        cos_r = np.cos(rotation)
        sin_r = np.sin(rotation)
        
        # Neue Koordinaten
        new_x = cos_r * dx - sin_r * dy + cx
        new_y = sin_r * dx + cos_r * dy + cy
        
        # Map nur innerhalb des Radius, sonst Original
        map_x = np.where(distance < max_radius, new_x, x).astype(np.float32)
        map_y = np.where(distance < max_radius, new_y, y).astype(np.float32)
        
        # Wende Remap an
        twisted = cv2.remap(frame, map_x, map_y,
                           interpolation=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_CONSTANT,
                           borderValue=(0, 0, 0))
        
        return twisted
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'angle':
            self.angle = float(value)
            return True
        elif name == 'radius':
            self.radius = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'angle': self.angle,
            'radius': self.radius
        }
