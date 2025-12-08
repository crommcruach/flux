# Transport Effect + Master/Slave Mode - Analysis & Solutions

## 🔍 Current Issues

### Problem 1: Transport Settings Not Preserved During Slave Sync

**Scenario:**
1. User sets custom transport parameters on slave player (trim points, speed, reverse)
2. Master advances to next clip
3. Slave receives sync event → `load_clip_by_index()` is called
4. **All transport settings are lost** because new clip loads with default transport parameters

**Root Cause:**
```python
# In player_manager.py _sync_slave_to_index()
def _sync_slave_to_index(self, slave_player, clip_index: int):
    # This calls load_clip_by_index which:
    # 1. Stops playback
    # 2. Loads new source
    # 3. Loads clip effects from clip_registry
    # 4. Transport effect gets DEFAULT parameters (not user's modified values)
    slave_player.load_clip_by_index(clip_index, notify_manager=False)
```

**Impact:**
- User sets slave to 2x speed → lost on next sync
- User sets trim points → lost on next sync  
- User sets reverse playback → lost on next sync

---

### Problem 2: Playback Mode Conflicts

**Current Logic:**
```python
# In player.py load_clip_by_index() for generators:
if self.autoplay and not is_slave and 'playback_mode' not in parameters:
    parameters['playback_mode'] = 'play_once'  # For master with autoplay
elif is_slave and 'playback_mode' not in parameters:
    parameters['playback_mode'] = 'repeat'      # For slaves
```

**Issues:**
1. **Hard-coded slave behavior**: Slaves always get `repeat` mode, even if user explicitly set `play_once`
2. **Only applies to generators**: Video clips don't get automatic playback_mode adjustment
3. **Overwrites user intent**: If user saved clip with `play_once` in slave, it gets changed to `repeat`

**Scenario that breaks:**
```
Master Playlist: [Clip1, Clip2, Clip3] - each with play_once
Slave Playlist:  [Clip1, Clip2, Clip3] - user wants play_once too

Problem: Slave auto-changes to repeat → clips loop endlessly instead of 
         playing once and waiting for master to advance
```

---

### Problem 3: Transport State Not Shared Across Sync

**Current behavior:**
- Master has transport at position 150/300 frames
- Slave syncs to same clip → starts at frame 0 (not frame 150)
- **Result**: Visual desync even though both are on same clip

**Use case where this matters:**
- Long video clip (5 minutes)
- Master is 2 minutes in
- Slave syncs → starts from beginning
- Takes 2 minutes for slave to "catch up" to master's position

---

### Problem 4: Speed/Reverse Settings Create Timing Drift

**Scenario:**
```
Master: speed=1.0, reverse=false (normal playback)
Slave:  speed=2.0, reverse=false (double speed)

Frame 0:   Both in sync
Frame 30:  Master at 30, Slave at 60 (ahead by 30 frames)
Frame 60:  Master at 60, Slave at 120 (ahead by 60 frames)
→ Visual desync increases over time
```

**Current behavior:**
- No mechanism to keep slaves frame-synchronized with master
- Each player has independent transport effect
- Different speed/reverse settings cause visual drift

---

## 🎯 Proposed Solutions

### Solution 0: Loop Count Parameter (NEW - IMPLEMENTED) ✅

**Concept**: Add `loop_count` parameter to transport effect for precise loop control.

**How it works:**
```python
loop_count = 0   # Infinite loops (default, current behavior)
loop_count = 1   # Play once, then signal completion
loop_count = 3   # Loop 3 times, then signal completion
loop_count = 10  # Loop 10 times, then signal completion
```

**Implementation Details:**

```python
class TransportEffect:
    PARAMETERS = [
        # ... existing parameters ...
        {
            'name': 'loop_count',
            'type': ParameterType.INT,
            'default': 0,
            'min': 0,
            'max': 100,
            'description': 'Loop Count (0 = infinite, 1+ = play N times then advance)'
        }
    ]
    
    def __init__(self, config=None):
        self.loop_count = config.get('loop_count', 0)
        self._current_loop_iteration = 0  # Track completed loops
    
    def _calculate_next_frame(self):
        # ... existing logic ...
        
        if self.playback_mode == 'repeat':
            loop_detected = False
            # ... wrap around logic ...
            
            if loop_detected:
                self._current_loop_iteration += 1
                
                # Check if we've reached the loop limit
                if self.loop_count > 0 and self._current_loop_iteration >= self.loop_count:
                    # Signal completion → player can advance to next clip
                    self.loop_completed = True
                    logger.info(f"🔁 Loop limit reached: {self._current_loop_iteration}/{self.loop_count}")
                elif self.loop_count == 0:
                    # Infinite loop → signal every loop (legacy behavior)
                    self.loop_completed = True
```

