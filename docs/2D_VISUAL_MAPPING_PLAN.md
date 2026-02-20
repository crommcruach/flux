# 2D Visual LED Mapping - Implementation Plan

**Feature:** Visual LED Position Capture via Webcam  
**Date:** February 19, 2026  
**Status:** Planning Phase

---

## 📋 Overview

Capture the physical 2D position of LEDs in a room using a webcam, then automatically create corresponding shapes in the canvas editor for accurate spatial mapping.

### Use Case
1. User mounts webcam with view of LED installation (wall, ceiling, etc.)
2. Application sequentially illuminates each LED/pixel
3. Webcam captures the lit position
4. System maps pixel coordinates to canvas editor shapes
5. Result: Accurate spatial representation for content creation

---

## 🎯 Core Requirements

### Functional Requirements
- ✅ Access USB or built-in laptop webcam via browser
- ✅ Calibrate camera view to canvas coordinate system
- ✅ Detect individual LED positions when lit
- ✅ Map detected positions to editor canvas coordinates
- ✅ Auto-generate shapes from captured positions
- ✅ Support multiple LED strips/objects
- ✅ Save/load mapping configurations

### Technical Requirements
- Browser-based (WebRTC MediaDevices API)
- Real-time video processing (Canvas API for frame analysis)
- Python backend LED control (Art-Net output)
- Integration with existing editor.js
- Performance: <50ms detection latency per LED

### User Experience
- Simple calibration workflow (4-corner reference points)
- Visual feedback during capture process
- Progress indicator (X/N LEDs mapped)
- Manual position adjustment after auto-capture
- Preview overlay showing detected positions

---

## 🏗️ Architecture

### Modal-Based Workflow

**All mapping happens within a single fullscreen modal in editor.html** - no separate page needed.

**4-Step Process:**

1. **Configuration Step**
   - User enters Art-Net IP, universe, LED count
   - Selects color type (RGB, RGBW, etc.)
   - Chooses webcam
   - Validates settings

2. **Calibration Step**
   - User clicks 4 reference points in canvas editor
   - User clicks same 4 points in camera view
   - System calculates perspective transform matrix
   - Transform maps camera pixels → canvas coordinates

3. **Mapping Step**
   - Backend sequentially lights each LED via Art-Net
   - Frontend detects bright spot in camera feed
   - Transforms detection to canvas coordinates
   - Displays real-time progress + success rate
   - Allows manual retry for failed detections

4. **Review Step**
   - Shows statistics (success rate, failed LEDs)
   - Displays final preview of all mapped positions
   - Allows manual placement of failed LEDs (click to place)
   - Exports config or saves directly to editor

### Frontend Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Mapping Interface                         │
│  ┌────────────────┐  ┌───────────────────────────────────┐  │
│  │  Webcam View   │  │   Canvas Editor (Reference)       │  │
│  │  (Live Feed)   │  │   - Detected positions overlay    │  │
│  │                │  │   - Calibration markers           │  │
│  └────────────────┘  └───────────────────────────────────┘  │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Controls: Calibrate | Start Mapping | Save | Cancel   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    Editor.html Page                          │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │         LED Mapper Modal (Fullscreen)                  │  │
│  │                                                         │  │
│  │  Step 1: Config → Step 2: Calibrate → Step 3: Map     │  │
│  │                                                         │  │
│  │  ┌──────────┐          ┌──────────┐                   │  │
│  │  │ Camera   │          │ Canvas   │                   │  │
│  │  │ Feed     │          │ Preview  │                   │  │
│  │  └──────────┘          └──────────┘                   │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                           │
                           │ WebSocket
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Python Backend                            │
│                                                               │
│  /api/mapper/start-sequence                                  │
│  - Receives config from modal form                           │
│  - Starts background task                                    │
│  - Emits 'led_active' events via SocketIO                   │
│                                                               │
│  Background Task:                                            │
│  For each LED:                                               │
│    1. Build Art-Net DMX packet                               │
│    2. Send to Art-Net IP:6454                               │
│    3. Emit led_active event                                  │
│    4. Wait delay_ms                                          │
│    5. Turn off LED                                           │
└──────────────────────────────────────────────────────────────┘
                           │ Art-Net UDP
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              Art-Net Controller / LED Hardware               │
│              (Receives DMX via Art-Net protocol)             │
└──────────────────────────────────────────────────────────────┘

Complete Flow:
1. User fills config form in modal (Art-Net IP, LED count, color type)
2. User calibrates camera (4-point transform)
3. Backend lights LED #1 via direct Art-Net packet
4. Webcam captures frame → Browser detects bright spot
5. JS transforms camera coords → canvas coords
6. Position stored + displayed
7. Backend lights LED #2 → Repeat
8. After all LEDs: Review stats, fix failed detections
9. Save as matrix shape in editor
```

---

## 🔧 Technical Implementation

### Phase 1: Webcam Access (2-3h)

**New File:** `frontend/js/led-mapper.js`

```javascript
export class LEDMapper {
    constructor(canvasElement) {
        this.canvas = canvasElement;
        this.ctx = canvas.getContext('2d', {willReadFrequently: true});
        this.videoElement = null;
        this.stream = null;
        this.isMapping = false;
        this.detectedPositions = [];
    }
    
