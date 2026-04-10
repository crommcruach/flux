# GPU Output Routing — Implementation Plan

**Status**: Planning  
**Priority**: High — eliminates ~26 ms/frame SSBO download for all non-recording outputs  
**Scope**: Output routing system, layer manager, GPU shaders  
**Approach**: Full GPU — CPU output paths removed entirely

---

## 1. Problem Statement

### Current CPU pipeline (every frame, for every output)

```
composite GPUFrame (live, ~6 MB on GPU)
  │
  ├── preview_gpu_hook() fires here  ← correct, no download
  │
  └── SSBO download (map_sync)  ~26 ms  ← full 1080p forced by output_manager
        │
        └── OutputManager.update_frame(numpy 1080p)
              │
              for each output:
                ├── _get_frame_for_output()
                │     ├── SliceManager.get_slice()
                │     │     ├── cv2 crop / warpAffine / warpPerspective
                │     │     ├── numpy soft-edge gradient mask
                │     │     ├── numpy float32 colour grade
                │     │     └── cv2.flip mirror
                │     └── returns sliced numpy array
                │
                ├── DisplayOutput.queue_frame(numpy)
                │     └── pushes numpy to GLFW → re-uploads to GPU  (wasted round-trip)
                │
                └── VirtualOutput.queue_frame(numpy 1080p)
                      └── stores 6 MB frame for preview API
```

**Root problems:**
- Full 1080p SSBO download triggered even when only a 200×200 slice is needed
- DisplayOutput downloads then re-uploads (GPU→CPU→GPU round-trip)
- All slice maths (crop, rotation, perspective, colour grade, mirror, soft edge) runs on CPU via OpenCV/NumPy
- A 26 ms floor on latency is added to every frame regardless of output type

---

## 2. GPU / CPU Transfer Cost Budget

**Rule: never upload or download unless there is no GPU-side alternative.**  
Every GPU↔CPU boundary is a synchronisation point that stalls the pipeline.

### Measured costs (AMD Radeon RX 6600)

| Transfer | Direction | Size | Cost | Notes |
|---|---|---|---|---|
| SSBO `buffer.read()` (map_sync) | GPU → CPU | 1080p = ~6 MB | ~26 ms | Only viable GPU→CPU path on this AMD driver |
| Texture `texture.read()` | GPU → CPU | any | **0 bytes — always returns zeros** | AMD driver bug #2 — do not use |
| `fbo.read(dtype='u1')` | GPU → CPU | any | **broken** | AMD driver bug — do not use |
| SSBO `buffer.read()` | GPU → CPU | 200×200 = ~160 KB | ~0.15 ms | Acceptable for small slices |
| `buffer.write()` (numpy → SSBO) | CPU → GPU | 1080p = ~6 MB | ~4–8 ms | Avoid per-frame; pre-upload static data once |
| `texture.write()` | CPU → GPU | any | ~same as SSBO write | Avoid per-frame |
| WGL texture share (`push_gpu_frame`) | GPU → GPU | 1080p | ~0 ms | Zero-copy, shared context |
| ArtNetGPUSampler SSBO | GPU → CPU | N×4 bytes | < 0.1 ms | Only LED positions sampled |
| PreviewDownscaler SSBO | GPU → CPU | 320p JPEG | ~2 ms | Existing triple-buffer ring |

### Decision rules

```
Need to display on screen?
  → use WGL GPU texture share (push_gpu_frame) — 0 ms, no download

Need a virtual/CPU output with a slice?
  → GPU render slice first, then SSBO download of slice dimensions only

Have an upload to do (static LUT, geometry, etc.)?
  → upload once on setup, reuse the SSBO/texture every frame

Want to read a texture directly?
  → Don't. texture.read() returns zeros on this AMD driver. Use SSBO only.

Tempted to do GPU→CPU→GPU (upload result back after CPU work)?
  → Always wrong. Do the work in a shader instead.
```

### What this means for the output routing design

- `DisplayOutput` receives a `GPUFrame` and calls `push_gpu_frame()` — no download ever
- `VirtualOutput` GPU-renders the slice first, then downloads only slice dimensions
- `OutputSliceRenderer` keeps all geometry, crop, grade, and mirror work in the WGSL shader — no numpy
- `_last_layer_gpu_frames` dict stores `GPUFrame` refs — zero copy, zero transfer, just a Python dict lookup
- The old `update_frame(numpy)` path is removed entirely

---

## 3. Target Architecture

### GPU-first pipeline

