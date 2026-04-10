"""
Tap system — formal Layer Abgriff (spec §8).

Provides per-frame capture of layer textures at defined pipeline stages,
with RT pinning so the TexturePool does not reclaim them mid-frame.

Usage (from LayerManager)::

    tap_cfg = TapConfig(tap_id='led_strip_1', stage=TapStage.LAYER_PROCESSED, layer_selector=0)
    layer_manager.register_tap(tap_cfg)

    # Each frame, after composite_layers():
    frame = layer_manager.tap_registry.get('led_strip_1')  # GPUFrame or None
"""
from .config import TapStage, TapConfig
from .registry import TapRegistry

__all__ = ['TapStage', 'TapConfig', 'TapRegistry']
