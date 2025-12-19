# Setlist & Multi-Playlist Management - Implementation Guide

## Overview

This document describes the implementation of a **setlist management system** with multiple playlists for the Flux Art-Net system. A setlist acts as a container for multiple playlists, allowing users to organize performances with multiple playlist variations.

## Goals

- **Setlist as superior container**: Setlist contains multiple playlists
- **Multi-playlist support**: Create, manage, and switch between multiple playlists within a setlist
- **Tab-based UI**: Click tabs to switch between playlists
- **No backwards compatibility**: Clean break from single-playlist design
- **Updated snapshot format**: Save/load setlists with all playlists
- **Independent playlist playback**: Each playlist has its own clips, effects, and settings
- **Quick playlist switching**: Instant switching via tabs (no loading delay)

## Architecture Changes

### Current Structure (Single Playlist)

```
Project
├── settings
├── playlist (single)
│   ├── clips[]
│   ├── default_transition
│   └── master_settings
└── effects[]
```

### New Structure (Setlist with Multiple Playlists)

```
Setlist
├── name: "My Performance"
├── created_at
├── modified_at
├── active_playlist_id: "playlist_001"
├── playlists[]
│   ├── Playlist 1
│   │   ├── id: "playlist_001"
│   │   ├── name: "Main Show"
│   │   ├── clips[]
│   │   ├── default_transition
│   │   └── settings
│   ├── Playlist 2
│   │   ├── id: "playlist_002"
│   │   ├── name: "Backup"
│   │   ├── clips[]
│   │   ├── default_transition
│   │   └── settings
│   └── Playlist 3
│       ├── id: "playlist_003"
│       ├── name: "Encore"
│       └── ...
└── global_settings
    ├── artnet_config
    ├── output_settings
    └── effect_defaults
```

## Data Structures

### Setlist Model

**File:** `src/modules/models/setlist.py`

