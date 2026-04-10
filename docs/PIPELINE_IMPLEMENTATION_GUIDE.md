# GPU Pipeline — Implementation Guide
## Based on: `docs/Pipeline.txt` (Architecture Spec)
## Audit date: 2026-03-27

---

## Executive Summary

The Pipeline.txt spec describes a **deterministic, fully shader-based GPU rendering
pipeline** with Linear + Straight Alpha color standards, JIT effect-stack compilation,
formal Layer Tap/Slice routing, Prefetch/ringbuffer for sources, and a Human-Decision
Gate for FPS monitoring.

The current codebase has a solid GPU foundation but implements only the core render
path. Several critical architectural pillars from the spec are absent or partial.

**Tier classification used below:**
- ✅ **DONE** — implemented and working
- ⚠️ **PARTIAL** — exists but gaps remain
- ❌ **MISSING** — not yet implemented

---

## Section-by-Section Audit

### Section 0 — Goals & Tier A Minimum

| Requirement | Status | Notes |
|---|---|---|
| 30 fps, 2 streams FHD | ⚠️ | AMD iGPU ~20fps; discrete GPU target met |
| 1 Layer, 5 effects | ⚠️ | Pipeline correct; only 4/67 effects are GPU shaders |
| Live param changes without recompile stutter | ✅ | Uniforms updated per-frame; no recompile |
| Stack changes without hard stalls | ⚠️ | CPU effects mid-chain still force download |

---

### Section 1 — Invariants: Straight Alpha + Linear Colorspace

| Invariant | Status | Notes |
|---|---|---|
| **Straight Alpha everywhere** | ⚠️ | blend.frag handles alpha correctly; but upload path does not enforce/track alpha_mode; RGB sources have no alpha plane |
| **Linear colorspace for all calculations** | ❌ | GPU textures are `float32` but raw video frames come in sRGB (uint8 from cv2 decoder). No sRGB→Linear conversion in `frame.upload()`. blend.frag and effect shaders operate on potentially sRGB-encoded data. |
| **SampleSource delivers Linear + Straight Alpha** | ❌ | No SampleSource() function exists. `frame.upload()` does BGR→RGB + /255 normalization only. |

**⚠️ OPEN QUESTION 1:** Implementing sRGB→Linear conversion requires modifying `GPUFrame.upload()` (add gamma decode) AND adding Linear→sRGB on `download()` (or on display output). This would also require verifying every existing `.frag` shader operates correctly in linear space. Is strict linear-space enforcement required for Phase 1, or is it acceptable to defer until HAP integration?

---

### Section 2 — Data Models: TextureSet, LayerDescriptor, ISource, IRenderer

| Component | Status | Notes |
|---|---|---|
| `TextureSet` (color_model, alpha_mode, colorspace_hint) | ❌ | Not implemented. Sources return numpy arrays directly. |
| `LayerDescriptor` (effect stack, composite params, tap config) | ⚠️ | `Layer` class exists with effect list, opacity, blend_mode. No tap configuration field. No formal `LayerDescriptor` name. |
| `ISource` (open/seek/acquire/close) | ❌ | No formal interface/ABC. Sources are duck-typed with `get_next_frame()`. |
| `IRenderer` (render → main output + slice outputs + tap registry) | ⚠️ | `LayerManager.composite_layers()` returns main output. Slice outputs via `OutputManager`. No tap registry per frame. |

---

### Section 3 — Sources

| Source Type | Status | Notes |
|---|---|---|
| **RAW Source (NumPy/memmap)** | ⚠️ | Works. But no async upload double-buffer. No prefetch ring. `get_next_frame()` is synchronous in render thread. |
| **Prefetch Thread + Ringbuffer** | ❌ | Not implemented. Critical for HAP; less urgent for small numpy clips. |
| **Async Upload (Double/Triple buffer)** | ❌ | Not implemented. `frame.upload()` is synchronous. |
| **Texture Reuse** | ✅ | `TexturePool` handles zero-alloc reuse after warmup. |
| **HAP Q Alpha Source** | ❌ | Not implemented. No HAP decoder anywhere in codebase. |
| **ISF Source** | ❌ | Not implemented (marked optional in spec). |

---

### Section 4 — SampleSource() Normalize Gate

| Feature | Status | Notes |
|---|---|---|
| Single normalize entrypoint | ❌ | No `SampleSource()` function. Normalization is split across `frame.upload()` (flip + /255), source decoders, and implicit shader math. |
| Format/Plane handling (RAW vs HAP) | ❌ | No plane-based dispatch; would be needed for HAP Q YCoCg planes |
| sRGB→Linear decoding | ❌ | Not performed. |
| alpha combine | ❌ | Not performed for sources that have separate alpha planes |

---

