"""
Display output plugin – GPU-accelerated GLFW window output for video.

Uses the in-process GLFWDisplay singleton from src/modules/gpu/glfw_display.py.
No subprocess, no IPC Queue, no pickle overhead.
The render thread hands off a numpy reference via push_frame(); the GLFW
thread uploads to its own GL texture and blits a full-screen quad.
"""

import logging
import numpy as np

from ..base import OutputBase
from ..monitor_utils import get_monitor_by_index, get_available_monitors

logger = logging.getLogger(__name__)


class DisplayOutput(OutputBase):
    """
    Display output: GPU-accelerated GLFW window via GLFWDisplay.

    An in-process GLFWDisplay thread receives the numpy frame via push_frame()
    (reference, no copy) and blits it to a GLFW window using its own GL context.
    No subprocess, no IPC Queue, no pickle overhead.

    Features: multi-monitor, fullscreen, windowed, resolution scaling.
    """

    def __init__(self, output_id: str, config: dict):
        super().__init__(output_id, config)

        self.monitor_index = config.get('monitor_index', 0)
        self.fullscreen = config.get('fullscreen', True)
        self.resolution = config.get('resolution', [1920, 1080])
        self.window_title = config.get('window_title', f'Flux Output - {output_id}')

        self.window_created = False
        self.window_name = f'flux_output_{output_id}'

        # No copy needed: GLFW stores a reference, no IPC.
        self.needs_frame_copy = False

        # Set in initialize() — True when GLFW path is active.
        self._using_glfw = False

        # Reference to Player (set by OutputManager after init, if available).
        # Used to signal _on_display_gpu_ready() when WGL sharing is confirmed.
        self._player_ref = None

        logger.info(
            f"🎬 [{self.output_id}] DisplayOutput initialized "
            f"(monitor={self.monitor_index}, fullscreen={self.fullscreen}, "
            f"resolution={self.resolution})"
        )

    # ------------------------------------------------------------------ init

    def initialize(self) -> bool:
        """Start the GLFW display window."""
        from ....gpu.glfw_display import get_glfw_display, _GLFW_AVAILABLE

        logger.info(
            f"🚀 [{self.output_id}] Initializing display output "
            f"(monitor={self.monitor_index}, fullscreen={self.fullscreen})"
        )

        if not _GLFW_AVAILABLE:
            logger.error(f"❌ [{self.output_id}] GLFW not available — cannot open display window")
            return False

        w, h = int(self.resolution[0]), int(self.resolution[1])
        ok = get_glfw_display().start(
            width=w, height=h,
            title=self.window_title,
            monitor_index=self.monitor_index,
            fullscreen=self.fullscreen,
        )
        if ok:
            self._using_glfw = True
            self.window_created = True
            logger.info(f"✅ [{self.output_id}] GLFW display window active")
            # Notify player when GPU mode (WGL context sharing) is ready so it
            # can skip the SSBO download for display-only use cases.
            display = get_glfw_display()
            if display.is_gpu_mode() and self._player_ref is not None:
                if hasattr(self._player_ref, '_on_display_gpu_ready'):
                    self._player_ref._on_display_gpu_ready()
            return True
        logger.error(f"❌ [{self.output_id}] GLFW window creation failed")
        return False

    def process_window_events(self) -> bool:
        """No-op: GLFW handles events in its own thread."""
        return True

    # ------------------------------------------------------------------ send

    def send_frame(self, frame: np.ndarray) -> bool:
        """Deliver a frame to the GLFW display."""
        if not self.window_created:
            return False

        from ....gpu.glfw_display import get_glfw_display
        display = get_glfw_display()
        if display._frame_seq == 0:
            logger.info(f'[{self.output_id}] send_frame: pushing first frame to GLFW ({frame.shape[1]}x{frame.shape[0]})')
        display.push_frame(frame)
        return True

    # ---------------------------------------------------------------- cleanup

    def cleanup(self):
        """Shut down the GLFW display window."""
        if self._using_glfw:
            from ....gpu.glfw_display import get_glfw_display
            get_glfw_display().stop()
            self._using_glfw = False
            self.window_created = False
            logger.debug(f"[{self.output_id}] GLFW display stopped")