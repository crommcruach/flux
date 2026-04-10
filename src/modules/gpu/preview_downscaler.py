"""GPU-side preview downscaler for MJPEG browser streams.

Blits a full-resolution composite GPUFrame to a small preview texture via
passthrough.wgsl, then uses a triple-buffer readback ring so the player
thread never stalls waiting for the GPU:

    Frame i
    ├─ GPU blit:  composite  →  ring_tex[i%3]        (render pass, no stall)
    ├─ GPU copy:  ring_tex[i%3] →  ring_staging[i%3] (copy cmd, no stall)
    └─ map_sync:  ring_staging[(i-2)%3]              (submitted 2 frames ago
                                                       → GPU already done
                                                       → near-zero stall)

The JPEG returned is always 2 frames delayed (~33 ms at 30 fps), which is
imperceptible in a browser MJPEG stream.

The ring is essential on AMD Vulkan: a synchronous map_sync on the *current*
frame stalls the player thread while the GPU drains the full-resolution
transform render pass (~20–50 ms), effectively throttling to ~15 fps.
Reading from a slot submitted 2 frames ago avoids that stall entirely.

Note: the bind-group-count mismatch error that previously broke this ring
(passthrough.wgsl declares @binding(0) uniform but doesn't reference it →
layout="auto" excluded it → descriptor had 3 entries, layout had 2) is fixed
in renderer.py by using an explicit GPUBindGroupLayout.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from .frame import GPUFrame

logger = logging.getLogger(__name__)

try:
    import simplejpeg
    _SIMPLEJPEG_AVAILABLE = True
except ImportError:
    _SIMPLEJPEG_AVAILABLE = False

# D3D12 / Vulkan staging-buffer row alignment
_BPP = 4
_ALIGN = 256


def _align(n: int) -> int:
    return (n + _ALIGN - 1) & ~(_ALIGN - 1)


_RING = 3  # number of buffered frames; 3 gives a 2-frame read-back delay


class PreviewDownscaler:
    """wgpu blit → triple-buffer ring → simplejpeg encode.

    Zero stall on the player thread:  GPU copy for frame i-2 completes
    asynchronously while frames i-1 and i are being rendered, so the
    map_sync call that reads it back returns near-instantly.

    Args:
        preview_w:  Target preview width in pixels.
        preview_h:  Target preview height in pixels.
        quality:    JPEG quality 1–100.
    """

    def __init__(self, preview_w: int, preview_h: int, quality: int = 85) -> None:
        self.preview_w = preview_w
        self.preview_h = preview_h
        self.quality = quality
        self._passthrough_src: str | None = None
        self.last_raw: np.ndarray | None = None

        # Triple-buffer ring — lazily initialised on first GPU call.
        self._ring: list = []          # list of (GPUFrame, GPUBuffer, bpr)
        self._ring_idx: int = 0
        self._ring_submitted = [False] * _RING   # slot has a pending GPU copy
        self._ring_poisoned  = [False] * _RING   # slot stuck in pending/mapped — recreate on next use

        # Pre-allocated CPU buffers (filled in _init_ring when dimensions are known).
        # Avoids two per-frame heap allocations (~172 KB each) during readback.
        self._rgba_buf: np.ndarray | None = None   # (h, w, 4) uint8
        self._bgr_buf:  np.ndarray | None = None   # (h, w, 3) uint8

        # Single-worker thread pool for JPEG encoding.
        # cvtColor (SIMD, < 0.3 ms) stays on the player thread so the BGR buffer
        # is always ready to hand off; only the turbojpeg encode (~1–3 ms) runs
        # asynchronously.  The player thread grabs the previous frame's result
        # (non-blocking) and immediately schedules the next encode.
        self._jpeg_pool: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix='PreviewJpeg'
        )
        self._jpeg_future: Future | None = None
        self._last_jpeg:   bytes | None = None

    # ------------------------------------------------------------------
    def _init_ring(self) -> None:
        """Allocate ring_size persistent small textures + staging buffers."""
        import wgpu
        from .frame import GPUFrame
        from .context import get_device

        device = get_device()
        w, h = self.preview_w, self.preview_h
        bpr = _align(w * _BPP)
        for _ in range(_RING):
            tex = GPUFrame(device, w, h)
            staging = device.create_buffer(
                size=bpr * h,
                usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
            )
            self._ring.append((tex, staging, bpr))

        # Pre-allocate CPU readback buffers now that dimensions are known.
        self._rgba_buf = np.empty((h, w, _BPP), dtype=np.uint8)
        self._bgr_buf  = np.empty((h, w, 3),    dtype=np.uint8)

    # ------------------------------------------------------------------
    def _recreate_staging(self, slot: int) -> None:
        """Replace a poisoned staging buffer with a fresh one.

        Called when a previous map_sync left the buffer in 'pending' state.
        The old buffer cannot be unmapped (no valid handle) so we destroy it
        and allocate a new one.
        """
        import wgpu
        from .context import get_device

        tex, old_staging, bpr = self._ring[slot]
        try:
            old_staging.destroy()
        except Exception:
            pass
        new_staging = get_device().create_buffer(
            size=bpr * self.preview_h,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        )
        self._ring[slot] = (tex, new_staging, bpr)
        self._ring_poisoned[slot] = False
        logger.debug('PreviewDownscaler: recreated poisoned staging buffer (slot %d)', slot)

    # ------------------------------------------------------------------
    def encode(self, composite: 'GPUFrame') -> bytes | None:
        """Triple-buffer GPU blit → JPEG encode with near-zero player stall.

        Two async optimisations on top of the ring:
        1. Blit + staging copy are batched into ONE command encoder (one submit).
        2. simplejpeg.encode_jpeg() runs in a background worker thread; the
           player thread only pays a .done() check + ~172 KB BGR copy (~0.05 ms).

        Returns the most recently completed JPEG bytes, or None during warm-up.
        """
        if not _SIMPLEJPEG_AVAILABLE:
            return None

        import wgpu
        import cv2
        from .renderer import get_renderer, load_shader
        from .context import get_device

        if not self._ring:
            self._init_ring()

        if self._passthrough_src is None:
            self._passthrough_src = load_shader('passthrough.wgsl')

        device = get_device()
        renderer = get_renderer()
        w, h = self.preview_w, self.preview_h

        # ── Write slot for this frame ────────────────────────────────────────
        i = self._ring_idx
        tex, staging, bpr = self._ring[i]

        try:
            # Batch blit + copy into ONE encoder → single queue.submit().
            enc = device.create_command_encoder()
            renderer.render(
                wgsl_source=self._passthrough_src,
                target=tex,
                uniforms={},
                textures=[composite],
                encoder=enc,
            )
            enc.copy_texture_to_buffer(
                {"texture": tex.texture, "mip_level": 0, "origin": (0, 0, 0)},
                {"buffer": staging, "offset": 0, "bytes_per_row": bpr, "rows_per_image": h},
                (w, h, 1),
            )
            device.queue.submit([enc.finish()])
            self._ring_submitted[i] = True
        except Exception as exc:
            logger.warning('PreviewDownscaler encode error (slot %d): %s', i, exc, exc_info=True)
            self._ring_idx = (i + 1) % _RING
            return None

        # ── Read the slot submitted 2 frames ago ────────────────────────────
        read_i = (i - (_RING - 1)) % _RING

        if self._ring_submitted[read_i]:
            # Recreate buffer if the slot was left in a bad map state.
            if self._ring_poisoned[read_i]:
                self._recreate_staging(read_i)

            _, read_staging, read_bpr = self._ring[read_i]
            _mapped = False
            try:
                read_staging.map_sync(wgpu.MapMode.READ)
                _mapped = True
                raw_bytes = read_staging.read_mapped()

                # Copy padded row data into pre-allocated RGBA buffer — no alloc.
                padded = np.frombuffer(raw_bytes, dtype=np.uint8).reshape(h, read_bpr)
                np.copyto(self._rgba_buf, padded[:, : w * _BPP].reshape(h, w, _BPP))
                cv2.cvtColor(self._rgba_buf, cv2.COLOR_RGBA2BGR, dst=self._bgr_buf)
                self.last_raw = self._bgr_buf

                # Collect previous encode if done (non-blocking).
                if self._jpeg_future is not None and self._jpeg_future.done():
                    try:
                        self._last_jpeg = self._jpeg_future.result()
                    except Exception:
                        pass

                # Snapshot BGR and hand to worker thread (~172 KB copy, cheap).
                bgr_snap = self._bgr_buf.copy()
                self._jpeg_future = self._jpeg_pool.submit(
                    simplejpeg.encode_jpeg, bgr_snap, self.quality, 'BGR'
                )
            except Exception as exc:
                logger.warning('PreviewDownscaler readback error (slot %d): %s', read_i, exc)
                if not _mapped:
                    # map_sync itself failed — buffer may be stuck in 'pending'.
                    # Mark slot for buffer recreation on next use.
                    self._ring_poisoned[read_i] = True
            finally:
                if _mapped:
                    try:
                        read_staging.unmap()
                    except Exception:
                        pass
                self._ring_submitted[read_i] = False

        self._ring_idx = (i + 1) % _RING
        return self._last_jpeg

    # ------------------------------------------------------------------
    def encode_numpy(self, frame: np.ndarray) -> 'bytes | None':
        """CPU-path fallback: cv2 resize + simplejpeg encode."""
        if not _SIMPLEJPEG_AVAILABLE:
            return None
        try:
            import cv2
            small = cv2.resize(
                frame,
                (self.preview_w, self.preview_h),
                interpolation=cv2.INTER_LINEAR,
            )
            self.last_raw = small
            return simplejpeg.encode_jpeg(small, quality=self.quality, colorspace='BGR')
        except Exception as exc:
            logger.debug('PreviewDownscaler.encode_numpy error: %s', exc)
            return None

    # ------------------------------------------------------------------
    def release(self) -> None:
        """Release GPU resources (call when player shuts down)."""
        # Shut down JPEG encoder thread first.
        self._jpeg_pool.shutdown(wait=False)
        self._jpeg_future = None
        self._last_jpeg   = None

        for tex, staging, _ in self._ring:
            try:
                tex.release()
            except Exception:
                pass
            try:
                staging.destroy()
            except Exception:
                pass
        self._ring.clear()
        self._ring_submitted = [False] * _RING
