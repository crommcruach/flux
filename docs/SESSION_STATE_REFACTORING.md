# Session State Refactoring Plan

## Current State Analysis

### 1. **player.html / session-loader.js** ✅ BEST IMPLEMENTATION
**Status:** Vollständig und gut strukturiert

**Verwendung:**
- `<script src="js/session-loader.js" defer></script>` in player.html
- Erstellt globales `window.sessionStateLoader` Objekt
- Automatisches Laden beim DOMContentLoaded

**API:**
```javascript
// Load state (singleton pattern)
await window.sessionStateLoader.load()

// Reload after changes
await window.sessionStateLoader.reload()

// Get specific section
const editor = window.sessionStateLoader.get('editor')
const players = window.sessionStateLoader.get('players')

// Register callback for when loaded
window.sessionStateLoader.onStateLoaded((state) => {
    // Initialize UI with state
})
```

**Features:**
- ✅ Singleton Pattern
- ✅ Debouncing (verhindert mehrfaches Laden)
- ✅ Listener System (onStateLoaded callbacks)
- ✅ Error Handling
- ✅ Loading Status
- ✅ Performance Tracking
- ✅ Nur GET (liest Session State)

**Backend Endpoints:**
- `GET /api/session/state` - Liest kompletten State

---

### 2. **editor.html / editor.js** ⚠️ CUSTOM IMPLEMENTATION
**Status:** Eigene Implementierung, inkonsistent

**Verwendung:**
- Keine session-loader.js Einbindung
- Eigene Funktionen: `saveEditorStateToSession()`, `loadEditorStateFromSession()`
- Manueller Aufruf bei window.load

**API:**
```javascript
// Save (with debouncing)
saveEditorStateToSession()  // Called after every change

// Load (on page load)
loadEditorStateFromSession()  // Called in window.addEventListener('load')
```

**Probleme:**
- ❌ Duplizierter Code (eigene Fetch-Logik)
- ❌ **FEHLER:** Verwendet POST auf `/api/session/state` statt spezialisiertem Endpoint
- ❌ Fetch GET + Merge + POST Pattern (ineffizient)
- ❌ Kein Listener System
- ❌ Kein Singleton Pattern
- ❌ AutoSave Badge Logik vermischt mit State Management

**Backend Endpoints:**
- `GET /api/session/state` - Liest kompletten State
- `POST /api/session/state` - **FALSCH!** Sollte `/api/session/editor` sein
- `POST /api/session/editor` - Existiert bereits, wird aber nicht genutzt!

**Aktueller Code-Flow (FALSCH):**
```javascript
// 1. GET full state
const getResponse = await fetch('/api/session/state');
const {state} = await getResponse.json();

// 2. Modify editor section
state.editor = { ... };

// 3. POST full state back (überschreibt alles!)
const response = await fetch('/api/session/state', {
    method: 'POST',
    body: JSON.stringify(state)  // DANGEROUS!
});
```

---

### 3. **output-settings.html / output-settings.js** ⚠️ CUSTOM IMPLEMENTATION
**Status:** Eigene Implementierung, inkonsistent

**Verwendung:**
- Keine session-loader.js Einbindung
- Eigene Methoden: `app.saveToBackend()`, `app.loadFromBackend()`
- Manueller Aufruf in `app.init()`

**API:**
```javascript
// Save (with debouncing)
app.saveToBackend()  // Called after every change

// Load (in init)
await app.loadFromBackend()
```

**Probleme:**
- ❌ Duplizierter Code (eigene Fetch-Logik)
- ❌ Verwendet spezielle Slice-Endpoints (nicht session state)
- ❌ Kein Listener System
- ❌ Backend Status UI vermischt mit State Management
- ✅ Aber: Eigene Endpoints sind korrekt (slice-spezifisch)

**Backend Endpoints:**
- `POST /api/slices/import` - Speichert Slices
- `GET /api/slices/export` - Lädt Slices

---

## Problem Summary

### Inkonsistenzen:
1. **Drei verschiedene Implementierungen** für dasselbe Problem
2. **Editor.js verwendet falschen Endpoint** - POST auf `/api/session/state` statt `/api/session/editor`
3. **Kein geteilter Code** - Jede Seite reimplementiert Session State Handling
4. **Keine einheitliche API** - Unterschiedliche Funktionsnamen und Patterns

