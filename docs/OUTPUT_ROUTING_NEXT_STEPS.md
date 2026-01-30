# 🎯 Output Routing Implementation - Next Steps

**Status**: Backend infrastructure COMPLETE ✅ | Frontend API integration PENDING ⚠️  
**Date**: 2026-01-30  
**Goal**: Connect frontend output-settings.html to working backend API

---

## 📊 Current State Assessment

### ✅ COMPLETED Backend Infrastructure

1. **Output Module System** (`src/modules/outputs/`)
   - ✅ `output_base.py` - Abstract base class with frame queuing
   - ✅ `output_manager.py` - Frame distribution coordinator (896 lines)
   - ✅ `slice_manager.py` - Slice extraction with shapes/masks/rotation (359 lines)
   - ✅ `monitor_utils.py` - Monitor detection utilities
   - ✅ `plugins/display_output.py` - OpenCV window output (269 lines, multiprocessing)
   - ✅ `plugins/virtual_output.py` - Virtual output for testing

2. **Player Integration** (`src/modules/player_core.py`)
   - ✅ OutputManager initialization (lines 179-234)
   - ✅ Frame distribution to outputs (lines 1415-1423)
   - ✅ Layer manager reference passing
   - ✅ Session state integration
   - ✅ Auto-save callback registration

3. **API Endpoints** (`src/modules/api_outputs.py`, 899 lines)
   - ✅ `/api/monitors` - Monitor detection
   - ✅ `/api/outputs/<player>` - Get all outputs
   - ✅ `/api/outputs/<player>/<output_id>/enable` - Enable output
   - ✅ `/api/outputs/<player>/<output_id>/disable` - Disable output
   - ✅ `/api/slices/*` - Slice CRUD endpoints
   - ✅ `/api/outputs/types` - Available output types

4. **Configuration System**
   - ✅ config.json `outputs.definitions` section
   - ✅ Session state persistence (save/load output state)
   - ✅ Output enable/disable state tracking

5. **Source Routing Features**
   - ✅ `canvas` - Full composited output
   - ✅ `clip:current` - Current clip routing
   - ✅ `clip:<uuid>` - Specific clip routing
   - ✅ `layer:<N>` - Single layer isolation
   - ✅ `layer:<N>:inclusive` - Hierarchical layer composite
   - ✅ Slice extraction (rectangle, polygon, circle)
   - ✅ Soft edges, masks, rotation

### ❌ MISSING Frontend Integration

1. **JavaScript API Client** (`frontend/js/output-settings.js`)
   - ❌ `loadMonitors()` function - NOT IMPLEMENTED
   - ❌ `saveSlicesToBackend()` function - NOT IMPLEMENTED  
   - ❌ `loadSlicesFromBackend()` function - NOT IMPLEMENTED
   - ❌ Backend connection status checking
   - ✅ Slice editor UI fully functional (3329 lines)
   - ✅ Local storage save/load working
   - ❌ No API calls to backend

2. **Frontend UI Elements** (`frontend/output-settings.html`)
   - ✅ Backend Sync section exists (lines 137-149)
   - ✅ "Load Monitors" button present
   - ✅ "Save to Backend" button present
   - ✅ "Load from Backend" button present
   - ✅ Backend status display area
   - ❌ Buttons not connected to backend

3. **Output Management UI**
   - ✅ Output checkboxes display (line 99)
   - ❌ No dynamic output creation UI
   - ❌ No output type selection (display/virtual/NDI/Spout)
   - ❌ No source routing UI (canvas/clip/layer selection)
   - ❌ No per-output slice assignment UI

---

## 🎯 Implementation Plan: Frontend API Integration

### Phase 1: Basic Backend Connectivity (2-3 hours)

#### Step 1.1: Implement Monitor Loading (30 minutes)

**File**: `frontend/js/output-settings.js`

**Add function to load monitors from backend:**

