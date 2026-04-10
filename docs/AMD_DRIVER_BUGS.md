# AMD Driver Bugs — ModernGL / OpenGL 3.3

**GPU:** AMD Radeon  
**Driver:** 25.8.1.250617  
**OpenGL:** 3.3 Core  
**ModernGL:** 5.12.0 (headless `create_standalone_context()`)  

---

## Bug 1 — GL_RGB8 / GL_RGBA8 textures return zeros in GLSL arithmetic

**Status:** Workaround applied ✅ (headless pipeline + GLFW display output)

### Symptom
When uploading a uint8 numpy frame to a `dtype='u1'` (GL_RGB8) texture and sampling it in a fragment shader, all arithmetic on the sampled values returns `vec3(0.0, 0.0, 0.0)`. Plain `texture()` lookup appears to work but the output is wrong when any math is applied.

Also confirmed: the bug produces a **completely black screen** in a GLFW window context (`_mgl.create_context()` — not standalone). The GLFW display window received frames and logged "first frame rendered" but remained black because the GL_RGB8 texture sampler returned zeros.

### Root Cause
AMD driver bug: integer-normalized texture formats (GL_RGB8) behave incorrectly under the OpenGL 3.3 Core profile in **both** headless/standalone ModernGL contexts **and** regular GLFW window contexts. The driver returns zeros for sampled texels.

### Workaround
Use `dtype='f4'` (GL_RGB32F / float32) textures throughout:
- Upload: `np.ascontiguousarray(frame[:,:,::-1]).astype(np.float32) * (1.0/255.0)` → write float32 buffer
- Download: `texture.read()` float32 → multiply × 255 → uint8

All GPU pipeline code (`frame.py`) and the GLFW display output (`glfw_display.py`) use float32 textures exclusively.

---

## Bug 2 — `fbo.read(dtype='u1')` returns zeros from a float32 FBO

**Status:** Workaround applied ✅

### Symptom
After rendering into an FBO backed by a float32 texture, calling `fbo.read(dtype='u1')` returns a buffer of all zeros, even though the texture contains valid data.

### Root Cause
AMD driver does not correctly perform implicit float→uint8 conversion during `glReadPixels` when the FBO attachment is a float32 texture. The returned bytes are all zero.

### Workaround
Use `texture.read()` instead of `fbo.read()` to download float32 data directly, then convert manually in Python:
```python
raw = self.texture.read()                         # float32 bytes
arr = np.frombuffer(raw, dtype=np.float32).reshape(h, w, c)
np.multiply(arr, 255.0, out=self._f32_buf)
np.copyto(self._download_buf, self._f32_buf, casting='unsafe')
result = self._download_buf[:, :, ::-1].copy()    # RGB→BGR
```

---

## Bug 3 — PBO async readback stalls immediately (`fbo.read_into()`)

**Status:** Investigated, PBO path abandoned ✅

### Symptom
Using a PBO (Pixel Buffer Object) for asynchronous GPU→CPU readback via `fbo.read_into(pbo_buffer)` does not perform asynchronously. The call blocks for the full pipeline drain (~36 ms) synchronously at the `read_into()` call site, giving no benefit over synchronous `texture.read()`.

### Expected Behaviour
`fbo.read_into(pbo_buffer)` with a `PIXEL_PACK_BUFFER` should initiate a DMA transfer and return immediately, allowing the CPU to do other work while the GPU copies data. A `glFenceSync` + `glClientWaitSync` or a double-buffer scheme would then retrieve the data in a future frame with near-zero stall.

### Actual Behaviour
The driver performs the copy synchronously on `read_into()` — the GPU pipeline is drained at that point regardless. Total cost: ~127 ms per frame (read_into 36 ms + data access 91 ms).

### Conclusion
PBO is useless on this AMD driver/OS combination for this use case. Readback stays on `texture.read()` (~43 ms at 1080p) or the CPU blend path is used to avoid readback entirely.

---

## Current Performance Impact

