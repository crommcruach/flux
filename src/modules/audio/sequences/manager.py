"""
Sequence Manager

Central coordinator for all parameter sequences.
Manages lifecycle, applies modulation, and handles parameter resolution.
"""

import logging
from typing import Dict, List, Optional, Any
from .base import BaseSequence
from ...player.clips.uid_registry import get_uid_registry

logger = logging.getLogger(__name__)


class SequenceManager:
    """Manages all parameter sequences"""
    
    def __init__(self, socketio=None, clip_registry=None):
        self.sequences: Dict[str, BaseSequence] = {}
        self._parameter_cache = {}  # Cache resolved parameter objects
        self.socketio = socketio  # SocketIO instance for real-time updates
        self._last_log_time = 0  # For throttled logging
        self._uid_warning_cache = set()  # Track UIDs we've already warned about
        self.clip_registry = clip_registry  # Reference to ClipRegistry
        logger.info("SequenceManager initialized")
    
    def set_clip_registry(self, clip_registry):
        """Set the clip registry reference"""
        self.clip_registry = clip_registry
        logger.debug("ClipRegistry reference set in SequenceManager")
    
    def create(self, sequence: BaseSequence) -> str:
        """
        Add a new sequence and associate with clip
        
        Args:
            sequence: Sequence instance to add
            
        Returns:
            Sequence ID
        """
        self.sequences[sequence.id] = sequence
        logger.info(f"Created sequence: {sequence.id} ({sequence.type}) -> {sequence.target_parameter}")
        
        # Associate sequence with clip in registry
        if self.clip_registry and sequence.target_parameter:
            clip_id = self._extract_clip_id_from_uid(sequence.target_parameter)
            if clip_id:
                self.clip_registry.add_sequence_to_clip(clip_id, sequence.id, sequence.target_parameter)
                logger.debug(f"Associated sequence {sequence.id} with clip {clip_id[:8]}...")
        
        return sequence.id
    
    def get(self, sequence_id: str) -> Optional[BaseSequence]:
        """Get sequence by ID"""
        return self.sequences.get(sequence_id)
    
    def get_all(self) -> List[BaseSequence]:
        """Get all sequences"""
        return list(self.sequences.values())
    
    def delete(self, sequence_id: str) -> bool:
        """
        Delete a sequence
        
        Args:
            sequence_id: ID of sequence to delete
            
        Returns:
            True if deleted, False if not found
        """
        if sequence_id in self.sequences:
            sequence = self.sequences.pop(sequence_id)
            
            # Remove from clip registry
            if self.clip_registry and sequence.target_parameter:
                clip_id = self._extract_clip_id_from_uid(sequence.target_parameter)
                if clip_id:
                    self.clip_registry.remove_sequence_from_clip(clip_id, sequence_id)
            
            # Clean up cached values for this sequence
            if hasattr(self, '_last_values') and sequence_id in self._last_values:
                del self._last_values[sequence_id]
            
            # Clean up frame updates for this parameter
            if hasattr(self, '_frame_updates') and sequence.target_parameter in self._frame_updates:
                # Only remove if this sequence was the last one controlling this parameter
                if self._frame_updates[sequence.target_parameter]['sequence_id'] == sequence_id:
                    del self._frame_updates[sequence.target_parameter]
            
            # Clean up emitted values for this parameter
            if hasattr(self, '_last_emitted_values') and sequence.target_parameter in self._last_emitted_values:
                # Check if any other sequence targets this parameter
                other_seq_exists = any(
                    s.target_parameter == sequence.target_parameter 
                    for s in self.sequences.values()
                )
                # Only remove if no other sequence targets this parameter
                if not other_seq_exists:
                    del self._last_emitted_values[sequence.target_parameter]
            
            logger.info(f"Deleted sequence: {sequence_id} (target: {sequence.target_parameter})")
            return True
        return False
    
    def toggle(self, sequence_id: str) -> bool:
        """
        Toggle sequence enabled state
        
        Args:
            sequence_id: ID of sequence to toggle
            
        Returns:
            New enabled state, or None if not found
        """
        sequence = self.get(sequence_id)
        if sequence:
            sequence.toggle()
            logger.debug(f"Toggled sequence {sequence_id}: enabled={sequence.enabled}")
            return sequence.enabled
        return None
    
    def _get_active_clip_ids(self, player_manager) -> set:
        """Get all currently active clip IDs from all players"""
        active_clips = set()
        if not player_manager:
            return active_clips
        
        for player in player_manager.players.values():
            if not player or not hasattr(player, 'layers'):
                continue
            for layer in player.layers:
                clip_id = getattr(layer, 'clip_id', None)
                if clip_id:
                    active_clips.add(clip_id)
                    logger.debug(f"  🎬 Active clip detected: {clip_id[:8]}...")
        
        return active_clips
    
    def _extract_clip_id_from_uid(self, uid: str) -> Optional[str]:
        """Extract clip_id from parameter UID"""
        if not uid or not uid.startswith('param_clip_'):
            return None
        
        parts = uid.split('_')
        if len(parts) >= 3:
            return parts[2]  # clip_id is third part
        return None
    
    def load_sequences_from_clip(self, clip_id: str) -> int:
        """
        Load all sequences from a clip's effects into active sequences (NEW ARCHITECTURE)
        
        This is called when a clip becomes active (loaded into player).
        Extracts sequences from clip_registry and instantiates them.
        
        Args:
            clip_id: Clip UUID to load sequences from
            
        Returns:
            Number of sequences loaded
        """
        # NO CACHE CLEARING NEEDED - we always resolve dynamically using stable identifiers
        # Effect instances may change on reload, but clip_id + effect_index are stable
        
        if not self.clip_registry:
            logger.warning("Cannot load sequences: clip_registry not set")
            return 0
        
        loaded_count = 0
        all_sequences = self.clip_registry.get_all_clip_sequences(clip_id)
        
        for seq_data in all_sequences:
            seq_config = seq_data['sequence_config']
            param_name = seq_data['param_name']
            effect_index = seq_data['effect_index']
            layer_index = seq_data['layer_index']
            sequence_id = seq_config.get('sequence_id')
            
            # Skip if already loaded
            if sequence_id and sequence_id in self.sequences:
                logger.debug(f"Sequence {sequence_id} already loaded, skipping")
                continue
            
            # Build target UID
            if layer_index is not None:
                target_uid = f"param_clip_{clip_id}_layer_{layer_index}_effect_{effect_index}_{param_name}"
            else:
                target_uid = f"param_clip_{clip_id}_effect_{effect_index}_{param_name}"
            
            # Instantiate sequence based on type
            seq_type = seq_config.get('type')
            
            try:
                if seq_type == 'timeline':
                    from .timeline import TimelineSequence
                    sequence = TimelineSequence(
                        sequence_id=sequence_id,
                        target_parameter=target_uid,
                        duration=seq_config.get('duration', 5.0),
                        playback_state=seq_config.get('playback_state', 'forward'),
                        loop_mode=seq_config.get('loop_mode', 'loop'),
                        speed=seq_config.get('speed', 1.0),
                        min_value=seq_config.get('min_value', 0.0),
                        max_value=seq_config.get('max_value', 100.0)
                    )
                elif seq_type == 'audio':
                    from .audio import AudioSequence
                    sequence = AudioSequence(
                        sequence_id=sequence_id,
                        target_parameter=target_uid,
                        feature=seq_config.get('feature', 'rms'),
                        min_value=seq_config.get('min_value', 0.0),
                        max_value=seq_config.get('max_value', 100.0),
                        smoothing=seq_config.get('smoothing', 0.1)
                    )
                elif seq_type == 'lfo':
                    from .lfo import LFOSequence
                    sequence = LFOSequence(
                        sequence_id=sequence_id,
                        target_parameter=target_uid,
                        frequency=seq_config.get('frequency', 1.0),
                        waveform=seq_config.get('waveform', 'sine'),
                        phase=seq_config.get('phase', 0.0),
                        min_value=seq_config.get('min_value', 0.0),
                        max_value=seq_config.get('max_value', 100.0)
                    )
                elif seq_type == 'bpm':
                    from .bpm import BPMSequence
                    sequence = BPMSequence(
                        sequence_id=sequence_id,
                        target_parameter=target_uid,
                        bpm=seq_config.get('bpm', 120.0),
                        subdivision=seq_config.get('subdivision', '1/4'),
                        phase_offset=seq_config.get('phase_offset', 0.0),
                        min_value=seq_config.get('min_value', 0.0),
                        max_value=seq_config.get('max_value', 100.0)
                    )
                else:
                    logger.warning(f"Unknown sequence type: {seq_type}")
                    continue
                
                # Override ID with stored one if available
                if sequence_id:
                    sequence.id = sequence_id
                
                # Set enabled state
                sequence.enabled = seq_config.get('enabled', True)
                
                # Add to active sequences
                self.sequences[sequence.id] = sequence
                loaded_count += 1
                
                logger.debug(f"  🔗 Loaded sequence {sequence.id} ({seq_type}) targeting {target_uid}")
                
            except Exception as e:
                logger.error(f"Error loading sequence from clip: {e}", exc_info=True)
        
        if loaded_count > 0:
            logger.debug(f"Loaded {loaded_count} sequences from clip {clip_id[:8]}...")
            logger.debug(f"  📊 Total sequences in manager: {len(self.sequences)}")
        else:
            logger.debug(f"No sequences found for clip {clip_id[:8]}...")
        
        return loaded_count
    
    def unload_sequences_for_clip(self, clip_id: str) -> int:
        """
        Unload all sequences for a clip (NEW ARCHITECTURE)
        
        This is called when a clip becomes inactive (unloaded from player).
        Removes sequences from active pool but keeps them stored in clip_registry.
        
        Args:
            clip_id: Clip UUID to unload sequences for
            
        Returns:
            Number of sequences unloaded
        """
        unloaded_count = 0
        
        # Find all sequences targeting this clip
        to_remove = []
        for seq_id, sequence in self.sequences.items():
            extracted_clip_id = self._extract_clip_id_from_uid(sequence.target_parameter)
            if extracted_clip_id == clip_id:
                to_remove.append(seq_id)
        
        # Remove them
        for seq_id in to_remove:
            if seq_id in self.sequences:
                del self.sequences[seq_id]
                unloaded_count += 1
        
        if unloaded_count > 0:
            logger.debug(f"Unloaded {unloaded_count} sequences for clip {clip_id[:8]}...")
        
        return unloaded_count
    
    def update_all(self, dt: float, player_manager=None):
        """
        Update all sequences and apply modulation
        
        Args:
            dt: Delta time in seconds
            player_manager: Reference to PlayerManager for parameter resolution
        """
        if not self.sequences:
            return
        
        # Log sequence count periodically
        if not hasattr(self, '_update_counter'):
            self._update_counter = 0
        self._update_counter += 1
        
        if self._update_counter % 120 == 1:  # Every ~4 seconds at 30fps
            logger.debug(f"🔄 update_all() called: {len(self.sequences)} sequences loaded")
        
        # Get active clip IDs to filter sequences
        active_clip_ids = self._get_active_clip_ids(player_manager) if player_manager else set()
        
        if self._update_counter % 120 == 1:
            logger.debug(f"  🎬 Active clips: {', '.join([c[:8] + '...' for c in active_clip_ids]) if active_clip_ids else 'NONE'}")
        
        # Detect clip changes early to clear caches before processing
        if player_manager:
            if not hasattr(self, '_last_active_clips'):
                self._last_active_clips = {}
            
            for player_name, player in player_manager.players.items():
                if not player:
                    continue
                current_clip = getattr(player, 'current_clip_id', None)
                if self._last_active_clips.get(player_name) != current_clip:
                    logger.debug(f"[{player_name}] Clip changed: {self._last_active_clips.get(player_name)} → {current_clip}")
                    self._last_active_clips[player_name] = current_clip
        
        # Log once every 60 frames (~2 seconds at 30fps)
        if not hasattr(self, '_update_counter'):
            self._update_counter = 0
        self._update_counter += 1
        
        # Increment frame counter for _apply_modulation call tracking
        if not hasattr(self, '_frame_counter'):
            self._frame_counter = 0
        self._frame_counter += 1
        
        # Initialize frame-level parameter update buffer
        if not hasattr(self, '_frame_updates'):
            self._frame_updates = {}
        if not hasattr(self, '_frame_updates_frame'):
            self._frame_updates_frame = -1
        
        # Clear frame buffer at start of new frame
        if self._frame_updates_frame != self._frame_counter:
            self._frame_updates = {}
            self._frame_updates_frame = self._frame_counter
        
        # Track skipped sequences for logging
        if not hasattr(self, '_skipped_sequences_count'):
            self._skipped_sequences_count = {}
        
        # Collect all parameter updates for this frame (deduplication)
        active_sequences = 0
        skipped_sequences = 0
        
        # CRITICAL: Create snapshot to prevent "dictionary changed size during iteration"
        # (unload_sequences_for_clip can be called concurrently)
        for sequence in list(self.sequences.values()):
            if not sequence.enabled:
                if self._update_counter % 60 == 0:
                    logger.debug(f"⏸️ Sequence {sequence.id} is disabled")
                continue
            
            # CRITICAL: Skip sequences for inactive clips
            clip_id = self._extract_clip_id_from_uid(sequence.target_parameter)
            if clip_id and clip_id not in active_clip_ids:
                skipped_sequences += 1
                # Log only once per sequence when it becomes inactive
                if self._skipped_sequences_count.get(sequence.id, 0) == 0:
                    logger.info(f"⏭️ Skipping sequence {sequence.id} - clip {clip_id[:8]}... not in active clips {[c[:8] for c in active_clip_ids]}")
                self._skipped_sequences_count[sequence.id] = self._skipped_sequences_count.get(sequence.id, 0) + 1
                continue
            
            # Reset skip counter when sequence becomes active again
            if sequence.id in self._skipped_sequences_count:
                if self._skipped_sequences_count[sequence.id] > 0:
                    logger.debug(f"Resuming sequence {sequence.id} - clip {clip_id[:8] if clip_id else 'unknown'}... now active")
                self._skipped_sequences_count[sequence.id] = 0
            
            active_sequences += 1
            
            try:
                # Update sequence state
                sequence.update(dt)
                
                # Collect parameter update for this frame
                if player_manager and sequence.target_parameter:
                    value = sequence.get_value()
                    
                    # Check if this UID is already in frame buffer (potential conflict)
                    if sequence.target_parameter in self._frame_updates:
                        existing = self._frame_updates[sequence.target_parameter]
                        if existing['sequence_id'] != sequence.id:
                            logger.warning(
                                f"⚠️ Multiple sequences targeting same UID in one frame! "
                                f"UID: {sequence.target_parameter[:50]}..., "
                                f"Existing seq: {existing['sequence_id']}, "
                                f"New seq: {sequence.id} (last write wins)"
                            )
                    
                    # Store in frame buffer (last write wins if multiple sequences target same parameter)
                    self._frame_updates[sequence.target_parameter] = {
                        'value': value,
                        'sequence_id': sequence.id,
                        'sequence_type': sequence.type
                    }
                    
                    # Track last value per sequence for change detection
                    if not hasattr(self, '_last_values'):
                        self._last_values = {}
                    self._last_values[sequence.id] = value
            
            except Exception as e:
                logger.error(f"Error updating sequence {sequence.id}: {e}", exc_info=True)
        
        # Log sequence statistics periodically (after counting is complete)
        if self._update_counter % 60 == 0:
            logger.debug(f"🔄 Sequences: {active_sequences} active, {skipped_sequences} skipped (inactive clips), {len(active_clip_ids)} active clips")
            if active_clip_ids:
                logger.debug(f"  🎬 Active clips: {', '.join([c[:8] + '...' for c in list(active_clip_ids)[:3]])}")
            # Log all sequences and their targets
            for seq_id, seq in self.sequences.items():
                seq_clip_id = self._extract_clip_id_from_uid(seq.target_parameter)
                is_active = seq_clip_id in active_clip_ids if seq_clip_id else False
                logger.debug(f"  📋 Sequence {seq_id}: type={seq.type}, clip={seq_clip_id[:8] if seq_clip_id else 'N/A'}..., active={is_active}, enabled={seq.enabled}")
        
        # Apply all buffered updates ONCE per parameter per frame
        for param_uid, update_info in self._frame_updates.items():
            value = update_info['value']
            sequence_type = update_info['sequence_type']
            
                # Apply modulation
            success = self._apply_modulation(param_uid, value, player_manager)
            
            # Log first few applications for debugging
            if not hasattr(self, '_apply_log_count'):
                self._apply_log_count = 0
            if self._apply_log_count < 5:
                logger.info(f"🎯 Applying {sequence_type} sequence value {value:.2f} to {param_uid[:60]}... (success={success})")
                self._apply_log_count += 1
            
            # Emit parameter update via WebSocket for visual feedback (red line)
            if not hasattr(self, '_last_emitted_values'):
                self._last_emitted_values = {}
            
            last_emitted = self._last_emitted_values.get(param_uid)
            # Emit if value changed by more than 0.1 OR every 5 frames for timeline sequences
            should_emit = (last_emitted is None or 
                           abs(value - last_emitted) > 0.1 or 
                           (sequence_type == 'timeline' and self._frame_counter % 5 == 0))
            
            if should_emit and self.socketio:
                self.socketio.emit('parameter_update', {
                    'parameter': param_uid,
                    'value': value
                })
                self._last_emitted_values[param_uid] = value
                if self._update_counter % 120 == 0 and value is not None:  # Log less frequently
                    logger.debug(f"📡 Emitted parameter_update: {param_uid[:50]}... = {value:.2f}")
    
    def _resolve_uid_to_path(self, uid: str, player_manager):
        """
        Resolve UID to actual parameter location (player, effect instance, param name)
        
        Uses global UID registry for O(1) lookup instead of O(n×m×k) nested loops.
        
        Args:
            uid: Parameter UID (e.g., "param_clip_1_scale_xy_1766570567525_hj1djcp9w")
            player_manager: PlayerManager instance
            
        Returns:
            Tuple of (player, effect_instance, param_name) or None if not found
        """
        try:
            # ALWAYS resolve dynamically using stable identifiers (clip_id + effect_index)
            # No caching because effect instances are recreated on layer reload
            # NEW format UIDs use effect_index for O(1) lookup, so no performance penalty
            
            logger.debug(f"🔍 Resolving UID: {uid[:50]}...")
            
            # Parse UID: Support both OLD and NEW formats
            # OLD: param_clip_{clip_id}_{param_name}_{uuid_short}
            # NEW: param_clip_{clip_id}_effect_{effect_index}_{param_name}
            # NEW: param_clip_{clip_id}_layer_{layer_idx}_effect_{effect_idx}_{param_name}
            
            parts = uid.split('_')
            if len(parts) < 4 or parts[0] != 'param' or parts[1] != 'clip':
                logger.warning(f"Invalid UID format: {uid}")
                return None
            
            clip_id = None
            param_name = None
            effect_index = None
            layer_index = None
            
            # Detect NEW format (has 'effect' keyword)
            if 'effect' in parts:
                try:
                    clip_idx = parts.index('clip') + 1
                    effect_idx_pos = parts.index('effect') + 1
                    
                    # Check if it's a layer effect
                    if 'layer' in parts:
                        layer_idx_pos = parts.index('layer') + 1
                        clip_id = '_'.join(parts[clip_idx:layer_idx_pos-1])  # Reconstruct UUID with hyphens
                        layer_index = int(parts[layer_idx_pos])
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                    else:
                        # Clip-level effect
                        clip_id = '_'.join(parts[clip_idx:effect_idx_pos-1])
                        effect_index = int(parts[effect_idx_pos])
                        param_name = '_'.join(parts[effect_idx_pos+1:])
                    
                    logger.debug(f"🆕 NEW UID format: clip={clip_id[:8]}..., effect={effect_index}, layer={layer_index}, param={param_name}")
                    
                except (ValueError, IndexError) as e:
                    logger.warning(f"Error parsing NEW UID format: {uid}, error: {e}")
                    return None
            else:
                # OLD format: param_clip_{clip_id}_{param_name}_{uuid_short}
                if len(parts) < 5:
                    logger.warning(f"OLD UID too short: {uid}")
                    return None
                    
                clip_id = parts[2]
                param_name = '_'.join(parts[3:-1])  # Everything between clip_id and short_uuid
                uuid_short = parts[-1]
                
                # Validate clip_id format (should be UUID with hyphens)
                if '-' not in clip_id:
                    logger.warning(f"Invalid clip_id format in UID: {clip_id}")
                    return None
                
                logger.debug(f"🔎 OLD UID format: clip={clip_id[:8]}..., param={param_name}, uuid={uuid_short}")
            
            # Validate we got the required parts
            if not clip_id or not param_name:
                logger.warning(f"Failed to parse UID: {uid}")
                return None
            
            # Search all players for the clip with matching UID
            for player_name, player in player_manager.players.items():
                if not player or not hasattr(player, 'layers'):
                    continue
                
                # Detect clip changes and clear caches to allow re-resolution
                current_clip = getattr(player, 'current_clip_id', None)
                if not hasattr(self, '_last_active_clips'):
                    self._last_active_clips = {}
                
                # If clip changed, clear resolution caches for this player
                if self._last_active_clips.get(player_name) != current_clip:
                    logger.debug(f"Clip changed in {player_name}, clearing caches")
                    
                    # Clear UID resolution cache to force re-resolution with new effect instances
                    if hasattr(self, '_uid_resolution_cache'):
                        self._uid_resolution_cache.clear()
                    
                    # Clear UID warning cache to get fresh warnings if needed
                    if hasattr(self, '_uid_warning_cache'):
                        self._uid_warning_cache.clear()
                    
                    # Clear global UID registry to force re-registration
                    uid_registry = get_uid_registry()
                    uid_registry.clear()
                    
                    self._last_active_clips[player_name] = current_clip
                
                logger.debug(f"  🔍 Checking player {player_name} ({len(player.layers)} layers), current_clip_id={current_clip}")
                
                # Check each layer
                for layer_idx, layer in enumerate(player.layers):
                    layer_clip_id = getattr(layer, 'clip_id', None)
                    
                    if not layer_clip_id or str(layer_clip_id) != clip_id:
                        continue
                    
                    logger.debug(f"    ✅ Found matching layer! clip_id={layer_clip_id}")
                    
                    # Found the layer with this clip, search effects for matching UID
                    if not hasattr(layer, 'effects') or not layer.effects:
                        logger.debug(f"    ❌ Layer has no effects")
                        continue
                    
                    # If NEW format: use effect_index directly for O(1) lookup
                    if effect_index is not None:
                        # Check if layer_index matches (if specified in NEW format)
                        if layer_index is not None and layer_idx != layer_index:
                            logger.debug(f"    ⏭️ Layer index mismatch: expected {layer_index}, got {layer_idx}")
                            continue
                        
                        # Direct effect lookup by index
                        if effect_index >= len(layer.effects):
                            logger.debug(f"    ❌ Effect index {effect_index} out of range (layer has {len(layer.effects)} effects)")
                            continue
                        
                        effect = layer.effects[effect_index]
                        if not effect or 'instance' not in effect:
                            logger.debug(f"    ❌ Effect at index {effect_index} is invalid")
                            continue
                        
                        instance = effect['instance']
                        effect_params = effect.get('parameters', {})
                        plugin_id = effect.get('plugin_id', 'unknown')
                        
                        if param_name in effect_params:
                            logger.debug(f"🎯 NEW format resolved: {plugin_id} effect #{effect_index} instance [{id(instance)}] on layer {layer_idx}")
                            result = (player, instance, param_name)
                            
                            # Cache and register
                            if not hasattr(self, '_uid_resolution_cache'):
                                self._uid_resolution_cache = {}
                            self._uid_resolution_cache[uid] = result
                            
                            uid_registry = get_uid_registry()
                            uid_registry.register(uid, player, instance, param_name)
                            
                            return result
                        else:
                            logger.debug(f"    ❌ Parameter '{param_name}' not found in effect {effect_index}")
                            continue
                    
                    # OLD format: search all effects for matching UID (slower fallback)
                    for effect_idx, effect in enumerate(layer.effects):
                        if not effect or 'instance' not in effect:
                            continue
                        
                        instance = effect['instance']
                        effect_params = effect.get('parameters', {})
                        plugin_id = effect.get('plugin_id', 'unknown')
                        
                        if param_name in effect_params:
                            stored_param = effect_params[param_name]
                            
                            # Debug: Show what we're looking for vs what we found
                            logger.debug(f"🔍 Checking param '{param_name}' in effect {plugin_id}: type={type(stored_param).__name__}, has_uid={'_uid' in stored_param if isinstance(stored_param, dict) else False}")
                            if isinstance(stored_param, dict) and '_uid' in stored_param:
                                logger.debug(f"   Stored UID: {stored_param.get('_uid')[:50]}...")
                                logger.debug(f"   Looking for: {uid[:50]}...")
                            
                            # Check if stored parameter has matching UID - PERFECT MATCH
                            if isinstance(stored_param, dict) and stored_param.get('_uid') == uid:
                                logger.debug(f"🎯 UID resolved: {plugin_id} effect #{effect_idx} instance [{id(instance)}] on layer {layer_idx}, clip {clip_id[:8]}...")
                                result = (player, instance, param_name)
                                # Cache successful resolution
                                if not hasattr(self, '_uid_resolution_cache'):
                                    self._uid_resolution_cache = {}
                                self._uid_resolution_cache[uid] = result
                                
                                # Also register in global registry for future O(1) lookups
                                uid_registry = get_uid_registry()
                                uid_registry.register(uid, player, instance, param_name)
                                
                                logger.debug(f"✅ Resolved UID: {param_name} [{effect.get('plugin_id')}]")
                                return result
                            else:
                                # Parameter exists but UID doesn't match - USE FALLBACK WITH VALIDATION
                                # CRITICAL: Only use this fallback if we're on the CORRECT clip
                                # This prevents sequences from applying to wrong clips with same parameter name
                                logger.warning(f"⚠️ Parameter '{param_name}' found but UID mismatch. Clip match: {str(layer_clip_id) == clip_id}")
                                logger.warning(f"   Expected clip: {clip_id[:8]}..., Found clip: {str(layer_clip_id)[:8]}...")
                                logger.warning(f"   Stored UID: {stored_param.get('_uid', 'N/A')[:50] if isinstance(stored_param, dict) else 'not a dict'}...")
                                logger.warning(f"   Looking for: {uid[:50]}...")
                                
                                # STRICT VALIDATION: Clip IDs must match to prevent cross-clip application
                                if str(layer_clip_id) == clip_id:
                                    logger.debug(f"Clip IDs match! Returning result")
                                    return (player, instance, param_name)
                                else:
                                    # Clip mismatch - this is the wrong clip, continue searching
                                    logger.debug(f"❌ Clip ID mismatch - continuing search for correct clip")
                                    continue
            
            # Only warn once per UID
            if uid not in self._uid_warning_cache:
                logger.warning(f"❌ UID not found in any active layer: {uid}")
                logger.warning(f"   Parsed: clip_id={clip_id[:8] if len(clip_id) > 8 else clip_id}..., param_name={param_name}")
                self._uid_warning_cache.add(uid)
            return None
            
        except Exception as e:
            logger.error(f"Error resolving UID {uid}: {e}", exc_info=True)
            return None
    
    def _apply_modulation(self, target_path: str, value: float, player_manager):
        """
        Apply modulated value to target parameter
        
        Args:
            target_path: UID (e.g., "param_clip_1_scale_xy_1766570567525_hj1djcp9w")
                        or Dot notation path (e.g., "player.video.clip.effects[0].brightness")
            value: Value to apply
            player_manager: PlayerManager instance
            
        Returns:
            bool: True if value was successfully applied, False otherwise
        """
        try:
            # Check if target_path is a UID (starts with "param_")
            if target_path.startswith('param_'):
                # UID format: param_clip_{clip_id}_{param_name}_{timestamp}_{random}
                # Need to resolve to actual parameter location
                resolved = self._resolve_uid_to_path(target_path, player_manager)
                if not resolved:
                    # Only log once per UID
                    if target_path not in self._uid_warning_cache:
                        logger.warning(f"❌ Could not resolve UID to parameter path: {target_path}")
                        self._uid_warning_cache.add(target_path)
                    return False
                player, effect_instance, param_name = resolved
                
                # Audio sequences now use the correct range from triple slider (e.g., 0-500 for scale)
                # No automatic scaling needed - use value as-is
                scaled_value = value
                
                # Apply value to effect instance
                if hasattr(effect_instance, 'update_parameter'):
                    success = effect_instance.update_parameter(param_name, scaled_value)
                    if success:
                        # Only log significant updates (throttled)
                        if not hasattr(self, '_apply_log_counter'):
                            self._apply_log_counter = {}
                        self._apply_log_counter[target_path] = self._apply_log_counter.get(target_path, 0) + 1
                        
                        # Log every 60 frames (~2 sec at 30fps) OR significant value changes
                        if not hasattr(self, '_last_logged_values'):
                            self._last_logged_values = {}
                        
                        should_log = False
                        if self._apply_log_counter[target_path] % 60 == 1:
                            should_log = True
                        elif target_path in self._last_logged_values:
                            change = abs(scaled_value - self._last_logged_values[target_path])
                            if change > 10.0:  # Log if change > 10
                                should_log = True
                        else:
                            should_log = True  # First time
                        
                        if should_log:
                            logger.debug(f"🎚️ [{id(effect_instance)}] {param_name} = {scaled_value:.1f}")
                            self._last_logged_values[target_path] = scaled_value
                        return True
                    else:
                        logger.warning(f"❌ update_parameter failed for {param_name}")
                        return False
                elif hasattr(effect_instance, param_name):
                    setattr(effect_instance, param_name, scaled_value)
                    logger.debug(f"✅ Applied: {param_name} = {scaled_value:.2f} via setattr [{player.__class__.__name__}]")
                    logger.debug(f"✅ Applied via setattr: {param_name} = {scaled_value:.4f}")
                    return True
                else:
                    logger.warning(f"Parameter not found on effect instance: {param_name}")
                    return False
            
            # Legacy path format: player.<player_id>.clip.<clip_id>.effects[index].<param>
            parts = target_path.split('.')
            
            if len(parts) < 4 or parts[0] != 'player':
                # Likely a UID format, not legacy path - log once per session
                if not hasattr(self, '_invalid_path_cache'):
                    self._invalid_path_cache = set()
                if target_path not in self._invalid_path_cache:
                    logger.debug(f"Skipping non-legacy path format: {target_path}")
                    self._invalid_path_cache.add(target_path)
                return False
            
            player_id = parts[1]
            
            # Get player
            player = player_manager.get_player(player_id)
            if not player:
                logger.warning(f"Player not found: {player_id}")
                return False
            
            # Navigate to target object
            current = player
            for i, part in enumerate(parts[2:], start=2):
                if '[' in part:
                    # Array access: effects[0]
                    name, index = part.split('[')
                    index = int(index.rstrip(']'))
                    current = getattr(current, name, None)
                    if current and isinstance(current, list) and len(current) > index:
                        current = current[index]
                    else:
                        logger.warning(f"Invalid array access: {part} in {target_path}")
                        return False
                elif i == len(parts) - 1:
                    # Last part is the parameter name
                    if hasattr(current, part):
                        setattr(current, part, value)
                        logger.debug(f"Applied modulation: {target_path} = {value}")
                        return True
                    else:
                        logger.warning(f"Parameter not found: {part} in {target_path}")
                        return False
                else:
                    # Navigate deeper
                    current = getattr(current, part, None)
                    if current is None:
                        logger.warning(f"Invalid path segment: {part} in {target_path}")
                        return False
            return False
        
        except Exception as e:
            logger.error(f"Error applying modulation to {target_path}: {e}", exc_info=True)
            return False
    
    def clear_all(self):
        """Remove all sequences"""
        self.sequences.clear()
        logger.info("Cleared all sequences")
    
    def serialize_all(self) -> List[Dict[str, Any]]:
        """
        Serialize all sequences to list of dictionaries
        
        Returns:
            List of sequence dictionaries
        """
        return [seq.serialize() for seq in self.sequences.values()]
    
    def get_by_target(self, target_parameter: str) -> List[BaseSequence]:
        """
        Get all sequences targeting a specific parameter
        
        Args:
            target_parameter: Target parameter path
            
        Returns:
            List of sequences
        """
        return [seq for seq in self.sequences.values() 
                if seq.target_parameter == target_parameter]