    async initCamera(deviceId = null) {
        try {
            // Request camera access
            const constraints = {
                video: {
                    deviceId: deviceId ? {exact: deviceId} : undefined,
                    width: {ideal: 1920},
                    height: {ideal: 1080},
                    facingMode: 'environment' // Prefer rear camera
                }
            };
            
            this.stream = await navigator.mediaDevices.getUserMedia(constraints);
            this.videoElement = document.createElement('video');
            this.videoElement.srcObject = this.stream;
            this.videoElement.play();
            
            return true;
        } catch (error) {
            console.error('Camera access failed:', error);
            showToast('Webcam nicht verfügbar', 'error');
            return false;
        }
    }
    
    async listCameras() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        return devices.filter(device => device.kind === 'videoinput');
    }
    
    stopCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    }
}
```

**UI Trigger:** Add button to editor.html toolbar (next to existing tools)

```html
<!-- Add to editor.html canvas-settings-bar -->
<button class="btn btn-info btn-sm" onclick="showLEDMapper()" title="LED Visual Mapper">
    📷 Mapper
</button>
```

The modal HTML will be added directly to editor.html (see Phase 6 for complete modal markup).

---

### Phase 2: Calibration System (3-4h)

**Calibration Workflow:**
1. User places 4 reference markers at canvas corners (or known positions)
2. User clicks corresponding corners in webcam view
3. System calculates perspective transform matrix

```javascript
class CalibrationManager {
    constructor() {
        this.referencePoints = []; // Canvas coordinates
        this.cameraPoints = [];    // Webcam pixel coordinates
        this.transformMatrix = null;
    }
    
    addCalibrationPoint(canvasX, canvasY, cameraX, cameraY) {
        this.referencePoints.push({x: canvasX, y: canvasY});
        this.cameraPoints.push({x: cameraX, y: cameraY});
    }
    
    calculateTransform() {
        // Use perspective transform (homography)
        // Libraries: cv.wasm (OpenCV.js) or numeric.js
        // Maps camera pixel coords -> canvas coords
        
        if (this.referencePoints.length < 4) {
            throw new Error('Need at least 4 calibration points');
        }
        
        // Simplified 2D affine transform (for planar LED setup)
        this.transformMatrix = this.computeAffineTransform(
            this.cameraPoints,
            this.referencePoints
        );
    }
    
    mapCameraToCanvas(cameraX, cameraY) {
        if (!this.transformMatrix) {
            throw new Error('Calibration not complete');
        }
        
        // Apply transform matrix
        const {x, y} = this.applyTransform(cameraX, cameraY);
        return {x, y};
    }
    
    computeAffineTransform(srcPoints, dstPoints) {
        // Solve for 2D affine transform:
        // [x']   [a b c] [x]
        // [y'] = [d e f] [y]
        // [1 ]   [0 0 1] [1]
        
        // Use least-squares to find a,b,c,d,e,f
        // Library: math.js or numeric.js
        
        // Placeholder - implement actual math
        return {a: 1, b: 0, c: 0, d: 0, e: 1, f: 0};
    }
}
```

**UI:** Modal for calibration

```html
<!-- mapping-calibration-modal.html -->
<div class="modal" id="calibrationModal">
    <div class="modal-dialog modal-xl">
        <div class="modal-content">
            <div class="modal-header">
                <h5>LED Mapper - Calibration</h5>
            </div>
            <div class="modal-body">
                <div class="row">
                    <div class="col-6">
                        <h6>1. Click 4 corners in canvas editor</h6>
                        <canvas id="calibrationCanvas"></canvas>
                    </div>
                    <div class="col-6">
                        <h6>2. Click same 4 corners in camera view</h6>
                        <video id="calibrationVideo" autoplay></video>
                    </div>
                </div>
                <div class="alert alert-info">
                    Progress: <span id="calibrationProgress">0/4</span> points
                </div>
            </div>
            <div class="modal-footer">
                <button class="btn btn-primary" onclick="completeCalibration()">
                    Calculate Transform
                </button>
            </div>
        </div>
    </div>
</div>
```

---

### Phase 3: LED Detection Algorithm (4-5h)

**Approach:** Detect brightest spot in frame (assumes LED is significantly brighter than background)

```javascript
class LEDDetector {
    constructor(videoElement, canvas) {
        this.video = videoElement;
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d', {willReadFrequently: true});
        this.detectionThreshold = 200; // Brightness threshold (0-255)
        this.minBlobSize = 3; // Minimum LED size in pixels
    }
    
    async detectLED(timeout = 2000) {
        const startTime = Date.now();
        
        while (Date.now() - startTime < timeout) {
            const position = this.analyzeSingleFrame();
            
            if (position) {
                return position; // {x, y, confidence}
            }
            
            await this.waitFrame(); // Wait for next video frame
        }
        
        return null; // Detection failed
    }
    
