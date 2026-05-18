/**
 * Sources Tab Component
 * Reusable component for displaying available generator sources
 */

import { debug } from '../logger.js';

export class SourcesTab {
    constructor(containerId, searchContainerId) {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.sources = [];
        this.filteredSources = [];
        this.searchTerm = '';
        this.contextMenu = null;
        this.contextMenuTarget = null; // {sourceId, sourceName}
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        this.setupContextMenu();
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
     * Setup context menu
     */
    setupContextMenu() {
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'file-context-menu';
        this.contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="playlist1">
                <i class="bi bi-play-circle"></i> Add to Video Player
            </div>
            <div class="context-menu-item" data-action="playlist2">
                <i class="bi bi-play-circle"></i> Add to Art-Net Player
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

    /**
     * Show context menu at position
     */
    showContextMenu(x, y, sourceId, sourceName) {
        this.contextMenuTarget = { sourceId, sourceName };
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

    /**
     * Hide context menu
     */
    hideContextMenu() {
        this.contextMenu.style.display = 'none';
        this.contextMenuTarget = null;
    }

    /**
     * Handle context menu action
     */
    handleContextMenuAction(action) {
        if (!this.contextMenuTarget) return;
        const { sourceId, sourceName } = this.contextMenuTarget;

        const playerId = action === 'playlist1' ? 'video' : 'artnet';
        window.dispatchEvent(new CustomEvent('addSourceToPlaylistRequested', {
            detail: { generatorId: sourceId, generatorName: sourceName, playerId }
        }));
    }

    /**
     * Attach drag event listeners
     */
    attachEventListeners() {
        const sourceCards = document.querySelectorAll(`#${this.containerId} .source-card, #${this.containerId} .generator-card`);
        
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

            card.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const sourceId = card.getAttribute('data-source-id');
                const sourceName = card.getAttribute('data-source-name');
                this.showContextMenu(e.clientX, e.clientY, sourceId, sourceName);
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
