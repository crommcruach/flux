/**
 * Effects Tab Component
 * Reusable component for displaying available effects
 */

import { debug } from '../logger.js';

export class EffectsTab {
    constructor(containerId, searchContainerId) {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.effects = [];
        this.filteredEffects = [];
        this.searchTerm = '';
        this.contextMenu = null;
        this.contextMenuTarget = null; // {effectId, effectName}
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        this.setupContextMenu();
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
                 data-effect-name="${effect.name}"
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
    setupContextMenu() {
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'file-context-menu';
        this.contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="fx-video">
                <i class="bi bi-camera-video"></i> Add to Video FX
            </div>
            <div class="context-menu-item" data-action="fx-artnet">
                <i class="bi bi-broadcast"></i> Add to Art-Net FX
            </div>
            <div class="context-menu-item" data-action="fx-clip">
                <i class="bi bi-layers"></i> Add to Current Clip Layer FX
            </div>
        `;
        document.body.appendChild(this.contextMenu);

        document.addEventListener('click', (e) => {
            if (!this.contextMenu.contains(e.target)) {
                this.hideContextMenu();
            }
        });

        window.addEventListener('resize', () => { this.hideContextMenu(); });

        this.contextMenu.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                this.handleContextMenuAction(item.getAttribute('data-action'));
                this.hideContextMenu();
            });
        });
    }

    showContextMenu(x, y, effectId, effectName) {
        this.contextMenuTarget = { effectId, effectName };
        this.contextMenu.style.display = 'block';

        const menuWidth = this.contextMenu.offsetWidth;
        const menuHeight = this.contextMenu.offsetHeight;
        const vw = window.innerWidth;
        const vh = window.innerHeight;

        let posX = Math.max(5, x + menuWidth > vw ? vw - menuWidth - 5 : x);
        let posY = Math.max(5, y + menuHeight > vh ? vh - menuHeight - 5 : y);

        this.contextMenu.style.left = `${posX}px`;
        this.contextMenu.style.top  = `${posY}px`;
    }

    hideContextMenu() {
        this.contextMenu.style.display = 'none';
        this.contextMenuTarget = null;
    }

    handleContextMenuAction(action) {
        if (!this.contextMenuTarget) return;
        const { effectId } = this.contextMenuTarget;

        if (action === 'fx-video' && window.addEffectToVideo) {
            window.addEffectToVideo(effectId);
        } else if (action === 'fx-artnet' && window.addEffectToArtnet) {
            window.addEffectToArtnet(effectId);
        } else if (action === 'fx-clip' && window.addEffectToClip) {
            window.addEffectToClip(effectId);
        }
    }

    attachEventListeners() {
        const effectCards = document.querySelectorAll(`#${this.containerId} .effect-card`);
        
        effectCards.forEach(card => {
            card.addEventListener('dragstart', (e) => {
                const effectId = card.getAttribute('data-effect-id');
                e.dataTransfer.setData('effectId', effectId);
                e.dataTransfer.effectAllowed = 'copy';
                card.classList.add('dragging');
            });
            card.addEventListener('dragend', (e) => {
                card.classList.remove('dragging');
            });
            card.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const effectId = card.getAttribute('data-effect-id');
                const effectName = card.getAttribute('data-effect-name');
                this.showContextMenu(e.clientX, e.clientY, effectId, effectName);
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
