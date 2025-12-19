# Statistics Widget - Implementation Guide

## Overview

This document describes the implementation of a **real-time system statistics widget** for the Flux Art-Net system, displaying performance metrics for monitoring and debugging.

## Goals

- Display real-time system performance metrics
- Monitor CPU, GPU, RAM, VRAM usage
- Track network adapter statistics
- Show FPS for all outputs (backend rendering + frontend preview)
- Provide visual feedback with color-coded indicators
- Minimal performance overhead
- Auto-refresh with configurable interval
- **Slide-in overlay design**: Panel slides from right side
- **Half-transparent background**: Backdrop blur + transparency
- **Always-visible tab**: Small tab handle for easy access

## Statistics to Display

### System Resources
- **CPU Load**: Overall percentage and per-core usage
- **GPU Load**: GPU utilization percentage
- **RAM Usage**: Used/Total memory in GB
- **VRAM Usage**: GPU memory used/total in GB

### Network Adapters
- **All Network Interfaces**: Name, sent/received bytes, current speed
- **Active Connections**: Count of active network connections

### Performance Metrics
- **Backend FPS**: 
  - Video player render FPS
  - Art-Net player render FPS
  - Effect processing time
- **Frontend FPS**: 
  - Preview canvas FPS
  - UI update rate

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend (Python)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │ System Monitor  │────────▶│ Statistics API   │          │
│  │   (psutil)      │         │  /api/stats      │          │
│  └─────────────────┘         └──────────────────┘          │
│         │                              │                    │
│         │ Collects every 1s            │ Serves JSON        │
│         ▼                              ▼                    │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │  Stats Cache    │         │   WebSocket      │          │
│  │  (threading)    │────────▶│  /ws/stats       │          │
│  └─────────────────┘         └──────────────────┘          │
│                                        │                    │
└────────────────────────────────────────┼────────────────────┘
                                         │
                                         ▼ JSON Stream
┌─────────────────────────────────────────────────────────────┐
│                   Frontend (JavaScript)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │ Stats Widget    │◀────────│  WebSocket       │          │
│  │  Component      │         │  Client          │          │
│  └─────────────────┘         └──────────────────┘          │
│         │                                                   │
│         │ Update every 1s                                   │
│         ▼                                                   │
│  ┌─────────────────┐         ┌──────────────────┐          │
│  │  Gauge Charts   │         │  FPS Counters    │          │
│  │  (CPU/GPU/RAM)  │         │  Network Stats   │          │
│  └─────────────────┘         └──────────────────┘          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Color Coding

- **🟢 Green**: 0-60% usage (healthy)
- **🟡 Yellow**: 60-80% usage (moderate)
- **🔴 Red**: 80-100% usage (high)

## Implementation Steps

### Phase 1: Backend - System Monitor

#### 1.1 Install Dependencies

**File:** `requirements.txt`

Add system monitoring library:

```txt
psutil>=5.9.0
GPUtil>=1.4.0
```

Install:
```bash
pip install psutil GPUtil
```

#### 1.2 Create Statistics Collector

**File:** `src/modules/system_stats.py`

