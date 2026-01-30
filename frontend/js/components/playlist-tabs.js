/**
 * Playlist Tabs Component
 * 
 * Manages multiple playlists with visual tabs.
 * - Active playlist (green border): Controls playback
 * - Viewed playlist (highlighted): Currently shown in GUI
 * - Left-click: VIEW playlist (edit without affecting playback)
 * - Right-click: Context menu with Activate, Rename, Delete
 */

class PlaylistTabsManager {
    constructor(containerId) {
        this.containerId = containerId;
        this.playlists = [];
        this.activePlaylistId = null;
        this.viewedPlaylistId = null;
        this.contextMenuPlaylistId = null;
        
        // Callbacks
        this.onActivate = null;  // Called when playlist is activated (playback changes)
        this.onView = null;       // Called when playlist is viewed (GUI only)
        this.onCreate = null;     // Called after creating new playlist
        this.onDelete = null;     // Called after deleting playlist
        this.onRename = null;     // Called after renaming playlist
    }
    
    async init() {
        await this.loadPlaylists();
        this.render();
        this.attachEvents();
        this.createContextMenu();
    }
    
    async loadPlaylists() {
        try {
            const response = await fetch('/api/playlists/list');
            const data = await response.json();
            
            if (data.success) {
                this.playlists = data.playlists;
                this.activePlaylistId = data.active_playlist_id;
                this.viewedPlaylistId = data.viewed_playlist_id;
                console.log('Loaded playlists:', this.playlists.length);
            }
        } catch (error) {
            console.error('Failed to load playlists:', error);
        }
    }
    
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        let html = '<div class="playlist-tabs-container">';
        
        // Render tabs
        html += '<div class="playlist-tabs">';
        
        for (const playlist of this.playlists) {
            const isActive = playlist.id === this.activePlaylistId;
            const isViewed = playlist.id === this.viewedPlaylistId;
            
            let classes = 'playlist-tab';
            if (isActive) classes += ' active';
            if (isViewed) classes += ' viewed';
            
            const icon = this.getTypeIcon(playlist.type);
            const sequencerBadge = playlist.sequencer_mode ? '<span class="sequencer-badge">🎵</span>' : '';
            
            html += `
                <div class="${classes}" data-playlist-id="${playlist.id}" title="${this.escapeHtml(playlist.name)}">
                    ${icon}
                    <span class="playlist-name">${this.escapeHtml(playlist.name)}</span>
                    ${sequencerBadge}
                    ${isActive ? '<span class="active-indicator">▶</span>' : ''}
                </div>
            `;
        }
        
        // Add playlist button
        html += `
            <button id="addPlaylistBtn" class="add-playlist-btn" title="Create New Playlist">
                <i class="fas fa-plus"></i>
            </button>
        `;
        
        html += '</div>';
        
        html += '</div>';
        
