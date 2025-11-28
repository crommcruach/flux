/**
 * Config.js - Configuration management page
 */

import { showToast, initErrorLogging } from './common.js';



// ========================================
// DEBUG LOGGING SYSTEM
// ========================================

let DEBUG_LOGGING = true; // Default: enabled

// Debug logger wrapper functions
const debug = {
    log: (...args) => { if (DEBUG_LOGGING) console.log(...args); },
    info: (...args) => { if (DEBUG_LOGGING) console.info(...args); },
    warn: (...args) => { if (DEBUG_LOGGING) console.warn(...args); },
    error: (...args) => console.error(...args), // Errors always shown
    group: (...args) => { if (DEBUG_LOGGING) console.group(...args); },
    groupEnd: () => { if (DEBUG_LOGGING) console.groupEnd(); },
    table: (...args) => { if (DEBUG_LOGGING) console.table(...args); }
};

// Load debug setting from config
async function loadDebugConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        DEBUG_LOGGING = config.frontend?.debug_logging ?? true;
        console.log(`🐛 Debug logging: ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    } catch (error) {
        console.error('❌ Failed to load debug config, using default (enabled):', error);
        DEBUG_LOGGING = true;
    }
}

// Runtime toggle function (accessible from browser console)
window.toggleDebug = function(enable) {
    DEBUG_LOGGING = enable ?? !DEBUG_LOGGING;
    console.log(`🐛 Debug logging ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return DEBUG_LOGGING;
};

// ========================================
// STATE
// ========================================
let configData = {};

// ========================================
// HELPER FUNCTIONS
// ========================================

function getInputType(value) {
    if (typeof value === 'boolean') return 'checkbox';
    if (typeof value === 'number') return 'number';
    if (Array.isArray(value)) return 'array';
    if (typeof value === 'object' && value !== null) return 'object';
    return 'text';
}

function createInput(key, value, path) {
    const inputType = getInputType(value);
    const fullPath = path ? `${path}.${key}` : key;
    
    if (inputType === 'checkbox') {
        return `
            <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" 
                       id="${fullPath}" data-path="${fullPath}" 
                       ${value ? 'checked' : ''}>
                <label class="form-check-label" for="${fullPath}">${key}</label>
            </div>
        `;
    } else if (inputType === 'array') {
        const items = value.map((item, idx) => `
            <div class="array-item">
                <input type="text" class="form-control" 
                       data-path="${fullPath}" data-index="${idx}" 
                       value="${item}">
                <button class="btn btn-sm btn-outline-danger remove-array-item" 
                        data-path="${fullPath}" data-index="${idx}">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `).join('');
        
        return `
            <div class="config-label">${key}</div>
            <div class="array-container" data-path="${fullPath}">
                ${items}
                <button class="btn btn-sm btn-outline-primary add-array-item" 
                        data-path="${fullPath}">
                    <i class="bi bi-plus"></i> Hinzufügen
                </button>
            </div>
        `;
    } else if (inputType === 'object') {
        return null; // Objects are handled separately
    } else {
        return `
            <div class="config-label">${key}</div>
            <input type="${inputType}" class="form-control" 
                   id="${fullPath}" data-path="${fullPath}" 
                   value="${value === null ? '' : value}"
                   ${value === null ? 'placeholder="null"' : ''}>
        `;
    }
}

function renderConfigSection(sectionKey, sectionData, parentPath = '') {
    const path = parentPath ? `${parentPath}.${sectionKey}` : sectionKey;
    const sectionId = path.replace(/\./g, '-');
    
    let itemsHTML = '';
    
    for (const [key, value] of Object.entries(sectionData)) {
        if (key.startsWith('_')) continue; // Skip comments
        
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            // Nested object - create subsection
            itemsHTML += `
                <div class="nested-object mt-3">
                    ${renderConfigSection(key, value, path)}
                </div>
            `;
        } else {
            const inputHTML = createInput(key, value, path);
            if (inputHTML) {
                itemsHTML += `<div class="config-item">${inputHTML}</div>`;
            }
        }
    }
    
    // Alle Abschnitte collapsable machen
    return `
        <div class="config-section" id="section-${sectionId}">
            <div class="config-section-header toggle-collapse" data-bs-toggle="collapse" data-bs-target="#collapse-${sectionId}" style="cursor:pointer;">
                <h3 class="config-section-title"><i class="bi bi-chevron-down collapse-icon"></i> ${sectionKey}</h3>
            </div>
            <div class="collapse" id="collapse-${sectionId}">
                ${itemsHTML}
            </div>
        </div>
    `;
}

