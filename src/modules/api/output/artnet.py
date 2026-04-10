"""
API Routes - Playback, Settings, Art-Net Endpoints

⚠️⚠️⚠️ DEPRECATED FILE - SCHEDULED FOR REMOVAL ⚠️⚠️⚠️
   
   DO NOT ADD ANY NEW ROUTES OR FUNCTIONS TO THIS FILE!
   
   This file contains legacy routes that are being migrated to their proper locations:
   - Playback routes → api/player/playback.py (Unified Player API)
   - Settings routes → api/player/settings.py
   - Background routes → api/content/backgrounds.py
   - Cache routes → api/system/cache.py
   - Console routes → api/system/console.py
   
   This file will be completely removed once migration is complete.
   Any new functionality should be added to the appropriate module above.
"""
from flask import jsonify, request
from ...core.logger import get_logger

logger = get_logger(__name__)


def register_reload_route(app):
    """Registriert Application Reload Endpunkt."""
    
    @app.route('/api/reload', methods=['POST'])
    def reload_application():
        """Startet die gesamte Anwendung neu."""
        import os
        import sys
        import threading
        import subprocess
        from modules.core.logger import get_logger
        
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
    
    @app.route('/api/loop', methods=['POST'])
    def set_loop():
        """Setzt Loop-Limit."""
        player = player_manager.player
        data = request.get_json()
        value = data.get('value', 0)
        player.set_loop_limit(value)
        return jsonify({"status": "success", "loop_limit": player.max_loops})


def register_artnet_routes(app, player_manager):
    """Registriert Art-Net Endpunkte (aktive Routen)."""
    
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


