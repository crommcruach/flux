"""
GPU device singleton — wgpu / Vulkan backend.

Public API:
    get_device() → wgpu.GPUDevice
    destroy_device() → None

Shims for backward compatibility:
    get_context()               → aliases get_device()
    is_context_from_current_thread() → always True
    try_claim_gpu() / release_gpu_ownership() → no-ops
    destroy_context() / _destroy_context_only() → aliases destroy_device()
"""
import threading
import wgpu
from ..core.logger import get_logger

logger = get_logger(__name__)

_device: wgpu.GPUDevice | None = None
_device_lock = threading.Lock()
_has_timestamp_query: bool = False


def get_device() -> wgpu.GPUDevice:
    """Return the wgpu GPU device singleton (created on first call)."""
    global _device, _has_timestamp_query
    if _device is not None:
        return _device
    with _device_lock:
        if _device is not None:
            return _device
        adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
        # Try to enable GPU timestamp queries for accurate per-pass profiling.
        # Falls back gracefully; most desktop Vulkan/D3D12 drivers support this.
        try:
            _device = adapter.request_device_sync(
                required_features=["timestamp-query"]
            )
            _has_timestamp_query = True
            logger.info("wgpu: timestamp-query enabled (GPU profiling available)")
        except Exception:
            _device = adapter.request_device_sync()
            _has_timestamp_query = False
            logger.info("wgpu: timestamp-query not available on this device")
        info = adapter.info
        logger.info(
            f"wgpu device ready: {info.get('description', '?')} "
            f"[{info.get('backend_type', '?')}] "
            f"adapter_type={info.get('adapter_type', '?')}"
        )
        return _device


def has_gpu_timestamps() -> bool:
    """Return True if the device was created with timestamp-query support.

    When True, render passes can use ``timestamp_writes`` to measure exact
    GPU execution time in nanoseconds.  Query the profiler for usage details.
    """
    return _has_timestamp_query


def destroy_device() -> None:
    """Destroy the wgpu device singleton (called on shutdown)."""
    global _device
    with _device_lock:
        if _device is not None:
            _device.destroy()
            _device = None
            logger.info("wgpu device destroyed")


# ---------------------------------------------------------------------------
# Legacy compatibility shims
# ---------------------------------------------------------------------------

def get_context():
    """Legacy alias — returns the wgpu GPUDevice."""
    return get_device()


def is_context_from_current_thread() -> bool:
    """Always True — wgpu device is thread-safe, no thread affinity."""
    return True


def try_claim_gpu() -> bool:
    """Always succeeds — wgpu device is thread-safe."""
    return True


def release_gpu_ownership() -> None:
    """No-op — wgpu device is thread-safe."""


def _destroy_context_only() -> None:
    """Legacy alias used by reset_gpu_pipeline()."""
    destroy_device()


def destroy_context() -> None:
    """Legacy alias."""
    destroy_device()
