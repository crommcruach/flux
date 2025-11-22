"""
Flux Module Package
"""
# Lazy imports to avoid circular dependencies
__all__ = ['Player', 'VideoSource', 'ScriptSource', 'VideoPlayer', 'ScriptPlayer', 'DMXController', 'ArtNetManager', 'RestAPI', 'ScriptGenerator',
           'PointsLoader', 'CacheManager', 'ConfigValidator',
           'list_videos', 'print_help', 'list_points_files', 'validate_points_file', 'validate_points_json']

def __getattr__(name):
    if name == 'Player':
        from .player import Player
        return Player
    elif name == 'VideoSource':
        from .frame_source import VideoSource
        return VideoSource
    elif name == 'ScriptSource':
        from .frame_source import ScriptSource
        return ScriptSource
    elif name == 'VideoPlayer':
        # Backward compatibility - deprecated
        from .video_player import VideoPlayer
        return VideoPlayer
    elif name == 'ScriptPlayer':
        # Backward compatibility - deprecated
        from .script_player import ScriptPlayer
        return ScriptPlayer
    elif name == 'DMXController':
        from .dmx_controller import DMXController
        return DMXController
    elif name == 'ArtNetManager':
        from .artnet_manager import ArtNetManager
        return ArtNetManager
    elif name == 'RestAPI':
        from .rest_api import RestAPI
        return RestAPI
    elif name == 'ScriptGenerator':
        from .script_generator import ScriptGenerator
        return ScriptGenerator
    elif name == 'PointsLoader':
        from .points_loader import PointsLoader
        return PointsLoader
    elif name == 'ConfigValidator':
        from .config_schema import ConfigValidator
        return ConfigValidator
    elif name == 'list_videos':
        from .utils import list_videos
        return list_videos
    elif name == 'print_help':
        from .utils import print_help
        return print_help
    elif name == 'list_points_files':
        from .utils import list_points_files
        return list_points_files
    elif name == 'validate_points_file':
        from .validator import validate_points_file
        return validate_points_file
    elif name == 'validate_points_json':
        from .validator import validate_points_json
        return validate_points_json
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