```
composite GPUFrame (live, never downloaded)
  │
  ├── preview_gpu_hook()       → 320p JPEG encode, exists, unchanged
  │
  └── output_gpu_hook() [NEW]
        │
        OutputManager.update_gpu_frame(composite_gpu, layer_manager)
          │
          for each output:
            ①  resolve_source_gpu()     → source_gpu (GPUFrame ref, 0 ms)
            ②  OutputSliceRenderer.render(source_gpu, slice_def)
                 → one wgpu render pass, output = slice_def.width × slice_def.height
                 → pooled GPUFrame (no allocation per frame)
            ③a  DisplayOutput.receive_gpu_frame(slice_gpu)
                 → GLFW WGL push_gpu_frame, 0 download
            ③b  VirtualOutput.receive_gpu_frame(slice_gpu)
                 → SSBO download of slice only (~0.15 ms for 200×200)
            ③c  ArtNetOutput.receive_gpu_frame(slice_gpu)
                 → ArtNetGPUSampler.sample(), N×4 bytes only
```

### Download cost comparison

| Scenario | Before | After |
|---|---|---|
| DisplayOutput + WGL sharing | 26 ms SSBO | 0 ms (GPU hook) |
| VirtualOutput + MJPEG preview | 26 ms SSBO | ~2 ms (480p existing downscaler) |
| 200×200 slice → virtual output | 26 ms SSBO (full 1080p) | ~0.15 ms (200×200 only) |
| Art-Net, 512 LEDs, from slice | 26 ms + CPU iterate | N×4 = 2 KB (ArtNetGPUSampler) |

---

## 4. Source Routing Model

Every output config has a `source` field:

| `source` value | GPU texture returned | Cost |
|---|---|---|
| `"canvas"` | Final composite GPUFrame | 0 ms — direct ref |
| `"layer:0"` | Layer 0 GPUFrame (post-effects) | 0 ms — dict ref |
| `"layer:1"` | Layer 1 GPUFrame (post-effects) | 0 ms — dict ref |
| `"layer:1:merged"` | Layers 0+1 composited | ~0.3 ms — 1 render pass |
| `"clip:<uuid>"` | Specific clip's raw GPU texture | 0 ms — dict ref |

### Example output config (session_state.json — no schema change)

```json
{
  "outputs": {
    "virt_layer1": {
      "id": "virt_layer1",
      "type": "virtual",
      "source": "layer:1",
      "slice": "slice2",
      "enabled": true
    },
    "main_display": {
      "id": "main_display",
      "type": "display",
      "source": "canvas",
      "slice": "slice1",
      "enabled": true,
      "monitor_index": 0,
      "fullscreen": true
    }
  }
}
```

### Full example: layer-isolated + composition outputs

```
layer 0  ─────────────────────────────────────────────────────┐
layer 1  ─── source:"layer:1" → slice2 → virt_layer1 output  │ ← layer 1 isolated
layer 2  ─────────────────────────────────────────────────────┘
composition ─── source:"canvas" → slice1 → main_display      ← all layers composited
```

---

## 5. New Components

### 4.1 `src/modules/gpu/shaders/output_slice.wgsl` (New)

Single-pass shader replacing all of `SliceManager.get_slice()`:

**Operations (all in UV space, one render pass):**
- **Crop**: UV offset + scale from `(x/cw, y/ch, w/cw, h/ch)`
- **Rotation**: 2D rotation around crop centre
- **Perspective warp**: 3×3 homography matrix (9 float uniforms)
- **Mirror/flip**: UV axis flip flag (0=none, 1=horizontal, 2=vertical, 3=both)
- **Colour grade**: brightness, contrast, R/G/B channel offsets
- **Soft edge**: per-pixel edge distance → alpha gradient, multiplied into output alpha

**Uniform slots (u.data — 64 × f32):**

```
[0]     use_perspective   int (0=crop+rotate, 1=full homography)
[1,2]   uv_offset         vec2  (x/cw, y/ch)
[3,4]   uv_scale          vec2  (w/cw, h/ch)
[5]     rotation_rad      f32   rotation around crop centre
[6]     mirror_flags      int   bitfield: bit0=flip_u, bit1=flip_v
[7]     soft_edge_px      f32   pixels (0=disabled)
[8,9]   canvas_size       vec2  (cw, ch) for pixel→uv soft edge
[10]    brightness        f32   -1..+1 (val/255.0)
[11]    contrast          f32   multiplier 0..3 (default 1.0)
[12]    red               f32   -1..+1 (val/255.0)
[13]    green             f32   -1..+1 (val/255.0)
[14]    blue              f32   -1..+1 (val/255.0)
[15..23] homography[9]   f32   row-major 3×3 for perspective warp
```

