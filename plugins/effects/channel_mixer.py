"""
Channel Mixer Effect Plugin - Mix RGB Channels
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class ChannelMixerEffect(PluginBase):
    """
    Channel Mixer Effect - Mischt RGB-Kanäle mit konfigurierbaren Gewichten.
    """
    
    METADATA = {
        'id': 'channel_mixer',
        'name': 'Channel Mixer',
        'description': 'Mischt RGB-Kanäle für kreative Farbeffekte',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Color/Tone'
    }
    
    PARAMETERS = [
        {
            'name': 'red_from_red',
            'label': 'Red ← Red',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des roten Kanals im Ausgabe-Rot'
        },
        {
            'name': 'red_from_green',
            'label': 'Red ← Green',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des grünen Kanals im Ausgabe-Rot'
        },
        {
            'name': 'red_from_blue',
            'label': 'Red ← Blue',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des blauen Kanals im Ausgabe-Rot'
        },
        {
            'name': 'green_from_red',
            'label': 'Green ← Red',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des roten Kanals im Ausgabe-Grün'
        },
        {
            'name': 'green_from_green',
            'label': 'Green ← Green',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des grünen Kanals im Ausgabe-Grün'
        },
        {
            'name': 'green_from_blue',
            'label': 'Green ← Blue',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des blauen Kanals im Ausgabe-Grün'
        },
        {
            'name': 'blue_from_red',
            'label': 'Blue ← Red',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des roten Kanals im Ausgabe-Blau'
        },
        {
            'name': 'blue_from_green',
            'label': 'Blue ← Green',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des grünen Kanals im Ausgabe-Blau'
        },
        {
            'name': 'blue_from_blue',
            'label': 'Blue ← Blue',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': -2.0,
            'max': 2.0,
            'step': 0.1,
            'description': 'Anteil des blauen Kanals im Ausgabe-Blau'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Channel-Mixing-Parametern."""
        # Red output channel
        self.red_from_red = float(config.get('red_from_red', 1.0))
        self.red_from_green = float(config.get('red_from_green', 0.0))
        self.red_from_blue = float(config.get('red_from_blue', 0.0))
        
        # Green output channel
        self.green_from_red = float(config.get('green_from_red', 0.0))
        self.green_from_green = float(config.get('green_from_green', 1.0))
        self.green_from_blue = float(config.get('green_from_blue', 0.0))
        
        # Blue output channel
        self.blue_from_red = float(config.get('blue_from_red', 0.0))
        self.blue_from_green = float(config.get('blue_from_green', 0.0))
        self.blue_from_blue = float(config.get('blue_from_blue', 1.0))
        
        self._update_matrix()
    
    def _update_matrix(self):
        """Erstellt Transform-Matrix für Channel-Mixing."""
        # Speichere Mixing-Gewichte (keine Matrix nötig)
        pass
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Channel-Mixing auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Channel-gemischtes Frame
        """
        # Konvertiere zu Float für präzise Berechnung
        frame_float = frame.astype(np.float32)
        
        # Separiere Kanäle (OpenCV = BGR)
        b, g, r = cv2.split(frame_float)
        
        # Mische Kanäle manuell
        # Ausgabe-Blau = Mix aus Input B/G/R
        out_b = (self.blue_from_blue * b + 
                 self.blue_from_green * g + 
                 self.blue_from_red * r)
        
        # Ausgabe-Grün = Mix aus Input B/G/R
        out_g = (self.green_from_blue * b + 
                 self.green_from_green * g + 
                 self.green_from_red * r)
        
        # Ausgabe-Rot = Mix aus Input B/G/R
        out_r = (self.red_from_blue * b + 
                 self.red_from_green * g + 
                 self.red_from_red * r)
        
        # Merge und Clip
        mixed = cv2.merge([out_b, out_g, out_r])
        mixed = np.clip(mixed, 0, 255)
        
        return mixed.astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        value = float(value)
        
        if name == 'red_from_red':
            self.red_from_red = value
        elif name == 'red_from_green':
            self.red_from_green = value
        elif name == 'red_from_blue':
            self.red_from_blue = value
        elif name == 'green_from_red':
            self.green_from_red = value
        elif name == 'green_from_green':
            self.green_from_green = value
        elif name == 'green_from_blue':
            self.green_from_blue = value
        elif name == 'blue_from_red':
            self.blue_from_red = value
        elif name == 'blue_from_green':
            self.blue_from_green = value
        elif name == 'blue_from_blue':
            self.blue_from_blue = value
        else:
            return False
        
        self._update_matrix()
        return True
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'red_from_red': self.red_from_red,
            'red_from_green': self.red_from_green,
            'red_from_blue': self.red_from_blue,
            'green_from_red': self.green_from_red,
            'green_from_green': self.green_from_green,
            'green_from_blue': self.green_from_blue,
            'blue_from_red': self.blue_from_red,
            'blue_from_green': self.blue_from_green,
            'blue_from_blue': self.blue_from_blue
        }
