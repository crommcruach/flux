/**
 * BPM Detection Widget
 * Real-time BPM display with WebSocket updates
 */
class BPMWidget {
    constructor() {
        this.socket = null;
        this.currentBPM = 0;
        this.beatCount = 0;
        this.isRunning = false;
        this.beatDot = null;
        this.bpmInput = null;
        this.lastBeatPhase = 0;
        this.manualTapMode = false; // Manual tap mode prevents audio from overwriting BPM
        this.tapBtn = null;
    }
    
    init() {
        // Get UI elements
        this.beatDot = document.getElementById('bpm-beat-dot');
        this.bpmInput = document.getElementById('bpm-value-input');
        
        this.playBtn = document.getElementById('bpm-play-btn');
        this.pauseBtn = document.getElementById('bpm-pause-btn');
        this.stopBtn = document.getElementById('bpm-stop-btn');
        this.tapBtn = document.getElementById('bpm-tap-btn');
        const resyncBtn = document.getElementById('bpm-resync-btn');
        
        // Transport controls
        this.playBtn.addEventListener('click', () => this.play());
        this.pauseBtn.addEventListener('click', () => this.pause());
        this.stopBtn.addEventListener('click', () => this.stop());
        
        // Action buttons
        this.tapBtn.addEventListener('click', () => this.tap());
        this.tapBtn.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this.toggleManualTapMode();
        });
        resyncBtn.addEventListener('click', () => this.resync());
        
        // Manual BPM input
        this.bpmInput.addEventListener('change', () => this.setManualBPM());
        
        // Load initial state from backend
        this.loadInitialState();
        
        // Connect Socket.IO
        this.connect();
    }
    
    loadInitialState() {
        // Fetch BPM status to restore UI state
        fetch('/api/bpm/status')
            .then(r => r.json())
            .then(data => {
                if (data.success && data.status) {
                    const status = data.status;
                    
                    console.log('🎵 BPM initial state loaded:', status);
                    
                    // Update BPM display
                    if (status.bpm > 0) {
                        this.currentBPM = status.bpm;
                        this.bpmInput.value = status.bpm.toFixed(1);
                    }
                    
                    // Set running state and button
                    if (status.enabled) {
                        this.isRunning = true;
                        this.setActiveButton(this.playBtn);
                        console.log('🎵 BPM widget: Initial state - PLAY button active (enabled=true)');
                    } else {
                        this.isRunning = false;
                        // Default to stop button active if not enabled
                        this.setActiveButton(this.stopBtn);
                        console.log('🎵 BPM widget: Initial state - STOP button active (enabled=false)');
                    }
                }
            })
            .catch(e => console.error('Failed to load BPM initial state:', e));
    }
    
    connect() {
        console.log('🎵 Connecting to BPM Socket.IO...');
        
        // Connect to /bpm namespace
        this.socket = io('/bpm');
        
        this.socket.on('connect', () => {
            console.log('✅ BPM Socket.IO connected');
        });
        
        this.socket.on('bpm_update', (data) => {
            this.handleBPMUpdate(data);
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('BPM Socket.IO error:', error);
        });
        
        this.socket.on('disconnect', () => {
            console.log('🎵 BPM Socket.IO disconnected');
        });
    }
    
    handleBPMUpdate(data) {
        // Update BPM display (if not manually editing and not in manual tap mode)
        if (document.activeElement !== this.bpmInput && data.bpm > 0 && !this.manualTapMode) {
            this.currentBPM = data.bpm;
            this.bpmInput.value = data.bpm.toFixed(1);
        }
        
        // Update running state based on backend status
        if (data.enabled !== undefined) {
            const wasRunning = this.isRunning;
            this.isRunning = data.enabled;
            
            // Update button UI if state changed
            if (wasRunning !== this.isRunning) {
                if (this.isRunning) {
                    this.setActiveButton(this.playBtn);
                    console.log('🎵 BPM widget: Setting PLAY button active (enabled=true)');
                } else {
                    this.setActiveButton(this.stopBtn);
                    console.log('🎵 BPM widget: Setting STOP button active (enabled=false)');
                }
            }
        }
        
        // Update beat indicator only if running
        if (this.isRunning && data.beat_phase !== undefined) {
            this.updateBeatIndicator(data.beat_phase, data.beat_count);
        }
    }
    
    setActiveButton(button) {
        // Remove active class from all buttons
        this.playBtn.classList.remove('active');
        this.pauseBtn.classList.remove('active');
        this.stopBtn.classList.remove('active');
        
        // Add active class to specified button
        if (button) {
            button.classList.add('active');
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
                this.setActiveButton(this.playBtn);
            })
            .catch(e => console.error('Failed to start BPM detection:', e));
    }
    
    pause() {
        fetch('/api/bpm/pause', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log('⏸ BPM detection paused');
                this.isRunning = false;
                this.setActiveButton(this.pauseBtn);
                // Reset beat dot to default
                if (this.beatDot) {
                    this.beatDot.classList.remove('beat-light-green', 'beat-yellow');
                }
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
                this.bpmInput.value = '';
                this.beatCount = 0;
                this.setActiveButton(this.stopBtn);
                // Reset beat dot to default
                if (this.beatDot) {
                    this.beatDot.classList.remove('beat-light-green', 'beat-yellow');
                }
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
    
    // Toggle manual tap mode
    toggleManualTapMode() {
        this.manualTapMode = !this.manualTapMode;
        
        if (this.manualTapMode) {
            // Enable manual tap mode - prevent audio from overwriting BPM
            this.tapBtn.classList.add('manual-tap-active');
            console.log('🔒 Manual tap mode enabled');
        } else {
            // Disable manual tap mode - allow audio to update BPM
            this.tapBtn.classList.remove('manual-tap-active');
            console.log('🔓 Manual tap mode disabled');
        }
    }
    
    // Resync all BPM sequences to current beat
    resync() {
        fetch('/api/bpm/resync', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                console.log(`🔄 BPM sequences resynced: ${data.synced_count} sequences`);
                this.beatCount = 0;
            })
            .catch(e => console.error('Failed to resync:', e));
    }
}

// Global instance
window.bpmWidget = new BPMWidget();

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.bpmWidget.init();
});