**Output texture format**: `rgba8unorm` — matches all existing GPUFrames.
**Output texture size**: `slice_def.width × slice_def.height` — NOT canvas size.

---

### 4.2 `src/modules/gpu/output_slice_renderer.py` (New)

```python
class OutputSliceRenderer:
    """
    Renders a source GPUFrame → slice_def-sized GPUFrame using output_slice.wgsl.

    All operations (crop, rotate, perspective, colour grade, mirror, soft edge)
    happen in a single render pass.  Output textures are pooled by (w, h).

    Lifecycle:
        renderer = OutputSliceRenderer()
        slice_gpu = renderer.render(source_gpu, slice_def, canvas_w, canvas_h)
        # slice_gpu is a pooled GPUFrame — valid until next render() call
        # for this slice, or until release() is called.
    """

    def render(
        self,
        source: GPUFrame,
        slice_def: SliceDefinition,
        canvas_w: int,
        canvas_h: int,
    ) -> GPUFrame:
        """One render pass: source (canvas-res) → output (slice-res) texture."""

    def release_all(self) -> None:
        """Release all pooled output textures back to texture pool."""
```

**Key implementation details:**
- Uses `get_texture_pool()` to acquire/release output textures (no per-frame GPU allocation)
- Texture pool keyed by `(slice_def.width, slice_def.height)`
- Uses `get_renderer()` with `output_slice.wgsl` — pipeline cached by wgsl source (already handled by `Renderer`)
- For `slice == 'full'` (no crop, no adjustments) → returns `source` directly (zero cost)
- For perspective warp: builds homography from `slice_def.transformCorners` into 9 uniforms
- Batch-friendly: multiple slices can share a single command encoder (future optimisation)

---

### 4.3 `src/modules/player/outputs/base.py` (Modify)

Replace CPU interface with GPU interface on `OutputBase`:

```python
class OutputBase(ABC):

    @abstractmethod
    def receive_gpu_frame(self, gpu_frame: 'GPUFrame') -> None:
        """
        Consume a sliced GPU texture.

        Called from the render thread while the GPU context is current.
        The gpu_frame is a pooled texture — caller retains ownership,
        do NOT release or store it beyond this call unless you blit it.
        """
        ...
```

`send_frame(numpy)` and the thread queue are removed. All outputs implement `receive_gpu_frame()`.

---

### 4.4 `src/modules/player/outputs/manager.py` (Modify)

Replace `update_frame(numpy)` with `update_gpu_frame()`:

```python
def update_gpu_frame(
    self,
    composite_gpu: 'GPUFrame',
    layer_manager,
    current_clip_id: Optional[str] = None,
) -> None:
    """
    GPU primary path.  Called from the output GPU hook while the
    composite texture is still live on the render thread.

    For each enabled output:
      1. Resolve source GPUFrame (canvas, layer:N, clip:uuid)
      2. Run OutputSliceRenderer if slice != 'full'
      3. Call output.receive_gpu_frame(slice_gpu)
      4. If receive_gpu_frame() returns False → fall back to CPU
         (download slice_gpu → queue_frame(numpy))
    """
```

**Source resolution (GPU-side):**

```python
def _resolve_source_gpu(
    self,
    source: str,
    composite_gpu: 'GPUFrame',
    layer_manager,
) -> 'GPUFrame':
    if source == 'canvas' or not source:
        return composite_gpu
    if source.startswith('layer:'):
        parts = source.split(':')
        idx = int(parts[1])
        mode = parts[2] if len(parts) > 2 else 'isolated'
        if mode == 'merged':
            return layer_manager.get_partial_composite_gpu(idx) or composite_gpu
        frames = getattr(layer_manager, '_last_layer_gpu_frames', {})
        return frames.get(idx, composite_gpu)
    if source.startswith('clip:'):
        uuid = source.split(':')[1]
        f = getattr(layer_manager, 'get_clip_gpu_frame', lambda _: None)(uuid)
        return f or composite_gpu
    return composite_gpu
```

`update_frame(numpy)` is **removed**. The GPU path is the only path.

---

### 4.5 `src/modules/player/layers/manager.py` (Modify)

#### 4.5.1 Retain per-layer GPU frame refs

After `apply_layer_effects(..., stay_on_gpu=True)` is called for each layer inside `composite_layers()`, store the result:

```python
# New member in __init__:
self._last_layer_gpu_frames: dict[int, 'GPUFrame'] = {}

# In composite_layers(), after each layer's effects are applied:
# (existing: overlay_frame = self.apply_layer_effects(layer, ..., stay_on_gpu=True))
self._last_layer_gpu_frames[layer_index] = overlay_frame
# lightweight — one dict write, no GPU work, no copy
```

