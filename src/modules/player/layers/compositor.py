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
from ...gpu.hap_texture import get_hap_texture_pool
from .slave import render_slave_layer

logger = get_logger(__name__)

# ─── Module-level lazy shader strings ────────────────────────────────────────
# Populated on first composite_layers() call (GPU context must exist first).
# Avoids repeated load_shader() dict lookups in the per-frame hot path.
_BLEND_SRC: str | None = None
_PASSTHROUGH_SRC: str | None = None
_SCALE_SRC: str | None = None


def _get_compositor_shaders() -> tuple[str, str, str]:
    """Return (blend_src, passthrough_src, scale_src), loading once on first call."""
    global _BLEND_SRC, _PASSTHROUGH_SRC, _SCALE_SRC
    if _BLEND_SRC is None:
        _BLEND_SRC = load_shader('blend.wgsl')
        _PASSTHROUGH_SRC = load_shader('passthrough.wgsl')
        _SCALE_SRC = load_shader('scale_mode.wgsl')
    return _BLEND_SRC, _PASSTHROUGH_SRC, _SCALE_SRC


# ─── Scale-rect result cache ──────────────────────────────────────────────────
# _compute_scale_rects() does floating-point division whose inputs (mode, frame
# size, canvas size) virtually never change between frames.  Cache the result
# so the common case is a single dict lookup.
_scale_rect_cache: dict[tuple, tuple] = {}

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
    if mgr._artnet_gpu_hook is not None:
        try:
            if profiler:
                with profiler.profile_stage('artnet_gpu_sampler'):
                    mgr._artnet_gpu_hook(master_frame)
            else:
                mgr._artnet_gpu_hook(master_frame)
        except Exception as e:
            logger.error(f'ArtNet GPU hook error: {e}')
    if mgr._output_gpu_hook is not None:
        try:
            mgr._output_gpu_hook(master_frame)
        except Exception as e:
            logger.debug('Output GPU hook error: %s', e)
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


# ─── Autosize scale-mode helper ──────────────────────────────────────────────

def _compute_scale_rects(mode: str, sw: int, sh: int, tw: int, th: int):
    """Compute (src_rect, dst_rect) UV tuples for a given autosize mode.

    Returns two (x0, y0, x1, y1) tuples in 0-1 UV space:
      src_rect — which portion of the *source* texture to sample
      dst_rect — where on the *canvas* to place the content (rest is black)

    Modes:
      'stretch' — full stretch, src=(0,0,1,1) dst=(0,0,1,1)
      'fit'     — letterbox / pillarbox, preserve aspect ratio
      'fill'    — crop to fill canvas, preserve aspect ratio
      'off'     — 1:1 pixel mapping centred, excess cropped / pad with black
    """
    _key = (mode, sw, sh, tw, th)
    _cached = _scale_rect_cache.get(_key)
    if _cached is not None:
        return _cached

    full = (0.0, 0.0, 1.0, 1.0)
    if mode == 'stretch':
        _scale_rect_cache[_key] = (full, full)
        return full, full

    ar_s = sw / sh
    ar_d = tw / th

    if mode == 'fit':
        if ar_s > ar_d:
            # Source wider than canvas → fit by width, black bars top/bottom
            dh = sh / sw * (tw / th)          # = sh*tw/(sw*th), always <= 1
            dy = (1.0 - dh) / 2.0
            _r = (full, (0.0, dy, 1.0, 1.0 - dy))
            _scale_rect_cache[_key] = _r
            return _r
        else:
            # Source taller/squarer → fit by height, black bars left/right
            dw = sw / sh * (th / tw)          # = sw*th/(sh*tw), always <= 1
            dx = (1.0 - dw) / 2.0
            _r = (full, (dx, 0.0, 1.0 - dx, 1.0))
            _scale_rect_cache[_key] = _r
            return _r

    if mode == 'fill':
        if ar_s > ar_d:
            # Source wider → scale to fill height, crop left/right of source
            cw = sw * th / sh                 # content width at canvas height
            cx0 = (cw - tw) / (2.0 * cw)     # source UV left crop
            _r = ((cx0, 0.0, 1.0 - cx0, 1.0), full)
            _scale_rect_cache[_key] = _r
            return _r
        else:
            # Source taller → scale to fill width, crop top/bottom of source
            ch = sh * tw / sw                 # content height at canvas width
            cy0 = (ch - th) / (2.0 * ch)     # source UV top crop
            _r = ((0.0, cy0, 1.0, 1.0 - cy0), full)
            _scale_rect_cache[_key] = _r
            return _r

    # mode == 'off' — 1:1 pixel, centred, excess cropped / padded with black
    dw = sw / tw    # > 1 if source wider than canvas
    dh = sh / th
    dx = (1.0 - dw) / 2.0  # negative when source > canvas
    dy = (1.0 - dh) / 2.0
    dst_x0 = max(0.0, dx)
    dst_y0 = max(0.0, dy)
    dst_x1 = min(1.0, 1.0 - dx)
    dst_y1 = min(1.0, 1.0 - dy)
    src_x0 = (dst_x0 - dx) / dw
    src_y0 = (dst_y0 - dy) / dh
    src_x1 = (dst_x1 - dx) / dw
    src_y1 = (dst_y1 - dy) / dh
    _r = ((src_x0, src_y0, src_x1, src_y1), (dst_x0, dst_y0, dst_x1, dst_y1))
    _scale_rect_cache[_key] = _r
    return _r


