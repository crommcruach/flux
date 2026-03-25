"""
GPUTransitionRenderer — GPU-accelerated two-frame transition renderer.

Holds a persistent 'A' buffer (outgoing frame, uploaded by store_frame())
and renders per-frame transitions via GLSL shaders that receive:
  tex_a (unit 0) = outgoing frame
  tex_b (unit 1) = incoming frame
  + arbitrary per-frame uniforms (e.g. progress)

Used exclusively by TransitionManager.  Do not call from a thread that does
not own the ModernGL context (checked by is_context_from_current_thread()).
"""
from typing import Optional
import numpy as np

from .context import get_context
from .texture_pool import get_texture_pool
from .renderer import get_renderer
from ..core.logger import get_logger

logger = get_logger(__name__)


class GPUTransitionRenderer:
    """
    Manages the GPU-side of a two-frame transition.

    Lifecycle:
        store_frame(frame)                           — upload outgoing frame to _buf_a
        render_transition(frag_src, frame_b, uniforms) → np.ndarray  — render one blended frame
        release()                                    — return GPU resources to pool
    """

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._buf_a: Optional[object] = None   # GPUFrame; acquired on first store_frame()
        self._has_a: bool = False

    def store_frame(self, frame: np.ndarray) -> None:
        """Upload the outgoing (A) frame to a pooled GPU texture."""
        import cv2
        pool = get_texture_pool()
        h, w = frame.shape[:2]
        if self._buf_a is None:
            self._buf_a = pool.acquire(w, h)
        if w != self._buf_a.width or h != self._buf_a.height:
            frame = cv2.resize(frame, (self._buf_a.width, self._buf_a.height))
        self._buf_a.upload(frame)
        self._has_a = True

    def render_transition(
        self,
        frag_src: str,
        frame_b: np.ndarray,
        uniforms: dict,
    ) -> Optional[np.ndarray]:
        """
        Render one transition frame.

        A (stored) is blended with B (current frame) using the given fragment shader.
        Returns BGR uint8 numpy array, or None on failure (caller should CPU-fallback).
        """
        if not self._has_a or self._buf_a is None:
            return None

        import cv2
        pool = get_texture_pool()
        renderer = get_renderer()
        w, h = self._buf_a.width, self._buf_a.height

        # Resize incoming frame to match A buffer if needed
        fh, fw = frame_b.shape[:2]
        if fw != w or fh != h:
            frame_b = cv2.resize(frame_b, (w, h))

        buf_b = pool.acquire(w, h)
        buf_out = pool.acquire(w, h)
        try:
            buf_b.upload(frame_b)
            renderer.render(
                frag_source=frag_src,
                target_fbo=buf_out.fbo,
                uniforms=uniforms,
                textures={
                    'tex_a': (0, self._buf_a),
                    'tex_b': (1, buf_b),
                },
            )
            return buf_out.download()
        except Exception as e:
            logger.error(f"GPUTransitionRenderer.render_transition: {e}")
            return None
        finally:
            pool.release(buf_b)
            pool.release(buf_out)

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
