"""
ArtNetGPUSampler — wgpu compute shader implementation.

Samples N LED UV positions from the final composite GPU texture.
Only N*4 bytes are transferred back to CPU (vs the full frame).
"""

import os
import numpy as np
import wgpu
from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

_SHADER_PATH = os.path.join(os.path.dirname(__file__), 'shaders', 'artnet_sample.wgsl')


class ArtNetGPUSampler:
    """
    Samples LED pixel colours from a GPU texture using a wgpu compute shader.

    Lifecycle:
        1. build_positions(objects, canvas_w, canvas_h)  — call on config change
        2. sample(gpu_frame)                              — call after each composite
        3. get_pixel_buffer()                             — {obj_id: (N,3) uint8 RGB}
    """

_RING = 3  # triple-buffer ring: submit to slot i, read from slot i-2


class ArtNetGPUSampler:
    """
    Samples LED pixel colours from a GPU texture using a wgpu compute shader.

    Lifecycle:
        1. build_positions(objects, canvas_w, canvas_h)  — call on config change
        2. sample(gpu_frame)                              — call after each composite
        3. get_pixel_buffer()                             — {obj_id: (N,3) uint8 RGB}

    Triple-buffer readback ring
    ---------------------------
    On AMD Vulkan, map_sync on the *current* staging buffer stalls the GPU
    pipeline for ~26 ms while the compute shader drains.  By submitting to slot
    ``i % 3`` and reading from slot ``(i-2) % 3`` (submitted 2 frames ago) the
    GPU has already finished before we call map_sync — near-zero stall.
    The first two calls still stall (slots 0 and 1 have no prior submit), but
    that only happens once at startup.
    """

    def __init__(self, ctx=None):
        self._pipeline = None          # compute pipeline (created once)
        self._pos_buf: wgpu.GPUBuffer | None = None   # UV positions (static)
        # Pre-allocated per-sample STORAGE buffer (compute output).
        self._output_buf: wgpu.GPUBuffer | None = None
        # Triple-buffer readback ring: _RING×(COPY_DST|MAP_READ) staging buffers.
        # Eliminates AMD Vulkan map_sync stall (~26 ms) by reading 2 frames behind.
        self._staging_ring: list[wgpu.GPUBuffer | None] = [None] * _RING
        self._ring_idx: int = 0
        self._ring_submitted: list[bool] = [False] * _RING
        self._all_rgb: np.ndarray | None = None           # (N, 3) uint8 scratch buffer
        self._n_leds = 0
        self._obj_offsets: dict[str, tuple[int, int]] = {}
        self._pixel_buffer: dict[str, np.ndarray] = {}
        self._ready = False
        self._last_build_key = None

    # ------------------------------------------------------------------
    # Position buffer management
    # ------------------------------------------------------------------

    def build_positions(self, objects: dict, canvas_w: int, canvas_h: int) -> None:
        build_key = (
            canvas_w, canvas_h,
            tuple((oid, len(obj.points)) for oid, obj in objects.items() if obj.points),
        )
        if build_key == self._last_build_key:
            return
        self._last_build_key = build_key

        all_uvs: list[tuple[float, float]] = []
        offsets: dict[str, tuple[int, int]] = {}

        for obj_id, obj in objects.items():
            if not obj.points:
                continue
            start = len(all_uvs)
            for p in obj.points:
                all_uvs.append((p.x / canvas_w, p.y / canvas_h))
            offsets[obj_id] = (start, len(obj.points))

        if not all_uvs:
            self._ready = False
            return

        self._n_leds = len(all_uvs)
        self._obj_offsets = offsets

        device = get_device()

        if self._pos_buf is not None:
            self._pos_buf.destroy()

        # (Re-)allocate fixed-size sample buffers whenever LED count changes.
        if self._output_buf is not None:
            self._output_buf.destroy()
        for sb in self._staging_ring:
            if sb is not None:
                sb.destroy()
        self._output_buf = device.create_buffer(
            size=self._n_leds * 4,
            usage=wgpu.BufferUsage.STORAGE | wgpu.BufferUsage.COPY_SRC,
        )
        self._staging_ring = [
            device.create_buffer(
                size=self._n_leds * 4,
                usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
            )
            for _ in range(_RING)
        ]
        self._ring_idx = 0
        self._ring_submitted = [False] * _RING
        self._all_rgb = np.empty((self._n_leds, 3), dtype=np.uint8)

        pos_data = np.array(all_uvs, dtype=np.float32)
        self._pos_buf = device.create_buffer_with_data(
            data=pos_data.tobytes(),
            usage=wgpu.BufferUsage.STORAGE,
        )

        # Load compute pipeline (first call only)
        if self._pipeline is None:
            try:
                with open(_SHADER_PATH, encoding='utf-8') as f:
                    source = f.read()
                shader = device.create_shader_module(code=source)
                self._pipeline = device.create_compute_pipeline(
                    layout="auto",
                    compute={"module": shader, "entry_point": "cs_main"},
                )
                logger.info("ArtNetGPUSampler: wgpu compute pipeline ready")
            except Exception as e:
                logger.error(f"ArtNetGPUSampler: failed to create compute pipeline: {e}")
                self._ready = False
                return

        self._ready = True
        logger.debug(
            f"ArtNetGPUSampler: positions rebuilt "
            f"({self._n_leds} LEDs, {len(offsets)} objects)"
        )

    # ------------------------------------------------------------------
    # Sampling
    # ------------------------------------------------------------------

    def sample(self, gpu_frame) -> None:
        """Triple-buffer ring compute + readback.

        Submit compute + copy to ring slot ``i``.  Read from slot ``(i-2) % 3``
        (submitted 2 frames ago — GPU already done, near-zero stall on AMD).
        """
        if not self._ready or self._n_leds == 0:
            return

        device = get_device()
        i      = self._ring_idx % _RING
        r      = (self._ring_idx - 2) % _RING  # read slot (2 frames ago)

        # ── Dispatch compute + enqueue copy to slot i ─────────────────────
        bg_layout  = self._pipeline.get_bind_group_layout(0)
        bind_group = device.create_bind_group(
            layout=bg_layout,
            entries=[
                {"binding": 0, "resource": gpu_frame.view},
                {"binding": 1, "resource": {"buffer": self._pos_buf,
                                             "offset": 0,
                                             "size": self._n_leds * 8}},
                {"binding": 2, "resource": {"buffer": self._output_buf,
                                             "offset": 0,
                                             "size": self._n_leds * 4}},
            ],
        )
        encoder = device.create_command_encoder()
        comp = encoder.begin_compute_pass()
        comp.set_pipeline(self._pipeline)
        comp.set_bind_group(0, bind_group)
        comp.dispatch_workgroups(max(1, (self._n_leds + 255) // 256))
        comp.end()
        encoder.copy_buffer_to_buffer(
            self._output_buf, 0, self._staging_ring[i], 0, self._n_leds * 4
        )
        device.queue.submit([encoder.finish()])
        self._ring_submitted[i] = True

        # ── Read from slot r (2 frames old, GPU certainly done) ───────────
        read_slot = self._staging_ring[r] if self._ring_submitted[r] else self._staging_ring[i]
        read_slot.map_sync(wgpu.MapMode.READ)
        raw = read_slot.read_mapped()
        read_slot.unmap()

        packed = np.frombuffer(raw, dtype=np.uint32)
        self._all_rgb[:, 0] = (packed & 0xFF).astype(np.uint8)
        self._all_rgb[:, 1] = ((packed >> 8) & 0xFF).astype(np.uint8)
        self._all_rgb[:, 2] = ((packed >> 16) & 0xFF).astype(np.uint8)

        self._pixel_buffer = {
            obj_id: self._all_rgb[start:start + count].copy()
            for obj_id, (start, count) in self._obj_offsets.items()
        }

        self._ring_idx += 1

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_pixel_buffer(self) -> dict:
        return self._pixel_buffer

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        if self._pos_buf is not None:
            self._pos_buf.destroy()
            self._pos_buf = None
        if self._output_buf is not None:
            self._output_buf.destroy()
            self._output_buf = None
        for sb in self._staging_ring:
            if sb is not None:
                try:
                    sb.destroy()
                except Exception:
                    pass
        self._staging_ring = [None] * _RING
        self._ring_submitted = [False] * _RING
        self._all_rgb = None
        self._pipeline = None
        self._ready = False
