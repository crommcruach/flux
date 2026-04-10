"""
FrameSource — abstract base class for all frame sources.
"""
from abc import ABC, abstractmethod
from ...core.constants import DEFAULT_FPS


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
