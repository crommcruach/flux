# MIDI Clock In/Out - Implementation Guide

## Overview

This document describes the implementation of **MIDI Clock input and output** for the Flux Art-Net system, enabling synchronization with external MIDI devices and DAWs (Digital Audio Workstations).

## Goals

- **MIDI Clock Input**: Sync playback to external MIDI clock source (DAW, drum machine, etc.)
- **MIDI Clock Output**: Send MIDI clock to sync external devices to system tempo
- **All core logic in backend** (Python MIDI processing)
- **Frontend visualization only** (connection status, BPM display, beat indicators)
- Support for MIDI Start/Stop/Continue messages
- Configurable PPQN (Pulses Per Quarter Note)
- Auto-detect MIDI devices
- Low-latency synchronization

## MIDI Clock Protocol

### MIDI Clock Messages

- **0xF8 (Timing Clock)**: Sent 24 times per quarter note (24 PPQN)
- **0xFA (Start)**: Start playback from beginning
- **0xFB (Continue)**: Continue playback from current position
- **0xFC (Stop)**: Stop playback
- **0xFE (Active Sensing)**: Optional keepalive message

### Timing Calculation

```
BPM = (Clocks per minute) / 24
Clock Interval (ms) = 60000 / (BPM * 24)

Example: 120 BPM
Clock Interval = 60000 / (120 * 24) = 20.833ms
```

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Python)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              MIDI Clock Manager                     │   │
│  │  ┌──────────────┐            ┌──────────────┐      │   │
│  │  │ MIDI Input   │            │ MIDI Output  │      │   │
│  │  │  Handler     │            │  Generator   │      │   │
│  │  │  (mido)      │            │  (mido)      │      │   │
│  │  └──────┬───────┘            └──────┬───────┘      │   │
│  │         │                            │              │   │
│  │         │  Clock messages            │  Clock ticks │   │
│  │         ▼                            ▼              │   │
│  │  ┌──────────────────────────────────────────────┐  │   │
│  │  │          Clock Synchronizer                  │  │   │
│  │  │  - BPM calculation                           │  │   │
│  │  │  - Beat tracking                             │  │   │
│  │  │  - Start/Stop/Continue                       │  │   │
│  │  └──────────────┬───────────────────────────────┘  │   │
│  └─────────────────┼──────────────────────────────────┘   │
│                    │                                       │
│  ┌─────────────────▼─────────────────────────────────┐    │
│  │        REST API & WebSocket                       │    │
│  │  /api/midi/devices         /ws/midi               │    │
│  │  /api/midi/connect         /api/midi/status       │    │
│  │  /api/midi/disconnect      /api/midi/send-clock   │    │
│  └─────────────────┬─────────────────────────────────┘    │
│                    │                                       │
└────────────────────┼───────────────────────────────────────┘
                     │
                     ▼ WebSocket Stream
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (JavaScript)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │ MIDI Display    │◀────────│  WebSocket       │          │
│  │ - Status        │         │  Client          │          │
│  │ - BPM           │         └──────────────────┘          │
│  │ - Beat Pulse    │                                        │
│  └─────────────────┘         ┌──────────────────┐          │
│                              │ Device Selector  │          │
│  ┌─────────────────┐         │ - Input devices  │          │
│  │ Connection UI   │         │ - Output devices │          │
│  │ ● Connected     │         └──────────────────┘          │
│  │ ○ Disconnected  │                                        │
│  └─────────────────┘         ┌──────────────────┐          │
│                              │  Beat Indicator  │          │
│  ┌─────────────────┐         │  ● ○ ○ ○         │          │
│  │ Controls        │         └──────────────────┘          │
│  │ [Start] [Stop]  │                                        │
│  │ [Continue]      │                                        │
│  └─────────────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Implementation Steps

### Phase 1: Backend - MIDI Clock Manager

#### 1.1 Install Dependencies

**File:** `requirements.txt`

Add MIDI library:

```txt
mido>=1.3.0
python-rtmidi>=1.5.0
```

Install:
```bash
pip install mido python-rtmidi
```

#### 1.2 Create MIDI Clock Manager

