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
    
    def setup_logging(self, log_dir='logs', log_level=logging.INFO, console_level=logging.WARNING):
        """
        Richtet das Logging-System ein.
        
        Args:
            log_dir: Verzeichnis für Log-Dateien
            log_level: Logging-Level für Datei (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            console_level: Logging-Level für Konsole (Standard: WARNING)
        """
        # Log-Verzeichnis erstellen
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
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
        file_handler.setLevel(logging.DEBUG)  # Alles in Datei loggen
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        
        # Konsolen-Handler mit konfigurierbarem Level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)  # Aus config.json
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # Speichere Console-Handler für spätere Level-Änderungen
        self.console_handler = console_handler
        
        # Spezielle Logger für externe Bibliotheken dämpfen
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('socketio').setLevel(logging.WARNING)
        logging.getLogger('engineio').setLevel(logging.WARNING)
        
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
    logger.info(f"Video geladen: {os.path.basename(video_path)}")
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
        logger.info(msg)
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
