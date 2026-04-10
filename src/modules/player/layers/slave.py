"""
Slave layer renderer — per-slave frame decode, effects, FPS rate-limiting.

Single public entry point:
    render_slave_layer(layer, preprocess_cb, apply_effects_fn,
                       get_texture_pool_fn, player_name, warned_layers_set)
        -> (layer_id, GPUFrame | numpy_frame | None)

Slave frames are returned as GPUFrames (stay_on_gpu=True in apply_effects_fn)
so the compositor blend loop can use them directly without re-uploading.
The CPU→GPU transfer is performed inside the slave thread (parallel with
other work) rather than blocking the main compositor thread.
"""
from __future__ import annotations
import time
import threading
import numpy as np
from ...core.logger import get_logger, debug_layers

logger = get_logger(__name__)


def render_slave_layer(
    layer,
    preprocess_callback,
    apply_effects_fn,
    get_texture_pool_fn,
    player_name: str = "",
    warned_layers_set: set | None = None,
):
    """
    Decode, effect-process, and FPS-rate-limit a single slave layer.

    Per-slave FPS throttle
    ----------------------
    Slaves are called once per *master* frame (master FPS).  If the slave clip
    has a lower FPS (e.g. 24 fps slave on 30 fps master) we MUST NOT advance its
    source every master frame — that would play it too fast.  Instead the last
    decoded frame is held until enough real time has elapsed for the slave's own
    frame interval.

    GPU generator GPUFrames
    -----------------------
    apply_effects_fn() may return a GPUFrame when the source is a GPU generator.
    Those are downloaded to numpy here (one GPU→CPU copy per slave-FPS advance)
    so the compositor blend loop always receives numpy arrays.

    Parameters
    ----------
    layer               Layer object (must have .source, .layer_id, .effects,
                        and the _slave_next_time / _slave_cached_frame attrs)
    preprocess_callback Called before fetching a new frame (e.g. transport effect)
    apply_effects_fn    Callable: apply_effects_fn(layer, frame, player_name)
    get_texture_pool_fn Callable returning the global TexturePool
    player_name         Used for log messages
    warned_layers_set   set for one-time "returned None after reset" warnings

    Returns
    -------
    (layer_id, GPUFrame | numpy_frame | None)
    """
    try:
        logger.debug(
            f"🧵 [THREAD:{threading.current_thread().name}] "
            f"rendering slave layer {layer.layer_id}"
        )

        now = time.perf_counter()
        slave_fps = getattr(layer.source, 'fps', 30.0) or 30.0
        slave_frame_interval = 1.0 / slave_fps

        if not hasattr(layer, '_slave_next_time'):
            layer._slave_next_time = now
            layer._slave_cached_frame = None

        if now >= layer._slave_next_time or layer._slave_cached_frame is None:
            # Time to advance — fetch a new frame.
            preprocess_callback(layer)
            overlay_frame, _ = layer.source.get_next_frame()

            if overlay_frame is None:
                debug_layers(
                    logger,
                    f"🔁 Layer {layer.layer_id} reached end, auto-reset (slave loop)"
                )
                layer.source.reset()
                overlay_frame, _ = layer.source.get_next_frame()

            if overlay_frame is None:
                source_info = getattr(
                    layer.source, 'video_path',
                    getattr(layer.source, 'generator_name', 'Unknown')
                )
                if warned_layers_set is not None and layer.layer_id not in warned_layers_set:
                    logger.warning(
                        f"⚠️ Layer {layer.layer_id} (source: {source_info}) "
                        f"returned None after reset, skipping"
                    )
                    warned_layers_set.add(layer.layer_id)
                return layer.layer_id, None

            overlay_frame = apply_effects_fn(layer, overlay_frame, player_name)

            # Fix A: strip alpha for numpy fallback so compositor skips the
            # np.ascontiguousarray copy on the main thread.
            if isinstance(overlay_frame, np.ndarray) and overlay_frame.ndim == 3 and overlay_frame.shape[2] == 4:
                overlay_frame = np.ascontiguousarray(overlay_frame[:, :, :3])

            # Release any previously cached GPUFrame before overwriting.
            if hasattr(layer._slave_cached_frame, 'texture'):
                get_texture_pool_fn().release(layer._slave_cached_frame)
            layer._slave_cached_frame = overlay_frame

            # Advance deadline by exactly one slave frame interval (drift-safe).
            layer._slave_next_time += slave_frame_interval
            # Guard: if we've fallen far behind, don't try to catch up.
            if layer._slave_next_time < now - slave_frame_interval:
                layer._slave_next_time = now + slave_frame_interval

        return layer.layer_id, layer._slave_cached_frame

    except Exception as e:
        logger.error(f"❌ Parallel slave render error (layer {layer.layer_id}): {e}")
        return layer.layer_id, None
