"""
Video Converter — HAP_NPY format only.

Converts source videos to DXT-compressed .hap flat binaries for zero-copy
GPU playback.  Each frame is BC1 (RGB) or BC3 (RGBA) compressed by imagecodecs
(libsquish/libdxt backend, ~2-5 ms per 1080p frame).

Output layout per clip:
    clips/<name>/
        original.mov          <- preserved source
        720p.hap              <- flat: frame0_dxt | frame1_dxt | ...
        720p.json             <- metadata: fps, frame_count, width, height, dxt_variant, frame_bytes
        1080p.hap
        1080p.json
        ...
        conversion_state.json <- per-preset progress (in_progress / done / failed)

Custom resolutions are also supported.  Dimensions are silently rounded up to
the nearest multiple of 4 (required for BC block-compressed textures).
"""

import os
import json
import shutil
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Resolution presets
# ---------------------------------------------------------------------------

RESOLUTION_PRESETS: Dict[str, Tuple[int, int]] = {
    '720p':  (1280, 720),
    '1080p': (1920, 1080),
    '1440p': (2560, 1440),
    '2160p': (3840, 2160),
}

ALL_PRESETS = ['720p', '1080p', '1440p', '2160p']

# State file stored inside each clip folder
JOB_STATE_FILE = 'conversion_state.json'

logger = logging.getLogger(__name__)


def get_target_preset(player_width: int, player_height: int) -> str:
    """Return the smallest preset whose dimensions cover the player resolution."""
    for preset in ALL_PRESETS:
        w, h = RESOLUTION_PRESETS[preset]
        if w >= player_width and h >= player_height:
            return preset
    return '2160p'


def _align4(v: int) -> int:
    """Round up to the nearest multiple of 4 (required for BC textures)."""
    return (v + 3) & ~3


