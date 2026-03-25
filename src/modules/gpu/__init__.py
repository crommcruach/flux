"""
GPU pipeline — ModernGL/GLSL layer compositor.

Public API used by LayerManager:
    from ...gpu import get_context, get_texture_pool, get_renderer, load_shader,
                       BLEND_MODES, probe_gpu_readback, GPU_READBACK_VIABLE,
                       reset_gpu_pipeline, is_context_from_current_thread
"""
import threading as _threading
import time as _time
import numpy as _np
from .context import get_context, destroy_context, is_context_from_current_thread
from .texture_pool import get_texture_pool
from .renderer import get_renderer, load_shader
from .frame import GPUFrame
from ..core.logger import get_logger as _get_logger

_logger = _get_logger(__name__)

# Lock so only one thread resets the pipeline at a time
_gpu_reset_lock = _threading.Lock()


def reset_gpu_pipeline() -> None:
    """Destroy all GPU module singletons so they are recreated by the NEXT thread
    that calls get_context() / get_renderer() / get_texture_pool().

    Call this at the start of a new _play_loop thread whenever
    is_context_from_current_thread() returns False.  This ensures ModernGL's
    WGL context (which is thread-affine) is always created and current on the
    thread that will actually render frames.
    """
    with _gpu_reset_lock:
        from .renderer import _reset_renderer
        from .texture_pool import _reset_pool
        _reset_renderer()   # drops program cache (references old context)
        _reset_pool()       # releases pooled GPU textures + FBOs
        destroy_context()   # releases the ModernGL/WGL context itself
        _logger.info(f"GPU pipeline reset — will reinit in thread {_threading.get_ident()}")

# Blend mode name → integer index used in blend.frag
BLEND_MODES: dict[str, int] = {
    'normal':   0,
    'add':      1,
    'subtract': 2,
    'multiply': 3,
    'screen':   4,
    'overlay':  5,
    'mask':     6,
}

# ── GPU readback viability flag ──────────────────────────────────────────────
# Set once at startup by probe_gpu_readback(). Read by LayerManager to decide
# whether to use the GPU shader pipeline or the CPU fallback path.
GPU_READBACK_VIABLE: bool = False

# Threshold: if mean readback time is below this, GPU compositing is faster
# than the CPU cv2 path (~9ms). 15ms gives comfortable headroom at 30fps.
_READBACK_THRESHOLD_MS: float = 15.0


def probe_gpu_readback(width: int = 1920, height: int = 1080) -> bool:
    """
    Time a GPU texture upload + readback roundtrip at the given resolution.
    Sets and returns GPU_READBACK_VIABLE based on whether the mean latency is
    below _READBACK_THRESHOLD_MS (15 ms).

    config.json  gpu.force_gpu_path = true  bypasses the timing test and
    always enables the GPU path — useful for shader testing on AMD hardware
    where readback is slow but you want to verify GLSL shader correctness.

    Called once from LayerManager.__init__() at player startup.
    Logs a clear INFO message with the result so the startup log shows the
    active rendering path.
    """
    global GPU_READBACK_VIABLE

    # ── config override ───────────────────────────────────────────────────────
    try:
        import json as _json
        import os as _os
        _cfg_path = _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'config.json')
        with open(_cfg_path) as _f:
            _cfg = _json.load(_f)
        if _cfg.get('gpu', {}).get('force_gpu_path', False):
            GPU_READBACK_VIABLE = True
            _logger.warning(
                "⚠️  gpu.force_gpu_path=true — GPU shader path FORCED. "
                "Readback probe skipped. "
                "Single composite download ~43–50ms per frame on AMD "
                "(pipeline drain stall — unavoidable on this driver). "
                "Set force_gpu_path=false to use the CPU blend path instead."
            )
            return True
    except Exception:
        pass  # config unreadable → fall through to normal probe

    try:
        ctx = get_context()
        # Small test frame — pattern doesn't matter, just needs valid data
        test = _np.random.randint(0, 255, (height, width, 3), dtype=_np.uint8)
        frame = GPUFrame(ctx, width, height, 3)
        upload_buf = _np.empty((height, width, 3), dtype=_np.float32)

        # Warm-up (shader compile, driver lazy-init)
        _np.multiply(test[:, :, ::-1], 1.0 / 255.0, out=upload_buf)
        frame.texture.write(upload_buf.tobytes())
        frame.texture.read()

        # Measure 5 rounds
        times = []
        for _ in range(5):
            t0 = _time.perf_counter()
            _np.multiply(test[:, :, ::-1], 1.0 / 255.0, out=upload_buf)
            frame.texture.write(upload_buf.tobytes())
            frame.texture.read()
            times.append((_time.perf_counter() - t0) * 1000)

        mean_ms = float(_np.mean(times))
        viable = mean_ms < _READBACK_THRESHOLD_MS
        GPU_READBACK_VIABLE = viable

        if viable:
            _logger.info(
                f"🚀 GPU rendering path ACTIVE — readback {mean_ms:.1f}ms "
                f"< {_READBACK_THRESHOLD_MS}ms threshold at "
                f"{width}×{height} "
                f"({ctx.info.get('GL_RENDERER', 'unknown GPU')})"
            )
        else:
            _logger.warning(
                f"⚠️  GPU readback too slow ({mean_ms:.1f}ms at {width}×{height}) "
                f"— falling back to CPU compositing. "
                f"GPU: {ctx.info.get('GL_RENDERER', 'unknown')} | "
                f"Driver: AMD known issue (glGetTexImage pipeline stall). "
                f"See docs/AMD_DRIVER_BUGS.md"
            )
        return viable

    except Exception as e:
        GPU_READBACK_VIABLE = False
        _logger.warning(
            f"⚠️  GPU probe failed ({e}) — falling back to CPU compositing"
        )
        return False


__all__ = [
    'get_context',
    'destroy_context',
    'get_texture_pool',
    'get_renderer',
    'load_shader',
    'GPUFrame',
    'BLEND_MODES',
    'GPU_READBACK_VIABLE',
    'probe_gpu_readback',
]
