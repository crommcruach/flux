# Layer → Slice Routing — N Layers to N Slices

> Per-layer sub-compositor: any combination of layers can be routed to any
> combination of named output slices, fully on GPU, inside a single wgpu
> command encoder submission.

---

## 1. Concept

```
Layer stack (top = rendered last)
───────────────────────────────────────────────────────────
  Layer 0   [Background video]          ──► main composite
  Layer 1   [DJ booth overlay]  Slice1  ──► main + Slice1 sub-compositor
  Layer 2   [DJ booth logo]     Slice1  ──► main + Slice1 sub-compositor
  Layer 3   [StageLeft BG]      Stage   ──► Stage sub-compositor only (bypass)
  Layer 4   [StageLeft fx]      Stage   ──► Stage sub-compositor only (bypass)
  Layer 5   [Global overlay]           ──► main composite
                                              │
                                        ┌─────┴──────────────────────────────┐
                                        ▼                                    ▼
                                   main output                          per-slice outputs
                               (full composite)                    Slice1 output ─► DjBooth display
                                                                   Stage output  ─► StageLeft display
```

Each `output_slices` entry on a layer is **additive**: one layer can feed the
main composite AND multiple slice sub-compositors simultaneously, at VRAM-only
cost (one extra passthrough blend per destination per frame).

`bypass_main = true` removes the layer from the main composite entirely — it
lives exclusively in its assigned slices.

---

## 2. Data Model

### 2a. Layer fields (new)

**File:** `src/modules/player/layers/layer.py`

```python
# NEW fields appended to Layer.__init__ after self.enabled:
self.output_slices: list[str] = []   # slice IDs this layer feeds into
self.bypass_main: bool = False        # True = skip blending into main composite
```

`to_dict()` addition:
```python
'output_slices': self.output_slices,
'bypass_main':   self.bypass_main,
```

`from_dict()` / clip registry deserialization must round-trip these fields.

### 2b. ClipRegistry / clip layer persistence

**File:** `src/modules/data/clips.py` (wherever `update_clip_layer` applies
partial dicts to layer records)

The PATCH endpoint at `PATCH /api/clips/<clip_id>/layers/<layer_id>` already
accepts arbitrary fields — no endpoint change needed. Adding `output_slices`
and `bypass_main` to the body is sufficient.

### 2c. session_state.json shape (no change needed)

Layer config is already stored verbatim inside each clip's `layers` array.
The new fields serialize transparently.

---

## 3. GPU Implementation

### 3a. Compositor changes

**File:** `src/modules/player/layers/compositor.py`

The blend loop already has a `layer_tex` variable (canvas-sized, pool-owned
GPUFrame) ready before the main blend pass.  The sub-compositor runs
**additional blend passes into per-slice ping-pong pairs** using the same
`blend_enc` — no new encoder, no extra submit.

#### 3a-i. Per-slice ping-pong allocation (before blend loop)

```python
# Build per-slice ping-pong pairs for every slice that appears in this frame.
# Keys = slice_id.  Values = (cur_tex, alt_tex | None).
slice_ping: dict[str, GPUFrame] = {}
slice_alt:  dict[str, GPUFrame | None] = {}

for layer in layers_snap:
    for sid in getattr(layer, 'output_slices', []):
        if sid not in slice_ping:
            slice_ping[sid] = pool.acquire(canvas_w, canvas_h)
            slice_alt[sid]  = None
            # Clear slice cur to transparent black so first blend is correct.
            # Cheapest: render a zero-output passthrough with no source texture,
            # OR initialize with a black 1×1 texture.  Use a dedicated clear
            # pass via the passthrough shader with alpha=0 uniform if available,
            # otherwise use pool.acquire() (pool textures are zero-initialized
            # on first allocation).  Pool reuse may have stale data — add a
            # clear_enc pass or use a dedicated "clear" pipeline.
            # IMPLEMENTATION NOTE: simplest safe option is a passthrough render
            # from a 1×1 black texture into slice_ping[sid] via blend_enc.
```