def register_info_routes(app, player_manager, api=None, config=None):
    """Registriert Info-Endpunkte."""
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """Gibt aktuellen Status zurück."""
        player = player_manager.player
        
        # Collect routing outputs (NEW - for routing system DMX monitor)
        routing_outputs = {}
        artnet_source = player_manager.artnet_player if hasattr(player_manager, 'artnet_player') and player_manager.artnet_player else player
        if hasattr(artnet_source, 'routing_bridge') and artnet_source.routing_bridge:
            try:
                last_frames = artnet_source.routing_bridge.get_last_frames()
                for output_id, dmx_data in last_frames.items():
                    if dmx_data and len(dmx_data) > 0:
                        # Convert bytes to list for JSON serialization
                        routing_outputs[output_id] = list(dmx_data)
            except Exception:
                pass  # Silently fail if routing bridge not available
        
        return jsonify({
            "status": player.status(),
            "is_playing": player.is_playing,
            "is_paused": player.is_paused,
            "current_loop": player.current_loop,
            "routing_outputs": routing_outputs
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
        import time

        cfg = config if config else {}
        preview_config = cfg.get('video', {}).get('preview_stream', {}).get('video', {})
        stream_fps = preview_config.get('fps', 30)
        frame_delay = 1.0 / stream_fps
        
        def generate_frames():
            """Generator für MJPEG-Stream."""
            _player = player_manager.player
            if _player and hasattr(_player, '_mjpeg_subscriber_count'):
                _player._mjpeg_subscriber_count += 1
            try:
                while True:
                    player = player_manager.player
                    frame_bytes = getattr(player, 'last_preview_jpeg', None) if player else None
                    if frame_bytes is not None:
                        api.stream_traffic['preview']['bytes'] += len(frame_bytes)
                        api.stream_traffic['preview']['frames'] += 1
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(frame_delay)
            finally:
                if _player and hasattr(_player, '_mjpeg_subscriber_count'):
                    _player._mjpeg_subscriber_count = max(0, _player._mjpeg_subscriber_count - 1)

        return Response(generate_frames(),
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/preview/artnet/stream')
    def preview_artnet_stream():
        """MJPEG Stream des Art-Net Players."""
        from flask import Response
        import time

        cfg = config if config else {}
        preview_config = cfg.get('video', {}).get('preview_stream', {}).get('artnet', {})
        stream_fps = preview_config.get('fps', 30)
        frame_delay = 1.0 / stream_fps
        
        def generate_frames():
            """Generator für Art-Net Player MJPEG-Stream."""
            _player = player_manager.artnet_player
            if _player and hasattr(_player, '_mjpeg_subscriber_count'):
                _player._mjpeg_subscriber_count += 1
            try:
                while True:
                    player = player_manager.artnet_player
                    frame_bytes = getattr(player, 'last_preview_jpeg', None) if player else None
                    if frame_bytes is not None:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                    time.sleep(frame_delay)
            finally:
                if _player and hasattr(_player, '_mjpeg_subscriber_count'):
                    _player._mjpeg_subscriber_count = max(0, _player._mjpeg_subscriber_count - 1)

        return Response(generate_frames(),
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/fullscreen/stream')
    def fullscreen_stream():
        """MJPEG Video-Stream in voller Player-Auflösung (ohne Skalierung)."""
        from flask import Response, request
        import time

        # Get player type from query parameter (video or artnet)
        player_type = request.args.get('player', 'video')

        cfg = config if config else {}
        fullscreen_config = cfg.get('video', {}).get('preview_stream', {}).get('fullscreen', {})
        stream_fps = fullscreen_config.get('fps', 60)
        frame_delay = 1.0 / stream_fps
        
        def generate_frames():
            """Generator für MJPEG-Stream ohne Preview-Skalierung."""
            _player = player_manager.artnet_player if player_type == 'artnet' else player_manager.player
            # Signal the player that a fullscreen subscriber is active so the
            # GPU fullscreen downscaler starts encoding (triple-buffer ring).
            if _player and hasattr(_player, '_fullscreen_subscriber_count'):
                _player._fullscreen_subscriber_count += 1
            try:
                while True:
                    try:
                        player = player_manager.artnet_player if player_type == 'artnet' else player_manager.player

                        # Fast path: GPU downscaler pre-encoded the JPEG on the
                        # player thread via the triple-buffer ring — no CPU download.
                        frame_bytes = getattr(player, 'last_fullscreen_jpeg', None) if player else None

                        if frame_bytes is not None:
                            api.stream_traffic['fullscreen']['bytes'] += len(frame_bytes)
                            api.stream_traffic['fullscreen']['frames'] += 1
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                        time.sleep(frame_delay)

                    except Exception as e:
                        logger.debug('fullscreen_stream error: %s', e)
                        time.sleep(0.1)

            finally:
                if _player and hasattr(_player, '_fullscreen_subscriber_count'):
                    _player._fullscreen_subscriber_count = max(
                        0, _player._fullscreen_subscriber_count - 1)

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


def register_console_command_routes(app, player, rest_api, video_dir, data_dir, config):
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
                from ...core.utils import print_help
                
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
                    
                    cli_handler = CLIHandler(player, None, rest_api, video_dir, data_dir, config)
                    continue_loop, new_player = cli_handler.execute_command(command, args)
                    result_container['continue_loop'] = continue_loop
                    result_container['new_player'] = new_player
                except Exception as e:
                    import traceback
                    from ...core.logger import get_logger
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
            
            # Update player reference wenn ersetzt
            # Note: dmx_controller removed - player update handled by PlayerManager
            
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
                from ...core.logger import get_logger
                logger = get_logger(__name__)
                logger.error(f"Console command error: {e}\n{error_trace}")
            except:
                pass
            
            return jsonify({
                "status": "error",
                "message": str(e),
                "traceback": error_trace
            }), 500


def register_background_routes(app):
    """Registriert Background Image Upload/Serve Endpunkte."""
    from pathlib import Path
    from flask import send_from_directory
    import re
    
    # Background folder at project root
    BACKGROUNDS_DIR = Path.cwd() / 'backgrounds'
    BACKGROUNDS_DIR.mkdir(exist_ok=True)
    
    @app.route('/api/backgrounds/upload', methods=['POST'])
    def upload_background():
        """Upload background image for canvas editor"""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            # Validate image extension
            allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
            if not file.filename.lower().endswith(allowed_extensions):
                return jsonify({
                    'success': False,
                    'error': 'Invalid file type. Allowed: PNG, JPG, GIF, BMP'
                }), 400
            
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
            
            # Save file
            file_path = BACKGROUNDS_DIR / safe_filename
            file.save(str(file_path))
            
            # Return relative path
            relative_path = f"backgrounds/{safe_filename}"
            
            logger.info(f"Background uploaded: {relative_path}")
            
            return jsonify({
                'success': True,
                'path': relative_path,
                'filename': safe_filename
            })
        
        except Exception as e:
            logger.error(f"Error uploading background: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/backgrounds/<path:filename>', methods=['GET'])
    def serve_background(filename):
        """Serve background images"""
        try:
            return send_from_directory(BACKGROUNDS_DIR, filename)
        except Exception as e:
            logger.error(f"Error serving background: {e}")
            return jsonify({'error': 'File not found'}), 404


# =============================================================================
# REMOVED/DEPRECATED ROUTES - HISTORY & DOCUMENTATION
# =============================================================================
#
# The following routes have been removed as no external tools depend on them.
# Frontend has been migrated to the new unified player API.
#
# REMOVED LEGACY PLAYBACK ROUTES (Replaced by Unified Player API):
#   /api/play        → Use /api/player/<player_id>/play
#   /api/stop        → Use /api/player/<player_id>/stop  
#   /api/pause       → Use /api/player/<player_id>/pause
#   /api/resume      → Use /api/player/<player_id>/resume
#   /api/restart     → Use /api/player/<player_id>/restart
#   Location: New routes in api/player/playback.py
#   Removed: 2026-03-03
#
# REMOVED OLD ART-NET ROUTES (Replaced by Routing System):
#   /api/fps                      → Use routing configuration
#   /api/blackout                 → Use routing system blackout
#   /api/test                     → Use routing system test patterns  
#   /api/artnet/info              → Use /api/status or routing API
#   /api/artnet/delta-encoding    → Needs reimplementation in routing
#   Location: New routes in api/output/routing.py
#   Removed: 2026-03-03
#
# REMOVED SCRIPT ROUTES (Replaced by Plugin System):
#   /api/scripts                  → Use generator plugins
#   /api/load_generator           → Use web UI Sources tab
#   Location: Plugin system in api/content/plugins.py
#   Removed: 2026-03-03
#
# REMOVED FEATURES (Complete Removal):
#   - Recording System: Will be reimplemented with routing system
#   - DMX Input Controller: Replaced by other control mechanisms
#   - Benchmark Module: Removed completely
#
# =============================================================================
