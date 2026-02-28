"""
Abstract base class for all output plugins
Provides common functionality for frame queueing, FPS throttling, and statistics
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from queue import Queue, Full
import numpy as np
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class OutputBase(ABC):
    """
    Abstract base class for all output plugins
    
    Features:
    - Thread-safe frame queue
    - FPS throttling
    - Enable/disable state
    - Statistics tracking (frames sent/dropped)
    """
    
    def __init__(self, output_id: str, config: dict):
        """
        Initialize output plugin
        
        Args:
            output_id: Unique identifier for this output
            config: Configuration dictionary
        """
        self.output_id = output_id
        self.config = config
        self.enabled = False
        
        # Statistics
        self.frames_sent = 0
        self.frames_dropped = 0
        self.last_frame_time = 0
        
        # FPS throttling
        self.target_fps = config.get('fps', 30)
        self.frame_interval = 1.0 / self.target_fps if self.target_fps > 0 else 0
        
        # Thread-safe frame queue
        self.frame_queue = Queue(maxsize=2)  # Small queue to avoid lag
        self.output_thread = None
        self.running = False
        
        # Thread lock for statistics
        self.stats_lock = threading.Lock()
        
        # Frame capture for streaming (optional per output)
        self.enable_capture = config.get('enable_capture', False)
        self.latest_frame: Optional[np.ndarray] = None
        self.frame_capture_lock = threading.Lock()
        
        logger.debug(f"[{self.output_id}] Output base initialized (FPS: {self.target_fps}, capture: {self.enable_capture})")
    
    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the output plugin (e.g., open window, create NDI sender)
        
        Returns:
            bool: True if initialization successful
        """
        pass
    
    @abstractmethod
    def send_frame(self, frame: np.ndarray) -> bool:
        """
        Send a single frame to the output
        
        Args:
            frame: Frame to send (numpy array, BGR format)
            
        Returns:
            bool: True if frame sent successfully
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """
        Cleanup resources (e.g., close window, destroy sender)
        """
        pass
    
    def enable(self) -> bool:
        """
        Enable output and start output thread
        
        Returns:
            bool: True if enabled successfully
        """
        if self.enabled:
            logger.warning(f"[{self.output_id}] Already enabled")
            return True
        
        logger.info(f"⚡ [{self.output_id}] Enabling output...")
        
        # Initialize plugin
        if not self.initialize():
            logger.error(f"❌ [{self.output_id}] Initialization failed - output NOT enabled")
            return False
        
        # Start output thread
        self.running = True
        self.output_thread = threading.Thread(target=self._output_loop, daemon=True)
        self.output_thread.start()
        
        self.enabled = True
        logger.info(f"✅ [{self.output_id}] Output enabled successfully")
        return True
    
    def disable(self):
        """Disable output and stop output thread"""
        if not self.enabled:
            return
        
        # Stop thread
        self.running = False
        if self.output_thread:
            self.output_thread.join(timeout=2.0)
            self.output_thread = None
        
        # Cleanup
        try:
            self.cleanup()
        except Exception as e:
            logger.error(f"[{self.output_id}] Cleanup error: {e}")
        
        self.enabled = False
        logger.debug(f"[{self.output_id}] Output disabled")
    
    def queue_frame(self, frame: np.ndarray):
        """
        Queue frame for output (thread-safe, non-blocking)
        
        Args:
            frame: Frame to queue
        """
        if not self.enabled:
            return
        
        try:
            # OPTIMIZATION: Only copy if output requires it (e.g., multiprocessing)
            # VirtualOutput overrides this to use direct reference
            # Default to True for safety (backwards compatibility)
            if getattr(self, 'needs_frame_copy', True):
                frame = frame.copy()
            
            # Non-blocking put (drop frame if queue full)
            self.frame_queue.put_nowait(frame)
        except Full:
            with self.stats_lock:
                self.frames_dropped += 1
    
    def _output_loop(self):
        """Output thread loop - processes frames from queue"""
        from queue import Empty
        logger.debug(f"[{self.output_id}] Output thread started")
        
        # Debug counter
        frame_count = 0
        
        while self.running:
            try:
                # Get frame from queue (blocking with timeout)
                frame = self.frame_queue.get(timeout=0.1)
                
                # Debug: Log first few frames
                frame_count += 1
                if frame_count <= 5:
                    logger.debug(f"[{self.output_id}] Received frame #{frame_count} from queue (shape: {frame.shape})")
                
                # Capture frame for streaming if enabled
                if self.enable_capture:
                    with self.frame_capture_lock:
                        self.latest_frame = frame.copy()
                
                # FPS throttling
                if self.frame_interval > 0:
                    elapsed = time.time() - self.last_frame_time
                    if elapsed < self.frame_interval:
                        time.sleep(self.frame_interval - elapsed)
                
                # Send frame
                if self.send_frame(frame):
                    with self.stats_lock:
                        self.frames_sent += 1
                        self.last_frame_time = time.time()
                    if frame_count <= 5:
                        logger.debug(f"[{self.output_id}] Frame #{frame_count} sent successfully")
                else:
                    with self.stats_lock:
                        self.frames_dropped += 1
                    if frame_count <= 5:
                        logger.warning(f"[{self.output_id}] Frame #{frame_count} send failed")
            
            except Empty:
                # Queue empty - process window events if this is a display output
                # This keeps cv2 windows responsive even when no frames are coming
                try:
                    if hasattr(self, 'process_window_events'):
                        self.process_window_events()
                except Exception as e:
                    logger.error(f"[{self.output_id}] Error processing window events: {e}", exc_info=True)
                continue
                
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"[{self.output_id}] Output loop error: {e}", exc_info=True)
                    time.sleep(0.1)
        
        logger.debug(f"[{self.output_id}] Output thread stopped")
    
    def get_statistics(self) -> Dict:
        """
        Get output statistics
        
        Returns:
            dict: Statistics (frames_sent, frames_dropped, etc.)
        """
        with self.stats_lock:
            return {
                'output_id': self.output_id,
                'enabled': self.enabled,
                'frames_sent': self.frames_sent,
                'frames_dropped': self.frames_dropped,
                'target_fps': self.target_fps,
                'type': self.config.get('type', 'unknown')
            }
    
    def reset_statistics(self):
        """Reset frame statistics"""
        with self.stats_lock:
            self.frames_sent = 0
            self.frames_dropped = 0
        logger.debug(f"[{self.output_id}] Statistics reset")
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get latest captured frame for streaming
        
        Returns:
            np.ndarray or None: Copy of latest frame, or None if capture disabled or no frame available
        """
        if not self.enable_capture:
            return None
        
        with self.frame_capture_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
