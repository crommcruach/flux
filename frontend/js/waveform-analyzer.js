import WaveSurfer from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/wavesurfer.esm.js';
import RegionsPlugin from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/regions.esm.js';
import TimelinePlugin from 'https://cdn.jsdelivr.net/npm/wavesurfer.js@7/dist/plugins/timeline.esm.js';

let wavesurfer = null;
let regions = null;
let timeline = null;
let splits = []; // Array of split times in seconds
let slots = []; // Array of {start, end, clipName}
let currentSlotIndex = -1;
let loopingSlot = null; // {start, end} or null if not looping
let currentAudioPath = null; // Track current audio file path on server

// Initialize WaveSurfer
function initWaveSurfer() {
    if (wavesurfer) {
        wavesurfer.destroy();
    }
    
    wavesurfer = WaveSurfer.create({
        container: '#waveform',
        waveColor: '#667eea',
        progressColor: '#5568d3',
        cursorColor: '#e74c3c',
        barWidth: 2,
        barGap: 1,
        height: 80,
        normalize: true,
        backend: 'WebAudio'
    });
    
    // Add regions plugin
    regions = wavesurfer.registerPlugin(RegionsPlugin.create());
    
    // Add timeline plugin
    timeline = wavesurfer.registerPlugin(TimelinePlugin.create({
        height: 15,
        timeInterval: 1,
        primaryLabelInterval: 5,
        style: {
            fontSize: '10px',
            color: '#a0a0a0'
        }
    }));
    
    // Event listeners
    wavesurfer.on('ready', onWaveformReady);
    wavesurfer.on('audioprocess', updatePlaybackInfo);
    wavesurfer.on('click', onWaveformClick);
    
    // Region events
    regions.on('region-created', onRegionCreated);
    regions.on('region-clicked', (region, e) => {
        if (e.button === 2) { // Right click
            e.preventDefault();
            e.stopPropagation();
            removeRegion(region);
            return false;
        }
    });
    regions.on('region-updated', onRegionResized);
    
    // Disable drag selection to avoid conflicts
    regions.enableDragSelection({
        color: 'rgba(102, 126, 234, 0.1)'
    });
}

function onWaveformReady() {
    document.getElementById('previewBtn').disabled = false;
    document.getElementById('playBtn').disabled = false;
    document.getElementById('pauseBtn').disabled = false;
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('clearSplitsBtn').disabled = false;
    
    const duration = wavesurfer.getDuration();
    document.getElementById('duration').textContent = formatTime(duration);
    
    updateSlots();
}

async function onWaveformClick(relativeX) {
    const duration = wavesurfer.getDuration();
    const time = relativeX * duration;
    await addSplitToBackend(time);
}

function onRegionCreated(region) {
    // Add contextmenu handler to catch right-click
    const regionEl = region.element;
    if (regionEl) {
        regionEl.addEventListener('contextmenu', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            await removeSplitFromBackend(region.start);
            return false;
        });
    }
}

function onRegionResized(region) {
    handleRegionResize(region);
}