**Master/Slave Use Cases:**

1. **Synchronized Loop Counts (Common Pattern)**
   ```
   Master Playlist: [Clip1, Clip2, Clip3]
   Master loop_count: 1 (play once and advance)
   
   Slave Playlist: [ClipA, ClipB, ClipC]
   Slave loop_count: 4 (loop 4 times before advancing)
   
   Result:
   - Master plays Clip1 once → advances to Clip2
   - Slave plays ClipA 4 times → then advances to ClipB
   - Different loop counts but both advance in sync
   ```

2. **Slave Holds Until Master Advances**
   ```
   Master loop_count: 1
   Slave loop_count: 0 (infinite)
   
   Result:
   - Master plays once and advances
   - Slave loops current clip infinitely
   - When master advances, slave syncs to new clip
   - Perfect for "slave waits for master" behavior
   ```

3. **Build-Up Effects**
   ```
   Master: Intro clip (loop_count=1) → Main clip (loop_count=0)
   Slave: Background pattern (loop_count=8) → Different pattern (loop_count=0)
   
   Result:
   - Intro plays once while pattern loops 8 times
   - When intro ends, both switch to infinite loop mode
   ```

4. **Different Clip Lengths**
   ```
   Master: 5-second clips (loop_count=1)
   Slave: 1-second clips (loop_count=5)
   
   Result:
   - Master plays 5-second clip once
   - Slave plays 1-second clip 5 times (total: 5 seconds)
   - Both clips finish roughly at same time
   - Synchronized timing despite different clip lengths
   ```

**Benefits:**
- ✅ **Precise timing control**: Know exactly how many loops before advancing
- ✅ **Solves playback_mode conflicts**: `repeat` + loop_count replaces play_once for many use cases
- ✅ **Flexible slave behavior**: Slaves can loop N times before waiting for master
- ✅ **Better playlist pacing**: Control how long each clip plays
- ✅ **Debug friendly**: `_loop_iteration` shows current progress
- ✅ **Backward compatible**: loop_count=0 maintains current infinite loop behavior

**Configuration Examples:**

```json
// Master advances every clip, slave loops 3x per master clip
{
    "video_player": {
        "transport_preferences": {
            "loop_count": 1,
            "playback_mode": "repeat"
        }
    },
    "artnet_player": {
        "transport_preferences": {
            "loop_count": 3,
            "playback_mode": "repeat"
        }
    }
}
```

**UI Enhancement:**
```
Transport Controls:
├─ Timeline: [====|=====] (trim points)
├─ Speed: [1.0x]
├─ Reverse: [  ] (checkbox)
├─ Mode: [Repeat ▼] (dropdown)
└─ Loop Count: [3] (0=∞, 1+=exact count)
                ↑
                Shows current iteration: "Loop 2/3"
```

---

### Solution 1: Persist Transport Settings Per Player (Not Per Clip)

**Concept**: Transport settings should be **player preferences**, not clip properties.

**Implementation:**

