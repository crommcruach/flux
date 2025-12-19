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
        self.clip_id = clip_id
        
        # GIF Support
        self.is_gif = self._is_gif_file(video_path)
        self.gif_frame_delays = None
        self.gif_transparency_bg = tuple(config.get('video', {}).get('gif_transparency_bg', [0, 0, 0]) if config else [0, 0, 0])
        self.gif_respect_timing = config.get('video', {}).get('gif_respect_frame_timing', True) if config else True
        
        # OPTIMIZATION: Loop frame caching (keep decoded frames for short loops)
        self.enable_loop_cache = config.get('performance', {}).get('enable_loop_cache', True) if config else True
        self.loop_cache_max_duration = config.get('performance', {}).get('loop_cache_max_duration', 10.0) if config else 10.0  # seconds
        self.loop_frame_cache = None  # Will store list of decoded frames
        self.loop_cache_active = False
        self.loop_number = 0
    
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
        # Check if RGB cache is enabled in config
        enable_rgb_cache = self.config.get('performance', {}).get('enable_rgb_cache', True) if self.config else True
        if not enable_rgb_cache:
            return False
        
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
        
        # CRITICAL: Lock BOTH seek and read for HAP codec thread-safety
        # HAP codec has internal threading that can cause race conditions
        with self._lock:
            # Double-check cap is still valid after acquiring lock (race condition)
            if not self.cap:
                return None, 0
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
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
    
    def reset(self):
        """Setzt Video auf Anfang zurück."""
        self.current_frame = 0
        
        with self._lock:  # Lock für seek-Operation (non-sequential access)
            if self.cap and self.cap.isOpened():
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    def cleanup(self):
        """Gibt Video-Ressourcen frei."""
        with self._lock:  # Lock für VideoCapture.release() (kritische Operation)
            if self.cap:
                self.cap.release()
                self.cap = None
    
    def get_source_name(self):
        """Gibt Video-Dateinamen zurück."""
        return os.path.basename(self.video_path) if self.video_path else "Unknown Video"


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
        
        # Duration: configurable per generator, max 60s (defined in generator plugin parameters)
        # Transport effect will auto-adjust to this duration
        # Convert to float if it's a string (from ParameterType.STRING)
        duration_value = parameters.get('duration', 10) if parameters else 10
        if isinstance(duration_value, str):
            try:
                duration_value = float(duration_value)
            except (ValueError, TypeError):
                duration_value = 10
        self.duration = min(60, max(1, duration_value))
        self.is_infinite = False  # Generators have fixed duration
        self.total_frames = int(self.duration * self.fps)
        
        logger.debug(f"GeneratorSource: duration={self.duration}s, total_frames={self.total_frames}")
        
        # Simple time tracking for generators (transport plugin handles playback control)
        self.start_time = 0
        
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
        """
        Generates next frame using simple time progression.
        Transport plugin handles speed, reverse, trim, and playback modes.
        """
        if not self.plugin_instance:
            return None, 0
        
        # Use current_frame if set by transport effect, otherwise calculate from time
        # This allows transport to control generator playback (speed, reverse, trim)
        if hasattr(self, 'current_frame') and self.current_frame >= 0:
            virtual_frame = self.current_frame
            current_time = virtual_frame / self.fps
        else:
            # Fallback: Calculate elapsed time since start (no transport control)
            current_time = time.time() - self.start_time
            
            # Calculate frame number from elapsed time
            virtual_frame = int(current_time * self.fps)
            
            # Loop frame number if duration is defined
            if self.total_frames > 0:
                virtual_frame = virtual_frame % self.total_frames
                current_time = virtual_frame / self.fps
        
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
        
        # Special handling for duration parameter (max 60s)
        if param_name == 'duration':
            self.duration = min(60, max(1, float(value)))
            self.total_frames = int(self.duration * self.fps)
            logger.info(f"Generator duration updated to {self.duration}s (total_frames={self.total_frames}, max 60s)")
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
    
    def is_duration_defined(self):
        """
        Check if generator has a defined duration (for master/slave sync compatibility).
        
        Returns:
            bool: True if duration > 0 (finite), False if duration = 0 (infinite)
        """
        return self.duration > 0


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
