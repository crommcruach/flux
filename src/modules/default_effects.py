"""
Default Effects Manager
Handles automatic loading and application of default effect chains from config.json
"""
from typing import Dict, List, Any, Optional
from copy import deepcopy
from .logger import get_logger

logger = get_logger(__name__)


class DefaultEffectsManager:
    """Manages default effect chains from configuration."""
    
    def __init__(self, config: Dict[str, Any], plugin_manager):
        """
        Initialize Default Effects Manager.
        
        Args:
            config: Application configuration dictionary
            plugin_manager: Plugin manager instance for effect validation
        """
        self.config = config
        self.plugin_manager = plugin_manager
        self.effects_config = config.get('effects', {})
        
        logger.info("🎨 Default Effects Manager initialized")
        self._log_config()
    
    def _log_config(self):
        """Log current default effects configuration."""
        video_count = len(self.effects_config.get('video', []))
        artnet_count = len(self.effects_config.get('artnet', []))
        clip_effects = self.effects_config.get('clips', [])
        clip_count = len(clip_effects) if isinstance(clip_effects, list) else 0
        
        if video_count > 0:
            logger.info(f"  📹 Video default effects: {video_count} configured")
        if artnet_count > 0:
            logger.info(f"  💡 Art-Net default effects: {artnet_count} configured")
        if clip_count > 0:
            logger.info(f"  🎬 Clip default effects: {clip_count} effects (applied to ALL clips)")
        
        if video_count == 0 and artnet_count == 0 and clip_count == 0:
            logger.info("  ℹ️  No default effects configured")
    
    def get_video_effects(self) -> List[Dict[str, Any]]:
        """
        Get default effect chain for video player.
        
        Returns:
            List of effect configurations
        """
        return self.effects_config.get('video', [])
    
    def get_artnet_effects(self) -> List[Dict[str, Any]]:
        """
        Get default effect chain for Art-Net player.
        
        Returns:
            List of effect configurations
        """
        return self.effects_config.get('artnet', [])
    
    def get_clip_effects(self) -> List[Dict[str, Any]]:
        """
        Get default effects for clips (applied to ALL clips).
        
        Returns:
            List of effect configurations to apply to all clips
        """
        clip_effects = self.effects_config.get('clips', [])
        
        if isinstance(clip_effects, list):
            return clip_effects
        
        return []
    
    def validate_effect_config(self, effect_config: Dict[str, Any]) -> bool:
        """
        Validate a single effect configuration.
        
        Args:
            effect_config: Effect config dict with plugin_id and params
            
        Returns:
            True if valid, False otherwise
        """
        if 'plugin_id' not in effect_config:
            logger.warning(f"❌ Effect config missing 'plugin_id': {effect_config}")
            return False
        
        plugin_id = effect_config['plugin_id']
        
        # Check if plugin exists in registry
        if plugin_id not in self.plugin_manager.registry:
            available = list(self.plugin_manager.registry.keys())
            logger.warning(f"❌ Plugin '{plugin_id}' not found in registry")
            logger.warning(f"   Available plugins: {', '.join(available)}")
            return False
        
        return True
    
    def apply_to_player(self, player_manager, player_type: str) -> int:
        """
        Apply default effects to a player.
        
        Args:
            player_manager: PlayerManager instance
            player_type: 'video' or 'artnet'
            
        Returns:
            Number of effects applied
        """
        if player_type == 'video':
            effects = self.get_video_effects()
            player = player_manager.get_player('video')
        elif player_type == 'artnet':
            effects = self.get_artnet_effects()
            player = player_manager.get_player('artnet')
        else:
            logger.error(f"❌ Invalid player type: {player_type}")
            return 0
        
        if not player:
            logger.warning(f"⚠️ Player '{player_type}' not available")
            return 0
        
        if not effects:
            logger.debug(f"No default effects for {player_type} player")
            return 0
        
        applied_count = 0
        
        for effect_config in effects:
            if not self.validate_effect_config(effect_config):
                continue
            
            plugin_id = effect_config['plugin_id']
            # Deep copy params to ensure each instance gets independent parameter objects
            params = deepcopy(effect_config.get('params', {}))
            
            try:
                # Add effect directly to player
                success, message = player.add_effect_to_chain(
                    plugin_id, 
                    params if params else None, 
                    chain_type=player_type
                )
                
                if success:
                    applied_count += 1
                    logger.debug(f"  ✅ Applied '{plugin_id}' to {player_type} player")
                else:
                    logger.warning(f"  ❌ Failed to apply '{plugin_id}': {message}")
                    
            except Exception as e:
                logger.error(f"  ❌ Error applying '{plugin_id}': {e}")
        
        if applied_count > 0:
            logger.info(f"🎨 Applied {applied_count}/{len(effects)} default effects to {player_type} player")
        
        return applied_count
    
    def apply_to_clip(self, clip_registry, clip_id: str) -> int:
        """
        Apply default effects to a clip (applies ALL default clip effects).
        
        Args:
            clip_registry: ClipRegistry instance
            clip_id: UUID of the clip
            
        Returns:
            Number of effects applied
        """
        effects = self.get_clip_effects()
        
        logger.debug(f"🔧 apply_to_clip: Found {len(effects) if effects else 0} default clip effects in config")
        
        if not effects:
            return 0
        
        applied_count = 0
        
        for effect_config in effects:
            if not self.validate_effect_config(effect_config):
                continue
            
            plugin_id = effect_config['plugin_id']
            # Deep copy params to ensure each clip gets independent parameter objects
            params = deepcopy(effect_config.get('params', {}))
            
            # SPECIAL CASE: transport_position should NOT be copied from config
            # Let transport initialize dynamically based on actual clip length
            if plugin_id == 'transport' and 'transport_position' in params:
                logger.debug(f"  ⏭️ Removing transport_position from config params - will auto-initialize from clip length")
                del params['transport_position']

            
            try:
                # Get plugin metadata
                plugin_class = self.plugin_manager.registry.get(plugin_id)
                if not plugin_class:
                    logger.warning(f"❌ Plugin '{plugin_id}' not found in registry")
                    continue
                
                # Build effect metadata (ensure all enums are converted to strings)
                metadata = plugin_class.METADATA.copy()
                
                # Convert plugin type enum to string
                if 'type' in metadata and hasattr(metadata['type'], 'value'):
                    metadata['type'] = metadata['type'].value
                
                # Build parameters list with all enums converted
                if hasattr(plugin_class, 'PARAMETERS'):
                    parameters = []
                    for param in plugin_class.PARAMETERS:
                        if isinstance(param, dict):
                            # Already a dict, ensure type is string
                            param_dict = param.copy()
                            if 'type' in param_dict and hasattr(param_dict['type'], 'name'):
                                param_dict['type'] = param_dict['type'].name
                            elif 'type' in param_dict:
                                param_dict['type'] = str(param_dict['type'])
                        else:
                            # Convert parameter object to dict
                            param_dict = {
                                'name': param.name,
                                'type': param.type.name if hasattr(param.type, 'name') else str(param.type),
                                'default': param.default,
                                'min': getattr(param, 'min', None),
                                'max': getattr(param, 'max', None),
                                'description': getattr(param, 'description', '')
                            }
                        parameters.append(param_dict)
                    metadata['parameters'] = parameters
                
                # Create effect data
                effect_data = {
                    'plugin_id': plugin_id,
                    'metadata': metadata,
                    'parameters': params if params else {}
                }
                
                # Set default parameters if not provided
                if 'parameters' in metadata:
                    for param in metadata['parameters']:
                        param_name = param['name']
                        if param_name not in effect_data['parameters']:
                            # SPECIAL CASE: transport_position should NOT use hardcoded default
                            # Let transport initialize dynamically based on actual clip length
                            if plugin_id == 'transport' and param_name == 'transport_position':
                                logger.debug(f"  ⏭️ Skipping default for transport_position - will auto-initialize from clip length")
                                continue
                            effect_data['parameters'][param_name] = param['default']
                
                # Add to clip registry
                logger.debug(f"🔧 Adding effect '{plugin_id}' to clip {clip_id}")
                success = clip_registry.add_effect_to_clip(clip_id, effect_data)
                
                if success:
                    applied_count += 1
                    logger.info(f"  ✅ Applied default effect '{plugin_id}' to clip {clip_id}")
                else:
                    logger.warning(f"  ❌ Failed to add '{plugin_id}' to clip registry")
                    
            except Exception as e:
                logger.error(f"  ❌ Error applying '{plugin_id}' to clip: {e}")
        
        if applied_count > 0:
            logger.info(f"🎨 Applied {applied_count}/{len(effects)} default effects to clip {clip_id}")
        
        return applied_count
    
    def get_example_config(self) -> Dict[str, Any]:
        """
        Get example configuration for documentation.
        
        Returns:
            Example config dictionary
        """
        return {
            "effects": {
                "video": [
                    {
                        "plugin_id": "brightness",
                        "params": {"brightness": 1.2}
                    },
                    {
                        "plugin_id": "color_balance",
                        "params": {"red": 1.1, "green": 1.0, "blue": 0.9}
                    }
                ],
                "artnet": [
                    {
                        "plugin_id": "hue_shift",
                        "params": {"shift": 30}
                    }
                ],
                "clips": {
                    "kanal_1/intro.mp4": [
                        {
                            "plugin_id": "fade_in",
                            "params": {"duration": 2.0}
                        }
                    ],
                    "a1b2c3d4-uuid-here": [
                        {
                            "plugin_id": "strobe",
                            "params": {"frequency": 5}
                        }
                    ]
                }
            }
        }


def get_default_effects_manager(config: Dict[str, Any], plugin_manager) -> DefaultEffectsManager:
    """
    Factory function to create DefaultEffectsManager instance.
    
    Args:
        config: Application configuration
        plugin_manager: Plugin manager instance
        
    Returns:
        DefaultEffectsManager instance
    """
    return DefaultEffectsManager(config, plugin_manager)
