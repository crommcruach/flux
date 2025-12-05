"""
REST API Endpoints für Effect Chain Management

⚠️ DEAD CODE - REMOVE IN FUTURE VERSION ⚠️
DEPRECATED: This file is replaced by api_player_unified.py
Use /api/player/<player_id>/effects/* endpoints instead.

TODO: Remove this file after verifying no dependencies remain.
"""
from flask import request, jsonify
from .logger import get_logger
from .session_state import get_session_state
from .clip_registry import get_clip_registry

logger = get_logger(__name__)


def register_effect_routes(app, player_manager):
    """Registriert Effect Chain API Endpoints."""
    
    @app.route('/api/player/effects', methods=['GET'])
    def get_effects():
        """
        Gibt die aktuelle Video Effect Chain zurück.
        
        Returns:
            200: {effects: [...], count: int}
            404: {error: "No active player"}
        """
        player = player_manager.get_video_player()
        
        if not player:
            return jsonify({'error': 'No active player'}), 404
        
        effects = player.get_effect_chain(chain_type='video')
        return jsonify({
            'success': True,
            'effects': effects,
            'count': len(effects)
        })
    
    @app.route('/api/player/effects/add', methods=['POST'])
    def add_effect():
        """
        Fügt einen Effect zur Chain hinzu.
        
        Body:
            {
                "plugin_id": "blur",
                "config": {"strength": 5.0}  # Optional
            }
        
        Returns:
            200: {success: true, message: "...", index: int}
            400: {success: false, message: "..."}
            404: {error: "No active player"}
        """
        player = player_manager.get_video_player()
        
        if not player:
            return jsonify({'error': 'No active player'}), 404
        
        data = request.get_json()
        if not data or 'plugin_id' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing plugin_id'
            }), 400
        
        plugin_id = data['plugin_id']
        config = data.get('config', None)
        
        success, message = player.add_effect_to_chain(plugin_id, config, chain_type='video')
        
        if success:
            # Get new chain length for index
            effects = player.get_effect_chain(chain_type='video')
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                clip_registry = get_clip_registry()
                session_state.save(player_manager, clip_registry)
            
            return jsonify({
                'success': True,
                'message': message,
                'index': len(effects) - 1
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    
    @app.route('/api/player/effects/<int:index>', methods=['DELETE'])
    def remove_effect(index):
        """
        Entfernt einen Effect aus der Chain.
        
        Args:
            index: Index des Effects (0-basiert)
        
        Returns:
            200: {success: true, message: "..."}
            400: {success: false, message: "..."}
            404: {error: "No active player"}
        """
        player = player_manager.get_video_player()
        
        if not player:
            return jsonify({'error': 'No active player'}), 404
        
        success, message = player.clear_effects_chain(chain_type='video')
        
        if success:
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                clip_registry = get_clip_registry()
                session_state.save(player_manager, clip_registry)
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    
    @app.route('/api/player/effects/clear', methods=['POST'])
    def clear_effects():
        """
        Entfernt alle Effects aus der Chain.
        
        Returns:
            200: {success: true, message: "..."}
            404: {error: "No active player"}
        """
        player = player_manager.get_video_player()
        
        if not player:
            return jsonify({'error': 'No active player'}), 404
        
        success, message = player.clear_effects_chain(chain_type='video')
        
        return jsonify({
            'success': True,
            'message': message
        })
    
    @app.route('/api/player/effects/<int:index>/parameters/<param_name>', methods=['POST'])
    def update_effect_parameter(index, param_name):
        """
        Aktualisiert einen Parameter eines Effects.
        
        Args:
            index: Index des Effects
            param_name: Name des Parameters
        
        Body:
            {"value": <new_value>}
        
        Returns:
            200: {success: true, message: "..."}
            400: {success: false, message: "..."}
            404: {error: "No active player"}
        """
        player = player_manager.get_video_player()
        
        if not player:
            return jsonify({'error': 'No active player'}), 404
        
        data = request.get_json()
        if not data or 'value' not in data:
            return jsonify({
                'success': False,
                'message': 'Missing value'
            }), 400
        
        value = data['value']
        success, message = player.update_effect_parameter(index, param_name, value, chain_type='video')
        
        if success:
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                clip_registry = get_clip_registry()
                session_state.save(player_manager, clip_registry)
            
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
    
    logger.info("Effect Chain API endpoints registered")
