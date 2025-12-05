# Layer-Effekte über Clip FX Tab - Umsetzungsplan (Layer-as-Clips Architecture)

## 📋 Ziel

Layer-Effekte sollen über den bestehenden **Clip FX Tab** verwaltet werden können. Wenn ein Layer ausgewählt ist, zeigt der Tab Layer-Effekte statt Clip-Effekte an.

**Architektur-Entscheidung:** 🎯 **Layer werden als eigenständige Clips behandelt!**

Jeder Layer bekommt eigene `clip_id` im ClipRegistry → Effekte werden über **bestehende Clip-Effekte API** verwaltet.

**Vorteile:**
- ✅ **0 neue API-Endpoints** (statt 6) → Clip-API wird wiederverwendet
- ✅ **0 Synchronisationsfunktionen** (statt 5+) → ClipRegistry ist Single Source
- ✅ **Einfacheres Routing** → Frontend verwendet `layer.clip_id` statt separate Layer-Endpoints
- ✅ **Automatische Persistenz** → Session-State funktioniert ohne Änderungen
- ✅ **3-4h Zeitersparnis** → Reduziert von 9-13h auf 5-9h

**Kernidee:**
```python
# Jeder Layer IST ein Clip mit Metadata:
clips['uuid-layer-1'] = {
    'clip_id': 'uuid-layer-1',
    'effects': [...],  # ← Effekte hier!
    'metadata': {'type': 'layer', 'layer_id': 1, 'layer_of': 'uuid-base'}
}

# Frontend einfach:
const clipId = layer.clip_id;  // 'uuid-layer-1'
POST /api/player/video/clip/uuid-layer-1/effects/add  // ← Gleiche API!
```

**Aktueller Stand:** 
- ✅ Multi-Layer-System funktioniert (v2.3.2)
- ✅ Clip FX Tab existiert und funktioniert für Clips
- ✅ `apply_layer_effects()` existiert (player.py:1579)
- ✅ Compositing-Loop wendet Layer-Effekte an (player.py:415, 437)
- ✅ Layer-Klasse mit `clip_id` Feld (layer.py:20)
- ✅ ClipRegistry UUID-basiert
- ❌ Layer bekommen noch keine eigene clip_id bei Erstellung
- ❌ Layer-Selection fehlt (kein visuelles Feedback)
- ❌ FX Tab routing kennt Layer-clip_ids noch nicht

**Ziel:** 
- Unified FX Tab für Clips UND Layer
- Layer-Selection mit visuellem Feedback
- Drag & Drop von Effekten funktioniert für beide
- API-Routing basiert auf `layer.clip_id` (keine separaten Endpoints!)

---

## 🔍 IST-Analyse

### ✅ Was bereits existiert

#### 1. Multi-Layer-System (Backend)
**Datei:** `src/modules/api_player_unified.py`

```python
# Layer CRUD bereits implementiert:
POST   /api/clips/{clip_id}/layers          # Layer hinzufügen
GET    /api/clips/{clip_id}/layers          # Alle Layer abrufen
DELETE /api/clips/{clip_id}/layers/{layer_id}  # Layer löschen
PUT    /api/clips/{clip_id}/layers/{layer_id}  # Layer-Properties ändern
```

**Struktur:**
```python
{
    "clip_id": "uuid-1234",
    "layers": [
        {
            "layer_id": 0,  # Base layer (immutable)
            "source_type": "video",
            "source_path": "kanal_1/video.mp4",
            "blend_mode": "normal",
            "opacity": 1.0,
            "effects": []  # ❌ Noch keine API für Layer-Effekte!
        },
        {
            "layer_id": 1,  # Overlay layer
            "source_type": "video",
            "source_path": "overlay.mp4",
            "blend_mode": "screen",
            "opacity": 0.7,
            "effects": []  # ❌ Noch keine API!
        }
    ]
}
```

---

#### 2. Clip FX Tab (Frontend)
**Datei:** `frontend/js/player.js`, Zeilen 2706-2850

**Funktionen:**
```javascript
// ✅ Bereits vorhanden:
window.addEffectToClip(pluginId)      // Effekt zu Clip hinzufügen
async function refreshClipEffects()    // Effekte vom Backend laden
function renderClipEffects()           // Effekte im UI rendern

// ✅ Global State:
let selectedClipId = null;             // Aktuell ausgewählter Clip
let selectedClipPlayerType = null;     // 'video' oder 'artnet'
let clipEffects = [];                  // Effekte des aktuellen Clips
```

**UI-Elemente:**
- `#clipFxTitle` - Titel (z.B. "🎬 Clip FX")
- `#clipFxList` - Container für Effekt-Liste
- Drag & Drop von Effekten aus Effect-Browser

---

#### 3. Clip FX API (Backend)
**Datei:** `src/modules/api_player_unified.py`, Zeilen 400-580

```python
# ✅ Bereits vorhanden:
GET    /api/player/{player_id}/clip/{clip_id}/effects       # Get clip effects
POST   /api/player/{player_id}/clip/{clip_id}/effects/add   # Add effect
DELETE /api/player/{player_id}/clip/{clip_id}/effects/{index}  # Remove effect
POST   /api/player/{player_id}/clip/{clip_id}/effects/clear    # Clear all
POST   /api/player/{player_id}/clip/{clip_id}/effects/{index}/params  # Update params
```

