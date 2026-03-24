"""
GPU Accelerator - Phase 3 Performance Optimization

Universal GPU acceleration using OpenCV OpenCL backend.
Supports AMD / NVIDIA / Intel GPUs via OpenCL.
Automatic CPU fallback when no GPU is available.
"""
import cv2
import numpy as np
from ..core.logger import get_logger

logger = get_logger(__name__)


class GPUAccelerator:
    """
    Universal GPU acceleration using OpenCL (AMD/NVIDIA/Intel).
    Automatic CPU fallback if no GPU is available or GPU is disabled in config.

    Usage:
        gpu = get_gpu_accelerator(config)
        frame = gpu.resize(frame, (1920, 1080))
        frame = gpu.warpAffine(frame, M, (w, h))
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.backend = self._init_gpu()
        self.enabled = self.backend != "CPU"

        # Per-operation GPU thresholds (pixels = w * h).
        # Measured on steady-state (warm OpenCL kernels, after JIT compilation):
        #   resize          → GPU 1.7x faster at 1080p+      → enable
        #   warpAffine      → GPU ≈ same as CPU               → disable (no benefit)
        #   warpPerspective → GPU 1.8-2.4x faster at any size → enable
        self._min_pixels_resize  = 640 * 480    # GPU for VGA and above
        self._min_pixels_affine  = 10 ** 9      # effectively disabled (CPU equal)
        self._min_pixels_persp   = 640 * 480    # GPU for VGA and above

        # Cache UMat remap coordinates (upload to GPU once, reuse every frame)
        self._remap_cache = {}

    def _init_gpu(self):
        """Detect and initialise GPU backend. Returns backend name string."""
        if not self.config.get('performance', {}).get('enable_gpu', True):
            logger.info("🔧 GPU acceleration disabled in config")
            return "CPU"

        # Try OpenCL (AMD / NVIDIA / Intel)
        try:
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                if cv2.ocl.useOpenCL():
                    device = cv2.ocl.Device.getDefault()
                    logger.info(f"🚀 GPU backend: OpenCL ({device.name()})")
                    return "OpenCL"
                else:
                    logger.warning("⚠️ OpenCL available but could not be enabled")
            else:
                logger.info("ℹ️ OpenCL not available on this system")
        except Exception as e:
            logger.warning(f"⚠️ OpenCL initialisation failed: {e}")

        logger.info("⚙️ GPU acceleration: using CPU fallback")
        return "CPU"

    # ──────────────────────────────────────────────────────────────────────────
    # GPU-accelerated operations
    # ──────────────────────────────────────────────────────────────────────────

    def resize(self, frame, size, interpolation=cv2.INTER_LINEAR):
        """GPU-accelerated resize. Falls back to CPU for small frames (avoids UMat overhead)."""
        if self.backend == "OpenCL" and frame.shape[0] * frame.shape[1] >= self._min_pixels_resize:
            try:
                result = cv2.resize(cv2.UMat(frame), size, interpolation=interpolation)
                return result.get()
            except Exception as e:
                logger.debug(f"GPU resize failed, falling back to CPU: {e}")
        return cv2.resize(frame, size, interpolation=interpolation)

    def warpAffine(self, frame, M, size, flags=cv2.INTER_LINEAR,
                   borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)):
        """GPU-accelerated warpAffine. Falls back to CPU for small frames."""
        if self.backend == "OpenCL" and frame.shape[0] * frame.shape[1] >= self._min_pixels_affine:
            try:
                result = cv2.warpAffine(cv2.UMat(frame), M, size,
                                        flags=flags, borderMode=borderMode,
                                        borderValue=borderValue)
                return result.get()
            except Exception as e:
                logger.debug(f"GPU warpAffine failed, falling back to CPU: {e}")
        return cv2.warpAffine(frame, M, size, flags=flags,
                              borderMode=borderMode, borderValue=borderValue)

    def warpPerspective(self, frame, M, size, flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0)):
        """GPU-accelerated warpPerspective. Falls back to CPU for small frames."""
        if self.backend == "OpenCL" and frame.shape[0] * frame.shape[1] >= self._min_pixels_persp:
            try:
                result = cv2.warpPerspective(cv2.UMat(frame), M, size,
                                             flags=flags, borderMode=borderMode,
                                             borderValue=borderValue)
                return result.get()
            except Exception as e:
                logger.debug(f"GPU warpPerspective failed, falling back to CPU: {e}")
        return cv2.warpPerspective(frame, M, size, flags=flags,
                                   borderMode=borderMode, borderValue=borderValue)

    def gaussian_blur(self, frame, ksize, sigma=0):
        """GPU-accelerated GaussianBlur.
        ksize: odd kernel size, or 0 to auto-derive from sigma.
        sigma: Gaussian sigma (0 = auto from ksize).
        """
        k = (ksize, ksize) if ksize > 0 else (0, 0)
        if self.backend == "OpenCL" and frame.shape[0] * frame.shape[1] >= self._min_pixels_resize:
            try:
                result = cv2.GaussianBlur(cv2.UMat(frame), k, sigma)
                return result.get()
            except Exception as e:
                logger.debug(f"GPU GaussianBlur failed, falling back to CPU: {e}")
        return cv2.GaussianBlur(frame, k, sigma)

    def remap(self, frame, map_x, map_y,
              interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT):
        """GPU-accelerated remap (~15x faster than CPU). Caches UMat map arrays."""
        if self.backend == "OpenCL":
            try:
                cache_key = (id(map_x), id(map_y))
                if cache_key not in self._remap_cache:
                    self._remap_cache[cache_key] = (cv2.UMat(map_x), cv2.UMat(map_y))
                umat_x, umat_y = self._remap_cache[cache_key]
                result = cv2.remap(cv2.UMat(frame), umat_x, umat_y,
                                   interpolation, borderMode=borderMode)
                return result.get()
            except Exception as e:
                logger.debug(f"GPU remap failed, falling back to CPU: {e}")
        return cv2.remap(frame, map_x, map_y, interpolation, borderMode=borderMode)

    def clear_remap_cache(self):
        """Clear cached UMat remap coordinates (call when map arrays change)."""
        self._remap_cache.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Global singleton
# ──────────────────────────────────────────────────────────────────────────────

_gpu_accelerator: GPUAccelerator | None = None


def get_gpu_accelerator(config=None) -> GPUAccelerator:
    """Return the global GPUAccelerator instance (created on first call)."""
    global _gpu_accelerator
    if _gpu_accelerator is None:
        _gpu_accelerator = GPUAccelerator(config)
    return _gpu_accelerator
