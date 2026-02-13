# Delta Encoding for ArtNet Routing System - Implementation Plan

**Status:** 📋 PLANNED - Not Yet Implemented  
**Date:** 2026-02-13  
**Priority:** Medium  
**Estimated Effort:** 4-6 hours

---

## 📊 Current Status Assessment

### ✅ Already Implemented

#### 1. **Color Corrections** - FULLY WORKING
- **Backend:** Applied per-object AND per-output in `output_manager.py` (lines 134-163)
- **Frontend:** Sliders in `output-settings.html` (lines 271-282) and `output-settings.js`
- **Parameters:** Brightness, Contrast, Red, Green, Blue (-255 to 255)
- **Data Flow:** GUI → session_state.json → backend → DMX output ✅

#### 2. **Channel Orders** - FULLY WORKING
- **Backend:** 36 channel orders supported by `rgb_format_mapper.py`
- **Frontend:** Dropdown selector in `output-settings.html` (lines 246-254)
- **Supported:** RGB, GRB, BGR, RGBW, GRBW, WRGB, RGBAW, RGBWW, RGBCWW, etc.
- **Data Flow:** GUI → session_state.json → backend → DMX output ✅

### ⚠️ Delta Encoding - DATA MODEL READY, NOT IMPLEMENTED

#### What Exists:
1. ✅ **Data Model:** Properties in `artnet_output.py` (lines 43-46):
   ```python
   delta_enabled: bool = False
   delta_threshold: int = 8          # 0-255
   full_frame_interval: int = 30     # Frames
   ```

2. ✅ **Documentation:** Comprehensive docs in `DELTA_ENCODING.md`
   - Algorithm explanation
   - Performance benchmarks
   - CLI commands (for old system)
   - REST API endpoints (for old system)

3. ✅ **Global Config:** Settings in `session_state.json`:
   ```json
   "delta_encoding": {
     "enabled": true,
     "threshold": 8,
     "threshold_16bit": 2048,
     "full_frame_interval": 30
   }
   ```

#### What's Missing:
1. ❌ **Backend Implementation:** `artnet_sender.py` doesn't use delta encoding yet
2. ❌ **Frontend UI:** No per-output delta encoding controls
3. ❌ **Monitoring Dashboard:** No visualization of delta encoding activity
4. ❌ **Statistics Tracking:** No metrics collection/reporting

---

## 🎯 Implementation Plan

### Phase 1: Backend Implementation (Priority: HIGH)

#### 1.1 Extend `ArtNetSender` Class

**File:** `src/modules/artnet_routing/artnet_sender.py`

**Add Class Attributes:**
```python
class ArtNetSender:
    def __init__(self):
        self.senders: Dict[str, Dict] = {}
        
        # Delta encoding state (NEW)
        self.delta_buffers: Dict[str, bytes] = {}           # output_id → last sent DMX data
        self.frame_counters: Dict[str, int] = {}            # output_id → frame counter
        self.delta_stats: Dict[str, Dict] = {}              # output_id → statistics
```

**Add Statistics Structure:**
```python
# Per-output delta statistics
self.delta_stats[output_id] = {
    'enabled': False,
    'total_frames': 0,
    'delta_frames': 0,
    'full_frames': 0,
    'bytes_saved': 0,
    'total_bytes': 0,
    'current_changed_pixels': 0,
    'current_changed_percent': 0.0,
    'last_decision': 'none',  # 'delta', 'full', 'sync', 'first'
    'last_decision_time': 0.0,
    'history': []  # Last 100 frames: [(frame_num, changed_px, decision)]
}
```

#### 1.2 Implement Delta Encoding Logic

**New Method: `send_dmx_with_delta()`**
```python
def send_dmx_with_delta(self, output_id: str, dmx_data: bytes):
    """
    Send DMX data with optional delta encoding.
    
    Args:
        output_id: Output identifier
        dmx_data: Complete DMX data as bytes
    """
    if output_id not in self.senders:
        return
    
    config = self.senders[output_id]['config']
    
    # Delta encoding disabled → normal full frame
    if not config.delta_enabled:
        return self._send_full_frame(output_id, dmx_data, reason='disabled')
    
    # Initialize counters if needed
    if output_id not in self.frame_counters:
        self.frame_counters[output_id] = 0
    
    frame_num = self.frame_counters[output_id]
    self.frame_counters[output_id] += 1
    
    # Periodic full frame sync (packet loss protection)
    if frame_num % config.full_frame_interval == 0:
        return self._send_full_frame(output_id, dmx_data, reason='sync')
    
    # First frame → must send full
    if output_id not in self.delta_buffers:
        return self._send_full_frame(output_id, dmx_data, reason='first')
    
    # Calculate difference from last frame
    last_frame = self.delta_buffers[output_id]
    changed_count, changed_percent = self._calculate_diff(
        dmx_data, 
        last_frame, 
        config.delta_threshold
    )
    
    # Decision: >80% changed → full frame
    if changed_percent > 80.0:
        return self._send_full_frame(
            output_id, 
            dmx_data, 
            reason='too_many_changes',
            changed_count=changed_count
        )
    
    # Delta update: send only changed channels
    return self._send_delta_update(
        output_id, 
        dmx_data, 
        changed_count,
        changed_percent
    )
```