function handleRegionResize(region) {
    const duration = wavesurfer.getDuration();
    const newStart = Math.round(region.start * 100) / 100;
    const newEnd = Math.round(region.end * 100) / 100;
    const slotIndex = region.slotIndex;
    
    // Get all current points
    const allPoints = [0, ...splits, duration];
    
    // Check if this is a left resize (start changed) or right resize (end changed)
    const originalStart = allPoints[slotIndex];
    const originalEnd = allPoints[slotIndex + 1];
    
    const leftResized = Math.abs(newStart - originalStart) > 0.01;
    const rightResized = Math.abs(newEnd - originalEnd) > 0.01;
    
    if (leftResized && slotIndex > 0) {
        // Left side resize - adjust split to the left
        const leftSplitIndex = slotIndex - 1;
        
        // Check if we're shrinking (moving right) or expanding (moving left)
        if (newStart < originalStart) {
            // Expanding left - check if we overlap previous slot completely
            const prevSlotStart = allPoints[slotIndex - 1];
            
            if (newStart <= prevSlotStart + 0.1) {
                // Remove the previous split completely
                splits.splice(leftSplitIndex, 1);
            } else {
                // Just adjust the split
                splits[leftSplitIndex] = newStart;
            }
        } else {
            // Shrinking - moving split right
            splits[leftSplitIndex] = newStart;
        }
    }
    
    if (rightResized && slotIndex < allPoints.length - 2) {
        // Right side resize - adjust split to the right
        const rightSplitIndex = slotIndex;
        
        // Check if we're shrinking (moving left) or expanding (moving right)
        if (newEnd > originalEnd) {
            // Expanding right - check if we overlap next slot completely
            const nextSlotEnd = allPoints[slotIndex + 2];
            
            if (newEnd >= nextSlotEnd - 0.1) {
                // Remove the next split completely
                splits.splice(rightSplitIndex, 1);
            } else {
                // Just adjust the split
                splits[rightSplitIndex] = newEnd;
            }
        } else {
            // Shrinking - moving split left
            splits[rightSplitIndex] = newEnd;
        }
    }
    
    // Ensure splits are sorted
    splits.sort((a, b) => a - b);
    
    // Update everything
    updateRegions();
    updateSlots();
}

function addSplit(time) {
    // Round to 2 decimals
    time = Math.round(time * 100) / 100;
    
    // Don't add if too close to start or end
    const duration = wavesurfer.getDuration();
    if (time < 0.1 || time > duration - 0.1) return;
    
    // Don't add if too close to existing split
    for (let split of splits) {
        if (Math.abs(split - time) < 0.5) return;
    }
    
    splits.push(time);
    splits.sort((a, b) => a - b);
    
    updateRegions();
    updateSlots();
}

function removeRegion(region) {
    // Find the split at the end of this region (right edge)
    // Or use the slotIndex to determine which split to remove
    const slotIndex = region.slotIndex;
    
    if (slotIndex === undefined || slotIndex < 0) return;
    
    // If this is not the last slot, remove the split at the end of this region
    const duration = wavesurfer.getDuration();
    const allPoints = [0, ...splits, duration];
    
    if (slotIndex < allPoints.length - 2) {
        // Remove the split at the right edge of this region
        splits.splice(slotIndex, 1);
    } else if (slotIndex > 0) {
        // If it's the last slot, remove the split at the left edge
        splits.splice(slotIndex - 1, 1);
    }
    
    updateRegions();
    updateSlots();
}

function updateRegions() {
    // Clear all regions
    regions.clearRegions();
    
    if (splits.length === 0) return;
    
    const duration = wavesurfer.getDuration();
    const allPoints = [0, ...splits, duration];
    
    // Create regions for each slot
    const colors = [
        'rgba(102, 126, 234, 0.2)',
        'rgba(76, 209, 196, 0.2)',
        'rgba(255, 107, 107, 0.2)',
        'rgba(255, 211, 61, 0.2)',
        'rgba(118, 75, 162, 0.2)',
        'rgba(69, 183, 209, 0.2)'
    ];
    
    for (let i = 0; i < allPoints.length - 1; i++) {
        const region = regions.addRegion({
            start: allPoints[i],
            end: allPoints[i + 1],
            color: colors[i % colors.length],
            drag: false,
            resize: true,
            minLength: 0.1,
            maxLength: duration
        });
        
        // Store slot index on region
        region.slotIndex = i;
    }
}

function updateSplitTime(splitIndex, newTime) {
    if (splitIndex < 0 || splitIndex >= splits.length) return;
    
    const duration = wavesurfer.getDuration();
    
    // Get adjacent split times for validation
    const prevTime = splitIndex > 0 ? splits[splitIndex - 1] : 0;
    const nextTime = splitIndex < splits.length - 1 ? splits[splitIndex + 1] : duration;
    
    // Ensure split stays between adjacent splits with 0.1s minimum spacing
    newTime = Math.max(prevTime + 0.1, Math.min(nextTime - 0.1, newTime));
    newTime = Math.round(newTime * 100) / 100;
    
    splits[splitIndex] = newTime;
    splits.sort((a, b) => a - b);
    
    updateRegions();
    updateSlots();
}

