"""
StackSignature — deterministic identity for an effect stack (spec §5.2).

Used as the cache key in Renderer's program cache, replacing the raw GLSL
string.  Captures effect IDs, versions, and order (including duplicates) plus
the pipeline version string (Linear + Straight Alpha).

Phase 1:  StackSignature is used as the LRU cache key in Renderer.
          build_merged_glsl() returns None → Renderer falls back to per-draw
          ping-pong (no merged JIT pass yet).

Phase 3:  Each plugin provides get_apply_glsl() snippet; build_merged_glsl()
          assembles them into one combined fragment shader (single draw call).
"""
import hashlib
from dataclasses import dataclass
from functools import cached_property
from typing import List, Optional, Tuple


# Pipeline version bumped whenever Linear+Straight Alpha invariants or the
# shader ABI change — forces cache invalidation for all stacks.
_PIPELINE_VERSION = '1.0-linear-straight'


@dataclass(frozen=True)
class _EffectEntry:
    """Immutable snapshot of one effect slot in the stack."""
    effect_id: str
    version: str


def _effect_entry(plugin_instance) -> _EffectEntry:
    """Extract _EffectEntry from a plugin instance."""
    meta = getattr(plugin_instance, 'METADATA', {})
    return _EffectEntry(
        effect_id=meta.get('id', type(plugin_instance).__name__),
        version=str(meta.get('version', '1.0')),
    )


class StackSignature:
    """
    Immutable identity of an ordered effect stack.

    Parameters
    ----------
    effects : list
        List of enabled effect plugin instances (order matters; duplicates allowed).
    pipeline_version : str
        Bumped whenever the shader ABI changes.  Default value is the current
        pipeline version (_PIPELINE_VERSION).
    """

    def __init__(
        self,
        effects: list,
        pipeline_version: str = _PIPELINE_VERSION,
    ):
        self._entries: Tuple[_EffectEntry, ...] = tuple(_effect_entry(e) for e in effects)
        self._pipeline_version = pipeline_version

    @cached_property
    def hash(self) -> str:
        """
        16-character hex digest (SHA-256) of (entries, pipeline_version).
        Stable across process restarts for the same stack.
        """
        key = repr(self._entries) + '|' + self._pipeline_version
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @cached_property
    def effect_count(self) -> int:
        return len(self._entries)

    def build_merged_glsl(self) -> Optional[str]:
        """
        Attempt to build a single merged fragment shader for the entire stack.

        Phase 1: always returns None (not yet implemented).
        Phase 3: each effect plugin provides get_apply_glsl() returning a
                 GLSL function body; this method namespacees and concatenates
                 them into one combined pass.

        Returns
        -------
        str or None
            Merged GLSL fragment source if all effects support it, else None.
            Caller falls back to per-draw-call ping-pong when None.
        """
        # TODO Phase 3: collect get_apply_glsl() from each effect instance,
        # assemble into one shader, return combined GLSL source string.
        return None

    def __eq__(self, other) -> bool:
        return isinstance(other, StackSignature) and self.hash == other.hash

    def __hash__(self) -> int:
        return hash(self.hash)

    def __repr__(self) -> str:
        return f"StackSignature(hash={self.hash}, effects={self._entries})"
