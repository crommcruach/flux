# BPM Detection System - Implementation Guide

## Overview

This document describes the implementation of a **comprehensive BPM (Beats Per Minute) detection system** for the Flux Art-Net system, supporting multiple input sources with all core logic in the backend.

## Goals

- Detect BPM from **line-in/microphone** audio input (real-time)
- Detect BPM from **sequencer audio** (loaded files)
- **Tap tempo** functionality (manual BPM input)
- **All core logic in backend** (Python audio processing)
- **Frontend visualization only** (BPM display, beat indicators, tap button)
- Real-time updates via WebSocket
- Smooth BPM averaging and stabilization
- Beat synchronization for effects/transitions

## BPM Detection Methods

### 1. Audio Input Detection (Line-In/Mic)
- Real-time audio capture from system audio devices
- Onset detection algorithm (spectral flux, energy-based)
- Tempo estimation using autocorrelation
- Continuous monitoring with configurable latency

### 2. Sequencer File Analysis
- Analyze loaded audio file in sequencer
- Full-file BPM detection (more accurate than real-time)
- Cache BPM per file for instant recall
- Beat grid generation for quantization

### 3. Tap Tempo
- Manual BPM entry by tapping beat
- Average of last 4-8 taps
- Smoothing algorithm for human timing variance
- Auto-reset after timeout (>3 seconds)

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Python)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         BPM Detection Engine                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │   │
│  │  │ Audio Input  │  │  Sequencer   │  │   Tap    │  │   │
│  │  │  Detector    │  │   Analyzer   │  │  Tempo   │  │   │
│  │  │  (librosa)   │  │  (librosa)   │  │          │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └─────┬────┘  │   │
│  │         │                  │                 │       │   │
│  │         └──────────────────┴─────────────────┘       │   │
│  │                           │                          │   │
│  │                    ┌──────▼────────┐                 │   │
│  │                    │  BPM Manager  │                 │   │
│  │                    │  - Smoothing  │                 │   │
│  │                    │  - Averaging  │                 │   │
│  │                    │  - Beats      │                 │   │
│  │                    └──────┬────────┘                 │   │
│  └───────────────────────────┼──────────────────────────┘   │
│                               │                              │
│  ┌────────────────────────────▼──────────────────────────┐  │
│  │              REST API & WebSocket                     │  │
│  │  /api/bpm/start-input     /ws/bpm (real-time)        │  │
│  │  /api/bpm/analyze-file    /api/bpm/tap               │  │
│  │  /api/bpm/stop            /api/bpm/status            │  │
│  └────────────────────────────┬──────────────────────────┘  │
│                               │                              │
└───────────────────────────────┼──────────────────────────────┘
                                │
                                ▼ WebSocket Stream
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (JavaScript)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │  BPM Display    │◀────────│  WebSocket       │          │
│  │  - Current BPM  │         │  Client          │          │
│  │  - Beat Pulse   │         └──────────────────┘          │
│  │  - Source       │                                        │
│  └─────────────────┘         ┌──────────────────┐          │
│                              │  Tap Tempo UI    │          │
│  ┌─────────────────┐         │  - Tap Button    │          │
│  │  Source Select  │         │  - Visual Guide  │          │
│  │  ○ Line In      │         └──────────────────┘          │
│  │  ○ Sequencer    │                                        │
│  │  ○ Tap Tempo    │         ┌──────────────────┐          │
│  └─────────────────┘         │  Beat Indicator  │          │
│                              │  ● ○ ○ ○         │          │
│                              └──────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Backend - BPM Detection Engine

#### 1.1 Install Dependencies

**File:** `requirements.txt`

Add audio processing libraries:

```txt
librosa>=0.10.0
sounddevice>=0.4.6
numpy>=1.24.0
scipy>=1.11.0
```

Install:
```bash
pip install librosa sounddevice numpy scipy
```

#### 1.2 Create BPM Detection Module

**File:** `src/modules/bpm_detector.py`