### Risiken:
1. **Daten-Korruption:** Editor überschreibt kompletten State beim Speichern
2. **Wartbarkeit:** Änderungen müssen an 3 Stellen gemacht werden
3. **Bugs:** Verschiedene Error Handling Logiken
4. **Performance:** Mehrfache unnötige Fetches

---

## Refactoring Plan

### Phase 1: Unified SessionStateManager (Neue zentrale API)

**Erstelle:** `frontend/js/session-state-manager.js`

```javascript
/**
 * Unified Session State Manager
 * Handles all session state operations (read & write)
 */
class SessionStateManager {
    constructor() {
        this.state = null;
        this.loaded = false;
        this.loading = false;
        this.listeners = [];
    }

    // ========================================
    // LOADING (from session-loader.js)
    // ========================================
    
    async load() {
        if (this.loaded || this.loading) return this.state;
        return this._fetchState();
    }

    async reload() {
        this.loaded = false;
        return this._fetchState();
    }

    async _fetchState() {
        this.loading = true;
        try {
            const response = await fetch('/api/session/state');
            if (response.ok) {
                const data = await response.json();
                this.state = data.state || {};
                this.loaded = true;
                this.notifyListeners();
                return this.state;
            }
        } catch (error) {
            console.error('Failed to load session state:', error);
        } finally {
            this.loading = false;
        }
    }

    // ========================================
    // SAVING (specialized endpoints)
    // ========================================
    
    async saveEditor(editorState, options = {}) {
        return this._saveSection('editor', editorState, '/api/session/editor', options);
    }

    async saveAudioAnalyzer(audioState, options = {}) {
        return this._saveSection('audio_analyzer', audioState, '/api/session/audio', options);
    }

    // Generic save for any section
    async _saveSection(sectionName, data, endpoint, options = {}) {
        const { debounce = 1000, onStatusChange = null } = options;

        // Clear existing debounce
        if (this._saveTimeouts?.[sectionName]) {
            clearTimeout(this._saveTimeouts[sectionName]);
        }

        if (!this._saveTimeouts) this._saveTimeouts = {};

        return new Promise((resolve, reject) => {
            this._saveTimeouts[sectionName] = setTimeout(async () => {
                try {
                    if (onStatusChange) onStatusChange('saving');

                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(data)
                    });

                    const result = await response.json();

                    if (result.success) {
                        // Update local cache
                        if (this.state) {
                            this.state[sectionName] = data;
                        }
                        if (onStatusChange) onStatusChange('saved');
                        resolve(result);
                    } else {
                        if (onStatusChange) onStatusChange('error');
                        reject(new Error(result.error));
                    }
                } catch (error) {
                    if (onStatusChange) onStatusChange('error');
                    reject(error);
                }
            }, debounce);
        });
    }

    // ========================================
    // GETTERS (from session-loader.js)
    // ========================================
    
    get(path) {
        if (!this.loaded) {
            console.warn('Attempting to access state before loaded');
            return null;
        }

        const keys = path.split('.');
        let value = this.state;
        
        for (const key of keys) {
            if (value && typeof value === 'object' && key in value) {
                value = value[key];
            } else {
                return null;
            }
        }
        
        return value;
    }

    // ========================================
    // LISTENER SYSTEM
    // ========================================
    
    onStateLoaded(callback) {
        if (this.loaded) {
            callback(this.state);
        } else {
            this.listeners.push(callback);
        }
    }

    notifyListeners() {
        this.listeners.forEach(cb => {
            try { cb(this.state); }
            catch (e) { console.error('Listener error:', e); }
        });
        this.listeners = [];
    }
}

// Global singleton
window.sessionStateManager = new SessionStateManager();

// Auto-load on DOMContentLoaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.sessionStateManager.load();
    });
} else {
    window.sessionStateManager.load();
}
```

---

### Phase 2: Migrate editor.js

**Änderungen in `editor.html`:**
```html
<!-- NACH session-state-manager.js (ersetzt alte Lösung) -->
<script src="js/session-state-manager.js" defer></script>
```

**Änderungen in `editor.js`:**

