"""
Wave Warp Effect Plugin - Sinusoidal Wave Distortion
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class WaveWarpEffect(PluginBase):
    """
    Wave Warp Effect - Erzeugt sinusförmige Wellenverzerrung.
    """
    
    METADATA = {
        'id': 'wave_warp',
        'name': 'Wave Warp',
        'description': 'Sinusförmige Wellenverzerrung (Horizontal/Vertikal)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur & Distortion'
    }
    
    PARAMETERS = [
        {
            'name': 'amplitude_x',
            'label': 'Amplitude X',
            'type': ParameterType.FLOAT,
            'default': 10.0,
            'min': 0.0,
            'max': 100.0,
            'description': 'Horizontale Wellenstärke in Pixeln'
        },
        {
            'name': 'frequency_x',
            'label': 'Frequenz X',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.1,
            'max': 20.0,
            'description': 'Horizontale Wellenfrequenz (Anzahl Wellen)'
        },
        {
            'name': 'amplitude_y',
            'label': 'Amplitude Y',
            'type': ParameterType.FLOAT,
            'default': 10.0,
            'min': 0.0,
            'max': 100.0,
            'description': 'Vertikale Wellenstärke in Pixeln'
        },
        {
            'name': 'frequency_y',
            'label': 'Frequenz Y',
            'type': ParameterType.FLOAT,
            'default': 2.0,
            'min': 0.1,
            'max': 20.0,
            'description': 'Vertikale Wellenfrequenz (Anzahl Wellen)'
        },
        {
            'name': 'phase',
            'label': 'Phase',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 360.0,
            'description': 'Phasenverschiebung der Welle in Grad'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Wave Warp Parametern."""
        self.amplitude_x = float(config.get('amplitude_x', 10.0))
        self.frequency_x = float(config.get('frequency_x', 2.0))
        self.amplitude_y = float(config.get('amplitude_y', 10.0))
        self.frequency_y = float(config.get('frequency_y', 2.0))
        self.phase = float(config.get('phase', 0.0))
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Wave Warp auf Frame an.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Wave-warped Frame
        """
        if (self.amplitude_x == 0 and self.amplitude_y == 0):
            return frame
        
        h, w = frame.shape[:2]
        
        # Phase in Radiant
        phase_rad = np.deg2rad(self.phase)
        
        # Erstelle Koordinaten-Grids mit np.meshgrid (optimiert)
        y_coords, x_coords = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
        
        # Horizontale Welle (verschiebt X basierend auf Y-Position)
        if self.amplitude_x > 0:
            wave_x = self.amplitude_x * np.sin(
                2 * np.pi * self.frequency_x * (y_coords / h) + phase_rad
            )
            x_warped = x_coords + wave_x
        else:
            x_warped = x_coords.astype(np.float32)
        
        # Vertikale Welle (verschiebt Y basierend auf X-Position)
        if self.amplitude_y > 0:
            wave_y = self.amplitude_y * np.sin(
                2 * np.pi * self.frequency_y * (x_coords / w) + phase_rad
            )
            y_warped = y_coords + wave_y
        else:
            y_warped = y_coords.astype(np.float32)
        
        # Begrenze auf gültige Koordinaten
        x_warped = np.clip(x_warped, 0, w - 1).astype(np.float32)
        y_warped = np.clip(y_warped, 0, h - 1).astype(np.float32)
        
        # Remap mit cv2.remap (sehr schnell)
        warped = cv2.remap(frame, 
                          x_warped, 
                          y_warped,
                          interpolation=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REFLECT)
        
        return warped
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'amplitude_x':
            self.amplitude_x = float(value)
            return True
        elif name == 'frequency_x':
            self.frequency_x = float(value)
            return True
        elif name == 'amplitude_y':
            self.amplitude_y = float(value)
            return True
        elif name == 'frequency_y':
            self.frequency_y = float(value)
            return True
        elif name == 'phase':
            self.phase = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'amplitude_x': self.amplitude_x,
            'frequency_x': self.frequency_x,
            'amplitude_y': self.amplitude_y,
            'frequency_y': self.frequency_y,
            'phase': self.phase
        }
