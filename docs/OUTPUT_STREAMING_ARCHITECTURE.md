# Output Streaming Architecture

## Current Implementation Analysis

### Existing Streaming Endpoints

The current system has **hardcoded** streaming endpoints for specific players:

1. **`/api/preview/stream`** - Video Player stream
   - Reads `player_manager.player.last_video_frame`
   - MJPEG stream format
   - FPS: configurable (default 30)
   - JPEG quality: configurable (default 85)
   - Max width scaling: configurable (default 640)

2. **`/api/preview/artnet/stream`** - ArtNet Player stream
   - Reads `player_manager.artnet_player.last_video_frame`
   - Same MJPEG format
   - Separate FPS/quality config

### Current Architecture Limitations

❌ **Hardcoded Player References**
```python
# Current implementation
player = player_manager.player  # Hardcoded to "video" player
player = player_manager.artnet_player  # Hardcoded to "artnet" player
```

❌ **Duplicate Code**
- Two nearly identical streaming functions
- Same frame encoding logic repeated
- Same error handling duplicated

❌ **Not Output-System Aware**
- Streams read directly from player objects
- No integration with `OutputManager`
- Can't stream arbitrary outputs

❌ **No Dynamic Output Streaming**
- Can't stream a virtual output
- Can't stream a preview output
- Can't stream NDI/SDI outputs for web preview

---

## Proposed Architecture: Generalized Output Streaming

### Core Concept

**Any output can be streamed via a unified API endpoint:**

```
/api/outputs/<player_id>/stream/<output_id>
```

**Examples:**
```
GET /api/outputs/video/stream/main_display    → Stream main display output
GET /api/outputs/video/stream/preview_1       → Stream preview output
GET /api/outputs/video/stream/virtual_record  → Stream virtual output (recording preview)
GET /api/outputs/artnet/stream/artnet_preview → Stream ArtNet player preview
```

---

## Implementation Design

### 1. Output Frame Capture Interface

Add frame capture capability to `OutputBase`:

```python
# src/modules/outputs/output_base.py

class OutputBase(ABC):
    def __init__(self, output_id: str, config: dict):
        # ... existing code ...
        
        # Frame capture for streaming
        self.latest_frame = None
        self.latest_frame_lock = threading.Lock()
        self.capture_enabled = config.get('enable_capture', False)
    
    def queue_frame(self, frame: np.ndarray):
        """Queue frame for output (thread-safe, non-blocking)"""
        if not self.enabled:
            return
        
        # Capture latest frame if enabled
        if self.capture_enabled:
            with self.latest_frame_lock:
                self.latest_frame = frame.copy()
        
        # ... existing queue logic ...
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """Get latest frame for streaming (thread-safe)"""
        with self.latest_frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None
```

**Key Features:**
- ✅ Optional per-output (avoid memory overhead for non-streamed outputs)
- ✅ Thread-safe frame capture
- ✅ Returns copy to avoid race conditions
- ✅ Works with all output types (Display, Virtual, Preview, NDI, etc.)

---

### 2. Unified Streaming Endpoint

Replace hardcoded endpoints with single generalized endpoint:

