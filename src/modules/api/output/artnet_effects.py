"""
API Art-Net Effects - Separate Effect Chain für Art-Net Ausgabe
"""
from flask import jsonify, request
from .logger import get_logger
from .session_state import get_session_state
from .clip_registry import get_clip_registry

logger = get_logger(__name__)


def register_artnet_effects_api(app, player_manager):
    """Registriert Art-Net Effect Chain API Endpunkte."""
    
    @app.route('/api/artnet/effects', methods=['GET'])
    def get_artnet_effects():
        """Gibt die aktuelle Art-Net Effect Chain zurück."""
        try:
            # Use artnet_player if available, fallback to main player with artnet chain
            player = player_manager.get_artnet_player() or player_manager.player
            if not player:
                return jsonify({"success": True, "effects": [], "count": 0})
            
            # Always use 'artnet' chain - both players have separate video/artnet chains
            effects = player.get_effect_chain(chain_type='artnet')
            
            return jsonify({
                "success": True,
                "effects": effects,
                "count": len(effects)
            })
        except Exception as e:
            logger.error(f"Error getting Art-Net effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/effects/add', methods=['POST'])
    def add_artnet_effect():
        """Fügt einen Effect zur Art-Net Chain hinzu."""
        try:
            data = request.get_json()
            plugin_id = data.get('plugin_id')
            config = data.get('config', {})
            
            if not plugin_id:
                return jsonify({"success": False, "error": "plugin_id required"}), 400
            
            player = player_manager.get_artnet_player() or player_manager.player
            if not player:
                return jsonify({"success": False, "error": "No player available"}), 404
            
            success, message = player.add_effect_to_chain(plugin_id, config, chain_type='artnet')
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    clip_registry = get_clip_registry()
                    session_state.save_async(player_manager, clip_registry)
                
                return jsonify({"success": True, "message": message})
            else:
                return jsonify({"success": False, "error": message}), 400
                
        except Exception as e:
            logger.error(f"Error adding Art-Net effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/effects/remove/<int:index>', methods=['DELETE'])
    def remove_artnet_effect(index):
        """Entfernt einen Effect aus der Art-Net Chain."""
        try:
            player = player_manager.get_artnet_player() or player_manager.player
            if not player:
                return jsonify({"success": False, "error": "No player available"}), 404
            
            success, message = player.remove_effect_from_chain(index, chain_type='artnet')
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    clip_registry = get_clip_registry()
                    session_state.save_async(player_manager, clip_registry)
                
                return jsonify({"success": True, "message": message})
            else:
                return jsonify({"success": False, "error": message}), 400
                
        except Exception as e:
            logger.error(f"Error removing Art-Net effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/effects/clear', methods=['POST'])
    def clear_artnet_effects():
        """Entfernt alle Effects aus der Art-Net Chain."""
        try:
            player = player_manager.get_artnet_player() or player_manager.player
            if not player:
                return jsonify({"success": False, "error": "No player available"}), 404
            
            success, message = player.clear_effects_chain(chain_type='artnet')
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                clip_registry = get_clip_registry()
                session_state.save_async(player_manager, clip_registry)
            
            return jsonify({"success": True, "message": message})
        except Exception as e:
            logger.error(f"Error clearing Art-Net effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/effects/<int:index>/parameter', methods=['PUT'])
    def update_artnet_effect_parameter(index):
        """Aktualisiert einen Parameter eines Art-Net Effects."""
        try:
            data = request.get_json()
            param_name = data.get('name')
            value = data.get('value')
            
            if param_name is None or value is None:
                return jsonify({"success": False, "error": "name and value required"}), 400
            
            player = player_manager.get_artnet_player() or player_manager.player
            if not player:
                return jsonify({"success": False, "error": "No player available"}), 404
            
            # Always use artnet_effect_chain
            chain = player.artnet_effect_chain
            
            if index < 0 or index >= len(chain):
                return jsonify({"success": False, "error": "Invalid index"}), 400
            
            effect = chain[index]
            plugin_instance = effect['instance']
            
            # Update parameter
            success = plugin_instance.update_parameter(param_name, value)
            
            if success:
                effect['config'][param_name] = value
                
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    clip_registry = get_clip_registry()
                    session_state.save_async(player_manager, clip_registry)
                
                return jsonify({"success": True, "message": f"Parameter '{param_name}' updated"})
            else:
                return jsonify({"success": False, "error": f"Failed to update parameter '{param_name}'"}), 400
                
        except Exception as e:
            logger.error(f"Error updating Art-Net effect parameter: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
