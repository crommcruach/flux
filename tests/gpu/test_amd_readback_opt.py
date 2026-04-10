"""
AMD Readback Optimization Test
================================
Tests two potential optimizations for the 43ms texture.read() bottleneck:

  Strategy 1 — Intermediate u1 blit:
    Render float32 texture → GL_RGBA8 (u1) FBO via passthrough shader,
    then read the u1 FBO.  Tests whether reading u1-from-u1 avoids the
    driver's broken float→u8 glReadPixels path AND whether it's faster.

  Strategy 2 — OpenGL version check:
    Reports the actual OGL version the driver hands us and lists
    extensions relevant to persistent mapped buffers.

Run with:
    python -m pytest tests/gpu/test_amd_readback_opt.py -v -s
or standalone:
    python tests/gpu/test_amd_readback_opt.py
"""

import sys
import time
import numpy as np

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_frame(w, h):
    """Return a BGR uint8 test frame with a gradient so we can verify values."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :, 2] = np.linspace(0, 255, w, dtype=np.uint8)   # R gradient
    frame[:, :, 1] = np.linspace(0, 255, h, dtype=np.uint8).reshape(h, 1)  # G gradient
    frame[:, :, 0] = 128  # B constant
    return frame


def _timeit(fn, rounds=10, warmup=3):
    """Run fn() warmup + rounds times, return (mean_ms, min_ms, max_ms)."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(rounds):
        t0 = time.perf_counter()
        fn()
        times.append((time.perf_counter() - t0) * 1000)
    return np.mean(times), np.min(times), np.max(times)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_opengl_version_and_extensions():
    """Report the actual OpenGL version and relevant extensions."""
    import moderngl
    ctx = moderngl.create_standalone_context()

    ver = ctx.version_code
    major = ver // 100
    minor = (ver % 100) // 10
    print(f"\n[OGL version] {major}.{minor}  (version_code={ver})")
    print(f"[OGL renderer] {ctx.info.get('GL_RENDERER', '?')}")
    print(f"[OGL vendor]   {ctx.info.get('GL_VENDOR', '?')}")

    # Extensions relevant to persistent mapped buffers and fast readback
    want = [
        'GL_ARB_buffer_storage',      # persistent mapped PBOs (OGL 4.4+)
        'GL_ARB_direct_state_access', # OGL 4.5 — DSA for buffer ops
        'GL_EXT_buffer_storage',      # ES variant
        'GL_ARB_sync',                # fence sync for async transfers
        'GL_ARB_pixel_buffer_object', # standard PBO
        'GL_ARB_map_buffer_range',    # glMapBufferRange
    ]
    exts = ctx.extensions
    for name in want:
        status = "✅" if name in exts else "❌"
        print(f"  {status} {name}")

    assert ver >= 330, f"Expected at least OGL 3.3, got {ver}"
    ctx.release()


