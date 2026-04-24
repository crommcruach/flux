"""
Transition Manager - GPU-only clip transitions.

All blending happens on the GPU via apply_gpu() + GPUTransitionRenderer.
No CPU fallbacks, no numpy pixel manipulation.
"""
import time
from typing import Optional
from ...core.logger import get_logger, debug_playback

logger = get_logger(__name__)

# WGSL shader filenames (relative to src/modules/gpu/shaders/)
_GPU_TRANSITION_SHADERS: dict = {
    'fade': 'fade_transition.wgsl',
}


class TransitionManager:
    """GPU-only transition between clips. Uses wgpu shader pipeline."""

    def __init__(self):
        self.config = {
            "enabled": False,
            "effect": "fade",
            "duration": 1.0,
            "easing": "ease_in_out",
        }
        self.active = False
        self.start_time = 0.0
        self.frames = 0
        self._gpu_renderer = None    # GPUTransitionRenderer, lazily created
        self._gpu_shaders: dict = {} # effect → loaded WGSL source string

    # ── configuration ─────────────────────────────────────────────────────────

    def configure(self, enabled=None, effect=None, duration=None, easing=None, **_ignored):
        """Update transition config. Unknown kwargs (e.g. legacy 'plugin=') are silently dropped."""
        if enabled is not None:  self.config["enabled"] = enabled
        if effect is not None:   self.config["effect"] = effect
        if duration is not None: self.config["duration"] = duration
        if easing is not None:   self.config["easing"] = easing

    # ── lifecycle ──────────────────────────────────────────────────────────────

    def start(self, player_name=""):
        """Activate the transition. Returns False if not enabled or no A-buffer."""
        if not self.config.get("enabled"):
            logger.debug(f"⏭️ [{player_name}] Transition skipped: enabled=False")
            return False
        has_frame = self._gpu_renderer is not None and self._gpu_renderer._has_a
        if not has_frame:
            logger.debug(
                f"⏭️ [{player_name}] Transition skipped: no A-buffer "
                f"(renderer={'None' if self._gpu_renderer is None else 'ok'}, "
                f"_has_a={getattr(self._gpu_renderer, '_has_a', '?')})"
            )
            return False
        self.active = True
        self.start_time = time.time()
        self.frames = 0
        logger.debug(f"⚡ [{player_name}] Transition STARTED: {self.config['effect']} {self.config.get('duration', 1.0)}s")
        return True

    def apply_gpu(self, gpu_frame_b, display_fn) -> bool:
        """Pure GPU transition: blend A-buffer + gpu_frame_b → display.

        Called every frame by _on_transition_gpu_frame while active.
        display_fn(GPUFrame) — glfw_display.push_gpu_frame().
        Releases the blended GPUFrame immediately after display_fn.
        Returns True while running, False when duration expires.
        """
        if not self.active:
            return False

        # Reset timer on first frame — guards against thread-stop gap.
        if self.frames == 0:
            self.start_time = time.time()

        elapsed = time.time() - self.start_time
        duration = self.config.get("duration", 1.0)

        if elapsed >= duration:
            self.active = False
            logger.debug(f"✅ GPU transition complete ({self.frames} frames blended)")
            return False

        progress = min(1.0, elapsed / duration)
        eased = max(0.0, min(1.0, self._apply_easing(
            progress, self.config.get("easing", "linear")
        )))
        frag_src = self._get_gpu_shader(self.config.get("effect", "fade"))

        if frag_src is None:
            effect = self.config.get('effect', 'fade')
            logger.warning(f"⚠️ GPU transition shader not available for effect='{effect}' — no blend rendered")
            return False

        if self._gpu_renderer is not None:
            try:
                result = self._gpu_renderer.render_transition_gpu(
                    frag_src, gpu_frame_b, {'progress': eased}
                )
                if result is not None:
                    try:
                        display_fn(result)
                        self.frames += 1
                        return True
                    finally:
                        from ...gpu.texture_pool import get_texture_pool
                        get_texture_pool().release(result)
            except Exception as e:
                logger.warning(f"⚠️ GPU transition blend error: {e}")

        return False

    def store_gpu_frame(self, gpu_frame) -> None:
        """Store the outgoing composite as the transition A-buffer (GPU→GPU copy).

        Called every frame by _on_transition_gpu_frame while NOT active,
        keeping the A-buffer fresh for the next transition trigger.
        """
        if not self.config.get("enabled") or self.active:
            return
        if self._gpu_renderer is None:
            self._try_init_gpu(gpu_frame.width, gpu_frame.height)
            if self._gpu_renderer is not None:
                logger.info(f"🎬 GPU transition renderer created ({gpu_frame.width}×{gpu_frame.height})")
            else:
                logger.warning("⚠️ GPU transition renderer init FAILED — transitions unavailable")
        if self._gpu_renderer is not None:
            try:
                self._gpu_renderer.store_gpu_frame(gpu_frame)
            except Exception as e:
                logger.debug(f"store_gpu_frame error: {e}")

    def clear(self):
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
        try:
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
