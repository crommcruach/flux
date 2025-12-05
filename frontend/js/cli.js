/**
 * CLI.js - Optimized version using common utilities
 * Console command interface and log viewer
 */

import { debug, loadDebugConfig } from './logger.js';
import { 
    loadConfig, 
    initWebSocket, 
    showToast, 
    apiCall, 
    isSocketConnected,
    getSocket,
    throttle,
    initErrorLogging
} from './common.js';

// ========================================
// STATE
// ========================================
let lastConsoleLines = 0;
let logAutoScroll = true;
let lastLogLength = 0;

// ========================================
// CONSOLE FUNCTIONS - Optimized
// ========================================

function updateConsoleFromWebSocket(data) {
    const consoleOutput = document.getElementById('consoleOutput');
    
    // Handle clear event
    if (data.clear) {
        consoleOutput.textContent = '';
        lastConsoleLines = 0;
        return;
    }
    
    if (data.append) {
        const newLog = data.log.join('\n');
        consoleOutput.textContent += (consoleOutput.textContent ? '\n' : '') + newLog;
    } else {
        consoleOutput.textContent = data.log.join('\n');
    }
    
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    lastConsoleLines = data.total;
}

async function fetchConsole() {
    const socket = getSocket();
    
    if (isSocketConnected() && socket) {
        socket.emit('request_console', { lines: 100 });
        return;
    }
    
    // Fallback: REST API
    const result = await apiCall('/console/log?lines=100');
    if (result) {
        updateConsoleFromWebSocket({ 
            log: result.log, 
            total: result.total, 
            append: false 
        });
    }
}

async function executeCommand() {
    const input = document.getElementById('consoleCommand');
    const command = input.value.trim();
    if (!command) return;
    
    const consoleOutput = document.getElementById('consoleOutput');
    
    // Show command
    const cmdLine = document.createElement('div');
    cmdLine.className = 'console-line-command';
    cmdLine.textContent = `> ${command}`;
    consoleOutput.appendChild(cmdLine);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
    
    const result = await apiCall('/console/command', 'POST', { command });
    
    if (result) {
        // Show output
        if (result.output) {
            const outputDiv = document.createElement('div');
            outputDiv.style.whiteSpace = 'pre-wrap';
            outputDiv.textContent = result.output;
            consoleOutput.appendChild(outputDiv);
        }
        
        // Show status message
        const msgDiv = document.createElement('div');
        if (result.status === 'success') {
            if (!result.output && result.message) {
                msgDiv.className = 'console-line-success';
                msgDiv.textContent = result.message;
                consoleOutput.appendChild(msgDiv);
            }
        } else {
            msgDiv.className = 'console-line-error';
            msgDiv.textContent = `Fehler: ${result.message || 'Unbekannter Fehler'}`;
            consoleOutput.appendChild(msgDiv);
        }
        
        consoleOutput.scrollTop = consoleOutput.scrollHeight;
        input.value = '';
    }
}

function clearConsole() {
    document.getElementById('consoleOutput').textContent = '';
    showToast('Console geleert', 'success');
}

window.executeCommand = executeCommand;
window.clearConsole = clearConsole;

// ========================================
// LOG VIEWER - Optimized
// ========================================

async function fetchLog() {
    const result = await apiCall('/logs');
    if (result) updateLogDisplay(result);
}

