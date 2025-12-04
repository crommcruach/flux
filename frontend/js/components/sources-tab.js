/**
 * Sources Tab Component
 * Reusable component for displaying available generator sources
 */



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

export class SourcesTab {
    constructor(containerId, searchContainerId) {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.sources = [];
        this.filteredSources = [];
        this.searchTerm = '';
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        await this.loadSources();
    }
    
    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchContainer = document.getElementById(this.searchContainerId);
        if (!searchContainer) return;
        
        searchContainer.innerHTML = `
            <div class="search-box">
                <input type="text" 
                       class="form-control form-control-sm" 
                       placeholder="🔍 Search sources..." 
                       id="${this.searchContainerId}-input">
            </div>
        `;
        
        const searchInput = document.getElementById(`${this.searchContainerId}-input`);
        searchInput.addEventListener('input', (e) => {
            this.searchTerm = e.target.value.toLowerCase();
            this.filterSources();
        });
    }
    
    /**
     * Load sources from API
     */
    async loadSources() {
        const container = document.getElementById(this.containerId);
        
        try {
            const response = await fetch('/api/plugins/list?type=generator');
            const data = await response.json();
            
            if (data.success) {
                this.sources = data.plugins || [];
                this.filteredSources = [...this.sources];
                this.render();
            } else {
                this.showError('Failed to load sources');
            }
        } catch (error) {
            console.error('Error loading sources:', error);
            this.showError('Error loading sources');
        }
    }
    
    /**
     * Filter sources based on search term
     */
    filterSources() {
        if (!this.searchTerm) {
            this.filteredSources = [...this.sources];
        } else {
            this.filteredSources = this.sources.filter(source => {
                const name = source.name?.toLowerCase() || '';
                const description = source.description?.toLowerCase() || '';
                const category = source.category?.toLowerCase() || '';
                
                return name.includes(this.searchTerm) || 
                       description.includes(this.searchTerm) ||
                       category.includes(this.searchTerm);
            });
        }
        
        this.render();
    }
    
    /**
     * Render sources list
     */
    render() {
        const container = document.getElementById(this.containerId);
        
        if (this.filteredSources.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>${this.searchTerm ? 'No sources found' : 'No sources available'}</p>
                </div>
            `;
            return;
        }
        
        // Group by category
        const categories = {};
        this.filteredSources.forEach(source => {
            const cat = source.category || 'Other';
            if (!categories[cat]) {
                categories[cat] = [];
            }
            categories[cat].push(source);
        });
        
        let html = '';
        
        for (const [category, sources] of Object.entries(categories)) {
            html += `
                <div class="source-category">
                    <div class="category-header">${category}</div>
                    <div class="sources-grid">
            `;
            
            sources.forEach(source => {
                html += this.renderSourceCard(source);
            });
            
            html += `
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;
        this.attachEventListeners();
    }
    
    /**
     * Render single source card
     */
    renderSourceCard(source) {
        return `
            <div class="source-card" 
                 data-source-id="${source.id}"
                 data-source-name="${source.name}"
                 data-source-type="generator"
                 draggable="true"
                 title="${source.description || source.name}">
                <div class="source-card-header">
                    <span class="source-icon">🎬</span>
                    <span class="source-name">${source.name}</span>
                </div>
                <div class="source-card-body">
                    <small class="text-muted">${source.description || ''}</small>
                </div>
            </div>
        `;
    }
    
    /**
     * Attach drag event listeners
     */
    attachEventListeners() {
        const sourceCards = document.querySelectorAll(`#${this.containerId} .source-card`);
        
        sourceCards.forEach(card => {
            card.addEventListener('dragstart', (e) => {
                const sourceId = card.getAttribute('data-source-id');
                const sourceName = card.getAttribute('data-source-name');
                const sourceType = card.getAttribute('data-source-type');
                e.dataTransfer.setData('generatorId', sourceId);
                e.dataTransfer.setData('generatorName', sourceName);
                e.dataTransfer.effectAllowed = 'copy';
                card.classList.add('dragging');
            });
            
            card.addEventListener('dragend', (e) => {
                card.classList.remove('dragging');
            });
        });
    }
    
    /**
     * Show error message
     */
    showError(message) {
        const container = document.getElementById(this.containerId);
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">⚠️</div>
                <p>${message}</p>
            </div>
        `;
    }
    
    /**
     * Refresh sources list
     */
    async refresh() {
        await this.loadSources();
    }
}
