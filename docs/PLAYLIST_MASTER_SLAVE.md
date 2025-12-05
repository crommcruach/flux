       # Playlist Master/Slave Synchronization

## 📋 Übersicht

Synchronisiert mehrere Playlists (Video + Art-Net) durch Master/Slave-Relationship. Der Master bestimmt, welcher Clip in der Sequenz aktiv ist, und alle Slaves folgen automatisch.

---

## 🎯 Ziel

- **Synchrone Shows**: Video- und Art-Net-Ausgabe laufen synchron (gleicher Clip-Index)
- **Flexible Steuerung**: Jede Playlist kann Master sein
- **Autonome Effekte**: Jede Playlist behält ihre eigenen Effekte und Transitions
- **Sofortige Reaktion**: Slaves wechseln sofort, wenn Master wechselt (auch bei laufendem Clip)

---

## 🔧 Funktionsweise

### Grundprinzip

```
┌─────────────────────────────────────────────────────────────┐
│ MASTER PLAYLIST (Video)                                     │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                   │
│ │Clip1│ │Clip2│ │Clip3│ │Clip4│ │Clip5│  ← Clip 4 aktiv  │
│ └─────┘ └─────┘ └─────┘ └──👑──┘ └─────┘                   │
└────────────────────────┬────────────────────────────────────┘
                         │ Sync Event
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ SLAVE PLAYLIST (Art-Net)                                    │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐                   │
│ │Clip1│ │Clip2│ │Clip3│ │Clip4│ │Clip5│  → Springt zu 4   │
│ └─────┘ └─────┘ └─────┘ └──⚡──┘ └─────┘                   │
└─────────────────────────────────────────────────────────────┘
```

### Ablauf

1. **Master aktivieren**: User klickt Master-Toggle auf Video-Playlist
2. **Initial Sync**: Art-Net Playlist wechselt sofort zu aktuellem Video-Clip-Index
3. **Laufende Sync**: Jeder Clip-Wechsel im Master triggert Sync-Event
4. **Slave-Reaktion**: Slave wechselt sofort zu neuem Clip-Index (mit eigener Transition)

---

## 🏗️ Architektur

### Backend-Komponenten

#### 1. PlayerManager - Master/Slave State

```python
class PlayerManager:
    def __init__(self):
        self.master_playlist = None  # 'video' oder 'artnet' oder None
        self.sync_observers = []  # Event-Listener für Sync
    
    def set_master_playlist(self, player_id: str) -> bool:
        """
        Setzt eine Playlist als Master, alle anderen werden Slaves.
        
        Args:
            player_id: 'video' oder 'artnet' oder None (deaktiviert Master)
        
        Returns:
            True wenn erfolgreich
        """
        if player_id not in ['video', 'artnet', None]:
            return False
        
        old_master = self.master_playlist
        self.master_playlist = player_id
        
        # Initial Sync: Wenn Master aktiviert, synchronisiere alle Slaves
        if player_id is not None:
            self.sync_slaves_to_master()
        
        logger.info(f"👑 Master playlist: {old_master} → {player_id}")
        return True
    
    def sync_slaves_to_master(self):
        """
        Synchronisiert alle Slave-Playlists zum Master-Clip-Index.
        """
        if not self.master_playlist:
            return
        
        master_player = self.get_player(self.master_playlist)
        if not master_player:
            return
        
        master_clip_index = master_player.get_current_clip_index()
        
        # Synchronisiere alle Slaves
        for player_id in ['video', 'artnet']:
            if player_id == self.master_playlist:
                continue
            
            slave_player = self.get_player(player_id)
            if slave_player:
                self._sync_slave_to_index(slave_player, master_clip_index)
    
    def _sync_slave_to_index(self, slave_player, clip_index: int):
        """
        Synchronisiert einzelnen Slave zu Clip-Index.
        
        Edge-Cases:
        - Slave hat weniger Clips als Index → Slave wird gestoppt (schwarzer Screen)
        - Clip-Index ungültig → Keine Aktion
        - Slave hat leere Playlist → Keine Aktion
        """
        playlist = slave_player.get_playlist()
        if not playlist or len(playlist) == 0:
            return
        
        # Wenn Slave nicht genug Clips hat → Stoppe Playback
        if clip_index >= len(playlist):
            slave_player.stop()
            logger.info(f"⏹️ Slave {slave_player.player_id} stopped (index {clip_index} out of range, has {len(playlist)} clips)")
            return
        
        # Lade Clip an Index
        clip = playlist[clip_index]
        slave_player.load_clip_by_index(clip_index)
        
        logger.debug(f"🔄 Slave {slave_player.player_id} synced to index {clip_index}")
    
    def on_clip_changed(self, player_id: str, clip_index: int):
        """
        Event-Handler: Wird aufgerufen wenn Clip wechselt.
        Wenn Player ist Master → Synchronisiere alle Slaves.
        """
        if player_id != self.master_playlist:
            return  # Nicht Master, keine Sync-Aktion
        
        logger.debug(f"👑 Master clip changed to index {clip_index}")
        
        # Synchronisiere alle Slaves
        for slave_id in ['video', 'artnet']:
            if slave_id == self.master_playlist:
                continue
            
            slave_player = self.get_player(slave_id)
            if slave_player:
                self._sync_slave_to_index(slave_player, clip_index)
```