**Helper Method: `_calculate_diff()`**
```python
def _calculate_diff(
    self, 
    current: bytes, 
    previous: bytes, 
    threshold: int
) -> Tuple[int, float]:
    """
    Calculate difference between two DMX frames.
    
    Args:
        current: Current DMX data
        previous: Previous DMX data
        threshold: Change threshold (0-255)
    
    Returns:
        (changed_count, changed_percent)
    """
    import numpy as np
    
    # Convert to numpy arrays
    curr_array = np.frombuffer(current, dtype=np.uint8)
    prev_array = np.frombuffer(previous, dtype=np.uint8)
    
    # Calculate absolute difference
    diff = np.abs(curr_array.astype(np.int16) - prev_array.astype(np.int16))
    
    # Count channels exceeding threshold
    changed_mask = diff > threshold
    changed_count = np.sum(changed_mask)
    
    # Calculate percentage
    total_channels = len(curr_array)
    changed_percent = (changed_count / total_channels) * 100.0
    
    return int(changed_count), float(changed_percent)
```

**Helper Method: `_send_full_frame()`**
```python
def _send_full_frame(
    self, 
    output_id: str, 
    dmx_data: bytes, 
    reason: str,
    changed_count: int = None
):
    """Send full DMX frame and update tracking."""
    # Send via normal path
    self.send_dmx(output_id, dmx_data)
    
    # Update buffer
    self.delta_buffers[output_id] = dmx_data
    
    # Update statistics
    if output_id in self.delta_stats:
        stats = self.delta_stats[output_id]
        stats['total_frames'] += 1
        stats['full_frames'] += 1
        stats['total_bytes'] += len(dmx_data)
        stats['last_decision'] = reason
        stats['last_decision_time'] = time.time()
        
        if changed_count is not None:
            stats['current_changed_pixels'] = changed_count
            stats['current_changed_percent'] = (changed_count / len(dmx_data)) * 100.0
        
        # Add to history
        frame_num = self.frame_counters.get(output_id, 0)
        stats['history'].append((frame_num, changed_count or 0, reason))
        if len(stats['history']) > 100:
            stats['history'].pop(0)
    
    logger.debug(f"Delta: Full frame sent ({reason}), {len(dmx_data)} bytes")
```

**Helper Method: `_send_delta_update()`**
```python
def _send_delta_update(
    self, 
    output_id: str, 
    dmx_data: bytes,
    changed_count: int,
    changed_percent: float
):
    """
    Send only changed channels (delta update).
    
    NOTE: stupidArtnet doesn't support partial updates natively,
    so we still send full frame but track savings for monitoring.
    Future: Could implement custom ArtNet packet with sparse updates.
    """
    # For now, send full frame (stupidArtnet limitation)
    # Future optimization: Send only changed channels via raw socket
    self.send_dmx(output_id, dmx_data)
    
    # Update buffer
    self.delta_buffers[output_id] = dmx_data
    
    # Update statistics
    if output_id in self.delta_stats:
        stats = self.delta_stats[output_id]
        stats['total_frames'] += 1
        stats['delta_frames'] += 1
        stats['total_bytes'] += len(dmx_data)
        
        # Calculate theoretical savings (changed channels only)
        # Each universe = 512 channels, but we only need to send changed ones
        theoretical_sent = changed_count * 3  # RGB channels
        actual_sent = len(dmx_data)
        bytes_saved = actual_sent - theoretical_sent
        stats['bytes_saved'] += bytes_saved
        
        stats['current_changed_pixels'] = changed_count
        stats['current_changed_percent'] = changed_percent
        stats['last_decision'] = 'delta'
        stats['last_decision_time'] = time.time()
        
        # Add to history
        frame_num = self.frame_counters.get(output_id, 0)
        stats['history'].append((frame_num, changed_count, 'delta'))
        if len(stats['history']) > 100:
            stats['history'].pop(0)
    
    logger.debug(f"Delta: Update sent ({changed_count} px, {changed_percent:.1f}%)")
```

#### 1.3 Add Statistics API

**New Method: `get_delta_stats()`**
```python
def get_delta_stats(self, output_id: str) -> Optional[Dict]:
    """
    Get delta encoding statistics for an output.
    
    Returns:
        Dictionary with statistics or None if not available
    """
    if output_id not in self.delta_stats:
        return None
    
    stats = self.delta_stats[output_id].copy()
    
    # Calculate efficiency
    if stats['total_bytes'] > 0:
        stats['efficiency_percent'] = (stats['bytes_saved'] / stats['total_bytes']) * 100.0
    else:
        stats['efficiency_percent'] = 0.0
    
    # Calculate frame type ratio
    if stats['total_frames'] > 0:
        stats['delta_ratio'] = (stats['delta_frames'] / stats['total_frames']) * 100.0
        stats['full_ratio'] = (stats['full_frames'] / stats['total_frames']) * 100.0
    else:
        stats['delta_ratio'] = 0.0
        stats['full_ratio'] = 0.0
    
    return stats
```

#### 1.4 Update Existing Methods