function updateLogDisplay(data) {
    const logOutput = document.getElementById('logOutput');
    const logInfo = document.getElementById('logInfo');
    
    if (!logOutput) return;
    
    if (data.lines?.length > 0) {
        logOutput.textContent = data.lines.join('\n');
        
        if (logAutoScroll) {
            logOutput.scrollTop = logOutput.scrollHeight;
        }
        
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

function updateLogFromWebSocket(data) {
    updateLogDisplay(data);
}

function refreshLog() {
    fetchLog();
    showToast('Log aktualisiert', 'info');
}

function toggleLogAutoScroll() {
    logAutoScroll = !logAutoScroll;
    const btn = document.getElementById('autoScrollBtn');
    const icon = document.getElementById('autoScrollIcon');
    
    if (btn && icon) {
        icon.textContent = logAutoScroll ? '🔒' : '🔓';
        btn.classList.toggle('btn-primary', logAutoScroll);
        btn.classList.toggle('btn-secondary', !logAutoScroll);
        showToast(`Auto-Scroll ${logAutoScroll ? 'aktiviert' : 'deaktiviert'}`, logAutoScroll ? 'success' : 'info');
        
        if (logAutoScroll) {
            const logOutput = document.getElementById('logOutput');
            if (logOutput) logOutput.scrollTop = logOutput.scrollHeight;
        }
    }
}

window.refreshLog = refreshLog;
window.toggleLogAutoScroll = toggleLogAutoScroll;

// ========================================
// HELP FUNCTIONS - Optimized
// ========================================

async function fetchHelp() {
    const result = await apiCall('/console/help');
    if (result) {
        displayHelp(result);
    } else {
        const helpContent = document.getElementById('helpContent');
        if (helpContent) {
            helpContent.innerHTML = '<p style="color: var(--danger);">Fehler beim Laden der Hilfe. Verwende <code>help</code> Befehl in der Console.</p>';
        }
    }
}

function toggleHelp() {
    const helpContent = document.getElementById('helpContent');
    const toggleIcon = document.getElementById('helpToggleIcon');
    
    if (helpContent && toggleIcon) {
        helpContent.classList.toggle('collapsed');
        toggleIcon.classList.toggle('collapsed');
    }
}

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
    
    if (!data.sections?.length) {
        helpContent.innerHTML = '<p style="color: var(--text-secondary);">Keine Befehle verfügbar.</p>';
        return;
    }
    
    // Build HTML efficiently
    const sections = data.sections.map(section => `
        <div style="margin-bottom: 1rem;">
            <h4 style="margin-bottom: 0.5rem; font-size: 0.95rem; color: var(--text-color);">${section.title}</h4>
            <ul style="margin: 0; padding-left: 1.5rem;">
                ${section.commands.map(cmd => `
                    <li style="margin-bottom: 0.3rem;">
                        <code style="background: var(--input-bg); padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; font-size: 12px;">${cmd.command}</code>
                        - ${cmd.description}
                    </li>
                `).join('')}
            </ul>
        </div>
    `).join('');
    
    helpContent.innerHTML = `
        ${sections}
        <div style="margin-top: 1rem; padding: 0.75rem; background: rgba(79, 70, 229, 0.1); border-left: 3px solid var(--accent-color); border-radius: 4px; font-size: 0.9rem;">
            💡 <strong>Hinweis:</strong> REST API startet automatisch beim Programmstart. Alle Befehle sind auch via Web-Interface verfügbar!
        </div>
    `;
}

window.toggleHelp = toggleHelp;
window.fetchHelp = fetchHelp;

// ========================================
// INITIALIZATION - Optimized
// ========================================

// Throttle console/log fetches to avoid spam
const throttledFetchConsole = throttle(fetchConsole, 1000);
const throttledFetchLog = throttle(fetchLog, 1000);

document.addEventListener('DOMContentLoaded', async () => {
    await loadDebugConfig();
    initErrorLogging();
    await loadConfig();
    
    initWebSocket({
        onConsoleUpdate: updateConsoleFromWebSocket,
        onLogUpdate: updateLogFromWebSocket
    });
    
    fetchConsole();
    fetchLog();
    fetchHelp();
    
    // Fallback polling with throttling
    let POLLING_INTERVAL = 3000;
    setInterval(() => {
        if (!isSocketConnected()) {
            throttledFetchConsole();
            throttledFetchLog();
        }
    }, POLLING_INTERVAL);
    
    // Additional log refresh when connected
    setInterval(() => {
        if (isSocketConnected()) {
            throttledFetchLog();
        }
    }, 5000);
});