### Section 5 — Effect Stack: JIT + Cache + Fallback

| Feature | Status | Notes |
|---|---|---|
| Reorderable effects, multiple instances | ✅ | `layer.effects` is an ordered list, duplicates allowed |
| GPU ping-pong chain | ✅ | `apply_layer_effects()` ping-pong with single upload/download |
| CPU fallback when no GPU effects | ✅ | Fast CPU-only path in `apply_layer_effects()` |
| **JIT compilation (merged single-pass shader per stack)** | ❌ | Not implemented. Each effect is rendered in a separate draw call. The spec requires merging all effects in a stack into one compiled GLSL program for performance. |
| **StackSignature** (effect IDs + versions + order) | ❌ | No StackSignature concept. Cache key is raw GLSL string per effect. |
| **LRU program cache (128–256 entries)** | ❌ | No LRU. Cache grows unbounded by GLSL string. |
| **Fallback Interpreter Shader** (max 20 ops via opcode dispatch) | ❌ | Not implemented. If JIT fails, there is no GPU fallback; effects fall to CPU `process_frame()`. |
| Compile debounce (no stall during drag&drop) | ❌ | No debounce. Currently re-compiles are not an issue since each effect has its own pre-compiled shader. |
| Live param changes (uniform updates only, no recompile) | ✅ | `get_uniforms()` called per-frame; uniforms set without recompile. |

**⚠️ OPEN QUESTION 2:** JIT compilation (merging multiple effect shaders into one GPU pass) is a significant complexity increase. Currently each effect runs as a separate draw call with ping-pong textures. For 5 effects this means 5 draw calls. The JIT approach merges them to 1. Is the multi-draw-call ping-pong approach acceptable for Phase 1, deferring JIT to Phase 3?

---

### Section 6 — Parameter Buffers (SSBO Layout)

| Feature | Status | Notes |
|---|---|---|
| Per-layer fixed-slot parameter buffer | ❌ | Not implemented. |
| Uniform updates via SSBO sub-update | ❌ | Uniforms are set individually via `program[name].value = x` per-effect per-frame. |
| Command buffer (opcode + paramIndex) | ❌ | Not implemented (only needed if JIT/interpreter implemented). |

**Note:** Given the current ping-pong architecture (one draw call per effect), individual uniform setting is correct and adequate. SSBO parameter buffers are only strictly necessary if JIT single-pass is implemented.

---

### Section 7 — Composite Pass (shader-based, Linear + Straight Alpha)

| Feature | Status | Notes |
|---|---|---|
| Shader-based compositing (no fixed-function blend) | ✅ | `blend.frag` handles all blending. `cv2.addWeighted` fallback removed. |
| Standard Over operator | ✅ | blend.frag mode=0 (normal) implements `mix(base, blended, alpha)` |
| Straight Alpha Over correctness | ⚠️ | blend.frag `alpha = opacity * overlay_px.a` — correct for straight alpha. BUT: if input is sRGB (not linear), blend results are slightly wrong in theory. |
| Blendmodes in Linear | ⚠️ | Same caveat: blendmodes exist (multiply, screen, overlay etc.) but not guaranteed to operate on linear data currently. |
| Multi-layer compositing | ✅ | `composite_layers()` chains layers via repeated blend.frag renders with ping-pong. |

---

### Section 8 — Layer Taps + Slice Routing

| Feature | Status | Notes |
|---|---|---|
| `stay_on_gpu=True` flag in apply_layer_effects | ✅ | Returns `GPUFrame` instead of numpy when True. |
| **Formal Tap system** (tap_id, stage, layer_selector, mode) | ❌ | No Tap system. Only an opaque `_artnet_gpu_hook` callback exists. |
| Tap stages: `LayerProcessed`, `CompositeAfterN` | ❌ | Only implicit: the ArtNet hook fires after full composite, not per-layer. |
| Tap Registry (per-frame: tap_id → texture) | ❌ | Not implemented. |
| `separate` vs `combined` multi-layer tap modes | ❌ | Not implemented. |
| Canonical order (low→high) for multi-layer taps | ❌ | Not implemented (assumed implicitly by layer list order). |
| Combined = Straight AlphaOver in canonical order | ❌ | Not implemented for taps. |
| **Slice System** (slice_id, target_type, resolution_policy) | ⚠️ | `SliceManager` + `OutputManager` exist. But Slice→Tap mapping per spec is not implemented. |
| RT pinning (taps keep textures alive past pool reuse) | ❌ | TexturePool does not support pinning. Acquired frames must be released in the same frame. |

---

### Section 9 — Plugin System