These refs are valid until the next frame overwrites them.  
Outputs consuming `source: layer:N` read from this dict — zero cost.

#### 4.5.2 Add `_output_gpu_hook` alongside existing hooks

```python
# New member in __init__:
self._output_gpu_hook = None

# New setter:
def set_output_gpu_hook(self, callback) -> None:
    """
    Register callback(composite_gpu, layer_manager) fired after compositing
    while the composite texture is still live.  Used by OutputManager.
    """
    self._output_gpu_hook = callback

# In composite_layers(), alongside existing hook calls:
if self._output_gpu_hook is not None:
    try:
        self._output_gpu_hook(master_frame, self)
    except Exception as _e:
        logger.error(f"output_gpu_hook error: {_e}")
```

Hook call order (all fire before the SSBO download decision):
```
1. _preview_gpu_hook()     ← JPEG encode (existing)
2. _display_gpu_hook()     ← GLFW WGL (existing)
3. _artnet_gpu_hook()      ← LED sampling (existing)
4. _transition_gpu_hook()  ← transition A-buffer (existing)
5. _output_gpu_hook()      ← output routing (NEW)
```

#### 4.5.3 Add `get_partial_composite_gpu(max_idx)` (optional, for `merged` mode)

```python
def get_partial_composite_gpu(self, max_layer_index: int) -> Optional['GPUFrame']:
    """
    Composite layers 0..max_layer_index into a new GPUFrame.
    Used by output source "layer:N:merged".
    One extra render pass per call — only executed when merged mode requested.
    """
```

---

### 4.6 `src/modules/player/outputs/plugins/display_output.py` (Rewrite)

Implement `receive_gpu_frame()`:

```python
    def receive_gpu_frame(self, gpu_frame: 'GPUFrame') -> None:
        """Zero-copy: blit slice GPU texture → GLFW without any CPU download."""
        from ....gpu.glfw_display import get_glfw_display
        get_glfw_display().push_gpu_frame(gpu_frame)
```

> `push_gpu_frame()` already exists on `GLFWDisplay` — used by the existing  
> `_display_hook` in `core.py`.  No GLFW changes needed.

---

### 4.7 `src/modules/player/outputs/plugins/virtual_output.py` (Rewrite)

Implement `receive_gpu_frame()`:

```python
    def receive_gpu_frame(self, gpu_frame: 'GPUFrame') -> None:
        """
        Download only the slice (e.g. 200×200 = 160 KB) instead of full 1080p
        (6 MB).  ~0.15 ms vs ~26 ms.  Stores result as latest_frame for the
        preview API.
        """
        raw = gpu_frame.download()   # slice dimensions only
        with self.frame_lock:
            self.latest_frame = raw
        with self.stats_lock:
            self.frames_sent += 1
```

---

### 4.8 `src/modules/player/core.py` (Modify)

#### 4.8.1 Register output GPU hook

In `_init_display_gpu_hook()` or a new `_init_output_gpu_hook()` method:

```python
def _init_output_gpu_hook(self) -> None:
    """Register the output GPU hook once output_manager is ready."""
    if self.output_manager is None:
        return

    def _output_hook(composite: 'GPUFrame', layer_manager) -> None:
        if self.output_manager:
            self.output_manager.update_gpu_frame(
                composite_gpu=composite,
                layer_manager=layer_manager,
                current_clip_id=self.current_clip_id,
            )

    self.layer_manager.set_output_gpu_hook(_output_hook)
```

Call `_init_output_gpu_hook()` at the end of `__init__()`, after `output_manager` is set up.

#### 4.8.2 Remove `needs_cpu_frame` special-cases

The existing `needs_cpu_frame` property special-cases for `DisplayOutput` (`_display_gpu_active`) and `VirtualOutput` (`_preview_downscaler`) are **removed**. All outputs are now GPU-only; the property simplifies to:

```python
@property
def needs_cpu_frame(self) -> bool:
    return False  # all outputs served by output_gpu_hook
```

---

## 6. File Change Summary

| File | Type | Change |
|---|---|---|
| `gpu/shaders/output_slice.wgsl` | **New** | Single-pass crop/grade/mirror/soft-edge shader |
| `gpu/output_slice_renderer.py` | **New** | `OutputSliceRenderer` with texture pool |
| `player/outputs/base.py` | **Rewrite** | Replace CPU queue/send_frame with `receive_gpu_frame()` |
| `player/outputs/manager.py` | **Rewrite** | Replace `update_frame()` with `update_gpu_frame()` + `_resolve_source_gpu()` |
| `player/outputs/plugins/display_output.py` | **Rewrite** | Implement `receive_gpu_frame()` via WGL push |
| `player/outputs/plugins/virtual_output.py` | **Rewrite** | Implement `receive_gpu_frame()` via slice SSBO download |
| `player/outputs/slices.py` | **Keep as data store** | `SliceManager` and `SliceDefinition` retained; CPU slice extraction removed |
| `player/layers/manager.py` | **Modify** | `_last_layer_gpu_frames`, `_output_gpu_hook`, setter, `get_partial_composite_gpu()` |
| `player/core.py` | **Modify** | `_init_output_gpu_hook()`, `needs_cpu_frame` simplified to `return False` |