| Operation | Cost | Status |
|---|---|---|
| `texture.read()` float32 full frame (1080p) | ~43 ms | Active download path |
| `fbo.read(dtype='u1')` | returns zeros | Abandoned |
| `fbo.read_into(pbo)` | ~127 ms (sync stall) | Abandoned |
| `cv2.addWeighted()` CPU blend (1080p, 2 layers) | ~9 ms | **Active blend path** |

### Bottom Line
GPU compositing via the shader pipeline is implemented and tested (14/14 tests pass), but the AMD readback bottleneck (~43 ms for `texture.read()`) makes per-effect GPU shader passes slower than the equivalent CPU numpy/cv2 operations for the current workload.

**Current architecture decision:** CPU blend path (`cv2.addWeighted`) stays active for layer compositing. GPU shader pipeline (transform, hue_rotate, colorize, brightness_contrast) is ready for Phase 2 but executed via CPU `process_frame()` until the readback issue is resolved or a zero-copy display path bypasses readback entirely.

---

## Bug 4 — SSBO `buffer.read()` fails with "cannot map the buffer" when GLFW display context is active

**Status:** Workaround applied ✅

### Symptom
`SSBODownloader.download()` calls `self._ssbo.read()` (i.e., `glGetBufferSubData`) after the compute shader completes. This works fine when running headless-only, but fails with `_moderngl.Error: cannot map the buffer` as soon as a GLFW display window is active in a separate thread (its own `_mgl.create_context()` context).

On subsequent frames the SSBO object becomes an `InvalidObject` (moderngl auto-releases it after the GL error), causing `bind_to_storage_buffer` to raise `AttributeError`. Because `_ensure_ssbo()` was previously called **outside** the try-except block, the thread crashed with `cannot create buffer` on the next reallocation attempt.

### Root Cause
AMD WGL driver bug: having two concurrent OpenGL contexts in the same process (headless `create_standalone_context()` + GLFW window `create_context()`) causes `glGetBufferSubData` or the underlying `glMapBufferRange` to fail on the headless context. The GLFW context creation (`wglCreateContextAttribsARB`) appears to corrupt shared WGL state.

### Workaround
`SSBODownloader` now:
1. Wraps the entire download path (including `_ensure_ssbo`) in the try-except block.
2. Resets `self._ssbo = None` + `self._ssbo_size = 0` on any GL error so the next call attempts fresh allocation.
3. After 3 consecutive errors sets `self._load_failed = True`, permanently switching to the `texture.read()` fallback for the session.

The `texture.read()` fallback is **still slow** (~43 ms / frame at 1080p) but does not crash the play loop. When the GLFW display is active, the SSBO path is effectively disabled.

---

## Potential Future Paths

- ~~OpenGL 4.5 persistent mapped buffers~~ — **TESTED AND FAILED** (see below)
- **Display output via texture sharing** — if output goes directly to an OpenGL window, readback is never needed
- **Vulkan / Vulkan interop** — bypasses the broken OpenGL readback path entirely
- **Driver update** — AMD driver 25.8.1.250617 may be patched in a future release

---

## Tested: OGL 4.6 + Persistent Mapped PBOs

**Test:** `tests/gpu/test_amd_readback_pbo.py`  
**Result: SLOWER than baseline. Strategy abandoned. ❌**

### Setup
The driver CAN provide OGL 4.6 (`create_standalone_context(require=460)`) and exposes `GL_ARB_buffer_storage`. These allow persistent mapped PBOs — the only AMD-compatible async GPU→CPU readback mechanism in OpenGL.

Strategy:
1. OGL 4.6 context
2. `glBufferStorage(GL_PIXEL_PACK_BUFFER, size, NULL, GL_MAP_READ_BIT | GL_MAP_PERSISTENT_BIT | GL_MAP_COHERENT_BIT)`
3. `glMapBufferRange(...)` → zero-copy CPU pointer into GPU PBO memory
4. Per frame: `glGetTexImage` → PBO (async DMA), then fence sync to read

### Results (1080p)

| Method | Mean | Min |
|---|---|---|
| Baseline `texture.read()` float32 | 53.7 ms | 47.5 ms |
| Persistent PBO synchronous (initiate+wait) | 94.5 ms | 84.9 ms |
| Persistent PBO async double-buffer | 83.1 ms | 80.0 ms |

