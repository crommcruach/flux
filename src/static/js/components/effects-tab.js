/**
 * Effects Tab Component
 * Reusable component for displaying available effects
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

export class EffectsTab {
    constructor(containerId, searchContainerId) {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.effects = [];
        this.filteredEffects = [];
        this.searchTerm = '';
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        await this.loadEffects();
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
                       placeholder="🔍 Search effects..." 
                       id="${this.searchContainerId}-input">
            </div>
        `;
        
        const searchInput = document.getElementById(`${this.searchContainerId}-input`);
        searchInput.addEventListener('input', (e) => {
            this.searchTerm = e.target.value.toLowerCase();
            this.filterEffects();
        });
    }
    
    /**
     * Load effects from API
     */
    async loadEffects() {
        const container = document.getElementById(this.containerId);
        
        try {
            const response = await fetch('/api/plugins/list?type=effect');
            const data = await response.json();
            
            if (data.success) {
                this.effects = data.plugins || [];
                this.filteredEffects = [...this.effects];
                this.render();
            } else {
                this.showError('Failed to load effects');
            }
        } catch (error) {
            console.error('Error loading effects:', error);
            this.showError('Error loading effects');
        }
    }
    
    /**
     * Filter effects based on search term
     */
    filterEffects() {
        if (!this.searchTerm) {
            this.filteredEffects = [...this.effects];
        } else {
            this.filteredEffects = this.effects.filter(effect => {
                const name = effect.name?.toLowerCase() || '';
                const description = effect.description?.toLowerCase() || '';
                const category = effect.category?.toLowerCase() || '';
                
                return name.includes(this.searchTerm) || 
                       description.includes(this.searchTerm) ||
                       category.includes(this.searchTerm);
            });
        }
        
        this.render();
    }
    
    /**
     * Render effects list
     */
    render() {
        const container = document.getElementById(this.containerId);
        
        if (this.filteredEffects.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>${this.searchTerm ? 'No effects found' : 'No effects available'}</p>
                </div>
            `;
            return;
        }
        
        // Group by category
        const categories = {};
        this.filteredEffects.forEach(effect => {
            const cat = effect.category || 'Other';
            if (!categories[cat]) {
                categories[cat] = [];
            }
            categories[cat].push(effect);
        });
        
        let html = '';
        
        for (const [category, effects] of Object.entries(categories)) {
            html += `
                <div class="effect-category">
                    <div class="category-header">${category}</div>
                    <div class="effects-grid">
            `;
            
            effects.forEach(effect => {
                html += this.renderEffectCard(effect);
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
     * Render single effect card
     */
    renderEffectCard(effect) {
        return `
            <div class="effect-card" 
                 data-effect-id="${effect.id}"
                 draggable="true"
                 title="${effect.description || effect.name}">
                <div class="effect-card-header">
                    <span class="effect-name">${effect.name}</span>
                </div>
                <div class="effect-card-body">
                    <small class="text-muted">${effect.description || ''}</small>
                </div>
            </div>
        `;
    }
    
    /**
     * Attach drag event listeners
     */
    attachEventListeners() {
        const effectCards = document.querySelectorAll(`#${this.containerId} .effect-card`);
        
        effectCards.forEach(card => {
            card.addEventListener('dragstart', (e) => {
                const effectId = card.getAttribute('data-effect-id');
                e.dataTransfer.setData('effect-id', effectId);
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
     * Refresh effects list
     */
    async refresh() {
        await this.loadEffects();
    }
}
