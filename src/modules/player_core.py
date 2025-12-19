"""
Unified Player - Universeller Media-Player mit austauschbaren Frame-Quellen
Unterstützt Videos, Scripts und zukünftige Quellen über FrameSource-Interface
"""
import time
import threading
import numpy as np
import cv2
import os
from collections import deque
from .logger import get_logger, debug_transport, debug_layers, debug_playback, debug_effects
from .artnet_manager import ArtNetManager
from .points_loader import PointsLoader
from .frame_source import VideoSource
from .plugin_manager import get_plugin_manager
from .layer import Layer
from .player.recording_manager import RecordingManager
from .player.transition_manager import TransitionManager
from .player.effect_processor import EffectProcessor
from .player.playlist_manager import PlaylistManager
from .player.layer_manager import LayerManager
from .constants import (
    DEFAULT_SPEED,
    UNLIMITED_LOOPS,
    DEFAULT_FPS
)

logger = get_logger(__name__)

# GLOBALE LOCK: Shared Lock für Player-Synchronisation
from . import player_lock


class Player:
    """
    Universeller Media-Player mit austauschbaren Frame-Quellen.
    Unterstützt Videos, Scripts und zukünftige Medien-Typen.
    """
    
    def __init__(self, frame_source, points_json_path, target_ip='127.0.0.1', start_universe=0, fps_limit=None, config=None, enable_artnet=True, player_name="Player", clip_registry=None):
        """
        Initialisiert Player mit Frame-Quelle.
        
        Args:
            frame_source: FrameSource-Instanz (VideoSource, GeneratorSource, etc.)
            points_json_path: Pfad zur Points-JSON-Datei
            target_ip: Art-Net Ziel-IP
            start_universe: Start-Universum für Art-Net
            fps_limit: FPS-Limit (None = Source-FPS)
            config: Konfigurations-Dict
            enable_artnet: Aktiviert Art-Net Ausgabe (False für Preview-Only Player)
            player_name: Name des Players für Logging
            clip_registry: ClipRegistry Instanz für UUID-basierte Clip-Verwaltung
        """
        self.player_name = player_name
        self.enable_artnet = enable_artnet
        self.clip_registry = clip_registry
        
        # Player ID für Clip Registry (normalisiert)
        if 'art-net' in player_name.lower() or 'artnet' in player_name.lower():
            self.player_id = 'artnet'
        else:
            self.player_id = 'video'
        
        # Legacy single source (backward compatibility wrapper)
        self._legacy_source = frame_source
        
        self.points_json_path = points_json_path
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.fps_limit = fps_limit
        self.config = config or {}
        
        # Plugin Manager (needed for LayerManager)
        self.plugin_manager = get_plugin_manager()
        
        # Lade Points-Konfiguration (needed for LayerManager initialization)
        # validate_bounds nur für Videos, nicht für Scripts
        validate_bounds = isinstance(frame_source, VideoSource)
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=validate_bounds)
        
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        # Layer Manager (Multi-Layer System)
        self.layer_manager = LayerManager(
            player_id=self.player_id,
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            config=self.config,
            plugin_manager=self.plugin_manager,
            clip_registry=clip_registry
        )
        # Give layer_manager access to player for WebSocket context
        self.layer_manager.player = self
        
        # Playback State
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        self.pause_event = threading.Event()  # Event-basierte Pause (low-latency)
        self.pause_event.set()  # Nicht pausiert = Event ist gesetzt
        self.thread = None
        self.artnet_manager = None
        
        # Erweiterte Steuerung
        self.brightness = 1.0  # 0.0 - 1.0
        self.speed_factor = DEFAULT_SPEED
        self.hue_shift = 0  # 0-360 Grad Hue Rotation
        self.max_loops = UNLIMITED_LOOPS  # 0 = unendlich
        self.current_loop = 0
        self.start_time = 0
        self.frames_processed = 0
        
        # Playlist Manager
        self.playlist_manager = PlaylistManager()
        self.playlist_manager.loop_playlist = True  # Initialize loop_playlist in manager
        self.current_clip_index = 0  # Track current position in playlist (for Master/Slave sync)
        self.player_manager = None  # Reference to PlayerManager (for Master/Slave sync)
        
        # Effect Processor
        self.effect_processor = EffectProcessor(
            plugin_manager=self.plugin_manager,
            clip_registry=clip_registry
        )
        self.current_clip_id = None  # UUID of currently loaded clip (for clip effects from registry)
        
        # Recording Manager
        self.recording_manager = RecordingManager(max_frames=36000)
        
        # Preview Frames
        self.last_frame = None  # Letztes Frame (LED-Punkte RGB) für Preview
        self.last_video_frame = None  # Letztes komplettes Frame für Preview
        
        # Transition Manager
        self.transition_manager = TransitionManager()
        
        # NICHT initialisieren im Konstruktor - wird lazy beim ersten play() gemacht
        # Grund: Verhindert dass mehrere Player dieselbe Video-Datei parallel öffnen (FFmpeg-Konflikt)
        self.source_initialized = False
        
        debug_playback(logger, f"{self.player_name} initialisiert:")
        debug_playback(logger, f"  Source: {self.source.get_source_name()} ({type(self.source).__name__})")
        debug_playback(logger, f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        debug_playback(logger, f"  Punkte: {self.total_points}, Kanäle: {self.total_channels}")
        debug_playback(logger, f"  Universen: {self.required_universes}")
        debug_playback(logger, f"  Art-Net: {'Enabled' if enable_artnet else 'Disabled'} ({target_ip}, Start-Universe: {start_universe})")
        
        # Art-Net Manager wird extern gesetzt
        self.artnet_manager = None
    
    # Properties that delegate to source
    @property
    def current_frame(self):
        """Aktueller Frame der Quelle."""
        return self.source.current_frame if self.source else 0
    
    @property
    def total_frames(self):
        """Gesamtzahl Frames der Quelle."""
        return self.source.total_frames if self.source else 0
    
    @property
    def video_path(self):
        """Video-Pfad (falls VideoSource)."""
        return getattr(self.source, 'video_path', None)
    
    @property
    def script_name(self):
        """Script-Name (deprecated - use generator_id instead)."""
        return getattr(self.source, 'script_name', None)
    
    # Properties that delegate to layer_manager
    @property
    def layers(self):
        """Layer list - delegates to layer_manager."""
        return self.layer_manager.layers
    
    @property
    def layer_counter(self):
        """Layer counter - delegates to layer_manager."""
        return self.layer_manager.layer_counter
    
    # Properties that delegate to playlist_manager
    @property
    def playlist(self):
        """Playlist - delegates to playlist_manager."""
        return self.playlist_manager.playlist
    
    @playlist.setter
    def playlist(self, value):
        """Playlist setter - delegates to playlist_manager."""
        self.playlist_manager.playlist = value
    
    @property
    def playlist_index(self):
        """Playlist index - delegates to playlist_manager."""
        return self.playlist_manager.playlist_index
    
    @playlist_index.setter
    def playlist_index(self, value):
        """Playlist index setter - delegates to playlist_manager."""
        self.playlist_manager.playlist_index = value
    
    @property
    def playlist_ids(self):
        """Playlist IDs - delegates to playlist_manager."""
        return self.playlist_manager.playlist_ids
    
    @playlist_ids.setter
    def playlist_ids(self, value):
        """Playlist IDs setter - delegates to playlist_manager."""
        self.playlist_manager.playlist_ids = value
    
    @property
    def autoplay(self):
        """Autoplay - delegates to playlist_manager."""
        return self.playlist_manager.autoplay
    
    @autoplay.setter
    def autoplay(self, value):
        """Autoplay setter - delegates to playlist_manager."""
        self.playlist_manager.autoplay = value
    
    @property
    def playlist_params(self):
        """Playlist params - delegates to playlist_manager."""
        return self.playlist_manager.playlist_params
    
    @playlist_params.setter
    def playlist_params(self, value):
        """Playlist params setter - delegates to playlist_manager."""
        self.playlist_manager.playlist_params = value
    
    @property
    def loop_playlist(self):
        """Loop playlist - delegates to playlist_manager."""
        return self.playlist_manager.loop_playlist
    
    @loop_playlist.setter
    def loop_playlist(self, value):
        """Loop playlist setter - delegates to playlist_manager."""
        self.playlist_manager.loop_playlist = value
    
    def _find_clip_by_id(self, clip_id):
        """
        Find a clip by ID in the clip registry (where effects are stored).
        
        Args:
            clip_id: Clip ID to search for
            
        Returns:
            dict: Clip data or None
        """
        # Effects are stored in clip_registry, not in playlist data
        from .clip_registry import get_clip_registry
        registry = get_clip_registry()
        return registry.get_clip(clip_id)
    
    def _extract_transition_from_effects(self, effects):
        """
        Extract transition effect configuration from clip effects.
        
        Args:
            effects: List of effect dicts from clip
            
        Returns:
            dict or None: Transition config or None if no transition effect found
        """
        if not effects or not isinstance(effects, list):
            return None
            
        for effect in effects:
            # Check both 'effect' and 'plugin_id' keys (registry uses plugin_id)
            if effect.get('effect') == 'transition' or effect.get('plugin_id') == 'transition':
                # Load the transition effect plugin
                try:
                    plugin = self.plugin_manager.load_plugin('transition')
                    if plugin:
                        parameters = effect.get('parameters', {})
                        config = plugin.get_transition_config(parameters)
                        return config
                except Exception as e:
                    logger.error(f"🎬 [{self.player_name}] Error extracting transition config: {e}")
                    return None
        return None
    
    def switch_source(self, new_source):
        """
        Wechselt zu einer neuen Frame-Quelle ohne Player zu zerstören.
        
        Args:
            new_source: Neue FrameSource-Instanz
        
        Returns:
            bool: True bei Erfolg
        """
        was_playing = self.is_playing
        was_paused = self.is_paused
        
        # Stoppe aktuelle Wiedergabe
        if was_playing:
            self.stop()
        
        # Warte bis Thread wirklich beendet ist (max 3 Sekunden)
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning(f"[{self.player_name}] Thread konnte nicht gestoppt werden beim Source-Wechsel!")
        
        # Cleanup alte Source (erst wenn Thread sicher beendet ist)
        if self.source:
            self.source.cleanup()
        
        # Setze neue Source
        self.source = new_source
        
        # Initialisiere neue Source
        if not self.source.initialize():
            logger.error(f"Neue Source konnte nicht initialisiert werden: {self.source.get_source_name()}")
            return False
        
        logger.info(f"Source gewechselt: {self.source.get_source_name()} ({type(self.source).__name__})")
        
        # Starte Wiedergabe wieder falls vorher aktiv
        if was_playing:
            # Verwende resume() statt start() um Thread nicht zu blockieren
            self.is_playing = True
            self.is_running = True
            self.source.reset()
            self.thread = threading.Thread(target=self._play_loop, daemon=True)
            self.thread.start()
            
            if was_paused:
                self.pause()
        
        return True
    
    # Master/Slave Sync Methods
    
    def get_current_clip_index(self) -> int:
        """
        Returns current clip index in playlist.
        
        Returns:
            Current clip index (0-based)
        """
        return self.current_clip_index
    
    def load_clip_by_index(self, index: int, notify_manager: bool = True) -> bool:
        """
        Loads clip at specific index in playlist.
        
        Args:
            index: Position in playlist (0-based)
            notify_manager: If True, notifies PlayerManager about clip change (default: True)
        
        Returns:
            True if successful, False otherwise
        """
        clip_item, clip_id = self.playlist_manager.get_item_at(index)
        if clip_item is None:
            logger.warning(f"[{self.player_name}] Invalid clip index: {index}")
            return False
        
        self.current_clip_index = index
        self.playlist_manager.set_index(index)
        
        logger.info(f"[{self.player_name}] Loading clip at index {index}, current state: playing={self.is_playing}, paused={self.is_paused}")
        
        # Save playback state
        was_playing = self.is_playing
        was_paused = self.is_paused
        
        debug_playback(logger, f"[{self.player_name}] Saved state: was_playing={was_playing}, was_paused={was_paused}")
        
        # Stop playback if running
        if was_playing:
            debug_playback(logger, f"[{self.player_name}] Stopping player before clip switch...")
            self.stop()
        
        # Wait for thread to finish (max 3 seconds)
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning(f"[{self.player_name}] Thread could not be stopped when switching clips!")
        
        # --- Check for custom transition effect BEFORE loading clip ---
        clip_data = self._find_clip_by_id(clip_id)
        if clip_data:
            effects = clip_data.get('effects', [])
            transition_config = self._extract_transition_from_effects(effects)
            
            if transition_config:
                plugin_name = transition_config.get('plugin')
                logger.info(f"🎬 [{self.player_name}] Custom transition found: plugin={plugin_name}, duration={transition_config.get('duration')}s, easing={transition_config.get('easing')}")
                
                # Load the actual transition plugin instance using load_plugin()
                transition_plugin_instance = self.plugin_manager.load_plugin(plugin_name)
                if transition_plugin_instance:
                    # Apply custom transition config to TransitionManager
                    if self.transition_manager:
                        # Extract actual values (handle triple-slider metadata)
                        duration = transition_config.get('duration', 1.0)
                        if isinstance(duration, dict) and '_value' in duration:
                            duration = duration['_value']
                        
                        easing = transition_config.get('easing', 'ease_in_out')
                        if isinstance(easing, dict) and '_value' in easing:
                            easing = easing['_value']
                        
                        self.transition_manager.configure(
                            plugin=transition_plugin_instance,
                            effect=plugin_name,
                            duration=duration,
                            easing=easing
                        )
                        logger.info(f"🎬 [{self.player_name}] Applied transition plugin instance: {transition_plugin_instance}")
                else:
                    logger.error(f"🎬 [{self.player_name}] Transition plugin not found: {plugin_name}")
            else:
                logger.info(f"🎬 [{self.player_name}] No custom transition, restoring playlist defaults")
                # Reset to playlist defaults by reloading the default transition plugin
                if self.transition_manager:
                    # Get current playlist transition config (defaults)
                    current_effect = self.transition_manager.config.get('effect', 'fade')
                    current_duration = self.transition_manager.config.get('duration', 1.0)
                    current_easing = self.transition_manager.config.get('easing', 'ease_in_out')
                    
                    # Check if we need to restore (only if different from current)
                    # Store original defaults on first custom transition
                    if not hasattr(self.transition_manager, '_original_effect'):
                        # Save the current config as original defaults
                        self.transition_manager._original_effect = current_effect
                        self.transition_manager._original_duration = current_duration
                        self.transition_manager._original_easing = current_easing
                        self.transition_manager._original_plugin = self.transition_manager.config.get('plugin')
                        logger.debug(f"🎬 [{self.player_name}] Saved original defaults: {current_effect}")
                    
                    # Restore original defaults
                    original_effect = getattr(self.transition_manager, '_original_effect', 'fade')
                    original_plugin = getattr(self.transition_manager, '_original_plugin', None)
                    
                    if current_effect != original_effect or original_plugin:
                        logger.info(f"🎬 [{self.player_name}] Restoring playlist default transition: {original_effect}")
                        # Reload the original plugin
                        if original_plugin is None:
                            original_plugin = self.plugin_manager.load_plugin(original_effect)
                        
                        self.transition_manager.configure(
                            plugin=original_plugin,
                            effect=original_effect,
                            duration=getattr(self.transition_manager, '_original_duration', 1.0),
                            easing=getattr(self.transition_manager, '_original_easing', 'ease_in_out')
                        )
        else:
            logger.debug(f"🎬 [{self.player_name}] Clip data not found for ID {clip_id}, using default transitions")
        
        try:
            from .frame_source import VideoSource, GeneratorSource
            
            # Check if it's a generator (string format: 'generator:generator_id')
            if clip_item.startswith('generator:'):
                generator_id = clip_item.replace('generator:', '')
                
                # Get parameters with priority fallback
                parameters = self.playlist_manager.get_generator_parameters(
                    generator_id,
                    plugin_manager=self.plugin_manager,
                    clip_registry=self.clip_registry,
                    current_source=self.source
                )
                
                # Auto-set playback_mode based on autoplay and slave status
                # If autoplay is enabled and not in slave mode, use play_once to advance through playlist
                is_slave = getattr(self, '_is_slave_cached', False)
                
                if self.autoplay and not is_slave and 'playback_mode' not in parameters:
                    parameters['playback_mode'] = 'play_once'
                    debug_playback(logger, f"🔄 [{self.player_name}] Auto-set playback_mode=play_once (autoplay=True, slave={is_slave})")
                elif is_slave and 'playback_mode' not in parameters:
                    parameters['playback_mode'] = 'repeat'
                    debug_playback(logger, f"🔁 [{self.player_name}] Auto-set playback_mode=repeat (slave mode)")
                
                new_source = GeneratorSource(generator_id, parameters, self.canvas_width, self.canvas_height, self.config)
            else:
                # Video file - clip_id already retrieved from playlist_manager
                new_source = VideoSource(clip_item, self.canvas_width, self.canvas_height, self.config, clip_id=clip_id)
            
            # Initialize new source
            if not new_source.initialize():
                logger.error(f"❌ [{self.player_name}] Failed to initialize clip: {clip_item}")
                return False
            
            # Cleanup old source and replace (after thread stopped)
            if self.layers:
                # Multi-Layer: Replace Layer 0 source
                if self.layers[0].source:
                    self.layers[0].source.cleanup()
                self.layers[0].source = new_source
            else:
                # Single-Source: Legacy behavior
                if self.source:
                    self.source.cleanup()
                self.source = new_source
            
            self.current_loop = 0
            
            # Reset transport effect completely if present (ensure clean start for new clip)
            if self.layers:
                for layer in self.layers:
                    for effect in layer.effects:
                        if effect.get('id') == 'transport' and effect.get('instance'):
                            transport = effect['instance']
                            # Force full reset for new clip
                            transport._current_loop_iteration = 0
                            transport.current_position = 0
                            transport._virtual_frame = 0.0
                            transport.loop_completed = False
                            transport._has_played_once = False
                            transport._frame_source = None  # Force re-initialization
                            logger.debug(f"🔁 [{self.player_name}] Reset transport effect state on clip load")
            
            logger.info(f"✅ [{self.player_name}] Loaded clip at index {index}")
            
            # Restart playback if it was playing before
            if was_playing:
                logger.info(f"[{self.player_name}] Restarting playback (was_playing={was_playing})...")
                
                # Registriere als aktiver Player NUR wenn Art-Net enabled ist
                if self.enable_artnet:
                    with player_lock._global_player_lock:
                        player_lock._active_player = self
                        from .logger import debug_log, DebugCategories
                        debug_log(logger, DebugCategories.ARTNET, f"[{self.player_name}] Registered as active Art-Net player")
                
                # Reaktiviere ArtNet (wurde bei stop() deaktiviert)
                if self.artnet_manager:
                    self.artnet_manager.is_active = True
                    self.artnet_manager.resume_video_mode()
                
                self.is_playing = True
                self.is_running = True
                new_source.reset()
                self.thread = threading.Thread(target=self._play_loop, daemon=True)
                self.thread.start()
                logger.info(f"[{self.player_name}] Playback restarted, thread alive={self.thread.is_alive()}")
                
                if was_paused:
                    self.pause()
            
            # Notify PlayerManager about clip change (for Master/Slave sync)
            if notify_manager and self.player_manager:
                self.player_manager.on_clip_changed(self.player_id, index)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [{self.player_name}] Error loading clip at index {index}: {e}")
            return False
    
    def play(self):
        """Intelligente Play-Funktion: startet oder setzt fort je nach Status."""
        if self.is_playing and not self.is_paused:
            debug_playback(logger, f"{self.player_name}: Wiedergabe läuft bereits!")
            return
        
        if self.is_paused:
            # Pausiert → nur fortsetzen
            self.resume()
        else:
            # Gestoppt → neu starten
            self.start()
    
    def start(self):
        """Startet die Wiedergabe (interner Start mit Thread-Erstellung)."""
        if self.is_playing:
            debug_playback(logger, f"{self.player_name}: Wiedergabe läuft bereits!")
            return
        
        # Registriere als aktiver Player NUR wenn Art-Net enabled ist
        # Dies erlaubt mehrere Preview-Only Player gleichzeitig
        if self.enable_artnet:
            with player_lock._global_player_lock:
                # Stoppe alten Art-Net Player falls vorhanden
                if player_lock._active_player and player_lock._active_player is not self:
                    old_player = player_lock._active_player
                    logger.info(f"Stoppe alten Art-Net Player: {old_player.player_name}")
                    old_player.stop()
                
                player_lock._active_player = self
                logger.info(f"Aktiver Art-Net Player: {self.player_name} ({self.source.get_source_name()})")
        else:
            logger.info(f"{self.player_name}: Starte Preview-Only (kein Art-Net)")
        
        # Prüfe ob Source vorhanden ist
        if not self.source:
            logger.warning(f"{self.player_name}: Keine Source geladen - kann nicht starten")
            return
        
        # Re-initialisiere Source falls nötig (nach stop)
        if not self.source.initialize():
            logger.error(f"Fehler beim Re-Initialisieren der Source: {self.source.get_source_name()}")
            return
        
        # Reaktiviere ArtNet (wurde bei stop() deaktiviert)
        if self.artnet_manager:
            self.artnet_manager.is_active = True
            self.artnet_manager.resume_video_mode()
        
        self.is_playing = True
        self.is_running = True
        self.source.reset()
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()
        logger.info(f"Wiedergabe gestartet: {self.source.get_source_name()}")
    
    def stop(self):
        """Stoppt die Wiedergabe."""
        if not self.is_playing:
            debug_playback(logger, "Wiedergabe läuft nicht!")
            return
        
        debug_playback(logger, "Stoppe Wiedergabe...")
        
        # Flags SOFORT setzen
        self.is_running = False
        self.is_playing = False
        self.is_paused = False
        
        # ArtNet deaktivieren
        if self.artnet_manager:
            self.artnet_manager.is_active = False
        
        # Warte auf Thread-Ende
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
            if self.thread.is_alive():
                logger.warning("Thread konnte nicht gestoppt werden!")
        
        self.thread = None
        
        # HINWEIS: Source und ArtNet Manager NICHT cleanup/zerstören
        # Sie werden beim nächsten start() wiederverwendet
        # Nur bei switch_source() oder Shutdown cleanup nötig
        
        # Deregistriere Player (nur wenn Art-Net enabled)
        if self.enable_artnet:
            with player_lock._global_player_lock:
                if player_lock._active_player is self:
                    player_lock._active_player = None
        
        logger.info(f"{self.player_name}: Wiedergabe gestoppt")
    
    def pause(self):
        """Pausiert die Wiedergabe."""
        if not self.is_playing or self.is_paused:
            debug_playback(logger, "Wiedergabe läuft nicht oder ist bereits pausiert!")
            return
        
        self.is_paused = True
        self.pause_event.clear()  # Event cleared = pausiert
        debug_playback(logger, "Wiedergabe pausiert")
    
    def resume(self):
        """Setzt Wiedergabe fort."""
        if not self.is_playing or not self.is_paused:
            debug_playback(logger, "Wiedergabe läuft nicht oder ist nicht pausiert!")
            return
        
        self.is_paused = False
        self.pause_event.set()  # Event set = fortsetzen (immediate response)
        debug_playback(logger, "Wiedergabe fortgesetzt")
        
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
    
    def restart(self):
        """Startet Wiedergabe neu vom ersten Frame (egal in welchem Status)."""
        # Stoppe falls läuft oder pausiert
        if self.is_playing or self.is_paused:
            self.stop()
            time.sleep(0.3)
        
        # Reset auf ersten Frame (direkt in Source)
        self.source.reset()
        self.source.current_frame = 0
        self.current_loop = 0
        self.is_paused = False  # Stelle sicher dass Pause-Flag aus ist
        
        # Starte immer neu (egal ob vorher pause oder stop)
        self.start()
        
        debug_playback(logger, "Wiedergabe neu gestartet (vom ersten Frame)")
    
    def _check_transport_loop_completion(self):
        """
        Prüft ob der Transport-Effekt einen Loop abgeschlossen hat.
        Returns True wenn Loop completed, False sonst.
        """
        if not self.clip_registry or not hasattr(self, 'current_clip_id') or not self.current_clip_id:
            return False
        
        try:
            # Use LAYER transport instance (live instance), not cached registry effects
            if not self.layers or len(self.layers) == 0:
                return False
            
            # Check Layer 0 effects for transport
            for effect in self.layers[0].effects:
                if effect.get('id') == 'transport' and effect.get('instance'):
                    transport_instance = effect['instance']
                    
                    # Check loop_completed flag
                    if hasattr(transport_instance, 'loop_completed') and transport_instance.loop_completed:
                        # Reset flag for next loop detection
                        transport_instance.loop_completed = False
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking transport loop completion: {e}")
            return False
    
    def _play_loop(self):
        """Haupt-Wiedergabeschleife (läuft in separatem Thread)."""
        self.is_running = True
        self.is_paused = False
        self.start_time = time.time()
        self.frames_processed = 0
        self.current_loop = 0
        
        # Deaktiviere Testmuster
        if self.artnet_manager:
            self.artnet_manager.resume_video_mode()
        
        # FPS für Timing
        # Multi-Layer: Master-Layer (0) bestimmt FPS
        if self.layers:
            fps = self.fps_limit if self.fps_limit else self.layers[0].source.fps
            debug_layers(logger, f"🎬 Multi-Layer Mode: Master FPS={fps} (Layer 0)")
        else:
            fps = self.fps_limit if self.fps_limit else self.source.fps
            debug_playback(logger, f"🎬 Single-Source Mode: FPS={fps}")
        
        frame_time = 1.0 / fps if fps > 0 else 0
        next_frame_time = time.time()
        
        frame_wait_delay = self.config.get('video', {}).get('frame_wait_delay', 0.1)
        
        source_name = self.layers[0].source.get_source_name() if self.layers else self.source.get_source_name()
        debug_playback(logger, f"Play-Loop gestartet: FPS={fps}, Source={source_name}")
        
        while self.is_running and self.is_playing:
            # Pause-Handling (Event-basiert für low-latency)
            if self.is_paused:
                # Warte auf resume (pause_event.set()) - keine CPU-Last, immediate wake
                self.pause_event.wait(timeout=frame_wait_delay)
                next_frame_time = time.time()  # Reset timing
                continue
            
            loop_start = time.time()
            
            # DEBUG: Log every 100 frames to monitor playback
            if self.current_frame % 100 == 0 and self.current_frame > 0:
                debug_playback(logger, f"[{self.player_name}] Playing: frame {self.current_frame}, max_loops={self.max_loops}, current_loop={self.current_loop}")
            
            # ========== TRANSPORT LOOP DETECTION ==========
            # Use cached slave state (updated only when user changes sequencer/master mode)
            is_slave = getattr(self, '_is_slave_cached', False)
            
            # Only check transport loop if NOT a slave
            # Slaves loop continuously until master/sequencer advances them
            transport_loop_completed = False
            should_autoadvance = False
            
            if not is_slave:
                # Check if transport effect signaled loop completion (für Playlist-Autoplay)
                transport_loop_completed = self._check_transport_loop_completion()
                
                if transport_loop_completed:
                    self.current_loop += 1
                    logger.info(f"🔁 [{self.player_name}] Transport loop completed: current_loop={self.current_loop}, max_loops={self.max_loops}")
                    
                    # Check if we should advance to next clip in playlist
                    if self.max_loops > 0 and self.current_loop >= self.max_loops:
                        logger.info(f"📋 [{self.player_name}] max_loops reached ({self.current_loop}/{self.max_loops})")
                        
                        # Prüfe Playlist-Autoplay
                        if self.autoplay and len(self.playlist) > 0:
                            # Skip frame reading and trigger autoplay
                            should_autoadvance = True
                            frame = None
                            source_delay = 0
                            debug_playback(logger, f"⏭️ [{self.player_name}] Triggering autoplay - skip frame reading")
            # Slave mode: ignore transport loop, just keep playing (no per-frame logging)
            
            # ========== MULTI-LAYER COMPOSITING ==========
            if not should_autoadvance and self.layers and len(self.layers) > 0:
                # OPTIMIZATION: Single-layer fast path (skip all compositing logic)
                if len(self.layers) == 1:
                    # Only one layer - no blending needed, process directly (saves 5-8ms)
                    layer = self.layers[0]
                    
                    # PRE-PROCESS: Transport effect if present
                    if layer.effects and layer.source:
                        for effect in layer.effects:
                            if effect.get('id') == 'transport' and effect.get('enabled', True):
                                transport_instance = effect.get('instance')
                                if transport_instance:
                                    if hasattr(transport_instance, '_initialize_state'):
                                        if transport_instance.out_point == 0:
                                            transport_instance._initialize_state(layer.source)
                                    if hasattr(transport_instance, '_calculate_next_frame'):
                                        next_frame = transport_instance._calculate_next_frame()
                                        if hasattr(layer.source, 'current_frame'):
                                            layer.source.current_frame = next_frame
                                break
                    
                    # Fetch and process single layer
                    frame, source_delay = layer.source.get_next_frame()
                    if frame is not None:
                        frame = self.apply_layer_effects(layer, frame)
                    # Continue to effect processing below (skip multi-layer compositing)
                    
                else:
                    # Multiple layers - full compositing pipeline
                    # PRE-PROCESS: Let transport effect calculate next frame BEFORE fetching
                    # This prevents fetching frames outside trim range
                    transport_preprocessed = False
                    if self.layers[0].effects and self.layers[0].source:
                        # Use LAYER transport instance, not registry instance!
                        # This ensures the live instance gets updated current_position
                        for effect in self.layers[0].effects:
                            if effect.get('id') == 'transport' and effect.get('enabled', True):
                                transport_instance = effect.get('instance')
                                
                                if transport_instance:
                                    # Initialize transport state if needed (only once)
                                    if hasattr(transport_instance, '_initialize_state'):
                                        if transport_instance.out_point == 0:
                                            transport_instance._initialize_state(self.layers[0].source)
                                            debug_transport(logger, f"🎬 Transport initialized: out_point={transport_instance.out_point}")
                                    
                                    # Calculate and set next frame BEFORE fetch
                                    if hasattr(transport_instance, '_calculate_next_frame'):
                                        next_frame = transport_instance._calculate_next_frame()
                                        # Set current_frame on source (works for VideoSource, GeneratorSource, ScriptSource)
                                        if hasattr(self.layers[0].source, 'current_frame'):
                                            self.layers[0].source.current_frame = next_frame
                                            transport_preprocessed = True
                                            debug_transport(logger, f"🎯 Transport pre-set frame to {next_frame}, live instance current_position={transport_instance.current_position}")
                                break
                    
                    # Master Frame (Layer 0 bestimmt Timing und Länge)
                    frame, source_delay = self.layers[0].source.get_next_frame()
                    
                    if frame is not None:
                        # Wende Layer 0 Effects an (Transport controls playback here)
                        frame = self.apply_layer_effects(self.layers[0], frame)
                        
                        # Composite Slave Layers (1-N)
                        for layer in self.layers[1:]:
                            # Skip invisible layers (saves get_next_frame + effects + blending)
                            if not layer.enabled or layer.opacity <= 0:
                                continue
                            
                            overlay_frame, _ = layer.source.get_next_frame()
                            
                            # Auto-Reset wenn Slave-Layer am Ende (Looping!)
                            if overlay_frame is None:
                                debug_layers(logger, f"🔁 Layer {layer.layer_id} reached end, auto-reset (slave loop)")
                                layer.source.reset()
                                overlay_frame, _ = layer.source.get_next_frame()
                            
                            # Wenn immer noch None (z.B. fehlerhafte Source) - überspringe Layer
                            if overlay_frame is None:
                                source_info = getattr(layer.source, 'video_path', getattr(layer.source, 'generator_name', 'Unknown'))
                                logger.warning(f"⚠️ Layer {layer.layer_id} (source: {source_info}) returned None after reset, skipping")
                                continue
                            
                            # Wende Layer Effects an
                            overlay_frame = self.apply_layer_effects(layer, overlay_frame)
                            
                            # Composite mit BlendEffect
                            blend_plugin = self.get_blend_plugin(layer.blend_mode, layer.opacity)
                            frame = blend_plugin.process_frame(frame, overlay=overlay_frame)
                    
                    # Frame ist jetzt das finale composited Frame
                    # Weiter mit existing logic (brightness, effects, etc.)
                
            elif not should_autoadvance:
                # Fallback: Single-Source Mode (Backward Compatibility)
                frame, source_delay = self.source.get_next_frame()
            
            # ========== REST IST UNVERÄNDERT ==========
            
            if frame is None:
                # Ende der Source (Video-Loop oder Fehler)
                # ACHTUNG: current_loop wurde bereits im Transport-Loop-Check erhöht!
                # Nur erhöhen wenn kein Transport-Loop (z.B. bei echtem Frame=None von Source)
                if not transport_loop_completed:
                    self.current_loop += 1
                
                logger.debug(f"🎬 [{self.player_name}] Frame=None (clip ended): current_loop={self.current_loop}, max_loops={self.max_loops}")
                
                # Use cached slave state (updated only when user changes sequencer/master mode)
                is_slave = getattr(self, '_is_slave_cached', False)
                
                # If slave: loop current clip, don't advance
                if is_slave:
                    # Reset source to beginning for loop
                    current_source = self.layers[0].source if self.layers else self.source
                    if current_source:
                        current_source.reset()
                        current_source.current_frame = 0
                    self.current_loop = 0
                    
                    # Reset transport effect loop counter if present
                    if self.layers:
                        for layer in self.layers:
                            for effect in layer.effects:
                                if hasattr(effect, '_current_loop_iteration'):
                                    effect._current_loop_iteration = 0
                    
                    # CRITICAL: Immediately fetch first frame for seamless looping
                    # Don't rely on fall-through logic - fetch directly here
                    if current_source:
                        frame, source_delay = current_source.get_next_frame()
                        if frame is None:
                            logger.warning(f"⚠️ [{self.player_name}] Slave loop: Failed to fetch first frame after reset")
                            break
                        logger.debug(f"🔁 [{self.player_name}] Slave seamless loop: fetched frame 0")
                    else:
                        logger.error(f"❌ [{self.player_name}] Slave loop: No source available")
                        break
                
                # Check playlist autoplay (only if NOT a slave!)
                if self.playlist_manager.should_autoplay(is_slave):
                    # Get next item from playlist manager
                    next_item_path, next_clip_id = self.playlist_manager.advance(self.player_name)
                    
                    if next_item_path is None:
                        # End of playlist reached
                        break
                    
                    try:
                        from .frame_source import VideoSource, GeneratorSource
                        
                        # Check if it's a generator
                        if next_item_path.startswith('generator:'):
                            generator_id = next_item_path.replace('generator:', '')
                            
                            # Get parameters using playlist_manager priority logic
                            current_source = self.layers[0].source if self.layers else self.source
                            parameters = self.playlist_manager.get_generator_parameters(
                                generator_id,
                                plugin_manager=self.plugin_manager,
                                clip_registry=self.clip_registry,
                                current_source=current_source
                            )
                            
                            # Auto-set playback_mode based on autoplay and slave status
                            # Use cached slave state
                            is_slave = getattr(self, '_is_slave_cached', False)
                            
                            if self.playlist_manager.autoplay and not is_slave and 'playback_mode' not in parameters:
                                parameters['playback_mode'] = 'play_once'
                                debug_playback(logger, f"🔄 [{self.player_name}] Auto-set playback_mode=play_once")
                            elif is_slave and 'playback_mode' not in parameters:
                                parameters['playback_mode'] = 'repeat'
                                debug_playback(logger, f"🔁 [{self.player_name}] Auto-set playback_mode=repeat (slave mode)")
                            
                            new_source = GeneratorSource(generator_id, parameters, self.canvas_width, self.canvas_height, self.config)
                            debug_playback(logger, f"🌟 [{self.player_name}] Loading generator: {generator_id}")
                        else:
                            # Video file - clip_id already from playlist_manager
                            new_source = VideoSource(next_item_path, self.canvas_width, self.canvas_height, self.config, clip_id=next_clip_id)
                            debug_playback(logger, f"🎬 [{self.player_name}] Loading video: {next_item_path} (clip_id={next_clip_id})")
                        
                        # Initialisiere neue Source
                        if not new_source.initialize():
                            logger.error(f"❌ [{self.player_name}] Fehler beim Initialisieren des nächsten Items: {next_item_path}")
                            break
                        
                        # Start transition if enabled
                        self.transition_manager.start(self.player_name)
                        
                        # Cleanup alte Source
                        if self.layers:
                            # Multi-Layer: Ersetze Layer 0 Source
                            if self.layers[0].source:
                                self.layers[0].source.cleanup()
                            self.layers[0].source = new_source
                            debug_layers(logger, f"🔧 [{self.player_name}] Layer 0 source replaced with new source")
                        else:
                            # Single-Source: Legacy behavior
                            if self.source:
                                self.source.cleanup()
                            self.source = new_source
                        
                        # Update indices (playlist_manager already advanced)
                        self.current_clip_index = self.playlist_manager.playlist_index
                        self.current_loop = 0
                        
                        # Notify PlayerManager about clip change (for Master/Slave sync)
                        if self.player_manager:
                            self.player_manager.on_clip_changed(self.player_id, self.playlist_manager.playlist_index)
                        
                        # Update clip_id - next_clip_id already from playlist_manager or needs registration
                        if not next_clip_id:
                            # No UUID yet - register new clip
                            if next_item_path.startswith('generator:'):
                                next_clip_id = self.clip_registry.register_clip(
                                    player_id=self.player_id,
                                    absolute_path=next_item_path,
                                    relative_path=next_item_path,
                                    metadata={'type': 'generator', 'generator_id': generator_id, 'parameters': parameters}
                                )
                            else:
                                relative_path = os.path.relpath(next_item_path, self.config.get('paths', {}).get('video_dir', 'video'))
                                next_clip_id = self.clip_registry.register_clip(
                                    player_id=self.player_id,
                                    absolute_path=next_item_path,
                                    relative_path=relative_path,
                                    metadata={}
                                )
                        
                        # Only reload layers if switching to a different clip
                        if self.current_clip_id != next_clip_id:
                            self.current_clip_id = next_clip_id
                            
                            # 🎬 Check for custom transition effect on new clip
                            clip_data = self._find_clip_by_id(next_clip_id)
                            if clip_data:
                                effects = clip_data.get('effects', [])
                                transition_config = self._extract_transition_from_effects(effects)
                                
                                if transition_config:
                                    plugin_name = transition_config.get('plugin')
                                    logger.info(f"🎬 [{self.player_name}] Autoplay: Custom transition on clip: {plugin_name}")
                                    
                                    # Load and apply transition plugin
                                    transition_plugin_instance = self.plugin_manager.load_plugin(plugin_name)
                                    if transition_plugin_instance and self.transition_manager:
                                        # Save defaults if not already saved
                                        if not hasattr(self.transition_manager, '_original_effect'):
                                            self.transition_manager._original_effect = self.transition_manager.config.get('effect', 'fade')
                                            self.transition_manager._original_plugin = self.transition_manager.config.get('plugin')
                                            self.transition_manager._original_duration = self.transition_manager.config.get('duration', 1.0)
                                            self.transition_manager._original_easing = self.transition_manager.config.get('easing', 'ease_in_out')
                                        
                                        # Extract actual values (handle triple-slider metadata)
                                        duration = transition_config.get('duration', 1.0)
                                        if isinstance(duration, dict) and '_value' in duration:
                                            duration = duration['_value']
                                        
                                        easing = transition_config.get('easing', 'ease_in_out')
                                        if isinstance(easing, dict) and '_value' in easing:
                                            easing = easing['_value']
                                        
                                        self.transition_manager.configure(
                                            plugin=transition_plugin_instance,
                                            effect=plugin_name,
                                            duration=duration,
                                            easing=easing
                                        )
                                else:
                                    # No custom transition - restore defaults
                                    if self.transition_manager and hasattr(self.transition_manager, '_original_effect'):
                                        logger.info(f"🎬 [{self.player_name}] Autoplay: Restoring default transition")
                                        original_plugin = self.transition_manager._original_plugin
                                        if original_plugin is None:
                                            original_plugin = self.plugin_manager.load_plugin(self.transition_manager._original_effect)
                                        
                                        self.transition_manager.configure(
                                            plugin=original_plugin,
                                            effect=self.transition_manager._original_effect,
                                            duration=self.transition_manager._original_duration,
                                            easing=self.transition_manager._original_easing
                                        )
                            
                            # Load layers for new clip
                            video_dir = self.config.get('paths', {}).get('video_dir', 'video')
                            if not self.load_clip_layers(next_clip_id, self.clip_registry, video_dir):
                                logger.warning(f"⚠️ [{self.player_name}] Could not load layers for clip {next_clip_id}, using single-source fallback")
                            debug_layers(logger, f"🔄 [{self.player_name}] Layers reloaded for new clip {next_clip_id}")
                        else:
                            # Same clip - just reset the source, keep existing layer objects
                            self.current_clip_id = next_clip_id
                            debug_layers(logger, f"🔁 [{self.player_name}] Same clip {next_clip_id}, reusing existing layers")
                        
                        item_name = generator_id if next_item_path.startswith('generator:') else os.path.basename(next_item_path)
                        logger.info(f"✅ [{self.player_name}] Nächstes Item geladen: {item_name} (clip_id={next_clip_id})")
                        continue
                    except Exception as e:
                        logger.error(f"❌ [{self.player_name}] Fehler beim Laden des nächsten Items: {e}")
                        break
                
                # Kein Autoplay - normales Loop-Verhalten
                # Loop-Limit prüfen (nur für nicht-infinite Sources)
                current_source = self.layers[0].source if self.layers else self.source
                if not current_source.is_infinite and self.max_loops > 0 and self.current_loop >= self.max_loops:
                    debug_playback(logger, f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                    break
                
                # Reset Source für nächsten Loop
                if self.layers:
                    # Multi-Layer: Reset nur Master (Layer 0), Slaves loopen selbst
                    self.layers[0].source.reset()
                    debug_layers(logger, f"🔁 [{self.player_name}] Master Layer 0 reset for next loop")
                else:
                    # Single-Source: Legacy behavior
                    self.source.reset()
                continue
            
            # Apply transition if active
            frame = self.transition_manager.apply(frame, self.player_name)
            
            # Store frame for next transition
            self.transition_manager.store_frame(frame)
            
            # Helligkeit in-place anwenden (Performance-Optimierung: keine Kopie!)
            if self.brightness != 1.0:
                # NumPy in-place multiplication (arbeitet direkt auf frame)
                np.multiply(frame, self.brightness, out=frame, casting='unsafe')
                np.clip(frame, 0, 255, out=frame)
                frame = frame.astype(np.uint8)
            
            # Hue Shift in-place anwenden wenn aktiviert (OPTIMIZATION: Lazy conversion)
            if self.hue_shift != 0:
                frame_hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                frame_hsv[:, :, 0] = (frame_hsv[:, :, 0].astype(np.int16) + self.hue_shift // 2) % 180
                cv2.cvtColor(frame_hsv, cv2.COLOR_HSV2RGB, dst=frame)
            # Note: When hue_shift == 0, skip entire HSV conversion (saves 2-3ms)
            
            # Wende Effect Chains an - nur kopieren wenn beide Chains unterschiedlich sind
            if self.effect_processor.video_effect_chain and self.effect_processor.artnet_effect_chain:
                # Beide Chains aktiv: Kopie nötig für separate Processing
                frame_for_video_preview = self.effect_processor.apply_effects(
                    frame.copy(), 
                    chain_type='video',
                    current_clip_id=self.current_clip_id,
                    source=self.source,
                    player=self,
                    player_name=self.player_name
                )
                frame_for_artnet = self.effect_processor.apply_effects(
                    frame, 
                    chain_type='artnet',
                    current_clip_id=self.current_clip_id,
                    source=self.source,
                    player=self,
                    player_name=self.player_name
                )
            elif self.effect_processor.video_effect_chain:
                # Nur Video-Chain: Art-Net nutzt Original
                frame_for_video_preview = self.effect_processor.apply_effects(
                    frame.copy(), 
                    chain_type='video',
                    current_clip_id=self.current_clip_id,
                    source=self.source,
                    player=self,
                    player_name=self.player_name
                )
                frame_for_artnet = frame
            elif self.effect_processor.artnet_effect_chain:
                # Nur Art-Net-Chain: Video nutzt Original
                frame_for_artnet = self.effect_processor.apply_effects(
                    frame, 
                    chain_type='artnet',
                    current_clip_id=self.current_clip_id,
                    source=self.source,
                    player=self,
                    player_name=self.player_name
                )
                frame_for_video_preview = frame
            else:
                # Keine Effects: Beide nutzen Original (View, keine Kopie!)
                frame_for_video_preview = frame
                frame_for_artnet = frame
            
            # Alpha-Compositing für Preview (wenn RGBA vorhanden)
            if frame_for_video_preview.shape[2] == 4:
                frame_for_video_preview = self._alpha_composite_to_black(frame_for_video_preview)
            
            # Alpha-Compositing für Art-Net (wenn RGBA vorhanden)
            if frame_for_artnet.shape[2] == 4:
                frame_for_artnet = self._alpha_composite_to_black(frame_for_artnet)
            
            # Speichere komplettes Frame für Video-Preview (BGR-Conversion mit Buffer-Reuse)
            if not hasattr(self, '_bgr_buffer') or self._bgr_buffer.shape != frame_for_video_preview.shape[:2]:
                self._bgr_buffer = np.empty((frame_for_video_preview.shape[0], frame_for_video_preview.shape[1], 3), dtype=np.uint8)
            cv2.cvtColor(frame_for_video_preview, cv2.COLOR_RGB2BGR, dst=self._bgr_buffer)
            self.last_video_frame = self._bgr_buffer
            
            # DMX extraction - only if needed (Art-Net enabled OR recording active)
            # This saves ~2-3ms per frame when Art-Net is disabled
            needs_dmx = (self.enable_artnet and self.artnet_manager) or self.recording_manager.is_recording
            
            if needs_dmx:
                # NumPy-optimierte Pixel-Extraktion (verwende Art-Net Frame!)
                valid_mask = (
                    (self.point_coords[:, 1] >= 0) & 
                    (self.point_coords[:, 1] < self.canvas_height) &
                    (self.point_coords[:, 0] >= 0) & 
                    (self.point_coords[:, 0] < self.canvas_width)
                )
                
                # Extrahiere RGB-Werte für alle Punkte aus Art-Net Frame
                y_coords = self.point_coords[valid_mask, 1]
                x_coords = self.point_coords[valid_mask, 0]
                rgb_values = frame_for_artnet[y_coords, x_coords]
                
                # DMX-Buffer erstellen
                dmx_buffer = np.zeros((len(self.point_coords), 3), dtype=np.uint8)
                dmx_buffer[valid_mask] = rgb_values
                dmx_buffer = dmx_buffer.flatten().tolist()
                
                # Speichere für Preview (Liste ist bereits Kopie, kein .copy() nötig)
                self.last_frame = dmx_buffer
            else:
                # No DMX needed - just set empty buffer for preview
                dmx_buffer = None
                self.last_frame = None
            
            # Recording
            if self.recording_manager.is_recording and dmx_buffer:
                self.recording_manager.add_frame({
                    'frame': self.source.current_frame,
                    'timestamp': time.time() - self.start_time,
                    'dmx_data': dmx_buffer.copy()
                })
            
            # Sende über Art-Net (nur wenn aktiviert und wir aktiver Art-Net Player sind)
            if self.enable_artnet and self.artnet_manager and self.is_running and dmx_buffer:
                # Prüfe ob wir noch der aktive Art-Net Player sind
                if player_lock._active_player is self:
                    self.artnet_manager.send_frame(dmx_buffer, source='video')
                else:
                    # Ein anderer Player hat Art-Net übernommen - stoppen
                    logger.info(f"{self.player_name}: Art-Net von anderem Player übernommen, stoppe")
                    break
            
            # Beende wenn gestoppt
            if not self.is_running:
                break
            
            # Für Preview-Only Player: Kein Lock-Check nötig
            if self.enable_artnet and player_lock._active_player is not self:
                # Art-Net Player wurde deaktiviert
                break
            
            self.frames_processed += 1
            
            # Frame-Timing mit Drift-Kompensation
            # Verwende source_delay wenn verfügbar, sonst calculated frame_time
            delay = source_delay if source_delay > 0 else frame_time
            delay /= self.speed_factor  # Speed-Faktor anwenden
            
            next_frame_time += delay
            current_time = time.time()
            sleep_time = next_frame_time - current_time
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            elif sleep_time < -0.1:  # Zu langsam, Reset
                next_frame_time = current_time + delay
        
        debug_playback(logger, "Play-Loop beendet")
    
    def status(self):
        """Gibt Status-String zurück."""
        if self.is_playing:
            if self.is_paused:
                return "pausiert"
            return "läuft"
        return "gestoppt"
    
    def get_info(self):
        """Gibt Informationen zurück."""
        import os
        
        info = {
            'source_type': type(self.source).__name__,
            'total_points': self.total_points,
            'total_universes': self.required_universes,
            'points_list': os.path.basename(self.points_json_path) if self.points_json_path else 'N/A',
            'fps_limit': self.fps_limit or self.source.fps
        }
        
        # Erweitere mit Source-spezifischen Infos
        source_info = self.source.get_info()
        info.update(source_info)
        
        return info
    
    def get_stats(self):
        """Gibt Live-Statistiken zurück."""
        runtime = time.time() - self.start_time if self.start_time > 0 else 0
        fps = self.frames_processed / runtime if runtime > 0 else 0
        
        return {
            'fps': round(fps, 1),
            'frames': self.frames_processed,
            'current_frame': self.source.current_frame,
            'total_frames': self.source.total_frames if not self.source.is_infinite else -1,
            'runtime': f"{int(runtime // 60):02d}:{int(runtime % 60):02d}"
        }
    
    # Art-Net Methoden
    def blackout(self):
        """Blackout (alle LEDs aus)."""
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.blackout()
    
    def test_pattern(self, color='red'):
        """Testmuster senden."""
        if self.is_playing and not self.is_paused:
            self.pause()
        
        if self.artnet_manager:
            self.artnet_manager.test_pattern(color)
    
    def set_artnet_manager(self, artnet_manager):
        """Setzt den Art-Net Manager von außen."""
        self.artnet_manager = artnet_manager
    
    def reload_artnet(self):
        """Lädt Art-Net Manager neu (falls bereits gesetzt)."""
        if not self.artnet_manager:
            logger.warning("Kein Art-Net Manager gesetzt")
            return False
        
        try:
            self.artnet_manager.stop()
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager.start(artnet_config)
            logger.info(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
            return True
        except Exception as e:
            logger.error(f"❌ Fehler beim Neuladen von Art-Net: {e}")
            return False
    
    # Einstellungen
    def set_brightness(self, value):
        """Setzt Helligkeit (0-100)."""
        try:
            val = float(value)
            if val < 0 or val > 100:
                debug_playback(logger, "Helligkeit muss zwischen 0 und 100 liegen!")
                return
            self.brightness = val / 100.0
            debug_playback(logger, f"Helligkeit auf {val}% gesetzt")
        except ValueError:
            logger.debug("Ungültiger Helligkeits-Wert!")
    
    def set_speed(self, value):
        """Setzt Geschwindigkeit."""
        try:
            val = float(value)
            if val <= 0:
                logger.debug("Geschwindigkeit muss größer als 0 sein!")
                return
            self.speed_factor = val
            logger.debug(f"Geschwindigkeit auf {val}x gesetzt")
        except ValueError:
            logger.debug("Ungültiger Geschwindigkeits-Wert!")
    
    def set_hue_shift(self, value):
        """Setzt Hue Rotation (0-360 Grad)."""
        try:
            val = int(value)
            if val < 0 or val > 360:
                logger.debug("Hue Shift muss zwischen 0 und 360 liegen!")
                return
            self.hue_shift = val
            logger.debug(f"Hue Shift auf {val}° gesetzt")
        except ValueError:
            logger.debug("Ungültiger Hue Shift-Wert!")
    
    # ========== Player-Level Effect Chain Management (Delegated to EffectProcessor) ==========
    def add_effect_to_chain(self, plugin_id, config=None, chain_type='video'):
        """Fügt einen Effect zur gewählten Chain hinzu - Delegiert an EffectProcessor."""
        return self.effect_processor.add_effect(plugin_id, config, chain_type)
    
    def remove_effect_from_chain(self, index, chain_type='video'):
        """Entfernt einen Effect aus der gewählten Chain - Delegiert an EffectProcessor."""
        return self.effect_processor.remove_effect(index, chain_type)
    
    def clear_effects_chain(self, chain_type='video'):
        """Entfernt alle Effects aus der gewählten Chain - Delegiert an EffectProcessor."""
        return self.effect_processor.clear_chain(chain_type)
    
    def get_effect_chain(self, chain_type='video'):
        """Gibt die aktuelle Effect Chain zurück - Delegiert an EffectProcessor."""
        return self.effect_processor.get_chain(chain_type, layers=self.layers)
    
    def update_effect_parameter(self, index, param_name, value, chain_type='video'):
        """Aktualisiert einen Parameter eines Effects - Delegiert an EffectProcessor."""
        return self.effect_processor.update_parameter(index, param_name, value, chain_type)
    
    def toggle_effect_enabled(self, index, chain_type='video'):
        """Toggles effect enabled/disabled state - Delegiert an EffectProcessor."""
        return self.effect_processor.toggle_enabled(index, chain_type)
    
    
    def _alpha_composite_to_black(self, rgba_frame):
        """
        Composites RGBA frame onto black background using alpha channel.
        
        Args:
            rgba_frame: RGBA frame (H, W, 4)
            
        Returns:
            RGB frame with alpha composited onto black
        """
        # Extract RGB and alpha
        rgb = rgba_frame[:, :, :3].astype(np.float32)
        alpha = rgba_frame[:, :, 3:].astype(np.float32) / 255.0
        
        # Composite: result = rgb * alpha + black * (1 - alpha) = rgb * alpha
        composited = (rgb * alpha).astype(np.uint8)
        
        return composited
    
    # Recording - Delegated to RecordingManager
    def start_recording(self, name=None):
        """Startet Aufzeichnung."""
        if not self.is_playing:
            logger.debug("Aufzeichnung nur während Wiedergabe möglich!")
            return False
        return self.recording_manager.start_recording(name)
    
    def stop_recording(self):
        """Stoppt Aufzeichnung und speichert sie."""
        return self.recording_manager.stop_recording(
            canvas_width=self.canvas_width,
            canvas_height=self.canvas_height,
            total_points=self.total_points
        )
    
    def load_points(self, points_json_path):
        """
        Lädt neue Points-Konfiguration und passt Player entsprechend an.
        
        WICHTIG: Stoppt/Startet Source neu, da Canvas-Größe sich ändern kann!
        
        Args:
            points_json_path: Pfad zur neuen Points-JSON-Datei
        """
        logger.info(f"Lade neue Points-Konfiguration: {os.path.basename(points_json_path)}")
        
        # Lade neue Points-Daten
        validate_bounds = isinstance(self.source, VideoSource)
        points_data = PointsLoader.load_points(points_json_path, validate_bounds=validate_bounds)
        
        # Prüfe ob Canvas-Größe sich ändert
        canvas_changed = (
            points_data['canvas_width'] != self.canvas_width or 
            points_data['canvas_height'] != self.canvas_height
        )
        
        # Update Points-Daten
        old_points = self.total_points
        old_universes = self.required_universes
        
        self.points_json_path = points_json_path
        self.point_coords = points_data['point_coords']
        self.canvas_width = points_data['canvas_width']
        self.canvas_height = points_data['canvas_height']
        self.universe_mapping = points_data['universe_mapping']
        self.total_points = points_data['total_points']
        self.total_channels = points_data['total_channels']
        self.required_universes = points_data['required_universes']
        self.channels_per_universe = points_data['channels_per_universe']
        
        # Wenn Canvas-Größe sich ändert, muss Source neu initialisiert werden
        if canvas_changed:
            logger.info(f"Canvas-Größe geändert: {self.canvas_width}x{self.canvas_height}")
            
            # Stoppe Source
            self.source.cleanup()
            
            # Erstelle neue Source-Instanz mit neuer Canvas-Größe
            source_path = self.source.source_path if hasattr(self.source, 'source_path') else None
            is_video_source = isinstance(self.source, VideoSource)
            
            if is_video_source:
                self.source = VideoSource(source_path, self.canvas_width, self.canvas_height, self.config)
            else:
                # ScriptSource oder andere - passe Canvas-Größe an
                self.source.canvas_width = self.canvas_width
                self.source.canvas_height = self.canvas_height
            
            # Neu initialisieren
            if not self.source.initialize():
                raise ValueError(f"Source konnte nicht neu initialisiert werden")
        
        # Art-Net Manager aktualisieren
        if self.artnet_manager:
            # Stoppe alten Manager
            self.artnet_manager.stop()
            
            # Erstelle neuen Manager mit neuen Dimensionen
            from .artnet_manager import ArtNetManager
            artnet_config = self.config.get('artnet', {})
            self.artnet_manager = ArtNetManager(
                self.target_ip,
                self.start_universe,
                self.total_points,
                self.channels_per_universe
            )
            self.artnet_manager.start(artnet_config)
            
            logger.info(f"Art-Net Manager aktualisiert: {self.required_universes} Universen")
        
        logger.info(f"✅ Points gewechselt:")
        logger.info(f"   Punkte: {old_points} → {self.total_points}")
        logger.info(f"   Universen: {old_universes} → {self.required_universes}")
        logger.info(f"   Canvas: {self.canvas_width}x{self.canvas_height}")
    
    # ========== Multi-Layer Management ==========
    
    def load_clip_layers(self, clip_id, clip_registry, video_dir=None):
        """Delegates to layer_manager.load_clip_layers()."""
        return self.layer_manager.load_clip_layers(clip_id, video_dir, self.player_name)
    
    def add_layer(self, source, clip_id=None, blend_mode='normal', opacity=100.0):
        """Delegates to layer_manager.add_layer()."""
        return self.layer_manager.add_layer(source, clip_id, blend_mode, opacity, self.player_name)
    
    def remove_layer(self, layer_id):
        """Delegates to layer_manager.remove_layer()."""
        return self.layer_manager.remove_layer(layer_id, self.player_name)
    
    def get_layer(self, layer_id):
        """Delegates to layer_manager.get_layer()."""
        return self.layer_manager.get_layer(layer_id)
    
    def reorder_layers(self, new_order):
        """Delegates to layer_manager.reorder_layers()."""
        return self.layer_manager.reorder_layers(new_order, self.player_name)
    
    def update_layer_config(self, layer_id, blend_mode=None, opacity=None, enabled=None):
        """Delegates to layer_manager.update_layer_config()."""
        return self.layer_manager.update_layer_config(layer_id, blend_mode, opacity, enabled, self.player_name)
    
    def apply_layer_effects(self, layer, frame):
        """Delegates to layer_manager.apply_layer_effects()."""
        return self.layer_manager.apply_layer_effects(layer, frame, self.player_name)
    
    def load_layer_effects_from_registry(self, layer):
        """Delegates to layer_manager.load_layer_effects_from_registry()."""
        return self.layer_manager.load_layer_effects_from_registry(layer, self.player_name)
    
    def reload_all_layer_effects(self):
        """Delegates to layer_manager.reload_all_layer_effects()."""
        return self.layer_manager.reload_all_layer_effects(self.player_name)
    
    def get_blend_plugin(self, blend_mode, opacity):
        """Delegates to layer_manager.get_blend_plugin()."""
        return self.layer_manager.get_blend_plugin(blend_mode, opacity)
    
    # Backward Compatibility: source Property
    @property
    def source(self):
        """
        Gibt erste Layer-Source zurück für Backward Compatibility.
        Wenn Layers existieren, gibt Layer 0 Source zurück.
        Sonst gibt Legacy-Source zurück.
        """
        if self.layers:
            return self.layers[0].source
        return self._legacy_source
    
    @source.setter
    def source(self, value):
        """
        Setzt Source - für Backward Compatibility.
        Wenn Layers existieren, aktualisiert Layer 0.
        Sonst speichert in Legacy-Source.
        """
        if self.layers:
            self.layers[0].source = value
        else:
            self._legacy_source = value
    
    # Backward Compatibility: current_clip_id Property
    @property
    def current_clip_id(self):
        """Gibt Clip-ID von Layer 0 zurück (Backward Compatibility)."""
        if self.layers:
            return self.layers[0].clip_id
        return None
    
    @current_clip_id.setter
    def current_clip_id(self, value):
        """Setzt Clip-ID von Layer 0 (Backward Compatibility)."""
        if self.layers:
            self.layers[0].clip_id = value
    
