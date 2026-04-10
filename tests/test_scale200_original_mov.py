"""
Performance test: original.mov @ 1080p + TransformEffect scale 200%

Pass criterion: sustained ≥ 30 FPS over a 15-second steady-state window.

Profiler summary (per-stage avg_ms, total frame time, FPS) is printed
on completion so regressions can be diagnosed without re-running.

Usage:
    cd C:\\Users\\cromm\\OneDrive\\Dokumente\\Py_artnet
    C:\\Users\\cromm\\AppData\\Local\\Programs\\Python\\Python312\\python.exe tests/test_scale200_original_mov.py
"""

import os
import sys
import time
import traceback

import cv2
import numpy as np

# Force UTF-8 output so Unicode chars in print() don't crash on cp1252 consoles
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── workspace root on sys.path ────────────────────────────────────────────────
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (WORKSPACE, os.path.join(WORKSPACE, 'src')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── constants ─────────────────────────────────────────────────────────────────
VIDEO_PATH    = r'C:\Users\cromm\OneDrive\Dokumente\Py_artnet\video\original\original.mov'
CANVAS_W      = 1920
CANVAS_H      = 1080
FPS_TARGET    = 30
SCALE_PCT     = 200.0
WARMUP_S      = 25     # wgpu cold-compiles WGSL shaders on first use (~7s); give extra headroom
MEASURE_S     = 15     # steady-state measurement window
MIN_FPS       = 30.0   # PASS threshold

CONFIG = {
    'video': {'default_brightness': 1.0, 'default_speed': 1.0, 'frame_wait_delay': 0.01},
    'gpu':   {'force_gpu_path': True},
    'artnet': {'fps': FPS_TARGET},
}


# ─────────────────────────────────────────────────────────────────────────────
# OpenCV looping source — reads original.mov, loops at end, no .npy conversion
# ─────────────────────────────────────────────────────────────────────────────

class MovSource:
    """
    FrameSource that pre-caches all frames from the video file into RAM,
    then serves them as numpy arrays.  This isolates the GPU pipeline
    performance from cv2 H.264 decode latency and seeks-on-loop overhead.
    Loops immediately when the last frame is reached.
    Provides the same duck-typed interface that Player/LayerManager expect.
    """

    def __init__(self, path: str, canvas_w: int, canvas_h: int):
        self.video_path  = path
        self.source_path = path
        self.source_type = 'video'
        self.canvas_width  = canvas_w
        self.canvas_height = canvas_h
        self.player_name   = 'TestPlayer'
        self.clip_id       = None
        self.is_infinite   = True

        self._frames_cache: list = []
        self._idx = 0
        self.fps       = FPS_TARGET
        self.current_frame = 0
        self.total_frames  = 0

    def initialize(self) -> bool:
        if self._frames_cache:   # already cached — avoid double-init from add_layer
            return True
        cap = cv2.VideoCapture(self.video_path)
        if not cap.isOpened():
            return False
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        _fps = cap.get(cv2.CAP_PROP_FPS)
        self.fps = _fps if _fps > 0 else FPS_TARGET
        print(f"  Pre-caching {self.total_frames} frames into RAM…", end='', flush=True)
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            h, w = frame.shape[:2]
            if w != self.canvas_width or h != self.canvas_height:
                frame = cv2.resize(frame, (self.canvas_width, self.canvas_height))
            self._frames_cache.append(frame)
        cap.release()
        self.total_frames = len(self._frames_cache)
        print(f" {self.total_frames} frames cached ({self.total_frames * self.canvas_width * self.canvas_height * 3 // 1024 // 1024} MB)")
        return self.total_frames > 0

    def get_next_frame(self):
        if not self._frames_cache:
            return None, 0.0
        frame = self._frames_cache[self._idx]
        self._idx = (self._idx + 1) % len(self._frames_cache)
        self.current_frame = self._idx
        return frame, 0.0

    def reset(self):
        self._idx = 0
        self.current_frame = 0

    def cleanup(self):
        self._frames_cache.clear()

    def get_source_name(self) -> str:
        return os.path.basename(self.video_path)

    def get_info(self) -> dict:
        return {'source_type': 'MovSource', 'path': self.video_path}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_player(source: MovSource):
    from modules.player.core import Player
    player = Player(
        source,
        target_ip='127.0.0.1',
        start_universe=0,
        fps_limit=FPS_TARGET,
        config=CONFIG,
        enable_artnet=False,
        player_name='TestPlayer',
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
    )
    return player


def _inject_transform(player, source: MovSource, scale_pct: float):
    from plugins.effects.transform import TransformEffect
    player.layer_manager.add_layer(source, player_name='TestPlayer')
    instance = TransformEffect(config={
        'scale_xy': scale_pct,
        'scale_x':  scale_pct,
        'scale_y':  scale_pct,
    })
    player.layers[0].effects = [{
        'id':       'transform',
        'enabled':  True,
        'instance': instance,
        'config':   {'scale_xy': scale_pct, 'scale_x': scale_pct, 'scale_y': scale_pct},
    }]
    # GPU-only path: needs_cpu_frame=False keeps the composite on the GPU and
    # avoids the ~42 ms AMD readback stall.  The _GPU_PROCESSED sentinel now
    # lets the play loop count frames without downloading.


def _frames(player) -> int:
    return getattr(player, 'frames_processed', 0)


def _print_profiler(player):
    """Print a formatted per-stage breakdown from the player profiler."""
    try:
        metrics = player.profiler.get_metrics()
        total = metrics['total_frame_time']
        fps   = metrics['fps']
        print(f"\n{'─'*62}")
        print(f"  PROFILER SUMMARY  ({metrics['player']})")
        print(f"{'─'*62}")
        print(f"  FPS (profiler):      {fps:.1f}")
        print(f"  Total frames:        {metrics['total_frames']}")
        print(f"  Avg frame time:      {total['avg_ms']:.2f} ms")
        print(f"  Min frame time:      {total['min_ms']:.2f} ms")
        print(f"  Max frame time:      {total['max_ms']:.2f} ms")
        print(f"  Unaccounted:         {metrics['unaccounted_ms']:.2f} ms")
        print(f"{'─'*62}")
        print(f"  {'Stage':<30} {'avg ms':>8}  {'min':>7}  {'max':>7}  {'%':>5}")
        print(f"  {'─'*30}  {'─'*7}  {'─'*7}  {'─'*7}  {'─'*5}")
        for s in metrics['stages']:
            if s['samples'] == 0:
                continue
            print(
                f"  {s['name']:<30}  {s['avg_ms']:>7.2f}  "
                f"{s['min_ms']:>7.2f}  {s['max_ms']:>7.2f}  {s['percentage']:>5.1f}%"
            )
        print(f"{'─'*62}\n")
    except Exception as e:
        print(f"  (profiler dump failed: {e})")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_test() -> bool:
    print("=" * 62)
    print("test_scale200_original_mov")
    print(f"  video  : {VIDEO_PATH}")
    print(f"  canvas : {CANVAS_W}×{CANVAS_H}")
    print(f"  effect : TransformEffect scale_xy={SCALE_PCT:.0f}%")
    print(f"  target : ≥{MIN_FPS:.0f} FPS (steady state over {MEASURE_S}s)")
    print("=" * 62)

    if not os.path.exists(VIDEO_PATH):
        print(f"FAIL: video file not found: {VIDEO_PATH}")
        return False

    # ── source ───────────────────────────────────────────────────────────────
    print("Opening video source…")
    source = MovSource(VIDEO_PATH, CANVAS_W, CANVAS_H)
    if not source.initialize():
        print("FAIL: cv2.VideoCapture could not open the video file")
        return False
    print(f"  {source.total_frames} frames @ {source.fps:.1f} fps  "
          f"({CANVAS_W}×{CANVAS_H})")

    # ── build player ─────────────────────────────────────────────────────────
    print("Building player…")
    try:
        player = _build_player(source)
    except Exception as e:
        print(f"FAIL: player construction: {e}")
        traceback.print_exc()
        return False

    print(f"Injecting TransformEffect scale_xy={SCALE_PCT:.0f}%…")
    try:
        _inject_transform(player, source, SCALE_PCT)
    except Exception as e:
        print(f"FAIL: effect injection: {e}")
        traceback.print_exc()
        return False

    # ── start ─────────────────────────────────────────────────────────────────
    print("Starting playback…")
    try:
        player.start()
    except Exception as e:
        print(f"FAIL: player.start(): {e}")
        traceback.print_exc()
        return False

    if not player.is_playing:
        print("FAIL: player.is_playing is False immediately after start()")
        return False

    # ── warm-up ───────────────────────────────────────────────────────────────
    print(f"GPU warm-up ({WARMUP_S}s)…", end='', flush=True)
    deadline = time.time() + WARMUP_S
    while time.time() < deadline:
        if _frames(player) >= 15:
            break
        if not player.is_playing:
            print(f"\nFAIL: player stopped during warm-up")
            return False
        time.sleep(0.1)
    else:
        print(f"\nFAIL: pipeline did not produce 15 frames within {WARMUP_S}s")
        return False
    print(f" done ({_frames(player)} frames)")

    # Reset profiler so steady-state stats start clean
    player.profiler.reset()

    # ── steady-state measurement ──────────────────────────────────────────────
    print(f"Measuring {MEASURE_S}s steady state…")
    frames_start = _frames(player)
    t0 = time.time()
    while time.time() - t0 < MEASURE_S:
        time.sleep(0.25)
        elapsed = time.time() - t0
        delta_f = _frames(player) - frames_start
        fps_now = delta_f / elapsed if elapsed > 0 else 0.0
        print(f"\r  {elapsed:5.1f}s  frames={delta_f:4d}  fps={fps_now:5.1f}    ",
              end='', flush=True)
        if not player.is_playing:
            print(f"\nFAIL: player stopped at {elapsed:.1f}s")
            _print_profiler(player)
            return False

    print()  # newline
    total_frames = _frames(player) - frames_start
    measured_fps = total_frames / MEASURE_S

    # ── stop ──────────────────────────────────────────────────────────────────
    print("Stopping player…")
    try:
        player.stop()
    except Exception as e:
        print(f"WARN: player.stop(): {e}")

    # ── profiler dump ─────────────────────────────────────────────────────────
    _print_profiler(player)

    # ── verdict ───────────────────────────────────────────────────────────────
    print(f"Result:")
    print(f"  frames rendered : {total_frames}")
    print(f"  measured FPS    : {measured_fps:.2f}")
    print(f"  minimum FPS     : {MIN_FPS:.1f}")

    if measured_fps < MIN_FPS:
        print(f"\nFAIL: {measured_fps:.2f} FPS < {MIN_FPS:.1f} FPS threshold")
        return False

    print(f"\nPASS: {measured_fps:.2f} FPS ≥ {MIN_FPS:.1f} FPS  (1080p + scale 200%, no crash)")
    return True


if __name__ == '__main__':
    ok = run_test()
    sys.exit(0 if ok else 1)
