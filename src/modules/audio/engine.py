"""
Audio Engine - Audio playback using PyAV + sounddevice

Provides simple API for:
- Loading audio files (MP3, WAV, OGG, FLAC, M4A, AAC)
- Playback control (play/pause/stop/seek)
- Thread-safe position tracking
- Duration and metadata extraction

Uses existing dependencies:
- PyAV (av) for audio decoding (FFmpeg bindings)
- sounddevice for audio output (PortAudio)
"""

import threading
import time
import queue
from pathlib import Path
from typing import Optional, Dict
import numpy as np
from ..core.logger import get_logger

# Try importing audio dependencies
try:
    import av
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False
    
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

AUDIO_AVAILABLE = AV_AVAILABLE and SOUNDDEVICE_AVAILABLE

logger = get_logger(__name__)

if not AUDIO_AVAILABLE:
    if not AV_AVAILABLE:
        logger.warning("⚠️ PyAV (av) not available - audio playback disabled")
    if not SOUNDDEVICE_AVAILABLE:
        logger.warning("⚠️ sounddevice not available - audio playback disabled")


class AudioEngine:
    """Manages audio file playback using PyAV + sounddevice"""
    
    def __init__(self):
        self.stream: Optional[sd.OutputStream] = None if SOUNDDEVICE_AVAILABLE else None
        self.container: Optional[av.container.InputContainer] = None if AV_AVAILABLE else None
        self.audio_stream = None
        self.sample_rate = 44100
        self.channels = 2
        self.current_position = 0.0  # seconds
        self.duration = 0.0
        self.is_playing = False
        self.is_loaded = False
        self._lock = threading.Lock()
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_playback = False
        self._file_path: Optional[str] = None
        self._audio_queue = queue.Queue(maxsize=10) if AUDIO_AVAILABLE else None
        self._seek_requested = False
        self._seek_position = 0.0
        
    def load(self, file_path: str) -> Dict:
        """Load audio file and return metadata
        
        Args:
            file_path: Path to audio file (MP3, WAV, OGG, FLAC, M4A, AAC)
            
        Returns:
            Dictionary with duration, sample_rate, channels, format
            
        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If file cannot be decoded or audio not available
        """
        if not AUDIO_AVAILABLE:
            raise Exception("Audio playback not available (PyAV or sounddevice missing)")
        
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            # Stop any existing playback
            self.stop()
            
            # Open audio file with PyAV
            self.container = av.open(file_path)
            
            # Get audio stream
            if not self.container.streams.audio:
                raise Exception("No audio stream found in file")
            
            self.audio_stream = self.container.streams.audio[0]
            
            # Get metadata
            self.duration = float(self.audio_stream.duration * self.audio_stream.time_base)
            self.sample_rate = self.audio_stream.rate
            self.channels = self.audio_stream.channels
            
            self.is_loaded = True
            self.current_position = 0.0
            self._file_path = file_path
            
            metadata = {
                'duration': self.duration,
                'sample_rate': self.sample_rate,
                'channels': self.channels,
                'format': str(self.audio_stream.format),
                'num_frames': int(self.duration * self.sample_rate)
            }
            
            logger.info(f"🎵 Audio loaded: {Path(file_path).name} ({self.duration:.2f}s, {self.sample_rate}Hz, {self.channels}ch)")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to load audio: {e}")
            self.is_loaded = False
            raise Exception(f"Failed to load audio: {e}")
    
    def play(self):
        """Start/resume playback
        
        Raises:
            Exception: If no audio is loaded or audio not available
        """
        if not AUDIO_AVAILABLE:
            logger.warning("⚠️ Audio playback not available")
            return
        
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        with self._lock:
            if not self.is_playing:
                self.is_playing = True
                self._stop_playback = False
                self._start_playback()
                logger.debug(f"▶️ Playback started at {self.current_position:.2f}s")
    
    def pause(self):
        """Pause playback"""
        if not AUDIO_AVAILABLE:
            return
        
        with self._lock:
            if self.is_playing:
                self.is_playing = False
                self._stop_playback = True
                if self.stream:
                    self.stream.stop()
                logger.debug(f"⏸️ Playback paused at {self.current_position:.2f}s")
    
    def stop(self):
        """Stop playback and reset position"""
        if not AUDIO_AVAILABLE:
            return
        
        with self._lock:
            self.is_playing = False
            self._stop_playback = True
            self.current_position = 0.0
            
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            # Wait for playback thread to finish
            if self._playback_thread and self._playback_thread.is_alive():
                self._playback_thread.join(timeout=0.5)
            
            # Clear audio queue
            if self._audio_queue:
                while not self._audio_queue.empty():
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        break
            
            logger.debug("⏹️ Playback stopped")
    
    def seek(self, position: float):
        """Seek to position in seconds
        
        Args:
            position: Target position in seconds (clamped to valid range)
        """
        if not AUDIO_AVAILABLE:
            return
        
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        position = max(0.0, min(position, self.duration))
        
        with self._lock:
            self._seek_requested = True
            self._seek_position = position
            self.current_position = position
            
            # Clear audio queue
            if self._audio_queue:
                while not self._audio_queue.empty():
                    try:
                        self._audio_queue.get_nowait()
                    except queue.Empty:
                        break
            
            logger.debug(f"⏩ Seek to {position:.2f}s")
    
    def get_position(self) -> float:
        """Get current playback position in seconds
        
        Returns:
            Current position in seconds
        """
        with self._lock:
            return self.current_position
    
    def get_duration(self) -> float:
        """Get total duration in seconds
        
        Returns:
            Duration in seconds (0.0 if no audio loaded)
        """
        return self.duration
    
    def _start_playback(self):
        """Internal: Start audio playback thread"""
        if self._playback_thread and self._playback_thread.is_alive():
            return
        
        self._playback_thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._playback_thread.start()
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """Callback for sounddevice OutputStream"""
        if status:
            logger.warning(f"⚠️ Audio callback status: {status}")
        
        try:
            # Get audio data from queue (non-blocking)
            data = self._audio_queue.get_nowait()
            
            # Ensure correct shape (frames, channels)
            if data.shape[0] < frames:
                # Pad with zeros if not enough data
                padded = np.zeros((frames, self.channels), dtype=np.float32)
                padded[:data.shape[0]] = data
                outdata[:] = padded
            else:
                # Use requested frames
                outdata[:] = data[:frames]
                
        except queue.Empty:
            # No data available - output silence
            outdata[:] = np.zeros((frames, self.channels), dtype=np.float32)
    
    def _playback_loop(self):
        """Internal: Audio decoding and playback loop (runs in separate thread)"""
        container = None
        try:
            start_position = self.current_position
            
            # Reopen container for fresh stream
            container = av.open(self._file_path)
            audio_stream = container.streams.audio[0]
            
            # Seek to start position if needed
            if start_position > 0:
                timestamp = int(start_position / audio_stream.time_base)
                container.seek(timestamp, stream=audio_stream)
            
            # Create sounddevice output stream
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                callback=self._audio_callback,
                dtype=np.float32
            )
            self.stream.start()
            
            # Track playback timing
            playback_start = time.time()
            frames_decoded = 0
            
            # Decode and queue audio frames
            for frame in container.decode(audio_stream):
                # Check for stop/seek
                if self._stop_playback:
                    break
                
                if self._seek_requested:
                    with self._lock:
                        self._seek_requested = False
                        seek_pos = self._seek_position
                    
                    # Perform seek
                    timestamp = int(seek_pos / audio_stream.time_base)
                    container.seek(timestamp, stream=audio_stream)
                    start_position = seek_pos
                    playback_start = time.time()
                    frames_decoded = 0
                    continue
                
                # Convert frame to numpy array
                audio_data = frame.to_ndarray()
                
                # Ensure correct shape: (samples, channels)
                if audio_data.ndim == 1:
                    # Mono - reshape to (samples, 1)
                    audio_data = audio_data.reshape(-1, 1)
                elif audio_data.shape[0] == self.channels:
                    # Channels first - transpose to (samples, channels)
                    audio_data = audio_data.T
                
                # Convert to float32 if needed
                if audio_data.dtype != np.float32:
                    if np.issubdtype(audio_data.dtype, np.integer):
                        # Convert integer to float (-1.0 to 1.0)
                        info = np.iinfo(audio_data.dtype)
                        audio_data = audio_data.astype(np.float32) / max(abs(info.min), abs(info.max))
                    else:
                        audio_data = audio_data.astype(np.float32)
                
                # Ensure correct channel count
                if audio_data.shape[1] != self.channels:
                    if audio_data.shape[1] == 1 and self.channels == 2:
                        # Mono to stereo - duplicate channel
                        audio_data = np.repeat(audio_data, 2, axis=1)
                    elif audio_data.shape[1] == 2 and self.channels == 1:
                        # Stereo to mono - average channels
                        audio_data = np.mean(audio_data, axis=1, keepdims=True)
                
                # Queue audio data (blocking if queue full)
                try:
                    self._audio_queue.put(audio_data, timeout=1.0)
                except queue.Full:
                    if self._stop_playback:
                        break
                    continue
                
                # Update position
                frames_decoded += audio_data.shape[0]
                elapsed = frames_decoded / self.sample_rate
                with self._lock:
                    self.current_position = start_position + elapsed
                
                # Check if reached end
                if self.current_position >= self.duration:
                    break
            
            # Playback finished
            with self._lock:
                self.is_playing = False
                self.current_position = min(self.current_position, self.duration)
            
            logger.debug("🏁 Playback finished")
            
            # Wait for audio queue to drain
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"❌ Playback error: {e}")
            with self._lock:
                self.is_playing = False
        finally:
            # Cleanup
            if self.stream:
                try:
                    self.stream.stop()
                except:
                    pass
            
            if container:
                try:
                    container.close()
                except:
                    pass
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        if self.stream:
            self.stream.close()
            self.stream = None
        if self.container:
            self.container.close()
            self.container = None
        self.audio_stream = None
        self.is_loaded = False
