"""
Audio Analyzer

Backend audio analysis service that runs in a separate thread.
Captures audio from microphone, line-in, or system audio and performs real-time FFT analysis.
"""

import sounddevice as sd
import numpy as np
import threading
import logging
from collections import deque
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class AudioAnalyzer:
    """Backend audio analysis service (thread-safe)"""
    
    def __init__(self, device: Optional[int] = None, sample_rate: int = 44100, 
                 block_size: int = 2048, config: Dict[str, Any] = None):
        """
        Initialize audio analyzer
        
        Args:
            device: Audio device index (None = default input)
            sample_rate: Sample rate in Hz
            block_size: FFT block size (power of 2)
            config: Configuration dict with audio source settings
        """
        self.device = device
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.config = config or {}
        
        # Feature cache (thread-safe)
        self._features = {
            'rms': 0.0,
            'peak': 0.0,
            'bass': 0.0,      # 20-250 Hz
            'mid': 0.0,       # 250-4000 Hz
            'treble': 0.0,    # 4000-20000 Hz
            'bpm': 0.0,
            'beat': False
        }
        self._lock = threading.Lock()
        
        # Audio buffer for BPM detection (4 seconds)
        self._audio_buffer = deque(maxlen=sample_rate * 4)
        
        # FFT setup
        self._window = np.hanning(block_size)
        
        # Frequency band indices
        freqs = np.fft.rfftfreq(block_size, 1 / sample_rate)
        self._bass_idx = (freqs >= 20) & (freqs < 250)
        self._mid_idx = (freqs >= 250) & (freqs < 4000)
        self._treble_idx = (freqs >= 4000) & (freqs < 20000)
        
        # Beat detection
        self._last_peak = 0.0
        self._peak_history = deque(maxlen=int(sample_rate / block_size * 2))  # 2 seconds
        
        # Stream
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        
        logger.info(f"AudioAnalyzer initialized: device={device}, rate={sample_rate}, block={block_size}")
    
    def set_device(self, device_index):
        """Set the audio input device
        
        Args:
            device_index: Device index from sounddevice
        """
        self.device = device_index
        logger.info(f"Audio device set to: {device_index}")
    
    def start(self):
        """Start audio capture"""
        if self._running:
            logger.warning("AudioAnalyzer already running")
            return
        
        try:
            # Get audio source from config
            audio_source = self.config.get('audio_source', 'microphone')
            
            # Configure device based on audio source (only if not explicitly set)
            if self.device is None:
                if audio_source == 'system_audio' or audio_source == 'speaker':
                    # On Windows, use WASAPI loopback
                    # This requires sounddevice with WASAPI support
                    logger.info("Using system audio (loopback) as input source")
                    # Note: Device configuration for loopback varies by platform
                    # For Windows WASAPI, we need to find the loopback device
                    self.device = self._find_loopback_device()
                elif audio_source == 'line_in':
                    logger.info("Using line-in as input source")
                    # Use line-in device (usually separate from microphone)
                else:  # 'microphone' or default
                    logger.info("Using microphone as input source")
            
            # Get device info and check supported sample rate
            device_info = sd.query_devices(self.device, 'input') if self.device is not None else sd.query_devices(kind='input')
            logger.info(f"Using audio device: {device_info['name']} (index: {self.device})")
            
            # Use device's default sample rate if our requested rate is not supported
            device_sample_rate = int(device_info.get('default_samplerate', 44100))
            actual_sample_rate = self.sample_rate
            
            # Try to use requested sample rate, fallback to device default if it fails
            try:
                sd.check_input_settings(device=self.device, channels=1, samplerate=self.sample_rate)
                logger.info(f"Using requested sample rate: {self.sample_rate} Hz")
            except sd.PortAudioError:
                logger.warning(f"Sample rate {self.sample_rate} Hz not supported, using device default: {device_sample_rate} Hz")
                actual_sample_rate = device_sample_rate
                # Update internal sample rate and recalculate frequency indices
                self.sample_rate = actual_sample_rate
                freqs = np.fft.rfftfreq(self.block_size, 1 / self.sample_rate)
                self._bass_idx = (freqs >= 20) & (freqs < 250)
                self._mid_idx = (freqs >= 250) & (freqs < 4000)
                self._treble_idx = (freqs >= 4000) & (freqs < 20000)
                self._audio_buffer = deque(maxlen=self.sample_rate * 4)
                self._peak_history = deque(maxlen=int(self.sample_rate / self.block_size * 2))
            
            self._stream = sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=actual_sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback
            )
            self._stream.start()
            self._running = True
            logger.info(f"AudioAnalyzer started successfully (source: {audio_source}, rate: {actual_sample_rate} Hz)")
        
        except Exception as e:
            logger.error(f"Failed to start AudioAnalyzer: {e}", exc_info=True)
            self._running = False
    
    def stop(self):
        """Stop audio capture"""
        if not self._running:
            return
        
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self._running = False
            logger.info("AudioAnalyzer stopped")
        except Exception as e:
            logger.error(f"Error stopping AudioAnalyzer: {e}", exc_info=True)
    
    def _find_loopback_device(self) -> Optional[int]:
        """
        Find loopback device for system audio capture
        
        Returns:
            Device index or None for default
        """
        try:
            devices = sd.query_devices()
            for idx, device in enumerate(devices):
                # Look for loopback devices (Windows WASAPI)
                if 'loopback' in device['name'].lower() or 'stereo mix' in device['name'].lower():
                    logger.info(f"Found loopback device: {device['name']} (index {idx})")
                    return idx
            
            logger.warning("No loopback device found, using default input")
            return None
        except Exception as e:
            logger.error(f"Error finding loopback device: {e}")
            return None
    
    def _audio_callback(self, indata, frames, time, status):
        """
        Audio thread callback (DO NOT BLOCK!)
        
        Args:
            indata: Input audio data
            frames: Number of frames
            time: Timestamp info
            status: Status flags
        """
        if status:
            logger.debug(f"Audio callback status: {status}")
        
        try:
            # Convert to mono
            audio = indata[:, 0] if indata.shape[1] > 0 else indata.flatten()
            
            # Add to buffer for BPM detection
            self._audio_buffer.extend(audio)
            
            # Calculate RMS (Root Mean Square)
            rms = float(np.sqrt(np.mean(audio**2)))
            
            # Calculate Peak
            peak = float(np.max(np.abs(audio)))
            
            # FFT Analysis
            windowed = audio * self._window
            fft = np.fft.rfft(windowed)
            magnitude = np.abs(fft)
            
            # Frequency bands
            bass = float(np.mean(magnitude[self._bass_idx])) if np.any(self._bass_idx) else 0.0
            mid = float(np.mean(magnitude[self._mid_idx])) if np.any(self._mid_idx) else 0.0
            treble = float(np.mean(magnitude[self._treble_idx])) if np.any(self._treble_idx) else 0.0
            
            # Normalize to 0-1 range (adjust scaling as needed)
            bass_norm = np.clip(bass / 100, 0, 1)
            mid_norm = np.clip(mid / 50, 0, 1)
            treble_norm = np.clip(treble / 20, 0, 1)
            
            # Simple beat detection (threshold-based)
            # Compare current peak to recent average
            self._peak_history.append(peak)
            avg_peak = np.mean(self._peak_history) if self._peak_history else 0.0
            beat = peak > avg_peak * 1.5 and peak > 0.3  # Beat if significantly above average
            
            # Log beat detection
            if beat:
                if not hasattr(self, '_beat_counter'):
                    self._beat_counter = 0
                self._beat_counter += 1
                # Log every 5th beat to avoid spam
                if self._beat_counter % 5 == 0:
                    logger.info(f"🥁 BEAT detected! peak={peak:.3f}, avg={avg_peak:.3f}, bass={bass_norm:.3f}")
            
            # Update features (thread-safe) - convert numpy types to Python native types
            with self._lock:
                self._features['rms'] = float(rms)
                self._features['peak'] = float(peak)
                self._features['bass'] = float(bass_norm)
                self._features['mid'] = float(mid_norm)
                self._features['treble'] = float(treble_norm)
                self._features['beat'] = bool(beat)  # Convert numpy bool to Python bool
                # BPM detection would go here (complex, optional for now)
                
                # Log audio features periodically
                if not hasattr(self, '_feature_log_counter'):
                    self._feature_log_counter = 0
                self._feature_log_counter += 1
                # Log every 100 callbacks (~2.3 seconds at 44100Hz/2048 block)
                if self._feature_log_counter % 100 == 0:
                    logger.debug(f"🎵 Audio features: rms={rms:.3f}, peak={peak:.3f}, bass={bass_norm:.3f}, mid={mid_norm:.3f}, treble={treble_norm:.3f}")
        
        except Exception as e:
            logger.error(f"Error in audio callback: {e}", exc_info=True)
    
    def get_features(self) -> Dict[str, float]:
        """
        Get current audio features (thread-safe)
        
        Returns:
            Dictionary of audio features
        """
        with self._lock:
            return self._features.copy()
    
    def is_running(self) -> bool:
        """Check if analyzer is running"""
        return self._running
    
    @staticmethod
    def list_devices() -> list:
        """
        List available audio input devices
        
        Returns:
            List of device dictionaries
        """
        try:
            devices = sd.query_devices()
            input_devices = []
            
            for idx, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append({
                        'index': idx,
                        'name': device['name'],
                        'channels': device['max_input_channels'],
                        'sample_rate': device['default_samplerate']
                    })
            
            return input_devices
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}", exc_info=True)
            return []
    
    def set_device(self, device: Optional[int]):
        """
        Change audio input device
        
        Args:
            device: Device index or None for default
        """
        was_running = self._running
        
        if was_running:
            self.stop()
        
        self.device = device
        
        if was_running:
            self.start()
        
        logger.info(f"Audio device changed to: {device}")
    
    def __del__(self):
        """Cleanup on destruction"""
        self.stop()
