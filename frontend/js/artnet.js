
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
// IMPORTS
// ========================================
import { 
    loadConfig, 
    initWebSocket, 
    showToast, 
    apiCall,
    initErrorLogging,
    API_BASE 
} from './common.js';

// ========================================
// CONFIGURATION & CONSTANTS
// ========================================

// ========================================
// ART-NET FUNCTIONS
// ========================================
async function blackout() {
    const result = await apiCall('/blackout', 'POST');
    if (result) {
        showToast('Blackout aktiviert', 'success');
    } else {
        showToast('Fehler beim Blackout', 'error');
    }
}

async function testPattern(color) {
    const result = await apiCall('/test', 'POST', { color: color });
    if (result) {
        showToast(`Testmuster ${color} aktiviert`, 'success');
    } else {
        showToast('Fehler beim Testmuster', 'error');
    }
}

async function resumeVideo() {
    const result = await apiCall('/resume', 'POST');
    if (result) {
        showToast('Video-Modus fortgesetzt', 'success');
    } else {
        showToast('Fehler beim Fortsetzen', 'error');
    }
}

// Art-Net Helligkeit Slider bewegt
function updateArtnetBrightnessSlider(value) {
    document.getElementById('artnetBrightnessValue').textContent = value + '%';
    document.getElementById('artnetBrightnessInput').value = value;
}

// Art-Net Helligkeit ändern (sendet an API)
async function updateArtnetBrightness(value) {
    const val = parseInt(value);
    if (isNaN(val) || val < 0 || val > 100) return;
    
    document.getElementById('artnetBrightnessValue').textContent = val + '%';
    document.getElementById('artnetBrightnessSlider').value = val;
    document.getElementById('artnetBrightnessInput').value = val;
    
    const result = await apiCall('/brightness', 'POST', { value: val });
    if (result) {
        showToast(`Helligkeit auf ${val}% gesetzt`, 'success');
    }
}

// ========================================
// INFO FUNCTIONS
// ========================================
let infoUpdateInterval = null;

async function loadInfo() {
    // Lade Player-Infos
    const playerInfo = await apiCall('/info', 'GET');
    // Lade Art-Net Metriken
    const artnetInfo = await apiCall('/artnet/info', 'GET');
    
    if (playerInfo || artnetInfo) {
        const infoDisplay = document.getElementById('infoDisplay');
        infoDisplay.innerHTML = '';
        
        // Zeige Player-Infos
        if (playerInfo) {
            for (const [key, value] of Object.entries(playerInfo)) {
                const div = document.createElement('div');
                div.innerHTML = `<strong>${key}:</strong> ${value}`;
                infoDisplay.appendChild(div);
            }
        }
        
        // Zeige Art-Net Metriken
        if (artnetInfo && artnetInfo.status === 'success') {
            // Separator
            const separator = document.createElement('div');
            separator.style.borderTop = '1px solid var(--border-color)';
            separator.style.margin = '10px 0';
            infoDisplay.appendChild(separator);
            
            // Art-Net Header
            const header = document.createElement('div');
            header.innerHTML = '<strong>Art-Net Metriken</strong>';
            header.style.marginTop = '10px';
            header.style.marginBottom = '5px';
            infoDisplay.appendChild(header);
            
            // Art-Net Daten
            const artnetData = {
                'Helligkeit': `${artnetInfo.artnet_brightness}%`,
                'FPS': artnetInfo.artnet_fps,
                'Universen': artnetInfo.total_universes,
                'Pakete gesendet': artnetInfo.packets_sent.toLocaleString(),
                'Pakete/Sek': artnetInfo.packets_per_sec,
                'Mbps': artnetInfo.mbps,
                'Netzwerkauslastung': `${artnetInfo.network_load}%`,
                'Modus': artnetInfo.active_mode
            };
            
            for (const [key, value] of Object.entries(artnetData)) {
                const div = document.createElement('div');
                div.innerHTML = `<strong>${key}:</strong> ${value}`;
                infoDisplay.appendChild(div);
            }
        }
    }
}

