/**
 * logger.js - Centralized Debug Logging System
 * Provides configurable debug logging with multiple log levels
 */

let DEBUG_LOGGING = true; // Default: enabled
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
 * Load debug configuration from backend
 * @param {string} apiBase - API base URL (default: '')
 */
export async function loadDebugConfig(apiBase = '') {
    try {
        const response = await fetch(`${apiBase}/api/config`);
        const config = await response.json();
        DEBUG_LOGGING = config.frontend?.debug_logging ?? true;
        VERBOSE_LOGGING = config.frontend?.verbose_logging ?? false;
        console.log(`🐛 Debug logging: ${DEBUG_LOGGING ? 'ENABLED' : 'DISABLED'}`);
        if (VERBOSE_LOGGING) console.log(`🔬 Verbose logging: ENABLED`);
    } catch (error) {
        console.error('❌ Failed to load debug config, using default (enabled):', error);
        DEBUG_LOGGING = true;
        VERBOSE_LOGGING = false;
    }
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
