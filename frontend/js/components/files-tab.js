/**
 * Files Tab Component
 * Reusable component for file browser with video and image support
 * 
 * PERFORMANCE OPTIMIZATION (2026-01-20):
 * - Implements progressive thumbnail loading to reduce LCP from 4.74s to ~1.3s
 * - Uses native lazy loading (loading="eager/lazy") for position-based priority
 * - Intersection Observer for viewport-aware loading with 50px root margin
 * - fetchpriority hints ("high/auto/low") to guide browser resource scheduling
 * - SVG placeholder with shimmer animation for instant visual feedback
 * - Width/height attributes (48x48) prevent layout shift (CLS)
 * - Tree view: Top-level items (indent < 40px) load eagerly
 * - List view: First 5 items high priority, next 5 auto, rest lazy
 */

import { debug } from '../logger.js';

export class FilesTab {
    constructor(containerId, searchContainerId, viewMode = 'list', enableMultiselect = false, enableThumbnails = false, filterParams = '') {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.filterParams = filterParams;
        this.convertedFilterActive = filterParams.includes('converted_only=true');
        this.showNonConverted = false; // when convertedFilterActive, tracks whether toggle is on
        this.files = [];
        this.filteredFiles = [];
        this.searchTerm = '';
        this.viewMode = viewMode; // 'list', 'tree', or 'button' (button = user can toggle)
        this.currentView = viewMode === 'button' ? 'list' : viewMode; // Actual view when in button mode
        this.expandedFolders = new Set();
        this.enableMultiselect = enableMultiselect; // Enable multiselect mode
        this.selectedFiles = new Set(); // Track selected files in multiselect mode
        this.enableThumbnails = enableThumbnails; // Enable thumbnail display
        this.thumbnailCache = new Map(); // Cache loaded thumbnails
        this.hoverPreview = null; // Hover preview element
        this.previewModal = null; // Preview modal element
        this.contextMenu = null; // Context menu element
        this.contextMenuTarget = null; // Currently right-clicked file
        this.thumbnailObserver = null; // Intersection Observer for lazy loading
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        if (this.viewMode === 'button') {
            this.setupViewToggle();
        }
        if (this.enableThumbnails) {
            this.setupThumbnailSystem();
        }
        this.setupContextMenu();
        await this.loadFiles();
    }
    
