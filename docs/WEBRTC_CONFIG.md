# WebRTC Configuration Guide

## 📝 Overview

WebRTC settings can be configured via `config.json` to customize quality presets, connection limits, STUN servers, and more.

---

## ⚙️ Configuration File

Add the following section to your `config.json`:

```json
{
  "webrtc": {
    "enabled": true,
    "default_quality": "medium",
    "max_connections": 5,
    "fallback_to_mjpeg": true,
    "stun_servers": [
      "stun:stun.l.google.com:19302",
      "stun:stun1.l.google.com:19302"
    ],
    "quality_presets": {
      "low": {
        "width": 640,
        "height": 360,
        "fps": 15,
        "bitrate_kbps": 500
      },
      "medium": {
        "width": 1280,
        "height": 720,
        "fps": 20,
        "bitrate_kbps": 1000
      },
      "high": {
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "bitrate_kbps": 2000
      }
    }
  }
}
```

---

## 🎛️ Configuration Options

### Global Settings

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable WebRTC globally |
| `default_quality` | string | `"medium"` | Default quality preset (low/medium/high) |
| `max_connections` | integer | `5` | Maximum concurrent WebRTC connections |
| `fallback_to_mjpeg` | boolean | `true` | Auto-fallback to MJPEG on WebRTC failure |
| `stun_servers` | array | Google STUN | List of STUN server URLs |
| `quality_presets` | object | See above | Quality preset definitions |

---

## 🎨 Quality Presets

Each quality preset defines:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `width` | Video width in pixels | `1280` |
| `height` | Video height in pixels | `720` |
| `fps` | Frames per second | `20` |
| `bitrate_kbps` | Target bitrate in kbps | `1000` |

### Preset Examples

#### Ultra Low (for remote access over slow connections)
```json
"ultra_low": {
  "width": 480,
  "height": 270,
  "fps": 10,
  "bitrate_kbps": 300
}
```

#### 4K (for high-end systems)
```json
"4k": {
  "width": 3840,
  "height": 2160,
  "fps": 60,
  "bitrate_kbps": 5000
}
```

#### Portrait (for vertical displays)
```json
"portrait": {
  "width": 720,
  "height": 1280,
  "fps": 30,
  "bitrate_kbps": 1500
}
```

---

## 🌐 STUN/TURN Servers

### Default (Google Public STUN)
```json
"stun_servers": [
  "stun:stun.l.google.com:19302",
  "stun:stun1.l.google.com:19302"
]
```

### Private STUN Server
```json
"stun_servers": [
  "stun:your-stun-server.com:3478"
]
```

### TURN Server (with authentication)
```json
"stun_servers": [
  "stun:your-stun-server.com:3478",
  "turn:your-turn-server.com:3478?transport=udp",
  "turn:your-turn-server.com:3478?transport=tcp"
]
```

**Note:** TURN server credentials must be configured in the frontend (`webrtc-preview.js`) separately.

---

## 🔧 Common Configurations

### For Low-End Hardware
Minimize CPU usage with reduced quality:

```json
{
  "webrtc": {
    "default_quality": "low",
    "quality_presets": {
      "low": {
        "width": 480,
        "height": 270,
        "fps": 10,
        "bitrate_kbps": 300
      },
      "medium": {
        "width": 640,
        "height": 360,
        "fps": 15,
        "bitrate_kbps": 500
      }
    }
  }
}
```

### For Remote Access (Low Bandwidth)
Optimize for bandwidth:

```json
{
  "webrtc": {
    "default_quality": "low",
    "quality_presets": {
      "low": {
        "width": 480,
        "height": 270,
        "fps": 10,
        "bitrate_kbps": 200
      }
    }
  }
}
```

### For High-End Systems
Maximum quality:

```json
{
  "webrtc": {
    "default_quality": "high",
    "quality_presets": {
      "high": {
        "width": 1920,
        "height": 1080,
        "fps": 60,
        "bitrate_kbps": 3000
      },
      "4k": {
        "width": 3840,
        "height": 2160,
        "fps": 30,
        "bitrate_kbps": 5000
      }
    }
  }
}
```