```python
# src/modules/api_routes.py

@app.route('/api/outputs/<player_id>/stream/<output_id>')
def stream_output(player_id, output_id):
    """
    MJPEG stream for any output
    
    Args:
        player_id: Player identifier (video, artnet, etc.)
        output_id: Output identifier from OutputManager
    
    Query Parameters:
        fps: Stream FPS (default: 30)
        quality: JPEG quality 0-100 (default: 85)
        max_width: Max width scaling (default: 640, 0=no scaling)
    """
    from flask import Response, request
    import cv2
    import time
    
    # Get parameters
    stream_fps = int(request.args.get('fps', 30))
    jpeg_quality = int(request.args.get('quality', 85))
    max_width = int(request.args.get('max_width', 640))
    frame_delay = 1.0 / stream_fps
    
    def generate_frames():
        """Generator for MJPEG stream"""
        while True:
            try:
                # Get player
                player = player_manager.get_player(player_id)
                if not player or not player.output_manager:
                    # Black frame if player not found
                    frame = np.zeros((180, 320, 3), dtype=np.uint8)
                else:
                    # Get output
                    output = player.output_manager.outputs.get(output_id)
                    if not output or not output.enabled:
                        # Black frame if output not found/disabled
                        frame = np.zeros((180, 320, 3), dtype=np.uint8)
                    else:
                        # Get latest frame from output
                        frame = output.get_latest_frame()
                        if frame is None:
                            # Black frame if no frame available yet
                            frame = np.zeros((180, 320, 3), dtype=np.uint8)
                
                # Scale if needed
                if max_width > 0 and frame.shape[1] > max_width:
                    scale = max_width / frame.shape[1]
                    new_width = int(frame.shape[1] * scale)
                    new_height = int(frame.shape[0] * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Encode as JPEG
                ret, buffer = cv2.imencode('.jpg', frame, 
                                          [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
                if not ret:
                    time.sleep(frame_delay)
                    continue
                
                frame_bytes = buffer.tobytes()
                
                # MJPEG format
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       frame_bytes + b'\r\n')
                
                time.sleep(frame_delay)
            
            except Exception as e:
                logger.error(f"Stream error for {player_id}/{output_id}: {e}")
                time.sleep(0.1)
    
    return Response(generate_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')
```

---

### 3. Output Configuration for Streaming

Enable streaming per output in config/session state:

```json
{
  "outputs": [
    {
      "id": "main_display",
      "type": "display",
      "resolution": [1920, 1080],
      "enable_capture": true,  // ← Enable frame capture for streaming
      "source": "canvas"
    },
    {
      "id": "preview_1",
      "type": "virtual",
      "resolution": [640, 360],
      "enable_capture": true,  // ← Enable for web preview
      "source": "layer:0"
    },
    {
      "id": "recording",
      "type": "virtual",
      "resolution": [1920, 1080],
      "enable_capture": false,  // ← Disable to save memory (recording doesn't need streaming)
      "source": "canvas"
    }
  ]
}
```