    analyzeSingleFrame() {
        // Draw video frame to canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        
        // Get pixel data
        const imageData = this.ctx.getImageData(
            0, 0, this.canvas.width, this.canvas.height
        );
        const pixels = imageData.data;
        
        let brightestX = -1;
        let brightestY = -1;
        let maxBrightness = 0;
        
        // Find brightest pixel
        for (let y = 0; y < this.canvas.height; y++) {
            for (let x = 0; x < this.canvas.width; x++) {
                const i = (y * this.canvas.width + x) * 4;
                const brightness = (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
                
                if (brightness > maxBrightness && brightness > this.detectionThreshold) {
                    maxBrightness = brightness;
                    brightestX = x;
                    brightestY = y;
                }
            }
        }
        
        if (maxBrightness > this.detectionThreshold) {
            // Refine position using centroid of bright region
            const position = this.refineBlobCenter(pixels, brightestX, brightestY);
            return {
                x: position.x,
                y: position.y,
                confidence: maxBrightness / 255
            };
        }
        
        return null;
    }
    
    refineBlobCenter(pixels, seedX, seedY) {
        // Find centroid of connected bright pixels (blob detection)
        const visited = new Set();
        const queue = [{x: seedX, y: seedY}];
        let sumX = 0, sumY = 0, count = 0;
        
        while (queue.length > 0) {
            const {x, y} = queue.shift();
            const key = `${x},${y}`;
            
            if (visited.has(key)) continue;
            visited.add(key);
            
            const i = (y * this.canvas.width + x) * 4;
            const brightness = (pixels[i] + pixels[i+1] + pixels[i+2]) / 3;
            
            if (brightness > this.detectionThreshold) {
                sumX += x;
                sumY += y;
                count++;
                
                // Add neighbors
                if (count < 100) { // Limit blob size
                    queue.push({x: x+1, y});
                    queue.push({x: x-1, y});
                    queue.push({x, y: y+1});
                    queue.push({x, y: y-1});
                }
            }
        }
        
        return {
            x: sumX / count,
            y: sumY / count
        };
    }
    
    waitFrame() {
        return new Promise(resolve => requestAnimationFrame(resolve));
    }
}
```

**Advanced Option:** Use color detection if LEDs are RGB

```javascript
detectColoredLED(targetColor) {
    // For RGB LEDs - detect specific color instead of brightness
    // targetColor = {r: 255, g: 0, b: 0}
    
    for (let y = 0; y < this.canvas.height; y++) {
        for (let x = 0; x < this.canvas.width; x++) {
            const i = (y * this.canvas.width + x) * 4;
            const r = pixels[i];
            const g = pixels[i+1];
            const b = pixels[i+2];
            
            // Color distance in RGB space
            const distance = Math.sqrt(
                Math.pow(r - targetColor.r, 2) +
                Math.pow(g - targetColor.g, 2) +
                Math.pow(b - targetColor.b, 2)
            );
            
            if (distance < 50) { // Threshold for color match
                // Found matching color
            }
        }
    }
}
```

---

### Phase 4: Backend LED Control (2-3h)

**API Endpoint:** Trigger individual LEDs for detection

Backend receives configuration from the modal form and controls LEDs accordingly.

```python
# src/modules/api/routes.py

@app.route('/api/mapper/start-sequence', methods=['POST'])
def start_mapping_sequence():
    """Initialize mapping sequence with user configuration"""
    data = request.get_json()
    
    # Configuration from modal
    artnet_ip = data.get('artnet_ip')
    universe = data.get('universe', 0)
    color_type = data.get('color_type', 'rgb')  # rgb, rgbw, etc.
    led_count = data.get('led_count')
    start_address = data.get('start_address', 1)
    delay_ms = data.get('delay_ms', 800)
    
    # Validate
    if not artnet_ip or not led_count:
        return jsonify({'success': False, 'error': 'Missing required parameters'})
    
    try:
        # Store config in session for this mapping run
        mapping_config = {
            'artnet_ip': artnet_ip,
            'universe': universe,
            'color_type': color_type,
            'led_count': led_count,
            'start_address': start_address,
            'channels_per_led': get_channels_per_led(color_type)
        }
        
        # Start background task
        task_id = start_background_task(
            mapping_sequence_task,
            mapping_config,
            delay_ms
        )
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'led_count': led_count
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


def get_channels_per_led(color_type):
    """Calculate DMX channels per LED based on type"""
    channel_map = {
        'rgb': 3,
        'rgbw': 4,
        'rgbww': 5,
        'rgbwwcw': 6
    }
    return channel_map.get(color_type, 3)


def mapping_sequence_task(mapping_config, delay_ms):
    """Background task: sequentially light each LED for detection"""
    
    artnet_ip = mapping_config['artnet_ip']
    universe = mapping_config['universe']
    led_count = mapping_config['led_count']
    start_address = mapping_config['start_address']
    channels_per_led = mapping_config['channels_per_led']
    color_type = mapping_config['color_type']
    
    # Initialize Art-Net sender
    artnet = ArtNetSender(artnet_ip)
    
    for led_index in range(led_count):
        # Calculate DMX address for this LED
        dmx_address = start_address + (led_index * channels_per_led)
        
        # Create DMX packet (all zeros except current LED)
        dmx_data = [0] * 512
        
        # Set LED to full white (or full RGB)
        if color_type == 'rgb':
            dmx_data[dmx_address - 1] = 255  # R
            dmx_data[dmx_address] = 255      # G
            dmx_data[dmx_address + 1] = 255  # B
        elif color_type == 'rgbw':
            dmx_data[dmx_address - 1] = 255  # R
            dmx_data[dmx_address] = 255      # G
            dmx_data[dmx_address + 1] = 255  # B
            dmx_data[dmx_address + 2] = 255  # W
        # Add other color types as needed
        
        # Send to Art-Net
        artnet.send_dmx(universe, dmx_data)
        
        # Notify frontend that LED is now active
        socketio.emit('mapper:led_active', {
            'led_index': led_index,
            'total': led_count,
            'dmx_address': dmx_address
        })
        
