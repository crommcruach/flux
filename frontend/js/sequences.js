/**
 * Dynamic Parameter Sequences - Frontend
 * 
 * Provides UI for creating and managing parameter sequences:
 * - Audio Reactive
 * - LFO (Low Frequency Oscillator)
 * - Timeline Keyframes
 */

class SequenceManager {
    constructor() {
        this.sequences = [];
        this.currentSequence = null;
        this.currentParameter = null;
        this.audioAnalyzerRunning = false;
        this.audioFeatures = {};
        this.audioGainKnob = null;
        this.beatSensitivityKnob = null;
        this.audioDevice = null;
        this.audioDeviceName = null;
        this.cachedAudioDevices = null; // Cache for audio devices
        this.audioFeaturePeaks = { bass: 0.001, mid: 0.001, treble: 0.001 }; // Track peak values for adaptive scaling
        this.peakDecayRate = 0.995; // Slow decay for peak tracking
        this._contextMenuSetup = false;
        this._audioContextMenuSetup = false;
        this._audioPollingInterval = null;
        
        // Canvas contexts
        this.spectrumCanvas = null;
        this.lfoCanvas = null;
        this.timelineCanvas = null;
        
        // Animation frame ID
        this.animationFrame = null;
        
        // Initialize
        this.init();
    }
    
    init() {
        console.log('SequenceManager initialized');
        
        // Load sequences from session state (not separate API call)
        this.loadSequencesFromSessionState();
        
        // Restore audio analyzer state from session (async, doesn't block)
        this.restoreAudioAnalyzerFromSession();
        
        // Setup WebSocket for audio features
        this.setupWebSocket();
        
        // Start preview updates
        this.startPreviewLoop();
        
        // Setup context menu
        this.setupContextMenu();
        
        // Setup audio analyzer context menu
        this.setupAudioContextMenu();
        
        // Initial gain
        this.audioGain = 1.0;
        this.beatSensitivity = 1.0;
        
        // Initialize audio gain circular slider
        this.initAudioGainKnob();
        
        // Initialize beat sensitivity knob
        this.initBeatSensitivityKnob();
    }
    