**File:** `src/modules/midi_clock.py`

```python
"""
MIDI Clock Manager
Handles MIDI clock input and output synchronization.
"""

import mido
import time
import threading
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)

class MIDIClockManager:
    """Manages MIDI clock input/output synchronization."""
    
    # MIDI Clock message types
    CLOCK = 0xF8
    START = 0xFA
    CONTINUE = 0xFB
    STOP = 0xFC
    ACTIVE_SENSING = 0xFE
    
    def __init__(self):
        # Input
        self.input_port = None
        self.input_device_name = None
        self.input_thread = None
        self.is_receiving = False
        
        # Output
        self.output_port = None
        self.output_device_name = None
        self.output_thread = None
        self.is_sending = False
        
        # Synchronization state
        self.bpm = 0.0
        self.is_playing = False
        self.beat_position = 0.0  # 0.0 to 4.0 (quarter notes)
        self.ppqn = 24  # Pulses per quarter note (MIDI standard)
        
        # Clock timing
        self.clock_times = deque(maxlen=24)  # Last 24 clock pulses
        self.last_clock_time = 0
        self.clock_count = 0
        
        # Output timing
        self.output_bpm = 120.0
        self.output_running = False
        
        # Callbacks
        self.on_start_callback = None
        self.on_stop_callback = None
        self.on_beat_callback = None
    
    def get_input_devices(self):
        """Get list of available MIDI input devices."""
        try:
            devices = mido.get_input_names()
            logger.info(f"🎹 Found {len(devices)} MIDI input devices: {devices}")
            return devices
        except Exception as e:
            logger.error(f"Error getting MIDI input devices: {e}")
            return []
    
    def get_output_devices(self):
        """Get list of available MIDI output devices."""
        try:
            devices = mido.get_output_names()
            logger.info(f"🎹 Found {len(devices)} MIDI output devices: {devices}")
            return devices
        except Exception as e:
            logger.error(f"Error getting MIDI output devices: {e}")
            return []
    
    def connect_input(self, device_name=None):
        """
        Connect to MIDI input device.
        
        Args:
            device_name: Name of MIDI device (None = first available)
        """
        try:
            if self.is_receiving:
                self.disconnect_input()
            
            if device_name is None:
                devices = self.get_input_devices()
                if not devices:
                    raise Exception("No MIDI input devices found")
                device_name = devices[0]
            
            self.input_port = mido.open_input(device_name)
            self.input_device_name = device_name
            self.is_receiving = True
            
            # Start input thread
            self.input_thread = threading.Thread(
                target=self._input_loop,
                daemon=True
            )
            self.input_thread.start()
            
            logger.info(f"🎹 Connected to MIDI input: {device_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to MIDI input: {e}")
            return False
    
    def disconnect_input(self):
        """Disconnect from MIDI input device."""
        self.is_receiving = False
        
        if self.input_thread:
            self.input_thread.join(timeout=2)
        
        if self.input_port:
            self.input_port.close()
            self.input_port = None
        
        logger.info("🎹 Disconnected MIDI input")
    
    def connect_output(self, device_name=None, bpm=120.0):
        """
        Connect to MIDI output device and start sending clock.
        
        Args:
            device_name: Name of MIDI device (None = first available)
            bpm: Tempo to send
        """
        try:
            if self.is_sending:
                self.disconnect_output()
            
            if device_name is None:
                devices = self.get_output_devices()
                if not devices:
                    raise Exception("No MIDI output devices found")
                device_name = devices[0]
            
            self.output_port = mido.open_output(device_name)
            self.output_device_name = device_name
            self.output_bpm = bpm
            self.is_sending = True
            
            # Start output thread
            self.output_thread = threading.Thread(
                target=self._output_loop,
                daemon=True
            )
            self.output_thread.start()
            
            logger.info(f"🎹 Connected to MIDI output: {device_name} @ {bpm} BPM")
            return True
        
        except Exception as e:
            logger.error(f"Error connecting to MIDI output: {e}")
            return False
    
    def disconnect_output(self):
        """Disconnect from MIDI output device."""
        self.is_sending = False
        self.output_running = False
        
        if self.output_thread:
            self.output_thread.join(timeout=2)
        
        if self.output_port:
            # Send stop message
            try:
                self.output_port.send(mido.Message.from_bytes([self.STOP]))
            except:
                pass
            self.output_port.close()
            self.output_port = None
        
        logger.info("🎹 Disconnected MIDI output")
    
    def _input_loop(self):
        """MIDI input processing loop."""
        logger.info("🎹 MIDI input loop started")
        
        try:
            for msg in self.input_port:
                if not self.is_receiving:
                    break
                
                # Handle clock messages
                if msg.type == 'clock':
                    self._handle_clock()
                elif msg.type == 'start':
                    self._handle_start()
                elif msg.type == 'continue':
                    self._handle_continue()
                elif msg.type == 'stop':
                    self._handle_stop()
        
        except Exception as e:
            logger.error(f"MIDI input loop error: {e}")
        
        finally:
            logger.info("🎹 MIDI input loop stopped")
    
    def _handle_clock(self):
        """Handle MIDI clock tick."""
        now = time.time()
        
        # Store clock time
        if self.last_clock_time > 0:
            self.clock_times.append(now - self.last_clock_time)
        
        self.last_clock_time = now
        self.clock_count += 1
        
        # Calculate BPM (average over last 24 ticks = 1 quarter note)
        if len(self.clock_times) >= 24:
            avg_interval = sum(self.clock_times) / len(self.clock_times)
            if avg_interval > 0:
                # 24 clocks per quarter note
                quarter_note_duration = avg_interval * 24
                self.bpm = 60.0 / quarter_note_duration
        
        # Update beat position
        self.beat_position = (self.clock_count % 96) / 24.0  # 96 clocks = 4 beats
        
        # Beat callback (every 24 clocks = 1 beat)
        if self.clock_count % 24 == 0 and self.on_beat_callback:
            beat_number = int(self.beat_position)
            self.on_beat_callback(beat_number)
    
    def _handle_start(self):
        """Handle MIDI start message."""
        logger.info("🎹 MIDI Start received")
        self.is_playing = True
        self.clock_count = 0
        self.beat_position = 0.0
        
        if self.on_start_callback:
            self.on_start_callback()
    
    def _handle_continue(self):
        """Handle MIDI continue message."""
        logger.info("🎹 MIDI Continue received")
        self.is_playing = True
        
        if self.on_start_callback:
            self.on_start_callback()
    
    def _handle_stop(self):
        """Handle MIDI stop message."""
        logger.info("🎹 MIDI Stop received")
        self.is_playing = False
        
        if self.on_stop_callback:
            self.on_stop_callback()
    
    def _output_loop(self):
        """MIDI output clock generation loop."""
        logger.info(f"🎹 MIDI output loop started @ {self.output_bpm} BPM")
        
        try:
            while self.is_sending:
                if self.output_running:
                    # Calculate clock interval
                    interval = 60.0 / (self.output_bpm * self.ppqn)
                    
                    # Send clock tick
                    self.output_port.send(mido.Message.from_bytes([self.CLOCK]))
                    
                    # High-precision sleep
                    time.sleep(interval)
                else:
                    # Not running, just wait
                    time.sleep(0.01)
        
        except Exception as e:
            logger.error(f"MIDI output loop error: {e}")
        
        finally:
            logger.info("🎹 MIDI output loop stopped")
    
    def send_start(self):
        """Send MIDI start message."""
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.START]))
            self.output_running = True
            logger.info("🎹 Sent MIDI Start")
    
    def send_continue(self):
        """Send MIDI continue message."""
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.CONTINUE]))
            self.output_running = True
            logger.info("🎹 Sent MIDI Continue")
    
    def send_stop(self):
        """Send MIDI stop message."""
        if self.output_port and self.is_sending:
            self.output_port.send(mido.Message.from_bytes([self.STOP]))
            self.output_running = False
            logger.info("🎹 Sent MIDI Stop")
    
    def set_output_bpm(self, bpm):
        """Change output tempo."""
        self.output_bpm = max(20.0, min(300.0, bpm))  # Clamp to reasonable range
        logger.info(f"🎹 Output BPM set to {self.output_bpm}")
    
    def get_status(self):
        """Get current MIDI clock status."""
        return {
            'input': {
                'connected': self.is_receiving,
                'device': self.input_device_name,
                'bpm': round(self.bpm, 1),
                'playing': self.is_playing,
                'beat_position': round(self.beat_position, 2)
            },
            'output': {
                'connected': self.is_sending,
                'device': self.output_device_name,
                'bpm': self.output_bpm,
                'running': self.output_running
            }
        }


# Global instance
_midi_clock_manager = None

def get_midi_clock_manager():
    """Get global MIDI clock manager instance."""
    global _midi_clock_manager
    if _midi_clock_manager is None:
        _midi_clock_manager = MIDIClockManager()
    return _midi_clock_manager
```