#### 2. Player - Clip-Index Tracking

```python
class Player:
    def __init__(self, ...):
        # ... existing code ...
        self.current_clip_index = 0  # Track current position in playlist
    
    def get_current_clip_index(self) -> int:
        """Gibt aktuellen Clip-Index in Playlist zurück."""
        return self.current_clip_index
    
    def load_clip_by_index(self, index: int) -> bool:
        """
        Lädt Clip an bestimmtem Index in Playlist.
        
        Args:
            index: Position in Playlist (0-based)
        
        Returns:
            True wenn erfolgreich
        """
        playlist = self.get_playlist()
        if not playlist or index < 0 or index >= len(playlist):
            return False
        
        clip = playlist[index]
        self.current_clip_index = index
        
        # Lade Clip (Video oder Generator)
        if clip.get('type') == 'generator':
            self.load_generator_clip(clip['generator_id'], clip['id'], ...)
        else:
            self.load_video_clip(clip['path'], clip['id'])
        
        # Notify PlayerManager about clip change
        if hasattr(self, 'player_manager') and self.player_manager:
            self.player_manager.on_clip_changed(self.player_id, index)
        
        return True
    
    def next_clip(self):
        """Wechselt zum nächsten Clip in Playlist."""
        playlist = self.get_playlist()
        if not playlist:
            return
        
        next_index = (self.current_clip_index + 1) % len(playlist)
        self.load_clip_by_index(next_index)
    
    def previous_clip(self):
        """Wechselt zum vorherigen Clip in Playlist."""
        playlist = self.get_playlist()
        if not playlist:
            return
        
        prev_index = (self.current_clip_index - 1) % len(playlist)
        self.load_clip_by_index(prev_index)
```

---

### REST API Endpoints

#### 1. Set Master Playlist

```
POST /api/player/{player_id}/set_master
```

**Request Body:**
```json
{
  "enabled": true  // false deaktiviert Master-Mode
}
```

**Response:**
```json
{
  "success": true,
  "master_playlist": "video",  // oder "artnet" oder null
  "synced_slaves": ["artnet"],
  "message": "Master playlist set to video"
}
```

**Implementierung:**
```python
@app.route('/api/player/<player_id>/set_master', methods=['POST'])
def set_master_playlist(player_id):
    """
    Aktiviert/deaktiviert Master-Mode für Playlist.
    """
    data = request.get_json()
    enabled = data.get('enabled', True)
    
    if enabled:
        success = player_manager.set_master_playlist(player_id)
    else:
        success = player_manager.set_master_playlist(None)
    
    if not success:
        return jsonify({
            'success': False,
            'error': f'Invalid player_id: {player_id}'
        }), 400
    
    return jsonify({
        'success': True,
        'master_playlist': player_manager.master_playlist,
        'synced_slaves': [p for p in ['video', 'artnet'] 
                          if p != player_manager.master_playlist]
    })
```

