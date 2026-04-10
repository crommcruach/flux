"""
Checkerboard Generator Plugin - Black and white checkerboard pattern
"""
import os
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'gen_checkerboard.wgsl'
)


class CheckerboardGenerator(PluginBase):

    _shader_src: str | None = None
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
            'type': ParameterType.STRING,
            'default': '10',
            'description': 'Playback duration in seconds (1-60, affects Transport timeline)'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Generator mit Parametern."""
        self.columns = int(config.get('columns', 8))
        self.rows = int(config.get('rows', 8))
        # Duration can be string or number, convert and clamp to 1-60
        duration_val = config.get('duration', 10)
        try:
            self.duration = max(1, min(60, float(duration_val)))
        except (ValueError, TypeError):
            self.duration = 10
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
            try:
                self.duration = max(1, min(60, float(value)))
            except (ValueError, TypeError):
                self.duration = 10
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

    # ── GPU shader interface ─────────────────────────────────────────────
    def get_shader(self) -> str | None:
        if CheckerboardGenerator._shader_src is None:
            with open(_SHADER_PATH, 'r', encoding='utf-8') as f:
                CheckerboardGenerator._shader_src = f.read()
        return CheckerboardGenerator._shader_src

    def get_uniforms(self, **kwargs) -> dict:
        return {
            'time':    0.0,
            'cw':      float(kwargs.get('width', 0)),
            'ch':      float(kwargs.get('height', 0)),
            'columns': int(self.columns),
            'rows':    int(self.rows),
        }