```python
"""
BPM Detection Module
Detects BPM from audio input, files, and tap tempo.
"""

import librosa
import numpy as np
import sounddevice as sd
import threading
import time
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

class BPMDetector:
    """Core BPM detection engine."""
    
    def __init__(self):
        self.current_bpm = 0.0
        self.beat_times = deque(maxlen=100)  # Last 100 beats
        self.source = None  # 'input', 'sequencer', 'tap'
        self.is_running = False
        self.confidence = 0.0
        
        # Audio input detection
        self.audio_thread = None
        self.audio_buffer = deque(maxlen=88200)  # 2 seconds at 44.1kHz
        self.sample_rate = 44100
        
        # Tap tempo
        self.tap_times = deque(maxlen=8)
        self.tap_timeout = 3.0  # Reset after 3 seconds
        
        # Smoothing
        self.bpm_history = deque(maxlen=10)
    
    def start_audio_input(self, device_id=None):
        """Start real-time BPM detection from audio input."""
        if self.is_running:
            logger.warning("BPM detection already running")
            return
        
        self.is_running = True
        self.source = 'input'
        self.audio_buffer.clear()
        
        # Start audio capture thread
        self.audio_thread = threading.Thread(
            target=self._audio_input_loop,
            args=(device_id,),
            daemon=True
        )
        self.audio_thread.start()
        logger.info(f"🎵 Started audio input BPM detection (device: {device_id})")
    
    def stop(self):
        """Stop BPM detection."""
        self.is_running = False
        if self.audio_thread:
            self.audio_thread.join(timeout=2)
        logger.info("🎵 Stopped BPM detection")
    
    def _audio_input_loop(self, device_id):
        """Audio input capture and analysis loop."""
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Audio input status: {status}")
            # Store audio data (mono, first channel)
            self.audio_buffer.extend(indata[:, 0])
        
        try:
            with sd.InputStream(
                device=device_id,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=2048,
                callback=audio_callback
            ):
                logger.info("🎤 Audio input stream started")
                
                while self.is_running:
                    # Analyze buffer every 0.5 seconds
                    time.sleep(0.5)
                    
                    if len(self.audio_buffer) >= self.sample_rate:
                        # Convert to numpy array
                        audio_data = np.array(list(self.audio_buffer))
                        
                        # Detect BPM
                        bpm, confidence = self._detect_bpm_realtime(audio_data)
                        
                        if bpm > 0:
                            self._update_bpm(bpm, confidence)
        
        except Exception as e:
            logger.error(f"Audio input error: {e}")
            self.is_running = False
    
    def _detect_bpm_realtime(self, audio_data):
        """
        Real-time BPM detection using onset detection.
        
        Args:
            audio_data: Audio samples (1D numpy array)
        
        Returns:
            tuple: (bpm, confidence)
        """
        try:
            # Onset detection (spectral flux)
            onset_env = librosa.onset.onset_strength(
                y=audio_data,
                sr=self.sample_rate,
                aggregate=np.median
            )
            
            # Tempo estimation
            tempo, beats = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=self.sample_rate,
                units='time'
            )
            
            # Calculate confidence based on beat consistency
            if len(beats) > 2:
                intervals = np.diff(beats)
                confidence = 1.0 - (np.std(intervals) / np.mean(intervals))
                confidence = max(0.0, min(1.0, confidence))
            else:
                confidence = 0.0
            
            return float(tempo), confidence
        
        except Exception as e:
            logger.error(f"BPM detection error: {e}")
            return 0.0, 0.0
    
    def analyze_file(self, audio_file_path):
        """
        Analyze audio file for BPM (more accurate than real-time).
        
        Args:
            audio_file_path: Path to audio file
        
        Returns:
            dict: {'bpm': float, 'confidence': float, 'beats': list}
        """
        try:
            logger.info(f"🎵 Analyzing file: {audio_file_path}")
            
            # Load audio file
            y, sr = librosa.load(audio_file_path, sr=None, mono=True)
            
            # Onset detection
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            
            # Tempo and beat detection
            tempo, beats = librosa.beat.beat_track(
                onset_envelope=onset_env,
                sr=sr,
                units='time'
            )
            
            # Calculate confidence
            if len(beats) > 2:
                intervals = np.diff(beats)
                confidence = 1.0 - (np.std(intervals) / np.mean(intervals))
                confidence = max(0.0, min(1.0, confidence))
            else:
                confidence = 0.0
            
            self.current_bpm = float(tempo)
            self.confidence = confidence
            self.source = 'sequencer'
            self.beat_times = deque(beats.tolist(), maxlen=100)
            
            logger.info(f"✅ Detected BPM: {tempo:.1f} (confidence: {confidence:.2f})")
            
            return {
                'bpm': float(tempo),
                'confidence': confidence,
                'beats': beats.tolist(),
                'duration': len(y) / sr
            }
        
        except Exception as e:
            logger.error(f"File analysis error: {e}")
            return {'bpm': 0.0, 'confidence': 0.0, 'beats': [], 'duration': 0.0}
    
    def tap(self):
        """
        Record a tap for tap tempo.
        
        Returns:
            float: Current tap tempo BPM (0 if not enough taps)
        """
        now = time.time()
        
        # Check for timeout (reset if too long since last tap)
        if len(self.tap_times) > 0:
            if now - self.tap_times[-1] > self.tap_timeout:
                self.tap_times.clear()
                logger.debug("🥁 Tap tempo reset (timeout)")
        
        # Add tap
        self.tap_times.append(now)
        
        # Calculate BPM if we have enough taps
        if len(self.tap_times) >= 2:
            intervals = [
                self.tap_times[i] - self.tap_times[i-1]
                for i in range(1, len(self.tap_times))
            ]
            
            # Average interval
            avg_interval = np.mean(intervals)
            
            # Convert to BPM
            bpm = 60.0 / avg_interval if avg_interval > 0 else 0.0
            
            # Update
            self.current_bpm = bpm
            self.confidence = len(self.tap_times) / 8.0  # Confidence increases with taps
            self.source = 'tap'
            
            logger.debug(f"🥁 Tap tempo: {bpm:.1f} BPM ({len(self.tap_times)} taps)")
            
            return bpm
        
        return 0.0
    
    def _update_bpm(self, bpm, confidence):
        """Update BPM with smoothing."""
        # Add to history
        self.bpm_history.append(bpm)
        
        # Smooth BPM (weighted average)
        if len(self.bpm_history) >= 3:
            weights = np.linspace(0.5, 1.0, len(self.bpm_history))
            smoothed_bpm = np.average(list(self.bpm_history), weights=weights)
        else:
            smoothed_bpm = bpm
        
        self.current_bpm = smoothed_bpm
        self.confidence = confidence
    
    def get_status(self):
        """Get current BPM status."""
        return {
            'bpm': round(self.current_bpm, 1),
            'confidence': round(self.confidence, 2),
            'source': self.source,
            'is_running': self.is_running,
            'beat_count': len(self.beat_times),
            'tap_count': len(self.tap_times)
        }
    
    def get_beat_phase(self):
        """
        Get current beat phase (0.0 to 1.0).
        Useful for syncing effects/transitions to beat.
        
        Returns:
            float: Phase within current beat (0.0 = on beat, 0.5 = half beat)
        """
        if self.current_bpm == 0:
            return 0.0
        
        beat_duration = 60.0 / self.current_bpm
        current_time = time.time()
        
        # Use last known beat time if available
        if len(self.beat_times) > 0:
            last_beat = self.beat_times[-1]
            phase = (current_time - last_beat) % beat_duration / beat_duration
            return phase
        
        # Fallback: use current time
        phase = (current_time % beat_duration) / beat_duration
        return phase


# Global instance
_bpm_detector = None

def get_bpm_detector():
    """Get global BPM detector instance."""
    global _bpm_detector
    if _bpm_detector is None:
        _bpm_detector = BPMDetector()
    return _bpm_detector
```

