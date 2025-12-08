"""
WebSocket Video Streaming API for Flux
Provides real-time video frame streaming via WebSocket for live preview.
Simpler and more efficient than WebRTC for LAN environments.
"""

import logging
import cv2
import numpy as np
from flask_socketio import SocketIO, emit, disconnect
from flask import request
import time
import threading

logger = logging.getLogger(__name__)

# Global variables
socketio = None
player_manager = None
_streaming_threads = {}  # {session_id: {'thread': Thread, 'active': bool, 'player_id': str}}
_config = {}

def init_websocket_streaming(app, player_mgr, config):
    """
    Initialize WebSocket streaming with Flask app and player manager.
    
    Args:
        app: Flask application instance
        player_mgr: PlayerManager instance
        config: WebSocket configuration dict
    """
    global socketio, player_manager, _config
    
    player_manager = player_mgr
    _config = config
    
    # Initialize Flask-SocketIO
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",  # Allow all origins for LAN
        async_mode='threading',     # Use threading for simplicity
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25
    )
    
    logger.info(f"WebSocket streaming initialized: quality={_config.get('default_quality', 'medium')}, "
                f"max_fps={_config.get('max_fps', 30)}")
    
    # Register event handlers
    @socketio.on('connect', namespace='/video')
    def handle_connect():
        """Handle client connection."""
        session_id = request.sid
        logger.info(f"WebSocket client connected: {session_id}")
        emit('connected', {'session_id': session_id})
    
    @socketio.on('disconnect', namespace='/video')
    def handle_disconnect(reason=None):
        """Handle client disconnection."""
        session_id = request.sid
        logger.info(f"WebSocket client disconnected: {session_id} (reason: {reason})")
        _stop_streaming(session_id)
    
    @socketio.on('start_stream', namespace='/video')
    def handle_start_stream(data):
        """
        Start streaming video frames to client.
        
        Expected data:
        {
            "player_id": "video" or "artnet",
            "quality": "low" / "medium" / "high" (optional),
            "fps": 15-30 (optional)
        }
        """
        session_id = request.sid
        player_id = data.get('player_id', 'video')
        quality = data.get('quality', _config.get('default_quality', 'medium'))
        fps = data.get('fps', _config.get('max_fps', 30))
        
        logger.info(f"Start stream request: session={session_id}, player={player_id}, quality={quality}, fps={fps}")
        
        # Get quality settings
        quality_presets = _config.get('quality_presets', {})
        if quality not in quality_presets:
            quality = _config.get('default_quality', 'medium')
        
        preset = quality_presets[quality]
        width = preset.get('width', 1280)
        height = preset.get('height', 720)
        jpeg_quality = preset.get('jpeg_quality', 85)
        target_fps = min(fps, preset.get('fps', 30))
        
        # Stop any existing stream for this session
        _stop_streaming(session_id)
        
        # Start new streaming thread
        streaming_thread = threading.Thread(
            target=_stream_worker,
            args=(session_id, player_id, width, height, jpeg_quality, target_fps),
            daemon=True
        )
        
        _streaming_threads[session_id] = {
            'thread': streaming_thread,
            'active': True,
            'player_id': player_id
        }
        
        streaming_thread.start()
        
        emit('stream_started', {
            'player_id': player_id,
            'quality': quality,
            'resolution': f'{width}x{height}',
            'fps': target_fps,
            'jpeg_quality': jpeg_quality
        })
    
    @socketio.on('stop_stream', namespace='/video')
    def handle_stop_stream():
        """Stop streaming video frames."""
        session_id = request.sid
        logger.info(f"Stop stream request: session={session_id}")
        _stop_streaming(session_id)
        emit('stream_stopped', {})
    
    return socketio