**Persistent PBO is 1.5–1.8× SLOWER than baseline.**

### Root Cause Analysis
The ~50ms latency is not PCIe bandwidth (that would be ~2ms for 24 MB over PCIe 3.0). It is the **GPU pipeline drain stall**: `glGetTexImage` and `glReadPixels` both force the GPU to flush and complete all pending work before reading pixels back. This stall is ~50ms regardless of how the data is transported afterward.

Persistent PBOs cannot eliminate this synchronization barrier. They only help if:
- The GPU completes the readback within one frame interval (33ms at 30fps)
- The CPU can do other work while the GPU drains

On this driver, the drain takes ~50ms > 33ms frame interval, so the double-buffer strategy always blocks: frame N+1 always arrives before frame N's transfer completes.

Additionally, `glReadPixels` returns zeros on this driver (Bug 2). The `glGetTexImage` path does not have that bug, but the PBO mapped data showed large pixel diffs (max=255), suggesting the PBO data path also has AMD driver issues.

### Conclusion
GPU readback latency on this AMD driver is **irrecoverably ~50ms** for any pixel readback method. The correct solution is to **avoid readback entirely** — keep compositing on the CPU.

---

## Tested: Intermediate u1 Blit Pass (Strategy 1)

**Test:** `tests/gpu/test_amd_readback_opt.py`  
**Result: fbo.read() still returns zeros even for u1 FBOs. ❌**

The suggestion was: render float32 → u1 FBO via blit shader, then `fbo.read()` on a u1 source. Result: `fbo.read()` returns all-zeros regardless of FBO format. This confirms Bug 2 is in `glReadPixels` itself (called internally by `fbo.read()`), not in the float→u8 conversion step.

---

## Untested Alternative: Integer Textures (`GL_RGBA8UI`)

**Suggested by external tool — NOT yet tested on this hardware.**

### Idea
Use unsigned integer textures (`GL_RGBA8UI`) with `usampler2D` in shaders instead of float32 textures. Integer textures bypass the driver's broken normalization path (Bug 1) without the 4× memory overhead of float32.

```python
# ModernGL: dtype='u1' maps to GL_RGBA8 (normalized).
# GL_RGBA8UI requires raw GL or a different ModernGL path.
texture = ctx.texture((w, h), 4, dtype='u1')
# Shader must use usampler2D + texelFetch() — not texture()
```

```glsl
// All shaders would change from:
uniform sampler2D inputTexture;
vec4 src = texture(inputTexture, v_uv);
// to:
uniform usampler2D inputTexture;
ivec2 coord = ivec2(v_uv * vec2(textureSize(inputTexture, 0)));
uvec4 src_u = texelFetch(inputTexture, coord, 0);
vec4 src = vec4(src_u) / 255.0;  // manual normalization
```

### Why not implemented yet

| Issue | Detail |
|---|---|
| `glBlendFunc` broken with integer FBOs | Standard OpenGL blend equations don't apply to integer framebuffer attachments — all blending must be done manually in the shader |
| Bug 2 unknown for integer FBOs | `fbo.read()` returning zeros was found on float32 FBOs; integer FBOs may have the same or different bugs — untested |
| Bug 3 unaffected | `texture.read()` latency (~43 ms) is a readback/PCIe bandwidth issue, not a texture format issue. Integer textures do not help this |
| All shaders must change | Every shader needs `usampler2D` + `texelFetch` + manual `/255.0` — significant rewrite for marginal benefit |
| ModernGL API unclear | `dtype='u1'` may or may not produce `GL_RGBA8UI` vs `GL_RGBA8`; needs verification with `glGetInternalformativ` |

### Verdict
The float32 path already works correctly and is tested. VRAM overhead (~18 MB extra per frame) is negligible at 1080p. The real bottleneck (Bug 3, 43 ms readback) is not addressed by integer textures. **Not worth the rewrite risk until Bug 3 becomes the blocking issue.**

