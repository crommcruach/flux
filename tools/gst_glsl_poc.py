#!/usr/bin/env python3
"""
GStreamer GL + GLSL Proof-of-Concept  —  Py_artnet
====================================================
Validates whether GStreamer can replace ModernGL as the GPU rendering
backend, solving the AMD WGL thread-affinity / context-sharing bugs.

Four progressive tests:
  1. Environment   — GStreamer runtime present, Python bindings importable
  2. GL elements   — glupload / glshader / gldownload registered in the registry
  3. Shader run    — transform.frag adapted for GStreamer runs without GL errors
  4. Benchmark     — 50 frames through the GL pipeline, per-frame latency

What we're testing specifically:
  - Does GStreamer create a working GL context on this AMD GPU?
  - Does our GLSL source compile through GStreamer's GL loader?
  - Can we read frames back as numpy arrays from appsink?
  - What is the baseline per-frame latency?

Usage:
    python tools/gst_glsl_poc.py

Install GStreamer if missing:
    https://gstreamer.freedesktop.org/data/pkg/windows/
    Download: gstreamer-1.0-msvc-x86_64-X.X.X.msi  (complete installer, ~200 MB)
    After install: reopen this terminal so PATH includes the GStreamer bin/
"""

import os
import sys
import time
import threading
import traceback
import ctypes.util

# ── ensure workspace root is on sys.path ─────────────────────────────────────
WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

# ── GStreamer DLL + Python bindings bootstrap (Windows, Python 3.8+) ─────────
# Python 3.8+ no longer searches PATH for DLLs of C extensions.
# We must call os.add_dll_directory() BEFORE any gi import so that _gi.pyd
# can find libglib-2.0-0.dll etc. from the GStreamer bin/ folder.
_GST_ROOTS = [
    os.environ.get("GSTREAMER_1_0_ROOT_MSVC_X86_64", ""),
    os.environ.get("GSTREAMER_1_0_ROOT_MINGW_X86_64", ""),
    os.environ.get("GSTREAMER_1_0_ROOT_X86_64", ""),
    r"C:\Program Files\gstreamer\1.0\msvc_x86_64",
    r"C:\Program Files\gstreamer\1.0\mingw_x86_64",
    r"C:\gstreamer\1.0\msvc_x86_64",
    r"C:\gstreamer-mingw\1.0\mingw_x86_64",
    r"C:\gstreamer\1.0\mingw_x86_64",
]
for _root in _GST_ROOTS:
    if _root and os.path.isdir(_root):
        _bin = os.path.join(_root, "bin")
        _sp  = os.path.join(_root, "lib", "site-packages")
        if os.path.isdir(_bin):
            os.add_dll_directory(_bin)  # type: ignore[attr-defined]  # py3.8+
        if os.path.isdir(_sp) and _sp not in sys.path:
            sys.path.insert(0, _sp)
        break

CANVAS_W, CANVAS_H = 640, 360   # small canvas for POC speed
BENCH_FRAMES       = 50
FRAME_TIMEOUT_MS   = 2_000      # ms to wait for each appsink frame

# ─────────────────────────────────────────────────────────────────────────────
# Transform shader adapted for GStreamer glshader element:
#   v_uv          →  v_texcoord  (GStreamer's built-in varying name)
#   inputTexture  →  tex         (GStreamer's default texture uniform name)
# All other logic is identical to src/modules/gpu/shaders/transform.frag
# ─────────────────────────────────────────────────────────────────────────────
TRANSFORM_FRAG_GST = """\
#version 330 core
in vec2 v_texcoord;
out vec4 fragColor;

uniform sampler2D tex;

// Transform parameters as GLSL constants for POC (hardcoded 2× scale).
// In production these become uniforms set via glshader's set-uniforms action.
const vec2  anchor    = vec2(0.5, 0.5);
const vec2  scale     = vec2(2.0, 2.0);   // 200% — same as the failing test case
const vec2  translate = vec2(0.0, 0.0);
const float rotation  = 0.0;

void main() {
    vec2 uv = v_texcoord - anchor;
    uv /= max(scale, vec2(0.001));
    float c = cos(-rotation);
    float s = sin(-rotation);
    uv = vec2(c * uv.x - s * uv.y, s * uv.x + c * uv.y);
    uv += anchor - vec2(translate.x, -translate.y);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        fragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }
    fragColor = texture(tex, uv);
}
"""

