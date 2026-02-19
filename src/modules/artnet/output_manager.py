"""
ArtNet Output Manager

Main rendering pipeline that processes video frames and sends to ArtNet outputs.
Handles:
- Pixel sampling from video frames
- Per-object color correction
- Per-output color correction  
- RGB format mapping
- DMX buffer generation per output
- Frame timing and delay
"""

import numpy as np
import time
from typing import Dict, List, Optional, Tuple
from collections import deque

from .object import ArtNetObject
from .output import ArtNetOutput
from .pixel_sampler import PixelSampler
from .color_correction import ColorCorrector
from .rgb_format_mapper import RGBFormatMapper


class OutputManager:
    """Manages ArtNet output rendering and transmission"""
    
    def __init__(self, canvas_width: int = 1920, canvas_height: int = 1080):
        """
        Initialize output manager.
        
        Args:
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
        """
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        
        # Rendering modules
        self.sampler = PixelSampler(canvas_width, canvas_height)
        self.corrector = ColorCorrector()
        self.mapper = RGBFormatMapper()
        
        # Output state tracking
        self.last_frame_time: Dict[str, float] = {}  # output_id → timestamp
        self.delay_buffers: Dict[str, deque] = {}    # output_id → deque of frames
        self.frame_counters: Dict[str, int] = {}     # output_id → frame count
        
        # Last frame storage for DMX monitor
        self.last_frames: Dict[str, bytes] = {}      # output_id → DMX data
        
    def render_frame(
        self,
        frame: np.ndarray,
        objects: Dict[str, ArtNetObject],
        outputs: Dict[str, ArtNetOutput]
    ) -> Dict[str, bytes]:
        """
        Render a single video frame to all active outputs.
        
        Args:
            frame: Video frame as RGB numpy array (H, W, 3) uint8
            objects: Dictionary of object_id → ArtNetObject
            outputs: Dictionary of output_id → ArtNetOutput
        
        Returns:
            Dictionary of output_id → DMX bytes ready for transmission
        """
        rendered_outputs = {}
        
        for output_id, output in outputs.items():
            # Skip inactive outputs
            if not output.active:
                continue
            
            # Check FPS throttling
            if not self._should_send_frame(output_id, output.fps):
                continue
            
            # Render DMX data for this output
            dmx_data = self._render_output(frame, output, objects)
            
            # Apply delay buffer
            dmx_data = self._apply_delay(output_id, output.delay, output.fps, dmx_data)
            
            # Store for DMX monitor
            self.last_frames[output_id] = dmx_data
            
            rendered_outputs[output_id] = dmx_data
        
        return rendered_outputs
    
    def _render_output(
        self,
        frame: np.ndarray,
        output: ArtNetOutput,
        objects: Dict[str, ArtNetObject]
    ) -> bytes:
        """
        Render DMX data for a single output.
        
        Args:
            frame: Video frame RGB array
            output: Target output configuration
            objects: All available objects
        
        Returns:
            DMX bytes for this output
        """
        # Collect all assigned objects
        assigned_objs = [
            obj for obj_id, obj in objects.items()
            if obj_id in output.assigned_objects
        ]
        
        if not assigned_objs:
            # No objects assigned, return black
            return bytes()
        
        # Process each object
        all_channels = []
        
        for obj in assigned_objs:
            if len(obj.points) == 0:
                continue
            
            # Sample pixels at object coordinates
            rgb_pixels = self.sampler.sample_object(obj, frame)
            
            if len(rgb_pixels) == 0:
                continue
            
            # Apply per-object color correction
            rgb_pixels = self.corrector.apply(
                rgb_pixels,
                brightness=obj.brightness,
                contrast=obj.contrast,
                red=obj.red,
                green=obj.green,
                blue=obj.blue
            )
            
            # Handle white channel for RGBW+ LEDs
            if obj.led_type != 'RGB':
                rgb_pixels = self.corrector.apply_white_channel(
                    rgb_pixels,
                    white_mode=obj.white_mode,
                    white_threshold=obj.white_threshold,
                    white_behavior=obj.white_behavior,
                    color_temp=obj.color_temp,
                    led_type=obj.led_type
                )
            
            # Apply per-output color correction
            rgb_pixels = self.corrector.apply(
                rgb_pixels,
                brightness=output.brightness,
                contrast=output.contrast,
                red=output.red,
                green=output.green,
                blue=output.blue
            )
            
            # Map to LED channel order
            rgb_pixels = self.mapper.map_channels(rgb_pixels, obj.channel_order)
            
            # Flatten to DMX channels
            dmx_bytes = self.mapper.flatten_to_dmx(rgb_pixels)
            all_channels.append(dmx_bytes)
        
        # Concatenate all object channels
        if all_channels:
            return b''.join(all_channels)
        else:
            return bytes()
    
    def _should_send_frame(self, output_id: str, fps: int) -> bool:
        """
        Check if enough time has passed based on FPS.
        
        Args:
            output_id: Output identifier
            fps: Target frames per second
        
        Returns:
            True if frame should be sent
        """
        current_time = time.time()
        frame_interval = 1.0 / fps if fps > 0 else 0
        
        last_time = self.last_frame_time.get(output_id, 0)
        
        if current_time - last_time >= frame_interval:
            self.last_frame_time[output_id] = current_time
            return True
        
        return False
    
    def _apply_delay(
        self, 
        output_id: str, 
        delay_ms: int, 
        fps: int,
        dmx_data: bytes
    ) -> bytes:
        """
        Apply delay buffer to output.
        
        Args:
            output_id: Output identifier
            delay_ms: Delay in milliseconds
            fps: Frames per second
            dmx_data: Current frame DMX data
        
        Returns:
            Delayed DMX data (or black if buffer not full)
        """
        if delay_ms == 0:
            return dmx_data
        
        # Initialize buffer if needed
        if output_id not in self.delay_buffers:
            self.delay_buffers[output_id] = deque()
        
        buffer = self.delay_buffers[output_id]
        
        # Add current frame
        buffer.append(dmx_data)
        
        # Calculate required buffer size
        delay_frames = int((delay_ms / 1000.0) * fps)
        
        # Return delayed frame if buffer is full
        if len(buffer) > delay_frames:
            return buffer.popleft()
        else:
            # Buffer not full yet, return black
            return bytes(len(dmx_data))
    
    def get_last_frame(self, output_id: str) -> Optional[bytes]:
        """
        Get last rendered frame for an output (for DMX monitor).
        
        Args:
            output_id: Output identifier
        
        Returns:
            Last DMX bytes or None if no frame rendered
        """
        return self.last_frames.get(output_id)
    
    def get_all_last_frames(self) -> Dict[str, bytes]:
        """Get all last frames for all outputs"""
        return self.last_frames.copy()
    
    def update_canvas_size(self, width: int, height: int):
        """
        Update canvas dimensions.
        
        Args:
            width: New canvas width
            height: New canvas height
        """
        self.canvas_width = width
        self.canvas_height = height
        self.sampler.update_canvas_size(width, height)
    
    def reset_output(self, output_id: str):
        """
        Reset state for a specific output.
        
        Args:
            output_id: Output identifier
        """
        self.last_frame_time.pop(output_id, None)
        self.delay_buffers.pop(output_id, None)
        self.frame_counters.pop(output_id, None)
        self.last_frames.pop(output_id, None)
    
    def reset_all(self):
        """Reset all output state"""
        self.last_frame_time.clear()
        self.delay_buffers.clear()
        self.frame_counters.clear()
        self.last_frames.clear()
    
    def get_stats(self, output_id: str) -> Dict:
        """
        Get statistics for an output.
        
        Args:
            output_id: Output identifier
        
        Returns:
            Dictionary with stats (fps, buffer size, etc.)
        """
        return {
            'last_frame_time': self.last_frame_time.get(output_id, 0),
            'buffer_size': len(self.delay_buffers.get(output_id, [])),
            'frame_count': self.frame_counters.get(output_id, 0),
            'has_data': output_id in self.last_frames
        }
