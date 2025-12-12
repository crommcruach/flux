"""
Player API Package - REST API endpoints for player control
"""

from .clip_api import register_clip_routes
from .effect_api import register_effect_routes
from .playback_api import register_playback_routes
from .status_api import register_status_routes
from .playlist_api import register_playlist_routes

__all__ = [
    'register_clip_routes',
    'register_effect_routes',
    'register_playback_routes',
    'register_status_routes',
    'register_playlist_routes'
]
