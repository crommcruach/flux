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
        'source_decode',       # Codec decoding (FFmpeg, HAP, etc.)
        'clip_effects',        # Clip-level effects processing
        'layer_composition',   # Multi-layer blending
        'player_effects',      # Player-level effects
        'audio_sequences',     # Audio-driven parameter modulation
        'transitions',         # Crossfade/transition effects
        'background_composite',# Background image overlay
        'output_routing',      # ArtNet pixel mapping
        'frame_delivery',      # Final output delivery
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
        self._timings: Dict[str, deque] = {
            stage: deque(maxlen=history_size) for stage in self.STAGES
        }
        
        # Current frame timing (for nested stages)
        self._current_frame_times: Dict[str, float] = {}
        
        # Thread-local storage for timer stack (handles nested timers)
        self._local = threading.local()
        
        # Lock for thread-safe access
        self._lock = threading.RLock()
        
        # Frame counter
        self._frame_count = 0
        self._start_time = time.time()
        
        # Total frame time tracking
        self._total_frame_times = deque(maxlen=history_size)
    
    @contextmanager
    def profile_stage(self, stage_name: str):
        """
        Context manager for profiling a pipeline stage.
        
        Usage:
            with profiler.profile_stage('clip_effects'):
                # ... processing code ...
        
        When profiling is disabled, this has near-zero overhead (just a yield).
        """
        # Fast path: profiling disabled or invalid stage (minimal overhead)
        if not self.enabled or stage_name not in self.STAGES:
            yield
            return
        
        # Profiling enabled: measure timing
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            with self._lock:
                self._timings[stage_name].append(elapsed_ms)
                self._current_frame_times[stage_name] = elapsed_ms
    
    def record_frame_complete(self):
        """Mark end of frame processing and record total time."""
        with self._lock:
            # Calculate total frame time (sum of all stages)
            total_time = sum(self._current_frame_times.values())
            self._total_frame_times.append(total_time)
            self._frame_count += 1
            
            # Clear current frame times for next frame
            self._current_frame_times = {}
    
    def get_metrics(self) -> Dict:
        """
        Get comprehensive performance metrics.
        
        Returns:
            Dict with stage metrics, totals, and summary
        """
        with self._lock:
            # Calculate total frame time average
            total_avg = sum(self._total_frame_times) / len(self._total_frame_times) if self._total_frame_times else 0
            
            # Stage metrics
            stages_data = []
            for stage in self.STAGES:
                timings = list(self._timings[stage])
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
                    'target_fps': 60,
                    'target_frame_time_ms': 16.67,
                    'performance_ratio': round((16.67 / total_avg) if total_avg > 0 else 0, 2)
                },
                'stages': stages_data
            }
    
    def reset(self):
        """Reset all metrics."""
        with self._lock:
            for stage in self.STAGES:
                self._timings[stage].clear()
            self._total_frame_times.clear()
            self._current_frame_times.clear()
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
