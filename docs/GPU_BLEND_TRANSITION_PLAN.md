# GPU Blend & Transition Migration Plan

## Status: PLANNING

**Goal**: Eliminate all software-rendering (CPU numpy / cv2) in blend effects and transition
plugins, replace with GLSL fragment shaders running through the existing ModernGL pipeline.
Remove legacy CPU code in the same sweep as GPU code is added.

---

## Key Findings (Pre-Work Audit)

### Layer-to-layer blending — ALREADY GPU ✅
`composite_layers()` in `manager.py` already uses `blend.frag` (7 modes: normal, add, subtract,
multiply, screen, overlay, mask) with a single gated `composite.download()`. No change needed here.

### `BlendEffect` plugin (`plugins/effects/blend.py`) — DEAD PATH
`apply_layer_effects()` never passes an `overlay` argument, so `BlendEffect` in a layer effect
chain only calls `_apply_opacity()` (a CPU float multiply). The actual layer-to-layer blending
is handled entirely by the GPU compositor. This plugin should be **archived/deactivated**, not
ported to GPU — it has no meaningful function in the current architecture.

### `BlendModeEffect` plugin (`plugins/effects/blend_mode.py`) — GPU TARGET
Blends the current frame against a solid RGB color using a blend mode. Legitimate single-texture
effect. Currently allocates ~3× full float32 frames per call (~25 MB at 1080p). **Top priority
for GPU port.**

### Transition plugins — all CPU
`TransitionManager.apply()` is called after `composite_layers()` on two CPU frames. All 6
plugins (`fade`, `slide_wipe`, `wipes`, `lens_blur`, `rgb_split`, `zoom`) are pure numpy/cv2.
The architecture must be extended to support GPU transitions.

### `store_frame()` wasteful copy — QUICK WIN
`buffer = frame.copy()` runs every frame whenever transitions are enabled in config — even
during normal playback with no active transition. Fix independently of GPU work.

---

## Architecture for GPU Transitions

Current flow:
```
composite_layers() → CPU frame
  → TransitionManager.store_frame(frame)   # saves copy every frame
  → TransitionManager.apply(frame)          # CPU blend two frames
  → VirtualOutput / preview
```

Target flow:
```
composite_layers() → CPU frame (or skipped if no CPU consumer)
  → GPU TransitionManager path:
       upload(frame_a) → GPU tex A   (previous, kept alive)
       upload(frame_b) → GPU tex B   (current)
       render(transition.frag, A, B, progress) → GPU tex C
       download(C) → CPU frame       (single download, result only)
  → VirtualOutput / preview
```

Implementation strategy:
- `TransitionManager` gets a GPU-capable backend (`GPUTransitionRenderer`)
- `GPUTransitionRenderer` holds two `GPUFrame` textures: `_buf_a` and `_buf_b`
- Each transition type gets its own `.frag` shader (with a `sampler2D tex_a` and `sampler2D tex_b`)
- `progress` and other params passed as uniforms
- Falls back to CPU path if GPU context unavailable

---

## Phase 1 — PoC (Two effects, one transition)

### PoC-1: `BlendModeEffect` → GPU (`blend_mode.frag`)

**Replaces**: `plugins/effects/blend_mode.py` CPU float32 pipeline

**New shader**: `src/modules/gpu/shaders/blend_mode.frag`
- Input: `sampler2D inputTexture` (existing convention), uniforms `vec3 color`, `float opacity`,
  `float mix_amount`, `int mode`
- Modes (int 0–13): normal, multiply, screen, overlay, add, subtract, darken, lighten,
  color_dodge, color_burn, hard_light, soft_light, difference, exclusion
- Output: RGB blend of frame + solid color layer

**Plugin changes** (`blend_mode.py`):
```python
def get_shader(self):
    return _read_shader('blend_mode.frag')  # same pattern as brightness_contrast.py

def get_uniforms(self, **kwargs):
    return {
        'color': [self.color_r / 255.0, self.color_g / 255.0, self.color_b / 255.0],
        'opacity': float(self.opacity) / 100.0,
        'mix_amount': float(self.mix),
        'mode': BLEND_MODE_IDS[self.mode],
    }

def process_frame(self, frame, **kwargs):
    return frame  # stub — GPU path handles real processing
```

**Archive**: move old CPU `process_frame()` body to `archive/effects/blend_mode_cpu.py`

---

### PoC-2: `FadeTransition` → GPU (`fade_transition.frag`)

**Replaces**: `plugins/transitions/fade.py` → `cv2.addWeighted`

**New shader**: `src/modules/gpu/shaders/fade_transition.frag`
```glsl
#version 330
uniform sampler2D tex_a;
uniform sampler2D tex_b;
uniform float progress;   // 0.0 = all A, 1.0 = all B
in vec2 uv;
out vec4 fragColor;
void main() {
    vec4 ca = texture(tex_a, uv);
    vec4 cb = texture(tex_b, uv);
    fragColor = mix(ca, cb, progress);
}
```

**`GPUTransitionRenderer`** (`src/modules/gpu/transition_renderer.py`):
- `render(frag_src, tex_a, tex_b, uniforms) → GPUFrame` — ping-pong two textures
- Used by `TransitionManager` when GPU context is available
- `TransitionManager.apply()` checks if `_gpu_renderer` exists and transitions are GPU-capable

**Archive**: move `fade.py` → `archive/transitions/fade_cpu.py.bak` (`.bak` suffix prevents import)

---

## Phase 2 — Remaining blend modes

After PoC validated, port `blend_mode.frag` extended with remaining modes. Port the rest of the
transition plugins as separate `.frag` shaders under `src/modules/gpu/shaders/`:

