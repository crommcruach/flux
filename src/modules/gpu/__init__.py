"""
GPU pipeline — wgpu/Vulkan layer compositor.

Public API used by LayerManager:
    from ...gpu import get_context, get_texture_pool, get_renderer, load_shader,
                       BLEND_MODES, probe_gpu_readback, GPU_READBACK_VIABLE,
                       reset_gpu_pipeline, is_context_from_current_thread
"""
import threading as _threading
from .context import (
    get_context, get_device, destroy_context,
    is_context_from_current_thread,
    try_claim_gpu, release_gpu_ownership,
    has_gpu_timestamps,
)
from .texture_pool import get_texture_pool
from .renderer import get_renderer, load_shader, warmup_pipelines, warmup_done
from .frame import GPUFrame
from .stack_signature import StackSignature
from .preview_downscaler import PreviewDownscaler
from ..core.logger import get_logger as _get_logger

_logger = _get_logger(__name__)

# Lock so only one thread resets the pipeline at a time
_gpu_reset_lock = _threading.Lock()


def reset_gpu_pipeline() -> None:
    """Reset renderer and texture pool singletons.

    Calling this forces pipeline objects to be recreated.
    The wgpu device is persistent and never reset between resets.
    """
    with _gpu_reset_lock:
        from .renderer import _reset_renderer
        from .texture_pool import _reset_pool
        _reset_renderer()
        _reset_pool()
        _logger.info(
            f"GPU pipeline reset (wgpu) — thread {_threading.get_ident()}"
        )


# Blend mode name → integer index used in blend.wgsl
BLEND_MODES: dict[str, int] = {
    'normal':   0,
    'add':      1,
    'subtract': 2,
    'multiply': 3,
    'screen':   4,
    'overlay':  5,
    'mask':     6,
}

# wgpu is always viable — no readback threshold needed.
GPU_READBACK_VIABLE: bool = True


def probe_gpu_readback(width: int = 1920, height: int = 1080) -> bool:
    """Verify wgpu device is accessible and return True.

    With wgpu the device is always initialised at startup; there is no
    slow glGetTexImage path.  This function logs the active GPU and sets
    GPU_READBACK_VIABLE = True unconditionally.

    config.json  gpu.force_gpu_path  is ignored (always True with wgpu).
    """
    global GPU_READBACK_VIABLE
    try:
        device = get_device()
        adapter_info = device.adapter_info
        gpu_name = adapter_info.get('name', 'unknown GPU')
        GPU_READBACK_VIABLE = True
        _logger.info(
            f"GPU rendering path ACTIVE — wgpu device ready "
            f"({gpu_name}  {width}\u00d7{height})"
        )
        return True
    except Exception as e:
        GPU_READBACK_VIABLE = True  # still try GPU; wgpu usually initialises fine
        _logger.warning(f"GPU probe: device query failed ({e}), proceeding anyway")
        return True


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
    'PreviewDownscaler',
    'StackSignature',
]
