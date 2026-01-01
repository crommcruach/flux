"""
Audio Timeline - Manages splits, slots, and clip mappings

Splits divide the audio timeline into sections (slots).
Each slot can be mapped to a playlist clip.
Slot duration determines when slave playlists advance.
"""

import json
from typing import List, Dict, Optional
from pathlib import Path
from .logger import get_logger

logger = get_logger(__name__)


class AudioTimeline:
    """Manages timeline splits and slot-to-clip mappings"""
    
    # Minimum distance between splits (seconds)
    MIN_SPLIT_DISTANCE = 0.5
    
    def __init__(self):
        self.audio_file: Optional[str] = None
        self.duration: float = 0.0
        self.splits: List[float] = []  # [2.5, 4.0, 7.2, ...] (sorted)
        self.clip_mapping: Dict[int, str] = {}  # {0: "video/intro.mp4", 1: "video/main.mp4", ...}
        
    def load_audio(self, file_path: str, duration: float):
        """Initialize timeline with audio file
        
        Args:
            file_path: Path to audio file
            duration: Audio duration in seconds
        """
        self.audio_file = file_path
        self.duration = duration
        self.splits = []
        self.clip_mapping = {}
        logger.info(f"📐 Timeline initialized: {Path(file_path).name} ({duration:.2f}s)")
    
    def add_split(self, time: float) -> bool:
        """Add split point to timeline
        
        Args:
            time: Split time in seconds
            
        Returns:
            True if split was added, False if rejected
        """
        # Validate boundaries
        if time <= 0.0 or time >= self.duration:
            logger.debug(f"⚠️ Split rejected: time {time:.2f}s outside boundaries (0.0 - {self.duration:.2f}s)")
            return False
        
        # Check minimum distance from existing splits
        for split in self.splits:
            if abs(split - time) < self.MIN_SPLIT_DISTANCE:
                logger.debug(f"⚠️ Split rejected: too close to existing split at {split:.2f}s (min {self.MIN_SPLIT_DISTANCE}s)")
                return False
        
        # Add and sort
        self.splits.append(time)
        self.splits.sort()
        logger.info(f"✂️ Split added at {time:.2f}s (total: {len(self.splits)} splits)")
        return True
    
    def remove_split(self, time: float, threshold: float = 0.1) -> bool:
        """Remove split near given time
        
        Args:
            time: Target time in seconds
            threshold: Maximum distance to match (seconds)
            
        Returns:
            True if split was removed, False if not found
        """
        for i, split in enumerate(self.splits):
            if abs(split - time) < threshold:
                removed = self.splits.pop(i)
                logger.info(f"🗑️ Split removed at {removed:.2f}s (total: {len(self.splits)} splits)")
                return True
        
        logger.debug(f"⚠️ No split found near {time:.2f}s (threshold: {threshold}s)")
        return False
    
    def clear_splits(self):
        """Remove all splits"""
        count = len(self.splits)
        self.splits = []
        self.clip_mapping = {}
        logger.info(f"🗑️ All splits cleared ({count} removed)")
    
    def get_slots(self) -> List[Dict]:
        """Convert splits to slot list
        
        Slots are time ranges between splits:
        - No splits: No slots
        - 1 split at 2.5s → 2 slots: [0.0-2.5s], [2.5-duration]
        - 2 splits at 2.5s, 4.0s → 3 slots: [0.0-2.5s], [2.5-4.0s], [4.0-duration]
        
        Returns:
            List of slot dictionaries with index, start, end, duration, clip_name
        """
        if not self.splits:
            return []
        
        # Build slot boundaries: [0.0, split1, split2, ..., duration]
        points = [0.0] + self.splits + [self.duration]
        slots = []
        
        for i in range(len(points) - 1):
            slot = {
                'index': i,
                'start': points[i],
                'end': points[i + 1],
                'duration': points[i + 1] - points[i],
                'clip_name': self.clip_mapping.get(i, f"Slot {i + 1}")
            }
            slots.append(slot)
        
        return slots
    
    def get_current_slot(self, position: float) -> Optional[int]:
        """Get slot index at given position
        
        Args:
            position: Playback position in seconds
            
        Returns:
            Slot index (0-based) or None if no slots
        """
        slots = self.get_slots()
        
        for slot in slots:
            if slot['start'] <= position < slot['end']:
                return slot['index']
        
        # Handle edge case: position exactly at duration
        if slots and position >= self.duration:
            return slots[-1]['index']
        
        return None
    
    def get_slot_duration(self, slot_index: int) -> float:
        """Get duration of a specific slot
        
        Args:
            slot_index: Slot index (0-based)
            
        Returns:
            Slot duration in seconds, or 0.0 if slot doesn't exist
        """
        slots = self.get_slots()
        
        if slot_index < 0 or slot_index >= len(slots):
            return 0.0
        
        return slots[slot_index]['duration']
    
    def set_clip_mapping(self, slot_index: int, clip_name: str):
        """Map slot to clip name
        
        Args:
            slot_index: Slot index (0-based)
            clip_name: Clip identifier (e.g., "video/intro.mp4")
        """
        self.clip_mapping[slot_index] = clip_name
        logger.debug(f"🎬 Slot {slot_index} mapped to: {clip_name}")
    
    def get_clip_mapping(self, slot_index: int) -> Optional[str]:
        """Get clip name for slot
        
        Args:
            slot_index: Slot index (0-based)
            
        Returns:
            Clip name or None if not mapped
        """
        return self.clip_mapping.get(slot_index)
    
    def to_dict(self) -> Dict:
        """Export timeline to dictionary
        
        Returns:
            Dictionary with audio_file, duration, splits, clip_mapping, slots
        """
        return {
            'audio_file': self.audio_file,
            'duration': self.duration,
            'splits': self.splits,
            'clip_mapping': {str(k): v for k, v in self.clip_mapping.items()},  # JSON keys must be strings
            'slots': self.get_slots()
        }
    
    def from_dict(self, data: Dict):
        """Import timeline from dictionary
        
        Args:
            data: Dictionary with audio_file, duration, splits, clip_mapping
        """
        self.audio_file = data.get('audio_file')
        self.duration = data.get('duration', 0.0)
        self.splits = sorted(data.get('splits', []))  # Ensure sorted
        
        # Convert string keys back to int
        clip_mapping_raw = data.get('clip_mapping', {})
        self.clip_mapping = {int(k): v for k, v in clip_mapping_raw.items()}
        
        logger.info(f"📥 Timeline loaded: {len(self.splits)} splits, {len(self.clip_mapping)} mappings")
        if self.clip_mapping:
            logger.debug(f"   Restored clip mappings: {self.clip_mapping}")
    
    def save(self, file_path: str):
        """Save timeline to JSON file
        
        Args:
            file_path: Path to output JSON file
        """
        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2)
            
            logger.info(f"💾 Timeline saved: {file_path}")
        except Exception as e:
            logger.error(f"❌ Failed to save timeline: {e}")
            raise
    
    def load(self, file_path: str):
        """Load timeline from JSON file
        
        Args:
            file_path: Path to JSON file
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Timeline file not found: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.from_dict(data)
            logger.info(f"📂 Timeline loaded: {file_path}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load timeline: {e}")
            raise
    
    def get_stats(self) -> Dict:
        """Get timeline statistics
        
        Returns:
            Dictionary with split count, slot count, average slot duration
        """
        slots = self.get_slots()
        avg_duration = sum(s['duration'] for s in slots) / len(slots) if slots else 0.0
        
        return {
            'split_count': len(self.splits),
            'slot_count': len(slots),
            'avg_slot_duration': avg_duration,
            'mapped_slots': len(self.clip_mapping),
            'total_duration': self.duration
        }
