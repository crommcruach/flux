"""
SSBODownloader — GPU-to-CPU frame download via compute shader + SSBO.

Replaces GPUFrame.download()'s texture.read() (glGetTexImage) which triggers
the AMD pipeline-drain stall (~111 ms on gfx902) with a compute shader path
that writes pixel data into an SSBO and reads it back via glGetBufferSubData.

On AMD gfx902:
    texture.read()   → ~111 ms  (glGetTexImage, full pipeline drain)
    buffer.read()    → ~2-21 ms (glGetBufferSubData, no pipeline drain)

Output format: 4 bytes per pixel (BGRX), row-major, top-to-bottom.
    np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)[:, :, :3]  → BGR uint8

The shader uses sampler2D on the float32 texture — this works correctly on
AMD (unlike GL_RGB8 uint8 textures which are broken under GLSL arithmetic).

Thread-safety: NOT thread-safe — all calls must be on the GL thread.
"""

import os
import numpy as np
from ..core.logger import get_logger

logger = get_logger(__name__)

_SHADER_PATH = os.path.join(os.path.dirname(__file__), 'shaders', 'preview_download.comp')


class SSBODownloader:
    """
    Downloads a GPUFrame (float32 texture) to CPU as BGR uint8 via compute shader.

    Lifecycle:
        downloader = SSBODownloader(ctx)
        bgr = downloader.download(gpu_frame)   # returns (H, W, 3) uint8 BGR

    The SSBO is allocated once on first use and re-allocated only when
    resolution changes — no per-frame heap allocation.
    """

    def __init__(self, ctx):
        self._ctx = ctx
        self._compute = None    # moderngl.ComputeShader, loaded once
        self._ssbo = None       # output buffer: W*H*4 bytes (BGRX uint32)
        self._ssbo_size = 0     # allocated size in bytes
        self._load_failed = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(self, gpu_frame) -> np.ndarray:
        """
        Download gpu_frame.texture to a BGR uint8 numpy array.

        Falls back to gpu_frame.texture.read() (slow path) if the compute
        shader cannot be loaded (e.g. OpenGL < 4.3).

        Returns: (H, W, 3) uint8 C-contiguous BGR array.
        """
        if self._load_failed:
            return self._fallback_download(gpu_frame)

        if not self._ensure_ready():
            return self._fallback_download(gpu_frame)

        W, H = gpu_frame.width, gpu_frame.height
        self._ensure_ssbo(W, H)

        try:
            # Zero the SSBO so stale data from previous frames doesn't leak
            # through if any threads are out-of-bounds skipped.
            # (Not strictly needed but cheaply catches bugs during testing.)
            # Actually: every pixel is written unconditionally, so no need.

            # Bind the float32 texture to unit 0
            gpu_frame.texture.use(location=0)
            self._compute['uTexture'] = 0
            self._compute['uWidth'] = W
            self._compute['uHeight'] = H

            # Bind output SSBO to binding point 0
            self._ssbo.bind_to_storage_buffer(0)

            # Dispatch: one thread per pixel
            groups = max(1, (W * H + 255) // 256)
            self._compute.run(group_x=groups)

            # glGetBufferSubData — does NOT trigger AMD pipeline-drain stall
            self._ctx.finish()
            raw = self._ssbo.read()

            # raw is W*H*4 bytes (BGRX uint32 per pixel), row 0 = top
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(H, W, 4)
            return arr[:, :, :3].copy()  # drop X byte → BGR

        except Exception as e:
            logger.error(f"SSBODownloader.download() error: {e}", exc_info=True)
            return self._fallback_download(gpu_frame)

    def release(self) -> None:
        """Release GPU resources."""
        if self._ssbo is not None:
            self._ssbo.release()
            self._ssbo = None
        # Compute shader is shared-ish but we own it — release it
        if self._compute is not None:
            self._compute.release()
            self._compute = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_ready(self) -> bool:
        """Load the compute shader on first call. Returns False if unavailable."""
        if self._compute is not None:
            return True
        try:
            with open(_SHADER_PATH, encoding='utf-8') as f:
                source = f.read()
            self._compute = self._ctx.compute_shader(source)
            logger.info("SSBODownloader: compute shader loaded — SSBO download path active")
            return True
        except Exception as e:
            logger.warning(
                f"SSBODownloader: compute shader unavailable ({e}) — "
                f"falling back to texture.read()"
            )
            self._load_failed = True
            return False

    def _ensure_ssbo(self, width: int, height: int) -> None:
        """Allocate or reallocate the SSBO when resolution changes."""
        needed = width * height * 4  # 4 bytes per pixel (BGRX)
        if self._ssbo is None or self._ssbo_size != needed:
            if self._ssbo is not None:
                self._ssbo.release()
            self._ssbo = self._ctx.buffer(reserve=needed)
            self._ssbo_size = needed
            logger.debug(
                f"SSBODownloader: SSBO allocated {needed / (1024*1024):.1f} MB "
                f"({width}×{height})"
            )

    @staticmethod
    def _fallback_download(gpu_frame) -> np.ndarray:
        """Slow fallback: texture.read() path (used when compute shader unavailable)."""
        data = gpu_frame.texture.read()
        arr = np.frombuffer(data, dtype=np.float32).reshape(
            gpu_frame.height, gpu_frame.width, gpu_frame.components
        )
        out = np.empty((gpu_frame.height, gpu_frame.width, gpu_frame.components), dtype=np.uint8)
        np.multiply(arr, 255.0, out=arr)  # reuse arr as scratch
        np.clip(arr, 0, 255, out=arr)
        np.copyto(out, arr, casting='unsafe')
        return out[:, :, ::-1].copy()  # RGB→BGR
