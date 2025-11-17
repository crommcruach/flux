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
        if command == "restart":
            self.player.restart()
            
        elif command == "stop":
            self.player.stop()
            
        elif command == "pause":
            self.player.pause()
            
        elif command == "resume":
            self.player.resume()
        
        # Video-Verwaltung
        elif command == "load":
            return self._handle_load(args)
            
        elif command == "list":
            self._handle_list()
            
        elif command == "switch":
            return self._handle_switch(args)
        
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
    
    def _handle_load(self, args):
        """Lädt ein Video."""
        if args:
            full_path = os.path.join(self.video_dir, args) if not os.path.isabs(args) else args
            self.player.load_video(full_path)
        else:
            print("Verwendung: load <pfad>")
        return (True, None)
    
    def _handle_list(self):
        """Listet alle Videos auf."""
        from .utils import list_videos
        list_videos(self.video_dir)
    
    def _handle_switch(self, args):
        """Wechselt zu einem Video."""
        if not args:
            print("Verwendung: switch <name>")
            return (True, None)
        
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    videos.append(os.path.join(root, f))
        
        matching = [v for v in videos if args.lower() in os.path.basename(v).lower()]
        if matching:
            self.player.load_video(matching[0])
        else:
            print(f"Kein Video gefunden mit: {args}")
        
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
