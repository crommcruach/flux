# HAP VideoSource Reimplementation Plan

**Status:** Planned — not yet implemented  
**Goal:** Replace raw `.npy` frame storage with DXT-compressed `.hapnpy` blocks to reduce RAM usage ~6× and enable loading more clips warm simultaneously.

---

## CRITICAL: Zero-Copy Per-Frame Path

**This constraint must be maintained throughout the entire implementation.**

The whole point of HAP is that DXT blocks move from RAM → GPU without any CPU decompression or Python-level copy per frame. Violating this turns it into a slower version of the current `.npy` pipeline.

### The exact allowed data path per frame

```
buffer[idx * fbs : (idx+1) * fbs]   ← numpy slice (view, zero-copy)
        │
        ▼
memoryview(slice)                    ← zero-copy buffer protocol wrapper
        │
        ▼
wgpu write_texture(bc1-rgba-unorm)   ← single C-level memcpy into D3D12 upload heap
        │                               (unavoidable — this is how D3D12 works)
        ▼
GPU DMA: upload heap → VRAM texture  ← hardware DMA, no CPU involved
        │
        ▼
GPU samples bc1 texture              ← hardware decompresses during sampling, free
```

### What is FORBIDDEN

```python
# ❌ WRONG — bytes() always makes a full Python heap copy
return bytes(self.buffer[start:end]), duration, 'bc1'

# ❌ WRONG — .tobytes() makes a heap copy
return self.buffer[start:end].tobytes(), duration, 'bc1'

# ❌ WRONG — np.ascontiguousarray() on a slice copies if not already C-contiguous
frame = np.ascontiguousarray(self.buffer[start:end])

# ❌ WRONG — decoding DXT on CPU before upload (defeats the purpose entirely)
rgb = imagecodecs.bc1_decode(dxt_slice)
device.queue.write_texture(..., rgb.tobytes(), ...)
```

### What is CORRECT

```python
# ✅ CORRECT — memoryview of numpy slice is zero-copy
slice_ = self.buffer[start:end]          # numpy view, no copy
return memoryview(slice_), duration, 'bc1'

# ✅ CORRECT — wgpu accepts buffer protocol directly
device.queue.write_texture(
    {"texture": bc1_tex, ...},
    frame,                               # memoryview, passed directly to C layer
    {"bytes_per_row": (w // 4) * 8, "rows_per_image": h // 4},
    (w // 4, h // 4, 1)                  # size in blocks, not pixels
)
```

### The one acceptable copy: eager-load in `initialize()`

```python
# ✅ ACCEPTABLE — one-time cost at load time, not per-frame
if nbytes <= threshold:
    self.buffer = np.ascontiguousarray(mmap_flat)  # heap copy, done once
```

This is intentional: contiguous heap RAM avoids Windows page-fault stalls (~25 ms/frame) that happen when sampling OS-managed memmap pages between frames. Same rationale as in the existing `VideoSource`.

### Why `bytes_per_row` is different for BC textures

For `rgba8unorm` (current): `bytes_per_row = width * 4`  
For `bc1-rgba-unorm` (HAP): `bytes_per_row = (width // 4) * 8`  — bytes per row of 4×4 blocks  
For `bc3-rgba-unorm` (HAP Alpha): `bytes_per_row = (width // 4) * 16`

**Getting this wrong causes a silent corrupt upload** — wgpu will accept it but the texture will be garbage. Always compute from block dimensions, never from pixel dimensions.

### Validation test to add (`tests/test_hap_zero_copy.py`)

Use `tracemalloc` to assert that `get_next_frame()` allocates **zero** Python heap bytes on the hot path:

```python
import tracemalloc
src.initialize()
tracemalloc.start()
frame, dur, fmt = src.get_next_frame()
snapshot = tracemalloc.take_snapshot()
stats = snapshot.statistics('lineno')
allocated = sum(s.size for s in stats)
assert allocated < 1024, f"get_next_frame() allocated {allocated} bytes — should be 0"
```

---

## Motivation

Current `.npy` pipeline RAM cost:

| Format | 1080p/25fps/60s | 10 clips |
|---|---|---|
| Raw `.npy` (RGB uint8) | ~9.3 GB | ~93 GB |
| BC1 `.hapnpy` (DXT1) | ~1.5 GB | ~15 GB |
| BC3 `.hapnpy` (DXT5) | ~3.0 GB | ~30 GB |

With 32 GB RAM: 3 raw clips warm → ~20 BC1 clips warm.  
GPU decompresses DXT blocks during texture sampling — effectively zero CPU/GPU overhead vs raw.

---

## Architecture Overview

```
Current:  .npy (RAM) → frames[idx] numpy RGB → write_texture(rgba8unorm) → GPU compositor
New:      .hapnpy (RAM) → frames[idx] DXT bytes → write_texture(bc1-rgba-unorm) → GPU compositor
                                                                    ↑ GPU decompresses here, free
```

Both pipelines coexist. `VideoSource._find_best_resolution()` prefers `.hapnpy` over `.npy` automatically — old clips keep working without migration.

