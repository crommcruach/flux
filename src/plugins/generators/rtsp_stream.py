"""
RTSP Stream Generator - Live video stream from RTSP sources (IP cameras, etc.)
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType

class RTSPStreamGenerator(PluginBase):
    """Generator that captures live video from RTSP streams."""
    
    METADATA = {
        'id': 'rtsp_stream',
        'name': 'RTSP Stream',
        'description': 'Live video stream from RTSP sources (IP cameras, RTSP servers)',
        'version': '1.0.0',
        'author': 'Flux',
        'type': PluginType.GENERATOR,
        'category': 'Live Sources'
    }
    
    PARAMETERS = [
        {
            'name': 'rtsp_url',
            'type': ParameterType.STRING,
            'default': 'rtsp://localhost:8554/stream',
            'label': 'RTSP URL',
            'description': 'Full RTSP URL (e.g., rtsp://192.168.1.100:554/stream1)'
        },
        {
            'name': 'reconnect_delay',
            'type': ParameterType.INT,
            'default': 5,
            'min': 1,
            'max': 60,
            'label': 'Reconnect Delay (s)',
            'description': 'Seconds to wait before reconnecting on connection loss'
        },
        {
            'name': 'buffer_size',
            'type': ParameterType.INT,
            'default': 1,
            'min': 1,
            'max': 10,
            'label': 'Buffer Size',
            'description': 'Number of frames to buffer (1 = lowest latency)'
        },
        {
            'name': 'timeout',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'label': 'Connection Timeout (s)',
            'description': 'Timeout for connection attempts'
        },
        {
            'name': 'duration',
            'type': ParameterType.INT,
            'default': 3600,
            'min': 5,
            'max': 86400,
            'label': 'Duration (s)',
            'description': 'Maximum stream duration before auto-advance (1h default)'
        }
    ]
    
    def initialize(self, config):
        """Initialize RTSP stream connection."""
        self.rtsp_url = str(config.get('rtsp_url', 'rtsp://localhost:8554/stream'))
        self.reconnect_delay = int(config.get('reconnect_delay', 5))
        self.buffer_size = int(config.get('buffer_size', 1))
        self.timeout = int(config.get('timeout', 10))
        self.duration = int(config.get('duration', 3600))
        
        self.cap = None
        self.last_frame = None
        self.frame_count = 0
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.last_connection_time = None
        
        # Try to connect
        self._connect()
        
        return True
    
    def _connect(self):
        """Connect to RTSP stream."""
        try:
            import time
            current_time = time.time()
            
            # Check if we should wait before reconnecting
            if self.last_connection_time:
                elapsed = current_time - self.last_connection_time
                if elapsed < self.reconnect_delay:
                    return False
            
            self.last_connection_time = current_time
            self.connection_attempts += 1
            
            # Open RTSP stream
            self.cap = cv2.VideoCapture(self.rtsp_url)
            
            # Set buffer size for low latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            
            # Set timeout (in milliseconds)
            self.cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.timeout * 1000)
            
            if not self.cap.isOpened():
                raise Exception("Failed to open RTSP stream")
            
            # Try to read first frame
            ret, frame = self.cap.read()
            if not ret or frame is None:
                raise Exception("Failed to read first frame from stream")
            
            self.last_frame = frame
            self.connection_attempts = 0  # Reset on successful connection
            
            return True
            
        except Exception as e:
            if self.cap:
                self.cap.release()
                self.cap = None
            return False
    
    def process_frame(self, frame, **kwargs):
        """
        Generate frame from RTSP stream.
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Must contain 'width', 'height'
            
        Returns:
            Frame from RTSP stream
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        
        # Check if we need to reconnect
        if self.cap is None or not self.cap.isOpened():
            if self.connection_attempts >= self.max_connection_attempts:
                # Too many failed attempts - return black frame with error message
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                error_text = f"RTSP Connection Failed"
                url_text = f"{self.rtsp_url[:40]}..."
                cv2.putText(frame, error_text, (width//2 - 150, height//2), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                cv2.putText(frame, url_text, (width//2 - 150, height//2 + 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
                return frame
            else:
                # Try to reconnect
                self._connect()
        
        # Try to read frame from stream
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            
            if ret and frame is not None:
                self.last_frame = frame
                self.frame_count += 1
                
                # Resize to target dimensions
                if frame.shape[1] != width or frame.shape[0] != height:
                    frame = cv2.resize(frame, (width, height))
                
                return frame
            else:
                # Failed to read frame - connection might be lost
                if self.cap:
                    self.cap.release()
                    self.cap = None
        
        # Return last known frame or black frame
        if self.last_frame is not None:
            frame = self.last_frame.copy()
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height))
            
            # Add "reconnecting" overlay
            cv2.putText(frame, "Reconnecting...", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            return frame
        else:
            # No frame available - return black
            return np.zeros((height, width, 3), dtype=np.uint8)
    
    def cleanup(self):
        """Release RTSP stream."""
        if self.cap:
            try:
                # Release in separate thread with timeout to avoid blocking
                import threading
                def release_cap():
                    try:
                        self.cap.release()
                    except:
                        pass
                
                release_thread = threading.Thread(target=release_cap, daemon=True)
                release_thread.start()
                release_thread.join(timeout=1.0)  # Max 1 second wait
                
                self.cap = None
            except Exception as e:
                # Ignore cleanup errors
                self.cap = None
                pass
    
    def is_infinite(self):
        """RTSP streams have a maximum duration for playlist management."""
        return False
    
    def get_duration(self):
        """Return configured duration in seconds."""
        return self.duration
    
    def update_parameter(self, name, value):
        """Update parameter at runtime."""
        if name == 'rtsp_url':
            self.rtsp_url = str(value)
            # Reconnect with new URL
            if self.cap:
                self.cap.release()
                self.cap = None
            self._connect()
            return True
        elif name == 'reconnect_delay':
            self.reconnect_delay = int(value)
            return True
        elif name == 'buffer_size':
            self.buffer_size = int(value)
            if self.cap:
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
            return True
        elif name == 'timeout':
            self.timeout = int(value)
            return True
        elif name == 'duration':
            self.duration = int(value)
            return True
        return False
    
    def get_parameters(self):
        """Return current parameters."""
        return {
            'rtsp_url': self.rtsp_url,
            'reconnect_delay': self.reconnect_delay,
            'buffer_size': self.buffer_size,
            'timeout': self.timeout,
            'duration': self.duration
        }

def get_plugin():
    """Plugin entry point."""
    return RTSPStreamGenerator
