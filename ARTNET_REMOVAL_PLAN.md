# 🗑️ Remove Old Art-Net Implementation - Battle Plan

**Generated:** February 13, 2026  
**Status:** Ready to execute  
**Estimated Time:** 3-4 hours

---

## 🔍 **SITUATION ANALYSIS**

### **The Problem: DUAL Systems Running Simultaneously**

Looking at the code, **BOTH Art-Net systems are active**:

```python
# main.py lines 478-486 - OLD SYSTEM
from modules.artnet_manager import ArtNetManager
artnet_manager = ArtNetManager(target_ip, start_universe, ...)
artnet_manager.start(artnet_config)

# main.py lines 554-563 - NEW SYSTEM  
from modules.artnet_routing.routing_bridge import RoutingBridge
routing_bridge = RoutingBridge(...)
artnet_player.routing_bridge = routing_bridge

# player_core.py lines 1503-1518 - BOTH SENDING FRAMES!
if self.artnet_manager and self.enable_artnet:
    self.artnet_manager.send_frame(dmx_buffer)  # OLD

if self.routing_bridge and self.enable_artnet:
    self.routing_bridge.process_frame(frame)     # NEW
```

**Result:** Both systems try to send Art-Net data → potential conflicts, confusion, wasted resources.

---

## 📊**FEATURE COMPARISON**

| Feature | Old System (artnet_manager.py) | New System (artnet_routing/) | Status |
|---------|-------------------------------|------------------------------|--------|
| **Send frames** | ✅ `send_frame(dmx_buffer)` | ✅ `process_frame(frame)` | Both work |
| **Test patterns** | ✅ `test_pattern('red')` | ❌ Missing | **Migration needed** |
| **Blackout** | ✅ `blackout()` | ❌ Missing | **Migration needed** |
| **Resume video** | ✅ `resume_video_mode()` | ❌ Missing | **Migration needed** |
| **Delta encoding** | ✅ Full implementation | ❌ Missing | Can remove (doc says not needed) |
| **FPS control** | ✅ `set_fps()` | ❌ Missing | Can remove (per-output instead) |
| **Network stats** | ✅ `get_network_stats()` | ❌ Missing | **Migration needed** |
| **Replay mode** | ✅ Priority system | ❌ Missing | **Migration needed** |
| **Channel mapping** | ✅ RGB/GRB/BGR per universe | ✅ Per-object mapping | NEW is better |
| **Multi-output** | ❌ Single output only | ✅ Multiple outputs | NEW is better |
| **Pixel sampling** | ❌ Points-based only | ✅ Canvas sampling | NEW is better |
| **DMX monitor** | ✅ `last_frame` | ✅ `get_last_frames()` | NEW is better |

---

## 🎯 **MIGRATION STRATEGY**

### **Option A: Complete Migration** (Recommended - 3-4h)
Add missing features to NEW system, then remove OLD system.

**Pros:**
- ✅ Clean, single Art-Net implementation
- ✅ Modern architecture (object-based, multi-output)
- ✅ Removes 445 lines of legacy code
- ✅ Removes confusion about which system to use

**Cons:**
- ❌ Requires adding 4-5 features to new system
- ❌ Needs thorough testing

### **Option B: Disable New System** (Quick but backwards - 30min)
Keep only OLD system, remove NEW routing system.

**Pros:**
- ✅ Very fast
- ✅ Keeps working features

**Cons:**
- ❌ Loses modern routing capabilities
- ❌ Keeps legacy architecture
- ❌ Not forward-looking

### **Option C: Clarify & Coexist** (Compromise - 1h)
Keep both but make it clear which does what.

**Pros:**
- ✅ Fast
- ✅ Preserves both feature sets

**Cons:**
- ❌ Doesn't solve the core confusion
- ❌ Both systems still running

---

## ✅ **RECOMMENDED: Option A - Complete Migration**

### **Phase 1: Add Missing Features to New System** (2-3h)

#### 1.1 Add Test Patterns to RoutingBridge (45min)

**File:** `src/modules/artnet_routing/routing_bridge.py`