| Feature | Status | Notes |
|---|---|---|
| Plugin base class + discovery | ✅ | `PluginBase` ABC with METADATA, PARAMETERS. |
| `DISABLED = True` gate | ✅ | Plugin loader skips `DISABLED=True` classes. |
| GPU shaders via `get_shader()` / `get_uniforms()` | ✅ | Pattern established, 4/67 effects implemented. |
| **Namespaced effect_id** | ⚠️ | `id` field exists but no namespace (e.g. no `com.vendor.effect_name`). |
| **effect_version** in METADATA | ⚠️ | Version field inconsistently present. |
| **effect_api_version** (host compatibility) | ❌ | Not implemented. |
| Effect classification A/B/C (local / multi-sample / multi-pass) | ❌ | Not declared in plugins. `transform.frag` is effectively class A; blur would be B/C. |
| Opcode registry for Interpreter fallback | ❌ | Not implemented. |
| JIT-only marking for plugins | ❌ | Not implemented. |
| LRU cache invalidation on plugin update | ❌ | Not implemented. |
| Plugin quarantine on repeated compile error | ⚠️ | try/except in apply_layer_effects logs errors; no quarantine timeout. |

---

### Section 10 — cv2 Removal from Playback Hotpath

| Feature | Status | Notes |
|---|---|---|
| Brightness/Hue CPU bypass removed | ✅ | Deleted from core.py (this session). |
| cv2 not Source-of-Truth for transport | ✅ | Transport is player state machine. |
| cv2.resize in composite_layers (layer size mismatch) | ⚠️ | Still present (line ~927); fires only on resolution mismatch. Should be replaced with a GPU blit/resize shader. |
| cv2.resize in transition_renderer.py | ⚠️ | Still present; fires only on size mismatch. |
| Player state machine (stop/play/pause) | ✅ | Implemented. |
| next/prev as playlist-item navigation | ✅ | PlaylistManager exists. |
| stop = hold last frame (Freeze) | ✅ | clear_frame() behavior correct. |
| loop modes | ⚠️ | max_loops exists; loop_mode variants not fully documented. |
| autoplay | ⚠️ | autoplay property exists; behavior may not cover all edge cases. |
| Prefetch integration with player state | ❌ | No prefetch to integrate. |
| Transport Plugin: speed forward/back/bounce/random | ⚠️ | `transport.py` plugin exists with seek_frame logic; full compliance not confirmed. |
| Timeline Triple Slider (Trim Min/Max) | ⚠️ | In UI; backend `_calculate_next_frame()` uses in/out points. Compliance not audited. |

---

### Section 11 — Resource Management

| Feature | Status | Notes |
|---|---|---|
| RenderTarget Pool (w,h,format keyed reuse) | ✅ | TexturePool implemented. |
| Zero per-frame alloc after warmup | ✅ | Confirmed in texture_pool.py and frame.py. |
| No hard sync points in hotpath | ⚠️ | `ctx.finish()` (glFinish) is called in ArtNet compute dispatch. SSBODownloader may also use finish internally. |
| Upload decoupling (double/triple buffer) | ❌ | Synchronous upload. |
| JIT compile non-blocking | N/A | No JIT yet. |

---

### Section 12 — I/O & Streaming Policy

| Feature | Status | Notes |
|---|---|---|
| Prefetch/Ringbuffer | ❌ | Not implemented. |
| Read throughput / decode time metrics | ⚠️ | `source_decode` stage in profiler exists; no ring buffer health metrics. |
| Preview-Quality Mode | ❌ | Not implemented (always full-res). |

---

### Section 15 — Human-Decision Gate

| Feature | Status | Notes |
|---|---|---|
| FPS monitoring (sustained drop below 30 fps) | ⚠️ | Profiler records FPS; no auto-trigger threshold implemented. |
| Human-Decision Gate prompt | ❌ | Not implemented. |
| Snapshot at Gate trigger | ❌ | Not implemented. |
| Dev/Low-Spec profile save | ❌ | Not implemented. |

---

### Section 16 — Profiler & Observability

| Feature | Status | Notes |
|---|---|---|
| Stage profiler (cpu wall time) | ✅ | `PerformanceProfiler` with 10 stages + dynamic stages. |
| Dev / Light mode | ❌ | Single mode only. No Light/Dev toggle. |
| GPU timing per pass | ❌ | No GPU timer queries (OpenGL `ARB_timer_query`). |
| Shader build/cache events | ❌ | Not tracked. |
| RT pool stats | ❌ | Not exposed. |
| Prefetch health (queue depth, starvation) | ❌ | No prefetch to monitor. |
| Light Snapshot on Gate | ❌ | No Gate; no snapshot. |
| p95/p99 aggregation | ❌ | Only min/avg/max currently. |
| Frame correlation (frame_id, player_id, stack_sig) | ❌ | No frame_id tracking. |

---