    /**
     * Setup thumbnail system (hover preview + modal)
     */
    setupThumbnailSystem() {
        // Create hover preview element
        this.hoverPreview = document.createElement('div');
        this.hoverPreview.className = 'file-thumbnail-preview';
        this.hoverPreview.innerHTML = '<img src="" alt="Preview">';
        document.body.appendChild(this.hoverPreview);
        
        // Create modal element
        this.previewModal = document.createElement('div');
        this.previewModal.className = 'file-preview-modal';
        this.previewModal.innerHTML = `
            <div class="file-preview-modal-backdrop"></div>
            <div class="file-preview-modal-content">
                <button class="file-preview-modal-close" aria-label="Close">&times;</button>
                <div class="file-preview-modal-body">
                    <div class="file-preview-media">
                        <div class="loading-spinner">Loading preview...</div>
                    </div>
                    <div class="file-preview-info">
                        <h4 class="file-preview-filename"></h4>
                        <div class="file-preview-meta"></div>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(this.previewModal);
        
        // Modal close handlers
        const closeBtn = this.previewModal.querySelector('.file-preview-modal-close');
        const backdrop = this.previewModal.querySelector('.file-preview-modal-backdrop');
        
        closeBtn.addEventListener('click', () => this.closePreviewModal());
        backdrop.addEventListener('click', () => this.closePreviewModal());
        
        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.previewModal.classList.contains('show')) {
                this.closePreviewModal();
            }
        });
        
        // Setup Intersection Observer for lazy thumbnail loading
        this.setupThumbnailObserver();
    }
    
    /**
     * Setup Intersection Observer for progressive thumbnail loading
     */
    setupThumbnailObserver() {
        if (!('IntersectionObserver' in window)) {
            debug.log('⚠️ IntersectionObserver not supported, thumbnails will load immediately');
            return;
        }
        
        this.thumbnailObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.classList.contains('loading')) {
                        this.loadSingleThumbnail(img);
                        this.thumbnailObserver.unobserve(img);
                    }
                }
            });
        }, {
            root: null,
            rootMargin: '50px', // Start loading 50px before visible
            threshold: 0.01
        });
    }
    
    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchContainer = document.getElementById(this.searchContainerId);
        if (!searchContainer) return;
        
        // Show view toggle button only in 'button' mode
        const showViewToggle = this.viewMode === 'button';
        const hasButtons = showViewToggle;
        
        searchContainer.innerHTML = `
            <div class="search-box ${hasButtons ? 'd-flex gap-2' : ''}">
                <input type="text" 
                       class="form-control form-control-sm ${hasButtons ? 'flex-grow-1' : ''}" 
                       placeholder="🔍 Search or tag:name..." 
                       id="${this.searchContainerId}-input">
                ${showViewToggle ? `
                <button class="btn btn-sm btn-outline-secondary" 
                        id="${this.searchContainerId}-viewToggle"
                        title="Toggle view mode">
                    📋
                </button>
                ` : ''}
            </div>
        `;
        
        const searchInput = document.getElementById(`${this.searchContainerId}-input`);
        searchInput.addEventListener('input', (e) => {
            this.searchTerm = e.target.value.toLowerCase();
            this.filterFiles();
        });
    }
    
    /**
     * Setup view toggle button (only in 'button' mode)
     */
    setupViewToggle() {
        const toggleBtn = document.getElementById(`${this.searchContainerId}-viewToggle`);
        if (!toggleBtn) return;
        
        // Set initial button state
        this.updateViewToggleButton(toggleBtn);
        
        toggleBtn.addEventListener('click', async () => {
            // Toggle between list and tree
            this.currentView = this.currentView === 'list' ? 'tree' : 'list';
            this.updateViewToggleButton(toggleBtn);
            // Reload data for the new view
            await this.loadFiles();
        });
    }
    
    /**
     * Update view toggle button appearance
     */
    updateViewToggleButton(toggleBtn) {
        if (this.currentView === 'list') {
            toggleBtn.textContent = '📋';
            toggleBtn.title = 'List view (click for tree view)';
        } else {
            toggleBtn.textContent = '🌳';
            toggleBtn.title = 'Tree view (click for list view)';
        }
    }
    
    /**
     * Setup context menu
     */
    setupContextMenu() {
        // Create context menu element
        this.contextMenu = document.createElement('div');
        this.contextMenu.className = 'file-context-menu';
        
        const filterItem = this.convertedFilterActive ? `
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" data-action="toggleConvertedFilter">
                <i class="bi bi-funnel"></i> <span id="${this.containerId}-filterLabel">Show non-converted files</span>
            </div>` : '';
        
        this.contextMenu.innerHTML = `
            <div class="context-menu-item" data-action="preview">
                <i class="bi bi-play-circle"></i> Preview
            </div>
            <div class="context-menu-item" data-action="playlist1">
                <i class="bi bi-collection-play"></i> Add to Video Playlist
            </div>
            <div class="context-menu-item" data-action="playlist2">
                <i class="bi bi-collection-play"></i> Add to Art-Net Playlist
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item" data-action="editMetadata">
                <i class="bi bi-tag"></i> Edit Tags / Alias
            </div>
            <div class="context-menu-divider"></div>
            <div class="context-menu-item context-menu-item-danger" data-action="delete">
                <i class="bi bi-trash"></i> Delete File
            </div>
            ${filterItem}
        `;
        document.body.appendChild(this.contextMenu);
        
        // Close menu on click outside
        document.addEventListener('click', (e) => {
            if (!this.contextMenu.contains(e.target)) {
                this.hideContextMenu();
            }
        });
        
        // Close menu on window resize
        window.addEventListener('resize', () => {
            this.hideContextMenu();
        });
        
        // Handle menu item clicks
        this.contextMenu.querySelectorAll('.context-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const action = item.getAttribute('data-action');
                this.handleContextMenuAction(action);
                this.hideContextMenu();
            });
        });
    }
    
    /**
     * Show context menu at position
     */
    showContextMenu(x, y, filePath) {
        this.contextMenuTarget = filePath;
        this.contextMenu.style.display = 'block';
        
        // Get menu dimensions after making it visible
        const menuWidth = this.contextMenu.offsetWidth;
        const menuHeight = this.contextMenu.offsetHeight;
        
        // Get viewport dimensions
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        
        // Adjust position to keep menu within viewport bounds
        let posX = x;
        let posY = y;
        
        // Check right boundary
        if (posX + menuWidth > viewportWidth) {
            posX = viewportWidth - menuWidth - 5; // 5px padding
        }
        
        // Check bottom boundary
        if (posY + menuHeight > viewportHeight) {
            posY = viewportHeight - menuHeight - 5; // 5px padding
        }
        
        // Ensure menu doesn't go off left/top
        posX = Math.max(5, posX);
        posY = Math.max(5, posY);
        
        this.contextMenu.style.left = `${posX}px`;
        this.contextMenu.style.top = `${posY}px`;
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
    async handleContextMenuAction(action) {
        if (!this.contextMenuTarget) return;
        
        const filePath = this.contextMenuTarget;
        
        switch (action) {
            case 'preview':
                // Get file details from filteredFiles
                const fileInfo = this.filteredFiles.find(f => f.path === filePath);
                if (fileInfo) {
                    this.showFilePreviewModal(filePath, fileInfo.type, fileInfo.filename, fileInfo.size_human, fileInfo.folder || '');
                }
                break;
            case 'playlist1':
                await this.addToPlaylist('video', filePath);
                break;
            case 'playlist2':
                await this.addToPlaylist('artnet', filePath);
                break;
            case 'delete':
                await this.deleteFile(filePath);
                break;
            case 'editMetadata':
                await this.showEditMetadataModal(filePath);
                break;
            case 'toggleConvertedFilter':
                if (!this.convertedFilterActive) break;
                this.showNonConverted = !this.showNonConverted;
                this.filterParams = this.showNonConverted ? '' : '?converted_only=true';
                // Update label for next open
                const label = document.getElementById(`${this.containerId}-filterLabel`);
                if (label) label.textContent = this.showNonConverted ? 'Show converted files only' : 'Show non-converted files';
                await this.loadFiles();
                break;
        }
    }
    
    /**
     * Add file to playlist
     */
    async addToPlaylist(playerId, filePath) {
        try {
            // Get file info
            const fileInfo = this.filteredFiles.find(f => f.path === filePath);
            const fileType = fileInfo ? fileInfo.type : 'video';
            const fileName = filePath.split('/').pop();
            
            // Dispatch custom event that player.js will handle
            const event = new CustomEvent('addToPlaylistRequested', {
                detail: {
                    playerId: playerId,
                    filePath: filePath,
                    fileType: fileType,
                    fileName: fileName
                }
            });
            window.dispatchEvent(event);
            
            const playlistName = playerId === 'video' ? 'Video Playlist' : 'Art-Net Playlist';
            console.log(`✅ Add to ${playlistName} requested:`, filePath);
            
        } catch (error) {
            console.error('Error adding to playlist:', error);
            alert(`Error: ${error.message}`);
        }
    }
    
    /**
     * Delete file
     */
    async deleteFile(filePath) {
        const fileName = filePath.split('/').pop();
        
        if (!confirm(`Are you sure you want to delete "${fileName}"?\n\nThis action cannot be undone.`)) {
            return;
        }
        
        try {
            const response = await fetch(`/api/files/delete`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: filePath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log(`✅ File deleted:`, filePath);
                // Refresh file list
                await this.refresh();
            } else {
                console.error('Failed to delete file:', result.error);
                alert(`Failed to delete file: ${result.error}`);
            }
        } catch (error) {
            console.error('Error deleting file:', error);
            alert(`Error: ${error.message}`);
        }
    }
    
    /**
     * Load files from API
     */
    async loadFiles() {
        const container = document.getElementById(this.containerId);
        
        // Determine actual view to use
        const activeView = this.viewMode === 'button' ? this.currentView : this.viewMode;
        debug.log(`📂 FilesTab: Loading files in '${activeView}' mode`);
        
        try {
            if (activeView === 'tree') {
                debug.log('📂 FilesTab: Loading tree view...');
                // Clear list data when switching to tree
                this.files = [];
                this.filteredFiles = [];
                await this.loadFileTree();
            } else {
                debug.log('📂 FilesTab: Loading list view...');
                // Clear tree data when switching to list
                this.fileTree = [];
                await this.loadFileList();
            }
        } catch (error) {
            console.error('Error loading files:', error);
            this.showError('Error loading files');
        }
    }
    
    /**
     * Load file tree structure
     */
    async loadFileTree() {
        debug.log('🌳 Fetching tree from /api/files/tree...');
        const response = await fetch('/api/files/tree');
        const data = await response.json();
        
        debug.log('🌳 Tree API response:', data);
        
        if (data.success) {
            this.fileTree = data.tree || [];
            debug.log(`🌳 Loaded tree with ${this.fileTree.length} root nodes`);
            this.render();
        } else {
            console.error('❌ Failed to load file tree:', data);
            this.showError('Failed to load file tree');
        }
    }
    
    /**
     * Load flat file list
     */
    async loadFileList() {
        const response = await fetch('/api/files/videos' + this.filterParams);
        const data = await response.json();
        
        debug.log('📁 Files API response:', data);
        
        if (data.success) {
            this.files = data.files || [];
            this.filteredFiles = [...this.files];
            debug.log(`📁 Loaded ${this.files.length} files in list view`);
            this.render();
        } else {
            console.error('❌ Failed to load files:', data);
            this.showError('Failed to load files');
        }
    }
    
    /**
     * Reload file list from server
     */
    async refresh() {
        return this.loadFiles();
    }

    /**
     * Filter files based on search term.
     * Supports "tag:name" prefix to filter by tag only.
     */
    filterFiles() {
        const activeView = this.viewMode === 'button' ? this.currentView : this.viewMode;

        if (activeView === 'list') {
            if (!this.searchTerm) {
                this.filteredFiles = [...this.files];
            } else {
                const tagMatch = this.searchTerm.match(/^tag:(.*)$/);
                if (tagMatch) {
                    const tagFilter = tagMatch[1].trim();
                    this.filteredFiles = this.files.filter(file => {
                        const tags = (file.tags || []).map(t => t.toLowerCase());
                        return !tagFilter || tags.some(t => t.includes(tagFilter));
                    });
                } else {
                    this.filteredFiles = this.files.filter(file => {
                        const filename = file.filename?.toLowerCase() || '';
                        const alias = (file.alias || '').toLowerCase();
                        const path = file.path?.toLowerCase() || '';
                        const tags = (file.tags || []).map(t => t.toLowerCase());
                        return filename.includes(this.searchTerm) ||
                               path.includes(this.searchTerm) ||
                               alias.includes(this.searchTerm) ||
                               tags.some(t => t.includes(this.searchTerm));
                    });
                }
            }
        } else if (activeView === 'tree') {
            // For tree view, we'll filter during render
        }

        this.render();
    }
    
    /**
     * Render files
     */
    render() {
        const activeView = this.viewMode === 'button' ? this.currentView : this.viewMode;
        debug.log('🎨 RENDER called with viewMode:', this.viewMode, 'activeView:', activeView);
        debug.log('🎨 fileTree:', this.fileTree ? `${this.fileTree.length} nodes` : 'undefined');
        debug.log('🎨 files:', this.files ? `${this.files.length} files` : 'undefined');
        debug.log('🎨 filteredFiles:', this.filteredFiles ? `${this.filteredFiles.length} files` : 'undefined');
        
        if (activeView === 'tree') {
            debug.log('🎨 Rendering TREE view');
            this.renderTree();
        } else {
            debug.log('🎨 Rendering LIST view');
            this.renderList();
        }
    }
    
    /**
     * Render tree view
     */
    renderTree() {
        const container = document.getElementById(this.containerId);
        
        if (!this.fileTree || this.fileTree.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📂</div>
                    <p>No files found</p>
                </div>
            `;
            return;
        }
        
