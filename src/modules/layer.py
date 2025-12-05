"""
Layer - Einzelne Compositing-Ebene im Multi-Layer System

Ein Layer kapselt eine Frame-Quelle (Video/Generator/Script) zusammen mit
seinen spezifischen Effekten und Compositing-Einstellungen.
"""

import numpy as np
from typing import Optional, List, Dict, Any
from .logger import get_logger

logger = get_logger(__name__)


class Layer:
    """
    Einzelne Layer-Ebene für Multi-Layer Compositing.
    
    Ein Layer besteht aus:
    - Frame-Quelle (VideoSource, GeneratorSource)
    - Layer-spezifische Effekte
    - Compositing-Einstellungen (Blend Mode, Opacity)
    - Metadaten (Clip-ID, enabled-Status)
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
        Initialisiert einen neuen Layer.
        
        Args:
            layer_id: Eindeutige Layer-ID innerhalb des Players
            source: FrameSource-Instanz (VideoSource, GeneratorSource, etc.)
            blend_mode: Blend-Modus für Compositing ('normal', 'multiply', 'screen', etc.)
            opacity: Layer-Opazität in Prozent (0-100)
            clip_id: Optional UUID aus ClipRegistry für Effekt-Management
        """
        self.layer_id = layer_id
        self.source = source
        self.blend_mode = blend_mode
        self.opacity = opacity
        self.clip_id = clip_id
        self.enabled = True
        
        # Layer-spezifische Effekte (Liste von {id, instance, config})
        self.effects: List[Dict[str, Any]] = []
        
        # Cache für letztes Frame (für HOLD-Mode oder Frame-Blending)
        self.last_frame: Optional[np.ndarray] = None
        
        logger.debug(
            f"Layer {layer_id} created: {source.get_source_name()} "
            f"(blend={blend_mode}, opacity={opacity}%)"
        )
    
    def get_source_name(self) -> str:
        """Gibt den Namen der Source zurück."""
        return self.source.get_source_name() if self.source else "No Source"
    
    def get_source_type(self) -> str:
        """Gibt den Typ der Source zurück."""
        return type(self.source).__name__
    
    def cleanup(self):
        """Räumt Layer-Ressourcen auf (z.B. bei Entfernung)."""
        if self.source:
            self.source.cleanup()
        self.effects.clear()
        self.last_frame = None
        logger.debug(f"Layer {self.layer_id} cleaned up")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialisiert Layer zu Dict (für API/Session State).
        
        Returns:
            Dict mit Layer-Konfiguration
        """
        # Bestimme Source-Typ und Pfad
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
        
        # Effekte serialisieren (ohne instance)
        layer_dict['effects'] = [
            {
                'plugin_id': effect['id'],
                'parameters': effect.get('config', {})
            }
            for effect in self.effects
        ]
        
        return layer_dict
    
    def __repr__(self) -> str:
        """String-Repräsentation für Debugging."""
        enabled_str = "enabled" if self.enabled else "disabled"
        return (
            f"Layer(id={self.layer_id}, source={self.get_source_name()}, "
            f"blend={self.blend_mode}, opacity={self.opacity}%, {enabled_str})"
        )