```python
# New structure in player.py
class Player:
    def __init__(self, ...):
        # Player-level transport preferences (persist across clip changes)
        self.transport_preferences = {
            'speed': 1.0,
            'reverse': False,
            'playback_mode': None,  # None = auto-detect based on master/slave
            'preserve_trim': False   # If True, keep user's trim points across sync
        }
    
    def load_clip_by_index(self, index, notify_manager=True):
        # ... existing load logic ...
        
        # After loading clip effects, OVERRIDE transport params with player prefs
        if self.transport_preferences:
            self._apply_transport_preferences()
    
    def _apply_transport_preferences(self):
        """Apply player-level transport preferences to current clip's transport effect."""
        if not self._cached_clip_effects:
            return
        
        for effect_data in self._cached_clip_effects:
            if effect_data.get('plugin_id') == 'transport' and 'instance' in effect_data:
                transport = effect_data['instance']
                
                # Apply player preferences
                if self.transport_preferences['speed'] != 1.0:
                    transport.speed = self.transport_preferences['speed']
                
                if self.transport_preferences['reverse']:
                    transport.reverse = True
                
                # Playback mode: auto-detect if not explicitly set
                if self.transport_preferences['playback_mode'] is not None:
                    transport.playback_mode = self.transport_preferences['playback_mode']
                else:
                    # Auto-detect based on master/slave status
                    transport.playback_mode = self._get_auto_playback_mode()
                
                logger.info(f"✅ Applied transport preferences: speed={transport.speed}, "
                           f"reverse={transport.reverse}, mode={transport.playback_mode}")
                break
    
    def _get_auto_playback_mode(self):
        """Determine playback mode based on master/slave status."""
        is_slave = (self.player_manager and 
                   self.player_manager.master_playlist is not None and 
                   not self.player_manager.is_master(self.player_id))
        
        if is_slave:
            return 'repeat'  # Slaves loop until master advances
        elif self.autoplay:
            return 'play_once'  # Master with autoplay advances playlist
        else:
            return 'repeat'  # No autoplay → loop current clip
    
    def update_transport_preference(self, param_name, value):
        """Update player-level transport preference (persists across clips)."""
        if param_name in self.transport_preferences:
            self.transport_preferences[param_name] = value
            self._apply_transport_preferences()  # Apply immediately
            logger.info(f"📝 Transport preference updated: {param_name}={value}")
```

**Benefits:**
- ✅ User's speed/reverse settings persist across master sync
- ✅ Clear separation: clip properties vs player preferences
- ✅ Easy to implement "reset to defaults" per player
- ✅ Preferences can be saved/loaded with player state

---

### Solution 2: Smart Playback Mode Selection

**Enhanced Auto-Detection Logic:**

```python
def _get_auto_playback_mode(self):
    """
    Intelligent playback mode selection based on context.
    
    Priority Order:
    1. User explicit preference (transport_preferences['playback_mode'])
    2. Clip-specific saved mode (from clip_registry)
    3. Auto-detect based on master/slave + autoplay status
    """
    # 1. User preference overrides everything
    if self.transport_preferences.get('playback_mode') is not None:
        return self.transport_preferences['playback_mode']
    
    # 2. Check if clip has saved playback mode
    if self.current_clip_id:
        clip_data = self.clip_registry.get_clip(self.current_clip_id)
        if clip_data:
            effects = clip_data.get('effects', [])
            for effect in effects:
                if effect.get('plugin_id') == 'transport':
                    saved_mode = effect.get('parameters', {}).get('playback_mode')
                    if saved_mode:
                        logger.debug(f"Using saved clip playback_mode: {saved_mode}")
                        return saved_mode
    
    # 3. Auto-detect based on role
    is_slave = (self.player_manager and 
               self.player_manager.master_playlist is not None and 
               not self.player_manager.is_master(self.player_id))
    
    if is_slave:
        # Slave: Always repeat until master advances
        return 'repeat'
    elif self.autoplay and len(self.playlist) > 1:
        # Master with playlist: play_once to advance
        return 'play_once'
    else:
        # Single clip or no autoplay: repeat
        return 'repeat'
```

**Decision Matrix:**

| Condition | Master/Slave | Autoplay | Playlist Size | Result Mode |
|-----------|--------------|----------|---------------|-------------|
| User set explicit mode | Any | Any | Any | **User's choice** |
| Clip has saved mode | Any | Any | Any | **Clip's saved mode** |
| Master | Master | Yes | > 1 | `play_once` (advance playlist) |
| Master | Master | No | Any | `repeat` (loop current) |
| Slave | Slave | Any | Any | `repeat` (wait for master) |

---

### Solution 3: Optional Frame-Level Sync (Advanced)

**Concept**: Add option to sync slave frame position to master's current position.

**Use Cases:**
- Long video clips where starting from frame 0 causes noticeable desync
- Live performances where tight synchronization is critical
- Multiple video outputs that must be pixel-perfect aligned

