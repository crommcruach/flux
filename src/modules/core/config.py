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
                "fps": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 120,
                    "description": "Art-Net FPS"
                },
                "broadcast": {
                    "type": "boolean",
                    "description": "Art-Net Broadcast Mode"
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
                "frame_wait_delay": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "description": "Wartezeit zwischen Frames in Sekunden"
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
                    "description": "Fallback Points-JSON Dateiname (use default_points_json instead)"
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
                },
                "video_sources": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Zusätzliche Video-Quellen (Ordner/Laufwerke) für File Browser",
                    "default": []
                }
            }
        },
        "effects": {
            "type": "object",
            "properties": {
                "video": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["plugin_id"],
                        "properties": {
                            "plugin_id": {"type": "string"},
                            "params": {"type": "object"}
                        }
                    },
                    "description": "Default effect chain für Video-Player",
                    "default": []
                },
                "artnet": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["plugin_id"],
                        "properties": {
                            "plugin_id": {"type": "string"},
                            "params": {"type": "object"}
                        }
                    },
                    "description": "Default effect chain für Art-Net-Player",
                    "default": []
                },
                "clips": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["plugin_id"],
                        "properties": {
                            "plugin_id": {"type": "string"},
                            "params": {"type": "object"}
                        }
                    },
                    "description": "Default effect chain for ALL clips",
                    "default": []
                }
            }
        },
        "outputs": {
            "type": "object",
            "properties": {
                "definitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "type"],
                        "properties": {
                            "id": {"type": "string"},
                            "type": {"type": "string", "enum": ["display", "virtual", "ndi"]},
                            "enabled": {"type": "boolean"},
                            "monitor_index": {"type": "integer"},
                            "fullscreen": {"type": "boolean"},
                            "resolution": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": 2,
                                "maxItems": 2
                            },
                            "fps": {"type": "integer", "minimum": 1, "maximum": 120},
                            "enable_capture": {"type": "boolean"},
                            "description": {"type": "string"}
                        }
                    },
                    "description": "Available output devices/targets"
                },
                "default_routing": {
                    "type": "object",
                    "properties": {
                        "video": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Default video player output routing"
                        },
                        "artnet": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Default artnet player output routing"
                        }
                    }
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
                logger.debug("Config-Validierung erfolgreich")
            
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
        
        # Historical note: Channel config and universe RGB order now managed per-object in session_state.json
        
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
                "fps": 60,
                "broadcast": True
            },
            "video": {
                "extensions": [".mp4", ".avi", ".mov", ".mkv", ".wmv", ".gif"],
                "default_fps": None,
                "default_brightness": 100,
                "default_speed": 1.0,
                "frame_wait_delay": 0.1,
                "gif_transparency_bg": [0, 0, 0],
                "gif_respect_frame_timing": True
            },
            "paths": {
                "video_dir": "video",
                "data_dir": "data",
                "points_json": "punkte_export.json",
                "scripts_dir": "scripts",
                "cache_dir": "cache",
                "projects_dir": "projects",
                "video_sources": []
            },
            "effects": {
                "video": [],
                "artnet": [],
                "clips": []
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
