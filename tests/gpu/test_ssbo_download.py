"""
Benchmark: GPUFrame.download() SSBO path vs legacy texture.read() path.

Tests:
  1. Correctness: SSBO download returns pixel-accurate results
  2. Timing: compare SSBO vs texture.read() at 1080p

Run from project root:
    python tests/gpu/test_ssbo_download.py
"""
import sys
import os
import time
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

PASS = 0
FAIL = 0


def check(condition, name, detail=""):
    global PASS, FAIL
    if condition:
        print(f"  [PASS] {name}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}" + (f": {detail}" if detail else ""))
        FAIL += 1


def _legacy_download(gpu_frame):
    """Baseline: original texture.read() path."""
    import moderngl
    data = gpu_frame.texture.read()
    arr = np.frombuffer(data, dtype=np.float32).reshape(
        gpu_frame.height, gpu_frame.width, gpu_frame.components
    )
    buf = np.empty_like(arr)
    np.multiply(arr, 255.0, out=buf)
    np.clip(buf, 0, 255, out=buf)
    out = np.empty((gpu_frame.height, gpu_frame.width, gpu_frame.components), dtype=np.uint8)
    np.copyto(out, buf, casting='unsafe')
    return out[:, :, ::-1].copy()  # RGB→BGR


def test_ssbo_correctness():
    """SSBO download must return pixel-accurate BGR values (max_diff ≤ 1)."""
    print("\n=== 1. Correctness: SSBO download matches legacy path ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame

    ctx = get_context()
    H, W = 64, 64
    src = np.zeros((H, W, 3), dtype=np.uint8)
    src[:H//2, :W//2] = [200,  50,  50]
    src[:H//2, W//2:] = [ 50, 200,  50]
    src[H//2:, :W//2] = [ 50,  50, 200]
    src[H//2:, W//2:] = [180, 180,  30]

    gpu = GPUFrame(ctx, W, H, 3)
    gpu.upload(src)

    # SSBO path (new)
    ssbo_result = gpu.download()

    # Legacy path (baseline)
    legacy_result = _legacy_download(gpu)

    diff_vs_src = np.abs(src.astype(np.int32) - ssbo_result.astype(np.int32))
    diff_vs_legacy = np.abs(ssbo_result.astype(np.int32) - legacy_result.astype(np.int32))

    check(diff_vs_src.max() <= 1,
          f"SSBO result matches source (max_diff={diff_vs_src.max()})",
          f"max diff {diff_vs_src.max()} — pixel data wrong?")
    check(diff_vs_legacy.max() <= 1,
          f"SSBO result matches legacy path (max_diff={diff_vs_legacy.max()})",
          f"max diff {diff_vs_legacy.max()} — channel swap or Y-flip issue?")

    gpu.release()


def test_ssbo_timing():
    """Compare SSBO vs texture.read() at 1080p."""
    print("\n=== 2. Timing: SSBO download vs legacy texture.read() (1080p) ===")
    from modules.gpu.context import get_context
    from modules.gpu.frame import GPUFrame
    from modules.gpu import frame as frame_mod

    ctx = get_context()
    H, W = 1080, 1920
    src = np.random.randint(0, 256, (H, W, 3), dtype=np.uint8)

    gpu = GPUFrame(ctx, W, H, 3)
    gpu.upload(src)

    # Warm up both paths
    _ = gpu.download()
    _ = _legacy_download(gpu)

    N = 5

    # SSBO path
    times_ssbo = []
    for _ in range(N):
        t0 = time.perf_counter()
        gpu.download()
        times_ssbo.append((time.perf_counter() - t0) * 1000)

    # Legacy path
    times_legacy = []
    for _ in range(N):
        t0 = time.perf_counter()
        _legacy_download(gpu)
        times_legacy.append((time.perf_counter() - t0) * 1000)

    ms = np.mean(times_ssbo)
    ml = np.mean(times_legacy)
    print(f"  SSBO path   : {ms:.1f} ms  {[f'{t:.1f}' for t in times_ssbo]}")
    print(f"  Legacy path : {ml:.1f} ms  {[f'{t:.1f}' for t in times_legacy]}")
    print(f"  Δ = {ml - ms:+.1f} ms  ({'SSBO faster' if ms < ml else 'legacy faster — unexpected'})")

    check(ms < ml,
          f"SSBO faster than legacy ({ms:.1f} ms vs {ml:.1f} ms)",
          f"SSBO was {ms - ml:.1f} ms slower — AMD stall still present?")

    gpu.release()


if __name__ == '__main__':
    test_ssbo_correctness()
    test_ssbo_timing()

    print(f"\n{'='*50}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL == 0:
        print("✅ SSBO download path working — AMD stall bypassed")
    else:
        print("❌ Check [FAIL] entries above")
    sys.exit(0 if FAIL == 0 else 1)