PASSTHROUGH_FRAG_GST = """\
#version 330 core
in vec2 v_texcoord;
out vec4 fragColor;
uniform sampler2D tex;
void main() {
    fragColor = texture(tex, v_texcoord);
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hr(label: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {label}")
    print('─'*60)

def _ok(msg: str) -> None:
    print(f"  ✓  {msg}")

def _fail(msg: str) -> None:
    print(f"  ✗  {msg}")

def _info(msg: str) -> None:
    print(f"     {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Environment
# ─────────────────────────────────────────────────────────────────────────────

def test_environment():
    _hr("TEST 1 — Environment check")

    # Detect GStreamer binary paths on Windows
    gst_root = None
    for env_var in (
        "GSTREAMER_1_0_ROOT_MSVC_X86_64",
        "GSTREAMER_1_0_ROOT_X86_64",
        "GSTREAMER_1_0_ROOT_MSVC_X86",
    ):
        val = os.environ.get(env_var)
        if val and os.path.isdir(val):
            gst_root = val
            _ok(f"GStreamer root via {env_var}: {val}")
            break

    if gst_root is None:
        # Try common install paths
        candidates = [
            r"C:\gstreamer\1.0\msvc_x86_64",
            r"C:\gstreamer\1.0\x86_64",
        ]
        for c in candidates:
            if os.path.isdir(c):
                gst_root = c
                _ok(f"GStreamer root detected at: {c}")
                break

    if gst_root is None:
        _fail("GStreamer root NOT found. Install from:")
        _info("https://gstreamer.freedesktop.org/data/pkg/windows/")
        _info("Download the MSVC complete installer and run it.")
        _info("Then reopen this terminal.")
        return False

    # Add bin/ to PATH so gi can find the DLLs
    gst_bin = os.path.join(gst_root, "bin")
    if gst_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = gst_bin + os.pathsep + os.environ.get("PATH", "")
        _info(f"Added {gst_bin} to PATH for this session")

    # Set plugin / typelib paths gi needs
    typelib_path = os.path.join(gst_root, "lib", "girepository-1.0")
    if os.path.isdir(typelib_path):
        cur = os.environ.get("GI_TYPELIB_PATH", "")
        if typelib_path not in cur:
            os.environ["GI_TYPELIB_PATH"] = typelib_path + (os.pathsep + cur if cur else "")

    # Now try importing
    try:
        import gi  # type: ignore
        gi.require_version("Gst", "1.0")
        gi.require_version("GstApp", "1.0")
        gi.require_version("GstVideo", "1.0")
        from gi.repository import Gst, GstApp, GstVideo  # type: ignore  # noqa: F401
        Gst.init(None)
        ver = Gst.version_string()
        _ok(f"gi + GStreamer Python bindings OK  ({ver})")
    except Exception as exc:
        _fail(f"gi import failed: {exc}")
        _info("Ensure the GStreamer runtime 'complete' installer was used.")
        _info("PyGObject (gi) comes bundled with the GStreamer MSVC installer.")
        return False

    # Check GLib version via gi
    try:
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib  # type: ignore  # noqa: F401
        _ok("GLib bindings OK")
    except Exception as exc:
        _fail(f"GLib import failed: {exc}")
        return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — GL element registry
# ─────────────────────────────────────────────────────────────────────────────

def test_gl_elements():
    _hr("TEST 2 — GL element registry")

    import gi  # type: ignore
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst  # type: ignore

    required = ["glupload", "gldownload", "glshader", "videotestsrc", "appsrc", "appsink"]
    all_ok = True
    for name in required:
        factory = Gst.ElementFactory.find(name)
        if factory:
            _ok(f"{name:20s}  found (rank {factory.get_rank()})")
        else:
            _fail(f"{name:20s}  NOT found — install gst-plugins-base or gst-plugins-bad")
            all_ok = False

    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# Shared GLib main loop runner (needed for GL context message pump on Windows)
# ─────────────────────────────────────────────────────────────────────────────

class GLibLoopThread:
    """Runs a GLib main loop in a background thread so GStreamer can pump GL
    window messages on Windows (WGL context needs the Win32 message loop)."""

    def __init__(self):
        import gi  # type: ignore
        gi.require_version("GLib", "2.0")
        from gi.repository import GLib  # type: ignore
        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, daemon=True)
        self._thread.start()

    def stop(self):
        self._loop.quit()
        self._thread.join(timeout=2.0)


def _run_pipeline(pipe_str: str, timeout_s: float = 5.0) -> bool:
    """Launch a pipeline, run it for up to timeout_s, return True if EOS or
    no error occurred."""
    import gi  # type: ignore
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst  # type: ignore

    pipeline = Gst.parse_launch(pipe_str)
    bus = pipeline.get_bus()
    bus.add_signal_watch()

    done = threading.Event()
    error_holder: list = []

    def on_message(_, msg):
        if msg.type == Gst.MessageType.EOS:
            done.set()
        elif msg.type == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            error_holder.append(f"{err.message}  ({debug})")
            done.set()

    bus.connect("message", on_message)

    loop_thread = GLibLoopThread()
    pipeline.set_state(Gst.State.PLAYING)
    done.wait(timeout=timeout_s)
    pipeline.set_state(Gst.State.NULL)
    loop_thread.stop()

    if error_holder:
        _fail(f"Pipeline error: {error_holder[0]}")
        return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — GLSL shader compilation + GL pipeline execution
# ─────────────────────────────────────────────────────────────────────────────

def test_shader_pipeline():
    _hr("TEST 3 — GLSL shader compilation via glshader")

    import gi  # type: ignore
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst  # type: ignore

    w, h = CANVAS_W, CANVAS_H

    # Phase 3a: passthrough shader
    _info("Phase 3a: passthrough GLSL …")
    frag_escaped = PASSTHROUGH_FRAG_GST.replace('"', '\\"').replace('\n', '\\n')
    pipe_a = (
        f'videotestsrc num-buffers=5 pattern=ball ! '
        f'video/x-raw,width={w},height={h},format=RGBA ! '
        f'glupload ! '
        f'glshader fragment="{frag_escaped}" ! '
        f'gldownload ! '
        f'video/x-raw,format=RGBA ! '
        f'fakesink'
    )
    ok_a = _run_pipeline(pipe_a, timeout_s=8.0)
    if ok_a:
        _ok("Passthrough shader compiled and ran OK")
    else:
        _fail("Passthrough shader FAILED — GL not functional on this machine")
        return False

    # Phase 3b: transform shader (the actual failing case from the bug report)
    _info("Phase 3b: transform shader at 200% scale (the bug reproduction) …")
    frag_escaped2 = TRANSFORM_FRAG_GST.replace('"', '\\"').replace('\n', '\\n')
    pipe_b = (
        f'videotestsrc num-buffers=5 pattern=ball ! '
        f'video/x-raw,width={w},height={h},format=RGBA ! '
        f'glupload ! '
        f'glshader fragment="{frag_escaped2}" ! '
        f'gldownload ! '
        f'video/x-raw,format=RGBA ! '
        f'fakesink'
    )
    ok_b = _run_pipeline(pipe_b, timeout_s=8.0)
    if ok_b:
        _ok("Transform shader (200% scale) compiled and ran OK")
    else:
        _fail("Transform shader FAILED — GLSL compile or GL error")
        return False

    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — numpy round-trip via appsrc → glshader → appsink
# ─────────────────────────────────────────────────────────────────────────────

def test_numpy_roundtrip():
    _hr("TEST 4 — numpy round-trip  (appsrc → glshader → appsink)")

    import gi  # type: ignore
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp  # type: ignore
    import numpy as np

    w, h = CANVAS_W, CANVAS_H
    frag_escaped = PASSTHROUGH_FRAG_GST.replace('"', '\\"').replace('\n', '\\n')

    pipe_str = (
        f'appsrc name=src emit-signals=false format=time '
        f'caps=video/x-raw,format=RGBA,width={w},height={h},framerate=30/1 ! '
        f'glupload ! '
        f'glshader fragment="{frag_escaped}" ! '
        f'gldownload ! '
        f'video/x-raw,format=RGBA ! '
        f'appsink name=sink emit-signals=false sync=false'
    )

    pipeline = Gst.parse_launch(pipe_str)
    src: GstApp.AppSrc = pipeline.get_by_name("src")
    sink: GstApp.AppSink = pipeline.get_by_name("sink")

    loop_thread = GLibLoopThread()
    pipeline.set_state(Gst.State.PLAYING)

    # Build a test frame: red gradient
    input_frame = np.zeros((h, w, 4), dtype=np.uint8)
    input_frame[:, :w//2, 0] = 200  # left half red
    input_frame[:, :, 3] = 255      # full alpha

    # Push one frame
    buf_bytes = input_frame.tobytes()
    buf = Gst.Buffer.new_wrapped(buf_bytes)
    buf.pts = 0
    buf.duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)
    flow = src.emit("push-buffer", buf)
    if flow != Gst.FlowReturn.OK:
        _fail(f"appsrc push-buffer returned {flow}")
        pipeline.set_state(Gst.State.NULL)
        loop_thread.stop()
        return False

    src.emit("end-of-stream")

    # Pull the processed frame back
    sample = sink.emit("pull-sample")
    if sample is None:
        # Try timed pull
        sample = sink.emit("try-pull-sample", FRAME_TIMEOUT_MS * Gst.MSECOND)

    pipeline.set_state(Gst.State.NULL)
    loop_thread.stop()

    if sample is None:
        _fail("appsink returned no sample — pipeline stalled or GL error")
        return False

    gbuf = sample.get_buffer()
    ok_map, info = gbuf.map(Gst.MapFlags.READ)
    if not ok_map:
        _fail("Could not map output buffer")
        return False

    out_bytes = bytes(info.data)
    gbuf.unmap(info)
    out_frame = np.frombuffer(out_bytes, dtype=np.uint8).reshape(h, w, 4)

    _ok(f"Received output frame: shape={out_frame.shape}  dtype={out_frame.dtype}")
    _info(f"Input  red mean (left half):  {input_frame[:, :w//2, 0].mean():.1f}")
    _info(f"Output red mean (left half):  {out_frame[:, :w//2, 0].mean():.1f}")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Latency benchmark
# ─────────────────────────────────────────────────────────────────────────────

def test_benchmark():
    _hr(f"TEST 5 — Latency benchmark ({BENCH_FRAMES} frames via glshader)")

    import gi  # type: ignore
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp  # type: ignore
    import numpy as np

    w, h = CANVAS_W, CANVAS_H
    frag_escaped = TRANSFORM_FRAG_GST.replace('"', '\\"').replace('\n', '\\n')

    pipe_str = (
        f'appsrc name=src emit-signals=false format=time '
        f'caps=video/x-raw,format=RGBA,width={w},height={h},framerate=30/1 ! '
        f'glupload ! '
        f'glshader fragment="{frag_escaped}" ! '
        f'gldownload ! '
        f'video/x-raw,format=RGBA ! '
        f'appsink name=sink emit-signals=false sync=false'
    )

    pipeline = Gst.parse_launch(pipe_str)
    src: GstApp.AppSrc = pipeline.get_by_name("src")
    sink: GstApp.AppSink = pipeline.get_by_name("sink")

    loop_thread = GLibLoopThread()
    pipeline.set_state(Gst.State.PLAYING)

    frame_data = np.random.randint(0, 255, (h, w, 4), dtype=np.uint8).tobytes()
    frame_duration = Gst.util_uint64_scale_int(1, Gst.SECOND, 30)

    latencies = []
    errors = 0
    t_total_start = time.perf_counter()

    for i in range(BENCH_FRAMES):
        buf = Gst.Buffer.new_wrapped(frame_data)
        buf.pts = i * frame_duration
        buf.duration = frame_duration

        t0 = time.perf_counter()
        src.emit("push-buffer", buf)
        sample = sink.emit("try-pull-sample", FRAME_TIMEOUT_MS * Gst.MSECOND)
        t1 = time.perf_counter()

        if sample is None:
            errors += 1
        else:
            latencies.append((t1 - t0) * 1000)

    src.emit("end-of-stream")
    pipeline.set_state(Gst.State.NULL)
    loop_thread.stop()

    total_s = time.perf_counter() - t_total_start

    if not latencies:
        _fail("No frames received during benchmark")
        return False

    arr = sorted(latencies)
    avg  = sum(arr) / len(arr)
    p50  = arr[len(arr) // 2]
    p95  = arr[int(len(arr) * 0.95)]
    achieved_fps = len(latencies) / total_s

    _ok(f"Frames:  {len(latencies)} / {BENCH_FRAMES}  ({errors} errors)")
    _ok(f"FPS:     {achieved_fps:.1f}")
    _ok(f"Latency  avg={avg:.1f}ms  p50={p50:.1f}ms  p95={p95:.1f}ms")
    _info(f"Reference (current ModernGL SSBO on AMD): ~26 ms avg")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  GStreamer GL + GLSL POC  —  Py_artnet")
    print("=" * 60)

    results: dict[str, bool] = {}

    results["1_environment"] = test_environment()
    if not results["1_environment"]:
        print("\n⛔  GStreamer not available. Install it first (see above).")
        sys.exit(1)

    results["2_gl_elements"] = test_gl_elements()
    if not results["2_gl_elements"]:
        print("\n⛔  Required GL elements missing. Install gst-plugins-base complete.")
        sys.exit(1)

    results["3_shader"] = test_shader_pipeline()
    results["4_roundtrip"] = test_numpy_roundtrip()
    results["5_benchmark"] = test_benchmark()

    _hr("RESULTS")
    all_passed = True
    for name, passed in results.items():
        label = name.split("_", 1)[1].replace("_", " ").title()
        if passed:
            _ok(label)
        else:
            _fail(label)
            all_passed = False

    print()
    if all_passed:
        print("  ✅  All tests passed — GStreamer GL is viable on this machine.")
        print("      Next step: full pipeline migration (see docs/ARCHITECTURE.md).")
    else:
        print("  ❌  One or more tests failed.")
        print("      Check errors above. GStreamer migration may need driver/version adjustments.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception:
        traceback.print_exc()
        sys.exit(2)