#### 1.3 Create BPM API

**File:** `src/modules/api_bpm.py`

```python
"""
BPM Detection API
REST and WebSocket endpoints for BPM detection.
"""

from flask import Blueprint, jsonify, request
from flask_sock import Sock
import json
import time
import logging
from .bpm_detector import get_bpm_detector

logger = logging.getLogger(__name__)

# Create blueprint
bpm_bp = Blueprint('bpm', __name__)
sock = Sock()

@bpm_bp.route('/api/bpm/start-input', methods=['POST'])
def start_input_detection():
    """Start real-time BPM detection from audio input."""
    try:
        data = request.get_json() or {}
        device_id = data.get('device_id')  # Optional specific device
        
        detector = get_bpm_detector()
        detector.start_audio_input(device_id)
        
        return jsonify({
            'success': True,
            'message': 'Audio input BPM detection started'
        })
    except Exception as e:
        logger.error(f"Error starting input detection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bpm_bp.route('/api/bpm/analyze-file', methods=['POST'])
def analyze_file():
    """Analyze audio file for BPM."""
    try:
        data = request.get_json() or {}
        file_path = data.get('path')
        
        if not file_path:
            return jsonify({'success': False, 'error': 'Missing file path'}), 400
        
        detector = get_bpm_detector()
        result = detector.analyze_file(file_path)
        
        return jsonify({
            'success': True,
            'bpm': result['bpm'],
            'confidence': result['confidence'],
            'beats': result['beats'],
            'duration': result['duration']
        })
    except Exception as e:
        logger.error(f"Error analyzing file: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bpm_bp.route('/api/bpm/tap', methods=['POST'])
def tap_tempo():
    """Record a tap for tap tempo."""
    try:
        detector = get_bpm_detector()
        bpm = detector.tap()
        
        return jsonify({
            'success': True,
            'bpm': round(bpm, 1),
            'tap_count': len(detector.tap_times)
        })
    except Exception as e:
        logger.error(f"Error processing tap: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bpm_bp.route('/api/bpm/stop', methods=['POST'])
def stop_detection():
    """Stop BPM detection."""
    try:
        detector = get_bpm_detector()
        detector.stop()
        
        return jsonify({
            'success': True,
            'message': 'BPM detection stopped'
        })
    except Exception as e:
        logger.error(f"Error stopping detection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bpm_bp.route('/api/bpm/status', methods=['GET'])
def get_status():
    """Get current BPM status."""
    try:
        detector = get_bpm_detector()
        status = detector.get_status()
        phase = detector.get_beat_phase()
        
        return jsonify({
            'success': True,
            'status': status,
            'beat_phase': round(phase, 3)
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@sock.route('/ws/bpm')
def bpm_websocket(ws):
    """WebSocket endpoint for real-time BPM updates."""
    logger.info("🎵 BPM WebSocket client connected")
    detector = get_bpm_detector()
    
    try:
        while True:
            # Get current status
            status = detector.get_status()
            phase = detector.get_beat_phase()
            
            # Send to client
            ws.send(json.dumps({
                'type': 'bpm_update',
                'bpm': status['bpm'],
                'confidence': status['confidence'],
                'source': status['source'],
                'is_running': status['is_running'],
                'beat_phase': round(phase, 3),
                'timestamp': time.time()
            }))
            
            # Update rate: 20 Hz (fast enough for beat indicators)
            time.sleep(0.05)
    
    except Exception as e:
        logger.info(f"BPM WebSocket closed: {e}")
    
    finally:
        logger.info("🎵 BPM WebSocket client disconnected")

def init_bpm_api(app):
    """Initialize BPM API with Flask app."""
    app.register_blueprint(bpm_bp)
    sock.init_app(app)
    logger.info("🎵 BPM API initialized")
```

