// ========================================
// CONSTANTS & CONFIGURATION
// ========================================
let API_BASE = 'http://localhost:5000/api';  // Default, wird aus Config geladen
let WEBSOCKET_URL = 'http://localhost:5000';  // Default, wird aus Config geladen
let POLLING_INTERVAL = 3000;  // Default, wird aus Config geladen
let socket = null;
let socketConnected = false;
let lastConsoleLines = 0;

// Log viewer state
let logAutoScroll = true;
let lastLogLength = 0;

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
    
    socket.on('console_update', (data) => {
        updateConsoleFromWebSocket(data);
    });
    
    socket.on('log_update', (data) => {
        updateLogFromWebSocket(data);
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
    cmdLine.className = 'console-line-command';
    cmdLine.textContent = `> ${command}`;
    consoleOutput.appendChild(cmdLine);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    
    try {
        const result = await apiCall('/console/command', 'POST', { command });
        
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
                    msgDiv.className = 'console-line-success';
                    msgDiv.textContent = result.message;
                    consoleOutput.appendChild(msgDiv);
                }
            } else {
                const errorDiv = document.createElement('div');
                errorDiv.className = 'console-line-error';
                errorDiv.textContent = `Fehler: ${result.message || 'Unbekannter Fehler'}`;
                consoleOutput.appendChild(errorDiv);
            }
            
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
            input.value = '';
        }
    } catch (error) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'console-line-error';
        errorDiv.textContent = `Fehler: ${error.message}`;
        consoleOutput.appendChild(errorDiv);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
}

function clearConsole() {
    document.getElementById('consoleOutput').textContent = '';
    showToast('Console geleert', 'success');
}

// ========================================
// LOG VIEWER FUNCTIONS
// ========================================

// Fetch log from API
async function fetchLog() {
    try {
        const response = await fetch(`${API_BASE}/logs`);
        if (response.ok) {
            const data = await response.json();
            updateLogDisplay(data);
        }
    } catch (error) {
        console.error('Fehler beim Laden der Logs:', error);
        const logInfo = document.getElementById('logInfo');
        if (logInfo) {
            logInfo.textContent = `Fehler beim Laden: ${error.message}`;
            logInfo.style.color = 'var(--danger)';
        }
    }
}