```python
"""
Setlist Data Model
Container for multiple playlists.
"""

import uuid
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class Clip:
    """Individual clip in a playlist."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    file_path: str = ""
    file_type: str = ""  # 'video', 'image', 'generator'
    duration: float = 0.0
    in_point: float = 0.0
    out_point: float = 0.0
    effects: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Playlist:
    """Individual playlist within a setlist."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Playlist"
    clips: List[Clip] = field(default_factory=list)
    default_transition: Dict[str, Any] = field(default_factory=dict)
    loop_mode: str = "none"  # 'none', 'playlist', 'clip'
    random_mode: bool = False
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'clips': [clip.to_dict() for clip in self.clips],
            'default_transition': self.default_transition,
            'loop_mode': self.loop_mode,
            'random_mode': self.random_mode,
            'settings': self.settings,
            'created_at': self.created_at,
            'modified_at': self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Playlist':
        clips = [Clip(**clip_data) for clip_data in data.get('clips', [])]
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'New Playlist'),
            clips=clips,
            default_transition=data.get('default_transition', {}),
            loop_mode=data.get('loop_mode', 'none'),
            random_mode=data.get('random_mode', False),
            settings=data.get('settings', {}),
            created_at=data.get('created_at', time.time()),
            modified_at=data.get('modified_at', time.time())
        )

@dataclass
class Setlist:
    """Setlist containing multiple playlists."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Setlist"
    playlists: List[Playlist] = field(default_factory=list)
    active_playlist_id: Optional[str] = None
    global_settings: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    modified_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """Ensure at least one playlist exists."""
        if not self.playlists:
            default_playlist = Playlist(name="Playlist 1")
            self.playlists.append(default_playlist)
            self.active_playlist_id = default_playlist.id
        
        if self.active_playlist_id is None and self.playlists:
            self.active_playlist_id = self.playlists[0].id
    
    def get_active_playlist(self) -> Optional[Playlist]:
        """Get currently active playlist."""
        for playlist in self.playlists:
            if playlist.id == self.active_playlist_id:
                return playlist
        return None
    
    def get_playlist_by_id(self, playlist_id: str) -> Optional[Playlist]:
        """Get playlist by ID."""
        for playlist in self.playlists:
            if playlist.id == playlist_id:
                return playlist
        return None
    
    def add_playlist(self, name: str = None) -> Playlist:
        """Add new playlist to setlist."""
        if name is None:
            name = f"Playlist {len(self.playlists) + 1}"
        
        playlist = Playlist(name=name)
        self.playlists.append(playlist)
        self.modified_at = time.time()
        
        logger.info(f"Added playlist: {name}")
        return playlist
    
    def remove_playlist(self, playlist_id: str) -> bool:
        """Remove playlist from setlist."""
        if len(self.playlists) <= 1:
            logger.warning("Cannot remove last playlist")
            return False
        
        for i, playlist in enumerate(self.playlists):
            if playlist.id == playlist_id:
                self.playlists.pop(i)
                
                # Switch active playlist if removed
                if self.active_playlist_id == playlist_id:
                    self.active_playlist_id = self.playlists[0].id
                
                self.modified_at = time.time()
                logger.info(f"Removed playlist: {playlist.name}")
                return True
        
        return False
    
    def set_active_playlist(self, playlist_id: str) -> bool:
        """Set active playlist."""
        if self.get_playlist_by_id(playlist_id):
            self.active_playlist_id = playlist_id
            self.modified_at = time.time()
            logger.info(f"Switched to playlist: {playlist_id}")
            return True
        return False
    
    def reorder_playlists(self, playlist_ids: List[str]) -> bool:
        """Reorder playlists by ID list."""
        if len(playlist_ids) != len(self.playlists):
            return False
        
        new_order = []
        for pid in playlist_ids:
            playlist = self.get_playlist_by_id(pid)
            if playlist:
                new_order.append(playlist)
            else:
                return False
        
        self.playlists = new_order
        self.modified_at = time.time()
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert setlist to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'playlists': [playlist.to_dict() for playlist in self.playlists],
            'active_playlist_id': self.active_playlist_id,
            'global_settings': self.global_settings,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'version': '2.0'  # New format version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Setlist':
        """Create setlist from dictionary."""
        playlists = [Playlist.from_dict(p) for p in data.get('playlists', [])]
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'New Setlist'),
            playlists=playlists,
            active_playlist_id=data.get('active_playlist_id'),
            global_settings=data.get('global_settings', {}),
            created_at=data.get('created_at', time.time()),
            modified_at=data.get('modified_at', time.time())
        )
```

## Backend Implementation

### Setlist Manager

**File:** `src/modules/setlist_manager.py`

