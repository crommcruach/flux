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
from datetime import datetime
from typing import Dict, Any, Optional
from .logger import get_logger

logger = get_logger(__name__)


class SessionStateManager:
    """Verwaltet persistenten Session-State für Player-Konfiguration."""
    
    def __init__(self, state_file_path: str):
        """
        Initialisiert SessionStateManager.
        
        Args:
            state_file_path: Pfad zur session_state.json Datei
        """
        self.state_file_path = state_file_path
        self._state = self._load_or_create()
        self._last_save_time = 0
        self._min_save_interval = 0.5  # Minimum 500ms zwischen Saves (Debouncing)
        logger.info(f"SessionStateManager initialisiert: {state_file_path}")
    
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
    
    def _create_empty_state(self) -> Dict[str, Any]:
        """Erstellt leere State-Struktur."""
        return {
            "last_updated": datetime.now().isoformat(),
            "players": {
                "video": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": False,
                    "loop": False,
                    "global_effects": []
                },
                "artnet": {
                    "playlist": [],
                    "current_index": -1,
                    "autoplay": False,
                    "loop": False,
                    "global_effects": []
                }
            }
        }
    
    def save(self, player_manager, clip_registry, force: bool = False) -> bool:
        """
        Speichert aktuellen Player-Status (mit Debouncing).
        
        Args:
            player_manager: PlayerManager-Instanz
            clip_registry: ClipRegistry-Instanz
            force: Ignoriere Debouncing (für kritische Saves)
            
        Returns:
            True bei Erfolg
        """
        # Debouncing: Skip wenn zu kurz nach letztem Save (außer force=True)
        import time
        current_time = time.time()
        if not force and (current_time - self._last_save_time) < self._min_save_interval:
            logger.debug(f"⏭️ Save übersprungen (Debouncing: {current_time - self._last_save_time:.2f}s < {self._min_save_interval}s)")
            return True  # Kein Fehler, nur übersprungen
        
        try:
            state = {
                "last_updated": datetime.now().isoformat(),
                "players": {}
            }
            
            # Für beide Player (video + artnet)
            for player_id in ['video', 'artnet']:
                player = player_manager.get_player(player_id)
                if not player:
                    logger.warning(f"Player '{player_id}' nicht gefunden beim Speichern")
                    continue
                
                # Baue Playlist mit vollständigen Clip-Informationen
                playlist = []
                for path in player.playlist:
                    clip_item = {"path": path}
                    clip_id = None  # Initialize clip_id
                    
                    # Hole UUID aus player.playlist_ids (wenn vorhanden)
                    playlist_ids = getattr(player, 'playlist_ids', {})
                    if path in playlist_ids:
                        clip_id = playlist_ids[path]
                        clip_item["id"] = clip_id
                    else:
                        # Fallback: Hole Clip-ID aus Registry
                        clip_id = clip_registry.find_clip_by_path(player_id, path)
                        if clip_id:
                            clip_item["id"] = clip_id
                    
                    # Typ erkennen
                    if path.startswith('generator:'):
                        clip_item["type"] = "generator"
                        clip_item["generator_id"] = path.replace('generator:', '')
                        
                        # Generator-Parameter aus player.playlist_params holen
                        gen_id = clip_item["generator_id"]
                        if gen_id in player.playlist_params:
                            clip_item["parameters"] = player.playlist_params[gen_id].copy()
                        else:
                            clip_item["parameters"] = {}
                    else:
                        clip_item["type"] = "video"
                    
                    # Effekte vom Clip (falls vorhanden)
                    if clip_id:
                        effects = clip_registry.get_clip_effects(clip_id)
                        # Filtere 'instance' aus effects (nicht JSON-serialisierbar)
                        serializable_effects = []
                        for effect in effects:
                            effect_copy = effect.copy()
                            if 'instance' in effect_copy:
                                del effect_copy['instance']
                            serializable_effects.append(effect_copy)
                        clip_item["effects"] = serializable_effects
                    else:
                        clip_item["effects"] = []
                    
                    playlist.append(clip_item)
                
                # Globale Player-Effekte
                global_effects = []
                # Video-Effect-Chain speichern (für Video Player)
                if hasattr(player, 'video_effect_chain') and player.video_effect_chain:
                    for effect_dict in player.video_effect_chain:
                        effect_data = {
                            "plugin_id": effect_dict['id'],
                            "parameters": effect_dict.get('config', {})
                        }
                        global_effects.append(effect_data)
                # Art-Net-Effect-Chain speichern (für Art-Net Player)
                elif hasattr(player, 'artnet_effect_chain') and player.artnet_effect_chain:
                    for effect_dict in player.artnet_effect_chain:
                        effect_data = {
                            "plugin_id": effect_dict['id'],
                            "parameters": effect_dict.get('config', {})
                        }
                        global_effects.append(effect_data)
                
                # Player-State speichern
                state["players"][player_id] = {
                    "playlist": playlist,
                    "current_index": player.playlist_index,
                    "autoplay": player.autoplay,
                    "loop": player.loop_playlist,
                    "global_effects": global_effects
                }
            
            # State in Datei schreiben
            os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
            with open(self.state_file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            
            self._state = state
            self._last_save_time = time.time()
            logger.debug(f"💾 Session State gespeichert: {len(state['players'])} Player")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern von session_state.json: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
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
