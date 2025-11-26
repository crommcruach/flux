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
        """Lädt einen Clip in einen Player und registriert ihn."""
        try:
            data = request.get_json()
            video_path = data.get('path')
            
            if not video_path:
                return jsonify({"success": False, "error": "No path provided"}), 400
            
            # Get player
            player = player_manager.get_player(player_id)
            if not player:
                return jsonify({"success": False, "error": f"Player '{player_id}' not found"}), 404
            
            # Build absolute path
            if not os.path.isabs(video_path):
                absolute_path = os.path.join(video_dir, video_path)
                relative_path = video_path
            else:
                absolute_path = video_path
                relative_path = os.path.relpath(video_path, video_dir)
            
            if not os.path.exists(absolute_path):
                return jsonify({"success": False, "error": f"Video not found: {video_path}"}), 404
            
            # Register clip (get existing or create new)
            clip_id = clip_registry.register_clip(
                player_id=player_id,
                absolute_path=absolute_path,
                relative_path=relative_path,
                metadata={}
            )
            
            # Load video into player
            was_playing = player.is_playing
            
            video_source = VideoSource(
                absolute_path,
                player.canvas_width,
                player.canvas_height,
                config
            )
            
            success = player.switch_source(video_source)
            
            if not success:
                return jsonify({"success": False, "error": "Failed to load video"}), 500
            
            # Set current clip ID for effect management
            player.current_clip_id = clip_id
            logger.info(f"✅ [{player_id}] Loaded clip: {os.path.basename(absolute_path)} (clip_id={clip_id})")
            
            # Update playlist index if applicable
            if hasattr(player, 'playlist') and player.playlist:
                try:
                    player.playlist_index = player.playlist.index(absolute_path)
                except ValueError:
                    player.playlist_index = -1
            
            # Resume playback if was playing
            if was_playing:
                player.play()
            
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
            
            if not hasattr(player.source, 'video_path'):
                return jsonify({"success": False, "error": "No clip loaded"}), 404
            
            absolute_path = player.source.video_path
            clip_id = clip_registry.find_clip_by_path(player_id, absolute_path)
            
            if not clip_id:
                # Auto-register if not found
                relative_path = os.path.relpath(absolute_path, video_dir)
                clip_id = clip_registry.register_clip(player_id, absolute_path, relative_path)
            
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
                        if 'type' in param_dict and hasattr(param_dict['type'], 'value'):
                            param_dict['type'] = param_dict['type'].value
                    else:
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
            
            return jsonify({"success": True})
            
        except Exception as e:
            logger.error(f"Error clearing clip effects: {e}")
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
            })
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
        
            video_source = VideoSource(next_video_path, player.canvas_width, player.canvas_height, config)
            success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load video"}), 500
        
            # Update playlist index
            player.playlist_index = next_index
            
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = os.path.relpath(next_video_path, video_dir)
            return jsonify({
                "success": True,
                "message": "Next video loaded",
                "video": rel_path,
                "playlist_index": next_index
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
        
            video_source = VideoSource(prev_video_path, player.canvas_width, player.canvas_height, config)
            success = player.switch_source(video_source)
        
            if not success:
                return jsonify({"success": False, "error": "Failed to load video"}), 500
        
            # Update playlist index
            player.playlist_index = prev_index
            
            if was_playing:
                player.play()
        
            # Return relative path for frontend
            rel_path = os.path.relpath(prev_video_path, video_dir)
            return jsonify({
                "success": True,
                "message": "Previous video loaded",
                "video": rel_path,
                "playlist_index": prev_index
            })
        
        except Exception as e:
            logger.error(f"Error loading previous video: {e}")
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
            
            # Konvertiere relative Pfade zu absoluten
            absolute_playlist = []
            for item in playlist:
                path = item if isinstance(item, str) else item.get('path', '')
                if not os.path.isabs(path):
                    path = os.path.join(video_dir, path)
                absolute_playlist.append(path)
            
            player.playlist = absolute_playlist
            player.autoplay = autoplay
            player.loop_playlist = loop
            
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
                # Aktuelles Video wurde aus Playlist entfernt
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
                
                player.max_loops = 1  # Nur 1x abspielen wenn nicht in Playlist
            
            logger.info(f"✅ [{player_id}] Playlist set: {len(absolute_playlist)} videos, autoplay={autoplay}, loop={loop}")
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
    
    logger.info("✅ Unified Player API routes registered")
