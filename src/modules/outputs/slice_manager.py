"""
Slice manager - handles slice definitions and frame extraction
Supports rectangles, polygons, circles with masks, soft edges, and rotation
"""

import logging
import cv2
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SliceDefinition:
    """Definition of a slice region"""
    slice_id: str
    x: int
    y: int
    width: int
    height: int
    rotation: float = 0  # Degrees
    shape: str = 'rectangle'  # 'rectangle', 'polygon', 'circle'
    soft_edge: Optional[int] = None  # Soft edge blur radius
    mask: Optional[np.ndarray] = None  # Custom mask
    description: str = ''
    points: Optional[List[Tuple[int, int]]] = None  # For polygon shape


class SliceManager:
    """
    Manages slice definitions and extracts slices from frames
    
    Features:
    - Rectangle, polygon, and circle slices
    - Rotation support
    - Soft edge blurring
    - Custom masks
    - Coordinate transformations
    """
    
    def __init__(self, canvas_width: int, canvas_height: int):
        """
        Initialize slice manager
        
        Args:
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.slices: Dict[str, SliceDefinition] = {}
        
        # Add default "full" slice
        self.add_slice(
            slice_id='full',
            x=0, y=0,
            width=canvas_width,
            height=canvas_height,
            description='Full canvas'
        )
        
        logger.info(f"SliceManager initialized ({canvas_width}x{canvas_height})")
    
    def add_slice(self, slice_id: str, x: int, y: int, width: int, height: int,
                  rotation: float = 0, shape: str = 'rectangle',
                  soft_edge: Optional[int] = None, mask: Optional[np.ndarray] = None,
                  description: str = '', points: Optional[List[Tuple[int, int]]] = None):
        """
        Add or update a slice definition
        
        Args:
            slice_id: Unique identifier
            x, y: Top-left corner position
            width, height: Slice dimensions
            rotation: Rotation in degrees
            shape: 'rectangle', 'polygon', or 'circle'
            soft_edge: Soft edge blur radius (pixels)
            mask: Custom mask (numpy array)
            description: Human-readable description
            points: Polygon points (for polygon shape)
        """
        slice_def = SliceDefinition(
            slice_id=slice_id,
            x=x, y=y,
            width=width, height=height,
            rotation=rotation,
            shape=shape,
            soft_edge=soft_edge,
            mask=mask,
            description=description,
            points=points
        )
        
        self.slices[slice_id] = slice_def
        logger.debug(f"Slice '{slice_id}' added/updated: {width}x{height} at ({x},{y})")
    
    def remove_slice(self, slice_id: str) -> bool:
        """
        Remove a slice definition
        
        Args:
            slice_id: Slice to remove
            
        Returns:
            bool: True if removed
        """
        if slice_id == 'full':
            logger.warning("Cannot remove 'full' slice")
            return False
        
        if slice_id in self.slices:
            del self.slices[slice_id]
            logger.debug(f"Slice '{slice_id}' removed")
            return True
        
        return False
    
    def get_slice(self, slice_id: str, frame: np.ndarray) -> np.ndarray:
        """
        Extract slice from frame
        
        Args:
            slice_id: Slice to extract
            frame: Source frame (numpy array, BGR)
            
        Returns:
            np.ndarray: Extracted and processed slice
        """
        if slice_id not in self.slices:
            logger.warning(f"Slice '{slice_id}' not found, returning full frame")
            return frame
        
        slice_def = self.slices[slice_id]
        
        # Extract based on shape
        if slice_def.shape == 'rectangle':
            sliced = self._extract_rectangle(frame, slice_def)
        elif slice_def.shape == 'polygon':
            sliced = self._extract_polygon(frame, slice_def)
        elif slice_def.shape == 'circle':
            sliced = self._extract_circle(frame, slice_def)
        else:
            logger.warning(f"Unknown shape '{slice_def.shape}', using rectangle")
            sliced = self._extract_rectangle(frame, slice_def)
        
        # Apply rotation if needed
        if slice_def.rotation != 0:
            sliced = self._apply_rotation(sliced, slice_def.rotation)
        
        # Apply soft edge if configured
        if slice_def.soft_edge:
            sliced = self._apply_soft_edge(sliced, slice_def.soft_edge)
        
        # Apply custom mask if provided
        if slice_def.mask is not None:
            sliced = self._apply_mask(sliced, slice_def.mask)
        
        return sliced
    
    def _extract_rectangle(self, frame: np.ndarray, slice_def: SliceDefinition) -> np.ndarray:
        """Extract rectangular region from frame"""
        h, w = frame.shape[:2]
        
        # Clamp coordinates to frame bounds
        x1 = max(0, min(slice_def.x, w))
        y1 = max(0, min(slice_def.y, h))
        x2 = max(0, min(slice_def.x + slice_def.width, w))
        y2 = max(0, min(slice_def.y + slice_def.height, h))
        
        # Extract region
        sliced = frame[y1:y2, x1:x2].copy()
        
        # Resize to target dimensions if needed
        if sliced.shape[1] != slice_def.width or sliced.shape[0] != slice_def.height:
            sliced = cv2.resize(sliced, (slice_def.width, slice_def.height))
        
        return sliced
    
    def _extract_polygon(self, frame: np.ndarray, slice_def: SliceDefinition) -> np.ndarray:
        """Extract polygonal region with mask"""
        if not slice_def.points or len(slice_def.points) < 3:
            logger.warning(f"Polygon slice '{slice_def.slice_id}' has insufficient points")
            return self._extract_rectangle(frame, slice_def)
        
        h, w = frame.shape[:2]
        
        # Create mask
        mask = np.zeros((h, w), dtype=np.uint8)
        points = np.array(slice_def.points, dtype=np.int32)
        cv2.fillPoly(mask, [points], 255)
        
        # Apply mask
        masked = cv2.bitwise_and(frame, frame, mask=mask)
        
        # Extract bounding box
        x, y, w_box, h_box = cv2.boundingRect(points)
        cropped = masked[y:y+h_box, x:x+w_box].copy()
        
        # Resize to target dimensions
        if cropped.shape[1] != slice_def.width or cropped.shape[0] != slice_def.height:
            cropped = cv2.resize(cropped, (slice_def.width, slice_def.height))
        
        return cropped
    
    def _extract_circle(self, frame: np.ndarray, slice_def: SliceDefinition) -> np.ndarray:
        """Extract circular region with mask"""
        h, w = frame.shape[:2]
        
        # Calculate center and radius
        cx = slice_def.x + slice_def.width // 2
        cy = slice_def.y + slice_def.height // 2
        radius = min(slice_def.width, slice_def.height) // 2
        
        # Create circular mask
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), radius, 255, -1)
        
        # Apply mask
        masked = cv2.bitwise_and(frame, frame, mask=mask)
        
        # Extract bounding box
        x1 = max(0, cx - radius)
        y1 = max(0, cy - radius)
        x2 = min(w, cx + radius)
        y2 = min(h, cy + radius)
        cropped = masked[y1:y2, x1:x2].copy()
        
        # Resize to target dimensions
        if cropped.shape[1] != slice_def.width or cropped.shape[0] != slice_def.height:
            cropped = cv2.resize(cropped, (slice_def.width, slice_def.height))
        
        return cropped
    
    def _apply_rotation(self, frame: np.ndarray, angle: float) -> np.ndarray:
        """Rotate frame by angle (degrees)"""
        if angle == 0:
            return frame
        
        h, w = frame.shape[:2]
        center = (w // 2, h // 2)
        
        # Get rotation matrix
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        
        # Calculate new dimensions
        cos = abs(matrix[0, 0])
        sin = abs(matrix[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        
        # Adjust rotation matrix for new dimensions
        matrix[0, 2] += (new_w / 2) - center[0]
        matrix[1, 2] += (new_h / 2) - center[1]
        
        # Rotate
        rotated = cv2.warpAffine(frame, matrix, (new_w, new_h))
        
        return rotated
    
    def _apply_soft_edge(self, frame: np.ndarray, blur_radius: int) -> np.ndarray:
        """Apply soft edge (fade to black at edges)"""
        h, w = frame.shape[:2]
        
        # Create gradient mask
        mask = np.ones((h, w), dtype=np.float32)
        
        # Apply gradient at edges
        for i in range(blur_radius):
            alpha = i / blur_radius
            mask[i, :] *= alpha  # Top
            mask[h-1-i, :] *= alpha  # Bottom
            mask[:, i] *= alpha  # Left
            mask[:, w-1-i] *= alpha  # Right
        
        # Apply mask to frame
        if frame.shape[2] == 3:  # BGR
            result = frame.astype(np.float32)
            for c in range(3):
                result[:, :, c] *= mask
            result = result.astype(np.uint8)
        else:
            result = (frame.astype(np.float32) * mask[:, :, np.newaxis]).astype(np.uint8)
        
        return result
    
    def _apply_mask(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Apply custom mask to frame"""
        # Resize mask if needed
        if mask.shape[:2] != frame.shape[:2]:
            mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]))
        
        # Convert to single channel if needed
        if len(mask.shape) == 3:
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        # Apply mask
        return cv2.bitwise_and(frame, frame, mask=mask)
    
    def get_slice_list(self) -> List[Dict]:
        """
        Get list of all slice definitions
        
        Returns:
            list: List of slice dictionaries
        """
        return [
            {
                'id': slice_def.slice_id,
                'x': slice_def.x,
                'y': slice_def.y,
                'width': slice_def.width,
                'height': slice_def.height,
                'rotation': slice_def.rotation,
                'shape': slice_def.shape,
                'soft_edge': slice_def.soft_edge,
                'description': slice_def.description,
                'has_mask': slice_def.mask is not None,
                'points': slice_def.points
            }
            for slice_def in self.slices.values()
        ]
    
    def get_state(self) -> dict:
        """Get all slice definitions for session persistence"""
        return {
            slice_id: {
                'x': slice_def.x,
                'y': slice_def.y,
                'width': slice_def.width,
                'height': slice_def.height,
                'rotation': slice_def.rotation,
                'shape': slice_def.shape,
                'soft_edge': slice_def.soft_edge,
                'description': slice_def.description,
                'points': slice_def.points
            }
            for slice_id, slice_def in self.slices.items()
        }
    
    def set_state(self, slices_dict: dict):
        """Restore slice definitions from session"""
        self.slices.clear()
        for slice_id, slice_data in slices_dict.items():
            self.add_slice(
                slice_id=slice_id,
                x=slice_data.get('x', 0),
                y=slice_data.get('y', 0),
                width=slice_data.get('width', self.canvas_width),
                height=slice_data.get('height', self.canvas_height),
                rotation=slice_data.get('rotation', 0),
                shape=slice_data.get('shape', 'rectangle'),
                soft_edge=slice_data.get('soft_edge'),
                description=slice_data.get('description', ''),
                points=slice_data.get('points')
            )
        logger.info(f"Restored {len(self.slices)} slices from session")
