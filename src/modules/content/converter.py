"""
Video Converter Module - Universal Video Converter mit HAP Codec Support
Unterstützt Batch-Processing, Auto-Resize, Loop-Optimierung, Multi-Resolution
"""

import os
import subprocess
import json
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Multi-Resolution Constants
# ---------------------------------------------------------------------------

RESOLUTION_PRESETS: Dict[str, Tuple[int, int]] = {
    '720p':  (1280, 720),
    '1080p': (1920, 1080),
    '1440p': (2560, 1440),
    '2160p': (3840, 2160),
}

ALL_PRESETS = ['720p', '1080p', '1440p', '2160p']

# State file name stored inside each clip folder
JOB_STATE_FILE = 'conversion_state.json'

# Maximum seconds per FFmpeg subprocess per resolution
CONVERSION_TIMEOUTS = {
    '720p':  1800,   # 30 min
    '1080p': 3600,   # 1 hour
    '1440p': 5400,   # 1.5 hours
    '2160p': 7200,   # 2 hours
}


def get_target_preset(player_width: int, player_height: int) -> str:
    """Return the smallest preset whose dimensions cover the player resolution."""
    for preset in ALL_PRESETS:
        w, h = RESOLUTION_PRESETS[preset]
        if w >= player_width and h >= player_height:
            return preset
    return '2160p'


