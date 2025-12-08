# WebSocket Command Channel - Implementation Plan

**Feature:** Hybrid REST/WebSocket Architecture for zeitkritische Commands  
**Priority:** P1 (High Impact Performance Optimization)  
**Estimated Time:** 6-8 hours  
**Target:** 20-50x faster command execution (50-100ms → 2-5ms)

---

## 🎯 Executive Summary

Replace polling-based REST endpoints with event-driven WebSocket commands for:
- **Effect parameter updates** (live sliders)
- **Layer opacity/blend mode** (real-time compositing)
- **Transport controls** (play/pause/stop/next/prev)
- **Status broadcasts** (push instead of poll)

**Architecture Decision:** Hybrid approach - REST for data operations, WebSocket for commands & live updates.

---

## 📋 Phase Breakdown

### Phase 1: Backend WebSocket Infrastructure (2-3h)

#### 1.1 WebSocket Namespace Setup (30min)
**File:** `src/modules/rest_api.py`

**Current State:**
```python
# Line 285: Flask-SocketIO already initialized
self.socketio = SocketIO(
    self.app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False
)
```

**Tasks:**
- [x] SocketIO already initialized ✅
- [ ] Add command namespaces:
  ```python
  # Add after line 95 (self.socketio initialization)
  
  # WebSocket command handlers
  @self.socketio.on('connect', namespace='/player')
  def handle_player_connect():
      logger.info(f"Client connected to /player namespace: {request.sid}")
      emit('connected', {'status': 'ready'})
  
  @self.socketio.on('disconnect', namespace='/player')
  def handle_player_disconnect():
      logger.info(f"Client disconnected from /player namespace: {request.sid}")
  
  @self.socketio.on('connect', namespace='/effects')
  def handle_effects_connect():
      logger.info(f"Client connected to /effects namespace: {request.sid}")
      emit('connected', {'status': 'ready'})
  
  @self.socketio.on('connect', namespace='/layers')
  def handle_layers_connect():
      logger.info(f"Client connected to /layers namespace: {request.sid}")
      emit('connected', {'status': 'ready'})
  ```

**Files to modify:**
- `src/modules/rest_api.py` (lines 90-100, add namespace handlers)

---

#### 1.2 Command Handler Infrastructure (1h)
**File:** `src/modules/rest_api.py`

