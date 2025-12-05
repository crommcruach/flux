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
from .logger import get_logger
from .artnet_manager import ArtNetManager
from .points_loader import PointsLoader
from .frame_source import VideoSource, ScriptSource
from .plugin_manager import get_plugin_manager
from .layer import Layer
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
            frame_source: FrameSource-Instanz (VideoSource, ScriptSource, etc.)
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
        
        # Multi-Layer System (NEW)
        self.layers = []  # List of Layer objects
        self.layer_counter = 0  # For generating unique layer IDs
        
        # ⚠️ DEAD CODE - REMOVE IN FUTURE VERSION ⚠️
        # TODO: Remove _legacy_source after all code uses layers[0].source instead
        # Legacy single source (for backward compatibility via @property)
        self._legacy_source = frame_source
        
        self.points_json_path = points_json_path
        self.target_ip = target_ip
        self.start_universe = start_universe
        self.fps_limit = fps_limit
        self.config = config or {}
        
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
        
        # Playlist Management
        self.playlist = []  # Liste von Video-Pfaden
        self.playlist_index = -1  # Aktueller Index in der Playlist
        self.playlist_params = {}  # Dict: generator_id -> parameters (for autoplay)
        self.playlist_ids = {}  # Map: path → UUID (für Clip-Effekt-Binding)
        self.autoplay = True  # Automatisch nächstes Video abspielen
        self.loop_playlist = True  # Playlist wiederholen
        
        # Effect Chains für Plugins (getrennt für Video-Preview und Art-Net)
        self.video_effect_chain = []  # Video-Preview FX (nicht zu Art-Net)
        self.artnet_effect_chain = []  # Art-Net Output FX (nicht zu Video-Preview)
        
        # B3 Performance: ClipRegistry-Effect-Cache mit Version-Tracking
        self._cached_clip_effects = None  # Cached effect list
        self._cached_clip_id = None       # Clip ID of cached effects
        self._cached_version = -1         # Version counter for cache invalidation
        self.current_clip_id = None  # UUID of currently loaded clip (for clip effects from registry)
        self.plugin_manager = get_plugin_manager()
        
        # Recording (deque mit maxlen verhindert Memory-Leak)
        self.is_recording = False
        # Max 1h bei 30 FPS = 108000 Frames (~650 MB), begrenze auf 36000 (~195 MB max)
        self.recorded_data = deque(maxlen=36000)
        self.recording_name = None
        
        # Preview Frames
        self.last_frame = None  # Letztes Frame (LED-Punkte RGB) für Preview
        self.last_video_frame = None  # Letztes komplettes Frame für Preview
        
        # Transition System
        self.transition_config = {
            "enabled": False,
            "effect": "fade",
            "duration": 1.0,
            "easing": "ease_in_out",
            "plugin": None
        }
        self.transition_buffer = None  # Buffer für letztes Frame (für Transitions)
        self.transition_active = False
        self.transition_start_time = 0
        self.transition_frames = 0
        
        # Lade Points-Konfiguration
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
        
        # NICHT initialisieren im Konstruktor - wird lazy beim ersten play() gemacht
        # Grund: Verhindert dass mehrere Player dieselbe Video-Datei parallel öffnen (FFmpeg-Konflikt)
        self.source_initialized = False
        
        logger.debug(f"{self.player_name} initialisiert:")
        logger.debug(f"  Source: {self.source.get_source_name()} ({type(self.source).__name__})")
        logger.debug(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Punkte: {self.total_points}, Kanäle: {self.total_channels}")
        logger.debug(f"  Universen: {self.required_universes}")
        logger.debug(f"  Art-Net: {'Enabled' if enable_artnet else 'Disabled'} ({target_ip}, Start-Universe: {start_universe})")
        
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
        """Script-Name (falls ScriptSource)."""
        return getattr(self.source, 'script_name', None)
    
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
    
    def play(self):
        """Intelligente Play-Funktion: startet oder setzt fort je nach Status."""
        if self.is_playing and not self.is_paused:
            logger.debug(f"{self.player_name}: Wiedergabe läuft bereits!")
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
            logger.debug(f"{self.player_name}: Wiedergabe läuft bereits!")
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
            logger.debug("Wiedergabe läuft nicht!")
            return
        
        logger.debug("Stoppe Wiedergabe...")
        
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
            logger.debug("Wiedergabe läuft nicht oder ist bereits pausiert!")
            return
        
        self.is_paused = True
        self.pause_event.clear()  # Event cleared = pausiert
        logger.debug("Wiedergabe pausiert")
    
    def resume(self):
        """Setzt Wiedergabe fort."""
        if not self.is_playing or not self.is_paused:
            logger.debug("Wiedergabe läuft nicht oder ist nicht pausiert!")
            return
        
        self.is_paused = False
        self.pause_event.set()  # Event set = fortsetzen (immediate response)
        logger.debug("Wiedergabe fortgesetzt")
        
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
        
        logger.debug("Wiedergabe neu gestartet (vom ersten Frame)")
    
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
            logger.debug(f"🎬 Multi-Layer Mode: Master FPS={fps} (Layer 0)")
        else:
            fps = self.fps_limit if self.fps_limit else self.source.fps
            logger.debug(f"🎬 Single-Source Mode: FPS={fps}")
        
        frame_time = 1.0 / fps if fps > 0 else 0
        next_frame_time = time.time()
        
        frame_wait_delay = self.config.get('video', {}).get('frame_wait_delay', 0.1)
        
        source_name = self.layers[0].source.get_source_name() if self.layers else self.source.get_source_name()
        logger.debug(f"Play-Loop gestartet: FPS={fps}, Source={source_name}")
        
        while self.is_running and self.is_playing:
            # Pause-Handling (Event-basiert für low-latency)
            if self.is_paused:
                # Warte auf resume (pause_event.set()) - keine CPU-Last, immediate wake
                self.pause_event.wait(timeout=frame_wait_delay)
                next_frame_time = time.time()  # Reset timing
                continue
            
            loop_start = time.time()
            
            # ========== MULTI-LAYER COMPOSITING ==========
            if self.layers and len(self.layers) > 0:
                # Master Frame (Layer 0 bestimmt Timing und Länge)
                frame, source_delay = self.layers[0].source.get_next_frame()
                
                if frame is not None:
                    # Wende Layer 0 Effects an
                    frame = self.apply_layer_effects(self.layers[0], frame)
                    
                    # Composite Slave Layers (1-N)
                    for layer in self.layers[1:]:
                        if not layer.enabled:
                            continue
                        
                        overlay_frame, _ = layer.source.get_next_frame()
                        
                        # Auto-Reset wenn Slave-Layer am Ende (Looping!)
                        if overlay_frame is None:
                            logger.debug(f"🔁 Layer {layer.layer_id} reached end, auto-reset (slave loop)")
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
                
            else:
                # Fallback: Single-Source Mode (Backward Compatibility)
                frame, source_delay = self.source.get_next_frame()
            
            # ========== REST IST UNVERÄNDERT ==========
            
            if frame is None:
                # Ende der Source (Video-Loop oder Fehler)
                self.current_loop += 1
                
                logger.debug(f"🎬 [{self.player_name}] Frame=None: autoplay={self.autoplay}, playlist_len={len(self.playlist)}, current_index={self.playlist_index}")
                
                # Prüfe Playlist-Autoplay
                if self.autoplay and len(self.playlist) > 0:
                    # Nächstes Video in Playlist laden
                    next_index = self.playlist_index + 1
                    
                    # Loop zurück zum Anfang wenn am Ende
                    if next_index >= len(self.playlist):
                        if self.loop_playlist:
                            next_index = 0
                            logger.debug("🔁 Playlist loop - zurück zum ersten Video")
                        else:
                            logger.debug("📋 Ende der Playlist erreicht, stoppe...")
                            break
                    
                    # Lade nächstes Video oder Generator
                    next_item_path = self.playlist[next_index]
                    logger.debug(f"⏭️ [{self.player_name}] Autoplay: Lade nächstes Item ({next_index + 1}/{len(self.playlist)}): {next_item_path}")
                    
                    try:
                        from .frame_source import VideoSource, GeneratorSource
                        
                        # Check if it's a generator
                        if next_item_path.startswith('generator:'):
                            generator_id = next_item_path.replace('generator:', '')
                            
                            # Try to get parameters from multiple sources (priority order):
                            parameters = None
                            
                            # 1. Check clip registry (stored parameters from playlist)
                            from .clip_registry import get_clip_registry
                            clip_registry = get_clip_registry()
                            clip_id = self.playlist_ids.get(next_item_path)
                            if clip_id and clip_id in clip_registry.clips:
                                clip_meta = clip_registry.clips[clip_id].get('metadata', {})
                                if clip_meta.get('parameters'):
                                    parameters = clip_meta['parameters'].copy()
                                    logger.debug(f"🌟 [{self.player_name}] Using ClipRegistry parameters: {parameters}")
                            
                            # 2. Check playlist_params (user runtime modifications)
                            if not parameters and generator_id in self.playlist_params:
                                parameters = self.playlist_params[generator_id].copy()
                                logger.debug(f"🌟 [{self.player_name}] Using playlist_params: {parameters}")
                            
                            # 3. Reuse current generator parameters if same generator
                            if not parameters:
                                current_source = self.layers[0].source if self.layers else self.source
                                if isinstance(current_source, GeneratorSource) and current_source.generator_id == generator_id:
                                    parameters = current_source.parameters.copy()
                                    self.playlist_params[generator_id] = parameters.copy()
                                    logger.debug(f"🌟 [{self.player_name}] Reusing and storing modified parameters: {parameters}")
                            
                            # 4. Fallback to defaults
                            if not parameters:
                                from .plugin_manager import get_plugin_manager
                                pm = get_plugin_manager()
                                param_list = pm.get_plugin_parameters(generator_id)
                                parameters = {p['name']: p['default'] for p in param_list}
                                logger.debug(f"🌟 [{self.player_name}] Using default parameters: {parameters}")
                            
                            new_source = GeneratorSource(generator_id, parameters, self.canvas_width, self.canvas_height, self.config)
                            logger.debug(f"🌟 [{self.player_name}] Loading generator: {generator_id}")
                        else:
                            # Look up clip_id for this video to support trim/reverse
                            clip_id = self.playlist_ids.get(next_item_path)
                            logger.info(f"🔍 [{self.player_name}] Looking up clip_id: path='{next_item_path}', found={clip_id}")
                            logger.debug(f"   playlist_ids keys: {list(self.playlist_ids.keys())}")
                            new_source = VideoSource(next_item_path, self.canvas_width, self.canvas_height, self.config, clip_id=clip_id)
                            logger.debug(f"🎬 [{self.player_name}] Loading video: {next_item_path} (clip_id={clip_id})")
                        
                        # Initialisiere neue Source
                        if not new_source.initialize():
                            logger.error(f"❌ [{self.player_name}] Fehler beim Initialisieren des nächsten Items: {next_item_path}")
                            break
                        
                        # Start transition if enabled
                        if self.transition_config.get("enabled") and self.transition_buffer is not None:
                            self.transition_active = True
                            self.transition_start_time = time.time()
                            self.transition_frames = 0
                            logger.debug(f"⚡ [{self.player_name}] Transition started: {self.transition_config['effect']}")
                        
                        # Cleanup alte Source
                        if self.layers:
                            # Multi-Layer: Ersetze Layer 0 Source
                            if self.layers[0].source:
                                self.layers[0].source.cleanup()
                            self.layers[0].source = new_source
                            logger.debug(f"🔧 [{self.player_name}] Layer 0 source replaced with new source")
                        else:
                            # Single-Source: Legacy behavior
                            if self.source:
                                self.source.cleanup()
                            self.source = new_source
                        
                        self.playlist_index = next_index
                        self.current_loop = 0
                        
                        # Register clip for effect management - USE EXISTING UUID FROM PLAYLIST!
                        from .clip_registry import get_clip_registry
                        clip_registry = get_clip_registry()
                        
                        # First, check if we already have a UUID for this path
                        clip_id = self.playlist_ids.get(next_item_path)
                        
                        if not clip_id:
                            # No UUID yet - register new clip
                            if next_item_path.startswith('generator:'):
                                clip_id = clip_registry.register_clip(
                                    player_id=self.player_id,
                                    absolute_path=next_item_path,
                                    relative_path=next_item_path,
                                    metadata={'type': 'generator', 'generator_id': generator_id, 'parameters': parameters}
                                )
                            else:
                                relative_path = os.path.relpath(next_item_path, self.config.get('paths', {}).get('video_dir', 'video'))
                                clip_id = clip_registry.register_clip(
                                    player_id=self.player_id,
                                    absolute_path=next_item_path,
                                    relative_path=relative_path,
                                    metadata={}
                                )
                            self.playlist_ids[next_item_path] = clip_id
                        
                        self.current_clip_id = clip_id
                        
                        # Load layers for new clip (wichtig: überschreibt alte Layer!)
                        video_dir = self.config.get('paths', {}).get('video_dir', 'video')
                        if not self.load_clip_layers(clip_id, clip_registry, video_dir):
                            logger.warning(f"⚠️ [{self.player_name}] Could not load layers for clip {clip_id}, using single-source fallback")
                        
                        item_name = generator_id if next_item_path.startswith('generator:') else os.path.basename(next_item_path)
                        logger.info(f"✅ [{self.player_name}] Nächstes Item geladen: {item_name} (clip_id={clip_id})")
                        continue
                    except Exception as e:
                        logger.error(f"❌ [{self.player_name}] Fehler beim Laden des nächsten Items: {e}")
                        break
                
                # Kein Autoplay - normales Loop-Verhalten
                # Loop-Limit prüfen (nur für nicht-infinite Sources)
                current_source = self.layers[0].source if self.layers else self.source
                if not current_source.is_infinite and self.max_loops > 0 and self.current_loop >= self.max_loops:
                    logger.debug(f"Loop-Limit ({self.max_loops}) erreicht, stoppe...")
                    break
                
                # Reset Source für nächsten Loop
                if self.layers:
                    # Multi-Layer: Reset nur Master (Layer 0), Slaves loopen selbst
                    self.layers[0].source.reset()
                    logger.debug(f"🔁 [{self.player_name}] Master Layer 0 reset for next loop")
                else:
                    # Single-Source: Legacy behavior
                    self.source.reset()
                continue
            
            # Apply transition if active
            if self.transition_active:
                elapsed = time.time() - self.transition_start_time
                duration = self.transition_config.get("duration", 1.0)
                
                if elapsed < duration and self.transition_buffer is not None:
                    # Calculate progress (0.0 to 1.0)
                    progress = min(1.0, elapsed / duration)
                    
                    # Apply transition using plugin
                    transition_plugin = self.transition_config.get("plugin")
                    if transition_plugin:
                        try:
                            frame = transition_plugin.blend_frames(
                                self.transition_buffer,
                                frame,
                                progress
                            )
                            self.transition_frames += 1
                        except Exception as e:
                            logger.error(f"❌ [{self.player_name}] Transition error: {e}")
                            self.transition_active = False
                else:
                    # Transition complete
                    self.transition_active = False
                    logger.debug(f"✅ [{self.player_name}] Transition complete ({self.transition_frames} frames)")
            
            # Store frame for next transition
            if self.transition_config.get("enabled"):
                self.transition_buffer = frame.copy()
            
            # Helligkeit in-place anwenden (Performance-Optimierung: keine Kopie!)
            if self.brightness != 1.0:
                # NumPy in-place multiplication (arbeitet direkt auf frame)
                np.multiply(frame, self.brightness, out=frame, casting='unsafe')
                np.clip(frame, 0, 255, out=frame)
                frame = frame.astype(np.uint8)
            
            # Hue Shift in-place anwenden wenn aktiviert
            if self.hue_shift != 0:
                frame_hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                frame_hsv[:, :, 0] = (frame_hsv[:, :, 0].astype(np.int16) + self.hue_shift // 2) % 180
                cv2.cvtColor(frame_hsv, cv2.COLOR_HSV2RGB, dst=frame)
            
            # Wende Effect Chains an - nur kopieren wenn beide Chains unterschiedlich sind
            if self.video_effect_chain and self.artnet_effect_chain:
                # Beide Chains aktiv: Kopie nötig für separate Processing
                frame_for_video_preview = self.apply_effects(frame.copy(), chain_type='video')
                frame_for_artnet = self.apply_effects(frame, chain_type='artnet')
            elif self.video_effect_chain:
                # Nur Video-Chain: Art-Net nutzt Original
                frame_for_video_preview = self.apply_effects(frame.copy(), chain_type='video')
                frame_for_artnet = frame
            elif self.artnet_effect_chain:
                # Nur Art-Net-Chain: Video nutzt Original
                frame_for_artnet = self.apply_effects(frame, chain_type='artnet')
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
            
            # Recording
            if self.is_recording:
                self.recorded_data.append({
                    'frame': self.source.current_frame,
                    'timestamp': time.time() - self.start_time,
                    'dmx_data': dmx_buffer.copy()
                })
            
            # Sende über Art-Net (nur wenn aktiviert und wir aktiver Art-Net Player sind)
            if self.enable_artnet and self.artnet_manager and self.is_running:
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
        
        logger.debug("Play-Loop beendet")
    
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
            logger.debug(f"✅ Art-Net neu geladen mit IP: {self.target_ip}")
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
                logger.debug("Helligkeit muss zwischen 0 und 100 liegen!")
                return
            self.brightness = val / 100.0
            logger.debug(f"Helligkeit auf {val}% gesetzt")
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
    
    # ========== Player-Level Effect Chain Management ==========
    def add_effect_to_chain(self, plugin_id, config=None, chain_type='video'):
        """
        Fügt einen Effect zur gewählten Chain hinzu.
        
        Args:
            plugin_id: Plugin-ID (z.B. 'blur')
            config: Plugin-Konfiguration (Dict)
            chain_type: 'video' für Video-Preview, 'artnet' für Art-Net
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Lade Plugin-Instanz
            logger.debug(f"Loading plugin '{plugin_id}' for {chain_type} chain with config: {config}")
            plugin_instance = self.plugin_manager.load_plugin(plugin_id, config)
            if not plugin_instance:
                return False, f"Plugin '{plugin_id}' konnte nicht geladen werden"
            
            # Prüfe ob es ein EFFECT-Plugin ist
            from plugins import PluginType
            plugin_type = plugin_instance.METADATA.get('type')
            
            if plugin_type != PluginType.EFFECT:
                return False, f"Plugin '{plugin_id}' ist kein EFFECT-Plugin"
            
            effect_data = {
                'id': plugin_id,
                'instance': plugin_instance,
                'config': config or {}
            }
            
            # Füge zur richtigen Chain hinzu
            if chain_type == 'artnet':
                self.artnet_effect_chain.append(effect_data)
                chain_length = len(self.artnet_effect_chain)
            else:
                self.video_effect_chain.append(effect_data)
                chain_length = len(self.video_effect_chain)
            
            logger.info(f"✅ Effect '{plugin_id}' zur {chain_type} Chain hinzugefügt (Position {chain_length})")
            return True, f"Effect '{plugin_id}' added to {chain_type} chain"
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Fehler beim Hinzufügen von Effect '{plugin_id}': {e}")
            logger.error(traceback.format_exc())
            return False, str(e)
    
    def remove_effect_from_chain(self, index, chain_type='video'):
        """Entfernt einen Effect aus der gewählten Chain."""
        try:
            chain = self.artnet_effect_chain if chain_type == 'artnet' else self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, f"Invalid index {index} (chain length: {len(chain)})"
            
            effect = chain.pop(index)
            logger.info(f"✅ Effect '{effect['id']}' von {chain_type} Chain Position {index} entfernt")
            return True, f"Effect removed from {chain_type} chain"
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Entfernen von Effect: {e}")
            return False, str(e)
    
    def clear_effects_chain(self, chain_type='video'):
        """Entfernt alle Effects aus der gewählten Chain."""
        if chain_type == 'artnet':
            count = len(self.artnet_effect_chain)
            self.artnet_effect_chain.clear()
        else:
            count = len(self.video_effect_chain)
            self.video_effect_chain.clear()
        
        logger.info(f"✅ {count} Effects aus {chain_type} Chain entfernt")
        return True, f"{count} effects cleared from {chain_type} chain"
    
    def get_effect_chain(self, chain_type='video'):
        """
        Gibt die aktuelle Effect Chain zurück.
        
        Args:
            chain_type: 'video' für Video-Preview, 'artnet' für Art-Net
        
        Returns:
            list: Liste von Effect-Infos [{plugin_id, parameters, metadata}, ...]
        """
        # Select correct chain
        if chain_type == 'artnet':
            chain = self.artnet_effect_chain
        else:
            chain = self.video_effect_chain
        
        chain_info = []
        for i, effect in enumerate(chain):
            plugin_instance = effect['instance']
            
            # Hole aktuelle Parameter-Werte von Plugin-Instanz via get_parameters()
            current_parameters = plugin_instance.get_parameters()
            
            # Konvertiere METADATA für JSON (Enums zu Strings)
            from plugins import PluginType, ParameterType
            metadata = plugin_instance.METADATA.copy()
            if 'type' in metadata and isinstance(metadata['type'], PluginType):
                metadata['type'] = metadata['type'].value
            
            # Konvertiere PARAMETERS für JSON
            parameters_schema = []
            for param in plugin_instance.PARAMETERS:
                param_copy = param.copy()
                if 'type' in param_copy and isinstance(param_copy['type'], ParameterType):
                    param_copy['type'] = param_copy['type'].value
                parameters_schema.append(param_copy)
            
            chain_info.append({
                'index': i,
                'plugin_id': effect['id'],  # Frontend erwartet 'plugin_id'
                'name': plugin_instance.METADATA.get('name', effect['id']),
                'version': plugin_instance.METADATA.get('version', '1.0.0'),
                'enabled': effect.get('enabled', True),  # Export enabled state
                'parameters': current_parameters,  # Aktuelle Werte
                'metadata': {
                    **metadata,
                    'parameters': parameters_schema  # Parameter-Schema mit konvertierten Types
                }
            })
        return chain_info
    
    def update_effect_parameter(self, index, param_name, value, chain_type='video'):
        """
        Aktualisiert einen Parameter eines Effects in der Chain.
        
        Args:
            index: Index des Effects
            param_name: Name des Parameters
            value: Neuer Wert
            chain_type: 'video' oder 'artnet'
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Select correct chain
            if chain_type == 'artnet':
                chain = self.artnet_effect_chain
            else:
                chain = self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, f"Invalid index {index}"
            
            effect = chain[index]
            plugin_id = effect['id']
            plugin_instance = effect['instance']
            
            # Validiere Parameter über PluginManager
            is_valid = self.plugin_manager.validate_parameter_value(plugin_id, param_name, value)
            if not is_valid:
                return False, f"Invalid value for parameter '{param_name}'"
            
            # Setze Parameter direkt auf Plugin-Instanz
            success = plugin_instance.update_parameter(param_name, value)
            
            if success:
                # Update config
                effect['config'][param_name] = value
                logger.debug(f"Effect '{plugin_id}' Parameter '{param_name}' = {value}")
                return True, f"Parameter '{param_name}' updated"
            else:
                return False, f"Plugin does not support parameter '{param_name}'"
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Update von Effect {index} Parameter: {e}")
            return False, str(e)
    
    def toggle_effect_enabled(self, index, chain_type='video'):
        """
        Toggles the enabled/disabled state of an effect in the chain.
        When disabled, the effect is skipped during processing but parameters are preserved.
        
        Args:
            index: Index of the effect
            chain_type: 'video' or 'artnet'
        
        Returns:
            tuple: (success: bool, enabled: bool, message: str)
        """
        try:
            # Select correct chain
            if chain_type == 'artnet':
                chain = self.artnet_effect_chain
            else:
                chain = self.video_effect_chain
            
            if index < 0 or index >= len(chain):
                return False, False, f"Invalid index {index}"
            
            effect = chain[index]
            
            # Toggle enabled state (default is enabled if not set)
            current_state = effect.get('enabled', True)
            new_state = not current_state
            effect['enabled'] = new_state
            
            plugin_id = effect['id']
            logger.info(f"Effect '{plugin_id}' at index {index} is now {'enabled' if new_state else 'disabled'}")
            
            return True, new_state, f"Effect {'enabled' if new_state else 'disabled'}"
            
        except Exception as e:
            logger.error(f"❌ Error toggling effect {index}: {e}")
            return False, False, str(e)
    
    def apply_effects(self, frame, chain_type='video'):
        """
        Wendet alle Effects in der gewählten Chain auf das Frame an.
        
        Args:
            frame: Input-Frame (numpy array, RGB, uint8)
            chain_type: 'video' für Video-Preview, 'artnet' für Art-Net Ausgabe
        
        Returns:
            numpy array: Prozessiertes Frame
        """
        processed_frame = frame
        
        # 1. Apply clip-level effects first (if current clip has effects)
        # NEU: Effekte aus ClipRegistry laden (UUID-basiert) statt aus self.clip_effects (path-basiert)
        # B3 Performance Optimization: Version-basierte Cache-Invalidierung
        if self.clip_registry and hasattr(self, 'current_clip_id') and self.current_clip_id:
            current_version = self.clip_registry.get_effects_version(self.current_clip_id)
            
            # Cache-Check: clip_id UND version müssen übereinstimmen
            if (self._cached_clip_id == self.current_clip_id and 
                self._cached_version == current_version):
                # Cache hit! Nutze gecachte Effekte (99.9% der Frames)
                clip_effects = self._cached_clip_effects
            else:
                # Cache miss: Lade Effekte neu (nur bei Clip-Wechsel oder Parameter-Änderung)
                clip_effects = self.clip_registry.get_clip_effects(self.current_clip_id)
                
                # Pre-instantiate plugin instances (remove lazy-loading overhead)
                for effect_data in clip_effects:
                    if 'instance' not in effect_data:
                        plugin_id = effect_data['plugin_id']
                        if plugin_id in self.plugin_manager.registry:
                            plugin_class = self.plugin_manager.registry[plugin_id]
                            effect_data['instance'] = plugin_class()
                            logger.info(f"✅ [{self.player_name}] Created clip effect instance: {plugin_id} for clip {self.current_clip_id}")
                        else:
                            logger.warning(f"Plugin '{plugin_id}' not found in registry")
                
                # Update cache
                self._cached_clip_effects = clip_effects
                self._cached_clip_id = self.current_clip_id
                self._cached_version = current_version
                logger.debug(f"📦 [{self.player_name}] Effect cache updated for clip {self.current_clip_id} (version: {current_version})")
            
            if clip_effects:
                # Log once per second to avoid spam
                if not hasattr(self, '_last_effect_log') or (hasattr(self, 'current_frame') and self.current_frame % 30 == 0):
                    logger.debug(f"[{self.player_name}] Applying {len(clip_effects)} clip effects for clip_id={self.current_clip_id}")
                    self._last_effect_log = True
                
                for effect_data in clip_effects:
                    # Skip disabled effects (parameters are preserved)
                    if not effect_data.get('enabled', True):
                        continue
                    
                    try:
                        # Instance ist garantiert vorhanden (pre-instantiated im Cache)
                        plugin_instance = effect_data['instance']
                        
                        # Update parameters from effect_data EVERY frame (parameters may have changed via API)
                        for param_name, param_value in effect_data['parameters'].items():
                            # Extract actual value if it's a range metadata dict
                            if isinstance(param_value, dict) and '_value' in param_value:
                                param_value = param_value['_value']
                            setattr(plugin_instance, param_name, param_value)
                        
                        # Process frame (pass source for Transport plugin)
                        processed_frame = plugin_instance.process_frame(processed_frame, source=self.source, player=self)
                        
                        if processed_frame is None:
                            logger.error(f"❌ [{self.player_name}] Clip effect '{effect_data['plugin_id']}' returned None")
                            processed_frame = frame
                            continue
                            
                    except Exception as e:
                        logger.error(f"❌ [{self.player_name}] Error in clip effect '{effect_data.get('plugin_id', 'unknown')}': {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        continue
            else:
                logger.debug(f"[{self.player_name}] No clip effects for clip_id={self.current_clip_id}")
        
        # 2. Apply player-level effects
        if chain_type == 'artnet':
            effect_chain = self.artnet_effect_chain
        else:
            effect_chain = self.video_effect_chain
        
        if effect_chain:
            for effect in effect_chain:
                # Skip disabled effects (parameters are preserved)
                if not effect.get('enabled', True):
                    continue
                
                try:
                    plugin_instance = effect['instance']
                    processed_frame = plugin_instance.process_frame(processed_frame)
                    
                    # Ensure frame is valid
                    if processed_frame is None:
                        logger.error(f"Effect '{effect['id']}' returned None, skipping")
                        processed_frame = frame
                        continue
                        
                except Exception as e:
                    logger.error(f"❌ Fehler in Effect '{effect['id']}': {e}")
                    # Continue with unprocessed frame on error
                    continue
        
        return processed_frame
    
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
    
    # Recording
    def start_recording(self, name=None):
        """Startet Aufzeichnung."""
        if not self.is_playing:
            logger.debug("Aufzeichnung nur während Wiedergabe möglich!")
            return False
        
        self.is_recording = True
        self.recorded_data = []
        self.recording_name = name or "Unnamed"
        logger.debug(f"Aufzeichnung gestartet: {self.recording_name}")
        return True
    
    def stop_recording(self):
        """Stoppt Aufzeichnung und speichert sie."""
        if not self.is_recording:
            logger.debug("Keine Aufzeichnung aktiv!")
            return None
        
        self.is_recording = False
        frame_count = len(self.recorded_data)
        
        if frame_count == 0:
            logger.debug("Keine Frames aufgezeichnet")
            return None
        
        # Speichere Aufzeichnung
        import json
        from datetime import datetime
        
        # Erstelle records Ordner falls nicht vorhanden (Root-Level)
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        records_dir = os.path.join(base_path, 'records')
        os.makedirs(records_dir, exist_ok=True)
        
        # Dateiname mit Timestamp und Name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in (self.recording_name or "recording") if c.isalnum() or c in (' ', '_', '-')).strip()
        filename = f"{safe_name}_{timestamp}.json"
        filepath = os.path.join(records_dir, filename)
        
        # Speichere als JSON
        recording_data = {
            'name': self.recording_name or "Unnamed Recording",
            'timestamp': timestamp,
            'frame_count': frame_count,
            'total_duration': self.recorded_data[-1]['timestamp'] if self.recorded_data else 0,
            'canvas_width': self.canvas_width,
            'canvas_height': self.canvas_height,
            'total_points': self.total_points,
            'frames': self.recorded_data
        }
        
        try:
            with open(filepath, 'w') as f:
                json.dump(recording_data, f)
            logger.info(f"✅ Aufzeichnung gespeichert: {filename} ({frame_count} Frames)")
            return filename
        except Exception as e:
            logger.error(f"❌ Fehler beim Speichern der Aufzeichnung: {e}")
            return None
    
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
        """
        Lädt alle Layers aus einer Clip-Definition und erstellt FrameSources.
        Ersetzt den aktuellen Layer-Stack.
        
        Args:
            clip_id: UUID des Clips aus ClipRegistry
            clip_registry: ClipRegistry-Instanz
            video_dir: Base directory for resolving relative video paths
        
        Returns:
            bool: True bei Erfolg
        """
        # Hole Clip-Daten
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            logger.error(f"❌ [{self.player_name}] Clip {clip_id} nicht gefunden")
            return False
        
        # Build new layer stack first, then swap atomically
        new_layers = []
        layer_counter = 0
        
        # Hole Layer-Definitionen
        layer_defs = clip_data.get('layers', [])
        
        from modules.frame_source import VideoSource, GeneratorSource, ScriptSource
        
        # ALWAYS create Layer 0 from the clip itself (base layer)
        abs_path = clip_data['absolute_path']
        base_source = None
        
        # Detect source type from path
        if abs_path.endswith(('.mp4', '.avi', '.mov', '.mkv')):
            base_source = VideoSource(abs_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height, config=self.config, clip_id=clip_id)
        elif abs_path.startswith('generator:'):
            gen_id = abs_path.replace('generator:', '')
            # Get generator parameters from clip metadata if available
            gen_params = clip_data.get('metadata', {}).get('generator_params', {})
            base_source = GeneratorSource(gen_id, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
        elif abs_path.endswith('.py'):
            base_source = ScriptSource(abs_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
        
        if base_source and base_source.initialize():
            from modules.player import Layer
            base_layer = Layer(layer_counter, base_source, 'normal', 100.0, clip_id)
            new_layers.append(base_layer)
            layer_counter += 1
            logger.info(f"✅ [{self.player_name}] Created clip {clip_id} as Layer 0 (base)")
        else:
            logger.error(f"❌ [{self.player_name}] Failed to create base layer for clip {clip_id}")
            return False
        
        # Now add additional layers from definitions (if any)
        if layer_defs:
            for layer_def in layer_defs:
                source_type = layer_def.get('source_type')
                source_path = layer_def.get('source_path')
                blend_mode = layer_def.get('blend_mode', 'normal')
                opacity = layer_def.get('opacity', 1.0) * 100  # Convert to 0-100
                enabled = layer_def.get('enabled', True)
                
                source = None
                
                if source_type == 'video':
                    # Convert relative path to absolute if needed
                    video_path = source_path
                    if video_dir and not os.path.isabs(video_path):
                        video_path = os.path.join(video_dir, video_path)
                    # Additional layers don't get clip_id - only base layer should have trim/reverse
                    source = VideoSource(video_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height, config=self.config)
                elif source_type == 'generator':
                    # Get generator parameters from layer definition if available
                    gen_params = layer_def.get('parameters', {})
                    source = GeneratorSource(source_path, gen_params, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
                elif source_type == 'script':
                    source = ScriptSource(source_path, canvas_width=self.canvas_width, canvas_height=self.canvas_height)
                
                if source and source.initialize():
                    from modules.player import Layer
                    new_layer = Layer(layer_counter, source, blend_mode, opacity, clip_id)
                    new_layer.enabled = enabled
                    new_layers.append(new_layer)
                    layer_counter += 1
                else:
                    logger.warning(f"⚠️ [{self.player_name}] Failed to create layer source: {source_type}:{source_path}")
        
        # Atomically swap layer stack (thread-safe)
        old_layers = self.layers
        self.layers = new_layers
        self.layer_counter = layer_counter
        
        # Cleanup old layers after swap
        for layer in old_layers:
            try:
                layer.cleanup()
            except Exception as e:
                logger.warning(f"⚠️ Error cleaning up old layer: {e}")
        
        logger.info(f"✅ [{self.player_name}] Loaded {len(self.layers)} layers from clip {clip_id}")
        return True
    
    def add_layer(self, source, clip_id=None, blend_mode='normal', opacity=100.0):
        """
        Fügt einen neuen Layer zum Stack hinzu.
        
        Args:
            source: FrameSource-Instanz (VideoSource, GeneratorSource, etc.)
            clip_id: Optional UUID aus ClipRegistry
            blend_mode: Blend-Modus ('normal', 'multiply', 'screen', etc.)
            opacity: Layer-Opazität 0-100%
        
        Returns:
            int: Layer-ID des neuen Layers
        """
        layer_id = self.layer_counter
        self.layer_counter += 1
        
        layer = Layer(layer_id, source, blend_mode, opacity, clip_id)
        self.layers.append(layer)
        
        logger.info(
            f"✅ [{self.player_name}] Layer {layer_id} added: {source.get_source_name()} "
            f"(blend={blend_mode}, opacity={opacity}%)"
        )
        
        return layer_id
    
    def remove_layer(self, layer_id):
        """
        Entfernt einen Layer aus dem Stack.
        
        Args:
            layer_id: ID des zu entfernenden Layers
        
        Returns:
            bool: True bei Erfolg, False wenn Layer nicht gefunden
        """
        for i, layer in enumerate(self.layers):
            if layer.layer_id == layer_id:
                # Cleanup Layer-Ressourcen
                layer.cleanup()
                
                # Entferne aus Liste
                del self.layers[i]
                
                logger.info(f"🗑️ [{self.player_name}] Layer {layer_id} removed")
                return True
        
        logger.warning(f"⚠️ [{self.player_name}] Layer {layer_id} not found")
        return False
    
    def get_layer(self, layer_id):
        """
        Holt einen Layer anhand seiner ID.
        
        Args:
            layer_id: Layer-ID
        
        Returns:
            Layer oder None wenn nicht gefunden
        """
        for layer in self.layers:
            if layer.layer_id == layer_id:
                return layer
        return None
    
    def reorder_layers(self, new_order):
        """
        Ändert die Reihenfolge der Layers.
        
        Args:
            new_order: Liste von Layer-IDs in neuer Reihenfolge
        
        Returns:
            bool: True bei Erfolg
        """
        # Erstelle Mapping layer_id → Layer
        layer_map = {layer.layer_id: layer for layer in self.layers}
        
        # Prüfe ob alle IDs existieren
        if not all(lid in layer_map for lid in new_order):
            logger.error(f"❌ [{self.player_name}] Invalid layer IDs in new_order")
            return False
        
        # Setze neue Reihenfolge
        self.layers = [layer_map[lid] for lid in new_order]
        
        logger.info(f"🔄 [{self.player_name}] Layers reordered: {new_order}")
        return True
    
    def update_layer_config(self, layer_id, blend_mode=None, opacity=None, enabled=None):
        """
        Aktualisiert Layer-Konfiguration zur Laufzeit.
        
        Args:
            layer_id: Layer-ID
            blend_mode: Optional neuer Blend-Modus
            opacity: Optional neue Opazität
            enabled: Optional enabled-Status
        
        Returns:
            bool: True bei Erfolg
        """
        layer = self.get_layer(layer_id)
        if not layer:
            return False
        
        if blend_mode is not None:
            layer.blend_mode = blend_mode
            logger.debug(f"🔧 [{self.player_name}] Layer {layer_id} blend_mode → {blend_mode}")
        
        if opacity is not None:
            layer.opacity = opacity
            logger.debug(f"🔧 [{self.player_name}] Layer {layer_id} opacity → {opacity}%")
        
        if enabled is not None:
            layer.enabled = enabled
            status = "enabled" if enabled else "disabled"
            logger.debug(f"🔧 [{self.player_name}] Layer {layer_id} → {status}")
        
        return True
    
    def apply_layer_effects(self, layer, frame):
        """
        Wendet alle Effekte eines Layers auf ein Frame an.
        
        Args:
            layer: Layer-Objekt
            frame: Input Frame
        
        Returns:
            Prozessiertes Frame
        """
        for effect in layer.effects:
            # Skip disabled effects (parameters are preserved)
            if not effect.get('enabled', True):
                continue
            
            try:
                instance = effect['instance']
                frame = instance.process_frame(frame)
            except Exception as e:
                logger.error(f"❌ [{self.player_name}] Layer {layer.layer_id} effect error: {e}")
        
        return frame
    
    def get_blend_plugin(self, blend_mode, opacity):
        """
        Erstellt BlendEffect Plugin-Instanz mit gegebenen Parametern.
        
        Args:
            blend_mode: Blend-Modus ('normal', 'multiply', etc.)
            opacity: Opazität 0-100%
        
        Returns:
            BlendEffect Plugin-Instanz
        """
        from plugins.effects.blend import BlendEffect
        
        blend = BlendEffect()
        blend.initialize({
            'blend_mode': blend_mode,
            'opacity': opacity
        })
        
        return blend
    
    # ⚠️ DEAD CODE - REMOVE IN FUTURE VERSION ⚠️
    # TODO: Remove source property after all code uses layers[0].source directly
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
    