        container.innerHTML = html;
    }
    
    getTypeIcon(type) {
        const icons = {
            'live': '<i class="fas fa-microphone"></i>',
            'sequence': '<i class="fas fa-list-ol"></i>',
            'standard': '<i class="fas fa-play"></i>'
        };
        return icons[type] || icons.standard;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    attachEvents() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        // Left-click: View/edit playlist (GUI only, no playback change)
        // Right-click: Context menu with "Activate" option (changes playback)
        container.addEventListener('click', (e) => {
            const tab = e.target.closest('.playlist-tab');
            if (tab) {
                const playlistId = tab.dataset.playlistId;
                this.viewPlaylist(playlistId);
            }
        });
        
        container.addEventListener('contextmenu', (e) => {
            const tab = e.target.closest('.playlist-tab');
            if (tab) {
                e.preventDefault();
                const playlistId = tab.dataset.playlistId;
                this.showContextMenu(e, playlistId);
            }
        });
        
        // Add button
        const addBtn = document.getElementById('addPlaylistBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                this.createPlaylist();
            });
        }
        
        // Hide context menu on outside click
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
    }
    
    async viewPlaylist(playlistId) {
        // View/edit playlist in GUI (does NOT change playback)
        try {
            const response = await fetch('/api/playlists/view', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.viewedPlaylistId = playlistId;
                this.render();
                
                // Update GUI to show this playlist's content
                if (this.onView) {
                    this.onView(playlistId, data.viewed_playlist);
                }
            }
        } catch (error) {
            console.error('Failed to view playlist:', error);
        }
    }
    
    async activatePlaylist(playlistId) {
        // Activate playlist (changes playback control)
        try {
            const response = await fetch('/api/playlists/activate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.activePlaylistId = playlistId;
                this.viewedPlaylistId = playlistId;  // Also view it
                this.render();
                
                // Trigger callback (updates ALL player displays)
                if (this.onActivate) {
                    this.onActivate(playlistId, data.active_playlist);
                }
                
                console.log(`Activated playlist: ${data.active_playlist.name}`);
            }
        } catch (error) {
            console.error('Failed to activate playlist:', error);
        }
    }
    
    showContextMenu(event, playlistId) {
        this.contextMenuPlaylistId = playlistId;
        const menu = document.getElementById('playlistContextMenu');
        if (!menu) return;
        
        // Position menu at cursor
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';
        menu.style.display = 'block';
        
        // Enable/disable delete button if it's the active playlist
        const deleteBtn = menu.querySelector('[data-action="delete"]');
        const playlist = this.playlists.find(p => p.id === playlistId);
        const isActive = playlist && playlist.id === this.activePlaylistId;
        const isLastPlaylist = this.playlists.length <= 1;
        
        if (deleteBtn) {
            deleteBtn.disabled = isActive || isLastPlaylist;
            deleteBtn.title = isActive ? 'Cannot delete active playlist' : 
                             isLastPlaylist ? 'Cannot delete last playlist' : '';
        }
    }
    
    hideContextMenu() {
        const menu = document.getElementById('playlistContextMenu');
        if (menu) {
            menu.style.display = 'none';
        }
    }
    
    createContextMenu() {
        // Create context menu if it doesn't exist
        if (document.getElementById('playlistContextMenu')) return;
        
        const menu = document.createElement('div');
        menu.id = 'playlistContextMenu';
        menu.className = 'playlist-context-menu';
        menu.innerHTML = `
            <button data-action="activate">
                <i class="fas fa-play"></i> Activate (Start Playing)
            </button>
            <button data-action="takeover-preview">
                🎬 Live Preview (Takeover Output)
            </button>
            <hr>
            <button data-action="rename">
                <i class="fas fa-edit"></i> Rename
            </button>
            <button data-action="sequencer">
                <i class="fas fa-music"></i> Toggle Sequencer Mode
            </button>
            <hr>
            <button data-action="delete" class="danger">
                <i class="fas fa-trash"></i> Delete
            </button>
        `;
        
        document.body.appendChild(menu);
        
        // Attach handlers
        menu.querySelector('[data-action="activate"]').addEventListener('click', () => {
            if (this.contextMenuPlaylistId) {
                this.activatePlaylist(this.contextMenuPlaylistId);
            }
            this.hideContextMenu();
        });
        
        menu.querySelector('[data-action="takeover-preview"]').addEventListener('click', async () => {
            if (this.contextMenuPlaylistId) {
                // Check if already in takeover mode
                const status = await window.checkTakeoverPreviewStatus();
                if (status) {
                    // Stop current takeover
                    await window.stopTakeoverPreview();
                } else {
                    // Start takeover for this playlist
                    if (this.contextMenuPlaylistId === this.activePlaylistId) {
                        alert('Cannot preview the active playlist. This playlist is already playing.');
                    } else {
                        await window.startTakeoverPreview(this.contextMenuPlaylistId);
                    }
                }
            }
            this.hideContextMenu();
        });
        
        menu.querySelector('[data-action="rename"]').addEventListener('click', () => {
            if (this.contextMenuPlaylistId) {
                this.renamePlaylist(this.contextMenuPlaylistId);
            }
            this.hideContextMenu();
        });
        
        menu.querySelector('[data-action="sequencer"]').addEventListener('click', () => {
            if (this.contextMenuPlaylistId) {
                this.toggleSequencerMode(this.contextMenuPlaylistId);
            }
            this.hideContextMenu();
        });
        
        menu.querySelector('[data-action="delete"]').addEventListener('click', () => {
            if (this.contextMenuPlaylistId) {
                this.deletePlaylist(this.contextMenuPlaylistId);
            }
            this.hideContextMenu();
        });
    }
    
    async createPlaylist() {
        const name = prompt('Enter playlist name:');
        if (!name || name.trim() === '') return;
        
        try {
            const response = await fetch('/api/playlists/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    name: name.trim(),
                    type: 'standard'
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadPlaylists();
                this.render();
                
                // View the new playlist
                this.viewPlaylist(data.playlist.id);
                
                if (this.onCreate) {
                    this.onCreate(data.playlist);
                }
                
                console.log('Created playlist:', data.playlist.name);
            } else {
                alert('Failed to create playlist: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to create playlist:', error);
            alert('Failed to create playlist');
        }
    }
    
    async renamePlaylist(playlistId) {
        const playlist = this.playlists.find(p => p.id === playlistId);
        if (!playlist) return;
        
        const newName = prompt('Enter new name:', playlist.name);
        if (!newName || newName.trim() === '' || newName === playlist.name) return;
        
        try {
            const response = await fetch(`/api/playlists/${playlistId}/rename`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: newName.trim() })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadPlaylists();
                this.render();
                
                if (this.onRename) {
                    this.onRename(playlistId, newName.trim());
                }
                
                console.log('Renamed playlist to:', newName);
            } else {
                alert('Failed to rename playlist: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to rename playlist:', error);
            alert('Failed to rename playlist');
        }
    }
    
    async deletePlaylist(playlistId) {
        const playlist = this.playlists.find(p => p.id === playlistId);
        if (!playlist) return;
        
        // Don't allow deleting active playlist
        if (playlist.id === this.activePlaylistId) {
            alert('Cannot delete the active playlist');
            return;
        }
        
        // Don't allow deleting last playlist
        if (this.playlists.length <= 1) {
            alert('Cannot delete the last playlist');
            return;
        }
        
        if (!confirm(`Delete playlist "${playlist.name}"?`)) return;
        
        try {
            const response = await fetch(`/api/playlists/${playlistId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadPlaylists();
                this.render();
                
                // If we deleted the viewed playlist, view the active one
                if (playlistId === this.viewedPlaylistId) {
                    this.viewPlaylist(this.activePlaylistId);
                }
                
                if (this.onDelete) {
                    this.onDelete(playlistId);
                }
                
                console.log('Deleted playlist:', playlist.name);
            } else {
                alert('Failed to delete playlist: ' + data.error);
            }
        } catch (error) {
            console.error('Failed to delete playlist:', error);
            alert('Failed to delete playlist');
        }
    }
    
    async toggleSequencerMode(playlistId) {
        const playlist = this.playlists.find(p => p.id === playlistId);
        if (!playlist) return;
        
        // Call the global toggleSequencerMode if it exists
        if (typeof window.toggleSequencerMode === 'function') {
            await window.toggleSequencerMode();
            // Reload playlists to reflect sequencer badge
            await this.loadPlaylists();
            this.render();
        } else {
            console.error('toggleSequencerMode function not found');
        }
    }
}

// Export for use in player.html
window.PlaylistTabsManager = PlaylistTabsManager;