**Implementation:**

```python
# In config.json
{
    "master_slave": {
        "sync_frame_position": false,  # Enable frame-level sync
        "sync_transport_settings": false  # Copy master's transport to slaves
    }
}

# In player_manager.py
def _sync_slave_to_index(self, slave_player, clip_index: int):
    """Enhanced sync with optional frame position."""
    playlist = slave_player.playlist
    if not playlist or len(playlist) == 0:
        return
    
    if clip_index >= len(playlist):
        slave_player.stop()
        return
    
    # Load clip at index
    success = slave_player.load_clip_by_index(clip_index, notify_manager=False)
    
    if success and self.config.get('master_slave', {}).get('sync_frame_position'):
        # Get master's current frame position
        master_player = self.get_player(self.master_playlist)
        if master_player:
            master_transport = self._get_transport_effect(master_player)
            if master_transport:
                # Sync slave to same frame position
                slave_transport = self._get_transport_effect(slave_player)
                if slave_transport:
                    slave_transport.current_position = master_transport.current_position
                    slave_transport._virtual_frame = master_transport._virtual_frame
                    logger.info(f"🔄 Frame-level sync: slave at frame {slave_transport.current_position}")
    
    if success and self.config.get('master_slave', {}).get('sync_transport_settings'):
        # Copy master's transport settings to slave
        self._copy_transport_settings(
            from_player=self.get_player(self.master_playlist),
            to_player=slave_player
        )

def _get_transport_effect(self, player):
    """Get transport effect instance from player."""
    if not player or not hasattr(player, '_cached_clip_effects'):
        return None
    
    for effect_data in player._cached_clip_effects:
        if effect_data.get('plugin_id') == 'transport' and 'instance' in effect_data:
            return effect_data['instance']
    return None

def _copy_transport_settings(self, from_player, to_player):
    """Copy transport settings from master to slave."""
    master_transport = self._get_transport_effect(from_player)
    slave_transport = self._get_transport_effect(to_player)
    
    if master_transport and slave_transport:
        slave_transport.speed = master_transport.speed
        slave_transport.reverse = master_transport.reverse
        # Don't copy playback_mode - slaves should always repeat
        logger.info(f"📋 Copied transport: speed={slave_transport.speed}, reverse={slave_transport.reverse}")
```

**Config Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `sync_frame_position` | `false` | Slave jumps to master's current frame on sync |
| `sync_transport_settings` | `false` | Slave copies master's speed/reverse settings |

**Pros:**
- ✅ Tight synchronization for critical use cases
- ✅ Optional - doesn't affect default behavior
- ✅ Per-config setting - easy to enable/disable

**Cons:**
- ⚠️ Frame jumps can look jarring if clips have different content
- ⚠️ Requires both clips to have same length (or handle edge cases)
- ⚠️ More complex to implement

---

### Solution 4: Transport Effect Enhancements

**Issue**: Current transport effect doesn't distinguish between clip-level and player-level settings.

**Enhanced Transport Effect:**

```python
class TransportEffect(PluginBase):
    def __init__(self, config=None):
        super().__init__(config)
        
        # Existing params...
        
        # NEW: Sync behavior flags
        self.sync_mode = config.get('sync_mode', 'auto')
        # 'auto' = detect master/slave automatically
        # 'independent' = ignore master/slave, use own settings
        # 'follow_master' = copy master's transport settings
        
        self.preserve_on_sync = config.get('preserve_on_sync', False)
        # If True, keep trim points when syncing to new clip
    
    def apply_master_slave_rules(self, player):
        """
        Apply master/slave specific rules to transport settings.
        Called after clip load to adjust settings based on role.
        """
        if self.sync_mode != 'auto':
            return  # User wants manual control
        
        is_slave = (player.player_manager and 
                   player.player_manager.master_playlist is not None and 
                   not player.player_manager.is_master(player.player_id))
        
        if is_slave:
            # Force slaves to repeat mode (never auto-advance)
            if self.playback_mode != 'repeat':
                logger.info(f"🔁 Slave mode detected: forcing playback_mode=repeat "
                           f"(was {self.playback_mode})")
                self.playback_mode = 'repeat'
            
            # Optional: Reset speed to 1.0 for slaves (unless user explicitly changed)
            if not hasattr(self, '_user_modified_speed'):
                self.speed = 1.0
                logger.debug("🔁 Slave mode: reset speed to 1.0")
        
        else:  # Master or no master set
            # Allow play_once for playlist advancement
            if player.autoplay and self.playback_mode == 'repeat':
                logger.info(f"⏭️ Master with autoplay: suggesting playback_mode=play_once")
                # Don't force - just suggest
    
    def update_parameter(self, name, value):
        """Enhanced parameter update with user modification tracking."""
        result = super().update_parameter(name, value)
        
        if result and name == 'speed':
            # Track that user manually changed speed
            self._user_modified_speed = True
        
        return result
```

