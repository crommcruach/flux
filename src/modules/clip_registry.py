"""
Clip Registry - Zentrales Management von Video-Clips mit eindeutigen IDs.

Ermöglicht:
- Eindeutige Identifikation von Clips unabhängig vom Dateinamen
- Mehrfache Verwendung desselben Videos in verschiedenen Playern
- Clip-spezifische Metadaten und Effekte
"""

import uuid
import os
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ClipRegistry:
    """Zentrale Registry für Video-Clips mit UUID-basierter Identifikation."""
    
    def __init__(self):
        """Initialisiert die Clip-Registry."""
        # Mapping: clip_id (UUID) -> clip_data
        self.clips: Dict[str, Dict] = {}
        
        # Version tracking for cache invalidation (B3 Performance Optimization)
        self._clip_effects_version: Dict[str, int] = {}  # clip_id -> version_counter
        
        # Optional: Default effects manager for auto-applying effects
        self._default_effects_manager = None
    
    def register_clip(
        self, 
        player_id: str, 
        absolute_path: str, 
        relative_path: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Registriert einen neuen Clip mit eindeutiger UUID.
        Jeder Call erzeugt eine NEUE Clip-Instanz, auch bei gleichem Pfad.
        
        Args:
            player_id: ID des Players ('video' oder 'artnet')
            absolute_path: Absoluter Pfad zur Video-Datei
            relative_path: Relativer Pfad (für UI)
            metadata: Optionale Metadaten (fps, duration, etc.)
        
        Returns:
            clip_id: Eindeutige UUID für diesen Clip
        """
        # Erstelle IMMER neue Clip-ID (jede Playlist-Instanz ist unabhängig)
        clip_id = str(uuid.uuid4())
        
        # Speichere Clip-Daten
        self.clips[clip_id] = {
            'clip_id': clip_id,
            'player_id': player_id,
            'absolute_path': absolute_path,
            'relative_path': relative_path,
            'filename': os.path.basename(absolute_path),
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'effects': [],  # Clip-spezifische Effekte
            'layers': [],   # Clip-spezifische Layer-Definitionen
            # Trimming & Playback Control
            'in_point': None,   # Start-Frame (None = Video-Start)
            'out_point': None,  # End-Frame (None = Video-Ende)
            'reverse': False    # Rückwärts abspielen
        }
        
        logger.info(f"✅ Clip registriert: {clip_id} → {player_id}/{os.path.basename(absolute_path)}")
        
        # Auto-apply default effects if manager is configured
        if self._default_effects_manager:
            try:
                logger.debug(f"🔧 Attempting to apply default effects to clip {clip_id}")
                applied = self._default_effects_manager.apply_to_clip(self, clip_id)
                if applied > 0:
                    logger.info(f"🎨 Auto-applied {applied} default effects to new clip {clip_id}")
                else:
                    logger.debug(f"ℹ️ No default effects configured for clips")
            except Exception as e:
                logger.warning(f"⚠️ Failed to auto-apply default effects: {e}")
                import traceback
                logger.debug(traceback.format_exc())
        else:
            logger.debug(f"ℹ️ No default effects manager configured")
        
        return clip_id
    
    def get_clip(self, clip_id: str) -> Optional[Dict]:
        """
        Holt Clip-Daten anhand der ID.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Clip-Daten oder None wenn nicht gefunden
        """
        return self.clips.get(clip_id)
    
    def find_clip_by_path(self, player_id: str, absolute_path: str) -> Optional[str]:
        """
        Findet ERSTE Clip-ID anhand von Player-ID und Pfad.
        HINWEIS: Mehrere Clips können denselben Pfad haben!
        Gibt nur den ersten gefundenen Clip zurück.
        
        Args:
            player_id: ID des Players
            absolute_path: Absoluter Pfad zur Video-Datei
        
        Returns:
            clip_id oder None wenn nicht gefunden
        """
        # Suche in allen Clips (kann mehrere mit gleichem Pfad geben)
        for clip_id, clip_data in self.clips.items():
            if clip_data['player_id'] == player_id and clip_data['absolute_path'] == absolute_path:
                return clip_id
        return None
    
    def get_clips_for_player(self, player_id: str) -> List[Dict]:
        """
        Holt alle Clips eines bestimmten Players.
        
        Args:
            player_id: ID des Players
        
        Returns:
            Liste von Clip-Daten
        """
        return [
            clip for clip in self.clips.values()
            if clip['player_id'] == player_id
        ]
    
    def _invalidate_cache(self, clip_id: str) -> None:
        """
        Invalidiert Effect-Cache für einen Clip durch Erhöhung des Version-Counters.
        Wird bei allen Änderungen an Effekten aufgerufen (add, remove, update, clear).
        
        Args:
            clip_id: Eindeutige Clip-ID
        """
        current_version = self._clip_effects_version.get(clip_id, 0)
        self._clip_effects_version[clip_id] = current_version + 1
        logger.debug(f"🔄 Cache invalidated for clip {clip_id} (version: {current_version} → {current_version + 1})")
    
    def get_effects_version(self, clip_id: str) -> int:
        """
        Gibt die aktuelle Version des Effect-Cache für einen Clip zurück.
        Player nutzen dies für Version-basierte Cache-Invalidierung.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Version-Counter (0 wenn Clip nicht existiert oder keine Version)
        """
        return self._clip_effects_version.get(clip_id, 0)
    
    def set_default_effects_manager(self, manager):
        """
        Setzt den Default Effects Manager für Auto-Apply bei Clip-Registrierung.
        
        Args:
            manager: DefaultEffectsManager instance
        """
        self._default_effects_manager = manager
        logger.info("🎨 Default Effects Manager configured for ClipRegistry")
    
    def unregister_clip(self, clip_id: str) -> bool:
        """
        Entfernt einen Clip aus der Registry.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            True wenn erfolgreich entfernt
        """
        if clip_id not in self.clips:
            return False
        
        clip_data = self.clips[clip_id]
        index_key = (clip_data['player_id'], clip_data['absolute_path'])
        
        # Entferne aus beiden Datenstrukturen
        del self.clips[clip_id]
        if index_key in self._path_index:
            del self._path_index[index_key]
        
        logger.info(f"🗑️ Clip unregistriert: {clip_id}")
        return True
    
    def add_effect_to_clip(self, clip_id: str, effect_data: Dict) -> bool:
        """
        Fügt einen Effekt zu einem Clip hinzu.
        
        Args:
            clip_id: Eindeutige Clip-ID
            effect_data: Effekt-Daten (plugin_id, parameters, etc.)
        
        Returns:
            True wenn erfolgreich hinzugefügt
        """
        if clip_id not in self.clips:
            logger.error(f"Clip nicht gefunden: {clip_id}")
            return False
        
        self.clips[clip_id]['effects'].append(effect_data)
        self._invalidate_cache(clip_id)  # B3: Cache invalidieren
        logger.debug(f"Effekt zu Clip hinzugefügt: {clip_id} → {effect_data.get('plugin_id')}")
        return True
    
    def get_clip_effects(self, clip_id: str) -> List[Dict]:
        """
        Holt alle Effekte eines Clips.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Liste von Effekt-Daten
        """
        if clip_id not in self.clips:
            return []
        
        return self.clips[clip_id].get('effects', [])
    
    def remove_effect_from_clip(self, clip_id: str, effect_index: int) -> bool:
        """
        Entfernt einen Effekt von einem Clip.
        
        Args:
            clip_id: Eindeutige Clip-ID
            effect_index: Index des zu entfernenden Effekts
        
        Returns:
            True wenn erfolgreich entfernt
        """
        if clip_id not in self.clips:
            return False
        
        effects = self.clips[clip_id]['effects']
        if 0 <= effect_index < len(effects):
            removed = effects.pop(effect_index)
            self._invalidate_cache(clip_id)  # B3: Cache invalidieren
            logger.debug(f"Effekt von Clip entfernt: {clip_id} → {removed.get('plugin_id')}")
            return True
        
        return False
    
    def clear_clip_effects(self, clip_id: str) -> bool:
        """
        Entfernt alle Effekte von einem Clip.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        self.clips[clip_id]['effects'] = []
        self._invalidate_cache(clip_id)  # B3: Cache invalidieren
        logger.debug(f"Alle Effekte von Clip entfernt: {clip_id}")
        return True
    
    def update_clip_metadata(self, clip_id: str, metadata: Dict) -> bool:
        """
        Aktualisiert Metadaten eines Clips.
        
        Args:
            clip_id: Eindeutige Clip-ID
            metadata: Neue/aktualisierte Metadaten
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        self.clips[clip_id]['metadata'].update(metadata)
        return True
    
    # ========================================
    # LAYER MANAGEMENT (Clip-based)
    # ========================================
    
    def add_layer_to_clip(self, clip_id: str, layer_config: Dict) -> Optional[int]:
        """
        Fügt einen Layer zu einem Clip hinzu.
        
        Args:
            clip_id: Eindeutige Clip-ID
            layer_config: Layer-Konfiguration {
                'source_type': 'video' | 'generator' | 'script',
                'source_path': path or generator_id,
                'blend_mode': 'normal' | 'multiply' | ...,
                'opacity': float (0.0-1.0),
                'enabled': bool
            }
        
        Returns:
            layer_id (index) oder None bei Fehler
        """
        if clip_id not in self.clips:
            logger.error(f"Clip nicht gefunden: {clip_id}")
            return None
        
        layers = self.clips[clip_id]['layers']
        # Layer 0 is always the base clip, so start additional layers at 1
        layer_id = len(layers) + 1
        
        # Füge layer_id hinzu
        layer_config['layer_id'] = layer_id
        layers.append(layer_config)
        
        logger.info(f"✅ Layer {layer_id} zu Clip {clip_id} hinzugefügt: {layer_config['source_type']}")
        return layer_id
    
    def get_clip_layers(self, clip_id: str) -> List[Dict]:
        """
        Holt alle Layer eines Clips.
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            Liste von Layer-Konfigurationen
        """
        if clip_id not in self.clips:
            return []
        
        return self.clips[clip_id].get('layers', [])
    
    def update_clip_layer(self, clip_id: str, layer_id: int, updates: Dict) -> bool:
        """
        Aktualisiert Layer-Konfiguration.
        
        Args:
            clip_id: Eindeutige Clip-ID
            layer_id: Layer-ID (NOT index)
            updates: Dict mit zu aktualisierenden Feldern
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        # Layer 0 is the base clip - cannot be updated in registry
        if layer_id == 0:
            logger.warning(f"Layer 0 is the base clip - cannot be updated in registry")
            return False
        
        layers = self.clips[clip_id]['layers']
        
        # Find layer by layer_id
        layer = next((l for l in layers if l['layer_id'] == layer_id), None)
        if not layer:
            logger.warning(f"Layer {layer_id} not found in clip {clip_id}")
            return False
        
        old_opacity = layer.get('opacity', 'N/A')
        layer.update(updates)
        new_opacity = layer.get('opacity', 'N/A')
        
        if 'opacity' in updates:
            logger.info(f"💾 Layer {layer_id} opacity updated in registry: {old_opacity} → {new_opacity}")
        
        logger.debug(f"Layer {layer_id} von Clip {clip_id} aktualisiert: {updates}")
        return True
    
    def remove_layer_from_clip(self, clip_id: str, layer_id: int) -> bool:
        """
        Entfernt einen Layer von einem Clip.
        
        Args:
            clip_id: Eindeutige Clip-ID
            layer_id: Layer-ID (NOT index)
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        # Layer 0 is the base clip - CANNOT be removed
        if layer_id == 0:
            logger.warning(f"Layer 0 is the base clip - cannot be removed")
            return False
        
        layers = self.clips[clip_id]['layers']
        
        # Find layer by layer_id
        layer_index = next((i for i, l in enumerate(layers) if l['layer_id'] == layer_id), None)
        if layer_index is None:
            logger.warning(f"Layer {layer_id} not found in clip {clip_id}")
            return False
        
        removed = layers.pop(layer_index)
        logger.info(f"✅ Layer {layer_id} von Clip {clip_id} entfernt: {removed.get('source_path')}")
        return True
    
    def reorder_clip_layers(self, clip_id: str, new_order: List[int]) -> bool:
        """
        Sortiert Layer eines Clips um.
        
        Args:
            clip_id: Eindeutige Clip-ID
            new_order: Liste von Layer-IDs in neuer Reihenfolge (excluding Layer 0 which is always base)
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        layers = self.clips[clip_id]['layers']
        
        # Filter out Layer 0 from new_order (it's not in registry)
        registry_order = [lid for lid in new_order if lid != 0]
        
        # Get current layer_ids in registry
        current_ids = [l['layer_id'] for l in layers]
        
        # Validate: new_order must contain exactly the same layer_ids
        if set(registry_order) != set(current_ids):
            logger.warning(f"Invalid reorder: expected {current_ids}, got {registry_order}")
            return False
        
        # Build layer_id -> layer mapping
        layer_map = {l['layer_id']: l for l in layers}
        
        # Reorder by new_order
        new_layers = [layer_map[lid] for lid in registry_order]
        
        self.clips[clip_id]['layers'] = new_layers
        logger.debug(f"Layers von Clip {clip_id} neu sortiert: {registry_order}")
        return True


# Globale Singleton-Instanz
_clip_registry: Optional[ClipRegistry] = None


def get_clip_registry() -> ClipRegistry:
    """
    Singleton-Getter für ClipRegistry.
    
    Returns:
        Globale ClipRegistry-Instanz
    """
    global _clip_registry
    if _clip_registry is None:
        _clip_registry = ClipRegistry()
        logger.info("📋 ClipRegistry initialisiert")
    return _clip_registry
