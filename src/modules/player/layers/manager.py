"""
Layer Manager - Manages multi-layer compositing and layer effects
"""
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from ...core.logger import get_logger, debug_layers, debug_transport
from ..sources import VideoSource, GeneratorSource
import cv2
import numpy as np
from ...gpu import get_context, get_texture_pool, get_renderer, load_shader, BLEND_MODES, probe_gpu_readback, GPU_READBACK_VIABLE
from .layer import Layer

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
        self._blend_cache = {}  # Cache blend plugin instances: {(blend_mode, opacity): plugin_instance}
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
    
    def apply_layer_effects(self, layer, frame, player_name=""):
        """
        Apply all effects of a layer to a frame.
        
        Args:
            layer: Layer object
            frame: Input frame
            player_name: Name for logging
        
        Returns:
            Processed frame
        """
        # Layer effects logging removed for performance
        
        # REMOVED: Don't restore parameters from registry every frame!
        # This was overwriting runtime parameter changes (e.g., from audio sequences).
        # The live instance is the source of truth - parameters should only be updated via update_parameter().
        # 
        # # Get latest parameters from registry (updated via API)
        # if self.clip_registry and layer.clip_id:
        #     registry_effects = self.clip_registry.get_clip_effects(layer.clip_id)
        #     
        #     # Update parameters on instances from registry
        #     for i, effect in enumerate(layer.effects):
        #         if i < len(registry_effects):
        #             registry_params = registry_effects[i].get('parameters', {})
        #             instance = effect['instance']
        #             
        #             # Update each parameter on the instance
        #             for param_name, param_value in registry_params.items():
        #                 # Extract actual value if it's a range metadata dict
        #                 if isinstance(param_value, dict) and '_value' in param_value:
        #                     param_value = param_value['_value']
        #                 setattr(instance, param_name, param_value)
        
        h, w = frame.shape[:2]
        enabled_effects = [e for e in layer.effects if e.get('enabled', True)]
        if not enabled_effects:
            return frame

        # Fast check: does any enabled effect provide a GPU shader?
        has_gpu_effect = any(e['instance'].get_shader() is not None for e in enabled_effects)

        if not has_gpu_effect:
            # ── Pure CPU path — no GPU allocation needed ──────────────────────
            for effect in enabled_effects:
                instance = effect['instance']
                try:
                    frame = instance.process_frame(frame, source=layer.source, player=None)
                except Exception as e:
                    plugin_id = effect.get('id', 'unknown')
                    logger.error(f"❌ [{player_name}] Layer {layer.layer_id} effect {plugin_id} error: {e}")
            return frame

        # ── GPU chaining path ─────────────────────────────────────────────────
        # Upload once → texture-to-texture ping-pong for every GPU effect →
        # single download at the end.  CPU effects force a one-off
        # download+process+re-upload for that step only; the chain resumes after.
        pool = get_texture_pool()
        renderer = get_renderer()
        current_gpu = None
        try:
            current_gpu = pool.acquire(w, h)
            current_gpu.upload(frame)

            for effect in enabled_effects:
                instance = effect['instance']
                try:
                    shader_src = instance.get_shader()
                    if shader_src is not None:
                        dst_gpu = pool.acquire(w, h)
                        try:
                            renderer.render(
                                frag_source=shader_src,
                                target_fbo=dst_gpu.fbo,
                                uniforms=instance.get_uniforms(frame_w=w, frame_h=h),
                                textures={'inputTexture': (0, current_gpu)},
                            )
                            pool.release(current_gpu)
                            current_gpu = dst_gpu  # ping-pong: no download
                        except Exception:
                            pool.release(dst_gpu)
                            raise
                        continue
                    # CPU effect: download into numpy, process, re-upload
                    frame = current_gpu.download()
                    frame = instance.process_frame(frame, source=layer.source, player=None)
                    current_gpu.upload(frame)
                except Exception as e:
                    plugin_id = effect.get('id', 'unknown')
                    logger.error(f"❌ [{player_name}] Layer {layer.layer_id} effect {plugin_id} error: {e}")

            # Single download — all GPU effects have already been applied
            frame = current_gpu.download()
        finally:
            if current_gpu is not None:
                pool.release(current_gpu)

        return frame
    
    def update_layer_effect_parameter(self, clip_id, effect_index, param_name, value, player_name=""):
        """
        Update a live effect plugin instance parameter on the layer whose clip_id matches.

        Called from the WebSocket handler after the registry has already been updated.
        Works for both single-clip (Layer 0) and additional slave layers.

        Args:
            clip_id: Clip UUID identifying which layer to update
            effect_index: Index into layer.effects list
            param_name: Parameter name on the plugin instance
            value: New value (may be a dict with '_value' key for range sliders)
            player_name: Name for logging

        Returns:
            bool: True if the instance was found and updated successfully
        """
        with self._render_lock:
            layers_snap = list(self.layers)

        for layer in layers_snap:
            if layer.clip_id != clip_id:
                continue
            if not layer.effects or effect_index >= len(layer.effects):
                logger.warning(f"⚠️ [{player_name}] update_layer_effect_parameter: effect_index {effect_index} out of range for layer {layer.layer_id} (has {len(layer.effects)} effects)")
                return False

            instance = layer.effects[effect_index].get('instance')
            if instance is None:
                logger.warning(f"⚠️ [{player_name}] update_layer_effect_parameter: no instance on effect {effect_index} for layer {layer.layer_id}")
                return False

            if hasattr(instance, 'update_parameter'):
                success = instance.update_parameter(param_name, value)
                logger.debug(f"🔧 [{player_name}] Layer {layer.layer_id} effect[{effect_index}].{param_name} = {value} → {'OK' if success else 'FAILED'}")
                return bool(success)
            else:
                logger.warning(f"⚠️ [{player_name}] Effect instance has no update_parameter method")
                return False

        logger.warning(f"⚠️ [{player_name}] update_layer_effect_parameter: no layer with clip_id={clip_id[:8]}... found")
        return False

    def load_layer_effects_from_registry(self, layer, player_name=""):
        """
        Load layer effects from ClipRegistry and create plugin instances.
        
        Args:
            layer: Layer object with clip_id
            player_name: Name for logging
        """
        if not self.clip_registry or not layer.clip_id:
            return
        
        clip_data = self.clip_registry.get_clip(layer.clip_id)
        if not clip_data:
            return
        
        effects = clip_data.get('effects', [])
        if not effects:
            return
        
        # Create plugin instances
        layer.effects = []
        logger.debug(f"📦 [{player_name}] Loading {len(effects)} effects for Layer {layer.layer_id} from registry")
        for effect_config in effects:
            plugin_id = effect_config.get('plugin_id')
            # IMPORTANT: Use 'parameters' key (not 'params') to match API and registry format
            params = effect_config.get('parameters', effect_config.get('params', {}))
            enabled = effect_config.get('enabled', True)
            
            logger.debug(f"   Loading plugin '{plugin_id}' with params: {params}")
            
            # Load plugin instance
            plugin_instance = self.plugin_manager.load_plugin(plugin_id, params)
            if not plugin_instance:
                logger.warning(f"⚠️ [{player_name}] Plugin '{plugin_id}' not found for Layer {layer.layer_id}")
                continue
            
            # Special handling for transport
            # CRITICAL: Only call _initialize_state() if transport has NO saved parameters
            # Otherwise we'd overwrite restored values (e.g., transport_position=6 → 0)
            if plugin_id == 'transport' and hasattr(plugin_instance, '_initialize_state') and layer.source:
                # Check if we have saved transport parameters (not just defaults)
                has_saved_params = params and any(key != 'metadata' for key in params.keys())
                
                if not has_saved_params:
                    # No saved params - initialize from source
                    plugin_instance._initialize_state(layer.source)
                    debug_transport(logger, f"🎬 [{player_name}] Transport initialized from source for Layer {layer.layer_id}: out_point={plugin_instance.out_point}")
                else:
                    # Has saved params - just update source reference without resetting
                    if hasattr(plugin_instance, '_frame_source'):
                        plugin_instance._frame_source = layer.source
                    debug_transport(logger, f"🎬 [{player_name}] Transport restored from saved params for Layer {layer.layer_id}: position={plugin_instance.current_position}, out_point={plugin_instance.out_point}")
                
                # Set WebSocket context for position updates (need to get player reference)
                # This needs to be done after layers are attached to player
                # For now, mark that we need to set it
                plugin_instance._needs_websocket_context = True
            
            # Add to layer effects
            try:
                effect_dict = {
                    'id': plugin_id,  # Use 'id' key for runtime checks (e.g., transport detection)
                    'plugin_id': plugin_id,  # Also keep 'plugin_id' for registry compatibility
                    'instance': plugin_instance,
                    'parameters': effect_config.get('parameters', params),  # Use 'parameters' key, prefer from effect_config
                    'enabled': enabled
                }
                layer.effects.append(effect_dict)
                logger.debug(f"   ✅ Added {plugin_id} instance [{id(plugin_instance)}] to layer effects (index {len(layer.effects)-1})")
            except Exception as e:
                logger.error(f"❌ [{player_name}] Error loading effect '{plugin_id}' for Layer {layer.layer_id}: {e}")
        
        logger.debug(f"✅ [{player_name}] Loaded {len(layer.effects)} effects for Layer {layer.layer_id}")
    
    def reload_all_layer_effects(self, player_name=""):
        """
        Reload effects for all layers from ClipRegistry.
        """
        logger.debug(f"🔄 [{player_name}] Reloading all layer effects, layers={len(self.layers)}")
        
        for layer in self.layers:
            if layer.clip_id:
                self.load_layer_effects_from_registry(layer, player_name)
        
        logger.debug(f"✅ [{player_name}] All layer effects reloaded")
    
    def get_blend_plugin(self, blend_mode, opacity):
        """
        Get BlendEffect plugin instance (cached for performance).
        
        OPTIMIZATION: Cache by blend_mode only, update opacity dynamically.
        This prevents cache pollution when opacity changes frequently (slider).
        
        Args:
            blend_mode: Blend mode
            opacity: Opacity 0-100%
        
        Returns:
            BlendEffect plugin instance
        """
        # OPTIMIZATION: Cache by blend_mode only (not opacity)
        # Opacity changes frequently via slider - don't create new instances!
        cache_key = blend_mode
        
        # Check cache first
        if cache_key in self._blend_cache:
            blend = self._blend_cache[cache_key]
            # Update opacity for this frame (lightweight attribute change)
            blend.opacity = opacity
            return blend
        
        # Create new instance and cache it
        from plugins.effects.blend import BlendEffect
        
        blend = BlendEffect()
        blend.initialize({
            'blend_mode': blend_mode,
            'opacity': opacity
        })
        
        self._blend_cache[cache_key] = blend
        return blend
    
    def composite_layers(self, preprocess_transport_callback, player_name="Player"):
        """
        Composite all layers into a single frame using the ModernGL GPU pipeline.

        CPU side (parallel where possible):
          - Layer 0 (master): transport preprocess + source decode + clip effects (sequential)
          - Slave layers 1..N: same steps in parallel thread pool

        GPU side (sequential, all on the calling thread which owns the GL context):
          - Upload each CPU frame to a pooled GL texture
          - Blend onto composite FBO using blend.frag shader (ping-pong FBOs)
          - Download composite to numpy BGR uint8 for CPU consumers

        Single-layer fast path skips the GPU entirely (no blend needed).

        Args:
            preprocess_transport_callback: called before fetching each layer's frame
            player_name: used for effect logging

        Returns:
            (np.ndarray BGR uint8, float source_delay)  or  (None, 0)
        """
        with self._render_lock:
            layers_snap = list(self.layers)

        if not layers_snap:
            return None, 0

        profiler = getattr(self, 'profiler', None)

        # ─── Layer 0 (master) — sequential (controls timing + transport) ────
        preprocess_transport_callback(layers_snap[0])

        if profiler:
            with profiler.profile_stage('source_decode'):
                master_frame, source_delay = layers_snap[0].source.get_next_frame()
        else:
            master_frame, source_delay = layers_snap[0].source.get_next_frame()

        if master_frame is None:
            return None, source_delay

        if profiler:
            with profiler.profile_stage('clip_effects'):
                master_frame = self.apply_layer_effects(
                    layers_snap[0], master_frame, player_name)
        else:
            master_frame = self.apply_layer_effects(
                layers_snap[0], master_frame, player_name)

        # ─── Single-layer fast path: no blending needed ──────────────────────
        if len(layers_snap) == 1:
            return master_frame, source_delay

        # ─── Slave layers: skip invisible ones early ─────────────────────────
        active_slaves = [
            l for l in layers_snap[1:] if l.enabled and l.opacity > 0
        ]
        if not active_slaves:
            return master_frame, source_delay

        # ─── Parallel CPU decode + effects for slave layers ──────────────────
        # Only CPU work here (source decode + numpy effects) — GPU ops come later.
        # cv2 / numpy release the GIL so threads run truly in parallel.
        import time as _time
        def _render_slave(layer):
            try:
                logger.debug(
                    f"🧵 [THREAD:{threading.current_thread().name}] "
                    f"rendering slave layer {layer.layer_id}")

                # ── Per-slave FPS rate limiting ───────────────────────────────
                # The slave is called once per master frame (at master FPS).
                # If the slave clip has a lower FPS (e.g. 24fps slave on 30fps
                # master), we must NOT advance its source every master frame —
                # that would play it too fast.  Instead hold the last frame until
                # enough time has elapsed for the slave's own frame interval.
                now = _time.perf_counter()
                slave_fps = getattr(layer.source, 'fps', 30.0) or 30.0
                slave_frame_interval = 1.0 / slave_fps

                if not hasattr(layer, '_slave_next_time'):
                    # First call — initialise timing state; fetch immediately.
                    layer._slave_next_time = now
                    layer._slave_cached_frame = None

                if now >= layer._slave_next_time or layer._slave_cached_frame is None:
                    # Time to advance — fetch a new frame from the source.
                    preprocess_transport_callback(layer)
                    overlay_frame, _ = layer.source.get_next_frame()

                    if overlay_frame is None:
                        debug_layers(logger,
                            f"🔁 Layer {layer.layer_id} reached end, auto-reset (slave loop)")
                        layer.source.reset()
                        overlay_frame, _ = layer.source.get_next_frame()

                    if overlay_frame is None:
                        source_info = getattr(
                            layer.source, 'video_path',
                            getattr(layer.source, 'generator_name', 'Unknown'))
                        if not hasattr(self, '_warned_layers'):
                            self._warned_layers = set()
                        if layer.layer_id not in self._warned_layers:
                            logger.warning(
                                f"⚠️ Layer {layer.layer_id} (source: {source_info}) "
                                f"returned None after reset, skipping")
                            self._warned_layers.add(layer.layer_id)
                        return layer.layer_id, None

                    overlay_frame = self.apply_layer_effects(
                        layer, overlay_frame, player_name)
                    layer._slave_cached_frame = overlay_frame
                    # Advance deadline by one slave frame interval (drift-safe)
                    layer._slave_next_time += slave_frame_interval
                    # Guard: if we've fallen far behind, don't try to catch up
                    if layer._slave_next_time < now - slave_frame_interval:
                        layer._slave_next_time = now + slave_frame_interval

                return layer.layer_id, layer._slave_cached_frame

            except Exception as e:
                logger.error(
                    f"❌ Parallel slave render error (layer {layer.layer_id}): {e}")
                return layer.layer_id, None

        futures_map = {
            self._render_pool.submit(_render_slave, layer): layer
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
                    logger.error(
                        f"❌ Slave render future error (layer {layer.layer_id}): {e}")
        except TimeoutError:
            logger.error(
                "⚠️ Slave layer rendering timed out (0.5s) — compositing available frames only")

        if profiler:
            stage_cm = profiler.profile_stage('layer_composition')
            stage_cm.__enter__()

        try:
            # ── GPU compositing path ──────────────────────────────────────────
            # blend.frag shader chain on GPU — single download at the very end.
            # No longer gated on self._use_gpu: with GPU-chained effects the
            # per-frame readback is already paid once per layer; the compositor
            # blend shaders themselves cost only microseconds.
            ctx = get_context()
            pool = get_texture_pool()
            renderer = get_renderer()
            blend_src = load_shader('blend.frag')
            canvas_w, canvas_h = self.canvas_width, self.canvas_height

            composite = pool.acquire(canvas_w, canvas_h)
            composite.upload(np.ascontiguousarray(master_frame[:, :, :3] if master_frame.shape[2] == 4 else master_frame))

            for layer in layers_snap[1:]:
                if not layer.enabled or layer.opacity <= 0:
                    continue
                overlay = slave_frames.get(layer.layer_id)
                if overlay is None:
                    continue
                ov3 = overlay[:, :, :3] if overlay.shape[2] == 4 else overlay
                if ov3.shape[:2] != (canvas_h, canvas_w):
                    ov3 = cv2.resize(ov3, (canvas_w, canvas_h))
                layer_tex = pool.acquire(canvas_w, canvas_h)
                try:
                    layer_tex.upload(np.ascontiguousarray(ov3))
                    blend_mode = BLEND_MODES.get(getattr(layer, 'blend_mode', 'normal'), 0)
                    renderer.render(
                        frag_source=blend_src,
                        target_fbo=composite.fbo,
                        uniforms={'opacity': layer.opacity / 100.0, 'mode': blend_mode},
                        textures={'base': (0, composite), 'overlay': (1, layer_tex)},
                    )
                finally:
                    pool.release(layer_tex)

            result = composite.download()
            pool.release(composite)

        finally:
            if profiler:
                stage_cm.__exit__(None, None, None)

        return result, source_delay
    
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