```python
"""
System Statistics Collector
Monitors CPU, GPU, RAM, VRAM, Network, and FPS metrics.
"""

import psutil
import GPUtil
import time
import threading
import logging
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)

class SystemStatsCollector:
    """Collects and caches system performance statistics."""
    
    def __init__(self, update_interval=1.0):
        self.update_interval = update_interval
        self.running = False
        self.thread = None
        
        # Stats cache
        self.stats = {
            'cpu': {'percent': 0, 'per_core': [], 'frequency': 0},
            'memory': {'used_gb': 0, 'total_gb': 0, 'percent': 0},
            'gpu': {'load': 0, 'memory_used_gb': 0, 'memory_total_gb': 0, 'memory_percent': 0, 'temperature': 0},
            'network': {'interfaces': [], 'total_sent_mb': 0, 'total_recv_mb': 0},
            'fps': {
                'video_backend': 0,
                'artnet_backend': 0,
                'video_frontend': 0,
                'artnet_frontend': 0
            },
            'timestamp': 0
        }
        
        # Network baseline for calculating deltas
        self.net_io_baseline = None
        self.last_net_io = None
        
        # FPS tracking
        self.fps_counters = {
            'video_backend': FPSCounter(),
            'artnet_backend': FPSCounter(),
            'video_frontend': FPSCounter(),
            'artnet_frontend': FPSCounter()
        }
    
    def start(self):
        """Start background stats collection."""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._collect_loop, daemon=True)
        self.thread.start()
        logger.info("📊 System stats collector started")
    
    def stop(self):
        """Stop background stats collection."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("📊 System stats collector stopped")
    
    def _collect_loop(self):
        """Background loop that collects stats periodically."""
        while self.running:
            try:
                self._collect_stats()
                time.sleep(self.update_interval)
            except Exception as e:
                logger.error(f"Error collecting stats: {e}")
    
    def _collect_stats(self):
        """Collect all system statistics."""
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_freq = psutil.cpu_freq()
        
        self.stats['cpu'] = {
            'percent': round(cpu_percent, 1),
            'per_core': [round(x, 1) for x in cpu_per_core],
            'frequency': round(cpu_freq.current, 0) if cpu_freq else 0
        }
        
        # Memory (RAM)
        mem = psutil.virtual_memory()
        self.stats['memory'] = {
            'used_gb': round(mem.used / (1024**3), 2),
            'total_gb': round(mem.total / (1024**3), 2),
            'percent': round(mem.percent, 1)
        }
        
        # GPU
        try:
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]  # Use first GPU
                self.stats['gpu'] = {
                    'load': round(gpu.load * 100, 1),
                    'memory_used_gb': round(gpu.memoryUsed / 1024, 2),
                    'memory_total_gb': round(gpu.memoryTotal / 1024, 2),
                    'memory_percent': round((gpu.memoryUsed / gpu.memoryTotal) * 100, 1) if gpu.memoryTotal > 0 else 0,
                    'temperature': round(gpu.temperature, 1) if gpu.temperature else 0
                }
            else:
                self.stats['gpu'] = {
                    'load': 0,
                    'memory_used_gb': 0,
                    'memory_total_gb': 0,
                    'memory_percent': 0,
                    'temperature': 0
                }
        except Exception as e:
            logger.debug(f"GPU stats unavailable: {e}")
            self.stats['gpu'] = {'load': 0, 'memory_used_gb': 0, 'memory_total_gb': 0, 'memory_percent': 0, 'temperature': 0}
        
        # Network
        net_io = psutil.net_io_counters(pernic=True)
        interfaces = []
        total_sent = 0
        total_recv = 0
        
        for interface_name, io_counters in net_io.items():
            # Skip loopback
            if 'loopback' in interface_name.lower() or 'lo' == interface_name.lower():
                continue
            
            # Calculate speed (bytes/sec) if we have previous data
            speed_sent = 0
            speed_recv = 0
            if self.last_net_io and interface_name in self.last_net_io:
                time_delta = self.update_interval
                bytes_sent_delta = io_counters.bytes_sent - self.last_net_io[interface_name].bytes_sent
                bytes_recv_delta = io_counters.bytes_recv - self.last_net_io[interface_name].bytes_recv
                speed_sent = bytes_sent_delta / time_delta / 1024  # KB/s
                speed_recv = bytes_recv_delta / time_delta / 1024  # KB/s
            
            interfaces.append({
                'name': interface_name,
                'sent_mb': round(io_counters.bytes_sent / (1024**2), 2),
                'recv_mb': round(io_counters.bytes_recv / (1024**2), 2),
                'speed_sent_kbps': round(speed_sent, 1),
                'speed_recv_kbps': round(speed_recv, 1)
            })
            
            total_sent += io_counters.bytes_sent
            total_recv += io_counters.bytes_recv
        
        self.last_net_io = net_io
        
        self.stats['network'] = {
            'interfaces': interfaces,
            'total_sent_mb': round(total_sent / (1024**2), 2),
            'total_recv_mb': round(total_recv / (1024**2), 2)
        }
        
        # FPS - get current values from counters
        self.stats['fps'] = {
            'video_backend': self.fps_counters['video_backend'].get_fps(),
            'artnet_backend': self.fps_counters['artnet_backend'].get_fps(),
            'video_frontend': self.fps_counters['video_frontend'].get_fps(),
            'artnet_frontend': self.fps_counters['artnet_frontend'].get_fps()
        }
        
        # Timestamp
        self.stats['timestamp'] = time.time()
    
    def get_stats(self):
        """Get current statistics."""
        return self.stats.copy()
    
    def record_frame(self, counter_name):
        """Record a frame for FPS calculation."""
        if counter_name in self.fps_counters:
            self.fps_counters[counter_name].tick()


class FPSCounter:
    """Simple FPS counter using sliding window."""
    
    def __init__(self, window_size=60):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)
    
    def tick(self):
        """Record a frame."""
        self.frame_times.append(time.time())
    
    def get_fps(self):
        """Calculate current FPS."""
        if len(self.frame_times) < 2:
            return 0
        
        time_span = self.frame_times[-1] - self.frame_times[0]
        if time_span == 0:
            return 0
        
        fps = (len(self.frame_times) - 1) / time_span
        return round(fps, 1)


# Global instance
_stats_collector = None

def get_stats_collector():
    """Get global stats collector instance."""
    global _stats_collector
    if _stats_collector is None:
        _stats_collector = SystemStatsCollector()
    return _stats_collector
```

