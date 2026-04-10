"""
Transition API - REST endpoints for transition configuration.

Provides:
- GET /api/transitions/list - List all available transitions
- POST /api/player/{player_id}/transition/config - Configure player transition
- GET /api/player/{player_id}/transition/status - Get current transition config
"""

from flask import request, jsonify
from ...core.logger import get_logger

logger = get_logger(__name__)

# Available GPU shader transitions (WGSL-based)
_GPU_TRANSITIONS = [
    {"id": "fade", "name": "Fade", "description": "Cross-fade blend"},
]


def register_transition_routes(app, player_manager, playlist_system=None):
    """
    Registriert Transition-API-Routes.
    
    Args:
        app: Flask-App-Instanz
        player_manager: PlayerManager-Instanz
        playlist_system: MultiPlaylistSystem instance for playlist-aware operations (optional)
    """
    @app.route('/api/transitions/list', methods=['GET'])
    def list_transitions():
        """List available GPU shader transitions."""
        try:
            return jsonify({
                "success": True,
                "transitions": _GPU_TRANSITIONS,
                "count": len(_GPU_TRANSITIONS)
            })
        except Exception as e:
            logger.error(f"❌ Error listing transitions: {e}", exc_info=True)
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/transition/config', methods=['POST'])
    def set_transition_config(player_id):
        """Setzt Transition-Konfiguration für einen Player."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({
                    "success": False,
                    "error": f"Player '{player_id}' not found"
                }), 404
            
            data = request.get_json()
            
            # Validate config
            enabled = data.get('enabled', False)
            effect = data.get('effect', 'fade')
            duration = data.get('duration', 1.0)
            easing = data.get('easing', 'ease_in_out')
            
            # Debug: Log playlist state
            logger.debug(f"[TRANSITION CONFIG DEBUG] playlist_system exists: {playlist_system is not None}")
            if playlist_system:
                logger.debug(f"[TRANSITION CONFIG DEBUG] viewed={playlist_system.viewed_playlist_id}, active={playlist_system.active_playlist_id}")
            
            # Validate duration range
            if not (0.1 <= duration <= 5.0):
                return jsonify({
                    "success": False,
                    "error": "Duration must be between 0.1 and 5.0 seconds"
                }), 400
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - update stored transition config
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    
                    # Update transition config in playlist storage
                    player_state.transition_config = {
                        'enabled': enabled,
                        'effect': effect,
                        'duration': duration,
                        'easing': easing
                    }
                    
                    logger.debug(f"[TRANSITION CONFIG] Updated transition config for viewed playlist '{viewed_playlist.name}' {player_id}: enabled={enabled}, effect={effect}")
                    
                    # Save playlist state
                    playlist_system._auto_save()
                    
                    return jsonify({
                        "success": True,
                        "player_id": player_id,
                        "config": {
                            "enabled": enabled,
                            "effect": effect,
                            "duration": duration,
                            "easing": easing
                        }
                    })
            
            # Otherwise apply to physical player (active playlist)
            logger.debug(f"[TRANSITION CONFIG DEBUG] Applying to physical player (active playlist)")

            new_config = {
                'enabled': enabled,
                'effect': effect,
                'duration': duration,
                'easing': easing,
            }

            # 1. Update the in-memory transition manager
            player.transition_manager.configure(**new_config)

            # 2. Keep player.transition_config in sync so _auto_save() persists it
            player.transition_config = new_config.copy()

            # 3. Update the active playlist's stored player_state and trigger a save
            if playlist_system:
                active_playlist = playlist_system.playlists.get(playlist_system.active_playlist_id)
                if active_playlist:
                    player_state = active_playlist.get_player_state(player_id)
                    if player_state:
                        player_state.transition_config = new_config.copy()
                playlist_system._auto_save()

            logger.debug(f"✅ {player_id} transition config updated: "
                       f"enabled={enabled}, effect={effect}, duration={duration}s, easing={easing}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "config": {
                    "enabled": enabled,
                    "effect": effect,
                    "duration": duration,
                    "easing": easing
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Error setting transition config for {player_id}: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    
    @app.route('/api/player/<player_id>/transition/status', methods=['GET'])
    def get_transition_status(player_id):
        """Gibt die aktuelle Transition-Konfiguration eines Players zurück."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({
                    "success": False,
                    "error": f"Player '{player_id}' not found"
                }), 404
            
            # Get config from transition manager
            config = player.transition_manager.config
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "config": {
                    "enabled": config.get("enabled", False),
                    "effect": config.get("effect", "fade"),
                    "duration": config.get("duration", 1.0),
                    "easing": config.get("easing", "ease_in_out")
                }
            })
            
        except Exception as e:
            logger.error(f"❌ Error getting transition status for {player_id}: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
