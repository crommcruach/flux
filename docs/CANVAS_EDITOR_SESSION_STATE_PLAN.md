# 🎨 Canvas Editor - Session State Integration Plan

**Date:** 2026-02-05  
**Status:** 🚧 In Progress

---

## 📋 Overview

Rework the canvas editor (`frontend/editor.html` + `frontend/js/editor.js`) to:

1. **Auto-save all editor data to backend session state** (similar to output-settings.html)
2. **Auto-restore on page reload** (like player settings)
3. **Replace "Canvas Size" with "ArtNet Resolution"** (input source resolution with proper scaling)
4. **Remove manual save/load** (deprecated server-based project system)

---

## 🎯 Requirements

### 1. Session State Auto-Save

**All editor data should be automatically saved to backend:**

- ✅ Project name → `session_state.editor.projectName`
- ✅ Canvas shapes (all properties) → `session_state.editor.shapes[]`
- ✅ Canvas dimensions → `session_state.editor.canvas`
- ✅ Background image (base64) → `session_state.editor.backgroundImage`
- ✅ Editor settings → `session_state.editor.settings`
  - Snap to grid
  - Snap to objects
  - Grid size
  - Allow out of bounds
  - Show connection lines
  - Show grid

**Save triggers:**
- ✅ Add/delete/modify shape
- ✅ Move/resize/rotate shape
- ✅ Change project name
- ✅ Change canvas size
- ✅ Upload background image
- ✅ Toggle settings

**Debouncing:** 1 second delay after last change

### 2. Auto-Restore on Page Load

**On editor.html load:**

```javascript
1. Frontend: loadFromSessionState()
2. Backend:  GET /api/session/state
3. Backend:  Returns state.editor object
4. Frontend: Restore shapes, canvas, settings, project name
5. Frontend: Render canvas
```

### 3. ArtNet Resolution Input

**Replace Canvas Size dropdown with ArtNet Resolution:**

- Remove: `<select id="canvasSize">` dropdown
- Add: `<input id="artnetWidth">` and `<input id="artnetHeight">`
- Label: "ArtNet Resolution" instead of "Canvas"
- Default: 1920×1080
- Canvas internally scales to fit window
- Shapes are saved in ArtNet coordinate space
- Export uses ArtNet resolution for pixel calculations

### 4. Remove Manual Save/Load

- ✅ Comment out "Projekt" dropdown (DONE)
- ✅ Add auto-save status badge (DONE)
- Remove: `saveProject()` function (keep for export only)
- Remove: `saveProjectToServer()` function
- Remove: `loadProjectFromServer()` function
- Remove: `showProjectManager()` function

---

## 🏗️ Implementation Steps

### Phase 1: Backend API Endpoint (30 min)

#### Create `/api/editor/state` endpoints

**File:** `src/modules/api_editor.py` (NEW)

```python
from flask import jsonify, request
import logging

logger = logging.getLogger(__name__)

def register_editor_routes(app, player_manager):
    """Register canvas editor session state API endpoints"""
    
    @app.route('/api/editor/state', methods=['GET'])
    def get_editor_state():
        """Get editor state from session"""
        try:
            session_state = player_manager.session_state.get_state()
            editor_state = session_state.get('editor', {})
            
            return jsonify({
                'success': True,
                'editor': editor_state
            })
        except Exception as e:
            logger.error(f"Failed to get editor state: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/editor/state', methods=['POST'])
    def save_editor_state():
        """Save editor state to session"""
        try:
            data = request.get_json()
            
            # Validate required fields
            if 'editor' not in data:
                return jsonify({'success': False, 'error': 'Missing editor data'}), 400
            
            # Get current session state
            session_state = player_manager.session_state.get_state()
            
            # Update editor section
            session_state['editor'] = data['editor']
            
            # Save async (debounced)
            player_manager.session_state.save_async(
                player_manager,
                player_manager.clip_registry
            )
            
            return jsonify({
                'success': True,
                'message': 'Editor state saved'
            })
        except Exception as e:
            logger.error(f"Failed to save editor state: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
```

#### Register routes in `src/main.py`

```python
from modules.api_editor import register_editor_routes

# After other route registrations
register_editor_routes(app, player_manager)
```

---

### Phase 2: Frontend Auto-Save (1 hour)

#### File: `frontend/js/editor.js`

**Add session state auto-save functions:**

