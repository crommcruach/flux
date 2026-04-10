"""
GPUTransitionRenderer — wgpu two-frame transition renderer.

Holds a persistent 'A' buffer (outgoing frame) and renders per-frame
transitions via WGSL shaders using the wgpu pipeline.
"""
from typing import Optional
import numpy as np

from .texture_pool import get_texture_pool
from .renderer import get_renderer
from ..core.logger import get_logger

logger = get_logger(__name__)


class GPUTransitionRenderer:
    """
    Manages the GPU-side of a two-frame transition.

    Lifecycle:
        store_gpu_frame(gpu_frame)                      — GPU-to-GPU copy of outgoing frame to _buf_a
        render_transition_gpu(wgsl_src, gpu_b, uniforms) → GPUFrame  — render one blended frame
        release()                                       — return GPU resources to pool
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._buf_a: Optional[object] = None
        self._has_a: bool = False

    def store_gpu_frame(self, gpu_frame) -> None:
        """Store the outgoing (A) frame via GPU-to-GPU texture copy (no CPU round-trip).

        Used when the main render loop runs in GPU-only mode (needs_download=False)
        so that transitions can still be triggered on the next clip change.
        """
        pool = get_texture_pool()
        w, h = gpu_frame.width, gpu_frame.height
        if self._buf_a is None or self._buf_a.width != w or self._buf_a.height != h:
            if self._buf_a is not None:
                pool.release(self._buf_a)
            self._buf_a = pool.acquire(w, h)
        from .context import get_device
        device = get_device()
        encoder = device.create_command_encoder()
        encoder.copy_texture_to_texture(
            {"texture": gpu_frame.texture, "origin": (0, 0, 0), "mip_level": 0},
            {"texture": self._buf_a.texture, "origin": (0, 0, 0), "mip_level": 0},
            (w, h, 1),
        )
        device.queue.submit([encoder.finish()])
        if not self._has_a:
            logger.debug("GPUTransitionRenderer: A-buffer ready (first frame stored)")
        self._has_a = True

    def render_transition_gpu(
        self,
        wgsl_src: str,
        gpu_frame_b,
        uniforms: dict,
    ):
        """Pure GPU-to-GPU blend — no CPU round-trip.

        tex_a (binding 1) = stored A buffer (outgoing)
        tex_b (binding 3) = gpu_frame_b (incoming composite GPUFrame)
        Returns a **pooled GPUFrame** — caller MUST release it to the pool.
        Returns None on failure.
        """
        if not self._has_a or self._buf_a is None:
            return None

        pool = get_texture_pool()
        renderer = get_renderer()
        buf_out = pool.acquire(self._buf_a.width, self._buf_a.height)
        try:
            renderer.render(
                wgsl_source=wgsl_src,
                target=buf_out,
                uniforms=uniforms,
                textures=[self._buf_a, gpu_frame_b],
            )
            return buf_out
        except Exception as e:
            logger.error(f"GPUTransitionRenderer.render_transition_gpu: {e}")
            pool.release(buf_out)
            return None

    def release(self) -> None:
        """Return the A-buffer GPU resource to the pool."""
        if self._buf_a is not None:
            try:
                pool = get_texture_pool()
                pool.release(self._buf_a)
            except Exception:
                pass
            self._buf_a = None
        self._has_a = False
