"""
TapRegistry — per-frame storage for tap outputs with RT pinning (spec §8.8).

The registry holds strong references to every GPUFrame it stores, preventing
TexturePool from reclaiming them until clear() is called at the start of
the *next* frame.

Thread-safety: NOT thread-safe.  Must be used exclusively on the GL thread
(same constraint as GPUFrame itself).
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Union

from ...core.logger import get_logger

if TYPE_CHECKING:
    from ...gpu.frame import GPUFrame

logger = get_logger(__name__)


class TapRegistry:
    """
    Maps tap_id → GPUFrame | list[GPUFrame] for the current frame.

    Lifecycle per frame::

        registry.clear()                          # start of frame, release last frame's RTs
        registry.register('my_tap', gpu_frame)   # called by compositor hooks
        result = registry.get('my_tap')          # called by OutputManager / SliceManager
        # ... frame rendered and dispatched
        # Next frame: clear() releases all held RTs
    """

    def __init__(self):
        self._entries: Dict[str, Union['GPUFrame', List['GPUFrame']]] = {}
        # Separate list so register() can accept GPUFrames that map to multiple taps
        self._pinned: List['GPUFrame'] = []

    # ------------------------------------------------------------------
    # Write path
    # ------------------------------------------------------------------

    def register(
        self,
        tap_id: str,
        frame: Union['GPUFrame', List['GPUFrame']],
    ) -> None:
        """
        Store a tap result and pin its GPUFrame(s) against pool reclaim.

        frame must already be a pooled GPUFrame acquired by the caller — the
        registry takes ownership (do NOT release it yourself after calling
        register).
        """
        if isinstance(frame, list):
            self._entries[tap_id] = frame
            for f in frame:
                if f not in self._pinned:
                    self._pinned.append(f)
        else:
            self._entries[tap_id] = frame
            if frame not in self._pinned:
                self._pinned.append(frame)

    def append_to_list(self, tap_id: str, frame: 'GPUFrame') -> None:
        """
        Append a GPUFrame to an existing list-valued tap, or start a new list.

        Used for 'separate' mode multi-layer taps where layers arrive one by one.
        """
        existing = self._entries.get(tap_id)
        if isinstance(existing, list):
            existing.append(frame)
        else:
            self._entries[tap_id] = [frame]
        if frame not in self._pinned:
            self._pinned.append(frame)

    # ------------------------------------------------------------------
    # Read path
    # ------------------------------------------------------------------

    def get(
        self, tap_id: str
    ) -> Optional[Union['GPUFrame', List['GPUFrame']]]:
        """Return the tap output, or None if not yet captured this frame."""
        return self._entries.get(tap_id)

    def tap_ids(self) -> List[str]:
        """All registered tap IDs for the current frame."""
        return list(self._entries.keys())

    # ------------------------------------------------------------------
    # Frame boundary
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """
        Release all pinned GPUFrames back to TexturePool and reset state.

        Must be called at the start of each frame, before any tap captures.
        """
        from ...gpu.texture_pool import get_texture_pool
        pool = get_texture_pool()
        released = 0
        for f in self._pinned:
            try:
                pool.release(f)
                released += 1
            except Exception as e:
                logger.warning(f"TapRegistry.clear: pool.release error: {e}")
        if released:
            logger.debug(f"TapRegistry: released {released} pinned RTs")
        self._pinned.clear()
        self._entries.clear()

    def __len__(self) -> int:
        return len(self._entries)

    def __repr__(self) -> str:
        return f"TapRegistry({list(self._entries.keys())})"