```python
"""
Setlist Manager
Manages setlist state and operations.
"""

import json
import logging
from pathlib import Path
from typing import Optional
from .models.setlist import Setlist, Playlist, Clip

logger = logging.getLogger(__name__)

class SetlistManager:
    """Manages current setlist and playlist operations."""
    
    def __init__(self):
        self.current_setlist: Optional[Setlist] = None
        self.snapshot_dir = Path("snapshots")
        self.snapshot_dir.mkdir(exist_ok=True)
    
    def new_setlist(self, name: str = "New Setlist") -> Setlist:
        """Create new empty setlist."""
        self.current_setlist = Setlist(name=name)
        logger.info(f"Created new setlist: {name}")
        return self.current_setlist
    
    def load_setlist(self, file_path: str) -> bool:
        """Load setlist from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check version
            version = data.get('version', '1.0')
            if version != '2.0':
                logger.error(f"Incompatible setlist version: {version} (expected 2.0)")
                return False
            
            self.current_setlist = Setlist.from_dict(data)
            logger.info(f"Loaded setlist: {self.current_setlist.name}")
            return True
        
        except Exception as e:
            logger.error(f"Error loading setlist: {e}")
            return False
    
    def save_setlist(self, file_path: str) -> bool:
        """Save current setlist to file."""
        if not self.current_setlist:
            logger.error("No setlist to save")
            return False
        
        try:
            data = self.current_setlist.to_dict()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved setlist: {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving setlist: {e}")
            return False
    
    def get_active_playlist(self) -> Optional[Playlist]:
        """Get currently active playlist."""
        if not self.current_setlist:
            return None
        return self.current_setlist.get_active_playlist()
    
    def switch_playlist(self, playlist_id: str) -> bool:
        """Switch to different playlist."""
        if not self.current_setlist:
            return False
        
        return self.current_setlist.set_active_playlist(playlist_id)
    
    def add_playlist(self, name: str = None) -> Optional[Playlist]:
        """Add new playlist to current setlist."""
        if not self.current_setlist:
            return None
        
        return self.current_setlist.add_playlist(name)
    
    def remove_playlist(self, playlist_id: str) -> bool:
        """Remove playlist from setlist."""
        if not self.current_setlist:
            return False
        
        return self.current_setlist.remove_playlist(playlist_id)
    
    def rename_playlist(self, playlist_id: str, new_name: str) -> bool:
        """Rename a playlist."""
        if not self.current_setlist:
            return False
        
        playlist = self.current_setlist.get_playlist_by_id(playlist_id)
        if playlist:
            playlist.name = new_name
            playlist.modified_at = time.time()
            return True
        return False
    
    def get_setlist_info(self) -> dict:
        """Get current setlist information."""
        if not self.current_setlist:
            return {'error': 'No setlist loaded'}
        
        return {
            'id': self.current_setlist.id,
            'name': self.current_setlist.name,
            'active_playlist_id': self.current_setlist.active_playlist_id,
            'playlists': [
                {
                    'id': p.id,
                    'name': p.name,
                    'clip_count': len(p.clips),
                    'modified_at': p.modified_at
                }
                for p in self.current_setlist.playlists
            ]
        }


# Global instance
_setlist_manager = None

def get_setlist_manager() -> SetlistManager:
    """Get global setlist manager instance."""
    global _setlist_manager
    if _setlist_manager is None:
        _setlist_manager = SetlistManager()
    return _setlist_manager
```

### API Endpoints

**File:** `src/modules/api_setlist.py`