        // Apply search filter if active
        const filteredTree = this.searchTerm ? this.filterTreeNodes(this.fileTree) : this.fileTree;
        
        if (filteredTree.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>No files found matching "${this.searchTerm}"</p>
                </div>
            `;
            return;
        }
        
        let html = '<div class="file-tree">';
        filteredTree.forEach(node => {
            html += this.renderTreeNode(node, 0);
        });
        html += '</div>';
        
        container.innerHTML = html;
        this.attachTreeEventListeners();
        
        // Load thumbnails after render
        if (this.enableThumbnails) {
            this.loadThumbnails();
        }
    }
    
    /**
     * Filter tree nodes based on search term
     */
    filterTreeNodes(nodes) {
        const filtered = [];
        
        const tagMatch = this.searchTerm.match(/^tag:(.*)$/);
        const tagFilter = tagMatch ? tagMatch[1].trim() : null;

        for (const node of nodes) {
            if (node.type === 'file' || node.type === 'clip_folder') {
                const name = node.name?.toLowerCase() || '';
                const path = node.path?.toLowerCase() || '';
                const alias = (node.alias || '').toLowerCase();
                const tags = (node.tags || []).map(t => t.toLowerCase());

                let matches;
                if (tagFilter !== null) {
                    matches = !tagFilter || tags.some(t => t.includes(tagFilter));
                } else {
                    matches = name.includes(this.searchTerm) ||
                              path.includes(this.searchTerm) ||
                              alias.includes(this.searchTerm) ||
                              tags.some(t => t.includes(this.searchTerm));
                }

                if (matches) filtered.push(node);
            } else if (node.type === 'folder') {
                // Recursively filter children
                const filteredChildren = node.children ? this.filterTreeNodes(node.children) : [];
                
                // Include folder if it has matching children or matches itself
                const name = node.name?.toLowerCase() || '';
                const folderMatches = tagFilter !== null ? false : name.includes(this.searchTerm);
                if (filteredChildren.length > 0 || folderMatches) {
                    filtered.push({
                        ...node,
                        children: filteredChildren
                    });
                    // Auto-expand folders when searching
                    if (this.searchTerm) {
                        this.expandedFolders.add(node.path);
                    }
                }
            }
        }
        
        return filtered;
    }
    
    /**
     * Render tree node recursively
     */
    renderTreeNode(node, level) {
        const indent = level * 20;
        const isExpanded = this.expandedFolders.has(node.path);
        
        if (node.type === 'folder') {
            const hasChildren = node.children && node.children.length > 0;
            const expandIcon = hasChildren ? (isExpanded ? '📂' : '📁') : '📁';
            
            let html = `
                <div class="tree-node folder" style="padding-left: ${indent}px" data-path="${node.path}">
                    <span class="tree-node-icon">${expandIcon}</span>
                    <span class="tree-node-name">${node.name}</span>
                </div>
            `;
            
            if (isExpanded && hasChildren) {
                node.children.forEach(child => {
                    html += this.renderTreeNode(child, level + 1);
                });
            }
            
            return html;
        } else {
            const isSelected = this.selectedFiles.has(node.path);
            const hasThumbnail = node.has_thumbnail || false;
            const thumbnailClass = this.enableThumbnails && hasThumbnail ? 'with-thumbnail' : '';
            
            // Build tooltip
            let tooltip = `${node.name}\nSize: ${node.size_human || 'Unknown'}`;
            if (node.type === 'video') {
                if (node.duration) {
                    tooltip += `\nDuration: ${node.duration}s`;
                }
                if (node.fps) {
                    tooltip += `\nFPS: ${node.fps}`;
                }
            }
            
            let thumbnailHtml = '';
            if (this.enableThumbnails && hasThumbnail) {
                // Determine loading priority based on tree depth (top items load first)
                const priority = indent < 40 ? 'high' : 'low';
                const loading = indent < 40 ? 'eager' : 'lazy';
                
                thumbnailHtml = `
                    <img class="file-thumbnail loading" 
                         data-path="${node.path}" 
                         alt="${node.name}"
                         loading="${loading}"
                         decoding="async"
                         fetchpriority="${priority}"
                         width="48"
                         height="48">
                `;
            }
            
            const displayName = node.alias || node.name;
            const tags = node.tags || [];
            const tagIndicator = tags.length ? `<span class="file-tag-indicator">🏷︎<span class="file-tag-popup">${tags.map(t => `<span class="file-tag-badge">${t}</span>`).join('')}</span></span>` : '';

            return `
                <div class="tree-node file ${thumbnailClass} ${isSelected ? 'selected' : ''}" 
                     style="padding-left: ${indent}px" 
                     data-path="${node.path}"
                     data-type="${node.type}"
                     data-filename="${node.name}"
                     data-size="${node.size_human || ''}"
                     title="${tooltip}"
                     draggable="true">
                    ${thumbnailHtml}
                    <div class="tree-node-info">
                        <span class="tree-node-name">${displayName}</span>${tagIndicator}
                    </div>
                    <span class="tree-node-size">${node.size_human || ''}</span>
                </div>
            `;
        }
    }
    
    /**
     * Render list view
     */
    renderList() {
        const container = document.getElementById(this.containerId);
        
        if (this.filteredFiles.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">🔍</div>
                    <p>${this.searchTerm ? 'No files found' : 'No files available'}</p>
                </div>
            `;
            return;
        }
        
