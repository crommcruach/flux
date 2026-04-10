"""
Edge Detection Effect Plugin - Sobel/Canny Edge Detection
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class EdgeDetectionEffect(PluginBase):
    """
    Edge Detection Effect - Kantenerkennung mit Sobel oder Canny Algorithmus.
    """
    
    METADATA = {
        'id': 'edge_detection',
        'name': 'Edge Detection',
        'description': 'Kantenerkennung mit Sobel oder Canny Algorithmus',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Edge & Detection'
    }
    
    PARAMETERS = [
        {
            'name': 'method',
            'label': 'Methode',
            'type': ParameterType.SELECT,
            'default': 'canny',
            'options': ['sobel', 'canny', 'laplacian'],
            'description': 'Kantenerkennung-Algorithmus (Canny = präzise, Sobel = weich, Laplacian = scharf)'
        },
        {
            'name': 'threshold1',
            'label': 'Schwellwert 1',
            'type': ParameterType.INT,
            'default': 50,
            'min': 0,
            'max': 255,
            'step': 5,
            'description': 'Unterer Schwellwert für Canny (oder allgemeiner Schwellwert für andere Methoden)'
        },
        {
            'name': 'threshold2',
            'label': 'Schwellwert 2',
            'type': ParameterType.INT,
            'default': 150,
            'min': 0,
            'max': 255,
            'step': 5,
            'description': 'Oberer Schwellwert für Canny'
        },
        {
            'name': 'invert',
            'label': 'Invertieren',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['no', 'yes'],
            'description': 'Invertiere Kanten (weiß auf schwarz oder schwarz auf weiß)'
        },
        {
            'name': 'color_mode',
            'label': 'Farbmodus',
            'type': ParameterType.SELECT,
            'default': 'white',
            'options': ['white', 'colored', 'overlay'],
            'description': 'Kantendarstellung (white = weiß auf schwarz, colored = Original-Farben, overlay = über Original)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Edge Detection Parametern."""
        self.method = str(config.get('method', 'canny'))
        self.threshold1 = int(config.get('threshold1', 50))
        self.threshold2 = int(config.get('threshold2', 150))
        self.invert = str(config.get('invert', 'no'))
        self.color_mode = str(config.get('color_mode', 'white'))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Edge Detection auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Kantenerkennung
        """
        # Konvertiere zu Graustufen
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Wende gewählte Methode an
        if self.method == 'canny':
            edges = cv2.Canny(gray, self.threshold1, self.threshold2)
        elif self.method == 'sobel':
            # Sobel in X und Y Richtung
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            # Magnitude berechnen
            edges = np.sqrt(sobelx**2 + sobely**2)
            edges = np.uint8(np.clip(edges, 0, 255))
            # Threshold anwenden
            _, edges = cv2.threshold(edges, self.threshold1, 255, cv2.THRESH_BINARY)
        elif self.method == 'laplacian':
            # Laplacian
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            edges = np.uint8(np.clip(np.abs(laplacian), 0, 255))
            # Threshold anwenden
            _, edges = cv2.threshold(edges, self.threshold1, 255, cv2.THRESH_BINARY)
        else:
            return frame
        
        # Invertiere falls gewünscht
        if self.invert == 'yes':
            edges = cv2.bitwise_not(edges)
        
        # Wende Farbmodus an
        if self.color_mode == 'white':
            # Weiße Kanten auf schwarzem Hintergrund
            result = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        elif self.color_mode == 'colored':
            # Kanten mit Original-Farben
            # Erstelle Maske aus Kanten
            mask = edges > 0
            result = np.zeros_like(frame)
            result[mask] = frame[mask]
        elif self.color_mode == 'overlay':
            # Kanten über Original-Frame
            edges_colored = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
            result = cv2.addWeighted(frame, 0.7, edges_colored, 0.3, 0)
        else:
            result = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'method':
            self.method = str(value)
            return True
        elif name == 'threshold1':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.threshold1 = int(value)
            return True
        elif name == 'threshold2':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.threshold2 = int(value)
            return True
        elif name == 'invert':
            self.invert = str(value)
            return True
        elif name == 'color_mode':
            self.color_mode = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'method': self.method,
            'threshold1': self.threshold1,
            'threshold2': self.threshold2,
            'invert': self.invert,
            'color_mode': self.color_mode
        }