```python
"""
Setlist API
REST endpoints for setlist and playlist management.
"""

from flask import Blueprint, jsonify, request
import logging
from .setlist_manager import get_setlist_manager

logger = logging.getLogger(__name__)

setlist_bp = Blueprint('setlist', __name__)

@setlist_bp.route('/api/setlist/info', methods=['GET'])
def get_setlist_info():
    """Get current setlist information."""
    try:
        manager = get_setlist_manager()
        info = manager.get_setlist_info()
        return jsonify({'success': True, 'setlist': info})
    except Exception as e:
        logger.error(f"Error getting setlist info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/setlist/new', methods=['POST'])
def new_setlist():
    """Create new setlist."""
    try:
        data = request.get_json() or {}
        name = data.get('name', 'New Setlist')
        
        manager = get_setlist_manager()
        setlist = manager.new_setlist(name)
        
        return jsonify({
            'success': True,
            'setlist': {
                'id': setlist.id,
                'name': setlist.name
            }
        })
    except Exception as e:
        logger.error(f"Error creating setlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/setlist/load', methods=['POST'])
def load_setlist():
    """Load setlist from file."""
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'success': False, 'error': 'No file path provided'}), 400
        
        manager = get_setlist_manager()
        success = manager.load_setlist(file_path)
        
        if success:
            return jsonify({'success': True, 'setlist': manager.get_setlist_info()})
        else:
            return jsonify({'success': False, 'error': 'Failed to load setlist'}), 500
    
    except Exception as e:
        logger.error(f"Error loading setlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/setlist/save', methods=['POST'])
def save_setlist():
    """Save current setlist to file."""
    try:
        data = request.get_json() or {}
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'success': False, 'error': 'No file path provided'}), 400
        
        manager = get_setlist_manager()
        success = manager.save_setlist(file_path)
        
        return jsonify({'success': success})
    
    except Exception as e:
        logger.error(f"Error saving setlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/playlist/switch', methods=['POST'])
def switch_playlist():
    """Switch to different playlist."""
    try:
        data = request.get_json() or {}
        playlist_id = data.get('playlist_id')
        
        if not playlist_id:
            return jsonify({'success': False, 'error': 'No playlist ID provided'}), 400
        
        manager = get_setlist_manager()
        success = manager.switch_playlist(playlist_id)
        
        return jsonify({'success': success})
    
    except Exception as e:
        logger.error(f"Error switching playlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/playlist/add', methods=['POST'])
def add_playlist():
    """Add new playlist to setlist."""
    try:
        data = request.get_json() or {}
        name = data.get('name')
        
        manager = get_setlist_manager()
        playlist = manager.add_playlist(name)
        
        if playlist:
            return jsonify({
                'success': True,
                'playlist': {
                    'id': playlist.id,
                    'name': playlist.name
                }
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add playlist'}), 500
    
    except Exception as e:
        logger.error(f"Error adding playlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/playlist/remove', methods=['POST'])
def remove_playlist():
    """Remove playlist from setlist."""
    try:
        data = request.get_json() or {}
        playlist_id = data.get('playlist_id')
        
        if not playlist_id:
            return jsonify({'success': False, 'error': 'No playlist ID provided'}), 400
        
        manager = get_setlist_manager()
        success = manager.remove_playlist(playlist_id)
        
        return jsonify({'success': success})
    
    except Exception as e:
        logger.error(f"Error removing playlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/playlist/rename', methods=['POST'])
def rename_playlist():
    """Rename a playlist."""
    try:
        data = request.get_json() or {}
        playlist_id = data.get('playlist_id')
        new_name = data.get('name')
        
        if not playlist_id or not new_name:
            return jsonify({'success': False, 'error': 'Missing playlist ID or name'}), 400
        
        manager = get_setlist_manager()
        success = manager.rename_playlist(playlist_id, new_name)
        
        return jsonify({'success': success})
    
    except Exception as e:
        logger.error(f"Error renaming playlist: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@setlist_bp.route('/api/playlist/reorder', methods=['POST'])
def reorder_playlists():
    """Reorder playlists in setlist."""
    try:
        data = request.get_json() or {}
        playlist_ids = data.get('playlist_ids', [])
        
        manager = get_setlist_manager()
        if manager.current_setlist:
            success = manager.current_setlist.reorder_playlists(playlist_ids)
            return jsonify({'success': success})
        
        return jsonify({'success': False, 'error': 'No setlist loaded'}), 400
    
    except Exception as e:
        logger.error(f"Error reordering playlists: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def init_setlist_api(app):
    """Initialize setlist API with Flask app."""
    app.register_blueprint(setlist_bp)
    logger.info("📋 Setlist API initialized")
```

## Frontend Implementation

### Playlist Tabs Component

**File:** `frontend/components/playlist-tabs.html`

