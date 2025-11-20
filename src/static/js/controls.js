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
    
    if (!toast || !toastMessage) {
        console.warn('Toast-Elemente nicht gefunden');
        return;
    }
    
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

async function executeCliCommand(command) {
    const result = await apiCall('/console/command', 'POST', { command: command });
    if (result && result.status === 'success') {
        showToast(`Befehl '${command}' ausgeführt`);
        updateStatus();
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
    }
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
// MEDIA (VIDEOS & SCRIPTS)
// ========================================

async function loadVideos() {
    const result = await apiCall('/videos', 'GET');
    if (result && result.videos) {
        const mediaList = document.getElementById('mediaList');
        mediaList.innerHTML = '<h3 style="margin-top: 0;">🎬 Videos</h3>';
        
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
            mediaList.appendChild(header);
            
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
            
            mediaList.appendChild(container);
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
    // Verwende video:<relativePath> CLI-Befehl (mit Kanal-Ordner)
    // path enthält bereits den relativen Pfad (z.B. "kanal_1/test.mp4")
    const relativePath = path.replace(/\\/g, '/');  // Normalisiere Backslashes zu Forward Slashes
    const result = await apiCall('/console/command', 'POST', { command: `video:${relativePath}` });
    if (result && result.status === 'success') {
        showToast(`Video startet: ${name}`);
        updateStatus();
        // Starte Video automatisch nach dem Laden
        await executeCliCommand('start');
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
    }
}

async function loadScripts() {
    const result = await apiCall('/scripts', 'GET');
    if (result && result.scripts) {
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
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong>${script.filename}</strong>
                        ${script.description ? `<br><small style="color: #999;">${script.description}</small>` : ''}
                    </div>
                    <button class="btn btn-primary btn-sm" onclick="loadScript('${script.filename}')" title="script:${script.filename}">▶️</button>
                </div>
            `;
            mediaList.appendChild(div);
        });
    }
}

async function loadScript(scriptName) {
    // Entferne .py Endung falls vorhanden
    const cleanName = scriptName.endsWith('.py') ? scriptName.slice(0, -3) : scriptName;
    const result = await apiCall('/console/command', 'POST', { command: `script:${cleanName}` });
    if (result && result.status === 'success') {
        showToast(`Script startet: ${cleanName}`);
        updateStatus();
        // Starte Script automatisch nach dem Laden
        await executeCliCommand('start');
    } else if (result) {
        showToast(`Fehler: ${result.message}`, 'error');
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
    
    // Preview Update
    updatePreview(data);
}

// ========================================
// PREVIEW
// ========================================

let previewStream = null;

function initPreview() {
    previewStream = document.getElementById('previewStream');
    if (!previewStream) {
        console.error('Preview Stream Element nicht gefunden!');
        return;
    }
    
    // Teste zuerst mit Test-Stream
    const useTestStream = false; // Setze auf true zum Testen
    const streamUrl = useTestStream ? 
        `${API_BASE}/preview/test` : 
        `${API_BASE}/preview/stream`;
    
    // Debug-Ausgaben BEFORE setting src
    previewStream.onerror = function(e) {
        console.error('Preview Stream Fehler:', e);
        console.error('Stream URL:', previewStream.src);
        console.error('Stream readyState:', previewStream.readyState);
        console.error('Stream complete:', previewStream.complete);
        
        // Versuche neu zu laden nach Fehler
        setTimeout(() => {
            console.log('Versuche Stream neu zu laden...');
            previewStream.src = streamUrl + '?t=' + Date.now();
        }, 1000);
    };
    
    previewStream.onloadstart = function() {
        console.log('Preview Stream lädt...');
    };
    
    previewStream.onload = function() {
        console.log('Preview Stream geladen:', previewStream.src);
        console.log('Bild-Größe:', previewStream.naturalWidth, 'x', previewStream.naturalHeight);
    };
    
    console.log('Preview initialisiert mit URL:', streamUrl);
    console.log('API_BASE:', API_BASE);
    console.log('Setting img.src now...');
    
    // Setze src NACH Event-Handlern
    previewStream.src = streamUrl;
    
    console.log('img.src gesetzt:', previewStream.src);
}

function updatePreview(data) {
    // Video-Name und Canvas-Größe aktualisieren
    const videoName = data.video || (data.status && data.status.video_path ? data.status.video_path.split('\\').pop() : '-');
    document.getElementById('previewVideoName').textContent = videoName;
    
    // Canvas-Größe aus Info-Daten holen (später über separaten API-Call)
    const canvasSize = '-'; // Wird beim nächsten info-Call aktualisiert
    document.getElementById('previewCanvasSize').textContent = canvasSize;
    
    // Frame-Info
    const currentFrame = data.current_frame || 0;
    const totalFrames = data.total_frames || 0;
    document.getElementById('previewFrame').textContent = `${currentFrame}/${totalFrames}`;
    
    // Progress Bar
    const progress = totalFrames > 0 ? (currentFrame / totalFrames * 100) : 0;
    document.getElementById('previewProgress').style.width = `${progress}%`;
    
    // Stream läuft automatisch via <img> Element
}

async function updatePreviewInfo() {
    // Info-Daten separat holen für Canvas-Größe
    const info = await apiCall('/info', 'GET');
    if (info && info.canvas) {
        document.getElementById('previewCanvasSize').textContent = info.canvas;
        
        // Setze img width/height Attribute für korrekte Skalierung
        const [w, h] = info.canvas.split('x').map(Number);
        if (previewStream && (previewStream.naturalWidth === 0 || previewStream.naturalWidth !== w)) {
            // Optional: Setze explizite Größe (Browser skaliert automatisch)
            console.log(`Preview Canvas-Größe: ${w}x${h}`);
        }
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
    
    const consoleOutput = document.getElementById('consoleOutput');
    
    // Zeige Befehl in Console
    const cmdLine = document.createElement('div');
    cmdLine.style.color = '#4CAF50';
    cmdLine.style.fontWeight = 'bold';
    cmdLine.textContent = `> ${command}`;
    consoleOutput.appendChild(cmdLine);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    
    try {
        const result = await apiCall('/console', 'POST', { command });
        
        if (result) {
            // Zeige Output
            if (result.output) {
                const outputDiv = document.createElement('div');
                outputDiv.style.whiteSpace = 'pre-wrap';
                outputDiv.textContent = result.output;
                consoleOutput.appendChild(outputDiv);
            }
            
            // Zeige Status-Meldung
            if (result.status === 'success') {
                if (!result.output && result.message) {
                    const msgDiv = document.createElement('div');
                    msgDiv.style.color = '#4CAF50';
                    msgDiv.textContent = result.message;
                    consoleOutput.appendChild(msgDiv);
                }
            } else {
                const errorDiv = document.createElement('div');
                errorDiv.style.color = '#f44336';
                errorDiv.textContent = `Fehler: ${result.message || 'Unbekannter Fehler'}`;
                consoleOutput.appendChild(errorDiv);
            }
            
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
            input.value = '';
            updateStatus();
        }
    } catch (error) {
        const errorDiv = document.createElement('div');
        errorDiv.style.color = '#f44336';
        errorDiv.textContent = `Fehler: ${error.message}`;
        consoleOutput.appendChild(errorDiv);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
}

async function clearConsole() {
    document.getElementById('consoleOutput').textContent = '';
}

// ========================================
// INITIALIZATION
// ========================================

// Lade Frontend-Config und initialisiere
async function loadConfig() {
    try {
        const response = await fetch('http://localhost:5000/api/config/frontend');
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
    initPreview();
    updateStatus();
    updatePreviewInfo();
    fetchConsole();
    
    // Fallback Polling (falls WebSocket nicht verbindet)
    setInterval(() => {
        if (!socketConnected) {
            updateStatus();
            fetchConsole();
        }
    }, POLLING_INTERVAL);
    
    // Preview Info regelmäßig aktualisieren
    setInterval(updatePreviewInfo, 5000);
});