### For Production (Multiple Users)
Increase connection limit:

```json
{
  "webrtc": {
    "max_connections": 20,
    "default_quality": "medium"
  }
}
```

---

## 🚀 Apply Configuration Changes

After editing `config.json`:

1. **Restart the server:**
   ```bash
   # Stop server (Ctrl+C)
   python src/main.py
   ```

2. **Reload browser:**
   ```
   Ctrl+Shift+R (hard reload to clear cache)
   ```

3. **Verify settings:**
   ```bash
   curl http://localhost:5000/api/webrtc/stats
   ```

---

## 🔍 Troubleshooting

### Configuration not loading

**Check server logs:**
```bash
tail -f logs/*.log | grep -i webrtc
```

**Expected output:**
```
WebRTC config loaded: max_connections=5, default_quality=medium
Loaded WebRTC quality preset 'low': 640x360 @ 15fps
Loaded WebRTC quality preset 'medium': 1280x720 @ 20fps
Loaded WebRTC quality preset 'high': 1920x1080 @ 30fps
```

### Invalid quality preset

If you see:
```
Invalid quality preset, using 'medium': your_preset_name
```

**Fix:**
1. Check spelling in `config.json`
2. Ensure preset is defined in `quality_presets`
3. Restart server

### STUN server not reachable

**Test STUN connectivity:**
```javascript
// Browser console:
const pc = new RTCPeerConnection({
    iceServers: [{urls: 'stun:stun.l.google.com:19302'}]
});
pc.createOffer().then(offer => console.log('STUN OK'));
```

---

## 📊 Performance Impact

### Resolution vs CPU Usage

| Resolution | FPS | CPU Usage | Bandwidth | Use Case |
|------------|-----|-----------|-----------|----------|
| 480x270 | 10 | 2-3% | 0.2 Mbps | Remote (slow network) |
| 640x360 | 15 | 3-5% | 0.5 Mbps | Low-end hardware |
| 1280x720 | 20 | 5-10% | 1.0 Mbps | Balanced (default) |
| 1920x1080 | 30 | 10-15% | 2.0 Mbps | High quality |
| 3840x2160 | 30 | 20-30% | 5.0 Mbps | 4K (high-end only) |

### Connection Limit Recommendations

| Scenario | Recommended Limit |
|----------|-------------------|
| Single user | 2-5 |
| Small team (2-5 users) | 10-15 |
| Production (10+ users) | 20-30 |
| High load | 50+ (requires high-end server) |

**Note:** Each connection uses ~5-15% CPU depending on quality.

---

## 🔐 Security Considerations

### Private STUN/TURN Servers

**Why use private servers:**
- Better privacy (no Google dependency)
- Better control over NAT traversal
- Required for restrictive networks
- Better performance (lower latency)

**Setup coturn (open-source TURN server):**
```bash
# Ubuntu/Debian
sudo apt install coturn

# Configure /etc/turnserver.conf
listening-port=3478
realm=your-domain.com
server-name=your-domain.com
lt-cred-mech
user=username:password

# Start service
sudo systemctl start coturn
sudo systemctl enable coturn
```

### WebRTC Security

- **DTLS encryption**: Enabled by default
- **SRTP**: Secure Real-time Transport Protocol
- **Authentication**: Add to `/api/webrtc/offer` endpoint
- **Rate limiting**: Limit connections per IP
- **HTTPS**: Use HTTPS for production (wss://)

---

## 📚 References

- **WebRTC Specification**: https://www.w3.org/TR/webrtc/
- **STUN/TURN**: https://webrtc.org/getting-started/turn-server
- **coturn**: https://github.com/coturn/coturn
- **aiortc**: https://aiortc.readthedocs.io/

---

**Need help?** Check `docs/WEBRTC_PREVIEW.md` for full documentation.