```javascript
/**
 * Load available monitors from backend
 */
async function loadMonitors() {
    try {
        const response = await fetch('/api/monitors');
        const data = await response.json();
        
        if (!data.success) {
            showToast('❌ Failed to load monitors: ' + data.error, 'error');
            updateBackendStatus(false, 'API error');
            return;
        }
        
        // Update backend status
        updateBackendStatus(true, `Connected (${data.count} monitors)`);
        
        // Update monitor count display
        const monitorCountEl = document.getElementById('monitorCount');
        const monitorCountNumEl = document.getElementById('monitorCountNum');
        if (monitorCountEl && monitorCountNumEl) {
            monitorCountEl.style.display = 'block';
            monitorCountNumEl.textContent = data.count;
        }
        
        // Update outputs list with monitors
        app.screens = data.monitors.map((monitor, index) => ({
            id: `monitor_${index}`,
            name: monitor.name,
            width: monitor.width,
            height: monitor.height,
            x: monitor.x,
            y: monitor.y,
            type: 'monitor',
            monitor_index: index
        }));
        
        // Update UI
        updateOutputsList();
        
        showToast(`✅ Loaded ${data.count} monitor(s)`, 'success');
        
    } catch (error) {
        console.error('Failed to load monitors:', error);
        showToast('❌ Backend connection failed', 'error');
        updateBackendStatus(false, 'Connection error');
    }
}

/**
 * Update backend connection status display
 */
function updateBackendStatus(connected, message) {
    const statusEl = document.getElementById('backendStatusText');
    if (statusEl) {
        statusEl.textContent = message;
        statusEl.style.color = connected ? '#4CAF50' : '#f44336';
    }
}

/**
 * Update outputs list UI with current screens
 */
function updateOutputsList() {
    const container = document.getElementById('screenButtonsContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    app.screens.forEach((screen, index) => {
        const checkbox = document.createElement('label');
        checkbox.className = 'screen-checkbox';
        checkbox.innerHTML = `
            <input type="checkbox" value="${screen.id}" onchange="app.toggleScreenAssignment('${screen.id}')">
            <span>${screen.name} (${screen.width}x${screen.height})</span>
        `;
        container.appendChild(checkbox);
    });
}
```

**Add to HTML (if not present):**
```html
<!-- Already exists in output-settings.html, just verify it's working -->
<button class="primary" onclick="loadMonitors()" style="background: #2196F3;">
    🖥️ Load Monitors
</button>
```

#### Step 1.2: Implement Slice Save to Backend (45 minutes)

**File**: `frontend/js/output-settings.js`

```javascript
/**
 * Save slices to backend
 */
async function saveSlicesToBackend() {
    try {
        // Prepare slice data
        const slicesData = {};
        
        app.slices.forEach(slice => {
            const sliceId = slice.id || `slice_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            slicesData[sliceId] = {
                x: Math.round(slice.x),
                y: Math.round(slice.y),
                width: Math.round(slice.width),
                height: Math.round(slice.height),
                rotation: slice.rotation || 0,
                shape: slice.shape || 'rectangle',
                soft_edge: slice.softEdge || null,
                description: slice.name || '',
                points: slice.points || null,
                outputs: slice.outputs || [],  // Which outputs use this slice
                source: slice.source || 'canvas'  // canvas/clip:current/layer:0
            };
            
            // Store slice ID back on object
            if (!slice.id) {
                slice.id = sliceId;
            }
        });
        
        // Send to backend
        const response = await fetch('/api/slices/video/batch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                slices: slicesData,
                canvas_width: app.canvasWidth,
                canvas_height: app.canvasHeight
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast('❌ Failed to save slices: ' + data.error, 'error');
            return;
        }
        
        showToast(`✅ Saved ${Object.keys(slicesData).length} slice(s) to backend`, 'success');
        
        // Update local storage too
        app.saveToLocalStorage();
        
    } catch (error) {
        console.error('Failed to save slices:', error);
        showToast('❌ Backend save failed', 'error');
    }
}
```

#### Step 1.3: Implement Slice Load from Backend (45 minutes)

**File**: `frontend/js/output-settings.js`

```javascript
/**
 * Load slices from backend
 */