| Transition | Shader | Complexity |
|---|---|---|
| slide_wipe | `slide_wipe_transition.frag` | Low — UV offset |
| linear_wipe | `wipe_transition.frag` | Low — coordinate projection |
| radial_wipe | `wipe_transition.frag` (mode uniform) | Medium — atan2 |
| round_wipe | `wipe_transition.frag` (mode uniform) | Medium — circle distance |
| zoom | `zoom_transition.frag` | Medium — cv2.resize → GPU zoom |
| lens_blur | `lens_blur_transition.frag` | High — Gaussian blur pass |

Lens blur transition may need a two-pass render (blur then blend) — do last.

---

## Phase 3 — Dead code removal

Once all effects/transitions are ported and PoC validated across the test suite:

1. Delete `plugins/effects/blend.py` (dead path, never used meaningfully post-GPU compositor)
2. Delete CPU `process_frame()` bodies from all ported blend/transition plugins
3. Remove `get_blend_plugin()` method + `_blend_cache` from `manager.py` (confirmed dead code)
4. Fix `store_frame()` to only copy when transition is starting/active (separate quick fix)

---

## Plugin Archiving Strategy

**Rule**: A plugin that is CPU-only AND has been replaced by a GPU equivalent must NOT be
auto-discoverable by the plugin loader.

**Convention**: Rename to `<name>.py.bak` — Python cannot import `.py.bak` files.

```
archive/
  effects/
    blend.py.bak           # BlendEffect — dead path, compositor handles blending
    blend_mode_cpu.py.bak  # CPU blend_mode before GPU port
  transitions/
    fade_cpu.py.bak        # CPU fade before GPU port
    slide_wipe_cpu.py.bak
    wipes_cpu.py.bak
    lens_blur_cpu.py.bak
    rgb_split_cpu.py.bak
    zoom_cpu.py.bak
```

Keep originals in `archive/` so they can be reviewed but cannot be accidentally registered by
the plugin loader.

**Alternative for plugins still in plugins/ dir during transition**: Add class attribute
`DISABLED = True`. Plugin loader must be updated to skip classes where `DISABLED is True`.
This allows a safe two-step: disable first, delete after validation.

---

## Implementation Checklist

### Quick win (independent, do first)
- [ ] Fix `store_frame()` in `transitions/manager.py` — add `if self.active` guard

### PoC-1: BlendModeEffect GPU
- [ ] Write `src/modules/gpu/shaders/blend_mode.frag` (14 modes + uniform `int mode`)
- [ ] Update `plugins/effects/blend_mode.py`: add `get_shader()`, `get_uniforms()`, stub `process_frame()`
- [ ] Move old CPU body to `archive/effects/blend_mode_cpu.py.bak`
- [ ] Validate with test: GPU path runs, output matches CPU reference

### PoC-2: Fade Transition GPU  
- [ ] Write `src/modules/gpu/shaders/fade_transition.frag`
- [ ] Create `src/modules/gpu/transition_renderer.py` (`GPUTransitionRenderer`)
- [ ] Update `TransitionManager` to use GPU renderer when context available
- [ ] Move `plugins/transitions/fade.py` → `archive/transitions/fade_cpu.py.bak`
- [ ] Update `TransitionManager` to not load `fade` from plugins/ (use shader directly)
- [ ] Validate crossfade works at 30fps, matches CPU reference

### Dead code (after PoC)
- [ ] Archive `plugins/effects/blend.py` → `archive/effects/blend_cpu.py.bak`
- [ ] Remove `get_blend_plugin()` + `_blend_cache` from `manager.py`
- [ ] Update plugin loader to support `DISABLED = True` attribute

### Phase 2 (after PoC sign-off)
- [ ] Port `slide_wipe` → GPU
- [ ] Port `wipes` (linear + radial + round, single shader with mode uniform) → GPU
- [ ] Port `zoom` → GPU
- [ ] Port `lens_blur` → GPU (two-pass)
- [ ] Port `rgb_split` → GPU

---

## Key Files

| File | Role |
|---|---|
| `src/modules/gpu/shaders/blend_mode.frag` | NEW — solid color blend modes |
| `src/modules/gpu/shaders/fade_transition.frag` | NEW — crossfade transition |
| `src/modules/gpu/transition_renderer.py` | NEW — GPU render for transitions |
| `src/modules/player/transitions/manager.py` | MODIFY — GPU path in apply() |
| `plugins/effects/blend_mode.py` | MODIFY — add get_shader() |
| `plugins/effects/blend.py` | ARCHIVE — dead path |
| `plugins/transitions/fade.py` | ARCHIVE — replaced by GPU |
| `src/modules/player/layers/manager.py` | MINOR — remove get_blend_plugin() |
| `archive/` | DESTINATION — disabled legacy plugins |

---

## Notes for Implementer

- GPU context is available in `TransitionManager` through `player._gpu_context` (or pass it in
  during `configure()`). Check how `ArtNetGPUSampler` receives its context reference.
- The existing `renderer.render()` in `manager.py` is the right primitive to reuse in
  `GPUTransitionRenderer` — it handles `passthrough.vert`, FBO setup, and uniform injection.
- `GPUFrame.pool.acquire()` / `pool.release()` handles texture allocation — use it in
  `GPUTransitionRenderer` to avoid creating permanent textures unless the resolution can vary.
- Easing functions (linear, ease_in, ease_out, ease_in_out) remain in Python — they just
  compute the `progress` float that is passed as a uniform. No shader change needed for easing.
- The `DISABLED = True` plugin gate requires one line in the plugin loader
  (`if getattr(cls, 'DISABLED', False): continue`). Add this before starting Phase 1.
