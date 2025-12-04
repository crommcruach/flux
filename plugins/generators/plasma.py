"""
Plasma Generator Plugin - Classic demo effect with flowing color patterns
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class PlasmaGenerator(PluginBase):
    """
    Plasma Generator - Klassischer Demo-Effekt.
    
    Erzeugt organische, fließende Farbmuster durch überlagerte Sinus-Wellen.
    """
    
    METADATA = {
        'id': 'plasma',
        'name': 'Plasma',
        'description': 'Klassischer Plasma-Effekt mit überlagerten Sinus-Wellen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }
    
    PARAMETERS = [
        {
            'name': 'speed',
            'label': 'Speed',
            'type': ParameterType.FLOAT,
            'default': 0.5,
            'min': 0.0,
            'max': 5.0,
            'step': 0.1,
            'description': 'Animation speed'
        },
        {
            'name': 'scale',
            'label': 'Scale',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Pattern scale (higher = larger features)'
        },
        {
            'name': 'hue_shift',
            'label': 'Hue Shift',
            'type': ParameterType.FLOAT,
            'default': 0.1,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Color rotation speed'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        print(f"[PLASMA] initialize called with config: {config}")
        self.speed = config.get('speed', 0.5)
        self.scale = config.get('scale', 1.0)
        self.hue_shift = config.get('hue_shift', 0.1)
        self.duration = config.get('duration', 10)
        self.time = 0.0
        print(f"[PLASMA] Initialized with speed={self.speed}, scale={self.scale}, hue_shift={self.hue_shift}")
    
    def _hsv_to_rgb_vectorized(self, h, s, v):
        """Schnelle HSV zu RGB Konvertierung (vektorisiert)."""
        i = (h * 6.0).astype(int)
        f = (h * 6.0) - i
        
        p = v * (1.0 - s)
        q = v * (1.0 - s * f)
        t = v * (1.0 - s * (1.0 - f))
        
        i = i % 6
        
        r = np.choose(i, [v, q, p, p, t, v])
        g = np.choose(i, [t, v, v, q, p, p])
        b = np.choose(i, [p, p, t, v, v, q])
        
        return r, g, b
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Plasma-Frame.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height', 'time' enthalten
            
        Returns:
            Generated frame
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        # Update internal time if not provided
        if 'time' not in kwargs:
            self.time += 1.0 / 30.0  # Assume 30 FPS
            time = self.time
        
        # Erstelle Koordinaten-Meshgrid
        x = np.arange(width, dtype=np.float32) / self.scale
        y = np.arange(height, dtype=np.float32) / self.scale
        X, Y = np.meshgrid(x, y)
        
        # Berechne alle 4 Sinus-Wellen parallel
        v1 = np.sin(X / 16.0 + time * self.speed)
        v2 = np.sin(Y / 8.0 + time * self.speed)
        v3 = np.sin((X + Y) / 16.0 + time * self.speed)
        v4 = np.sin(np.sqrt(X*X + Y*Y) / 8.0 + time * self.speed)
        
        # Kombiniere Wellen
        plasma = (v1 + v2 + v3 + v4) / 4.0
        
        # Normalisiere zu 0-1
        plasma = (plasma + 1.0) / 2.0
        
        # Konvertiere zu Hue mit Farbrotation
        hue = (plasma + time * self.hue_shift) % 1.0
        
        # HSV zu RGB
        r, g, b = self._hsv_to_rgb_vectorized(hue, 1.0, 1.0)
        
        # Stack zu RGB und konvertiere zu uint8
        frame = np.stack([r * 255, g * 255, b * 255], axis=-1).astype(np.uint8)
        
        return frame
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'speed':
            self.speed = float(value)
            return True
        elif name == 'scale':
            self.scale = float(value)
            return True
        elif name == 'hue_shift':
            self.hue_shift = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'speed': self.speed,
            'scale': self.scale,
            'hue_shift': self.hue_shift
        }
