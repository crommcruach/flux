"""
Blend Compositor — GPU ping-pong blend pipeline for multi-layer compositing.

Public entry point:
    composite_layers(mgr, preprocess_transport_callback, player_name, needs_download)
        -> (result, source_delay)

Helpers (also called by LayerManager.__init__ to set up ring-buffer state):
    init_comp_ring(mgr, w, h)
    download_composite_ring(mgr, composite, w, h)

Hook setters are thin wrappers that stay on the LayerManager class itself
(see manager.py) so external callers can do ``layer_manager.set_preview_gpu_hook(cb)``
without importing this module.

Design
------
- Master layer (Layer 0): sequential decode + effects on the caller thread.
- Slave layers (1..N): decoded in parallel via the LayerManager thread pool,
  then composited on the GPU with a single command encoder per frame.
- Triple-buffer async download eliminates the ~45 ms synchronous map_sync.
- _GPU_PROCESSED sentinel is returned when needs_download=False to signal
  "successfully rendered on GPU, no CPU frame produced".
"""
from __future__ import annotations
import numpy as np
import cv2
from concurrent.futures import as_completed
from ...core.logger import get_logger
from ...gpu import get_texture_pool, get_renderer, load_shader, BLEND_MODES, get_device
from .slave import render_slave_layer

logger = get_logger(__name__)

# Sentinel: returned by composite_layers when needs_download=False.
# Distinguishes a GPU-only frame from an actual source EOF (None).
_GPU_PROCESSED = object()


# ─── Composite download ring ─────────────────────────────────────────────────

def init_comp_ring(mgr, w: int, h: int) -> None:
    """(Re-)allocate staging buffers for the async composite download ring."""
    import wgpu
    bpr = (w * 4 + 255) & ~255   # 256-byte row alignment
    for buf, _ in mgr._comp_ring:
        try:
            buf.destroy()
        except Exception:
            pass
    device = get_device()
    mgr._comp_ring = [
        (device.create_buffer(
            size=bpr * h,
            usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
        ), bpr)
        for _ in range(mgr._COMP_RING)
    ]
    mgr._comp_ring_submitted = [False] * mgr._COMP_RING
    mgr._comp_ring_w = w
    mgr._comp_ring_h = h


def download_composite_ring(mgr, composite, w: int, h: int) -> np.ndarray:
    """
    Triple-buffer async composite download.

    Submits copy composite → ring_staging[i] (non-blocking), then reads
    ring_staging[i-2] which the GPU finished two frames ago (near-zero stall).
    Falls back to composite.download() for the first two warm-up frames.
    """
    import wgpu

    if not mgr._comp_ring or mgr._comp_ring_w != w or mgr._comp_ring_h != h:
        init_comp_ring(mgr, w, h)

    i = mgr._comp_ring_idx
    buf, bpr = mgr._comp_ring[i]

    # Async copy: composite texture → staging[i]
    enc = get_device().create_command_encoder()
    enc.copy_texture_to_buffer(
        {"texture": composite.texture, "mip_level": 0, "origin": (0, 0, 0)},
        {"buffer": buf, "offset": 0, "bytes_per_row": bpr, "rows_per_image": h},
        (w, h, 1),
    )
    get_device().queue.submit([enc.finish()])
    mgr._comp_ring_submitted[i] = True

    # Read the slot from (COMP_RING-1) frames ago.
    read_i = (i - (mgr._COMP_RING - 1)) % mgr._COMP_RING
    result = None

    if mgr._comp_ring_submitted[read_i]:
        read_buf, read_bpr = mgr._comp_ring[read_i]
        try:
            read_buf.map_sync(wgpu.MapMode.READ)
            raw = read_buf.read_mapped()
            read_buf.unmap()
            padded = np.frombuffer(raw, dtype=np.uint8).reshape(h, read_bpr)
            rgba = np.ascontiguousarray(padded[:, : w * 4].reshape(h, w, 4))
            result = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
        except Exception as exc:
            logger.warning('Composite DL ring readback error (slot %d): %s', read_i, exc)
        finally:
            mgr._comp_ring_submitted[read_i] = False

    mgr._comp_ring_idx = (i + 1) % mgr._COMP_RING

    # Warm-up fallback: synchronous download for the first COMP_RING-1 frames.
    if result is None:
        result = composite.download()
    return result


