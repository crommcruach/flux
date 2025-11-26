"""
API Art-Net Videos - Video Management Endpoints für Art-Net Player

Alle Video-bezogenen Endpoints für den Art-Net Player.
Separiert vom Video Player (api_videos.py).
"""
from flask import jsonify, request
import os
from .logger import get_logger
from .frame_source import VideoSource

logger = get_logger(__name__)


def register_artnet_video_routes(app, player_manager, video_dir, config):
    """Registriert Video-Management Endpunkte für Art-Net Player."""
    logger.info("🔧 Registering Art-Net Video routes...")
    
    @app.route('/api/artnet/video/load', methods=['POST'])
    def load_artnet_video():
        """Lädt ein Video in den Art-Net Player."""
        data = request.get_json()
        video_path = data.get('path')
        
        if not video_path:
            return jsonify({"status": "error", "message": "Kein Pfad angegeben"}), 400
        
        # Erstelle absoluten Pfad falls relativ
        if not os.path.isabs(video_path):
            video_path = os.path.join(video_dir, video_path)
        
        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": f"Video nicht gefunden: {video_path}"}), 404
        
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"status": "error", "message": "No Art-Net player available"}), 500  # Should never happen - Art-Net player always exists
            
            was_playing = player.is_playing
            
            # Erstelle neue VideoSource
            video_source = VideoSource(
                video_path,
                player.canvas_width,
                player.canvas_height,
                config
            )
            
            # Wechsle Source
            success = player.switch_source(video_source)
            
            if not success:
                return jsonify({"status": "error", "message": "Fehler beim Laden des Videos"}), 500
            
            # Try to find index in playlist
            if hasattr(player, 'playlist') and player.playlist:
                try:
                    player.playlist_index = player.playlist.index(video_path)
                    logger.debug(f"📋 Art-Net Video in Playlist gefunden: Index {player.playlist_index}/{len(player.playlist)}")
                except ValueError:
                    player.playlist_index = -1
                    logger.warning(f"⚠️ Art-Net Video nicht in Playlist: {video_path}")
            
            # Play if was playing before
            if was_playing:
                player.play()
            
            rel_path = os.path.relpath(video_path, video_dir)
            
            return jsonify({
                "status": "success",
                "message": f"Art-Net video geladen: {os.path.basename(video_path)}",
                "video": rel_path,
                "was_playing": was_playing
            })
            
        except Exception as e:
            logger.error(f"Error loading Art-Net video: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/artnet/video/status', methods=['GET'])
    def artnet_video_status():
        """Gibt den Status des Art-Net Players zurück."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"status": "error", "message": "No Art-Net player available"}), 500  # Should never happen - Art-Net player always exists
            
            current_video = None
            if hasattr(player, 'source') and player.source and hasattr(player.source, 'video_path'):
                current_video = os.path.relpath(player.source.video_path, video_dir)
            
            # Get playlist as relative paths
            playlist = []
            if hasattr(player, 'playlist'):
                for path in player.playlist:
                    try:
                        rel_path = os.path.relpath(path, video_dir)
                        playlist.append(rel_path)
                    except:
                        playlist.append(path)
            
            return jsonify({
                "status": "success",
                "is_playing": player.is_playing,
                "is_paused": player.is_paused,
                "current_frame": player.current_frame,
                "total_frames": getattr(player.source, 'total_frames', 0) if player.source else 0,
                "current_video": current_video,
                "playlist": playlist,
                "playlist_index": getattr(player, 'playlist_index', -1),
                "autoplay": getattr(player, 'autoplay', False),
                "loop": getattr(player, 'loop_playlist', False)
            })
        except Exception as e:
            logger.error(f"Error getting Art-Net video status: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/artnet/video/next', methods=['POST'])
    def next_artnet_video():
        """Lädt das nächste Video aus der Art-Net Playlist."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"status": "error", "message": "No Art-Net player available"}), 500  # Should never happen - Art-Net player always exists
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"status": "error", "message": "No playlist configured"}), 400
        
            # Calculate next index
            next_index = player.playlist_index + 1
            if next_index >= len(player.playlist):
                if player.loop_playlist:
                    next_index = 0
                else:
                    return jsonify({"status": "error", "message": "End of playlist"}), 400
            
            # Get next video path
            next_video_path = player.playlist[next_index]
            
            was_playing = player.is_playing
        
            video_source = VideoSource(next_video_path, player.canvas_width, player.canvas_height, config)
            success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"status": "error", "message": "Failed to load video"}), 500
        
            # Update playlist index
            player.playlist_index = next_index
            
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = os.path.relpath(next_video_path, video_dir)
            return jsonify({
                "status": "success",
                "message": "Next Art-Net video loaded",
                "video": rel_path
            })
        
        except Exception as e:
            logger.error(f"Error loading next Art-Net video: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/artnet/video/previous', methods=['POST'])
    def previous_artnet_video():
        """Lädt das vorherige Video aus der Art-Net Playlist."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"status": "error", "message": "No Art-Net player available"}), 500  # Should never happen - Art-Net player always exists
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"status": "error", "message": "No playlist configured"}), 400
        
            # Calculate previous index
            prev_index = player.playlist_index - 1
            if prev_index < 0:
                if player.loop_playlist:
                    prev_index = len(player.playlist) - 1
                else:
                    return jsonify({"status": "error", "message": "Start of playlist"}), 400
            
            # Get previous video path
            prev_video_path = player.playlist[prev_index]
        
            was_playing = player.is_playing
        
            video_source = VideoSource(prev_video_path, player.canvas_width, player.canvas_height, config)
            success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"status": "error", "message": "Failed to load video"}), 500
        
            # Update playlist index
            player.playlist_index = prev_index
            
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = os.path.relpath(prev_video_path, video_dir)
            return jsonify({
                "status": "success",
                "message": "Previous Art-Net video loaded",
                "video": rel_path
            })
        
        except Exception as e:
            logger.error(f"Error loading previous Art-Net video: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/artnet/video/playlist/set', methods=['POST'])
    def set_artnet_playlist():
        """Setzt die Playlist für den Art-Net Player."""
        try:
            data = request.get_json()
            playlist = data.get('playlist', [])
            autoplay = data.get('autoplay', False)
            loop = data.get('loop', False)
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"status": "error", "message": "No Art-Net player available"}), 500  # Should never happen - Art-Net player always exists
            
            # Convert relative paths to absolute
            absolute_playlist = []
            for rel_path in playlist:
                if not os.path.isabs(rel_path):
                    abs_path = os.path.join(video_dir, rel_path)
                else:
                    abs_path = rel_path
                absolute_playlist.append(abs_path)
            
            # Set playlist in player
            player.playlist = absolute_playlist
            player.autoplay = autoplay
            player.loop_playlist = loop
            player.max_loops = 1  # Important: Stop after one playthrough for autoplay to work
            
            # Try to find current video in playlist
            if hasattr(player, 'source') and player.source and hasattr(player.source, 'video_path'):
                current_path = player.source.video_path
                try:
                    player.playlist_index = absolute_playlist.index(current_path)
                    logger.debug(f"📋 Art-Net Current video in playlist: Index {player.playlist_index}")
                except ValueError:
                    player.playlist_index = -1
                    logger.debug(f"📋 Art-Net Current video not in playlist")
            else:
                player.playlist_index = -1
                logger.debug(f"📋 Art-Net No current video loaded")
            
            logger.info(f"Art-Net playlist set: {len(absolute_playlist)} videos, autoplay={autoplay}, loop={loop}, playlist_index={player.playlist_index}")
            
            return jsonify({
                "status": "success",
                "message": "Art-Net playlist configured",
                "playlist_length": len(absolute_playlist),
                "autoplay": autoplay,
                "loop": loop
            })
            
        except Exception as e:
            logger.error(f"Error setting Art-Net playlist: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # ========================================
    # CLIP-LEVEL EFFECTS
    # ========================================
    
    @app.route('/api/artnet/clip/effects/add_v2', methods=['POST'])
    def add_clip_effect_artnet_v2():
        """Fügt einen Effekt zu einem Art-Net-Clip hinzu (v2 workaround for Flask caching)."""
        try:
            data = request.get_json()
            plugin_id = data.get('plugin_id')
            clip_path = data.get('clip_path')
            
            if not plugin_id:
                return jsonify({"success": False, "error": "Missing plugin_id"}), 400
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "Art-Net player not found"}), 500  # Should never happen - Art-Net player always exists
            
            # Get plugin class from registry (not instance!)
            pm = player.plugin_manager
            if plugin_id not in pm.registry:
                return jsonify({"success": False, "error": f"Plugin '{plugin_id}' not found"}), 404
            
            plugin_class = pm.registry[plugin_id]
            
            # Merge METADATA and PARAMETERS
            metadata = plugin_class.METADATA.copy()
            if hasattr(plugin_class, 'PARAMETERS'):
                # PARAMETERS are already dicts, just need to convert ParameterType enum to string
                parameters = []
                for param in plugin_class.PARAMETERS:
                    # Check if param is dict or object
                    if isinstance(param, dict):
                        param_dict = param.copy()
                        # Convert ParameterType enum to string if present
                        if 'type' in param_dict and hasattr(param_dict['type'], 'value'):
                            param_dict['type'] = param_dict['type'].value
                    else:
                        # Handle Parameter objects (fallback)
                        param_dict = {
                            'name': param.name,
                            'type': param.type.value if hasattr(param.type, 'value') else str(param.type),
                            'default': param.default,
                            'min': getattr(param, 'min', None),
                            'max': getattr(param, 'max', None),
                            'description': getattr(param, 'description', '')
                        }
                    parameters.append(param_dict)
                metadata['parameters'] = parameters
            
            # Convert plugin type enum to string
            if 'type' in metadata and hasattr(metadata['type'], 'value'):
                metadata['type'] = metadata['type'].value
            
            # Initialize effect with default parameters
            effect_data = {
                'plugin_id': plugin_id,
                'metadata': metadata,
                'parameters': {}
            }
            
            # Set default parameter values
            if 'parameters' in metadata:
                for param in metadata['parameters']:
                    effect_data['parameters'][param['name']] = param['default']
            
            # Convert clip_path to absolute path
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            logger.info(f"➕ Adding Art-Net clip effect '{plugin_id}' to: {clip_path}")
            logger.info(f"   Relative path: {clip_path}")
            logger.info(f"   Absolute path: {abs_clip_path}")
            logger.info(f"   Current source: {player.source.video_path if hasattr(player.source, 'video_path') else 'N/A'}")
            
            # Initialize clip_effects dict if not exists
            if not hasattr(player, 'clip_effects'):
                player.clip_effects = {}
            
            # Add effect to clip
            if abs_clip_path not in player.clip_effects:
                player.clip_effects[abs_clip_path] = []
            
            player.clip_effects[abs_clip_path].append(effect_data)
            
            logger.info(f"✅ Art-Net clip effect '{plugin_id}' added successfully")
            logger.info(f"   Total effects for this clip: {len(player.clip_effects[abs_clip_path])}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error adding Art-Net clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/clip/effects', methods=['POST'])
    def get_clip_effects_artnet():
        """Gibt die Effekte eines Art-Net-Clips zurück."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "Art-Net player not found"}), 500  # Should never happen - Art-Net player always exists
            
            # Convert to absolute path
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            # Get effects for this clip
            clip_effects = []
            if hasattr(player, 'clip_effects') and abs_clip_path in player.clip_effects:
                clip_effects = player.clip_effects[abs_clip_path]
            
            # Filter out plugin instances (not JSON serializable)
            serializable_effects = []
            for effect in clip_effects:
                effect_copy = effect.copy()
                if 'instance' in effect_copy:
                    del effect_copy['instance']
                serializable_effects.append(effect_copy)
            
            return jsonify({"success": True, "effects": serializable_effects})
        
        except Exception as e:
            logger.error(f"Error getting Art-Net clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/clip/effects/<int:index>', methods=['DELETE'])
    def remove_clip_effect_artnet(index):
        """Entfernt einen Effekt von einem Art-Net-Clip."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "Art-Net player not found"}), 500  # Should never happen - Art-Net player always exists
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            if not hasattr(player, 'clip_effects') or abs_clip_path not in player.clip_effects:
                return jsonify({"success": False, "error": "No effects for this clip"}), 400
            
            if index < 0 or index >= len(player.clip_effects[abs_clip_path]):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            removed = player.clip_effects[abs_clip_path].pop(index)
            
            logger.info(f"Removed Art-Net clip effect at index {index} from clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error removing Art-Net clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/clip/effects/clear', methods=['POST'])
    def clear_clip_effects_artnet():
        """Löscht alle Effekte eines Art-Net-Clips."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "Art-Net player not found"}), 500  # Should never happen - Art-Net player always exists
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            if hasattr(player, 'clip_effects') and abs_clip_path in player.clip_effects:
                player.clip_effects[abs_clip_path] = []
            
            logger.info(f"Cleared all Art-Net clip effects from clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error clearing Art-Net clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/clip/effects/<int:index>/parameter', methods=['PUT'])
    def update_clip_effect_parameter_artnet(index):
        """Aktualisiert einen Parameter eines Art-Net Clip-Effekts."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            param_name = data.get('name')
            param_value = data.get('value')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            if not param_name:
                return jsonify({"success": False, "error": "Missing parameter name"}), 400
            
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "Art-Net player not found"}), 500  # Should never happen - Art-Net player always exists
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            logger.info(f"🔧 Updating Art-Net clip effect #{index}: {param_name}={param_value}")
            logger.info(f"   clip_path: {clip_path} → abs: {abs_clip_path}")
            if hasattr(player, 'clip_effects'):
                logger.info(f"   Available clips: {list(player.clip_effects.keys())}")
            
            if not hasattr(player, 'clip_effects') or abs_clip_path not in player.clip_effects:
                return jsonify({"success": False, "error": "No effects for this clip"}), 400
            
            if index < 0 or index >= len(player.clip_effects[abs_clip_path]):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            effect = player.clip_effects[abs_clip_path][index]
            
            # Update parameter value
            effect['parameters'][param_name] = param_value
            
            # If plugin instance exists, update it too
            if 'instance' in effect:
                setattr(effect['instance'], param_name, param_value)
            
            logger.debug(f"Updated Art-Net clip effect parameter {param_name}={param_value} for clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error updating Art-Net clip effect parameter: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    logger.info("✅ Art-Net Video routes registered successfully")
