"""
Recording Manager - Handles frame recording and playback
"""
import os
import json
from datetime import datetime
from collections import deque
from ...core.logger import get_logger

logger = get_logger(__name__)


class RecordingManager:
    """Manages frame recording and saving to JSON files."""
    
    def __init__(self, max_frames=36000):
        """
        Initialize RecordingManager.
        
        Args:
            max_frames: Maximum frames to record (default: 36000 = ~20min @ 30fps)
        """
        self.is_recording = False
        self.recorded_data = deque(maxlen=max_frames)
        self.recording_name = None
        
    def start_recording(self, name=None):
        """
        Start recording frames.
        
        Args:
            name: Optional recording name
            
        Returns:
            bool: True if recording started, False if already recording
        """
        if self.is_recording:
            logger.warning("Recording already active!")
            return False
            
        self.is_recording = True
        self.recorded_data.clear()
        self.recording_name = name or "Unnamed"
        logger.info(f"Recording started: {self.recording_name}")
        return True
    
    def stop_recording(self, canvas_width=None, canvas_height=None, total_points=None):
        """
        Stop recording and save to file.
        
        Args:
            canvas_width: Canvas width for metadata
            canvas_height: Canvas height for metadata
            total_points: Total points for metadata
            
        Returns:
            str: Filename if saved successfully, None otherwise
        """
        if not self.is_recording:
            logger.debug("No recording active!")
            return None
        
        self.is_recording = False
        frame_count = len(self.recorded_data)
        
        if frame_count == 0:
            logger.debug("No frames recorded")
            return None
        
        # Create records directory if not exists
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        records_dir = os.path.join(base_path, 'records')
        os.makedirs(records_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in (self.recording_name or "recording") 
                           if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{safe_name}_{timestamp}.json"
        filepath = os.path.join(records_dir, filename)
        
        # Build recording data
        recording_data = {
            'name': self.recording_name or "Unnamed Recording",
            'timestamp': timestamp,
            'frame_count': frame_count,
            'total_duration': self.recorded_data[-1]['timestamp'] if self.recorded_data else 0,
            'canvas_width': canvas_width,
            'canvas_height': canvas_height,
            'total_points': total_points,
            'frames': list(self.recorded_data)
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(recording_data, f)
            logger.info(f"✅ Recording saved: {filename} ({frame_count} frames)")
            return filename
        except Exception as e:
            logger.error(f"❌ Error saving recording: {e}")
            return None
    
    def add_frame(self, frame_data):
        """
        Add frame to recording.
        
        Args:
            frame_data: Frame data dict with timestamp and data
        """
        if self.is_recording:
            self.recorded_data.append(frame_data)
    
    def clear(self):
        """Clear recorded data."""
        self.recorded_data.clear()
        self.recording_name = None
        self.is_recording = False
