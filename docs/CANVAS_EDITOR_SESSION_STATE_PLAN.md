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
- ✅ Background image path → `session_state.editor.backgroundImagePath` (file saved in `backgrounds/` folder)
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
- ✅ Upload background image (saves to `backgrounds/` folder, stores path only)
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

### Phase 1: Reuse Existing Session State (No Backend Changes Needed!)

**The editor will use the existing session state system** - no new API endpoints required!

#### Existing Infrastructure:

✅ **Endpoint:** `GET /api/session/state` (already exists in `src/modules/api_session.py`)  
✅ **Session Manager:** `SessionStateManager` with auto-save and debouncing  
✅ **Integration:** Already used by player, sequencer, output settings

**Session State Structure:**
```json
{
  "players": { ... },      // Video/ArtNet players
  "sequencer": { ... },    // Audio sequencer
  "output": { ... },       // Output routing
  "editor": {              // 👈 Canvas editor (NEW section)
    "shapes": [...],
    "settings": {...},
    "canvas": {...}
  }
}
```

**How Editor Saves:**
```javascript
// Editor modifies session state directly
const response = await fetch('/api/session/state');
const {state} = await response.json();

// Update editor section
state.editor = editorState;

// Session manager handles auto-save with debouncing
// (Triggered automatically by session state manager)
```

**No custom routes needed** - session state manager already:
- ✅ Auto-saves with 1-second debounce
- ✅ Includes editor data in snapshots
- ✅ Handles restore from snapshots
- ✅ Thread-safe async I/O

---

### Phase 1: Background Upload Endpoint (15 min)

#### Create `/api/backgrounds/upload` endpoint

**File:** `src/modules/api_backgrounds.py` (NEW)

```python
from flask import jsonify, request, send_from_directory
from pathlib import Path
import logging
import re

logger = logging.getLogger(__name__)

def register_background_routes(app):
    """Register background image upload/serve endpoints"""
    
    # Background folder at project root
    BACKGROUNDS_DIR = Path.cwd() / 'backgrounds'
    BACKGROUNDS_DIR.mkdir(exist_ok=True)
    
    @app.route('/api/backgrounds/upload', methods=['POST'])
    def upload_background():
        """Upload background image for canvas editor"""
        try:
            if 'file' not in request.files:
                return jsonify({'success': False, 'error': 'No file provided'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400
            
            # Validate image extension
            allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp')
            if not file.filename.lower().endswith(allowed_extensions):
                return jsonify({
                    'success': False,
                    'error': 'Invalid file type. Allowed: PNG, JPG, GIF, BMP'
                }), 400
            
            # Sanitize filename
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', file.filename)
            
            # Save file
            file_path = BACKGROUNDS_DIR / safe_filename
            file.save(str(file_path))
            
            # Return relative path
            relative_path = f"backgrounds/{safe_filename}"
            
            logger.info(f"Background uploaded: {relative_path}")
            
            return jsonify({
                'success': True,
                'path': relative_path,
                'filename': safe_filename
            })
        
        except Exception as e:
            logger.error(f"Error uploading background: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/backgrounds/<path:filename>', methods=['GET'])
    def serve_background(filename):
        """Serve background images"""
        try:
            return send_from_directory(BACKGROUNDS_DIR, filename)
        except Exception as e:
            logger.error(f"Error serving background: {e}")
            return jsonify({'error': 'File not found'}), 404
```

**Register in `flux_web.py`:**

```python
from modules.api_backgrounds import register_background_routes

# After other route registrations
register_background_routes(app)
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
 * Uses existing /api/session/state endpoint (no custom routes needed)
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
            
            // Get current session state
            const getResponse = await fetch('/api/session/state');
            const {state} = await getResponse.json();
            
            // Update editor section
            state.editor = {
                projectName: document.getElementById('projectName').value || 'Untitled Project',
                version: '2.0',
                canvas: {
                    width: actualCanvasWidth,
                    height: actualCanvasHeight
                },
                backgroundImagePath: backgroundImagePath || null,  // Path to file in backgrounds/
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
            
            // Session state manager will auto-save (backend handles debouncing)
            // No explicit save call needed - modification triggers auto-save
            const response = await fetch('/api/session/state', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(state)  // Send complete state with updated editor section
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
        
        const state = result.state.editor;
        
        // Restore project name
        if (state && state.projectName) {
            document.getElementById('projectName').value = state.projectName;
        }
        
        // Restore canvas size
        if (state.canvas) {
            setCanvasSize(state.canvas.width, state.canvas.height);
        }
        
        // Restore background image from file path
        if (state.backgroundImagePath) {
            backgroundImagePath = state.backgroundImagePath;
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
            };
            img.src = '/' + state.backgroundImagePath;  // Load from backgrounds/ folder
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

/**
 * Upload background image to backgrounds/ folder
 * Uses existing /api/backgrounds/upload endpoint
 */
async function uploadBackgroundImage(file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/api/backgrounds/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Store path to uploaded file
            backgroundImagePath = result.path;  // e.g., "backgrounds/myimage.png"
            
            // Load image for display
            const img = new Image();
            img.onload = () => {
                backgroundImage = img;
                markForRedraw();
                saveEditorStateToSession();  // Auto-save with new background path
                showToast('Background uploaded', 'success');
            };
            img.src = '/' + result.path;  // Load from server
        } else {
            showToast('Upload failed: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Background upload error:', error);
        showToast('Upload error', 'error');
    }
}

// Call on page load
window.addEventListener('load', () => {
    loadEditorStateFromSession();
});
```