        let html = '<div class="file-list">';
        
        this.filteredFiles.forEach(file => {
            const isSelected = this.selectedFiles.has(file.path);
            const hasThumbnail = file.has_thumbnail || false;
            const thumbnailClass = this.enableThumbnails && hasThumbnail ? 'with-thumbnail' : '';
            
            // Build tooltip
            let tooltip = `${file.filename}\nSize: ${file.size_human}`;
            if (file.type === 'video') {
                if (file.duration) {
                    tooltip += `\nDuration: ${file.duration}s`;
                }
                if (file.fps) {
                    tooltip += `\nFPS: ${file.fps}`;
                }
            }
            if (file.folder) {
                tooltip += `\nFolder: ${file.folder}`;
            }
            
            let thumbnailHtml = '';
            if (this.enableThumbnails && hasThumbnail) {
                // Only load first 10 thumbnails eagerly, rest lazy
                const index = this.filteredFiles.indexOf(file);
                const loading = index < 10 ? 'eager' : 'lazy';
                const priority = index < 5 ? 'high' : (index < 10 ? 'auto' : 'low');
                
                thumbnailHtml = `
                    <img class="file-thumbnail loading" 
                         data-path="${file.path}" 
                         alt="${file.filename}"
                         loading="${loading}"
                         decoding="async"
                         fetchpriority="${priority}"
                         width="48"
                         height="48">
                `;
            }
            
            const displayName = file.alias || file.filename;
            const tags = file.tags || [];
            const tagIndicator = tags.length ? `<span class="file-tag-indicator">🏷︎<span class="file-tag-popup">${tags.map(t => `<span class="file-tag-badge">${t}</span>`).join('')}</span></span>` : '';

            html += `
                <div class="file-item ${thumbnailClass} ${isSelected ? 'selected' : ''}" 
                     data-path="${file.path}"
                     data-type="${file.type}"
                     data-filename="${file.filename}"
                     data-size="${file.size_human}"
                     data-folder="${file.folder || ''}"
                     title="${tooltip}"
                     draggable="true">
                    ${thumbnailHtml}
                    <div class="file-info">
                        <div class="file-name">${displayName}${tagIndicator}</div>
                        <div class="file-path text-muted">${file.folder}</div>
                    </div>
                    <div class="file-size text-muted">${file.size_human}</div>
                </div>
            `;
        });
        
