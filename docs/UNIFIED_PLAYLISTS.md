# Unified Playlist System - Umsetzungsplan

## 📋 Ziel

Vollständige Generalisierung des Player/Playlist-Systems, sodass neue Player nur durch Hinzufügen in `playerConfigs` möglich sind, ohne Code-Änderungen.

**Aktueller Stand:** ~60% generalisiert ✅ | **Ziel:** 100% generalisiert 🎯

---

## 🔍 IST-Analyse

### ✅ Was bereits generalisiert ist

#### 1. `playerConfigs` Struktur (player.js, Zeile 76-115)
```javascript
const playerConfigs = {
    video: {
        id: 'video',
        name: 'Video',
        apiBase: '/api/player/video',
        playlistContainerId: 'videoPlaylist',
        autoplayBtnId: 'videoAutoplayBtn',
        loopBtnId: 'videoLoopBtn',
        files: [],
        currentFile: null,
        autoplay: true,
        loop: true,
        transitionConfig: {...}
    },
    artnet: {
        // ... analog
    }
};
```
**Status:** ✅ Vorhanden, gut strukturiert

#### 2. Generische Kontrollf unktionen
```javascript
async function play(playerId) { const config = playerConfigs[playerId]; ... }
async function pause(playerId) { ... }
async function stop(playerId) { ... }
async function next(playerId) { ... }
async function previous(playerId) { ... }
async function toggleAutoplay(playerId) { ... }
async function toggleLoop(playerId) { ... }
async function updatePlaylist(playerId) { ... }
```
**Status:** ✅ Vollständig generisch implementiert (Zeilen 2132-2315)

#### 3. Generische Playlist-Rendering
```javascript
function renderPlaylist(playlistId) {
    renderPlaylistGeneric(playlistId);
}

function renderPlaylistGeneric(playlistId) {
    const config = playerConfigs[playlistId];
    // ... nutzt config für alle Operationen
}
```
**Status:** ✅ Vollständig generisch (Zeilen 1512-1976)

#### 4. Event-Handler mit Delegation
```javascript
function attachPlaylistItemHandlers(container, playlistId, files, cfg) {
    // Delegated event listeners statt einzelne pro Item
    container.addEventListener('click', clickHandler);
    container.addEventListener('dblclick', dblclickHandler);
    // ...
}
```
**Status:** ✅ Performance-optimiert mit Event-Delegation

---

### ❌ Was noch hardcodiert ist

#### 1. Legacy Playlist-Arrays (player.js, Zeile 1332-1335)
```javascript
let videoFiles = [];
let currentVideo = null;
let artnetFiles = [];
let currentArtnet = null;
```
**Problem:** Separate Arrays statt Verwendung von `playerConfigs[id].files`

**Verwendung:**
- Zeile 193: `const files = playerId === 'video' ? videoFiles : artnetFiles;`
- Zeile 712: `videoFiles.push(newGenerator);`
- Zeile 840: `artnetFiles.push(newGenerator);`
- Zeile 2061-2063: `videoFiles.push({...});`
- Zeile 2391-2393: `artnetFiles.push({...});`

**Betroffen:**
- loadPlaylist() (Zeile 1338+)
- loadVideoPlaylist() (Zeile 1978+)
- loadArtnetPlaylist() (Zeile 1982+)
- Generator-Drops (Zeilen 712, 840)
- Video-Drops (Zeilen 2061, 2391)

---

#### 2. Legacy Current-Item-IDs (player.js, Zeile 132-133)
```javascript
let currentVideoItemId = null;
let currentArtnetItemId = null;
```
**Problem:** Separate Variablen statt `playerConfigs[id].currentItemId`

**Verwendung:**
- Zeile 345-349: `currentVideoItemId = newClipId;`
- Zeile 371-375: `currentArtnetItemId = newClipId;`
- Zeile 1534: `currentVideoItemId = clipId || data.clip_id;`
- Zeile 1553: `currentArtnetItemId = clipId || data.clip_id;`
- Zeile 2013-2014: `currentVideoItemId = clipId || data.clip_id;`
- Zeile 2342-2343: `currentArtnetItemId = clipId || data.clip_id;`

**Betroffen:**
- updateCurrentVideoFromPlayer() (Zeile 333+)
- updateCurrentArtnetFromPlayer() (Zeile 359+)
- loadVideoFile() (Zeile 1997+)
- loadArtnetFile() (Zeile 2328+)

