"""
GPU-Accelerated Layer Compositor

Architecture:
  Called directly from composite_layers() in manager.py, bypassing blend.py for
  blend modes that benefit from GPU acceleration.

Why this is better than blend.py approach:
  blend.py current approach:
    1. frame.astype(np.float32)   → allocate + copy 25MB for 1080p
    2. math operations            → work on float32
    3. np.clip + astype(uint8)    → allocate + copy again
    Total: ~8-12ms per blend operation at 1080p

  This compositor:
    - add/subtract/multiply: cv2.add/subtract/multiply on uint8 natively (SIMD!)
      no float32 conversion → ~1ms per operation
    - screen/overlay/mask: CuPy float32 on GPU when installed
      → ~0.5ms per operation (vs 8ms CPU float32)
    - normal at 100%: zero-copy direct reference
    - normal with opacity: cv2.addWeighted (same as blend.py fast path)

  For multi-layer setups with add/subtract/multiply blend modes:
    3 layers → 2 blends → ~16ms CPU → ~2ms with this compositor

OpenCL (cv2 UMat):
  Used for add/subtract/multiply when OpenCL is available.
  Threshold: VGA+ frames only (same as Phase 3 resize threshold).
  When OpenCL is off, falls back to plain cv2 on numpy (still avoids float32!).

CuPy (CUDA/ROCm):
  Used for screen/overlay/mask when CuPy is installed.
  Falls back to CPU float32 numpy (same as blend.py) when not available.
"""

import numpy as np
import cv2

try:
    import cupy as cp
    CUPY_AVAILABLE = True
except ImportError:
    cp = None
    CUPY_AVAILABLE = False

from ..core.logger import get_logger

logger = get_logger(__name__)


