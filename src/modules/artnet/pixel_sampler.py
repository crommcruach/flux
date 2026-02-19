"""
Pixel Sampler Module

Samples colors from video frames at specific coordinates.
Handles coordinate normalization and bounds checking.
"""

import numpy as np
from typing import List, Tuple
from .object import ArtNetObject, ArtNetPoint


class PixelSampler:
    """Sample pixel colors from video frames"""
    
    def __init__(self, canvas_width: int = 1920, canvas_height: int = 1080):
        """
        Initialize pixel sampler.
        
        Args:
            canvas_width: Canvas width in pixels (coordinate space)
            canvas_height: Canvas height in pixels (coordinate space)
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
    
    def sample_object(
        self, 
        obj: ArtNetObject, 
        frame: np.ndarray
    ) -> np.ndarray:
        """
        Sample pixel colors for all points in an object.
        
        Args:
            obj: ArtNet object with point coordinates
            frame: Video frame as numpy array (H, W, 3) RGB uint8
        
        Returns:
            RGB colors as numpy array (N, 3) uint8 where N = number of points
        """
        if len(obj.points) == 0:
            return np.array([], dtype=np.uint8).reshape(0, 3)
        
        frame_height, frame_width = frame.shape[:2]
        
        # Normalize coordinates from canvas space to frame space
        colors = []
        for point in obj.points:
            # Convert canvas coordinates to frame coordinates
            x = int((point.x / self.canvas_width) * frame_width)
            y = int((point.y / self.canvas_height) * frame_height)
            
            # Clamp to frame bounds
            x = max(0, min(x, frame_width - 1))
            y = max(0, min(y, frame_height - 1))
            
            # Sample pixel (frame is RGB)
            color = frame[y, x]
            colors.append(color)
        
        return np.array(colors, dtype=np.uint8)
    
    def sample_points(
        self, 
        points: List[ArtNetPoint], 
        frame: np.ndarray
    ) -> np.ndarray:
        """
        Sample pixel colors for a list of points.
        
        Args:
            points: List of ArtNetPoint coordinates
            frame: Video frame as numpy array (H, W, 3) RGB uint8
        
        Returns:
            RGB colors as numpy array (N, 3) uint8
        """
        if len(points) == 0:
            return np.array([], dtype=np.uint8).reshape(0, 3)
        
        frame_height, frame_width = frame.shape[:2]
        
        # Vectorized coordinate conversion
        xs = np.array([p.x for p in points])
        ys = np.array([p.y for p in points])
        
        # Normalize and convert to frame coordinates
        xs = ((xs / self.canvas_width) * frame_width).astype(int)
        ys = ((ys / self.canvas_height) * frame_height).astype(int)
        
        # Clamp to bounds
        xs = np.clip(xs, 0, frame_width - 1)
        ys = np.clip(ys, 0, frame_height - 1)
        
        # Sample all pixels at once
        colors = frame[ys, xs]
        
        return colors
    
    def update_canvas_size(self, width: int, height: int):
        """
        Update canvas dimensions.
        
        Args:
            width: New canvas width
            height: New canvas height
        """
        self.canvas_width = width
        self.canvas_height = height
    
    @staticmethod
    def sample_at_coordinates(
        frame: np.ndarray, 
        coordinates: List[Tuple[float, float]],
        canvas_width: int = 1920,
        canvas_height: int = 1080
    ) -> np.ndarray:
        """
        Static method to sample pixels at specific coordinates.
        
        Args:
            frame: Video frame (H, W, 3) RGB uint8
            coordinates: List of (x, y) tuples in canvas space
            canvas_width: Canvas width for normalization
            canvas_height: Canvas height for normalization
        
        Returns:
            RGB colors as numpy array (N, 3) uint8
        """
        if len(coordinates) == 0:
            return np.array([], dtype=np.uint8).reshape(0, 3)
        
        frame_height, frame_width = frame.shape[:2]
        
        # Extract and normalize coordinates
        coords = np.array(coordinates, dtype=np.float32)
        xs = ((coords[:, 0] / canvas_width) * frame_width).astype(int)
        ys = ((coords[:, 1] / canvas_height) * frame_height).astype(int)
        
        # Clamp
        xs = np.clip(xs, 0, frame_width - 1)
        ys = np.clip(ys, 0, frame_height - 1)
        
        # Sample
        return frame[ys, xs]