---

#### 3. Spezifische Lade-Funktionen
```javascript
window.loadVideoFile = async function(videoPath, clipId = null) { ... }
window.loadVideo = async function(videoPath) { ... }
window.loadArtnetFile = async function(videoPath, clipId = null) { ... }
window.loadArtnetVideo = async function(videoPath) { ... }
```
**Problem:** Separate Funktionen statt einer generischen `loadFile(playerId, path, clipId)`

**Verwendung:**
- 20+ Aufrufe in player.js (siehe grep_search Ergebnisse)
- Aufrufe in:
  - Generator-Drops
  - File-Drops
  - Playlist-Clicks
  - Auto-Load-Logik
  - Autoplay-Start

**Betroffen:**
- loadVideoFile() (Zeile 1997-2038)
- loadVideo() (Zeile 2040-2073)
- loadArtnetFile() (Zeile 2328-2366)
- loadArtnetVideo() (Zeile 2369-2404)

---

#### 4. Legacy onclick-Handler (player.js, Zeile 2212-2217)
```javascript
window.playVideo = async function() { await play('video'); };
window.pauseVideo = async function() { await pause('video'); };
window.stopVideo = async function() { await stop('video'); };
window.nextVideo = async function() { await next('video'); };
window.previousVideo = async function() { await previous('video'); };
// + analog für Art-Net
```
**Problem:** Wrapper-Funktionen statt direkter generischer Aufrufe

**Status:** Werden NICHT in HTML verwendet (grep fand 0 Matches), können entfernt werden

---

#### 5. Legacy Autoplay/Loop-Variablen (player.js, Zeile 120-123)
```javascript
let videoAutoplay = true;
let videoLoop = true;
let artnetAutoplay = true;
let artnetLoop = true;
```
**Problem:** Separate Variablen statt `playerConfigs[id].autoplay/loop`

**Verwendung:**
- Zeile 2235-2236: `if (playerId === 'video') videoAutoplay = config.autoplay;`
- Zeile 2278-2279: `if (playerId === 'video') videoLoop = config.loop;`

**Betroffen:**
- toggleAutoplay() (Zeile 2219+)
- toggleLoop() (Zeile 2262+)

---

#### 6. Spezifische Playlist-Load-Wrapper (player.js)
```javascript
async function loadVideoPlaylist() {
    await loadPlaylist('video');
}

async function loadArtnetPlaylist() {
    await loadPlaylist('artnet');
}
```
**Problem:** Unnötige Wrapper, `loadPlaylist(id)` ist schon generisch

**Verwendung:**
- Zeile 186: `await loadVideoPlaylist();`
- Zeile 187: `await loadArtnetPlaylist();`
- Zeile 2076: `await loadVideoPlaylist();`
- Zeile 2406: `await loadArtnetPlaylist();`

---

#### 7. Spezifische Update-Funktionen
```javascript
async function updateCurrentVideoFromPlayer() { ... }
async function updateCurrentArtnetFromPlayer() { ... }
```
**Problem:** Zwei separate Funktionen statt einer `updateCurrentFromPlayer(playerId)`

**Verwendung:**
- Zeile 265: `await updateCurrentVideoFromPlayer();`
- Zeile 266: `await updateCurrentArtnetFromPlayer();`

---

## 🎯 Umsetzungsplan

### Phase 1: Legacy-Variablen zu playerConfigs migrieren (~2-3h)

#### 1.1 Playlist-Arrays konsolidieren (1h)
**Ziel:** Alle Zugriffe auf `videoFiles`/`artnetFiles` durch `playerConfigs[id].files` ersetzen

**Schritte:**
1. Alle `videoFiles` durch `playerConfigs.video.files` ersetzen
2. Alle `artnetFiles` durch `playerConfigs.artnet.files` ersetzen
3. Legacy-Variablen-Deklarationen entfernen (Zeile 1332-1335)

**Betroffene Stellen:** (via grep_search identifiziert)
- `loadPlaylist()` - Zeile 1338+
- `renderPlaylistGeneric()` - Zeile 1512+
- Generator-Drops - Zeilen 712, 840
- Video-Drops - Zeilen 2061, 2391
- `loadVideo()` / `loadArtnetVideo()` - Zeilen 2040+, 2369+
- `removeFromVideoPlaylist()` - Zeile 2079+
- `removeFromArtnetPlaylist()` - Zeile 2407+