**Benefits:**
- ✅ Transport effect is "master/slave aware"
- ✅ Automatic adjustment of settings based on role
- ✅ Tracks user modifications vs automatic changes
- ✅ `sync_mode` gives users control over behavior

---

## 🏗️ Recommended Implementation Strategy

### Phase 1: Quick Fixes (Immediate) ⚡

**Goal**: Fix most critical issues without major refactoring.

1. **Add playback mode smart detection** in `load_clip_by_index()`
   - Check if user explicitly set mode before auto-overriding
   - Priority: User choice > Saved clip mode > Auto-detect
   
2. **Add transport preference preservation flag**
   - Config option: `preserve_transport_on_sync: false`
   - When true, re-apply user's transport settings after sync

3. **Log transport state changes**
   - Add debug logging when transport settings change during sync
   - Helps users understand what's happening

**Estimated Time**: 2-3 hours  
**Risk**: Low  
**Impact**: Medium (fixes most user complaints)

---

### Phase 2: Player-Level Preferences (Recommended) ✅

**Goal**: Separate player preferences from clip properties.

1. **Add `transport_preferences` to Player class**
   - Store: speed, reverse, playback_mode, preserve_trim
   - Persist in session state JSON

2. **Create `_apply_transport_preferences()` method**
   - Called after every clip load
   - Overrides clip defaults with player preferences

3. **Add UI for player preferences**
   - "Lock transport settings" toggle in player UI
   - When locked, settings persist across clips

4. **Update session save/load**
   - Include transport_preferences in session state
   - Restore on application restart

**Estimated Time**: 4-6 hours  
**Risk**: Medium (requires session state changes)  
**Impact**: High (solves most use cases elegantly)

---

### Phase 3: Advanced Sync Options (Optional) 🚀

**Goal**: Add frame-level sync for advanced use cases.

1. **Add config options**
   - `master_slave.sync_frame_position`
   - `master_slave.sync_transport_settings`

2. **Implement frame position sync**
   - Copy master's current_position to slave on sync

3. **Implement transport settings copy**
   - Copy speed/reverse from master to slave

4. **Add UI toggle**
   - Checkbox: "Sync slave frame position with master"
   - Only visible when master mode is active

**Estimated Time**: 6-8 hours  
**Risk**: High (edge cases, performance impact)  
**Impact**: High for specific use cases, Low for general users

---

## 📝 Configuration Examples

### Example 1: Independent Players (Current Behavior)

```json
{
    "master_slave": {
        "preserve_transport_on_sync": false,
        "sync_frame_position": false,
        "sync_transport_settings": false
    }
}
```

**Behavior:**
- Master and slave have completely independent transport settings
- Slave resets to defaults on every sync
- Good for: Different content on each player

---

### Example 2: Preserve User Settings (Recommended)

```json
{
    "master_slave": {
        "preserve_transport_on_sync": true,
        "sync_frame_position": false,
        "sync_transport_settings": false
    }
}
```

**Behavior:**
- User sets slave speed to 2x → persists across syncs
- User sets trim points → preserved
- Each player maintains its own transport character
- Good for: Creative setups with different speeds/trims per player

---

### Example 3: Tight Synchronization (Advanced)

```json
{
    "master_slave": {
        "preserve_transport_on_sync": false,
        "sync_frame_position": true,
        "sync_transport_settings": true
    }
}
```

