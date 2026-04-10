# GPU Pipeline Redesign — Implementation Plan

**Status:** Planned  
**Decision Date:** 2026-03-23  
**Priority:** Critical — replaces CPU frame pipeline  

---

## Design Constraints

- **No backwards compatibility.** The CPU path is removed entirely. No fallbacks, no `if gpu_available` branches.  
- **No CUDA / CuPy.** GLSL via ModernGL only — works on AMD, NVIDIA, Intel, any OpenGL 3.3+ GPU.  
- **No FFmpeg at runtime.** Frame source stays numpy memmap (already implemented, keep as-is).  
- **No frontend changes.** API contracts, session state, playlist — all unchanged.  
- **No Art-Net protocol changes.** UDP output stays. Only the pixel sampling step moves.
- **No deprecated / disabled code.** When old code is replaced, move it wholesale to `archive/legacy_cpu_pipeline.py` (one file per phase), then delete it from its original location. Never comment out, `# TODO: remove`, or leave dead code in place. The archive file is reference-only — never imported. If the old code has no value as reference, delete it outright instead of archiving.
- **Write tests when needed.** For non-trivial GPU functions (upload/download roundtrip, blend weight correctness, texture pool acquire/release, pixel sampling accuracy) create standalone test scripts in `tests/gpu/`. Tests are plain Python — no test framework required. Run them manually to verify before integrating.
- **Ask before deciding.** If anything is ambiguous — API shape, shader behavior at edge cases, how a component integrates with existing code — stop and ask. Do not guess on design decisions that affect the architecture.

---

## Why This Is Necessary

At 1920×1080 every frame is 6 MB. CPU memory bandwidth is ~50 GB/s. Theoretical minimum per operation:

| Operation | CPU minimum | GPU target |
|---|---|---|
| Transform (resize + placement) | ~3 ms | ~0.2 ms |
| Alpha blend (2 layers) | ~4 ms | ~0.3 ms |
| Blur (Gaussian, r=15) | ~12 ms | ~0.3 ms |
| Full pipeline (3 layers, 3 effects) | ~35–50 ms | ~3–6 ms |

GPU memory bandwidth is 200–500 GB/s (6–15×). Every pixel is processed in parallel. There is no micro-optimization on the CPU path that closes this gap.

---

## Architecture Overview

```
Memmap (.npy)
    │
    ▼
GPU Upload (numpy → GL texture, once per frame)  ~0.5 ms
    │
    ▼
Layer Stack (N layers, each a texture)
    │  ┌─────────────────────────────────────────────┐
    │  │  Per Layer:                                 │
    │  │   1. Source texture (video or generator)    │
    │  │   2. Effect chain (N shader passes)         │
    │  │   3. Blend into composite FBO               │
    │  └─────────────────────────────────────────────┘
    │
    ▼
Composite FBO (single framebuffer, accumulated result)
    │
    ├──▶ Display Output (FBO → OpenCV window via PBO readback)
    │
    ├──▶ Virtual Output / MJPEG Preview (FBO → numpy via PBO)  ~0.5 ms
    │
    └──▶ Art-Net Pixel Sampling
             GPU texture → sample pixel coords → numpy → UDP  ~0.5 ms
```

Everything between Upload and Readback stays on the GPU. No intermediate numpy allocations.

---

## Module Structure

```
src/modules/gpu/
├── context.py          # ModernGL headless context singleton
├── texture_pool.py     # Reusable texture/FBO allocation
├── renderer.py         # Full-screen quad renderer (core of all passes)
├── frame.py            # GPUFrame — thin wrapper: upload/download/sample
└── shaders/
    ├── passthrough.vert         # Shared vertex shader (all passes)
    ├── passthrough.frag         # Identity (texture copy)
    ├── blend.frag               # All blend modes in one shader (uniform mode)
    ├── transform.frag           # Scale, position, rotation in one pass
    ├── color.frag               # Brightness, hue, saturation, contrast
    ├── blur_h.frag              # Gauss horizontal (separable)
    ├── blur_v.frag              # Gauss vertical (separable)
    └── [future effects...]
```

