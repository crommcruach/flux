# Plugin Template & Checklist

## Quick Reference: Plugin erstellen

### 1. Generator Plugin Template

```python
"""
[Name] Generator Plugin - [Kurzbeschreibung]
"""
import numpy as np
from plugins import PluginBase, PluginType, ParameterType


class [Name]Generator(PluginBase):
    """
    [Name] Generator - [Ausführliche Beschreibung]
    """
    
    # ========================================
    # METADATA - PFLICHT
    # ========================================
    METADATA = {
        'id': '[lowercase_id]',              # PFLICHT: Eindeutige ID (lowercase, underscore)
        'name': '[Display Name]',             # PFLICHT: Anzeigename
        'description': '[Beschreibung]',      # PFLICHT: Kurze Beschreibung
        'author': 'Flux Team',                # Optional
        'version': '1.0.0',                   # Optional
        'type': PluginType.GENERATOR,         # PFLICHT: PluginType.GENERATOR
        'category': '[Category]'              # Optional: z.B. 'Procedural', 'Patterns', 'Live Sources'
    }
    
    # ========================================
    # PARAMETERS - PFLICHT (kann leer sein)
    # ========================================
    PARAMETERS = [
        {
            'name': 'param_name',              # PFLICHT: Parameter-Name (lowercase_underscore)
            'label': 'Display Label',          # PFLICHT: Anzeigename für UI
            'type': ParameterType.FLOAT,       # PFLICHT: FLOAT, INT, BOOL, SELECT, COLOR, STRING, RANGE
            'default': 1.0,                    # PFLICHT: Default-Wert
            'min': 0.0,                        # Für FLOAT/INT/RANGE
            'max': 10.0,                       # Für FLOAT/INT/RANGE
            'step': 0.1,                       # Optional: Für FLOAT/INT
            'description': 'Beschreibung'      # Optional: Tooltip/Hilfetext
        },
        {
            'name': 'duration',                # Standard-Parameter für Playlist-Autoadvance
            'label': 'Duration (seconds)',
            'type': ParameterType.INT,
            'default': 30,
            'min': 5,
            'max': 600,
            'step': 5,
            'description': 'Playback duration in seconds (for playlist auto-advance)'
        }
    ]
    
    # ========================================
    # PFLICHT-METHODEN
    # ========================================
    
    def initialize(self, config):
        """
        Initialisiert Generator mit Parametern.
        Wird beim Laden aufgerufen.
        
        Args:
            config: Dict mit Parameter-Werten {param_name: value}
        """
        # Lade Parameter aus config mit Defaults
        # ⚠️ WICHTIG: Bei INT-Parametern explizit zu int() casten!
        self.param_name = float(config.get('param_name', 1.0))
        self.duration = int(config.get('duration', 30))
        
        # Initialisiere interne State-Variablen
        self.time = 0.0
    
    def process_frame(self, frame, **kwargs):
        """
        Generiert ein Frame.
        
        ⚠️ WICHTIG: Generatoren verwenden process_frame(), nicht generate()!
        
        Args:
            frame: Unused (generator creates new frame)
            **kwargs: Muss 'width', 'height' enthalten, optional 'time', 'frame_number', 'fps'
        
        Returns:
            numpy.ndarray: Frame als (height, width, 3) RGB Array, dtype=uint8
        """
        width = kwargs.get('width', 60)
        height = kwargs.get('height', 300)
        time = kwargs.get('time', self.time)
        
        self.time = time
        
        # Erstelle Frame (height, width, 3)
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # TODO: Zeichne auf frame
        
        return frame
    
    def update_parameter(self, name, value):
        """
        Aktualisiert einen Parameter zur Laufzeit.
        
        Args:
            name: Parameter-Name (str)
            value: Neuer Wert (Any)
        
        Returns:
            bool: True wenn Parameter existiert und aktualisiert wurde
        """
        if name == 'param_name':
            self.param_name = float(value)
            return True
        elif name == 'duration':
            self.duration = int(value)
            return True
        return False
    
    def get_parameters(self):
        """
        Gibt aktuelle Parameter-Werte zurück.
        
        Returns:
            dict: {parameter_name: current_value}
        """
        return {
            'param_name': self.param_name,
            'duration': self.duration
        }
    
    def cleanup(self):
        """
        Cleanup beim Beenden (optional).
        """
        pass
```

---

### 2. Effect Plugin Template