```html
<template id="playlist-tabs-template">
    <div class="playlist-tabs-container">
        <div class="playlist-tabs" id="playlist-tabs">
            <!-- Tabs populated dynamically -->
        </div>
        <button class="btn-add-playlist" id="btn-add-playlist" title="Add Playlist">
            +
        </button>
    </div>
    
    <!-- Context menu for playlist tabs -->
    <div class="playlist-tab-context-menu" id="playlist-tab-context-menu" style="display: none;">
        <div class="context-menu-item" data-action="rename">
            <span class="context-menu-icon">✏️</span>
            <span>Rename</span>
        </div>
        <div class="context-menu-item" data-action="duplicate">
            <span class="context-menu-icon">📋</span>
            <span>Duplicate</span>
        </div>
        <div class="context-menu-item context-menu-divider"></div>
        <div class="context-menu-item" data-action="remove">
            <span class="context-menu-icon">🗑️</span>
            <span>Remove</span>
        </div>
    </div>
</template>

<script>
class PlaylistTabs {
    constructor() {
        this.playlists = [];
        this.activePlaylistId = null;
        this.contextMenuPlaylistId = null;
        this.onPlaylistChange = null;  // Callback when playlist switches
    }
    
    init(containerId) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('Playlist tabs container not found');
            return;
        }
        
        // Load template
        const template = document.getElementById('playlist-tabs-template');
        const content = template.content.cloneNode(true);
        container.appendChild(content);
        
        // Setup event listeners
        document.getElementById('btn-add-playlist').addEventListener('click', () => {
            this.addPlaylist();
        });
        
        // Context menu
        document.addEventListener('click', () => {
            this.hideContextMenu();
        });
        
        document.getElementById('playlist-tab-context-menu').addEventListener('click', (e) => {
            const item = e.target.closest('.context-menu-item');
            if (item) {
                const action = item.dataset.action;
                this.handleContextMenuAction(action);
            }
        });
        
        // Load initial data
        this.loadSetlistInfo();
    }
    
    async loadSetlistInfo() {
        try {
            const response = await fetch('/api/setlist/info');
            const data = await response.json();
            
            if (data.success && data.setlist) {
                this.playlists = data.setlist.playlists || [];
                this.activePlaylistId = data.setlist.active_playlist_id;
                this.render();
            }
        } catch (e) {
            console.error('Error loading setlist info:', e);
        }
    }
    
    render() {
        const tabsContainer = document.getElementById('playlist-tabs');
        if (!tabsContainer) return;
        
        // Clear existing tabs
        tabsContainer.innerHTML = '';
        
        // Render tabs
        this.playlists.forEach(playlist => {
            const tab = document.createElement('div');
            tab.className = 'playlist-tab';
            tab.dataset.playlistId = playlist.id;
            
            if (playlist.id === this.activePlaylistId) {
                tab.classList.add('active');
            }
            
            const nameSpan = document.createElement('span');
            nameSpan.className = 'playlist-tab-name';
            nameSpan.textContent = playlist.name;
            
            const clipCount = document.createElement('span');
            clipCount.className = 'playlist-tab-count';
            clipCount.textContent = playlist.clip_count || 0;
            
            tab.appendChild(nameSpan);
            tab.appendChild(clipCount);
            
            // Click to switch
            tab.addEventListener('click', () => {
                this.switchPlaylist(playlist.id);
            });
            
            // Right-click for context menu
            tab.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                this.showContextMenu(e.clientX, e.clientY, playlist.id);
            });
            
            tabsContainer.appendChild(tab);
        });
    }
    
    async switchPlaylist(playlistId) {
        if (playlistId === this.activePlaylistId) return;
        
        try {
            const response = await fetch('/api/playlist/switch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.activePlaylistId = playlistId;
                this.render();
                
                // Trigger callback
                if (this.onPlaylistChange) {
                    this.onPlaylistChange(playlistId);
                }
                
                console.log(`Switched to playlist: ${playlistId}`);
            }
        } catch (e) {
            console.error('Error switching playlist:', e);
        }
    }
    
    async addPlaylist() {
        const name = prompt('Playlist name:', `Playlist ${this.playlists.length + 1}`);
        if (!name) return;
        
        try {
            const response = await fetch('/api/playlist/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadSetlistInfo();
                console.log('Added playlist:', name);
            }
        } catch (e) {
            console.error('Error adding playlist:', e);
        }
    }
    
    showContextMenu(x, y, playlistId) {
        this.contextMenuPlaylistId = playlistId;
        const menu = document.getElementById('playlist-tab-context-menu');
        
        menu.style.display = 'block';
        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;
    }
    
    hideContextMenu() {
        const menu = document.getElementById('playlist-tab-context-menu');
        menu.style.display = 'none';
    }
    
    async handleContextMenuAction(action) {
        this.hideContextMenu();
        
        const playlistId = this.contextMenuPlaylistId;
        if (!playlistId) return;
        
        switch (action) {
            case 'rename':
                await this.renamePlaylist(playlistId);
                break;
            case 'duplicate':
                await this.duplicatePlaylist(playlistId);
                break;
            case 'remove':
                await this.removePlaylist(playlistId);
                break;
        }
    }
    
    async renamePlaylist(playlistId) {
        const playlist = this.playlists.find(p => p.id === playlistId);
        if (!playlist) return;
        
        const newName = prompt('Rename playlist:', playlist.name);
        if (!newName) return;
        
        try {
            const response = await fetch('/api/playlist/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId, name: newName })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadSetlistInfo();
            }
        } catch (e) {
            console.error('Error renaming playlist:', e);
        }
    }
    
    async duplicatePlaylist(playlistId) {
        // TODO: Implement duplicate functionality
        console.log('Duplicate playlist:', playlistId);
    }
    
    async removePlaylist(playlistId) {
        const playlist = this.playlists.find(p => p.id === playlistId);
        if (!playlist) return;
        
        if (!confirm(`Remove playlist "${playlist.name}"?`)) return;
        
        try {
            const response = await fetch('/api/playlist/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ playlist_id: playlistId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                await this.loadSetlistInfo();
            } else {
                alert('Cannot remove last playlist');
            }
        } catch (e) {
            console.error('Error removing playlist:', e);
        }
    }
}

// Global instance
window.playlistTabs = new PlaylistTabs();
</script>
```