class GPUCompositor:
    """
    GPU-accelerated layer stack compositor.

    Handles all blend modes:
      normal    → cv2.addWeighted (uint8, fast path at 100% opacity)
      add       → cv2.add (uint8, saturated at 255 — correct!)
      subtract  → cv2.subtract (uint8, saturated at 0 — correct!)
      multiply  → cv2.multiply(scale=1/255) (uint8 normalized — correct!)
      screen    → CuPy float32 (GPU) or numpy float32 (CPU fallback)
      overlay   → CuPy float32 (GPU) or numpy float32 (CPU fallback)
      mask      → CuPy float32 (GPU) or numpy float32 (CPU fallback)

    Falls back to blend.py (returns None) only when:
      - A float mode (screen/overlay/mask) is requested AND CuPy is not installed
        AND the overlay has an RGBA alpha channel (complex case)
    """

    # Only use GPU ops for VGA+ frames (same breakeven as Phase 3 resize)
    _min_pixels = 640 * 480

    # Blend modes handled natively as uint8 — no float32 conversion needed
    _UINT8_MODES = frozenset({'normal', 'add', 'subtract', 'multiply'})

    # Blend modes requiring float32 operations
    _FLOAT_MODES = frozenset({'screen', 'overlay', 'mask'})

    def __init__(self):
        self._has_opencl = cv2.ocl.haveOpenCL() and cv2.ocl.useOpenCL()
        self._logged = False

    def _log_once(self, base_h, base_w):
        if not self._logged:
            self._logged = True
            opencl_str = "OpenCL UMat" if self._has_opencl else "CPU uint8 cv2"
            cupy_str = f"CuPy GPU" if CUPY_AVAILABLE else "CPU float32 numpy"
            logger.debug(
                f"🎮 GPUCompositor active ({base_w}x{base_h}): "
                f"uint8 modes={opencl_str}, float modes={cupy_str}"
            )

    def composite(self, base_frame, overlays):
        """
        Composite base_frame with a list of overlay layers.

        Args:
            base_frame: numpy array (H, W, 3) uint8
            overlays: list of (frame, blend_mode_str, opacity_0_to_1_float)
                      frame may be (H, W, 3) RGB or (H, W, 4) RGBA from mask effect

        Returns:
            Composited numpy (H, W, 3) uint8.
            Returns None if GPU compositor cannot handle the combination —
            caller should fall back to the blend.py CPU path.
        """
        if not overlays:
            return base_frame

        h, w = base_frame.shape[:2]
        use_opencl = self._has_opencl and (w * h >= self._min_pixels)

        self._log_once(h, w)

        # Pre-check: can we handle ALL blend mode + alpha channel combinations?
        # If a float mode is requested AND CuPy is not available AND there's an RGBA
        # overlay → fall back to blend.py which handles this complex case correctly.
        for overlay_frame, mode, _ in overlays:
            if mode in self._FLOAT_MODES and not CUPY_AVAILABLE:
                if overlay_frame is not None and overlay_frame.ndim == 3 and overlay_frame.shape[2] == 4:
                    return None  # Complex RGBA + float mode without CuPy → use blend.py

        result = base_frame

        for overlay_frame, blend_mode, opacity in overlays:
            if overlay_frame is None:
                continue

            # Extract RGBA alpha channel if present (from mask effect output)
            overlay_alpha = None
            if overlay_frame.ndim == 3 and overlay_frame.shape[2] == 4:
                overlay_alpha = overlay_frame[:, :, 3].astype(np.float32) / 255.0
                overlay_frame = overlay_frame[:, :, :3]

            # Resize overlay to match base if needed
            if overlay_frame.shape[:2] != (h, w):
                overlay_frame = cv2.resize(overlay_frame, (w, h), interpolation=cv2.INTER_LINEAR)
                if overlay_alpha is not None:
                    overlay_alpha = cv2.resize(overlay_alpha, (w, h), interpolation=cv2.INTER_LINEAR)

            # ── Fast path: normal at 100% opacity, no alpha mask ──────────────
            if blend_mode == 'normal' and opacity >= 1.0 and overlay_alpha is None:
                result = overlay_frame
                continue

            # ── Float modes: screen, overlay, mask ───────────────────────────
            if blend_mode in self._FLOAT_MODES:
                if CUPY_AVAILABLE:
                    result = self._blend_cupy(result, overlay_frame, overlay_alpha, blend_mode, opacity)
                else:
                    # CuPy not available — use CPU float32 numpy (same quality as blend.py)
                    result = self._blend_float_cpu(result, overlay_frame, overlay_alpha, blend_mode, opacity)
                continue

            # ── uint8 modes: normal, add, subtract, multiply ─────────────────
            if overlay_alpha is not None:
                # RGBA overlay on uint8 mode: composite alpha first, then blend
                # Flatten RGBA → RGB using alpha compositing, then blend RGB
                alpha_3ch = overlay_alpha[:, :, np.newaxis]
                base_f = result.astype(np.float32) / 255.0
                over_f = overlay_frame.astype(np.float32) / 255.0
                overlay_frame = (base_f * (1.0 - alpha_3ch) + over_f * alpha_3ch)
                overlay_frame = np.clip(overlay_frame * 255.0, 0, 255).astype(np.uint8)
                overlay_alpha = None  # Consumed

            result = self._blend_cv2(result, overlay_frame, blend_mode, opacity, use_opencl)

        return result

    def _blend_cv2(self, base, overlay, mode, opacity, use_opencl):
        """
        Blend using cv2 operations on uint8 — NO float32 conversion needed.
        cv2.add/subtract/multiply are SIMD-optimized C++ operations.
        Optional UMat (OpenCL GPU) path when hardware is available.
        """
        if use_opencl:
            b = cv2.UMat(base)
            o = cv2.UMat(overlay)
        else:
            b, o = base, overlay

        if mode == 'normal':
            # Linear blend: (1-opacity)*base + opacity*overlay
            result = cv2.addWeighted(b, 1.0 - opacity, o, opacity, 0)

        elif mode == 'add':
            # Saturated add (clips at 255 — correct for Add blend mode)
            added = cv2.add(b, o)
            if opacity < 1.0:
                result = cv2.addWeighted(b, 1.0 - opacity, added, opacity, 0)
            else:
                result = added

        elif mode == 'subtract':
            # Saturated subtract (clips at 0 — correct for Subtract blend mode)
            subtracted = cv2.subtract(b, o)
            if opacity < 1.0:
                result = cv2.addWeighted(b, 1.0 - opacity, subtracted, opacity, 0)
            else:
                result = subtracted

        elif mode == 'multiply':
            # (base * overlay) / 255 — stays in uint8 domain!
            # cv2.multiply with scale=1/255 does this via SIMD, no float32 needed.
            multiplied = cv2.multiply(b, o, scale=1.0 / 255.0)
            if opacity < 1.0:
                result = cv2.addWeighted(b, 1.0 - opacity, multiplied, opacity, 0)
            else:
                result = multiplied

        else:
            logger.warning(f"GPUCompositor: Unknown blend mode '{mode}', using base")
            return base

        # Download from UMat if needed
        if use_opencl:
            return result.get()
        return result

    def _blend_cupy(self, base, overlay, overlay_alpha, mode, opacity):
        """CuPy float32 blend for screen/overlay/mask — runs on CUDA/ROCm GPU."""
        base_f = cp.asarray(base, dtype=cp.float32) / 255.0
        over_f = cp.asarray(overlay, dtype=cp.float32) / 255.0

        if mode == 'screen':
            # 1 - (1 - base) * (1 - overlay)
            blended = 1.0 - (1.0 - base_f) * (1.0 - over_f)

        elif mode == 'overlay':
            # Combine Multiply (dark) and Screen (bright) based on base value
            mask = base_f < 0.5
            multiply = 2.0 * base_f * over_f
            screen = 1.0 - 2.0 * (1.0 - base_f) * (1.0 - over_f)
            blended = cp.where(mask, multiply, screen)

        elif mode == 'mask':
            # Use overlay luminance as transparency mask for base
            lum = (0.299 * over_f[:, :, 0] +
                   0.587 * over_f[:, :, 1] +
                   0.114 * over_f[:, :, 2])
            blended = base_f * lum[:, :, cp.newaxis]

        else:
            blended = over_f  # fallback (pre-check prevents this)

        # Apply per-pixel overlay alpha (from RGBA mask effect output)
        if overlay_alpha is not None:
            alpha_gpu = cp.asarray(overlay_alpha)[:, :, cp.newaxis]
            blended = base_f * (1.0 - alpha_gpu) + blended * alpha_gpu

        # Apply layer opacity
        if opacity < 1.0:
            blended = base_f * (1.0 - opacity) + blended * opacity

        return (cp.clip(blended, 0.0, 1.0) * 255.0).astype(cp.uint8).get()

    def _blend_float_cpu(self, base, overlay, overlay_alpha, mode, opacity):
        """CPU float32 fallback for screen/overlay/mask when CuPy is not available."""
        base_f = base.astype(np.float32) / 255.0
        over_f = overlay.astype(np.float32) / 255.0

        if mode == 'screen':
            blended = 1.0 - (1.0 - base_f) * (1.0 - over_f)

        elif mode == 'overlay':
            mask = base_f < 0.5
            multiply = 2.0 * base_f * over_f
            screen = 1.0 - 2.0 * (1.0 - base_f) * (1.0 - over_f)
            blended = np.where(mask, multiply, screen)

        elif mode == 'mask':
            lum = (0.299 * over_f[:, :, 0] +
                   0.587 * over_f[:, :, 1] +
                   0.114 * over_f[:, :, 2])
            blended = base_f * lum[:, :, np.newaxis]

        else:
            blended = over_f

        if overlay_alpha is not None:
            alpha_3ch = overlay_alpha[:, :, np.newaxis]
            blended = base_f * (1.0 - alpha_3ch) + blended * alpha_3ch

        if opacity < 1.0:
            blended = base_f * (1.0 - opacity) + blended * opacity

        return np.clip(blended * 255.0, 0, 255).astype(np.uint8)


_gpu_compositor: GPUCompositor | None = None


def get_gpu_compositor() -> GPUCompositor:
    """Get the global GPUCompositor singleton."""
    global _gpu_compositor
    if _gpu_compositor is None:
        _gpu_compositor = GPUCompositor()
    return _gpu_compositor
