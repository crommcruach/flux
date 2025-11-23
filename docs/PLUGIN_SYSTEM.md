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

### Alle Plugins auflisten

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
- `src/scripts/rainbow_wave.py` - Generator-ähnlich (GENERATOR Vorlage)

## Support

Bei Fragen oder Issues:
- GitHub Issues erstellen
- Plugin-ID und Error-Message angeben
- METADATA und PARAMETERS mitschicken