async function loadSlicesFromBackend() {
    try {
        const response = await fetch('/api/slices/video');
        const data = await response.json();
        
        if (!data.success) {
            showToast('❌ Failed to load slices: ' + data.error, 'error');
            return;
        }
        
        // Clear current slices
        app.slices = [];
        
        // Load slices from backend
        Object.entries(data.slices || {}).forEach(([sliceId, sliceData]) => {
            app.slices.push({
                id: sliceId,
                x: sliceData.x,
                y: sliceData.y,
                width: sliceData.width,
                height: sliceData.height,
                rotation: sliceData.rotation || 0,
                shape: sliceData.shape || 'rectangle',
                softEdge: sliceData.soft_edge || null,
                name: sliceData.description || sliceId,
                points: sliceData.points || null,
                outputs: sliceData.outputs || [],
                source: sliceData.source || 'canvas',
                color: app.colors[app.colorIndex % app.colors.length],
                masks: []
            });
            app.colorIndex++;
        });
        
        // Update UI
        app.updateSlicesList();
        app.render();
        
        showToast(`✅ Loaded ${app.slices.length} slice(s) from backend`, 'success');
        
    } catch (error) {
        console.error('Failed to load slices:', error);
        showToast('❌ Backend load failed', 'error');
    }
}
```

#### Step 1.4: Add API Endpoint for Batch Slice Update (30 minutes)

**File**: `src/modules/api_outputs.py`

**Add to existing routes (check if already present):**

```python
@app.route('/api/slices/<player>/batch', methods=['POST'])
def batch_update_slices(player):
    """Batch update/create slices"""
    try:
        player_obj = player_manager.get_player(player)
        if not player_obj or not player_obj.output_manager:
            return jsonify({
                'success': False,
                'error': 'Output manager not available'
            }), 404
        
        data = request.json
        slices = data.get('slices', {})
        
        # Clear existing slices
        # Note: This will keep 'full' slice
        
        # Add all slices
        for slice_id, slice_data in slices.items():
            player_obj.output_manager.add_slice(slice_id, slice_data)
        
        return jsonify({
            'success': True,
            'message': f'Updated {len(slices)} slices'
        })
        
    except Exception as e:
        logger.error(f"Failed to batch update slices: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/slices/<player>', methods=['GET'])
def get_all_slices(player):
    """Get all slices for player"""
    try:
        player_obj = player_manager.get_player(player)
        if not player_obj or not player_obj.output_manager:
            return jsonify({
                'success': False,
                'error': 'Output manager not available'
            }), 404
        
        state = player_obj.output_manager.get_state()
        
        return jsonify({
            'success': True,
            'slices': state.get('slices', {}),
            'canvas_width': player_obj.canvas_width,
            'canvas_height': player_obj.canvas_height
        })
        
    except Exception as e:
        logger.error(f"Failed to get slices: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
```

---

### Phase 2: Output Management UI (3-4 hours)

#### Step 2.1: Add Output Creation Dialog (2 hours)

**Create new modal in `output-settings.html`:**

```html
<!-- Add before closing </body> tag -->
<div class="modal fade" id="createOutputModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Create Output</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <label class="form-label">Output Type</label>
                    <select class="form-select" id="outputType" onchange="updateOutputTypeFields()">
                        <option value="display">🖥️ Display/Monitor</option>
                        <option value="virtual">💾 Virtual Output</option>
                        <option value="ndi">📡 NDI Network (if available)</option>
                        <option value="spout">🎨 Spout GPU (if available)</option>
                    </select>
                </div>
                
                <div id="outputTypeFields"></div>
                
                <div class="mb-3">
                    <label class="form-label">Source</label>
                    <select class="form-select" id="outputSource">
                        <option value="canvas">Full Canvas (all layers)</option>
                        <option value="clip:current">Current Clip</option>
                        <option value="layer:0">Layer 0 (Background)</option>
                        <option value="layer:1">Layer 1 (Overlay 1)</option>
                        <option value="layer:2">Layer 2 (Overlay 2)</option>
                        <option value="layer:3">Layer 3 (Overlay 3)</option>
                        <option value="layer:0:inclusive">Layers 0-0 (Inclusive)</option>
                        <option value="layer:1:inclusive">Layers 0-1 (Inclusive)</option>
                        <option value="layer:2:inclusive">Layers 0-2 (Inclusive)</option>
                        <option value="layer:3:inclusive">Layers 0-3 (Inclusive)</option>
                    </select>
                </div>
                
                <div class="mb-3">
                    <label class="form-label">Slice</label>
                    <select class="form-select" id="outputSlice">
                        <option value="full">Full Canvas</option>
                        <!-- Populated dynamically from slices -->
                    </select>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                <button type="button" class="btn btn-primary" onclick="createOutputSubmit()">Create</button>
            </div>
        </div>
    </div>
</div>
```

**Add JavaScript to handle output creation:**

```javascript
/**
 * Show create output modal
 */
function showCreateOutputModal() {
    // Load available output types from backend
    fetch('/api/outputs/types')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // Update modal with available types
                populateOutputTypeOptions(data.types);
            }
        });
    
    // Update slice dropdown
    updateSliceDropdown();
    
    // Show modal
    const modal = new bootstrap.Modal(document.getElementById('createOutputModal'));
    modal.show();
}

