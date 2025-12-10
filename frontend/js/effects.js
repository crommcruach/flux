/**
 * Flux Effects Panel - Dynamic UI Generation for Plugin System
 * Automatically generates controls based on plugin parameter types
 */

import { debug, loadDebugConfig } from './logger.js';

const API_BASE = '';
let availablePlugins = [];
let activeEffects = [];
let updateInterval = null;

// Current effect chain context
let currentPlayerId = 'video';
let currentChainType = 'video';

// Parameter Type to UI Control Mapping
const PARAMETER_TYPES = {
    FLOAT: 'range',
    INT: 'range',
    BOOL: 'checkbox',
    SELECT: 'select',
    COLOR: 'color',
    STRING: 'text',
    RANGE: 'dual-range'
};

/**
 * Initialize the effects panel
 */
async function init() {
    await loadDebugConfig();
    debug.log('🎨 Initializing Effects Panel...');
    await loadAvailableEffects();
    await refreshEffectChain();
    
    // Start auto-refresh for active effects (every 2 seconds)
    updateInterval = setInterval(refreshEffectChain, 2000);
}

/**
 * Load all available effect plugins
 */
async function loadAvailableEffects() {
    try {
        const response = await fetch(`${API_BASE}/api/plugins/list`);
        const data = await response.json();
        
        if (data.success) {
            // Filter only EFFECT type plugins (case-insensitive)
            availablePlugins = data.plugins.filter(p => p.type && p.type.toLowerCase() === 'effect');
            renderAvailableEffects();
        } else {
            console.error('❌ Failed to load plugins:', data.message);
            showError('availableEffects', 'Failed to load effects');
        }
    } catch (error) {
        console.error('❌ Error loading plugins:', error);
        showError('availableEffects', 'Network error loading effects');
    }
}

/**
 * Render available effects list
 */
function renderAvailableEffects() {
    const container = document.getElementById('availableEffects');
    
    if (availablePlugins.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No effect plugins found</p>
                <small>Add effect plugins to src/plugins/effects/</small>
            </div>
        `;
        return;
    }
    
    container.innerHTML = availablePlugins.map(plugin => `
        <div class="effect-card" 
             draggable="true"
             data-plugin-id="${plugin.id}"
             onclick="addEffect('${plugin.id}')">
            <div class="effect-card-title">${plugin.name}</div>
            <div class="effect-card-description">${plugin.description || 'No description'}</div>
            <small class="text-muted">v${plugin.version} • ${plugin.author}</small>
        </div>
    `).join('');
    
    // Add drag handlers to effect cards
    container.querySelectorAll('.effect-card').forEach(card => {
        card.addEventListener('dragstart', (e) => {
            const pluginId = e.target.closest('.effect-card').dataset.pluginId;
            e.dataTransfer.setData('text/plain', pluginId);
            e.dataTransfer.setData('application/x-effect-plugin', pluginId);
            e.dataTransfer.effectAllowed = 'copy';
        });
    });
}

/**
 * Add effect to the chain
 */
async function addEffect(pluginId) {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/effects/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            debug.log('✅ Effect added:', pluginId);
            await refreshEffectChain();
        } else {
            alert(`Failed to add effect: ${data.message}`);
        }
    } catch (error) {
        console.error('❌ Error adding effect:', error);
        alert('Network error adding effect');
    }
}

/**
 * Refresh the effect chain display
 */
async function refreshEffectChain() {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/effects`);
        const data = await response.json();
        
        if (data.success) {
            activeEffects = data.effects;
            renderEffectChain();
            
            // Enable/disable clear all button
            document.getElementById('clearAllBtn').disabled = activeEffects.length === 0;
        }
    } catch (error) {
        console.error('❌ Error refreshing effect chain:', error);
    }
}

/**
 * Render the active effect chain
 */
