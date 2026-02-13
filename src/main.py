"""
Haupteinstiegspunkt für die Flux Anwendung.
"""
import os
import json
import sys
import time
import logging
import threading
import traceback
import signal
import atexit
from datetime import datetime

# Setup crash log file BEFORE anything else
crash_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs', 'crash.log')
os.makedirs(os.path.dirname(crash_log_path), exist_ok=True)

def log_crash(message):
    """Log crash to file"""
    try:
        with open(crash_log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"CRASH at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
            f.write(message)
            f.write(f"\n{'='*80}\n\n")
            f.flush()
        print(f"🔥 CRASH logged to: {crash_log_path}")
    except Exception as e:
        print(f"Failed to write crash log: {e}")

# Global exception handler for threads
def global_exception_handler(args):
    """Catch uncaught exceptions in threads"""
    thread_name = args.thread.name if args.thread else "Unknown"
    exc_type = args.exc_type.__name__ if args.exc_type else "Unknown"
    exc_value = str(args.exc_value) if args.exc_value else "Unknown"
    
    error_msg = f"""
Thread: {thread_name}
Type: {exc_type}
Message: {exc_value}
"""
    
    if args.exc_traceback:
        error_msg += "\nTraceback:\n"
        error_msg += "".join(traceback.format_tb(args.exc_traceback))
    
    print(f"\n{'='*80}")
    print(f"🔥 UNCAUGHT EXCEPTION IN THREAD: {thread_name}")
    print(f"{'='*80}")
    print(error_msg)
    print(f"{'='*80}\n")
    
    log_crash(error_msg)
    logging.critical(f"Thread '{thread_name}' crashed: {exc_type}: {exc_value}")

# Set global thread exception handler
threading.excepthook = global_exception_handler

# Catch ALL unhandled exceptions (even in main thread)
def unhandled_exception_handler(exc_type, exc_value, exc_traceback):
    """Catch exceptions in main thread"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = f"""
Type: {exc_type.__name__}
Message: {str(exc_value)}

Traceback:
{"".join(traceback.format_tb(exc_traceback))}
"""
    
    print(f"\n{'='*80}")
    print(f"🔥 UNHANDLED EXCEPTION IN MAIN THREAD")
    print(f"{'='*80}")
    print(error_msg)
    print(f"{'='*80}\n")
    
    log_crash(error_msg)

sys.excepthook = unhandled_exception_handler

# Add project root to Python path for plugins/ access
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# CRITICAL: Set FFmpeg options BEFORE any cv2 imports
# This prevents HAP codec threading assertion errors
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'

from modules import RestAPI, PlayerManager
from modules.player.core import Player
from modules.player.sources import VideoSource
from modules.cli.handler import CLIHandler
from modules.core.logger import FluxLogger, get_logger
from modules.player.effects.defaults import get_default_effects_manager
from modules.api.audio.bpm import bpm_bp, set_audio_analyzer, set_sequence_manager

logger = get_logger(__name__)

# Global shutdown flag and cleanup resources
_shutdown_requested = False
_cleanup_resources = {}
_shutdown_confirmation_enabled = False  # Set to True in production

def register_cleanup_resource(name, cleanup_func):
    """Register a resource for cleanup on shutdown"""
    _cleanup_resources[name] = cleanup_func

def confirm_shutdown():
    """Ask user for confirmation before shutdown (production mode).
    
    Returns:
        bool: True if user confirms shutdown, False if cancelled
    """
    try:
        print("\n" + "="*80)
        print("⚠️  Shutdown requested - All Art-Net output will stop!")
        print("="*80)
        response = input("Are you sure you want to exit? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            return True
        else:
            print("✅ Shutdown cancelled - continuing operation")
            return False
    except (EOFError, KeyboardInterrupt):
        # If user presses Ctrl+C again or input fails, proceed with shutdown
        return True

def graceful_shutdown(signum=None, frame=None):
    """Gracefully shutdown all components"""
    global _shutdown_requested
    
    if _shutdown_requested:
        print("\n⚠️  Shutdown already in progress...")
        return
    
    # Ask for confirmation if enabled (production mode)
    if _shutdown_confirmation_enabled:
        if not confirm_shutdown():
            return  # User cancelled shutdown
    
    _shutdown_requested = True
    print("\n\n" + "="*80)
    print("🛑 Shutting down gracefully...")
    print("="*80)
    
    # Cleanup in reverse order of initialization (most important first)
    cleanup_order = [
        'outputs',      # Close display windows first
        'players',      # Stop playback
        'artnet',       # Send blackout to all ArtNet channels
        'rest_api',     # Stop web server
        'dmx',          # Stop DMX controller
        'session',      # Save session state
    ]
    
    import concurrent.futures
    
    for resource_name in cleanup_order:
        if resource_name in _cleanup_resources:
            try:
                print(f"  ├─ Cleaning up: {resource_name}...")
                
                # Execute cleanup with 5 second timeout
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_cleanup_resources[resource_name])
                    try:
                        future.result(timeout=5.0)
                        print(f"  ✅ {resource_name} cleaned up")
                    except concurrent.futures.TimeoutError:
                        print(f"  ⚠️  Timeout cleaning up {resource_name} (forced)")
            except Exception as e:
                print(f"  ⚠️  Error cleaning up {resource_name}: {e}")
    
    # Cleanup remaining resources
    for resource_name, cleanup_func in _cleanup_resources.items():
        if resource_name not in cleanup_order:
            try:
                print(f"  ├─ Cleaning up: {resource_name}...")
                
                # Execute cleanup with 3 second timeout
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(cleanup_func)
                    try:
                        future.result(timeout=3.0)
                        print(f"  ✅ {resource_name} cleaned up")
                    except concurrent.futures.TimeoutError:
                        print(f"  ⚠️  Timeout cleaning up {resource_name} (forced)")
            except Exception as e:
                print(f"  ⚠️  Error cleaning up {resource_name}: {e}")
    
    print("="*80)
    print("✅ Shutdown complete. Auf Wiedersehen!")
    print("="*80)
    
    # Force exit after 1 second to ensure we don't hang
    def force_exit():
        time.sleep(1.0)
        os._exit(0)
    
    exit_thread = threading.Thread(target=force_exit, daemon=True)
    exit_thread.start()
    
    # Exit cleanly
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, graceful_shutdown)   # Ctrl+C
signal.signal(signal.SIGTERM, graceful_shutdown)  # Termination request
atexit.register(lambda: graceful_shutdown() if not _shutdown_requested else None)


# Cleanup helper functions
def _cleanup_outputs(player_manager):
    """Close all output windows (display outputs)"""
    try:
        for player_id in ['video', 'artnet']:
            player = player_manager.get_player(player_id)
            if player and hasattr(player, 'output_manager') and player.output_manager:
                for output_id, output in player.output_manager.outputs.items():
                    try:
                        if hasattr(output, 'cleanup'):
                            output.cleanup()
                            logger.info(f"  └─ Output {output_id} cleaned up")
                    except Exception as e:
                        logger.warning(f"  └─ Failed to cleanup output {output_id}: {e}")
    except Exception as e:
        logger.error(f"Failed to cleanup outputs: {e}")

def _cleanup_players(player, artnet_player):
    """Stop both players"""
    try:
        player.stop()
        artnet_player.stop()
        logger.info("  └─ Players stopped")
    except Exception as e:
        logger.error(f"Failed to stop players: {e}")

def _cleanup_rest_api(rest_api):
    """Stop REST API server"""
    try:
        if hasattr(rest_api, 'stop'):
            rest_api.stop()
        logger.info("  └─ REST API stopped")
    except Exception as e:
        logger.error(f"Failed to stop REST API: {e}")

def _cleanup_session(playlist_system):
    """Save session state"""
    try:
        if playlist_system and playlist_system.active_playlist_id:
            playlist_system.capture_active_playlist_state()
            playlist_system._auto_save()
        logger.info("  └─ Session state saved")
    except Exception as e:
        logger.error(f"Failed to save session: {e}")


class ConsoleCapture:
    """Fängt print() Ausgaben ab und leitet sie an REST API Console Log weiter."""
    def __init__(self, rest_api=None):
        self.rest_api = rest_api
        self.original_stdout = sys.stdout
        self._in_request = False
    
    def write(self, text):
        """Schreibt Text sowohl in Terminal als auch in Console Log."""
        import threading
        
        # Schreibe immer ins Terminal
        try:
            self.original_stdout.write(text)
            self.original_stdout.flush()
        except:
            pass
        
        # Sende NUR zu REST API wenn:
        # 1. REST API existiert
        # 2. Text nicht leer ist
        # 3. Wir sind NICHT in einem Flask/Werkzeug Thread
        # 4. Wir sind NICHT bereits in einem Request-Kontext
        thread_name = threading.current_thread().name
        is_flask_thread = (
            'werkzeug' in thread_name.lower() or 
            'dummy' in thread_name.lower() or
            'thread' in thread_name.lower() and 'wsgi' in thread_name.lower()
        )
        
        # Prüfe ob wir in einem Flask Request Context sind
        try:
            from flask import has_request_context
            in_request = has_request_context()
        except:
            in_request = False
        
        if self.rest_api and text.strip() and not is_flask_thread and not in_request and not self._in_request:
            self._in_request = True
            try:
                self.rest_api.add_log(text.rstrip())
            except:
                # Stiller Fehler - verhindert Endlosschleife bei Problemen
                pass
            finally:
                self._in_request = False
    
    def flush(self):
        """Flush für stdout Kompatibilität."""
        self.original_stdout.flush()
    
    def attach(self, rest_api):
        """Bindet REST API Console an."""
        self.rest_api = rest_api


def load_config():
    """Lädt und validiert Konfiguration aus config.json."""
    from modules.core.config import validate_config_file, ConfigValidator
    
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    
    # Versuche Config zu laden und validieren
    is_valid, errors, config = validate_config_file(config_path)
    
    if not is_valid:
        print(f"⚠️  Config-Validierung fehlgeschlagen:")
        for error in errors:
            print(f"    - {error}")
        
        # Verwende Default-Config bei Fehler
        validator = ConfigValidator()
        config = validator.get_default_config()
        print(f"⚠️  Verwende Standard-Konfiguration")
    else:
        logger.debug("Konfiguration erfolgreich geladen und validiert")
    
    return config


def main():
    """Hauptfunktion der Anwendung mit erweiteter CLI."""
    # Heartbeat Monitor disabled (not needed for now)
    # from heartbeat_monitor import HeartbeatMonitor
    # heartbeat = HeartbeatMonitor()
    # heartbeat.start()
    
    # Konfiguration laden (vor Logger, um console_log_level zu erhalten)
    config = load_config()
    
    # Log-Levels aus Config lesen
    console_level_str = config.get('app', {}).get('console_log_level', 'WARNING')
    file_level_str = config.get('app', {}).get('file_log_level', 'WARNING')
    max_log_files = config.get('app', {}).get('max_log_files', 10)
    
    log_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    console_level = log_level_map.get(console_level_str.upper(), logging.WARNING)
    file_level = log_level_map.get(file_level_str.upper(), logging.WARNING)
    
    # Logging initialisieren mit Levels aus Config
    flux_logger = FluxLogger()
    flux_logger.setup_logging(log_level=file_level, console_level=console_level, max_log_files=max_log_files)
    logger.debug("Flux startet...")
    logger.debug("Konfiguration geladen")
    
    # Pfade
    base_path = os.path.dirname(os.path.dirname(__file__))
    video_dir = os.path.join(base_path, config['paths']['video_dir'])
    data_dir = os.path.join(base_path, config['paths']['data_dir'])
    
    # Erstelle video-Ordner falls nicht vorhanden
    if not os.path.exists(video_dir):
        os.makedirs(video_dir)
        print(f"Video-Ordner erstellt: {video_dir}")
    
    # Video-Ordner Existenz ist sichergestellt, aber kein Video wird automatisch geladen
    # User muss explizit ein Video laden (via Web-UI, API oder CLI)
    # Legacy video_path Variable wird nicht mehr verwendet (Player startet mit DummySource)
    
    # Suche Punkte-JSON-Dateien
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')] if os.path.exists(data_dir) else []
    
    if json_files:
        # 1. Priorität: Konfigurierte Standard-Punkte
        default_points = config['paths'].get('default_points_json')
        if default_points and default_points in json_files:
            points_json_path = os.path.join(data_dir, default_points)
            print(f"Punkte-Liste (config): {default_points}")
        # 2. Fallback: Old config setting
        elif config['paths']['points_json'] in json_files:
            points_json_path = os.path.join(data_dir, config['paths']['points_json'])
            print(f"Punkte-Liste: {config['paths']['points_json']}")
        # 3. Fallback: Erste gefundene
        else:
            points_json_path = os.path.join(data_dir, sorted(json_files)[0])
            print(f"Punkte-Liste: {sorted(json_files)[0]}")
    else:
        print(f"WARNUNG: Keine Punkte-Liste gefunden in {data_dir}")
        points_json_path = os.path.join(data_dir, "punkte_export.json")
    
    # Konfiguration für Art-Net
    target_ip = config['artnet']['target_ip']
    start_universe = config['artnet']['start_universe']
    fps_limit = config['video']['default_fps']
    
    # Scripts-Ordner
    scripts_dir = os.path.join(base_path, config['paths']['scripts_dir'])
    
    # Lade Points-Daten um Canvas-Dimensionen zu erhalten
    from modules.content.points import PointsLoader
    points_data = PointsLoader.load_points(points_json_path, validate_bounds=True)
    
    # Art-Net player uses resolution from points file (LED matrix dimensions)
    artnet_canvas_width = points_data['canvas_width']
    artnet_canvas_height = points_data['canvas_height']
    
    # Initialize session state early (needed for video player settings)
    from modules.session.state import init_session_state, get_session_state
    session_state_path = os.path.join(base_path, 'session_state.json')
    
    # Lösche alte Session-Daten beim Neustart
    if os.path.exists(session_state_path):
        try:
            os.remove(session_state_path)
            logger.debug("Alte Session-Daten gelöscht (Neustart)")
        except Exception as e:
            logger.warning(f"Konnte Session-Daten nicht löschen: {e}")
    
    session_state = init_session_state(session_state_path)
    logger.debug("SessionStateManager initialisiert")
    
    # Get video player resolution from session state or config (preview only)
    session_state_instance = get_session_state()
    video_settings = {}
    if session_state_instance:
        video_settings = session_state_instance._state.get('video_player_settings', {})
    
    if not video_settings:
        # Use config defaults if no session settings
        video_config = config.get('video', {}).get('player_resolution', {})
        video_settings = {
            'preset': video_config.get('preset', '1080p'),
            'custom_width': video_config.get('custom_width', 1920),
            'custom_height': video_config.get('custom_height', 1080),
            'autosize': video_config.get('autosize', 'off')
        }
    
    # Calculate video player canvas dimensions based on preset or custom
    if video_settings.get('preset') == 'custom':
        video_canvas_width = video_settings.get('custom_width', 1920)
        video_canvas_height = video_settings.get('custom_height', 1080)
    else:
        # Map preset to resolution
        preset_resolutions = {
            '720p': (1280, 720),
            '1080p': (1920, 1080),
            '1440p': (2560, 1440),
            '2160p': (3840, 2160)
        }
        video_canvas_width, video_canvas_height = preset_resolutions.get(video_settings.get('preset', '1080p'), (1920, 1080))
    
    logger.info(f"Video player resolution: {video_canvas_width}x{video_canvas_height} (preset: {video_settings.get('preset', '1080p')}, autosize: {video_settings.get('autosize', 'off')})")
    logger.info(f"Art-Net player resolution: {artnet_canvas_width}x{artnet_canvas_height} (from points file)")
    
    # ClipRegistry initialisieren (ERST, bevor Player erstellt werden)
    from modules.player.clips.registry import get_clip_registry
    clip_registry = get_clip_registry()
    logger.debug("ClipRegistry initialisiert")
    
    # Video Player initialisieren (nur für Preview, KEIN Art-Net Output!)
    # Starte mit leerer DummySource - User muss Video explizit laden
    from modules.player.sources import DummySource
    video_source = DummySource(video_canvas_width, video_canvas_height)
    player = Player(video_source, points_json_path, target_ip, start_universe, fps_limit, config, 
                   enable_artnet=False, player_name="Video Player (Preview)", clip_registry=clip_registry)
    logger.debug(f"Video Player initialisiert (Preview only, kein Video geladen)")
    
    # Replay Manager global initialisieren (mit Player-Referenz)
    # Note: artnet_manager removed - replay functionality will be reimplemented with routing_bridge
    from modules.player.recording.replay import ReplayManager
    replay_manager = ReplayManager(None, config, player)
    logger.debug("Replay Manager initialisiert (ohne Art-Net Manager)")

    
    # Speichere data_dir für spätere Verwendung
    player.data_dir = data_dir
    
    # Setze Standard-Werte aus Config
    player.set_brightness(config['video']['default_brightness'])
    player.set_speed(config['video']['default_speed'])
    
    # Art-Net Player initialisieren (separat vom Video Player)
    # Starte mit leerer DummySource - User muss Video explizit laden
    artnet_video_source = DummySource(artnet_canvas_width, artnet_canvas_height)
    artnet_player = Player(artnet_video_source, points_json_path, target_ip, start_universe, fps_limit, config,
                          enable_artnet=True, player_name="Art-Net Player", clip_registry=clip_registry)
    logger.debug(f"Art-Net Player initialisiert (kein Video geladen)")

    
    # PlayerManager initialisieren (Single Source of Truth)
    player_manager = PlayerManager(player, artnet_player)
    logger.debug("PlayerManager initialisiert mit Video Player und Art-Net Player")
    
    # Set PlayerManager reference in players (for Master/Slave sync)
    player.player_manager = player_manager
    artnet_player.player_manager = player_manager
    
    # Initialize Audio Sequencer
    player_manager.init_sequencer()
    logger.debug("Audio Sequencer initialisiert")
    
    # Initialize Dynamic Parameter Sequences
    from modules.audio.sequences import SequenceManager, AudioAnalyzer
    sequence_manager = SequenceManager(clip_registry=clip_registry)
    audio_analyzer = AudioAnalyzer(config=config)
    player_manager.sequence_manager = sequence_manager
    player_manager.audio_analyzer = audio_analyzer
    logger.debug("Parameter Sequence System initialisiert")
    
    # Connect sequence_manager to session_state for persistence
    session_state.set_sequence_manager(sequence_manager)
    logger.debug("SequenceManager connected to SessionState")
    
    # Initialize ArtNet Routing Manager
    from modules.artnet_routing.artnet_routing_manager import ArtNetRoutingManager
    artnet_routing_manager = ArtNetRoutingManager(session_state)
    logger.debug("ArtNet Routing Manager initialized")
    
    # Initialize Routing Bridge (connects OutputManager + ArtNetSender)
    from modules.artnet_routing.routing_bridge import RoutingBridge
    routing_bridge = RoutingBridge(
        routing_manager=artnet_routing_manager,
        canvas_width=video_canvas_width,
        canvas_height=video_canvas_height
    )
    logger.debug("ArtNet Routing Bridge initialized")
    
    # Connect routing bridge to Art-Net Player (NEW ArtNet output routing system)
    artnet_player.routing_bridge = routing_bridge
    logger.debug("Routing bridge connected to Art-Net Player")
    
    # Initialize Multi-Playlist System
    from modules.player.playlists.playlist_manager import MultiPlaylistSystem
    from modules.api.player.playlists import register_playlist_routes, set_playlist_system
    
    playlist_system = MultiPlaylistSystem(player_manager, session_state, None, config)
    set_playlist_system(playlist_system)
    player_manager.playlist_system = playlist_system
    
    # Always try to restore playlists from session_state.json
    try:
        if os.path.exists(session_state_path):
            with open(session_state_path, 'r', encoding='utf-8') as f:
                saved_state = json.load(f)
                playlists_data = saved_state.get('playlists', {})
                if playlists_data and isinstance(playlists_data, dict) and playlists_data.get('items'):
                    # Has playlists data - restore it
                    if playlist_system.load_from_dict(playlists_data):
                        logger.info(f"✅ Restored {len(playlist_system.playlists)} playlists from session state")
    except Exception as e:
        logger.warning(f"⚠️ Failed to restore playlists from session state: {e}")
    
    # Create default playlist only if nothing was restored
    if len(playlist_system.playlists) == 0:
        default_playlist = playlist_system.create_playlist("Default", "standard")
        playlist_system.activate_playlist(default_playlist.id)
        logger.debug("Created and activated Default playlist (first start or empty session)")
    
    logger.debug("Multi-Playlist System initialisiert")
    
    # Auto-start audio analyzer if it was running in previous session
    try:
        if os.path.exists(session_state_path):
            with open(session_state_path, 'r', encoding='utf-8') as f:
                saved_state = json.load(f)
                audio_state = saved_state.get('audio_analyzer', {})
                if audio_state.get('running', False):
                    device = audio_state.get('device')
                    if device is not None:
                        audio_analyzer.set_device(device)
                    audio_analyzer.start()
                    logger.debug(f"🎤 Audio analyzer auto-started (device={device})")
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-start audio analyzer: {e}")
    
    # Start both players to generate frames (even with DummySource for preview)
    player.start()
    artnet_player.start()
    logger.debug("Players started for preview generation")
    
    # Register cleanup for outputs (first to close display windows)
    register_cleanup_resource('outputs', lambda: _cleanup_outputs(player_manager))
    
    # Register cleanup for players
    register_cleanup_resource('players', lambda: _cleanup_players(player, artnet_player))
    
    # Default Effects Manager - Used by ClipRegistry for clip-level effects
    # IMPORTANT: Default PLAYER effects are now applied per-playlist (see playlist_manager.py)
    try:
        # Hole PluginManager vom Player (bereits initialisiert)
        plugin_manager = player.plugin_manager
        default_effects_manager = get_default_effects_manager(config, plugin_manager)
        
        # Configure ClipRegistry to auto-apply default clip effects
        clip_registry.set_default_effects_manager(default_effects_manager)
        
        # REMOVED: Default player effects now applied per-playlist when playlist is created/activated
        # This prevents duplicate effects when switching playlists
        # video_applied = default_effects_manager.apply_to_player(player_manager, 'video')
        # artnet_applied = default_effects_manager.apply_to_player(player_manager, 'artnet')
        
        logger.debug(f"✨ Default effects manager configured for clip-level effects")
    except Exception as e:
        logger.warning(f"⚠️ Failed to configure default effects manager: {e}")
    
    # Session State wird NICHT geladen beim Start (frischer Start)
    # User kann über Snapshots wiederherstellen wenn gewünscht
    logger.debug("Start mit leeren Playlists (Session State gelöscht)")
    
    # Kommentiert: Alte Session State Loading Logik - nicht mehr beim Start geladen
    # try:
    #     saved_state = session_state.load()
    #     # ... Restore Video Player state ...
    #     # ... Restore Art-Net Player state ...
    #     logger.info(f"✅ Session State geladen: {saved_state['last_updated']}")
    # except Exception as e:
    #     logger.warning(f"⚠️ Fehler beim Laden von Session State: {e}")
    
    # DMX Input Controller removed - will be reimplemented later
    # See snippets/old-dmx-input/ for archived implementation
    
    # REST API initialisieren und automatisch starten
    rest_api = RestAPI(player_manager, None, data_dir, video_dir, config, replay_manager=replay_manager)
    
    # Register unified player routes now that both rest_api and playlist_system exist
    rest_api.register_unified_player_routes(playlist_system)
    
    # Register transition routes with playlist_system
    rest_api.register_transition_routes(playlist_system)
    
    # Register BPM API blueprint
    rest_api.app.register_blueprint(bpm_bp)
    set_audio_analyzer(audio_analyzer)
    if hasattr(player_manager, 'sequence_manager'):
        set_sequence_manager(player_manager.sequence_manager)
    logger.debug("BPM API registered")
    
    # Register Multi-Playlist API routes
    register_playlist_routes(rest_api.app, player_manager, config, rest_api.socketio)
    logger.debug("Multi-Playlist API routes registered")
    
    # Register ArtNet Routing API routes
    from modules.api.api_artnet_routing import register_artnet_routing_routes
    register_artnet_routing_routes(rest_api.app, artnet_routing_manager)
    logger.debug("ArtNet Routing API routes registered")
    
    # Background Images routes registered in rest_api.py
    
    # Connect websocket to playlist system
    player_manager.playlist_system.websocket_manager = rest_api.socketio
    logger.debug("Playlist system connected to WebSocket")
    
    # Set socketio reference in player_manager for WebSocket events
    player_manager.socketio = rest_api.socketio
    
    # Update SequenceManager with socketio reference for real-time parameter updates
    if hasattr(player_manager, 'sequence_manager'):
        player_manager.sequence_manager.socketio = rest_api.socketio
        logger.debug("SequenceManager connected to SocketIO for real-time updates")
    
    rest_api.start(host=config['api']['host'], port=config['api']['port'])
    
    # Register cleanup for REST API
    register_cleanup_resource('rest_api', lambda: _cleanup_rest_api(rest_api))
    
    # Register cleanup for session state
    register_cleanup_resource('session', lambda: _cleanup_session(playlist_system))
    
    # Console Capture NICHT aktivieren - verursacht "write() before start_response" Fehler
    # Die REST API Console Log funktioniert über direkte add_log() Aufrufe
    # console_capture = ConsoleCapture(rest_api)
    # sys.stdout = console_capture
    
    # CLI Handler initialisieren
    cli_handler = CLIHandler(player_manager, None, rest_api, video_dir, data_dir, config)
    
    print("\n" + "=" * 80)
    print("Flux - Video Art-Net Controller")
    print("=" * 80)
    print("Gib 'help' ein für alle Befehle")
    print("=" * 80)
    
    # CLI-Loop
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            parts = user_input.split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1] if len(parts) > 1 else None
            
            # Führe Befehl aus
            continue_loop, new_player = cli_handler.execute_command(command, args)
            
            # Update Player wenn ersetzt
            if new_player:
                player_manager.set_player(new_player)
            
            # Exit wenn gewünscht
            if not continue_loop:
                graceful_shutdown()
                break
        
        except KeyboardInterrupt:
            graceful_shutdown()
        except Exception as e:
            print(f"Fehler: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        graceful_shutdown()
    except Exception as e:
        print("\n" + "=" * 80)
        print("FATAL ERROR - Application crashed during startup")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        print("=" * 80)
        print("\nPress Enter to exit...")
        try:
            input()
        except:
            pass
        sys.exit(1)
