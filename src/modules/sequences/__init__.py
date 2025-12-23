"""
Dynamic Parameter Sequences Module

Provides automated parameter modulation through:
- Audio Reactive: Bind parameters to audio features (Bass, RMS, Peak, etc.)
- LFO: Low Frequency Oscillator with multiple waveforms
- Timeline: Keyframe-based animation
- Envelope: ADSR envelope modulation
"""

from .base_sequence import BaseSequence
from .sequence_manager import SequenceManager
from .audio_analyzer import AudioAnalyzer
from .audio_sequence import AudioSequence
from .lfo_sequence import LFOSequence
from .timeline_sequence import TimelineSequence

__all__ = [
    'BaseSequence',
    'SequenceManager',
    'AudioAnalyzer',
    'AudioSequence',
    'LFOSequence',
    'TimelineSequence',
]