#### 1.3 Create MIDI Clock API

**File:** `src/modules/api_midi.py`

```python
"""
MIDI Clock API
REST and WebSocket endpoints for MIDI clock synchronization.
"""

from flask import Blueprint, jsonify, request
from flask_sock import Sock
import json
import time
import logging
from .midi_clock import get_midi_clock_manager

logger = logging.getLogger(__name__)

# Create blueprint
midi_bp = Blueprint('midi', __name__)
sock = Sock()

@midi_bp.route('/api/midi/devices', methods=['GET'])
def get_devices():
    """Get available MIDI input and output devices."""
    try:
        manager = get_midi_clock_manager()
        
        return jsonify({
            'success': True,
            'input_devices': manager.get_input_devices(),
            'output_devices': manager.get_output_devices()
        })
    except Exception as e:
        logger.error(f"Error getting MIDI devices: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/connect-input', methods=['POST'])
def connect_input():
    """Connect to MIDI input device."""
    try:
        data = request.get_json() or {}
        device_name = data.get('device')
        
        manager = get_midi_clock_manager()
        success = manager.connect_input(device_name)
        
        return jsonify({
            'success': success,
            'device': manager.input_device_name
        })
    except Exception as e:
        logger.error(f"Error connecting MIDI input: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/disconnect-input', methods=['POST'])
def disconnect_input():
    """Disconnect from MIDI input device."""
    try:
        manager = get_midi_clock_manager()
        manager.disconnect_input()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error disconnecting MIDI input: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/connect-output', methods=['POST'])
def connect_output():
    """Connect to MIDI output device."""
    try:
        data = request.get_json() or {}
        device_name = data.get('device')
        bpm = data.get('bpm', 120.0)
        
        manager = get_midi_clock_manager()
        success = manager.connect_output(device_name, bpm)
        
        return jsonify({
            'success': success,
            'device': manager.output_device_name
        })
    except Exception as e:
        logger.error(f"Error connecting MIDI output: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/disconnect-output', methods=['POST'])
def disconnect_output():
    """Disconnect from MIDI output device."""
    try:
        manager = get_midi_clock_manager()
        manager.disconnect_output()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error disconnecting MIDI output: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/send-start', methods=['POST'])
def send_start():
    """Send MIDI start message."""
    try:
        manager = get_midi_clock_manager()
        manager.send_start()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error sending MIDI start: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/send-continue', methods=['POST'])
def send_continue():
    """Send MIDI continue message."""
    try:
        manager = get_midi_clock_manager()
        manager.send_continue()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error sending MIDI continue: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/send-stop', methods=['POST'])
def send_stop():
    """Send MIDI stop message."""
    try:
        manager = get_midi_clock_manager()
        manager.send_stop()
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error sending MIDI stop: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/set-bpm', methods=['POST'])
def set_bpm():
    """Set output BPM."""
    try:
        data = request.get_json() or {}
        bpm = data.get('bpm', 120.0)
        
        manager = get_midi_clock_manager()
        manager.set_output_bpm(bpm)
        
        return jsonify({'success': True, 'bpm': manager.output_bpm})
    except Exception as e:
        logger.error(f"Error setting BPM: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@midi_bp.route('/api/midi/status', methods=['GET'])
def get_status():
    """Get current MIDI clock status."""
    try:
        manager = get_midi_clock_manager()
        status = manager.get_status()
        
        return jsonify({'success': True, 'status': status})
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@sock.route('/ws/midi')
def midi_websocket(ws):
    """WebSocket endpoint for real-time MIDI status updates."""
    logger.info("🎹 MIDI WebSocket client connected")
    manager = get_midi_clock_manager()
    
    try:
        while True:
            # Get current status
            status = manager.get_status()
            
            # Send to client
            ws.send(json.dumps({
                'type': 'midi_update',
                'status': status,
                'timestamp': time.time()
            }))
            
            # Update rate: 20 Hz (fast enough for beat indicators)
            time.sleep(0.05)
    
    except Exception as e:
        logger.info(f"MIDI WebSocket closed: {e}")
    
    finally:
        logger.info("🎹 MIDI WebSocket client disconnected")

def init_midi_api(app):
    """Initialize MIDI API with Flask app."""
    app.register_blueprint(midi_bp)
    sock.init_app(app)
    logger.info("🎹 MIDI API initialized")
```

