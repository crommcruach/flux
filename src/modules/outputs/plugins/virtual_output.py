"""
Virtual output plugin - NULL output for testing/preview
Stores frames in memory without displaying, useful for preview API and testing
"""

import logging
import numpy as np
import threading
from typing import Optional

from ..output_base import OutputBase

logger = logging.getLogger(__name__)


class VirtualOutput(OutputBase):
    """
    Virtual output - stores frames in memory without displaying
    
    Features:
    - No display/window creation
    - Frames stored for preview API access
    - Custom resolution support
    - Full slice and source routing support
    - Zero CPU overhead (no rendering)
    - Useful for testing, preview, and multi-output workflows
    """
    
    def __init__(self, output_id: str, config: dict):
        """
        Initialize virtual output
        
        Args:
            output_id: Unique identifier (e.g., 'virtual_1')
            config: Configuration dict with keys:
                    - resolution: [width, height] for virtual output
                    - name: Optional display name
        """
        super().__init__(output_id, config)
        
        self.resolution = config.get('resolution', [1920, 1080])
        self.name = config.get('name', f'Virtual Output {output_id}')
        
        # Store latest frame for preview
        self.latest_frame: Optional[np.ndarray] = None
        self.frame_lock = threading.Lock()
        
        logger.debug(f"[{self.output_id}] VirtualOutput initialized ({self.resolution[0]}x{self.resolution[1]})")
    
    def initialize(self) -> bool:
        """Initialize virtual output (no-op, always succeeds)"""
        logger.info(f"✅ [{self.output_id}] Virtual output initialized: {self.name} ({self.resolution[0]}x{self.resolution[1]})")
        return True
    
    def send_frame(self, frame: np.ndarray) -> bool:
        """
        Store frame in memory for preview access
        
        Args:
            frame: Frame to store (numpy array, BGR format)
            
        Returns:
            bool: Always True (virtual output never fails)
        """
        try:
            # Resize frame to target resolution if needed
            if frame.shape[1] != self.resolution[0] or frame.shape[0] != self.resolution[1]:
                import cv2
                frame = cv2.resize(frame, tuple(self.resolution))
            
            # Store frame (thread-safe)
            with self.frame_lock:
                self.latest_frame = frame.copy()
            
            return True
        
        except Exception as e:
            logger.error(f"[{self.output_id}] Virtual output error: {e}")
            return False
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get latest stored frame (thread-safe)
        
        Returns:
            np.ndarray or None: Latest frame or None if no frame yet
        """
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
    
    def cleanup(self):
        """Cleanup virtual output (clear stored frame)"""
        with self.frame_lock:
            self.latest_frame = None
        logger.info(f"[{self.output_id}] Virtual output cleaned up")
    
    def get_info(self) -> dict:
        """
        Get virtual output information
        
        Returns:
            dict: Output info including resolution and frame availability
        """
        with self.frame_lock:
            has_frame = self.latest_frame is not None
        
        return {
            'output_id': self.output_id,
            'type': 'virtual',
            'name': self.name,
            'resolution': self.resolution,
            'enabled': self.enabled,
            'has_frame': has_frame,
            'frames_sent': self.frames_sent,
            'frames_dropped': self.frames_dropped
        }