```python
"""
[Name] Effect Plugin - [Kurzbeschreibung]
"""
import numpy as np
import cv2
from plugins import PluginBase, PluginType, ParameterType


class [Name]Effect(PluginBase):
    """
    [Name] Effect - [Ausführliche Beschreibung]
    """
    
    METADATA = {
        'id': '[lowercase_id]',
        'name': '[Display Name]',
        'description': '[Beschreibung]',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,           # PFLICHT: PluginType.EFFECT
        'category': '[Category]'              # z.B. 'Farb-Manipulation', 'Blur/Distortion', 'Time & Motion'
    }
    
    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Stärke',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.05,
            'description': 'Effekt-Stärke'
        }
        # Optional: Add 'group': 'Group Name' to organize parameters in collapsible sections
        # Example:
        # {
        #     'name': 'color_r',
        #     'label': 'R',
        #     'type': ParameterType.FLOAT,
        #     'default': 1.0,
        #     'min': 0.0,
        #     'max': 1.0,
        #     'group': 'Color',  # Groups parameters with same group name
        #     'description': 'Red channel'
        # }
    ]
    
    def initialize(self, config):
        """Initialisiert Effect mit Parametern."""
        self.strength = config.get('strength', 1.0)
    
    def process_frame(self, frame, **kwargs):
        """
        Verarbeitet ein Frame.
        
        Args:
            frame: Input-Frame als (height, width, 3) RGB Array, dtype=uint8
            **kwargs: Zusätzliche Argumente (z.B. frame_number, time)
        
        Returns:
            numpy.ndarray: Verarbeitetes Frame (height, width, 3), dtype=uint8
        """
        # TODO: Verarbeite frame
        
        return frame
    
    def update_parameter(self, name, value):
        """Aktualisiert Parameter zur Laufzeit."""
        if name == 'strength':
            self.strength = float(value)
            return True
        return False
    
    def get_parameters(self):
        """Gibt aktuelle Parameter zurück."""
        return {'strength': self.strength}
    
    def cleanup(self):
        """Cleanup beim Beenden."""
        pass
```

---

## Checklist: Neues Plugin erstellen

### Generator Plugin:
- [ ] Datei erstellen: `src/plugins/generators/[name].py`
- [ ] Klasse: `[Name]Generator(PluginBase)`
- [ ] `METADATA` definieren mit:
  - [ ] `id` (lowercase_underscore)
  - [ ] `name` (Display Name)
  - [ ] `description`
  - [ ] `type: PluginType.GENERATOR`
  - [ ] Optional: `category`, `author`, `version`
- [ ] `PARAMETERS` definieren (Liste von Dicts)
- [ ] Methoden implementieren:
  - [ ] `initialize(self, config)`
  - [ ] `generate(self, frame_number, time, width, height, fps)`
  - [ ] `update_parameter(self, name, value)` → `return True/False`
  - [ ] `get_parameters(self)` → `return dict`
  - [ ] `cleanup(self)` (optional)
- [ ] In `src/plugins/generators/__init__.py` registrieren:
  - [ ] `from .[name] import [Name]Generator`
  - [ ] Zu `__all__` hinzufügen

### Effect Plugin:
- [ ] Datei erstellen: `src/plugins/effects/[name].py`
- [ ] Klasse: `[Name]Effect(PluginBase)`
- [ ] `METADATA` definieren mit `type: PluginType.EFFECT`
- [ ] `PARAMETERS` definieren
- [ ] Methoden implementieren:
  - [ ] `initialize(self, config)`
  - [ ] `process_frame(self, frame, **kwargs)`
  - [ ] `update_parameter(self, name, value)`
  - [ ] `get_parameters(self)`
  - [ ] `cleanup(self)` (optional)
- [ ] In `src/plugins/effects/__init__.py` registrieren

---

## Parameter Types

```python
ParameterType.FLOAT      # Slider mit float-Werten (min, max, step)
ParameterType.INT        # Slider mit int-Werten (min, max, step)
ParameterType.BOOL       # Checkbox (True/False)
ParameterType.SELECT     # Dropdown (benötigt 'options': ['opt1', 'opt2'])
ParameterType.COLOR      # Color Picker (hex string '#RRGGBB')
ParameterType.STRING     # Text Input
ParameterType.RANGE      # Dual-Slider (min, max)
```

---

## Parameter Grouping (Optional)

Parameters can be organized into collapsible groups for a cleaner UI by adding the optional `group` field.

### Benefits:
- **Cleaner Layout**: Related parameters grouped together
- **Collapsible Sections**: Users can hide/show groups
- **Better Organization**: Clear visual hierarchy
- **Backward Compatible**: Plugins without groups work as before

### Example: Transform Effect with Groups

```python
PARAMETERS = [
    # Position Group
    {
        'name': 'position_x',
        'label': 'X',
        'type': ParameterType.FLOAT,
        'default': 0.0,
        'min': -2000.0,
        'max': 2000.0,
        'group': 'Position',  # ← Optional group field
        'description': 'Horizontal position in pixels'
    },
    {
        'name': 'position_y',
        'label': 'Y',
        'type': ParameterType.FLOAT,
        'default': 0.0,
        'min': -2000.0,
        'max': 2000.0,
        'group': 'Position',  # ← Same group name
        'description': 'Vertical position in pixels'
    },
    # Scale Group
    {
        'name': 'scale_xy',
        'label': 'XY (Symmetric)',
        'type': ParameterType.FLOAT,
        'default': 100.0,
        'min': 0.0,
        'max': 500.0,
        'group': 'Scale',  # ← Different group
        'description': 'Symmetric scaling in percent'
    },
    {
        'name': 'scale_x',
        'label': 'X',
        'type': ParameterType.FLOAT,
        'default': 100.0,
        'min': 0.0,
        'max': 500.0,
        'group': 'Scale',
        'description': 'Horizontal scaling in percent'
    },
    # Ungrouped Parameter (backward compatibility)
    {
        'name': 'opacity',
        'label': 'Opacity',
        'type': ParameterType.FLOAT,
        'default': 100.0,
        'min': 0.0,
        'max': 100.0,
        # No 'group' field - renders at top level
        'description': 'Overall opacity'
    }
]
```

