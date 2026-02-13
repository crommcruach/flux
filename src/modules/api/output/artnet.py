"""
API Routes - Playback, Settings, Art-Net Endpoints
"""
from flask import jsonify, request
from ...core.logger import get_logger

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
    
    @app.route('/api/fps', methods=['POST'])
    def set_fps():
        """Setzt Art-Net FPS (DEPRECATED - old system removed)."""
        return jsonify({"status": "error", "message": "Old Art-Net system removed. Use routing system instead."}), 410
    
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
        """Aktiviert Blackout (DEPRECATED - old system removed)."""
        # TODO: Reimplement with routing_bridge
        return jsonify({"status": "error", "message": "Blackout feature needs reimplementation with routing system"}), 501
    
    @app.route('/api/test', methods=['POST'])
    def test_pattern():
        """Sendet Testmuster (DEPRECATED - old system removed)."""
        # TODO: Reimplement with routing_bridge
        return jsonify({"status": "error", "message": "Test pattern feature needs reimplementation with routing system"}), 501
    
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
        """Gibt Art-Net Informationen und Statistiken zurück (DEPRECATED)."""
        # Old Art-Net system removed - return minimal info
        try:
            player = player_manager.player
            brightness = int(player.brightness * 100) if hasattr(player, 'brightness') else 100
            
            return jsonify({
                "status": "success",
                "message": "Old Art-Net system removed. Use routing API instead.",
                "artnet_brightness": brightness,
                "active_mode": "Video"
            })
        except Exception as e:
            logger.error(f"Fehler in /api/artnet/info: {str(e)}")
            return jsonify({"status": "error", "message": f"Fehler: {str(e)}"}), 500
    
    @app.route('/api/artnet/delta-encoding', methods=['POST'])
    def set_delta_encoding():
        """Aktiviert/Deaktiviert Delta-Encoding (DEPRECATED - old system removed)."""
        # Delta encoding needs to be reimplemented in new routing system
        return jsonify({
            "status": "error",
            "message": "Delta-Encoding removed with old Art-Net system. Needs reimplementation in routing system."
        }), 410


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
    
    def apply_mask_to_frame(frame, mask_config):
        """
        Apply a mask to frame (make masked region black)
        
        Args:
            frame: Input frame
            mask_config: Mask definition with shape, position, etc.
        
        Returns:
            np.ndarray: Frame with mask applied
        """
        try:
            import cv2
            import numpy as np
            
            h, w = frame.shape[:2]
            mask_shape = mask_config.get('shape', 'circle')
            
            # Create mask image (white = keep, black = remove)
            mask = np.ones((h, w), dtype=np.uint8) * 255
            
            if mask_shape == 'rectangle':
                x = int(mask_config.get('x', 0))
                y = int(mask_config.get('y', 0))
                mask_width = int(mask_config.get('width', w))
                mask_height = int(mask_config.get('height', h))
                cv2.rectangle(mask, (x, y), (x + mask_width, y + mask_height), 0, -1)
                
            elif mask_shape == 'circle':
                centerX = int(mask_config.get('centerX', w // 2))
                centerY = int(mask_config.get('centerY', h // 2))
                radius = int(mask_config.get('radius', min(w, h) // 4))
                cv2.circle(mask, (centerX, centerY), radius, 0, -1)
                
            elif mask_shape in ['polygon', 'triangle', 'freehand']:
                points = mask_config.get('points', [])
                if points and len(points) >= 3:
                    pts = np.array([[int(p.get('x', 0)), int(p.get('y', 0))] for p in points], dtype=np.int32)
                    cv2.fillPoly(mask, [pts], 0)
            
            # Apply mask
            frame_masked = cv2.bitwise_and(frame, frame, mask=mask)
            return frame_masked
            
        except Exception as e:
            logger.error(f"Failed to apply mask: {e}")
            return frame
    
    def apply_inline_slice(frame, slice_config):
        """
        Helper function to apply inline slice definition to frame
        
        Args:
            frame: Source frame (numpy array, BGR)
            slice_config: Dict with slice parameters
            
        Returns:
            np.ndarray: Sliced frame
        """
        try:
            import cv2
            import numpy as np
            
            shape = slice_config.get('shape', 'rectangle')
            x = int(slice_config.get('x', 0))
            y = int(slice_config.get('y', 0))
            width = int(slice_config.get('width', frame.shape[1]))
            height = int(slice_config.get('height', frame.shape[0]))
            rotation = slice_config.get('rotation', 0)
            transform_corners = slice_config.get('transformCorners', None)
            
            h, w = frame.shape[:2]
            
            # Check if perspective transform is needed
            if transform_corners and len(transform_corners) == 4:
                logger.debug(f"Applying perspective transform with corners: {transform_corners}")
                try:
                    # Convert transform corners to numpy array
                    src_points = np.float32([
                        [transform_corners[0]['x'], transform_corners[0]['y']],  # top-left
                        [transform_corners[1]['x'], transform_corners[1]['y']],  # top-right
                        [transform_corners[2]['x'], transform_corners[2]['y']],  # bottom-right
                        [transform_corners[3]['x'], transform_corners[3]['y']]   # bottom-left
                    ])
                    
                    # Define destination rectangle (output size)
                    dst_points = np.float32([
                        [0, 0],              # top-left
                        [width, 0],          # top-right
                        [width, height],     # bottom-right
                        [0, height]          # bottom-left
                    ])
                    
                    # Calculate perspective transform matrix
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    
                    # Apply perspective warp
                    sliced = cv2.warpPerspective(frame, matrix, (width, height))
                    logger.debug(f"Perspective transform applied successfully")
                    
                    return sliced
                except Exception as e:
                    logger.error(f"Failed to apply perspective transform: {e}")
                    # Fall through to normal slice extraction
            
            # Normal rectangular extraction
            # Clamp coordinates to frame bounds
            x1 = max(0, min(x, w))
            y1 = max(0, min(y, h))
            x2 = max(0, min(x + width, w))
            y2 = max(0, min(y + height, h))
            
            # Extract region
            sliced = frame[y1:y2, x1:x2].copy()
            
            # Resize to target dimensions if needed
            if sliced.shape[1] != width or sliced.shape[0] != height:
                sliced = cv2.resize(sliced, (width, height))
            
            # Apply rotation if specified
            if rotation != 0:
                center = (width // 2, height // 2)
                matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
                sliced = cv2.warpAffine(sliced, matrix, (width, height))
            
            # Apply masks if present
            masks = slice_config.get('masks', [])
            if masks and len(masks) > 0:
                logger.debug(f"Applying {len(masks)} mask(s) to slice")
                for mask in masks:
                    if mask.get('visible', True):
                        sliced = apply_mask_to_frame(sliced, mask)
            
            return sliced
            
        except Exception as e:
            # Return original frame on error
            return frame
    
    @app.route('/api/outputs/<player_id>/stream/<output_id>')
    def stream_output(player_id, output_id):
        """
        MJPEG stream for any output (generalized streaming endpoint)
        
        Args:
            player_id: Player identifier (e.g., 'video', 'artnet')
            output_id: Output identifier from OutputManager
        
        Query Parameters:
            fps: Stream FPS (default: 25)
            quality: JPEG quality 0-100 (default: 85)
            max_width: Max width scaling (default: 640, 0=no scaling)
        """
        from flask import Response, request
        import cv2
        import numpy as np
        import time
        
        # Get query parameters
        stream_fps = int(request.args.get('fps', 25))
        jpeg_quality = int(request.args.get('quality', 85))
        max_width = int(request.args.get('max_width', 640))
        frame_delay = 1.0 / stream_fps if stream_fps > 0 else 0.04
        
        def generate_frames():
            """Generator for MJPEG stream"""
            while True:
                try:
                    # Get player
                    player = player_manager.get_player(player_id)
                    
                    if not player or not hasattr(player, 'output_manager') or not player.output_manager:
                        # Black frame if player or output manager not found
                        frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    else:
                        # Get output
                        output = player.output_manager.outputs.get(output_id)
                        
                        if not output or not output.enabled:
                            # Black frame if output not found or disabled
                            frame = np.zeros((180, 320, 3), dtype=np.uint8)
                        else:
                            # Get latest frame from output
                            frame = output.get_latest_frame()
                            
                            if frame is None:
                                # Black frame if no frame available yet
                                frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    
                    # Scale if needed
                    if max_width > 0 and frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Encode as JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, 
                                              [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    if not ret:
                        time.sleep(frame_delay)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           frame_bytes + b'\r\n')
                    
                    time.sleep(frame_delay)
                
                except Exception as e:
                    logger.error(f"Stream error for {player_id}/{output_id}: {e}")
                    # Black frame on error
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               frame_bytes + b'\r\n')
                    time.sleep(0.1)
        
        return Response(generate_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/outputs/<player_id>/stream/preview_live')
    def stream_preview_player(player_id):
        """
        MJPEG stream for preview players (non-active playlist preview)
        
        Args:
            player_id: 'video' or 'artnet' (preview player automatically selected)
        
        Query Parameters:
            fps: Stream FPS (default: 15)
            quality: JPEG quality 0-100 (default: 80)
            max_width: Max width scaling (default: 640)
        """
        from flask import Response, request
        import cv2
        import numpy as np
        import time
        
        # Get query parameters (lower defaults for preview)
        stream_fps = int(request.args.get('fps', 15))
        jpeg_quality = int(request.args.get('quality', 80))
        max_width = int(request.args.get('max_width', 640))
        frame_delay = 1.0 / stream_fps if stream_fps > 0 else 0.066
        
        def generate_preview_frames():
            """Generator for preview player MJPEG stream"""
            while True:
                try:
                    # Get preview player
                    preview_player_id = f"{player_id}_preview"
                    preview_player = player_manager.get_player(preview_player_id)
                    
                    if not preview_player:
                        # Black frame with text if preview player not found
                        frame = np.zeros((180, 320, 3), dtype=np.uint8)
                        cv2.putText(frame, "Preview not active", (10, 90),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    else:
                        # Get last video frame from preview player
                        if player_id == 'video':
                            frame = preview_player.last_video_frame
                        else:  # artnet
                            frame = preview_player.last_video_frame
                        
                        if frame is None:
                            # Black frame if no frame available yet
                            frame = np.zeros((180, 320, 3), dtype=np.uint8)
                            cv2.putText(frame, "Loading preview...", (10, 90),
                                      cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    # Scale if needed
                    if max_width > 0 and frame.shape[1] > max_width:
                        scale = max_width / frame.shape[1]
                        new_width = int(frame.shape[1] * scale)
                        new_height = int(frame.shape[0] * scale)
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    # Encode as JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, 
                                              [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                    if not ret:
                        time.sleep(frame_delay)
                        continue
                    
                    frame_bytes = buffer.tobytes()
                    
                    # MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + 
                           frame_bytes + b'\r\n')
                    
                    time.sleep(frame_delay)
                
                except Exception as e:
                    logger.error(f"Preview stream error for {player_id}: {e}")
                    # Black frame on error
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + 
                               frame_bytes + b'\r\n')
                    time.sleep(0.1)
        
        return Response(generate_preview_frames(), 
                       mimetype='multipart/x-mixed-replace; boundary=frame')
    
    @app.route('/api/preview/stream')
    def preview_stream():
        """MJPEG Video-Stream des aktuellen Frames mit optionalem Slice-Parameter."""
        from flask import Response, request
        import cv2
        import numpy as np
        import time
        import json
        
        # Get optional slice parameter from query string
        slice_param = request.args.get('slice', None)
        slice_config = None
        
        if slice_param:
            try:
                # Try to parse as JSON (inline slice definition)
                slice_config = json.loads(slice_param)
            except:
                # If not JSON, treat as slice ID (string)
                slice_config = slice_param
        
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
                    
                    # Check if player exists and is initialized
                    if player is None:
                        frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    # Hole aktuelles Video-Frame (komplettes Bild)
                    elif hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                        # Verwende komplettes Video-Frame (bereits in BGR) - MAKE A COPY to avoid race conditions
                        try:
                            frame = player.last_video_frame.copy()
                        except:
                            # If copy fails, create black frame
                            canvas_width = getattr(player, 'canvas_width', 320)
                            canvas_height = getattr(player, 'canvas_height', 180)
                            frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
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
                    
                    # Apply slice if configured
                    if slice_config is not None:
                        if isinstance(slice_config, dict):
                            # Inline slice definition - apply directly
                            frame = apply_inline_slice(frame, slice_config)
                        elif player and hasattr(player, 'output_manager') and player.output_manager:
                            # Slice ID - use output manager's slice manager
                            if hasattr(player.output_manager, 'slice_manager'):
                                frame = player.output_manager.slice_manager.get_slice(slice_config, frame)
                    
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
                    # Bei Fehler: Schwarzes Bild mit aktueller Player-Auflösung
                    player = player_manager.player
                    error_width = getattr(player, 'canvas_width', 320)
                    error_height = getattr(player, 'canvas_height', 180)
                    frame = np.zeros((error_height, error_width, 3), dtype=np.uint8)
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
        # from .script_generator import ScriptGenerator  # Deprecated - using plugin system
        return jsonify({'scripts': [], 'error': 'Script system deprecated, use generators plugin'})
        
        return jsonify({
            "status": "success",
            "scripts": scripts,
            "count": len(scripts)
        })
    
    # ScriptSource removed - use GeneratorSource with generator plugins instead
    
    @app.route('/api/load_generator', methods=['POST'])
    def load_generator():
        """Lädt und startet einen Generator."""
        from ...core.logger import get_logger
        
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
    # Note: dmx_controller parameter deprecated - DMX input removed
    
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
