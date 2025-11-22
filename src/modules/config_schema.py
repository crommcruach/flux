"""
Configuration Schema - JSON Schema für config.json Validierung
"""
from typing import Dict, Any, List, Tuple
import json
from .logger import get_logger

logger = get_logger(__name__)

# JSON Schema für config.json
CONFIG_SCHEMA = {
    "type": "object",
    "required": ["artnet", "video", "paths"],
    "properties": {
        "artnet": {
            "type": "object",
            "required": ["target_ip", "start_universe"],
            "properties": {
                "target_ip": {
                    "type": "string",
                    "pattern": "^\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}$",
                    "description": "Art-Net Ziel-IP-Adresse"
                },
                "start_universe": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 32767,
                    "description": "Start-Universum für Art-Net Ausgabe"
                },
                "dmx_control_universe": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 32767,
                    "description": "DMX Control Universum für Input"
                },
                "dmx_listen_ip": {
                    "type": "string",
                    "description": "IP-Adresse für DMX Listening"
                },
                "dmx_listen_port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "Port für DMX Listening"
                },
                "fps": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 120,
                    "description": "Art-Net FPS"
                },
                "even_packet": {
                    "type": "boolean",
                    "description": "Art-Net Even Packet Mode"
                },
                "broadcast": {
                    "type": "boolean",
                    "description": "Art-Net Broadcast Mode"
                },
                "universe_configs": {
                    "type": "object",
                    "properties": {
                        "default": {
                            "type": "string",
                            "enum": ["RGB", "GRB", "BGR", "RBG", "GBR", "BRG"],
                            "description": "Standard RGB-Kanal-Reihenfolge"
                        }
                    },
                    "patternProperties": {
                        "^\\d+$": {
                            "type": "string",
                            "enum": ["RGB", "GRB", "BGR", "RBG", "GBR", "BRG"],
                            "description": "RGB-Kanal-Reihenfolge für spezifisches Universum"
                        }
                    },
                    "description": "RGB-Kanal-Mapping pro Universum"
                }
            }
        },
        "video": {
            "type": "object",
            "properties": {
                "extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Unterstützte Video-Dateiformate"
                },
                "max_per_channel": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 255,
                    "description": "Max Videos pro Kanal"
                },
                "default_fps": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 240,
                    "description": "Standard FPS (null = auto)"
                },
                "default_brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Standard Helligkeit in Prozent"
                },
                "default_speed": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 10.0,
                    "description": "Standard Geschwindigkeitsfaktor"
                },
                "shutdown_delay": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 10,
                    "description": "Verzögerung beim Shutdown in Sekunden"
                },
                "frame_wait_delay": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Wartezeit zwischen Frames in Sekunden"
                },
                "recording_stop_delay": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 5,
                    "description": "Verzögerung beim Stoppen der Aufzeichnung in Sekunden"
                },
                "gif_transparency_bg": {
                    "type": "array",
                    "items": {"type": "integer", "minimum": 0, "maximum": 255},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "RGB-Hintergrundfarbe für GIF-Transparenz"
                },
                "gif_respect_frame_timing": {
                    "type": "boolean",
                    "description": "GIF Frame-Timing respektieren"
                }
            }
        },
        "paths": {
            "type": "object",
            "required": ["video_dir", "data_dir", "points_json"],
            "properties": {
                "video_dir": {
                    "type": "string",
                    "description": "Verzeichnis für Videos"
                },
                "data_dir": {
                    "type": "string",
                    "description": "Verzeichnis für Points-JSON Dateien"
                },
                "points_json": {
                    "type": "string",
                    "description": "Standard Points-JSON Dateiname (deprecated, use default_points_json)"
                },
                "default_points_json": {
                    "type": ["string", "null"],
                    "description": "Standard Points-JSON Dateiname (relativ zu data_dir)"
                },
                "scripts_dir": {
                    "type": "string",
                    "description": "Verzeichnis für Script-Dateien"
                },
                "cache_dir": {
                    "type": "string",
                    "description": "Verzeichnis für Video-Cache-Dateien"
                },
                "projects_dir": {
                    "type": "string",
                    "description": "Verzeichnis für gespeicherte Projekte"
                }
            }
        },
        "channels": {
            "type": "object",
            "properties": {
                "max_per_universe": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 512,
                    "description": "Maximale Kanäle pro Universum"
                },
                "channels_per_point": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 4,
                    "description": "Kanäle pro Punkt (RGB=3, RGBW=4)"
                }
            }
        },
        "cache": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "RGB-Cache aktivieren"
                },
                "max_size_mb": {
                    "type": "integer",
                    "minimum": 0,
                    "description": "Maximale Cache-Größe in MB (0=unbegrenzt)"
                }
            }
        },
        "api": {
            "type": "object",
            "properties": {
                "port": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 65535,
                    "description": "REST API Port"
                },
                "host": {
                    "type": "string",
                    "description": "REST API Host"
                },
                "secret_key": {
                    "type": "string",
                    "description": "Flask Secret Key"
                },
                "console_log_maxlen": {
                    "type": "integer",
                    "minimum": 10,
                    "maximum": 10000,
                    "description": "Maximale Console-Log Einträge"
                },
                "status_broadcast_interval": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 60,
                    "description": "Status-Broadcast Intervall in Sekunden"
                }
            }
        },
        "app": {
            "type": "object",
            "properties": {
                "default_player": {
                    "type": "string",
                    "enum": ["video", "script"],
                    "description": "Standard Player-Typ"
                }
            }
        },
        "frontend": {
            "type": "object",
            "properties": {
                "polling_interval": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 30000,
                    "description": "Frontend Polling-Intervall in Millisekunden"
                },
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "auto"],
                    "description": "Standard Theme"
                }
            }
        }
    },
    "additionalProperties": True  # Erlaube zusätzliche Properties für Erweiterbarkeit
}


