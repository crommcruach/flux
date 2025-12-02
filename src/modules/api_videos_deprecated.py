"""
API Videos - Video Management Endpoints

WICHTIG: Verwende NIEMALS print() Statements in API-Funktionen!
Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
Nutze stattdessen immer den Logger.
"""
from flask import jsonify, request
import os


"""Video-Management API Routen"""
from flask import jsonify
import os
import sys
import io
from .constants import VIDEO_EXTENSIONS
from .logger import get_logger
from .frame_source import VideoSource

logger = get_logger(__name__)


def register_video_routes(app, player_manager, video_dir, config):
    """Registriert Video-Management Endpunkte."""
    
    @app.route('/api/videos', methods=['GET'])
    def list_videos():
        """Listet alle verfügbaren Videos auf."""
        try:
            if not os.path.exists(video_dir):
                return jsonify({"status": "error", "message": "Video-Verzeichnis nicht gefunden"}), 404
            
            video_extensions = VIDEO_EXTENSIONS
            videos = []
            
            # Scanne video-Ordner und Unterordner
            for root, dirs, files in os.walk(video_dir):
                for filename in files:
                    if filename.lower().endswith(video_extensions):
                        filepath = os.path.join(root, filename)
                        rel_path = os.path.relpath(filepath, video_dir)
                        file_size = os.path.getsize(filepath)
                        folder_name = os.path.dirname(rel_path) if os.path.dirname(rel_path) else "root"
                        
                        # Extrahiere Kanal-Nummer aus Ordnername (z.B. "kanal_1" -> 1)
                        kanal = 0
                        if folder_name.startswith("kanal_"):
                            try:
                                kanal = int(folder_name.split("_")[1])
                            except (IndexError, ValueError):
                                pass
                        
                        videos.append({
                            "filename": filename,
                            "name": os.path.splitext(filename)[0],
                            "path": rel_path,
                            "full_path": filepath,
                            "size": file_size,
                            "folder": folder_name,
                            "kanal": kanal
                        })
            
            # Prüfe ob aktueller Player ein VideoPlayer ist
            current_player = player_manager.player
            current_video = None
            if hasattr(current_player, 'video_path') and current_player.video_path:
                current_video = os.path.relpath(current_player.video_path, video_dir)
            
            return jsonify({
                "status": "success",
                "videos": sorted(videos, key=lambda x: x['path']),
                "current": current_video,
                "total": len(videos)
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/video/load', methods=['POST'])
    def load_video():
        """Lädt ein Video in den Video Player."""
        data = request.get_json()
        video_path = data.get('path')
        clip_id = data.get('clip_id')  # Frontend kann UUID mitgeben
        
        if not video_path:
            return jsonify({"status": "error", "message": "Kein Pfad angegeben"}), 400
        
        # Erstelle absoluten Pfad falls relativ
        if not os.path.isabs(video_path):
            video_path = os.path.join(video_dir, video_path)
        
        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": f"Video nicht gefunden: {video_path}"}), 404
        
        try:
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"status": "error", "message": "No video player available"}), 404
            
            was_playing = player.is_playing
            
            # Erstelle neue VideoSource mit clip_id für trim settings
            video_source = VideoSource(
                video_path,
                player.canvas_width,
                player.canvas_height,
                config,
                clip_id=clip_id  # Pass clip_id to load trim settings
            )
            
            # Set current_clip_id on player for reload functionality
            player.current_clip_id = clip_id
            
            # Wechsle Source
            success = player.switch_source(video_source)
            
            if not success:
                return jsonify({"status": "error", "message": "Fehler beim Laden des Videos"}), 500
            
            # Try to find index in playlist
            video_in_playlist = False
            if hasattr(player, 'playlist') and player.playlist:
                try:
                    player.playlist_index = player.playlist.index(video_path)
                    video_in_playlist = True
                    logger.debug(f"📋 Video in Playlist gefunden: Index {player.playlist_index}/{len(player.playlist)}")
                except ValueError:
                    player.playlist_index = -1
                    logger.warning(f"⚠️ Video nicht in Playlist: {video_path}")
            
            # Setze Loop-Verhalten basierend auf Playlist-Status
            if video_in_playlist:
                player.max_loops = 0  # Endlosschleife wenn in Playlist
                logger.debug(f"🔁 Video in Endlosschleife (in Playlist)")
            else:
                player.max_loops = 1  # Nur 1x abspielen wenn nicht in Playlist
                logger.debug(f"▶️ Video einmal abspielen (nicht in Playlist)")
            
            # Play if was playing before
            if was_playing:
                player.play()
            
            rel_path = os.path.relpath(video_path, video_dir)
            
            return jsonify({
                "status": "success",
                "message": f"Video geladen: {os.path.basename(video_path)}",
                "video": rel_path,
                "was_playing": was_playing
            })
            
        except Exception as e:
            logger.error(f"Error loading video: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # NOTE: Art-Net video endpoints are in api_artnet_videos.py
    
    @app.route('/api/video/current', methods=['GET'])
    def current_video():
        """Gibt aktuell geladenes Video zurück."""
        current_player = player_manager.get_video_player()
        
        # Prüfe ob es ein VideoPlayer ist
        if not current_player or not hasattr(current_player, 'source'):
            return jsonify({
                "status": "error",
                "message": "Kein Video geladen"
            }), 404
        
        # Get video path from source
        video_path = None
        if hasattr(current_player.source, 'video_path'):
            video_path = current_player.source.video_path
        
        if not video_path:
            return jsonify({
                "status": "error",
                "message": "Kein Video geladen"
            }), 404
        
        rel_path = os.path.relpath(video_path, video_dir)
        return jsonify({
            "status": "success",
            "filename": os.path.basename(video_path),
            "path": rel_path,
            "full_path": video_path,
            "is_playing": current_player.is_playing,
            "is_paused": current_player.is_paused,
            "current_frame": current_player.current_frame,
            "total_frames": getattr(current_player.source, 'total_frames', 0) if current_player.source else 0
        })
    
    def _get_video_list():
        """Helper: Holt sortierte Video-Liste."""
        videos = []
        if os.path.exists(video_dir):
            for root, dirs, files in os.walk(video_dir):
                for filename in files:
                    if filename.lower().endswith(VIDEO_EXTENSIONS):
                        filepath = os.path.join(root, filename)
                        rel_path = os.path.relpath(filepath, video_dir)
                        videos.append(rel_path)
        return sorted(videos)

    @app.route('/api/video/next', methods=['POST'])
    def next_video():
        """Lädt das nächste Video aus der Playlist."""
        try:
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"status": "error", "message": "No video player available"}), 404
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"status": "error", "message": "No playlist configured"}), 404
        
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
                "message": "Next video loaded",
                "video": rel_path
            })
        
        except Exception as e:
            logger.error(f"Error loading next video: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/video/previous', methods=['POST'])
    def previous_video():
        """Lädt das vorherige Video aus der Playlist."""
        try:
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"status": "error", "message": "No video player available"}), 404
        
            # Check if player has playlist
            if not hasattr(player, 'playlist') or not player.playlist:
                return jsonify({"status": "error", "message": "No playlist configured"}), 404
        
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
                "message": "Previous video loaded",
                "video": rel_path
            })
        
        except Exception as e:
            logger.error(f"Error loading previous video: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/video/status', methods=['GET'])
    def video_status():
        """Gibt den Status des Video Players zurück."""
        try:
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"status": "error", "message": "No video player available"}), 404
            
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
            logger.error(f"Error getting video status: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # NOTE: /api/artnet/video/status is in api_artnet_videos.py
    
    @app.route('/api/video/playlist/set', methods=['POST'])
    def set_video_playlist():
        """Setzt die Playlist für den Video Player."""
        try:
            data = request.get_json()
            playlist = data.get('playlist', [])
            autoplay = data.get('autoplay', False)
            loop = data.get('loop', False)
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"status": "error", "message": "No video player available"}), 404
            
            # Konvertiere relative Pfade zu absoluten UND speichere UUIDs
            absolute_playlist = []
            playlist_ids = {}  # Map: path -> uuid
            
            for item in playlist:
                path = item if isinstance(item, str) else item.get('path', '')
                if not os.path.isabs(path):
                    path = os.path.join(video_dir, path)
                absolute_playlist.append(path)
                
                # Extrahiere UUID und registriere Clip proaktiv
                if isinstance(item, dict):
                    item_id = item.get('id')
                    item_type = item.get('type', 'video')
                    generator_id = item.get('generator_id')
                    parameters = item.get('parameters')
                    
                    if item_id:
                        playlist_ids[path] = item_id
                        logger.debug(f"🔍 [VIDEO] Processing playlist item: {item_id} → {path}")
                        
                        # Registriere in clip_registry
                        if item_id not in clip_registry.clips:
                            logger.info(f"📌 [VIDEO] Registering NEW clip: {item_id} → {os.path.basename(path)}")
                            clip_registry.clips[item_id] = {
                                'clip_id': item_id,
                                'player_id': 'video',
                                'absolute_path': path,
                                'relative_path': os.path.relpath(path, video_dir) if not path.startswith('generator:') else path,
                                'filename': os.path.basename(path),
                                'metadata': {'type': item_type, 'generator_id': generator_id, 'parameters': parameters} if item_type == 'generator' else {},
                                'created_at': datetime.now().isoformat(),
                                'effects': []
                            }
                        else:
                            logger.debug(f"✅ [VIDEO] Clip already registered: {item_id}")
                    else:
                        logger.warning(f"⚠️ [VIDEO] Playlist item has no UUID: {path}")
            
            player.playlist = absolute_playlist
            player.playlist_ids = playlist_ids
            logger.info(f"📋 [VIDEO] Playlist set with {len(playlist_ids)} UUIDs, {len([id for id in playlist_ids.values() if id in clip_registry.clips])} registered")
            player.autoplay = autoplay
            player.loop_playlist = loop
            
            # Setze Index auf aktuelles Video wenn vorhanden
            current_video_in_playlist = False
            if hasattr(player.source, 'video_path') and player.source.video_path:
                try:
                    player.playlist_index = absolute_playlist.index(player.source.video_path)
                    current_video_in_playlist = True
                    logger.debug(f"📋 Current video in playlist: Index {player.playlist_index}")
                except ValueError:
                    player.playlist_index = -1
                    logger.debug(f"📋 Current video not in playlist")
            
            # Wenn aktuelles Video in Playlist ist: setze Endlosschleife
            if current_video_in_playlist:
                player.max_loops = 0  # 0 = Endlosschleife
                logger.debug(f"🔁 Video in Endlosschleife gesetzt (max_loops=0)")
                
                # Starte automatisch wenn nicht schon läuft
                if not player.is_playing:
                    player.play()
                    logger.info(f"▶️ Video automatisch gestartet (in Playlist)")
            else:
                # Aktuelles Video wurde aus Playlist entfernt
                if hasattr(player.source, 'video_path') and player.source.video_path:
                    logger.info(f"🗑️ Video aus Playlist entfernt - stoppe Player: {os.path.basename(player.source.video_path)}")
                    player.stop()
                    # Optional: Source zurücksetzen auf leeres Dummy
                    # player.source = None
                
                player.max_loops = 1  # Nur 1x abspielen wenn nicht in Playlist
            
            logger.info(f"Video playlist set: {len(absolute_playlist)} videos, autoplay={autoplay}, loop={loop}, playlist_index={player.playlist_index}, max_loops={player.max_loops}")
            return jsonify({
                "status": "success",
                "playlist_length": len(absolute_playlist),
                "autoplay": autoplay,
                "loop": loop
            })
        except Exception as e:
            logger.error(f"Error setting video playlist: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # NOTE: Art-Net video endpoints (next, previous, playlist/set) are in api_artnet_videos.py
    
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
            
            logger.info(f"Playlists saved: {name} (Video: {len(video_playlist)}, Art-Net: {len(artnet_playlist)})")
            return jsonify({
                "status": "success",
                "message": f"Playlists '{name}' saved",
                "path": playlist_path,
                "video_count": len(video_playlist),
                "artnet_count": len(artnet_playlist)
            })
        
        except Exception as e:
            logger.error(f"Error saving playlists: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/playlist/load/<name>', methods=['GET'])
    def load_playlist(name):
        """Lädt eine gespeicherte Playlist."""
        try:
            import json
            
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            
            if not os.path.exists(playlist_path):
                return jsonify({"status": "error", "message": "Playlist not found"}), 404
            
            with open(playlist_path, 'r', encoding='utf-8') as f:
                playlist_data = json.load(f)
            
            logger.info(f"Playlist loaded: {name} ({len(playlist_data.get('videos', []))} videos)")
            return jsonify({
                "status": "success",
                "playlist": playlist_data
            })
        
        except Exception as e:
            logger.error(f"Error loading playlist: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/playlists', methods=['GET'])
    def list_playlists():
        """Listet alle gespeicherten Playlists auf."""
        try:
            import json
            
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            
            if not os.path.exists(playlists_dir):
                return jsonify({"status": "success", "playlists": []})
            
            playlists = []
            for filename in os.listdir(playlists_dir):
                if filename.endswith('.json'):
                    try:
                        with open(os.path.join(playlists_dir, filename), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Handle both old and new format
                            video_count = len(data.get('video_playlist', data.get('videos', [])))
                            artnet_count = len(data.get('artnet_playlist', []))
                            
                            playlists.append({
                                'name': data.get('name', filename[:-5]),
                                'created': data.get('created', ''),
                                'video_count': video_count,
                                'artnet_count': artnet_count,
                                'total_count': video_count + artnet_count
                            })
                    except Exception as e:
                        logger.warning(f"Could not read playlist {filename}: {e}")
            
            playlists.sort(key=lambda x: x.get('created', ''), reverse=True)
            
            return jsonify({
                "status": "success",
                "playlists": playlists
            })
        
        except Exception as e:
            logger.error(f"Error listing playlists: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/playlist/delete/<name>', methods=['DELETE'])
    def delete_playlist(name):
        """Löscht eine gespeicherte Playlist."""
        try:
            playlists_dir = os.path.join(os.path.dirname(video_dir), 'playlists')
            playlist_path = os.path.join(playlists_dir, f'{name}.json')
            
            if not os.path.exists(playlist_path):
                return jsonify({"status": "error", "message": "Playlist not found"}), 404
            
            os.remove(playlist_path)
            
            logger.info(f"Playlist deleted: {name}")
            return jsonify({
                "status": "success",
                "message": f"Playlist '{name}' deleted"
            })
        
        except Exception as e:
            logger.error(f"Error deleting playlist: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # ========================================
    # CLIP-LEVEL EFFECTS
    # ========================================
    
    @app.route('/api/video/clip/effects/add', methods=['POST'])
    def add_clip_effect_video():
        """Fügt einen Effekt zu einem Video-Clip hinzu."""
        try:
            data = request.get_json()
            plugin_id = data.get('plugin_id')
            clip_path = data.get('clip_path')
            
            if not plugin_id:
                return jsonify({"success": False, "error": "Missing plugin_id"}), 400
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"success": False, "error": "Video player not found"}), 404
            
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
                        if 'type' in param_dict and hasattr(param_dict['type'], 'name'):
                            param_dict['type'] = param_dict['type'].name
                    else:
                        # Handle Parameter objects (fallback)
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
            
            # Initialize clip_effects dict if not exists
            if not hasattr(player, 'clip_effects'):
                player.clip_effects = {}
            
            # Add effect to clip
            if abs_clip_path not in player.clip_effects:
                player.clip_effects[abs_clip_path] = []
            
            player.clip_effects[abs_clip_path].append(effect_data)
            
            logger.info(f"Added clip effect '{plugin_id}' to clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error adding clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/video/clip/effects', methods=['POST'])
    def get_clip_effects_video():
        """Gibt die Effekte eines Video-Clips zurück."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"success": False, "error": "Video player not found"}), 404
            
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
            logger.error(f"Error getting clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/video/clip/effects/<int:index>', methods=['DELETE'])
    def remove_clip_effect_video(index):
        """Entfernt einen Effekt von einem Video-Clip."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"success": False, "error": "Video player not found"}), 404
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            if not hasattr(player, 'clip_effects') or abs_clip_path not in player.clip_effects:
                return jsonify({"success": False, "error": "No effects for this clip"}), 404
            
            if index < 0 or index >= len(player.clip_effects[abs_clip_path]):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            removed = player.clip_effects[abs_clip_path].pop(index)
            
            logger.info(f"Removed clip effect at index {index} from clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error removing clip effect: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/video/clip/effects/clear', methods=['POST'])
    def clear_clip_effects_video():
        """Löscht alle Effekte eines Video-Clips."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"success": False, "error": "Video player not found"}), 404
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            if hasattr(player, 'clip_effects') and abs_clip_path in player.clip_effects:
                player.clip_effects[abs_clip_path] = []
            
            logger.info(f"Cleared all clip effects from clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error clearing clip effects: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/video/clip/effects/<int:index>/parameter', methods=['PUT'])
    def update_clip_effect_parameter_video(index):
        """Aktualisiert einen Parameter eines Clip-Effekts."""
        try:
            data = request.get_json()
            clip_path = data.get('clip_path')
            param_name = data.get('name')
            param_value = data.get('value')
            
            if not clip_path:
                return jsonify({"success": False, "error": "Missing clip_path"}), 400
            
            if not param_name:
                return jsonify({"success": False, "error": "Missing parameter name"}), 400
            
            player = player_manager.get_video_player()
            if not player:
                return jsonify({"success": False, "error": "Video player not found"}), 404
            
            abs_clip_path = os.path.abspath(os.path.join(video_dir, clip_path))
            
            logger.info(f"🔧 Updating Video clip effect #{index}: {param_name}={param_value}")
            logger.info(f"   clip_path: {clip_path} → abs: {abs_clip_path}")
            if hasattr(player, 'clip_effects'):
                logger.info(f"   Available clips: {list(player.clip_effects.keys())}")
            
            if not hasattr(player, 'clip_effects') or abs_clip_path not in player.clip_effects:
                return jsonify({"success": False, "error": "No effects for this clip"}), 404
            
            if index < 0 or index >= len(player.clip_effects[abs_clip_path]):
                return jsonify({"success": False, "error": "Invalid effect index"}), 400
            
            effect = player.clip_effects[abs_clip_path][index]
            
            # Update parameter value
            effect['parameters'][param_name] = param_value
            
            # If plugin instance exists, update it too
            if 'instance' in effect:
                setattr(effect['instance'], param_name, param_value)
            
            logger.debug(f"Updated clip effect parameter {param_name}={param_value} for clip: {clip_path}")
            
            return jsonify({"success": True})
        
        except Exception as e:
            logger.error(f"Error updating clip effect parameter: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