def test_strategy1_u1_blit_timing(width=1920, height=1080):
    """
    Strategy 1: Render float32 texture → u1 FBO (blit pass), then read u1 FBO.

    Compares:
      A) Baseline:  upload → float32 texture.read() (current path)
      B) Blit path: upload → blit to u1 FBO → u1 fbo.read()

    Checks:
      - Whether fbo.read() on a u1 FBO returns non-zero data (Bug 2 bypass)
      - Whether pixel values are within ±2 of original (correct conversion)
      - Timing vs baseline
    """
    import moderngl
    ctx = moderngl.create_standalone_context()

    # ── Passthrough vertex + fragment shaders ────────────────────────────────
    VERT = """
    #version 330
    in vec2 in_position;
    in vec2 in_uv;
    out vec2 v_uv;
    void main() {
        gl_Position = vec4(in_position, 0.0, 1.0);
        v_uv = in_uv;
    }
    """
    FRAG = """
    #version 330
    in vec2 v_uv;
    out vec4 fragColor;
    uniform sampler2D tex;
    void main() {
        fragColor = texture(tex, v_uv);
    }
    """

    prog = ctx.program(vertex_shader=VERT, fragment_shader=FRAG)

    verts = np.array([
        -1, -1,  0, 0,
         1, -1,  1, 0,
         1,  1,  1, 1,
        -1,  1,  0, 1,
    ], dtype=np.float32)
    idx = np.array([0, 1, 2, 0, 2, 3], dtype=np.int32)
    vbo = ctx.buffer(verts.tobytes())
    ibo = ctx.buffer(idx.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, '2f 2f', 'in_position', 'in_uv')],
                           index_buffer=ibo)

    # ── Float32 source texture + FBO (current path) ──────────────────────────
    f32_tex = ctx.texture((width, height), 3, dtype='f4')
    f32_fbo = ctx.framebuffer(color_attachments=[f32_tex])

    # ── u1 destination texture + FBO (blit target) ───────────────────────────
    u1_tex = ctx.texture((width, height), 3, dtype='u1')
    u1_fbo = ctx.framebuffer(color_attachments=[u1_tex])

    # ── Upload test frame into float32 texture ───────────────────────────────
    frame = _make_test_frame(width, height)
    upload_buf = np.empty((height, width, 3), dtype=np.float32)
    np.multiply(frame[:, :, ::-1], 1.0 / 255.0, out=upload_buf)
    f32_tex.write(upload_buf.tobytes())

    prog['tex'].value = 0

    # ── A) Baseline: texture.read() on float32 (current path) ────────────────
    def baseline_read():
        raw = f32_tex.read()
        arr = np.frombuffer(raw, dtype=np.float32).reshape(height, width, 3)
        return (arr * 255).astype(np.uint8)

    mean_a, min_a, max_a = _timeit(baseline_read)
    print(f"\n[Strategy 1] Baseline  texture.read() float32: "
          f"mean={mean_a:.1f}ms  min={min_a:.1f}ms  max={max_a:.1f}ms")

    # ── B) Blit pass: render float32 → u1 FBO, then fbo.read() ───────────────
    def blit_and_read():
        # Blit pass: float32 → u1 FBO
        f32_tex.use(location=0)
        u1_fbo.use()
        ctx.clear()
        vao.render()

        # Read u1 FBO (no implicit type conversion — u1 reads u1)
        raw = u1_fbo.read(components=3)
        return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)

    # First check correctness
    result = blit_and_read()
    if np.all(result == 0):
        print("[Strategy 1] ❌ fbo.read() on u1 FBO still returns all zeros — Bug 2 NOT bypassed by this strategy")
        ctx.release()
        return

    # Check pixel accuracy vs original (allow ±2 for float rounding)
    # GL origin is bottom-left; flip Y to compare to numpy frame
    result_bgr = result[::-1, :, ::-1]   # flip Y + RGB→BGR
    diff = np.abs(result_bgr.astype(np.int32) - frame.astype(np.int32))
    max_diff = int(diff.max())
    mean_diff = float(diff.mean())
    print(f"[Strategy 1] Pixel diff vs original: max={max_diff}  mean={mean_diff:.2f}")

    if max_diff <= 2:
        print("[Strategy 1] ✅ Pixel values match — conversion is correct")
    else:
        print(f"[Strategy 1] ⚠️  Pixel diff {max_diff} > 2 — check conversion")

    mean_b, min_b, max_b = _timeit(blit_and_read)
    speedup = mean_a / mean_b if mean_b > 0 else 0
    print(f"[Strategy 1] Blit+read u1 FBO:       "
          f"mean={mean_b:.1f}ms  min={min_b:.1f}ms  max={max_b:.1f}ms  "
          f"({speedup:.1f}× {'faster' if speedup > 1 else 'SLOWER'})")

    ctx.release()


def test_strategy2_higher_ogl_version():
    """
    Strategy 2: Try to get a higher OGL context and check for persistent
    mapped buffer support.  ModernGL's create_standalone_context() picks the
    highest available version by default; this test verifies that and checks
    whether GL_ARB_buffer_storage is actually exposed.
    """
    import moderngl

    # Try requesting 4.6 explicitly
    for req in [460, 450, 440, 430, 420, 410, 400, 330]:
        try:
            ctx = moderngl.create_standalone_context(require=req)
            ver = ctx.version_code
            has_buf_storage = 'GL_ARB_buffer_storage' in ctx.extensions
            print(f"\n[Strategy 2] Requested {req//100}.{(req%100)//10}: "
                  f"got {ver//100}.{(ver%100)//10}  "
                  f"GL_ARB_buffer_storage={'✅' if has_buf_storage else '❌'}")
            ctx.release()
            break
        except Exception as e:
            print(f"[Strategy 2] Requested {req//100}.{(req%100)//10}: FAILED ({e})")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("=" * 60)
    print("AMD Readback Optimization Test")
    print("=" * 60)

    print("\n--- OpenGL version and extensions ---")
    test_opengl_version_and_extensions()

    print("\n--- Strategy 2: Higher OGL version ---")
    test_strategy2_higher_ogl_version()

    print("\n--- Strategy 1: u1 blit path (1080p) ---")
    test_strategy1_u1_blit_timing(1920, 1080)

    print("\n--- Strategy 1: u1 blit path (720p) ---")
    test_strategy1_u1_blit_timing(1280, 720)

    print("\nDone.")
