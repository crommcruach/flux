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
        IDEMPOTENT: Wenn Clip bereits existiert (player_id + absolute_path), 
        wird die existierende clip_id zurückgegeben (OHNE Daten zu überschreiben).
        
        Args:
            player_id: ID des Players ('video' oder 'artnet')
            absolute_path: Absoluter Pfad zur Video-Datei
            relative_path: Relativer Pfad (für UI)
            metadata: Optionale Metadaten (fps, duration, etc.)
        
        Returns:
            clip_id: Eindeutige UUID für diesen Clip
        """
        # CRITICAL FIX: Check if clip already exists (for session restore)
        # When restoring from saved state, clips are already in registry with effects/layers
        # We must NOT overwrite them with fresh registrations!
        existing_clip_id = self.find_clip_by_path(player_id, absolute_path)
        if existing_clip_id:
            logger.debug(f"🔄 Clip already registered: {existing_clip_id} → {player_id}/{os.path.basename(absolute_path)} (reusing existing data)")
            return existing_clip_id
        
        # Create NEW clip only if it doesn't exist yet
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
            'sequences': {},  # Clip-spezifische Sequences: {uid: [sequence_ids]}
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
        # Normalize path for comparison (handle forward/backward slashes, case)
        normalized_search_path = os.path.normpath(absolute_path).lower()
        
        # Also try matching by filename if exact match fails (for path prefix mismatches)
        search_filename = os.path.basename(normalized_search_path)
        
        # Suche in allen Clips (kann mehrere mit gleichem Pfad geben)
        for clip_id, clip_data in self.clips.items():
            if clip_data['player_id'] == player_id:
                normalized_clip_path = os.path.normpath(clip_data['absolute_path']).lower()
                
                # Try exact path match first
                if normalized_clip_path == normalized_search_path:
                    return clip_id
                
                # Try suffix match (e.g., "converted\test.mov" matches "video\converted\test.mov")
                if normalized_clip_path.endswith(normalized_search_path) or normalized_search_path.endswith(normalized_clip_path):
                    logger.debug(f"🔍 Found clip by suffix match: {clip_data['absolute_path']} ≈ {absolute_path}")
                    return clip_id
                
                # Last resort: match by filename only (weakest match, only if path components match)
                clip_filename = os.path.basename(normalized_clip_path)
                if clip_filename == search_filename:
                    # Verify filename matches and paths overlap
                    logger.debug(f"🔍 Found clip by filename match: {clip_data['absolute_path']} ≈ {absolute_path}")
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
        Entfernt alle Effekte von einem Clip, außer system_plugins (z.B. transport).
        
        Args:
            clip_id: Eindeutige Clip-ID
        
        Returns:
            True wenn erfolgreich
        """
        if clip_id not in self.clips:
            return False
        
        # Keep system plugins (e.g. transport)
        system_effects = [
            effect for effect in self.clips[clip_id]['effects']
            if effect.get('metadata', {}).get('system_plugin', False)
        ]
        
        self.clips[clip_id]['effects'] = system_effects
        self._invalidate_cache(clip_id)  # B3: Cache invalidieren
        
        removed_count = len(self.clips[clip_id]['effects']) - len(system_effects)
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} effects from clip {clip_id}, kept {len(system_effects)} system plugins")
        else:
            logger.debug(f"No user effects to remove from clip {clip_id} (kept {len(system_effects)} system plugins)")
        
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
    
    def update_clip_effect_parameter(self, clip_id: str, effect_index: int, param_name: str, value) -> bool:
        """
        Updates a specific parameter of a clip effect in the registry.
        
        Args:
            clip_id: Unique clip ID
            effect_index: Index of effect in clip's effects array
            param_name: Name of parameter to update
            value: New parameter value
        
        Returns:
            True if successful
        """
        if clip_id not in self.clips:
            logger.debug(f"Clip not found in registry: {clip_id}")
            return False
        
        effects = self.clips[clip_id].get('effects', [])
        if effect_index < 0 or effect_index >= len(effects):
            logger.debug(f"Invalid effect index {effect_index} for clip {clip_id}")
            return False
        
        effect = effects[effect_index]
        if 'parameters' not in effect:
            effect['parameters'] = {}
        
        effect['parameters'][param_name] = value
        
        # Increment version for cache invalidation
        if clip_id in self._clip_effects_version:
            self._clip_effects_version[clip_id] += 1
        else:
            self._clip_effects_version[clip_id] = 1
        
        logger.debug(f"📝 Updated clip {clip_id} effect {effect_index} parameter '{param_name}' = {value}")
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
        
        # If layer_config already has layer_id, use it (from layer_manager)
        # Otherwise assign next available ID (Layer 0 is always the base clip, so start at 1)
        if 'layer_id' not in layer_config:
            layer_id = len(layers) + 1
            layer_config['layer_id'] = layer_id
        else:
            layer_id = layer_config['layer_id']
        
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
    def add_sequence_to_effect(self, clip_id: str, effect_index: int, param_name: str, sequence_config: Dict, layer_index: Optional[int] = None) -> bool:
        """
        Add a sequence to an effect parameter (NEW ARCHITECTURE)
        
        Args:
            clip_id: Clip UUID
            effect_index: Index of effect in clip's effects list
            param_name: Parameter name (e.g., 'scale_xy')
            sequence_config: Full sequence configuration dict
            layer_index: Optional layer index (None = clip-level effect)
        
        Returns:
            True if successful
        """
        if clip_id not in self.clips:
            logger.warning(f"Cannot add sequence to non-existent clip: {clip_id}")
            return False
        
        clip = self.clips[clip_id]
        
        # Get target effect list (clip-level or layer-level)
        if layer_index is not None:
            if layer_index >= len(clip.get('layers', [])):
                logger.warning(f"Layer {layer_index} not found in clip {clip_id}")
                return False
            effects = clip['layers'][layer_index].get('effects', [])
        else:
            effects = clip.get('effects', [])
        
        if effect_index >= len(effects):
            logger.warning(f"Effect index {effect_index} out of range for clip {clip_id}")
            return False
        
        effect = effects[effect_index]
        
        # Initialize sequences dict if needed
        if 'sequences' not in effect:
            effect['sequences'] = {}
        
        # Store sequence config
        effect['sequences'][param_name] = sequence_config
        
        location = f"layer {layer_index}, " if layer_index is not None else ""
        logger.debug(f"Added sequence to clip {clip_id[:8]}..., {location}effect {effect_index}, param {param_name}")
        
        return True
    
    def remove_sequence_from_effect(self, clip_id: str, effect_index: int, param_name: str, layer_index: Optional[int] = None) -> bool:
        """
        Remove a sequence from an effect parameter (NEW ARCHITECTURE)
        
        Args:
            clip_id: Clip UUID
            effect_index: Index of effect in clip's effects list
            param_name: Parameter name
            layer_index: Optional layer index
        
        Returns:
            True if removed
        """
        if clip_id not in self.clips:
            return False
        
        clip = self.clips[clip_id]
        
        # Get target effect list
        if layer_index is not None:
            if layer_index >= len(clip.get('layers', [])):
                return False
            effects = clip['layers'][layer_index].get('effects', [])
        else:
            effects = clip.get('effects', [])
        
        if effect_index >= len(effects):
            return False
        
        effect = effects[effect_index]
        
        if 'sequences' in effect and param_name in effect['sequences']:
            del effect['sequences'][param_name]
            logger.debug(f"Removed sequence from clip {clip_id[:8]}..., effect {effect_index}, param {param_name}")
            return True
        
        return False
    
    def get_effect_sequences(self, clip_id: str, effect_index: int, layer_index: Optional[int] = None) -> Dict[str, Dict]:
        """
        Get all sequences for an effect (NEW ARCHITECTURE)
        
        Args:
            clip_id: Clip UUID
            effect_index: Index of effect
            layer_index: Optional layer index
        
        Returns:
            Dict mapping param_name to sequence_config
        """
        if clip_id not in self.clips:
            return {}
        
        clip = self.clips[clip_id]
        
        # Get target effect list
        if layer_index is not None:
            if layer_index >= len(clip.get('layers', [])):
                return {}
            effects = clip['layers'][layer_index].get('effects', [])
        else:
            effects = clip.get('effects', [])
        
        if effect_index >= len(effects):
            return {}
        
        return effects[effect_index].get('sequences', {})
    
    def get_all_clip_sequences(self, clip_id: str) -> List[Dict]:
        """
        Get ALL sequences from a clip (all effects, all layers) (NEW ARCHITECTURE)
        
        Returns list of dicts with:
        - sequence_config: The sequence configuration
        - effect_index: Index of effect
        - layer_index: Index of layer (None for clip-level)
        - param_name: Parameter name
        - plugin_id: Plugin ID for context
        """
        if clip_id not in self.clips:
            return []
        
        clip = self.clips[clip_id]
        all_sequences = []
        
        # Clip-level effects
        for effect_idx, effect in enumerate(clip.get('effects', [])):
            for param_name, seq_config in effect.get('sequences', {}).items():
                all_sequences.append({
                    'sequence_config': seq_config,
                    'effect_index': effect_idx,
                    'layer_index': None,
                    'param_name': param_name,
                    'plugin_id': effect.get('plugin_id', 'unknown')
                })
        
        # Layer-level effects
        for layer_idx, layer in enumerate(clip.get('layers', [])):
            for effect_idx, effect in enumerate(layer.get('effects', [])):
                for param_name, seq_config in effect.get('sequences', {}).items():
                    all_sequences.append({
                        'sequence_config': seq_config,
                        'effect_index': effect_idx,
                        'layer_index': layer_idx,
                        'param_name': param_name,
                        'plugin_id': effect.get('plugin_id', 'unknown')
                    })
        
        return all_sequences
    
    def add_sequence_to_clip(self, clip_id: str, sequence_id: str, target_uid: str) -> bool:
        """
        Add a sequence to a clip
        
        Args:
            clip_id: Clip UUID
            sequence_id: Sequence ID
            target_uid: Parameter UID this sequence targets
        
        Returns:
            True if successful
        """
        if clip_id not in self.clips:
            logger.warning(f"Cannot add sequence to non-existent clip: {clip_id}")
            return False
        
        if 'sequences' not in self.clips[clip_id]:
            self.clips[clip_id]['sequences'] = {}
        
        if target_uid not in self.clips[clip_id]['sequences']:
            self.clips[clip_id]['sequences'][target_uid] = []
        
        if sequence_id not in self.clips[clip_id]['sequences'][target_uid]:
            self.clips[clip_id]['sequences'][target_uid].append(sequence_id)
            logger.debug(f"Added sequence {sequence_id} to clip {clip_id[:8]}... (UID: {target_uid[:50]}...)")
            return True
        
        return False
    
    def remove_sequence_from_clip(self, clip_id: str, sequence_id: str) -> bool:
        """
        Remove a sequence from a clip
        
        Args:
            clip_id: Clip UUID
            sequence_id: Sequence ID to remove
        
        Returns:
            True if removed
        """
        if clip_id not in self.clips or 'sequences' not in self.clips[clip_id]:
            return False
        
        removed = False
        for uid, seq_list in list(self.clips[clip_id]['sequences'].items()):
            if sequence_id in seq_list:
                seq_list.remove(sequence_id)
                removed = True
                if not seq_list:  # Remove empty list
                    del self.clips[clip_id]['sequences'][uid]
                logger.debug(f"Removed sequence {sequence_id} from clip {clip_id[:8]}...")
        
        return removed
    
    def get_clip_sequences(self, clip_id: str) -> Dict[str, List[str]]:
        """
        Get all sequences for a clip
        
        Args:
            clip_id: Clip UUID
        
        Returns:
            Dict mapping UIDs to sequence IDs
        """
        if clip_id not in self.clips:
            return {}
        
        return self.clips[clip_id].get('sequences', {})
    
    def serialize(self) -> Dict:
        """
        Serialize the entire clip registry to a dictionary.
        This saves the complete state including all clips, effects, and parameters.
        
        Returns:
            Dictionary containing complete registry state
        """
        # DEBUG: Log actual parameter values in memory before serializing
        for clip_id, clip_data in self.clips.items():
            if 'effects' in clip_data:
                logger.info(f"[SERIALIZE DEBUG] Clip {clip_id[:8]}... has {len(clip_data['effects'])} effects in memory")
                for i, effect in enumerate(clip_data['effects']):
                    if 'parameters' in effect:
                        for param_name, param_value in list(effect['parameters'].items())[:5]:
                            logger.info(f"[SERIALIZE DEBUG]   effect[{i}].{param_name} = {param_value}")
        
        return {
            'clips': self.clips.copy(),
            'effects_versions': self._clip_effects_version.copy()
        }
    
    def deserialize(self, data: Dict) -> None:
        """
        Restore the clip registry from serialized data.
        This completely replaces the current registry state.
        
        Args:
            data: Dictionary containing registry state from serialize()
        """
        if not data:
            logger.warning("⚠️ No clip registry data to deserialize")
            return
        
        self.clips = data.get('clips', {}).copy()
        self._clip_effects_version = data.get('effects_versions', {}).copy()
        
        # Rebuild path index from clips
        self._path_index = {}
        for clip_id, clip_data in self.clips.items():
            index_key = (clip_data['player_id'], clip_data['absolute_path'])
            self._path_index[index_key] = clip_id
        
        # DEBUG: Log layer counts after deserialize
        total_layers = sum(len(clip.get('layers', [])) for clip in self.clips.values())
        clips_with_layers = sum(1 for clip in self.clips.values() if len(clip.get('layers', [])) > 0)
        logger.info(f"📋 ClipRegistry deserialized: {len(self.clips)} clips restored with complete state ({total_layers} total layers, {clips_with_layers} clips with layers)")



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
