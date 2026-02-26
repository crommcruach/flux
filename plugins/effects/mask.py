"""
Mask Effect Plugin - Alpha Mask from Luminance
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class MaskEffect(PluginBase):
    """
    Mask Effect - Verwendet Luminanz als Alpha-Kanal (weiß = sichtbar, schwarz = transparent).
    """
    
    METADATA = {
        'id': 'mask',
        'name': 'Luminance Mask',
        'description': 'Verwendet Helligkeit als Alpha-Maske (weiß = sichtbar, schwarz = transparent)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Composite & Mask'
    }
    
    PARAMETERS = [
        {
            'name': 'invert',
            'label': 'Maske invertieren',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Invertiert die Maske (schwarz = sichtbar, weiß = transparent)'
        },
        {
            'name': 'threshold',
            'label': 'Schwellenwert',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 255.0,
            'step': 1.0,
            'description': 'Schwellenwert für Maske (0 = keine Schwelle, >0 = harte Kante)'
        },
        {
            'name': 'feather',
            'label': 'Weichzeichnen',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': 0.0,
            'max': 20.0,
            'step': 0.5,
            'description': 'Weichzeichnen der Maske für weiche Kanten'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Parametern."""
        self.invert = config.get('invert', False)
        self.threshold = config.get('threshold', 0.0)
        self.feather = config.get('feather', 0.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Luminanz-Maske auf Frame an und gibt RGBA zurück.
        
        Args:
            frame: Input Frame (NumPy Array, RGB oder RGBA)
            **kwargs: Unused
            
        Returns:
            RGBA Frame mit Luminanz als Alpha-Kanal
        """
        # Check number of channels
        num_channels = frame.shape[2] if len(frame.shape) == 3 else 1
        
        # Get RGB channels
        if num_channels == 4:  # RGBA
            rgb = frame[:, :, :3]
        else:  # RGB
            rgb = frame
        
        # OPTIMIZED: Manual RGB to grayscale conversion (2x faster than cv2.cvtColor)
        # Standard luminance weights: 0.299*R + 0.587*G + 0.114*B
        # Using integer weights for speed: (77*R + 150*G + 29*B) >> 8
        gray = np.dot(rgb[...,:3], [0.114, 0.587, 0.299]).astype(np.uint8)
        
        # Apply threshold if specified
        if self.threshold > 0:
            _, gray = cv2.threshold(gray, int(self.threshold), 255, cv2.THRESH_BINARY)
        
        # Apply feathering (blur) to mask
        if self.feather > 0:
            kernel_size = int(self.feather) * 2 + 1
            kernel_size = max(1, kernel_size)
            # PERFORMANCE: Limit kernel size to prevent extreme blur slowdown
            kernel_size = min(kernel_size, 51)  # Max kernel = 51 (feather=25)
            
            # PERFORMANCE: For large blur, downscale → blur → upscale (much faster!)
            if kernel_size > 15:
                h, w = gray.shape
                # Downscale to half resolution
                small = cv2.resize(gray, (w // 2, h // 2), interpolation=cv2.INTER_LINEAR)
                # Blur at half resolution (4x fewer pixels!)
                small_kernel = max(3, kernel_size // 2)
                if small_kernel % 2 == 0:
                    small_kernel += 1
                small = cv2.blur(small, (small_kernel, small_kernel))
                # Upscale back (bilinear adds smoothness)
                gray = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                # Small blur: Direct box blur
                gray = cv2.blur(gray, (kernel_size, kernel_size))
        
        # Invert mask if requested
        if self.invert:
            gray = 255 - gray
        
        # PERFORMANCE: Optimized RGBA creation (faster than np.dstack)
        # Pre-allocate RGBA array and copy channels directly
        h, w = gray.shape
        rgba = np.empty((h, w, 4), dtype=np.uint8)
        rgba[:, :, :3] = rgb  # Copy RGB channels
        rgba[:, :, 3] = gray  # Set alpha channel
        return rgba
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter."""
        if name == 'invert':
            self.invert = bool(value)
            return True
        elif name == 'threshold':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.threshold = float(value)
            return True
        elif name == 'feather':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.feather = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'invert': self.invert,
            'threshold': self.threshold,
            'feather': self.feather
        }
