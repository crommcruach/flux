"""
Renderer — wgpu full-screen shader runner.

All GPU passes (blend, effects, colour grading, …) go through this renderer.
Pipelines are cached by WGSL source string — compiled once, reused every frame.
LRU eviction (default limit 256) prevents unbounded cache growth.

Uniform convention
------------------
Every WGSL shader declares:

    struct Uniforms { data: array<f32, 64> }
    @group(0) @binding(0) var<uniform> u: Uniforms;

The renderer packs the caller's ``uniforms`` dict into 256 bytes (64 × f32):

* float  → stored as f32
* int    → stored as bitcast f32 (recover in WGSL: bitcast<i32>(u.data[N]))
* tuple  → each element expanded in order

Values are packed in the iteration order of the ``uniforms`` dict (Python 3.7+).

Texture bindings
----------------
Each element of the ``textures`` list occupies two consecutive bindings:

    index 0  → binding 1 (texture_2d<f32>)  +  binding 2 (sampler)
    index 1  → binding 3 (texture_2d<f32>)  +  binding 4 (sampler)
    …

A shared linear sampler (binding 2, 4, …) is created once per device.

Usage
-----
    renderer = get_renderer()
    renderer.render(
        wgsl_source=blend_src,              # complete WGSL module
        target=composite_gpu_frame,         # GPUFrame used as render attachment
        uniforms={'opacity': 0.8, 'mode': 0},
        textures=[composite_gpu_frame, layer_gpu_frame],
    )
"""
import os
import re
import struct
import threading
from collections import OrderedDict
import numpy as np
import wgpu
from .context import get_device
from ..core.logger import get_logger

logger = get_logger(__name__)

_SHADER_DIR = os.path.join(os.path.dirname(__file__), 'shaders')
_LRU_LIMIT = 256
_BG_CACHE_LIMIT = 64   # max cached bind group objects (keyed by unifbuf+texture ids)
_TARGET_FORMAT = wgpu.TextureFormat.rgba8unorm
_UNIF_RING = 8        # pre-allocated uniform buffer slots (supports N-pass batching)
_EMPTY_UNIFORMS: bytes = bytes(256)  # cached zero block for empty-uniform passes


# ---------------------------------------------------------------------------
# Uniform packing helper
# ---------------------------------------------------------------------------

def _pack_uniforms(uniforms: dict) -> bytes:
    """Pack a uniforms dict into 256 bytes (64 × f32 flat array).

    * float  → f32
    * int    → bitcast as f32 (use bitcast<i32>(u.data[N]) in WGSL)
    * tuple/list → each element expanded recursively
    """
    if not uniforms:
        return _EMPTY_UNIFORMS   # cached singleton — no allocation
    slots: list[float] = []

    def _push(v):
        if isinstance(v, bool):
            slots.append(struct.unpack('f', struct.pack('I', int(v)))[0])
        elif isinstance(v, int):
            slots.append(struct.unpack('f', struct.pack('i', v))[0])
        elif isinstance(v, float):
            slots.append(v)
        elif isinstance(v, (tuple, list)):
            for x in v:
                _push(x)
        else:
            slots.append(float(v))

    for v in uniforms.values():
        _push(v)

    # Pad to exactly 64 floats
    while len(slots) < 64:
        slots.append(0.0)
    return struct.pack('64f', *slots[:64])


# ---------------------------------------------------------------------------
# Renderer class
# ---------------------------------------------------------------------------