**Benefits:**
- ✅ Opt-in per output (no overhead for outputs that don't need streaming)
- ✅ Flexible: enable/disable dynamically
- ✅ Memory efficient: only capture frames for streamed outputs

---

### 4. Frontend Integration

Update frontend to use new generalized endpoint:

```javascript
// frontend/js/player.js

function startVideoPreview() {
    const previewImg = document.getElementById('videoPreviewImg');
    if (!previewImg) return;
    
    // NEW: Use output-based streaming endpoint
    const playerId = 'video';
    const outputId = 'main_display';  // Or 'preview_1', 'virtual_record', etc.
    
    previewImg.src = `${API_BASE}/api/outputs/${playerId}/stream/${outputId}?fps=25&quality=85`;
    previewImg.style.display = 'block';
}

function startArtNetPreview() {
    const previewImg = document.getElementById('artnetPreviewImg');
    if (!previewImg) return;
    
    // NEW: Use output-based streaming endpoint
    const playerId = 'artnet';
    const outputId = 'artnet_preview';
    
    previewImg.src = `${API_BASE}/api/outputs/${playerId}/stream/${outputId}?fps=25&quality=85`;
    previewImg.style.display = 'block';
}
```

---

### 5. Backwards Compatibility

Keep legacy endpoints as redirects:

```python
# src/modules/api_routes.py

@app.route('/api/preview/stream')
def preview_stream_legacy():
    """Legacy endpoint - redirect to output-based stream"""
    from flask import redirect
    # Default to 'video' player, 'main_display' output
    return redirect(f'/api/outputs/video/stream/main_display', code=307)

@app.route('/api/preview/artnet/stream')
def preview_artnet_stream_legacy():
    """Legacy endpoint - redirect to output-based stream"""
    from flask import redirect
    # Default to 'artnet' player, 'artnet_preview' output
    return redirect(f'/api/outputs/artnet/stream/artnet_preview', code=307)
```

**Benefits:**
- ✅ Existing frontends keep working
- ✅ Clean migration path
- ✅ Can remove legacy endpoints later

---

## Benefits of Generalized Architecture

### ✅ Flexibility
- Stream **any** output (display, virtual, preview, NDI, etc.)
- No code changes needed to add new output types
- Dynamic output creation → automatic streaming capability

### ✅ Clean Code
- Single streaming implementation (no duplication)
- Consistent API pattern
- Easier to maintain and extend

### ✅ Multi-Output Support
- Frontend can display multiple preview streams
- Preview panels for different layers/clips
- Side-by-side comparison of outputs

### ✅ Performance Control
- Opt-in frame capture per output
- No overhead for non-streamed outputs
- Configurable FPS/quality per stream

### ✅ Future-Proof
- Works with upcoming multi-output architecture
- Supports preview output type (from NON_ACTIVE_PLAYLIST_PREVIEW.md)
- Compatible with output routing system

---

## Implementation Phases

### Phase 1: Add Frame Capture to OutputBase (2-3h)
- Add `latest_frame` storage with lock
- Add `enable_capture` config flag
- Implement `get_latest_frame()` method
- Update `queue_frame()` to capture when enabled

**Test:** Virtual output can capture frames

### Phase 2: Implement Unified Streaming Endpoint (3-4h)
- Create `/api/outputs/<player>/<output>/stream` endpoint
- Implement MJPEG generator with output frame retrieval
- Add query parameters (fps, quality, max_width)
- Error handling (output not found, no frames, etc.)

**Test:** Can stream a virtual output via new endpoint

### Phase 3: Update Frontend (2-3h)
- Update `player.js` to use new endpoint
- Add output selector (dropdown to switch between outputs)
- Update preview panels to use dynamic endpoints

**Test:** Frontend displays streams from new endpoint

### Phase 4: Add Legacy Redirects (1h)
- Implement redirect endpoints
- Test backwards compatibility
- Document migration path

**Test:** Old URLs still work

### Phase 5: Documentation & Testing (2h)
- Update API documentation
- Add streaming examples
- Performance testing (multiple concurrent streams)

**Total Estimate: 10-13 hours**

---

## Configuration Examples

### Stream Main Display
```javascript
// 25 FPS, high quality, scaled to 1280px width
fetch('/api/outputs/video/stream/main_display?fps=25&quality=95&max_width=1280')
```

### Stream Preview Output (Low Quality for Monitoring)
```javascript
// 10 FPS, low quality, scaled to 320px width
fetch('/api/outputs/video/stream/preview_1?fps=10&quality=60&max_width=320')
```

### Stream Virtual Recording Output
```javascript
// Full resolution preview of what's being recorded
fetch('/api/outputs/video/stream/recording_virtual?fps=15&quality=80&max_width=0')
```

---

## Integration with MULTI_OUTPUT_ARCHITECTURE.md

This streaming architecture integrates seamlessly with the planned multi-output system:

1. **Output Manager** already has frame distribution logic
2. **OutputBase** provides unified interface for all outputs
3. **Source Routing** (canvas/layer/clip) determines what each output receives
4. **Streaming** is just another consumer of output frames

**No architectural conflicts** - this is a complementary feature that leverages the planned architecture.

---

## Security Considerations

### Access Control
- Add authentication to streaming endpoints
- Limit concurrent streams per user
- Rate limiting per IP

### Resource Protection
```python
# Global stream limiter
MAX_CONCURRENT_STREAMS = 10
active_streams = {}

@app.route('/api/outputs/<player_id>/stream/<output_id>')
def stream_output(player_id, output_id):
    # Check stream limit
    if len(active_streams) >= MAX_CONCURRENT_STREAMS:
        return jsonify({'error': 'Too many active streams'}), 429
    
    # Register stream
    stream_id = f"{player_id}:{output_id}"
    active_streams[stream_id] = time.time()
    
    try:
        # ... generate frames ...
    finally:
        # Cleanup on disconnect
        active_streams.pop(stream_id, None)
```

---

## Performance Optimization

### Memory Efficiency
- Only capture frames for outputs with `enable_capture=true`
- Use `numpy` views where possible (no copy if not needed)
- Limit frame queue depth (already 2 frames max)

### CPU Efficiency
- JPEG encoding only happens once per stream (not per output)
- Scaling happens in stream generator (not in output queue)
- Frame delay prevents CPU spinning

### Network Efficiency
- Configurable FPS (lower for monitoring views)
- Configurable JPEG quality (lower for thumbnails)
- Scaling reduces bandwidth (max_width parameter)

---

## API Reference

### GET /api/outputs/{player_id}/stream/{output_id}

**Description:** MJPEG video stream of specified output

**Path Parameters:**
- `player_id` (string): Player identifier (e.g., "video", "artnet")
- `output_id` (string): Output identifier from OutputManager

**Query Parameters:**
- `fps` (integer, optional): Stream frame rate (default: 30)
- `quality` (integer, optional): JPEG quality 0-100 (default: 85)
- `max_width` (integer, optional): Max width in pixels, 0=no scaling (default: 640)

**Response:**
- Content-Type: `multipart/x-mixed-replace; boundary=frame`
- Body: MJPEG stream (continuous JPEG frames)

**Example Usage:**
```html
<img id="outputPreview" 
     src="/api/outputs/video/stream/main_display?fps=25&quality=85&max_width=800">
```

**Error Handling:**
- Player not found → Black frame
- Output not found → Black frame
- Output disabled → Black frame
- No frames available → Black frame

---

## Next Steps

1. **Review this design** with team
2. **Decide on implementation priority** (vs other architecture work)
3. **Consider integration timing** with MULTI_OUTPUT_ARCHITECTURE.md refactor
4. **Evaluate if streaming should be part of Phase 1 (Output Manager Core)** or separate phase

---

## Cluster Architecture Considerations

### Integration with Multi-Video Render Cluster

The streaming architecture must consider future cluster deployment where multiple nodes render the same content.

**Cluster Context (from MULTI_VIDEO_RENDER_CLUSTER.md):**
- **Command Replication** - Nodes receive commands, not frames
- **Zero Frame Streaming** - No video data transfer between nodes
- **Distributed Outputs** - Each slave node has its own physical outputs
- **Master/Slave Topology** - One control node, many render nodes

### Streaming in Cluster Mode

**Two Streaming Scenarios:**

#### 1. Local Output Streaming (Per-Node)
Each node streams its own outputs for monitoring:

```
Master Node:
  └─ Stream: /api/outputs/video/stream/master_output_1

Slave Node 1:
  └─ Stream: /api/outputs/video/stream/slave1_output_1

Slave Node 2:
  └─ Stream: /api/outputs/video/stream/slave2_output_1
```

**Use Case:** Monitor all node outputs from central control room

**Implementation:**
- Each node runs independent streaming endpoints
- Master UI displays grid of all node streams
- Frontend loads streams via direct node IPs

```javascript
// Master UI showing all cluster outputs
const nodes = [
    {id: 'master', ip: '192.168.1.100'},
    {id: 'slave1', ip: '192.168.1.101'},
    {id: 'slave2', ip: '192.168.1.102'}
];

nodes.forEach(node => {
    const img = document.createElement('img');
    img.src = `http://${node.ip}:5000/api/outputs/video/stream/output_1?fps=10&quality=70`;
    monitorGrid.appendChild(img);
});
```

#### 2. Master-Only Streaming (Simplified)
Only master provides preview streams (slaves have no web access):

```
Master Node:
  ├─ Full output streaming
  └─ Represents cluster state (all slaves identical)

