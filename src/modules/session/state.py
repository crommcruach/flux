"""
Session State Manager - Persistiert Player-Status für Page-Reloads

Speichert automatisch:
- Playlists (Video + Art-Net) mit allen Clip-Details
- Generator-Parameter
- Effekt-Ketten pro Clip
- Player-Effekte (global)
- Autoplay/Loop-Settings
- Aktueller Playlist-Index
"""

import os
import time
import queue
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from ..core.logger import get_logger
from ..player.clips.uid_registry import get_uid_registry
from .session_persistence import SessionPersistence

logger = get_logger(__name__)


class SessionStateManager:
    """Verwaltet persistenten Session-State für Player-Konfiguration."""
    
    def __init__(self, state_file_path: str, sequence_manager=None):
        """
        Initialisiert SessionStateManager.
        
        Args:
            state_file_path: Pfad zur session_state.json Datei
            sequence_manager: Optional SequenceManager for sequence persistence
        """
        self.state_file_path = state_file_path
        self.sequence_manager = sequence_manager
        
        # Initialize persistence layer
        data_dir = os.path.dirname(state_file_path)
        self.persistence = SessionPersistence(data_dir)
        
        self._state = self._load_or_create()
        self._last_save_time = 0
        self._min_save_interval = 0.5  # Minimum 500ms zwischen Saves (Debouncing)
        
        # Async save infrastructure
        self._save_queue = queue.Queue()
        self._pending_save = False
        self._pending_save_data = None
        self._shutdown = False
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True, name="SessionStateSaver")
        self._save_thread.start()
        
        logger.info(f"SessionStateManager initialized: {os.path.basename(state_file_path)} (async mode)")
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load existing state or create empty."""
        state = self.persistence.read_from_file(self.state_file_path)
        if state:
            return state
        else:
            logger.info("No session found - creating new")
            return SessionPersistence.create_empty_state()
    
    def _save_worker(self):
        """Background thread for async file I/O with debouncing."""
        debounce_interval = 1.0  # Wait 1 second after last change before writing
        
        while not self._shutdown:
            try:
                # Check for pending save with timeout
                if self._pending_save and self._pending_save_data:
                    # Wait for debounce interval
                    time.sleep(debounce_interval)
                    
                    # Check if still pending (no new changes arrived)
                    if self._pending_save and self._pending_save_data:
                        save_data = self._pending_save_data
                        self._pending_save = False
                        self._pending_save_data = None
                        
                        # Perform the actual file write
                        self._do_file_write(save_data)
                else:
                    # No pending save, wait a bit before checking again
                    time.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"❌ Background save worker error: {e}")
                import traceback
                logger.error(traceback.format_exc())
    
    def _do_file_write(self, state: Dict[str, Any]):
        """Perform the actual file write operation."""
        success = self.persistence.write_to_file(state, self.state_file_path)
        if success:
            self._last_save_time = time.time()
    
    def _create_empty_state(self) -> Dict[str, Any]:
        """Create empty state structure (delegated to persistence layer)."""
        return SessionPersistence.create_empty_state()
    
    def save_async(self, player_manager, clip_registry, force: bool = False) -> bool:
        """
        Speichert aktuellen Player-Status asynchron (mit Debouncing).
        Updates in-memory state immediately, queues file write for background thread.
        
        Args:
            player_manager: PlayerManager-Instanz
            clip_registry: ClipRegistry-Instanz
            force: If True, skip debouncing and write immediately (blocks until complete)
            
        Returns:
            True bei Erfolg
        """
        try:
            # Build state dict (same as synchronous save)
            state = self._build_state_dict(player_manager, clip_registry)
            
            # Update in-memory state immediately
            self._state = state
            
            if force:
                # Force immediate write (blocks current thread)
                self._do_file_write(state)
                return True
            else:
                # Queue for async write with debouncing
                self._pending_save = True
                self._pending_save_data = state
                return True
                
        except Exception as e:
            logger.error(f"❌ Fehler beim Vorbereiten des async Save: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def save(self, player_manager, clip_registry, force: bool = False) -> bool:
        """
        Speichert aktuellen Player-Status synchron (DEPRECATED - use save_async instead).
        This method is kept for backward compatibility and critical operations only.
        Flushes ALL session data from RAM to disk immediately, including any pending async writes.
        
        Args:
            player_manager: PlayerManager-Instanz
            clip_registry: ClipRegistry-Instanz
            force: Ignored (always synchronous)
            
        Returns:
            True bei Erfolg
        """
        try:
            # Build complete state from self._state (includes editor, outputs, etc.)
            state = self._build_state_dict(player_manager, clip_registry, capture_active=True)
            
            # Update in-memory state
            self._state = state
            
            # Clear any pending async save (we're doing immediate write)
            self._pending_save = False
            self._pending_save_data = None
            
            # Write to disk immediately
            self._do_file_write(state)
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim synchronen Speichern: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def save_without_capture(self, player_manager, clip_registry, force: bool = False) -> bool:
        """
        Save session state WITHOUT capturing active playlist state.
        Use this when you've already explicitly updated playlist state and don't want it overwritten.
        Flushes ALL session data from RAM to disk immediately, including any pending async writes.
        
        Args:
            player_manager: PlayerManager instance
            clip_registry: ClipRegistry instance
            force: Ignored (always synchronous)
            
        Returns:
            True on success
        """
        try:
            # Build complete state from self._state (includes editor, outputs, etc.)
            state = self._build_state_dict(player_manager, clip_registry, capture_active=False)
            
            # Update in-memory state
            self._state = state
            
            # Clear any pending async save (we're doing immediate write)
            self._pending_save = False
            self._pending_save_data = None
            
            # Write to disk immediately
            self._do_file_write(state)
            return True
        except Exception as e:
            logger.error(f"❌ Error saving without capture: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _build_state_dict(self, player_manager, clip_registry, capture_active: bool = True) -> Dict[str, Any]:
        """Build the complete state dictionary for saving."""
        # Start with existing state to preserve editor, outputs, and other sections
        state = self._state.copy() if self._state else {}
        
        # Update timestamp
        state["last_updated"] = datetime.now().isoformat()
        
        # LEGACY: Old player state save code removed (200+ lines)
        # All player/playlist/sequencer state is now saved by playlists system
        # Root level: all config sections flattened (api, artnet, video, audio_analyzer, etc.) + playlists
        
        # Save application config - flatten all config sections to root level
        if hasattr(player_manager, 'audio_analyzer') and player_manager.audio_analyzer:
            if player_manager.audio_analyzer.config:
                # Merge all config sections directly into state root
                config = player_manager.audio_analyzer.config.copy()
                for key, value in config.items():
                    state[key] = value
                
                # Add audio_analyzer runtime state at root level
                audio_analyzer = player_manager.audio_analyzer
                bpm_status = audio_analyzer.get_bpm_status()
                state["audio_analyzer"] = {
                    "device": audio_analyzer.device,
                    "running": audio_analyzer._running,
                    "bpm": {
                        "enabled": bpm_status.get('enabled', False),
                        "bpm": bpm_status.get('bpm', 0.0),
                        "mode": bpm_status.get('mode', 'auto'),
                        "manual_bpm": audio_analyzer._manual_bpm if hasattr(audio_analyzer, '_manual_bpm') else None
                    }
                }
                logger.debug(f"⚙️ Application config saved (flattened to root) with audio_analyzer: device={audio_analyzer.device}, bpm_enabled={bpm_status.get('enabled')}")
        
        # Master/Slave state is now stored per-playlist (playlist.master_player)
        # No need for root-level master_playlist field
        
        # Explicitly preserve sections that are updated via separate methods
        # (Even though they're in the initial copy, make it explicit for clarity)
        
        # Video player settings
        if 'video_player_settings' in self._state:
            state["video_player_settings"] = self._state['video_player_settings'].copy()
        
        # Output routing (updated via save_output_state())
        if 'outputs' in self._state:
            state['outputs'] = self._state['outputs'].copy()
        
        # Canvas editor state (updated via set_editor_state())
        if 'editor' in self._state:
            state['editor'] = self._state['editor'].copy()
        
        # ArtNet routing state (updated via set_artnet_routing_state())
        if 'artnet_routing' in self._state:
            state['artnet_routing'] = self._state['artnet_routing'].copy()
        
        # Sequences (if stored at root level - legacy)
        if 'sequences' in self._state:
            state['sequences'] = self._state['sequences'].copy()
        
        # Save playlists system
        if hasattr(player_manager, 'playlist_system') and player_manager.playlist_system:
            # Optionally capture current active playlist state before saving
            if capture_active:
                player_manager.playlist_system.capture_active_playlist_state()
            state['playlists'] = player_manager.playlist_system.serialize_all()
        
        # Save complete clip registry (all clips, effects, parameters)
        state['clip_registry'] = clip_registry.serialize()
        
        return state
    
    def _save_sequences(self):
        """Save all sequences flat by UID"""
        if not self.sequence_manager:
            return {}
        
        sequences_by_uid = {}
        for seq in self.sequence_manager.get_all():
            uid = seq.target_parameter
            if uid not in sequences_by_uid:
                sequences_by_uid[uid] = []
            sequences_by_uid[uid].append(seq.serialize())
        
        logger.info(f"💾 Saved {len(sequences_by_uid)} parameter sequences (flat by UID)")
        return sequences_by_uid
    
    def load(self) -> Dict[str, Any]:
        """
        Lädt gespeicherten Session-State.
        
        Returns:
            State-Dict mit Player-Konfigurationen
        """
        return self._state.copy()
    
    def get_player_state(self, player_id: str) -> Optional[Dict[str, Any]]:
        """
        Holt State für spezifischen Player.
        
        Args:
            player_id: 'video' oder 'artnet'
            
        Returns:
            Player-State-Dict oder None
        """
        return self._state.get('players', {}).get(player_id)
    
    def restore(self, player_manager, clip_registry, config) -> bool:
        """
        Restauriert Player-Status aus Session State (mit Layer-Support und Migration).
        
        Args:
            player_manager: PlayerManager-Instanz
            clip_registry: ClipRegistry-Instanz
            config: Config-Dict für FrameSource-Initialisierung
            
        Returns:
            True bei Erfolg
        """
        try:
            state = self._state
            
            if not state:
                logger.info("Kein Session State zum Restaurieren vorhanden")
                return False
            
            # LEGACY: Root-level players state restore removed
            # All player state is now restored by PlaylistManager when playlists are loaded/activated
            # Old session files with root-level 'players' will be ignored - data is in playlists now
            
            # ========== SEQUENCES RESTAURIEREN (FLAT BY UID) ==========
            sequences_data = state.get('sequences', {})
            if sequences_data and self.sequence_manager and player_manager.audio_analyzer:
                logger.info(f"🔄 Restoring {len(sequences_data)} parameter sequences from flat structure...")
                
                for uid, seq_list in sequences_data.items():
                    for seq_data in seq_list:
                        try:
                            seq_type = seq_data.get('type')
                            
                            if seq_type == 'audio':
                                from .sequences import AudioSequence
                                sequence = AudioSequence.deserialize(seq_data, player_manager.audio_analyzer)
                            elif seq_type == 'lfo':
                                from .sequences import LFOSequence
                                sequence = LFOSequence.deserialize(seq_data)
                            elif seq_type == 'timeline':
                                from .sequences import TimelineSequence
                                sequence = TimelineSequence.deserialize(seq_data)
                            elif seq_type == 'bpm':
                                from .sequences import BPMSequence
                                sequence = BPMSequence.deserialize(seq_data, player_manager.audio_analyzer)
                            else:
                                logger.warning(f"Unknown sequence type: {seq_type}")
                                continue
                            
                            # Add to sequence manager
                            self.sequence_manager.create(sequence)
                            logger.info(f"✅ Restored sequence: {sequence.id} (UID: {uid})")
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to restore sequence for UID {uid}: {e}")
            
            # LEGACY: Sequencer state restore removed - now handled per-playlist by PlaylistManager
            # When playlists are activated, their sequencer timeline/mode is loaded automatically
            
            # ========== AUDIO ANALYZER BPM STATE RESTAURIEREN ==========
            # New structure: audio_analyzer at root level
            # Old structure: config.audio_analyzer or root level
            config_data = state.get('config', {})
            audio_analyzer_data = state.get('audio_analyzer') or config_data.get('audio_analyzer')
            if audio_analyzer_data and hasattr(player_manager, 'audio_analyzer') and player_manager.audio_analyzer:
                try:
                    bpm_data = audio_analyzer_data.get('bpm', {})
                    if bpm_data:
                        audio_analyzer = player_manager.audio_analyzer
                        
                        # Restore manual BPM if set
                        manual_bpm = bpm_data.get('manual_bpm')
                        if manual_bpm and bpm_data.get('mode') == 'manual':
                            audio_analyzer.set_manual_bpm(manual_bpm)
                            logger.debug(f"🎵 Restored manual BPM: {manual_bpm}")
                        
                        # Restore BPM enabled state
                        # If 'enabled' key doesn't exist in saved data, default to True (enabled by default)
                        if 'enabled' in bpm_data:
                            # Explicitly saved state exists - respect it
                            enabled = bpm_data['enabled']
                        else:
                            # No explicit enabled state saved - default to enabled
                            enabled = True
                            
                        if enabled:
                            audio_analyzer.enable_bpm_detection(True)
                            logger.info(f"🎵 BPM detection restored: enabled=True, mode={bpm_data.get('mode', 'auto')}")
                        else:
                            audio_analyzer.enable_bpm_detection(False)
                            logger.info("🎵 BPM detection disabled (from saved state)")
                    else:
                        # No saved BPM data - enable by default
                        audio_analyzer = player_manager.audio_analyzer
                        audio_analyzer.enable_bpm_detection(True)
                        logger.info("🎵 BPM detection enabled by default (no saved state)")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore BPM state: {e}")
            
            # Master/Slave state is now restored per-playlist when activated
            # No need to restore root-level master_playlist field
            
            # ========== CLIP REGISTRY RESTAURIEREN ==========
            # CRITICAL: Restore clip registry BEFORE playlists!
            # When playlists load, they will use the restored clip data (layers, params)
            # If we restore playlists first, they register clips with default state and overwrite saved data
            clip_registry_data = state.get('clip_registry')
            if clip_registry_data:
                try:
                    clip_registry.deserialize(clip_registry_data)
                    logger.info(f"📋 Clip registry restored: {len(clip_registry.clips)} clips with complete state")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore clip registry: {e}")
            
            # ========== PLAYLISTS SYSTEM RESTAURIEREN ==========
            # Try new name first, fallback to old name for backward compatibility
            # Playlists load AFTER clip registry so they use the restored clip data
            playlists_data = state.get('playlists') or state.get('multi_playlist_system')
            if playlists_data and hasattr(player_manager, 'playlist_system'):
                try:
                    success = player_manager.playlist_system.load_from_dict(playlists_data)
                    if success:
                        num_playlists = len(playlists_data.get('items', playlists_data.get('playlists', [])))
                        logger.info(f"📋 Playlists system restored: {num_playlists} playlists")
                    else:
                        logger.warning("⚠️ Failed to restore playlists system")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore playlists system: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Restaurieren von Session State: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def clear(self) -> bool:
        """
        Reset session state (clear all data).
        
        Returns:
            True on success
        """
        try:
            self._state = SessionPersistence.create_empty_state()
            success = self.persistence.delete_file(self.state_file_path)
            if success:
                logger.info("Session state cleared")
            return True
        except Exception as e:
            logger.error(f"Error clearing session state: {e}")
            return False
    
    def save_output_state(self, player_name: str, output_state: dict):
        """
        Save output routing state to session
        
        Args:
            player_name: Name of the player ('video' or 'artnet')
            output_state: Output state dictionary from OutputManager.get_state()
        """
        if 'outputs' not in self._state:
            self._state['outputs'] = {}
        
        self._state['outputs'][player_name] = {
            'outputs': output_state.get('outputs', {}),
            'slices': output_state.get('slices', {}),
            'enabled_outputs': output_state.get('enabled_outputs', []),
            'timestamp': time.time()
        }
        
        # Trigger async save
        self._pending_save = True
        self._pending_save_data = self._state.copy()
        
        logger.debug(f"Output state saved for {player_name}")
    
    def get_output_state(self, player_name: str) -> dict:
        """
        Load output routing state from session
        
        Args:
            player_name: Name of the player ('video' or 'artnet')
            
        Returns:
            dict: Output state or empty dict if not found
        """
        if 'outputs' not in self._state:
            return {}
        return self._state['outputs'].get(player_name, {})
    
    def clear_output_state(self, player_name: str):
        """
        Clear output state for specific player
        
        Args:
            player_name: Name of the player ('video' or 'artnet')
        """
        if 'outputs' in self._state and player_name in self._state['outputs']:
            del self._state['outputs'][player_name]
            # Trigger async save
            self._pending_save = True
            self._pending_save_data = self._state.copy()
            logger.debug(f"Output state cleared for {player_name}")
    
    def set_video_player_settings(self, settings: dict):
        """
        Save video player settings (resolution, autosize, etc.)
        
        Args:
            settings: Dictionary with video player settings
        """
        if 'video_player_settings' not in self._state:
            self._state['video_player_settings'] = {}
        self._state['video_player_settings'] = settings.copy()
        # Trigger async save
        self._pending_save = True
        self._pending_save_data = self._state.copy()
        logger.debug(f"🎬 Video player settings updated: {settings}")
    
    def get_video_player_settings(self) -> dict:
        """
        Get video player settings.
        
        Returns:
            Dictionary with video player settings
        """
        return self._state.get('video_player_settings', {}).copy()
    
    def set_artnet_player_settings(self, settings: dict):
        """
        Save art-net player settings (resolution, autosize, etc.)
        
        Args:
            settings: Dictionary with art-net player settings
        """
        if 'artnet_player_settings' not in self._state:
            self._state['artnet_player_settings'] = {}
        self._state['artnet_player_settings'] = settings.copy()
        # Trigger async save
        self._pending_save = True
        self._pending_save_data = self._state.copy()
        logger.debug(f"🎨 Art-Net player settings updated: {settings}")
    
    def get_artnet_player_settings(self) -> dict:
        """
        Get art-net player settings.
        
        Returns:
            Dictionary with art-net player settings
        """
        return self._state.get('artnet_player_settings', {}).copy()
    
    def set_editor_state(self, editor_data: dict):
        """
        Save editor state (canvas, shapes, settings, etc.)
        
        Args:
            editor_data: Dictionary with editor state
        """
        if 'editor' not in self._state:
            self._state['editor'] = {}
        self._state['editor'] = editor_data.copy()
        # Trigger async save
        self._pending_save = True
        self._pending_save_data = self._state.copy()
        logger.debug(f"🎨 Editor state updated")
    
    def get_editor_state(self) -> dict:
        """
        Get editor state.
        
        Returns:
            Dictionary with editor state
        """
        return self._state.get('editor', {}).copy()
    
    def set_artnet_routing_state(self, routing_data: dict):
        """
        Save ArtNet routing state (objects, outputs, assignments).
        
        Args:
            routing_data: Dictionary with routing state from routing_manager.get_state()
        """
        if 'artnet_routing' not in self._state:
            self._state['artnet_routing'] = {}
        self._state['artnet_routing'] = routing_data.copy()
        # Trigger async save
        self._pending_save = True
        self._pending_save_data = self._state.copy()
        logger.debug(f"🎛️  ArtNet routing state updated")
    
    def get_artnet_routing_state(self) -> dict:
        """
        Get ArtNet routing state.
        
        Returns:
            Dictionary with artnet routing state (objects + outputs)
        """
        return self._state.get('artnet_routing', {}).copy()
    
    def get_state_file_path(self) -> str:
        """
        Get the path to the session state file.
        
        Returns:
            Absolute path to session_state.json
        """
        return self.state_file_path
    
    def set_sequence_manager(self, sequence_manager):
        """
        Set the sequence manager for sequence persistence.
        
        Args:
            sequence_manager: SequenceManager instance
        """
        self.sequence_manager = sequence_manager
        logger.info("SequenceManager attached to SessionStateManager")


# Singleton-Instanz
_session_state_manager: Optional[SessionStateManager] = None


def init_session_state(state_file_path: str) -> SessionStateManager:
    """
    Initialisiert globalen SessionStateManager.
    
    Args:
        state_file_path: Pfad zur session_state.json
        
    Returns:
        SessionStateManager-Instanz
    """
    global _session_state_manager
    _session_state_manager = SessionStateManager(state_file_path)
    return _session_state_manager


def get_session_state() -> Optional[SessionStateManager]:
    """
    Holt globalen SessionStateManager.
    
    Returns:
        SessionStateManager-Instanz oder None
    """
    return _session_state_manager