---

## Phase 1 — Fully Working Player (GPU foundation + pipeline + readback)

**Deliverable:** After this phase the player works end-to-end on the GPU pipeline:

- Add clip(s) to a playlist, press play — correct output on display, Art-Net, and preview
- **Autoplay** — playlist advances to next clip when current ends (`PlaylistManager.autoplay`)  
- **Loop playlist** — playlist wraps back to index 0 (`PlaylistManager.loop_playlist`)  
- **Transport** — per-clip speed, reverse, bounce/repeat/play_once/random, paused, loop_count, position scrub all work. The transport plugin runs CPU-side before GPU upload — it selects which frame index to fetch from memmap. No change to transport logic, no GPU migration in Phase 1.
- No rendering effects yet — passthrough only (transform, color, blur are Phase 2)

**Key point on autoplay / loop / transport:** These all live above the GPU layer. `PlaylistManager` and the transport plugin drive _which_ memmap frame gets fetched. The GPU pipeline only changes _what happens after_ the frame is fetched. All three work in Phase 1 with zero changes to their own code.

**Target: 3 days**

### `src/modules/gpu/context.py`

Single ModernGL headless context shared by all pipeline stages.

```python
import moderngl

_ctx = None

def get_context() -> moderngl.Context:
    global _ctx
    if _ctx is None:
        _ctx = moderngl.create_standalone_context()
    return _ctx

def destroy_context():
    global _ctx
    if _ctx:
        _ctx.release()
        _ctx = None
```

No `is_available()` check — no fallback. If ModernGL fails to create a context, the application logs the error and exits. This is a hard requirement.

### `src/modules/gpu/texture_pool.py`

Pre-allocate textures and FBOs per resolution. Reused every frame — no per-frame GPU memory allocation.

```python
class TexturePool:
    """
    Resolution-keyed pool of (texture, fbo) pairs.
    Acquire before use, release after — zero allocation per frame after warmup.
    """
    def __init__(self, ctx: moderngl.Context):
        self._ctx = ctx
        self._pool: dict[tuple, list] = {}      # (w, h, components) → [GPUFrame, ...]
        self._in_use: set = set()

    def acquire(self, width: int, height: int, components: int = 3) -> 'GPUFrame':
        key = (width, height, components)
        pool = self._pool.setdefault(key, [])
        for frame in pool:
            if frame not in self._in_use:
                self._in_use.add(frame)
                return frame
        # Allocate new
        frame = GPUFrame(self._ctx, width, height, components)
        pool.append(frame)
        self._in_use.add(frame)
        return frame

    def release(self, frame: 'GPUFrame'):
        self._in_use.discard(frame)

    def warmup(self, width: int, height: int, count: int = 4):
        """Pre-allocate N frames at startup to avoid first-frame latency."""
        for _ in range(count):
            f = self.acquire(width, height)
            self.release(f)
```

### `src/modules/gpu/frame.py`

