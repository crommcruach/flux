#!/usr/bin/env python3
"""
wgpu-py D3D12 + WGSL Proof-of-Concept  —  Py_artnet
=====================================================
Validates whether wgpu-py (D3D12 backend) can replace ModernGL
as the GPU rendering backend, eliminating AMD WGL thread-affinity bugs.

Five progressive tests:
  1. Adapter      — D3D12 adapter found, AMD GPU detected
  2. Passthrough  — WGSL passthrough shader, numpy frame in → frame out
  3. Transform    — transform.frag logic ported to WGSL at 200% scale
  4. Benchmark    — 50 frames, per-frame latency vs current ~26ms baseline
  5. Thread safety — render from a non-main thread (the WGL bug scenario)

Usage:
    python tools/wgpu_poc.py

Install:
    pip install wgpu       (already done if you're reading this)
"""

import os
import sys
import time
import threading
import traceback
import numpy as np

WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

CANVAS_W    = 640
CANVAS_H    = 360
BENCH_FRAMES = 50

# ─────────────────────────────────────────────────────────────────────────────
# WGSL shaders
# ─────────────────────────────────────────────────────────────────────────────

# Passthrough — identical logic to a plain texture copy
WGSL_PASSTHROUGH = """
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var samp: sampler;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    // Full-screen triangle (covers NDC -1..1 with 3 vertices)
    var positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(2.0, 1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(positions[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    return textureSample(tex, samp, in.uv);
}
"""