#### 1.4 Integrate with Sequencer

**File:** `src/modules/api_sequencer.py`

Add BPM analysis when audio is loaded:

```python
from .bpm_detector import get_bpm_detector

@app.route('/api/sequencer/load', methods=['POST'])
def load_audio():
    data = request.get_json() or {}
    audio_file = data.get('file')
    
    # ... existing load code ...
    
    # Analyze BPM in background
    def analyze_bpm():
        detector = get_bpm_detector()
        detector.analyze_file(audio_file)
    
    threading.Thread(target=analyze_bpm, daemon=True).start()
    
    return jsonify({'success': True})
```

### Phase 2: Frontend UI

#### 2.1 Create BPM Display Component

**File:** `frontend/components/bpm-display.html`

```html
<template id="bpm-display-template">
    <div class="bpm-container">
        <!-- BPM Value Display -->
        <div class="bpm-display">
            <div class="bpm-label">BPM</div>
            <div class="bpm-value" id="bpm-value">--</div>
            <div class="bpm-source" id="bpm-source">No source</div>
        </div>
        
        <!-- Beat Indicator -->
        <div class="beat-indicator">
            <div class="beat-dot" id="beat-dot-1"></div>
            <div class="beat-dot" id="beat-dot-2"></div>
            <div class="beat-dot" id="beat-dot-3"></div>
            <div class="beat-dot" id="beat-dot-4"></div>
        </div>
        
        <!-- Source Selection -->
        <div class="bpm-sources">
            <label class="bpm-source-option">
                <input type="radio" name="bpm-source" value="input" onchange="window.bpmDisplay.changeSource('input')">
                <span>🎤 Audio Input</span>
            </label>
            <label class="bpm-source-option">
                <input type="radio" name="bpm-source" value="sequencer" onchange="window.bpmDisplay.changeSource('sequencer')" checked>
                <span>🎵 Sequencer</span>
            </label>
            <label class="bpm-source-option">
                <input type="radio" name="bpm-source" value="tap" onchange="window.bpmDisplay.changeSource('tap')">
                <span>🥁 Tap Tempo</span>
            </label>
        </div>
        
        <!-- Tap Tempo Button -->
        <div class="tap-tempo-container" id="tap-tempo-container" style="display: none;">
            <button class="tap-button" id="tap-button" onclick="window.bpmDisplay.tap()">
                TAP
            </button>
            <div class="tap-guide">Tap the beat (min 2 taps)</div>
        </div>
        
        <!-- Confidence Indicator -->
        <div class="bpm-confidence">
            <div class="confidence-label">Confidence:</div>
            <div class="confidence-bar">
                <div class="confidence-fill" id="confidence-fill" style="width: 0%"></div>
            </div>
            <div class="confidence-value" id="confidence-value">0%</div>
        </div>
    </div>
</template>

<script>
class BPMDisplay {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        self.currentSource = 'sequencer';
        this.beatDots = [];
        this.lastBeatPhase = 0;
    }
    
    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('BPM container not found');
            return;
        }
        
        // Load template
        const template = document.getElementById('bpm-display-template');
        const content = template.content.cloneNode(true);
        container.appendChild(content);
        
        // Get beat dots
        this.beatDots = [
            document.getElementById('beat-dot-1'),
            document.getElementById('beat-dot-2'),
            document.getElementById('beat-dot-3'),
            document.getElementById('beat-dot-4')
        ];
        
        // Connect WebSocket
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/bpm`;
        
        console.log('🎵 Connecting to BPM WebSocket...');
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('🎵 BPM WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'bpm_update') {
                    this.updateDisplay(message);
                }
            } catch (e) {
                console.error('Error parsing BPM message:', e);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('BPM WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('🎵 BPM WebSocket closed, reconnecting...');
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };
    }
    
    updateDisplay(data) {
        // Update BPM value
        const bpmValue = document.getElementById('bpm-value');
        if (bpmValue) {
            bpmValue.textContent = data.bpm > 0 ? data.bpm.toFixed(1) : '--';
        }
        
        // Update source
        const bpmSource = document.getElementById('bpm-source');
        if (bpmSource) {
            const sourceNames = {
                'input': '🎤 Audio Input',
                'sequencer': '🎵 Sequencer',
                'tap': '🥁 Tap Tempo'
            };
            bpmSource.textContent = sourceNames[data.source] || 'No source';
        }
        
        // Update confidence
        const confidencePercent = Math.round(data.confidence * 100);
        const confidenceFill = document.getElementById('confidence-fill');
        const confidenceValue = document.getElementById('confidence-value');
        
        if (confidenceFill) {
            confidenceFill.style.width = `${confidencePercent}%`;
            
            // Color based on confidence
            if (confidencePercent >= 70) {
                confidenceFill.style.background = 'linear-gradient(90deg, #4caf50, #66bb6a)';
            } else if (confidencePercent >= 40) {
                confidenceFill.style.background = 'linear-gradient(90deg, #ff9800, #ffb74d)';
            } else {
                confidenceFill.style.background = 'linear-gradient(90deg, #f44336, #e57373)';
            }
        }
        
        if (confidenceValue) {
            confidenceValue.textContent = `${confidencePercent}%`;
        }
        
        // Update beat indicator
        this.updateBeatIndicator(data.beat_phase);
    }
    
    updateBeatIndicator(phase) {
        // Determine which beat we're on (0-3)
        const beatIndex = Math.floor(phase * 4);
        
        // Check if we crossed a beat boundary
        if (Math.floor(this.lastBeatPhase * 4) !== beatIndex) {
            // Flash the corresponding dot
            this.flashBeat(beatIndex);
        }
        
        this.lastBeatPhase = phase;
    }
    
    flashBeat(index) {
        const dot = this.beatDots[index];
        if (!dot) return;
        
        // Add active class
        dot.classList.add('beat-active');
        
        // Remove after 150ms
        setTimeout(() => {
            dot.classList.remove('beat-active');
        }, 150);
    }
    
    async changeSource(source) {
        this.currentSource = source;
        
        // Show/hide tap tempo UI
        const tapContainer = document.getElementById('tap-tempo-container');
        if (tapContainer) {
            tapContainer.style.display = source === 'tap' ? 'block' : 'none';
        }
        
        // Stop current detection
        await fetch('/api/bpm/stop', { method: 'POST' });
        
        // Start new source
        if (source === 'input') {
            await fetch('/api/bpm/start-input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
        } else if (source === 'sequencer') {
            // Sequencer BPM is auto-detected on file load
            console.log('🎵 Switched to sequencer BPM');
        }
    }
    
    async tap() {
        try {
            const response = await fetch('/api/bpm/tap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const data = await response.json();
            
            // Visual feedback
            const button = document.getElementById('tap-button');
            if (button) {
                button.classList.add('tap-active');
                setTimeout(() => button.classList.remove('tap-active'), 100);
            }
            
            console.log(`🥁 Tap recorded: ${data.bpm} BPM (${data.tap_count} taps)`);
        } catch (e) {
            console.error('Error sending tap:', e);
        }
    }
    
    destroy() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
    }
}