**Beispiel:**
```javascript
// VORHER
videoFiles.push(newGenerator);

// NACHHER
playerConfigs.video.files.push(newGenerator);
```

---

#### 1.2 Current-Item-IDs konsolidieren (30min)
**Ziel:** `currentVideoItemId`/`currentArtnetItemId` durch `playerConfigs[id].currentItemId` ersetzen

**Schritte:**
1. `currentItemId` zu `playerConfigs` Schema hinzufügen
2. Alle Zugriffe auf `currentVideoItemId` durch `playerConfigs.video.currentItemId` ersetzen
3. Alle Zugriffe auf `currentArtnetItemId` durch `playerConfigs.artnet.currentItemId` ersetzen
4. Legacy-Variablen entfernen (Zeile 132-133)

**Betroffene Stellen:**
- `updateCurrentVideoFromPlayer()` - Zeile 333+
- `updateCurrentArtnetFromPlayer()` - Zeile 359+
- `loadVideoFile()` - Zeile 1997+
- `loadArtnetFile()` - Zeile 2328+
- `renderPlaylistGeneric()` (für active-Border) - Zeile 1512+

**Beispiel:**
```javascript
// VORHER
currentVideoItemId = clipId;

// NACHHER
playerConfigs.video.currentItemId = clipId;
```

---

#### 1.3 Autoplay/Loop-Variablen entfernen (30min)
**Ziel:** `videoAutoplay`/`videoLoop` etc. entfernen, nur noch `playerConfigs` nutzen

**Schritte:**
1. Sync-Code in `toggleAutoplay()` / `toggleLoop()` entfernen (Zeilen 2235-2236, 2278-2279)
2. Legacy-Variablen-Deklarationen entfernen (Zeile 120-123)

**Beispiel:**
```javascript
// VORHER
if (playerId === 'video') videoAutoplay = config.autoplay;

// NACHHER
// Komplett entfernen - config.autoplay ist Source of Truth
```

---

### Phase 2: Generische Lade-Funktionen (~3-4h)

#### 2.1 Generische loadFile() Funktion erstellen (1-2h)
**Ziel:** Eine universelle Funktion statt 4 separate