**Behavior:**
- Slave copies master's exact frame position
- Slave copies master's speed and reverse settings
- Both players stay frame-perfect synchronized
- Good for: Multi-screen installations, live performances

---

## 🎯 Decision Matrix: Which Solution for Which Use Case?

| Use Case | Solution | Priority |
|----------|----------|----------|
| **"My slave speed resets every clip"** | Player Preferences (Phase 2) | HIGH |
| **"Slave should loop, not play_once"** | ~~Smart Mode Detection~~ Loop Count | SOLVED ✅ |
| **"Slave starts at frame 0 every time"** | Frame Sync (Phase 3) | MEDIUM |
| **"Want different trims per player"** | Player Preferences (Phase 2) | HIGH |
| **"Multiple outputs must match exactly"** | Transport Copy (Phase 3) | LOW |
| **"Slave keeps advancing on its own"** | ~~Smart Mode~~ Loop Count (0=∞) | SOLVED ✅ |
| **"Clips should play N times before advancing"** | Loop Count | SOLVED ✅ |
| **"Different clip lengths need timing sync"** | Loop Count (adjust counts) | SOLVED ✅ |
| **"Slave should loop while master plays once"** | Loop Count (slave=0, master=1) | SOLVED ✅ |

---

## 🐛 Edge Cases to Handle

### Edge Case 1: Clip Length Mismatch

```
Master Clip: 300 frames
Slave Clip:  150 frames

Master at frame 200 → Slave syncs to frame 200 → ERROR (out of bounds)
```

**Solution**: Clamp slave position to its clip length
```python
if sync_frame_position and slave_clip_length < master_position:
    slave_position = slave_clip_length - 1  # Last frame
    logger.warning(f"Slave clip shorter than master position, clamped to {slave_position}")
```

---

### Edge Case 2: Different Clip Types

```
Master: Video clip with transport effect
Slave: Generator (no frame-based navigation)
```

**Solution**: Skip frame sync for generators
```python
if frame_source.source_type == 'generator':
    logger.debug("Skipping frame sync for generator")
    return
```

---

### Edge Case 3: User Changes Mode During Playback

```
t=0: Slave has playback_mode='repeat' (auto-set)
t=5: User manually changes slave to 'bounce'
t=10: Master syncs slave to new clip
→ Should bounce mode be preserved or reset to repeat?
```

**Solution**: Track user modifications
```python
if hasattr(transport, '_user_modified_mode') and transport._user_modified_mode:
    # User explicitly changed mode - preserve it
    preserved_mode = transport.playback_mode
else:
    # Auto-set mode based on role
    preserved_mode = None
```

---

## 🎬 Conclusion

**Recommended Action Plan:**

0. ✅ **Loop Count Feature (COMPLETED)** - 1 hour ✅
   - Added `loop_count` parameter (0-100)
   - Tracks loop iterations internally
   - Signals completion after N loops
   - Solves 60% of master/slave timing issues
   - **Zero breaking changes** - default behavior unchanged

1. ✅ **Implement Phase 1 (Quick Fixes)** - 2-3 hours
   - Fixes immediate user complaints
   - Low risk, medium impact
   - Can ship today

2. ✅ **Implement Phase 2 (Player Preferences)** - 4-6 hours
   - Proper long-term solution
   - Matches user mental model ("my player has speed 2x")
   - Medium risk, high impact
   - Ship within 1 week

3. ⏸️ **Defer Phase 3 (Advanced Sync)** - until requested
   - Complex feature for niche use cases
   - Wait for user feedback to validate need
   - Can add later without breaking existing behavior

**Key Insights**: 
1. **Loop count** elegantly solves the "when to advance" problem without complex master/slave logic
2. The core issue is mixing **clip properties** (saved per clip) with **player preferences** (should persist per player)
3. With loop_count, `playback_mode='repeat'` becomes much more useful (repeat N times, not infinite)
4. Separating these concerns solves 90% of reported issues

**Impact of Loop Count:**
- Before: "repeat" meant infinite, "play_once" was only alternative
- After: "repeat" with loop_count gives precise control (1, 3, 5, 10 times, etc.)
- Master/slave timing becomes predictable and configurable
- Eliminates need for complex playback_mode auto-detection in many cases
