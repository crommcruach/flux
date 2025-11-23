"""
API Art-Net Playback - Separate Playback-Controls für Art-Net Player
"""
from flask import jsonify, request
import os
from .logger import get_logger
from .frame_source import VideoSource

logger = get_logger(__name__)


def register_artnet_playback_api(app, player_manager, video_dir, config):
    """Registriert Art-Net Player Playback API Endpunkte."""
    
    @app.route('/api/artnet/play', methods=['POST'])
    def artnet_play():
        """Startet oder setzt Art-Net Player Wiedergabe fort."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "No Art-Net player available"}), 404
            
            player.play()
            return jsonify({"success": True, "message": "Art-Net playback started"})
        except Exception as e:
            logger.error(f"Error starting Art-Net playback: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/pause', methods=['POST'])
    def artnet_pause():
        """Pausiert Art-Net Player Wiedergabe."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "No Art-Net player available"}), 404
            
            player.pause()
            return jsonify({"success": True, "message": "Art-Net playback paused"})
        except Exception as e:
            logger.error(f"Error pausing Art-Net playback: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/stop', methods=['POST'])
    def artnet_stop():
        """Stoppt Art-Net Player Wiedergabe."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "No Art-Net player available"}), 404
            
            player.stop()
            return jsonify({"success": True, "message": "Art-Net playback stopped"})
        except Exception as e:
            logger.error(f"Error stopping Art-Net playback: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    @app.route('/api/artnet/restart', methods=['POST'])
    def artnet_restart():
        """Startet Art-Net Player neu."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({"success": False, "error": "No Art-Net player available"}), 404
            
            player.restart()
            return jsonify({"success": True, "message": "Art-Net playback restarted"})
        except Exception as e:
            logger.error(f"Error restarting Art-Net playback: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    # NOTE: /api/artnet/video/load is now in api_videos.py (unified with video player)
    
    @app.route('/api/artnet/status', methods=['GET'])
    def artnet_status():
        """Gibt Status des Art-Net Players zurück."""
        try:
            player = player_manager.get_artnet_player()
            if not player:
                return jsonify({
                    "available": False,
                    "message": "No Art-Net player configured"
                })
            
            # Get video name
            video_name = "Unknown"
            if hasattr(player, 'current_source') and player.current_source:
                if hasattr(player.current_source, 'video_path'):
                    video_name = os.path.basename(player.source.video_path)
            
            return jsonify({
                "available": True,
                "is_playing": player.is_playing,
                "video": video_name,
                "fps": getattr(player.source, 'fps', 0) if player.source else 0,
                "total_frames": getattr(player.source, 'total_frames', 0) if player.source else 0,
                "current_frame": player.current_frame if player else 0
            })
        except Exception as e:
            logger.error(f"Error getting Art-Net status: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    
    def _get_video_list():
        """Helper: Holt sortierte Video-Liste."""
        videos = []
        if os.path.exists(video_dir):
            for root, dirs, files in os.walk(video_dir):
                for filename in files:
                    if filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
                        filepath = os.path.join(root, filename)
                        rel_path = os.path.relpath(filepath, video_dir)
                        videos.append(rel_path)
        return sorted(videos)

    # NOTE: Video-related endpoints (load, next, previous, playlist/set, status) 
    # are now in api_artnet_videos.py for cleaner separation