```javascript
// ========================================
// SESSION STATE AUTO-SAVE
// ========================================

let autoSaveTimeout = null;
const AUTO_SAVE_DELAY = 1000; // 1 second debounce

/**
 * Save current editor state to backend session state
 */
async function saveEditorStateToSession() {
    // Clear existing timeout
    if (autoSaveTimeout) {
        clearTimeout(autoSaveTimeout);
    }
    
    // Debounce: wait 1s after last change
    autoSaveTimeout = setTimeout(async () => {
        try {
            updateAutoSaveStatus('saving');
            
            // Convert background image to base64 if present
            let bgImageData = null;
            if (backgroundImage) {
                const tempCanvas = document.createElement('canvas');
                tempCanvas.width = backgroundImage.width;
                tempCanvas.height = backgroundImage.height;
                const tempCtx = tempCanvas.getContext('2d');
                tempCtx.drawImage(backgroundImage, 0, 0);
                bgImageData = tempCanvas.toDataURL('image/png');
            }
            
            const editorState = {
                projectName: document.getElementById('projectName').value || 'Untitled Project',
                version: '2.0',
                canvas: {
                    width: actualCanvasWidth,
                    height: actualCanvasHeight
                },
                backgroundImage: bgImageData,
                settings: {
                    snapToGrid: snapToGrid,
                    snapToObjects: snapToObjects,
                    allowOutOfBounds: allowOutOfBounds,
                    gridSize: gridSize,
                    showGrid: showGrid,
                    showConnectionLines: showConnectionLines
                },
                shapes: shapes.map(s => ({
                    id: s.id,
                    type: s.type,
                    name: s.name,
                    x: s.x,
                    y: s.y,
                    size: s.size,
                    rotation: s.rotation,
                    scaleX: s.scaleX,
                    scaleY: s.scaleY,
                    color: s.color,
                    pointCount: s.pointCount,
                    rows: s.rows,
                    cols: s.cols,
                    rowSpacing: s.rowSpacing,
                    colSpacing: s.colSpacing,
                    pattern: s.pattern,
                    spikes: s.spikes,
                    innerRatio: s.innerRatio,
                    sides: s.sides,
                    control: s.control,
                    controls: s.controls,
                    controlPoints: s.controlPoints,
                    freehandPoints: s.freehandPoints
                })),
                groups: groups,
                savedAt: new Date().toISOString()
            };
            
            const response = await fetch('/api/editor/state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ editor: editorState })
            });
            
            const result = await response.json();
            
            if (result.success) {
                updateAutoSaveStatus('saved');
            } else {
                updateAutoSaveStatus('error');
                console.error('Auto-save failed:', result.error);
            }
            
        } catch (error) {
            console.error('Auto-save error:', error);
            updateAutoSaveStatus('error');
        }
    }, AUTO_SAVE_DELAY);
}

/**
 * Update auto-save status badge
 */
function updateAutoSaveStatus(status) {
    const badge = document.getElementById('autoSaveStatus');
    if (!badge) return;
    
    switch (status) {
        case 'saving':
            badge.className = 'badge bg-warning';
            badge.textContent = '⏳ Speichert...';
            break;
        case 'saved':
            badge.className = 'badge bg-success';
            badge.textContent = '✓ Gespeichert';
            break;
        case 'error':
            badge.className = 'badge bg-danger';
            badge.textContent = '✗ Fehler';
            break;
    }
}

/**
 * Load editor state from session on page load
 */
async function loadEditorStateFromSession() {
    try {
        const response = await fetch('/api/editor/state');
        const result = await response.json();
        
        if (!result.success || !result.editor) {
            console.log('No saved editor state found');
            return;
        }
        
        const state = result.editor;
        
        // Restore project name
        if (state.projectName) {
            document.getElementById('projectName').value = state.projectName;
        }
        
        // Restore canvas size
        if (state.canvas) {
            setCanvasSize(state.canvas.width, state.canvas.height);
        }
        
        // Restore background image
        if (state.backgroundImage) {
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
            };
            img.src = state.backgroundImage;
        }
        
        // Restore settings
        if (state.settings) {
            snapToGrid = state.settings.snapToGrid ?? true;
            snapToObjects = state.settings.snapToObjects ?? true;
            allowOutOfBounds = state.settings.allowOutOfBounds ?? false;
            gridSize = state.settings.gridSize ?? 10;
            showGrid = state.settings.showGrid ?? true;
            showConnectionLines = state.settings.showConnectionLines ?? true;
            
            // Update UI
            document.getElementById('snapToGrid').checked = snapToGrid;
            document.getElementById('snapToObjects').checked = snapToObjects;
            document.getElementById('allowOutOfBounds').checked = allowOutOfBounds;
            document.getElementById('gridSize').value = gridSize;
            document.getElementById('showGrid').checked = showGrid;
            document.getElementById('showConnectionLines').checked = showConnectionLines;
        }
        
        // Restore shapes
        if (state.shapes && Array.isArray(state.shapes)) {
            shapes = state.shapes;
            shapeCounter = Math.max(...shapes.map(s => parseInt(s.id.split('-')[1]) || 0), 0) + 1;
        }
        
        // Restore groups
        if (state.groups) {
            groups = state.groups;
            groupCounter = groups.length + 1;
        }
        
        markForRedraw();
        updateObjectList();
        updateProjectStats();
        
        console.log('✅ Editor state restored from session');
        showToast('Editor state restored', 'success');
        
    } catch (error) {
        console.error('Failed to load editor state:', error);
    }
}

// Call on page load
window.addEventListener('load', () => {
    loadEditorStateFromSession();
});
```

