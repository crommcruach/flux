"""
API Benchmark - Latenz-Messung für API-Calls
"""
from flask import jsonify, request
import time
from .logger import get_logger

logger = get_logger(__name__)


def register_benchmark_routes(app, player_manager):
    """Registriert Benchmark-Endpunkte für Latenz-Messung."""
    
    @app.route('/api/benchmark/ping', methods=['GET'])
    def benchmark_ping():
        """Einfacher Ping-Test ohne Player-Zugriff."""
        return jsonify({
            "status": "success",
            "message": "pong",
            "server_timestamp": time.time()
        })
    
    @app.route('/api/benchmark/player-status', methods=['GET'])
    def benchmark_player_status():
        """Misst Latenz für Player-Status-Abfrage."""
        start = time.perf_counter()
        
        player = player_manager.get_video_player()
        if not player:
            return jsonify({"status": "error", "message": "No player"}), 404
        
        # Sammle Player-Daten
        status = {
            "is_playing": player.is_playing,
            "is_paused": player.is_paused,
            "current_frame": player.current_frame,
            "total_frames": getattr(player.source, 'total_frames', 0) if player.source else 0
        }
        
        end = time.perf_counter()
        processing_time_ms = (end - start) * 1000
        
        return jsonify({
            "status": "success",
            "data": status,
            "server_processing_ms": round(processing_time_ms, 3),
            "server_timestamp": time.time()
        })
    
    @app.route('/api/benchmark/player-command', methods=['POST'])
    def benchmark_player_command():
        """Misst Latenz für Player-Befehl (Play/Pause Toggle)."""
        start = time.perf_counter()
        
        data = request.get_json() or {}
        command = data.get('command', 'toggle')  # toggle, play, pause, stop
        
        player = player_manager.get_video_player()
        if not player:
            return jsonify({"status": "error", "message": "No player"}), 404
        
        # Führe Befehl aus
        command_start = time.perf_counter()
        
        if command == 'toggle':
            if player.is_playing:
                player.pause()
                action = 'paused'
            else:
                player.play()
                action = 'started'
        elif command == 'play':
            player.play()
            action = 'started'
        elif command == 'pause':
            player.pause()
            action = 'paused'
        elif command == 'stop':
            player.stop()
            action = 'stopped'
        else:
            return jsonify({"status": "error", "message": f"Unknown command: {command}"}), 400
        
        command_end = time.perf_counter()
        command_time_ms = (command_end - command_start) * 1000
        
        end = time.perf_counter()
        total_time_ms = (end - start) * 1000
        
        return jsonify({
            "status": "success",
            "action": action,
            "command_execution_ms": round(command_time_ms, 3),
            "total_processing_ms": round(total_time_ms, 3),
            "server_timestamp": time.time()
        })
