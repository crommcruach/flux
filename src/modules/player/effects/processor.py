"""
Effect Processor - Manages effect chains and applies effects to frames
"""
from ...core.logger import get_logger, debug_effects
from ...plugins.manager import get_plugin_manager
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
            
            logger.debug(f"✅ Effect '{plugin_id}' added to {chain_type} chain (position {chain_length})")
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
            logger.debug(f"✅ Effect '{effect['id']}' removed from {chain_type} chain position {index}")
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
        
        logger.debug(f"✅ {count} effects cleared from {chain_type} chain")
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
            
            # REMOVED: Don't call _initialize_state here - it would reset saved parameters!
            # get_chain() is called by frontend for display, shouldn't modify state
            # Initialization happens in apply_clip_effects() and layer manager
            
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
            logger.debug(f"Effect '{plugin_id}' at index {index} is now {'enabled' if new_state else 'disabled'}")
            
            return True, new_state, f"Effect {'enabled' if new_state else 'disabled'}"
            
        except Exception as e:
            logger.error(f"❌ Error toggling effect {index}: {e}")
            return False, False, str(e)
    
    def is_chain_noop(self, chain_type='video'):
        """Check if effect chain consists only of no-op effects.
        
        Args:
            chain_type: 'video' or 'artnet'
            
        Returns:
            bool: True if all effects in chain are no-ops or chain is empty
        """
        effect_chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
        
        if not effect_chain:
            return True  # Empty chain is a no-op
        
        for effect in effect_chain:
            # Skip disabled effects
            if not effect.get('enabled', True):
                continue
                
            plugin_instance = effect.get('instance')
            if plugin_instance and hasattr(plugin_instance, 'is_noop'):
                if not plugin_instance.is_noop():
                    return False  # Found an effect that will modify the frame
            else:
                # Effect doesn't have is_noop() method, assume it will modify
                return False
        
        return True  # All effects are no-ops
    
    def clear_clip_cache(self):
        """Clear clip effect cache."""
        self._cached_clip_effects = None
        self._cached_clip_id = None
        self._cached_version = -1