function updateSlots() {
    if (!wavesurfer) return;
    
    const duration = wavesurfer.getDuration();
    const allPoints = [0, ...splits, duration];
    
    slots = [];
    for (let i = 0; i < allPoints.length - 1; i++) {
        const existingSlot = slots[i];
        slots.push({
            index: i,
            start: allPoints[i],
            end: allPoints[i + 1],
            clipName: existingSlot?.clipName || `Clip ${i}`
        });
    }
    
    renderSlots();
}

function renderSlots() {
    const container = document.getElementById('slotsList');
    
    if (slots.length === 0) {
        container.innerHTML = '<div style="color: #666; font-size: 0.8rem;">No slots. Click on waveform to create splits.</div>';
        return;
    }
    
    container.innerHTML = '';
    
    slots.forEach((slot, index) => {
        const div = document.createElement('div');
        div.className = 'slot-item';
        if (index === currentSlotIndex) {
            div.classList.add('active');
        }
        if (loopingSlot && loopingSlot.index === index) {
            div.classList.add('looping');
        }
        
        // Add click handler to play/loop this slot
        div.addEventListener('click', (e) => {
            // Don't trigger if clicking on inputs or buttons
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') {
                return;
            }
            
            if (loopingSlot && loopingSlot.index === index) {
                // Stop looping if clicking the same slot
                wavesurfer.pause();
                stopSlotLoop();
            } else {
                // Start looping this slot
                playSlotLoop(index);
            }
        });
        
        // Build split editor HTML if there's a split after this slot
        let splitEditorHTML = '';
        if (index < slots.length - 1) {
            const splitTime = slot.end;
            splitEditorHTML = `
                <div class="slot-split-editor">
                    <span class="split-label">Split at:</span>
                    <input type="number" 
                           class="split-time-input" 
                           value="${splitTime.toFixed(2)}" 
                           step="0.01" 
                           data-split-index="${index}">
                </div>
            `;
        }
        
        div.innerHTML = `
            <div class="slot-header">
                <div class="slot-title">
                    Slot ${slot.index}
                    <svg class="countdown-circle" data-slot-index="${index}" style="display: none;">
                        <circle cx="10" cy="10" r="8" fill="none" stroke="#3c3c3c" stroke-width="2"/>
                        <circle cx="10" cy="10" r="8" fill="none" stroke="#667eea" stroke-width="2" 
                                class="countdown-progress" 
                                stroke-dasharray="50.265" 
                                stroke-dashoffset="0"/>
                    </svg>
                    <div class="slot-time">${formatTime(slot.start)} - ${formatTime(slot.end)} (${formatTime(slot.end - slot.start)})</div>
                </div>
            </div>
            ${splitEditorHTML}
        `;
        
        // Add split time editor listeners
        const splitInput = div.querySelector('.split-time-input');
        if (splitInput) {
            splitInput.addEventListener('change', (e) => {
                const newTime = parseFloat(e.target.value);
                updateSplitTime(index, newTime);
            });
        }
        
        container.appendChild(div);
        
        // Add spacer after each slot (except the last one)
        if (index < slots.length - 1) {
            const spacer = document.createElement('div');
            spacer.className = 'slot-spacer';
            container.appendChild(spacer);
        }
    });
}