**Modify `configure_output()`:**
```python
def configure_output(self, output: ArtNetOutput):
    # ... existing code ...
    
    # Initialize delta encoding stats
    self.delta_stats[output.id] = {
        'enabled': output.delta_enabled,
        'threshold': output.delta_threshold,
        'full_frame_interval': output.full_frame_interval,
        'total_frames': 0,
        'delta_frames': 0,
        'full_frames': 0,
        'bytes_saved': 0,
        'total_bytes': 0,
        'current_changed_pixels': 0,
        'current_changed_percent': 0.0,
        'last_decision': 'none',
        'last_decision_time': 0.0,
        'history': []
    }
```

**Modify `routing_bridge.py` to use delta:**
```python
# In RoutingBridge.process_frame()
for output_id, dmx_data in rendered_outputs.items():
    # Use delta-aware sending (instead of direct send_dmx)
    self.sender.send_dmx_with_delta(output_id, dmx_data)
```

---

### Phase 2: Frontend UI (Priority: HIGH)

#### 2.1 Add Context Menu Option

**File:** `frontend/output-settings.html` (line 466)

```html
<div id="outputContextMenu" class="context-menu">
    <div class="context-menu-item" onclick="app.outputContextMenuAction('preview', event)">📊 DMX Monitor</div>
    <div class="context-menu-item" onclick="app.outputContextMenuAction('deltaencoding', event)">⚡ Delta Encoding</div>
    <div class="context-menu-item" onclick="app.outputContextMenuAction('edit', event)">✏️ Edit Output</div>
    <div class="context-menu-item" onclick="app.outputContextMenuAction('delete', event)">🗑️ Delete Output</div>
</div>
```

#### 2.2 Create Delta Encoding Settings Modal

**Add to `frontend/output-settings.html`** (after DMX Monitor modal):

```html
<!-- Delta Encoding Settings Modal -->
<div id="deltaEncodingModal" class="modal">
    <div class="modal-content" style="width: 500px; max-width: 90vw;">
        <span class="close-modal" onclick="app.closeDeltaEncodingModal()">&times;</span>
        <h3>⚡ Delta Encoding Settings</h3>
        <p style="font-size: 12px; color: #888; margin-bottom: 20px;">
            Only transmit changed pixels to reduce network traffic by 50-90%
        </p>
        
        <div id="deltaEncodingContent">
            <!-- Output name display -->
            <div style="margin-bottom: 20px; padding: 10px; background: #1a1a1a; border-radius: 4px;">
                <strong id="deltaOutputName">Output Name</strong>
                <span id="deltaOutputIP" style="color: #888; margin-left: 10px; font-size: 12px;">192.168.1.10</span>
            </div>
            
            <!-- Enable toggle -->
            <div style="margin-bottom: 20px;">
                <label style="display: flex; align-items: center; cursor: pointer;">
                    <input type="checkbox" id="deltaEnabled" onchange="app.updateDeltaProperty('enabled')" 
                           style="width: 20px; height: 20px; margin-right: 10px;">
                    <span style="font-size: 14px; font-weight: bold;">Enable Delta Encoding</span>
                </label>
            </div>
            
            <!-- Threshold slider -->
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-size: 12px; color: #ccc;">
                    Change Threshold
                    <span style="color: #666; margin-left: 5px;">(pixels must change by this amount)</span>
                </label>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="range" id="deltaThreshold" min="0" max="255" value="8" 
                           oninput="app.updateDeltaDisplay('threshold')" 
                           onchange="app.updateDeltaProperty('threshold')" 
                           style="flex: 1;">
                    <span id="deltaThresholdValue" style="min-width: 120px; font-size: 14px;">8 / 255 (3.1%)</span>
                </div>
                <div style="margin-top: 8px; font-size: 11px; color: #666;">
                    <div>• 0-5: Very sensitive (sends frequently)</div>
                    <div>• 5-15: Balanced (recommended)</div>
                    <div>• 15+: Only major changes</div>
                </div>
            </div>
            
            <!-- Full frame interval -->
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px; font-size: 12px; color: #ccc;">
                    Full Frame Sync Interval
                    <span style="color: #666; margin-left: 5px;">(packet loss protection)</span>
                </label>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <input type="number" id="deltaFullFrameInterval" min="10" max="300" value="30" 
                           onchange="app.updateDeltaProperty('fullFrameInterval')" 
                           style="flex: 1; padding: 8px; background: #1a1a1a; border: 1px solid #444; 
                                  color: #fff; border-radius: 4px;">
                    <span id="deltaIntervalSeconds" style="min-width: 120px; font-size: 14px;">1.0s @ 30fps</span>
                </div>
                <div style="margin-top: 8px; font-size: 11px; color: #666;">
                    Every N frames, send complete frame to prevent desync from packet loss
                </div>
            </div>
            
            <!-- Presets -->
            <div style="margin-bottom: 20px; padding: 15px; background: #1a1a1a; border-radius: 4px;">
                <label style="display: block; margin-bottom: 10px; font-size: 12px; color: #ccc; font-weight: bold;">
                    Quick Presets
                </label>
                <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                    <button onclick="app.applyDeltaPreset('conservative')" 
                            style="padding: 6px 12px; background: #2a2a2a; border: 1px solid #444; 
                                   color: #fff; border-radius: 4px; cursor: pointer; font-size: 11px;">
                        Conservative (15, 60)
                    </button>
                    <button onclick="app.applyDeltaPreset('balanced')" 
                            style="padding: 6px 12px; background: #2a2a2a; border: 1px solid #444; 
                                   color: #fff; border-radius: 4px; cursor: pointer; font-size: 11px;">
                        Balanced (8, 30)
                    </button>
                    <button onclick="app.applyDeltaPreset('aggressive')" 
                            style="padding: 6px 12px; background: #2a2a2a; border: 1px solid #444; 
                                   color: #fff; border-radius: 4px; cursor: pointer; font-size: 11px;">
                        Aggressive (3, 15)
                    </button>
                </div>
            </div>
            
            <!-- Info panel -->
            <div style="padding: 15px; background: #1a2a1a; border: 1px solid #2a4a2a; 
                        border-radius: 4px; font-size: 12px; color: #8f8;">
                <div style="font-weight: bold; margin-bottom: 8px;">💡 Typical Results:</div>
                <div>• Static scenes: 85-95% bandwidth reduction</div>
                <div>• Slow animations: 60-80% bandwidth reduction</div>
                <div>• Fast animations: 20-40% bandwidth reduction</div>
                <div>• Rapid changes: Automatic full frame fallback</div>
            </div>
        </div>
        
        <div style="margin-top: 20px; display: flex; gap: 10px; justify-content: flex-end;">
            <button onclick="app.resetDeltaSettings()" 
                    style="padding: 10px 20px; background: #2a2a2a; border: 1px solid #444; 
                           color: #fff; border-radius: 4px; cursor: pointer;">
                Reset to Defaults
            </button>
            <button onclick="app.closeDeltaEncodingModal()" 
                    style="padding: 10px 20px; background: #0066cc; border: none; 
                           color: #fff; border-radius: 4px; cursor: pointer;">
                Close
            </button>
        </div>
    </div>
</div>
```

