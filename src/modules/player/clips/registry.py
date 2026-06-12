"""
Clip Registry - Central management of video clips with unique IDs.

Enables:
- Unique identification of clips independent of filename
- Multiple use of the same video in different players
- Clip-specific metadata and effects
"""

import uuid
import os
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ClipRegistry:
    """Central registry for video clips with UUID-based identification."""
    
    def __init__(self):
        """Initializes the clip registry."""
        # Mapping: clip_id (UUID) -> clip_data
        self.clips: Dict[str, Dict] = {}
        
        # Version tracking for cache invalidation (B3 Performance Optimization)
        self._clip_effects_version: Dict[str, int] = {}  # clip_id -> version_counter
        
        # Optional: Default effects manager for auto-applying effects
        self._default_effects_manager = None

        # Default layer names for pre-allocated slots (index = slot layer_id)
        self._default_layer_names: List[str] = ["Background", "Overlay 1", "Overlay 2", "Overlay 3", "Mask"]

    def set_layer_defaults(self, names: List[str]) -> None:
        """Configure default layer names from config (index 0 = base, 1-N = overlay slots)."""
        if names:
            self._default_layer_names = list(names)

    def ensure_layer_slots(self, clip_id: str) -> None:
        """Ensure clip has all pre-allocated overlay slot entries (lazy migration for old clips)."""
        if clip_id not in self.clips:
            return
        layers = self.clips[clip_id]['layers']
        existing_ids = {l['layer_id'] for l in layers}
        changed = False
        for slot_id in range(1, len(self._default_layer_names)):
            if slot_id not in existing_ids:
                slot_name = self._default_layer_names[slot_id]
                layers.append({
                    'layer_id': slot_id,
                    'name': slot_name,
                    'source_type': 'empty',
                    'source_path': None,
                    'blend_mode': 'normal',
                    'opacity': 1.0,
                    'enabled': True
                })
                changed = True
        if changed:
            layers.sort(key=lambda l: l['layer_id'])
        # Ensure base_layer_name exists
        if 'base_layer_name' not in self.clips[clip_id]:
            self.clips[clip_id]['base_layer_name'] = self._default_layer_names[0] if self._default_layer_names else 'Background'
    
    def register_clip(
        self, 
        player_id: str, 
        absolute_path: str, 
        relative_path: str,
        metadata: Optional[Dict] = None,
        clip_id: Optional[str] = None
    ) -> str:
        """
        Registriert einen neuen Clip mit eindeutiger UUID.
        IDEMPOTENT: If clip already exists (player_id + absolute_path),
        the existing clip_id is returned (WITHOUT overwriting data).
        
        Args:
            player_id: ID of the player ('video' or 'artnet')
            absolute_path: Absolute path to the video file
            relative_path: Relative path (for UI)
            metadata: Optional metadata (fps, duration, etc.)
            clip_id: Optional clip_id (if frontend provides UUID)
        
        Returns:
            clip_id: Unique UUID for this clip
        """
        # If clip_id is provided and already exists in registry, reuse it (idempotent).
        if clip_id and clip_id in self.clips:
            logger.debug(f"🔄 Clip already registered: {clip_id} → {player_id}/{os.path.basename(absolute_path)} (reusing existing data)")
            return clip_id

        # Always create a new entry with a fresh UUID when no clip_id is given.
        # Path-based dedup is intentionally removed here: each call to register_clip
        # may represent a distinct playlist slot (even for the same file), and each
        # slot must have its own UUID so effects/parameters can be assigned independently.
        # Session-restore dedup is handled separately via _ensure_clip_registered.
        if not clip_id:
            clip_id = str(uuid.uuid4())
        
        # Pre-populate empty overlay slots (layer_id 1..N) with default names
        empty_slots = []
        for slot_id in range(1, len(self._default_layer_names)):
            slot_name = self._default_layer_names[slot_id] if slot_id < len(self._default_layer_names) else f"Layer {slot_id}"
            empty_slots.append({
                'layer_id': slot_id,
                'name': slot_name,
                'source_type': 'empty',
                'source_path': None,
                'blend_mode': 'normal',
                'opacity': 1.0,
                'enabled': True
            })

        # Save clip data
        self.clips[clip_id] = {
            'clip_id': clip_id,
            'player_id': player_id,
            'absolute_path': absolute_path,
            'relative_path': relative_path,
            'filename': os.path.basename(absolute_path),
            'metadata': metadata or {},
            'created_at': datetime.now().isoformat(),
            'effects': [],  # Clip-specific effects
            'layers': empty_slots,  # Pre-allocated overlay slot definitions
            'base_layer_name': self._default_layer_names[0] if self._default_layer_names else 'Background',
            'sequences': {},  # Clip-specific sequences: {uid: [sequence_ids]}
            # Trimming & Playback Control
            'in_point': None,   # Start frame (None = video start)
            'out_point': None,  # End frame (None = video end)
            'reverse': False    # Play in reverse
        }
        
        logger.debug(f"✅ Clip registered: {clip_id} → {player_id}/{os.path.basename(absolute_path)}")
        
        # Auto-apply default effects if manager is configured
        if self._default_effects_manager:
            try:
                logger.debug(f"🔧 Attempting to apply default effects to clip {clip_id}")
                applied = self._default_effects_manager.apply_to_clip(self, clip_id)
                if applied > 0:
                    logger.debug(f"🎨 Auto-applied {applied} default effects to new clip {clip_id}")
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
        Gets clip data by ID.
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            Clip data or None if not found
        """
        return self.clips.get(clip_id)
    
    def find_clip_by_path(self, player_id: str, absolute_path: str) -> Optional[str]:
        """
        Finds FIRST clip ID by player ID and path.
        NOTE: Multiple clips can have the same path!
        Returns only the first matching clip.
        
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
        
        # Search across all clips (may have multiple with same path)
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
        Gets all clips for a specific player.
        
        Args:
            player_id: ID of the player
        
        Returns:
            List of clip data
        """
        return [
            clip for clip in self.clips.values()
            if clip['player_id'] == player_id
        ]
    
    def _invalidate_cache(self, clip_id: str) -> None:
        """
        Invalidates effect cache for a clip by incrementing the version counter.
        Called on all changes to effects (add, remove, update, clear).
        
        Args:
            clip_id: Unique clip ID
        """
        current_version = self._clip_effects_version.get(clip_id, 0)
        self._clip_effects_version[clip_id] = current_version + 1
        logger.debug(f"🔄 Cache invalidated for clip {clip_id} (version: {current_version} → {current_version + 1})")
    
    def get_effects_version(self, clip_id: str) -> int:
        """
        Returns the current version of the effect cache for a clip.
        Players use this for version-based cache invalidation.
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            Version counter (0 if clip does not exist or has no version)
        """
        return self._clip_effects_version.get(clip_id, 0)
    
    def set_default_effects_manager(self, manager):
        """
        Sets the default effects manager for auto-apply at clip registration.
        
        Args:
            manager: DefaultEffectsManager instance
        """
        self._default_effects_manager = manager
        logger.debug("🎨 Default Effects Manager configured for ClipRegistry")
    
    def unregister_clip(self, clip_id: str) -> bool:
        """
        Removes a clip from the registry.
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            True if successfully removed
        """
        if clip_id not in self.clips:
            return False
        
        clip_data = self.clips[clip_id]
        index_key = (clip_data['player_id'], clip_data['absolute_path'])
        
        # Remove from both data structures
        del self.clips[clip_id]
        if index_key in self._path_index:
            del self._path_index[index_key]
        
        logger.debug(f"🗑️ Clip unregistered: {clip_id}")
        return True
    
    def add_effect_to_clip(self, clip_id: str, effect_data: Dict) -> bool:
        """
        Adds an effect to a clip.
        
        Args:
            clip_id: Unique clip ID
            effect_data: Effect data (plugin_id, parameters, etc.)
        
        Returns:
            True if successfully added
        """
        if clip_id not in self.clips:
            logger.error(f"Clip not found: {clip_id}")
            return False
        
        self.clips[clip_id]['effects'].append(effect_data)
        self._invalidate_cache(clip_id)  # B3: Invalidate cache
        logger.debug(f"Effect added to clip: {clip_id} → {effect_data.get('plugin_id')}")
        return True
    
    def get_clip_effects(self, clip_id: str) -> List[Dict]:
        """
        Gets all effects for a clip.
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            List of effect data
        """
        if clip_id not in self.clips:
            return []
        
        return self.clips[clip_id].get('effects', [])
    
    def remove_effect_from_clip(self, clip_id: str, effect_index: int) -> bool:
        """
        Removes an effect from a clip.
        
        Args:
            clip_id: Unique clip ID
            effect_index: Index of the effect to remove
        
        Returns:
            True if successfully removed
        """
        if clip_id not in self.clips:
            return False
        
        effects = self.clips[clip_id]['effects']
        if 0 <= effect_index < len(effects):
            removed = effects.pop(effect_index)
            self._invalidate_cache(clip_id)  # B3: Invalidate cache
            logger.debug(f"Effect removed from clip: {clip_id} → {removed.get('plugin_id')}")
            return True
        
        return False
    
    def clear_clip_effects(self, clip_id: str) -> bool:
        """
        Removes all effects from a clip, except system_plugins (e.g. transport).
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            True if successful
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
        self._invalidate_cache(clip_id)  # B3: Invalidate cache
        
        removed_count = len(self.clips[clip_id]['effects']) - len(system_effects)
        if removed_count > 0:
            logger.debug(f"Removed {removed_count} effects from clip {clip_id}, kept {len(system_effects)} system plugins")
        else:
            logger.debug(f"No user effects to remove from clip {clip_id} (kept {len(system_effects)} system plugins)")
        
        return True
    
    def update_clip_metadata(self, clip_id: str, metadata: Dict) -> bool:
        """
        Updates metadata of a clip.
        
        Args:
            clip_id: Unique clip ID
            metadata: New/updated metadata
        
        Returns:
            True if successful
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
        Adds a layer to a clip.
        
        Args:
            clip_id: Unique clip ID
            layer_config: Layer configuration {
                'source_type': 'video' | 'generator' | 'script',
                'source_path': path or generator_id,
                'blend_mode': 'normal' | 'multiply' | ...,
                'opacity': float (0.0-1.0),
                'enabled': bool
            }
        
        Returns:
            layer_id (index) or None on error
        """
        if clip_id not in self.clips:
            logger.error(f"Clip not found: {clip_id}")
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
        
        logger.debug(f"✅ Layer {layer_id} added to clip {clip_id}: {layer_config['source_type']}")
        return layer_id
    
    def get_clip_layers(self, clip_id: str) -> List[Dict]:
        """
        Gets all layers for a clip.
        
        Args:
            clip_id: Unique clip ID
        
        Returns:
            List of layer configurations
        """
        if clip_id not in self.clips:
            return []
        
        return self.clips[clip_id].get('layers', [])
    
    def update_clip_layer(self, clip_id: str, layer_id: int, updates: Dict) -> bool:
        """
        Updates layer configuration.
        
        Args:
            clip_id: Unique clip ID
            layer_id: Layer ID (NOT index)
            updates: Dict with fields to update
        
        Returns:
            True if successful
        """
        if clip_id not in self.clips:
            return False
        
        # Layer 0 is the base clip — allow visibility/opacity/blend updates in
        # addition to name; block source or structural changes.
        if layer_id == 0:
            _allowed = {'name', 'enabled', 'opacity', 'blend_mode'}
            if not set(updates.keys()) <= _allowed:
                _blocked = set(updates.keys()) - _allowed
                logger.warning(f"Layer 0: blocked update keys {_blocked} (only {_allowed} allowed)")
                return False
            if 'name' in updates:
                self.clips[clip_id]['base_layer_name'] = updates['name']
            # Persist enabled/opacity/blend_mode on the clip itself so they
            # survive a reload (base layer has no separate layer dict).
            for _k in ('enabled', 'opacity', 'blend_mode'):
                if _k in updates:
                    self.clips[clip_id][_k] = updates[_k]
            return True
        
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
            logger.debug(f"💾 Layer {layer_id} opacity updated in registry: {old_opacity} → {new_opacity}")
        
        logger.debug(f"Layer {layer_id} of clip {clip_id} updated: {updates}")
        return True
    
    def remove_layer_from_clip(self, clip_id: str, layer_id: int) -> bool:
        """
        Removes a layer from a clip.
        
        Args:
            clip_id: Unique clip ID
            layer_id: Layer ID (NOT index)
        
        Returns:
            True if successful
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
        logger.debug(f"✅ Layer {layer_id} removed from clip {clip_id}: {removed.get('source_path')}")
        return True
    
    def reorder_clip_layers(self, clip_id: str, new_order: List[int]) -> bool:
        """
        Reorders layers of a clip.
        
        Args:
            clip_id: Unique clip ID
            new_order: List of layer IDs in new order (excluding layer 0 which is always base)
        
        Returns:
            True if successful
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
    def reorder_clip_effects(self, clip_id: str, new_order: List[int]) -> bool:
        """
        Reorders effects of a clip.

        Args:
            clip_id: Unique clip ID
            new_order: List of current effect indices in desired order
                       e.g. [2, 0, 1] moves effect 2 to front

        Returns:
            True if successful
        """
        if clip_id not in self.clips:
            return False

        effects = self.clips[clip_id]['effects']

        if sorted(new_order) != list(range(len(effects))):
            logger.warning(f"Invalid effect reorder for clip {clip_id}: expected indices 0-{len(effects)-1}, got {new_order}")
            return False

        self.clips[clip_id]['effects'] = [effects[i] for i in new_order]
        self._invalidate_cache(clip_id)
        logger.debug(f"Effects of clip {clip_id} reordered: {new_order}")
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
                logger.debug(f"[SERIALIZE DEBUG] Clip {clip_id[:8]}... has {len(clip_data['effects'])} effects in memory")
                for i, effect in enumerate(clip_data['effects']):
                    if 'parameters' in effect:
                        for param_name, param_value in list(effect['parameters'].items())[:5]:
                            logger.debug(f"[SERIALIZE DEBUG]   effect[{i}].{param_name} = {param_value}")
        
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
        
        # Repair stale UIDs: effect parameter _uid strings may reference an old
        # clip_id that no longer matches the current clip_id (e.g. after a path-
        # mismatch re-registration).  Walk every parameter value and rewrite the
        # clip segment of each UID so the frontend always sends the current ID.
        repaired = 0
        for clip_id, clip_data in self.clips.items():
            for effect in clip_data.get('effects', []):
                for param_name, param_val in list(effect.get('parameters', {}).items()):
                    if isinstance(param_val, dict) and '_uid' in param_val:
                        uid = param_val['_uid']
                        prefix = 'param_clip_'
                        if uid.startswith(prefix):
                            # UID format: param_clip_<old_id>_effect_<n>_<param>
                            rest = uid[len(prefix):]
                            # old_id is the 36-char UUID segment (UUID v4 = 36 chars)
                            old_id = rest[:36]
                            if old_id != clip_id:
                                param_val['_uid'] = prefix + clip_id + rest[36:]
                                repaired += 1
        if repaired:
            logger.debug(f"📋 ClipRegistry: repaired {repaired} stale UIDs after deserialize")

        # DEBUG: Log layer counts after deserialize
        total_layers = sum(len(clip.get('layers', [])) for clip in self.clips.values())
        clips_with_layers = sum(1 for clip in self.clips.values() if len(clip.get('layers', [])) > 0)
        logger.debug(f"📋 ClipRegistry deserialized: {len(self.clips)} clips restored with complete state ({total_layers} total layers, {clips_with_layers} clips with layers)")



# Globale Singleton-Instanz
_clip_registry: Optional[ClipRegistry] = None


def get_clip_registry() -> ClipRegistry:
    """
    Singleton getter for ClipRegistry.
    
    Returns:
        Global ClipRegistry instance
    """
    global _clip_registry
    if _clip_registry is None:
        _clip_registry = ClipRegistry()
        logger.debug("📋 ClipRegistry initialisiert")
    return _clip_registry
