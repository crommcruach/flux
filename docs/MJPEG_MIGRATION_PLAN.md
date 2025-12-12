# MJPEG Migration Plan
**Date:** 2024-12-12  
**Goal:** Reactivate MJPEG as primary preview source and remove WebSocket video implementation entirely

---

## 🎯 Objectives

1. **Remove WebSocket Video Streaming** - Eliminate `api_websocket.py` and all related Socket.IO video namespace
2. **Reactivate MJPEG as Primary** - Make MJPEG the sole video preview mechanism
3. **Simplify Frontend** - Remove WebSocket preview components and fallback logic
4. **Improve Stability** - Reduce complexity, eliminate Socket.IO connection issues
5. **Maintain Performance** - MJPEG is sufficient for LAN preview (simpler = more stable)

---

## 📊 Current Architecture

### Backend Components
- ✅ **MJPEG Endpoints** (in `api_routes.py`)
  - `/preview` - Scaled preview (default 640x480)
  - `/preview_full` - Full resolution preview
  - Both working and ready to use

- ❌ **WebSocket Video** (in `api_websocket.py`)
  - `/video` namespace with Socket.IO
  - Frame streaming with quality/FPS control
  - Adds complexity, connection issues, resource overhead
  - **TO BE REMOVED**

### Frontend Components
- ✅ **MJPEG Display** (in `player.js`)
  - `startMJPEGPreview()` - Simple `<img>` refresh
  - Currently used as fallback
  - **TO BE PRIMARY**

- ❌ **WebSocket Preview** (in `websocket-preview.js`)
  - `WebSocketPreview` class with Socket.IO connection
  - Canvas rendering, FPS stats, reconnection logic
  - **TO BE REMOVED**

- ❌ **WebRTC Preview** (in `webrtc-preview.js`)
  - Experimental, never fully implemented
  - **TO BE REMOVED**

---

## 🗑️ Components to Remove

### Backend Files
1. **`src/modules/api_websocket.py`** (334 lines)
   - Entire WebSocket video streaming implementation
   - Frame compression, quality adjustment, threading
   - Socket.IO `/video` namespace handlers

### Frontend Files
1. **`frontend/js/websocket-preview.js`** (408 lines)
   - `WebSocketPreview` class
   - Socket.IO client connection
   - Canvas frame rendering

2. **`frontend/js/webrtc-preview.js`** (~400 lines)
   - Experimental WebRTC implementation
   - Never fully activated
   - Cleanup

### Modified Files

**Backend:**
- `src/modules/rest_api.py`
  - Remove `_init_websocket_video_streaming()` method
  - Remove `api_websocket` import
  - Remove `/video` namespace registration

**Frontend:**
- `frontend/js/player.js`
  - Remove `websocketPreview` variable and logic
  - Remove `startPreviewStream()` WebSocket path
  - Simplify to only use `startMJPEGPreview()`
  - Remove preview mode toggle (no fallback needed)

- `frontend/player.html`
  - Remove `<script src="js/websocket-preview.js">`
  - Remove `<script src="js/webrtc-preview.js">`
  - Remove `<canvas id="videoPreviewVideo">` (use only `<img>`)

- `frontend/js/common.js`
  - Remove `/video` socket initialization
  - Keep only main `/` socket and other namespaces

**Config:**
- `config.json`
  - Remove `websocket_streaming` section entirely
  - Simplify to only have MJPEG-relevant settings

---

## ✅ What Stays (MJPEG Core)

### Backend
- `api_routes.py` - `/preview` and `/preview_full` endpoints
- Player's `last_video_frame` capture (already working)
- JPEG encoding with quality control

### Frontend
- Simple `<img>` element with periodic refresh
- No complex connection management
- No Socket.IO dependency for video

---

## 📝 Implementation Steps

### Phase 1: Backend Cleanup (30 min)

**Step 1.1: Remove WebSocket Video Init**
```python
# In rest_api.py

# DELETE METHOD:
def _init_websocket_video_streaming(self):
    # ... entire method ...

# DELETE CALL in __init__():
self._init_websocket_video_streaming()
```