### Section 17 — Additional Requirements

| Requirement | Status | Notes |
|---|---|---|
| Transport plugin speed/bounce/random | ⚠️ | Exists; full compliance unconfirmed. |
| Frontend plugin system compatibility | ✅ | API endpoints preserved. |
| MJPEG stream without CPU copy | ⚠️ | SSBODownloader reduces to ~10–21ms. Preview subscriber gating exists. Full zero-copy would require GPU video encoder (not feasible headless). |
| Output Routing redesign | ⚠️ | OutputManager + SliceManager exist; Tap-based redesign pending. |
| ArtNet pixel calculation | ✅ | GPU compute shader (ArtNet SSBO sampler) implemented. |
| API endpoints remain | ✅ | No break observed. |
| Frontend compatibility 100% | ✅ | Current UI continues to work. |

---

## Implementation Roadmap

### Phase 1 — Core Pipeline Health (Tier A baseline)

These are items that are **required for reliable 30 fps on target hardware** and are
**low-to-medium effort** given the existing foundation.

#### 1A — GPU effect shader coverage (highest leverage)
Only 4/67 effect plugins have `get_shader()`. Every time a CPU effect appears in
an otherwise GPU chain it forces one full GPU→CPU download + re-upload. Target:
the most commonly used CPU effects.

**Priority effects to port (GLSL is straightforward):**

| Plugin | GLSL complexity | Notes |
|---|---|---|
| `blur.py` | Medium | Separable Gaussian — 2-pass; classify as type B |
| `sharpen.py` | Low | 3×3 convolution kernel |
| `vignette.py` | Low | Radial distance from center, multiply |
| `invert.py` | Low | `1.0 - color` |
| `opacity.py` | Low | `mix(color, vec3(0), opacity)` or alpha multiply |
| `saturation.py` | Low | HSL saturation in GLSL |
| `temperature.py` | Low | Wade/Berger RGB matrix |
| `gamma.py` | Low | `pow(color, vec3(1/gamma))` |
| `exposure.py` | Low | `color * pow(2.0, ev)` |
| `sepia.py` | Low | 3×3 matrix multiply |
| `mirror.py` | Low | UV flip |
| `flip.py` | Low | UV flip |
| `crop.py` | Low | UV clamp/discard |
| `noise.py` | Low | Hash noise GLSL |
| `wave_warp.py` | Medium | UV sine distortion |
| `mosaic.py` / `pixelate.py` | Low | UV floor snap |

**Implementation pattern** (same as `brightness_contrast.py`):
```python
_SHADER_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'modules', 'gpu', 'shaders', 'blur.frag')

def get_shader(self): return open(_SHADER_PATH).read()
def get_uniforms(self, frame_w=1, frame_h=1, **kw): return {'radius': self.radius, ...}
def process_frame(self, frame, **kw): return frame  # stub — GPU handles it
```

#### 1B — Replace cv2.resize in compositor with GPU blit

**File:** `src/modules/player/layers/manager.py` ~line 927  
**File:** `src/modules/gpu/transition_renderer.py` ~line 48, 75

Replace `cv2.resize(frame, (canvas_w, canvas_h))` with a GPU blit:
```python
# Create a blit shader: passthrough.frag already exists
# Or: upload the mismatched-size frame to a temporary GPU texture
#     and render with passthrough.frag to the target size
```

This removes the last cv2 call from the render hotpath.

#### 1C — Fix `stay_on_gpu` return path in `apply_layer_effects`

Currently `stay_on_gpu=True` is passed but the returned type (numpy vs GPUFrame) may not
be consistently handled by callers. Verify and enforce the contract in:
- `composite_layers()` — calls with `stay_on_gpu=True`, checks `isinstance(result, np.ndarray)`
- Ensure `pool.release()` is always called in `composite_layers` when the GPUFrame path is taken

#### 1D — Profiler: Dev/Light mode toggle + p95/p99

**File:** `src/modules/performance/profiler.py`

Add:
```python
class ProfilerMode(Enum):
    OFF = 0
    LIGHT = 1   # frame total, source total, render total, jit flag
    DEV = 2     # full per-stage, per-layer, per-effect

# runtime toggle: profiler.set_mode(ProfilerMode.DEV)
```

Add p95/p99 to `get_metrics()` (use `statistics.quantiles` on the deque).

---

### Phase 2 — Source Pipeline + Prefetch

These items enable HAP migration and eliminate synchronous I/O from the render loop.

#### 2A — Formal ISource interface

```python
# src/modules/player/sources/base.py
from abc import ABC, abstractmethod

class ISource(ABC):
    @abstractmethod
    def open(self, uri: str, opts: dict = None): ...
    
    @abstractmethod
    def seek(self, time_or_frame): ...
    
    @abstractmethod
    def acquire(self, time_or_frame=None) -> 'TextureSet':
        """Must NOT block unboundedly. Returns None on miss (consumer should retry)."""
        ...
    
    @abstractmethod
    def close(self): ...
```

