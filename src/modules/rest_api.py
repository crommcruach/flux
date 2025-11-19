"""
Flask REST API mit WebSocket für Flux Steuerung
"""
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import threading
from collections import deque
from .logger import get_logger

logger = get_logger(__name__)
from .constants import (
    CONSOLE_LOG_MAX_LENGTH,
    DEFAULT_API_PORT,
    VIDEO_EXTENSIONS
)


class RestAPI:
    """REST API Server mit WebSocket für Video-Player Steuerung."""
    
    def __init__(self, player, dmx_controller, data_dir, video_dir, config=None):
        self.player = player
        self.dmx_controller = dmx_controller
        self.data_dir = data_dir
        self.video_dir = video_dir
        self.config = config or {}
        self.logger = logger  # Add logger as instance attribute
        
        # Console Log Buffer aus config oder default
        console_maxlen = self.config.get('api', {}).get('console_log_maxlen', CONSOLE_LOG_MAX_LENGTH)
        self.console_log = deque(maxlen=console_maxlen)
        
        # Flask App erstellen - static_folder muss absoluter Pfad sein
        static_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
        self.app = Flask(__name__, static_folder=static_path, static_url_path='')
        secret_key = self.config.get('api', {}).get('secret_key', 'flux_secret_key_2025')
        self.app.config['SECRET_KEY'] = secret_key
        
        # Deaktiviere Flask/Werkzeug Logger komplett um write() Konflikte zu vermeiden
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)
        log.disabled = True
        
        CORS(self.app)  # CORS für alle Routen aktivieren
        
        # Socket.IO initialisieren mit engineio_logger aus
        self.socketio = SocketIO(
            self.app, 
            cors_allowed_origins="*", 
            async_mode='threading',
            logger=False,  # Deaktiviert Socket.IO Logger
            engineio_logger=False  # Deaktiviert Engine.IO Logger (verhindert write() Fehler)
        )
        
        # Routen registrieren
        self._register_routes()
        self._register_socketio_events()
        
        self.server_thread = None
        self.status_broadcast_thread = None
        self.is_running = False
    
    def _register_routes(self):
        """Registriert alle API-Routen."""
        
        # Web-Interface
        @self.app.route('/')
        def index():
            """Serve the Bootstrap GUI."""
            return send_from_directory(self.app.static_folder, 'index.html')
        
        @self.app.route('/controls')
        def controls():
            """Serve the control panel."""
            return send_from_directory(self.app.static_folder, 'controls.html')
        
        @self.app.route('/config')
        def config_page():
            """Serve the configuration page."""
            return send_from_directory(self.app.static_folder, 'config.html')
        
        @self.app.route('/static/<path:filename>')
        def serve_static(filename):
            """Serve static files like logos, CSS, JS."""
            return send_from_directory(self.app.static_folder, filename)
        
        @self.app.route('/api/config/frontend')
        def frontend_config():
            """Liefert Frontend-Konfiguration."""
            from flask import jsonify
            return jsonify({
                "api_base": f"http://localhost:{self.config.get('api', {}).get('port', 5000)}/api",
                "websocket_url": f"http://localhost:{self.config.get('api', {}).get('port', 5000)}",
                "polling_interval": self.config.get('frontend', {}).get('polling_interval', 3000)
            })
        
        # Lade externe Route-Module
        from .api_routes import (
            register_playback_routes, 
            register_settings_routes,
            register_artnet_routes,
            register_info_routes,
            register_recording_routes,
            register_cache_routes,
            register_script_routes,
            register_console_command_routes
        )
        from .api_points import register_points_routes
        from .api_videos import register_video_routes
        from .api_console import register_console_routes
        from .api_projects import register_project_routes
        from .api_config import register_config_routes
        
        # Registriere alle Routen
        register_playback_routes(self.app, self.player)
        register_settings_routes(self.app, self.player)
        register_artnet_routes(self.app, self.player)
        register_info_routes(self.app, self.player)
        register_script_routes(self.app, self.player, self.config)
        register_recording_routes(self.app, self.player)
        register_cache_routes(self.app)
        register_points_routes(self.app, self.player, self.data_dir)
        register_video_routes(self.app, self.player, self.video_dir)
        register_console_routes(self.app, self)
        register_console_command_routes(self.app, self.player, self.dmx_controller, self, self.video_dir, self.data_dir, self.config)
        register_project_routes(self.app, self.logger)
        register_config_routes(self.app)
    
    def _register_socketio_events(self):
        """Registriert WebSocket Events."""
        
        @self.socketio.on('connect')
        def handle_connect():
            """Client verbunden."""
            try:
                self.logger.debug(f"WebSocket Client verbunden: {threading.current_thread().name}")
                try:
                    emit('status', self._get_status_data())
                except:
                    # Stiller Fehler bei emit - kann bei disconnect passieren
                    pass
            except Exception as e:
                self.logger.error(f"Fehler bei WebSocket connect: {e}")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Client getrennt."""
            try:
                # Verwende logger statt print - print kann während disconnect problematisch sein
                self.logger.debug(f"WebSocket Client getrennt: {threading.current_thread().name}")
            except:
                # Stiller Fehler - disconnect kann in ungültigem Kontext passieren
                pass
        
        @self.socketio.on('request_status')
        def handle_status_request():
            """Client fordert Status an."""
            try:
                try:
                    emit('status', self._get_status_data())
                except:
                    # Stiller Fehler bei emit - kann bei disconnect passieren
                    pass
            except Exception as e:
                self.logger.error(f"Fehler bei status request: {e}")
        
        @self.socketio.on('request_console')
        def handle_console_request(data):
            """Client fordert Console Log an."""
            lines = data.get('lines', 100) if data else 100
            log_lines = list(self.console_log)[-lines:]
            emit('console_update', {
                "log": log_lines,
                "total": len(self.console_log)
            })
    
    def _get_status_data(self):
        """Erstellt Status-Daten für WebSocket."""
        return {
            "status": self.player.status(),
            "is_playing": self.player.is_playing,
            "is_paused": self.player.is_paused,
            "current_frame": self.player.current_frame,
            "total_frames": self.player.total_frames,
            "current_loop": self.player.current_loop,
            "brightness": self.player.brightness * 100,
            "speed": self.player.speed_factor,
            "video": os.path.basename(self.player.video_path)
        }
    
    def _status_broadcast_loop(self):
        """Sendet Status-Updates an alle Clients."""
        import time
        interval = self.config.get('api', {}).get('status_broadcast_interval', 2)
        while self.is_running:
            try:
                status_data = self._get_status_data()
                self.socketio.emit('status', status_data, namespace='/')
                time.sleep(interval)
            except Exception as e:
                self.logger.debug(f"Fehler beim Status-Broadcast: {e}")
                time.sleep(interval)
    
    def add_log(self, message):
        """Fügt Nachricht zum Console Log hinzu und sendet an Clients."""
        self.console_log.append(message)
        # Broadcast an alle WebSocket Clients
        if self.is_running:
            self.socketio.emit('console_update', {
                "log": [message],
                "total": len(self.console_log),
                "append": True
            }, namespace='/')
    
    def _execute_command(self, command):
        """Führt CLI-Befehl aus und gibt Ergebnis zurück."""
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        
        # Playback
        # restart entfernt
        if cmd == "stop":
            self.player.stop()
            return "Video gestoppt"
        elif cmd == "pause":
            self.player.pause()
            return "Video pausiert"
        elif cmd == "resume":
            self.player.resume()
            return "Wiedergabe fortgesetzt"
        
        # Video Management
        elif cmd == "load":
            if args:
                try:
                    self.player.load_video(args)
                    return f"Video geladen: {args}"
                except Exception as e:
                    return f"Fehler beim Laden: {e}"
            return "Verwendung: load <pfad>"
        elif cmd == "list":
            if not os.path.exists(self.video_dir):
                return "Video-Ordner nicht gefunden"
            video_extensions = VIDEO_EXTENSIONS
            videos = []
            for root, dirs, files in os.walk(self.video_dir):
                for f in files:
                    if f.lower().endswith(video_extensions):
                        videos.append(os.path.relpath(os.path.join(root, f), self.video_dir))
            if videos:
                return f"Videos ({len(videos)}):\n" + "\n".join(f"  - {v}" for v in sorted(videos))
            return "Keine Videos gefunden"
        elif cmd == "switch":
            if args:
                try:
                    video_extensions = VIDEO_EXTENSIONS
                    videos = []
                    for root, dirs, files in os.walk(self.video_dir):
                        for f in files:
                            if f.lower().endswith(video_extensions):
                                videos.append(os.path.join(root, f))
                    matching = [v for v in videos if args.lower() in os.path.basename(v).lower()]
                    if matching:
                        self.player.load_video(matching[0])
                        return f"Video gewechselt: {os.path.basename(matching[0])}"
                    return f"Kein Video gefunden mit: {args}"
                except Exception as e:
                    return f"Fehler: {e}"
            return "Verwendung: switch <name>"
        
        # Settings
        elif cmd == "brightness":
            if args:
                self.player.set_brightness(args)
                return f"Helligkeit auf {args} gesetzt"
            return "Verwendung: brightness <0-100>"
        elif cmd == "speed":
            if args:
                self.player.set_speed(args)
                return f"Geschwindigkeit auf {args} gesetzt"
            return "Verwendung: speed <faktor>"
        elif cmd == "fps":
            if args:
                self.player.set_fps(args)
                return f"FPS auf {args} gesetzt"
            return "Verwendung: fps <wert>"
        elif cmd == "loop":
            if args:
                self.player.set_loop_limit(args)
                return f"Loop-Limit auf {args} gesetzt"
            return "Verwendung: loop <anzahl>"
        
        # Art-Net
        elif cmd == "blackout":
            self.player.blackout()
            return "Blackout aktiviert"
        elif cmd == "test":
            color = args if args else 'red'
            self.player.test_pattern(color)
            return f"Testmuster: {color}"
        elif cmd == "ip":
            if args:
                self.player.target_ip = args
                return f"Ziel-IP gesetzt: {args}\nHINWEIS: Starte Video neu f\u00fcr \u00c4nderung"
            return f"Aktuelle IP: {self.player.target_ip}"
        elif cmd == "universe":
            if args:
                try:
                    self.player.start_universe = int(args)
                    return f"Start-Universum gesetzt: {args}\nHINWEIS: Starte Video neu f\u00fcr \u00c4nderung"
                except ValueError:
                    return "Ung\u00fcltiger Wert!"
            return f"Aktuelles Start-Universum: {self.player.start_universe}"
        
        # Info
        elif cmd == "status":
            return f"Status: {self.player.status()}"
        elif cmd == "info":
            info = self.player.get_info()
            return "\n".join([f"{k}: {v}" for k, v in info.items()])
        elif cmd == "stats":
            stats = self.player.get_stats()
            if isinstance(stats, dict):
                return "\n".join([f"{k}: {v}" for k, v in stats.items()])
            return str(stats)
        
        # Cache
        elif cmd == "cache":
            from .cache_commands import execute_cache_command
            cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'cache')
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config.json')
            result = execute_cache_command(args, cache_dir, config_path)
            if result:
                return result
            if args == "fill":
                return "⚠ 'cache fill' ist nur über CLI verfügbar (dauert sehr lange)"
            return "Verwendung: cache clear | info | delete <name> | enable | disable | size"
        
        # System
        # reload entfernt
        
        # Help
        elif cmd == "help":
            return "Verfügbare Befehle: stop, pause, resume, load, list, switch, brightness, speed, fps, loop, ip, universe, blackout, test, status, info, stats, cache, help"
        
        else:
            return f"Unbekannter Befehl: {cmd}. Gib 'help' ein für alle Befehle."
    
    def start(self, host='0.0.0.0', port=5000):
        """Startet REST API & WebSocket Server."""
        if self.is_running:
            self.logger.debug("REST API läuft bereits!")
            return
        

        
        self.is_running = True
        
        # Flask/SocketIO Logging komplett deaktivieren
        import logging
        import sys
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        logging.getLogger('socketio').setLevel(logging.ERROR)
        logging.getLogger('engineio').setLevel(logging.ERROR)
        
        # Unterdrücke Flask Startup-Nachrichten
        cli = sys.modules.get('flask.cli')
        if cli is not None:
            cli.show_server_banner = lambda *args: None
        
        # Status Broadcast Thread starten
        self.status_broadcast_thread = threading.Thread(target=self._status_broadcast_loop, daemon=True)
        self.status_broadcast_thread.start()
        
        # Server Thread starten
        self.server_thread = threading.Thread(
            target=lambda: self.socketio.run(
                self.app, 
                host=host, 
                port=port, 
                debug=False, 
                use_reloader=False, 
                allow_unsafe_werkzeug=True,
                log_output=False  # Completely suppress Werkzeug output
            ),
            daemon=True
        )
        self.server_thread.start()
        print(f"REST API + WebSocket gestartet auf http://{host}:{port}")
        print(f"Web-Interface: http://localhost:{port}")
        print(f"Control Panel: http://localhost:{port}/controls")
    
    def stop(self):
        """Stoppt REST API Server."""
        self.is_running = False
        print("REST API gestoppt")
