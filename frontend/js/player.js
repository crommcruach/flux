/**
 * Controls.js - New Dual-Player Layout
 * Video + Art-Net players with FX control
 */

import { showToast, executeCommand, WEBSOCKET_ENABLED, WEBSOCKET_DEBOUNCE_MS, initWebSocket, getPlayerSocket, getEffectsSocket } from './common.js';
import { EffectsTab } from './components/effects-tab.js';
import { SourcesTab } from './components/sources-tab.js';
import { FilesTab } from './components/files-tab.js';
import { debug, loadDebugConfig } from './logger.js';

const API_BASE = '';
let availableEffects = [];
let availableGenerators = [];
let videoEffects = [];
let artnetEffects = [];
let clipEffects = [];
let availableBlendModes = []; // Dynamically loaded from backend
let updateInterval = null;

// Performance: Maps for O(1) lookups instead of Array.find() (5-10% CPU reduction)
let effectsMap = new Map();
let generatorsMap = new Map();

// ========================================
// GENERIC PLAYER CONFIGURATION
// ========================================

const playerConfigs = {
    video: {
        id: 'video',
        name: 'Video',
        apiBase: '/api/player/video',
        playlistContainerId: 'videoPlaylist',
        autoplayBtnId: 'videoAutoplayBtn',
        loopBtnId: 'videoLoopBtn',
        files: [],
        currentFile: null,
        currentItemId: null,
        currentClipIndex: -1,
        autoplay: true,
        loop: true,
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
        currentItemId: null,
        currentClipIndex: -1,
        autoplay: true,
        loop: true,
        transitionConfig: {
            enabled: false,
            effect: 'fade',
            duration: 1.0,
            easing: 'ease_in_out'
        }
    }
};

// Clip FX State (NEW: UUID-based)
let selectedClipId = null;  // UUID from clip registry
let selectedClipPath = null;  // Original path (for display)
let selectedClipPlayerType = null;  // 'video' or 'artnet'

// Layer Selection State (Layer-as-Clips Architecture)
let selectedLayerId = null;  // null = no layer selected, 0/1/2/... = layer ID
let selectedLayerClipId = null;  // clip_id of selected layer

// Master/Slave Synchronization State
let masterPlaylist = null;  // 'video' or 'artnet' or null
let sequencerModeActive = false;  // True when sequencer controls all playlists

// ========================================
// INITIALIZATION
// ========================================

// Tab component instances
let effectsTab = null;
let sourcesTab = null;
let filesTab = null;

document.addEventListener('DOMContentLoaded', () => {
    init().catch(error => {
        console.error('❌ Initialization error:', error);
    });
});

/**
 * Initialize tab components
 */
async function initializeTabComponents() {
    // Initialize Effects Tab
    effectsTab = new EffectsTab('availableEffects', 'effectsSearchContainer');
    await effectsTab.init();
    
    // Initialize Sources Tab
    sourcesTab = new SourcesTab('availableSources', 'sourcesSearchContainer');
    await sourcesTab.init();
    
    // Initialize Files Tab with 'list' mode (options: 'list', 'tree', 'button')
    // 'list' shows only flat file list without toggle button
    // enableThumbnails = true activates thumbnail display and preview modal
    filesTab = new FilesTab('fileBrowser', 'filesSearchContainer', 'list', false, true);
    await filesTab.init();
    
    debug.log('✅ Tab components initialized');
}

async function init() {
    try {
        // Load debug configuration first
        await loadDebugConfig(API_BASE);
        
        // Initialize tab components (includes search functionality)
        await initializeTabComponents();
        
        await loadAvailableEffects();
        await loadAvailableGenerators();
        await loadAvailableBlendModes();
        // initializeSearchFilters(); // DISABLED: Tab components now handle their own search
        await loadPlaylist('video');
        await loadPlaylist('artnet');
        
        // MIGRATION: Check and fix any Float IDs in loaded playlists
        let needsUpdate = false;
        
        for (const playerId of ['video', 'artnet']) {
            const files = playerConfigs[playerId].files;
            for (let i = 0; i < files.length; i++) {
                const id = files[i].id;
                const isFloatId = (typeof id === 'number') || 
                                  (typeof id === 'string' && /^\d+\.\d+$/.test(id));
                
                if (isFloatId) {
                    debug.warn(`⚠️ Migrating ${playerId} playlist item ${i} (${files[i].name}) from float ID (${id}) to UUID`);
                    const newId = crypto.randomUUID();
                    files[i].id = newId;
                    debug.log(`   └─ New UUID: ${newId}`);
                    needsUpdate = true;
                } else if (!id) {
                    debug.warn(`⚠️ ${playerId} playlist item ${i} (${files[i].name}) has no ID, generating UUID`);
                    files[i].id = crypto.randomUUID();
                    needsUpdate = true;
                } else {
                    debug.log(`✅ ${playerId} playlist item ${i} (${files[i].name}) has valid UUID: ${id}`);
                }
            }
        }
        
        // If any IDs were migrated, update backend playlists
        if (needsUpdate) {
            debug.log('🔄 Updating backend playlists with new UUIDs...');
            await updatePlaylist('video');
            await updatePlaylist('artnet');
        } else {
            debug.log('✅ All playlist items have valid UUIDs, no migration needed');
        }
        
        await refreshVideoEffects();
        await refreshArtnetEffects();
        
        // Restore master/slave state from backend
        await restoreMasterSlaveState();
        
        // Layers are now loaded per-clip when clips are loaded
        
        // Initialize WebSocket and setup event listeners BEFORE starting preview
        initWebSocket({});
        setupWebSocketListeners();
        
        // Start preview streams with staggered timing to prevent connection burst
        startPreviewStream();
        setTimeout(() => {
            startArtnetPreviewStream();
        }, 500); // 500ms delay between preview connections
        
        setupEffectDropZones();
        setupGeneratorDropZones();
        setupPlaylistContainerDropHandlers(); // Register container handlers once
        setupLayerPanelDropZone(); // Set up layer panel drop zone once
        initializeTransitionMenus(); // Initialize transition menu components
        updatePlaylistButtonStates(); // Set initial button states
        
        // REMOVED: Master/Slave sync polling - no longer needed
    } catch (error) {
        console.error('❌ Init failed:', error);
        throw error;
    }
    
    // ========================================
    // WEBSOCKET EVENT LISTENERS (Real-time Updates)
    // ========================================
    function setupWebSocketListeners() {
        const playerSocket = getPlayerSocket();
        if (!playerSocket) {
            console.warn('⚠️ PlayerSocket not available, skipping WebSocket listeners');
            return;
        }
        
        // Listen for playlist changes (REPLACES playlist polling)
        playerSocket.on('playlist.changed', (data) => {
            debug.log(`📋 Playlist changed via WebSocket: ${data.player_id}, index: ${data.current_index}`);
            
            // Ignore if we're currently reordering (prevent race condition)
            if (window._ignorePlaylistChange) {
                debug.log(`⏭️ Ignoring playlist.changed event - manual reorder in progress`);
                return;
            }
            
            // Update current clip index immediately from WebSocket event
            const playerId = data.player_id;
            const config = playerConfigs[playerId];
            if (config) {
                const newIndex = data.current_index !== undefined ? data.current_index : -1;
                if (config.currentClipIndex !== newIndex) {
                    debug.log(`✅ [${playerId}] Active clip index updated via WebSocket: ${config.currentClipIndex} → ${newIndex}`);
                    config.currentClipIndex = newIndex;
                    renderPlaylist(playerId); // Re-render to show active state
                }
            }
            
            // Also fetch full status for file path, etc.
            updateCurrentFromPlayer(data.player_id);
        });
        
        // Listen for player status updates (REPLACES status polling for play/pause state)
        playerSocket.on('player.status', (data) => {
            debug.log(`▶️ Player status update via WebSocket:`, data);
            updatePlayerStatusUI(data);
        });
        
        // Listen for sequencer mode changes
        playerSocket.on('sequencer_mode_changed', (data) => {
            debug.log(`🎵 Sequencer mode changed via WebSocket:`, data);
            // Update sequencer mode state
            sequencerModeActive = data.enabled || false;
            // Update master playlist state
            if (data.master_playlist !== undefined) {
                masterPlaylist = data.master_playlist;
            }
            updateMasterUI();
        });
        
        // Listen for master/slave mode changes
        playerSocket.on('master_slave_changed', (data) => {
            debug.log(`👑 Master/Slave mode changed via WebSocket:`, data);
            // Update master playlist state
            if (data.master_playlist !== undefined) {
                masterPlaylist = data.master_playlist;
            }
            updateMasterUI();
        });
        
        // Listen for effect parameter changes
        const effectsSocket = getEffectsSocket();
        if (effectsSocket) {
            effectsSocket.on('effect.param.changed', (data) => {
                debug.log(`🎨 Effect parameter changed via WebSocket:`, data);
            });
            
            // Listen for effect list changes (REPLACES effect list polling)
            effectsSocket.on('effects.changed', async (data) => {
                debug.log('📡 WebSocket: effects.changed event received', data);
                
                // Refresh appropriate effect list
                if (data.player_id === 'video') {
                    await refreshVideoEffects();
                } else if (data.player_id === 'artnet') {
                    await refreshArtnetEffects();
                }
                
                // Also refresh clip effects if this was a clip effect change
                if (data.clip_id && selectedClipId === data.clip_id) {
                    await loadClipEffects(selectedClipId, selectedClipPlayerType);
                }
            });
            
            // Listen for transport position updates (REPLACES polling)
            effectsSocket.on('transport.position', (data) => {
                debug.log('📡 WebSocket: transport.position event received', data);
                
                // Only update if this is the currently selected clip
                if (data.clip_id === selectedClipId && data.player_id === selectedClipPlayerType) {
                    debug.log('🎯 Updating transport for current clip:', {
                        selectedClipId,
                        selectedClipPlayerType,
                        position: data.position
                    });
                    updateTransportPositionDisplay(data);
                } else {
                    debug.log('⏭️ Skipping transport update - not current clip:', {
                        eventClipId: data.clip_id,
                        selectedClipId,
                        eventPlayerId: data.player_id,
                        selectedPlayerType: selectedClipPlayerType
                    });
                }
            });
        }
        
        debug.log('✅ WebSocket event listeners registered');
    }
    
    /**
     * Update player UI based on status event from WebSocket
     */
    function updatePlayerStatusUI(statusData) {
        const playerId = statusData.player_id;
        const isPlaying = statusData.is_playing;
        const isPaused = statusData.is_paused;
        
        // Update play/pause button states or visual indicators
        const config = playerConfigs[playerId];
        if (config) {
            // Update internal state if needed
            debug.log(`Status update: ${playerId} - playing: ${isPlaying}, paused: ${isPaused}`);
            
            // You can add visual indicators here (e.g., highlight active player)
            // Example: Update button states, add active class, etc.
        }
    }
    
    // ========================================
    // MINIMAL UPDATE INTERVAL (WebSocket-based, no playlist polling)
    // ========================================
    
    // REMOVED: Playlist polling - now handled by WebSocket events
    // REMOVED: Effect list refresh polling - now handled by WebSocket events  
    // REMOVED: Transport position polling - now handled by WebSocket events
    
    // No more polling intervals needed!
    updateInterval = null;
}

/**
 * Update transport position display from WebSocket data
 */
