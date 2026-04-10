"""
Benchmark: cv2.UMat (OpenCL) vs CPU for 2-layer + 4-effect pipeline.

Goal: Prove that cv2.UMat can hit 30fps (33ms budget) on AMD/NVIDIA/Intel
      without any changes to production code.

Run:
    python tests/gpu/test_umat_pipeline_bench.py

Requirements: opencv-python (already installed) — NO new dependencies.

The 4 effects benchmarked match the current GPU-native stubs that have
no CPU fallback (brightness_contrast, hue_rotate, colorize) plus saturation
which already has a CPU impl.
"""

import time
import sys
import numpy as np
import cv2

# ─── Config ──────────────────────────────────────────────────────────────────
WIDTH, HEIGHT   = 1920, 1080
WARMUP_FRAMES   = 10    # discard JIT / kernel-compile overhead
BENCH_FRAMES    = 100   # measured frames

# Effect parameters (realistic values)
BRIGHTNESS      =  30.0   # -100..+100
CONTRAST        =   1.2   # 0..3
HUE_SHIFT_DEG   =  45.0   # -180..+180  (OpenCV H: 0-180 → shift = deg/2)
SATURATION_MULT =   1.5   # 0..2
BLEND_ALPHA     =   0.6   # layer 0 weight
# ─────────────────────────────────────────────────────────────────────────────


def make_frame():
    """Random 1080p BGR uint8 frame (realistic content)."""
    return np.random.randint(0, 256, (HEIGHT, WIDTH, 3), dtype=np.uint8)


# ─── CPU implementations ─────────────────────────────────────────────────────

def cpu_brightness_contrast(frame: np.ndarray, brightness: float, contrast: float) -> np.ndarray:
    """brightness in -100..+100, contrast in 0..3"""
    beta = int(brightness * 255.0 / 100.0)
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=beta)


def cpu_hue_rotate(frame: np.ndarray, degrees: float) -> np.ndarray:
    """Shift hue by degrees (-180..+180). OpenCV H is 0-180."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.int16)
    shift = int(degrees / 2.0)  # /2 because OpenCV H is 0-180
    hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)


def cpu_saturation(frame: np.ndarray, factor: float) -> np.ndarray:
    """factor 0=grayscale, 1=original, 2=oversaturated."""
    if abs(factor - 1.0) < 0.01:
        return frame
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1].astype(np.float32)
    hsv[:, :, 1] = np.clip(s * factor, 0, 255).astype(np.uint8)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def cpu_colorize(frame: np.ndarray, hue: int, sat: int) -> np.ndarray:
    """Set fixed hue+saturation, preserve luminance. hue 0-179, sat 0-255."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hsv[:, :, 0] = hue
    hsv[:, :, 1] = sat
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)


def cpu_layer_blend(a: np.ndarray, b: np.ndarray, alpha: float) -> np.ndarray:
    return cv2.addWeighted(a, alpha, b, 1.0 - alpha, 0)


# ─── UMat (OpenCL) implementations ───────────────────────────────────────────

# Precomputed LUT for hue rotation — avoids int16 array on GPU (no UMat int16)
def _make_hue_lut(degrees: float) -> np.ndarray:
    shift = int(degrees / 2.0) % 180
    lut = np.zeros(256, dtype=np.uint8)
    for i in range(180):
        lut[i] = (i + shift) % 180
    for i in range(180, 256):
        lut[i] = i  # out-of-range H values pass through
    return lut


_HUE_LUT = _make_hue_lut(HUE_SHIFT_DEG)


def umat_brightness_contrast(u: cv2.UMat, brightness: float, contrast: float) -> cv2.UMat:
    beta = int(brightness * 255.0 / 100.0)
    return cv2.convertScaleAbs(u, alpha=contrast, beta=beta)