**Clip-Effekte sind in ClipRegistry gespeichert:**
```python
clip_registry.clips[clip_id] = {
    'clip_id': clip_id,
    'effects': [
        {'plugin_id': 'blur', 'params': {'strength': 5.0}},
        {'plugin_id': 'brightness', 'params': {'factor': 1.2}}
    ]
}
```

---

### ❌ Was fehlt

#### 1. Layer-Clip-Registrierung (Backend) - **EINFACH**
**Layer bekommen noch keine eigene clip_id bei Erstellung!**

**Benötigt:**
```python
# In add_layer_to_clip() - Layer als Clip registrieren:
def add_layer_to_clip(self, base_clip_id, source_path, blend_mode='normal', opacity=1.0):
    # ✅ NEU: Layer als eigenständigen Clip registrieren
    layer_clip_id = self.clip_registry.register_clip(
        player_id='video',  # oder 'artnet'
        absolute_path=source_path,
        relative_path=os.path.relpath(source_path, VIDEO_DIR),
        metadata={
            'type': 'layer',
            'layer_of': base_clip_id,
            'layer_id': self.layer_counter,
            'blend_mode': blend_mode,
            'opacity': opacity
        }
    )
    
    # Layer-Objekt mit clip_id erstellen
    layer = Layer(
        layer_id=self.layer_counter,
        source=source,
        blend_mode=blend_mode,
        opacity=opacity,
        clip_id=layer_clip_id  # ✅ Wichtig!
    )
    
    return layer, layer_clip_id
```

**Effekte funktionieren dann automatisch über bestehende API!**
```python
# Frontend kann Layer-Effekte mit bestehender Clip-API verwalten:
POST /api/player/video/clip/{layer_clip_id}/effects/add
# Kein Unterschied zwischen Clip und Layer! ✅
```

---

#### 2. Layer-Selection-Logik (Frontend) - **KRITISCH**
**Kein System um Layer auszuwählen!**

**Benötigt:**
```javascript
// Neue Global State:
let selectedLayerId = null;  // Aktuell ausgewählter Layer (0, 1, 2, ...)

// Neue Funktionen:
function selectLayer(layerId)     // Layer auswählen
function deselectLayer()          // Layer-Selection aufheben
function isLayerSelected()        // Check ob Layer ausgewählt
```

**Layer-Cards brauchen Click-Handler:**
- Click auf Layer-Card → Layer wird ausgewählt
- Visuelles Feedback: Border, Hintergrundfarbe ändern
- Clip FX Tab Titel ändert sich: "🎬 Clip FX" → "📐 Layer 1 FX"

---

#### 3. Layer-Cards UI (Frontend)
**Layer-Cards existieren, aber ohne Selection-Feedback!**

**Aktueller Code** (vermutlich in `player.js` oder separatem Layer-Modul):
```javascript
// Layer-Cards werden irgendwo gerendert, aber:
// ❌ Kein Click-Handler für Selection
// ❌ Kein visuelles Feedback bei Selection
// ❌ Keine Integration mit Clip FX Tab
```

**Wo sind Layer-Cards?**
- Suche nach: `layer-card`, `renderLayers`, `addLayer`, etc.
- Wahrscheinlich inline HTML oder dynamisch generiert

---

#### 4. FX Tab Routing-Logik (Frontend)
**Clip FX Tab kennt nur Clips, keine Layer!**

**Aktuell:**
```javascript
// IMMER Clip-Endpoints:
const endpoint = `/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects`;
```

**Benötigt:**
```javascript
// Dynamisches Routing basierend auf Selection:
let endpoint;
if (selectedLayerId !== null) {
    // Layer ausgewählt → Layer-Endpoints
    endpoint = `/api/clips/${selectedClipId}/layers/${selectedLayerId}/effects`;
} else {
    // Nur Clip ausgewählt → Clip-Endpoints
    endpoint = `/api/player/${selectedClipPlayerType}/clip/${selectedClipId}/effects`;
}
```

---

## 🎯 Umsetzungsplan

### Phase 1: Backend - Layer-Clip-Registrierung (~1-2h)

#### 1.1 Layer als Clip registrieren (1h)
**Datei:** `src/modules/player.py`, Zeile ~800 (add_layer_to_clip)

**Konzept:** Jeder Layer bekommt eigene `clip_id` im ClipRegistry → Effekte automatisch über bestehende Clip-API!

**Änderungen:**