#### 3a-ii. Inside the blend loop, after `layer_tex` is ready

Insert immediately before the existing `_fire_layer_processed_tap` call:

```python
# ── Sub-compositor: route layer_tex to assigned slices ────────────────
for sid in getattr(layer, 'output_slices', []):
    if sid not in slice_ping:
        continue  # race: slice appeared after allocation scan
    s_cur = slice_ping[sid]
    s_alt = slice_alt[sid]
    blend_mode_val = BLEND_MODES.get(getattr(layer, 'blend_mode', 'normal'), 0)
    if s_alt is None:
        s_alt = pool.acquire(canvas_w, canvas_h)
    renderer.render(
        wgsl_source=blend_src,
        target=s_alt,
        uniforms={'opacity': layer.opacity / 100.0, 'mode': blend_mode_val},
        textures={'base': (0, s_cur), 'overlay': (1, layer_tex)},
        encoder=blend_enc,
    )
    slice_ping[sid], slice_alt[sid] = s_alt, s_cur  # ping-pong

# ── Skip main composite if layer is bypass-only ───────────────────────
if getattr(layer, 'bypass_main', False) and getattr(layer, 'output_slices', []):
    _deferred_releases.append(layer_tex)
    continue  # skip the existing main blend pass below
```

#### 3a-iii. After `blend_enc.finish()` — fire slice output hook

Replace the current single `get_device().queue.submit(...)` block with:

```python
get_device().queue.submit([blend_enc.finish()])
for _t in _deferred_releases:
    pool.release(_t)
_deferred_releases.clear()

# Fire slice sub-composites to OutputManager
if slice_ping and mgr._output_layer_slice_hook is not None:
    try:
        mgr._output_layer_slice_hook(slice_ping)
    except Exception as e:
        logger.error(f"Layer-slice hook error: {e}")

# Release slice ping-pong pairs
for sid, tex in slice_ping.items():
    pool.release(tex)
for sid, tex in slice_alt.items():
    if tex is not None:
        pool.release(tex)
slice_ping.clear()
slice_alt.clear()
```

### 3b. LayerManager hook

**File:** `src/modules/player/layers/manager.py`

Add alongside the existing `_output_gpu_hook`:

```python
# ─── Layer-slice sub-compositor hook ────────────────────────────────────────
# Fired after blend_enc.finish() with a dict {slice_id: GPUFrame} containing
# the fully-composited sub-frames for each slice group.  GPUFrames are live
# in VRAM; caller must NOT release them (compositor does that after the call).
# Set via set_output_layer_slice_hook().
self._output_layer_slice_hook = None
```

```python
def set_output_layer_slice_hook(self, callback) -> None:
    """Register callback fired with {slice_id: GPUFrame} sub-compositor results."""
    self._output_layer_slice_hook = callback
```

### 3c. OutputManager — receive slice sub-composites

**File:** `src/modules/player/outputs/manager.py`

Add a new method alongside `update_gpu_frame`:

```python
def update_gpu_layer_slices(self, slice_frames: dict) -> None:
    """Route per-slice sub-compositor GPUFrames to matching outputs.

    slice_frames: {slice_id: GPUFrame}  — compositor owns these, do NOT release.

    For each output whose config['slice'] matches a key in slice_frames, apply
    GPUSliceRenderer (crop/rotate/soft-edge/colour) and queue the result.
    This runs BEFORE update_gpu_frame() (which handles the main composite).
    """
    for output_id, output in list(self.outputs.items()):
        if not output.enabled:
            continue
        if not hasattr(output, 'queue_gpu_frame'):
            continue
        slice_cfg = output.config.get('slice', 'full')
        if not isinstance(slice_cfg, str) or slice_cfg not in slice_frames:
            continue
        try:
            sub_frame = slice_frames[slice_cfg]
            # Apply slice transforms (crop to slice rect, rotation, soft-edge, colour).
            processed = self.slice_manager.get_slice_gpu(
                slice_cfg, sub_frame, self.canvas_width, self.canvas_height
            )
            output.needs_cpu_frame = False
            output.queue_gpu_frame(processed if processed is not None else sub_frame)
        except Exception as exc:
            logger.error(
                '[%s] Layer-slice routing error for output \'%s\': %s',
                self.player_name, output_id, exc, exc_info=True,
            )
```

