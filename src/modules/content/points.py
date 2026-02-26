"""
Points Loader - Lädt und verarbeitet Punkte-Konfigurationen
"""
import json
import numpy as np
from ..core.logger import get_logger
from ..core.constants import (
    DMX_CHANNELS_PER_UNIVERSE,
    DMX_CHANNELS_PER_POINT,
    DMX_MAX_CHANNELS_8_UNIVERSES,
    DEFAULT_CANVAS_WIDTH,
    DEFAULT_CANVAS_HEIGHT
)

logger = get_logger(__name__)


class PointsLoader:
    """Lädt Points-JSON und berechnet Universe-Mapping."""
    
    @staticmethod
    def load_points(points_json_path, validate_bounds=True):
        """
        Lädt Points-Konfiguration aus JSON-Datei.
        
        Args:
            points_json_path: Pfad zur JSON-Datei
            validate_bounds: Ob Punkte auf Canvas-Größe validiert werden sollen
            
        Returns:
            dict: {
                'point_coords': np.array,  # Numpy-Array mit Koordinaten
                'canvas_width': int,
                'canvas_height': int,
                'universe_mapping': dict,  # Point-Index -> Universe-Offset
                'total_points': int,
                'total_channels': int,
                'required_universes': int
            }
        """
        with open(points_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Canvas-Größe
        canvas = data.get('canvas', {})
        canvas_width = canvas.get('width', DEFAULT_CANVAS_WIDTH)
        canvas_height = canvas.get('height', DEFAULT_CANVAS_HEIGHT)
        
        objects = data.get('objects', [])
        
        # Konstanten
        channels_per_universe = DMX_CHANNELS_PER_UNIVERSE
        channels_per_point = DMX_CHANNELS_PER_POINT
        max_channels_8_universes = DMX_MAX_CHANNELS_8_UNIVERSES
        
        # Sammle Punkte mit Universe-Mapping
        point_list = []
        universe_mapping = {}
        current_channel = 0
        universe_offset = 0
        
        for obj_idx, obj in enumerate(objects):
            obj_id = obj.get('id', f'object-{obj_idx}')
            points = obj.get('points', [])
            
            # Validiere Punkte falls gewünscht
            if validate_bounds:
                valid_points = []
                for point in points:
                    x, y = point.get('x'), point.get('y')
                    if x is not None and y is not None:
                        if 0 <= x < canvas_width and 0 <= y < canvas_height:
                            valid_points.append((x, y))
                        else:
                            logger.debug(f"Punkt außerhalb Canvas: ({x}, {y})")
            else:
                # Keine Validierung - nutze alle Punkte
                valid_points = [(p.get('x'), p.get('y')) for p in points 
                               if p.get('x') is not None and p.get('y') is not None]
            
            if not valid_points:
                continue
            
            obj_channels = len(valid_points) * channels_per_point
            obj_start_channel = current_channel + universe_offset
            obj_end_channel = obj_start_channel + obj_channels
            
            # Prüfe ob Objekt über 8-Universen-Grenze geht
            if obj_start_channel < max_channels_8_universes and obj_end_channel > max_channels_8_universes:
                # Objekt würde Grenze überschreiten -> verschiebe komplett zu Universum 9
                universe_offset = max_channels_8_universes - current_channel
                obj_start_channel = current_channel + universe_offset
                obj_end_channel = obj_start_channel + obj_channels
                logger.debug(f"Objekt '{obj_id}' verschoben zu Universum 9+ (würde Grenze überschreiten)")
            
            # Füge Punkte hinzu und speichere Universe-Mapping
            for point in valid_points:
                point_list.append(point)
                point_idx = len(point_list) - 1
                universe_mapping[point_idx] = universe_offset
            
            current_channel += obj_channels
        
        # Als Numpy-Array für schnelleren Zugriff
        point_coords = np.array(point_list, dtype=np.int32) if point_list else np.array([])
        total_points = len(point_list)
        total_channels = total_points * channels_per_point + universe_offset
        required_universes = (total_channels + channels_per_universe - 1) // channels_per_universe
        
        logger.debug(f"Points geladen: {total_points} Punkte, {required_universes} Universen")
        
        return {
            'point_coords': point_coords,
            'canvas_width': canvas_width,
            'canvas_height': canvas_height,
            'universe_mapping': universe_mapping,
            'total_points': total_points,
            'total_channels': total_channels,
            'required_universes': required_universes,
            'channels_per_universe': channels_per_universe
        }