**ALT (LÖSCHEN):**
```javascript
async function saveEditorStateToSession() {
    // ... 70 Zeilen Code
    const getResponse = await fetch('/api/session/state');  // ❌ FALSCH
    const {state} = await getResponse.json();
    state.editor = { ... };
    const response = await fetch('/api/session/state', {    // ❌ FALSCH
        method: 'POST',
        body: JSON.stringify(state)
    });
}

async function loadEditorStateFromSession() {
    // ... 40 Zeilen Code
    const response = await fetch('/api/session/state');
    const result = await response.json();
    const state = result.state.editor;
    // ... restore logic
}
```

**NEU (VERWENDEN):**
```javascript
async function saveEditorStateToSession() {
    const editorState = {
        version: '2.0',
        canvas: {
            width: actualCanvasWidth,
            height: actualCanvasHeight
        },
        backgroundImagePath: backgroundImagePath || null,
        settings: {
            snapToGrid, snapToObjects, allowOutOfBounds,
            gridSize, showGrid, showConnectionLines
        },
        shapes: shapes.map(s => ({ /* ... */ })),
        groups: groups,
        savedAt: new Date().toISOString()
    };

    try {
        await window.sessionStateManager.saveEditor(editorState, {
            debounce: AUTO_SAVE_DELAY,
            onStatusChange: updateAutoSaveStatus
        });
    } catch (error) {
        console.error('Save failed:', error);
        updateAutoSaveStatus('error');
    }
}

async function loadEditorStateFromSession() {
    // Wait for state to be loaded
    await window.sessionStateManager.load();
    
    const state = window.sessionStateManager.get('editor');
    if (!state) {
        console.log('No editor state found');
        return;
    }

    // Restore background
    if (state.backgroundImagePath) {
        backgroundImagePath = state.backgroundImagePath;
        const img = new Image();
        img.onload = () => {
            backgroundImage = img;
            markForRedraw();
        };
        img.src = '/' + state.backgroundImagePath;
    }

    // Restore settings
    if (state.settings) {
        snapToGrid = state.settings.snapToGrid ?? true;
        snapToObjects = state.settings.snapToObjects ?? true;
        // ... etc
    }

    // Restore shapes
    if (state.shapes) {
        shapes = state.shapes;
        updateObjectList();
        markForRedraw();
    }

    // Restore groups
    if (state.groups) {
        groups = state.groups;
    }

    console.log('✅ Editor state loaded');
}
```

---

### Phase 3: Migrate player.html

**Änderungen in `player.html`:**
```html
<!-- ALT: -->
<script src="js/session-loader.js" defer></script>

<!-- NEU: -->
<script src="js/session-state-manager.js" defer></script>
```

**Änderungen in `player.js`:**
```javascript
// ALT:
window.sessionStateLoader.reload()

// NEU:
window.sessionStateManager.reload()

// ALT:
window.sessionStateLoader.get('players.video')

// NEU:
window.sessionStateManager.get('players.video')
```

---

### Phase 4: Migrate output-settings.html (Optional)

Da Output Settings bereits eigene Slice-spezifische Endpoints verwendet (`/api/slices/import`, `/api/slices/export`), ist hier weniger Refactoring nötig.

**Optional:** Erweitere SessionStateManager um Slice-Support:
```javascript
async saveSlices(slicesData, options = {}) {
    // Use existing /api/slices/import endpoint
    return this._saveSection('slices', slicesData, '/api/slices/import', options);
}
```

---

## Backend Changes Needed

### Verify these endpoints exist:

1. ✅ `GET /api/session/state` - Returns complete session state
2. ✅ `POST /api/session/editor` - Updates only editor section
3. ⚠️ `POST /api/session/audio` - May need to be added for audio_analyzer
4. ✅ `POST /api/slices/import` - Slices (already exists)
5. ✅ `GET /api/slices/export` - Slices (already exists)

### Remove/deprecate:
- ❌ `POST /api/session/state` - Should NOT exist (encourages bad pattern)

---

## Implementation Steps

### Step 1: Create Unified Manager ✅
- [ ] Erstelle `frontend/js/session-state-manager.js`
- [ ] Kopiere Load-Logik von `session-loader.js`
- [ ] Füge Save-Logik hinzu (mit spezialisierten Endpoints)
- [ ] Teste mit player.html

### Step 2: Migrate Editor ✅
- [ ] Ändere `editor.html` - lade `session-state-manager.js`
- [ ] Ersetze `saveEditorStateToSession()` - nutze `.saveEditor()`
- [ ] Ersetze `loadEditorStateFromSession()` - nutze `.load()` + `.get('editor')`
- [ ] Entferne alte POST zu `/api/session/state`
- [ ] Teste Editor Auto-Save + Restore

