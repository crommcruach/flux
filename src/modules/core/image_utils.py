"""
Image Processing Utilities
Helper functions for frame manipulation, slicing, and masking.
"""
import cv2
import numpy as np
from .logger import get_logger

logger = get_logger(__name__)


def apply_mask_to_frame(frame, mask_config, slice_x=0, slice_y=0):
    """
    Apply a mask to frame (make masked region black)
    
    Args:
        frame: Input frame (extracted slice)
        mask_config: Mask definition with shape, position, etc. (in canvas coordinates)
        slice_x: X position of the slice on canvas (for coordinate translation)
        slice_y: Y position of the slice on canvas (for coordinate translation)
    
    Returns:
        np.ndarray: Frame with mask applied
    """
    try:
        h, w = frame.shape[:2]
        mask_shape = mask_config.get('shape', 'circle')
        
        # Create mask image (white = keep, black = remove)
        mask = np.ones((h, w), dtype=np.uint8) * 255
        
        if mask_shape == 'rectangle':
            # Translate mask coordinates from canvas to slice-relative coordinates
            x = int(mask_config.get('x', 0)) - slice_x
            y = int(mask_config.get('y', 0)) - slice_y
            mask_width = int(mask_config.get('width', w))
            mask_height = int(mask_config.get('height', h))
            
            # Only draw if mask intersects with slice
            if x < w and y < h and x + mask_width > 0 and y + mask_height > 0:
                cv2.rectangle(mask, (x, y), (x + mask_width, y + mask_height), 0, -1)
            
        elif mask_shape == 'circle':
            # Translate mask coordinates from canvas to slice-relative coordinates
            centerX = int(mask_config.get('centerX', w // 2)) - slice_x
            centerY = int(mask_config.get('centerY', h // 2)) - slice_y
            radius = int(mask_config.get('radius', min(w, h) // 4))
            
            # Only draw if circle intersects with slice
            if (centerX + radius > 0 and centerX - radius < w and 
                centerY + radius > 0 and centerY - radius < h):
                cv2.circle(mask, (centerX, centerY), radius, 0, -1)
            
        elif mask_shape in ['polygon', 'triangle', 'freehand']:
            points = mask_config.get('points', [])
            if points and len(points) >= 3:
                # Translate all points from canvas to slice-relative coordinates
                pts = np.array([
                    [int(p.get('x', 0)) - slice_x, int(p.get('y', 0)) - slice_y] 
                    for p in points
                ], dtype=np.int32)
                cv2.fillPoly(mask, [pts], 0)
        
        # Apply mask
        frame_masked = cv2.bitwise_and(frame, frame, mask=mask)
        return frame_masked
        
    except Exception as e:
        logger.error(f"Failed to apply mask: {e}")
        return frame


def apply_inline_slice(frame, slice_config):
    """
    Helper function to apply inline slice definition to frame
    
    Args:
        frame: Source frame (numpy array, BGR)
        slice_config: Dict with slice parameters
        
    Returns:
        np.ndarray: Sliced frame
    """
    try:
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
        
        # Normal rectangular extraction
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
                    # Masks from preview are already in slice-relative coordinates
                    # (frontend converts them before sending), so pass 0,0
                    sliced = apply_mask_to_frame(sliced, mask, slice_x=0, slice_y=0)
        
        # Apply color adjustments (brightness, contrast, RGB)
        brightness = slice_config.get('brightness', 0)
        contrast = slice_config.get('contrast', 0)
        red = slice_config.get('red', 0)
        green = slice_config.get('green', 0)
        blue = slice_config.get('blue', 0)
        
        if brightness != 0 or contrast != 0 or red != 0 or green != 0 or blue != 0:
            sliced = sliced.astype(np.float32)
            
            # Apply contrast first (multiplicative)
            if contrast != 0:
                factor = (100 + contrast) / 100.0
                sliced = (sliced - 127.5) * factor + 127.5
            
            # Apply brightness (additive)
            if brightness != 0:
                sliced = sliced + brightness
            
            # Apply RGB channel adjustments
            if blue != 0:
                sliced[:, :, 0] = sliced[:, :, 0] + blue  # B channel
            if green != 0:
                sliced[:, :, 1] = sliced[:, :, 1] + green  # G channel
            if red != 0:
                sliced[:, :, 2] = sliced[:, :, 2] + red  # R channel
            
            # Clip to valid range and convert back to uint8
            sliced = np.clip(sliced, 0, 255).astype(np.uint8)
        
        # Apply mirror/flip
        mirror = slice_config.get('mirror', 'none')
        if mirror == 'horizontal':
            sliced = cv2.flip(sliced, 1)
        elif mirror == 'vertical':
            sliced = cv2.flip(sliced, 0)
        elif mirror == 'both':
            sliced = cv2.flip(sliced, -1)
        
        return sliced
        
    except Exception as e:
        # Return original frame on error
        logger.error(f"Failed to apply inline slice: {e}")
        return frame
