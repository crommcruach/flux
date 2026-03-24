# Effect Reorder Implementation Plan

**Feature:** Drag-and-drop reordering of effects in the Clip FX panel via the effect header.  
**Status:** Not started  
**Scope:** Clip-level effects only (`clipFxList` panel in `player.html`). Player-level effect chains (global `effects.js` page) are out of scope for now.

---

## Background

Effects applied to a clip are stored as an ordered list in `ClipRegistry.clips[clip_id]['effects']`. The order determines the processing pipeline — effect[0] is applied first, effect[N-1] last. Currently there is no mechanism to reorder this list after effects have been added.

At runtime the order is mirrored in `layer.effects` (the live plugin-instance list). A reorder must therefore update both the registry (for persistence) and the live layer (for immediate effect).

---

## Architecture Overview

```
User drags effect header in #clipFxList
        │
        ▼
JS drag-drop handlers (player.js)
  - on drop: compute new_order array [2, 0, 1]
  - call POST /api/player/<player_id>/clip/<clip_id>/effects/reorder
        │
        ▼
API endpoint (playback.py)
  - calls clip_registry.reorder_clip_effects(clip_id, new_order)
  - calls player.reload_all_layer_effects() on all active players
  - emits effects.changed WebSocket event
  - calls session_state.save_async()
        │
        ▼
ClipRegistry (registry.py)
  - reorders self.clips[clip_id]['effects'] in place
  - calls _invalidate_cache(clip_id)
```

---

## Backend Changes

### 1. `src/modules/player/clips/registry.py`

Add the following method after `remove_effect_from_clip`:

```python
def reorder_clip_effects(self, clip_id: str, new_order: List[int]) -> bool:
    """
    Reorder clip effects according to new_order index list.

    Args:
        clip_id: Unique clip ID
        new_order: List of current indices in the desired new order.
                   E.g. [2, 0, 1] moves effect[2] to position 0.
                   Must contain every current index exactly once.
                   System plugins (transport) at index 0 are read-only
                   and must remain at index 0.

    Returns:
        True if reordered successfully, False on error.
    """
    if clip_id not in self.clips:
        logger.error(f"reorder_clip_effects: clip not found: {clip_id}")
        return False

    effects = self.clips[clip_id]['effects']
    n = len(effects)

    if sorted(new_order) != list(range(n)):
        logger.error(f"reorder_clip_effects: invalid new_order {new_order} for {n} effects")
        return False

    # Enforce: transport (system plugin at index 0) must stay at index 0
    if n > 0 and effects[0].get('metadata', {}).get('system_plugin', False):
        if new_order[0] != 0:
            logger.error("reorder_clip_effects: system plugin (transport) must remain at index 0")
            return False

    self.clips[clip_id]['effects'] = [effects[i] for i in new_order]
    self._invalidate_cache(clip_id)
    logger.debug(f"🔀 Clip {clip_id[:8]}... effects reordered: {new_order}")
    return True
```

---

### 2. `src/modules/api/player/playback.py`

Add a new endpoint after the existing `toggle_clip_effect` route:

```python
@app.route('/api/player/<player_id>/clip/<clip_id>/effects/reorder', methods=['POST'])
def reorder_clip_effects(player_id, clip_id):
    """Reorder effects in a clip's effect chain."""
    try:
        data = request.get_json()
        new_order = data.get('new_order')

        if new_order is None or not isinstance(new_order, list):
            return jsonify({"success": False, "error": "Missing or invalid new_order"}), 400

        success = clip_registry.reorder_clip_effects(clip_id, new_order)
        if not success:
            return jsonify({"success": False, "error": "Failed to reorder effects"}), 400

        # Reload live layer effects on all players holding this clip
        for check_player_id, check_player in player_manager.players.items():
            if check_player and hasattr(check_player, 'layers') and check_player.layers:
                if any(layer.clip_id == clip_id for layer in check_player.layers):
                    if hasattr(check_player, 'reload_all_layer_effects'):
                        check_player.reload_all_layer_effects()

        # Persist
        session_state = get_session_state()
        if session_state:
            session_state.save_async(player_manager, clip_registry)

        # Notify UI
        if socketio:
            socketio.emit('effects.changed', {
                'player_id': player_id,
                'clip_id': clip_id,
                'action': 'reorder',
                'new_order': new_order
            }, namespace='/effects')

        return jsonify({"success": True})

    except Exception as e:
        logger.error(f"Error reordering clip effects: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

**Note:** Calling `reload_all_layer_effects()` after a reorder recreates all plugin instances from the registry. This resets the transport `current_position`. A smarter path would be to reorder `layer.effects` in-place without recreating instances — but that requires careful index bookkeeping. For a first implementation, the reload approach is simpler and safe; the transport reset on effect reorder is an acceptable trade-off (users rarely reorder effects during playback).

---

## Frontend Changes

### 3. `frontend/js/player.js` — `renderEffectItem()`

Add a drag handle to the header for non-system-plugins:

```js
// Inside renderEffectItem(), in the effect-header div, before effect-title
${!isSystemPlugin ? '<span class="effect-drag-handle" title="Drag to reorder">☰</span>' : ''}
```

Add `draggable="true"` to the `.effect-item` div for non-system-plugins:

```js
// Change the opening div line:
<div class="effect-item ${isSystemPlugin ? 'system-plugin' : ''} ${!isEnabled ? 'effect-disabled' : ''}"
     id="${player}-effect-${index}"
     ${!isSystemPlugin ? 'draggable="true"' : ''}>
