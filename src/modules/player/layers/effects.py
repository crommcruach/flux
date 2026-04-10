"""
Layer Effects — GPU shader pipeline for per-layer clip effects.

Public functions (called from LayerManager):
    apply_layer_effects(mgr, layer, frame, player_name, stay_on_gpu)
    update_layer_effect_parameter(mgr, clip_id, effect_index, param_name, value, player_name)
    load_layer_effects_from_registry(mgr, layer, player_name)
    reload_all_layer_effects(mgr, player_name)

All functions receive the LayerManager instance as the first argument ``mgr``
so they can read shared state (canvas size, profiler, pools) without being
methods on the class.
"""
from __future__ import annotations
import numpy as np
from ...core.logger import get_logger, debug_transport

logger = get_logger(__name__)


def apply_layer_effects(mgr, layer, frame, player_name: str = "", stay_on_gpu: bool = False):
    """
    Apply all GPU-shader effects attached to *layer* to *frame*.

    Supports both numpy arrays and GPUFrames as input.  When the input is a
    GPUFrame the output is always a GPUFrame regardless of *stay_on_gpu*.

    Returns:
        numpy uint8 array  — when stay_on_gpu=False and input was numpy
        GPUFrame           — when stay_on_gpu=True OR input was GPUFrame
        None               — on GPU context error (only when GPUFrame expected)
    """
    from ...gpu import get_texture_pool, get_renderer, get_device

    _frame_is_gpu = hasattr(frame, 'texture')
    if _frame_is_gpu:
        h, w = frame.height, frame.width
    else:
        h, w = frame.shape[:2]

    enabled_effects = [e for e in layer.effects if e.get('enabled', True)]
    if not enabled_effects:
        if _frame_is_gpu:
            return frame
        if stay_on_gpu:
            _gf = get_texture_pool().acquire(w, h)
            _gf.upload(frame)
            return _gf
        return frame

    # Filter mathematical no-ops to avoid unnecessary GPU upload/download cycles.
    enabled_effects = [
        e for e in enabled_effects
        if not (hasattr(e['instance'], 'is_noop') and e['instance'].is_noop())
    ]
    if not enabled_effects:
        if _frame_is_gpu:
            return frame
        if stay_on_gpu:
            _gf = get_texture_pool().acquire(w, h)
            _gf.upload(frame)
            return _gf
        return frame

    has_gpu_effect = any(e['instance'].get_shader() is not None for e in enabled_effects)
    if not has_gpu_effect:
        plugin_ids = [e.get('id', 'unknown') for e in enabled_effects]
        logger.warning(
            f"⚠️  [{player_name}] Layer {layer.layer_id}: effects {plugin_ids} have no GPU "
            f"shader and were skipped. Migrate to get_shader() for GPU pipeline."
        )
        if _frame_is_gpu:
            return frame
        if stay_on_gpu:
            _gf = get_texture_pool().acquire(w, h)
            _gf.upload(frame)
            return _gf
        return frame

    # ── GPU chaining path ─────────────────────────────────────────────────────
    gpu_effects = [e for e in enabled_effects if e['instance'].get_shader() is not None]
    cpu_skipped = [e.get('id', 'unknown') for e in enabled_effects if e['instance'].get_shader() is None]
    if cpu_skipped:
        logger.warning(
            f"⚠️  [{player_name}] Layer {layer.layer_id}: effects {cpu_skipped} have no GPU "
            f"shader and were skipped in the GPU chain. Migrate to get_shader()."
        )

    try:
        pool = get_texture_pool()
        renderer = get_renderer()
    except Exception as _ctx_err:
        logger.error(f"❌ [{player_name}] GPU context unavailable: {_ctx_err}")
        return frame

    profiler = getattr(mgr, 'profiler', None)
    current_gpu = None
    try:
        if _frame_is_gpu:
            current_gpu = frame  # ownership transferred; caller already uploaded (source_upload stage)
        else:
            # Slave-layer path: frame arrives as numpy (no pre-upload in compositor).
            current_gpu = pool.acquire(w, h)
            current_gpu.upload(frame)

        device = get_device()
        batch_enc = device.create_command_encoder()

        for i, effect in enumerate(gpu_effects):
            instance = effect['instance']
            try:
                shader_src = instance.get_shader()
                if shader_src is not None:
                    dst_gpu = pool.acquire(w, h)
                    try:
                        stage_name = f'effects_shader_{effect.get("id", i)}'
                        if profiler:
                            with profiler.profile_stage(stage_name):
                                renderer.render(
                                    wgsl_source=shader_src,
                                    target=dst_gpu,
                                    uniforms=instance.get_uniforms(frame_w=w, frame_h=h),
                                    textures={'inputTexture': (0, current_gpu)},
                                    encoder=batch_enc,
                                )
                        else:
                            renderer.render(
                                wgsl_source=shader_src,
                                target=dst_gpu,
                                uniforms=instance.get_uniforms(frame_w=w, frame_h=h),
                                textures={'inputTexture': (0, current_gpu)},
                                encoder=batch_enc,
                            )
                        pool.release(current_gpu)
                        current_gpu = dst_gpu
                    except Exception:
                        pool.release(dst_gpu)
                        raise
                    continue
                plugin_id = effect.get('id', 'unknown')
                logger.warning(
                    f"⚠️  [{player_name}] Effect '{plugin_id}' has no get_shader() "
                    f"and was placed after a GPU effect — skipped (add a WGSL shader)."
                )
            except Exception as e:
                plugin_id = effect.get('id', 'unknown')
                logger.error(
                    f"❌ [{player_name}] Layer {layer.layer_id} effect {plugin_id} error: {e}"
                )

        device.queue.submit([batch_enc.finish()])

        if stay_on_gpu or _frame_is_gpu:
            result = current_gpu
            current_gpu = None  # prevent finally block from releasing it
            return result
        frame = current_gpu.download()
    except Exception as _gpu_err:
        logger.error(f"❌ [{player_name}] GPU effect pipeline error: {_gpu_err}")
        if stay_on_gpu or _frame_is_gpu:
            return None
    finally:
        if current_gpu is not None:
            pool.release(current_gpu)

    return frame