        # Wait for detection
        time.sleep(delay_ms / 1000)
        
        # Turn off LED before next one
        dmx_data = [0] * 512
        artnet.send_dmx(universe, dmx_data)
        time.sleep(0.1)  # Brief pause between LEDs
    
    # All done
    socketio.emit('mapper:sequence_complete', {
        'total_leds': led_count
    })
    
    # Turn off all LEDs
    artnet.send_dmx(universe, [0] * 512)


@app.route('/api/mapper/test-single-led', methods=['POST'])
def test_single_led():
    """Test a single LED (for manual retry)"""
    data = request.get_json()
    
    led_index = data.get('led_index')
    config = data.get('config')  # Mapping config
    
    artnet = ArtNetSender(config['artnet_ip'])
    channels_per_led = get_channels_per_led(config['color_type'])
    dmx_address = config['start_address'] + (led_index * channels_per_led)
    
    dmx_data = [0] * 512
    dmx_data[dmx_address - 1] = 255  # Full white
    dmx_data[dmx_address] = 255
    dmx_data[dmx_address + 1] = 255
    
    artnet.send_dmx(config['universe'], dmx_data)
    
    return jsonify({'success': True, 'dmx_address': dmx_address})


class ArtNetSender:
    """Simple Art-Net DMX sender"""
    def __init__(self, target_ip):
        self.target_ip = target_ip
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    def send_dmx(self, universe, dmx_data):
        """Send DMX data via Art-Net"""
        # Art-Net packet construction
        packet = bytearray()
        packet.extend(b'Art-Net\x00')  # Header
        packet.extend([0x00, 0x50])    # OpCode ArtDMX
        packet.extend([0x00, 0x0e])    # Protocol version
        packet.append(0)               # Sequence
        packet.append(0)               # Physical
        packet.extend(universe.to_bytes(2, 'little'))  # Universe
        packet.extend(len(dmx_data).to_bytes(2, 'big'))  # Data length
        packet.extend(dmx_data)        # DMX data
        
        self.socket.sendto(packet, (self.target_ip, 6454))
```

---

### Phase 5: Editor Integration (3-4h)

**Mapping Workflow Integration:**

The modal handles the entire workflow - no separate page needed.

```javascript
// frontend/js/led-mapper.js (continued)

class MappingSession {
    constructor(config, calibration, detector) {
        this.config = config;  // From modal form
        this.calibration = calibration;
        this.detector = detector;
        this.mappedPositions = new Map(); // led_index -> {x, y, confidence}
        this.failedLEDs = [];
        this.isPaused = false;
    }
    