function startInfoUpdates() {
    // Stoppe vorherige Updates
    if (infoUpdateInterval) {
        clearInterval(infoUpdateInterval);
    }
    
    // Initiales Laden
    loadInfo();
    
    // Update alle 1 Sekunde
    infoUpdateInterval = setInterval(loadInfo, 1000);
}

function stopInfoUpdates() {
    if (infoUpdateInterval) {
        clearInterval(infoUpdateInterval);
        infoUpdateInterval = null;
    }
}

// ========================================
// RECORDING FUNCTIONS
// ========================================
async function startRecording() {
    const nameInput = document.getElementById('recordingName');
    const name = nameInput ? nameInput.value.trim() : '';
    
    const result = await apiCall('/record/start', 'POST', { name: name || null });
    if (result) {
        showToast(result.message, 'success');
        if (nameInput) nameInput.value = ''; // Leere Eingabefeld
    }
}

async function stopRecording() {
    const result = await apiCall('/record/stop', 'POST');
    if (result) {
        if (result.status === 'success') {
            showToast(result.message + ': ' + result.filename, 'success');
            loadRecordings(); // Aktualisiere Liste
        } else {
            showToast(result.message, 'error');
        }
    }
}

async function loadRecordings() {
    const result = await apiCall('/recordings', 'GET');
    if (result && result.recordings) {
        const select = document.getElementById('recordingSelect');
        select.innerHTML = '<option value="">-- Wähle Aufzeichnung --</option>';
        
        result.recordings.forEach(rec => {
            const option = document.createElement('option');
            option.value = rec.filename;
            
            // Formatiere Dateigröße
            const sizeMB = (rec.size / 1024 / 1024).toFixed(2);
            
            // Formatiere Datum
            const date = new Date(rec.modified * 1000);
            const dateStr = date.toLocaleDateString('de-DE') + ' ' + date.toLocaleTimeString('de-DE');
            
            // Zeige Name (oder Filename falls kein Name) mit Frame-Count und Dauer
            const displayName = rec.name || rec.filename;
            const duration = rec.duration ? ` (${rec.duration.toFixed(1)}s, ${rec.frame_count} Frames)` : '';
            option.textContent = `${displayName}${duration} - ${sizeMB} MB`;
            select.appendChild(option);
        });
        
        showToast(`${result.recordings.length} Aufzeichnungen geladen`, 'success');
    }
}

async function startReplay() {
    const select = document.getElementById('recordingSelect');
    const filename = select.value;
    
    if (!filename) {
        showToast('Bitte Aufzeichnung wählen', 'error');
        return;
    }
    
    // Lade Aufzeichnung
    const loadResult = await apiCall('/replay/load', 'POST', { filename: filename });
    if (!loadResult || loadResult.status !== 'success') {
        showToast('Fehler beim Laden der Aufzeichnung', 'error');
        return;
    }
    
    // Starte Replay
    const startResult = await apiCall('/replay/start', 'POST');
    if (startResult && startResult.status === 'success') {
        showToast('Replay gestartet: ' + filename, 'success');
    } else {
        showToast('Fehler beim Starten des Replays', 'error');
    }
}

async function stopReplay() {
    const result = await apiCall('/replay/stop', 'POST');
    if (result) {
        if (result.status === 'success') {
            showToast(result.message, 'success');
        } else {
            showToast(result.message, 'error');
        }
    }
}

// ========================================
// POINTS LIST MANAGEMENT
// ========================================
async function loadPointsList() {
    const result = await apiCall('/points/list', 'GET');
    if (result && result.files) {
        const select = document.getElementById('pointsSelect');
        select.innerHTML = '<option value="">-- Wähle Punkte-Liste --</option>';
        
        result.files.forEach(file => {
            const option = document.createElement('option');
            option.value = file.filename;
            
            // Formatiere Dateigröße
            const sizeKB = (file.size / 1024).toFixed(1);
            
            // Markiere aktuelle Datei
            const marker = file.is_current ? ' ✓ (aktiv)' : '';
            option.textContent = `${file.filename} (${sizeKB} KB)${marker}`;
            
            if (file.is_current) {
                option.selected = true;
                option.style.fontWeight = 'bold';
            }
            
            select.appendChild(option);
        });
        
        // Event Listener für Vorschau
        select.addEventListener('change', updatePointsPreview);
        
        // Zeige Vorschau der aktuellen Auswahl
        updatePointsPreview();
        
        showToast(`${result.total} Punkte-Listen gefunden`, 'success');
    }
}

