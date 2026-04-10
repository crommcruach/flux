"""
Delay RGB Effect Plugin - RGB channel delay with frame buffers
"""
import cv2
import numpy as np
from collections import deque
from plugins import PluginBase, PluginType, ParameterType


class DelayRGBEffect(PluginBase):
    """
    Delay RGB Effect - Verzögert RGB-Kanäle unabhängig voneinander.
    """
    
    METADATA = {
        'id': 'delay_rgb',
        'name': 'Delay RGB',
        'description': 'RGB-Kanal-Verzögerung mit Frame-Buffern',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'red_delay',
            'label': 'Red Delay',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 30,
            'step': 1,
            'description': 'Frame-Verzögerung für Rot-Kanal'
        },
        {
            'name': 'green_delay',
            'label': 'Green Delay',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 30,
            'step': 1,
            'description': 'Frame-Verzögerung für Grün-Kanal'
        },
        {
            'name': 'blue_delay',
            'label': 'Blue Delay',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 30,
            'step': 1,
            'description': 'Frame-Verzögerung für Blau-Kanal'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit RGB-Delays."""
        self.red_delay = int(config.get('red_delay', 0))
        self.green_delay = int(config.get('green_delay', 0))
        self.blue_delay = int(config.get('blue_delay', 0))
        
        # Create buffers for each channel
        max_delay = max(self.red_delay, self.green_delay, self.blue_delay, 1)
        self.red_buffer = deque(maxlen=max_delay + 1)
        self.green_buffer = deque(maxlen=max_delay + 1)
        self.blue_buffer = deque(maxlen=max_delay + 1)
    
    def process_frame(self, frame, **kwargs):
        """
        Verzögert RGB-Kanäle unabhängig voneinander.
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Frame mit verzögerten RGB-Kanälen
        """
        # Split into BGR channels (OpenCV uses BGR, not RGB)
        b, g, r = cv2.split(frame)
        
        # Add current channels to buffers
        self.blue_buffer.append(b)
        self.green_buffer.append(g)
        self.red_buffer.append(r)
        
        # Get delayed channels (or current if not enough history)
        if len(self.blue_buffer) > self.blue_delay:
            b_delayed = list(self.blue_buffer)[-(self.blue_delay + 1)]
        else:
            b_delayed = b
        
        if len(self.green_buffer) > self.green_delay:
            g_delayed = list(self.green_buffer)[-(self.green_delay + 1)]
        else:
            g_delayed = g
        
        if len(self.red_buffer) > self.red_delay:
            r_delayed = list(self.red_buffer)[-(self.red_delay + 1)]
        else:
            r_delayed = r
        
        # Merge delayed channels back
        return cv2.merge([b_delayed, g_delayed, r_delayed])
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'red_delay':
            self.red_delay = int(value)
            self._update_buffer_sizes()
            return True
        elif name == 'green_delay':
            self.green_delay = int(value)
            self._update_buffer_sizes()
            return True
        elif name == 'blue_delay':
            self.blue_delay = int(value)
            self._update_buffer_sizes()
            return True
        return False
    
    def _update_buffer_sizes(self):
        """Update buffer sizes when delays change."""
        max_delay = max(self.red_delay, self.green_delay, self.blue_delay, 1)
        
        # Preserve existing data while updating maxlen
        old_r = list(self.red_buffer)
        old_g = list(self.green_buffer)
        old_b = list(self.blue_buffer)
        
        self.red_buffer = deque(old_r, maxlen=max_delay + 1)
        self.green_buffer = deque(old_g, maxlen=max_delay + 1)
        self.blue_buffer = deque(old_b, maxlen=max_delay + 1)
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'red_delay': self.red_delay,
            'green_delay': self.green_delay,
            'blue_delay': self.blue_delay
        }
    
    def cleanup(self):
        """Cleanup buffers."""
        self.red_buffer.clear()
        self.green_buffer.clear()
        self.blue_buffer.clear()
