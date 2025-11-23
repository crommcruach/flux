"""
Web-Interface Routen für Flux
Enthält alle HTML-Seiten und statische Datei-Routen
"""
from flask import send_from_directory, jsonify


def register_web_routes(app, config=None):
    """Registriert alle Web-Interface Routen.
    
    Args:
        app: Flask-App-Instanz
        config: Konfigurationsdictionary
    """
    config = config or {}
    
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