---

## Tested: Compute Shader SSBO Readback — Bug 3 Workaround ✅

**Test:** `tests/gpu/test_amd_ssbo_vs_texture_read.py`
**Result: 5× faster than `texture.read()` at 1080p. Bug 3 is bypassed. ✅**

### Discovery
The ArtNet GPU sampler (already committed) proved that `glGetBufferSubData` on a compute-shader-written SSBO is not affected by the pipeline drain stall that hits `glGetTexImage` / `glReadPixels`. That was verified at 2 KB (512 LEDs × 4 bytes). This test extended the measurement to full-frame scale.

### Strategy
1. OGL 4.3 compute shader reads the float32 composite texture pixel-by-pixel
2. Packs each pixel to uint8 and writes into a pre-allocated SSBO
3. `ctx.finish()` waits for compute to complete
4. `glGetBufferSubData` (via `ssbo.read()`) transfers the SSBO to CPU RAM

### Results (1920×1080, AMD gfx902 iGPU)

| Method | Mean | Min | Max |
|---|---|---|---|
| `texture.read()` float32 (baseline) | 111.1 ms | 90.6 ms | 135.8 ms |
| **SSBO compute+read 1080p full** | **21.1 ms** | **11.0 ms** | **28.0 ms** |
| **SSBO compute+read 640×360 preview** | **10.0 ms** | **2.3 ms** | **21.0 ms** |
| compute dispatch+`ctx.finish()` only | 5.4 ms | 2.6 ms | 13.3 ms |
| `glGetBufferSubData` alone (7.9 MB) | 11.4 ms | 8.5 ms | 14.9 ms |

**SSBO path is 5× faster than `texture.read()` at 1080p.**
**Preview resolution (640×360): 10× faster, fits comfortably in a 33ms frame budget.**

Correctness check passed: max pixel diff = 0 between `texture.read()` and SSBO paths.

### Root Cause of Why This Works
The ~50ms AMD stall is specific to `glGetTexImage` and `glReadPixels` — both are pixel-pack operations that force a full GPU pipeline drain by OpenGL spec.
`glGetBufferSubData` is a buffer-object read. The OpenGL spec does NOT require a pipeline drain for buffer reads — only coherency with respect to prior compute writes is needed, which `ctx.finish()` (a `glFinish()` call) already ensures.

The AMD driver correctly implements this distinction: texture readback → 110ms stall, buffer readback → no stall.

### Expected Performance on Discrete GPU
On any discrete GPU (AMD RX series, NVIDIA GTX/RTX, Intel Arc):
- Compute dispatch: ~0.1–0.5 ms
- `glGetBufferSubData` 640×360×3 = 691 KB over PCIe 4.0: ~0.05 ms
- **Total: < 1 ms** for preview readback

### Conclusion and New Architecture
Bug 3 is bypassed entirely via the compute shader SSBO path.

**New download strategy:**
```
texture.read()      → ABANDONED for frame download (111ms AMD stall)
compute → SSBO.read() → ADOPTED as the universal frame download path
```

This is now the preferred implementation for both:
- **Preview**: compute shader downsamples 1080p → 640×360, writes SSBO, Flask reads it
- **ArtNet**: already implemented — compute shader samples N LED UV positions into SSBO
- **Full-frame download** (when needed by CPU effects): compute shader → SSBO at native resolution (21ms)

Update `Current Performance Impact` table:

| Operation | Cost | Status |
|---|---|---|
| `texture.read()` float32 full frame (1080p) | ~111 ms | **Abandoned** |
| `fbo.read(dtype='u1')` | returns zeros | Abandoned |
| `fbo.read_into(pbo)` | ~127 ms (sync stall) | Abandoned |
| `cv2.addWeighted()` CPU blend (1080p, 2 layers) | ~9 ms | Active (no GPU blend needed) |
| **Compute shader → SSBO → `glGetBufferSubData` (1080p)** | **~21 ms** | **✅ New download path** |
| **Compute shader → SSBO → `glGetBufferSubData` (640×360)** | **~10 ms** | **✅ Preview path** |
