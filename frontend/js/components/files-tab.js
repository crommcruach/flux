/**
 * Files Tab Component
 * Reusable component for file browser with video and image support
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

export class FilesTab {
    constructor(containerId, searchContainerId, viewMode = 'list', enableMultiselect = false) {
        this.containerId = containerId;
        this.searchContainerId = searchContainerId;
        this.files = [];
        this.filteredFiles = [];
        this.searchTerm = '';
        this.viewMode = viewMode; // 'list', 'tree', or 'button' (button = user can toggle)
        this.currentView = viewMode === 'button' ? 'list' : viewMode; // Actual view when in button mode
        this.expandedFolders = new Set();
        this.enableMultiselect = enableMultiselect; // Enable multiselect mode
        this.selectedFiles = new Set(); // Track selected files in multiselect mode
    }
    
    /**
     * Initialize the component
     */
    async init() {
        this.setupSearch();
        if (this.viewMode === 'button') {
            this.setupViewToggle();
        }
        await this.loadFiles();
    }
    
    /**
     * Setup search functionality
     */
    setupSearch() {
        const searchContainer = document.getElementById(this.searchContainerId);
        if (!searchContainer) return;
        
        // Show toggle button only in 'button' mode
        const showButton = this.viewMode === 'button';
        
        searchContainer.innerHTML = `
            <div class="search-box ${showButton ? 'd-flex gap-2' : ''}">
                <input type="text" 
                       class="form-control form-control-sm ${showButton ? 'flex-grow-1' : ''}" 
                       placeholder="🔍 Search files..." 
                       id="${this.searchContainerId}-input">
                ${showButton ? `
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
        const response = await fetch('/api/files/videos');
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
     * Filter files based on search term
     */
    filterFiles() {
        const activeView = this.viewMode === 'button' ? this.currentView : this.viewMode;
        
        if (activeView === 'list') {
            // Filter list view
            if (!this.searchTerm) {
                this.filteredFiles = [...this.files];
            } else {
                this.filteredFiles = this.files.filter(file => {
                    const filename = file.filename?.toLowerCase() || '';
                    const path = file.path?.toLowerCase() || '';
                    
                    return filename.includes(this.searchTerm) || 
                           path.includes(this.searchTerm);
                });
            }
        } else if (activeView === 'tree') {
            // For tree view, we'll filter during render
            // Just trigger a re-render
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
    }
    
    /**
     * Filter tree nodes based on search term
     */
    filterTreeNodes(nodes) {
        const filtered = [];
        
        for (const node of nodes) {
            if (node.type === 'file') {
                // Check if file matches search
                const name = node.name?.toLowerCase() || '';
                const path = node.path?.toLowerCase() || '';
                
                if (name.includes(this.searchTerm) || path.includes(this.searchTerm)) {
                    filtered.push(node);
                }
            } else if (node.type === 'folder') {
                // Recursively filter children
                const filteredChildren = node.children ? this.filterTreeNodes(node.children) : [];
                
                // Include folder if it has matching children or matches itself
                const name = node.name?.toLowerCase() || '';
                if (filteredChildren.length > 0 || name.includes(this.searchTerm)) {
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
            const icon = node.type === 'video' ? '🎬' : '🖼️';
            const isSelected = this.selectedFiles.has(node.path);
            
            return `
                <div class="tree-node file ${isSelected ? 'selected' : ''}" 
                     style="padding-left: ${indent}px" 
                     data-path="${node.path}"
                     data-type="${node.type}"
                     draggable="true">
                    <span class="tree-node-icon">${icon}</span>
                    <span class="tree-node-name">${node.name}</span>
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
            const icon = file.type === 'video' ? '🎬' : '🖼️';
            const isSelected = this.selectedFiles.has(file.path);
            
            html += `
                <div class="file-item ${isSelected ? 'selected' : ''}" 
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
        
        html += '</div>';
        
        container.innerHTML = html;
        this.attachListEventListeners();
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
}
