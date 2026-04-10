"""
Frame Sources package — re-exports all public source classes.

Sub-modules:
    base        — FrameSource (ABC)
    video       — VideoSource (memmap .npy arrays)
    generator   — GeneratorSource (WGSL-shader GPU generators)
    dummy       — DummySource (black-frame placeholder)
"""
from .base import FrameSource
from .video import VideoSource
from .generator import GeneratorSource
from .dummy import DummySource

__all__ = ['FrameSource', 'VideoSource', 'GeneratorSource', 'DummySource']
