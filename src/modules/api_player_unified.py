"""
Unified Player API - Einheitliche REST-API für alle Player.

Ersetzt separate Video- und Art-Net-APIs durch ein einheitliches Interface:
- /api/player/<player_id>/...
- Clip-basiertes Management mit UUIDs
- Konsistente Fehlerbehandlung
"""

import os
from flask import request, jsonify
from .logger import get_logger
from .clip_registry import get_clip_registry
from .frame_source import VideoSource
from .session_state import get_session_state

logger = get_logger(__name__)


def register_unified_routes(app, player_manager, config):
    """
    Registriert vereinheitlichte Player-API-Routes.
    
    Args:
        app: Flask-App-Instanz
        player_manager: PlayerManager-Instanz
        config: Konfiguration
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
                from .frame_source import GeneratorSource
                
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
                    
                    # Always update playlist_ids mapping
                    if hasattr(player, 'playlist_ids'):
                        player.playlist_ids[gen_path] = clip_id
                    else:
                        player.playlist_ids = {gen_path: clip_id}
                    
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
                    # Store in playlist_ids for future loops
                    if hasattr(player, 'playlist_ids'):
                        player.playlist_ids[gen_path] = clip_id
                    else:
                        player.playlist_ids = {gen_path: clip_id}
                    
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
                
                # Start playback if was playing OR autoplay is enabled
                if was_playing or player.autoplay:
                    player.play()
                    logger.info(f"▶️ [{player_id}] Started playback (was_playing={was_playing}, autoplay={player.autoplay})")
                
                # Auto-save session state (force=True für kritische Clip-Änderung)
                session_state = get_session_state()
                if session_state:
                    session_state.save(player_manager, clip_registry, force=True)
                
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
                    
                    # Always update playlist_ids mapping
                    if hasattr(player, 'playlist_ids'):
                        player.playlist_ids[absolute_path] = clip_id
                    else:
                        player.playlist_ids = {absolute_path: clip_id}
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
                player.playlist_ids[absolute_path] = clip_id  # Store UUID for future loops
                logger.info(f"✅ [{player_id}] Loaded clip: {os.path.basename(absolute_path)} (clip_id={clip_id})")
                logger.debug(f"   Player state: current_clip_id={player.current_clip_id}, source type={type(video_source).__name__}")
                
                # Load clip layers from registry
                player.load_clip_layers(clip_id, clip_registry, video_dir)
                
                # Update playlist index if applicable
                if hasattr(player, 'playlist') and player.playlist:
                    try:
                        player.playlist_index = player.playlist.index(absolute_path)
                    except ValueError:
                        player.playlist_index = -1
                
                # Start playback if was playing OR autoplay is enabled
                if was_playing or player.autoplay:
                    player.play()
                    logger.info(f"▶️ [{player_id}] Started playback (was_playing={was_playing}, autoplay={player.autoplay})")
                
                # Auto-save session state (force=True für kritische Clip-Änderung)
                session_state = get_session_state()
                if session_state:
                    session_state.save(player_manager, clip_registry, force=True)
                
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
        """Gibt alle Effekte eines Clips zurück."""
        try:
            effects = clip_registry.get_clip_effects(clip_id)
            
            # Filter out non-serializable data (instances)
            serializable_effects = []
            for effect in effects:
                effect_copy = effect.copy()
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
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
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
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
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
            
            if not param_name:
                return jsonify({"success": False, "error": "Missing parameter name"}), 400
            
            effects = clip_registry.get_clip_effects(clip_id)
            
            if index < 0 or index >= len(effects):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            effect = effects[index]
            effect['parameters'][param_name] = param_value
            
            logger.debug(f"🔧 Clip effect parameter updated: {clip_id}[{index}].{param_name} = {param_value}")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Error updating clip effect parameter: {e}")
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
            
            logger.info(f"🗑️ All effects cleared from clip {clip_id}")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
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
            
            # Use appropriate chain type
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.add_effect_to_chain(plugin_id, config, chain_type=chain_type)
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save(player_manager, clip_registry)
                
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
            
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.remove_effect_from_chain(index, chain_type=chain_type)
            
            if success:
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save(player_manager, clip_registry)
                
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
            
            chain_type = 'artnet' if player_id == 'artnet' else 'video'
            success, message = player.clear_effects_chain(chain_type=chain_type)
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
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
            
            if param_name is None or value is None:
                return jsonify({"success": False, "error": "name and value required"}), 400
            
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Get appropriate chain
            chain = player.artnet_effect_chain if player_id == 'artnet' else player.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return jsonify({"success": False, "error": "Invalid index"}), 400
            
            effect = chain[index]
            effect['instance'].update_parameter(param_name, value)
            effect['config'][param_name] = value
            
            logger.info(f"✅ Parameter '{param_name}' von Effect {index} auf {value} gesetzt ({player_id})")
            
            # Auto-save session state
            session_state = get_session_state()
            if session_state:
                session_state.save(player_manager, clip_registry)
            
            return jsonify({"success": True, "player_id": player_id, "index": index, "parameter": param_name, "value": value})
            
        except Exception as e:
            logger.error(f"Error updating player effect parameter: {e}")
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
            from .frame_source import DummySource
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
                for path in player.playlist:
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
                    
                    # Add UUID if available in player.playlist_ids
                    if hasattr(player, 'playlist_ids') and path in player.playlist_ids:
                        playlist_item['id'] = player.playlist_ids[path]
                    
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
                "autoplay": getattr(player, 'autoplay', False),
                "loop": getattr(player, 'loop_playlist', False),
                "max_loops": getattr(player, 'max_loops', 1)
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
                from .plugin_manager import get_plugin_manager
                pm = get_plugin_manager()
                
                params_dict = {}
                if generator_id in pm.registry:
                    plugin_class = pm.registry[generator_id]
                    if hasattr(plugin_class, 'PARAMETERS'):
                        for param in plugin_class.PARAMETERS:
                            params_dict[param['name']] = param['default']
                
                # Create generator source
                from .frame_source import GeneratorSource
                generator_source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=params_dict,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                success = player.switch_source(generator_source)
            else:
                # It's a video file - look up clip_id for trim/reverse support
                clip_id = player.playlist_ids.get(next_video_path)
                video_source = VideoSource(next_video_path, player.canvas_width, player.canvas_height, config, clip_id=clip_id)
                success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load next clip"}), 500
        
            # Update playlist index
            player.playlist_index = next_index
            
            # Set current_clip_id from playlist_ids (or register if missing)
            clip_id = player.playlist_ids.get(next_video_path)
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
                player.playlist_ids[next_video_path] = clip_id
            
            player.current_clip_id = clip_id
            
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
                from .plugin_manager import get_plugin_manager
                pm = get_plugin_manager()
                
                params_dict = {}
                if generator_id in pm.registry:
                    plugin_class = pm.registry[generator_id]
                    if hasattr(plugin_class, 'PARAMETERS'):
                        for param in plugin_class.PARAMETERS:
                            params_dict[param['name']] = param['default']
                
                # Create generator source
                from .frame_source import GeneratorSource
                generator_source = GeneratorSource(
                    generator_id=generator_id,
                    parameters=params_dict,
                    canvas_width=player.canvas_width,
                    canvas_height=player.canvas_height,
                    config=config
                )
                success = player.switch_source(generator_source)
            else:
                # It's a video file - look up clip_id for trim/reverse support
                clip_id = player.playlist_ids.get(prev_video_path)
                video_source = VideoSource(prev_video_path, player.canvas_width, player.canvas_height, config, clip_id=clip_id)
                success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load previous clip"}), 500
        
            # Update playlist index
            player.playlist_index = prev_index
            
            # Set current_clip_id from playlist_ids (or register if missing)
            clip_id = player.playlist_ids.get(prev_video_path)
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
                player.playlist_ids[prev_video_path] = clip_id
            
            player.current_clip_id = clip_id
            
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
            from .frame_source import GeneratorSource
            if not isinstance(player.source, GeneratorSource):
                return jsonify({"success": False, "error": "Current source is not a generator"}), 400
            
            # Log the update attempt
            logger.info(f"🔧 [{player_id}] Attempting to update generator parameter: {param_name} = {param_value} (generator: {player.source.generator_id})")
            
            # Update parameter
            success = player.source.update_parameter(param_name, param_value)
            
            if success:
                # Also store in player's playlist_params for persistence across loops
                generator_id = player.source.generator_id
                if generator_id not in player.playlist_params:
                    player.playlist_params[generator_id] = {}
                player.playlist_params[generator_id][param_name] = param_value
                
                logger.info(f"✅ [{player_id}] Generator parameter updated and stored: {param_name} = {param_value}")
                
                # Auto-save session state
                session_state = get_session_state()
                if session_state:
                    session_state.save(player_manager, clip_registry)
                
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
        """Setzt die Playlist für einen Player."""
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
            playlist_ids = {}  # Map: path -> uuid
            
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
                
                # Speichere UUID-Mapping UND registriere Clip sofort
                if item_id:
                    playlist_ids[absolute_path] = item_id
                    logger.debug(f"📝 Playlist mapping: {absolute_path} → {item_id}")
                    
                    # Registriere Clip in Registry wenn noch nicht vorhanden
                    if item_id not in clip_registry.clips:
                        logger.debug(f"📌 Registering clip from playlist: {item_id} → {os.path.basename(absolute_path)}")
                        
                        # Use register_clip() to ensure default effects are applied
                        relative_path = os.path.relpath(absolute_path, video_dir) if not absolute_path.startswith('generator:') else absolute_path
                        metadata = {'type': item_type, 'generator_id': generator_id, 'parameters': parameters} if item_type == 'generator' else {}
                        
                        # Register with the provided UUID instead of generating new one
                        registered_id = clip_registry.register_clip(
                            player_id,
                            absolute_path,
                            relative_path,
                            metadata
                        )
                        
                        # Update the clip_id to use the provided one (overwrite generated UUID)
                        if registered_id != item_id:
                            clip_registry.clips[item_id] = clip_registry.clips[registered_id]
                            clip_registry.clips[item_id]['clip_id'] = item_id
                            del clip_registry.clips[registered_id]
                    else:
                        logger.debug(f"✓ Clip {item_id} already registered, reusing existing clip")
                else:
                    # No item_id provided - check if clip already exists by path
                    existing_id = clip_registry.find_clip_by_path(player_id, absolute_path)
                    if existing_id:
                        logger.debug(f"✓ Found existing clip for path: {existing_id} → {os.path.basename(absolute_path)}")
                        playlist_ids[absolute_path] = existing_id
                    # If no existing clip, it will be registered during autoplay
            
            player.playlist = absolute_playlist
            player.playlist_ids = playlist_ids  # Neue Property für UUID-Mapping
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
            
            # Wenn aktuelles Video in Playlist ist: setze Endlosschleife
            if current_video_in_playlist:
                player.max_loops = 0  # 0 = Endlosschleife
                logger.debug(f"🔁 [{player_id}] Video in Endlosschleife gesetzt (max_loops=0)")
                
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
                    from .frame_source import DummySource
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
                        from .frame_source import GeneratorSource
                        new_source = GeneratorSource(generator_id, parameters, canvas_width=player.canvas_width, canvas_height=player.canvas_height)
                    else:
                        from .frame_source import VideoSource
                        # Look up clip_id for trim/reverse support
                        first_clip_id = playlist_ids.get(first_item)
                        logger.debug(f"   Looking up clip_id for '{first_item}': {first_clip_id}")
                        new_source = VideoSource(first_item, canvas_width=player.canvas_width, canvas_height=player.canvas_height, clip_id=first_clip_id)
                    
                    if new_source.initialize():
                        if hasattr(player, 'source') and player.source:
                            player.source.cleanup()
                        
                        # Hole oder registriere Clip-ID für erstes Item
                        first_clip_id = playlist_ids.get(first_item)
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
                            playlist_ids[first_item] = first_clip_id
                        
                        # Setze current_clip_id
                        player.current_clip_id = first_clip_id
                        
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
                session_state.save(player_manager, clip_registry, force=True)
            
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
            
            # Save combined playlist as JSON
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            playlist_data = {
                'name': name,
                'created': datetime.now().isoformat(),
                'video_playlist': video_playlist,
                'artnet_playlist': artnet_playlist,
                'total_videos': len(video_playlist) + len(artnet_playlist)
            }
            
            with open(playlist_path, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Playlists saved: {name} (Video: {len(video_playlist)}, Art-Net: {len(artnet_playlist)})")
            return jsonify({
                "success": True,
                "status": "success",
                "message": f"Playlists '{name}' saved",
                "path": playlist_path,
                "video_count": len(video_playlist),
                "artnet_count": len(artnet_playlist)
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
            
            logger.info(f"📂 Playlist loaded: {name}")
            return jsonify({
                "success": True,
                "name": name,
                "video_playlist": playlist_data.get('video_playlist', []),
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
    
    logger.info("✅ Unified Player API routes registered")
