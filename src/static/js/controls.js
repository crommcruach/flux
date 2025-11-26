/**
 * Controls.js - New Dual-Player Layout
 * Video + Art-Net players with FX control
 */

import { showToast } from './common.js';

const API_BASE = '';
let availableEffects = [];
let videoEffects = [];
let artnetEffects = [];
let clipEffects = [];
let updateInterval = null;
let playlistUpdateInterval = null;

// Autoplay & Loop State
let videoAutoplay = false;
let videoLoop = false;
let artnetAutoplay = false;
let artnetLoop = false;

// Clip FX State (NEW: UUID-based)
let selectedClipId = null;  // UUID from clip registry
let selectedClipPath = null;  // Original path (for display)
let selectedClipPlayerType = null;  // 'video' or 'artnet'

// Transition State
let videoTransitionConfig = {
    enabled: false,
    effect: 'fade',
    duration: 1.0,
    easing: 'ease_in_out'
};

let artnetTransitionConfig = {
    enabled: false,
    effect: 'fade',
    duration: 1.0,
    easing: 'ease_in_out'
};

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', init);

async function init() {
    await loadAvailableEffects();
    await loadVideoPlaylist();
    await loadArtnetPlaylist();
    await refreshVideoEffects();
    await refreshArtnetEffects();
    startPreviewStream();
    startArtnetPreviewStream();
    setupEffectDropZones();
    
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
        const response = await fetch(`${API_BASE}/api/video/status`);
        const data = await response.json();
        
        if (data.status === 'success') {
            // Normalisiere Pfad (entferne führende Slashes/Backslashes)
            const newVideo = data.current_video ? data.current_video.replace(/^[\\\/]+/, '') : null;
            const normalizedCurrent = currentVideo ? currentVideo.replace(/^[\\\/]+/, '') : null;
            
            if (normalizedCurrent !== newVideo) {
                currentVideo = newVideo;
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
        const response = await fetch(`${API_BASE}/api/artnet/video/status`);
        const data = await response.json();
        
        if (data.status === 'success') {
            // Normalisiere Pfad (entferne führende Slashes/Backslashes)
            const newVideo = data.current_video ? data.current_video.replace(/^[\\\/]+/, '') : null;
            const normalizedCurrent = currentArtnet ? currentArtnet.replace(/^[\\\/]+/, '') : null;
            
            if (normalizedCurrent !== newVideo) {
                currentArtnet = newVideo;
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

// Drag & Drop for Effects
window.startEffectDrag = function(event, effectId) {
    event.dataTransfer.effectAllowed = 'copy';
    event.dataTransfer.setData('effectId', effectId);
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
// VIDEO PLAYLIST
// ========================================

let videoFiles = [];
let currentVideo = null;

async function loadVideoPlaylist() {
    try {
        // Load player configuration from server
        const response = await fetch(`${API_BASE}/api/video/status`);
        const data = await response.json();
        
        if (data.status === 'success' && data.playlist) {
            // Restore playlist
            videoFiles = data.playlist.map(path => ({
                name: path.split('/').pop().split('\\').pop(),
                path: path
            }));
            
            // Restore autoplay/loop state
            videoAutoplay = data.autoplay || false;
            videoLoop = data.loop || false;
            
            // Restore current video
            if (data.current_video) {
                currentVideo = data.current_video.replace(/^[\\\/]+/, '');
            }
            
            // Update UI buttons
            const autoplayBtn = document.getElementById('videoAutoplayBtn');
            const loopBtn = document.getElementById('videoLoopBtn');
            if (autoplayBtn) {
                if (videoAutoplay) {
                    autoplayBtn.classList.remove('btn-outline-primary');
                    autoplayBtn.classList.add('btn-primary');
                } else {
                    autoplayBtn.classList.remove('btn-primary');
                    autoplayBtn.classList.add('btn-outline-primary');
                }
            }
            if (loopBtn) {
                if (videoLoop) {
                    loopBtn.classList.remove('btn-outline-primary');
                    loopBtn.classList.add('btn-primary');
                } else {
                    loopBtn.classList.remove('btn-primary');
                    loopBtn.classList.add('btn-outline-primary');
                }
            }
            
            // Video playlist loaded successfully
        } else {
            // Start with empty playlist
            videoFiles = [];
        }
    } catch (error) {
        console.error('❌ Failed to load video playlist:', error);
        videoFiles = [];
    }
    
    renderVideoPlaylist();
}

function renderVideoPlaylist() {
    const container = document.getElementById('videoPlaylist');
    
    if (videoFiles.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="width: 100%; padding: 2rem; text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📂</div>
                <p style="margin: 0.5rem 0;">Playlist leer</p>
                <small style="color: var(--text-secondary, #999);">Drag & Drop aus Files Tab</small>
            </div>
        `;
        return;
    }
    
    // Build HTML with drop zones between items
    let html = '';
    videoFiles.forEach((video, index) => {
        // Normalisiere Pfade für Vergleich (entferne führende Slashes)
        const normalizedVideoPath = video.path.replace(/^[\\\/]+/, '');
        const normalizedCurrent = currentVideo ? currentVideo.replace(/^[\\\/]+/, '') : null;
        const isActive = normalizedCurrent === normalizedVideoPath;
        
        // Drop zone before item
        html += `<div class="drop-zone" data-drop-index="${index}" data-playlist="video"></div>`;
        
        // Playlist item
        html += `
            <div class="playlist-item ${isActive ? 'active' : ''}" 
                 data-video-index="${index}"
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
    
    // Playlist item handlers (click and dragstart)
    container.querySelectorAll('.playlist-item').forEach((item) => {
        const index = parseInt(item.dataset.videoIndex);
        
        // Click handler - nur abspielen, NICHT zur Playlist hinzufügen
        item.addEventListener('click', async (e) => {
            if (!isDragging && !e.target.classList.contains('playlist-item-remove')) {
                await loadVideoFile(videoFiles[index].path);
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
                e.dataTransfer.dropEffect = 'move';
            }
            zone.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', (e) => {
            zone.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('drag-over');
            
            const dropIndex = parseInt(zone.dataset.dropIndex);
            
            // Check if dropping a file from file browser
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                console.log('🎯 DROP FILE from browser at index:', dropIndex, 'path:', videoPath);
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: Date.now() + Math.random()
                };
                videoFiles.splice(dropIndex, 0, newVideo);
                renderVideoPlaylist();
                console.log(`📋 Added file ${fileName} at position ${dropIndex}`);
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
            }
            
            return false;
        });
    });
    
    // Sync playlist to player after rendering
    updateVideoPlaylist().catch(err => console.error('Failed to sync video playlist:', err));
}

// Load video file WITHOUT adding to playlist (used for playlist clicks)
window.loadVideoFile = async function(videoPath) {
    try {
        // NEW: Use unified API
        const response = await fetch(`${API_BASE}/api/player/video/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentVideo = videoPath.replace(/^[\\\/]+/, '');
            renderVideoPlaylist();
            
            // NEW: Store clip ID and path
            selectedClipId = data.clip_id;
            selectedClipPath = videoPath;
            selectedClipPlayerType = 'video';
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
        const response = await fetch(`${API_BASE}/api/video/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            currentVideo = videoPath.replace(/^[\\\/]+/, '');
            
            // Always add to playlist (allow duplicates)
            const filename = videoPath.split('/').pop();
            const folder = videoPath.includes('/') ? videoPath.split('/')[0] : 'root';
            videoFiles.push({
                filename: filename,
                path: videoPath,
                folder: folder,
                name: filename,
                id: Date.now() + Math.random() // Unique ID for each entry
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

window.removeFromVideoPlaylist = function(index) {
    const video = videoFiles[index];
    videoFiles.splice(index, 1);
    
    // If removed video was current, clear current
    if (currentVideo === video.path) {
        currentVideo = null;
    }
    
    renderVideoPlaylist();
};

// ========================================
// VIDEO PLAYER CONTROLS
// ========================================

window.playVideo = async function() {
    await fetch(`${API_BASE}/api/play`, { method: 'POST' });
};

window.pauseVideo = async function() {
    await fetch(`${API_BASE}/api/pause`, { method: 'POST' });
};

window.stopVideo = async function() {
    await fetch(`${API_BASE}/api/stop`, { method: 'POST' });
};

window.restartVideo = async function() {
    await fetch(`${API_BASE}/api/restart`, { method: 'POST' });
};

window.nextVideo = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/video/next`, { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'success') {
            currentVideo = data.video;
            renderVideoPlaylist();
            console.log('⏭️ Next video:', data.video);
        } else {
            console.error('Failed to load next video:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading next video:', error);
    }
};

window.previousVideo = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/video/previous`, { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'success') {
            currentVideo = data.video;
            renderVideoPlaylist();
            console.log('⏮️ Previous video:', data.video);
        } else {
            console.error('Failed to load previous video:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading previous video:', error);
    }
};

// Autoplay & Loop Toggle für Video Player
window.toggleVideoAutoplay = async function() {
    videoAutoplay = !videoAutoplay;
    const btn = document.getElementById('videoAutoplayBtn');
    if (videoAutoplay) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast('Video Autoplay aktiviert', 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast('Video Autoplay deaktiviert', 'info');
    }
    
    // Update Player ZUERST - damit autoplay flag gesetzt ist
    await updateVideoPlaylist();
    
    // Dann starte Wiedergabe wenn autoplay aktiviert und Playlist vorhanden
    if (videoAutoplay && videoFiles.length > 0) {
        const statusResponse = await fetch(`${API_BASE}/api/video/status`);
        const statusData = await statusResponse.json();
        if (statusData.status === 'success' && !statusData.is_playing) {
            // Lade und starte erstes Video wenn keins läuft
            await loadVideoFile(videoFiles[0].path);
            await playVideo();
            console.log('🎬 Autoplay: Starte erstes Video');
        }
    }
};

window.toggleVideoLoop = async function() {
    videoLoop = !videoLoop;
    const btn = document.getElementById('videoLoopBtn');
    if (videoLoop) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast('Video Loop aktiviert', 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast('Video Loop deaktiviert', 'info');
    }
    // Update Player
    await updateVideoPlaylist();
};

// Sendet aktuelle Playlist an Video Player
async function updateVideoPlaylist() {
    try {
        const response = await fetch(`${API_BASE}/api/video/playlist/set`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                playlist: videoFiles.map(v => v.path),
                autoplay: videoAutoplay,
                loop: videoLoop
            })
        });
        const data = await response.json();
        // Playlist updated successfully
    } catch (error) {
        console.error('❌ Error updating video playlist:', error);
    }
}


// ========================================
// ART-NET PLAYLIST
// ========================================

let artnetFiles = [];
let currentArtnet = null;

async function loadArtnetPlaylist() {
    try {
        // Load player configuration from server
        const response = await fetch(`${API_BASE}/api/artnet/video/status`);
        const data = await response.json();
        
        if (data.status === 'success' && data.playlist) {
            // Restore playlist
            artnetFiles = data.playlist.map(path => ({
                name: path.split('/').pop().split('\\').pop(),
                path: path
            }));
            
            // Restore autoplay/loop state
            artnetAutoplay = data.autoplay || false;
            artnetLoop = data.loop || false;
            
            // Restore current Art-Net video
            if (data.current_video) {
                currentArtnet = data.current_video.replace(/^[\\\/]+/, '');
            }
            
            // Update UI buttons
            const autoplayBtn = document.getElementById('artnetAutoplayBtn');
            const loopBtn = document.getElementById('artnetLoopBtn');
            if (autoplayBtn) {
                if (artnetAutoplay) {
                    autoplayBtn.classList.remove('btn-outline-primary');
                    autoplayBtn.classList.add('btn-primary');
                } else {
                    autoplayBtn.classList.remove('btn-primary');
                    autoplayBtn.classList.add('btn-outline-primary');
                }
            }
            if (loopBtn) {
                if (artnetLoop) {
                    loopBtn.classList.remove('btn-outline-primary');
                    loopBtn.classList.add('btn-primary');
                } else {
                    loopBtn.classList.remove('btn-primary');
                    loopBtn.classList.add('btn-outline-primary');
                }
            }
        } else {
            // Start with empty playlist
            artnetFiles = [];
        }
    } catch (error) {
        console.error('❌ Failed to load Art-Net playlist:', error);
        artnetFiles = [];
    }
    
    renderArtnetPlaylist();
}

function renderArtnetPlaylist() {
    const container = document.getElementById('artnetPlaylist');
    
    if (artnetFiles.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="width: 100%; padding: 2rem; text-align: center;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">📂</div>
                <p style="margin: 0.5rem 0;">Playlist leer</p>
                <small style="color: var(--text-secondary, #999);">Drag & Drop aus Files Tab</small>
            </div>
        `;
        return;
    }
    
    // Build HTML with drop zones between items
    let html = '';
    artnetFiles.forEach((video, index) => {
        // Normalisiere Pfade für Vergleich (entferne führende Slashes)
        const normalizedVideoPath = video.path.replace(/^[\\\/]+/, '');
        const normalizedCurrent = currentArtnet ? currentArtnet.replace(/^[\\\/]+/, '') : null;
        const isActive = normalizedCurrent === normalizedVideoPath;
        
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
    
    // Playlist item handlers (click and dragstart)
    container.querySelectorAll('.playlist-item').forEach((item) => {
        const index = parseInt(item.dataset.artnetIndex);
        
        // Click handler - nur abspielen, NICHT zur Playlist hinzufügen
        item.addEventListener('click', async (e) => {
            if (!isDragging && !e.target.classList.contains('playlist-item-remove')) {
                await loadArtnetFile(artnetFiles[index].path);
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
                e.dataTransfer.dropEffect = 'move';
            }
            zone.classList.add('drag-over');
        });
        
        zone.addEventListener('dragleave', (e) => {
            zone.classList.remove('drag-over');
        });
        
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            zone.classList.remove('drag-over');
            
            const dropIndex = parseInt(zone.dataset.dropIndex);
            
            // Check if dropping a file from file browser
            const videoPath = e.dataTransfer.getData('video-path');
            if (videoPath) {
                console.log('🎯 ARTNET DROP FILE from browser at index:', dropIndex, 'path:', videoPath);
                const fileName = videoPath.split(/[/\\]/).pop();
                const newVideo = {
                    path: videoPath,
                    name: fileName,
                    id: Date.now() + Math.random()
                };
                artnetFiles.splice(dropIndex, 0, newVideo);
                renderArtnetPlaylist();
                console.log(`📋 Added file ${fileName} at position ${dropIndex}`);
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
    
    // Sync playlist to player after rendering
    updateArtnetPlaylist().catch(err => console.error('Failed to sync artnet playlist:', err));
}

// Load Art-Net video file WITHOUT adding to playlist (used for playlist clicks)
window.loadArtnetFile = async function(videoPath) {
    try {
        // NEW: Use unified API
        const response = await fetch(`${API_BASE}/api/player/artnet/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentArtnet = videoPath.replace(/^[\\\/]+/, '');
            renderArtnetPlaylist();
            
            // NEW: Store clip ID and path
            selectedClipId = data.clip_id;
            selectedClipPath = videoPath;
            selectedClipPlayerType = 'artnet';
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
        const response = await fetch(`${API_BASE}/api/artnet/video/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: videoPath })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            currentArtnet = videoPath.replace(/^[\\\/]+/, '');
            
            // Always add to playlist (allow duplicates)
            const filename = videoPath.split('/').pop();
            const folder = videoPath.includes('/') ? videoPath.split('/')[0] : 'root';
            artnetFiles.push({
                filename: filename,
                path: videoPath,
                folder: folder,
                name: filename,
                id: Date.now() + Math.random() // Unique ID for each entry
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

window.removeFromArtnetPlaylist = function(index) {
    const video = artnetFiles[index];
    artnetFiles.splice(index, 1);
    
    // If removed video was current, clear current
    if (currentArtnet === video.path) {
        currentArtnet = null;
    }
    
    renderArtnetPlaylist();
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
// ART-NET PLAYER CONTROLS
// ========================================

window.playArtnet = async function() {
    await fetch(`${API_BASE}/api/artnet/play`, { method: 'POST' });
};

window.pauseArtnet = async function() {
    await fetch(`${API_BASE}/api/artnet/pause`, { method: 'POST' });
};

window.stopArtnet = async function() {
    await fetch(`${API_BASE}/api/artnet/stop`, { method: 'POST' });
};

window.restartArtnet = async function() {
    await fetch(`${API_BASE}/api/artnet/restart`, { method: 'POST' });
};

window.nextArtnet = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/artnet/video/next`, { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'success') {
            currentArtnet = data.video;
            renderArtnetPlaylist();
            console.log('⏭️ Next Art-Net video:', data.video);
        } else {
            console.error('Failed to load next Art-Net video:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading next Art-Net video:', error);
    }
};

window.previousArtnet = async function() {
    try {
        const response = await fetch(`${API_BASE}/api/artnet/video/previous`, { method: 'POST' });
        const data = await response.json();
        
        if (data.status === 'success') {
            currentArtnet = data.video;
            renderArtnetPlaylist();
            console.log('⏮️ Previous Art-Net video:', data.video);
        } else {
            console.error('Failed to load previous Art-Net video:', data.message);
        }
    } catch (error) {
        console.error('❌ Error loading previous Art-Net video:', error);
    }
};

// Autoplay & Loop Toggle für Art-Net Player
window.toggleArtnetAutoplay = async function() {
    artnetAutoplay = !artnetAutoplay;
    const btn = document.getElementById('artnetAutoplayBtn');
    if (artnetAutoplay) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast('Art-Net Autoplay aktiviert', 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast('Art-Net Autoplay deaktiviert', 'info');
    }
    
    // Update Player ZUERST - damit autoplay flag gesetzt ist
    await updateArtnetPlaylist();
    
    // Dann starte Wiedergabe wenn autoplay aktiviert und Playlist vorhanden
    if (artnetAutoplay && artnetFiles.length > 0) {
        const statusResponse = await fetch(`${API_BASE}/api/artnet/video/status`);
        const statusData = await statusResponse.json();
        if (statusData.status === 'success' && !statusData.is_playing) {
            // Lade und starte erstes Video wenn keins läuft
            await loadArtnetFile(artnetFiles[0].path);
            await playArtnet();
            console.log('🎬 Art-Net Autoplay: Starte erstes Video');
        }
    }
};

window.toggleArtnetLoop = async function() {
    artnetLoop = !artnetLoop;
    const btn = document.getElementById('artnetLoopBtn');
    if (artnetLoop) {
        btn.classList.remove('btn-outline-primary');
        btn.classList.add('btn-primary');
        showToast('Art-Net Loop aktiviert', 'success');
    } else {
        btn.classList.remove('btn-primary');
        btn.classList.add('btn-outline-primary');
        showToast('Art-Net Loop deaktiviert', 'info');
    }
    // Update Player
    await updateArtnetPlaylist();
};

// Sendet aktuelle Playlist an Art-Net Player
async function updateArtnetPlaylist() {
    try {
        const response = await fetch(`${API_BASE}/api/artnet/video/playlist/set`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                playlist: artnetFiles.map(v => v.path),
                autoplay: artnetAutoplay,
                loop: artnetLoop
            })
        });
        const data = await response.json();
        // Art-Net playlist updated successfully
    } catch (error) {
        console.error('❌ Error updating Art-Net playlist:', error);
    }
}

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
    const icon = selectedClipPlayerType === 'video' ? '🎬' : '🎨';
    const clipName = selectedClipPath ? selectedClipPath.split('/').pop() : 'No Clip';
    title.innerHTML = `<span class="player-icon">${icon}</span> ${clipName}`;
    
    // Save expanded states
    const expandedStates = new Set();
    container.querySelectorAll('.effect-item.expanded').forEach(item => {
        expandedStates.add(item.id);
    });
    
    if (clipEffects.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">✨</div>
                <h6>No Clip Effects</h6>
                <p>Add effects from the left panel</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = clipEffects.map((effect, index) => 
        renderEffectItem(effect, index, 'clip')
    ).join('');
    
    // Restore expanded states after rerender
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
        
        if (data.status === 'success') {
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
        if (data.status === 'success') {
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
        
        if (loadData.status === 'success') {
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
            
            if (data.status === 'success') {
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

// Cleanup
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
});
