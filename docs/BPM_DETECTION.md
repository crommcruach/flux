# BPM Detection System - Implementation Guide

## Overview

This document describes the implementation of **BPM (Beats Per Minute) detection algorithms** for the Flux Art-Net system. The audio infrastructure (sequencer, audio input/output, device selection) is already implemented.

## Current Status

✅ **Already Implemented:**
- Audio sequencer with file playback (miniaudio backend)
- Audio input capture (sounddevice) with device selection
- Audio analyzer with FFT (Bass/Mid/Treble frequency bands)
- Real-time audio monitoring thread
- WebSocket streaming for audio data
- Audio source selection UI and API

🔧 **To Be Implemented:**
- BPM detection algorithms (librosa onset detection & tempo estimation)
- Tap tempo functionality
- BPM smoothing and averaging
- Beat phase calculation for effect synchronization
- BPM WebSocket streaming
- BPM UI display and beat indicators

## Goals

- Detect BPM from **existing audio input** (line-in/microphone)
- Detect BPM from **sequencer audio files** (use existing AudioTimeline)
- **Tap tempo** functionality (manual BPM input)
- Smooth BPM averaging and stabilization
- Beat synchronization for effects/transitions
- Expose BPM as bindable parameter in Dynamic Parameter Sequences

## BPM Detection Methods

### 1. Audio Input Detection (Line-In/Mic)
- ✅ Real-time audio capture from system audio devices **[IMPLEMENTED]**
- 🔧 **TO IMPLEMENT:** Onset detection algorithm (spectral flux, energy-based) using librosa
- 🔧 **TO IMPLEMENT:** Tempo estimation using autocorrelation/beat tracking
- ✅ Continuous monitoring thread **[IMPLEMENTED]**
- **Integration Point:** Use existing `AudioAnalyzer` class from audio reactive sequences

### 2. Sequencer File Analysis
- ✅ Audio file loading and playback **[IMPLEMENTED]** via `AudioTimeline` class
- 🔧 **TO IMPLEMENT:** Full-file BPM detection using librosa.beat.beat_track()
- 🔧 **TO IMPLEMENT:** Cache BPM per file in session state for instant recall
- 🔧 **TO IMPLEMENT:** Beat grid generation for quantization
- **Integration Point:** Add BPM detection to `AudioTimeline.load_audio()` method

### 3. Tap Tempo
- 🔧 **TO IMPLEMENT:** Manual BPM entry by tapping beat
- 🔧 **TO IMPLEMENT:** Average of last 4-8 taps
- 🔧 **TO IMPLEMENT:** Smoothing algorithm for human timing variance
- 🔧 **TO IMPLEMENT:** Auto-reset after timeout (>3 seconds)
- **Integration Point:** New REST API endpoint + WebSocket event

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

Add BPM detection library (audio infrastructure already installed):

```txt
librosa>=0.10.0  # BPM detection & beat tracking
```

✅ Already installed:
- sounddevice (audio input capture)
- numpy (FFT analysis)
- miniaudio (audio playback)

Install:
```bash
pip install librosa
```

#### 1.2 Extend AudioAnalyzer with BPM Detection

**File:** `src/modules/audio_analyzer.py` (EXTEND EXISTING)

Add BPM detection to the existing `AudioAnalyzer` class:

```python
# Add to existing imports
import librosa
from collections import deque

class AudioAnalyzer:
    """Audio analysis with FFT and BPM detection."""
    
    def __init__(self):
        # ... existing initialization ...
        
        # BPM Detection (NEW)
        self.current_bpm = 0.0
        self.beat_times = deque(maxlen=100)
        self.bpm_confidence = 0.0
        self.bpm_history = deque(maxlen=10)
        self.bpm_enabled = False
        
        # Tap tempo (NEW)
        self.tap_times = deque(maxlen=8)
        self.tap_timeout = 3.0
    
    def enable_bpm_detection(self, enabled=True):
        """Enable/disable BPM detection."""
        self.bpm_enabled = enabled
        if enabled:
            logger.info("🎵 BPM detection enabled")
        else:
            logger.info("🎵 BPM detection disabled")
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Audio callback (EXISTING - extend with BPM)."""
        # ... existing FFT analysis code ...
        
        # NEW: BPM Detection (if enabled)
        if self.bpm_enabled and len(self.audio_buffer) >= self.sample_rate:
            audio_data = np.array(list(self.audio_buffer))
            bpm, confidence = self._detect_bpm_realtime(audio_data)
            if bpm > 0:
                self._update_bpm(bpm, confidence)
    
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

#### 2.1 Create BPM Display Widget

**Location:** `middle-section-left` container in player.html

**File:** `frontend/player.html` (add to middle-section-left)

```html
<!-- BPM Detection Widget in middle-section-left -->
<div id="bpm-widget" class="bpm-widget">
    <!-- Beat Indicator Dot -->
    <div class="bpm-beat-indicator">
        <div class="beat-dot" id="bpm-beat-dot"></div>
    </div>
    
    <!-- Transport Controls -->
    <div class="bpm-transport">
        <button class="bpm-transport-btn" id="bpm-play-btn" title="Enable BPM Detection">
            <span class="icon">▶</span>
        </button>
        <button class="bpm-transport-btn" id="bpm-pause-btn" title="Pause BPM Detection">
            <span class="icon">⏸</span>
        </button>
        <button class="bpm-transport-btn" id="bpm-stop-btn" title="Stop BPM Detection">
            <span class="icon">⏹</span>
        </button>
    </div>
    
    <!-- BPM Display & Manual Input -->
    <div class="bpm-display-row">
        <label class="bpm-label">BPM:</label>
        <input 
            type="number" 
            id="bpm-value-input" 
            class="bpm-value-input" 
            min="20" 
            max="300" 
            step="0.1" 
            value="--" 
            placeholder="--"
        />
    </div>
    
    <!-- Action Buttons -->
    <div class="bpm-actions">
        <button class="bpm-action-btn" id="bpm-tap-btn" title="Tap Tempo">
            TAP
        </button>
        <button class="bpm-action-btn" id="bpm-resync-btn" title="Resync Auto Detection">
            Resync
        </button>
    </div>