    async startMappingSequence() {
        showToast(`Starting mapping of ${this.config.ledCount} LEDs...`, 'info');
        
        // Update UI
        document.getElementById('totalLEDs').textContent = this.config.ledCount;
        document.getElementById('detectionStatus').className = 'badge bg-secondary';
        document.getElementById('detectionStatus').textContent = 'Initializing...';
        
        // Start backend sequence with modal configuration
        const response = await fetch('/api/mapper/start-sequence', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                artnet_ip: this.config.artnetIP,
                universe: this.config.universe,
                color_type: this.config.colorType,
                led_count: this.config.ledCount,
                start_address: this.config.startAddress,
                delay_ms: 800
            })
        });
        
        const data = await response.json();
        
        if (!data.success) {
            showToast('Failed to start mapping: ' + data.error, 'error');
            return;
        }
        
        // Listen for LED activation events from backend
        socket.on('mapper:led_active', async (eventData) => {
            if (!this.isPaused) {
                await this.captureLEDPosition(eventData.led_index, eventData.total);
            }
        });
        
        socket.on('mapper:sequence_complete', () => {
            this.finishMapping();
        });
    }
    
    async captureLEDPosition(ledIndex, total) {
        // Update progress UI
        const progress = ((ledIndex + 1) / total) * 100;
        document.getElementById('mappingProgressBar').style.width = `${progress}%`;
        document.getElementById('mappingProgressBar').innerHTML = 
            `<strong>${ledIndex + 1} / ${total}</strong>`;
        
        document.getElementById('currentLEDIndex').textContent = ledIndex + 1;
        document.getElementById('detectionStatus').className = 'badge bg-warning';
        document.getElementById('detectionStatus').textContent = 'Detecting...';
        
        // Wait for LED to be fully lit
        await sleep(100);
        
        // Detect LED in camera view
        const cameraPos = await this.detector.detectLED(1500);
        
        if (!cameraPos) {
            console.warn(`Failed to detect LED #${ledIndex}`);
            showToast(`LED ${ledIndex + 1} not detected`, 'warning');
            
            this.failedLEDs.push(ledIndex);
            document.getElementById('failedLEDs').textContent = this.failedLEDs.length;
            
            document.getElementById('detectionStatus').className = 'badge bg-danger';
            document.getElementById('detectionStatus').textContent = 'Failed';
            
            // Enable retry button
            document.getElementById('retryBtn').disabled = false;
            
            return;
        }
        
        // Transform camera coordinates to canvas coordinates
        const canvasPos = this.calibration.mapCameraToCanvas(
            cameraPos.x,
            cameraPos.y
        );
        
        // Store position with confidence score
        this.mappedPositions.set(ledIndex, {
            x: canvasPos.x,
            y: canvasPos.y,
            confidence: cameraPos.confidence
        });
        
        // Show visual feedback on both views
        this.drawDetectionMarker(canvasPos, ledIndex);
        this.highlightCameraDetection(cameraPos);
        
        // Update success rate
        const successRate = ((this.mappedPositions.size / (ledIndex + 1)) * 100).toFixed(1);
        document.getElementById('successRate').textContent = `${successRate}%`;
        document.getElementById('failedLEDs').textContent = this.failedLEDs.length;
    }
    
    highlightCameraDetection(cameraPos) {
        const overlay = document.getElementById('detectionOverlay');
        const ctx = overlay.getContext('2d');
        
        // Draw circle around detected LED in camera view
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(cameraPos.x, cameraPos.y, 15, 0, Math.PI * 2);
        ctx.stroke();
        
        // Fade out after 500ms
        setTimeout(() => {
            ctx.clearRect(0, 0, overlay.width, overlay.height);
        }, 500);
    }
    
    finishMapping() {
        showToast('Mapping sequence complete!', 'success');
        
        // Calculate statistics
        const totalLEDs = this.config.ledCount;
        const successCount = this.mappedPositions.size;
        const failedCount = this.failedLEDs.length;
        const successRate = ((successCount / totalLEDs) * 100).toFixed(1);
        
        let totalConfidence = 0;
        this.mappedPositions.forEach(pos => {
            totalConfidence += pos.confidence;
        });
        const avgConfidence = (totalConfidence / successCount * 100).toFixed(1);
        
        // Update Step 4 (Review) UI
        document.getElementById('statsTotal').textContent = totalLEDs;
        document.getElementById('statsSuccess').textContent = successCount;
        document.getElementById('statsFailed').textContent = failedCount;
        document.getElementById('statsRate').textContent = `${successRate}%`;
        document.getElementById('statsConfidence').textContent = `${avgConfidence}%`;
        
        // Show failed LEDs list
        this.displayFailedLEDs();
        
        // Draw final preview
        this.drawFinalPreview();
        
        // Move to review step
        mapperNextStep();
    }
    
    displayFailedLEDs() {
        const container = document.getElementById('failedLEDsList');
        container.innerHTML = '';
        
        if (this.failedLEDs.length === 0) {
            container.innerHTML = '<p class="text-success">All LEDs detected successfully! ✅</p>';
            return;
        }
        
        this.failedLEDs.forEach(ledIndex => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-sm btn-outline-warning m-1';
            btn.textContent = `LED ${ledIndex + 1}`;
            btn.onclick = () => this.manuallyPlaceLED(ledIndex);
            container.appendChild(btn);
        });
    }
    
    manuallyPlaceLED(ledIndex) {
        showToast(`Click on canvas to place LED ${ledIndex + 1}`, 'info');
        
        // Enable click mode on canvas
        const canvas = document.getElementById('finalPreview');
        const clickHandler = (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) * (canvas.width / rect.width);
            const y = (e.clientY - rect.top) * (canvas.height / rect.height);
            
            this.mappedPositions.set(ledIndex, {x, y, confidence: 0.5});
            this.failedLEDs = this.failedLEDs.filter(i => i !== ledIndex);
            
            this.drawFinalPreview();
            this.displayFailedLEDs();
            
            canvas.removeEventListener('click', clickHandler);
            canvas.style.cursor = 'default';
        };
        
        canvas.addEventListener('click', clickHandler);
        canvas.style.cursor = 'crosshair';
    }
    
    drawFinalPreview() {
        const canvas = document.getElementById('finalPreview');
        const ctx = canvas.getContext('2d');
        
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw grid or background reference
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        for (let i = 0; i < canvas.width; i += 50) {
            ctx.beginPath();
            ctx.moveTo(i, 0);
            ctx.lineTo(i, canvas.height);
            ctx.stroke();
        }
        for (let i = 0; i < canvas.height; i += 50) {
            ctx.beginPath();
            ctx.moveTo(0, i);
            ctx.lineTo(canvas.width, i);
            ctx.stroke();
        }
        
        // Draw all mapped LED positions
        this.mappedPositions.forEach((pos, ledIndex) => {
            // Color based on confidence
            const isManual = pos.confidence < 0.6;
            ctx.fillStyle = isManual ? '#ffaa00' : '#00ff00';
            ctx.strokeStyle = isManual ? '#ff6600' : '#00cc00';
            
            // Draw LED circle
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 8, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
            
            // Draw LED number
            ctx.fillStyle = '#000';
            ctx.font = '10px monospace';
            ctx.textAlign = 'center';
            ctx.fillText(ledIndex + 1, pos.x, pos.y + 3);
        });
    }
}

function saveMappingToEditor() {
    // Create new shape with mapped LED positions
    const positions = Array.from(mappingSession.mappedPositions.entries())
        .sort((a, b) => a[0] - b[0])  // Sort by LED index
        .map(([idx, pos]) => ({x: pos.x, y: pos.y, index: idx}));
    
    // Add as matrix shape
    const newShape = {
        id: `mapped_leds_${Date.now()}`,
        type: 'matrix',
        dots: positions,
        name: `Mapped LEDs (${positions.length})`,
        config: mapperConfig  // Store mapping config
    };
    
    shapes.push(newShape);
    saveEditorStateToSession();
    render();
    
    // Close modal
    bootstrap.Modal.getInstance(document.getElementById('ledMapperModal')).hide();
    
    showToast(`${positions.length} LEDs added to editor!`, 'success');
}

