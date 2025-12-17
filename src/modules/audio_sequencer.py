"""
Audio Sequencer - Main controller for audio-driven timeline

Coordinates AudioEngine and AudioTimeline to:
- Monitor playback position (50ms loop)
- Detect slot boundary crossings
- Trigger master/slave playlist advances
- Provide callbacks for UI updates
"""

import threading
import time
from typing import Optional, Callable, Dict
from .audio_engine import AudioEngine
from .audio_timeline import AudioTimeline
from .logger import get_logger

logger = get_logger(__name__)


class AudioSequencer:
    """Main audio sequencer controller
    
    When sequencer mode is ON:
    - Sequencer is the MASTER timeline controller
    - All playlists are SLAVES following slot boundaries
    - Each slot boundary triggers next clip in all slave playlists
    """
    
    # Monitoring interval (seconds)
    MONITOR_INTERVAL = 0.1  # 100ms = 10 updates/sec (reduced from 50ms for performance)
    
    def __init__(self, player_manager=None):
        self.engine = AudioEngine()
        self.timeline = AudioTimeline()
        self.player_manager = player_manager
        
        # Monitoring thread
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_active = False
        self.current_slot_index: Optional[int] = None
        
        # Callbacks for UI updates
        self.on_slot_change: Optional[Callable[[int], None]] = None
        self.on_position_update: Optional[Callable[[float, Optional[int]], None]] = None
        
        logger.info("🎵 AudioSequencer initialized")
    
    def load_audio(self, file_path: str) -> Dict:
        """Load audio file and initialize timeline
        
        Args:
            file_path: Path to audio file
            
        Returns:
            Dictionary with metadata (duration, sample_rate, etc.)
        """
        try:
            metadata = self.engine.load(file_path)
            self.timeline.load_audio(file_path, metadata['duration'])
            self.current_slot_index = None
            
            logger.info(f"🎼 Audio loaded into sequencer: {file_path}")
            return {
                'duration': metadata['duration'],
                'sample_rate': metadata['sample_rate'],
                'channels': metadata['channels'],
                'audio_file': file_path
            }
        except Exception as e:
            logger.error(f"❌ Failed to load audio: {e}")
            raise
    
    def play(self):
        """Start playback and monitoring"""
        try:
            # Initialize current slot to the slot at current position
            position = self.engine.get_position()
            self.current_slot_index = self.timeline.get_current_slot(position)
            
            # Initialize all playlists to match current slot
            if self.player_manager:
                initial_slot = self.current_slot_index if self.current_slot_index is not None else 0
                logger.info(f"🎬 Initializing playlists to slot {initial_slot}")
                self.player_manager.sequencer_advance_slaves(initial_slot, force_reload=True)
            
            # Start audio playback
            self.engine.play()
            
            # Start monitoring loop
            if not self.monitor_active:
                self._start_monitoring()
            
            logger.info(f"▶️ Sequencer playback started at slot {self.current_slot_index}")
        except Exception as e:
            logger.error(f"❌ Failed to start playback: {e}")
            raise
    
    def pause(self):
        """Pause playback (monitoring continues)"""
        self.engine.pause()
        logger.info("⏸️ Sequencer playback paused")
    
    def stop(self):
        """Stop playback and reset"""
        self.engine.stop()
        self._stop_monitoring()
        self.current_slot_index = None
        logger.info("⏹️ Sequencer playback stopped")
    
    def seek(self, position: float):
        """Seek to position
        
        Args:
            position: Target position in seconds
        """
        self.engine.seek(position)
        
        # Update current slot immediately
        new_slot = self.timeline.get_current_slot(position)
        if new_slot != self.current_slot_index:
            self.current_slot_index = new_slot
            if self.on_slot_change:
                self.on_slot_change(new_slot)
        
        logger.debug(f"⏩ Sequencer seek to {position:.2f}s (slot {new_slot})")
    
    def get_position(self) -> float:
        """Get current playback position
        
        Returns:
            Position in seconds
        """
        return self.engine.get_position()
    
    def add_split(self, time: float) -> bool:
        """Add split point to timeline
        
        Args:
            time: Split time in seconds
            
        Returns:
            True if added, False if rejected
        """
        success = self.timeline.add_split(time)
        if success:
            # Recalculate current slot
            position = self.get_position()
            self.current_slot_index = self.timeline.get_current_slot(position)
        return success
    
    def remove_split(self, time: float) -> bool:
        """Remove split point from timeline
        
        Args:
            time: Split time in seconds (finds nearest within threshold)
            
        Returns:
            True if removed, False if not found
        """
        success = self.timeline.remove_split(time)
        if success:
            # Recalculate current slot
            position = self.get_position()
            self.current_slot_index = self.timeline.get_current_slot(position)
        return success
    
    def get_timeline_data(self) -> Dict:
        """Get full timeline data including splits and slots
        
        Returns:
            Dictionary with audio_file, duration, splits, slots, clip_mapping
        """
        return self.timeline.to_dict()
    
    def set_clip_mapping(self, slot_index: int, clip_name: str):
        """Map slot to clip name
        
        Args:
            slot_index: Slot index (0-based)
            clip_name: Clip identifier
        """
        self.timeline.set_clip_mapping(slot_index, clip_name)
    
    def _start_monitoring(self):
        """Start monitoring thread (50ms interval)"""
        if self.monitor_active:
            return
        
        self.monitor_active = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.debug("👁️ Monitoring loop started")
    
    def _stop_monitoring(self):
        """Stop monitoring thread"""
        self.monitor_active = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)
        logger.debug("👁️ Monitoring loop stopped")
    
    def _monitor_loop(self):
        """Monitoring loop - checks position every 100ms
        
        Detects slot boundary crossings and triggers:
        1. Master/slave playlist advances via player_manager
        2. UI updates via callbacks
        """
        logger.debug("🔄 Monitor loop started")
        
        while self.monitor_active:
            try:
                position = self.engine.get_position()
                
                # Check for slot change
                current_slot = self.timeline.get_current_slot(position)
                
                if current_slot != self.current_slot_index and current_slot is not None:
                    logger.info(f"🎯 Slot changed: {self.current_slot_index} → {current_slot} at position {position:.2f}s")
                    self._handle_slot_change(current_slot)
                    self.current_slot_index = current_slot
                
                # Notify position update (for UI)
                if self.on_position_update:
                    self.on_position_update(position, current_slot)
                
            except Exception as e:
                logger.error(f"❌ Monitor loop error: {e}", exc_info=True)
            
            time.sleep(self.MONITOR_INTERVAL)
        
        logger.debug("🔄 Monitor loop finished")
    
    def _handle_slot_change(self, new_slot_index: int):
        """Handle slot boundary crossing
        
        When sequencer mode is ON:
        - Sequencer is the MASTER timeline controller
        - All playlists are SLAVES following slot boundaries
        - Each slot advance triggers next clip in all slave playlists
        
        Args:
            new_slot_index: New slot index (0-based)
        """
        logger.info(f"🎬 Slot change: {new_slot_index}")
        
        # Trigger master/slave advance via player_manager
        if self.player_manager:
            try:
                self.player_manager.sequencer_advance_slaves(new_slot_index)
            except Exception as e:
                logger.error(f"❌ Failed to advance slaves: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ No player_manager available to advance slaves!")
        
        # Call UI callback
        if self.on_slot_change:
            try:
                self.on_slot_change(new_slot_index)
            except Exception as e:
                logger.error(f"❌ Slot change callback error: {e}")
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        self.engine.cleanup()
        logger.info("🧹 AudioSequencer cleaned up")
