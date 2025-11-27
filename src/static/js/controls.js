/**
 * Controls.js - New Dual-Player Layout
 * Video + Art-Net players with FX control
 */

import { showToast } from './common.js';

const API_BASE = '';
let availableEffects = [];
let availableGenerators = [];
let videoEffects = [];
let artnetEffects = [];
let clipEffects = [];
let updateInterval = null;
let playlistUpdateInterval = null;

// ========================================
// GENERIC PLAYER CONFIGURATION
// ========================================

const playerConfigs = {
    video: {
        id: 'video',
        name: 'Video',
        apiBase: '/api/player/video',
        legacyApi: {
            play: '/api/play',
            pause: '/api/pause',
            stop: '/api/stop'
        },
        playlistContainerId: 'videoPlaylist',
        autoplayBtnId: 'videoAutoplayBtn',
        loopBtnId: 'videoLoopBtn',
        files: [],
        currentFile: null,
        autoplay: false,
        loop: false,
        transitionConfig: {
            enabled: false,
            effect: 'fade',
            duration: 1.0,
            easing: 'ease_in_out'
        }
    },
    artnet: {
        id: 'artnet',
        name: 'Art-Net',
        apiBase: '/api/player/artnet',
        playlistContainerId: 'artnetPlaylist',
        autoplayBtnId: 'artnetAutoplayBtn',
        loopBtnId: 'artnetLoopBtn',
        files: [],
        currentFile: null,
        autoplay: false,
        loop: false,
        transitionConfig: {
            enabled: false,
            effect: 'fade',
            duration: 1.0,
            easing: 'ease_in_out'
        }
    }
};

// Legacy global variables for backwards compatibility
let videoAutoplay = false;
let videoLoop = false;
let artnetAutoplay = false;
let artnetLoop = false;

// Clip FX State (NEW: UUID-based)
let selectedClipId = null;  // UUID from clip registry
let selectedClipPath = null;  // Original path (for display)
let selectedClipPlayerType = null;  // 'video' or 'artnet'

// Active Item Tracking (for "active" border)
let currentVideoItemId = null;  // UUID of currently playing video item
let currentArtnetItemId = null;  // UUID of currently playing artnet item

// Transition State (legacy - now in playerConfigs)
let videoTransitionConfig = playerConfigs.video.transitionConfig;
let artnetTransitionConfig = playerConfigs.artnet.transitionConfig;

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    init().catch(error => {
        console.error('❌ Initialization error:', error);
    });
});

async function init() {
    try {
        await loadAvailableEffects();
        await loadAvailableGenerators();
        await loadVideoPlaylist();
        await loadArtnetPlaylist();
        
        // MIGRATION: Check and fix any Float IDs in loaded playlists
        let needsUpdate = false;
        
        for (const playerId of ['video', 'artnet']) {
            const files = playerId === 'video' ? videoFiles : artnetFiles;
            for (let i = 0; i < files.length; i++) {
                const id = files[i].id;
                const isFloatId = (typeof id === 'number') || 
                                  (typeof id === 'string' && /^\d+\.\d+$/.test(id));
                
                if (isFloatId) {
                    console.warn(`⚠️ Migrating ${playerId} playlist item ${i} (${files[i].name}) from float ID (${id}) to UUID`);
                    const newId = crypto.randomUUID();
                    files[i].id = newId;
                    console.log(`   └─ New UUID: ${newId}`);
                    needsUpdate = true;
                } else if (!id) {
                    console.warn(`⚠️ ${playerId} playlist item ${i} (${files[i].name}) has no ID, generating UUID`);
                    files[i].id = crypto.randomUUID();
                    needsUpdate = true;
                } else {
                    console.log(`✅ ${playerId} playlist item ${i} (${files[i].name}) has valid UUID: ${id}`);
                }
            }
        }
        
        // If any IDs were migrated, update backend playlists
        if (needsUpdate) {
            console.log('🔄 Updating backend playlists with new UUIDs...');
            await updateVideoPlaylist();
            await updateArtnetPlaylist();
        } else {
            console.log('✅ All playlist items have valid UUIDs, no migration needed');
        }
        
        await refreshVideoEffects();
        await refreshArtnetEffects();
        startPreviewStream();
        startArtnetPreviewStream();
        setupEffectDropZones();
        setupGeneratorDropZones();
        setupPlaylistContainerDropHandlers(); // Register container handlers once
    } catch (error) {
        console.error('❌ Init failed:', error);
        throw error;
    }
    
    // Start auto-refresh
    updateInterval = setInterval(async () => {
        await refreshVideoEffects();
        await refreshArtnetEffects();
    }, 2000);
    
    // Schneller Poll für aktuelle Videos (500ms) - nur wenn autoplay aktiv
    playlistUpdateInterval = setInterval(async () => {
        if (videoAutoplay || artnetAutoplay) {
            await updateCurrentVideoFromPlayer();
            await updateCurrentArtnetFromPlayer();
        }
    }, 500);
}

