"""
CLI Command Handler - Zentrale Verarbeitung aller CLI-Befehle
"""
import os
import sys
import time
import json
from .constants import VIDEO_EXTENSIONS, AFFIRMATIVE_RESPONSES


class CLIHandler:
    """Verarbeitet CLI-Befehle und delegiert an entsprechende Komponenten."""
    
    def __init__(self, player, dmx_controller, rest_api, video_dir, data_dir, config):
        self.player = player
        self.dmx_controller = dmx_controller
        self.rest_api = rest_api
        self.video_dir = video_dir
        self.data_dir = data_dir
        self.config = config
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Tracking für next/back Navigation
        self.current_video_path = None
        self.current_script_name = None
        self.video_list_cache = None
        self.script_list_cache = None
    
    def execute_command(self, command, args=None):
        """
        Führt einen CLI-Befehl aus.
        
        Args:
            command: Befehlsname (lowercase)
            args: Optionale Argumente als String
            
        Returns:
            tuple: (continue_loop, new_player) - continue_loop=False bei Exit, new_player wenn Player ersetzt wurde
        """
        # Playback-Befehle
        if command == "start":
            self.player.start()
        
        elif command == "restart":
            self.player.restart()
            
        elif command == "stop":
            self.player.stop()
            
        elif command == "pause":
            self.player.pause()
            
        elif command == "resume":
            self.player.resume()
        
        elif command == "next":
            return self._handle_next()
        
        elif command == "back":
            return self._handle_back()
        
        # Video-Verwaltung
        elif command == "videos":
            self._handle_videos_list()
            
        elif command.startswith("video:"):
            return self._handle_video_load(command)
        
        # REST API
        elif command == "api":
            self._handle_api(args)
        
        # Punkte-Verwaltung
        elif command == "points":
            new_player = self._handle_points(args)
            if new_player:
                return (True, new_player)
        
        # Einstellungen
        elif command == "fps":
            self._handle_fps(args)
            
        elif command == "speed":
            self._handle_speed(args)
            
        elif command == "brightness":
            self._handle_brightness(args)
            
        elif command == "loop":
            self._handle_loop(args)
        
        # Art-Net
        elif command == "blackout":
            self.player.blackout()
            
        elif command == "test":
            self._handle_test(args)
            
        elif command == "ip":
            self._handle_ip(args)
            
        elif command == "universe":
            self._handle_universe(args)
        
        elif command == "artnet":
            self._handle_artnet(args)
        
        # Info
        elif command == "status":
            self._handle_status()
            
        elif command == "info":
            self._handle_info()
            
        elif command == "stats":
            self._handle_stats()
        
        # Recording
        elif command == "record":
            self._handle_record(args)
        
        # Cache
        elif command == "cache":
            self._handle_cache(args)
        
        # Scripts
        elif command == "scripts":
            self._handle_scripts(args)
            
        elif command.startswith("script:"):
            return self._handle_load_script(command)
        
        # System
        elif command == "help":
            self._handle_help()
        
        elif command == "browser":
            self._handle_open()
            
        elif command in ["exit", "quit"]:
            return (False, None)
        
        else:
            print(f"Unbekannter Befehl: {command}")
            print("Gib 'help' ein für alle Befehle")
        
        return (True, None)
    
    # === Video-Verwaltung ===
    
    def _handle_videos_list(self):
        """Listet alle Videos auf."""
        from .utils import list_videos
        list_videos(self.video_dir)
    
    def _handle_video_load(self, command):
        """Lädt und startet ein Video."""
        # Extrahiere Video-Namen
        video_name = command.split(':', 1)[1].strip()
        
        if not video_name:
            print("Verwendung: video:<name>")
            return (True, None)
        
        # Sammle alle Videos
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    videos.append(os.path.join(root, f))
        
        # Normalisiere Suchstring (erlaube beide Slash-Arten)
        search_name = video_name.lower().replace('/', '\\')
        
        # Suche nach passendem Video - prüfe sowohl Dateiname als auch relativen Pfad
        matching = []
        for v in videos:
            rel_path = os.path.relpath(v, self.video_dir).lower()
            basename = os.path.basename(v).lower()
            if search_name in rel_path or search_name in basename:
                matching.append(v)
        
        if not matching:
            print(f"Kein Video gefunden mit: {video_name}")
            return (True, None)
        
        if len(matching) > 1:
            print(f"Mehrere Videos gefunden:")
            for v in matching:
                # Zeige relativen Pfad zum video_dir für bessere Übersicht
                rel_path = os.path.relpath(v, self.video_dir)
                print(f"  - {rel_path}")
            print("Bitte spezifischer wählen (z.B. 'video:kanal_1/test' oder kompletter Pfad).")
            return (True, None)
        
        # Stoppe aktuellen Player
        if self.player.is_playing:
            self.player.stop()
            time.sleep(0.5)
        
        # Prüfe ob aktueller Player ein VideoPlayer ist
        from .video_player import VideoPlayer
        from .script_player import ScriptPlayer
        
        if isinstance(self.player, ScriptPlayer):
            # Erstelle neuen VideoPlayer
            new_player = VideoPlayer(
                matching[0],
                self.player.points_json_path,
                self.player.target_ip,
                self.player.start_universe,
                self.player.fps_limit,
                self.config
            )
            
            # Übernehme Einstellungen
            new_player.brightness = self.player.brightness
            new_player.speed_factor = self.player.speed_factor
            
            # Starte Video
            new_player.start()
            
            # Tracking
            self.current_video_path = matching[0]
            self.current_script_name = None
            
            return (True, new_player)
        else:
            # Normales Video laden
            if self.player.load_video(matching[0]):
                self.current_video_path = matching[0]
                self.current_script_name = None
                self.player.start()
        
        return (True, None)
    
    def _get_all_videos(self):
        """Sammelt alle Videos sortiert."""
        if self.video_list_cache:
            return self.video_list_cache
        
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    videos.append(os.path.join(root, f))
        
        self.video_list_cache = sorted(videos)
        return self.video_list_cache
    
    def _get_all_scripts(self):
        """Sammelt alle Scripts sortiert."""
        if self.script_list_cache:
            return self.script_list_cache
        
        from .script_generator import ScriptGenerator
        scripts_dir = self.config['paths']['scripts_dir']
        script_gen = ScriptGenerator(scripts_dir)
        scripts = script_gen.list_scripts()
        
        self.script_list_cache = [s['filename'] for s in scripts]
        return self.script_list_cache
    
    def _handle_next(self):
        """Lädt nächstes Video oder Script."""
        # Prüfe ob Video oder Script aktiv
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                print("Keine Videos verfügbar")
                return (True, None)
            
            try:
                current_idx = videos.index(self.current_video_path)
                next_idx = (current_idx + 1) % len(videos)
                next_video = videos[next_idx]
                
                # Stoppe aktuelles Video
                if self.player.is_playing:
                    self.player.stop()
                    time.sleep(0.5)
                
                # Lade nächstes Video
                if self.player.load_video(next_video):
                    self.current_video_path = next_video
                    self.player.start()
                    print(f"Nächstes Video: {os.path.basename(next_video)}")
            except ValueError:
                print("Aktuelles Video nicht in Liste gefunden")
        
        elif self.current_script_name:
            scripts = self._get_all_scripts()
            if not scripts:
                print("Keine Scripts verfügbar")
                return (True, None)
            
            try:
                current_idx = scripts.index(self.current_script_name)
                next_idx = (current_idx + 1) % len(scripts)
                next_script = scripts[next_idx]
                
                # Lade nächstes Script
                return self._handle_load_script(f"script:{next_script.replace('.py', '')}")
            except ValueError:
                print("Aktuelles Script nicht in Liste gefunden")
        else:
            print("Kein Video oder Script aktiv")
        
        return (True, None)
    
    def _handle_back(self):
        """Lädt vorheriges Video oder Script."""
        # Prüfe ob Video oder Script aktiv
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                print("Keine Videos verfügbar")
                return (True, None)
            
            try:
                current_idx = videos.index(self.current_video_path)
                prev_idx = (current_idx - 1) % len(videos)
                prev_video = videos[prev_idx]
                
                # Stoppe aktuelles Video
                if self.player.is_playing:
                    self.player.stop()
                    time.sleep(0.5)
                
                # Lade vorheriges Video
                if self.player.load_video(prev_video):
                    self.current_video_path = prev_video
                    self.player.start()
                    print(f"Vorheriges Video: {os.path.basename(prev_video)}")
            except ValueError:
                print("Aktuelles Video nicht in Liste gefunden")
        
        elif self.current_script_name:
            scripts = self._get_all_scripts()
            if not scripts:
                print("Keine Scripts verfügbar")
                return (True, None)
            
            try:
                current_idx = scripts.index(self.current_script_name)
                prev_idx = (current_idx - 1) % len(scripts)
                prev_script = scripts[prev_idx]
                
                # Lade vorheriges Script
                return self._handle_load_script(f"script:{prev_script.replace('.py', '')}")
            except ValueError:
                print("Aktuelles Script nicht in Liste gefunden")
        else:
            print("Kein Video oder Script aktiv")
        
        return (True, None)
    
    # === REST API ===
    
    def _handle_api(self, args):
        """Steuert REST API."""
        if not args:
            print("Verwendung: api start [port] | api stop")
            return
        
        if args == "start":
            parts = args.split()
            port = int(parts[1]) if len(parts) > 1 else self.config['api']['port']
            self.rest_api.start(port=port)
        elif args == "stop":
            self.rest_api.stop()
        else:
            print("Verwendung: api start [port] | api stop")
    
    # === Punkte-Verwaltung ===
    
    def _handle_points(self, args):
        """Verwaltet Punkte-Listen."""
        from .utils import list_points_files
        from .validator import validate_points_file
        from .video_player import VideoPlayer
        
        if args == "list":
            list_points_files(self.data_dir)
            return None
        
        elif args and args.startswith("validate"):
            self._handle_points_validate(args)
            return None
        
        elif args and args.startswith("switch"):
            return self._handle_points_switch(args)
        
        elif args == "reload":
            return self._handle_points_reload()
        
        else:
            print("Verwendung: points list | points validate [name] | points switch <name> | points reload")
            return None
    
    def _handle_points_validate(self, args):
        """Validiert eine Punkte-Liste."""
        from .validator import validate_points_file
        
        parts = args.split(maxsplit=1)
        if len(parts) > 1:
            search_name = parts[1]
            json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
            matching = [f for f in json_files if search_name.lower() in f.lower()]
            if matching:
                file_path = os.path.join(self.data_dir, matching[0])
                print(f"\nValidiere: {matching[0]}")
                is_valid, message, errors, data = validate_points_file(file_path)
                
                if is_valid:
                    print(f"✓ {message}")
                else:
                    print(f"✗ {message}")
                    if errors:
                        print("\nFehler:")
                        for error in errors:
                            print(f"  • {error}")
            else:
                print(f"Keine Punkte-Liste gefunden mit: {search_name}")
        else:
            # Validiere aktuelle Liste
            print(f"\nValidiere: {os.path.basename(self.player.points_json_path)}")
            is_valid, message, errors, data = validate_points_file(self.player.points_json_path)
            
            if is_valid:
                print(f"✓ {message}")
            else:
                print(f"✗ {message}")
                if errors:
                    print("\nFehler:")
                    for error in errors:
                        print(f"  • {error}")
    
    def _handle_points_switch(self, args):
        """Wechselt Punkte-Liste."""
        from .video_player import VideoPlayer
        
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Verwendung: points switch <name>")
            return None
        
        search_name = parts[1]
        json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        matching = [f for f in json_files if search_name.lower() in f.lower()]
        
        if not matching:
            print(f"Keine Punkte-Liste gefunden mit: {search_name}")
            return None
        
        new_points_path = os.path.join(self.data_dir, matching[0])
        was_playing = self.player.is_playing
        if was_playing:
            self.player.stop()
        
        try:
            new_player = VideoPlayer(
                self.player.video_path, 
                new_points_path,
                self.player.target_ip, 
                self.player.start_universe, 
                self.player.fps_limit,
                self.config
            )
            new_player.brightness = self.player.brightness
            new_player.speed_factor = self.player.speed_factor
            new_player.max_loops = self.player.max_loops
            
            print(f"✓ Punkte-Liste gewechselt: {matching[0]}")
            print(f"  Anzahl Punkte: {new_player.total_points}")
            print(f"  Benötigte Universen: {new_player.required_universes}")
            
            if was_playing:
                new_player.start()
            
            return new_player
        except Exception as e:
            print(f"Fehler beim Laden der Punkte-Liste: {e}")
            return None
    
    def _handle_points_reload(self):
        """Lädt aktuelle Punkte-Liste neu."""
        from .video_player import VideoPlayer
        
        was_playing = self.player.is_playing
        current_points_path = self.player.points_json_path
        if was_playing:
            self.player.stop()
        
        try:
            new_player = VideoPlayer(
                self.player.video_path, 
                current_points_path,
                self.player.target_ip, 
                self.player.start_universe, 
                self.player.fps_limit,
                self.config
            )
            new_player.brightness = self.player.brightness
            new_player.speed_factor = self.player.speed_factor
            new_player.max_loops = self.player.max_loops
            
            print(f"✓ Punkte-Liste neu geladen: {os.path.basename(current_points_path)}")
            print(f"  Anzahl Punkte: {new_player.total_points}")
            print(f"  Benötigte Universen: {new_player.required_universes}")
            
            if was_playing:
                new_player.start()
            
            return new_player
        except Exception as e:
            print(f"Fehler beim Neuladen der Punkte-Liste: {e}")
            return None
    
    # === Einstellungen ===
    
    def _handle_fps(self, args):
        """Setzt FPS."""
        if args:
            self.player.set_fps(args)
        else:
            print("Verwendung: fps <wert>")
    
    def _handle_speed(self, args):
        """Setzt Geschwindigkeit."""
        if args:
            self.player.set_speed(args)
        else:
            print("Verwendung: speed <faktor>")
    
    def _handle_brightness(self, args):
        """Setzt Helligkeit."""
        if args:
            self.player.set_brightness(args)
        else:
            print("Verwendung: brightness <0-100>")
    
    def _handle_loop(self, args):
        """Setzt Loop-Limit."""
        if args:
            try:
                limit = int(args)
                self.player.set_loop_limit(limit)
                print(f"Loop-Limit gesetzt: {limit} (0 = unendlich)")
            except ValueError:
                print("Ungültiger Wert! Verwende eine Zahl.")
        else:
            print("Verwendung: loop <anzahl>")
    
    # === Art-Net ===
    
    def _handle_test(self, args):
        """Zeigt Testmuster."""
        color = args if args else 'red'
        self.player.test_pattern(color)
    
    def _handle_ip(self, args):
        """Setzt oder zeigt Ziel-IP."""
        if args:
            self.player.target_ip = args
            print(f"Ziel-IP gesetzt: {args}")
            print("HINWEIS: Starte Video neu für Änderung")
        else:
            print(f"Aktuelle IP: {self.player.target_ip}")
    
    def _handle_universe(self, args):
        """Setzt oder zeigt Start-Universum."""
        if args:
            try:
                self.player.start_universe = int(args)
                print(f"Start-Universum gesetzt: {args}")
                print("HINWEIS: Starte Video neu für Änderung")
            except ValueError:
                print("Ungültiger Wert!")
        else:
            print(f"Aktuelles Start-Universum: {self.player.start_universe}")
    
    def _handle_artnet(self, args):
        """Verwaltet Art-Net Konfiguration (Subcommands: map, show)."""
        if not args:
            print("❌ Verwendung: artnet <subcommand> [args]")
            print("")
            print("Subcommands:")
            print("  artnet map <format> <universes>  - Setzt RGB-Kanal-Reihenfolge")
            print("  artnet show                      - Zeigt aktuelle Kanal-Mappings")
            print("")
            print("Formate: RGB, GRB, BGR, RBG, GBR, BRG")
            print("")
            print("Beispiele:")
            print("  artnet map rgb 0-4       - Universen 0-4 auf RGB setzen")
            print("  artnet map grb 5         - Universum 5 auf GRB setzen")
            print("  artnet map bgr 6-10      - Universen 6-10 auf BGR setzen")
            print("  artnet show              - Zeigt alle Mappings")
            return
        
        parts = args.split(maxsplit=2)
        subcommand = parts[0].lower()
        
        if subcommand == "map":
            if len(parts) < 3:
                print("❌ Verwendung: artnet map <format> <universes>")
                print("Beispiel: artnet map grb 0-5")
                return
            self._handle_artnet_map(parts[1], parts[2])
        
        elif subcommand == "show":
            self._handle_artnet_show()
        
        else:
            print(f"❌ Unbekanntes Subcommand: {subcommand}")
            print("Verfügbar: map, show")
    
    def _handle_artnet_map(self, format_str, universes_str):
        """Setzt RGB-Kanal-Reihenfolge für Universen."""
        # Validiere Format
        format_str = format_str.upper()
        valid_formats = ['RGB', 'GRB', 'BGR', 'RBG', 'GBR', 'BRG']
        if format_str not in valid_formats:
            print(f"❌ Ungültiges Format: {format_str}")
            print(f"Verfügbar: {', '.join(valid_formats)}")
            return
        
        # Parse Universum-Bereich (z.B. "0-5" oder "3")
        try:
            if '-' in universes_str:
                start, end = universes_str.split('-')
                start_uni = int(start)
                end_uni = int(end)
                if start_uni > end_uni:
                    print("❌ Start-Universum muss kleiner als End-Universum sein")
                    return
                universe_list = list(range(start_uni, end_uni + 1))
            else:
                universe_list = [int(universes_str)]
        except ValueError:
            print(f"❌ Ungültiger Universum-Bereich: {universes_str}")
            print("Verwende Format: '0-5' oder '3'")
            return
        
        # Lade config.json
        config_path = os.path.join(self.base_path, "config.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = {}
            
            # Stelle Struktur sicher
            if 'artnet' not in config_data:
                config_data['artnet'] = {}
            if 'universe_configs' not in config_data['artnet']:
                config_data['artnet']['universe_configs'] = {'default': 'RGB'}
            
            # Setze Mapping für alle Universen im Bereich
            for uni in universe_list:
                config_data['artnet']['universe_configs'][str(uni)] = format_str
            
            # Speichere config.json
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            # Erfolgsausgabe
            if len(universe_list) == 1:
                print(f"✅ Universum {universe_list[0]} auf {format_str} gesetzt")
            else:
                print(f"✅ Universen {universe_list[0]}-{universe_list[-1]} auf {format_str} gesetzt")
            print("💾 Konfiguration gespeichert in config.json")
            print("⚠️  HINWEIS: Starte Video neu, damit die Änderung wirksam wird")
            
        except Exception as e:
            print(f"❌ Fehler beim Speichern: {e}")
    
    def _handle_artnet_show(self):
        """Zeigt aktuelle RGB-Kanal-Mappings."""
        config_path = os.path.join(self.base_path, "config.json")
        try:
            if not os.path.exists(config_path):
                print("⚠️  Keine config.json gefunden")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            universe_configs = config_data.get('artnet', {}).get('universe_configs', {})
            
            if not universe_configs:
                print("⚠️  Keine Universe-Konfigurationen gefunden")
                return
            
            print("")
            print("🎨 Art-Net RGB-Kanal-Mappings:")
            print("=" * 40)
            
            # Default zuerst
            default = universe_configs.get('default', 'RGB')
            print(f"Default:  {default}")
            print("-" * 40)
            
            # Sortiere Universen numerisch
            universe_nums = [k for k in universe_configs.keys() if k.isdigit()]
            universe_nums.sort(key=int)
            
            if not universe_nums:
                print("Keine spezifischen Universen konfiguriert")
            else:
                for uni in universe_nums:
                    format_str = universe_configs[uni]
                    print(f"Universum {uni:>3}: {format_str}")
            
            print("=" * 40)
            print("")
            
        except Exception as e:
            print(f"❌ Fehler beim Laden: {e}")
    
    # === Info ===
    
    def _handle_status(self):
        """Zeigt Status."""
        print(self.player.status())
    
    def _handle_info(self):
        """Zeigt Informationen."""
        info = self.player.get_info()
        for key, value in info.items():
            print(f"{key}: {value}")
    
    def _handle_stats(self):
        """Zeigt Statistiken."""
        stats = self.player.get_stats()
        if isinstance(stats, dict):
            for key, value in stats.items():
                print(f"{key}: {value}")
        else:
            print(stats)
    
    # === Recording ===
    
    def _handle_record(self, args):
        """Verwaltet Recording."""
        if args == "start":
            self.player.start_recording()
        elif args and args.startswith("stop"):
            parts = args.split(maxsplit=1)
            filename = parts[1] if len(parts) > 1 else None
            self.player.stop_recording(filename)
        else:
            print("Verwendung: record start | record stop [datei]")
    
    # === Cache ===
    
    def _handle_cache(self, args):
        """Verwaltet Cache."""
        from .video_player import VideoPlayer
        
        cache_dir = os.path.join(self.base_path, self.config['paths'].get('cache_dir', 'cache'))
        
        if args == "clear":
            self._handle_cache_clear(cache_dir)
        elif args == "info":
            self._handle_cache_info(cache_dir)
        elif args and args.startswith("delete"):
            self._handle_cache_delete(args, cache_dir)
        elif args == "enable":
            self._handle_cache_enable()
        elif args == "disable":
            self._handle_cache_disable()
        elif args == "size":
            self._handle_cache_size(cache_dir)
        elif args == "fill":
            self._handle_cache_fill(cache_dir)
        else:
            print("Verwendung: cache clear | info | delete <name> | enable | disable | size | fill")
    
    def _handle_cache_clear(self, cache_dir):
        """Leert Cache."""
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            file_count = 0
            for f in files:
                try:
                    os.remove(os.path.join(cache_dir, f))
                    file_count += 1
                except Exception as e:
                    print(f"  ⚠ Konnte nicht löschen: {f} ({e})")
            print(f"✓ Cache geleert ({file_count} Dateien gelöscht)")
        else:
            print("Cache-Ordner existiert nicht")
    
    def _handle_cache_info(self, cache_dir):
        """Zeigt Cache-Info."""
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            print(f"Cache-Informationen:")
            print(f"  Dateien: {len(files)}")
            print(f"  Größe: {total_size / (1024*1024):.2f} MB")
            print(f"  Pfad: {cache_dir}")
            print(f"  Status: {'Aktiviert' if self.config.get('cache', {}).get('enabled', True) else 'Deaktiviert'}")
        else:
            print("Cache-Ordner existiert nicht")
    
    def _handle_cache_delete(self, args, cache_dir):
        """Löscht Cache für bestimmtes Video."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            print("Verwendung: cache delete <videoname>")
            return
        
        video_name = parts[1]
        found = False
        if os.path.exists(cache_dir):
            for cache_file in os.listdir(cache_dir):
                if cache_file.endswith('.msgpack'):
                    cache_path = os.path.join(cache_dir, cache_file)
                    try:
                        import msgpack
                        with open(cache_path, 'rb') as f:
                            cache_data = msgpack.unpackb(f.read(), raw=False)
                        if video_name.lower() in cache_data.get('video', '').lower():
                            file_size_mb = os.path.getsize(cache_path) / (1024*1024)
                            os.remove(cache_path)
                            print(f"✓ Cache gelöscht für: {cache_data.get('video')} ({file_size_mb:.2f} MB)")
                            found = True
                            break
                    except:
                        pass
        if not found:
            print(f"Keine Cache-Datei gefunden für: {video_name}")
    
    def _handle_cache_enable(self):
        """Aktiviert Cache."""
        self.config['cache']['enabled'] = True
        config_path = os.path.join(self.base_path, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        print("✓ RGB-Caching aktiviert")
    
    def _handle_cache_disable(self):
        """Deaktiviert Cache."""
        self.config['cache']['enabled'] = False
        config_path = os.path.join(self.base_path, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        print("✓ RGB-Caching deaktiviert")
    
    def _handle_cache_size(self, cache_dir):
        """Zeigt Cache-Größe."""
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            print(f"Cache-Größe: {total_size / (1024*1024):.2f} MB ({len(files)} Dateien)")
            if files:
                print("\nTop 5 größte Dateien:")
                file_sizes = [(f, os.path.getsize(os.path.join(cache_dir, f))) for f in files]
                for fname, fsize in sorted(file_sizes, key=lambda x: x[1], reverse=True)[:5]:
                    print(f"  {fname}: {fsize / (1024*1024):.2f} MB")
        else:
            print("Cache-Ordner existiert nicht")
    
    def _handle_cache_fill(self, cache_dir):
        """Füllt Cache für alle Videos."""
        from .video_player import VideoPlayer
        
        if not self.config.get('cache', {}).get('enabled', True):
            print("⚠ Cache ist deaktiviert! Aktiviere mit: cache enable")
            return
        
        print("⚠ WARNUNG: Dies cached alle Videos neu und kann sehr lange dauern!")
        confirm = input("Fortfahren? (j/n): ").strip().lower()
        if confirm not in AFFIRMATIVE_RESPONSES:
            print("Abgebrochen")
            return
        
        all_videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    all_videos.append(os.path.join(root, f))
        
        print(f"\nStarte Cache-Fill für {len(all_videos)} Videos...")
        
        for idx, video_path in enumerate(all_videos, 1):
            print(f"\n[{idx}/{len(all_videos)}] Processing: {os.path.basename(video_path)}")
            try:
                temp_player = VideoPlayer(
                    video_path, 
                    self.player.points_json_path,
                    self.player.target_ip, 
                    self.player.start_universe,
                    self.player.fps_limit, 
                    self.config
                )
                cache_path = temp_player._get_cache_path()
                if cache_path and os.path.exists(cache_path):
                    print(f"  ✓ Cache existiert bereits, überspringe...")
                else:
                    print(f"  → Erstelle Cache (dauert einige Sekunden)...")
                    temp_player.start()
                    while temp_player.current_loop < 1 and temp_player.is_running:
                        time.sleep(0.5)
                    temp_player.stop()
                    time.sleep(0.5)
                    print(f"  ✓ Cache erstellt")
            except Exception as e:
                print(f"  ✗ Fehler: {e}")
        
        print(f"\n✓ Cache-Fill abgeschlossen für {len(all_videos)} Videos")
    
    # === System ===
    
    def _handle_help(self):
        """Zeigt Hilfe."""
        from .utils import print_help
        print_help()
    
    # === Scripts ===
    
    def _handle_scripts(self, args):
        """Verwaltet Scripts."""
        from .script_generator import ScriptGenerator
        
        scripts_dir = self.config['paths']['scripts_dir']
        script_gen = ScriptGenerator(scripts_dir)
        
        if not args or args == "list":
            self._handle_scripts_list(script_gen)
        else:
            print("Verwendung: scripts [list]")
    
    def _handle_scripts_list(self, script_gen):
        """Listet alle Scripts auf."""
        scripts = script_gen.list_scripts()
        
        if not scripts:
            print("\nKeine Scripts gefunden!")
            return
        
        print(f"\n{'='*60}")
        print(f"{'Script':<30} {'Beschreibung':<30}")
        print(f"{'='*60}")
        
        for script in scripts:
            name = script['name'][:28]
            desc = script.get('description', 'Keine Beschreibung')[:28]
            print(f"{name:<30} {desc:<30}")
        
        print(f"{'='*60}")
        print(f"\nInsgesamt {len(scripts)} Script(s)")
        print("Verwendung: script:<name>  (z.B. script:rainbow_wave)")
    
    def _handle_load_script(self, command):
        """Lädt und startet ein Script."""
        from .script_player import ScriptPlayer
        
        # Extrahiere Script-Namen
        script_name = command.split(':', 1)[1].strip()
        if not script_name.endswith('.py'):
            script_name += '.py'
        
        # Stoppe aktuellen Player wenn er läuft
        was_playing = self.player.is_playing
        
        # Speichere alte Player-Daten
        old_player = self.player
        points_json_path = old_player.points_json_path
        target_ip = old_player.target_ip
        start_universe = old_player.start_universe
        fps_limit = old_player.fps_limit
        
        # Stoppe alten Player komplett
        if was_playing:
            old_player.stop()
        
        # Warte und lösche Referenz
        import time
        time.sleep(0.5)
        del old_player
        
        try:
            # Erstelle neuen ScriptPlayer
            new_player = ScriptPlayer(
                script_name,
                points_json_path,
                target_ip,
                start_universe,
                fps_limit,
                self.config
            )
            
            # Übernehme Einstellungen vom alten Player
            new_player.brightness = self.player.brightness
            new_player.speed_factor = self.player.speed_factor
            
            # Zeige Info
            info = new_player.get_info()
            print(f"\n✓ Script geladen: {info.get('name', script_name)}")
            if 'description' in info:
                print(f"  {info['description']}")
            if 'parameters' in info:
                print(f"  Parameter: {', '.join(info['parameters'].keys())}")
            
            # Starte automatisch
            new_player.start()
            
            # Tracking für next/back
            self.current_script_name = script_name
            self.current_video_path = None
            
            return (True, new_player)
            
        except Exception as e:
            print(f"Fehler beim Laden des Scripts: {e}")
            import traceback
            traceback.print_exc()
            return (True, None)
    
    def _handle_open(self):
        """Öffnet Web-Interface im Browser (undokumentiert)."""
        import webbrowser
        port = self.config.get('api', {}).get('port', 5000)
        
        if not self.rest_api.is_running:
            print("⚠️  REST API ist nicht aktiv")
            print("Starte API mit: api start")
            return
        
        url = f"http://localhost:{port}"
        print(f"Öffne Browser: {url}")
        webbrowser.open(url)