#### 1.3 Create Statistics API

**File:** `src/modules/api_stats.py`

```python
"""
Statistics API
Provides REST and WebSocket endpoints for system statistics.
"""

from flask import Blueprint, jsonify
from flask_sock import Sock
import json
import time
import logging
from .system_stats import get_stats_collector

logger = logging.getLogger(__name__)

# Create blueprint
stats_bp = Blueprint('stats', __name__)
sock = Sock()

@stats_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Get current system statistics (REST endpoint)."""
    try:
        collector = get_stats_collector()
        stats = collector.get_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@sock.route('/ws/stats')
def stats_websocket(ws):
    """WebSocket endpoint for real-time stats streaming."""
    logger.info("📊 Stats WebSocket client connected")
    collector = get_stats_collector()
    
    try:
        while True:
            # Get latest stats
            stats = collector.get_stats()
            
            # Send to client
            ws.send(json.dumps({
                'type': 'stats_update',
                'data': stats
            }))
            
            # Wait before next update
            time.sleep(1)
    
    except Exception as e:
        logger.info(f"Stats WebSocket closed: {e}")
    
    finally:
        logger.info("📊 Stats WebSocket client disconnected")

def init_stats_api(app):
    """Initialize stats API with Flask app."""
    app.register_blueprint(stats_bp)
    sock.init_app(app)
    
    # Start stats collector
    collector = get_stats_collector()
    collector.start()
    
    logger.info("📊 Stats API initialized")
```

#### 1.4 Integrate with Players

**File:** `src/modules/player/player_base.py`

Add FPS recording to render loop:

```python
from ..system_stats import get_stats_collector

class PlayerBase:
    def __init__(self, name):
        self.name = name
        # ... existing code ...
        self.stats_collector = get_stats_collector()
    
    def render_frame(self):
        """Render current frame."""
        # ... existing render code ...
        
        # Record frame for FPS tracking
        counter_name = f"{self.name}_backend"  # e.g., "video_backend"
        self.stats_collector.record_frame(counter_name)
        
        return frame
```

### Phase 2: Frontend Widget

#### 2.1 Create Stats Widget Component

**File:** `frontend/components/stats-widget.html`