class Renderer:
    def __init__(self):
        self._pipelines: OrderedDict[tuple, wgpu.GPURenderPipeline] = OrderedDict()
        # Explicit BGL/pipeline-layout cache keyed by texture count.
        # Avoids layout="auto" which excludes WGSL bindings that are declared
        # but not referenced in the shader body (e.g. the uniform in passthrough.wgsl),
        # causing create_bind_group to fail with a binding-count mismatch.
        self._bgls: dict[int, wgpu.GPUBindGroupLayout] = {}
        self._pip_layouts: dict[int, wgpu.GPUPipelineLayout] = {}
        self._sampler: wgpu.GPUSampler | None = None
        # Uniform buffer ring — _UNIF_RING pre-allocated slots.
        # When multiple render passes are batched into one command encoder
        # each pass needs its own uniform region (a single buffer would be
        # overwritten by the next write_buffer before the GPU reads it).
        # Lazy-init on first render().
        self._unif_ring: list[wgpu.GPUBuffer] = []
        self._unif_idx: int = 0
        # Per-slot last-written bytes: skip write_buffer when data unchanged
        # (most passthrough/blend passes use identical uniforms every frame).
        self._unif_last: list[bytes | None] = [None] * _UNIF_RING
        # Bind group cache — avoids device.create_bind_group() every frame.
        # Keyed by (id(unifbuf), id(tex0), id(tex1), ...).  Safe because
        # TexturePool recycles GPUFrame objects (same Python object = same
        # texture), and write_buffer updates the uniform data in-place so
        # the cached bind group always reads the current value.
        self._bg_cache: OrderedDict = OrderedDict()

    def _get_sampler(self) -> wgpu.GPUSampler:
        if self._sampler is None:
            self._sampler = get_device().create_sampler(
                min_filter=wgpu.FilterMode.linear,
                mag_filter=wgpu.FilterMode.linear,
                mipmap_filter=wgpu.MipmapFilterMode.nearest,
                address_mode_u=wgpu.AddressMode.clamp_to_edge,
                address_mode_v=wgpu.AddressMode.clamp_to_edge,
            )
        return self._sampler

    def _get_bgl(self, tex_count: int) -> wgpu.GPUBindGroupLayout:
        """Return an explicit bind group layout for *tex_count* textures.

        Layout convention (all project shaders must follow this):
            binding 0  → uniform buffer  (64 × f32 = 256 bytes)
            binding 1  → texture_2d<f32> (first texture)
            binding 2  → sampler         (first texture sampler)
            binding 3  → texture_2d<f32> (second texture, if any)
            binding 4  → sampler         (second texture sampler)
            …

        Using an explicit layout instead of layout="auto" ensures that bindings
        declared in WGSL but not referenced in the shader body (e.g. the uniform
        in passthrough.wgsl) are still included in the bind group layout.
        """
        if tex_count in self._bgls:
            return self._bgls[tex_count]

        device = get_device()
        entries = [
            {
                "binding": 0,
                "visibility": wgpu.ShaderStage.VERTEX | wgpu.ShaderStage.FRAGMENT,
                "buffer": {"type": wgpu.BufferBindingType.uniform},
            }
        ]
        for i in range(tex_count):
            entries.append({
                "binding": 1 + i * 2,
                "visibility": wgpu.ShaderStage.FRAGMENT,
                "texture": {
                    "sample_type": wgpu.TextureSampleType.float,
                    "view_dimension": wgpu.TextureViewDimension.d2,
                    "multisampled": False,
                },
            })
            entries.append({
                "binding": 2 + i * 2,
                "visibility": wgpu.ShaderStage.FRAGMENT,
                "sampler": {"type": wgpu.SamplerBindingType.filtering},
            })
        bgl = device.create_bind_group_layout(entries=entries)
        self._bgls[tex_count] = bgl
        self._pip_layouts[tex_count] = device.create_pipeline_layout(
            bind_group_layouts=[bgl]
        )
        return bgl

    def _get_pipeline(self, wgsl_source: str, tex_count: int) -> wgpu.GPURenderPipeline:
        key = (wgsl_source, tex_count)
        if key in self._pipelines:
            self._pipelines.move_to_end(key)
            return self._pipelines[key]

        device = get_device()
        self._get_bgl(tex_count)  # ensure _pip_layouts[tex_count] is populated
        shader = device.create_shader_module(code=wgsl_source)
        pipeline = device.create_render_pipeline(
            layout=self._pip_layouts[tex_count],
            vertex={
                "module": shader,
                "entry_point": "vs_main",
            },
            primitive={
                "topology": wgpu.PrimitiveTopology.triangle_list,
                "front_face": wgpu.FrontFace.ccw,
                "cull_mode": wgpu.CullMode.none,
            },
            fragment={
                "module": shader,
                "entry_point": "fs_main",
                "targets": [{"format": _TARGET_FORMAT}],
            },
            depth_stencil=None,
            multisample=None,
        )

        self._pipelines[key] = pipeline
        logger.debug(f"Renderer: compiled WGSL pipeline ({len(self._pipelines)} cached)")

        if len(self._pipelines) > _LRU_LIMIT:
            self._pipelines.popitem(last=False)
            logger.debug(f"Renderer: LRU evicted oldest pipeline "
                         f"({len(self._pipelines)} remain)")

        return pipeline

    def render(
        self,
        wgsl_source: str = None,
        target=None,
        uniforms: dict = None,
        textures=None,
        encoder: 'wgpu.GPUCommandEncoder | None' = None,
        load_op=None,
        viewport: 'tuple | None' = None,
    ) -> None:
        """Run one shader pass.

        Parameters
        ----------
        wgsl_source : str
            Complete WGSL module (vertex + fragment).
        target : GPUFrame
            Render target (RENDER_ATTACHMENT texture).
        uniforms : dict
            {name: float | int | tuple} — packed into binding 0 uniform buffer.
        textures : list[GPUFrame] or dict {name: (unit, GPUFrame)}
            Textures in binding order (index 0 → binding 1, index 1 → binding 3, …).
        encoder : wgpu.GPUCommandEncoder | None
            Optional external command encoder.  If provided the render pass is
            recorded into it without submitting — caller must call
            ``device.queue.submit([encoder.finish()])``.  Use this to batch
            multiple render passes into one submission (saves one
            kernel-transition round-trip per pass on AMD Vulkan).
        load_op : wgpu.LoadOp or None
            LoadOp for the render pass colour attachment.  Defaults to
            ``wgpu.LoadOp.clear`` (black background).  Pass
            ``wgpu.LoadOp.load`` to preserve existing target contents (used
            by GPUCompositionRenderer to accumulate slice blits).
        viewport : tuple or None
            If set, ``(x, y, width, height, min_depth, max_depth)`` is applied
            to the render pass via ``set_viewport()``.  Restricts rasterisation
            to the given rectangle so the full-screen triangle only fills the
            target region (used for composition blit passes).
        """
        if wgsl_source is None or target is None:
            raise ValueError("render() requires wgsl_source and target")

        uniforms = uniforms or {}

        # Normalise textures: accept list or legacy dict {name: (unit, frame)}
        if textures is None:
            tex_list = []
        elif isinstance(textures, dict):
            # Sort by unit index (the int in the (unit, frame) tuple)
            tex_list = [frame for _, frame in sorted(textures.values(), key=lambda x: x[0])]
        else:
            tex_list = list(textures)

        device = get_device()
        tex_count = len(tex_list)
        pipeline = self._get_pipeline(wgsl_source, tex_count)
        bgl = self._get_bgl(tex_count)

        # --- uniform buffer ring ---
        # Lazy-init on first call.
        if not self._unif_ring:
            for _ in range(_UNIF_RING):
                self._unif_ring.append(device.create_buffer(
                    size=256,
                    usage=wgpu.BufferUsage.UNIFORM | wgpu.BufferUsage.COPY_DST,
                ))

        slot = self._unif_idx % _UNIF_RING
        self._unif_idx = (self._unif_idx + 1) % (_UNIF_RING * 65536)  # prevent overflow
        unifbuf = self._unif_ring[slot]

        uniform_data = _pack_uniforms(uniforms)
        # Skip write_buffer if data is byte-identical to the last write for
        # this slot (identity check first: _EMPTY_UNIFORMS is a singleton).
        if uniform_data is not self._unif_last[slot] and uniform_data != self._unif_last[slot]:
            device.queue.write_buffer(unifbuf, 0, uniform_data)
            self._unif_last[slot] = uniform_data

        # --- bind group (cached by unifbuf slot + texture object identity) ---
        sampler = self._get_sampler()
        bg_key = (id(unifbuf), tuple(id(tf) for tf in tex_list))
        if bg_key in self._bg_cache:
            self._bg_cache.move_to_end(bg_key)
            bind_group = self._bg_cache[bg_key]
        else:
            entries = [
                {
                    "binding": 0,
                    "resource": {"buffer": unifbuf, "offset": 0, "size": 256},
                }
            ]
            for i, tex_frame in enumerate(tex_list):
                entries.append({"binding": 1 + i * 2, "resource": tex_frame.view})
                entries.append({"binding": 2 + i * 2, "resource": sampler})
            bind_group = device.create_bind_group(layout=bgl, entries=entries)
            self._bg_cache[bg_key] = bind_group
            if len(self._bg_cache) > _BG_CACHE_LIMIT:
                self._bg_cache.popitem(last=False)

        # --- render pass ---
        own_encoder = encoder is None
        if own_encoder:
            encoder = device.create_command_encoder()

        pass_ = encoder.begin_render_pass(
            color_attachments=[
                {
                    "view": target.view,
                    "resolve_target": None,
                    "load_op": load_op if load_op is not None else wgpu.LoadOp.clear,
                    "store_op": wgpu.StoreOp.store,
                    "clear_value": (0.0, 0.0, 0.0, 1.0),
                }
            ]
        )
        pass_.set_pipeline(pipeline)
        pass_.set_bind_group(0, bind_group)
        if viewport is not None:
            pass_.set_viewport(*viewport)
        pass_.draw(3)   # full-screen triangle
        pass_.end()

        if own_encoder:
            device.queue.submit([encoder.finish()])

    def release(self) -> None:
        self._pipelines.clear()
        self._bgls.clear()
        self._pip_layouts.clear()
        self._bg_cache.clear()
        self._sampler = None
        for buf in self._unif_ring:
            try:
                buf.destroy()
            except Exception:
                pass
        self._unif_ring.clear()
        self._unif_last = [None] * _UNIF_RING
        self._unif_idx = 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_renderer: Renderer | None = None