// Global instance
window.bpmDisplay = new BPMDisplay();
</script>
```

#### 2.2 Add BPM Display Styles

**File:** `frontend/css/bpm-display.css`

```css
.bpm-container {
    background: rgba(20, 20, 30, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 15px;
    backdrop-filter: blur(10px);
}

/* BPM Value Display */
.bpm-display {
    text-align: center;
    margin-bottom: 15px;
}

.bpm-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #999;
    letter-spacing: 1px;
    margin-bottom: 5px;
}

.bpm-value {
    font-size: 48px;
    font-weight: 700;
    color: #fff;
    line-height: 1;
    font-family: 'Courier New', monospace;
    text-shadow: 0 0 10px rgba(76, 175, 80, 0.5);
}

.bpm-source {
    font-size: 12px;
    color: #888;
    margin-top: 5px;
}

/* Beat Indicator */
.beat-indicator {
    display: flex;
    justify-content: center;
    gap: 10px;
    margin-bottom: 15px;
}

.beat-dot {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    transition: all 0.1s ease;
}

.beat-dot.beat-active {
    background: #4caf50;
    box-shadow: 0 0 15px rgba(76, 175, 80, 0.8);
    transform: scale(1.3);
}

/* Source Selection */
.bpm-sources {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 15px;
}