```html
<template id="stats-widget-template">
    <!-- Tab handle (always visible) -->
    <div class="stats-tab-handle" onclick="window.statsWidget.toggle()">
        <span class="stats-tab-icon">📊</span>
        <span class="stats-tab-text">STATS</span>
    </div>
    
    <!-- Slide-in panel -->
    <div class="stats-widget stats-widget-hidden">
        <div class="stats-header">
            <span class="stats-title">📊 System Statistics</span>
            <button class="btn-close-stats" onclick="window.statsWidget.toggle()">✕</button>
        </div>
        
        <div class="stats-body">
            <!-- CPU Section -->
            <div class="stat-section">
                <div class="stat-label">💻 CPU</div>
                <div class="stat-value">
                    <span id="stat-cpu-percent" class="stat-number">0</span>%
                    <span id="stat-cpu-freq" class="stat-detail">@ 0 MHz</span>
                </div>
                <div class="stat-bar">
                    <div id="stat-cpu-bar" class="stat-bar-fill" style="width: 0%"></div>
                </div>
            </div>
            
            <!-- RAM Section -->
            <div class="stat-section">
                <div class="stat-label">🧠 RAM</div>
                <div class="stat-value">
                    <span id="stat-ram-used" class="stat-number">0</span> /
                    <span id="stat-ram-total">0</span> GB
                    (<span id="stat-ram-percent">0</span>%)
                </div>
                <div class="stat-bar">
                    <div id="stat-ram-bar" class="stat-bar-fill" style="width: 0%"></div>
                </div>
            </div>
            
            <!-- GPU Section -->
            <div class="stat-section">
                <div class="stat-label">🎮 GPU</div>
                <div class="stat-value">
                    <span id="stat-gpu-percent" class="stat-number">0</span>%
                    <span id="stat-gpu-temp" class="stat-detail">🌡️ 0°C</span>
                </div>
                <div class="stat-bar">
                    <div id="stat-gpu-bar" class="stat-bar-fill" style="width: 0%"></div>
                </div>
            </div>
            
            <!-- VRAM Section -->
            <div class="stat-section">
                <div class="stat-label">💾 VRAM</div>
                <div class="stat-value">
                    <span id="stat-vram-used" class="stat-number">0</span> /
                    <span id="stat-vram-total">0</span> GB
                    (<span id="stat-vram-percent">0</span>%)
                </div>
                <div class="stat-bar">
                    <div id="stat-vram-bar" class="stat-bar-fill" style="width: 0%"></div>
                </div>
            </div>
            
            <!-- FPS Section -->
            <div class="stat-section">
                <div class="stat-label">🎬 FPS</div>
                <div class="stat-grid">
                    <div class="stat-item">
                        <span class="stat-item-label">Video BE:</span>
                        <span id="stat-fps-video-backend" class="stat-item-value">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-item-label">Art-Net BE:</span>
                        <span id="stat-fps-artnet-backend" class="stat-item-value">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-item-label">Video FE:</span>
                        <span id="stat-fps-video-frontend" class="stat-item-value">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-item-label">Art-Net FE:</span>
                        <span id="stat-fps-artnet-frontend" class="stat-item-value">0</span>
                    </div>
                </div>
            </div>
            
            <!-- Network Section -->
            <div class="stat-section">
                <div class="stat-label">🌐 Network</div>
                <div id="stat-network-interfaces" class="stat-network">
                    <!-- Populated dynamically -->
                </div>
            </div>
        </div>
    </div>
</template>

<script>
class StatsWidget {
    constructor() {
        this.visible = false;
        this.ws = null;
        this.reconnectTimer = null;
        this.container = null;
    }
    
    init(containerId = 'stats-widget-container') {
        // Create container if it doesn't exist
        this.container = document.getElementById(containerId);
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = containerId;
            document.body.appendChild(this.container);
        }
        
        // Load template
        const template = document.getElementById('stats-widget-template');
        const content = template.content.cloneNode(true);
        this.container.appendChild(content);
        
        // Get panel reference
        this.panel = this.container.querySelector('.stats-widget');
        this.tabHandle = this.container.querySelector('.stats-tab-handle');
        
        // Start hidden
        this.hide();
        
        // Connect WebSocket
        this.connect();
    }
    
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/stats`;
        
        console.log('📊 Connecting to stats WebSocket...');
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('📊 Stats WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'stats_update') {
                    this.updateStats(message.data);
                }
            } catch (e) {
                console.error('Error parsing stats message:', e);
            }
        };
        
        this.ws.onerror = (error) => {
            console.error('Stats WebSocket error:', error);
        };
        
        this.ws.onclose = () => {
            console.log('📊 Stats WebSocket closed, reconnecting...');
            this.reconnectTimer = setTimeout(() => this.connect(), 3000);
        };
    }
    
    updateStats(stats) {
        // CPU
        document.getElementById('stat-cpu-percent').textContent = stats.cpu.percent;
        document.getElementById('stat-cpu-freq').textContent = `@ ${stats.cpu.frequency} MHz`;
        this.updateBar('stat-cpu-bar', stats.cpu.percent);
        
        // RAM
        document.getElementById('stat-ram-used').textContent = stats.memory.used_gb;
        document.getElementById('stat-ram-total').textContent = stats.memory.total_gb;
        document.getElementById('stat-ram-percent').textContent = stats.memory.percent;
        this.updateBar('stat-ram-bar', stats.memory.percent);
        
        // GPU
        document.getElementById('stat-gpu-percent').textContent = stats.gpu.load;
        document.getElementById('stat-gpu-temp').textContent = `🌡️ ${stats.gpu.temperature}°C`;
        this.updateBar('stat-gpu-bar', stats.gpu.load);
        
        // VRAM
        document.getElementById('stat-vram-used').textContent = stats.gpu.memory_used_gb;
        document.getElementById('stat-vram-total').textContent = stats.gpu.memory_total_gb;
        document.getElementById('stat-vram-percent').textContent = stats.gpu.memory_percent;
        this.updateBar('stat-vram-bar', stats.gpu.memory_percent);
        
        // FPS
        document.getElementById('stat-fps-video-backend').textContent = stats.fps.video_backend;
        document.getElementById('stat-fps-artnet-backend').textContent = stats.fps.artnet_backend;
        document.getElementById('stat-fps-video-frontend').textContent = stats.fps.video_frontend;
        document.getElementById('stat-fps-artnet-frontend').textContent = stats.fps.artnet_frontend;
        
        // Network
        this.updateNetwork(stats.network);
    }
    
    updateBar(elementId, percent) {
        const bar = document.getElementById(elementId);
        bar.style.width = `${percent}%`;
        
        // Color coding
        bar.className = 'stat-bar-fill';
        if (percent > 80) {
            bar.classList.add('stat-bar-critical');
        } else if (percent > 60) {
            bar.classList.add('stat-bar-warning');
        } else {
            bar.classList.add('stat-bar-normal');
        }
    }
    
    updateNetwork(network) {
        const container = document.getElementById('stat-network-interfaces');
        
        let html = '';
        for (const iface of network.interfaces) {
            html += `
                <div class="stat-network-item">
                    <div class="stat-network-name">${iface.name}</div>
                    <div class="stat-network-speed">
                        ↑ ${iface.speed_sent_kbps} KB/s
                        ↓ ${iface.speed_recv_kbps} KB/s
                    </div>
                </div>
            `;
        }
        
        container.innerHTML = html;
    }
    
    show() {
        if (this.panel) {
            this.panel.classList.remove('stats-widget-hidden');
            this.panel.classList.add('stats-widget-visible');
        }
        if (this.tabHandle) {
            this.tabHandle.classList.add('stats-tab-hidden');
        }
        this.visible = true;
    }
    
    hide() {
        if (this.panel) {
            this.panel.classList.remove('stats-widget-visible');
            this.panel.classList.add('stats-widget-hidden');
        }
        if (this.tabHandle) {
            this.tabHandle.classList.remove('stats-tab-hidden');
        }
        this.visible = false;
    }
    
    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.show();
        }
    }
    
    destroy() {
        if (this.ws) {
            this.ws.close();
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
        }
    }
}