# ─── GPU output hooks (single-layer & no-slave paths) ────────────────────────

def _fire_single_layer_hooks(mgr, master_frame, profiler):
    """Fire preview / display / transition hooks for single-layer or no-slave paths."""
    if mgr._preview_gpu_hook is not None:
        try:
            if profiler:
                with profiler.profile_stage('preview_encode'):
                    mgr._preview_gpu_hook(master_frame)
            else:
                mgr._preview_gpu_hook(master_frame)
        except Exception as e:
            logger.debug('Preview GPU hook error: %s', e)
    if mgr._display_gpu_hook is not None:
        try:
            mgr._display_gpu_hook(master_frame)
        except Exception as e:
            logger.debug('Display GPU hook error: %s', e)
    if mgr._transition_gpu_hook is not None:
        try:
            mgr._transition_gpu_hook(master_frame)
        except Exception as e:
            logger.debug('Transition GPU hook error: %s', e)


# ─── Main compositor ─────────────────────────────────────────────────────────

def composite_layers(mgr, preprocess_transport_callback, player_name: str = "Player",
                     needs_download: bool = True):
    """
    Composite all layers into a single frame using the GPU blend pipeline.

    CPU side  (parallel where possible):
      - Layer 0 (master): transport preprocess + source decode + clip effects — sequential
      - Slave layers 1..N: same steps in thread pool — parallel

    GPU side  (sequential; caller owns the GL context):
      - Upload each slave numpy frame to a pooled texture
      - Ping-pong blend with blend.wgsl across N slave layers
      - Conditional download (skipped when needs_download=False)

    Returns
    -------
    (np.ndarray BGR uint8, float source_delay)  — normal path
    (_GPU_PROCESSED, float source_delay)         — when needs_download=False
    (None, 0)                                    — on source EOF or empty stack
    """
    from .effects import apply_layer_effects as _apply_effects
    from ..taps import TapStage

    with mgr._render_lock:
        layers_snap = list(mgr.layers)

    if not layers_snap:
        return None, 0

    # Clear tap registry from previous frame.
    if mgr._tap_configs:
        mgr.tap_registry.clear()

    profiler = getattr(mgr, 'profiler', None)

    # ─── Layer 0 (master) ────────────────────────────────────────────────────
    if profiler:
        with profiler.profile_stage('transport_preprocess'):
            preprocess_transport_callback(layers_snap[0])
    else:
        preprocess_transport_callback(layers_snap[0])

    if profiler:
        with profiler.profile_stage('source_decode'):
            master_frame, source_delay = layers_snap[0].source.get_next_frame()
    else:
        master_frame, source_delay = layers_snap[0].source.get_next_frame()

    if master_frame is None:
        return None, source_delay

    # Upload numpy frame to GPU immediately after decode, before any effects.
    # This gives source_upload its own profiler slot and ensures clip_effects
    # only measures shader execution — not the PCIe/UMA bus transfer cost.
    if isinstance(master_frame, np.ndarray):
        _h, _w = master_frame.shape[:2]
        if profiler:
            with profiler.profile_stage('source_upload'):
                _gf = get_texture_pool().acquire(_w, _h)
                _gf.upload(master_frame)
                master_frame = _gf
        else:
            _gf = get_texture_pool().acquire(_w, _h)
            _gf.upload(master_frame)
            master_frame = _gf

    if profiler:
        with profiler.profile_stage('clip_effects'):
            master_frame = _apply_effects(mgr, layers_snap[0], master_frame, player_name, stay_on_gpu=True)
    else:
        master_frame = _apply_effects(mgr, layers_snap[0], master_frame, player_name, stay_on_gpu=True)

    # ─── Single-layer fast path ───────────────────────────────────────────────
    if len(layers_snap) == 1:
        if master_frame is None:
            return None, source_delay
        _fire_single_layer_hooks(mgr, master_frame, profiler)
        if needs_download:
            result = (
                profiler.profile_stage('composite_download')
                and master_frame.download()  # unreachable — profiler context below
            ) if False else None
            if profiler:
                with profiler.profile_stage('composite_download'):
                    result = master_frame.download()
            else:
                result = master_frame.download()
        else:
            result = _GPU_PROCESSED
        get_texture_pool().release(master_frame)
        return result, source_delay

    # ─── Slave layers: skip invisible ones early ──────────────────────────────
    active_slaves = [l for l in layers_snap[1:] if l.enabled and l.opacity > 0]
    if not active_slaves:
        if master_frame is None:
            return None, source_delay
        _fire_single_layer_hooks(mgr, master_frame, profiler)
        if needs_download:
            if profiler:
                with profiler.profile_stage('composite_download'):
                    result = master_frame.download()
            else:
                result = master_frame.download()
        else:
            result = _GPU_PROCESSED
        get_texture_pool().release(master_frame)
        return result, source_delay

    if master_frame is None:
        return None, source_delay

    # ─── Parallel slave decode + effects ─────────────────────────────────────
    if not hasattr(mgr, '_warned_layers'):
        mgr._warned_layers = set()

    def _slave_task(layer):
        return render_slave_layer(
            layer=layer,
            preprocess_callback=preprocess_transport_callback,
            apply_effects_fn=lambda l, f, pn: _apply_effects(mgr, l, f, pn, stay_on_gpu=True),
            get_texture_pool_fn=get_texture_pool,
            player_name=player_name,
            warned_layers_set=mgr._warned_layers,
        )

    futures_map = {
        mgr._render_pool.submit(_slave_task, layer): layer
        for layer in active_slaves
    }

    slave_frames: dict = {}
    try:
        for future in as_completed(futures_map, timeout=0.5):
            layer = futures_map[future]
            try:
                layer_id, overlay = future.result()
                slave_frames[layer_id] = overlay
            except Exception as e:
                logger.error(f"❌ Slave render future error (layer {layer.layer_id}): {e}")
    except TimeoutError:
        logger.error(
            "⚠️ Slave layer rendering timed out (0.5s) — compositing available frames only"
        )

    if profiler:
        stage_cm = profiler.profile_stage('layer_composition')
        stage_cm.__enter__()

    try:
        # ── GPU compositing ───────────────────────────────────────────────────
        pool = get_texture_pool()
        renderer = get_renderer()
        blend_src = load_shader('blend.wgsl')
        passthrough_src = load_shader('passthrough.wgsl')
        canvas_w, canvas_h = mgr.canvas_width, mgr.canvas_height

        cur = master_frame
        if mgr._tap_configs:
            _fire_layer_processed_tap(mgr, layers_snap[0], cur)

        slave_blend_n = 0
        alt = None          # spare buffer; allocated lazily on first blend

        _src_resize_textures = []
        blend_enc = get_device().create_command_encoder()

        for layer in layers_snap[1:]:
            if not layer.enabled or layer.opacity <= 0:
                continue
            overlay = slave_frames.get(layer.layer_id)
            if overlay is None:
                continue

            # Slave returns GPUFrame (stay_on_gpu=True) or numpy fallback.
            slave_owns_tex = hasattr(overlay, 'texture')
            if slave_owns_tex:
                ov_h2, ov_w2 = overlay.height, overlay.width
            else:
                # numpy fallback (e.g. GPU context error): alpha already stripped
                # by slave.py (Fix A); ensure contiguity.
                ov3 = overlay if overlay.flags['C_CONTIGUOUS'] else np.ascontiguousarray(overlay)
                ov_h2, ov_w2 = ov3.shape[:2]

            if ov_h2 != canvas_h or ov_w2 != canvas_w:
                # GPU resize: render to a canvas-sized target via passthrough.
                layer_tex = pool.acquire(canvas_w, canvas_h)
                release_layer_tex = True
                if slave_owns_tex:
                    # already on GPU — use directly as resize source (no upload)
                    renderer.render(
                        wgsl_source=passthrough_src,
                        target=layer_tex,
                        uniforms={},
                        textures={'inputTexture': (0, overlay)},
                        encoder=blend_enc,
                    )
                else:
                    src_tex = pool.acquire(ov_w2, ov_h2)
                    _src_resize_textures.append(src_tex)
                    src_tex.upload(ov3)
                    renderer.render(
                        wgsl_source=passthrough_src,
                        target=layer_tex,
                        uniforms={},
                        textures={'inputTexture': (0, src_tex)},
                        encoder=blend_enc,
                    )
            else:
                if slave_owns_tex:
                    # Same size: use GPUFrame directly — no acquire/upload needed.
                    layer_tex = overlay
                    release_layer_tex = False
                else:
                    layer_tex = pool.acquire(canvas_w, canvas_h)
                    release_layer_tex = True
                    layer_tex.upload(ov3)
            try:
                if mgr._tap_configs:
                    _fire_layer_processed_tap(mgr, layer, layer_tex)
                blend_mode = BLEND_MODES.get(getattr(layer, 'blend_mode', 'normal'), 0)
                if alt is None:
                    alt = pool.acquire(canvas_w, canvas_h)
                renderer.render(
                    wgsl_source=blend_src,
                    target=alt,
                    uniforms={'opacity': layer.opacity / 100.0, 'mode': blend_mode},
                    textures={'base': (0, cur), 'overlay': (1, layer_tex)},
                    encoder=blend_enc,
                )
                if mgr._tap_configs:
                    _fire_composite_after_n_tap(mgr, slave_blend_n, alt)
                slave_blend_n += 1
                cur, alt = alt, cur   # ping-pong: freshly-written becomes new source
            finally:
                if release_layer_tex:
                    pool.release(layer_tex)

        get_device().queue.submit([blend_enc.finish()])
        for _t in _src_resize_textures:
            pool.release(_t)

        if alt is not None:
            pool.release(alt)
        composite = cur

        # ── Output hooks ──────────────────────────────────────────────────────
        if mgr._artnet_gpu_hook is not None:
            try:
                mgr._artnet_gpu_hook(composite)
            except Exception as e:
                logger.error(f"ArtNet GPU hook error: {e}")
        if mgr._preview_gpu_hook is not None:
            try:
                mgr._preview_gpu_hook(composite)
            except Exception as e:
                logger.debug('Preview GPU hook error (multi-layer): %s', e)
        if mgr._display_gpu_hook is not None:
            try:
                mgr._display_gpu_hook(composite)
            except Exception as e:
                logger.debug('Display GPU hook error (multi-layer): %s', e)
        if mgr._transition_gpu_hook is not None:
            try:
                mgr._transition_gpu_hook(composite)
            except Exception as e:
                logger.debug('Transition GPU hook error (multi-layer): %s', e)

        # ── Conditional download ──────────────────────────────────────────────
        if needs_download:
            if profiler:
                with profiler.profile_stage('composite_download'):
                    result = download_composite_ring(mgr, composite, canvas_w, canvas_h)
            else:
                result = download_composite_ring(mgr, composite, canvas_w, canvas_h)
        else:
            result = _GPU_PROCESSED
        pool.release(composite)

    finally:
        if profiler:
            stage_cm.__exit__(None, None, None)

    return result, source_delay


