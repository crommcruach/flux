"""
Zentrales Logging-System für Flux
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler


class FluxLogger:
    """Zentraler Logger mit Datei- und Konsolen-Ausgabe."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FluxLogger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not FluxLogger._initialized:
            self.setup_logging()  # Wird mit Defaults initialisiert
            FluxLogger._initialized = True
    
    def _cleanup_old_logs(self, log_dir, max_files=10):
        """
        Clean up old log files, keeping only the most recent ones.
        
        Args:
            log_dir: Path to log directory
            max_files: Maximum number of log files to keep (0 = infinite, keep all)
        """
        # Skip cleanup if max_files is 0 (infinite)
        if max_files == 0:
            return
        
        try:
            # Get all flux log files
            log_files = sorted(
                log_dir.glob('flux_*.log*'),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Remove old files beyond max_files limit
            for old_file in log_files[max_files:]:
                try:
                    old_file.unlink()
                    print(f"Deleted old log file: {old_file.name}")
                except Exception as e:
                    print(f"Failed to delete {old_file.name}: {e}")
        
        except Exception as e:
            print(f"Log cleanup failed: {e}")
    
    def setup_logging(self, log_dir='logs', log_level=logging.INFO, console_level=logging.WARNING, max_log_files=10):
        """
        Richtet das Logging-System ein.
        
        Args:
            log_dir: Verzeichnis für Log-Dateien
            log_level: Logging-Level für Datei (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_level: Logging-Level für Konsole (Standard: WARNING)
            max_log_files: Maximum number of log files to keep (0 = infinite)
        """
        # Log-Verzeichnis erstellen
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # Cleanup old log files (keep only last N files, or all if max_log_files=0)
        self._cleanup_old_logs(log_path, max_files=max_log_files)
        
        # Timestamp für Log-Datei
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = log_path / f'flux_{timestamp}.log'
        
        # Root Logger konfigurieren
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Entferne existierende Handler
        root_logger.handlers.clear()
        
        # Formatter definieren
        detailed_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(levelname)-8s | %(name)s | %(message)s'
        )
        
        # Datei-Handler mit Rotation (max 10MB, 5 Backup-Dateien)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)  # Verwendet log_level aus config.json
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Konsolen-Handler mit konfigurierbarem Level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)  # Aus config.json
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # Speichere Handler für spätere Level-Änderungen
        self.console_handler = console_handler
        self.file_handler = file_handler
        
        # Spezielle Logger für externe Bibliotheken dämpfen
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('socketio').setLevel(logging.WARNING)
        logging.getLogger('engineio').setLevel(logging.WARNING)
        
        # Store module-specific log levels
        self.module_log_levels = {}
        
        # Startup-Log (nur in Datei, nicht auf Konsole)
        # Temporär Console-Handler entfernen
        root_logger.removeHandler(console_handler)
        root_logger.info("=" * 80)
        root_logger.info("Flux Video Art-Net Controller gestartet")
        root_logger.info(f"Log-Datei: {log_file}")
        root_logger.info("=" * 80)
        # Console-Handler wieder hinzufügen
        root_logger.addHandler(console_handler)
    
    def set_console_log_level(self, level):
        """
        Ändert das Log-Level für die Konsolen-Ausgabe.
        
        Args:
            level: logging.DEBUG, logging.INFO, logging.WARNING, etc.
        """
        if hasattr(self, 'console_handler'):
            self.console_handler.setLevel(level)
            level_name = logging.getLevelName(level)
            # Nur in Datei loggen, nicht auf Konsole ausgeben
            file_logger = logging.getLogger('flux.logger')
            file_logger.debug(f"Console-Log-Level auf {level_name} gesetzt")
    
    def get_console_log_level(self):
        """
        Gibt das aktuelle Console-Log-Level zurück.
        
        Returns:
            int: Aktuelles Log-Level (z.B. logging.WARNING)
        """
        if hasattr(self, 'console_handler'):
            return self.console_handler.level
        return logging.WARNING
    
    def set_module_log_level(self, module_pattern, level=logging.DEBUG):
        """
        Setzt Log-Level für ein bestimmtes Modul oder Modul-Pattern.
        
        Args:
            module_pattern: Modulname oder Pattern (z.B. 'modules.player.core' oder 'modules.player.*')
            level: Log-Level (logging.DEBUG, logging.INFO, etc.)
        """
        # Store pattern for later reference
        self.module_log_levels[module_pattern] = level
        
        # Apply to all existing loggers matching the pattern
        import fnmatch
        for logger_name in logging.Logger.manager.loggerDict:
            if fnmatch.fnmatch(logger_name, module_pattern):
                logger = logging.getLogger(logger_name)
                logger.setLevel(level)
                level_name = logging.getLevelName(level)
                # Log only to file, not console
                root_logger = logging.getLogger()
                if hasattr(self, 'console_handler'):
                    root_logger.removeHandler(self.console_handler)
                root_logger.info(f"Module '{logger_name}' log level set to {level_name}")
                if hasattr(self, 'console_handler'):
                    root_logger.addHandler(self.console_handler)
    
    def apply_debug_modules(self, debug_modules):
        """
        Aktiviert DEBUG-Level für eine Liste von Modulen.
        
        Args:
            debug_modules: Liste von Modul-Patterns (z.B. ['modules.player.*', 'modules.api.artnet'])
        """
        if not debug_modules:
            return
        
        for module_pattern in debug_modules:
            self.set_module_log_level(module_pattern, logging.DEBUG)
        
        root_logger = logging.getLogger()
        if hasattr(self, 'console_handler'):
            root_logger.removeHandler(self.console_handler)
        root_logger.info(f"🔍 Debug enabled for modules: {', '.join(debug_modules)}")
        if hasattr(self, 'console_handler'):
            root_logger.addHandler(self.console_handler)
    
    def get_module_log_levels(self):
        """
        Gibt alle konfigurierten Modul-Log-Levels zurück.
        
        Returns:
            dict: Module patterns und ihre Log-Levels
        """
        return self.module_log_levels.copy()
    
    @staticmethod
    def get_logger(name):
        """
        Holt einen benannten Logger.
        
        Args:
            name: Name des Loggers (meist __name__ des Moduls)
            
        Returns:
            logging.Logger: Konfigurierter Logger
        """
        return logging.getLogger(name)