// Global instance
window.statsWidget = new StatsWidget();
</script>
```

#### 2.2 Add Widget Styles

**File:** `frontend/css/stats-widget.css`

```css
/* Tab handle - always visible */
.stats-tab-handle {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 40px;
    height: 120px;
    background: rgba(20, 20, 30, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-right: none;
    border-radius: 8px 0 0 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    cursor: pointer;
    z-index: 9998;
    transition: all 0.3s ease;
    backdrop-filter: blur(5px);
}

.stats-tab-handle:hover {
    background: rgba(30, 30, 40, 0.85);
    width: 45px;
}

.stats-tab-hidden {
    opacity: 0;
    pointer-events: none;
}

.stats-tab-icon {
    font-size: 20px;
    line-height: 1;
}

.stats-tab-text {
    writing-mode: vertical-rl;
    text-orientation: mixed;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 1px;
    color: #999;
}

/* Slide-in panel */
.stats-widget {
    position: fixed;
    top: 0;
    right: 0;
    width: 380px;
    height: 100vh;
    background: rgba(20, 20, 30, 0.5);
    border-left: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.5);
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    color: #e0e0e0;
    z-index: 9999;
    backdrop-filter: blur(15px);
    transition: transform 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
    transform: translateX(0);
}

.stats-widget-hidden {
    transform: translateX(100%);
}