```python
# VORHER:
    """Gibt alle Effekte eines Layers zurück."""
    try:
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            return jsonify({'error': 'Clip not found'}), 404
        
        layers = clip_data.get('layers', [])
        if layer_id >= len(layers):
            return jsonify({'error': f'Layer {layer_id} not found'}), 404
        
        effects = layers[layer_id].get('effects', [])
        
        return jsonify({
            'success': True,
            'clip_id': clip_id,
            'layer_id': layer_id,
            'effects': effects,
            'count': len(effects)
        })
    
    except Exception as e:
        logger.error(f"Error getting layer effects: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clips/<clip_id>/layers/<int:layer_id>/effects/add', methods=['POST'])
def add_layer_effect(clip_id, layer_id):
    """Fügt einen Effekt zu einem Layer hinzu."""
    try:
        data = request.get_json()
        plugin_id = data.get('plugin_id')
        params = data.get('params', {})
        
        if not plugin_id:
            return jsonify({'error': 'plugin_id required'}), 400
        
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            return jsonify({'error': 'Clip not found'}), 404
        
        layers = clip_data.get('layers', [])
        if layer_id >= len(layers):
            return jsonify({'error': f'Layer {layer_id} not found'}), 404
        
        # Initialize effects array if not exists
        if 'effects' not in layers[layer_id]:
            layers[layer_id]['effects'] = []
        
        # Add effect
        effect_config = {
            'plugin_id': plugin_id,
            'params': params
        }
        layers[layer_id]['effects'].append(effect_config)
        
        # Update clip in registry
        clip_registry.clips[clip_id]['layers'] = layers
        
        # Auto-save session state
        session_state = get_session_state()
        if session_state:
            session_state.save(player_manager, clip_registry)
        
        logger.info(f"✅ Effect '{plugin_id}' added to Layer {layer_id} of Clip {clip_id}")
        
        return jsonify({
            'success': True,
            'message': f'Effect added to layer {layer_id}',
            'effect_index': len(layers[layer_id]['effects']) - 1
        })
    
    except Exception as e:
        logger.error(f"Error adding layer effect: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clips/<clip_id>/layers/<int:layer_id>/effects/<int:index>', methods=['DELETE'])
def remove_layer_effect(clip_id, layer_id, index):
    """Entfernt einen Effekt von einem Layer."""
    try:
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            return jsonify({'error': 'Clip not found'}), 404
        
        layers = clip_data.get('layers', [])
        if layer_id >= len(layers):
            return jsonify({'error': f'Layer {layer_id} not found'}), 404
        
        effects = layers[layer_id].get('effects', [])
        if index >= len(effects):
            return jsonify({'error': f'Effect index {index} out of range'}), 404
        
        # Remove effect
        removed_effect = effects.pop(index)
        layers[layer_id]['effects'] = effects
        
        # Update clip in registry
        clip_registry.clips[clip_id]['layers'] = layers
        
        # Auto-save session state
        session_state = get_session_state()
        if session_state:
            session_state.save(player_manager, clip_registry)
        
        logger.info(f"🗑️ Effect removed from Layer {layer_id} of Clip {clip_id}: {removed_effect['plugin_id']}")
        
        return jsonify({'success': True, 'message': 'Effect removed'})
    
    except Exception as e:
        logger.error(f"Error removing layer effect: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clips/<clip_id>/layers/<int:layer_id>/effects/<int:index>/params', methods=['POST'])
def update_layer_effect_params(clip_id, layer_id, index):
    """Aktualisiert Parameter eines Layer-Effekts."""
    try:
        data = request.get_json()
        params = data.get('params', {})
        
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            return jsonify({'error': 'Clip not found'}), 404
        
        layers = clip_data.get('layers', [])
        if layer_id >= len(layers):
            return jsonify({'error': f'Layer {layer_id} not found'}), 404
        
        effects = layers[layer_id].get('effects', [])
        if index >= len(effects):
            return jsonify({'error': f'Effect index {index} out of range'}), 404
        
        # Update parameters
        effects[index]['params'] = params
        layers[layer_id]['effects'] = effects
        
        # Update clip in registry
        clip_registry.clips[clip_id]['layers'] = layers
        
        # Auto-save session state
        session_state = get_session_state()
        if session_state:
            session_state.save(player_manager, clip_registry)
        
        logger.info(f"🔧 Layer effect params updated: Clip {clip_id}, Layer {layer_id}, Effect {index}")
        
        return jsonify({'success': True, 'message': 'Parameters updated'})
    
    except Exception as e:
        logger.error(f"Error updating layer effect params: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/clips/<clip_id>/layers/<int:layer_id>/effects/clear', methods=['POST'])
def clear_layer_effects(clip_id, layer_id):
    """Entfernt alle Effekte von einem Layer."""
    try:
        clip_data = clip_registry.get_clip(clip_id)
        if not clip_data:
            return jsonify({'error': 'Clip not found'}), 404
        
        layers = clip_data.get('layers', [])
        if layer_id >= len(layers):
            return jsonify({'error': f'Layer {layer_id} not found'}), 404
        
        # Clear effects
        layers[layer_id]['effects'] = []
        
        # Update clip in registry
        clip_registry.clips[clip_id]['layers'] = layers
        
        # Auto-save session state
        session_state = get_session_state()
        if session_state:
            session_state.save(player_manager, clip_registry)
        
        logger.info(f"🗑️ All effects cleared from Layer {layer_id} of Clip {clip_id}")
        
        return jsonify({'success': True, 'message': 'All effects cleared'})
    
    except Exception as e:
        logger.error(f"Error clearing layer effects: {e}")
        return jsonify({'error': str(e)}), 500
```

---

#### 1.2 Layer-Effekte in apply_layer_effects() Integration (1h)
**Datei:** `src/modules/player.py` (Zeile 1579+)

**Status:** ✅ `apply_layer_effects()` existiert bereits!

**Aktueller Code:**
```python
def apply_layer_effects(self, layer, frame):
    """
    Wendet alle Effekte eines Layers auf ein Frame an.
    
    Args:
        layer: Layer-Objekt
        frame: Input Frame
    
    Returns:
        Prozessiertes Frame
    """
    for effect in layer.effects:
        # Skip disabled effects (parameters are preserved)
        if not effect.get('enabled', True):
            continue
        
        try:
            instance = effect['instance']
            frame = instance.process_frame(frame)
        except Exception as e:
            logger.error(f"❌ [{self.player_name}] Layer {layer.layer_id} effect error: {e}")
    
    return frame
```