```python
class GPUFrame:
    """
    Wraps a ModernGL texture + FBO pair.
    Upload: numpy (H,W,3 uint8 BGR) or (H,W,4 uint8 BGRA) → texture
    Download: texture → numpy BGR or BGRA uint8
    components auto-detected from source memmap shape[3] (3=BGR, 4=BGRA)
    Sample: vectorized pixel coordinate lookup (for Art-Net)
    """
    def __init__(self, ctx: moderngl.Context, width: int, height: int, components: int = 3):
        self.ctx = ctx
        self.width = width
        self.height = height
        self.components = components
        # GL textures use RGB/RGBA not BGR/BGRA — conversion handled in upload/download
        self.texture = ctx.texture((width, height), components, dtype='u1')
        self.texture.filter = moderngl.LINEAR, moderngl.LINEAR
        self.fbo = ctx.framebuffer(color_attachments=[self.texture])

    def upload(self, frame: np.ndarray):
        """
        Upload numpy BGR/BGRA uint8 → GL RGB/RGBA texture.
        Reverses channel order (BGR→RGB, BGRA→RGBA) — alpha channel preserved as-is.
        frame must be C-contiguous — checked at call site, not here.
        """
        # BGR→RGB or BGRA→RGBA: reverse the color channels, keep alpha if present
        converted = frame[:, :, ::-1]
        self.texture.write(converted.tobytes())

    def download(self) -> np.ndarray:
        """
        Download GL RGB/RGBA texture → numpy BGR/BGRA uint8.
        ~0.5 ms at 1080p via glReadPixels.
        """
        data = self.fbo.read(components=self.components)
        arr = np.frombuffer(data, dtype=np.uint8).reshape(self.height, self.width, self.components)
        return arr[::-1, :, ::-1].copy()   # Flip Y (GL origin bottom-left) + RGB→BGR / RGBA→BGRA

    def sample_pixels(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """
        Vectorized pixel sampling for Art-Net output.
        xs, ys: int arrays of pixel coordinates.
        Returns: (N, 3) uint8 array in RGB order.
        Only downloads the bounding box, not the full frame.
        """
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        data = self.fbo.read(viewport=(x0, y0, x1 - x0, y1 - y0), components=self.components)
        patch = np.frombuffer(data, dtype=np.uint8).reshape(y1 - y0, x1 - x0, self.components)
        patch = patch[::-1]   # Flip Y
        return patch[ys - y0, xs - x0]
```

### `src/modules/gpu/renderer.py`

The single full-screen quad renderer used by every shader pass.

```python
VERTEX_SHADER = """
#version 330
in vec2 in_position;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    v_uv = in_uv;
}
"""

class Renderer:
    """
    Renders a full-screen textured quad using a given fragment shader.
    All GPU effects (transform, blend, color, blur, ...) use this renderer.
    """
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        self._programs: dict[str, moderngl.Program] = {}
        # Full-screen quad (NDC): two triangles covering -1..1
        vertices = np.array([
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
             1.0,  1.0,  1.0, 1.0,
            -1.0,  1.0,  0.0, 1.0,
        ], dtype=np.float32)
        indices = np.array([0, 1, 2, 0, 2, 3], dtype=np.int32)
        self._vbo = ctx.buffer(vertices.tobytes())
        self._ibo = ctx.buffer(indices.tobytes())

    def get_program(self, frag_source: str) -> moderngl.Program:
        if frag_source not in self._programs:
            prog = self.ctx.program(vertex_shader=VERTEX_SHADER,
                                    fragment_shader=frag_source)
            vao = self.ctx.vertex_array(prog, [(self._vbo, '2f 2f', 'in_position', 'in_uv')],
                                        index_buffer=self._ibo)
            self._programs[frag_source] = (prog, vao)
        return self._programs[frag_source]

    def render(self, frag_source: str, target_fbo: moderngl.Framebuffer,
               uniforms: dict, textures: dict):
        """
        Run a shader pass.
        uniforms: {name: value} — ints, floats, tuples
        textures: {uniform_name: (texture_unit, GPUFrame)}
        """
        prog, vao = self.get_program(frag_source)
        for name, val in uniforms.items():
            if name in prog:
                prog[name].value = val if not isinstance(val, (list, tuple)) else tuple(val)
        for name, (unit, gpu_frame) in textures.items():
            gpu_frame.texture.use(location=unit)
            if name in prog:
                prog[name].value = unit
        target_fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)
        vao.render()
```

### Phase 1 — Layer Pipeline Integration

Replace `LayerManager.composite_layers()` internals. This is the final step that wires the GPU foundation into the actual player.

