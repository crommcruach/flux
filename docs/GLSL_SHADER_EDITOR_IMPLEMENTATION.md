# GLSL / ISF Shader Editor — Implementation Plan

**Status:** Planned  
**Languages:** ISF 2.0 (Interactive Shader Format) — primary + GLSL ES 3.00 (Shadertoy-style) — import/compat  
**Architecture:** Hybrid (browser live-preview + server-side generator plugin)  

---

## Overview

Add a GLSL shader editor page to the frontend that lets users write or paste fragment shaders and run them as a live preview. Saved shaders are persisted as files and auto-registered as `PluginType.GENERATOR` plugins, feeding frames into the full existing pipeline (layers, effects, Art-Net output).

**Primary format: ISF 2.0** (Interactive Shader Format, BSD 2-Clause) — self-describing shaders with an embedded JSON header that declares all parameters (name, type, min/max/default). The header maps directly to `PluginBase.PARAMETERS`, so every ISF shader gets auto-generated sliders, color pickers, and toggles in the plugin UI with no extra code. Large community library at [editor.isf.video](https://editor.isf.video).

Also supports **Shadertoy-style raw GLSL** as an import/compatibility format — paste directly from shadertoy.com, standard `mainImage()` convention. Raw GLSL shaders only expose the base `speed`/`width`/`height` parameters (no auto-generated UI) because GLSL uniforms carry no metadata.

Format is auto-detected: if the file starts with `/*{`, it is parsed as ISF; otherwise treated as raw GLSL. The editor **opens with the ISF template by default**.

The main design goal is **write once, run everywhere**: the same shader file runs identically in the browser (WebGL2) and on the backend (ModernGL offscreen context).

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│  Browser: shader-editor.html                            │
│                                                         │
│  ┌──────────────────┐    ┌────────────────────────────┐ │
│  │  Monaco Editor   │    │  WebGL2 Canvas Preview     │ │
  │  (GLSL syntax)   │───▶│  TIME/RENDERSIZE + ISF     │ │
  │  ISF default,    │    │  uniforms; iTime shim for  │ │
  │  auto-detect fmt │    │  raw GLSL                  │ │
│  └──────────────────┘    └────────────────────────────┘ │
│           │ Save                                         │
└───────────┼─────────────────────────────────────────────┘
            │ POST /api/shaders  { name, code, format }   
            ▼
┌─────────────────────────────────────────────────────────┐
│  Backend: Flask API                                     │
│                                                         │
│  Persist → plugins/shaders/user_<name>.glsl             │
│  Parse ISF header → extract PARAMETERS automatically    │
│  Register → ShaderGenerator(glsl_path) as GENERATOR     │
└─────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│  ShaderGenerator (plugins/generators/shader.py)         │
│                                                         │
│  ModernGL offscreen context                             │
│  Full-screen quad + user fragment shader                │
│  Outputs numpy ndarray (BGR) → existing pipeline        │
└─────────────────────────────────────────────────────────┘
            │
            ▼
  LayerCompositor → EffectProcessor → MJPEG / Art-Net
```

---

## Phase 1 — Backend: ShaderGenerator Plugin

### 1.1 New file: `plugins/generators/shader.py`

A standard `PluginBase` generator that uses **ModernGL** to execute a GLSL fragment shader in a headless offscreen context and return a numpy frame.

**PARAMETERS exposed to existing plugin UI:**

| Name | Type | Default | Description |
|---|---|---|---|
| `glsl_file` | STRING | `""` | Path to `.glsl` / `.isf` file (set by API, not editable by user) |
| `speed` | FLOAT | 1.0 | Multiplier for `iTime`/`TIME` progression |
| `width` | INT | 1280 | Output width override (0 = use player resolution) |
| `height` | INT | 720 | Output height override |

For ISF shaders, **additional parameters are extracted automatically from the `INPUTS` array** in the JSON header and appended to `PARAMETERS` at load time — giving the user sliders/color pickers/toggles for every declared ISF input with no extra work.

### Format Detection & Uniform Shims

**Detection logic (both backend and frontend):**
```python
def detect_format(source: str) -> str:
    return 'isf' if source.lstrip().startswith('/*{') else 'glsl'
```

**Shadertoy GLSL shim** (prepended for raw GLSL shaders):
```glsl
#version 300 es
precision highp float;

uniform float iTime;
uniform vec2  iResolution;
uniform vec4  iMouse;
uniform int   iFrame;
uniform sampler2D iChannel0;
uniform sampler2D iChannel1;
uniform sampler2D iChannel2;
uniform sampler2D iChannel3;

out vec4 fragColor;
// mainImage() wrapper appended after user code
```

**ISF shim** (prepended for ISF shaders, after JSON header is stripped):
```glsl
#version 300 es
precision highp float;

// ISF built-in uniforms
uniform float TIME;           // seconds elapsed
uniform float TIMEDELTA;      // seconds since last frame
uniform int   FRAMEINDEX;     // frame counter
uniform vec2  RENDERSIZE;     // output resolution
uniform vec4  DATE;           // year, month, day, seconds

// User-declared INPUTS become uniforms here (injected from parsed JSON)
// e.g. uniform float speed;  uniform vec4 color;

out vec4 gl_FragColor;
```

After the ISF header is stripped and the shim is injected, the remaining GLSL body is compiled normally.

### ISF Parameter Mapping

| ISF input TYPE | PluginBase ParameterType | Notes |
|---|---|---|
| `float` | `FLOAT` | min/max/default from header |
| `long` (integer) | `INT` | |
| `bool` | `BOOL` | |
| `color` | `COLOR` | RGBA |
| `point2D` | Two FLOATs (x, y) | Expanded into two sliders |
| `image` | Future — skipped v1 | Black texture bound |
| `audioFFT` | Future — skipped v1 | Black texture bound |

**Key implementation points:**
- Create ModernGL context once in `initialize()`, recreate on resolution change
- Detect format, strip ISF JSON header, inject appropriate shim, compile
- For ISF: parse JSON header with `json.loads()`, build `PARAMETERS` list dynamically
- Render full-screen triangle each frame, read pixels with `fbo.read()`, reshape to numpy
- Pass `iTime`/`TIME` as `self.time` (incremented by `delta_time` each frame)
- Catch GLSL compile/link errors → return solid red error frame with text via `cv2.putText`

### 1.2 New dependency

```
moderngl>=5.10.0
```

Add to `requirements.txt`. ModernGL creates an offscreen OpenGL context via WGL (Windows), EGL (Linux/headless), or CGL (macOS) — no display window needed.

---

## Phase 2 — Backend: Shader API

### 2.1 New file: `src/modules/api/shaders.py`

REST endpoints for CRUD on user shaders.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/shaders` | List all saved shaders (id, name, created_at) |
| `POST` | `/api/shaders` | Create new shader → save `.glsl`, register plugin |
| `GET` | `/api/shaders/<id>` | Return shader metadata + full GLSL source |
| `PUT` | `/api/shaders/<id>` | Update GLSL source (hot-reload running instance) |
| `DELETE` | `/api/shaders/<id>` | Delete `.glsl` file, unregister plugin |

### 2.2 Storage

Shaders saved to: `plugins/shaders/user_<slug>_<timestamp>.glsl`  
ISF shaders use the same `.glsl` extension — format is always detected from file content, not extension.  
Metadata (name, id, file path, format, created_at) stored in `session_state.json` under key `shaders`.

### 2.3 Hot Reload

On `PUT`, the running `ShaderGenerator` instance recompiles the shader program in-place without recreating the ModernGL context, keeping `iTime` running uninterrupted.

---

## Phase 3 — Frontend: Shader Editor Page

### 3.1 New file: `frontend/shader-editor.html`

Standalone page linked from the main nav, same Bootstrap 5 + vanilla JS pattern as existing pages.

**Layout:**

```
┌──────────────────────────────────────────────────────┐
│  Nav: [← Back]  Shader Editor   [shader name input]  │
├─────────────────────────┬────────────────────────────┤
│                         │                            │
│   Monaco Editor         │   WebGL2 Preview Canvas    │
│   (GLSL syntax +        │   (live, auto-refreshes    │
│    error markers)       │    on each keystroke       │
│                         │    after 500ms debounce)   │
│                         │                            │
├─────────────────────────┴────────────────────────────┤
│  [▶ Run]  [💾 Save as Plugin]  [📋 Load Example]     │
│  Error console (red, shows GLSL compile errors)      │
└──────────────────────────────────────────────────────┘
```

### 3.2 New file: `frontend/js/shader-editor.js`

**WebGL2 setup:**
- Create `WebGL2RenderingContext` on the preview canvas
- Full-screen triangle (single tri, no quad) for maximum simplicity
- Uniform locations: `iTime`, `iResolution`, `iMouse`, `iFrame`
- `requestAnimationFrame` loop, starts/stops on Run/Stop

**Dual-format shader runner** (same detection logic as backend):
- Detect format from source: `/*{` prefix = ISF, otherwise Shadertoy GLSL
- **GLSL mode:** prepend Shadertoy uniform shim, auto-wrap `mainImage` → `main()`
- **ISF mode:** strip JSON header, parse `INPUTS`, inject ISF uniform shim + user uniform declarations, render
- Show compile errors from `gl.getShaderInfoLog()` in the error console with line numbers
- ISF mode: display parsed parameters in a live panel next to the canvas (sliders/color pickers), bound to WebGL uniforms in real time

**Monaco Editor integration:**
- Load Monaco from CDN (`https://cdn.jsdelivr.net/npm/monaco-editor`) — no npm build step
- Use built-in `glsl` language mode (Monaco supports it)
- Wire `onDidChangeModelContent` → debounced recompile (500ms)

**Save flow:**
1. User clicks "Save as Plugin", enters a name
2. `POST /api/shaders` with `{ name, code }`
3. Backend saves + registers → responds with new plugin id
4. Show success toast: "Shader 'my_shader' added as generator plugin"

### 3.3 Example shaders (built-in load menu)

ISF examples are listed first and the editor opens with the ISF template. Shadertoy GLSL examples are available under a secondary "Import from Shadertoy" group.

**ISF examples (primary):**
- **ISF template** *(default on open)* — blank template with header scaffold and inline comments explaining every field; starts with a single `float speed` input so the user immediately sees an auto-generated slider
- **ISF Color Gradient** — minimal ISF with `float` + `color` INPUTS, demonstrates the full param-to-slider pipeline
- **ISF Kaleidoscope** — shows `long` (integer) and `bool` inputs
- **ISF Plasma** — animated pattern, good starting point for customisation

**Shadertoy GLSL examples (import/compat):**
- **Classic plasma** — simple `sin()` color field, ~10 lines, explains `iTime`/`iResolution`; note shown: *"tip: convert to ISF to get UI controls"*
- **Raymarched sphere** — basic SDF raymarcher, shows 3D capability
- **Audio reactive bars** — placeholder that explains `iChannel0` (future texture input)

---

## Phase 4 — Navigation Integration

Add "Shader Editor" link to the main nav in relevant HTML files.  
When a saved shader plugin is selected in the plugin picker, show an "Edit Shader" button that opens `shader-editor.html?id=<shader_id>` pre-loaded with that shader's source.

---

## File Map

```
plugins/
  generators/
    shader.py               ← NEW: ShaderGenerator plugin (ModernGL, GLSL + ISF)
  shaders/                  ← NEW: directory for user shader files
    examples/
      _isf_template.glsl    ← ISF blank template (editor default)
      gradient.glsl         ← ISF example with INPUTS (float + color)
      kaleidoscope.glsl     ← ISF example (long + bool inputs)
      isf_plasma.glsl       ← ISF animated pattern
      glsl_plasma.glsl      ← Shadertoy GLSL example
      glsl_sphere.glsl      ← Raymarched sphere example

src/
  modules/
    api/
      shaders.py            ← NEW: CRUD REST API for shaders
    shaders/
      isf_parser.py         ← NEW: parse ISF JSON header → PARAMETERS list
      shader_compiler.py    ← NEW: format detection + shim injection (shared by backend + tests)

frontend/
  shader-editor.html        ← NEW: editor page
  js/
    shader-editor.js        ← NEW: WebGL2 preview + Monaco + ISF param panel
```

---

## Dependencies

| Package | Version | Purpose |
|---|---|---|
| `moderngl` | ≥5.10.0 | Headless OpenGL context for server-side shader execution |

No new frontend dependencies — Monaco loads from CDN, WebGL2 is native browser API, JSON parsing is built-in.  
ISF parsing is pure Python (`json` stdlib) — no additional packages required.

---

## Implementation Order

1. **`src/modules/shaders/shader_compiler.py`** — format detection + shim injection utility  
   Validate: unit tests for GLSL and ISF detection, shim output correct
2. **`src/modules/shaders/isf_parser.py`** — ISF JSON header parser → `PARAMETERS` list  
   Validate: parse example ISF headers, confirm correct ParameterType mapping
3. **`plugins/generators/shader.py`** — ShaderGenerator with ModernGL (GLSL + ISF)  
   Validate: run hardcoded GLSL and ISF test shaders, confirm numpy frame output
4. **`src/modules/api/shaders.py`** — REST endpoints  
   Validate: `POST` saves file, plugin appears in `/api/plugins`, ISF inputs appear as parameters
5. **`frontend/shader-editor.html` + `shader-editor.js`** — editor + WebGL2 preview + ISF param panel  
   Validate: GLSL live preview works; paste ISF shader → param sliders auto-appear
6. **Save → Load flow** — save both formats, reload, shaders appear in picker with correct parameters  
7. **Nav integration** — link from main UI, "Edit Shader" button on saved shaders

---

## Known Limitations (v1 scope)

**Shadertoy GLSL:**
- **`iChannel0`–`iChannel3` (texture inputs):** Not implemented in v1. Shaders that sample `iChannel` will compile but receive a black texture. Phase 2 feature.
- **`iDate`, `iSampleRate`:** Not implemented. Low value for typical use cases.
- **Multi-pass / Buffer A/B/C/D:** Not in scope v1.

**ISF:**
- **`image` input type:** Not implemented in v1 — black texture bound.
- **`audioFFT` / `audio` input type:** Not implemented in v1 — black texture bound. Phase 2 addition once the app's existing audio analysis pipeline is wired to a texture.
- **`point2D` input type:** Expanded into two separate FLOAT sliders in v1 (no 2D drag widget).
- **ISF multi-pass (`PASSES` array with `TARGET`):** Not implemented in v1. Single-pass only.
- **`PERSISTENT` buffers:** Not in scope v1.

**Both formats:**
- **Compute shaders:** Not in scope — fragment shaders only.
- **SPIR-V / Vulkan:** Not in scope. GLSL ES 3.00 only.

---

## Shadertoy Compatibility Notes

Most Shadertoy shaders will work without modification. Known differences:

| Shadertoy | This implementation | Action needed |
|---|---|---|
| `mainImage(out vec4 fragColor, in vec2 fragCoord)` | Wrapped automatically | None |
| `#version` pragma | Stripped/replaced | None — auto-inserted |
| `iChannelResolution[N]` | Not implemented | Manual removal |
| `iChannelTime[N]` | Not implemented | Manual removal |
| Multi-pass / Buffer A/B/C/D | Not implemented | Out of scope v1 |
| `precision` specifiers | Pass-through | OK |

---

## ISF Compatibility Notes

ISF 2.0 shaders from [editor.isf.video](https://editor.isf.video) will largely work. Known differences:

| ISF Feature | This implementation | Action needed |
|---|---|---|
| `float`, `long`, `bool`, `color` inputs | Fully supported | None |
| `point2D` input | Two separate sliders | None (functional, less elegant) |
| `image` input | Black texture bound | None in v1 |
| `audioFFT` / `audio` input | Black texture bound | None in v1 |
| `PASSES` (multi-pass) | Not implemented | Out of scope v1 |
| `PERSISTENT` buffers | Not implemented | Out of scope v1 |
| `DESCRIPTION`, `CREDIT`, `CATEGORIES` metadata | Stored in session_state, shown in UI | None |
| `TIME`, `TIMEDELTA`, `FRAMEINDEX`, `RENDERSIZE`, `DATE` built-ins | All implemented | None |
| ISF `gl_FragCoord` / `isf_FragNormCoord` | `isf_FragNormCoord` added to shim | None |

**ISF vs Shadertoy uniform name differences** (handled automatically by format detection):

| Concept | Shadertoy | ISF |
|---|---|---|
| Elapsed time | `iTime` | `TIME` |
| Resolution | `iResolution` | `RENDERSIZE` |
| Frame counter | `iFrame` | `FRAMEINDEX` |
| Time delta | — | `TIMEDELTA` |

---

*Created: 2026-03-16 — Updated: 2026-03-16 (added ISF 2.0 support)*