function exportMappingConfig() {
    const config = {
        version: '1.0',
        created_at: new Date().toISOString(),
        config: mapperConfig,
        calibration: {
            reference_points: calibrationManager.referencePoints,
            camera_points: calibrationManager.cameraPoints,
            transform_matrix: calibrationManager.transformMatrix
        },
        mapped_leds: Array.from(mappingSession.mappedPositions.entries()).map(([idx, pos]) => ({
            led_index: idx,
            position: [pos.x, pos.y],
            confidence: pos.confidence
        }))
    };
    
    const blob = new Blob([JSON.stringify(config, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `led-mapping-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    
    showToast('Mapping config exported!', 'success');
}
```

---

### Phase 6: UI & User Experience (2-3h)

**Multi-Step Modal Workflow:**

The entire mapping process happens in a single modal with multiple steps:

**Step 1: Configuration** → **Step 2: Calibration** → **Step 3: Mapping** → **Step 4: Review**

```html
<!-- Add to editor.html -->
<div class="modal fade" id="ledMapperModal" tabindex="-1">
    <div class="modal-dialog modal-fullscreen">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">📷 LED Visual Mapper</h5>
                <span id="mapperStepIndicator" class="ms-3 badge bg-secondary">Step 1/4: Configuration</span>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            
            <div class="modal-body">
                <!-- STEP 1: Configuration Form -->
                <div id="mapperStep1" class="mapper-step">
                    <div class="container" style="max-width: 600px; margin-top: 3rem;">
                        <h4 class="mb-4">LED Configuration</h4>
                        
                        <div class="mb-3">
                            <label class="form-label">Art-Net IP Address</label>
                            <input type="text" class="form-control" id="mapperArtnetIP" 
                                   placeholder="192.168.1.100" value="192.168.1.100">
                            <small class="text-muted">IP of the Art-Net controller/node</small>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Art-Net Universe</label>
                            <input type="number" class="form-control" id="mapperUniverse" 
                                   min="0" max="32767" value="0">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">LED Color Type</label>
                            <select class="form-select" id="mapperColorType">
                                <option value="rgb">RGB (3 channels)</option>
                                <option value="rgbw">RGBW (4 channels)</option>
                                <option value="rgbww">RGB+WW (5 channels)</option>
                                <option value="rgbwwcw">RGB+WW+CW (6 channels)</option>
                            </select>
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Number of LEDs to Map</label>
                            <input type="number" class="form-control" id="mapperLEDCount" 
                                   min="1" max="500" value="50">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label">Starting DMX Address</label>
                            <input type="number" class="form-control" id="mapperStartAddress" 
                                   min="1" max="512" value="1">
                        </div>
                        
                        <div class="mb-4">
                            <label class="form-label">Webcam</label>
                            <select class="form-select" id="mapperCamera">
                                <option value="">Auto-detect</option>
                            </select>
                            <small class="text-muted">Will be populated with available cameras</small>
                        </div>
                        
                        <button class="btn btn-primary btn-lg w-100" onclick="mapperNextStep()">
                            Next: Calibration →
                        </button>
                    </div>
                </div>
                
                <!-- STEP 2: Calibration -->
                <div id="mapperStep2" class="mapper-step" style="display: none;">
                    <h4 class="mb-3">Camera Calibration</h4>
                    <p class="text-muted">Click 4 corners: Top-Left → Top-Right → Bottom-Right → Bottom-Left</p>
                    
                    <div class="row">
                        <div class="col-6">
                            <h6>Canvas Editor (Click corners here)</h6>
                            <div style="position: relative; border: 2px solid var(--border-color);">
                                <canvas id="calibrationCanvasView" style="width: 100%; cursor: crosshair;"></canvas>
                                <div id="calibrationMarkers"></div>
                            </div>
                        </div>
                        <div class="col-6">
                            <h6>Camera View (Click same corners here)</h6>
                            <div style="position: relative; border: 2px solid var(--border-color);">
                                <video id="calibrationVideo" autoplay style="width: 100%; cursor: crosshair;"></video>
                                <canvas id="calibrationOverlay" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <div class="alert alert-info mt-3">
                        <strong>Progress:</strong> <span id="calibrationProgress">0/4 points</span>
                        <div class="progress mt-2" style="height: 8px;">
                            <div id="calibrationProgressBar" class="progress-bar" style="width: 0%"></div>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <button class="btn btn-secondary" onclick="mapperPrevStep()">← Back</button>
                        <button class="btn btn-primary" id="calibrationNextBtn" disabled onclick="mapperNextStep()">
                            Next: Start Mapping →
                        </button>
                        <button class="btn btn-warning" onclick="resetCalibration()">Reset Points</button>
                    </div>
                </div>
                
                <!-- STEP 3: Mapping in Progress -->
                <div id="mapperStep3" class="mapper-step" style="display: none;">
                    <h4 class="mb-3">Mapping in Progress...</h4>
                    
                    <div class="row h-100">
                        <div class="col-6">
                            <h6>Camera View</h6>
                            <div style="position: relative; border: 2px solid var(--border-color);">
                                <video id="mappingVideo" autoplay style="width: 100%;"></video>
                                <canvas id="detectionOverlay" 
                                        style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;">
                                </canvas>
                            </div>
                            <div class="mt-2">
                                <strong>Current LED:</strong> <span id="currentLEDIndex">-</span> / <span id="totalLEDs">-</span>
                                <br>
                                <strong>Detection Status:</strong> <span id="detectionStatus" class="badge bg-secondary">Waiting...</span>
                            </div>
                        </div>
                        
                        <div class="col-6">
                            <h6>Canvas Mapping Preview</h6>
                            <canvas id="mappingPreview" style="width: 100%; border: 2px solid var(--border-color);"></canvas>
                            <div class="mt-3">
                                <div class="progress" style="height: 30px;">
                                    <div id="mappingProgressBar" class="progress-bar progress-bar-striped progress-bar-animated" 
                                         style="width: 0%">
                                        <strong>0 / 0</strong>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-2">
                                <strong>Success Rate:</strong> <span id="successRate">-</span>
                                <br>
                                <strong>Failed LEDs:</strong> <span id="failedLEDs">-</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mt-3">
                        <button class="btn btn-warning" id="pauseMappingBtn" onclick="pauseMapping()">
                            ⏸ Pause
                        </button>
                        <button class="btn btn-danger" onclick="cancelMapping()">
                            ✕ Cancel
                        </button>
                        <button class="btn btn-secondary" onclick="retryCurrentLED()" disabled id="retryBtn">
                            🔄 Retry Current
                        </button>
                    </div>
                </div>
                
                <!-- STEP 4: Review & Save -->
                <div id="mapperStep4" class="mapper-step" style="display: none;">
                    <h4 class="mb-3">✅ Mapping Complete!</h4>
                    
                    <div class="row">
                        <div class="col-6">
                            <h6>Statistics</h6>
                            <table class="table table-sm">
                                <tr>
                                    <td>Total LEDs:</td>
                                    <td><strong id="statsTotal">-</strong></td>
                                </tr>
                                <tr>
                                    <td>Successfully Mapped:</td>
                                    <td><strong id="statsSuccess" class="text-success">-</strong></td>
                                </tr>
                                <tr>
                                    <td>Failed:</td>
                                    <td><strong id="statsFailed" class="text-danger">-</strong></td>
                                </tr>
                                <tr>
                                    <td>Success Rate:</td>
                                    <td><strong id="statsRate">-</strong></td>
                                </tr>
                                <tr>
                                    <td>Average Position Confidence:</td>
                                    <td><strong id="statsConfidence">-</strong></td>
                                </tr>
                            </table>
                            
                            <h6 class="mt-4">Failed LEDs (click to manually place)</h6>
                            <div id="failedLEDsList" style="max-height: 200px; overflow-y: auto;"></div>
                        </div>
                        
                        <div class="col-6">
                            <h6>Final Mapping Preview</h6>
                            <canvas id="finalPreview" style="width: 100%; border: 2px solid var(--border-color);"></canvas>
                        </div>
                    </div>
                    
                    <div class="mt-4">
                        <button class="btn btn-warning" onclick="mapperPrevStep()">
                            ← Redo Mapping
                        </button>
                        <button class="btn btn-success btn-lg" onclick="saveMappingToEditor()">
                            💾 Save to Editor
                        </button>
                        <button class="btn btn-info" onclick="exportMappingConfig()">
                            📥 Export Config
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Modal Step Controller:**

```javascript
// frontend/js/led-mapper.js (modal control)

let currentMapperStep = 1;
const mapperConfig = {
    artnetIP: null,
    universe: 0,
    colorType: 'rgb',
    ledCount: 0,
    startAddress: 1,
    cameraId: null
};

function showLEDMapper() {
    // Initialize modal
    const modal = new bootstrap.Modal(document.getElementById('ledMapperModal'));
    modal.show();
    
    // Populate camera list
    populateCameraList();
    
    currentMapperStep = 1;
    showMapperStep(1);
}

function mapperNextStep() {
    if (currentMapperStep === 1) {
        // Validate and save configuration
        if (!validateMapperConfig()) return;
        saveMapperConfig();
    }
    
    currentMapperStep++;
    showMapperStep(currentMapperStep);
    
    if (currentMapperStep === 2) {
        initializeCalibration();
    } else if (currentMapperStep === 3) {
        startMappingSequence();
    }
}

function mapperPrevStep() {
    currentMapperStep--;
    showMapperStep(currentMapperStep);
}

function showMapperStep(step) {
    // Hide all steps
    document.querySelectorAll('.mapper-step').forEach(el => {
        el.style.display = 'none';
    });
    
    // Show current step
    document.getElementById(`mapperStep${step}`).style.display = 'block';
    
    // Update step indicator
    const stepNames = ['Configuration', 'Calibration', 'Mapping', 'Review'];
    document.getElementById('mapperStepIndicator').textContent = 
        `Step ${step}/4: ${stepNames[step - 1]}`;
}

function validateMapperConfig() {
    const ip = document.getElementById('mapperArtnetIP').value;
    const ledCount = parseInt(document.getElementById('mapperLEDCount').value);
    
    if (!ip || !/^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(ip)) {
        showToast('Invalid Art-Net IP address', 'error');
        return false;
    }
    
    if (ledCount < 1 || ledCount > 500) {
        showToast('LED count must be between 1 and 500', 'error');
        return false;
    }
    
    return true;
}

function saveMapperConfig() {
    mapperConfig.artnetIP = document.getElementById('mapperArtnetIP').value;
    mapperConfig.universe = parseInt(document.getElementById('mapperUniverse').value);
    mapperConfig.colorType = document.getElementById('mapperColorType').value;
    mapperConfig.ledCount = parseInt(document.getElementById('mapperLEDCount').value);
    mapperConfig.startAddress = parseInt(document.getElementById('mapperStartAddress').value);
    mapperConfig.cameraId = document.getElementById('mapperCamera').value || null;
}

async function populateCameraList() {
    const select = document.getElementById('mapperCamera');
    const cameras = await navigator.mediaDevices.enumerateDevices();
    const videoDevices = cameras.filter(d => d.kind === 'videoinput');
    
    select.innerHTML = '<option value="">Auto-detect</option>';
    videoDevices.forEach((device, idx) => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.textContent = device.label || `Camera ${idx + 1}`;
        select.appendChild(option);
    });
}

function drawDetectionMarker(canvasPos, ledIndex) {
    const ctx = document.getElementById('mappingPreview').getContext('2d');
    
    // Draw crosshair at detected position
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(canvasPos.x - 10, canvasPos.y);
    ctx.lineTo(canvasPos.x + 10, canvasPos.y);
    ctx.moveTo(canvasPos.x, canvasPos.y - 10);
    ctx.lineTo(canvasPos.x, canvasPos.y + 10);
    ctx.stroke();
    
    // Add number label
    ctx.fillStyle = '#00ff00';
    ctx.font = '12px monospace';
    ctx.fillText(ledIndex, canvasPos.x + 15, canvasPos.y - 5);
    
    // Update UI
    document.getElementById('currentLEDIndex').textContent = ledIndex;
    document.getElementById('detectionStatus').className = 'badge bg-success';
    document.getElementById('detectionStatus').textContent = 'Detected!';
}
```

---

## 📊 Implementation Timeline

| Phase | Task | Effort | Dependencies |
|-------|------|--------|--------------|
| 1 | Webcam access & camera selection | 2-3h | - |
| 2 | Calibration system (4-point transform) | 3-4h | Phase 1 |
| 3 | LED detection algorithm | 4-5h | Phase 1 |
| 4 | Backend LED control API | 2-3h | - |
| 5 | Editor integration | 3-4h | Phases 2-4 |
| 6 | UI/UX polish | 2-3h | All phases |
| **Total** | | **16-22h** | |

---

## 🧪 Testing Plan

### Unit Tests
- ✅ Camera initialization (mock MediaDevices API)
- ✅ Calibration point transformation accuracy
- ✅ LED detection with synthetic frames
- ✅ Backend API endpoints

### Integration Tests
- ✅ Full mapping workflow with 10-LED strip
- ✅ Calibration accuracy (measure deviation)
- ✅ Detection success rate (>95% target)

### Edge Cases
- ❌ No camera available → Show error message
- ❌ LED not detected → Allow manual position click
- ❌ Multiple bright spots → Use brightest or color filter
- ❌ Camera permission denied → Fallback to manual mode

---

## 🚀 Future Enhancements

### V2 Features
1. **Auto-calibration:** Use ArUco markers for automatic calibration
2. **3D Mapping:** Stereo camera setup for depth (Z-axis)
3. **Multiple cameras:** Combine views for better coverage
4. **Real-time preview:** Show live overlay during content playback
5. **Smart grouping:** Auto-detect LED strips and group by proximity
6. **Export/Import:** Save mapping configs as JSON files

### Performance Optimizations
- Web Workers for frame processing (offload main thread)
- GPU acceleration via WebGL for pixel analysis
- Adaptive detection threshold based on ambient light

---

## 📝 Configuration Schema

```json
{
  "mapping_config": {
    "version": "1.0",
    "created_at": "2026-02-19T14:30:00Z",
    "camera": {
      "device_id": "abc123...",
      "resolution": [1920, 1080],
      "fps": 30
    },
    "calibration": {
      "reference_points": [
        {"canvas": [0, 0], "camera": [120, 80]},
        {"canvas": [1920, 0], "camera": [1800, 90]},
        {"canvas": [1920, 1080], "camera": [1810, 990]},
        {"canvas": [0, 1080], "camera": [110, 1000]}
      ],
      "transform_matrix": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    },
    "detection": {
      "brightness_threshold": 200,
      "min_blob_size": 3,
      "timeout_ms": 2000
    },
    "mapped_leds": [
      {"shape_id": "shape_001", "led_index": 0, "position": [100, 200]},
      {"shape_id": "shape_001", "led_index": 1, "position": [110, 205]}
    ]
  }
}
```

---

## ✅ Success Criteria

- ✅ Detect 95%+ of LEDs automatically
- ✅ Position accuracy within ±5 pixels
- ✅ Complete mapping in <1 second per LED
- ✅ Support 100+ LEDs in single session
- ✅ Works with USB and built-in webcams
- ✅ Calibration persists across sessions

---

## 🔗 Related Documents

- [FEATURES.md](../FEATURES.md) - Overall feature roadmap
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [API.md](API.md) - API endpoints
- [EDITOR.md](EDITOR.md) - Canvas editor documentation

---

**Next Steps:**
1. Prototype Phase 1 (camera access)
2. Test detection algorithm with single LED
3. Implement calibration workflow
4. Full integration with editor
