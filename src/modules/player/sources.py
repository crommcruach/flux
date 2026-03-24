"""
Frame Sources - Abstrakte Basisklasse und Implementierungen für verschiedene Frame-Quellen
"""
import os
import time
import random
import numpy as np
from abc import ABC, abstractmethod
from ..core.logger import get_logger
from ..core.constants import DEFAULT_FPS
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
    """Video file as frame source via memory-mapped .npy arrays."""

    def __init__(self, video_path, canvas_width, canvas_height, config=None, clip_id=None, player_name='video'):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = self._find_best_resolution(video_path)
        self.source_path = self.video_path
        self.source_type = 'video'
        self.clip_id = clip_id
        self.player_name = player_name
        self.frames = None  # np.memmap loaded in initialize()

    def _find_best_resolution(self, path: str) -> str:
        """Resolve clip folder to the best-matching .npy file."""
        if not os.path.isdir(path):
            return path

        from ..content.converter import ALL_PRESETS, get_target_preset
        target = get_target_preset(self.canvas_width, self.canvas_height)
        start_idx = ALL_PRESETS.index(target)
        ordered = ALL_PRESETS[start_idx:] + ALL_PRESETS[:start_idx][::-1]

        for preset in ordered:
            candidate = os.path.join(path, f"{preset}.npy")
            if os.path.exists(candidate):
                logger.debug(f"[NpySource] {os.path.basename(path)} -> {preset}.npy")
                return candidate

        logger.error(f"[NpySource] No .npy found in clip folder: {path}")
        return path

    def initialize(self):
        if self.frames is not None:
            return True

        if not os.path.exists(self.video_path):
            logger.error(f"[NpySource] File not found: {self.video_path}")
            return False

        try:
            self.frames = np.load(self.video_path, mmap_mode='r')
            self.total_frames = self.frames.shape[0]

            meta_path = self.video_path[:-4] + '.json'
            if os.path.exists(meta_path):
                import json as _json
                with open(meta_path) as f:
                    meta = _json.load(f)
                self.fps = float(meta.get('fps', DEFAULT_FPS))
            else:
                self.fps = DEFAULT_FPS

            if self.clip_id:
                from .clips.registry import get_clip_registry
                clip = get_clip_registry().get_clip(self.clip_id)
                if clip:
                    clip['total_frames'] = self.total_frames

            logger.info(
                f"[NpySource] {os.path.basename(self.video_path)} "
                f"{self.total_frames} frames @ {self.fps:.1f}fps"
            )
            return True
        except Exception as e:
            logger.error(f"[NpySource] Failed to load {self.video_path}: {e}")
            return False

    def get_next_frame(self):
        if self.frames is None or self.current_frame >= self.total_frames:
            return None, 0
        # Return a read-only view directly from the memmap — no upfront 6 MB copy.
        # Effects that create a new output array (transform, resize, etc.) benefit
        # immediately: they only read the pixels they actually need.
        # The core play-loop ensures writability before any in-place mutation.
        frame = self.frames[self.current_frame]
        self.current_frame += 1
        return frame, 1.0 / self.fps

    def reset(self):
        self.current_frame = 0

    def cleanup(self):
        self.frames = None

    def get_source_name(self):
        return os.path.basename(self.video_path) if self.video_path else "Unknown"


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
        # Calculate total_frames: for 10s @ 30fps = 300 frames (0-299)
        # Match VideoSource behavior (CAP_PROP_FRAME_COUNT returns total, not last index)
        self.total_frames = int(self.duration * self.fps)
        
        logger.debug(f"GeneratorSource: duration={self.duration}s, total_frames={self.total_frames} (frames 0-{self.total_frames-1})")
        
        # Simple time tracking for generators (transport plugin handles playback control)
        self.start_time = 0
        
    def initialize(self):
        """Initialisiert Generator-Plugin."""
        from ..plugins.manager import get_plugin_manager
        
        pm = get_plugin_manager()
        
        # Erstelle Plugin-Instanz (load_plugin erstellt neue Instanz mit config)
        logger.debug(f"🔧 GeneratorSource initializing: {self.generator_id} with parameters: {self.parameters}")
        self.plugin_instance = pm.load_plugin(self.generator_id, config=self.parameters)
        if not self.plugin_instance:
            logger.error(f"❌ Generator konnte nicht geladen werden: {self.generator_id}")
            return False
        
        self.start_time = time.time()
        
        logger.debug(f"✅ GeneratorSource initialisiert:")
        logger.debug(f"  Generator: {self.generator_id}")
        logger.debug(f"  Canvas: {self.canvas_width}x{self.canvas_height}")
        logger.debug(f"  Parameters: {self.parameters}")
        logger.debug(f"  Plugin instance: {type(self.plugin_instance).__name__}")
        logger.debug(f"  Has update_parameter: {hasattr(self.plugin_instance, 'update_parameter')}")
        
        # Apply any parameters that were set before initialization
        # (This handles race condition where frontend sets params before plugin is ready)
        if self.parameters and hasattr(self.plugin_instance, 'update_parameter'):
            logger.debug(f"📝 Applying pre-initialization parameters to plugin...")
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
            # Only log once to avoid spamming in 60Hz loop
            if not hasattr(self, '_warned_none_frame'):
                logger.warning(f"Generator {self.generator_id} returned None frame")
                self._warned_none_frame = True
            # Return black frame as fallback
            frame = np.zeros((self.canvas_height, self.canvas_width, 3), dtype=np.uint8)
        
        # Ensure correct size
        if frame.shape[:2] != (self.canvas_height, self.canvas_width):
            from ..gpu.accelerator import get_gpu_accelerator
            frame = get_gpu_accelerator(self.config).resize(frame, (self.canvas_width, self.canvas_height))
        
        delay = 1.0 / self.fps
        self.current_frame += 1
        
        return frame, delay
    
    def update_parameter(self, param_name, value):
        """Aktualisiert Generator-Parameter zur Laufzeit."""
        # Check if plugin is initialized
        if not self.plugin_instance:
            logger.debug(f"📝 Parameter '{param_name}' stored for initialization (plugin not ready yet)")
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
            logger.debug(f"Generator duration updated to {self.duration}s (total_frames={self.total_frames}, max 60s)")
            return True
        
        # Use plugin's update_parameter method if available (preferred)
        if self.plugin_instance and hasattr(self.plugin_instance, 'update_parameter'):
            success = self.plugin_instance.update_parameter(param_name, value)
            if success:
                logger.debug(f"Generator parameter updated: {param_name} = {value}")
                return True
            else:
                logger.debug(f"Plugin's update_parameter returned False for: {param_name}")
        
        # Fallback: Try to set as attribute directly
        if self.plugin_instance and hasattr(self.plugin_instance, param_name):
            setattr(self.plugin_instance, param_name, value)
            logger.debug(f"Generator parameter updated (direct): {param_name} = {value}")
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
        logger.debug("Dummy Source initialisiert (leere Playlist)")
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