function updatePointsPreview() {
    const select = document.getElementById('pointsSelect');
    const previewImg = document.getElementById('pointsPreview');
    const filename = select.value;
    
    if (filename && previewImg) {
        previewImg.src = `${API_BASE}/points/preview/${encodeURIComponent(filename)}`;
        previewImg.style.display = 'block';
    } else if (previewImg) {
        previewImg.style.display = 'none';
    }
}

async function switchPoints() {
    const select = document.getElementById('pointsSelect');
    const filename = select.value;
    
    if (!filename) {
        showToast('Bitte wähle eine Punkte-Liste', 'warning');
        return;
    }
    
    // Bestätigung vom User
    if (!confirm(`Punkte-Liste wechseln zu "${filename}"?\n\nDies wird:\n• Video/Script stoppen\n• Canvas-Größe anpassen\n• Art-Net Universen neu konfigurieren`)) {
        return;
    }
    
    const result = await apiCall('/points/switch', 'POST', { filename });
    if (result) {
        if (result.status === 'success') {
            showToast(result.message, 'success');
            // Aktualisiere Info-Anzeige
            if (typeof loadInfo === 'function') {
                loadInfo();
            }
            // Lade Liste neu um aktuelle Auswahl zu aktualisieren
            setTimeout(loadPointsList, 500);
        } else {
            showToast(result.message || 'Fehler beim Wechseln der Punkte-Liste', 'error');
        }
    }
}

// ========================================
// FPS CONTROL
// ========================================
async function setFPS() {
    const fps = document.getElementById('fpsInput').value;
    if (fps) {
        const result = await apiCall('/fps', 'POST', { value: parseInt(fps) });
        if (result) {
            showToast(`FPS auf ${fps} gesetzt`, 'success');
            document.getElementById('fpsInput').value = '';
        }
    } else {
        showToast('Bitte FPS-Wert eingeben', 'error');
    }
}

// ========================================
// DMX MONITOR
// ========================================
let currentUniverse = 0;
let dmxData = null;
let socket = null;

function initDMXMonitor() {
    // Erstelle 512 Kanal-Elemente
    const dmxGrid = document.getElementById('dmxGrid');
    for (let i = 1; i <= 512; i++) {
        const channel = document.createElement('div');
        channel.className = 'dmx-channel';
        channel.id = `dmx-ch-${i}`;
        channel.dataset.channel = `Ch ${i}`;
        channel.textContent = '0';
        channel.style.backgroundColor = '#000';
        channel.style.color = '#666';
        dmxGrid.appendChild(channel);
    }
    
    // Socket.IO für Live-Updates
    socket = io('http://localhost:5000');
    socket.on('connect', () => {
        debug.log('DMX Monitor: Socket verbunden');
    });
    
    socket.on('status', (data) => {
        if (data.dmx_preview) {
            dmxData = data.dmx_preview;
            updateDMXDisplay();
        }
        
        // Update Universe-Dropdown
        if (data.total_universes !== undefined) {
            updateUniverseSelect(data.total_universes);
        }
        
        // Update Active Mode Display
        if (data.active_mode !== undefined && window.updateActiveModeDisplay) {
            window.updateActiveModeDisplay(data.active_mode);
        }
    });
}

