# Centralized Shader Source Cache

## Status
**Deferred** — current per-class `_shader_src` cache already solves the OneDrive I/O problem.

## Problem
Each GPU effect plugin caches its shader source in a class-level attribute (`_shader_src`).
This is correct but scattered — 4 plugins today, will grow as more GPU effects are added.

## Proposed Solution
A single `load_shader_cached(path: str) -> str` utility in `src/modules/gpu/shader_cache.py`:

```python
_cache: dict[str, str] = {}

def load_shader_cached(path: str) -> str:
    if path not in _cache:
        with open(path) as f:
            _cache[path] = f.read()
    return _cache[path]

def clear_cache() -> None:
    """For dev hot-reload."""
    _cache.clear()
```

Each plugin's `get_shader()` becomes a one-liner:

```python
def get_shader(self):
    return load_shader_cached(_SHADER_PATH)
```

## Files to Change
| File | Change |
|---|---|
| `src/modules/gpu/shader_cache.py` | **Create** — module with `load_shader_cached` + `clear_cache` |
| `plugins/effects/transform.py` | Remove `_shader_src`, call `load_shader_cached` |
| `plugins/effects/brightness_contrast.py` | Same |
| `plugins/effects/colorize.py` | Same |
| `plugins/effects/hue_rotate.py` | Same |
| Any future GPU plugin | Use `load_shader_cached` from day 1 |

## Benefits
- Single source of truth for shader I/O — no per-plugin boilerplate
- `clear_cache()` enables dev-time hot-reload without restarting the process
- Easy to extend (e.g. add `mtime` check for auto-invalidation in debug mode)

## Current Workaround
Per-class `_shader_src` attribute on `TransformEffect`, `BrightnessContrastEffect`,
`ColorizeEffect`, `HueRotateEffect` — files read once from disk at first call, then RAM-only.