.stats-widget-visible {
    transform: translateX(0);
}

.stats-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.15);
    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
}

.stats-title {
    font-weight: 600;
    font-size: 14px;
}

.btn-close-stats {
    background: none;
    border: none;
    color: #888;
    font-size: 18px;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.2s;
}

.btn-close-stats:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #fff;
}

.stats-body {
    padding: 20px;
    height: calc(100vh - 60px);
    overflow-y: auto;
    overflow-x: hidden;
}

.stat-section {
    margin-bottom: 15px;
    padding-bottom: 15px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-section:last-child {
    border-bottom: none;
    margin-bottom: 0;
    padding-bottom: 0;
}

.stat-label {
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    color: #999;
    margin-bottom: 5px;
    letter-spacing: 0.5px;
}

.stat-value {
    font-size: 13px;
    margin-bottom: 5px;
    display: flex;
    align-items: baseline;
    gap: 5px;
}

.stat-number {
    font-weight: 700;
    font-size: 16px;
    color: #fff;
}

.stat-detail {
    font-size: 11px;
    color: #888;
}

.stat-bar {
    height: 6px;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
    overflow: hidden;
}

.stat-bar-fill {
    height: 100%;
    border-radius: 3px;
    transition: width 0.3s ease, background-color 0.3s ease;
}

.stat-bar-normal {
    background: linear-gradient(90deg, #4caf50, #66bb6a);
}

.stat-bar-warning {
    background: linear-gradient(90deg, #ff9800, #ffb74d);
}

.stat-bar-critical {
    background: linear-gradient(90deg, #f44336, #e57373);
}

.stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}

.stat-item {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
}

.stat-item-label {
    color: #888;
}

.stat-item-value {
    font-weight: 600;
    color: #fff;
}

.stat-network {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.stat-network-item {
    background: rgba(255, 255, 255, 0.03);
    padding: 8px;
    border-radius: 4px;
    font-size: 11px;
}

.stat-network-name {
    font-weight: 600;
    margin-bottom: 4px;
    color: #fff;
}

.stat-network-speed {
    color: #888;
    display: flex;
    justify-content: space-between;
}

/* Scrollbar styling */
.stats-body::-webkit-scrollbar {
    width: 6px;
}

.stats-body::-webkit-scrollbar-track {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 3px;
}

.stats-body::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
}

.stats-body::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
}
```

#### 2.3 Integrate into Main UI

**File:** `frontend/player.html`

Add to `<head>`:

```html
<link rel="stylesheet" href="css/stats-widget.css">
```

Add before closing `</body>`:

```html
<!-- Stats Widget (Slide-in overlay) -->
<div id="stats-widget-container"></div>
<script src="components/stats-widget.html"></script>

<script>
    // Initialize stats widget on page load
    document.addEventListener('DOMContentLoaded', () => {
        window.statsWidget.init();
    });
    
    // Keyboard shortcut: Ctrl+Shift+S to toggle stats
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.shiftKey && e.key === 'S') {
            e.preventDefault();
            window.statsWidget.toggle();
        }
    });
    
    // Close on Escape key when visible
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && window.statsWidget.visible) {
            window.statsWidget.hide();
        }
    });
</script>
```

**Optional**: Add toggle button to menu bar (tab handle is always visible):

```html
<button class="btn btn-sm btn-outline-secondary" 
        onclick="window.statsWidget.toggle()" 
        title="Toggle Stats (Ctrl+Shift+S)">
    📊 Stats
</button>
```

### Phase 3: Frontend FPS Tracking

#### 3.1 Track Preview Canvas FPS

**File:** `frontend/js/player.js`

Add FPS tracking to preview rendering:

```javascript
// FPS tracking for frontend
const frontendFPS = {
    video: { lastTime: 0, frames: [] },
    artnet: { lastTime: 0, frames: [] }
};