**API — one new read-only GET endpoint required:**  
`GET /api/player/{player}/layers` — returns active layer list (index, name, visible).  
Needed so the frontend can populate the layer source picker.  
The existing `PUT /api/outputs/{player}/{id}/source` already accepts any string — `"layer:1"` works today.

**UI — one small addition:**  
One `<select>` element in the output config panel populated from the new `/layers` endpoint, calling the existing `updateOutputSource()` function.

---

## 7. Implementation Order

Each step is independently testable and non-breaking.

### Step 1 — Shader: `output_slice.wgsl`
Write and unit-test the WGSL shader.  
Test: render a known-colour canvas texture at various crop/rotate/grade/mirror configs, verify output pixel values.

### Step 2 — `OutputSliceRenderer`
Wire shader into a Python class using `get_renderer()` + `get_texture_pool()`.  
Test: render a 1920×1080 GPUFrame → 400×300 slice with known crop coords; download the result and verify dimensions and pixel values.

### Step 3 — `OutputBase` rewrite
Remove CPU thread queue and `send_frame(numpy)`. Add abstract `receive_gpu_frame()`.

### Step 4 — `LayerManager` changes
- Add `_last_layer_gpu_frames` dict population in `composite_layers()`
- Add `_output_gpu_hook` + `set_output_gpu_hook()`
- `get_partial_composite_gpu()` (for `merged` mode — can be deferred)

### Step 5 — `OutputManager.update_gpu_frame()`
Replace `update_frame()` with `update_gpu_frame()`.  
Test: enable one VirtualOutput with a 400×300 slice; verify `latest_frame` is 400×300 after a render pass.

### Step 6 — `DisplayOutput.receive_gpu_frame()`
Implement to call `push_gpu_frame()`.  
Test: enable DisplayOutput; confirm zero SSBO downloads during playback.

### Step 7 — `VirtualOutput.receive_gpu_frame()`
Override to call `gpu_frame.download()` on the small slice.  
Test: confirm `latest_frame` dimensions match slice, not canvas.

### Step 8 — `Player._init_output_gpu_hook()` + `needs_cpu_frame = False`
Wire everything together.  
Test: full pipeline, zero SSBO downloads with canvas→display + layer:1→virtual config.

---

## 8. Open Questions — Agree Before Implementation

**1. Layer endpoint — include GPU frame availability status?**  
`_last_layer_gpu_frames` is only populated while a clip is playing. The API could return `"has_frame": true/false` to let the UI warn when selecting a layer source with no active clip. Prevents silent black-output bugs.  
Recommendation: include it.

**2. `merged` mode (`layer:N:merged`) — in scope now?**  
Requires `get_partial_composite_gpu()` (one extra render pass). Can ship later.  
Recommendation: defer; add `(merged)` variants as follow-up.

**3. `clip:<uuid>` source — in scope?**  
Requires the clip system to retain GPU frames beyond the composite pass — more invasive.  
Recommendation: defer.

## 9. Notes on Layer GPU Frame Lifetime  
These textures are **not released** between hook invocation and the next `composite_layers()` call.  
The `output_gpu_hook` fires while the render thread holds the GL context, before any pool release — so the textures are guaranteed live during the hook.  

If an output's `receive_gpu_frame()` needs to retain the texture beyond the hook (e.g. async encode), it must acquire a fresh texture from the pool and blit the slice into it. The standard case (synchronous download in `VirtualOutput`) does not need this.

---

## 10. Deferred / Out of Scope

- **`merged` mode** (`source: "layer:N:merged"`) — can ship after initial GPU routing; `get_partial_composite_gpu()` is not required for step 1.
- **Art-Net output via `receive_gpu_frame()`** — `ArtNetGPUSampler` already samples from composite; per-slice Art-Net routing is a separate feature.
- **Multi-slice composition mode** (`output.config['composition']`) — currently CPU-only in `_render_composition()`; GPU port deferred.
- **Clip-source GPU routing** (`source: "clip:<uuid>"`) — requires clip system to retain GPU frames; deferred.