**Problem:** Layer-Effekte liegen direkt in `layer.effects` Array, NICHT in ClipRegistry!

**Architektur:**
```python
# Layer-Objekt (in player.py):
class Layer:
    def __init__(self, layer_id, source, ...):
        self.effects = []  # Liste von {id, instance, config}

# ClipRegistry (in clip_registry.py):
clips[clip_id] = {
    'layers': [
        {
            'layer_id': 1,
            'source_type': 'video',
            'effects': []  # ⚠️ Noch leer! Muss synchronisiert werden!
        }
    ]
}
```

**Zwei Speicherorte:**
1. **Runtime:** `player.layers[i].effects` (Plugin-Instanzen)
2. **Persistence:** `clip_registry.clips[clip_id]['layers'][i]['effects']` (Konfiguration)

**Benötigte Änderungen:**

```python
# 1. Layer-Effekte zu ClipRegistry synchronisieren (nach add/remove)
def sync_layer_effects_to_registry(self, layer):
    """Synchronisiert Layer-Effekte zu ClipRegistry für Persistenz."""
    if not self.clip_registry or not layer.clip_id:
        return
    
    # Serialisiere Effekte (ohne Instanzen)
    effect_configs = [
        {
            'plugin_id': effect['id'],
            'params': effect.get('config', {}),
            'enabled': effect.get('enabled', True)
        }
        for effect in layer.effects
    ]
    
    # Update ClipRegistry
    clip_data = self.clip_registry.get_clip(layer.clip_id)
    if clip_data:
        layers = clip_data.get('layers', [])
        for reg_layer in layers:
            if reg_layer.get('layer_id') == layer.layer_id:
                reg_layer['effects'] = effect_configs
                break

# 2. Layer-Effekte von ClipRegistry laden (beim Clip-Load)
def load_layer_effects_from_registry(self, layer):
    """Lädt Layer-Effekte aus ClipRegistry und erstellt Plugin-Instanzen."""
    if not self.clip_registry or not layer.clip_id:
        return
    
    clip_data = self.clip_registry.get_clip(layer.clip_id)
    if not clip_data:
        return
    
    layers = clip_data.get('layers', [])
    for reg_layer in layers:
        if reg_layer.get('layer_id') == layer.layer_id:
            effects = reg_layer.get('effects', [])
            
            # Erstelle Plugin-Instanzen
            layer.effects = []
            for effect_config in effects:
                plugin_id = effect_config['plugin_id']
                params = effect_config.get('params', {})
                
                # Get plugin from manager
                plugin_instance = self.plugin_manager.create_effect_instance(
                    plugin_id, params
                )
                
                if plugin_instance:
                    layer.effects.append({
                        'id': plugin_id,
                        'instance': plugin_instance,
                        'config': params,
                        'enabled': effect_config.get('enabled', True)
                    })
            
            logger.debug(f"✅ Loaded {len(layer.effects)} effects for Layer {layer.layer_id}")
            break
```

**Integration in Compositing-Loop (Zeile 410-440):**
```python
# ✅ Bereits vorhanden!
if self.layers and len(self.layers) > 0:
    frame, source_delay = self.layers[0].source.get_next_frame()
    
    if frame is not None:
        # Wende Layer 0 Effects an ✅
        frame = self.apply_layer_effects(self.layers[0], frame)
        
        # Composite Slave Layers
        for layer in self.layers[1:]:
            overlay_frame, _ = layer.source.get_next_frame()
            
            # Wende Layer Effects an ✅
            overlay_frame = self.apply_layer_effects(layer, overlay_frame)
            
            # Blend
            blend_plugin = self.get_blend_plugin(layer.blend_mode, layer.opacity)
            frame = blend_plugin.process_frame(frame, overlay=overlay_frame)
```

**Status:** Compositing-Loop ist bereits korrekt! Nur Synchronisation zu ClipRegistry fehlt.

---

#### 1.3 Synchronisation Layer ↔ ClipRegistry (1-2h)
**Datei:** `src/modules/player.py`

**Problem:** Layer-Effekte existieren zweimal:
- **Runtime:** `player.layers[i].effects` (Plugin-Instanzen)
- **Persistence:** `clip_registry.clips[clip_id]['layers'][i]['effects']` (Config)

**Benötigte Funktionen:**

