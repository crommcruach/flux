"""
Freeze Effect Plugin - Frame freeze (static or partial)
"""
import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class FreezeEffect(PluginBase):
    """
    Freeze Effect - Friert Frame ein (komplett oder partiell mit Maske).
    """
    
    METADATA = {
        'id': 'freeze',
        'name': 'Freeze',
        'description': 'Frame einfrieren (komplett oder partiell)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'active',
            'label': 'Active',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Freeze aktivieren/deaktivieren'
        },
        {
            'name': 'mix',
            'label': 'Mix',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.1,
            'description': 'Mix zwischen eingefrorenen und Live-Frame (0 = live, 1 = frozen)'
        },
        {
            'name': 'trigger',
            'label': 'Capture Trigger',
            'type': ParameterType.BOOL,
            'default': False,
            'description': 'Neues Frame einfrieren (wird automatisch zurückgesetzt)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Freeze-Parametern."""
        self.active = config.get('active', False)
        self.mix = config.get('mix', 1.0)
        self.trigger = config.get('trigger', False)
        self.frozen_frame = None
    
    def process_frame(self, frame, **kwargs):
        """
        Friert Frame ein (komplett oder partiell).
        
        Args:
            frame: Input Frame (NumPy Array, BGR)
            **kwargs: Unused
            
        Returns:
            Eingefrorenes oder gemischtes Frame
        """
        # Capture new frozen frame if trigger is set
        if self.trigger:
            self.frozen_frame = frame.copy()
            self.trigger = False  # Auto-reset trigger
        
        # If not active or no frozen frame yet, return current frame
        if not self.active or self.frozen_frame is None:
            return frame
        
        # If mix is 1.0, return fully frozen frame
        if self.mix >= 0.99:
            return self.frozen_frame
        
        # If mix is 0.0, return live frame
        if self.mix <= 0.01:
            return frame
        
        # Blend between frozen and live frame
        return cv2.addWeighted(frame, 1.0 - self.mix, self.frozen_frame, self.mix, 0)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'active':
            self.active = bool(value)
            return True
        elif name == 'mix':
            # Extract actual value if it's a range metadata dict
            if isinstance(value, dict) and '_value' in value:
                value = value['_value']
            self.mix = float(value)
            return True
        elif name == 'trigger':
            self.trigger = bool(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'active': self.active,
            'mix': self.mix,
            'trigger': self.trigger
        }
    
    def cleanup(self):
        """Cleanup frozen frame."""
        self.frozen_frame = None
