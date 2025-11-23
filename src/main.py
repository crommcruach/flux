"""
Haupteinstiegspunkt für die Flux Anwendung.
"""
import os
import json
import sys
import time
import logging
from modules import DMXController, RestAPI, PlayerManager
from modules.player import Player
from modules.frame_source import VideoSource
from modules.cli_handler import CLIHandler
from modules.logger import FluxLogger, get_logger

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
        logger.info("Konfiguration erfolgreich geladen und validiert")
    
    return config


def main():
    """Hauptfunktion der Anwendung mit erweiteter CLI."""
    # Konfiguration laden (vor Logger, um console_log_level zu erhalten)
    config = load_config()
    
    # Console Log-Level aus Config lesen
    console_level_str = config.get('app', {}).get('console_log_level', 'WARNING')
    console_level_map = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    console_level = console_level_map.get(console_level_str.upper(), logging.WARNING)
    
    # Logging initialisieren mit Console-Level aus Config
    flux_logger = FluxLogger()
    flux_logger.setup_logging(console_level=console_level)
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
    
    # Suche nach Videos im video-Ordner (zuerst in kanal_1, dann root)
    from modules.constants import VIDEO_EXTENSIONS
    video_extensions = VIDEO_EXTENSIONS
    video_path = None
    
    # Prüfe zuerst kanal_1 Ordner
    kanal1_dir = os.path.join(video_dir, "kanal_1")
    if os.path.exists(kanal1_dir):
        videos_kanal1 = sorted([f for f in os.listdir(kanal1_dir) if f.endswith(video_extensions)])
        if videos_kanal1:
            video_path = os.path.join(kanal1_dir, videos_kanal1[0])
            print(f"Standard-Video: kanal_1/{videos_kanal1[0]}")
    
    # Fallback: Suche im Haupt-Video-Ordner
    if not video_path and os.path.exists(video_dir):
        videos_root = sorted([f for f in os.listdir(video_dir) if f.endswith(video_extensions)])
        if videos_root:
            video_path = os.path.join(video_dir, videos_root[0])
            print(f"Standard-Video: {videos_root[0]}")
    
    # Wenn gar nichts gefunden wurde
    if not video_path:
        print(f"WARNUNG: Kein Video gefunden!")
        print(f"Bitte Video in {video_dir} oder {kanal1_dir} ablegen.")
        video_path = os.path.join(video_dir, "placeholder.mp4")
    
    # Suche Punkte-JSON-Dateien
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')] if os.path.exists(data_dir) else []
    
    if json_files:
        # 1. Priorität: Konfigurierte Standard-Punkte
        default_points = config['paths'].get('default_points_json')
        if default_points and default_points in json_files:
            points_json_path = os.path.join(data_dir, default_points)
            print(f"Punkte-Liste (config): {default_points}")
        # 2. Fallback: Legacy points_json Setting
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
    canvas_width = points_data['canvas_width']
    canvas_height = points_data['canvas_height']
    
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
    logger.info(f"Art-Net gestartet: {target_ip}, Universen: {points_data['required_universes']}")
    
    # Unified Player initialisieren mit VideoSource
    video_source = VideoSource(video_path, canvas_width, canvas_height, config)
    player = Player(video_source, points_json_path, target_ip, start_universe, fps_limit, config)
    player.set_artnet_manager(artnet_manager)  # Verbinde Player mit globalem Art-Net
    logger.info(f"Player initialisiert: Source={os.path.basename(video_path)}, Points={os.path.basename(points_json_path)}")
    
    # Replay Manager global initialisieren (mit Player-Referenz)
    from modules.replay_manager import ReplayManager
    replay_manager = ReplayManager(artnet_manager, config, player)
    logger.info("Replay Manager initialisiert")
    
    # Speichere data_dir für spätere Verwendung
    player.data_dir = data_dir
    
    # Setze Standard-Werte aus Config
    player.set_brightness(config['video']['default_brightness'])
    player.set_speed(config['video']['default_speed'])
    
    # PlayerManager initialisieren (Single Source of Truth)
    player_manager = PlayerManager(player)
    logger.info("PlayerManager initialisiert")
    
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
