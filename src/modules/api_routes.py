"""
API Routes - Playback, Settings, Art-Net Endpoints
"""
from flask import jsonify, request


def register_playback_routes(app, player):
    """Registriert Playback-Control Endpunkte."""
    
    @app.route('/api/play', methods=['POST'])
    def play():
        """Startet Video-Wiedergabe."""
        player.start()
        return jsonify({"status": "success", "message": "Video gestartet"})
    
    @app.route('/api/stop', methods=['POST'])
    def stop():
        """Stoppt Video-Wiedergabe."""
        player.stop()
        return jsonify({"status": "success", "message": "Video gestoppt"})
    
    @app.route('/api/pause', methods=['POST'])
    def pause():
        """Pausiert Wiedergabe."""
        player.pause()
        return jsonify({"status": "success", "message": "Video pausiert"})
    
    @app.route('/api/resume', methods=['POST'])
    def resume():
        """Setzt Wiedergabe fort."""
        player.resume()
        return jsonify({"status": "success", "message": "Wiedergabe fortgesetzt"})
    
    @app.route('/api/restart', methods=['POST'])
    def restart():
        """Startet Video neu."""
        player.restart()
        return jsonify({"status": "success", "message": "Video neu gestartet"})
    
    @app.route('/api/reload', methods=['POST'])
    def reload_application():
        """Startet die gesamte Anwendung neu."""
        import os
        import sys
        import threading
        
        def restart_app():
            import time
            time.sleep(0.5)
            python = sys.executable
            os.execl(python, python, *sys.argv)
        
        # Starte Neustart in separatem Thread, damit Response noch gesendet wird
        thread = threading.Thread(target=restart_app)
        thread.daemon = True
        thread.start()
        
        return jsonify({"status": "success", "message": "Anwendung wird neu gestartet..."})


def register_settings_routes(app, player):
    """Registriert Settings-Endpunkte."""
    
    @app.route('/api/brightness', methods=['POST'])
    def set_brightness():
        """Setzt Helligkeit."""
        data = request.get_json()
        value = data.get('value', 100)
        player.set_brightness(value)
        return jsonify({"status": "success", "brightness": player.brightness * 100})
    
    @app.route('/api/speed', methods=['POST'])
    def set_speed():
        """Setzt Wiedergabe-Geschwindigkeit."""
        data = request.get_json()
        value = data.get('value', 1.0)
        player.set_speed(value)
        return jsonify({"status": "success", "speed": player.speed_factor})
    
    @app.route('/api/fps', methods=['POST'])
    def set_fps():
        """Setzt FPS-Limit."""
        data = request.get_json()
        value = data.get('value')
        player.set_fps(value)
        return jsonify({"status": "success", "fps": player.fps_limit})
    
    @app.route('/api/loop', methods=['POST'])
    def set_loop():
        """Setzt Loop-Limit."""
        data = request.get_json()
        value = data.get('value', 0)
        player.set_loop_limit(value)
        return jsonify({"status": "success", "loop_limit": player.max_loops})


def register_artnet_routes(app, player):
    """Registriert Art-Net Endpunkte."""
    
    @app.route('/api/blackout', methods=['POST'])
    def blackout():
        """Aktiviert Blackout."""
        player.blackout()
        return jsonify({"status": "success", "message": "Blackout aktiviert"})
    
    @app.route('/api/test', methods=['POST'])
    def test_pattern():
        """Sendet Testmuster."""
        data = request.get_json() or {}
        color = data.get('color', 'red')
        player.test_pattern(color)
        return jsonify({"status": "success", "message": f"Testmuster '{color}' gesendet"})
    
    @app.route('/api/ip', methods=['POST'])
    def set_ip():
        """Setzt Art-Net Ziel-IP."""
        data = request.get_json()
        ip = data.get('ip')
        if ip:
            player.target_ip = ip
            return jsonify({"status": "success", "ip": player.target_ip, "message": "HINWEIS: Starte Video neu für Änderung"})
        return jsonify({"status": "error", "message": "Keine IP angegeben"}), 400
    
    @app.route('/api/ip', methods=['GET'])
    def get_ip():
        """Gibt aktuelle Art-Net Ziel-IP zurück."""
        return jsonify({"status": "success", "ip": player.target_ip})
    
    @app.route('/api/universe', methods=['POST'])
    def set_universe():
        """Setzt Art-Net Start-Universum."""
        data = request.get_json()
        universe = data.get('universe')
        if universe is not None:
            try:
                player.start_universe = int(universe)
                return jsonify({"status": "success", "universe": player.start_universe, "message": "HINWEIS: Starte Video neu für Änderung"})
            except ValueError:
                return jsonify({"status": "error", "message": "Ungültiger Wert"}), 400
        return jsonify({"status": "error", "message": "Kein Universum angegeben"}), 400
    
    @app.route('/api/universe', methods=['GET'])
    def get_universe():
        """Gibt aktuelles Art-Net Start-Universum zurück."""
        return jsonify({"status": "success", "universe": player.start_universe})


def register_info_routes(app, player):
    """Registriert Info-Endpunkte."""
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """Gibt aktuellen Status zurück."""
        return jsonify({
            "status": player.status(),
            "is_playing": player.is_playing,
            "is_paused": player.is_paused,
            "current_frame": player.current_frame,
            "total_frames": player.total_frames,
            "current_loop": player.current_loop,
            "brightness": player.brightness * 100,
            "speed": player.speed_factor
        })
    
    @app.route('/api/info', methods=['GET'])
    def info():
        """Gibt Player-Informationen zurück."""
        return jsonify(player.get_info())
    
    @app.route('/api/stats', methods=['GET'])
    def stats():
        """Gibt Live-Statistiken zurück."""
        return jsonify(player.get_stats())


def register_recording_routes(app, player):
    """Registriert Recording-Endpunkte."""
    
    @app.route('/api/record/start', methods=['POST'])
    def record_start():
        """Startet Aufzeichnung."""
        player.start_recording()
        return jsonify({"status": "success", "message": "Aufzeichnung gestartet"})
    
    @app.route('/api/record/stop', methods=['POST'])
    def record_stop():
        """Stoppt Aufzeichnung."""
        data = request.get_json() or {}
        filename = data.get('filename')
        player.stop_recording(filename)
        return jsonify({"status": "success", "message": "Aufzeichnung gestoppt"})


def register_cache_routes(app):
    """Registriert Cache-Management Endpunkte."""
    
    @app.route('/api/cache/info', methods=['GET'])
    def cache_info():
        """Gibt Cache-Informationen zurück."""
        import os
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
        
        if not os.path.exists(cache_dir):
            return jsonify({
                "status": "success",
                "exists": False,
                "message": "Cache-Ordner existiert nicht"
            })
        
        files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
        total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
        
        return jsonify({
            "status": "success",
            "exists": True,
            "files": len(files),
            "size_bytes": total_size,
            "size_mb": round(total_size / (1024*1024), 2),
            "path": cache_dir
        })
    
    @app.route('/api/cache/clear', methods=['POST'])
    def cache_clear():
        """Löscht Cache."""
        import os
        import shutil
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
        
        if not os.path.exists(cache_dir):
            return jsonify({
                "status": "success",
                "message": "Cache-Ordner existiert nicht"
            })
        
        file_count = len([f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))])
        shutil.rmtree(cache_dir)
        os.makedirs(cache_dir)
        
        return jsonify({
            "status": "success",
            "message": f"Cache geleert ({file_count} Dateien gelöscht)",
            "deleted_files": file_count
        })