#### 2. Get Sync Status

```
GET /api/player/sync_status
```

**Response:**
```json
{
  "success": true,
  "master_playlist": "video",
  "slaves": ["artnet"],
  "master_clip_index": 4,
  "slave_clip_indices": {
    "artnet": 4
  }
}
```

#### 3. Unified Player Status (erweitert)

Erweitere bestehenden `/api/player/{player_id}/status` Endpoint:

```json
{
  "success": true,
  "is_playing": true,
  "current_clip_index": 4,  // NEU
  "is_master": true,         // NEU
  "master_playlist": "video", // NEU (nur wenn is_master = true)
  "...": "... existing fields ..."
}
```

---

### Frontend UI

#### 1. Master Toggle Button

**Position:** Playlist-Header (neben Autoplay/Loop Buttons)

```html
<button id="videoMasterToggle" 
        class="btn btn-sm btn-outline-warning"
        onclick="toggleMasterPlaylist('video')">
    <span class="master-icon">👑</span>
    Master
</button>
```

**States:**
- **Inactive** (btn-outline-warning): Grauer Button, kein Icon
- **Active** (btn-warning): Goldener Button, 👑 Icon

#### 2. Visual Feedback

**Master Playlist:**
```css
.playlist-header.master {
    border: 2px solid gold;
    background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);
}

.playlist-header.master::before {
    content: '👑';
    font-size: 1.5rem;
    margin-right: 0.5rem;
}
```

**Slave Playlist (während Sync):**
```css
@keyframes sync-pulse {
    0% { box-shadow: 0 0 0 0 rgba(0, 123, 255, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(0, 123, 255, 0); }
    100% { box-shadow: 0 0 0 0 rgba(0, 123, 255, 0); }
}

.playlist-item.syncing {
    animation: sync-pulse 0.5s ease-out;
}
```

#### 3. JavaScript Implementation

```javascript
let masterPlaylist = null;  // 'video' oder 'artnet' oder null

async function toggleMasterPlaylist(playerId) {
    const enabled = (masterPlaylist !== playerId);
    
    try {
        const response = await fetch(`${API_BASE}/api/player/${playerId}/set_master`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled })
        });
        
        const data = await response.json();
        
        if (data.success) {
            masterPlaylist = data.master_playlist;
            updateMasterUI();
            showToast(enabled ? 
                `👑 ${playerId} is now Master` : 
                '🔓 Master mode disabled', 
                'success'
            );
        }
    } catch (error) {
        console.error('Error toggling master:', error);
        showToast('Failed to toggle master mode', 'error');
    }
}

function updateMasterUI() {
    // Update button states
    ['video', 'artnet'].forEach(playerId => {
        const btn = document.getElementById(`${playerId}MasterToggle`);
        const header = document.getElementById(`${playerId}PlaylistHeader`);
        
        if (masterPlaylist === playerId) {
            btn.classList.remove('btn-outline-warning');
            btn.classList.add('btn-warning');
            header.classList.add('master');
        } else {
            btn.classList.remove('btn-warning');
            btn.classList.add('btn-outline-warning');
            header.classList.remove('master');
        }
    });
}

// Poll sync status (optional, für realtime feedback)
setInterval(async () => {
    if (!masterPlaylist) return;
    
    const response = await fetch(`${API_BASE}/api/player/sync_status`);
    const data = await response.json();
    
    if (data.success) {
        // Update UI mit Sync-Status
        // z.B. Highlight der aktuellen Clips
    }
}, 1000);
```

---

## 🎬 User Stories

### Story 1: Aktiviere Master-Mode

