"""
Display output plugin - OpenCV window output for video
Uses multiprocessing for Windows compatibility (GUI must run in own process)
Supports multi-monitor, fullscreen, and windowed modes
"""

import logging
import cv2
import numpy as np
from typing import Optional
import multiprocessing as mp
from multiprocessing import Process, Queue, Event
import time

from ..base import OutputBase
from ..monitor_utils import get_monitor_by_index, get_available_monitors

logger = logging.getLogger(__name__)


def _display_process_loop(output_id: str, window_name: str, window_title: str,
                          monitor_index: int, fullscreen: bool, resolution: tuple,
                          frame_queue: Queue, stop_event: Event):
    """
    Display process - runs cv2 window in isolated process
    This MUST run in a separate process on Windows for proper GUI handling
    
    Args:
        output_id: Output identifier for logging
        window_name: OpenCV window name
        window_title: Window title text
        monitor_index: Monitor index
        fullscreen: Fullscreen mode flag
        resolution: (width, height) for windowed mode
        frame_queue: Queue to receive frames from main process
        stop_event: Event to signal process shutdown
    """
    window_created = False
    
    try:
        # Check monitor count - if only 1 monitor, force windowed mode
        available_monitors = get_available_monitors()
        monitor_count = len(available_monitors)
        use_fullscreen = fullscreen
        
        if monitor_count == 1 and fullscreen:
            use_fullscreen = False
            logger.info(f"[{output_id}] Only 1 monitor detected - using windowed mode")
        
        # Get monitor information
        monitor = get_monitor_by_index(monitor_index)
        
        # Create window
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        if use_fullscreen:
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            cv2.moveWindow(window_name, monitor['x'], monitor['y'])
            cv2.resizeWindow(window_name, monitor['width'], monitor['height'])
            logger.info(f"✅ [{output_id}] Display process started (fullscreen {monitor['width']}x{monitor['height']})")
        else:
            cv2.resizeWindow(window_name, resolution[0], resolution[1])
            x = monitor['x'] + (monitor['width'] - resolution[0]) // 2
            y = monitor['y'] + (monitor['height'] - resolution[1]) // 2
            cv2.moveWindow(window_name, x, y)
            logger.info(f"✅ [{output_id}] Display process started (windowed {resolution[0]}x{resolution[1]})")
        
        cv2.setWindowTitle(window_name, window_title)
        window_created = True
        
        frame_count = 0
        last_log_time = time.time()
        
        # Display loop
        while not stop_event.is_set():
            try:
                # Get frame from queue (non-blocking with timeout)
                try:
                    frame = frame_queue.get(timeout=0.05)
                    
                    # Resize if needed
                    if use_fullscreen:
                        target_size = (monitor['width'], monitor['height'])
                    else:
                        target_size = resolution
                    
                    if frame.shape[1] != target_size[0] or frame.shape[0] != target_size[1]:
                        frame = cv2.resize(frame, target_size)
                    
                    # Display frame
                    cv2.imshow(window_name, frame)
                    frame_count += 1
                    
                except:
                    # No frame available, that's OK
                    pass
                
                # Process window events (CRITICAL for responsiveness)
                key = cv2.waitKey(1) & 0xFF
                
                # ESC key - signal shutdown
                if key == 27:
                    logger.info(f"[{output_id}] ESC pressed in display process")
                    stop_event.set()
                    break
                
                # Log stats every 5 seconds
                if time.time() - last_log_time > 5.0:
                    logger.debug(f"[{output_id}] Display process: {frame_count} frames processed")
                    last_log_time = time.time()
                    
            except Exception as e:
                logger.error(f"[{output_id}] Display loop error: {e}")
                time.sleep(0.1)
        
        logger.info(f"[{output_id}] Display process shutting down ({frame_count} frames total)")
        
    except Exception as e:
        logger.error(f"[{output_id}] Display process error: {e}", exc_info=True)
    
    finally:
        if window_created:
            try:
                cv2.destroyWindow(window_name)
            except:
                pass


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
        """Start display process"""
        try:
            # Create IPC objects
            self.process_frame_queue = Queue(maxsize=2)  # Small queue to avoid lag
            self.process_stop_event = Event()
            
            # Start display process
            self.display_process = Process(
                target=_display_process_loop,
                args=(
                    self.output_id,
                    self.window_name,
                    self.window_title,
                    self.monitor_index,
                    self.fullscreen,
                    tuple(self.resolution),
                    self.process_frame_queue,
                    self.process_stop_event
                ),
                daemon=False  # Non-daemon so we can clean shutdown
            )
            self.display_process.start()
            
            # Wait a moment for process to initialize
            time.sleep(0.1)
            
            if self.display_process.is_alive():
                self.window_created = True  # Mark window as ready
                logger.info(f"✅ [{self.output_id}] Display process started (PID: {self.display_process.pid})")
                return True
            else:
                logger.error(f"❌ [{self.output_id}] Display process failed to start")
                self.window_created = False
                return False
                
        except Exception as e:
            logger.error(f"[{self.output_id}] Failed to start display process: {e}", exc_info=True)
            self.window_created = False
            return False
    
    def process_window_events(self) -> bool:
        """
        Process window events - now handled in separate process
        This is a no-op for compatibility with OutputBase
        
        Returns:
            bool: Always True (process handles window events)
        """
        return True
    
    def send_frame(self, frame: np.ndarray) -> bool:
        """Send frame to display process via queue"""
        if not self.window_created:
            logger.debug(f"[{self.output_id}] send_frame: window not created")
            return False
        
        if not hasattr(self, 'display_process'):
            logger.error(f"[{self.output_id}] send_frame: display_process attribute missing")
            return False
            
        if not self.display_process.is_alive():
            logger.warning(f"[{self.output_id}] send_frame: display process not alive")
            return False
        
        try:
            # Make a copy of the frame (separate process memory space)
            frame_copy = frame.copy()
            
            # Put frame in queue (non-blocking)
            # If queue is full, we drop the frame (display can't keep up)
            try:
                self.process_frame_queue.put_nowait(frame_copy)
                return True
            except Exception:
                # Queue full - drop frame silently (normal under high load)
                return True
        
        except Exception as e:
            logger.error(f"[{self.output_id}] Frame send error: {e}", exc_info=True)
            return False
    
    def cleanup(self):
        """Shutdown display process gracefully"""
        if self.window_created and hasattr(self, 'display_process'):
            try:
                # Signal process to stop
                self.process_stop_event.set()
                logger.info(f"[{self.output_id}] Stopping display process...")
                
                # Wait for clean exit (max 2 seconds)
                self.display_process.join(timeout=2)
                
                # Force terminate if still alive
                if self.display_process.is_alive():
                    logger.warning(f"[{self.output_id}] Process did not exit cleanly, terminating...")
                    self.display_process.terminate()
                    self.display_process.join(timeout=1)
                
                self.window_created = False
                logger.info(f"[{self.output_id}] Display process stopped")
                
            except Exception as e:
                logger.error(f"[{self.output_id}] Cleanup error: {e}", exc_info=True)