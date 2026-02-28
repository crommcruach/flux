/**
 * Unified Session State Manager
 * Handles all session state operations (read & write)
 */

class SessionStateManager {
    constructor() {
        this.state = null;
        this.loaded = false;
        this.loading = false;
        this.listeners = [];
        this._saveTimeouts = {};
        this._loadPromise = null; // Track ongoing load promise
        this.debug = false; // Set to true to enable debug console logs
    }

    /**
     * Load session state from server (called once on page load)
     */
    async load() {
        // If already loaded, return cached state
        if (this.loaded) {
            if (this.debug) console.log('⏭️ Session state already loaded');
            return this.state;
        }

        // If currently loading, wait for existing load to complete
        if (this.loading && this._loadPromise) {
            if (this.debug) console.log('⏭️ Session state loading in progress, waiting...');
            return this._loadPromise;
        }

        // Start new load
        this._loadPromise = this._fetchState();
        return this._loadPromise;
    }

    /**
     * Force reload session state from server (used after modifications)
     */
    async reload() {
        if (this.debug) console.log('🔄 Reloading session state...');
        this.loaded = false;
        this._loadPromise = null; // Clear cached promise
        return this.load();
    }

    /**
     * Internal method to fetch state from server
     */
    async _fetchState() {
        this.loading = true;
        const startTime = performance.now();
        
        try {
            if (this.debug) console.log('🔄 Loading session state...');
            const response = await fetch('/api/session/state');
            
            if (response.ok) {
                const data = await response.json();
                this.state = data.state || {};
                this.loaded = true;
                
                const loadTime = (performance.now() - startTime).toFixed(2);
                if (this.debug) console.log(`✅ Session state loaded in ${loadTime}ms`);
                
                this.notifyListeners();
                
                return this.state;
            } else {
                console.error('❌ Failed to load session state:', response.status);
                this.state = this.getEmptyState();
                this.loaded = true;
                return this.state;
            }
        } catch (error) {
            console.error('❌ Error loading session state:', error);
            this.state = this.getEmptyState();
            this.loaded = true;
            return this.state;
        } finally {
            this.loading = false;
            this._loadPromise = null; // Clear promise after completion
        }
    }

    /**
     * Get empty state structure
     */
    getEmptyState() {
        return {
            players: {
                video: { playlist: [], current_index: -1, autoplay: true, loop: true },
                artnet: { playlist: [], current_index: -1, autoplay: true, loop: true }
            },
            sequencer: {
                mode_active: false,
                audio_file: null
            },
            audio_analyzer: {
                device: null,
                running: false,
                config: {}
            }
        };
    }

    /**
     * Save editor state to backend
     */
    async saveEditor(editorState, options = {}) {
        return this._saveSection('editor', editorState, '/api/session/editor', options);
    }

    /**
     * Save audio analyzer state to backend
     */
    async saveAudioAnalyzer(audioState, options = {}) {
        return this._saveSection('audio_analyzer', audioState, '/api/session/audio', options);
    }