/**
 * Update output type fields based on selection
 */
function updateOutputTypeFields() {
    const outputType = document.getElementById('outputType').value;
    const fieldsContainer = document.getElementById('outputTypeFields');
    
    // Fetch field configuration for this type
    fetch('/api/outputs/types')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.types[outputType]) {
                const typeConfig = data.types[outputType];
                fieldsContainer.innerHTML = buildOutputTypeFields(typeConfig);
            }
        });
}

/**
 * Build HTML for output type-specific fields
 */
function buildOutputTypeFields(typeConfig) {
    let html = '';
    
    Object.entries(typeConfig.configurable_fields || {}).forEach(([fieldName, fieldConfig]) => {
        html += '<div class="mb-3">';
        html += `<label class="form-label">${fieldConfig.label}</label>`;
        
        if (fieldConfig.type === 'select') {
            html += `<select class="form-select" id="field_${fieldName}">`;
            fieldConfig.options.forEach(opt => {
                html += `<option value="${opt.value}">${opt.label}</option>`;
            });
            html += '</select>';
        } else if (fieldConfig.type === 'checkbox') {
            const checked = fieldConfig.default ? 'checked' : '';
            html += `<input type="checkbox" class="form-check-input" id="field_${fieldName}" ${checked}>`;
        } else if (fieldConfig.type === 'text') {
            const value = fieldConfig.default || '';
            html += `<input type="text" class="form-control" id="field_${fieldName}" value="${value}">`;
        } else if (fieldConfig.type === 'resolution') {
            html += `<input type="text" class="form-control" id="field_${fieldName}" placeholder="1920x1080">`;
        }
        
        html += '</div>';
    });
    
    return html;
}

/**
 * Submit output creation
 */