function trackFrontendFPS(playerType) {
    const now = performance.now();
    const fps = frontendFPS[playerType];
    
    fps.frames.push(now);
    
    // Keep only last 60 frames
    if (fps.frames.length > 60) {
        fps.frames.shift();
    }
    
    // Calculate FPS
    if (fps.frames.length >= 2) {
        const timeSpan = (fps.frames[fps.frames.length - 1] - fps.frames[0]) / 1000;
        const currentFPS = (fps.frames.length - 1) / timeSpan;
        
        // Send to backend
        if (now - fps.lastTime > 1000) {
            fetch('/api/stats/frontend-fps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    player: playerType,
                    fps: Math.round(currentFPS * 10) / 10
                })
            });
            fps.lastTime = now;
        }
    }
}

// Add to preview render functions
function renderVideoPreview() {
    // ... existing render code ...
    trackFrontendFPS('video');
}

function renderArtnetPreview() {
    // ... existing render code ...
    trackFrontendFPS('artnet');
}
```

#### 3.2 Backend Endpoint for Frontend FPS

**File:** `src/modules/api_stats.py`

```python
@stats_bp.route('/api/stats/frontend-fps', methods=['POST'])
def update_frontend_fps():
    """Update frontend FPS from client."""
    try:
        data = request.get_json() or {}
        player = data.get('player')
        fps = data.get('fps', 0)
        
        collector = get_stats_collector()
        counter_name = f"{player}_frontend"
        
        # Update FPS counter directly
        collector.stats['fps'][counter_name] = fps
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating frontend FPS: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
```

## Usage

### Toggle Widget

- **Tab Handle**: Click the always-visible tab on the right edge of screen
- **Button**: Click "📊 Stats" in menu bar (if added)
- **Keyboard**: Press `Ctrl+Shift+S` to open, `Escape` to close
- **JavaScript**: `window.statsWidget.toggle()`

### Panel Behavior

- **Slides in from right**: Smooth animation (300ms cubic-bezier)
- **Half-transparent**: `rgba(20, 20, 30, 0.5)` with 15px backdrop blur
- **Full height**: Panel spans entire viewport height
- **Tab auto-hides**: When panel is open, tab handle fades out
- **Click outside**: Panel stays open (click tab/button/Esc to close)

### Auto-Updates

- Stats refresh every **1 second**
- WebSocket connection auto-reconnects on disconnect
- Minimal CPU/bandwidth overhead

### Monitoring Scenarios

**Performance Tuning:**
- Watch CPU/GPU load during effect processing
- Monitor VRAM usage with large videos
- Track FPS drops in real-time

**Network Debugging:**
- Monitor Art-Net output bandwidth
- Track network adapter activity
- Identify connection issues

**System Health:**
- Ensure resources stay in green zone
- Identify bottlenecks (CPU vs GPU)
- Monitor temperature for throttling

## Performance Considerations

### Backend Overhead

- Stats collection: ~0.5-1% CPU
- Network monitoring: ~0.1% CPU
- FPS tracking: negligible (simple counters)

### Network Bandwidth

- WebSocket updates: ~1-2 KB/second
- Compression not needed (small payload)
- Automatic reconnection on failure

### Optimization Tips

1. **Increase update interval** if overhead is concern:
   ```python
   collector = SystemStatsCollector(update_interval=2.0)  # 2 seconds
   ```

2. **Disable unused metrics** in `system_stats.py`

3. **Close widget when not needed** - WebSocket closes on hide

## Future Enhancements

1. **Historical Graphs**
   - Chart.js integration
   - 1-hour history graphs
   - Min/max/average values

2. **Alerts & Notifications**
   - Toast notification when CPU > 90%
   - Warning when VRAM nearly full
   - FPS drop alerts

3. **Export Stats**
   - Download CSV of statistics
   - Performance report generation
   - Session logging

4. **Per-Effect Profiling**
   - Show render time per effect
   - Identify slow effects
   - Effect performance comparison

5. **Remote Monitoring**
   - View stats from other devices
   - Dashboard for multiple instances
   - Prometheus/Grafana integration

## References

- `src/modules/system_stats.py` - Statistics collector
- `src/modules/api_stats.py` - REST and WebSocket API
- `frontend/components/stats-widget.html` - Widget component
- `frontend/css/stats-widget.css` - Widget styles
- External: [psutil documentation](https://psutil.readthedocs.io/)
- External: [GPUtil documentation](https://github.com/anderskm/gputil)
