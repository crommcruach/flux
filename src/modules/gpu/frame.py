"""
GPUFrame — wgpu RGBA8 texture with upload / download helpers.

Each frame is a GPU texture with usage:
    TEXTURE_BINDING | RENDER_ATTACHMENT | COPY_SRC | COPY_DST

Upload:  numpy BGR/BGRA uint8 → device.queue.write_texture() (async DMA)
Download: staging buffer copy → map_sync(READ) → numpy BGR uint8

Thread-safe: wgpu device queue is internally serialized.
"""
import struct
import cv2
import numpy as np
import wgpu
from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

# RGBA8 is the standard format for all GPU frames.
_FMT = wgpu.TextureFormat.rgba8unorm
_BPP = 4  # bytes per pixel (RGBA8)
_DL_RING = 3  # download staging ring depth (submit slot i, read slot i-2 = near-zero stall)


def _align256(n: int) -> int:
    """Round n up to the next multiple of 256 (D3D12 buffer-copy alignment)."""
    return (n + 255) & ~255


class GPUFrame:
    """
    One GPU frame: RGBA8 texture with upload / download.

    Parameters
    ----------
    device_or_ctx : wgpu.GPUDevice (or ignored legacy context)
    width, height : int
    components : int
        Kept for API compatibility; always stored as 3 (RGB output).
    """

    def __init__(self, device_or_ctx, width: int, height: int, components: int = 3):
        self.width = width
        self.height = height
        self.components = 3  # logical output channels (always RGB)

        device = get_device()
        self.texture: wgpu.GPUTexture = device.create_texture(
            size=(width, height, 1),
            format=_FMT,
            usage=(
                wgpu.TextureUsage.TEXTURE_BINDING
                | wgpu.TextureUsage.RENDER_ATTACHMENT
                | wgpu.TextureUsage.COPY_SRC
                | wgpu.TextureUsage.COPY_DST
            ),
        )
        self.view: wgpu.GPUTextureView = self.texture.create_view()

        # Pre-allocate staging buffer for download reuse.
        # Avoids per-frame GPU memory allocation (create_buffer) which adds
        # overhead on every readback.  Rows are padded to 256 bytes (D3D12).
        _bpr = _align256(width * _BPP)
        self._staging: wgpu.GPUBuffer = device.create_buffer(
            size=_bpr * height,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        )
        self._staging_bpr: int = _bpr
        # Download staging ring — lazy-extended to _DL_RING slots on the first
        # download() call.  Submitting to slot i and reading from slot i-2
        # (submitted 2 frames prior, guaranteed idle) eliminates the
        # map_sync() stall on AMD Vulkan (~20-50 ms on current frame).
        # _staging is reused as ring slot 0; extra slots are only allocated if
        # download() is actually called (most GPUFrames never need it).
        self._dl_ring: list | None = None     # None = not yet initialised
        self._dl_slot: int = 0                # monotonically increasing call count
        self._dl_submitted: list = [False] * _DL_RING

        # Pre-allocated CPU-side RGBA buffer for upload.
        # cv2.cvtColor writes directly into this buffer (no per-frame 8 MB alloc).
        # write_texture() is called with this buffer each frame — it queues a
        # non-blocking DMA copy via wgpu's internal staging ring.  This avoids
        # the MAP_WRITE map_sync() stall (~10 ms on AMD Vulkan) that is caused
        # by wgpu-native waiting for ALL previously-submitted GPU work (not just
        # the buffer copy) before releasing the write lock.
        self._rgba_buf: np.ndarray = np.empty((height, width, _BPP), dtype=np.uint8)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload(self, frame: np.ndarray) -> None:
        """Upload BGR/BGRA uint8 numpy array → GPU texture (RGBA8).

        Uses write_texture() which queues a non-blocking DMA copy via wgpu's
        internal staging ring.  The CPU call returns immediately; the GPU copy
        is ordered before any subsequent render pass that reads this texture
        (wgpu queue ordering guarantee).  The conversion is done in-place into
        a pre-allocated buffer to avoid an 8 MB numpy allocation per frame.
        """
        h, w = frame.shape[:2]
        ch = frame.shape[2] if frame.ndim >= 3 else 1

        # cv2.cvtColor with dst= writes in-place into the pre-allocated RGBA
        # buffer — single SIMD pass, zero allocation.
        if ch == 4:
            cv2.cvtColor(frame, cv2.COLOR_BGRA2RGBA, dst=self._rgba_buf)
        else:
            cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA, dst=self._rgba_buf)

        get_device().queue.write_texture(
            {"texture": self.texture, "mip_level": 0, "origin": (0, 0, 0)},
            self._rgba_buf,
            {"offset": 0, "bytes_per_row": w * _BPP, "rows_per_image": h},
            (w, h, 1),
        )

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download(self) -> np.ndarray:
        """Download GPU texture → BGR uint8 numpy (H, W, 3).

        Uses a 3-slot staging ring to avoid map_sync() stalling on in-flight
        GPU work: copy to slot i, read from slot i-2 (submitted 2 calls ago
        and guaranteed done).  First/second call falls back to synchronous
        read on the just-submitted slot.
        The ring is lazy-initialised on the first call (extra staging buffers
        only allocated when download() is actually used).
        """
        device = get_device()
        w, h = self.width, self.height

        # Lazy-init: extend single _staging to _DL_RING slots.
        if self._dl_ring is None:
            extra = [
                device.create_buffer(
                    size=self._staging_bpr * h,
                    usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
                )
                for _ in range(_DL_RING - 1)
            ]
            self._dl_ring = [self._staging, *extra]

        slot = self._dl_slot % _DL_RING
        read_slot = (self._dl_slot - 2) % _DL_RING

        encoder = device.create_command_encoder()
        encoder.copy_texture_to_buffer(
            {"texture": self.texture, "mip_level": 0, "origin": (0, 0, 0)},
            {
                "buffer": self._dl_ring[slot],
                "offset": 0,
                "bytes_per_row": self._staging_bpr,
                "rows_per_image": h,
            },
            (w, h, 1),
        )
        device.queue.submit([encoder.finish()])
        self._dl_submitted[slot] = True
        self._dl_slot += 1

        # Read from 2 frames ago (near-zero stall) if available, else current (stall).
        buf = self._dl_ring[read_slot] if self._dl_submitted[read_slot] else self._dl_ring[slot]
        buf.map_sync(wgpu.MapMode.READ)
        raw = buf.read_mapped()
        buf.unmap()  # don't destroy — buffer is reused by the ring

        # Strip D3D12 row padding, then convert RGBA → BGR via cv2 (SIMD).
        padded = np.frombuffer(raw, dtype=np.uint8).reshape(h, self._staging_bpr)
        rgba = np.ascontiguousarray(padded[:, : w * _BPP].reshape(h, w, _BPP))
        return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)

    # ------------------------------------------------------------------
    # Pixel sampling (Art-Net)
    # ------------------------------------------------------------------

    def sample_pixels(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Sample pixel colors at given (x, y) arrays. Returns (N, 3) uint8 RGB."""
        bgr = self.download()           # (H, W, 3) BGR
        return bgr[ys, xs, ::-1].copy()  # BGR → RGB

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Release GPU resources."""
        if self._dl_ring is not None:
            for buf in self._dl_ring:
                if buf is not None:
                    try:
                        buf.destroy()
                    except Exception:
                        pass
            self._dl_ring = None
            self._staging = None  # was dl_ring[0]
        elif getattr(self, '_staging', None) is not None:
            self._staging.destroy()
            self._staging = None
        if self.texture is not None:
            self.texture.destroy()
            self.texture = None
            self.view = None


# ---------------------------------------------------------------------------
# Legacy reset shim (called by __init__.reset_gpu_pipeline)
# ---------------------------------------------------------------------------

def _reset_frame_singletons() -> None:
    """No-op — wgpu has no per-context singletons to reset."""
    pass

