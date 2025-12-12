"""
Player Module - Modular components for the unified player
"""
# Import Player class from parent level
from ..player_core import Player

# Import manager modules
from .recording_manager import RecordingManager
from .transition_manager import TransitionManager
from .effect_processor import EffectProcessor
from .playlist_manager import PlaylistManager
from .layer_manager import LayerManager

__all__ = ['Player', 'RecordingManager', 'TransitionManager', 'EffectProcessor', 'PlaylistManager', 'LayerManager']