function updateUniverseSelect(totalUniverses) {
    const select = document.getElementById('universeSelect');
    const currentValue = select.value;
    
    // Erstelle Optionen für alle genutzten Universen
    select.innerHTML = '';
    for (let i = 0; i < totalUniverses; i++) {
        const option = document.createElement('option');
        option.value = i;
        option.textContent = i;
        select.appendChild(option);
    }
    
    // Setze vorherigen Wert wieder, wenn noch gültig
    if (parseInt(currentValue) < totalUniverses) {
        select.value = currentValue;
    } else {
        select.value = 0;
        currentUniverse = 0;
        document.getElementById('dmxUniverseNum').textContent = 0;
    }
}

function updateDMXDisplay() {
    if (!dmxData || !Array.isArray(dmxData)) {
        debug.log('DMX Monitor: Keine Daten vorhanden');
        return;
    }
    
    // Jedes Universe hat 512 DMX-Kanäle
    const channelsPerUniverse = 512;
    const startIdx = currentUniverse * channelsPerUniverse;
    const endIdx = startIdx + channelsPerUniverse;
    
    debug.log(`DMX Monitor: Universe ${currentUniverse}, Daten ${startIdx}-${endIdx}, Total: ${dmxData.length}`);
    
    for (let i = 0; i < channelsPerUniverse; i++) {
        const dmxIndex = startIdx + i;
        const value = (dmxIndex < dmxData.length) ? dmxData[dmxIndex] : 0;
        const channel = document.getElementById(`dmx-ch-${i + 1}`);
        if (!channel) continue;
        
        channel.textContent = value;
        
        // Farb-Coding basierend auf Wert (Schwarz -> Dunkelgrau -> Cyan -> Hellcyan -> Weiß)
        if (value === 0) {
            channel.style.backgroundColor = '#000';
            channel.style.color = '#666';
        } else if (value < 50) {
            const intensity = value / 50;
            channel.style.backgroundColor = `rgb(${Math.floor(30 * intensity)}, ${Math.floor(30 * intensity)}, ${Math.floor(30 * intensity)})`;
            channel.style.color = '#888';
        } else if (value < 128) {
            const intensity = (value - 50) / 78;
            channel.style.backgroundColor = `rgb(0, ${Math.floor(100 + 100 * intensity)}, ${Math.floor(100 + 100 * intensity)})`;
            channel.style.color = '#000';
        } else if (value < 200) {
            const intensity = (value - 128) / 72;
            channel.style.backgroundColor = `rgb(${Math.floor(100 * intensity)}, ${Math.floor(200 + 40 * intensity)}, ${Math.floor(200 + 40 * intensity)})`;
            channel.style.color = '#000';
        } else {
            const intensity = (value - 200) / 55;
            channel.style.backgroundColor = `rgb(${Math.floor(100 + 155 * intensity)}, ${Math.floor(240 + 15 * intensity)}, ${Math.floor(240 + 15 * intensity)})`;
            channel.style.color = '#000';
        }
    }
}

function switchUniverse(universe) {
    currentUniverse = parseInt(universe);
    document.getElementById('dmxUniverseNum').textContent = currentUniverse;
    updateDMXDisplay();
}

// ========================================
// INITIALIZATION
// ========================================
document.addEventListener('DOMContentLoaded', async () => {
    await loadDebugConfig();
    initErrorLogging();
    await loadConfig();
    initDMXMonitor();
    
    // Register global functions for inline onclick handlers
    // (ES6 modules don't export to global scope by default)
    window.blackout = blackout;
    window.resumeVideo = resumeVideo;
    window.testPattern = testPattern;
    window.setFPS = setFPS;
    window.startRecording = startRecording;
    window.stopRecording = stopRecording;
    window.loadRecordings = loadRecordings;
    window.startReplay = startReplay;
    window.stopReplay = stopReplay;
    window.loadPointsList = loadPointsList;
    window.switchPoints = switchPoints;
    window.startInfoUpdates = startInfoUpdates;
    window.stopInfoUpdates = stopInfoUpdates;
    window.updateArtnetBrightnessSlider = updateArtnetBrightnessSlider;
    window.updateArtnetBrightness = updateArtnetBrightness;
});

// ========================================
// Toast notification now imported from common.js
