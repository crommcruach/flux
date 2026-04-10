"""
System memory snapshot — RAM and VRAM (GPU) usage.

Returns a single dict with three scopes:
  - total   : hardware capacity (MiB)
  - app     : used by this Python process
  - other   : used by the rest of the system  (total_used - app)

VRAM is read via wgpu adapter info when available; falls back to a best-effort
estimate using psutil virtual memory when the adapter does not expose VRAM.
"""
from __future__ import annotations
import os
import sys
from ..core.logger import get_logger

logger = get_logger(__name__)


def _mb(n: int) -> float:
    """Bytes → MiB, rounded to 1 decimal."""
    return round(n / (1024 * 1024), 1)


def get_ram_snapshot() -> dict:
    """Return RAM usage in MiB: total / used / app / other / free."""
    try:
        import psutil
        proc   = psutil.Process(os.getpid())
        vm     = psutil.virtual_memory()

        app_bytes   = proc.memory_info().rss          # resident set size of this process
        total_bytes = vm.total
        used_bytes  = vm.used                         # OS-reported used (all processes)
        free_bytes  = vm.available                    # available to new allocations
        other_bytes = max(0, used_bytes - app_bytes)  # everything except us

        return {
            'total_mb':  _mb(total_bytes),
            'used_mb':   _mb(used_bytes),
            'app_mb':    _mb(app_bytes),
            'other_mb':  _mb(other_bytes),
            'free_mb':   _mb(free_bytes),
            'app_pct':   round(app_bytes  / total_bytes * 100, 1) if total_bytes else 0,
            'used_pct':  round(used_bytes / total_bytes * 100, 1) if total_bytes else 0,
        }
    except Exception as exc:
        logger.debug('get_ram_snapshot failed: %s', exc)
        return {'error': str(exc)}


def get_vram_snapshot() -> dict:
    """Return VRAM usage in MiB for the active wgpu adapter.

    wgpu does not expose a per-process VRAM counter; only the adapter's total
    and a best-effort estimate via Windows DXGI / Vulkan memory budget where
    the driver supports it.  We report:
      - total_mb  : adapter VRAM (from adapter_info)
      - budget_mb : memory budget reported by driver (approx. available to us)
      - used_mb   : total_mb - budget_mb  (rough — may include other apps)
      - app_mb    : not available from wgpu (reported as null)
    """
    try:
        from ..gpu.context import get_device
        device = get_device()
        info   = device.adapter_info          # dict with adapter metadata

        # wgpu exposes memory budget only on some backends/drivers.
        # 'memory_budget' and 'dedicated_video_memory' are optional keys.
        total_bytes  = info.get('dedicated_video_memory',  0)
        budget_bytes = info.get('memory_budget',           0)

        if total_bytes == 0:
            # Integrated GPU — shares system RAM; VRAM is not a separate pool.
            # Report system RAM total as a proxy.
            try:
                import psutil
                total_bytes = psutil.virtual_memory().total
            except Exception:
                pass
            return {
                'integrated': True,
                'total_mb':   _mb(total_bytes),
                'used_mb':    None,   # not separately trackable
                'app_mb':     None,
                'free_mb':    None,
                'note': 'Integrated GPU shares system RAM — see ram.free_mb',
            }

        used_mb  = _mb(total_bytes - budget_bytes) if budget_bytes else None
        free_mb  = _mb(budget_bytes)               if budget_bytes else None

        return {
            'integrated': False,
            'total_mb':  _mb(total_bytes),
            'used_mb':   used_mb,
            'app_mb':    None,    # wgpu does not expose per-process VRAM
            'free_mb':   free_mb,
            'note': 'app_mb not available from wgpu — used_mb includes all GPU processes',
        }
    except Exception as exc:
        logger.debug('get_vram_snapshot failed: %s', exc)
        return {'error': str(exc)}


def get_system_memory_snapshot() -> dict:
    """Combined RAM + VRAM snapshot, safe to call from any thread."""
    return {
        'ram':  get_ram_snapshot(),
        'vram': get_vram_snapshot(),
    }