.bpm-source-option {
    display: flex;
    align-items: center;
    padding: 8px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
}

.bpm-source-option:hover {
    background: rgba(255, 255, 255, 0.1);
}

.bpm-source-option input[type="radio"] {
    margin-right: 8px;
}

.bpm-source-option span {
    font-size: 13px;
}

/* Tap Tempo */
.tap-tempo-container {
    text-align: center;
    margin-bottom: 15px;
    padding: 15px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 6px;
}

.tap-button {
    width: 120px;
    height: 120px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4caf50, #66bb6a);
    border: 3px solid rgba(255, 255, 255, 0.2);
    color: #fff;
    font-size: 24px;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.1s ease;
    box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
}

.tap-button:hover {
    transform: scale(1.05);
    box-shadow: 0 6px 20px rgba(76, 175, 80, 0.5);
}

.tap-button.tap-active {
    transform: scale(0.95);
    box-shadow: 0 2px 10px rgba(76, 175, 80, 0.6);
}

.tap-guide {
    margin-top: 10px;
    font-size: 11px;
    color: #888;
}

/* Confidence Indicator */
.bpm-confidence {
    display: flex;
    align-items: center;
    gap: 8px;
}

.confidence-label {
    font-size: 11px;
    color: #999;
    white-space: nowrap;
}

