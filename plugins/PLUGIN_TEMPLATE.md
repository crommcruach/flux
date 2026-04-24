# Plugin Template & Developer Guide

> **Pipeline Overview**  
> Flux runs a **100% GPU rendering pipeline** powered by [wgpu](https://wgpu.dev/) and WGSL shaders.  
> Every plugin that touches pixels **must** implement `get_shader()` + `get_uniforms()`.  
> `process_frame()` is a **stub only** — it must return the frame unchanged.  
> Never add CPU pixel-processing code inside a GPU plugin.

---

## Architecture

```
VideoSource / GeneratorPlugin
       │  (numpy BGR upload via GPUUploader ~5 ms)
       ▼
  GPU Texture (rgba32float, wgpu)
       │
  ┌────▼──────────────────────────────────┐
  │  Effect chain  (ping-pong textures)   │
  │  plugin.get_shader() → WGSL source    │
  │  plugin.get_uniforms() → uniform dict │
  │  renderer.render(wgsl, target, ...)   │
  └────────────────────────────────────────┘
       │
  Composite GPU Texture
       │  (SSBO compute readback ~21 ms at 1080p, only when Art-Net/recording active)
       ▼
  numpy BGR  →  Art-Net / Recording / Preview JPEG
```

**Key rules:**
- One WGSL shader file per plugin, stored in `src/modules/gpu/shaders/`
- `get_shader()` reads the file **once** and caches it at class level (`_shader_src`)
- `get_uniforms()` is called **every frame** — keep it fast (pure math only)
- `process_frame()` **must** return `frame` unchanged — never manipulate pixels here
- `is_noop()` is optional but recommended to skip no-op passes

---

## Plugin Types at a Glance

| Type | Folder | When to use |
|---|---|---|
| `PluginType.GENERATOR` | `plugins/generators/` | Procedural content — creates frames from scratch via WGSL shader |
| `PluginType.EFFECT` | `plugins/effects/` | Post-processing — reads one input texture, writes a modified output |
| `PluginType.TRANSITION` | `plugins/transitions/` | Clip change — blends two GPU textures (A outgoing, B incoming) |

---

## 1. Effect Plugin (GPU-native)

Effects are the most common plugin type. They receive one GPU texture (the current composite) and produce a modified texture via a WGSL fragment shader. No CPU round-trip.

### Python side — `plugins/effects/my_effect.py`

```python
"""
[Name] Effect Plugin — [short description]
"""
import os
from plugins import PluginBase, PluginType, ParameterType

# Path to the WGSL shader file (relative from this file)
_SHADER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'my_effect.wgsl'
)


class [Name]Effect(PluginBase):

    # Shader source cached at class level — loaded once, reused every frame
    _shader_src: str | None = None

    METADATA = {
        'id': 'my_effect',            # unique lowercase_underscore ID
        'name': 'My Effect',          # display name shown in UI
        'description': '...',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.EFFECT,
        'category': 'Farb-Manipulation'  # UI category grouping
    }

    PARAMETERS = [
        {
            'name': 'strength',
            'label': 'Strength',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.0,
            'max': 1.0,
            'step': 0.01,
            'description': 'Effect intensity'
        }
        # Add 'group': 'Section Name' to any parameter to create collapsible UI sections
    ]

    def initialize(self, config):
        # Use self._get_param_value() for parameters that may be range-slider dicts
        self.strength = float(self._get_param_value('strength', 1.0))

    def process_frame(self, frame, **kwargs):
        """GPU-native plugin — rendered via WGSL shader. STUB — never manipulate pixels here."""
        return frame

    # ── GPU shader interface (called every frame, keep fast) ──────────────

    def get_shader(self) -> str:
        """Return WGSL source. Read from disk once, cache at class level."""
        if [Name]Effect._shader_src is None:
            with open(_SHADER_PATH, 'r', encoding='utf-8') as f:
                [Name]Effect._shader_src = f.read()
        return [Name]Effect._shader_src

    def get_uniforms(self, **kwargs) -> dict:
        """Return uniform values for this frame. kwargs may include frame_w, frame_h."""
        return {'strength': float(self.strength)}

    def is_noop(self) -> bool:
        """Optional — return True when the effect does nothing (skips shader pass)."""
        return self.strength == 0.0

    def update_parameter(self, name, value):
        # Always strip range-slider metadata before casting
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'strength':
            self.strength = float(value)
            return True
        return False

    def get_parameters(self) -> dict:
        return {'strength': self.strength}
```

### WGSL side — `src/modules/gpu/shaders/my_effect.wgsl`

```wgsl
// my_effect.wgsl — short description of what this shader does.
//
// Uniforms (u.data slots):
//   [0].x  strength  (f32, 0..1)
//
// Textures: binding 1 = inputTexture (rgba32float)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex0: texture_2d<f32>;
@group(0) @binding(2) var samp0: sampler;

// ── Standard full-screen triangle vertex shader (copy this verbatim) ──────
struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(2.0, 1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}
// ──────────────────────────────────────────────────────────────────────────

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let strength = u.data[0].x;

    let src = textureSample(tex0, samp0, in.uv);

    // TODO: your pixel math here
    // All values are linear 0..1 float.  Output alpha should normally be preserved.
    let result = mix(src.rgb, 1.0 - src.rgb, strength);  // example: invert by 'strength'

    return vec4<f32>(result, src.a);
}
```

### Uniform packing rules

The renderer packs the `uniforms` dict into a flat `array<vec4<f32>, 16>` (256 bytes total, 64 floats). Values are packed in dict iteration order:

| Python value | WGSL access | Notes |
|---|---|---|
| `float` | `u.data[N].x/y/z/w` | Stored as f32 |
| `int` | `bitcast<i32>(u.data[N].x)` | Bitcast required in WGSL |
| `bool` | `bitcast<i32>(u.data[N].x) != 0` | Pass as `int(bool_val)` |
| `tuple(a,b)` | `u.data[N].xy` | Each element fills next slot |

Example — packing for `hue_rotate`:
```python
def get_uniforms(self, **kwargs):
    return {'hue_shift': float(self.hue_shift)}
# → u.data[0].x = hue_shift
```

Example — packing for `transform`:
```python
def get_uniforms(self, **kwargs):
    return {
        'anchor':    (self.anchor_x / 100.0, self.anchor_y / 100.0),  # slots 0,1
        'scale':     (sx, sy),                                          # slots 2,3
        'translate': (tx, ty),                                          # slots 4,5
        'rotation':  math.radians(self.rotation_z),                     # slot 6
    }
# → u.data[0] = vec4(anchor_x, anchor_y, scale_x, scale_y)
# → u.data[1] = vec4(translate_x, translate_y, rotation, 0)
```

---

## 2. Generator Plugin (GPU-native)

Generators create frames from scratch. They still have a `process_frame()` CPU stub for fallback registration, but all real rendering happens in the WGSL shader. The shader receives **no** input texture — it generates pixels purely from uniforms and `time`.

### Python side — `plugins/generators/my_generator.py`

```python
"""
[Name] Generator Plugin — procedural content
"""
import os
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'gen_my_generator.wgsl'
)


class [Name]Generator(PluginBase):

    _shader_src: str | None = None  # class-level cache
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
    
    _shader_src: str | None = None  # class-level cache — loaded once

    METADATA = {
        'id': 'my_generator',
        'name': 'My Generator',
        'description': '...',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.GENERATOR,
        'category': 'Procedural'
    }

    PARAMETERS = [
        {
            'name': 'speed',
            'label': 'Speed',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 10.0,
            'step': 0.1,
            'description': 'Animation speed'
        },
        {
            'name': 'duration',
            'label': 'Duration (s)',
            'type': ParameterType.INT,
            'default': 10,
            'min': 1,
            'max': 60,
            'step': 1,
            'description': 'Playback duration for playlist auto-advance'
        }
    ]

    def initialize(self, config):
        self.speed = float(config.get('speed', 1.0))
        self.duration = int(config.get('duration', 10))
        self.time = 0.0

    def process_frame(self, frame, **kwargs):
        """GPU-native generator — rendered via WGSL shader. STUB ONLY."""
        return frame

    # ── GPU shader interface ──────────────────────────────────────────────

    def get_shader(self) -> str:
        if [Name]Generator._shader_src is None:
            with open(_SHADER_PATH, 'r', encoding='utf-8') as f:
                [Name]Generator._shader_src = f.read()
        return [Name]Generator._shader_src

    def get_uniforms(self, **kwargs) -> dict:
        """Called every frame. Pass time + canvas size + your parameters."""
        return {
            'time':   float(kwargs.get('time', 0.0)),
            'cw':     float(kwargs.get('width', 1920)),
            'ch':     float(kwargs.get('height', 1080)),
            'speed':  float(self.speed),
        }

    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'speed':
            self.speed = float(value)
            return True
        elif name == 'duration':
            self.duration = int(value)
            return True
        return False

    def get_parameters(self) -> dict:
        return {'speed': self.speed, 'duration': self.duration}
```

### WGSL side — `src/modules/gpu/shaders/gen_my_generator.wgsl`

Generator shaders receive **no** input texture. They produce pixels from uniforms alone.

```wgsl
// gen_my_generator.wgsl — procedural frame generator.
//
// Uniforms (u.data slots):
//   [0].x  time   (f32, seconds)
//   [0].y  cw     (f32, canvas width px)
//   [0].z  ch     (f32, canvas height px)
//   [0].w  speed  (f32)
//
// No textures — generator creates pixels from scratch.

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0), vec2<f32>(2.0, 1.0), vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let t     = u.data[0].x;
    let cw    = u.data[0].y;
    let ch    = u.data[0].z;
    let speed = u.data[0].w;

    // Pixel position in canvas space
    let px = in.uv * vec2<f32>(cw, ch);

    // TODO: generate your colour here
    let col = vec3<f32>(in.uv.x, in.uv.y, fract(t * speed));

    return vec4<f32>(col, 1.0);
}
```

> **Real example:** `plugins/generators/rainbow_wave.py` + `src/modules/gpu/shaders/gen_rainbow.wgsl`

---

## 3. Transition Plugin (GPU two-frame blend)

Transitions are triggered on clip changes. The system stores the outgoing frame (A) in a GPU buffer and calls the transition shader every frame with both A and B (incoming) textures until `progress` reaches 1.0.

### How transitions are wired

```
clip changes
    → GPUTransitionRenderer.store_gpu_frame(outgoing)   (GPU→GPU copy, no CPU)
    → each frame: render_transition_gpu(wgsl_src, incoming, uniforms)
                   ├─ binding 1 = tex_a (outgoing, frozen or live)
                   └─ binding 3 = tex_b (incoming composite)
    → progress 0.0→1.0 over transition_duration seconds (eased in Python)
    → output GPUFrame replaces composite for that frame
```

### Python side — `plugins/transitions/my_transition.py`

```python
"""
[Name] Transition Plugin — [description]
"""
import os
from plugins import PluginBase, PluginType, ParameterType

_SHADER_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'my_transition.wgsl'
)


class [Name]Transition(PluginBase):

    _shader_src: str | None = None

    METADATA = {
        'id': 'my_transition',
        'name': 'My Transition',
        'description': '...',
        'author': 'Flux Team',
        'version': '1.0.0',
        'type': PluginType.TRANSITION,
    }

    PARAMETERS = [
        {
            'name': 'duration',
            'label': 'Duration (s)',
            'type': ParameterType.FLOAT,
            'default': 1.0,
            'min': 0.1,
            'max': 5.0,
            'step': 0.1,
            'description': 'Transition duration in seconds'
        }
    ]

    def initialize(self, config):
        self.duration = float(config.get('duration', 1.0))

    def process_frame(self, frame, **kwargs):
        """Stub — transitions are GPU-only via get_shader() / get_uniforms()."""
        return frame

    # ── GPU shader interface ──────────────────────────────────────────────

    def get_shader(self) -> str:
        if [Name]Transition._shader_src is None:
            with open(_SHADER_PATH, 'r', encoding='utf-8') as f:
                [Name]Transition._shader_src = f.read()
        return [Name]Transition._shader_src

    def get_uniforms(self, **kwargs) -> dict:
        """
        progress: float 0..1 (pre-eased by the player before calling here).
        The shader receives it directly — no further easing needed in WGSL.
        """
        progress = float(kwargs.get('progress', 0.0))
        return {'progress': progress}

    def update_parameter(self, name, value):
        if isinstance(value, dict) and '_value' in value:
            value = value['_value']
        if name == 'duration':
            self.duration = float(value)
            return True
        return False

    def get_parameters(self) -> dict:
        return {'duration': self.duration}
```

### WGSL side — `src/modules/gpu/shaders/my_transition.wgsl`

Transition shaders always receive **two** textures:
- `binding 1` / `samp_a` = outgoing frame (A)
- `binding 3` / `samp_b` = incoming frame (B)

```wgsl
// my_transition.wgsl — [description]
// progress 0.0 = 100% A (outgoing), 1.0 = 100% B (incoming)
//
// Uniforms (u.data slots):
//   [0].x  progress  (f32, 0..1, pre-eased)
//
// Textures:
//   binding 1 = tex_a (outgoing)
//   binding 3 = tex_b (incoming)

struct Uniforms { data: array<vec4<f32>, 16> }
@group(0) @binding(0) var<uniform> u: Uniforms;
@group(0) @binding(1) var tex_a: texture_2d<f32>;
@group(0) @binding(2) var samp_a: sampler;
@group(0) @binding(3) var tex_b: texture_2d<f32>;
@group(0) @binding(4) var samp_b: sampler;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var pos = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0), vec2<f32>(2.0, 1.0), vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(pos[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    let progress = u.data[0].x;
    let ca = textureSample(tex_a, samp_a, in.uv);
    let cb = textureSample(tex_b, samp_b, in.uv);

    // TODO: your blend math here.
    // Simple crossfade example:
    return mix(ca, cb, progress);
}
```

> **Real example:** `src/modules/gpu/shaders/fade_transition.wgsl` (crossfade)

### Transition ideas

| Effect | WGSL technique |
|---|---|
| Crossfade | `mix(ca, cb, progress)` |
| Wipe left→right | `select(ca, cb, in.uv.x < progress)` |
| Wipe with soft edge | `smoothstep(progress - 0.05, progress + 0.05, in.uv.x)` |
| Zoom dissolve | Scale UVs of A outward while fading in B |
| Flash | Add `vec4(1.0)` at `progress ≈ 0.5`, fade both sides |
| Luma key | Replace A pixels darker than threshold with B |

---

## 4. Existing GPU Effects — Reference

| Plugin | File | Shader | What it does |
|---|---|---|---|
| `hue_rotate` | `effects/hue_rotate.py` | `hue_rotate.wgsl` | RGB→HSV, shift hue, HSV→RGB |
| `brightness_contrast` | `effects/brightness_contrast.py` | `brightness_contrast.wgsl` | `clamp(contrast * src + brightness)` |
| `colorize` | `effects/colorize.py` | `colorize.wgsl` | Replace hue+sat, keep luminance |
| `transform` | `effects/transform.py` | `transform.wgsl` | Scale + translate + Z-rotate (anchor-based) |
| `blend_mode` | `effects/blend_mode.py` | `blend_mode.wgsl` | 14 blend modes against solid colour |
| `rainbow_wave` | `generators/rainbow_wave.py` | `gen_rainbow.wgsl` | Scrolling HSV gradient |
| `plasma` | `generators/plasma.py` | `gen_plasma.wgsl` | Classic plasma sin-wave pattern |
| `fire` | `generators/fire.py` | `gen_fire.wgsl` | Animated fire simulation |
| fade | _(built-in)_ | `fade_transition.wgsl` | `mix(A, B, progress)` crossfade |

---

## 5. Parameter Types Reference

```python
ParameterType.FLOAT      # Float slider (requires min, max, step)
ParameterType.INT        # Integer slider (requires min, max, step)
ParameterType.BOOL       # Checkbox (True/False)
ParameterType.SELECT     # Dropdown — add 'options': ['opt1', 'opt2']
ParameterType.COLOR      # Color picker — value is '#RRGGBB' hex string
ParameterType.STRING     # Free text input
ParameterType.RANGE      # Dual-handle slider (min, max)
```

### Parameter grouping

Add `'group': 'Section Name'` to any parameter to create collapsible UI sections:

```python
{'name': 'scale_x', 'label': 'X', 'type': ParameterType.FLOAT,
 'default': 100.0, 'min': 0.0, 'max': 500.0, 'group': 'Scale'},
{'name': 'scale_y', 'label': 'Y', 'type': ParameterType.FLOAT,
 'default': 100.0, 'min': 0.0, 'max': 500.0, 'group': 'Scale'},
```

Common group names: `Position`, `Scale`, `Rotation`, `Anchor`, `Color`, `Timing`, `Advanced`

---

## 6. Checklist

### Effect or Generator:
- [ ] Create `plugins/effects/[name].py` or `plugins/generators/[name].py`
- [ ] Create `src/modules/gpu/shaders/[name].wgsl` (or `gen_[name].wgsl`)
- [ ] METADATA: `id`, `name`, `type`, optional `category`
- [ ] PARAMETERS list (can be empty `[]`)
- [ ] `initialize(self, config)` — load params with defaults
- [ ] `process_frame(self, frame, **kwargs)` — **STUB, return frame unchanged**
- [ ] `get_shader(self)` — read file once, cache at class level
- [ ] `get_uniforms(self, **kwargs)` — return `{name: value}` dict, pure math only
- [ ] `update_parameter(self, name, value)` — strip range metadata, cast types
- [ ] `get_parameters(self)` — return current values dict
- [ ] Optional: `is_noop(self)` — return True when shader would be identity pass
- [ ] Register in `plugins/effects/__init__.py` or `plugins/generators/__init__.py`

### Transition:
- [ ] Create `plugins/transitions/[name].py`
- [ ] Create `src/modules/gpu/shaders/[name].wgsl`
- [ ] METADATA: `type: PluginType.TRANSITION`
- [ ] `get_shader()` and `get_uniforms(progress=...)` implemented
- [ ] WGSL declares **two** textures (bindings 1+3)
- [ ] Register in `plugins/transitions/__init__.py`

---

## 7. Common Mistakes

### ❌ Adding CPU pixel processing to `process_frame()`
`process_frame()` is a stub. **Never** use `cv2`, `numpy` pixel ops, or any frame manipulation here. The shader does all the work.

### ❌ Reading the shader file every frame
Cache at class level with `_shader_src: str | None = None`. Reading from disk every frame stalls the render loop.

### ❌ INT parameter cast missing in `update_parameter()`
Frontend sliders send `28.0` (float) even for INT parameters. Always cast:
```python
if name == 'columns':
    self.columns = int(value)   # not just float(value)!
```
And in `initialize()`: `self.columns = int(config.get('columns', 8))`

### ❌ Forgetting range-slider metadata stripping
The triple-slider widget sends `{'_value': 5.0, '_rangeMin': 0, '_rangeMax': 10}`. Use `self._get_param_value('param', default)` in `initialize()`, or strip manually in `update_parameter()`:
```python
if isinstance(value, dict) and '_value' in value:
    value = value['_value']
```

### ❌ Wrong uniform slot in WGSL
The renderer packs all values sequentially into `array<vec4<f32>, 16>`. A `tuple(a,b)` occupies 2 slots. Track your slot offsets carefully:
```python
# Python:                               # WGSL:
{'anchor': (ax, ay), 'scale': (sx, sy)} # data[0] = vec4(ax, ay, sx, sy)
{'translate': (tx, ty), 'rot': r}       # data[1] = vec4(tx, ty, r, 0)
```

### ❌ Transition WGSL with only one texture binding
Transitions require **two** texture+sampler pairs: bindings 1+2 for A, bindings 3+4 for B. See the template above.

---

## 8. Testing

```bash
# In the CLI:
plugin reload              # hot-reload all plugins
plugin list                # list all registered plugins
plugin list effect         # filter by type
plugin info hue_rotate     # show metadata + parameters for one plugin
```