```
GIVEN: Zwei Playlists (Video + Art-Net) mit Clips
WHEN: User klickt "Master" Button auf Video-Playlist
THEN: 
  - Video wird als Master markiert (👑 Icon)
  - Art-Net springt sofort zum gleichen Clip-Index wie Video
  - Art-Net folgt allen weiteren Clip-Wechseln von Video
```

### Story 2: Wechsel während Playback

```
GIVEN: Master-Mode aktiv, Video bei Clip 3, Art-Net bei Clip 3
WHEN: Video wechselt zu Clip 4 (automatisch oder manuell)
THEN: 
  - Art-Net wechselt sofort zu Clip 4
  - Transition von Art-Net wird verwendet (nicht die von Video)
  - Effekte von Art-Net bleiben erhalten
```

### Story 3: Ungleiche Playlist-Längen

```
GIVEN: Master-Mode aktiv
  - Video: 10 Clips
  - Art-Net: 5 Clips (nur Clips 0-4)
WHEN: Video wechselt zu Clip 7 (Index 7)
THEN: 
  - Art-Net wird gestoppt (schwarzer Screen)
  - Info-Message: "Slave artnet stopped (index 7 out of range)"
WHEN: Video wechselt zurück zu Clip 3
THEN:
  - Art-Net startet wieder und spielt Clip 3
```

### Story 4: Deaktiviere Master-Mode

```
GIVEN: Master-Mode aktiv auf Video
WHEN: User klickt "Master" Button erneut
THEN: 
  - Master-Mode wird deaktiviert
  - Beide Playlists laufen wieder autonom
  - Kein Sync mehr bei Clip-Wechsel
```

---

## ⚙️ Konfiguration

### Session State Persistence

```json
{
  "player_manager": {
    "master_playlist": "video",
    "sync_enabled": true
  }
}
```

### Config.json (optional)

```json
{
  "playlist_sync": {
    "enabled": true,
    "default_master": null,  // 'video', 'artnet', oder null
    "sync_on_startup": false
  }
}
```

---

## 🧪 Testing

### Unit Tests

```python
def test_set_master_playlist():
    pm = PlayerManager()
    
    # Aktiviere Master
    assert pm.set_master_playlist('video') == True
    assert pm.master_playlist == 'video'
    
    # Wechsel Master
    assert pm.set_master_playlist('artnet') == True
    assert pm.master_playlist == 'artnet'
    
    # Deaktiviere Master
    assert pm.set_master_playlist(None) == True
    assert pm.master_playlist == None

def test_sync_slaves_to_master():
    pm = PlayerManager()
    pm.set_master_playlist('video')
    
    # Master bei Clip 5
    video_player.current_clip_index = 5
    
    # Initial Sync
    pm.sync_slaves_to_master()
    
def test_slave_stop_when_out_of_range():
    pm = PlayerManager()
    pm.set_master_playlist('video')
    
    # Video: 10 Clips, Art-Net: 5 Clips
    video_player.playlist = [f'clip{i}' for i in range(10)]
    artnet_player.playlist = [f'clip{i}' for i in range(5)]
    
    # Master bei Clip 7 (außerhalb Slave-Range)
    video_player.current_clip_index = 7
    pm.sync_slaves_to_master()
    
    # Slave sollte gestoppt sein
    assert artnet_player.is_playing == False
    
    # Master zurück zu Clip 3 (innerhalb Range)
    video_player.current_clip_index = 3
    pm.sync_slaves_to_master()
    
    # Slave sollte Clip 3 spielen
    assert artnet_player.current_clip_index == 3
    assert artnet_player.is_playing == True
    
    # Slave sollte bei Clip 2 sein (7 % 5 = 2)
    assert artnet_player.current_clip_index == 2
```

### Integration Tests