async function createOutputSubmit() {
    try {
        const outputType = document.getElementById('outputType').value;
        const source = document.getElementById('outputSource').value;
        const slice = document.getElementById('outputSlice').value;
        
        // Collect type-specific fields
        const config = {
            type: outputType,
            source: source,
            slice: slice,
            enabled: true
        };
        
        // Add type-specific fields
        document.querySelectorAll('[id^="field_"]').forEach(field => {
            const fieldName = field.id.replace('field_', '');
            if (field.type === 'checkbox') {
                config[fieldName] = field.checked;
            } else {
                config[fieldName] = field.value;
            }
        });
        
        // Generate unique output ID
        const outputId = `output_${Date.now()}`;
        
        // Send to backend
        const response = await fetch(`/api/outputs/video/${outputId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast('❌ Failed to create output: ' + data.error, 'error');
            return;
        }
        
        showToast('✅ Output created successfully', 'success');
        
        // Close modal
        bootstrap.Modal.getInstance(document.getElementById('createOutputModal')).hide();
        
        // Reload outputs
        loadOutputsFromBackend();
        
    } catch (error) {
        console.error('Failed to create output:', error);
        showToast('❌ Output creation failed', 'error');
    }
}

/**
 * Load outputs from backend and update UI
 */
async function loadOutputsFromBackend() {
    try {
        const response = await fetch('/api/outputs/video');
        const data = await response.json();
        
        if (!data.success) {
            console.error('Failed to load outputs:', data.error);
            return;
        }
        
        // Update UI with outputs
        displayOutputsList(data.outputs);
        
    } catch (error) {
        console.error('Failed to load outputs:', error);
    }
}

/**
 * Display outputs in UI
 */
function displayOutputsList(outputs) {
    const container = document.getElementById('screenButtonsContainer');
    if (!container) return;
    
    container.innerHTML = '';
    
    Object.entries(outputs).forEach(([outputId, outputConfig]) => {
        const div = document.createElement('div');
        div.className = 'output-item';
        div.innerHTML = `
            <div class="output-header">
                <strong>${outputConfig.type}</strong>: ${outputId}
            </div>
            <div class="output-details">
                Source: ${outputConfig.source}<br>
                Slice: ${outputConfig.slice}<br>
                Status: ${outputConfig.enabled ? '✅ Enabled' : '❌ Disabled'}
            </div>
            <div class="output-actions">
                <button class="btn btn-sm btn-primary" onclick="toggleOutput('${outputId}', ${!outputConfig.enabled})">
                    ${outputConfig.enabled ? 'Disable' : 'Enable'}
                </button>
                <button class="btn btn-sm btn-danger" onclick="deleteOutput('${outputId}')">Delete</button>
            </div>
        `;
        container.appendChild(div);
    });
}

/**
 * Toggle output enabled state
 */
async function toggleOutput(outputId, enable) {
    try {
        const endpoint = enable ? 'enable' : 'disable';
        const response = await fetch(`/api/outputs/video/${outputId}/${endpoint}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast('❌ Failed to toggle output', 'error');
            return;
        }
        
        showToast(`✅ Output ${enable ? 'enabled' : 'disabled'}`, 'success');
        loadOutputsFromBackend();
        
    } catch (error) {
        console.error('Failed to toggle output:', error);
    }
}
```

**Update "Add Output" button:**

```html
<!-- In output-settings.html, update existing button -->
<button class="primary" onclick="showCreateOutputModal()" style="margin-top: 10px; width: 100%;">
    ➕ Add Output
</button>
```

---

### Phase 3: Testing & Validation (2 hours)

#### Test Checklist:

1. **Monitor Detection**
   - [ ] Click "Load Monitors" button
   - [ ] Verify monitors appear in list
   - [ ] Verify backend status shows "Connected"

2. **Slice Management**
   - [ ] Create slice in editor
   - [ ] Click "Save to Backend"
   - [ ] Refresh page
   - [ ] Click "Load from Backend"
   - [ ] Verify slice reappears

3. **Output Creation**
   - [ ] Click "Add Output"
   - [ ] Select "Display/Monitor"
   - [ ] Configure settings
   - [ ] Create output
   - [ ] Verify output appears in list

4. **Output Enable/Disable**
   - [ ] Enable output
   - [ ] Verify window appears on screen
   - [ ] Disable output
   - [ ] Verify window closes

5. **Source Routing**
   - [ ] Create output with "Layer 0" source
   - [ ] Verify only background layer visible
   - [ ] Change to "canvas" source
   - [ ] Verify all layers visible

6. **Slice Assignment**
   - [ ] Create slice (e.g., left half)
   - [ ] Create output with slice assigned
   - [ ] Verify only sliced region displayed

---

## 🔧 Quick Fixes Needed

### Issue 1: Missing API Endpoint - Create Output

**File**: `src/modules/api_outputs.py`

**Check if this endpoint exists:**

```python
@app.route('/api/outputs/<player>/<output_id>', methods=['POST'])
def create_output(player, output_id):
    """Create a new output dynamically"""
    # Implementation needed
