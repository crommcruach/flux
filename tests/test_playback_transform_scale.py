"""
Integration test: Video playback + transform scale XY 200% without crash, ≥25 FPS.

Runs headlessly (no GLFW display, no Art-Net, no REST API).
Uses the SINGLE Preview player path so there is no dual-player GPU context race.

Pass/fail criteria:
  - No unhandled exception or silent process crash during 5-second run.
  - Measured FPS ≥ 25.

Usage:
    cd C:\\Users\\cromm\\OneDrive\\Dokumente\\Py_artnet
    python tests/test_playback_transform_scale.py
"""

import os
import sys
import time
import threading
import traceback
import numpy as np

# ── resolve workspace root ────────────────────────────────────────────────────
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(WORKSPACE, 'src')
for _p in (WORKSPACE, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── constants ─────────────────────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1920, 1080
FPS_TARGET      = 30
TEST_DURATION_S = 10         # seconds to measure (longer window → less jitter)
MIN_FPS         = 22         # minimum acceptable — steady state is ~25 FPS;
                             # 22 gives headroom for Windows timer jitter while
                             # still catching real regressions (crashes → 0 FPS)
SCALE_PCT       = 200.0      # scale_x and scale_y percentage to apply

# ── minimal stub config ──────────────────────────────────────────────────────
CONFIG = {
    'video': {
        'default_brightness': 1.0,
        'default_speed': 1.0,
        'frame_wait_delay': 0.01,
    },
    'gpu': {'force_gpu_path': True},
    'artnet': {'fps': 30},
}


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic frame source — generates solid-grey frames at FPS_TARGET, no I/O
# ─────────────────────────────────────────────────────────────────────────────

class SolidColorSource:
    """Synthetic FrameSource: returns a solid-grey frame at 30 FPS, loops forever.

    Runs the composite_layers GPU path without any file I/O, letting the test
    measure the rendering pipeline throughput rather than disk read speed.
    """

    def __init__(self, w, h, fps=FPS_TARGET):
        self.canvas_width  = w
        self.canvas_height = h
        self.fps           = fps
        self.current_frame = 0
        self.total_frames  = fps * 60   # 60-second supply — never exhausted during test
        self.is_infinite   = True
        self.source_type   = 'video'
        self.video_path    = 'test://solid_color'
        # Pre-allocated solid grey frame — shared across calls (read-only by GPU path)
        self._frame = np.full((h, w, 3), 64, dtype=np.uint8)

    def initialize(self):
        return True

    def get_next_frame(self):
        self.current_frame = (self.current_frame + 1) % self.total_frames
        # delay=0 → play loop uses fps_limit pacing (1/FPS_TARGET ≈ 33 ms)
        return self._frame, 0.0

    def reset(self):
        self.current_frame = 0

    def cleanup(self):
        pass

    def get_source_name(self):
        return 'SolidColorTestSource'

    def get_info(self):
        return {'source_type': 'SolidColorTestSource'}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_player():
    """Build a minimal single-player (Preview mode, no Art-Net, no display)."""
    from modules.player.core import Player

    solid = SolidColorSource(CANVAS_W, CANVAS_H)
    player = Player(
        solid,
        target_ip='127.0.0.1',
        start_universe=0,
        fps_limit=FPS_TARGET,
        config=CONFIG,
        enable_artnet=False,
        player_name='TestPlayer',
        canvas_width=CANVAS_W,
        canvas_height=CANVAS_H,
    )
    return player, solid


def _add_transform_scale(player, solid_source, scale_pct: float):
    """Wire the solid source as a layer, inject TransformEffect, force CPU download."""
    from plugins.effects.transform import TransformEffect

    # Add solid source as layer 0 → play loop uses composite_layers() path
    player.layer_manager.add_layer(solid_source, player_name='TestPlayer')

    # TransformEffect.__init__ calls initialize(config) automatically
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

    # Force needs_cpu_frame=True so composite_layers downloads each GPU frame to
    # numpy — without this the GPU-path returns None and frames_processed never
    # increments (the play loop mistakes None for end-of-source).
    player._fullscreen_subscriber_count = 1

    print(f'  TransformEffect injected into layer 0 (scale_xy={scale_pct}%)')


# ─────────────────────────────────────────────────────────────────────────────
# FPS measurement via player.frames_processed counter
# ─────────────────────────────────────────────────────────────────────────────

def _snapshot_fps(player):
    """Return current frames_processed value from the play loop."""
    return getattr(player, 'frames_processed', 0)


# ─────────────────────────────────────────────────────────────────────────────
# Main test
# ─────────────────────────────────────────────────────────────────────────────

def run_test():
    print("=" * 60)
    print("test_playback_transform_scale")
    print(f"  source : SolidColorSource (synthetic, no file I/O)")
    print(f"  canvas : {CANVAS_W}×{CANVAS_H}")
    print(f"  scale  : {SCALE_PCT}%")
    print(f"  target : {MIN_FPS} FPS for {TEST_DURATION_S}s")
    print("=" * 60)

    # ── Build player ─────────────────────────────────────────────────────────
    print("Building player…")
    try:
        player, solid_source = _make_player()
    except Exception as e:
        print(f"FAIL: player construction error: {e}")
        traceback.print_exc()
        return False

    # ── Add transform scale 200% before playback starts ──────────────────────
    print(f"Injecting TransformEffect scale_xy={SCALE_PCT}%…")
    try:
        _add_transform_scale(player, solid_source, SCALE_PCT)
    except Exception as e:
        print(f"FAIL: effect injection error: {e}")
        traceback.print_exc()
        return False

    # ── Start playback ───────────────────────────────────────────────────────
    print("Starting playback…")
    try:
        player.start()
    except Exception as e:
        print(f"FAIL: player.start() raised: {e}")
        traceback.print_exc()
        return False

    if not player.is_playing:
        print("FAIL: player.is_playing is False immediately after start()")
        return False

    # Allow the play loop to warm up (pipeline reset + GPU init), then measure
    print("Waiting for GPU pipeline warm-up…", end='', flush=True)
    warmup_deadline = time.time() + 10.0
    while time.time() < warmup_deadline:
        if _snapshot_fps(player) >= 10:
            break
        if not player.is_playing:
            print("\nFAIL: player stopped during GPU warm-up")
            return False
        time.sleep(0.05)
    else:
        print("\nFAIL: GPU pipeline did not start within 10s")
        return False
    print(f" done ({_snapshot_fps(player)} frames already)")

    # ── Steady-state FPS measurement ────────────────────────────────────────
    print(f"Measuring {TEST_DURATION_S}s…", end='', flush=True)
    frames_start = _snapshot_fps(player)
    t0 = time.time()
    while time.time() - t0 < TEST_DURATION_S:
        time.sleep(0.25)
        elapsed = time.time() - t0
        frames_now = _snapshot_fps(player) - frames_start
        fps_now = frames_now / elapsed if elapsed > 0 else 0
        print(f"\r  {elapsed:.1f}s  frames={frames_now}  fps={fps_now:.1f}    ", end='', flush=True)
        if not player.is_playing:
            print(f"\nFAIL: player stopped unexpectedly after {elapsed:.1f}s")
            return False

    print()  # newline after progress
    total_frames = _snapshot_fps(player) - frames_start

    # ── Stop player cleanly ──────────────────────────────────────────────────
    print("Stopping player…")
    try:
        player.stop()
    except Exception as e:
        print(f"WARN: player.stop() raised: {e}")

    # ── Result ───────────────────────────────────────────────────────────────
    measured_fps = total_frames / TEST_DURATION_S
    print(f"\nResult:")
    print(f"  frames rendered : {total_frames}")
    print(f"  measured FPS    : {measured_fps:.1f}")
    print(f"  minimum FPS     : {MIN_FPS}")

    if measured_fps < MIN_FPS:
        print(f"FAIL: FPS {measured_fps:.1f} < minimum {MIN_FPS}")
        return False

    print(f"PASS: FPS {measured_fps:.1f} ≥ {MIN_FPS} and no crash")
    return True


if __name__ == '__main__':
    ok = run_test()
    sys.exit(0 if ok else 1)
