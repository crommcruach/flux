"""
Auto Mask Effect Plugin - Automatic Background Removal
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class AutoMaskEffect(PluginBase):
    """
    Auto Mask Effect - Automatische Hintergrundentfernung durch Bewegungserkennung oder Schwellwert.
    """
    
    METADATA = {
        'id': 'auto_mask',
        'name': 'Auto Mask',
        'description': 'Automatische Maskierung durch Bewegungs- oder Helligkeitserkennung',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Edge & Detection'
    }
    
    PARAMETERS = [
        {
            'name': 'mode',
            'label': 'Modus',
            'type': ParameterType.SELECT,
            'default': 'brightness',
            'options': ['brightness', 'color_range', 'edges'],
            'description': 'Masken-Methode (brightness = Helligkeit, color_range = Farbbereich, edges = Kantenerkennung)'
        },
        {
            'name': 'threshold',
            'label': 'Schwellwert',
            'type': ParameterType.INT,
            'default': 127,
            'min': 0,
            'max': 255,
            'step': 5,
            'description': 'Schwellwert für Brightness-Modus (dunkler = transparent)'
        },
        {
            'name': 'tolerance',
            'label': 'Toleranz',
            'type': ParameterType.INT,
            'default': 30,
            'min': 0,
            'max': 100,
            'step': 5,
            'description': 'Toleranz für Color Range Modus'
        },
        {
            'name': 'invert',
            'label': 'Invertieren',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['no', 'yes'],
            'description': 'Invertiere Maske (zeige andere Bereiche)'
        },
        {
            'name': 'blur',
            'label': 'Weichzeichnen',
            'type': ParameterType.INT,
            'default': 5,
            'min': 0,
            'max': 50,
            'step': 1,
            'description': 'Weichzeichnung der Maskenkanten (0 = keine, höher = weicher)'
        },
        {
            'name': 'bg_color',
            'label': 'Hintergrund',
            'type': ParameterType.COLOR,
            'default': '#000000',
            'description': 'Hintergrundfarbe für maskierte Bereiche'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Auto Mask Parametern."""
        self.mode = str(config.get('mode', 'brightness'))
        self.threshold = int(config.get('threshold', 127))
        self.tolerance = int(config.get('tolerance', 30))
        self.invert = str(config.get('invert', 'no'))
        self.blur = int(config.get('blur', 5))
        bg_color_hex = str(config.get('bg_color', '#000000'))
        # Konvertiere Hex zu BGR
        self.bg_color = self._hex_to_bgr(bg_color_hex)
    
    def _hex_to_bgr(self, hex_color):
        """Konvertiert Hex-Farbe zu BGR Tupel."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (b, g, r)
        return (0, 0, 0)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Auto Mask auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Maskiertes Frame
        """
        h, w = frame.shape[:2]
        
        # Erstelle Maske basierend auf gewähltem Modus
        if self.mode == 'brightness':
            # Helligkeitsbasierte Maske
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, self.threshold, 255, cv2.THRESH_BINARY)
        
        elif self.mode == 'color_range':
            # Farbbereichs-Maske (entfernt dunkle Bereiche)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            # Definiere Bereich für "nicht-schwarze" Farben
            lower = np.array([0, 0, self.threshold])
            upper = np.array([180, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)
        
        elif self.mode == 'edges':
            # Kantenbasierte Maske
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, self.threshold // 2, self.threshold)
            # Dilate für geschlossene Konturen
            kernel = np.ones((5, 5), np.uint8)
            mask = cv2.dilate(edges, kernel, iterations=2)
        else:
            return frame
        
        # Invertiere Maske falls gewünscht
        if self.invert == 'yes':
            mask = cv2.bitwise_not(mask)
        
        # Weichzeichnung der Maskenkanten
        if self.blur > 0:
            blur_size = self.blur * 2 + 1  # Muss ungerade sein
            mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
        
        # Normalisiere Maske zu 0-1 Bereich
        mask_normalized = mask.astype(np.float32) / 255.0
        
        # Erstelle Hintergrund
        background = np.full_like(frame, self.bg_color, dtype=np.uint8)
        
        # Blende Frame über Hintergrund mit Maske
        # Alpha Blending: result = frame * mask + background * (1 - mask)
        mask_3channel = np.stack([mask_normalized] * 3, axis=2)
        result = (frame.astype(np.float32) * mask_3channel + 
                 background.astype(np.float32) * (1 - mask_3channel))
        
        return result.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'mode':
            self.mode = str(value)
            return True
        elif name == 'threshold':
            self.threshold = int(value)
            return True
        elif name == 'tolerance':
            self.tolerance = int(value)
            return True
        elif name == 'invert':
            self.invert = str(value)
            return True
        elif name == 'blur':
            self.blur = int(value)
            return True
        elif name == 'bg_color':
            self.bg_color = self._hex_to_bgr(str(value))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        # Konvertiere BGR zurück zu Hex
        b, g, r = self.bg_color
        bg_hex = f'#{r:02x}{g:02x}{b:02x}'
        
        return {
            'mode': self.mode,
            'threshold': self.threshold,
            'tolerance': self.tolerance,
            'invert': self.invert,
            'blur': self.blur,
            'bg_color': bg_hex
        }
