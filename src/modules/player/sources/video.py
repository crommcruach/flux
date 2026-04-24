"""
VideoSource — memory-mapped .npy video frames.
"""
import os
import numpy as np
from ...core.logger import get_logger
from ...core.constants import DEFAULT_FPS
from .base import FrameSource

logger = get_logger(__name__)


class VideoSource(FrameSource):
    """Video file as frame source via memory-mapped .npy arrays."""

    def __init__(self, video_path, canvas_width, canvas_height, config=None, clip_id=None, player_name='video'):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = self._find_best_resolution(video_path)
        self.source_path = self.video_path
        self.source_type = 'video'
        self.clip_id = clip_id
        self.player_name = player_name
        self.frames = None       # np.ndarray (heap or memmap) set in initialize()
        self._mmap_ref = None    # always the full memmap — kept alive for retrim()
        self._trim_start = 0     # first frame index of self.frames in full-file coordinates

        # Apply config override for eager-load threshold
        cfg_mb = (config or {}).get('performance', {}).get('eager_load_threshold_mb')
        if cfg_mb is not None:
            self._EAGER_LOAD_THRESHOLD_BYTES = int(cfg_mb) * 1024 * 1024

    def _find_best_resolution(self, path: str) -> str:
        """Resolve clip folder to the best-matching .npy file."""
        if not os.path.isdir(path):
            return path

        from ...content.converter import ALL_PRESETS, get_target_preset
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
            mmap_frames = np.load(self.video_path, mmap_mode='r')
            self.total_frames = mmap_frames.shape[0]
            self._mmap_ref = mmap_frames   # keep a reference so retrim() can re-slice at any time
            self._trim_start = 0

            meta_path = self.video_path[:-4] + '.json'
            if os.path.exists(meta_path):
                import json as _json
                with open(meta_path) as f:
                    meta = _json.load(f)
                self.fps = float(meta.get('fps', DEFAULT_FPS))
            else:
                self.fps = DEFAULT_FPS

            if self.clip_id:
                from ..clips.registry import get_clip_registry
                clip = get_clip_registry().get_clip(self.clip_id)
                if clip:
                    clip['total_frames'] = self.total_frames

            # Eagerly copy small clips into a contiguous RAM array so that
            # get_next_frame() returns heap data.  Memmap views trigger OS page
            # faults inside cv2.cvtColor (source_upload stage) on every frame —
            # ~25 ms on Windows because the working-set pages are evicted between
            # rendered frames even when data is in the page cache.
            # Large clips stay memory-mapped to avoid exhausting RAM.
            # Note: if the Transport effect has a saved trim, it will call retrim()
            # shortly after initialize() to discard out-of-trim frames.
            file_bytes = mmap_frames.nbytes
            if file_bytes <= self._EAGER_LOAD_THRESHOLD_BYTES:
                self.frames = np.ascontiguousarray(mmap_frames)
                logger.debug(
                    f"[NpySource] {os.path.basename(self.video_path)} "
                    f"{self.total_frames} frames @ {self.fps:.1f}fps "
                    f"(eager-loaded {file_bytes // (1024*1024)} MB into RAM)"
                )
            else:
                self.frames = mmap_frames
                logger.debug(
                    f"[NpySource] {os.path.basename(self.video_path)} "
                    f"{self.total_frames} frames @ {self.fps:.1f}fps "
                    f"(memory-mapped — {file_bytes // (1024*1024)} MB > {self._EAGER_LOAD_THRESHOLD_BYTES // (1024*1024)} MB threshold)"
                )
            return True
        except Exception as e:
            logger.error(f"[NpySource] Failed to load {self.video_path}: {e}")
            return False

    # RAM size threshold for eager loading.  Files smaller than this are copied
    # into a contiguous heap array at initialize() time so that get_next_frame()
    # returns plain RAM data instead of a memmap view.
    # Memmap views cause OS page faults on every cv2.cvtColor read in source_upload
    # (~25 ms on Windows for a 1080p frame) because the OS evicts working-set pages
    # between frames even when the data is in the page cache.
    # Clips larger than this threshold stay memory-mapped (only the accessed pages
    # are ever loaded from disk, saving RAM for large/long clips).
    # Configurable via config.json: performance.eager_load_threshold_mb
    _EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024  # 512 MB default (overridden in __init__)

    def get_next_frame(self):
        if self.frames is None or self.current_frame >= self.total_frames:
            return None, 0
        idx = self.current_frame - self._trim_start
        if idx < 0 or idx >= len(self.frames):
            return None, 0
        frame = self.frames[idx]
        self.current_frame += 1
        return frame, 1.0 / self.fps

    def retrim(self, in_point: int, out_point: int) -> None:
        """Discard out-of-trim frames from RAM, keeping only [in_point, out_point].

        The underlying memmap (``_mmap_ref``) is always retained so the range can
        be widened again later without touching the file.  ``total_frames`` stays
        as the full clip length so the Transport's slider keeps its correct scale.

        Call this after Transport sets a non-trivial trim.  On integrated GPUs /
        UMA architectures the freed heap memory is immediately available to the
        rest of the application.
        """
        if self._mmap_ref is None:
            return
        if in_point < 0 or out_point >= self.total_frames or in_point > out_point:
            logger.warning(f"[NpySource] retrim({in_point}, {out_point}) out of range "
                           f"for {self.total_frames}-frame clip — ignored")
            return

        old_bytes = self.frames.nbytes if self.frames is not None else 0
        slice_frames = self._mmap_ref[in_point:out_point + 1]
        slice_bytes = slice_frames.nbytes

        if slice_bytes <= self._EAGER_LOAD_THRESHOLD_BYTES:
            new_frames = np.ascontiguousarray(slice_frames)   # heap copy, page-fault-free
        else:
            new_frames = slice_frames   # leave as memmap — still narrower range

        self.frames = new_frames
        self._trim_start = in_point

        saved_mb = (old_bytes - slice_bytes) // (1024 * 1024)
        logger.info(
            f"[NpySource] retrim [{in_point}–{out_point}] "
            f"{out_point - in_point + 1} of {self.total_frames} frames "
            f"({slice_bytes // (1024*1024)} MB kept"
            + (f", freed ~{saved_mb} MB" if saved_mb > 0 else "")
            + ")"
        )

    def reset(self):
        self.current_frame = 0

    def cleanup(self):
        self.frames = None
        self._mmap_ref = None
        self._trim_start = 0

    def get_source_name(self):
        return os.path.basename(self.video_path) if self.video_path else "Unknown"