function renderConfig() {
    const container = document.getElementById('configContainer');
    let html = '';
    
    for (const [sectionKey, sectionData] of Object.entries(configData)) {
        html += renderConfigSection(sectionKey, sectionData);
    }
    
    container.innerHTML = html;
    attachEventHandlers();
}

function attachEventHandlers() {
    // Array item removal
    document.querySelectorAll('.remove-array-item').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.closest('.array-item').remove();
        });
    });
    
    // Array item addition
    document.querySelectorAll('.add-array-item').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const path = e.target.closest('.add-array-item').dataset.path;
            const container = e.target.closest('.array-container');
            const items = container.querySelectorAll('.array-item');
            const newIndex = items.length;
            
            const newItemHTML = `
                <div class="array-item">
                    <input type="text" class="form-control" 
                           data-path="${path}" data-index="${newIndex}" 
                           value="">
                    <button class="btn btn-sm btn-outline-danger remove-array-item" 
                            data-path="${path}" data-index="${newIndex}">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            `;
            
            e.target.closest('.add-array-item').insertAdjacentHTML('beforebegin', newItemHTML);
            attachEventHandlers();
        });
    });

    // Collapse toggles
    document.querySelectorAll('.toggle-collapse').forEach(toggle => {
        toggle.addEventListener('click', (e) => {
            const icon = toggle.querySelector('.collapse-icon');
            if (icon) {
                icon.classList.toggle('collapsed');
            }
        });
    });
}

function collectConfigData() {
    const newConfig = JSON.parse(JSON.stringify(configData)); // Deep clone
    
    // Collect all inputs
    document.querySelectorAll('input[data-path]').forEach(input => {
        const path = input.dataset.path;
        const keys = path.split('.');
        
        let target = newConfig;
        for (let i = 0; i < keys.length - 1; i++) {
            target = target[keys[i]];
        }
        
        const lastKey = keys[keys.length - 1];
        
        if (input.type === 'checkbox') {
            target[lastKey] = input.checked;
        } else if (input.type === 'number') {
            const value = input.value.trim();
            target[lastKey] = value === '' ? null : parseFloat(value);
        } else if (input.dataset.index !== undefined) {
            // Array item
            if (!Array.isArray(target[lastKey])) {
                target[lastKey] = [];
            }
            const idx = parseInt(input.dataset.index);
            const value = input.value.trim();
            
            // Try to parse as number if it looks like a number
            if (value !== '' && !isNaN(value)) {
                target[lastKey][idx] = parseFloat(value);
            } else {
                target[lastKey][idx] = value;
            }
        } else {
            const value = input.value.trim();
            target[lastKey] = value === '' ? null : value;
        }
    });
    
    return newConfig;
}

// ========================================
// API FUNCTIONS
// ========================================

async function loadConfig() {
    try {
        const response = await fetch('/api/config');
        if (!response.ok) throw new Error('Failed to load config');
        
        configData = await response.json();
        renderConfig();
        showToast('Konfiguration geladen', 'success');
    } catch (error) {
        console.error('Error loading config:', error);
        showToast('Fehler beim Laden der Konfiguration', 'error');
    }
}

async function saveConfig() {
    const newConfig = collectConfigData();
    
    try {
        // Save config
        const saveResponse = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(newConfig)
        });
        
        if (!saveResponse.ok) {
            const errorData = await saveResponse.json().catch(() => ({}));
            throw new Error(errorData.error || 'Failed to save config');
        }
        
        const saveResult = await saveResponse.json();
        debug.log('Config saved:', saveResult);
        
        showToast('Konfiguration gespeichert - Anwendung wird neu gestartet...', 'success', 2000);
        
        // Restart application after short delay
        setTimeout(async () => {
            try {
                const reloadResponse = await fetch('/api/reload', { 
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                if (reloadResponse.ok) {
                    debug.log('Reload triggered successfully');
                } else {
                    console.error('Reload failed:', reloadResponse.status);
                    showToast('Neustart fehlgeschlagen - bitte manuell neustarten', 'error', 5000);
                }
            } catch (reloadError) {
                console.error('Error triggering reload:', reloadError);
                // Server ist wahrscheinlich schon am Neustarten
            }
        }, 1000);
        
    } catch (error) {
        console.error('Error saving config:', error);
        showToast(`Fehler beim Speichern: ${error.message}`, 'error', 5000);
    }
}

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', async () => {
    await loadDebugConfig();
    initErrorLogging();
    
    // Event Listeners
    document.getElementById('saveBtn').addEventListener('click', saveConfig);
    
    // Initialize
    loadConfig();
});
