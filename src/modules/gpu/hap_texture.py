"""
HapTexture — BC1/BC3 GPU texture for HAP-compressed video sources.

BC1/BC3 (block-compressed) textures have limited usage flags:
    TEXTURE_BINDING | COPY_DST  ← only these are allowed for BC formats
They CANNOT be render attachments — all blend/effect passes work on rgba8unorm.

Upload flow (per-frame, zero CPU decompression):
    memoryview (DXT bytes)
        ↓  write_texture() — C-level DMA into D3D12 upload heap
    BC1 texture (VRAM)
        ↓  passthrough shader samples BC1 (GPU decompresses during sampling)
    rgba8unorm GPUFrame (VRAM)
        ↓  normal compositor pipeline (effects, blend, etc.)

The BC1/BC3 "decode" is hardware-accelerated during sampling — effectively free.

Thread safety: HapTexturePool is thread-safe via an internal lock.
"""
from __future__ import annotations
import threading
import wgpu
from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

# Bytes per 4×4 DXT block per variant
_BC_BYTES_PER_BLOCK: dict[str, int] = {'bc1': 8, 'bc3': 16}

# wgpu texture format constants
_BC_FORMAT: dict[str, wgpu.TextureFormat] = {
    'bc1': wgpu.TextureFormat.bc1_rgba_unorm,
    'bc3': wgpu.TextureFormat.bc3_rgba_unorm,
}

# Passthrough WGSL shader — samples a BC1/BC3 (or any) texture and writes rgba.
# GPU hardware decompresses BC1/BC3 during textureSample, no manual decode needed.
_PASSTHROUGH_WGSL = """\
struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var t_src: texture_2d<f32>;
@group(0) @binding(2) var s_src: sampler;

struct VertexOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex fn vs_main(@builtin(vertex_index) vi: u32) -> VertexOut {
    var uv = vec2<f32>(f32((vi << 1u) & 2u), f32(vi & 2u));
    return VertexOut(vec4<f32>(uv * 2.0 - 1.0, 0.0, 1.0), vec2<f32>(uv.x, 1.0 - uv.y));
}

@fragment fn fs_main(in: VertexOut) -> @location(0) vec4<f32> {
    return textureSample(t_src, s_src, in.uv);
}
"""


class HapTexture:
    """One BC1/BC3 input texture for HAP video sources.

    Not a render target — only TEXTURE_BINDING | COPY_DST.
    After upload(), call decode_to(output_frame, renderer) to run the
    passthrough shader and write decoded rgba into an rgba8unorm GPUFrame.

    The .view attribute is wgpu-compatible (same interface as GPUFrame.view)
    so HapTexture can be passed directly to Renderer.render() as a texture.
    """

    def __init__(self, width: int, height: int, dxt_variant: str = 'bc1') -> None:
        if dxt_variant not in _BC_FORMAT:
            raise ValueError(f"Unknown DXT variant: {dxt_variant!r}. Use 'bc1' or 'bc3'.")

        self.width = width
        self.height = height
        self.dxt_variant = dxt_variant

        bpb = _BC_BYTES_PER_BLOCK[dxt_variant]
        # bytes_per_row: one row of 4×4 blocks
        self._bpr = (width // 4) * bpb

        device = get_device()
        fmt = _BC_FORMAT[dxt_variant]
        self.texture: wgpu.GPUTexture = device.create_texture(
            size=(width, height, 1),
            format=fmt,
            usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
        )
        self.view: wgpu.GPUTextureView = self.texture.create_view()

    def upload(self, dxt_bytes) -> None:
        """Upload DXT-compressed bytes to the BC texture via zero-copy DMA.

        dxt_bytes must be a memoryview or bytes-like object of exactly
        frame_bytes (width//4 * height//4 * bytes_per_block) bytes.
        Uses write_texture() which queues a non-blocking async DMA —
        CPU returns immediately; GPU uses the data before any subsequent
        render pass that samples this texture (wgpu queue ordering).
        """
        get_device().queue.write_texture(
            {"texture": self.texture, "mip_level": 0, "origin": (0, 0, 0)},
            dxt_bytes,
            {
                "offset": 0,
                "bytes_per_row": self._bpr,
                "rows_per_image": self.height // 4,
            },
            (self.width, self.height, 1),  # size in texels (pixels) — wgpu requirement
        )

    def decode_to(self, output_frame, renderer) -> None:
        """Render BC1/BC3 texture → rgba8unorm output_frame.

        The GPU samples this BC texture (hardware decompresses during sampling)
        and writes the result into output_frame (rgba8unorm GPUFrame).
        This is effectively a free decompression step — no CPU involvement.
        """
        renderer.render(
            wgsl_source=_PASSTHROUGH_WGSL,
            target=output_frame,
            uniforms={},
            textures=[self],
        )


class HapTexturePool:
    """Pool of HapTexture objects keyed by (width, height, dxt_variant).

    Reusing BC1/BC3 GPU textures avoids per-frame VRAM allocation.
    Acquire before use, release after the GPU render pass that samples it.
    Thread-safe via internal lock.
    """

    MAX_PER_BUCKET = 4  # Enough for master + a few slave HAP layers

    def __init__(self) -> None:
        self._pool: dict[tuple, list[HapTexture]] = {}
        self._in_use: set[int] = set()
        self._lock = threading.Lock()

    def acquire(self, width: int, height: int, dxt_variant: str = 'bc1') -> HapTexture:
        key = (width, height, dxt_variant)
        with self._lock:
            pool = self._pool.setdefault(key, [])
            for tex in pool:
                if id(tex) not in self._in_use:
                    self._in_use.add(id(tex))
                    return tex

            if len(pool) >= self.MAX_PER_BUCKET:
                evicted = pool.pop(0)
                self._in_use.discard(id(evicted))
                logger.warning(
                    f"HapTexturePool: bucket {width}x{height} {dxt_variant} hit cap "
                    f"({self.MAX_PER_BUCKET}). Force-evicting oldest slot."
                )

            tex = HapTexture(width, height, dxt_variant)
            pool.append(tex)
            self._in_use.add(id(tex))
            logger.debug(f"HapTexturePool: new {width}x{height} {dxt_variant} "
                         f"(pool size now {len(pool)})")
            return tex

    def release(self, tex: HapTexture | None) -> None:
        if tex is not None:
            with self._lock:
                self._in_use.discard(id(tex))

    def release_all(self) -> None:
        with self._lock:
            self._pool.clear()
            self._in_use.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_hap_pool: HapTexturePool | None = None
_hap_pool_lock = threading.Lock()


def get_hap_texture_pool() -> HapTexturePool:
    global _hap_pool
    if _hap_pool is None:
        with _hap_pool_lock:
            if _hap_pool is None:
                _hap_pool = HapTexturePool()
    return _hap_pool


def _reset_hap_pool() -> None:
    """Reset the HAP texture pool (call after GPU pipeline reset)."""
    global _hap_pool
    with _hap_pool_lock:
        if _hap_pool is not None:
            try:
                _hap_pool.release_all()
            except Exception:
                pass
            _hap_pool = None