**Trigger auto-save on every change:**

Add `saveEditorStateToSession()` calls after:

**Shape modifications (in `editor.js`):**
```javascript
function addShape(type) {
    // ... existing code ...
    shapes.push(base);
    selectedShape = base;
    updateToolbarSections();
    markForRedraw();
    updateObjectList();
    saveEditorStateToSession();  // 👈 ADD THIS
}

function deleteSelectedShape() {
    // ... existing code ...
    markForRedraw();
    updateObjectList();
    saveEditorStateToSession();  // 👈 ADD THIS
}

function duplicateSelectedShape() {
    // ... existing code ...
    markForRedraw();
    updateObjectList();
    saveEditorStateToSession();  // 👈 ADD THIS
}

function resetSelectedShape() {
    // ... existing code ...
    markForRedraw();
    saveEditorStateToSession();  // 👈 ADD THIS
}

function groupSelectedShapes() {
    // ... existing code ...
    markForRedraw();
    saveEditorStateToSession();  // 👈 ADD THIS
}

function ungroupSelectedShapes() {
    // ... existing code ...
    markForRedraw();
    saveEditorStateToSession();  // 👈 ADD THIS
}
```

**Mouse interactions (in canvas event handlers):**
```javascript
canvas.addEventListener('mouseup', (e) => {
    // ... existing drag/resize/rotate logic ...
    
    if (dragMode) {
        // Shape was moved/resized/rotated
        saveEditorStateToSession();  // 👈 ADD THIS
    }
    
    dragMode = null;
    // ... rest of code ...
});
```

**Settings changes:**
```javascript
document.getElementById('projectName').addEventListener('change', saveEditorStateToSession);
document.getElementById('artnetWidth').addEventListener('change', saveEditorStateToSession);
document.getElementById('artnetHeight').addEventListener('change', saveEditorStateToSession);
document.getElementById('snapToGrid').addEventListener('change', saveEditorStateToSession);
document.getElementById('snapToObjects').addEventListener('change', saveEditorStateToSession);
document.getElementById('showGrid').addEventListener('change', saveEditorStateToSession);
document.getElementById('showConnectionLines').addEventListener('change', saveEditorStateToSession);
```

**Result:** Every shape add/modify/delete/move/rotate/resize triggers auto-save with 1-second debounce.

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

### ✅ **Clear Separation: Editor Settings vs Object Settings**

```json
{
  "editor": {
    // ========================================
    // GLOBAL EDITOR SETTINGS (Canvas-level)
    // ========================================
    "projectName": "My LED Matrix",
    "version": "2.0",
    
    "canvas": {
      "width": 1920,           // ArtNet resolution (not visual canvas size)
      "height": 1080
    },
    
    "backgroundImagePath": "backgrounds/stage_layout.png",
    
    // EDITOR BEHAVIOR SETTINGS (apply to all editing operations)
    "settings": {
      "snapToGrid": true,           // Global: snap any object to grid
      "snapToObjects": true,         // Global: snap any object to other objects
      "allowOutOfBounds": false,     // Global: allow any object outside canvas
      "gridSize": 10,                // Global: grid spacing in pixels
      "showGrid": true,              // Global: grid visibility toggle
      "showConnectionLines": true    // Global: connection lines visibility
    },
    
    // ========================================
    // OBJECT-SPECIFIC SETTINGS (per shape)
    // ========================================
    "shapes": [
      {
        // SHAPE IDENTITY
        "id": "shape-1",
        "type": "matrix",
        "name": "Matrix 1",
        
        // SHAPE TRANSFORM (position, size, rotation)
        "x": 500,
        "y": 400,
        "size": 200,
        "rotation": 0,
        "scaleX": 1,
        "scaleY": 1,
        
        // SHAPE APPEARANCE
        "color": "cyan",
        
        // SHAPE-SPECIFIC PROPERTIES (different per type)
        "pointCount": 64,
        "rows": 8,
        "cols": 8,
        "pattern": "zigzag-left"      // Matrix-specific
      },
      {
        // Another shape with different properties
        "id": "shape-2",
        "type": "circle",
        "name": "Circle Ring",
        "x": 800,
        "y": 600,
        "size": 150,
        "rotation": 0,
        "scaleX": 1,
        "scaleY": 1,
        "color": "magenta",
        "pointCount": 32              // Circle-specific (no rows/cols/pattern)
      },
      {
        "id": "shape-3",
        "type": "star",
        "name": "Star Fixture",
        "x": 300,
        "y": 200,
        "size": 100,
        "rotation": 45,
        "scaleX": 1,
        "scaleY": 1,
        "color": "yellow",
        "pointCount": 25,
        "spikes": 5,                  // Star-specific
        "innerRatio": 0.5             // Star-specific
      }
    ],
    
    // ========================================
    // GROUPING (object relationships)
    // ========================================
    "groups": [
      {
        "id": "group-1",
        "name": "Left Side Matrices",
        "shapeIds": ["shape-1", "shape-4"]
      }
    ],
    
    "savedAt": "2026-02-05T10:30:00.000Z"
  }
}
```