---

## Phase 1 — New Storage Format: `.hapnpy`

### File layout

```
clips/my_clip/
  original.mov          ← preserved as-is
  1080p.hapnpy          ← new binary: flat concatenated DXT frames (fixed-size per frame)
  1080p.json            ← extended: adds "format", "dxt_variant", "frame_bytes"
  720p.hapnpy
  720p.json
  1080p.npy             ← old file stays until verified; VideoSource ignores it if .hapnpy exists
```

### Frame size formula (fixed, no offset table needed)

```python
# BC1 (DXT1): 8 bytes per 4×4 block, RGB no alpha
frame_bytes_bc1 = (width // 4) * (height // 4) * 8
# BC3 (DXT5): 16 bytes per 4×4 block, RGBA with alpha
frame_bytes_bc3 = (width // 4) * (height // 4) * 16

# Frame N starts at:  N * frame_bytes
```

Dimensions must be multiples of 4. All existing presets (720p, 1080p, etc.) already are.

### Extended `.json` sidecar

```json
{
  "fps": 25.0,
  "frame_count": 1500,
  "width": 1920,
  "height": 1080,
  "format": "hapnpy",
  "dxt_variant": "bc1",
  "frame_bytes": 1048576
}
```

---

## Phase 2 — Converter Changes

**File:** `src/modules/content/converter.py`

### New enum value

```python
class OutputFormat(Enum):
    HAP_NPY = "hap_npy"   # DXT-compressed .hapnpy (new internal format)
    # ... existing values stay
```

### New method `_hap_convert_preset()`

Add alongside existing `_npy_convert_preset()`:

```python
def _hap_convert_preset(self, input_path, clip_folder, preset, dxt_variant='bc1'):
    """Decode all frames, DXT-compress each, write flat .hapnpy binary."""
    import imagecodecs  # pip install imagecodecs
    
    target_w, target_h = RESOLUTION_PRESETS[preset]
    output_hap = os.path.join(clip_folder, f"{preset}.hapnpy")
    output_meta = os.path.join(clip_folder, f"{preset}.json")
    
    cap = cv2.VideoCapture(input_path, cv2.CAP_FFMPEG)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    
    encode_fn = imagecodecs.bc1_encode if dxt_variant == 'bc1' else imagecodecs.bc3_encode
    frame_bytes = (target_w // 4) * (target_h // 4) * (8 if dxt_variant == 'bc1' else 16)
    
    with open(output_hap, 'wb') as f:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = _scale_frame_fit(frame, target_w, target_h)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            dxt = encode_fn(rgb)   # returns bytes of length frame_bytes
            f.write(dxt)
            frame_count += 1
    
    meta = {
        'fps': fps, 'frame_count': frame_count,
        'width': target_w, 'height': target_h,
        'format': 'hapnpy', 'dxt_variant': dxt_variant,
        'frame_bytes': frame_bytes
    }
    with open(output_meta, 'w') as f:
        json.dump(meta, f)
```

### Hook into `convert_multi_resolution()`

When `output_format == OutputFormat.HAP_NPY`, call `_hap_convert_preset()` instead of `_npy_convert_preset()`.

---

## Phase 3 — New HapVideoSource

**New file:** `src/modules/player/sources/hap_video.py`

```python
class HapVideoSource(FrameSource):
    """Video source backed by DXT-compressed .hapnpy flat binary.
    
    get_next_frame() returns (dxt_bytes: bytes, frame_duration: float, dxt_variant: str)
    instead of the usual (numpy_array, frame_duration).
    The compositor source_upload stage detects bytes and uses a bc1/bc3 texture format.
    """

    def __init__(self, hapnpy_path, canvas_width, canvas_height, config=None, ...):
        # Same signature as VideoSource
        ...

    def initialize(self):
        # Read sidecar JSON → fps, frame_count, width, height, dxt_variant, frame_bytes
        # np.memmap(hapnpy_path, dtype=np.uint8, mode='r') → flat buffer
        # Eager-copy if buffer.nbytes <= threshold (same logic as VideoSource)
        ...

    def get_next_frame(self):
        start = self.current_frame * self.frame_bytes
        dxt = self.buffer[start:start + self.frame_bytes]
        # Returns bytes (or memoryview), not numpy array
        return bytes(dxt), 1.0 / self.fps, self.dxt_variant

    def retrim(self, in_point, out_point):
        # Same logic as VideoSource.retrim() but operates on flat byte offsets
        # self.buffer = full_mmap[in_point*frame_bytes : (out_point+1)*frame_bytes]
        ...

    def reset(self):
        self.current_frame = self._trim_start

    def cleanup(self):
        self.buffer = None
        self._mmap_ref = None
```

**Export:** Add to `src/modules/player/sources/__init__.py`:
```python
from .hap_video import HapVideoSource
```

---

## Phase 4 — VideoSource Smart Dispatch

**File:** `src/modules/player/sources/video.py`

In `_find_best_resolution()`, add `.hapnpy` check **before** `.npy`:

```python
for preset in ordered:
    # Prefer DXT-compressed if available
    candidate = os.path.join(path, f"{preset}.hapnpy")
    if os.path.exists(candidate):
        logger.debug(f"[HapSource] {os.path.basename(path)} -> {preset}.hapnpy")
        self._is_hap = True
        return candidate
    # Fall back to raw npy
    candidate = os.path.join(path, f"{preset}.npy")
    if os.path.exists(candidate):
        logger.debug(f"[NpySource] {os.path.basename(path)} -> {preset}.npy")
        return candidate
```

Then in `initialize()`:
```python
if self.video_path.endswith('.hapnpy'):
    from .hap_video import HapVideoSource
    self._delegate = HapVideoSource(self.video_path, ...)
    return self._delegate.initialize()
```

All other methods (`get_next_frame`, `retrim`, `reset`, `cleanup`) delegate to `self._delegate` when set.

---

## Phase 5 — Compositor: Compressed Texture Upload

**File:** `src/modules/gpu/` — wherever `source_upload` / `write_texture` is called.

Current:
```python
device.queue.write_texture(
    {"texture": tex, ...},
    frame.tobytes(),          # numpy RGB array
    {"bytes_per_row": w * 3, ...},
    (w, h, 1)
)
# tex created with format=wgpu.TextureFormat.rgba8unorm
```

New path when `get_next_frame()` returns bytes (HAP):
```python
if isinstance(frame, (bytes, memoryview)):
    # Use pre-allocated bc1/bc3 texture from pool (different format key)
    tex = pool.acquire(w, h, format='bc1')   # or 'bc3'
    device.queue.write_texture(
        {"texture": tex, ...},
        frame,                # raw DXT bytes, no conversion
        {"bytes_per_row": (w // 4) * 8, ...},   # bc1: 8 bytes per 4×4 block per row of blocks
        (w, h, 1)
    )
else:
    # existing numpy path unchanged
    ...
```

### Texture pool changes (`src/modules/gpu/texture_pool.py`)

Pool key changes from `(w, h)` to `(w, h, format)`.  
New format strings: `'rgba8unorm'` (existing), `'bc1-rgba-unorm'`, `'bc3-rgba-unorm'`.

wgpu texture format constants:
```python
wgpu.TextureFormat.bc1_rgba_unorm      # DXT1 / HAP
wgpu.TextureFormat.bc3_rgba_unorm      # DXT5 / HAP Alpha
```

Both are natively supported on D3D12 and Vulkan. No shader changes needed — sampler reads them identically to `rgba8unorm`.

---

## Phase 6 — Conversion Tool

**New file:** `tools/convert_to_hap.py`

```
python tools/convert_to_hap.py --input videos/ --preset 1080p --variant bc1 [--delete-npy]
```

- Iterates all clip folders under `videos/`
- Skips folders that already have `{preset}.hapnpy`  
- Calls `VideoConverter._hap_convert_preset()`
- `--delete-npy` flag removes old `.npy` after successful conversion
- Progress bar via `tqdm`

---

## Dependencies

Add to `requirements.txt`:
```
imagecodecs>=2023.1.23   # DXT1/BC1 and DXT5/BC3 encode/decode
```

Install: `pip install imagecodecs`

`imagecodecs` uses a fast C backend (libsquish/libdxt). BC1 encode at 1080p takes ~2–5 ms/frame on a modern CPU — conversion of a 60s clip takes ~3 minutes.

---

## Migration Strategy

1. Install `imagecodecs`
2. Run `tools/convert_to_hap.py` on your clip library for `1080p` preset first
3. Restart Flux — it automatically uses `.hapnpy` where available, `.npy` as fallback
4. Verify visual quality (BC1 is lossy — check for banding on subtle gradients)
5. Convert remaining presets (`720p`, `1440p`)
6. Once satisfied: `--delete-npy` to reclaim disk space

**No code changes needed in `core.py`, `PlaylistManager`, effects pipeline, or API layer.**  
The `VideoSource` public interface (`initialize()`, `get_next_frame()`, `retrim()`, `reset()`) stays identical from the caller's perspective.

---

## Risk / Notes

- **BC1 is lossy** — 6:1 compression. Suitable for VJ content (gradients, motion). Noticeable on sharp text, fine diagonal lines. Use BC3 for alpha/transparency clips.
- **wgpu BC texture support** — Requires `wgpu >= 0.15`. Feature `TextureFeatures.TEXTURE_COMPRESSION_BC` must be available. On D3D12/Metal/Vulkan this is guaranteed. Check: `device.features` at startup.
- **VRAM** — BC textures decompress to full size in VRAM during sampling. VRAM cost is same as uncompressed. Only system RAM cost decreases.
- **Effects pipeline** — Effects operate on decompressed textures (GPU side). No changes needed to any effect shader.
- **Retrim with HAP** — Works the same way: `_mmap_ref` keeps the full flat binary, `buffer` is a narrowed slice. Byte offsets: `in_point * frame_bytes` to `(out_point + 1) * frame_bytes`.