```

### 4. `frontend/js/player.js` — `renderClipEffects()`

After `container.innerHTML = html;`, call a new function `setupClipFxDragDrop()`:

```js
setupClipFxDragDrop();
```

### 5. `frontend/js/player.js` — new `setupClipFxDragDrop()` function

Add this function (call site: bottom of `renderClipEffects`, and once on init):

```js
function setupClipFxDragDrop() {
    const container = document.getElementById('clipFxList');
    if (!container) return;

    let dragSrcIndex = null;

    container.addEventListener('dragstart', (e) => {
        const item = e.target.closest('.effect-item[draggable="true"]');
        if (!item) { e.preventDefault(); return; }
        // Only allow drag if handle was the origin
        if (!e.target.closest('.effect-drag-handle')) { e.preventDefault(); return; }

        dragSrcIndex = parseInt(item.id.split('-').pop());
        item.classList.add('fx-dragging');
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', String(dragSrcIndex));
    });

    container.addEventListener('dragend', (e) => {
        container.querySelectorAll('.effect-item').forEach(el => {
            el.classList.remove('fx-dragging', 'fx-drag-over-top', 'fx-drag-over-bottom');
        });
        dragSrcIndex = null;
    });

    container.addEventListener('dragover', (e) => {
        const item = e.target.closest('.effect-item[draggable="true"]');
        if (!item || dragSrcIndex === null) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        // Determine top/bottom half for insertion indicator
        container.querySelectorAll('.effect-item').forEach(el => {
            el.classList.remove('fx-drag-over-top', 'fx-drag-over-bottom');
        });
        const rect = item.getBoundingClientRect();
        const isTopHalf = e.clientY < rect.top + rect.height / 2;
        item.classList.add(isTopHalf ? 'fx-drag-over-top' : 'fx-drag-over-bottom');
    });

    container.addEventListener('dragleave', (e) => {
        const item = e.target.closest('.effect-item');
        if (item) item.classList.remove('fx-drag-over-top', 'fx-drag-over-bottom');
    });

    container.addEventListener('drop', async (e) => {
        e.preventDefault();
        const item = e.target.closest('.effect-item[draggable="true"]');
        if (!item || dragSrcIndex === null) return;

        let destIndex = parseInt(item.id.split('-').pop());
        if (dragSrcIndex === destIndex) return;

        // Build new_order: move dragSrcIndex to destIndex position
        const n = clipEffects.length;
        const indices = Array.from({ length: n }, (_, i) => i);
        indices.splice(dragSrcIndex, 1);          // remove src
        const insertAt = destIndex > dragSrcIndex ? destIndex : destIndex;
        // Adjust insertion position after removal
        const adjustedDest = destIndex > dragSrcIndex ? destIndex - 1 : destIndex;
        const rect = item.getBoundingClientRect();
        const isTopHalf = e.clientY < rect.top + rect.height / 2;
        const finalDest = isTopHalf ? adjustedDest : adjustedDest + 1;
        indices.splice(Math.max(0, Math.min(finalDest, n - 1)), 0, dragSrcIndex);

        // Skip if transport is at index 0 and would move (enforced server-side too)
        if (clipEffects[0]?.metadata?.system_plugin && indices[0] !== 0) {
            showToast('Transport effect must remain at position 0', 'warning');
            return;
        }

        const targetClipId = selectedLayerClipId || selectedClipId;
        try {
            const resp = await fetch(
                `${API_BASE}/api/player/${selectedClipPlayerType}/clip/${targetClipId}/effects/reorder`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_order: indices })
                }
            );
            const data = await resp.json();
            if (data.success) {
                await refreshClipEffects();
            } else {
                showToast(`Reorder failed: ${data.error}`, 'error');
            }
        } catch (err) {
            console.error('Effect reorder error:', err);
            showToast('Effect reorder failed', 'error');
        }
    });
}
```

---

## CSS Changes

Add to the effects / player stylesheet (search for `.effect-header` declarations):

```css
/* Drag handle */
.effect-drag-handle {
    cursor: grab;
    padding: 0 6px;
    opacity: 0.4;
    user-select: none;
    font-size: 14px;
    flex-shrink: 0;
}
.effect-drag-handle:active {
    cursor: grabbing;
}

/* Dragging state */
.effect-item.fx-dragging {
    opacity: 0.4;
}

/* Drop position indicators */
.effect-item.fx-drag-over-top {
    border-top: 2px solid #0bf;
}
.effect-item.fx-drag-over-bottom {
    border-bottom: 2px solid #0bf;
}
```

---

## Testing Checklist

- [ ] Add 3+ non-system effects to a clip
- [ ] Drag effect by its header handle — confirm `☰` handle is the only drag trigger (clicking parameters must NOT start a drag)
- [ ] Drop above another effect — confirm order changes correctly
- [ ] Drop below another effect — confirm order changes correctly
- [ ] Verify transport plugin (system) cannot be dragged (no handle, `draggable` not set)
- [ ] Verify transport plugin cannot be displaced from index 0 (server rejects, toast shown)
- [ ] Verify video does NOT reset when reordering effects while clip is playing (see known issue — reload_all_layer_effects resets transport; consider live in-place reorder as a follow-up)
- [ ] Verify session save persists the new order (reload page and check Clip FX panel)
- [ ] Verify WebSocket `effects.changed` event fires and UI refreshes in other open tabs

---

## Known Constraints / Follow-up

- **Transport reset on reorder:** `reload_all_layer_effects()` recreates all plugin instances, resetting the transport position. This is the same trade-off as adding a new effect. A future improvement is to reorder `layer.effects` in-place (without destroying instances) and skip the full reload.
- **Player-level effect chain:** The global `EffectProcessor` chains (`video_effect_chain`, `artnet_effect_chain`) have no reorder mechanism. Those are less commonly used and out of scope.
