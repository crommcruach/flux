"""
Transition Manager - Handles smooth transitions between clips.

GPU path (fade): uses GPUTransitionRenderer + fade_transition.frag.
CPU fallback: uses transition plugin's blend_frames() when GPU unavailable.
"""
import time
import numpy as np
from typing import Optional
from ...core.logger import get_logger, debug_playback

logger = get_logger(__name__)

# GPU transition shaders (filenames relative to src/modules/gpu/shaders/)
_GPU_TRANSITION_SHADERS: dict = {
    'fade': 'fade_transition.frag',
}


class TransitionManager:
    """Manages transitions between video clips. GPU-accelerated for 'fade'."""

    def __init__(self):
        self.config = {
            "enabled": False,
            "effect": "fade",
            "duration": 1.0,
            "easing": "ease_in_out",
            "plugin": None
        }
        self.buffer: Optional[np.ndarray] = None  # CPU fallback "from" frame
        self.active = False
        self.start_time = 0.0
        self.frames = 0
        self._gpu_renderer = None    # GPUTransitionRenderer, lazily created
        self._gpu_shaders: dict = {} # effect → loaded frag source string

    # ── configuration ─────────────────────────────────────────────────────────

    def configure(self, enabled=None, effect=None, duration=None, easing=None, plugin=None):
        if enabled is not None:  self.config["enabled"] = enabled
        if effect is not None:   self.config["effect"] = effect
        if duration is not None: self.config["duration"] = duration
        if easing is not None:   self.config["easing"] = easing
        if plugin is not None:   self.config["plugin"] = plugin

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self, player_name=""):
        if not self.config.get("enabled"):
            return False
        has_frame = (
            self.buffer is not None
            or (self._gpu_renderer is not None and self._gpu_renderer._has_a)
        )
        if not has_frame:
            return False
        self.active = True
        self.start_time = time.time()
        self.frames = 0
        debug_playback(logger, f"⚡ [{player_name}] Transition started: {self.config['effect']}")
        return True

    def apply(self, new_frame: np.ndarray, player_name: str = "") -> np.ndarray:
        if not self.active:
            return new_frame

        elapsed = time.time() - self.start_time
        duration = self.config.get("duration", 1.0)

        if elapsed < duration:
            progress = min(1.0, elapsed / duration)
            eased = max(0.0, min(1.0, self._apply_easing(
                progress, self.config.get("easing", "linear")
            )))
            effect = self.config.get("effect", "fade")

            # ── GPU path ───────────────────────────────────────────────────────
            frag_src = self._get_gpu_shader(effect)
            if frag_src is not None and self._gpu_renderer is not None:
                try:
                    result = self._gpu_renderer.render_transition(
                        frag_src, new_frame, {'progress': eased}
                    )
                    if result is not None:
                        self.frames += 1
                        return result
                except Exception as e:
                    logger.warning(f"⚠️ [{player_name}] GPU transition fallback to CPU: {e}")

            # ── CPU fallback ──────────────────────────────────────────────────
            transition_plugin = self.config.get("plugin")
            if transition_plugin is not None and self.buffer is not None:
                try:
                    blended = transition_plugin.blend_frames(self.buffer, new_frame, eased)
                    self.frames += 1
                    return blended
                except Exception as e:
                    logger.error(f"❌ [{player_name}] Transition error: {e}")
                    self.active = False

            return new_frame
        else:
            self.active = False
            debug_playback(logger, f"✅ [{player_name}] Transition complete ({self.frames} frames)")

        return new_frame

    def store_frame(self, frame: np.ndarray) -> None:
        """Store the outgoing frame for use as transition start.

        Only runs when not already in a transition: avoids overwriting the stored
        outgoing frame and eliminates the wasteful every-frame copy during an
        active transition.
        """
        if not self.config.get("enabled") or self.active:
            return
        self.buffer = frame.copy()
        if self._gpu_renderer is None:
            self._try_init_gpu(frame.shape[1], frame.shape[0])
        if self._gpu_renderer is not None:
            try:
                self._gpu_renderer.store_frame(frame)
            except Exception:
                pass

    def clear(self):
        self.buffer = None
        self.active = False
        self.start_time = 0.0
        self.frames = 0
        if self._gpu_renderer is not None:
            try:
                self._gpu_renderer.release()
            except Exception:
                pass
            self._gpu_renderer = None
        self._gpu_shaders.clear()

    # ── private helpers ────────────────────────────────────────────────────────

    def _try_init_gpu(self, width: int, height: int) -> None:
        """Lazily create GPUTransitionRenderer when the GL context is current."""
        try:
            from ...gpu import is_context_from_current_thread
            if not is_context_from_current_thread():
                return
            from ...gpu.transition_renderer import GPUTransitionRenderer
            self._gpu_renderer = GPUTransitionRenderer(width, height)
            logger.debug(f"GPUTransitionRenderer created ({width}×{height})")
        except Exception as e:
            logger.debug(f"GPU transition renderer unavailable: {e}")

    def _get_gpu_shader(self, effect: str) -> Optional[str]:
        if effect not in _GPU_TRANSITION_SHADERS:
            return None
        if effect not in self._gpu_shaders:
            try:
                from ...gpu.renderer import load_shader
                self._gpu_shaders[effect] = load_shader(_GPU_TRANSITION_SHADERS[effect])
            except Exception:
                return None
        return self._gpu_shaders.get(effect)

    @staticmethod
    def _apply_easing(progress: float, easing: str) -> float:
        if easing == 'ease_in':
            return progress * progress
        elif easing == 'ease_out':
            return 1.0 - (1.0 - progress) ** 2
        elif easing == 'ease_in_out':
            if progress < 0.5:
                return 4.0 * progress ** 3
            else:
                return 1.0 - ((-2.0 * progress + 2.0) ** 3) / 2.0
        return progress  # linear

