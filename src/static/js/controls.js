/**
 * Controls.js - Optimized version using common utilities
 * Video/Script player controls with preview and settings
 */

import { 
    loadConfig, 
    initWebSocket, 
    showToast, 
    apiCall, 
    getSocket, 
    isSocketConnected,
    initErrorLogging,
    API_BASE 
} from './common.js';

// ========================================
// PLAYBACK CONTROLS
// ========================================

async function executeCliCommand(command) {
    const result = await apiCall('/console/command', 'POST', { command });
    if (result?.status === 'success') {
        showToast(`Befehl '${command}' ausgeführt`);
        updateStatus();
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
    }
}

// ========================================
// SETTINGS - Optimized with less duplication
// ========================================

const sliderConfig = {
    brightness: {
        selector: 'brightness',
        unit: '%',
        endpoint: '/brightness',
        format: (v) => parseInt(v),
        display: (v) => `${v}%`
    },
    speed: {
        selector: 'speed',
        unit: 'x',
        endpoint: '/speed',
        format: (v) => parseFloat(v),
        display: (v) => `${v.toFixed(1)}x`,
        validate: (v) => v > 0 && v <= 10
    },
    hue: {
        selector: 'hue',
        unit: '°',
        endpoint: '/hue',
        format: (v) => parseInt(v),
        display: (v) => `${v}°`,
        validate: (v) => v >= 0 && v <= 360
    }
};

function createSliderHandlers(config) {
    const { selector, format, display, endpoint, validate } = config;
    
    return {
        updateSlider: (value) => {
            const val = format(value);
            document.getElementById(`${selector}Value`).textContent = display(val);
            document.getElementById(`${selector}Input`).value = val;
        },
        
        updateInput: async (value) => {
            const val = format(value);
            if (isNaN(val) || (validate && !validate(val))) return;
            
            document.getElementById(`${selector}Value`).textContent = display(val);
            document.getElementById(`${selector}Slider`).value = val;
            
            const result = await apiCall(endpoint, 'POST', { value: val });
            if (result) {
                showToast(`${selector.charAt(0).toUpperCase() + selector.slice(1)} auf ${display(val)} gesetzt`);
            }
        }
    };
}

// Create handlers for all sliders
const brightnessHandlers = createSliderHandlers(sliderConfig.brightness);
const speedHandlers = createSliderHandlers(sliderConfig.speed);
const hueHandlers = createSliderHandlers(sliderConfig.hue);

// Export for HTML onchange attributes
window.updateBrightnessSlider = brightnessHandlers.updateSlider;
window.updateBrightnessInput = brightnessHandlers.updateInput;
window.updateSpeedSlider = speedHandlers.updateSlider;
window.updateSpeedInput = speedHandlers.updateInput;
window.updateHueSlider = hueHandlers.updateSlider;
window.updateHueInput = hueHandlers.updateInput;

// ========================================
// ART-NET
// ========================================

async function blackout() {
    const result = await apiCall('/blackout', 'POST');
    if (result) showToast(result.message);
}

async function testPattern(color) {
    const result = await apiCall('/test', 'POST', { color });
    if (result) showToast(`Testmuster: ${color}`);
}

window.blackout = blackout;
window.testPattern = testPattern;

// ========================================
// MEDIA (VIDEOS & SCRIPTS)
// ========================================