### 3d. Player — register the new hook

**File:** `src/modules/player/core.py`

In `_init_output_manager()`, after the existing `set_output_gpu_hook` call:

```python
def _layer_slice_hook_fn(slice_frames, _om=self.output_manager):
    _om.update_gpu_layer_slices(slice_frames)
self.layer_manager.set_output_layer_slice_hook(_layer_slice_hook_fn)
```

---

## 4. API Endpoint

**File:** `src/modules/api/player/clips.py`

No new endpoint needed. The existing `PATCH /api/clips/<clip_id>/layers/<layer_id>`
already accepts arbitrary layer fields.  The frontend sends:

```json
PATCH /api/clips/{clip_id}/layers/{layer_id}
{
  "output_slices": ["Slice1", "DjBooth"],
  "bypass_main": false
}
```

For clearing:
```json
{ "output_slices": [], "bypass_main": false }
```

The existing `update_clip_layer` → `clip_registry.update_clip_layer()` →
`reload_player_layers_if_active()` chain already handles live reload.

---

## 5. Frontend

**File:** `frontend/js/player.js`

### 5a. Layer card — route badge

In `buildLayerPanel()`, inside the non-empty card template, after the
`layer-source` div:

```js
// After source name div:
const routeBadges = (layer.output_slices || []).map(sid => {
    const color = window.sliceColorMap?.[sid] || '#e67e22';
    return `<span class="layer-route-badge" style="background:${color}" 
                  title="Routed to: ${sid}">${sid}</span>`;
}).join('');

// Add to card HTML:
${routeBadges ? `<div class="layer-route-badges">${routeBadges}</div>` : ''}
```

Layer card left border color when routed:
```js
// In the outer div class string:
${(layer.output_slices?.length) ? 'layer-routed' : ''}
```

CSS (add to `frontend/css/player.css` or existing style block):
```css
.layer-card.layer-routed { border-left: 3px solid #e67e22; }
.layer-route-badge {
    display: inline-block;
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 3px;
    color: #fff;
    margin-right: 3px;
    opacity: 0.9;
}
.layer-route-badges { margin-top: 2px; }
```

### 5b. Right-click context menu on layer card

In `buildLayerPanel()`, add `oncontextmenu` to the card `div`:

```js
oncontextmenu="showLayerContextMenu(event, '${selectedClipId}', ${layer.layer_id})"
```

New function (modeled on `showPlaylistContextMenu`):