**Trigger auto-save on every change:**

Add `saveEditorStateToSession()` calls after:
- `addShape()`
- `deleteSelectedShape()`
- `duplicateSelectedShape()`
- `resetSelectedShape()`
- `groupSelectedShapes()`
- `ungroupSelectedShapes()`
- Canvas mouseup (after move/resize/rotate)
- Project name input change
- Canvas size change
- Background image upload
- Settings checkbox change

---

### Phase 3: ArtNet Resolution Input (30 min)

#### Replace Canvas Size with ArtNet Resolution

**HTML changes in `frontend/editor.html`:**

```html
<!-- ArtNet Resolution -->
<div class="d-flex align-items-center" style="gap: 0.5rem;">
  <label style="margin: 0; white-space: nowrap;">ArtNet:</label>
  <input type="number" id="artnetWidth" class="form-control form-control-sm" 
    placeholder="Width" value="1920" min="100" max="10000" style="width: 80px;">
  <span>×</span>
  <input type="number" id="artnetHeight" class="form-control form-control-sm" 
    placeholder="Height" value="1080" min="100" max="10000" style="width: 80px;">
  <button class="btn btn-primary btn-sm" onclick="applyArtNetResolution()">✓</button>
</div>
```

**JS function in `editor.js`:**

```javascript
function applyArtNetResolution() {
    const width = parseInt(document.getElementById('artnetWidth').value);
    const height = parseInt(document.getElementById('artnetHeight').value);
    
    if (width && height) {
        setCanvasSize(width, height);
        saveEditorStateToSession();
        showToast(`ArtNet Resolution: ${width}×${height}`, 'success');
    }
}
```

---

### Phase 4: Cleanup (15 min)

Remove deprecated functions from `editor.js`:

```javascript
// DELETE these functions:
// - saveProject() (unless needed for manual export)
// - saveProjectToServer()
// - loadProjectFromServer()
// - showProjectManager()
// - refreshProjectList()
// - initializeProjectModal()
```

Remove from global exports:

```javascript
// DELETE from window exports:
// window.saveProject = saveProject;
// window.saveProjectToServer = saveProjectToServer;
// window.showProjectManager = showProjectManager;
// window.loadProjectFromServer = loadProjectFromServer;
// window.refreshProjectList = refreshProjectList;
```

---

## 📊 Session State Structure

```json
{
  "editor": {
    "projectName": "My LED Matrix",
    "version": "2.0",
    "canvas": {
      "width": 1920,
      "height": 1080
    },
    "backgroundImage": "data:image/png;base64,...",
    "settings": {
      "snapToGrid": true,
      "snapToObjects": true,
      "allowOutOfBounds": false,
      "gridSize": 10,
      "showGrid": true,
      "showConnectionLines": true
    },
    "shapes": [
      {
        "id": "shape-1",
        "type": "matrix",
        "name": "Matrix 1",
        "x": 500,
        "y": 400,
        "size": 200,
        "rotation": 0,
        "scaleX": 1,
        "scaleY": 1,
        "color": "cyan",
        "pointCount": 64,
        "rows": 8,
        "cols": 8,
        "pattern": "zigzag-left"
      }
    ],
    "groups": [],
    "savedAt": "2026-02-05T10:30:00.000Z"
  }
}
```

---

## ✅ Testing Checklist

- [ ] Add shapes → auto-save triggered → reload page → shapes restored
- [ ] Change project name → auto-save → reload → name restored
- [ ] Upload background image → auto-save → reload → image restored
- [ ] Toggle settings → auto-save → reload → settings restored
- [ ] Change ArtNet resolution → canvas resizes → shapes scale properly
- [ ] Move/resize/rotate shape → auto-save → reload → changes restored
- [ ] Delete shape → auto-save → reload → shape gone
- [ ] Group shapes → auto-save → reload → groups restored
- [ ] Auto-save status badge updates correctly (⏳ → ✓)
- [ ] Works offline (graceful fallback if backend unavailable)
- [ ] Session state included in snapshot system
- [ ] Export still works (shapes exported at ArtNet resolution)

---

## 📝 Notes

- **Migration:** Existing server-saved projects can be manually loaded once, then auto-saved to session
- **Export:** Keep manual export functionality for sharing projects
- **Compatibility:** Version 2.0 format (session state) vs 1.x (server files)
- **Performance:** Debouncing prevents excessive API calls
- **Snapshots:** Editor state automatically included in global snapshots

---

## 🚀 Future Enhancements

- **Undo/Redo:** Track change history in session state
- **Collaboration:** Multiple users editing same session (WebSocket sync)
- **Templates:** Save/load shape templates from library
- **Cloud Sync:** Optional sync to cloud storage
- **Version History:** Keep last N versions in session state

---

**Status Legend:**
- ✅ Completed
- 🚧 In Progress
- ⏸️ Blocked
- ❌ Not Started