async function loadVideos() {
    const result = await apiCall('/videos');
    if (!result?.videos) return;
    
    const mediaList = document.getElementById('mediaList');
    mediaList.innerHTML = '<h3 style="margin-top: 0;">🎬 Videos</h3>';
    
    // Group by channel
    const grouped = result.videos.reduce((acc, video) => {
        const kanal = video.kanal > 0 ? `Kanal ${video.kanal}` : 'Andere';
        (acc[kanal] = acc[kanal] || []).push(video);
        return acc;
    }, {});
    
    // Create collapsible sections
    Object.keys(grouped).sort().forEach((kanal, index) => {
        const videos = grouped[kanal];
        const kanalId = `kanal-${index}`;
        
        const header = document.createElement('div');
        header.className = 'kanal-header';
        header.innerHTML = `
            <span class="kanal-toggle">▶</span>
            <span class="kanal-title">${kanal}</span>
            <span class="kanal-count">${videos.length}</span>
        `;
        header.onclick = () => toggleKanal(kanalId);
        mediaList.appendChild(header);
        
        const container = document.createElement('div');
        container.id = kanalId;
        container.className = 'kanal-videos collapsed';
        
        videos.forEach(video => {
            const div = document.createElement('div');
            div.className = 'video-item';
            div.textContent = video.name;
            div.onclick = (e) => {
                e.stopPropagation();
                loadVideo(video.path, video.name);
            };
            container.appendChild(div);
        });
        
        mediaList.appendChild(container);
    });
    
    showToast(`${result.videos.length} Videos in ${Object.keys(grouped).length} Kanälen`);
}

function toggleKanal(kanalId) {
    const container = document.getElementById(kanalId);
    const toggle = container.previousElementSibling.querySelector('.kanal-toggle');
    
    container.classList.toggle('collapsed');
    toggle.textContent = container.classList.contains('collapsed') ? '▶' : '▼';
}

async function loadVideo(path, name) {
    const relativePath = path.replace(/\\/g, '/');
    const result = await apiCall('/console/command', 'POST', { 
        command: `video:${relativePath}` 
    });
    
    if (result?.status === 'success') {
        showToast(`Video startet: ${name}`);
        updateStatus();
        await executeCliCommand('start');
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
    }
}

async function loadScripts() {
    const result = await apiCall('/scripts');
    if (!result?.scripts) return;
    
    const mediaList = document.getElementById('mediaList');
    mediaList.innerHTML = '<h3 style="margin-top: 0;">📜 Scripts</h3>';
    
    if (result.scripts.length === 0) {
        mediaList.innerHTML += '<p style="text-align: center; color: #999;">Keine Scripts gefunden</p>';
        return;
    }
    
    result.scripts.forEach(script => {
        const div = document.createElement('div');
        div.className = 'video-item';
        div.innerHTML = `
            <div>
                <strong>${script.filename}</strong>
                ${script.description ? `<br><small style="color: #999;">${script.description}</small>` : ''}
            </div>
        `;
        div.onclick = () => loadScript(script.filename);
        mediaList.appendChild(div);
    });
}

async function loadScript(scriptName) {
    const cleanName = scriptName.replace(/\.py$/, '');
    const result = await apiCall('/console/command', 'POST', { 
        command: `script:${cleanName}` 
    });
    
    if (result?.status === 'success') {
        showToast(`Script startet: ${cleanName}`);
        updateStatus();
        await executeCliCommand('start');
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
    }
}

window.loadVideos = loadVideos;
window.loadScripts = loadScripts;
window.executeCliCommand = executeCliCommand;

// ========================================
// STATUS - Optimized update logic
// ========================================

function updateStatusFromWebSocket(data) {
    updatePreview(data);
    
    if (data.active_mode && window.updateActiveModeDisplay) {
        window.updateActiveModeDisplay(data.active_mode);
    }
    
    // Sync sliders efficiently
    const sliderUpdates = {
        brightness: { value: Math.round(data.brightness), display: brightnessHandlers.updateSlider },
        speed: { value: parseFloat(data.speed), display: speedHandlers.updateSlider },
        hue_shift: { value: parseInt(data.hue_shift), display: hueHandlers.updateSlider }
    };
    
    Object.entries(sliderUpdates).forEach(([key, { value, display }]) => {
        if (data[key] !== undefined && !isNaN(value)) {
            display(value);
        }
    });
}

async function updateStatus() {
    const result = await apiCall('/status');
    if (result) updateStatusFromWebSocket(result);
}

// ========================================
// PREVIEW - Optimized with better error handling
// ========================================

let previewStream = null;
let previewRetryCount = 0;
const MAX_PREVIEW_RETRIES = 3;

