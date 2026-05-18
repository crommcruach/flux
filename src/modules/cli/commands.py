"""
Command Executor - Unified command handling for CLI and Web Console
"""
from ..core.logger import get_logger

logger = get_logger(__name__)


class CommandResult:
    """Standardized command result."""
    
    def __init__(self, success=True, message="", data=None, error=None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        result = {
            "success": self.success,
            "message": self.message
        }
        if self.data:
            result["data"] = self.data
        if self.error:
            result["error"] = self.error
        return result
    
    def __str__(self):
        """String representation for CLI output."""
        if self.success:
            return self.message
        else:
            return f"❌ {self.message}" + (f"\n{self.error}" if self.error else "")


class CommandExecutor:
    """
    Unified command executor for both CLI and Web Console.
    Handles all playback, configuration, and system commands.
    """
    
    def __init__(self, player_provider, dmx_controller, video_dir, data_dir, config):
        """
        Initialize command executor.
        
        Args:
            player_provider: Callable that returns current player instance
            dmx_controller: DMX controller instance (deprecated - now None)
            video_dir: Path to video directory
            data_dir: Path to data directory
            config: Configuration dictionary
        """
        self.player_provider = player_provider
        self.video_dir = video_dir
        self.data_dir = data_dir
        self.config = config
    
    @property
    def player(self):
        """Get current player instance."""
        return self.player_provider() if callable(self.player_provider) else self.player_provider
    
    def execute(self, command_string):
        """
        Execute a command string.
        
        Args:
            command_string: Full command string (e.g., "start", "brightness 50", "video:test.mp4")
            
        Returns:
            CommandResult: Standardized result object
        """
        command_string = command_string.strip()
        
        if not command_string:
            return CommandResult(False, "Empty command")
        
        # Check for prefix commands (video:, script:)
        if ':' in command_string:
            prefix, target = command_string.split(':', 1)
            prefix = prefix.lower().strip()
            target = target.strip()
            
            if prefix == 'video':
                return self._handle_video_load(target)
            elif prefix == 'script':
                return self._handle_script_load(target)
        
        # Parse command and arguments
        parts = command_string.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None
        
        # Route to appropriate handler
        handler_map = {
            # Playback
            'start': self._handle_start,
            'stop': self._handle_stop,
            'pause': self._handle_pause,
            'resume': self._handle_resume,
            'restart': self._handle_restart,
            
            # Settings
            'brightness': self._handle_brightness,
            'speed': self._handle_speed,
            'fps': self._handle_fps,
            'loop': self._handle_loop,
            'hue': self._handle_hue,
            
            # Art-Net
            'blackout': self._handle_blackout,
            'test': self._handle_test,
            'ip': self._handle_ip,
            'universe': self._handle_universe,
            'delta': self._handle_delta,
            
            # Info
            'status': self._handle_status,
            'info': self._handle_info,
            'stats': self._handle_stats,
            'debug': self._handle_debug,
            
            # Video/Script
            'list': self._handle_list,
            'videos': self._handle_videos,
            'scripts': self._handle_scripts,
            
            # System
            'help': self._handle_help,
            'display': self._handle_display,
        }
        
        handler = handler_map.get(command)
        
        if handler:
            try:
                return handler(args)
            except Exception as e:
                logger.error(f"Command execution error: {e}", exc_info=True)
                return CommandResult(False, f"Error executing command", error=str(e))
        else:
            return CommandResult(False, f"Unknown command: {command}", error="Use 'help' for available commands")
    
    # === Playback Commands ===
    
    def _handle_start(self, args):
        """Start playback."""
        self.player.start()
        return CommandResult(True, "Playback started")
    
    def _handle_stop(self, args):
        """Stop playback."""
        self.player.stop()
        return CommandResult(True, "Playback stopped")
    
    def _handle_pause(self, args):
        """Pause playback."""
        self.player.pause()
        return CommandResult(True, "Playback paused")
    
    def _handle_resume(self, args):
        """Resume playback."""
        self.player.resume()
        return CommandResult(True, "Playback resumed")
    
    def _handle_restart(self, args):
        """Restart playback."""
        self.player.restart()
        return CommandResult(True, "Playback restarted")
    
    # === Settings Commands ===
    
    def _handle_brightness(self, args):
        """Set brightness."""
        if not args:
            return CommandResult(False, "Brightness value missing", error="Usage: brightness <0-100>")
        
        try:
            value = float(args)
            if value < 0 or value > 100:
                return CommandResult(False, "Brightness must be between 0 and 100")
            
            self.player.set_brightness(value)
            return CommandResult(True, f"Brightness set to {value}%", {"brightness": value})
        except ValueError:
            return CommandResult(False, "Invalid brightness value", error=f"'{args}' is not a number")
    
    def _handle_speed(self, args):
        """Set playback speed."""
        if not args:
            return CommandResult(False, "Speed value missing", error="Usage: speed <0.1-10.0>")
        
        try:
            value = float(args)
            if value <= 0:
                return CommandResult(False, "Speed must be greater than 0")
            
            self.player.set_speed(value)
            return CommandResult(True, f"Speed set to {value}x", {"speed": value})
        except ValueError:
            return CommandResult(False, "Invalid speed value", error=f"'{args}' is not a number")
    
    def _handle_fps(self, args):
        """Set FPS limit."""
        if not args:
            return CommandResult(False, "FPS value missing", error="Usage: fps <value>")
        
        try:
            value = int(args) if args.lower() != 'none' else None
            self.player.set_fps(value)
            msg = f"FPS limit set to {value}" if value else "FPS limit removed"
            return CommandResult(True, msg, {"fps": value})
        except ValueError:
            return CommandResult(False, "Invalid FPS value", error=f"'{args}' is not a number")
    
    def _handle_loop(self, args):
        """Set loop limit."""
        if not args:
            return CommandResult(False, "Loop value missing", error="Usage: loop <count>")
        
        try:
            value = int(args)
            self.player.set_loop_limit(value)
            msg = f"Loop limit set to {value}" if value > 0 else "Endless loop activated"
            return CommandResult(True, msg, {"loop_limit": value})
        except ValueError:
            return CommandResult(False, "Invalid loop value", error=f"'{args}' is not a number")
    
    def _handle_hue(self, args):
        """Set hue shift."""
        if not args:
            return CommandResult(False, "Hue value missing", error="Usage: hue <0-360>")
        
        try:
            value = float(args)
            if value < 0 or value > 360:
                return CommandResult(False, "Hue must be between 0 and 360")
            
            self.player.set_hue_shift(value)
            return CommandResult(True, f"Hue Shift auf {value}° gesetzt", {"hue_shift": value})
        except ValueError:
            return CommandResult(False, "Invalid hue value", error=f"'{args}' is not a number")
    
    # === Art-Net Commands ===
    
    def _handle_blackout(self, args):
        """Activate blackout."""
        self.player.blackout()
        return CommandResult(True, "Blackout aktiviert")
    
    def _handle_test(self, args):
        """Send test pattern."""
        color = args.lower() if args else 'red'
        valid_colors = ['red', 'green', 'blue', 'white', 'gradient']
        
        if color not in valid_colors:
            return CommandResult(False, f"Invalid color: {color}", error=f"Valid colors: {', '.join(valid_colors)}")
        
        self.player.test_pattern(color)
        return CommandResult(True, f"Testmuster '{color}' gesendet", {"color": color})
    
    def _handle_ip(self, args):
        """Set Art-Net target IP."""
        if not args:
            return CommandResult(True, f"Current IP: {self.player.target_ip}", {"ip": self.player.target_ip})
        
        # Validate IP format
        parts = args.split('.')
        if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return CommandResult(False, "Invalid IP address", error=f"'{args}' is not a valid IP")
        
        self.player.target_ip = args
        return CommandResult(True, f"Art-Net Ziel-IP auf {args} gesetzt (restart required)", {"ip": args})
    
    def _handle_universe(self, args):
        """Set Art-Net start universe."""
        if not args:
            return CommandResult(True, f"Current universe: {self.player.start_universe}", {"universe": self.player.start_universe})
        
        try:
            value = int(args)
            if value < 0 or value > 32767:
                return CommandResult(False, "Universe must be between 0 and 32767")
            
            self.player.start_universe = value
            return CommandResult(True, f"Start-Universum auf {value} gesetzt (restart required)", {"universe": value})
        except ValueError:
            return CommandResult(False, "Invalid universe value", error=f"'{args}' is not a number")
    
    def _handle_delta(self, args):
        """Control Art-Net delta-encoding optimization (OLD SYSTEM - REMOVED)."""
        return CommandResult(False, "Delta-Encoding command removed - old Art-Net system deprecated. Use routing system instead.")
    
    def _handle_debug(self, args):
        """Toggle CLI debug mode (console log level)."""
        import logging
        from ..core.logger import set_console_log_level, get_console_log_level
        
        if not args:
            # Show current status
            current_level = get_console_log_level()
            level_name = logging.getLevelName(current_level)
            is_debug = current_level <= logging.INFO
            
            lines = ["CLI Debug Mode:"]
            lines.append(f"  Status: {'ON' if is_debug else 'OFF'}")
            lines.append(f"  Console-Level: {level_name}")
            lines.append(f"  Output: {'All messages' if is_debug else 'Warnings & errors only'}")
            
            return CommandResult(True, "\n".join(lines), {
                "debug": is_debug,
                "level": level_name,
                "level_value": current_level
            })
        
        # Parse subcommand
        subcommand = args.lower().strip()
        
        if subcommand in ['on', 'enable', 'true', '1']:
            set_console_log_level(logging.INFO)
            return CommandResult(True, "Debug mode enabled (console shows INFO, DEBUG, WARNING, ERROR)", {"debug": True})
        
        elif subcommand in ['off', 'disable', 'false', '0']:
            set_console_log_level(logging.WARNING)
            return CommandResult(True, "Debug mode disabled (console shows only WARNING, ERROR)", {"debug": False})
        
        elif subcommand == 'verbose':
            set_console_log_level(logging.DEBUG)
            return CommandResult(True, "Verbose mode enabled (console shows all messages incl. DEBUG)", {"debug": True, "verbose": True})
        
        elif subcommand in ['status', 'info']:
            # Same as no args
            return self._handle_debug(None)
        
        else:
            return CommandResult(False, f"Unknown debug subcommand: {subcommand}", 
                              error="Verwendung: debug [on|off|verbose|status]")
    
    # === Info Commands ===
    
    def _handle_status(self, args):
        """Get player status."""
        status = self.player.status()
        return CommandResult(True, f"Status: {status}", {"status": status})
    
    def _handle_info(self, args):
        """Get player info."""
        info = self.player.get_info()
        
        # Format info for display
        lines = ["Player Information:"]
        lines.append(f"  Source: {info.get('source_name', 'Unknown')}")
        lines.append(f"  Type: {info.get('source_type', 'Unknown')}")
        lines.append(f"  Canvas: {info.get('canvas_width', 0)}x{info.get('canvas_height', 0)}")
        lines.append(f"  Points: {info.get('total_points', 0)}")
        lines.append(f"  Universes: {info.get('total_universes', 0)}")
        lines.append(f"  Brightness: {info.get('brightness', 0)}%")
        lines.append(f"  Speed: {info.get('speed', 1.0)}x")
        
        return CommandResult(True, "\n".join(lines), info)
    
    def _handle_stats(self, args):
        """Get live statistics."""
        stats = self.player.get_stats()
        
        lines = ["Live Statistics:"]
        lines.append(f"  FPS: {stats.get('fps', 0)}")
        lines.append(f"  Frames: {stats.get('frames', 0)}")
        lines.append(f"  Current: {stats.get('current_frame', 0)}/{stats.get('total_frames', 0)}")
        lines.append(f"  Runtime: {stats.get('runtime', '00:00')}")
        
        return CommandResult(True, "\n".join(lines), stats)
    
    # === Video/Script Commands ===
    
    def _handle_list(self, args):
        """List videos or scripts."""
        # Default to videos
        return self._handle_videos(args)
    
    def _handle_videos(self, args):
        """List all videos."""
        import os
        from ..core.constants import VIDEO_EXTENSIONS
        
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for filename in files:
                if filename.lower().endswith(VIDEO_EXTENSIONS):
                    rel_path = os.path.relpath(os.path.join(root, filename), self.video_dir)
                    videos.append(rel_path)
        
        videos.sort()
        
        if not videos:
            return CommandResult(True, "No videos found", {"videos": []})
        
        lines = [f"Videos found ({len(videos)}):"]
        for i, video in enumerate(videos, 1):
            lines.append(f"  {i}. {video}")
        
        return CommandResult(True, "\n".join(lines), {"videos": videos, "count": len(videos)})
    
    def _handle_scripts(self, args):
        """List all scripts."""
        return CommandResult(True, "Script system deprecated. Use generators plugin.", {"scripts": []})
        """Load a video."""
        import os
        from ..player.sources import VideoSource
        from ..core.constants import VIDEO_EXTENSIONS
        
        # Find video
        videos = []
        for root, dirs, files in os.walk(self.video_dir):
            for filename in files:
                if filename.lower().endswith(VIDEO_EXTENSIONS):
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, self.video_dir)
                    videos.append((filename, rel_path, full_path))
        
        # Search for matching video
        search_name = video_name.lower().replace('/', '\\')
        matching = [v for v in videos if search_name in v[1].lower() or search_name in v[0].lower()]
        
        if not matching:
            return CommandResult(False, f"Video not found: {video_name}")
        
        if len(matching) > 1:
            lines = ["Multiple videos found:"]
            for i, (name, rel, full) in enumerate(matching, 1):
                lines.append(f"  {i}. {rel}")
            lines.append("\nPlease be more specific.")
            return CommandResult(False, "\n".join(lines), {"matches": [v[1] for v in matching]})
        
        video_path = matching[0][2]
        
        # Create VideoSource
        video_source = VideoSource(
            video_path,
            self.player.canvas_width,
            self.player.canvas_height,
            self.config
        )
        
        # Switch source
        success = self.player.switch_source(video_source)
        
        if success:
            return CommandResult(True, f"Video loaded: {os.path.basename(video_path)}", {"video": video_path})
        else:
            return CommandResult(False, "Error loading video")
    
    # === System Commands ===

    def _handle_display(self, args):
        """Manage outputs: start/stop/restart individual or all outputs.

        Syntax:
          display                        - list all outputs + status
          display status                 - same
          display start [<id>|all]       - enable output(s)
          display stop  [<id>|all]       - disable output(s)
          display restart [<id>|all]     - disable then re-enable output(s)
          display open  [<id>|all]       - alias for start
          display close [<id>|all]       - alias for stop
        """
        import time

        parts = (args or '').split(maxsplit=1)
        subcmd = parts[0].lower() if parts else ''
        target = parts[1].strip() if len(parts) > 1 else 'all'

        player = self.player
        om = getattr(player, 'output_manager', None) if player else None

        # ── status / list ────────────────────────────────────────────────────
        if subcmd in ('', 'status', 'list'):
            if om is None:
                return CommandResult(False, "Output manager not available")
            lines = [f"Outputs ({len(om.outputs)}):"]
            for oid, out in om.outputs.items():
                state = 'enabled' if out.enabled else 'disabled'
                otype = out.config.get('type', 'unknown')
                lines.append(f"  {oid}  [{otype}]  {state}")
            return CommandResult(True, "\n".join(lines),
                                 {"outputs": {k: v.enabled for k, v in om.outputs.items()}})

        # ── resolve target output ids ─────────────────────────────────────────
        def _resolve_ids(target_str):
            if om is None:
                return None, "Output manager not available"
            if target_str in ('all', ''):
                return list(om.outputs.keys()), None
            if target_str in om.outputs:
                return [target_str], None
            # partial match
            matches = [k for k in om.outputs if target_str in k]
            if not matches:
                return None, f"No output matching '{target_str}'. Available: {list(om.outputs.keys())}"
            return matches, None

        # ── start / open ──────────────────────────────────────────────────────
        if subcmd in ('start', 'open'):
            ids, err = _resolve_ids(target)
            if err:
                return CommandResult(False, err)
            results = []
            for oid in ids:
                out = om.outputs[oid]
                if out.enabled:
                    results.append(f"{oid}: already running")
                else:
                    ok = om.enable_output(oid)
                    results.append(f"{oid}: started" if ok else f"{oid}: failed to start")
            return CommandResult(True, "\n".join(results))

        # ── stop / close ──────────────────────────────────────────────────────
        if subcmd in ('stop', 'close'):
            ids, err = _resolve_ids(target)
            if err:
                return CommandResult(False, err)
            results = []
            for oid in ids:
                out = om.outputs[oid]
                if not out.enabled:
                    results.append(f"{oid}: already stopped")
                else:
                    om.disable_output(oid)
                    results.append(f"{oid}: stopped")
            return CommandResult(True, "\n".join(results))

        # ── restart / reopen ──────────────────────────────────────────────────
        if subcmd in ('restart', 'reopen'):
            ids, err = _resolve_ids(target)
            if err:
                return CommandResult(False, err)
            results = []
            for oid in ids:
                out = om.outputs[oid]
                if out.enabled:
                    om.disable_output(oid)
                    time.sleep(0.3)
                ok = om.enable_output(oid)
                results.append(f"{oid}: restarted" if ok else f"{oid}: failed to restart")
            return CommandResult(True, "\n".join(results))

        return CommandResult(False,
            "Usage: display [status|start|stop|restart] [<output-id>|all]",
            error=f"Unknown subcommand: '{subcmd}'")

    def _handle_help(self, args):
        """Show help message."""
        help_text = """
Available commands:

Playback:
  start              - Start playback
  stop               - Stop playback
  pause              - Pause
  resume             - Resume
  restart            - Restart

Settings:
  brightness <0-100> - Set brightness
  speed <factor>     - Speed (0.1-10.0)
  fps <value>        - Set FPS limit (none = no limit)
  loop <count>       - Loop limit (0 = endless)
  hue <0-360>        - Set hue shift

Art-Net:
  blackout           - All LEDs off
  test <color>       - Test pattern (red/green/blue/white/gradient)
  ip <address>       - Set target IP
  universe <number>  - Set start universe
  delta [on|off]     - Enable/disable delta encoding
  delta status       - Show delta encoding status
  delta threshold <n> - Set threshold
  delta interval <n> - Set full-frame interval

Video/Script:
  video:<name>       - Load video (e.g. video:test.mp4)
  script:<name>      - Load script (e.g. script:rainbow_wave)
  list / videos      - List all videos
  scripts            - List all scripts

Info:
  status             - Current status
  info               - Detailed information
  stats              - Live statistics
  debug [on|off]     - Toggle debug mode (console logging)
  debug verbose      - Verbose mode (incl. DEBUG messages)
  help               - Show this help

Display:
  display                    - List all outputs and their status
  display status             - Same as above
  display start [<id>|all]   - Start/enable output(s)
  display stop  [<id>|all]   - Stop/disable output(s)
  display restart [<id>|all] - Restart output(s)
"""
        return CommandResult(True, help_text.strip())
