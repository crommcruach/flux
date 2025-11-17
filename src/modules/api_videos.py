"""
API Videos - Video Management Endpoints
"""
from flask import jsonify, request
import os


"""Video-Management API Routen"""
from flask import jsonify
import os
from .constants import VIDEO_EXTENSIONS


def register_video_routes(app, player, video_dir):
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
            
            current_video = os.path.relpath(player.video_path, video_dir)
            
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
        try:
            data = request.get_json()
            video_path = data.get('path')
            
            if not video_path:
                return jsonify({"status": "error", "message": "Kein Pfad angegeben"}), 400
            
            # Erstelle absoluten Pfad falls relativ
            if not os.path.isabs(video_path):
                video_path = os.path.join(video_dir, video_path)
            
            if not os.path.exists(video_path):
                return jsonify({"status": "error", "message": f"Video nicht gefunden: {video_path}"}), 404
            
            # Lade Video
            was_playing = player.is_playing
            success = player.load_video(video_path)
            
            if not success:
                return jsonify({"status": "error", "message": "Fehler beim Laden des Videos"}), 500
            
            # Auto-start wenn vorher spielte
            if was_playing:
                player.start()
            
            return jsonify({
                "status": "success",
                "message": f"Video geladen: {os.path.basename(video_path)}",
                "video": os.path.basename(video_path),
                "was_playing": was_playing
            })
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    @app.route('/api/video/current', methods=['GET'])
    def current_video():
        """Gibt aktuell geladenes Video zurück."""
        rel_path = os.path.relpath(player.video_path, video_dir)
        return jsonify({
            "status": "success",
            "filename": os.path.basename(player.video_path),
            "path": rel_path,
            "full_path": player.video_path,
            "is_playing": player.is_playing,
            "is_paused": player.is_paused,
            "current_frame": player.current_frame,
            "total_frames": player.total_frames
        })