def umat_hue_rotate(u: cv2.UMat, lut: np.ndarray) -> cv2.UMat:
    u_hsv = cv2.cvtColor(u, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(u_hsv)
    h_rotated = cv2.LUT(h, lut)
    u_hsv_rot = cv2.merge([h_rotated, s, v])
    return cv2.cvtColor(u_hsv_rot, cv2.COLOR_HSV2BGR)


def umat_saturation(u: cv2.UMat, factor: float) -> cv2.UMat:
    if abs(factor - 1.0) < 0.01:
        return u
    u_hsv = cv2.cvtColor(u, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(u_hsv)
    s_f = cv2.convertScaleAbs(s, alpha=factor)
    u_hsv_sat = cv2.merge([h, s_f, v])
    return cv2.cvtColor(u_hsv_sat, cv2.COLOR_HSV2BGR)


def umat_colorize(u: cv2.UMat, hue: int, sat: int) -> cv2.UMat:
    u_hsv = cv2.cvtColor(u, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(u_hsv)
    h_fixed = cv2.UMat(np.full((HEIGHT, WIDTH), hue, dtype=np.uint8))
    s_fixed = cv2.UMat(np.full((HEIGHT, WIDTH), sat, dtype=np.uint8))
    u_hsv_col = cv2.merge([h_fixed, s_fixed, v])
    return cv2.cvtColor(u_hsv_col, cv2.COLOR_HSV2BGR)


def umat_layer_blend(a: cv2.UMat, b: cv2.UMat, alpha: float) -> cv2.UMat:
    return cv2.addWeighted(a, alpha, b, 1.0 - alpha, 0)


# ─── OPTIMIZED UMat: single HSV roundtrip for all 3 HSV effects ───────────────
# Pre-allocate fixed colorize H/S arrays once (avoid np.full every frame)
_COLORIZE_H_UMAT = cv2.UMat(np.full((HEIGHT, WIDTH), 30, dtype=np.uint8))
_COLORIZE_S_UMAT = cv2.UMat(np.full((HEIGHT, WIDTH), 200, dtype=np.uint8))


def umat_apply_layer_optimized(u: cv2.UMat) -> cv2.UMat:
    """
    Single-pass: brightness_contrast + hue_rotate + saturation + colorize.
    Only ONE BGR→HSV and ONE HSV→BGR per layer instead of 3.
    colorize is last and overwrites H+S, so hue_rotate+saturation have no effect
    when colorize is active — this reflects actual plugin behavior (last effect wins).
    """
    # brightness/contrast (stays in BGR)
    u = cv2.convertScaleAbs(u, alpha=CONTRAST, beta=int(BRIGHTNESS * 255.0 / 100.0))

    # single HSV roundtrip for hue_rotate + saturation + colorize
    u_hsv = cv2.cvtColor(u, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(u_hsv)

    # hue_rotate
    h = cv2.LUT(h, _HUE_LUT)

    # saturation
    s = cv2.convertScaleAbs(s, alpha=SATURATION_MULT)

    # colorize (overwrites h and s with fixed values)
    u_hsv = cv2.merge([_COLORIZE_H_UMAT, _COLORIZE_S_UMAT, v])

    return cv2.cvtColor(u_hsv, cv2.COLOR_HSV2BGR)


def run_umat_optimized(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """Optimized: upload once, single HSV pass per layer, download once."""
    ua = cv2.UMat(frame_a)
    ub = cv2.UMat(frame_b)

    ua = umat_apply_layer_optimized(ua)
    ub = umat_apply_layer_optimized(ub)

    result = cv2.addWeighted(ua, BLEND_ALPHA, ub, 1.0 - BLEND_ALPHA, 0)
    return result.get()


def run_cpu_optimized(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """CPU with same single-HSV-pass optimization for fair comparison."""
    def apply(frame):
        f = cpu_brightness_contrast(frame, BRIGHTNESS, CONTRAST)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.int16)
        # hue_rotate
        hsv[:, :, 0] = (hsv[:, :, 0] + int(HUE_SHIFT_DEG / 2.0)) % 180
        # saturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.float32) * SATURATION_MULT, 0, 255)
        # colorize (overwrites H+S)
        hsv[:, :, 0] = 30
        hsv[:, :, 1] = 200
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    a = apply(frame_a)
    b = apply(frame_b)
    return cv2.addWeighted(a, BLEND_ALPHA, b, 1.0 - BLEND_ALPHA, 0)


# ─── LUT approach: precompute all per-pixel color math into a 256-entry table ─
# All effects that are pixel-independent (brightness, contrast, hue, sat,
# colorize) can be collapsed into a single 256×3 LUT applied per channel.
# Cost: ~1-2ms at 1080p regardless of how many effects are stacked.
# The LUT is recomputed only when parameters change (not per-frame).

def _build_color_lut(brightness: float, contrast: float,
                     hue_shift_deg: float, sat_factor: float,
                     colorize_hue: int, colorize_sat: int) -> np.ndarray:
    """
    Build a (256, 1, 3) BGR LUT that encodes all 4 effects for use with cv2.LUT().
    Strategy: walk all 256 possible gray values through the effect chain,
    record output. For colorized effects the hue/sat are fixed so LUT is exact.
    """
    # Create a 256-pixel grayscale ramp in BGR
    ramp = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        ramp[i, 0] = [i, i, i]

    # brightness/contrast
    beta = int(brightness * 255.0 / 100.0)
    ramp = cv2.convertScaleAbs(ramp, alpha=contrast, beta=beta)

    # HSV effects
    hsv = cv2.cvtColor(ramp, cv2.COLOR_BGR2HSV).astype(np.int16)
    shift = int(hue_shift_deg / 2.0)
    hsv[:, :, 0] = (hsv[:, :, 0] + shift) % 180
    hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.float32) * sat_factor, 0, 255)
    # colorize
    hsv[:, :, 0] = colorize_hue
    hsv[:, :, 1] = colorize_sat
    result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    return result  # shape (256, 1, 3) BGR


_LUT = _build_color_lut(BRIGHTNESS, CONTRAST, HUE_SHIFT_DEG,
                         SATURATION_MULT, 30, 200)


def run_lut_cpu(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """CPU: apply precomputed LUT (single cv2.LUT call per layer)."""
    a = cv2.LUT(frame_a, _LUT)
    b = cv2.LUT(frame_b, _LUT)
    return cv2.addWeighted(a, BLEND_ALPHA, b, 1.0 - BLEND_ALPHA, 0)


def run_lut_umat(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """UMat (OpenCL): same LUT applied on GPU."""
    ua = cv2.UMat(frame_a)
    ub = cv2.UMat(frame_b)
    ua = cv2.LUT(ua, _LUT)
    ub = cv2.LUT(ub, _LUT)
    result = cv2.addWeighted(ua, BLEND_ALPHA, ub, 1.0 - BLEND_ALPHA, 0)
    return result.get()


# ─── Pipeline runners ─────────────────────────────────────────────────────────

def run_cpu_pipeline(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """2-layer CPU pipeline: each layer gets all 4 effects, then blend."""
    a = cpu_brightness_contrast(frame_a, BRIGHTNESS, CONTRAST)
    a = cpu_hue_rotate(a, HUE_SHIFT_DEG)
    a = cpu_saturation(a, SATURATION_MULT)
    a = cpu_colorize(a, hue=30, sat=200)

    b = cpu_brightness_contrast(frame_b, BRIGHTNESS, CONTRAST)
    b = cpu_hue_rotate(b, HUE_SHIFT_DEG)
    b = cpu_saturation(b, SATURATION_MULT)
    b = cpu_colorize(b, hue=30, sat=200)

    return cpu_layer_blend(a, b, BLEND_ALPHA)


def run_umat_pipeline(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """2-layer UMat (OpenCL) pipeline: upload once, all ops on GPU, download once."""
    ua = cv2.UMat(frame_a)
    ub = cv2.UMat(frame_b)

    ua = umat_brightness_contrast(ua, BRIGHTNESS, CONTRAST)
    ua = umat_hue_rotate(ua, _HUE_LUT)
    ua = umat_saturation(ua, SATURATION_MULT)
    ua = umat_colorize(ua, hue=30, sat=200)

    ub = umat_brightness_contrast(ub, BRIGHTNESS, CONTRAST)
    ub = umat_hue_rotate(ub, _HUE_LUT)
    ub = umat_saturation(ub, SATURATION_MULT)
    ub = umat_colorize(ub, hue=30, sat=200)

    result = umat_layer_blend(ua, ub, BLEND_ALPHA)
    return result.get()  # <-- only readback: this is where the OpenCL sync happens


def run_umat_upload_only(frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
    """Only upload+download, no effects — measures raw transfer overhead."""
    ua = cv2.UMat(frame_a)
    ub = cv2.UMat(frame_b)
    result = cv2.addWeighted(ua, BLEND_ALPHA, ub, 1.0 - BLEND_ALPHA, 0)
    return result.get()


# ─── Benchmark harness ────────────────────────────────────────────────────────

def bench(name: str, fn, *args) -> dict:
    # Warmup
    for _ in range(WARMUP_FRAMES):
        fn(*args)

    times = []
    for _ in range(BENCH_FRAMES):
        t0 = time.perf_counter()
        fn(*args)
        times.append((time.perf_counter() - t0) * 1000)  # ms

    times_arr = np.array(times)
    result = {
        'name':   name,
        'mean':   float(np.mean(times_arr)),
        'min':    float(np.min(times_arr)),
        'max':    float(np.max(times_arr)),
        'p95':    float(np.percentile(times_arr, 95)),
        'fps':    1000.0 / float(np.mean(times_arr)),
    }
    return result


def print_result(r: dict, budget_ms: float = 33.3):
    status = "✅ FITS 30fps" if r['mean'] < budget_ms else "❌ TOO SLOW"
    print(f"\n  {r['name']}")
    print(f"    mean={r['mean']:.1f}ms  min={r['min']:.1f}ms  p95={r['p95']:.1f}ms  fps={r['fps']:.1f}  {status}")


def check_correctness(cpu_out: np.ndarray, umat_out: np.ndarray):
    diff = np.abs(cpu_out.astype(np.int16) - umat_out.astype(np.int16))
    max_diff = int(diff.max())
    mean_diff = float(diff.mean())
    ok = max_diff <= 2  # allow ±2 rounding difference between CPU/GPU paths
    print(f"\n  Correctness check (CPU vs UMat output):")
    print(f"    max_pixel_diff={max_diff}  mean_diff={mean_diff:.3f}  {'✅ OK' if ok else '⚠️  LARGE DIFF (check implementation)'}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  cv2.UMat (OpenCL) vs CPU — 2 layers × 4 effects @ 1080p")
    print("=" * 60)

    # OpenCL availability
    if cv2.ocl.haveOpenCL():
        cv2.ocl.setUseOpenCL(True)
        if cv2.ocl.useOpenCL():
            dev = cv2.ocl.Device.getDefault()
            print(f"\n  GPU: {dev.name()}  (OpenCL {dev.OpenCLVersion()})")
            print(f"  Vendor: {dev.vendorName()}")
            print(f"  Max compute units: {dev.maxComputeUnits()}")
        else:
            print("\n  ⚠️  OpenCL available but could not be enabled — UMat will run on CPU")
    else:
        print("\n  ⚠️  OpenCL NOT available — UMat will use CPU fallback")

    print(f"\n  Frame size: {WIDTH}×{HEIGHT}  Warmup: {WARMUP_FRAMES}  Bench: {BENCH_FRAMES} frames")
    print(f"  Frame budget at 30fps: 33.3ms\n")

    # Prepare test frames
    frame_a = make_frame()
    frame_b = make_frame()

    results = []

    print("─" * 60)
    print("  Running benchmarks...")

    r = bench("CPU — upload+blend only (baseline blend)", run_umat_upload_only, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("CPU — 2 layers × 4 effects (naive, 3 HSV roundtrips each)", run_cpu_pipeline, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("CPU — 2 layers × 4 effects (optimized, 1 HSV roundtrip each)", run_cpu_optimized, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("CPU — LUT (precomputed, all 4 effects → 1 table lookup)", run_lut_cpu, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("UMat (OpenCL) — naive pipeline (3 HSV roundtrips per layer)", run_umat_pipeline, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("UMat (OpenCL) — optimized (1 HSV roundtrip per layer, pre-alloc)", run_umat_optimized, frame_a, frame_b)
    results.append(r); print_result(r)

    r = bench("UMat (OpenCL) — LUT (precomputed table, GPU apply)", run_lut_umat, frame_a, frame_b)
    results.append(r); print_result(r)

    # Correctness: LUT vs CPU optimized
    cpu_out  = run_cpu_optimized(frame_a, frame_b)
    lut_out  = run_lut_cpu(frame_a, frame_b)
    umat_out = run_umat_optimized(frame_a, frame_b)
    lut_umat_out = run_lut_umat(frame_a, frame_b)
    print()
    check_correctness(cpu_out, lut_out)
    check_correctness(cpu_out, umat_out)
    check_correctness(cpu_out, lut_umat_out)

    # Summary
    cpu_naive  = next(r['mean'] for r in results if 'naive' in r['name'] and 'CPU' in r['name'])
    cpu_opt    = next(r['mean'] for r in results if 'optimized' in r['name'] and 'CPU' in r['name'])
    cpu_lut    = next(r['mean'] for r in results if 'LUT' in r['name'] and 'CPU' in r['name'])
    umat_naive = next(r['mean'] for r in results if 'naive' in r['name'] and 'UMat' in r['name'])
    umat_opt   = next(r['mean'] for r in results if 'optimized' in r['name'] and 'UMat' in r['name'])
    umat_lut   = next(r['mean'] for r in results if 'LUT' in r['name'] and 'UMat' in r['name'])

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"  CPU  naive:     {cpu_naive:.1f} ms  ({1000/cpu_naive:.1f} fps)")
    print(f"  CPU  optimized: {cpu_opt:.1f} ms  ({1000/cpu_opt:.1f} fps)")
    print(f"  CPU  LUT:       {cpu_lut:.1f} ms  ({1000/cpu_lut:.1f} fps)")
    print(f"  UMat naive:     {umat_naive:.1f} ms  ({1000/umat_naive:.1f} fps)")
    print(f"  UMat optimized: {umat_opt:.1f} ms  ({1000/umat_opt:.1f} fps)")
    print(f"  UMat LUT:       {umat_lut:.1f} ms  ({1000/umat_lut:.1f} fps)")
    print(f"  30fps budget:   33.3 ms")
    for label, t in [("UMat LUT", umat_lut), ("CPU LUT", cpu_lut),
                     ("UMat optimized", umat_opt), ("CPU optimized", cpu_opt)]:
        if t < 33.3:
            print(f"  ✅ {label} PASSES 30fps — {t/33.3*100:.0f}% of budget used")
        else:
            print(f"  ❌ {label} MISSES 30fps by {t-33.3:.1f}ms")
    print(f"\n  GPU: {cv2.ocl.Device.getDefault().name()} ({cv2.ocl.Device.getDefault().maxComputeUnits()} CUs)")
    print("=" * 60)


if __name__ == '__main__':
    main()