### UI Rendering:

Parameters with the same `group` value are rendered together in a collapsible section:

```
📐 Transform Effect
├─ Opacity: ████████████ 100%  (ungrouped - at top)
├─ 📁 Position (collapsible)
│  ├─ X: ████████ 0
│  └─ Y: ████████ 0
├─ 📁 Scale (collapsible)
│  ├─ XY (Symmetric): ████████ 100%
│  └─ X: ████████ 100%
└─ 📁 Rotation (collapsible)
   ├─ X: ████████ 0°
   ├─ Y: ████████ 0°
   └─ Z: ████████ 0°
```

### Guidelines:
- **Group Names**: Use clear, short names (e.g., 'Position', 'Scale', 'Color')
- **Label Simplification**: Within groups, labels can be shorter (e.g., 'X' instead of 'Position X')
- **Optional Field**: The `group` field is completely optional - omit it for ungrouped parameters
- **Backward Compatibility**: Existing plugins without groups continue to work unchanged

### Common Group Names:
- `Position` - X/Y/Z position parameters
- `Scale` - Scaling parameters
- `Rotation` - Rotation angles
- `Color` - Color-related parameters
- `Timing` - Duration, speed, delay
- `Advanced` - Expert-level settings

---

## Häufige Fehler

### ❌ Fehler: "Can't instantiate abstract class"
**Ursache:** Abstrakte Methoden nicht implementiert  
**Lösung:** Alle Methoden implementieren:
- `initialize(self, config)`
- `update_parameter(self, name, value)` (Singular!)
- `get_parameters(self)` (mit 's'!)
- `process_frame(self, frame, **kwargs)` für Generator UND Effect (!)

### ❌ Fehler: "implementiert keine process_frame() Methode"
**Ursache:** Generator verwendet `generate()` statt `process_frame()`  
**Lösung:** Generatoren verwenden `process_frame(frame, **kwargs)`, nicht `generate()`!  
→ Siehe Template oben für korrekte Signatur

### ❌ Fehler: "'float' object cannot be interpreted as an integer"
**Ursache:** INT-Parameter wird als float übergeben (vom Frontend-Slider oder JSON), aber in `range()` verwendet  
**Lösung:** DREIFACHER Schutz erforderlich:

1. **In `initialize()`:**
```python
self.columns = int(config.get('columns', 8))
```

2. **In `update_parameter()`:**
```python
if name == 'columns':
    self.columns = int(value)  # ⚠️ Frontend sendet oft floats!
    return True
```

3. **Als Fallback in `range()`:**
```python
for row in range(int(self.rows)):  # ⚠️ Extra Schutz!
    for col in range(int(self.columns)):
```

**Warum?** Frontend-Slider senden Parameter-Updates als float (z.B. `28.0`). Auch wenn `initialize()` int() verwendet, überschreibt `update_parameter()` den Wert später mit einem float, wenn kein int()-Cast vorhanden ist!

### ❌ Fehler: "Plugin fehlt METADATA['type']"
**Ursache:** `type` nicht gesetzt oder falscher Typ  
**Lösung:** `'type': PluginType.GENERATOR` oder `PluginType.EFFECT`

### ❌ Fehler: "Parameter benötigt 'min' und 'max'"
**Ursache:** FLOAT/INT Parameter ohne min/max  
**Lösung:** `'min': 0.0, 'max': 10.0` hinzufügen

### ❌ Fehler: Plugin wird nicht geladen
**Ursache:** Nicht in `__init__.py` registriert  
**Lösung:** Import + `__all__` erweitern

---

## Beispiel: Vollständiges Checkerboard Plugin

Siehe: `src/plugins/generators/checkerboard.py`

Key Points:
- METADATA mit `id: 'checkerboard'` und `type: PluginType.GENERATOR`
- PARAMETERS: `columns`, `rows`, `duration`
- `generate()` gibt `(height, width, 3)` uint8 Array zurück
- `update_parameter()` gibt `True` bei Erfolg zurück (wichtig!)
- `get_parameters()` gibt Dict mit aktuellen Werten zurück
- Registriert in `generators/__init__.py`

---

## Testing

```bash
# Im CLI:
> plugin reload              # Plugins neu laden
> plugin list                # Alle Plugins anzeigen
> plugin list generator      # Nur Generatoren
> plugin info [id]           # Plugin-Details
```

```python
# Im Frontend:
# Generatoren erscheinen im Sources-Tab
# Effekte erscheinen im Effects-Tab
# Per Drag & Drop in Playlist ziehen
```
