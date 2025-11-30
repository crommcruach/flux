# Plugin-System - Quick Start

## Überblick

Das Plugin-System ermöglicht dynamische Erweiterung von Flux mit:
- **Effects** - Bildverarbeitung (Blur, Color, Distortion)
- **Generators** - Frame-Generierung (Patterns, Procedural Graphics)
- **Sources** - Frame-Quellen (LiveStream, ImageSequence)
- **Transitions** - Übergänge zwischen Frames

## Architektur

```
src/plugins/
├── plugin_base.py         # PluginBase, PluginType, ParameterType
├── effects/               # Effect Plugins
│   ├── blur.py            # Beispiel: BlurEffect
│   └── ...
├── generators/            # Generator Plugins
├── sources/               # Source Plugins
└── transitions/           # Transition Plugins

src/modules/
└── plugin_manager.py      # PluginManager (Discovery, Registry, Validation)
```

## Plugin erstellen

### 1. Plugin-Klasse definieren

```python
from plugins import PluginBase, PluginType, ParameterType
import cv2

class BlurEffect(PluginBase):
    # Metadaten
    METADATA = {
        'id': 'blur',
        'name': 'Gaussian Blur',
        'description': 'Verwischt das Bild mit Gaussian Blur',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Blur/Distortion'
    }
    
    # Parameter-Definitionen
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Blur Stärke',
            'type': ParameterType.FLOAT,
            'default': 5.0,
            'min': 0.0,
            'max': 20.0,
            'step': 0.5,
            'description': 'Stärke des Blur-Effekts'
        }
    ]
    
    def initialize(self, config):
        """Initialisiert Plugin mit Config."""
        self.strength = config.get('strength', 5.0)
    
    def process_frame(self, frame, **kwargs):
        """Verarbeitet Frame."""
        if self.strength == 0:
            return frame
        
        kernel_size = int(self.strength) * 2 + 1
        return cv2.GaussianBlur(frame, (kernel_size, kernel_size), 0)
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'strength':
            self.strength = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Werte zurück."""
        return {'strength': self.strength}
```

### 2. Plugin speichern

Speichere als `src/plugins/effects/blur.py`. Der PluginManager findet es automatisch beim Start.

### 3. Plugin registrieren (automatisch)

```python
# PluginManager scannt plugins/ Ordner automatisch
from modules.plugin_manager import get_plugin_manager

pm = get_plugin_manager()
# ✓ Plugin geladen: blur (plugins.effects.blur)
```

## REST API

### Effect Pipeline (Player)

Die Effect Chain erlaubt es, Effects auf den Video/Script-Stream anzuwenden. Effects werden in der Reihenfolge ihrer Hinzufügung angewendet.

#### GET /api/player/effects

Gibt die aktuelle Effect Chain zurück.

**Response:**
```json
{
  "effects": [
    {
      "index": 0,
      "id": "blur",
      "name": "Gaussian Blur",
      "version": "1.0.0",
      "config": {
        "strength": 5.0
      }
    }
  ],
  "count": 1
}
```

#### POST /api/player/effects/add

Fügt einen Effect zur Chain hinzu.

**Request Body:**
```json
{
  "plugin_id": "blur",
  "config": {
    "strength": 5.0
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Effect 'blur' added to chain",
  "index": 0
}
```

#### DELETE /api/player/effects/{index}

Entfernt einen Effect aus der Chain.

**Response:**
```json
{
  "success": true,
  "message": "Effect 'blur' removed from chain"
}
```

#### POST /api/player/effects/clear

Entfernt alle Effects aus der Chain.

**Response:**
```json
{
  "success": true,
  "message": "2 effects cleared"
}
```

#### POST /api/player/effects/{index}/parameters/{param_name}

Aktualisiert einen Parameter eines Effects zur Laufzeit.

**Request Body:**
```json
{
  "value": 15.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Parameter 'strength' updated"
}
```

**Beispiel:**
```bash
# Blur Effect hinzufügen
curl -X POST http://localhost:5000/api/player/effects/add \
  -H "Content-Type: application/json" \
  -d '{"plugin_id":"blur","config":{"strength":5.0}}'

# Blur Stärke erhöhen
curl -X POST http://localhost:5000/api/player/effects/0/parameters/strength \
  -H "Content-Type: application/json" \
  -d '{"value":15.0}'

# Effect entfernen
curl -X DELETE http://localhost:5000/api/player/effects/0

# Alle Effects löschen
curl -X POST http://localhost:5000/api/player/effects/clear
```

---

### Plugin-Verwaltung

#### Alle Plugins auflisten

