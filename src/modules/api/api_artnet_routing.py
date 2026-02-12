"""
ArtNet Routing REST API Endpoints

Provides HTTP endpoints for managing ArtNet objects, outputs, and routing assignments.

Endpoints:
- POST /api/artnet/routing/sync - Sync objects from editor shapes
- GET/POST /api/artnet/routing/objects - List/create objects
- GET/PUT/DELETE /api/artnet/routing/objects/<id> - Get/update/delete object
- GET/POST /api/artnet/routing/outputs - List/create outputs
- GET/PUT/DELETE /api/artnet/routing/outputs/<id> - Get/update/delete output
- POST /api/artnet/routing/assign - Assign object to output
- POST /api/artnet/routing/unassign - Remove object from output
- GET/POST /api/artnet/routing/state - Get/set complete routing state
"""

from flask import jsonify, request
from ..artnet_routing.artnet_routing_manager import ArtNetRoutingManager
from ..artnet_routing.artnet_object import ArtNetObject
from ..artnet_routing.artnet_output import ArtNetOutput
from ..logger import get_logger

logger = get_logger(__name__)


def register_artnet_routing_routes(app, routing_manager: ArtNetRoutingManager):
    """
    Register ArtNet routing API endpoints with Flask app
    
    Args:
        app: Flask application instance
        routing_manager: ArtNetRoutingManager instance
    """
    
    # Helper function to save routing state to session
    def _save_routing_state_to_session(routing_mgr):
        """Save current routing state to session state for persistence"""
        try:
            from ..session_state import get_session_state
            session_state = get_session_state()
            if session_state:
                routing_state = routing_mgr.get_state()
                session_state.set_artnet_routing_state(routing_state)
                logger.debug("ArtNet routing state saved to session")
        except Exception as e:
            logger.warning(f"Could not save routing state to session: {e}")
    
    # ==================== SYNC ====================
    
    @app.route('/api/artnet/routing/sync', methods=['POST'], endpoint='artnet_sync')
    def sync_from_editor():
        """
        Sync ArtNet objects from editor shapes
        
        Request Body:
        {
            "removeOrphaned": false  // Optional, default false
        }
        
        Response:
        {
            "success": true,
            "created": [...],
            "updated": [...],
            "removed": [...],
            "summary": {
                "createdCount": 1,
                "updatedCount": 2,
                "removedCount": 0
            }
        }
        """
        try:
            data = request.get_json() or {}
            remove_orphaned = data.get('removeOrphaned', False)
            
            result = routing_manager.sync_from_editor_shapes(remove_orphaned=remove_orphaned)
            
            # Convert objects to dicts
            created_dicts = [obj.to_dict() for obj in result['created']]
            updated_dicts = [obj.to_dict() for obj in result['updated']]
            
            # Auto-save routing state to session after sync
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({
                'success': True,
                'created': created_dicts,
                'updated': updated_dicts,
                'removed': result['removed'],
                'summary': {
                    'createdCount': len(created_dicts),
                    'updatedCount': len(updated_dicts),
                    'removedCount': len(result['removed'])
                }
            })
        except Exception as e:
            logger.error(f"Sync error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== OBJECTS ====================
    
    @app.route('/api/artnet/routing/objects', methods=['GET'], endpoint='artnet_get_objects')
    def get_objects():
        """
        Get all ArtNet objects
        
        Response:
        {
            "success": true,
            "objects": [...]
        }
        """
        try:
            objects = [obj.to_dict() for obj in routing_manager.get_all_objects()]
            return jsonify({'success': True, 'objects': objects})
        except Exception as e:
            logger.error(f"Get objects error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['GET'], endpoint='artnet_get_object')
    def get_object(obj_id):
        """
        Get single ArtNet object by ID
        
        Response:
        {
            "success": true,
            "object": {...}
        }
        """
        try:
            obj = routing_manager.get_object(obj_id)
            if not obj:
                return jsonify({'success': False, 'error': 'Object not found'}), 404
            
            return jsonify({'success': True, 'object': obj.to_dict()})
        except Exception as e:
            logger.error(f"Get object error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects', methods=['POST'], endpoint='artnet_create_object')
    def create_object():
        """
        Create new ArtNet object
        
        Request Body:
        {
            "id": "obj-abc123",
            "name": "Matrix Left",
            "sourceShapeId": "shape-1",
            "type": "matrix",
            "points": [...],
            "ledType": "RGB",
            ...
        }
        
        Response:
        {
            "success": true,
            "object": {...}
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            obj = ArtNetObject.from_dict(data)
            routing_manager.create_object(obj)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True, 'object': obj.to_dict()}), 201
        except Exception as e:
            logger.error(f"Create object error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['PUT'], endpoint='artnet_update_object')
    def update_object(obj_id):
        """
        Update ArtNet object properties
        
        Request Body:
        {
            "name": "Updated Name",
            "ledType": "RGBW",
            "brightness": 10,
            ...
        }
        
        Response:
        {
            "success": true,
            "object": {...}
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            routing_manager.update_object(obj_id, data)
            obj = routing_manager.get_object(obj_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True, 'object': obj.to_dict()})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Update object error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/objects/<obj_id>', methods=['DELETE'], endpoint='artnet_delete_object')
    def delete_object(obj_id):
        """
        Delete ArtNet object
        
        Response:
        {
            "success": true
        }
        """
        try:
            routing_manager.delete_object(obj_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Delete object error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== OUTPUTS ====================
    
    @app.route('/api/artnet/routing/outputs', methods=['GET'], endpoint='artnet_get_outputs')
    def get_outputs():
        """
        Get all ArtNet outputs
        
        Response:
        {
            "success": true,
            "outputs": [...]
        }
        """
        try:
            outputs = [out.to_dict() for out in routing_manager.get_all_outputs()]
            return jsonify({'success': True, 'outputs': outputs})
        except Exception as e:
            logger.error(f"Get outputs error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['GET'], endpoint='artnet_get_output')
    def get_output(out_id):
        """
        Get single ArtNet output by ID
        
        Response:
        {
            "success": true,
            "output": {...}
        }
        """
        try:
            output = routing_manager.get_output(out_id)
            if not output:
                return jsonify({'success': False, 'error': 'Output not found'}), 404
            
            return jsonify({'success': True, 'output': output.to_dict()})
        except Exception as e:
            logger.error(f"Get output error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs', methods=['POST'], endpoint='artnet_create_output')
    def create_output():
        """
        Create new ArtNet output
        
        Request Body:
        {
            "id": "out-abc123",
            "name": "Main LED Wall",
            "targetIP": "192.168.1.10",
            "subnet": "255.255.255.0",
            "startUniverse": 1,
            "fps": 30,
            ...
        }
        
        Response:
        {
            "success": true,
            "output": {...}
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            output = ArtNetOutput.from_dict(data)
            routing_manager.create_output(output)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True, 'output': output.to_dict()}), 201
        except Exception as e:
            logger.error(f"Create output error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['PUT'], endpoint='artnet_update_output')
    def update_output(out_id):
        """
        Update ArtNet output properties
        
        Request Body:
        {
            "name": "Updated Output",
            "fps": 60,
            "targetIP": "192.168.1.20",
            ...
        }
        
        Response:
        {
            "success": true,
            "output": {...}
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            routing_manager.update_output(out_id, data)
            output = routing_manager.get_output(out_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True, 'output': output.to_dict()})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Update output error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/outputs/<out_id>', methods=['DELETE'], endpoint='artnet_delete_output')
    def delete_output(out_id):
        """
        Delete ArtNet output
        
        Response:
        {
            "success": true
        }
        """
        try:
            routing_manager.delete_output(out_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Delete output error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== ASSIGNMENTS ====================
    
    @app.route('/api/artnet/routing/assign', methods=['POST'], endpoint='artnet_assign')
    def assign_object():
        """
        Assign object to output (many-to-many)
        
        Request Body:
        {
            "objectId": "obj-abc123",
            "outputId": "out-def456"
        }
        
        Response:
        {
            "success": true
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            obj_id = data.get('objectId')
            out_id = data.get('outputId')
            
            if not obj_id or not out_id:
                return jsonify({'success': False, 'error': 'objectId and outputId required'}), 400
            
            routing_manager.assign_object_to_output(obj_id, out_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Assign error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/unassign', methods=['POST'], endpoint='artnet_unassign')
    def unassign_object():
        """
        Remove object from output
        
        Request Body:
        {
            "objectId": "obj-abc123",
            "outputId": "out-def456"
        }
        
        Response:
        {
            "success": true
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'Request body required'}), 400
            
            obj_id = data.get('objectId')
            out_id = data.get('outputId')
            
            if not obj_id or not out_id:
                return jsonify({'success': False, 'error': 'objectId and outputId required'}), 400
            
            routing_manager.remove_object_from_output(obj_id, out_id)
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True})
        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 404
        except Exception as e:
            logger.error(f"Unassign error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    # ==================== STATE ====================
    
    @app.route('/api/artnet/routing/state', methods=['GET'], endpoint='artnet_get_state')
    def get_routing_state():
        """
        Get complete routing state (for session persistence)
        
        Response:
        {
            "success": true,
            "state": {
                "objects": {...},
                "outputs": {...}
            }
        }
        """
        try:
            state = routing_manager.get_state_with_assignments()
            return jsonify({'success': True, 'state': state})
        except Exception as e:
            logger.error(f"Get state error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/artnet/routing/state', methods=['POST'], endpoint='artnet_set_state')
    def set_routing_state():
        """
        Set complete routing state (for session restore)
        
        Request Body:
        {
            "state": {
                "objects": {...},
                "outputs": {...}
            }
        }
        
        Response:
        {
            "success": true
        }
        """
        try:
            data = request.get_json()
            if not data or 'state' not in data:
                return jsonify({'success': False, 'error': 'state property required'}), 400
            
            routing_manager.set_state(data['state'])
            
            # Auto-save to session
            _save_routing_state_to_session(routing_manager)
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Set state error: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
    
    logger.info("✅ ArtNet routing API routes registered")