Add methods:
```python
def blackout(self):
    """Send all zeros to all outputs"""
    for output_id, sender_info in self.sender.senders.items():
        if sender_info['config'].active:
            # Send 510 zeros per universe
            blackout_data = bytes([0] * 510 * len(sender_info['universes']))
            self.sender.send(output_id, blackout_data)
    logger.info("Blackout sent to all outputs")

def test_pattern(self, color='red'):
    """Send test pattern to all outputs"""
    colors = {
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'white': (255, 255, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255)
    }
    
    rgb = colors.get(color, (255, 0, 0))
    
    # Create test frame filled with color
    test_frame = np.full(
        (self.output_manager.canvas_height, 
         self.output_manager.canvas_width, 3),
        rgb,
        dtype=np.uint8
    )
    
    # Process through normal pipeline
    self.process_frame(test_frame)
    logger.info(f"Test pattern '{color}' sent to all outputs")

def gradient_pattern(self):
    """Send rainbow gradient pattern"""
    height = self.output_manager.canvas_height
    width = self.output_manager.canvas_width
    
    # Create horizontal rainbow gradient
    gradient = np.zeros((height, width, 3), dtype=np.uint8)
    for x in range(width):
        hue = (x / width) * 360
        # Convert HSV to RGB (simplified)
        rgb = self._hsv_to_rgb(hue, 1.0, 1.0)
        gradient[:, x] = rgb
    
    self.process_frame(gradient)
    logger.info("Gradient pattern sent to all outputs")

def _hsv_to_rgb(self, h, s, v):
    """Convert HSV to RGB"""
    import colorsys
    r, g, b = colorsys.hsv_to_rgb(h / 360, s, v)
    return [int(r * 255), int(g * 255), int(b * 255)]
```

#### 1.2 Add Network Stats to ArtNetSender (30min)

**File:** `src/modules/artnet_routing/artnet_sender.py`

Add tracking:
```python
class ArtNetSender:
    def __init__(self):
        self.senders = {}
        # Stats tracking
        self.total_packets_sent = 0
        self.total_bytes_sent = 0
        self.stats_start_time = time.time()
    
    def send(self, output_id: str, dmx_data: bytes):
        # ... existing code ...
        
        # Update stats
        self.total_packets_sent += len(universes)
        self.total_bytes_sent += len(dmx_data)
        
        # ... rest of method ...
    
    def get_network_stats(self):
        """Get network statistics"""
        elapsed = time.time() - self.stats_start_time
        return {
            'total_packets': self.total_packets_sent,
            'total_bytes': self.total_bytes_sent,
            'packets_per_second': self.total_packets_sent / elapsed if elapsed > 0 else 0,
            'bytes_per_second': self.total_bytes_sent / elapsed if elapsed > 0 else 0,
            'uptime_seconds': elapsed
        }
    
    def reset_stats(self):
        """Reset statistics"""
        self.total_packets_sent = 0
        self.total_bytes_sent = 0
        self.stats_start_time = time.time()
```

#### 1.3 Add Replay Mode Support (30min)

**File:** `src/modules/artnet_routing/routing_bridge.py`

Add priority system:
```python
class RoutingBridge:
    def __init__(self, ...):
        # ... existing code ...
        self.replay_mode = False
        self.test_mode = False
    
    def process_frame(self, frame: np.ndarray, source='video'):
        """Process frame with priority: test > replay > video"""
        # Test mode has highest priority (already handled in test_pattern())  
        if self.test_mode:
            return
        
        # Check source priority
        if source == 'replay':
            self.replay_mode = True
        
        # Normal processing
        # ... existing code ...
    
    def send_replay_frame(self, dmx_data: bytes):
        """Send raw DMX data for replay mode"""
        # Send to all active outputs
        for output_id, sender_info in self.sender.senders.items():
            if sender_info['config'].active:
                self.sender.send(output_id, dmx_data)
```

#### 1.4 Update ReplayManager (15min)

**File:** `src/modules/replay_manager.py`

Change from `artnet_manager` to `routing_bridge`:
```python
class ReplayManager:
    def __init__(self, routing_bridge, config, player):  # Changed param
        self.routing_bridge = routing_bridge  # Changed
        # ... rest stays same ...
    
    def start_replay(self, ...):
        if self.routing_bridge:
            self.routing_bridge.replay_mode = True  # Changed
    
    def stop_replay(self):
        if self.routing_bridge:
            self.routing_bridge.replay_mode = False  # Changed
    
    def _replay_thread_func(self):
        # ... in replay loop ...
        if self.routing_bridge and self.routing_bridge.initialized:
            self.routing_bridge.send_replay_frame(dmx_data)  # Changed
```

---

### **Phase 2: Update All References** (30-45min)

#### 2.1 Update main.py

Remove OLD system initialization:
```python
# DELETE THESE LINES (478-486):
# from modules.artnet_manager import ArtNetManager
# artnet_manager = ArtNetManager(...)
# artnet_manager.start(artnet_config)
# register_cleanup_resource('artnet', lambda: artnet_manager.stop())

# KEEP NEW system (554-563) - already there
# Just update ReplayManager initialization:
replay_manager = ReplayManager(routing_bridge, config, player)  # Changed param
```

#### 2.2 Update player_core.py