Slave Nodes:
  └─ No streaming endpoints (render-only mode)
```

**Use Case:** Locked-down production networks, simplified slave nodes

**Implementation:**
- Slaves run with `--no-webserver` flag
- Only master has HTTP/WebSocket endpoints
- Master preview represents entire cluster (deterministic rendering)

### Architecture Alignment

**✅ Compatible Design Choices:**

1. **Output-Based Endpoint Pattern**
   - `/api/outputs/{player}/{output}` works per-node
   - Each slave is independent cluster member
   - No cross-node dependencies

2. **Frame Capture Per Output**
   - `enable_capture` flag controls overhead
   - Slaves can disable capture to save resources
   - Master enables for monitoring

3. **No Shared State Assumption**
   - Streaming doesn't require cluster coordination
   - Each node streams independently
   - No synchronization needed (monitoring only)

**⚠️ Design Considerations:**

1. **Network Bandwidth**
   - Multiple nodes streaming simultaneously
   - 10 nodes × 30 FPS × 50KB = 15 MB/s total
   - Solution: Lower FPS/quality for monitoring (10 FPS, quality 60)

2. **Firewall Configuration**
   - Cluster uses WebSocket for commands (/cluster/*)
   - Streaming uses HTTP (/api/outputs/*/stream/*)
   - Must allow both protocols

3. **Node Discovery**
   - Master needs to know slave IPs for monitoring grid
   - Could use cluster connection state
   - Slaves register outputs on connect

### Future Enhancement: Cluster Monitoring Dashboard

**Centralized Monitoring UI on Master:**

```
┌─────────────────────────────────────────────────────────┐
│ Cluster Monitoring Dashboard                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Master (192.168.1.100)         Slave 1 (192.168.1.101) │
│  ┌────────────────────┐         ┌────────────────────┐  │
│  │   Output: main     │         │   Output: led_1    │  │
│  │   [Live Preview]   │         │   [Live Preview]   │  │
│  │   Status: ✅ Active │         │   Status: ✅ Active │  │
│  └────────────────────┘         └────────────────────┘  │
│                                                          │
│  Slave 2 (192.168.1.102)        Slave 3 (192.168.1.103) │
│  ┌────────────────────┐         ┌────────────────────┐  │
│  │   Output: led_2    │         │   Output: led_3    │  │
│  │   [Live Preview]   │         │   [Live Preview]   │  │
│  │   Status: ✅ Active │         │   Status: ⚠️ Lag 50ms│  │
│  └────────────────────┘         └────────────────────┘  │
│                                                          │
│  Network: 2.1 MB/s │ Sync: ±8ms │ Uptime: 4h 23m      │
└─────────────────────────────────────────────────────────┘
```

**Implementation Plan (Future Phase):**
- Master maintains cluster topology (from `/cluster` WebSocket)
- Frontend queries each node for output list
- Grid layout with live stream per output
- Color-coded status (sync quality, lag warnings)

### Streaming Performance in Cluster

**Bandwidth Requirements:**

| Scenario | Nodes | Outputs/Node | FPS | Quality | Bandwidth per Node | Total |
|----------|-------|--------------|-----|---------|-------------------|-------|
| Monitoring | 10 | 1 | 10 | 60 | 150 KB/s | 1.5 MB/s |
| High Quality | 10 | 1 | 25 | 85 | 500 KB/s | 5 MB/s |
| Multi-Output | 10 | 4 | 10 | 60 | 600 KB/s | 6 MB/s |
| Production | 50 | 2 | 10 | 60 | 300 KB/s | 15 MB/s |

**Recommendations:**
- Monitoring streams: 10 FPS, quality 60, max_width 480
- Production: Only enable capture on nodes that need monitoring
- Control room: Dedicated monitoring network (separate from command network)

---

## References

- [MULTI_OUTPUT_ARCHITECTURE.md](MULTI_OUTPUT_ARCHITECTURE.md) - Multi-output system design
- [NON_ACTIVE_PLAYLIST_PREVIEW.md](NON_ACTIVE_PLAYLIST_PREVIEW.md) - Preview system implementation
- [OUTPUT_BACKEND_IMPLEMENTATION_PLAN.md](OUTPUT_BACKEND_IMPLEMENTATION_PLAN.md) - Output system details
- [MULTI_VIDEO_RENDER_CLUSTER.md](MULTI_VIDEO_RENDER_CLUSTER.md) - Distributed rendering architecture

---

**Status:** ✅ Design Complete - Ready for Review  
**Estimated Implementation Time:** 10-13 hours (base) + 6-8 hours (cluster monitoring UI)  
**Dependencies:** None (works with current architecture), Optional cluster support  
**Conflicts:** None (complements both multi-output and cluster architectures)