```

If missing, add it.

### Issue 2: Output Manager - Dynamic Output Creation

**File**: `src/modules/outputs/output_manager.py`

**Add method if missing:**

```python
def create_output(self, output_id: str, config: dict) -> bool:
    """
    Create a new output dynamically
    
    Args:
        output_id: Unique output identifier
        config: Output configuration dict
        
    Returns:
        bool: True if created successfully
    """
    try:
        output_type = config.get('type')
        
        if output_type == 'display':
            from .plugins import DisplayOutput
            output = DisplayOutput(output_id, config)
        elif output_type == 'virtual':
            from .plugins import VirtualOutput
            output = VirtualOutput(output_id, config)
        else:
            logger.error(f"Unknown output type: {output_type}")
            return False
        
        self.register_output(output_id, output)
        
        if config.get('enabled', False):
            self.enable_output(output_id)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create output: {e}", exc_info=True)
        return False
```

---

## 📋 Priority Action Items

### Immediate (Today):

1. **Implement `loadMonitors()` function** (30 min)
   - Add to `output-settings.js`
   - Test with backend
   - Verify monitors load

2. **Implement `saveSlicesToBackend()` function** (45 min)
   - Add to `output-settings.js`
   - Test slice persistence
   - Verify session state save

3. **Implement `loadSlicesFromBackend()` function** (45 min)
   - Add to `output-settings.js`
   - Test slice restoration
   - Verify UI updates

### Next (Tomorrow):

4. **Add Output Creation UI** (2 hours)
   - Create modal
   - Add JavaScript handlers
   - Test output creation

5. **Test Complete Workflow** (2 hours)
   - End-to-end testing
   - Bug fixes
   - Documentation

---

## 🎯 Success Criteria

### Minimum Viable (Must Have):

- ✅ Backend monitors load in frontend
- ✅ Slices save to backend
- ✅ Slices load from backend
- ✅ Outputs can be created via UI
- ✅ Outputs can be enabled/disabled
- ✅ Display windows appear on correct monitor

### Full Feature Set (Nice to Have):

- ✅ Source routing UI (canvas/clip/layer)
- ✅ Slice assignment per output
- ✅ Output preview thumbnails
- ✅ Live output status indicators
- ✅ Output statistics (FPS, frames sent)

---

## 📁 Files to Modify

### Frontend:
1. `frontend/js/output-settings.js` - Add API functions (lines to add: ~200)
2. `frontend/output-settings.html` - Add output modal (lines to add: ~50)
3. `frontend/css/output-settings.css` - Add output styles (optional)

### Backend:
4. `src/modules/api_outputs.py` - Add missing endpoints (if any)
5. `src/modules/outputs/output_manager.py` - Add dynamic output creation (if missing)

---

## 🚀 Estimated Time to Complete

| Task | Time | Priority |
|------|------|----------|
| Phase 1: Basic Connectivity | 2-3h | 🔴 Critical |
| Phase 2: Output Management UI | 3-4h | 🟡 High |
| Phase 3: Testing | 2h | 🟡 High |
| **Total** | **7-9h** | |

---

**Next Action**: Start with Phase 1, Step 1.1 - Implement `loadMonitors()` function

**Goal**: Have functional backend sync within 3 hours
