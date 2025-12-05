"""
Frame Sources - Abstrakte Basisklasse und Implementierungen für verschiedene Frame-Quellen
"""
import os
import time
import random
import cv2
import numpy as np
import threading
from abc import ABC, abstractmethod
from .logger import get_logger
from .script_generator import ScriptGenerator
from .constants import DEFAULT_FPS

logger = get_logger(__name__)


class FrameSource(ABC):
    """Abstrakte Basisklasse für Frame-Quellen."""
    
    def __init__(self, canvas_width, canvas_height, config=None):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.config = config or {}
        self.current_frame = 0
        self.total_frames = 0
        self.fps = DEFAULT_FPS
        self.is_infinite = False  # True für Scripts (unendlich)
    
    @abstractmethod
    def initialize(self):
        """Initialisiert die Frame-Quelle. Gibt True bei Erfolg zurück."""
        pass
    
    @abstractmethod
    def get_next_frame(self):
        """
        Gibt das nächste Frame zurück als numpy array (RGB).
        Returns: (frame, delay) tuple
        - frame: numpy array (height, width, 3) in RGB format oder None
        - delay: empfohlene Verzögerung bis zum nächsten Frame in Sekunden
        """
        pass
    
    @abstractmethod
    def reset(self):
        """Setzt die Quelle auf Frame 0 zurück."""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Cleanup-Operationen beim Stoppen."""
        pass
    
    @abstractmethod
    def get_source_name(self):
        """Gibt Namen der Quelle zurück (z.B. Dateiname)."""
        pass
    
    def get_info(self):
        """Gibt Informationen über die Quelle zurück."""
        return {
            'source_type': self.__class__.__name__
        }


class VideoSource(FrameSource):
    """Video-Datei als Frame-Quelle (mit Cache-Support)."""
    
    def __init__(self, video_path, canvas_width, canvas_height, config=None, clip_id=None):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = video_path
        self.source_path = video_path  # Generischer Pfad für load_points()
        self.source_type = 'video'  # Marker für Transport-Effekt
        self.cap = None
        self._lock = threading.Lock()  # Thread-Safety für FFmpeg
        
        # ⚠️ DEAD CODE - REMOVE IN FUTURE VERSION ⚠️
        # DEPRECATED: Clip trimming and playback control - Use Transport Effect Plugin instead
        # TODO: Remove trim/reverse properties and ClipRegistry loading after Transport plugin migration complete
        self.clip_id = clip_id
        self.in_point = None  # Start frame (None = video start)
        self.out_point = None  # End frame (None = video end)
        self.reverse = False  # Reverse playback
        
        # DEPRECATED: Load trim settings from ClipRegistry if clip_id provided
        if self.clip_id:
            from .clip_registry import get_clip_registry
            clip_registry = get_clip_registry()
            playback_info = clip_registry.get_clip_playback_info(self.clip_id)
            if playback_info:
                self.in_point = playback_info.get('in_point')
                self.out_point = playback_info.get('out_point')
                self.reverse = playback_info.get('reverse', False)
                # Set current_frame to in_point if trimming is active
                if self.in_point is not None:
                    self.current_frame = self.in_point
                if self.in_point is not None or self.out_point is not None or self.reverse:
                    logger.info(f"✂️ VideoSource trim settings loaded from ClipRegistry: clip_id={self.clip_id}, in={self.in_point}, out={self.out_point}, reverse={self.reverse}, start_frame={self.current_frame}")
                else:
                    logger.info(f"📹 VideoSource initialized with clip_id={self.clip_id} (no trim settings)")
            else:
                logger.warning(f"⚠️ VideoSource clip_id={self.clip_id} but no playback_info found in ClipRegistry")
        
        # GIF Support
        self.is_gif = self._is_gif_file(video_path)
        self.gif_frame_delays = None
        self.gif_transparency_bg = tuple(config.get('video', {}).get('gif_transparency_bg', [0, 0, 0]) if config else [0, 0, 0])
        self.gif_respect_timing = config.get('video', {}).get('gif_respect_frame_timing', True) if config else True
    
    def _is_gif_file(self, path):
        """Prüft ob Datei ein GIF ist."""
        return path.lower().endswith('.gif')
    
    def _load_gif_frame_delays(self):
        """Lädt Frame-Delays aus GIF mit Pillow."""
        try:
            from PIL import Image
            img = Image.open(self.video_path)
            delays = []
            try:
                frame_idx = 0
                while True:
                    duration = img.info.get('duration', 100)
                    delays.append(duration / 1000.0)
                    frame_idx += 1
                    img.seek(frame_idx)
            except EOFError:
                pass
            
            logger.debug(f"GIF Frame-Delays geladen: {len(delays)} Frames")
            return delays
        except ImportError:
            logger.warning("Pillow nicht verfügbar - GIF Frame-Timing wird ignoriert")
            return None
        except Exception as e:
            logger.warning(f"Fehler beim Laden der GIF Frame-Delays: {e}")
            return None
    
    def _process_frame_transparency(self, frame):
        """Verarbeitet Transparenz in Frames (für GIFs mit Alpha-Channel)."""
        if frame.shape[2] == 4:  # RGBA
            alpha = frame[:, :, 3:4] / 255.0
            rgb = frame[:, :, :3]
            bg = np.array(self.gif_transparency_bg, dtype=np.uint8).reshape(1, 1, 3)
            frame = (rgb * alpha + bg * (1 - alpha)).astype(np.uint8)
        
        return frame[:, :, :3]
    
    def _load_cache(self, points_json_path):
        """Lädt gecachte RGB-Daten wenn verfügbar."""
        if not self.cache_manager:
            return False
        
        cache_path = self.cache_manager.get_cache_path(
            self.video_path, 
            points_json_path, 
            self.canvas_width, 
            self.canvas_height
        )
        
        if not cache_path:
            return False
        
        cache_data = self.cache_manager.load_cache(cache_path)
        if not cache_data:
            return False
        
        self.cached_rgb_data = cache_data['frames']
        self.total_frames = len(self.cached_rgb_data)
        self.fps = cache_data.get('video_fps', DEFAULT_FPS)
        self.is_gif = cache_data.get('is_gif', False)
        self.gif_frame_delays = cache_data.get('gif_frame_delays', None)
        
        logger.debug(f"  ✓ Cache geladen: {self.total_frames} Frames, {self.fps} FPS")
        return True
    
    def initialize(self):
        """Initialisiert Video-Capture."""
        # NOTE: Cache-Loading wird im Player behandelt (benötigt points_json_path für Cache-Key)
        
        # Schließe alte Capture falls vorhanden
        if self.cap and self.cap.isOpened():
            # Already initialized - but ensure ClipRegistry has total_frames
            if self.clip_id and self.total_frames > 0:
                from .clip_registry import get_clip_registry
                clip_registry = get_clip_registry()
                clip = clip_registry.get_clip(self.clip_id)
                if clip and clip.get('total_frames') is None:
                    clip['total_frames'] = self.total_frames
                    logger.debug(f"  ✓ Updated ClipRegistry (already init): clip_id={self.clip_id}, total_frames={self.total_frames}")
            return True  # Bereits initialisiert
        
        if not os.path.exists(self.video_path):
            logger.error(f"Video nicht gefunden: {self.video_path}")
            return False
        
        # Force FFmpeg backend for HAP codec support
        # MSMF doesn't support HAP, so we must use FFmpeg
        logger.debug(f"Opening video with FFmpeg backend: {self.video_path}")
        self.cap = cv2.VideoCapture(self.video_path, cv2.CAP_FFMPEG)
        
        if not self.cap.isOpened():
            logger.error(f"Video konnte nicht geöffnet werden: {self.video_path}")
            logger.error(f"  Path: {self.video_path}")
            logger.error(f"  File exists: {os.path.exists(self.video_path)}")
            logger.error(f"  Tried backend: CAP_FFMPEG")
            return False
        
        logger.debug(f"  ✓ Video opened successfully with FFmpeg backend")
        
        # Video-Informationen
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Update ClipRegistry with total_frames if clip_id is set
        if self.clip_id:
            from .clip_registry import get_clip_registry
            clip_registry = get_clip_registry()
            clip = clip_registry.get_clip(self.clip_id)
            if clip:
                clip['total_frames'] = self.total_frames
                logger.debug(f"  ✓ Updated ClipRegistry: clip_id={self.clip_id}, total_frames={self.total_frames}")
        
        # GIF Frame-Delays laden
        if self.is_gif and self.gif_respect_timing:
            self.gif_frame_delays = self._load_gif_frame_delays()
        
        logger.debug(f"VideoSource initialisiert:")
        logger.debug(f"  Video: {os.path.basename(self.video_path)}")
        logger.debug(f"  Auflösung: {original_width}x{original_height} → {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  FPS: {self.fps}, Frames: {self.total_frames}")
        
        return True
    
    def get_next_frame(self):
        """Gibt nächstes Video-Frame zurück."""
        if not self.cap or not self.cap.isOpened():
            return None, 0
        
        # Check trim boundaries BEFORE reading frame
        effective_in = self.in_point if self.in_point is not None else 0
        effective_out = self.out_point if self.out_point is not None else self.total_frames - 1
        
        # Determine which frame to read
        if not self.reverse:
            # Forward playback
            actual_frame = self.current_frame
            
            # Check if we've reached out_point
            if actual_frame > effective_out:
                return None, 0  # End of trimmed clip
        else:
            # Reverse playback: play from out_point down to in_point
            # current_frame counts up (0, 1, 2...) but we read backwards
            playback_position = self.current_frame - effective_in
            actual_frame = effective_out - playback_position
            
            # Check if we've gone before in_point
            if actual_frame < effective_in:
                return None, 0  # End of trimmed clip (in reverse)
        
        # CRITICAL: Lock BOTH seek and read for HAP codec thread-safety
        # HAP codec has internal threading that can cause race conditions
        with self._lock:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, actual_frame)
            ret, frame = self.cap.read()
        
        if not ret:
            return None, 0  # End of video
        
        # BGR zu RGB konvertieren
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Transparenz verarbeiten (GIF)
        if self.is_gif:
            frame = self._process_frame_transparency(frame)
        
        # Auf Canvas-Größe skalieren
        if frame.shape[1] != self.canvas_width or frame.shape[0] != self.canvas_height:
            frame = cv2.resize(frame, (self.canvas_width, self.canvas_height), interpolation=cv2.INTER_AREA)
        
        # Frame-Delay berechnen
        delay = self.gif_frame_delays[self.current_frame] if (self.is_gif and self.gif_frame_delays and self.current_frame < len(self.gif_frame_delays)) else (1.0 / self.fps)
        
        self.current_frame += 1
        return frame, delay
    
    def reload_trim_settings(self):
        """
        DEPRECATED: Use Transport Effect Plugin instead.
        Lädt Trim-Einstellungen aus ClipRegistry neu.
        """
        if self.clip_id:
            from .clip_registry import get_clip_registry
            clip_registry = get_clip_registry()
            playback_info = clip_registry.get_clip_playback_info(self.clip_id)
            old_current = self.current_frame
            logger.info(f"reload_trim_settings: clip_id={self.clip_id}, current_frame={old_current}, playback_info={playback_info}")
            if playback_info:
                self.in_point = playback_info.get('in_point')
                self.out_point = playback_info.get('out_point')
                self.reverse = playback_info.get('reverse', False)
                logger.info(f"✅ VideoSource trim settings reloaded: in={self.in_point}, out={self.out_point}, reverse={self.reverse}")
                # Reset to appropriate starting position
                self.reset()
                logger.info(f"🔄 VideoSource reset: current_frame {old_current} → {self.current_frame}")
                return True
            else:
                logger.warning(f"⚠️ No playback_info found for clip_id={self.clip_id}")
        else:
            logger.warning(f"⚠️ VideoSource has no clip_id set")
        return False
    
    def reset(self):
        """Setzt Video auf Anfang zurück (oder in_point wenn trimmed)."""
        # Start at in_point if trimming is active, otherwise frame 0
        start_frame = self.in_point if self.in_point is not None else 0
        self.current_frame = start_frame
        
        with self._lock:  # Lock für seek-Operation (non-sequential access)
            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    def cleanup(self):
        """Gibt Video-Ressourcen frei."""
        with self._lock:  # Lock für VideoCapture.release() (kritische Operation)
            if self.cap:
                self.cap.release()
                self.cap = None
    
    def get_source_name(self):
        """Gibt Video-Dateinamen zurück."""
        return os.path.basename(self.video_path) if self.video_path else "Unknown Video"


class ScriptSource(FrameSource):
    """
    ⚠️ DEAD CODE - REMOVE IN FUTURE VERSION ⚠️
    DEPRECATED: Python-Script als Frame-Quelle (prozedural generiert).
    Use GeneratorSource with generator plugins instead.
    
    TODO: Remove ScriptSource class and all references after GeneratorSource migration complete.
    References found in:
    - api_routes.py (register_script_routes)
    - cli_handler.py (load_script command)
    - dmx_controller.py (script loading)
    - rest_api.py (is_script check)
    - __init__.py (export)
    """
    
    def __init__(self, script_name, canvas_width, canvas_height, config=None):
        super().__init__(canvas_width, canvas_height, config)
        self.script_name = script_name
        self.source_path = script_name  # Generischer Pfad für load_points()
        self.source_type = 'script'  # Marker für Transport-Effekt
        self.script_gen = None
        self.start_time = 0
        self.is_infinite = True  # Scripts laufen unendlich
        
        # Lade Script-Generator
        scripts_dir = config.get('paths', {}).get('scripts_dir', 'scripts') if config else 'scripts'
        self.script_gen = ScriptGenerator(scripts_dir)
    
    def initialize(self):
        """Initialisiert Script-Generator."""
        if not self.script_gen.load_script(self.script_name):
            logger.error(f"Script konnte nicht geladen werden: {self.script_name}")
            return False
        
        self.start_time = time.time()
        
        logger.debug(f"ScriptSource initialisiert:")
        logger.debug(f"  Script: {self.script_name}")
        logger.debug(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        
        return True
    
    def get_next_frame(self):
        """Generiert nächstes Frame."""
        if not self.script_gen:
            return None, 0
        
        current_time = time.time() - self.start_time
        
        frame = self.script_gen.generate_frame(
            width=self.canvas_width,
            height=self.canvas_height,
            fps=self.fps,
            frame_number=self.current_frame,
            time=current_time
        )
        
        if frame is None:
            logger.warning("Fehler beim Generieren des Frames")
            return None, 1.0 / self.fps
        
        # Frame ist bereits RGB
        delay = 1.0 / self.fps
        self.current_frame += 1
        
        return frame, delay
    
    def reset(self):
        """Setzt Script zurück."""
        self.current_frame = 0
        self.start_time = time.time()
        
        if self.script_gen:
            self.script_gen.reset()
    
    def cleanup(self):
        """Cleanup für Script."""
        # Script-Generator hat keine speziellen Cleanup-Anforderungen
        pass
    
    def get_source_name(self):
        """Gibt Script-Namen zurück."""
        return self.script_name
    
    def get_info(self):
        """Erweiterte Info mit Script-Details."""
        info = super().get_info()
        
        if self.script_gen:
            script_info = self.script_gen.get_info()
            info.update(script_info)
        
        return info


class GeneratorSource(FrameSource):
    """Plugin-basierter Generator als Frame-Quelle (prozedural generiert)."""
    
    def __init__(self, generator_id, parameters, canvas_width, canvas_height, config=None):
        super().__init__(canvas_width, canvas_height, config)
        self.generator_id = generator_id
        self.parameters = parameters or {}
        self.source_path = f"generator:{generator_id}"  # Generischer Pfad für load_points()
        self.source_type = 'generator'  # Marker für Transport-Effekt
        self.plugin_instance = None
        self.start_time = 0
        self.duration = parameters.get('duration', 30) if parameters else 30  # Duration in seconds
        self.is_infinite = False  # Generators have duration for playlist auto-advance
        
        # Playback control parameters
        self.speed = 1.0
        self.reverse = False
        self.playback_mode = 'repeat'  # 'repeat', 'play_once', 'bounce', 'random'
        
        # Internal playback state
        self._virtual_time = 0.0
        self._last_update = None
        self._bounce_direction = 1
        self._has_played_once = False
        
    def initialize(self):
        """Initialisiert Generator-Plugin."""
        from .plugin_manager import get_plugin_manager
        
        pm = get_plugin_manager()
        
        # Erstelle Plugin-Instanz (load_plugin erstellt neue Instanz mit config)
        logger.info(f"🔧 GeneratorSource initializing: {self.generator_id} with parameters: {self.parameters}")
        self.plugin_instance = pm.load_plugin(self.generator_id, config=self.parameters)
        if not self.plugin_instance:
            logger.error(f"❌ Generator konnte nicht geladen werden: {self.generator_id}")
            return False
        
        self.start_time = time.time()
        
        logger.info(f"✅ GeneratorSource initialisiert:")
        logger.info(f"  Generator: {self.generator_id}")
        logger.info(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        logger.info(f"  Parameters: {self.parameters}")
        logger.info(f"  Plugin instance: {type(self.plugin_instance).__name__}")
        logger.info(f"  Has update_parameter: {hasattr(self.plugin_instance, 'update_parameter')}")
        
        # Apply any parameters that were set before initialization
        # (This handles race condition where frontend sets params before plugin is ready)
        if self.parameters and hasattr(self.plugin_instance, 'update_parameter'):
            logger.info(f"📝 Applying pre-initialization parameters to plugin...")
            for param_name, param_value in self.parameters.items():
                if param_name != 'duration':  # duration is handled separately
                    success = self.plugin_instance.update_parameter(param_name, param_value)
                    if success:
                        logger.debug(f"  ✓ {param_name} = {param_value}")
                    else:
                        logger.debug(f"  ✗ {param_name} = {param_value} (not accepted)")
        
        return True
    
    def get_next_frame(self):
        """Generiert nächstes Frame mit Playback-Control."""
        if not self.plugin_instance:
            return None, 0
        
        # Initialize last_update on first call
        if self._last_update is None:
            self._last_update = time.time()
        
        # Calculate time delta
        now = time.time()
        delta_time = (now - self._last_update) * self.speed
        self._last_update = now
        
        # Apply playback mode logic
        if self.playback_mode == 'random':
            # Random mode: Jump to random position in duration
            self._virtual_time = random.uniform(0, self.duration)
        else:
            # Calculate direction
            direction = -1 if self.reverse else 1
            if self.playback_mode == 'bounce':
                direction *= self._bounce_direction
            
            # Update virtual time
            self._virtual_time += delta_time * direction
            
            # Handle playback mode boundaries
            if self.playback_mode == 'repeat':
                # Loop between 0 and duration
                while self._virtual_time >= self.duration:
                    self._virtual_time -= self.duration
                while self._virtual_time < 0:
                    self._virtual_time += self.duration
            
            elif self.playback_mode == 'play_once':
                # Play once and stop
                if self.reverse:
                    if self._virtual_time < 0:
                        self._virtual_time = 0
                        self._has_played_once = True
                else:
                    if self._virtual_time >= self.duration:
                        self._virtual_time = self.duration
                        self._has_played_once = True
                
                # Check if should advance playlist
                if self._has_played_once:
                    logger.info(f"Generator {self.generator_id} play_once finished, triggering auto-advance")
                    return None, 0
            
            elif self.playback_mode == 'bounce':
                # Bounce between 0 and duration
                if self._virtual_time >= self.duration:
                    self._virtual_time = self.duration - (self._virtual_time - self.duration)
                    self._bounce_direction = -1
                elif self._virtual_time < 0:
                    self._virtual_time = abs(self._virtual_time)
                    self._bounce_direction = 1
        
        # Clamp to valid range
        current_time = max(0, min(self.duration, self._virtual_time))
        
        # Calculate virtual frame number
        virtual_frame = int(current_time * self.fps)
        
        # Generators erzeugen Frames ohne Input (None)
        # Pass time and frame info via kwargs
        frame = self.plugin_instance.process_frame(
            None,
            width=self.canvas_width,
            height=self.canvas_height,
            fps=self.fps,
            frame_number=virtual_frame,
            time=current_time
        )
        
        if frame is None:
            logger.warning(f"Generator {self.generator_id} returned None frame")
            # Return black frame as fallback
            frame = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        
        # Ensure correct size
        if frame.shape[:2] != (self.canvas_height, self.canvas_width):
            frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))
        
        delay = 1.0 / self.fps
        self.current_frame += 1
        
        return frame, delay
    
    def update_parameter(self, param_name, value):
        """Aktualisiert Generator-Parameter zur Laufzeit."""
        # Check if plugin is initialized
        if not self.plugin_instance:
            logger.info(f"📝 Parameter '{param_name}' stored for initialization (plugin not ready yet)")
            # Store in parameters dict for when plugin initializes
            self.parameters[param_name] = value
            # Return True because we've stored it successfully
            return True
        
        # Convert value to correct type if needed
        try:
            value = float(value) if isinstance(value, (str, int, float)) else value
        except (ValueError, TypeError):
            pass
        
        # Always update parameters dict
        self.parameters[param_name] = value
        
        # Special handling for playback control parameters
        if param_name == 'duration':
            self.duration = float(value)
            logger.info(f"Generator duration updated to {self.duration}s")
            return True
        
        elif param_name == 'speed':
            self.speed = float(value)
            logger.info(f"Generator speed updated to {self.speed}x")
            return True
        
        elif param_name == 'reverse':
            self.reverse = bool(value)
            logger.info(f"Generator reverse updated to {self.reverse}")
            return True
        
        elif param_name == 'playback_mode':
            old_mode = self.playback_mode
            self.playback_mode = str(value)
            if old_mode != self.playback_mode:
                # Reset playback state on mode change
                self._bounce_direction = 1
                self._has_played_once = False
                logger.info(f"Generator playback_mode updated to {self.playback_mode}")
            return True
        
        # Use plugin's update_parameter method if available (preferred)
        if self.plugin_instance and hasattr(self.plugin_instance, 'update_parameter'):
            success = self.plugin_instance.update_parameter(param_name, value)
            if success:
                logger.info(f"Generator parameter updated: {param_name} = {value}")
                return True
            else:
                logger.debug(f"Plugin's update_parameter returned False for: {param_name}")
        
        # Fallback: Try to set as attribute directly
        if self.plugin_instance and hasattr(self.plugin_instance, param_name):
            setattr(self.plugin_instance, param_name, value)
            logger.info(f"Generator parameter updated (direct): {param_name} = {value}")
            return True
        
        logger.warning(f"Unknown generator parameter: {param_name} (plugin: {self.generator_id}, has update_parameter: {hasattr(self.plugin_instance, 'update_parameter') if self.plugin_instance else 'No instance'})")
        return False
    
    def reset(self):
        """Setzt Generator zurück."""
        self.current_frame = 0
        self.start_time = time.time()
        self._virtual_time = 0.0
        self._last_update = None
        self._bounce_direction = 1
        self._has_played_once = False
        
        # Re-initialize plugin if needed
        if self.plugin_instance:
            # Most generators don't need explicit reset
            pass
    
    def cleanup(self):
        """Cleanup für Generator."""
        if self.plugin_instance:
            if hasattr(self.plugin_instance, 'cleanup'):
                self.plugin_instance.cleanup()
            self.plugin_instance = None
    
    def get_source_name(self):
        """Gibt Generator-Namen zurück."""
        if self.plugin_instance and hasattr(self.plugin_instance, 'METADATA'):
            return self.plugin_instance.METADATA.get('name', self.generator_id)
        return self.generator_id
    
    def get_info(self):
        """Erweiterte Info mit Generator-Details."""
        info = super().get_info()
        info['type'] = 'generator'
        info['generator_id'] = self.generator_id
        info['parameters'] = self.parameters
        
        if self.plugin_instance and hasattr(self.plugin_instance, 'METADATA'):
            metadata = self.plugin_instance.METADATA
            info['generator_name'] = metadata.get('name', self.generator_id)
            info['description'] = metadata.get('description', '')
            info['version'] = metadata.get('version', '1.0.0')
        
        return info


class DummySource(FrameSource):
    """Dummy Source für leere Playlists - zeigt schwarzes Bild."""
    
    def __init__(self, canvas_width, canvas_height):
        super().__init__(canvas_width, canvas_height)
        self.frame = None
        self.fps = 30
        self.total_frames = 0
        self.is_infinite = True
    
    def initialize(self):
        """Erstellt schwarzes Dummy-Frame."""
        self.frame = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        logger.info("Dummy Source initialisiert (leere Playlist)")
        return True
    
    def get_next_frame(self):
        """Gibt schwarzes Frame zurück."""
        if self.frame is None:
            self.initialize()
        return self.frame, 1.0 / self.fps
    
    def reset(self):
        """Nichts zu resetten."""
        pass
    
    def cleanup(self):
        """Nichts zu cleanupen."""
        pass
    
    def get_source_name(self):
        """Source Name."""
        return "Empty Playlist"
    
    def get_info(self):
        """Source Info."""
        info = super().get_info()
        info['type'] = 'dummy'
        info['description'] = 'Waiting for video...'
        return info