#### 2.3 Add JavaScript Functions

**File:** `frontend/js/output-settings.js`

```javascript
/**
 * Open delta encoding settings modal
 */
app.openDeltaEncodingModal = function(output) {
    const modal = document.getElementById('deltaEncodingModal');
    modal.style.display = 'flex';
    
    this.deltaEncodingTarget = output;
    
    // Update modal with output info
    document.getElementById('deltaOutputName').textContent = output.name || 'Output';
    document.getElementById('deltaOutputIP').textContent = `${output.targetIP} | Universe ${output.startUniverse}`;
    
    // Load current settings
    document.getElementById('deltaEnabled').checked = output.deltaEnabled || false;
    document.getElementById('deltaThreshold').value = output.deltaThreshold || 8;
    document.getElementById('deltaFullFrameInterval').value = output.fullFrameInterval || 30;
    
    // Update displays
    this.updateDeltaDisplay('threshold');
    this.updateDeltaDisplay('interval');
};

/**
 * Close delta encoding modal
 */
app.closeDeltaEncodingModal = function() {
    const modal = document.getElementById('deltaEncodingModal');
    modal.style.display = 'none';
    this.deltaEncodingTarget = null;
};

/**
 * Update delta encoding display values
 */
app.updateDeltaDisplay = function(field) {
    if (field === 'threshold') {
        const value = parseInt(document.getElementById('deltaThreshold').value);
        const percent = (value / 255 * 100).toFixed(1);
        document.getElementById('deltaThresholdValue').textContent = `${value} / 255 (${percent}%)`;
    } else if (field === 'interval') {
        const frames = parseInt(document.getElementById('deltaFullFrameInterval').value);
        const output = this.deltaEncodingTarget;
        const fps = output ? (output.fps || 30) : 30;
        const seconds = (frames / fps).toFixed(1);
        document.getElementById('deltaIntervalSeconds').textContent = `${seconds}s @ ${fps}fps`;
    }
};

/**
 * Update delta encoding property
 */
app.updateDeltaProperty = function(property) {
    if (!this.deltaEncodingTarget) return;
    
    const output = this.deltaEncodingTarget;
    
    switch (property) {
        case 'enabled':
            output.deltaEnabled = document.getElementById('deltaEnabled').checked;
            break;
        case 'threshold':
            output.deltaThreshold = parseInt(document.getElementById('deltaThreshold').value);
            break;
        case 'fullFrameInterval':
            output.fullFrameInterval = parseInt(document.getElementById('deltaFullFrameInterval').value);
            this.updateDeltaDisplay('interval');
            break;
    }
    
    // Save to backend
    this.saveRoutingOutputsToState();
    this.showToast(`Delta encoding ${property} updated`);
};

/**
 * Apply delta encoding preset
 */
app.applyDeltaPreset = function(preset) {
    const presets = {
        conservative: { threshold: 15, interval: 60 },
        balanced: { threshold: 8, interval: 30 },
        aggressive: { threshold: 3, interval: 15 }
    };
    
    const config = presets[preset];
    if (!config) return;
    
    document.getElementById('deltaThreshold').value = config.threshold;
    document.getElementById('deltaFullFrameInterval').value = config.interval;
    
    this.updateDeltaDisplay('threshold');
    this.updateDeltaDisplay('interval');
    
    this.updateDeltaProperty('threshold');
    this.updateDeltaProperty('fullFrameInterval');
    
    this.showToast(`Applied ${preset} preset`);
};

/**
 * Reset delta encoding settings to defaults
 */
app.resetDeltaSettings = function() {
    document.getElementById('deltaEnabled').checked = false;
    document.getElementById('deltaThreshold').value = 8;
    document.getElementById('deltaFullFrameInterval').value = 30;
    
    this.updateDeltaDisplay('threshold');
    this.updateDeltaDisplay('interval');
    
    this.updateDeltaProperty('enabled');
    this.updateDeltaProperty('threshold');
    this.updateDeltaProperty('fullFrameInterval');
    
    this.showToast('Delta settings reset to defaults');
};

/**
 * Handle output context menu action
 */
app.outputContextMenuAction = function(action, event) {
    // ... existing code ...
    
    switch (action) {
        case 'preview':
            this.openDmxMonitor(output);
            break;
        case 'deltaencoding':  // NEW
            this.openDeltaEncodingModal(output);
            break;
        case 'edit':
            this.editArtNetOutput(output.id);
            break;
        case 'delete':
            this.deleteArtNetOutput(output.id);
            break;
    }
};
```