</div>

```

**File:** `frontend/js/bpm-widget.js`

```javascript
/**
 * BPM Detection Widget
 * Real-time BPM display with WebSocket updates
 */
class BPMWidget {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        this.currentBPM = 0;
        this.beatCount = 0;
        this.isRunning = false;
        this.beatDot = null;
        this.bpmInput = null;
    }
    
    init() {
        // Get UI elements
        this.beatDot = document.getElementById('bpm-beat-dot');
        this.bpmInput = document.getElementById('bpm-value-input');
        
        const playBtn = document.getElementById('bpm-play-btn');
        const pauseBtn = document.getElementById('bpm-pause-btn');
        const stopBtn = document.getElementById('bpm-stop-btn');
        const tapBtn = document.getElementById('bpm-tap-btn');
        const resyncBtn = document.getElementById('bpm-resync-btn');
        
        // Transport controls
        playBtn.addEventListener('click', () => this.play());
        pauseBtn.addEventListener('click', () => this.pause());
        stopBtn.addEventListener('click', () => this.stop());
        
        // Action buttons
        tapBtn.addEventListener('click', () => this.tap());
        resyncBtn.addEventListener('click', () => this.resync());
        
        // Manual BPM input
        this.bpmInput.addEventListener('change', () => this.setManualBPM());
        
        // Connect WebSocket
        this.connect();
    }
    
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/bpm`;
        
        console.log('🎵 Connecting to BPM WebSocket...');
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('✅ BPM WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleBPMUpdate(data);
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
    
    
    handleBPMUpdate(data) {
        // Update BPM display (if not manually editing)
        if (document.activeElement !== this.bpmInput && data.bpm > 0) {
            this.currentBPM = data.bpm;
            this.bpmInput.value = data.bpm.toFixed(1);
        }
        
        // Update beat indicator
        if (data.beat_phase !== undefined) {
            this.updateBeatIndicator(data.beat_phase, data.beat_count);
        }
    }
    
    updateBeatIndicator(phase, beatCount) {
        if (!this.beatDot) return;
        
        // Beat boundary detection (phase wraps from 0.99 to 0.0)
        const prevPhase = this.lastBeatPhase || 0;
        const beatOccurred = phase < prevPhase;
        
        if (beatOccurred) {
            this.beatCount++;
            
            // Every beat: light green blink
            // Every 16th beat: yellow blink
            const isBar = (this.beatCount % 16) === 0;
            
            if (isBar) {
                this.flashBeat('yellow');
            } else {
                this.flashBeat('light-green');
            }
        }
        
        this.lastBeatPhase = phase;
    }
    
    flashBeat(color) {
        if (!this.beatDot) return;
        
        // Remove existing color classes
        this.beatDot.classList.remove('beat-light-green', 'beat-yellow');
        
        // Add color class
        if (color === 'yellow') {
            this.beatDot.classList.add('beat-yellow');
        } else {
            this.beatDot.classList.add('beat-light-green');
        }
        
        // Remove after animation (200ms)
        setTimeout(() => {
            this.beatDot.classList.remove('beat-light-green', 'beat-yellow');
        }, 200);
    }
    
    // Transport controls
    play() {
        fetch('/api/bpm/start', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log('▶ BPM detection started');
                this.isRunning = true;
            })
            .catch(e => console.error('Failed to start BPM detection:', e));
    }
    
    pause() {
        fetch('/api/bpm/pause', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log('⏸ BPM detection paused');
            })
            .catch(e => console.error('Failed to pause BPM detection:', e));
    }
    
    stop() {
        fetch('/api/bpm/stop', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log('⏹ BPM detection stopped');
                this.isRunning = false;
                this.currentBPM = 0;
                this.bpmInput.value = '--';
                this.beatCount = 0;
            })
            .catch(e => console.error('Failed to stop BPM detection:', e));
    }
    
    // Manual BPM input
    setManualBPM() {
        const manualBPM = parseFloat(this.bpmInput.value);
        
        if (isNaN(manualBPM) || manualBPM < 20 || manualBPM > 300) {
            alert('BPM must be between 20 and 300');
            return;
        }
        
        fetch('/api/bpm/manual', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({bpm: manualBPM})
        })
            .then(r => r.json())
            .then(data => {
                console.log(`🎹 Manual BPM set: ${manualBPM}`);
                this.currentBPM = manualBPM;
            })
            .catch(e => console.error('Failed to set manual BPM:', e));
    }
    
    // Tap tempo
    tap() {
        fetch('/api/bpm/tap', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log(`🥁 Tap registered: ${data.bpm} BPM`);
                if (data.bpm > 0) {
                    this.currentBPM = data.bpm;
                    this.bpmInput.value = data.bpm.toFixed(1);
                }
            })
            .catch(e => console.error('Failed to tap:', e));
    }
    }
}

// Global instance
window.bpmWidget = new BPMWidget();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.bpmWidget.init();
});
```