// Update current video from player status
async function updateCurrentVideoFromPlayer() {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/status`);
        const data = await response.json();
        
        if (data.success) {
            // Normalisiere Pfad (entferne führende Slashes/Backslashes)
            const newVideo = data.current_video ? data.current_video.replace(/^[\\\/]+/, '') : null;
            const normalizedCurrent = currentVideo ? currentVideo.replace(/^[\\\/]+/, '') : null;
            
            // Update currentVideoItemId from backend (important for active border)
            const newClipId = data.clip_id || null;
            const clipIdChanged = currentVideoItemId !== newClipId;
            
            if (normalizedCurrent !== newVideo || clipIdChanged) {
                currentVideo = newVideo;
                currentVideoItemId = newClipId;  // Update active item ID
                renderVideoPlaylist();
            }
        }
    } catch (error) {
        // Silent fail - don't spam console
    }
}

// Update current Art-Net video from player status
async function updateCurrentArtnetFromPlayer() {
    try {
        const response = await fetch(`${API_BASE}/api/player/artnet/status`);
        const data = await response.json();
        
        if (data.success) {
            // Normalisiere Pfad (entferne führende Slashes/Backslashes)
            const newVideo = data.current_video ? data.current_video.replace(/^[\\\/]+/, '') : null;
            const normalizedCurrent = currentArtnet ? currentArtnet.replace(/^[\\\/]+/, '') : null;
            
            // Update currentArtnetItemId from backend (important for active border)
            const newClipId = data.clip_id || null;
            const clipIdChanged = currentArtnetItemId !== newClipId;
            
            if (normalizedCurrent !== newVideo || clipIdChanged) {
                currentArtnet = newVideo;
                currentArtnetItemId = newClipId;  // Update active item ID
                renderArtnetPlaylist();
            }
        }
    } catch (error) {
        // Silent fail - don't spam console
    }
}

// ========================================
// TAB SWITCHING
// ========================================

window.switchTab = function(tabName) {
    // Remove active from all tabs
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    
    // Add active to selected tab
    event.target.classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
};

// ========================================
// EFFECTS LIBRARY
// ========================================

async function loadAvailableEffects() {
    try {
        console.log('📥 Loading available effects from API...');
        const response = await fetch(`${API_BASE}/api/plugins/list`);
        const data = await response.json();
        
        console.log('📦 API Response:', data);
        
        if (data.success) {
            availableEffects = data.plugins.filter(p => p.type && p.type.toLowerCase() === 'effect');
            console.log(`✅ Loaded ${availableEffects.length} effects:`, availableEffects.map(e => e.id));
            renderAvailableEffects();
        } else {
            console.error('❌ Failed to load effects:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading effects:', error);
    }
}

function renderAvailableEffects() {
    const container = document.getElementById('availableEffects');
    
    if (availableEffects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No effect plugins found</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = availableEffects.map(effect => `
        <div class="effect-card" 
             draggable="true" 
             data-effect-id="${effect.id}"
             ondragstart="startEffectDrag(event, '${effect.id}')">
            <div class="effect-card-title">🎨 ${effect.name}</div>
            <div class="effect-card-description">${effect.description || 'No description'}</div>
            <small class="text-muted">v${effect.version} • Drag to FX panel</small>
        </div>
    `).join('');
}

// ========================================
// GENERATOR LOADING
// ========================================

async function loadAvailableGenerators() {
    try {
        console.log('📥 Loading available generators from API...');
        const response = await fetch(`${API_BASE}/api/plugins/list?type=generator`);
        const data = await response.json();
        
        console.log('📦 Generators API Response:', data);
        
        if (data.success) {
            availableGenerators = data.plugins;
            console.log(`✅ Loaded ${availableGenerators.length} generators:`, availableGenerators.map(g => g.id));
            renderAvailableGenerators();
        } else {
            console.error('❌ Failed to load generators:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading generators:', error);
    }
}

function renderAvailableGenerators() {
    const container = document.getElementById('availableSources');
    
    if (availableGenerators.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p>No generator plugins found</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = availableGenerators.map(generator => `
        <div class="generator-card" 
             draggable="true" 
             data-generator-id="${generator.id}"
             ondragstart="startGeneratorDrag(event, '${generator.id}')"
             ondragend="endGeneratorDrag(event)">
            <div class="generator-card-title">🌟 ${generator.name}</div>
            <div class="generator-card-description">${generator.description || 'No description'}</div>
            <small class="text-muted">v${generator.version} • Drag to playlist</small>
        </div>
    `).join('');
}

// Drag & Drop for Effects
window.startEffectDrag = function(event, effectId) {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('effectId', effectId);
};

// Drag & Drop for Generators
window.startGeneratorDrag = function(event, generatorId) {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('generatorId', generatorId);
    event.dataTransfer.setData('text/plain', `generator:${generatorId}`);
    
    const generator = availableGenerators.find(g => g.id === generatorId);
    if (generator) {
        event.dataTransfer.setData('generatorName', generator.name);
    }
    
    // Make dragged element semi-transparent
    event.target.style.opacity = '0.5';
    
    // Store in global var as backup (dataTransfer might not be accessible during dragover)
    window.currentDragGenerator = {
        id: generatorId,
        name: generator?.name
    };
};

// Handle drag end for generators
window.endGeneratorDrag = function(event) {
    event.target.style.opacity = '1';
    window.currentDragGenerator = null;
};

// Setup drop zones for FX panels
function setupEffectDropZones() {
    const videoFxPanel = document.getElementById('videoFxList');
    const artnetFxPanel = document.getElementById('artnetFxList');
    const clipFxPanel = document.getElementById('clipFxList');
    
    [videoFxPanel, artnetFxPanel].forEach((panel, index) => {
        const playerType = index === 0 ? 'video' : 'artnet';
        
        panel.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            panel.style.background = 'var(--bg-tertiary)';
        });
        
        panel.addEventListener('dragleave', (e) => {
            panel.style.background = '';
        });
        
        panel.addEventListener('drop', async (e) => {
            e.preventDefault();
            panel.style.background = '';
            
            const effectId = e.dataTransfer.getData('effectId');
            if (effectId) {
                if (playerType === 'video') {
                    await addEffectToVideo(effectId);
                } else {
                    await addEffectToArtnet(effectId);
                }
            }
        });
    });
    
    // Clip FX Drop Zone
    clipFxPanel.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        clipFxPanel.style.background = 'var(--bg-tertiary)';
    });
    
    clipFxPanel.addEventListener('dragleave', (e) => {
        clipFxPanel.style.background = '';
    });
    
    clipFxPanel.addEventListener('drop', async (e) => {
        e.preventDefault();
        clipFxPanel.style.background = '';
        
        const effectId = e.dataTransfer.getData('effectId');
        if (effectId && selectedClipId && selectedClipPlayerType) {
            await addEffectToClip(effectId);
        }
    });
}

// Setup drop zones for Generators (to playlists)
function setupGeneratorDropZones() {
    // This function is called once on init
    // The actual drop handling is done in renderVideoPlaylist() and renderArtnetPlaylist()
    // because they rebuild the DOM on each render
    console.log('✅ Generator drop zones will be handled in playlist rendering');
}

// Setup container-level drop handlers (ONCE on init, not on every render!)
function setupPlaylistContainerDropHandlers() {
    const videoContainer = document.getElementById('videoPlaylist');
    const artnetContainer = document.getElementById('artnetPlaylist');
    
    // Video container drop handler  
    videoContainer.addEventListener('drop', (e) => {
        // Delay execution to allow child handlers to set flag first
        setTimeout(() => {
            // Skip if already handled by drop-zone or empty-state
            if (e._handledByDropZone) {
                return;
            }
        
            
            // Skip if drop is on playlist item or drop-zone
            if (e.target.classList.contains('playlist-item') || 
                e.target.closest('.playlist-item') ||
                e.target.classList.contains('drop-zone') || 
                e.target.classList.contains('empty-state')) {
                return;
            }
            
            // Handle drop on empty container space
            e.preventDefault();
            e.stopPropagation();
            
            // Check if dropping a generator
            let generatorId = e.dataTransfer.getData('generatorId');
            if (!generatorId && window.currentDragGenerator) {
                generatorId = window.currentDragGenerator.id;
            }
            
            if (generatorId) {
                const generatorName = e.dataTransfer.getData('generatorName') || window.currentDragGenerator?.name || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId
                };
                videoFiles.push(newGenerator);
                renderVideoPlaylist();
                updateVideoPlaylist();
                return;
            }
            
            // Check if dropping a file
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: crypto.randomUUID() // Unique ID that becomes clip_id
                };
                videoFiles.push(newVideo);
                renderVideoPlaylist();
                updateVideoPlaylist();
            }
        }, 0); // Delayed to let child handlers set flag first
    });
    
    // Art-Net container drop handler
    artnetContainer.addEventListener('drop', (e) => {
        // Delay execution to allow child handlers to set flag first
        setTimeout(() => {
            // Skip if already handled by drop-zone or empty-state
            if (e._handledByDropZone) {
                return;
            }
        
            
            // Skip if drop is on playlist item or drop-zone
            if (e.target.classList.contains('playlist-item') || 
                e.target.closest('.playlist-item') ||
                e.target.classList.contains('drop-zone') || 
                e.target.classList.contains('empty-state')) {
                return;
            }
            
            // Handle drop on empty container space
            e.preventDefault();
            e.stopPropagation();
            
            // Check if dropping a generator
            let generatorId = e.dataTransfer.getData('generatorId');
            if (!generatorId && window.currentDragGenerator) {
                generatorId = window.currentDragGenerator.id;
            }
            
            if (generatorId) {
                const generatorName = e.dataTransfer.getData('generatorName') || window.currentDragGenerator?.name || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId
                };
                artnetFiles.push(newGenerator);
                renderArtnetPlaylist();
                updateArtnetPlaylist();
                return;
            }
            
            // Check if dropping a file
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: crypto.randomUUID() // Unique ID that becomes clip_id
                };
                artnetFiles.push(newVideo);
                renderArtnetPlaylist();
                updateArtnetPlaylist();
            }
        }, 0); // Delayed to let child handlers set flag first
    });
    
    console.log('✅ Container drop handlers registered (once)');
}

// Load generator as clip into player
window.loadGeneratorClip = async function(generatorId, playerType = 'video', clipId = null) {
    try {
        const generator = availableGenerators.find(g => g.id === generatorId);
        if (!generator) {
            showToast(`Generator not found: ${generatorId}`, 'error');
            return;
        }
        
        // Get default parameters for this generator
        const paramsResponse = await fetch(`${API_BASE}/api/plugins/${generatorId}/parameters`);
        const paramsData = await paramsResponse.json();
        
        const defaultParams = {};
        // API returns {parameters: [...]} without success field
        if (paramsData.parameters) {
            paramsData.parameters.forEach(param => {
                defaultParams[param.name] = param.default;
            });
        }
        
        console.log('🔧 Loading generator with parameters:', defaultParams);
        
        // Load generator as clip
        const response = await fetch(`${API_BASE}/api/player/${playerType}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'generator',
                generator_id: generatorId,
                parameters: defaultParams,
                clip_id: clipId  // Frontend-provided UUID
            })
        });
        
        const data = await response.json();
        if (data.success) {
            // Store clip info - use frontend clipId (UUID) instead of backend response
            selectedClipId = clipId || data.clip_id;
            console.log(`🆔 Generator clip ID: frontend=${clipId}, backend=${data.clip_id}, using=${selectedClipId}`);
            selectedClipPath = `generator:${generatorId}`;
            selectedClipPlayerType = playerType;
            
            // Update active item ID based on player type
            if (playerType === 'video') {
                currentVideoItemId = clipId || data.clip_id;
            } else if (playerType === 'artnet') {
                currentArtnetItemId = clipId || data.clip_id;
            }
            
            // Store generator metadata for parameter display
            window.currentGeneratorId = generatorId;
            window.currentGeneratorParams = defaultParams;
            window.currentGeneratorMeta = generator;
            
            // Set currentVideo for playlist highlighting (normalize path like loadVideoFile does)
            currentVideo = `generator:${generatorId}`.replace(/^[\\\/]+/, '');
            renderVideoPlaylist();
            
            showToast(`✅ Generator loaded: ${generator.name}`, 'success');
            console.log('✅ Generator clip loaded:', data);
            
            // Start playback automatically
            try {
                await fetch(`${API_BASE}/api/player/${playerType}/play`, { method: 'POST' });
                console.log('▶️ Auto-started generator playback');
            } catch (error) {
                console.error('Error starting playback:', error);
            }
            
            // Refresh effects and show generator parameters
            await refreshClipEffects();
            await displayGeneratorParameters(generatorId, paramsData.parameters);
        } else {
            showToast(`❌ Failed to load generator: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error loading generator clip:', error);
        showToast(`❌ Error: ${error.message}`, 'error');
    }
};

// Display generator parameters in clip section
async function displayGeneratorParameters(generatorId, parameters) {
    const generator = availableGenerators.find(g => g.id === generatorId);
    if (!generator) return;
    
    // Store parameters for later rendering
    window.currentGeneratorParameters = parameters;
    
    // Re-render to include parameters
    renderClipEffects();
}

function renderGeneratorParametersSection() {
    if (!window.currentGeneratorId || !window.currentGeneratorParameters) {
        return '';
    }
    
    const parameters = window.currentGeneratorParameters;
    const generator = availableGenerators.find(g => g.id === window.currentGeneratorId);
    if (!generator || !parameters || parameters.length === 0) {
        return '';
    }
    
    // Build collapsible parameter section
    let html = `
        <div class="generator-params-section expanded" style="border-bottom: 1px solid var(--border-color); margin-bottom: 1rem;">
            <div class="effect-header" onclick="this.parentElement.classList.toggle('expanded')" style="cursor: pointer; padding: 0.75rem; background: var(--bg-tertiary); display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <span style="font-size: 1.2rem;">🌟</span>
                    <strong>Generator Parameters</strong>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="effect-params" style="padding: 0.5rem;">
    `;
    
    parameters.forEach(param => {
        const currentValue = window.currentGeneratorParams?.[param.name] ?? param.default;
        
        html += `
            <div class="param-control" style="margin-bottom: 1rem; padding: 0.5rem;">
                <label style="display: block; margin-bottom: 0.25rem; font-weight: 500;">
                    ${param.label || param.name}
                </label>
                <small style="display: block; margin-bottom: 0.5rem; color: var(--text-secondary);">
                    ${param.description || ''}
                </small>
        `;
        
        // Render control based on parameter type
        if (param.type === 'float' || param.type === 'int') {
            const step = param.step || (param.type === 'int' ? 1 : 0.01);
            html += `
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="range" 
                           id="gen-param-${param.name}"
                           min="${param.min}"
                           max="${param.max}"
                           step="${step}"
                           value="${currentValue}"
                           onchange="updateGeneratorParameter('${param.name}', this.value)"
                           style="flex: 1;">
                    <span id="gen-param-${param.name}-value" style="min-width: 50px; text-align: right;">
                        ${currentValue}
                    </span>
                </div>
            `;
        } else if (param.type === 'bool') {
            html += `
                <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer;">
                    <input type="checkbox" 
                           id="gen-param-${param.name}"
                           ${currentValue ? 'checked' : ''}
                           onchange="updateGeneratorParameter('${param.name}', this.checked)">
                    <span>Enable</span>
                </label>
            `;
        } else if (param.type === 'string') {
            html += `
                <input type="text" 
                       id="gen-param-${param.name}"
                       value="${currentValue}"
                       onchange="updateGeneratorParameter('${param.name}', this.value)"
                       class="form-control form-control-sm">
            `;
        }
        
        html += `</div>`;
    });
    
    html += `
            </div>
        </div>
    `;
    
    return html;
}

// Update generator parameter
window.updateGeneratorParameter = async function(paramName, value) {
    if (!window.currentGeneratorId || !selectedClipId || !selectedClipPlayerType) {
        console.error('No generator clip selected');
        return;
    }
    
    try {
        // Convert value to correct type
        const numValue = parseFloat(value);
        const finalValue = isNaN(numValue) ? value : numValue;
        
        // Update local state
        if (!window.currentGeneratorParams) {
            window.currentGeneratorParams = {};
        }
        window.currentGeneratorParams[paramName] = finalValue;
        
        // Update value display
        const valueDisplay = document.getElementById(`gen-param-${paramName}-value`);
        if (valueDisplay) {
            valueDisplay.textContent = finalValue;
        }
        
        // Send update to backend
        const response = await fetch(`/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/generator/parameter`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                parameter: paramName,
                value: finalValue
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`✅ Generator parameter updated: ${paramName} = ${finalValue}`);
            
            // Update the generator in the playlist with new parameters
            if (window.currentGeneratorId && selectedClipPath) {
                const playerType = selectedClipPlayerType;
                const playlistArray = playerType === 'video' ? videoFiles : artnetFiles;
                
                // Find all instances of this generator in playlist and update their parameters
                playlistArray.forEach(item => {
                    if (item.type === 'generator' && item.generator_id === window.currentGeneratorId) {
                        if (!item.parameters) {
                            item.parameters = {};
                        }
                        item.parameters[paramName] = finalValue;
                    }
                });
                
                console.log(`📋 Updated generator parameters in playlist`);
            }
        } else {
            console.error(`Failed to update parameter: ${result.error}`);
            showToast(`Error: ${result.error}`, 'error');
        }
        
    } catch (error) {
        console.error('Error updating generator parameter:', error);
        showToast(`Error: ${error.message}`, 'error');
    }
};

// ========================================
// VIDEO PREVIEW STREAM
// ========================================

function startPreviewStream() {
    const previewImg = document.getElementById('videoPreviewImg');
    previewImg.src = `${API_BASE}/preview?t=${Date.now()}`;
    
    // Refresh preview every 100ms
    setInterval(() => {
        previewImg.src = `${API_BASE}/preview?t=${Date.now()}`;
    }, 100);
}

window.openVideoFullscreen = function() {
    window.open('/fullscreen', 'Flux Fullscreen', 'width=1920,height=1080');
};

// ========================================
// GENERIC PLAYLIST MANAGEMENT
// ========================================

// Legacy global variables (for backwards compatibility)
let videoFiles = [];
let currentVideo = null;
let artnetFiles = [];
let currentArtnet = null;

async function loadPlaylist(playerId) {
    const config = playerConfigs[playerId];
    if (!config) {
        console.error(`Unknown player: ${playerId}`);
        return;
    }
    
    try {
        // Load player configuration from server
        const response = await fetch(`${API_BASE}${config.apiBase}/status`);
        const data = await response.json();
        
        if (data.success && data.playlist) {
            // Restore playlist (detect generators)
            config.files = data.playlist.map((path, idx) => {
                // Handle both string paths (legacy) and object entries (new)
                let actualPath = typeof path === 'string' ? path : path.path;
                let savedId = (typeof path === 'object' && path.id) ? path.id : null;
                
                // MIGRATION: Convert old float IDs to new UUIDs
                if (savedId && typeof savedId === 'number') {
                    console.warn(`⚠️ Converting old float ID (${savedId}) to UUID`);
                    savedId = null; // Force generation of new UUID
                }
                
                if (!actualPath) {
                    console.warn(`Empty path in ${playerId} playlist at index`, idx);
                    return null;
                }
                
                if (actualPath.startsWith('generator:')) {
                    // Generator item
                    const generatorId = actualPath.replace('generator:', '');
                    const generator = availableGenerators.find(g => g.id === generatorId);
                    const generatorName = generator ? generator.name : generatorId;
                    return {
                        path: actualPath,
                        name: `🌟 ${generatorName}`,
                        id: savedId || crypto.randomUUID(), // Use saved UUID or generate new
                        type: 'generator',
                        generator_id: generatorId,
                        parameters: (typeof path === 'object' && path.parameters) ? path.parameters : {}
                    };
                } else {
                    // Regular video item
                    return {
                        name: actualPath.split('/').pop().split('\\').pop(),
                        path: actualPath,
                        id: savedId || crypto.randomUUID() // Use saved UUID or generate new
                    };
                }
            }).filter(item => item !== null);
            
            // Restore autoplay/loop state
            config.autoplay = data.autoplay || false;
            config.loop = data.loop || false;
            
            // Restore current file
            if (data.current_video) {
                config.currentFile = data.current_video.replace(/^[\\\/]+/, '');
            }
            
            // Update UI buttons
            const autoplayBtn = document.getElementById(config.autoplayBtnId);
            const loopBtn = document.getElementById(config.loopBtnId);
            if (autoplayBtn) {
                if (config.autoplay) {
                    autoplayBtn.classList.remove('btn-outline-primary');
                    autoplayBtn.classList.add('btn-primary');
                } else {
                    autoplayBtn.classList.remove('btn-primary');
                    autoplayBtn.classList.add('btn-outline-primary');
                }
            }
            if (loopBtn) {
                if (config.loop) {
                    loopBtn.classList.remove('btn-outline-primary');
                    loopBtn.classList.add('btn-primary');
                } else {
                    loopBtn.classList.remove('btn-primary');
                    loopBtn.classList.add('btn-outline-primary');
                }
            }
            
            // Sync legacy variables
            if (playerId === 'video') {
                videoFiles = config.files;
                currentVideo = config.currentFile;
                videoAutoplay = config.autoplay;
                videoLoop = config.loop;
            } else if (playerId === 'artnet') {
                artnetFiles = config.files;
                currentArtnet = config.currentFile;
                artnetAutoplay = config.autoplay;
                artnetLoop = config.loop;
            }
        } else {
            // Start with empty playlist
            config.files = [];
            if (playerId === 'video') videoFiles = [];
            if (playerId === 'artnet') artnetFiles = [];
        }
    } catch (error) {
        console.error(`❌ Failed to load ${playerId} playlist:`, error);
        config.files = [];
        if (playerId === 'video') videoFiles = [];
        if (playerId === 'artnet') artnetFiles = [];
    }
    
    renderPlaylist(playerId);
}

// Generic render function (delegates to specific implementations for now)
function renderPlaylist(playerId) {
    if (playerId === 'video') {
        renderVideoPlaylist();
    } else if (playerId === 'artnet') {
        renderArtnetPlaylist();
    }
}

// Legacy wrapper functions
async function loadVideoPlaylist() {
    await loadPlaylist('video');
}

async function loadArtnetPlaylist() {
    await loadPlaylist('artnet');
}

function renderVideoPlaylist() {
    const container = document.getElementById('videoPlaylist');
    
    if (videoFiles.length === 0) {
        container.innerHTML = `
            <div class="empty-state drop-zone" data-drop-index="0" data-playlist="video" style="width: 100%; padding: 2rem; text-align: center; min-height: 150px;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📂</div>
                <p style="margin: 0.5rem 0;">Playlist leer</p>
                <small style="color: var(--text-secondary, #999);">Drag & Drop aus Files Tab oder Sources</small>
            </div>
        `;
        
        // Add drop handler to empty state
        const emptyZone = container.querySelector('.empty-state.drop-zone');
        if (emptyZone) {
            emptyZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) {
                    e.dataTransfer.dropEffect = 'copy';
                }
                emptyZone.style.background = 'var(--bg-tertiary)';
            });
            
            emptyZone.addEventListener('dragleave', (e) => {
                emptyZone.style.background = '';
            });
            
            emptyZone.addEventListener('drop', (e) => {
                e._handledByDropZone = true; // Set flag FIRST before anything else!
                e.preventDefault();
                e.stopPropagation(); // WICHTIG: Verhindere Bubbling zum Container!
                e.stopImmediatePropagation();
                emptyZone.style.background = '';
                
                // Get playlist type from data attribute
                const playlistType = emptyZone.dataset.playlist || 'video';
                const files = playlistType === 'video' ? videoFiles : artnetFiles;
                
                // Check if dropping a generator
                const generatorId = e.dataTransfer.getData('generatorId');
                if (generatorId) {
                    console.log(`🌟 DROP GENERATOR to empty ${playlistType} playlist, id:`, generatorId);
                    const generatorName = e.dataTransfer.getData('generatorName') || generatorId;
                    const newGenerator = {
                        path: `generator:${generatorId}`,
                        name: `🌟 ${generatorName}`,
                        id: crypto.randomUUID(),
                        type: 'generator',
                        generator_id: generatorId
                    };
                    files.push(newGenerator);
                    
                    // Autoload since playlist was empty (nur bei video)
                    if (playlistType === 'video') {
                        loadGeneratorClip(generatorId, 'video', newGenerator.id);
                    }
                    console.log(`📋 Added and loaded generator ${generatorName} to empty ${playlistType} playlist`);
                    
                    // Delay render to allow event to finish propagating
                    setTimeout(() => {
                        renderPlaylist(playlistType);
                        updatePlaylist(playlistType);  // Sync to backend!
                    }, 0);
                    return false;
                }
                
                // Check if dropping a file
                const videoPath = e.dataTransfer.getData('video-path');
                if (videoPath) {
                    console.log(`🎯 DROP FILE to empty ${playlistType} playlist, path:`, videoPath);
                    const fileName = videoPath.split(/[/\\]/).pop();
                    const newVideo = {
                        path: videoPath,
                        name: fileName,
                        id: crypto.randomUUID()
                    };
                    files.push(newVideo);
                    console.log(`📋 Added file ${fileName} to empty ${playlistType} playlist`);
                    
                    // Delay render to allow event to finish propagating
                    setTimeout(() => {
                        renderPlaylist(playlistType);
                        updatePlaylist(playlistType);  // Sync to backend!
                    }, 0);
                    return false;
                }
            });
        }
        
        return;
    }
    
    // Build HTML with drop zones between items
    let html = '';
    videoFiles.forEach((video, index) => {
        // Check if this is the currently playing clip (use UUID instead of path)
        const isActive = currentVideoItemId && video.id === currentVideoItemId;
        
        // Drop zone before item
        html += `<div class="drop-zone" data-drop-index="${index}" data-playlist="video"></div>`;
        
        // Playlist item (store path for identification)
        html += `
            <div class="playlist-item ${isActive ? 'active' : ''}" 
                 data-video-index="${index}"
                 data-video-path="${video.path}"
                 data-playlist="video"
                 draggable="true">
                <div class="playlist-item-name">${video.name}</div>
                <button class="playlist-item-remove" onclick="removeFromVideoPlaylist(${index}); event.stopPropagation();" title="Remove from playlist">×</button>
            </div>
        `;
    });
    
    // Drop zone at the end
    html += `<div class="drop-zone" data-drop-index="${videoFiles.length}" data-playlist="video"></div>`;
    
    container.innerHTML = html;
    
    // Add event handlers after rendering
    let isDragging = false;
    let hoverTimer = null;
    
    // Playlist item handlers (click, hover and dragstart)
    container.querySelectorAll('.playlist-item').forEach((item) => {
        const index = parseInt(item.dataset.videoIndex);
        
        // Hover handler - zeige Effekte/Parameter nach 1 Sekunde
        item.addEventListener('mouseenter', (e) => {
            if (isDragging) return;
            
            // Clear any existing timer
            if (hoverTimer) {
                clearTimeout(hoverTimer);
            }
            
            // Start new timer (1 second)
            hoverTimer = setTimeout(async () => {
                const videoItem = videoFiles[index];
                
                // Check if item still exists (might have been removed)
                if (!videoItem) {
                    return;
                }
                
                // Load effects/parameters without switching video
                if (videoItem.type === 'generator' && videoItem.generator_id) {
                    // Load generator parameters
                    console.log(`👁️ Hovering generator: ${videoItem.generator_id}`);
                    
                    // Use the item's UUID directly from the playlist
                    selectedClipId = videoItem.id;
                    console.log(`🎯 Using generator clip UUID from playlist: ${selectedClipId}`);
                    
                    selectedClipPath = videoItem.path;
                    selectedClipPlayerType = 'video';
                    
                    // Get generator metadata and show parameters
                    const generator = availableGenerators.find(g => g.id === videoItem.generator_id);
                    if (generator) {
                        window.currentGeneratorId = videoItem.generator_id;
                        window.currentGeneratorMeta = generator;
                        
                        // Get parameter metadata from API
                        const paramsResponse = await fetch(`${API_BASE}/api/plugins/${videoItem.generator_id}/parameters`);
                        const paramsData = await paramsResponse.json();
                        
                        // Store parameter definitions (array) for rendering
                        window.currentGeneratorParameters = paramsData.parameters || [];
                        
                        // Store current values (object) for display
                        const params = {};
                        if (paramsData.parameters) {
                            paramsData.parameters.forEach(param => {
                                params[param.name] = videoItem.parameters?.[param.name] ?? param.default;
                            });
                        }
                        window.currentGeneratorParams = params;
                        
                        // Show parameters (pass metadata array)
                        displayGeneratorParameters(videoItem.generator_id, paramsData.parameters || []);
                    }
                } else {
                    // Regular video - show effects
                    console.log(`👁️ Hovering video: ${videoItem.path}`);
                    
                    // Use the item's UUID directly from the playlist
                    selectedClipId = videoItem.id;
                    console.log(`🎯 Using clip UUID from playlist: ${selectedClipId}`);
                    
                    selectedClipPath = videoItem.path;
                    selectedClipPlayerType = 'video';
                    
                    // Clear generator state
                    window.currentGeneratorId = null;
                    window.currentGeneratorParams = null;
                    window.currentGeneratorMeta = null;
                    
                    // Refresh effects panel
                    await refreshClipEffects();
                }
                
                // Already called refreshClipEffects for videos, generators call displayGeneratorParameters
            }, 1000); // 1 second delay
        });
        
        item.addEventListener('mouseleave', (e) => {
            // Clear hover timer when leaving
            if (hoverTimer) {
                clearTimeout(hoverTimer);
                hoverTimer = null;
            }
        });
        
        // Click handler - abspielen UND Effekte anzeigen
        item.addEventListener('click', async (e) => {
            if (!isDragging && !e.target.classList.contains('playlist-item-remove')) {
                // Clear hover timer
                if (hoverTimer) {
                    clearTimeout(hoverTimer);
                    hoverTimer = null;
                }
                
                const videoItem = videoFiles[index];
                currentVideoItemId = videoItem.id; // Store which item is playing
                
                if (videoItem.type === 'generator' && videoItem.generator_id) {
                    await loadGeneratorClip(videoItem.generator_id, 'video', videoItem.id);
                } else {
                    await loadVideoFile(videoItem.path, videoItem.id);
                }
            }
        });
        
        // Dragstart
        item.addEventListener('dragstart', (e) => {
            isDragging = true;
            draggedIndex = index;
            draggedPlaylist = 'video';
            item.style.opacity = '0.5';
            e.dataTransfer.effectAllowed = 'all';
            e.dataTransfer.setData('text/plain', index.toString());
            e.dataTransfer.setData('application/x-playlist-item', index.toString());
        });
        
        // Dragend
        item.addEventListener('dragend', (e) => {
            // Delay cleanup to allow drop event to fire first
            setTimeout(() => {
                item.style.opacity = '1';
                container.querySelectorAll('.drop-zone').forEach(zone => zone.classList.remove('drag-over'));
                isDragging = false;
                draggedIndex = null;
                draggedPlaylist = null;
            }, 50);
        });
    });
    
    // Drop zone handlers
    container.querySelectorAll('.drop-zone').forEach((zone) => {
        
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) {
                // Always allow copy for external drops (generators/files)
                e.dataTransfer.dropEffect = 'copy';
            }
            zone.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', (e) => {
            zone.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            e._handledByDropZone = true; // Flag for container handler
            zone.classList.remove('drag-over');
            
            const dropIndex = parseInt(zone.dataset.dropIndex);
            
            // Get generator ID from dataTransfer or backup
            let generatorId = e.dataTransfer.getData('generatorId');
            if (!generatorId && window.currentDragGenerator) {
                generatorId = window.currentDragGenerator.id;
            }
            
            // Check if dropping a generator from sources
            if (generatorId) {
                const generatorName = e.dataTransfer.getData('generatorName') || window.currentDragGenerator?.name || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId
                };
                videoFiles.splice(dropIndex, 0, newGenerator);
                
                // Only autoload if dropped at position 0 and playlist is empty or nothing is playing
                if (dropIndex === 0 && !currentVideo) {
                    loadGeneratorClip(generatorId, 'video', newGenerator.id);
                }
                
                // Update backend playlist
                updateVideoPlaylist();
                
                // Delay render to allow event to finish propagating
                setTimeout(() => renderVideoPlaylist(), 0);
                return false;
            }
            
            // Check if dropping a file from file browser
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                console.log('🎯 DROP FILE from browser at index:', dropIndex, 'path:', videoPath);
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: crypto.randomUUID() // Unique ID that becomes clip_id
                };
                videoFiles.splice(dropIndex, 0, newVideo);
                updateVideoPlaylist();
                console.log(`📋 Added file ${fileName} at position ${dropIndex}`);
                
                // Only autoload if dropped at position 0 and playlist was empty
                if (dropIndex === 0 && !currentVideo) {
                    loadVideoFile(newVideo.path);
                }
                
                // Delay render to allow event to finish propagating
                setTimeout(() => renderVideoPlaylist(), 0);
                return false;
            }
            
            // Check if reordering within playlist
            console.log('🎯 DROP: draggedPlaylist =', draggedPlaylist, 'draggedIndex =', draggedIndex);
            
            if (draggedPlaylist !== 'video' || draggedIndex === null) {
                return;
            }
            
            // Adjust drop index if dragging from before the drop position
            let adjustedDropIndex = dropIndex;
            if (draggedIndex < dropIndex) {
                adjustedDropIndex--;
            }
            
            if (draggedIndex !== adjustedDropIndex) {
                const [movedItem] = videoFiles.splice(draggedIndex, 1);
                videoFiles.splice(adjustedDropIndex, 0, movedItem);
                renderVideoPlaylist();
                updateVideoPlaylist();
            }
            
            return false;
        });
    });
    
    // Add drop handler to the playlist container itself (for drops on empty space)
    container.addEventListener('dragover', (e) => {
        // Only handle if not over a drop-zone or playlist-item
        if (!e.target.classList.contains('drop-zone') && !e.target.classList.contains('playlist-item')) {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) {
                e.dataTransfer.dropEffect = 'copy';
            }
        }
    });
    
    // Note: Container-level drop handler is now registered in setupPlaylistContainerDropHandlers()
    // called once during init to prevent multiple handler registrations
}

// Load video file WITHOUT adding to playlist (used for playlist clicks)
window.loadVideoFile = async function(videoPath, clipId = null) {
    try {
        // NEW: Use unified API
        const response = await fetch(`${API_BASE}/api/player/video/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: videoPath,
                clip_id: clipId  // Frontend-provided UUID
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentVideo = videoPath.replace(/^[\\\/]+/, '');
            
            // NEW: Store clip ID and path - use frontend clipId (UUID) instead of backend response
            selectedClipId = clipId || data.clip_id;
            currentVideoItemId = clipId || data.clip_id;  // Update active item ID
            console.log(`🆔 Video clip ID: frontend=${clipId}, backend=${data.clip_id}, using=${selectedClipId}`);
            selectedClipPath = videoPath;
            selectedClipPlayerType = 'video';
            
            renderVideoPlaylist();
            
            // Clear generator state (this is a regular video)
            window.currentGeneratorId = null;
            window.currentGeneratorParams = null;
            window.currentGeneratorMeta = null;
            
            console.log('✅ Video loaded with Clip-ID:', selectedClipId);
            await refreshClipEffects();
        } else {
            showToast(`Failed to load video: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error loading video:', error);
        showToast('Error loading video', 'error');
    }
};

// Load video and ADD to playlist (used for file browser drops)
window.loadVideo = async function(videoPath) {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentVideo = videoPath.replace(/^[\\\/]+/, '');
            
            // Always add to playlist (allow duplicates)
            const filename = videoPath.split('/').pop();
            const folder = videoPath.includes('/') ? videoPath.split('/')[0] : 'root';
            videoFiles.push({
                filename: filename,
                path: videoPath,
                folder: folder,
                name: filename,
                id: crypto.randomUUID() // Unique ID for each entry
            });
            
            renderVideoPlaylist();
            console.log('✅ Video loaded:', videoPath);
        } else {
            showToast(`Failed to load video: ${data.message}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error loading video:', error);
        showToast('Error loading video', 'error');
    }
};

window.refreshVideoPlaylist = async function() {
    await loadVideoPlaylist();
};

window.removeFromVideoPlaylist = async function(index) {
    const video = videoFiles[index];
    const wasCurrentlyPlaying = (currentVideo === video.path);
    
    videoFiles.splice(index, 1);
    
    // If removed video was current, load next or stop
    if (wasCurrentlyPlaying) {
        currentVideo = null;
        selectedClipId = null;
        selectedClipPath = null;
        window.currentGeneratorId = null;
        window.currentGeneratorParams = null;
        window.currentGeneratorMeta = null;
        
        // Check if there are more clips in playlist
        if (videoFiles.length > 0) {
            // Load next clip (stay at same index, or go to previous if was last)
            const nextIndex = Math.min(index, videoFiles.length - 1);
            const nextItem = videoFiles[nextIndex];
            
            console.log(`⏭️ Auto-loading next clip after removal: ${nextItem.name}`);
            
            if (nextItem.type === 'generator' && nextItem.generator_id) {
                await loadGeneratorClip(nextItem.generator_id, 'video', nextItem.id);
            } else {
                await loadVideoFile(nextItem.path, nextItem.id);
            }
        } else {
            // No more clips - stop player and show black screen
            console.log('⏹️ No more clips in playlist - stopping player');
            try {
                await fetch(`${API_BASE}/api/player/video/stop`, { method: 'POST' });
            } catch (error) {
                console.error('Error stopping player:', error);
            }
            
            // Clear effects panel
            await refreshClipEffects();
        }
    }
    
    renderVideoPlaylist();
    
    // Update server with new playlist
    await updateVideoPlaylist();
};

// ========================================
// GENERIC PLAYER CONTROLS
// ========================================

async function play(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    const endpoint = config.legacyApi?.play || `${config.apiBase}/play`;
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
}

async function pause(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    const endpoint = config.legacyApi?.pause || `${config.apiBase}/pause`;
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
}

async function stop(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    const endpoint = config.legacyApi?.stop || `${config.apiBase}/stop`;
    await fetch(`${API_BASE}${endpoint}`, { method: 'POST' });
}

async function next(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/next`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            config.currentFile = data.video;
            if (playerId === 'video') {
                currentVideo = data.video;
                currentVideoItemId = data.clip_id || null;
            }
            if (playerId === 'artnet') {
                currentArtnet = data.video;
                currentArtnetItemId = data.clip_id || null;
            }
            renderPlaylist(playerId);
            console.log(`⏭️ Next ${config.name}:`, data.video);
        } else {
            console.error(`Failed to load next ${config.name}:`, data.message);
        }
    } catch (error) {
        console.error(`❌ Error loading next ${config.name}:`, error);
    }
}

async function previous(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/previous`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            config.currentFile = data.video;
            if (playerId === 'video') {
                currentVideo = data.video;
                currentVideoItemId = data.clip_id || null;
            }
            if (playerId === 'artnet') {
                currentArtnet = data.video;
                currentArtnetItemId = data.clip_id || null;
            }
            renderPlaylist(playerId);
            console.log(`⏮️ Previous ${config.name}:`, data.video);
        } else {
            console.error(`Failed to load previous ${config.name}:`, data.message);
        }
    } catch (error) {
        console.error(`❌ Error loading previous ${config.name}:`, error);
    }
}

