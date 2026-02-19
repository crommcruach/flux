/**
 * logger.js - Centralized Debug Logging System
 * Provides configurable debug logging with multiple log levels
 */

let DEBUG_LOGGING = false; // Default: disabled (use window.toggleDebug() to enable)
let VERBOSE_LOGGING = false; // Default: disabled (very noisy logs)

// Debug logger wrapper functions
export const debug = {
    log: (...args) => { if (DEBUG_LOGGING) console.log(...args); },
    verbose: (...args) => { if (VERBOSE_LOGGING) console.log(...args); }, // Extra verbose logs
    info: (...args) => { if (DEBUG_LOGGING) console.info(...args); },
    warn: (...args) => { if (DEBUG_LOGGING) console.warn(...args); },
    error: (...args) => console.error(...args), // Errors always shown
    group: (...args) => { if (DEBUG_LOGGING) console.group(...args); },
    groupEnd: () => { if (DEBUG_LOGGING) console.groupEnd(); },
    table: (...args) => { if (DEBUG_LOGGING) console.table(...args); }
};

/**
 * Load debug configuration from backend (DEPRECATED - now use browser console)
 * @param {string} apiBase - API base URL (default: '')
 * @deprecated This feature has been removed. Use window.toggleDebug() from browser console instead.
 */
export async function loadDebugConfig(apiBase = '') {
    // No-op: Debug logging is now controlled via browser console only
    // Use window.toggleDebug() or window.toggleVerbose() to enable logging
}

/**
 * Runtime toggle for debug logging (accessible from browser console)
 * @param {boolean} enable - Enable/disable debug logging (toggles if undefined)
 * @returns {boolean} Current debug logging state
 */
export function toggleDebug(enable) {
    DEBUG_LOGGING = enable ?? !DEBUG_LOGGING;
    console.log(`🐛 Debug logging ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return DEBUG_LOGGING;
}

/**
 * Runtime toggle for verbose logging (accessible from browser console)
 * @param {boolean} enable - Enable/disable verbose logging (toggles if undefined)
 * @returns {boolean} Current verbose logging state
 */
export function toggleVerbose(enable) {
    VERBOSE_LOGGING = enable ?? !VERBOSE_LOGGING;
    console.log(`🔬 Verbose logging ${VERBOSE_LOGGING ? 'ENABLED' : 'DISABLED'}`);
    return VERBOSE_LOGGING;
}

// Expose to window for browser console access
if (typeof window !== 'undefined') {
    window.toggleDebug = toggleDebug;
    window.toggleVerbose = toggleVerbose;
}
