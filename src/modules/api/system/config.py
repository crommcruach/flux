"""
API Config Routes - Configuration Management Endpoints

IMPORTANT: NEVER use print() statements in API functions!
This causes "write() before start_response" errors in Flask/Werkzeug.
Always use the logger for debug output:
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
        """Returns the current configuration."""
        try:
            # Finde config.json im Root-Verzeichnis (5 levels up from this file:
            # src/modules/api/system/config.py -> system -> api -> modules -> src -> root)
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            config_file = os.path.join(base_path, 'config.json')
            
            if not os.path.exists(config_file):
                return jsonify({
                    "status": "error",
                    "message": f"Config file not found: {config_file}"
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
                    "message": "No configuration sent"
                }), 400
            # Validate config against schema
            is_valid, errors = validator.validate(new_config)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Validation failed",
                    "errors": errors,
                    "valid": False
                }), 400
            
            # Finde config.json im Root-Verzeichnis (5 levels up from this file:
            # src/modules/api/system/config.py -> system -> api -> modules -> src -> root)
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
            config_file = os.path.join(base_path, 'config.json')
            
            # Create backup
            backup_file = config_file + '.backup'
            if os.path.exists(config_file):
                import shutil
                shutil.copy2(config_file, backup_file)
            
            # Save new config with formatting
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, indent=2, ensure_ascii=False)
            
            return jsonify({
                "status": "success",
                "message": "Configuration saved and validated",
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
        """Validates configuration without saving (with schema)."""
        try:
            config_data = request.get_json()
            
            if not config_data:
                return jsonify({
                    "status": "error",
                    "message": "No configuration sent",
                    "valid": False
                }), 400
            
            # Validate against schema
            is_valid, errors = validator.validate(config_data)
            
            if not is_valid:
                return jsonify({
                    "status": "error",
                    "message": "Validation failed",
                    "valid": False,
                    "errors": errors
                }), 400
            
            return jsonify({
                "status": "success",
                "message": "Configuration is valid",
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
        """Restores backup."""
        try:
            base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            config_file = os.path.join(base_path, 'config.json')
            backup_file = config_file + '.backup'
            
            if not os.path.exists(backup_file):
                return jsonify({
                    "status": "error",
                    "message": "No backup found"
                }), 404
            
            import shutil
            shutil.copy2(backup_file, config_file)
            
            return jsonify({
                "status": "success",
                "message": "Backup restored"
            })
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    
    @app.route('/api/config/schema', methods=['GET'])
    def get_config_schema():
        """Returns the JSON schema for config.json."""
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
        """Returns the default configuration."""
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
