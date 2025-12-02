"""
Tile Effect Plugin
Wiederholt das Frame in einem Gitter-Muster.
"""

import cv2
import numpy as np
from plugins import PluginBase, PluginType, ParameterType

class TileEffect(PluginBase):
    """Tile - Repeat frame in grid pattern."""
    
    METADATA = {
        'id': 'tile',
        'name': 'Tile',
        'description': 'Repeat frame in grid pattern with configurable count',
        'author': 'Py_artnet',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Simple 3D & Kaleidoscope'
    }
    
    PARAMETERS = [
        {
            'name': 'tiles_x',
            'label': 'Tiles X',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 10,
            'description': 'Number of horizontal tiles'
        },
        {
            'name': 'tiles_y',
            'label': 'Tiles Y',
            'type': ParameterType.INT,
            'default': 2,
            'min': 1,
            'max': 10,
            'description': 'Number of vertical tiles'
        },
        {
            'name': 'offset_x',
            'label': 'Offset X',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -1.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Horizontal tile offset (0-1)'
        },
        {
            'name': 'offset_y',
            'label': 'Offset Y',
            'type': ParameterType.FLOAT,
            'default': 0.0,
            'min': -1.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Vertical tile offset (0-1)'
        },
        {
            'name': 'mirror_x',
            'label': 'Mirror X',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['yes', 'no'],
            'description': 'Mirror alternating columns'
        },
        {
            'name': 'mirror_y',
            'label': 'Mirror Y',
            'type': ParameterType.SELECT,
            'default': 'no',
            'options': ['yes', 'no'],
            'description': 'Mirror alternating rows'
        },
        {
            'name': 'zoom',
            'label': 'Zoom',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 3.0,
            'step': 0.1,
            'description': 'Zoom level per tile'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert den Effekt mit Konfiguration."""
        self.tiles_x = int(config.get('tiles_x', 2))
        self.tiles_y = int(config.get('tiles_y', 2))
        self.offset_x = float(config.get('offset_x', 0.0))
        self.offset_y = float(config.get('offset_y', 0.0))
        self.mirror_x = str(config.get('mirror_x', 'no'))
        self.mirror_y = str(config.get('mirror_y', 'no'))
        self.zoom = float(config.get('zoom', 1.0))
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet ein Frame mit Tile."""
        h, w = frame.shape[:2]
        
        # Erstelle Output-Frame
        result = np.zeros_like(frame)
        
        # Berechne Tile-Größe
        tile_w = w // self.tiles_x
        tile_h = h // self.tiles_y
        
        # Zoome Source-Frame wenn nötig
        if self.zoom != 1.0:
            zoom_w = int(tile_w / self.zoom)
            zoom_h = int(tile_h / self.zoom)
            
            # Stelle sicher dass Größe mindestens 1x1 ist
            zoom_w = max(1, zoom_w)
            zoom_h = max(1, zoom_h)
            
            # Berechne Center-Crop
            start_x = (w - zoom_w) // 2
            start_y = (h - zoom_h) // 2
            
            # Crop und skaliere
            source_tile = frame[start_y:start_y+zoom_h, start_x:start_x+zoom_w]
        else:
            source_tile = frame
        
        # Berechne Offset in Pixeln
        offset_x_px = int(self.offset_x * tile_w)
        offset_y_px = int(self.offset_y * tile_h)
        
        # Erstelle jedes Tile
        for ty in range(self.tiles_y):
            for tx in range(self.tiles_x):
                # Berechne Position
                x = tx * tile_w
                y = ty * tile_h
                
                # Addiere Offset (mit Wrap)
                x = (x + offset_x_px) % w
                y = (y + offset_y_px) % h
                
                # Resize Source zu Tile-Größe
                tile = cv2.resize(source_tile, (tile_w, tile_h), interpolation=cv2.INTER_LINEAR)
                
                # Mirror wenn gewünscht
                if self.mirror_x == 'yes' and tx % 2 == 1:
                    tile = cv2.flip(tile, 1)  # Horizontal flip
                
                if self.mirror_y == 'yes' and ty % 2 == 1:
                    tile = cv2.flip(tile, 0)  # Vertical flip
                
                # Platziere Tile (mit Wrap-Around)
                for dy in range(tile_h):
                    for dx in range(tile_w):
                        dest_x = (x + dx) % w
                        dest_y = (y + dy) % h
                        
                        src_dy = min(dy, tile.shape[0] - 1)
                        src_dx = min(dx, tile.shape[1] - 1)
                        
                        result[dest_y, dest_x] = tile[src_dy, src_dx]
        
        return result
    
    def update_parameter(self, name, value):
        """Aktualisiert einen Parameter zur Laufzeit."""
        if name == 'tiles_x':
            self.tiles_x = int(value)
            return True
        elif name == 'tiles_y':
            self.tiles_y = int(value)
            return True
        elif name == 'offset_x':
            self.offset_x = float(value)
            return True
        elif name == 'offset_y':
            self.offset_y = float(value)
            return True
        elif name == 'mirror_x':
            self.mirror_x = str(value)
            return True
        elif name == 'mirror_y':
            self.mirror_y = str(value)
            return True
        elif name == 'zoom':
            self.zoom = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter-Werte zurück."""
        return {
            'tiles_x': self.tiles_x,
            'tiles_y': self.tiles_y,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'mirror_x': self.mirror_x,
            'mirror_y': self.mirror_y,
            'zoom': self.zoom
        }
    
    def cleanup(self):
        """Räumt Ressourcen auf."""
        pass
