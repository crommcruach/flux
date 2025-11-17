// ========================================
// CONSTANTS & CONFIGURATION
// ========================================
let API_BASE = 'http://localhost:5000/api';  // Default, wird aus Config geladen
let WEBSOCKET_URL = 'http://localhost:5000';  // Default, wird aus Config geladen
let POLLING_INTERVAL = 3000;  // Default, wird aus Config geladen
let socket = null;
let socketConnected = false;
let lastConsoleLines = 0;

// ========================================
// WEBSOCKET FUNCTIONS
// ========================================

// WebSocket initialisieren
function initWebSocket() {
    socket = io(WEBSOCKET_URL, {
        transports: ['websocket', 'polling']
    });
    
    socket.on('connect', () => {
        console.log('WebSocket verbunden');
        socketConnected = true;
        showToast('WebSocket verbunden', 'success');
    });
    
    socket.on('disconnect', () => {
        console.log('WebSocket getrennt');
        socketConnected = false;
        showToast('WebSocket getrennt', 'error');
    });
    
    socket.on('status', (data) => {
        updateStatusFromWebSocket(data);
    });
    
    socket.on('console_update', (data) => {
        updateConsoleFromWebSocket(data);
    });
    
    socket.on('connect_error', (error) => {
        console.error('WebSocket Fehler:', error);
        socketConnected = false;
    });
}

// ========================================
// UI HELPER FUNCTIONS
// ========================================

// Toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    toast.className = `toast ${type}`;
    toastMessage.textContent = message;
    toast.style.display = 'block';
    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

// ========================================
// API CALL HELPER
// ========================================

// API call helper
async function apiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        if (data) {
            options.body = JSON.stringify(data);
        }
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        const result = await response.json();
        return result;
    } catch (error) {
        showToast(`Fehler: ${error.message}`, 'error');
        return null;
    }
}

// ========================================
// PLAYBACK CONTROLS
// ========================================

async function playVideo() {
    const result = await apiCall('/play', 'POST');
    if (result) showToast(result.message);
    updateStatus();
}

async function stopVideo() {
    const result = await apiCall('/stop', 'POST');
    if (result) showToast(result.message);
    updateStatus();
}

async function pauseVideo() {
    const result = await apiCall('/pause', 'POST');
    if (result) showToast(result.message);
    updateStatus();
}

async function resumeVideo() {
    const result = await apiCall('/resume', 'POST');
    if (result) showToast(result.message);
    updateStatus();
}

async function restartVideo() {
    const result = await apiCall('/restart', 'POST');
    if (result) showToast(result.message);
    updateStatus();
}

// ========================================
// SETTINGS
// ========================================

async function updateBrightness(value) {
    document.getElementById('brightnessValue').textContent = value + '%';
    await apiCall('/brightness', 'POST', { value: parseInt(value) });
}

async function updateSpeed(value) {
    document.getElementById('speedValue').textContent = parseFloat(value).toFixed(1) + 'x';
    await apiCall('/speed', 'POST', { value: parseFloat(value) });
}

async function setFPS() {
    const fps = document.getElementById('fpsInput').value;
    if (fps) {
        const result = await apiCall('/fps', 'POST', { value: parseInt(fps) });
        if (result) showToast(`FPS auf ${fps} gesetzt`);
    }
}

// ========================================
// ART-NET
// ========================================

async function blackout() {
    const result = await apiCall('/blackout', 'POST');
    if (result) showToast(result.message);
}

async function testPattern(color) {
    const result = await apiCall('/test', 'POST', { color: color });
    if (result) showToast(`Testmuster: ${color}`);
}



// ========================================
// VIDEOS
// ========================================

async function loadVideos() {
    const result = await apiCall('/videos', 'GET');
    if (result && result.videos) {
        const videoList = document.getElementById('videoList');
        videoList.innerHTML = '';
        
        // Gruppiere Videos nach Kanal
        const grouped = {};
        result.videos.forEach(video => {
            const kanal = video.kanal > 0 ? `Kanal ${video.kanal}` : 'Andere';
            if (!grouped[kanal]) grouped[kanal] = [];
            grouped[kanal].push(video);
        });
        
        // Erstelle collapsible Sections für jeden Kanal
        Object.keys(grouped).sort().forEach((kanal, index) => {
            const videos = grouped[kanal];
            const kanalId = `kanal-${index}`;
            
            // Kanal Header (collapsible)
            const header = document.createElement('div');
            header.className = 'kanal-header';
            header.innerHTML = `
                <span class="kanal-toggle">▶</span>
                <span class="kanal-title">${kanal}</span>
                <span class="kanal-count">${videos.length}</span>
            `;
            header.onclick = () => toggleKanal(kanalId);
            videoList.appendChild(header);
            
            // Video Container (collapsible content)
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
            
            videoList.appendChild(container);
        });
        
        showToast(`${result.videos.length} Videos in ${Object.keys(grouped).length} Kanälen geladen`);
    }
}

function toggleKanal(kanalId) {
    const container = document.getElementById(kanalId);
    const header = container.previousElementSibling;
    const toggle = header.querySelector('.kanal-toggle');
    
    if (container.classList.contains('collapsed')) {
        container.classList.remove('collapsed');
        toggle.textContent = '▼';
    } else {
        container.classList.add('collapsed');
        toggle.textContent = '▶';
    }
}

async function loadVideo(path, name) {
    const result = await apiCall('/video/load', 'POST', { path: path });
    if (result && result.status === 'success') {
        showToast(`Video geladen: ${name}`);
        updateStatus();
    }
}

