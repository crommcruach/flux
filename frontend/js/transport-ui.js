/**
 * Custom Transport Effect UI Layout
 * Uses existing parameter controls but with custom layout
 */

/**
 * Render transport controls with custom layout
 * Uses the existing renderParameterControl function to maintain all functionality
 */
function renderTransportControls(effect, index, player, clipId = null) {
    const metadata = effect.metadata || {};
    const parameters = metadata.parameters || [];
    const params = effect.parameters || {};
    const pluginId = 'transport';
    
    // Find parameter definitions
    const transportPosParam = parameters.find(p => p.name === 'transport_position');
    const speedParam = parameters.find(p => p.name === 'speed');
    const reverseParam = parameters.find(p => p.name === 'reverse');
    const playbackModeParam = parameters.find(p => p.name === 'playback_mode');
    const loopCountParam = parameters.find(p => p.name === 'loop_count');
    const pausedParam = parameters.find(p => p.name === 'paused');
    
    // Get current values
    const transportPosValue = params.transport_position;
    const speedValue = params.speed !== undefined ? params.speed : 1.0;
    const reverseValue = params.reverse;
    const playbackModeValue = params.playback_mode;
    const loopCountValue = params.loop_count;
    const pausedValue = params.paused;
    
    // Format time helper (mm:ss.ms)
    const formatTime = (frame, fps) => {
        const totalSeconds = frame / fps;
        const minutes = Math.floor(totalSeconds / 60);
        const seconds = Math.floor(totalSeconds % 60);
        const milliseconds = Math.floor((totalSeconds % 1) * 1000);
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
    };
    
    // Calculate current position and duration
    const fps = transportPosValue?._fps || 30;
    const currentPosition = transportPosValue?._value || 0;
    const inPoint = transportPosValue?._rangeMin || 0;
    const outPoint = transportPosValue?._rangeMax || 100;
    const durationFrames = (outPoint - inPoint) + 1;  // +1 because range is inclusive [inPoint, outPoint]
    const currentTime = formatTime(currentPosition, fps);
    
    // Calculate effective playback duration (adjusted for speed)
    // At 2x speed, a 5-second clip plays in 2.5 seconds
    const effectiveDurationFrames = durationFrames / speedValue;
    const durationTime = formatTime(effectiveDurationFrames, fps);
    
    // Generate unique IDs for dynamic displays
    const positionValueId = `${clipId ? 'clip_' + clipId : player}_transport_transport_position_value`;
    const durationValueId = `${clipId ? 'clip_' + clipId : player}_transport_duration_value`;
    
    return `
        <div class="transport-custom-layout">
            <!-- Timeline Slider (Triple Slider for trimming) -->
            <div class="transport-timeline">
                <span class="transport-position-display parameter-value" id="${positionValueId}">${currentTime}</span>
                ${transportPosParam ? renderParameterControl(transportPosParam, transportPosValue, index, player, pluginId, clipId, true) : ''}
            </div>
            
            <!-- Playback Direction + Mode + Loop Count in ONE row -->
            <div class="parameter-grid-row transport-playback-combined">
                <div class="param-cogwheel"></div>
                <div class="param-name"></div>
                <div class="param-slider" style="display: flex; gap: 8px; align-items: center;">
                    <button class="transport-direction-btn ${reverseValue ? 'active' : ''}" 
                        onclick="toggleTransportDirection('${player}', ${index}, true, this)" 
                        title="Play backward">◀</button>
                    <button class="transport-pause-btn ${pausedValue ? 'active' : ''}" 
                        onclick="toggleTransportPause('${player}', ${index}, this)" 
                        data-paused="${pausedValue}" 
                        title="Pause">⏸</button>
                    <button class="transport-direction-btn ${!reverseValue ? 'active' : ''}" 
                        onclick="toggleTransportDirection('${player}', ${index}, false, this)" 
                        title="Play forward">▶</button>
                    ${playbackModeParam ? `<select class="form-select" onchange="updateParameter('${player}', ${index}, 'playback_mode', this.value)">
                        ${playbackModeParam.options.map(opt => `<option value="${opt.value}" ${playbackModeValue === opt.value ? 'selected' : ''} ${opt.tooltip ? `title="${opt.tooltip}"` : ''}>${opt.label || opt.value}</option>`).join('')}
                    </select>` : ''}
                    ${loopCountParam ? `<span class="transport-loop-label">Loop Count:</span>
                    <input type="number" class="transport-loop-input" value="${loopCountValue}" 
                        min="${loopCountParam.min || 0}" 
                        max="${loopCountParam.max || 999}" 
                        onchange="updateParameter('${player}', ${index}, 'loop_count', parseInt(this.value))"
                        title="Number of loops (0 = infinite)">` : ''}
                </div>
            </div>
            
            <!-- Speed Control -->
            <div class="parameter-grid-row transport-speed-row">
                <div class="param-cogwheel"></div>
                <div class="param-name"></div>
                <div class="param-slider transport-speed-control">
                    <span class="transport-speed-label">Speed:</span>
                    <input type="number" class="transport-speed-input" 
                        value="${speedValue !== undefined ? speedValue : 1.0}" 
                        min="${speedParam?.min || 0.1}" 
                        max="${speedParam?.max || 5.0}" 
                        step="0.1"
                        oninput="updateTransportSpeed('${player}', ${index}, this, 'input')"
                        oncontextmenu="resetTransportSpeed('${player}', ${index}, this); return false;"
                        title="Playback speed multiplier (right-click to reset to 1.0x)">
                    <button class="transport-speed-btn" 
                        onclick="adjustTransportSpeed('${player}', ${index}, 0.1, this)" 
                        title="Increase speed by 0.1">+</button>
                    <button class="transport-speed-btn" 
                        onclick="adjustTransportSpeed('${player}', ${index}, -0.1, this)" 
                        title="Decrease speed by 0.1">-</button>
                    <input type="range" class="slider transport-speed-slider" 
                        min="${speedParam?.min || 0.1}" 
                        max="${speedParam?.max || 5.0}" 
                        step="0.1" 
                        value="${speedValue !== undefined ? speedValue : 1.0}"
                        oninput="updateTransportSpeed('${player}', ${index}, this, 'slider')"
                        oncontextmenu="resetTransportSpeed('${player}', ${index}, this); return false;"
                        title="Playback speed slider (right-click to reset to 1.0x)">
                </div>
            </div>
            
            <!-- Duration Display -->
            <div class="transport-duration">
                <label>Duration:</label>
                <span class="transport-duration-value" id="${durationValueId}" data-fps="${fps}" data-frames="${durationFrames}">${durationTime}</span>
            </div>
        </div>
    `;
}

