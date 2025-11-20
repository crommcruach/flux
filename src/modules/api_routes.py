"""
API Routes - Playback, Settings, Art-Net Endpoints
"""
from flask import jsonify, request


def register_playback_routes(app, dmx_controller):
    """Registriert Playback-Control Endpunkte."""
    
    @app.route('/api/play', methods=['POST'])
    def play():
        """Startet Video-Wiedergabe."""
        player = dmx_controller.player
        player.start()
        return jsonify({"status": "success", "message": "Video gestartet"})
    
    @app.route('/api/stop', methods=['POST'])
    def stop():
        """Stoppt Video-Wiedergabe."""
        player = dmx_controller.player
        player.stop()
        return jsonify({"status": "success", "message": "Video gestoppt"})
    
    @app.route('/api/pause', methods=['POST'])
    def pause():
        """Pausiert Wiedergabe."""
        player = dmx_controller.player
        player.pause()
        return jsonify({"status": "success", "message": "Video pausiert"})
    
    @app.route('/api/resume', methods=['POST'])
    def resume():
        """Setzt Wiedergabe fort."""
        player = dmx_controller.player
        player.resume()
        return jsonify({"status": "success", "message": "Wiedergabe fortgesetzt"})
    
    @app.route('/api/restart', methods=['POST'])
    def restart():
        """Startet Video neu."""
        player = dmx_controller.player
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


def register_settings_routes(app, dmx_controller):
    """Registriert Settings-Endpunkte."""
    
    @app.route('/api/brightness', methods=['POST'])
    def set_brightness():
        """Setzt Helligkeit."""
        player = dmx_controller.player
        data = request.get_json()
        value = data.get('value', 100)
        player.set_brightness(value)
        return jsonify({"status": "success", "brightness": player.brightness * 100})
    
    @app.route('/api/speed', methods=['POST'])
    def set_speed():
        """Setzt Wiedergabe-Geschwindigkeit."""
        player = dmx_controller.player
        data = request.get_json()
        value = data.get('value', 1.0)
        player.set_speed(value)
        return jsonify({"status": "success", "speed": player.speed_factor})
    
    @app.route('/api/fps', methods=['POST'])
    def set_fps():
        """Setzt FPS-Limit."""
        player = dmx_controller.player
        data = request.get_json()
        value = data.get('value')
        player.set_fps(value)
        return jsonify({"status": "success", "fps": player.fps_limit})
    
    @app.route('/api/loop', methods=['POST'])
    def set_loop():
        """Setzt Loop-Limit."""
        player = dmx_controller.player
        data = request.get_json()
        value = data.get('value', 0)
        player.set_loop_limit(value)
        return jsonify({"status": "success", "loop_limit": player.max_loops})


def register_artnet_routes(app, dmx_controller):
    """Registriert Art-Net Endpunkte."""
    
    @app.route('/api/blackout', methods=['POST'])
    def blackout():
        """Aktiviert Blackout."""
        player = dmx_controller.player
        player.blackout()
        return jsonify({"status": "success", "message": "Blackout aktiviert"})
    
    @app.route('/api/test', methods=['POST'])
    def test_pattern():
        """Sendet Testmuster."""
        player = dmx_controller.player
        data = request.get_json() or {}
        color = data.get('color', 'red')
        player.test_pattern(color)
        return jsonify({"status": "success", "message": f"Testmuster '{color}' gesendet"})
    
    @app.route('/api/ip', methods=['POST'])
    def set_ip():
        """Setzt Art-Net Ziel-IP."""
        player = dmx_controller.player
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
            player = dmx_controller.player
            return jsonify({"status": "success", "ip": player.target_ip})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/universe', methods=['POST'])
    def set_universe():
        """Setzt Art-Net Start-Universum."""
        try:
            player = dmx_controller.player
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
            player = dmx_controller.player
            return jsonify({"status": "success", "universe": player.start_universe})
        except Exception as e:
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500


