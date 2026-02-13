"""
Flux Module Package
"""
# Lazy imports to avoid circular dependencies
__all__ = ['Player', 'VideoSource', 'GeneratorSource', 'RestAPI', 'ScriptGenerator',
           'PointsLoader', 'CacheManager', 'ConfigValidator', 'PlayerManager', 'ClipRegistry',
           'list_videos', 'print_help', 'list_points_files', 'validate_points_file', 'validate_points_json']

def __getattr__(name):
    if name == 'Player':
        from .player import Player
        return Player
    elif name == 'VideoSource':
        from .frame_source import VideoSource
        return VideoSource
    elif name == 'GeneratorSource':
        from .frame_source import GeneratorSource
        return GeneratorSource
    elif name == 'ClipRegistry':
        from .clip_registry import ClipRegistry, get_clip_registry
        return ClipRegistry
    elif name == 'RestAPI':
        from .rest_api import RestAPI
        return RestAPI
    elif name == 'ScriptGenerator':
        # from .script_generator import ScriptGenerator  # Deprecated - using plugin system now
        return ScriptGenerator
    elif name == 'PointsLoader':
        from .points_loader import PointsLoader
        return PointsLoader
    elif name == 'ConfigValidator':
        from .config_schema import ConfigValidator
        return ConfigValidator
    elif name == 'PlayerManager':
        from .player_manager import PlayerManager
        return PlayerManager
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
