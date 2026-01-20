"""
Display output plugin - OpenCV window output for video
Supports multi-monitor, fullscreen, and windowed modes
"""

import logging
import cv2
import numpy as np
from typing import Optional

from ..output_base import OutputBase
from ..monitor_utils import get_monitor_by_index

logger = logging.getLogger(__name__)


class DisplayOutput(OutputBase):
    """
    Display output using OpenCV windows
    
    Features:
    - Multi-monitor support
    - Fullscreen and windowed modes
    - Window positioning
    - Resolution scaling
    - Keyboard shortcuts (ESC to close, F to toggle fullscreen)
    """
    
    def __init__(self, output_id: str, config: dict):
        """
        Initialize display output
        
        Args:
            output_id: Unique identifier
            config: Configuration dict with keys:
                    - monitor_index: Which monitor to use (0-based)
                    - fullscreen: True for fullscreen mode
                    - resolution: [width, height] for window
                    - window_title: Window title string
        """
        super().__init__(output_id, config)
        
        self.monitor_index = config.get('monitor_index', 0)
        self.fullscreen = config.get('fullscreen', True)
        self.resolution = config.get('resolution', [1920, 1080])
        self.window_title = config.get('window_title', f'Flux Output - {output_id}')
        
        self.window_created = False
        self.window_name = f'flux_output_{output_id}'
        
        logger.debug(f"[{self.output_id}] DisplayOutput initialized (monitor: {self.monitor_index})")
    
    def initialize(self) -> bool:
        """Create and position display window"""
        try:
            # Get monitor information
            monitor = get_monitor_by_index(self.monitor_index)
            
            # Create named window
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            
            if self.fullscreen:
                # Fullscreen mode
                cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                
                # Position window on correct monitor
                cv2.moveWindow(self.window_name, monitor['x'], monitor['y'])
                
                # Resize to monitor resolution
                cv2.resizeWindow(self.window_name, monitor['width'], monitor['height'])
                
                logger.info(f"✅ [{self.output_id}] Display created (fullscreen on monitor {self.monitor_index}: {monitor['width']}x{monitor['height']})")
            
            else:
                # Windowed mode
                cv2.resizeWindow(self.window_name, self.resolution[0], self.resolution[1])
                
                # Center on monitor
                x = monitor['x'] + (monitor['width'] - self.resolution[0]) // 2
                y = monitor['y'] + (monitor['height'] - self.resolution[1]) // 2
                cv2.moveWindow(self.window_name, x, y)
                
                logger.info(f"✅ [{self.output_id}] Display created (windowed {self.resolution[0]}x{self.resolution[1]} on monitor {self.monitor_index})")
            
            # Set window title
            cv2.setWindowTitle(self.window_name, self.window_title)
            
            self.window_created = True
            return True
        
        except Exception as e:
            logger.error(f"[{self.output_id}] Failed to create display: {e}")
            return False
    
    def send_frame(self, frame: np.ndarray) -> bool:
        """Display frame in window"""
        if not self.window_created:
            return False
        
        try:
            # Resize frame if needed
            if self.fullscreen:
                monitor = get_monitor_by_index(self.monitor_index)
                target_size = (monitor['width'], monitor['height'])
            else:
                target_size = tuple(self.resolution)
            
            if frame.shape[1] != target_size[0] or frame.shape[0] != target_size[1]:
                frame = cv2.resize(frame, target_size)
            
            # Display frame
            cv2.imshow(self.window_name, frame)
            
            # Process keyboard events (1ms wait)
            key = cv2.waitKey(1) & 0xFF
            
            # ESC key - close window
            if key == 27:  # ESC
                logger.info(f"[{self.output_id}] ESC pressed - closing display")
                self.disable()
                return False
            
            # F key - toggle fullscreen
            elif key == ord('f') or key == ord('F'):
                self.fullscreen = not self.fullscreen
                logger.info(f"[{self.output_id}] Toggled fullscreen: {self.fullscreen}")
                
                # Reinitialize window with new mode
                self.cleanup()
                self.initialize()
            
            return True
        
        except Exception as e:
            logger.error(f"[{self.output_id}] Display error: {e}")
            return False
    
    def cleanup(self):
        """Destroy window"""
        if self.window_created:
            try:
                cv2.destroyWindow(self.window_name)
                self.window_created = False
                logger.info(f"[{self.output_id}] Display window closed")
            except Exception as e:
                logger.error(f"[{self.output_id}] Cleanup error: {e}")