# ─── Tap helpers (used inside this compositor) ────────────────────────────────

def _fire_layer_processed_tap(mgr, layer, gpu_frame) -> None:
    from ..taps import TapStage
    configs = [
        tc for tc in mgr._tap_configs
        if tc.stage == TapStage.LAYER_PROCESSED and tc.matches_layer(layer.layer_id)
    ]
    if not configs:
        return
    pool = get_texture_pool()
    renderer = get_renderer()
    passthrough_src = load_shader('passthrough.wgsl')
    copy = pool.acquire(gpu_frame.width, gpu_frame.height)
    renderer.render(
        wgsl_source=passthrough_src,
        target=copy,
        uniforms={},
        textures={'inputTexture': (0, gpu_frame)},
    )
    for tc in configs:
        if tc.mode == 'separate':
            mgr.tap_registry.append_to_list(tc.tap_id, copy)
        else:
            mgr.tap_registry.register(tc.tap_id, copy)


def _fire_composite_after_n_tap(mgr, n: int, composite_gpu) -> None:
    from ..taps import TapStage
    configs = [
        tc for tc in mgr._tap_configs
        if tc.stage == TapStage.COMPOSITE_AFTER_N
        and (tc.composite_after_n is None or tc.composite_after_n == n)
    ]
    if not configs:
        return
    pool = get_texture_pool()
    renderer = get_renderer()
    passthrough_src = load_shader('passthrough.wgsl')
    copy = pool.acquire(composite_gpu.width, composite_gpu.height)
    renderer.render(
        wgsl_source=passthrough_src,
        target=copy,
        uniforms={},
        textures={'inputTexture': (0, composite_gpu)},
    )
    for tc in configs:
        mgr.tap_registry.register(tc.tap_id, copy)
