"""
REST API Endpoints für Plugin-System
"""
from flask import Blueprint, jsonify, request
from modules.plugins.manager import get_plugin_manager
from ...core.logger import get_logger, debug_api

logger = get_logger(__name__)

# Blueprint erstellen
plugins_bp = Blueprint('plugins', __name__, url_prefix='/api/plugins')


@plugins_bp.route('/list', methods=['GET'])
def list_plugins():
    """
    Listet alle verfügbaren Plugins auf.
    
    Query Parameters:
        type (optional): Filtert nach Plugin-Typ (generator, effect, source, transition)
    
    Returns:
        {
            "plugins": [
                {
                    "id": "blur",
                    "name": "Gaussian Blur",
                    "description": "...",
                    "type": "effect",
                    "category": "Blur/Distortion",
                    "author": "Flux Team",
                    "version": "1.0.0"
                },
                ...
            ],
            "count": 1
        }
    """
    pm = get_plugin_manager()
    debug_api(logger, f"API /list called. PluginManager registry has {len(pm.registry)} plugins")
    
    # Optional: Filter by type
    plugin_type = request.args.get('type')
    if plugin_type:
        from plugins.plugin_base import PluginType
        try:
            filter_type = PluginType(plugin_type)
            plugins = pm.list_plugins(plugin_type=filter_type)
        except ValueError:
            return jsonify({"error": f"Invalid plugin type: {plugin_type}"}), 400
    else:
        plugins = pm.list_plugins()
    
    debug_api(logger, f"Returning {len(plugins)} plugins to API client")
    
    return jsonify({
        "success": True,
        "plugins": plugins,
        "count": len(plugins)
    })


@plugins_bp.route('/<plugin_id>/metadata', methods=['GET'])
def get_plugin_metadata(plugin_id):
    """
    Gibt METADATA eines Plugins zurück.
    
    Args:
        plugin_id: Plugin-ID (z.B. "blur")
    
    Returns:
        {
            "id": "blur",
            "name": "Gaussian Blur",
            "description": "...",
            "type": "effect",
            "category": "Blur/Distortion",
            "author": "Flux Team",
            "version": "1.0.0"
        }
    """
    pm = get_plugin_manager()
    metadata = pm.get_plugin_metadata(plugin_id)
    
    if not metadata:
        return jsonify({"error": f"Plugin '{plugin_id}' not found"}), 404
    
    return jsonify(metadata)


@plugins_bp.route('/<plugin_id>/parameters', methods=['GET'])
def get_plugin_parameters(plugin_id):
    """
    Gibt PARAMETERS eines Plugins zurück (für UI-Generierung).
    
    Args:
        plugin_id: Plugin-ID
    
    Returns:
        {
            "parameters": [
                {
                    "name": "strength",
                    "label": "Blur Stärke",
                    "type": "float",
                    "default": 5.0,
                    "min": 0.0,
                    "max": 20.0,
                    "step": 0.5,
                    "description": "..."
                },
                ...
            ]
        }
    """
    pm = get_plugin_manager()
    parameters = pm.get_plugin_parameters(plugin_id)
    
    if parameters is None:
        return jsonify({"error": f"Plugin '{plugin_id}' not found"}), 404
    
    return jsonify({"parameters": parameters})


@plugins_bp.route('/<plugin_id>/load', methods=['POST'])
def load_plugin(plugin_id):
    """
    Lädt Plugin mit Konfiguration.
    
    Args:
        plugin_id: Plugin-ID
    
    Body (JSON):
        {
            "config": {
                "strength": 10.0
            }
        }
    
    Returns:
        {
            "success": true,
            "plugin_id": "blur",
            "message": "Plugin loaded successfully"
        }
    """
    pm = get_plugin_manager()
    data = request.get_json() or {}
    config = data.get('config', {})
    
    instance = pm.load_plugin(plugin_id, config=config)
    
    if not instance:
        return jsonify({
            "success": False,
            "error": f"Failed to load plugin '{plugin_id}'"
        }), 500
    
    return jsonify({
        "success": True,
        "plugin_id": plugin_id,
        "message": "Plugin loaded successfully"
    })