.confidence-bar {
    flex: 1;
    height: 6px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
    overflow: hidden;
}

.confidence-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease, background 0.3s ease;
}

.confidence-value {
    font-size: 11px;
    color: #fff;
    font-weight: 600;
    min-width: 35px;
    text-align: right;
}
```

#### 2.3 Integrate into Player UI

**File:** `frontend/player.html`

Add to `<head>`:

```html
<link rel="stylesheet" href="css/bpm-display.css">
```

Add BPM display to UI (e.g., in sidebar or control panel):

```html
<!-- BPM Display -->
<div id="bpm-display-container"></div>
<script src="components/bpm-display.html"></script>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        window.bpmDisplay.init('bpm-display-container');
    });
</script>
```

#### 2.4 Auto-Analyze Sequencer Files

**File:** `frontend/js/waveform-analyzer.js`

Add BPM analysis when audio is loaded:

```javascript
async function loadAudioFromServer(filename) {
    // ... existing load code ...
    
    // Analyze BPM
    try {
        const response = await fetch('/api/bpm/analyze-file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filename })
        });
        
        const data = await response.json();
        if (data.success) {
            console.log(`🎵 Detected BPM: ${data.bpm} (confidence: ${data.confidence})`);
        }
    } catch (e) {
        console.error('BPM analysis error:', e);
    }
}
```

## Usage

### Audio Input Detection

1. Select "🎤 Audio Input" source
2. Backend captures audio from default input device
3. Real-time BPM detection starts
4. Beat indicators pulse in sync

### Sequencer BPM

1. Select "🎵 Sequencer" source
2. Load audio file in sequencer
3. Backend analyzes full file for BPM
4. More accurate than real-time detection

### Tap Tempo

1. Select "🥁 Tap Tempo" source
2. Tap button shows
3. Tap along with the beat (minimum 2 taps)
4. BPM calculated from tap intervals
5. Auto-resets after 3 seconds of inactivity

### Beat Synchronization

Use BPM in effects/transitions:

```javascript
// Get current beat phase
const response = await fetch('/api/bpm/status');
const data = await response.json();
const phase = data.beat_phase;  // 0.0 to 1.0