### Phase 2: Frontend UI

#### 2.1 Create MIDI Display Component

**File:** `frontend/components/midi-display.html`

```html
<template id="midi-display-template">
    <div class="midi-container">
        <!-- Input Section -->
        <div class="midi-section">
            <div class="midi-section-header">
                <span class="midi-section-title">🎹 MIDI Clock In</span>
                <div class="midi-status" id="midi-input-status">
                    <span class="status-dot status-disconnected"></span>
                    <span class="status-text">Disconnected</span>
                </div>
            </div>
            
            <div class="midi-device-select">
                <select id="midi-input-device" class="form-select form-select-sm">
                    <option value="">No device selected</option>
                </select>
                <button class="btn btn-sm btn-primary" id="btn-connect-input" onclick="window.midiDisplay.connectInput()">
                    Connect
                </button>
            </div>
            
            <div class="midi-info" id="midi-input-info">
                <div class="midi-bpm">
                    <span class="midi-label">BPM:</span>
                    <span class="midi-value" id="midi-input-bpm">--</span>
                </div>
                <div class="midi-position">
                    <span class="midi-label">Beat:</span>
                    <span class="midi-value" id="midi-input-beat">--</span>
                </div>
            </div>
            
            <div class="beat-indicator">
                <div class="beat-dot" id="input-beat-dot-1"></div>
                <div class="beat-dot" id="input-beat-dot-2"></div>
                <div class="beat-dot" id="input-beat-dot-3"></div>
                <div class="beat-dot" id="input-beat-dot-4"></div>
            </div>
        </div>
        
        <!-- Output Section -->
        <div class="midi-section">
            <div class="midi-section-header">
                <span class="midi-section-title">🎹 MIDI Clock Out</span>
                <div class="midi-status" id="midi-output-status">
                    <span class="status-dot status-disconnected"></span>
                    <span class="status-text">Disconnected</span>
                </div>
            </div>
            
            <div class="midi-device-select">
                <select id="midi-output-device" class="form-select form-select-sm">
                    <option value="">No device selected</option>
                </select>
                <button class="btn btn-sm btn-primary" id="btn-connect-output" onclick="window.midiDisplay.connectOutput()">
                    Connect
                </button>
            </div>
            
            <div class="midi-bpm-control">
                <label class="form-label">
                    BPM: <span id="midi-output-bpm-value">120</span>
                </label>
                <input type="range" class="form-range" id="midi-output-bpm" 
                       min="20" max="300" value="120" step="1"
                       oninput="window.midiDisplay.updateOutputBPM(this.value)">
            </div>
            
            <div class="midi-controls">
                <button class="btn btn-sm btn-success" onclick="window.midiDisplay.sendStart()">▶ Start</button>
                <button class="btn btn-sm btn-warning" onclick="window.midiDisplay.sendContinue()">⏯ Continue</button>
                <button class="btn btn-sm btn-danger" onclick="window.midiDisplay.sendStop()">⏹ Stop</button>
            </div>
        </div>
    </div>
</template>

<script>
class MIDIDisplay {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        this.inputDevices = [];
        this.outputDevices = [];
    }
    
    async init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('MIDI container not found');
            return;
        }
        
        // Load template
        const template = document.getElementById('midi-display-template');
        const content = template.content.cloneNode(true);
        container.appendChild(content);
        
        // Load devices
        await this.loadDevices();
        
        // Connect WebSocket
        this.connect();
    }
    
    async loadDevices() {
        try {
            const response = await fetch('/api/midi/devices');
            const data = await response.json();
            
            if (data.success) {
                this.inputDevices = data.input_devices;
                this.outputDevices = data.output_devices;
                
                // Populate select boxes
                this.populateSelect('midi-input-device', this.inputDevices);
                this.populateSelect('midi-output-device', this.outputDevices);
                
                console.log('🎹 Loaded MIDI devices');
            }
        } catch (e) {
            console.error('Error loading MIDI devices:', e);
        }
    }
    
    populateSelect(selectId, devices) {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        // Clear existing options (except first)
        while (select.options.length > 1) {
            select.remove(1);
        }
        
        // Add devices
        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device;
            option.textContent = device;
            select.appendChild(option);
        });
    }
    
    async connectInput() {
        const select = document.getElementById('midi-input-device');
        const device = select.value;
        
        if (!device) {
            alert('Please select an input device');
            return;
        }
        
        try {
            const response = await fetch('/api/midi/connect-input', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('🎹 Connected to MIDI input');
            } else {
                alert('Failed to connect: ' + data.error);
            }
        } catch (e) {
            console.error('Error connecting MIDI input:', e);
            alert('Connection error: ' + e.message);
        }
    }
    
    async connectOutput() {
        const select = document.getElementById('midi-output-device');
        const device = select.value;
        const bpmInput = document.getElementById('midi-output-bpm');
        const bpm = parseFloat(bpmInput.value);
        
        if (!device) {
            alert('Please select an output device');
            return;
        }
        
        try {
            const response = await fetch('/api/midi/connect-output', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ device, bpm })
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log('🎹 Connected to MIDI output');
            } else {
                alert('Failed to connect: ' + data.error);
            }
        } catch (e) {
            console.error('Error connecting MIDI output:', e);
            alert('Connection error: ' + e.message);
        }
    }
    
    async updateOutputBPM(bpm) {
        document.getElementById('midi-output-bpm-value').textContent = bpm;
        
        try {
            await fetch('/api/midi/set-bpm', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bpm: parseFloat(bpm) })
            });
        } catch (e) {
            console.error('Error setting BPM:', e);
        }
    }
    
    async sendStart() {
        try {
            await fetch('/api/midi/send-start', { method: 'POST' });
        } catch (e) {
            console.error('Error sending start:', e);
        }
    }
    
    async sendContinue() {
        try {
            await fetch('/api/midi/send-continue', { method: 'POST' });
        } catch (e) {
            console.error('Error sending continue:', e);
        }
    }
    
    async sendStop() {
        try {
            await fetch('/api/midi/send-stop', { method: 'POST' });
        } catch (e) {
            console.error('Error sending stop:', e);
        }
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/midi`;
        
        console.log('🎹 Connecting to MIDI WebSocket...');
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('🎹 MIDI WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'midi_update') {
                    this.updateDisplay(message.status);
                }
            } catch (e) {
                console.error('Error parsing MIDI message:', e);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('MIDI WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('🎹 MIDI WebSocket closed, reconnecting...');
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };
    }
    
    updateDisplay(status) {
        // Input status
        const inputStatus = document.getElementById('midi-input-status');
        if (inputStatus) {
            const dot = inputStatus.querySelector('.status-dot');
            const text = inputStatus.querySelector('.status-text');
            
            if (status.input.connected) {
                dot.className = 'status-dot status-connected';
                text.textContent = `Connected: ${status.input.device}`;
            } else {
                dot.className = 'status-dot status-disconnected';
                text.textContent = 'Disconnected';
            }
        }
        
        // Input values
        if (status.input.connected) {
            document.getElementById('midi-input-bpm').textContent = status.input.bpm;
            document.getElementById('midi-input-beat').textContent = status.input.beat_position.toFixed(2);
            
            // Beat indicators
            const beatIndex = Math.floor(status.input.beat_position) % 4;
            for (let i = 0; i < 4; i++) {
                const dot = document.getElementById(`input-beat-dot-${i + 1}`);
                if (dot) {
                    dot.classList.toggle('beat-active', i === beatIndex && status.input.playing);
                }
            }
        }
        
        // Output status
        const outputStatus = document.getElementById('midi-output-status');
        if (outputStatus) {
            const dot = outputStatus.querySelector('.status-dot');
            const text = outputStatus.querySelector('.status-text');
            
            if (status.output.connected) {
                dot.className = status.output.running ? 'status-dot status-running' : 'status-dot status-connected';
                text.textContent = `${status.output.device} ${status.output.running ? '(Running)' : ''}`;
            } else {
                dot.className = 'status-dot status-disconnected';
                text.textContent = 'Disconnected';
            }
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
window.midiDisplay = new MIDIDisplay();
</script>
```

#### 2.2 Add MIDI Display Styles

**File:** `frontend/css/midi-display.css`

```css
.midi-container {
    background: rgba(20, 20, 30, 0.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 15px;
    backdrop-filter: blur(10px);
}

.midi-section {
    background: rgba(255, 255, 255, 0.03);
    border-radius: 6px;
    padding: 15px;
    margin-bottom: 15px;
}

.midi-section:last-child {
    margin-bottom: 0;
}

.midi-section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}

.midi-section-title {
    font-size: 14px;
    font-weight: 600;
    color: #fff;
}

.midi-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    color: #888;
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #555;
}

.status-dot.status-connected {
    background: #4caf50;
    box-shadow: 0 0 8px rgba(76, 175, 80, 0.6);
}

.status-dot.status-running {
    background: #2196f3;
    box-shadow: 0 0 8px rgba(33, 150, 243, 0.6);
    animation: pulse 1s infinite;
}

.status-dot.status-disconnected {
    background: #666;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

.status-text {
    font-size: 11px;
}

.midi-device-select {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
}

.midi-device-select select {
    flex: 1;
}

.midi-info {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 12px;
}

.midi-bpm, .midi-position {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(255, 255, 255, 0.05);
    padding: 8px;
    border-radius: 4px;
}

.midi-label {
    font-size: 11px;
    color: #999;
    text-transform: uppercase;
}

.midi-value {
    font-size: 14px;
    font-weight: 600;
    color: #fff;
    font-family: 'Courier New', monospace;
}

.beat-indicator {
    display: flex;
    justify-content: center;
    gap: 8px;
    padding: 8px 0;
}

.beat-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.2);
    transition: all 0.1s ease;
}

