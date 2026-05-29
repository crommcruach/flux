"""
Layer - Single compositing layer in the multi-layer system

A layer encapsulates a frame source (video/generator/script) together with
its specific effects and compositing settings.
"""

import numpy as np
from typing import Optional, List, Dict, Any
from ...core.logger import get_logger, debug_layers

logger = get_logger(__name__)


class Layer:
    """
    Single layer for multi-layer compositing.
    
    A layer consists of:
    - Frame source (VideoSource, GeneratorSource)
    - Layer-specific effects
    - Compositing settings (blend mode, opacity)
    - Metadata (clip ID, enabled status)
    """
    
    def __init__(
        self,
        layer_id: int,
        source,
        blend_mode: str = 'normal',
        opacity: float = 100.0,
        clip_id: Optional[str] = None
    ):
        """
        Initializes a new layer.
        
        Args:
            layer_id: Unique layer ID within the player
            source: FrameSource instance (VideoSource, GeneratorSource, etc.)
            blend_mode: Blend mode for compositing ('normal', 'multiply', 'screen', etc.)
            opacity: Layer opacity in percent (0-100)
            clip_id: Optional UUID from ClipRegistry for effect management
        """
        self.layer_id = layer_id
        self.source = source
        self.blend_mode = blend_mode
        self.opacity = opacity
        self.clip_id = clip_id
        self.name: str = ""
        self.enabled = True
        
        # Layer-spezifische Effekte (Liste von {id, instance, config})
        self.effects: List[Dict[str, Any]] = []
        
        # Cache for last frame (for HOLD mode or frame blending)
        self.last_frame: Optional[np.ndarray] = None
        
        debug_layers(
            logger,
            f"Layer {layer_id} created: {source.get_source_name()} "
            f"(blend={blend_mode}, opacity={opacity}%)"
        )
    
    def get_source_name(self) -> str:
        """Returns the name of the source."""
        return self.source.get_source_name() if self.source else "No Source"
    
    def get_source_type(self) -> str:
        """Returns the type of the source."""
        return type(self.source).__name__
    
    def cleanup(self):
        """Cleans up layer resources (e.g. when removed)."""
        if self.source:
            self.source.cleanup()
        self.effects.clear()
        self.last_frame = None
        debug_layers(logger, f"Layer {self.layer_id} cleaned up")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serializes layer to dict (for API/session state).
        
        Returns:
            Dict with layer configuration
        """
        # Determine source type and path
        source_type = "unknown"
        source_path = ""
        generator_id = None
        parameters = {}
        
        if hasattr(self.source, 'video_path'):
            source_type = "video"
            source_path = self.source.video_path
        elif hasattr(self.source, 'script_name'):
            source_type = "script"
            source_path = f"script:{self.source.script_name}"
        elif hasattr(self.source, 'generator_id'):
            source_type = "generator"
            generator_id = self.source.generator_id
            source_path = f"generator:{generator_id}"
            parameters = getattr(self.source, 'parameters', {})
        
        layer_dict = {
            'layer_id': self.layer_id,
            'name': self.name,
            'type': source_type,
            'path': source_path,
            'blend_mode': self.blend_mode,
            'opacity': self.opacity,
            'enabled': self.enabled,
            'clip_id': self.clip_id
        }
        
        # Generator-spezifische Felder
        if source_type == 'generator':
            layer_dict['generator_id'] = generator_id
            layer_dict['parameters'] = parameters
        
        # Serialize effects (without instance)
        layer_dict['effects'] = [
            {
                'plugin_id': effect['id'],
                'parameters': effect.get('config', {})
            }
            for effect in self.effects
        ]
        
        return layer_dict
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        enabled_str = "enabled" if self.enabled else "disabled"
        return (
            f"Layer(id={self.layer_id}, source={self.get_source_name()}, "
            f"blend={self.blend_mode}, opacity={self.opacity}%, {enabled_str})"
        )