// Trigger effect on beat
if (phase < 0.1) {  // Within 10% of beat
    triggerBeatEffect();
}
```

## Integration Examples

### 1. Beat-Synced Transitions

**File:** `src/modules/player/transition_manager.py`

```python
from ..bpm_detector import get_bpm_detector

class TransitionManager:
    def should_transition_now(self):
        """Check if we're on a beat for transition."""
        detector = get_bpm_detector()
        phase = detector.get_beat_phase()
        
        # Transition on downbeat (phase near 0)
        return phase < 0.1 or phase > 0.9
```

### 2. BPM-Based Effect Speed

**File:** `plugins/effects/pulse.py`

```python
from src.modules.bpm_detector import get_bpm_detector

class PulseEffect(EffectPlugin):
    def process(self, frame, parameters, frame_count, fps):
        detector = get_bpm_detector()
        
        # Pulse speed matches BPM
        if detector.current_bpm > 0:
            pulse_freq = detector.current_bpm / 60.0  # Hz
        else:
            pulse_freq = parameters.get('speed', 1.0)
        
        # ... apply pulse effect ...
```

### 3. Beat-Triggered Events

**Frontend:** Beat callback

```javascript
let lastBeatIndex = -1;

window.bpmDisplay.updateBeatIndicator = function(phase) {
    const beatIndex = Math.floor(phase * 4);
    
    if (beatIndex !== lastBeatIndex) {
        // Beat event!
        onBeat(beatIndex);
        lastBeatIndex = beatIndex;
    }
    
    // ... rest of indicator code ...
};

function onBeat(beatIndex) {
    console.log(`🥁 Beat ${beatIndex + 1}/4`);
    
    // Trigger animations, effects, etc.
    if (beatIndex === 0) {
        // Downbeat - major beat
        flashScreen();
    }
}
```

## Performance Considerations

### CPU Usage

- **Audio Input Detection**: ~2-5% CPU (depends on analysis frequency)
- **File Analysis**: One-time ~10-20% CPU spike (1-2 seconds)
- **Tap Tempo**: Negligible (<0.1% CPU)

### Optimization Tips

1. **Adjust analysis frequency** in `_audio_input_loop()`:
   ```python
   time.sleep(0.5)  # Analyze every 0.5s (default)
   # Increase to 1.0 for lower CPU usage
   ```

2. **Cache file BPM results**:
   ```python
   bpm_cache = {}  # filename -> bpm
   ```

3. **Use tap tempo for live performances** (zero CPU)

## Future Enhancements

1. **Beat Grid Editor**
   - Visual beat markers in sequencer
   - Manual beat adjustment
   - Downbeat/measure markers

2. **Multiple BPM Detection**
   - Detect tempo changes in file
   - Time signature detection (3/4, 4/4, 6/8, etc.)
   - Polyrhythm support

3. **Advanced Audio Input**
   - Device selection UI
   - Input level meter
   - Low-latency mode

4. **BPM Automation**
   - Gradual tempo changes
   - BPM envelopes
   - Sync multiple players

5. **Export Beat Data**
   - Export beat markers to JSON
   - MIDI beat clock output
   - Ableton Link integration

## Troubleshooting

### No Audio Input Detected

- Check system audio permissions
- Verify microphone/line-in connected
- Test with: `python -m sounddevice`

### Inaccurate BPM

- Increase confidence threshold
- Use file analysis instead of real-time
- Ensure clean audio signal (no noise)

### High CPU Usage

- Increase analysis interval (0.5s → 1.0s)
- Use tap tempo for live input
- Close other audio applications

## References

- `src/modules/bpm_detector.py` - Core detection engine
- `src/modules/api_bpm.py` - REST and WebSocket API
- `frontend/components/bpm-display.html` - Display component
- `frontend/css/bpm-display.css` - Styling
- External: [librosa documentation](https://librosa.org/)
- External: [sounddevice documentation](https://python-sounddevice.readthedocs.io/)