#### 2.2 Add BPM Widget Styles

**File:** `frontend/css/bpm-widget.css`

```css
/* BPM Widget Container */
.bpm-widget {
    background: rgba(20, 20, 30, 0.9);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 15px;
    backdrop-filter: blur(10px);
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-width: 200px;
}

/* Beat Indicator Dot */
.bpm-beat-indicator {
    display: flex;
    justify-content: center;
    align-items: center;
    margin-bottom: 5px;
}

.beat-dot {
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: #1a3a1a; /* Dark green default */
    transition: all 0.15s ease;
    box-shadow: inset 0 0 5px rgba(0, 0, 0, 0.5);
}

/* Beat flash states */
.beat-dot.beat-light-green {
    background: #4caf50; /* Light green on beat */
    box-shadow: 0 0 20px rgba(76, 175, 80, 0.8);
}

.beat-dot.beat-yellow {
    background: #ffeb3b; /* Yellow on 16th beat */
    box-shadow: 0 0 20px rgba(255, 235, 59, 0.8);
}

/* Transport Controls */
.bpm-transport {
    display: flex;
    gap: 6px;
    justify-content: center;
}

.bpm-transport-btn {
    width: 32px;
    height: 28px;
    background: rgba(255, 255, 255, 0.1);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.bpm-transport-btn:hover {
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.4);
}

.bpm-transport-btn:active {
    transform: scale(0.95);
}

.bpm-transport-btn .icon {
    font-size: 14px;
}

/* BPM Display & Input */
.bpm-display-row {
    display: flex;
    align-items: center;
    gap: 8px;
}

.bpm-label {
    font-size: 12px;
    font-weight: 600;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.bpm-value-input {
    flex: 1;
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 4px;
    color: #fff;
    font-size: 18px;
    font-weight: 600;
    font-family: 'Courier New', monospace;
    padding: 6px 10px;
    text-align: center;
    transition: all 0.2s;
}

.bpm-value-input:hover {
    border-color: rgba(255, 255, 255, 0.4);
}

.bpm-value-input:focus {
    outline: none;
    border-color: #4caf50;
    box-shadow: 0 0 8px rgba(76, 175, 80, 0.4);
}

/* Action Buttons */
.bpm-actions {
    display: flex;
    gap: 8px;
}

.bpm-action-btn {
    flex: 1;
    background: rgba(76, 175, 80, 0.2);
    border: 1px solid rgba(76, 175, 80, 0.4);
    border-radius: 4px;
    color: #4caf50;
    font-size: 12px;
    font-weight: 600;
    padding: 8px;
    cursor: pointer;
    transition: all 0.2s;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.bpm-action-btn:hover {
    background: rgba(76, 175, 80, 0.3);
    border-color: rgba(76, 175, 80, 0.6);
    color: #66bb6a;
}

.bpm-action-btn:active {
    transform: scale(0.98);
}

#bpm-tap-btn {
    background: rgba(33, 150, 243, 0.2);
    border-color: rgba(33, 150, 243, 0.4);
    color: #2196f3;
}

#bpm-tap-btn:hover {
    background: rgba(33, 150, 243, 0.3);
    border-color: rgba(33, 150, 243, 0.6);
    color: #42a5f5;
}

#bpm-resync-btn {
    background: rgba(255, 152, 0, 0.2);
    border-color: rgba(255, 152, 0, 0.4);
    color: #ff9800;
}

#bpm-resync-btn:hover {
    background: rgba(255, 152, 0, 0.3);
    border-color: rgba(255, 152, 0, 0.6);
    color: #ffb74d;
}
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

- `src/modules/sequences/audio_analyzer.py` - Audio analysis with BPM detection
- `src/modules/sequences/bpm_sequence.py` - Beat-synchronized keyframe animation
- `src/modules/api_bpm.py` - REST and WebSocket API
- `frontend/js/bpm-widget.js` - BPM widget UI
- `frontend/css/bpm-widget.css` - BPM widget styling
- External: [librosa documentation](https://librosa.org/)
- External: [sounddevice documentation](https://python-sounddevice.readthedocs.io/)