```bash
GET /api/plugins/list
```

**Response:**
```json
{
  "plugins": [
    {
      "id": "blur",
      "name": "Gaussian Blur",
      "description": "Verwischt das Bild mit Gaussian Blur",
      "type": "effect",
      "category": "Blur/Distortion",
      "author": "Flux Team",
      "version": "1.0.0"
    }
  ],
  "count": 1
}
```

### Plugin-Parameter abrufen

```bash
GET /api/plugins/blur/parameters
```

**Response:**
```json
{
  "parameters": [
    {
      "name": "strength",
      "label": "Blur Stärke",
      "type": "float",
      "default": 5.0,
      "min": 0.0,
      "max": 20.0,
      "step": 0.5,
      "description": "Stärke des Blur-Effekts"
    }
  ]
}
```

### Plugin laden

```bash
POST /api/plugins/blur/load
Content-Type: application/json

{
  "config": {
    "strength": 10.0
  }
}
```

**Response:**
```json
{
  "success": true,
  "plugin_id": "blur",
  "message": "Plugin loaded successfully"
}
```

### Parameter aktualisieren

```bash
POST /api/plugins/blur/parameters/strength
Content-Type: application/json

{
  "value": 15.0
}
```

**Response:**
```json
{
  "success": true,
  "plugin_id": "blur",
  "parameter": "strength",
  "value": 15.0
}
```

### Plugin entladen

```bash
POST /api/plugins/blur/unload
```

## Parameter-Typen

### FLOAT / INT
Slider mit min, max, step

```python
{
    'name': 'strength',
    'type': ParameterType.FLOAT,
    'default': 5.0,
    'min': 0.0,
    'max': 20.0,
    'step': 0.5
}
```

### BOOL
Checkbox

```python
{
    'name': 'enabled',
    'type': ParameterType.BOOL,
    'default': True
}
```

### SELECT
Dropdown

```python
{
    'name': 'mode',
    'type': ParameterType.SELECT,
    'default': 'fast',
    'options': ['fast', 'quality', 'balanced']
}
```

### COLOR
Color Picker (Hex)

```python
{
    'name': 'tint_color',
    'type': ParameterType.COLOR,
    'default': '#FF0000'
}
```

### STRING
Text Input

```python
{
    'name': 'text',
    'type': ParameterType.STRING,
    'default': 'Hello World'
}
```

### RANGE
Dual-Slider (min/max Range)

```python
{
    'name': 'threshold_range',
    'type': ParameterType.RANGE,
    'default': [50, 150],
    'min': 0,
    'max': 255
}
```

## Plugin-Typen

### EFFECT
Verarbeitet Frames (Input → Output)

```python
METADATA = {'type': PluginType.EFFECT}

def process_frame(self, frame, **kwargs):
    return cv2.GaussianBlur(frame, (5, 5), 0)
```

### GENERATOR
Erzeugt Frames (kein Input)

```python
METADATA = {'type': PluginType.GENERATOR}

def generate_frame(self, width, height, frame_number, time, fps):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # ... Pattern generieren
    return frame
```

### SOURCE
Frame-Quelle (z.B. Video, Stream)

```python
METADATA = {'type': PluginType.SOURCE}

def get_frame(self):
    ret, frame = self.cap.read()
    return frame if ret else None

def seek(self, frame_number):
    self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
```

### TRANSITION
Mischt zwei Frames

```python
METADATA = {'type': PluginType.TRANSITION}

def blend_frames(self, frame_a, frame_b, progress):
    return cv2.addWeighted(frame_a, 1-progress, frame_b, progress, 0)
```

## Entwicklung

### Plugin-Reload (Development)

```bash
POST /api/plugins/reload
```

Lädt alle Plugins neu ohne Server-Restart.

### Fehlerbehandlung

```python
try:
    instance = pm.load_plugin('blur', config={'strength': 10.0})
except Exception as e:
    print(f"Fehler: {e}")
```

### Validierung

```python
# Parameter-Wert validieren
is_valid = pm.validate_parameter_value('blur', 'strength', 15.0)
# True

is_valid = pm.validate_parameter_value('blur', 'strength', 999)
# False (außerhalb min/max)
```

## Statistiken

```bash
GET /api/plugins/stats
```

**Response:**
```json
{
  "total_plugins": 10,
  "loaded_instances": 2,
  "by_type": {
    "effect": 5,
    "generator": 3,
    "source": 1,
    "transition": 1
  }
}
```

## Best Practices

