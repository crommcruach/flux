"""
TapConfig — immutable tap descriptor (spec §8.3).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Literal, Optional, Union


class TapStage(str, Enum):
    """Pipeline point at which the tap captures a texture."""
    SOURCE_DECODED = 'SourceDecoded'        # after SampleSource, before effect stack (optional)
    LAYER_PROCESSED = 'LayerProcessed'      # after effect stack, before composite
    COMPOSITE_AFTER_N = 'CompositeAfterN'   # after composite step N (0-based)


@dataclass(frozen=True)
class TapConfig:
    """
    Describes a single tap — what to capture, when, and how.

    Parameters
    ----------
    tap_id : str
        Unique string key.  Used to look up results in TapRegistry.
    stage : TapStage
        Pipeline point at which to capture.
    layer_selector : int | list[int]
        Single layer index (int) or list of layer indices (multi-layer).
        Layer indices follow canonical order (low → high) as per spec §8.4.
    mode : 'separate' | 'combined'
        For multi-layer taps:
          separate  → one GPUFrame per matching layer (list[GPUFrame] in registry).
          combined  → layers blended Low→High using Straight Alpha Over → single GPUFrame.
        Ignored for single-layer taps.
    resolution_policy : 'native' | 'output' | 'fixed'
        'output'  → match canvas resolution (default, cheap — no resize).
        'native'  → keep each layer's native resolution (not yet implemented).
        'fixed'   → specific (w, h) via fixed_resolution.
    fixed_resolution : (int, int) | None
        (width, height) when resolution_policy == 'fixed'.
    lifetime_policy : 'frame_ephemeral' | 'persist'
        'frame_ephemeral' → RT released at start of next frame (default).
        'persist'         → RT kept until explicitly unregistered.
    composite_after_n : int | None
        For COMPOSITE_AFTER_N stage: which blend step to capture (0-based).
        0 = after first slave blended onto master; None = final composite.
    """
    tap_id: str
    stage: TapStage
    layer_selector: Union[int, List[int]]
    mode: Literal['separate', 'combined'] = 'combined'
    resolution_policy: Literal['native', 'output', 'fixed'] = 'output'
    fixed_resolution: Optional[tuple] = None
    lifetime_policy: Literal['frame_ephemeral', 'persist'] = 'frame_ephemeral'
    composite_after_n: Optional[int] = None

    def matches_layer(self, layer_id: int) -> bool:
        """True if this tap captures the given layer."""
        if isinstance(self.layer_selector, int):
            return self.layer_selector == layer_id
        return layer_id in self.layer_selector

    def canonical_layer_ids(self) -> List[int]:
        """Return layer_selector as a sorted deduplicated list (spec §8.4)."""
        if isinstance(self.layer_selector, int):
            return [self.layer_selector]
        return sorted(set(self.layer_selector))
