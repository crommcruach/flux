"""
ArtNet Routing Manager

Central manager for ArtNet objects, outputs, and routing assignments.
Handles synchronization with editor shapes, CRUD operations, and session state persistence.
"""

from typing import Dict, List, Optional
import uuid

from .artnet_object import ArtNetObject
from .artnet_output import ArtNetOutput
from .point_generator import PointGenerator
from ..logger import get_logger

logger = get_logger(__name__)


class ArtNetRoutingManager:
    """Manages ArtNet objects, outputs, and routing assignments"""
    
    def __init__(self, session_state_manager):
        """
        Initialize routing manager
        
        Args:
            session_state_manager: SessionStateManager instance for state persistence
        """
        self.session = session_state_manager
        self.objects: Dict[str, ArtNetObject] = {}
        self.outputs: Dict[str, ArtNetOutput] = {}
        
        logger.info("ArtNetRoutingManager initialized")
    
    # =============================================================================
    # Sync from Editor
    # =============================================================================
    
    def sync_from_editor_shapes(self, remove_orphaned: bool = False) -> dict:
        """
        Load shapes from session_state.editor.shapes and generate ArtNet objects
        
        This is the PRIMARY sync method that should be called when:
        - New shapes are added in editor
        - Session is loaded/restored
        
        This method:
        1. Reads editor shapes from session state
        2. Creates new ArtNet objects for new shapes
        3. Skips existing objects (preserves ALL properties and assignments)
        4. Optionally removes objects whose shapes no longer exist in editor
        
        NOTE: Existing objects are NOT updated. If you move/resize a shape in the editor,
        the corresponding ArtNet object coordinates will NOT change. This preserves:
        - All LED properties (type, white detection, color correction, etc.)
        - Output assignments
        - User customizations (name, brightness, contrast, delay, etc.)
        
        Args:
            remove_orphaned: If True, deletes objects whose source shapes are missing
        
        Returns:
            Dictionary with:
            - created: List of newly created objects
            - updated: Empty list (objects are never updated)
            - removed: List of removed object IDs (if remove_orphaned=True)
        """
        editor_state = self.session._state.get('editor', {})
        shapes = editor_state.get('shapes', [])
        
        if not shapes:
            logger.info("No editor shapes found in session state")
            return {'created': [], 'updated': [], 'removed': []}
        
        # Track shape IDs that exist in editor
        editor_shape_ids = {shape['id'] for shape in shapes}
        
        created_objects = []
        skipped_objects = []
        
        # Process all shapes from editor
        for shape in shapes:
            shape_id = shape['id']
            
            # Check if object already exists
            existing_obj = self._find_object_by_shape_id(shape_id)
            
            if existing_obj:
                # Skip existing object - preserve all properties and assignments
                skipped_objects.append(existing_obj)
                logger.debug(f"Skipped existing object {existing_obj.id} for shape {shape_id}")
            else:
                # Create new object
                obj = self._create_object_from_shape(shape)
                self.objects[obj.id] = obj
                created_objects.append(obj)
        
        # Remove orphaned objects (whose shapes were deleted in editor)
        removed_ids = []
        if remove_orphaned:
            removed_ids = self._remove_orphaned_objects(editor_shape_ids)
        
        logger.info(
            f"✅ Sync complete: {len(created_objects)} created, "
            f"{len(skipped_objects)} skipped, {len(removed_ids)} removed"
        )
        
        return {
            'created': created_objects,
            'updated': [],  # No longer updating objects
            'removed': removed_ids
        }
    
    def _remove_orphaned_objects(self, valid_shape_ids: set) -> List[str]:
        """
        Remove objects whose source shapes no longer exist in editor
        
        Args:
            valid_shape_ids: Set of shape IDs that exist in editor
        
        Returns:
            List of removed object IDs
        """
        removed_ids = []
        
        # Find objects with missing source shapes
        for obj_id, obj in list(self.objects.items()):
            if obj.source_shape_id and obj.source_shape_id not in valid_shape_ids:
                # Remove from all outputs first
                for output in self.outputs.values():
                    if obj_id in output.assigned_objects:
                        output.assigned_objects.remove(obj_id)
                
                # Remove object
                del self.objects[obj_id]
                removed_ids.append(obj_id)
                logger.debug(f"Removed orphaned object {obj_id} (shape {obj.source_shape_id} deleted)")
        
        return removed_ids
    
    def _find_object_by_shape_id(self, shape_id: str) -> Optional[ArtNetObject]:
        """
        Find ArtNet object by source shape ID
        
        Args:
            shape_id: Editor shape ID
        
        Returns:
            ArtNetObject if found, None otherwise
        """
        for obj in self.objects.values():
            if obj.source_shape_id == shape_id:
                return obj
        return None
    
    def _create_object_from_shape(self, shape: dict) -> ArtNetObject:
        """
        Create new ArtNet object from editor shape
        
        Args:
            shape: Editor shape dictionary from session state
        
        Returns:
            Newly created ArtNetObject
        """
        # Generate LED coordinates
        points = PointGenerator.generate_points(shape)
        
        # Create object with default LED configuration
        obj_id = f"obj-{uuid.uuid4().hex[:8]}"
        obj = ArtNetObject(
            id=obj_id,
            name=shape.get('name', f"Object {obj_id}"),
            source_shape_id=shape['id'],
            type=shape['type'],
            points=points,
            led_type='RGB',  # Default, can be changed by user
            channels_per_pixel=3,
            channel_order='RGB',
            universe_start=1,
            universe_end=1
        )
        
        # Calculate universe range based on LED count
        obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.debug(f"Created object {obj_id}: {len(points)} points, universes {obj.universe_start}-{obj.universe_end}")
        
        return obj
    
    def _update_object_from_shape(self, obj: ArtNetObject, shape: dict) -> ArtNetObject:
        """
        Update existing ArtNet object from modified editor shape
        
        Regenerates LED coordinates but preserves all user-configured properties
        (LED type, white detection, color correction, etc.)
        
        Note: Name is NOT updated to preserve user customization. The name is only
        set when creating a new object from a shape.
        
        Args:
            obj: Existing ArtNetObject
            shape: Updated editor shape dictionary
        
        Returns:
            Updated ArtNetObject
        """
        # Regenerate LED coordinates (shape may have moved/resized)
        obj.points = PointGenerator.generate_points(shape)
        # Note: obj.name is NOT updated - preserve user customization
        obj.type = shape['type']
        
        # Recalculate universe range (point count may have changed)
        obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.debug(f"Updated object {obj.id}: {len(obj.points)} points")
        
        return obj
    
    # =============================================================================
    # State Persistence
    # =============================================================================
    
    def get_state(self) -> dict:
        """
        Get complete routing state for session persistence
        
        Returns:
            Dictionary with objects and outputs (serialized)
        """
        return {
            'objects': {obj_id: obj.to_dict() for obj_id, obj in self.objects.items()},
            'outputs': {out_id: out.to_dict() for out_id, out in self.outputs.items()}
        }
    
    def get_state_with_assignments(self) -> dict:
        """
        Get complete routing state with output assignments included in objects
        
        Returns:
            Dictionary with objects (including outputIds) and outputs
        """
        # Add output IDs to each object
        objects_with_outputs = {}
        for obj_id, obj in self.objects.items():
            obj_dict = obj.to_dict()
            # Find all outputs this object is assigned to
            obj_dict['outputIds'] = [
                out_id for out_id, out in self.outputs.items()
                if obj_id in out.assigned_objects
            ]
            objects_with_outputs[obj_id] = obj_dict
        
        return {
            'objects': objects_with_outputs,
            'outputs': {out_id: out.to_dict() for out_id, out in self.outputs.items()}
        }
    
    def set_state(self, state: dict):
        """
        Restore routing state from session
        
        Args:
            state: Dictionary with objects and outputs (from get_state)
        """
        # Restore objects
        self.objects = {}
        for obj_id, obj_data in state.get('objects', {}).items():
            try:
                self.objects[obj_id] = ArtNetObject.from_dict(obj_data)
            except Exception as e:
                logger.error(f"Failed to restore object {obj_id}: {e}")
        
        # Restore outputs
        self.outputs = {}
        for out_id, out_data in state.get('outputs', {}).items():
            try:
                self.outputs[out_id] = ArtNetOutput.from_dict(out_data)
            except Exception as e:
                logger.error(f"Failed to restore output {out_id}: {e}")
        
        logger.info(f"✅ Restored state: {len(self.objects)} objects, {len(self.outputs)} outputs")
    
    # =============================================================================
    # Object CRUD Operations
    # =============================================================================
    
    def create_object(self, obj: ArtNetObject):
        """
        Add new ArtNet object
        
        Args:
            obj: ArtNetObject to add
        """
        self.objects[obj.id] = obj
        logger.info(f"Created object {obj.id}")
    
    def get_object(self, obj_id: str) -> Optional[ArtNetObject]:
        """
        Get ArtNet object by ID
        
        Args:
            obj_id: Object ID
        
        Returns:
            ArtNetObject if found, None otherwise
        """
        return self.objects.get(obj_id)
    
    def get_all_objects(self) -> Dict[str, ArtNetObject]:
        """
        Get all ArtNet objects
        
        Returns:
            Dictionary of object_id → ArtNetObject
        """
        return self.objects.copy()
    
    def update_object(self, obj_id: str, updates: dict):
        """
        Update ArtNet object properties
        
        Args:
            obj_id: Object ID to update
            updates: Dictionary of property updates
        
        Raises:
            ValueError: If object not found
        """
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        
        obj = self.objects[obj_id]
        
        # Map camelCase to snake_case for common properties
        property_map = {
            'ledType': 'led_type',
            'channelsPerPixel': 'channels_per_pixel',
            'channelOrder': 'channel_order',
            'universeStart': 'universe_start',
            'universeEnd': 'universe_end',
            'whiteDetection': 'white_detection',
            'whiteMode': 'white_mode',
            'whiteThreshold': 'white_threshold',
            'whiteBehavior': 'white_behavior',
            'colorTemp': 'color_temp',
            'inputLayer': 'input_layer',
            'masterId': 'master_id',
            'scaleX': 'scale_x',
            'scaleY': 'scale_y'
        }
        
        # Update properties
        for key, value in updates.items():
            # Convert camelCase to snake_case if needed
            prop_name = property_map.get(key, key)
            
            if hasattr(obj, prop_name):
                # Special handling for points - convert dicts to ArtNetPoint objects
                if prop_name == 'points' and isinstance(value, list):
                    from .artnet_object import ArtNetPoint
                    value = [ArtNetPoint.from_dict(p) if isinstance(p, dict) else p for p in value]
                
                setattr(obj, prop_name, value)
        
        # Recalculate universe range if LED config changed
        if any(k in updates for k in ['ledType', 'led_type', 'channelsPerPixel', 'channels_per_pixel', 'points']):
            obj.universe_start, obj.universe_end = obj.calculate_universe_range()
        
        logger.info(f"Updated object {obj_id}")
    
    def delete_object(self, obj_id: str):
        """
        Delete ArtNet object
        
        Also removes object from all output assignments.
        
        Args:
            obj_id: Object ID to delete
        
        Raises:
            ValueError: If object not found
        """
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        
        # Remove from all outputs
        for output in self.outputs.values():
            if obj_id in output.assigned_objects:
                output.assigned_objects.remove(obj_id)
        
        del self.objects[obj_id]
        logger.info(f"Deleted object {obj_id}")
    
    # =============================================================================
    # Output CRUD Operations
    # =============================================================================
    
    def create_output(self, output: ArtNetOutput):
        """
        Add new ArtNet output
        
        Args:
            output: ArtNetOutput to add
        """
        self.outputs[output.id] = output
        logger.info(f"Created output {output.id}")
    
    def get_output(self, out_id: str) -> Optional[ArtNetOutput]:
        """
        Get ArtNet output by ID
        
        Args:
            out_id: Output ID
        
        Returns:
            ArtNetOutput if found, None otherwise
        """
        return self.outputs.get(out_id)
    
    def get_all_outputs(self) -> Dict[str, ArtNetOutput]:
        """
        Get all ArtNet outputs
        
        Returns:
            Dictionary of output_id → ArtNetOutput
        """
        return self.outputs.copy()
    
    def update_output(self, out_id: str, updates: dict):
        """
        Update ArtNet output properties
        
        Args:
            out_id: Output ID to update
            updates: Dictionary of property updates
        
        Raises:
            ValueError: If output not found
        """
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        
        # Map camelCase to snake_case for common properties
        property_map = {
            'targetIP': 'target_ip',
            'startUniverse': 'start_universe',
            'deltaEnabled': 'delta_enabled',
            'deltaThreshold': 'delta_threshold',
            'fullFrameInterval': 'full_frame_interval',
            'assignedObjects': 'assigned_objects'
        }
        
        # Update properties
        for key, value in updates.items():
            # Convert camelCase to snake_case if needed
            prop_name = property_map.get(key, key)
            
            if hasattr(output, prop_name):
                setattr(output, prop_name, value)
        
        logger.info(f"Updated output {out_id}")
    
    def delete_output(self, out_id: str):
        """
        Delete ArtNet output
        
        Args:
            out_id: Output ID to delete
        
        Raises:
            ValueError: If output not found
        """
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        del self.outputs[out_id]
        logger.info(f"Deleted output {out_id}")
    
    # =============================================================================
    # Assignment Operations
    # =============================================================================
    
    def assign_object_to_output(self, obj_id: str, out_id: str):
        """
        Assign ArtNet object to output (many-to-many)
        
        Args:
            obj_id: Object ID to assign
            out_id: Output ID to assign to
        
        Raises:
            ValueError: If object or output not found
        """
        if obj_id not in self.objects:
            raise ValueError(f"Object {obj_id} not found")
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        if obj_id not in output.assigned_objects:
            output.assigned_objects.append(obj_id)
            logger.info(f"Assigned object {obj_id} to output {out_id}")
        else:
            logger.debug(f"Object {obj_id} already assigned to output {out_id}")
    
    def remove_object_from_output(self, obj_id: str, out_id: str):
        """
        Remove ArtNet object from output
        
        Args:
            obj_id: Object ID to remove
            out_id: Output ID to remove from
        
        Raises:
            ValueError: If output not found
        """
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        if obj_id in output.assigned_objects:
            output.assigned_objects.remove(obj_id)
            logger.info(f"Removed object {obj_id} from output {out_id}")
        else:
            logger.debug(f"Object {obj_id} not assigned to output {out_id}")
    
    def get_objects_for_output(self, out_id: str) -> List[ArtNetObject]:
        """
        Get all objects assigned to an output
        
        Args:
            out_id: Output ID
        
        Returns:
            List of ArtNetObject instances assigned to the output
        
        Raises:
            ValueError: If output not found
        """
        if out_id not in self.outputs:
            raise ValueError(f"Output {out_id} not found")
        
        output = self.outputs[out_id]
        objects = []
        
        for obj_id in output.assigned_objects:
            if obj_id in self.objects:
                objects.append(self.objects[obj_id])
            else:
                logger.warning(f"Assigned object {obj_id} not found")
        
        return objects
    
    def get_outputs_for_object(self, obj_id: str) -> List[ArtNetOutput]:
        """
        Get all outputs that have an object assigned
        
        Args:
            obj_id: Object ID
        
        Returns:
            List of ArtNetOutput instances that have the object assigned
        """
        outputs = []
        
        for output in self.outputs.values():
            if obj_id in output.assigned_objects:
                outputs.append(output)
        
        return outputs