Existing `VideoSource`, `GeneratorSource` can implement this without breaking current callers.

#### 2B — Prefetch Ringbuffer

```python
# src/modules/player/sources/prefetch_buffer.py
class PrefetchBuffer:
    """
    Thread-safe ringbuffer + prefetch thread.
    Producer: decodes from source on background thread, uploads to GPU texture.
    Consumer (render thread): acquire() returns next pre-decoded frame without IO wait.
    """
    def __init__(self, source: ISource, buffer_size: int = 4): ...
    def start(self): ...   # spawn prefetch thread
    def acquire(self) -> GPUFrame: ...  # returns pre-uploaded GPUFrame or blocks briefly
    def stop(self): ...
```

Wrap any `ISource` in `PrefetchBuffer` when the source is opened.
All `get_next_frame()` call sites in `LayerManager` become `prefetch_buffer.acquire()`.

#### 2C — SampleSource() normalize gate

```python
# src/modules/gpu/sample_source.py
def sample_source(raw_frame: np.ndarray, colorspace_hint: str = 'srgb') -> GPUFrame:
    """
    Single entrypoint for all source normalization.
    Returns: GPUFrame with float32 Linear RGBA (Straight Alpha).
    """
    gpu_frame = get_texture_pool().acquire(raw_frame.shape[1], raw_frame.shape[0], components=4)
    if colorspace_hint == 'srgb':
        # Apply sRGB→Linear conversion on upload
        # In GLSL: pow(color, vec3(2.2)) — or use hardware sRGB texture sampling
        gpu_frame.upload_srgb(raw_frame)
    else:
        gpu_frame.upload(raw_frame)  # assume already linear
    return gpu_frame
```

For display outputs, add `Linear→sRGB` encoding pass (or use `GL_FRAMEBUFFER_SRGB`).

**Note:** This requires verifying all existing .frag shaders are correct in linear space.

#### 2D — HAP Q Alpha decoder

Uses `hap` Python package or custom FFmpeg-based decoder.
SampleSource path handles YCoCg→RGB shader conversion.

---

### Phase 3 — Advanced Pipeline Features

These items implement the more advanced spec features and are deferred to Phase 3.

#### 3A — JIT Shader Compilation (Stack Signature)

> **Precondition:** Requires §2C (SampleSource) and significant all-effects GPU coverage.

```python
class StackSignature:
    """Immutable identity of an effect stack configuration."""
    def __init__(self, effects: list):
        # effect_id + version + order (including duplicates)
        self.hash = hash(tuple((e.METADATA['id'], e.METADATA.get('version','1.0')) 
                               for e in effects))
    
    def build_merged_glsl(self) -> str:
        """Concatenate all effect's apply() GLSL functions into one pass."""
        ...
```

LRU cache (128–256 entries) over compiled `moderngl.Program` objects keyed by `StackSignature.hash`.

#### 3B — Fallback Interpreter Shader

> **Precondition:** Requires §3A (JIT) as primary path.

For effects that have registered opcodes, a single GLSL interpreter shader dispatches
up to 20 opcodes per frame without recompile. Activated when JIT compile fails or is
in progress.

#### 3C — Formal Tap / Layer Abgriff System

```python
class TapConfig:
    tap_id: str
    stage: Literal['LayerProcessed', 'CompositeAfterN', 'SourceDecoded']
    layer_selector: int | list[int]   # single or multi
    mode: Literal['separate', 'combined']
    resolution_policy: Literal['native', 'output', 'fixed']
    lifetime_policy: Literal['frame_ephemeral', 'persist']

class TapRegistry:
    """Per-frame: tap_id → GPUFrame or list[GPUFrame]"""
    def register(self, tap_id: str, texture: GPUFrame | list[GPUFrame]): ...
    def get(self, tap_id: str) -> GPUFrame | list[GPUFrame] | None: ...
    def clear(self): ...   # called at start of each frame
```

Integrate into `composite_layers()`:
- Fire `LayerProcessed` taps after each `apply_layer_effects()` call
- Fire `CompositeAfterN` taps after each blend step
- RT pinning: acquired GPUFrames in TapRegistry must NOT be released until registry.clear()

Connect Tap outputs to Slice routing:
```python
output_manager.slice_manager.assign_tap(slice_id, tap_id, tap_output_index)
```

#### 3D — Human-Decision Gate