---

### Phase 3: Monitoring Dashboard (Priority: MEDIUM)

#### Option A: Integrated Tab in DMX Monitor (RECOMMENDED)

**Add to DMX Monitor Modal:**

```html
<!-- Add tabs to DMX Monitor -->
<div id="dmxMonitorModal" class="modal">
    <div class="modal-content" style="width: 900px; max-width: 95vw;">
        <span class="close-modal" onclick="app.closeDmxMonitor()">&times;</span>
        <h3>DMX Monitor - <span id="dmxMonitorOutputName">Output</span></h3>
        
        <!-- NEW: Tab navigation -->
        <div style="display: flex; gap: 5px; margin-bottom: 15px; border-bottom: 1px solid #333;">
            <button id="dmxTabChannels" onclick="app.switchDmxTab('channels')" 
                    style="padding: 10px 20px; background: #333; border: none; color: #fff; 
                           cursor: pointer; border-radius: 4px 4px 0 0;">
                📊 DMX Channels
            </button>
            <button id="dmxTabDelta" onclick="app.switchDmxTab('delta')" 
                    style="padding: 10px 20px; background: #1a1a1a; border: none; color: #fff; 
                           cursor: pointer; border-radius: 4px 4px 0 0;">
                ⚡ Delta Stats
            </button>
        </div>
        
        <!-- Tab 1: DMX Channels (existing) -->
        <div id="dmxTabContentChannels" style="display: block;">
            <!-- Existing DMX channel grid content -->
        </div>
        
        <!-- Tab 2: Delta Statistics (NEW) -->
        <div id="dmxTabContentDelta" style="display: none;">
            <div style="background: #1a1a1a; padding: 20px; border-radius: 4px;">
                
                <!-- Status header -->
                <div style="display: flex; justify-content: space-between; align-items: center; 
                            margin-bottom: 20px; padding-bottom: 15px; border-bottom: 1px solid #333;">
                    <div>
                        <div style="font-size: 18px; font-weight: bold; margin-bottom: 5px;">
                            <span id="deltaStatusIcon">⚪</span>
                            <span id="deltaStatusText">Disabled</span>
                        </div>
                        <div style="font-size: 12px; color: #888;">
                            <span id="deltaStatusDetail">Enable in output settings</span>
                        </div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 24px; font-weight: bold; color: #0066cc;">
                            <span id="deltaEfficiency">--%</span>
                        </div>
                        <div style="font-size: 11px; color: #666;">Network Savings</div>
                    </div>
                </div>
                
                <!-- Statistics grid -->
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; 
                            margin-bottom: 20px;">
                    <!-- Current frame info -->
                    <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                        <div style="font-size: 11px; color: #888; margin-bottom: 5px;">Current Frame</div>
                        <div style="font-size: 20px; font-weight: bold;">
                            <span id="deltaCurrentFrame">0</span>
                        </div>
                    </div>
                    
                    <!-- Changed pixels -->
                    <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                        <div style="font-size: 11px; color: #888; margin-bottom: 5px;">Changed Pixels</div>
                        <div style="font-size: 20px; font-weight: bold;">
                            <span id="deltaChangedPixels">0</span>
                            <span style="font-size: 12px; color: #666;"> / 512</span>
                        </div>
                        <div style="font-size: 11px; color: #666; margin-top: 5px;">
                            <span id="deltaChangedPercent">0.0%</span> changed
                        </div>
                    </div>
                    
                    <!-- Decision type -->
                    <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                        <div style="font-size: 11px; color: #888; margin-bottom: 5px;">Last Decision</div>
                        <div style="font-size: 16px; font-weight: bold;">
                            <span id="deltaLastDecision">-</span>
                        </div>
                    </div>
                </div>
                
                <!-- Frame type breakdown -->
                <div style="background: #2a2a2a; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 10px; font-weight: bold;">
                        Frame Type Distribution
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px;">
                        <div>
                            <div style="font-size: 11px; color: #888;">Delta Frames (Δ)</div>
                            <div style="font-size: 18px; font-weight: bold; color: #4a4;">
                                <span id="deltaDeltaFrames">0</span>
                                <span style="font-size: 12px; color: #666;">
                                    (<span id="deltaDeltaPercent">0%</span>)
                                </span>
                            </div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #888;">Full Frames (⬛)</div>
                            <div style="font-size: 18px; font-weight: bold; color: #c66;">
                                <span id="deltaFullFrames">0</span>
                                <span style="font-size: 12px; color: #666;">
                                    (<span id="deltaFullPercent">0%</span>)
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Bandwidth savings -->
                <div style="background: #2a2a2a; padding: 15px; border-radius: 4px; margin-bottom: 20px;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 10px; font-weight: bold;">
                        Bandwidth Analysis
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px;">
                        <div>
                            <div style="font-size: 11px; color: #666;">Total Sent</div>
                            <div style="font-size: 16px; font-weight: bold;">
                                <span id="deltaTotalBytes">0</span> KB
                            </div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #666;">Bytes Saved</div>
                            <div style="font-size: 16px; font-weight: bold; color: #4a4;">
                                <span id="deltaSavedBytes">0</span> KB
                            </div>
                        </div>
                        <div>
                            <div style="font-size: 11px; color: #666;">Next Full Frame</div>
                            <div style="font-size: 16px; font-weight: bold;">
                                <span id="deltaNextFull">-</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Recent activity log -->
                <div style="background: #2a2a2a; padding: 15px; border-radius: 4px;">
                    <div style="font-size: 11px; color: #888; margin-bottom: 10px; font-weight: bold;">
                        Recent Activity (Last 20 Frames)
                    </div>
                    <div id="deltaHistoryLog" style="font-family: 'Courier New', monospace; 
                         font-size: 11px; max-height: 200px; overflow-y: auto;">
                        <div style="color: #666;">No activity yet</div>
                    </div>
                </div>
                
                <!-- Legend -->
                <div style="margin-top: 15px; padding: 10px; background: #151515; border-radius: 4px; 
                            font-size: 11px; color: #888;">
                    <strong>Legend:</strong>
                    <span style="margin-left: 15px;">Δ = Delta update (changed pixels only)</span>
                    <span style="margin-left: 15px;">⬛ = Full frame (many changes)</span>
                    <span style="margin-left: 15px;">🔄 = Full frame (periodic sync)</span>
                </div>
            </div>
        </div>
    </div>
</div>
```

