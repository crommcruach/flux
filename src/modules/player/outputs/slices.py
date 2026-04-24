"""
Slice manager - handles slice definitions and frame extraction
Supports rectangles, polygons, circles with masks, soft edges, and rotation
"""

import logging
import cv2
import numpy as np
from typing import Dict, Optional, List, Tuple, Union
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
    soft_edge: Optional[Union[int, Dict]] = None  # Soft edge config (int for legacy, dict for full control)
    mask: Optional[np.ndarray] = None  # Custom mask (compiled numpy array)
    masks: Optional[List[Dict]] = None  # Raw mask geometries for UI editing
    description: str = ''
    points: Optional[List[Tuple[int, int]]] = None  # For polygon shape
    brightness: int = 0  # Brightness adjustment (-255 to 255)
    contrast: int = 0  # Contrast adjustment (-100 to 100)
    red: int = 0  # Red channel adjustment (-255 to 255)
    green: int = 0  # Green channel adjustment (-255 to 255)
    blue: int = 0  # Blue channel adjustment (-255 to 255)
    mirror: str = 'none'  # Mirror mode: 'none', 'horizontal', 'vertical', 'both'
    transformCorners: Optional[List[Dict]] = None  # Transform corner positions for perspective transform


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
        self._logged_warnings = set()  # Track which warnings we've already logged
        
        # Add default "full" slice
        self.add_slice(
            slice_id='full',
            x=0, y=0,
            width=canvas_width,
            height=canvas_height,
            description='Full canvas'
        )
        
        logger.debug(f"SliceManager initialized ({canvas_width}x{canvas_height})")
    
    def add_slice(self, slice_id: str, x: int, y: int, width: int, height: int,
                  rotation: float = 0, shape: str = 'rectangle',
                  soft_edge: Optional[Union[int, Dict]] = None, mask: Optional[np.ndarray] = None,
                  masks: Optional[List[Dict]] = None,
                  description: str = '', points: Optional[List[Tuple[int, int]]] = None,
                  brightness: int = 0, contrast: int = 0,
                  red: int = 0, green: int = 0, blue: int = 0,
                  mirror: str = 'none', transformCorners: Optional[List[Dict]] = None):
        """
        Add or update a slice definition
        
        Args:
            slice_id: Unique identifier
            x, y: Top-left corner position
            width, height: Slice dimensions
            rotation: Rotation in degrees
            shape: 'rectangle', 'polygon', or 'circle'
            soft_edge: Soft edge blur radius (pixels)
            mask: Custom mask (numpy array, compiled)
            masks: Raw mask geometries for UI editing
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
            masks=masks,
            description=description,
            points=points,
            brightness=brightness,
            contrast=contrast,
            red=red,
            green=green,
            blue=blue,
            mirror=mirror,
            transformCorners=transformCorners
        )
        
        self.slices[slice_id] = slice_def
        # Clear warning flag when slice is added (in case it was previously missing)
        self._logged_warnings.discard(slice_id)
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
            # Only log warning once per missing slice_id to avoid spam
            if slice_id not in self._logged_warnings:
                logger.warning(f"Slice '{slice_id}' not found, returning full frame")
                self._logged_warnings.add(slice_id)
            return frame
        
        slice_def = self.slices[slice_id]

        # Perspective transform takes precedence over normal shape extraction
        # when corners have been moved from their default rectangular positions.
        if (slice_def.transformCorners
                and len(slice_def.transformCorners) == 4
                and self._is_transformed(slice_def)):
            sliced = self._apply_perspective_transform(frame, slice_def)
        else:
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

            # Apply rotation (only when not using perspective transform — warpPerspective
            # already encodes the desired geometry).
            if slice_def.rotation != 0:
                sliced = self._apply_rotation(sliced, slice_def.rotation)
        
        # Apply soft edge if configured
        if slice_def.soft_edge:
            sliced = self._apply_soft_edge(sliced, slice_def.soft_edge)
        
        # Apply custom mask if provided
        if slice_def.mask is not None:
            logger.debug(f"🎭 Applying mask to slice '{slice_id}': mask shape={slice_def.mask.shape}, slice shape={sliced.shape[:2]}")
            sliced = self._apply_mask(sliced, slice_def.mask)
            logger.debug(f"✅ Mask applied to slice '{slice_id}'")
        else:
            logger.debug(f"No mask to apply for slice '{slice_id}'")
        
        # Apply color adjustments (brightness, contrast, RGB)
        if slice_def.brightness != 0 or slice_def.contrast != 0 or slice_def.red != 0 or slice_def.green != 0 or slice_def.blue != 0:
            sliced = self._apply_color_adjustments(sliced, slice_def)
        
        # Apply mirror/flip
        if slice_def.mirror != 'none':
            sliced = self._apply_mirror(sliced, slice_def.mirror)
        
        return sliced
    
    # ------------------------------------------------------------------
    # Perspective / transform helpers
    # ------------------------------------------------------------------

    def _is_transformed(self, slice_def: 'SliceDefinition') -> bool:
        """Return True when transformCorners deviate from the default rectangle."""
        corners = slice_def.transformCorners
        defaults = [
            (0, 0),
            (slice_def.width, 0),
            (slice_def.width, slice_def.height),
            (0, slice_def.height),
        ]
        for i, c in enumerate(corners):
            if abs(c.get('x', 0) - defaults[i][0]) > 1 or abs(c.get('y', 0) - defaults[i][1]) > 1:
                return True
        return False

    def _apply_perspective_transform(self, frame: np.ndarray, slice_def: 'SliceDefinition') -> np.ndarray:
        """Warp a quadrilateral region of *frame* into a width×height rectangle.

        transformCorners stores corner offsets RELATIVE to the slice origin
        (slice_def.x, slice_def.y).  Converting to absolute canvas coords:
            abs_x = slice_def.x + corner['x']
            abs_y = slice_def.y + corner['y']

        Corner order expected by the frontend: TL, TR, BR, BL.
        """
        try:
            src = np.float32([
                [slice_def.x + c.get('x', 0), slice_def.y + c.get('y', 0)]
                for c in slice_def.transformCorners
            ])
            dst = np.float32([
                [0, 0],
                [slice_def.width, 0],
                [slice_def.width, slice_def.height],
                [0, slice_def.height],
            ])
            M = cv2.getPerspectiveTransform(src, dst)
            return cv2.warpPerspective(frame, M, (slice_def.width, slice_def.height))
        except Exception as exc:
            logger.error("Perspective transform failed for slice '%s': %s", slice_def.slice_id, exc)
            return self._extract_rectangle(frame, slice_def)

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
    
    def _apply_soft_edge(self, frame: np.ndarray, soft_edge_cfg) -> np.ndarray:
        """Apply soft edge fade to black.

        Accepts:
        - int/float  : legacy symmetric pixel-radius fade on all four edges
        - dict       : frontend format {enabled, width:{top,bottom,left,right}, curve}
        """
        if soft_edge_cfg is None:
            return frame

        h, w = frame.shape[:2]

        # ── dict format (frontend per-edge) ──────────────────────────────────
        if isinstance(soft_edge_cfg, dict):
            if not soft_edge_cfg.get('enabled'):
                return frame
            ew = soft_edge_cfg.get('width', {})
            top_px    = max(0, int(ew.get('top',    0)))
            bot_px    = max(0, int(ew.get('bottom', 0)))
            left_px   = max(0, int(ew.get('left',   0)))
            right_px  = max(0, int(ew.get('right',  0)))
            curve     = soft_edge_cfg.get('curve', 'smooth')

            if not any([top_px, bot_px, left_px, right_px]):
                return frame

            mask = np.ones((h, w), dtype=np.float32)

            # Build per-edge linear ramps, then apply curve.
            for i in range(h):
                t_top = min(i / top_px, 1.0)    if top_px    else 1.0
                t_bot = min((h-1-i) / bot_px, 1.0) if bot_px else 1.0
                row_alpha = min(t_top, t_bot)
                if row_alpha < 1.0:
                    mask[i, :] *= row_alpha

            for j in range(w):
                t_left  = min(j / left_px,  1.0)    if left_px  else 1.0
                t_right = min((w-1-j) / right_px, 1.0) if right_px else 1.0
                col_alpha = min(t_left, t_right)
                if col_alpha < 1.0:
                    mask[:, j] *= col_alpha

            # Apply curve
            if curve == 'smooth':
                mask = mask * mask * (3.0 - 2.0 * mask)
            elif curve == 'exponential':
                mask = mask * mask

            return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)

        # ── legacy int/float symmetric mode ──────────────────────────────────
        blur_radius = int(soft_edge_cfg)
        if blur_radius <= 0:
            return frame

        mask = np.ones((h, w), dtype=np.float32)
        for i in range(blur_radius):
            alpha = i / blur_radius
            mask[i, :]     *= alpha  # top
            mask[h-1-i, :] *= alpha  # bottom
            mask[:, i]     *= alpha  # left
            mask[:, w-1-i] *= alpha  # right

        return (frame.astype(np.float32) * mask[:, :, np.newaxis]).clip(0, 255).astype(np.uint8)
    
    def _apply_mask(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Apply custom mask to frame"""
        logger.debug(f"_apply_mask: frame shape={frame.shape}, mask shape={mask.shape}")
        
        # Resize mask if needed
        if mask.shape[:2] != frame.shape[:2]:
            logger.debug(f"Resizing mask from {mask.shape[:2]} to {frame.shape[:2]}")
            mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]))
        
        # Convert to single channel if needed
        if len(mask.shape) == 3:
            logger.debug("Converting mask to grayscale")
            mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
        
        # Count black pixels (masked regions)
        black_pixels = np.sum(mask == 0)
        total_pixels = mask.shape[0] * mask.shape[1]
        logger.debug(f"Mask has {black_pixels}/{total_pixels} black pixels ({black_pixels/total_pixels*100:.1f}%)")
        
        # Apply mask
        result = cv2.bitwise_and(frame, frame, mask=mask)
        logger.debug(f"✅ Mask applied via bitwise_and")
        return result
    
    def _apply_color_adjustments(self, frame: np.ndarray, slice_def: SliceDefinition) -> np.ndarray:
        """Apply brightness, contrast, and RGB adjustments"""
        result = frame.astype(np.float32)
        
        # Apply contrast first (multiplicative)
        if slice_def.contrast != 0:
            # Contrast formula: output = (input - 127.5) * factor + 127.5
            # factor = (100 + contrast) / 100, range roughly 0.0 to 2.0
            factor = (100 + slice_def.contrast) / 100.0
            result = (result - 127.5) * factor + 127.5
        
        # Apply brightness (additive)
        if slice_def.brightness != 0:
            result = result + slice_def.brightness
        
        # Apply RGB channel adjustments
        if slice_def.blue != 0:
            result[:, :, 0] = result[:, :, 0] + slice_def.blue  # B channel
        if slice_def.green != 0:
            result[:, :, 1] = result[:, :, 1] + slice_def.green  # G channel
        if slice_def.red != 0:
            result[:, :, 2] = result[:, :, 2] + slice_def.red  # R channel
        
        # Clip to valid range and convert back to uint8
        result = np.clip(result, 0, 255).astype(np.uint8)
        return result
    
    def _apply_mirror(self, frame: np.ndarray, mirror_mode: str) -> np.ndarray:
        """Apply mirror/flip transformation"""
        if mirror_mode == 'horizontal':
            return cv2.flip(frame, 1)  # Flip horizontally
        elif mirror_mode == 'vertical':
            return cv2.flip(frame, 0)  # Flip vertically
        elif mirror_mode == 'both':
            return cv2.flip(frame, -1)  # Flip both axes
        return frame
    
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
                'masks': slice_def.masks or [],
                'points': slice_def.points,
                'brightness': slice_def.brightness,
                'contrast': slice_def.contrast,
                'red': slice_def.red,
                'green': slice_def.green,
                'blue': slice_def.blue,
                'mirror': slice_def.mirror,
                'transformCorners': slice_def.transformCorners
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
                'masks': slice_def.masks or [],
                'points': slice_def.points,
                'brightness': slice_def.brightness,
                'contrast': slice_def.contrast,
                'red': slice_def.red,
                'green': slice_def.green,
                'blue': slice_def.blue,
                'mirror': slice_def.mirror,
                'transformCorners': slice_def.transformCorners
            }
            for slice_id, slice_def in self.slices.items()
        }
    
    def get_slice_gpu(self, slice_id: str, composite_gpu_frame,
                       canvas_w: int, canvas_h: int):
        """Apply the named slice as a single GPU render pass.

        Returns
        -------
        GPUFrame  : the same *composite_gpu_frame* for slice_id='full' (no-op),
                    or a cached GPUFrame owned by the internal GPUSliceRenderer
                    for any other slice — do NOT release it.
        None if the GPU renderer is unavailable.
        """
        if slice_id == 'full':
            return composite_gpu_frame

        if slice_id not in self.slices:
            if slice_id not in self._logged_warnings:
                logger.warning("[GPU] Slice '%s' not found; passing through full frame", slice_id)
                self._logged_warnings.add(slice_id)
            return composite_gpu_frame

        if not hasattr(self, '_gpu_renderer'):
            try:
                from ...gpu.slice_renderer import GPUSliceRenderer
                self._gpu_renderer = GPUSliceRenderer()
            except Exception as exc:
                logger.warning("GPUSliceRenderer unavailable: %s", exc)
                self._gpu_renderer = None

        if self._gpu_renderer is None:
            return composite_gpu_frame

        return self._gpu_renderer.slice(
            composite_gpu_frame, self.slices[slice_id], canvas_w, canvas_h
        )

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
                masks=slice_data.get('masks', []),
                description=slice_data.get('description', ''),
                points=slice_data.get('points'),
                brightness=slice_data.get('brightness', 0),
                contrast=slice_data.get('contrast', 0),
                red=slice_data.get('red', 0),
                green=slice_data.get('green', 0),
                blue=slice_data.get('blue', 0),
                mirror=slice_data.get('mirror', 'none'),
                transformCorners=slice_data.get('transformCorners')
            )
        logger.debug(f"Restored {len(self.slices)} slices from session")
