"""
Frame Sources - Abstrakte Basisklasse und Implementierungen für verschiedene Frame-Quellen
"""
import os
import time
import cv2
import numpy as np
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
    
    def __init__(self, video_path, canvas_width, canvas_height, config=None):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = video_path
        self.source_path = video_path  # Generischer Pfad für load_points()
        self.cap = None
        
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
            return True  # Bereits initialisiert
        
        if not os.path.exists(self.video_path):
            logger.error(f"Video nicht gefunden: {self.video_path}")
            return False
        
        self.cap = cv2.VideoCapture(self.video_path)
        
        if not self.cap.isOpened():
            logger.error(f"Video konnte nicht geöffnet werden: {self.video_path}")
            return False
        
        # Hardware-Beschleunigung
        try:
            self.cap.set(cv2.CAP_PROP_HW_ACCELERATION, cv2.VIDEO_ACCELERATION_ANY)
            hw_accel = self.cap.get(cv2.CAP_PROP_HW_ACCELERATION)
            if hw_accel > 0:
                logger.debug(f"  ✓ Hardware-Beschleunigung aktiv (Type: {int(hw_accel)})")
        except Exception as e:
            logger.debug(f"  ⚠ Hardware-Beschleunigung nicht verfügbar: {e}")
        
        # Video-Informationen
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        original_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        original_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
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
        # Cache-System wurde entfernt - nur noch Live-Modus
        if not self.cap or not self.cap.isOpened():
            return None, 0
        
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
        
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    
    def cleanup(self):
        """Gibt Video-Ressourcen frei."""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def get_source_name(self):
        """Gibt Video-Dateinamen zurück."""
        return os.path.basename(self.video_path) if self.video_path else "Unknown Video"


class ScriptSource(FrameSource):
    """Python-Script als Frame-Quelle (prozedural generiert)."""
    
    def __init__(self, script_name, canvas_width, canvas_height, config=None):
        super().__init__(canvas_width, canvas_height, config)
        self.script_name = script_name
        self.source_path = script_name  # Generischer Pfad für load_points()
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
