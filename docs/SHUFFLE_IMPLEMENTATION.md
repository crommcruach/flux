# Shuffle Mode — Implementation Guide

## Overview

Shuffle gives playlists pseudo-random playback while keeping the next clip
deterministic at all times. This is required because `VideoSource.initialize()`
(HAP eager-load) takes up to several hundred milliseconds — the system must
know the next clip well before it is needed to kick off background prefetching.

---

## Core Principle: Pre-Shuffled Queue

Shuffle is **not** "pick a random clip when the current one ends". It is a
**pre-generated permutation** committed to in advance.

```
clips = [A, B, C, D, E]

shuffle_queue = [C, A, E, B, D]   ← Fisher-Yates shuffle at queue-build time
shuffle_pos   = 0                  ← advances with each advance() call
```

At any point `shuffle_queue[shuffle_pos + 1]` is the definite next clip —
available for prefetching immediately after the current clip starts.

When the queue is exhausted, a new permutation is generated with one
constraint: `new_queue[0] != old_queue[-1]` (prevents the same clip playing
twice at the wrap boundary).

---

## Files to Change

### 1. `src/modules/player/playlists/manager.py` — `PlaylistManager`

Add state:
```python
self.shuffle: bool = False
self._shuffle_queue: list[int] = []   # permutation of playlist indices
self._shuffle_pos: int = -1           # position in _shuffle_queue
```

Modify `get_next_index()`:
```python
def get_next_index(self) -> int | None:
    if not self.playlist:
        return None

    if not self.shuffle:
        # existing linear logic
        next_index = self.playlist_index + 1
        if next_index >= len(self.playlist):
            return 0 if self.loop_playlist else None
        return next_index

    # Shuffle path
    if not self._shuffle_queue:
        self._build_shuffle_queue(last_index=self.playlist_index)

    next_pos = self._shuffle_pos + 1
    if next_pos >= len(self._shuffle_queue):
        if not self.loop_playlist:
            return None
        # Regenerate — avoid repeating the last played clip
        self._build_shuffle_queue(last_index=self._shuffle_queue[-1])
        next_pos = 0

    return self._shuffle_queue[next_pos]
```

Add `_build_shuffle_queue()`:
```python
def _build_shuffle_queue(self, last_index: int = -1) -> None:
    import random
    indices = list(range(len(self.playlist)))
    random.shuffle(indices)

    # Swap first element away from last_index to prevent consecutive repeat
    if indices and indices[0] == last_index and len(indices) > 1:
        swap_with = random.randrange(1, len(indices))
        indices[0], indices[swap_with] = indices[swap_with], indices[0]

    self._shuffle_queue = indices
    self._shuffle_pos = -1
```

Modify `advance()` — after computing next index, advance `_shuffle_pos`:
```python
def advance(self, player_name=""):
    next_index = self.get_next_index()
    if next_index is None:
        return None, None

    self.playlist_index = next_index

    if self.shuffle:
        self._shuffle_pos += 1
        if self._shuffle_pos >= len(self._shuffle_queue):
            self._shuffle_pos = 0   # just wrapped after regeneration
    ...
```

Add `get_lookahead_index(n=1)` for prefetch consumers:
```python
def get_lookahead_index(self, n: int = 1) -> int | None:
    """Return the index n steps ahead of the current position, without advancing."""
    if not self.playlist:
        return None
    if not self.shuffle:
        idx = self.playlist_index + n
        if idx >= len(self.playlist):
            return 0 if self.loop_playlist else None
        return idx
    pos = self._shuffle_pos + n
    if pos < len(self._shuffle_queue):
        return self._shuffle_queue[pos]
    if self.loop_playlist:
        return self._shuffle_queue[pos % len(self._shuffle_queue)]
    return None
```

Invalidate queue when playlist contents change (add to `set_playlist()`):
```python
def set_playlist(self, items, ids=None):
    self.playlist = items
    self.playlist_ids = ids if ids else []
    self.playlist_index = -1
    self._shuffle_queue = []   # invalidate — will be rebuilt on next advance
    self._shuffle_pos = -1
```

Persist shuffle state in `to_dict` / `from_dict` — add to `PlayerState`
in `playlist_manager.py`:
```python
# PlayerState.to_dict()
'shuffle': self.shuffle

# PlayerState.from_dict()
state.shuffle = data.get('shuffle', False)
```

