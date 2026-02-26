"""
CLI Command Handler - Zentrale Verarbeitung aller CLI-Befehle
"""
import os
import sys
import time
import json
from ..core.constants import VIDEO_EXTENSIONS, AFFIRMATIVE_RESPONSES
from ..core.logger import get_logger
from .commands import CommandExecutor

logger = get_logger(__name__)


class CLIHandler:
    """Verarbeitet CLI-Befehle und delegiert an entsprechende Komponenten."""
    
    def __init__(self, player_manager, dmx_controller, rest_api, video_dir, data_dir, config):
        # Nutze player_manager für zentralen Player-Zugriff
        self.player_manager = player_manager
        self.dmx_controller = dmx_controller  # Deprecated - DMX input removed
        self.rest_api = rest_api
        self.video_dir = video_dir
        self.data_dir = data_dir
        self.config = config
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Initialize unified command executor
        self.command_executor = CommandExecutor(
            player_provider=lambda: self.player_manager.player,
            dmx_controller=None,  # DMX input removed
            video_dir=video_dir,
            data_dir=data_dir,
            config=config
        )
        
        # Tracking für next/back Navigation
        self.current_video_path = None
        self.current_script_name = None
        self.video_list_cache = None
        self.script_list_cache = None
    
    @property
    def player(self):
        """Gibt aktuellen Player dynamisch zurück."""
        return self.player_manager.player
    
    def execute_command(self, command, args=None):
        """
        Führt einen CLI-Befehl aus.
        
        Args:
            command: Befehlsname (lowercase)
            args: Optionale Argumente als String
            
        Returns:
            tuple: (continue_loop, new_player) - continue_loop=False bei Exit, new_player wenn Player ersetzt wurde
        """
        # Build full command string for CommandExecutor
        full_command = f"{command} {args}" if args else command
        
        # Handle CLI-specific commands first (navigation, exit, etc.)
        if command == "next":
            return self._handle_next()
        elif command == "back":
            return self._handle_back()
        elif command == "api":
            self._handle_api(args)
            return (True, None)
        elif command == "points":
            new_player = self._handle_points(args)
            if new_player:
                return (True, new_player)
            return (True, None)
        elif command == "cache":
            logger.debug("Cache system deprecated. RGB caching is no longer used.")
            return (True, None)
        elif command == "artnet":
            self._handle_artnet(args)
            return (True, None)
        elif command == "plugin":
            self._handle_plugin(args)
            return (True, None)
        elif command == "browser":
            self._handle_open()
            return (True, None)
        elif command == "clear":
            self._handle_clear()
            return (True, None)
        elif command in ["exit", "quit"]:
            print("\nBeende Anwendung...")
            return (False, None)
        
        # Use CommandExecutor for standard commands
        result = self.command_executor.execute(full_command)
        
        # Print result to console
        print(str(result))
        
        # Return continue flag
        return (True, None)
    
    # === Video-Verwaltung ===
    
    def _handle_videos_list(self):
        """Listet alle Videos auf."""
        from ..core.utils import list_videos
        list_videos(self.video_dir)
    
    def _handle_video_load(self, command):
        """Lädt und startet ein Video."""
        from ..player.sources import VideoSource
        
        # Extrahiere Video-Namen
        video_name = command.split(':', 1)[1].strip()
        
        if not video_name:
            logger.debug("Verwendung: video:<name>")
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
            logger.warning(f"Kein Video gefunden mit: {video_name}")
            return (True, None)
        
        if len(matching) > 1:
            logger.debug(f"Mehrere Videos gefunden:")
            for v in matching:
                # Zeige relativen Pfad zum video_dir für bessere Übersicht
                rel_path = os.path.relpath(v, self.video_dir)
                logger.debug(f"  - {rel_path}")
            logger.debug("Bitte spezifischer wählen (z.B. 'video:kanal_1/test' oder kompletter Pfad).")
            return (True, None)
        
        # Erstelle neue VideoSource
        video_source = VideoSource(
            matching[0],
            self.player.canvas_width,
            self.player.canvas_height,
            self.config
        )
        
        # Wechsle Source (unified Player bleibt bestehen)
        success = self.player.switch_source(video_source)
        
        if not success:
            logger.error(f"Fehler beim Laden des Videos: {os.path.basename(matching[0])}")
            return (True, None)
        
        # Tracking
        self.current_video_path = matching[0]
        self.current_script_name = None
        
        logger.debug(f"✓ Video geladen: {os.path.basename(matching[0])}")
        
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
        
        # from .script_generator import ScriptGenerator  # Deprecated - using plugin system
        # scripts_dir = self.config['paths']['scripts_dir']
        # script_gen = ScriptGenerator(scripts_dir)
        # scripts = script_gen.list_scripts()
        scripts = []  # Script system deprecated
        
        self.script_list_cache = [s['filename'] for s in scripts]
        return self.script_list_cache
    
    def _handle_next(self):
        """Lädt nächstes Video oder Script."""
        # Prüfe ob Video oder Script aktiv
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                logger.debug("Keine Videos verfügbar")
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
                    logger.debug(f"Nächstes Video: {os.path.basename(next_video)}")
            except ValueError:
                logger.debug("Aktuelles Video nicht in Liste gefunden")
        
        elif self.current_script_name:
            logger.warning("⚠️  Script navigation is deprecated - use generator plugins from web UI")
            return (True, None)
        else:
            logger.debug("Kein Video oder Script aktiv")
        
        return (True, None)
    
    def _handle_back(self):
        """Lädt vorheriges Video oder Script."""
        # Prüfe ob Video oder Script aktiv
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                logger.debug("Keine Videos verfügbar")
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
                    logger.debug(f"Vorheriges Video: {os.path.basename(prev_video)}")
            except ValueError:
                logger.debug("Aktuelles Video nicht in Liste gefunden")
        
        elif self.current_script_name:
            logger.warning("⚠️  Script navigation is deprecated - use generator plugins from web UI")
            return (True, None)
        else:
            logger.debug("Kein Video oder Script aktiv")
        
        return (True, None)
    
    # === REST API ===
    
    def _handle_api(self, args):
        """Steuert REST API."""
        if not args:
            logger.debug("Verwendung: api start [port] | api stop")
            return
        
        if args == "start":
            parts = args.split()
            port = int(parts[1]) if len(parts) > 1 else self.config['api']['port']
            self.rest_api.start(port=port)
        elif args == "stop":
            self.rest_api.stop()
        else:
            logger.debug("Verwendung: api start [port] | api stop")
    
    # === Punkte-Verwaltung ===
    
    def _handle_points(self, args):
        """Verwaltet Punkte-Listen."""
        from ..core.utils import list_points_files
        from ..core.validator import validate_points_file
        
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
            logger.debug("Verwendung: points list | points validate [name] | points switch <name> | points reload")
            return None
    
    def _handle_points_validate(self, args):
        """Validiert eine Punkte-Liste."""
        from ..core.validator import validate_points_file
        
        parts = args.split(maxsplit=1)
        if len(parts) > 1:
            search_name = parts[1]
            json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
            matching = [f for f in json_files if search_name.lower() in f.lower()]
            if matching:
                file_path = os.path.join(self.data_dir, matching[0])
                logger.debug(f"\nValidiere: {matching[0]}")
                is_valid, message, errors, data = validate_points_file(file_path)
                
                if is_valid:
                    logger.debug(f"✓ {message}")
                else:
                    logger.warning(f"✗ {message}")
                    if errors:
                        logger.warning("\nFehler:")
                        for error in errors:
                            logger.warning(f"  • {error}")
            else:
                logger.warning(f"Keine Punkte-Liste gefunden mit: {search_name}")
        else:
            # Validiere aktuelle Liste
            logger.debug(f"\nValidiere: {os.path.basename(self.player.points_json_path)}")
            is_valid, message, errors, data = validate_points_file(self.player.points_json_path)
            
            if is_valid:
                logger.debug(f"✓ {message}")
            else:
                logger.warning(f"✗ {message}")
                if errors:
                    logger.warning("\nFehler:")
                    for error in errors:
                        logger.warning(f"  • {error}")
    
    def _handle_points_switch(self, args):
        """Wechselt Punkte-Liste."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            logger.debug("Verwendung: points switch <name>")
            return None
        
        search_name = parts[1]
        json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
        matching = [f for f in json_files if search_name.lower() in f.lower()]
        
        if not matching:
            logger.warning(f"Keine Punkte-Liste gefunden mit: {search_name}")
            return None
        
        new_points_path = os.path.join(self.data_dir, matching[0])
        was_playing = self.player.is_playing
        if was_playing:
            self.player.stop()
        
        try:
            # Update points path in existing player
            self.player.points_json_path = new_points_path
            self.player.reload_points()
            
            logger.debug(f"✓ Punkte-Liste gewechselt: {matching[0]}")
            logger.debug(f"  Anzahl Punkte: {self.player.total_points}")
            logger.debug(f"  Benötigte Universen: {self.player.required_universes}")
            
            if was_playing:
                self.player.start()
            
            return self.player
        except Exception as e:
            logger.error(f"Fehler beim Laden der Punkte-Liste: {e}")
            return None
    
    def _handle_points_reload(self):
        """Lädt aktuelle Punkte-Liste neu."""
        was_playing = self.player.is_playing
        current_points_path = self.player.points_json_path
        if was_playing:
            self.player.stop()
        
        try:
            # Reload points in existing player
            self.player.reload_points()
            
            logger.debug(f"✓ Punkte-Liste neu geladen: {os.path.basename(current_points_path)}")
            logger.debug(f"  Anzahl Punkte: {self.player.total_points}")
            logger.debug(f"  Benötigte Universen: {self.player.required_universes}")
            
            if was_playing:
                self.player.start()
            
            return self.player
        except Exception as e:
            logger.error(f"Fehler beim Neuladen der Punkte-Liste: {e}")
            return None
    
    # === Einstellungen ===
    
    def _handle_fps(self, args):
        """Setzt FPS."""
        if args:
            self.player.set_fps(args)
        else:
            logger.debug("Verwendung: fps <wert>")
    
    def _handle_speed(self, args):
        """Setzt Geschwindigkeit."""
        if args:
            self.player.set_speed(args)
        else:
            logger.debug("Verwendung: speed <faktor>")
    
    def _handle_brightness(self, args):
        """Setzt Helligkeit."""
        if args:
            self.player.set_brightness(args)
        else:
            logger.debug("Verwendung: brightness <0-100>")
    
    def _handle_loop(self, args):
        """Setzt Loop-Limit."""
        if args:
            try:
                limit = int(args)
                self.player.set_loop_limit(limit)
                logger.debug(f"Loop-Limit gesetzt: {limit} (0 = unendlich)")
            except ValueError:
                logger.warning("Ungültiger Wert! Verwende eine Zahl.")
        else:
            logger.debug("Verwendung: loop <anzahl>")
    
    # === Art-Net ===
    
    def _handle_test(self, args):
        """Zeigt Testmuster."""
        color = args if args else 'red'
        self.player.test_pattern(color)
    
    def _handle_ip(self, args):
        """Setzt oder zeigt Ziel-IP."""
        if args:
            self.player.target_ip = args
            logger.debug(f"Ziel-IP gesetzt: {args}")
            logger.debug("HINWEIS: Starte Video neu für Änderung")
        else:
            logger.debug(f"Aktuelle IP: {self.player.target_ip}")
    
    def _handle_universe(self, args):
        """Setzt oder zeigt Start-Universum."""
        if args:
            try:
                self.player.start_universe = int(args)
                logger.debug(f"Start-Universum gesetzt: {args}")
                logger.debug("HINWEIS: Starte Video neu für Änderung")
            except ValueError:
                logger.warning("Ungültiger Wert!")
        else:
            logger.debug(f"Aktuelles Start-Universum: {self.player.start_universe}")
    
    def _handle_artnet(self, args):
        """Verwaltet Art-Net Konfiguration (Subcommands: map, show)."""
        if not args:
            logger.debug("❌ Verwendung: artnet <subcommand> [args]")
            logger.debug("")
            logger.debug("Subcommands:")
            logger.debug("  artnet map <format> <universes>  - Setzt RGB-Kanal-Reihenfolge")
            logger.debug("  artnet show                      - Zeigt aktuelle Kanal-Mappings")
            logger.debug("")
            logger.debug("Formate: RGB, GRB, BGR, RBG, GBR, BRG")
            logger.debug("")
            logger.debug("Beispiele:")
            logger.debug("  artnet map rgb 0-4       - Universen 0-4 auf RGB setzen")
            logger.debug("  artnet map grb 5         - Universum 5 auf GRB setzen")
            logger.debug("  artnet map bgr 6-10      - Universen 6-10 auf BGR setzen")
            logger.debug("  artnet show              - Zeigt alle Mappings")
            return
        
        parts = args.split(maxsplit=2)
        subcommand = parts[0].lower()
        
        if subcommand == "map":
            if len(parts) < 3:
                logger.debug("❌ Verwendung: artnet map <format> <universes>")
                logger.debug("Beispiel: artnet map grb 0-5")
                return
            self._handle_artnet_map(parts[1], parts[2])
        
        elif subcommand == "show":
            self._handle_artnet_show()
        
        else:
            logger.warning(f"❌ Unbekanntes Subcommand: {subcommand}")
            logger.debug("Verfügbar: map, show")
    
    def _handle_artnet_map(self, format_str, universes_str):
        """Setzt RGB-Kanal-Reihenfolge für Universen."""
        # Validiere Format
        format_str = format_str.upper()
        valid_formats = ['RGB', 'GRB', 'BGR', 'RBG', 'GBR', 'BRG']
        if format_str not in valid_formats:
            logger.warning(f"❌ Ungültiges Format: {format_str}")
            logger.debug(f"Verfügbar: {', '.join(valid_formats)}")
            return
        
        # Parse Universum-Bereich (z.B. "0-5" oder "3")
        try:
            if '-' in universes_str:
                start, end = universes_str.split('-')
                start_uni = int(start)
                end_uni = int(end)
                if start_uni > end_uni:
                    logger.warning("❌ Start-Universum muss kleiner als End-Universum sein")
                    return
                universe_list = list(range(start_uni, end_uni + 1))
            else:
                universe_list = [int(universes_str)]
        except ValueError:
            logger.warning(f"❌ Ungültiger Universum-Bereich: {universes_str}")
            logger.debug("Verwende Format: '0-5' oder '3'")
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
                logger.debug(f"✅ Universum {universe_list[0]} auf {format_str} gesetzt")
            else:
                logger.debug(f"✅ Universen {universe_list[0]}-{universe_list[-1]} auf {format_str} gesetzt")
            logger.debug("💾 Konfiguration gespeichert in config.json")
            logger.debug("⚠️  HINWEIS: Starte Video neu, damit die Änderung wirksam wird")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern: {e}")
    
    def _handle_artnet_show(self):
        """Zeigt aktuelle RGB-Kanal-Mappings."""
        config_path = os.path.join(self.base_path, "config.json")
        try:
            if not os.path.exists(config_path):
                logger.warning("⚠️  Keine config.json gefunden")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            universe_configs = config_data.get('artnet', {}).get('universe_configs', {})
            
            if not universe_configs:
                logger.warning("⚠️  Keine Universe-Konfigurationen gefunden")
                return
            
            logger.debug("")
            logger.debug("🎨 Art-Net RGB-Kanal-Mappings:")
            logger.debug("=" * 40)
            
            # Default zuerst
            default = universe_configs.get('default', 'RGB')
            logger.debug(f"Default:  {default}")
            logger.debug("-" * 40)
            
            # Sortiere Universen numerisch
            universe_nums = [k for k in universe_configs.keys() if k.isdigit()]
            universe_nums.sort(key=int)
            
            if not universe_nums:
                logger.debug("Keine spezifischen Universen konfiguriert")
            else:
                for uni in universe_nums:
                    format_str = universe_configs[uni]
                    logger.debug(f"Universum {uni:>3}: {format_str}")
            
            logger.debug("=" * 40)
            logger.debug("")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Laden: {e}")
    
    # === Info ===
    
    def _handle_status(self):
        """Zeigt Status."""
        logger.debug(self.player.status())
    
    def _handle_info(self):
        """Zeigt Informationen."""
        info = self.player.get_info()
        for key, value in info.items():
            logger.debug(f"{key}: {value}")
    
    def _handle_stats(self):
        """Zeigt Statistiken."""
        stats = self.player.get_stats()
        if isinstance(stats, dict):
            for key, value in stats.items():
                logger.debug(f"{key}: {value}")
        else:
            logger.debug(stats)
    
    # === Cache ===
    
    # REMOVED: _handle_record - Recording system removed
    
    def _handle_cache(self, args):
        """Verwaltet Cache."""
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
            logger.debug("Verwendung: cache clear | info | delete <name> | enable | disable | size | fill")
    
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
                    logger.warning(f"  ⚠ Konnte nicht löschen: {f} ({e})")
            logger.debug(f"✓ Cache geleert ({file_count} Dateien gelöscht)")
        else:
            logger.debug("Cache-Ordner existiert nicht")
    
    def _handle_cache_info(self, cache_dir):
        """Zeigt Cache-Info."""
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            logger.debug(f"Cache-Informationen:")
            logger.debug(f"  Dateien: {len(files)}")
            logger.debug(f"  Größe: {total_size / (1024*1024):.2f} MB")
            logger.debug(f"  Pfad: {cache_dir}")
            logger.debug(f"  Status: {'Aktiviert' if self.config.get('cache', {}).get('enabled', True) else 'Deaktiviert'}")
        else:
            logger.debug("Cache-Ordner existiert nicht")
    
    def _handle_cache_delete(self, args, cache_dir):
        """Löscht Cache für bestimmtes Video."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            logger.debug("Verwendung: cache delete <videoname>")
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
                            logger.debug(f"✓ Cache gelöscht für: {cache_data.get('video')} ({file_size_mb:.2f} MB)")
                            found = True
                            break
                    except:
                        pass
        if not found:
            logger.warning(f"Keine Cache-Datei gefunden für: {video_name}")
    
    def _handle_cache_enable(self):
        """Aktiviert Cache."""
        self.config['cache']['enabled'] = True
        config_path = os.path.join(self.base_path, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        logger.debug("✓ RGB-Caching aktiviert")
    
    def _handle_cache_disable(self):
        """Deaktiviert Cache."""
        self.config['cache']['enabled'] = False
        config_path = os.path.join(self.base_path, 'config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2)
        logger.debug("✓ RGB-Caching deaktiviert")
    
    def _handle_cache_size(self, cache_dir):
        """Zeigt Cache-Größe."""
        if os.path.exists(cache_dir):
            files = [f for f in os.listdir(cache_dir) if os.path.isfile(os.path.join(cache_dir, f))]
            total_size = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
            logger.debug(f"Cache-Größe: {total_size / (1024*1024):.2f} MB ({len(files)} Dateien)")
            if files:
                logger.debug("\nTop 5 größte Dateien:")
                file_sizes = [(f, os.path.getsize(os.path.join(cache_dir, f))) for f in files]
                for fname, fsize in sorted(file_sizes, key=lambda x: x[1], reverse=True)[:5]:
                    logger.debug(f"  {fname}: {fsize / (1024*1024):.2f} MB")
        else:
            logger.debug("Cache-Ordner existiert nicht")
    
    def _handle_cache_fill(self, cache_dir):
        """Füllt Cache für alle Videos."""
        if not self.config.get('cache', {}).get('enabled', True):
            logger.warning("⚠ Cache ist deaktiviert! Aktiviere mit: cache enable")
            return
        
        logger.warning("⚠ WARNUNG: Dies cached alle Videos neu und kann sehr lange dauern!")
        confirm = input("Fortfahren? (j/n): ").strip().lower()
        if confirm not in AFFIRMATIVE_RESPONSES:
            logger.debug("Abgebrochen")
            return
        
        all_videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    all_videos.append(os.path.join(root, f))
        
        logger.debug(f"\nStarte Cache-Fill für {len(all_videos)} Videos...")
        
        from ..player.sources import VideoSource
        from .player import Player
        
        for idx, video_path in enumerate(all_videos, 1):
            logger.debug(f"\n[{idx}/{len(all_videos)}] Processing: {os.path.basename(video_path)}")
            try:
                # Create temporary VideoSource for caching
                temp_source = VideoSource(
                    video_path,
                    self.player.canvas_width,
                    self.player.canvas_height,
                    self.config
                )
                
                # Create temporary player for caching
                temp_player = Player(
                    temp_source,
                    self.player.points_json_path,
                    self.player.target_ip,
                    self.player.start_universe,
                    self.player.fps_limit,
                    self.config
                )
                
                cache_path = temp_source._get_cache_path()
                if cache_path and os.path.exists(cache_path):
                    logger.debug(f"  ✓ Cache existiert bereits, überspringe...")
                else:
                    logger.debug(f"  → Erstelle Cache (dauert einige Sekunden)...")
                    temp_player.start()
                    while temp_player.current_loop < 1 and temp_player.is_running:
                        time.sleep(0.5)
                    temp_player.stop()
                    time.sleep(0.5)
                    logger.debug(f"  ✓ Cache erstellt")
            except Exception as e:
                logger.error(f"  ✗ Fehler: {e}")
        
        logger.debug(f"\n✓ Cache-Fill abgeschlossen für {len(all_videos)} Videos")
    
    # === System ===
    
    def _handle_help(self):
        """Zeigt Hilfe."""
        from ..core.utils import print_help
        print_help()
    
    # === Scripts ===
    
    def _handle_scripts(self, args):
        """Verwaltet Scripts."""
        # from .script_generator import ScriptGenerator  # Deprecated - using plugin system
        logger.debug("Script system deprecated. Use generators plugin instead.")
        return
    
    def _handle_scripts_list(self, script_gen):
        """Listet alle Scripts auf."""
        scripts = script_gen.list_scripts()
        
        if not scripts:
            logger.debug("\nKeine Scripts gefunden!")
            return
        
        logger.debug(f"\n{'='*60}")
        logger.debug(f"{'Script':<30} {'Beschreibung':<30}")
        logger.debug(f"{'='*60}")
        
        for script in scripts:
            name = script['name'][:28]
            desc = script.get('description', 'Keine Beschreibung')[:28]
            logger.debug(f"{name:<30} {desc:<30}")
        
        logger.debug(f"{'='*60}")
        logger.debug(f"\nInsgesamt {len(scripts)} Script(s)")
        logger.debug("Verwendung: Use generators from the Sources tab in the web UI")
        logger.debug("⚠️  Script loading via CLI is no longer supported")
    
    def _handle_open(self):
        """Öffnet Web-Interface im Browser (undokumentiert)."""
        import webbrowser
        port = self.config.get('api', {}).get('port', 5000)
        
        if not self.rest_api.is_running:
            logger.warning("⚠️  REST API ist nicht aktiv")
            logger.debug("Starte API mit: api start")
            return
        
        url = f"http://localhost:{port}"
        logger.debug(f"Öffne Browser: {url}")
        webbrowser.open(url)
    
    def _handle_clear(self):
        """Löscht die Console-Anzeige."""
        # Clear REST API console log
        if self.rest_api:
            self.rest_api.clear_console()
            logger.debug("✓ Console geleert")
    
    def _handle_plugin(self, args):
        """Verwaltet Plugins (list, reload)."""
        from ..plugins.manager import get_plugin_manager
        
        if not args:
            logger.debug("Verwendung: plugin list | plugin reload")
            return
        
        pm = get_plugin_manager()
        
        if args == "list":
            plugins = pm.list_plugins()
            if not plugins:
                print("\n❌ Keine Plugins gefunden.")
                return
            
            print(f"\n📦 Verfügbare Plugins ({len(plugins)}):")
            print("=" * 80)
            
            # Group by type
            by_type = {}
            for plugin in plugins:
                ptype = plugin.get('type', 'unknown')
                if ptype not in by_type:
                    by_type[ptype] = []
                by_type[ptype].append(plugin)
            
            for ptype, plugin_list in by_type.items():
                print(f"\n🔸 {ptype.upper()}:")
                for plugin in plugin_list:
                    name = plugin.get('name', 'Unknown')
                    plugin_id = plugin.get('id', 'unknown')
                    version = plugin.get('version', '1.0.0')
                    description = plugin.get('description', 'No description')
                    category = plugin.get('category', 'General')
                    print(f"  • {name} (ID: {plugin_id}, v{version})")
                    print(f"    {description}")
                    print(f"    Category: {category}")
            
            print("\n" + "=" * 80)
        
        elif args == "reload":
            print("\n🔄 Lade alle Plugins neu...")
            try:
                pm.reload_plugins()
                stats = pm.get_stats()
                print(f"✅ Plugins neu geladen: {stats['total_plugins']} Plugins registriert")
                
                # Show summary by type
                print("\n📊 Plugin-Übersicht:")
                for ptype, count in stats['by_type'].items():
                    print(f"  • {ptype}: {count}")
            except Exception as e:
                logger.error(f"❌ Fehler beim Reload: {e}")
                import traceback
                traceback.print_exc()
        
        else:
            logger.debug("Verwendung: plugin list | plugin reload")
