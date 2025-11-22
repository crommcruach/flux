// ========================================
// CONSTANTS & CONFIGURATION
// ========================================
let API_BASE = 'http://localhost:5000/api';  // Default, wird aus Config geladen
let WEBSOCKET_URL = 'http://localhost:5000';  // Default, wird aus Config geladen
let POLLING_INTERVAL = 3000;  // Default, wird aus Config geladen
let socket = null;
let socketConnected = false;

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

// Helligkeit Slider bewegt
function updateBrightnessSlider(value) {
    document.getElementById('brightnessValue').textContent = value + '%';
    document.getElementById('brightnessInput').value = value;
}

// Helligkeit Input geändert (sendet an API)
async function updateBrightnessInput(value) {
    const val = parseInt(value);
    if (isNaN(val) || val < 0 || val > 100) return;
    
    document.getElementById('brightnessValue').textContent = val + '%';
    document.getElementById('brightnessSlider').value = val;
    
    const result = await apiCall('/brightness', 'POST', { value: val });
    if (result) {
        showToast(`Helligkeit auf ${val}% gesetzt`, 'success');
    }
}

// Geschwindigkeit Slider bewegt
function updateSpeedSlider(value) {
    const speed = parseFloat(value);
    document.getElementById('speedValue').textContent = speed.toFixed(1) + 'x';
    document.getElementById('speedInput').value = speed.toFixed(1);
}

// Geschwindigkeit Input geändert (sendet an API)
async function updateSpeedInput(value) {
    const val = parseFloat(value);
    if (isNaN(val) || val <= 0 || val > 10) return;
    
    document.getElementById('speedValue').textContent = val.toFixed(1) + 'x';
    document.getElementById('speedSlider').value = val;
    
    const result = await apiCall('/speed', 'POST', { value: val });
    if (result) {
        showToast(`Geschwindigkeit auf ${val.toFixed(1)}x gesetzt`, 'success');
    }
}

// Hue Slider bewegt
function updateHueSlider(value) {
    const hue = parseInt(value);
    document.getElementById('hueValue').textContent = hue + '°';
    document.getElementById('hueInput').value = hue;
}

