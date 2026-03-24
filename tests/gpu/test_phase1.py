"""
GPU pipeline tests — Phase 1
Run from the project root:
    python tests/gpu/test_phase1.py

Tests:
  1. Context creation
  2. Upload/download roundtrip (BGR)
  3. Upload/download roundtrip (BGRA)
  4. Texture pool acquire/release
  5. Blend shader — normal mode (opacity 1.0)
  6. Blend shader — opacity 0.0 (base unchanged)
  7. Blend shader — opacity 0.5 (50% blend)
  8. Blend shader — add mode (clamp check)
  9. sample_pixels accuracy
 10. Pixel-pool warmup pre-allocates textures
"""
import sys
import os

# Add src/ to path so imports work from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import numpy as np

PASS = 0
FAIL = 0


def check(condition: bool, name: str, detail: str = ""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))
        FAIL += 1


# ---------------------------------------------------------------------------
# 1. Context
# ---------------------------------------------------------------------------
def test_context():
    print("\n=== 1. Context creation ===")
    from modules.gpu.context import get_context, destroy_context
    ctx = get_context()
    check(ctx is not None, "context not None")
    ctx2 = get_context()
    check(ctx is ctx2, "singleton — same object returned")


# ---------------------------------------------------------------------------
# 2 & 3. Upload/download roundtrip
# ---------------------------------------------------------------------------
def test_upload_download():
    print("\n=== 2 & 3. Upload/download roundtrip ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame

    ctx = get_context()
    H, W = 32, 64

    # BGR (3-channel)
    src = np.random.randint(0, 256, (H, W, 3), dtype=np.uint8)
    frame = GPUFrame(ctx, W, H, components=3)
    frame.upload(src)
    got = frame.download()
    check(got.shape == (H, W, 3), "shape matches (BGR)")
    check(np.array_equal(src, got), "pixel values preserved (BGR)",
          f"max diff = {np.abs(src.astype(int) - got.astype(int)).max()}")
    frame.release()

    # BGRA (4-channel)
    src4 = np.random.randint(0, 256, (H, W, 4), dtype=np.uint8)
    frame4 = GPUFrame(ctx, W, H, components=4)
    frame4.upload(src4)
    got4 = frame4.download()
    check(got4.shape == (H, W, 4), "shape matches (BGRA)")
    check(np.array_equal(src4, got4), "pixel values preserved (BGRA)",
          f"max diff = {np.abs(src4.astype(int) - got4.astype(int)).max()}")
    frame4.release()


# ---------------------------------------------------------------------------
# 4. Texture pool
# ---------------------------------------------------------------------------
def test_texture_pool():
    print("\n=== 4. Texture pool acquire/release ===")
    from modules.gpu.texture_pool import TexturePool
    from modules.gpu.context import get_context

    ctx = get_context()
    pool = TexturePool(ctx)

    f1 = pool.acquire(64, 32, 3)
    f2 = pool.acquire(64, 32, 3)
    check(f1 is not f2, "two acquires return different objects")

    pool.release(f1)
    f3 = pool.acquire(64, 32, 3)
    check(f3 is f1, "released frame is reused")

    pool.release(f2)
    pool.release(f3)
    pool.release_all()


# ---------------------------------------------------------------------------
# Blend helper: run one blend pass and return 1D pixels of the result
# ---------------------------------------------------------------------------
def _run_blend(base_color, overlay_color, opacity, mode_int,
               w=4, h=4):
    """Upload solid-color base and overlay, blend, download result."""
    from modules.gpu.context import get_context
    from modules.gpu.texture_pool import TexturePool
    from modules.gpu.renderer import Renderer, load_shader

    ctx = get_context()
    pool = TexturePool(ctx)
    renderer = Renderer(ctx)
    blend_src = load_shader('blend.frag')

    base_arr = np.full((h, w, 3), base_color, dtype=np.uint8)
    overlay_arr = np.full((h, w, 3), overlay_color, dtype=np.uint8)

    result_fbo = pool.acquire(w, h, 3)
    scratch_fbo = pool.acquire(w, h, 3)
    layer_tex = pool.acquire(w, h, 3)

    result_fbo.upload(base_arr)
    layer_tex.upload(overlay_arr)

    renderer.render(
        frag_source=blend_src,
        target_fbo=scratch_fbo.fbo,
        uniforms={'opacity': opacity, 'mode': mode_int},
        textures={'base': (0, result_fbo), 'overlay': (1, layer_tex)},
    )

    result = scratch_fbo.download()
    pool.release(result_fbo)
    pool.release(scratch_fbo)
    pool.release(layer_tex)
    renderer.release()
    return result


# ---------------------------------------------------------------------------
# 5. Blend — normal at opacity 1.0
# ---------------------------------------------------------------------------
def test_blend_normal_full():
    print("\n=== 5. Blend: normal mode opacity=1.0 ===")
    base = [50, 100, 150]
    overlay = [200, 80, 30]
    result = _run_blend(base, overlay, opacity=1.0, mode_int=0)
    pixel = result[0, 0]
    expected = np.array(overlay, dtype=np.uint8)
    check(np.allclose(pixel, expected, atol=2),
          f"output == overlay ({pixel} ≈ {expected})")


# ---------------------------------------------------------------------------
# 6. Blend — opacity 0.0 (base must be unchanged)
# ---------------------------------------------------------------------------
def test_blend_opacity_zero():
    print("\n=== 6. Blend: opacity=0.0 (base unchanged) ===")
    base = [100, 150, 200]
    overlay = [10, 20, 30]
    result = _run_blend(base, overlay, opacity=0.0, mode_int=0)
    pixel = result[0, 0]
    expected = np.array(base, dtype=np.uint8)
    check(np.allclose(pixel, expected, atol=2),
          f"output == base ({pixel} ≈ {expected})")


# ---------------------------------------------------------------------------
# 7. Blend — opacity 0.5 (50% mix)
# ---------------------------------------------------------------------------
def test_blend_opacity_half():
    print("\n=== 7. Blend: normal mode opacity=0.5 ===")
    base = [100, 100, 100]
    overlay = [200, 200, 200]
    result = _run_blend(base, overlay, opacity=0.5, mode_int=0)
    pixel = result[0, 0].astype(float)
    expected = 150.0
    check(abs(float(pixel[0]) - expected) <= 2,
          f"R channel ≈ 150 (got {pixel[0]:.1f})")


# ---------------------------------------------------------------------------
# 8. Blend — add mode clamp
# ---------------------------------------------------------------------------
def test_blend_add_clamp():
    print("\n=== 8. Blend: add mode clamp to 255 ===")
    base = [200, 200, 200]
    overlay = [100, 100, 100]
    result = _run_blend(base, overlay, opacity=1.0, mode_int=1)
    pixel = result[0, 0]
    check(all(pixel == 255), f"add clamp to 255 (got {pixel})")


# ---------------------------------------------------------------------------
# 9. sample_pixels accuracy
# ---------------------------------------------------------------------------
def test_sample_pixels():
    print("\n=== 9. sample_pixels ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame

    ctx = get_context()
    H, W = 16, 16
    # Gradient: pixel(y, x) = (x*10, y*10, 128)
    src = np.zeros((H, W, 3), dtype=np.uint8)
    for y in range(H):
        for x in range(W):
            src[y, x] = [x * 10, y * 10, 128]

    frame = GPUFrame(ctx, W, H, components=3)
    frame.upload(src)

    xs = np.array([0, 5, 10], dtype=int)
    ys = np.array([0, 3, 7], dtype=int)
    sampled = frame.sample_pixels(xs, ys)

    ok = True
    for i, (x, y) in enumerate(zip(xs, ys)):
        # sample_pixels returns RGB; src is BGR: src[y,x] = [B=x*10, G=y*10, R=128]
        # RGB means: R=128, G=y*10, B=x*10
        expected_rgb = np.array([128, y * 10, x * 10], dtype=np.uint8)
        if not np.allclose(sampled[i], expected_rgb, atol=2):
            ok = False
            print(f"    pixel ({x},{y}): got {sampled[i]}, expected {expected_rgb}")

    check(ok, "sample_pixels returns correct RGB values")
    frame.release()


# ---------------------------------------------------------------------------
# 10. Pool warmup pre-allocates
# ---------------------------------------------------------------------------
def test_pool_warmup():
    print("\n=== 10. Pool warmup ===")
    from modules.gpu.texture_pool import TexturePool
    from modules.gpu.context import get_context

    ctx = get_context()
    pool = TexturePool(ctx)
    pool.warmup(128, 72, count=3)
    key = (128, 72, 3)
    count = len(pool._pool.get(key, []))
    check(count == 3, f"warmup pre-allocated 3 frames (got {count})")
    pool.release_all()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    tests = [
        test_context,
        test_upload_download,
        test_texture_pool,
        test_blend_normal_full,
        test_blend_opacity_zero,
        test_blend_opacity_half,
        test_blend_add_clamp,
        test_sample_pixels,
        test_pool_warmup,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  [ERROR] {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            FAIL += 1

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)