**New Method:** Add command routing system
```python
def _setup_websocket_handlers(self):
    """Setup WebSocket command handlers."""
    
    # ========================================
    # PLAYER COMMANDS (play, pause, stop, etc.)
    # ========================================
    @self.socketio.on('command.play', namespace='/player')
    def handle_play(data):
        """Handle play command via WebSocket."""
        player_id = data.get('player_id', 'video')
        try:
            player = self.player_manager.get_player(player_id)
            if player:
                player.play()
                emit('command.response', {
                    'success': True,
                    'command': 'play',
                    'player_id': player_id
                }, namespace='/player')
                # Broadcast status change to all clients
                self.socketio.emit('player.status', {
                    'player_id': player_id,
                    'is_playing': True,
                    'is_paused': False
                }, namespace='/player')
        except Exception as e:
            emit('command.error', {
                'command': 'play',
                'error': str(e)
            }, namespace='/player')
    
    @self.socketio.on('command.pause', namespace='/player')
    def handle_pause(data):
        """Handle pause command via WebSocket."""
        player_id = data.get('player_id', 'video')
        try:
            player = self.player_manager.get_player(player_id)
            if player:
                player.pause()
                emit('command.response', {'success': True, 'command': 'pause'})
                self.socketio.emit('player.status', {
                    'player_id': player_id,
                    'is_paused': True
                }, namespace='/player')
        except Exception as e:
            emit('command.error', {'command': 'pause', 'error': str(e)})
    
    @self.socketio.on('command.stop', namespace='/player')
    def handle_stop(data):
        """Handle stop command via WebSocket."""
        player_id = data.get('player_id', 'video')
        try:
            player = self.player_manager.get_player(player_id)
            if player:
                player.stop()
                emit('command.response', {'success': True, 'command': 'stop'})
                self.socketio.emit('player.status', {
                    'player_id': player_id,
                    'is_playing': False,
                    'is_paused': False
                }, namespace='/player')
        except Exception as e:
            emit('command.error', {'command': 'stop', 'error': str(e)})
    
    @self.socketio.on('command.next', namespace='/player')
    def handle_next(data):
        """Handle next clip command via WebSocket."""
        player_id = data.get('player_id', 'video')
        try:
            player = self.player_manager.get_player(player_id)
            if player and hasattr(player, 'next_clip'):
                player.next_clip()
                emit('command.response', {'success': True, 'command': 'next'})
                # Broadcast playlist change
                self.socketio.emit('playlist.changed', {
                    'player_id': player_id,
                    'current_index': player.playlist_index
                }, namespace='/player')
        except Exception as e:
            emit('command.error', {'command': 'next', 'error': str(e)})
    
    @self.socketio.on('command.previous', namespace='/player')
    def handle_previous(data):
        """Handle previous clip command via WebSocket."""
        player_id = data.get('player_id', 'video')
        try:
            player = self.player_manager.get_player(player_id)
            if player and hasattr(player, 'previous_clip'):
                player.previous_clip()
                emit('command.response', {'success': True, 'command': 'previous'})
                self.socketio.emit('playlist.changed', {
                    'player_id': player_id,
                    'current_index': player.playlist_index
                }, namespace='/player')
        except Exception as e:
            emit('command.error', {'command': 'previous', 'error': str(e)})
    
    # ========================================
    # EFFECT PARAMETER COMMANDS
    # ========================================
    @self.socketio.on('command.effect.param', namespace='/effects')
    def handle_effect_param_update(data):
        """Handle effect parameter update via WebSocket."""
        player_id = data.get('player_id')
        clip_id = data.get('clip_id')
        effect_index = data.get('effect_index')
        param_name = data.get('param_name')
        value = data.get('value')
        
        try:
            # Call existing API logic
            from .api_routes import update_effect_parameter
            result = update_effect_parameter(
                player_id, clip_id, effect_index, param_name, value
            )
            
            emit('command.response', {
                'success': True,
                'command': 'effect.param',
                'effect_index': effect_index,
                'param_name': param_name,
                'value': value
            })
            
            # Broadcast to all clients for multi-user sync
            self.socketio.emit('effect.param.changed', {
                'player_id': player_id,
                'clip_id': clip_id,
                'effect_index': effect_index,
                'param_name': param_name,
                'value': value
            }, namespace='/effects')
        except Exception as e:
            emit('command.error', {
                'command': 'effect.param',
                'error': str(e)
            })
    
    # ========================================
    # LAYER COMMANDS
    # ========================================
    @self.socketio.on('command.layer.opacity', namespace='/layers')
    def handle_layer_opacity(data):
        """Handle layer opacity update via WebSocket."""
        player_id = data.get('player_id')
        clip_id = data.get('clip_id')
        layer_id = data.get('layer_id')
        opacity = data.get('opacity')
        
        try:
            player = self.player_manager.get_player(player_id)
            if player and player.layers and layer_id < len(player.layers):
                player.layers[layer_id].opacity = opacity / 100.0
                
                emit('command.response', {
                    'success': True,
                    'command': 'layer.opacity',
                    'layer_id': layer_id,
                    'opacity': opacity
                })
                
                # Broadcast to all clients
                self.socketio.emit('layer.changed', {
                    'player_id': player_id,
                    'clip_id': clip_id,
                    'layer_id': layer_id,
                    'opacity': opacity
                }, namespace='/layers')
        except Exception as e:
            emit('command.error', {'command': 'layer.opacity', 'error': str(e)})
    
    @self.socketio.on('command.layer.blend_mode', namespace='/layers')
    def handle_layer_blend_mode(data):
        """Handle layer blend mode update via WebSocket."""
        player_id = data.get('player_id')
        clip_id = data.get('clip_id')
        layer_id = data.get('layer_id')
        blend_mode = data.get('blend_mode')
        
        try:
            player = self.player_manager.get_player(player_id)
            if player and player.layers and layer_id < len(player.layers):
                player.layers[layer_id].blend_mode = blend_mode
                
                emit('command.response', {
                    'success': True,
                    'command': 'layer.blend_mode',
                    'layer_id': layer_id,
                    'blend_mode': blend_mode
                })
                
                self.socketio.emit('layer.changed', {
                    'player_id': player_id,
                    'clip_id': clip_id,
                    'layer_id': layer_id,
                    'blend_mode': blend_mode
                }, namespace='/layers')
        except Exception as e:
            emit('command.error', {'command': 'layer.blend_mode', 'error': str(e)})
```