def get_renderer() -> Renderer:
    global _renderer
    if _renderer is None:
        _renderer = Renderer()
        warmup_pipelines()   # kick off background compilation immediately
    return _renderer


def _reset_renderer() -> None:
    global _renderer, _warmup_thread
    _renderer = None
    _warmup_thread = None
    _warmup_done.clear()


def load_shader(filename: str) -> str:
    """Load a WGSL source file from src/modules/gpu/shaders/."""
    path = os.path.join(_SHADER_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


# ---------------------------------------------------------------------------
def _tc_from_source(wgsl_src: str) -> int:
    """Derive tex_count from the highest @binding(N) in a WGSL source.

    Layout convention: binding 0 = uniforms, then pairs (texture, sampler)
    at bindings 1+2, 3+4, 5+6, …  The sampler binding is always even so
    max_binding = 2 * tex_count.

    Generator shaders declare only binding 0 (uniform) → tex_count = 0.
    Effect shaders declare binding 1+ (textures) → tex_count ≥ 1.
    """
    nums = [int(x) for x in re.findall(r'@binding\((\d+)\)', wgsl_src)]
    if not nums:
        return 1
    max_b = max(nums)
    if max_b <= 0:
        return 0  # only uniform buffer (binding 0) — generator shader
    # Sampler of Nth texture is at binding 2N → tc = max_b // 2
    return max(1, max_b // 2)

# Background warm-up state
_warmup_thread: threading.Thread | None = None
_warmup_done = threading.Event()

# Optional callback to forward warmup messages to the web CLI console.
# Set via set_warmup_console_log_fn(fn) from main.py after rest_api is ready.
_console_log_fn: 'Callable[[str], None] | None' = None


def set_warmup_console_log_fn(fn) -> None:
    """Register a callback that receives GPU warmup status lines.

    Call this once from main.py after the REST API is started, passing
    ``rest_api.add_log`` so warmup messages appear in the web CLI console.
    """
    global _console_log_fn
    _console_log_fn = fn


def warmup_pipelines() -> None:
    """Pre-compile all WGSL shaders in the shaders/ directory in the background.

    Called once from get_renderer() after the Renderer singleton is first
    created.  Compilation runs on a daemon thread so the player thread is
    never blocked:

    * Each shader is compiled via ``create_render_pipeline_async`` so the
      wgpu-native worker threads can process multiple shaders concurrently
      (Vulkan driver may parallelize ISA generation across CPU cores).
    * The compiled pipelines are stored in the Renderer's LRU cache, so by
      the time the user first applies an effect the pipeline is already ready.
    * New plugin shaders are discovered automatically — any .wgsl file added
      to ``plugins/effects/`` or ``src/modules/gpu/shaders/`` is compiled.
    * ``warmup_done`` event is set when all shaders are compiled — callers
      that do care about completion can ``warmup_done.wait(timeout=...)``.
    """
    global _warmup_thread
    if _warmup_thread is not None:
        return  # already started

    def _run() -> None:
        renderer = get_renderer()
        # Collect WGSL sources from the built-in shaders directory.
        sources: list[tuple[str, int]] = []   # (wgsl_source, tex_count)
        for fname in os.listdir(_SHADER_DIR):
            if not fname.endswith('.wgsl'):
                continue
            try:
                src = load_shader(fname)
                if 'vs_main' not in src:
                    logger.debug('warmup_pipelines: skipping %s (no vs_main — compute shader)', fname)
                    continue
                tc = _tc_from_source(src)
                sources.append((src, tc))
            except Exception as exc:
                logger.debug('warmup_pipelines: skipping %s: %s', fname, exc)

        # Also scan plugins/effects/ for any .wgsl files defined there.
        plugins_shader_dir = os.path.normpath(
            os.path.join(_SHADER_DIR, '..', '..', '..', '..', 'plugins', 'effects')
        )
        if os.path.isdir(plugins_shader_dir):
            for fname in os.listdir(plugins_shader_dir):
                if not fname.endswith('.wgsl'):
                    continue
                try:
                    path = os.path.join(plugins_shader_dir, fname)
                    with open(path, 'r', encoding='utf-8') as fh:
                        src = fh.read()
                    if 'vs_main' not in src:
                        logger.debug('warmup_pipelines: skipping plugin %s (no vs_main)', fname)
                        continue
                    tc = _tc_from_source(src)
                    sources.append((src, tc))
                except Exception as exc:
                    logger.debug('warmup_pipelines: skipping plugin %s: %s', fname, exc)

        logger.info('GPU warm-up: compiling %d shaders in background …', len(sources))
        _msg_start = f'🔥 GPU: warming shader cache ({len(sources)} shaders) …'
        print(_msg_start, flush=True)
        if _console_log_fn:
            try:
                _console_log_fn(_msg_start)
            except Exception:
                pass

        # Use create_render_pipeline_async so the native back-end can exploit
        # multiple CPU cores for ISA generation.  We collect all coroutines
        # first (kicking off parallel compilation), then await them in order.
        import asyncio

        device = get_device()

        async def _compile_all():
            tasks = []
            for src, tc in sources:
                key = (src, tc)
                if key in renderer._pipelines:
                    continue   # already compiled (e.g. by a first frame)
                renderer._get_bgl(tc)   # ensure layout is ready
                shader = device.create_shader_module(code=src)
                coro = device.create_render_pipeline_async(
                    layout=renderer._pip_layouts[tc],
                    vertex={"module": shader, "entry_point": "vs_main"},
                    primitive={
                        "topology": wgpu.PrimitiveTopology.triangle_list,
                        "front_face": wgpu.FrontFace.ccw,
                        "cull_mode": wgpu.CullMode.none,
                    },
                    fragment={
                        "module": shader,
                        "entry_point": "fs_main",
                        "targets": [{"format": _TARGET_FORMAT}],
                    },
                    depth_stencil=None,
                    multisample=None,
                )
                tasks.append((key, coro))
            # return_exceptions=True: one failing shader never aborts the rest
            results = await asyncio.gather(*(coro for _, coro in tasks), return_exceptions=True)
            compiled = 0
            for (key, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning('warmup_pipelines: compile failed: %s', result)
                    continue
                renderer._pipelines[key] = result
                compiled += 1
            logger.info('GPU warm-up complete: %d/%d shaders compiled', compiled, len(tasks))
            _msg_done = f'✅ GPU: shader cache ready ({compiled}/{len(tasks)} compiled)'
            print(_msg_done, flush=True)
            if _console_log_fn:
                try:
                    _console_log_fn(_msg_done)
                except Exception:
                    pass

        asyncio.run(_compile_all())
        _warmup_done.set()

    _warmup_thread = threading.Thread(target=_run, name='GPUWarmup', daemon=True)
    _warmup_thread.start()


def warmup_done() -> threading.Event:
    """Return the Event that is set when background shader compilation finishes."""
    return _warmup_done
