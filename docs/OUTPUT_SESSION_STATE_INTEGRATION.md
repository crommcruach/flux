# 🔄 Output Settings - Session State Integration

**Date**: 2026-01-30  
**Status**: ✅ **IMPLEMENTED**

## 📊 Overview

All output routing settings (slices, outputs, canvas dimensions) are now **automatically stored in backend session state** instead of browser localStorage. This ensures:

- ✅ **Persistence across browser sessions** - Settings survive page reloads
- ✅ **Server-side storage** - No dependency on browser storage
- ✅ **Automatic backups** - Included in snapshot system
- ✅ **Auto-save** - Changes saved automatically after 1 second (debounced)
- ✅ **Fallback support** - localStorage used if backend unavailable

---

## 🔧 Changes Made

### Frontend (`frontend/js/output-settings.js`)

#### 1. **Replaced localStorage with Backend API**

**Before:**
```javascript
loadFromLocalStorage()  // Load from browser storage
saveToLocalStorage()    // Save to browser storage
```

**After:**
```javascript
loadFromBackend()       // Load from backend session state via API
saveToBackend()         // Save to backend session state via API
```

#### 2. **Auto-save with Debouncing**

All edit operations now trigger `saveToBackend()` which:
- Debounces saves (waits 1 second after last change)
- Sends data to `/api/slices/import` endpoint
- Falls back to localStorage if backend unavailable
- Updates backend connection status

**Affected Operations:**
- Creating/editing slices
- Moving/resizing slices
- Rotating slices
- Deleting slices
- Adding masks
- Transform operations
- All property changes

#### 3. **Added Global Functions**

New functions callable from HTML buttons:

```javascript
loadMonitors()           // Load monitors from /api/monitors
saveSlicesToBackend()    // Manual save trigger
loadSlicesFromBackend()  // Manual load trigger
```

#### 4. **Backend Status Display**

```javascript
updateBackendStatus(connected, message)
```

Shows real-time connection status in UI:
- 🟢 Green: Connected and synced
- 🔴 Red: Connection error or using fallback

---

### Backend (Already Implemented)

The backend infrastructure was already in place:

#### Session State Manager (`src/modules/session_state.py`)

```python
def save_output_state(self, player_name: str, output_state: dict):
    """Save output routing state to session"""
    self._state['outputs'][player_name] = {
        'outputs': output_state.get('outputs', {}),
        'slices': output_state.get('slices', {}),
        'enabled_outputs': output_state.get('enabled_outputs', []),
        'timestamp': time.time()
    }
    # Triggers async file write to session_state.json

def get_output_state(self, player_name: str) -> dict:
    """Load output routing state from session"""
    return self._state['outputs'].get(player_name, {})
```

#### Output Manager (`src/modules/outputs/output_manager.py`)

```python
def get_state(self) -> dict:
    """Get complete output state for session persistence"""
    return {
        'outputs': {...},  # All output configurations
        'slices': {...},   # All slice definitions
        'enabled_outputs': [...]
    }

def set_state(self, state: dict):
    """Restore output state from session"""
    # Restores slices and output configurations
```

#### Slice Manager (`src/modules/outputs/slice_manager.py`)

```python
def get_state(self) -> dict:
    """Get all slice definitions for session persistence"""
    
def set_state(self, slices_dict: dict):
    """Restore slice definitions from session"""
```

#### API Endpoints (`src/modules/api_outputs.py`)

```python
@app.route('/api/slices/import', methods=['POST'])
def import_slices():
    """Import slices - saves to session state via output_manager.add_slice()"""

@app.route('/api/slices/export', methods=['GET'])
def export_slices():
    """Export slices - loads from session state"""

@app.route('/api/monitors', methods=['GET'])
def get_monitors():
    """Get available monitors for output assignment"""
```

#### Player Integration (`src/modules/player_core.py`)

```python
# On player initialization (lines 217-227):
if self.output_manager:
    # Restore from session
    saved_state = session_state.get_output_state(self.player_name)
    if saved_state:
        self.output_manager.set_state(saved_state)
    
    # Register auto-save callback
    self.output_manager.set_state_save_callback(
        lambda player_name, state: session_state.save_output_state(player_name, state)
    )
```

---

## 💾 Data Flow

### On Page Load:

```
1. Frontend: app.init()
2. Frontend: loadFromBackend()
3. Backend:  GET /api/slices/export
4. Backend:  output_manager.slice_manager.get_state()
5. Backend:  Returns slice definitions from session_state.json
6. Frontend: Renders slices in UI
```

### On Edit:

```
1. User:     Edits slice (move/resize/rotate)
2. Frontend: saveToBackend() triggered (debounced 1s)
3. Frontend: POST /api/slices/import
4. Backend:  output_manager.add_slice(slice_id, data)
5. Backend:  slice_manager.add_slice()
6. Backend:  Triggers _save_state()
7. Backend:  Calls session_state.save_output_state()
8. Backend:  Async write to session_state.json (debounced)
```

### Session State File Structure:

```json
{
  "outputs": {
    "video": {
      "outputs": {
        "display_main": {
          "type": "display",
          "source": "canvas",
          "slice": "full",
          "monitor_index": 0,
          "enabled": true
        }
      },
      "slices": {
        "slice_12345": {
          "x": 0,
          "y": 0,
          "width": 960,
          "height": 1080,
          "rotation": 0,
          "shape": "rectangle",
          "description": "Left Half"
        }
      },
      "enabled_outputs": ["display_main"],
      "timestamp": 1738249200.0
    }
  }
}
```

---

## 🔄 Automatic Save Triggers

**Every change triggers `saveToBackend()`:**

1. **Slice Operations:**
   - Create new slice
   - Move slice
   - Resize slice
   - Rotate slice
   - Delete slice
   - Duplicate slice

2. **Transform Operations:**
   - Move corner points
   - Apply transform
   - Delete transform

3. **Property Changes:**
   - Soft edge settings
   - Shape type changes
   - Output assignments
   - Source routing

4. **Mask Operations:**
   - Add mask
   - Edit mask
   - Delete mask

5. **UI Actions:**
   - Context menu actions
   - Alignment operations
   - Snap to grid changes

**All operations are debounced** (1 second delay) to avoid excessive API calls.

---

## 🎯 Benefits

### 1. **Reliability**
- Settings survive browser crashes
- No localStorage quota limits
- Consistent across all browsers

### 2. **Integration**
- Part of snapshot system
- Included in session backups
- Can be versioned/tracked

### 3. **Performance**
- Debounced saves (1 second)
- Async file writes (non-blocking)
- No UI freezing

### 4. **User Experience**
- Automatic saves (no manual save needed)
- Real-time status display
- Seamless page reloads

### 5. **Fallback Safety**
- localStorage used if backend unavailable
- Graceful degradation
- No data loss

---

## 🧪 Testing

### Manual Test Workflow:

1. **Load Existing Settings:**
   ```
   - Open output-settings.html
   - Check if existing slices appear
   - Verify backend status shows "Loaded X slices"
   ```

2. **Create New Slice:**
   ```
   - Draw a rectangle
   - Wait 1 second
   - Check backend status (should show "Auto-saved")
   - Refresh page
   - Verify slice persists
   ```

3. **Edit Slice:**
   ```
   - Move/resize slice
   - Wait 1 second
   - Refresh page
   - Verify changes persisted
   ```

4. **Monitor Detection:**
   ```
   - Click "Load Monitors"
   - Verify monitors appear in list
   - Check backend status shows monitor count
   ```

5. **Manual Save:**
   ```
   - Click "Save to Backend"
   - Verify success toast
   - Check backend status
   ```

6. **Session State File:**
   ```
   - Check session_state.json
   - Verify "outputs" section exists
   - Verify "slices" data is present
   ```

### Expected Behavior:

- ✅ Page reload restores all slices
- ✅ Backend status shows green when connected
- ✅ Auto-save happens 1 second after changes
- ✅ Manual buttons work correctly
- ✅ localStorage used as fallback if backend unavailable

---

## 📁 Files Modified

1. **Frontend:**
   - `frontend/js/output-settings.js` - Replaced localStorage with backend API

2. **Backend (Already Complete):**
   - `src/modules/session_state.py` - Session state persistence
   - `src/modules/outputs/output_manager.py` - Output state management
   - `src/modules/outputs/slice_manager.py` - Slice state management
   - `src/modules/api_outputs.py` - API endpoints
   - `src/modules/player_core.py` - Player integration

---

## 🚀 Next Steps

1. **Test the implementation:**
   - Load the page and verify slices load from backend
   - Create/edit slices and verify auto-save works
   - Check session_state.json file for output data

2. **Monitor backend logs:**
   - Check for "Output state saved for video" messages
   - Verify no errors during save/load

3. **Future Enhancements:**
   - Add undo/redo support
   - Version history for slices
   - Export/import slice libraries
   - Preset slice templates

---

## 📊 Summary

**Status**: ✅ All output routing settings now stored in backend session state  
**Auto-save**: ✅ Enabled with 1-second debouncing  
**Fallback**: ✅ localStorage used if backend unavailable  
**Integration**: ✅ Full integration with session state system  
**Testing**: ⚠️ Needs user testing

The output routing settings are now fully integrated with the backend session state system, ensuring reliable persistence and seamless user experience.
