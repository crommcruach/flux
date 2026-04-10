# GPU Pipeline: Single-Download Architecture

## Problem Statement

The current effect loop in `src/modules/player/layers/manager.py` downloads the frame from GPU to CPU **after every single effect**. With 4 effects × 2 layers this means 8 GPU→CPU downloads per frame. On the AMD iGPU each download costs ~50ms due to the OpenGL pipeline drain bug (see `AMD_DRIVER_BUGS.md`).

### Current broken flow (simplified):
```
Layer 1:
  upload frame → GPU
  effect 1: shader → DOWNLOAD to numpy   ← 50ms
  effect 2: upload numpy → shader → DOWNLOAD   ← 50ms
  effect 3: upload numpy → shader → DOWNLOAD   ← 50ms
  effect 4: upload numpy → shader → DOWNLOAD   ← 50ms

Layer 2: same × 4 more downloads

CPU composite (cv2.addWeighted)  ← forced because layers returned numpy

→ preview JPEG encode
→ ArtNet pixel sample
```
**Total: ~400ms per frame = ~2.5 fps**

### Root Cause

In `_apply_layer_effects()` (manager.py ~line 517), the GPU texture variables `src_gpu` / `dst_gpu` are created and **released inside each loop iteration**. After each effect, `frame = dst_gpu.download()` writes a numpy array back to `frame`. The next iteration then uploads that numpy array again. Nobody chained the textures across iterations.

---

## Target Architecture

```
Layer 1:
  upload frame → GPU once
  effect 1 shader → ping-pong GPU texture (no download)
  effect 2 shader → ping-pong GPU texture (no download)
  effect 3 shader → ping-pong GPU texture (no download)
  effect 4 shader → ping-pong GPU texture (no download)
  → result: GPU texture (still on GPU)

Layer 2: same → GPU texture

GPU composite shader (blend Layer1 + Layer2 textures)  ← already implemented, just disabled
→ ONE download to numpy

→ JPEG encode → WebSocket preview
→ ArtNet pixel sample (from this numpy, async, separate thread)
```
**Total: ~50ms on AMD iGPU (~20fps). On any discrete GPU: ~1-3ms (30fps+)**

---

## Why One Download Is Still Needed

- **Preview → WebSocket**: needs JPEG encoding via `cv2.imencode()` which requires numpy. This is unavoidable but only needs to happen ONCE per frame after full compositing.
- **ArtNet**: can sample from the final numpy frame asynchronously. Does NOT drive the pipeline timing.

The download is not avoidable entirely — but reducing it from N×downloads to 1 is the entire performance win.

---

## Files To Change

### 1. `src/modules/player/layers/manager.py` — `apply_layer_effects()`

**Current code (lines 473–544):**
```python
for effect in layer.effects:
    if not effect.get('enabled', True):
        continue
    instance = effect['instance']
    try:
        shader_src = instance.get_shader()
        if shader_src is not None:
            ctx = get_context()
            pool = get_texture_pool()
            renderer = get_renderer()
            src_gpu = pool.acquire(w, h)
            dst_gpu = pool.acquire(w, h)
            try:
                src_gpu.upload(frame)        # ← uploads numpy every iteration
                renderer.render(...)
                frame = dst_gpu.download()   # ← downloads after EVERY effect
            finally:
                pool.release(src_gpu)
                pool.release(dst_gpu)
            continue
        frame = instance.process_frame(frame, ...)
    except Exception as e:
        ...
return frame
```

**Target code:**
```python
pool = get_texture_pool()
renderer = get_renderer()

# Upload once before the loop
current_gpu = pool.acquire(w, h)
current_gpu.upload(frame)
uploaded_to_gpu = True

try:
    for effect in layer.effects:
        if not effect.get('enabled', True):
            continue
        instance = effect['instance']
        try:
            shader_src = instance.get_shader()
            if shader_src is not None:
                dst_gpu = pool.acquire(w, h)
                try:
                    renderer.render(
                        frag_source=shader_src,
                        target_fbo=dst_gpu.fbo,
                        uniforms=instance.get_uniforms(frame_w=w, frame_h=h),
                        textures={'inputTexture': (0, current_gpu)},
                    )
                    pool.release(current_gpu)
                    current_gpu = dst_gpu   # ping-pong, no download
                except Exception:
                    pool.release(dst_gpu)
                    raise
                continue
            # CPU effect: must download, process, re-upload
            frame = current_gpu.download()
            frame = instance.process_frame(frame, source=layer.source, player=None)
            current_gpu.upload(frame)
        except Exception as e:
            plugin_id = effect.get('id', 'unknown')
            logger.error(f"❌ [{player_name}] Layer {layer.layer_id} effect {plugin_id} error: {e}")

    # Download ONCE at the end
    frame = current_gpu.download()
finally:
    pool.release(current_gpu)

return frame
```