```js
window.showLayerContextMenu = async function(e, clipId, layerId) {
    e.preventDefault();
    e.stopPropagation();

    const existing = document.getElementById('layerContextMenu');
    if (existing) existing.remove();

    // Fetch available slices
    let slices = [];
    try {
        const r = await fetch(`${API_BASE}/api/player/video/outputs/slices`);
        const d = await r.json();
        slices = d.slices || [];
    } catch(_) {}

    const layer = (clipLayers[clipId] || []).find(l => l.layer_id === layerId);
    const currentSlices = layer?.output_slices || [];
    const bypassMain   = layer?.bypass_main || false;

    const sliceItems = slices
        .filter(s => s.slice_id !== 'full')
        .map(s => {
            const active = currentSlices.includes(s.slice_id);
            return `<div class="context-menu-item ${active ? 'active' : ''}"
                         data-action="toggle-slice" data-slice="${s.slice_id}">
                <span>${active ? '✓' : '◻'} ${s.slice_id}</span>
                <small>${s.description || ''}</small>
            </div>`;
        }).join('');

    const menu = document.createElement('div');
    menu.id = 'layerContextMenu';
    menu.className = 'context-menu';
    menu.style.position = 'fixed';
    menu.innerHTML = `
        <div class="context-menu-header">Route Layer ${layerId} to:</div>
        ${sliceItems || '<div class="context-menu-item disabled"><span>No slices defined</span></div>'}
        <div class="context-menu-separator"></div>
        <div class="context-menu-item ${bypassMain ? 'active' : ''}" data-action="toggle-bypass">
            <span>${bypassMain ? '✓' : '◻'} Bypass main composite</span>
            <small>Exclude from main LED wall output</small>
        </div>
        <div class="context-menu-separator"></div>
        <div class="context-menu-item" data-action="clear-routing">
            <span>✖ Clear all routing</span>
        </div>
    `;
    document.body.appendChild(menu);

    // Viewport boundary check (same as showPlaylistContextMenu)
    const rect = menu.getBoundingClientRect();
    let px = e.clientX, py = e.clientY;
    if (px + rect.width  > window.innerWidth)  px = window.innerWidth  - rect.width  - 5;
    if (py + rect.height > window.innerHeight) py = window.innerHeight - rect.height - 5;
    menu.style.left = `${px}px`;
    menu.style.top  = `${py}px`;

    menu.addEventListener('click', async (ev) => {
        const item = ev.target.closest('.context-menu-item');
        if (!item || item.classList.contains('disabled')) return;
        const action = item.dataset.action;

        if (action === 'toggle-slice') {
            const sid = item.dataset.slice;
            const next = currentSlices.includes(sid)
                ? currentSlices.filter(s => s !== sid)
                : [...currentSlices, sid];
            await patchLayerRouting(clipId, layerId, next, bypassMain);
        } else if (action === 'toggle-bypass') {
            await patchLayerRouting(clipId, layerId, currentSlices, !bypassMain);
        } else if (action === 'clear-routing') {
            await patchLayerRouting(clipId, layerId, [], false);
        }
        menu.remove();
    });

    // Close on outside click
    setTimeout(() => {
        document.addEventListener('click', () => {
            document.getElementById('layerContextMenu')?.remove();
        }, { once: true });
    }, 0);
};

async function patchLayerRouting(clipId, layerId, slices, bypassMain) {
    try {
        await fetch(`${API_BASE}/api/clips/${clipId}/layers/${layerId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ output_slices: slices, bypass_main: bypassMain })
        });
        // Update local cache
        const layer = (clipLayers[clipId] || []).find(l => l.layer_id === layerId);
        if (layer) { layer.output_slices = slices; layer.bypass_main = bypassMain; }
        renderLayerPanel();
    } catch(e) {
        showToast('Failed to update layer routing', 'error');
    }
}
```

### 5c. Slice color map

Populate `window.sliceColorMap` from the output-settings panel's existing
slice color data when slices are loaded/changed:

```js
window.sliceColorMap = {};   // populated on slice config load
// e.g. after fetching slice list: slices.forEach(s => sliceColorMap[s.slice_id] = s.color || '#e67e22');
```

---

## 6. TexturePool — capacity note

Each active slice group requires **2 extra pool slots** (cur + alt) for the
duration of the blend loop.  With the current `MAX_PER_BUCKET = 16` cap and
a typical 8–16 layers, headroom is sufficient for 4–6 concurrent slice groups.
If more are needed, raise `MAX_PER_BUCKET` or ensure slice groups are not all
at canvas resolution (sub-resolution slices use a smaller bucket).

---

## 7. Implementation order

| Step | File(s) | Lines | Notes |
|------|---------|-------|-------|
| 1 | `layer.py` | ~15 | Add `output_slices`, `bypass_main` fields + `to_dict` |
| 2 | `compositor.py` | ~50 | Ping-pong alloc, blend loop insert, hook fire, cleanup |
| 3 | `manager.py` | ~15 | `_output_layer_slice_hook` field + setter |
| 4 | `outputs/manager.py` | ~35 | `update_gpu_layer_slices()` method |
| 5 | `core.py` | ~8 | Register `_layer_slice_hook_fn` |
| 6 | `player.js` | ~100 | Context menu, badge, `patchLayerRouting`, CSS |

**Total: ~220 lines.**  No new files, no shader changes, no new GPU objects
beyond extra pool texture pairs.
