"""
Debug API - Laufzeit-Kontrolle über Debug-Kategorien und Logging
"""
from flask import Blueprint, jsonify, request
from ...core.logger import DebugCategories, get_logger

logger = get_logger(__name__)

debug_bp = Blueprint('debug', __name__)


@debug_bp.route('/api/debug/categories', methods=['GET'])
def get_debug_categories():
    """
    Gibt alle verfügbaren Debug-Kategorien und ihren Status zurück.
    
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
            logger.info("🐛 Alle Debug-Kategorien aktiviert")
            return jsonify({
                'success': True,
                'message': 'All debug categories enabled',
                'enabled': DebugCategories.get_enabled()
            })
        
        DebugCategories.enable(*categories)
        logger.info(f"🐛 Debug-Kategorien aktiviert: {', '.join(categories)}")
        
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
            logger.info("🐛 Alle Debug-Kategorien deaktiviert")
            return jsonify({
                'success': True,
                'message': 'All debug categories disabled',
                'enabled': []
            })
        
        DebugCategories.disable(*categories)
        logger.info(f"🐛 Debug-Kategorien deaktiviert: {', '.join(categories)}")
        
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
            logger.info(f"🐛 Debug-Kategorie '{category}' deaktiviert")
        else:
            DebugCategories.enable(category)
            enabled = True
            logger.info(f"🐛 Debug-Kategorie '{category}' aktiviert")
        
        return jsonify({
            'success': True,
            'category': category,
            'enabled': enabled,
            'all_enabled': DebugCategories.get_enabled()
        })
    
    except Exception as e:
        logger.error(f"Error toggling debug category: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def register_debug_routes(app):
    """
    Registriert Debug-API-Routen in der Flask-App.
    
    Args:
        app: Flask-App-Instanz
    """
    app.register_blueprint(debug_bp)
    logger.info("✅ Debug API routes registered at /api/debug/*")