def _scale_frame_fit(frame: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """Scale frame to fit target_w×target_h with letterbox (black bars, no crop)."""
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


class OutputFormat(Enum):
    """Unterstützte Output-Formate"""
    HAP = "hap"
    HAP_ALPHA = "hap_alpha"
    HAP_Q = "hap_q"
    H264 = "h264"
    H264_NVENC = "h264_nvenc"  # Hardware-Encoding (NVIDIA)


class ResizeMode(Enum):
    """Resize-Modi"""
    NONE = "none"
    FIT = "fit"  # Fit into canvas, keep aspect ratio
    FILL = "fill"  # Fill canvas, crop if needed
    STRETCH = "stretch"  # Stretch to canvas size
    AUTO = "auto"  # Automatic based on canvas config


@dataclass
class ConversionJob:
    """Einzelner Conversion-Job"""
    input_path: str
    output_path: str
    format: OutputFormat
    target_size: Optional[Tuple[int, int]] = None
    resize_mode: ResizeMode = ResizeMode.NONE
    optimize_loop: bool = False
    bitrate: Optional[str] = None  # z.B. "5M" für H.264
    fps: Optional[int] = None
    
    
@dataclass
class ConversionResult:
    """Ergebnis einer Conversion"""
    success: bool
    input_path: str
    output_path: str
    error: Optional[str] = None
    duration: float = 0.0
    input_size_mb: float = 0.0
    output_size_mb: float = 0.0
    compression_ratio: float = 0.0


class VideoConverter:
    """
    Universal Video Converter mit HAP Codec Support
    """
    
    def __init__(self, ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe"):
        """
        Initialize VideoConverter
        
        Args:
            ffmpeg_path: Pfad zu ffmpeg executable
            ffprobe_path: Pfad zu ffprobe executable
        """
        self.ffmpeg_path = ffmpeg_path
        self.ffprobe_path = ffprobe_path
        self._verify_ffmpeg()
        
    def _verify_ffmpeg(self):
        """Überprüfe ob FFmpeg verfügbar ist und HAP Codec unterstützt"""
        try:
            # Check FFmpeg
            result = subprocess.run(
                [self.ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("FFmpeg not found or not working")
            
            # Check HAP Codec Support
            result = subprocess.run(
                [self.ffmpeg_path, "-codecs"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "hap" not in result.stdout.lower():
                print("WARNING: HAP codec might not be available in this FFmpeg build")
                
        except FileNotFoundError:
            raise RuntimeError(f"FFmpeg not found at: {self.ffmpeg_path}. Please install FFmpeg: https://ffmpeg.org/download.html")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"FFmpeg command timed out")
        except Exception as e:
            raise RuntimeError(f"Error verifying FFmpeg: {e}")
    
    def get_video_info(self, video_path: str) -> Dict:
        """
        Hole Video-Informationen via ffprobe
        
        Args:
            video_path: Pfad zum Video
            
        Returns:
            Dictionary mit Video-Informationen
        """
        try:
            result = subprocess.run(
                [
                    self.ffprobe_path,
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"ffprobe failed: {result.stderr}")
            
            data = json.loads(result.stdout)
            
            # Extrahiere relevante Infos
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                None
            )
            
            if not video_stream:
                raise RuntimeError("No video stream found")
            
            return {
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "codec": video_stream.get("codec_name"),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "bitrate": int(data.get("format", {}).get("bit_rate", 0)),
                "size_bytes": int(data.get("format", {}).get("size", 0))
            }
            
        except Exception as e:
            raise RuntimeError(f"Error getting video info: {e}")
    
    def _build_ffmpeg_command(self, job: ConversionJob) -> List[str]:
        """
        Baue FFmpeg-Command für Conversion-Job
        
        Args:
            job: ConversionJob
            
        Returns:
            FFmpeg command als Liste
        """
        cmd = [self.ffmpeg_path, "-i", job.input_path]
        
        # Video Filter Chain
        filters = []
        
        # Resize Filter
        if job.target_size and job.resize_mode != ResizeMode.NONE:
            width, height = job.target_size
            
            if job.resize_mode == ResizeMode.FIT:
                # Scale to fit, pad if needed
                filters.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
                filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
                
            elif job.resize_mode == ResizeMode.FILL:
                # Scale to fill, crop if needed
                filters.append(f"scale={width}:{height}:force_original_aspect_ratio=increase")
                filters.append(f"crop={width}:{height}")
                
            elif job.resize_mode == ResizeMode.STRETCH:
                # Simple stretch
                filters.append(f"scale={width}:{height}")
        
        # Loop Optimization (für nahtlose Loops)
        if job.optimize_loop:
            # Fade out last frames and fade in first frames for smooth loop
            filters.append("fade=t=out:st=0:d=0.5,fade=t=in:st=0:d=0.5")
        
        # Apply filters
        if filters:
            cmd.extend(["-vf", ",".join(filters)])
        
        # FPS
        if job.fps:
            cmd.extend(["-r", str(job.fps)])
        
        # Codec-spezifische Optionen
        if job.format == OutputFormat.HAP:
            cmd.extend(["-c:v", "hap"])
            
        elif job.format == OutputFormat.HAP_ALPHA:
            cmd.extend(["-c:v", "hap", "-format", "hap_alpha"])
            
        elif job.format == OutputFormat.HAP_Q:
            cmd.extend(["-c:v", "hap", "-format", "hap_q"])
        
        # Audio (copy or remove)
        cmd.extend(["-an"])  # No audio for LED content
        
        # Output
        cmd.extend(["-y", job.output_path])  # -y overwrite
        
        return cmd
    
    def convert(self, job: ConversionJob, progress_callback=None) -> ConversionResult:
        """
        Konvertiere Video
        
        Args:
            job: ConversionJob
            progress_callback: Optional callback(percent: float, message: str)
            
        Returns:
            ConversionResult
        """
        import time
        start_time = time.time()
        
        try:
            # Get input info
            input_info = self.get_video_info(job.input_path)
            input_size_mb = input_info["size_bytes"] / (1024 * 1024)
            
            if progress_callback:
                progress_callback(0, f"Converting {Path(job.input_path).name}...")
            
            # Build command
            cmd = self._build_ffmpeg_command(job)
            
            # Execute
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Monitor progress
            stderr_output = []
            for line in process.stderr:
                stderr_output.append(line)
                
                # Parse progress from FFmpeg output
                if "time=" in line and progress_callback:
                    try:
                        time_str = line.split("time=")[1].split()[0]
                        h, m, s = time_str.split(":")
                        current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                        percent = min(100, (current_sec / input_info["duration"]) * 100)
                        progress_callback(percent, f"Converting... {percent:.1f}%")
                    except:
                        pass
            
            process.wait()
            
            if process.returncode != 0:
                error_msg = "\n".join(stderr_output[-10:])  # Last 10 lines
                return ConversionResult(
                    success=False,
                    input_path=job.input_path,
                    output_path=job.output_path,
                    error=f"FFmpeg error: {error_msg}"
                )
            
            # Get output info
            if os.path.exists(job.output_path):
                output_size_mb = os.path.getsize(job.output_path) / (1024 * 1024)
                compression_ratio = output_size_mb / input_size_mb if input_size_mb > 0 else 0
            else:
                output_size_mb = 0
                compression_ratio = 0
            
            duration = time.time() - start_time
            
            if progress_callback:
                progress_callback(100, "Conversion complete!")
            
            return ConversionResult(
                success=True,
                input_path=job.input_path,
                output_path=job.output_path,
                duration=duration,
                input_size_mb=input_size_mb,
                output_size_mb=output_size_mb,
                compression_ratio=compression_ratio
            )
            
        except Exception as e:
            return ConversionResult(
                success=False,
                input_path=job.input_path,
                output_path=job.output_path,
                error=str(e)
            )
    
    # -----------------------------------------------------------------------
    # Multi-Resolution Conversion (Phase 1)
    # -----------------------------------------------------------------------

    def convert_multi_resolution(
        self,
        input_path: str,
        presets: List[str] = None,
        output_format: OutputFormat = OutputFormat.HAP,
        output_dir: str = None,
    ) -> Tuple[str, Dict]:
        """Convert a video to multiple resolution presets inside a clip folder.

        Supports resume: calling this again on an existing clip folder skips
        presets already marked 'done' in conversion_state.json.

        Args:
            input_path:    Path to the source video file.
            presets:       List of preset names to convert.  Defaults to ALL_PRESETS.
            output_format: Output codec / container format.
            output_dir:    Directory where the clip folder is created.
                           Defaults to the same directory as input_path.

        Returns:
            (clip_folder, results) where results is a dict mapping preset → info.
        """
        import logging
        logger = logging.getLogger(__name__)

        if presets is None:
            presets = ALL_PRESETS

        base_name = os.path.splitext(os.path.basename(input_path))[0]
        target_dir = output_dir if output_dir else os.path.dirname(input_path)
        clip_folder = os.path.join(target_dir, base_name)
        os.makedirs(clip_folder, exist_ok=True)

        # Load existing state (resume support)
        state = self._load_job_state(clip_folder)

        # Copy original once
        original_dest = os.path.join(clip_folder, 'original.mov')
        if not os.path.exists(original_dest):
            shutil.copy2(input_path, original_dest)
            logger.info(f"[MultiRes] Copied original → {original_dest}")

        results = {}
        for preset in presets:
            output_npy = os.path.join(clip_folder, f"{preset}.npy")
            output_meta = os.path.join(clip_folder, f"{preset}.json")

            # Skip already-completed presets
            if state.get(preset) == 'done' and os.path.exists(output_npy):
                logger.info(f"[NpyConvert] {preset}: already done, skipping")
                results[preset] = {'success': True, 'skipped': True, 'output_path': output_npy}
                continue

            # Clean up partial files from a previous crashed run
            if state.get(preset) == 'in_progress':
                for partial in [output_npy, output_meta]:
                    if os.path.exists(partial):
                        os.remove(partial)
                logger.warning(f"[NpyConvert] {preset}: removed partial files from previous run")

            # Mark in-progress before starting
            state[preset] = 'in_progress'
            self._save_job_state(clip_folder, state)

            try:
                result = self._npy_convert_preset(original_dest, clip_folder, preset)
                if result.success:
                    state[preset] = 'done'
                    results[preset] = {
                        'success': True,
                        'output_path': output_npy,
                        'size_mb': result.output_size_mb,
                    }
                    logger.info(f"[NpyConvert] {preset}: done ({result.output_size_mb:.0f} MB in {result.duration:.0f}s)")
                else:
                    state[preset] = f"failed: {result.error}"
                    results[preset] = {'success': False, 'error': result.error}
                    logger.error(f"[NpyConvert] {preset}: failed — {result.error}")
            except Exception as e:
                msg = str(e)
                state[preset] = f"failed: {msg}"
                results[preset] = {'success': False, 'error': msg}
                logger.error(f"[NpyConvert] {preset}: exception — {e}")

            self._save_job_state(clip_folder, state)

        return clip_folder, results

    def _npy_convert_preset(
        self,
        input_path: str,
        clip_folder: str,
        preset: str,
    ) -> ConversionResult:
        """Decode all frames from input_path, scale to preset resolution, and save as .npy + .json."""
        import time
        import logging
        logger = logging.getLogger(__name__)

        target_w, target_h = RESOLUTION_PRESETS[preset]
        output_npy = os.path.join(clip_folder, f"{preset}.npy")
        output_meta = os.path.join(clip_folder, f"{preset}.json")

        t0 = time.perf_counter()

        cap = cv2.VideoCapture(input_path, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            return ConversionResult(
                success=False, input_path=input_path, output_path=output_npy,
                error=f"Could not open video: {input_path}"
            )

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        frames = []
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(_scale_frame_fit(frame, target_w, target_h))
        finally:
            cap.release()

        if not frames:
            return ConversionResult(
                success=False, input_path=input_path, output_path=output_npy,
                error="No frames decoded from video"
            )

        arr = np.stack(frames)  # shape: (N, H, W, 3)
        np.save(output_npy, arr)

        meta = {
            'fps': fps,
            'total_frames': len(frames),
            'width': target_w,
            'height': target_h,
            'original_width': orig_w,
            'original_height': orig_h,
            'preset': preset,
        }
        with open(output_meta, 'w') as f:
            json.dump(meta, f, indent=2)

        elapsed = time.perf_counter() - t0
        size_mb = arr.nbytes / (1024 * 1024)
        input_size_mb = os.path.getsize(input_path) / (1024 * 1024) if os.path.exists(input_path) else 0

        logger.info(f"[NpyConvert] {preset}: {len(frames)} frames @ {fps:.1f}fps → {size_mb:.0f} MB in {elapsed:.0f}s")

        return ConversionResult(
            success=True,
            input_path=input_path,
            output_path=output_npy,
            duration=elapsed,
            input_size_mb=input_size_mb,
            output_size_mb=size_mb,
            compression_ratio=size_mb / input_size_mb if input_size_mb > 0 else 0,
        )

    def _load_job_state(self, clip_folder: str) -> Dict:
        """Load per-preset conversion state from clip folder."""
        state_path = os.path.join(clip_folder, JOB_STATE_FILE)
        if os.path.exists(state_path):
            try:
                with open(state_path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_job_state(self, clip_folder: str, state: Dict) -> None:
        """Persist per-preset conversion state to clip folder."""
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
            'failed': [p for p, s in state.items() if isinstance(s, str) and s.startswith('failed')],
            'timeout': [p for p, s in state.items() if s == 'timeout'],
        }

    # -----------------------------------------------------------------------

    def batch_convert(
        self,
        input_pattern: str,
        output_dir: str,
        format: OutputFormat,
        target_size: Optional[Tuple[int, int]] = None,
        resize_mode: ResizeMode = ResizeMode.NONE,
        optimize_loop: bool = False,
        progress_callback=None
    ) -> List[ConversionResult]:
        """
        Batch-Convert mehrere Videos
        
        Args:
            input_pattern: Glob pattern für Input-Files (z.B. "kanal_1/*.mp4")
            output_dir: Output-Verzeichnis
            format: Output-Format
            target_size: Optional target size (width, height)
            resize_mode: Resize-Modus
            optimize_loop: Loop-Optimierung aktivieren
            progress_callback: Optional callback(job_index, total_jobs, percent, message)
            
        Returns:
            Liste von ConversionResults
        """
        from glob import glob
        
        # Find input files (recursive=True enables ** pattern)
        input_files = glob(input_pattern, recursive=True)
        if not input_files:
            raise ValueError(f"No files found matching pattern: {input_pattern}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert each file
        results = []
        for i, input_file in enumerate(input_files):
            # Build output filename
            input_name = Path(input_file).stem
            ext = ".mov" if format.value.startswith("hap") else ".mp4"
            output_file = os.path.join(output_dir, f"{input_name}{ext}")
            
            # Create job
            job = ConversionJob(
                input_path=input_file,
                output_path=output_file,
                format=format,
                target_size=target_size,
                resize_mode=resize_mode,
                optimize_loop=optimize_loop
            )
            
            # Convert
            def job_progress(percent, message):
                if progress_callback:
                    progress_callback(i + 1, len(input_files), percent, message)
            
            result = self.convert(job, job_progress)
            results.append(result)
        
        return results


# Singleton instance
_converter_instance = None

def get_converter() -> VideoConverter:
    """Get singleton VideoConverter instance"""
    global _converter_instance
    if _converter_instance is None:
        _converter_instance = VideoConverter()
    return _converter_instance
