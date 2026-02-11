/**
 * Session Manager
 * Unified module for session state management accessible from all pages.
 * Handles: Save, Load, Upload, Download, Snapshot creation and restoration.
 */

const SessionManager = (function() {
    const API_BASE = '';
    
    // Modal instance (initialized on first use)
    let modal = null;
    
    /**
     * Initialize or get modal instance
     */
    function getModal() {
        // Try to create modal if not exists and ModalManager is available
        if (!modal && typeof ModalManager !== 'undefined') {
            try {
                modal = ModalManager.create({
                    id: 'session-modal',
                    title: 'Session Management',
                    size: 'lg'
                });
                console.log('✅ Modal instance created');
            } catch (error) {
                console.error('❌ Failed to create modal:', error);
                return null;
            }
        }
        
        // Log warning if still not available
        if (!modal) {
            console.warn('⚠️ ModalManager is not defined yet. Available:', typeof ModalManager);
        }
        
        return modal;
    }
    
    /**
     * Show toast notification (fallback to alert if toast not available)
     */
    function showToast(message, type = 'info') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
            if (type === 'error') {
                alert(message);
            }
        }
    }
    
    /**
     * Save current session with custom name
     */
    async function saveSession() {
        try {
            const modalInstance = getModal();
            if (!modalInstance) {
                console.error('❌ ModalManager not available. Check console for details.');
                showToast('Modal-Komponente nicht verfügbar. Bitte Konsole prüfen.', 'error');
                return;
            }
            
            // Show modal with input form
            modalInstance.show();
            modalInstance.setContent(`
                <div class="mb-3">
                    <label for="sessionName" class="form-label">Session Name</label>
                    <input type="text" class="form-control" id="sessionName" placeholder="z.B. Meine Show" autofocus>
                    <small class="text-muted">Ein Timestamp wird automatisch hinzugefügt</small>
                </div>
                <div class="d-flex gap-2 justify-content-end">
                    <button class="btn btn-secondary" onclick="SessionManager.closeModal()">Abbrechen</button>
                    <button class="btn btn-primary" onclick="SessionManager.confirmSaveSession()">💾 Speichern</button>
                </div>
            `);
            
            // Add Enter key handler
            setTimeout(() => {
                const input = document.getElementById('sessionName');
                if (input) {
                    input.focus();
                    input.addEventListener('keypress', (e) => {
                        if (e.key === 'Enter') {
                            confirmSaveSession();
                        }
                    });
                }
            }, 100);
            
        } catch (error) {
            console.error('❌ Error showing save dialog:', error);
            showToast('Error showing save dialog', 'error');
        }
    }
    
    /**
     * Confirm and execute save with entered name
     */
    async function confirmSaveSession() {
        const input = document.getElementById('sessionName');
        const name = input ? input.value.trim() : '';
        
        if (!name) {
            showToast('Bitte geben Sie einen Namen ein', 'error');
            input?.focus();
            return;
        }
        
        closeModal();
        
        try {
            const response = await fetch(`${API_BASE}/api/session/save`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`💾 Session gespeichert: ${data.filename}`, 'success');
            } else {
                showToast(`Fehler beim Speichern: ${data.error}`, 'error');
            }
            
        } catch (error) {
            console.error('❌ Error saving session:', error);
            showToast('Fehler beim Speichern der Session', 'error');
        }
    }
    
    /**
     * Download current session state as JSON file
     */
    async function downloadSession() {
        try {
            const response = await fetch(`${API_BASE}/api/session/download`);
            
            if (!response.ok) {
                const data = await response.json();
                throw new Error(data.error || 'Download failed');
            }
            
            // Get filename from Content-Disposition header or generate
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = 'session_state.json';
            if (contentDisposition) {
                const match = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
                if (match && match[1]) {
                    filename = match[1].replace(/['"]/g, '');
                }
            }
            
            // Download file
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showToast(`📥 Session downloaded: ${filename}`, 'success');
            
        } catch (error) {
            console.error('❌ Error downloading session:', error);
            showToast(`Error downloading session: ${error.message}`, 'error');
        }
    }
    
    /**
     * Create snapshot of current session
     */
    async function createSnapshot() {
        try {
            const response = await fetch(`${API_BASE}/api/session/snapshot`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`📸 Snapshot created: ${data.filename}`, 'success');
                return data;
            } else {
                showToast(`Failed to create snapshot: ${data.error}`, 'error');
                return null;
            }
            
        } catch (error) {
            console.error('❌ Error creating snapshot:', error);
            showToast('Error creating snapshot', 'error');
            return null;
        }
    }
    
    /**
     * Load list of available saved sessions
     */
    async function listSessions() {
        try {
            const response = await fetch(`${API_BASE}/api/session/list`);
            const data = await response.json();
            
            if (data.success) {
                return data.sessions || [];
            } else {
                console.error('Failed to list sessions:', data.error);
                return [];
            }
            
        } catch (error) {
            console.error('❌ Error listing sessions:', error);
            return [];
        }
    }
    
    /**
     * Load saved session by filename
     */
    async function restoreSession(filename) {
        try {
            const response = await fetch(`${API_BASE}/api/session/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('✅ Session wiederhergestellt! Seite wird neu geladen...', 'success');
                
                // Reload page after short delay with restore flag
                if (data.requires_reload) {
                    setTimeout(() => {
                        // Add restore timestamp to URL to force cache clear
                        const url = new URL(window.location.href);
                        url.searchParams.set('restored', data.restore_timestamp || Date.now());
                        window.location.href = url.toString();
                    }, 1000);
                }
                
                return true;
            } else {
                showToast(`Fehler beim Wiederherstellen: ${data.error}`, 'error');
                return false;
            }
            
        } catch (error) {
            console.error('❌ Error restoring session:', error);
            showToast('Fehler beim Wiederherstellen der Session', 'error');
            return false;
        }
    }
    
    /**
     * Load list of available snapshots
     */
    async function listSnapshots() {
        try {
            const response = await fetch(`${API_BASE}/api/session/snapshots`);
            const data = await response.json();
            
            if (data.success) {
                return data.snapshots || [];
            } else {
                console.error('Failed to list snapshots:', data.error);
                return [];
            }
            
        } catch (error) {
            console.error('❌ Error listing snapshots:', error);
            return [];
        }
    }
    
    /**
     * Delete saved session by filename
     */
    async function deleteSession(filename) {
        try {
            const response = await fetch(`${API_BASE}/api/session/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`Session "${filename}" gelöscht`, 'success');
                return true;
            } else {
                showToast(`Fehler beim Löschen: ${data.error}`, 'error');
                return false;
            }
            
        } catch (error) {
            console.error('❌ Error deleting session:', error);
            showToast('Fehler beim Löschen der Session', 'error');
            return false;
        }
    }
    
    /**
     * Restore snapshot by filename
     */
    async function restoreSnapshot(filename) {
        try {
            const response = await fetch(`${API_BASE}/api/session/snapshot/restore`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast('✅ Snapshot restored! Reloading...', 'success');
                
                // Reload page after short delay with restore flag
                if (data.requires_reload) {
                    setTimeout(() => {
                        // Add restore timestamp to URL to force cache clear
                        const url = new URL(window.location.href);
                        url.searchParams.set('restored', data.restore_timestamp || Date.now());
                        window.location.href = url.toString();
                    }, 1000);
                }
                
                return true;
            } else {
                showToast(`Failed to restore: ${data.error}`, 'error');
                return false;
            }
            
        } catch (error) {
            console.error('❌ Error restoring snapshot:', error);
            showToast('Error restoring snapshot', 'error');
            return false;
        }
    }
    
    /**
     * Delete snapshot by filename
     */
    async function deleteSnapshot(filename) {
        try {
            const response = await fetch(`${API_BASE}/api/session/snapshot/delete`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            });
            
            const data = await response.json();
            
            if (data.success) {
                showToast(`Snapshot "${filename}" gelöscht`, 'success');
                return true;
            } else {
                showToast(`Fehler beim Löschen: ${data.error}`, 'error');
                return false;
            }
            
        } catch (error) {
            console.error('❌ Error deleting snapshot:', error);
            showToast('Fehler beim Löschen des Snapshots', 'error');
            return false;
        }
    }
    
    /**
     * Show modal with sessions and snapshots list for loading
     */
    async function showLoadModal() {
        try {
            const modalInstance = getModal();
            if (!modalInstance) {
                console.error('❌ ModalManager not available. Check console for details.');
                showToast('Modal-Komponente nicht verfügbar. Bitte Konsole prüfen.', 'error');
                return;
            }
            
            // Show modal with loading state
            modalInstance.show();
            modalInstance.setContent('<div class="text-center"><div class="spinner-border" role="status"></div><p class="mt-2">Loading...</p></div>');
            
            // Load both sessions and snapshots
            const [sessions, snapshots] = await Promise.all([
                listSessions(),
                listSnapshots()
            ]);
            
            if (sessions.length === 0 && snapshots.length === 0) {
                modalInstance.setContent(`
                    <div class="text-center py-4">
                        <div style="font-size: 48px; margin-bottom: 16px;">💾</div>
                        <p class="mb-2">Keine gespeicherten Sessions gefunden</p>
                        <p class="text-muted small">Speichern Sie eine Session, um sie später wiederherzustellen</p>
                    </div>
                `);
                return;
            }
            
            let html = '';
            
            // Saved Sessions Section
            if (sessions.length > 0) {
                html += '<h6 class="mb-3">💾 Gespeicherte Sessions</h6>';
                html += '<div class="list-group mb-4">';
                
                sessions.forEach((session) => {
                    const date = new Date(session.created).toLocaleDateString('de-DE', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                    
                    const videoCount = session.video_count || 0;
                    const artnetCount = session.artnet_count || 0;
                    const sizeKB = (session.size / 1024).toFixed(1);
                    
                    // Extract display name (remove timestamp)
                    let displayName = session.filename.replace('.json', '');
                    const timestampMatch = displayName.match(/_(\d{8}_\d{6})$/);
                    if (timestampMatch) {
                        displayName = displayName.replace(timestampMatch[0], '');
                    }
                    
                    html += `
                        <div class="list-group-item" style="background: var(--bg-secondary); border-color: var(--border-color); margin-bottom: 8px; border-radius: 6px;">
                            <div class="d-flex align-items-center gap-2">
                                <button type="button" 
                                        class="flex-grow-1 btn btn-outline-success text-start p-3" 
                                        onclick="SessionManager.loadSession('${session.filename}', 'session')">
                                    <div class="d-flex w-100 justify-content-between align-items-start">
                                        <div>
                                            <h6 class="mb-1">💾 ${displayName}</h6>
                                            <small class="text-muted">${date}</small>
                                        </div>
                                    </div>
                                    <div class="mt-2">
                                        <span class="badge bg-primary">Video: ${videoCount}</span>
                                        <span class="badge bg-info">Art-Net: ${artnetCount}</span>
                                        <span class="badge bg-secondary">${sizeKB} KB</span>
                                    </div>
                                </button>
                                <button type="button" 
                                        class="btn btn-danger" 
                                        onclick="SessionManager.deleteWithConfirm('${session.filename}', 'session', event)"
                                        title="Session löschen"
                                        style="min-width: 48px;">
                                    🗑️
                                </button>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
            }
            
            // Snapshots Section
            if (snapshots.length > 0) {
                html += '<h6 class="mb-3">📸 Snapshots</h6>';
                html += '<div class="list-group">';
                
                snapshots.forEach((snapshot) => {
                    const date = new Date(snapshot.created).toLocaleDateString('de-DE', {
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit'
                    });
                    
                    const videoCount = snapshot.video_count || 0;
                    const artnetCount = snapshot.artnet_count || 0;
                    const sizeKB = (snapshot.size / 1024).toFixed(1);
                    
                    html += `
                        <div class="list-group-item" style="background: var(--bg-secondary); border-color: var(--border-color); margin-bottom: 8px; border-radius: 6px;">
                            <div class="d-flex align-items-center gap-2">
                                <button type="button" 
                                        class="flex-grow-1 btn btn-outline-primary text-start p-3" 
                                        onclick="SessionManager.loadSession('${snapshot.filename}', 'snapshot')">
                                    <div class="d-flex w-100 justify-content-between align-items-start">
                                        <div>
                                            <h6 class="mb-1">📸 ${snapshot.filename}</h6>
                                            <small class="text-muted">${date}</small>
                                        </div>
                                    </div>
                                    <div class="mt-2">
                                        <span class="badge bg-primary">Video: ${videoCount}</span>
                                        <span class="badge bg-info">Art-Net: ${artnetCount}</span>
                                        <span class="badge bg-secondary">${sizeKB} KB</span>
                                    </div>
                                </button>
                                <button type="button" 
                                        class="btn btn-danger" 
                                        onclick="SessionManager.deleteWithConfirm('${snapshot.filename}', 'snapshot', event)"
                                        title="Snapshot löschen"
                                        style="min-width: 48px;">
                                    🗑️
                                </button>
                            </div>
                        </div>
                    `;
                });
                
                html += '</div>';
            }
            
            modalInstance.setContent(html);
            
        } catch (error) {
            console.error('❌ Error showing load modal:', error);
            showToast('Error loading list', 'error');
        }
    }
    
    /**
     * Load session or snapshot (called from modal)
     */
    async function loadSession(filename, type) {
        // Confirm restore
        const typeName = type === 'session' ? 'Session' : 'Snapshot';
        if (!confirm(`${typeName} "${filename}" laden?\n\nDies wird die aktuelle Session überschreiben und die Seite neu laden.`)) {
            return;
        }
        
        // Close modal
        closeModal();
        
        // Restore based on type
        if (type === 'session') {
            await restoreSession(filename);
        } else {
            await restoreSnapshot(filename);
        }
    }
    
    /**
     * Delete session or snapshot with confirmation (called from modal)
     */
    async function deleteWithConfirm(filename, type, event) {
        if (event) {
            event.stopPropagation();
        }
        
        const button = event?.currentTarget;
        if (!button) return;
        
        const originalText = button.innerHTML;
        const originalClasses = button.className;
        
        // First click: Confirm
        button.innerHTML = '✓ Confirm';
        button.classList.remove('btn-danger');
        button.classList.add('btn-warning');
        button.disabled = true;
        
        // Reset after 3 seconds
        const resetTimer = setTimeout(() => {
            button.innerHTML = originalText;
            button.className = originalClasses;
            button.disabled = false;
        }, 3000);
        
        // Enable button for second click after short delay
        setTimeout(() => {
            button.disabled = false;
            button.onclick = async (e) => {
                e.stopPropagation();
                clearTimeout(resetTimer);
                
                let success = false;
                if (type === 'session') {
                    success = await deleteSession(filename);
                } else {
                    success = await deleteSnapshot(filename);
                }
                
                if (success) {
                    // Refresh modal content
                    await showLoadModal();
                } else {
                    // Reset button on error
                    button.innerHTML = originalText;
                    button.className = originalClasses;
                }
            };
        }, 200);
    }
    
    /**
     * Close modal
     */
    function closeModal() {
        if (modal) {
            modal.hide();
        }
    }
    
    /**
     * Check if page was reloaded after restore and force refresh playlists
     */
    function checkRestoreAndRefresh() {
        const urlParams = new URLSearchParams(window.location.search);
        const restored = urlParams.get('restored');
        
        if (restored) {
            console.log('🔄 Page loaded after session restore - forcing playlist refresh');
            
            // Remove the restored parameter from URL
            urlParams.delete('restored');
            const newUrl = window.location.pathname + (urlParams.toString() ? '?' + urlParams.toString() : '');
            window.history.replaceState({}, '', newUrl);
            
            // Wait for components to be ready before forcing refresh
            const waitForComponents = () => {
                let attempts = 0;
                const maxAttempts = 20; // 2 seconds max wait
                
                const checkInterval = setInterval(() => {
                    attempts++;
                    
                    // Check if playlistTabs is ready
                    if (window.playlistTabs && typeof window.playlistTabs.loadPlaylists === 'function') {
                        clearInterval(checkInterval);
                        console.log('🔄 Forcing playlist tabs refresh...');
                        
                        window.playlistTabs.loadPlaylists().then(() => {
                            window.playlistTabs.render();
                            console.log('✅ Playlist tabs refreshed after restore');
                        }).catch(err => {
                            console.error('❌ Failed to refresh playlists:', err);
                        });
                        
                        // Also reload session state
                        if (window.sessionStateManager && typeof window.sessionStateManager.reload === 'function') {
                            console.log('🔄 Reloading session state...');
                            window.sessionStateManager.reload();
                        }
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        console.warn('⚠️ Playlist tabs not ready after ' + (maxAttempts * 100) + 'ms');
                    }
                }, 100);
            };
            
            // Start waiting after a short delay to let initial page load complete
            setTimeout(waitForComponents, 300);
        }
    }
    
    // Run on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkRestoreAndRefresh);
    } else {
        checkRestoreAndRefresh();
    }
    
    // Public API
    return {
        saveSession,
        confirmSaveSession,
        downloadSession,
        createSnapshot,
        listSessions,
        listSnapshots,
        restoreSession,
        restoreSnapshot,
        deleteSession,
        deleteSnapshot,
        showLoadModal,
        loadSession,
        deleteWithConfirm,
        closeModal
    };
})();

// Make available globally
window.SessionManager = SessionManager;