**Integration Point:**
```python
# In __init__ method, after socketio initialization (line ~95):
self._setup_websocket_handlers()
```

**Files to modify:**
- `src/modules/rest_api.py` (add new method `_setup_websocket_handlers()`)

---

#### 1.3 Event Broadcasting System (30min)
**File:** `src/modules/player.py`

**Task:** Add WebSocket event emission to Player state changes

**Integration points:**
```python
# In Player.play() method (around line 550):
def play(self):
    """Startet die Wiedergabe."""
    if not self.is_playing:
        self.is_playing = True
        self.is_paused = False
        self.pause_event.set()
        
        # NEW: Broadcast via WebSocket
        if hasattr(self, 'rest_api') and self.rest_api:
            self.rest_api.socketio.emit('player.status', {
                'player_id': self.player_id,
                'is_playing': True,
                'is_paused': False
            }, namespace='/player')
        
        if not self.play_thread or not self.play_thread.is_alive():
            self.play_thread = threading.Thread(target=self._play_loop, daemon=True)
            self.play_thread.start()

# Similar for pause(), stop(), etc.
```

**Files to modify:**
- `src/modules/player.py` (lines ~550, ~560, ~565 - play/pause/stop methods)

---

### Phase 2: Frontend WebSocket Client (2-3h)

#### 2.1 WebSocket Connection Manager (1h)
**File:** `frontend/js/common.js`

**Current State:**
```javascript
// Line ~30: Socket.IO already imported and initialized
const socket = io('/', {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});
```

**Tasks:**
- [ ] Add namespace connections:
```javascript
// Add after existing socket initialization (line ~40)

// WebSocket Command Channels
const playerSocket = io('/player', {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

const effectsSocket = io('/effects', {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

const layersSocket = io('/layers', {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

// Connection status tracking
let isPlayerSocketConnected = false;
let isEffectsSocketConnected = false;
let isLayersSocketConnected = false;

// Connection handlers
playerSocket.on('connect', () => {
    console.log('✅ Player WebSocket connected');
    isPlayerSocketConnected = true;
});

playerSocket.on('disconnect', () => {
    console.log('❌ Player WebSocket disconnected');
    isPlayerSocketConnected = false;
});

effectsSocket.on('connect', () => {
    console.log('✅ Effects WebSocket connected');
    isEffectsSocketConnected = true;
});

effectsSocket.on('disconnect', () => {
    console.log('❌ Effects WebSocket disconnected');
    isEffectsSocketConnected = false;
});

layersSocket.on('connect', () => {
    console.log('✅ Layers WebSocket connected');
    isLayersSocketConnected = true;
});

layersSocket.on('disconnect', () => {
    console.log('❌ Layers WebSocket disconnected');
    isLayersSocketConnected = false;
});

// Export sockets for use in other modules
window.playerSocket = playerSocket;
window.effectsSocket = effectsSocket;
window.layersSocket = layersSocket;
window.isPlayerSocketConnected = () => isPlayerSocketConnected;
window.isEffectsSocketConnected = () => isEffectsSocketConnected;
window.isLayersSocketConnected = () => isLayersSocketConnected;
```