function updatePlaybackInfo() {
    const currentTime = wavesurfer.getCurrentTime();
    document.getElementById('currentTime').textContent = formatTime(currentTime);
    
    // Handle slot looping
    if (loopingSlot && currentTime >= loopingSlot.end) {
        wavesurfer.seekTo(loopingSlot.start / wavesurfer.getDuration());
    }
    
    // Find current slot
    let newSlotIndex = -1;
    for (let i = 0; i < slots.length; i++) {
        if (currentTime >= slots[i].start && currentTime < slots[i].end) {
            newSlotIndex = i;
            break;
        }
    }
    
    // Update countdown circles
    document.querySelectorAll('.countdown-circle').forEach(circle => {
        const slotIndex = parseInt(circle.dataset.slotIndex);
        const slot = slots[slotIndex];
        
        if (slotIndex === newSlotIndex && currentTime >= slot.start && currentTime < slot.end) {
            // Show and update countdown for current slot
            circle.style.display = 'inline-block';
            const slotDuration = slot.end - slot.start;
            const elapsed = currentTime - slot.start;
            const progress = elapsed / slotDuration;
            const circumference = 50.265; // 2 * PI * 8
            const offset = circumference * (1 - progress);
            
            const progressCircle = circle.querySelector('.countdown-progress');
            progressCircle.style.strokeDashoffset = offset;
        } else {
            circle.style.display = 'none';
        }
    });
    
    if (newSlotIndex !== currentSlotIndex) {
        currentSlotIndex = newSlotIndex;
        document.getElementById('currentSlot').textContent = 
            currentSlotIndex >= 0 ? `Slot ${currentSlotIndex}` : 'None';
        renderSlots();
    }
}

function playSlotLoop(slotIndex) {
    if (slotIndex < 0 || slotIndex >= slots.length) return;
    
    const slot = slots[slotIndex];
    loopingSlot = { start: slot.start, end: slot.end, index: slotIndex };
    
    // Seek to start of slot and play
    wavesurfer.seekTo(slot.start / wavesurfer.getDuration());
    wavesurfer.play();
    
    renderSlots();
}

function stopSlotLoop() {
    loopingSlot = null;
    renderSlots();
}

function formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// API Integration Functions
async function addSplitToBackend(time) {
    try {
        const response = await fetch('/api/sequencer/split/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time: time })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`✅ Split added at ${time.toFixed(2)}s`);
            await fetchAndRenderTimeline();
        } else {
            console.warn('⚠️ Split not added (too close to existing split or boundary)');
        }
    } catch (error) {
        console.error('❌ Error adding split:', error);
    }
}

async function removeSplitFromBackend(time) {
    try {
        const response = await fetch('/api/sequencer/split/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ time: time })
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log(`✅ Split removed at ${time.toFixed(2)}s`);
            await fetchAndRenderTimeline();
        } else {
            console.warn('⚠️ Split not found');
        }
    } catch (error) {
        console.error('❌ Error removing split:', error);
    }
}

async function fetchAndRenderTimeline() {
    try {
        const response = await fetch('/api/sequencer/timeline');
        const timeline = await response.json();
        
        if (timeline.splits) {
            // Update local state
            splits = timeline.splits;
            slots = timeline.slots || [];
            
            // Update WaveSurfer regions to match backend splits
            updateRegions();
            renderSlots();
            
            console.log('📊 Timeline updated:', timeline);
        }
    } catch (error) {
        console.error('❌ Error fetching timeline:', error);
    }
}

async function uploadAudioFile(file) {
    if (!file) return;
    
    // Validate audio file
    const validExtensions = ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac'];
    const extension = file.name.split('.').pop().toLowerCase();
    if (!validExtensions.includes(extension)) {
        alert('Invalid file type. Please upload MP3, WAV, OGG, FLAC, M4A, or AAC.');
        return;
    }
    
    // Upload file to backend
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        document.getElementById('waveformFileInfo').textContent = `📤 Uploading ${file.name}...`;
        
        const response = await fetch('/api/sequencer/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            console.log('✅ Audio uploaded:', result.metadata);
            document.getElementById('waveformFileInfo').textContent = `📊 ${result.filename}`;
            await loadAudioFromServer(result.path);
        } else {
            alert('Upload failed: ' + result.error);
            document.getElementById('waveformFileInfo').textContent = 'No file loaded';
        }
    } catch (error) {
        console.error('❌ Upload error:', error);
        alert('Failed to upload audio file');
        document.getElementById('waveformFileInfo').textContent = 'No file loaded';
    }
}