function updateTransportPositionDisplay(data) {
    try {
        const { position, in_point, out_point, total_frames, fps } = data;
        
        debug.log('🎬 updateTransportPositionDisplay called:', {
            position,
            in_point,
            out_point,
            total_frames,
            fps,
            clipEffectsLength: clipEffects.length
        });
        
        // Find the transport effect in clip effects
        const transportIndex = clipEffects.findIndex(e => e.plugin_id === 'transport');
        if (transportIndex === -1) {
            debug.log('⚠️ Transport effect not found in clipEffects');
            return;
        }
        
        debug.log('✅ Found transport at index:', transportIndex);
        
        const controlId = `clip_effect_${transportIndex}_transport_position`;
        const slider = getTripleSlider(controlId);
        
        debug.log('🎚️ Slider lookup:', { controlId, sliderFound: !!slider });
        
        if (slider) {
            // Determine if we should auto-scale
            const shouldScale = total_frames && out_point === (total_frames - 1);
            debug.log('📊 Updating slider values:', { position, in_point, out_point, shouldScale });
            slider.updateValues(position, in_point, out_point, shouldScale);
            
            // Update time display
            const displayElem = document.getElementById(`${controlId}_value`);
            if (displayElem && fps) {
                const totalSeconds = Math.floor(position / fps);
                const hours = Math.floor(totalSeconds / 3600);
                const minutes = Math.floor((totalSeconds % 3600) / 60);
                const seconds = totalSeconds % 60;
                
                if (hours > 0) {
                    displayElem.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    displayElem.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
                debug.log('🕐 Time display updated:', displayElem.textContent);
            }
        } else {
            debug.log('❌ Triple slider not found for controlId:', controlId);
        }
    } catch (error) {
        console.error('❌ Failed to update transport position display:', error);
    }
}

// Update playlist button states (autoplay/loop)
function updatePlaylistButtonStates() {
    // Update video player buttons
    const videoAutoplayBtn = document.getElementById('videoAutoplayBtn');
    const videoLoopBtn = document.getElementById('videoLoopBtn');
    
    if (videoAutoplayBtn) {
        if (playerConfigs.video.autoplay) {
            videoAutoplayBtn.classList.remove('btn-outline-primary');
            videoAutoplayBtn.classList.add('btn-primary');
        } else {
            videoAutoplayBtn.classList.remove('btn-primary');
            videoAutoplayBtn.classList.add('btn-outline-primary');
        }
    }
    
    if (videoLoopBtn) {
        if (playerConfigs.video.loop) {
            videoLoopBtn.classList.remove('btn-outline-primary');
            videoLoopBtn.classList.add('btn-primary');
        } else {
            videoLoopBtn.classList.remove('btn-primary');
            videoLoopBtn.classList.add('btn-outline-primary');
        }
    }
    
    // Update artnet player buttons
    const artnetAutoplayBtn = document.getElementById('artnetAutoplayBtn');
    const artnetLoopBtn = document.getElementById('artnetLoopBtn');
    
    if (artnetAutoplayBtn) {
        if (playerConfigs.artnet.autoplay) {
            artnetAutoplayBtn.classList.remove('btn-outline-primary');
            artnetAutoplayBtn.classList.add('btn-primary');
        } else {
            artnetAutoplayBtn.classList.remove('btn-primary');
            artnetAutoplayBtn.classList.add('btn-outline-primary');
        }
    }
    
    if (artnetLoopBtn) {
        if (playerConfigs.artnet.loop) {
            artnetLoopBtn.classList.remove('btn-outline-primary');
            artnetLoopBtn.classList.add('btn-primary');
        } else {
            artnetLoopBtn.classList.remove('btn-primary');
            artnetLoopBtn.classList.add('btn-outline-primary');
        }
    }
}

// ========================================
// GENERIC UPDATE FUNCTIONS (Phase 3)
// ========================================

/**
 * Generic update function - polls player status and updates UI
 * @param {string} playerId - Player ID ('video' or 'artnet')
 */
async function updateCurrentFromPlayer(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/status`);
        const data = await response.json();
        
        if (data.success) {
            // Normalize path (remove leading slashes/backslashes)
            const newVideo = data.current_video ? data.current_video.replace(/^[\\\/]+/, '') : null;
            const normalizedCurrent = config.currentFile ? config.currentFile.replace(/^[\\\/]+/, '') : null;
            
            // Update currentItemId from backend (important for active border)
            const newClipId = data.clip_id || null;
            const newClipIndex = data.current_clip_index !== undefined ? data.current_clip_index : -1;
            const clipIdChanged = config.currentItemId !== newClipId;
            const clipIndexChanged = config.currentClipIndex !== newClipIndex;
            
            // Check what changed before updating
            const needsRender = normalizedCurrent !== newVideo || clipIdChanged || clipIndexChanged;
            
            // Debug logging for slave mode
            if (clipIndexChanged) {
                debug.log(`🔄 [${playerId}] Clip index: ${config.currentClipIndex} → ${newClipIndex}`);
            }
            
            // Always update these values
            config.currentFile = newVideo;
            config.currentItemId = newClipId;  // Update active item ID
            config.currentClipIndex = newClipIndex;  // Update clip index for active border
            
            if (needsRender) {
                if (clipIdChanged && newClipId) {
                    debug.log(`🔄 [${playerId}] Current clip changed: ${newClipId.substring(0,8)}...`);
                }
                if (clipIndexChanged) {
                    debug.log(`✅ [${playerId}] Re-rendering playlist - index changed to ${newClipIndex}`);
                }
                renderPlaylist(playerId);
            }
            
            // Update master state from backend (for Master/Slave sync)
            if (data.master_playlist !== undefined) {
                const oldMaster = masterPlaylist;
                masterPlaylist = data.master_playlist;
                if (oldMaster !== masterPlaylist) {
                    updateMasterUI();
                }
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
        debug.log('📥 Loading available effects from API...');
        const response = await fetch(`${API_BASE}/api/plugins/list`);
        const data = await response.json();
        
        debug.log('📦 API Response:', data);
        
        if (data.success) {
            // Filter effects and exclude system plugins from UI
            availableEffects = data.plugins.filter(p => 
                p.type && 
                p.type.toLowerCase() === 'effect' && 
                !p.system_plugin  // Hide system plugins from effects list
            );
            debug.log(`✅ Loaded ${availableEffects.length} effects:`, availableEffects.map(e => e.id));
            
            // Performance: Populate effectsMap for O(1) lookups
            effectsMap.clear();
            availableEffects.forEach(effect => effectsMap.set(effect.id, effect));
            
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
    
    // Tab component handles search refresh automatically
}

// ========================================
// GENERATOR LOADING
// ========================================

async function loadAvailableGenerators() {
    try {
        debug.log('📥 Loading available generators from API...');
        const response = await fetch(`${API_BASE}/api/plugins/list?type=generator`);
        const data = await response.json();
        
        debug.log('📦 Generators API Response:', data);
        
        if (data.success) {
            availableGenerators = data.plugins;
            debug.log(`✅ Loaded ${availableGenerators.length} generators:`, availableGenerators.map(g => g.id));
            
            // Performance: Populate generatorsMap for O(1) lookups
            generatorsMap.clear();
            availableGenerators.forEach(gen => generatorsMap.set(gen.id, gen));
            
            renderAvailableGenerators();
        } else {
            console.error('❌ Failed to load generators:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading generators:', error);
    }
}

async function loadAvailableBlendModes() {
    try {
        debug.log('📥 Loading available blend modes from API...');
        const response = await fetch(`${API_BASE}/api/blend-modes`);
        const data = await response.json();
        
        if (data.success) {
            availableBlendModes = data.blend_modes;
            debug.log(`✅ Loaded ${availableBlendModes.length} blend modes:`, availableBlendModes);
        } else {
            console.error('❌ Failed to load blend modes:', data.message);
            // Fallback to basic modes
            availableBlendModes = ['normal', 'multiply', 'screen', 'add', 'subtract', 'overlay'];
        }
    } catch (error) {
        console.error('❌ Error loading blend modes:', error);
        // Fallback to basic modes
        availableBlendModes = ['normal', 'multiply', 'screen', 'add', 'subtract', 'overlay'];
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
    
    // Tab component handles search refresh automatically
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
    
    // Performance: Use Map.get() instead of Array.find()
    const generator = generatorsMap.get(generatorId);
    if (generator) {
        event.dataTransfer.setData('generatorName', generator.name);
    }
    
    // Make dragged element semi-transparent
    event.target.classList.add('dragging');
    
    // Store in global var as backup (dataTransfer might not be accessible during dragover)
    window.currentDragGenerator = {
        id: generatorId,
        name: generator?.name
    };
};

// Handle drag end for generators
window.endGeneratorDrag = function(event) {
    event.target.classList.remove('dragging');
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
            panel.classList.add('drop-target');
        });
        
        panel.addEventListener('dragleave', (e) => {
            panel.classList.remove('drop-target');
        });
        
        panel.addEventListener('drop', async (e) => {
            e.preventDefault();
            panel.classList.remove('drop-target');
            
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
        clipFxPanel.classList.add('drop-target');
    });
    
    clipFxPanel.addEventListener('dragleave', (e) => {
        clipFxPanel.classList.remove('drop-target');
    });
    
    clipFxPanel.addEventListener('drop', async (e) => {
        e.preventDefault();
        clipFxPanel.classList.remove('drop-target');
        
        const effectId = e.dataTransfer.getData('effectId');
        if (effectId && selectedClipId && selectedClipPlayerType) {
            await addEffectToClip(effectId);
        }
    });
}

// Setup drop zones for Generators (to playlists)
function setupGeneratorDropZones() {
    // This function is called once on init
    // The actual drop handling is done in renderPlaylistGeneric()
    // because it rebuilds the DOM on each render
    debug.log('✅ Generator drop zones will be handled in playlist rendering');
}

// Setup container-level drop handlers (ONCE on init, not on every render!)
function setupPlaylistContainerDropHandlers() {
    const videoContainer = document.getElementById('videoPlaylist');
    const artnetContainer = document.getElementById('artnetPlaylist');
    
    // Video container dragover handler - REQUIRED for drop to work!
    videoContainer.addEventListener('dragover', (e) => {
        debug.log('🔄 DRAGOVER on videoPlaylist container');
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) {
            e.dataTransfer.dropEffect = 'copy';
        }
    });
    
    // Video container drop handler  
    videoContainer.addEventListener('drop', (e) => {
        debug.log('📥 DROP on videoPlaylist container');
        e.preventDefault();
        e.stopPropagation();
        
        // Read dataTransfer BEFORE setTimeout (it becomes unavailable after event!)
        const dropData = {
            generatorId: e.dataTransfer.getData('generatorId'),
            generatorName: e.dataTransfer.getData('generatorName'),
            filePath: e.dataTransfer.getData('file-path') || e.dataTransfer.getData('video-path'),
            fileType: e.dataTransfer.getData('file-type')
        };
        
        // Delay execution to allow child handlers to set flag first
        setTimeout(async () => {
            debug.log('⏰ VIDEO Container setTimeout executing', {
                handledFlag: e._handledByDropZone,
                emptyStateExists: !!videoContainer.querySelector('.empty-state.drop-zone'),
                targetClasses: e.target.className,
                isPlaylistItem: e.target.classList.contains('playlist-item'),
                isDropZone: e.target.classList.contains('drop-zone'),
                isEmpty: e.target.classList.contains('empty-state')
            });
            
            // Skip if already handled by drop-zone or empty-state
            if (e._handledByDropZone) {
                debug.log('⏭️ VIDEO Container: skipping - already handled by drop-zone');
                return;
            }
        
            // Check if empty-state exists - if so, let it handle drops
            if (videoContainer.querySelector('.empty-state.drop-zone')) {
                debug.log('⏭️ VIDEO Container: skipping - empty-state exists');
                return;
            }
            
            // Skip if drop is on playlist item or drop-zone
            if (e.target.classList.contains('playlist-item') || 
                e.target.closest('.playlist-item') ||
                e.target.classList.contains('drop-zone') || 
                e.target.classList.contains('empty-state')) {
                debug.log('⏭️ VIDEO Container: skipping - target is item/zone/empty');
                return;
            }
            
            debug.log('✅ VIDEO Container: Processing drop!', dropData);
            
            // Check if dropping a generator
            let generatorId = dropData.generatorId;
            if (!generatorId && window.currentDragGenerator) {
                generatorId = window.currentDragGenerator.id;
            }
            
            if (generatorId) {
                const generatorName = dropData.generatorName || window.currentDragGenerator?.name || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId,
                    parameters: {}
                };
                playerConfigs.video.files.push(newGenerator);
                
                // Update playlist to backend first (so backend knows autoplay setting)
                renderPlaylist('video');
                await updatePlaylist('video');
                
                // Autoload first generator
                if (playerConfigs.video.files.length === 1) {
                    await loadGeneratorClip(generatorId, 'video', newGenerator.id, newGenerator.parameters);
                    // Backend should auto-play if autoplay is enabled, but ensure it's playing
                    if (playerConfigs.video.autoplay) {
                        await play('video');
                        debug.log('▶️ Ensured video generator playback after drop');
                    }
                }
                debug.log('✅ Added generator to video playlist');
                return;
            }
            
            // Check if dropping a file
            const filePath = dropData.filePath;
            const fileType = dropData.fileType;
            if (filePath) {
                const fileName = filePath.split(/[/\\]/).pop();
                
                let newItem;
                // For images, create static_picture generator instead
                if (fileType === 'image') {
                    newItem = {
                        path: `generator:static_picture`,
                        name: `🖼️ ${fileName}`,
                        id: crypto.randomUUID(),
                        type: 'generator',
                        generator_id: 'static_picture',
                        parameters: {
                            image_path: filePath,
                            duration: 10
                        }
                    };
                } else {
                    // For videos, add as regular clip
                    newItem = {
                        path: filePath,
                        name: `🎬 ${fileName}`,
                        id: crypto.randomUUID(),
                        type: 'video'
                    };
                }
                playerConfigs.video.files.push(newItem);
                
                // Update playlist to backend first (so backend knows autoplay setting)
                renderPlaylist('video');
                await updatePlaylist('video');
                
                // Auto-load and auto-play first item
                if (playerConfigs.video.files.length === 1) {
                    if (fileType === 'image') {
                        await loadGeneratorClip('static_picture', 'video', newItem.id, newItem.parameters);
                    } else {
                        await loadFile('video', filePath, newItem.id, false);
                    }
                    // Backend should auto-play if autoplay is enabled, but ensure it's playing
                    if (playerConfigs.video.autoplay) {
                        await play('video');
                        debug.log('▶️ Ensured video playback after drop');
                    }
                }
                debug.log(`✅ Added ${fileType === 'image' ? 'image as generator' : 'video file'} ${fileName} to video playlist`);
            }
        }, 0); // Delayed to let child handlers set flag first
    });
    
    // ArtNet container dragover handler - REQUIRED for drop to work!
    artnetContainer.addEventListener('dragover', (e) => {
        debug.log('🔄 DRAGOVER on artnetPlaylist container');
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) {
            e.dataTransfer.dropEffect = 'copy';
        }
    });
    
    // Art-Net container drop handler
    artnetContainer.addEventListener('drop', (e) => {
        debug.log('📥 DROP on artnetPlaylist container');
        e.preventDefault();
        e.stopPropagation();
        
        // Read dataTransfer BEFORE setTimeout (it becomes unavailable after event!)
        const dropData = {
            generatorId: e.dataTransfer.getData('generatorId'),
            generatorName: e.dataTransfer.getData('generatorName'),
            filePath: e.dataTransfer.getData('file-path') || e.dataTransfer.getData('video-path'),
            fileType: e.dataTransfer.getData('file-type')
        };
        
        // Delay execution to allow child handlers to set flag first
        setTimeout(async () => {
            debug.log('⏰ ARTNET Container setTimeout executing', {
                handledFlag: e._handledByDropZone,
                emptyStateExists: !!artnetContainer.querySelector('.empty-state.drop-zone'),
                targetClasses: e.target.className,
                isPlaylistItem: e.target.classList.contains('playlist-item'),
                isDropZone: e.target.classList.contains('drop-zone'),
                isEmpty: e.target.classList.contains('empty-state')
            });
            
            // Skip if already handled by drop-zone or empty-state
            if (e._handledByDropZone) {
                debug.log('⏭️ ARTNET Container: skipping - already handled by drop-zone');
                return;
            }
        
            // Check if empty-state exists - if so, let it handle drops
            if (artnetContainer.querySelector('.empty-state.drop-zone')) {
                debug.log('⏭️ ARTNET Container: skipping - empty-state exists');
                return;
            }
            
            // Skip if drop is on playlist item or drop-zone
            if (e.target.classList.contains('playlist-item') || 
                e.target.closest('.playlist-item') ||
                e.target.classList.contains('drop-zone') || 
                e.target.classList.contains('empty-state')) {
                debug.log('⏭️ ARTNET Container: skipping - target is item/zone/empty');
                return;
            }
            
            debug.log('✅ ARTNET Container: Processing drop!', dropData);
            
            // Check if dropping a generator
            let generatorId = dropData.generatorId;
            if (!generatorId && window.currentDragGenerator) {
                generatorId = window.currentDragGenerator.id;
            }
            
            if (generatorId) {
                const generatorName = dropData.generatorName || window.currentDragGenerator?.name || generatorId;
                const newGenerator = {
                    path: `generator:${generatorId}`,
                    name: `🌟 ${generatorName}`,
                    id: crypto.randomUUID(), // Unique ID that becomes clip_id
                    type: 'generator',
                    generator_id: generatorId,
                    parameters: {}
                };
                playerConfigs.artnet.files.push(newGenerator);
                
                // Update playlist to backend first (so backend knows autoplay setting)
                renderPlaylist('artnet');
                await updatePlaylist('artnet');
                
                // Autoload first generator
                if (playerConfigs.artnet.files.length === 1) {
                    await loadGeneratorClip(generatorId, 'artnet', newGenerator.id, newGenerator.parameters);
                    // Backend should auto-play if autoplay is enabled, but ensure it's playing
                    if (playerConfigs.artnet.autoplay) {
                        await play('artnet');
                        debug.log('▶️ Ensured artnet generator playback after drop');
                    }
                }
                debug.log('✅ Added generator to artnet playlist');
                return;
            }
            
            // Check if dropping a file
            const filePath = dropData.filePath;
            const fileType = dropData.fileType;
            if (filePath) {
                const fileName = filePath.split(/[/\\]/).pop();
                
                let newItem;
                // For images, create static_picture generator instead
                if (fileType === 'image') {
                    newItem = {
                        path: `generator:static_picture`,
                        name: `🖼️ ${fileName}`,
                        id: crypto.randomUUID(),
                        type: 'generator',
                        generator_id: 'static_picture',
                        parameters: {
                            image_path: filePath,
                            duration: 10
                        }
                    };
                } else {
                    // For videos, add as regular clip
                    newItem = {
                        path: filePath,
                        name: `🎬 ${fileName}`,
                        id: crypto.randomUUID(),
                        type: 'video'
                    };
                }
                playerConfigs.artnet.files.push(newItem);
                
                // Update playlist to backend first (so backend knows autoplay setting)
                renderPlaylist('artnet');
                await updatePlaylist('artnet');
                
                // Auto-load and auto-play first item
                if (playerConfigs.artnet.files.length === 1) {
                    if (fileType === 'image') {
                        await loadGeneratorClip('static_picture', 'artnet', newItem.id, newItem.parameters);
                    } else {
                        await loadFile('artnet', filePath, newItem.id, false);
                    }
                    // Backend should auto-play if autoplay is enabled, but ensure it's playing
                    if (playerConfigs.artnet.autoplay) {
                        await play('artnet');
                        debug.log('▶️ Ensured artnet playback after drop');
                    }
                }
                debug.log(`✅ Added ${fileType === 'image' ? 'image as generator' : 'video file'} ${fileName} to artnet playlist`);
            }
        }, 0); // Delayed to let child handlers set flag first
    });
    
    debug.log('✅ Container drop handlers registered (once)');
}

// Load generator as clip into player
window.loadGeneratorClip = async function(generatorId, playerType = 'video', clipId = null, savedParameters = null) {
    try {
        // Performance: Use Map.get() instead of Array.find()
        const generator = generatorsMap.get(generatorId);
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
        
        // Merge saved parameters with defaults (saved parameters override defaults)
        const finalParams = { ...defaultParams, ...(savedParameters || {}) };
        
        debug.log('🔧 Loading generator with parameters:', finalParams);
        if (savedParameters) {
            debug.log('   ├─ Default params:', defaultParams);
            debug.log('   └─ Saved params (override):', savedParameters);
        }
        
        // Load generator as clip
        const response = await fetch(`${API_BASE}/api/player/${playerType}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                type: 'generator',
                generator_id: generatorId,
                parameters: finalParams,
                clip_id: clipId  // Frontend-provided UUID
            })
        });
        
        const data = await response.json();
        if (data.success) {
            // Clear layer selection when loading new clip
            deselectLayer();
            
            // Store clip info - use frontend clipId (UUID) instead of backend response
            selectedClipId = clipId || data.clip_id;
            debug.log(`🆔 Generator clip ID: frontend=${clipId}, backend=${data.clip_id}, using=${selectedClipId}`);
            selectedClipPath = `generator:${generatorId}`;
            selectedClipPlayerType = playerType;
            
            // Update active item ID based on player type
            if (playerType === 'video') {
                playerConfigs.video.currentItemId = clipId || data.clip_id;
            } else if (playerType === 'artnet') {
                playerConfigs.artnet.currentItemId = clipId || data.clip_id;
            }
            
            // Store generator metadata for parameter display
            window.currentGeneratorId = generatorId;
            window.currentGeneratorParams = finalParams;
            window.currentGeneratorMeta = generator;
            
            // Update parameters in playlist object so they persist
            const playlist = playerConfigs[playerType].files;
            const playlistItem = playlist.find(item => item.id === selectedClipId);
            if (playlistItem && playlistItem.type === 'generator') {
                playlistItem.parameters = finalParams;
                debug.log('💾 Saved generator parameters to playlist item:', finalParams);
            }
            
            // Set currentFile for playlist highlighting (normalize path like loadVideoFile does)
            playerConfigs[playerType].currentFile = `generator:${generatorId}`.replace(/^[\\\/]+/, '');
            renderPlaylist(playerType);
            
            showToast(`✅ Generator loaded: ${generator.name}`, 'success');
            debug.log('✅ Generator clip loaded:', data);
            
            // Start playback automatically
            try {
                await fetch(`${API_BASE}/api/player/${playerType}/play`, { method: 'POST' });
                debug.log('▶️ Auto-started generator playback');
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
    // Performance: Use Map.get() instead of Array.find()
    const generator = generatorsMap.get(generatorId);
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
    // Performance: Use Map.get() instead of Array.find()
    const generator = generatorsMap.get(window.currentGeneratorId);
    if (!generator || !parameters || parameters.length === 0) {
        return '';
    }
    
    // Build collapsible parameter section
    let html = `
        <div class="generator-params-section expanded">
            <div class="effect-header" onclick="this.parentElement.classList.toggle('expanded')">
                <div>
                    <span class="param-icon">🌟</span>
                    <strong>Generator Parameters</strong>
                </div>
                <span class="expand-icon">▼</span>
            </div>
            <div class="effect-params">
    `;
    
    parameters.forEach(param => {
        const currentValue = window.currentGeneratorParams?.[param.name] ?? param.default;
        
        html += `
            <div class="param-control">
                <label>
                    ${param.label || param.name}
                </label>
                <small>
                    ${param.description || ''}
                </small>
        `;
        
        // Render control based on parameter type
        if (param.type === 'float' || param.type === 'int') {
            const step = param.step || (param.type === 'int' ? 1 : 0.01);
            const genActualValue = (currentValue !== undefined && typeof currentValue === 'object' && currentValue._value !== undefined) ? currentValue._value : currentValue;
            
            // Use simple slider for generator parameters (not triple slider)
            html += `
                <div class="param-control-row">
                    <input type="range" 
                           id="gen-param-${param.name}"
                           min="${param.min}"
                           max="${param.max}"
                           step="${step}"
                           value="${genActualValue}"
                           class="slider"
                           oncontextmenu="resetGeneratorParameterToDefault(event, '${param.name}', ${param.default})"
                           oninput="updateGeneratorParameter('${param.name}', this.value)">
                    <span id="gen-param-${param.name}-value" class="param-value">
                        ${genActualValue}
                    </span>
                </div>
            `;
        } else if (param.type === 'bool') {
            html += `
                <label class="checkbox-label">
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
    
    // Playback controls removed - use Transport Effect plugin instead
    
    html += `
            </div>
        </div>
    `;
    
    return html;
}

/**
 * Reset generator parameter to default value on right-click
 */
window.resetGeneratorParameterToDefault = function(event, paramName, defaultValue) {
    event.preventDefault(); // Prevent context menu
    
    const slider = document.getElementById(`gen-param-${paramName}`);
    const valueDisplay = document.getElementById(`gen-param-${paramName}-value`);
    
    if (slider && valueDisplay) {
        slider.value = defaultValue;
        valueDisplay.textContent = defaultValue;
        
        // Send update to backend
        updateGeneratorParameter(paramName, defaultValue);
    }
    
    return false;
};

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
            debug.log(`✅ Generator parameter updated: ${paramName} = ${finalValue}`);
            
            // Update the generator in the playlist with new parameters (only current instance by clip ID)
            if (selectedClipId && selectedClipPlayerType) {
                const playerType = selectedClipPlayerType;
                const playlistArray = playerConfigs[playerType].files;
                
                // Find THIS specific generator instance by clip ID
                const playlistItem = playlistArray.find(item => item.id === selectedClipId);
                if (playlistItem && playlistItem.type === 'generator') {
                    if (!playlistItem.parameters) {
                        playlistItem.parameters = {};
                    }
                    playlistItem.parameters[paramName] = finalValue;
                    debug.log(`💾 Updated parameter in playlist item ${selectedClipId}: ${paramName} = ${finalValue}`);
                }
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
// VIDEO PREVIEW STREAM (MJPEG)
// ========================================

let previewFpsInterval = null;
let previewFrameCount = 0;
let previewLastFpsUpdate = Date.now();

function startPreviewStream() {
    const previewImg = document.getElementById('videoPreviewImg');
    if (!previewImg) return;
    
    // Stop existing preview
    stopPreviewStream();
    
    // Start MJPEG stream (browser handles it natively - no JavaScript interference)
    previewImg.style.display = 'block';
    previewImg.src = `${API_BASE}/api/preview/stream`;
    
    debug.log(`MJPEG preview stream started`);
}

function stopPreviewStream() {
    if (previewFpsInterval) {
        clearInterval(previewFpsInterval);
        previewFpsInterval = null;
    }
    previewFrameCount = 0;
    previewLastFpsUpdate = Date.now();
    
    const previewImg = document.getElementById('videoPreviewImg');
    if (previewImg) {
        previewImg.src = '';
    }
}

function updatePreviewFPS() {
    // FPS display removed to prevent interference with MJPEG stream rendering
}

window.openVideoFullscreen = function() {
    window.open('/fullscreen', 'Flux Fullscreen', 'width=1920,height=1080');
};

// ========================================
// ART-NET PREVIEW STREAM (WebSocket)
// ========================================

let artnetPreviewFpsInterval = null;
let artnetPreviewFrameCount = 0;
let artnetPreviewLastFpsUpdate = Date.now();

function startArtnetPreviewStream() {
    const previewImg = document.getElementById('artnetPreviewImg');
    if (!previewImg) return;
    
    // Stop existing preview
    stopArtnetPreviewStream();
    
    // Start MJPEG stream (browser handles it natively - no JavaScript interference)
    previewImg.style.display = 'block';
    previewImg.src = `${API_BASE}/api/preview/artnet/stream`;
    
    debug.log(`Art-Net MJPEG preview stream started`);
}

function stopArtnetPreviewStream() {
    if (artnetPreviewFpsInterval) {
        clearInterval(artnetPreviewFpsInterval);
        artnetPreviewFpsInterval = null;
    }
    artnetPreviewFrameCount = 0;
    artnetPreviewLastFpsUpdate = Date.now();
    
    const previewImg = document.getElementById('artnetPreviewImg');
    if (previewImg) {
        previewImg.src = '';
    }
}

function updateArtnetPreviewFPS() {
    // FPS display removed to prevent interference with MJPEG stream rendering
}

// ========================================
// GENERIC PLAYLIST MANAGEMENT
// ========================================

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
                // Handle both string paths and object entries
                let actualPath = typeof path === 'string' ? path : path.path;
                let savedId = (typeof path === 'object' && path.id) ? path.id : null;
                
                if (!actualPath) {
                    debug.warn(`Empty path in ${playerId} playlist at index`, idx);
                    return null;
                }
                
                if (actualPath.startsWith('generator:')) {
                    // Generator item
                    const generatorId = actualPath.replace('generator:', '');
                    // Performance: Use Map.get() instead of Array.find()
                    const generator = generatorsMap.get(generatorId);
                    const generatorName = generator ? generator.name : generatorId;
                    const params = (typeof path === 'object' && path.parameters) ? path.parameters : {};
                    if (Object.keys(params).length > 0) {
                        debug.log(`📦 [${playerId}] Loaded generator ${generatorId} with saved parameters:`, params);
                    }
                    return {
                        path: actualPath,
                        name: `🌟 ${generatorName}`,
                        id: savedId || crypto.randomUUID(), // Use saved UUID or generate new
                        type: 'generator',
                        generator_id: generatorId,
                        parameters: params
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
            
            // Restore autoplay/loop state (use defaults if not set)
            config.autoplay = data.autoplay !== undefined ? data.autoplay : config.autoplay;
            config.loop = data.loop !== undefined ? data.loop : config.loop;
            
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
        } else {
            // Start with empty playlist - keep default autoplay/loop settings
            config.files = [];
            
            // Update UI buttons for defaults
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
            
            // Send default settings to backend (first time setup)
            try {
                await fetch(`${API_BASE}${config.apiBase}/playlist/set`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        playlist: [],
                        autoplay: config.autoplay,
                        loop: config.loop
                    })
                });
                debug.log(`✅ ${config.name} default settings sent to backend: autoplay=${config.autoplay}, loop=${config.loop}`);
            } catch (error) {
                console.error(`Failed to send default settings for ${config.name}:`, error);
            }
        }
    } catch (error) {
        console.error(`❌ Failed to load ${playerId} playlist:`, error);
        config.files = [];
    }
    
    renderPlaylist(playerId);
    
    // Load layer counts for all clips in background (for badge display)
    loadAllClipLayerCounts(config.files);
}

// Generic render function - USES GENERIC IMPLEMENTATION
function renderPlaylist(playlistId) {
    renderPlaylistGeneric(playlistId);
}

// Generic playlist renderer - works for both video and artnet
function renderPlaylistGeneric(playlistId) {
    // Configuration per playlist
    const config = {
        video: {
            containerId: 'videoPlaylist',
            files: playerConfigs.video.files,
            currentItemId: playerConfigs.video.currentItemId,
            currentClipIndex: playerConfigs.video.currentClipIndex,
            updateFunc: () => updatePlaylist('video'),
            removeFunc: (index) => `removeFromVideoPlaylist(${index})`,
            loadFunc: async (item) => {
                // Load clip and play (called on double-click)
                playerConfigs.video.currentItemId = item.id;
                if (item.type === 'generator' && item.generator_id) {
                    await loadGeneratorClip(item.generator_id, 'video', item.id, item.parameters);
                } else {
                    await loadFile('video', item.path, item.id, false);
                }
                // Note: loadClipLayers() is only called on Ctrl+Click, not on double-click
            },
            dataAttr: 'data-video-index',
            icon: '📹'
        },
        artnet: {
            containerId: 'artnetPlaylist',
            files: playerConfigs.artnet.files,
            currentItemId: playerConfigs.artnet.currentItemId,
            currentClipIndex: playerConfigs.artnet.currentClipIndex,
            updateFunc: () => updatePlaylist('artnet'),
            removeFunc: (index) => `removeFromArtnetPlaylist(${index})`,
            loadFunc: async (item) => {
                // Load clip and play (called on double-click)
                playerConfigs.artnet.currentItemId = item.id;
                if (item.type === 'generator' && item.generator_id) {
                    await loadGeneratorClip(item.generator_id, 'artnet', item.id, item.parameters);
                } else {
                    await loadFile('artnet', item.path, item.id, false);
                }
                // Note: loadClipLayers() is only called on Ctrl+Click, not on double-click
            },
            dataAttr: 'data-artnet-index',
            icon: '🎨'
        }
    };
    
    const cfg = config[playlistId];
    if (!cfg) {
        console.error('Unknown playlist ID:', playlistId);
        return;
    }
    
    const container = document.getElementById(cfg.containerId);
    const files = cfg.files;
    
    // Empty state handling
    if (files.length === 0) {
        container.innerHTML = `
            <div class="empty-state drop-zone" data-drop-index="0" data-playlist="${playlistId}">
                <div class="empty-state-icon-large">📂</div>
                <p class="empty-state-title">Playlist leer</p>
                <small class="empty-state-subtitle">Drag & Drop aus Files Tab oder Sources</small>
            </div>
        `;
        
        // Add drop handler to empty state
        const emptyZone = container.querySelector('.empty-state.drop-zone');
        if (emptyZone) {
            debug.log(`✅ ${playlistId.toUpperCase()} empty-state drop-zone found, attaching handlers`);
            
            emptyZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (e.dataTransfer) {
                    e.dataTransfer.dropEffect = 'copy';
                }
                emptyZone.classList.add('drop-target');
            });
            
            emptyZone.addEventListener('dragleave', (e) => {
                emptyZone.classList.remove('drop-target');
            });
            
            emptyZone.addEventListener('drop', (e) => {
                e._handledByDropZone = true;
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                emptyZone.classList.remove('drop-target');
                
                const playlistType = emptyZone.dataset.playlist || playlistId;
                
                // Check if dropping a generator
                const generatorId = e.dataTransfer.getData('generatorId');
                if (generatorId) {
                    const generatorName = e.dataTransfer.getData('generatorName') || generatorId;
                    const newGenerator = {
                        path: `generator:${generatorId}`,
                        name: `🌟 ${generatorName}`,
                        id: crypto.randomUUID(),
                        type: 'generator',
                        generator_id: generatorId,
                        parameters: {}
                    };
                    files.push(newGenerator);
                    
                    // Autoload if video playlist
                    if (playlistId === 'video') {
                        loadGeneratorClip(generatorId, playlistId, newGenerator.id, newGenerator.parameters);
                    }
                    
                    setTimeout(() => {
                        renderPlaylist(playlistType);
                        cfg.updateFunc();
                    }, 0);
                    return false;
                }
                
                // Check if dropping a file
                const filePath = e.dataTransfer.getData('file-path') || e.dataTransfer.getData('video-path');
                const fileType = e.dataTransfer.getData('file-type');
                if (filePath) {
                    const fileName = filePath.split(/[/\\]/).pop();
                    
                    let newItem;
                    if (fileType === 'image') {
                        newItem = {
                            path: `generator:static_picture`,
                            name: `🖼️ ${fileName}`,
                            id: crypto.randomUUID(),
                            type: 'generator',
                            generator_id: 'static_picture',
                            parameters: {
                                image_path: filePath,
                                duration: 10
                            }
                        };
                    } else {
                        newItem = {
                            path: filePath,
                            name: `🎬 ${fileName}`,
                            id: crypto.randomUUID(),
                            type: 'video'
                        };
                    }
                    files.push(newItem);
                    
                    // Auto-load first item
                    if (files.length === 1) {
                        setTimeout(() => {
                            if (fileType === 'image') {
                                loadGeneratorClip('static_picture', playlistType, newItem.id, newItem.parameters);
                            } else {
                                loadFile(playlistType, filePath, newItem.id, false);
                            }
                        }, 50);
                    }
                    
                    setTimeout(() => {
                        renderPlaylist(playlistType);
                        cfg.updateFunc();
                    }, 0);
                    return false;
                }
            });
        }
        return;
    }
    
    // Build HTML with playlist items in horizontal row (layers now managed per-clip)
    let itemsHtml = '';
    files.forEach((item, index) => {
        // Use clip index ONLY for active state (most reliable for Master/Slave sync)
        // Fallback to clip_id only if index is not available
        const isActive = cfg.currentClipIndex >= 0 
            ? (index === cfg.currentClipIndex)
            : (cfg.currentItemId && item.id === cfg.currentItemId);
        
        // Debug: Show comparison values for ALL items when index changes
        if (cfg.currentClipIndex >= 0) {
            debug.log(`🔍 [${playlistId}] item[${index}]: ${item.name.substring(0,20)} | index=${index} vs currentClipIndex=${cfg.currentClipIndex} | isActive=${isActive}`);
        }
        
        // Debug duplicate active items
        if (isActive) {
            debug.log(`✅ [${playlistId}] Active clip: ${item.name} (id: ${item.id.substring(0,8)}...)`);
        }
        
        // Debug tooltip with UUID and index
        const debugTooltip = `Index: ${index}\nUUID: ${item.id}\nPath: ${item.path || 'N/A'}`;
        
        itemsHtml += `<div class="drop-zone" data-drop-index="${index}" data-playlist="${playlistId}"></div>`;
        
        const isFxSelected = (selectedClipId === item.id && selectedClipPlayerType === playlistId);
        
        // Truncate name for FX tab if too long
        const maxTabLength = 15;
        const tabName = item.name.length > maxTabLength 
            ? item.name.substring(0, maxTabLength) + '...' 
            : item.name;
        
        // Generate thumbnail URL if item has a path
        const thumbnailUrl = item.path ? `${API_BASE}/api/files/thumbnail/${encodeURIComponent(item.path)}` : null;
        const thumbnailStyle = thumbnailUrl 
            ? `background-image: url('${thumbnailUrl}'); background-size: cover; background-position: center;` 
            : '';
        
        itemsHtml += `
            <div class="playlist-item-wrapper ${isActive ? 'active' : ''}">
                <div class="playlist-item" 
                     ${cfg.dataAttr}="${index}"
                     data-playlist="${playlistId}"
                     data-clip-id="${item.id}"
                     draggable="true"
                     style="${thumbnailStyle}"
                     title="${debugTooltip}">
                    ${getLayerBadgeHtml(item.id)}
                    <button class="playlist-item-remove" onclick="${cfg.removeFunc(index)}; event.stopPropagation();" title="Remove from playlist">×</button>
                </div>
                <div class="playlist-item-fx-tab ${isFxSelected ? 'selected' : ''}" 
                     data-playlist="${playlistId}"
                     data-clip-id="${item.id}"
                     data-clip-index="${index}"
                     title="${item.name}">
                    <span class="fx-icon">${tabName}</span>
                </div>
            </div>
        `;
    });
    itemsHtml += `<div class="drop-zone" data-drop-index="${files.length}" data-playlist="${playlistId}"></div>`;
    
    // Render playlist items only (no player-global layer stack)
    container.innerHTML = `
        <div class="playlist-items-row">
            ${itemsHtml}
        </div>
    `;
    
    attachPlaylistItemHandlers(container, playlistId, files, cfg);
    attachPlaylistDropZoneHandlers(container, playlistId, files, cfg);
}

// Helper function for item event handlers using Event Delegation
// Performance: Instead of adding listeners to each item (15-20 per item * N items),
// we add listeners to the container once (40-60% memory reduction)
function attachPlaylistItemHandlers(container, playlistId, files, cfg) {
    // Remove old handlers if they exist (cleanup on re-render)
    if (container._playlistHandlers) {
        container._playlistHandlers.forEach(({ event, handler }) => {
            container.removeEventListener(event, handler);
        });
    }
    container._playlistHandlers = [];
    
    let isDragging = false;
    
    // FX Tab click handler - select clip for ClipFX without playing it
    const fxTabClickHandler = (e) => {
        const fxTab = e.target.closest('.playlist-item-fx-tab');
        if (!fxTab) return;
        
        e.preventDefault();
        e.stopPropagation(); // Prevent playlist item click
        
        const clipId = fxTab.getAttribute('data-clip-id');
        const index = parseInt(fxTab.getAttribute('data-clip-index'));
        const fileItem = files[index];
        
        if (!fileItem) return;
        
        // Select clip for FX editing (synchronous)
        selectedClipId = fileItem.id;
        selectedClipPath = fileItem.path;
        selectedClipPlayerType = playlistId;
        
        debug.log(`🎨 Selected clip for FX: ${fileItem.name} (${clipId})`);
        
        // Update UI immediately (sync operations first)
        // Update all FX tabs in ALL playlists to show correct selection
        document.querySelectorAll('.playlist-item-fx-tab').forEach(tab => {
            const tabClipId = tab.getAttribute('data-clip-id');
            const tabPlaylistId = tab.getAttribute('data-playlist');
            if (tabClipId === clipId && tabPlaylistId === playlistId) {
                tab.classList.add('selected');
            } else {
                tab.classList.remove('selected');
            }
        });
        
        // Switch to ClipFX tab immediately
        const clipFxTab = document.querySelector('.tab-button[data-tab="clipfx"]');
        if (clipFxTab && !clipFxTab.classList.contains('active')) {
            clipFxTab.click();
        }
        
        // Load data asynchronously (non-blocking)
        (async () => {
            try {
                // Load clip layers
                await loadClipLayers(fileItem.id);
                renderSelectedClipLayers();
                
                // Load effects/generator parameters
                if (fileItem.type === 'generator' && fileItem.generator_id) {
                    const generator = generatorsMap.get(fileItem.generator_id) || availableGenerators.find(g => g.id === fileItem.generator_id);
                    if (generator) {
                        window.currentGeneratorId = fileItem.generator_id;
                        window.currentGeneratorMeta = generator;
                        
                        const paramsResponse = await fetch(`${API_BASE}/api/plugins/${fileItem.generator_id}/parameters`);
                        const paramsData = await paramsResponse.json();
                        
                        window.currentGeneratorParameters = paramsData.parameters || [];
                        
                        const params = {};
                        if (paramsData.parameters) {
                            paramsData.parameters.forEach(param => {
                                params[param.name] = fileItem.parameters?.[param.name] ?? param.default;
                            });
                        }
                        window.currentGeneratorParams = params;
                        displayGeneratorParameters(fileItem.generator_id, paramsData.parameters || []);
                    }
                } else {
                    window.currentGeneratorId = null;
                    window.currentGeneratorParams = null;
                    window.currentGeneratorMeta = null;
                    await refreshClipEffects();
                }
            } catch (error) {
                console.error('Error loading clip FX data:', error);
            }
        })();
    };
    
    // Single click handler - delegated to container
    const clickHandler = async (e) => {
        const item = e.target.closest('.playlist-item');
        if (!item || isDragging || e.target.classList.contains('playlist-item-remove')) return;
        
        const indexAttr = item.getAttribute(cfg.dataAttr);
        const index = parseInt(indexAttr);
        const fileItem = files[index];
        if (!fileItem) return;
        
        // Select clip
        selectedClipId = fileItem.id;
        selectedClipPath = fileItem.path;
        selectedClipPlayerType = playlistId;
        
        // Always load clip layers (auto-show if layers exist)
        await loadClipLayers(fileItem.id);
        renderSelectedClipLayers();
        
        // Load effects/generator parameters
        if (fileItem.type === 'generator' && fileItem.generator_id) {
            const generator = generatorsMap.get(fileItem.generator_id) || availableGenerators.find(g => g.id === fileItem.generator_id);
            if (generator) {
                window.currentGeneratorId = fileItem.generator_id;
                window.currentGeneratorMeta = generator;
                
                const paramsResponse = await fetch(`${API_BASE}/api/plugins/${fileItem.generator_id}/parameters`);
                const paramsData = await paramsResponse.json();
                
                window.currentGeneratorParameters = paramsData.parameters || [];
                
                const params = {};
                if (paramsData.parameters) {
                    paramsData.parameters.forEach(param => {
                        params[param.name] = fileItem.parameters?.[param.name] ?? param.default;
                    });
                }
                window.currentGeneratorParams = params;
                displayGeneratorParameters(fileItem.generator_id, paramsData.parameters || []);
            }
        } else {
            window.currentGeneratorId = null;
            window.currentGeneratorParams = null;
            window.currentGeneratorMeta = null;
            await refreshClipEffects();
        }
    };
    
    // Double click handler - delegated to container
    const dblclickHandler = async (e) => {
        const item = e.target.closest('.playlist-item');
        if (!item || isDragging || e.target.classList.contains('playlist-item-remove')) return;
        
        const indexAttr = item.getAttribute(cfg.dataAttr);
        const index = parseInt(indexAttr);
        const fileItem = files[index];
        if (!fileItem) return;
        
        await cfg.loadFunc(fileItem);
    };
    
    // Drag start handler - delegated to container
    const dragstartHandler = (e) => {
        const item = e.target.closest('.playlist-item');
        if (!item) return;
        
        const indexAttr = item.getAttribute(cfg.dataAttr);
        const index = parseInt(indexAttr);
        
        isDragging = true;
        window.draggedIndex = index;
        window.draggedPlaylist = playlistId;
        item.classList.add('dragging');
        e.dataTransfer.effectAllowed = 'all';
        e.dataTransfer.setData('text/plain', index.toString());
    };
    
    // Drag end handler - delegated to container
    const dragendHandler = (e) => {
        const item = e.target.closest('.playlist-item');
        if (!item) return;
        
        setTimeout(() => {
            item.classList.remove('dragging');
            container.querySelectorAll('.drop-zone').forEach(zone => zone.classList.remove('drag-over'));
            isDragging = false;
            window.draggedIndex = null;
            window.draggedPlaylist = null;
        }, 50);
    };
    
    // Attach delegated event listeners to container
    container.addEventListener('click', fxTabClickHandler); // FX tab first (stopPropagation)
    container.addEventListener('click', clickHandler);
    container.addEventListener('dblclick', dblclickHandler);
    container.addEventListener('dragstart', dragstartHandler, true); // Use capture for drag events
    container.addEventListener('dragend', dragendHandler, true);
    
    // Store handlers for cleanup
    container._playlistHandlers = [
        { event: 'click', handler: fxTabClickHandler },
        { event: 'click', handler: clickHandler },
        { event: 'dblclick', handler: dblclickHandler },
        { event: 'dragstart', handler: dragstartHandler },
        { event: 'dragend', handler: dragendHandler }
    ];
}

// Helper function for drop zone handlers using Event Delegation
// Performance: Instead of adding 3 listeners to each drop zone (N * 3),
// we add 3 listeners to the container once (60% memory reduction for drop zones)
function attachPlaylistDropZoneHandlers(container, playlistId, files, cfg) {
    // Remove old drop zone handlers if they exist
    if (container._dropZoneHandlers) {
        container._dropZoneHandlers.forEach(({ event, handler }) => {
            container.removeEventListener(event, handler);
        });
    }
    container._dropZoneHandlers = [];
    
    // Dragover handler - delegated to container
    const dragoverHandler = (e) => {
        const zone = e.target.closest('.drop-zone');
        if (!zone) return;
        
        e.preventDefault();
        e.stopPropagation();
        if (e.dataTransfer) {
            e.dataTransfer.dropEffect = 'copy';
        }
        zone.classList.add('drag-over');
    };
    
    // Dragleave handler - delegated to container
    const dragleaveHandler = (e) => {
        const zone = e.target.closest('.drop-zone');
        if (!zone) return;
        
        zone.classList.remove('drag-over');
    };
    
    // Drop handler - delegated to container
    const dropHandler = (e) => {
        const zone = e.target.closest('.drop-zone');
        if (!zone) return;
        
        e.preventDefault();
        e.stopPropagation();
        e._handledByDropZone = true;
        zone.classList.remove('drag-over');
        
        const dropIndex = parseInt(zone.dataset.dropIndex);
        
        // Check for generator drop
        let generatorId = e.dataTransfer.getData('generatorId');
        if (!generatorId && window.currentDragGenerator) {
            generatorId = window.currentDragGenerator.id;
        }
        
        if (generatorId) {
            const generatorName = e.dataTransfer.getData('generatorName') || window.currentDragGenerator?.name || generatorId;
            const newGenerator = {
                path: `generator:${generatorId}`,
                name: `🌟 ${generatorName}`,
                id: crypto.randomUUID(),
                type: 'generator',
                generator_id: generatorId,
                parameters: {}
            };
            files.splice(dropIndex, 0, newGenerator);
            // Autoload if first item in video playlist
            if (playlistId === 'video' && dropIndex === 0 && files.length === 1) {
                setTimeout(() => loadGeneratorClip(generatorId, playlistId, newGenerator.id, newGenerator.parameters), 100);
            }
            cfg.updateFunc();
            setTimeout(() => renderPlaylist(playlistId), 0);
            return false;
        }
        
        // Check for file drop
        const filePath = e.dataTransfer.getData('file-path') || e.dataTransfer.getData('video-path');
        const fileType = e.dataTransfer.getData('file-type');
        if (filePath) {
            const fileName = filePath.split(/[/\\]/).pop();
            
            let newItem;
            if (fileType === 'image') {
                newItem = {
                    path: `generator:static_picture`,
                    name: `🖼️ ${fileName}`,
                    id: crypto.randomUUID(),
                    type: 'generator',
                    generator_id: 'static_picture',
                    parameters: {
                        image_path: filePath,
                        duration: 10
                    }
                };
            } else {
                newItem = {
                    path: filePath,
                    name: `🎬 ${fileName}`,
                    id: crypto.randomUUID(),
                    type: 'video'
                };
            }
            files.splice(dropIndex, 0, newItem);
            
            // Auto-load first item in empty playlist
            if (files.length === 1) {
                setTimeout(() => {
                    if (fileType === 'image') {
                        loadGeneratorClip('static_picture', playlistId, newItem.id, newItem.parameters);
                    } else {
                        loadFile(playlistId, filePath, newItem.id, false);
                    }
                }, 100);
            }
            
            cfg.updateFunc();
            setTimeout(() => renderPlaylist(playlistId), 0);
            return false;
        }
        
        // Check for playlist item reordering
        if (window.draggedIndex !== null && window.draggedPlaylist === playlistId) {
            const dragIndex = window.draggedIndex;
            if (dragIndex !== dropIndex) {
                const item = files.splice(dragIndex, 1)[0];
                const newIndex = dragIndex < dropIndex ? dropIndex - 1 : dropIndex;
                files.splice(newIndex, 0, item);
                
                // Set flag to ignore WebSocket playlist.changed events briefly (prevent race condition)
                window._ignorePlaylistChange = true;
                setTimeout(() => {
                    window._ignorePlaylistChange = false;
                }, 500); // Ignore events for 500ms after manual reorder
                
                cfg.updateFunc();
                setTimeout(() => renderPlaylist(playlistId), 0);
            }
            return false;
        }
    };
    
    // Attach delegated event listeners to container
    container.addEventListener('dragover', dragoverHandler);
    container.addEventListener('dragleave', dragleaveHandler);
    container.addEventListener('drop', dropHandler);
    
    // Store handlers for cleanup
    container._dropZoneHandlers = [
        { event: 'dragover', handler: dragoverHandler },
        { event: 'dragleave', handler: dragleaveHandler },
        { event: 'drop', handler: dropHandler }
    ];
}

// ========================================
// GENERIC FILE LOADING (Phase 2)
// ========================================

/**
 * Generic file loader - works for any player (video, artnet, etc.)
 * @param {string} playerId - Player ID ('video' or 'artnet')
 * @param {string} filePath - Path to the file to load
 * @param {string|null} clipId - UUID for the clip (optional, will be generated if null)
 * @param {boolean} addToPlaylist - If true, add to playlist; if false, just load
 */
window.loadFile = async function(playerId, filePath, clipId = null, addToPlaylist = false) {
    const config = playerConfigs[playerId];
    if (!config) {
        console.error(`❌ Unknown player: ${playerId}`);
        return;
    }
    
    try {
        debug.log(`📂 Loading file for ${config.name}: ${filePath} (addToPlaylist: ${addToPlaylist})`);
        
        // Call backend API to load the file
        const response = await fetch(`${API_BASE}${config.apiBase}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: filePath,
                clip_id: clipId  // Frontend-provided UUID
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Clear layer selection when loading new clip
            deselectLayer();
            
            // Update current file
            config.currentFile = filePath.replace(/^[\\\/]+/, '');
            
            // Store clip ID and path - use frontend clipId (UUID) instead of backend response
            selectedClipId = clipId || data.clip_id;
            config.currentItemId = clipId || data.clip_id;  // Update active item ID
            debug.log(`🆔 ${config.name} clip ID: frontend=${clipId}, backend=${data.clip_id}, using=${selectedClipId}`);
            selectedClipPath = filePath;
            selectedClipPlayerType = playerId;
            
            // Add to playlist if requested
            if (addToPlaylist) {
                const filename = filePath.split('/').pop();
                const folder = filePath.includes('/') ? filePath.split('/')[0] : 'root';
                const newItem = {
                    id: clipId || data.clip_id,
                    path: filePath,
                    name: filename,
                    folder: folder,
                    type: 'video'
                };
                
                config.files.push(newItem);
                debug.log(`➕ Added to ${config.name} playlist:`, newItem);
                
                // Update backend playlist
                await updatePlaylist(playerId);
            }
            
            // Render playlist to update UI
            renderPlaylist(playerId);
            
            // Clear generator state (this is a regular video file)
            window.currentGeneratorId = null;
            window.currentGeneratorParams = null;
            window.currentGeneratorMeta = null;
            
            debug.log(`✅ ${config.name} file loaded with Clip-ID:`, selectedClipId);
            await refreshClipEffects();
            
            if (addToPlaylist) {
                showToast(`✅ Added to ${config.name} playlist`, 'success');
            }
        } else {
            showToast(`❌ Failed to load file: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error(`❌ Error loading file for ${config.name}:`, error);
        showToast(`❌ Error loading file`, 'error');
    }
};

window.refreshVideoPlaylist = async function() {
    await loadPlaylist('video');
};

window.removeFromVideoPlaylist = async function(index) {
    const video = playerConfigs.video.files[index];
    const wasCurrentlyPlaying = (playerConfigs.video.currentFile === video.path);
    
    playerConfigs.video.files.splice(index, 1);
    
    // If removed video was current, load next or stop
    if (wasCurrentlyPlaying) {
        playerConfigs.video.currentFile = null;
        playerConfigs.video.currentItemId = null;
        selectedClipId = null;
        selectedClipPath = null;
        window.currentGeneratorId = null;
        window.currentGeneratorParams = null;
        window.currentGeneratorMeta = null;
        
        // Check if there are more clips in playlist
        if (playerConfigs.video.files.length > 0) {
            // Load next clip (stay at same index, or go to previous if was last)
            const nextIndex = Math.min(index, playerConfigs.video.files.length - 1);
            const nextItem = playerConfigs.video.files[nextIndex];
            
            debug.log(`⏭️ Auto-loading next clip after removal: ${nextItem.name}`);
            
            if (nextItem.type === 'generator' && nextItem.generator_id) {
                await loadGeneratorClip(nextItem.generator_id, 'video', nextItem.id, nextItem.parameters);
            } else {
                await loadFile('video', nextItem.path, nextItem.id, false);
            }
        } else {
            // No more clips - stop player and show black screen
            debug.log('⏹️ No more clips in playlist - stopping player');
            try {
                await fetch(`${API_BASE}/api/player/video/stop`, { method: 'POST' });
            } catch (error) {
                console.error('Error stopping player:', error);
            }
            
            // Clear effects panel
            await refreshClipEffects();
        }
    }
    
    renderPlaylist('video');
    
    // Update server with new playlist
    await updatePlaylist('video');
};

// ========================================
// GENERIC PLAYER CONTROLS
// ========================================

window.play = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // NEW: Hybrid command - try WebSocket first, fallback to REST
    await executeCommand(
        'player',
        'command.play',
        { player_id: playerId },
        async () => {
            // REST fallback
            await fetch(`${API_BASE}${config.apiBase}/play`, { method: 'POST' });
        }
    );
};

window.pause = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // NEW: Hybrid command - try WebSocket first, fallback to REST
    await executeCommand(
        'player',
        'command.pause',
        { player_id: playerId },
        async () => {
            // REST fallback
            await fetch(`${API_BASE}${config.apiBase}/pause`, { method: 'POST' });
        }
    );
};

window.stop = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // NEW: Hybrid command - try WebSocket first, fallback to REST
    await executeCommand(
        'player',
        'command.stop',
        { player_id: playerId },
        async () => {
            // REST fallback
            await fetch(`${API_BASE}${config.apiBase}/stop`, { method: 'POST' });
        }
    );
};

window.next = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        // NEW: Hybrid command - try WebSocket first, fallback to REST
        const result = await executeCommand(
            'player',
            'command.next',
            { player_id: playerId },
            async () => {
                // REST fallback
                const response = await fetch(`${API_BASE}${config.apiBase}/next`, { method: 'POST' });
                return await response.json();
            }
        );
        
        // Handle response (from WebSocket or REST)
        const data = result.success !== undefined ? result : { success: result };
        
        if (data.success) {
            if (data.video) config.currentFile = data.video;
            if (data.clip_id) config.currentItemId = data.clip_id;
            renderPlaylist(playerId);
            debug.log(`⏭️ Next ${config.name}:`, data.video || 'clip');
        } else {
            console.error(`Failed to load next ${config.name}:`, data.message);
        }
    } catch (error) {
        console.error(`❌ Error loading next ${config.name}:`, error);
    }
}

window.previous = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        // NEW: Hybrid command - try WebSocket first, fallback to REST
        const result = await executeCommand(
            'player',
            'command.previous',
            { player_id: playerId },
            async () => {
                // REST fallback
                const response = await fetch(`${API_BASE}${config.apiBase}/previous`, { method: 'POST' });
                return await response.json();
            }
        );
        
        // Handle response (from WebSocket or REST)
        const data = result.success !== undefined ? result : { success: result };
        
        if (data.success) {
            if (data.video) config.currentFile = data.video;
            if (data.clip_id) config.currentItemId = data.clip_id;
            renderPlaylist(playerId);
            debug.log(`⏮️ Previous ${config.name}:`, data.video || 'clip');
        } else {
            console.error(`Failed to load previous ${config.name}:`, data.message);
        }
    } catch (error) {
        console.error(`❌ Error loading previous ${config.name}:`, error);
    }
};

window.toggleAutoplay = async function(playerId) {
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
                await loadGeneratorClip(firstFile.generator_id, playerId, firstFile.id, firstFile.parameters);
            } else {
                await loadFile(playerId, firstFile.path, firstFile.id, false);
            }
            await play(playerId);
            debug.log(`🎬 ${config.name} Autoplay: Starte erstes Video`);
        }
    }
};

window.toggleLoop = async function(playerId) {
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
    
    // Update Player
    await updatePlaylist(playerId);
};

// ========================================
// MASTER/SLAVE SYNCHRONIZATION
// ========================================

async function restoreMasterSlaveState() {
    try {
        const response = await fetch(`${API_BASE}/api/player/sync_status`);
        const data = await response.json();
        
        if (data.success && data.master_playlist) {
            debug.log('👑 Restoring master/slave state:', data);
            
            // Update UI checkboxes
            const videoCheckbox = document.getElementById('videoMasterSwitch');
            const artnetCheckbox = document.getElementById('artnetMasterSwitch');
            
            if (videoCheckbox && artnetCheckbox) {
                videoCheckbox.checked = (data.master_playlist === 'video');
                artnetCheckbox.checked = (data.master_playlist === 'artnet');
                masterPlaylist = data.master_playlist;
                updateMasterUI();
                debug.log('✅ Master/slave state restored from backend');
            }
        }
    } catch (error) {
        console.error('❌ Error restoring master/slave state:', error);
    }
}

window.toggleMasterPlaylist = async function(playerId) {
    const checkbox = document.getElementById(`${playerId}MasterSwitch`);
    const enabled = checkbox.checked;
    
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/set_master`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            masterPlaylist = data.master_playlist;
            updateMasterUI();
            
            const message = enabled ? 
                `👑 ${playerId} is now Master` : 
                '🔓 Master mode disabled';
            showToast(message, 'success');
            
            debug.log(`Master/Slave status: master=${masterPlaylist}, slaves=${data.synced_slaves}`);
        } else {
            // Revert checkbox on error
            checkbox.checked = !enabled;
            showToast(`Failed to toggle master mode: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error toggling master:', error);
        checkbox.checked = !enabled;
        showToast('Failed to toggle master mode', 'error');
    }
};

function updateMasterUI() {
    // Update toggle switch states and labels for both players
    ['video', 'artnet'].forEach(playerId => {
        const checkbox = document.getElementById(`${playerId}MasterSwitch`);
        const label = document.getElementById(`${playerId}MasterLabel`);
        if (!checkbox || !label) return;
        
        if (sequencerModeActive) {
            // Sequencer mode: All playlists are slaves to sequencer
            checkbox.checked = false;
            checkbox.disabled = true;
            label.textContent = 'Slave (Sequencer)';
            label.className = 'master-label is-slave';
        } else if (masterPlaylist === playerId) {
            // This player is Master
            checkbox.checked = true;
            checkbox.disabled = false;
            label.textContent = 'Master';
            label.className = 'master-label is-master';
        } else if (masterPlaylist && masterPlaylist !== playerId) {
            // This player is Slave
            checkbox.checked = false;
            checkbox.disabled = true;
            label.textContent = 'Slave';
            label.className = 'master-label is-slave';
        } else {
            // No master, autonomous
            checkbox.checked = false;
            checkbox.disabled = false;
            label.textContent = 'Master';
            label.className = 'master-label';
        }
    });
}

// REMOVED: Master/slave sync polling - no external master changes expected
// If needed in future, implement via WebSocket events instead of polling

async function updatePlaylist(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // Get files array from playerConfigs
    const files = config.files;
    
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

window.refreshArtnetPlaylist = async function() {
    await loadPlaylist('artnet');
};

window.removeFromArtnetPlaylist = async function(index) {
    const video = playerConfigs.artnet.files[index];
    const wasCurrentlyPlaying = (playerConfigs.artnet.currentFile === video.path);
    
    playerConfigs.artnet.files.splice(index, 1);
    
    // If removed video was current, load next or stop
    if (wasCurrentlyPlaying) {
        playerConfigs.artnet.currentFile = null;
        playerConfigs.artnet.currentItemId = null;
        selectedClipId = null;
        selectedClipPath = null;
        window.currentGeneratorId = null;
        window.currentGeneratorParams = null;
        window.currentGeneratorMeta = null;
        
        // Check if there are more clips in playlist
        if (playerConfigs.artnet.files.length > 0) {
            // Load next clip (stay at same index, or go to previous if was last)
            const nextIndex = Math.min(index, playerConfigs.artnet.files.length - 1);
            const nextItem = playerConfigs.artnet.files[nextIndex];
            
            debug.log(`⏭️ Auto-loading next clip after removal: ${nextItem.name}`);
            
            if (nextItem.type === 'generator' && nextItem.generator_id) {
                await loadGeneratorClip(nextItem.generator_id, 'artnet', nextItem.id, nextItem.parameters);
            } else {
                await loadFile('artnet', nextItem.path, nextItem.id, false);
            }
        } else {
            // No more clips - stop player and show black screen
            debug.log('⏹️ No more clips in artnet playlist - stopping player');
            try {
                await fetch(`${API_BASE}/api/player/artnet/stop`, { method: 'POST' });
            } catch (error) {
                console.error('Error stopping artnet player:', error);
            }
            
            // Clear effects panel
            await refreshClipEffects();
        }
    }
    
    renderPlaylist('artnet');
    
    // Update server with new playlist
    await updatePlaylist('artnet');
};

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

// Expose WebSocket preview instances for debugging
window.getWebSocketPreview = () => websocketPreview;
window.getWebSocketArtnetPreview = () => websocketArtnetPreview;

// ========================================
// VIDEO FX MANAGEMENT
// ========================================

window.addEffectToVideo = async function(pluginId) {
    try {
        const response = await fetch(`${API_BASE}/api/player/video/effects/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            debug.log('✅ Effect added to video:', pluginId);
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
        const response = await fetch(`${API_BASE}/api/player/video/effects`);
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
        const response = await fetch(`${API_BASE}/api/player/video/effects/clear`, {
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
        const response = await fetch(`${API_BASE}/api/player/artnet/effects/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            debug.log('✅ Effect added to Art-Net:', pluginId);
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
        const response = await fetch(`${API_BASE}/api/player/artnet/effects`);
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
        const response = await fetch(`${API_BASE}/api/player/artnet/effects/clear`, {
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
    
    // Transport effect now works with generators (speed, reverse, trim, playback modes)
    
    try {
        // Layer-as-Clips Architecture: Use layer.clip_id if layer is selected
        const targetClipId = selectedLayerClipId || selectedClipId;
        const target = isLayerSelected() ? `Layer ${selectedLayerId}` : 'Clip';
        
        // NEW: Unified API endpoint
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${targetClipId}/effects/add`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                plugin_id: pluginId
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            debug.log(`✅ Effect added to ${target}:`, pluginId, 'Clip-ID:', targetClipId);
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
        // Layer-as-Clips Architecture: Use layer.clip_id if layer is selected
        const targetClipId = selectedLayerClipId || selectedClipId;
        
        // NEW: Unified API endpoint (GET instead of POST)
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${targetClipId}/effects`;
        
        const response = await fetch(endpoint, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show all effects including transport (works with generators now)
            clipEffects = data.effects || [];
            renderClipEffects();
        }
    } catch (error) {
        console.error('❌ Error refreshing clip effects:', error);
    }
}

// Update live parameters without re-rendering (for real-time updates like Transport position)
async function updateClipEffectLiveParameters() {
    if (!selectedClipId || !selectedClipPlayerType || clipEffects.length === 0) {
        return;
    }
    
    try {
        // Layer-as-Clips Architecture: Use layer.clip_id if layer is selected
        const targetClipId = selectedLayerClipId || selectedClipId;
        
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${targetClipId}/effects`;
        const response = await fetch(endpoint, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success && data.effects) {
            // Update only the live parameters without re-rendering
            data.effects.forEach((effect, index) => {
                if (effect.parameters) {
                    Object.keys(effect.parameters).forEach(paramName => {
                        const paramValue = effect.parameters[paramName];
                        const controlId = `clip_effect_${index}_${paramName}`;
                        
                        // Update triple-slider if it exists
                        const slider = getTripleSlider(controlId);
                        if (slider && typeof paramValue === 'object' && paramValue._value !== undefined) {
                            // DEBUG: Log transport position updates
                            if (paramName === 'transport_position') {
                                debug.log('🎬 Updating transport slider:', {
                                    controlId,
                                    value: paramValue._value,
                                    rangeMin: paramValue._rangeMin,
                                    rangeMax: paramValue._rangeMax,
                                    sliderExists: !!slider
                                });
                            }
                            
                            // Determine if we should auto-scale: only if rangeMax == totalFrames-1 (full content, not trimmed)
                            const shouldScale = paramValue._totalFrames && paramValue._rangeMax === (paramValue._totalFrames - 1);
                            slider.updateValues(paramValue._value, paramValue._rangeMin, paramValue._rangeMax, shouldScale);
                            
                            // Update external display
                            const displayElem = document.getElementById(`${controlId}_value`);
                            if (displayElem && paramValue._displayFormat === 'time') {
                                const fps = paramValue._fps || 30;
                                const totalSeconds = Math.floor(paramValue._value / fps);
                                const hours = Math.floor(totalSeconds / 3600);
                                const minutes = Math.floor((totalSeconds % 3600) / 60);
                                const seconds = totalSeconds % 60;
                                if (hours > 0) {
                                    displayElem.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                                } else {
                                    displayElem.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                                }
                            }
                        }
                    });
                }
            });
        }
    } catch (error) {
        // Silent fail - don't spam console with errors
    }
}

function renderClipEffects() {
    const container = document.getElementById('clipFxList');
    const title = document.getElementById('clipFxTitle');
    
    // Dynamic title based on selection (Layer-as-Clips Architecture)
    let icon, titleText;
    
    if (isLayerSelected()) {
        // Layer selected - show Layer FX
        icon = '📐';
        titleText = `Layer ${selectedLayerId} FX`;
    } else if (window.currentGeneratorId && window.currentGeneratorMeta) {
        // Generator clip
        icon = '🌟';
        titleText = `${window.currentGeneratorMeta.name} FX`;
    } else {
        // Normal clip
        icon = selectedClipPlayerType === 'video' ? '🎬' : '🎨';
        const clipName = selectedClipPath ? selectedClipPath.split('/').pop() : 'No Clip';
        titleText = `${clipName} FX`;
    }
    
    title.innerHTML = `<span class="player-icon">${icon}</span> ${titleText}`;
    
    // Save expanded states (including generator params)
    const expandedStates = new Set();
    const generatorParamsExpanded = container.querySelector('.generator-params-section.expanded') !== null;
    container.querySelectorAll('.effect-item.expanded').forEach(item => {
        expandedStates.add(item.id);
    });
    
    // Build HTML: Trim Controls + Generator Parameters (if any) + Effects
    let html = '';
    
    // Add generator parameters section
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
    if (!selectedClipId || !selectedClipPlayerType) {
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
    const isSystemPlugin = metadata.system_plugin === true;
    
    // Debug: Log effect data
    if (parameters.length === 0) {
        debug.warn(`⚠️ Effect "${metadata.name || effect.plugin_id}" has no parameters:`, effect);
    }
    
    // Debug transform specifically (verbose only)
    if (effect.plugin_id === 'transform') {
        debug.verbose(`🔍 Transform metadata.parameters (schema):`, parameters);
        debug.verbose(`🔍 Transform effect.parameters (values):`, effect.parameters);
        parameters.forEach(param => {
            debug.verbose(`  - ${param.name}: type=${param.type}, min=${param.min}, max=${param.max}, value=${effect.parameters[param.name]}`);
        });
    }
    
    const isEnabled = effect.enabled !== false; // Default: enabled if not specified
    
    return `
        <div class="effect-item ${isSystemPlugin ? 'system-plugin' : ''} ${!isEnabled ? 'effect-disabled' : ''}" id="${player}-effect-${index}">
            <div class="effect-header" onclick="toggleEffect('${player}', ${index}, event)">
                <div class="effect-title">
                    <span class="effect-toggle"></span>
                    <span>${metadata.name || effect.plugin_id}${isSystemPlugin ? ' 🔒' : ''}</span>
                </div>
                <div class="effect-actions">
                    ${!isSystemPlugin ? `
                        <span class="effect-enable-switch" onclick="toggleEffectEnabledClick('${player}', ${index}, event)">
                            <input type="checkbox" ${isEnabled ? 'checked' : ''}>
                            <span class="effect-enable-slider"></span>
                        </span>
                        <button class="btn btn-sm btn-danger btn-icon" onclick="removeEffect('${player}', ${index}, event)">🗑️</button>
                    ` : ''}
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

window.toggleEffectEnabledClick = async function(player, index, event) {
    event.stopPropagation();
    
    // Find the checkbox within the clicked element
    const switchElement = event.currentTarget;
    const checkbox = switchElement.querySelector('input[type="checkbox"]');
    if (!checkbox) return;
    
    // Toggle the checkbox
    checkbox.checked = !checkbox.checked;
    const newState = checkbox.checked;
    
    try {
        // Determine endpoint based on player type
        let endpoint;
        if (player === 'clip') {
            endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects/${index}/toggle`;
        } else if (player === 'video') {
            endpoint = `${API_BASE}/api/player/video/effects/${index}/toggle`;
        } else if (player === 'artnet') {
            endpoint = `${API_BASE}/api/player/artnet/effects/${index}/toggle`;
        }
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            debug.log(`✅ ${player} effect ${index} toggled: enabled=${data.enabled}`);
            
            // Sync checkbox state with server response
            checkbox.checked = data.enabled;
            
            // Update UI state
            const effectItem = document.getElementById(`${player}-effect-${index}`);
            if (effectItem) {
                if (data.enabled) {
                    effectItem.classList.remove('effect-disabled');
                } else {
                    effectItem.classList.add('effect-disabled');
                }
            }
            
            showToast(`Effect ${data.enabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            // Revert checkbox on error
            checkbox.checked = !newState;
            showToast(`Error: ${data.message}`, 'error');
        }
    } catch (error) {
        // Revert checkbox on error
        checkbox.checked = !newState;
        console.error(`❌ Error toggling ${player} effect:`, error);
        showToast('Error toggling effect', 'error');
    }
};

window.removeEffect = async function(player, index, e) {
    e.stopPropagation();
    
    const button = e.currentTarget;
    const originalText = button.innerHTML;
    const originalOnclick = button.onclick;
    
    // First click: Confirm
    button.innerHTML = '✓';
    button.classList.remove('btn-danger');
    button.classList.add('btn-warning');
    button.onclick = null;
    
    // Reset after 3 seconds
    const resetTimer = setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('btn-warning');
        button.classList.add('btn-danger');
        button.onclick = originalOnclick;
    }, 3000);
    
    // Second click: Execute
    button.onclick = async (e) => {
        e.stopPropagation();
        clearTimeout(resetTimer);
        
        try {
            let endpoint;
            let bodyData = null;
            
            if (player === 'clip') {
                // Layer-as-Clips Architecture: Use layer.clip_id if layer is selected
                const targetClipId = selectedLayerClipId || selectedClipId;
                endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${targetClipId}/effects/${index}`;
                bodyData = null;
            } else {
                endpoint = player === 'video' 
                    ? `${API_BASE}/api/player/video/effects/${index}`
                    : `${API_BASE}/api/player/artnet/effects/${index}`;
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
                debug.log(`✅ ${player} effect removed:`, index);
                if (player === 'video') {
                    await refreshVideoEffects();
                } else if (player === 'artnet') {
                    await refreshArtnetEffects();
                } else if (player === 'clip') {
                    await refreshClipEffects();
                }
            } else {
                showToast(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error(`❌ Error removing ${player} effect:`, error);
            showToast('Error removing effect', 'error');
        }
    };
};

// ========================================
// PARAMETER CONTROLS
// ========================================

function renderParameterControl(param, currentValue, effectIndex, player) {
    const value = currentValue !== undefined ? currentValue : param.default;
    const controlId = `${player}_effect_${effectIndex}_${param.name}`;
    
    const paramType = (param.type || '').toUpperCase();
    
    // Debug: Log if param type is missing
    if (!paramType) {
        console.warn(`⚠️ Parameter '${param.name}' has no type:`, param);
    }
    
    let control = '';
    
    switch (paramType) {
        case 'FLOAT':
        case 'INT':
            const intStep = param.step || 1;
            const intDecimals = intStep >= 1 ? 0 : (intStep >= 0.1 ? 1 : 2);
            const intDefaultValue = param.default || 0;
            const intMin = param.min || 0;
            const intMax = param.max || 100;
            
            // Restore saved range if available, otherwise use full range
            const intSavedRangeMin = currentValue !== undefined && typeof currentValue === 'object' && currentValue._rangeMin !== undefined ? currentValue._rangeMin : intMin;
            const intSavedRangeMax = currentValue !== undefined && typeof currentValue === 'object' && currentValue._rangeMax !== undefined ? currentValue._rangeMax : intMax;
            const intActualValue = (currentValue !== undefined && typeof currentValue === 'object' && currentValue._value !== undefined) ? currentValue._value : value;
            
            // Extract metadata (displayFormat, fps, totalFrames) from currentValue
            const displayFormat = (currentValue && typeof currentValue === 'object' && currentValue._displayFormat) || param.displayFormat || 'number';
            const fps = (currentValue && typeof currentValue === 'object' && currentValue._fps) || param.fps || 30;
            const totalFrames = (currentValue && typeof currentValue === 'object' && currentValue._totalFrames) || intMax;
            
            // Format display value (time or number)
            let intDisplayValue;
            
            if (displayFormat === 'time') {
                const totalSeconds = Math.floor(intActualValue / fps);
                const hours = Math.floor(totalSeconds / 3600);
                const minutes = Math.floor((totalSeconds % 3600) / 60);
                const seconds = totalSeconds % 60;
                if (hours > 0) {
                    intDisplayValue = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                } else {
                    intDisplayValue = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
            } else {
                intDisplayValue = intDecimals === 0 ? Math.round(intActualValue) : intActualValue.toFixed(intDecimals);
            }
            
            control = `
                <div class="parameter-control">
                    <div class="parameter-label">
                        <label>${param.label || param.name}</label>
                        <span class="parameter-value" id="${controlId}_value">${intDisplayValue}</span>
                    </div>
                    <div id="${controlId}" class="triple-slider-container" 
                         data-default="${intDefaultValue}" 
                         data-decimals="${intDecimals}"
                         oncontextmenu="resetParameterToDefaultTriple(event, '${player}', ${effectIndex}, '${param.name}', ${intDefaultValue}, '${controlId}', '${controlId}_value', ${intDecimals})"></div>
                </div>
            `;
            // Initialize triple-slider after DOM is updated
            setTimeout(() => {
                // Use the same metadata extraction as above (already extracted)
                
                // Helper function to update display value
                const updateDisplayValue = (val) => {
                    const displayElem = document.getElementById(`${controlId}_value`);
                    if (displayElem) {
                        if (displayFormat === 'time') {
                            const totalSeconds = Math.floor(val / fps);
                            const hours = Math.floor(totalSeconds / 3600);
                            const minutes = Math.floor((totalSeconds % 3600) / 60);
                            const seconds = totalSeconds % 60;
                            if (hours > 0) {
                                displayElem.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                            } else {
                                displayElem.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                            }
                        } else {
                            displayElem.textContent = intDecimals === 0 ? Math.round(val) : val.toFixed(intDecimals);
                        }
                    }
                };
                
                // FIX: Check if slider exists AND if its DOM container is still in document
                // If container was replaced by innerHTML, destroy old instance
                const existingSlider = getTripleSlider(controlId);
                const containerInDOM = document.getElementById(controlId);
                
                if (existingSlider && containerInDOM && existingSlider.container === containerInDOM) {
                    // Slider exists with valid DOM reference - update it
                    existingSlider.updateValues(intActualValue, intSavedRangeMin, intSavedRangeMax);
                    existingSlider.config.displayFormat = displayFormat;
                    existingSlider.config.fps = fps;
                    existingSlider.config.max = totalFrames;
                    existingSlider.updateUI();
                    // Update external display
                    updateDisplayValue(intActualValue);
                } else {
                    // Slider doesn't exist OR DOM was replaced - destroy old and create new
                    if (existingSlider) {
                        debug.verbose(`🔄 Triple-slider DOM replaced for ${controlId}, recreating slider`);
                        existingSlider.destroy();
                    }
                    
                    // Create new slider
                    initTripleSlider(controlId, {
                        min: intMin,
                        max: totalFrames,
                        value: intActualValue,
                        step: intStep,
                        showRangeHandles: true,
                        rangeMin: intSavedRangeMin,
                        rangeMax: intSavedRangeMax,
                        displayFormat: displayFormat,
                        fps: fps,
                        onChange: (newValue) => {
                            const finalValue = intDecimals === 0 ? Math.round(newValue) : newValue;
                            updateDisplayValue(finalValue);
                            updateParameter(player, effectIndex, param.name, finalValue, `${controlId}_value`);
                        },
                        onRangeChange: (rangeMin, rangeMax) => {
                            // Range changed - trigger update to save range
                            const slider = getTripleSlider(controlId);
                            if (slider) {
                                const finalValue = intDecimals === 0 ? Math.round(slider.getValue()) : slider.getValue();
                                updateDisplayValue(finalValue);
                                updateParameter(player, effectIndex, param.name, finalValue, `${controlId}_value`);
                            }
                        },
                        onDragStart: (handleType) => {
                            // Pause video only when dragging the value handle (position), not min/max
                            if (handleType === 'value' && player === 'clip' && selectedClipPlayerType) {
                                pause(selectedClipPlayerType);
                            }
                        },
                        onDragEnd: (handleType) => {
                            // Resume video only when releasing the value handle
                            if (handleType === 'value' && player === 'clip' && selectedClipPlayerType) {
                                play(selectedClipPlayerType);
                            }
                        }
                    });
                }
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
                            onchange="updateParameter('${player}', ${effectIndex}, '${param.name}', this.checked)"
                        >
                        <label class="form-check-label" for="${controlId}">
                            ${param.name}
                        </label>
                    </div>
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
                        onchange="updateParameter('${player}', ${effectIndex}, '${param.name}', this.value)"
                    >
                        ${param.options.map(opt => `<option value="${opt}" ${value === opt ? 'selected' : ''}>${opt}</option>`).join('')}
                    </select>
                </div>
            `;
            break;
            
        case 'COLOR':
            control = `
                <div class="parameter-control">
                    <label for="${controlId}" class="parameter-label">${param.name}</label>
                    <input 
                        type="color" 
                        class="form-control form-control-color" 
                        id="${controlId}"
                        value="${value || '#FFFFFF'}"
                        onchange="updateParameter('${player}', ${effectIndex}, '${param.name}', this.value)"
                    >
                </div>
            `;
            break;
            
        default:
            // Fallback: If no type is specified, try to infer from value
            if (typeof value === 'number' && param.min !== undefined && param.max !== undefined) {
                // Looks like a numeric parameter, render as slider
                console.warn(`⚠️ Parameter '${param.name}' has no type but looks numeric, rendering as FLOAT`);
                const fallbackStep = param.step || 1;
                const fallbackDecimals = fallbackStep >= 1 ? 0 : (fallbackStep >= 0.1 ? 1 : 2);
                const fallbackValue = value;
                const fallbackMin = param.min || 0;
                const fallbackMax = param.max || 100;
                
                control = `
                    <div class="parameter-control">
                        <div class="parameter-label">
                            <label>${param.label || param.name}</label>
                            <span class="parameter-value" id="${controlId}_value">${fallbackDecimals === 0 ? Math.round(fallbackValue) : fallbackValue.toFixed(fallbackDecimals)}</span>
                        </div>
                        <div id="${controlId}" class="triple-slider-container" 
                             data-default="${param.default || 0}" 
                             data-decimals="${fallbackDecimals}"
                             oncontextmenu="resetParameterToDefaultTriple(event, '${player}', ${effectIndex}, '${param.name}', ${param.default || 0}, '${controlId}', '${controlId}_value', ${fallbackDecimals})"></div>
                    </div>
                `;
                // Initialize slider
                setTimeout(() => {
                    // FIX: Check if slider exists AND if its DOM container is still in document
                    const existingSlider = getTripleSlider(controlId);
                    const containerInDOM = document.getElementById(controlId);
                    
                    if (existingSlider && containerInDOM && existingSlider.container === containerInDOM) {
                        // Slider exists with valid DOM - update it
                        existingSlider.updateValues(fallbackValue, fallbackMin, fallbackMax);
                        existingSlider.updateUI();
                    } else {
                        // Slider doesn't exist OR DOM was replaced - recreate
                        if (existingSlider) {
                            debug.verbose(`🔄 Triple-slider DOM replaced for ${controlId}, recreating slider`);
                            existingSlider.destroy();
                        }
                        
                        initTripleSlider(controlId, {
                            min: fallbackMin,
                            max: fallbackMax,
                            value: fallbackValue,
                            step: fallbackStep,
                            showRangeHandles: true,
                            rangeMin: fallbackMin,
                            rangeMax: fallbackMax,
                            onChange: (newValue) => {
                                const finalValue = fallbackDecimals === 0 ? Math.round(newValue) : newValue;
                                document.getElementById(`${controlId}_value`).textContent = fallbackDecimals === 0 ? Math.round(finalValue) : finalValue.toFixed(fallbackDecimals);
                                updateParameter(player, effectIndex, param.name, finalValue, `${controlId}_value`);
                            }
                        });
                    }
                }, 0);
            } else {
                control = `<p class="text-muted">${param.label || param.name}: ${value}</p>`;
            }
    }
    
    return control;
}

// Debounce timer für Parameter-Updates
const parameterUpdateTimers = {};

/**
 * Reset parameter to default value on right-click
 */
window.resetParameterToDefault = function(event, player, effectIndex, paramName, defaultValue, sliderId, valueDisplayId) {
    event.preventDefault(); // Prevent context menu
    
    const slider = document.getElementById(sliderId);
    const valueDisplay = document.getElementById(valueDisplayId);
    
    if (slider && valueDisplay) {
        const roundedDefault = Math.round(defaultValue);
        slider.value = roundedDefault;
        valueDisplay.textContent = roundedDefault;
        
        // Send update to backend
        updateParameter(player, effectIndex, paramName, roundedDefault, valueDisplayId);
    }
    
    return false;
};

/**
 * Reset parameter to default value on right-click for triple-slider
 */
window.resetParameterToDefaultTriple = function(event, player, effectIndex, paramName, defaultValue, controlId, valueDisplayId, decimals = 0) {
    event.preventDefault(); // Prevent context menu
    
    const tripleSlider = getTripleSlider(controlId);
    const valueDisplay = document.getElementById(valueDisplayId);
    
    if (tripleSlider && valueDisplay) {
        const finalValue = decimals === 0 ? Math.round(defaultValue) : defaultValue;
        tripleSlider.setValue(finalValue);
        valueDisplay.textContent = decimals === 0 ? Math.round(finalValue) : finalValue.toFixed(decimals);
        
        // Send update to backend
        updateParameter(player, effectIndex, paramName, finalValue, valueDisplayId);
    }
    
    return false;
};

/**
 * Reset generator parameter to default value on right-click for triple-slider
 */
window.resetGeneratorParameterToDefaultTriple = function(event, paramName, defaultValue, controlId) {
    event.preventDefault(); // Prevent context menu
    
    const tripleSlider = getTripleSlider(controlId);
    
    if (tripleSlider) {
        tripleSlider.setValue(defaultValue);
        updateGeneratorParameter(paramName, defaultValue);
    }
    
    return false;
};

window.updateParameter = async function(player, effectIndex, paramName, value, valueDisplayId = null) {
    try {
        // Sofort UI-Update für responsives Feedback mit korrekter Formatierung
        if (valueDisplayId) {
            const displayElement = document.getElementById(valueDisplayId);
            if (displayElement) {
                const controlId = valueDisplayId.replace('_value', '');
                const slider = document.getElementById(controlId);
                const decimals = slider ? parseInt(slider.getAttribute('data-decimals') || '0') : 0;
                displayElement.textContent = decimals === 0 ? Math.round(value) : value.toFixed(decimals);
            }
        }
        
        // Configurable debounce (from config.json websocket.commands.debounce_ms)
        const timerKey = `${player}_${effectIndex}_${paramName}`;
        
        if (parameterUpdateTimers[timerKey]) {
            clearTimeout(parameterUpdateTimers[timerKey]);
        }
        
        parameterUpdateTimers[timerKey] = setTimeout(async () => {
            await sendParameterUpdate(player, effectIndex, paramName, value, valueDisplayId);
            delete parameterUpdateTimers[timerKey];
        }, WEBSOCKET_DEBOUNCE_MS); // Configurable from config.json (default: 50ms)
        
    } catch (error) {
        console.error(`❌ Error updating ${player} parameter:`, error);
    }
};

async function sendParameterUpdate(player, effectIndex, paramName, value, valueDisplayId = null) {
    try {
        // Check if this is a triple-slider and include range data
        const controlId = valueDisplayId ? valueDisplayId.replace('_value', '') : null;
        const tripleSlider = controlId ? getTripleSlider(controlId) : null;
        
        let endpoint;
        let body;
        let method;
        let playerId;
        let targetClipId;
        
        if (player === 'clip') {
            // Layer-as-Clips Architecture: Use layer.clip_id if layer is selected
            targetClipId = selectedLayerClipId || selectedClipId;
            playerId = selectedClipPlayerType;
            debug.log(`🔍 sendParameterUpdate: selectedLayerId=${selectedLayerId}, selectedLayerClipId=${selectedLayerClipId}, selectedClipId=${selectedClipId}, targetClipId=${targetClipId}`);
            
            body = { 
                name: paramName, 
                value: value
            };
            if (tripleSlider) {
                const range = tripleSlider.getRange();
                body.rangeMin = range.min;
                body.rangeMax = range.max;
                if (window.DEBUG_LOGGING) {
                    console.log(`🎚️ Triple-slider range: min=${range.min}, max=${range.max}, value=${value}`);
                }
            }
            
            // Try WebSocket first for clip effects
            try {
                const wsParams = {
                    player_id: playerId,
                    clip_id: targetClipId,
                    effect_index: effectIndex,
                    param_name: paramName,
                    value: value
                };
                
                // Include range data if triple slider
                if (tripleSlider) {
                    const range = tripleSlider.getRange();
                    wsParams.rangeMin = range.min;
                    wsParams.rangeMax = range.max;
                }
                
                await executeCommand(
                    'effects',
                    'command.effect.param',
                    wsParams,
                    async () => {
                        // REST fallback
                        endpoint = `${API_BASE}/api/player/${playerId}/clip/${targetClipId}/effects/${effectIndex}/parameter`;
                        const response = await fetch(endpoint, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(body)
                        });
                        return await response.json();
                    }
                );
                
                const target = isLayerSelected() ? `Layer ${selectedLayerId}` : player;
                debug.log(`✅ Updated ${target} ${paramName} = ${value} (WebSocket)`);
                return;
            } catch (error) {
                console.error(`❌ WebSocket effect param update failed:`, error);
            }
        } else if (player === 'video') {
            playerId = 'video';
            endpoint = `${API_BASE}/api/player/video/effects/${effectIndex}/parameter`;
            body = { name: paramName, value: value };
            if (tripleSlider) {
                const range = tripleSlider.getRange();
                body.rangeMin = range.min;
                body.rangeMax = range.max;
            }
            method = 'PUT';
        } else {
            playerId = 'artnet';
            endpoint = `${API_BASE}/api/player/artnet/effects/${effectIndex}/parameter`;
            body = { name: paramName, value: value };
            if (tripleSlider) {
                const range = tripleSlider.getRange();
                body.rangeMin = range.min;
                body.rangeMax = range.max;
            }
            method = 'PUT';
        }
        
        // REST API fallback for video/artnet global effects
        const response = await fetch(endpoint, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const data = await response.json();
        
        if (data.success) {
            const target = isLayerSelected() ? `Layer ${selectedLayerId}` : player;
            debug.log(`✅ Updated ${target} ${paramName} = ${value}`);
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
        itemDiv.style.paddingLeft = `${level * 20 + 8}px`; // Dynamic nesting depth
        
        if (item.type === 'folder') {
            itemDiv.innerHTML = `
                <div class="file-item-content folder" onclick="toggleFolder(this)">
                    <span class="folder-icon">📁</span>
                    <span class="file-name">${item.name}</span>
                    <span class="folder-toggle">▶</span>
                </div>
                <div class="folder-children"></div>
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
    
    if (children.classList.contains('expanded')) {
        children.classList.remove('expanded');
        toggle.textContent = '▶';
    } else {
        children.classList.add('expanded');
        toggle.textContent = '▼';
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
    // NOTE: File browser is now handled by FilesTab component in initializeTabComponents()
    
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
                video_playlist: playerConfigs.video.files,
                artnet_playlist: playerConfigs.artnet.files
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

// Initialize modals once ModalManager is available
let playlistModal = null;
let snapshotModal = null;

function initializeModals() {
    if (!window.ModalManager) {
        debug.warn('⚠️ ModalManager not loaded yet, retrying...');
        setTimeout(initializeModals, 100);
        return;
    }
    
    // Create playlist modal
    playlistModal = ModalManager.create({
        id: 'playlistModal',
        title: '📂 Load Playlists',
        content: '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>',
        centered: true,
        size: null
    });
    
    // Create snapshot modal
    snapshotModal = ModalManager.create({
        id: 'snapshotModal',
        title: '🔄 Restore Session Snapshot',
        content: '<div class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>',
        centered: true,
        size: null
    });
    
    debug.log('✅ Modals initialized');
}

// Call initialization when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeModals);
} else {
    initializeModals();
}

window.refreshPlaylistModal = async function() {
    try {
        if (!playlistModal) {
            console.error('❌ Playlist modal not initialized');
            return;
        }
        
        // Get list of available playlists
        const response = await fetch(`${API_BASE}/api/playlists`);
        const data = await response.json();
        
        if (data.status !== 'success' || !data.playlists || data.playlists.length === 0) {
            playlistModal.setContent(`
                <div class="text-center">
                    <div class="large-icon">📂</div>
                    <p>No saved playlists found</p>
                </div>
            `);
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
                <div class="list-group-item modal-list-item">
                    <div class="d-flex">
                        <button type="button" 
                                class="flex-grow-1 btn text-start p-3 btn-main" 
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
                                class="btn btn-danger btn-delete" 
                                onclick="deletePlaylist('${playlist.name}', event)"
                                title="Playlist löschen">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        playlistModal.setContent(html);
        
    } catch (error) {
        console.error('❌ Error refreshing playlists:', error);
        showToast('Error loading playlists', 'error');
    }
};

window.loadPlaylists = async function() {
    try {
        if (!playlistModal) {
            console.error('❌ Playlist modal not initialized');
            return;
        }
        
        // Show modal
        playlistModal.show();
        
        // Load playlist list
        await refreshPlaylistModal();
        
    } catch (error) {
        console.error('❌ Error loading playlists:', error);
        showToast('Error loading playlists', 'error');
        playlistModal?.hide();
    }
};

window.selectPlaylist = async function(playlistName) {
    try {
        debug.log('🎯 Loading playlist:', playlistName);
        
        // Load the playlist
        const loadResponse = await fetch(`${API_BASE}/api/playlist/load/${playlistName}`);
        const loadData = await loadResponse.json();
        
        debug.log('🎯 Playlist data received:', loadData);
        
        if (loadData.success) {
            // Load both playlists
            playerConfigs.video.files = loadData.video_playlist || [];
            playerConfigs.artnet.files = loadData.artnet_playlist || [];
            
            debug.log('🎯 Video files:', playerConfigs.video.files.length);
            debug.log('🎯 Art-Net files:', playerConfigs.artnet.files.length);
            
            renderPlaylist('video');
            renderPlaylist('artnet');
            
            // Restore master/slave state
            const savedMasterPlaylist = loadData.master_playlist;
            if (savedMasterPlaylist) {
                debug.log('👑 Restoring master playlist:', savedMasterPlaylist);
                // Update UI checkboxes
                const videoCheckbox = document.getElementById('videoMasterSwitch');
                const artnetCheckbox = document.getElementById('artnetMasterSwitch');
                if (videoCheckbox && artnetCheckbox) {
                    videoCheckbox.checked = (savedMasterPlaylist === 'video');
                    artnetCheckbox.checked = (savedMasterPlaylist === 'artnet');
                    masterPlaylist = savedMasterPlaylist;
                    updateMasterUI();
                    debug.log('✅ Master/slave UI restored');
                }
            } else {
                // Clear master state if none saved
                const videoCheckbox = document.getElementById('videoMasterSwitch');
                const artnetCheckbox = document.getElementById('artnetMasterSwitch');
                if (videoCheckbox && artnetCheckbox) {
                    videoCheckbox.checked = false;
                    artnetCheckbox.checked = false;
                    masterPlaylist = null;
                    updateMasterUI();
                }
            }
            
            showToast(`Playlists "${playlistName}" loaded (Video: ${playerConfigs.video.files.length}, Art-Net: ${playerConfigs.artnet.files.length})`, 'success');
            
            // Close modal
            playlistModal?.hide();
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

let transitionMenus = {}; // Store transition menu controllers

async function initializeTransitionMenus() {
    // Wait for template to be loaded
    const checkTemplate = () => {
        return new Promise((resolve, reject) => {
            const interval = setInterval(() => {
                const template = document.getElementById('transition-menu-template');
                if (template && window.createTransitionMenu) {
                    clearInterval(interval);
                    resolve();
                }
            }, 100);
            
            // Timeout after 5 seconds
            setTimeout(() => {
                clearInterval(interval);
                reject(new Error('Transition menu template not loaded within timeout'));
            }, 5000);
        });
    };
    
    try {
        await checkTemplate();
        
        // Create transition menus for both players
        const videoContainer = document.getElementById('videoTransitionMenuContainer');
        const artnetContainer = document.getElementById('artnetTransitionMenuContainer');
        
        if (videoContainer) {
            transitionMenus.video = await window.createTransitionMenu('video', videoContainer);
            debug.log('✅ Video transition menu initialized');
        }
        
        if (artnetContainer) {
            transitionMenus.artnet = await window.createTransitionMenu('artnet', artnetContainer);
            debug.log('✅ Art-Net transition menu initialized');
        }
    } catch (error) {
        console.error('❌ Failed to initialize transition menus:', error);
    }
}

// Backward compatibility functions (optional)
window.toggleTransitionMenu = function(playerId) {
    if (transitionMenus[playerId]) {
        transitionMenus[playerId].toggle();
    }
};

window.closeTransitionMenu = function(playerId) {
    if (transitionMenus[playerId]) {
        transitionMenus[playerId].close();
    }
};

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
        if (!snapshotModal) {
            console.error('❌ Snapshot modal not initialized');
            return;
        }
        
        // Get list of available snapshots
        const response = await fetch(`${API_BASE}/api/session/snapshots`);
        const data = await response.json();
        
        if (!data.success || !data.snapshots || data.snapshots.length === 0) {
            snapshotModal.setContent(`
                <div class="text-center">
                    <div class="large-icon">📸</div>
                    <p>No snapshots found</p>
                    <p class="text-muted small">Create a snapshot to save the current session state</p>
                </div>
            `);
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
                <div class="list-group-item modal-list-item">
                    <div class="d-flex">
                        <button type="button" 
                                class="flex-grow-1 btn text-start p-3 btn-main" 
                                onclick="selectSnapshot('${snapshot.filename}')>
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
                                class="btn btn-danger btn-delete" 
                                onclick="deleteSnapshot('${snapshot.filename}', event)"
                                title="Snapshot löschen">
                            🗑️
                        </button>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        
        snapshotModal.setContent(html);
        
    } catch (error) {
        console.error('❌ Error refreshing snapshots:', error);
        showToast('Error loading snapshots', 'error');
    }
};

window.loadSnapshotModal = async function() {
    try {
        if (!snapshotModal) {
            console.error('❌ Snapshot modal not initialized');
            return;
        }
        
        // Show modal
        snapshotModal.show();
        
        // Load snapshot list
        await refreshSnapshotModal();
        
    } catch (error) {
        console.error('❌ Error loading snapshots:', error);
        showToast('Error loading snapshots', 'error');
        snapshotModal?.hide();
    }
};

window.selectSnapshot = async function(filename) {
    try {
        debug.log('🔄 Restoring snapshot:', filename);
        
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
            snapshotModal?.hide();
            
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

// ========================================
// MULTI-LAYER SYSTEM
// ========================================

// Layer state (now per clip, not per player)
let clipLayers = {};  // { clip_id: [{layer_id, source_type, ...}] }
// selectedClipId already declared above (line 112)

/**
 * Load layer counts for all clips in background (for badge display)
 */
async function loadAllClipLayerCounts(clips) {
    for (const clip of clips) {
        if (clip.id && !clipLayers[clip.id]) {
            // Load layers in background without awaiting
            loadClipLayers(clip.id).catch(err => {
                debug.error(`Failed to load layers for clip ${clip.id}:`, err);
            });
        }
    }
}

/**
 * Get layer count for a clip
 */
function getClipLayerCount(clipId) {
    const layers = clipLayers[clipId] || [];
    return layers.length;
}

/**
 * Get layer badge HTML for playlist item
 */
function getLayerBadgeHtml(clipId) {
    const count = getClipLayerCount(clipId);
    // Only show badge if clip has overlay layers (more than just Layer 0)
    if (count <= 1) {
        return '';
    }
    return `<span class="layer-badge" title="${count} layer(s)">🎞️ ${count}</span>`;
}

/**
 * Load layers for a clip
 */
async function loadClipLayers(clipId) {
    try {
        const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers`);
        const data = await response.json();
        
        if (data.success) {
            const layers = data.layers || [];
            clipLayers[clipId] = layers;
            debug.log(`✅ Loaded ${layers.length} layers for clip ${clipId}`);
            
            // Re-render if this clip is currently selected
            if (selectedClipId === clipId) {
                renderSelectedClipLayers();
            }
            
            // Re-render playlist to update badge (only if clip has overlay layers)
            if (layers.length > 1) {  // Only if has overlay layers (Layer 0 is always present)
                // Find which playlist this clip belongs to
                const inVideo = playerConfigs.video.files.some(f => f.id === clipId);
                const inArtnet = playerConfigs.artnet.files.some(f => f.id === clipId);
                
                if (inVideo) {
                    renderPlaylist('video');
                } else if (inArtnet) {
                    renderPlaylist('artnet');
                }
            }
        }
    } catch (error) {
        debug.error(`❌ Error loading clip layers:`, error);
    }
}

/**
 * Render layer management panel for selected clip
 */
function renderSelectedClipLayers() {
    if (!selectedClipId) return;
    
    const layers = clipLayers[selectedClipId] || [];
    const panelContent = document.getElementById('layerPanelContent');
    if (!panelContent) return;
    
    // Note: layers should always include at least Layer 0 (base clip)
    // If only Layer 0 exists (no overlay layers), show empty state
    if (layers.length === 0 || layers.length === 1) {
        // Update header with playlist info
        const playlist = playerConfigs[selectedClipPlayerType].files;
        const clipIndex = playlist.findIndex(item => item.id === selectedClipId);
        const position = clipIndex >= 0 ? clipIndex + 1 : '?';
        const playlistName = selectedClipPlayerType === 'video' ? 'Video' : 'Art-Net';
        
        const panelTitle = document.getElementById('layerPanelTitle');
        if (panelTitle) {
            panelTitle.innerHTML = `🎞️ Layers <small class="layer-panel-title-small">(${playlistName} #${position})</small>`;
        }
        
        panelContent.innerHTML = `
            <div class="empty-state">
                <p class="empty-state-hint">Klicke auf Clip um Layer zu verwalten</p>
                <p class="empty-state-secondary">Drag files from Files tab to add layers</p>
            </div>
        `;
        // No need to call setupLayerPanelDropZone() - it's already set up once
        return;
    }
    
    // Sort by layer_id descending (top layer first in UI)
    const sortedLayers = [...layers].sort((a, b) => b.layer_id - a.layer_id);
    
    const layerCardsHtml = sortedLayers.map(layer => {
        const isEnabled = layer.enabled !== false;
        const sourceName = layer.source_path ? layer.source_path.split(/[\\/]/).pop() : 'Unknown';
        const isBaseLayer = layer.layer_id === 0;
        
        return `
            <div class="layer-card ${!isEnabled ? 'disabled' : ''} ${isBaseLayer ? 'base-layer' : ''} ${selectedLayerId === layer.layer_id ? 'selected' : ''}"
                 data-layer-id="${layer.layer_id}"
                 draggable="false"
                 onclick="toggleLayerSelection(${layer.layer_id}, event)">
                <div class="layer-header">
                    <span class="layer-id">
                        ${!isBaseLayer ? '<span class="layer-drag-handle" title="Drag to reorder">☰</span>' : ''}
                        🎞️ Layer ${layer.layer_id} ${isBaseLayer ? '(Base Clip)' : ''}
                    </span>
                    ${!isBaseLayer ? `
                        <button class="btn btn-sm btn-danger layer-remove" 
                                onclick="removeLayerFromClip('${selectedClipId}', ${layer.layer_id}, event)"
                                title="Remove Layer">
                            ❌
                        </button>
                    ` : '<span class="layer-lock-icon">🔒</span>'}
                </div>
                <div class="layer-source">
                    ${sourceName}
                </div>
                <div class="layer-config">
                    <select class="blend-mode-select" 
                            onchange="updateClipLayerBlendMode('${selectedClipId}', ${layer.layer_id}, this.value)"
                            ${isBaseLayer ? 'disabled' : ''}>
                        ${availableBlendModes.map(mode => `
                            <option value="${mode}" ${layer.blend_mode === mode ? 'selected' : ''}>
                                ${mode.charAt(0).toUpperCase() + mode.slice(1)}
                            </option>
                        `).join('')}
                    </select>
                    <input type="range" 
                           class="opacity-slider" 
                           min="0" 
                           max="100" 
                           value="${Math.round(layer.opacity * 100)}"
                           oninput="updateClipLayerOpacity('${selectedClipId}', ${layer.layer_id}, this.value)"
                           title="Opacity: ${Math.round(layer.opacity * 100)}%"
                           ${isBaseLayer ? 'disabled' : ''}>
                    <span class="opacity-value">${Math.round(layer.opacity * 100)}%</span>
                </div>
            </div>
        `;
    }).join('');
    
    // Update panel header with playlist info
    const playlist = playerConfigs[selectedClipPlayerType].files;
    const clipIndex = playlist.findIndex(item => item.id === selectedClipId);
    const position = clipIndex >= 0 ? clipIndex + 1 : '?';
    const playlistName = selectedClipPlayerType === 'video' ? 'Video' : 'Art-Net';
    
    const panelTitle = document.getElementById('layerPanelTitle');
    if (panelTitle) {
        panelTitle.innerHTML = `🎞️ Layers <small class="layer-panel-title-small">(${playlistName} #${position})</small>`;
    }
    
    panelContent.innerHTML = `
        <div class="layer-stack-container">
            <div class="layer-stack-items" id="layerStackItems">
                ${layerCardsHtml}
            </div>
        </div>
    `;
    
    // Setup drag & drop for reordering
    setupLayerDragAndDrop();
}

/**
 * Setup drop zone for layer panel (called once on init)
 */
let layerPanelDropZoneInitialized = false;
function setupLayerPanelDropZone() {
    if (layerPanelDropZoneInitialized) return; // Already set up
    
    const panel = document.getElementById('layerPanelContent');
    if (!panel) return;
    
    layerPanelDropZoneInitialized = true;
    
    panel.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (selectedClipId) {
            panel.classList.add('drop-target-bordered');
        }
    });
    
    panel.addEventListener('dragleave', (e) => {
        panel.classList.remove('drop-target-bordered');
    });
    
    panel.addEventListener('drop', async (e) => {
        e.preventDefault();
        e.stopPropagation();
        panel.classList.remove('drop-target-bordered');
        
        if (!selectedClipId) {
            showToast('No clip selected', 'warning');
            return;
        }
        
        // Check for video file
        const filePath = e.dataTransfer.getData('file-path') || e.dataTransfer.getData('video-path');
        const fileType = e.dataTransfer.getData('file-type');
        
        if (filePath) {
            debug.log(`📥 Adding ${filePath} as layer to clip ${selectedClipId}`);
            
            if (fileType === 'image') {
                // Images should be added as video layers (they're treated as single-frame videos)
                // Or we could use static_picture generator but that requires special handling
                showToast('Image layers not yet supported - use videos', 'warning');
            } else {
                // Add video layer
                await addLayerToClip(selectedClipId, filePath, 'video');
            }
            return;
        }
        
        // Check for generator
        const generatorId = e.dataTransfer.getData('generatorId');
        if (generatorId) {
            debug.log(`📥 Adding generator ${generatorId} as layer to clip ${selectedClipId}`);
            await addLayerToClip(selectedClipId, generatorId, 'generator');
            return;
        }
        
        showToast('Drop a video file or generator here', 'info');
    });
}

/**
 * Close layer panel (deprecated - panel now always visible)
 */
window.closeLayerPanel = function() {
    // Panel is now always visible
    selectedClipId = null;
    const panelContent = document.getElementById('layerPanelContent');
    // Reset panel header
    const panelTitle = document.getElementById('layerPanelTitle');
    if (panelTitle) {
        panelTitle.innerHTML = '🎞️ Layers';
    }
    
    if (panelContent) {
        panelContent.innerHTML = `
            <div class="empty-state">
                <p class="empty-state-hint">Klicke auf Clip um Layer zu verwalten</p>
                <p class="empty-state-secondary">Drag files from Files tab to add layers</p>
            </div>
        `;
        // No need to call setupLayerPanelDropZone() - it's already set up once
    }
};

// Add layers via drag & drop from Files tab - no modal needed

/**
 * Add layer to clip (called programmatically or by drag-drop)
 */
window.addLayerToClip = async function(clipId, sourcePath, sourceType = 'video') {
    if (!sourcePath) {
        showToast('No source path provided', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_type: sourceType,
                source_path: sourcePath,
                blend_mode: 'normal',
                opacity: 1.0
            })
        });
        
        const data = await response.json();
        if (data.success) {
            await loadClipLayers(clipId);
            renderSelectedClipLayers();
        } else {
            showToast(`Failed to add layer: ${data.error}`, 'error');
        }
    } catch (error) {
        debug.error('Error adding layer:', error);
        showToast('Error adding layer', 'error');
    }
};

// ========================================
// LAYER SELECTION (Layer-as-Clips Architecture)
// ========================================

/**
 * Select a layer for effect management
 */
async function selectLayer(layerId) {
    if (!selectedClipId) {
        console.warn('⚠️ No clip selected, cannot select layer');
        return;
    }
    
    // Update state
    selectedLayerId = layerId;
    
    // Load layer.clip_id from backend
    try {
        const response = await fetch(`${API_BASE}/api/clips/${selectedClipId}/layers`);
        const data = await response.json();
        
        console.log('🔍 API response:', data);
        
        if (data.success && data.layers) {
            console.log('🔍 All layers:', data.layers);
            const layer = data.layers.find(l => l.layer_id === layerId);
            console.log(`🔍 Found layer ${layerId}:`, layer);
            if (layer && layer.clip_id) {
                selectedLayerClipId = layer.clip_id;
                debug.log(`📐 Layer ${layerId} selected, clip_id: ${selectedLayerClipId}`);
            } else {
                console.warn(`⚠️ Layer ${layerId} has no clip_id!`, layer);
            }
        }
    } catch (error) {
        console.error('Error loading layer clip_id:', error);
    }
    
    // Update UI
    updateLayerSelectionUI();
    
    // Refresh FX Tab (loads layer effects)
    await refreshClipEffects();
}

/**
 * Deselect layer
 */
function deselectLayer() {
    selectedLayerId = null;
    selectedLayerClipId = null;
    
    debug.log('📐 Layer deselected');
    
    // Update UI
    updateLayerSelectionUI();
    
    // Refresh FX Tab (loads clip effects)
    refreshClipEffects();
}

/**
 * Check if layer is selected
 */
function isLayerSelected() {
    return selectedLayerId !== null;
}

/**
 * Update visual feedback for layer selection
 */
function updateLayerSelectionUI() {
    // Remove 'selected' class from all layer cards
    document.querySelectorAll('.layer-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add 'selected' class to selected layer
    if (selectedLayerId !== null) {
        const selectedCard = document.querySelector(`.layer-card[data-layer-id="${selectedLayerId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }
    }
}

/**
 * Toggle layer selection (called from layer-card click)
 */
window.toggleLayerSelection = async function(layerId, event) {
    // Stop propagation to prevent conflicts with other handlers
    if (event) {
        event.stopPropagation();
        
        // Don't toggle if clicking on buttons or inputs
        const target = event.target;
        if (target.tagName === 'BUTTON' || target.tagName === 'INPUT' || target.tagName === 'SELECT') {
            return;
        }
    }
    
    // Toggle: deselect if already selected, select if not
    if (selectedLayerId === layerId) {
        deselectLayer();
    } else {
        await selectLayer(layerId);
    }
};

/**
 * Remove layer from clip (two-click confirmation)
 */
window.removeLayerFromClip = async function(clipId, layerId, e) {
    e.stopPropagation();
    
    const button = e.currentTarget;
    const originalText = button.innerHTML;
    const originalOnclick = button.onclick;
    
    // First click: Confirm
    button.innerHTML = '✓';
    button.classList.remove('btn-danger');
    button.classList.add('btn-warning');
    button.onclick = null;
    
    // Reset after 3 seconds
    const resetTimer = setTimeout(() => {
        button.innerHTML = originalText;
        button.classList.remove('btn-warning');
        button.classList.add('btn-danger');
        button.onclick = originalOnclick;
    }, 3000);
    
    // Second click: Execute
    button.onclick = async (e) => {
        e.stopPropagation();
        clearTimeout(resetTimer);
        
        try {
            const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers/${layerId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            if (data.success) {
                showToast(`Layer ${layerId} removed`, 'success');
                await loadClipLayers(clipId);
                renderSelectedClipLayers();
            } else {
                showToast(`Failed to remove layer: ${data.error}`, 'error');
            }
        } catch (error) {
            debug.error('Error removing layer:', error);
            showToast('Error removing layer', 'error');
        }
    };
};

/**
 * Update layer blend mode
 */
window.updateClipLayerBlendMode = async function(clipId, layerId, blendMode) {
    try {
        const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers/${layerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ blend_mode: blendMode })
        });
        
        const data = await response.json();
        if (data.success) {
            debug.log(`✅ Layer ${layerId} blend mode updated to ${blendMode}`);
            await loadClipLayers(clipId);
        } else {
            showToast(`Failed to update blend mode: ${data.error}`, 'error');
        }
    } catch (error) {
        debug.error('Error updating blend mode:', error);
    }
};

/**
 * Update layer opacity
 */
// Debounce timer for opacity updates
let opacityUpdateTimer = null;

window.updateClipLayerOpacity = async function(clipId, layerId, opacity) {
    // Update the UI immediately for smooth visual feedback
    const opacityValueSpan = document.querySelector(`.layer-card[data-layer-id="${layerId}"] .opacity-value`);
    if (opacityValueSpan) {
        opacityValueSpan.textContent = `${opacity}%`;
    }
    
    // Debounce the API call
    clearTimeout(opacityUpdateTimer);
    opacityUpdateTimer = setTimeout(async () => {
        const opacityFloat = parseFloat(opacity) / 100;
        
        try {
            const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers/${layerId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ opacity: opacityFloat })
            });
            
            const data = await response.json();
            if (data.success) {
                debug.log(`✅ Layer ${layerId} opacity updated to ${opacity}%`);
                await loadClipLayers(clipId);
            } else {
                showToast(`Failed to update opacity: ${data.error}`, 'error');
            }
        } catch (error) {
            debug.error('Error updating opacity:', error);
        }
    }, 300); // Wait 300ms after user stops dragging
};

/**
 * Remove a layer
 */
window.removeLayer = async function(playerId, layerId) {
    if (!confirm(`Remove layer ${layerId}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/${layerId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Layer ${layerId} removed`, 'success');
            
            // Clear selection if removed layer was selected
            if (selectedLayerId[playerId] === layerId) {
                selectedLayerId[playerId] = null;
            }
            
            // await loadLayers(playerId); // OLD: Now using clip-based layers
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        debug.error(`❌ Error removing layer:`, error);
        showToast('Error removing layer', 'error');
    }
};

/**
 * Update layer blend mode
 */
window.updateLayerBlendMode = async function(playerId, layerId, blendMode) {
    try {
        // Try WebSocket first
        await executeCommand(
            'layers',
            'command.layer.blend_mode',
            {
                player_id: playerId,
                layer_id: layerId,
                blend_mode: blendMode
            },
            async () => {
                // REST fallback
                const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/${layerId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ blend_mode: blendMode })
                });
                return await response.json();
            }
        );
        
        debug.log(`✅ Layer ${layerId} blend mode: ${blendMode} (WebSocket)`);
    } catch (error) {
        debug.error(`❌ Error updating blend mode:`, error);
        showToast('Error updating blend mode', 'error');
    }
};

/**
 * Update layer opacity
 */
window.updateLayerOpacity = async function(playerId, layerId, value) {
    const opacity = parseFloat(value);
    
    try {
        // Try WebSocket first
        await executeCommand(
            'layers',
            'command.layer.opacity',
            {
                player_id: playerId,
                layer_id: layerId,
                opacity: opacity
            },
            async () => {
                // REST fallback
                const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/${layerId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ opacity: opacity / 100 })
                });
                return await response.json();
            }
        );
        
        // Update only the opacity display without full re-render
        const card = document.querySelector(`[data-layer-id="${layerId}"] .opacity-value`);
        if (card) {
            card.textContent = `${Math.round(opacity)}%`;
        }
        
        debug.log(`✅ Layer ${layerId} opacity: ${opacity}% (WebSocket)`);
    } catch (error) {
        debug.error(`❌ Error updating opacity:`, error);
    }
};

/**
 * Toggle layer enabled/disabled
 */
window.toggleLayer = async function(playerId, layerId) {
    // OLD: Now using clip-based layers
    const newEnabled = true; // Default value
    
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/${layerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newEnabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Layer ${layerId} ${newEnabled ? 'enabled' : 'disabled'}`, 'success');
            // await loadLayers(playerId); // OLD: Now using clip-based layers
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        debug.error(`❌ Error toggling layer:`, error);
        showToast('Error toggling layer', 'error');
    }
};

/**
 * Setup drag and drop for layer reordering (clip-based layers)
 * Drag nur über Burger-Icon aktivierbar
 */
function setupLayerDragAndDrop() {
    const container = document.getElementById('layerStackItems');
    if (!container) return;
    
    const cards = container.querySelectorAll('.layer-card');
    
    let draggedElement = null;
    
    cards.forEach(card => {
        const dragHandle = card.querySelector('.layer-drag-handle');
        if (!dragHandle) return; // Skip base layer (no drag handle)
        
        // Make card draggable only when dragging from handle
        dragHandle.addEventListener('mousedown', (e) => {
            card.setAttribute('draggable', 'true');
            dragHandle.classList.add('drag-handle-grabbing');
        });
        
        dragHandle.addEventListener('mouseup', (e) => {
            card.setAttribute('draggable', 'false');
            dragHandle.classList.remove('drag-handle-grabbing');
        });
        
        card.addEventListener('dragstart', (e) => {
            draggedElement = card;
            card.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.layerId);
        });
        
        card.addEventListener('dragend', (e) => {
            card.classList.remove('dragging');
            card.setAttribute('draggable', 'false');
            const dragHandle = card.querySelector('.layer-drag-handle');
            if (dragHandle) dragHandle.classList.remove('drag-handle-grabbing');
            draggedElement = null;
        });
        
        card.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            
            if (draggedElement && draggedElement !== card) {
                // Don't allow dropping on base layer (layer 0)
                const targetLayerId = parseInt(card.dataset.layerId);
                if (targetLayerId === 0) {
                    e.dataTransfer.dropEffect = 'none';
                    return;
                }
                
                // Add visual feedback
                card.classList.add('drag-over');
                
                const rect = card.getBoundingClientRect();
                const midpoint = rect.top + rect.height / 2;
                
                if (e.clientY < midpoint) {
                    container.insertBefore(draggedElement, card);
                } else {
                    container.insertBefore(draggedElement, card.nextSibling);
                }
            }
        });
        
        card.addEventListener('dragleave', (e) => {
            card.classList.remove('drag-over');
        });
        
        card.addEventListener('drop', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            
            // Remove visual feedback
            card.classList.remove('drag-over');
            
            if (!selectedClipId) return;
            
            // Get new order from DOM (top to bottom in UI)
            const uiOrder = Array.from(container.querySelectorAll('.layer-card'))
                .map(c => parseInt(c.dataset.layerId));
            
            // Filter out layer 0 (base layer is not in the reorder list)
            const newOrder = uiOrder.filter(id => id !== 0);
            
            debug.log(`🔄 Reordering layers: ${newOrder.join(', ')}`);
            
            await reorderClipLayers(selectedClipId, newOrder);
        });
    });
}

/**
 * Reorder clip layers via API
 */
async function reorderClipLayers(clipId, newOrder) {
    try {
        const response = await fetch(`${API_BASE}/api/clips/${clipId}/layers/reorder`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_order: newOrder })
        });
        
        const data = await response.json();
        
        if (data.success) {
            debug.log(`✅ Layers reordered for clip ${clipId}`);
            // Reload layers to get updated order from backend
            await loadClipLayers(clipId);
        } else {
            showToast(`Failed to reorder layers: ${data.error}`, 'error');
            // Reload to restore correct order
            await loadClipLayers(clipId);
        }
    } catch (error) {
        console.error('❌ Error reordering layers:', error);
        showToast('Error reordering layers', 'error');
        // Reload to restore correct order
        await loadClipLayers(clipId);
    }
}

/**
 * Load clip into selected layer
 */
async function loadClipIntoLayer(playerId, layerId, item) {
    try {
        const body = {};
        
        if (item.type === 'generator' && item.generator_id) {
            body.source_type = 'generator';
            body.generator_id = item.generator_id;
            if (item.parameters) {
                body.parameters = item.parameters;
            }
        } else {
            body.source_type = 'video';
            body.video_path = item.path;
        }
        
        const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/${layerId}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`Loaded ${item.name} into Layer ${layerId}`, 'success');
            // await loadLayers(playerId); // OLD: Now using clip-based layers
        } else {
            showToast(`Error: ${data.error}`, 'error');
        }
    } catch (error) {
        debug.error(`❌ Error loading clip into layer:`, error);
        showToast('Error loading clip into layer', 'error');
    }
}

/**
 * Reorder layers
 */
async function reorderLayers(playerId, layerOrder) {
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/layers/reorder`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ layer_order: layerOrder })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Layers reordered', 'success');
            // await loadLayers(playerId); // OLD: Now using clip-based layers
        } else {
            showToast(`Error: ${data.error}`, 'error');
            // await loadLayers(playerId); // OLD: Now using clip-based layers
        }
    } catch (error) {
        debug.error(`❌ Error reordering layers:`, error);
        showToast('Error reordering layers', 'error');
        // await loadLayers(playerId); // OLD: Now using clip-based layers
    }
}

// ========================================
// INITIALIZATION: Load layers on startup
// ========================================

// Add to init() function - we'll need to call loadLayers for both players
// This will be integrated when init() is modified

// Cleanup
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    
    // Clean up WebSocket connections to prevent "Insufficient resources" errors
    if (websocketPreview) {
        websocketPreview.stop();
        websocketPreview = null;
    }
    if (websocketArtnetPreview) {
        websocketArtnetPreview.stop();
        websocketArtnetPreview = null;
    }
});
