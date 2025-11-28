# Performance-Verbesserungen für player.js

## Identifizierte Probleme

### 1. ❌ Event-Handler-Leak bei Playlist-Rendering
**Problem:** Bei jedem `renderPlaylist()` werden neue Event-Handler attached, alte werden nicht entfernt.

**Aktueller Code (ineffizient):**
```javascript
container.querySelectorAll('.playlist-item').forEach((item) => {
    item.addEventListener('click', async (e) => {...});
    item.addEventListener('dragstart', (e) => {...});
    // ... mehrere Handler pro Item
});
```

**Lösung: Event-Delegation verwenden**
```javascript
// Einmal beim Init:
container.addEventListener('click', (e) => {
    const item = e.target.closest('.playlist-item');
    if (!item) return;
    const index = parseInt(item.dataset.index);
    // Handle click...
});
```

**Vorteil:** 
- ✅ Nur 1 Event-Handler statt N
- ✅ Kein Memory-Leak
- ✅ Funktioniert auch für dynamisch hinzugefügte Items

---

### 2. ❌ Wiederholte DOM-Queries

**Problem:** Gleiche Queries werden mehrfach ausgeführt

**Aktueller Code:**
```javascript
document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
```

**Lösung: Caching**
```javascript
// Beim Init cachen:
const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Später verwenden:
tabButtons.forEach(btn => btn.classList.remove('active'));
```

---

### 3. ❌ Array.find() in Hover-Events

**Problem:** Bei jedem Hover O(n) Suche durch availableGenerators

**Aktueller Code:**
```javascript
const generator = availableGenerators.find(g => g.id === fileItem.generator_id);
```

**Lösung: Map für O(1) Lookup**
```javascript
// Beim Laden einmalig erstellen:
const generatorsMap = new Map(availableGenerators.map(g => [g.id, g]));

// Im Hover-Event:
const generator = generatorsMap.get(fileItem.generator_id); // O(1)!
```

---

### 4. ❌ Doppelte setInterval

**Problem:** 2 separate Intervals pollen gleichzeitig

**Aktueller Code:**
```javascript
updateInterval = setInterval(async () => {...}, 2000);
playlistUpdateInterval = setInterval(async () => {...}, 2000);
```

**Lösung: Ein kombinierter Interval**
```javascript
const updateAll = async () => {
    await Promise.all([
        updatePlayerState(),
        updatePlaylistState()
    ]);
};

updateInterval = setInterval(updateAll, 2000);
```

---

### 5. ⚠️ Verschachtelte setTimeout

**Problem:** Timing-Probleme und schwer zu debuggen

**Aktueller Code:**
```javascript
setTimeout(() => {
    setTimeout(() => {
        loadVideoFile(filePath, newItem.id);
    }, 50);
}, 0);
```

**Lösung: requestAnimationFrame + Promise**
```javascript
const waitForNextFrame = () => new Promise(resolve => requestAnimationFrame(resolve));

await waitForNextFrame();
await loadVideoFile(filePath, newItem.id);
```

---

### 6. ❌ querySelectorAll().forEach() statt for-of

**Problem:** forEach erstellt Closures, höherer Memory-Footprint

**Aktueller Code:**
```javascript
container.querySelectorAll('.drop-zone').forEach((zone) => {
    zone.addEventListener('dragover', (e) => {...});
});
```

**Lösung: for-of verwenden**
```javascript
const zones = container.querySelectorAll('.drop-zone');
for (const zone of zones) {
    zone.addEventListener('dragover', (e) => {...});
}
```

---

## Prioritäts-Liste

### Kritisch (Sofort):
1. **Event-Delegation** - Verhindert Memory-Leaks
2. **Generator-Map** - Reduziert CPU-Last bei Hover
3. **Interval-Merge** - Halbiert Polling-Last

### Wichtig (Bald):
4. **DOM-Query-Caching** - Spart wiederholte Queries
5. **setTimeout-Cleanup** - Besseres Timing

### Optional (Nice-to-have):
6. **for-of statt forEach** - Geringerer Memory-Footprint

---

## Geschätzte Performance-Gewinne

| Optimierung | CPU-Einsparung | Memory-Einsparung | Komplexität |
|-------------|----------------|-------------------|-------------|
| Event-Delegation | 15-30% | 40-60% | Mittel |
| Generator-Map | 5-10% | 2-5% | Niedrig |
| Interval-Merge | 10-15% | 5-10% | Niedrig |
| DOM-Caching | 3-8% | 1-3% | Niedrig |
| setTimeout-Cleanup | 2-5% | 1-2% | Mittel |

**Gesamt-Potenzial:** 35-68% CPU, 49-80% Memory

---

## Implementierungs-Reihenfolge

```javascript
// 1. Init-Phase: Caching
const generatorsMap = new Map();
let cachedTabButtons = null;
let cachedTabPanes = null;

// 2. Event-Delegation einrichten
function setupPlaylistEventDelegation(containerId, playlistId) {
    const container = document.getElementById(containerId);
    
    // Single click handler
    container.addEventListener('click', handlePlaylistClick);
    container.addEventListener('mouseenter', handlePlaylistHover, true);
    // ...
}

// 3. Generator-Laden optimieren
async function loadAvailableGenerators() {
    const data = await fetch(...);
    availableGenerators = data.plugins;
    
    // Build map for O(1) lookups
    generatorsMap.clear();
    for (const gen of availableGenerators) {
        generatorsMap.set(gen.id, gen);
    }
}

// 4. Unified Update-Loop
const unifiedUpdate = async () => {
    try {
        const [playerState, playlistState] = await Promise.all([
            fetch('/api/player/state'),
            fetch('/api/player/playlist')
        ]);
        // Process results...
    } catch (err) {
        debug.error('Update failed:', err);
    }
};

updateInterval = setInterval(unifiedUpdate, 2000);
```

---

## Testing-Checkliste

- [ ] Memory-Profiling vor/nach (Chrome DevTools)
- [ ] CPU-Profiling vor/nach
- [ ] Event-Handler-Count überprüfen
- [ ] Hover-Latenz messen
- [ ] Playlist mit 100+ Items testen
- [ ] Drag & Drop funktioniert
- [ ] Click-Events funktionieren
- [ ] Keine Fehler in Console

---

## Risikoabschätzung

**Event-Delegation:** 
- ⚠️ Mittel - Muss alle Event-Handler umschreiben
- Test-Aufwand: Hoch

**Generator-Map:**
- ✅ Niedrig - Einfach, keine Breaking Changes
- Test-Aufwand: Niedrig

**Interval-Merge:**
- ✅ Niedrig - Straightforward
- Test-Aufwand: Mittel

---

## Nächste Schritte

1. ✅ Performance-Analyse dokumentiert
2. ⏳ Entscheidung: Welche Optimierungen implementieren?
3. ⏳ Testing-Plan erstellen
4. ⏳ Schrittweise Implementation
5. ⏳ Vor/Nach-Messungen durchführen
