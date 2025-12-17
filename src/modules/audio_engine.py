"""
Audio Engine - Wrapper around miniaudio for audio playback

Provides simple API for:
- Loading audio files (MP3, WAV, OGG, FLAC)
- Playback control (play/pause/stop/seek)
- Thread-safe position tracking
- Duration and metadata extraction
"""

import miniaudio
import threading
import time
from pathlib import Path
from typing import Optional, Dict
from .logger import get_logger

logger = get_logger(__name__)


class AudioEngine:
    """Manages audio file playback using miniaudio"""
    
    def __init__(self):
        self.device: Optional[miniaudio.PlaybackDevice] = None
        self.decoder: Optional[miniaudio.DecodedSoundFile] = None
        self.current_position = 0.0  # seconds
        self.duration = 0.0
        self.is_playing = False
        self.is_loaded = False
        self._lock = threading.Lock()
        self._stream_thread: Optional[threading.Thread] = None
        self._stop_stream = False
        self._file_path: Optional[str] = None
        
    def load(self, file_path: str) -> Dict:
        """Load audio file and return metadata
        
        Args:
            file_path: Path to audio file (MP3, WAV, OGG, FLAC, M4A, AAC)
            
        Returns:
            Dictionary with duration, sample_rate, channels, format
            
        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: If file cannot be decoded
        """
        try:
            if not Path(file_path).exists():
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            # Stop any existing playback
            self.stop()
            
            # Decode audio file
            self.decoder = miniaudio.decode_file(file_path)
            self.duration = self.decoder.num_frames / self.decoder.sample_rate
            self.is_loaded = True
            self.current_position = 0.0
            self._file_path = file_path
            
            # Initialize playback device
            if self.device is None:
                self.device = miniaudio.PlaybackDevice(
                    sample_rate=self.decoder.sample_rate,
                    nchannels=self.decoder.nchannels,
                    output_format=self.decoder.sample_format
                )
            
            metadata = {
                'duration': self.duration,
                'sample_rate': self.decoder.sample_rate,
                'channels': self.decoder.nchannels,
                'format': str(self.decoder.sample_format),
                'num_frames': self.decoder.num_frames
            }
            
            logger.info(f"🎵 Audio loaded: {Path(file_path).name} ({self.duration:.2f}s, {self.decoder.sample_rate}Hz)")
            return metadata
            
        except Exception as e:
            logger.error(f"❌ Failed to load audio: {e}")
            raise Exception(f"Failed to load audio: {e}")
    
    def play(self):
        """Start/resume playback
        
        Raises:
            Exception: If no audio is loaded
        """
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        with self._lock:
            if not self.is_playing:
                self.is_playing = True
                self._stop_stream = False
                self._start_stream()
                logger.debug(f"▶️ Playback started at {self.current_position:.2f}s")
    
    def pause(self):
        """Pause playback"""
        with self._lock:
            if self.is_playing:
                self.is_playing = False
                self._stop_stream = True
                logger.debug(f"⏸️ Playback paused at {self.current_position:.2f}s")
    
    def stop(self):
        """Stop playback and reset position"""
        with self._lock:
            self.is_playing = False
            self._stop_stream = True
            self.current_position = 0.0
            
            # Wait for stream thread to finish
            if self._stream_thread and self._stream_thread.is_alive():
                self._stream_thread.join(timeout=0.5)
            
            logger.debug("⏹️ Playback stopped")
    
    def seek(self, position: float):
        """Seek to position in seconds
        
        Args:
            position: Target position in seconds (clamped to valid range)
        """
        if not self.is_loaded:
            raise Exception("No audio loaded")
        
        position = max(0.0, min(position, self.duration))
        
        was_playing = self.is_playing
        
        # Stop playback
        if was_playing:
            self.pause()
        
        with self._lock:
            self.current_position = position
            logger.debug(f"⏩ Seek to {position:.2f}s")
        
        # Resume if was playing
        if was_playing:
            self.play()
    
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
    
    def _start_stream(self):
        """Internal: Start audio streaming thread"""
        if self._stream_thread and self._stream_thread.is_alive():
            return
        
        self._stream_thread = threading.Thread(target=self._stream_audio, daemon=True)
        self._stream_thread.start()
    
    def _stream_audio(self):
        """Internal: Audio streaming loop (runs in separate thread)"""
        try:
            start_position = self.current_position
            
            # Simplified approach: Always decode fresh, use file_stream for proper seeking
            # This avoids all the DecodedSoundFile internal state issues
            
            # Track when playback started
            playback_start = time.time()
            
            # Use stream_file which handles seeking internally
            # This is the most compatible approach with miniaudio
            try:
                # Create a file stream (supports seeking natively)
                file_stream = miniaudio.stream_file(
                    self._file_path,
                    sample_rate=self.decoder.sample_rate,
                    nchannels=self.decoder.nchannels,
                    output_format=self.decoder.sample_format
                )
                
                # For seeking: we'll manually skip samples in the stream
                if start_position > 0:
                    # Calculate samples to skip
                    samples_to_skip = int(start_position * self.decoder.sample_rate * self.decoder.nchannels)
                    
                    # Read and discard samples (seeking)
                    chunk_size = 4096
                    while samples_to_skip > 0 and not self._stop_stream:
                        skip_now = min(chunk_size, samples_to_skip)
                        try:
                            next(file_stream)  # Advance stream
                        except StopIteration:
                            break
                        samples_to_skip -= skip_now
                
                # Start playback
                self.device.start(file_stream)
                
                # Monitor position while playing
                while self.is_playing and not self._stop_stream:
                    elapsed = time.time() - playback_start
                    with self._lock:
                        self.current_position = start_position + elapsed
                        
                        if self.current_position >= self.duration:
                            self.is_playing = False
                            self.current_position = self.duration
                            logger.debug("🏁 Playback finished")
                            break
                    
                    time.sleep(0.05)
                
                # Stop if interrupted
                if self._stop_stream:
                    self.device.stop()
                    
            except AttributeError:
                # Fallback: stream_file might not exist in this miniaudio version
                # Use simple decode approach (no seeking support)
                logger.warning("⚠️ stream_file not available, using decode (no seek support)")
                
                if start_position > 0:
                    logger.warning(f"⚠️ Seeking from {start_position:.2f}s not supported in fallback mode")
                    start_position = 0
                
                # Decode entire file
                sound = miniaudio.decode_file(self._file_path)
                
                # Start streaming
                self.device.start(miniaudio.stream_any(sound))
                
                # Monitor position
                while self.is_playing and not self._stop_stream:
                    elapsed = time.time() - playback_start
                    with self._lock:
                        self.current_position = elapsed
                        
                        if self.current_position >= self.duration:
                            self.is_playing = False
                            self.current_position = self.duration
                            logger.debug("🏁 Playback finished")
                            break
                    
                    time.sleep(0.05)
                
                if self._stop_stream:
                    self.device.stop()
                        
        except Exception as e:
            logger.error(f"❌ Stream error: {e}")
            self.is_playing = False
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop()
        if self.device:
            self.device.close()
            self.device = None
        self.decoder = None
        self.is_loaded = False
