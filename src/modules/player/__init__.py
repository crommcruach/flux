"""Player Module - Video playback engine"""

# Import core player components from new structure
from .core import Player
from .manager import PlayerManager
from .lock import player_lock

# Import subsystem managers
from .recording.manager import RecordingManager
from .transitions.manager import TransitionManager
from .effects.processor import EffectProcessor
from .playlists.manager import PlaylistManager
from .layers.manager import LayerManager

__all__ = [
    'Player', 
    'PlayerManager', 
    'player_lock',
    'RecordingManager', 
    'TransitionManager', 
    'EffectProcessor', 
    'PlaylistManager', 
    'LayerManager',
    'core', 
    'manager', 
    'lock', 
    'clips', 
    'layers', 
    'effects', 
    'playlists', 
    'transitions', 
    'recording', 
    'outputs', 
    'sources'
]
