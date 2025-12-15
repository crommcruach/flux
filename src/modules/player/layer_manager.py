"""
Layer Manager - Manages multi-layer compositing and layer effects
"""
import os
from ..logger import get_logger, debug_layers, debug_transport
from ..layer import Layer

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
        
    def _set_websocket_context_on_transport(self, clip_id, player_name=""):
        """Set WebSocket context on all transport effects in layers."""
        if not self.player or not hasattr(self.player, 'player_manager'):
            logger.warning(f"⚠️ [{player_name}] Cannot set WebSocket context: player or player_manager not available")
            return
        
        if not hasattr(self.player.player_manager, 'socketio'):
            logger.warning(f"⚠️ [{player_name}] Cannot set WebSocket context: socketio not available on player_manager")
            return
        
        socketio = self.player.player_manager.socketio
        player_id = self.player_id
        
        for layer in self.layers:
            for effect in layer.effects:
                if effect.get('id') == 'transport' and effect.get('instance'):
                    transport = effect['instance']
                    if hasattr(transport, '_needs_websocket_context'):
                        transport.socketio = socketio
                        transport.player_id = player_id
                        transport.clip_id = clip_id
                        logger.info(f"📡 [{player_name}] Set WebSocket context on transport: player_id={player_id}, clip_id={clip_id}, socketio={socketio is not None}")
        
    def load_clip_layers(self, clip_id, video_dir=None, player_name=""):
        """
        Load all layers from clip definition and create FrameSources.
        Replaces current layer stack.
        
        Args:
            clip_id: Clip UUID from ClipRegistry
            video_dir: Base directory for resolving relative video paths
            player_name: Name for logging
        
        Returns:
            bool: True on success
        """
        # Get clip data
        clip_data = self.clip_registry.get_clip(clip_id)
        if not clip_data:
            logger.error(f"❌ [{player_name}] Clip {clip_id} not found")
            return False
        
        # Build new layer stack first, then swap atomically
        new_layers = []
        layer_counter = 0
        
        # Get layer definitions
        layer_defs = clip_data.get('layers', [])
        
        from ..frame_source import VideoSource, GeneratorSource
        
        # ALWAYS create Layer 0 from the clip itself (base layer)
        abs_path = clip_data['absolute_path']
        base_source = None
        
        # Get video extensions from config
        video_extensions = tuple(self.config.get('extensions', ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.gif']))
        
        # Detect source type from path
        if abs_path.endswith(video_extensions):
            base_source = VideoSource(abs_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height, config=self.config, clip_id=clip_id)
        elif abs_path.startswith('generator:'):
            gen_id = abs_path.replace('generator:', '')
            # Get generator parameters from clip metadata if available
            metadata = clip_data.get('metadata', {})
            gen_params = metadata.get('parameters', metadata.get('generator_params', {}))
            base_source = GeneratorSource(gen_id, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
        
        if base_source and base_source.initialize():
            base_layer = Layer(layer_counter, base_source, 'normal', 100.0, clip_id)
            new_layers.append(base_layer)
            layer_counter += 1
            logger.info(f"✅ [{player_name}] Created clip {clip_id} as Layer 0 (base)")
            
            # Load effects for base layer from registry
            self.load_layer_effects_from_registry(base_layer, player_name)
        else:
            logger.error(f"❌ [{player_name}] Failed to create base layer for clip {clip_id}")
            return False
        
        # Now add additional layers from definitions (if any)
        if layer_defs:
            for layer_def in layer_defs:
                source_type = layer_def.get('source_type')
                source_path = layer_def.get('source_path')
                blend_mode = layer_def.get('blend_mode', 'normal')
                opacity = layer_def.get('opacity', 1.0) * 100  # Convert to 0-100
                enabled = layer_def.get('enabled', True)
                layer_id = layer_def.get('layer_id', layer_counter)
                
                source = None
                
                if source_type == 'video':
                    # Convert relative path to absolute if needed
                    video_path = source_path
                    if video_dir and not os.path.isabs(video_path):
                        video_path = os.path.join(video_dir, video_path)
                    source = VideoSource(video_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height, config=self.config)
                elif source_type == 'generator':
                    gen_params = layer_def.get('parameters', {})
                    source = GeneratorSource(source_path, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
                
                if source and source.initialize():
                    # Check if layer already has a clip_id
                    layer_clip_id = layer_def.get('clip_id')
                    
                    # If no clip_id exists, register this layer as a clip
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
                        # Update the layer config with clip_id for persistence
                        self.clip_registry.update_clip_layer(clip_id, layer_id, {'clip_id': layer_clip_id})
                        logger.debug(f"📐 Layer {layer_id} registered as clip during load: {layer_clip_id}")
                    
                    new_layer = Layer(layer_id, source, blend_mode, opacity, layer_clip_id)
                    new_layer.enabled = enabled
                    new_layers.append(new_layer)
                    
                    logger.info(f"📐 Layer {layer_id} loaded: opacity={opacity}%, blend={blend_mode}, enabled={enabled}")
                    
                    # Load effects from registry
                    if layer_clip_id:
                        self.load_layer_effects_from_registry(new_layer, player_name)
                    
                    layer_counter = layer_id + 1
                else:
                    logger.warning(f"⚠️ [{player_name}] Failed to create layer source: {source_type}:{source_path}")
        
        # Atomically swap layer stack (thread-safe)
        old_layers = self.layers
        self.layers = new_layers
        self.layer_counter = layer_counter
        
        # Cleanup old layers after swap
        for layer in old_layers:
            try:
                layer.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up old layer: {e}")
        
        # Set WebSocket context on transport effects (needs player reference)
        self._set_websocket_context_on_transport(clip_id, player_name)
        
        logger.info(f"✅ [{player_name}] Loaded {len(self.layers)} layers from clip {clip_id}")
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
            if hasattr(source, 'video_path'):
                source_path = source.video_path
            elif hasattr(source, 'generator_id'):
                source_path = f"generator:{source.generator_id}"
            
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
            
            # Store clip_id in base clip's layer config for API access
            self.clip_registry.update_clip_layer(clip_id, layer_id, {'clip_id': layer_clip_id})
        
        # Create layer with clip_id
        layer = Layer(layer_id, source, blend_mode, opacity, layer_clip_id)
        self.layers.append(layer)
        
        # Load effects from registry if layer has clip_id
        if layer_clip_id:
            self.load_layer_effects_from_registry(layer, player_name)
        
        logger.info(
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
                
                logger.info(f"🗑️ [{player_name}] Layer {layer_id} removed")
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
        
        logger.info(f"🔄 [{player_name}] Layers reordered: {new_order}")
        return True
    
    def update_layer_config(self, layer_id, blend_mode=None, opacity=None, enabled=None, player_name=""):
        """
        Update layer configuration at runtime.
        
        Args:
            layer_id: Layer ID
            blend_mode: Optional new blend mode
            opacity: Optional new opacity
            enabled: Optional enabled status
            player_name: Name for logging
        
        Returns:
            bool: True on success
        """
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
        # Log every 30 frames to avoid spam
        if layer.layer_id not in self._layer_effect_log_frame:
            self._layer_effect_log_frame[layer.layer_id] = 0
        
        if self._layer_effect_log_frame[layer.layer_id] % 30 == 0:
            logger.info(f"🎨 [{player_name}] Layer {layer.layer_id} has {len(layer.effects)} effects (clip_id={layer.clip_id})")
            if layer.effects:
                for i, eff in enumerate(layer.effects):
                    logger.info(f"   [{i}] {eff.get('id')} - enabled: {eff.get('enabled', True)}")
        
        self._layer_effect_log_frame[layer.layer_id] += 1
        
        # Get latest parameters from registry (updated via API)
        if self.clip_registry and layer.clip_id:
            registry_effects = self.clip_registry.get_clip_effects(layer.clip_id)
            
            # Update parameters on instances from registry
            for i, effect in enumerate(layer.effects):
                if i < len(registry_effects):
                    registry_params = registry_effects[i].get('parameters', {})
                    instance = effect['instance']
                    
                    # Update each parameter on the instance
                    for param_name, param_value in registry_params.items():
                        # Extract actual value if it's a range metadata dict
                        if isinstance(param_value, dict) and '_value' in param_value:
                            param_value = param_value['_value']
                        setattr(instance, param_name, param_value)
        
        for effect in layer.effects:
            # Skip disabled effects
            if not effect.get('enabled', True):
                continue
            
            try:
                instance = effect['instance']
                plugin_id = effect.get('id', 'unknown')
                logger.debug(f"  ✓ Layer {layer.layer_id} effect: {plugin_id}")
                # Pass layer's source and player context
                frame = instance.process_frame(frame, source=layer.source, player=None)
            except Exception as e:
                logger.error(f"❌ [{player_name}] Layer {layer.layer_id} effect error: {e}")
        
        return frame
    
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
        logger.info(f"📦 [{player_name}] Loading {len(effects)} effects for Layer {layer.layer_id} from registry")
        for effect_config in effects:
            plugin_id = effect_config.get('plugin_id')
            params = effect_config.get('params', {})
            enabled = effect_config.get('enabled', True)
            
            logger.info(f"   Loading plugin '{plugin_id}' with params: {params}")
            
            # Load plugin instance
            plugin_instance = self.plugin_manager.load_plugin(plugin_id, params)
            if not plugin_instance:
                logger.warning(f"⚠️ [{player_name}] Plugin '{plugin_id}' not found for Layer {layer.layer_id}")
                continue
            
            # Special handling for transport
            if plugin_id == 'transport' and hasattr(plugin_instance, '_initialize_state') and layer.source:
                plugin_instance._initialize_state(layer.source)
                debug_transport(logger, f"🎬 [{player_name}] Transport initialized for Layer {layer.layer_id}: out_point={plugin_instance.out_point}")
                
                # Set WebSocket context for position updates (need to get player reference)
                # This needs to be done after layers are attached to player
                # For now, mark that we need to set it
                plugin_instance._needs_websocket_context = True
            
            # Add to layer effects
            try:
                layer.effects.append({
                    'id': plugin_id,
                    'instance': plugin_instance,
                    'config': params,
                    'enabled': enabled
                })
            except Exception as e:
                logger.error(f"❌ [{player_name}] Error loading effect '{plugin_id}' for Layer {layer.layer_id}: {e}")
        
        logger.info(f"✅ [{player_name}] Loaded {len(layer.effects)} effects for Layer {layer.layer_id}")
    
    def reload_all_layer_effects(self, player_name=""):
        """
        Reload effects for all layers from ClipRegistry.
        """
        logger.info(f"🔄 [{player_name}] Reloading all layer effects, layers={len(self.layers)}")
        
        for layer in self.layers:
            if layer.clip_id:
                self.load_layer_effects_from_registry(layer, player_name)
        
        logger.info(f"✅ [{player_name}] All layer effects reloaded")
    
    def get_blend_plugin(self, blend_mode, opacity):
        """
        Get BlendEffect plugin instance (cached for performance).
        
        Args:
            blend_mode: Blend mode
            opacity: Opacity 0-100%
        
        Returns:
            BlendEffect plugin instance
        """
        cache_key = (blend_mode, opacity)
        
        # Check cache first
        if cache_key in self._blend_cache:
            return self._blend_cache[cache_key]
        
        # Create new instance and cache it
        from plugins.effects.blend import BlendEffect
        
        blend = BlendEffect()
        blend.initialize({
            'blend_mode': blend_mode,
            'opacity': opacity
        })
        
        self._blend_cache[cache_key] = blend
        return blend
    
    def clear(self):
        """Clear all layers."""
        for layer in self.layers:
            try:
                layer.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up layer: {e}")
        
        self.layers.clear()
        self.layer_counter = 0
        self._layer_effect_log_frame.clear()