```python
def sync_layer_effects_to_registry(self, layer):
    """
    Synchronisiert Layer-Effekte zu ClipRegistry (für Session-State Persistenz).
    Wird nach jedem add/remove/update aufgerufen.
    """
    if not self.clip_registry or not layer.clip_id:
        return
    
    # Serialisiere Effekte
    effect_configs = [
        {
            'plugin_id': effect['id'],
            'params': effect.get('config', {}),
            'enabled': effect.get('enabled', True)
        }
        for effect in layer.effects
    ]
    
    # Update Registry
    clip_data = self.clip_registry.get_clip(layer.clip_id)
    if clip_data:
        layers = clip_data.get('layers', [])
        for reg_layer in layers:
            if reg_layer.get('layer_id') == layer.layer_id:
                reg_layer['effects'] = effect_configs
                logger.debug(f"✅ Synced {len(effect_configs)} effects to registry: Layer {layer.layer_id}")
                return

def load_layer_effects_from_registry(self, layer):
    """
    Lädt Layer-Effekte aus ClipRegistry und erstellt Plugin-Instanzen.
    Wird beim Layer-Load aufgerufen.
    """
    if not self.clip_registry or not layer.clip_id:
        return
    
    clip_data = self.clip_registry.get_clip(layer.clip_id)
    if not clip_data:
        return
    
    layers = clip_data.get('layers', [])
    for reg_layer in layers:
        if reg_layer.get('layer_id') == layer.layer_id:
            effects = reg_layer.get('effects', [])
            
            # Erstelle Plugin-Instanzen
            layer.effects = []
            for effect_config in effects:
                plugin_id = effect_config['plugin_id']
                params = effect_config.get('params', {})
                enabled = effect_config.get('enabled', True)
                
                # Create plugin instance
                plugin_class = self.plugin_manager.get_plugin(plugin_id)
                if not plugin_class:
                    logger.warning(f"⚠️ Plugin '{plugin_id}' not found")
                    continue
                
                plugin_instance = plugin_class()
                plugin_instance.initialize(params)
                
                layer.effects.append({
                    'id': plugin_id,
                    'instance': plugin_instance,
                    'config': params,
                    'enabled': enabled
                })
            
            logger.info(f"✅ Loaded {len(layer.effects)} effects for Layer {layer.layer_id}")
            return

def add_effect_to_layer(self, layer_id, plugin_id, params=None):
    """
    Fügt Effekt zu Layer hinzu (wird von API aufgerufen).
    """
    if layer_id >= len(self.layers):
        return False, f"Layer {layer_id} not found"
    
    layer = self.layers[layer_id]
    
    # Create plugin instance
    plugin_class = self.plugin_manager.get_plugin(plugin_id)
    if not plugin_class:
        return False, f"Plugin '{plugin_id}' not found"
    
    plugin_instance = plugin_class()
    plugin_instance.initialize(params or {})
    
    # Add to layer
    layer.effects.append({
        'id': plugin_id,
        'instance': plugin_instance,
        'config': params or {},
        'enabled': True
    })
    
    # Sync to registry
    self.sync_layer_effects_to_registry(layer)
    
    logger.info(f"✅ Effect '{plugin_id}' added to Layer {layer_id}")
    return True, "Effect added"

def remove_effect_from_layer(self, layer_id, effect_index):
    """
    Entfernt Effekt von Layer (wird von API aufgerufen).
    """
    if layer_id >= len(self.layers):
        return False, f"Layer {layer_id} not found"
    
    layer = self.layers[layer_id]
    
    if effect_index >= len(layer.effects):
        return False, f"Effect index {effect_index} out of range"
    
    removed = layer.effects.pop(effect_index)
    
    # Sync to registry
    self.sync_layer_effects_to_registry(layer)
    
    logger.info(f"🗑️ Effect '{removed['id']}' removed from Layer {layer_id}")
    return True, "Effect removed"

def update_layer_effect_params(self, layer_id, effect_index, params):
    """
    Aktualisiert Effekt-Parameter (wird von API aufgerufen).
    """
    if layer_id >= len(self.layers):
        return False, f"Layer {layer_id} not found"
    
    layer = self.layers[layer_id]
    
    if effect_index >= len(layer.effects):
        return False, f"Effect index {effect_index} out of range"
    
    effect = layer.effects[effect_index]
    
    # Update config
    effect['config'].update(params)
    
    # Re-initialize plugin with new params
    effect['instance'].initialize(effect['config'])
    
    # Sync to registry
    self.sync_layer_effects_to_registry(layer)
    
    logger.info(f"🔧 Layer {layer_id} effect {effect_index} params updated")
    return True, "Parameters updated"
```

**Integration in Layer-Load:**
```python
# In load_clip() oder add_layer() - nach Layer-Erstellung:
def add_layer_to_clip(self, source, blend_mode='normal', opacity=100.0):
    layer_id = len(self.layers)
    layer = Layer(layer_id, source, blend_mode, opacity, clip_id=self.current_clip_id)
    self.layers.append(layer)
    
    # ✅ Lade Effekte aus Registry
    self.load_layer_effects_from_registry(layer)
    
    return layer
```

---

### Phase 2: Frontend - Layer-Selection (~2-3h)

#### 2.1 Layer-Selection State & Logik (1h)
**Datei:** `frontend/js/player.js`

**Neue Global Variables:**
```javascript
// Layer-Selection State
let selectedLayerId = null;  // null = kein Layer ausgewählt, 0/1/2/... = Layer-ID

/**
 * Wählt einen Layer aus und aktualisiert UI.
 * @param {number} layerId - Layer-ID (0, 1, 2, ...)
 */
function selectLayer(layerId) {
    if (!selectedClipId) {
        console.warn('⚠️ No clip selected, cannot select layer');
        return;
    }
    
    // Update state
    selectedLayerId = layerId;
    
    debug.log(`📐 Layer ${layerId} selected for Clip ${selectedClipId}`);
    
    // Update UI
    updateLayerSelectionUI();
    
    // Refresh FX Tab (lädt Layer-Effekte)
    refreshClipEffects();
}

/**
 * Hebt Layer-Selection auf.
 */
function deselectLayer() {
    selectedLayerId = null;
    
    debug.log('📐 Layer deselected');
    
    // Update UI
    updateLayerSelectionUI();
    
    // Refresh FX Tab (lädt Clip-Effekte)
    refreshClipEffects();
}

/**
 * Check ob Layer ausgewählt ist.
 */
function isLayerSelected() {
    return selectedLayerId !== null;
}

/**
 * Aktualisiert visuelles Feedback für Layer-Selection.
 */
function updateLayerSelectionUI() {
    // Remove 'selected' class from all layer cards
    document.querySelectorAll('.layer-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    // Add 'selected' class to selected layer
    if (selectedLayerId !== null) {
        const selectedCard = document.querySelector(`.layer-card[data-layer-id="${selectedLayerId}"]`);
        if (selectedCard) {
            selectedCard.classList.add('selected');
        }
    }
}
```

