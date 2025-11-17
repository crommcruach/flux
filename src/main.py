"""
Haupteinstiegspunkt für die Flux Anwendung.
"""
import os
import json
import sys
import time
from modules import VideoPlayer, DMXController, RestAPI
from modules.cli_handler import CLIHandler
from modules.logger import FluxLogger, get_logger

logger = get_logger(__name__)


class ConsoleCapture:
    """Fängt print() Ausgaben ab und leitet sie an REST API Console Log weiter."""
    def __init__(self, rest_api=None):
        self.rest_api = rest_api
        self.original_stdout = sys.stdout
    
    def write(self, text):
        """Schreibt Text sowohl in Terminal als auch in Console Log."""
        self.original_stdout.write(text)
        if self.rest_api and text.strip():
            self.rest_api.add_log(text.rstrip())
    
    def flush(self):
        """Flush für stdout Kompatibilität."""
        self.original_stdout.flush()
    
    def attach(self, rest_api):
        """Bindet REST API Console an."""
        self.rest_api = rest_api


def load_config():
    """Lädt Konfiguration aus config.json."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    
    # Standardwerte falls config.json nicht existiert
    default_config = {
        "artnet": {
            "target_ip": "127.0.0.1",
            "start_universe": 0,
            "dmx_control_universe": 100,
            "dmx_listen_ip": "0.0.0.0",
            "dmx_listen_port": 6454
        },
        "video": {
            "extensions": [".mp4", ".avi", ".mov", ".mkv", ".wmv"],
            "max_per_channel": 255,
            "default_fps": None,
            "default_brightness": 100,
            "default_speed": 1.0
        },
        "paths": {
            "video_dir": "video",
            "data_dir": "data",
            "points_json": "punkte_export.json"
        }
    }
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  config.json nicht gefunden, verwende Standardwerte")
        return default_config
    except json.JSONDecodeError as e:
        print(f"⚠️  Fehler beim Lesen von config.json: {e}")
        print("Verwende Standardwerte")
        return default_config


def main():
    """Hauptfunktion der Anwendung mit erweiteter CLI."""
    # Logging initialisieren
    FluxLogger()
    logger.info("Flux startet...")
    
    # Konfiguration laden
    config = load_config()
    logger.info("Konfiguration geladen")
    
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
        # Prüfe ob default aus config existiert
        default_points = config['paths']['points_json']
        if default_points in json_files:
            points_json_path = os.path.join(data_dir, default_points)
        else:
            # Nimm erste gefundene
            points_json_path = os.path.join(data_dir, sorted(json_files)[0])
        print(f"Punkte-Liste: {os.path.basename(points_json_path)}")
    else:
        print(f"WARNUNG: Keine Punkte-Liste gefunden in {data_dir}")
        points_json_path = os.path.join(data_dir, "punkte_export.json")
    
    # Konfiguration für Art-Net
    target_ip = config['artnet']['target_ip']
    start_universe = config['artnet']['start_universe']
    fps_limit = config['video']['default_fps']
    
    # Video Player initialisieren
    player = VideoPlayer(video_path, points_json_path, target_ip, start_universe, fps_limit, config)
    logger.info(f"VideoPlayer initialisiert: Video={os.path.basename(video_path)}, Points={os.path.basename(points_json_path)}")
    
    # Speichere data_dir für spätere Verwendung
    player.data_dir = data_dir
    
    # Setze Standard-Werte aus Config
    player.set_brightness(config['video']['default_brightness'])
    player.set_speed(config['video']['default_speed'])
    
    # DMX-Controller initialisieren
    dmx_controller = DMXController(
        player, 
        listen_ip=config['artnet']['dmx_listen_ip'],
        listen_port=config['artnet']['dmx_listen_port'],
        control_universe=config['artnet']['dmx_control_universe'],
        video_base_dir=video_dir
    )
    dmx_controller.start()
    
    # REST API initialisieren und automatisch starten
    rest_api = RestAPI(player, dmx_controller, data_dir, video_dir, config)
    rest_api.start(host=config['api']['host'], port=config['api']['port'])
    
    # Console Capture aktivieren
    console_capture = ConsoleCapture(rest_api)
    sys.stdout = console_capture
    
    # CLI Handler initialisieren
    cli_handler = CLIHandler(player, dmx_controller, rest_api, video_dir, data_dir, config)
    
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
                player = new_player
                dmx_controller.player = player
                cli_handler.player = player
            
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
