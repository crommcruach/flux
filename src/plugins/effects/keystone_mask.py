"""
Keystone Mask Effect Plugin
Maskiert Bereiche durch perspektivische Keystone-Transformation.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class KeystoneMaskEffect(PluginBase):
    """Keystone Mask - Maskiert Bereiche durch Perspektivtransformation."""
    
    METADATA = {
        'id': 'keystone_mask',
        'name': 'Keystone Mask',
        'description': 'Mask regions with keystone/perspective transformation',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }
    
    PARAMETERS = [
        {
            'name': 'top_left_x',
            'label': 'Top Left X',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Top-left corner X position (0-1)'
        },
        {
            'name': 'top_left_y',
            'label': 'Top Left Y',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Top-left corner Y position (0-1)'
        },
        {
            'name': 'top_right_x',
            'label': 'Top Right X',
            'type': ParameterType.FLOAT,
            'default': 0.9,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Top-right corner X position (0-1)'
        },
        {
            'name': 'top_right_y',
            'label': 'Top Right Y',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Top-right corner Y position (0-1)'
        },
        {
            'name': 'bottom_left_x',
            'label': 'Bottom Left X',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Bottom-left corner X position (0-1)'
        },
        {
            'name': 'bottom_left_y',
            'label': 'Bottom Left Y',
            'type': ParameterType.FLOAT,
            'default': 0.9,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Bottom-left corner Y position (0-1)'
        },
        {
            'name': 'bottom_right_x',
            'label': 'Bottom Right X',
            'type': ParameterType.FLOAT,
            'default': 0.9,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Bottom-right corner X position (0-1)'
        },
        {
            'name': 'bottom_right_y',
            'label': 'Bottom Right Y',
            'type': ParameterType.FLOAT,
            'default': 0.9,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Bottom-right corner Y position (0-1)'
        },
        {
            'name': 'invert',
            'label': 'Invert Mask',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['yes', 'no'],
            'description': 'Invert the mask (keep outside instead of inside)'
        },
        {
            'name': 'feather',
            'label': 'Edge Feather',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 50,
            'step': 5,
            'description': 'Blur mask edges for soft transition'
        },
        {
            'name': 'bg_color',
            'label': 'Background Color',
            'type': ParameterType.COLOR,
            'default': '#000000',
            'description': 'Color for masked regions'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.top_left_x = float(config.get('top_left_x', 0.1))
        self.top_left_y = float(config.get('top_left_y', 0.1))
        self.top_right_x = float(config.get('top_right_x', 0.9))
        self.top_right_y = float(config.get('top_right_y', 0.1))
        self.bottom_left_x = float(config.get('bottom_left_x', 0.1))
        self.bottom_left_y = float(config.get('bottom_left_y', 0.9))
        self.bottom_right_x = float(config.get('bottom_right_x', 0.9))
        self.bottom_right_y = float(config.get('bottom_right_y', 0.9))
        self.invert = str(config.get('invert', 'no'))
        self.feather = int(config.get('feather', 0))
        
        bg_color_hex = str(config.get('bg_color', '#000000'))
        self.bg_color = self._hex_to_bgr(bg_color_hex)
    
    def _hex_to_bgr(self, hex_color):
        """Konvertiert Hex-Farbe zu BGR Tupel."""
        # Convert to str to handle NumPy string types
        hex_color = str(hex_color).lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (b, g, r)
        return (0, 0, 0)
    
    def _bgr_to_hex(self, bgr):
        """Konvertiert BGR Tupel zu Hex."""
        b, g, r = bgr
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Keystone Mask."""
        h, w = frame.shape[:2]
        
        # Konvertiere normalisierte Koordinaten zu Pixeln
        src_pts = np.float32([
            [self.top_left_x * w, self.top_left_y * h],
            [self.top_right_x * w, self.top_right_y * h],
            [self.bottom_right_x * w, self.bottom_right_y * h],
            [self.bottom_left_x * w, self.bottom_left_y * h]
        ])
        
        # Ziel-Punkte (voller Frame)
        dst_pts = np.float32([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]
        ])
        
        # Berechne Perspektiv-Transformation
        try:
            matrix = cv2.getPerspectiveTransform(dst_pts, src_pts)
            
            # Erstelle Maske durch Warping eines weißen Rechtecks
            white_rect = np.ones((h, w), dtype=np.uint8) * 255
            mask = cv2.warpPerspective(white_rect, matrix, (w, h), 
                                       flags=cv2.INTER_LINEAR,
                                       borderMode=cv2.BORDER_CONSTANT,
                                       borderValue=0)
            
            # Invertiere Maske wenn gewünscht
            if self.invert == 'yes':
                mask = cv2.bitwise_not(mask)
            
            # Feather Edges
            if self.feather > 0:
                kernel_size = self.feather * 2 + 1
                mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
            
            # Normalisiere zu 0-1 Float
            alpha = mask.astype(float) / 255.0
            alpha = np.stack([alpha, alpha, alpha], axis=2)
            
            # Erstelle Hintergrund
            background = np.full_like(frame, self.bg_color, dtype=np.uint8)
            
            # Alpha Blending
            result = (frame.astype(float) * alpha + background.astype(float) * (1 - alpha))
            result = np.clip(result, 0, 255).astype(np.uint8)
            
            return result
            
        except Exception as e:
            # Bei ungültiger Transformation gebe Original zurück
            return frame
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'top_left_x':
            self.top_left_x = float(value)
            return True
        elif name == 'top_left_y':
            self.top_left_y = float(value)
            return True
        elif name == 'top_right_x':
            self.top_right_x = float(value)
            return True
        elif name == 'top_right_y':
            self.top_right_y = float(value)
            return True
        elif name == 'bottom_left_x':
            self.bottom_left_x = float(value)
            return True
        elif name == 'bottom_left_y':
            self.bottom_left_y = float(value)
            return True
        elif name == 'bottom_right_x':
            self.bottom_right_x = float(value)
            return True
        elif name == 'bottom_right_y':
            self.bottom_right_y = float(value)
            return True
        elif name == 'invert':
            self.invert = str(value)
            return True
        elif name == 'feather':
            self.feather = int(value)
            return True
        elif name == 'bg_color':
            self.bg_color = self._hex_to_bgr(str(value))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'top_left_x': self.top_left_x,
            'top_left_y': self.top_left_y,
            'top_right_x': self.top_right_x,
            'top_right_y': self.top_right_y,
            'bottom_left_x': self.bottom_left_x,
            'bottom_left_y': self.bottom_left_y,
            'bottom_right_x': self.bottom_right_x,
            'bottom_right_y': self.bottom_right_y,
            'invert': self.invert,
            'feather': self.feather,
            'bg_color': self._bgr_to_hex(self.bg_color)
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
