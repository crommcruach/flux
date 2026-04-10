"""Layer management package.

Sub-modules:
    layer.py       — Layer dataclass
    manager.py     — LayerManager (lifecycle, delegates to sub-modules)
    effects.py     — GPU shader effect pipeline
    compositor.py  — GPU ping-pong blend compositor + ring-buffer download
    slave.py       — Per-slave FPS-throttled decode + effects
"""
from .manager import LayerManager, _GPU_PROCESSED  # noqa: F401

__all__ = ['LayerManager', '_GPU_PROCESSED']