### 2. `src/modules/player/layers/manager.py` — `composite_layers()`  (lines 711–920)

The GPU compositor shader is already implemented and tested (14/14 tests pass) but currently bypassed in favour of `cv2.addWeighted` CPU fallback. Once `apply_layer_effects()` returns a GPU-chained result, the compositor should also stay on GPU to avoid an intermediate download.

**Current state:** `self._use_gpu` flag on the `LayerManager` forces the CPU path because "GPU readback is 50ms". This was measured when per-effect downloads were still happening. With chaining fixed, the GPU compositor only costs the shader execution time (microseconds), and the download happens once after composite.

Re-enable the GPU compositor path. The `composite.download()` call at the end of `composite_layers()` is the single final download.

---

## Per-Layer Output Assignment (Multi-Layer Scenario)

When outputs are assigned to individual layers (e.g. "Layer 1 → Output A", "Layer 2 → Output B"), each layer's processed frame must be accessible. This is solvable without extra full-frame CPU copies because **the per-layer GPU textures already exist separately before the compositor merges them**.

### Key insight

`_apply_layer_effects()` currently returns numpy. In the new architecture it should return the **GPU texture handle** instead. The compositor receives a list of GPU texture handles, blends them on GPU, and the final composite is the only thing downloaded.

The per-layer textures are still alive in GPU memory between `_apply_layer_effects()` finishing and `pool.release()` being called — this window is where output sampling happens.

### Option A — ArtNet pixel sampler shader (preferred, zero extra CPU copy)

**User's idea:** Write a dedicated shader that knows the LED UV positions, samples the final composited GPU texture at exactly those pixels, and writes the RGB results into a small buffer. The ArtNet listener reads from that buffer — it never touches the full frame at all.

**Concrete design:**

```
Final composite GPU texture (1080p, stays on GPU)
        ↓
Pixel sampler compute shader:
  - Input:  sampler2D finalTexture
  - Input:  SSBO/UBO ledPositions[]  ← N×(u, v) floats, preloaded at startup from routing config
  - Output: SSBO ledColors[]         ← N×3 bytes (RGB)
  - Dispatch: 1 work group of N invocations, each reads 1 pixel
        ↓
Read back ledColors SSBO: N×3 bytes  ← microseconds, not 50ms (tiny data, no pipeline drain)
        ↓
Write to shared in-memory pixel buffer (not session_state.json — in-memory only)
        ↓
ArtNet sender reads from pixel buffer → builds DMX universe → sends UDP
```

**The shader itself is trivial:**
```glsl
#version 430
layout(local_size_x = 256) in;

uniform sampler2D finalTexture;

layout(std430, binding = 0) readonly buffer LedPositions {
    vec2 positions[];   // UV coords, precomputed from routing config
};
layout(std430, binding = 1) writeonly buffer LedColors {
    uint colors[];      // packed RGB: R | (G<<8) | (B<<16)
};

void main() {
    uint i = gl_GlobalInvocationID.x;
    if (i >= positions.length()) return;
    vec4 c = texture(finalTexture, positions[i]);
    colors[i] = uint(c.r * 255.0)
              | (uint(c.g * 255.0) << 8)
              | (uint(c.b * 255.0) << 16);
}
```

**Key properties:**
- Runs on GPU, dispatched once per frame after composite
- UV positions loaded once at startup (or when routing config changes)
- Readback: 512 LEDs × 4 bytes = 2 KB — the AMD 50ms stall is for megabytes of full-frame pixel data; a 2 KB SSBO read is unaffected
- ArtNet sender is completely decoupled: reads from the shared pixel buffer at its own rate
- Works per-layer too: dispatch the shader once per layer that has outputs assigned, passing that layer's texture and its LED positions

**Shared pixel buffer (in-memory, not JSON):**
```python
# In routing_bridge.py or a new artnet_pixel_buffer.py
_pixel_buffer: dict[str, np.ndarray] = {}  # layer_id → (N, 3) uint8 RGB

def update_pixels(layer_id: str, rgb_data: np.ndarray):
    _pixel_buffer[layer_id] = rgb_data      # written by GPU sampler after each frame

def get_pixels(layer_id: str) -> np.ndarray | None:
    return _pixel_buffer.get(layer_id)      # read by ArtNet sender
```