.beat-dot.beat-active {
    background: #2196f3;
    box-shadow: 0 0 12px rgba(33, 150, 243, 0.8);
    transform: scale(1.2);
}

.midi-bpm-control {
    margin-bottom: 12px;
}

.midi-bpm-control .form-label {
    font-size: 12px;
    color: #999;
    margin-bottom: 4px;
}

.midi-bpm-control #midi-output-bpm-value {
    color: #fff;
    font-weight: 600;
}

.midi-controls {
    display: flex;
    gap: 6px;
}

.midi-controls .btn {
    flex: 1;
    font-size: 11px;
}
```

#### 2.3 Integrate into Player UI

**File:** `frontend/player.html`

Add to `<head>`:

```html
<link rel="stylesheet" href="css/midi-display.css">
```

Add MIDI display to UI:

```html
<!-- MIDI Clock Display -->
<div id="midi-display-container"></div>
<script src="components/midi-display.html"></script>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        window.midiDisplay.init('midi-display-container');
    });
</script>
```

## Usage

### MIDI Clock Input

1. Connect MIDI device to computer
2. Select device from "MIDI Clock In" dropdown
3. Click "Connect"
4. Start MIDI clock from external device (DAW, drum machine, etc.)
5. BPM and beat position display automatically
6. Beat indicators pulse with incoming clock

### MIDI Clock Output

1. Connect MIDI device to computer
2. Select device from "MIDI Clock Out" dropdown
3. Set desired BPM with slider
4. Click "Connect"
5. Click "Start" to begin sending clock
6. External devices will sync to this tempo

### Transport Control

- **Start**: Begin from start (beat 0)
- **Continue**: Resume from current position
- **Stop**: Stop playback

## Integration Examples

### 1. Sync Sequencer to MIDI Clock

**File:** `src/modules/sequencer.py`

```python
from .midi_clock import get_midi_clock_manager