def get_logger(name):
    """
    Convenience-Funktion zum Holen eines Loggers.
    
    Args:
        name: Name des Loggers (meist __name__)
        
    Returns:
        logging.Logger: Konfigurierter Logger
    """
    # Stelle sicher, dass FluxLogger initialisiert ist
    FluxLogger()
    return logging.getLogger(name)


def set_console_log_level(level):
    """
    Ändert das Console-Log-Level.
    
    Args:
        level: logging.DEBUG, logging.INFO, logging.WARNING, etc.
    """
    flux_logger = FluxLogger()
    flux_logger.set_console_log_level(level)


def get_console_log_level():
    """
    Gibt das aktuelle Console-Log-Level zurück.
    
    Returns:
        int: Aktuelles Log-Level
    """
    flux_logger = FluxLogger()
    return flux_logger.get_console_log_level()


# Hilfsfunktionen für strukturiertes Logging
def log_function_call(logger, func_name, **kwargs):
    """
    Loggt einen Funktionsaufruf mit Parametern.
    
    Args:
        logger: Logger-Instanz
        func_name: Name der Funktion
        **kwargs: Parameter als Key-Value-Paare
    """
    params = ', '.join(f'{k}={v}' for k, v in kwargs.items())
    logger.debug(f"Aufruf: {func_name}({params})")


def log_performance(logger, operation, duration_ms):
    """
    Loggt Performance-Metriken.
    
    Args:
        logger: Logger-Instanz
        operation: Name der Operation
        duration_ms: Dauer in Millisekunden
    """
    if duration_ms > 1000:
        logger.warning(f"Performance: {operation} dauerte {duration_ms:.2f}ms (>1s)")
    else:
        logger.debug(f"Performance: {operation} dauerte {duration_ms:.2f}ms")


def log_video_info(logger, video_path, frames, fps, dimensions):
    """
    Loggt Video-Informationen strukturiert.
    
    Args:
        logger: Logger-Instanz
        video_path: Pfad zum Video
        frames: Anzahl Frames
        fps: Frames pro Sekunde
        dimensions: Tuple (width, height)
    """
    logger.debug(f"Video geladen: {os.path.basename(video_path)}")
    logger.debug(f"  └─ Frames: {frames}, FPS: {fps:.2f}, Auflösung: {dimensions[0]}x{dimensions[1]}")


def log_cache_operation(logger, operation, video_hash, success, details=None):
    """
    Loggt Cache-Operationen.
    
    Args:
        logger: Logger-Instanz
        operation: Art der Operation (load, save, delete)
        video_hash: Hash des Videos
        success: Ob Operation erfolgreich war
        details: Optionale Details (z.B. Dateigröße)
    """
    status = "✓" if success else "✗"
    msg = f"Cache {operation}: {video_hash[:8]}... {status}"
    if details:
        msg += f" ({details})"
    
    if success:
        logger.debug(msg)
    else:
        logger.warning(msg)


def log_artnet_output(logger, universe, channel_count, first_values):
    """
    Loggt Art-Net-Ausgabe.
    
    Args:
        logger: Logger-Instanz
        universe: Universe-Nummer
        channel_count: Anzahl der Kanäle
        first_values: Liste der ersten paar Werte für Debug
    """
    values_str = ', '.join(str(v) for v in first_values[:6])
    logger.debug(f"Art-Net Universe {universe}: {channel_count} Kanäle [{values_str}...]")


# ========== DEBUG CATEGORIES SYSTEM ==========
# Granulare Kontrolle über Debug-Ausgaben nach Kategorie

