"""
Debug API - Runtime control over debug categories and logging
"""
from flask import Blueprint, jsonify, request
import logging
from ...core.logger import DebugCategories, get_logger, FluxLogger

logger = get_logger(__name__)

debug_bp = Blueprint('debug', __name__)


@debug_bp.route('/api/debug/categories', methods=['GET'])
def get_debug_categories():
    """
    Returns all available debug categories and their status.
    
    Returns:
        JSON mit allen Kategorien und welche aktiviert sind
    """
    all_categories = DebugCategories.get_all()
    enabled_categories = DebugCategories.get_enabled()
    
    return jsonify({
        'categories': [
            {
                'name': cat,
                'enabled': cat in enabled_categories
            }
            for cat in all_categories
        ],
        'total': len(all_categories),
        'enabled_count': len(enabled_categories)
    })


@debug_bp.route('/api/debug/categories/enable', methods=['POST'])
def enable_debug_categories():
    """
    Aktiviert eine oder mehrere Debug-Kategorien.
    
    Body:
        {
            "categories": ["transport", "effects"],  // Oder ["all"]
        }
    """
    try:
        data = request.get_json()
        categories = data.get('categories', [])
        
        if 'all' in categories:
            DebugCategories.enable_all()
            logger.debug("🐛 All debug categories enabled")
            return jsonify({
                'success': True,
                'message': 'All debug categories enabled',
                'enabled': DebugCategories.get_enabled()
            })
        
        DebugCategories.enable(*categories)
        logger.debug(f"🐛 Debug categories enabled: {', '.join(categories)}")
        
        return jsonify({
            'success': True,
            'message': f'Enabled {len(categories)} categories',
            'enabled': DebugCategories.get_enabled()
        })
    
    except Exception as e:
        logger.error(f"Error enabling debug categories: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@debug_bp.route('/api/debug/categories/disable', methods=['POST'])
def disable_debug_categories():
    """
    Deaktiviert eine oder mehrere Debug-Kategorien.
    
    Body:
        {
            "categories": ["transport", "effects"],  // Oder ["all"]
        }
    """
    try:
        data = request.get_json()
        categories = data.get('categories', [])
        
        if 'all' in categories:
            DebugCategories.disable_all()
            logger.debug("🐛 All debug categories disabled")
            return jsonify({
                'success': True,
                'message': 'All debug categories disabled',
                'enabled': []
            })
        
        DebugCategories.disable(*categories)
        logger.debug(f"🐛 Debug categories disabled: {', '.join(categories)}")
        
        return jsonify({
            'success': True,
            'message': f'Disabled {len(categories)} categories',
            'enabled': DebugCategories.get_enabled()
        })
    
    except Exception as e:
        logger.error(f"Error disabling debug categories: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@debug_bp.route('/api/debug/categories/toggle', methods=['POST'])
def toggle_debug_category():
    """
    Schaltet eine Debug-Kategorie um (an/aus).
    
    Body:
        {
            "category": "transport"
        }
    """
    try:
        data = request.get_json()
        category = data.get('category')
        
        if not category:
            return jsonify({'success': False, 'error': 'No category specified'}), 400
        
        if DebugCategories.is_enabled(category):
            DebugCategories.disable(category)
            enabled = False
            logger.debug(f"🐛 Debug category '{category}' disabled")
        else:
            DebugCategories.enable(category)
            enabled = True
            logger.debug(f"🐛 Debug category '{category}' enabled")
        
        return jsonify({
            'success': True,
            'category': category,
            'enabled': enabled,
            'all_enabled': DebugCategories.get_enabled()
        })
    
    except Exception as e:
        logger.error(f"Error toggling debug category: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@debug_bp.route('/api/debug/modules', methods=['GET'])
def get_module_debug_levels():
    """
    Returns all configured module-specific debug levels.
    
    Returns:
        JSON mit allen Modulen und ihren Log-Levels
    """
    try:
        flux_logger = FluxLogger()
        module_levels = flux_logger.get_module_log_levels()
        
        return jsonify({
            'success': True,
            'modules': {
                pattern: logging.getLevelName(level)
                for pattern, level in module_levels.items()
            },
            'total': len(module_levels)
        })
    
    except Exception as e:
        logger.error(f"Error getting module debug levels: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@debug_bp.route('/api/debug/modules/enable', methods=['POST'])
def enable_module_debug():
    """
    Activates DEBUG level for one or more modules (runtime, without restart).
    
    Body:
        {
            "modules": ["modules.player.core", "modules.api.*"]
        }
    
    Supports wildcards:
        - "modules.player.*" = All player modules
        - "modules.api.artnet" = Art-Net API only
    """
    try:
        data = request.get_json()
        modules = data.get('modules', [])
        
        if not modules:
            return jsonify({'success': False, 'error': 'No modules specified'}), 400
        
        flux_logger = FluxLogger()
        for module_pattern in modules:
            flux_logger.set_module_log_level(module_pattern, logging.DEBUG)
        
        logger.info(f"🔍 Debug enabled for modules: {', '.join(modules)}")
        
        return jsonify({
            'success': True,
            'message': f'Debug enabled for {len(modules)} module(s)',
            'modules': modules,
            'current_levels': flux_logger.get_module_log_levels()
        })
    
    except Exception as e:
        logger.error(f"Error enabling module debug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@debug_bp.route('/api/debug/modules/disable', methods=['POST'])
def disable_module_debug():
    """
    Deactivates DEBUG level for modules (resets to INFO).
    
    Body:
        {
            "modules": ["modules.player.core", "modules.api.*"]
        }
    """
    try:
        data = request.get_json()
        modules = data.get('modules', [])
        
        if not modules:
            return jsonify({'success': False, 'error': 'No modules specified'}), 400
        
        flux_logger = FluxLogger()
        for module_pattern in modules:
            flux_logger.set_module_log_level(module_pattern, logging.INFO)
        
        logger.info(f"🔍 Debug disabled for modules: {', '.join(modules)}")
        
        return jsonify({
            'success': True,
            'message': f'Debug disabled for {len(modules)} module(s)',
            'modules': modules,
            'current_levels': flux_logger.get_module_log_levels()
        })
    
    except Exception as e:
        logger.error(f"Error disabling module debug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def register_debug_routes(app):
    """
    Registriert Debug-API-Routen in der Flask-App.
    
    Args:
        app: Flask-App-Instanz
    """
    app.register_blueprint(debug_bp)
    logger.debug("✅ Debug API routes registered at /api/debug/*")
