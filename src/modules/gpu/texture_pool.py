"""
TexturePool — reusable GPU texture/FBO allocation.

One pool per player (or one global pool).
Zero per-frame GPU memory allocation after warmup.

Usage:
    pool = get_texture_pool()
    composite = pool.acquire(1920, 1080)
    layer_tex = pool.acquire(1920, 1080, components=4)   # BGRA
    ...
    pool.release(layer_tex)
    ...
    # composite returned to pool by composite_layers caller via pool.release(composite)
"""
import moderngl
from .frame import GPUFrame
from .context import get_context
from ..core.logger import get_logger

logger = get_logger(__name__)


class TexturePool:
    """
    Resolution-keyed pool of GPUFrame objects.
    Acquire before use, release after — zero allocation per frame after warmup.
    """

    def __init__(self, ctx: moderngl.Context):
        self._ctx = ctx
        # (width, height, components) → list[GPUFrame]
        self._pool: dict[tuple, list[GPUFrame]] = {}
        self._in_use: set[int] = set()      # id() of frames currently acquired

    def acquire(self, width: int, height: int, components: int = 3) -> GPUFrame:
        """
        Return a free GPUFrame for the given resolution / component count.
        Creates a new one if none are available.
        """
        key = (width, height, components)
        pool = self._pool.setdefault(key, [])
        for frame in pool:
            if id(frame) not in self._in_use:
                self._in_use.add(id(frame))
                return frame
        # Allocate new frame
        frame = GPUFrame(self._ctx, width, height, components)
        pool.append(frame)
        self._in_use.add(id(frame))
        logger.debug(f"TexturePool: new GPUFrame {width}x{height} c={components} "
                     f"(pool size now {len(pool)})")
        return frame

    def release(self, frame: GPUFrame) -> None:
        """Mark a frame as available for reuse."""
        self._in_use.discard(id(frame))

    def warmup(self, width: int, height: int, count: int = 4,
               components: int = 3) -> None:
        """
        Pre-allocate N frames at startup to avoid first-frame GPU allocation latency.
        """
        frames = [self.acquire(width, height, components) for _ in range(count)]
        for f in frames:
            self.release(f)
        logger.debug(f"TexturePool: warmed up {count} frames at {width}x{height} c={components}")

    def release_all(self) -> None:
        """Release all GL resources (call on shutdown)."""
        for pool in self._pool.values():
            for frame in pool:
                frame.release()
        self._pool.clear()
        self._in_use.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pool: TexturePool | None = None


def get_texture_pool() -> TexturePool:
    global _pool
    if _pool is None:
        _pool = TexturePool(get_context())
    return _pool


def _reset_pool() -> None:
    """Release all pooled textures and discard the singleton for thread recreation."""
    global _pool
    if _pool is not None:
        try:
            _pool.release_all()
        except Exception:
            pass
        _pool = None