**JavaScript for Dashboard:**

```javascript
/**
 * Switch DMX monitor tab
 */
app.switchDmxTab = function(tab) {
    // Update tab buttons
    document.getElementById('dmxTabChannels').style.background = tab === 'channels' ? '#333' : '#1a1a1a';
    document.getElementById('dmxTabDelta').style.background = tab === 'delta' ? '#333' : '#1a1a1a';
    
    // Show/hide content
    document.getElementById('dmxTabContentChannels').style.display = tab === 'channels' ? 'block' : 'none';
    document.getElementById('dmxTabContentDelta').style.display = tab === 'delta' ? 'block' : 'none';
    
    // Start updating delta stats if on delta tab
    if (tab === 'delta') {
        this.startDeltaStatsUpdates();
    } else {
        this.stopDeltaStatsUpdates();
    }
};

/**
 * Update delta statistics display
 */
app.updateDeltaStats = function(data) {
    if (!data) return;
    
    // Status
    const statusIcon = document.getElementById('deltaStatusIcon');
    const statusText = document.getElementById('deltaStatusText');
    const statusDetail = document.getElementById('deltaStatusDetail');
    
    if (data.enabled) {
        statusIcon.textContent = '🟢';
        statusText.textContent = 'Active';
        
        if (data.last_decision === 'delta') {
            statusDetail.textContent = `Delta mode: ${data.current_changed_percent.toFixed(1)}% changed`;
        } else if (data.last_decision === 'full' || data.last_decision === 'too_many_changes') {
            statusDetail.textContent = `Full frame: ${data.current_changed_percent.toFixed(1)}% changed (threshold exceeded)`;
        } else if (data.last_decision === 'sync') {
            statusDetail.textContent = 'Full frame: Periodic sync';
        }
    } else {
        statusIcon.textContent = '⚪';
        statusText.textContent = 'Disabled';
        statusDetail.textContent = 'Enable in output context menu → Delta Encoding';
    }
    
    // Efficiency
    document.getElementById('deltaEfficiency').textContent = 
        data.efficiency_percent ? `${data.efficiency_percent.toFixed(1)}%` : '--';
    
    // Current frame info
    document.getElementById('deltaCurrentFrame').textContent = data.total_frames || 0;
    document.getElementById('deltaChangedPixels').textContent = data.current_changed_pixels || 0;
    document.getElementById('deltaChangedPercent').textContent = 
        (data.current_changed_percent || 0).toFixed(1) + '%';
    
    // Last decision
    const decisionMap = {
        'delta': '✓ Delta Update',
        'full': '⬛ Full Frame',
        'too_many_changes': '⬛ Full (Many Changes)',
        'sync': '🔄 Full (Sync)',
        'first': '⬛ Full (First)',
        'disabled': '- Disabled'
    };
    document.getElementById('deltaLastDecision').textContent = 
        decisionMap[data.last_decision] || '-';
    
    // Frame type distribution
    document.getElementById('deltaDeltaFrames').textContent = data.delta_frames || 0;
    document.getElementById('deltaDeltaPercent').textContent = 
        (data.delta_ratio || 0).toFixed(1) + '%';
    document.getElementById('deltaFullFrames').textContent = data.full_frames || 0;
    document.getElementById('deltaFullPercent').textContent = 
        (data.full_ratio || 0).toFixed(1) + '%';
    
    // Bandwidth
    document.getElementById('deltaTotalBytes').textContent = 
        ((data.total_bytes || 0) / 1024).toFixed(1);
    document.getElementById('deltaSavedBytes').textContent = 
        ((data.bytes_saved || 0) / 1024).toFixed(1);
    
    // Next full frame
    if (data.enabled && data.full_frame_interval) {
        const framesUntilFull = data.full_frame_interval - (data.total_frames % data.full_frame_interval);
        document.getElementById('deltaNextFull').textContent = `${framesUntilFull} frames`;
    } else {
        document.getElementById('deltaNextFull').textContent = '-';
    }
    
    // History log
    if (data.history && data.history.length > 0) {
        const historyHtml = data.history.slice(-20).reverse().map(entry => {
            const [frameNum, changedPx, decision] = entry;
            const icon = decision === 'delta' ? 'Δ' : decision === 'sync' ? '🔄' : '⬛';
            const percent = ((changedPx / 512) * 100).toFixed(1);
            const color = decision === 'delta' ? '#4a4' : '#c66';
            
            return `<div style="padding: 3px 0; color: ${color};">
                Frame ${String(frameNum).padStart(5)}: ${String(changedPx).padStart(3)} px (${String(percent).padStart(5)}%) → ${icon}
            </div>`;
        }).join('');
        
        document.getElementById('deltaHistoryLog').innerHTML = historyHtml;
    }
};
```

