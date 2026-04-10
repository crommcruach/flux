# Preview Pull Model — On-Demand GPU Download via Compute Shader SSBO

## Discovery: SSBO Readback Bypasses the AMD 50ms Stall

Benchmark `tests/gpu/test_amd_ssbo_vs_texture_read.py` confirmed:

| Method | Mean | Min |
|---|---|---|
| `texture.read()` 1080p (old path) | 111 ms | 90 ms |
| **SSBO compute+read 1080p** | **21 ms** | **11 ms** |
| **SSBO compute+read 640×360** | **10 ms** | **2 ms** |

`glGetBufferSubData` does NOT trigger the AMD pipeline drain stall that `glGetTexImage` does.
This means **the compute shader SSBO path is the correct universal download strategy**, not
just a workaround for small ArtNet pixel reads.

On a discrete GPU all times drop to < 1 ms. See `AMD_DRIVER_BUGS.md` for full analysis.

---

## Current State (before this change)

The MJPEG streaming is already a loose pull model — the Flask generator in
`src/modules/api/output/artnet.py` (line 262) reads from `VirtualOutput.latest_frame`
at its own rate (25fps by default). The browser pulls MJPEG chunks natively via
`<img src="/api/outputs/video/stream/preview_virtual?fps=25&quality=85">`.

**The problem:** The GPU→CPU download (`composite.download()` which calls `texture.read()`)
happens **unconditionally on every rendered frame** regardless of whether anyone is
watching. On this AMD iGPU that's 111ms per download = render throughput completely
limited by preview whether or not anyone is watching.

### Current data path:
```
composite_layers() — always:
  → composite.download()          ← texture.read() → 111ms AMD stall, EVERY frame
  → numpy BGR returned
      → core.py: self.last_video_frame = frame
      → OutputManager → VirtualOutput.latest_frame = frame

Flask MJPEG generator (runs in Flask worker thread, 25fps):
  → output.get_latest_frame()     ← reads latest_frame reference
  → cv2.imencode('.jpg', frame)
  → yield MJPEG chunk → browser
```

---

## Target Architecture

### Preferred: Compute Shader SSBO preview + subscriber-gated dispatch

```
composite_layers() — GPU composite texture stays on GPU
  → if preview_active:
      dispatch preview_copy.comp shader:
        float32 texture 1920×1080 → downsample → 640×360 packed RGB SSBO
      ssbo.read()                 ← glGetBufferSubData, ~10ms, NO AMD stall
      np.frombuffer → reshape → BGR → VirtualOutput.latest_frame
  → if artnet_active:
      ArtNetGPUSampler.sample()   ← already implemented, same SSBO pattern
  → composite.download() only needed for CPU effects mid-chain
    (replace with SSBO path in GPUFrame.download() too — future)
```

Result on AMD iGPU:
- **Nobody watching**: 0 dispatches, 0 SSBO reads
- **Preview at 25fps**: ~10ms per frame for 640×360 SSBO read (fits in 33ms budget)
- **Preview at 30fps full 1080**: ~21ms per frame
- **Discrete GPU**: < 1ms regardless of resolution

### Fallback: Subscriber-gated download (if SSBO path not yet implemented)

```
Flask MJPEG generator:
  → subscriber connects:   player.preview_subscriber_count += 1
  → subscriber disconnects: player.preview_subscriber_count -= 1

composite_layers() — conditional:
  if preview_active OR artnet_outputs_active:
      → composite.download()    ← only when actually needed
      → return numpy frame
  else:
      → return None             ← render loop skips distribution
```

Result:
- **Nobody watching**: 0 downloads, 0 AMD stalls
- **1 browser at 25fps**: render loop downloads only on frames the subscriber is alive
- **Preview disabled via UI**: 0 downloads regardless of browser state
- **ArtNet active without preview**: only needed for ArtNet routing (future: compute shader sampler replaces this too)

---

## Files To Change

### 1. `src/modules/player/core.py` — add `preview_active` property

Add to `Player.__init__()`:
```python
self._preview_subscriber_count: int = 0   # incremented by MJPEG generator on connect
self._preview_enabled: bool = True         # user toggle from UI
```