---

#### 2.2 Layer-Cards Click-Handler (1h)
**Wo sind Layer-Cards?** → Suche + Integration

**Vermutete Orte:**
- `frontend/js/player.js` (inline HTML generation)
- Separate Datei `frontend/js/layers.js` (nicht gefunden)
- HTML inline in `index.html`

**Integration:**
```javascript
// Beispiel: Wenn Layer-Cards dynamisch generiert werden
function renderLayerCard(layer, layerId) {
    const card = document.createElement('div');
    card.className = 'layer-card';
    card.dataset.layerId = layerId;
    
    // Click-Handler für Selection ✅ NEU!
    card.addEventListener('click', (e) => {
        e.stopPropagation();
        
        if (selectedLayerId === layerId) {
            // Toggle: Deselect wenn bereits ausgewählt
            deselectLayer();
        } else {
            // Select layer
            selectLayer(layerId);
        }
    });
    
    // ... rest of layer card rendering
    
    return card;
}
```

**CSS für Selection-Feedback:**
```css
/* In frontend/css/styles.css */
.layer-card {
    border: 2px solid transparent;
    transition: border-color 0.2s;
    cursor: pointer;
}

.layer-card:hover {
    border-color: rgba(255, 255, 255, 0.3);
}

.layer-card.selected {
    border-color: #007bff;  /* Blau für ausgewählten Layer */
    background-color: rgba(0, 123, 255, 0.1);
}
```

---

#### 2.3 Clip-Selection cleant Layer-Selection (30min)
**Problem:** Wenn neuer Clip ausgewählt wird, muss Layer-Selection zurückgesetzt werden!

**Fix in `loadVideoFile()` / `loadArtnetFile()` / etc.:**
```javascript
// In allen Clip-Load-Funktionen:
async function loadClipAnywhere(playerId, clipPath, clipId) {
    // ... existing code ...
    
    // Clear layer selection when new clip is loaded ✅ NEU!
    deselectLayer();
    
    // ... rest ...
}
```

---

### Phase 3: Frontend - FX Tab Routing (~2-3h)

#### 3.1 Dynamisches API-Routing mit Layer-clip_id (1h)
**Datei:** `frontend/js/player.js`, Zeilen 2706-2850

**Konzept:** Layer haben eigene `clip_id` → Frontend verwendet `layer.clip_id` statt `base_clip_id`!

**Neue Global Variables:**
```javascript
let selectedLayerClipId = null;  // clip_id des ausgewählten Layers
```

**Änderungen:**

```javascript
// ✅ VEREINFACHT: Keine separaten Endpoints mehr!
// Layer-clip_id wird wie normale clip_id behandelt

// In selectLayer():
async function selectLayer(layerId) {
    if (!selectedClipId) return;
    
    selectedLayerId = layerId;
    
    // ✅ NEU: Lade layer.clip_id vom Backend
    try {
        const response = await fetch(`${API_BASE}/api/clips/${selectedClipId}/layers`);
        const data = await response.json();
        
        if (data.success && data.layers) {
            const layer = data.layers.find(l => l.layer_id === layerId);
            if (layer && layer.clip_id) {
                selectedLayerClipId = layer.clip_id;  // ✅ Speichere Layer-clip_id
                debug.log(`📐 Layer ${layerId} selected, clip_id: ${selectedLayerClipId}`);
            }
        }
    } catch (error) {
        console.error('Error loading layer clip_id:', error);
    }
    
    updateLayerSelectionUI();
    refreshClipEffects();
}

// In deselectLayer():
function deselectLayer() {
    selectedLayerId = null;
    selectedLayerClipId = null;  // ✅ Reset
    updateLayerSelectionUI();
    refreshClipEffects();
}

// ✅ Update: addEffectToClip - VEREINFACHT!
window.addEffectToClip = async function(pluginId) {
    if (!selectedClipId || !selectedClipPlayerType) {
        showToast('No clip selected', 'warning');
        return;
    }
    
    // Prevent Transport on generators (nur für Clips, nicht Layer!)
    if (pluginId === 'transport' && window.currentGeneratorId && !isLayerSelected()) {
        showToast('⚠️ Transport effect not available for generator clips', 'warning');
        return;
    }
    
    try {
        // ✅ EINFACH: Verwende layer.clip_id falls Layer ausgewählt
        const clipId = selectedLayerClipId || selectedClipId;
        const endpoint = `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${clipId}/effects/add`;
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plugin_id: pluginId })
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            const target = isLayerSelected() ? `Layer ${selectedLayerId}` : 'Clip';
            debug.log(`✅ Effect added to ${target}:`, pluginId);
            await refreshClipEffects();
        } else {
            showToast(`Failed to add effect: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('❌ Error adding effect:', error);
        showToast('Error adding effect', 'error');
    }
};