---

### � **Relationship: Editor Shapes vs Art-Net Objects**

**Two-tier storage system:**

| Tier | Location | Purpose | Content |
|------|----------|---------|---------|
| **Editor Shapes** | `editor.shapes[]` | Shape parameters for editing | Position, size, rotation, rows/cols, pattern, etc. |
| **Art-Net Objects** | `output.artnet.objects[]` | Actual LED coordinates for output | Calculated x/y pixel coordinates for each LED |

**Data Flow:**

1. **User edits shape** → Update `editor.shapes[n]` parameters
2. **Auto-save triggered** → Calculate all LED coordinates from shape parameters
3. **Save both tiers**:
   - `editor.shapes[]` → For editing/manipulation
   - `output.artnet.objects[]` → For Art-Net rendering

**Why both?**
- **Editor shapes** = Compact (8-10 properties per shape)
- **Art-Net objects** = Expanded (100+ coordinate pairs per object)
- **Backend needs coordinates** for rendering video to LEDs
- **Frontend needs parameters** for interactive editing

**Example:**
```javascript
// Editor shape (compact)
editor.shapes[0] = { type: "matrix", x: 500, y: 400, rows: 8, cols: 10 }

// Generated Art-Net object (expanded)
output.artnet.objects[0] = { 
  id: "shape-1", 
  points: [
    {id: 1, x: 450, y: 350}, 
    {id: 2, x: 470, y: 350},
    // ... 80 total coordinate pairs
  ]
}
```

---

### �📋 **Settings Location Reference**

| Setting Type | Location in Session State | Scope |
|--------------|---------------------------|-------|
| **GLOBAL EDITOR** | `editor.settings.*` | Applies to all objects |
| Snap to Grid | `editor.settings.snapToGrid` | Global behavior |
| Snap to Objects | `editor.settings.snapToObjects` | Global behavior |
| Allow Out of Bounds | `editor.settings.allowOutOfBounds` | Global constraint |
| Grid Size | `editor.settings.gridSize` | Global grid spacing |
| Show Grid | `editor.settings.showGrid` | Global visibility |
| Show Connection Lines | `editor.settings.showConnectionLines` | Global visibility |
| | | |
| **CANVAS PROPERTIES** | `editor.canvas.*` | Canvas-level |
| ArtNet Width | `editor.canvas.width` | Resolution width |
| ArtNet Height | `editor.canvas.height` | Resolution height |
| Background Image | `editor.backgroundImagePath` | Visual reference |
| | | |
| **OBJECT PROPERTIES** | `editor.shapes[n].*` | Per-shape only |
| Position | `shapes[n].x`, `shapes[n].y` | Individual shape |
| Size/Scale | `shapes[n].size`, `shapes[n].scaleX/Y` | Individual shape |
| Rotation | `shapes[n].rotation` | Individual shape |
| Color | `shapes[n].color` | Individual shape |
| Type-specific | `shapes[n].rows`, `spikes`, etc. | Individual shape |

**Note:** LED dot coordinates are **calculated on-demand** (not stored in session state).  
Art-Net Output Routing page will load shapes and calculate dots using same logic.

---

### 🔍 **Example: How Settings Are Applied**

**Scenario: User drags a shape**

1. **Check global editor setting:** `editor.settings.snapToGrid`
   - If `true` → apply grid snapping to this shape
   - Grid spacing from: `editor.settings.gridSize`

2. **Check global editor setting:** `editor.settings.snapToObjects`
   - If `true` → check distance to all other shapes
   - Snap if within threshold

3. **Check global constraint:** `editor.settings.allowOutOfBounds`
   - If `false` → constrain shape position to canvas bounds
   - Canvas bounds from: `editor.canvas.width` × `editor.canvas.height`

4. **Update individual shape:** `editor.shapes[n].x`, `editor.shapes[n].y`
   - Store new position in shape's own properties
   - Other shapes not affected

5. **Auto-save to session state**
   - Shape parameters persisted
   - Dots recalculated by Art-Net page when needed

**Result:** Global settings control behavior, shape stores parameters, dots calculated on-demand.

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
- [ ] Background image uploads to `backgrounds/` folder
- [ ] Background image path persists in session state
- [ ] Background image loads correctly after reload
- [ ] Session state included in snapshot system
- [ ] Export still works (shapes exported at ArtNet resolution)

---

## 📝 Notes

- **Export:** Keep manual export functionality for sharing projects
- **Performance:** Debouncing prevents excessive API calls
- **Snapshots:** Editor state automatically included in global snapshots
- **Background Images:** Stored as files in `backgrounds/` folder (not base64)
- **No Migration:** Fresh start - no backward compatibility with old server-saved projects

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