// Update log display
function updateLogDisplay(data) {
    const logOutput = document.getElementById('logOutput');
    const logInfo = document.getElementById('logInfo');
    
    if (!logOutput) return;
    
    if (data.lines && data.lines.length > 0) {
        const logText = data.lines.join('\n');
        logOutput.textContent = logText;
        
        // Auto-scroll to bottom if enabled
        if (logAutoScroll) {
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
        // Update info
        if (logInfo) {
            const timestamp = new Date().toLocaleTimeString('de-DE');
            logInfo.textContent = `${data.lines.length} Zeilen | Aktualisiert: ${timestamp}`;
            logInfo.style.color = 'var(--text-secondary)';
        }
        
        lastLogLength = data.lines.length;
    } else {
        logOutput.textContent = 'Keine Log-Einträge verfügbar';
        if (logInfo) {
            logInfo.textContent = 'Keine Daten';
            logInfo.style.color = 'var(--text-secondary)';
        }
    }
}

// Update log from WebSocket
function updateLogFromWebSocket(data) {
    updateLogDisplay(data);
}

// Refresh log manually
function refreshLog() {
    fetchLog();
    showToast('Log aktualisiert', 'info');
}

// Toggle auto-scroll
function toggleLogAutoScroll() {
    logAutoScroll = !logAutoScroll;
    const btn = document.getElementById('autoScrollBtn');
    const icon = document.getElementById('autoScrollIcon');
    
    if (btn && icon) {
        if (logAutoScroll) {
            icon.textContent = '🔒';
            btn.classList.add('btn-primary');
            btn.classList.remove('btn-secondary');
            showToast('Auto-Scroll aktiviert', 'success');
            // Scroll to bottom immediately
            const logOutput = document.getElementById('logOutput');
            if (logOutput) {
                logOutput.scrollTop = logOutput.scrollHeight;
            }
        } else {
            icon.textContent = '🔓';
            btn.classList.add('btn-secondary');
            btn.classList.remove('btn-primary');
            showToast('Auto-Scroll deaktiviert', 'info');
        }
    }
}

// ========================================
// HELP FUNCTIONS
// ========================================

// Fetch and display dynamic help from CLI
async function fetchHelp() {
    try {
        const response = await fetch(`${API_BASE}/console/help`);
        if (response.ok) {
            const data = await response.json();
            displayHelp(data);
        }
    } catch (error) {
        console.error('Fehler beim Laden der Hilfe:', error);
        const helpContent = document.getElementById('helpContent');
        if (helpContent) {
            helpContent.innerHTML = '<p style="color: var(--danger);">Fehler beim Laden der Hilfe. Verwende <code>help</code> Befehl in der Console.</p>';
        }
    }
}

// Toggle help section
function toggleHelp() {
    const helpContent = document.getElementById('helpContent');
    const toggleIcon = document.getElementById('helpToggleIcon');
    
    if (helpContent && toggleIcon) {
        helpContent.classList.toggle('collapsed');
        toggleIcon.classList.toggle('collapsed');
    }
}

// Display help in structured format
function displayHelp(data) {
    const helpSection = document.getElementById('helpSection');
    const helpContent = document.getElementById('helpContent');
    
    if (!helpContent) return;
    
    // Update title
    const title = helpSection.querySelector('h3');
    if (title) {
        title.innerHTML = '<span class="help-toggle-icon collapsed" id="helpToggleIcon">▼</span> 📖 Verfügbare Befehle <button class="btn btn-sm btn-secondary" onclick="event.stopPropagation(); fetchHelp()" style="margin-left: 10px;">🔄 Aktualisieren</button>';
        title.onclick = toggleHelp;
    }
    
    // Build HTML from sections
    let html = '';
    
    if (data.sections && data.sections.length > 0) {
        data.sections.forEach(section => {
            html += `<div style="margin-bottom: 1rem;">`;
            html += `<h4 style="margin-bottom: 0.5rem; font-size: 0.95rem; color: var(--text-color);">${section.title}</h4>`;
            html += `<ul style="margin: 0; padding-left: 1.5rem;">`;
            
            section.commands.forEach(cmd => {
                html += `<li style="margin-bottom: 0.3rem;">`;
                html += `<code style="background: var(--input-bg); padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 12px;">${cmd.command}</code>`;
                html += ` - ${cmd.description}`;
                html += `</li>`;
            });
            
            html += `</ul>`;
            html += `</div>`;
        });
        
        // Add note at the end
        html += `<div style="margin-top: 1rem; padding: 0.75rem; background: rgba(79, 70, 229, 0.1); border-left: 3px solid var(--accent-color); border-radius: 4px; font-size: 0.9rem;">`;
        html += `💡 <strong>Hinweis:</strong> REST API startet automatisch beim Programmstart. Alle Befehle sind auch via Web-Interface verfügbar!`;
        html += `</div>`;
    } else {
        html = '<p style="color: var(--text-secondary);">Keine Befehle verfügbar.</p>';
    }
    
    helpContent.innerHTML = html;
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
    fetchConsole();
    fetchLog();  // Initial log load
    fetchHelp();  // Load dynamic help
    
    // Fallback Polling (falls WebSocket nicht verbindet)
    setInterval(() => {
        if (!socketConnected) {
            fetchConsole();
            fetchLog();
        }
    }, POLLING_INTERVAL);
    
    // Additional log refresh every 5 seconds if connected
    setInterval(() => {
        if (socketConnected) {
            fetchLog();
        }
    }, 5000);
});
