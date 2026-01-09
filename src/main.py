"""
Haupteinstiegspunkt für die Flux Anwendung.
"""
import os
import json
import sys
import time
import logging

# Add project root to Python path for plugins/ access
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# CRITICAL: Set FFmpeg options BEFORE any cv2 imports
# This prevents HAP codec threading assertion errors
os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'threads;1'

from modules import DMXController, RestAPI, PlayerManager
from modules.player import Player
from modules.frame_source import VideoSource
from modules.cli_handler import CLIHandler
from modules.logger import FluxLogger, get_logger
from modules.default_effects import get_default_effects_manager
from modules.api_bpm import bpm_bp, set_audio_analyzer, set_sequence_manager

logger = get_logger(__name__)


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
    from modules.config_schema import validate_config_file, ConfigValidator
    
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
    # Konfiguration laden (vor Logger, um console_log_level zu erhalten)
    config = load_config()
    
    # Log-Levels aus Config lesen
    console_level_str = config.get('app', {}).get('console_log_level', 'WARNING')
    file_level_str = config.get('app', {}).get('file_log_level', 'WARNING')
    
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
    flux_logger.setup_logging(log_level=file_level, console_level=console_level)
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
    from modules.points_loader import PointsLoader
    points_data = PointsLoader.load_points(points_json_path, validate_bounds=True)
    
    # Art-Net player uses resolution from points file (LED matrix dimensions)
    artnet_canvas_width = points_data['canvas_width']
    artnet_canvas_height = points_data['canvas_height']
    
    # Initialize session state early (needed for video player settings)
    from modules.session_state import init_session_state, get_session_state
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
    
    # Art-Net Manager global initialisieren (unabhängig vom Player)
    from modules.artnet_manager import ArtNetManager
    artnet_manager = ArtNetManager(
        target_ip, 
        start_universe, 
        points_data['total_points'], 
        points_data['channels_per_universe']
    )
    artnet_config = config.get('artnet', {})
    artnet_manager.start(artnet_config)
    logger.debug(f"Art-Net gestartet: {target_ip}, Universen: {points_data['required_universes']}")
    
    # ClipRegistry initialisieren (ERST, bevor Player erstellt werden)
    from modules.clip_registry import get_clip_registry
    clip_registry = get_clip_registry()
    logger.debug("ClipRegistry initialisiert")
    
    # Video Player initialisieren (nur für Preview, KEIN Art-Net Output!)
    # Starte mit leerer DummySource - User muss Video explizit laden
    from modules.frame_source import DummySource
    video_source = DummySource(video_canvas_width, video_canvas_height)
    player = Player(video_source, points_json_path, target_ip, start_universe, fps_limit, config, 
                   enable_artnet=False, player_name="Video Player (Preview)", clip_registry=clip_registry)
    logger.debug(f"Video Player initialisiert (Preview only, kein Video geladen)")
    
    # Replay Manager global initialisieren (mit Player-Referenz)
    from modules.replay_manager import ReplayManager
    replay_manager = ReplayManager(artnet_manager, config, player)
    logger.debug("Replay Manager initialisiert")
    
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
    artnet_player.set_artnet_manager(artnet_manager)
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
    from modules.sequences import SequenceManager, AudioAnalyzer
    sequence_manager = SequenceManager(clip_registry=clip_registry)
    audio_analyzer = AudioAnalyzer(config=config)
    player_manager.sequence_manager = sequence_manager
    player_manager.audio_analyzer = audio_analyzer
    logger.debug("Parameter Sequence System initialisiert")
    
    # Connect sequence_manager to session_state for persistence
    session_state.set_sequence_manager(sequence_manager)
    logger.debug("SequenceManager connected to SessionState")
    
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
    
    # Default Effects Manager initialisieren und anwenden
    # WICHTIG: Nach Player-Initialisierung, damit PluginManager bereits geladen ist
    try:
        # Hole PluginManager vom Player (bereits initialisiert)
        plugin_manager = player.plugin_manager
        default_effects_manager = get_default_effects_manager(config, plugin_manager)
        
        # Configure ClipRegistry to auto-apply default effects
        clip_registry.set_default_effects_manager(default_effects_manager)
        
        # Apply default effects to video player
        video_applied = default_effects_manager.apply_to_player(player_manager, 'video')
        
        # Apply default effects to artnet player
        artnet_applied = default_effects_manager.apply_to_player(player_manager, 'artnet')
        
        if video_applied > 0 or artnet_applied > 0:
            logger.debug(f"✨ Default effects applied: {video_applied} video, {artnet_applied} artnet")
    except Exception as e:
        logger.warning(f"⚠️ Failed to apply default effects: {e}")
    
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
    
    # DMX-Controller initialisieren (nur für DMX-Input zuständig)
    dmx_controller = DMXController(
        player_manager, 
        listen_ip=config['artnet']['dmx_listen_ip'],
        listen_port=config['artnet']['dmx_listen_port'],
        control_universe=config['artnet']['dmx_control_universe'],
        video_base_dir=video_dir,
        scripts_dir=scripts_dir,
        config=config
    )
    dmx_controller.start()
    
    # REST API initialisieren und automatisch starten
    rest_api = RestAPI(player_manager, dmx_controller, data_dir, video_dir, config, replay_manager=replay_manager)
    
    # Register BPM API blueprint
    rest_api.app.register_blueprint(bpm_bp)
    set_audio_analyzer(audio_analyzer)
    if hasattr(player_manager, 'sequence_manager'):
        set_sequence_manager(player_manager.sequence_manager)
    logger.debug("BPM API registered")
    
    # Set socketio reference in player_manager for WebSocket events
    player_manager.socketio = rest_api.socketio
    
    # Update SequenceManager with socketio reference for real-time parameter updates
    if hasattr(player_manager, 'sequence_manager'):
        player_manager.sequence_manager.socketio = rest_api.socketio
        logger.debug("SequenceManager connected to SocketIO for real-time updates")
    
    rest_api.start(host=config['api']['host'], port=config['api']['port'])
    
    # Console Capture NICHT aktivieren - verursacht "write() before start_response" Fehler
    # Die REST API Console Log funktioniert über direkte add_log() Aufrufe
    # console_capture = ConsoleCapture(rest_api)
    # sys.stdout = console_capture
    
    # CLI Handler initialisieren
    cli_handler = CLIHandler(player_manager, dmx_controller, rest_api, video_dir, data_dir, config)
    
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
                break
        
        except KeyboardInterrupt:
            print("\n\nBeende Anwendung...")
            player.stop()
            dmx_controller.stop()
            break
        except Exception as e:
            print(f"Fehler: {e}")
            import traceback
            traceback.print_exc()
    
    dmx_controller.stop()
    print("Auf Wiedersehen!")


if __name__ == "__main__":
    main()