**Files to modify:**
- `frontend/js/common.js` (lines ~40-50, add namespace connections)

---

#### 2.2 Hybrid Command Router (1h)
**File:** `frontend/js/common.js`

**New Function:** Smart routing between WebSocket and REST

```javascript
/**
 * Hybrid command executor - tries WebSocket first, falls back to REST
 * @param {string} namespace - WebSocket namespace ('player', 'effects', 'layers')
 * @param {string} event - WebSocket event name (e.g., 'command.play')
 * @param {object} data - Command payload
 * @param {function} restFallback - REST API fallback function
 * @returns {Promise<object>} Command result
 */
async function executeCommand(namespace, event, data, restFallback) {
    // Get appropriate socket
    const socketMap = {
        'player': playerSocket,
        'effects': effectsSocket,
        'layers': layersSocket
    };
    
    const connectionMap = {
        'player': isPlayerSocketConnected,
        'effects': isEffectsSocketConnected,
        'layers': isLayersSocketConnected
    };
    
    const socket = socketMap[namespace];
    const isConnected = connectionMap[namespace];
    
    // Try WebSocket first (if connected)
    if (isConnected && socket) {
        try {
            return await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('WebSocket command timeout'));
                }, 5000); // 5 second timeout
                
                // Listen for response
                socket.once('command.response', (response) => {
                    clearTimeout(timeout);
                    resolve(response);
                });
                
                socket.once('command.error', (error) => {
                    clearTimeout(timeout);
                    reject(error);
                });
                
                // Send command
                socket.emit(event, data);
            });
        } catch (error) {
            console.warn(`WebSocket command failed, falling back to REST:`, error);
            // Fall through to REST fallback
        }
    }
    
    // Fallback to REST
    if (restFallback) {
        return await restFallback();
    } else {
        throw new Error('No REST fallback provided and WebSocket unavailable');
    }
}

// Export for use in other modules
window.executeCommand = executeCommand;
```

**Files to modify:**
- `frontend/js/common.js` (add new `executeCommand()` function)

---

#### 2.3 Player Controls Integration (30min)
**File:** `frontend/js/player.js`

**Task:** Replace REST calls with hybrid commands

**Current Code (example - line ~2130):**
```javascript
window.play = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    await fetch(`${API_BASE}${config.apiBase}/play`, { method: 'POST' });
};
```

**New Code:**
```javascript
window.play = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    // Hybrid: Try WebSocket first, fallback to REST
    await executeCommand(
        'player',
        'command.play',
        { player_id: playerId },
        async () => {
            // REST fallback
            await fetch(`${API_BASE}${config.apiBase}/play`, { method: 'POST' });
        }
    );
};

window.pause = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    await executeCommand(
        'player',
        'command.pause',
        { player_id: playerId },
        async () => {
            await fetch(`${API_BASE}${config.apiBase}/pause`, { method: 'POST' });
        }
    );
};

window.stop = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    await executeCommand(
        'player',
        'command.stop',
        { player_id: playerId },
        async () => {
            await fetch(`${API_BASE}${config.apiBase}/stop`, { method: 'POST' });
        }
    );
};

window.next = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    await executeCommand(
        'player',
        'command.next',
        { player_id: playerId },
        async () => {
            const response = await fetch(`${API_BASE}${config.apiBase}/next`, { method: 'POST' });
            return await response.json();
        }
    );
};

window.previous = async function(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    await executeCommand(
        'player',
        'command.previous',
        { player_id: playerId },
        async () => {
            const response = await fetch(`${API_BASE}${config.apiBase}/previous`, { method: 'POST' });
            return await response.json();
        }
    );
};
```

**Files to modify:**
- `frontend/js/player.js` (lines ~2130-2200, update play/pause/stop/next/previous functions)

---