**Implementierung:**
```javascript
/**
 * Lädt Datei für beliebigen Player (generisch).
 * @param {string} playerId - 'video' oder 'artnet'
 * @param {string} filePath - Pfad zur Datei
 * @param {string|null} clipId - UUID (optional, wird generiert falls null)
 * @param {boolean} addToPlaylist - Wenn true, zu Playlist hinzufügen
 */
window.loadFile = async function(playerId, filePath, clipId = null, addToPlaylist = false) {
    const config = playerConfigs[playerId];
    if (!config) {
        console.error(`❌ Unknown player: ${playerId}`);
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/clip/load`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                path: filePath,
                clip_id: clipId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            config.currentFile = filePath.replace(/^[\\\/]+/, '');
            
            if (addToPlaylist) {
                const filename = filePath.split('/').pop();
                const folder = filePath.includes('/') ? filePath.split('/')[0] : 'root';
                config.files.push({
                    filename: filename,
                    path: filePath,
                    folder: folder,
                    name: filename,
                    id: clipId || crypto.randomUUID(),
                    type: 'video'
                });
            }
            
            renderPlaylist(playerId);
            
            // Update IDs
            selectedClipId = clipId || data.clip_id;
            config.currentItemId = clipId || data.clip_id;
            selectedClipPath = filePath;
            selectedClipPlayerType = playerId;
            
            // Clear generator state
            window.currentGeneratorId = null;
            window.currentGeneratorParams = null;
            window.currentGeneratorMeta = null;
            
            debug.log(`✅ ${config.name} loaded with Clip-ID:`, selectedClipId);
            await refreshClipEffects();
        } else {
            showToast(`Failed to load ${config.name}: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error(`❌ Error loading ${config.name}:`, error);
        showToast(`Error loading ${config.name}`, 'error');
    }
};
```

---

#### 2.2 Alle loadVideoFile/loadArtnetFile ersetzen (1-2h)
**Ziel:** Alle 20+ Aufrufe durch `loadFile()` ersetzen

**Migration:**
```javascript
// VORHER
await loadVideoFile(item.path, item.id);
await loadArtnetFile(item.path, item.id);

// NACHHER
await loadFile('video', item.path, item.id);
await loadFile('artnet', item.path, item.id);
```

**Betroffene Stellen:** (via grep_search)
- Generator-Load-Callbacks (Zeilen 759, 887)
- Playlist-Doppelklick-Handler (Zeilen 1528, 1547)
- Drop-Handler (Zeilen 1663, 1665, 1938, 1940)
- Next-Clip-Load (Zeilen 2105, 2433)
- Autoplay-Start (Zeilen 2252, 2253)

---

#### 2.3 Legacy-Funktionen entfernen (30min)
**Ziel:** `loadVideoFile`, `loadVideo`, `loadArtnetFile`, `loadArtnetVideo` löschen

**Schritte:**
1. Sicherstellen alle Aufrufe migriert sind
2. Funktionen löschen (Zeilen 1997-2073, 2328-2404)
3. Legacy-onclick-Handler löschen (Zeilen 2212-2217)

---

### Phase 3: Update-Funktionen generalisieren (~1-2h)

#### 3.1 Generische updateCurrentFromPlayer() (30min)
**Implementierung:**
```javascript
async function updateCurrentFromPlayer(playerId) {
    const config = playerConfigs[playerId];
    if (!config) return;
    
    try {
        const response = await fetch(`${API_BASE}${config.apiBase}/status`);
        const data = await response.json();
        
        if (data.success && data.video) {
            const newVideo = data.video.replace(/^[\\\/]+/, '');
            const newClipId = data.clip_id;
            const normalizedCurrent = config.currentFile ? 
                config.currentFile.replace(/^[\\\/]+/, '') : null;
            
            const clipIdChanged = config.currentItemId !== newClipId;
            
            if (newVideo !== normalizedCurrent || clipIdChanged) {
                config.currentFile = newVideo;
                config.currentItemId = newClipId;
                renderPlaylist(playerId);
                debug.log(`🔄 ${config.name} updated:`, newVideo, 'Clip-ID:', newClipId);
            }
        }
    } catch (error) {
        // Silent fail
    }
}
```

---

#### 3.2 Update-Loop anpassen (30min)
```javascript
// VORHER
await updateCurrentVideoFromPlayer();
await updateCurrentArtnetFromPlayer();

// NACHHER
await updateCurrentFromPlayer('video');
await updateCurrentFromPlayer('artnet');
```

---

#### 3.3 Legacy-Funktionen löschen (10min)
Löschen:
- `updateCurrentVideoFromPlayer()` (Zeile 333+)
- `updateCurrentArtnetFromPlayer()` (Zeile 359+)

---

### Phase 4: Playlist-Wrapper vereinfachen (~30min)

#### 4.1 Direkte loadPlaylist() Aufrufe (20min)
```javascript
// VORHER
await loadVideoPlaylist();
await loadArtnetPlaylist();

// NACHHER
await loadPlaylist('video');
await loadPlaylist('artnet');
```

**Betroffene Stellen:**
- Init (Zeilen 186-187)
- refreshVideoPlaylist (Zeile 2076)
- refreshArtnetPlaylist (Zeile 2406)

---

#### 4.2 Wrapper-Funktionen löschen (10min)
Löschen:
- `loadVideoPlaylist()` (Zeile 1978+)
- `loadArtnetPlaylist()` (Zeile 1982+)
- `renderVideoPlaylist()` (Zeile 1986+)
- `renderArtnetPlaylist()` (Zeile 1990+)

---

### Phase 5: HTML/UI dynamisch generieren (~2-3h)

**Hinweis:** HTML verwendet KEINE hardcodierten onclick-Handler mehr (grep fand 0 Matches). 
Buttons nutzen bereits generische Event-Handler oder sind via JavaScript dynamisch.

#### 5.1 Dynamische Player-Container (Optional, 1h)
Falls neue Player hinzugefügt werden sollen, HTML-Container dynamisch aus `playerConfigs` generieren:

```javascript
function renderPlayerContainers() {
    const container = document.getElementById('playersContainer');
    
    Object.values(playerConfigs).forEach(config => {
        const html = `
            <div class="player-panel">
                <h3>${config.name}</h3>
                <div id="${config.playlistContainerId}"></div>
                <div class="player-controls">
                    <button onclick="play('${config.id}')">Play</button>
                    <button onclick="pause('${config.id}')">Pause</button>
                    <!-- etc. -->
                </div>
            </div>
        `;
        container.innerHTML += html;
    });
}
```

**Status:** Aktuell NICHT notwendig - HTML ist bereits generisch genug

---

## 📊 Aufwands-Zusammenfassung

| Phase | Aufwand | Beschreibung |
|-------|---------|--------------|
| **Phase 1** | 2-3h | Legacy-Variablen migrieren |
| **Phase 2** | 3-4h | Generische Lade-Funktionen |
| **Phase 3** | 1-2h | Update-Funktionen generalisieren |
| **Phase 4** | 30min | Playlist-Wrapper vereinfachen |
| **Phase 5** | Optional | HTML dynamisch (nicht notwendig) |
| **GESAMT** | **~7-10h** | **Vollständige Generalisierung** |

---

## ✅ Checkliste

### Phase 1: Legacy-Variablen
- [ ] `videoFiles` → `playerConfigs.video.files` (alle Stellen)
- [ ] `artnetFiles` → `playerConfigs.artnet.files` (alle Stellen)
- [ ] Legacy-Arrays löschen (Zeile 1332-1335)
- [ ] `currentVideoItemId` → `playerConfigs.video.currentItemId`
- [ ] `currentArtnetItemId` → `playerConfigs.artnet.currentItemId`
- [ ] Legacy-IDs löschen (Zeile 132-133)
- [ ] `videoAutoplay`/`videoLoop` etc. entfernen (Zeilen 120-123, 2235, 2278)

### Phase 2: Lade-Funktionen
- [ ] `window.loadFile(playerId, path, clipId, addToPlaylist)` implementieren
- [ ] Alle `loadVideoFile()` Aufrufe ersetzen (20+ Stellen)
- [ ] Alle `loadArtnetFile()` Aufrufe ersetzen (20+ Stellen)
- [ ] Legacy-Funktionen löschen (Zeilen 1997-2073, 2328-2404)
- [ ] Legacy-onclick-Handler löschen (Zeilen 2212-2217)

### Phase 3: Update-Funktionen
- [ ] `updateCurrentFromPlayer(playerId)` implementieren
- [ ] Update-Loop anpassen (Zeile 265-266)
- [ ] Legacy-Funktionen löschen (Zeilen 333+, 359+)

### Phase 4: Playlist-Wrapper
- [ ] Direkte `loadPlaylist(id)` Aufrufe (4 Stellen)
- [ ] Wrapper-Funktionen löschen (Zeilen 1978+, 1982+, 1986+, 1990+)

### Phase 5: Testing
- [ ] Video-Player Playlist laden/abspielen
- [ ] Art-Net-Player Playlist laden/abspielen
- [ ] Generator-Drops funktionieren
- [ ] Video-Drops funktionieren
- [ ] Autoplay/Loop funktioniert
- [ ] Clip-Wechsel (next/previous)
- [ ] Active-Border funktioniert
- [ ] Effekte laden korrekt

---

## 🎯 Ergebnis

Nach Abschluss aller Phasen:

### ✅ Neuer Player hinzufügen - SO EINFACH:

```javascript
// 1. Config hinzufügen
const playerConfigs = {
    video: { ... },
    artnet: { ... },
    // NEU: Einfach hier hinzufügen!
    dmx: {
        id: 'dmx',
        name: 'DMX',
        apiBase: '/api/player/dmx',
        playlistContainerId: 'dmxPlaylist',
        autoplayBtnId: 'dmxAutoplayBtn',
        loopBtnId: 'dmxLoopBtn',
        files: [],
        currentFile: null,
        currentItemId: null,
        autoplay: true,
        loop: true,
        transitionConfig: {
            enabled: false,
            effect: 'fade',
            duration: 1.0,
            easing: 'ease_in_out'
        }
    }
};

// 2. HTML Container hinzufügen (player-panel Div)
// 3. FERTIG! Alle generischen Funktionen funktionieren automatisch:
//    - play('dmx')
//    - pause('dmx')
//    - loadFile('dmx', path)
//    - renderPlaylist('dmx')
//    - toggleAutoplay('dmx')
//    - etc.
```

### 📈 Code-Qualität nach Refactoring

**Vorher:**
- 4 separate Lade-Funktionen
- 2 separate Update-Funktionen
- 4 separate Wrapper-Funktionen
- 6 Legacy-Variablen
- **Neuer Player:** ~500 Zeilen Code-Duplikation

**Nachher:**
- 1 generische Lade-Funktion
- 1 generische Update-Funktion
- 0 Wrapper-Funktionen
- 0 Legacy-Variablen
- **Neuer Player:** ~20 Zeilen Config + HTML

**Reduktion:** ~95% weniger Code für neue Player! 🚀

---

## 🔄 Migrations-Reihenfolge

**Empfohlen:** Phase für Phase, mit Testing nach jeder Phase

1. **Phase 1.1** → Test → Commit
2. **Phase 1.2** → Test → Commit
3. **Phase 1.3** → Test → Commit
4. **Phase 2.1-2.2** → Test → Commit
5. **Phase 2.3** → Test → Commit
6. **Phase 3** → Test → Commit
7. **Phase 4** → Test → Commit

**Gesamt-Zeit:** 7-10h (mit Testing)

---

---

## 🔧 Backend-Analyse

### ✅ Backend ist bereits vollständig generalisiert!

Das Backend verwendet bereits ein **generisches URL-Pattern**:

```python
@app.route('/api/player/<player_id>/clip/load', methods=['POST'])
@app.route('/api/player/<player_id>/status', methods=['GET'])
@app.route('/api/player/<player_id>/play', methods=['POST'])
@app.route('/api/player/<player_id>/pause', methods=['POST'])
# etc.
```

**PlayerManager mit Unified Access:**
```python
class PlayerManager:
    def __init__(self):
        self.players = {
            'video': self.video_player,
            'artnet': self.artnet_player
        }
    
    def get_player(self, player_id: str):
        """Get player by ID - FULLY GENERIC!"""
        return self.players.get(player_id)
```

### ❌ Einzige Ausnahme: Default Effects (1 Stelle!)

**Datei:** `src/modules/default_effects.py`, Zeile 115-118

```python
# ❌ HARDCODED player_type checks
if player_type == 'video':
    effects = self.get_video_effects()
    player = player_manager.get_player('video')
elif player_type == 'artnet':
    effects = self.get_artnet_effects()
    player = player_manager.get_player('artnet')
```

**Problem:** Separate `get_video_effects()` / `get_artnet_effects()` Methoden

**Lösung:** Eine generische Methode:
```python
def get_effects(self, player_type: str) -> List[Dict[str, Any]]:
    """Get default effects for any player type."""
    return deepcopy(self.effects_config.get(player_type, []))

def apply_to_player(self, player_manager, player_type: str) -> int:
    """Apply default effects to any player (GENERIC)."""
    effects = self.get_effects(player_type)
    player = player_manager.get_player(player_type)
    
    if not player:
        logger.warning(f"⚠️ Player '{player_type}' not available")
        return 0
    # ... rest bleibt generisch
```

**Aufwand:** ~15 Minuten

---

## 📊 Backend vs. Frontend Vergleich

| Aspekt | Backend | Frontend |
|--------|---------|----------|
| **URL-Pattern** | ✅ Generisch (`/api/player/<player_id>/...`) | ✅ Generisch (nutzt `apiBase` aus config) |
| **Player Access** | ✅ `player_manager.get_player(player_id)` | ❌ `videoFiles`, `artnetFiles`, etc. |
| **Load Functions** | ✅ Eine Route für alle Player | ❌ `loadVideoFile()`, `loadArtnetFile()` |
| **Status Updates** | ✅ Generisch über `player_id` | ❌ `updateCurrentVideoFromPlayer()`, etc. |
| **Playlist Management** | ✅ Generisch | ❌ Separate Arrays |
| **Default Effects** | ⚠️ 1 hardcoded Stelle (15min Fix) | N/A |
| **GESAMT** | **~99% generisch** 🎉 | **~60% generisch** |

### 🎯 Fazit

**Backend:** Fast perfekt! Nur 1 kleine Stelle in `default_effects.py` (15min Fix).

**Frontend:** Hier liegt die Hauptarbeit (~7-10h).

Das Backend ist durch die **Unified Player API** bereits so designed, dass neue Player automatisch funktionieren! 🚀

---

**Erstellt:** 2025-12-05  
**Status:** 🟡 Analyse abgeschlossen - Bereit für Umsetzung  
**Nächster Schritt:** Phase 1.1 starten (videoFiles/artnetFiles konsolidieren)  
**Backend-Fix:** Optional - `default_effects.py` generalisieren (~15min)