// Legacy wrapper functions for HTML onclick handlers
window.playVideo = async function() { await play('video'); };
window.pauseVideo = async function() { await pause('video'); };
window.stopVideo = async function() { await stop('video'); };
window.nextVideo = async function() { await next('video'); };
window.previousVideo = async function() { await previous('video'); };

async function toggleAutoplay(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    config.autoplay = !config.autoplay;
    const btn = document.getElementById(config.autoplayBtnId);
    
    if (config.autoplay) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast(`${config.name} Autoplay aktiviert`, 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast(`${config.name} Autoplay deaktiviert`, 'info');
    }
    
    // Sync legacy variables
    if (playerId === 'video') videoAutoplay = config.autoplay;
    if (playerId === 'artnet') artnetAutoplay = config.autoplay;
    
    // Update Player ZUERST - damit autoplay flag gesetzt ist
    await updatePlaylist(playerId);
    
    // Dann starte Wiedergabe wenn autoplay aktiviert und Playlist vorhanden
    if (config.autoplay && config.files.length > 0) {
        const statusResponse = await fetch(`${API_BASE}${config.apiBase}/status`);
        const statusData = await statusResponse.json();
        if (statusData.success && !statusData.is_playing) {
            // Lade und starte erstes Video wenn keins läuft
            const firstFile = config.files[0];
            if (firstFile.type === 'generator' && firstFile.generator_id) {
                await loadGeneratorClip(firstFile.generator_id, playerId, firstFile.id);
            } else {
                if (playerId === 'video') await loadVideoFile(firstFile.path, firstFile.id);
                if (playerId === 'artnet') await loadArtnetFile(firstFile.path, firstFile.id);
            }
            await play(playerId);
            console.log(`🎬 ${config.name} Autoplay: Starte erstes Video`);
        }
    }
}