def _stop_streaming(session_id):
    """Stop streaming for a specific session."""
    if session_id in _streaming_threads:
        _streaming_threads[session_id]['active'] = False
        # Don't join if we're the streaming thread itself (would cause RuntimeError)
        thread = _streaming_threads[session_id]['thread']
        current_thread = threading.current_thread()
        if thread.is_alive() and thread != current_thread:
            thread.join(timeout=1.0)
        del _streaming_threads[session_id]
        logger.debug(f"Stopped streaming for session {session_id}")


def _stream_worker(session_id, player_id, width, height, jpeg_quality, target_fps):
    """
    Worker thread that continuously sends video frames to client.
    
    Args:
        session_id: SocketIO session ID
        player_id: 'video' or 'artnet'
        width: Target frame width
        height: Target frame height
        jpeg_quality: JPEG compression quality (1-100)
        target_fps: Target frames per second
    """
    frame_interval = 1.0 / target_fps
    frame_count = 0
    start_time = time.time()
    last_frame_id = None  # Track frame identity to avoid re-encoding same frame
    
    logger.info(f"Stream worker started: session={session_id}, player={player_id}, "
                f"{width}x{height} @ {target_fps}fps, quality={jpeg_quality}")
    
    try:
        while _streaming_threads.get(session_id, {}).get('active', False):
            loop_start = time.time()
            
            # Get player
            if player_id == 'artnet':
                player = player_manager.get_artnet_player() if player_manager else None
            else:
                player = player_manager.get_video_player() if player_manager else None
            
            if not player:
                # Send black frame if no player
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                frame_id = None
            else:
                # Get current frame from player
                if hasattr(player, 'last_video_frame') and player.last_video_frame is not None:
                    frame = player.last_video_frame
                    # Use frame object id to detect if it's a new frame
                    frame_id = id(frame)
                elif hasattr(player, 'last_frame') and player.last_frame is not None:
                    # For artnet player, render the LED frame to image
                    canvas_width = getattr(player, 'canvas_width', width)
                    canvas_height = getattr(player, 'canvas_height', height)
                    frame = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
                    frame_id = None
                else:
                    # No frame available, send black
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
                    frame_id = None
            
            # Skip if same frame as last time (no new content)
            if frame_id is not None and frame_id == last_frame_id:
                # Wait shorter interval and check again
                time.sleep(0.001)  # 1ms
                continue
            
            last_frame_id = frame_id
            
            # Resize if needed
            if frame.shape[1] != width or frame.shape[0] != height:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_LINEAR)
            
            # Encode as JPEG (use FASTEST interpolation for low latency)
            _, buffer = cv2.imencode('.jpg', frame, [
                cv2.IMWRITE_JPEG_QUALITY, jpeg_quality,
                cv2.IMWRITE_JPEG_OPTIMIZE, 0  # Disable optimization for faster encoding
            ])
            frame_data = buffer.tobytes()
            
            # Send frame to client
            socketio.emit('video_frame', frame_data, namespace='/video', room=session_id)
            
            frame_count += 1
            
            # Log stats every 100 frames
            if frame_count % 100 == 0:
                elapsed = time.time() - start_time
                actual_fps = frame_count / elapsed if elapsed > 0 else 0
                logger.debug(f"Stream stats: session={session_id}, frames={frame_count}, "
                           f"fps={actual_fps:.1f}, size={len(frame_data)/1024:.1f}KB")
            
            # Maintain target FPS
            elapsed = time.time() - loop_start
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except Exception as e:
        logger.error(f"Stream worker error (session={session_id}): {e}", exc_info=True)
    
    finally:
        logger.info(f"Stream worker stopped: session={session_id}, total_frames={frame_count}")
        # Clean up
        if session_id in _streaming_threads:
            _streaming_threads[session_id]['active'] = False


def cleanup():
    """Clean up all active streams."""
    global _streaming_threads
    
    logger.info("Cleaning up WebSocket streams...")
    
    # Stop all streaming threads
    for session_id in list(_streaming_threads.keys()):
        _stop_streaming(session_id)
    
    _streaming_threads.clear()
    logger.info("WebSocket cleanup complete")
