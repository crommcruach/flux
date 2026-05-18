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
    # Maximum GPUFrames per resolution bucket.  When all slots are in-use
    # at this limit, the oldest slot is force-released (pool leak recovery)
    # rather than allocating a new texture and exhausting VRAM.
    MAX_PER_BUCKET = 16

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

            # All frames in this bucket are in-use.
            if len(pool) >= self.MAX_PER_BUCKET:
                # Hard cap hit — a previous frame was never released (leak).
                # Evict the oldest slot from the pool and return a fresh
                # GPUFrame in its place.
                #
                # WHY NOT reuse pool[0] directly:
                #   Returning pool[0] while it is still referenced as `cur`
                #   (or any other active frame) by the compositor would make
                #   two different acquire() callers share the SAME Python
                #   object.  When one uses it as COLOR_TARGET and the other
                #   already has it as RESOURCE in the same render pass,
                #   wgpu raises:
                #     GPUValidationError: conflicting usages —
                #     TextureUses(RESOURCE) vs TextureUses(COLOR_TARGET).
                #
                # By popping pool[0] out of the pool and returning a brand-
                # new GPUFrame, aliasing is impossible.  The evicted frame
                # stays alive (its holder still references it) and will be
                # GC'd once that holder releases it.  VRAM overhead is at
                # most one extra frame per cap-hit event.
                evicted = pool.pop(0)
                self._in_use.discard(id(evicted))
                logger.warning(
                    f"TexturePool: bucket {width}x{height} hit cap "
                    f"({self.MAX_PER_BUCKET}). Force-evicting oldest slot "
                    f"(id={id(evicted):#x}). Check for missing pool.release() calls."
                )
                # Do NOT call evicted.release() — the original holder may
                # still be using the underlying GPU texture.
                frame = GPUFrame(None, width, height, components)
                pool.append(frame)
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
