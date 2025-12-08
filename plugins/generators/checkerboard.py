"""
Checkerboard Generator Plugin - Black and white checkerboard pattern
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class CheckerboardGenerator(PluginBase):
    """
    Checkerboard Generator - Schwarz-weißes Schachbrettmuster.
    
    Klassisches Schachbrettmuster mit konfigurierbarer Anzahl von Spalten und Reihen.
    """
    
    METADATA = {
        'id': 'checkerboard',
        'name': 'Schachbrett',
        'description': 'Schwarz-weißes Schachbrettmuster mit konfigurierbaren Spalten und Reihen',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Patterns'
    }
    
    PARAMETERS = [
        {
            'name': 'columns',
            'label': 'Spalten',
            'type': ParameterType.INT,
            'default': 8,
            'min': 1,
            'max': 64,
            'step': 1,
            'description': 'Anzahl der Spalten'
        },
        {
            'name': 'rows',
            'label': 'Reihen',
            'type': ParameterType.INT,
            'default': 8,
            'min': 1,
            'max': 64,
            'step': 1,
            'description': 'Anzahl der Reihen'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 1,
            'max': 60,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.columns = int(config.get('columns', 8))
        self.rows = int(config.get('rows', 8))
        self.duration = int(config.get('duration', 10))
        self.time = 0.0
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert Schachbrettmuster Frame.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height' enthalten
        
        Returns:
            numpy.ndarray: Frame als (height, width, 3) RGB Array
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        self.time = time
        
        # Erstelle schwarzes Canvas
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Berechne Größe der einzelnen Felder
        cell_width = width / self.columns
        cell_height = height / self.rows
        
        # Zeichne Schachbrettmuster
        for row in range(int(self.rows)):
            for col in range(int(self.columns)):
                # Bestimme Farbe: Weiß wenn (row + col) gerade, sonst schwarz
                if (row + col) % 2 == 0:
                    color = 255  # Weiß
                    
                    # Berechne Pixel-Koordinaten
                    x_start = int(col * cell_width)
                    x_end = int((col + 1) * cell_width)
                    y_start = int(row * cell_height)
                    y_end = int((row + 1) * cell_height)
                    
                    # Zeichne weißes Feld (schwarz ist bereits default)
                    frame[y_start:y_end, x_start:x_end] = color
        
        return frame
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        # Extract actual value if it's a range metadata dict
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        
        if name == 'columns':
            self.columns = max(1, min(64, int(value)))
            return True
        elif name == 'rows':
            self.rows = max(1, min(64, int(value)))
            return True
        elif name == 'duration':
            self.duration = max(5, min(600, int(value)))
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'columns': self.columns,
            'rows': self.rows,
            'duration': self.duration
        }
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        pass
