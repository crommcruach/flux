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
from .constants import VIDEO_EXTENSIONS


def register_video_routes(app, player, dmx_controller, video_dir, config):
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
            current_player = dmx_controller.player
            current_video = None
            if hasattr(current_player, 'video_path'):
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
        """Lädt ein Video."""
        import sys
        import io
        from ..logger import get_logger
        
        logger = get_logger(__name__)
        
        data = request.get_json()
        video_path = data.get('path')
        
        if not video_path:
            return jsonify({"status": "error", "message": "Kein Pfad angegeben"}), 400
        
        # Erstelle absoluten Pfad falls relativ
        if not os.path.isabs(video_path):
            video_path = os.path.join(video_dir, video_path)
        
        if not os.path.exists(video_path):
            return jsonify({"status": "error", "message": f"Video nicht gefunden: {video_path}"}), 404
        
        # Umleite stdout/stderr um print() während Video-Load zu verhindern
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        try:
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            current_player = dmx_controller.player
            was_playing = current_player.is_playing
            
            # Prüfe ob aktueller Player ein ScriptPlayer ist
            if type(current_player).__name__ == 'ScriptPlayer':
                # Erstelle neuen VideoPlayer
                from .video_player import VideoPlayer
                
                # Stoppe ScriptPlayer
                current_player.stop()
                
                # Erstelle VideoPlayer mit gleichen Einstellungen
                new_player = VideoPlayer(
                    video_path,
                    current_player.points_json_path,
                    current_player.target_ip,
                    current_player.start_universe,
                    current_player.fps_limit,
                    config
                )
                
                # Übernehme Einstellungen
                new_player.brightness = current_player.brightness
                new_player.speed_factor = current_player.speed_factor
                
                # Aktualisiere Player-Referenz
                dmx_controller.player = new_player
                
                # Starte wenn vorher lief
                if was_playing:
                    new_player.start()
            else:
                # Normaler VideoPlayer - nutze load_video
                success = current_player.load_video(video_path)
                
                if not success:
                    return jsonify({"status": "error", "message": "Fehler beim Laden des Videos"}), 500
                
                # Auto-start wenn vorher spielte
                if was_playing:
                    current_player.start()
            
            # Warte kurz damit Thread initialisiert
            import time
            time.sleep(0.1)
            
            # WICHTIG: stdout/stderr VOR return wiederherstellen!
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            return jsonify({
                "status": "success",
                "message": f"Video geladen: {os.path.basename(video_path)}",
                "video": os.path.basename(video_path),
                "was_playing": was_playing
            })
            
        except Exception as e:
            import traceback
            # Stelle stdout/stderr wieder her vor dem return
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            logger.error(traceback.format_exc())
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/video/current', methods=['GET'])
    def current_video():
        """Gibt aktuell geladenes Video zurück."""
        current_player = dmx_controller.player
        
        # Prüfe ob es ein VideoPlayer ist
        if not hasattr(current_player, 'video_path'):
            return jsonify({
                "status": "error",
                "message": "Kein Video geladen (Script-Modus aktiv)"
            }), 404
        
        rel_path = os.path.relpath(current_player.video_path, video_dir)
        return jsonify({
            "status": "success",
            "filename": os.path.basename(current_player.video_path),
            "path": rel_path,
            "full_path": current_player.video_path,
            "is_playing": current_player.is_playing,
            "is_paused": current_player.is_paused,
            "current_frame": current_player.current_frame,
            "total_frames": current_player.total_frames
        })
