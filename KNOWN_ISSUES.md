# Known Issues

Bugs and problems identified but not yet resolved. Add new entries at the top of the relevant section.

---

## UI / Frontend

### Video output: no default fullscreen slice on clean start
**Status:** Open
**Description:** On a clean start (no saved output configuration), the video output settings page is empty. The user must manually create a slice and map it to the main display output before any video is shown. There is no sensible default, which is confusing especially for first-time setup or after a config reset.
**Planned fix:** On clean start (no slices defined), automatically create a single fullscreen slice that covers the full canvas and maps it to the `main_display` output. This should be a non-destructive default — existing saved configurations must not be affected.



### Fullscreen preview "Connection Lost" overlay — false positives
**File:** `frontend/fullscreen.html`
**Status:** Workaround applied (health check disabled)
**Description:** The periodic connection health check triggered the "Connection Lost" overlay even when video was playing normally. Root cause unclear — likely the MJPEG stream stalls briefly under load and the 5 s (later 15 s) timeout was still too tight.
**Workaround:** Health check `setInterval` is commented out. Overlay will no longer auto-trigger.
**To fix:** Detect disconnection more reliably — e.g. track actual image `onerror` events and WebSocket close events instead of polling frame timestamps.

---

## Plugins / Effects

### ASCII art plugin broken — fragments only, performance degraded
**Status:** Open
**Description:** The ASCII art plugin no longer renders correctly. Output shows only partial fragments instead of a full ASCII frame, and overall performance is significantly degraded during playback with this plugin active.
**Planned fix:** Investigate the plugin's frame conversion logic — likely a buffer size or stride mismatch introduced by a recent change to the frame pipeline. Also profile the character-mapping loop, which may need vectorisation or caching to restore acceptable performance.

### No multi-effect assignment possible
**Status:** Open
**Description:** Only a single effect can be assigned to a layer/player at a time. There is no way to stack or chain multiple effects simultaneously.
**Planned fix:** Implement an effect chain / pipeline per layer that allows multiple effects to be applied in sequence.

### Video resets on effect toggle (on/off)
**Status:** Fixed
**Description:** Toggling an effect on or off causes the video to reset (jumps back to the beginning or re-initialises playback).
**Root cause:** `toggle_clip_effect` called `reload_all_layer_effects()` which recreated all plugin instances from the registry, losing the transport plugin's live play position.
**Fix:** In `toggle_clip_effect` (playback.py), directly toggle the `enabled` flag on the live layer effect at the given index instead of reloading all effects. The registry is still updated; only the live instance flag is changed without recreating any plugins.

### Toggle effects cannot use timeline audio-reactive dynamic parameters
**Status:** Open
**Description:** Effects that are toggled on/off (enable/disable) cannot use timeline-based audio-reactive dynamic parameters. When an effect is toggled, the dynamic parameter binding is lost or not re-established, so audio-reactive sequences have no effect on the plugin.
**Planned fix:** Re-attach dynamic parameter bindings after an effect toggle, ensuring the sequence engine re-registers the effect instance with its sequences.

### Datamosh — `reset` parameter is a slider, not a button
**File:** `plugins/effects/datamosh.py`
**Status:** Open
**Description:** The `reset` parameter is rendered as a 0/1 INT slider. It works but UX is poor — user must drag slider to 1 and it snaps back to 0. Ideally this should be a one-shot trigger button.
**Planned fix:** Change parameter type to `trigger` (or equivalent) once the UI supports it, or add auto-reset via scene-cut detection (`reset_threshold` parameter).

---

## Backend / Core

### Master/slave mode — slave shows only first frame (still image)
**Status:** Open
**Description:** When running in master/slave mode, the slave player displays only the first frame of the current clip as a still image instead of playing the video.
**Planned fix:** Investigate slave playback sync — likely the slave receives the clip/position state but does not advance its own frame loop, or the stream is not being pushed correctly to slave clients.

### Display output process dies with no automatic recovery
**File:** `src/modules/player/outputs/plugins/display_output.py`
**Status:** Open
**Description:** When the display output subprocess crashes or exits unexpectedly, `send_frame()` logs `[main_display] send_frame: display process not alive` and all subsequent frames are silently dropped. There is no automatic restart or recovery — the display output remains dead for the rest of the session.
**Planned fix:** Detect the dead process in `send_frame()` (or a watchdog loop) and automatically restart the display subprocess, then resume normal output. Should include a cooldown/retry limit to avoid restart loops on hard failures.

### Playlist autoplay disrupts parameter editing
**Status:** Open
**Description:** When a playlist is running in autoplay mode, the active clip advances automatically. If a user is editing parameters on a clip, the playlist switches to the next clip mid-edit, forcing the user to either wait for the clip to cycle back around or manually click it again. This is particularly disruptive during show preparation.
**Planned fix:** Implement an "edit lock" or "preparation mode" that temporarily pauses autoadvance while the user has a clip's parameter panel open or is actively editing. Options to explore:
- Auto-pause autoplay when any parameter panel is focused, resume on close
- A dedicated "Prep Mode" toggle that freezes the playlist position without stopping playback
- A per-clip "pin" button that keeps the clip selected in the UI independently of the active playback position

---

## Performance

### Reverse play performance is slow
**Status:** Open
**Description:** Playing video in reverse (negative speed/direction) has noticeably degraded performance compared to forward playback. Frame delivery is inconsistent and the perceived frame rate drops under normal load.
**Planned fix:** Investigate frame decoding strategy for reverse playback — likely requires pre-buffering frames or seeking backwards frame-by-frame, which is expensive. Consider caching a short reverse buffer or using a dedicated reverse-decode path.