Add property:
```python
@property
def preview_active(self) -> bool:
    return self._preview_enabled and self._preview_subscriber_count > 0
```

In the render loop (around line 1450), gate the output distribution:
```python
# Before (always distributes):
self.last_video_frame = frame
if self.output_manager:
    self.output_manager.update_frame(frame, ...)

# After (only distributes when needed):
if frame is not None:
    self.last_video_frame = frame
    if self.output_manager and (self.preview_active or self.output_manager.has_active_artnet_outputs()):
        self.output_manager.update_frame(frame, ...)
```

### 2. `src/modules/api/output/artnet.py` — subscriber tracking in MJPEG generator

Current `generate_frames()` (line ~288) is a plain generator with no connect/disconnect hook.
Change to track lifetime using try/finally:

```python
@app.route('/api/outputs/<player_id>/stream/<output_id>')
def stream_output(player_id, output_id):
    player = get_player(player_id)
    fps = float(request.args.get('fps', 25))
    jpeg_quality = int(request.args.get('quality', 85))
    max_width = int(request.args.get('max_width', 640))
    frame_delay = 1.0 / fps

    def generate_frames():
        if player:
            player._preview_subscriber_count += 1
        try:
            while True:
                if not player or not player._preview_enabled:
                    # Preview disabled — serve a black frame or placeholder
                    time.sleep(0.5)
                    continue
                output = player.output_manager.outputs.get(output_id)
                if output is None:
                    time.sleep(0.1)
                    continue
                frame = output.get_latest_frame()
                if frame is None:
                    time.sleep(frame_delay)
                    continue
                if max_width > 0 and frame.shape[1] > max_width:
                    scale = max_width / frame.shape[1]
                    frame = cv2.resize(frame, (max_width, int(frame.shape[0] * scale)))
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if ret:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                           + buffer.tobytes() + b'\r\n')
                time.sleep(frame_delay)
        finally:
            if player:
                player._preview_subscriber_count = max(0, player._preview_subscriber_count - 1)

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
```

Same pattern applies to `/api/outputs/<player_id>/stream/preview_live` (line 350) and
`/api/preview/stream` (line 438).

### 3. New API endpoint — `src/modules/api/output/artnet.py`

Add toggle endpoint (near line 754 where debug endpoints are):

```python
@app.route('/api/preview/toggle', methods=['POST'])
def toggle_preview():
    player_id = request.json.get('player_id', 'video')
    player = get_player(player_id)
    if not player:
        return jsonify({'error': 'player not found'}), 404
    player._preview_enabled = not player._preview_enabled
    # Persist to session_state
    state = get_session_state()
    state.setdefault('video', {})['preview_enabled'] = player._preview_enabled
    save_session_state(state)
    return jsonify({'preview_enabled': player._preview_enabled})

@app.route('/api/preview/status', methods=['GET'])
def preview_status():
    player_id = request.args.get('player_id', 'video')
    player = get_player(player_id)
    if not player:
        return jsonify({'error': 'player not found'}), 404
    return jsonify({
        'preview_enabled': player._preview_enabled,
        'subscriber_count': player._preview_subscriber_count,
        'preview_active': player.preview_active,
    })
```

On player startup, restore `_preview_enabled` from session_state:
```python
# core.py __init__:
state = get_session_state()
self._preview_enabled = state.get('video', {}).get('preview_enabled', True)
```

### 4. `session_state.json` — add key

```json
"video": {
    "preview_enabled": true,    ← add this key
    "preview_fps_limit": 30,
    ...
}
```

### 5. Frontend — context menu on preview image

**`frontend/player.html`** — add context menu element (near line 136):

```html
<!-- existing preview container -->
<div class="preview-video" id="videoPreview" onclick="openVideoFullscreen()">
    <img src="" alt="Video Preview" id="videoPreviewImg" ...>
</div>

<!-- context menu (hidden by default) -->
<div id="previewContextMenu" class="context-menu" style="display:none; position:fixed; z-index:9999;">
    <div class="context-menu-item" id="previewToggleItem" onclick="togglePreview()">
        Disable Preview
    </div>
    <div class="context-menu-item" onclick="openVideoFullscreen(); hidePreviewContextMenu()">
        Fullscreen
    </div>
</div>
```

