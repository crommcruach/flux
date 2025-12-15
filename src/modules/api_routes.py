"""
API Routes - Playback, Settings, Art-Net Endpoints
"""
from flask import jsonify, request
from .logger import get_logger

logger = get_logger(__name__)


def register_playback_routes(app, player_manager):
    """Registriert Playback-Control Endpunkte."""
    
    @app.route('/api/play', methods=['POST'])
    def play():
        """Startet oder setzt Video-Wiedergabe fort."""
        player = player_manager.get_video_player()
        if not player.source:
            return jsonify({"status": "error", "message": "Kein Video geladen"}), 400
        player.play()
        return jsonify({"status": "success", "message": "Video play"})
    
    @app.route('/api/stop', methods=['POST'])
    def stop():
        """Stoppt Video-Wiedergabe."""
        player = player_manager.get_video_player()
        player.stop()
        return jsonify({"status": "success", "message": "Video gestoppt"})
    
    @app.route('/api/pause', methods=['POST'])
    def pause():
        """Pausiert Wiedergabe."""
        player = player_manager.get_video_player()
        player.pause()
        return jsonify({"status": "success", "message": "Video pausiert"})
    
    @app.route('/api/resume', methods=['POST'])
    def resume():
        """Setzt Wiedergabe fort."""
        player = player_manager.get_video_player()
        player.resume()
        return jsonify({"status": "success", "message": "Wiedergabe fortgesetzt"})
    
    @app.route('/api/restart', methods=['POST'])
    def restart():
        """Startet Video neu."""
        player = player_manager.get_video_player()
        player.restart()
        return jsonify({"status": "success", "message": "Video neu gestartet"})
    
    @app.route('/api/reload', methods=['POST'])
    def reload_application():
        """Startet die gesamte Anwendung neu."""
        import os
        import sys
        import threading
        import subprocess
        from modules.logger import get_logger
        
        logger = get_logger(__name__)
        
        def restart_app():
            import time
            time.sleep(1.0)  # Warte länger, damit Response gesendet wird
            
            try:
                python = sys.executable
                script = sys.argv[0]
                
                logger.info(f"Starte Anwendung neu: {python} {script}")
                
                # Windows: Nutze subprocess.Popen für sauberen Neustart
                if sys.platform == 'win32':
                    # Starte neuen Prozess ohne neue Console
                    # DETACHED_PROCESS = 0x00000008 (als Konstante, da nicht in subprocess)
                    DETACHED_PROCESS = 0x00000008
                    subprocess.Popen(
                        [python, script] + sys.argv[1:],
                        creationflags=DETACHED_PROCESS,
                        close_fds=True
                    )
                else:
                    # Unix: os.execl funktioniert hier besser
                    os.execl(python, python, *sys.argv)
                
                # Beende aktuellen Prozess
                logger.info("Beende aktuellen Prozess...")
                os._exit(0)
                
            except Exception as e:
                logger.error(f"Fehler beim Neustart: {e}")
                os._exit(1)
        
        # Starte Neustart in separatem Thread, damit Response noch gesendet wird
        thread = threading.Thread(target=restart_app)
        thread.daemon = False  # Nicht-daemon, damit Thread zu Ende läuft
        thread.start()
        
        return jsonify({"status": "success", "message": "Anwendung wird neu gestartet..."})