```python
def composite_layers(self, ...):
    pool = get_texture_pool()
    renderer = get_renderer()
    blend_src = load_shader('blend.frag')
    composite = pool.acquire(canvas_w, canvas_h)   # output FBO
    # Clear composite to black
    composite.fbo.use()
    ctx.clear(0.0, 0.0, 0.0)

    for layer in self.layers:
        # 1. Upload source frame (memmap view → GPU)
        # components auto-detected from memmap shape[3]: 3=BGR, 4=BGRA
        src_frame = layer.source.get_next_frame()
        n_components = src_frame.shape[2]          # 3 or 4
        layer_tex = pool.acquire(canvas_w, canvas_h, components=n_components)
        layer_tex.upload(src_frame)                # ~0.5 ms

        # 2. No effects yet — straight to blend
        renderer.render(
            frag_source=blend_src,
            target_fbo=composite.fbo,
            uniforms={'opacity': layer.opacity / 100.0, 'mode': BLEND_MODES[layer.blend_mode]},
            textures={'base': (0, composite), 'overlay': (1, layer_tex)}
        )
        pool.release(layer_tex)

    return composite   # GPUFrame — stays on GPU
```

### Phase 1 — Output Readback

**Art-Net pixel sampling:**
```python
rgb_pixels = composite.sample_pixels(xs, ys)   # partial readback of bounding box only
```

**Display output** (separate process, queue as before):
```python
bgr = composite.download()   # full frame, ~0.5 ms
# push to multiprocessing queue as numpy bytes — unchanged from today
```

**MJPEG preview** (background thread, not on play loop hot path):
```python
bgr = composite.download()
# cv2.imencode → send
```

---

## Phase 2 — Effects (Shaders + Plugin Interface)

**Deliverable:** Effects work. Transform, color grade, blur all run as GPU shader passes. Plugin interface migrated. CPU `process_frame` path deleted.

**Target: 3 days**

### `src/modules/gpu/shaders/passthrough.frag`
```glsl
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D inputTexture;
void main() {
    fragColor = texture(inputTexture, v_uv);
}
```

### `src/modules/gpu/shaders/transform.frag`
```glsl
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D inputTexture;
uniform vec2 anchor;        // 0..1 (normalized anchor point)
uniform vec2 scale;         // sx, sy
uniform vec2 translate;     // tx, ty in normalized coords
uniform float rotation;     // radians

void main() {
    // Translate UV to anchor-relative space
    vec2 uv = v_uv - anchor;
    // Inverse scale
    uv /= scale;
    // Inverse rotation
    float c = cos(-rotation), s = sin(-rotation);
    uv = vec2(c * uv.x - s * uv.y, s * uv.x + c * uv.y);
    // Translate back
    uv += anchor - translate;
    // Out-of-bounds → black
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    fragColor = texture(inputTexture, uv);
}
```

**Single shader pass replaces: contiguousarray + resize + canvas alloc + canvas zero + canvas copy.**

### `src/modules/gpu/shaders/blend.frag`
```glsl
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D base;
uniform sampler2D overlay;
uniform float opacity;      // 0..1 (layer opacity, multiplied with source alpha)
uniform int mode;           // 0=normal 1=add 2=subtract 3=multiply 4=screen 5=overlay

vec3 blendNormal(vec3 b, vec3 o)    { return o; }
vec3 blendAdd(vec3 b, vec3 o)       { return min(b + o, vec3(1.0)); }
vec3 blendSubtract(vec3 b, vec3 o)  { return max(b - o, vec3(0.0)); }
vec3 blendMultiply(vec3 b, vec3 o)  { return b * o; }
vec3 blendScreen(vec3 b, vec3 o)    { return 1.0 - (1.0 - b) * (1.0 - o); }
vec3 blendOverlay(vec3 b, vec3 o)   {
    return mix(2.0*b*o, 1.0 - 2.0*(1.0-b)*(1.0-o), step(0.5, b));
}

void main() {
    vec3 b = texture(base, v_uv).rgb;
    vec4 ov = texture(overlay, v_uv);   // read full RGBA — alpha is 1.0 for RGB-only sources
    vec3 o = ov.rgb;
    // Final blend weight = layer opacity × source alpha (handles both RGB and RGBA clips)
    float weight = opacity * ov.a;
    vec3 result;
    if      (mode == 0) result = blendNormal(b, o);
    else if (mode == 1) result = blendAdd(b, o);
    else if (mode == 2) result = blendSubtract(b, o);
    else if (mode == 3) result = blendMultiply(b, o);
    else if (mode == 4) result = blendScreen(b, o);
    else                result = blendOverlay(b, o);
    fragColor = vec4(mix(b, result, weight), 1.0);
}
```