```python
# src/modules/performance/gate.py
class HumanDecisionGate:
    """Fires when sustained FPS drops below target."""
    FPS_WINDOW_SEC = 5.0
    FPS_TARGET = 30.0
    
    def check(self, profiler: PerformanceProfiler) -> bool:
        """Returns True if gate should fire."""
        recent_fps = profiler.get_recent_fps(window_sec=self.FPS_WINDOW_SEC)
        return recent_fps < self.FPS_TARGET * 0.95
    
    def prompt(self, current_fps: float) -> GateDecision:
        # POST to /api/fps-gate event → frontend modal dialog
        ...
```

Connect to render loop in `core.py`. On gate fire: emit event, pause gate checking until decision made.

#### 3E — GPU Profiler (ARB_timer_query)

```python
# src/modules/performance/gpu_timer.py
class GPUTimer:
    """Wraps OpenGL ARB_timer_query for per-pass GPU timing."""
    def __init__(self, ctx):
        self._query = ctx.query(moderngl.TIME_ELAPSED)
    
    @contextmanager
    def measure(self):
        self._query.mglo.begin()
        yield
        self._query.mglo.end()
        self._query.mglo.wait_result()  # read on NEXT frame to avoid sync stall
    
    def get_ns(self) -> int: ...   # nanoseconds
```

Integrate optional GPU timing into profiler stages in DEV mode.

---

## Priority Matrix

| Item | Phase | Effort | Impact on 30fps | Required for Tier A |
|---|---|---|---|---|
| **1A — Port 15+ effect plugins to GPU** | 1 | Medium | High | ✅ |
| **1B — Replace cv2.resize with GPU blit** | 1 | Low | Low | ✅ |
| **1C — stay_on_gpu contract audit** | 1 | Low | Medium | ✅ |
| **1D — Profiler Light/Dev mode** | 1 | Low | None | ✅ |
| **2A — ISource formal interface** | 2 | Low | None | No |
| **2B — Prefetch ringbuffer** | 2 | Medium | Medium (HAP) | No (needed for HAP) |
| **2C — SampleSource / Linear colorspace** | 2 | High | None (correctness) | No |
| **2D — HAP Q Alpha decoder** | 2 | High | None (new format) | No |
| **3A — JIT StackSignature** | 3 | Very High | Medium | No |
| **3B — Interpreter Shader** | 3 | High | None (fallback) | No |
| **3C — Tap/Slice system** | 3 | High | None | No |
| **3D — Human-Decision Gate** | 3 | Medium | None | No |
| **3E — GPU Profiler** | 3 | Medium | None | No |

---

## Decisions (2026-03-27)

| Question | Decision |
|---|---|
| **Q1 — Linear colorspace** | **Implement now.** Add sRGB→Linear in `GPUFrame.upload()` and Linear→sRGB in display download path. Verify all existing `.frag` shaders. Add `SampleSource()` gate. |
| **Q2 — JIT StackSignature** | **Prepare now.** Implement `StackSignature` + LRU program cache in `Renderer`. Implement merged shader compilation. Defer full JIT pipeline-drain (production use) to Phase 3. |
| **Q3 — HAP** | **Defer.** NumPy/RAW source is sufficient for Phase 1. HAP Q Alpha is Phase 2. |
| **Q4 — Tap system** | **Implement now.** Full formal Tap/Slice system: `TapConfig`, `TapRegistry`, `LayerProcessed` + `CompositeAfterN` stages wired into compositor. |

---

## Implementation Plan (Phase 1 Priorities)

### STEP 1 — Linear Colorspace (Q1)

**Impact:** Changes visual output of entire pipeline. Must be done first (Q2/Q4 depend on correct colorspace).

**Files to change:**
- `src/modules/gpu/frame.py` — `upload()`, add `upload_srgb()` / `upload_linear()`
- `src/modules/gpu/ssbo_downloader.py` — add sRGB-encode pass in compute shader (or post-process in numpy)
- `src/modules/gpu/shaders/` — add `srgb_utils.glsl` with `srgb_to_linear()` / `linear_to_srgb()` functions
- New: `src/modules/gpu/sample_source.py` — `SampleSource()` normalize gate

**Concrete steps:**

1. **sRGB→Linear on upload** — modify `upload()` in `frame.py`:
   ```python
   # Current:
   np.multiply(frame[:, :, ::-1], 1.0 / 255.0, out=self._upload_buf)
   # New (sRGB decode — approximation: pow 2.2):
   np.power(frame[:, :, ::-1] * (1.0 / 255.0), 2.2, out=self._upload_buf)
   ```
   Add `colorspace: str = 'srgb'` parameter so caller can pass `'linear'` if source is already linear.

2. **Linear→sRGB on display download** — in `SSBODownloader.download()` or as a post-process step:
   ```python
   # After download from GPU (values are 0.0–1.0 linear):
   # Apply sRGB encode before uint8 clamp:
   np.power(linear_float, 1.0 / 2.2) * 255.0 → uint8
   ```

