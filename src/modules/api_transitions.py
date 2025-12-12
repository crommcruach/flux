"""
Transition API - REST endpoints for transition configuration.

Provides:
- GET /api/transitions/list - List all available transitions
- POST /api/player/{player_id}/transition/config - Configure player transition
- GET /api/player/{player_id}/transition/status - Get current transition config
"""

from flask import request, jsonify
from .logger import get_logger
from .plugin_manager import get_plugin_manager
from plugins.plugin_base import PluginType

logger = get_logger(__name__)


def register_transition_routes(app, player_manager):
    """
    Registriert Transition-API-Routes.
    
    Args:
        app: Flask-App-Instanz
        player_manager: PlayerManager-Instanz
    """
    plugin_manager = get_plugin_manager()
    
    @app.route('/api/transitions/list', methods=['GET'])
    def list_transitions():
        """Liste aller verfügbaren Transition-Plugins."""
        try:
            transitions = plugin_manager.list_plugins(PluginType.TRANSITION)
            
            # Format für Frontend
            transition_list = []
            for trans in transitions:
                transition_list.append({
                    "id": trans["id"],
                    "name": trans["name"],
                    "description": trans.get("description", ""),
                    "parameters": trans.get("parameters", {}),
                    "version": trans.get("version", "1.0.0")
                })
            
            return jsonify({
                "success": True,
                "transitions": transition_list,
                "count": len(transition_list)
            })
            
        except Exception as e:
            logger.error(f"❌ Error listing transitions: {e}", exc_info=True)
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    
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
            
            # Validate duration range
            if not (0.1 <= duration <= 5.0):
                return jsonify({
                    "success": False,
                    "error": "Duration must be between 0.1 and 5.0 seconds"
                }), 400
            
            # Check if transition plugin exists
            transition_plugin = None
            if enabled:
                # Get plugin instance (PluginManager.get_plugin only takes plugin_id)
                transition_plugin = plugin_manager.get_plugin(effect)
                if not transition_plugin:
                    # Try to load the plugin if not already loaded
                    transition_plugin = plugin_manager.load_plugin(effect)
                
                if not transition_plugin:
                    return jsonify({
                        "success": False,
                        "error": f"Transition plugin '{effect}' not found"
                    }), 404
                
                # Verify it's a transition plugin (type is PluginType enum, not string)
                plugin_type = transition_plugin.__class__.METADATA.get('type')
                if plugin_type != PluginType.TRANSITION:
                    return jsonify({
                        "success": False,
                        "error": f"Plugin '{effect}' is not a transition plugin (type: {plugin_type})"
                    }), 400
                
                # Set transition parameters (update_parameter is singular)
                transition_plugin.update_parameter("duration", duration)
                transition_plugin.update_parameter("easing", easing)
            
            # Store config in player's transition manager
            player.transition_manager.configure(
                enabled=enabled,
                effect=effect,
                duration=duration,
                easing=easing,
                plugin=transition_plugin
            )
            
            logger.info(f"✅ {player_id} transition config updated: "
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