# ─── Global effect chain helper ─────────────────────────────────────────────

class _EffectsLayer:
    """Minimal duck-type for apply_layer_effects — avoids SimpleNamespace overhead."""
    __slots__ = ('effects', 'layer_id')


def _apply_chain_gpu(mgr, frame, effects, player_name):
    """Apply a player-global effect list to a GPUFrame on GPU.

    When GPU effects are actually applied the *input* frame is consumed
    (released to the pool) and a new GPUFrame is returned.  When there are no
    enabled GPU effects the input frame is returned unchanged (not consumed).
    Returns None on GPU error (input frame has been consumed in that case).
    """
    from .effects import apply_layer_effects as _afx
    pseudo = _EffectsLayer()
    pseudo.effects = effects
    pseudo.layer_id = 'global'
    return _afx(mgr, pseudo, frame, player_name, stay_on_gpu=True)


# ─── Main compositor ─────────────────────────────────────────────────────────

def composite_layers(mgr, preprocess_transport_callback, player_name: str = "Player",
                     needs_download: bool = True, global_effects=None):
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
    # Always clear regardless of _tap_configs so that tap frames from a
    # previous frame where taps were active are released even when taps
    # are subsequently disabled (e.g. after a clip switch stops Art-Net).
    mgr.tap_registry.clear()

    profiler = getattr(mgr, 'profiler', None)

    # ─── Layer 0 (master) ────────────────────────────────────────────────────
    if profiler:
        with profiler.profile_stage('transport_preprocess'):
            preprocess_transport_callback(layers_snap[0])
    else:
        preprocess_transport_callback(layers_snap[0])

    # When layer 0 is disabled, skip source decode and use a black GPU frame
    # as the base.  Slave layers still composite on top of it normally.
    _layer0_enabled = getattr(layers_snap[0], 'enabled', True)

    if not _layer0_enabled:
        master_frame = get_texture_pool().acquire(mgr.canvas_width, mgr.canvas_height)
        # pool.acquire() returns a texture cleared to black (rgba=0,0,0,1 from
        # the render pass clear_value in renderer.py) — no explicit fill needed.
        source_delay = 0.0
    else:
        if profiler:
            with profiler.profile_stage('source_decode'):
                master_frame, source_delay = layers_snap[0].source.get_next_frame()
        else:
            master_frame, source_delay = layers_snap[0].source.get_next_frame()

        if master_frame is None:
            # ── Layer duration mode ───────────────────────────────────────────────
            # 'master'   (default) — EOF on layer 0 ends the clip (existing behaviour)
            # 'longest'  — loop master until every slave has completed ≥ 1 pass
            # 'shortest' — master EOF always ends (slaves can also trigger early end)
            # 'layer_N'  — loop master until layer N has completed ≥ 1 pass
            duration_mode = getattr(mgr, 'layer_duration_mode', 'master')
            should_loop_master = False

            if duration_mode == 'longest':
                active_slaves_snap = [l for l in layers_snap[1:] if l.enabled and l.opacity > 0]
                if active_slaves_snap and not all(getattr(l, '_play_count', 0) >= 1 for l in active_slaves_snap):
                    should_loop_master = True   # some slaves not yet done → loop master
            elif duration_mode.startswith('layer_'):
                try:
                    target_layer_id = int(duration_mode.split('_', 1)[1])
                    target = next((l for l in layers_snap if l.layer_id == target_layer_id), None)
                    if target and getattr(target, '_play_count', 0) < 1:
                        should_loop_master = True
                except (ValueError, IndexError):
                    pass

            if should_loop_master:
                layers_snap[0].source.reset()
                if profiler:
                    with profiler.profile_stage('source_decode'):
                        master_frame, source_delay = layers_snap[0].source.get_next_frame()
                else:
                    master_frame, source_delay = layers_snap[0].source.get_next_frame()

            if master_frame is None:
                return None, source_delay

        # Upload frame to GPU immediately after decode, before any effects.
        # HAP path: DXT memoryview → BC1/BC3 texture → passthrough → rgba8unorm GPUFrame.
        # Numpy path: kept for GeneratorSource / DummySource (non-video sources).
        if isinstance(master_frame, memoryview):
            # Zero-copy HAP upload: no CPU decompression, hardware decompresses on sample.
            _src0 = layers_snap[0].source
            _hap_pool = get_hap_texture_pool()
            _hap_tex = _hap_pool.acquire(_src0.width, _src0.height, _src0.dxt_variant)
            _gf = get_texture_pool().acquire(_src0.width, _src0.height)
            if profiler:
                with profiler.profile_stage('source_upload'):
                    _hap_tex.upload(master_frame)
                    _hap_tex.decode_to(_gf, get_renderer())
            else:
                _hap_tex.upload(master_frame)
                _hap_tex.decode_to(_gf, get_renderer())
            _hap_pool.release(_hap_tex)
            master_frame = _gf
        elif isinstance(master_frame, np.ndarray):
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

        # ─── Autosize scale pass ──────────────────────────────────────────────────
        # Apply the player's autosize mode to scale the master frame to canvas size.
        # Skipped when the frame is already canvas-sized and mode is 'stretch'
        # (the default) to avoid an unnecessary GPU pass every frame.
        _autosize = getattr(mgr, 'autosize_mode', 'stretch')
        _cw, _ch = mgr.canvas_width, mgr.canvas_height
        _fw, _fh = master_frame.width, master_frame.height
        if _fw != _cw or _fh != _ch or _autosize not in ('stretch', None):
            _src_rect, _dst_rect = _compute_scale_rects(
                _autosize or 'stretch', _fw, _fh, _cw, _ch
            )
            _scale_out = get_texture_pool().acquire(_cw, _ch)
            _, _, _scale_src = _get_compositor_shaders()
            _do_scale = lambda: get_renderer().render(
                wgsl_source=_scale_src,
                target=_scale_out,
                uniforms={
                    'src_x0': _src_rect[0], 'src_y0': _src_rect[1],
                    'src_x1': _src_rect[2], 'src_y1': _src_rect[3],
                    'dst_x0': _dst_rect[0], 'dst_y0': _dst_rect[1],
                    'dst_x1': _dst_rect[2], 'dst_y1': _dst_rect[3],
                },
                textures=[master_frame],
            )
            if profiler:
                with profiler.profile_stage('autosize_scale'):
                    _do_scale()
            else:
                _do_scale()
            get_texture_pool().release(master_frame)
            master_frame = _scale_out

        if profiler:
            with profiler.profile_stage('clip_effects'):
                master_frame = _apply_effects(mgr, layers_snap[0], master_frame, player_name, stay_on_gpu=True)
        else:
            master_frame = _apply_effects(mgr, layers_snap[0], master_frame, player_name, stay_on_gpu=True)


    # ─── Single-layer fast path ───────────────────────────────────────────────
    if len(layers_snap) == 1:
        if master_frame is None:
            return None, source_delay
        if global_effects:
            _gef = _apply_chain_gpu(mgr, master_frame, global_effects, player_name)
            if _gef is None:
                return None, source_delay
            master_frame = _gef
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
    # Log once when a slave layer is excluded (opacity=0 or disabled), since
    # this silently prevents layer effects from running.
    _excluded = [
        (l.layer_id, f"opacity={l.opacity}", f"enabled={l.enabled}")
        for l in layers_snap[1:]
        if not (l.enabled and l.opacity > 0)
    ]
    if _excluded:
        _warn_key = f'_compositor_excluded_warn_{tuple(l.layer_id for l in layers_snap[1:])}'
        if not getattr(mgr, _warn_key, False):
            setattr(mgr, _warn_key, True)
            logger.warning(
                f"⚠️ [COMPOSITOR] [{getattr(mgr, 'player_name', '')}] "
                f"Layer(s) excluded from rendering: {_excluded} — "
                f"layer effects on these layers will NOT be applied"
            )
    if not active_slaves:
        if master_frame is None:
            return None, source_delay
        if global_effects:
            _gef = _apply_chain_gpu(mgr, master_frame, global_effects, player_name)
            if _gef is None:
                return None, source_delay
            master_frame = _gef
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
            profiler=profiler,
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

    # 'shortest' mode: end clip as soon as any slave completes its first pass
    _duration_mode = getattr(mgr, 'layer_duration_mode', 'master')
    if _duration_mode == 'shortest':
        if any(getattr(l, '_play_count', 0) >= 1 for l in active_slaves):
            get_texture_pool().release(master_frame)
            return None, source_delay

    if profiler:
        stage_cm = profiler.profile_stage('layer_composition')
        stage_cm.__enter__()

    cur = master_frame
    alt = None
    _deferred_releases = []  # textures to release AFTER blend_enc.finish()
    _slice_cur: dict = {}    # per-slice sub-compositor cur textures
    _slice_alt: dict = {}    # per-slice sub-compositor alt textures
    composite = None
    result = None

    try:
        # ── GPU compositing ───────────────────────────────────────────────────
        pool = get_texture_pool()
        renderer = get_renderer()
        blend_src, passthrough_src, _ = _get_compositor_shaders()
        canvas_w, canvas_h = mgr.canvas_width, mgr.canvas_height

        blend_enc = get_device().create_command_encoder()

        # ── Per-slice ping-pong pairs ─────────────────────────────────────────
        # Collect all slice IDs referenced by active layers this frame.
        # Allocate one ping-pong pair per slice; initialized transparently by
        # the pool (first frame uses empty-black baseline from pool.acquire()).
        for _sl in layers_snap[1:]:
            if not _sl.enabled or _sl.opacity <= 0:
                continue
            for _sid in getattr(_sl, 'output_slices', []):
                if _sid not in _slice_cur:
                    _slice_cur[_sid] = pool.acquire(canvas_w, canvas_h)
                    _slice_alt[_sid] = None

        if mgr._tap_configs:
            _fire_layer_processed_tap(mgr, layers_snap[0], cur, encoder=blend_enc)

        slave_blend_n = 0

        for layer in layers_snap[1:]:
            if not layer.enabled or layer.opacity <= 0:
                continue
            overlay = slave_frames.get(layer.layer_id)
            if overlay is None:
                continue

            # Slave returns GPUFrame (stay_on_gpu=True), HAP memoryview, or numpy fallback.
            slave_owns_tex = hasattr(overlay, 'texture')
            _hap_slave_tex = None  # track HAP-decoded GPUFrame for deferred release
            if slave_owns_tex:
                ov_h2, ov_w2 = overlay.height, overlay.width
            elif isinstance(overlay, memoryview):
                # HAP DXT frame from slave VideoSource — decode to rgba8unorm GPUFrame
                _sl = next((l for l in layers_snap if l.layer_id == layer.layer_id), None)
                if _sl is not None and hasattr(_sl.source, 'dxt_variant'):
                    _sl_src = _sl.source
                    _h_pool = get_hap_texture_pool()
                    _h_tex = _h_pool.acquire(_sl_src.width, _sl_src.height, _sl_src.dxt_variant)
                    _h_tex.upload(overlay)
                    overlay = pool.acquire(_sl_src.width, _sl_src.height)
                    _h_tex.decode_to(overlay, renderer)
                    _h_pool.release(_h_tex)
                    # Apply layer effects to the decoded GPUFrame.
                    # Effects were skipped in slave.py because HAP arrives as a
                    # memoryview; now that we have a real GPUFrame we can run the
                    # GPU shader chain (brightness_contrast, transform, etc.).
                    _fx_out = _apply_effects(mgr, layer, overlay, player_name, stay_on_gpu=True)
                    if _fx_out is not None and _fx_out is not overlay:
                        # Effects returned a new GPUFrame — release the intermediate
                        # decode target and track the new one for deferred release.
                        pool.release(overlay)
                        overlay = _fx_out
                    _hap_slave_tex = overlay  # remember to release after blend
                    slave_owns_tex = True
                    ov_h2, ov_w2 = overlay.height, overlay.width
                else:
                    continue  # cannot decode without source metadata
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
                    # Do NOT release overlay here — slave owns _slave_cached_frame's
                    # lifetime and will release it when fetching the next frame.
                    # Releasing it here would let the pool reuse it as 'alt' next
                    # frame while the slave still holds a reference to it.
                else:
                    src_tex = pool.acquire(ov_w2, ov_h2)
                    _deferred_releases.append(src_tex)
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
                    # Same size: copy slave's GPU texture to a pool-owned frame via
                    # passthrough (identical to the resize path above).
                    #
                    # Using overlay directly has two irreconcilable failure modes:
                    #   release_layer_tex=False → 1 pool slot leaked per throttle
                    #     frame; after ~16 frames the pool hits MAX_PER_BUCKET,
                    #     force-releases pool[0] (which may be cur), then the next
                    #     pool.acquire() returns the same slot as alt → blend pass
                    #     uses it as COLOR_TARGET while it is still cur's RESOURCE
                    #     → wgpu ValidationError (conflicting usages).
                    #   release_layer_tex=True → overlay is returned to the pool
                    #     after blend_enc.finish(); on the next throttled frame the
                    #     pool may reissue that same slot as alt while the slave
                    #     returns it unchanged as overlay → same conflict.
                    #
                    # The passthrough copy is pool-owned and safely deferred-released;
                    # the slave's texture is never touched by the compositor.
                    layer_tex = pool.acquire(canvas_w, canvas_h)
                    release_layer_tex = True
                    renderer.render(
                        wgsl_source=passthrough_src,
                        target=layer_tex,
                        uniforms={},
                        textures={'inputTexture': (0, overlay)},
                        encoder=blend_enc,
                    )
                else:
                    layer_tex = pool.acquire(canvas_w, canvas_h)
                    release_layer_tex = True
                    layer_tex.upload(ov3)
            try:
                if mgr._tap_configs:
                    _fire_layer_processed_tap(mgr, layer, layer_tex, encoder=blend_enc)

                blend_mode = BLEND_MODES.get(getattr(layer, 'blend_mode', 'normal'), 0)

                # ── Sub-compositor: blend layer_tex into each assigned slice ──
                _layer_slices = getattr(layer, 'output_slices', [])
                for _sid in _layer_slices:
                    if _sid not in _slice_cur:
                        continue  # slice appeared after allocation (race)
                    _s_cur = _slice_cur[_sid]
                    _s_alt = _slice_alt[_sid]
                    if _s_alt is None:
                        _s_alt = pool.acquire(canvas_w, canvas_h)
                    renderer.render(
                        wgsl_source=blend_src,
                        target=_s_alt,
                        uniforms={'opacity': layer.opacity / 100.0, 'mode': blend_mode},
                        textures={'base': (0, _s_cur), 'overlay': (1, layer_tex)},
                        encoder=blend_enc,
                    )
                    _slice_cur[_sid], _slice_alt[_sid] = _s_alt, _s_cur

                # ── Skip main composite when layer is bypass-only ─────────────
                _bypass = getattr(layer, 'bypass_main', False) and bool(_layer_slices)
                if not _bypass:
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
                        _fire_composite_after_n_tap(mgr, slave_blend_n, alt, encoder=blend_enc)
                    slave_blend_n += 1
                    cur, alt = alt, cur   # ping-pong: freshly-written becomes new source
            finally:
                if release_layer_tex:
                    # Defer release until after blend_enc.finish().
                    # Releasing now lets the pool re-issue this texture as a
                    # passthrough COLOR_TARGET in the next iteration while it is
                    # still recorded as RESOURCE in the current encoder → wgpu
                    # ValidationError (conflicting usages within usage scope).
                    _deferred_releases.append(layer_tex)
                if _hap_slave_tex is not None:
                    # HAP-decoded intermediate GPUFrame — not owned by the slave,
                    # must be returned to pool after the blend is submitted.
                    _deferred_releases.append(_hap_slave_tex)

        get_device().queue.submit([blend_enc.finish()])
        for _t in _deferred_releases:
            pool.release(_t)
        _deferred_releases.clear()

        # ── Fire slice sub-compositor hook ────────────────────────────────────
        if _slice_cur and mgr._output_layer_slice_hook is not None:
            try:
                mgr._output_layer_slice_hook(_slice_cur)
            except Exception as _e:
                logger.error('Layer-slice hook error: %s', _e)
        # Release slice ping-pong pairs
        for _tex in _slice_cur.values():
            pool.release(_tex)
        for _tex in _slice_alt.values():
            if _tex is not None:
                pool.release(_tex)
        _slice_cur.clear()
        _slice_alt.clear()

        if alt is not None:
            pool.release(alt)
            alt = None
        composite = cur
        cur = None  # composite owns the reference now

        # ── Player-global effects (Video FX / Art-Net FX panels) ─────────────
        if global_effects:
            _gef = _apply_chain_gpu(mgr, composite, global_effects, player_name)
            if _gef is None:
                composite = None
                return None, source_delay
            composite = _gef

        # ── Output hooks ──────────────────────────────────────────────────────
        if mgr._artnet_gpu_hook is not None:
            try:
                if profiler:
                    with profiler.profile_stage('artnet_gpu_sampler'):
                        mgr._artnet_gpu_hook(composite)
                else:
                    mgr._artnet_gpu_hook(composite)
            except Exception as e:
                logger.error(f"ArtNet GPU hook error: {e}")
        if mgr._output_gpu_hook is not None:
            try:
                mgr._output_gpu_hook(composite)
            except Exception as e:
                logger.debug('Output GPU hook error (multi-layer): %s', e)
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
        composite = None

    except Exception:
        # Ensure all in-flight GPU frames are returned to the pool so VRAM
        # doesn't accumulate when an exception aborts a frame mid-composite.
        _cleanup_pool = get_texture_pool()
        if cur is not None:
            _cleanup_pool.release(cur)
        if alt is not None:
            _cleanup_pool.release(alt)
        if composite is not None:
            _cleanup_pool.release(composite)
        for _t in _deferred_releases:
            _cleanup_pool.release(_t)
        # Release any slice ping-pong pairs allocated before the exception.
        for _tex in _slice_cur.values():
            _cleanup_pool.release(_tex)
        for _tex in _slice_alt.values():
            if _tex is not None:
                _cleanup_pool.release(_tex)
        # Also release any tap frames acquired inside blend_enc before the
        # exception.  These are tracked by tap_registry but NOT in
        # _deferred_releases, so they would otherwise stay in pool._in_use
        # until the NEXT frame's clear() — which may never fire if
        # _tap_configs is empty after a clip switch.
        mgr.tap_registry.clear()
        raise

    finally:
        if profiler:
            stage_cm.__exit__(None, None, None)

    return result, source_delay


