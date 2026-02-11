"""
Session Persistence - File I/O operations for session state

This module handles all file operations for session state management.
Separated from session_state.py to cleanly distinguish:
- Runtime state management (session_state.py)
- File persistence (this module)
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from ..logger import get_logger

logger = get_logger(__name__)


class SessionPersistence:
    """Handles file I/O operations for session state."""
    
    def __init__(self, data_dir: str):
        """
        Initialize persistence layer.
        
        Args:
            data_dir: Directory for session state files
        """
        self.data_dir = data_dir
        self.default_file_path = os.path.join(data_dir, "session_state.json")
        os.makedirs(data_dir, exist_ok=True)
    
    def read_from_file(self, file_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Read session state from JSON file.
        
        Args:
            file_path: Path to session file (uses default if None)
            
        Returns:
            State dict or None if file doesn't exist/error
        """
        path = file_path or self.default_file_path
        
        if not os.path.exists(path):
            logger.info(f"No session file found: {path}")
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            playlists_count = len(state.get('playlists', {}).get('items', {}))
            clips_count = len(state.get('clip_registry', {}).get('clips', {}))
            logger.info(f"Session loaded: {os.path.basename(path)} ({playlists_count} playlists, {clips_count} clips)")
            return state
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading session file {path}: {e}")
            return None
    
    def write_to_file(self, state: Dict[str, Any], file_path: Optional[str] = None) -> bool:
        """
        Write session state to JSON file with retry logic.
        
        Args:
            state: State dictionary to write
            file_path: Path to session file (uses default if None)
            
        Returns:
            True on success, False on failure
        """
        path = file_path or self.default_file_path
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Retry up to 3 times (Windows can lock files temporarily)
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    with open(path, 'w', encoding='utf-8') as f:
                        json.dump(state, f, indent=2, ensure_ascii=False)
                    
                    playlists_count = len(state.get('playlists', {}).get('items', {}))
                    clips_count = len(state.get('clip_registry', {}).get('clips', {}))
                    logger.info(f"Session saved: {os.path.basename(path)} ({playlists_count} playlists, {clips_count} clips)")
                    return True
                    
                except PermissionError as perm_err:
                    if attempt < max_retries - 1:
                        logger.warning(f"File locked (attempt {attempt + 1}/{max_retries}), retrying in 0.5s...")
                        time.sleep(0.5)
                    else:
                        logger.error(f"Failed to write session file (locked): {perm_err}")
                        logger.info("Tip: Close any programs that have session_state.json open")
                        return False
            
            return False
            
        except Exception as e:
            logger.error(f"Error writing session file {path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def list_saved_sessions(self, pattern: str = "*.json") -> List[Tuple[str, datetime]]:
        """
        List all saved session files in data directory.
        
        Args:
            pattern: Glob pattern for matching files
            
        Returns:
            List of (filename, modified_time) tuples, sorted by time (newest first)
        """
        try:
            import glob
            files = []
            
            for file_path in glob.glob(os.path.join(self.data_dir, pattern)):
                if os.path.isfile(file_path):
                    mtime = os.path.getmtime(file_path)
                    files.append((os.path.basename(file_path), datetime.fromtimestamp(mtime)))
            
            # Sort by modification time, newest first
            files.sort(key=lambda x: x[1], reverse=True)
            return files
            
        except Exception as e:
            logger.error(f"Error listing saved sessions: {e}")
            return []
    
    def delete_file(self, file_path: str) -> bool:
        """
        Delete a session file.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True on success
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted session file: {os.path.basename(file_path)}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting session file {file_path}: {e}")
            return False
    
    @staticmethod
    def create_empty_state() -> Dict[str, Any]:
        """
        Create an empty session state structure.
        
        Returns:
            Empty state dictionary with default structure
        """
        return {
            "last_updated": datetime.now().isoformat(),
            "players": {
                "video": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": True,
                    "loop": True,
                    "global_effects": [],
                    "transition_config": {
                        "enabled": False,
                        "effect": "fade",
                        "duration": 1.0,
                        "easing": "ease_in_out"
                    }
                },
                "artnet": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": True,
                    "loop": True,
                    "global_effects": [],
                    "transition_config": {
                        "enabled": False,
                        "effect": "fade",
                        "duration": 1.0,
                        "easing": "ease_in_out"
                    }
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
                "bpm": {
                    "enabled": True,
                    "bpm": 0.0,
                    "mode": "auto",
                    "manual_bpm": None
                }
            }
        }