**`frontend/js/player.js`** — wire up right-click and toggle (near line 97):

```javascript
// Context menu setup
document.addEventListener('DOMContentLoaded', () => {
    const previewContainer = document.getElementById('videoPreview');
    const menu = document.getElementById('previewContextMenu');

    previewContainer.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        menu.style.display = 'block';
        menu.style.left = e.clientX + 'px';
        menu.style.top  = e.clientY + 'px';
        updatePreviewMenuLabel();
    });

    document.addEventListener('click', hidePreviewContextMenu);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hidePreviewContextMenu(); });
});

function hidePreviewContextMenu() {
    const menu = document.getElementById('previewContextMenu');
    if (menu) menu.style.display = 'none';
}

let _previewEnabled = true;

async function updatePreviewMenuLabel() {
    const res = await fetch(`${API_BASE}/api/preview/status?player_id=video`);
    const data = await res.json();
    _previewEnabled = data.preview_enabled;
    const item = document.getElementById('previewToggleItem');
    if (item) item.textContent = _previewEnabled ? 'Disable Preview' : 'Enable Preview';
    // Grey out the <img> when disabled
    const img = document.getElementById('videoPreviewImg');
    if (img) img.style.opacity = _previewEnabled ? '1' : '0.3';
}

async function togglePreview() {
    hidePreviewContextMenu();
    await fetch(`${API_BASE}/api/preview/toggle`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({player_id: 'video'})
    });
    await updatePreviewMenuLabel();
}
```

**`frontend/css/player.css`** (or inline) — context menu styling:

```css
.context-menu {
    background: #1e1e1e;
    border: 1px solid #444;
    border-radius: 4px;
    box-shadow: 2px 2px 8px rgba(0,0,0,0.5);
    min-width: 160px;
    padding: 4px 0;
}
.context-menu-item {
    padding: 8px 16px;
    cursor: pointer;
    color: #ddd;
    font-size: 13px;
}
.context-menu-item:hover {
    background: #333;
    color: #fff;
}
```

---

## Performance Impact

| Scenario | Current | After |
|---|---|---|
| No browser tab open | 30 × 50ms = **1500ms stall/sec** | **0ms** |
| Preview disabled via UI | 30 × 50ms = 1500ms stall/sec | **0ms** |
| 1 browser at 25fps | 30 × 50ms = 1500ms | 25 × 50ms = **1250ms** |
| 1 browser at 10fps (throttled) | 1500ms | 10 × 50ms = **500ms** |
| ArtNet output only (no browser) | 1500ms | 0ms (future: compute shader) |

On **discrete GPU** the 50ms becomes ~2ms, making preview cost negligible regardless.

---

## Threading Note

`composite.download()` runs on the GL render thread (it owns the GL context).
`VirtualOutput.latest_frame` is a memory buffer read by the Flask MJPEG thread.
The subscriber counter is a plain `int` — reads/writes on CPython are GIL-protected
and the counter only needs to reach 0 vs >0, so no lock is needed.

---

## Implementation Checklist

- [ ] Add `_preview_subscriber_count` and `_preview_enabled` to `Player.__init__()` in `core.py`
- [ ] Add `preview_active` property and gate `output_manager.update_frame()` in render loop
- [ ] Wrap `generate_frames()` in MJPEG endpoints with try/finally subscriber counter in `artnet.py`  
- [ ] Add `POST /api/preview/toggle` and `GET /api/preview/status` endpoints
- [ ] Persist `preview_enabled` to `session_state.json`, restore on startup
- [ ] Add right-click context menu to `#videoPreview` in `player.html`
- [ ] Add `togglePreview()` JS function in `player.js`
- [ ] Add context menu CSS to `player.css`
- [ ] Test: no browser → measure frame time (should drop by ~50ms vs current)
- [ ] Test: disable via UI → frame renders but no download cost
- [ ] Test: re-enable → preview resumes within 1 frame
