/**
 * Common Utilities - Shared functions across all pages
 * Vermeidet Code-Duplikation zwischen controls.js, cli.js und editor.js
 */

import { debug, loadDebugConfig } from './logger.js';
export { debug, loadDebugConfig };

// ========================================
// CONFIGURATION
// ========================================
export let API_BASE = 'http://localhost:5000/api';
export let WEBSOCKET_URL = 'http://localhost:5000';
export let POLLING_INTERVAL = 3000;

/**
 * Load configuration from API
 */
export async function loadConfig() {
    try {
        const response = await fetch('/api/config/frontend');
        const config = await response.json();
        
        const host = config.host || 'localhost';
        const port = config.port || 5000;
        
        API_BASE = `http://${host}:${port}/api`;
        WEBSOCKET_URL = `http://${host}:${port}`;
        POLLING_INTERVAL = config.status_broadcast_interval || 3000;
        
        debug.log('Config loaded:', { API_BASE, WEBSOCKET_URL, POLLING_INTERVAL });
    } catch (error) {
        debug.warn('Could not load config, using defaults:', error);
    }
}

// ========================================
// WEBSOCKET
// ========================================
let socket = null;
let socketConnected = false;

export function getSocket() {
    return socket;
}

export function isSocketConnected() {
    return socketConnected;
}

/**
 * Initialize WebSocket connection
 * @param {Object} handlers - Event handlers { onConnect, onDisconnect, onStatus, onConsoleUpdate, onLogUpdate }
 */
export function initWebSocket(handlers = {}) {
    socket = io(WEBSOCKET_URL, {
        transports: ['websocket', 'polling']
    });
    
    socket.on('connect', () => {
        debug.log('WebSocket connected');
        socketConnected = true;
        if (handlers.onConnect) handlers.onConnect();
        showToast('WebSocket verbunden', 'success');
    });
    
    socket.on('disconnect', () => {
        debug.log('WebSocket disconnected');
        socketConnected = false;
        if (handlers.onDisconnect) handlers.onDisconnect();
        showToast('WebSocket getrennt', 'error');
    });
    
    socket.on('connect_error', (error) => {
        console.error('WebSocket error:', error);
        socketConnected = false;
    });
    
    // Optional event handlers
    if (handlers.onStatus) {
        socket.on('status', handlers.onStatus);
    }
    if (handlers.onConsoleUpdate) {
        socket.on('console_update', handlers.onConsoleUpdate);
    }
    if (handlers.onLogUpdate) {
        socket.on('log_update', handlers.onLogUpdate);
    }
}

// ========================================
// TOAST NOTIFICATIONS
// ========================================

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in ms (default: 3000)
 */
export function showToast(message, type = 'success', duration = 3000) {
    // Log all toast messages to console
    const emoji = {
        success: '✅',
        error: '❌',
        info: 'ℹ️',
        warning: '⚠️'
    };
    debug.log(`${emoji[type] || '📢'} [TOAST ${type.toUpperCase()}] ${message}`);
    
    // Try different toast container variants
    let container = document.getElementById('toastContainer');
    
    if (!container) {
        // Fallback to old toast element for controls/cli pages
        const toast = document.getElementById('toast');
        const toastMessage = document.getElementById('toastMessage');
        
        if (toast && toastMessage) {
            toast.className = `toast ${type}`;
            toastMessage.textContent = message;
            toast.style.display = 'block';
            
            setTimeout(() => {
                toast.style.display = 'none';
            }, duration);
            return;
        }
        
        debug.warn('Toast container not found');
        return;
    }
    
    // Create dynamic toast element
    const toastId = 'toast-' + Date.now();
    const icons = {
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    };
    
    const toastElement = document.createElement('div');
    toastElement.id = toastId;
    toastElement.className = `toast-message ${type}`;
    toastElement.innerHTML = `
        <span class="toast-icon">${icons[type] || icons.info}</span>
        <span class="toast-content">${message}</span>
        <button class="toast-close" onclick="this.parentElement.remove()">×</button>
    `;
    
    container.appendChild(toastElement);
    
    // Auto remove after duration
    setTimeout(() => {
        toastElement.classList.add('removing');
        setTimeout(() => toastElement.remove(), 300);
    }, duration);
}

// ========================================
// API CALLS
// ========================================

/**
 * Make API call with error handling
 * @param {string} endpoint - API endpoint (e.g., '/status')
 * @param {string} method - HTTP method (default: 'GET')
 * @param {Object} data - Request body data (optional)
 * @returns {Promise<Object|null>} Response data or null on error
 */
export async function apiCall(endpoint, method = 'GET', data = null) {
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
// UTILITY FUNCTIONS
// ========================================

/**
 * Debounce function - delays execution until after wait time
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in ms
 * @returns {Function} Debounced function
 */
export function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle function - limits execution rate
 * @param {Function} func - Function to throttle
 * @param {number} limit - Minimum time between executions in ms
 * @returns {Function} Throttled function
 */
export function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Format bytes to human readable string
 * @param {number} bytes - Number of bytes
 * @returns {string} Formatted string (e.g., "1.5 MB")
 */
export function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format number with thousands separator
 * @param {number} num - Number to format
 * @returns {string} Formatted string (e.g., "1,234,567")
 */
export function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// ========================================
// ERROR LOGGING
// ========================================

/**
 * Log JavaScript error to backend
 * @param {Error} error - Error object
 * @param {string} source - Source file/context
 */
async function logErrorToBackend(error, source = 'unknown') {
    try {
        const errorData = {
            message: error.message || String(error),
            source: source,
            stack: error.stack || '',
            url: window.location.href,
            userAgent: navigator.userAgent,
            timestamp: new Date().toISOString()
        };
        
        // Parse stack trace for line/column if available
        if (error.stack) {
            const stackMatch = error.stack.match(/:(\d+):(\d+)/);
            if (stackMatch) {
                errorData.line = parseInt(stackMatch[1]);
                errorData.column = parseInt(stackMatch[2]);
            }
        }
        
        // Use relative URL to avoid CORS issues
        const response = await fetch('/api/logs/js-error', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(errorData)
        });
        
        debug.log('Error logged to backend:', response.ok ? 'Success' : 'Failed');
    } catch (e) {
        console.error('Failed to log error to backend:', e);
    }
}

/**
 * Initialize global error handlers
 * Catches unhandled errors and promise rejections
 */
export function initErrorLogging() {
    // Global error handler
    window.addEventListener('error', (event) => {
        console.error('Uncaught error:', event.error);
        
        const source = event.filename ? event.filename.split('/').pop() : 'unknown';
        const error = event.error || {
            message: event.message,
            stack: `at ${source}:${event.lineno}:${event.colno}`
        };
        
        logErrorToBackend(error, source);
    });
    
    // Unhandled promise rejection handler
    window.addEventListener('unhandledrejection', (event) => {
        console.error('Unhandled promise rejection:', event.reason);
        
        const error = event.reason instanceof Error ? event.reason : {
            message: String(event.reason),
            stack: ''
        };
        
        logErrorToBackend(error, 'promise-rejection');
    });
    
    debug.log('Error logging initialized');
}
