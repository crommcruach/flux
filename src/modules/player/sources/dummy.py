"""
DummySource — black-frame placeholder for empty playlists.
"""
import numpy as np
from ...core.logger import get_logger
from .base import FrameSource

logger = get_logger(__name__)


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
        pass

    def cleanup(self):
        pass

    def get_source_name(self):
        return "Empty Playlist"

    def get_info(self):
        info = super().get_info()
        info['type'] = 'dummy'
        info['description'] = 'Waiting for video...'
        return info
