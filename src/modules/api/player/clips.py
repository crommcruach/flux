"""
Clip Layer API - REST Endpoints für Layer-Management pro Clip

Ermöglicht:
- Layer zu einzelnen Clips hinzufügen/entfernen
- Layer-Konfiguration ändern (blend_mode, opacity, enabled)
- Layer-Reihenfolge ändern
- Clips in Layers ersetzen
"""

from flask import request, jsonify
import logging
from plugins.effects.blend import BlendEffect
from ...session.state import get_session_state

logger = logging.getLogger(__name__)


def register_clip_layer_routes(app, clip_registry, player_manager, video_dir):
    """
    Registriert alle Clip-Layer API-Endpunkte.
    
    Args:
        app: Flask App-Instanz
        clip_registry: ClipRegistry-Instanz
        player_manager: PlayerManager-Instanz
        video_dir: Base directory for video files
    """
    
    @app.route('/api/blend-modes', methods=['GET'])
    def get_blend_modes():
        """Gibt verfügbare Blend-Modes zurück."""
        return jsonify({
            "success": True,
            "blend_modes": BlendEffect.BLEND_MODES
        })
    
    def reload_player_layers_if_active(clip_id):
        """Helper: Reload layers in player if this clip is currently loaded"""
        try:
            # Check both video and artnet players
            for player_id in ['video', 'artnet']:
                player = player_manager.get_player(player_id)
                if player and hasattr(player, 'current_clip_id') and player.current_clip_id == clip_id:
                    logger.debug(f"🔄 Reloading layers for {player_id} player (clip {clip_id[:8]}...)")
                    player.load_clip_layers(clip_id, clip_registry, video_dir)
        except Exception as e:
            logger.warning(f"⚠️ Failed to reload player layers: {e}")
    
    @app.route('/api/clips/<clip_id>/layers', methods=['GET'])
    def get_clip_layers(clip_id):
        """Holt alle Layers eines Clips."""
        try:
            clip = clip_registry.get_clip(clip_id)
            if not clip:
                return jsonify({"success": False, "error": "Clip not found"}), 404
            
            # Get additional layers from registry (layer_id >= 1)
            registry_layers = clip_registry.get_clip_layers(clip_id)
            
            # Layer 0 is always the base clip itself
            # Determine source type from path
            abs_path = clip['absolute_path']
            if abs_path.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                source_type = 'video'
            elif abs_path.startswith('generator:'):
                source_type = 'generator'
            elif abs_path.endswith('.py'):
                source_type = 'script'
            else:
                source_type = 'video'  # fallback
            
            base_layer = {
                'layer_id': 0,
                'source_type': source_type,
                'source_path': clip['relative_path'],
                'blend_mode': 'normal',
                'opacity': 1.0,
                'enabled': True
            }
            
            # Combine base layer + additional layers
            all_layers = [base_layer] + registry_layers
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "layers": all_layers
            })
            
        except Exception as e:
            logger.error(f"Error getting clip layers: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/layers/add', methods=['POST'])
    def add_clip_layer(clip_id):
        """
        Fügt einen Layer zu einem Clip hinzu.
        
        Body:
            source_type: 'video' | 'generator' | 'script'
            source_path: Pfad zur Video-Datei oder Generator-ID
            blend_mode: 'normal' | 'multiply' | 'screen' | 'add' | 'subtract' | 'overlay' (default: 'normal')
            opacity: 0.0-1.0 (default: 1.0)
            enabled: bool (default: True)
        """
        try:
            data = request.json
            
            source_type = data.get('source_type')
            source_path = data.get('source_path')
            blend_mode = data.get('blend_mode', 'normal')
            opacity = data.get('opacity', 1.0)
            enabled = data.get('enabled', True)
            
            # Validation
            if not source_type or not source_path:
                return jsonify({"success": False, "error": "source_type and source_path required"}), 400
            
            if source_type not in ['video', 'generator', 'script']:
                return jsonify({"success": False, "error": "Invalid source_type"}), 400
            
            if blend_mode not in BlendEffect.BLEND_MODES:
                return jsonify({"success": False, "error": "Invalid blend_mode"}), 400
            
            # Create layer config
            layer_config = {
                'source_type': source_type,
                'source_path': source_path,
                'blend_mode': blend_mode,
                'opacity': float(opacity),
                'enabled': bool(enabled)
            }
            
            # Add to clip
            layer_id = clip_registry.add_layer_to_clip(clip_id, layer_config)
            
            if layer_id is None:
                return jsonify({"success": False, "error": "Failed to add layer"}), 500
            
            # Reload layers in player if this clip is currently active
            reload_player_layers_if_active(clip_id)
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "layer_id": layer_id,
                "layer": layer_config
            })
            
        except Exception as e:
            logger.error(f"Error adding clip layer: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/layers/<int:layer_id>', methods=['DELETE'])
    def remove_clip_layer(clip_id, layer_id):
        """Entfernt einen Layer von einem Clip."""
        try:
            # Get layer info before removal for cleanup
            clip_data = clip_registry.get_clip(clip_id)
            if not clip_data:
                return jsonify({"success": False, "error": "Clip not found"}), 404
            
            # Find the layer's clip_id for cleanup
            layers = clip_data.get('layers', [])
            layer_clip_id = None
            for layer in layers:
                if layer.get('layer_id') == layer_id:
                    layer_clip_id = layer.get('clip_id')
                    break
            
            # Remove layer from registry
            success = clip_registry.remove_layer_from_clip(clip_id, layer_id)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to remove layer"}), 400
            
            # Cleanup: If layer had its own clip_id, unregister it from clip registry
            if layer_clip_id and layer_clip_id != clip_id:
                try:
                    clip_registry.unregister_clip(layer_clip_id)
                    logger.debug(f"🗑️ Unregistered layer clip_id: {layer_clip_id[:8]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to unregister layer clip_id: {e}")
            
            # Reload layers in player if this clip is currently active
            reload_player_layers_if_active(clip_id)
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
                logger.debug(f"💾 Session state saved after layer {layer_id} removal")
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "layer_id": layer_id,
                "layer_clip_id": layer_clip_id  # Return for frontend cleanup
            })
            
        except Exception as e:
            logger.error(f"Error removing clip layer: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/layers/<int:layer_id>', methods=['PATCH'])
    def update_clip_layer(clip_id, layer_id):
        """
        Aktualisiert Layer-Konfiguration.
        
        Body (alle optional):
            blend_mode: 'normal' | 'multiply' | ...
            opacity: 0.0-1.0
            enabled: bool
        """
        try:
            data = request.json
            
            # Validate blend_mode if provided
            if 'blend_mode' in data:
                if data['blend_mode'] not in BlendEffect.BLEND_MODES:
                    return jsonify({"success": False, "error": "Invalid blend_mode"}), 400
            
            # Update
            success = clip_registry.update_clip_layer(clip_id, layer_id, data)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to update layer"}), 400
            
            # Reload layers in player if this clip is currently active
            reload_player_layers_if_active(clip_id)
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "layer_id": layer_id,
                "updates": data
            })
            
        except Exception as e:
            logger.error(f"Error updating clip layer: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/clips/<clip_id>/layers/reorder', methods=['PUT'])
    def reorder_clip_layers(clip_id):
        """
        Ändert die Reihenfolge der Layers.
        
        Body:
            layer_order: Liste von Layer-IDs in neuer Reihenfolge
        """
        try:
            data = request.json
            new_order = data.get('new_order', [])
            
            if not isinstance(new_order, list):
                return jsonify({"success": False, "error": "new_order must be a list"}), 400
            
            success = clip_registry.reorder_clip_layers(clip_id, new_order)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to reorder layers"}), 400
            
            # Reload layers in player if this clip is currently active
            reload_player_layers_if_active(clip_id)
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "new_order": new_order
            })
            
        except Exception as e:
            logger.error(f"Error reordering clip layers: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    logger.debug("✅ Clip Layer API routes registered")