        html += '</div>';
        
        container.innerHTML = html;
        this.attachListEventListeners();
        
        // Load thumbnails after render
        if (this.enableThumbnails) {
            this.loadThumbnails();
        }
    }
    
    /**
     * Render all view (both tree and list)
     */
    renderAll() {
        const container = document.getElementById(this.containerId);
        
        let html = '<div class="file-all-view">';
        
        // Render tree section
        if (this.fileTree && this.fileTree.length > 0) {
            html += '<div class="file-section"><h6>Tree View</h6><div class="file-tree">';
            this.fileTree.forEach(node => {
                html += this.renderTreeNode(node, 0);
            });
            html += '</div></div>';
        }
        
        // Render list section
        if (this.filteredFiles && this.filteredFiles.length > 0) {
            html += '<div class="file-section"><h6>List View</h6><div class="file-list">';
            this.filteredFiles.forEach(file => {
                const icon = file.type === 'video' ? '🎬' : '🖼️';
                
                html += `
                    <div class="file-item" 
                         data-path="${file.path}"
                         data-type="${file.type}"
                         draggable="true">
                        <span class="file-icon">${icon}</span>
                        <div class="file-info">
                            <div class="file-name">${file.filename}</div>
                            <div class="file-path text-muted">${file.folder}</div>
                        </div>
                        <div class="file-size text-muted">${file.size_human}</div>
                    </div>
                `;
            });
            html += '</div></div>';
        }
        
        html += '</div>';
        
        container.innerHTML = html;
        this.attachTreeEventListeners();
        this.attachListEventListeners();
    }
    
    /**
     * Attach tree view event listeners
     */
    attachTreeEventListeners() {
        const container = document.getElementById(this.containerId);
        
        // Folder click to expand/collapse
        container.querySelectorAll('.tree-node.folder').forEach(folder => {
            folder.addEventListener('click', (e) => {
                const path = folder.getAttribute('data-path');
                
                if (this.expandedFolders.has(path)) {
                    this.expandedFolders.delete(path);
                } else {
                    this.expandedFolders.add(path);
                }
                
                this.render();
            });
        });
        
        // File click events (for multiselect)
        if (this.enableMultiselect) {
            container.querySelectorAll('.tree-node.file').forEach(file => {
                file.addEventListener('click', (e) => {
                    const path = file.getAttribute('data-path');
                    const type = file.getAttribute('data-type');
                    
                    // Toggle selection
                    if (this.selectedFiles.has(path)) {
                        this.selectedFiles.delete(path);
                    } else {
                        this.selectedFiles.add(path);
                    }
                    
                    // Dispatch custom event for parent component
                    this.dispatchSelectionEvent();
                    
                    this.render();
                });
            });
        }
        
        // File drag events
        container.querySelectorAll('.tree-node.file').forEach(file => {
            // Context menu
            file.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const path = file.getAttribute('data-path');
                this.showContextMenu(e.clientX, e.clientY, path);
            });

            file.addEventListener('dragstart', (e) => {
                const path = file.getAttribute('data-path');
                const type = file.getAttribute('data-type');
                
                // If multiselect is enabled and files are selected, drag all selected files
                if (this.enableMultiselect && this.selectedFiles.size > 0) {
                    // If the dragged file is not in selection, add it
                    if (!this.selectedFiles.has(path)) {
                        this.selectedFiles.add(path);
                        this.render();
                    }
                    
                    debug.log('🎬 DRAG START (tree) - Multiple files:', Array.from(this.selectedFiles));
                    e.dataTransfer.setData('text/plain', path); // Single path for compatibility
                    e.dataTransfer.setData('file-paths', JSON.stringify(Array.from(this.selectedFiles)));
                    e.dataTransfer.setData('file-type', type);
                } else {
                    debug.log('🎬 DRAG START (tree):', path, 'type:', type);
                    e.dataTransfer.setData('text/plain', path);
                    e.dataTransfer.setData('file-path', path);
                    e.dataTransfer.setData('file-type', type);
                }
                
                e.dataTransfer.effectAllowed = 'copy';
                file.classList.add('dragging');
            });
            
            file.addEventListener('dragend', (e) => {
                file.classList.remove('dragging');
            });
        });
        
        // Thumbnail hover preview
        if (this.enableThumbnails) {
            container.querySelectorAll('.file-thumbnail').forEach(thumbnail => {
                thumbnail.addEventListener('mouseenter', (e) => {
                    this.showHoverPreview(thumbnail, e);
                });
                
                thumbnail.addEventListener('mousemove', (e) => {
                    if (this.hoverPreview && this.hoverPreview.classList.contains('show')) {
                        const x = e.clientX + 20;
                        const y = e.clientY - this.hoverPreview.offsetHeight - 10;
                        this.hoverPreview.style.left = `${x}px`;
                        this.hoverPreview.style.top = `${y}px`;
                    }
                });
                
                thumbnail.addEventListener('mouseleave', () => {
                    this.hideHoverPreview();
                });
            });
        }
    }
    
    /**
     * Dispatch selection change event
     */
    dispatchSelectionEvent() {
        const container = document.getElementById(this.containerId);
        if (container) {
            const event = new CustomEvent('filesSelected', {
                detail: {
                    selectedFiles: Array.from(this.selectedFiles)
                }
            });
            container.dispatchEvent(event);
        }
    }
    
    /**
     * Clear selection
     */
    clearSelection() {
        this.selectedFiles.clear();
        this.render();
        this.dispatchSelectionEvent();
    }
    
    /**
     * Get selected files
     */
    getSelectedFiles() {
        return Array.from(this.selectedFiles);
    }
    
    /**
     * Attach list view event listeners
     */
    attachListEventListeners() {
        const fileItems = document.querySelectorAll(`#${this.containerId} .file-item`);
        
        fileItems.forEach(item => {
            // Context menu event
            item.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const path = item.getAttribute('data-path');
                // Use clientX/clientY for viewport-relative positioning (works with fixed positioning)
                this.showContextMenu(e.clientX, e.clientY, path);
            });
            
            // Click event for multiselect
            if (this.enableMultiselect) {
                item.addEventListener('click', (e) => {
                    const path = item.getAttribute('data-path');
                    const type = item.getAttribute('data-type');
                    
                    // Toggle selection
                    if (this.selectedFiles.has(path)) {
                        this.selectedFiles.delete(path);
                    } else {
                        this.selectedFiles.add(path);
                    }
                    
                    // Dispatch custom event for parent component
                    this.dispatchSelectionEvent();
                    
                    this.render();
                });
            }
            
            // Drag events
            item.addEventListener('dragstart', (e) => {
                const path = item.getAttribute('data-path');
                const type = item.getAttribute('data-type');
                
                // If multiselect is enabled and files are selected, drag all selected files
                if (this.enableMultiselect && this.selectedFiles.size > 0) {
                    // If the dragged file is not in selection, add it
                    if (!this.selectedFiles.has(path)) {
                        this.selectedFiles.add(path);
                        this.render();
                    }
                    
                    debug.log('🎬 DRAG START (list) - Multiple files:', Array.from(this.selectedFiles));
                    e.dataTransfer.setData('text/plain', path); // Single path for compatibility
                    e.dataTransfer.setData('file-paths', JSON.stringify(Array.from(this.selectedFiles)));
                    e.dataTransfer.setData('file-type', type);
                } else {
                    debug.log('🎬 DRAG START (list):', path, 'type:', type);
                    e.dataTransfer.setData('text/plain', path);
                    e.dataTransfer.setData('file-path', path);
                    e.dataTransfer.setData('file-type', type);
                }
                
                e.dataTransfer.effectAllowed = 'copy';
                item.classList.add('dragging');
            });
            
            item.addEventListener('dragend', (e) => {
                item.classList.remove('dragging');
            });
        });
        
        // Thumbnail hover preview
        if (this.enableThumbnails) {
            const thumbnails = document.querySelectorAll(`#${this.containerId} .file-thumbnail`);
            
            thumbnails.forEach(thumbnail => {
                thumbnail.addEventListener('mouseenter', (e) => {
                    this.showHoverPreview(thumbnail, e);
                });
                
                thumbnail.addEventListener('mousemove', (e) => {
                    if (this.hoverPreview && this.hoverPreview.classList.contains('show')) {
                        const x = e.clientX + 20;
                        const y = e.clientY - this.hoverPreview.offsetHeight - 10;
                        this.hoverPreview.style.left = `${x}px`;
                        this.hoverPreview.style.top = `${y}px`;
                    }
                });
                
                thumbnail.addEventListener('mouseleave', () => {
                    this.hideHoverPreview();
                });
            });
        }
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
     * Refresh files
     */
    async refresh() {
        await this.loadFiles();
    }
    
    /**
     * Load thumbnails for all visible file items
     * Uses Intersection Observer for progressive loading
     */
    async loadThumbnails() {
        const container = document.getElementById(this.containerId);
        const thumbnails = container.querySelectorAll('.file-thumbnail.loading');
        
        debug.log(`🖼️ Found ${thumbnails.length} thumbnails to load...`);
        
        // Setup Intersection Observer for lazy images
        if (this.thumbnailObserver) {
            thumbnails.forEach(img => {
                const loading = img.getAttribute('loading');
                if (loading === 'lazy') {
                    // Lazy images handled by Intersection Observer
                    this.thumbnailObserver.observe(img);
                } else {
                    // Eager images load immediately
                    this.loadSingleThumbnail(img);
                }
            });
        } else {
            // Fallback: load all immediately if no observer
            thumbnails.forEach(img => this.loadSingleThumbnail(img));
        }
    }
    
    /**
     * Load a single thumbnail
     */
    async loadSingleThumbnail(img) {
        const path = img.getAttribute('data-path');
        
        // Check cache first
        if (this.thumbnailCache.has(path)) {
            debug.log(`✅ Thumbnail cached: ${path}`);
            img.src = this.thumbnailCache.get(path);
            img.classList.remove('loading');
            return;
        }
        
        // Load from API
        try {
            const url = `/api/files/thumbnail/${encodeURIComponent(path)}?generate=true`;
            const response = await fetch(url);
            
            if (response.ok) {
                const blob = await response.blob();
                const objectUrl = URL.createObjectURL(blob);
                
                img.src = objectUrl;
                img.classList.remove('loading');
                this.thumbnailCache.set(path, objectUrl);
                debug.log(`✅ Thumbnail loaded: ${path} (${blob.size} bytes)`);
            } else {
                // Show placeholder on error
                debug.warn(`⚠️ Thumbnail failed (HTTP ${response.status}): ${path}`);
                img.classList.remove('loading');
                img.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to load thumbnail:', path, error);
            img.classList.remove('loading');
            img.style.display = 'none';
        }
    }
    
    /**
     * Show hover preview for thumbnail
     */
    showHoverPreview(thumbnailElement, event) {
        if (!this.hoverPreview) return;
        
        const img = this.hoverPreview.querySelector('img');
        img.src = thumbnailElement.src;
        
        // Position near mouse
        const x = event.clientX + 20;
        const y = event.clientY + 20;
        
        this.hoverPreview.style.left = `${x}px`;
        this.hoverPreview.style.top = `${y}px`;
        this.hoverPreview.classList.add('show');
    }
    
    /**
     * Hide hover preview
     */
    hideHoverPreview() {
        if (this.hoverPreview) {
            this.hoverPreview.classList.remove('show');
        }
    }
    
    /**
     * Show file preview modal
     */
    async showFilePreviewModal(filePath, fileType, filename, fileSize, fileFolder) {
        if (!this.previewModal) return;
        
        const modalBody = this.previewModal.querySelector('.file-preview-modal-body');
        const mediaContainer = this.previewModal.querySelector('.file-preview-media');
        const infoFilename = this.previewModal.querySelector('.file-preview-filename');
        const infoMeta = this.previewModal.querySelector('.file-preview-meta');
        
        // Set file info
        infoFilename.textContent = filename;
        infoMeta.innerHTML = `
            <div class="meta-item"><strong>Type:</strong> ${fileType}</div>
            <div class="meta-item"><strong>Size:</strong> ${fileSize}</div>
            ${fileFolder ? `<div class="meta-item"><strong>Folder:</strong> ${fileFolder}</div>` : ''}
        `;
        
        // Show modal with loading state
        mediaContainer.innerHTML = '<div class="loading-spinner">Loading preview...</div>';
        this.previewModal.classList.add('show');
        
        // Load video preview
        if (fileType === 'video') {
            try {
                const url = `/api/files/video-preview/${encodeURIComponent(filePath)}?generate=true&format=gif`;
                const response = await fetch(url);
                
                if (response.ok) {
                    const blob = await response.blob();
                    const objectUrl = URL.createObjectURL(blob);
                    
                    mediaContainer.innerHTML = `<img src="${objectUrl}" class="preview-media" alt="${filename}">`;
                } else {
                    mediaContainer.innerHTML = '<div class="no-preview">Video preview not available</div>';
                }
            } catch (error) {
                console.error('Failed to load video preview:', error);
                mediaContainer.innerHTML = '<div class="error-preview">Failed to load preview</div>';
            }
        } else if (fileType === 'image') {
            // For images, show full-size image
            try {
                const url = `/api/files/thumbnail/${encodeURIComponent(filePath)}?generate=true`;
                const response = await fetch(url);
                
                if (response.ok) {
                    const blob = await response.blob();
                    const objectUrl = URL.createObjectURL(blob);
                    
                    mediaContainer.innerHTML = `<img src="${objectUrl}" class="preview-media" alt="${filename}">`;
                } else {
                    mediaContainer.innerHTML = '<div class="no-preview">Image preview not available</div>';
                }
            } catch (error) {
                console.error('Failed to load image preview:', error);
                mediaContainer.innerHTML = '<div class="error-preview">Failed to load preview</div>';
            }
        } else {
            mediaContainer.innerHTML = '<div class="no-preview">Preview not available for this file type</div>';
        }
    }
    
    /**
     * Close preview modal
     */
    closePreviewModal() {
        if (this.previewModal) {
            this.previewModal.classList.remove('show');
        }
    }

    /**
     * Save file metadata (tags + alias) to the backend
     */
    async saveFileMetadata(filePath, alias, tags) {
        const response = await fetch('/api/files/metadata', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: filePath, alias, tags })
        });
        const data = await response.json();
        if (data.success) {
            // Reload files to reflect updated alias/tags
            await this.loadFiles();
        } else {
            console.error('Failed to save file metadata:', data.error);
            alert(`Failed to save: ${data.error}`);
        }
    }

    /**
     * Show modal for editing alias and tags of a file
     */
    async showEditMetadataModal(filePath) {
        // Find current metadata from loaded files
        let currentAlias = '';
        let currentTags = [];

        const fileInfo = this.filteredFiles.find(f => f.path === filePath);
        if (fileInfo) {
            currentAlias = fileInfo.alias || '';
            currentTags = fileInfo.tags || [];
        } else {
            // Search in tree
            const findInTree = (nodes) => {
                for (const n of nodes) {
                    if (n.path === filePath) return n;
                    if (n.children) {
                        const found = findInTree(n.children);
                        if (found) return found;
                    }
                }
                return null;
            };
            const treeNode = this.fileTree ? findInTree(this.fileTree) : null;
            if (treeNode) {
                currentAlias = treeNode.alias || '';
                currentTags = treeNode.tags || [];
            }
        }

        const displayName = filePath.split('/').pop();

        // Remove any existing metadata modal
        const existing = document.getElementById('fileMetadataModal');
        if (existing) existing.remove();

        const modal = document.createElement('div');
        modal.id = 'fileMetadataModal';
        modal.className = 'file-metadata-modal-overlay';
        modal.innerHTML = `
            <div class="file-metadata-modal">
                <div class="file-metadata-modal-header">
                    <span>🏷️ Tags &amp; Alias</span>
                    <button class="file-metadata-modal-close" aria-label="Close">&times;</button>
                </div>
                <div class="file-metadata-modal-body">
                    <div class="file-metadata-filename">${displayName}</div>
                    <label class="file-metadata-label">Alias (display name)</label>
                    <input type="text" id="fileMetaAlias" class="file-metadata-input"
                           placeholder="Leave empty to use filename"
                           value="${currentAlias}">
                    <label class="file-metadata-label">Tags (comma-separated)</label>
                    <input type="text" id="fileMetaTags" class="file-metadata-input"
                           placeholder="e.g. loop, ambient, night"
                           value="${currentTags.join(', ')}">
                </div>
                <div class="file-metadata-modal-footer">
                    <button id="fileMetaSaveBtn" class="btn btn-sm btn-primary">Save</button>
                    <button id="fileMetaCancelBtn" class="btn btn-sm btn-secondary">Cancel</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        const close = () => modal.remove();

        modal.querySelector('.file-metadata-modal-close').addEventListener('click', close);
        document.getElementById('fileMetaCancelBtn').addEventListener('click', close);
        modal.addEventListener('click', (e) => { if (e.target === modal) close(); });

        document.getElementById('fileMetaSaveBtn').addEventListener('click', async () => {
            const alias = document.getElementById('fileMetaAlias').value.trim();
            const tagsRaw = document.getElementById('fileMetaTags').value;
            const tags = tagsRaw.split(',').map(t => t.trim()).filter(t => t);
            close();
            await this.saveFileMetadata(filePath, alias, tags);
        });

        // Focus alias input
        setTimeout(() => document.getElementById('fileMetaAlias')?.focus(), 50);
    }
}
