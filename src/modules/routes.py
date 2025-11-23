"""
Web-Interface Routen für Flux
Enthält alle HTML-Seiten und statische Datei-Routen
"""
from flask import send_from_directory, jsonify


def register_web_routes(app, config=None, player_manager=None):
    """Registriert alle Web-Interface Routen.
    
    Args:
        app: Flask-App-Instanz
        config: Konfigurationsdictionary
        player_manager: PlayerManager-Instanz für Preview-Stream
    """
    config = config or {}
    
    # Store player_manager in app for preview route
    if player_manager:
        app.player_manager = player_manager
    
    # ========================================
    # HTML-SEITEN
    # ========================================
    
    @app.route('/')
    def index():
        """Redirect to default page based on config."""
        from flask import redirect, url_for
        default_page = config.get('frontend', {}).get('default_page', 'editor')
        
        # Map page names to route functions
        page_routes = {
            'editor': 'editor',
            'controls': 'controls',
            'cli': 'cli',
            'artnet': 'artnet',
            'config': 'config_page'
        }
        
        route_name = page_routes.get(default_page, 'editor')
        return redirect(url_for(route_name))
    
    @app.route('/editor')
    def editor():
        """Serve the main editor page."""
        return send_from_directory(app.static_folder, 'editor.html')
    
    @app.route('/controls')
    def controls():
        """Serve the control panel."""
        return send_from_directory(app.static_folder, 'controls.html')
    
    @app.route('/cli')
    def cli():
        """Serve the web CLI panel."""
        return send_from_directory(app.static_folder, 'cli.html')
    
    @app.route('/artnet')
    def artnet():
        """Serve the Art-Net control panel."""
        return send_from_directory(app.static_folder, 'artnet.html')
    
    @app.route('/config')
    def config_page():
        """Serve the configuration panel."""
        return send_from_directory(app.static_folder, 'config.html')
    
    @app.route('/effects')
    def effects():
        """Serve the effects panel."""
        return send_from_directory(app.static_folder, 'effects.html')
    
    @app.route('/fullscreen')
    def fullscreen():
        """Serve the fullscreen video page."""
        return send_from_directory(app.static_folder, 'fullscreen.html')
    
    # ========================================
    # VIDEO PREVIEW STREAM
    # ========================================
    
    @app.route('/preview')
    def preview():
        """Single-frame preview image endpoint for VIDEO player."""
        from flask import Response, current_app
        import cv2
        import numpy as np
        
        # Get player_manager from app config
        player_manager = getattr(current_app, 'player_manager', None)
        if not player_manager:
            black_frame = np.zeros((180, 320, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', black_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Use VIDEO player explicitly
        player = player_manager.get_video_player()
        if not player:
            black_frame = np.zeros((180, 320, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', black_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Get current video frame
        if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
            frame = player.last_video_frame
        elif hasattr(player, 'last_frame') and player.last_frame is not None:
            canvas_width = getattr(player, 'canvas_width', 320)
            canvas_height = getattr(player, 'canvas_height', 180)
            frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
        else:
            canvas_width = getattr(player, 'canvas_width', 320)
            canvas_height = getattr(player, 'canvas_height', 180)
            frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    @app.route('/preview/artnet')
    def preview_artnet():
        """Single-frame preview image endpoint for ART-NET player."""
        from flask import Response, current_app
        import cv2
        import numpy as np
        
        # Get player_manager from app config
        player_manager = getattr(current_app, 'player_manager', None)
        if not player_manager:
            black_frame = np.zeros((180, 320, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', black_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Use ART-NET player explicitly
        player = player_manager.get_artnet_player()
        if not player:
            black_frame = np.zeros((180, 320, 3), dtype=np.uint8)
            _, buffer = cv2.imencode('.jpg', black_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return Response(buffer.tobytes(), mimetype='image/jpeg')
        
        # Get current video frame
        if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
            frame = player.last_video_frame
        elif hasattr(player, 'last_frame') and player.last_frame is not None:
            canvas_width = getattr(player, 'canvas_width', 320)
            canvas_height = getattr(player, 'canvas_height', 180)
            frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
        else:
            canvas_width = getattr(player, 'canvas_width', 320)
            canvas_height = getattr(player, 'canvas_height', 180)
            frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
        
        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return Response(buffer.tobytes(), mimetype='image/jpeg')
    
    # ========================================
    # STATISCHE DATEIEN
    # ========================================
    
    @app.route('/static/<path:filename>')
    def serve_static(filename):
        """Serve static files like logos, CSS, JS."""
        return send_from_directory(app.static_folder, filename)
    
    # ========================================
    # FRONTEND-KONFIGURATION
    # ========================================
    
    @app.route('/api/config/frontend')
    def frontend_config():
        """Liefert Frontend-Konfiguration für JavaScript."""
        port = config.get('api', {}).get('port', 5000)
        return jsonify({
            "api_base": f"http://localhost:{port}/api",
            "websocket_url": f"http://localhost:{port}",
            "polling_interval": config.get('frontend', {}).get('polling_interval', 3000)
        })
