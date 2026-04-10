"""
Layer Manager — Manages layer stack, blending, and layer effects.

This module is the **public face** of the layers package.
Heavy per-frame logic lives in dedicated sub-modules:

    effects.py     — apply_layer_effects, effect parameter helpers
    compositor.py  — GPU ping-pong blend pipeline, ring-buffer download
    slave.py       — per-slave FPS-throttled decode + effects

All routing is done through thin wrapper methods so external callers
continue to use the same API:::

    layer_manager.composite_layers(cb, player_name, needs_download)
    layer_manager.apply_layer_effects(layer, frame, ...)
    layer_manager.set_preview_gpu_hook(cb)
    ...etc.
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from ...core.logger import get_logger, debug_layers, debug_transport
from ..sources import VideoSource, GeneratorSource
import numpy as np
from ...gpu import get_texture_pool, probe_gpu_readback
from .layer import Layer
from ..taps import TapConfig, TapRegistry
from . import effects as _effects
from .compositor import composite_layers as _composite_layers, _GPU_PROCESSED

logger = get_logger(__name__)

class LayerManager:
    """Manages layer stack, blending, and layer effects."""
    
    def __init__(self, player_id, canvas_width, canvas_height, config, plugin_manager, clip_registry):
        """
        Initialize LayerManager.
        
        Args:
            player_id: Player identifier
            canvas_width: Canvas width
            canvas_height: Canvas height
            config: Configuration dict
            plugin_manager: PluginManager instance
            clip_registry: ClipRegistry instance
        """
        self.player_id = player_id
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.config = config
        self.plugin_manager = plugin_manager
        self.clip_registry = clip_registry
        
        self.layers = []  # List of Layer objects
        self.layer_counter = 0  # For generating unique layer IDs
        self._layer_effect_log_frame = {}  # Frame counter for logging
        self.player = None  # Will be set by player after initialization

        # ─── Phase 2: Thread pools for parallel loading and rendering ─────────
        # _render_lock protects self.layers list during swap and property updates
        self._render_lock = threading.RLock()
        # Parallel source initialization (I/O bound - GIL released during file open)
        self._load_pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix='LayerLoader')
        # Parallel slave-layer decode + effects (GIL released in cv2/numpy)
        self._render_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix='LayerRenderer')
        logger.info("🧵 LayerManager thread pools ready (load=8 workers, render=4 workers)")

        # ─── GPU readback viability probe (informational) ─────────────────────
        # Measures upload+readback latency at canvas resolution and logs it.
        # Result is stored but no longer gates any code path: with the
        # single-download architecture (GPU-chained effects + GPU compositor)
        # one readback per frame is unavoidable and acceptable.
        self._use_gpu = probe_gpu_readback(canvas_width, canvas_height)

        # ─── ArtNet GPU sampling hook ─────────────────────────────────────────
        # Optional callback fired inside composite_layers() while the final
        # composite GPUFrame is still live on the GPU.  ArtNetGPUSampler uses
        # a compute shader to sample only the N LED positions without a full
        # frame download.  Set via set_artnet_gpu_hook().
        self._artnet_gpu_hook = None

        # ─── Preview GPU hook ────────────────────────────────────────────────
        # Optional callback fired alongside _artnet_gpu_hook.  Used by the
        # PreviewDownscaler to blit composite → small FBO → SSBO download →
        # simplejpeg encode while the texture is still live.  This allows
        # needs_download=False for MJPEG-only consumers (~19 ms saved at 1080p).
        # Set via set_preview_gpu_hook().
        self._preview_gpu_hook = None

        # ─── Display GPU hook ────────────────────────────────────────────────
        # Optional callback fired alongside _preview_gpu_hook.  Used by the
        # GLFW display (GLFWDisplay) when WGL context sharing is active.
        # Blit composite → dedicated display texture → ctx.finish() →
        # signal GLFW thread.  Eliminates 26 ms SSBO download for display-only
        # use cases.  Set via set_display_gpu_hook().
        self._display_gpu_hook = None

        # ─── Transition GPU hook ─────────────────────────────────────────────
        # Optional callback fired with the composite GPUFrame before download.
        # Used by TransitionManager to store the "A" buffer GPU-to-GPU when the
        # render loop runs in GPU-only mode (needs_download=False), ensuring that
        # transitions have a frame ready to use even without a CPU download.
        # Set via set_transition_gpu_hook().
        self._transition_gpu_hook = None

        # ─── Tap system (spec §8) ────────────────────────────────────────────
        # Formal per-frame layer capture at defined pipeline stages.
        # register_tap() / unregister_tap() manage the config list.
        # tap_registry is cleared and repopulated every frame.
        self._tap_configs: list[TapConfig] = []
        self.tap_registry = TapRegistry()

        # ─── Composite download ring ───────────────────────────────────────
        # Triple-buffer async download of the final composite frame.
        # Eliminates the ~45 ms synchronous map_sync on the player thread:
        # copy composite → staging[i] (async), read staging[i-2] (done).
        # Only active when needs_download=True (CPU consumer present).
        _COMP_RING = 3
        self._comp_ring: list = []                      # [(GPUBuffer, bpr)]
        self._comp_ring_idx: int = 0
        self._comp_ring_submitted: list[bool] = [False] * _COMP_RING
        self._comp_ring_w: int = 0
        self._comp_ring_h: int = 0
        self._COMP_RING: int = _COMP_RING

        
    def _set_websocket_context_on_transport(self, clip_id, player_name=""):
        """Set WebSocket context on all transport effects in layers."""
        logger.debug(f"🎯 [{player_name}] _set_websocket_context_on_transport called with clip_id={clip_id}")
        
        if not self.player or not hasattr(self.player, 'player_manager'):
            logger.warning(f"⚠️ [{player_name}] Cannot set WebSocket context: player or player_manager not available")
            return
        
        if not hasattr(self.player.player_manager, 'socketio'):
            logger.warning(f"⚠️ [{player_name}] Cannot set WebSocket context: socketio not available on player_manager")
            return
        
        socketio = self.player.player_manager.socketio
        player_id = self.player_id
        
        transport_found = False
        for layer_idx, layer in enumerate(self.layers):
            logger.debug(f"🔍 [{player_name}] Checking layer {layer_idx}, has {len(layer.effects) if layer.effects else 0} effects")
            for effect_idx, effect in enumerate(layer.effects):
                effect_id = effect.get('id', effect.get('plugin_id', 'unknown'))
                logger.debug(f"🔍 [{player_name}]   Effect {effect_idx}: id={effect_id}, has_instance={effect.get('instance') is not None}")
                if effect.get('id') == 'transport' and effect.get('instance'):
                    transport = effect['instance']
                    transport.socketio = socketio
                    transport.player_id = player_id
                    # IMPORTANT: Use layer's own clip_id, not parent clip_id
                    # This ensures each layer's transport sends updates with its own unique ID
                    layer_clip_id = getattr(layer, 'clip_id', clip_id)
                    transport.clip_id = layer_clip_id
                    transport_found = True
                    logger.debug(f"📡 [{player_name}] Set WebSocket context on transport: layer={layer_idx}, player_id={player_id}, layer_clip_id={layer_clip_id}, socketio={socketio is not None}")
        
        if not transport_found:
            logger.warning(f"⚠️ [{player_name}] No transport effect found in {len(self.layers)} layers to set WebSocket context")
        
    def load_clip_layers(self, clip_id, video_dir=None, player_name="", sequence_manager=None):
        """
        Load all layers from clip definition and create FrameSources.
        Replaces current layer stack.
        
        Args:
            clip_id: Clip UUID from ClipRegistry
            video_dir: Base directory for resolving relative video paths
            player_name: Name for logging
            sequence_manager: SequenceManager for loading sequences (NEW ARCHITECTURE)
        
        Returns:
            bool: True on success
        """
        # Unload sequences for old clip if we had one
        if sequence_manager and hasattr(self, '_current_clip_id') and self._current_clip_id:
            sequence_manager.unload_sequences_for_clip(self._current_clip_id)
        
        # Get clip data
        clip_data = self.clip_registry.get_clip(clip_id)
        if not clip_data:
            logger.error(f"❌ [{player_name}] Clip {clip_id} not found")
            return False
        
        # Get layer definitions
        layer_defs = clip_data.get('layers', [])

        # Resolve player_name once (original code reassigned the parameter mid-loop)
        resolved_player_name = self.player.player_name if self.player and hasattr(self.player, 'player_name') else (player_name or 'video')

        abs_path = clip_data['absolute_path']
        video_extensions = tuple(self.config.get('extensions', ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.gif']))

        # Resolve relative base path against video_dir when the direct check fails.
        # This handles clips whose absolute_path was stored without the video_dir
        # prefix (e.g. "test1" instead of "video/test1").
        if video_dir and not os.path.isabs(abs_path) and not abs_path.startswith('generator:'):
            if not (abs_path.endswith(video_extensions) or os.path.isdir(abs_path)):
                maybe = os.path.join(video_dir, abs_path)
                if os.path.isdir(maybe) or maybe.endswith(video_extensions):
                    abs_path = maybe

        # ─── PHASE 1: Create all source objects (fast, sequential) ───────────
        # Each item: (kind, source_or_none, layer_def_or_none)
        pending = []

        # Base source (Layer 0)
        base_source = None
        if abs_path.endswith(video_extensions) or os.path.isdir(abs_path):
            base_source = VideoSource(abs_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height,
                                      config=self.config, clip_id=clip_id, player_name=resolved_player_name)
        elif abs_path.startswith('generator:'):
            gen_id = abs_path.replace('generator:', '')
            metadata = clip_data.get('metadata', {})
            gen_params = metadata.get('parameters', metadata.get('generator_params', {}))
            base_source = GeneratorSource(gen_id, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)

        pending.append(('base', base_source, None))

        # Additional layer sources
        for layer_def in layer_defs:
            source_type = layer_def.get('source_type')
            source_path = layer_def.get('source_path')
            source = None
            if source_type == 'video':
                video_path = source_path
                if video_dir and not os.path.isabs(video_path):
                    video_path = os.path.join(video_dir, video_path)
                source = VideoSource(video_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height,
                                     config=self.config, player_name=resolved_player_name)
            elif source_type == 'generator':
                gen_params = layer_def.get('parameters', {})
                source = GeneratorSource(source_path, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
            pending.append(('layer', source, layer_def))

        # ─── PHASE 2: Initialize all sources in parallel (I/O bound) ─────────
        # cv2.VideoCapture / file open releases GIL → real multi-core parallelism
        def _init_source(item):
            _, source, _ = item
            if source is None:
                return False
            try:
                result = source.initialize()
                logger.debug(f"🧵 [THREAD:{threading.current_thread().name}] source initialized: {getattr(source, 'video_path', getattr(source, 'generator_id', '?'))}")
                return result
            except Exception as e:
                logger.error(f"❌ Source initialization error: {e}")
                return False

        if len(pending) > 1:
            futures = [self._load_pool.submit(_init_source, item) for item in pending]
            init_results = []
            for f in futures:
                try:
                    init_results.append(f.result(timeout=30.0))
                except Exception as e:
                    logger.error(f"❌ Source init future error: {e}")
                    init_results.append(False)
            logger.debug(f"✅ [{resolved_player_name}] Initialized {sum(init_results)}/{len(pending)} sources in parallel")
        else:
            init_results = [_init_source(pending[0])]

        # ─── PHASE 3: Build layer objects from results (sequential) ──────────
        new_layers = []
        layer_counter = 0

        for i, (kind, source, layer_def) in enumerate(pending):
            ok = init_results[i]

            if kind == 'base':
                if not ok:
                    logger.error(f"❌ [{resolved_player_name}] Failed to create base layer for clip {clip_id}")
                    return False
                base_layer = Layer(layer_counter, source, 'normal', 100.0, clip_id)
                new_layers.append(base_layer)
                layer_counter += 1
                logger.debug(f"✅ [{resolved_player_name}] Created clip {clip_id} as Layer 0 (base)")
                self.load_layer_effects_from_registry(base_layer, resolved_player_name)

            else:  # 'layer'
                blend_mode = layer_def.get('blend_mode', 'normal')
                opacity = layer_def.get('opacity', 1.0) * 100
                enabled = layer_def.get('enabled', True)
                layer_id = layer_def.get('layer_id', layer_counter)
                source_path = layer_def.get('source_path')

                if not ok:
                    source_type = layer_def.get('source_type')
                    logger.warning(f"⚠️ [{resolved_player_name}] Failed to create layer source: {source_type}:{source_path}")
                    continue

                layer_clip_id = layer_def.get('clip_id')
                if not layer_clip_id and self.clip_registry:
                    # Compute full path with video_dir so the registry entry is
                    # resolvable later (PHASE 1 uses the same expansion).
                    abs_layer_path = source_path
                    if source_type == 'video' and video_dir and not os.path.isabs(source_path):
                        abs_layer_path = os.path.join(video_dir, source_path)
                    layer_clip_id = self.clip_registry.register_clip(
                        player_id=self.player_id,
                        absolute_path=abs_layer_path,
                        relative_path=source_path,
                        metadata={
                            'type': 'layer',
                            'layer_of': clip_id,
                            'layer_id': layer_id,
                            'blend_mode': blend_mode,
                            'opacity': opacity
                        }
                    )
                    self.clip_registry.update_clip_layer(clip_id, layer_id, {'clip_id': layer_clip_id})
                    logger.debug(f"📐 Layer {layer_id} registered as clip during load: {layer_clip_id}")

                new_layer = Layer(layer_id, source, blend_mode, opacity, layer_clip_id)
                new_layer.enabled = enabled
                new_layers.append(new_layer)
                logger.debug(f"📐 Layer {layer_id} loaded: opacity={opacity}%, blend={blend_mode}, enabled={enabled}")

                if layer_clip_id:
                    self.load_layer_effects_from_registry(new_layer, resolved_player_name)

                layer_counter = layer_id + 1

        # Atomically swap layer stack (protected by render lock)
        with self._render_lock:
            old_layers = self.layers
            self.layers = new_layers
            self.layer_counter = layer_counter

        # Cleanup old layers after swap
        for layer in old_layers:
            try:
                layer.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up old layer: {e}")

        # Update player_name for downstream calls (match original behaviour)
        player_name = resolved_player_name
        
        # Set WebSocket context on transport effects (needs player reference)
        self._set_websocket_context_on_transport(clip_id, player_name)
        
        # Store current clip_id for unloading sequences later
        self._current_clip_id = clip_id
        
        # Load sequences from clip (NEW ARCHITECTURE)
        if sequence_manager:
            loaded_seq_count = sequence_manager.load_sequences_from_clip(clip_id)
            logger.debug(f"📊 [{player_name}] Loaded {loaded_seq_count} sequences for clip {clip_id[:8]}...")
        
        logger.debug(f"✅ [{player_name}] Loaded {len(self.layers)} layers from clip {clip_id}")
        return True
    
    def add_layer(self, source, clip_id=None, blend_mode='normal', opacity=100.0, player_name=""):
        """
        Add new layer to stack.
        
        Args:
            source: FrameSource instance
            clip_id: Base Clip UUID (layer belongs to this clip)
            blend_mode: Blend mode
            opacity: Layer opacity 0-100%
            player_name: Name for logging
        
        Returns:
            int: Layer ID of new layer
        """
        layer_id = self.layer_counter
        self.layer_counter += 1
        
        # Register layer as clip in ClipRegistry
        layer_clip_id = None
        if self.clip_registry and clip_id:
            # Determine source path for registration
            source_path = ""
            source_type = "video"
            if hasattr(source, 'video_path'):
                source_path = source.video_path
                source_type = "video"
            elif hasattr(source, 'generator_id'):
                source_path = f"generator:{source.generator_id}"
                source_type = "generator"
            
            # Register layer as clip with metadata
            layer_clip_id = self.clip_registry.register_clip(
                player_id=self.player_id,
                absolute_path=source_path,
                relative_path=source_path,
                metadata={
                    'type': 'layer',
                    'layer_of': clip_id,
                    'layer_id': layer_id,
                    'blend_mode': blend_mode,
                    'opacity': opacity
                }
            )
            logger.debug(f"📐 Layer {layer_id} registered as clip: {layer_clip_id}")
            
            # Add layer config to base clip's layers array (persist for save/restore)
            layer_config = {
                'source_type': source_type,
                'source_path': source_path,
                'blend_mode': blend_mode,
                'opacity': opacity / 100.0,  # Convert to 0-1 range for storage
                'enabled': True,
                'layer_id': layer_id,
                'clip_id': layer_clip_id
            }
            self.clip_registry.add_layer_to_clip(clip_id, layer_config)
            logger.debug(f"💾 Layer {layer_id} added to clip {clip_id} registry for persistence")
        
        # Create layer with clip_id
        layer = Layer(layer_id, source, blend_mode, opacity, layer_clip_id)
        self.layers.append(layer)
        
        # Load effects from registry if layer has clip_id
        if layer_clip_id:
            self.load_layer_effects_from_registry(layer, player_name)
        
        logger.debug(
            f"✅ [{player_name}] Layer {layer_id} added: {source.get_source_name()} "
            f"(blend={blend_mode}, opacity={opacity}%, clip_id={layer_clip_id})"
        )
        
        return layer_id
    
    def remove_layer(self, layer_id, player_name=""):
        """
        Remove layer from stack.
        
        Args:
            layer_id: Layer ID to remove
            player_name: Name for logging
        
        Returns:
            bool: True on success, False if layer not found
        """
        for i, layer in enumerate(self.layers):
            if layer.layer_id == layer_id:
                # Cleanup layer resources
                layer.cleanup()
                
                # Remove from list
                del self.layers[i]
                
                logger.debug(f"🗑️ [{player_name}] Layer {layer_id} removed")
                return True
        
        logger.warning(f"⚠️ [{player_name}] Layer {layer_id} not found")
        return False
    
    def get_layer(self, layer_id):
        """
        Get layer by ID.
        
        Args:
            layer_id: Layer ID
        
        Returns:
            Layer or None if not found
        """
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer
        return None
    
    def reorder_layers(self, new_order, player_name=""):
        """
        Change layer order.
        
        Args:
            new_order: List of layer IDs in new order
            player_name: Name for logging
        
        Returns:
            bool: True on success
        """
        # Create mapping layer_id → Layer
        layer_map = {layer.layer_id: layer for layer in self.layers}
        
        # Check if all IDs exist
        if not all(lid in layer_map for lid in new_order):
            logger.error(f"❌ [{player_name}] Invalid layer IDs in new_order")
            return False
        
        # Set new order
        self.layers = [layer_map[lid] for lid in new_order]
        
        logger.debug(f"🔄 [{player_name}] Layers reordered: {new_order}")
        return True
    
    def update_layer_config(self, layer_id, blend_mode=None, opacity=None, enabled=None, player_name=""):
        """
        Update layer configuration at runtime.

        Thread-safe: property mutations are protected by _render_lock so they
        cannot race with composite_layers() reading the same attributes.
        Changes take effect on the NEXT frame (imperceptible at 60fps).

        Args:
            layer_id: Layer ID
            blend_mode: Optional new blend mode
            opacity: Optional new opacity
            enabled: Optional enabled status
            player_name: Name for logging

        Returns:
            bool: True on success
        """
        with self._render_lock:
            layer = self.get_layer(layer_id)
            if not layer:
                return False

            if blend_mode is not None:
                layer.blend_mode = blend_mode
                logger.debug(f"🔧 [{player_name}] Layer {layer_id} blend_mode → {blend_mode}")

            if opacity is not None:
                layer.opacity = opacity
                logger.debug(f"🔧 [{player_name}] Layer {layer_id} opacity → {opacity}%")

            if enabled is not None:
                layer.enabled = enabled
                status = "enabled" if enabled else "disabled"
                logger.debug(f"🔧 [{player_name}] Layer {layer_id} → {status}")

            # Capture for registry persistence (outside lock below)
            layer_clip_id = layer.clip_id

        # Persist changes to clip_registry (outside lock - may be slow I/O)
        if self.clip_registry and layer_clip_id:
            clip_data = self.clip_registry.get_clip(layer_clip_id)
            if clip_data:
                # Get the base clip this layer belongs to
                layer_of = clip_data.get('metadata', {}).get('layer_of')
                if layer_of:
                    # Build update dict with only changed values
                    update_data = {}
                    if blend_mode is not None:
                        update_data['blend_mode'] = blend_mode
                    if opacity is not None:
                        update_data['opacity'] = opacity / 100.0  # Convert to 0-1 range for storage
                    if enabled is not None:
                        update_data['enabled'] = enabled
                    
                    # Update the layer config in the base clip's layers array
                    if update_data:
                        self.clip_registry.update_clip_layer(layer_of, layer_id, update_data)
                        logger.debug(f"💾 [{player_name}] Layer {layer_id} config persisted to registry")
        
        return True
    
    # ──────────────────────────────────────────────────────────────────────────
    # Effects — delegate to layers/effects.py
    # ──────────────────────────────────────────────────────────────────────────

    def apply_layer_effects(self, layer, frame, player_name="", stay_on_gpu=False):
        """Apply GPU-shader effects to *frame*.  See layers/effects.py."""
        return _effects.apply_layer_effects(self, layer, frame, player_name, stay_on_gpu)

    def update_layer_effect_parameter(self, clip_id, effect_index, param_name, value, player_name=""):
        """Update a live effect param on the matching layer.  See layers/effects.py."""
        return _effects.update_layer_effect_parameter(self, clip_id, effect_index, param_name, value, player_name)

    def load_layer_effects_from_registry(self, layer, player_name=""):
        """Load effect plugin instances from ClipRegistry into *layer*.  See layers/effects.py."""
        _effects.load_layer_effects_from_registry(self, layer, player_name)

    def reload_all_layer_effects(self, player_name=""):
        """Reload effects for all layers from ClipRegistry.  See layers/effects.py."""
        _effects.reload_all_layer_effects(self, player_name)

    # ──────────────────────────────────────────────────────────────────────────
    # Compositor — delegate to layers/compositor.py
    # ──────────────────────────────────────────────────────────────────────────

    def composite_layers(self, preprocess_transport_callback, player_name="Player",
                         needs_download: bool = True):
        """GPU ping-pong blend pipeline.  See layers/compositor.py."""
        from .compositor import composite_layers as _cl
        return _cl(self, preprocess_transport_callback, player_name, needs_download)

    def _init_comp_ring(self, w: int, h: int) -> None:
        """(Re-)allocate staging buffers.  See layers/compositor.py."""
        from .compositor import init_comp_ring
        init_comp_ring(self, w, h)

    def _download_composite_ring(self, composite, w: int, h: int):
        """Triple-buffer async composite download.  See layers/compositor.py."""
        from .compositor import download_composite_ring
        return download_composite_ring(self, composite, w, h)

    def _fire_layer_processed_tap(self, layer, gpu_frame) -> None:
        """Fire per-layer tap callbacks.  See layers/compositor.py."""
        from .compositor import _fire_layer_processed_tap
        _fire_layer_processed_tap(self, layer, gpu_frame)

    def _fire_composite_after_n_tap(self, n: int, composite_gpu) -> None:
        """Fire composite-after-N tap callbacks.  See layers/compositor.py."""
        from .compositor import _fire_composite_after_n_tap
        _fire_composite_after_n_tap(self, n, composite_gpu)

    def set_artnet_gpu_hook(self, callback) -> None:
        """
        Register a callback that receives the final composite GPUFrame before
        it is downloaded to CPU.  Used by ArtNetGPUSampler to sample LED pixel
        positions directly from GPU texture via a compute shader.

        Pass None to disable.
        """
        self._artnet_gpu_hook = callback

    def set_preview_gpu_hook(self, callback) -> None:
        """
        Register a callback that receives the final composite GPUFrame before
        it is downloaded to CPU.  Used by PreviewDownscaler to produce a small
        JPEG-encoded preview without a full-resolution SSBO download.

        Pass None to disable.
        """
        self._preview_gpu_hook = callback

    def set_display_gpu_hook(self, callback) -> None:
        """
        Register a callback that receives the final composite GPUFrame for
        zero-copy display via WGL context sharing.

        The callback is called from the render thread while the GL context is
        current.  It should:
          1. Blit composite → dedicated display texture (main context).
          2. Call ctx.finish() so GPU writes are complete.
          3. Call glfw_display.push_gpu_frame(glo, w, h).

        This eliminates the 26 ms SSBO download when only display outputs are
        active (no Art-Net, no recording).

        Pass None to disable.
        """
        self._display_gpu_hook = callback

    def set_transition_gpu_hook(self, callback) -> None:
        """
        Register a callback that receives the final composite GPUFrame before
        it is downloaded to CPU.  Used by TransitionManager to store the "A"
        buffer GPU-to-GPU when the render loop runs in GPU-only mode.

        Pass None to disable.
        """
        self._transition_gpu_hook = callback

    # ─── Tap API (spec §8) ────────────────────────────────────────────────────

    def register_tap(self, config: TapConfig) -> None:
        """Register a tap. Replaces any existing tap with the same tap_id."""
        self._tap_configs = [tc for tc in self._tap_configs if tc.tap_id != config.tap_id]
        self._tap_configs.append(config)
        logger.info(f"Tap registered: {config.tap_id} stage={config.stage} layer={config.layer_selector}")

    def unregister_tap(self, tap_id: str) -> None:
        """Remove a tap. Silent if not found."""
        before = len(self._tap_configs)
        self._tap_configs = [tc for tc in self._tap_configs if tc.tap_id != tap_id]
        if len(self._tap_configs) < before:
            logger.info(f"Tap unregistered: {tap_id}")

    def clear(self):
        """Clear all layers (thread-safe)."""
        with self._render_lock:
            layers_to_clean = list(self.layers)
            self.layers.clear()
            self.layer_counter = 0
            self._layer_effect_log_frame.clear()

        for layer in layers_to_clean:
            try:
                layer.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up layer: {e}")

    def shutdown(self):
        """Shutdown thread pools (call when LayerManager is being destroyed)."""
        self._load_pool.shutdown(wait=False)
        self._render_pool.shutdown(wait=False)
