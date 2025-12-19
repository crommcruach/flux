"""
Transition Effect Plugin
Allows clips to override playlist default transition settings.
"""

from ..plugin_base import PluginBase, PluginType, ParameterType
import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


def _load_available_transitions():
    """Load all available transition plugins from plugins/transitions/."""
    transitions = {}
    transitions_dir = Path('plugins/transitions')
    
    if not transitions_dir.exists():
        logger.warning("Transitions directory not found")
        return {'none': 'No Transition'}
    
    # Scan for transition plugins
    for file in transitions_dir.glob('*.py'):
        if file.name.startswith('__'):
            continue
        
        plugin_name = file.stem
        # Convert filename to label (e.g., 'fade_transition' -> 'Fade Transition')
        label = ' '.join(word.capitalize() for word in plugin_name.replace('_transition', '').split('_'))
        transitions[plugin_name] = label
    
    # Always include 'none' option
    transitions['none'] = 'No Transition'
    
    logger.info(f"Loaded {len(transitions)} transition options")
    return transitions


def _build_parameters():
    """Build PARAMETERS list with discovered transitions."""
    transitions = _load_available_transitions()
    
    # Build options as simple string array (frontend expects strings, not objects)
    options = ['none']  # Start with 'none' option
    for plugin_name in sorted(transitions.keys()):
        if plugin_name != 'none':
            options.append(plugin_name)
    
    # Get default
    default_plugin = 'none'
    if 'fade' in transitions:
        default_plugin = 'fade'
    elif len(transitions) > 1:
        for key in transitions.keys():
            if key != 'none':
                default_plugin = key
                break
    
    return [
        {
            'name': 'plugin',
            'label': 'Transition Plugin',
            'type': ParameterType.SELECT,
            'default': default_plugin,
            'options': options,
            'description': 'Transition effect to use for this clip'
        },
        {
            'name': 'duration',
            'label': 'Duration (seconds)',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Duration of the transition effect'
        },
        {
            'name': 'easing',
            'label': 'Easing',
            'type': ParameterType.SELECT,
            'default': 'ease_in_out',
            'options': ['linear', 'ease_in', 'ease_out', 'ease_in_out'],
            'description': 'Easing curve for the transition'
        }
    ]


class TransitionEffect(PluginBase):
    """Clip-level transition override effect."""
    
    # Plugin metadata
    METADATA = {
        'id': 'transition',
        'name': 'Transition',
        'description': 'Override playlist transition for this clip',
        'author': 'Flux',
        'version': '1.0.0',
        'type': PluginType.EFFECT
    }
    
    # Parameters - built dynamically with discovered transitions
    PARAMETERS = _build_parameters()
    
    def __init__(self, config=None):
        # Initialize instance parameters with defaults
        self.plugin = 'fade'
        self.duration = 1.0
        self.easing = 'ease_in_out'
        
        # Call parent init which will call our initialize() method
        super().__init__(config)
    
    # ========================================
    # REQUIRED ABSTRACT METHODS
    # ========================================
    
    def initialize(self, config):
        """Initialize plugin with configuration."""
        self.plugin = self._get_param_value('plugin', 'fade')
        self.duration = self._get_param_value('duration', 1.0)
        self.easing = self._get_param_value('easing', 'ease_in_out')
        logger.debug(f"Transition effect initialized: plugin={self.plugin}, duration={self.duration}s")
    
    def update_parameter(self, name, value):
        """Update a parameter at runtime."""
        if name == 'plugin':
            self.plugin = value
            return True
        elif name == 'duration':
            # Extract value from range metadata if present
            if isinstance(value, dict) and '_value' in value:
                self.duration = float(value['_value'])
            else:
                self.duration = float(value)
            return True
        elif name == 'easing':
            self.easing = value
            return True
        return False
    
    def get_parameters(self):
        """Get current parameter values."""
        return {
            'plugin': self.plugin,
            'duration': self.duration,
            'easing': self.easing
        }
    
    # ========================================
    # EFFECT PROCESSING
    # ========================================
    
    def process_frame(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """
        This effect doesn't process frames - it only provides config.
        Actual transition is handled by TransitionManager.
        """
        return frame
    
    def get_transition_config(self, parameters=None):
        """
        Extract transition configuration from effect parameters.
        
        Args:
            parameters: Optional effect parameters dict, uses current values if None
            
        Returns:
            dict: Transition config {enabled, plugin, duration, easing}
        """
        if parameters is None:
            parameters = self.get_parameters()
        
        plugin = parameters.get('plugin', 'fade')
        
        if plugin == 'none':
            logger.debug("🎬 Transition effect: None (no transition)")
            return None
        
        config = {
            'enabled': plugin != 'none',
            'plugin': plugin if plugin != 'none' else None,
            'duration': parameters.get('duration', 1.0),
            'easing': parameters.get('easing', 'ease_in_out')
        }
        logger.debug(f"🎬 Transition effect config: {config}")
        return config


# Plugin entry point
def create_plugin():
    """Factory function to create plugin instance."""
    import numpy as np
    return TransitionEffect()