**Step 1.2: Delete api_websocket.py**
```bash
rm src/modules/api_websocket.py
```

**Step 1.3: Remove WebSocket Import**
```python
# In rest_api.py
# DELETE:
from .api_websocket import init_websocket_streaming
```

**Step 1.4: Update Config Schema**
```python
# In config_schema.py
# Remove 'websocket_streaming' from DEFAULT_CONFIG
# Remove validation for websocket_streaming section
```

---

### Phase 2: Frontend Cleanup (45 min)

**Step 2.1: Delete WebSocket/WebRTC Files**
```bash
rm frontend/js/websocket-preview.js
rm frontend/js/webrtc-preview.js
```

**Step 2.2: Simplify player.js**

Remove:
```javascript
// DELETE THESE:
let websocketPreview = null;
let previewUseWebSocket = true;

function startPreviewStream() {
    // Complex WebSocket/MJPEG fallback logic
}

function updatePreviewModeButton() {
    // Preview mode indicator
}
```

Replace with:
```javascript
function startPreviewStream() {
    const previewImg = document.getElementById('videoPreviewImg');
    previewImg.style.display = 'block';
    previewImg.src = `${API_BASE}/preview?t=${Date.now()}`;
    
    // Refresh preview every 100ms
    if (window.previewRefreshInterval) {
        clearInterval(window.previewRefreshInterval);
    }
    window.previewRefreshInterval = setInterval(() => {
        if (document.getElementById('videoPreviewImg')) {
            previewImg.src = `${API_BASE}/preview?t=${Date.now()}`;
        }
    }, 100);
}

function stopPreviewStream() {
    if (window.previewRefreshInterval) {
        clearInterval(window.previewRefreshInterval);
        window.previewRefreshInterval = null;
    }
}
```

**Step 2.3: Simplify player.html**

Remove:
```html
<!-- DELETE THESE: -->
<script src="js/websocket-preview.js"></script>
<script src="js/webrtc-preview.js"></script>

<canvas id="videoPreviewVideo" style="display:none;"></canvas>
```

Keep only:
```html
<img id="videoPreviewImg" class="video-preview-img" />
```

**Step 2.4: Clean up common.js**

Remove:
```javascript
// DELETE:
const videoSocket = io('/video', {
    transports: ['polling', 'websocket'],
    upgrade: true,
    rememberUpgrade: true
});
```

Keep only:
- Main socket (`/`)
- Player socket (`/player`)
- Effects socket (`/effects`)
- Layers socket (`/layers`)

---

### Phase 3: Configuration Cleanup (15 min)

**Step 3.1: Simplify config.json**

Remove:
```json
"websocket_streaming": {
    "enabled": true,
    "default_quality": "medium",
    "max_fps": 30,
    "max_concurrent_streams": 10,
    "max_frame_size_kb": 200,
    "skip_frame_threshold": 50,
    "quality_auto_adjust": true
}
```

Keep only:
```json
"video": {
    "preview_quality": 85,
    "preview_scale": [640, 480],
    "preview_fps": 30
}
```

**Step 3.2: Update DEFAULT_CONFIG in config_schema.py**

Remove `websocket_streaming` section validation.

---

### Phase 4: Testing & Validation (30 min)

**Test Cases:**

1. ✅ **Basic Preview**
   - Open player.html
   - Load a video
   - Verify preview appears in `<img>` element
   - Check smooth refresh at ~10 FPS

2. ✅ **Quality Settings**
   - Test preview quality selector (if exists)
   - Verify JPEG quality changes

3. ✅ **Multiple Browsers**
   - Open 2-3 browser tabs
   - Verify all show preview without connection conflicts

4. ✅ **No WebSocket Errors**
   - Check browser console for errors
   - Check backend logs for errors
   - Verify no `/video` namespace errors

5. ✅ **Resource Usage**
   - Monitor backend CPU/memory
   - Should be lower than before (no threading, no Socket.IO overhead)

---

## 🎁 Benefits of MJPEG-Only

### Stability
- ✅ No WebSocket connection management
- ✅ No reconnection logic needed
- ✅ No frame buffering issues
- ✅ Simple HTTP requests (stateless)

