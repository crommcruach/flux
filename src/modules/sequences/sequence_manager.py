"""
Sequence Manager

Central coordinator for all parameter sequences.
Manages lifecycle, applies modulation, and handles parameter resolution.
"""

import logging
from typing import Dict, List, Optional, Any
from .base_sequence import BaseSequence

logger = logging.getLogger(__name__)


class SequenceManager:
    """Manages all parameter sequences"""
    
    def __init__(self, socketio=None):
        self.sequences: Dict[str, BaseSequence] = {}
        self._parameter_cache = {}  # Cache resolved parameter objects
        self.socketio = socketio  # SocketIO instance for real-time updates
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
        for sequence in self.sequences.values():
            if not sequence.enabled:
                continue
            
            try:
                # Update sequence state
                sequence.update(dt)
                
                # Apply modulation to target parameter
                if player_manager and sequence.target_parameter:
                    value = sequence.get_value()
                    logger.info(f"🎵 [{sequence.type}] {sequence.target_parameter} = {value:.2f} (enabled={sequence.enabled})")
                    self._apply_modulation(sequence.target_parameter, value, player_manager)
                    
                    # Emit parameter update via WebSocket for visual feedback
                    if self.socketio:
                        self.socketio.emit('parameter_update', {
                            'parameter': sequence.target_parameter,
                            'value': value
                        })
                        logger.debug(f"📡 Emitted parameter_update: {sequence.target_parameter} = {value:.2f}")
            
            except Exception as e:
                logger.error(f"Error updating sequence {sequence.id}: {e}", exc_info=True)
    
    def _apply_modulation(self, target_path: str, value: float, player_manager):
        """
        Apply modulated value to target parameter
        
        Args:
            target_path: Dot notation path (e.g., "player.video.clip.effects[0].brightness")
            value: Value to apply
            player_manager: PlayerManager instance
        """
        try:
            # Parse target path
            # Format: player.<player_id>.clip.<clip_id>.effects[index].<param>
            # Or: player.<player_id>.clip.<clip_id>.<param>
            
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