### Playlist Tabs Styles

**File:** `frontend/css/playlist-tabs.css`

```css
.playlist-tabs-container {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(20, 20, 30, 0.8);
    padding: 8px 12px;
    border-radius: 8px;
    margin-bottom: 15px;
}

.playlist-tabs {
    display: flex;
    gap: 4px;
    flex: 1;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: thin;
}

.playlist-tabs::-webkit-scrollbar {
    height: 4px;
}

.playlist-tabs::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
}

.playlist-tabs::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 2px;
}

.playlist-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
    user-select: none;
}

.playlist-tab:hover {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.2);
}

.playlist-tab.active {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-color: rgba(255, 255, 255, 0.3);
    box-shadow: 0 2px 8px rgba(102, 126, 234, 0.4);
}

.playlist-tab-name {
    font-size: 13px;
    font-weight: 500;
    color: #e0e0e0;
}

.playlist-tab.active .playlist-tab-name {
    color: #fff;
    font-weight: 600;
}

.playlist-tab-count {
    font-size: 11px;
    color: #888;
    background: rgba(0, 0, 0, 0.3);
    padding: 2px 6px;
    border-radius: 10px;
}

.playlist-tab.active .playlist-tab-count {
    color: #fff;
    background: rgba(255, 255, 255, 0.2);
}

.btn-add-playlist {
    width: 32px;
    height: 32px;
    border-radius: 6px;
    border: 1px dashed rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.05);
    color: #888;
    font-size: 18px;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
}

.btn-add-playlist:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.5);
    color: #fff;
}

/* Context menu */
.playlist-tab-context-menu {
    position: fixed;
    background: rgba(30, 30, 40, 0.95);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    padding: 4px;
    z-index: 10000;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
    min-width: 150px;
}

.context-menu-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 4px;
    font-size: 13px;
    color: #e0e0e0;
    transition: background 0.2s;
}

.context-menu-item:hover {
    background: rgba(255, 255, 255, 0.1);
}

.context-menu-icon {
    font-size: 14px;
    width: 18px;
    text-align: center;
}

.context-menu-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.1);
    margin: 4px 0;
    padding: 0;
}

.context-menu-divider:hover {
    background: rgba(255, 255, 255, 0.1);
    cursor: default;
}
```

### Integration into Player UI

**File:** `frontend/player.html`

Add to `<head>`:

```html
<link rel="stylesheet" href="css/playlist-tabs.css">
```

Add playlist tabs above existing playlist section:

```html
<!-- Playlist Tabs -->
<div id="playlist-tabs-container"></div>
<script src="components/playlist-tabs.html"></script>

<!-- Existing playlist display -->
<div id="playlist-clips">
    <!-- Clips displayed here -->
</div>

<script>
    document.addEventListener('DOMContentLoaded', () => {
        // Initialize playlist tabs
        window.playlistTabs.init('playlist-tabs-container');
        
        // Reload clips when playlist switches
        window.playlistTabs.onPlaylistChange = (playlistId) => {
            console.log('Playlist changed:', playlistId);
            loadPlaylistClips();  // Your existing function
        };
    });
</script>
```

## Snapshot Format Changes

### New Snapshot Structure

**File:** `snapshots/example_setlist_v2.json`