1. **METADATA validieren** - Immer `id`, `name`, `type` angeben
2. **PARAMETERS dokumentieren** - `description` für UI-Hints
3. **cleanup() implementieren** - Ressourcen freigeben (OpenCV Captures, etc.)
4. **NumPy nutzen** - Für Performance bei Frame-Verarbeitung
5. **Fehlerbehandlung** - Exceptions in process_frame() abfangen
6. **Type Hints** - Für bessere IDE-Unterstützung

## Roadmap

- [ ] **Effect Pipeline** - Effekt-Ketten im Player
- [ ] **Presets** - Speichern/Laden von Parameter-Sets
- [ ] **Hot-Reload** - Automatisches Reload bei Code-Änderung
- [ ] **UI-Generierung** - Dynamisches Frontend-Panel
- [ ] **Plugin-Store** - Zentrale Plugin-Registry

## Beispiele

Siehe:
- `src/plugins/effects/blur.py` - Blur Effect (EFFECT)
- `src/plugins/effects/opacity.py` - Opacity Effect (EFFECT)
- `src/plugins/effects/transform.py` - Transform Effect (EFFECT)
- `src/scripts/rainbow_wave.py` - Generator-ähnlich (GENERATOR Vorlage)

## Built-in Effect Plugins

### Blend Effect (Multi-Layer Compositing)
**ID:** `blend`  
**Kategorie:** Compositing

Mischt zwei Frames mit verschiedenen Blend-Modi (für Layer-Compositing):
- **blend_mode** (SELECT) - Blend-Algorithmus:
  - `normal` - Standard Alpha-Compositing
  - `multiply` - Farben multiplizieren (dunkles Overlay)
  - `screen` - Invertiert multiplizieren (helles Overlay)
  - `overlay` - Multiply + Screen kombiniert
  - `add` - Additive Blending (Lichter aufaddieren)
  - `subtract` - Subtraktive Blending (Farben subtrahieren)
- **opacity** (0-100%) - Overlay-Transparenz

**Verwendung:**
```python
# Automatisch vom Player verwendet (Layer-System)
# Layer 0 (Base) + Layer 1 (Overlay):
result = blend_plugin.process_frame(
    frame,              # Base frame (Layer 0)
    overlay=overlay,    # Overlay frame (Layer 1)
    blend_mode='screen',
    opacity=70.0
)
```

**Hinweise:**
- Wird intern vom Multi-Layer-System verwendet
- Nicht direkt als Player-Effect hinzufügbar
- Layer-Management via `/api/clips/{clip_id}/layers` API

### Opacity Effect
**ID:** `opacity`  
**Kategorie:** Farb-Manipulation

Steuert die Video-Opazität (Transparenz):
- **opacity** (0-100%) - Video-Transparenz
  - 100% = vollständig sichtbar (normal)
  - 50% = halb-transparent
  - 0% = vollständig transparent (schwarz)

**Beispiel:**
```python
# Via REST API
POST /api/effects/video/add
{
  "plugin_id": "opacity",
  "config": {
    "opacity": 50.0
  }
}
```

### Transform Effect
**ID:** `transform`  
**Kategorie:** Transformation

2D/3D Transformationen (Position, Skalierung, Rotation):
- **position_x** (-2000 bis +2000 px) - Horizontale Position
- **position_y** (-2000 bis +2000 px) - Vertikale Position
- **scale_xy** (0-500%) - Symmetrische Skalierung
- **scale_x** (0-500%) - Horizontale Skalierung
- **scale_y** (0-500%) - Vertikale Skalierung
- **rotation_x** (0-360°) - 3D Rotation um X-Achse (Perspektive)
- **rotation_y** (0-360°) - 3D Rotation um Y-Achse (Perspektive)
- **rotation_z** (0-360°) - 2D Rotation (im Uhrzeigersinn)

**Beispiel:**
```python
# Via REST API - Kombinierte Transformation
POST /api/effects/video/add
{
  "plugin_id": "transform",
  "config": {
    "position_x": 100.0,
    "position_y": 50.0,
    "scale_xy": 150.0,
    "rotation_y": 30.0
  }
}
```

**Hinweise:**
- Transformationen werden in folgender Reihenfolge angewendet:
  1. Skalierung (symmetrisch + individuell kombiniert)
  2. 2D Rotation (Z-Achse)
  3. 3D Rotation (X und Y Achsen mit Perspektive)
  4. Translation (Position)
- Frame-Größe bleibt konstant (Cropping/Padding bei Skalierung)
- Bereiche außerhalb des Frames werden schwarz dargestellt

## Support

Bei Fragen oder Issues:
- GitHub Issues erstellen
- Plugin-ID und Error-Message angeben
- METADATA und PARAMETERS mitschicken
