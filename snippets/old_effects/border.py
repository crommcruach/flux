"""
Border Effect Plugin - Add Border/Frame
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class BorderEffect(PluginBase):
    """
    Border Effect - Fügt einen Rahmen um das Bild hinzu.
    """
    
    METADATA = {
        'id': 'border',
        'name': 'Border',
        'description': 'Fügt einen farbigen Rahmen um das Bild hinzu',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite'
    }
    
    PARAMETERS = [
        {
            'name': 'width',
            'label': 'Breite',
            'type': ParameterType.INT,
            'default': 5,
            'min': 0,
            'max': 50,
            'step': 1,
            'description': 'Rahmenbreite in Pixeln'
        },
        {
            'name': 'color',
            'label': 'Farbe',
            'type': ParameterType.COLOR,
            'default': '#FFFFFF',
            'description': 'Rahmenfarbe (RGB Hex)'
        },
        {
            'name': 'type',
            'label': 'Typ',
            'type': ParameterType.SELECT,
            'default': 'solid',
            'options': ['solid', 'replicate', 'reflect'],
            'description': 'Rahmen-Typ (solid = einfarbig, replicate = Rand wiederholen, reflect = spiegeln)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Border-Parametern."""
        self.width = int(config.get('width', 5))
        self.color = str(config.get('color', '#FFFFFF'))
        self.border_type = str(config.get('type', 'solid'))
        self._parse_color()
    
    def _parse_color(self):
        """Konvertiert Hex-Farbe zu BGR."""
        color_hex = self.color.lstrip('#')
        color_rgb = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
        self.color_bgr = [color_rgb[2], color_rgb[1], color_rgb[0]]
    
    def process_frame(self, frame, **kwargs):
        """
        Fügt Rahmen zum Frame hinzu.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit Rahmen
        """
        if self.width <= 0:
            return frame
        
        if self.border_type == 'solid':
            # Einfarbiger Rahmen
            bordered = cv2.copyMakeBorder(
                frame,
                self.width, self.width, self.width, self.width,
                cv2.BORDER_CONSTANT,
                value=self.color_bgr
            )
        elif self.border_type == 'replicate':
            # Rand-Pixel wiederholen
            bordered = cv2.copyMakeBorder(
                frame,
                self.width, self.width, self.width, self.width,
                cv2.BORDER_REPLICATE
            )
        elif self.border_type == 'reflect':
            # Spiegeln
            bordered = cv2.copyMakeBorder(
                frame,
                self.width, self.width, self.width, self.width,
                cv2.BORDER_REFLECT
            )
        else:
            return frame
        
        return bordered
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'width':
            self.width = int(value)
            return True
        elif name == 'color':
            self.color = str(value)
            self._parse_color()
            return True
        elif name == 'type':
            self.border_type = str(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'width': self.width,
            'color': self.color,
            'type': self.border_type
        }