**Alpha note:** RGB sources (3-channel .npy) upload as `GL_RGB` — OpenGL fills alpha=1.0 on sample, so `weight = opacity * 1.0 = opacity`. BGRA sources (4-channel .npy) upload as `GL_RGBA` — alpha comes from the source directly. No shader change needed between the two cases.

### `src/modules/gpu/shaders/color.frag`
```glsl
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D inputTexture;
uniform float brightness;  // multiplier, 1.0 = no change
uniform float hue_shift;   // degrees, 0 = no change
uniform float saturation;  // multiplier, 1.0 = no change

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0*d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void main() {
    vec3 color = texture(inputTexture, v_uv).rgb * brightness;
    if (hue_shift != 0.0 || saturation != 1.0) {
        vec3 hsv = rgb2hsv(color);
        hsv.x = fract(hsv.x + hue_shift / 360.0);
        hsv.y *= saturation;
        color = hsv2rgb(hsv);
    }
    fragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
```

### `src/modules/gpu/shaders/blur_h.frag` + `blur_v.frag`
```glsl
// blur_h.frag — horizontal pass (blur_v.frag is identical with axis flipped)
#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform sampler2D inputTexture;
uniform float radius;       // pixels
uniform vec2 texelSize;     // 1.0/vec2(width, height)

void main() {
    vec3 result = vec3(0.0);
    float total = 0.0;
    int r = int(radius);
    for (int i = -r; i <= r; i++) {
        float weight = exp(-float(i*i) / (2.0 * radius * radius));
        result += texture(inputTexture, v_uv + vec2(float(i) * texelSize.x, 0.0)).rgb * weight;
        total += weight;
    }
    fragColor = vec4(result / total, 1.0);
}
```

---

## Phase 2 — Plugin Interface

Each effect plugin exposes a GLSL fragment shader source and its uniforms. The pipeline calls `get_shader()` once (cached), then `get_uniforms()` every frame.

```python
class PluginBase:
    # NEW — GPU path
    def get_shader(self) -> str:
        """Return GLSL fragment shader source. Called once, result cached."""
        raise NotImplementedError

    def get_uniforms(self) -> dict:
        """Return {uniform_name: value} for current parameter values. Called every frame."""
        return {}

    # OLD — CPU path, REMOVED
    # def process_frame(self, frame, **kwargs) → removed entirely
```

### Transform plugin (GPU version)

```python
class TransformEffect(PluginBase):
    def get_shader(self) -> str:
        with open('src/modules/gpu/shaders/transform.frag') as f:
            return f.read()

    def get_uniforms(self) -> dict:
        scale_xy = self.scale_xy / 100.0
        return {
            'anchor':    (self.anchor_x / 100.0, self.anchor_y / 100.0),
            'scale':     (self.scale_x / 100.0 * scale_xy, self.scale_y / 100.0 * scale_xy),
            'translate': (self.position_x / canvas_w, self.position_y / canvas_h),
            'rotation':  math.radians(self.rotation_z),
        }
```

**Cost per frame: ~0.2 ms** (one draw call, ~2M tex lookups in parallel).

### Phase 2 — Layer Pipeline (with effects)

Expand `composite_layers()` to run the effect chain per layer, now that plugins implement `get_shader()`:

```python
        # 2. Apply effect chain (each effect = one shader pass)
        for effect in layer.effects:
            out_tex = pool.acquire(canvas_w, canvas_h)
            renderer.render(
                frag_source=effect.instance.get_shader(),
                target_fbo=out_tex.fbo,
                uniforms=effect.instance.get_uniforms(),
                textures={'inputTexture': (0, layer_tex)}
            )
            pool.release(layer_tex)
            layer_tex = out_tex
```

Brightness / hue from `core.py` also moves here: append `color.frag` pass when either is non-default, skip entirely when both are default.

---

## Dependencies

```
moderngl>=5.8.0
glcontext>=2.5.0   # headless context backend for moderngl
```

Add to `requirements.txt`. No other new runtime dependencies.

```bash
pip install moderngl glcontext
```

Verify GPU context at startup:
```python
ctx = moderngl.create_standalone_context()
# If this raises: log error, exit with clear message
```

---

## What Is NOT Changed

| Component | Status |
|---|---|
| `sources.py` — memmap frame loading | Unchanged |
| `core.py` play loop — timing, transport, playlist | Unchanged |
| `profiler.py` — stage timing | Unchanged (profile GPU stages the same way) |
| Flask API, all endpoints | Unchanged |
| `session_state.json`, `config.json` | Unchanged |
| Playlist manager, clip registry | Unchanged |
| Art-Net UDP sender | Unchanged |
| Frontend JS | Unchanged |
| Display output (separate process) | Unchanged — receives numpy bytes via queue as before |

---

## Code Removal / Archival Policy

When replacing old code, move it to `archive/` first, then delete it from its original location. Never leave dead code, commented-out blocks, or `# TODO: remove` markers in production files.

### Phase 1 archive target: `archive/legacy_cpu_pipeline_phase1.py`
- `src/modules/gpu/accelerator.py` — OpenCL UMat wrapper (replaced by ModernGL)
- `src/modules/gpu/compositor.py` — CPU/CuPy compositor (replaced by `blend.frag`)

### Phase 2 archive target: `archive/legacy_cpu_pipeline_phase2.py`
- The `process_frame(frame)` method from all effect plugins (one block per plugin)
- `np.ascontiguousarray` call sites throughout the codebase
- Writability flag checks (`frame.flags['WRITEABLE']`)

The archive files are never imported — reference only. If the archived code has no reference value (e.g. trivial one-liners), delete outright.

---

## Implementation Order

```
Phase 1 — GPU foundation + playback pipeline                         (3 days)
    context.py, texture_pool.py, renderer.py, frame.py
    passthrough.frag + blend.frag (layer compositor)
    composite_layers() rewrite (passthrough, no effects yet)
    readback: display queue + Art-Net sampling + MJPEG
    ✅ MILESTONE: add clip(s), press play — display/Art-Net/preview all work
               autoplay, loop playlist, transport (speed/reverse/bounce/paused) all work

Phase 2 — Effects (shaders + plugin interface)                       (3 days)
    transform.frag, color.frag, blur_h.frag, blur_v.frag
    PluginBase: get_shader() + get_uniforms(), process_frame() removed
    Migrate Transform + Color plugins to GPU interface
    Expand composite_layers() to run effect chains
    brightness/hue from core.py → color shader pass
    Delete CPU compositor, delete OpenCL accelerator
    ✅ MILESTONE: effects run, old CPU path gone
```

**Total: ~6 days of focused work.**

---

## Expected Results

| Metric | Before | After |
|---|---|---|
| Simple transform (1 layer, 1 effect) | ~12 ms | ~1 ms |
| 3 layers + blend | ~40–50 ms | ~3–5 ms |
| Blur (r=15) | ~12 ms | ~0.5 ms |
| Full pipeline at 1080p, 3 layers, 5 effects | >50 ms | ~6–8 ms |
| Max theoretical FPS (1080p, complex scene) | ~20 fps | **120+ fps** |
