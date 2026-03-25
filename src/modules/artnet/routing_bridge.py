"""
ArtNet Routing Bridge

Bridges the routing system (OutputManager + ArtNetSender) with the player.
Processes video frames and sends to configured ArtNet outputs.
"""

import numpy as np
from typing import Optional, Dict
from .output_manager import OutputManager
from .sender import ArtNetSender
from .routing_manager import ArtNetRoutingManager
from ..core.logger import get_logger

logger = get_logger(__name__)

# GPU sampler imported lazily so the artnet module can load without a GPU context
_ArtNetGPUSampler = None

def _get_gpu_sampler_class():
    global _ArtNetGPUSampler
    if _ArtNetGPUSampler is None:
        try:
            from ..gpu.artnet_sampler import ArtNetGPUSampler as _cls
            _ArtNetGPUSampler = _cls
        except Exception as e:
            logger.warning(f"ArtNetGPUSampler unavailable (compute shaders not supported?): {e}")
    return _ArtNetGPUSampler


class RoutingBridge:
    """Bridges routing system with player and network"""
    
    def __init__(
        self,
        routing_manager: ArtNetRoutingManager,
        canvas_width: int = 1920,
        canvas_height: int = 1080
    ):
        """
        Initialize routing bridge.
        
        Args:
            routing_manager: ArtNet routing manager instance
            canvas_width: Canvas width in pixels
            canvas_height: Canvas height in pixels
        """
        self.routing_manager = routing_manager
        self.output_manager = OutputManager(canvas_width, canvas_height)
        self.sender = ArtNetSender()
        
        self.enabled = False
        self.initialized = False

        # GPU compute shader sampler (optional — lazy init on first GPU hook call)
        self._gpu_sampler = None
        self._gpu_pixel_buffer: dict = {}  # {obj_id: (N,3) uint8 RGB}, updated each frame
        
    def initialize(self):
        """Initialize ArtNet senders from routing configuration"""
        if self.initialized:
            return
        
        # Configure all active outputs
        outputs = self.routing_manager.get_all_outputs()
        for output in outputs.values():
            if output.active:
                try:
                    self.sender.configure_output(output)
                    logger.debug(f"Routing output configured: {output.name}")
                except Exception as e:
                    logger.error(f"Failed to configure output {output.name}: {e}")
        
        self.initialized = True
        logger.debug(f"Routing bridge initialized with {len(outputs)} output(s)")
    
    def process_frame(self, frame: Optional[np.ndarray]):
        """
        Process a video frame and send to all active outputs.

        Args:
            frame: Video frame as RGB numpy array (H, W, 3) uint8, OR None when
                   the GPU compute-shader sampler already populated
                   _gpu_pixel_buffer (frame download was skipped to avoid the
                   ~43-111 ms AMD pipeline drain stall).
        """
        if not self.enabled or not self.initialized:
            return
        
        # FAST PATH: Skip if no outputs configured (saves CPU on pixel sampling)
        outputs = self.routing_manager.get_all_outputs()
        if not outputs:
            return
        
        # FAST PATH: Check if any outputs are actually active
        active_outputs = [o for o in outputs.values() if o.active]
        if not active_outputs:
            return
        
        # Debug logging (throttled)
        if not hasattr(self, '_frame_counter'):
            self._frame_counter = 0
        self._frame_counter += 1
        if self._frame_counter % 120 == 1:
            if frame is not None:
                logger.debug(f"🎬 [RoutingBridge] Received frame: shape={frame.shape}, mean={frame.mean():.1f}")
            else:
                logger.debug("🎬 [RoutingBridge] frame=None (GPU sampler active)")

        try:
            # Get current objects from routing manager
            objects = self.routing_manager.get_all_objects()

            # Convert BGR (OpenCV native) → RGB (expected by pixel sampler)
            # frame may be None when GPU sampler covered all LED reads.
            rgb_frame = frame[:, :, ::-1] if frame is not None else None

            # Render frame to DMX data per output
            rendered_outputs = self.output_manager.render_frame(
                frame=rgb_frame,
                objects=objects,
                outputs=outputs,
                gpu_pixel_buffer=self._gpu_pixel_buffer,
            )
            
            # Send each output's DMX data via ArtNet
            for output_id, dmx_data in rendered_outputs.items():
                if len(dmx_data) > 0:
                    try:
                        # Check if output is configured in sender, if not configure it
                        if output_id not in self.sender.senders:
                            output = outputs.get(output_id)
                            if output and output.active:
                                self.sender.configure_output(output)
                                logger.debug(f"Auto-configured new output: {output.name}")
                        
                        self.sender.send(output_id, dmx_data)
                    except Exception as e:
                        logger.error(f"Failed to send data to output {output_id}: {e}")
        
        except Exception as e:
            logger.error(f"Frame processing error in routing bridge: {e}", exc_info=True)

    def on_gpu_composite(self, gpu_frame) -> None:
        """
        GPU hook: called inside composite_layers() while the final composite
        GPUFrame is still resident on the GPU.

        Lazily creates ArtNetGPUSampler on first call, then dispatches the
        compute shader to sample all LED pixel positions without a full frame
        download.  Results land in self._gpu_pixel_buffer for use by the next
        process_frame() call.

        Args:
            gpu_frame: GPUFrame containing the final composite texture.
        """
        if not self.enabled:
            return

        cls = _get_gpu_sampler_class()
        if cls is None:
            return

        # Lazy initialise sampler (needs GL context — must run on GL thread)
        if self._gpu_sampler is None:
            try:
                from ..gpu import get_context
                ctx = get_context()
                self._gpu_sampler = cls(ctx)
                logger.info("ArtNetGPUSampler: initialised")
            except Exception as e:
                logger.error(f"ArtNetGPUSampler: could not initialise: {e}")
                return

        objects = self.routing_manager.get_all_objects()
        if not objects:
            return

        canvas_w = self.output_manager.canvas_width
        canvas_h = self.output_manager.canvas_height

        self._gpu_sampler.build_positions(objects, canvas_w, canvas_h)
        self._gpu_sampler.sample(gpu_frame)
        self._gpu_pixel_buffer = self._gpu_sampler.get_pixel_buffer()

    def start(self):
        """Enable routing system"""
        if not self.initialized:
            self.initialize()
        
        self.enabled = True
        logger.debug("Routing bridge started")
    
    def stop(self):
        """Disable routing system and send blackout"""
        self.enabled = False
        
        try:
            self.sender.blackout_all()
        except Exception as e:
            logger.error(f"Error during blackout: {e}")
        
        logger.debug("Routing bridge stopped")
    
    def blackout(self):
        """Send blackout to all outputs"""
        self.sender.blackout_all()
    
    def update_canvas_size(self, width: int, height: int):
        """
        Update canvas dimensions.
        
        Args:
            width: New canvas width
            height: New canvas height
        """
        self.output_manager.update_canvas_size(width, height)
    
    def reconfigure_output(self, output_id: str):
        """
        Reconfigure a specific output (after settings change).
        
        Args:
            output_id: Output identifier
        """
        outputs = self.routing_manager.get_all_outputs()
        if output_id in outputs:
            output = outputs[output_id]
            self.sender.update_output_config(output)
            logger.debug(f"Output reconfigured: {output.name}")
    
    def reconfigure_all(self):
        """Reconfigure all outputs (after bulk changes)"""
        outputs = self.routing_manager.get_all_outputs()
        for output in outputs.values():
            if output.active:
                self.sender.configure_output(output)
            else:
                self.sender.remove_output(output.id)
        
        logger.debug("All routing outputs reconfigured")
    
    def get_last_frames(self) -> Dict[str, bytes]:
        """
        Get last rendered frames for all outputs (for DMX monitor).
        
        Returns:
            Dictionary of output_id → DMX bytes
        """
        return self.output_manager.get_all_last_frames()
    
    def get_stats(self) -> Dict:
        """Get statistics for all outputs"""
        outputs = self.routing_manager.get_all_outputs()
        stats = {}
        
        for output_id in outputs.keys():
            stats[output_id] = {
                'render': self.output_manager.get_stats(output_id),
                'sender': self.sender.get_stats(output_id)
            }
        
        return stats
    
    def cleanup(self):
        """Cleanup all resources"""
        self.stop()
        self.sender.cleanup()
        self.output_manager.reset_all()
        if self._gpu_sampler is not None:
            try:
                self._gpu_sampler.release()
            except Exception:
                pass
            self._gpu_sampler = None
        logger.debug("Routing bridge cleaned up")