# Transform — direct port of src/modules/gpu/shaders/transform.frag
# Hardcoded 200% scale (the bug reproduction case). Uniforms would replace
# the constants in production.
WGSL_TRANSFORM = """
@group(0) @binding(0) var tex: texture_2d<f32>;
@group(0) @binding(1) var samp: sampler;

struct VertOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) uv: vec2<f32>,
};

@vertex
fn vs_main(@builtin(vertex_index) vi: u32) -> VertOut {
    var positions = array<vec2<f32>, 3>(
        vec2<f32>(-1.0, -1.0),
        vec2<f32>( 3.0, -1.0),
        vec2<f32>(-1.0,  3.0),
    );
    var uvs = array<vec2<f32>, 3>(
        vec2<f32>(0.0, 1.0),
        vec2<f32>(2.0, 1.0),
        vec2<f32>(0.0, -1.0),
    );
    var out: VertOut;
    out.pos = vec4<f32>(positions[vi], 0.0, 1.0);
    out.uv  = uvs[vi];
    return out;
}

@fragment
fn fs_main(in: VertOut) -> @location(0) vec4<f32> {
    // === Ported from transform.frag (GLSL → WGSL) ===
    let anchor    = vec2<f32>(0.5, 0.5);
    let scale     = vec2<f32>(2.0, 2.0);   // 200% — the failing test case
    let translate = vec2<f32>(0.0, 0.0);
    let rotation  = 0.0f;

    var uv = in.uv - anchor;

    uv = uv / max(scale, vec2<f32>(0.001, 0.001));

    let c = cos(-rotation);
    let s = sin(-rotation);
    uv = vec2<f32>(c * uv.x - s * uv.y,
                   s * uv.x + c * uv.y);

    uv = uv + anchor - vec2<f32>(translate.x, -translate.y);

    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 1.0);
    }

    return textureSample(tex, samp, uv);
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Core GPU helper — builds a render pipeline + runs one frame
# ─────────────────────────────────────────────────────────────────────────────

def _make_device():
    import wgpu
    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    device  = adapter.request_device_sync()
    return adapter, device


def _render_frame(device, wgsl_src: str, input_rgba: np.ndarray) -> np.ndarray:
    """
    Upload input_rgba (H, W, 4 uint8) to a GPU texture, run wgsl_src shader,
    read back result as (H, W, 4 uint8) numpy array.
    Uses D3D12 staging buffer readback — no OpenGL, no WGL.
    """
    import wgpu

    h, w = input_rgba.shape[:2]

    # ── upload input texture ──────────────────────────────────────────────────
    tex_in = device.create_texture(
        size=(w, h, 1),
        format=wgpu.TextureFormat.rgba8unorm,
        usage=wgpu.TextureUsage.TEXTURE_BINDING | wgpu.TextureUsage.COPY_DST,
    )
    device.queue.write_texture(
        {"texture": tex_in, "mip_level": 0, "origin": (0, 0, 0)},
        input_rgba.tobytes(),
        {"bytes_per_row": w * 4, "rows_per_image": h},
        (w, h, 1),
    )

    sampler = device.create_sampler(
        min_filter="linear",
        mag_filter="linear",
    )

    # ── output render texture ─────────────────────────────────────────────────
    tex_out = device.create_texture(
        size=(w, h, 1),
        format=wgpu.TextureFormat.rgba8unorm,
        usage=wgpu.TextureUsage.RENDER_ATTACHMENT | wgpu.TextureUsage.COPY_SRC,
    )

    # ── shader + pipeline ─────────────────────────────────────────────────────
    shader_mod = device.create_shader_module(code=wgsl_src)

    bind_group_layout = device.create_bind_group_layout(entries=[
        {"binding": 0,
         "visibility": wgpu.ShaderStage.FRAGMENT,
         "texture": {"sample_type": "float", "view_dimension": "2d"}},
        {"binding": 1,
         "visibility": wgpu.ShaderStage.FRAGMENT,
         "sampler": {"type": "filtering"}},
    ])

    pipeline_layout = device.create_pipeline_layout(
        bind_group_layouts=[bind_group_layout]
    )

    pipeline = device.create_render_pipeline(
        layout=pipeline_layout,
        vertex={
            "module": shader_mod,
            "entry_point": "vs_main",
        },
        fragment={
            "module": shader_mod,
            "entry_point": "fs_main",
            "targets": [{"format": wgpu.TextureFormat.rgba8unorm}],
        },
        primitive={"topology": "triangle-list"},
        depth_stencil=None,
        multisample=None,
    )

    bind_group = device.create_bind_group(
        layout=bind_group_layout,
        entries=[
            {"binding": 0, "resource": tex_in.create_view()},
            {"binding": 1, "resource": sampler},
        ],
    )

    # ── render ────────────────────────────────────────────────────────────────
    encoder = device.create_command_encoder()
    render_pass = encoder.begin_render_pass(
        color_attachments=[{
            "view": tex_out.create_view(),
            "resolve_target": None,
            "clear_value": (0, 0, 0, 1),
            "load_op": "clear",
            "store_op": "store",
        }]
    )
    render_pass.set_pipeline(pipeline)
    render_pass.set_bind_group(0, bind_group)
    render_pass.draw(3)
    render_pass.end()
    device.queue.submit([encoder.finish()])

    # ── readback via D3D12 staging buffer (no glReadPixels, no WGL) ──────────
    bytes_per_row = (w * 4 + 255) & ~255   # D3D12 256-byte row alignment
    staging = device.create_buffer(
        size=bytes_per_row * h,
        usage=wgpu.BufferUsage.COPY_DST | wgpu.BufferUsage.MAP_READ,
    )
    enc2 = device.create_command_encoder()
    enc2.copy_texture_to_buffer(
        {"texture": tex_out, "mip_level": 0, "origin": (0, 0, 0)},
        {"buffer": staging, "bytes_per_row": bytes_per_row, "rows_per_image": h},
        (w, h, 1),
    )
    device.queue.submit([enc2.finish()])

    staging.map_sync(wgpu.MapMode.READ)
    raw = staging.read_mapped(0, bytes_per_row * h)
    # Strip row padding (D3D12 requires 256-byte aligned rows)
    rows = [raw[r * bytes_per_row: r * bytes_per_row + w * 4] for r in range(h)]
    out = np.frombuffer(b"".join(rows), dtype=np.uint8).reshape(h, w, 4)
    staging.unmap()
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hr(label):
    print(f"\n{'─'*60}\n  {label}\n{'─'*60}")

def _ok(msg):  print(f"  ✓  {msg}")
def _fail(msg): print(f"  ✗  {msg}")
def _info(msg): print(f"     {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Adapter / D3D12
# ─────────────────────────────────────────────────────────────────────────────

def test_adapter():
    _hr("TEST 1 — D3D12 adapter")
    import wgpu
    _ok(f"wgpu version: {wgpu.__version__}")

    adapter = wgpu.gpu.request_adapter_sync(power_preference="high-performance")
    info = adapter.info
    _ok(f"Adapter:      {info['device']}  (vendor: {info['vendor']})")
    _ok(f"Backend:      {info['backend_type']}")
    _ok(f"Adapter type: {info['adapter_type']}")

    backend = info['backend_type'].lower()
    if "d3d12" in backend or "vulkan" in backend:
        _ok("Non-OpenGL backend confirmed — AMD WGL bug does not apply here")
    elif "opengl" in backend:
        _fail("OpenGL backend selected — WGL issues may still occur")
        _info("Force D3D12: set env var WGPU_BACKEND=dx12")
    else:
        _info(f"Backend '{backend}' — verify this avoids WGL on Windows")

    return adapter, info


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Passthrough shader + numpy round-trip
# ─────────────────────────────────────────────────────────────────────────────

def test_passthrough(device):
    _hr("TEST 2 — Passthrough WGSL + numpy round-trip")

    # Red left half, green right half
    frame = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    frame[:, :CANVAS_W//2, 0] = 200   # red left
    frame[:, CANVAS_W//2:, 1] = 200   # green right
    frame[:, :, 3] = 255

    out = _render_frame(device, WGSL_PASSTHROUGH, frame)

    r_in  = frame[:, :CANVAS_W//2, 0].mean()
    r_out = out[:, :CANVAS_W//2, 0].mean()
    g_in  = frame[:, CANVAS_W//2:, 1].mean()
    g_out = out[:, CANVAS_W//2:, 1].mean()

    _ok(f"Output shape: {out.shape}  dtype: {out.dtype}")
    _info(f"Red   (left)  in={r_in:.0f}  out={r_out:.0f}")
    _info(f"Green (right) in={g_in:.0f}  out={g_out:.0f}")

    if abs(r_in - r_out) > 5 or abs(g_in - g_out) > 5:
        _fail("Pixel values differ too much — shader or readback broken")
        return False

    _ok("Pixel values match — passthrough correct")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Transform shader at 200% scale
# ─────────────────────────────────────────────────────────────────────────────

def test_transform(device):
    _hr("TEST 3 — Transform WGSL at 200% scale (bug reproduction)")

    # White cross on black background — easy to verify zoom
    frame = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    frame[CANVAS_H//2-5:CANVAS_H//2+5, :, :3] = 255   # horizontal bar
    frame[:, CANVAS_W//2-5:CANVAS_W//2+5, :3] = 255   # vertical bar
    frame[:, :, 3] = 255

    out = _render_frame(device, WGSL_TRANSFORM, frame)

    _ok(f"Output shape: {out.shape}  dtype: {out.dtype}")

    # At 200% scale the zoomed-in cross should fill more of the output.
    # Centre pixel should still be white (cross centre visible at any scale).
    cx, cy = CANVAS_W // 2, CANVAS_H // 2
    centre_val = out[cy, cx, 0]
    _info(f"Centre pixel R: {centre_val}  (expect ~255)")

    # Corner pixels should be black (black area zoomed in, no wrap)
    corner_val = out[0, 0, 0]
    _info(f"Corner pixel R: {corner_val}  (expect 0 — black outside)")

    if centre_val < 200:
        _fail("Centre not white after 200% zoom — WGSL transform logic error")
        return False
    if corner_val > 50:
        _fail("Corner not black — out-of-bounds handling broken")
        return False

    _ok("Transform shader correct at 200% scale")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Benchmark
# ─────────────────────────────────────────────────────────────────────────────

def test_benchmark(device):
    _hr(f"TEST 4 — Latency benchmark ({BENCH_FRAMES} frames, transform shader)")

    frame = np.random.randint(0, 255, (CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
    frame[:, :, 3] = 255

    latencies = []
    t_total = time.perf_counter()

    for _ in range(BENCH_FRAMES):
        t0 = time.perf_counter()
        _render_frame(device, WGSL_TRANSFORM, frame)
        latencies.append((time.perf_counter() - t0) * 1000)

    total_s = time.perf_counter() - t_total

    arr = sorted(latencies)
    avg = sum(arr) / len(arr)
    p50 = arr[len(arr) // 2]
    p95 = arr[int(len(arr) * 0.95)]
    fps = BENCH_FRAMES / total_s

    _ok(f"FPS:           {fps:.1f}")
    _ok(f"Latency (ms):  avg={avg:.1f}  p50={p50:.1f}  p95={p95:.1f}")
    _info(f"Reference:     ModernGL SSBO on AMD ~26ms avg")

    if avg < 26:
        _ok("Faster than current ModernGL SSBO path")
    else:
        _info("Slower or equal — may improve once pipeline is reused across frames")

    return True


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Thread safety (the exact scenario that kills ModernGL on AMD)
# ─────────────────────────────────────────────────────────────────────────────

def test_thread_safety(device):
    _hr("TEST 5 — Render from non-main thread (AMD WGL bug scenario)")

    results = []
    errors  = []

    def render_worker():
        try:
            frame = np.zeros((CANVAS_H, CANVAS_W, 4), dtype=np.uint8)
            frame[:, :, 3] = 255
            out = _render_frame(device, WGSL_TRANSFORM, frame)
            results.append(out.shape)
        except Exception as exc:
            errors.append(str(exc))

    threads = [threading.Thread(target=render_worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    if errors:
        _fail(f"Thread render failed: {errors[0]}")
        return False

    _ok(f"{len(results)}/3 threads completed successfully")
    _ok("No WGL context errors — D3D12 is thread-safe by design")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print()
    print("=" * 60)
    print("  wgpu-py D3D12 + WGSL POC  —  Py_artnet")
    print("=" * 60)

    results = {}

    try:
        adapter, info = test_adapter()
        results["1_adapter"] = True
    except Exception as exc:
        _fail(f"Adapter test failed: {exc}")
        traceback.print_exc()
        sys.exit(1)

    try:
        _, device = _make_device()
    except Exception as exc:
        _fail(f"Could not create device: {exc}")
        traceback.print_exc()
        sys.exit(1)

    for name, fn in [
        ("2_passthrough",  lambda: test_passthrough(device)),
        ("3_transform",    lambda: test_transform(device)),
        ("4_benchmark",    lambda: test_benchmark(device)),
        ("5_thread_safety",lambda: test_thread_safety(device)),
    ]:
        try:
            results[name] = fn()
        except Exception as exc:
            _fail(f"{name} raised: {exc}")
            traceback.print_exc()
            results[name] = False

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
        print("  ✅  All tests passed — wgpu D3D12 is viable on this machine.")
        print("      AMD WGL issues are gone. Next: port shaders GLSL → WGSL.")
    else:
        print("  ❌  One or more tests failed — check output above.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception:
        traceback.print_exc()
        sys.exit(2)
