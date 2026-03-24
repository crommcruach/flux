"""
GPU Acceleration Benchmark - Phase 3 Verification
Run from workspace root:
    python tools/benchmark_gpu.py
"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import cv2
import numpy as np
from src.modules.gpu.accelerator import GPUAccelerator

WARMUP   = 10
RUNS     = 50

# Test both a "small" and "large" frame to show threshold behaviour
CASES = [
    {"label": "1080p → 720p",  "src": (1920, 1080), "dst": (1280, 720)},
    {"label": "4K → 1080p",    "src": (3840, 2160), "dst": (1920, 1080)},
]


def bench(label, fn, runs=RUNS):
    # warmup
    for _ in range(WARMUP):
        fn()
    t0 = time.perf_counter()
    for _ in range(runs):
        fn()
    elapsed = time.perf_counter() - t0
    ms = elapsed / runs * 1000
    return ms


def main():
    print("=" * 60)
    print("  GPU Acceleration Benchmark")
    print("=" * 60)

    # Init GPU (OpenCL)
    gpu_enabled = GPUAccelerator({'performance': {'enable_gpu': True}})

    print(f"\nGPU backend detected : {gpu_enabled.backend}")
    print(f"Runs   : {RUNS} (after {WARMUP} warmup)\n")

    for case in CASES:
        SRC_SIZE = case["src"]
        DST_SIZE = case["dst"]
        w, h = SRC_SIZE
        frame = np.random.randint(0, 255, (h, w, 3), dtype=np.uint8)

        print(f"── {case['label']} ({w}x{h} → {DST_SIZE[0]}x{DST_SIZE[1]}) ──")
        results = []

        cpu_ms = bench("CPU resize",  lambda: cv2.resize(frame, DST_SIZE))
        gpu_ms = bench("GPU resize",  lambda: gpu_enabled.resize(frame, DST_SIZE))
        results.append(("resize", cpu_ms, gpu_ms))

        M = cv2.getRotationMatrix2D((w / 2, h / 2), 15, 1.0)
        cpu_ms = bench("CPU warpAffine", lambda: cv2.warpAffine(frame, M, (w, h)))
        gpu_ms = bench("GPU warpAffine", lambda: gpu_enabled.warpAffine(frame, M, (w, h)))
        results.append(("warpAffine", cpu_ms, gpu_ms))

        src_pts = np.float32([[0,0],[w,0],[w,h],[0,h]])
        dst_pts = np.float32([[50,50],[w-50,0],[w,h],[0,h]])
        Mp = cv2.getPerspectiveTransform(src_pts, dst_pts)
        cpu_ms = bench("CPU warpPersp", lambda: cv2.warpPerspective(frame, Mp, (w, h)))
        gpu_ms = bench("GPU warpPersp", lambda: gpu_enabled.warpPerspective(frame, Mp, (w, h)))
        results.append(("warpPerspective", cpu_ms, gpu_ms))

        print(f"  {'Operation':<18} {'CPU ms':>8} {'GPU ms':>8} {'Speedup':>9}")
        print("  " + "-" * 48)
        for op, cpu, gpu in results:
            speedup = cpu / gpu if gpu > 0 else float('inf')
            mark = "🚀" if speedup > 2 else ("⚡" if speedup > 1.1 else ("⚠️ slower" if speedup < 0.95 else "≈ same"))
            tag  = "(CPU fallback)" if gpu == cpu else ""
            print(f"  {op:<18} {cpu:>8.2f} {gpu:>8.2f} {speedup:>7.1f}x  {mark} {tag}")
        print()

    print()
    if gpu_enabled.backend == "OpenCL":
        print("✅ GPU (OpenCL) is active.")
        print("   Small frames (< 1080p) automatically fall back to CPU to avoid UMat overhead.")
        print("   Large frames (≥ 1080p resize, ≥ 720p warp) use GPU.")
    else:
        print("⚠️  No GPU detected – running on CPU. Check OpenCL drivers.")

    # also show what's actually in the singleton used by the app
    from src.modules.gpu.accelerator import get_gpu_accelerator as get_app_gpu
    app_gpu = get_app_gpu()
    print(f"\n   App singleton backend : {app_gpu.backend}")
    print("=" * 60)


if __name__ == "__main__":
    main()