def register_info_routes(app, dmx_controller):
    """Registriert Info-Endpunkte."""
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """Gibt aktuellen Status zurück."""
        player = dmx_controller.player
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
        player = dmx_controller.player
        return jsonify(player.get_info())
    
    @app.route('/api/stats', methods=['GET'])
    def stats():
        """Gibt Live-Statistiken zurück."""
        player = dmx_controller.player
        return jsonify(player.get_stats())
    
    @app.route('/api/preview/stream')
    def preview_stream():
        """MJPEG Video-Stream des aktuellen Frames."""
        from flask import Response
        import cv2
        import numpy as np
        import time
        
        # WICHTIG: Keine Logger/Print-Aufrufe vor oder im Generator!
        # Dies würde "write() before start_response" Fehler verursachen
        
        def generate_frames():
            """Generator für MJPEG-Stream."""
            frame_count = 0
            while True:
                try:
                    frame_count += 1
                    # Hole aktuellen Player dynamisch
                    player = dmx_controller.player
                    # Hole aktuelles Video-Frame (komplettes Bild)
                    if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                        # Verwende komplettes Video-Frame (bereits in BGR)
                        frame = player.last_video_frame.copy()
                    elif not hasattr(player, 'last_frame') or player.last_frame is None:
                        # Schwarzes Bild wenn kein Frame vorhanden
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                    else:
                        # Fallback: Rekonstruiere Bild aus LED-Punkten
                        frame_data = player.last_frame
                        canvas_width = getattr(player, 'canvas_width', 320)
                        canvas_height = getattr(player, 'canvas_height', 180)
                        point_coords = getattr(player, 'point_coords', None)
                        
                        # Erstelle schwarzes Bild
                        frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                        
                        # Zeichne die Punkte auf das Bild
                        if point_coords is not None and len(frame_data) >= len(point_coords) * 3:
                            for i in range(len(point_coords)):
                                x, y = point_coords[i]
                                if 0 <= y < canvas_height and 0 <= x < canvas_width:
                                    r = frame_data[i * 3]
                                    g = frame_data[i * 3 + 1]
                                    b = frame_data[i * 3 + 2]
                                    # BGR Format für OpenCV
                                    frame[y, x] = [b, g, r]
                    
                    # Skaliere auf vernünftige Preview-Größe (optional)
                    max_width = 640
                    if frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Encode als JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if not ret:
                        time.sleep(0.033)  # ~30 FPS
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # MJPEG Format: --frame boundary
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    
                    # Limitiere auf ~30 FPS
                    time.sleep(0.033)
                
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


def register_script_routes(app, player, dmx_controller, config):
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
    
    @app.route('/api/load_script', methods=['POST'])
    def load_script():
        """Lädt und startet ein Script."""
        import sys
        import io
        from .script_player import ScriptPlayer
        from ..logger import get_logger
        
        logger = get_logger(__name__)
        
        data = request.get_json()
        script_name = data.get('script')
        
        if not script_name:
            return jsonify({
                "status": "error",
                "message": "Kein Script-Name angegeben"
            }), 400
        
        if not script_name.endswith('.py'):
            script_name += '.py'
        
        # Umleite stdout/stderr um print() während Script-Start zu verhindern
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        
        try:
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            # Stoppe aktuellen Player
            was_playing = player.is_playing
            if was_playing:
                player.stop()
            
            # Erstelle ScriptPlayer
            new_player = ScriptPlayer(
                script_name,
                player.points_json_path,
                player.target_ip if hasattr(player, 'target_ip') else '127.0.0.1',
                player.start_universe if hasattr(player, 'start_universe') else 0,
                player.fps_limit if hasattr(player, 'fps_limit') else 30,
                config
            )
            
            # Übernehme Einstellungen
            new_player.brightness = player.brightness if hasattr(player, 'brightness') else 1.0
            new_player.speed_factor = player.speed_factor if hasattr(player, 'speed_factor') else 1.0
            
            # Starte Script
            new_player.start()
            
            # Warte kurz damit Thread initialisiert (und potentielle stdout writes passieren)
            import time
            time.sleep(0.1)
            
            # Info
            info = new_player.get_info()
            
            # Aktualisiere Player-Referenz in dmx_controller
            if dmx_controller:
                dmx_controller.player = new_player
            
            # WICHTIG: stdout/stderr VOR return wiederherstellen!
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            
            return jsonify({
                "status": "success",
                "message": f"Script geladen: {info.get('name', script_name)}",
                "info": info
            })
            
        except Exception as e:
            import traceback
            # Stelle stdout/stderr wieder her vor dem return
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            logger.error(traceback.format_exc())
            return jsonify({
                "status": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }), 500


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
