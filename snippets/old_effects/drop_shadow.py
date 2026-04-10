"""
Drop Shadow Effect Plugin
Fügt einen Schatten mit konfigurierbarem Offset, Blur und Opacity hinzu.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class DropShadowEffect(PluginBase):
    """Drop Shadow - Fügt Schatten hinzu."""
    
    METADATA = {
        'id': 'drop_shadow',
        'name': 'Drop Shadow',
        'description': 'Add shadow with offset, blur, and opacity',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }
    
    PARAMETERS = [
        {
            'name': 'offset_x',
            'label': 'Offset X',
            'type': ParameterType.INT,
            'default': 10,
            'min': -100,
            'max': 100,
            'step': 5,
            'description': 'Horizontal shadow offset (pixels)'
        },
        {
            'name': 'offset_y',
            'label': 'Offset Y',
            'type': ParameterType.INT,
            'default': 10,
            'min': -100,
            'max': 100,
            'step': 5,
            'description': 'Vertical shadow offset (pixels)'
        },
        {
            'name': 'blur',
            'label': 'Blur',
            'type': ParameterType.INT,
            'default': 15,
            'min': 0,
            'max': 50,
            'step': 5,
            'description': 'Shadow blur amount'
        },
        {
            'name': 'opacity',
            'label': 'Opacity',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Shadow opacity (0-1)'
        },
        {
            'name': 'color',
            'label': 'Shadow Color',
            'type': ParameterType.COLOR,
            'default': '#000000',
            'description': 'Shadow color'
        },
        {
            'name': 'detection_mode',
            'label': 'Detection Mode',
            'type': ParameterType.SELECT,
            'default': 'brightness',
            'options': ['brightness', 'edges', 'full_frame'],
            'description': 'How to detect content for shadow'
        },
        {
            'name': 'threshold',
            'label': 'Threshold',
            'type': ParameterType.INT,
            'default': 30,
            'min': 0,
            'max': 255,
            'step': 5,
            'description': 'Brightness threshold for shadow detection'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.offset_x = int(config.get('offset_x', 10))
        self.offset_y = int(config.get('offset_y', 10))
        self.blur = int(config.get('blur', 15))
        self.opacity = float(config.get('opacity', 0.5))
        self.detection_mode = str(config.get('detection_mode', 'brightness'))
        self.threshold = int(config.get('threshold', 30))
        
        color_hex = str(config.get('color', '#000000'))
        self.color = self._hex_to_bgr(color_hex)
    
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
        """Verarbeitet ein Frame mit Drop Shadow."""
        h, w = frame.shape[:2]
        
        # Erstelle Shadow-Maske basierend auf Detection Mode
        if self.detection_mode == 'brightness':
            # Nutze Helligkeit als Maske
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
            
        elif self.detection_mode == 'edges':
            # Nutze Kanten-Detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, self.threshold, self.threshold * 2)
            # Dilate edges um Schatten zu vergrößern
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.dilate(edges, kernel, iterations=2)
            
        else:  # full_frame
            # Ganzes Frame bekommt Schatten
            mask = np.ones((h, w), dtype=np.uint8) * 255
        
        # Erstelle größere Canvas für Offset
        pad = max(abs(self.offset_x), abs(self.offset_y)) + self.blur * 2
        padded_h = h + pad * 2
        padded_w = w + pad * 2
        
        # Erstelle Shadow-Layer
        shadow = np.zeros((padded_h, padded_w), dtype=np.uint8)
        
        # Platziere Maske mit Offset
        y_start = pad + self.offset_y
        x_start = pad + self.offset_x
        shadow[y_start:y_start+h, x_start:x_start+w] = mask
        
        # Blur Shadow
        if self.blur > 0:
            kernel_size = self.blur * 2 + 1
            shadow = cv2.GaussianBlur(shadow, (kernel_size, kernel_size), 0)
        
        # Crop zurück zu Original-Größe
        shadow = shadow[pad:pad+h, pad:pad+w]
        
        # Normalisiere Shadow-Maske
        shadow_alpha = shadow.astype(float) / 255.0 * self.opacity
        shadow_alpha = np.stack([shadow_alpha, shadow_alpha, shadow_alpha], axis=2)
        
        # Erstelle farbigen Shadow
        shadow_colored = np.full_like(frame, self.color, dtype=np.uint8)
        
        # Composite: Shadow unter Frame
        # Zuerst Shadow auf schwarzem Hintergrund
        result = shadow_colored.astype(float) * shadow_alpha
        
        # Dann Original-Frame darüber (mit invertierter Shadow-Alpha als Maske)
        # Frame sollte da erscheinen, wo er hell genug ist (detection_mode)
        if self.detection_mode == 'full_frame':
            # Bei full_frame: Frame einfach vollständig darüber
            frame_alpha = np.ones_like(shadow_alpha)
        else:
            # Bei anderen Modi: Nutze Detection-Maske
            frame_mask = mask.astype(float) / 255.0
            frame_alpha = np.stack([frame_mask, frame_mask, frame_mask], axis=2)
        
        # Blend Frame über Shadow
        result = result * (1 - frame_alpha) + frame.astype(float) * frame_alpha
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'offset_x':
            self.offset_x = int(value)
            return True
        elif name == 'offset_y':
            self.offset_y = int(value)
            return True
        elif name == 'blur':
            self.blur = int(value)
            return True
        elif name == 'opacity':
            self.opacity = float(value)
            return True
        elif name == 'color':
            self.color = self._hex_to_bgr(str(value))
            return True
        elif name == 'detection_mode':
            self.detection_mode = str(value)
            return True
        elif name == 'threshold':
            self.threshold = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'blur': self.blur,
            'opacity': self.opacity,
            'color': self._bgr_to_hex(self.color),
            'detection_mode': self.detection_mode,
            'threshold': self.threshold
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