def _scale_frame_fit(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Scale frame to fit target_w x target_h with letterbox (no crop, no distortion)."""
    fh, fw = frame.shape[:2]
    if fw == target_w and fh == target_h:
        return frame
    scale = min(target_w / fw, target_h / fh)
    new_w = int(fw * scale)
    new_h = int(fh * scale)
    scaled = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
    if new_w == target_w and new_h == target_h:
        return scaled
    result = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    result[y:y + new_h, x:x + new_w] = scaled
    return result


# ---------------------------------------------------------------------------
# Output format enum
# ---------------------------------------------------------------------------

class OutputFormat(Enum):
    HAP_NPY = "hap_npy"   # DXT-compressed .hap (internal format)


# ---------------------------------------------------------------------------
# Conversion result
# ---------------------------------------------------------------------------

@dataclass
class ConversionResult:
    success: bool
    input_path: str
    output_path: str
    error: Optional[str] = None
    duration: float = 0.0
    input_size_mb: float = 0.0
    output_size_mb: float = 0.0
    compression_ratio: float = 0.0


# ---------------------------------------------------------------------------
# VideoConverter
# ---------------------------------------------------------------------------

class VideoConverter:
    """Convert source videos to DXT-compressed .hap files for HAP playback."""

    def __init__(self) -> None:
        self._check_dependencies()

    # ------------------------------------------------------------------
    # Dependency check
    # ------------------------------------------------------------------

    def _check_dependencies(self) -> None:
        """Verify FFmpeg CLI and PyAV are available."""
        if not hasattr(cv2, 'VideoCapture'):
            raise RuntimeError("OpenCV VideoCapture not available")

        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(
                "ffmpeg not found in PATH. "
                "Install with: winget install Gyan.FFmpeg"
            )

        try:
            import av  # noqa: F401
        except ImportError:
            raise RuntimeError("PyAV not installed. Install with: pip install av")

    # ------------------------------------------------------------------
    # Video info (used by API)
    # ------------------------------------------------------------------

    def get_video_info(self, video_path: str) -> Dict:
        """Return basic metadata for a video file via OpenCV."""
        cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")
        try:
            fps_raw = cap.get(cv2.CAP_PROP_FPS)
            fps = fps_raw if fps_raw > 0 else 25.0
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0.0
            size_bytes = os.path.getsize(video_path) if os.path.exists(video_path) else 0
            return {
                "width": width,
                "height": height,
                "fps": fps,
                "frame_count": frame_count,
                "duration": duration,
                "size_bytes": size_bytes,
            }
        finally:
            cap.release()

    # ------------------------------------------------------------------
    # Internal: DXT conversion for one preset
    # ------------------------------------------------------------------

    def _hap_convert_preset(
        self,
        input_path: str,
        clip_folder: str,
        preset: str,
        dxt_variant: str = 'bc1',
        custom_resolution: Optional[Tuple[int, int]] = None,
    ) -> ConversionResult:
        """Encode to HAP via FFmpeg, extract raw DXT blocks via PyAV, write .hap.

        FFmpeg encodes with the HAP codec (DXT1/BC1 for 'bc1', DXT5/BC3 for 'bc3')
        to a temporary .mov.  PyAV demuxes the HAP packets — each packet is a
        4-byte HAP section header followed by raw DXT data — which are written
        directly to the flat .hap binary.
        """
        import subprocess
        import tempfile
        import av

        t0 = time.perf_counter()

        if custom_resolution is not None:
            target_w, target_h = custom_resolution
        else:
            target_w, target_h = RESOLUTION_PRESETS[preset]

        target_w = _align4(target_w)
        target_h = _align4(target_h)

        output_hap = os.path.join(clip_folder, f"{preset}.hap")
        output_meta = os.path.join(clip_folder, f"{preset}.json")

        bpb = 8 if dxt_variant == 'bc1' else 16
        frame_bytes = (target_w // 4) * (target_h // 4) * bpb

        # FFmpeg HAP format name: 'hap' → DXT1/BC1, 'hap_alpha' → DXT5/BC3
        hap_format = 'hap' if dxt_variant == 'bc1' else 'hap_alpha'

        # Scale + letterbox to exact target dimensions
        vf = (
            f"scale={target_w}:{target_h}:flags=lanczos"
            f":force_original_aspect_ratio=decrease,"
            f"pad={target_w}:{target_h}:-1:-1:color=black"
        )

        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.mov')
        os.close(tmp_fd)

        fps = 25.0
        frame_count = 0

        try:
            # --- Step 1: FFmpeg HAP encode → temp .mov ---
            cmd = [
                'ffmpeg', '-y', '-i', input_path,
                '-vf', vf,
                '-vcodec', 'hap',
                '-format', hap_format,
                '-chunks', '1',
                '-compressor', 'none',
                '-an',
                tmp_path,
            ]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0:
                err = result.stderr.decode(errors='replace')[-600:]
                return ConversionResult(
                    success=False, input_path=input_path, output_path=output_hap,
                    error=f"FFmpeg failed: {err}"
                )

            # --- Step 2: Demux HAP .mov → extract raw DXT bytes per packet ---
            # HAP packet layout (single-chunk, no Snappy):
            #   [size_lo][size_mid][size_hi][descriptor] + [raw DXT data]
            # descriptor: 0x0B = BC1 (HAP), 0x0E = BC3 (HAP Alpha)
            with av.open(tmp_path) as container:
                v_stream = container.streams.video[0]
                if v_stream.average_rate:
                    fps = float(v_stream.average_rate)

                with open(output_hap, 'wb') as f_out:
                    for packet in container.demux(v_stream):
                        if packet.size <= 4:
                            continue  # flush / empty packet
                        raw = bytes(packet)
                        # HAP packet layout (single-chunk, no Snappy, FFmpeg):
                        #   raw[0:4]  outer section header (size 3B LE + type 0x0B/0x0E)
                        #   raw[4:8]  inner DXT-data section header (type 0x01)
                        #   raw[8:]   raw DXT bytes
                        dxt = raw[8:]
                        if len(dxt) != frame_bytes:
                            logger.warning(
                                f"[HapConvert] {preset}: frame {frame_count} "
                                f"size {len(dxt)} != expected {frame_bytes} — skipping"
                            )
                            continue
                        f_out.write(dxt)
                        frame_count += 1

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if frame_count == 0:
            return ConversionResult(
                success=False, input_path=input_path, output_path=output_hap,
                error="No frames extracted from HAP encode"
            )

        meta = {
            'fps': fps,
            'frame_count': frame_count,
            'width': target_w,
            'height': target_h,
            'format': 'hap',
            'dxt_variant': dxt_variant,
            'frame_bytes': frame_bytes,
            'preset': preset,
        }
        with open(output_meta, 'w') as f:
            json.dump(meta, f, indent=2)

        elapsed = time.perf_counter() - t0
        size_mb = (frame_count * frame_bytes) / (1024 * 1024)
        input_size_mb = os.path.getsize(input_path) / (1024 * 1024) if os.path.exists(input_path) else 0

        logger.info(
            f"[HapConvert] {preset} ({dxt_variant.upper()}): "
            f"{frame_count}fr @ {fps:.1f}fps -> {size_mb:.0f} MB in {elapsed:.0f}s"
        )

        return ConversionResult(
            success=True,
            input_path=input_path,
            output_path=output_hap,
            duration=elapsed,
            input_size_mb=input_size_mb,
            output_size_mb=size_mb,
            compression_ratio=size_mb / input_size_mb if input_size_mb > 0 else 0,
        )

    # ------------------------------------------------------------------
    # Multi-resolution conversion (main pipeline)
    # ------------------------------------------------------------------

    def convert_multi_resolution(
        self,
        input_path: str,
        presets: Optional[List[str]] = None,
        output_format: Optional[OutputFormat] = None,
        output_dir: Optional[str] = None,
        dxt_variant: str = 'bc1',
        custom_resolutions: Optional[List[Dict]] = None,
    ) -> Tuple[str, Dict]:
        """Convert a video to multiple resolution presets inside a clip folder.

        Supports resume: re-calling on an existing clip folder skips presets
        already marked 'done'.

        Args:
            input_path:          Source video file.
            presets:             Standard preset names (e.g. ['720p', '1080p']).
                                 Defaults to ALL_PRESETS.
            output_format:       Unused (kept for API compatibility).
            output_dir:          Parent directory for the clip folder.
            dxt_variant:         'bc1' (RGB) or 'bc3' (RGBA with alpha).
            custom_resolutions:  List of {'name': str, 'width': int, 'height': int}.

        Returns:
            (clip_folder, results) where results maps preset_name -> info dict.
        """
        if presets is None:
            presets = list(ALL_PRESETS)
        if custom_resolutions is None:
            custom_resolutions = []

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        target_dir = output_dir if output_dir else os.path.dirname(input_path)
        clip_folder = os.path.join(target_dir, base_name)
        os.makedirs(clip_folder, exist_ok=True)

        state = self._load_job_state(clip_folder)

        original_dest = os.path.join(clip_folder, 'original.mov')
        if not os.path.exists(original_dest):
            shutil.copy2(input_path, original_dest)
            logger.info(f"[MultiRes] Copied original -> {original_dest}")

        # Build job list: standard presets + custom resolutions
        jobs: List[Tuple[str, Optional[Tuple[int, int]]]] = [
            (p, None) for p in presets
        ]
        for cr in custom_resolutions:
            w = _align4(int(cr['width']))
            h = _align4(int(cr['height']))
            name = cr.get('name') or f"custom_{w}x{h}"
            jobs.append((name, (w, h)))

        results = {}
        for preset_name, custom_res in jobs:
            output_hap = os.path.join(clip_folder, f"{preset_name}.hap")
            output_meta = os.path.join(clip_folder, f"{preset_name}.json")

            if state.get(preset_name) == 'done' and os.path.exists(output_hap):
                logger.info(f"[HapConvert] {preset_name}: already done, skipping")
                results[preset_name] = {
                    'success': True, 'skipped': True, 'output_path': output_hap
                }
                continue

            if state.get(preset_name) == 'in_progress' or (
                isinstance(state.get(preset_name), str)
                and state[preset_name].startswith('failed')
            ):
                for partial in [output_hap, output_meta]:
                    if os.path.exists(partial):
                        os.remove(partial)
                logger.warning(f"[HapConvert] {preset_name}: removed partial files before retry")

            state[preset_name] = 'in_progress'
            self._save_job_state(clip_folder, state)

            try:
                result = self._hap_convert_preset(
                    original_dest, clip_folder, preset_name,
                    dxt_variant=dxt_variant,
                    custom_resolution=custom_res,
                )
                if result.success:
                    state[preset_name] = 'done'
                    results[preset_name] = {
                        'success': True,
                        'output_path': output_hap,
                        'size_mb': result.output_size_mb,
                        'dxt_variant': dxt_variant,
                    }
                else:
                    state[preset_name] = f"failed: {result.error}"
                    results[preset_name] = {'success': False, 'error': result.error}
                    logger.error(f"[HapConvert] {preset_name}: failed -- {result.error}")
            except Exception as e:
                msg = str(e)
                state[preset_name] = f"failed: {msg}"
                results[preset_name] = {'success': False, 'error': msg}
                logger.error(f"[HapConvert] {preset_name}: exception -- {e}")

            self._save_job_state(clip_folder, state)

        return clip_folder, results

    # ------------------------------------------------------------------
    # Job state helpers
    # ------------------------------------------------------------------

    def _load_job_state(self, clip_folder: str) -> Dict:
        state_path = os.path.join(clip_folder, JOB_STATE_FILE)
        if os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_job_state(self, clip_folder: str, state: Dict) -> None:
        state_path = os.path.join(clip_folder, JOB_STATE_FILE)
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)

    def get_conversion_status(self, clip_folder: str) -> Dict:
        """Return current conversion status for a clip folder (for frontend polling)."""
        state = self._load_job_state(clip_folder)
        return {
            'clip': os.path.basename(clip_folder),
            'clip_folder': clip_folder,
            'presets': state,
            'done': [p for p, s in state.items() if s == 'done'],
            'pending': [p for p, s in state.items() if s != 'done'],
            'in_progress': [p for p, s in state.items() if s == 'in_progress'],
            'failed': [
                p for p, s in state.items()
                if isinstance(s, str) and s.startswith('failed')
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_converter_instance: Optional[VideoConverter] = None


def get_converter() -> VideoConverter:
    """Return the singleton VideoConverter instance."""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = VideoConverter()
    return _converter_instance
