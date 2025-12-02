"""
Video Converter Module - Universal Video Converter mit HAP Codec Support
Unterstützt Batch-Processing, Auto-Resize, Loop-Optimierung
"""

import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


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
            
        elif job.format == OutputFormat.H264:
            cmd.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "23"])
            if job.bitrate:
                cmd.extend(["-b:v", job.bitrate])
                
        elif job.format == OutputFormat.H264_NVENC:
            cmd.extend(["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr"])
            if job.bitrate:
                cmd.extend(["-b:v", job.bitrate])
        
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