/**
 * Toggle transport direction buttons (backward/forward)
 * Updates UI immediately and syncs with backend
 */
function toggleTransportDirection(player, effectIndex, reverseValue, clickedButton) {
    // Find all direction buttons in the same row
    const row = clickedButton.closest('.transport-playback-combined');
    const directionButtons = row.querySelectorAll('.transport-direction-btn');
    
    // Remove active class from all direction buttons
    directionButtons.forEach(btn => btn.classList.remove('active'));
    
    // Add active class to clicked button
    clickedButton.classList.add('active');
    
    // Update backend
    updateParameter(player, effectIndex, 'reverse', reverseValue);
}

/**
 * Toggle transport pause button
 * Updates UI immediately and syncs with backend
 */
function toggleTransportPause(player, effectIndex, clickedButton) {
    // Get current state from button's data attribute
    const currentPausedState = clickedButton.getAttribute('data-paused') === 'true';
    const newPausedState = !currentPausedState;
    
    // Update button state
    clickedButton.setAttribute('data-paused', newPausedState);
    
    // Toggle active class (orange highlight when paused)
    if (newPausedState) {
        clickedButton.classList.add('active');
    } else {
        clickedButton.classList.remove('active');
    }
    
    // Update backend
    updateParameter(player, effectIndex, 'paused', newPausedState);
}

/**
 * Update transport speed from input or slider
 * Keeps input and slider in sync and recalculates duration
 */