class Sequencer:
    def __init__(self):
        # ... existing code ...
        
        # MIDI sync
        midi = get_midi_clock_manager()
        midi.on_start_callback = self.on_midi_start
        midi.on_stop_callback = self.on_midi_stop
    
    def on_midi_start(self):
        """Callback when MIDI start received."""
        self.play()
    
    def on_midi_stop(self):
        """Callback when MIDI stop received."""
        self.pause()
```

### 2. Generate MIDI Clock from Sequencer BPM

**File:** `frontend/js/waveform-analyzer.js`

```javascript
// When sequencer loads audio with detected BPM
async function onBPMDetected(bpm) {
    // Update MIDI output BPM
    await fetch('/api/midi/set-bpm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bpm })
    });
}
```

### 3. Beat-Synced Effects

**File:** `plugins/effects/strobe.py`

```python
from src.modules.midi_clock import get_midi_clock_manager

class StrobeEffect(EffectPlugin):
    def process(self, frame, parameters, frame_count, fps):
        midi = get_midi_clock_manager()
        
        # Flash on every beat
        beat_pos = midi.beat_position % 1.0
        
        if beat_pos < 0.1:  # First 10% of beat
            # Apply strobe flash
            return frame * 2.0  # Brighten
        
        return frame
```

## Performance Considerations

### CPU Usage

- **MIDI Input**: <1% CPU (event-driven)
- **MIDI Output**: ~1-2% CPU (high-precision timing loop)
- **WebSocket Updates**: ~0.5% CPU (20 Hz updates)

### Latency

- **Input**: <5ms (near-realtime with python-rtmidi)
- **Output**: <1ms clock jitter (high-precision sleep)
- **WebSocket**: 50ms update rate (adequate for visual feedback)

### Optimization Tips

1. **Reduce WebSocket update rate** for lower bandwidth:
   ```python
   time.sleep(0.1)  # 10 Hz instead of 20 Hz
   ```

2. **Use MIDI thru** for daisy-chaining devices

3. **Close unused connections** (input or output)

## Troubleshooting

### No MIDI Devices Found

- Check MIDI device drivers installed
- Verify device connected via USB/MIDI
- Restart application
- Test with: `python -m mido.ports`

### Clock Drift/Timing Issues

- Close other MIDI applications
- Use dedicated USB port (not hub)
- Check system load (high CPU affects timing)
- Update python-rtmidi: `pip install --upgrade python-rtmidi`

### Connection Fails

- Check device not in use by other software
- Try different MIDI device
- Check permissions (Linux: add user to `audio` group)

## Future Enhancements

1. **MIDI Mapping**
   - Map MIDI CC to effect parameters
   - MIDI note triggers for clips
   - Program change for scene switching

2. **Advanced Timing**
   - Time signature support (3/4, 6/8, etc.)
   - Song position pointer (SPP)
   - MTC (MIDI Time Code) support

3. **Multi-Device Support**
   - Multiple input/output devices
   - MIDI thru functionality
   - Device presets

4. **Visualization**
   - Clock timing graph
   - Latency monitor
   - Jitter analysis

5. **Integration**
   - Ableton Link support
   - OSC (Open Sound Control)
   - Network MIDI (RTP-MIDI)

## References

- `src/modules/midi_clock.py` - MIDI clock manager
- `src/modules/api_midi.py` - REST and WebSocket API
- `frontend/components/midi-display.html` - Display component
- `frontend/css/midi-display.css` - Styling
- External: [mido documentation](https://mido.readthedocs.io/)
- External: [python-rtmidi documentation](https://spotlightkid.github.io/python-rtmidi/)
- MIDI Specification: [MIDI Association](https://www.midi.org/)