async function loadAudioFromServer(serverPath) {
    try {
        // Store the server path
        currentAudioPath = serverPath;
        
        // Load audio via backend sequencer
        const response = await fetch('/api/sequencer/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_path: serverPath })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Failed to load audio');
        }
        
        console.log('🎵 Audio loaded from backend:', result.metadata);
        
        // Initialize WaveSurfer if needed
        initWaveSurfer();
        
        // Load audio into WaveSurfer from server
        const audioUrl = `/api/sequencer/audio/${encodeURIComponent(serverPath)}`;
        await wavesurfer.load(audioUrl);
        
        // After loading, fetch initial timeline (may have saved splits)
        await fetchAndRenderTimeline();
    } catch (error) {
        console.error('❌ Error loading audio:', error);
        alert('Failed to load audio: ' + error.message);
    }
}

async function openFileBrowserModal() {
    try {
        const response = await fetch('/api/sequencer/browse-audio');
        const result = await response.json();
        
        if (result.success) {
            renderFileList(result.files);
            const modalElement = document.getElementById('sequencerFileBrowserModal');
            const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
            modal.show();
        } else {
            alert('Failed to load audio files: ' + result.error);
        }
    } catch (error) {
        console.error('❌ Error loading file list:', error);
        alert('Failed to browse audio files');
    }
}

function renderFileList(files) {
    const tbody = document.getElementById('sequencerFileList');
    tbody.innerHTML = '';
    
    if (files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">No audio files found</td></tr>';
        return;
    }
    
    files.forEach(file => {
        const row = document.createElement('tr');
        row.style.cursor = 'pointer';
        row.innerHTML = `
            <td>${file.filename}</td>
            <td><small class="text-muted">${file.folder}</small></td>
            <td><small class="text-muted">${formatBytes(file.size)}</small></td>
        `;
        
        row.addEventListener('click', () => selectAudioFile(file.path));
        tbody.appendChild(row);
    });
}