async function toggleLoop(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    config.loop = !config.loop;
    const btn = document.getElementById(config.loopBtnId);
    
    if (config.loop) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast(`${config.name} Loop aktiviert`, 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast(`${config.name} Loop deaktiviert`, 'info');
    }
    
    // Sync legacy variables
    if (playerId === 'video') videoLoop = config.loop;
    if (playerId === 'artnet') artnetLoop = config.loop;
    
    // Update Player
    await updatePlaylist(playerId);
}

async function updatePlaylist(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // Get files array (use legacy for backwards compat)
    const files = playerId === 'video' ? videoFiles : artnetFiles;
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/playlist/set`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                playlist: files.map(v => ({
                    path: v.path,
                    id: v.id,  // Save UUID
                    type: v.type,
                    generator_id: v.generator_id,
                    parameters: v.parameters
                })),
                autoplay: config.autoplay,
                loop: config.loop
            })
        });
        const data = await response.json();
        // Playlist updated successfully
    } catch (error) {
        console.error(`❌ Error updating ${config.name} playlist:`, error);
    }
}

// Legacy wrapper functions
window.toggleVideoAutoplay = async function() { await toggleAutoplay('video'); };
window.toggleVideoLoop = async function() { await toggleLoop('video'); };
async function updateVideoPlaylist() { await updatePlaylist('video'); }
async function updateArtnetPlaylist() { await updatePlaylist('artnet'); }


// ========================================
// ART-NET PLAYLIST RENDERING (LEGACY - uses generic load functions)
// ========================================

function renderArtnetPlaylist() {
    const container = document.getElementById('artnetPlaylist');
    
    if (artnetFiles.length === 0) {
        container.innerHTML = `
            <div class="empty-state drop-zone" data-drop-index="0" data-playlist="artnet" style="width: 100%; padding: 2rem; text-align: center; min-height: 150px;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📂</div>
                <p style="margin: 0.5rem 0;">Playlist leer</p>
                <small style="color: var(--text-secondary, #999);">Drag & Drop aus Files Tab oder Sources</small>
            </div>
        `;
        
        // Add drop handler to empty state
        const emptyZone = container.querySelector('.empty-state.drop-zone');
        if (emptyZone) {
            emptyZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) {
                    e.dataTransfer.dropEffect = 'copy';
                }
                emptyZone.style.background = 'var(--bg-tertiary)';
            });
            
            emptyZone.addEventListener('dragleave', (e) => {
                emptyZone.style.background = '';
            });
            
            emptyZone.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation(); // WICHTIG: Verhindere Bubbling zum Container!
                e.stopImmediatePropagation();
                e._handledByDropZone = true; // Flag for container handler
                emptyZone.style.background = '';
                
                // Get playlist type from data attribute
                const playlistType = emptyZone.dataset.playlist || 'artnet';
                const files = playlistType === 'video' ? videoFiles : artnetFiles;
                
                // Check if dropping a generator
                const generatorId = e.dataTransfer.getData('generatorId');
                if (generatorId) {
                    console.log(`🌟 DROP GENERATOR to empty ${playlistType} playlist, id:`, generatorId);
                    const generatorName = e.dataTransfer.getData('generatorName') || generatorId;
                    const newGenerator = {
                        path: `generator:${generatorId}`,
                        name: `🌟 ${generatorName}`,
                        id: crypto.randomUUID(),
                        type: 'generator',
                        generator_id: generatorId
                    };
                    files.push(newGenerator);
                    renderPlaylist(playlistType);
                    updatePlaylist(playlistType);  // Sync to backend!
                    console.log(`📋 Added generator ${generatorName} to empty ${playlistType} playlist`);
                    return false;
                }
                
                // Check if dropping a file
                const videoPath = e.dataTransfer.getData('video-path');
                if (videoPath) {
                    console.log(`🎯 DROP FILE to empty ${playlistType} playlist, path:`, videoPath);
                    const fileName = videoPath.split(/[/\\]/).pop();
                    const newVideo = {
                        path: videoPath,
                        name: fileName,
                        id: crypto.randomUUID()
                    };
                    files.push(newVideo);
                    renderPlaylist(playlistType);
                    updatePlaylist(playlistType);  // Sync to backend!
                    console.log(`📋 Added file ${fileName} to empty ${playlistType} playlist`);
                    return false;
                }
            });
        }
        
        return;
    }
    
    // Build HTML with drop zones between items
    let html = '';
    artnetFiles.forEach((video, index) => {
        // Check if this specific playlist item is currently playing (by unique frontend ID)
        const isActive = (currentArtnetItemId === video.id);
        
        // Drop zone before item
        html += `<div class="drop-zone" data-drop-index="${index}" data-playlist="artnet"></div>`;
        
        // Playlist item
        html += `
            <div class="playlist-item ${isActive ? 'active' : ''}" 
                 data-artnet-index="${index}"
                 data-playlist="artnet"
                 draggable="true">
                <div class="playlist-item-name">${video.name}</div>
                <button class="playlist-item-remove" onclick="removeFromArtnetPlaylist(${index}); event.stopPropagation();" title="Remove from playlist">×</button>
            </div>
        `;
    });
    
    // Drop zone at the end
    html += `<div class="drop-zone" data-drop-index="${artnetFiles.length}" data-playlist="artnet"></div>`;
    
    container.innerHTML = html;
    
    // Add event handlers after rendering
    let isDragging = false;
    
    // Playlist item handlers (hover, click and dragstart)
    container.querySelectorAll('.playlist-item').forEach((item) => {
        const index = parseInt(item.dataset.artnetIndex);
        let hoverTimer = null;
        
        // Hover handler - show effects/params after 1s without switching
        item.addEventListener('mouseenter', () => {
            // Clear any existing timer
            if (hoverTimer) {
                clearTimeout(hoverTimer);
            }
            
            // Start new timer (1 second)
            hoverTimer = setTimeout(async () => {
                const artnetItem = artnetFiles[index];
                
                // Check if item still exists (might have been removed)
                if (!artnetItem) {
                    return;
                }
                
                // Load effects/parameters without switching video
                if (artnetItem.type === 'generator' && artnetItem.generator_id) {
                    // Load generator parameters
                    console.log(`👁️ Hovering generator: ${artnetItem.generator_id}`);
                    
                    // Use the item's UUID directly from the playlist
                    selectedClipId = artnetItem.id;
                    console.log(`🎯 Using artnet generator clip UUID from playlist: ${selectedClipId}`);
                    
                    selectedClipPath = artnetItem.path;
                    window.currentGeneratorId = artnetItem.generator_id;
                    window.currentGeneratorParams = artnetItem.parameters || {};
                    window.currentGeneratorMeta = artnetItem;
                    
                    await refreshClipEffects();
                    
                    // Get generator metadata and show parameters
                    const generator = availableGenerators.find(g => g.id === artnetItem.generator_id);
                    if (generator) {
                        // Get parameter metadata from API
                        const paramsResponse = await fetch(`${API_BASE}/api/plugins/${artnetItem.generator_id}/parameters`);
                        const paramsData = await paramsResponse.json();
                        
                        // Store parameter definitions (array) for rendering
                        window.currentGeneratorParameters = paramsData.parameters || [];
                        
                        // Store current values (object) for display
                        const params = {};
                        if (paramsData.parameters) {
                            paramsData.parameters.forEach(param => {
                                params[param.name] = artnetItem.parameters?.[param.name] ?? param.default;
                            });
                        }
                        window.currentGeneratorParams = params;
                        
                        // Show parameters (pass metadata array)
                        displayGeneratorParameters(artnetItem.generator_id, paramsData.parameters || []);
                    }
                } else {
                    // Regular video - load effects
                    selectedClipPath = artnetItem.path;
                    selectedClipId = artnetItem.id; // Use UUID from playlist
                    window.currentGeneratorId = null;
                    window.currentGeneratorParams = null;
                    window.currentGeneratorMeta = null;
                    console.log(`🎯 Using artnet video clip UUID from playlist: ${selectedClipId}`);
                    await refreshClipEffects();
                }
            }, 1000);
        });
        
        item.addEventListener('mouseleave', () => {
            // Clear hover timer when leaving
            if (hoverTimer) {
                clearTimeout(hoverTimer);
                hoverTimer = null;
            }
        });
        
        // Click handler - abspielen UND Effekte anzeigen
        item.addEventListener('click', async (e) => {
            if (!isDragging && !e.target.classList.contains('playlist-item-remove')) {
                // Clear hover timer
                if (hoverTimer) {
                    clearTimeout(hoverTimer);
                    hoverTimer = null;
                }
                
                const artnetItem = artnetFiles[index];
                currentArtnetItemId = artnetItem.id; // Store which item is playing
                
                if (artnetItem.type === 'generator' && artnetItem.generator_id) {
                    await loadGeneratorClip(artnetItem.generator_id, 'artnet', artnetItem.id);
                } else {
                    await loadArtnetFile(artnetItem.path, artnetItem.id);
                }
            }
        });
        
        // Dragstart
        item.addEventListener('dragstart', (e) => {
            isDragging = true;
            draggedIndex = index;
            draggedPlaylist = 'artnet';
            item.style.opacity = '0.5';
            e.dataTransfer.effectAllowed = 'all';
            e.dataTransfer.setData('text/plain', index.toString());
            e.dataTransfer.setData('application/x-playlist-item', index.toString());
            console.log('🎯 ARTNET DRAGSTART: draggedIndex =', draggedIndex);
        });
        
        // Dragend
        item.addEventListener('dragend', (e) => {
            console.log('🎯 ARTNET DRAGEND');
            // Delay cleanup to allow drop event to fire first
            setTimeout(() => {
                item.style.opacity = '1';
                container.querySelectorAll('.drop-zone').forEach(zone => zone.classList.remove('drag-over'));
                isDragging = false;
                draggedIndex = null;
                draggedPlaylist = null;
            }, 50);
        });
    });
    
    // Drop zone handlers
    container.querySelectorAll('.drop-zone').forEach((zone) => {
        
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.dataTransfer) {
                // Always allow copy for external drops (generators/files)
                e.dataTransfer.dropEffect = 'copy';
            }
            zone.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', (e) => {
            zone.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            e._handledByDropZone = true; // Flag for container handler
            zone.classList.remove('drag-over');
            
            const dropIndex = parseInt(zone.dataset.dropIndex);
            
            // Check if dropping a generator from sources
            const generatorId = e.dataTransfer.getData('generatorId');
            if (generatorId) {
                console.log('🌟 ARTNET DROP GENERATOR at index:', dropIndex, 'id:', generatorId);
                const generatorName = e.dataTransfer.getData('generatorName') || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId
                };
                artnetFiles.splice(dropIndex, 0, newGenerator);
                console.log(`📋 Added generator ${generatorName} at position ${dropIndex}`);
                
                // Delay render to allow event to finish propagating
                setTimeout(() => renderArtnetPlaylist(), 0);
                return false;
            }
            
            // Check if dropping a file from file browser
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                console.log('🎯 ARTNET DROP FILE from browser at index:', dropIndex, 'path:', videoPath);
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: crypto.randomUUID() // Unique ID that becomes clip_id
                };
                artnetFiles.splice(dropIndex, 0, newVideo);
                console.log(`📋 Added file ${fileName} at position ${dropIndex}`);
                
                // Delay render to allow event to finish propagating
                setTimeout(() => renderArtnetPlaylist(), 0);
                return false;
            }
            
            // Check if reordering within playlist
            console.log('🎯 ARTNET DROP: draggedPlaylist =', draggedPlaylist, 'draggedIndex =', draggedIndex);
            
            if (draggedPlaylist !== 'artnet' || draggedIndex === null) {
                console.log('🎯 ARTNET DROP: REJECTED - wrong playlist or null index');
                return;
            }
            
            console.log('🎯 ARTNET DROP: draggedIndex =', draggedIndex, 'dropIndex =', dropIndex);
            console.log('🎯 ARTNET DROP: artnetFiles before =', artnetFiles.map((v, i) => `${i}:${v.name}`));
            
            // Adjust drop index if dragging from before the drop position
            let adjustedDropIndex = dropIndex;
            if (draggedIndex < dropIndex) {
                adjustedDropIndex--;
            }
            
            if (draggedIndex !== adjustedDropIndex) {
                const [movedItem] = artnetFiles.splice(draggedIndex, 1);
                artnetFiles.splice(adjustedDropIndex, 0, movedItem);
                renderArtnetPlaylist();
            }
            
            return false;
        });
    });
    
    // Note: Container-level drop handler is now registered in setupPlaylistContainerDropHandlers()
    // called once during init to prevent multiple handler registrations
    
    // Sync playlist to player after rendering
    updateArtnetPlaylist().catch(err => console.error('Failed to sync artnet playlist:', err));
}

// Load Art-Net video file WITHOUT adding to playlist (used for playlist clicks)
window.loadArtnetFile = async function(videoPath, clipId = null) {
    try {
        // NEW: Use unified API
        const response = await fetch(`${API_BASE}/api/player/artnet/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: videoPath,
                clip_id: clipId  // Frontend-provided UUID
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentArtnet = videoPath.replace(/^[\\\/]+/, '');
            renderArtnetPlaylist();
            
            // NEW: Store clip ID and path - use frontend clipId (UUID) instead of backend response
            selectedClipId = clipId || data.clip_id;
            console.log(`🆔 Artnet clip ID: frontend=${clipId}, backend=${data.clip_id}, using=${selectedClipId}`);
            selectedClipPath = videoPath;
            selectedClipPlayerType = 'artnet';
            
            // Clear generator state (this is a regular video)
            window.currentGeneratorId = null;
            window.currentGeneratorParams = null;
            window.currentGeneratorMeta = null;
            
            console.log('✅ Art-Net video loaded with Clip-ID:', selectedClipId);
            await refreshClipEffects();
        } else {
            showToast(`Failed to load Art-Net video: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error loading Art-Net video:', error);
        showToast('Error loading Art-Net video', 'error');
    }
};

// Load Art-Net video and ADD to playlist (used for file browser drops)
window.loadArtnetVideo = async function(videoPath) {
    try {
        const response = await fetch(`${API_BASE}/api/player/artnet/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentArtnet = videoPath.replace(/^[\\\/]+/, '');
            
            // Always add to playlist (allow duplicates)
            const filename = videoPath.split('/').pop();
            const folder = videoPath.includes('/') ? videoPath.split('/')[0] : 'root';
            artnetFiles.push({
                filename: filename,
                path: videoPath,
                folder: folder,
                name: filename,
                id: crypto.randomUUID() // Unique ID for each entry
            });
            
            renderArtnetPlaylist();
        } else {
            showToast(`Failed to load Art-Net video: ${data.message}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error loading Art-Net video:', error);
        showToast('Error loading Art-Net video', 'error');
    }
};

window.refreshArtnetPlaylist = async function() {
    await loadArtnetPlaylist();
};

window.removeFromArtnetPlaylist = async function(index) {
    const video = artnetFiles[index];
    const wasCurrentlyPlaying = (currentArtnet === video.path);
    
    artnetFiles.splice(index, 1);
    
    // If removed video was current, load next or stop
    if (wasCurrentlyPlaying) {
        currentArtnet = null;
        selectedClipId = null;
        selectedClipPath = null;
        window.currentGeneratorId = null;
        window.currentGeneratorParams = null;
        window.currentGeneratorMeta = null;
        
        // Check if there are more clips in playlist
        if (artnetFiles.length > 0) {
            // Load next clip (stay at same index, or go to previous if was last)
            const nextIndex = Math.min(index, artnetFiles.length - 1);
            const nextItem = artnetFiles[nextIndex];
            
            console.log(`⏭️ Auto-loading next clip after removal: ${nextItem.name}`);
            
            if (nextItem.type === 'generator' && nextItem.generator_id) {
                await loadGeneratorClip(nextItem.generator_id, 'artnet', nextItem.id);
            } else {
                await loadArtnetFile(nextItem.path, nextItem.id);
            }
        } else {
            // No more clips - stop player and show black screen
            console.log('⏹️ No more clips in artnet playlist - stopping player');
            try {
                await fetch(`${API_BASE}/api/player/artnet/stop`, { method: 'POST' });
            } catch (error) {
                console.error('Error stopping artnet player:', error);
            }
            
            // Clear effects panel
            await refreshClipEffects();
        }
    }
    
    renderArtnetPlaylist();
    
    // Update server with new playlist
    await updateArtnetPlaylist();
};

function startArtnetPreviewStream() {
    const previewImg = document.getElementById('artnetPreviewImg');
    
    // Use separate Art-Net preview endpoint
    previewImg.src = `${API_BASE}/preview/artnet?t=${Date.now()}`;
    setInterval(() => {
        previewImg.src = `${API_BASE}/preview/artnet?t=${Date.now()}`;
    }, 100);
}

window.openArtnetFullscreen = function() {
    window.open('/fullscreen', 'Art-Net Fullscreen', 'width=1920,height=1080');
};

// ========================================
// ART-NET PLAYER CONTROLS (using generic functions)
// ========================================

window.playArtnet = async function() { await play('artnet'); };
window.pauseArtnet = async function() { await pause('artnet'); };
window.stopArtnet = async function() { await stop('artnet'); };
window.nextArtnet = async function() { await next('artnet'); };
window.previousArtnet = async function() { await previous('artnet'); };
window.toggleArtnetAutoplay = async function() { await toggleAutoplay('artnet'); };
window.toggleArtnetLoop = async function() { await toggleLoop('artnet'); };

// ========================================
// VIDEO FX MANAGEMENT
// ========================================

window.addEffectToVideo = async function(pluginId) {
    try {
        const response = await fetch(`${API_BASE}/api/player/effects/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            console.log('✅ Effect added to video:', pluginId);
            await refreshVideoEffects();
        } else {
            const errorMsg = data.error || data.message || 'Unknown error';
            console.error('❌ Failed to add effect:', errorMsg);
            showToast(`Failed to add effect: ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error adding effect:', error);
        showToast('Error adding effect', 'error');
    }
};

async function refreshVideoEffects() {
    try {
        const response = await fetch(`${API_BASE}/api/player/effects`);
        const data = await response.json();
        
        if (data.success) {
            videoEffects = data.effects;
            renderVideoEffects();
        }
    } catch (error) {
        console.error('❌ Error refreshing video effects:', error);
    }
}

function renderVideoEffects() {
    const container = document.getElementById('videoFxList');
    
    // Save expanded states before rerender
    const expandedStates = new Set();
    container.querySelectorAll('.effect-item.expanded').forEach(item => {
        expandedStates.add(item.id);
    });
    
    if (videoEffects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <h6>No Effects</h6>
                <p>Add effects from the left panel</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = videoEffects.map((effect, index) => 
        renderEffectItem(effect, index, 'video')
    ).join('');
    
    // Restore expanded states after rerender
    expandedStates.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.classList.add('expanded');
        }
    });
}

let clearVideoEffectsClicks = 0;
let clearVideoEffectsTimer = null;

window.clearVideoEffects = async function() {
    clearVideoEffectsClicks++;
    
    if (clearVideoEffectsClicks === 1) {
        showToast('Click again to confirm clearing all video effects', 'warning');
        clearVideoEffectsTimer = setTimeout(() => {
            clearVideoEffectsClicks = 0;
        }, 3000);
        return;
    }
    
    // Second click - clear effects
    clearTimeout(clearVideoEffectsTimer);
    clearVideoEffectsClicks = 0;
    
    try {
        const response = await fetch(`${API_BASE}/api/player/effects/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Video effects cleared', 'success');
            await refreshVideoEffects();
        }
    } catch (error) {
        console.error('❌ Error clearing effects:', error);
        showToast('Error clearing video effects', 'error');
    }
};

// ========================================
// ART-NET FX MANAGEMENT
// ========================================

window.addEffectToArtnet = async function(pluginId) {
    try {
        const response = await fetch(`${API_BASE}/api/artnet/effects/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            console.log('✅ Effect added to Art-Net:', pluginId);
            await refreshArtnetEffects();
        } else {
            const errorMsg = data.error || data.message || 'Unknown error';
            console.error('❌ Failed to add Art-Net effect:', errorMsg);
            showToast(`Failed to add effect: ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error adding Art-Net effect:', error);
        showToast('Error adding Art-Net effect', 'error');
    }
};

async function refreshArtnetEffects() {
    try {
        const response = await fetch(`${API_BASE}/api/artnet/effects`);
        const data = await response.json();
        
        if (data.success) {
            artnetEffects = data.effects || [];
            renderArtnetEffects();
        }
    } catch (error) {
        console.error('❌ Error loading Art-Net effects:', error);
        artnetEffects = [];
        renderArtnetEffects();
    }
}

function renderArtnetEffects() {
    const container = document.getElementById('artnetFxList');
    
    // Save expanded states before rerender
    const expandedStates = new Set();
    container.querySelectorAll('.effect-item.expanded').forEach(item => {
        expandedStates.add(item.id);
    });
    
    if (artnetEffects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <h6>No Effects</h6>
                <p>Add effects from the left panel</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = artnetEffects.map((effect, index) => 
        renderEffectItem(effect, index, 'artnet')
    ).join('');
    
    // Restore expanded states after rerender
    expandedStates.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.classList.add('expanded');
        }
    });
}