// ========================================
// INFO
// ========================================

async function loadInfo() {
    const result = await apiCall('/info', 'GET');
    if (result) {
        const infoDisplay = document.getElementById('infoDisplay');
        infoDisplay.innerHTML = '';
        for (const [key, value] of Object.entries(result)) {
            const div = document.createElement('div');
            div.innerHTML = `<strong>${key}:</strong> ${value}`;
            infoDisplay.appendChild(div);
        }
    }
}

// ========================================
// STATUS
// ========================================

function updateStatusFromWebSocket(data) {
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    
    if (data.is_playing) {
        statusDot.className = 'status-dot playing';
        statusText.textContent = 'Läuft';
    } else if (data.is_paused) {
        statusDot.className = 'status-dot paused';
        statusText.textContent = 'Pausiert';
    } else {
        statusDot.className = 'status-dot';
        statusText.textContent = 'Gestoppt';
    }
    
    // Video-Name anzeigen (direkt aus data.video)
    if (data.video) {
        document.getElementById('currentVideo').textContent = data.video;
    } else if (data.status && data.status.video_path) {
        const videoName = data.status.video_path.split('\\').pop();
        document.getElementById('currentVideo').textContent = videoName;
    }
    
    // Frame-Info anzeigen
    if (data.current_frame !== undefined) {
        document.getElementById('currentFrame').textContent = data.current_frame;
        document.getElementById('totalFrames').textContent = data.total_frames || 0;
    } else if (data.status && data.status.current_frame !== undefined) {
        document.getElementById('currentFrame').textContent = data.status.current_frame;
        document.getElementById('totalFrames').textContent = data.status.total_frames || 0;
    }
}

async function updateStatus() {
    const result = await apiCall('/status', 'GET');
    if (result) {
        updateStatusFromWebSocket(result);
    }
}

// ========================================
// RECORDING
// ========================================

async function startRecording() {
    const result = await apiCall('/record/start', 'POST');
    if (result) showToast(result.message);
}

async function stopRecording() {
    const result = await apiCall('/record/stop', 'POST');
    if (result) showToast(result.message);
}

// ========================================
// THEME TOGGLE
// ========================================

function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    const themeLabel = document.getElementById('themeLabel');
    
    // Load saved theme preference or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeToggle.checked = true;
        themeLabel.textContent = 'Dunkel';
    } else {
        themeLabel.textContent = 'Hell';
    }
    
    themeToggle.addEventListener('change', () => {
        if (themeToggle.checked) {
            document.documentElement.setAttribute('data-theme', 'dark');
            themeLabel.textContent = 'Dunkel';
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
            themeLabel.textContent = 'Hell';
            localStorage.setItem('theme', 'light');
        }
    });
}

// ========================================
// CONSOLE FUNCTIONS
// ========================================

function updateConsoleFromWebSocket(data) {
    const consoleOutput = document.getElementById('consoleOutput');
    
    if (data.append) {
        // Append neue Zeilen
        const newLog = data.log.join('\n');
        if (consoleOutput.textContent) {
            consoleOutput.textContent += '\n' + newLog;
        } else {
            consoleOutput.textContent = newLog;
        }
    } else {
        // Komplettes Update
        const log = data.log.join('\n');
        consoleOutput.textContent = log;
    }
    
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    lastConsoleLines = data.total;
}

async function fetchConsole() {
    if (socketConnected) {
        // Request via WebSocket
        socket.emit('request_console', { lines: 100 });
        return;
    }
    
    // Fallback: REST API
    try {
        const response = await fetch(`${API_BASE}/console/log?lines=100`);
        if (!response.ok) return;
        const result = await response.json();
        if (result) {
            updateConsoleFromWebSocket({ log: result.log, total: result.total, append: false });
        }
    } catch (error) {
        // Stiller Fehler bei Console-Polling
    }
}

async function executeCommand() {
    const input = document.getElementById('consoleCommand');
    const command = input.value.trim();
    if (!command) return;
    
    try {
        const response = await fetch(`${API_BASE}/console/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        if (response.ok) {
            const result = await response.json();
            input.value = '';
            setTimeout(fetchConsole, 300);
            updateStatus();
        }
    } catch (error) {
        showToast('Console-Befehl fehlgeschlagen', 'error');
    }
}

async function clearConsole() {
    try {
        await fetch(`${API_BASE}/console/clear`, { method: 'POST' });
        document.getElementById('consoleOutput').textContent = '';
    } catch (error) {
        // Stiller Fehler
    }
}

// ========================================
// INITIALIZATION
// ========================================

// Lade Frontend-Config und initialisiere
async function loadConfig() {
    try {
        const response = await fetch('/api/config/frontend');
        if (response.ok) {
            const config = await response.json();
            API_BASE = config.api_base || API_BASE;
            WEBSOCKET_URL = config.websocket_url || WEBSOCKET_URL;
            POLLING_INTERVAL = config.polling_interval || POLLING_INTERVAL;
        }
    } catch (error) {
        console.warn('Konnte Frontend-Config nicht laden, verwende Defaults:', error);
    }
}

// Initial load when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    await loadConfig();  // Lade Config zuerst
    
    initWebSocket();
    initThemeToggle();
    updateStatus();
    fetchConsole();
    
    // Fallback Polling (falls WebSocket nicht verbindet)
    setInterval(() => {
        if (!socketConnected) {
            updateStatus();
            fetchConsole();
        }
    }, POLLING_INTERVAL);
});