@plugins_bp.route('/<plugin_id>/unload', methods=['POST'])
def unload_plugin(plugin_id):
    """
    Entlädt Plugin-Instanz.
    
    Args:
        plugin_id: Plugin-ID
    
    Returns:
        {
            "success": true,
            "message": "Plugin unloaded successfully"
        }
    """
    pm = get_plugin_manager()
    pm.unload_plugin(plugin_id)
    
    return jsonify({
        "success": True,
        "message": "Plugin unloaded successfully"
    })


@plugins_bp.route('/<plugin_id>/parameters/<param_name>', methods=['POST'])
def update_plugin_parameter(plugin_id, param_name):
    """
    Aktualisiert Parameter zur Laufzeit.
    
    Args:
        plugin_id: Plugin-ID
        param_name: Parameter-Name (z.B. "strength")
    
    Body (JSON):
        {
            "value": 10.0
        }
    
    Returns:
        {
            "success": true,
            "plugin_id": "blur",
            "parameter": "strength",
            "value": 10.0
        }
    """
    pm = get_plugin_manager()
    data = request.get_json()
    
    if not data or 'value' not in data:
        return jsonify({"error": "Missing 'value' in request body"}), 400
    
    value = data['value']
    
    # Validiere Wert
    if not pm.validate_parameter_value(plugin_id, param_name, value):
        return jsonify({
            "error": f"Invalid value for parameter '{param_name}'"
        }), 400
    
    # Hole Plugin-Instanz
    instance = pm.get_plugin(plugin_id)
    if not instance:
        return jsonify({
            "error": f"Plugin '{plugin_id}' not loaded. Load it first with POST /api/plugins/{plugin_id}/load"
        }), 404
    
    # Update Parameter
    success = instance.update_parameter(param_name, value)
    
    if not success:
        return jsonify({
            "error": f"Failed to update parameter '{param_name}'"
        }), 500
    
    return jsonify({
        "success": True,
        "plugin_id": plugin_id,
        "parameter": param_name,
        "value": value
    })


@plugins_bp.route('/<plugin_id>/parameters', methods=['GET'])
def get_current_parameter_values(plugin_id):
    """
    Gibt aktuelle Parameter-Werte einer geladenen Plugin-Instanz zurück.
    
    Args:
        plugin_id: Plugin-ID
    
    Returns:
        {
            "plugin_id": "blur",
            "parameters": {
                "strength": 10.0
            }
        }
    """
    pm = get_plugin_manager()
    instance = pm.get_plugin(plugin_id)
    
    if not instance:
        return jsonify({
            "error": f"Plugin '{plugin_id}' not loaded"
        }), 404
    
    return jsonify({
        "plugin_id": plugin_id,
        "parameters": instance.get_parameters()
    })


@plugins_bp.route('/stats', methods=['GET'])
def get_plugin_stats():
    """
    Gibt Statistiken über geladene Plugins zurück.
    
    Returns:
        {
            "total_plugins": 10,
            "loaded_instances": 2,
            "by_type": {
                "effect": 5,
                "generator": 3,
                "source": 1,
                "transition": 1
            }
        }
    """
    pm = get_plugin_manager()
    return jsonify(pm.get_stats())


@plugins_bp.route('/reload', methods=['POST'])
def reload_plugins():
    """
    Lädt alle Plugins neu (Development).
    
    Returns:
        {
            "success": true,
            "message": "All plugins reloaded"
        }
    """
    pm = get_plugin_manager()
    pm.reload_plugins()
    
    return jsonify({
        "success": True,
        "message": "All plugins reloaded"
    })


def register_plugins_api(app):
    """
    Registriert Plugins-Blueprint in Flask-App.
    
    Args:
        app: Flask-App-Instanz
    """
    app.register_blueprint(plugins_bp)
    logger.debug("Plugins API registriert: /api/plugins/*")
