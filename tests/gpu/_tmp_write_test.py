"""write the uint8 upload test to its final path"""
import os

target = os.path.join(os.path.dirname(__file__), 'test_uint8_upload.py')

src = r'''"""
Test: uint8 staging texture -> float32 FBO via passthrough blit shader.

Tests GL_RGB8 (3-component) and GL_RGBA8 (4-component) staging separately.
AMD Bug #1 may be specific to GL_RGB8 - RGBA8 is better-aligned (4 bytes/pixel,
no GL_UNPACK_ALIGNMENT issues) and more widely supported.

If RGBA8 passes but RGB8 fails, we can switch GPUFrame to use RGBA8 staging
and cut DMA from ~24 MB (float32) to ~8 MB (RGBA8) - ~3x reduction.

Run from project root:
    python tests/gpu/test_uint8_upload.py
"""
import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

PASS = 0
FAIL = 0


class TexWrapper:
    """Minimal duck-type wrapper so a raw moderngl.Texture works with Renderer."""
    def __init__(self, texture):
        self.texture = texture


def check(condition, name, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))
        FAIL += 1


# ---------------------------------------------------------------------------
# NOTE: Renderer vertex shader outputs 'v_uv' (not 'vUV') - must match here.
# ---------------------------------------------------------------------------

# Passthrough blit: samples RGB/RGBA staging tex, writes RGB to float32 FBO.
PASSTHROUGH_FRAG = """
#version 330 core
uniform sampler2D uStaging;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    fragColor = vec4(texture(uStaging, v_uv).rgb, 1.0);
}
"""

# Arithmetic shader: multiply by 0.5 - tests that float32 FBO arithmetic works.
MULTIPLY_FRAG = """
#version 330 core
uniform sampler2D uTex;
uniform float uFactor;
in vec2 v_uv;
out vec4 fragColor;
void main() {
    fragColor = texture(uTex, v_uv) * uFactor;
}
"""


def _make_test_pattern(H, W):
    src = np.zeros((H, W, 3), dtype=np.uint8)
    src[:H//2, :W//2] = [200,  50,  50]   # top-left: red-ish
    src[:H//2, W//2:] = [ 50, 200,  50]   # top-right: green-ish
    src[H//2:, :W//2] = [ 50,  50, 200]   # bottom-left: blue-ish
    src[H//2:, W//2:] = [180, 180,  30]   # bottom-right: yellow-ish
    return src


def _run_passthrough_test(label, upload_fn):
    """
    Generic passthrough roundtrip: upload uint8 via staging tex -> float32 FBO -> download.
    upload_fn(ctx, W, H, src_bgr) -> staging moderngl.Texture (caller must release)
    Returns True if passed.
    """
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame
    from modules.gpu.renderer import Renderer

    ctx = get_context()
    renderer = Renderer(ctx)

    H, W = 64, 64
    src = _make_test_pattern(H, W)  # BGR

    staging = upload_fn(ctx, W, H, src)
    dst = GPUFrame(ctx, W, H, 3)

    renderer.render(
        frag_source=PASSTHROUGH_FRAG,
        target_fbo=dst.fbo,
        uniforms={},
        textures={'uStaging': (0, TexWrapper(staging))},
    )

    result = dst.download()  # BGR uint8

    diff = np.abs(src.astype(np.int32) - result.astype(np.int32))
    max_diff = int(diff.max())
    mean_diff = float(diff.mean())
    passed = max_diff <= 1
    check(passed, f"{label} pixel values (max_diff={max_diff}, mean={mean_diff:.3f})",
          f"max diff {max_diff} > 1 - all zeros? AMD bug?")
    staging.release()
    dst.release()
    return passed


def test_rgb8_passthrough_roundtrip():
    """GL_RGB8 (3 components) - known to fail on AMD (Bug #1)."""
    print("\n=== 1a. GL_RGB8 staging -> float32 FBO: passthrough roundtrip ===")
    def upload(ctx, W, H, src_bgr):
        t = ctx.texture((W, H), 3, dtype='u1')
        t.filter = ctx.LINEAR, ctx.LINEAR
        t.write(np.ascontiguousarray(src_bgr[:, :, ::-1]))  # BGR->RGB
        return t
    _run_passthrough_test("GL_RGB8", upload)


def test_rgba8_passthrough_roundtrip():
    """GL_RGBA8 (4 components) - 4-byte/pixel alignment, no alignment edge cases."""
    print("\n=== 1b. GL_RGBA8 staging -> float32 FBO: passthrough roundtrip ===")
    def upload(ctx, W, H, src_bgr):
        H2, W2 = src_bgr.shape[:2]
        t = ctx.texture((W2, H2), 4, dtype='u1')
        t.filter = ctx.LINEAR, ctx.LINEAR
        rgb = src_bgr[:, :, ::-1]  # BGR->RGB
        rgba = np.dstack([rgb, np.full((H2, W2), 255, dtype=np.uint8)])
        t.write(np.ascontiguousarray(rgba))
        return t
    _run_passthrough_test("GL_RGBA8", upload)


def test_uint8_then_arithmetic():
    """Staging -> float32 FBO -> arithmetic shader (x0.5, expect ~100). Both RGB8 + RGBA8."""
    print("\n=== 2. uint8 staging -> float32 -> arithmetic shader ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame
    from modules.gpu.renderer import Renderer

    ctx = get_context()
    renderer = Renderer(ctx)

    H, W = 16, 16
    src = np.full((H, W, 3), 200, dtype=np.uint8)

    for label, components, make_data in [
        ("GL_RGB8 ", 3, lambda s: np.ascontiguousarray(s[:, :, ::-1])),
        ("GL_RGBA8", 4, lambda s: np.ascontiguousarray(
            np.dstack([s[:, :, ::-1], np.full(s.shape[:2], 255, dtype=np.uint8)]))),
    ]:
        staging = ctx.texture((W, H), components, dtype='u1')
        staging.filter = ctx.LINEAR, ctx.LINEAR
        staging.write(make_data(src))

        mid = GPUFrame(ctx, W, H, 3)
        renderer.render(frag_source=PASSTHROUGH_FRAG, target_fbo=mid.fbo,
                        uniforms={}, textures={'uStaging': (0, TexWrapper(staging))})

        dst = GPUFrame(ctx, W, H, 3)
        renderer.render(frag_source=MULTIPLY_FRAG, target_fbo=dst.fbo,
                        uniforms={'uFactor': 0.5}, textures={'uTex': (0, mid)})

        result = dst.download()
        max_diff = int(np.abs(result.astype(np.int32) - 100).max())
        check(max_diff <= 1,
              f"{label}: arithmetic correct (expected ~100, max_diff={max_diff})",
              f"max diff {max_diff} - AMD bug on arithmetic path?")
        staging.release(); mid.release(); dst.release()


def test_timing_comparison():
    """Timing: current float32 path vs GL_RGB8 staging vs GL_RGBA8 staging."""
    print("\n=== 3. Timing: float32 vs RGB8 vs RGBA8 staging (1080p) ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame
    from modules.gpu.renderer import Renderer

    ctx = get_context()
    renderer = Renderer(ctx)

    H, W = 1080, 1920
    src_uint8 = np.random.randint(0, 256, (H, W, 3), dtype=np.uint8)
    float_buf = np.empty((H, W, 3), dtype=np.float32)
    rgb_uint8  = np.ascontiguousarray(src_uint8[:, :, ::-1])
    rgba_uint8 = np.ascontiguousarray(
        np.dstack([src_uint8[:, :, ::-1], np.full((H, W), 255, dtype=np.uint8)]))

    gpu_f        = GPUFrame(ctx, W, H, 3)
    staging_rgb  = ctx.texture((W, H), 3, dtype='u1')
    staging_rgba = ctx.texture((W, H), 4, dtype='u1')
    mid          = GPUFrame(ctx, W, H, 3)
    for s in (staging_rgb, staging_rgba):
        s.filter = ctx.LINEAR, ctx.LINEAR

    def blit(stg):
        renderer.render(frag_source=PASSTHROUGH_FRAG, target_fbo=mid.fbo,
                        uniforms={}, textures={'uStaging': (0, TexWrapper(stg))})

    # Warm up
    gpu_f.upload(src_uint8);          gpu_f.texture.read()
    staging_rgb.write(rgb_uint8);     blit(staging_rgb);  mid.texture.read()
    staging_rgba.write(rgba_uint8);   blit(staging_rgba); mid.texture.read()

    N = 5
    def bench(fn):
        times = []
        for _ in range(N):
            t0 = time.perf_counter(); fn(); times.append((time.perf_counter()-t0)*1000)
        return times

    tc = bench(lambda: (
        np.multiply(src_uint8[:, :, ::-1], 1.0/255.0, out=float_buf),
        gpu_f.texture.write(float_buf),
        gpu_f.texture.read(),
    ))
    tr = bench(lambda: (staging_rgb.write(rgb_uint8),   blit(staging_rgb),  mid.texture.read()))
    ta = bench(lambda: (staging_rgba.write(rgba_uint8), blit(staging_rgba), mid.texture.read()))

    mc, mr, ma = np.mean(tc), np.mean(tr), np.mean(ta)
    print(f"  Current  (CPU f32 + 24MB write + read): {mc:.1f} ms  {[f'{t:.1f}' for t in tc]}")
    print(f"  GL_RGB8  ( 6MB uint8 + blit   + read): {mr:.1f} ms  {[f'{t:.1f}' for t in tr]}")
    print(f"  GL_RGBA8 ( 8MB uint8 + blit   + read): {ma:.1f} ms  {[f'{t:.1f}' for t in ta]}")
    print(f"  RGB8  delta: {mc-mr:+.1f} ms  ({'faster' if mr < mc else 'slower'})")
    print(f"  RGBA8 delta: {mc-ma:+.1f} ms  ({'faster' if ma < mc else 'slower'})")

    gpu_f.release(); staging_rgb.release(); staging_rgba.release(); mid.release()


if __name__ == '__main__':
    test_rgb8_passthrough_roundtrip()
    test_rgba8_passthrough_roundtrip()
    test_uint8_then_arithmetic()
    test_timing_comparison()

    print(f"\n{'='*50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("OK: uint8 staging viable on this driver")
    else:
        print("See [PASS]/[FAIL] above for GL_RGB8 vs GL_RGBA8 breakdown")
        print("If GL_RGBA8 passes: switch GPUFrame to RGBA8 staging (8MB vs 24MB)")
        print("If both fail: AMD bug present - keep float32 upload path")
    sys.exit(0 if FAIL == 0 else 1)
'''

with open(target, 'w', encoding='utf-8') as f:
    f.write(src)
print(f"Written {len(src.splitlines())} lines to {target}")