This completely eliminates the full-frame numpy copy from the video pipeline. ArtNet becomes a pure side-consumer of a tiny pre-sampled buffer.

---

### Option A — GPU compute shader sampling (preferred, zero extra CPU copy) [original summary]

After all layer effects complete and before releasing layer textures, dispatch a small compute shader (OpenGL 4.3+, available on this machine with OGL 4.6) that reads specific UV pixel positions from each layer texture and writes RGB values into a tiny SSBO (Shader Storage Buffer Object).

```
Layer 1 GPU texture  →  compute shader reads N pixel UVs  →  SSBO (N×3 bytes)
Layer 2 GPU texture  →  compute shader reads N pixel UVs  →  SSBO (N×3 bytes)
                                                               ↓
                                              read back SSBO  ~microseconds (tiny data)
                                              no full-frame download needed
```

- Cost for 512 LEDs: 512 × 3 = 1536 bytes readback — negligible, no pipeline drain stall
- The 50ms AMD stall only occurs for full-frame `glGetTexImage` / `glReadPixels` — small SSBO reads are unaffected
- UV coordinates for LED positions are precomputed once from the output routing config

### Option B — Selective layer download (simple fallback)

Only download a layer texture to numpy if at least one output is assigned to that layer. No output assigned = texture stays on GPU, zero download cost.

```python
for layer_gpu_tex, layer in zip(layer_textures, layers):
    if layer.has_assigned_outputs():
        layer_numpy = layer_gpu_tex.download()   # only when needed
        send_to_outputs(layer.outputs, layer_numpy)
    # else: skip, no download
```

Worst case (all layers have outputs): N downloads. But these are explicit, controlled, and only happen when the user has actually configured an output on that layer — not every frame unconditionally.

### Proposed `composite_layers()` signature change

Currently `_apply_layer_effects()` returns `numpy`. Change it to return a `GPUFrame` / texture handle:

```python
# Before:
frame: np.ndarray = self._apply_layer_effects(layer, frame, player_name)

# After:
gpu_tex: GPUFrame = self._apply_layer_effects_gpu(layer, frame, player_name)
# gpu_tex stays alive for output sampling before compositor releases it
```

The compositor then accepts a list of `GPUFrame` objects, blends them, and returns a final `GPUFrame`. Only `composite_result.download()` is called — once.

### Updated implementation checklist addition

- [ ] `apply_layer_effects()` returns `GPUFrame` (texture handle) instead of numpy
- [ ] `composite_layers()` accepts list of `GPUFrame`, composites on GPU, returns final `GPUFrame`
- [ ] Per-layer output sampling (Option A or B) happens between effects completion and compositor release
- [ ] `composite_result.download()` is the single final CPU transfer

---

## What Changes Nothing

- **ArtNet** (`routing_bridge.py`): already decoupled, receives numpy BGR from the final frame. No changes needed. The BGR→RGB fix (`rgb_frame = frame[:, :, ::-1]`) stays as-is.
- **Existing GLSL shaders**: all `.frag` files unchanged. This is pure Python loop restructuring.
- **Plugin API**: `get_shader()`, `get_uniforms()`, `process_frame()` interfaces unchanged.

---

## Hardware Reality

| Hardware | Download cost | Expected FPS (2 layers, 4 effects each) |
|---|---|---|
| AMD gfx902 iGPU (current dev machine) | ~50ms | ~20fps |
| Any discrete GPU (AMD RX, NVIDIA GTX/RTX, Intel Arc) | ~1-3ms | 30fps+ |

The AMD iGPU bottleneck is the OpenGL pipeline drain bug documented in `AMD_DRIVER_BUGS.md`. It affects `texture.read()` / `glGetTexImage` regardless of data size. This is a hardware/driver limitation only on this specific dev machine. The architecture is correct for all target deployment hardware.

---

## Implementation Checklist

- [ ] Refactor `apply_layer_effects()` in `manager.py` (lines 473–544) to ping-pong GPU textures across effect loop
- [ ] Set `self._use_gpu = True` to re-enable GPU compositor in `composite_layers()` (lines 711–920) in `manager.py`
- [ ] Verify single download path: only `composite.download()` at end of `composite_layers()`
- [ ] Test: 2 layers × 4 effects, measure frame time, confirm effects are visually applied
- [ ] Test: CPU-only effect (no shader) in middle of chain still works (download → process → re-upload)
