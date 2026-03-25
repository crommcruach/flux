"""
GPUFrame — thin wrapper around a ModernGL texture + FBO pair.

Lifecycle:
    Allocated by TexturePool.acquire(), returned via TexturePool.release().
    Never instantiated directly in application code.

Upload:  numpy BGR/BGRA uint8 → GL RGB/RGBA float32 texture
Download: GL RGB/RGBA float32 texture → numpy BGR/BGRA uint8
Sample:   partial readback for Art-Net pixel sampling  (bounding-box only)

GPU texture format: float32 (dtype='f4', GL_RGB32F / GL_RGBA32F)
----------------------------------------------------------------------
AMD Radeon GPUs have a driver bug where GL_RGB8 (uint8 normalized, dtype='u1')
textures produce incorrect results when their sampled values are used in GLSL
arithmetic (e.g. multiplication returns 0, addition with constants gives wrong
output). Direct assignment / passthrough works by accident (hardware blit path).

Using float32 textures (GL_RGB32F) avoids this bug entirely — all shader
arithmetic behaves correctly. The uint8↔float32 conversion is done on the CPU
at upload/download time, which adds negligible overhead.
"""
import numpy as np
import moderngl

# Module-level singleton — shared across all GPUFrame instances.
# Lazy-imported to avoid circular imports; resolved on first download() call.
_ssbo_downloader = None


def _get_ssbo_downloader(ctx):
    global _ssbo_downloader
    if _ssbo_downloader is None:
        from .ssbo_downloader import SSBODownloader
        _ssbo_downloader = SSBODownloader(ctx)
    return _ssbo_downloader


class GPUFrame:
    """
    Wraps a ModernGL texture + FBO pair for one compositing layer or output buffer.

    GPU storage is always float32 (dtype='f4') to work around AMD driver bugs
    with uint8 normalized textures (GL_RGB8) in GLSL arithmetic shaders.

    components: 3 = RGB/BGR, 4 = RGBA/BGRA  (auto-detected from source shape[2])
    """

    def __init__(self, ctx: moderngl.Context, width: int, height: int, components: int = 3):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.components = components
        # Float32 textures: avoids AMD driver bug with GL_RGB8 GLSL arithmetic.
        # Channel reversal (BGR↔RGB) handled in upload/download.
        self.texture: moderngl.Texture = ctx.texture(
            (width, height), components, dtype='f4'
        )
        self.texture.filter = moderngl.LINEAR, moderngl.LINEAR
        self.fbo: moderngl.Framebuffer = ctx.framebuffer(
            color_attachments=[self.texture]
        )
        # Pre-allocated scratch buffers — reused every frame to avoid per-frame
        # heap allocation (eliminates ~24 MB alloc/free per upload and download).
        self._upload_buf = np.empty((height, width, components), dtype=np.float32)
        self._download_buf = np.empty((height, width, components), dtype=np.uint8)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, frame: np.ndarray) -> None:
        """
        Upload numpy BGR/BGRA uint8 array → GL float32 texture.

        frame must be C-contiguous — ensured at call site (memmap views are).
        Channel order: BGR→RGB or BGRA→RGBA (reverse color channels, keep alpha).
        Values are normalised to [0.0, 1.0] before upload.
        Uses a pre-allocated float32 buffer to avoid per-frame heap allocation.
        """
        # In-place: channel-flip + normalize into pre-allocated buffer, no new allocs.
        np.multiply(frame[:, :, ::-1], 1.0 / 255.0, out=self._upload_buf)
        self.texture.write(self._upload_buf)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self) -> np.ndarray:
        """
        Download GL float32 texture → numpy BGR uint8.

        Returns (H, W, 3) uint8 array in BGR order.

        Uses a compute shader + SSBO readback (glGetBufferSubData) to avoid
        the AMD pipeline-drain stall (~111 ms) caused by glGetTexImage.
        Falls back to texture.read() if compute shaders are unavailable.
        """
        return _get_ssbo_downloader(self.ctx).download(self)

    # ------------------------------------------------------------------
    # Pixel sampling (Art-Net)
    # ------------------------------------------------------------------

    def sample_pixels(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """
        Vectorized pixel sampling for Art-Net output.

        xs, ys: integer arrays of pixel coordinates (same length N), y=0 = top.
        Returns: (N, 3) uint8 array in RGB order (Art-Net expects RGB).

        Uses the SSBO download path — same AMD-stall avoidance as download().
        BGR frame is indexed at (ys, xs) and channels are swapped to RGB.
        """
        bgr = _get_ssbo_downloader(self.ctx).download(self)  # (H, W, 3) BGR
        # BGR channel order: index [B, G, R]; Art-Net wants [R, G, B]
        return bgr[ys, xs, ::-1].copy()  # BGR→RGB slice

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release GL resources. Call only when discarding (not pooled release)."""
        self.fbo.release()
        self.texture.release()
