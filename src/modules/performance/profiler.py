"""
Performance Profiler - Tracks processing times through the entire rendering pipeline.

Pipeline stages:
1. Clip Load (video source reading)
2. Source Decoding (codec, frame extraction)
3. Clip Effects (individual clip processing)
4. Layer Composition (multi-layer blending)
5. Player Effects (final composition effects)
6. Audio Sequences (parameter modulation)
7. Transitions (crossfade between clips)
8. Background Compositing (background image overlay)
9. Output Routing (ArtNet pixel mapping)
10. Frame Delivery (final output)
"""

import time
import threading
from collections import deque, defaultdict
from contextlib import contextmanager
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class StageMetrics:
    """Metrics for a single processing stage."""
    name: str
    avg_ms: float
    min_ms: float
    max_ms: float
    last_ms: float
    samples: int
    percentage: float = 0.0
    
    def to_dict(self):
        return asdict(self)


class PerformanceProfiler:
    """
    Tracks processing times for each stage of the rendering pipeline.
    Thread-safe, uses circular buffers for efficient memory usage.
    """
    
    # Pipeline stage definitions (in processing order)
    STAGES = [
        'transport_preprocess', # Transport effect frame-position calculation
        'source_decode',        # Codec decoding (FFmpeg, HAP, etc.)
        'clip_effects',         # Clip-level effects processing
        'effects_upload',       # GPU texture upload for effect chain
        'composite_download',   # GPU texture.read() stall (SSBO / texture.read fallback)
        'layer_composition',    # Multi-layer blending
        'preview_encode',       # MJPEG thumbnail encode (PIL resize + simplejpeg)
        'player_effects',       # Player-level effects
        'audio_sequences',      # Audio-driven parameter modulation
        'transitions',          # Crossfade/transition effects
        'background_composite', # Background image overlay
        'output_routing',       # ArtNet pixel mapping
        'frame_delivery',       # Final output delivery
    ]
    
    def __init__(self, history_size: int = 100, player_name: str = "Unknown"):
        """
        Initialize profiler.
        
        Args:
            history_size: Number of samples to keep per stage
            player_name: Name of the player (Video/ArtNet)
        """
        self.history_size = history_size
        self.player_name = player_name
        self.enabled = True
        
        # Storage: {stage_name: deque([time1, time2, ...])}
        # All known stages are pre-created so profile_stage() never needs a
        # lock for them — deque.append and dict.__setitem__ are GIL-atomic in CPython.
        self._timings: Dict[str, deque] = {
            stage: deque(maxlen=history_size) for stage in self.STAGES
        }
        
        # Current frame timing — pre-populated so dict never resizes for known stages.
        self._current_frame_times: Dict[str, float] = {stage: 0.0 for stage in self.STAGES}
        
        # Lock only used for: unknown-stage lazy-create, get_metrics(), record_frame_complete()
        self._lock = threading.RLock()
        
        # Frame counter
        self._frame_count = 0
        self._start_time = time.time()
        
        # Total frame time tracking
        self._total_frame_times = deque(maxlen=history_size)
        self._source_fps: float = 0.0  # updated each frame via record_frame_complete
    
    @contextmanager
    def profile_stage(self, stage_name: str):
        """
        Context manager for profiling a pipeline stage.

        Accepts any stage name — predefined stages in STAGES as well as
        dynamic sub-stages (e.g. effects_upload, effects_shader_transform).

        Hot-path design: zero lock acquisitions for known stages.
        deque.append and dict.__setitem__ are GIL-atomic in CPython, so no
        lock is needed when writing to pre-created entries from the render
        thread.  The lock is only acquired for unknown dynamic stages (rare)
        and by get_metrics() / record_frame_complete() when reading.
        """
        if not self.enabled:
            yield
            return

        # Fast path: known stage — no lock needed (pre-created in __init__)
        timings = self._timings.get(stage_name)
        if timings is None:
            # Unknown dynamic stage — create once, then never lock again
            with self._lock:
                if stage_name not in self._timings:
                    self._timings[stage_name] = deque(maxlen=self.history_size)
                    self._current_frame_times[stage_name] = 0.0
            timings = self._timings[stage_name]

        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            # GIL-atomic writes — no lock needed for known stages
            timings.append(elapsed_ms)
            self._current_frame_times[stage_name] = elapsed_ms
    
    def record_frame_complete(self, frame_start_perf: float = None, source_fps: float = None):
        """Mark end of frame processing and record total time.

        Args:
            frame_start_perf: time.perf_counter() value captured at the very start
                of the frame loop iteration.  When provided, the true wall-clock
                elapsed time is stored as total_frame_time.  When omitted, falls
                back to summing profiled stages (old behaviour — always too low
                because it ignores unprofiled gaps like MJPEG encoding).
            source_fps: actual FPS of the current clip/source (e.g. 17 for a GIF,
                30 for standard video).  Stored so get_metrics() can report the
                real frame budget instead of a hardcoded target.
        """
        with self._lock:
            if frame_start_perf is not None:
                total_time = (time.perf_counter() - frame_start_perf) * 1000
            else:
                total_time = sum(self._current_frame_times.values())
            self._total_frame_times.append(total_time)
            self._frame_count += 1
            if source_fps and source_fps > 0:
                self._source_fps = source_fps

            for key in self._current_frame_times:
                self._current_frame_times[key] = 0.0
    
    def get_metrics(self) -> Dict:
        """
        Get comprehensive performance metrics.
        
        Returns:
            Dict with stage metrics, totals, and summary
        """
        with self._lock:
            # Calculate total frame time average
            total_avg = sum(self._total_frame_times) / len(self._total_frame_times) if self._total_frame_times else 0
            
            # Stage metrics — predefined stages first, then any dynamic sub-stages
            all_stage_names = list(self.STAGES) + [
                s for s in self._timings if s not in self.STAGES
            ]
            stages_data = []
            for stage in all_stage_names:
                timings = list(self._timings.get(stage, []))
                if not timings:
                    stages_data.append(StageMetrics(
                        name=stage,
                        avg_ms=0,
                        min_ms=0,
                        max_ms=0,
                        last_ms=0,
                        samples=0,
                        percentage=0
                    ).to_dict())
                    continue
                
                avg_ms = sum(timings) / len(timings)
                percentage = (avg_ms / total_avg * 100) if total_avg > 0 else 0
                
                stages_data.append(StageMetrics(
                    name=stage,
                    avg_ms=round(avg_ms, 3),
                    min_ms=round(min(timings), 3),
                    max_ms=round(max(timings), 3),
                    last_ms=round(timings[-1], 3),
                    samples=len(timings),
                    percentage=round(percentage, 1)
                ).to_dict())
            
            # Calculate FPS
            uptime = time.time() - self._start_time
            fps = self._frame_count / uptime if uptime > 0 else 0
            
            return {
                'player': self.player_name,
                'enabled': self.enabled,
                'timestamp': datetime.now().isoformat(),
                'uptime_seconds': round(uptime, 1),
                'total_frames': self._frame_count,
                'fps': round(fps, 1),
                'total_frame_time': {
                    'avg_ms': round(total_avg, 3),
                    'min_ms': round(min(self._total_frame_times), 3) if self._total_frame_times else 0,
                    'max_ms': round(max(self._total_frame_times), 3) if self._total_frame_times else 0,
                    'source_fps': round(self._source_fps, 3),
                    'target_frame_time_ms': round(1000.0 / self._source_fps, 3) if self._source_fps > 0 else 0,
                    'performance_ratio': round((1000.0 / self._source_fps / total_avg) if (self._source_fps > 0 and total_avg > 0) else 0, 2),
                },
                'stages': stages_data,
                'unaccounted_ms': round(
                    max(0.0, total_avg - sum(
                        s['avg_ms'] for s in stages_data if s['avg_ms'] > 0
                    )),
                    3
                ),
            }
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            for deq in self._timings.values():
                deq.clear()
            self._total_frame_times.clear()
            self._source_fps = 0.0
            for key in self._current_frame_times:
                self._current_frame_times[key] = 0.0
            self._frame_count = 0
            self._start_time = time.time()
    
    def enable(self):
        """Enable profiling."""
        self.enabled = True
    
    def disable(self):
        """Disable profiling."""
        self.enabled = False


# Global profiler instances (one per player)
_profilers: Dict[str, PerformanceProfiler] = {}
_profilers_lock = threading.Lock()
_profiling_enabled = True  # Can be disabled globally via config


def set_profiling_enabled(enabled: bool):
    """Enable or disable profiling globally (typically set from config)."""
    global _profiling_enabled
    _profiling_enabled = enabled


def is_profiling_enabled() -> bool:
    """Check if profiling is enabled globally."""
    return _profiling_enabled


def get_profiler(player_name: str) -> PerformanceProfiler:
    """Get or create profiler for a player.
    
    If profiling is disabled globally, returns a profiler with enabled=False
    for zero overhead.
    """
    with _profilers_lock:
        if player_name not in _profilers:
            profiler = PerformanceProfiler(player_name=player_name)
            # Apply global enable/disable setting
            profiler.enabled = _profiling_enabled
            _profilers[player_name] = profiler
        return _profilers[player_name]


def get_all_profilers() -> Dict[str, PerformanceProfiler]:
    """Get all registered profilers."""
    with _profilers_lock:
        return _profilers.copy()