// ✅ Update: refreshClipEffects
async function refreshClipEffects() {
    if (!selectedClipId || !selectedClipPlayerType) {
        const container = document.getElementById('clipFxList');
        const title = document.getElementById('clipFxTitle');
        container.innerHTML = '<div class="empty-state"><p>Select a clip to manage effects</p></div>';
        title.innerHTML = '<span class="player-icon">🎬</span> Clip FX';
        clipEffects = [];
        return;
    }
    
    try {
        const endpoint = getFXEndpoint();  // ✅ Dynamisch!
        
        const response = await fetch(endpoint, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            let effects = data.effects || [];
            
            // Filter Transport nur für Generator-CLIPS (nicht Layer!)
            if (window.currentGeneratorId && !isLayerSelected()) {
                effects = effects.filter(effect => effect.plugin_id !== 'transport');
            }
            
### Phase 1: Backend (Layer-as-Clips Architecture)
- [ ] `add_layer_to_clip()` registriert Layer als Clip im ClipRegistry
- [ ] Layer-Objekt speichert `clip_id` (metadata: type='layer')
- [ ] `load_layer_effects_from_clip_registry()` implementiert
- [ ] Integration: Effekte beim Layer-Load aus ClipRegistry laden
- [ ] ✅ `apply_layer_effects()` bereits vorhanden (Zeile 1579)
- [ ] ✅ Compositing-Loop bereits korrekt (Zeile 410-440)
- [ ] ✅ API-Endpoints bereits vorhanden (Clip-API wird wiederverwendet!)
- [ ] ✅ Keine Synchronisation nötig (ClipRegistry = Single Source of Truth)
    } catch (error) {
        console.error('❌ Error refreshing effects:', error);
    }
}

// ✅ Update: removeEffectFromClip
window.removeEffectFromClip = async function(index) {
    try {
        const endpoint = getFXEndpoint(`/${index}`);  // ✅ Dynamisch!
        
        const response = await fetch(endpoint, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            await refreshClipEffects();
        }
    } catch (error) {
        console.error('❌ Error removing effect:', error);
    }
};

// ✅ Update: updateEffectParameter
async function updateEffectParameter(effectIndex, paramName, paramValue) {
    try {
        const endpoint = getFXEndpoint(`/${effectIndex}/params`);  // ✅ Dynamisch!
        
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                params: {
                    [paramName]: paramValue
                }
            })
        });
        
        // ... rest ...
    } catch (error) {
        console.error('❌ Error updating effect parameter:', error);
    }
}
```

---

#### 3.2 FX Tab Titel & Icon dynamisch (30min)
**Datei:** `frontend/js/player.js`, Funktion `renderClipEffects()`

```javascript
function renderClipEffects() {
    const container = document.getElementById('clipFxList');
    const title = document.getElementById('clipFxTitle');
    
    // ✅ Dynamischer Titel basierend auf Selection
    let icon, titleText;
    
    if (isLayerSelected()) {
        // Layer ausgewählt
        icon = '📐';
        titleText = `Layer ${selectedLayerId} FX`;
    } else if (window.currentGeneratorId && window.currentGeneratorMeta) {
        // Generator-Clip
        icon = '⚙️';
        titleText = `${window.currentGeneratorMeta.name} FX`;
    } else {
        // Normaler Clip
        icon = selectedClipPlayerType === 'video' ? '🎬' : '🎨';
        let clipName = selectedClipPath ? selectedClipPath.split('/').pop() : 'Clip';
        titleText = `${clipName} FX`;
    }
    
    title.innerHTML = `<span class="player-icon">${icon}</span> ${titleText}`;
    
    // ... rest of rendering ...
}
```

---

#### 3.3 Drag & Drop für Layer-Effekte (1h)
**Aktuell:** Drag & Drop funktioniert nur für Clips

**Fix:** Drop-Handler muss Layer-Selection prüfen

```javascript
// In Effect-Browser Drop-Handler:
effectBrowser.addEventListener('drop', async (e) => {
    e.preventDefault();
    
    const pluginId = e.dataTransfer.getData('text/plain');
    
    if (!pluginId) return;
    
    // Check if clip or layer is selected
    if (!selectedClipId) {
        showToast('⚠️ Select a clip or layer first', 'warning');
        return;
    }
    
    // Add effect (routing happens in addEffectToClip) ✅ Bereits korrekt!
    await window.addEffectToClip(pluginId);
});
```

**Status:** Sollte automatisch funktionieren wenn `addEffectToClip()` korrekt umgeschrieben ist! ✅

---

### Phase 4: Testing & Edge-Cases (~1-2h)

#### 4.1 Test-Szenarien
- [ ] **Clip-Effekte:**
  - Effekt zu Clip hinzufügen → funktioniert
  - Parameter ändern → funktioniert
  - Effekt löschen → funktioniert
  
- [ ] **Layer-Effekte:**
  - Layer auswählen → Selection-UI funktioniert
  - Effekt zu Layer hinzufügen → API-Call korrekt
  - Parameter ändern → API-Call korrekt
  - Effekt löschen → API-Call korrekt
  - Layer deselect → zurück zu Clip-Effekten
  
- [ ] **Layer-Selection:**
  - Click auf Layer-Card → ausgewählt
  - Click auf bereits ausgewählte Layer-Card → deselected
  - Neuer Clip laden → Layer-Selection zurückgesetzt
  - Layer löschen während ausgewählt → Selection zurückgesetzt
  
- [ ] **Edge-Cases:**
  - Transport-Effekt auf Generator-Layer → sollte funktionieren!
  - Trim-Controls versteckt bei Layer-Selection → funktioniert
  - Effect-Browser Drag & Drop auf Layer → funktioniert
  - Session-State speichert Layer-Effekte → funktioniert

---

#### 4.2 Debugging & Logging
```javascript
// Debug-Logging für Layer-Selection
debug.log('📐 Layer Selection State:', {
    selectedClipId,
    selectedLayerId,
    isLayerSelected: isLayerSelected(),
    endpoint: getFXEndpoint()
| Phase | Aufwand | Beschreibung |
|-------|---------|--------------|
| **Phase 1** | 1-2h | Backend Layer-Clip-Registrierung (Layer-as-Clips) |
| **Phase 2** | 2-3h | Frontend Layer-Selection |
| **Phase 3** | 1-2h | Frontend FX Tab Routing (vereinfacht!) |
| **Phase 4** | 1-2h | Testing & Edge-Cases |
| **GESAMT** | **5-9h** | **Vollständige Layer-FX Integration** (3-4h gespart!) |
| Phase | Aufwand | Beschreibung |
|-------|---------|--------------|
| **Phase 1** | 3-4h | Backend Layer-Effekt-API |
| **Phase 2** | 2-3h | Frontend Layer-Selection |
| **Phase 3** | 2-3h | Frontend FX Tab Routing |
| **Phase 4** | 1-2h | Testing & Edge-Cases |
| **GESAMT** | **8-12h** | **Vollständige Layer-FX Integration** |

---

## ✅ Checkliste

### Phase 1: Backend
- [ ] `GET /api/clips/{clip_id}/layers/{layer_id}/effects` implementiert
- [ ] `POST /api/clips/{clip_id}/layers/{layer_id}/effects/add` implementiert
- [ ] `DELETE /api/clips/{clip_id}/layers/{layer_id}/effects/{index}` implementiert
- [ ] `POST /api/clips/{clip_id}/layers/{layer_id}/effects/{index}/params` implementiert
- [ ] `POST /api/clips/{clip_id}/layers/{layer_id}/effects/clear` implementiert
- [ ] `apply_layer_effects()` Integration in Compositing-Loop
- [ ] Session-State speichert Layer-Effekte

### Phase 2: Layer-Selection
- [ ] Global State `selectedLayerId` hinzugefügt
- [ ] `selectLayer(layerId)` Funktion implementiert
- [ ] `deselectLayer()` Funktion implementiert
- [ ] `isLayerSelected()` Helper implementiert
- [ ] `updateLayerSelectionUI()` für visuelles Feedback
- [ ] Layer-Cards Click-Handler hinzugefügt
- [ ] CSS für `.layer-card.selected` Styling
- [ ] Clip-Load cleant Layer-Selection

### Phase 3: FX Tab Routing (vereinfacht!)
- [ ] `selectedLayerClipId` state hinzugefügt (speichert layer.clip_id)
- [ ] `selectLayer()` lädt layer.clip_id aus Backend
- [ ] `addEffectToClip()` verwendet `selectedLayerClipId || selectedClipId`
- [ ] `refreshClipEffects()` verwendet `selectedLayerClipId || selectedClipId`  
- [ ] `removeEffectFromClip()` verwendet `selectedLayerClipId || selectedClipId`
- [ ] `updateEffectParameter()` verwendet `selectedLayerClipId || selectedClipId`
- [ ] FX Tab Titel dynamisch (Clip vs Layer)
- [ ] ✅ Keine separaten Endpoints nötig! (Clip-API wird wiederverwendet)

### Phase 4: Testing
- [ ] Clip-Effekte funktionieren (add/remove/update)
- [ ] Layer-Effekte funktionieren (add/remove/update)
- [ ] Layer-Selection UI funktioniert
- [ ] Drag & Drop auf Layer funktioniert
- [ ] Edge-Cases getestet (Transport, Trim, Session-State)

---

## 🎯 Ergebnis

Nach Abschluss:

### ✅ Unified FX Tab
- **Ein Tab für alles:** Clip-Effekte UND Layer-Effekte
- **Smart Routing:** API-Calls basieren auf Selection-State
- **Visual Feedback:** Layer-Selection mit Border + Background

### ✅ User-Flow

**Clip-Effekte verwalten:**
1. Clip in Playlist auswählen (wie bisher)
2. Clip FX Tab zeigt Clip-Effekte
3. Effekte hinzufügen/bearbeiten

**Layer-Effekte verwalten:**
1. Clip in Playlist auswählen
2. **NEU:** Layer-Card clicken (z.B. Layer 1)
3. Clip FX Tab wird zu "Layer 1 FX"
4. Effekte hinzufügen/bearbeiten für Layer
5. Layer-Card nochmal clicken → zurück zu Clip-Effekten

### ✅ Vorteile
- Keine separate Layer-FX-UI nötig (spart Platz)
- Konsistente UX (gleiche Effekt-Controls)
- Wiederverwendung aller bestehenden FX-Features (Drag & Drop, Parameter-UI, etc.)
- Minimal-invasive Änderungen (kein großes Refactoring)

---

**Erstellt:** 2025-12-05  
**Status:** 🟡 Plan erstellt - Bereit für Umsetzung  
**Priorität:** P1 (Quick Win)  
**Nächster Schritt:** Phase 1 - Layer-Clip-Registrierung (1-2h, ~50 Zeilen Code)