### Performance
- ✅ Lower backend CPU (no frame encoding threads)
- ✅ Lower memory (no frame buffers)
- ✅ Simpler code = fewer bugs

### Simplicity
- ✅ ~1000 lines of code removed
- ✅ Fewer dependencies (no Socket.IO for video)
- ✅ Easier to maintain
- ✅ Faster debugging

### Network
- ✅ Works with any HTTP proxy
- ✅ No special WebSocket routing needed
- ✅ LAN bandwidth is sufficient (no need for WebSocket efficiency)

---

## 📉 Tradeoffs (Accepted)

### Lower FPS
- WebSocket: 30 FPS possible
- MJPEG: ~10 FPS typical
- **Acceptable**: Preview only, not critical path

### Higher Bandwidth
- WebSocket: Compressed, efficient
- MJPEG: Each frame = full JPEG
- **Acceptable**: LAN environment, bandwidth not constrained

### No Frame Sync
- WebSocket: Can sync with player frame counter
- MJPEG: Periodic polling, slight lag
- **Acceptable**: Preview accuracy not critical

---

## 🚀 Rollout Strategy

### Step 1: Backup Current State
```bash
git checkout -b backup/before-mjpeg-migration
git commit -am "Backup before MJPEG migration"
git checkout main
```

### Step 2: Implement Changes
Follow Phase 1-3 steps above in order.

### Step 3: Test Locally
Run all test cases from Phase 4.

### Step 4: Commit
```bash
git add -A
git commit -m "refactor: migrate to MJPEG-only preview, remove WebSocket video

REMOVED:
- api_websocket.py (334 lines)
- websocket-preview.js (408 lines)
- webrtc-preview.js (~400 lines)
- WebSocket /video namespace
- Complex fallback logic

SIMPLIFIED:
- player.js preview to simple <img> refresh
- Removed Socket.IO video dependency
- Cleaned config.json (no websocket_streaming)

BENEFITS:
- ~1000 lines removed
- Lower CPU/memory usage
- Simpler architecture
- More stable (no connection issues)
- MJPEG sufficient for LAN preview"
```

### Step 5: Deploy & Monitor
- Deploy to production
- Monitor for 24h
- Check for any preview-related errors
- Verify resource usage improvement

---

## 🔄 Rollback Plan

If issues arise:

```bash
git checkout backup/before-mjpeg-migration
git checkout -b fix/mjpeg-issues
# Debug and fix issues
```

Or revert commit:
```bash
git revert HEAD
git commit -m "Revert MJPEG migration due to [issue]"
```

---

## 📋 Checklist

### Pre-Implementation
- [ ] Review current WebSocket usage across codebase
- [ ] Create backup branch
- [ ] Document current behavior (screenshots/videos)

### Backend
- [ ] Remove `_init_websocket_video_streaming()` from rest_api.py
- [ ] Delete `api_websocket.py`
- [ ] Remove imports
- [ ] Update config_schema.py

### Frontend
- [ ] Delete `websocket-preview.js`
- [ ] Delete `webrtc-preview.js`
- [ ] Simplify `player.js` preview functions
- [ ] Update `player.html` (remove scripts/canvas)
- [ ] Clean up `common.js` socket connections

### Config
- [ ] Remove `websocket_streaming` from config.json
- [ ] Update schema validation

### Testing
- [ ] Basic preview works
- [ ] Multiple tabs work
- [ ] No console errors
- [ ] No backend errors
- [ ] Resource usage improved

### Deployment
- [ ] Commit changes
- [ ] Push to repository
- [ ] Deploy to production
- [ ] Monitor for 24h

---

## 📚 References

- **MJPEG Endpoints**: `src/modules/api_routes.py` lines 378-550
- **WebSocket Code**: `src/modules/api_websocket.py` (entire file)
- **Frontend Preview**: `frontend/js/player.js` lines 1234-1300
- **Socket.IO Docs**: https://socket.io/docs/v4/

---

**Estimated Total Time:** 2 hours  
**Risk Level:** Low (MJPEG already working, just removing extras)  
**Impact:** Positive (simpler, more stable, less resource usage)