class ConfigValidator:
    """Validiert Konfigurationsdateien gegen Schema."""
    
    def __init__(self):
        """Initialisiert Validator."""
        try:
            import jsonschema
            self.jsonschema = jsonschema
            self.validator = jsonschema.Draft7Validator(CONFIG_SCHEMA)
            self.available = True
        except ImportError:
            logger.warning("jsonschema nicht installiert - Schema-Validierung deaktiviert")
            self.available = False
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validiert Konfiguration gegen Schema.
        
        Args:
            config: Configuration Dictionary
            
        Returns:
            Tuple[bool, List[str]]: (is_valid, error_messages)
        """
        if not self.available:
            logger.warning("Schema-Validierung übersprungen (jsonschema nicht verfügbar)")
            return True, []
        
        errors = []
        
        try:
            # Validiere gegen Schema
            schema_errors = list(self.validator.iter_errors(config))
            
            for error in schema_errors:
                path = ".".join(str(p) for p in error.path) if error.path else "root"
                errors.append(f"{path}: {error.message}")
            
            # Zusätzliche Custom-Validierungen
            custom_errors = self._custom_validations(config)
            errors.extend(custom_errors)
            
            is_valid = len(errors) == 0
            
            if not is_valid:
                logger.error(f"Config-Validierung fehlgeschlagen: {len(errors)} Fehler")
                for error in errors:
                    logger.error(f"  - {error}")
            else:
                logger.info("Config-Validierung erfolgreich")
            
            return is_valid, errors
            
        except Exception as e:
            logger.error(f"Fehler bei Config-Validierung: {e}", exc_info=True)
            return False, [f"Validierungs-Fehler: {str(e)}"]
    
    def _custom_validations(self, config: Dict[str, Any]) -> List[str]:
        """
        Führt zusätzliche Custom-Validierungen durch.
        
        Args:
            config: Configuration Dictionary
            
        Returns:
            List[str]: Liste von Fehlermeldungen
        """
        errors = []
        
        # Validiere IP-Adresse Format
        if "artnet" in config and "target_ip" in config["artnet"]:
            ip = config["artnet"]["target_ip"]
            if not self._is_valid_ip(ip):
                errors.append(f"artnet.target_ip: Ungültige IP-Adresse '{ip}'")
        
        # Validiere Pfade
        if "paths" in config:
            paths = config["paths"]
            if "video_dir" in paths and not paths["video_dir"]:
                errors.append("paths.video_dir: Darf nicht leer sein")
            if "data_dir" in paths and not paths["data_dir"]:
                errors.append("paths.data_dir: Darf nicht leer sein")
        
        # Validiere Channel-Konfiguration
        if "channels" in config:
            channels = config["channels"]
            max_per_universe = channels.get("max_per_universe", 510)
            channels_per_point = channels.get("channels_per_point", 3)
            
            if max_per_universe % channels_per_point != 0:
                logger.warning(
                    f"channels.max_per_universe ({max_per_universe}) ist nicht "
                    f"durch channels_per_point ({channels_per_point}) teilbar"
                )
        
        # Validiere RGB-Ordnung in universe_configs
        if "artnet" in config and "universe_configs" in config["artnet"]:
            valid_orders = ["RGB", "GRB", "BGR", "RBG", "GBR", "BRG"]
            for key, value in config["artnet"]["universe_configs"].items():
                # Ignoriere Kommentar-Felder
                if key.startswith("_"):
                    continue
                if value not in valid_orders:
                    errors.append(
                        f"artnet.universe_configs.{key}: Ungültige RGB-Reihenfolge '{value}'. "
                        f"Muss einer von {valid_orders} sein"
                    )
        
        return errors
    
    def _is_valid_ip(self, ip: str) -> bool:
        """
        Prüft ob IP-Adresse gültig ist.
        
        Args:
            ip: IP-Adresse String
            
        Returns:
            bool: True wenn gültig
        """
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        
        try:
            for part in parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False
            return True
        except ValueError:
            return False
    
    def get_schema(self) -> Dict[str, Any]:
        """
        Gibt das vollständige Schema zurück.
        
        Returns:
            Dict[str, Any]: JSON Schema
        """
        return CONFIG_SCHEMA
    
    def get_default_config(self) -> Dict[str, Any]:
        """
        Generiert Standard-Konfiguration basierend auf Schema.
        
        Returns:
            Dict[str, Any]: Default Configuration
        """
        return {
            "artnet": {
                "target_ip": "127.0.0.1",
                "start_universe": 0,
                "dmx_control_universe": 100,
                "dmx_listen_ip": "0.0.0.0",
                "dmx_listen_port": 6454,
                "fps": 60,
                "even_packet": True,
                "broadcast": True,
                "universe_configs": {
                    "default": "RGB"
                }
            },
            "video": {
                "extensions": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".gif"],
                "max_per_channel": 255,
                "default_fps": None,
                "default_brightness": 100,
                "default_speed": 1.0,
                "shutdown_delay": 0.5,
                "frame_wait_delay": 0.1,
                "recording_stop_delay": 0.3,
                "gif_transparency_bg": [0, 0, 0],
                "gif_respect_frame_timing": True
            },
            "paths": {
                "video_dir": "video",
                "data_dir": "data",
                "points_json": "punkte_export.json",
                "scripts_dir": "scripts",
                "cache_dir": "cache",
                "projects_dir": "PROJECTS"
            },
            "channels": {
                "max_per_universe": 510,
                "channels_per_point": 3
            },
            "cache": {
                "enabled": True,
                "max_size_mb": 0
            },
            "api": {
                "port": 5000,
                "host": "0.0.0.0",
                "secret_key": "flux_secret_key_2025",
                "console_log_maxlen": 500,
                "status_broadcast_interval": 2
            },
            "app": {
                "default_player": "video"
            },
            "frontend": {
                "polling_interval": 3000,
                "theme": "dark"
            }
        }


def validate_config_file(config_path: str) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Lädt und validiert Config-Datei.
    
    Args:
        config_path: Pfad zur config.json
        
    Returns:
        Tuple[bool, List[str], Dict]: (is_valid, errors, config_dict)
    """
    validator = ConfigValidator()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        is_valid, errors = validator.validate(config)
        return is_valid, errors, config
        
    except FileNotFoundError:
        return False, [f"Config-Datei nicht gefunden: {config_path}"], {}
    except json.JSONDecodeError as e:
        return False, [f"JSON-Parsing Fehler: {str(e)}"], {}
    except Exception as e:
        return False, [f"Fehler beim Laden der Config: {str(e)}"], {}