def update_layer_effect_parameter(mgr, clip_id: str, effect_index: int,
                                   param_name: str, value, player_name: str = "") -> bool:
    """
    Update a live effect plugin instance parameter on the layer whose clip_id matches.
    """
    with mgr._render_lock:
        layers_snap = list(mgr.layers)

    for layer in layers_snap:
        if layer.clip_id != clip_id:
            continue
        if not layer.effects or effect_index >= len(layer.effects):
            logger.warning(
                f"⚠️ [{player_name}] update_layer_effect_parameter: effect_index "
                f"{effect_index} out of range for layer {layer.layer_id} "
                f"(has {len(layer.effects)} effects)"
            )
            return False

        instance = layer.effects[effect_index].get('instance')
        if instance is None:
            logger.warning(
                f"⚠️ [{player_name}] update_layer_effect_parameter: no instance on "
                f"effect {effect_index} for layer {layer.layer_id}"
            )
            return False

        if hasattr(instance, 'update_parameter'):
            success = instance.update_parameter(param_name, value)
            logger.debug(
                f"🔧 [{player_name}] Layer {layer.layer_id} "
                f"effect[{effect_index}].{param_name} = {value} "
                f"→ {'OK' if success else 'FAILED'}"
            )
            return bool(success)
        else:
            logger.warning(
                f"⚠️ [{player_name}] Effect instance has no update_parameter method"
            )
            return False

    # No live layer for this clip_id — clip is in the registry but not currently
    # playing in this player.  This is normal: the registry write already persisted
    # the parameter; it will be loaded when the clip starts playing.
    # Return None (not False) so callers can distinguish 'not playing' from 'failed'.
    logger.debug(
        f"[{player_name}] update_layer_effect_parameter: "
        f"clip {clip_id[:8]}... has no live layer (not currently playing — registry write is sufficient)"
    )
    return None


def load_layer_effects_from_registry(mgr, layer, player_name: str = "") -> None:
    """Load layer effects from ClipRegistry and create plugin instances."""
    if not mgr.clip_registry or not layer.clip_id:
        return

    clip_data = mgr.clip_registry.get_clip(layer.clip_id)
    if not clip_data:
        return

    effects = clip_data.get('effects', [])
    if not effects:
        return

    layer.effects = []
    logger.debug(
        f"📦 [{player_name}] Loading {len(effects)} effects for "
        f"Layer {layer.layer_id} from registry"
    )
    for effect_config in effects:
        plugin_id = effect_config.get('plugin_id')
        params = effect_config.get('parameters', effect_config.get('params', {}))
        enabled = effect_config.get('enabled', True)

        logger.debug(f"   Loading plugin '{plugin_id}' with params: {params}")

        plugin_instance = mgr.plugin_manager.load_plugin(plugin_id, params)
        if not plugin_instance:
            logger.warning(
                f"⚠️ [{player_name}] Plugin '{plugin_id}' not found for "
                f"Layer {layer.layer_id}"
            )
            continue

        # Special handling for transport effect
        if plugin_id == 'transport' and hasattr(plugin_instance, '_initialize_state') and layer.source:
            has_saved_params = params and any(key != 'metadata' for key in params.keys())
            if not has_saved_params:
                plugin_instance._initialize_state(layer.source)
                debug_transport(
                    logger,
                    f"🎬 [{player_name}] Transport initialized from source for "
                    f"Layer {layer.layer_id}: out_point={plugin_instance.out_point}"
                )
            else:
                if hasattr(plugin_instance, '_frame_source'):
                    plugin_instance._frame_source = layer.source
                debug_transport(
                    logger,
                    f"🎬 [{player_name}] Transport restored from saved params for "
                    f"Layer {layer.layer_id}: position={plugin_instance.current_position}, "
                    f"out_point={plugin_instance.out_point}"
                )
            plugin_instance._needs_websocket_context = True

        try:
            effect_dict = {
                'id': plugin_id,
                'plugin_id': plugin_id,
                'instance': plugin_instance,
                'parameters': effect_config.get('parameters', params),
                'enabled': enabled,
            }
            layer.effects.append(effect_dict)
            logger.debug(
                f"   ✅ Added {plugin_id} instance [{id(plugin_instance)}] to layer effects "
                f"(index {len(layer.effects) - 1})"
            )
        except Exception as e:
            logger.error(
                f"❌ [{player_name}] Error loading effect '{plugin_id}' for "
                f"Layer {layer.layer_id}: {e}"
            )

    logger.debug(
        f"✅ [{player_name}] Loaded {len(layer.effects)} effects for Layer {layer.layer_id}"
    )


def reload_all_layer_effects(mgr, player_name: str = "") -> None:
    """Reload effects for all layers from ClipRegistry."""
    logger.debug(
        f"🔄 [{player_name}] Reloading all layer effects, layers={len(mgr.layers)}"
    )
    for layer in mgr.layers:
        if layer.clip_id:
            load_layer_effects_from_registry(mgr, layer, player_name)
    logger.debug(f"✅ [{player_name}] All layer effects reloaded")