# ─── Tap helpers (used inside this compositor) ────────────────────────────────

def _fire_layer_processed_tap(mgr, layer, gpu_frame, encoder=None) -> None:
    """Copy gpu_frame into a tap output.  encoder=blend_enc batches into main submit."""
    from ..taps import TapStage
    configs = [
        tc for tc in mgr._tap_configs
        if tc.stage == TapStage.LAYER_PROCESSED and tc.matches_layer(layer.layer_id)
    ]
    if not configs:
        return
    _, passthrough_src, _ = _get_compositor_shaders()
    pool = get_texture_pool()
    renderer = get_renderer()
    copy = pool.acquire(gpu_frame.width, gpu_frame.height)
    renderer.render(
        wgsl_source=passthrough_src,
        target=copy,
        uniforms={},
        textures={'inputTexture': (0, gpu_frame)},
        encoder=encoder,
    )
    for tc in configs:
        if tc.mode == 'separate':
            mgr.tap_registry.append_to_list(tc.tap_id, copy)
        else:
            mgr.tap_registry.register(tc.tap_id, copy)


def _fire_composite_after_n_tap(mgr, n: int, composite_gpu, encoder=None) -> None:
    """Copy composite into a tap output.  encoder=blend_enc batches into main submit."""
    from ..taps import TapStage
    configs = [
        tc for tc in mgr._tap_configs
        if tc.stage == TapStage.COMPOSITE_AFTER_N
        and (tc.composite_after_n is None or tc.composite_after_n == n)
    ]
    if not configs:
        return
    _, passthrough_src, _ = _get_compositor_shaders()
    pool = get_texture_pool()
    renderer = get_renderer()
    copy = pool.acquire(composite_gpu.width, composite_gpu.height)
    renderer.render(
        wgsl_source=passthrough_src,
        target=copy,
        uniforms={},
        textures={'inputTexture': (0, composite_gpu)},
        encoder=encoder,
    )
    for tc in configs:
        mgr.tap_registry.register(tc.tap_id, copy)
