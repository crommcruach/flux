"""
Sequence Manager

Central coordinator for all parameter sequences.
Manages lifecycle, applies modulation, and handles parameter resolution.
"""

import logging
from typing import Dict, List, Optional, Any
from .base_sequence import BaseSequence
from ..uid_registry import get_uid_registry

logger = logging.getLogger(__name__)


class SequenceManager:
    """Manages all parameter sequences"""
    
    def __init__(self, socketio=None):
        self.sequences: Dict[str, BaseSequence] = {}
        self._parameter_cache = {}  # Cache resolved parameter objects
        self.socketio = socketio  # SocketIO instance for real-time updates
        self._last_log_time = 0  # For throttled logging
        self._uid_warning_cache = set()  # Track UIDs we've already warned about
        logger.info("SequenceManager initialized")
    
    def create(self, sequence: BaseSequence) -> str:
        """
        Add a new sequence
        
        Args:
            sequence: Sequence instance to add
            
        Returns:
            Sequence ID
        """
        self.sequences[sequence.id] = sequence
        logger.info(f"Created sequence: {sequence.id} ({sequence.type}) -> {sequence.target_parameter}")
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
            logger.info(f"Deleted sequence: {sequence_id}")
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
            logger.info(f"Toggled sequence {sequence_id}: enabled={sequence.enabled}")
            return sequence.enabled
        return None
    
    def update_all(self, dt: float, player_manager=None):
        """
        Update all sequences and apply modulation
        
        Args:
            dt: Delta time in seconds
            player_manager: Reference to PlayerManager for parameter resolution
        """
        if not self.sequences:
            return
        
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
        
        if self._update_counter % 60 == 0:
            logger.debug(f"🔄 Updating {len(self.sequences)} sequences (dt={dt:.3f}s)")
            # Log all sequences and their targets
            for seq_id, seq in self.sequences.items():
                logger.debug(f"  📋 Sequence {seq_id}: type={seq.type}, target={seq.target_parameter[:50] if seq.target_parameter else 'None'}..., enabled={seq.enabled}")
        
        # Collect all parameter updates for this frame (deduplication)
        for sequence in self.sequences.values():
            if not sequence.enabled:
                if self._update_counter % 60 == 0:
                    logger.debug(f"⏸️ Sequence {sequence.id} is disabled")
                continue
            
            try:
                # Update sequence state
                sequence.update(dt)
                
                # Collect parameter update for this frame
                if player_manager and sequence.target_parameter:
                    value = sequence.get_value()
                    
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
        
        # Apply all buffered updates ONCE per parameter per frame
        for param_uid, update_info in self._frame_updates.items():
            value = update_info['value']
            sequence_type = update_info['sequence_type']
            
            # Apply modulation
            self._apply_modulation(param_uid, value, player_manager)
            
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
                if self._update_counter % 120 == 0:  # Log less frequently
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
            # Try global UID registry first (O(1) lookup)
            uid_registry = get_uid_registry()
            result = uid_registry.resolve(uid)
            
            if result:
                # Found in registry - blazing fast!
                return result
            
            # Fallback: Manual search (slow, but needed for UIDs registered before registry existed)
            # This also populates the registry for future lookups
            logger.debug(f"🔍 UID not in registry, performing fallback search: {uid[:50]}...")
            
            # OLD SLOW METHOD - kept as fallback only
            # Cache successful resolutions to avoid excessive logging
            if hasattr(self, '_uid_resolution_cache') and uid in self._uid_resolution_cache:
                return self._uid_resolution_cache[uid]
            
            # Parse UID: param_clip_{clip_id}_{param_name}_{timestamp}_{random}
            parts = uid.split('_')
            if len(parts) < 5 or parts[0] != 'param' or parts[1] != 'clip':
                logger.warning(f"Invalid UID format: {uid}")
                return None
            
            clip_id = parts[2]
            param_name = '_'.join(parts[3:-1])  # Reconstruct param_name (include everything except last random part)
            
            logger.debug(f"🔎 Parsing UID: clip_id={clip_id}, param_name={param_name}")
            
            # Search all players for the clip with matching UID
            for player_name, player in player_manager.players.items():
                if not player or not hasattr(player, 'layers'):
                    continue
                
                logger.debug(f"  🔍 Checking player {player_name} ({len(player.layers)} layers)")
                
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
                            
                            # Check if stored parameter has matching UID
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
                            elif param_name in effect_params:
                                # Parameter exists but UID doesn't match - register it anyway for this sequence
                                logger.warning(f"⚠️ Parameter '{param_name}' found but UID mismatch or missing. Registering UID: {uid[:50]}...")
                                result = (player, instance, param_name)
                                # Register in global registry
                                uid_registry = get_uid_registry()
                                uid_registry.register(uid, player, instance, param_name)
                                return result
            
            # Only warn once per UID
            if uid not in self._uid_warning_cache:
                logger.warning(f"❌ UID not found in any active layer: {uid}")
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
                    return
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
                    else:
                        logger.warning(f"❌ update_parameter failed for {param_name}")
                elif hasattr(effect_instance, param_name):
                    setattr(effect_instance, param_name, scaled_value)
                    logger.debug(f"✅ Applied: {param_name} = {scaled_value:.2f} via setattr [{player.__class__.__name__}]")
                    logger.debug(f"✅ Applied via setattr: {param_name} = {scaled_value:.4f}")
                else:
                    logger.warning(f"Parameter not found on effect instance: {param_name}")
                return
            
            # Legacy path format: player.<player_id>.clip.<clip_id>.effects[index].<param>
            parts = target_path.split('.')
            
            if len(parts) < 4 or parts[0] != 'player':
                logger.warning(f"Invalid target path: {target_path}")
                return
            
            player_id = parts[1]
            
            # Get player
            player = player_manager.get_player(player_id)
            if not player:
                logger.warning(f"Player not found: {player_id}")
                return
            
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
                        return
                elif i == len(parts) - 1:
                    # Last part is the parameter name
                    if hasattr(current, part):
                        setattr(current, part, value)
                        logger.debug(f"Applied modulation: {target_path} = {value}")
                    else:
                        logger.warning(f"Parameter not found: {part} in {target_path}")
                    return
                else:
                    # Navigate deeper
                    current = getattr(current, part, None)
                    if current is None:
                        logger.warning(f"Invalid path segment: {part} in {target_path}")
                        return
        
        except Exception as e:
            logger.error(f"Error applying modulation to {target_path}: {e}", exc_info=True)
    
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