let clearArtnetEffectsClicks = 0;
let clearArtnetEffectsTimer = null;

window.clearArtnetEffects = async function() {
    clearArtnetEffectsClicks++;
    
    if (clearArtnetEffectsClicks === 1) {
        showToast('Click again to confirm clearing all Art-Net effects', 'warning');
        clearArtnetEffectsTimer = setTimeout(() => {
            clearArtnetEffectsClicks = 0;
        }, 3000);
        return;
    }
    
    // Second click - clear effects
    clearTimeout(clearArtnetEffectsTimer);
    clearArtnetEffectsClicks = 0;
    
    try {
        const response = await fetch(`${API_BASE}/api/artnet/effects/clear`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Art-Net effects cleared', 'success');
            await refreshArtnetEffects();
        }
    } catch (error) {
        console.error('❌ Error clearing Art-Net effects:', error);
        showToast('Error clearing Art-Net effects', 'error');
    }
};

// ========================================
// CLIP FX MANAGEMENT
// ========================================

window.addEffectToClip = async function(pluginId) {
    if (!selectedClipId || !selectedClipPlayerType) {
        showToast('No clip selected', 'warning');
        return;
    }
    
    try {
        // NEW: Unified API endpoint
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/add`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                plugin_id: pluginId
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            console.log('✅ Clip effect added:', pluginId, 'to Clip-ID:', selectedClipId);
            await refreshClipEffects();
        } else {
            const errorMsg = data.error || data.message || 'Unknown error';
            console.error('❌ Failed to add clip effect:', errorMsg);
            showToast(`Failed to add clip effect: ${errorMsg}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error adding clip effect:', error);
        showToast('Error adding clip effect', 'error');
    }
};

