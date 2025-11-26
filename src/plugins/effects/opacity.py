"""
Opacity Effect Plugin - Controls video transparency/opacity
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class OpacityEffect(PluginBase):
    """
    Opacity Effect - Steuert die Transparenz/Opazität des Videos.
    
    Bei 100% ist das Video vollständig sichtbar (normal).
    Bei 0% ist das Video vollständig transparent (schwarz).
    """
    
    METADATA = {
        'id': 'opacity',
        'name': 'Opacity',
        'description': 'Steuert die Video-Opazität (Transparenz)',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'
    }
    
    PARAMETERS = [
        {
            'name': 'opacity',
            'label': 'Opacity',
            'type': ParameterType.FLOAT,
            'default': 100.0,
            'min': 0.0,
            'max': 100.0,
            'step': 1.0,
            'description': 'Video-Opazität in Prozent (100% = vollständig sichtbar, 0% = transparent/schwarz)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Opacity-Wert."""
        self.opacity = config.get('opacity', 100.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Wendet Opacity auf Frame an.
        
        Die Opazität wird als Multiplikator angewendet:
        - 100% = Faktor 1.0 (keine Änderung)
        - 50% = Faktor 0.5 (halb-transparent)
        - 0% = Faktor 0.0 (vollständig transparent/schwarz)
        
        Args:
            frame: Input Frame (NumPy Array, RGB, uint8)
            **kwargs: Unused
            
        Returns:
            Modifiziertes Frame mit angewendeter Opazität
        """
        if self.opacity >= 100.0:
            # Keine Änderung bei 100%
            return frame
        
        # Konvertiere Opacity-Prozent zu Faktor (0-1)
        opacity_factor = self.opacity / 100.0
        
        # Wende Opacity an: multipliziere alle Pixel mit dem Faktor
        # Verwende float32 für Präzision, dann zurück zu uint8
        frame_float = frame.astype(np.float32)
        frame_float *= opacity_factor
        
        # Clip und zurück zu uint8
        return np.clip(frame_float, 0, 255).astype(np.uint8)
    
    def update_parameter(self, name, value):
        """Update parameter zur Laufzeit."""
        if name == 'opacity':
            self.opacity = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {
            'opacity': self.opacity
        }