// Hue Input geändert (sendet an API)
async function updateHueInput(value) {
    const val = parseInt(value);
    if (isNaN(val) || val < 0 || val > 360) return;
    
    document.getElementById('hueValue').textContent = val + '°';
    document.getElementById('hueSlider').value = val;
    
    const result = await apiCall('/hue', 'POST', { value: val });
    if (result) {
        showToast(`Hue Rotation auf ${val}° gesetzt`, 'success');
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
                <div>
                    <strong>${script.filename}</strong>
                    ${script.description ? `<br><small style="color: #999;">${script.description}</small>` : ''}
                </div>
            `;
            div.onclick = (e) => {
                e.stopPropagation();
                loadScript(script.filename);
            };
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
// STATUS
// ========================================

function updateStatusFromWebSocket(data) {
    // Preview Update
    updatePreview(data);
    
    // Active Mode Update
    if (data.active_mode !== undefined && window.updateActiveModeDisplay) {
        window.updateActiveModeDisplay(data.active_mode);
    }
    
    // Slider-Werte synchronisieren
    if (data.brightness !== undefined) {
        const brightness = Math.round(data.brightness);
        const brightnessSlider = document.getElementById('brightnessSlider');
        const brightnessInput = document.getElementById('brightnessInput');
        const brightnessValue = document.getElementById('brightnessValue');
        
        if (brightnessSlider) brightnessSlider.value = brightness;
        if (brightnessInput) brightnessInput.value = brightness;
        if (brightnessValue) brightnessValue.textContent = brightness + '%';
    }
    
    if (data.speed !== undefined) {
        const speed = parseFloat(data.speed);
        const speedSlider = document.getElementById('speedSlider');
        const speedInput = document.getElementById('speedInput');
        const speedValue = document.getElementById('speedValue');
        
        if (speedSlider) speedSlider.value = speed;
        if (speedInput) speedInput.value = speed.toFixed(1);
        if (speedValue) speedValue.textContent = speed.toFixed(1) + 'x';
    }
    
    if (data.hue_shift !== undefined) {
        const hue = parseInt(data.hue_shift);
        const hueSlider = document.getElementById('hueSlider');
        const hueInput = document.getElementById('hueInput');
        const hueValue = document.getElementById('hueValue');
        
        if (hueSlider) hueSlider.value = hue;
        if (hueInput) hueInput.value = hue;
        if (hueValue) hueValue.textContent = hue + '°';
    }
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
    // Video-Name aktualisieren
    const videoName = data.video || (data.status && data.status.video_path ? data.status.video_path.split('\\').pop() : '-');
    document.getElementById('previewVideoName').textContent = videoName;
    
    // Canvas-Größe wird separat über info-Call geholt
    
    const isScript = data.is_script || false;
    
    if (isScript) {
        // Bei Scripts: Keine Frame-Zählung (endlos)
        document.getElementById('previewFrame').textContent = 'Endlos';
        document.getElementById('previewProgress').style.width = '100%';
    } else {
        // Bei Videos: Frame-Info anzeigen
        const currentFrame = data.current_frame || 0;
        const totalFrames = data.total_frames || 0;
        document.getElementById('previewFrame').textContent = `${currentFrame}/${totalFrames}`;
        
        // Progress Bar
        const progress = totalFrames > 0 ? (currentFrame / totalFrames * 100) : 0;
        document.getElementById('previewProgress').style.width = `${progress}%`;
    }
    
    // Stream läuft automatisch via <img> Element
}

async function updatePreviewInfo() {
    // Info-Daten separat holen für Canvas-Größe
    const info = await apiCall('/info', 'GET');
    if (info) {
        // Canvas-Größe aus width/height zusammensetzen
        const canvasSize = (info.canvas_width && info.canvas_height) 
            ? `${info.canvas_width}x${info.canvas_height}` 
            : '-';
        document.getElementById('previewCanvasSize').textContent = canvasSize;
        
        // Setze img width/height Attribute für korrekte Skalierung
        if (info.canvas_width && info.canvas_height) {
            const previewStream = document.getElementById('previewStream');
            if (previewStream && (previewStream.naturalWidth === 0 || previewStream.naturalWidth !== info.canvas_width)) {
                // Optional: Setze explizite Größe (Browser skaliert automatisch)
                console.log(`Preview Canvas-Größe: ${info.canvas_width}x${info.canvas_height}`);
            }
        }
    }
    
    // Traffic-Statistiken holen
    const traffic = await apiCall('/stream/traffic', 'GET');
    if (traffic && traffic.preview && traffic.fullscreen && traffic.total) {
        document.getElementById('trafficPreview').textContent = traffic.preview.formatted;
        document.getElementById('trafficPreviewMbps').textContent = traffic.preview.mbps;
        document.getElementById('trafficFullscreen').textContent = traffic.fullscreen.formatted;
        document.getElementById('trafficFullscreenMbps').textContent = traffic.fullscreen.mbps;
        document.getElementById('trafficTotal').textContent = traffic.total.formatted;
        document.getElementById('trafficTotalMbps').textContent = traffic.total.mbps;
    }
}

async function updateStatus() {
    const result = await apiCall('/status', 'GET');
    if (result) {
        updateStatusFromWebSocket(result);
    }
}

// ========================================
// PREVIEW WINDOW
// ========================================

function openPreviewWindow() {
    // Öffne den Preview-Stream in einem neuen Fenster (nicht Tab)
    // Zeigt Stream in Original Canvas-Auflösung (pixelated)
    const fullscreenUrl = '/fullscreen.html';
    const width = 900;
    const height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;
    
    window.open(
        fullscreenUrl, 
        'FullscreenWindow',
        `width=${width},height=${height},left=${left},top=${top},resizable=yes,scrollbars=no,status=no,toolbar=no,menubar=no,location=no`
    );
}

// ========================================
// THEME TOGGLE
// ========================================

function initThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    const themeLabel = document.getElementById('themeLabel');
    
    // Exit if theme toggle not present on this page
    if (!themeToggle) return;
    
    // Load saved theme preference or default to light
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        themeToggle.checked = true;
        if (themeLabel) themeLabel.textContent = 'Dunkel';
    } else {
        if (themeLabel) themeLabel.textContent = 'Hell';
    }
    
    themeToggle.addEventListener('change', () => {
        if (themeToggle.checked) {
            document.documentElement.setAttribute('data-theme', 'dark');
            if (themeLabel) themeLabel.textContent = 'Dunkel';
            localStorage.setItem('theme', 'dark');
        } else {
            document.documentElement.removeAttribute('data-theme');
            if (themeLabel) themeLabel.textContent = 'Hell';
            localStorage.setItem('theme', 'light');
        }
    });
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
    
    // Fallback Polling (falls WebSocket nicht verbindet)
    setInterval(() => {
        if (!socketConnected) {
            updateStatus();
        }
    }, POLLING_INTERVAL);
    
    // Preview Info regelmäßig aktualisieren
    setInterval(updatePreviewInfo, 5000);
});