function updateTransportSpeed(player, effectIndex, changedElement, sourceType) {
    // Find the speed input and slider in the same row
    const row = changedElement.closest('.transport-speed-control');
    const speedInput = row.querySelector('.transport-speed-input');
    const speedSlider = row.querySelector('.transport-speed-slider');
    
    // Get new value from the changed element
    let newValue = parseFloat(changedElement.value);
    
    // Clamp to min/max
    const min = parseFloat(speedInput.min);
    const max = parseFloat(speedInput.max);
    newValue = Math.max(min, Math.min(max, newValue));
    
    // Round to 1 decimal place (0.1 increments) for both input and slider
    newValue = Math.round(newValue * 10) / 10;
    
    // Update both controls to stay in sync
    speedInput.value = newValue;
    speedSlider.value = newValue;
    
    // Update duration display dynamically
    updateTransportDuration(changedElement, newValue);
    
    // Update backend
    updateParameter(player, effectIndex, 'speed', newValue);
}

/**
 * Adjust transport speed by increment (+/- buttons)
 * Updates UI immediately and syncs with backend
 */
function adjustTransportSpeed(player, effectIndex, increment, clickedButton) {
    // Find the speed input and slider in the same row
    const row = clickedButton.closest('.transport-speed-control');
    const speedInput = row.querySelector('.transport-speed-input');
    const speedSlider = row.querySelector('.transport-speed-slider');
    
    // Get current value
    const currentValue = parseFloat(speedInput.value);
    const min = parseFloat(speedInput.min);
    const max = parseFloat(speedInput.max);
    
    // Calculate new value (clamped to min/max)
    let newValue = currentValue + increment;
    newValue = Math.max(min, Math.min(max, newValue));
    newValue = Math.round(newValue * 10) / 10; // Round to 1 decimal place
    
    // Update UI
    speedInput.value = newValue;
    speedSlider.value = newValue;
    
    // Update duration display dynamically
    updateTransportDuration(clickedButton, newValue);
    
    // Update backend
    updateParameter(player, effectIndex, 'speed', newValue);
}

/**
 * Update duration display based on new speed
 * Helper function to recalculate and update duration in real-time
 */
function updateTransportDuration(speedElement, newSpeed) {
    // Find duration display element (navigate up from speed control)
    const transportLayout = speedElement.closest('.transport-custom-layout');
    if (!transportLayout) return;
    
    const durationValueElement = transportLayout.querySelector('.transport-duration-value');
    if (!durationValueElement) return;
    
    // Get stored frame count and fps from data attributes
    const durationFrames = parseFloat(durationValueElement.getAttribute('data-frames'));
    const fps = parseFloat(durationValueElement.getAttribute('data-fps'));
    
    if (!durationFrames || !fps) return;
    
    // Calculate effective duration (adjusted for speed)
    const effectiveDurationFrames = durationFrames / newSpeed;
    
    // Format time (mm:ss.ms)
    const totalSeconds = effectiveDurationFrames / fps;
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = Math.floor(totalSeconds % 60);
    const milliseconds = Math.floor((totalSeconds % 1) * 1000);
    const formattedTime = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
    
    // Update display
    durationValueElement.textContent = formattedTime;
}

/**
 * Reset transport speed to default (1.0x) on right-click
 * Updates UI immediately and syncs with backend
 */
function resetTransportSpeed(player, effectIndex, clickedElement) {
    // Find the speed input and slider in the same row
    const row = clickedElement.closest('.transport-speed-control');
    const speedInput = row.querySelector('.transport-speed-input');
    const speedSlider = row.querySelector('.transport-speed-slider');
    
    // Reset to default speed (1.0x)
    const defaultSpeed = 1.0;
    
    // Update UI
    speedInput.value = defaultSpeed;
    speedSlider.value = defaultSpeed;
    
    // Update duration display
    updateTransportDuration(clickedElement, defaultSpeed);
    
    // Update backend
    updateParameter(player, effectIndex, 'speed', defaultSpeed);
}

/**
 * No custom event handlers needed - using existing parameter control handlers
 */
function attachTransportEventHandlers() {
    // Event handlers are already attached by renderParameterControl
    // This function exists for compatibility but does nothing
}

// Export to global scope
window.renderTransportControls = renderTransportControls;
window.attachTransportEventHandlers = attachTransportEventHandlers;
window.toggleTransportDirection = toggleTransportDirection;
window.toggleTransportPause = toggleTransportPause;
window.updateTransportSpeed = updateTransportSpeed;
window.updateTransportDuration = updateTransportDuration;
window.adjustTransportSpeed = adjustTransportSpeed;
window.resetTransportSpeed = resetTransportSpeed;

