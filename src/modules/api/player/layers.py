"""
Layer Stack API - REST API for multi-layer management.

Enables layer-based compositing with:
- Add/remove layers
- Change layer order
- Blend-Mode und Opacity pro Layer
- Clip in Layer laden
"""

import os
from flask import request, jsonify
from ...core.logger import get_logger
from ...player.clips.registry import get_clip_registry
from ...player.sources import VideoSource, GeneratorSource

logger = get_logger(__name__)


def register_layer_routes(app, player_manager, config):
    """
    Registriert Layer-API-Routes.
    
    Args:
        app: Flask-App-Instanz
        player_manager: PlayerManager-Instanz
        config: Konfiguration
    """
    clip_registry = get_clip_registry()
    video_dir = config['paths']['video_dir']
    
    # ========================================
    # LAYER MANAGEMENT
    # ========================================
    
    @app.route('/api/player/<player_id>/layers', methods=['GET'])
    def get_layers(player_id):
        """Returns all layers of a player."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Serialisiere Layer-Stack
            layers_data = [layer.to_dict() for layer in player.layers]
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_count": len(player.layers),
                "layers": layers_data
            }), 200
            
        except Exception as e:
            logger.error(f"Error getting layers for player {player_id}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/layers/add', methods=['POST'])
    def add_layer(player_id):
        """
        Adds a new layer to the stack.
        
        Body:
        {
            "type": "video" | "generator",
            "path": "video/file.mp4" (for video),
            "generator_id": "plasma" (for generator),
            "parameters": {} (for generator),
            "blend_mode": "multiply",
            "opacity": 50,
            "clip_id": "optional-uuid"
        }
        """
        try:
            data = request.get_json()
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            layer_type = data.get('type', 'video')
            blend_mode = data.get('blend_mode', 'normal')
            opacity = float(data.get('opacity', 100))
            # Base clip ID - the clip this layer belongs to
            base_clip_id = data.get('clip_id') or getattr(player, 'current_clip_id', None)
            
            if not base_clip_id:
                return jsonify({"success": False, "error": "No active clip - cannot add layer without a base clip"}), 400
            
            # Erstelle FrameSource basierend auf Typ
            if layer_type == 'generator':
                generator_id = data.get('generator_id')
                parameters = data.get('parameters', {})
                
                if not generator_id:
                    return jsonify({"success": False, "error": "No generator_id provided"}), 400
                
                source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=parameters,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                
                if not source.initialize():
                    return jsonify({"success": False, "error": f"Failed to initialize generator '{generator_id}'"}), 500
                
            elif layer_type == 'video':
                video_path = data.get('path')
                if not video_path:
                    return jsonify({"success": False, "error": "No video path provided"}), 400
                
                # Resolve absolute path
                if not os.path.isabs(video_path):
                    video_path = os.path.join(video_dir, video_path)
                
                if not os.path.exists(video_path):
                    return jsonify({"success": False, "error": f"Video file not found: {video_path}"}), 404
                
                source = VideoSource(
                    video_path=video_path,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                
                if not source.initialize():
                    return jsonify({"success": False, "error": f"Failed to initialize video '{video_path}'"}), 500
                
            else:
                return jsonify({"success": False, "error": f"Unknown type: {layer_type}"}), 400
            
            # Add layer - layer_manager will register the layer source as a clip
            layer_id = player.add_layer(
                source=source,
                clip_id=base_clip_id,  # Base clip this layer belongs to
                blend_mode=blend_mode,
                opacity=opacity
            )
            
            # Get layer info
            layer = player.get_layer(layer_id)
            layer_dict = layer.to_dict() if layer else {}
            layer_clip_id = layer.clip_id if layer else None
            
            logger.debug(f"✅ Layer {layer_id} added to player {player_id}: {source.get_source_name()}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_id": layer_id,
                "clip_id": base_clip_id,  # Base clip the layer belongs to
                "layer_clip_id": layer_clip_id,  # Layer's own clip ID
                "layer": layer_dict
            }), 201
            
        except Exception as e:
            logger.error(f"Error adding layer to player {player_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/layers/<int:layer_id>', methods=['DELETE'])
    def remove_layer(player_id, layer_id):
        """Entfernt einen Layer aus dem Stack."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            success = player.remove_layer(layer_id)
            
            if not success:
                return jsonify({"success": False, "error": f"Layer {layer_id} not found"}), 404
            
            logger.debug(f"🗑️ Layer {layer_id} removed from player {player_id}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_id": layer_id,
                "remaining_layers": len(player.layers)
            }), 200
            
        except Exception as e:
            logger.error(f"Error removing layer {layer_id} from player {player_id}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/layers/<int:layer_id>', methods=['PATCH'])
    def update_layer(player_id, layer_id):
        """
        Aktualisiert Layer-Konfiguration (blend_mode, opacity, enabled).
        
        Body:
        {
            "blend_mode": "screen",
            "opacity": 75,
            "enabled": true
        }
        """
        try:
            data = request.get_json()
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Update layer config
            success = player.update_layer_config(
                layer_id=layer_id,
                blend_mode=data.get('blend_mode'),
                opacity=data.get('opacity'),
                enabled=data.get('enabled')
            )
            
            if not success:
                return jsonify({"success": False, "error": f"Layer {layer_id} not found or update failed"}), 404
            
            # Get updated layer
            layer = player.get_layer(layer_id)
            layer_dict = layer.to_dict() if layer else {}
            
            logger.debug(f"🔧 Layer {layer_id} updated in player {player_id}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_id": layer_id,
                "layer": layer_dict
            }), 200
            
        except Exception as e:
            logger.error(f"Error updating layer {layer_id} in player {player_id}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/layers/reorder', methods=['PUT'])
    def reorder_layers(player_id):
        """
        Changes the order of layers.
        
        Body:
        {
            "order": [2, 0, 1]  // Neue Reihenfolge der Layer-IDs
        }
        """
        try:
            data = request.get_json()
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            new_order = data.get('order', [])
            if not isinstance(new_order, list):
                return jsonify({"success": False, "error": "Order must be a list of layer IDs"}), 400
            
            success = player.reorder_layers(new_order)
            
            if not success:
                return jsonify({"success": False, "error": "Invalid layer order or layer IDs"}), 400
            
            # Get updated layer list
            layers_data = [layer.to_dict() for layer in player.layers]
            
            logger.debug(f"🔄 Layers reordered in player {player_id}: {new_order}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "new_order": new_order,
                "layers": layers_data
            }), 200
            
        except Exception as e:
            logger.error(f"Error reordering layers in player {player_id}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    
    @app.route('/api/player/<player_id>/layers/<int:layer_id>/clip/load', methods=['POST'])
    def load_clip_to_layer(player_id, layer_id):
        """
        Loads a new clip into an existing layer.
        
        Body:
        {
            "type": "video" | "generator",
            "path": "video/file.mp4" (for video),
            "generator_id": "plasma" (for generator),
            "parameters": {} (for generator),
            "clip_id": "optional-uuid"
        }
        """
        try:
            data = request.get_json()
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            layer = player.get_layer(layer_id)
            if not layer:
                return jsonify({"success": False, "error": f"Layer {layer_id} not found"}), 404
            
            layer_type = data.get('type', 'video')
            clip_id = data.get('clip_id')
            
            # Cleanup alte Source
            if layer.source:
                layer.source.cleanup()
            
            # Erstelle neue FrameSource
            if layer_type == 'generator':
                generator_id = data.get('generator_id')
                parameters = data.get('parameters', {})
                
                if not generator_id:
                    return jsonify({"success": False, "error": "No generator_id provided"}), 400
                
                source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=parameters,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                
                if not source.initialize():
                    return jsonify({"success": False, "error": f"Failed to initialize generator '{generator_id}'"}), 500
                
                # Register clip wenn nicht vorhanden
                gen_path = f"generator:{generator_id}"
                if not clip_id:
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=gen_path,
                        relative_path=gen_path,
                        metadata={'type': 'generator', 'generator_id': generator_id, 'parameters': parameters}
                    )
                
            elif layer_type == 'video':
                video_path = data.get('path')
                if not video_path:
                    return jsonify({"success": False, "error": "No video path provided"}), 400
                
                # Resolve absolute path
                if not os.path.isabs(video_path):
                    video_path = os.path.join(video_dir, video_path)
                
                if not os.path.exists(video_path):
                    return jsonify({"success": False, "error": f"Video file not found: {video_path}"}), 404
                
                source = VideoSource(
                    video_path=video_path,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                
                if not source.initialize():
                    return jsonify({"success": False, "error": f"Failed to initialize video '{video_path}'"}), 500
                
                # Register clip wenn nicht vorhanden
                if not clip_id:
                    relative_path = os.path.relpath(video_path, video_dir)
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=video_path,
                        relative_path=relative_path,
                        metadata={'type': 'video'}
                    )
            else:
                return jsonify({"success": False, "error": f"Unknown type: {layer_type}"}), 400
            
            # Ersetze Source im Layer
            layer.source = source
            layer.clip_id = clip_id
            
            layer_dict = layer.to_dict()
            
            logger.debug(f"🔄 Layer {layer_id} source replaced in player {player_id}: {source.get_source_name()}")
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_id": layer_id,
                "clip_id": clip_id,
                "layer": layer_dict
            }), 200
            
        except Exception as e:
            logger.error(f"Error loading clip to layer {layer_id} in player {player_id}: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"success": False, "error": str(e)}), 500


    @app.route('/api/player/<player_id>/layers/duration-mode', methods=['GET', 'PATCH'])
    def layer_duration_mode(player_id):
        """
        GET  → return current duration mode for this player's layer stack.
        PATCH → set it.

        Valid modes:
            'master'    stop when layer 0 completes one pass (default)
            'longest'   loop master until all slave layers have completed ≥ 1 pass
            'shortest'  stop as soon as any layer completes one pass
            'layer_N'   loop master until layer N has completed ≥ 1 pass (N = layer_id int)
        """
        VALID_PREFIXES = {'master', 'longest', 'shortest'}
        player = player_manager.get_player(player_id)
        if not player:
            return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404

        if request.method == 'GET':
            mode = getattr(player.layer_manager, 'layer_duration_mode', 'master')
            return jsonify({"success": True, "player_id": player_id, "duration_mode": mode}), 200

        # PATCH
        data = request.get_json() or {}
        mode = data.get('mode', '')
        if not isinstance(mode, str):
            return jsonify({"success": False, "error": "mode must be a string"}), 400
        valid = mode in VALID_PREFIXES or (mode.startswith('layer_') and mode[6:].isdigit())
        if not valid:
            return jsonify({"success": False,
                            "error": f"Invalid mode '{mode}'. Use master/longest/shortest/layer_N"}), 400

        player.layer_manager.layer_duration_mode = mode
        # Reset play-count on all slave layers so the new mode starts fresh
        for lyr in player.layers[1:]:
            lyr._play_count = 0
        logger.debug(f"⏱ [{player_id}] layer_duration_mode → {mode}")
        return jsonify({"success": True, "player_id": player_id, "duration_mode": mode}), 200


    @app.route('/api/player/<player_id>/layers/<int:layer_id>/align-to/<int:target_layer_id>', methods=['POST'])
    def align_layer_to(player_id, layer_id, target_layer_id):
        """
        Compute and apply the Transport speed multiplier needed to make
        *layer_id* finish at the same time as *target_layer_id*.

        Both layers must have total_frames > 0 on their source.
        The speed is written to the Transport effect of *layer_id* (added
        automatically if missing).  The computed value is also returned so
        the UI can update the speed slider without a round-trip.

        Returns:
            {success, player_id, layer_id, target_layer_id, speed, total_frames, target_total_frames}
        """
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404

            layer = player.get_layer(layer_id)
            target = player.get_layer(target_layer_id)
            if not layer:
                return jsonify({"success": False, "error": f"Layer {layer_id} not found"}), 404
            if not target:
                return jsonify({"success": False, "error": f"Target layer {target_layer_id} not found"}), 404

            src_frames = getattr(layer.source, 'total_frames', 0)
            tgt_frames = getattr(target.source, 'total_frames', 0)
            if not src_frames or not tgt_frames:
                return jsonify({"success": False,
                                "error": "Both layers need total_frames > 0 (video or finite generator)"}), 400

            src_fps = getattr(layer.source, 'fps', 30.0) or 30.0
            tgt_fps = getattr(target.source, 'fps', 30.0) or 30.0

            # speed = (src_duration / tgt_duration)
            # src_duration  = src_frames / src_fps   seconds this layer takes at 1×
            # tgt_duration  = tgt_frames / tgt_fps   seconds the target takes
            src_duration = src_frames / src_fps
            tgt_duration = tgt_frames / tgt_fps
            speed = round(src_duration / tgt_duration, 4)

            # Apply to Transport effect on the layer (create one if absent)
            transport_effect = next(
                (e for e in layer.effects if e.get('id') == 'transport' and e.get('instance')), None
            )
            if transport_effect:
                transport_effect['instance'].update_parameter('speed', speed)
                # Persist to effect config dict too
                transport_effect.setdefault('config', {})['speed'] = speed
                # Also update clip registry so reloads (e.g. on opacity change) use the aligned speed
                layer_clip_id = getattr(layer, 'clip_id', None)
                if layer_clip_id:
                    registry_effects = clip_registry.get_clip_effects(layer_clip_id)
                    for reg_effect in registry_effects:
                        if reg_effect.get('plugin_id') == 'transport':
                            reg_effect.setdefault('parameters', {})['speed'] = speed
                            break
            else:
                logger.warning(
                    f"⚠️ [{player_id}] Layer {layer_id} has no Transport effect — "
                    f"speed={speed} computed but not applied (add Transport first)"
                )

            logger.debug(
                f"⇔ [{player_id}] align layer {layer_id} ({src_frames}fr@{src_fps}fps) "
                f"→ layer {target_layer_id} ({tgt_frames}fr@{tgt_fps}fps): speed={speed}"
            )
            return jsonify({
                "success": True,
                "player_id": player_id,
                "layer_id": layer_id,
                "target_layer_id": target_layer_id,
                "speed": speed,
                "total_frames": src_frames,
                "target_total_frames": tgt_frames,
                "has_transport": transport_effect is not None,
            }), 200

        except Exception as e:
            logger.error(f"Error aligning layer {layer_id} to {target_layer_id}: {e}")
            return jsonify({"success": False, "error": str(e)}), 500


    logger.debug("✅ Layer API routes registered")