function renderEffectChain() {
    const container = document.getElementById('effectChain');
    
    if (activeEffects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🎨</div>
                <h4>No Effects Active</h4>
                <p>Add effects from the panel on the right to start processing</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = activeEffects.map((effect, index) => {
        const plugin = availablePlugins.find(p => p.id === effect.plugin_id);
        return renderEffectItem(effect, index, plugin);
    }).join('');
}

/**
 * Render a single effect item with parameters
 */
function renderEffectItem(effect, index, plugin) {
    // Use metadata from effect (includes parameters schema), fallback to plugin
    const metadata = effect.metadata || plugin?.metadata || {};
    const parameters = metadata.parameters || [];
    
    return `
        <div class="effect-item" data-index="${index}">
            <div class="effect-header">
                <div class="effect-title">
                    <span>#${index + 1}</span>
                    <span>${metadata.name || effect.plugin_id}</span>
                    <span class="effect-badge">${metadata.type || 'EFFECT'}</span>
                </div>
                <button class="btn btn-sm btn-danger" onclick="removeEffect(${index})">
                    🗑️ Remove
                </button>
            </div>
            
            ${parameters.length > 0 ? `
                <div class="parameters">
                    ${parameters.map(param => renderParameterControl(param, effect.parameters[param.name], index)).join('')}
                </div>
            ` : '<p class="text-muted">No configurable parameters</p>'}
        </div>
    `;
}

/**
 * Render a parameter control based on its type
 */
function renderParameterControl(param, currentValue, effectIndex) {
    const value = currentValue !== undefined ? currentValue : param.default;
    const controlId = `effect_${effectIndex}_${param.name}`;
    
    let control = '';
    
    // Normalize type to uppercase for comparison
    const paramType = (param.type || '').toUpperCase();
    
    switch (paramType) {
        case 'FLOAT':
        case 'INT':
            const step = paramType === 'INT' ? 1 : 0.1;
            const min = param.min || 0;
            const max = param.max || 100;
            // Restore saved range if available, otherwise use full range
            const savedRangeMin = currentValue !== undefined && typeof currentValue === 'object' && currentValue._rangeMin !== undefined ? currentValue._rangeMin : min;
            const savedRangeMax = currentValue !== undefined && typeof currentValue === 'object' && currentValue._rangeMax !== undefined ? currentValue._rangeMax : max;
            const actualValue = (currentValue !== undefined && typeof currentValue === 'object' && currentValue._value !== undefined) ? currentValue._value : value;
            
            // Use savedRangeMax as slider max if it's a reasonable value (for dynamic ranges like Transport)
            const sliderMax = savedRangeMax > 0 && savedRangeMax <= max ? savedRangeMax : max;
            
            control = `
                <div class="parameter-control">
                    <div class="parameter-label">
                        <label>${param.name}</label>
                        <span class="parameter-value" id="${controlId}_value">${actualValue}</span>
                    </div>
                    <div id="${controlId}" class="triple-slider-container"></div>
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            // Initialize triple-slider after DOM is updated
            setTimeout(() => {
                initTripleSlider(controlId, {
                    min: min,
                    max: sliderMax,
                    value: actualValue,
                    step: step,
                    showRange: true,
                    rangeMin: savedRangeMin,
                    rangeMax: savedRangeMax,
                    onChange: (newValue) => {
                        updateParameter(effectIndex, param.name, newValue, `${controlId}_value`);
                    },
                    onRangeChange: (rangeMin, rangeMax) => {
                        // Range changed - trigger update to save range
                        const slider = getTripleSlider(controlId);
                        if (slider) {
                            updateParameter(effectIndex, param.name, slider.getValue(), `${controlId}_value`);
                        }
                    }
                });
            }, 0);
            break;
            
        case 'BOOL':
            control = `
                <div class="parameter-control">
                    <div class="form-check form-switch">
                        <input 
                            class="form-check-input" 
                            type="checkbox" 
                            id="${controlId}"
                            ${value ? 'checked' : ''}
                            onchange="updateParameter(${effectIndex}, '${param.name}', this.checked)"
                        >
                        <label class="form-check-label" for="${controlId}">
                            ${param.name}
                        </label>
                    </div>
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            break;
            
        case 'SELECT':
            control = `
                <div class="parameter-control">
                    <label for="${controlId}" class="parameter-label">${param.name}</label>
                    <select 
                        class="form-select" 
                        id="${controlId}"
                        onchange="updateParameter(${effectIndex}, '${param.name}', this.value)"
                    >
                        ${(param.options || []).map(opt => 
                            `<option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>`
                        ).join('')}
                    </select>
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            break;
            
        case 'COLOR':
            control = `
                <div class="parameter-control">
                    <label for="${controlId}" class="parameter-label">${param.name}</label>
                    <div class="input-group">
                        <input 
                            type="color" 
                            class="form-control form-control-color" 
                            id="${controlId}"
                            value="${value || '#000000'}"
                            onchange="updateParameter(${effectIndex}, '${param.name}', this.value)"
                        >
                        <input 
                            type="text" 
                            class="form-control" 
                            value="${value || '#000000'}"
                            readonly
                        >
                    </div>
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            break;
            
        case 'STRING':
            control = `
                <div class="parameter-control">
                    <label for="${controlId}" class="parameter-label">${param.name}</label>
                    <input 
                        type="text" 
                        class="form-control" 
                        id="${controlId}"
                        value="${value || ''}"
                        onchange="updateParameter(${effectIndex}, '${param.name}', this.value)"
                    >
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            break;
            
        case 'RANGE':
            control = `
                <div class="parameter-control">
                    <label class="parameter-label">${param.name}</label>
                    <div class="row g-2">
                        <div class="col">
                            <label class="form-label small">Min</label>
                            <input 
                                type="number" 
                                class="form-control" 
                                value="${value?.[0] || param.min || 0}"
                                onchange="updateRangeParameter(${effectIndex}, '${param.name}', 0, parseFloat(this.value))"
                            >
                        </div>
                        <div class="col">
                            <label class="form-label small">Max</label>
                            <input 
                                type="number" 
                                class="form-control" 
                                value="${value?.[1] || param.max || 100}"
                                onchange="updateRangeParameter(${effectIndex}, '${param.name}', 1, parseFloat(this.value))"
                            >
                        </div>
                    </div>
                    ${param.description ? `<div class="parameter-description">${param.description}</div>` : ''}
                </div>
            `;
            break;
            
        default:
            control = `<p class="text-warning">Unknown parameter type: ${param.type}</p>`;
    }
    
    return control;
}

/**
 * Update a parameter value
 */
async function updateParameter(effectIndex, paramName, value, valueDisplayId = null) {
    try {
        // Update display value if provided (for sliders)
        if (valueDisplayId) {
            document.getElementById(valueDisplayId).textContent = value;
        }
        
        // Check if this is a triple-slider and include range data
        const controlId = valueDisplayId ? valueDisplayId.replace('_value', '') : null;
        const slider = controlId ? getTripleSlider(controlId) : null;
        const payload = { name: paramName, value: value };
        
        if (slider) {
            const range = slider.getRange();
            payload.rangeMin = range.min;
            payload.rangeMax = range.max;
        }
        
        const response = await fetch(`${API_BASE}/api/player/video/effects/${effectIndex}/parameter`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        if (!data.success) {
            console.error('❌ Failed to update parameter:', data.message);
            alert(`Failed to update parameter: ${data.message}`);
        } else {
            debug.log(`✅ Updated ${paramName} = ${value}`);
        }
    } catch (error) {
        console.error('❌ Error updating parameter:', error);
    }
}

/**
 * Update a range parameter (special case with two values)
 */
async function updateRangeParameter(effectIndex, paramName, valueIndex, newValue) {
    // Get current range value
    const effect = activeEffects[effectIndex];
    const currentValue = effect.parameters[paramName] || [0, 100];
    
    // Update the specific index
    const newRange = [...currentValue];
    newRange[valueIndex] = newValue;
    
    await updateParameter(effectIndex, paramName, newRange);
}

/**
 * Remove an effect from the chain
 */
async function removeEffect(index) {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/effects/${index}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            debug.log('✅ Effect removed:', index);
            await refreshEffectChain();
        } else {
            alert(`Failed to remove effect: ${data.message}`);
        }
    } catch (error) {
        console.error('❌ Error removing effect:', error);
        alert('Network error removing effect');
    }
}

/**
 * Clear all effects from the chain
 */
async function clearAllEffects() {
    if (!confirm('Remove all effects from the chain?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/player/video/effects/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            debug.log('✅ All effects cleared');
            await refreshEffectChain();
        } else {
            alert(`Failed to clear effects: ${data.message}`);
        }
    } catch (error) {
        console.error('❌ Error clearing effects:', error);
        alert('Network error clearing effects');
    }
}

/**
 * Show error message
 */
function showError(containerId, message) {
    document.getElementById(containerId).innerHTML = `
        <div class="alert alert-danger" role="alert">
            ❌ ${message}
        </div>
    `;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', init);

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
});
