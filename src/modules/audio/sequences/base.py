"""
Base Sequence Class

Abstract base class for all sequence types.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import uuid


class BaseSequence(ABC):
    """Abstract base class for parameter sequences"""
    
    def __init__(self, sequence_id: str = None, sequence_type: str = None, 
                 target_parameter: str = None):
        """
        Initialize base sequence
        
        Args:
            sequence_id: Unique identifier (auto-generated if None)
            sequence_type: Type of sequence (audio, lfo, timeline, envelope)
            target_parameter: Dot notation path to parameter (e.g., "player.video.clip.effects[0].brightness")
        """
        self.id = sequence_id or f"seq_{uuid.uuid4().hex[:8]}"
        self.type = sequence_type
        self.target_parameter = target_parameter
        self.enabled = True
        self.name = f"{sequence_type}_{self.id}" if sequence_type else self.id
    
    @abstractmethod
    def update(self, dt: float):
        """
        Update sequence state
        
        Args:
            dt: Delta time in seconds since last update
        """
        pass
    
    @abstractmethod
    def get_value(self) -> float:
        """
        Get current modulated value
        
        Returns:
            Current value to apply to target parameter
        """
        pass
    
    @abstractmethod
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize sequence to dictionary
        
        Returns:
            Dictionary representation of sequence
        """
        pass
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'BaseSequence':
        """
        Create sequence from dictionary
        
        Args:
            data: Dictionary representation
            
        Returns:
            Sequence instance
        """
        # To be implemented by subclasses
        raise NotImplementedError(f"Deserialize not implemented for {cls.__name__}")
    
    def toggle(self):
        """Toggle sequence enabled state"""
        self.enabled = not self.enabled
    
    def reset(self):
        """Reset sequence to initial state (optional, implemented by subclasses)"""
        pass
    
    def __repr__(self):
        return f"<{self.__class__.__name__} id={self.id} type={self.type} target={self.target_parameter}>"