async function refreshClipEffects() {
    if (!selectedClipId || !selectedClipPlayerType) {
        // Clear panel if no clip selected
        const container = document.getElementById('clipFxList');
        const title = document.getElementById('clipFxTitle');
        container.innerHTML = '<div class="empty-state"><p>Select a clip to manage effects</p></div>';
        title.innerHTML = '<span class="player-icon">🎬</span> Clip FX';
        clipEffects = [];
        return;
    }
    
    try {
        // NEW: Unified API endpoint (GET instead of POST)
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects`;
        
        const response = await fetch(endpoint, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            clipEffects = data.effects || [];
            renderClipEffects();
        }
    } catch (error) {
        console.error('❌ Error refreshing clip effects:', error);
    }
}

function renderClipEffects() {
    const container = document.getElementById('clipFxList');
    const title = document.getElementById('clipFxTitle');
    
    // Update title with player icon and clip name
    let icon = selectedClipPlayerType === 'video' ? '🎬' : '🎨';
    let clipName = selectedClipPath ? selectedClipPath.split('/').pop() : 'No Clip';
    
    // If it's a generator, use generator icon and name
    if (window.currentGeneratorId && window.currentGeneratorMeta) {
        icon = '🌟';
        clipName = window.currentGeneratorMeta.name;
    }
    
    title.innerHTML = `<span class="player-icon">${icon}</span> ${clipName}`;
    
    // Save expanded states (including generator params)
    const expandedStates = new Set();
    const generatorParamsExpanded = container.querySelector('.generator-params-section.expanded') !== null;
    container.querySelectorAll('.effect-item.expanded').forEach(item => {
        expandedStates.add(item.id);
    });
    
    // Build HTML: Generator Parameters (if any) + Effects
    let html = '';
    
    // Add generator parameters section first
    html += renderGeneratorParametersSection();
    
    // Add effects section
    if (clipEffects.length === 0) {
        html += `
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <h6>No Clip Effects</h6>
                <p>Add effects from the left panel</p>
            </div>
        `;
    } else {
        html += clipEffects.map((effect, index) => 
            renderEffectItem(effect, index, 'clip')
        ).join('');
    }
    
    container.innerHTML = html;
    
    // Restore expanded states after rerender
    if (generatorParamsExpanded) {
        const paramsSection = container.querySelector('.generator-params-section');
        if (paramsSection) {
            paramsSection.classList.add('expanded');
        }
    }
    expandedStates.forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.classList.add('expanded');
        }
    });
}

let clearClipEffectsClicks = 0;
let clearClipEffectsTimer = null;

window.clearClipEffects = async function() {
    if (!selectedClip || !selectedClipPlayerType) {
        showToast('No clip selected', 'warning');
        return;
    }
    
    clearClipEffectsClicks++;
    
    if (clearClipEffectsClicks === 1) {
        showToast('Click again to confirm clearing clip effects', 'warning');
        clearClipEffectsTimer = setTimeout(() => {
            clearClipEffectsClicks = 0;
        }, 3000);
        return;
    }
    
    // Second click - clear effects
    clearTimeout(clearClipEffectsTimer);
    clearClipEffectsClicks = 0;
    
    try {
        // NEW: Unified API endpoint
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/clear`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Clip effects cleared', 'success');
            await refreshClipEffects();
        }
    } catch (error) {
        console.error('❌ Error clearing clip effects:', error);
        showToast('Error clearing clip effects', 'error');
    }
};