### Step 3: Migrate Player ✅
- [ ] Ändere `player.html` - lade `session-state-manager.js` statt `session-loader.js`
- [ ] Ersetze alle `sessionStateLoader` → `sessionStateManager`
- [ ] Verifiziere Playlist Load/Save funktioniert
- [ ] Lösche `session-loader.js` (deprecated)

### Step 4: Cleanup Backend ✅
- [ ] Entferne `POST /api/session/state` Route aus `api_session.py`
- [ ] Verifiziere `/api/session/editor` Endpoint existiert
- [ ] Update API Documentation

---

## Benefits After Refactoring

### Code Quality:
- ✅ **Single source of truth** - Eine Implementierung für alle Seiten
- ✅ **Consistent API** - Gleiche Funktionen überall
- ✅ **Better error handling** - Zentrale Error Logik
- ✅ **Less code** - ~200 Zeilen duplizierter Code entfernt

### Sicherheit:
- ✅ **No data corruption** - Kein überschreiben des kompletten States
- ✅ **Specialized endpoints** - Jede Sektion hat eigenen Endpoint
- ✅ **Atomic updates** - Nur einzelne Sektionen updaten

### Performance:
- ✅ **Debouncing** - Zentrale Debounce-Logik
- ✅ **Caching** - State wird gecacht nach Load
- ✅ **Lazy loading** - Nur laden wenn nötig

### Wartbarkeit:
- ✅ **Einfache Updates** - Nur eine Datei zu ändern
- ✅ **Testbar** - Zentrale Logik leichter zu testen
- ✅ **Dokumentiert** - Klare API Dokumentation

---

## Testing Checklist

Nach jedem Migrations-Schritt:

### Editor Tests:
- [ ] Shapes erstellen und speichern
- [ ] Page Reload - Shapes werden restored
- [ ] Background Upload + Restore
- [ ] Settings ändern + Restore
- [ ] Auto-Save Badge funktioniert

### Player Tests:
- [ ] Playlist laden/speichern
- [ ] Snapshot erstellen
- [ ] Sequencer Mode speichern
- [ ] Audio Analyzer State speichern

### Output Settings Tests:
- [ ] Slices erstellen/bearbeiten
- [ ] Page Reload - Slices werden restored
- [ ] Output assignments speichern

---

## Migration Timeline

**Estimated:** 2-3 Stunden

1. **30 min** - Erstelle `session-state-manager.js`
2. **45 min** - Migrate editor.js + teste
3. **30 min** - Migrate player.js + teste
4. **30 min** - Backend cleanup + verify
5. **15 min** - Final testing + documentation

---

## Breaking Changes

### Für Editor:
- `saveEditorStateToSession()` intern geändert (API gleich)
- `loadEditorStateFromSession()` intern geändert (API gleich)
- **Keine Breaking Changes für User** - Funktionen heißen gleich

### Für Player:
- `window.sessionStateLoader` → `window.sessionStateManager`
- **Breaking Change:** Code muss angepasst werden

### Für Output Settings:
- Keine Breaking Changes (behält eigene Endpoints)

---

## Rollback Plan

Falls Probleme auftreten:

1. **Editor:** Git revert - alte `saveEditorStateToSession()` wiederherstellen
2. **Player:** `session-loader.js` zurück einbinden
3. **Backend:** `POST /api/session/state` Route wieder aktivieren (temporär)

---

## Conclusion

Aktuell haben wir **3 verschiedene Implementierungen** für Session State Management, was zu **Inkonsistenzen, Bugs und Wartungs-Overhead** führt.

Der größte Fehler ist in `editor.js`: Es überschreibt den kompletten Session State beim Speichern, statt den spezialisierten `/api/session/editor` Endpoint zu nutzen.

Mit dem `SessionStateManager` haben wir:
- ✅ Eine zentrale, getestete Implementierung
- ✅ Spezialisierte Endpoints für jede Sektion
- ✅ Konsistente API über alle Seiten
- ✅ Bessere Performance durch Caching & Debouncing
- ✅ Keine Daten-Korruption mehr möglich

**Empfehlung:** Sofort mit Phase 1 + 2 starten (Editor Migration), da dies den kritischsten Bug behebt.