---

### Phase 4: REST API & Socket.IO (Priority: HIGH)

#### 4.1 Add API Endpoints

**File:** `src/modules/api_routes.py`

```python
@app.route('/api/routing/delta-stats/<output_id>', methods=['GET'])
def get_delta_stats(output_id):
    """Get delta encoding statistics for an output"""
    try:
        if not hasattr(app_state, 'artnet_player') or not app_state.artnet_player:
            return jsonify({'error': 'ArtNet player not initialized'}), 503
        
        routing_bridge = app_state.artnet_player.routing_bridge
        if not routing_bridge:
            return jsonify({'error': 'Routing bridge not available'}), 503
        
        stats = routing_bridge.sender.get_delta_stats(output_id)
        if stats is None:
            return jsonify({'error': 'Output not found or no statistics available'}), 404
        
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting delta stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/routing/delta-stats', methods=['GET'])
def get_all_delta_stats():
    """Get delta encoding statistics for all outputs"""
    try:
        if not hasattr(app_state, 'artnet_player') or not app_state.artnet_player:
            return jsonify({'error': 'ArtNet player not initialized'}), 503
        
        routing_bridge = app_state.artnet_player.routing_bridge
        if not routing_bridge:
            return jsonify({'error': 'Routing bridge not available'}), 503
        
        all_stats = {}
        for output_id in routing_bridge.sender.senders.keys():
            stats = routing_bridge.sender.get_delta_stats(output_id)
            if stats:
                all_stats[output_id] = stats
        
        return jsonify(all_stats)
    except Exception as e:
        logger.error(f"Error getting all delta stats: {e}")
        return jsonify({'error': str(e)}), 500
```

#### 4.2 Add Socket.IO Broadcasts

**File:** `src/modules/rest_api.py`

```python
def _get_status_data():
    """Get status data including delta encoding stats"""
    # ... existing code ...
    
    # Add delta encoding stats
    if hasattr(app_state, 'artnet_player') and app_state.artnet_player:
        routing_bridge = getattr(app_state.artnet_player, 'routing_bridge', None)
        if routing_bridge:
            delta_stats = {}
            for output_id in routing_bridge.sender.senders.keys():
                stats = routing_bridge.sender.get_delta_stats(output_id)
                if stats:
                    delta_stats[output_id] = stats
            
            status_data['delta_stats'] = delta_stats
    
    return status_data
```

---

## 📈 Expected Performance

### Bandwidth Reduction by Scene Type

| Scene Type | Change Rate | Delta Efficiency | Bandwidth Saved |
|------------|-------------|------------------|-----------------|
| Static | 0-5% | 85-95% | 85-95% |
| Slow fade | 5-15% | 70-85% | 70-85% |
| Medium animation | 15-40% | 50-70% | 50-70% |
| Fast animation | 40-70% | 20-40% | 20-40% |
| Rapid changes | >70% | <20% (auto fallback) | Minimal |

### Network Traffic Example

**Scenario:** 512 LEDs (RGB), 30 FPS, static background with 5% moving elements

- **Without Delta:** 512 × 3 × 30 = 46,080 bytes/sec = **45 KB/s**
- **With Delta (5% changed):** 512 × 0.05 × 3 × 30 = 2,304 bytes/sec = **2.25 KB/s**
- **Savings:** 43,776 bytes/sec = **95.0% reduction**

---

## ⚠️ Limitations & Future Improvements