// ========================================
// EFFECT RENDERING
// ========================================

function renderEffectItem(effect, index, player) {
    const metadata = effect.metadata || {};
    const parameters = metadata.parameters || [];
    
    // Debug: Log effect data
    if (parameters.length === 0) {
        console.warn(`⚠️ Effect "${metadata.name || effect.plugin_id}" has no parameters:`, effect);
    }
    
    return `
        <div class="effect-item" id="${player}-effect-${index}">
            <div class="effect-header" onclick="toggleEffect('${player}', ${index}, event)">
                <div class="effect-title">
                    <span class="effect-toggle"></span>
                    <span>${metadata.name || effect.plugin_id}</span>
                </div>
                <div class="effect-actions">
                    <button class="btn btn-sm btn-danger btn-icon" onclick="event.stopPropagation(); removeEffect('${player}', ${index})">🗑️</button>
                </div>
            </div>
            <div class="effect-body">
                ${parameters.length > 0 ? 
                    parameters.map(param => renderParameterControl(param, effect.parameters[param.name], index, player)).join('') :
                    '<p class="text-muted">No configurable parameters</p>'
                }
            </div>
        </div>
    `;
}

window.toggleEffect = function(player, index, event) {
    if (event) {
        event.stopPropagation();
    }
    const element = document.getElementById(`${player}-effect-${index}`);
    if (element) {
        element.classList.toggle('expanded');
    }
};

window.removeEffect = async function(player, index) {
    try {
        let endpoint;
        let bodyData = null;
        
        if (player === 'clip') {
            // NEW: Unified API endpoint (no body needed, clip_id in URL)
            endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/${index}`;
            bodyData = null;
        } else {
            // Player effects use URL-only
            endpoint = player === 'video' 
                ? `${API_BASE}/api/player/effects/${index}`
                : `${API_BASE}/api/artnet/effects/remove/${index}`;
        }
        
        const fetchOptions = {
            method: 'DELETE'
        };
        
        if (bodyData) {
            fetchOptions.headers = { 'Content-Type': 'application/json' };
            fetchOptions.body = JSON.stringify(bodyData);
        }
        
        const response = await fetch(endpoint, fetchOptions);
        
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ ${player} effect removed:`, index);
            if (player === 'video') {
                await refreshVideoEffects();
            } else if (player === 'artnet') {
                await refreshArtnetEffects();
            } else if (player === 'clip') {
                await refreshClipEffects();
            }
        }
    } catch (error) {
        console.error(`❌ Error removing ${player} effect:`, error);
    }
};

// ========================================
// PARAMETER CONTROLS
// ========================================

function renderParameterControl(param, currentValue, effectIndex, player) {
    const value = currentValue !== undefined ? currentValue : param.default;
    const controlId = `${player}_effect_${effectIndex}_${param.name}`;
    
    const paramType = (param.type || '').toUpperCase();
    
    let control = '';
    
    switch (paramType) {
        case 'FLOAT':
        case 'INT':
            const step = paramType === 'INT' ? 1 : 0.1;
            control = `
                <div class="parameter-control">
                    <div class="parameter-label">
                        <label for="${controlId}">${param.name}</label>
                        <span class="parameter-value" id="${controlId}_value">${value}</span>
                    </div>
                    <input 
                        type="range" 
                        class="form-range" 
                        id="${controlId}"
                        min="${param.min || 0}" 
                        max="${param.max || 100}" 
                        step="${step}"
                        value="${value}"
                        oninput="updateParameter('${player}', ${effectIndex}, '${param.name}', parseFloat(this.value), '${controlId}_value')"
                    >
                </div>
            `;
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
                            onchange="updateParameter('${player}', ${effectIndex}, '${param.name}', this.checked)"
                        >
                        <label class="form-check-label" for="${controlId}">
                            ${param.name}
                        </label>
                    </div>
                </div>
            `;
            break;
            
        default:
            control = `<p class="text-warning">Unknown parameter type: ${param.type}</p>`;
    }
    
    return control;
}

// Debounce timer für Parameter-Updates
const parameterUpdateTimers = {};

window.updateParameter = async function(player, effectIndex, paramName, value, valueDisplayId = null) {
    try {
        // Sofort UI-Update für responsives Feedback
        if (valueDisplayId) {
            document.getElementById(valueDisplayId).textContent = value;
        }
        
        // Debounce: Warte 150ms nach letzter Änderung
        const timerKey = `${player}_${effectIndex}_${paramName}`;
        
        if (parameterUpdateTimers[timerKey]) {
            clearTimeout(parameterUpdateTimers[timerKey]);
        }
        
        parameterUpdateTimers[timerKey] = setTimeout(async () => {
            await sendParameterUpdate(player, effectIndex, paramName, value);
            delete parameterUpdateTimers[timerKey];
        }, 150);
        
    } catch (error) {
        console.error(`❌ Error updating ${player} parameter:`, error);
    }
};

async function sendParameterUpdate(player, effectIndex, paramName, value) {
    try {
        let endpoint;
        let body;
        let method;
        
        if (player === 'clip') {
            // NEW: Unified API endpoint (clip_id in URL, no clip_path in body)
            endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/${effectIndex}/parameter`;
            body = { 
                name: paramName, 
                value: value
            };
            method = 'PUT';
        } else if (player === 'video') {
            endpoint = `${API_BASE}/api/player/effects/${effectIndex}/parameters/${paramName}`;
            body = { value: value };
            method = 'POST';
        } else {
            endpoint = `${API_BASE}/api/artnet/effects/${effectIndex}/parameter`;
            body = { name: paramName, value: value };
            method = 'PUT';
        }
        
        const response = await fetch(endpoint, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ Updated ${player} ${paramName} = ${value}`);
        } else {
            console.error(`❌ Failed to update ${player} ${paramName}:`, data.message || data.error);
        }
    } catch (error) {
        console.error(`❌ Error sending ${player} parameter update:`, error);
    }
}

// ========================================
// FILE BROWSER
// ========================================

async function loadFileBrowser() {
    try {
        const response = await fetch(`${API_BASE}/api/files/tree`);
        const data = await response.json();
        
        if (data.success) {
            renderFileTree(data.tree);
        }
    } catch (error) {
        console.error('❌ Error loading file browser:', error);
    }
}

function renderFileTree(tree, container = null, level = 0) {
    if (!container) {
        container = document.getElementById('fileBrowser');
        container.innerHTML = '<div class="file-tree"></div>';
        container = container.querySelector('.file-tree');
    }
    
    tree.forEach(item => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'file-item';
        itemDiv.style.paddingLeft = `${level * 20 + 8}px`;
        
        if (item.type === 'folder') {
            itemDiv.innerHTML = `
                <div class="file-item-content folder" onclick="toggleFolder(this)">
                    <span class="folder-icon">📁</span>
                    <span class="file-name">${item.name}</span>
                    <span class="folder-toggle">▶</span>
                </div>
                <div class="folder-children" style="display: none;"></div>
            `;
            container.appendChild(itemDiv);
            
            // Recursively render children
            const childContainer = itemDiv.querySelector('.folder-children');
            if (item.children && item.children.length > 0) {
                renderFileTree(item.children, childContainer, level + 1);
            }
        } else {
            itemDiv.innerHTML = `
                <div class="file-item-content video" 
                     draggable="true"
                     ondragstart="startVideoDrag(event, '${item.path}')"
                     title="${item.size_human}">
                    <span class="file-icon">🎬</span>
                    <span class="file-name">${item.name}</span>
                    <span class="file-size">${item.size_human}</span>
                </div>
            `;
            container.appendChild(itemDiv);
        }
    });
}

window.toggleFolder = function(element) {
    const parent = element.parentElement;
    const children = parent.querySelector('.folder-children');
    const toggle = element.querySelector('.folder-toggle');
    
    if (children.style.display === 'none') {
        children.style.display = 'block';
        toggle.textContent = '▼';
    } else {
        children.style.display = 'none';
        toggle.textContent = '▶';
    }
};

window.startVideoDrag = function(event, videoPath) {
    event.dataTransfer.setData('video-path', videoPath);
    event.dataTransfer.effectAllowed = 'copy';
};

// ========================================
// DRAG & DROP STATE
// ========================================

let draggedIndex = null;
let draggedPlaylist = null;

// ========================================
// DRAG & DROP FOR PLAYLISTS
// ========================================

// Make playlists drop targets
document.addEventListener('DOMContentLoaded', () => {
    // Load file browser when tab is activated
    document.querySelector('[onclick*="files"]').addEventListener('click', loadFileBrowser);
    
    const videoPlaylist = document.getElementById('videoPlaylist');
    const artnetPlaylist = document.getElementById('artnetPlaylist');
    
    [videoPlaylist, artnetPlaylist].forEach(playlist => {
        playlist.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'copy';
            playlist.classList.add('drag-over');
        });
        
        playlist.addEventListener('dragleave', (e) => {
            playlist.classList.remove('drag-over');
        });
        
        playlist.addEventListener('drop', async (e) => {
            e.preventDefault();
            playlist.classList.remove('drag-over');
            
            const videoPath = e.dataTransfer.getData('video-path');
            if (!videoPath) return;
            
            const isArtnet = playlist.id === 'artnetPlaylist';
            
            if (isArtnet) {
                // Try to load - loadArtnetVideo() will handle 503 and show appropriate message
                await loadArtnetVideo(videoPath);
            } else {
                await loadVideo(videoPath);
            }
        });
    });
});

window.dragStart = function(event, effectId) {
    event.dataTransfer.setData('effect-id', effectId);
};

// ========================================
// PLAYLIST PERSISTENCE
// ========================================

window.savePlaylists = async function() {
    const name = prompt('Playlist Name:', `playlist_${new Date().toISOString().slice(0, 10)}`);
    if (!name) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/playlist/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: name,
                video_playlist: videoFiles,
                artnet_playlist: artnetFiles
            })
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`Playlists "${name}" saved (Video: ${data.video_count}, Art-Net: ${data.artnet_count})`, 'success');
        } else {
            showToast(`Failed to save playlists: ${data.message}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error saving playlists:', error);
        showToast('Error saving playlists', 'error');
    }
};