3. **Shader utils** — add shared `srgb_utils.glsl` with:
   ```glsl
   vec3 srgb_to_linear(vec3 c) { return pow(c, vec3(2.2)); }
   vec3 linear_to_srgb(vec3 c) { return pow(c, vec3(1.0/2.2)); }
   ```
   Not needed inline since conversion is done in upload/download (CPU side), but useful
   if ISF or HAP sources later supply sRGB textures that need GPU-side decode.

4. **SampleSource() gate** — new `src/modules/gpu/sample_source.py`:
   ```python
   def sample_source(frame: np.ndarray, colorspace: str = 'srgb') -> GPUFrame:
       """Normalize gate: returns GPUFrame with Linear RGBA. All sources must go through here."""
       gpu = get_texture_pool().acquire(frame.shape[1], frame.shape[0])
       gpu.upload(frame, colorspace=colorspace)
       return gpu
   ```
   Replace direct `gpu.upload(frame)` calls in `apply_layer_effects()` and `composite_layers()`.

5. **Verify existing shaders** — in linear space all current math is already correct:
   - `blend.frag`: multiply, screen, overlay, add — all valid in linear ✅
   - `brightness_contrast.frag`: multiply/add — correct in linear ✅
   - `hue_rotate.frag`: HSV conversion — HSV math is value-space agnostic ✅
   - `colorize.frag`: needs review (hue shift in possibly sRGB space)
   - `transform.frag`: UV sampling — colorspace-agnostic ✅
   - `blend_mode.frag`: 14 modes — correct in linear ✅
   - `fade_transition.frag`: `mix()` — correct in linear ✅

---

### STEP 2 — Formal Tap/Slice System (Q4)

**Impact:** Additive — does not change existing render path. New capability only.

**New package:** `src/modules/player/taps/`

**Files:**

```
src/modules/player/taps/
    __init__.py
    config.py      ← TapConfig, TapStage dataclasses
    registry.py    ← TapRegistry (per-frame: tap_id → GPUFrame | list[GPUFrame])
```

**Concrete steps:**

1. **`config.py`** — data models:
   ```python
   from dataclasses import dataclass, field
   from enum import Enum
   from typing import Literal, Optional, List

   class TapStage(str, Enum):
       SOURCE_DECODED = 'SourceDecoded'       # optional
       LAYER_PROCESSED = 'LayerProcessed'     # after effect stack, before composite
       COMPOSITE_AFTER_N = 'CompositeAfterN'  # after composite step N

   @dataclass
   class TapConfig:
       tap_id: str
       stage: TapStage
       layer_selector: int | List[int]        # single index or list
       mode: Literal['separate', 'combined'] = 'combined'
       resolution_policy: Literal['native', 'output', 'fixed'] = 'output'
       lifetime_policy: Literal['frame_ephemeral', 'persist'] = 'frame_ephemeral'
       # For CompositeAfterN: which composite step (0-based)
       composite_after_n: Optional[int] = None
   ```

2. **`registry.py`** — per-frame registry with RT pinning:
   ```python
   class TapRegistry:
       def __init__(self):
           self._taps: dict[str, GPUFrame | list[GPUFrame]] = {}
           self._pinned: list[GPUFrame] = []   # prevents pool reclaim during frame

       def register(self, tap_id: str, frame: GPUFrame | list[GPUFrame]):
           """Pin and store. frame must NOT be returned to pool while registered."""
           self._taps[tap_id] = frame
           if isinstance(frame, list):
               self._pinned.extend(frame)
           else:
               self._pinned.append(frame)

       def get(self, tap_id: str) -> GPUFrame | list[GPUFrame] | None:
           return self._taps.get(tap_id)

       def clear(self):
           """Release all pinned RTs back to pool. Call at start of each frame."""
           pool = get_texture_pool()
           for f in self._pinned:
               pool.release(f)
           self._pinned.clear()
           self._taps.clear()
   ```

3. **Wire into `LayerManager`:**
   - Add `self._tap_configs: list[TapConfig] = []` and `self._tap_registry = TapRegistry()`
   - In `composite_layers()`:
     - At start of frame: `self._tap_registry.clear()`
     - After `apply_layer_effects()` for each layer: fire `LayerProcessed` taps
     - After each blend step in the compositor loop: fire `CompositeAfterN` taps
   - Expose `register_tap(config: TapConfig)` and `unregister_tap(tap_id: str)` methods

4. **Connect to SliceManager / OutputManager:**
   - `OutputManager` queries `TapRegistry.get(tap_id)` to route slice outputs
   - Slice→Tap mapping stored in `SliceManager`

---

