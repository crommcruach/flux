/**
 * Centralized Session State Loader
 * Loads session state once on page load and distributes to all components
 */

class SessionStateLoader {
    constructor() {
        this.state = null;
        this.loaded = false;
        this.loading = false;
        this.listeners = [];
    }

    /**
     * Load session state from server (called once on page load)
     */
    async load() {
        if (this.loaded || this.loading) {
            console.log('⏭️ Session state already loaded/loading');
            return this.state;
        }

        return this._fetchState();
    }

    /**
     * Force reload session state from server (used after modifications)
     */
    async reload() {
        console.log('🔄 Reloading session state...');
        this.loaded = false;
        return this._fetchState();
    }

    /**
     * Internal method to fetch state from server
     */
    async _fetchState() {
        this.loading = true;
        const startTime = performance.now();
        
        try {
            console.log('🔄 Loading session state...');
            const response = await fetch('/api/session/state');
            
            if (response.ok) {
                const data = await response.json();
                this.state = data.state || {};
                this.loaded = true;
                
                const loadTime = (performance.now() - startTime).toFixed(2);
                console.log(`✅ Session state loaded in ${loadTime}ms`);
                
                // Notify all listeners
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
     * Register a callback to be notified when state is loaded
     */
    onStateLoaded(callback) {
        if (this.loaded) {
            // Already loaded, call immediately
            callback(this.state);
        } else {
            // Register for later
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
        this.listeners = []; // Clear listeners after notification
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

    /**
     * Force reload state
     */
    async reload() {
        this.loaded = false;
        this.loading = false;
        return await this.load();
    }
}

// Create global instance
window.sessionStateLoader = new SessionStateLoader();

// Auto-load on page ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.sessionStateLoader.load();
    });
} else {
    // DOMContentLoaded already fired
    window.sessionStateLoader.load();
}
