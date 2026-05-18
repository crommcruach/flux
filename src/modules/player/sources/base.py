"""
FrameSource — abstract base class for all frame sources.
"""
from abc import ABC, abstractmethod
from ...core.constants import DEFAULT_FPS


class FrameSource(ABC):
    """Abstract base class for frame sources."""

    def __init__(self, canvas_width, canvas_height, config=None):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.config = config or {}
        self.current_frame = 0
        self.total_frames = 0
        self.fps = DEFAULT_FPS
        self.is_infinite = False  # True for scripts (infinite)

    @abstractmethod
    def initialize(self):
        """Initializes the frame source. Returns True on success."""
        pass

    @abstractmethod
    def get_next_frame(self):
        """
        Returns the next frame as a numpy array (RGB).
        Returns: (frame, delay) tuple
        - frame: numpy array (height, width, 3) in RGB format or None
        - delay: recommended delay until next frame in seconds
        """
        pass

    @abstractmethod
    def reset(self):
        """Resets the source to frame 0."""
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup-Operationen beim Stoppen."""
        pass

    @abstractmethod
    def get_source_name(self):
        """Returns the source name (e.g. filename)."""
        pass

    def get_info(self):
        """Returns information about the source."""
        return {
            'source_type': self.__class__.__name__
        }
