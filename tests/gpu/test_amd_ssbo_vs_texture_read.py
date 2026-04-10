"""
AMD Readback: glGetBufferSubData (SSBO) vs glGetTexImage (texture.read())
=========================================================================
Tests whether routing a full 1080p frame through a compute shader into an
SSBO and then reading it with glGetBufferSubData avoids the ~50ms AMD
pipeline drain stall that glGetTexImage (texture.read()) triggers.

Hypothesis:
  - glGetTexImage / glReadPixels trigger a full GPU pipeline drain → ~50ms
  - glGetBufferSubData on a compute-shader-written SSBO may NOT trigger the
    same drain, because it is a buffer-object read, not a pixel-pack readback

This was proven stall-free for small ArtNet SSBOs (512 LEDs × 4 bytes = 2KB).
This test measures whether the stall-free property holds at full-frame scale:
  640×360×3 = 691 KB  (preview resolution)
  1920×1080×3 = 6.2 MB (full render resolution)

Compute shader: copies texture pixels into a packed-uint8 SSBO.
The shader reads float32 texture, packs to uint8, writes to SSBO.

Run:
    python tests/gpu/test_amd_ssbo_vs_texture_read.py
"""

import sys
import time
import numpy as np

try:
    import OpenGL.GL as gl
    PYOPENGL = True
except ImportError:
    PYOPENGL = False
    print("PyOpenGL not found — install with: pip install PyOpenGL")
    sys.exit(1)

import moderngl

# ── Compute shader: downsample or copy texture → packed RGB SSBO ─────────────
# Reads each pixel of inputTexture at the matching UV and packs to 3 bytes.
# Output SSBO: width * height * 3 bytes (packed RGB uint8).
COPY_COMP_SRC = """
#version 430
layout(local_size_x = 16, local_size_y = 16) in;

uniform sampler2D inputTexture;
uniform int outWidth;
uniform int outHeight;

layout(std430, binding = 0) writeonly buffer PixelBuffer {
    uint pixels[];   // packed: pixel[i] = R | (G<<8) | (B<<16), one uint per pixel
};

void main() {
    int x = int(gl_GlobalInvocationID.x);
    int y = int(gl_GlobalInvocationID.y);
    if (x >= outWidth || y >= outHeight) return;

    vec2 uv = (vec2(x, y) + 0.5) / vec2(float(outWidth), float(outHeight));
    vec4 c = texture(inputTexture, uv);

    // float32 [0,1] → uint8 [0,255], pack RGB into one uint
    uint r = uint(clamp(c.r * 255.0, 0.0, 255.0));
    uint g = uint(clamp(c.g * 255.0, 0.0, 255.0));
    uint b = uint(clamp(c.b * 255.0, 0.0, 255.0));

    int idx = y * outWidth + x;
    pixels[idx] = r | (g << 8) | (b << 16);
}
"""


def _make_test_frame(w, h):
    frame = np.zeros((h, w, 3), dtype=np.float32)
    frame[:, :, 0] = np.linspace(0, 1, w, dtype=np.float32)
    frame[:, :, 1] = np.linspace(0, 1, h, dtype=np.float32).reshape(h, 1)
    frame[:, :, 2] = 0.5
    return frame


def _timeit(fn, rounds=15, warmup=5):
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return float(np.mean(times)), float(np.min(times)), float(np.max(times))


