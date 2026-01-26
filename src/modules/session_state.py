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
import json
import time
import queue
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from .logger import get_logger
from .uid_registry import get_uid_registry

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
        
        logger.info(f"SessionStateManager initialisiert: {state_file_path} (async mode)")
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Lädt existierenden State oder erstellt leeren."""
        if os.path.exists(self.state_file_path):
            try:
                with open(self.state_file_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.info(f"✅ Session State geladen: {len(state.get('players', {}))} Player")
                return state
            except Exception as e:
                logger.error(f"❌ Fehler beim Laden von session_state.json: {e}")
                return self._create_empty_state()
        else:
            logger.info("📄 Keine session_state.json gefunden - erstelle neue")
            return self._create_empty_state()
    
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
        try:
            # State in Datei schreiben mit Retry-Logik für Windows File-Locking
            os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
            
            # Versuche bis zu 3x zu speichern (Windows kann Dateien kurzzeitig locken)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with open(self.state_file_path, 'w', encoding='utf-8') as f:
                        json.dump(state, f, indent=2, ensure_ascii=False)
                    break  # Erfolg - raus aus Retry-Loop
                except PermissionError as perm_err:
                    if attempt < max_retries - 1:
                        logger.warning(f"⚠️ Permission denied beim Speichern (Versuch {attempt + 1}/{max_retries}), retry in 0.5s...")
                        time.sleep(0.5)
                    else:
                        logger.warning(f"⚠️ Session State konnte nicht gespeichert werden (Datei gesperrt): {perm_err}")
                        logger.info("💡 Tipp: Schließe alle Programme die session_state.json geöffnet haben")
                        return
            
            self._last_save_time = time.time()
            logger.debug(f"💾 Session State async saved: {len(state.get('players', {}))} Player")
            
        except Exception as e:
            logger.error(f"❌ Fehler beim async Speichern von session_state.json: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _create_empty_state(self) -> Dict[str, Any]:
        """Erstellt leere State-Struktur."""
        return {
            "last_updated": datetime.now().isoformat(),
            "players": {
                "video": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": True,
                    "loop": True,
                    "global_effects": []
                },
                "artnet": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": True,
                    "loop": True,
                    "global_effects": []
                }
            },
            "sequencer": {
                "mode_active": False,
                "audio_file": None,
                "timeline": {
                    "duration": 0.0,
                    "splits": [],
                    "clip_mapping": {}
                },
                "last_position": 0.0
            },
            "audio_analyzer": {
                "device": None,
                "running": False,
                "config": {},
                "bpm": {
                    "enabled": False,
                    "bpm": 0.0,
                    "mode": "auto",
                    "manual_bpm": None
                }
            }
        }
    
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
                logger.debug(f"📝 Session State queued for async save (debouncing: 1s)")
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
        
        Args:
            player_manager: PlayerManager-Instanz
            clip_registry: ClipRegistry-Instanz
            force: Ignored (always synchronous)
            
        Returns:
            True bei Erfolg
        """
        try:
            state = self._build_state_dict(player_manager, clip_registry, capture_active=True)
            self._state = state
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
        
        Args:
            player_manager: PlayerManager instance
            clip_registry: ClipRegistry instance
            force: Ignored (always synchronous)
            
        Returns:
            True on success
        """
        try:
            state = self._build_state_dict(player_manager, clip_registry, capture_active=False)
            self._state = state
            self._do_file_write(state)
            return True
        except Exception as e:
            logger.error(f"❌ Error saving without capture: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _build_state_dict(self, player_manager, clip_registry, capture_active: bool = True) -> Dict[str, Any]:
        """Build the complete state dictionary for saving."""
        state = {
            "last_updated": datetime.now().isoformat()
        }
        
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
        
        # Video player settings speichern (resolution, autosize)
        if 'video_player_settings' in self._state:
            state["video_player_settings"] = self._state['video_player_settings'].copy()
            logger.debug(f"🎬 Video player settings saved: {state['video_player_settings']}")
        
        # LEGACY: Sequences removed from root - now stored per-clip/per-playlist
        # Sequences are managed by SequenceManager and linked to specific parameters
        
        # Save playlists system
        if hasattr(player_manager, 'playlist_system') and player_manager.playlist_system:
            # Optionally capture current active playlist state before saving
            if capture_active:
                player_manager.playlist_system.capture_active_playlist_state()
            state['playlists'] = player_manager.playlist_system.serialize_all()
            logger.debug(f"💾 Saved playlists system: {len(state['playlists'].get('items', {}))} playlists (capture_active={capture_active})")
        
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
            
            # ========== PLAYLISTS SYSTEM RESTAURIEREN ==========
            # Try new name first, fallback to old name for backward compatibility
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
        Löscht Session-State (Reset).
        
        Returns:
            True bei Erfolg
        """
        try:
            self._state = self._create_empty_state()
            if os.path.exists(self.state_file_path):
                os.remove(self.state_file_path)
            logger.info("🗑️ Session State gelöscht")
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Löschen von session_state.json: {e}")
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
