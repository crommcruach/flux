"""
Effect Processor - Manages effect chains and applies effects to frames
"""
from ..logger import get_logger, debug_effects
from ..plugin_manager import get_plugin_manager
from plugins import PluginType, ParameterType

logger = get_logger(__name__)


class EffectProcessor:
    """Manages video and Art-Net effect chains and applies them to frames."""
    
    def __init__(self, plugin_manager=None, clip_registry=None):
        """
        Initialize EffectProcessor.
        
        Args:
            plugin_manager: Reference to PluginManager (optional)
            clip_registry: Reference to ClipRegistry (optional)
        """
        self.video_effect_chain = []  # Video-Preview FX (not sent to Art-Net)
        self.artnet_effect_chain = []  # Art-Net Output FX (not sent to Video-Preview)
        
        # Clip-Effect Cache (B3 Performance: Version-based cache invalidation)
        self._cached_clip_effects = None  # Cached effect list
        self._cached_clip_id = None       # Clip ID of cached effects
        self._cached_version = -1         # Version counter for cache invalidation
        
        self.plugin_manager = plugin_manager or get_plugin_manager()
        self.clip_registry = clip_registry
        
    def add_effect(self, plugin_id, config=None, chain_type='video'):
        """
        Add effect to chain.
        
        Args:
            plugin_id: Plugin identifier
            config: Plugin configuration dict
            chain_type: 'video' or 'artnet'
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Load plugin instance
            plugin_instance = self.plugin_manager.load_plugin(plugin_id, config)
            if not plugin_instance:
                return False, f"Plugin '{plugin_id}' could not be loaded"
            
            # Check if it's an EFFECT plugin
            plugin_type = plugin_instance.METADATA.get('type')
            
            if plugin_type != PluginType.EFFECT:
                return False, f"Plugin '{plugin_id}' is not an EFFECT plugin"
            
            effect_data = {
                'id': plugin_id,
                'instance': plugin_instance,
                'config': config or {},
                'enabled': True
            }
            
            # Add to correct chain
            if chain_type == 'artnet':
                self.artnet_effect_chain.append(effect_data)
                chain_length = len(self.artnet_effect_chain)
            else:
                self.video_effect_chain.append(effect_data)
                chain_length = len(self.video_effect_chain)
            
            logger.info(f"✅ Effect '{plugin_id}' added to {chain_type} chain (position {chain_length})")
            return True, f"Effect '{plugin_id}' added to {chain_type} chain"
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Error adding effect '{plugin_id}': {e}")
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def remove_effect(self, index, chain_type='video'):
        """
        Remove effect from chain.
        
        Args:
            index: Effect index
            chain_type: 'video' or 'artnet'
            
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, f"Invalid index {index} (chain length: {len(chain)})"
            
            effect = chain.pop(index)
            logger.info(f"✅ Effect '{effect['id']}' removed from {chain_type} chain position {index}")
            return True, f"Effect removed from {chain_type} chain"
            
        except Exception as e:
            logger.error(f"❌ Error removing effect: {e}")
            return False, str(e)
    
    def clear_chain(self, chain_type='video'):
        """
        Clear all effects from chain.
        
        Args:
            chain_type: 'video' or 'artnet'
            
        Returns:
            tuple: (success: bool, message: str)
        """
        if chain_type == 'artnet':
            count = len(self.artnet_effect_chain)
            self.artnet_effect_chain.clear()
        else:
            count = len(self.video_effect_chain)
            self.video_effect_chain.clear()
        
        logger.info(f"✅ {count} effects cleared from {chain_type} chain")
        return True, f"{count} effects cleared from {chain_type} chain"
    
    def get_chain(self, chain_type='video', layers=None):
        """
        Get current effect chain info.
        
        Args:
            chain_type: 'video' or 'artnet'
            layers: Layer list for transport initialization (optional)
        
        Returns:
            list: List of effect info [{plugin_id, parameters, metadata}, ...]
        """
        # Select correct chain
        chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
        
        chain_info = []
        for i, effect in enumerate(chain):
            plugin_instance = effect['instance']
            
            # SPECIAL: If transport and has source, ensure it's initialized
            if effect['id'] == 'transport' and hasattr(plugin_instance, '_initialize_state'):
                if layers and len(layers) > 0 and layers[0].source:
                    logger.info(f"🎬 [get_chain] Initializing transport with source: {type(layers[0].source).__name__}")
                    plugin_instance._initialize_state(layers[0].source)
                else:
                    logger.warning(f"⚠️ [get_chain] Cannot initialize transport: no source available")
            
            # Get current parameter values from plugin instance
            current_parameters = plugin_instance.get_parameters()
            
            # Convert METADATA for JSON (Enums to strings)
            metadata = plugin_instance.METADATA.copy()
            if 'type' in metadata and isinstance(metadata['type'], PluginType):
                metadata['type'] = metadata['type'].value
            
            # Convert PARAMETERS for JSON
            parameters_schema = []
            for param in plugin_instance.PARAMETERS:
                param_copy = param.copy()
                if 'type' in param_copy and isinstance(param_copy['type'], ParameterType):
                    param_copy['type'] = param_copy['type'].value
                parameters_schema.append(param_copy)
            
            chain_info.append({
                'index': i,
                'plugin_id': effect['id'],
                'name': plugin_instance.METADATA.get('name', effect['id']),
                'version': plugin_instance.METADATA.get('version', '1.0.0'),
                'enabled': effect.get('enabled', True),
                'parameters': current_parameters,
                'metadata': {
                    **metadata,
                    'parameters': parameters_schema
                }
            })
        return chain_info
    
    def update_parameter(self, index, param_name, value, chain_type='video'):
        """
        Update effect parameter.
        
        Args:
            index: Effect index
            param_name: Parameter name
            value: New value
            chain_type: 'video' or 'artnet'
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Select correct chain
            chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, f"Invalid index {index}"
            
            effect = chain[index]
            plugin_id = effect['id']
            plugin_instance = effect['instance']
            
            # Validate parameter
            is_valid = self.plugin_manager.validate_parameter_value(plugin_id, param_name, value)
            if not is_valid:
                return False, f"Invalid value for parameter '{param_name}'"
            
            # Set parameter on plugin instance
            success = plugin_instance.update_parameter(param_name, value)
            
            if success:
                # Update config
                effect['config'][param_name] = value
                logger.debug(f"Effect '{plugin_id}' parameter '{param_name}' = {value}")
                return True, f"Parameter '{param_name}' updated"
            else:
                return False, f"Plugin does not support parameter '{param_name}'"
            
        except Exception as e:
            logger.error(f"❌ Error updating effect {index} parameter: {e}")
            return False, str(e)
    
    def toggle_enabled(self, index, chain_type='video'):
        """
        Toggle effect enabled/disabled state.
        
        Args:
            index: Effect index
            chain_type: 'video' or 'artnet'
        
        Returns:
            tuple: (success: bool, enabled: bool, message: str)
        """
        try:
            # Select correct chain
            chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, False, f"Invalid index {index}"
            
            effect = chain[index]
            
            # Toggle enabled state
            current_state = effect.get('enabled', True)
            new_state = not current_state
            effect['enabled'] = new_state
            
            plugin_id = effect['id']
            logger.info(f"Effect '{plugin_id}' at index {index} is now {'enabled' if new_state else 'disabled'}")
            
            return True, new_state, f"Effect {'enabled' if new_state else 'disabled'}"
            
        except Exception as e:
            logger.error(f"❌ Error toggling effect {index}: {e}")
            return False, False, str(e)
    
    def apply_effects(self, frame, chain_type='video', current_clip_id=None, source=None, player=None, player_name=""):
        """
        Apply all effects in chain to frame.
        
        Args:
            frame: Input frame (numpy array, RGB, uint8)
            chain_type: 'video' or 'artnet'
            current_clip_id: Current clip UUID for clip-level effects
            source: Frame source (for transport plugin)
            player: Player reference (for effects that need it)
            player_name: Player name for logging
        
        Returns:
            numpy array: Processed frame
        """
        processed_frame = frame
        
        # 1. Apply clip-level effects first (if current clip has effects)
        # B3 Performance Optimization: Version-based cache invalidation
        if self.clip_registry and current_clip_id:
            current_version = self.clip_registry.get_effects_version(current_clip_id)
            
            # Cache check: clip_id AND version must match
            if (self._cached_clip_id == current_clip_id and 
                self._cached_version == current_version):
                # Cache hit! Use cached effects (99.9% of frames)
                clip_effects = self._cached_clip_effects
            else:
                # Cache miss: Reload effects (only on clip change or parameter change)
                clip_effects = self.clip_registry.get_clip_effects(current_clip_id)
                
                # Pre-instantiate plugin instances (remove lazy-loading overhead)
                for effect_data in clip_effects:
                    if 'instance' not in effect_data:
                        plugin_id = effect_data['plugin_id']
                        if plugin_id in self.plugin_manager.registry:
                            plugin_class = self.plugin_manager.registry[plugin_id]
                            # Pass parameters as config
                            config = effect_data.get('parameters', {})
                            effect_data['instance'] = plugin_class(config)
                            
                            # Special handling for transport
                            if plugin_id == 'transport' and hasattr(effect_data['instance'], '_initialize_state'):
                                if source:
                                    # Only call _initialize_state if transport has no valid trim yet
                                    # (to avoid overwriting user's trim settings from config)
                                    transport = effect_data['instance']
                                    needs_init = (
                                        transport._frame_source is None or
                                        transport._total_frames is None
                                    )
                                    
                                    if needs_init:
                                        transport._initialize_state(source)
                                        logger.info(f"🎬 [{player_name}] Transport initialized for clip {current_clip_id}: [{transport.in_point}, {transport.out_point}]")
                                    else:
                                        logger.info(f"🎬 [{player_name}] Transport already initialized, keeping trim: [{transport.in_point}, {transport.out_point}]")
                                    
                                    # Set WebSocket context for position updates
                                    if player and hasattr(player, 'player_manager') and hasattr(player.player_manager, 'socketio'):
                                        transport.socketio = player.player_manager.socketio
                                        transport.player_id = player.player_id
                                        transport.clip_id = current_clip_id
                                        logger.info(f"📡 [{player_name}] Transport WebSocket context set: player_id={player.player_id}, clip_id={current_clip_id}, socketio={transport.socketio is not None}")
                                    else:
                                        logger.warning(f"⚠️ [{player_name}] Could not set Transport WebSocket context: player={player is not None}, has_manager={hasattr(player, 'player_manager') if player else False}, has_socketio={hasattr(player.player_manager, 'socketio') if player and hasattr(player, 'player_manager') else False}")
                                    
                                    # Sync parameters back to registry
                                    effect_data['parameters']['transport_position'] = {
                                        '_value': transport.current_position,
                                        '_rangeMin': transport.in_point,
                                        '_rangeMax': transport.out_point
                                    }
                            
                            logger.info(f"✅ [{player_name}] Created clip effect instance: {plugin_id}")
                        else:
                            logger.warning(f"Plugin '{plugin_id}' not found in registry")
                
                # Update cache
                self._cached_clip_effects = clip_effects
                self._cached_clip_id = current_clip_id
                self._cached_version = current_version
                logger.debug(f"📦 [{player_name}] Effect cache updated for clip {current_clip_id}")
            
            if clip_effects:
                for effect_data in clip_effects:
                    # Skip disabled effects
                    if not effect_data.get('enabled', True):
                        continue
                    
                    try:
                        plugin_instance = effect_data['instance']

                        # Update parameters from effect_data EVERY frame
                        for param_name, param_value in effect_data['parameters'].items():
                            # Skip transport_position - it's managed internally
                            if param_name == 'transport_position':
                                # Only update if not initialized yet
                                if hasattr(plugin_instance, 'in_point') and hasattr(plugin_instance, '_virtual_frame'):
                                    # Already initialized - only update if trim range changed
                                    if isinstance(param_value, dict):
                                        new_in = param_value.get('_rangeMin', plugin_instance.in_point)
                                        new_out = param_value.get('_rangeMax', plugin_instance.out_point)
                                        if new_in != plugin_instance.in_point or new_out != plugin_instance.out_point:
                                            if hasattr(plugin_instance, 'update_parameter'):
                                                plugin_instance.update_parameter(param_name, param_value)
                                else:
                                    # First initialization
                                    if hasattr(plugin_instance, 'update_parameter'):
                                        plugin_instance.update_parameter(param_name, param_value)
                                continue
                            
                            # Use update_parameter if available
                            if hasattr(plugin_instance, 'update_parameter'):
                                # Extract actual value from dict format if needed
                                value_to_set = param_value
                                if isinstance(param_value, dict) and '_value' in param_value:
                                    value_to_set = param_value['_value']
                                plugin_instance.update_parameter(param_name, value_to_set)
                            else:
                                # Fallback: direct setattr
                                if isinstance(param_value, dict) and '_value' in param_value:
                                    setattr(plugin_instance, param_name, param_value['_value'])
                                else:
                                    setattr(plugin_instance, param_name, param_value)

                        # Process frame
                        processed_frame = plugin_instance.process_frame(processed_frame, source=source, player=player)
                        
                        if processed_frame is None:
                            logger.error(f"❌ [{player_name}] Clip effect '{effect_data['plugin_id']}' returned None")
                            processed_frame = frame
                            continue
                            
                    except Exception as e:
                        logger.error(f"❌ [{player_name}] Error in clip effect '{effect_data.get('plugin_id', 'unknown')}': {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        continue
        
        # 2. Apply player-level effects
        effect_chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
        
        if effect_chain:
            for effect in effect_chain:
                # Skip disabled effects
                if not effect.get('enabled', True):
                    continue
                
                try:
                    plugin_instance = effect['instance']
                    processed_frame = plugin_instance.process_frame(processed_frame)
                    
                    # Ensure frame is valid
                    if processed_frame is None:
                        logger.error(f"Effect '{effect['id']}' returned None, skipping")
                        processed_frame = frame
                        continue
                        
                except Exception as e:
                    logger.error(f"❌ Error in effect '{effect['id']}': {e}")
                    continue
        
        return processed_frame
    
    def clear_clip_cache(self):
        """Clear clip effect cache."""
        self._cached_clip_effects = None
        self._cached_clip_id = None
        self._cached_version = -1
