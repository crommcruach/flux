"""
Output manager - coordinates all video outputs
Distributes frames to multiple outputs with slice and source routing support
"""

import logging
import numpy as np
from typing import Dict, Optional, Any
import threading

from .slices import SliceManager
from .base import OutputBase

logger = logging.getLogger(__name__)


class OutputManager:
    """
    Manages multiple video outputs with slice and source routing
    
    Features:
    - Register/unregister output plugins
    - Distribute frames to all active outputs
    - Slice assignment per output
    - Source routing (canvas/clip/layer)
    - Thread-safe frame distribution
    - Statistics aggregation
    - Session state persistence
    """
    
    def __init__(self, player_name: str, canvas_width: int, canvas_height: int, config: dict):
        """
        Initialize output manager
        
        Args:
            player_name: Name of the player ('video' or 'artnet')
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
            config: Configuration dictionary
        """
        self.player_name = player_name
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.config = config
        
        # Output plugins
        self.outputs: Dict[str, OutputBase] = {}
        
        # Slice manager
        self.slice_manager = SliceManager(canvas_width, canvas_height)
        
        # Latest frames
        self.composite_frame: Optional[np.ndarray] = None
        self.layer_manager: Optional[Any] = None
        self.current_clip_id: Optional[str] = None
        
        # Thread safety
        self.frame_lock = threading.Lock()
        
        # State persistence callback
        self._state_save_callback = None
        
        logger.debug(f"✅ OutputManager initialized for '{player_name}' ({canvas_width}x{canvas_height})")
    
    def load_outputs_from_config(self, output_definitions: list) -> int:
        """
        Load and register outputs from config definitions
        
        Args:
            output_definitions: List of output configuration dicts from config.json
            
        Returns:
            int: Number of outputs successfully created
        """
        from .plugins import DisplayOutput, VirtualOutput
        
        created_count = 0
        
        for output_def in output_definitions:
            output_id = output_def.get('id')
            output_type = output_def.get('type')
            enabled = output_def.get('enabled', True)
            
            if not output_id or not output_type:
                logger.warning(f"[{self.player_name}] Skipping invalid output definition: {output_def}")
                continue
            
            # Skip if output already exists
            if output_id in self.outputs:
                logger.debug(f"[{self.player_name}] Output '{output_id}' already registered")
                continue
            
            try:
                # Create output instance based on type
                if output_type == 'display':
                    output = DisplayOutput(output_id, output_def)
                elif output_type == 'virtual':
                    output = VirtualOutput(output_id, output_def)
                else:
                    logger.warning(f"[{self.player_name}] Unknown output type '{output_type}' for '{output_id}'")
                    continue
                
                # Register output
                self.outputs[output_id] = output
                logger.debug(f"✅ [{self.player_name}] Output '{output_id}' created (type: {output_type})")
                
                # Enable if configured
                if enabled:
                    if output.enable():
                        logger.debug(f"✅ [{self.player_name}] Output '{output_id}' enabled")
                    else:
                        logger.error(f"❌ [{self.player_name}] Failed to enable output '{output_id}'")
                
                created_count += 1
                
            except Exception as e:
                logger.error(f"[{self.player_name}] Failed to create output '{output_id}': {e}", exc_info=True)
        
        return created_count
    
    def register_output(self, output_id: str, output: OutputBase):
        """
        Register an output plugin
        
        Args:
            output_id: Unique identifier
            output: Output plugin instance
        """
        self.outputs[output_id] = output
        logger.debug(f"[{self.player_name}] Output '{output_id}' registered")
        self._save_state()
    
    def create_output(self, output_id: str, config: dict) -> bool:
        """
        Create a new output dynamically
        
        Args:
            output_id: Unique output identifier
            config: Output configuration dict
            
        Returns:
            bool: True if created successfully
        """
        try:
            output_type = config.get('type')
            
            if output_type == 'display':
                from .plugins import DisplayOutput
                output = DisplayOutput(output_id, config)
            elif output_type == 'virtual':
                from .plugins import VirtualOutput
                output = VirtualOutput(output_id, config)
            else:
                logger.error(f"[{self.player_name}] Unknown output type: {output_type}")
                return False
            
            self.register_output(output_id, output)
            
            if config.get('enabled', False):
                self.enable_output(output_id)
            
            logger.debug(f"✅ [{self.player_name}] Output '{output_id}' created dynamically (type: {output_type})")
            return True
            
        except Exception as e:
            logger.error(f"[{self.player_name}] Failed to create output '{output_id}': {e}", exc_info=True)
            return False
    
    def unregister_output(self, output_id: str) -> bool:
        """
        Unregister and cleanup an output plugin
        
        Args:
            output_id: Output to remove
            
        Returns:
            bool: True if removed
        """
        if output_id in self.outputs:
            output = self.outputs[output_id]
            if output.enabled:
                output.disable()
            del self.outputs[output_id]
            logger.debug(f"[{self.player_name}] Output '{output_id}' unregistered")
            self._save_state()
            return True
        return False
    
    def enable_output(self, output_id: str) -> bool:
        """
        Enable a specific output
        
        Args:
            output_id: Output to enable
            
        Returns:
            bool: True if enabled
        """
        if output_id not in self.outputs:
            logger.error(f"[{self.player_name}] Output '{output_id}' not found")
            return False
        
        result = self.outputs[output_id].enable()
        if result:
            self._save_state()
        return result
    
    def disable_output(self, output_id: str) -> bool:
        """
        Disable a specific output
        
        Args:
            output_id: Output to disable
            
        Returns:
            bool: True if disabled
        """
        if output_id not in self.outputs:
            logger.error(f"[{self.player_name}] Output '{output_id}' not found")
            return False
        
        self.outputs[output_id].disable()
        self._save_state()
        return True
    
    def update_frame(self, composite_frame: np.ndarray, 
                    layer_manager: Optional[Any] = None,
                    current_clip_id: Optional[str] = None):
        """
        Update frame and distribute to all active outputs
        
        Args:
            composite_frame: Full composited canvas frame
            layer_manager: Layer manager reference (for layer routing)
            current_clip_id: Current clip UUID (for clip routing)
        """
        with self.frame_lock:
            self.composite_frame = composite_frame
            self.layer_manager = layer_manager
            self.current_clip_id = current_clip_id
        
        # Debug: Log first few frames
        if not hasattr(self, '_frame_count'):
            self._frame_count = 0
        self._frame_count += 1
        if self._frame_count <= 5:
            logger.debug(f"[{self.player_name}] update_frame called (frame #{self._frame_count}), outputs: {len(self.outputs)}, enabled: {sum(1 for o in self.outputs.values() if o.enabled)}")
        
        # Distribute to all enabled outputs (use list() to avoid RuntimeError if outputs dict changes during iteration)
        for output_id, output in list(self.outputs.items()):
            if not output.enabled:
                continue
            
            try:
                # Get frame for this output (with source routing)
                frame = self._get_frame_for_output(output)
                
                if frame is not None:
                    # Queue frame for output
                    output.queue_frame(frame)
            
            except Exception as e:
                logger.error(f"[{self.player_name}] Error distributing to '{output_id}': {e}", exc_info=True)
    
    def _get_frame_for_output(self, output: OutputBase) -> Optional[np.ndarray]:
        """
        Get frame for specific output with source routing
        
        Args:
            output: Output plugin
            
        Returns:
            np.ndarray or None: Processed frame
        """
        # Check if this output has a composition (multi-slice)
        composition = output.config.get('composition', None)
        if composition and isinstance(composition, dict) and 'slices' in composition:
            # Multi-slice composition mode
            return self._render_composition(composition)
        
        source = output.config.get('source', 'canvas')
        
        # Get source frame
        if source == 'canvas':
            # Full composited canvas
            frame = self.composite_frame
        
        elif source.startswith('clip:'):
            # Clip routing
            clip_id = source.split(':', 1)[1]
            if clip_id == 'current':
                # Get current active clip
                frame = self._get_current_clip_frame()
            else:
                # Get specific clip by UUID
                frame = self._get_clip_frame(clip_id)
        
        elif source.startswith('layer:'):
            # Layer routing
            parts = source.split(':')
            try:
                layer_index = int(parts[1])
                include_sub_layers = len(parts) > 2 and parts[2] == 'inclusive'
                
                if include_sub_layers:
                    # Composite layers 0 through layer_index
                    frame = self._get_composite_layers_through(layer_index)
                else:
                    # Get specific layer only (isolated)
                    frame = self._get_layer_frame(layer_index)
            except (ValueError, IndexError):
                logger.error(f"Invalid layer source: {source}")
                frame = self.composite_frame
        
        else:
            # Unknown source, fallback to canvas
            logger.warning(f"Unknown source '{source}', using canvas")
            frame = self.composite_frame
        
        if frame is None:
            return None
        
        # Apply slice if configured
        slice_config = output.config.get('slice', 'full')
        if slice_config != 'full':
            # Check if slice is a dict (inline slice definition) or string (slice ID)
            if isinstance(slice_config, dict):
                # Inline slice definition - apply it directly
                frame = self._apply_inline_slice(frame, slice_config)
            else:
                # Slice ID - look it up in slice manager
                frame = self.slice_manager.get_slice(slice_config, frame)
        
        return frame
    
    def _get_current_clip_frame(self) -> Optional[np.ndarray]:
        """Get current active clip frame (before layer compositing)"""
        if self.layer_manager and hasattr(self.layer_manager, 'get_current_clip_frame'):
            try:
                return self.layer_manager.get_current_clip_frame()
            except Exception as e:
                logger.error(f"Failed to get current clip frame: {e}")
        return self.composite_frame
    
    def _get_clip_frame(self, clip_id: str) -> Optional[np.ndarray]:
        """Get specific clip frame by UUID"""
        if self.layer_manager and hasattr(self.layer_manager, 'get_clip_frame'):
            try:
                return self.layer_manager.get_clip_frame(clip_id)
            except Exception as e:
                logger.error(f"Failed to get clip frame '{clip_id}': {e}")
        return self.composite_frame
    
    def _get_layer_frame(self, layer_index: int) -> Optional[np.ndarray]:
        """Get specific layer frame (isolated, no compositing)"""
        if self.layer_manager and hasattr(self.layer_manager, 'get_layer_frame'):
            try:
                return self.layer_manager.get_layer_frame(layer_index)
            except Exception as e:
                logger.error(f"Failed to get layer {layer_index} frame: {e}")
        return self.composite_frame
    
    def _get_composite_layers_through(self, max_layer_index: int) -> Optional[np.ndarray]:
        """
        Get hierarchical composite of layers 0 through max_layer_index
        (Layers composited with blend modes)
        """
        if self.layer_manager and hasattr(self.layer_manager, 'composite_layers_through'):
            try:
                return self.layer_manager.composite_layers_through(max_layer_index)
            except Exception as e:
                logger.error(f"Failed to composite layers through {max_layer_index}: {e}")
        return self.composite_frame
    
    def _apply_inline_slice(self, frame: np.ndarray, slice_config: dict) -> np.ndarray:
        """
        Apply inline slice definition directly to frame
        
        Args:
            frame: Source frame
            slice_config: Dict with slice parameters (x, y, width, height, shape, rotation, etc.)
            
        Returns:
            np.ndarray: Sliced frame
        """
        try:
            import cv2
            import numpy as np
            
            shape = slice_config.get('shape', 'rectangle')
            x = int(slice_config.get('x', 0))
            y = int(slice_config.get('y', 0))
            width = int(slice_config.get('width', frame.shape[1]))
            height = int(slice_config.get('height', frame.shape[0]))
            rotation = slice_config.get('rotation', 0)
            transform_corners = slice_config.get('transformCorners', None)
            
            h, w = frame.shape[:2]
            
            # Check if perspective transform is needed
            if transform_corners and len(transform_corners) == 4:
                logger.debug(f"Applying perspective transform with corners: {transform_corners}")
                try:
                    # Convert transform corners to numpy array
                    src_points = np.float32([
                        [transform_corners[0]['x'], transform_corners[0]['y']],  # top-left
                        [transform_corners[1]['x'], transform_corners[1]['y']],  # top-right
                        [transform_corners[2]['x'], transform_corners[2]['y']],  # bottom-right
                        [transform_corners[3]['x'], transform_corners[3]['y']]   # bottom-left
                    ])
                    
                    # Define destination rectangle (output size)
                    dst_points = np.float32([
                        [0, 0],              # top-left
                        [width, 0],          # top-right
                        [width, height],     # bottom-right
                        [0, height]          # bottom-left
                    ])
                    
                    # Calculate perspective transform matrix
                    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
                    
                    # Apply perspective warp
                    sliced = cv2.warpPerspective(frame, matrix, (width, height))
                    logger.debug(f"Perspective transform applied successfully")
                    
                    return sliced
                except Exception as e:
                    logger.error(f"Failed to apply perspective transform: {e}")
                    # Fall through to normal slice extraction
            
            if shape == 'rectangle':
                # Clamp coordinates to frame bounds
                x1 = max(0, min(x, w))
                y1 = max(0, min(y, h))
                x2 = max(0, min(x + width, w))
                y2 = max(0, min(y + height, h))
                
                # Extract region
                sliced = frame[y1:y2, x1:x2].copy()
                
                # Resize to target dimensions if needed
                if sliced.shape[1] != width or sliced.shape[0] != height:
                    sliced = cv2.resize(sliced, (width, height))
                
                # Apply rotation if specified
                if rotation != 0:
                    center = (width // 2, height // 2)
                    matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
                    sliced = cv2.warpAffine(sliced, matrix, (width, height))
                
                # Apply masks if present
                masks = slice_config.get('masks', [])
                if masks and len(masks) > 0:
                    logger.debug(f"Applying {len(masks)} mask(s) to slice")
                    for mask in masks:
                        if mask.get('visible', True):
                            sliced = self._apply_mask_to_frame(sliced, mask)
                
                return sliced
            
            else:
                # For complex shapes (circle, polygon, etc.), fall back to full frame extraction for now
                logger.warning(f"Inline slice shape '{shape}' not fully supported, using rectangle")
                x1 = max(0, min(x, w))
                y1 = max(0, min(y, h))
                x2 = max(0, min(x + width, w))
                y2 = max(0, min(y + height, h))
                sliced = frame[y1:y2, x1:x2].copy()
                
                if sliced.shape[1] != width or sliced.shape[0] != height:
                    sliced = cv2.resize(sliced, (width, height))
                
                return sliced
                
        except Exception as e:
            logger.error(f"Failed to apply inline slice: {e}", exc_info=True)
            return frame  # Return original frame on error
    
    def _apply_mask_to_frame(self, frame: np.ndarray, mask_config: dict) -> np.ndarray:
        """
        Apply a mask to frame (make masked region black)
        
        Args:
            frame: Input frame
            mask_config: Mask definition with shape, position, etc.
        
        Returns:
            np.ndarray: Frame with mask applied
        """
        try:
            import cv2
            import numpy as np
            
            h, w = frame.shape[:2]
            mask_shape = mask_config.get('shape', 'circle')
            
            # Create mask image (white = keep, black = remove)
            mask = np.ones((h, w), dtype=np.uint8) * 255
            
            if mask_shape == 'rectangle':
                x = int(mask_config.get('x', 0))
                y = int(mask_config.get('y', 0))
                mask_width = int(mask_config.get('width', w))
                mask_height = int(mask_config.get('height', h))
                cv2.rectangle(mask, (x, y), (x + mask_width, y + mask_height), 0, -1)
                
            elif mask_shape == 'circle':
                centerX = int(mask_config.get('centerX', w // 2))
                centerY = int(mask_config.get('centerY', h // 2))
                radius = int(mask_config.get('radius', min(w, h) // 4))
                cv2.circle(mask, (centerX, centerY), radius, 0, -1)
                
            elif mask_shape in ['polygon', 'triangle', 'freehand']:
                points = mask_config.get('points', [])
                if points and len(points) >= 3:
                    pts = np.array([[int(p.get('x', 0)), int(p.get('y', 0))] for p in points], dtype=np.int32)
                    cv2.fillPoly(mask, [pts], 0)
            
            # Apply mask
            frame_masked = cv2.bitwise_and(frame, frame, mask=mask)
            return frame_masked
            
        except Exception as e:
            logger.error(f"Failed to apply mask: {e}")
            return frame
    
    def _render_composition(self, composition: dict) -> Optional[np.ndarray]:
        """
        Render multi-slice composition into single output frame
        
        Args:
            composition: Dict with width, height, and slices array
            
        Returns:
            np.ndarray: Composited output frame
        """
        try:
            import cv2
            import numpy as np
            
            width = composition.get('width', 1920)
            height = composition.get('height', 1080)
            comp_slices = composition.get('slices', [])
            
            # Create black output canvas
            output_frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Get source frame (canvas composite)
            source_frame = self.composite_frame
            if source_frame is None:
                return output_frame
            
            logger.debug(f"Rendering composition with {len(comp_slices)} slices")
            
            # Render each slice in the composition
            for comp_slice in comp_slices:
                slice_id = comp_slice.get('sliceId')
                out_x = int(comp_slice.get('x', 0))
                out_y = int(comp_slice.get('y', 0))
                out_width = int(comp_slice.get('width', 100))
                out_height = int(comp_slice.get('height', 100))
                
                # Get slice definition (look up in session state or use inline)
                # For now, assume sliceId refers to a slice object that has x, y, width, height
                # We'll need to extract that slice from the source frame
                
                # This is a simplified version - you may need to integrate with slice_manager
                # For now, treat sliceId as inline slice config lookup
                slice_frame = self._get_slice_frame_by_id(slice_id, source_frame)
                
                if slice_frame is None:
                    continue
                
                # Resize slice to target dimensions if needed
                if slice_frame.shape[1] != out_width or slice_frame.shape[0] != out_height:
                    slice_frame = cv2.resize(slice_frame, (out_width, out_height))
                
                # Place slice on output canvas
                # Clamp to output bounds
                x1 = max(0, out_x)
                y1 = max(0, out_y)
                x2 = min(width, out_x + out_width)
                y2 = min(height, out_y + out_height)
                
                if x2 > x1 and y2 > y1:
                    # Calculate source region if slice is partially outside bounds
                    src_x1 = 0 if out_x >= 0 else -out_x
                    src_y1 = 0 if out_y >= 0 else -out_y
                    src_x2 = src_x1 + (x2 - x1)
                    src_y2 = src_y1 + (y2 - y1)
                    
                    output_frame[y1:y2, x1:x2] = slice_frame[src_y1:src_y2, src_x1:src_x2]
            
            return output_frame
            
        except Exception as e:
            logger.error(f"Failed to render composition: {e}", exc_info=True)
            return np.zeros((composition.get('height', 1080), composition.get('width', 1920), 3), dtype=np.uint8)
    
    def _get_slice_frame_by_id(self, slice_id: str, source_frame: np.ndarray) -> Optional[np.ndarray]:
        """
        Get slice frame by ID - looks up slice definition and extracts it from source
        
        Args:
            slice_id: Slice identifier
            source_frame: Source frame to extract from
            
        Returns:
            np.ndarray or None: Extracted slice frame
        """
        try:
            # Use slice_manager to get and extract the slice
            if slice_id == 'full':
                return source_frame
            
            # Get slice from slice_manager and extract it
            # Note: get_slice(slice_id, frame) - correct order!
            slice_frame = self.slice_manager.get_slice(slice_id, source_frame)
            
            if slice_frame is None:
                logger.warning(f"Slice '{slice_id}' not found or failed to extract")
                return None
            
            return slice_frame
            
        except Exception as e:
            logger.error(f"Failed to get slice frame '{slice_id}': {e}")
            return None
    
    def set_output_source(self, output_id: str, source: str) -> bool:
        """
        Set source for specific output
        
        Args:
            output_id: Output to configure
            source: Source string ('canvas', 'clip:<id>', 'layer:<index>', 'layer:<index>:inclusive')
            
        Returns:
            bool: True if set successfully
        """
        if output_id not in self.outputs:
            return False
        
        self.outputs[output_id].config['source'] = source
        logger.debug(f"[{self.player_name}] Output '{output_id}' source set to '{source}'")
        self._save_state()
        return True
    
    def set_output_slice(self, output_id: str, slice_id: str) -> bool:
        """
        Set slice for specific output
        
        Args:
            output_id: Output to configure
            slice_id: Slice identifier
            
        Returns:
            bool: True if set successfully
        """
        if output_id not in self.outputs:
            return False
        
        if slice_id not in self.slice_manager.slices and slice_id != 'full':
            logger.warning(f"Slice '{slice_id}' not found")
            return False
        
        self.outputs[output_id].config['slice'] = slice_id
        # Clear composition when setting single slice
        self.outputs[output_id].config.pop('composition', None)
        logger.debug(f"[{self.player_name}] Output '{output_id}' slice set to '{slice_id}'")
        self._save_state()
        return True
    
    def set_output_composition(self, output_id: str, composition: dict) -> bool:
        """
        Set composition (multiple slices) for specific output
        
        Args:
            output_id: Output to configure
            composition: Composition dict with 'width', 'height', 'slices' array
                        Each slice in array: {sliceId, x, y, width, height, scale}
            
        Returns:
            bool: True if set successfully
        """
        if output_id not in self.outputs:
            logger.error(f"Output '{output_id}' not found")
            return False
        
        # Validate composition structure
        if 'slices' not in composition or not isinstance(composition['slices'], list):
            logger.error(f"Invalid composition structure for '{output_id}'")
            return False
        
        # Validate all slices exist
        for comp_slice in composition['slices']:
            slice_id = comp_slice.get('sliceId')
            if not slice_id or (slice_id not in self.slice_manager.slices and slice_id != 'full'):
                logger.warning(f"Slice '{slice_id}' in composition not found")
                return False
        
        # Store composition in output config
        self.outputs[output_id].config['composition'] = composition
        # Clear single slice when setting composition
        self.outputs[output_id].config.pop('slice', None)
        
        logger.debug(f"[{self.player_name}] Output '{output_id}' composition set with {len(composition['slices'])} slices")
        self._save_state()
        return True
    
    def get_statistics(self) -> Dict:
        """
        Get aggregated statistics from all outputs
        
        Returns:
            dict: Statistics for each output
        """
        return {
            output_id: output.get_statistics()
            for output_id, output in self.outputs.items()
        }
    
    def cleanup(self):
        """Cleanup all outputs"""
        for output_id, output in list(self.outputs.items()):
            try:
                if output.enabled:
                    output.disable()
            except Exception as e:
                logger.error(f"Error cleaning up output '{output_id}': {e}")
        
        self.outputs.clear()
        logger.debug(f"[{self.player_name}] OutputManager cleaned up")
    
    def get_state(self) -> dict:
        """
        Get complete output state for session persistence
        
        Returns:
            dict: {outputs, slices, enabled_outputs}
        """
        return {
            'outputs': {
                output_id: {
                    'type': output.config.get('type'),
                    'source': output.config.get('source', 'canvas'),
                    'slice': output.config.get('slice', 'full'),
                    'composition': output.config.get('composition'),  # Include composition data
                    'monitor_index': output.config.get('monitor_index', 0),
                    'resolution': output.config.get('resolution', [1920, 1080]),
                    'fps': output.config.get('fps', 30),
                    'fullscreen': output.config.get('fullscreen', True),
                    'window_title': output.config.get('window_title', ''),
                    'enabled': output.enabled
                }
                for output_id, output in self.outputs.items()
            },
            'slices': self.slice_manager.get_state(),
            'enabled_outputs': [
                output_id for output_id, output in self.outputs.items()
                if output.enabled
            ]
        }
    
    def set_state(self, state: dict):
        """
        Restore output state from session
        
        Args:
            state: Dict from get_state()
        """
        # Restore slices
        if 'slices' in state:
            self.slice_manager.set_state(state['slices'])
        
        # Update output configurations
        if 'outputs' in state:
            for output_id, output_config in state['outputs'].items():
                if output_id in self.outputs:
                    # Update existing output
                    output = self.outputs[output_id]
                    output.config.update(output_config)
                    
                    # Handle enable/disable
                    if output_config.get('enabled', False) and not output.enabled:
                        self.enable_output(output_id)
                    elif not output_config.get('enabled', False) and output.enabled:
                        self.disable_output(output_id)
                else:
                    # Recreate dynamically created output (not in config)
                    output_type = output_config.get('type')
                    
                    if output_type == 'virtual':
                        from .plugins import VirtualOutput
                        output = VirtualOutput(output_id, output_config)
                        self.register_output(output_id, output)
                        
                        if output_config.get('enabled', False):
                            self.enable_output(output_id)
                    
                    elif output_type == 'display':
                        from .plugins import DisplayOutput
                        output = DisplayOutput(output_id, output_config)
                        self.register_output(output_id, output)
                        
                        if output_config.get('enabled', False):
                            self.enable_output(output_id)
                    
                    else:
                        logger.warning(f"Cannot restore output '{output_id}' with unknown type '{output_type}'")
        
        logger.debug(f"[{self.player_name}] Output state restored from session")
    
    def add_slice(self, slice_id: str, slice_data: dict) -> bool:
        """
        Add or update a slice definition
        
        Args:
            slice_id: Unique slice identifier
            slice_data: Slice configuration dict
            
        Returns:
            bool: True if added
        """
        try:
            # Ensure coordinates are integers (convert if needed)
            x = int(slice_data.get('x', 0))
            y = int(slice_data.get('y', 0))
            width = int(slice_data.get('width', self.canvas_width))
            height = int(slice_data.get('height', self.canvas_height))
            rotation = float(slice_data.get('rotation', 0))
            
            # Ignore complex soft_edge for now (SliceDefinition only supports int)
            soft_edge = None
            
            self.slice_manager.add_slice(
                slice_id=slice_id,
                x=x, y=y,
                width=width, height=height,
                rotation=rotation,
                shape=slice_data.get('shape', 'rectangle'),
                soft_edge=soft_edge,
                description=slice_data.get('description', ''),
                points=slice_data.get('points')
            )
            self._save_state()
            return True
        except Exception as e:
            logger.error(f"Failed to add slice '{slice_id}': {e}", exc_info=True)
            return False
    
    def remove_slice(self, slice_id: str) -> bool:
        """
        Remove a slice definition
        
        Args:
            slice_id: Slice to remove
            
        Returns:
            bool: True if removed
        """
        if self.slice_manager.remove_slice(slice_id):
            self._save_state()
            return True
        return False
    
    def update_slice(self, slice_id: str, slice_data: dict) -> bool:
        """
        Update an existing slice definition
        
        Args:
            slice_id: Slice to update
            slice_data: New slice configuration
            
        Returns:
            bool: True if updated
        """
        return self.add_slice(slice_id, slice_data)
    
    def set_state_save_callback(self, callback):
        """
        Set callback function for automatic state persistence
        
        Args:
            callback: Function to call when state changes (receives player_name and state dict)
        """
        self._state_save_callback = callback
        logger.debug(f"[{self.player_name}] State save callback registered")
    
    def _save_state(self):
        """Internal method to trigger state save if callback is set"""
        if self._state_save_callback:
            try:
                state = self.get_state()
                self._state_save_callback(self.player_name, state)
            except Exception as e:
                logger.error(f"Failed to save output state: {e}")
    
    def add_slice(self, slice_id: str, slice_data: dict) -> bool:
        """
        Add or update a slice definition
        
        Args:
            slice_id: Unique slice identifier
            slice_data: Slice configuration dict
            
        Returns:
            bool: True if added
        """
        try:
            # Ensure coordinates are integers (convert if needed)
            x = int(slice_data.get('x', 0))
            y = int(slice_data.get('y', 0))
            width = int(slice_data.get('width', self.canvas_width))
            height = int(slice_data.get('height', self.canvas_height))
            rotation = float(slice_data.get('rotation', 0))
            
            # Ignore complex soft_edge for now (SliceDefinition only supports int)
            soft_edge = None
            
            self.slice_manager.add_slice(
                slice_id=slice_id,
                x=x, y=y,
                width=width, height=height,
                rotation=rotation,
                shape=slice_data.get('shape', 'rectangle'),
                soft_edge=soft_edge,
                description=slice_data.get('description', ''),
                points=slice_data.get('points')
            )
            self._save_state()
            return True
        except Exception as e:
            logger.error(f"Failed to add slice '{slice_id}': {e}", exc_info=True)
            return False
    
    def remove_slice(self, slice_id: str) -> bool:
        """
        Remove a slice definition
        
        Args:
            slice_id: Slice to remove
            
        Returns:
            bool: True if removed
        """
        if self.slice_manager.remove_slice(slice_id):
            self._save_state()
            return True
        return False
    
    def update_slice(self, slice_id: str, slice_data: dict) -> bool:
        """
        Update an existing slice definition
        
        Args:
            slice_id: Slice to update
            slice_data: New slice configuration
            
        Returns:
            bool: True if updated
        """
        return self.add_slice(slice_id, slice_data)
    
    def set_state_save_callback(self, callback):
        """
        Set callback function for automatic state persistence
        
        Args:
            callback: Function to call when state changes (receives player_name and state dict)
        """
        self._state_save_callback = callback
        logger.debug(f"[{self.player_name}] State save callback registered")
    
    def _save_state(self):
        """Internal method to trigger state save if callback is set"""
        if self._state_save_callback:
            try:
                state = self.get_state()
                self._state_save_callback(self.player_name, state)
            except Exception as e:
                logger.error(f"Failed to save output state: {e}")