class DebugCategories:
    """
    Verwaltet Debug-Kategorien für granulare Log-Kontrolle.
    Kategorien können zur Laufzeit aktiviert/deaktiviert werden.
    """
    
    # Definierte Debug-Kategorien
    TRANSPORT = 'transport'          # Transport plugin (position, loop, speed)
    EFFECTS = 'effects'              # Effect processing
    LAYERS = 'layers'                # Layer compositing
    PLAYBACK = 'playback'            # Playback loop, frame fetch
    API = 'api'                      # API calls
    WEBSOCKET = 'websocket'          # WebSocket communication
    ARTNET = 'artnet'                # Art-Net output
    PERFORMANCE = 'performance'      # Performance metrics
    CACHE = 'cache'                  # Cache operations
    
    _enabled_categories = set()
    _initialized = False
    
    @classmethod
    def initialize(cls, enabled_categories=None):
        """
        Initialisiert Debug-Kategorien.
        
        Args:
            enabled_categories: Liste der zu aktivierenden Kategorien (None = alle aus)
        """
        cls._enabled_categories = set(enabled_categories or [])
        cls._initialized = True
    
    @classmethod
    def enable(cls, *categories):
        """Aktiviert eine oder mehrere Debug-Kategorien."""
        if not cls._initialized:
            cls.initialize()
        cls._enabled_categories.update(categories)
    
    @classmethod
    def disable(cls, *categories):
        """Deaktiviert eine oder mehrere Debug-Kategorien."""
        if not cls._initialized:
            cls.initialize()
        cls._enabled_categories.difference_update(categories)
    
    @classmethod
    def is_enabled(cls, category):
        """Prüft, ob eine Kategorie aktiviert ist."""
        if not cls._initialized:
            cls.initialize()
        return category in cls._enabled_categories
    
    @classmethod
    def enable_all(cls):
        """Aktiviert alle Debug-Kategorien."""
        cls._enabled_categories = {
            cls.TRANSPORT, cls.EFFECTS, cls.LAYERS, cls.PLAYBACK,
            cls.API, cls.WEBSOCKET, cls.ARTNET, cls.PERFORMANCE, cls.CACHE
        }
    
    @classmethod
    def disable_all(cls):
        """Deaktiviert alle Debug-Kategorien."""
        cls._enabled_categories.clear()
    
    @classmethod
    def get_enabled(cls):
        """Gibt Liste der aktivierten Kategorien zurück."""
        return list(cls._enabled_categories)
    
    @classmethod
    def get_all(cls):
        """Gibt Liste aller verfügbaren Kategorien zurück."""
        return [
            cls.TRANSPORT, cls.EFFECTS, cls.LAYERS, cls.PLAYBACK,
            cls.API, cls.WEBSOCKET, cls.ARTNET, cls.PERFORMANCE, cls.CACHE
        ]


def debug_log(logger, category, message, *args, **kwargs):
    """
    Bedingte Debug-Log-Ausgabe basierend auf Kategorie.
    
    Args:
        logger: Logger-Instanz
        category: Debug-Kategorie (z.B. DebugCategories.TRANSPORT)
        message: Log-Nachricht (kann Formatierungs-Platzhalter enthalten)
        *args: Argumente für String-Formatierung
        **kwargs: Keyword-Argumente für String-Formatierung
    
    Example:
        debug_log(logger, DebugCategories.TRANSPORT, 
                  "Frame %d, position=%s", frame, position)
    """
    if DebugCategories.is_enabled(category):
        # Format message if args provided
        if args or kwargs:
            message = message % args if args else message.format(**kwargs)
        logger.debug(f"[{category}] {message}")


def info_log_conditional(logger, category, message, *args, **kwargs):
    """
    Bedingte Info-Log-Ausgabe basierend auf Kategorie.
    INFO-Logs werden immer in Datei geschrieben, aber nur bei aktivierter Kategorie auch ausgegeben.
    
    Args:
        logger: Logger-Instanz
        category: Debug-Kategorie
        message: Log-Nachricht
        *args, **kwargs: Format-Argumente
    """
    if DebugCategories.is_enabled(category):
        if args or kwargs:
            message = message % args if args else message.format(**kwargs)
        logger.debug(f"[{category}] {message}")


# Convenience-Funktionen für häufig genutzte Kategorien
def debug_transport(logger, message, *args, **kwargs):
    """Transport-spezifisches Debug-Log."""
    debug_log(logger, DebugCategories.TRANSPORT, message, *args, **kwargs)

def debug_effects(logger, message, *args, **kwargs):
    """Effects-spezifisches Debug-Log."""
    debug_log(logger, DebugCategories.EFFECTS, message, *args, **kwargs)

def debug_layers(logger, message, *args, **kwargs):
    """Layer-spezifisches Debug-Log."""
    debug_log(logger, DebugCategories.LAYERS, message, *args, **kwargs)

def debug_playback(logger, message, *args, **kwargs):
    """Playback-spezifisches Debug-Log."""
    debug_log(logger, DebugCategories.PLAYBACK, message, *args, **kwargs)

def debug_api(logger, message, *args, **kwargs):
    """API-spezifisches Debug-Log."""
    debug_log(logger, DebugCategories.API, message, *args, **kwargs)