def register_settings_routes(app, player_manager):
    """Registriert Settings-Endpunkte."""
    
    @app.route('/api/brightness', methods=['POST'])
    def set_brightness():
        """Setzt Helligkeit."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value', 100)
        player.set_brightness(value)
        return jsonify({"status": "success", "brightness": player.brightness * 100})
    
    @app.route('/api/speed', methods=['POST'])
    def set_speed():
        """Setzt Wiedergabe-Geschwindigkeit."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value', 1.0)
        player.set_speed(value)
        return jsonify({"status": "success", "speed": player.speed_factor})
    
    @app.route('/api/hue', methods=['POST'])
    def set_hue():
        """Setzt Hue Rotation."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value', 0)
        player.set_hue_shift(value)
        return jsonify({"status": "success", "hue_shift": player.hue_shift})
    
    @app.route('/api/fps', methods=['POST'])
    def set_fps():
        """Setzt Art-Net FPS."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value')
        if player and player.artnet_manager:
            player.artnet_manager.set_fps(value)
            return jsonify({"status": "success", "fps": value})
        return jsonify({"status": "error", "message": "Kein Art-Net aktiv"}), 400
    
    @app.route('/api/loop', methods=['POST'])
    def set_loop():
        """Setzt Loop-Limit."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value', 0)
        player.set_loop_limit(value)
        return jsonify({"status": "success", "loop_limit": player.max_loops})


def register_artnet_routes(app, player_manager):
    """Registriert Art-Net Endpunkte."""
    
    @app.route('/api/blackout', methods=['POST'])
    def blackout():
        """Aktiviert Blackout."""
        player = player_manager.player
        if not player:
            return jsonify({"status": "error", "message": "Kein Player geladen"}), 400
        player.blackout()
        return jsonify({"status": "success", "message": "Blackout aktiviert"})
    
    @app.route('/api/test', methods=['POST'])
    def test_pattern():
        """Sendet Testmuster."""
        player = player_manager.player
        if not player:
            return jsonify({"status": "error", "message": "Kein Player geladen"}), 400
        data = request.get_json() or {}
        color = data.get('color', 'red')
        player.test_pattern(color)
        return jsonify({"status": "success", "message": f"Testmuster '{color}' gesendet"})
    
    @app.route('/api/ip', methods=['POST'])
    def set_ip():
        """Setzt Art-Net Ziel-IP."""
        player = player_manager.player
        data = request.get_json()
        ip = data.get('ip')
        if ip:
            player.target_ip = ip
            return jsonify({"status": "success", "ip": player.target_ip, "message": "HINWEIS: Starte Video neu für Änderung"})
        return jsonify({"status": "error", "message": "Keine IP angegeben"}), 400
    
    @app.route('/api/ip', methods=['GET'])
    def get_ip():
        """Gibt aktuelle Art-Net Ziel-IP zurück."""
        try:
            player = player_manager.player
            return jsonify({"status": "success", "ip": player.target_ip})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/universe', methods=['POST'])
    def set_universe():
        """Setzt Art-Net Start-Universum."""
        try:
            player = player_manager.player
            data = request.get_json()
            universe = data.get('universe')
            if universe is not None:
                try:
                    player.start_universe = int(universe)
                    return jsonify({"status": "success", "universe": player.start_universe, "message": "HINWEIS: Starte Video neu für Änderung"})
                except ValueError:
                    return jsonify({"status": "error", "message": "Ungültiger Wert"}), 400
            return jsonify({"status": "error", "message": "Kein Universum angegeben"}), 400
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/universe', methods=['GET'])
    def get_universe():
        """Gibt aktuelles Art-Net Start-Universum zurück."""
        try:
            player = player_manager.player
            return jsonify({"status": "success", "universe": player.start_universe})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/artnet/info', methods=['GET'])
    def artnet_info():
        """Gibt Art-Net Informationen und Statistiken zurück."""
        try:
            player = player_manager.player
            artnet_manager = player.artnet_manager
            
            network_stats = artnet_manager.get_network_stats()
            
            # Get brightness from player
            brightness = int(player.brightness * 100) if hasattr(player, 'brightness') else 100
            
            return jsonify({
                "status": "success",
                "artnet_brightness": brightness,
                "artnet_fps": artnet_manager.get_fps(),
                "total_universes": artnet_manager.required_universes,
                "packets_sent": network_stats['packets_sent'],
                "packets_per_sec": network_stats['packets_per_sec'],
                "mbps": network_stats['mbps'],
                "network_load": network_stats['network_load_percent'],
                "active_mode": artnet_manager.get_active_mode(),
                "delta_encoding": {
                    "enabled": artnet_manager.delta_encoding_enabled,
                    "threshold": artnet_manager.delta_threshold,
                    "bit_depth": artnet_manager.bit_depth,
                    "full_frame_interval": artnet_manager.full_frame_interval,
                    "frame_counter": artnet_manager.frame_counter
                }
            })
        except Exception as e:
            logger.error(f"Fehler in /api/artnet/info: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/artnet/delta-encoding', methods=['POST'])
    def set_delta_encoding():
        """Aktiviert/Deaktiviert Delta-Encoding zur Laufzeit."""
        try:
            from flask import request
            data = request.get_json()
            
            player = player_manager.player
            artnet_manager = player.artnet_manager
            
            if 'enabled' in data:
                enabled = bool(data['enabled'])
                artnet_manager.delta_encoding_enabled = enabled
                
                # Reset Frame-Counter und last_sent_frame bei Änderung
                artnet_manager.frame_counter = 0
                artnet_manager.last_sent_frame = None
                
                logger.info(f"Delta-Encoding {'aktiviert' if enabled else 'deaktiviert'}")
            
            if 'threshold' in data:
                artnet_manager.delta_threshold = int(data['threshold'])
                logger.info(f"Delta-Threshold auf {artnet_manager.delta_threshold} gesetzt")
            
            if 'full_frame_interval' in data:
                artnet_manager.full_frame_interval = int(data['full_frame_interval'])
                logger.info(f"Full-Frame-Interval auf {artnet_manager.full_frame_interval} gesetzt")
            
            return jsonify({
                "status": "success",
                "delta_encoding": {
                    "enabled": artnet_manager.delta_encoding_enabled,
                    "threshold": artnet_manager.delta_threshold,
                    "full_frame_interval": artnet_manager.full_frame_interval
                }
            })
        except Exception as e:
            logger.error(f"Fehler in /api/artnet/delta-encoding: {str(e)}")
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


def register_info_routes(app, player_manager, api=None, config=None):
    """Registriert Info-Endpunkte."""
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """Gibt aktuellen Status zurück."""
        player = player_manager.player
        return jsonify({
            "status": player.status(),
            "is_playing": player.is_playing,
            "is_paused": player.is_paused,
            "current_loop": player.current_loop
        })
    
    @app.route('/api/info', methods=['GET'])
    def info():
        """Gibt Player-Informationen zurück."""
        player = player_manager.player
        return jsonify(player.get_info())
    
    @app.route('/api/stats', methods=['GET'])
    def stats():
        """Gibt Live-Statistiken zurück."""
        player = player_manager.player
        return jsonify(player.get_stats())
    
    @app.route('/api/stream/traffic', methods=['GET'])
    def stream_traffic():
        """Gibt Traffic-Statistiken für Stream-APIs zurück."""
        import time
        
        def format_bytes(bytes_val):
            """Formatiert Bytes in lesbare Einheit."""
            for unit in ['B', 'KB', 'MB', 'GB']:
                if bytes_val < 1024.0:
                    return f"{bytes_val:.2f} {unit}"
                bytes_val /= 1024.0
            return f"{bytes_val:.2f} TB"
        
        def calculate_mbps(bytes_val, start_time):
            """Berechnet Mbps basierend auf Bytes und Zeitspanne."""
            elapsed = time.time() - start_time
            if elapsed <= 0:
                return 0.0
            bits = bytes_val * 8
            mbps = (bits / elapsed) / 1_000_000
            return round(mbps, 2)
        
        if api is None:
            return jsonify({'error': 'API instance not available'}), 500
            
        preview_stats = api.stream_traffic['preview']
        fullscreen_stats = api.stream_traffic['fullscreen']
        
        preview_mbps = calculate_mbps(preview_stats['bytes'], preview_stats['start_time'])
        fullscreen_mbps = calculate_mbps(fullscreen_stats['bytes'], fullscreen_stats['start_time'])
        
        return jsonify({
            'preview': {
                'bytes': preview_stats['bytes'],
                'frames': preview_stats['frames'],
                'formatted': format_bytes(preview_stats['bytes']),
                'mbps': preview_mbps
            },
            'fullscreen': {
                'bytes': fullscreen_stats['bytes'],
                'frames': fullscreen_stats['frames'],
                'formatted': format_bytes(fullscreen_stats['bytes']),
                'mbps': fullscreen_mbps
            },
            'total': {
                'bytes': preview_stats['bytes'] + fullscreen_stats['bytes'],
                'frames': preview_stats['frames'] + fullscreen_stats['frames'],
                'formatted': format_bytes(preview_stats['bytes'] + fullscreen_stats['bytes']),
                'mbps': round(preview_mbps + fullscreen_mbps, 2)
            }
        })
    
    @app.route('/api/preview/stream')
    def preview_stream():
        """MJPEG Video-Stream des aktuellen Frames."""
        from flask import Response
        import cv2
        import numpy as np
        import time
        
        # Load config settings for video preview
        cfg = config if config else {}
        preview_config = cfg.get('video', {}).get('preview_stream', {}).get('video', {})
        stream_fps = preview_config.get('fps', 30)
        max_width = preview_config.get('max_width', 640)
        jpeg_quality = preview_config.get('jpeg_quality', 85)
        frame_delay = 1.0 / stream_fps
        
        # WICHTIG: Keine Logger/Print-Aufrufe vor oder im Generator!
        # Dies würde "write() before start_response" Fehler verursachen
        
        def generate_frames():
            """Generator für MJPEG-Stream."""
            frame_count = 0
            while True:
                try:
                    frame_count += 1
                    # Hole aktuellen Player dynamisch
                    player = player_manager.player
                    # Hole aktuelles Video-Frame (komplettes Bild)
                    if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                        # Verwende komplettes Video-Frame (bereits in BGR) - KEIN COPY!
                        frame = player.last_video_frame
                    elif not hasattr(player, 'last_frame') or player.last_frame is None:
                        # Schwarzes Bild wenn kein Frame vorhanden
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                    else:
                        # Fallback: Rekonstruiere Bild aus LED-Punkten (NumPy-optimiert)
                        frame_data = player.last_frame
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        point_coords = getattr(player, 'point_coords', None)
                        
                        # Erstelle schwarzes Bild
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                        
                        # Zeichne die Punkte auf das Bild (NumPy fancy indexing - 10-50x schneller)
                        if point_coords is not None and len(frame_data) >= len(point_coords) * 3:
                            # NumPy array aus frame_data erstellen und reshapen
                            rgb_array = np.array(frame_data, dtype=np.uint8).reshape(-1, 3)
                            
                            # Filtere gültige Koordinaten
                            x_coords = point_coords[:, 0]
                            y_coords = point_coords[:, 1]
                            valid_mask = (y_coords >= 0) & (y_coords < canvas_height) & (x_coords >= 0) & (x_coords < canvas_width)
                            
                            # Setze alle Pixel auf einmal (BGR Format für OpenCV)
                            frame[y_coords[valid_mask], x_coords[valid_mask]] = rgb_array[valid_mask][:, [2, 1, 0]]
                    
                    # Skaliere auf Preview-Größe (wenn konfiguriert)
                    if max_width > 0 and frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Encode als JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    if not ret:
                        time.sleep(frame_delay)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # Traffic-Tracking
                    api.stream_traffic['preview']['bytes'] += len(frame_bytes)
                    api.stream_traffic['preview']['frames'] += 1
                    
                    # MJPEG Format: --frame boundary
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    # Frame rate limiting
                    time.sleep(frame_delay)
                
                except Exception as e:
                    # Bei Fehler: Schwarzes Bild
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)
        
        return Response(generate_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/preview/artnet/stream')
    def preview_artnet_stream():
        """MJPEG Stream des Art-Net Players."""
        from flask import Response
        import cv2
        import numpy as np
        import time
        
        # Load config settings for artnet preview
        cfg = config if config else {}
        preview_config = cfg.get('video', {}).get('preview_stream', {}).get('artnet', {})
        stream_fps = preview_config.get('fps', 30)
        max_width = preview_config.get('max_width', 640)
        jpeg_quality = preview_config.get('jpeg_quality', 85)
        frame_delay = 1.0 / stream_fps
        
        def generate_frames():
            """Generator für Art-Net Player MJPEG-Stream."""
            while True:
                try:
                    # Hole Art-Net Player
                    player = player_manager.artnet_player
                    
                    # Hole aktuelles Frame
                    if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                        frame = player.last_video_frame
                    elif not hasattr(player, 'last_frame') or player.last_frame is None:
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                    else:
                        # Rekonstruiere aus LED-Punkten
                        frame_data = player.last_frame
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        point_coords = getattr(player, 'point_coords', None)
                        
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                        
                        if point_coords is not None and len(frame_data) >= len(point_coords) * 3:
                            rgb_array = np.array(frame_data, dtype=np.uint8).reshape(-1, 3)
                            x_coords = point_coords[:, 0]
                            y_coords = point_coords[:, 1]
                            valid_mask = (y_coords >= 0) & (y_coords < canvas_height) & (x_coords >= 0) & (x_coords < canvas_width)
                            frame[y_coords[valid_mask], x_coords[valid_mask]] = rgb_array[valid_mask][:, [2, 1, 0]]
                    
                    # Skaliere auf Preview-Größe (wenn konfiguriert)
                    if max_width > 0 and frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    
                    # Encode als JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    if not ret:
                        time.sleep(frame_delay)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # MJPEG Format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    time.sleep(frame_delay)
                
                except Exception as e:
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)
        
        return Response(generate_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/fullscreen/stream')
    def fullscreen_stream():
        """MJPEG Video-Stream in voller Player-Auflösung (ohne Skalierung)."""
        from flask import Response
        import cv2
        import numpy as np
        import time
        
        # Load config settings for fullscreen
        cfg = config if config else {}
        fullscreen_config = cfg.get('video', {}).get('preview_stream', {}).get('fullscreen', {})
        stream_fps = fullscreen_config.get('fps', 60)
        max_width = fullscreen_config.get('max_width', 0)
        jpeg_quality = fullscreen_config.get('jpeg_quality', 95)
        frame_delay = 1.0 / stream_fps
        
        def generate_frames():
            """Generator für MJPEG-Stream ohne Preview-Skalierung."""
            frame_count = 0
            while True:
                try:
                    frame_count += 1
                    player = player_manager.player
                    
                    # Hole aktuelles Video-Frame (komplettes Bild)
                    if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                        # Verwende komplettes Video-Frame in voller Auflösung (bereits in BGR) - KEIN COPY!
                        frame = player.last_video_frame
                    elif not hasattr(player, 'last_frame') or player.last_frame is None:
                        # Schwarzes Bild wenn kein Frame vorhanden
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                    else:
                        # Fallback: Rekonstruiere Bild aus LED-Punkten (NumPy-optimiert)
                        frame_data = player.last_frame
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        point_coords = getattr(player, 'point_coords', None)
                        
                        # Erstelle schwarzes Bild
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                        
                        # Zeichne die Punkte auf das Bild (NumPy fancy indexing - 10-50x schneller)
                        if point_coords is not None and len(frame_data) >= len(point_coords) * 3:
                            # NumPy array aus frame_data erstellen und reshapen
                            rgb_array = np.array(frame_data, dtype=np.uint8).reshape(-1, 3)
                            
                            # Filtere gültige Koordinaten
                            x_coords = point_coords[:, 0]
                            y_coords = point_coords[:, 1]
                            valid_mask = (y_coords >= 0) & (y_coords < canvas_height) & (x_coords >= 0) & (x_coords < canvas_width)
                            
                            # Setze alle Pixel auf einmal (BGR Format für OpenCV)
                            frame[y_coords[valid_mask], x_coords[valid_mask]] = rgb_array[valid_mask][:, [2, 1, 0]]
                    
                    # Skaliere auf konfigurierte Größe (wenn max_width > 0)
                    if max_width > 0 and frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    
                    # Encode als JPEG mit konfigurierter Qualität
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    if not ret:
                        time.sleep(frame_delay)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # Traffic-Tracking
                    api.stream_traffic['fullscreen']['bytes'] += len(frame_bytes)
                    api.stream_traffic['fullscreen']['frames'] += 1
                    
                    # MJPEG Format: --frame boundary
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    # Frame rate limiting
                    time.sleep(frame_delay)
                
                except Exception as e:
                    # Bei Fehler: Schwarzes Bild
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(0.1)
        
        return Response(generate_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/preview/debug')
    def preview_debug():
        """Debug-Info über Player-Zustand."""
        info = {
            "has_last_video_frame": hasattr(player, 'last_video_frame'),
            "last_video_frame_is_none": hasattr(player, 'last_video_frame') and player.last_video_frame is None,
            "has_last_frame": hasattr(player, 'last_frame'),
            "last_frame_is_none": hasattr(player, 'last_frame') and player.last_frame is None,
            "is_playing": getattr(player, 'is_playing', False),
            "canvas_width": getattr(player, 'canvas_width', 'N/A'),
            "canvas_height": getattr(player, 'canvas_height', 'N/A'),
            "point_coords_len": len(getattr(player, 'point_coords', [])),
        }
        if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
            info["video_frame_shape"] = player.last_video_frame.shape
        if hasattr(player, 'last_frame') and player.last_frame is not None:
            info["last_frame_len"] = len(player.last_frame)
        return jsonify(info)
    
    @app.route('/api/preview/test')
    def preview_test():
        """Test-Endpoint: Zeigt ein farbiges Testbild."""
        from flask import Response
        import cv2
        import numpy as np
        import time
        
        def generate_test_frames():
            """Generiert bunte Testbilder."""
            colors = [
                (255, 0, 0),    # Blau
                (0, 255, 0),    # Grün
                (0, 0, 255),    # Rot
                (255, 255, 0),  # Cyan
                (255, 0, 255),  # Magenta
                (0, 255, 255),  # Gelb
            ]
            color_idx = 0
            
            while True:
                # Erstelle farbiges Testbild
                frame = np.zeros((180, 320, 3), dtype=np.uint8)
                frame[:, :] = colors[color_idx]
                color_idx = (color_idx + 1) % len(colors)
                
                # Encode als JPEG
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(0.5)  # Wechsel alle 0.5 Sekunden
        
        return Response(generate_test_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')


def register_recording_routes(app, player_manager, rest_api):
    """Registriert Recording-Endpunkte."""
    
    @app.route('/api/record/start', methods=['POST'])
    def record_start():
        """Startet Aufzeichnung."""
        data = request.get_json() or {}
        name = data.get('name')
        result = player_manager.player.start_recording(name)
        if result:
            return jsonify({"status": "success", "message": "Aufzeichnung gestartet"})
        else:
            return jsonify({"status": "error", "message": "Aufzeichnung nur während Video-Wiedergabe möglich"})
    
    @app.route('/api/record/stop', methods=['POST'])
    def record_stop():
        """Stoppt Aufzeichnung."""
        filename = player_manager.player.stop_recording()
        if filename:
            return jsonify({"status": "success", "message": "Aufzeichnung gespeichert", "filename": filename})
        return jsonify({"status": "error", "message": "Keine Frames aufgezeichnet - Video muss laufen"})
    
    @app.route('/api/recordings', methods=['GET'])
    def list_recordings():
        """Listet alle gespeicherten Aufzeichnungen."""
        if not rest_api.replay_manager:
            return jsonify({"recordings": []})
        
        recordings = rest_api.replay_manager.list_recordings()
        return jsonify({"recordings": recordings})
    
    @app.route('/api/replay/load', methods=['POST'])
    def replay_load():
        """Lädt eine Aufzeichnung."""
        if not rest_api.replay_manager:
            return jsonify({"status": "error", "message": "Replay Manager nicht verfügbar"}), 500
        
        data = request.get_json() or {}
        filename = data.get('filename')
        
        if not filename:
            return jsonify({"status": "error", "message": "Kein Dateiname angegeben"}), 400
        
        if rest_api.replay_manager.load_recording(filename):
            return jsonify({"status": "success", "message": f"Aufzeichnung {filename} geladen"})
        return jsonify({"status": "error", "message": "Fehler beim Laden"}), 400
    
    @app.route('/api/replay/start', methods=['POST'])
    def replay_start():
        """Startet Replay."""
        if not rest_api.replay_manager:
            return jsonify({"status": "error", "message": "Replay Manager nicht verfügbar"}), 500
        
        if rest_api.replay_manager.start():
            return jsonify({"status": "success", "message": "Replay gestartet"})
        return jsonify({"status": "error", "message": "Replay konnte nicht gestartet werden"}), 400
    
    @app.route('/api/replay/stop', methods=['POST'])
    def replay_stop():
        """Stoppt Replay."""
        if not rest_api.replay_manager:
            return jsonify({"status": "error", "message": "Replay Manager nicht verfügbar"}), 500
        
        if rest_api.replay_manager.stop():
            return jsonify({"status": "success", "message": "Replay gestoppt"})
        return jsonify({"status": "error", "message": "Kein Replay aktiv"}), 400
    
    @app.route('/api/replay/brightness', methods=['POST'])
    def replay_brightness():
        """Setzt Replay-Helligkeit."""
        if not rest_api.replay_manager:
            return jsonify({"status": "error", "message": "Replay Manager nicht verfügbar"}), 500
        
        data = request.get_json() or {}
        brightness = data.get('brightness')
        
        if brightness is None:
            return jsonify({"status": "error", "message": "Helligkeit nicht angegeben"}), 400
        
        brightness = max(0, min(100, int(brightness)))  # 0-100
        rest_api.replay_manager.set_brightness(brightness / 100.0)
        return jsonify({"status": "success", "brightness": brightness})
    
    @app.route('/api/replay/speed', methods=['POST'])
    def replay_speed():
        """Setzt Replay-Geschwindigkeit."""
        if not rest_api.replay_manager:
            return jsonify({"status": "error", "message": "Replay Manager nicht verfügbar"}), 500
        
        data = request.get_json() or {}
        speed = data.get('speed')
        
        if speed is None:
            return jsonify({"status": "error", "message": "Geschwindigkeit nicht angegeben"}), 400
        
        speed = max(0.1, min(10.0, float(speed)))
        rest_api.replay_manager.set_speed(speed)
        return jsonify({"status": "success", "speed": speed})


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


def register_script_routes(app, player_manager, config):
    """Registriert Script-Management Endpunkte."""
    
    @app.route('/api/scripts', methods=['GET'])
    def list_scripts():
        """Listet alle verfügbaren Scripts."""
        from .script_generator import ScriptGenerator
        
        scripts_dir = config['paths']['scripts_dir']
        script_gen = ScriptGenerator(scripts_dir)
        scripts = script_gen.list_scripts()
        
        return jsonify({
            "status": "success",
            "scripts": scripts,
            "count": len(scripts)
        })
    
    # ScriptSource removed - use GeneratorSource with generator plugins instead
    
    @app.route('/api/load_generator', methods=['POST'])
    def load_generator():
        """Lädt und startet einen Generator."""
        from ..logger import get_logger
        
        logger = get_logger(__name__)
        
        data = request.get_json()
        generator_id = data.get('generator_id')
        
        if not generator_id:
            return jsonify({
                "status": "error",
                "message": "Kein Generator-ID angegeben"
            }), 400
        
        # TODO: Implement generator loading via GeneratorSource
        logger.warning(f"Generator loading not yet implemented: {generator_id}")
        
        return jsonify({
            "status": "error",
            "message": "Generator loading not yet implemented - use web UI Sources tab"
        }), 501


def register_console_command_routes(app, player, dmx_controller, rest_api, video_dir, data_dir, config):
    """Registriert Console Command Endpunkte."""
    
    @app.route('/api/console', methods=['POST'])
    def execute_console_command():
        """Führt CLI-Befehl über Console aus."""
        import io
        import sys
        
        old_stdout = None
        try:
            data = request.get_json()
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "Keine Daten empfangen"
                }), 400
                
            command_line = data.get('command', '').strip()
            
            if not command_line:
                return jsonify({
                    "status": "error",
                    "message": "Kein Befehl angegeben"
                }), 400
            
            # Parse command und args wie in CLI
            parts = command_line.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else None
            
            # Spezielle Behandlung für help
            if command == "help":
                from .utils import print_help
                
                # Capture print output
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()
                try:
                    print_help()
                    output = sys.stdout.getvalue()
                finally:
                    sys.stdout = old_stdout
                    old_stdout = None
                
                return jsonify({
                    "status": "success",
                    "output": output
                })
            
            # Führe Befehl über CLI Handler aus - in separatem Thread!
            # Dies verhindert dass print() Statements die Flask Response stören
            import threading
            from .cli_handler import CLIHandler
            
            result_container = {'continue_loop': True, 'new_player': None, 'done': False}
            
            def execute_cli_command():
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                try:
                    # Umleite stdout/stderr zu StringIO um print() zu isolieren
                    sys.stdout = io.StringIO()
                    sys.stderr = io.StringIO()
                    
                    cli_handler = CLIHandler(player, dmx_controller, rest_api, video_dir, data_dir, config)
                    continue_loop, new_player = cli_handler.execute_command(command, args)
                    result_container['continue_loop'] = continue_loop
                    result_container['new_player'] = new_player
                except Exception as e:
                    import traceback
                    from ..logger import get_logger
                    logger = get_logger(__name__)
                    logger.error(traceback.format_exc())
                finally:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr
                    result_container['done'] = True
            
            # Starte in separatem Thread
            cmd_thread = threading.Thread(target=execute_cli_command, daemon=True)
            cmd_thread.start()
            cmd_thread.join(timeout=10.0)  # Warte max 10 Sekunden
            
            # Update player reference wenn ersetzt (über dmx_controller)
            if result_container['new_player']:
                dmx_controller.player = result_container['new_player']
            
            return jsonify({
                "status": "success",
                "output": f"Befehl '{command}' ausgeführt",
                "exit": not result_container['continue_loop']
            })
                
        except Exception as e:
            # Restore stdout wenn noch nicht gemacht
            if old_stdout:
                sys.stdout = old_stdout
            
            import traceback
            error_trace = traceback.format_exc()
            
            # Log Fehler
            try:
                from .logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"Console command error: {e}\n{error_trace}")
            except:
                pass
            
            return jsonify({
                "status": "error",
                "message": str(e),
                "traceback": error_trace
            }), 500
