"""
ChromaKey Effect Plugin
Entfernt einen Hintergrund basierend auf einer Zielfarbe (Green/Blue Screen).
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class ChromaKeyEffect(PluginBase):
    """ChromaKey (Green/Blue Screen) Effekt."""
    
    METADATA = {
        'id': 'chroma_key',
        'name': 'Chroma Key',
        'description': 'Remove background by color (green/blue screen)',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }
    
    PARAMETERS = [
        {
            'name': 'key_color',
            'label': 'Key Color',
            'type': ParameterType.COLOR,
            'default': '#00ff00',
            'description': 'Color to remove (chroma key color)'
        },
        {
            'name': 'tolerance',
            'label': 'Tolerance',
            'type': ParameterType.INT,
            'default': 40,
            'min': 0,
            'max': 100,
            'step': 5,
            'description': 'Color matching tolerance (0-100)'
        },
        {
            'name': 'softness',
            'label': 'Edge Softness',
            'type': ParameterType.INT,
            'default': 10,
            'min': 0,
            'max': 50,
            'step': 5,
            'description': 'Edge feathering/blur amount'
        },
        {
            'name': 'spill_suppression',
            'label': 'Spill Suppression',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Reduce color spill on edges'
        },
        {
            'name': 'bg_color',
            'label': 'Background Color',
            'type': ParameterType.COLOR,
            'default': '#000000',
            'description': 'Replacement background color'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        key_color_hex = str(config.get('key_color', '#00ff00'))
        self.key_color = self._hex_to_bgr(key_color_hex)
        
        bg_color_hex = str(config.get('bg_color', '#000000'))
        self.bg_color = self._hex_to_bgr(bg_color_hex)
        
        self.tolerance = int(config.get('tolerance', 40))
        self.softness = int(config.get('softness', 10))
        self.spill_suppression = float(config.get('spill_suppression', 0.5))
    
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
        """Verarbeitet ein Frame mit ChromaKey."""
        h, w = frame.shape[:2]
        
        # Konvertiere zu HSV für besseres Color Matching
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Konvertiere Key-Color zu HSV
        key_color_bgr = np.uint8([[self.key_color]])
        key_color_hsv = cv2.cvtColor(key_color_bgr, cv2.COLOR_BGR2HSV)[0][0]
        
        # Berechne Toleranz-Range
        tolerance_hue = int(self.tolerance * 1.8)  # Hue hat 0-180 Range
        tolerance_sat = int(self.tolerance * 2.55)  # Sat/Val haben 0-255 Range
        
        lower_bound = np.array([
            max(0, key_color_hsv[0] - tolerance_hue),
            max(0, key_color_hsv[1] - tolerance_sat),
            max(0, key_color_hsv[2] - tolerance_sat)
        ])
        upper_bound = np.array([
            min(180, key_color_hsv[0] + tolerance_hue),
            min(255, key_color_hsv[1] + tolerance_sat),
            min(255, key_color_hsv[2] + tolerance_sat)
        ])
        
        # Erstelle Maske
        mask = cv2.inRange(hsv, lower_bound, upper_bound)
        mask = cv2.bitwise_not(mask)  # Invertiere (1 = behalten, 0 = entfernen)
        
        # Edge Softness (Blur)
        if self.softness > 0:
            kernel_size = self.softness * 2 + 1
            mask = cv2.GaussianBlur(mask, (kernel_size, kernel_size), 0)
        
        # Normalisiere Maske zu 0-1 Float
        alpha = mask.astype(float) / 255.0
        alpha = np.stack([alpha, alpha, alpha], axis=2)
        
        # Spill Suppression (reduziere Key-Color-Anteile an Kanten)
        if self.spill_suppression > 0:
            frame_float = frame.astype(float)
            
            # Berechne "wie grün/blau ist jedes Pixel"
            if key_color_hsv[0] < 90:  # Grün-basiert
                spill_mask = (frame_float[:,:,1] > frame_float[:,:,0]) & (frame_float[:,:,1] > frame_float[:,:,2])
                spill_amount = (frame_float[:,:,1] - np.maximum(frame_float[:,:,0], frame_float[:,:,2])) * self.spill_suppression
                frame_float[:,:,1] = np.where(spill_mask, frame_float[:,:,1] - spill_amount, frame_float[:,:,1])
            else:  # Blau-basiert
                spill_mask = (frame_float[:,:,0] > frame_float[:,:,1]) & (frame_float[:,:,0] > frame_float[:,:,2])
                spill_amount = (frame_float[:,:,0] - np.maximum(frame_float[:,:,1], frame_float[:,:,2])) * self.spill_suppression
                frame_float[:,:,0] = np.where(spill_mask, frame_float[:,:,0] - spill_amount, frame_float[:,:,0])
            
            frame = np.clip(frame_float, 0, 255).astype(np.uint8)
        
        # Erstelle Hintergrund
        background = np.full_like(frame, self.bg_color, dtype=np.uint8)
        
        # Alpha Blending
        result = (frame.astype(float) * alpha + background.astype(float) * (1 - alpha))
        result = np.clip(result, 0, 255).astype(np.uint8)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'key_color':
            self.key_color = self._hex_to_bgr(str(value))
            return True
        elif name == 'bg_color':
            self.bg_color = self._hex_to_bgr(str(value))
            return True
        elif name == 'tolerance':
            self.tolerance = int(value)
            return True
        elif name == 'softness':
            self.softness = int(value)
            return True
        elif name == 'spill_suppression':
            self.spill_suppression = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'key_color': self._bgr_to_hex(self.key_color),
            'bg_color': self._bgr_to_hex(self.bg_color),
            'tolerance': self.tolerance,
            'softness': self.softness,
            'spill_suppression': self.spill_suppression
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