```json
{
  "version": "2.0",
  "id": "setlist_001",
  "name": "Live Performance 2025",
  "created_at": 1702900000.0,
  "modified_at": 1702900000.0,
  "active_playlist_id": "playlist_001",
  "playlists": [
    {
      "id": "playlist_001",
      "name": "Main Show",
      "clips": [
        {
          "id": "clip_001",
          "name": "Intro",
          "file_path": "video/intro.mp4",
          "file_type": "video",
          "duration": 10.0,
          "in_point": 0.0,
          "out_point": 10.0,
          "effects": [],
          "metadata": {}
        }
      ],
      "default_transition": {
        "type": "fade",
        "duration": 1.0
      },
      "loop_mode": "none",
      "random_mode": false,
      "settings": {},
      "created_at": 1702900000.0,
      "modified_at": 1702900000.0
    },
    {
      "id": "playlist_002",
      "name": "Backup",
      "clips": [],
      "default_transition": {
        "type": "cut",
        "duration": 0.0
      },
      "loop_mode": "playlist",
      "random_mode": false,
      "settings": {},
      "created_at": 1702900000.0,
      "modified_at": 1702900000.0
    }
  ],
  "global_settings": {
    "artnet_config": {
      "universe": 0,
      "subnet": 0
    },
    "output_settings": {
      "resolution": "1920x1080",
      "fps": 30
    }
  }
}
```

### Snapshot Loading/Saving

Update existing snapshot functions to use new format:

**File:** `src/modules/snapshot_manager.py`

```python
"""
Snapshot Manager
Handles loading and saving setlist snapshots.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from .setlist_manager import get_setlist_manager

logger = logging.getLogger(__name__)

def save_snapshot(name: str = None) -> bool:
    """Save current setlist as snapshot."""
    try:
        manager = get_setlist_manager()
        
        if not manager.current_setlist:
            logger.error("No setlist to save")
            return False
        
        # Generate filename
        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"snapshot_{timestamp}"
        
        file_path = Path("snapshots") / f"{name}.json"
        
        # Save using setlist manager
        return manager.save_setlist(str(file_path))
    
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        return False

def load_snapshot(file_path: str) -> bool:
    """Load snapshot file."""
    try:
        manager = get_setlist_manager()
        return manager.load_setlist(file_path)
    
    except Exception as e:
        logger.error(f"Error loading snapshot: {e}")
        return False

def list_snapshots() -> list:
    """List all available snapshots."""
    try:
        snapshot_dir = Path("snapshots")
        if not snapshot_dir.exists():
            return []
        
        snapshots = []
        for file in snapshot_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                
                snapshots.append({
                    'file_path': str(file),
                    'name': data.get('name', file.stem),
                    'version': data.get('version', '1.0'),
                    'modified_at': data.get('modified_at', 0),
                    'playlist_count': len(data.get('playlists', []))
                })
            except Exception as e:
                logger.warning(f"Error reading snapshot {file}: {e}")
        
        # Sort by modified time (newest first)
        snapshots.sort(key=lambda x: x['modified_at'], reverse=True)
        return snapshots
    
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        return []
```

## Migration Notes

**⚠️ Breaking Change: No backwards compatibility**

- Old snapshots (version 1.0) will **not load** automatically
- Users must **manually convert** old projects or start fresh
- Version check prevents accidental loading of old format

### Manual Migration (Optional)

If you want to provide manual migration tool:

**File:** `scripts/migrate_v1_to_v2.py`

