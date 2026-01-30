/**
 * Client-Side Logger - Pipes all console logs to the server
 * 
 * This script intercepts console.log, console.warn, console.error, console.info, 
 * and console.debug calls and sends them to the server for centralized logging.
 * 
 * Features:
 * - Automatic error capturing (window.onerror, unhandledrejection)
 * - Batched log sending to reduce network overhead
 * - Fallback to original console if server is unavailable
 * - Configurable log levels to send
 * - Rate limiting to prevent log spam
 */

(function() {
    'use strict';
    
    // Configuration
    const CONFIG = {
        enabled: true,
        endpoint: '/api/logs/js-log',
        errorEndpoint: '/api/logs/js-error',
        batchSize: 10,              // Send logs in batches
        batchTimeout: 2000,         // Send batch after 2 seconds
        maxQueueSize: 100,          // Max logs to keep in queue
        rateLimit: 100,             // Max logs per minute
        rateLimitWindow: 60000,     // 1 minute
        sendLevels: {
            log: true,
            info: true,
            warn: true,
            error: true,
            debug: false            // Set to true if you want debug logs
        },
        // Don't log these patterns to reduce noise
        ignorePatterns: [
            /socket\.io/i,          // Socket.io connection messages
            /favicon\.ico/i         // Favicon 404s
        ]
    };
    
    // State
    let logQueue = [];
    let batchTimer = null;
    let logCounter = 0;
    let rateLimitResetTimer = null;
    
    // Store original console methods
    const originalConsole = {
        log: console.log.bind(console),
        warn: console.warn.bind(console),
        error: console.error.bind(console),
        info: console.info.bind(console),
        debug: console.debug.bind(console)
    };
    
    /**
     * Check if message should be ignored
     */
    function shouldIgnore(message) {
        if (!message) return false;
        const str = String(message);
        return CONFIG.ignorePatterns.some(pattern => pattern.test(str));
    }
    
    /**
     * Check rate limit
     */
    function checkRateLimit() {
        if (logCounter >= CONFIG.rateLimit) {
            return false;
        }
        logCounter++;
        
        // Reset counter after window
        if (!rateLimitResetTimer) {
            rateLimitResetTimer = setTimeout(() => {
                logCounter = 0;
                rateLimitResetTimer = null;
            }, CONFIG.rateLimitWindow);
        }
        
        return true;
    }
    
    /**
     * Serialize arguments for sending to server
     */
    function serializeArgs(args) {
        return Array.from(args).map(arg => {
            if (arg === null) return 'null';
            if (arg === undefined) return 'undefined';
            if (typeof arg === 'object') {
                try {
                    // Handle DOM elements
                    if (arg instanceof Element) {
                        return `<${arg.tagName.toLowerCase()}${arg.id ? '#' + arg.id : ''}${arg.className ? '.' + arg.className.split(' ').join('.') : ''}>`;
                    }
                    // Handle errors
                    if (arg instanceof Error) {
                        return `${arg.name}: ${arg.message}`;
                    }
                    // Regular objects
                    return JSON.stringify(arg, null, 2);
                } catch (e) {
                    return String(arg);
                }
            }
            return String(arg);
        });
    }
    
    /**
     * Get stack trace
     */
    function getStackTrace() {
        try {
            throw new Error();
        } catch (e) {
            // Remove first 3 lines (getStackTrace, interceptConsole, actual call)
            return e.stack.split('\n').slice(3).join('\n');
        }
    }
    
    /**
     * Send log batch to server
     */
    function sendBatch() {
        if (logQueue.length === 0) return;
        
        const batch = logQueue.splice(0, CONFIG.batchSize);
        
        // Send each log individually (could be optimized to batch endpoint)
        batch.forEach(log => {
            fetch(CONFIG.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(log)
            }).catch(err => {
                // Silently fail - don't want to create infinite loop
                // Fall back to original console
                originalConsole.error('Failed to send log to server:', err);
            });
        });
        
        // Schedule next batch if there are more logs
        if (logQueue.length > 0) {
            batchTimer = setTimeout(sendBatch, 100);
        } else {
            batchTimer = null;
        }
    }
    
    /**
     * Queue log for sending
     */
    function queueLog(level, args) {
        if (!CONFIG.enabled || !CONFIG.sendLevels[level]) {
            return;
        }
        
        // Check rate limit
        if (!checkRateLimit()) {
            if (logCounter === CONFIG.rateLimit + 1) {
                originalConsole.warn('[ClientLogger] Rate limit reached, throttling logs to server');
            }
            return;
        }
        
        // Serialize arguments
        const serializedArgs = serializeArgs(args);
        const message = serializedArgs[0] || '';
        
        // Check if should ignore
        if (shouldIgnore(message)) {
            return;
        }
        
        // Create log entry
        const logEntry = {
            level: level,
            message: message,
            args: serializedArgs.slice(1),
            url: window.location.href,
            timestamp: Date.now(),
            stack: level === 'error' ? getStackTrace() : undefined
        };
        
        // Add to queue
        logQueue.push(logEntry);
        
        // Trim queue if too large
        if (logQueue.length > CONFIG.maxQueueSize) {
            logQueue.shift();
        }
        
        // Schedule batch send
        if (!batchTimer) {
            batchTimer = setTimeout(sendBatch, CONFIG.batchTimeout);
        }
        
        // For errors, send immediately
        if (level === 'error') {
            clearTimeout(batchTimer);
            sendBatch();
        }
    }
    
    /**
     * Intercept console method
     */
    function interceptConsole(level) {
        console[level] = function(...args) {
            // Call original console first
            originalConsole[level].apply(console, args);
            
            // Queue for server
            queueLog(level, args);
        };
    }
    
    /**
     * Send error to server
     */
    function sendError(errorData) {
        fetch(CONFIG.errorEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(errorData)
        }).catch(err => {
            originalConsole.error('Failed to send error to server:', err);
        });
    }
    
    /**
     * Initialize client logger
     */
    function init() {
        // Intercept console methods
        ['log', 'info', 'warn', 'error', 'debug'].forEach(interceptConsole);
        
        // Capture global errors
        window.addEventListener('error', (event) => {
            const errorData = {
                message: event.message,
                source: event.filename,
                line: event.lineno,
                column: event.colno,
                stack: event.error ? event.error.stack : '',
                url: window.location.href,
                userAgent: navigator.userAgent
            };
            
            sendError(errorData);
        });
        
        // Capture unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            const errorData = {
                message: `Unhandled Promise Rejection: ${event.reason}`,
                source: 'Promise',
                line: 0,
                column: 0,
                stack: event.reason && event.reason.stack ? event.reason.stack : '',
                url: window.location.href,
                userAgent: navigator.userAgent
            };
            
            sendError(errorData);
        });
        
        // Flush logs before page unload
        window.addEventListener('beforeunload', () => {
            if (logQueue.length > 0) {
                // Use sendBeacon for reliable sending during page unload
                const batch = logQueue.splice(0, CONFIG.maxQueueSize);
                batch.forEach(log => {
                    const blob = new Blob([JSON.stringify(log)], { type: 'application/json' });
                    navigator.sendBeacon(CONFIG.endpoint, blob);
                });
            }
        });
        
        originalConsole.info('🚀 Client Logger initialized - Logs will be sent to server');
    }
    
    // Initialize immediately
    init();
    
    // Expose API for configuration
    window.ClientLogger = {
        enable: () => { CONFIG.enabled = true; },
        disable: () => { CONFIG.enabled = false; },
        setLevel: (level, enabled) => { CONFIG.sendLevels[level] = enabled; },
        flush: sendBatch,
        config: CONFIG
    };
    
})();
