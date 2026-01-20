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
            state = self._build_state_dict(player_manager, clip_registry)
            self._state = state
            self._do_file_write(state)
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim synchronen Speichern: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _build_state_dict(self, player_manager, clip_registry) -> Dict[str, Any]:
        """Build the complete state dictionary for saving."""
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
                        
                        # Store parameter UIDs if they have sequences
                        if self.sequence_manager and 'parameters' in effect_copy:
                            for param_name, param_value in effect_copy['parameters'].items():
                                # Check if parameter has UID assigned (exists in any sequence)
                                param_uid = None
                                for seq in self.sequence_manager.get_all():
                                    # If sequence target looks like a UID (starts with param_)
                                    if seq.target_parameter.startswith('param_') and param_name in seq.target_parameter:
                                        param_uid = seq.target_parameter
                                        break
                                
                                # If parameter has UID, store it
                                if param_uid:
                                    if not isinstance(param_value, dict):
                                        effect_copy['parameters'][param_name] = {
                                            '_value': param_value,
                                            '_uid': param_uid
                                        }
                                    else:
                                        effect_copy['parameters'][param_name]['_uid'] = param_uid
                        
                        serializable_effects.append(effect_copy)
                    clip_item["effects"] = serializable_effects
                else:
                    clip_item["effects"] = []
                
                # Layers vom Clip (falls vorhanden)
                if clip_id:
                    layers = clip_registry.get_clip_layers(clip_id)
                    clip_item["layers"] = layers
                else:
                    clip_item["layers"] = []
                
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
            
            # Player-State speichern (Layer-Stack wird jetzt pro Clip gespeichert, nicht global)
            state["players"][player_id] = {
                "playlist": playlist,
                "current_index": player.playlist_index,
                "autoplay": player.autoplay,
                "loop": player.loop_playlist,
                "global_effects": global_effects
            }
        
        # Sequencer state speichern
        if player_manager.sequencer:
            try:
                sequencer_state = {
                    "mode_active": player_manager.sequencer_mode_active,
                    "audio_file": player_manager.sequencer.timeline.audio_file,
                    "timeline": player_manager.sequencer.timeline.to_dict(),
                    "last_position": player_manager.sequencer.get_position()
                }
                state["sequencer"] = sequencer_state
                logger.debug(f"🎵 Sequencer state saved: mode={sequencer_state['mode_active']}, audio={sequencer_state['audio_file']}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save sequencer state: {e}")
        
        # Audio analyzer state speichern (device, gain werden im Frontend gespeichert)
        if hasattr(player_manager, 'audio_analyzer') and player_manager.audio_analyzer:
            try:
                audio_analyzer = player_manager.audio_analyzer
                bpm_status = audio_analyzer.get_bpm_status()
                state["audio_analyzer"] = {
                    "device": audio_analyzer.device,
                    "running": audio_analyzer._running,
                    "config": audio_analyzer.config.copy() if audio_analyzer.config else {},
                    "bpm": {
                        "enabled": bpm_status.get('enabled', False),
                        "bpm": bpm_status.get('bpm', 0.0),
                        "mode": bpm_status.get('mode', 'auto'),
                        "manual_bpm": audio_analyzer._manual_bpm if hasattr(audio_analyzer, '_manual_bpm') else None
                    }
                }
                logger.debug(f"🎤 Audio analyzer state saved: device={audio_analyzer.device}, running={audio_analyzer._running}, bpm_enabled={bpm_status.get('enabled')}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to save audio analyzer state: {e}")
        
        # Master/Slave state speichern
        state["master_playlist"] = player_manager.get_master_playlist()
        if state["master_playlist"]:
            logger.debug(f"👑 Master playlist saved: {state['master_playlist']}")
        
        # Video player settings speichern (resolution, autosize)
        if 'video_player_settings' in self._state:
            state["video_player_settings"] = self._state['video_player_settings'].copy()
            logger.debug(f"🎬 Video player settings saved: {state['video_player_settings']}")
        
        # Save flat sequences by UID
        state["sequences"] = self._save_sequences()
        
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
            
            if not state or 'players' not in state:
                logger.info("Kein Session State zum Restaurieren vorhanden")
                return False
            
            # Für beide Player restaurieren
            for player_id in ['video', 'artnet']:
                player_state = state['players'].get(player_id)
                if not player_state:
                    continue
                
                player = player_manager.get_player(player_id)
                if not player:
                    logger.warning(f"Player '{player_id}' nicht gefunden beim Restaurieren")
                    continue
                
                # ========== PLAYLIST RESTAURIEREN ==========
                # Layers werden jetzt pro Clip gespeichert, nicht mehr global am Player
                
                # Restauriere Playlist (mit Clip-Layers)
                playlist = player_state.get('playlist', [])
                
                # Registriere alle Clips mit ihren Layers in der Registry
                for item in playlist:
                    clip_id = item.get('id')
                    item_type = item.get('type', 'video')
                    item_path = item.get('path', '')
                    clip_layers = item.get('layers', [])
                    
                    # Clip registrieren/updaten
                    if clip_id:
                        # Check if clip exists
                        existing_clip = clip_registry.get_clip(clip_id)
                        if existing_clip:
                            # Update layers
                            clip_registry.clips[clip_id]['layers'] = clip_layers
                        else:
                            # Create new clip entry
                            from datetime import datetime
                            if item_type == 'generator':
                                gen_id = item.get('generator_id')
                                clip_registry.clips[clip_id] = {
                                    'clip_id': clip_id,
                                    'player_id': player_id,
                                    'absolute_path': f"generator:{gen_id}",
                                    'relative_path': f"generator:{gen_id}",
                                    'filename': gen_id,
                                    'metadata': {
                                        'type': 'generator',
                                        'generator_id': gen_id,
                                        'parameters': item.get('parameters', {})
                                    },
                                    'created_at': datetime.now().isoformat(),
                                    'effects': item.get('effects', []),
                                    'layers': clip_layers
                                }
                            else:
                                clip_registry.clips[clip_id] = {
                                    'clip_id': clip_id,
                                    'player_id': player_id,
                                    'absolute_path': item_path,
                                    'relative_path': item_path,
                                    'filename': os.path.basename(item_path),
                                    'metadata': {},
                                    'created_at': datetime.now().isoformat(),
                                    'effects': item.get('effects', []),
                                    'layers': clip_layers
                                }
                
                # Legacy layer migration code removed - Layers are now clip-based
                
                if False:  # Disabled old layer restoration code
                    layers_data = []  # Placeholder
                    
                    # Erstelle Layers aus State
                    from .frame_source import VideoSource, GeneratorSource
                    
                    for layer_data in layers_data:
                        layer_type = layer_data.get('type', 'unknown')
                        source_path = layer_data.get('path', '')
                        blend_mode = layer_data.get('blend_mode', 'normal')
                        opacity = layer_data.get('opacity', 100.0)
                        clip_id = layer_data.get('clip_id')
                        
                        # Erstelle FrameSource basierend auf Typ
                        source = None
                        
                        if layer_type == 'generator':
                            generator_id = layer_data.get('generator_id')
                            parameters = layer_data.get('parameters', {})
                            
                            if generator_id:
                                source = GeneratorSource(
                                    generator_id=generator_id,
                                    parameters=parameters,
                                    canvas_width=player.canvas_width,
                                    canvas_height=player.canvas_height,
                                    config=config
                                )
                                if not source.initialize():
                                    logger.error(f"❌ Generator '{generator_id}' konnte nicht initialisiert werden")
                                    continue
                        
                        elif layer_type == 'video':
                            video_path = source_path
                            if not os.path.isabs(video_path):
                                video_dir = config.get('paths', {}).get('video_dir', 'video')
                                video_path = os.path.join(video_dir, video_path)
                            
                            if os.path.exists(video_path):
                                source = VideoSource(
                                    video_path=video_path,
                                    canvas_width=player.canvas_width,
                                    canvas_height=player.canvas_height,
                                    config=config
                                )
                                if not source.initialize():
                                    logger.error(f"❌ Video '{video_path}' konnte nicht initialisiert werden")
                                    continue
                            else:
                                logger.warning(f"⚠️ Video nicht gefunden: {video_path}")
                                continue
                        
                        else:
                            logger.warning(f"⚠️ Unbekannter Layer-Typ: {layer_type}")
                            continue
                        
                        # Füge Layer hinzu
                        if source:
                            layer_id = player.add_layer(
                                source=source,
                                clip_id=clip_id,
                                blend_mode=blend_mode,
                                opacity=opacity
                            )
                            logger.debug(f"✅ Layer {layer_id} restauriert: {source_path}")
                            
                            # Restauriere Layer-Effekte
                            layer = player.get_layer(layer_id)
                            if layer:
                                layer_effects = layer_data.get('effects', [])
                                # TODO: Effekte restaurieren (wenn Layer-Effekte implementiert sind)
                
                else:
                    # ========== MIGRATION: Altes Format ohne Layers ==========
                    # Konvertiere Playlist zu Layer-System
                    playlist = player_state.get('playlist', [])
                    current_index = player_state.get('current_index', -1)
                    
                    if playlist and current_index >= 0 and current_index < len(playlist):
                        logger.info(f"🔄 Migration: Konvertiere Playlist zu Layer für Player '{player_id}'")
                        
                        # Cleanup alte Layers
                        for layer in list(player.layers):
                            player.remove_layer(layer.layer_id)
                        
                        # Erstelle Layer 0 aus aktuellem Playlist-Item
                        current_item = playlist[current_index]
                        item_type = current_item.get('type', 'video')
                        item_path = current_item.get('path', '')
                        clip_id = current_item.get('id')
                        
                        from .frame_source import VideoSource, GeneratorSource
                        
                        source = None
                        
                        if item_type == 'generator':
                            generator_id = current_item.get('generator_id')
                            parameters = current_item.get('parameters', {})
                            
                            if generator_id:
                                source = GeneratorSource(
                                    generator_id=generator_id,
                                    parameters=parameters,
                                    canvas_width=player.canvas_width,
                                    canvas_height=player.canvas_height,
                                    config=config
                                )
                                if source.initialize():
                                    player.add_layer(
                                        source=source,
                                        clip_id=clip_id,
                                        blend_mode='normal',
                                        opacity=100.0
                                    )
                                    logger.info(f"✅ Migration: Generator '{generator_id}' als Layer 0 geladen")
                        
                        elif item_type == 'video':
                            video_path = item_path
                            if not os.path.isabs(video_path):
                                video_dir = config.get('paths', {}).get('video_dir', 'video')
                                video_path = os.path.join(video_dir, video_path)
                            
                            if os.path.exists(video_path):
                                source = VideoSource(
                                    video_path=video_path,
                                    canvas_width=player.canvas_width,
                                    canvas_height=player.canvas_height,
                                    config=config
                                )
                                if source.initialize():
                                    player.add_layer(
                                        source=source,
                                        clip_id=clip_id,
                                        blend_mode='normal',
                                        opacity=100.0
                                    )
                                    logger.info(f"✅ Migration: Video '{os.path.basename(video_path)}' als Layer 0 geladen")
                        
                # Restauriere Playlist unabhängig von Layers
                playlist = player_state.get('playlist', [])
                player.playlist = [item['path'] for item in playlist]
                player.playlist_index = player_state.get('current_index', -1)
                
                # Restauriere playlist_ids und playlist_params
                for item in playlist:
                    if item.get('id'):
                        player.playlist_ids[item['path']] = item['id']
                    if item.get('type') == 'generator' and item.get('generator_id'):
                        player.playlist_params[item['generator_id']] = item.get('parameters', {})
                    
                    # Note: Sequences are now restored from flat structure at end, not nested in parameters
                
                # Restauriere Player-Settings
                player.autoplay = player_state.get('autoplay', False)
                player.loop_playlist = player_state.get('loop', False)
                
                # Restauriere globale Effekte
                # TODO: Globale Effekte restaurieren (wenn implementiert)
                
                logger.info(f"✅ Player '{player_id}' restauriert: {len(player.layers)} Layer")
            
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
            
            # ========== SEQUENCER RESTAURIEREN ==========
            sequencer_data = state.get('sequencer')
            if sequencer_data and player_manager.sequencer:
                try:
                    # Restore audio file
                    audio_file = sequencer_data.get('audio_file')
                    if audio_file and os.path.exists(audio_file):
                        player_manager.sequencer.load_audio(audio_file)
                        
                        # Restore timeline (splits, clip_mapping)
                        timeline_data = sequencer_data.get('timeline', {})
                        if timeline_data:
                            player_manager.sequencer.timeline.from_dict(timeline_data)
                        
                        # Restore last position
                        last_position = sequencer_data.get('last_position', 0.0)
                        if last_position > 0:
                            player_manager.sequencer.seek(last_position)
                        
                        # Restore sequencer mode
                        mode_active = sequencer_data.get('mode_active', False)
                        if mode_active:
                            player_manager.set_sequencer_mode(True)
                        
                        logger.info(f"🎵 Sequencer restored: audio={os.path.basename(audio_file)}, splits={len(timeline_data.get('splits', []))}, mode={'ON' if mode_active else 'OFF'}")
                    else:
                        logger.debug("🎵 Sequencer audio file not found, skipping restore")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore sequencer: {e}")
                        # ========== AUDIO ANALYZER BPM STATE RESTAURIEREN ==========
            audio_analyzer_data = state.get('audio_analyzer')
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
                        # ========== MASTER/SLAVE STATE RESTAURIEREN ==========
            master_playlist = state.get('master_playlist')
            if master_playlist:
                try:
                    success = player_manager.set_master_playlist(master_playlist)
                    if success:
                        logger.info(f"👑 Master playlist restored: {master_playlist}")
                    else:
                        logger.warning(f"⚠️ Failed to set master playlist: {master_playlist}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to restore master/slave state: {e}")
            
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