```python
@pytest.mark.integration
async def test_master_slave_sync_e2e():
    # Setup: Zwei Playlists mit verschiedenen Clips
    # ...
    
    # Aktiviere Master
    response = await client.post('/api/player/video/set_master', 
                                  json={'enabled': True})
    assert response.json()['success'] == True
    
    # Wechsel Clip im Master
    await client.post('/api/player/video/next')
    
    # Warte kurz für Sync
    await asyncio.sleep(0.1)
    
    # Check: Slave sollte gleichen Index haben
    video_status = await client.get('/api/player/video/status')
    artnet_status = await client.get('/api/player/artnet/status')
    
    assert video_status.json()['current_clip_index'] == \
           artnet_status.json()['current_clip_index']
```
### Optimierungen

1. **Event-basiert statt Polling**: Direct callback bei Clip-Wechsel
2. **Async Loading**: Slaves laden Clips parallel, nicht sequenziell
3. **Cache Preloading**: Nächste 2-3 Clips in allen Playlists vorgeladen

### Verhalten bei unterschiedlichen Playlist-Längen

**Simpler Ansatz:** Slave wird gestoppt wenn Master-Index außerhalb der Slave-Range liegt

```
Master (10 Clips):  [0] [1] [2] [3] [4] [5] [6] [7] [8] [9]
Slave (5 Clips):    [0] [1] [2] [3] [4] ⏹️  ⏹️  ⏹️  ⏹️  ⏹️
                    ✅  ✅  ✅  ✅  ✅  ❌  ❌  ❌  ❌  ❌
```

- **Index 0-4:** Slave spielt entsprechenden Clip
- **Index 5-9:** Slave wird gestoppt (schwarzer Screen)
- **Zurück zu 0-4:** Slave startet wieder

**Vorteil:** Einfach, klar, kein Verwirrung durch Loop-Effekte
### Latenz-Ziele

- **Sync-Reaktion:** < 50ms (Zeit von Master-Clip-Wechsel bis Slave-Clip-Start)
- **UI-Update:** < 100ms (Zeit bis UI zeigt neuen Sync-Status)
- **API-Response:** < 20ms (für set_master Endpoint)

### Optimierungen

1. **Event-basiert statt Polling**: Direct callback bei Clip-Wechsel
2. **Async Loading**: Slaves laden Clips parallel, nicht sequenziell
3. **Cache Preloading**: Nächste 2-3 Clips in allen Playlists vorgeladen

---

## 🚧 Implementierungs-Phasen

### Phase 1: Backend Core (4-6h)
- [ ] PlayerManager.set_master_playlist()
- [ ] PlayerManager.sync_slaves_to_master()
- [ ] Player.get_current_clip_index()
- [ ] Player.load_clip_by_index()
- [ ] Event-System: on_clip_changed()

### Phase 2: REST API (1-2h)
- [ ] POST /api/player/{id}/set_master
- [ ] GET /api/player/sync_status
- [ ] Erweitere /api/player/{id}/status

### Phase 3: Frontend UI (2h)
- [ ] Master Toggle Buttons
- [ ] Visual Feedback (Icons, Borders)
- [ ] JavaScript Integration
- [ ] Toast Notifications

### Phase 4: Persistence (1h)
- [ ] Session State: master_playlist
- [ ] Load/Save bei Startup/Shutdown

### Phase 5: Testing & Polish (1-2h)
- [ ] Unit Tests
- [ ] Integration Tests
- [ ] Edge-Case Handling
- [ ] Performance Tuning

---

## 💡 Erweiterungen (Future)

### Multi-Master-Sync
- Mehrere Master-Gruppen (Group A: Video1+Art-Net1, Group B: Video2+Art-Net2)

### Delayed Sync
- Slaves folgen Master mit konfigurierbarem Delay (z.B. 5 Sekunden später)

### Selective Sync
- User wählt welche Slaves synchronisiert werden (Checkboxes)

### MIDI/Timecode Sync
- Synchronisation über MIDI Timecode oder LTC

---

**Erstellt:** 2025-12-05  
**Status:** 🟡 In Planung - Feature-Spec vollständig  
**Geschätzte Implementierungszeit:** 8-14h  
**Priorität:** P1 (Quick Win - Hoher Nutzen)