Remove `artnet_manager` completely:
```python
# DELETE import (line 12):
# from .artnet_manager import ArtNetManager

# DELETE initialization (lines 130, 184):
# self.artnet_manager = None

# DELETE all artnet_manager code blocks (lines 750-752, 819-821, 852-853, etc.)

# KEEP routing_bridge code unchanged

# UPDATE methods to use routing_bridge:
def blackout(self):
    if self.routing_bridge:
        self.routing_bridge.blackout()

def test_pattern(self, color='red'):
    if self.routing_bridge:
        self.routing_bridge.test_pattern(color)

# DELETE set_artnet_manager() method (lines 1607-1623)
# DELETE reload_artnet() method (lines 1609-1621)
```

#### 2.3 Update player_manager.py

Remove `artnet_manager` references:
```python
# DELETE lines 691-692, 859-860 - blackout code
# Blackout will be handled by routing_bridge in player

# Or add helper method:
def send_blackout_to_slave(self, slave_player):
    if hasattr(slave_player, 'routing_bridge') and slave_player.routing_bridge:
        slave_player.routing_bridge.blackout()
```

#### 2.4 Update api_routes.py

Replace `artnet_manager` with `routing_bridge`:
```python
@app.route('/api/artnet/info', methods=['GET'])
def artnet_info():
    artnet_source = player_manager.get_player('artnet')
    
    if not artnet_source or not hasattr(artnet_source, 'routing_bridge'):
        return jsonify({"error": "Art-Net not available"}), 404
    
    bridge = artnet_source.routing_bridge
    
    network_stats = bridge.sender.get_network_stats()
    
    return jsonify({
        "success": True,
        "info": {
            "active": bridge.enabled,
            "outputs": len(bridge.sender.senders),
            "network": network_stats,
            # Delta encoding removed (not needed in new system)
        }
    })

# DELETE /api/artnet/delta-encoding endpoint entirely (lines 255-292)
# (New system doesn't use delta encoding - doc says not needed)
```

#### 2.5 Update rest_api.py

Replace `artnet_manager` usage:
```python
# Lines 704-740 - Update to use routing_bridge
if hasattr(artnet_source, 'routing_bridge') and artnet_source.routing_bridge:
    bridge = artnet_source.routing_bridge
    # Use bridge methods instead of artnet_manager
```

#### 2.6 Update command_executor.py

Delete artnet CLI commands or update:
```python
# Lines 296-299 - Either delete or update:
if hasattr(self.player, 'routing_bridge') and self.player.routing_bridge:
    bridge = self.player.routing_bridge
    # Use bridge methods
```

#### 2.7 Update modules/__init__.py

Remove export:
```python
# DELETE line 26:
# from .artnet_manager import ArtNetManager
```

---

### **Phase 3: Delete Old System** (5min)

```powershell
# Backup first
Copy-Item "src/modules/artnet_manager.py" "src/modules/artnet_manager.py.backup"

# Delete the file
Remove-Item "src/modules/artnet_manager.py"
```

---

### **Phase 4: Testing** (30min)

**Test checklist:**
- [ ] Application starts without import errors
- [ ] Art-Net player sends frames
- [ ] Test pattern works: `/api/test` with color=red
- [ ] Blackout works: `/api/blackout`
- [ ] Replay recording works
- [ ] Network stats visible: `/api/artnet/info`
- [ ] DMX monitor shows output
- [ ] No Python errors in logs

---

## 🚦 **EXECUTION DECISION**

**Before we start, I need your input:**

### **Question 1: Which option?**
- **A)** Complete migration (recommended - 3-4h)
- **B)** Keep old system only (backwards - 30min)
- **C)** Clarify and coexist (compromise - 1h)

### **Question 2: If Option A, can we break things temporarily?**
The new routing system is designed for object-based output (output-settings.html).  
Do you still need the OLD points-based output, or have you fully migrated to the new routing UI?

### **Question 3: What's your setup?**
- Are you using the output routing editor (shapes → outputs)?
- Or the old points.json system?
- Or both?

---

## 📝 **CURRENT RECOMMENDATION**

Based on the code analysis, I recommend:

**Start with Phase 1 (Add missing features) - 2-3h**
- Add test patterns, blackout, stats to routing_bridge
- Don't break anything yet
- Test new features work

**Then Phase 2-3 (Remove old system) - 1h**
- Once new system has all features
- Remove old system
- Update all references

**Total: 3-4 hours for complete, clean migration**

---

## 🎬 **READY TO START?**

Tell me:
1. Which option (A, B, or C)?
2. Should I start with Phase 1.1 (add test patterns)?
3. Or do you want to review the plan first?

I can begin immediately once you confirm! 🚀
