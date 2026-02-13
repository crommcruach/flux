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
        self.dmx_controller = dmx_controller  # Deprecated - DMX input removed
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
            return CommandResult(False, "Leerer Befehl")
        
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
        }
        
        handler = handler_map.get(command)
        
        if handler:
            try:
                return handler(args)
            except Exception as e:
                logger.error(f"Command execution error: {e}", exc_info=True)
                return CommandResult(False, f"Fehler beim Ausführen des Befehls", error=str(e))
        else:
            return CommandResult(False, f"Unbekannter Befehl: {command}", error="Nutze 'help' für verfügbare Befehle")
    
    # === Playback Commands ===
    
    def _handle_start(self, args):
        """Start playback."""
        self.player.start()
        return CommandResult(True, "Wiedergabe gestartet")
    
    def _handle_stop(self, args):
        """Stop playback."""
        self.player.stop()
        return CommandResult(True, "Wiedergabe gestoppt")
    
    def _handle_pause(self, args):
        """Pause playback."""
        self.player.pause()
        return CommandResult(True, "Wiedergabe pausiert")
    
    def _handle_resume(self, args):
        """Resume playback."""
        self.player.resume()
        return CommandResult(True, "Wiedergabe fortgesetzt")
    
    def _handle_restart(self, args):
        """Restart playback."""
        self.player.restart()
        return CommandResult(True, "Wiedergabe neu gestartet")
    
    # === Settings Commands ===
    
    def _handle_brightness(self, args):
        """Set brightness."""
        if not args:
            return CommandResult(False, "Helligkeit-Wert fehlt", error="Verwendung: brightness <0-100>")
        
        try:
            value = float(args)
            if value < 0 or value > 100:
                return CommandResult(False, "Helligkeit muss zwischen 0 und 100 liegen")
            
            self.player.set_brightness(value)
            return CommandResult(True, f"Helligkeit auf {value}% gesetzt", {"brightness": value})
        except ValueError:
            return CommandResult(False, "Ungültiger Helligkeits-Wert", error=f"'{args}' ist keine Zahl")
    
    def _handle_speed(self, args):
        """Set playback speed."""
        if not args:
            return CommandResult(False, "Geschwindigkeits-Wert fehlt", error="Verwendung: speed <0.1-10.0>")
        
        try:
            value = float(args)
            if value <= 0:
                return CommandResult(False, "Geschwindigkeit muss größer als 0 sein")
            
            self.player.set_speed(value)
            return CommandResult(True, f"Geschwindigkeit auf {value}x gesetzt", {"speed": value})
        except ValueError:
            return CommandResult(False, "Ungültiger Geschwindigkeits-Wert", error=f"'{args}' ist keine Zahl")
    
    def _handle_fps(self, args):
        """Set FPS limit."""
        if not args:
            return CommandResult(False, "FPS-Wert fehlt", error="Verwendung: fps <wert>")
        
        try:
            value = int(args) if args.lower() != 'none' else None
            self.player.set_fps(value)
            msg = f"FPS-Limit auf {value} gesetzt" if value else "FPS-Limit entfernt"
            return CommandResult(True, msg, {"fps": value})
        except ValueError:
            return CommandResult(False, "Ungültiger FPS-Wert", error=f"'{args}' ist keine Zahl")
    
    def _handle_loop(self, args):
        """Set loop limit."""
        if not args:
            return CommandResult(False, "Loop-Wert fehlt", error="Verwendung: loop <anzahl>")
        
        try:
            value = int(args)
            self.player.set_loop_limit(value)
            msg = f"Loop-Limit auf {value} gesetzt" if value > 0 else "Endlos-Loop aktiviert"
            return CommandResult(True, msg, {"loop_limit": value})
        except ValueError:
            return CommandResult(False, "Ungültiger Loop-Wert", error=f"'{args}' ist keine Zahl")
    
    def _handle_hue(self, args):
        """Set hue shift."""
        if not args:
            return CommandResult(False, "Hue-Wert fehlt", error="Verwendung: hue <0-360>")
        
        try:
            value = float(args)
            if value < 0 or value > 360:
                return CommandResult(False, "Hue muss zwischen 0 und 360 liegen")
            
            self.player.set_hue_shift(value)
            return CommandResult(True, f"Hue Shift auf {value}° gesetzt", {"hue_shift": value})
        except ValueError:
            return CommandResult(False, "Ungültiger Hue-Wert", error=f"'{args}' ist keine Zahl")
    
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
            return CommandResult(False, f"Ungültige Farbe: {color}", error=f"Gültige Farben: {', '.join(valid_colors)}")
        
        self.player.test_pattern(color)
        return CommandResult(True, f"Testmuster '{color}' gesendet", {"color": color})
    
    def _handle_ip(self, args):
        """Set Art-Net target IP."""
        if not args:
            return CommandResult(True, f"Aktuelle IP: {self.player.target_ip}", {"ip": self.player.target_ip})
        
        # Validate IP format
        parts = args.split('.')
        if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return CommandResult(False, "Ungültige IP-Adresse", error=f"'{args}' ist keine gültige IP")
        
        self.player.target_ip = args
        return CommandResult(True, f"Art-Net Ziel-IP auf {args} gesetzt (restart required)", {"ip": args})
    
    def _handle_universe(self, args):
        """Set Art-Net start universe."""
        if not args:
            return CommandResult(True, f"Aktuelles Universum: {self.player.start_universe}", {"universe": self.player.start_universe})
        
        try:
            value = int(args)
            if value < 0 or value > 32767:
                return CommandResult(False, "Universum muss zwischen 0 und 32767 liegen")
            
            self.player.start_universe = value
            return CommandResult(True, f"Start-Universum auf {value} gesetzt (restart required)", {"universe": value})
        except ValueError:
            return CommandResult(False, "Ungültiger Universum-Wert", error=f"'{args}' ist keine Zahl")
    
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
            
            lines = ["CLI Debug-Modus:"]
            lines.append(f"  Status: {'AN' if is_debug else 'AUS'}")
            lines.append(f"  Console-Level: {level_name}")
            lines.append(f"  Ausgabe: {'Alle Meldungen' if is_debug else 'Nur Warnungen & Fehler'}")
            
            return CommandResult(True, "\n".join(lines), {
                "debug": is_debug,
                "level": level_name,
                "level_value": current_level
            })
        
        # Parse subcommand
        subcommand = args.lower().strip()
        
        if subcommand in ['on', 'enable', 'true', '1']:
            set_console_log_level(logging.INFO)
            return CommandResult(True, "Debug-Modus aktiviert (Console zeigt INFO, DEBUG, WARNING, ERROR)", {"debug": True})
        
        elif subcommand in ['off', 'disable', 'false', '0']:
            set_console_log_level(logging.WARNING)
            return CommandResult(True, "Debug-Modus deaktiviert (Console zeigt nur WARNING, ERROR)", {"debug": False})
        
        elif subcommand == 'verbose':
            set_console_log_level(logging.DEBUG)
            return CommandResult(True, "Verbose-Modus aktiviert (Console zeigt alle Meldungen inkl. DEBUG)", {"debug": True, "verbose": True})
        
        elif subcommand in ['status', 'info']:
            # Same as no args
            return self._handle_debug(None)
        
        else:
            return CommandResult(False, f"Unbekannter Debug-Subbefehl: {subcommand}", 
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
            return CommandResult(True, "Keine Videos gefunden", {"videos": []})
        
        lines = [f"Gefundene Videos ({len(videos)}):"]
        for i, video in enumerate(videos, 1):
            lines.append(f"  {i}. {video}")
        
        return CommandResult(True, "\n".join(lines), {"videos": videos, "count": len(videos)})
    
    def _handle_scripts(self, args):
        """List all scripts."""
        # from .script_generator import ScriptGenerator  # Deprecated - using plugin system
        return CommandResult(True, "Script system deprecated. Use generators plugin.", {"scripts": []})
        
        if not scripts:
            return CommandResult(True, "Keine Scripts gefunden", {"scripts": []})
        
        lines = [f"Verfügbare Scripts ({len(scripts)}):"]
        for i, script in enumerate(scripts, 1):
            name = script['name']
            desc = script.get('description', 'Keine Beschreibung')
            lines.append(f"  {i}. {name} - {desc}")
        
        return CommandResult(True, "\n".join(lines), {"scripts": scripts, "count": len(scripts)})
    
    def _handle_video_load(self, video_name):
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
            return CommandResult(False, f"Video nicht gefunden: {video_name}")
        
        if len(matching) > 1:
            lines = ["Mehrere Videos gefunden:"]
            for i, (name, rel, full) in enumerate(matching, 1):
                lines.append(f"  {i}. {rel}")
            lines.append("\nBitte spezifischer wählen.")
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
            return CommandResult(True, f"Video geladen: {os.path.basename(video_path)}", {"video": video_path})
        else:
            return CommandResult(False, "Fehler beim Laden des Videos")
    
    # === System Commands ===
    
    def _handle_help(self, args):
        """Show help message."""
        help_text = """
Verfügbare Befehle:

Playback:
  start              - Wiedergabe starten
  stop               - Wiedergabe stoppen
  pause              - Pausieren
  resume             - Fortsetzen
  restart            - Neu starten

Einstellungen:
  brightness <0-100> - Helligkeit setzen
  speed <faktor>     - Geschwindigkeit (0.1-10.0)
  fps <wert>         - FPS-Limit setzen (none = kein Limit)
  loop <anzahl>      - Loop-Limit (0 = endlos)
  hue <0-360>        - Hue Shift setzen

Art-Net:
  blackout           - Alle LEDs aus
  test <farbe>       - Testmuster (red/green/blue/white/gradient)
  ip <adresse>       - Ziel-IP setzen
  universe <nummer>  - Start-Universum setzen
  delta [on|off]     - Delta-Encoding aktivieren/deaktivieren
  delta status       - Delta-Encoding Status anzeigen
  delta threshold <n> - Schwellwert setzen
  delta interval <n> - Full-Frame Intervall setzen

Video/Script:
  video:<name>       - Video laden (z.B. video:test.mp4)
  script:<name>      - Script laden (z.B. script:rainbow_wave)
  list / videos      - Alle Videos auflisten
  scripts            - Alle Scripts auflisten

Info:
  status             - Aktueller Status
  info               - Detaillierte Informationen
  stats              - Live-Statistiken
  debug [on|off]     - Debug-Modus umschalten (Console-Logging)
  debug verbose      - Verbose-Modus (inkl. DEBUG-Meldungen)
  help               - Diese Hilfe anzeigen
"""
        return CommandResult(True, help_text.strip())
