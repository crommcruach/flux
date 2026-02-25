"""
Unified Player API - Einheitliche REST-API für alle Player.

Ersetzt separate Video- und Art-Net-APIs durch ein einheitliches Interface:
- /api/player/<player_id>/...
- Clip-basiertes Management mit UUIDs
- Konsistente Fehlerbehandlung
"""

import os
import time
from flask import request, jsonify
from ...core.logger import get_logger, debug_api, debug_playback, DebugCategories
from ...player.clips.registry import get_clip_registry
from ...player.sources import VideoSource
from ...session.state import get_session_state

logger = get_logger(__name__)


def register_unified_routes(app, player_manager, config, socketio=None, playlist_system=None):
    """
    Registriert vereinheitlichte Player-API-Routes.
    
    Args:
        app: Flask-App-Instanz
        player_manager: PlayerManager-Instanz
        config: Konfiguration
        socketio: SocketIO instance for WebSocket events (optional)
        playlist_system: MultiPlaylistSystem instance for playlist-aware operations (optional)
    """
    clip_registry = get_clip_registry()
    video_dir = config['paths']['video_dir']
    
    # ========================================
    # CLIP MANAGEMENT
    # ========================================
    
    @app.route('/api/player/<player_id>/clip/load', methods=['POST'])
    def load_clip(player_id):
        """Lädt einen Clip (Video oder Generator) in einen Player und registriert ihn."""
        try:
            data = request.get_json()
            clip_type = data.get('type', 'video')  # 'video' or 'generator'
            
            # Get player
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            was_playing = player.is_playing
            
            if clip_type == 'generator':
                # Load generator clip
                generator_id = data.get('generator_id')
                parameters = data.get('parameters', {})
                
                if not generator_id:
                    return jsonify({"success": False, "error": "No generator_id provided"}), 400
                
                # Import here to avoid circular dependency
                from ...player.sources import GeneratorSource
                
                # Create generator source
                logger.info(f"Loading generator '{generator_id}' with parameters: {parameters}")
                generator_source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=parameters,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                
                # Register clip with provided or generated ID
                clip_id = data.get('clip_id')  # Frontend can provide UUID
                if clip_id:
                    # Use frontend-provided clip_id - only register if not already exists!
                    gen_path = f"generator:{generator_id}"
                    if clip_id not in clip_registry.clips:
                        from datetime import datetime
                        clip_registry.clips[clip_id] = {
                            'clip_id': clip_id,
                            'player_id': player_id,
                            'absolute_path': gen_path,
                            'relative_path': gen_path,
                            'metadata': {'type': 'generator', 'generator_id': generator_id, 'parameters': parameters},
                            'created_at': datetime.now().isoformat(),
                            'effects': []
                        }
                    
                    # Update playlist_ids list at current index (if in playlist)
                    if hasattr(player, 'playlist') and gen_path in player.playlist:
                        idx = player.playlist.index(gen_path)
                        if not hasattr(player, 'playlist_ids') or not isinstance(player.playlist_ids, list):
                            player.playlist_ids = []
                        # Extend list if needed
                        while len(player.playlist_ids) <= idx:
                            player.playlist_ids.append(None)
                        player.playlist_ids[idx] = clip_id
                    
                    # Store parameters for future access
                    if not hasattr(player, 'playlist_params'):
                        player.playlist_params = {}
                    player.playlist_params[generator_id] = parameters.copy()
                else:
                    # Fallback: Generate new clip_id
                    gen_path = f"generator:{generator_id}"
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=gen_path,
                        relative_path=gen_path,
                        metadata={'type': 'generator', 'generator_id': generator_id, 'parameters': parameters}
                    )
                    # Store in playlist_ids list at current index (if in playlist)
                    if hasattr(player, 'playlist') and gen_path in player.playlist:
                        idx = player.playlist.index(gen_path)
                        if not hasattr(player, 'playlist_ids') or not isinstance(player.playlist_ids, list):
                            player.playlist_ids = []
                        while len(player.playlist_ids) <= idx:
                            player.playlist_ids.append(None)
                        player.playlist_ids[idx] = clip_id
                    
                    # Store parameters for future access
                    if not hasattr(player, 'playlist_params'):
                        player.playlist_params = {}
                    player.playlist_params[generator_id] = parameters.copy()
                
                # Load generator into player
                success = player.switch_source(generator_source)
                
                if not success:
                    return jsonify({"success": False, "error": "Failed to load generator"}), 500
                
                # Set current clip ID for effect management
                player.current_clip_id = clip_id
                logger.info(f"✅ [{player_id}] Loaded generator: {generator_id} (clip_id={clip_id})")
                
                # Load clip layers from registry
                player.load_clip_layers(clip_id, clip_registry, video_dir)
                
                # Set max_loops if generator is in playlist
                gen_path = f"generator:{generator_id}"
                if hasattr(player, 'playlist') and player.playlist is not None:
                    try:
                        player.playlist_index = player.playlist.index(gen_path)
                        player.max_loops = 1 if player.autoplay else 0
                        debug_api(logger, f"🔁 [{player_id}] Generator in playlist: max_loops={player.max_loops} (autoplay={player.autoplay})")
                    except ValueError:
                        # Generator not in playlist yet - still set max_loops for autoplay
                        player.max_loops = 1 if player.autoplay else 0
                        debug_api(logger, f"🔁 [{player_id}] Generator not in playlist (yet): max_loops={player.max_loops} (autoplay={player.autoplay})")
                
                # Start playback if was playing OR autoplay is enabled
                if was_playing or player.autoplay:
                    # Stop first to ensure clean restart with new clip
                    if player.is_playing:
                        player.stop()
                    player.play()
                    logger.info(f"▶️ [{player_id}] Started playback (was_playing={was_playing}, autoplay={player.autoplay})")
                
                # Auto-save session state (force=True für kritische Clip-Änderung)
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry, force=True)
                
                # Save clip to viewed playlist
                try:
                    from .api_playlists import get_playlist_system
                    playlist_system = get_playlist_system()
                    if playlist_system:
                        viewed = playlist_system.get_viewed_playlist()
                        if viewed:
                            player_state = viewed.players[player_id]
                            # Save complete player state to viewed playlist
                            player_state.clips = list(player.playlist) if hasattr(player, 'playlist') and player.playlist else []
                            player_state.clip_ids = list(player.playlist_ids) if hasattr(player, 'playlist_ids') and player.playlist_ids else []
                            player_state.clip_params = dict(player.playlist_params) if hasattr(player, 'playlist_params') else {}
                            player_state.index = player.playlist_index
                            playlist_system._auto_save()
                            logger.debug(f"💾 Saved generator clip to viewed playlist '{viewed.name}'")
                except Exception as e:
                    logger.warning(f"Failed to save clip to playlist: {e}")
                
                return jsonify({
                    "success": True,
                    "message": f"Generator loaded: {generator_id}",
                    "clip_id": clip_id,
                    "player_id": player_id,
                    "type": "generator",
                    "generator_id": generator_id,
                    "was_playing": was_playing
                })
                
            else:
                # Load video clip (original code)
                video_path = data.get('path')
                
                if not video_path:
                    return jsonify({"success": False, "error": "No path provided"}), 400
                
                # Build absolute path
                if not os.path.isabs(video_path):
                    absolute_path = os.path.join(video_dir, video_path)
                    relative_path = video_path
                else:
                    absolute_path = video_path
                    relative_path = os.path.relpath(video_path, video_dir)
                
                if not os.path.exists(absolute_path):
                    return jsonify({"success": False, "error": f"Video not found: {video_path}"}), 404
                
                # Register clip with provided or generated ID
                clip_id = data.get('clip_id')  # Frontend can provide UUID
                if clip_id:
                    # Use frontend-provided clip_id - only register if not already exists!
                    if clip_id not in clip_registry.clips:
                        from datetime import datetime
                        clip_registry.clips[clip_id] = {
                            'clip_id': clip_id,
                            'player_id': player_id,
                            'absolute_path': absolute_path,
                            'relative_path': relative_path,
                            'filename': os.path.basename(absolute_path),
                            'metadata': {},
                            'created_at': datetime.now().isoformat(),
                            'effects': []
                        }
                    
                    # Update playlist_ids list at current index (if in playlist)
                    if hasattr(player, 'playlist') and absolute_path in player.playlist:
                        idx = player.playlist.index(absolute_path)
                        if not hasattr(player, 'playlist_ids') or not isinstance(player.playlist_ids, list):
                            player.playlist_ids = []
                        while len(player.playlist_ids) <= idx:
                            player.playlist_ids.append(None)
                        player.playlist_ids[idx] = clip_id
                else:
                    # Fallback: Generate new clip_id
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=absolute_path,
                        relative_path=relative_path,
                        metadata={}
                    )
                
                # Load video into player with clip_id for trim/reverse support
                video_source = VideoSource(
                    absolute_path,
                    player.canvas_width,
                    player.canvas_height,
                    config,
                    clip_id=clip_id
                )
                
                success = player.switch_source(video_source)
                
                if not success:
                    return jsonify({"success": False, "error": "Failed to load video"}), 500
                
                # Set current clip ID for effect management AND save to playlist_ids
                player.current_clip_id = clip_id
                # Store UUID in playlist_ids list at current index (if in playlist)
                if hasattr(player, 'playlist') and absolute_path in player.playlist:
                    idx = player.playlist.index(absolute_path)
                    if not hasattr(player, 'playlist_ids') or not isinstance(player.playlist_ids, list):
                        player.playlist_ids = []
                    while len(player.playlist_ids) <= idx:
                        player.playlist_ids.append(None)
                    player.playlist_ids[idx] = clip_id
                logger.info(f"✅ [{player_id}] Loaded clip: {os.path.basename(absolute_path)} (clip_id={clip_id})")
                debug_api(logger, f"   Player state: current_clip_id={player.current_clip_id}, source type={type(video_source).__name__}")
                
                # Load clip layers from registry
                player.load_clip_layers(clip_id, clip_registry, video_dir)
                
                # Update playlist index if applicable
                if hasattr(player, 'playlist') and player.playlist is not None:
                    try:
                        player.playlist_index = player.playlist.index(absolute_path)
                        # Set max_loops based on autoplay (if clip is in playlist)
                        player.max_loops = 1 if player.autoplay else 0
                        debug_api(logger, f"🔁 [{player_id}] Clip in playlist: max_loops={player.max_loops} (autoplay={player.autoplay})")
                    except ValueError:
                        player.playlist_index = -1
                        # Clip not in playlist yet - still set max_loops for autoplay
                        player.max_loops = 1 if player.autoplay else 0
                        debug_api(logger, f"🔁 [{player_id}] Clip not in playlist (yet): max_loops={player.max_loops} (autoplay={player.autoplay})")
                
                # Start playback if was playing OR autoplay is enabled
                if was_playing or player.autoplay:
                    # Stop first to ensure clean restart with new clip
                    if player.is_playing:
                        player.stop()
                    player.play()
                    logger.info(f"▶️ [{player_id}] Started playback (was_playing={was_playing}, autoplay={player.autoplay})")
                
                # Auto-save session state (force=True für kritische Clip-Änderung)
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry, force=True)
                
                # Save clip to viewed playlist
                try:
                    from .api_playlists import get_playlist_system
                    playlist_system = get_playlist_system()
                    if playlist_system:
                        viewed = playlist_system.get_viewed_playlist()
                        if viewed:
                            player_state = viewed.players[player_id]
                            # Save complete player state to viewed playlist
                            player_state.clips = list(player.playlist) if hasattr(player, 'playlist') and player.playlist else []
                            player_state.clip_ids = list(player.playlist_ids) if hasattr(player, 'playlist_ids') and player.playlist_ids else []
                            player_state.index = player.playlist_index
                            playlist_system._auto_save()
                            logger.debug(f"💾 Saved video clip to viewed playlist '{viewed.name}'")
                except Exception as e:
                    logger.warning(f"Failed to save clip to playlist: {e}")
                
                return jsonify({
                    "success": True,
                    "message": f"Clip loaded: {os.path.basename(absolute_path)}",
                    "clip_id": clip_id,
                    "player_id": player_id,
                    "relative_path": relative_path,
                    "was_playing": was_playing
                })
            
        except Exception as e:
            logger.error(f"Error loading clip: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/current', methods=['GET'])
    def get_current_clip(player_id):
        """Gibt die aktuell geladene Clip-ID zurück."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Use current_clip_id from player (set during load_clip)
            clip_id = player.current_clip_id
            
            if not clip_id:
                # Fallback: No clip loaded or old session without clip_id
                if not hasattr(player.source, 'video_path'):
                    return jsonify({"success": False, "error": "No clip loaded"}), 404
                
                # Auto-register a new clip instance
                absolute_path = player.source.video_path
                relative_path = os.path.relpath(absolute_path, video_dir)
                clip_id = clip_registry.register_clip(player_id, absolute_path, relative_path)
                player.current_clip_id = clip_id
            
            clip_data = clip_registry.get_clip(clip_id)
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "clip_data": clip_data
            })
            
        except Exception as e:
            logger.error(f"Error getting current clip: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # CLIP EFFECTS
    # ========================================
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects', methods=['GET'])
    def get_clip_effects(player_id, clip_id):
        """Gibt alle Effekte eines Clips zurück mit Live-Parametern von aktiven Instanzen."""
        try:
            effects = clip_registry.get_clip_effects(clip_id)
            
            # Check if this clip_id belongs to an active layer - if so, get live instances
            player = player_manager.get_player(player_id)
            active_layer_effects = None
            if player and hasattr(player, 'layers'):
                logger.info(f"🔍 [get_clip_effects] Searching for active layer with clip_id={clip_id}, player has {len(player.layers)} layers")
                for layer_idx, layer in enumerate(player.layers):
                    layer_clip_id = getattr(layer, 'clip_id', None)
                    logger.info(f"🔍 [get_clip_effects] Layer {layer_idx}: clip_id={layer_clip_id}, matches={layer_clip_id == clip_id}")
                    if hasattr(layer, 'clip_id') and layer.clip_id == clip_id:
                        # Found the active layer - use its live effect instances
                        active_layer_effects = layer.effects
                        logger.info(f"✅ [get_clip_effects] Found active layer {layer_idx} with clip_id {clip_id}, has {len(layer.effects) if layer.effects else 0} effects")
                        break
            
            # Filter out non-serializable data and update with live parameters
            serializable_effects = []
            for i, effect in enumerate(effects):
                effect_copy = effect.copy()
                
                # Prefer live parameters from active layer instances
                live_instance = None
                plugin_id = effect.get('plugin_id')
                
                # Search for matching plugin in active layer by plugin_id, not just index
                if active_layer_effects:
                    for layer_effect in active_layer_effects:
                        if layer_effect.get('id') == plugin_id:
                            live_instance = layer_effect.get('instance')
                            logger.info(f"🔍 [get_clip_effects] Found LIVE instance for {plugin_id} in active layer")
                            break
                
                # Fallback to registry instance (will be stuck at position=0 during playback)
                if not live_instance and 'instance' in effect:
                    live_instance = effect['instance']
                    logger.info(f"⚠️ [get_clip_effects] Using REGISTRY instance for {plugin_id} (not live!)")
                
                # Get live parameters from instance if available
                if live_instance is not None:
                    try:
                        # SPECIAL: Initialize transport ONLY if not already initialized
                        if effect.get('plugin_id') == 'transport' and hasattr(live_instance, '_initialize_state'):
                            # Check if already initialized by looking at out_point
                            if live_instance.out_point == 0 and player and len(player.layers) > 0 and player.layers[0].source:
                                logger.info(f"🎬 [get_clip_effects] Transport NOT initialized yet, initializing for clip {clip_id}")
                                live_instance._initialize_state(player.layers[0].source)
                                logger.info(f"🎬 [get_clip_effects] Transport initialized: out_point={live_instance.out_point}")
                            else:
                                logger.info(f"🎬 [get_clip_effects] Transport already initialized, skipping (out_point={live_instance.out_point})")
                        
                        live_params = live_instance.get_parameters()
                        if live_params:
                            effect_copy['parameters'] = live_params
                            # DEBUG: Log transport position
                            if effect.get('plugin_id') == 'transport':
                                logger.info(f"🎬 [get_clip_effects] Transport params: current_position={live_instance.current_position}, in_point={live_instance.in_point}, out_point={live_instance.out_point}")
                                logger.info(f"🎬 [get_clip_effects] Transport get_parameters returned: {live_params.get('transport_position', 'N/A')}")
                            debug_api(logger, f"Got live parameters for {effect.get('plugin_id')}: {live_params}")
                    except Exception as e:
                        logger.warning(f"Could not get live parameters from {effect.get('plugin_id')}: {e}")
                
                # Merge UIDs from stored parameters into live parameters
                stored_params = effect.get('parameters', {})
                if stored_params and 'parameters' in effect_copy:
                    for param_name, param_value in stored_params.items():
                        # If stored parameter has _uid, merge it with live value
                        if isinstance(param_value, dict) and '_uid' in param_value:
                            if param_name in effect_copy['parameters']:
                                # Get current live value
                                live_value = effect_copy['parameters'][param_name]
                                
                                # If live value is already a dict with metadata, preserve it
                                if isinstance(live_value, dict):
                                    effect_copy['parameters'][param_name] = {
                                        **live_value,  # Keep existing metadata (_value, _rangeMin, _rangeMax)
                                        '_uid': param_value['_uid']  # Add stored UID
                                    }
                                else:
                                    # Live value is plain number, wrap with UID
                                    effect_copy['parameters'][param_name] = {
                                        '_value': live_value,
                                        '_uid': param_value['_uid']
                                    }
                
                # Remove instance from response
                if 'instance' in effect_copy:
                    del effect_copy['instance']
                
                serializable_effects.append(effect_copy)
            
            return jsonify({
                "success": True,
                "clip_id": clip_id,
                "effects": serializable_effects
            })
            
        except Exception as e:
            logger.error(f"Error getting clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects/add', methods=['POST'])
    def add_clip_effect(player_id, clip_id):
        """Fügt einen Effekt zu einem Clip hinzu."""
        try:
            data = request.get_json()
            plugin_id = data.get('plugin_id')
            
            if not plugin_id:
                return jsonify({"success": False, "error": "Missing plugin_id"}), 400
            
            # Get player and plugin manager
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # LAZY REGISTRATION: If clip doesn't exist, try to register it from playlist
            if clip_id not in clip_registry.clips:
                logger.warning(f"⚠️ Clip {clip_id} not found in registry, attempting lazy registration from playlist")
                
                # Find path in player.playlist_ids
                if hasattr(player, 'playlist_ids'):
                    # Reverse lookup: Find path by clip_id
                    found_path = None
                    for path, pid in player.playlist_ids.items():
                        if pid == clip_id:
                            found_path = path
                            break
                    
                    if found_path:
                        from datetime import datetime
                        logger.info(f"✅ Lazy registering clip {clip_id} for path: {found_path}")
                        
                        # Register the clip
                        clip_registry.clips[clip_id] = {
                            'clip_id': clip_id,
                            'player_id': player_id,
                            'absolute_path': found_path,
                            'relative_path': os.path.relpath(found_path, video_dir) if not found_path.startswith('generator:') else found_path,
                            'filename': os.path.basename(found_path),
                            'metadata': {},
                            'created_at': datetime.now().isoformat(),
                            'effects': []
                        }
                    else:
                        return jsonify({"success": False, "error": f"Clip '{clip_id}' not found in playlist"}), 404
                else:
                    return jsonify({"success": False, "error": f"Clip '{clip_id}' not found"}), 404
            
            pm = player.plugin_manager
            if plugin_id not in pm.registry:
                return jsonify({"success": False, "error": f"Plugin '{plugin_id}' not found"}), 404
            
            plugin_class = pm.registry[plugin_id]
            
            # Build effect metadata
            metadata = plugin_class.METADATA.copy()
            if hasattr(plugin_class, 'PARAMETERS'):
                parameters = []
                for param in plugin_class.PARAMETERS:
                    if isinstance(param, dict):
                        param_dict = param.copy()
                        if 'type' in param_dict and hasattr(param_dict['type'], 'name'):
                            param_dict['type'] = param_dict['type'].name
                    else:
                        param_dict = {
                            'name': param.name,
                            'type': param.type.name if hasattr(param.type, 'name') else str(param.type),
                            'default': param.default,
                            'min': getattr(param, 'min', None),
                            'max': getattr(param, 'max', None),
                            'description': getattr(param, 'description', '')
                        }
                    parameters.append(param_dict)
                metadata['parameters'] = parameters
            
            if 'type' in metadata and hasattr(metadata['type'], 'value'):
                metadata['type'] = metadata['type'].value
            
            # Create effect data
            effect_data = {
                'plugin_id': plugin_id,
                'metadata': metadata,
                'parameters': {}
            }
            
            # Set default parameters
            if 'parameters' in metadata:
                for param in metadata['parameters']:
                    effect_data['parameters'][param['name']] = param['default']
            
            # Add to clip registry
            success = clip_registry.add_effect_to_clip(clip_id, effect_data)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to add effect"}), 500
            
            logger.info(f"✅ Effect '{plugin_id}' added to clip {clip_id} ({player_id})")
            
            # Reload effects on ALL players that have this clip loaded
            # (not just the player in the API route - clip might be in both video AND artnet players!)
            logger.info(f"🔍 Checking all players for clip {clip_id}...")
            reloaded_on_players = []
            for check_player_id, check_player in player_manager.players.items():
                if check_player and hasattr(check_player, 'layers') and check_player.layers:
                    # Log what layers this player has
                    layer_info = [(i, layer.clip_id if hasattr(layer, 'clip_id') else 'no-id') for i, layer in enumerate(check_player.layers)]
                    logger.info(f"  Player '{check_player_id}': {len(check_player.layers)} layers - {layer_info}")
                    
                    clip_is_loaded = any(layer.clip_id == clip_id for layer in check_player.layers)
                    if clip_is_loaded:
                        logger.info(f"  ✅ Found clip {clip_id} in {check_player_id} player - reloading effects")
                        if hasattr(check_player, 'reload_all_layer_effects'):
                            check_player.reload_all_layer_effects()
                            reloaded_on_players.append(check_player_id)
                        else:
                            logger.warning(f"⚠️ Player {check_player_id} doesn't have reload_all_layer_effects method")
                    else:
                        logger.debug(f"  ➖ Clip {clip_id} not found in {check_player_id} player")
                else:
                    logger.debug(f"  Player '{check_player_id}': No layers or player not initialized")
            
            if reloaded_on_players:
                logger.info(f"✅ Clip effects reloaded on players: {', '.join(reloaded_on_players)}")
            else:
                logger.warning(f"⚠️ Clip {clip_id} not currently loaded in any player, effects will be loaded when clip is played")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            # Emit WebSocket event for effect list change
            if socketio:
                try:
                    socketio.emit('effects.changed', {
                        'player_id': player_id,
                        'clip_id': clip_id,
                        'action': 'add',
                        'effect_name': plugin_id
                    }, namespace='/effects')
                    logger.debug(f"📡 WebSocket: effects.changed emitted (add {plugin_id})")
                except Exception as e:
                    logger.error(f"❌ Error emitting effects.changed: {e}")
            
            return jsonify({"success": True, "clip_id": clip_id})
            
        except Exception as e:
            logger.error(f"Error adding clip effect: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects/<int:index>', methods=['DELETE'])
    def remove_clip_effect(player_id, clip_id, index):
        """Entfernt einen Effekt von einem Clip."""
        try:
            success = clip_registry.remove_effect_from_clip(clip_id, index)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to remove effect"}), 500
            
            logger.info(f"🗑️ Effect removed from clip {clip_id} at index {index}")
            
            # Reload effects on ALL players that have this clip loaded
            # (not just the player in the API route - clip might be in both video AND artnet players!)
            reloaded_on_players = []
            for check_player_id, check_player in player_manager.players.items():
                if check_player and hasattr(check_player, 'layers') and check_player.layers:
                    clip_is_loaded = any(layer.clip_id == clip_id for layer in check_player.layers)
                    if clip_is_loaded:
                        logger.debug(f"Reloading effects for clip {clip_id} on {check_player_id} player")
                        if hasattr(check_player, 'reload_all_layer_effects'):
                            check_player.reload_all_layer_effects()
                            reloaded_on_players.append(check_player_id)
                        else:
                            logger.warning(f"⚠️ Player {check_player_id} doesn't have reload_all_layer_effects method")
            
            if reloaded_on_players:
                logger.info(f"✅ Clip effects reloaded on players: {', '.join(reloaded_on_players)}")
            else:
                logger.debug(f"Clip {clip_id} not currently loaded in any player, skipping effect reload")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            # Emit WebSocket event for effect list change
            if socketio:
                try:
                    socketio.emit('effects.changed', {
                        'player_id': player_id,
                        'clip_id': clip_id,
                        'action': 'remove',
                        'index': index
                    }, namespace='/effects')
                    logger.debug(f"📡 WebSocket: effects.changed emitted (remove index {index})")
                except Exception as e:
                    logger.error(f"❌ Error emitting effects.changed: {e}")
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Error removing clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects/<int:index>/parameter', methods=['PUT'])
    def update_clip_effect_parameter(player_id, clip_id, index):
        """Aktualisiert einen Parameter eines Clip-Effekts."""
        try:
            data = request.get_json()
            param_name = data.get('name')
            param_value = data.get('value')
            range_min = data.get('rangeMin')
            range_max = data.get('rangeMax')
            uid = data.get('uid')  # Preserve UID for sequence restoration
            
            if not param_name:
                return jsonify({"success": False, "error": "Missing parameter name"}), 400
            
            effects = clip_registry.get_clip_effects(clip_id)
            
            if index < 0 or index >= len(effects):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            effect = effects[index]
            
            # Store parameter with range metadata if provided (for persistence)
            if range_min is not None and range_max is not None:
                param_data = {
                    '_value': param_value,
                    '_rangeMin': range_min,
                    '_rangeMax': range_max
                }
                # Preserve UID if provided
                if uid:
                    param_data['_uid'] = uid
                effect['parameters'][param_name] = param_data
                logger.info(f"🎚️ API received triple-slider: {param_name}={param_value}, range=[{range_min}, {range_max}]")
            else:
                # For simple values, store as dict if UID is present, otherwise plain value
                if uid:
                    param_data = {
                        '_value': param_value,
                        '_uid': uid
                    }
                else:
                    param_data = param_value
                effect['parameters'][param_name] = param_data
            
            # For transport_position, pass the full dict with range metadata
            # For other parameters, extract scalar value
            if param_name == 'transport_position':
                value_to_update = param_data  # Keep full dict {_value, _rangeMin, _rangeMax}
            else:
                # Extract scalar value from dict format (triple-slider sends {_value, _rangeMin, _rangeMax})
                value_to_update = param_data
                if isinstance(param_data, dict) and '_value' in param_data:
                    value_to_update = param_data['_value']
            
            # Update LIVE plugin instances in ALL players that have this clip loaded
            # (not just the player in the API route - clip might be in both video AND artnet players!)
            updated_live_players = []
            
            for check_player_id, check_player in player_manager.players.items():
                if check_player and hasattr(check_player, 'layers'):
                    for layer in check_player.layers:
                        if hasattr(layer, 'clip_id') and layer.clip_id == clip_id:
                            # Found the active layer - update its live effect instance
                            if index < len(layer.effects):
                                live_effect = layer.effects[index]
                                if 'instance' in live_effect and live_effect['instance']:
                                    live_effect['instance'].update_parameter(param_name, value_to_update)
                                    updated_live_players.append(check_player_id)
                                    logger.debug(f"✅ Updated live effect in {check_player_id} player: Layer {layer.layer_id}, effect {index}, {param_name}={value_to_update}")
                                    break  # Only update first matching layer per player
            
            if updated_live_players:
                logger.info(f"✅ Parameter updated on players: {', '.join(updated_live_players)}")
            else:
                # Fallback: Update registry instance (for non-layer clips)
                if 'instance' in effect and effect['instance']:
                    effect['instance'].update_parameter(param_name, value_to_update)
                    logger.info(f"✅ Updated registry effect instance: {clip_id}[{index}].{param_name} (not currently loaded)")
            
            # B3: Invalidate cache so player detects parameter change
            clip_registry._invalidate_cache(clip_id)
            
            debug_api(logger, f"🔧 Clip effect parameter updated: {clip_id}[{index}].{param_name} = {param_value}")
            
            # DON'T reload layer effects - we just updated the live instance!
            # Reloading would recreate all plugins from registry and lose runtime state.
            # Only reload when adding/removing/toggling effects, not when updating parameters.
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Error updating clip effect parameter: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects/<int:index>/toggle', methods=['POST'])
    def toggle_clip_effect(player_id, clip_id, index):
        """
        Toggles enabled/disabled state of a clip effect.
        Parameters are preserved, but effect is not applied when disabled.
        """
        try:
            effects = clip_registry.get_clip_effects(clip_id)
            
            if index < 0 or index >= len(effects):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            effect = effects[index]
            
            # Toggle enabled state (default is enabled if not set)
            current_state = effect.get('enabled', True)
            new_state = not current_state
            effect['enabled'] = new_state
            
            # Invalidate cache so player detects the change
            clip_registry._invalidate_cache(clip_id)
            
            logger.info(f"Clip effect {clip_id}[{index}] toggled: {'enabled' if new_state else 'disabled'}")
            
            # Reload effects on ALL players that have this clip loaded
            reloaded_on_players = []
            for check_player_id, check_player in player_manager.players.items():
                if check_player and hasattr(check_player, 'layers') and check_player.layers:
                    clip_is_loaded = any(layer.clip_id == clip_id for layer in check_player.layers)
                    if clip_is_loaded:
                        logger.debug(f"Reloading effects for clip {clip_id} on {check_player_id} player")
                        if hasattr(check_player, 'reload_all_layer_effects'):
                            check_player.reload_all_layer_effects()
                            reloaded_on_players.append(check_player_id)
            
            if reloaded_on_players:
                logger.info(f"✅ Clip effects reloaded on players: {', '.join(reloaded_on_players)}")
            else:
                logger.debug(f"Clip {clip_id} not currently loaded in any player, skipping effect reload")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            return jsonify({
                "success": True,
                "enabled": new_state,
                "message": f"Effect {'enabled' if new_state else 'disabled'}"
            })
            
        except Exception as e:
            logger.error(f"Error toggling clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/effects/clear', methods=['POST'])
    def clear_clip_effects(player_id, clip_id):
        """Entfernt alle Effekte von einem Clip."""
        try:
            success = clip_registry.clear_clip_effects(clip_id)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to clear effects"}), 500
            
            # Also clear from player's clip_effects
            player = player_manager.get_player(player_id)
            if player:
                clip_data = clip_registry.get_clip(clip_id)
                if clip_data and hasattr(player, 'clip_effects'):
                    abs_path = clip_data['absolute_path']
                    if abs_path in player.clip_effects:
                        player.clip_effects[abs_path] = []
                
                # Reload effects on ALL players that have this clip loaded
                reloaded_on_players = []
                for check_player_id, check_player in player_manager.players.items():
                    if check_player and hasattr(check_player, 'layers') and check_player.layers:
                        clip_is_loaded = any(layer.clip_id == clip_id for layer in check_player.layers)
                        if clip_is_loaded:
                            logger.debug(f"Reloading effects for clip {clip_id} on {check_player_id} player")
                            if hasattr(check_player, 'reload_all_layer_effects'):
                                check_player.reload_all_layer_effects()
                                reloaded_on_players.append(check_player_id)
                
                if reloaded_on_players:
                    logger.info(f"✅ Clip effects reloaded on players: {', '.join(reloaded_on_players)}")
                else:
                    logger.debug(f"Clip {clip_id} not currently loaded in any player, skipping effect reload")
            
            logger.info(f"🗑️ All effects cleared from clip {clip_id}")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            # Emit WebSocket event for effect list change
            if socketio:
                try:
                    socketio.emit('effects.changed', {
                        'player_id': player_id,
                        'clip_id': clip_id,
                        'action': 'clear'
                    }, namespace='/effects')
                    logger.debug(f"📡 WebSocket: effects.changed emitted (clear all)")
                except Exception as e:
                    logger.error(f"❌ Error emitting effects.changed: {e}")
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Error clearing clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYER EFFECT CHAIN (Unified API for /api/player/effects and /api/artnet/effects)
    # ========================================
    
    @app.route('/api/player/<player_id>/effects', methods=['GET'])
    def get_player_effects(player_id):
        """Gibt die Effect Chain eines Players zurück."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({'error': f'Player "{player_id}" not found'}), 404
            
            # Get effects from appropriate chain based on player_id
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            effects = player.get_effect_chain(chain_type=chain_type)
            
            return jsonify({
                'success': True,
                'player_id': player_id,
                'effects': effects,
                'count': len(effects)
            })
            
        except Exception as e:
            logger.error(f"Error getting player effects: {e}")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/api/player/<player_id>/effects/add', methods=['POST'])
    def add_player_effect(player_id):
        """Fügt einen Effect zur Player Chain hinzu."""
        try:
            data = request.get_json()
            plugin_id = data.get('plugin_id')
            config = data.get('config', {})
            
            if not plugin_id:
                return jsonify({"success": False, "error": "plugin_id required"}), 400
            
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Debug: Log playlist state
            logger.info(f"[EFFECT ADD DEBUG] playlist_system exists: {playlist_system is not None}")
            if playlist_system:
                logger.info(f"[EFFECT ADD DEBUG] viewed={playlist_system.viewed_playlist_id}, active={playlist_system.active_playlist_id}")
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - add to stored effects
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    
                    # Create effect entry in playlist storage format
                    effect_entry = {
                        'index': len(player_state.global_effects),
                        'plugin_id': plugin_id,
                        'parameters': config,
                        'enabled': True,
                        'config': config
                    }
                    player_state.global_effects.append(effect_entry)
                    
                    logger.info(f"[EFFECT ADD] Added '{plugin_id}' to viewed playlist '{viewed_playlist.name}' {player_id} effects")
                    
                    # Save playlist state
                    playlist_system._auto_save()
                    
                    # Emit WebSocket event
                    if socketio:
                        try:
                            socketio.emit('effects.changed', {
                                'player_id': player_id,
                                'action': 'add',
                                'effect_name': plugin_id
                            }, namespace='/effects')
                        except Exception as e:
                            logger.error(f"❌ Error emitting effects.changed: {e}")
                    
                    return jsonify({"success": True, "message": f"Effect '{plugin_id}' added to viewed playlist", "player_id": player_id})
            
            # Otherwise add to physical player (active playlist)
            logger.info(f"[EFFECT ADD DEBUG] Adding to physical player (active playlist)")
            # Use appropriate chain type
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.add_effect_to_chain(plugin_id, config, chain_type=chain_type)
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry)
                
                # Emit WebSocket event for player effect change
                if socketio:
                    try:
                        socketio.emit('effects.changed', {
                            'player_id': player_id,
                            'action': 'add',
                            'effect_name': plugin_id
                        }, namespace='/effects')
                        logger.debug(f"📡 WebSocket: effects.changed emitted (player {player_id} add {plugin_id})")
                    except Exception as e:
                        logger.error(f"❌ Error emitting effects.changed: {e}")
                
                return jsonify({"success": True, "message": message, "player_id": player_id})
            else:
                return jsonify({"success": False, "error": message}), 400
                
        except Exception as e:
            logger.error(f"Error adding player effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/effects/<int:index>', methods=['DELETE'])
    def remove_player_effect(player_id, index):
        """Entfernt einen Effect aus der Player Chain."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - remove from stored effects
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    
                    if 0 <= index < len(player_state.global_effects):
                        removed_effect = player_state.global_effects.pop(index)
                        
                        # Re-index remaining effects
                        for i, effect in enumerate(player_state.global_effects):
                            effect['index'] = i
                        
                        logger.info(f"[EFFECT REMOVE] Removed effect at index {index} from viewed playlist '{viewed_playlist.name}' {player_id}")
                        
                        # Save playlist state
                        playlist_system._auto_save()
                        
                        # Emit WebSocket event
                        if socketio:
                            try:
                                socketio.emit('effects.changed', {
                                    'player_id': player_id,
                                    'action': 'remove',
                                    'index': index
                                }, namespace='/effects')
                            except Exception as e:
                                logger.error(f"❌ Error emitting effects.changed: {e}")
                        
                        return jsonify({"success": True, "message": f"Effect removed from viewed playlist", "player_id": player_id})
                    else:
                        return jsonify({"success": False, "error": f"Invalid index {index}"}), 400
            
            # Otherwise remove from physical player (active playlist)
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.remove_effect_from_chain(index, chain_type=chain_type)
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry)
                
                # Emit WebSocket event for player effect change
                if socketio:
                    try:
                        socketio.emit('effects.changed', {
                            'player_id': player_id,
                            'action': 'remove',
                            'index': index
                        }, namespace='/effects')
                        logger.debug(f"📡 WebSocket: effects.changed emitted (player {player_id} remove index {index})")
                    except Exception as e:
                        logger.error(f"❌ Error emitting effects.changed: {e}")
                
                return jsonify({"success": True, "message": message, "player_id": player_id})
            else:
                return jsonify({"success": False, "error": message}), 400
                
        except Exception as e:
            logger.error(f"Error removing player effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/effects/clear', methods=['POST'])
    def clear_player_effects(player_id):
        """Entfernt alle Effects aus der Player Chain."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - clear stored effects
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    player_state.global_effects = []
                    
                    logger.info(f"[EFFECT CLEAR] Cleared all effects from viewed playlist '{viewed_playlist.name}' {player_id}")
                    
                    # Save playlist state
                    playlist_system._auto_save()
                    
                    # Emit WebSocket event
                    if socketio:
                        try:
                            socketio.emit('effects.changed', {
                                'player_id': player_id,
                                'action': 'clear'
                            }, namespace='/effects')
                        except Exception as e:
                            logger.error(f"❌ Error emitting effects.changed: {e}")
                    
                    return jsonify({"success": True, "message": "All effects cleared from viewed playlist", "player_id": player_id})
            
            # Otherwise clear from physical player (active playlist)
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.clear_effects_chain(chain_type=chain_type)
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            # Emit WebSocket event for player effect change
            if socketio:
                try:
                    socketio.emit('effects.changed', {
                        'player_id': player_id,
                        'action': 'clear'
                    }, namespace='/effects')
                    logger.debug(f"📡 WebSocket: effects.changed emitted (player {player_id} clear all)")
                except Exception as e:
                    logger.error(f"❌ Error emitting effects.changed: {e}")
            
            return jsonify({"success": True, "message": message, "player_id": player_id})
            
        except Exception as e:
            logger.error(f"Error clearing player effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/effects/<int:index>/parameter', methods=['PUT'])
    def update_player_effect_parameter(player_id, index):
        """Aktualisiert einen Parameter eines Player Effects."""
        try:
            data = request.get_json()
            param_name = data.get('name')
            value = data.get('value')
            range_min = data.get('rangeMin')
            range_max = data.get('rangeMax')
            uid = data.get('uid')  # Preserve UID for sequence restoration
            
            if param_name is None or value is None:
                return jsonify({"success": False, "error": "name and value required"}), 400
            
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - update stored effect parameter
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    
                    if 0 <= index < len(player_state.global_effects):
                        effect = player_state.global_effects[index]
                        
                        # Update parameter with range metadata if provided
                        if range_min is not None and range_max is not None:
                            effect['parameters'][param_name] = {
                                '_value': value,
                                '_rangeMin': range_min,
                                '_rangeMax': range_max
                            }
                            if uid:
                                effect['parameters'][param_name]['_uid'] = uid
                        else:
                            effect['parameters'][param_name] = value
                        
                        # Also update config dict (they're separate in storage)
                        if 'config' in effect:
                            effect['config'][param_name] = effect['parameters'][param_name]
                        
                        logger.info(f"[EFFECT PARAM] Updated {param_name}={value} for effect at index {index} in viewed playlist '{viewed_playlist.name}' {player_id}")
                        
                        # Save playlist state
                        playlist_system._auto_save()
                        
                        return jsonify({"success": True, "player_id": player_id, "index": index, "parameter": param_name, "value": value})
                    else:
                        return jsonify({"success": False, "error": f"Invalid index {index}"}), 400
            
            # Otherwise update physical player (active playlist)
            # Get appropriate chain from effect_processor
            chain = player.effect_processor.artnet_effect_chain if player_id == 'artnet' else player.effect_processor.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return jsonify({"success": False, "error": "Invalid index"}), 400
            
            effect = chain[index]
            # Plugin instance always gets the actual value, not the metadata wrapper
            effect['instance'].update_parameter(param_name, value)
            
            # Store parameter with range metadata if provided (for UI persistence)
            if range_min is not None and range_max is not None:
                effect['config'][param_name] = {
                    '_value': value,
                    '_rangeMin': range_min,
                    '_rangeMax': range_max
                }
                # Preserve UID if provided
                if uid:
                    effect['config'][param_name]['_uid'] = uid
            else:
                # For simple values, store as dict if UID is present, otherwise plain value
                if uid:
                    effect['config'][param_name] = {
                        '_value': value,
                        '_uid': uid
                    }
                else:
                    effect['config'][param_name] = value
            
            logger.info(f"✅ Parameter '{param_name}' von Effect {index} auf {value} gesetzt ({player_id})")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry)
            
            return jsonify({"success": True, "player_id": player_id, "index": index, "parameter": param_name, "value": value})
            
        except Exception as e:
            logger.error(f"Error updating player effect parameter: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/effects/<int:index>/toggle', methods=['POST'])
    def toggle_player_effect(player_id, index):
        """Toggles the enabled/disabled state of a player-level effect."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Check if we're viewing a different playlist than the active one
            if playlist_system and playlist_system.viewed_playlist_id != playlist_system.active_playlist_id:
                # Viewing non-active playlist - toggle in stored effects
                viewed_playlist = playlist_system.playlists.get(playlist_system.viewed_playlist_id)
                if viewed_playlist:
                    player_state = viewed_playlist.players[player_id]
                    
                    if 0 <= index < len(player_state.global_effects):
                        effect = player_state.global_effects[index]
                        effect['enabled'] = not effect.get('enabled', True)
                        
                        logger.info(f"[EFFECT TOGGLE] Toggled effect at index {index} to {effect['enabled']} in viewed playlist '{viewed_playlist.name}' {player_id}")
                        
                        # Save playlist state
                        playlist_system._auto_save()
                        
                        return jsonify({"success": True, "enabled": effect['enabled'], "message": f"Effect toggled in viewed playlist"})
                    else:
                        return jsonify({"success": False, "message": f"Invalid index {index}"}), 400
            
            # Otherwise toggle on physical player (active playlist)
            # Determine chain type based on player_id
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            
            # Use the toggle method from player
            success, enabled, message = player.toggle_effect_enabled(index, chain_type=chain_type)
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry)
                
                return jsonify({"success": True, "enabled": enabled, "message": message})
            else:
                return jsonify({"success": False, "message": message}), 400
                
        except Exception as e:
            logger.error(f"Error toggling player effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYBACK CONTROL
    # ========================================
    
    @app.route('/api/player/<player_id>/play', methods=['POST'])
    def unified_play(player_id):
        """Startet die Wiedergabe."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Prüfe ob echtes Video geladen ist (nicht DummySource)
            from ...player.sources import DummySource
            if not player.source or isinstance(player.source, DummySource):
                logger.info(f"⚠️ [{player_id}] Kein Video geladen - Play abgebrochen")
                return jsonify({"success": False, "error": "Kein Video geladen"}), 400
            
            player.play()
            logger.info(f"▶️ Player '{player_id}' playing")
            
            return jsonify({"success": True, "player_id": player_id, "status": "playing"})
            
        except Exception as e:
            logger.error(f"Error playing: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/pause', methods=['POST'])
    def unified_pause(player_id):
        """Pausiert die Wiedergabe."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            player.pause()
            logger.info(f"⏸️ Player '{player_id}' paused")
            
            return jsonify({"success": True, "player_id": player_id, "status": "paused"})
            
        except Exception as e:
            logger.error(f"Error pausing: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/stop', methods=['POST'])
    def unified_stop(player_id):
        """Stoppt die Wiedergabe."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            player.stop()
            logger.info(f"⏹️ Player '{player_id}' stopped")
            
            return jsonify({"success": True, "player_id": player_id, "status": "stopped"})
            
        except Exception as e:
            logger.error(f"Error stopping: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYER STATUS & INFO
    # ========================================
    
    @app.route('/api/player/<player_id>/status', methods=['GET'])
    def get_player_status(player_id):
        """Gibt den Status eines Players zurück."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            current_video = None
            clip_id = None
            if hasattr(player, 'source') and player.source:
                if hasattr(player.source, 'video_path'):
                    # Regular video source
                    current_video = os.path.relpath(player.source.video_path, video_dir)
                elif hasattr(player.source, 'generator_id'):
                    # Generator source
                    current_video = f"generator:{player.source.generator_id}"
            
            # Get clip_id from player (stored in player.current_clip_id)
            if hasattr(player, 'current_clip_id'):
                clip_id = player.current_clip_id
            
            # Get playlist with full metadata (for GUI reconstruction)
            playlist = []
            if hasattr(player, 'playlist'):
                for idx, path in enumerate(player.playlist):
                    # Don't relativize generator paths
                    if path.startswith('generator:'):
                        rel_path = path
                    else:
                        try:
                            rel_path = os.path.relpath(path, video_dir)
                        except:
                            rel_path = path
                    
                    # Build playlist item object
                    if path.startswith('generator:'):
                        # Generator item
                        generator_id = path.replace('generator:', '')
                        playlist_item = {
                            'path': rel_path,
                            'type': 'generator',
                            'generator_id': generator_id
                        }
                        # Include parameters if stored
                        if hasattr(player, 'playlist_params') and generator_id in player.playlist_params:
                            playlist_item['parameters'] = player.playlist_params[generator_id]
                    else:
                        # Regular video item
                        playlist_item = {
                            'path': rel_path,
                            'type': 'video'
                        }
                    
                    # Add UUID from playlist_ids list (now using index instead of path as key)
                    if hasattr(player, 'playlist_ids') and isinstance(player.playlist_ids, list) and idx < len(player.playlist_ids):
                        playlist_item['id'] = player.playlist_ids[idx]
                    
                    playlist.append(playlist_item)
            
            response_data = {
                "success": True,
                "player_id": player_id,
                "is_playing": player.is_playing,
                "is_paused": player.is_paused,
                "current_frame": player.current_frame,
                "total_frames": getattr(player.source, 'total_frames', 0) if player.source else 0,
                "current_video": current_video,
                "playlist": playlist,
                "playlist_index": getattr(player, 'playlist_index', -1),
                "current_clip_index": getattr(player, 'current_clip_index', 0),  # For Master/Slave sync
                "autoplay": getattr(player, 'autoplay', False),
                "loop": getattr(player, 'loop_playlist', False),
                "max_loops": getattr(player, 'max_loops', 1),
                "is_master": player_manager.is_master(player_id),  # Master/Slave sync status
                "master_playlist": player_manager.get_master_playlist()  # Current master (if any)
            }
            
            # Only include clip_id if it exists
            if clip_id:
                response_data["clip_id"] = clip_id
            
            return jsonify(response_data)
        except Exception as e:
            logger.error(f"Error getting player status: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYLIST NAVIGATION
    # ========================================
    
    @app.route('/api/player/<player_id>/next', methods=['POST'])
    def next_video(player_id):
        """Lädt das nächste Video aus der Playlist."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"success": False, "error": "No playlist configured"}), 404
        
            # Calculate next index
            next_index = player.playlist_index + 1
            if next_index >= len(player.playlist):
                if player.loop_playlist:
                    next_index = 0
                else:
                    return jsonify({"success": False, "error": "End of playlist"}), 400
            
            # Get next video path
            next_video_path = player.playlist[next_index]
            
            was_playing = player.is_playing
        
            # Check if it's a generator or video
            if next_video_path.startswith('generator:'):
                # It's a generator
                generator_id = next_video_path.split(':', 1)[1]
                
                # Get default parameters from plugin registry
                from ...plugins.manager import get_plugin_manager
                pm = get_plugin_manager()
                
                params_dict = {}
                if generator_id in pm.registry:
                    plugin_class = pm.registry[generator_id]
                    if hasattr(plugin_class, 'PARAMETERS'):
                        for param in plugin_class.PARAMETERS:
                            params_dict[param['name']] = param['default']
                
                # Create generator source
                from ...player.sources import GeneratorSource
                generator_source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=params_dict,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                success = player.switch_source(generator_source)
            else:
                # It's a video file - look up clip_id from playlist_ids list
                clip_id = None
                if isinstance(player.playlist_ids, list) and next_index < len(player.playlist_ids):
                    clip_id = player.playlist_ids[next_index]
                video_source = VideoSource(next_video_path, player.canvas_width, player.canvas_height, config, clip_id=clip_id)
                success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load next clip"}), 500
        
            # Update playlist index
            player.playlist_index = next_index
            
            # Set current_clip_id from playlist_ids list (or register if missing)
            clip_id = None
            if isinstance(player.playlist_ids, list) and next_index < len(player.playlist_ids):
                clip_id = player.playlist_ids[next_index]
            if not clip_id:
                # Register new clip
                if next_video_path.startswith('generator:'):
                    generator_id = next_video_path.split(':', 1)[1]
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=next_video_path,
                        relative_path=next_video_path,
                        metadata={'type': 'generator', 'generator_id': generator_id}
                    )
                else:
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=next_video_path,
                        relative_path=os.path.relpath(next_video_path, video_dir),
                        metadata={}
                    )
                # Store clip_id in playlist_ids list at correct index
                if not isinstance(player.playlist_ids, list):
                    player.playlist_ids = []
                # Extend list if needed
                while len(player.playlist_ids) <= next_index:
                    player.playlist_ids.append(None)
                player.playlist_ids[next_index] = clip_id
            
            player.current_clip_id = clip_id
            
            # Load clip layers
            player.load_clip_layers(clip_id, clip_registry, video_dir)
            
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = next_video_path if next_video_path.startswith('generator:') else os.path.relpath(next_video_path, video_dir)
            return jsonify({
                "success": True,
                "message": "Next video loaded",
                "video": rel_path,
                "playlist_index": next_index,
                "clip_id": clip_id
            })
        
        except Exception as e:
            logger.error(f"Error loading next video: {e}")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route('/api/player/<player_id>/previous', methods=['POST'])
    def previous_video(player_id):
        """Lädt das vorherige Video aus der Playlist."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"success": False, "error": "No playlist configured"}), 404
        
            # Calculate previous index
            prev_index = player.playlist_index - 1
            if prev_index < 0:
                if player.loop_playlist:
                    prev_index = len(player.playlist) - 1
                else:
                    return jsonify({"success": False, "error": "Start of playlist"}), 400
            
            # Get previous video path
            prev_video_path = player.playlist[prev_index]
        
            was_playing = player.is_playing
        
            # Check if it's a generator or video
            if prev_video_path.startswith('generator:'):
                # It's a generator
                generator_id = prev_video_path.split(':', 1)[1]
                
                # Get default parameters from plugin registry
                from ...plugins.manager import get_plugin_manager
                pm = get_plugin_manager()
                
                params_dict = {}
                if generator_id in pm.registry:
                    plugin_class = pm.registry[generator_id]
                    if hasattr(plugin_class, 'PARAMETERS'):
                        for param in plugin_class.PARAMETERS:
                            params_dict[param['name']] = param['default']
                
                # Create generator source
                from ...player.sources import GeneratorSource
                generator_source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=params_dict,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                success = player.switch_source(generator_source)
            else:
                # It's a video file - look up clip_id from playlist_ids list
                clip_id = None
                if isinstance(player.playlist_ids, list) and prev_index < len(player.playlist_ids):
                    clip_id = player.playlist_ids[prev_index]
                video_source = VideoSource(prev_video_path, player.canvas_width, player.canvas_height, config, clip_id=clip_id)
                success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load previous clip"}), 500
        
            # Update playlist index
            player.playlist_index = prev_index
            
            # Set current_clip_id from playlist_ids list (or register if missing)
            clip_id = None
            if isinstance(player.playlist_ids, list) and prev_index < len(player.playlist_ids):
                clip_id = player.playlist_ids[prev_index]
            if not clip_id:
                # Register new clip
                if prev_video_path.startswith('generator:'):
                    generator_id = prev_video_path.split(':', 1)[1]
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=prev_video_path,
                        relative_path=prev_video_path,
                        metadata={'type': 'generator', 'generator_id': generator_id}
                    )
                else:
                    clip_id = clip_registry.register_clip(
                        player_id=player_id,
                        absolute_path=prev_video_path,
                        relative_path=os.path.relpath(prev_video_path, video_dir),
                        metadata={}
                    )
                # Store clip_id in playlist_ids list at correct index
                if not isinstance(player.playlist_ids, list):
                    player.playlist_ids = []
                # Extend list if needed
                while len(player.playlist_ids) <= prev_index:
                    player.playlist_ids.append(None)
                player.playlist_ids[prev_index] = clip_id
        
            player.current_clip_id = clip_id
            
            # Load clip layers
            player.load_clip_layers(clip_id, clip_registry, video_dir)
        
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = prev_video_path if prev_video_path.startswith('generator:') else os.path.relpath(prev_video_path, video_dir)
            return jsonify({
                "success": True,
                "message": "Previous video loaded",
                "video": rel_path,
                "playlist_index": prev_index,
                "clip_id": clip_id
            })
        
        except Exception as e:
            logger.error(f"Error loading previous video: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/clip/<clip_id>/generator/parameter', methods=['POST'])
    def update_generator_parameter(player_id, clip_id):
        """Update parameter of a running generator clip."""
        try:
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            data = request.get_json()
            
            if not data or 'parameter' not in data or 'value' not in data:
                return jsonify({"success": False, "error": "Missing parameter or value"}), 400
            
            param_name = data['parameter']
            param_value = data['value']
            
            # Get current source
            if not player.source:
                return jsonify({"success": False, "error": "No active source"}), 400
            
            # Check if it's a generator source
            from ...player.sources import GeneratorSource
            if not isinstance(player.source, GeneratorSource):
                return jsonify({"success": False, "error": "Current source is not a generator"}), 400
            
            # Log the update attempt
            logger.info(f"🔧 [{player_id}] Attempting to update generator parameter: {param_name} = {param_value} (generator: {player.source.generator_id})")
            
            # Update parameter
            success = player.source.update_parameter(param_name, param_value)
            
            if success:
                # Store in player's playlist_params for persistence across loops
                generator_id = player.source.generator_id
                if generator_id not in player.playlist_params:
                    player.playlist_params[generator_id] = {}
                player.playlist_params[generator_id][param_name] = param_value
                
                # Update ClipRegistry metadata so parameters persist on clip reload
                if hasattr(player, 'current_clip_id') and player.current_clip_id:
                    clip = clip_registry.get_clip(player.current_clip_id)
                    if clip and clip.get('metadata', {}).get('type') == 'generator':
                        if 'parameters' not in clip['metadata']:
                            clip['metadata']['parameters'] = {}
                        clip['metadata']['parameters'][param_name] = param_value
                        logger.info(f"📝 [{player_id}] Updated ClipRegistry metadata: {param_name} = {param_value}")
                
                logger.info(f"✅ [{player_id}] Generator parameter updated: {param_name} = {param_value}")
                
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save_async(player_manager, clip_registry)
                
                return jsonify({
                    "success": True,
                    "message": f"Parameter {param_name} updated",
                    "parameter": param_name,
                    "value": param_value
                })
            else:
                logger.error(f"❌ [{player_id}] Failed to update generator parameter: {param_name} = {param_value} (generator: {player.source.generator_id}, has plugin: {player.source.plugin_instance is not None})")
                return jsonify({"success": False, "error": f"Failed to update parameter {param_name}"}), 400
            
        except Exception as e:
            logger.error(f"❌ Error updating generator parameter: {str(e)}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/player/<player_id>/playlist/set', methods=['POST'])
    def set_playlist(player_id):
        """
        DEPRECATED: Direct player playlist manipulation.
        Use /api/playlists/update_player instead for multi-playlist-aware updates.
        
        This endpoint modifies the active player directly without playlist awareness.
        """
        logger.warning(f"⚠️ DEPRECATED: /api/player/{player_id}/playlist/set called. Use /api/playlists/update_player instead.")
        
        try:
            data = request.get_json()
            playlist = data.get('playlist', [])
            autoplay = data.get('autoplay', False)
            loop = data.get('loop', False)
            
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Konvertiere relative Pfade zu absoluten und speichere UUIDs separat
            absolute_playlist = []
            playlist_ids = []  # List of UUIDs matching playlist order
            
            from datetime import datetime
            
            for item in playlist:
                if isinstance(item, str):
                    # Legacy: nur Pfad (backwards compatibility)
                    path = item
                    item_id = None
                    item_type = 'video'
                    generator_id = None
                    parameters = {}
                else:
                    # New: vollständiges Objekt mit UUID
                    path = item.get('path', '')
                    item_id = item.get('id')  # Extract UUID
                    item_type = item.get('type', 'video')
                    generator_id = item.get('generator_id')
                    parameters = item.get('parameters', {})
                
                # Don't modify generator paths
                if path.startswith('generator:'):
                    absolute_path = path
                elif not os.path.isabs(path):
                    absolute_path = os.path.join(video_dir, path)
                else:
                    absolute_path = path
                
                absolute_playlist.append(absolute_path)
                
                # Speichere UUID in list (same index as playlist) UND registriere Clip sofort
                if item_id:
                    playlist_ids.append(item_id)
                    debug_api(logger, f"📝 Playlist[{len(playlist_ids)-1}]: {os.path.basename(absolute_path)} → {item_id}")
                    
                    # Registriere Clip in Registry wenn noch nicht vorhanden
                    if item_id not in clip_registry.clips:
                        debug_api(logger, f"📌 Registering clip from playlist: {item_id} → {os.path.basename(absolute_path)}")
                        
                        # Use register_clip() to ensure default effects are applied
                        relative_path = os.path.relpath(absolute_path, video_dir) if not absolute_path.startswith('generator:') else absolute_path
                        metadata = {'type': item_type, 'generator_id': generator_id, 'parameters': parameters} if item_type == 'generator' else {}
                        
                        # Register with a new UUID (default effects will be applied to this clip)
                        registered_id = clip_registry.register_clip(
                            player_id,
                            absolute_path,
                            relative_path,
                            metadata
                        )
                        
                        # Update the clip_id to use the provided one (overwrite generated UUID)
                        if registered_id != item_id:
                            # Move the clip data (with effects) to the target ID
                            clip_registry.clips[item_id] = clip_registry.clips[registered_id]
                            clip_registry.clips[item_id]['clip_id'] = item_id
                            del clip_registry.clips[registered_id]
                            # Also update version tracking if present
                            if registered_id in clip_registry._clip_effects_version:
                                clip_registry._clip_effects_version[item_id] = clip_registry._clip_effects_version[registered_id]
                                del clip_registry._clip_effects_version[registered_id]
                            logger.debug(f"📌 Moved clip data from {registered_id} to {item_id} (with effects intact)")
                    else:
                        debug_api(logger, f"✓ Clip {item_id} already registered, reusing existing clip")
                else:
                    # No item_id provided - check if clip already exists by path
                    existing_id = clip_registry.find_clip_by_path(player_id, absolute_path)
                    if existing_id:
                        logger.debug(f"✓ Found existing clip for path: {existing_id} → {os.path.basename(absolute_path)}")
                        playlist_ids.append(existing_id)
                    else:
                        playlist_ids.append(None)  # Will be generated during autoplay
            
            player.playlist = absolute_playlist
            player.playlist_ids = playlist_ids  # List of UUIDs (same order as playlist)
            player.autoplay = autoplay
            player.loop_playlist = loop
            
            # Store generator parameters for playlist items
            if not hasattr(player, 'playlist_params'):
                player.playlist_params = {}
            for item in playlist:
                if not isinstance(item, str):
                    item_type = item.get('type', 'video')
                    if item_type == 'generator':
                        generator_id = item.get('generator_id')
                        parameters = item.get('parameters', {})
                        if generator_id and parameters:
                            player.playlist_params[generator_id] = parameters.copy()
            
            # Setze Index auf aktuelles Video wenn vorhanden
            current_video_in_playlist = False
            if hasattr(player.source, 'video_path') and player.source.video_path:
                try:
                    player.playlist_index = absolute_playlist.index(player.source.video_path)
                    current_video_in_playlist = True
                    logger.debug(f"📋 [{player_id}] Current video in playlist: Index {player.playlist_index}")
                except ValueError:
                    player.playlist_index = -1
                    logger.debug(f"📋 [{player_id}] Current video not in playlist")
            
            # Wenn aktuelles Video in Playlist ist
            if current_video_in_playlist:
                # Wenn autoplay aktiv: max_loops=1 damit Clip 1x spielt und dann zum nächsten wechselt
                # Sonst: max_loops=0 (Endlosschleife, manuelle Navigation mit Next/Previous)
                player.max_loops = 1 if autoplay else 0
                logger.debug(f"🔁 [{player_id}] Video in Playlist: max_loops={player.max_loops} (autoplay={autoplay})")
                
                # Starte automatisch wenn nicht schon läuft
                if not player.is_playing:
                    player.play()
                    logger.info(f"▶️ [{player_id}] Video automatisch gestartet (in Playlist)")
            else:
                # Aktuelles Video wurde aus Playlist entfernt ODER kein Video geladen
                if hasattr(player.source, 'video_path') and player.source.video_path:
                    logger.info(f"🗑️ [{player_id}] Video aus Playlist entfernt - lade leere Source: {os.path.basename(player.source.video_path)}")
                    player.stop()
                    # Entlade das Video vollständig
                    if hasattr(player, 'source') and player.source:
                        player.source.cleanup()
                    
                    # Lade DummySource (schwarzes Frame)
                    from ...player.sources import DummySource
                    player.source = DummySource(player.canvas_width, player.canvas_height)
                    player.source.initialize()
                    player.playlist_index = -1
                    # Lösche Preview-Frames (leert die Anzeige)
                    player.last_frame = None
                    player.last_video_frame = None
                
                # Wenn Playlist nicht leer ist und autoplay aktiviert: lade und starte erstes Video
                # WICHTIG: Auch wenn Player läuft, ersetze durch erstes Playlist-Video wenn DummySource aktiv
                has_dummy_source = hasattr(player.source, '__class__') and player.source.__class__.__name__ == 'DummySource'
                should_autostart = absolute_playlist and autoplay and (
                    not player.is_playing or has_dummy_source
                )
                
                if should_autostart:
                    player.playlist_index = 0
                    first_item = absolute_playlist[0]
                    logger.info(f"🎬 [{player_id}] Autoplay aktiviert - lade erstes Video: {os.path.basename(first_item)}")
                    logger.debug(f"   playlist_ids mapping: {playlist_ids}")
                    
                    # Lade erstes Video/Generator
                    if first_item.startswith('generator:'):
                        generator_id = first_item.replace('generator:', '')
                        parameters = player.playlist_params.get(generator_id, {})
                        from ...player.sources import GeneratorSource
                        new_source = GeneratorSource(generator_id, parameters, canvas_width=player.canvas_width, canvas_height=player.canvas_height)
                    else:
                        from ...player.sources import VideoSource
                        # Look up clip_id from playlist_ids list (index 0)
                        first_clip_id = playlist_ids[0] if len(playlist_ids) > 0 else None
                        logger.debug(f"   Looking up clip_id for index 0: {first_clip_id}")
                        new_source = VideoSource(first_item, canvas_width=player.canvas_width, canvas_height=player.canvas_height, clip_id=first_clip_id)
                    
                    if new_source.initialize():
                        if hasattr(player, 'source') and player.source:
                            player.source.cleanup()
                        
                        # Hole oder registriere Clip-ID für erstes Item (index 0)
                        first_clip_id = playlist_ids[0] if len(playlist_ids) > 0 else None
                        if not first_clip_id:
                            # Registriere Clip wenn noch keine ID vorhanden
                            if first_item.startswith('generator:'):
                                generator_id = first_item.replace('generator:', '')
                                parameters = player.playlist_params.get(generator_id, {})
                                first_clip_id = clip_registry.register_clip(
                                    player_id=player_id,
                                    absolute_path=first_item,
                                    relative_path=first_item,
                                    metadata={'type': 'generator', 'generator_id': generator_id, 'parameters': parameters}
                                )
                            else:
                                relative_path = os.path.relpath(first_item, video_dir)
                                first_clip_id = clip_registry.register_clip(
                                    player_id=player_id,
                                    absolute_path=first_item,
                                    relative_path=relative_path,
                                    metadata={}
                                )
                            # Update the playlist_ids list with the new/registered clip_id
                            if player.playlist_ids and len(player.playlist_ids) > 0:
                                player.playlist_ids[0] = first_clip_id
                            else:
                                player.playlist_ids = [first_clip_id]
                        
                        # Setze current_clip_id
                        player.current_clip_id = first_clip_id
                        logger.debug(f"🆔 [{player_id}] Set current_clip_id = {first_clip_id}, updated playlist_ids[0]")
                        
                        # Lade Layer für den Clip
                        if not player.load_clip_layers(first_clip_id, clip_registry, video_dir):
                            # Fallback: Ersetze nur Source
                            if player.layers:
                                player.layers[0].source = new_source
                            else:
                                player.source = new_source
                            logger.warning(f"⚠️ [{player_id}] Could not load layers for first clip, using single-source fallback")
                        
                        player.play()
                        logger.info(f"▶️ [{player_id}] Erstes Video automatisch gestartet (clip_id={first_clip_id})")
                    else:
                        logger.error(f"❌ [{player_id}] Fehler beim Laden des ersten Videos")
                
                player.max_loops = 1  # Nur 1x abspielen wenn nicht in Playlist
            
            logger.info(f"✅ [{player_id}] Playlist set: {len(absolute_playlist)} videos, autoplay={autoplay}, loop={loop}")
            
            # Auto-save session state (force=True für kritische Playlist-Änderung)
            session_state = get_session_state()
            if session_state:
                session_state.save_async(player_manager, clip_registry, force=True)
            
            return jsonify({
                "success": True,
                "player_id": player_id,
                "playlist_length": len(absolute_playlist),
                "autoplay": autoplay,
                "loop": loop,
                "playlist_index": player.playlist_index
            })
            
        except Exception as e:
            logger.error(f"Error setting playlist: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"success": False, "error": str(e)}), 500
    
    # ========================================
    # PLAYLIST SAVE/LOAD
    # ========================================
    
    @app.route('/api/playlist/save', methods=['POST'])
    def save_playlist():
        """Speichert beide Playlists zusammen."""
        try:
            import json
            from datetime import datetime
            
            data = request.get_json()
            name = data.get('name', f'playlist_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            video_playlist = data.get('video_playlist', [])
            artnet_playlist = data.get('artnet_playlist', [])
            
            # Create playlists directory if it doesn't exist
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            os.makedirs(playlists_dir, exist_ok=True)
            
            # Get sequencer state
            sequencer_state = None
            if player_manager.sequencer:
                try:
                    sequencer_state = {
                        "mode_active": player_manager.sequencer_mode_active,
                        "audio_file": player_manager.sequencer.timeline.audio_file,
                        "timeline": player_manager.sequencer.timeline.to_dict()
                    }
                except Exception as e:
                    logger.warning(f"Failed to get sequencer state: {e}")
            
            # Save combined playlist as JSON
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            playlist_data = {
                'name': name,
                'created': datetime.now().isoformat(),
                'video_playlist': video_playlist,
                'artnet_playlist': artnet_playlist,
                'sequencer': sequencer_state,  # Include sequencer settings
                'master_playlist': player_manager.get_master_playlist(),  # Include master/slave state
                'total_videos': len(video_playlist) + len(artnet_playlist)
            }
            
            with open(playlist_path, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Playlists saved: {name} (Video: {len(video_playlist)}, Art-Net: {len(artnet_playlist)}, Sequencer: {'Yes' if sequencer_state else 'No'})")
            return jsonify({
                "success": True,
                "status": "success",
                "message": f"Playlists '{name}' saved",
                "path": playlist_path,
                "video_count": len(video_playlist),
                "artnet_count": len(artnet_playlist),
                "has_sequencer": sequencer_state is not None
            })
        
        except Exception as e:
            logger.error(f"Error saving playlists: {e}")
            return jsonify({"success": False, "status": "error", "message": str(e)}), 500
    
    @app.route('/api/playlist/load/<name>', methods=['GET'])
    def load_playlist(name):
        """Lädt eine gespeicherte Playlist."""
        try:
            import json
            
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            
            if not os.path.exists(playlist_path):
                return jsonify({"success": False, "message": f"Playlist '{name}' not found"}), 404
            
            with open(playlist_path, 'r', encoding='utf-8') as f:
                playlist_data = json.load(f)
            # Restore sequencer if included
            sequencer_data = playlist_data.get('sequencer')
            if sequencer_data and player_manager.sequencer:
                try:
                    # Restore audio file
                    audio_file = sequencer_data.get('audio_file')
                    if audio_file and os.path.exists(audio_file):
                        player_manager.sequencer.load_audio(audio_file)
                        
                        # Restore timeline (splits, clip_mapping)
                        timeline_data = sequencer_data.get('timeline', {})
                        if timeline_data:
                            player_manager.sequencer.timeline.from_dict(timeline_data)
                            logger.info(f"🎵 Timeline restored: {len(timeline_data.get('splits', []))} splits, {len(timeline_data.get('clip_mapping', {}))} clip mappings")
                            logger.debug(f"   Clip mappings: {timeline_data.get('clip_mapping', {})}")
                        
                        # Restore sequencer mode
                        mode_active = sequencer_data.get('mode_active', False)
                        player_manager.set_sequencer_mode(mode_active)
                        
                        logger.info(f"🎵 Sequencer restored from playlist: audio={os.path.basename(audio_file)}, mode_active={mode_active}")
                except Exception as e:
                    logger.warning(f"Failed to restore sequencer from playlist: {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Restore master/slave state
            master_playlist = playlist_data.get('master_playlist')
            if master_playlist:
                try:
                    success = player_manager.set_master_playlist(master_playlist)
                    if success:
                        logger.info(f"👑 Master playlist restored from playlist: {master_playlist}")
                except Exception as e:
                    logger.warning(f"Failed to restore master/slave state from playlist: {e}")
            
            logger.info(f"📂 Playlist loaded: {name}")
            return jsonify({
                "success": True,
                "name": name,
                "video_playlist": playlist_data.get('video_playlist', []),
                "artnet_playlist": playlist_data.get('artnet_playlist', []),
                "sequencer": sequencer_data,  # Send sequencer data to frontend
                "artnet_playlist": playlist_data.get('artnet_playlist', []),
                "created": playlist_data.get('created'),
                "total_videos": playlist_data.get('total_videos', 0)
            })
        
        except Exception as e:
            logger.error(f"Error loading playlist: {e}")
            return jsonify({"success": False, "message": str(e)}), 500
    
    @app.route('/api/playlists', methods=['GET'])
    def get_playlists():
        """Gibt Liste aller gespeicherten Playlists zurück."""
        try:
            import json
            
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            
            if not os.path.exists(playlists_dir):
                return jsonify({"status": "success", "playlists": []})
            
            playlists = []
            for filename in os.listdir(playlists_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(playlists_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        playlists.append({
                            'name': data.get('name', filename[:-5]),
                            'filename': filename[:-5],
                            'created': data.get('created'),
                            'video_count': len(data.get('video_playlist', [])),
                            'artnet_count': len(data.get('artnet_playlist', [])),
                            'total': data.get('total_videos', 0)
                        })
                    except Exception as e:
                        logger.error(f"Error reading playlist {filename}: {e}")
                        continue
            
            # Sort by creation date (newest first)
            playlists.sort(key=lambda x: x.get('created', ''), reverse=True)
            
            return jsonify({"status": "success", "playlists": playlists})
        
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/playlist/delete/<name>', methods=['DELETE'])
    def delete_playlist(name):
        """Löscht eine gespeicherte Playlist."""
        try:
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            
            if not os.path.exists(playlist_path):
                return jsonify({"success": False, "message": f"Playlist '{name}' not found"}), 404
            
            os.remove(playlist_path)
            logger.info(f"🗑️ Playlist deleted: {name}")
            
            return jsonify({"success": True, "message": f"Playlist '{name}' deleted"})
        
        except Exception as e:
            logger.error(f"Error deleting playlist: {e}")
            return jsonify({"success": False, "message": str(e)}), 500
    
    # ========================================
    # MASTER/SLAVE SYNCHRONIZATION
    # ========================================
    
    @app.route('/api/player/<player_id>/set_master', methods=['POST'])
    def set_master_playlist(player_id):
        """
        Activates/deactivates Master mode for the VIEWED playlist.
        When enabled, all players in this playlist become master/slave synchronized.
        This setting is per-playlist and saved with the playlist.
        
        Request Body:
            {
                "enabled": true  // false deactivates Master mode
            }
        
        Response:
            {
                "success": true,
                "master_player": "video",  // or "artnet" or null
                "playlist_id": "...",
                "message": "Master player set to video for playlist 'Default'"
            }
        """
        try:
            data = request.get_json()
            enabled = data.get('enabled', True)
            
            # Validate player_id
            if player_id not in player_manager.get_all_player_ids():
                return jsonify({
                    'success': False,
                    'error': f'Invalid player_id: {player_id}'
                }), 400
            
            # Get the VIEWED playlist (master/slave is per-playlist, set on viewed playlist)
            playlist_system = player_manager.playlist_system
            if not playlist_system:
                return jsonify({
                    'success': False,
                    'error': 'Playlist system not initialized'
                }), 500
            
            viewed_playlist = playlist_system.get_viewed_playlist()
            if not viewed_playlist:
                return jsonify({
                    'success': False,
                    'error': 'No viewed playlist'
                }), 400
            
            # Set or clear master_player on the VIEWED playlist
            old_master = viewed_playlist.master_player
            if enabled:
                viewed_playlist.master_player = player_id
            else:
                viewed_playlist.master_player = None
            
            # If the viewed playlist is also the active one, update global master for immediate effect
            # Otherwise, the setting will be applied when this playlist is activated
            active_playlist = playlist_system.get_active_playlist()
            if viewed_playlist.id == active_playlist.id:
                player_manager.master_playlist = viewed_playlist.master_player
                player_manager._update_all_slave_caches()
            
            # Emit WebSocket event
            if player_manager.socketio and old_master != viewed_playlist.master_player:
                try:
                    player_manager.socketio.emit('master_slave_changed', {
                        'master_player': viewed_playlist.master_player,
                        'playlist_id': viewed_playlist.id,
                        'playlist_name': viewed_playlist.name,
                        'timestamp': time.time()
                    }, namespace='/player')
                    logger.info(f"📡 WebSocket: master_slave_changed emitted (master={viewed_playlist.master_player}, playlist={viewed_playlist.name})")
                except Exception as e:
                    logger.error(f"❌ Error emitting master_slave_changed WebSocket event: {e}")
            
            # Save to session state
            from ...session.state import get_session_state
            from ...player.clips.registry import get_clip_registry
            session_state = get_session_state()
            clip_registry = get_clip_registry()
            session_state.save_without_capture(player_manager, clip_registry)
            
            logger.info(f"👑 Set master_player={viewed_playlist.master_player} for playlist '{viewed_playlist.name}' (id={viewed_playlist.id})")
            
            message = f"Master player set to {viewed_playlist.master_player} for playlist '{viewed_playlist.name}'" if viewed_playlist.master_player else f"Master mode disabled for playlist '{viewed_playlist.name}'"
            
            return jsonify({
                'success': True,
                'master_player': viewed_playlist.master_player,
                'playlist_id': viewed_playlist.id,
                'playlist_name': viewed_playlist.name,
                'message': message
            })
            
        except Exception as e:
            logger.error(f"Error setting master playlist: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/player/sync_status', methods=['GET'])
    def get_sync_status():
        """
        Gets current Master/Slave synchronization status.
        
        Response:
            {
                "success": true,
                "master_playlist": "video",
                "slaves": ["artnet"],
                "master_clip_index": 4,
                "slave_clip_indices": {
                    "artnet": 4
                }
            }
        """
        try:
            master_playlist = player_manager.get_master_playlist()
            slaves = [pid for pid in player_manager.get_all_player_ids() 
                     if pid != master_playlist]
            
            master_clip_index = None
            slave_clip_indices = {}
            
            # Get master clip index
            if master_playlist:
                master_player = player_manager.get_player(master_playlist)
                if master_player:
                    master_clip_index = master_player.get_current_clip_index()
            
            # Get slave clip indices
            for slave_id in slaves:
                slave_player = player_manager.get_player(slave_id)
                if slave_player:
                    slave_clip_indices[slave_id] = slave_player.get_current_clip_index()
            
            return jsonify({
                'success': True,
                'master_playlist': master_playlist,
                'slaves': slaves,
                'master_clip_index': master_clip_index,
                'slave_clip_indices': slave_clip_indices
            })
            
        except Exception as e:
            logger.error(f"Error getting sync status: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # VIDEO PLAYER SETTINGS
    # ========================================
    
    @app.route('/api/player/video/settings', methods=['GET'])
    def get_video_player_settings():
        """Get video player resolution and autosize settings"""
        try:
            session_state = get_session_state()
            settings = session_state._state.get('video_player_settings', {}) if session_state else {}
            
            # Apply defaults if not set
            if not settings:
                settings = {
                    'preset': '1080p',
                    'custom_width': 1920,
                    'custom_height': 1080,
                    'autosize': 'off'
                }
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            logger.error(f"Error getting video player settings: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/player/video/settings', methods=['POST'])
    def save_video_player_settings():
        """Save video player resolution and autosize settings"""
        try:
            data = request.get_json()
            
            settings = {
                'preset': data.get('preset', '1080p'),
                'autosize': data.get('autosize', 'off')
            }
            
            if data.get('preset') == 'custom':
                settings['custom_width'] = data.get('custom_width', 1920)
                settings['custom_height'] = data.get('custom_height', 1080)
            
            # Save to session state using proper API
            session_state = get_session_state()
            if session_state:
                session_state.set_video_player_settings(settings)
            
            # Apply resolution change immediately to video player
            video_player = player_manager.get_player('video')
            if video_player:
                # Calculate new resolution
                if settings.get('preset') == 'custom':
                    new_width = settings.get('custom_width', 1920)
                    new_height = settings.get('custom_height', 1080)
                else:
                    preset_resolutions = {
                        '720p': (1280, 720),
                        '1080p': (1920, 1080),
                        '1440p': (2560, 1440),
                        '2160p': (3840, 2160)
                    }
                    new_width, new_height = preset_resolutions.get(settings.get('preset', '1080p'), (1920, 1080))
                
                # Update player resolution with autosize mode
                video_player.update_resolution(new_width, new_height, settings.get('autosize', 'off'))
            
            logger.info(f"Video player settings saved and applied: {settings}")
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            logger.error(f"Error saving video player settings: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # ART-NET PLAYER SETTINGS
    # ========================================
    
    @app.route('/api/player/artnet/settings', methods=['GET'])
    def get_artnet_player_settings():
        """Get art-net player resolution and autosize settings"""
        try:
            session_state = get_session_state()
            settings = session_state._state.get('artnet_player_settings', {}) if session_state else {}
            
            # Apply defaults if not set
            if not settings:
                settings = {
                    'preset': '1080p',
                    'custom_width': 1920,
                    'custom_height': 1080,
                    'autosize': 'off'
                }
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            logger.error(f"Error getting art-net player settings: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/player/artnet/settings', methods=['POST'])
    def save_artnet_player_settings():
        """Save art-net player resolution and autosize settings"""
        try:
            data = request.get_json()
            
            settings = {
                'preset': data.get('preset', '1080p'),
                'autosize': data.get('autosize', 'off')
            }
            
            if data.get('preset') == 'custom':
                settings['custom_width'] = data.get('custom_width', 1920)
                settings['custom_height'] = data.get('custom_height', 1080)
            
            # Save to session state using proper API
            session_state = get_session_state()
            if session_state:
                session_state.set_artnet_player_settings(settings)
            
            # Apply resolution change immediately to artnet player
            artnet_player = player_manager.get_player('artnet')
            if artnet_player:
                # Calculate new resolution
                if settings.get('preset') == 'custom':
                    new_width = settings.get('custom_width', 1920)
                    new_height = settings.get('custom_height', 1080)
                else:
                    preset_resolutions = {
                        '720p': (1280, 720),
                        '1080p': (1920, 1080),
                        '1440p': (2560, 1440),
                        '2160p': (3840, 2160)
                    }
                    new_width, new_height = preset_resolutions.get(settings.get('preset', '1080p'), (1920, 1080))
                
                # Update player resolution with autosize mode
                artnet_player.update_resolution(new_width, new_height, settings.get('autosize', 'off'))
            
            logger.info(f"Art-Net player settings saved and applied: {settings}")
            
            return jsonify({
                'success': True,
                'settings': settings
            })
            
        except Exception as e:
            logger.error(f"Error saving art-net player settings: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    # ========================================
    # ART-NET RESOLUTION SETTINGS
    # ========================================
    
    @app.route('/api/artnet/resolution', methods=['GET'])
    def get_artnet_resolution():
        """Get current Art-Net canvas resolution from points file"""
        try:
            from modules.content.points import PointsLoader
            import os
            
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            points_json_path = os.path.join(base_path, 'data', 'punkte_export.json')
            
            points_data = PointsLoader.load_points(points_json_path, validate_bounds=False)
            
            return jsonify({
                'success': True,
                'resolution': {
                    'width': points_data['canvas_width'],
                    'height': points_data['canvas_height']
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting Art-Net resolution: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route('/api/artnet/resolution', methods=['POST'])
    def update_artnet_resolution():
        """Update Art-Net canvas resolution in points file"""
        try:
            import os
            import json
            
            data = request.get_json()
            preset = data.get('preset')
            
            # Calculate new resolution
            if preset == 'custom':
                new_width = int(data.get('custom_width', 1024))
                new_height = int(data.get('custom_height', 768))
            else:
                preset_resolutions = {
                    '720p': (1280, 720),
                    '1080p': (1920, 1080),
                    '1440p': (2560, 1440),
                    '2160p': (3840, 2160)
                }
                new_width, new_height = preset_resolutions.get(preset, (1024, 768))
            
            # Validate resolution
            if new_width < 640 or new_width > 7680 or new_height < 480 or new_height > 4320:
                return jsonify({
                    'success': False,
                    'error': 'Resolution out of valid range (640x480 to 7680x4320)'
                }), 400
            
            # Load points file
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            points_json_path = os.path.join(base_path, 'data', 'punkte_export.json')
            
            with open(points_json_path, 'r', encoding='utf-8') as f:
                points_data = json.load(f)
            
            # Update canvas dimensions
            old_width = points_data['canvas']['width']
            old_height = points_data['canvas']['height']
            
            points_data['canvas']['width'] = new_width
            points_data['canvas']['height'] = new_height
            
            # Create backup before saving
            backup_path = points_json_path + '.backup'
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(points_data, f, indent=2)
            
            # Save updated points file
            with open(points_json_path, 'w', encoding='utf-8') as f:
                json.dump(points_data, f, indent=2)
            
            logger.info(f"Art-Net canvas resolution updated from {old_width}x{old_height} to {new_width}x{new_height}")
            logger.info(f"Backup created at {backup_path}")
            
            return jsonify({
                'success': True,
                'resolution': {
                    'width': new_width,
                    'height': new_height
                },
                'message': f'Resolution updated to {new_width}x{new_height}. Restart required to apply changes.',
                'backup_created': backup_path
            })
            
        except Exception as e:
            logger.error(f"Error updating Art-Net resolution: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