### Current Limitations

1. **stupidArtnet Library:** Doesn't support partial packet updates natively
   - Currently sends full frames but tracks theoretical savings
   - Real packet-level optimization would require raw socket implementation

2. **No Smart Channel Grouping:** Could optimize by grouping RGB channels
   - Example: If R changes but GB don't, could send selective updates

3. **Fixed Threshold:** Single threshold for all channels
   - Could implement per-channel thresholds (R more sensitive than B)

### Future Enhancements

1. **Raw Socket Implementation:**
   ```python
   # Send only changed channels via custom ArtNet packet
   def send_sparse_dmx(self, universe, changed_indices, values):
       """Send ArtNet packet with only changed channels"""
       # Build custom ArtNet packet with sparse data
       pass
   ```

2. **Predictive Delta Encoding:**
   - Learn animation patterns
   - Pre-calculate expected changes
   - Adjust threshold dynamically

3. **Multi-Universe Optimization:**
   - Coordinate delta encoding across universes
   - Prioritize universes with more changes

4. **Compression Integration:**
   - Combine with run-length encoding for static regions
   - Use LZ4 for changed pixel blocks

---

## 🔧 Testing Strategy

### Unit Tests

```python
def test_delta_diff_calculation():
    """Test diff calculation accuracy"""
    current = bytes([100, 150, 200] * 10)
    previous = bytes([100, 150, 200] * 10)
    
    changed, percent = sender._calculate_diff(current, previous, threshold=8)
    assert changed == 0
    assert percent == 0.0

def test_delta_threshold_detection():
    """Test threshold-based change detection"""
    current = bytes([100, 150, 200] * 10)
    previous = bytes([100, 142, 200] * 10)  # Middle value changed by 8
    
    changed, percent = sender._calculate_diff(current, previous, threshold=8)
    assert changed == 0  # 8 is NOT exceeding threshold (must be >8)
```

### Integration Tests

1. Test full frame fallback at 80% threshold
2. Test periodic sync at full_frame_interval
3. Verify statistics accuracy
4. Test Socket.IO broadcast with delta stats

### Manual Testing Scenarios

1. **Static Scene:** Show maximum bandwidth savings
2. **Moving Object:** Verify delta updates for changed regions
3. **Flash Effect:** Confirm full frame fallback on rapid changes
4. **Long Running:** Check periodic sync behavior over 5+ minutes

---

## 📋 Implementation Checklist

### Backend (4-5 hours)
- [ ] Add delta state tracking to `ArtNetSender`
- [ ] Implement `send_dmx_with_delta()` method
- [ ] Implement `_calculate_diff()` helper
- [ ] Implement `_send_full_frame()` with statistics
- [ ] Implement `_send_delta_update()` with statistics
- [ ] Add `get_delta_stats()` method
- [ ] Update `configure_output()` to initialize stats
- [ ] Update `routing_bridge.py` to use delta-aware sending
- [ ] Add REST API endpoints for delta stats
- [ ] Add Socket.IO broadcast for delta stats
- [ ] Write unit tests
- [ ] Write integration tests

### Frontend (2-3 hours)
- [ ] Add context menu option
- [ ] Create delta encoding settings modal
- [ ] Implement modal JavaScript functions
- [ ] Add dashboard tab to DMX Monitor
- [ ] Implement dashboard update functions
- [ ] Add Socket.IO listener for delta stats
- [ ] Test modal interactions
- [ ] Test dashboard real-time updates

### Documentation (30 minutes)
- [ ] Update `DELTA_ENCODING.md` with new routing system details
- [ ] Update `API.md` with new endpoints
- [ ] Add user guide section to `README.md`

### Testing (1 hour)
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Manual testing with various scene types
- [ ] Performance profiling
- [ ] Network traffic verification with Wireshark

---

## 🎯 Success Criteria

✅ **Implementation Complete When:**

1. Per-output delta encoding can be enabled/disabled via GUI
2. Threshold and interval are configurable per output
3. Backend correctly calculates and applies delta logic
4. Statistics are tracked and available via API
5. Dashboard shows real-time delta encoding activity
6. Network traffic measurably reduced (verify with Wireshark)
7. No performance degradation in rendering pipeline
8. All tests passing

✅ **User Experience Complete When:**

1. User can quickly enable delta for an output (2 clicks)
2. User can see immediate feedback on bandwidth savings
3. Dashboard clearly shows what delta encoding is doing
4. Presets make configuration easy for non-technical users
5. Help text explains when to use different settings

---

## 📞 Questions for Implementation

Before starting implementation, clarify:

1. **stupidArtnet Limitation:** Accept that we track savings but can't actually send partial packets, OR implement raw socket ArtNet sender?

2. **Default Behavior:** Should delta encoding be enabled by default for new outputs?

3. **Global vs Per-Output:** Keep both global config (session_state.json) AND per-output settings? Or remove global config?

4. **Monitoring Persistence:** Should delta statistics persist across restarts? Or start fresh each session?

5. **Dashboard Location:** Confirm integrated tab in DMX Monitor is preferred over separate modal?

---

**End of Implementation Plan**

This document provides complete specifications for implementing delta encoding in the new ArtNet routing system. Return to this document when ready to implement.