async function selectAudioFile(filePath) {
    try {
        const modal = bootstrap.Modal.getInstance(document.getElementById('sequencerFileBrowserModal'));
        modal.hide();
        
        const filename = filePath.split('/').pop();
        document.getElementById('waveformFileInfo').textContent = `📂 Loading ${filename}...`;
        
        await loadAudioFromServer(filePath);
        
        document.getElementById('waveformFileInfo').textContent = `📊 ${filename}`;
    } catch (error) {
        console.error('❌ Error selecting audio:', error);
        document.getElementById('waveformFileInfo').textContent = 'No file loaded';
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// Load audio file helper (for local file input - legacy)
function loadAudioFile(file) {
    if (!file) return;
    
    // Check if it's an audio file
    if (!file.type.startsWith('audio/')) {
        alert('Please select an audio file (MP3, WAV, etc.)');
        return;
    }
    
    // Use upload instead
    uploadAudioFile(file);
}

// Initialize event handlers
function initApp() {
    // Click on preview area to open file browser
    const previewArea = document.getElementById('preview-area-waveform');
    if (previewArea) {
        previewArea.addEventListener('click', openFileBrowserModal);
    }
    
    // File search filter
    const fileSearch = document.getElementById('sequencerFileSearch');
    if (fileSearch) {
        fileSearch.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const rows = document.querySelectorAll('#sequencerFileList tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
    
    // Button handlers
    document.getElementById('audioFileInput').addEventListener('change', (e) => {
        loadAudioFile(e.target.files[0]);
    });
    
    // Drag and drop handlers (previewArea already selected above)
    if (previewArea) {
        previewArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            previewArea.style.borderColor = 'var(--primary-color, #667eea)';
            previewArea.style.background = 'rgba(102, 126, 234, 0.1)';
        });
        
        previewArea.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            previewArea.style.borderColor = '';
            previewArea.style.background = '';
        });
        
        previewArea.addEventListener('drop', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            previewArea.style.borderColor = '';
            previewArea.style.background = '';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                await uploadAudioFile(files[0]);
            }
        });
    }
    
    // Preview button - frontend only (for testing/setup)
    const previewBtn = document.getElementById('previewBtn');
    if (previewBtn) {
        previewBtn.addEventListener('click', () => {
            if (wavesurfer) {
                wavesurfer.play();
                console.log('👁️ Preview playback (frontend only)');
            }
        });
    }
    
    // Play Synced button - triggers backend audio + playlist sync
    const playBtn = document.getElementById('playBtn');
    if (playBtn) {
        playBtn.addEventListener('click', async () => {
            if (wavesurfer) {
                // Stop and reset to beginning before playing
                wavesurfer.stop();
                wavesurfer.play();
                // Call backend play endpoint
                try {
                    await fetch('/api/sequencer/play', { method: 'POST' });
                    console.log('▶️ Synced playback started');
                } catch (error) {
                    console.error('❌ Error calling play endpoint:', error);
                }
            }
        });
    }
    
    const pauseBtn = document.getElementById('pauseBtn');
    if (pauseBtn) {
        pauseBtn.addEventListener('click', async () => {
            if (wavesurfer) {
                wavesurfer.pause();
                // Call backend pause endpoint
                try {
                    await fetch('/api/sequencer/pause', { method: 'POST' });
                } catch (error) {
                    console.error('❌ Error calling pause endpoint:', error);
                }
            }
        });
    }
    
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', async () => {
            if (wavesurfer) {
                wavesurfer.stop();
                currentSlotIndex = -1;
                document.getElementById('currentSlot').textContent = 'None';
                document.getElementById('currentTime').textContent = '0:00';
                renderSlots();
                // Call backend stop endpoint
                try {
                    await fetch('/api/sequencer/stop', { method: 'POST' });
                } catch (error) {
                    console.error('❌ Error calling stop endpoint:', error);
                }
            }
        });
    }
    
    const clearSplitsBtn = document.getElementById('clearSplitsBtn');
    if (clearSplitsBtn) {
        clearSplitsBtn.addEventListener('click', async () => {
            if (confirm('Clear all splits?')) {
                // Remove splits one by one from backend
                for (const split of [...splits]) {
                    await removeSplitFromBackend(split);
                }
            }
        });
    }
    
    // Prevent context menu on waveform
    const waveformEl = document.getElementById('waveform');
    if (waveformEl) {
        waveformEl.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        });
    }
    
    // Minify toggle
    const minifyBtn = document.getElementById('minifyBtn');
    const slotsContainer = document.getElementById('slotsContainer');
    const waveformContainer = document.querySelector('.waveform-container');
    if (minifyBtn && slotsContainer && waveformContainer) {
        minifyBtn.addEventListener('click', () => {
            slotsContainer.classList.toggle('minified');
            waveformContainer.classList.toggle('minified');
            const isMinified = slotsContainer.classList.contains('minified');
            minifyBtn.textContent = isMinified ? '⬆️' : '⬇️';
            minifyBtn.title = isMinified ? 'Expand' : 'Minify';
        });
    }
    
    // Restore sequencer state on page load
    restoreSequencerState();
}

async function restoreSequencerState() {
    try {
        const response = await fetch('/api/sequencer/status');
        const status = await response.json();
        
        console.log('📋 Restoring sequencer state:', status);
        
        // Restore sequencer mode UI if backend says it's active
        if (status.mode_active) {
            const waveformSection = document.querySelector('.waveform-analyzer-section');
            const btn = document.getElementById('sequencerModeBtn');
            
            if (waveformSection && btn) {
                // Update UI to match backend state
                waveformSection.style.display = 'grid';
                btn.classList.remove('btn-outline-secondary');
                btn.classList.add('btn-success');
                btn.textContent = '🎵 Sequencer: MASTER';
                
                // Update global variable in player.html
                if (typeof window.sequencerModeActive !== 'undefined') {
                    window.sequencerModeActive = true;
                }
                
                console.log('✅ Sequencer mode restored: MASTER');
            }
        }
        
        // Restore audio file and timeline
        if (status.has_audio && status.audio_file) {
            console.log('📂 Restoring audio file:', status.audio_file);
            await loadAudioFromServer(status.audio_file);
            console.log('✅ Audio and timeline restored');
        }
    } catch (error) {
        console.error('❌ Error restoring sequencer state:', error);
    }
}

// Auto-init on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
