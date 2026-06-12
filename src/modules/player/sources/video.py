"""
VideoSource — HAP-compressed .hap video frames.

Zero-copy per-frame: DXT blocks move from RAM → GPU without CPU decompression.

    buffer[idx * fbs : (idx+1) * fbs]   ← numpy slice (view, zero-copy)
            ↓
    memoryview(slice)                    ← zero-copy buffer protocol wrapper
            ↓
    wgpu write_texture(bc1-rgba-unorm)   ← single C-level memcpy into D3D12
            ↓
    GPU DMA: upload heap → VRAM          ← hardware DMA, no CPU involved
            ↓
    GPU samples bc1 texture              ← hardware decompresses, free

NOTE: .npy clips are no longer supported. Re-convert with the Video Converter.
"""
import os
import json
import numpy as np
from ...core.logger import get_logger
from ...core.constants import DEFAULT_FPS
from .base import FrameSource

logger = get_logger(__name__)


class VideoSource(FrameSource):
    """Video source backed by DXT-compressed .hap flat binary.

    get_next_frame() returns (memoryview, frame_duration) — a zero-copy view
    into the DXT data.  The compositor detects memoryview and uses a BC1/BC3
    texture upload path instead of the rgba8unorm numpy path.
    """

    # RAM threshold for eager-loading.  Files below this are copied to
    # contiguous heap at initialize() to avoid OS page-fault stalls (~25 ms)
    # on memmap reads between frames.  Configurable via
    # config.performance.eager_load_threshold_mb.
    _EAGER_LOAD_THRESHOLD_BYTES = 512 * 1024 * 1024  # 512 MB

    def __init__(self, video_path, canvas_width, canvas_height, config=None,
                 clip_id=None, player_name='video'):
        super().__init__(canvas_width, canvas_height, config)
        self.video_path = self._find_best_resolution(video_path)
        self.source_path = self.video_path
        self.source_type = 'video'
        self.clip_id = clip_id
        self.player_name = player_name

        # Set in initialize():
        self.buffer = None       # contiguous heap or memmap uint8 flat array
        self._mmap_ref = None    # always the full memmap — kept alive for retrim()
        self._trim_start = 0     # frame index offset into the full file

        # HAP metadata (set in initialize()):
        self.width = 0
        self.height = 0
        self.dxt_variant = 'bc1'   # 'bc1' (RGB) or 'bc3' (RGBA)
        self.frame_bytes = 0

        cfg_mb = (config or {}).get('performance', {}).get('eager_load_threshold_mb')
        if cfg_mb is not None:
            self._EAGER_LOAD_THRESHOLD_BYTES = int(cfg_mb) * 1024 * 1024

    def _find_best_resolution(self, path: str) -> str:
        """Resolve clip folder to the best-matching .hap file."""
        if not os.path.isdir(path):
            return path

        from ...content.converter import ALL_PRESETS, get_target_preset
        target = get_target_preset(self.canvas_width, self.canvas_height)
        start_idx = ALL_PRESETS.index(target)
        ordered = ALL_PRESETS[start_idx:] + ALL_PRESETS[:start_idx][::-1]

        for preset in ordered:
            candidate = os.path.join(path, f"{preset}.hap")
            sidecar = os.path.join(path, f"{preset}.json")
            if os.path.exists(candidate) and os.path.exists(sidecar):
                logger.debug(f"[HapSource] {os.path.basename(path)} -> {preset}.hap")
                return candidate

        logger.error(
            f"[HapSource] No .hap found in clip folder: {path}. "
            f"Re-convert your clips with the Video Converter (HAP_NPY format)."
        )
        return path

    def initialize(self):
        if self.buffer is not None:
            return True

        if not os.path.exists(self.video_path):
            logger.error(f"[HapSource] File not found: {self.video_path}")
            return False

        if not self.video_path.endswith('.hap'):
            logger.error(
                f"[HapSource] Not a .hap file: {self.video_path}. "
                f"Re-convert your clip to HAP_NPY format using the Video Converter."
            )
            return False

        try:
            meta_path = self.video_path[:-4] + '.json'  # strip '.hap', add '.json'
            if not os.path.exists(meta_path):
                logger.error(f"[HapSource] Sidecar JSON not found: {meta_path}")
                return False

            with open(meta_path) as f:
                meta = json.load(f)

            self.fps = float(meta.get('fps', DEFAULT_FPS))
            self.total_frames = int(meta['frame_count'])
            self.width = int(meta['width'])
            self.height = int(meta['height'])
            self.dxt_variant = meta.get('dxt_variant', 'bc1')
            self.frame_bytes = int(meta['frame_bytes'])

            if self.clip_id:
                from ..clips.registry import get_clip_registry
                clip = get_clip_registry().get_clip(self.clip_id)
                if clip:
                    clip['total_frames'] = self.total_frames

            # Memory-map the flat binary (all frames concatenated end-to-end)
            mmap_flat = np.memmap(self.video_path, dtype=np.uint8, mode='r')
            self._mmap_ref = mmap_flat
            self._trim_start = 0

            file_bytes = mmap_flat.nbytes
            if file_bytes <= self._EAGER_LOAD_THRESHOLD_BYTES:
                # Eager-copy into contiguous heap RAM.  Avoids OS page-fault
                # stalls (~25 ms on Windows) when reading memmap pages that
                # were evicted between frames.  One-time cost at load time.
                self.buffer = np.ascontiguousarray(mmap_flat)
                logger.debug(
                    f"[HapSource] {os.path.basename(self.video_path)} "
                    f"{self.total_frames}fr @ {self.fps:.1f}fps "
                    f"{self.width}x{self.height} {self.dxt_variant.upper()} "
                    f"(eager {file_bytes // (1024*1024)} MB)"
                )
            else:
                self.buffer = mmap_flat
                logger.debug(
                    f"[HapSource] {os.path.basename(self.video_path)} "
                    f"{self.total_frames}fr @ {self.fps:.1f}fps "
                    f"{self.width}x{self.height} {self.dxt_variant.upper()} "
                    f"(mmap {file_bytes // (1024*1024)} MB, "
                    f">{self._EAGER_LOAD_THRESHOLD_BYTES // (1024*1024)} MB threshold)"
                )
            return True
        except Exception as e:
            logger.error(f"[HapSource] Failed to load {self.video_path}: {e}")
            return False

    def get_next_frame(self):
        """Return (memoryview, frame_duration) — zero-copy DXT slice."""
        if self.buffer is None or self.current_frame >= self.total_frames:
            return None, 0
        idx = self.current_frame - self._trim_start
        buf_frames = len(self.buffer) // self.frame_bytes
        if idx < 0 or idx >= buf_frames:
            return None, 0
        start = idx * self.frame_bytes
        dxt_slice = self.buffer[start:start + self.frame_bytes]
        self.current_frame += 1
        # memoryview is zero-copy: no heap allocation per frame
        return memoryview(dxt_slice), 1.0 / self.fps

    def retrim(self, in_point: int, out_point: int) -> None:
        """Narrow the active frame range to [in_point, out_point].

        _mmap_ref keeps the full file alive so retrim() can widen the range
        again without touching the file.  total_frames stays at the full clip
        length so Transport sliders keep their correct scale.
        """
        if self._mmap_ref is None:
            return
        if in_point < 0 or out_point >= self.total_frames or in_point > out_point:
            logger.warning(
                f"[HapSource] retrim({in_point}, {out_point}) out of range "
                f"for {self.total_frames}-frame clip — ignored"
            )
            return

        old_bytes = len(self.buffer) if self.buffer is not None else 0
        start_byte = in_point * self.frame_bytes
        end_byte = (out_point + 1) * self.frame_bytes
        slice_bytes = end_byte - start_byte

        slice_buf = self._mmap_ref[start_byte:end_byte]
        if slice_bytes <= self._EAGER_LOAD_THRESHOLD_BYTES:
            new_buffer = np.ascontiguousarray(slice_buf)
        else:
            new_buffer = slice_buf

        self.buffer = new_buffer
        self._trim_start = in_point

        saved_mb = (old_bytes - slice_bytes) // (1024 * 1024)
        logger.debug(
            f"[HapSource] retrim [{in_point}–{out_point}] "
            f"{out_point - in_point + 1} of {self.total_frames} frames"
            + (f", freed ~{saved_mb} MB" if saved_mb > 0 else "")
        )

    def reset(self):
        self.current_frame = self._trim_start

    def cleanup(self):
        self.buffer = None
        self._mmap_ref = None
        self._trim_start = 0

    def get_source_name(self):
        return os.path.basename(self.video_path) if self.video_path else "Unknown"
