"""
API Config Routes - Configuration Management Endpoints

WICHTIG: Verwende NIEMALS print() Statements in API-Funktionen!
Dies verursacht "write() before start_response" Fehler in Flask/Werkzeug.
Nutze stattdessen immer den Logger für Debug-Ausgaben:
    from ...core.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Message")
"""
from flask import jsonify, request
import json
import os
from ...core.config import ConfigValidator
from ...core.logger import get_logger

logger = get_logger(__name__)


def register_config_routes(app, config_path='config.json'):
    """Registriert Config-Management Endpunkte."""
    
    validator = ConfigValidator()
    
    @app.route('/api/config', methods=['GET'])
    def get_config():
        """Gibt aktuelle Konfiguration zurück."""
        try:
            # Finde config.json im Root-Verzeichnis (4 levels up from this file)
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_file = os.path.join(base_path, 'config.json')
            
            if not os.path.exists(config_file):
                return jsonify({
                    "status": "error",
                    "message": f"Config-Datei nicht gefunden: {config_file}"
                }), 404
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            return jsonify(config_data)
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/config', methods=['POST'])
    def update_config():
        """Speichert Konfiguration mit Schema-Validierung."""
        try:
            new_config = request.get_json()
            
            if not new_config:
                return jsonify({
                    "status": "error",
                    "message": "Keine Konfiguration gesendet"
                }), 400
            
            # Validiere Config gegen Schema
            is_valid, errors = validator.validate(new_config)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Validierung fehlgeschlagen",
                    "errors": errors,
                    "valid": False
                }), 400
            
            # Finde config.json im Root-Verzeichnis (4 levels up from this file)
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_file = os.path.join(base_path, 'config.json')
            
            # Backup erstellen
            backup_file = config_file + '.backup'
            if os.path.exists(config_file):
                import shutil
                shutil.copy2(config_file, backup_file)
            
            # Neue Config speichern mit Formatierung
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            
            return jsonify({
                "status": "success",
                "message": "Konfiguration gespeichert und validiert",
                "backup": backup_file,
                "valid": True
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/config/validate', methods=['POST'])
    def validate_config():
        """Validiert Konfiguration ohne zu speichern (mit Schema)."""
        try:
            config_data = request.get_json()
            
            if not config_data:
                return jsonify({
                    "status": "error",
                    "message": "Keine Konfiguration gesendet",
                    "valid": False
                }), 400
            
            # Validiere gegen Schema
            is_valid, errors = validator.validate(config_data)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Validierung fehlgeschlagen",
                    "valid": False,
                    "errors": errors
                }), 400
            
            return jsonify({
                "status": "success",
                "message": "Konfiguration ist valide",
                "valid": True,
                "errors": []
            })
            
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e),
                "valid": False
            }), 500
    
    @app.route('/api/config/restore', methods=['POST'])
    def restore_config():
        """Stellt Backup wieder her."""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_file = os.path.join(base_path, 'config.json')
            backup_file = config_file + '.backup'
            
            if not os.path.exists(backup_file):
                return jsonify({
                    "status": "error",
                    "message": "Kein Backup gefunden"
                }), 404
            
            import shutil
            shutil.copy2(backup_file, config_file)
            
            return jsonify({
                "status": "success",
                "message": "Backup wiederhergestellt"
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/config/schema', methods=['GET'])
    def get_config_schema():
        """Gibt das JSON-Schema für config.json zurück."""
        try:
            schema = validator.get_schema()
            return jsonify({
                "status": "success",
                "schema": schema
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/config/default', methods=['GET'])
    def get_default_config():
        """Gibt die Standard-Konfiguration zurück."""
        try:
            default_config = validator.get_default_config()
            return jsonify({
                "status": "success",
                "config": default_config
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