window.refreshPlaylistModal = async function() {
    try {
        // Get list of available playlists
        const response = await fetch(`${API_BASE}/api/playlists`);
        const data = await response.json();
        
        const modalBody = document.getElementById('playlistModalBody');
        
        if (data.status !== 'success' || !data.playlists || data.playlists.length === 0) {
            modalBody.innerHTML = `
                <div class="text-center">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📂</div>
                    <p>No saved playlists found</p>
                </div>
            `;
            return;
        }
        
        // Build playlist selection list
        let html = '<div class="list-group">';
        data.playlists.forEach((playlist, index) => {
            const date = new Date(playlist.created).toLocaleDateString('de-DE', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            const videoCount = playlist.video_count || 0;
            const artnetCount = playlist.artnet_count || 0;
            
            html += `
                <div class="list-group-item" 
                     style="background: var(--bg-tertiary, #333); color: var(--text-primary, #e0e0e0); border: 1px solid var(--border-color, #444); margin-bottom: 0.5rem; border-radius: 4px; padding: 0;">
                    <div class="d-flex">
                        <button type="button" 
                                class="flex-grow-1 btn text-start p-3" 
                                style="background: none; border: none; color: inherit;"
                                onclick="selectPlaylist('${playlist.name}')">
                            <div class="d-flex w-100 justify-content-between">
                                <h6 class="mb-1">${playlist.name}</h6>
                                <small>${date}</small>
                            </div>
                            <p class="mb-0">
                                <span class="badge bg-primary">Video: ${videoCount}</span>
                                <span class="badge bg-info">Art-Net: ${artnetCount}</span>
                            </p>
                        </button>
                        <button type="button" 
                                class="btn btn-danger" 
                                style="border-radius: 0 4px 4px 0; min-width: 60px;"
                                onclick="deletePlaylist('${playlist.name}', event)"
                                title="Playlist löschen">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        modalBody.innerHTML = html;
        
    } catch (error) {
        console.error('❌ Error refreshing playlists:', error);
        showToast('Error loading playlists', 'error');
    }
};

window.loadPlaylists = async function() {
    try {
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('playlistModal'));
        modal.show();
        
        // Load playlist list
        await refreshPlaylistModal();
        
    } catch (error) {
        console.error('❌ Error loading playlists:', error);
        showToast('Error loading playlists', 'error');
        bootstrap.Modal.getInstance(document.getElementById('playlistModal'))?.hide();
    }
};

window.selectPlaylist = async function(playlistName) {
    try {
        console.log('🎯 Loading playlist:', playlistName);
        
        // Load the playlist
        const loadResponse = await fetch(`${API_BASE}/api/playlist/load/${playlistName}`);
        const loadData = await loadResponse.json();
        
        console.log('🎯 Playlist data received:', loadData);
        
        if (loaddata.success) {
            // Load both playlists
            videoFiles = loadData.playlist.video_playlist || loadData.playlist.videos || [];
            artnetFiles = loadData.playlist.artnet_playlist || [];
            
            console.log('🎯 Video files:', videoFiles.length);
            console.log('🎯 Art-Net files:', artnetFiles.length);
            
            renderVideoPlaylist();
            renderArtnetPlaylist();
            
            showToast(`Playlists "${playlistName}" loaded (Video: ${videoFiles.length}, Art-Net: ${artnetFiles.length})`, 'success');
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('playlistModal')).hide();
        } else {
            showToast(`Failed to load playlists: ${loadData.message}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error selecting playlist:', error);
        showToast('Error loading playlist', 'error');
    }
};

window.deletePlaylist = async function(playlistName, event) {
    event.stopPropagation(); // Prevent triggering the load action
    
    // Change button text to confirm
    const button = event.target;
    const originalText = button.innerHTML;
    const originalOnclick = button.onclick;
    
    button.innerHTML = '✓ Confirm';
    button.classList.remove('btn-danger');
    button.classList.add('btn-warning');
    
    // Reset after 3 seconds
    const resetTimer = setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('btn-warning');
        button.classList.add('btn-danger');
        button.onclick = originalOnclick;
    }, 3000);
    
    // If clicked again within 3 seconds, actually delete
    button.onclick = async (e) => {
        e.stopPropagation();
        clearTimeout(resetTimer);
        
        try {
            const response = await fetch(`${API_BASE}/api/playlist/delete/${playlistName}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                showToast(`Playlist "${playlistName}" gelöscht`, 'success');
                // Refresh the playlist list without closing modal
                await refreshPlaylistModal();
            } else {
                showToast(`Fehler beim Löschen: ${data.message}`, 'error');
                // Reset button on error
                button.innerHTML = originalText;
                button.classList.remove('btn-warning');
                button.classList.add('btn-danger');
                button.onclick = originalOnclick;
            }
        } catch (error) {
            console.error('❌ Error deleting playlist:', error);
            showToast('Fehler beim Löschen der Playlist', 'error');
            // Reset button on error
            button.innerHTML = originalText;
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
            button.onclick = originalOnclick;
        }
    };
};

// ========================================
// TRANSITION MENU
// ========================================

window.toggleTransitionMenu = function(player) {
    const panel = document.getElementById(`${player}TransitionPanel`);
    panel.classList.toggle('active');
};

window.closeTransitionMenu = function(player) {
    const panel = document.getElementById(`${player}TransitionPanel`);
    panel.classList.remove('active');
};

window.toggleTransitions = function(player, enabled) {
    const config = player === 'video' ? videoTransitionConfig : artnetTransitionConfig;
    config.enabled = enabled;
    
    const settings = document.getElementById(`${player}TransitionSettings`);
    if (enabled) {
        settings.classList.remove('disabled');
        showToast(`${player === 'video' ? 'Video' : 'Art-Net'} Transitions enabled`, 'success');
    } else {
        settings.classList.add('disabled');
        showToast(`${player === 'video' ? 'Video' : 'Art-Net'} Transitions disabled`, 'info');
    }
    
    // Send to backend
    updateTransitionConfig(player);
};

window.updateTransition = function(player) {
    const config = player === 'video' ? videoTransitionConfig : artnetTransitionConfig;
    
    const effectSelect = document.getElementById(`${player}TransitionEffect`);
    const durationSlider = document.getElementById(`${player}TransitionDuration`);
    const easingSelect = document.getElementById(`${player}TransitionEasing`);
    const durationValue = document.getElementById(`${player}DurationValue`);
    
    config.effect = effectSelect.value;
    config.duration = parseFloat(durationSlider.value);
    config.easing = easingSelect.value;
    
    // Update duration display
    durationValue.textContent = config.duration.toFixed(1) + 's';
    
    // Send to backend
    updateTransitionConfig(player);
};

async function updateTransitionConfig(player) {
    const config = player === 'video' ? videoTransitionConfig : artnetTransitionConfig;
    const endpoint = player === 'video' 
        ? `${API_BASE}/api/video/transition/config`
        : `${API_BASE}/api/artnet/transition/config`;
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ ${player} transition config updated:`, config);
        }
    } catch (error) {
        console.error(`❌ Error updating ${player} transition config:`, error);
    }
}

// ========================================
// SESSION SNAPSHOT MANAGEMENT
// ========================================

window.saveSnapshot = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/session/snapshot`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        if (data.success) {
            showToast(`📸 Snapshot created: ${data.filename}`, 'success');
        } else {
            showToast(`Failed to create snapshot: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error creating snapshot:', error);
        showToast('Error creating snapshot', 'error');
    }
};

window.refreshSnapshotModal = async function() {
    try {
        // Get list of available snapshots
        const response = await fetch(`${API_BASE}/api/session/snapshots`);
        const data = await response.json();
        
        const modalBody = document.getElementById('snapshotModalBody');
        
        if (!data.success || !data.snapshots || data.snapshots.length === 0) {
            modalBody.innerHTML = `
                <div class="text-center">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📸</div>
                    <p>No snapshots found</p>
                    <p class="text-muted small">Create a snapshot to save the current session state</p>
                </div>
            `;
            return;
        }
        
        // Build snapshot selection list
        let html = '<div class="list-group">';
        data.snapshots.forEach((snapshot, index) => {
            const date = new Date(snapshot.created).toLocaleDateString('de-DE', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            const videoCount = snapshot.video_count || 0;
            const artnetCount = snapshot.artnet_count || 0;
            const sizeKB = (snapshot.size / 1024).toFixed(1);
            
            html += `
                <div class="list-group-item" 
                     style="background: var(--bg-tertiary, #333); color: var(--text-primary, #e0e0e0); border: 1px solid var(--border-color, #444); margin-bottom: 0.5rem; border-radius: 4px; padding: 0;">
                    <div class="d-flex">
                        <button type="button" 
                                class="flex-grow-1 btn text-start p-3" 
                                style="background: none; border: none; color: inherit;"
                                onclick="selectSnapshot('${snapshot.filename}')">
                            <div class="d-flex w-100 justify-content-between align-items-start">
                                <div>
                                    <h6 class="mb-1">📸 ${snapshot.filename}</h6>
                                    <small class="text-muted">${date}</small>
                                </div>
                            </div>
                            <p class="mb-0 mt-2">
                                <span class="badge bg-primary">Video: ${videoCount}</span>
                                <span class="badge bg-info">Art-Net: ${artnetCount}</span>
                                <span class="badge bg-secondary">${sizeKB} KB</span>
                            </p>
                        </button>
                        <button type="button" 
                                class="btn btn-danger" 
                                style="border-radius: 0 4px 4px 0; min-width: 60px;"
                                onclick="deleteSnapshot('${snapshot.filename}', event)"
                                title="Snapshot löschen">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        modalBody.innerHTML = html;
        
    } catch (error) {
        console.error('❌ Error refreshing snapshots:', error);
        showToast('Error loading snapshots', 'error');
    }
};

window.loadSnapshotModal = async function() {
    try {
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('snapshotModal'));
        modal.show();
        
        // Load snapshot list
        await refreshSnapshotModal();
        
    } catch (error) {
        console.error('❌ Error loading snapshots:', error);
        showToast('Error loading snapshots', 'error');
        bootstrap.Modal.getInstance(document.getElementById('snapshotModal'))?.hide();
    }
};

window.selectSnapshot = async function(filename) {
    try {
        console.log('🔄 Restoring snapshot:', filename);
        
        // Confirm restore
        if (!confirm(`Restore snapshot "${filename}"?\n\nThis will replace the current session state and reload the page.`)) {
            return;
        }
        
        // Restore the snapshot
        const restoreResponse = await fetch(`${API_BASE}/api/session/snapshot/restore`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        const restoreData = await restoreResponse.json();
        
        if (restoreData.success) {
            showToast('✅ Snapshot restored! Reloading...', 'success');
            
            // Close modal
            bootstrap.Modal.getInstance(document.getElementById('snapshotModal'))?.hide();
            
            // Reload page after short delay
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(`Failed to restore: ${restoreData.error}`, 'error');
        }
        
    } catch (error) {
        console.error('❌ Error restoring snapshot:', error);
        showToast('Error restoring snapshot', 'error');
    }
};

window.deleteSnapshot = async function(filename, e) {
    e.stopPropagation();
    
    const button = e.currentTarget;
    const originalText = button.innerHTML;
    const originalOnclick = button.onclick;
    
    // First click: Confirm
    button.innerHTML = '✓';
    button.classList.remove('btn-danger');
    button.classList.add('btn-warning');
    button.onclick = null; // Disable further clicks
    
    // Set timeout to reset button
    const resetTimer = setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('btn-warning');
        button.classList.add('btn-danger');
        button.onclick = originalOnclick;
    }, 3000);
    
    // Wait for second click
    button.onclick = async (e) => {
        e.stopPropagation();
        clearTimeout(resetTimer);
        
        try {
            const response = await fetch(`${API_BASE}/api/session/snapshot/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            const data = await response.json();
            
            if (data.success) {
                showToast(`Snapshot "${filename}" deleted`, 'success');
                // Refresh the snapshot list without closing modal
                await refreshSnapshotModal();
            } else {
                showToast(`Error deleting: ${data.error}`, 'error');
                // Reset button on error
                button.innerHTML = originalText;
                button.classList.remove('btn-warning');
                button.classList.add('btn-danger');
                button.onclick = originalOnclick;
            }
        } catch (error) {
            console.error('❌ Error deleting snapshot:', error);
            showToast('Error deleting snapshot', 'error');
            // Reset button on error
            button.innerHTML = originalText;
            button.classList.remove('btn-warning');
            button.classList.add('btn-danger');
            button.onclick = originalOnclick;
        }
    };
};

// Cleanup
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
});
