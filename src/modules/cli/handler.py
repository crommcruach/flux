"""
CLI Command Handler - Central processing of all CLI commands
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
    """Processes CLI commands and delegates to corresponding components."""
    
    def __init__(self, player_manager, rest_api, video_dir, data_dir, config):
        # Use player_manager for central player access
        self.player_manager = player_manager
        self.rest_api = rest_api
        self.video_dir = video_dir
        self.data_dir = data_dir
        self.config = config
        self.base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        
        # Initialize unified command executor
        self.command_executor = CommandExecutor(
            player_provider=lambda: self.player_manager.player,
            video_dir=video_dir,
            data_dir=data_dir,
            config=config
        )
        
        # Tracking for next/back navigation
        self.current_video_path = None
        self.current_script_name = None
        self.video_list_cache = None
        self.script_list_cache = None
    
    @property
    def player(self):
        """Returns current player dynamically."""
        return self.player_manager.player
    
    def execute_command(self, command, args=None):
        """
        Executes a CLI command.
        
        Args:
            command: Command name (lowercase)
            args: Optional arguments as string
            
        Returns:
            tuple: (continue_loop, new_player) - continue_loop=False on exit, new_player if player was replaced
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
            print("\nShutting down application...")
            return (False, None)
        
        # Use CommandExecutor for standard commands
        result = self.command_executor.execute(full_command)
        
        # Print result to console
        print(str(result))
        
        # Return continue flag
        return (True, None)
    
    # === Video management ===
    
    def _handle_videos_list(self):
        """Lists all videos."""
        from ..core.utils import list_videos
        list_videos(self.video_dir)
    
    def _handle_video_load(self, command):
        """Loads and starts a video."""
        from ..player.sources import VideoSource
        
        # Extract video name
        video_name = command.split(':', 1)[1].strip()
        
        if not video_name:
            logger.debug("Usage: video:<name>")
            return (True, None)
        
        # Sammle alle Videos
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for f in files:
                if f.lower().endswith(VIDEO_EXTENSIONS):
                    videos.append(os.path.join(root, f))
        
        # Normalize search string (allow both slash styles)
        search_name = video_name.lower().replace('/', '\\')
        
        # Search for matching video - check both filename and relative path
        matching = []
        for v in videos:
            rel_path = os.path.relpath(v, self.video_dir).lower()
            basename = os.path.basename(v).lower()
            if search_name in rel_path or search_name in basename:
                matching.append(v)
        
        if not matching:
            logger.warning(f"No video found with: {video_name}")
            return (True, None)
        
        if len(matching) > 1:
            logger.debug(f"Multiple videos found:")
            for v in matching:
                # Show relative path to video_dir for better overview
                rel_path = os.path.relpath(v, self.video_dir)
                logger.debug(f"  - {rel_path}")
            logger.debug("Please be more specific (e.g. 'video:channel_1/test' or full path).")
            return (True, None)
        
        # Erstelle neue VideoSource
        video_source = VideoSource(
            matching[0],
            self.player.canvas_width,
            self.player.canvas_height,
            self.config
        )
        
        # Switch source (unified player persists)
        success = self.player.switch_source(video_source)
        
        if not success:
            logger.error(f"Error loading video: {os.path.basename(matching[0])}")
            return (True, None)
        
        # Tracking
        self.current_video_path = matching[0]
        self.current_script_name = None
        
        logger.debug(f"✓ Video loaded: {os.path.basename(matching[0])}")
        
        return (True, None)
    
    def _get_all_videos(self):
        """Collects all videos sorted."""
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
        """Collects all scripts sorted."""
        if self.script_list_cache:
            return self.script_list_cache
        
        scripts = []  # Script system deprecated
        
        self.script_list_cache = [s['filename'] for s in scripts]
        return self.script_list_cache
    
    def _handle_next(self):
        """Loads next video or script."""
        # Check whether video or script is active
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                logger.debug("No videos available")
                return (True, None)
            
            try:
                current_idx = videos.index(self.current_video_path)
                next_idx = (current_idx + 1) % len(videos)
                next_video = videos[next_idx]
                
                # Stop current video
                if self.player.is_playing:
                    self.player.stop()
                    time.sleep(0.5)
                
                # Load next video
                if self.player.load_video(next_video):
                    self.current_video_path = next_video
                    self.player.start()
                    logger.debug(f"Next video: {os.path.basename(next_video)}")
            except ValueError:
                logger.debug("Current video not found in list")
        
        elif self.current_script_name:
            logger.warning("⚠️  Script navigation is deprecated - use generator plugins from web UI")
            return (True, None)
        else:
            logger.debug("No video or script active")
        
        return (True, None)
    
    def _handle_back(self):
        """Loads previous video or script."""
        # Check whether video or script is active
        if self.current_video_path:
            videos = self._get_all_videos()
            if not videos:
                logger.debug("No videos available")
                return (True, None)
            
            try:
                current_idx = videos.index(self.current_video_path)
                prev_idx = (current_idx - 1) % len(videos)
                prev_video = videos[prev_idx]
                
                # Stop current video
                if self.player.is_playing:
                    self.player.stop()
                    time.sleep(0.5)
                
                # Load previous video
                if self.player.load_video(prev_video):
                    self.current_video_path = prev_video
                    self.player.start()
                    logger.debug(f"Previous video: {os.path.basename(prev_video)}")
            except ValueError:
                logger.debug("Current video not found in list")
        
        elif self.current_script_name:
            logger.warning("⚠️  Script navigation is deprecated - use generator plugins from web UI")
            return (True, None)
        else:
            logger.debug("No video or script active")
        
        return (True, None)
    
    # === REST API ===
    
    def _handle_api(self, args):
        """Controls REST API."""
        if not args:
            logger.debug("Usage: api start [port] | api stop")
            return
        
        if args == "start":
            parts = args.split()
            port = int(parts[1]) if len(parts) > 1 else self.config['api']['port']
            self.rest_api.start(port=port)
        elif args == "stop":
            self.rest_api.stop()
        else:
            logger.debug("Verwendung: api start [port] | api stop")
    
    # === Points management ===
    
    def _handle_points(self, args):
        """Manages points lists."""
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
            logger.debug("Usage: points list | points validate [name] | points switch <name> | points reload")
            return None
    
    def _handle_points_validate(self, args):
        """Validates a points list."""
        from ..core.validator import validate_points_file
        
        parts = args.split(maxsplit=1)
        if len(parts) > 1:
            search_name = parts[1]
            json_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json')]
            matching = [f for f in json_files if search_name.lower() in f.lower()]
            if matching:
                file_path = os.path.join(self.data_dir, matching[0])
                logger.debug(f"\nValidating: {matching[0]}")
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
                logger.warning(f"No points list found with: {search_name}")
        else:
            # Validiere aktuelle Liste
            logger.debug(f"\nValidating: {os.path.basename(self.player.points_json_path)}")
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
        """Switches points list."""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            logger.debug("Usage: points switch <name>")
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
            
            logger.debug(f"✓ Points list switched: {matching[0]}")
            logger.debug(f"  Number of points: {self.player.total_points}")
            logger.debug(f"  Required universes: {self.player.required_universes}")
            
            if was_playing:
                self.player.start()
            
            return self.player
        except Exception as e:
            logger.error(f"Error loading points list: {e}")
            return None
    
    def _handle_points_reload(self):
        """Reloads current points list."""
        was_playing = self.player.is_playing
        current_points_path = self.player.points_json_path
        if was_playing:
            self.player.stop()
        
        try:
            # Reload points in existing player
            self.player.reload_points()
            
            logger.debug(f"✓ Points list reloaded: {os.path.basename(current_points_path)}")
            logger.debug(f"  Number of points: {self.player.total_points}")
            logger.debug(f"  Required universes: {self.player.required_universes}")
            
            if was_playing:
                self.player.start()
            
            return self.player
        except Exception as e:
            logger.error(f"Error reloading points list: {e}")
            return None
    
    # === Settings ===
    
    def _handle_fps(self, args):
        """Sets FPS."""
        if args:
            self.player.set_fps(args)
        else:
            logger.debug("Usage: fps <value>")
    
    def _handle_speed(self, args):
        """Sets playback speed."""
        if args:
            self.player.set_speed(args)
        else:
            logger.debug("Usage: speed <factor>")
    
    def _handle_brightness(self, args):
        """Sets brightness."""
        if args:
            self.player.set_brightness(args)
        else:
            logger.debug("Usage: brightness <0-100>")
    
    def _handle_loop(self, args):
        """Sets loop limit."""
        if args:
            try:
                limit = int(args)
                self.player.set_loop_limit(limit)
                logger.debug(f"Loop limit set: {limit} (0 = infinite)")
            except ValueError:
                logger.warning("Invalid value! Use a number.")
        else:
            logger.debug("Usage: loop <count>")
    
    # === Art-Net ===
    
    def _handle_test(self, args):
        """Shows test pattern."""
        color = args if args else 'red'
        self.player.test_pattern(color)
    
    def _handle_ip(self, args):
        """Sets or shows target IP."""
        if args:
            self.player.target_ip = args
            logger.debug(f"Target IP set: {args}")
            logger.debug("NOTE: Restart video for change to take effect")
        else:
            logger.debug(f"Current IP: {self.player.target_ip}")
    
    def _handle_universe(self, args):
        """Sets or shows start universe."""
        if args:
            try:
                self.player.start_universe = int(args)
                logger.debug(f"Start universe set: {args}")
                logger.debug("NOTE: Restart video for change to take effect")
            except ValueError:
                logger.warning("Invalid value!")
        else:
            logger.debug(f"Current start universe: {self.player.start_universe}")
    
    def _handle_artnet(self, args):
        """Manages Art-Net configuration (subcommands: map, show)."""
        if not args:
            logger.debug("❌ Usage: artnet <subcommand> [args]")
            logger.debug("")
            logger.debug("Subcommands:")
            logger.debug("  artnet map <format> <universes>  - Sets RGB channel order")
            logger.debug("  artnet show                      - Shows current channel mappings")
            logger.debug("")
            logger.debug("Formats: RGB, GRB, BGR, RBG, GBR, BRG")
            logger.debug("")
            logger.debug("Examples:")
            logger.debug("  artnet map rgb 0-4       - Set universes 0-4 to RGB")
            logger.debug("  artnet map grb 5         - Set universe 5 to GRB")
            logger.debug("  artnet map bgr 6-10      - Set universes 6-10 to BGR")
            logger.debug("  artnet show              - Show all mappings")
            return
        
        parts = args.split(maxsplit=2)
        subcommand = parts[0].lower()
        
        if subcommand == "map":
            if len(parts) < 3:
                logger.debug("❌ Usage: artnet map <format> <universes>")
                logger.debug("Example: artnet map grb 0-5")
                return
            self._handle_artnet_map(parts[1], parts[2])
        
        elif subcommand == "show":
            self._handle_artnet_show()
        
        else:
            logger.warning(f"❌ Unknown subcommand: {subcommand}")
            logger.debug("Available: map, show")
    
    def _handle_artnet_map(self, format_str, universes_str):
        """Sets RGB channel order for universes."""
        # Validiere Format
        format_str = format_str.upper()
        valid_formats = ['RGB', 'GRB', 'BGR', 'RBG', 'GBR', 'BRG']
        if format_str not in valid_formats:
            logger.warning(f"❌ Invalid format: {format_str}")
            logger.debug(f"Available: {', '.join(valid_formats)}")
            return
        
        # Parse universe range (e.g. "0-5" or "3")
        try:
            if '-' in universes_str:
                start, end = universes_str.split('-')
                start_uni = int(start)
                end_uni = int(end)
                if start_uni > end_uni:
                    logger.warning("❌ Start universe must be less than end universe")
                    return
                universe_list = list(range(start_uni, end_uni + 1))
            else:
                universe_list = [int(universes_str)]
        except ValueError:
            logger.warning(f"❌ Invalid universe range: {universes_str}")
            logger.debug("Use format: '0-5' or '3'")
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
            
            # Set mapping for all universes in range
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
            logger.debug("💾 Configuration saved to config.json")
            logger.debug("⚠️  NOTE: Restart video for the change to take effect")
            
        except Exception as e:
            logger.error(f"❌ Error saving: {e}")
    
    def _handle_artnet_show(self):
        """Shows current RGB channel mappings."""
        config_path = os.path.join(self.base_path, "config.json")
        try:
            if not os.path.exists(config_path):
                logger.warning("⚠️  No config.json found")
                return
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            universe_configs = config_data.get('artnet', {}).get('universe_configs', {})
            
            if not universe_configs:
                logger.warning("⚠️  No universe configurations found")
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
                logger.debug("No specific universes configured")
            else:
                for uni in universe_nums:
                    format_str = universe_configs[uni]
                    logger.debug(f"Universe {uni:>3}: {format_str}")
            
            logger.debug("=" * 40)
            logger.debug("")
            
        except Exception as e:
            logger.error(f"❌ Error loading: {e}")
    
    # === Info ===
    
    def _handle_status(self):
        """Shows status."""
        logger.debug(self.player.status())
    
    def _handle_info(self):
        """Shows information."""
        info = self.player.get_info()
        for key, value in info.items():
            logger.debug(f"{key}: {value}")
    
    def _handle_stats(self):
        """Shows statistics."""
        stats = self.player.get_stats()
        if isinstance(stats, dict):
            for key, value in stats.items():
                logger.debug(f"{key}: {value}")
        else:
            logger.debug(stats)
    
    # === System ===
    
    def _handle_help(self):
        """Shows help."""
        from ..core.utils import print_help
        print_help()
    
    # === Scripts ===
    
    def _handle_scripts(self, args):
        """Manages scripts."""
        logger.debug("Script system deprecated. Use generators plugin instead.")
        return
    
    def _handle_scripts_list(self, script_gen):
        """Lists all scripts."""
        scripts = script_gen.list_scripts()
        
        if not scripts:
            logger.debug("\nNo scripts found!")
            return
        
        logger.debug(f"\n{'='*60}")
        logger.debug(f"{'Script':<30} {'Description':<30}")
        logger.debug(f"{'='*60}")
        
        for script in scripts:
            name = script['name'][:28]
            desc = script.get('description', 'No description')[:28]
            logger.debug(f"{name:<30} {desc:<30}")
        
        logger.debug(f"{'='*60}")
        logger.debug(f"\nTotal {len(scripts)} script(s)")
        logger.debug("Verwendung: Use generators from the Sources tab in the web UI")
        logger.debug("⚠️  Script loading via CLI is no longer supported")
    
    def _handle_open(self):
        """Opens web interface in browser (undocumented)."""
        import webbrowser
        port = self.config.get('api', {}).get('port', 5000)
        
        if not self.rest_api.is_running:
            logger.warning("⚠️  REST API is not active")
            logger.debug("Start API with: api start")
            return
        
        url = f"http://localhost:{port}"
        logger.debug(f"Opening browser: {url}")
        webbrowser.open(url)
    
    def _handle_clear(self):
        """Clears the console display."""
        # Clear REST API console log
        if self.rest_api:
            self.rest_api.clear_console()
            logger.debug("✓ Console cleared")
    
    def _handle_plugin(self, args):
        """Manages plugins (list, reload)."""
        from ..plugins.manager import get_plugin_manager
        
        if not args:
            logger.debug("Usage: plugin list | plugin reload")
            return
        
        pm = get_plugin_manager()
        
        if args == "list":
            plugins = pm.list_plugins()
            if not plugins:
                print("\n❌ Keine Plugins gefunden.")
                return
            
                print(f"\n📦 Available plugins ({len(plugins)}):")
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
            print("\n🔄 Reloading all plugins...")
            try:
                pm.reload_plugins()
                stats = pm.get_stats()
                print(f"✅ Plugins neu geladen: {stats['total_plugins']} Plugins registriert")
                
                # Show summary by type
                print("\n📊 Plugin overview:")
                for ptype, count in stats['by_type'].items():
                    print(f"  • {ptype}: {count}")
            except Exception as e:
                logger.error(f"❌ Error reloading: {e}")
                import traceback
                traceback.print_exc()
        
        else:
            logger.debug("Verwendung: plugin list | plugin reload")
