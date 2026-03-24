"""
ArtNet GPU Pixel Sampler

Uses an OpenGL 4.3 compute shader to sample N LED pixel positions directly
from the final composite GPU texture, writing packed RGB values into a tiny
Shader Storage Buffer Object (SSBO).

Instead of downloading the full ~24 MB float32 frame and indexing N pixels
in numpy, only N*4 bytes are read back from the GPU.

On AMD gfx902 (driver 25.8.1): the full-frame texture.read() stall is ~50 ms
due to GPU pipeline drain. An SSBO readback of ~2 KB may be significantly
cheaper.  Even if the AMD drain stall applies equally, this path avoids
wasting PCIe bandwidth on megabytes of frame data that ArtNet doesn't need.

UV convention (matches renderer quad and PixelSampler.sample_points):
    (0, 0) = top-left of canvas
    (1, 1) = bottom-right of canvas
    (see renderer.py _QUAD_VERTICES for full derivation)
"""

import os
import numpy as np
from ..core.logger import get_logger

logger = get_logger(__name__)

_SHADER_PATH = os.path.join(os.path.dirname(__file__), 'shaders', 'artnet_sample.comp')


class ArtNetGPUSampler:
    """
    Samples LED pixel colors from a GPU texture using a compute shader.

    Lifecycle:
        1. build_positions(objects, canvas_w, canvas_h)  — call on routing config change
        2. sample(gpu_frame)                              — call after each composite render
        3. get_pixel_buffer()                             — {obj_id: (N,3) uint8 RGB}

    Thread safety: NOT thread-safe.  All calls must be on the GL thread.
    """

    def __init__(self, ctx):
        self._ctx = ctx
        self._compute = None       # moderngl.ComputeShader — loaded once
        self._pos_buf = None       # SSBO: float32 (u,v) pairs, N*2 floats
        self._color_buf = None     # SSBO: uint32 packed RGB, N uints
        self._n_leds = 0
        self._obj_offsets: dict[str, tuple[int, int]] = {}  # {obj_id: (start, count)}
        self._pixel_buffer: dict[str, np.ndarray] = {}      # {obj_id: (N,3) uint8 RGB}
        self._ready = False
        self._last_build_key = None

    # ------------------------------------------------------------------
    # Position buffer management
    # ------------------------------------------------------------------

    def build_positions(self, objects: dict, canvas_w: int, canvas_h: int) -> None:
        """
        Build/rebuild the UV position SSBO from all configured ArtNet objects.

        Idempotent: skips rebuild if objects and canvas size are unchanged.
        Call whenever the routing configuration changes.
        """
        # Compute a cheap change-detection key
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
                # Canvas y=0 = top → UV y=0 = top (matches texture convention)
                all_uvs.append((p.x / canvas_w, p.y / canvas_h))
            offsets[obj_id] = (start, len(obj.points))

        if not all_uvs:
            self._ready = False
            logger.debug("ArtNetGPUSampler: no LED positions — sampler idle")
            return

        self._n_leds = len(all_uvs)
        self._obj_offsets = offsets

        # Upload UV positions to SSBO
        pos_data = np.array(all_uvs, dtype=np.float32)
        if self._pos_buf is not None:
            self._pos_buf.release()
        if self._color_buf is not None:
            self._color_buf.release()

        self._pos_buf = self._ctx.buffer(pos_data.tobytes())
        self._color_buf = self._ctx.buffer(reserve=self._n_leds * 4)  # 1 uint32 per LED

        # Load compute shader (first time only)
        if self._compute is None:
            try:
                with open(_SHADER_PATH, encoding='utf-8') as f:
                    source = f.read()
                self._compute = self._ctx.compute_shader(source)
                logger.info(
                    f"ArtNetGPUSampler: compute shader loaded "
                    f"({self._n_leds} LEDs across {len(offsets)} objects)"
                )
            except Exception as e:
                logger.error(f"ArtNetGPUSampler: failed to load compute shader: {e}")
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
        """
        Dispatch the compute shader to sample all LED positions from gpu_frame.

        gpu_frame: GPUFrame whose .texture is a float32 RGB composite.
        Results stored internally — call get_pixel_buffer() to retrieve.
        Runs synchronously (ctx.finish()) so the caller can read immediately.
        """
        if not self._ready or self._n_leds == 0:
            return

        try:
            # Bind composite texture to unit 0
            gpu_frame.texture.use(location=0)
            self._compute['finalTexture'] = 0
            self._compute['n_leds'] = self._n_leds

            # Bind position (input) and color (output) SSBOs
            self._pos_buf.bind_to_storage_buffer(0)
            self._color_buf.bind_to_storage_buffer(1)

            # Dispatch one thread per LED, in groups of 256
            groups = max(1, (self._n_leds + 255) // 256)
            self._compute.run(group_x=groups)

            # Synchronise: wait for compute shader to finish before CPU read.
            # ctx.finish() maps to glFinish().  On AMD this may still incur the
            # ~50 ms pipeline drain — profiling will show whether SSBO readback
            # is cheaper than full texture.read().
            self._ctx.finish()

            # Read back only N*4 bytes (vs ~24 MB for full frame)
            raw = self._color_buf.read()
            packed = np.frombuffer(raw, dtype=np.uint32)

            # Unpack uint32 → RGB channels
            all_rgb = np.empty((self._n_leds, 3), dtype=np.uint8)
            all_rgb[:, 0] = (packed & 0xFF).astype(np.uint8)           # R
            all_rgb[:, 1] = ((packed >> 8) & 0xFF).astype(np.uint8)    # G
            all_rgb[:, 2] = ((packed >> 16) & 0xFF).astype(np.uint8)   # B

            # Split flat array back into per-object slices
            self._pixel_buffer = {
                obj_id: all_rgb[start:start + count].copy()
                for obj_id, (start, count) in self._obj_offsets.items()
            }

        except Exception as e:
            logger.error(f"ArtNetGPUSampler.sample() error: {e}", exc_info=True)
            self._pixel_buffer = {}

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def get_pixel_buffer(self) -> dict[str, np.ndarray]:
        """
        Return the latest sampled pixel data.

        Returns:
            {obj_id: (N, 3) uint8 array in RGB order}
            Empty dict if sampler is idle or last sample failed.
        """
        return self._pixel_buffer

    @property
    def is_ready(self) -> bool:
        return self._ready

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self) -> None:
        """Free GPU resources."""
        if self._pos_buf is not None:
            self._pos_buf.release()
            self._pos_buf = None
        if self._color_buf is not None:
            self._color_buf.release()
            self._color_buf = None
        self._ready = False
        logger.debug("ArtNetGPUSampler: released")