---

### 2. `src/modules/player/core.py` — `Player` (clip autoadvance loop)

After a new clip successfully starts playing, kick off a background prefetch
for the next-in-queue clip. Place this immediately after the "Next item loaded"
log line inside the autoadvance block:

```python
# ── Background prefetch for shuffle/sequential caching ───────────────
_lookahead_idx = self.playlist_manager.get_lookahead_index(n=1)
if _lookahead_idx is not None:
    _la_path, _la_id = self.playlist_manager.get_item_at(_lookahead_idx)
    if _la_path and not _la_path.startswith('generator:'):
        import threading as _pt
        def _prefetch(path, cid):
            try:
                from .sources import VideoSource as _VS
                _src = _VS(path, self.canvas_width, self.canvas_height,
                           self.config, clip_id=cid, player_name=self.player_name)
                _src.initialize()   # idempotent — safe to call even if already cached
                logger.debug(f"🔮 [{self.player_name}] Prefetch complete: {os.path.basename(path)}")
            except Exception as _e:
                logger.debug(f"🔮 [{self.player_name}] Prefetch failed: {_e}")
        _pt.Thread(target=_prefetch, args=(_la_path, _la_id),
                   daemon=True, name="ClipPrefetch").start()
# ─────────────────────────────────────────────────────────────────────
```

**Important**: `VideoSource.initialize()` checks `if self.buffer is not None: return True`
so calling it twice on the same path is a no-op after the first call. However,
the prefetch creates a **new** `VideoSource` instance — it does not update
the instance that `advance()` will create later. The value is that the OS page
cache is warm and the file bytes are in RAM, so the real `initialize()` call
will be near-instant (no page-fault stalls).

For a deeper integration (reuse the prefetched buffer), a clip prefetch cache
dict could be added to `Player` — but warm OS page cache is sufficient for
most clips and keeps the implementation simple. See "Future Extensions" below.

---

### 3. REST API — expose `shuffle` toggle

In the playlist API endpoint that updates `PlayerState` (wherever `autoplay`
and `loop` are read/written), add `shuffle`:

```python
# GET player state
'shuffle': player_state.shuffle

# POST / PATCH player state
if 'shuffle' in data:
    player_state.shuffle = bool(data['shuffle'])
    # Invalidate queue so next advance() picks up the change
    playlist_manager._shuffle_queue = []
    playlist_manager._shuffle_pos = -1
```

---

## Serialization / Session Restore

`shuffle` is stored in `PlayerState` (inside each `Playlist`). The shuffle
**queue itself is not persisted** — it is regenerated fresh on the first
`advance()` after restore. This is intentional: restoring the exact previous
random order would feel unexpected.

---

## Edge Cases

| Scenario | Behaviour |
|---|---|
| Single clip | `_build_shuffle_queue` returns `[0]`, loops on itself — same as linear |
| Two clips | Alternates `[0,1]` or `[1,0]` per cycle |
| Playlist modified while playing | `set_playlist()` clears the queue; new permutation built on next `advance()` |
| Shuffle turned off mid-playback | `get_next_index()` falls through to linear path immediately |
| `loop_playlist = False` with shuffle | Plays one full permutation then stops |
| Master/Slave sync | Slaves do not call `advance()` — shuffle has no effect on them |
| Generator clips | Prefetch skipped (generators are instantiated, not file-loaded) |

---

## Future Extensions

### Prefetch Buffer Cache (optional, higher complexity)

Add a dict to `Player`:
```python
self._prefetch_cache: dict[str, VideoSource] = {}  # path -> initialized source
```

In the prefetch thread, store the initialized source in the cache.
In the autoadvance block, check the cache before calling `VideoSource(...).initialize()`:
```python
new_source = self._prefetch_cache.pop(next_item_path, None)
if new_source is None:
    new_source = VideoSource(...)
    new_source.initialize()
```

This would fully eliminate the initialize stall for prefetched clips, at the
cost of holding one extra clip's HAP buffer in RAM while playing the current one.

### Weighted Shuffle (optional)

Add a `weight` field to each clip in `ClipRegistry`. Modify
`_build_shuffle_queue` to use `random.choices(indices, weights=weights, k=len(indices))`
with deduplication — gives frequently-desired clips higher probability without
breaking the deterministic lookahead contract.