### STEP 3 — JIT StackSignature + LRU Cache (Q2)

**Impact:** Replaces raw-string cache key in `Renderer`. Non-breaking (cache hit logic improves). JIT merged-pass is the final step.

**Files to change:**
- `src/modules/gpu/renderer.py` — replace `dict[str, ...]` with `StackSignature`-keyed LRU
- New: `src/modules/gpu/stack_signature.py`

**Concrete steps:**

1. **`stack_signature.py`**:
   ```python
   import hashlib
   from dataclasses import dataclass
   from functools import cached_property
   from typing import List

   @dataclass(frozen=True)
   class EffectEntry:
       effect_id: str
       version: str
       defines: frozenset[str] = frozenset()

   class StackSignature:
       """
       Immutable identity of an effect stack for JIT shader cache keying.
       Contains effect IDs, versions, order (including duplicates).
       """
       def __init__(self, effects: list, pipeline_version: str = '1.0-linear-straight'):
           self._entries = tuple(
               EffectEntry(
                   effect_id=e.METADATA.get('id', type(e).__name__),
                   version=str(e.METADATA.get('version', '1.0')),
               )
               for e in effects
           )
           self._pipeline_version = pipeline_version

       @cached_property
       def hash(self) -> str:
           key = repr(self._entries) + self._pipeline_version
           return hashlib.sha256(key.encode()).hexdigest()[:16]

       def build_merged_glsl(self) -> str | None:
           """
           Attempt to merge all effect apply() functions into one GLSL pass.
           Returns None if any effect does not provide get_apply_glsl().
           """
           parts = []
           for entry in self._entries:
               # Future: each effect plugin provides get_apply_glsl() snippet
               # For now: returns None (falls back to per-draw-call ping-pong)
               return None
           # TODO Phase 3: assemble merged GLSL from snippets
           return None

       def __eq__(self, other):
           return isinstance(other, StackSignature) and self.hash == other.hash

       def __hash__(self):
           return hash(self.hash)
   ```

2. **Modify `Renderer`** — add LRU limit (default 256 entries):
   ```python
   from collections import OrderedDict
   _LRU_LIMIT = 256

   class Renderer:
       def __init__(self, ctx):
           ...
           self._programs: OrderedDict[str, tuple] = OrderedDict()  # LRU

       def _get_program(self, frag_source: str):
           if frag_source in self._programs:
               self._programs.move_to_end(frag_source)  # LRU touch
               return self._programs[frag_source]
           prog, vao = self._compile(frag_source)
           self._programs[frag_source] = (prog, vao)
           if len(self._programs) > _LRU_LIMIT:
               oldest_key, (p, v) = self._programs.popitem(last=False)
               v.release(); p.release()
               logger.debug(f"Renderer: LRU evicted shader ({len(self._programs)} cached)")
           return self._programs[frag_source]
   ```

3. **Future (Phase 3):** When all required effects have `get_apply_glsl()`, use `StackSignature.build_merged_glsl()` in `apply_layer_effects()` to replace the ping-pong loop with a single merged draw call. The `StackSignature.hash` becomes the cache key.

---

## Key Files Reference

| File | Role |
|---|---|
| `src/modules/gpu/frame.py` | GPUFrame: float32 texture + FBO, upload/download |
| `src/modules/gpu/renderer.py` | Renderer: program cache, quad render, `render()` |
| `src/modules/gpu/texture_pool.py` | TexturePool: zero-alloc warmup, acquire/release |
| `src/modules/gpu/context.py` | ModernGL standalone context, thread-affine |
| `src/modules/gpu/artnet_sampler.py` | ArtNet GPU compute sampler (SSBO) |
| `src/modules/gpu/ssbo_downloader.py` | Frame download via compute shader (avoids AMD 111ms stall) |
| `src/modules/gpu/shaders/blend.frag` | Multi-layer compositor (7 blend modes) |
| `src/modules/player/layers/manager.py` | apply_layer_effects() + composite_layers() |
| `src/modules/player/core.py` | Player state machine, render loop |
| `src/modules/player/transitions/manager.py` | TransitionManager with GPU+CPU path |
| `src/modules/gpu/transition_renderer.py` | GPUTransitionRenderer (fade implemented) |
| `src/modules/performance/profiler.py` | PerformanceProfiler (10 stages) |
| `plugins/plugin_base.py` | PluginBase ABC, METADATA/PARAMETERS schema |
| `docs/GPU_BLEND_TRANSITION_PLAN.md` | Phase 1 GPU blend/transition plan |
| `docs/GPU_PIPELINE_SINGLE_DOWNLOAD.md` | Single-download architecture (implemented) |
| `docs/PREVIEW_PULL_MODEL.md` | Preview SSBO pull model (pending) |
