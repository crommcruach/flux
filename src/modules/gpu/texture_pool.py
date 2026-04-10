"""
TexturePool — reusable GPU texture allocation.

Resolution-keyed pool of GPUFrame objects.
Acquire before use, release after — zero allocation per frame after warmup.
Thread-safe via internal lock (wgpu device is thread-safe itself).
"""
import threading
from .frame import GPUFrame
from ..core.logger import get_logger

logger = get_logger(__name__)


class TexturePool:
    def __init__(self):
        # (width, height, components) → list[GPUFrame]
        self._pool: dict[tuple, list[GPUFrame]] = {}
        self._in_use: set[int] = set()
        self._lock = threading.Lock()

    def acquire(self, width: int, height: int, components: int = 3) -> GPUFrame:
        key = (width, height, components)
        with self._lock:
            pool_exists = key in self._pool
            pool = self._pool.setdefault(key, [])

            # On first acquire for a NEW resolution, evict idle frames from all
            # other buckets.  Prevents VRAM growth when canvas resolution changes
            # mid-session (old frames are never acquired again but stay allocated).
            if not pool_exists and len(self._pool) > 1:
                for stale_key in list(self._pool.keys()):
                    if stale_key == key:
                        continue
                    stale = self._pool[stale_key]
                    idle = [f for f in stale if id(f) not in self._in_use]
                    for frame in idle:
                        try:
                            frame.release()
                        except Exception:
                            pass
                        stale.remove(frame)
                    if not stale:
                        del self._pool[stale_key]

            for frame in pool:
                if id(frame) not in self._in_use:
                    self._in_use.add(id(frame))
                    return frame
            frame = GPUFrame(None, width, height, components)
            pool.append(frame)
            self._in_use.add(id(frame))
            logger.debug(f"TexturePool: new GPUFrame {width}x{height} "
                         f"(pool size now {len(pool)})")
            return frame

    def release(self, frame: GPUFrame) -> None:
        if frame is None:
            return
        with self._lock:
            self._in_use.discard(id(frame))

    def warmup(self, width: int, height: int, count: int = 4,
               components: int = 3) -> None:
        frames = [self.acquire(width, height, components) for _ in range(count)]
        for f in frames:
            self.release(f)
        logger.debug(f"TexturePool: warmed up {count} frames at {width}x{height}")

    def release_all(self) -> None:
        with self._lock:
            for pool in self._pool.values():
                for frame in pool:
                    try:
                        frame.release()
                    except Exception:
                        pass
            self._pool.clear()
            self._in_use.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pool: TexturePool | None = None


def get_texture_pool() -> TexturePool:
    global _pool
    if _pool is None:
        _pool = TexturePool()
    return _pool


def _reset_pool() -> None:
    global _pool
    if _pool is not None:
        try:
            _pool.release_all()
        except Exception:
            pass
        _pool = None