    /**
     * Setup context menu
     */
    setupContextMenu() {
        const menu = document.getElementById('sequenceContextMenu');
        if (!menu) return;
        
        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.sequence-btn') && !e.target.closest('#sequenceContextMenu')) {
                menu.classList.remove('show');
            }
        });
    }
    
    /**
     * Setup audio analyzer context menu
     */
    setupAudioContextMenu() {
        const menu = document.getElementById('audioAnalyzerContextMenu');
        if (!menu) return;
        
        // Prevent duplicate event listeners
        if (this._audioContextMenuSetup) return;
        this._audioContextMenuSetup = true;
        
        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('#globalAudioStatus') && !e.target.closest('#audioAnalyzerContextMenu')) {
                menu.classList.remove('show');
            }
        });
    }
    
    /**
     * Show audio analyzer context menu
     */
    async showAudioContextMenu(event) {
        event.preventDefault();
        event.stopPropagation();
        
        const menu = document.getElementById('audioAnalyzerContextMenu');
        if (!menu) return;
        
        // Update toggle text based on current state
        const toggleText = document.getElementById('audioToggleText');
        if (toggleText) {
            toggleText.textContent = this.audioAnalyzerRunning ? '⏸️ Stop Analyzer' : '▶️ Start Analyzer';
        }
        
        // Position menu at click location
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        menu.classList.add('show');
        
        // Use cached devices if available, otherwise load
        const deviceList = document.getElementById('audioDeviceList');
        if (this.cachedAudioDevices && deviceList) {
            // Show cached devices immediately
            this.populateDeviceList(this.cachedAudioDevices);
        } else if (deviceList) {
            // Show loading state
            deviceList.innerHTML = '<div class="sequence-context-menu-item" style="opacity: 0.5;">Loading devices...</div>';
            // Load devices for first time
            this.loadAudioDevices();
        }
        
        console.log('🎚️ Audio analyzer context menu opened');
    }
    
    /**
     * Load available audio devices
     */
    async loadAudioDevices() {
        try {
            const response = await fetch('/api/audio/devices');
            if (response.ok) {
                const data = await response.json();
                const devices = data.devices || [];
                
                // Cache the devices
                this.cachedAudioDevices = devices;
                
                // Populate the device list
                this.populateDeviceList(devices);
            }
        } catch (error) {
            console.error('Error loading audio devices:', error);
            const deviceList = document.getElementById('audioDeviceList');
            if (deviceList) {
                deviceList.innerHTML = '<div class="sequence-context-menu-item" style="opacity: 0.5; color: #ff6b6b;">Error loading devices</div>';
            }
        }
    }
    
    /**
     * Populate device list in context menu
     */
    populateDeviceList(devices) {
        const deviceList = document.getElementById('audioDeviceList');
        if (!deviceList) return;
        
        // Clear existing devices
        deviceList.innerHTML = '';
        
        if (devices.length === 0) {
            deviceList.innerHTML = '<div class="sequence-context-menu-item" style="opacity: 0.5;">No devices found</div>';
            return;
        }
        
        // Add each device
        devices.forEach(device => {
            const item = document.createElement('div');
            item.className = 'sequence-context-menu-item';
            
            // Check if this is the currently selected device
            const isSelected = this.audioDevice === device.index;
            if (isSelected) {
                item.classList.add('selected');
            }
            
            item.textContent = `${isSelected ? '✓ ' : ''}🎤 ${device.name}`;
            item.onclick = () => this.setAudioDevice(device.index, device.name);
            deviceList.appendChild(item);
        });
        
        // Add refresh button
        const refreshItem = document.createElement('div');
        refreshItem.className = 'sequence-context-menu-item';
        refreshItem.style.borderTop = '1px solid #444';
        refreshItem.style.marginTop = '4px';
        refreshItem.style.paddingTop = '8px';
        refreshItem.style.opacity = '0.7';
        refreshItem.textContent = '🔄 Refresh Devices';
        refreshItem.onclick = () => {
            this.cachedAudioDevices = null; // Clear cache
            deviceList.innerHTML = '<div class="sequence-context-menu-item" style="opacity: 0.5;">Loading devices...</div>';
            this.loadAudioDevices();
        };
        deviceList.appendChild(refreshItem);
    }
    
    /**
     * Set audio device by index
     */
    async setAudioDevice(deviceIndex, deviceName) {
        const menu = document.getElementById('audioAnalyzerContextMenu');
        if (menu) menu.classList.remove('show');
        
        try {
            const wasRunning = this.audioAnalyzerRunning;
            
            // Stop if running
            if (wasRunning) {
                await this.stopAudioAnalyzer();
                // Wait a bit for the device to be released
                await new Promise(resolve => setTimeout(resolve, 200));
            }
            
            console.log('🎚️ Switching to device:', deviceIndex, deviceName);
            
            // Store device selection
            this.audioDevice = deviceIndex;
            this.audioDeviceName = deviceName;
            
            // Restart with new device if it was running
            if (wasRunning) {
                try {
                    await this.startAudioAnalyzer();
                    this.showNotification(`Audio device: ${deviceName}`, 'success');
                    
                    // Save to session
                    this.saveAudioAnalyzerToSession();
                } catch (startError) {
                    console.error('Error starting audio analyzer with new device:', startError);
                    this.showNotification(`Failed to start with device: ${deviceName}`, 'error');
                    this.audioAnalyzerRunning = false;
                }
            } else {
                this.showNotification(`Device set to: ${deviceName}`, 'info');
                
                // Save to session even if not running
                this.saveAudioAnalyzerToSession();
            }
        } catch (error) {
            console.error('Error changing audio device:', error);
            this.showNotification('Failed to change audio device', 'error');
        }
    }
    
    /**
     * Get audio analyzer state for session saving
     */
    getAudioAnalyzerState() {
        return {
            running: this.audioAnalyzerRunning,
            device: this.audioDevice || null,
            deviceName: this.audioDeviceName || null,
            gain: this.audioGainKnob ? this.audioGainKnob.getValue() : 1.0,
            beat_sensitivity: this.beatSensitivityKnob ? this.beatSensitivityKnob.getValue() : 1.0
        };
    }
    
    /**
     * Restore audio analyzer state from session
     */
    async restoreAudioAnalyzerState(state) {
        if (!state) return;
        
        try {
            console.log('🔄 Restoring audio analyzer state:', state);
            
            // Restore device if specified
            if (state.device !== null && state.device !== undefined) {
                this.audioDevice = state.device;
                this.audioDeviceName = state.deviceName || null;
            }
            
            // Restore gain
            if (state.gain !== undefined && this.audioGainKnob) {
                this.audioGainKnob.setValue(state.gain);
                // Send to backend
                await fetch('/api/audio/gain', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ gain: state.gain })
                });
            }
            
            // Restore running state
            if (state.running && !this.audioAnalyzerRunning) {
                await this.startAudioAnalyzer();
            }
            
            console.log('✅ Audio analyzer state restored');
        } catch (error) {
            console.error('Error restoring audio analyzer state:', error);
        }
    }
    
    /**
     * Restore audio analyzer from session state (called on page load)
     */
    async restoreAudioAnalyzerFromSession() {
        try {
            // First check if audio analyzer is already running on backend
            const statusResponse = await fetch('/api/audio/status');
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.running) {
                    console.log('✅ Audio analyzer already running on backend');
                    this.audioAnalyzerRunning = true;
                    this.updateAudioStatus();
                    
                    // Still restore device info and gain from session if available
                    if (window.sessionStateLoader && window.sessionStateLoader.isLoaded()) {
                        const audioState = window.sessionStateLoader.get('audio_analyzer');
                        if (audioState) {
                            if (audioState.device !== null && audioState.device !== undefined) {
                                this.audioDevice = audioState.device;
                            }
                            if (audioState.config?.gain !== undefined && this.audioGainKnob) {
                                this.audioGainKnob.setValue(audioState.config.gain);
                            }
                            if (audioState.config?.beat_sensitivity !== undefined && this.beatSensitivityKnob) {
                                this.beatSensitivityKnob.setValue(audioState.config.beat_sensitivity);
                            }
                        }
                    }
                    return;
                }
            }
            
            // AUTO-START LOGIC: Get default device and start analyzer automatically
            console.log('🎤 Auto-starting audio analyzer with default device...');
            
            // Try to get available devices
            try {
                const devicesResponse = await fetch('/api/audio/devices');
                if (devicesResponse.ok) {
                    const devicesData = await devicesResponse.json();
                    const devices = devicesData.devices || [];
                    
                    if (devices.length > 0) {
                        // Find default device (usually the first one or one marked as default)
                        let defaultDevice = devices.find(d => d.is_default) || devices[0];
                        this.audioDevice = defaultDevice.index;
                        this.audioDeviceName = defaultDevice.name;
                        console.log(`🎤 Auto-selected default device: ${this.audioDeviceName} (${this.audioDevice})`);
                    }
                }
            } catch (deviceError) {
                console.warn('Could not fetch devices, will use system default:', deviceError);
                // Continue anyway - backend will use default if no device specified
            }
            
            // Restore gain settings from session if available
            if (window.sessionStateLoader) {
                if (!window.sessionStateLoader.isLoaded()) {
                    await window.sessionStateLoader.load();
                }
                
                const audioState = window.sessionStateLoader.get('audio_analyzer');
                if (audioState) {
                    if (audioState.config?.gain !== undefined && this.audioGainKnob) {
                        this.audioGainKnob.setValue(audioState.config.gain);
                    }
                    if (audioState.config?.beat_sensitivity !== undefined && this.beatSensitivityKnob) {
                        this.beatSensitivityKnob.setValue(audioState.config.beat_sensitivity);
                    }
                    
                    // If user had a specific device saved, use that instead
                    if (audioState.device !== null && audioState.device !== undefined) {
                        this.audioDevice = audioState.device;
                        console.log('📝 Using saved device:', this.audioDevice);
                    }
                }
            }
            
            // DON'T auto-start - let user start manually or backend will auto-start on first use
            // Auto-starting causes crashes when page reloads while audio is already running
            console.log('💡 Audio analyzer ready (start manually if needed)');
            
        } catch (error) {
            console.error('Error auto-starting audio analyzer:', error);
            // Don't show error to user - audio analyzer is optional
            // User can manually start it if needed
        }
    }
    
    /**
     * Toggle audio analyzer on/off
     */
    async toggleAudioAnalyzer() {
        const menu = document.getElementById('audioAnalyzerContextMenu');
        if (menu) menu.classList.remove('show');
        
        if (this.audioAnalyzerRunning) {
            await this.stopAudioAnalyzer();
        } else {
            await this.startAudioAnalyzer();
        }
    }
    
    /**
     * Set audio source
     */
    async setAudioSource(source) {
        const menu = document.getElementById('audioAnalyzerContextMenu');
        if (menu) menu.classList.remove('show');
        
        try {
            const wasRunning = this.audioAnalyzerRunning;
            
            // Stop if running
            if (wasRunning) {
                await this.stopAudioAnalyzer();
            }
            
            // Set source in config
            console.log('🎚️ Switching audio source to:', source);
            
            // Restart with new source
            if (wasRunning) {
                // Pass source parameter when starting
                const response = await fetch('/api/audio/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ source: source })
                });
                
                if (response.ok) {
                    this.audioAnalyzerRunning = true;
                    this.updateAudioStatus();
                    this.showNotification(`Audio source changed to ${source}`, 'success');
                } else {
                    throw new Error('Failed to restart with new source');
                }
            } else {
                this.showNotification(`Audio source set to ${source}`, 'info');
            }
        } catch (error) {
            console.error('Error changing audio source:', error);
            this.showNotification('Failed to change audio source', 'error');
        }
    }
    
    /**
     * Show context menu for parameter
     */
    showContextMenu(parameterId, parameterLabel, currentValue, event, paramUid, controlId) {
        event.preventDefault();
        event.stopPropagation();
        
        console.log('📝 Context menu for:', { parameterId, parameterLabel, currentValue, paramUid, controlId });
        
        // Store current parameter for context menu actions
        this.contextParameter = {
            id: parameterId,
            label: parameterLabel,
            value: currentValue,
            uid: paramUid,
            controlId: controlId
        };
        
        const menu = document.getElementById('sequenceContextMenu');
        if (!menu) return;
        
        // Position menu at click location
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        menu.classList.add('show');
    }
    
    /**
     * Open editor with specific type from context menu
     */
    openEditorWithType(type) {
        console.log('🎯 Opening editor with type:', type);
        
        if (!this.contextParameter) {
            console.error('❌ No context parameter set');
            return;
        }
        
        // Close context menu
        document.getElementById('sequenceContextMenu').classList.remove('show');
        
        // For audio type, show inline controls WITHOUT creating sequence yet
        if (type === 'audio') {
            console.log('🎵 Showing audio inline controls for:', this.contextParameter.id);
            this.showInlineAudioControlsEmpty(this.contextParameter.id);
        } else if (type === 'timeline') {
            // For timeline type, show inline controls WITHOUT creating sequence yet
            console.log('📈 Showing timeline inline controls for:', this.contextParameter.id);
            this.showInlineTimelineControlsEmpty(this.contextParameter.id);
        } else if (type === 'bpm') {
            // For BPM type, show inline controls WITHOUT creating sequence yet
            console.log('🥁 Showing BPM inline controls for:', this.contextParameter.id);
            this.showInlineBPMControlsEmpty(this.contextParameter.id);
        } else if (type === 'lfo') {
            // For LFO type, show inline controls WITHOUT creating sequence yet
            console.log('🌊 Showing LFO inline controls for:', this.contextParameter.id);
            this.showInlineLFOControlsEmpty(this.contextParameter.id);
        } else {
            console.warn('⚠️ Unknown sequence type:', type);
        }
    }
    
    /**
     * Show inline audio controls WITHOUT creating sequence (user will create by clicking band/direction)
     */
    showInlineAudioControlsEmpty(parameterId) {
        console.log('🎵 Showing empty audio controls for:', parameterId);
        
        // Use controlId from context parameter (passed from button click)
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // FIRST: Hide all other inline controls to prevent stacking
        this.hideInlineTimelineControls(parameterId);
        this.hideInlineBPMControls(parameterId);
        
        const controlsContainer = document.getElementById(`${controlId}_audio_controls`);
        
        console.log('🔍 Looking for audio controls:', `${controlId}_audio_controls`);
        
        if (!controlsContainer) {
            console.warn('⚠️ Audio controls container not found for:', parameterId, 'controlId:', controlId);
            return;
        }
        
        // Show the controls (param-dynamic-settings in new grid layout)
        controlsContainer.style.display = 'block';
        
        // Track selected band and direction
        let selectedBand = null;
        let selectedDirection = null;
        
        // Function to create sequence when both band and direction are selected
        const tryCreateSequence = () => {
            if (selectedBand && selectedDirection) {
                this.createAudioSequenceWithConfig(parameterId, {
                    band: selectedBand,
                    direction: selectedDirection
                });
            }
        };
        
        // Set up band buttons to select band and create if direction is set
        const bandButtons = controlsContainer.querySelectorAll('.audio-band-btn-inline');
        bandButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.onclick = () => {
                // Toggle active state
                bandButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                selectedBand = btn.dataset.band;
                console.log('🎵 Band selected:', selectedBand);
                tryCreateSequence();
            };
        });
        
        // Set up direction buttons to select direction and create if band is set
        const dirButtons = controlsContainer.querySelectorAll('.audio-dir-btn-inline');
        dirButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.onclick = () => {
                // Toggle active state
                dirButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                selectedDirection = btn.dataset.direction;
                console.log('🎵 Direction selected:', selectedDirection);
                tryCreateSequence();
            };
        });
        
        // Initialize attack/release knob
        const knobContainer = document.getElementById(`${controlId}_attack_release`);
        if (knobContainer) {
            // Destroy existing slider if present
            if (knobContainer._circularSlider) {
                knobContainer.innerHTML = '';
                delete knobContainer._circularSlider;
            }
            
            const slider = new CircularSlider(knobContainer, {
                min: 0.2,
                max: 1.0,
                value: 0.7,
                step: 0.01,
                arc: 270,
                startAngle: 135, // Start at 7:30, deadzone at bottom
                size: 'tiny',
                label: '',
                decimals: 2,
                unit: '',
                variant: 'primary',
                showValue: false,
                onChange: (value) => {
                    // Update sequence if exists, otherwise just store value
                    const sequence = this.sequences.find(s => s.target_parameter === parameterId);
                    if (sequence) {
                        this.updateSequenceInline(parameterId, { attack_release: value });
                    }
                }
            });
            knobContainer._circularSlider = slider;
            console.log('🎛️ Initialized empty state attack/release knob');
        } else {
            console.warn('⚠️ Attack/release knob container not found in showInlineAudioControlsEmpty');
        }
        
        console.log('✅ Audio controls shown (no sequence created yet - select band + direction)');
    }
    
    /**
     * Create audio sequence with specific configuration (when user clicks band/direction)
     */
    async createAudioSequenceWithConfig(parameterId, updates) {
        console.log('🎯 Creating audio sequence with config:', { parameterId, updates });
        
        // Use stored controlId from context parameter
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // Get current knob value from CircularSlider instance
        const knobContainer = document.getElementById(`${controlId}_attack_release`);
        let attackRelease = 0.5; // Default
        if (knobContainer && knobContainer._circularSlider) {
            attackRelease = knobContainer._circularSlider.getValue ? 
                           knobContainer._circularSlider.getValue() : 
                           (knobContainer._circularSlider.value || 0.5);
        }
        
        console.log('🎛️ Attack/Release value from knob:', attackRelease);
        
        // Get min/max from triple slider
        const tripleSlider = getTripleSlider(controlId);
        let minValue = 0;
        let maxValue = 100;
        
        console.log('🔍 Looking for triple slider:', controlId);
        console.log('🔍 Slider instance:', tripleSlider);
        
        if (tripleSlider) {
            const range = tripleSlider.getRange();
            minValue = range.min;
            maxValue = range.max;
            console.log('📊 Using slider range:', { minValue, maxValue });
        } else {
            console.warn('⚠️ Triple slider not found, using defaults:', { minValue, maxValue });
        }
        
        // Create config with values from UI
        const config = {
            feature: 'rms',
            band: updates.band,
            direction: updates.direction,
            attack_release: attackRelease,
            min_value: minValue,
            max_value: maxValue,
            invert: false
        };
        
        const data = {
            type: 'audio',
            target_parameter: this.contextParameter.uid || parameterId,
            config: config
        };
        
        console.log('📦 Creating sequence with UID:', this.contextParameter.uid, 'config:', data);
        
        try {
            const response = await fetch('/api/sequences', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Audio sequence created:', result);
                
                await window.sessionStateLoader.reload();
                await this.loadSequencesFromSessionState();
                
                const savedSequence = this.sequences.find(s => s.target_parameter === parameterId);
                if (savedSequence) {
                    this.showInlineAudioControls(parameterId, savedSequence);
                }
                
                this.showNotification('Audio reactive applied!', 'success');
            } else {
                const error = await response.json();
                console.error('❌ Server error:', error);
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('❌ Error creating audio sequence:', error);
            this.showNotification('Failed to create audio sequence', 'error');
        }
    }
    
    /**
     * Remove sequence from context menu
     */
    async removeSequenceFromContext() {
        if (!this.contextParameter) {
            console.warn('⚠️ No context parameter set');
            return;
        }
        
        console.log('🗑️ Removing ALL sequences for:', this.contextParameter);
        
        // Close context menu
        document.getElementById('sequenceContextMenu').classList.remove('show');
        
        // Find ALL sequences for this parameter (use UID, not path)
        const paramUid = this.contextParameter.uid || this.contextParameter.id;
        console.log('🔍 Looking for sequences with target_parameter:', paramUid);
        console.log('📋 Available sequences:', this.sequences.map(s => ({
            id: s.id,
            target_parameter: s.target_parameter,
            type: s.type
        })));
        
        const existingSequences = this.sequences.filter(s => s.target_parameter === paramUid);
        console.log('✅ Found sequences:', existingSequences.length);
        
        if (existingSequences.length > 0) {
            console.log(`✅ Found ${existingSequences.length} sequence(s) to remove:`, existingSequences.map(s => s.id));
            
            // Delete all sequences for this parameter (skip confirmation since user already chose Remove from menu)
            for (const seq of existingSequences) {
                this.currentSequence = seq;
                await this.deleteSequence(true); // skipConfirm=true
            }
            
            this.showNotification(`Removed ${existingSequences.length} sequence(s)`, 'success');
            
            // Restore default triple slider UI (hide dynamic settings)
            console.log('🔄 Restoring default UI for controlId:', this.contextParameter.controlId);
            this.restoreDefaultTripleSlider(this.contextParameter.controlId);
        } else {
            console.warn('⚠️ No sequence found for parameter:', paramUid);
            // Even if no sequence exists, hide the dynamic settings
            this.restoreDefaultTripleSlider(this.contextParameter.controlId);
            this.showNotification('No sequence found for this parameter', 'warning');
        }
    }
    
    /**
     * Restore default triple slider (hide audio/timeline controls, show triple slider)
     */
    restoreDefaultTripleSlider(controlId) {
        console.log('🔄 Restoring default triple slider for:', controlId);
        
        if (!controlId) {
            console.warn('⚠️ No controlId provided for restoring triple slider');
            return;
        }
        
        // Hide audio controls (param-dynamic-settings in new grid layout)
        const audioControls = document.getElementById(`${controlId}_audio_controls`);
        if (audioControls) {
            audioControls.style.display = 'none';
            console.log('✅ Hidden audio controls');
            
            // Remove any active classes from inline buttons (cleanup)
            const inlineButtons = audioControls.querySelectorAll('.audio-band-btn-inline, .audio-dir-btn-inline');
            inlineButtons.forEach(btn => btn.classList.remove('active'));
        }
        
        // Hide timeline controls
        const timelineControls = document.getElementById(`${controlId}_timeline_controls`);
        if (timelineControls) {
            timelineControls.style.display = 'none';
            console.log('✅ Hidden timeline controls');
        }
        
        // Hide BPM controls
        const bpmControls = document.getElementById(`${controlId}_bpm_controls`);
        if (bpmControls) {
            bpmControls.style.display = 'none';
            console.log('✅ Hidden BPM controls');
        }
    }
    
    /**
     * Show inline timeline controls WITHOUT creating sequence (user will create by configuring first)
     */
    showInlineTimelineControlsEmpty(parameterId) {
        console.log('📈 Showing empty timeline controls for:', parameterId);
        
        // Use controlId from context parameter (passed from button click)
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // FIRST: Hide all other inline controls to prevent stacking
        this.hideInlineAudioControls(parameterId);
        this.hideInlineBPMControls(parameterId);
        
        const controlsContainer = document.getElementById(`${controlId}_timeline_controls`);
        
        console.log('🔍 Looking for timeline controls:', `${controlId}_timeline_controls`);
        
        if (!controlsContainer) {
            console.warn('⚠️ Timeline controls container not found for:', parameterId, 'controlId:', controlId);
            return;
        }
        
        // Show the controls (param-dynamic-settings in new grid layout)
        controlsContainer.style.display = 'block';
        
        // Track selected loop mode, playback state, and duration
        let selectedLoopMode = 'once';
        let playbackState = 'pause'; // 'forward', 'backward', 'pause'
        let duration = 5.0; // Default 5 seconds
        
        // Function to create sequence when configuration is complete
        const createSequence = () => {
            this.createTimelineSequenceWithConfig(parameterId, {
                loop_mode: selectedLoopMode,
                duration: duration,
                playback_state: playbackState
            });
        };
        
        // Set up playback buttons
        const playButtons = controlsContainer.querySelectorAll('.timeline-play-btn-inline');
        playButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.onclick = () => {
                // Toggle active state
                playButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                playbackState = btn.dataset.direction;
                console.log('📈 Playback state selected:', playbackState);
                createSequence(); // Create/update sequence immediately
            };
        });
        
        // Set default pause button as active
        const pauseBtn = controlsContainer.querySelector('.timeline-play-btn-inline[data-direction="pause"]');
        if (pauseBtn) {
            pauseBtn.classList.add('active');
        }
        
        // Set up loop mode dropdown
        const loopDropdown = controlsContainer.querySelector('.timeline-loop-dropdown-inline');
        if (loopDropdown) {
            loopDropdown.value = selectedLoopMode;
            loopDropdown.onchange = () => {
                selectedLoopMode = loopDropdown.value;
                console.log('📈 Loop mode selected:', selectedLoopMode);
                createSequence(); // Create/update sequence immediately
            };
        }
        
        // Set up duration input
        const durationInput = controlsContainer.querySelector('.timeline-duration-input-inline');
        if (durationInput) {
            durationInput.value = duration;
            durationInput.onchange = () => {
                duration = parseFloat(durationInput.value) || 5.0;
                console.log('⏱️ Duration changed:', duration);
                createSequence(); // Create/update sequence immediately
            };
        }
        
        // Set up speed circular slider
        const speedKnobContainer = document.getElementById(`${controlId}_timeline_speed`);
        if (speedKnobContainer && !speedKnobContainer._circularSlider) {
            const speedSlider = new CircularSlider(speedKnobContainer, {
                min: 0.1,
                max: 10.0,
                value: 1.0,
                step: 0.1,
                arc: 270,
                startAngle: 135,
                size: 'tiny',
                label: '',
                decimals: 1,
                unit: '×',
                variant: 'primary',
                showValue: true,
                onChange: (value) => {
                    console.log('⚡ Speed changed:', value);
                    createSequence(); // Create/update sequence immediately
                }
            });
            speedKnobContainer._circularSlider = speedSlider;
        }
        
        console.log('✅ Timeline controls shown (ready to configure)');
    }
    
    /**
     * Get current clip duration (in seconds) from active player/clip
    /**
     * Get current clip duration for BPM sequence
     */
    getCurrentClipDuration() {
        // Try to get duration from current video player clip
        try {
            // Check session state for current clip
            const sessionState = window.sessionStateLoader?.cachedState;
            if (!sessionState) {
                console.debug('⚠️ No session state available, using default duration');
                return 10.0; // Default 10 seconds
            }
            
            // Get video player state
            const videoPlayer = sessionState.players?.video;
            if (!videoPlayer) {
                console.debug('⚠️ No video player state, using default duration');
                return 10.0;
            }
            
            // Get current clip
            const currentClipIndex = videoPlayer.current_clip_index || 0;
            const currentClip = videoPlayer.clips?.[currentClipIndex];
            
            if (!currentClip) {
                console.warn('⚠️ No current clip found');
                return 10.0;
            }
            
            // Try to get duration from clip config
            const duration = currentClip.config?.duration;
            if (duration && duration > 0) {
                console.log('✅ Got clip duration from config:', duration);
                return duration;
            }
            
            // Fallback: Try to get from clip metadata
            const metadata = currentClip.metadata;
            if (metadata?.duration && metadata.duration > 0) {
                console.log('✅ Got clip duration from metadata:', metadata.duration);
                return metadata.duration;
            }
            
            console.warn('⚠️ Could not determine clip duration, using default');
            return 10.0;
            
        } catch (error) {
            console.error('❌ Error getting clip duration:', error);
            return 10.0; // Default 10 seconds
        }
    }
    
    /**
     * Create timeline sequence with specific configuration (when user configures)
     */
    async createTimelineSequenceWithConfig(parameterId, updates) {
        console.log('🎯 Creating timeline sequence with config:', { parameterId, updates });
        
        // Use stored controlId from context parameter
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // Get speed from circular slider
        const speedKnobContainer = document.getElementById(`${controlId}_timeline_speed`);
        const speed = speedKnobContainer?._circularSlider?.getValue() || updates.speed || 1.0;
        
        // Get duration from input field
        const durationInput = document.getElementById(`${controlId}_timeline_controls`)?.querySelector('.timeline-duration-input-inline');
        const duration = durationInput ? parseFloat(durationInput.value) || 5.0 : (updates.duration || 5.0);
        
        // Get min/max from triple slider
        const tripleSlider = getTripleSlider(controlId);
        let minValue = 0;
        let maxValue = 100;
        
        console.log('🔍 Looking for triple slider:', controlId);
        console.log('🔍 Slider instance:', tripleSlider);
        
        if (tripleSlider) {
            const range = tripleSlider.getRange();
            minValue = range.min;
            maxValue = range.max;
            console.log('📊 Using slider range:', { minValue, maxValue });
        } else {
            console.warn('⚠️ Triple slider not found, using defaults:', { minValue, maxValue });
        }
        
        // Create config with values from UI
        const config = {
            loop_mode: updates.loop_mode,
            duration: duration,
            playback_state: updates.playback_state || 'pause',
            speed: speed,
            min_value: minValue,
            max_value: maxValue
        };
        
        const data = {
            type: 'timeline',
            target_parameter: this.contextParameter.uid || parameterId,
            config: config
        };
        
        console.log('📦 Creating timeline sequence with UID:', this.contextParameter.uid, 'config:', data);
        
        try {
            // Check if sequence already exists and update it
            const existingSequence = this.sequences.find(s => s.target_parameter === parameterId);
            
            let response;
            if (existingSequence) {
                // Update existing sequence
                console.log('🔄 Updating existing timeline sequence:', existingSequence.id);
                response = await fetch(`/api/sequences/${existingSequence.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config: config })
                });
            } else {
                // Create new sequence
                console.log('➕ Creating new timeline sequence');
                response = await fetch('/api/sequences', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
            }
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Timeline sequence saved:', result);
                
                await window.sessionStateLoader.reload();
                await this.loadSequencesFromSessionState();
                
                const savedSequence = this.sequences.find(s => s.target_parameter === parameterId);
                if (savedSequence) {
                    this.showInlineTimelineControls(parameterId, savedSequence);
                }
                
                if (!existingSequence) {
                    this.showNotification('Timeline sequence created!', 'success');
                }
            } else {
                const error = await response.json();
                console.error('❌ Server error:', error);
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('❌ Error creating timeline sequence:', error);
            this.showNotification('Failed to create timeline sequence', 'error');
        }
    }
    
    /**
     * Show inline timeline controls with existing sequence
     */
    showInlineTimelineControls(parameterId, sequence) {
        console.log('📈 showInlineTimelineControls called:', { parameterId, sequence });
        
        // Find the control container by parameter path
        const controlId = this.parameterPathToControlId(parameterId);
        console.log('🔍 Looking for control ID:', `${controlId}_timeline_controls`);
        
        const controlsContainer = document.getElementById(`${controlId}_timeline_controls`);
        
        if (!controlsContainer) {
            console.warn('⚠️ Timeline controls container not found for:', parameterId);
            console.warn('   Expected element ID:', `${controlId}_timeline_controls`);
            const allControls = document.querySelectorAll('[id$="_timeline_controls"]');
            console.log('   Available timeline control elements:', Array.from(allControls).map(el => el.id));
            return;
        }
        
        console.log('✅ Found timeline controls container');
        
        // Show the controls
        controlsContainer.style.display = 'block';
        
        // Set active states from sequence
        if (sequence && sequence.config) {
            // Set loop mode
            const loopDropdown = controlsContainer.querySelector('.timeline-loop-dropdown-inline');
            if (loopDropdown) {
                loopDropdown.value = sequence.config.loop_mode || 'once';
                loopDropdown.onchange = () => {
                    this.updateTimelineSequenceInline(parameterId, { loop_mode: loopDropdown.value });
                };
            }
            
            // Set speed
            const speedInput = controlsContainer.querySelector('.timeline-speed-input-inline');
            if (speedInput) {
                speedInput.value = sequence.config.speed || 1.0;
                speedInput.onchange = () => {
                    const speed = parseFloat(speedInput.value) || 1.0;
                    this.updateTimelineSequenceInline(parameterId, { speed: speed });
                };
            }
            
            // Set playback button handlers with API update
            const playButtons = controlsContainer.querySelectorAll('.timeline-play-btn-inline');
            playButtons.forEach(btn => {
                btn.onclick = () => {
                    playButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    // Update playback state in backend
                    this.updateTimelineSequenceInline(parameterId, { playback_state: btn.dataset.direction });
                };
            });
        }
    }
    
    /**
     * Hide inline timeline controls for a parameter
     */
    hideInlineTimelineControls(parameterId) {
        const controlId = this.parameterPathToControlId(parameterId);
        const controlsContainer = document.getElementById(`${controlId}_timeline_controls`);
        
        if (controlsContainer) {
            controlsContainer.style.display = 'none';
        }
    }
    
    /**
     * Show inline BPM controls WITHOUT creating sequence (user will create by configuring)
     */
    showInlineBPMControlsEmpty(parameterId) {
        console.log('🥁 Showing empty BPM controls for:', parameterId);
        
        // Use controlId from context parameter (passed from button click)
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // FIRST: Hide all other inline controls to prevent stacking
        this.hideInlineAudioControls(parameterId);
        this.hideInlineTimelineControls(parameterId);
        
        const controlsContainer = document.getElementById(`${controlId}_bpm_controls`);
        
        console.log('🔍 Looking for BPM controls:', `${controlId}_bpm_controls`);
        
        if (!controlsContainer) {
            console.warn('⚠️ BPM controls container not found for:', parameterId, 'controlId:', controlId);
            return;
        }
        
        // Show the controls
        controlsContainer.style.display = 'block';
        
        // Get current clip duration automatically
        const clipDuration = this.getCurrentClipDuration();
        console.log('⏱️ Current clip duration:', clipDuration);
        
        // Track selected settings
        let beatDivision = 8;
        let loopMode = 'once';
        let playbackState = 'pause';
        let speed = 1.0;
        
        // Function to create sequence when configuration changes
        const createSequence = () => {
            this.createBPMSequenceWithConfig(parameterId, {
                beat_division: beatDivision,
                clip_duration: clipDuration,
                loop_mode: loopMode,
                playback_state: playbackState,
                speed: speed
            });
        };
        
        // Set up playback buttons
        const playButtons = controlsContainer.querySelectorAll('.bpm-play-btn-inline');
        playButtons.forEach(btn => {
            btn.classList.remove('active');
            btn.onclick = () => {
                // Toggle active state
                playButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                playbackState = btn.dataset.direction;
                console.log('🥁 Playback state selected:', playbackState);
                createSequence(); // Create/update sequence immediately
            };
        });
        
        // Set default pause button as active
        const pauseBtn = controlsContainer.querySelector('.bpm-play-btn-inline[data-direction="pause"]');
        if (pauseBtn) {
            pauseBtn.classList.add('active');
        }
        
        // Set up loop mode dropdown
        const loopDropdown = controlsContainer.querySelector('.bpm-loop-dropdown-inline');
        if (loopDropdown) {
            loopDropdown.value = loopMode;
            loopDropdown.onchange = () => {
                loopMode = loopDropdown.value;
                console.log('🥁 Loop mode selected:', loopMode);
                createSequence(); // Create/update sequence immediately
            };
        }
        
        // Set up speed knob (circular slider)
        const speedKnobContainer = document.getElementById(`${controlId}_bpm_speed`);
        if (speedKnobContainer && !speedKnobContainer._circularSlider) {
            const speedSlider = new CircularSlider(speedKnobContainer, {
                min: 0.1,
                max: 10.0,
                value: speed,
                step: 0.1,
                arc: 270,
                startAngle: 135,
                size: 'tiny',
                label: '',
                decimals: 1,
                unit: '×',
                variant: 'primary',
                showValue: true,
                onChange: (value) => {
                    speed = value;
                    console.log('⚡ Speed changed:', speed);
                    createSequence(); // Create/update sequence immediately
                }
            });
            speedKnobContainer._circularSlider = speedSlider;
        }
        
        // Set up beat division dropdown
        const divisionDropdown = controlsContainer.querySelector('.bpm-division-dropdown-inline');
        if (divisionDropdown) {
            divisionDropdown.value = beatDivision;
            divisionDropdown.onchange = () => {
                beatDivision = parseFloat(divisionDropdown.value);
                console.log('🥁 Beat division selected:', beatDivision);
                createSequence(); // Create/update sequence immediately
            };
        }
        
        console.log('✅ BPM controls shown (ready to configure)');
    }
    
    /**
     * Create BPM sequence with specific configuration (when user configures)
     */
    async createBPMSequenceWithConfig(parameterId, updates) {
        console.log('🎯 Creating BPM sequence with config:', { parameterId, updates });
        
        // Get controlId for accessing UI elements
        const controlId = this.contextParameter?.controlId || this.parameterPathToControlId(parameterId);
        
        // Get beat division from updates (supports fractional beats like 0.5)
        const beatDivision = updates.beat_division || 8;
        
        // Get speed from input if not provided
        const speedInput = document.getElementById(`${controlId}_bpm_controls`)?.querySelector('.bpm-speed-input-inline');
        const speed = updates.speed !== undefined ? updates.speed : (speedInput ? parseFloat(speedInput.value) : 1.0);
        
        // Get min/max from triple slider
        const tripleSlider = getTripleSlider(controlId);
        let minValue = 0;
        let maxValue = 100;
        
        if (tripleSlider) {
            const range = tripleSlider.getRange();
            minValue = range.min;
            maxValue = range.max;
            console.log('📊 Using slider range:', { minValue, maxValue });
        } else {
            console.warn('⚠️ Triple slider not found, using defaults:', { minValue, maxValue });
        }
        
        const data = {
            type: 'bpm',
            target_parameter: this.contextParameter.uid || parameterId,
            config: {
                beat_division: beatDivision,
                clip_duration: updates.clip_duration || 10.0,
                loop_mode: updates.loop_mode || 'once',
                playback_state: updates.playback_state || 'pause',
                speed: speed,
                min_value: minValue,
                max_value: maxValue
            }
        };
        
        console.log('📦 Creating BPM sequence with UID:', this.contextParameter.uid, 'config:', data);
        
        try {
            const response = await fetch('/api/sequences', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ BPM sequence created:', result);
                
                await window.sessionStateLoader.reload();
                await this.loadSequencesFromSessionState();
                
                const savedSequence = this.sequences.find(s => s.target_parameter === parameterId);
                if (savedSequence) {
                    this.showInlineBPMControls(parameterId, savedSequence);
                }
                
                this.showNotification('BPM sequence applied!', 'success');
            } else {
                const error = await response.json();
                console.error('❌ Server error:', error);
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('❌ Error creating BPM sequence:', error);
            this.showNotification('Failed to create BPM sequence', 'error');
        }
    }
    
    /**
     * Show inline BPM controls with existing sequence
     */
    showInlineBPMControls(parameterId, sequence) {
        console.log('🥁 showInlineBPMControls called:', { parameterId, sequence });
        
        // Find the control container by parameter path
        const controlId = this.parameterPathToControlId(parameterId);
        console.log('🔍 Looking for control ID:', `${controlId}_bpm_controls`);
        
        const controlsContainer = document.getElementById(`${controlId}_bpm_controls`);
        
        if (!controlsContainer) {
            console.warn('⚠️ BPM controls container not found for:', parameterId);
            return;
        }
        
        // Show controls
        controlsContainer.style.display = 'block';
        
        // Update playback buttons
        const playButtons = controlsContainer.querySelectorAll('.bpm-play-btn-inline');
        playButtons.forEach(btn => {
            if (btn.dataset.direction === sequence.config?.playback_state) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        // Update loop mode dropdown
        const loopDropdown = controlsContainer.querySelector('.bpm-loop-dropdown-inline');
        if (loopDropdown && sequence.config?.loop_mode) {
            loopDropdown.value = sequence.config.loop_mode;
            loopDropdown.onchange = () => {
                this.updateBPMSequenceInline(parameterId, { 
                    loop_mode: loopDropdown.value 
                });
            };
        }
        
        // Update speed input
        const speedInput = controlsContainer.querySelector('.bpm-speed-input-inline');
        if (speedInput && sequence.config?.speed !== undefined) {
            speedInput.value = sequence.config.speed;
            speedInput.onchange = () => {
                this.updateBPMSequenceInline(parameterId, { 
                    speed: parseFloat(speedInput.value) || 1.0 
                });
            };
        }
        
        // Update beat division dropdown
        const divisionDropdown = controlsContainer.querySelector('.bpm-division-dropdown-inline');
        if (divisionDropdown && sequence.config?.beat_division) {
            divisionDropdown.value = sequence.config.beat_division;
            divisionDropdown.onchange = () => {
                this.updateBPMSequenceInline(parameterId, { 
                    beat_division: parseFloat(divisionDropdown.value) 
                });
            };
        }
        
        // Set playback button handlers with API update
        playButtons.forEach(btn => {
            btn.onclick = () => {
                playButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                // Update playback state in backend
                this.updateBPMSequenceInline(parameterId, { playback_state: btn.dataset.direction });
            };
        });
    }
    
    /**
     * Hide inline BPM controls for a parameter
     */
    hideInlineBPMControls(parameterId) {
        const controlId = this.parameterPathToControlId(parameterId);
        const controlsContainer = document.getElementById(`${controlId}_bpm_controls`);
        
        if (controlsContainer) {
            controlsContainer.style.display = 'none';
        }
    }
    
    /**
     * Update BPM sequence parameters inline (without opening modal)
     */
    async updateBPMSequenceInline(parameterId, updates) {
        // parameterId can be either UID or dot-notation path
        // Try to find sequence by both
        const sequence = this.sequences.find(s => 
            s.target_parameter === parameterId || 
            s.id === parameterId ||
            (this.contextParameter && this.contextParameter.uid === parameterId)
        );
        
        if (!sequence) {
            console.warn('⚠️ No BPM sequence found for parameter:', parameterId);
            return;
        }
        
        console.log('🔄 Updating BPM sequence inline:', sequence.id, updates);
        
        try {
            const response = await fetch(`/api/sequences/${sequence.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: updates })
            });
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ BPM sequence updated:', result);
                
                await window.sessionStateLoader.reload();
                await this.loadSequencesFromSessionState();
            } else {
                const error = await response.json();
                console.error('❌ Server error:', error);
            }
        } catch (error) {
            console.error('❌ Error updating BPM sequence:', error);
        }
    }
    
    /**
     * Update timeline sequence parameters inline (without opening modal)
     */
    async updateTimelineSequenceInline(parameterId, updates) {
        const sequence = this.sequences.find(s => s.target_parameter === parameterId);
        if (!sequence) {
            console.warn('⚠️ No timeline sequence found for:', parameterId);
            return;
        }
        
        try {
            // Merge updates with existing sequence data
            const updatedConfig = {
                loop_mode: updates.loop_mode !== undefined ? updates.loop_mode : sequence.loop_mode,
                duration: updates.duration !== undefined ? updates.duration : sequence.duration,
                playback_state: updates.playback_state !== undefined ? updates.playback_state : sequence.playback_state,
                speed: updates.speed !== undefined ? updates.speed : sequence.speed,
                min_value: updates.min_value !== undefined ? updates.min_value : sequence.min_value,
                max_value: updates.max_value !== undefined ? updates.max_value : sequence.max_value
            };
            
            console.log('🔄 Updating timeline sequence:', updatedConfig);
            
            const response = await fetch(`/api/sequences/${sequence.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: updatedConfig })
            });
            
            if (response.ok) {
                await window.sessionStateLoader.reload();
                await this.loadSequencesFromSessionState();
                
                // Update UI to reflect changes
                const controlId = this.parameterPathToControlId(parameterId);
                const controlsContainer = document.getElementById(`${controlId}_timeline_controls`);
                
                if (controlsContainer && updates.loop_mode) {
                    const loopDropdown = controlsContainer.querySelector('.timeline-loop-dropdown-inline');
                    if (loopDropdown) {
                        loopDropdown.value = updates.loop_mode;
                    }
                }
            }
        } catch (error) {
            console.error('Error updating timeline sequence inline:', error);
        }
    }
    
    /**
     * Restore default triple slider (hide audio/timeline controls, show triple slider)
     */
    restoreDefaultTripleSlider(controlId) {
        console.log('🔄 Restoring default triple slider for:', controlId);
        
        if (!controlId) {
            console.warn('⚠️ No controlId provided for restoring triple slider');
            return;
        }
        
        // Hide audio controls (param-dynamic-settings in new grid layout)
        const audioControls = document.getElementById(`${controlId}_audio_controls`);
        if (audioControls) {
            audioControls.style.display = 'none';
            console.log('✅ Hidden audio controls');
            
            // Remove any active classes from inline buttons (cleanup)
            const inlineButtons = audioControls.querySelectorAll('.audio-band-btn-inline, .audio-dir-btn-inline');
            inlineButtons.forEach(btn => btn.classList.remove('active'));
        }
        
        // Hide timeline controls
        const timelineControls = document.getElementById(`${controlId}_timeline_controls`);
        if (timelineControls) {
            timelineControls.style.display = 'none';
            console.log('✅ Hidden timeline controls');
        }
        
        // Show triple slider container (inside param-slider in new grid layout)
        const tripleSliderContainer = document.getElementById(controlId);
        if (tripleSliderContainer) {
            // The triple slider container should already be visible in grid layout
            // Just ensure it's not hidden
            tripleSliderContainer.style.display = '';
            console.log('✅ Restored triple slider display');
        }
        
        this.showNotification('Parameter reset to default', 'success');
    }
    
    /**
     * Open sequence editor for a parameter
     * @deprecated Use inline controls instead (showInlineAudioControls, showInlineLFOControls, etc.)
     */
    openEditor(parameterId, parameterLabel, currentValue, presetType = null) {
        console.warn('⚠️ openEditor is DEPRECATED - use inline controls instead');
        return; // Modal disabled - use inline controls
        console.log('🔓 openEditor called:', { parameterId, parameterLabel, currentValue, presetType });
        
        this.currentParameter = {
            id: parameterId,
            label: parameterLabel,
            value: currentValue
        };
        
        console.log('📌 Set currentParameter:', this.currentParameter);
        
        // Check if sequence already exists for this parameter
        const existing = this.sequences.find(s => s.target_parameter === parameterId);
        if (existing && !presetType) {
            this.currentSequence = existing;
            this.loadSequenceIntoEditor(existing);
            console.log('✏️ Editing existing sequence:', existing);
        } else {
            this.currentSequence = null;
            this.resetEditor();
            
            // Select preset type if provided
            if (presetType) {
                this.selectType(presetType);
                console.log('🎯 Preset type selected:', presetType);
            }
            
            console.log('➕ Creating new sequence');
        }
        
        // Update modal title
        document.getElementById('sequenceParameterName').textContent = parameterLabel;
        
        // Show modal
        const modal = document.getElementById('sequenceModal');
        modal.classList.add('show');
        modal.style.display = 'block';
        console.log('✅ Modal shown');
    }
    
    /**
     * Close sequence editor
     * @deprecated Modal no longer used
     */
    closeEditor() {
        console.warn('⚠️ closeEditor is DEPRECATED - modal no longer used');
        return; // Modal disabled
        console.log('🔒 closeEditor called');
        const modal = document.getElementById('sequenceModal');
        if (modal) {
            modal.classList.remove('show');
            modal.style.display = 'none';
        }
        this.currentParameter = null;
        this.currentSequence = null;
    }
    
    /**
     * Reset editor to default state
     * @deprecated Modal no longer used
     */
    resetEditor() {
        console.warn('⚠️ resetEditor is DEPRECATED - modal no longer used');
        return; // Modal disabled
        // Select Audio type by default
        this.selectType('audio');
        
        // Reset audio form
        document.getElementById('audioFeature').value = 'rms';
        document.getElementById('audioMinValue').value = '0';
        document.getElementById('audioMaxValue').value = '100';
        document.getElementById('audioInvert').checked = false;
        
        // Reset audio band selection (default to bass)
        this.selectAudioBand('bass');
        
        // Reset audio direction (default to rise-from-max)
        this.selectAudioDirection('rise-from-max');
        
        // Reset attack/release knob to 0.5
        if (this.audioAttackReleaseSlider) {
            this.audioAttackReleaseSlider.setValue(0.5);
        }
        
        // Reset LFO form
        document.getElementById('lfoWaveform').value = 'sine';
        document.getElementById('lfoFrequency').value = '1.0';
        document.getElementById('lfoAmplitude').value = '1.0';
        document.getElementById('lfoPhase').value = '0.0';
        document.getElementById('lfoMinValue').value = '0';
        document.getElementById('lfoMaxValue').value = '100';
        
        // Reset timeline form
        document.getElementById('timelineKeyframes').innerHTML = '<p style="color: #666; text-align: center;">No keyframes yet</p>';
        document.getElementById('timelineInterpolation').value = 'linear';
        document.getElementById('timelineLoopMode').value = 'once';
        document.getElementById('timelineDuration').value = '10.0';
        
        // Clear keyframes array
        this.timelineKeyframes = [];
    }
    
    /**
     * Load existing sequence into editor
     */
    loadSequenceIntoEditor(sequence) {
        this.selectType(sequence.type);
        
        const config = sequence.config || sequence;
        
        if (sequence.type === 'audio') {
            document.getElementById('audioFeature').value = config.feature || 'rms';
            document.getElementById('audioMinValue').value = config.min_value || 0;
            document.getElementById('audioMaxValue').value = config.max_value || 100;
            document.getElementById('audioInvert').checked = config.invert || false;
            
            // Restore band selection
            const band = config.band || 'bass';
            this.selectAudioBand(band);
            
            // Restore direction selection
            const direction = config.direction || 'rise-from-min';
            this.selectAudioDirection(direction);
            
            // Restore attack/release
            if (this.audioAttackReleaseKnob && config.attack_release !== undefined) {
                this.audioAttackReleaseKnob.setValue(config.attack_release);
            }
        } else if (sequence.type === 'lfo') {
            document.getElementById('lfoWaveform').value = config.waveform || 'sine';
            document.getElementById('lfoFrequency').value = config.frequency || 1.0;
            document.getElementById('lfoAmplitude').value = config.amplitude || 1.0;
            document.getElementById('lfoPhase').value = config.phase || 0.0;
            document.getElementById('lfoMinValue').value = config.min_value || 0;
            document.getElementById('lfoMaxValue').value = config.max_value || 100;
        } else if (sequence.type === 'timeline') {
            this.timelineKeyframes = config.keyframes || [];
            this.renderKeyframesList();
            document.getElementById('timelineInterpolation').value = config.interpolation || 'linear';
            document.getElementById('timelineLoopMode').value = config.loop_mode || 'once';
            document.getElementById('timelineDuration').value = config.duration || 10.0;
            this.drawTimelinePreview();
        }
    }
    
    /**
     * Select sequence type
     * @deprecated Modal no longer used
     */
    selectType(type) {
        console.warn('⚠️ selectType is DEPRECATED - modal no longer used');
        return; // Modal disabled
        // Update buttons
        document.querySelectorAll('.sequence-type-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-type="${type}"]`).classList.add('active');
        
        // Show/hide controls
        document.querySelectorAll('.sequence-controls').forEach(ctrl => {
            ctrl.style.display = 'none';
        });
        document.getElementById(`${type}Controls`).style.display = 'block';
        
        // Initialize canvases if needed
        if (type === 'audio' && !this.spectrumCanvas) {
            this.spectrumCanvas = document.getElementById('audioSpectrumCanvas');
            this.drawAudioSpectrum();
            // Initialize attack/release knob
            this.initAudioAttackReleaseKnob();
        } else if (type === 'lfo' && !this.lfoCanvas) {
            this.lfoCanvas = document.getElementById('lfoPreviewCanvas');
            this.drawLFOPreview();
        } else if (type === 'timeline' && !this.timelineCanvas) {
            this.timelineCanvas = document.getElementById('timelineCanvas');
            this.drawTimelinePreview();
        }
    }
    
    /**
     * Save sequence
     */
    async saveSequence() {
        console.log('💾 saveSequence() called');
        console.log('📌 currentParameter:', this.currentParameter);
        
        if (!this.currentParameter) {
            console.error('❌ No currentParameter set!');
            this.showNotification('No parameter selected. Please close and reopen the editor.', 'error');
            return;
        }
        
        const typeBtn = document.querySelector('.sequence-type-btn.active');
        if (!typeBtn) {
            console.error('❌ No active sequence type button found');
            this.showNotification('Please select a sequence type', 'error');
            return;
        }
        
        const type = typeBtn.dataset.type;
        console.log('📝 Sequence type:', type);
        
        let config = {};
        
        if (type === 'audio') {
            // Get selected band
            const selectedBand = document.querySelector('.audio-band-btn.active')?.dataset.band || 'bass';
            // Get selected direction
            const selectedDirection = document.querySelector('.audio-direction-btn.active')?.dataset.direction || 'rise-from-min';
            // Get attack/release value
            const attackRelease = this.audioAttackReleaseKnob ? this.audioAttackReleaseKnob.getValue() : 0.1;
            
            config = {
                feature: document.getElementById('audioFeature').value,
                band: selectedBand,
                direction: selectedDirection,
                attack_release: attackRelease,
                min_value: parseFloat(document.getElementById('audioMinValue').value),
                max_value: parseFloat(document.getElementById('audioMaxValue').value),
                invert: document.getElementById('audioInvert').checked
            };
        } else if (type === 'lfo') {
            config = {
                waveform: document.getElementById('lfoWaveform').value,
                frequency: parseFloat(document.getElementById('lfoFrequency').value),
                amplitude: parseFloat(document.getElementById('lfoAmplitude').value),
                phase: parseFloat(document.getElementById('lfoPhase').value),
                min_value: parseFloat(document.getElementById('lfoMinValue').value),
                max_value: parseFloat(document.getElementById('lfoMaxValue').value)
            };
        } else if (type === 'timeline') {
            config = {
                keyframes: this.timelineKeyframes,
                interpolation: document.getElementById('timelineInterpolation').value,
                loop_mode: document.getElementById('timelineLoopMode').value,
                duration: parseFloat(document.getElementById('timelineDuration').value)
            };
        }
        
        const data = {
            type: type,
            target_parameter: this.currentParameter.id,
            config: config
        };
        
        console.log('📦 Data to send:', data);
        
        try {
            let response;
            if (this.currentSequence) {
                // Update existing
                console.log('🔄 Updating existing sequence:', this.currentSequence.id);
                response = await fetch(`/api/sequences/${this.currentSequence.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ config: config })
                });
            } else {
                // Create new
                console.log('➕ Creating new sequence');
                response = await fetch('/api/sequences', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
            }
            
            console.log('📡 Response status:', response.status);
            
            if (response.ok) {
                const result = await response.json();
                console.log('✅ Sequence saved:', result);
                await window.sessionStateLoader.reload(); // Force reload to get updated state
                await this.loadSequencesFromSessionState();
                
                // Show inline controls immediately if it's an audio sequence
                if (type === 'audio' && this.currentParameter) {
                    const savedSequence = this.sequences.find(s => s.target_parameter === this.currentParameter.id);
                    if (savedSequence) {
                        this.showInlineAudioControls(this.currentParameter.id, savedSequence);
                    }
                }
                
                this.closeEditor();
                this.showNotification('Sequence saved successfully!', 'success');
            } else {
                const error = await response.json();
                console.error('❌ Server error:', error);
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('❌ Error saving sequence:', error);
            this.showNotification('Failed to save sequence', 'error');
        }
    }
    
    /**
     * Delete sequence
     */
    async deleteSequence(skipConfirm = false) {
        if (!this.currentSequence) {
            this.showNotification('No sequence to delete', 'warning');
            return;
        }
        
        if (!skipConfirm && !confirm('Delete this sequence?')) {
            return;
        }
        
        // Save sequence ID before deletion (this.currentSequence may be cleared during the process)
        const sequenceId = this.currentSequence.id;
        
        try {
            const response = await fetch(`/api/sequences/${sequenceId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                console.log('✅ Sequence deleted:', sequenceId);
                await window.sessionStateLoader.reload(); // Force reload to get updated state
                await this.loadSequencesFromSessionState();
                // Clear references (modal is deprecated)
                this.currentSequence = null;
                this.currentParameter = null;
                if (!skipConfirm) {
                    this.showNotification('Sequence deleted', 'success');
                }
            } else {
                const error = await response.json();
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('Error deleting sequence:', error);
            this.showNotification('Failed to delete sequence', 'error');
        }
    }
    
    /**
     * Cleanup all sequences for a removed clip
     * @param {string} clipId - The UUID of the removed clip
     */
    async cleanupSequencesForClip(clipId) {
        if (!clipId) return;
        
        console.log(`🧹 Cleaning up sequences for removed clip: ${clipId}`);
        
        // Find all sequences whose target_parameter contains this clip_id
        // Format (NEW): param_clip_{clip_id}_effect_{idx}_{param}
        // Format (OLD): param_clip_{clip_id}_{param}_{uuid}
        const clipSequences = this.sequences.filter(seq => 
            seq.target_parameter && seq.target_parameter.includes(`_${clipId}_`)
        );
        
        if (clipSequences.length === 0) {
            console.log(`✅ No sequences found for clip ${clipId}`);
            return;
        }
        
        console.log(`🗑️ Found ${clipSequences.length} sequence(s) to delete for clip ${clipId}`);
        
        // Delete each sequence using existing deleteSequence method
        for (const seq of clipSequences) {
            this.currentSequence = seq;
            await this.deleteSequence(true); // skipConfirm=true
        }
        
        console.log(`✅ Cleanup complete for clip ${clipId}`);
    }
    
    /**
     * Cleanup all sequences for a specific effect on a clip
     * @param {string} clipId - The UUID of the clip
     * @param {string} pluginId - The plugin ID of the effect (e.g., 'transform', 'blur')
     */
    async cleanupSequencesForEffect(clipId, pluginId) {
        if (!clipId || !pluginId) return;
        
        console.log(`🧹 Cleaning up sequences for effect ${pluginId} on clip: ${clipId}`);
        
        // Find all sequences whose target_parameter matches this clip and plugin
        // Format (NEW): param_clip_{clip_id}_effect_{idx}_{param}
        // Format (OLD): param_clip_{clip_id}_{param}_... (matches by path)
        const effectSequences = this.sequences.filter(seq => {
            if (!seq.target_parameter || !seq.target_parameter.includes(`_${clipId}_`)) {
                return false;
            }
            // Also check if the parameter path includes the plugin_id
            // Path format: {player}.{clipId}.{pluginId}.{paramName}
            const pathParts = seq.target_parameter.split('.');
            return pathParts.length >= 3 && pathParts[2] === pluginId;
        });
        
        if (effectSequences.length === 0) {
            console.log(`✅ No sequences found for effect ${pluginId} on clip ${clipId}`);
            return;
        }
        
        console.log(`🗑️ Found ${effectSequences.length} sequence(s) to delete for effect ${pluginId}`);
        
        // Delete each sequence using existing deleteSequence method
        for (const seq of effectSequences) {
            this.currentSequence = seq;
            await this.deleteSequence(true); // skipConfirm=true
        }
        
        console.log(`✅ Cleanup complete for effect ${pluginId} on clip ${clipId}`);
    }
    
    /**
     * Cleanup all sequences for a specific layer
     * Checks all parameters on the layer's clip for the given layer_id
     * @param {string} clipId - The UUID of the clip
     * @param {number} layerId - The layer ID within the clip
     */
    async cleanupSequencesForLayer(clipId, layerId) {
        if (!clipId || layerId === undefined || layerId === null) return;
        
        console.log(`🧹 Cleaning up sequences for layer ${layerId} on clip: ${clipId}`);
        
        // Find all sequences whose target_parameter contains this clip_id and layer_id
        // Format (NEW): param_clip_{clip_id}_layer_{layer_idx}_effect_{idx}_{param}
        // Format (OLD): param_clip_{clip_id}_{param}_{uuid} (requires metadata check)
        const layerSequences = this.sequences.filter(seq => {
            if (!seq.target_parameter || !seq.target_parameter.includes(`_${clipId}_`)) {
                return false;
            }
            // Additional check: layer sequences have layerId in their context or metadata
            // For now, we'll remove all sequences for the clip+layer combination
            return true;
        });
        
        if (layerSequences.length === 0) {
            console.log(`✅ No sequences found for layer ${layerId} on clip ${clipId}`);
            return;
        }
        
        console.log(`🗑️ Found ${layerSequences.length} sequence(s) to delete for layer ${layerId}`);
        
        // Delete each sequence using existing deleteSequence method
        for (const seq of layerSequences) {
            this.currentSequence = seq;
            await this.deleteSequence(true); // skipConfirm=true
        }
        
        console.log(`✅ Cleanup complete for layer ${layerId} on clip ${clipId}`);
    }
    
    /**
     * Load sequences from centralized session state (flat by UID structure)
     */
    async loadSequencesFromSessionState() {
        try {
            // Wait for session state to load
            await window.sessionStateLoader.load();
            const state = window.sessionStateLoader.state;
            
            console.log('🔍 Loading sequences from flat structure...');
            
            // Load from flat sequences dictionary
            const sequencesData = state.sequences || {};
            const sequences = [];
            
            for (const [uid, seqList] of Object.entries(sequencesData)) {
                for (const seq of seqList) {
                    sequences.push(seq);
                    console.log(`✅ Loaded sequence for UID ${uid}:`, {
                        type: seq.type,
                        band: seq.band,
                        mode: seq.mode,
                        attack_release: seq.attack_release
                    });
                }
            }
            
            this.sequences = sequences;
            console.log(`📦 Loaded ${sequences.length} sequences from flat structure`);
            
            // Don't restore controls here - wait for renderClipEffects() to call it
            // when the DOM is actually ready (after clip is loaded and effects are rendered)
            
        } catch (error) {
            console.error('❌ Error loading sequences from session state:', error);
        }
    }
    
    /**
     * Restore inline audio controls for all audio sequences on page reload
     */
    restoreInlineAudioControls() {
        console.log('🔄 Restoring inline audio controls for audio sequences...');
        console.log('📊 Total sequences:', this.sequences.length);
        
        // Find all audio sequences
        const audioSequences = this.sequences.filter(seq => seq.type === 'audio');
        console.log(`📋 Found ${audioSequences.length} audio sequences to restore`);
        
        if (audioSequences.length === 0) {
            console.log('✅ No audio sequences to restore');
            return;
        }
        
        audioSequences.forEach((seq, index) => {
            console.log(`\n🔍 [${index + 1}/${audioSequences.length}] Processing sequence:`, {
                uid: seq.target_parameter,
                band: seq.band,
                mode: seq.mode
            });
            
            // Find the button with matching UID
            const button = document.querySelector(`[data-param-uid="${seq.target_parameter}"]`);
            if (!button) {
                console.log('❌ Button not found in DOM (parameter not visible)');
                return;
            }
            console.log('✅ Found button:', button);
            
            // Get the parameter control container (new grid layout)
            const paramControl = button.closest('.parameter-grid-row');
            if (!paramControl) {
                console.warn('❌ No parameter-grid-row found for button');
                return;
            }
            console.log('✅ Found parameter-grid-row');
            
            // Find the audio controls container
            const tripleSliderContainer = paramControl.querySelector('.triple-slider-container');
            if (!tripleSliderContainer) {
                console.warn('❌ No triple slider container found');
                return;
            }
            console.log('✅ Found triple-slider-container:', tripleSliderContainer.id);
            
            const controlId = tripleSliderContainer.id;
            const controlsContainer = document.getElementById(`${controlId}_audio_controls`);
            
            if (!controlsContainer) {
                console.warn('❌ No audio controls container found for:', controlId);
                return;
            }
            console.log('✅ Found audio controls container');
            console.log('📏 Current display style:', controlsContainer.style.display);
            
            // Show the controls
            controlsContainer.style.display = 'block';
            console.log('✅ Set display to block, new value:', controlsContainer.style.display);
            
            // Restore band selection (inline buttons)
            const bandButtons = controlsContainer.querySelectorAll('.audio-band-btn-inline');
            console.log('🔘 Found band buttons:', bandButtons.length);
            bandButtons.forEach(btn => {
                const isActive = btn.dataset.band === seq.band;
                btn.classList.toggle('active', isActive);
                // Attach onclick handler
                btn.onclick = () => {
                    // Update UI
                    bandButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    // Update sequence
                    this.updateSequenceInline(seq.target_parameter, { band: btn.dataset.band });
                };
                if (isActive) {
                    console.log('✅ Restored band:', seq.band);
                }
            });
            
            // Restore direction selection (inline buttons) - seq.mode, not seq.config.direction
            const dirButtons = controlsContainer.querySelectorAll('.audio-dir-btn-inline');
            console.log('🔘 Found direction buttons:', dirButtons.length);
            dirButtons.forEach(btn => {
                const isActive = btn.dataset.direction === seq.mode;
                btn.classList.toggle('active', isActive);
                // Attach onclick handler - send 'mode' to match backend
                btn.onclick = () => {
                    // Update UI
                    dirButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    // Update sequence - use 'mode' key for backend
                    this.updateSequenceInline(seq.target_parameter, { mode: btn.dataset.direction });
                };
                if (isActive) {
                    console.log('✅ Restored mode:', seq.mode);
                }
            });
            
            // Restore attack/release knob value
            const knobContainer = document.getElementById(`${controlId}_attack_release`);
            if (knobContainer) {
                console.log('✅ Found knob container, has slider:', !!knobContainer._circularSlider);
                
                // Create slider if it doesn't exist
                if (!knobContainer._circularSlider) {
                    console.log('🎛️ Creating new CircularSlider for restore');
                    const slider = new CircularSlider(knobContainer, {
                        min: 0.2,
                        max: 1.0,
                        value: seq.attack_release || 0.7,
                        step: 0.01,
                        arc: 270,
                        startAngle: 135,
                        size: 'tiny',
                        label: '',
                        decimals: 2,
                        unit: '',
                        variant: 'primary',
                        showValue: false,
                        onChange: (value) => {
                            this.updateSequenceInline(seq.target_parameter, { attack_release: value });
                        }
                    });
                    knobContainer._circularSlider = slider;
                    console.log('✅ Created and set attack_release:', seq.attack_release || 0.5);
                } else if (seq.attack_release !== undefined) {
                    // Update existing slider
                    knobContainer._circularSlider.setValue(seq.attack_release);
                    console.log('✅ Updated attack_release:', seq.attack_release);
                }
            } else {
                console.warn('❌ Knob container not found');
            }
            
            console.log('✅ Successfully restored controls for:', seq.target_parameter);
        });
        
        console.log('\n✅ Restore complete');
    }
    
    /**
     * Restore inline BPM controls for all BPM sequences on page reload
     */
    restoreInlineBPMControls() {
        console.log('🔄 Restoring inline BPM controls for BPM sequences...');
        console.log('📊 Total sequences:', this.sequences.length);
        
        // Find all BPM sequences
        const bpmSequences = this.sequences.filter(seq => seq.type === 'bpm');
        console.log(`📋 Found ${bpmSequences.length} BPM sequences to restore`);
        
        if (bpmSequences.length === 0) {
            console.log('✅ No BPM sequences to restore');
            return;
        }
        
        bpmSequences.forEach((seq, index) => {
            console.log(`\n🔍 [${index + 1}/${bpmSequences.length}] Processing BPM sequence:`, {
                uid: seq.target_parameter,
                beat_division: seq.beat_division,
                loop_mode: seq.loop_mode,
                speed: seq.speed,
                playback_state: seq.playback_state
            });
            
            // Find the button with matching UID
            const button = document.querySelector(`[data-param-uid="${seq.target_parameter}"]`);
            if (!button) {
                console.log('❌ Button not found in DOM (parameter not visible)');
                return;
            }
            console.log('✅ Found button');
            
            // Get the parameter control container (new grid layout)
            const paramControl = button.closest('.parameter-grid-row');
            if (!paramControl) {
                console.warn('❌ No parameter-grid-row found for button');
                return;
            }
            console.log('✅ Found parameter-grid-row');
            
            // Find the triple slider container
            const tripleSliderContainer = paramControl.querySelector('.triple-slider-container');
            if (!tripleSliderContainer) {
                console.warn('❌ No triple slider container found');
                return;
            }
            console.log('✅ Found triple-slider-container:', tripleSliderContainer.id);
            
            const controlId = tripleSliderContainer.id;
            const controlsContainer = document.getElementById(`${controlId}_bpm_controls`);
            
            if (!controlsContainer) {
                console.warn(`❌ BPM controls container not found for: ${controlId}`);
                return;
            }
            console.log('✅ Found BPM controls container');
            
            // Show controls
            controlsContainer.style.display = 'block';
            console.log('✅ Set display to block');
            
            // Restore playback state buttons
            const playButtons = controlsContainer.querySelectorAll('.bpm-play-btn-inline');
            const playbackState = seq.playback_state || 'pause';
            playButtons.forEach(btn => {
                btn.classList.remove('active');
                if (btn.dataset.direction === playbackState) {
                    btn.classList.add('active');
                    console.log('✅ Set active playback state:', playbackState);
                }
                // Attach click handler
                btn.onclick = () => {
                    playButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    this.updateBPMSequenceInline(seq.target_parameter, { playback_state: btn.dataset.direction });
                };
            });
            
            // Restore loop mode dropdown
            const loopDropdown = controlsContainer.querySelector('.bpm-loop-dropdown-inline');
            if (loopDropdown) {
                loopDropdown.value = seq.loop_mode || 'once';
                console.log('✅ Set loop mode:', loopDropdown.value);
                loopDropdown.onchange = () => {
                    this.updateBPMSequenceInline(seq.target_parameter, { loop_mode: loopDropdown.value });
                };
            }
            
            // Restore speed knob (circular slider)
            const speedKnobContainer = document.getElementById(`${controlId}_bpm_speed`);
            if (speedKnobContainer) {
                console.log('✅ Found speed knob container');
                
                // Create slider if it doesn't exist
                if (!speedKnobContainer._circularSlider) {
                    console.log('🎛️ Creating new CircularSlider for restore');
                    const slider = new CircularSlider(speedKnobContainer, {
                        min: 0.1,
                        max: 10.0,
                        value: seq.speed || 1.0,
                        step: 0.1,
                        arc: 270,
                        startAngle: 135,
                        size: 'tiny',
                        label: '',
                        decimals: 1,
                        unit: '×',
                        variant: 'primary',
                        showValue: true,
                        onChange: (value) => {
                            this.updateBPMSequenceInline(seq.target_parameter, { speed: value });
                        }
                    });
                    speedKnobContainer._circularSlider = slider;
                    console.log('✅ Created and set speed:', seq.speed || 1.0);
                } else if (seq.speed !== undefined) {
                    // Update existing slider
                    speedKnobContainer._circularSlider.setValue(seq.speed);
                    console.log('✅ Updated speed:', seq.speed);
                }
            } else {
                console.warn('❌ Speed knob container not found');
            }
            
            // Restore beat division dropdown
            const divisionDropdown = controlsContainer.querySelector('.bpm-division-dropdown-inline');
            if (divisionDropdown) {
                divisionDropdown.value = seq.beat_division || 8;
                console.log('✅ Set beat division:', divisionDropdown.value);
                divisionDropdown.onchange = () => {
                    this.updateBPMSequenceInline(seq.target_parameter, { beat_division: parseFloat(divisionDropdown.value) });
                };
            }
            
            console.log('✅ Successfully restored BPM controls for:', seq.target_parameter);
        });
        
        console.log('\n✅ BPM restore complete');
    }
    
    /**
     * Restore inline timeline controls for all timeline sequences on page reload
     */
    restoreInlineTimelineControls() {
        console.log('🔄 Restoring inline timeline controls for timeline sequences...');
        console.log('📊 Total sequences:', this.sequences.length);
        
        // Find all timeline sequences
        const timelineSequences = this.sequences.filter(seq => seq.type === 'timeline');
        console.log(`📋 Found ${timelineSequences.length} timeline sequences to restore`);
        
        if (timelineSequences.length === 0) {
            console.log('✅ No timeline sequences to restore');
            return;
        }
        
        timelineSequences.forEach((seq, index) => {
            console.log(`\n🔍 [${index + 1}/${timelineSequences.length}] Processing timeline sequence:`, {
                uid: seq.target_parameter,
                loop_mode: seq.loop_mode,
                duration: seq.duration,
                speed: seq.speed,
                playback_state: seq.playback_state
            });
            
            // Find the button with matching UID
            const button = document.querySelector(`[data-param-uid="${seq.target_parameter}"]`);
            if (!button) {
                console.log('❌ Button not found in DOM (parameter not visible)');
                return;
            }
            console.log('✅ Found button:', button);
            
            // Get the parameter control container (new grid layout)
            const paramControl = button.closest('.parameter-grid-row');
            if (!paramControl) {
                console.warn('❌ No parameter-grid-row found for button');
                return;
            }
            console.log('✅ Found parameter-grid-row');
            
            // Find the timeline controls container
            const tripleSliderContainer = paramControl.querySelector('.triple-slider-container');
            if (!tripleSliderContainer) {
                console.warn('❌ No triple slider container found');
                return;
            }
            console.log('✅ Found triple-slider-container:', tripleSliderContainer.id);
            
            const controlId = tripleSliderContainer.id;
            const controlsContainer = document.getElementById(`${controlId}_timeline_controls`);
            
            if (!controlsContainer) {
                console.warn('❌ No timeline controls container found for:', controlId);
                return;
            }
            console.log('✅ Found timeline controls container');
            console.log('📏 Current display style:', controlsContainer.style.display);
            
            // Show the controls
            controlsContainer.style.display = 'block';
            console.log('✅ Set display to block, new value:', controlsContainer.style.display);
            
            // Restore loop mode selection
            const loopDropdown = controlsContainer.querySelector('.timeline-loop-dropdown-inline');
            if (loopDropdown && seq.loop_mode) {
                loopDropdown.value = seq.loop_mode;
                console.log('✅ Restored loop mode:', seq.loop_mode);
                
                // Re-attach change handler
                loopDropdown.onchange = () => {
                    this.updateTimelineSequenceInline(seq.target_parameter, { loop_mode: loopDropdown.value });
                };
            } else {
                console.warn('❌ Loop dropdown not found');
            }
            
            // Restore duration input
            const durationInput = controlsContainer.querySelector('.timeline-duration-input-inline');
            if (durationInput) {
                durationInput.value = seq.duration || 5.0;
                console.log('✅ Restored duration:', seq.duration || 5.0);
                
                // Re-attach change handler
                durationInput.onchange = () => {
                    const duration = parseFloat(durationInput.value) || 5.0;
                    this.updateTimelineSequenceInline(seq.target_parameter, { duration: duration });
                };
            }
            
            // Restore speed knob (circular slider)
            const speedKnobContainer = document.getElementById(`${controlId}_timeline_speed`);
            if (speedKnobContainer) {
                console.log('✅ Found speed knob container');
                
                // Create slider if it doesn't exist
                if (!speedKnobContainer._circularSlider) {
                    console.log('🏛️ Creating new CircularSlider for restore');
                    const slider = new CircularSlider(speedKnobContainer, {
                        min: 0.1,
                        max: 10.0,
                        value: seq.speed || 1.0,
                        step: 0.1,
                        arc: 270,
                        startAngle: 135,
                        size: 'tiny',
                        label: '',
                        decimals: 1,
                        unit: '×',
                        variant: 'primary',
                        showValue: true,
                        onChange: (value) => {
                            this.updateTimelineSequenceInline(seq.target_parameter, { speed: value });
                        }
                    });
                    speedKnobContainer._circularSlider = slider;
                    console.log('✅ Created and set speed:', seq.speed || 1.0);
                } else if (seq.speed !== undefined) {
                    // Update existing slider
                    speedKnobContainer._circularSlider.setValue(seq.speed);
                    console.log('✅ Updated speed:', seq.speed);
                }
            } else {
                console.warn('❌ Speed knob container not found');
            }
            
            // Restore playback state
            const playButtons = controlsContainer.querySelectorAll('.timeline-play-btn-inline');
            const playbackState = seq.playback_state || 'pause';
            const activePlayBtn = controlsContainer.querySelector(`.timeline-play-btn-inline[data-direction="${playbackState}"]`);
            if (activePlayBtn) {
                playButtons.forEach(btn => btn.classList.remove('active'));
                activePlayBtn.classList.add('active');
                console.log('✅ Restored playback state:', playbackState);
            }
            
            // Attach playback button handlers with API update
            playButtons.forEach(btn => {
                btn.onclick = () => {
                    playButtons.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    console.log('📈 Playback state changed:', btn.dataset.direction);
                    // Update playback state in backend
                    this.updateTimelineSequenceInline(seq.target_parameter, { playback_state: btn.dataset.direction });
                };
            });
            
            console.log('✅ Successfully restored timeline controls for:', seq.target_parameter);
        });
        
        console.log('\n✅ Timeline restore complete');
    }
    
    /**
     * Update sequence buttons in UI
     */
    updateSequenceButtons() {
        // Find all parameter controls and add/update sequence buttons
        document.querySelectorAll('[data-parameter-id]').forEach(param => {
            const paramId = param.dataset.parameterId;
            const sequence = this.sequences.find(s => s.target_parameter === paramId && s.enabled);
            const hasSequence = !!sequence;
            
            let btn = param.querySelector('.sequence-btn');
            if (!btn) {
                btn = document.createElement('button');
                btn.className = 'sequence-btn';
                btn.innerHTML = '⚙️';
                btn.title = 'Parameter Sequence (Deprecated - Use context menu)';
                param.appendChild(btn);
                
                // DEPRECATED: Modal is disabled, button kept for backward compatibility but non-functional
                btn.addEventListener('click', () => {
                    console.warn('⚠️ ⚙️ button is DEPRECATED - use right-click context menu instead');
                });
            }
            
            if (hasSequence) {
                btn.classList.add('active');
                // ALWAYS hide all inline controls first to prevent stacking
                this.hideInlineAudioControls(paramId);
                this.hideInlineTimelineControls(paramId);
                this.hideInlineBPMControls(paramId);
                
                // Show inline controls based on sequence type
                if (sequence) {
                    if (sequence.type === 'audio') {
                        this.showInlineAudioControls(paramId, sequence);
                    } else if (sequence.type === 'timeline') {
                        this.showInlineTimelineControls(paramId, sequence);
                    } else if (sequence.type === 'bpm') {
                        this.showInlineBPMControls(paramId, sequence);
                    }
                }
            } else {
                btn.classList.remove('active');
                // Hide all inline controls
                this.hideInlineAudioControls(paramId);
                this.hideInlineTimelineControls(paramId);
                this.hideInlineBPMControls(paramId);
            }
        });
    }
    
    /**
     * Check audio analyzer status
     */
    async checkAudioStatus() {
        try {
            const response = await fetch('/api/audio/status');
            if (response.ok) {
                const data = await response.json();
                this.audioAnalyzerRunning = data.running;
                this.updateAudioStatus();
            }
        } catch (error) {
            console.error('Error checking audio status:', error);
        }
    }
    
    /**
     * Initialize audio gain circular slider
     */
    initAudioGainKnob() {
        const container = document.getElementById('audioGainKnob');
        if (!container) {
            console.warn('⚠️ Audio gain knob container not found');
            return;
        }
        
        // Prevent duplicate initialization
        if (this.audioGainKnob) {
            console.log('⚠️ Audio gain knob already initialized');
            return;
        }
        
        this.audioGainKnob = new CircularSlider(container, {
            min: 0.1,
            max: 5.0,
            value: 1.0,
            step: 0.1,
            arc: 270,
            startAngle: 135, // 135° = 7:30, +270° wraps to 45° = 4:30, deadzone at bottom
            size: 'tiny',
            label: '',
            decimals: 1,
            unit: '',
            variant: 'primary',
            showValue: true,
            onChange: (value) => {
                // Only update local gain value during dragging
                this.audioGain = parseFloat(value);
            },
            onDragEnd: (value) => {
                // Update and log only when drag ends (mouse release)
                this.setAudioGain(value);
            }
        });
        
        console.log('🎛️ Audio gain knob initialized');
    }
    
    /**
     * Initialize beat sensitivity circular slider
     */
    initBeatSensitivityKnob() {
        const container = document.getElementById('beatSensitivityKnob');
        if (!container) {
            console.warn('⚠️ Beat sensitivity knob container not found');
            return;
        }
        
        // Prevent duplicate initialization
        if (this.beatSensitivityKnob) {
            console.log('⚠️ Beat sensitivity knob already initialized');
            return;
        }
        
        this.beatSensitivityKnob = new CircularSlider(container, {
            min: 0.1,
            max: 3.0,
            value: 1.0,
            step: 0.1,
            arc: 270,
            startAngle: 135,
            size: 'tiny',
            label: '',
            decimals: 1,
            unit: '',
            variant: 'warning',  // Different color to distinguish from gain
            showValue: true,
            onChange: (value) => {
                this.beatSensitivity = parseFloat(value);
            },
            onDragEnd: (value) => {
                this.setBeatSensitivity(value);
            }
        });
        
        console.log('🥁 Beat sensitivity knob initialized');
    }
    
    /**
     * Set beat sensitivity
     */
    async setBeatSensitivity(sensitivity) {
        try {
            const response = await fetch('/api/audio/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ beat_sensitivity: parseFloat(sensitivity) })
            });
            
            if (!response.ok) throw new Error('Failed to set beat sensitivity');
            
            this.beatSensitivity = parseFloat(sensitivity);
            console.log(`🥁 Beat sensitivity: ${sensitivity}`);
        } catch (error) {
            console.error('Error setting beat sensitivity:', error);
            showToast('Failed to set beat sensitivity', 'error');
        }
    }
    
    /**
     * Initialize audio attack/release knob
     */
    initAudioAttackReleaseKnob() {
        const container = document.getElementById('audioAttackReleaseKnob');
        if (!container) return;
        
        if (this.audioAttackReleaseKnob) {
            return; // Already initialized
        }
        
        this.audioAttackReleaseKnob = new CircularSlider(container, {
            min: 0.2,
            max: 1.0,
            value: 0.7,
            step: 0.01,
            arc: 270,
            size: 'small',
            label: '',
            decimals: 2,
            unit: '',
            variant: 'success',
            showValue: true,
            onDragEnd: (value) => {
                // Update when drag ends
                if (this.currentSequence && this.currentSequence.type === 'audio') {
                    this.updateAudioSequenceAttackRelease(value);
                }
            }
        });
        
        console.log('🎛️ Audio attack/release knob initialized');
    }
    
    /**
     * Update audio sequence attack/release value
     */
    async updateAudioSequenceAttackRelease(value) {
        if (!this.currentSequence) return;
        
        try {
            const response = await fetch(`/api/sequences/${this.currentSequence.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    config: {
                        ...this.currentSequence.config,
                        attack_release: parseFloat(value)
                    }
                })
            });
            
            if (response.ok) {
                console.log(`🎛️ Attack/release updated: ${value}`);
                // Update local sequence object
                this.currentSequence.config.attack_release = parseFloat(value);
            }
        } catch (error) {
            console.error('Error updating attack/release:', error);
        }
    }
    
    /**
     * Select audio frequency band
     */
    selectAudioBand(band) {
        // Update button states
        document.querySelectorAll('.audio-band-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-band="${band}"]`).classList.add('active');
        
        console.log('📊 Audio band selected:', band);
    }
    
    /**
     * Select audio playback direction
     */
    selectAudioDirection(direction) {
        // Update button states
        document.querySelectorAll('.audio-direction-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-direction="${direction}"]`).classList.add('active');
        
        console.log('🎯 Audio direction selected:', direction);
    }
    
    /**
     * Set audio gain
     */
    async setAudioGain(gain) {
        this.audioGain = parseFloat(gain);
        
        // Update circular slider if it exists and value is different
        if (this.audioGainKnob && this.audioGainKnob.getValue() !== this.audioGain) {
            this.audioGainKnob.setValue(this.audioGain);
        }
        
        console.log('🔊 Audio gain set to:', this.audioGain);
        
        // Send to backend and trigger session save
        try {
            await fetch('/api/audio/gain', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gain: this.audioGain })
            });
            
            // Trigger session save
            this.saveAudioAnalyzerToSession();
        } catch (error) {
            console.error('Error setting audio gain:', error);
        }
    }
    
    /**
     * Save current audio analyzer state to session
     */
    async saveAudioAnalyzerToSession() {
        try {
            const state = this.getAudioAnalyzerState();
            // The backend will automatically save this during next session save
            // This just ensures the config is updated in the audio analyzer
            await fetch('/api/audio/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(state)
            });
        } catch (error) {
            // Silent fail - not critical
            console.debug('Could not save audio analyzer state:', error);
        }
    }
    
    /**
     * Start audio analyzer
     */
    async startAudioAnalyzer() {
        try {
            // Check if already running on backend
            const statusResponse = await fetch('/api/audio/status');
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                if (statusData.running) {
                    console.log('✅ Audio analyzer already running on backend');
                    this.audioAnalyzerRunning = true;
                    this.updateAudioStatus();
                    return;
                }
            }
            
            // Prepare start parameters
            const startParams = {};
            if (this.audioDevice !== null && this.audioDevice !== undefined) {
                startParams.device = this.audioDevice;
                console.log('🎤 Starting with device:', this.audioDevice, this.audioDeviceName);
            }
            
            const response = await fetch('/api/audio/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(startParams)
            });
            
            if (response.ok) {
                this.audioAnalyzerRunning = true;
                this.updateAudioStatus();
                this.showNotification('Audio analyzer started', 'success');
                console.log('✅ Audio analyzer started');
            } else {
                const error = await response.json();
                this.showNotification(`Error: ${error.error}`, 'error');
            }
        } catch (error) {
            console.error('Error starting audio:', error);
            this.showNotification('Failed to start audio analyzer', 'error');
        }
    }
    
    /**
     * Stop audio analyzer
     */
    async stopAudioAnalyzer() {
        try {
            const response = await fetch('/api/audio/stop', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (response.ok) {
                this.audioAnalyzerRunning = false;
                this.updateAudioStatus();
                this.showNotification('Audio analyzer stopped', 'success');
                console.log('✅ Audio analyzer stopped');
            }
        } catch (error) {
            console.error('Error stopping audio:', error);
        }
    }
    
    /**
     * Update audio status indicator
     */
    updateAudioStatus() {
        const dot = document.getElementById('audioStatusDot');
        const text = document.getElementById('audioStatusText');
        const globalDot = document.getElementById('globalAudioStatus');
        
        if (this.audioAnalyzerRunning) {
            if (dot) {
                dot.classList.add('running');
                text.textContent = 'Audio analyzer running';
            }
            if (globalDot) {
                globalDot.classList.add('running');
            }
        } else {
            if (dot) {
                dot.classList.remove('running');
                text.textContent = 'Audio analyzer stopped';
            }
            if (globalDot) {
                globalDot.classList.remove('running');
            }
        }
    }
    
    /**
     * Setup WebSocket for real-time audio features
     */
    setupWebSocket() {
        // Initialize Socket.IO connection if not already connected
        if (!window.socket) {
            window.socket = io();
            console.log('🔌 Connecting to Socket.IO server...');
        }
        
        // Listen for audio features
        window.socket.on('audio_features', (data) => {
            if (data.features) {
                this.audioFeatures = data.features;
                // Debug log first time
                if (!this._audioFeaturesDebugLogged) {
                    console.log('🎵 Audio features received via WebSocket:', this.audioFeatures);
                    this._audioFeaturesDebugLogged = true;
                }
            }
        });
        
        // Listen for parameter value updates (for triple slider feedback)
        // Track last values to only log when changed
        this._lastParameterValues = this._lastParameterValues || {};
        
        window.socket.on('parameter_update', (data) => {
            if (data.parameter && data.value !== undefined) {
                // Only log if value actually changed
                const lastValue = this._lastParameterValues[data.parameter];
                if (lastValue !== data.value) {
                    // console.log('📡 Parameter changed:', data.parameter, lastValue, '→', data.value);
                    this._lastParameterValues[data.parameter] = data.value;
                }
                
                this.updateParameterVisualFeedbackByUID(data.parameter, data.value);
            }
        });
        
        window.socket.on('connect', () => {
            console.log('✅ Socket.IO connected');
        });
        
        window.socket.on('disconnect', () => {
            console.log('❌ Socket.IO disconnected');
        });
        
        // Listen for sequence deletion events
        window.socket.on('sequence_deleted', async (data) => {
            console.log('🗑️ Sequence deleted event:', data);
            
            // Reload sequences from session state to reflect deletion
            await this.loadSequencesFromSessionState();
            
            // Clear current sequence references if it was the deleted one
            if (this.currentSequence && this.currentSequence.id === data.sequence_id) {
                this.currentSequence = null;
                this.currentParameter = null;
            }
            
            // Force refresh the UI to remove visual indicators
            this.updateSequenceButtons();
        });
    }
    
    /**
     * Update visual feedback for parameter by UID (red line in triple slider)
     */
    updateParameterVisualFeedbackByUID(paramUid, value) {
        // Find sequence button with this UID
        const button = document.querySelector(`[data-param-uid="${paramUid}"]`);
        if (!button) {
            // This is normal - parameter might not be visible (e.g., clip not selected)
            // Only log in verbose mode
            console.debug('Parameter not currently visible in DOM:', paramUid);
            return;
        }
        
        // Get triple slider from parent container (new grid layout)
        const paramControl = button.closest('.parameter-grid-row');
        if (!paramControl) {
            console.debug('No parameter-grid-row found for:', paramUid);
            return;
        }
        
        const tripleSliderContainer = paramControl.querySelector('.triple-slider-container');
        if (!tripleSliderContainer) {
            console.debug('No triple slider container found for:', paramUid);
            return;
        }
        
        const slider = getTripleSlider(tripleSliderContainer.id);
        
        if (slider && slider.updateCurrentValue) {
            slider.updateCurrentValue(value);
            console.debug('✅ Updated triple slider red line to:', value);
        }
    }
    
    /**
     * Update visual feedback for parameter (red line in triple slider) - Legacy path-based method
     */
    updateParameterVisualFeedback(parameterId, value) {
        const controlId = this.parameterPathToControlId(parameterId);
        const slider = getTripleSlider(controlId);
        
        console.log('🎯 Updating visual feedback:', { parameterId, controlId, value, found: !!slider });
        
        if (slider && slider.updateCurrentValue) {
            slider.updateCurrentValue(value);
            console.log('✅ Triple slider updated:', controlId, '=', value);
        } else {
            console.warn('⚠️ Triple slider not found:', controlId);
        }
    }
    
    /**
     * Draw audio spectrum
     */
    drawAudioSpectrum() {
        if (!this.spectrumCanvas) return;
        
        const ctx = this.spectrumCanvas.getContext('2d');
        const width = this.spectrumCanvas.width;
        const height = this.spectrumCanvas.height;
        
        // Clear
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        
        if (!this.audioFeatures) return;
        
        // Draw bars for bass, mid, treble
        const features = ['bass', 'mid', 'treble'];
        const colors = ['#ff4444', '#44ff44', '#4444ff'];
        const barWidth = width / features.length;
        
        features.forEach((feature, i) => {
            const value = this.audioFeatures[feature] || 0;
            const barHeight = value * height;
            
            ctx.fillStyle = colors[i];
            ctx.fillRect(i * barWidth + 2, height - barHeight, barWidth - 4, barHeight);
            
            // Label
            ctx.fillStyle = '#fff';
            ctx.font = '12px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(feature.toUpperCase(), i * barWidth + barWidth / 2, height - 5);
        });
    }
    
    /**
     * Draw LFO preview
     */
    drawLFOPreview() {
        if (!this.lfoCanvas) return;
        
        const ctx = this.lfoCanvas.getContext('2d');
        const width = this.lfoCanvas.width;
        const height = this.lfoCanvas.height;
        
        // Clear
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        
        // Get parameters
        const waveform = document.getElementById('lfoWaveform')?.value || 'sine';
        const frequency = parseFloat(document.getElementById('lfoFrequency')?.value || 1.0);
        
        // Draw waveform
        ctx.strokeStyle = '#0d6efd';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let x = 0; x < width; x++) {
            const t = (x / width) * 2 * frequency; // 2 cycles visible
            let y;
            
            switch (waveform) {
                case 'sine':
                    y = Math.sin(t * Math.PI * 2);
                    break;
                case 'square':
                    y = (t % 1) < 0.5 ? 1 : -1;
                    break;
                case 'triangle':
                    y = 1 - 4 * Math.abs((t % 1) - 0.5);
                    break;
                case 'sawtooth':
                    y = 2 * ((t % 1) - 0.5);
                    break;
                case 'random':
                    y = Math.sin(t * Math.PI * 2); // Placeholder
                    break;
                default:
                    y = 0;
            }
            
            const py = height / 2 - (y * height / 2.5);
            
            if (x === 0) {
                ctx.moveTo(x, py);
            } else {
                ctx.lineTo(x, py);
            }
        }
        
        ctx.stroke();
        
        // Center line
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, height / 2);
        ctx.lineTo(width, height / 2);
        ctx.stroke();
    }
    
    /**
     * Add timeline keyframe
     */
    addTimelineKeyframe() {
        const time = parseFloat(document.getElementById('keyframeTime').value);
        const value = parseFloat(document.getElementById('keyframeValue').value);
        
        if (isNaN(time) || isNaN(value)) {
            this.showNotification('Invalid keyframe values', 'error');
            return;
        }
        
        // Add keyframe
        this.timelineKeyframes = this.timelineKeyframes || [];
        this.timelineKeyframes.push([time, value]);
        
        // Sort by time
        this.timelineKeyframes.sort((a, b) => a[0] - b[0]);
        
        // Update UI
        this.renderKeyframesList();
        this.drawTimelinePreview();
        
        // Clear inputs
        document.getElementById('keyframeTime').value = '';
        document.getElementById('keyframeValue').value = '';
    }
    
    /**
     * Remove timeline keyframe
     */
    removeTimelineKeyframe(index) {
        this.timelineKeyframes.splice(index, 1);
        this.renderKeyframesList();
        this.drawTimelinePreview();
    }
    
    /**
     * Render keyframes list
     */
    renderKeyframesList() {
        const container = document.getElementById('timelineKeyframes');
        
        if (!this.timelineKeyframes || this.timelineKeyframes.length === 0) {
            container.innerHTML = '<p style="color: #666; text-align: center;">No keyframes yet</p>';
            return;
        }
        
        container.innerHTML = this.timelineKeyframes.map((kf, i) => `
            <div class="timeline-keyframe-item">
                <span class="timeline-keyframe-info">t=${kf[0].toFixed(2)}s → ${kf[1].toFixed(2)}</span>
                <span class="timeline-keyframe-remove" onclick="sequenceManager.removeTimelineKeyframe(${i})">✕</span>
            </div>
        `).join('');
    }
    
    /**
     * Draw timeline preview
     */
    drawTimelinePreview() {
        if (!this.timelineCanvas) return;
        
        const ctx = this.timelineCanvas.getContext('2d');
        const width = this.timelineCanvas.width;
        const height = this.timelineCanvas.height;
        
        // Clear
        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, width, height);
        
        if (!this.timelineKeyframes || this.timelineKeyframes.length < 2) return;
        
        const duration = parseFloat(document.getElementById('timelineDuration')?.value || 10.0);
        
        // Draw interpolated curve
        ctx.strokeStyle = '#0d6efd';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let x = 0; x < width; x++) {
            const t = (x / width) * duration;
            const value = this.interpolateTimeline(t);
            const y = height - (value / 100) * height; // Assuming 0-100 range
            
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // Draw keyframe points
        ctx.fillStyle = '#ff4444';
        this.timelineKeyframes.forEach(kf => {
            const x = (kf[0] / duration) * width;
            const y = height - (kf[1] / 100) * height;
            ctx.beginPath();
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();
        });
    }
    
    /**
     * Interpolate timeline value at time t
     */
    interpolateTimeline(t) {
        if (!this.timelineKeyframes || this.timelineKeyframes.length === 0) return 0;
        
        // Find surrounding keyframes
        let before = null;
        let after = null;
        
        for (let i = 0; i < this.timelineKeyframes.length; i++) {
            const kf = this.timelineKeyframes[i];
            if (kf[0] <= t) {
                before = kf;
            }
            if (kf[0] >= t && !after) {
                after = kf;
                break;
            }
        }
        
        if (!before) return this.timelineKeyframes[0][1];
        if (!after) return this.timelineKeyframes[this.timelineKeyframes.length - 1][1];
        if (before === after) return before[1];
        
        // Linear interpolation
        const progress = (t - before[0]) / (after[0] - before[0]);
        return before[1] + (after[1] - before[1]) * progress;
    }
    
    /**
     * Start preview loop
     */
    startPreviewLoop() {
        // Prevent duplicate animation loops
        if (this.animationFrame) {
            return;
        }
        
        const update = () => {
            // Update canvases if visible
            const modal = document.getElementById('sequenceModal');
            if (modal && modal.classList.contains('show')) {
                const activeType = document.querySelector('.sequence-type-btn.active')?.dataset.type;
                
                if (activeType === 'audio') {
                    this.drawAudioSpectrum();
                } else if (activeType === 'lfo') {
                    this.drawLFOPreview();
                }
            }
            
            // Always draw global spectrum if audio is running
            if (this.audioAnalyzerRunning) {
                this.drawGlobalAudioSpectrum();
            }
            
            this.animationFrame = requestAnimationFrame(update);
        };
        
        update();
    }
    
    /**
     * Draw global audio spectrum (mini version)
     */
    drawGlobalAudioSpectrum() {
        const canvas = document.getElementById('globalAudioSpectrum');
        if (!canvas || !this.audioFeatures) return;
        
        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        
        // Clear
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, width, height);
        
        // Draw spectrum bars (simplified)
        const features = ['bass', 'mid', 'treble'];
        const barWidth = width / features.length;
        
        // Check if beat is triggered
        const isBeat = this.audioFeatures['beat'] || false;
        
        // Normal colors vs beat colors (brighter/white when beat)
        const normalColors = ['#ff6b6b', '#64c8ff', '#a8e6cf'];
        const beatColors = ['#ffffff', '#ffffff', '#ffffff'];
        const colors = isBeat ? beatColors : normalColors;
        
        features.forEach((feature, i) => {
            // Get raw value
            const rawValue = this.audioFeatures[feature] || 0;
            
            // Track peak for adaptive scaling
            if (rawValue > this.audioFeaturePeaks[feature]) {
                this.audioFeaturePeaks[feature] = rawValue;
            } else {
                // Slow decay to adapt to changing levels
                this.audioFeaturePeaks[feature] *= this.peakDecayRate;
            }
            
            // Normalize by peak with minimum threshold
            const peak = Math.max(this.audioFeaturePeaks[feature], 0.00001);
            const normalized = rawValue / peak;
            
            // Apply gain and clamp
            const value = normalized * (this.audioGain || 1.0);
            const barHeight = Math.min(Math.max(value * height, 0), height);
            
            ctx.fillStyle = colors[i];
            ctx.fillRect(i * barWidth + 2, height - barHeight, barWidth - 4, barHeight);
        });
    }
    
    /**
     * Set audio gain
     */
    setAudioGain(gain) {
        this.audioGain = parseFloat(gain);
        const display = document.getElementById('audioGainValue');
        if (display) {
            display.textContent = gain + 'x';
        }
        console.log('🔊 Audio gain set to:', this.audioGain);
    }
    
    /**
     * Setup context menu
     */
    setupContextMenu() {
        const menu = document.getElementById('sequenceContextMenu');
        if (!menu) return;
        
        // Close menu when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.sequence-btn') && !e.target.closest('#sequenceContextMenu')) {
                menu.classList.remove('show');
            }
        });
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Simple console log for now - could implement toast notifications
        console.log(`[${type.toUpperCase()}] ${message}`);
        
        // If notification system exists in main app, use it
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else if (typeof showToast === 'function') {
            // Try showToast as well
            showToast(message, type);
        }
    }
    
    /**
     * Show inline audio controls for a parameter
     */
    showInlineAudioControls(parameterId, sequence) {
        console.log('🎛️ showInlineAudioControls called:', { parameterId, sequence });
        
        // Small delay to ensure DOM is fully rendered
        setTimeout(() => {
            // Find the control container by parameter path
            // Convert parameterId (e.g., "video.effects[0].parameters.scale_xy") to control ID
            const controlId = this.parameterPathToControlId(parameterId);
            console.log('🔍 Looking for control ID:', `${controlId}_audio_controls`);
            
            const controlsContainer = document.getElementById(`${controlId}_audio_controls`);
            
            if (!controlsContainer) {
                console.warn('⚠️ Audio controls container not found for:', parameterId);
                console.warn('   Expected element ID:', `${controlId}_audio_controls`);
                // List all elements with _audio_controls suffix to help debug
                const allControls = document.querySelectorAll('[id$="_audio_controls"]');
                console.log('   Available audio control elements:', Array.from(allControls).map(el => el.id));
                return;
            }
            
            console.log('✅ Found audio controls container');
            
            // Show the controls
            controlsContainer.style.display = 'block';
            
            // Initialize attack/release knob if not already initialized
            const knobContainer = document.getElementById(`${controlId}_attack_release`);
            console.log('🔍 Looking for knob container:', `${controlId}_attack_release`, 'found:', !!knobContainer);
            
            if (knobContainer) {
                // Destroy existing slider if present
                if (knobContainer._circularSlider) {
                    console.log('🧹 Cleaning up old slider instance');
                    // Clean up old instance
                    knobContainer.innerHTML = '';
                    delete knobContainer._circularSlider;
                }
                
                console.log('🎛️ Creating new CircularSlider with value:', sequence?.attack_release || 0.5);
                
                const slider = new CircularSlider(knobContainer, {
                    min: 0.2,
                    max: 1.0,
                    value: sequence?.attack_release || 0.7,
                    step: 0.01,
                    arc: 270,
                    startAngle: 135, // Start at 7:30, deadzone at bottom
                    size: 'tiny',
                    label: '',
                    decimals: 2,
                    unit: '',
                    variant: 'primary',
                    showValue: false,
                    onChange: (value) => {
                        // Update sequence when knob changes
                        this.updateSequenceInline(parameterId, { attack_release: value });
                    }
                });
                knobContainer._circularSlider = slider;
                console.log('✅ Initialized inline attack/release knob with value:', sequence?.attack_release || 0.5);
            } else {
                console.warn('⚠️ Attack/release knob container not found:', `${controlId}_attack_release`);
                console.log('   All elements with attack_release in ID:',
                    Array.from(document.querySelectorAll('[id*="attack_release"]')).map(el => el.id));
            }
            
            // Set active states from sequence
            if (sequence) {
                // Set active band
            const bandButtons = controlsContainer.querySelectorAll('.audio-band-btn-inline');
            bandButtons.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.band === sequence.band);
                btn.onclick = () => this.updateSequenceInline(parameterId, { band: btn.dataset.band });
            });
            
            // Set active direction
            const dirButtons = controlsContainer.querySelectorAll('.audio-dir-btn-inline');
            dirButtons.forEach(btn => {
                btn.classList.toggle('active', btn.dataset.direction === sequence.direction);
                btn.onclick = () => this.updateSequenceInline(parameterId, { mode: btn.dataset.direction });
            });
        }
        }, 50); // 50ms delay to ensure DOM is ready
    }
    
    /**
     * Hide inline audio controls for a parameter
     */
    hideInlineAudioControls(parameterId) {
        const controlId = this.parameterPathToControlId(parameterId);
        const controlsContainer = document.getElementById(`${controlId}_audio_controls`);
        
        if (controlsContainer) {
            controlsContainer.style.display = 'none';
        }
    }
    
    /**
     * Convert parameter path to control ID
     */
    parameterPathToControlId(paramPath) {
        // Convert parameter path to control ID matching the DOM element IDs
        // 
        // Formats:
        //   Player level: "video.effects[0].parameters.scale_xy" -> "video_effect_0_scale_xy"
        //   Clip level:   "clip.effects[1].parameters.scale_xy" -> "clip_effect_1_scale_xy"
        //   Layer level:  "video.layers[0].effects[0].parameters.scale" -> "video_layer_0_effect_0_scale"
        
        // Convert path to controlId format
        let converted = paramPath
            .replace(/\./g, '_')           // dots to underscores
            .replace(/\[/g, '_')            // [ to underscore  
            .replace(/\]/g, '')             // remove ]
            .replace(/effects_/, 'effect_') // effects -> effect (singular)
            .replace(/layers_/, 'layer_')   // layers -> layer (singular)
            .replace(/_parameters_/, '_');  // remove parameters segment
        
        console.log('🔄 Parameter path conversion:', paramPath, '->', converted);
        return converted;
    }
    
    /**
     * Update sequence parameters inline (without opening modal)
     */
    async updateSequenceInline(parameterId, updates) {
        const sequence = this.sequences.find(s => s.target_parameter === parameterId);
        if (!sequence) {
            console.warn('⚠️ No sequence found for:', parameterId);
            return;
        }
        
        try {
            const response = await fetch(`/api/sequences/${sequence.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ config: { ...sequence.config, ...updates } })
            });
            
            if (response.ok) {
                await window.sessionStateLoader.reload(); // Force reload to get updated state
                await this.loadSequencesFromSessionState();
                
                // Update UI to reflect changes
                const controlId = this.parameterPathToControlId(parameterId);
                const controlsContainer = document.getElementById(`${controlId}_audio_controls`);
                
                if (controlsContainer && updates.band) {
                    // Update active band button
                    controlsContainer.querySelectorAll('.audio-band-btn-inline').forEach(btn => {
                        btn.classList.toggle('active', btn.dataset.band === updates.band);
                    });
                }
                
                if (controlsContainer && updates.mode) {
                    // Update active direction button
                    controlsContainer.querySelectorAll('.audio-dir-btn-inline').forEach(btn => {
                        btn.classList.toggle('active', btn.dataset.direction === updates.mode);
                    });
                }
            }
        } catch (error) {
            console.error('Error updating sequence inline:', error);
        }
    }
}