```python
"""
Migration script: Convert v1.0 projects to v2.0 setlists.
Usage: python scripts/migrate_v1_to_v2.py old_project.json new_setlist.json
"""

import json
import sys
from pathlib import Path

def migrate(old_file, new_file):
    with open(old_file, 'r') as f:
        old_data = json.load(f)
    
    # Create new setlist structure
    new_data = {
        'version': '2.0',
        'id': 'migrated_001',
        'name': old_data.get('name', 'Migrated Setlist'),
        'active_playlist_id': 'playlist_001',
        'playlists': [
            {
                'id': 'playlist_001',
                'name': 'Main Playlist',
                'clips': old_data.get('clips', []),
                'default_transition': old_data.get('default_transition', {}),
                'loop_mode': 'none',
                'random_mode': False,
                'settings': {},
                'created_at': 0,
                'modified_at': 0
            }
        ],
        'global_settings': old_data.get('settings', {}),
        'created_at': 0,
        'modified_at': 0
    }
    
    with open(new_file, 'w') as f:
        json.dump(new_data, f, indent=2)
    
    print(f"✅ Migrated: {old_file} -> {new_file}")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python migrate_v1_to_v2.py <old_file> <new_file>")
        sys.exit(1)
    
    migrate(sys.argv[1], sys.argv[2])
```

## Usage

### Creating Setlist

1. Start application → automatically creates default setlist with 1 playlist
2. Or: File → New Setlist → enter name

### Adding Playlists

1. Click **[+]** button next to tabs
2. Enter playlist name
3. New playlist becomes active

### Switching Playlists

1. Click on any playlist tab
2. Active playlist highlights with gradient background
3. Clip list updates instantly

### Managing Playlists

1. **Right-click** on playlist tab → context menu
2. **Rename**: Change playlist name
3. **Duplicate**: Copy playlist with all clips
4. **Remove**: Delete playlist (minimum 1 must remain)

### Saving/Loading

1. File → Save Setlist → saves entire setlist with all playlists
2. File → Load Setlist → loads setlist and all playlists
3. Snapshots directory: `snapshots/*.json`

## Integration with Player

### Update Player to Use Active Playlist

**File:** `src/modules/player/video_player.py`

```python
from ..setlist_manager import get_setlist_manager

class VideoPlayer:
    def __init__(self):
        # ... existing code ...
        self.setlist_manager = get_setlist_manager()
    
    def get_current_clips(self):
        """Get clips from active playlist."""
        playlist = self.setlist_manager.get_active_playlist()
        if playlist:
            return playlist.clips
        return []
    
    def play_next_clip(self):
        """Play next clip from active playlist."""
        clips = self.get_current_clips()
        # ... existing playback logic ...
```

## Testing Checklist

- [ ] Create new setlist with default playlist
- [ ] Add multiple playlists (3-5)
- [ ] Switch between playlists via tabs
- [ ] Rename playlist
- [ ] Remove playlist (verify minimum 1 remains)
- [ ] Add clips to different playlists
- [ ] Verify clips don't mix between playlists
- [ ] Save setlist to file
- [ ] Load setlist from file
- [ ] Verify active playlist restores correctly
- [ ] Test tab scrolling with many playlists (10+)
- [ ] Test context menu on all playlists
- [ ] Verify playback uses active playlist clips

## Performance Considerations

### Memory Usage

- Each playlist holds separate clip list
- Minimal overhead: ~1-2 KB per playlist
- Typical setlist (5 playlists): ~5-10 KB

### Switching Speed

- No loading delay (in-memory switching)
- UI updates: <50ms
- Instant tab highlight change

### File Size

- Snapshot size grows with playlists
- Typical setlist (5 playlists, 20 clips each): ~50-100 KB
- Compression optional for large setlists

## Future Enhancements

1. **Playlist Groups/Folders**
   - Organize playlists into folders
   - Collapsible groups in tab bar

2. **Playlist Templates**
   - Save playlist as template
   - Quick create from template

3. **Cross-Playlist Copy**
   - Drag clips between playlists
   - Copy effects across playlists

4. **Playlist Sync**
   - Link playlists for simultaneous editing
   - Master/slave playlist relationships

5. **Playlist History**
   - Undo/redo per playlist
   - Version history for each playlist

6. **Search Across Playlists**
   - Find clips in all playlists
   - Filter by playlist

## References

- `src/modules/models/setlist.py` - Data models
- `src/modules/setlist_manager.py` - Setlist management
- `src/modules/api_setlist.py` - API endpoints
- `frontend/components/playlist-tabs.html` - Tab UI component
- `frontend/css/playlist-tabs.css` - Tab styling
- `snapshots/*.json` - Setlist files
