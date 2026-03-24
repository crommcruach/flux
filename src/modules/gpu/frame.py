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

        Returns (H, W, components) uint8 array in BGR/BGRA order.
        Uses texture.read() (float32 path) to avoid the AMD glReadPixels bug
        that returns zeros when reading float32 FBOs as uint8 (dtype='u1').
        Pre-allocated buffers eliminate per-frame heap allocation.
        """
        data = self.texture.read()
        arr = np.frombuffer(data, dtype=np.float32).reshape(
            self.height, self.width, self.components
        )
        # In-place float→uint8 conversion reusing pre-allocated buffers.
        np.multiply(arr, 255.0, out=self._upload_buf)
        np.clip(self._upload_buf, 0, 255, out=self._upload_buf)
        np.copyto(self._download_buf, self._upload_buf, casting='unsafe')
        return self._download_buf[:, :, ::-1].copy()   # RGB→BGR

    # ------------------------------------------------------------------
    # Pixel sampling (Art-Net)
    # ------------------------------------------------------------------

    def sample_pixels(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """
        Vectorized pixel sampling for Art-Net output.

        xs, ys: integer arrays of pixel coordinates (same length N), y=0 = top.
        Returns: (N, 3) uint8 array in RGB order (Art-Net expects RGB).

        Row 0 of the array = top of the image (same convention as upload).
        Uses texture.read() — AMD-safe float32 path, same as download().
        """
        data = self.texture.read()
        arr = np.frombuffer(data, dtype=np.float32).reshape(
            self.height, self.width, self.components
        )
        np.multiply(arr, 255.0, out=self._upload_buf)
        np.clip(self._upload_buf, 0, 255, out=self._upload_buf)
        np.copyto(self._download_buf, self._upload_buf, casting='unsafe')
        # arr[y, x] = RGB pixel at screen position (x, y); no Y-flip needed
        return self._download_buf[ys, xs, :3]    # return RGB (drop alpha if present)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release GL resources. Call only when discarding (not pooled release)."""
        self.fbo.release()
        self.texture.release()