def run_test(tex_width=1920, tex_height=1080, preview_width=640, preview_height=360):

    ctx = moderngl.create_standalone_context(require=430)
    print(f"[ctx] OpenGL {ctx.version_code // 100}.{(ctx.version_code % 100) // 10}")

    # ── Upload test frame into float32 texture ───────────────────────────────
    frame_f32 = _make_test_frame(tex_width, tex_height)
    tex = ctx.texture((tex_width, tex_height), 3, dtype='f4')
    tex.write(frame_f32.tobytes())
    print(f"[tex] float32 texture {tex_width}×{tex_height} uploaded")

    # ── Compute program (OGL 4.3+) ───────────────────────────────────────────
    try:
        compute = ctx.compute_shader(COPY_COMP_SRC)
        print("[cs]  Compute shader compiled ✅")
    except Exception as e:
        print(f"[cs]  Compute shader FAILED: {e}")
        sys.exit(1)

    # ── SSBO at full resolution ──────────────────────────────────────────────
    full_ssbo_bytes = tex_width * tex_height * 4  # one uint per pixel
    full_ssbo = ctx.buffer(reserve=full_ssbo_bytes)
    print(f"[ssbo] Full-res SSBO: {full_ssbo_bytes / 1024 / 1024:.1f} MB")

    # ── SSBO at preview resolution ───────────────────────────────────────────
    prev_ssbo_bytes = preview_width * preview_height * 4
    prev_ssbo = ctx.buffer(reserve=prev_ssbo_bytes)
    print(f"[ssbo] Preview SSBO: {prev_ssbo_bytes / 1024:.0f} KB")

    # ── Helpers ──────────────────────────────────────────────────────────────
    def dispatch_and_read_ssbo(ssbo, out_w, out_h):
        compute['inputTexture'] = 0
        compute['outWidth'] = out_w
        compute['outHeight'] = out_h
        tex.use(location=0)
        ssbo.bind_to_storage_buffer(0)
        groups_x = (out_w + 15) // 16
        groups_y = (out_h + 15) // 16
        compute.run(group_x=groups_x, group_y=groups_y)
        ctx.finish()                         # wait for compute to complete
        raw = ssbo.read()                    # glGetBufferSubData
        return np.frombuffer(raw, dtype=np.uint32).reshape(out_h, out_w)

    def texture_read_full():
        raw = tex.read()                     # glGetTexImage → float32 bytes
        arr = np.frombuffer(raw, dtype=np.float32).reshape(tex_height, tex_width, 3)
        return np.clip(arr * 255.0, 0, 255).astype(np.uint8)

    def ssbo_read_full():
        return dispatch_and_read_ssbo(full_ssbo, tex_width, tex_height)

    def ssbo_read_preview():
        return dispatch_and_read_ssbo(prev_ssbo, preview_width, preview_height)

    # ── Correctness check ────────────────────────────────────────────────────
    print("\n[check] Verifying SSBO output matches texture.read()...")
    tex_result = texture_read_full()
    ssbo_result_raw = dispatch_and_read_ssbo(full_ssbo, tex_width, tex_height)
    # unpack SSBO: R = bits 0-7, G = bits 8-15, B = bits 16-23
    ssbo_r = (ssbo_result_raw & 0xFF).astype(np.uint8)
    ssbo_g = ((ssbo_result_raw >> 8) & 0xFF).astype(np.uint8)
    ssbo_b = ((ssbo_result_raw >> 16) & 0xFF).astype(np.uint8)
    ssbo_rgb = np.stack([ssbo_r, ssbo_g, ssbo_b], axis=2)

    diff = np.abs(tex_result.astype(np.int32) - ssbo_rgb.astype(np.int32))
    max_diff = int(diff.max())
    mean_diff = float(diff.mean())
    if max_diff <= 2:
        print(f"[check] ✅ SSBO matches texture (max_diff={max_diff}, mean={mean_diff:.3f})")
    else:
        print(f"[check] ❌ SSBO MISMATCH (max_diff={max_diff}, mean={mean_diff:.3f})")
        print("         AMD driver may have issues with this SSBO path too.")

    # ── Benchmarks ───────────────────────────────────────────────────────────
    print(f"\n[bench] Warming up and benchmarking (15 rounds, 5 warmup)...")
    print(f"        All times in milliseconds.\n")
    print(f"{'Method':<50} {'Mean':>8} {'Min':>8} {'Max':>8}")
    print("-" * 80)

    mean, mn, mx = _timeit(texture_read_full)
    print(f"{'texture.read() [glGetTexImage] 1080p full':<50} {mean:>7.1f}ms {mn:>7.1f}ms {mx:>7.1f}ms")

    mean, mn, mx = _timeit(ssbo_read_full)
    print(f"{'SSBO compute+read 1080p full (6.2MB buf)':<50} {mean:>7.1f}ms {mn:>7.1f}ms {mx:>7.1f}ms")

    mean, mn, mx = _timeit(ssbo_read_preview)
    print(f"{'SSBO compute+read 640x360 preview (691KB)':<50} {mean:>7.1f}ms {mn:>7.1f}ms {mx:>7.1f}ms")

    # ── Breakdown: compute dispatch only vs read only ─────────────────────────
    def dispatch_only():
        compute['inputTexture'] = 0
        compute['outWidth'] = tex_width
        compute['outHeight'] = tex_height
        tex.use(location=0)
        full_ssbo.bind_to_storage_buffer(0)
        groups_x = (tex_width + 15) // 16
        groups_y = (tex_height + 15) // 16
        compute.run(group_x=groups_x, group_y=groups_y)
        ctx.finish()

    def read_ssbo_only():
        full_ssbo.read()

    mean, mn, mx = _timeit(dispatch_only)
    print(f"{'  └ compute dispatch+finish only (no read)':<50} {mean:>7.1f}ms {mn:>7.1f}ms {mx:>7.1f}ms")

    # Pre-dispatch so SSBO has data before we time the read alone
    dispatch_only()
    mean, mn, mx = _timeit(read_ssbo_only)
    print(f"{'  └ glGetBufferSubData alone (6.2MB SSBO)':<50} {mean:>7.1f}ms {mn:>7.1f}ms {mx:>7.1f}ms")

    print("\n[result] Interpretation:")
    print("  If 'SSBO compute+read' is << 50ms → compute shader path bypass confirmed ✅")
    print("  If 'SSBO compute+read' is ~50ms   → AMD pipeline drain also hits SSBO reads ❌")
    print("  If 'glGetBufferSubData alone' is << 50ms but 'dispatch+finish' is ~50ms")
    print("    → drain is in ctx.finish(), not glGetBufferSubData — try async dispatch ❌")

    # ── Cleanup ──────────────────────────────────────────────────────────────
    tex.release()
    full_ssbo.release()
    prev_ssbo.release()
    ctx.release()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='AMD SSBO vs texture.read() readback benchmark')
    parser.add_argument('--width',  type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--preview-width',  type=int, default=640)
    parser.add_argument('--preview-height', type=int, default=360)
    args = parser.parse_args()
    run_test(args.width, args.height, args.preview_width, args.preview_height)