    /**
     * Save slices configuration to backend
     */
    async saveSlices(slicesConfig, options = {}) {
        const { debounce = 1000, onStatusChange = null } = options;

        if (this._saveTimeouts['slices']) {
            clearTimeout(this._saveTimeouts['slices']);
        }

        return new Promise((resolve, reject) => {
            this._saveTimeouts['slices'] = setTimeout(async () => {
                try {
                    // Check timestamp lock before saving
                    const lockStatus = await this._checkTimestampLock();
                    
                    if (lockStatus.locked) {
                        const errorMsg = '🔒 Session was restored elsewhere. Please reload the page to continue editing.';
                        console.error(errorMsg);
                        
                        // Show toast notification
                        if (typeof window.showToast === 'function') {
                            window.showToast(errorMsg, 'warning', 8000);
                        }
                        
                        if (onStatusChange) onStatusChange('locked');
                        reject(new Error('Session locked due to restore in another tab/page'));
                        return;
                    }

                    if (onStatusChange) onStatusChange('saving');

                    const response = await fetch('/api/slices/import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(slicesConfig)
                    });

                    const result = await response.json();

                    if (result.success) {
                        if (onStatusChange) onStatusChange('saved', result.message || `Saved ${Object.keys(slicesConfig.slices || {}).length} slices`);
                        resolve(result);
                    } else {
                        if (onStatusChange) onStatusChange('error');
                        reject(new Error(result.error));
                    }
                } catch (error) {
                    if (onStatusChange) onStatusChange('error');
                    reject(error);
                }
            }, debounce);
        });
    }

    /**
     * Load slices configuration from backend
     */
    async loadSlices() {
        try {
            const response = await fetch('/api/slices/export');
            const data = await response.json();
            
            if (data.success) {
                return data;
            } else {
                throw new Error(data.error || 'Failed to load slices');
            }
        } catch (error) {
            console.error('Failed to load slices:', error);
            throw error;
        }
    }

    /**
     * Check if restore timestamp has changed (session restored elsewhere)
     */
    async _checkTimestampLock() {
        // If already locked, don't check again
        if (this._timestampLocked) {
            return { locked: true, reason: 'already_locked' };
        }

        // If we have no timestamp, no lock needed (no restore has happened)
        if (!this.restoreTimestamp) {
            return { locked: false };
        }

        try {
            // Fetch current session state to check timestamp
            const response = await fetch('/api/session/state');
            if (!response.ok) {
                console.warn('⚠️ Failed to check timestamp lock');
                return { locked: false }; // Allow save if check fails
            }

            const data = await response.json();
            const currentTimestamp = data.state?.restore_timestamp;

            // If timestamps don't match, session was restored elsewhere
            if (currentTimestamp && currentTimestamp !== this.restoreTimestamp) {
                console.warn('🔒 Session restored elsewhere! Blocking save.');
                this._timestampLocked = true;
                return { 
                    locked: true, 
                    reason: 'timestamp_mismatch',
                    oldTimestamp: this.restoreTimestamp,
                    newTimestamp: currentTimestamp
                };
            }

            return { locked: false };
        } catch (error) {
            console.error('❌ Error checking timestamp lock:', error);
            return { locked: false }; // Allow save if check fails
        }
    }

    /**
     * Generic save method for any section
     */
    async _saveSection(sectionName, data, endpoint, options = {}) {
        const { debounce = 1000, onStatusChange = null } = options;

        if (this._saveTimeouts[sectionName]) {
            clearTimeout(this._saveTimeouts[sectionName]);
        }

        return new Promise((resolve, reject) => {
            this._saveTimeouts[sectionName] = setTimeout(async () => {
                try {
                    // Check timestamp lock before saving
                    const lockStatus = await this._checkTimestampLock();
                    
                    if (lockStatus.locked) {
                        const errorMsg = '🔒 Session was restored elsewhere. Please reload the page to continue editing.';
                        console.error(errorMsg);
                        
                        // Show toast notification
                        if (typeof window.showToast === 'function') {
                            window.showToast(errorMsg, 'warning', 8000);
                        }
                        
                        if (onStatusChange) onStatusChange('locked');
                        reject(new Error('Session locked due to restore in another tab/page'));
                        return;
                    }

                    if (onStatusChange) onStatusChange('saving');

                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    const result = await response.json();

                    if (result.success) {
                        if (this.state) {
                            this.state[sectionName] = data;
                        }
                        if (onStatusChange) onStatusChange('saved');
                        resolve(result);
                    } else {
                        if (onStatusChange) onStatusChange('error');
                        reject(new Error(result.error));
                    }
                } catch (error) {
                    if (onStatusChange) onStatusChange('error');
                    reject(error);
                }
            }, debounce);
        });
    }

    /**
     * Register a callback to be notified when state is loaded
     */
    onStateLoaded(callback) {
        if (this.loaded) {
            callback(this.state);
        } else {
            this.listeners.push(callback);
        }
    }

    /**
     * Notify all listeners that state is loaded
     */
    notifyListeners() {
        this.listeners.forEach(callback => {
            try {
                callback(this.state);
            } catch (error) {
                console.error('Error in state loaded callback:', error);
            }
        });
        this.listeners = [];
    }

    /**
     * Get specific section of state
     */
    get(path) {
        if (!this.loaded) {
            console.warn('⚠️ Attempting to access state before it is loaded');
            return null;
        }

        const keys = path.split('.');
        let value = this.state;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return null;
            }
        }
        
        return value;
    }

    /**
     * Check if state is loaded
     */
    isLoaded() {
        return this.loaded;
    }
}

// Create global instance
window.sessionStateManager = new SessionStateManager();

// Auto-load on page ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.sessionStateManager.load();
    });
} else {
    window.sessionStateManager.load();
}