function initPreview() {
    previewStream = document.getElementById('previewStream');
    if (!previewStream) {
        console.error('Preview Stream Element not found!');
        return;
    }
    
    const streamUrl = `${API_BASE}/preview/stream`;
    
    previewStream.onerror = () => {
        console.error('Preview Stream error');
        
        if (previewRetryCount < MAX_PREVIEW_RETRIES) {
            previewRetryCount++;
            setTimeout(() => {
                console.log(`Retry preview stream (${previewRetryCount}/${MAX_PREVIEW_RETRIES})`);
                previewStream.src = `${streamUrl}?t=${Date.now()}`;
            }, 1000 * previewRetryCount); // Exponential backoff
        }
    };
    
    previewStream.onload = () => {
        console.log('Preview stream loaded:', previewStream.naturalWidth, 'x', previewStream.naturalHeight);
        previewRetryCount = 0; // Reset on success
    };
    
    previewStream.src = streamUrl;
}

function updatePreview(data) {
    const videoName = data.video || data.status?.video_path?.split('\\').pop() || '-';
    document.getElementById('previewVideoName').textContent = videoName;
    
    const isScript = data.is_script || false;
    
    if (isScript) {
        document.getElementById('previewFrame').textContent = 'Endlos';
        document.getElementById('previewProgress').style.width = '100%';
    } else {
        const currentFrame = data.current_frame || 0;
        const totalFrames = data.total_frames || 0;
        document.getElementById('previewFrame').textContent = `${currentFrame}/${totalFrames}`;
        
        const progress = totalFrames > 0 ? (currentFrame / totalFrames * 100) : 0;
        document.getElementById('previewProgress').style.width = `${progress}%`;
    }
}

async function updatePreviewInfo() {
    const [info, traffic] = await Promise.all([
        apiCall('/info'),
        apiCall('/stream/traffic')
    ]);
    
    if (info?.canvas_width && info?.canvas_height) {
        document.getElementById('previewCanvasSize').textContent = 
            `${info.canvas_width}x${info.canvas_height}`;
    }
    
    if (traffic?.preview && traffic?.fullscreen && traffic?.total) {
        const elements = {
            trafficPreview: traffic.preview.formatted,
            trafficPreviewMbps: traffic.preview.mbps,
            trafficFullscreen: traffic.fullscreen.formatted,
            trafficFullscreenMbps: traffic.fullscreen.mbps,
            trafficTotal: traffic.total.formatted,
            trafficTotalMbps: traffic.total.mbps
        };
        
        Object.entries(elements).forEach(([id, text]) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        });
    }
}

function openPreviewWindow() {
    const width = 900, height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    window.open(
        '/fullscreen.html', 
        'FullscreenWindow',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes`
    );
}

window.openPreviewWindow = openPreviewWindow;

// ========================================
// THEME TOGGLE
// ========================================

function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    const themeLabel = document.getElementById('themeLabel');
    
    if (!themeToggle) return;
    
    const savedTheme = localStorage.getItem('theme') || 'light';
    const isDark = savedTheme === 'dark';
    
    if (isDark) {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeToggle.checked = true;
    }
    
    if (themeLabel) {
        themeLabel.textContent = isDark ? 'Dunkel' : 'Hell';
    }
    
    themeToggle.addEventListener('change', () => {
        const isDark = themeToggle.checked;
        
        if (isDark) {
            document.documentElement.setAttribute('data-theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
        }
        
        if (themeLabel) themeLabel.textContent = isDark ? 'Dunkel' : 'Hell';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });
}

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', async () => {
    initErrorLogging();
    await loadConfig();
    
    initWebSocket({
        onStatus: updateStatusFromWebSocket
    });
    
    initThemeToggle();
    initPreview();
    updateStatus();
    updatePreviewInfo();
    
    // Fallback polling
    let POLLING_INTERVAL = 3000;
    setInterval(() => {
        if (!isSocketConnected()) {
            updateStatus();
        }
    }, POLLING_INTERVAL);
    
    // Preview info updates
    setInterval(updatePreviewInfo, 5000);
});
