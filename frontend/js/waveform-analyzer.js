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
    document.getElementById('playBtn').disabled = false;
    document.getElementById('pauseBtn').disabled = false;
    document.getElementById('stopBtn').disabled = false;
    document.getElementById('clearSplitsBtn').disabled = false;
    
    const duration = wavesurfer.getDuration();
    document.getElementById('duration').textContent = formatTime(duration);
    
    updateSlots();
}

function onWaveformClick(relativeX) {
    const duration = wavesurfer.getDuration();
    const time = relativeX * duration;
    addSplit(time);
}

function onRegionCreated(region) {
    // Add contextmenu handler to catch right-click
    const regionEl = region.element;
    if (regionEl) {
        regionEl.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            e.stopPropagation();
            removeRegion(region);
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

// Load audio file helper
function loadAudioFile(file) {
    if (!file) return;
    
    // Check if it's an audio file
    if (!file.type.startsWith('audio/')) {
        alert('Please select an audio file (MP3, WAV, etc.)');
        return;
    }
    
    document.getElementById('waveformFileInfo').textContent = `📊 ${file.name}`;
    
    initWaveSurfer();
    
    const url = URL.createObjectURL(file);
    wavesurfer.load(url);
}

// Initialize event handlers
function initApp() {
    // Button handlers
    document.getElementById('audioFileInput').addEventListener('change', (e) => {
        loadAudioFile(e.target.files[0]);
    });
    
    // Drag and drop handlers
    const previewArea = document.querySelector('.preview-area-waveform');
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
        
        previewArea.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            previewArea.style.borderColor = '';
            previewArea.style.background = '';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                loadAudioFile(files[0]);
            }
        });
    }
    
    const playBtn = document.getElementById('playBtn');
    if (playBtn) {
        playBtn.addEventListener('click', () => {
            if (wavesurfer) wavesurfer.play();
        });
    }
    
    const pauseBtn = document.getElementById('pauseBtn');
    if (pauseBtn) {
        pauseBtn.addEventListener('click', () => {
            if (wavesurfer) wavesurfer.pause();
        });
    }
    
    const stopBtn = document.getElementById('stopBtn');
    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (wavesurfer) {
                wavesurfer.stop();
                currentSlotIndex = -1;
                document.getElementById('currentSlot').textContent = 'None';
                document.getElementById('currentTime').textContent = '0:00';
                renderSlots();
            }
        });
    }
    
    const clearSplitsBtn = document.getElementById('clearSplitsBtn');
    if (clearSplitsBtn) {
        clearSplitsBtn.addEventListener('click', () => {
            if (confirm('Clear all splits?')) {
                splits = [];
                updateRegions();
                updateSlots();
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
}

// Auto-init on load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
