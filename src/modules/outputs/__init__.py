"""
Output routing system for Flux
Manages multiple video outputs (displays, NDI, Spout) with slice support
"""

from .output_manager import OutputManager
from .slice_manager import SliceManager, SliceDefinition
from .output_base import OutputBase

__all__ = ['OutputManager', 'SliceManager', 'SliceDefinition', 'OutputBase']