#### 2.4 Effect Parameter Integration (30min)
**File:** `frontend/js/player.js`

**Task:** Replace effect parameter REST calls with WebSocket

**Current Code (example - around line 3400):**
```javascript
// In triple-slider onChange handler:
const response = await fetch(`${API_BASE}/api/player/${player}/clip/${targetClipId}/effects/${effectIndex}/parameter`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        parameter: paramName,
        value: value
    })
});
```

**New Code:**
```javascript
// In triple-slider onChange handler:
await executeCommand(
    'effects',
    'command.effect.param',
    {
        player_id: player,
        clip_id: targetClipId,
        effect_index: effectIndex,
        param_name: paramName,
        value: value
    },
    async () => {
        // REST fallback
        const response = await fetch(`${API_BASE}/api/player/${player}/clip/${targetClipId}/effects/${effectIndex}/parameter`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                parameter: paramName,
                value: value
            })
        });
        return await response.json();
    }
);
```

**Files to modify:**
- `frontend/js/player.js` (find all effect parameter update calls and wrap with `executeCommand()`)

---

#### 2.5 Layer Opacity/Blend Mode Integration (30min)
**File:** `frontend/js/player.js`

**Task:** Replace layer update REST calls with WebSocket

**Current Code (example):**
```javascript
// Layer opacity update:
await fetch(`${API_BASE}/api/player/${playerId}/clip/${clipId}/layers/${layerId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ opacity: opacity })
});
```

**New Code:**
```javascript
// Layer opacity update:
await executeCommand(
    'layers',
    'command.layer.opacity',
    {
        player_id: playerId,
        clip_id: clipId,
        layer_id: layerId,
        opacity: opacity
    },
    async () => {
        // REST fallback
        const response = await fetch(`${API_BASE}/api/player/${playerId}/clip/${clipId}/layers/${layerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ opacity: opacity })
        });
        return await response.json();
    }
);

// Similar for blend mode updates
```

**Files to modify:**
- `frontend/js/player.js` (find all layer update calls and wrap with `executeCommand()`)

---

### Phase 3: Event-Driven Status Updates (1h)

#### 3.1 Replace Status Polling with WebSocket Events (1h)
**File:** `frontend/js/player.js`

**Current Code (line ~200):**
```javascript
updateInterval = setInterval(async () => {
    const now = Date.now();
    
    // Effect refresh every 2000ms
    if (now - lastEffectRefresh >= EFFECT_REFRESH_INTERVAL) {
        await refreshVideoEffects();
        await refreshArtnetEffects();
        lastEffectRefresh = now;
    }
    
    // ... other polling logic
}, 250);
```

**New Code:**
```javascript
// Replace polling with event listeners

// Listen for player status changes
playerSocket.on('player.status', (data) => {
    const playerId = data.player_id;
    const config = playerConfigs[playerId];
    
    if (config) {
        // Update UI based on status
        if (data.is_playing !== undefined) {
            // Update play button state
            updatePlayButtonState(playerId, data.is_playing, data.is_paused);
        }
    }
});

// Listen for playlist changes
playerSocket.on('playlist.changed', (data) => {
    const playerId = data.player_id;
    renderPlaylist(playerId);
});

// Listen for effect changes
effectsSocket.on('effect.param.changed', (data) => {
    // Update UI to reflect parameter change (multi-user sync)
    const { player_id, clip_id, effect_index, param_name, value } = data;
    updateEffectParameterUI(player_id, clip_id, effect_index, param_name, value);
});

// Listen for layer changes
layersSocket.on('layer.changed', (data) => {
    // Update UI to reflect layer change (multi-user sync)
    const { player_id, clip_id, layer_id, opacity, blend_mode } = data;
    updateLayerUI(player_id, clip_id, layer_id, opacity, blend_mode);
});

// Keep reduced polling for things that still need it (effect list refresh, etc.)
updateInterval = setInterval(async () => {
    const now = Date.now();
    
    // Only poll for non-critical updates
    if (now - lastEffectRefresh >= EFFECT_REFRESH_INTERVAL) {
        await refreshVideoEffects();
        await refreshArtnetEffects();
        lastEffectRefresh = now;
    }
}, 2000); // Increased interval since most updates come via WebSocket
```

**Files to modify:**
- `frontend/js/player.js` (lines ~190-230, replace polling with event listeners)

---

### Phase 4: Testing & Optimization (1-2h)

#### 4.1 Latency Benchmarking (30min)

**Create:** `tests/benchmark_websocket_latency.py`

```python
"""
Benchmark WebSocket vs REST latency
"""
import time
import asyncio
import requests
from socketio import Client

def benchmark_rest_latency(iterations=100):
    """Benchmark REST API latency."""
    latencies = []
    
    for _ in range(iterations):
        start = time.time()
        response = requests.post('http://localhost:5000/api/player/video/play')
        latency = (time.time() - start) * 1000  # ms
        latencies.append(latency)
    
    avg = sum(latencies) / len(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"REST API Latency:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  Min: {min_lat:.2f}ms")
    print(f"  Max: {max_lat:.2f}ms")
    
    return avg

def benchmark_websocket_latency(iterations=100):
    """Benchmark WebSocket command latency."""
    sio = Client()
    latencies = []
    
    @sio.on('command.response', namespace='/player')
    def on_response(data):
        end = time.time()
        latency = (end - response_start[0]) * 1000  # ms
        latencies.append(latency)
    
    response_start = [0]
    
    sio.connect('http://localhost:5000', namespaces=['/player'])
    
    for _ in range(iterations):
        response_start[0] = time.time()
        sio.emit('command.play', {'player_id': 'video'}, namespace='/player')
        time.sleep(0.01)  # Small delay between commands
    
    time.sleep(1)  # Wait for all responses
    sio.disconnect()
    
    avg = sum(latencies) / len(latencies)
    min_lat = min(latencies)
    max_lat = max(latencies)
    
    print(f"WebSocket Latency:")
    print(f"  Average: {avg:.2f}ms")
    print(f"  Min: {min_lat:.2f}ms")
    print(f"  Max: {max_lat:.2f}ms")
    
    return avg

if __name__ == '__main__':
    print("Starting latency benchmarks...\n")
    
    rest_latency = benchmark_rest_latency(100)
    ws_latency = benchmark_websocket_latency(100)
    
    improvement = (rest_latency / ws_latency) if ws_latency > 0 else 0
    print(f"\nImprovement: {improvement:.1f}x faster")
```

**Run:**
```bash
python tests/benchmark_websocket_latency.py
```

**Expected Results:**
- REST: 20-100ms average
- WebSocket: 2-10ms average
- **Improvement: 10-50x faster**

---

#### 4.2 Multi-User Sync Testing (30min)

**Test Scenario:**
1. Open 3 browser windows to `http://localhost:5000`
2. Change effect parameter in Window 1
3. Verify Windows 2 & 3 update immediately (via WebSocket broadcast)

**Test Script:** `tests/test_multi_user_sync.html`
```html
<!DOCTYPE html>
<html>
<head>
    <title>Multi-User Sync Test</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
</head>
<body>
    <h1>Multi-User WebSocket Sync Test</h1>
    <div>
        <label>Brightness: <span id="brightness-value">50</span></label>
        <input type="range" id="brightness-slider" min="0" max="100" value="50">
    </div>
    
    <div id="log"></div>
    
    <script>
        const effectsSocket = io('/effects');
        const log = document.getElementById('log');
        const slider = document.getElementById('brightness-slider');
        const valueSpan = document.getElementById('brightness-value');
        
        effectsSocket.on('connect', () => {
            addLog('Connected to /effects namespace');
        });
        
        effectsSocket.on('effect.param.changed', (data) => {
            if (data.param_name === 'brightness') {
                slider.value = data.value * 100;
                valueSpan.textContent = (data.value * 100).toFixed(0);
                addLog(`Received update: brightness=${data.value}`);
            }
        });
        
        slider.addEventListener('input', (e) => {
            const value = e.target.value / 100;
            valueSpan.textContent = e.target.value;
            
            effectsSocket.emit('command.effect.param', {
                player_id: 'video',
                clip_id: 'test_clip',
                effect_index: 0,
                param_name: 'brightness',
                value: value
            });
            
            addLog(`Sent update: brightness=${value}`);
        });
        
        function addLog(message) {
            const entry = document.createElement('div');
            entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
            log.appendChild(entry);
        }
    </script>
</body>
</html>
```

---

#### 4.3 Error Handling & Fallback Testing (30min)

**Test Cases:**
1. **WebSocket Disconnection:**
   - Stop Flask server
   - Try to execute command
   - Verify REST fallback works

2. **Command Timeout:**
   - Add artificial delay in backend
   - Verify 5-second timeout triggers
   - Verify fallback to REST

3. **Invalid Data:**
   - Send malformed command
   - Verify error handling (command.error event)

4. **Connection Recovery:**
   - Disconnect client
   - Reconnect
   - Verify commands work again

---

## 📊 Success Metrics

### Performance Targets:
- ✅ Command latency: <5ms (was 20-100ms)
- ✅ Multi-user sync: <10ms (was never possible)
- ✅ Server load: -80% fewer HTTP requests
- ✅ UI responsiveness: Instant slider updates (no lag)

### Functional Requirements:
- ✅ All commands work via WebSocket
- ✅ Graceful fallback to REST if WebSocket fails
- ✅ Multi-user sync (parameter changes broadcast to all clients)
- ✅ Auto-reconnect on connection loss
- ✅ Backward compatibility (REST APIs still work)

---

## 🔧 Migration Strategy

### Phase-wise Rollout:
1. **Week 1:** Backend infrastructure + testing
2. **Week 2:** Frontend integration for transport controls
3. **Week 3:** Effect parameters + layer controls
4. **Week 4:** Status broadcasts + optimization

### Feature Flags:
Add config option to enable/disable WebSocket:
```json
{
  "api": {
    "websocket_enabled": true,
    "websocket_fallback_timeout": 5000
  }
}
```

### Monitoring:
Track in `rest_api.py`:
```python
# WebSocket statistics
self.ws_stats = {
    'commands_sent': 0,
    'commands_failed': 0,
    'fallback_to_rest': 0,
    'average_latency': 0
}
```

---

## 📝 Documentation Updates

**Files to create/update:**
1. `docs/WEBSOCKET_API.md` - WebSocket event documentation
2. `docs/MIGRATION_WEBSOCKET.md` - Migration guide for users
3. `README.md` - Add WebSocket features to feature list
4. `CHANGELOG.md` - Document WebSocket implementation

---

## ✅ Acceptance Criteria

- [ ] All transport controls work via WebSocket
- [ ] Effect parameter updates <5ms latency
- [ ] Layer opacity/blend mode updates <5ms latency
- [ ] Multi-user sync works (all clients see changes)
- [ ] Fallback to REST works when WebSocket fails
- [ ] Auto-reconnect works after disconnection
- [ ] Latency benchmarks show 20-50x improvement
- [ ] No breaking changes to existing REST API
- [ ] Documentation complete
- [ ] Tests pass (unit + integration + benchmark)

---

## 🎯 Next Steps After Completion

1. **Expand to more commands:**
   - Brightness/speed controls
   - Effect add/remove/reorder
   - Snapshot save/restore

2. **Optimize broadcasts:**
   - Room-based broadcasting (only to relevant clients)
   - Rate limiting for high-frequency updates

3. **Add MessagePack support:**
   - Binary protocol for even lower latency
   - Smaller payload sizes

4. **MIDI/OSC integration:**
   - Use WebSocket infrastructure for external controllers
   - Low-latency hardware control
