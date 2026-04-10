"""
Frame Sources — backward-compatibility shim.

All source classes now live in the `sources/` sub-package.
This module re-exports them so existing imports continue to work::

    from .sources import VideoSource, GeneratorSource, DummySource, FrameSource
"""
from .sources import FrameSource, VideoSource, GeneratorSource, DummySource  # noqa: F401

__all__ = ['FrameSource', 'VideoSource', 'GeneratorSource', 'DummySource']
